"""Tests for collision detection, layers, and push-out resolution."""

from dataclasses import dataclass, field

import pygame
import pytest

from glitchygames.collision import (
    CollisionManager,
    check_aabb_overlap,
    compute_push_out,
    get_collision_rect,
    get_collision_rect_with_margin,
)


def _default_rect(world_x: float, world_y: float, size: int = 32) -> pygame.Rect:
    """Create a default rect at world position."""
    return pygame.Rect(round(world_x), round(world_y), size, size)


@dataclass
class FakeSprite:
    """Minimal sprite with world position and rect."""

    world_x: float = 0.0
    world_y: float = 0.0
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 32, 32))

    def __post_init__(self):  # noqa: D105
        self.rect = _default_rect(self.world_x, self.world_y)


@dataclass
class HitboxSprite:
    """Sprite with a TOML-style hitbox method."""

    world_x: float = 0.0
    world_y: float = 0.0
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 32, 32))
    hitbox_offset_x: int = 4
    hitbox_offset_y: int = 2
    hitbox_width: int = 24
    hitbox_height: int = 28

    def __post_init__(self):  # noqa: D105
        self.rect = _default_rect(self.world_x, self.world_y)

    def get_hitbox_world_rect(
        self,
        world_x: float,
        world_y: float,
    ) -> pygame.Rect:
        """Simulate AnimatedSprite.get_hitbox_world_rect."""
        return pygame.Rect(
            round(world_x) + self.hitbox_offset_x,
            round(world_y) + self.hitbox_offset_y,
            self.hitbox_width,
            self.hitbox_height,
        )


# --- Detection ---


class TestGetCollisionRect:
    """Hitbox-aware collision rect generation."""

    def test_sprite_without_hitbox_uses_full_rect(self):
        """Sprites without get_hitbox_world_rect use their full rect."""
        sprite = FakeSprite(world_x=100.0, world_y=200.0)
        rect = get_collision_rect(sprite, world_x=100.0, world_y=200.0)
        assert rect == pygame.Rect(100, 200, 32, 32)

    def test_sprite_with_hitbox_uses_hitbox(self):
        """Sprites with get_hitbox_world_rect use their TOML hitbox."""
        sprite = HitboxSprite(world_x=100.0, world_y=200.0)
        rect = get_collision_rect(sprite, world_x=100.0, world_y=200.0)
        # Hitbox offset (4, 2) applied to world position
        assert rect == pygame.Rect(104, 202, 24, 28)

    def test_margin_shrinks_rect(self):
        """Margin creates a forgiveness zone around the collision rect."""
        sprite = FakeSprite(world_x=100.0, world_y=200.0)
        rect = get_collision_rect_with_margin(
            sprite,
            world_x=100.0,
            world_y=200.0,
            margin=4,
        )
        # 32x32 shrunk by 4 on each side = 24x24 at (104, 204)
        assert rect.width == 24
        assert rect.height == 24


class TestCheckAABBOverlap:
    """AABB overlap detection."""

    def test_overlapping_rects(self):
        """Overlapping rectangles return True."""
        rect_a = pygame.Rect(0, 0, 50, 50)
        rect_b = pygame.Rect(25, 25, 50, 50)
        assert check_aabb_overlap(rect_a, rect_b) is True

    def test_non_overlapping_rects(self):
        """Non-overlapping rectangles return False."""
        rect_a = pygame.Rect(0, 0, 50, 50)
        rect_b = pygame.Rect(100, 100, 50, 50)
        assert check_aabb_overlap(rect_a, rect_b) is False

    def test_touching_rects_not_overlapping(self):
        """Rects that share an edge but don't overlap return False."""
        rect_a = pygame.Rect(0, 0, 50, 50)
        rect_b = pygame.Rect(50, 0, 50, 50)
        assert check_aabb_overlap(rect_a, rect_b) is False


class TestComputePushOut:
    """Push-out displacement calculation."""

    def test_push_out_moving_right(self):
        """Moving right into a static object pushes left."""
        mover = pygame.Rect(40, 0, 20, 20)
        static = pygame.Rect(50, 0, 20, 20)
        displacement_x, displacement_y = compute_push_out(
            mover,
            static,
            velocity_x=100.0,
        )
        assert displacement_x < 0  # Pushed left
        assert displacement_y == 0.0

    def test_push_out_moving_left(self):
        """Moving left into a static object pushes right."""
        mover = pygame.Rect(40, 0, 20, 20)
        static = pygame.Rect(30, 0, 20, 20)
        displacement_x, displacement_y = compute_push_out(
            mover,
            static,
            velocity_x=-100.0,
        )
        assert displacement_x > 0  # Pushed right
        assert displacement_y == 0.0

    def test_no_push_out_when_no_overlap(self):
        """No displacement when rects don't overlap."""
        mover = pygame.Rect(0, 0, 20, 20)
        static = pygame.Rect(100, 100, 20, 20)
        displacement_x, displacement_y = compute_push_out(mover, static)
        assert displacement_x == 0.0
        assert displacement_y == 0.0


# --- Layers ---


