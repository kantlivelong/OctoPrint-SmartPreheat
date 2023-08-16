# coding=utf-8
from __future__ import absolute_import

__author__ = "Shawn Bruce <kantlivelong@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2020 Shawn Bruce - Released under terms of the AGPLv3 License"

import octoprint.plugins
from octoprint.util.version import is_octoprint_compatible
import textwrap

class SmartPreheat(octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self.default_smartpreheat_script = textwrap.dedent(
        """
        ; Wait for bed to reach 80% of required temp then set to required temp
        {% if printer_profile.heatedBed and plugins.smartpreheat.bed != None %}
        M190 S{{ (plugins.smartpreheat.bed * 0.8)|round }}
        M140 S{{ plugins.smartpreheat.bed }}
        {% endif %}

        ; Set tool temps
        {% for tool, temp in plugins.smartpreheat.tools.items() %}
        M104 T{{ tool }} S{{ temp }}
        {% endfor %}

        ; Wait for bed
        {% if printer_profile.heatedBed and plugins.smartpreheat.bed != None %}
        M190 S{{ plugins.smartpreheat.bed }}
        {% endif %}

        ; Wait for tools
        {% for tool, temp in plugins.smartpreheat.tools.items() %}
        M109 T{{ tool }} S{{ temp }}
        {% endfor %}
        """)

        self.temp_data = None

    def initialize(self):
        if is_octoprint_compatible("<=1.3.6"):
            raise Exception("OctoPrint 1.3.7 or greater required.")

    def on_settings_initialized(self):
        scripts = self._settings.listScripts("gcode")
        if not "snippets/doSmartPreheat" in scripts:
            script = self.default_smartpreheat_script
            self._settings.saveScript("gcode", "snippets/doSmartPreheat", u'' + script.replace("\r\n", "\n").replace("\r", "\n"))
        elif "{% if printer_profile.heatedBed %}" in scripts["snippets/doSmartPreheat"]:
            script = scripts["snippets/doSmartPreheat"].replace("{% if printer_profile.heatedBed %}", "{% if printer_profile.heatedBed and plugins.smartpreheat.bed != None %}")
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
        currentToolNum = 0
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

                if gcode and gcode.startswith("T"):
                    toolMatch = octoprint.util.comm.regexes_parameters["intT"].search(line)
                    if toolMatch:
                        self._logger.debug("Line %d: Detected SetTool. Line=%s", lineNum, line)
                        currentToolNum = int(toolMatch.group("value"))

                if gcode in ('M104', 'M109', 'M140', 'M190'):
                    self._logger.debug("Line %d: Detected SetTemp. Line=%s", lineNum, line)

                    toolMatch = octoprint.util.comm.regexes_parameters["intT"].search(line)
                    if toolMatch:
                        toolNum = int(toolMatch.group("value"))
                    else:
                        toolNum = currentToolNum

                    tempMatch = octoprint.util.comm.regexes_parameters["floatS"].search(line)
                    if tempMatch:
                        temp = float(tempMatch.group("value"))

                        if gcode in ("M104", "M109"):
                            self._logger.debug("Line %d: Tool %s = %s", lineNum, toolNum, temp)
                            temps["tools"][toolNum] = temp
                        elif gcode in ("M140", "M190"):
                            self._logger.debug("Line %d: Bed = %s", lineNum, temp)
                            temps["bed"] = temp

        self._logger.debug("Temperatures: %r", temps)
        return temps

    def populate_script_variables(self, comm_instance, script_type, script_name, *args, **kwargs):
        if not script_type == "gcode":
            return None

        if script_name == 'beforePrintStarted':
            current_data = self._printer.get_current_data()

            if current_data['job']['file']['origin'] == octoprint.filemanager.FileDestinations.LOCAL:
                self.temp_data = self.get_temps_from_file(current_data['job']['file']['path'])

        return (None, None, self.temp_data)

    def on_settings_save(self, data):
        if 'scripts_gcode_snippets_doSmartPreheat' in data:
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
