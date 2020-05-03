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
        ; Wait for bed to reach 80% of required temp then set to required temp
        {% if printer_profile.heatedBed %}
        M190 S{{ (plugins.smartpreheat.bed * 0.8)|round }}
        M140 S{{ plugins.smartpreheat.bed }}
        {% endif %}

        ; Set tool temps
        {% for tool, temp in plugins.smartpreheat.tools.items() %}
        M104 T{{ tool }} S{{ temp }}
        {% endfor %}

        ; Wait for bed
        {% if printer_profile.heatedBed %}
        M190 S{{ plugins.smartpreheat.bed }}
        {% endif %}

        ; Wait for tools
        {% for tool, temp in plugins.smartpreheat.tools.items() %}
        M109 T{{ tool }} S{{ temp }}
        {% endfor %}
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
        toolNum = 0
        lineNum = 0
        self._logger.debug("Parsing g-code file, Path=%s", path_on_disk)
        with open(path_on_disk, "r") as file:
            for line in file:
                lineNum += 1

                gcode = octoprint.util.comm.gcode_command_for_cmd(line)
                extrusionMatch = octoprint.util.comm.regexes_parameters["floatE"].search(line)
                if gcode == "G1" and extrusionMatch:
                    self._logger.debug("Line %d: Detected first extrusion. Read complete.", lineNum)
                    break

                toolMatch = octoprint.util.comm.regexes_parameters["intT"].search(line)
                if toolMatch:
                    self._logger.debug("Line %d: Detected SetTool. Line=%s", lineNum, line)
                    toolNum = int(toolMatch.group("value"))

                if gcode in ('M104', 'M109', 'M140', 'M190'):
                    self._logger.debug("Line %d: Detected SetTemp. Line=%s", lineNum, line)

                    tempMatch = octoprint.util.comm.regexes_parameters["floatS"].search(line)
                    if tempMatch:
                        temp = int(tempMatch.group("value"))

                        if gcode in ("M104", "M109"):
                            self._logger.debug("Line %d: Tool %s = %s", lineNum, toolNum, temp)
                            temps["tools"][toolNum] = temp
                        elif gcode in ("M140", "M190"):
                            self._logger.debug("Line %d: Bed = %s", lineNum, temp)
                            temps["bed"] = temp

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
