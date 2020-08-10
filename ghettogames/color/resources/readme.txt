To create a pallete from a list of colors in a file just list each
color on its own line in R,G,B or R,G,B,A format. Don't use any blank lines.
Duplicates are removed from the final palette.

123, 123, 44, 128
10, 10, 10
0, 0, 0, 240


To create a loadable palette you can use a basic config format. The sections names
are surrounded by brackets [ ] and the name value pairs follow.  There is one [palette]
section that must have the number of colors the palette contains specified in the colors
field.  Following the palette section are the color sections with the zero-based color
index as the section title.

[palette]
name = My Palette
info = My favorite colors
colors = 2

[0]
red = 172
green = 124
blue = 0

[1]
red = 124
green = 124
blue = 124

