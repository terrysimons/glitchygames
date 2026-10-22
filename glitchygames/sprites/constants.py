"""Constants for the sprites module."""

# Default file format for saving sprites
DEFAULT_FILE_FORMAT = 'toml'

# The characters a sprite's pixels are written with, one per color
#
# This was once planned to grow by every Unicode letter not already here: each import walked all
# 1,114,112 codepoints (about 90 ms) to build that set, but the line adding it stayed commented
# out, so the set was never used. To widen the glyph set, build it where it is used, or as a
# literal here, rather than computing it at import.
SPRITE_GLYPHS = '.aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ0123456789@'
