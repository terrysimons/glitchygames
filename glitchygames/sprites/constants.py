"""Constants for the sprites module."""

# Default file format for saving sprites
DEFAULT_FILE_FORMAT = "toml"

# Universal character set for sprite encoding
# Original set plus all Unicode letters (excluding duplicates)
import unicodedata

# Start with the original set
original_glyphs = ".aAbBcCdDeEfFgGhHiIjJkKlLmMnNoOpPqQrRsStTuUvVwWxXyYzZ0123456789@"

# Get all Unicode letters that aren't already in the original set
unicode_letters = set()
for i in range(0x10FFFF + 1):  # Full Unicode range
    try:
        char = chr(i)
        if unicodedata.category(char).startswith("L"):  # Unicode letter categories
            unicode_letters.add(char)
    except ValueError:
        pass

# Remove characters already in original set
unicode_letters -= set(original_glyphs)

# Combine: original set first, then additional Unicode letters
SPRITE_GLYPHS = original_glyphs + "".join(sorted(unicode_letters))
