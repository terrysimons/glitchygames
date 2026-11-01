"""Sprite utilities for the Papyrus Edition.

Converts TOML sprite surfaces from colorkey transparency (magenta) to
per-pixel alpha (SRCALPHA). SRCALPHA surfaces preserve transparency
through scaling, flipping, and cache rebuilds without needing to
re-apply colorkey every frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from brave_adventurer_papyrus.constants import MAGENTA_KEY, SPRITE_SCALE

if TYPE_CHECKING:
    from glitchygames.sprites import AnimatedSprite


def _convert_to_alpha_surface(surface: pygame.Surface) -> pygame.Surface:
    """Convert a surface with magenta pixels to a proper SRCALPHA surface.

    Sets colorkey on the source, then blits onto an SRCALPHA surface.
    Magenta pixels become alpha=0 (truly transparent).

    Args:
        surface: Source surface with magenta transparency pixels.

    Returns:
        New SRCALPHA surface with per-pixel alpha transparency.

    """
    surface.set_colorkey(MAGENTA_KEY)
    alpha_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    alpha_surface.blit(surface, (0, 0))
    return alpha_surface


def prepare_papyrus_sprite(sprite: AnimatedSprite, scale_factor: int = SPRITE_SCALE) -> None:
    """Convert all animation frames from colorkey to per-pixel alpha, and set the draw scale.

    Call this immediately after AnimatedSprite.__init__() loads the TOML file.
    Replaces every frame surface with an SRCALPHA version where magenta
    pixels are fully transparent, and sets the sprite's scale to the scale it is
    drawn at, so its image, rect and hitboxes are scaled from construction on
    (before its first dt_tick).

    Args:
        sprite: The AnimatedSprite to prepare.
        scale_factor: Integer scale the sprite is drawn at.

    """
    for frames in sprite.animation_data.values():
        for frame in frames:
            frame.image = _convert_to_alpha_surface(frame.image)

    # Clears the surface cache and redraws the current frame at the new scale; image, rect,
    # hitboxes and draw_offset all follow it (BUGS.md #144)
    sprite.scale = scale_factor


def refresh_drawn_image(sprite: AnimatedSprite) -> None:
    """Reset the sprite's image to a fresh copy of its current frame, as the engine draws it.

    The engine only redraws image when the frame changes, but Papyrus sprites flip and fade
    image every tick; starting from a copy each tick keeps those effects from stacking up or
    reaching the engine's cached surface.

    Args:
        sprite: The sprite to refresh.

    """
    sprite.image = sprite.drawn_frame_surface().copy()
