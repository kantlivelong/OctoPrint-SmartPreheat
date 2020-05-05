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
M117 Set {{ 'default tool' if tool|int < 0 else 'tool ' + tool|int|string }} to temp {{ temp|int -}} 
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
