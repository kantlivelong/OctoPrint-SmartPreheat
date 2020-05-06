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
        M117 Set bed: {{ bed|int }}
        M190 S{{- (bed|int * 0.8)|round|int -}} ; Wait for Bed
        M140 S{{- bed|int -}} ; Set Bed
        {% endif %}

        ; Set tool temps
        {%- for tool, temp in list.items() %}
        M117 Set {{ 'default tool' if tool|int < 0 else 'tool ' + tool|int|string }} to temp {{ temp|int }}
        M104 {{- '' if tool|int < 0 else ' T' + tool|int|string }} S{{- temp|int -}} ; Set Hotend
        {%- endfor %}

        {%- if printer_profile.heatedBed -%}
        ; Wait bed
        M190 S{{- bed -}} ; Wait for Bed
        {% endif %}

        ; Wait tool temps
        {%- for tool, temp in list.items() %}
        M109 {{- '' if tool|int < 0 else ' T' + tool|int|string }} S{{- temp|int -}} ; Wait for Hotend
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

        temps = dict(tools=dict(), bed=None)
        toolNum = None
        lineNum = 0

        self._logger.debug("gcode alalysis started: %s", selected_file)
        with open(path_on_disk, "r") as file_:
            for line in file_:
                if lineNum < 1000:
                    lineNum += 1
                else:
                    break
                if not toolNum:
                    match = re.match(r'^\s*?T(\d+)', line) # https://regex101.com/
                    if match:
                        toolNum = match.group(1)
                        self._logger.debug("Line %d: found tool number = %s", lineNum, toolNum)
                        continue
                match = re.match(r'^\s*?M(109|190)+\s', line) # r'M(104|109|140|190).*S.*'
                if match:
                    code = match.group(1)
                    line = line.split(';')[0].strip()
                    temp = re.match(r'.*?S(\d+)', line)
                    if temp:
                        if code == '109' and not len(temps["tools"]): # in ["104", "109"]
                            match = re.match(r'.*?T(\d+)', line)
                            if match: toolNum = match.group(1)
                            if not toolNum: toolNum = -1
                            temps["tools"][toolNum] = temp.group(1)
                            self._logger.debug("Line %d: assigned tool %s temp %s", lineNum, toolNum, temps["tools"][toolNum])
                            if temps["bed"]: break
                        elif code == '190' and not temps["bed"]: # in ["140", "190"]
                            temps["bed"] = temp.group(1)
                            self._logger.debug("Line %d: assigned bed temp = %s", lineNum, temps["bed"])
                            if len(temps["tools"]): break
                elif re.match(r'^\s*?G(0|1)+.*?E\d*?[^;]', line):
                    break
            self._logger.debug("Line %d: Read complete" % lineNum)
        return temps

    def on_event(self, event, payload):
        if event is Events.PRINT_STARTED: # in [Events.FILE_SELECTED, Events.PRINT_STARTED]
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
