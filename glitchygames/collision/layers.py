"""Collision layer system for organizing sprite-vs-sprite collision checks.

CollisionManager groups sprites into named layers and provides efficient
pair-checking between layers with callbacks.

Usage:
    collisions = CollisionManager()
    player_layer = collisions.add_layer('player')
    enemy_layer = collisions.add_layer('enemies')
    player_layer.add(player_sprite)
    enemy_layer.add(cobra_sprite)
    collisions.check_overlap('player', 'enemies', on_player_hit_enemy)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from glitchygames.collision.detection import (
    check_aabb_overlap,
    get_collision_rect,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    import pygame


class CollisionLayer:
    """A named group of sprites that participate in collision.

    Sprites in a layer can be checked against sprites in another
    layer (or the same layer for intra-group collisions).

    Args:
        name: Human-readable name for this layer.

    """

    def __init__(self, name: str) -> None:
        """Initialize the collision layer."""
        self.name = name
        self._sprites: list[Any] = []

    def add(self, sprite: Any) -> None:
        """Add a sprite to this layer.

        Args:
            sprite: The sprite to track for collision.

        """
        if sprite not in self._sprites:
            self._sprites.append(sprite)

    def remove(self, sprite: Any) -> None:
        """Remove a sprite from this layer.

        Args:
            sprite: The sprite to remove.

        """
        if sprite in self._sprites:
            self._sprites.remove(sprite)

    def clear(self) -> None:
        """Remove all sprites from this layer."""
        self._sprites.clear()

    @property
    def sprites(self) -> list[Any]:
        """All sprites currently in this layer.

        Returns:
            List of sprites in this layer.

        """
        return self._sprites

    def __len__(self) -> int:
        """Number of sprites in this layer.

        Returns:
            Sprite count.

        """
        return len(self._sprites)


class CollisionManager:
    """Manages collision layers and checks between them.

    Provides a clean API for registering sprite groups and running
    collision checks with callbacks. Replaces manual sprite list
    iteration in game code.
    """

    def __init__(self) -> None:
        """Initialize the collision manager."""
        self._layers: dict[str, CollisionLayer] = {}

    def add_layer(self, name: str) -> CollisionLayer:
        """Create and register a named collision layer.

        Args:
            name: Unique name for this layer (e.g., 'player', 'enemies').

        Returns:
            The created CollisionLayer.

        Raises:
            ValueError: If a layer with this name already exists.

        """
        if name in self._layers:
            msg = f"Collision layer '{name}' already exists"
            raise ValueError(msg)
        layer = CollisionLayer(name)
        self._layers[name] = layer
        return layer

    def get_layer(self, name: str) -> CollisionLayer:
        """Get a collision layer by name.

        Args:
            name: The layer name.

        Returns:
            The CollisionLayer.

        Raises:
            KeyError: If no layer with this name exists.

        """
        if name not in self._layers:
            msg = f"No collision layer named '{name}'"
            raise KeyError(msg)
        return self._layers[name]

    def check_overlap(
        self,
        layer_a_name: str,
        layer_b_name: str,
        callback: Callable[[Any, Any], None],
    ) -> None:
        """Check all pairs between two layers, calling callback on collision.

        For each sprite in layer_a that overlaps a sprite in layer_b,
        calls callback(sprite_a, sprite_b). Uses hitbox-aware collision
        rects when available.

        If layer_a and layer_b are the same, checks all unique pairs
        within the layer (no self-collision, no duplicate pairs).

        Args:
            layer_a_name: Name of the first layer.
            layer_b_name: Name of the second layer.
            callback: Called with (sprite_a, sprite_b) on each collision.

        """
        layer_a = self.get_layer(layer_a_name)
        layer_b = self.get_layer(layer_b_name)

        same_layer = layer_a_name == layer_b_name

        for index_a, sprite_a in enumerate(layer_a.sprites):
            rect_a = _get_sprite_collision_rect(sprite_a)

            start_b = index_a + 1 if same_layer else 0
            sprites_b = layer_b.sprites[start_b:] if same_layer else layer_b.sprites

            for sprite_b in sprites_b:
                rect_b = _get_sprite_collision_rect(sprite_b)
                if check_aabb_overlap(rect_a, rect_b):
                    callback(sprite_a, sprite_b)

    def check_single(
        self,
        sprite: Any,
        layer_name: str,
        callback: Callable[[Any, Any], None],
    ) -> None:
        """Check one sprite against all sprites in a layer.

        Args:
            sprite: The sprite to check.
            layer_name: Name of the layer to check against.
            callback: Called with (sprite, other) on each collision.

        """
        layer = self.get_layer(layer_name)
        rect = _get_sprite_collision_rect(sprite)

        for other in layer.sprites:
            if other is sprite:
                continue
            other_rect = _get_sprite_collision_rect(other)
            if check_aabb_overlap(rect, other_rect):
                callback(sprite, other)

    @property
    def layer_names(self) -> list[str]:
        """Names of all registered layers."""
        return list(self._layers.keys())


def _get_sprite_collision_rect(sprite: Any) -> pygame.Rect:
    """Extract a collision rect from a sprite.

    Handles sprites with world_x/world_y (game objects) and
    sprites with only rect (UI elements).

    Returns:
        A pygame.Rect for collision detection.

    """
    import pygame

    if hasattr(sprite, 'world_x') and hasattr(sprite, 'world_y'):
        return get_collision_rect(sprite, sprite.world_x, sprite.world_y)

    if hasattr(sprite, 'rect') and sprite.rect is not None:
        return sprite.rect

    return pygame.Rect(0, 0, 0, 0)
