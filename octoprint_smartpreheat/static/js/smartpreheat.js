$(function() {
    function SmartPreheatViewModel(parameters) {
        var self = this;

        self.global_settings = parameters[0];

        self.settings = ko.observable(undefined);
        self.scripts_gcode_snippets_doSmartPreheat = ko.observable(undefined);

        self.onBeforeBinding = function () {
            self.settings = self.global_settings.settings;
        };

        self.onSettingsShown = function () {
            self.scripts_gcode_snippets_doSmartPreheat(self.settings.scripts.gcode["snippets/doSmartPreheat"]());
        };

        self.onSettingsHidden = function () {
            self.settings.plugins.smartpreheat.scripts_gcode_snippets_doSmartPreheat = null;
        };

        self.onSettingsBeforeSave = function () {
            if (self.scripts_gcode_snippets_doSmartPreheat() !== undefined) {
                if (self.scripts_gcode_snippets_doSmartPreheat() != self.settings.scripts.gcode["snippets/doSmartPreheat"]()) {
                    self.settings.plugins.smartpreheat.scripts_gcode_snippets_doSmartPreheat = self.scripts_gcode_snippets_doSmartPreheat;
                    self.settings.scripts.gcode["snippets/doSmartPreheat"](self.scripts_gcode_snippets_doSmartPreheat());
                }
            }
        };
    }
    
    OCTOPRINT_VIEWMODELS.push([
        SmartPreheatViewModel,
        ["settingsViewModel"],
        ["#settings_plugin_smartpreheat"]
    ]);
});