"""Collision detection helpers with hitbox-aware rect generation.

Connects the TOML hitbox system to actual collision detection.
Sprites with TOML-defined hitboxes get accurate collision rects;
sprites without hitboxes collide as the visible pixels of their image
(see glitchygames.collision.bounds), or their full rect when they opt out.
"""

from __future__ import annotations

from typing import Any

import pygame

from glitchygames.collision.bounds import opaque_bounds, trims_transparent_hitbox
from glitchygames.pixel_snap import resolve_snap_mode, snap_to_pixel


def snapped_world_position(
    sprite: Any,
    world_x: float,
    world_y: float,
) -> tuple[int, int]:
    """Return the whole-pixel position a sprite is drawn at for a world position.

    Sprites with a ``pixel_snap_mode`` (such as BallSprite) are snapped with it; other sprites
    use the active scene's ``PIXEL_SNAP_MODE`` (glitchygames.pixel_snap.resolve_snap_mode), the
    same resolution the engine positions world sprites with, so the collision rect sits
    exactly where the sprite is drawn.

    Args:
        sprite: The sprite.
        world_x: X position in world space.
        world_y: Y position in world space.

    Returns:
        The snapped (x, y) position.

    """
    pixel_snap_mode = resolve_snap_mode(sprite)
    return (
        snap_to_pixel(world_x, pixel_snap_mode),
        snap_to_pixel(world_y, pixel_snap_mode),
    )


def get_collision_rect(
    sprite: Any,
    world_x: float,
    world_y: float,
) -> pygame.Rect:
    """Get the collision rect for a sprite at a world position.

    Uses the sprite's TOML hitbox if available (via get_hitbox_world_rect).
    Otherwise the rect starts at the snapped world position (see
    snapped_world_position) and covers the visible pixels of the sprite's image
    (see opaque_bounds), or the sprite's full rect size when the sprite has no
    image or sets TRIM_TRANSPARENT_HITBOX = False.

    Args:
        sprite: The sprite to get a collision rect for.
        world_x: X position in world space.
        world_y: Y position in world space.

    Returns:
        A pygame.Rect positioned in world coordinates.

    """
    if hasattr(sprite, 'get_hitbox_world_rect'):
        return sprite.get_hitbox_world_rect(world_x, world_y)

    snapped_x, snapped_y = snapped_world_position(sprite, world_x, world_y)
    image = getattr(sprite, 'image', None)
    if image is not None and trims_transparent_hitbox(sprite):
        visible_bounds = opaque_bounds(image)
        return pygame.Rect(
            snapped_x + visible_bounds.x,
            snapped_y + visible_bounds.y,
            visible_bounds.width,
            visible_bounds.height,
        )

    return pygame.Rect(
        snapped_x,
        snapped_y,
        sprite.rect.width,
        sprite.rect.height,
    )


def get_collision_rect_with_margin(
    sprite: Any,
    world_x: float,
    world_y: float,
    margin: int = 0,
) -> pygame.Rect:
    """Get a collision rect with an inset margin for forgiving collisions.

    Shrinks the rect by `margin` pixels on all sides. Useful for
    "forgiveness" in player-enemy collisions where pixel-perfect
    overlap feels unfair.

    Args:
        sprite: The sprite to get a collision rect for.
        world_x: X position in world space.
        world_y: Y position in world space.
        margin: Pixels to shrink on each side (default 0).

    Returns:
        A pygame.Rect shrunk by margin on all sides.

    """
    rect = get_collision_rect(sprite, world_x, world_y)
    if margin > 0:
        rect.inflate_ip(-margin * 2, -margin * 2)
    return rect


def check_aabb_overlap(
    rect_a: pygame.Rect,
    rect_b: pygame.Rect,
) -> bool:
    """Check if two axis-aligned bounding boxes overlap.

    Args:
        rect_a: First rectangle.
        rect_b: Second rectangle.

    Returns:
        True if the rectangles overlap.

    """
    return rect_a.colliderect(rect_b)


def compute_push_out(
    mover: pygame.Rect,
    static: pygame.Rect,
    velocity_x: float = 0.0,
) -> tuple[float, float]:
    """Compute the displacement needed to push mover out of static.

    Uses the mover's horizontal velocity to determine push direction.
    If moving right, pushes mover to the left of static; if moving
    left, pushes to the right.

    Args:
        mover: The rect of the moving object.
        static: The rect of the static object.
        velocity_x: Horizontal velocity of the mover (determines push direction).

    Returns:
        Tuple of (dx, dy) displacement to apply to the mover's position.

    """
    if not mover.colliderect(static):
        return (0.0, 0.0)

    # Compute overlap on each axis
    overlap_left = mover.right - static.left
    overlap_right = static.right - mover.left
    overlap_top = mover.bottom - static.top
    overlap_bottom = static.bottom - mover.top

    # Push out along the axis of least penetration
    min_horizontal = min(overlap_left, overlap_right)
    min_vertical = min(overlap_top, overlap_bottom)

    if min_horizontal < min_vertical:
        # Push horizontally
        if velocity_x > 0:
            return (-float(overlap_left), 0.0)
        return (float(overlap_right), 0.0)

    # Push vertically
    if overlap_top < overlap_bottom:
        return (0.0, -float(overlap_top))
    return (0.0, float(overlap_bottom))
