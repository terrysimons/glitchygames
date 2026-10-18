"""Sub-pixel to whole-pixel snapping shared by sprites, collision and debug tools."""

from __future__ import annotations

import math
from enum import Enum

# Fractional pixel at which NEAREST_HALF_UP snapping rounds up
HALF_PIXEL = 0.5


class PixelSnapMode(Enum):
    """How a sub-pixel world position is converted to the whole pixel a sprite is drawn at.

    NEAREST_HALF_UP suits smooth-motion games (Pong, PaddleSlap): the drawn position
    tracks the true position as closely as possible with even steps at half pixels.
    FLOOR suits retro, top-down, and platformer games: like SNES-era fixed-point
    positions, only the whole-pixel part is drawn, and it behaves the same on both
    sides of zero.
    """

    NEAREST_HALF_UP = 'nearest_half_up'  # Halves round toward +infinity: 2.5 -> 3, -2.5 -> -2
    NEAREST_EVEN = 'nearest_even'  # Python round(): halves go to the even pixel: 2.5 -> 2
    FLOOR = 'floor'  # Toward -infinity: 2.9 -> 2, -0.5 -> -1
    CEIL = 'ceil'  # Toward +infinity: 2.1 -> 3, -2.9 -> -2
    TRUNCATE = 'truncate'  # Toward zero: -0.5 and 0.5 both -> 0


def snap_to_pixel(value: float, mode: PixelSnapMode) -> int:
    """Convert a sub-pixel coordinate to a whole pixel using the given snap mode.

    Args:
        value: The sub-pixel coordinate.
        mode: The rounding rule to apply.

    Returns:
        int: The whole-pixel coordinate.

    """
    match mode:
        case PixelSnapMode.NEAREST_HALF_UP:
            # Not math.floor(value + 0.5): the addition itself rounds at float boundaries,
            # e.g. 0.49999999999999994 + 0.5 == 1.0, and above 2**52 a whole number plus
            # 0.5 rounds to an even neighbor. Subtracting the floor is exact, so compare
            # the fractional part directly.
            whole_pixel = math.floor(value)
            return whole_pixel + 1 if value - whole_pixel >= HALF_PIXEL else whole_pixel
        case PixelSnapMode.NEAREST_EVEN:
            return round(value)
        case PixelSnapMode.FLOOR:
            return math.floor(value)
        case PixelSnapMode.CEIL:
            return math.ceil(value)
        case PixelSnapMode.TRUNCATE:
            return math.trunc(value)
