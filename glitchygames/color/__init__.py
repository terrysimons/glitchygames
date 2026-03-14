"""Color constants and palette helpers.

This module contains color constants and palette helpers.
"""

from .palette import (
    NES,
    SYSTEM,
    VGA,
    Default,
)

__all__ = ["NES", "SYSTEM", "VGA", "Default"]

# --- Color format constants ---
# Number of components in an RGB pixel tuple (red, green, blue)
RGB_COMPONENT_COUNT = 3
# Number of components in an RGBA pixel tuple (red, green, blue, alpha)
RGBA_COMPONENT_COUNT = 4

# --- Color channel value constants ---
# Maximum value for an 8-bit color channel (0-255)
MAX_COLOR_CHANNEL_VALUE = 255
# Alpha value 255 means fully opaque; 0-254 indicates per-pixel transparency
MAX_PER_PIXEL_ALPHA = 254
# Midpoint of the 0-255 color range, used as a threshold for transparency detection
ALPHA_TRANSPARENCY_THRESHOLD = 128

# --- Transparency key ---
# Magenta (255, 0, 255) is used as the transparency key color
MAGENTA_TRANSPARENCY_KEY = (255, 0, 255)

_default_colors: Default = Default()
YELLOW = _default_colors.YELLOW
PURPLE = _default_colors.PURPLE
BLUE = _default_colors.BLUE
GREEN = _default_colors.GREEN
WHITE = _default_colors.WHITE
BLACK = _default_colors.BLACK
BLACKLUCENT = _default_colors.BLACKLUCENT
BLUELUCENT = _default_colors.BLUELUCENT
RED = _default_colors.RED
