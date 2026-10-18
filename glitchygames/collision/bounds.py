"""Visible-pixel bounds of sprite images, used to trim hitboxes to what is drawn.

By default a sprite without a TOML hitbox collides as the smallest rect that contains its
image's visible pixels (per-pixel alpha and colorkey are both honoured), not as the whole
image. A sprite opts out with a ``TRIM_TRANSPARENT_HITBOX = False`` attribute on its class
or instance.

Bounds are cached per surface. Images whose visible shape is redrawn in place at the same
size keep the cached bounds: call ``forget_opaque_bounds(image)`` after such a redraw.
"""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pygame

# Measured cost of Surface.get_bounding_rect(): ~1 us for 20x20, ~8 us for 64x64 and ~1 ms
# for 800x600, so results are cached. Keys are weak so cached surfaces can still be freed.
# Each entry stores the image size with its bounds and is recomputed if the size differs.
_OPAQUE_BOUNDS_CACHE: weakref.WeakKeyDictionary[
    pygame.Surface, tuple[tuple[int, int], pygame.Rect]
] = weakref.WeakKeyDictionary()


def opaque_bounds(image: pygame.Surface) -> pygame.Rect:
    """Return the rect of an image's visible pixels, relative to its top-left corner.

    Pixels that are fully transparent (alpha 0, or equal to the colorkey) are trimmed. An
    image with no visible pixels returns its full rect, so invisible trigger sprites keep
    their area.

    The result is cached per surface. Images whose visible shape is redrawn in place at the
    same size keep the cached bounds: call ``forget_opaque_bounds(image)`` after such a
    redraw.

    Args:
        image (pygame.Surface): The sprite image.

    Returns:
        pygame.Rect: A new rect (callers may mutate it).

    """
    image_size = image.get_size()
    cached_entry = _OPAQUE_BOUNDS_CACHE.get(image)
    if cached_entry is not None and cached_entry[0] == image_size:
        return cached_entry[1].copy()

    visible_bounds = image.get_bounding_rect()
    if visible_bounds.width == 0 or visible_bounds.height == 0:
        visible_bounds = image.get_rect()
    _OPAQUE_BOUNDS_CACHE[image] = (image_size, visible_bounds)
    return visible_bounds.copy()


def forget_opaque_bounds(image: pygame.Surface) -> None:
    """Drop an image's cached bounds so the next lookup measures it again.

    Call this after drawing a different visible shape into the same image.

    Args:
        image (pygame.Surface): The sprite image.

    """
    _OPAQUE_BOUNDS_CACHE.pop(image, None)


def trims_transparent_hitbox(sprite: Any) -> bool:
    """Whether a sprite's default hitbox is trimmed to its image's visible pixels.

    Reads the sprite's ``TRIM_TRANSPARENT_HITBOX`` attribute (instance or class); a sprite
    without it trims.

    Args:
        sprite (Any): The sprite.

    Returns:
        bool: True unless the sprite opts out.

    """
    return bool(getattr(sprite, 'TRIM_TRANSPARENT_HITBOX', True))
