#!/usr/bin/env python3
"""Test script for loading sprite data from INI files."""

import configparser
from io import StringIO

from bokeh.plotting import figure, output_notebook, show

# Sample INI content for sprite data
ini_content = """
[sprite]
name = mysprite
pixels =
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222220000220000222222222224
       22222222201111001111022222222224
       22222222011111111111102222222224
       22222220111111111111310222222224
       22222201111111311111131022222224
       22222201111111131111131022222224
       22222201111111311111131022222224
       22222201111111311111131022222224
       22222220111111111111310222222224
       22222222011111111111102222222224
       22222222201111111111022222222224
       22222222220111111110222222222224
       22222222222011111102222222222224
       22222222222201111022222222222224
       22222222222220110222222222222224
       22222222222222002222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222224
       22222222222222222222222222222244

[0]
red = 191
green = 187
blue = 191

[1]
red = 175
green = 27
blue = 0

[2]
red = 255
green = 0
blue = 255

[3]
red = 255
green = 35
blue = 151

[4]
red = 0
green = 0
blue = 0
"""

# Load the content using configparser
config = configparser.ConfigParser()
config.optionxform = str  # Preserve case sensitivity for keys
config.read_file(StringIO(ini_content))

# Extract multi-line `pixels` data
pixels_raw = config.get("sprite", "pixels")
pixels = [line.strip() for line in pixels_raw.splitlines() if line.strip()]

# Extract color data
color_map = {}
for i in range(5):
    color_map[str(i)] = (
        int(config[str(i)]["red"]),
        int(config[str(i)]["green"]),
        int(config[str(i)]["blue"]),
    )


# Convert RGB colors to hex
def rgb_to_hex(rgb):
    """Convert RGB tuple to hex color string."""
    return "#{:02x}{:02x}{:02x}".format(*rgb)


# Prepare the Bokeh plot
output_notebook()
p = figure(
    width=320,
    height=320,
    title="Sprite Visualization",
    x_range=(0, len(pixels[0])),
    y_range=(0, len(pixels)),
    tools="",
    toolbar_location=None,
)

# Plot each "pixel" as a square on the Bokeh figure
for y, row in enumerate(pixels):
    for x, pixel in enumerate(row):
        color = rgb_to_hex(color_map[pixel])
        p.rect(x + 0.5, len(pixels) - y - 0.5, width=1, height=1, color=color, line_color=None)

p.xgrid.visible = False
p.ygrid.visible = False
p.axis.visible = False

# Display the sprite
show(p, notebook_handle=True)
