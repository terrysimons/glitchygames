"""Sprite utilities for the Papyrus Edition.

Converts TOML sprite surfaces from colorkey transparency (magenta) to
per-pixel alpha (SRCALPHA). SRCALPHA surfaces preserve transparency
through scaling, flipping, and cache rebuilds without needing to
re-apply colorkey every frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from glitchygames.examples.brave_adventurer_papyrus.constants import MAGENTA_KEY, SPRITE_SCALE

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


def prepare_papyrus_sprite(sprite: AnimatedSprite) -> None:
    """Convert all animation frames from colorkey to per-pixel alpha.

    Call this immediately after AnimatedSprite.__init__() loads the TOML file.
    Replaces every frame surface with an SRCALPHA version where magenta
    pixels are fully transparent.

    Args:
        sprite: The AnimatedSprite to prepare.

    """
    for frames in sprite.animation_data.values():
        for frame in frames:
            frame.image = _convert_to_alpha_surface(frame.image)

    sprite.clear_surface_cache()

    current_frame = sprite.get_current_frame()
    if current_frame is not None:
        sprite.image = current_frame.image


def apply_transparency_and_scale(
    sprite: AnimatedSprite,
    scale_factor: int = SPRITE_SCALE,
) -> None:
    """Scale from the original frame surface with proper alpha transparency.

    Always reads from the current animation frame's source surface
    (not self.image) to prevent cumulative double-scaling.
    The SRCALPHA format set by prepare_papyrus_sprite() is preserved
    through pygame.transform.scale().

    Args:
        sprite: The sprite to process.
        scale_factor: Integer scale multiplier.

    """
    frame = sprite.get_current_frame()
    if frame is None:
        return

    source_surface = frame.image

    if scale_factor > 1:
        scaled_width = source_surface.get_width() * scale_factor
        scaled_height = source_surface.get_height() * scale_factor
        sprite.image = pygame.transform.scale(
            source_surface,
            (scaled_width, scaled_height),
        )
    else:
        sprite.image = source_surface.copy()
