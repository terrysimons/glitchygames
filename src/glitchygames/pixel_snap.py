"""Sub-pixel to whole-pixel snapping shared by sprites, collision and debug tools."""

from __future__ import annotations

import dataclasses
import math
from enum import Enum
from typing import assert_never

from glitchygames.engine_context import ContextSlot, current_context

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
        case _:  # pragma: no cover - every PixelSnapMode is matched above
            assert_never(mode)


@dataclasses.dataclass
class _SnapSettings:
    """Holds an engine context's default snap mode (the running scene's PIXEL_SNAP_MODE)."""

    default_mode: PixelSnapMode = PixelSnapMode.NEAREST_HALF_UP


# Each engine context's default snap mode (glitchygames.engine_context)
SNAP_SETTINGS_SLOT: ContextSlot[_SnapSettings] = ContextSlot(
    name='glitchygames.pixel_snap.default_mode', factory=_SnapSettings
)


def set_active_default_snap_mode(mode: PixelSnapMode) -> None:
    """Set the snap mode used by sprites that do not choose their own, in this engine context.

    Args:
        mode: The new default (normally the active scene's PIXEL_SNAP_MODE).

    """
    current_context().value(slot=SNAP_SETTINGS_SLOT).default_mode = mode


def active_default_snap_mode() -> PixelSnapMode:
    """Return the snap mode used by sprites that do not choose their own, in this engine context.

    Returns:
        PixelSnapMode: The active default (initially NEAREST_HALF_UP).

    """
    return current_context().value(slot=SNAP_SETTINGS_SLOT).default_mode


def resolve_snap_mode(sprite: object) -> PixelSnapMode:
    """Pick the snap mode for a sprite: its own pixel_snap_mode, else the active default.

    Args:
        sprite: Any object; only a pixel_snap_mode that is a PixelSnapMode counts.

    Returns:
        PixelSnapMode: The mode to snap this sprite's positions with.

    """
    # Looked up by name: any sprite may be resolved (a game's own DirtySprite), and only some
    # declare a mode (BallSprite). A default declared on the engine's sprite classes would not
    # save the lookup: getattr costs the same whether or not it finds the attribute
    sprite_mode = getattr(sprite, 'pixel_snap_mode', None)
    if isinstance(sprite_mode, PixelSnapMode):
        return sprite_mode
    return current_context().value(slot=SNAP_SETTINGS_SLOT).default_mode
