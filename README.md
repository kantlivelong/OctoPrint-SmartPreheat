# OctoPrint Smart Preheat
This OctoPrint plugin reads the currently selected GCode file to determine what temperatures will be set prior to extrusion and exposes the values as variables which can be used in scripts. This plugin also provides its own default GCode snippet script which can be included in other existing GCode scripts.

##### Benefits:
- Heating can be performed in Parallel.
- Reduced time to heat all required tools.
- Heaters can be set and ready before other routines in GCode scripts or the selected file.
- Preheat routine is user customizable.

![SmartPreHeat-TempGraph-With](extra/screenshots/tempgraph_with.png?raw=true)

![SmartPreHeat-TempGraph-Without](extra/screenshots/tempgraph_without.png?raw=true)

![SmartPreHeat-GCode-Scripts-beforePrintStarted](extra/screenshots/beforePrintStarted.png?raw=true)

This started out as a fork of [marian42/OctoPrint-Preheat](https://github.com/marian42/octoprint-preheat) but I ended up completely rewriting and changing things.

## Setup
Install the plugin using Plugin Manager from Settings

## Support
Help can be found at the [OctoPrint Community Forums](https://community.octoprint.org)
