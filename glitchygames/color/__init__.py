"""Color constants and palette helpers.

This module contains color constants and palette helpers.
"""

from .palette import (
    NES,
    SYSTEM,
    VGA,
    Default,
)

__all__ = ['NES', 'SYSTEM', 'VGA', 'Default']

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
