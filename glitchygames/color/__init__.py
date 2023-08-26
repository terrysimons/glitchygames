from .palette import (
    NES,  # noqa: F401
    SYSTEM,  # noqa: F401
    VGA,  # noqa: F401
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
