"""What a hit looks like: a white flash of a sprite's shape, and a fading frame.

Feature plan 6 (plans/2026-11-15-zombies-aint-my-neighbors-6-channel-changer.md): a struck zombie
or TV flashes white for 0.05 s, and a crumbled zombie's slippers fade out. Both make new
surfaces from a frame and never change the engine's cached one (``drawn_frame_surface``'s rule).
"""

from __future__ import annotations

from typing import Final

import pygame

WHITE: Final = (255, 255, 255, 255)
CLEAR: Final = (0, 0, 0, 0)


def white_silhouette(surface: pygame.Surface) -> pygame.Surface:
    """Return a frame's shape in solid white, clear everywhere it is clear.

    Args:
        surface: The frame (per-pixel alpha or a colour key: the mask reads either).

    Returns:
        A new surface with per-pixel alpha.

    """
    return pygame.mask.from_surface(surface).to_surface(setcolor=WHITE, unsetcolor=CLEAR)


def faded(surface: pygame.Surface, *, alpha: int) -> pygame.Surface:
    """Return a copy of a frame drawn at an opacity.

    Args:
        surface: The frame.
        alpha: 0 (invisible) to 255 (as drawn).

    Returns:
        A new surface.

    """
    copy = surface.copy()
    copy.set_alpha(alpha)
    return copy
