"""Collision detection and resolution framework.

Provides collision layers, hitbox-aware detection, and push-out
resolution. Connects the TOML hitbox system to actual collision
checking so sprites with defined hitboxes get accurate collisions.

Usage:
    collisions = CollisionManager()
    collisions.add_layer('player')
    collisions.add_layer('enemies')
    collisions.check_overlap('player', 'enemies', on_hit)
"""

from glitchygames.collision.detection import (
    check_aabb_overlap,
    compute_push_out,
    get_collision_rect,
    get_collision_rect_with_margin,
)
from glitchygames.collision.layers import CollisionLayer, CollisionManager

__all__ = [
    'CollisionLayer',
    'CollisionManager',
    'check_aabb_overlap',
    'compute_push_out',
    'get_collision_rect',
    'get_collision_rect_with_margin',
]
