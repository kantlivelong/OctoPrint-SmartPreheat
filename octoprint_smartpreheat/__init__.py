# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 Shawn Bruce - Released under terms of the AGPLv3 License"

import octoprint.plugins
from octoprint.util.version import is_octoprint_compatible
from octoprint.events import Events
import threading
import textwrap
import re

class SmartPreheat(octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.EventHandlerPlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self.default_smartpreheat_script = textwrap.dedent(
        """
        {# Init vars #}
        {%- set bed = plugins.smartpreheat.bed|default(75 , true) -%}
        {%- set list = plugins.smartpreheat.tools|default({-1: 195}, true) -%}

        {%- if printer_profile.heatedBed -%}
        ; Set bed
        M117 Set bed: {{ bed }}
        M190 S{{- (bed * 0.8)|round -}} ; Wait for Bed
        M140 S{{- bed -}} ; Set Bed
        {% endif %}

        ; Set tool temps
        {%- for tool, temp in list.items() %}
        M117 Set {{ 'default tool' if tool < 0 else 'tool ' + tool|string }} to temp {{ temp }}
        M104 {{- '' if tool < 0 else ' T' + tool|string }} S{{- temp -}} ; Set Hotend
        {%- endfor %}

        {%- if printer_profile.heatedBed -%}
        ; Wait bed
        M190 S{{- bed -}} ; Wait for Bed
        {% endif %}

        ; Wait tool temps
        {%- for tool, temp in list.items() %}
        M109 {{- '' if tool < 0 else ' T' + tool|string }} S{{- temp -}} ; Wait for Hotend
        {%- endfor %}

        G28 X Y
        M400; wait
        M117 PreHeat DONE
        """)

        self.temp_data = None
        self._scan_event = threading.Event()
        self._scan_event.set()

    def initialize(self):
        if is_octoprint_compatible("<=1.3.6"):
            raise Exception("OctoPrint 1.3.7 or greater required.")

    def on_settings_initialized(self):
        scripts = self._settings.listScripts("gcode")
        if not "snippets/doSmartPreheat" in scripts:
            script = self.default_smartpreheat_script
            self._settings.saveScript("gcode", "snippets/doSmartPreheat", u'' + script.replace("\r\n", "\n").replace("\r", "\n"))

    def get_settings_defaults(self):
        return dict(dummy=False)

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings = True)
        ]

    def get_assets(self):
        return dict(
            js = ["js/smartpreheat.js"]
        )

    def get_temps_from_file(self, selected_file):
        path_on_disk = octoprint.server.fileManager.path_on_disk(octoprint.filemanager.FileDestinations.LOCAL, selected_file)

        default_bed = 55
        default_tool = 195

        temps = dict(tools=dict(), bed=None)
        toolNum = None
        lineNum = 0

        # https://regex101.com/
        regex_extr = re.compile(r'^\s*?G(?:0|1)+.*?E\d+')
        regex_temp = re.compile(r'^\s*?M(?P<code>109|190)+(?:\s+(?:S(?P<temp>\d+))|(?:\s+T(?P<tool>\d+)))+')
        regex_tool = re.compile(r'^\s*?T(?P<tool>\d+)')

        self._logger.debug("Scanning:\t%s", selected_file)
        with open(path_on_disk, "r") as file_:
            for line in file_:
                if lineNum < 1000:
                    lineNum += 1
                else:
                    break
                if toolNum is None:
                    match = regex_tool.search(line)
                    if match:
                        toolNum = int(match.group('tool').replace('\D',''))
                        self._logger.debug("Line %d:\tfound tool number = %s", lineNum, toolNum)
                        continue
                match = regex_temp.search(line)
                if match:
                    temp = int(match.group('temp').replace('\D',''))
                    if temp:
                        # self._logger.debug("Line %d: assigned tool %s", lineNum, match.groupdict())
                        if match.group('code') == '109' and not len(temps["tools"]):
                            if match.group('tool'): toolNum = int(match.group('tool').replace('\D',''))
                            if toolNum is None: toolNum = -1
                            temps["tools"][toolNum] = temp
                            self._logger.debug("Line %d:\tassigned tool %s temp = %s", lineNum, toolNum, temps["tools"][toolNum])
                            if temps["bed"]: break
                        elif match.group('code') == '190' and not temps["bed"]:
                            temps["bed"] = temp
                            self._logger.debug("Line %d:\tassigned bed temp = %s", lineNum, temps["bed"])
                            if len(temps["tools"]): break
                elif regex_extr.search(line): break

            if not temps["bed"]:
                temps["bed"] = default_bed
                self._logger.debug("Default:\tassigned bed temp = %s", lineNum, default_bed)

            if not len(temps["tools"]):
                temps["tools"] = {-1: default_tool}
                self._logger.debug("Default:\tassigned tool %s temp %s", lineNum, -1, default_tool)
            elif not temps["tools"][temps["tools"].keys()[0]]:
                temps["tools"][temps["tools"].keys()[0]] =  default_tool
                self._logger.debug("Default:\tassigned tool %s temp %s", lineNum, temps["tools"].keys()[0], default_tool)

            self._logger.debug("Line %d:\tRead %s", lineNum, 'complete' if lineNum < 1000 else 'abort')

        return temps

    def on_event(self, event, payload):
        if event == Events.FILE_SELECTED:
            self._scan_event.clear()

            self.temp_data = None
            if payload['origin'] == 'local':
                self.temp_data = self.get_temps_from_file(payload['path'])

            self._scan_event.set()

    def populate_script_variables(self, comm_instance, script_type, script_name, *args, **kwargs):
        if not script_type == "gcode":
            return None

        self._scan_event.wait()

        return (None, None, self.temp_data)

    def on_settings_save(self, data):
        if data.has_key("scripts_gcode_snippets_doSmartPreheat"):
            script = data["scripts_gcode_snippets_doSmartPreheat"]
            self._settings.saveScript("gcode", "snippets/doSmartPreheat", u'' + script.replace("\r\n", "\n").replace("\r", "\n"))

    def get_update_information(self):
        return dict(
            smartpreheat=dict(
                displayName="Smart Preheat",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="kantlivelong",
                repo="OctoPrint-SmartPreheat",
                current=self._plugin_version,

                # update method: pip w/ dependency links
                pip="https://github.com/kantlivelong/OctoPrint-SmartPreheat/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "Smart Preheat"
__plugin_pythoncompat__ = ">=2.7,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = SmartPreheat()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
        "octoprint.comm.protocol.scripts": __plugin_implementation__.populate_script_variables
    }
