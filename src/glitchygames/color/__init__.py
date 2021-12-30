from .palette import Custom, VGA, System

# Load Common Palettes
VGA = VGA()
SYSTEM = System()

# TODO: Refactor code to use CUSTOM.<COLOR> instead. kept for backwards compatibility
__custom_palette__ = Custom()
YELLOW = __custom_palette__.YELLOW
PURPLE = __custom_palette__.PURPLE
BLUE = __custom_palette__.BLUE
GREEN = __custom_palette__.GREEN
WHITE = __custom_palette__.WHITE
BLACK = __custom_palette__.BLACK
BLACKLUCENT = __custom_palette__.BLACKLUCENT
BLUELUCENT = __custom_palette__.BLUELUCENT
RED = __custom_palette__.RED