class TestCollisionLayer:
    """CollisionLayer sprite management."""

    def test_add_and_count(self):
        """Adding sprites increases layer size."""
        manager = CollisionManager()
        layer = manager.add_layer('test')
        sprite = FakeSprite()
        layer.add(sprite)
        assert len(layer) == 1

    def test_remove(self):
        """Removing a sprite decreases layer size."""
        manager = CollisionManager()
        layer = manager.add_layer('test')
        sprite = FakeSprite()
        layer.add(sprite)
        layer.remove(sprite)
        assert len(layer) == 0

    def test_no_duplicates(self):
        """Adding the same sprite twice doesn't duplicate."""
        manager = CollisionManager()
        layer = manager.add_layer('test')
        sprite = FakeSprite()
        layer.add(sprite)
        layer.add(sprite)
        assert len(layer) == 1


class TestCollisionManager:
    """CollisionManager layer registration and collision checking."""

    def test_add_layer(self):
        """Can add and retrieve layers by name."""
        manager = CollisionManager()
        manager.add_layer('player')
        assert 'player' in manager.layer_names

    def test_duplicate_layer_raises(self):
        """Adding a layer with an existing name raises ValueError."""
        manager = CollisionManager()
        manager.add_layer('player')
        with pytest.raises(ValueError, match='already exists'):
            manager.add_layer('player')

    def test_get_unknown_layer_raises(self):
        """Getting an unknown layer raises KeyError."""
        manager = CollisionManager()
        with pytest.raises(KeyError, match='No collision layer'):
            manager.get_layer('nonexistent')

    def test_check_overlap_calls_callback(self):
        """Overlapping sprites trigger the callback."""
        manager = CollisionManager()
        player_layer = manager.add_layer('player')
        enemy_layer = manager.add_layer('enemies')

        player = FakeSprite(world_x=100.0, world_y=100.0)
        enemy = FakeSprite(world_x=110.0, world_y=110.0)
        player_layer.add(player)
        enemy_layer.add(enemy)

        collisions_found: list[tuple] = []
        manager.check_overlap(
            'player',
            'enemies',
            callback=lambda sprite_a, sprite_b: collisions_found.append(
                (sprite_a, sprite_b),
            ),
        )
        assert len(collisions_found) == 1
        assert collisions_found[0] == (player, enemy)

    def test_check_overlap_no_collision(self):
        """Non-overlapping sprites don't trigger callback."""
        manager = CollisionManager()
        player_layer = manager.add_layer('player')
        enemy_layer = manager.add_layer('enemies')

        player = FakeSprite(world_x=0.0, world_y=0.0)
        enemy = FakeSprite(world_x=500.0, world_y=500.0)
        player_layer.add(player)
        enemy_layer.add(enemy)

        collisions_found: list[tuple] = []
        manager.check_overlap(
            'player',
            'enemies',
            callback=lambda sprite_a, sprite_b: collisions_found.append(
                (sprite_a, sprite_b),
            ),
        )
        assert len(collisions_found) == 0

    def test_check_overlap_same_layer(self):
        """Checking a layer against itself finds unique pairs."""
        manager = CollisionManager()
        ball_layer = manager.add_layer('balls')

        ball_a = FakeSprite(world_x=100.0, world_y=100.0)
        ball_b = FakeSprite(world_x=110.0, world_y=110.0)
        ball_layer.add(ball_a)
        ball_layer.add(ball_b)

        collisions_found: list[tuple] = []
        manager.check_overlap(
            'balls',
            'balls',
            callback=lambda sprite_a, sprite_b: collisions_found.append(
                (sprite_a, sprite_b),
            ),
        )
        # Should find exactly one pair (a, b), not (a, a) or (b, a)
        assert len(collisions_found) == 1

    def test_check_single(self):
        """check_single tests one sprite against a layer."""
        manager = CollisionManager()
        enemy_layer = manager.add_layer('enemies')

        player = FakeSprite(world_x=100.0, world_y=100.0)
        enemy_near = FakeSprite(world_x=110.0, world_y=110.0)
        enemy_far = FakeSprite(world_x=500.0, world_y=500.0)
        enemy_layer.add(enemy_near)
        enemy_layer.add(enemy_far)

        hits: list[tuple] = []
        manager.check_single(
            player,
            'enemies',
            callback=lambda sprite_a, sprite_b: hits.append(
                (sprite_a, sprite_b),
            ),
        )
        assert len(hits) == 1
        assert hits[0] == (player, enemy_near)

    def test_hitbox_sprite_uses_hitbox_for_collision(self):
        """Sprites with TOML hitboxes use them for collision detection."""
        manager = CollisionManager()
        player_layer = manager.add_layer('player')
        enemy_layer = manager.add_layer('enemies')

        # Player with hitbox offset (4,2) and size 24x28
        player = HitboxSprite(world_x=100.0, world_y=100.0)
        # Enemy placed to overlap full rect but NOT hitbox
        # Full rect: (100, 100, 32, 32). Hitbox: (104, 102, 24, 28)
        # Enemy at (97, 97, 5, 5) overlaps full rect (100-97=3 < 5)
        # but doesn't overlap hitbox (104-97=7 > 5)
        enemy = FakeSprite(world_x=97.0, world_y=97.0)
        enemy.rect = pygame.Rect(97, 97, 5, 5)

        player_layer.add(player)
        enemy_layer.add(enemy)

        hits: list[tuple] = []
        manager.check_overlap(
            'player',
            'enemies',
            callback=lambda sprite_a, sprite_b: hits.append(
                (sprite_a, sprite_b),
            ),
        )
        # Should NOT collide because hitbox doesn't reach (97, 97)
        assert len(hits) == 0
