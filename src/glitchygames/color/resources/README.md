# Palette Config Files
Palette files (`<name>.palette`) contain RGBA values in [Python's ConfigParser](https://docs.python.org/3/library/configparser.html) format.
The `[default]` section defines the properties of the palette: `colors` (required) is the number of colors it contains;
`name` and `description` are informational and are not read by the loader.

`ColorPalette(colors=None, filename='<name>')` looks for `<name>.palette` in this directory, then in the running
script's directory, then in that directory's `resources/` folder. `PaletteUtility.load_palette_from_file()` loads a
palette file from any path.

## RGB(A) Values
Each color in the palette has its own section with the zero-based color index as the section title.  Each color section
contains a `red`, `green`, and `blue` key/value pair (a missing one reads as 0).  There is also an optional `alpha` key
to set transparency (default 255, opaque).

### Example
```cfg
[default]
name = My Palette
description = My favorite colors
colors = 2

[0]
red = 172
green = 124
blue = 0
alpha = 128

[1]
red = 124
green = 124
blue = 124
```
