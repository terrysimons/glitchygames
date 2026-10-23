"""Visible-pixel bounds of sprite images, used to trim hitboxes to what is drawn.

By default a sprite without a TOML hitbox collides as the smallest rect that contains its
image's visible pixels (per-pixel alpha and colorkey are both honoured), not as the whole
image. A sprite opts out with a ``TRIM_TRANSPARENT_HITBOX = False`` attribute on its class
or instance.

Bounds are measured on every call, never cached per surface: several games (Brave Adventurer,
Clockwork Keep) create a blank image and redraw each frame's pose into that same surface, so
a per-surface cache would keep the blank or first pose. AnimatedSprite frames, whose surfaces
do not change, cache their bounds per frame (see SpriteFrame.opaque_bounds).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame


def opaque_bounds(image: pygame.Surface) -> pygame.Rect:
    """Return the rect of an image's visible pixels, relative to its top-left corner.

    Pixels that are fully transparent (alpha 0, or equal to the colorkey) are trimmed. An
    image with no visible pixels returns its full rect, so invisible trigger sprites (and
    images not drawn yet) keep their area. Measured on every call: about 1 us for 20x20,
    8 us for 64x64 and 1 ms for 800x600.

    Args:
        image (pygame.Surface): The sprite image.

    Returns:
        pygame.Rect: A new rect (callers may mutate it).

    """
    visible_bounds = image.get_bounding_rect()
    if visible_bounds.width == 0 or visible_bounds.height == 0:
        return image.get_rect()
    return visible_bounds


def trims_transparent_hitbox(sprite: object) -> bool:
    """Whether a sprite's default hitbox is trimmed to its image's visible pixels.

    Reads the sprite's ``TRIM_TRANSPARENT_HITBOX`` attribute (instance or class); a sprite
    without it trims.

    Args:
        sprite (object): The sprite (only its attribute is read).

    Returns:
        bool: True unless the sprite opts out.

    """
    # Looked up by name: the opt-out is optional on any sprite, of any class
    return bool(getattr(sprite, 'TRIM_TRANSPARENT_HITBOX', True))
