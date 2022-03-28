# Pallete Config Files
Palette files contain RGBA values in [Python's CongigParser](https://docs.python.org/3/library/configparser.html) format.  
The `[default]` section defines the properties of the palette and the number of colors it contains.

## RGB(A) Values
Each color in the palette has it's own section with the zero-based color index as the section title.  Each color section 
contains a `red`, `green`, and `blue` key/value pair.  There is also an optional `alpha` ket to set transparency.

### Example
```cfg
[palette]
name = My Palette
info = My favorite colors
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
