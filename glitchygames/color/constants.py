"""Color constants used throughout the engine.

This module defines numeric constants for color formats, channel values,
transparency thresholds, and named color tuples derived from the default palette.
"""

from pygame import Color

from .palette import Default

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

# Default palette always has valid colors for these indices.
# get_color() can return None for invalid indices, but these are known-good.
# Colors are explicitly converted to tuples so the type matches the annotation.
_RGBColorTuple = tuple[int, int, int]
_RGBAColorTuple = tuple[int, int, int, int]


def _to_rgb(color: object) -> _RGBColorTuple:
    # Module-initialization helper: converts a pygame.Color to a plain RGB tuple.
    if not isinstance(color, Color):
        raise TypeError(f'Expected pygame.Color, got {type(color).__name__}')
    return (color.r, color.g, color.b)


def _to_rgba(color: object) -> _RGBAColorTuple:
    # Module-initialization helper: converts a pygame.Color to a plain RGBA tuple.
    if not isinstance(color, Color):
        raise TypeError(f'Expected pygame.Color, got {type(color).__name__}')
    return (color.r, color.g, color.b, color.a)


YELLOW: _RGBColorTuple = _to_rgb(_default_colors.YELLOW)
PURPLE: _RGBColorTuple = _to_rgb(_default_colors.PURPLE)
BLUE: _RGBColorTuple = _to_rgb(_default_colors.BLUE)
GREEN: _RGBColorTuple = _to_rgb(_default_colors.GREEN)
WHITE: _RGBColorTuple = _to_rgb(_default_colors.WHITE)
BLACK: _RGBColorTuple = _to_rgb(_default_colors.BLACK)
BLACKLUCENT: _RGBAColorTuple = _to_rgba(_default_colors.BLACKLUCENT)
BLUELUCENT: _RGBAColorTuple = _to_rgba(_default_colors.BLUELUCENT)
RED: _RGBColorTuple = _to_rgb(_default_colors.RED)
