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
from glitchygames.collision.bounds import opaque_bounds, trims_transparent_hitbox
from glitchygames.collision.detection import snapped_world_position
from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode


def _default_rect(world_x: float, world_y: float, size: int = 32) -> pygame.Rect:
    """Create a default rect at world position."""
    return pygame.Rect(round(world_x), round(world_y), size, size)


@dataclass
class FakeSprite:
    """Minimal sprite with world position and rect."""

    world_x: float = 0.0
    world_y: float = 0.0
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 32, 32))

    def __post_init__(self):  # ruff: ignore[undocumented-magic-method]
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

    def __post_init__(self):  # ruff: ignore[undocumented-magic-method]
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


class TestGetSpriteCollisionRect:
    """Public sprite-to-collision-rect lookup shared by layers and the debug overlay."""

    def test_is_public_and_uses_world_position(self, mocker):
        """Sprites with world_x/world_y get their rect at the world position."""
        sprite = mocker.Mock(spec=['world_x', 'world_y', 'rect'])
        sprite.world_x, sprite.world_y = 100.0, 50.0
        sprite.rect = pygame.Rect(0, 0, 10, 20)
        rect = get_sprite_collision_rect(sprite)
        assert (rect.x, rect.y) == (100, 50)

    def test_sprite_without_world_position_uses_its_rect(self, mocker):
        """UI sprites without world_x/world_y fall back to their screen rect."""
        sprite = mocker.Mock(spec=['rect'])
        sprite.rect = pygame.Rect(7, 8, 9, 10)
        assert get_sprite_collision_rect(sprite) == pygame.Rect(7, 8, 9, 10)

    def test_sprite_without_any_rect_gets_empty_rect(self, mocker):
        """Sprites with neither world position nor rect get an empty rect."""
        sprite = mocker.Mock(spec=['rect'])
        sprite.rect = None
        assert get_sprite_collision_rect(sprite) == pygame.Rect(0, 0, 0, 0)


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


# --- Visible-pixel hitboxes ---


BALL_IMAGE_SIZE = 20
BALL_RADIUS = 5


def _ball_like_image() -> pygame.Surface:
    """A 20x20 colorkey image with a radius-5 circle in the middle, like BallSprite's."""
    image = pygame.Surface((BALL_IMAGE_SIZE, BALL_IMAGE_SIZE))
    image.set_colorkey(0)
    pygame.draw.circle(
        image,
        (255, 255, 255),
        (BALL_IMAGE_SIZE // 2, BALL_IMAGE_SIZE // 2),
        BALL_RADIUS,
        0,
    )
    return image


class ImageWorldSprite:
    """A world-space sprite with a real image and no TOML hitbox."""

    def __init__(self, *, image, world_x=0.0, world_y=0.0):
        """Initialize the test double."""
        self.image = image
        self.world_x = world_x
        self.world_y = world_y
        self.rect = image.get_rect()


class UntrimmedImageWorldSprite(ImageWorldSprite):
    """A world-space sprite whose class opts out of visible-pixel trimming."""

    TRIM_TRANSPARENT_HITBOX = False


class SnappingImageWorldSprite(ImageWorldSprite):
    """A world-space sprite with its own pixel snap mode, like BallSprite."""

    def __init__(self, *, pixel_snap_mode, **kwargs):
        """Initialize the test double."""
        super().__init__(**kwargs)
        self.pixel_snap_mode = pixel_snap_mode


class ImageScreenSprite:
    """A screen-space sprite (rect only, no world position) with a real image."""

    def __init__(self, *, image, x, y):
        """Initialize the test double."""
        self.image = image
        self.rect = image.get_rect(topleft=(x, y))


class TestOpaqueBounds:
    """opaque_bounds: the visible-pixel rect of an image, cached per surface."""

    def test_colorkey_circle_is_trimmed_to_its_visible_pixels(self):
        """The ball's radius-5 circle on a 20x20 colorkey image is a 10x10 box at (5, 5)."""
        assert opaque_bounds(_ball_like_image()) == pygame.Rect(5, 5, 10, 10)

    def test_per_pixel_alpha_is_honoured(self):
        """Fully transparent SRCALPHA pixels are trimmed."""
        image = pygame.Surface((8, 8), pygame.SRCALPHA)
        image.fill((10, 20, 30, 255), pygame.Rect(2, 3, 4, 1))
        assert opaque_bounds(image) == pygame.Rect(2, 3, 4, 1)

    def test_opaque_image_keeps_its_full_rect(self):
        """An image without colorkey or alpha is visible everywhere."""
        assert opaque_bounds(pygame.Surface((12, 7))) == pygame.Rect(0, 0, 12, 7)

    def test_fully_transparent_image_keeps_its_full_rect(self):
        """An invisible trigger image keeps its whole area instead of an empty rect."""
        image = pygame.Surface((16, 9), pygame.SRCALPHA)
        assert opaque_bounds(image) == pygame.Rect(0, 0, 16, 9)

    def test_returns_a_copy_callers_may_mutate(self):
        """Mutating a returned rect does not change later results."""
        image = _ball_like_image()
        first = opaque_bounds(image)
        first.move_ip(100, 100)
        assert opaque_bounds(image) == pygame.Rect(5, 5, 10, 10)

    def test_in_place_redraw_is_measured_again(self):
        """Bounds are measured on every call, so redrawing into the same surface is seen."""
        image = _ball_like_image()
        assert opaque_bounds(image) == pygame.Rect(5, 5, 10, 10)

        image.fill((0, 0, 0))
        image.fill((255, 255, 255), pygame.Rect(1, 2, 3, 4))
        assert opaque_bounds(image) == pygame.Rect(1, 2, 3, 4)

    def test_query_before_first_draw_then_draw(self):
        """A blank image (queried before the game draws it) is full-size, then trims once drawn.

        Brave Adventurer and Clockwork Keep create a blank SRCALPHA image and draw into it in
        update(), after dt_tick has already run collision checks.
        """
        image = pygame.Surface((16, 9), pygame.SRCALPHA)
        assert opaque_bounds(image) == pygame.Rect(0, 0, 16, 9)

        image.fill((255, 0, 0, 255), pygame.Rect(4, 2, 6, 5))
        assert opaque_bounds(image) == pygame.Rect(4, 2, 6, 5)

    def test_pose_change_in_place_follows(self):
        """A cobra-like pose change redrawn into the same surface moves the trimmed rect."""
        image = pygame.Surface((20, 20), pygame.SRCALPHA)
        image.fill((0, 255, 0, 255), pygame.Rect(2, 10, 6, 10))  # coiled
        assert opaque_bounds(image) == pygame.Rect(2, 10, 6, 10)

        image.fill((0, 0, 0, 0))
        image.fill((0, 255, 0, 255), pygame.Rect(2, 2, 16, 18))  # striking
        assert opaque_bounds(image) == pygame.Rect(2, 2, 16, 18)

    def test_trims_transparent_hitbox_defaults_to_true(self):
        """Sprites without the attribute trim; the attribute opts out."""
        assert trims_transparent_hitbox(ImageWorldSprite(image=_ball_like_image())) is True
        untrimmed = UntrimmedImageWorldSprite(image=_ball_like_image())
        assert trims_transparent_hitbox(untrimmed) is False


class TestVisiblePixelCollisionRect:
    """Collision rects default to the visible pixels of the sprite's image."""

    def test_world_sprite_rect_is_trimmed_to_visible_pixels(self):
        """A ball-like world sprite at (100, 50) collides as the 10x10 circle box."""
        sprite = ImageWorldSprite(image=_ball_like_image(), world_x=100.0, world_y=50.0)
        rect = get_collision_rect(sprite, world_x=100.0, world_y=50.0)
        assert rect == pygame.Rect(105, 55, 10, 10)

    def test_class_attribute_opts_out_of_trimming(self):
        """TRIM_TRANSPARENT_HITBOX = False on the class keeps the full image size."""
        sprite = UntrimmedImageWorldSprite(image=_ball_like_image(), world_x=100.0, world_y=50.0)
        rect = get_collision_rect(sprite, world_x=100.0, world_y=50.0)
        assert rect == pygame.Rect(100, 50, 20, 20)

    def test_instance_attribute_opts_out_of_trimming(self):
        """TRIM_TRANSPARENT_HITBOX = False on one instance keeps the full image size."""
        sprite = ImageWorldSprite(image=_ball_like_image(), world_x=100.0, world_y=50.0)
        sprite.TRIM_TRANSPARENT_HITBOX = False
        assert get_sprite_collision_rect(sprite) == pygame.Rect(100, 50, 20, 20)

    def test_toml_hitbox_wins_over_trimming(self):
        """A sprite with get_hitbox_world_rect keeps its explicit hitbox."""
        sprite = HitboxSprite(world_x=100.0, world_y=200.0)
        sprite.image = _ball_like_image()  # type: ignore[attr-defined]
        assert get_collision_rect(sprite, world_x=100.0, world_y=200.0) == pygame.Rect(
            104, 202, 24, 28
        )

    def test_screen_sprite_rect_is_trimmed_to_visible_pixels(self):
        """A sprite without a world position trims from its screen rect's top-left."""
        sprite = ImageScreenSprite(image=_ball_like_image(), x=30, y=40)
        assert get_sprite_collision_rect(sprite) == pygame.Rect(35, 45, 10, 10)

    def test_screen_sprite_opt_out_returns_its_rect(self):
        """A screen sprite that opts out collides as its full rect."""
        sprite = ImageScreenSprite(image=_ball_like_image(), x=30, y=40)
        sprite.TRIM_TRANSPARENT_HITBOX = False
        assert get_sprite_collision_rect(sprite) == pygame.Rect(30, 40, 20, 20)

    def test_check_overlap_ignores_transparent_corners(self):
        """Two ball-like sprites whose full boxes overlap but visible boxes do not miss."""
        manager = CollisionManager()
        manager.add_layer('balls')
        first = ImageWorldSprite(image=_ball_like_image(), world_x=100.0, world_y=100.0)
        # Full boxes overlap (100-120 vs 112-132); visible boxes (105-115 vs 117-127) do not.
        second = ImageWorldSprite(image=_ball_like_image(), world_x=112.0, world_y=100.0)
        manager.get_layer('balls').add(first)
        manager.get_layer('balls').add(second)

        hits: list[tuple] = []
        manager.check_overlap('balls', 'balls', callback=lambda a, b: hits.append((a, b)))
        assert hits == []


class TestSnappedCollisionPosition:
    """Collision rects use the sprite's own pixel snapping, matching where it is drawn."""

    def test_snap_mode_sprite_rounds_half_up(self):
        """NEAREST_HALF_UP draws 10.5 at 11, so the collision rect is at 11 too."""
        sprite = SnappingImageWorldSprite(
            image=_ball_like_image(),
            world_x=10.5,
            world_y=20.5,
            pixel_snap_mode=PixelSnapMode.NEAREST_HALF_UP,
        )
        assert snapped_world_position(sprite, world_x=10.5, world_y=20.5) == (11, 21)
        assert get_sprite_collision_rect(sprite) == pygame.Rect(16, 26, 10, 10)

    def test_floor_snap_mode_sprite(self):
        """FLOOR snapping is honoured as well."""
        sprite = SnappingImageWorldSprite(
            image=_ball_like_image(),
            world_x=10.9,
            world_y=-0.5,
            pixel_snap_mode=PixelSnapMode.FLOOR,
        )
        assert snapped_world_position(sprite, world_x=10.9, world_y=-0.5) == (10, -1)

    def test_sprite_without_snap_mode_uses_the_scene_default(self):
        """Sprites without pixel_snap_mode use the active scene mode (default half-up).

        Exact halves round up (10.5 -> 11), where the old round() fallback went to even.
        """
        sprite = FakeSprite(world_x=10.5, world_y=11.5)
        assert snapped_world_position(sprite, world_x=10.5, world_y=11.5) == (11, 12)
        assert get_collision_rect(sprite, world_x=10.5, world_y=11.5).topleft == (11, 12)

    def test_sprite_without_snap_mode_follows_a_floor_scene(self):
        """With a FLOOR scene active, a sprite without its own mode is floored."""
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        sprite = FakeSprite(world_x=10.5, world_y=-0.5)
        assert snapped_world_position(sprite, world_x=10.5, world_y=-0.5) == (10, -1)

    def test_sprite_own_mode_beats_the_scene_default(self):
        """A sprite's own pixel_snap_mode wins over the active scene mode."""
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        sprite = SnappingImageWorldSprite(
            image=_ball_like_image(),
            world_x=10.5,
            world_y=20.5,
            pixel_snap_mode=PixelSnapMode.NEAREST_EVEN,
        )
        assert snapped_world_position(sprite, world_x=10.5, world_y=20.5) == (10, 20)


class TestRedrawnGameSprites:
    """Games that redraw into the same image each update get up-to-date hitboxes."""

    @pytest.fixture(autouse=True)
    def real_display(self):
        """Brave Adventurer's sprites convert against a real display."""
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 600))

    def test_cobra_hitbox_follows_first_draw_and_strike(self):
        """Brave Adventurer's Cobra: blank before update(), then idle, then striking pose."""
        from glitchygames.examples.brave_adventurer.enemies import Cobra

        cobra = Cobra(500.0, pygame.sprite.LayeredDirty())
        full_rect = get_sprite_collision_rect(cobra)
        assert full_rect.size == cobra.image.get_size()

        cobra.update()
        idle_rect = get_sprite_collision_rect(cobra)
        idle_visible = cobra.image.get_bounding_rect()
        assert idle_rect.size == idle_visible.size
        assert idle_rect.topleft == (
            full_rect.x + idle_visible.x,
            full_rect.y + idle_visible.y,
        )

        cobra.striking = True
        cobra.update()
        striking_visible = cobra.image.get_bounding_rect()
        assert striking_visible != idle_visible
        assert get_sprite_collision_rect(cobra).size == striking_visible.size


class TestPapyrusHitboxScale:
    """Papyrus draws sprites at SPRITE_SCALE, so its TOML hitboxes must scale with them."""

    @pytest.fixture(autouse=True)
    def real_display(self):
        """Papyrus sprites load TOML art and convert against a real display."""
        pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 600))

    def test_scaled_papyrus_player_collides_at_twice_the_toml_hitbox(self):
        """After its first tick the player's collision rect is the TOML hitbox times 2."""
        from glitchygames.examples.brave_adventurer_papyrus.constants import SPRITE_SCALE
        from glitchygames.examples.brave_adventurer_papyrus.player import PapyrusPlayer

        player = PapyrusPlayer(100.0, 200.0, pygame.sprite.LayeredDirty())
        player.dt_tick(0.0)

        assert player.hitbox_scale == SPRITE_SCALE == 2
        frame = player.get_current_frame()
        assert frame is not None
        native_hitbox = frame.hitbox if frame.has_explicit_hitbox else player.default_hitbox
        assert native_hitbox is not None
        draw_offset_x, draw_offset_y = player.draw_offset  # BOTTOM frame anchoring
        assert get_sprite_collision_rect(player) == pygame.Rect(
            round(player.world_x) + native_hitbox.x * 2 + draw_offset_x,
            round(player.world_y) + native_hitbox.y * 2 + draw_offset_y,
            native_hitbox.width * 2,
            native_hitbox.height * 2,
        )

    @pytest.mark.parametrize(
        'sprite_name', ['player', 'cobra', 'scarab', 'scorpion', 'gold_scarab']
    )
    def test_freshly_constructed_sprites_have_scaled_hitboxes_before_any_tick(self, sprite_name):
        """No frame ever uses native-size hitboxes: the scale is set when the sprite is built."""
        from glitchygames.examples.brave_adventurer_papyrus.constants import SPRITE_SCALE
        from glitchygames.examples.brave_adventurer_papyrus.enemies import (
            PapyrusCobra,
            PapyrusScarab,
            PapyrusScorpion,
        )
        from glitchygames.examples.brave_adventurer_papyrus.player import PapyrusPlayer
        from glitchygames.examples.brave_adventurer_papyrus.terrain import PapyrusGoldScarab

        group = pygame.sprite.LayeredDirty()
        builders = {
            'player': lambda: PapyrusPlayer(100.0, 200.0, group),
            'cobra': lambda: PapyrusCobra(100.0, group),
            'scarab': lambda: PapyrusScarab(100.0, group),
            'scorpion': lambda: PapyrusScorpion(100.0, group),
            'gold_scarab': lambda: PapyrusGoldScarab(100.0, 200.0, group),
        }
        sprite = builders[sprite_name]()

        assert sprite.hitbox_scale == SPRITE_SCALE
        frame = sprite.get_current_frame()
        assert frame is not None
        if frame.has_explicit_hitbox:
            native_hitbox = frame.hitbox
        elif sprite.default_hitbox is not None:
            native_hitbox = sprite.default_hitbox
        else:
            native_hitbox = frame.opaque_bounds()
        assert sprite.hitbox.size == (
            native_hitbox.width * SPRITE_SCALE,
            native_hitbox.height * SPRITE_SCALE,
        )

    def test_scale_one_keeps_native_hitbox(self):
        """apply_transparency_and_scale with scale_factor=1 leaves hitboxes native."""
        from glitchygames.examples.brave_adventurer_papyrus.player import PapyrusPlayer
        from glitchygames.examples.brave_adventurer_papyrus.sprite_utils import (
            apply_transparency_and_scale,
        )

        player = PapyrusPlayer(100.0, 200.0, pygame.sprite.LayeredDirty())
        apply_transparency_and_scale(player, scale_factor=1)

        assert player.hitbox_scale == 1
        frame = player.get_current_frame()
        assert frame is not None
        native_hitbox = frame.hitbox if frame.has_explicit_hitbox else player.default_hitbox
        assert native_hitbox is not None
        assert player.hitbox == native_hitbox.move(player.draw_offset)


class TestCallbacksThatRemoveSprites:
    """Callbacks may remove sprites from the layers being checked without skipping pairs."""

    def test_check_overlap_collects_two_overlapped_pickups_in_one_pass(self):
        """Removing the first pickup inside the callback must not skip the second."""
        manager = CollisionManager()
        manager.add_layer('player')
        manager.add_layer('cogs')
        player = FakeSprite(world_x=100.0, world_y=100.0)
        first_cog = FakeSprite(world_x=110.0, world_y=110.0)
        second_cog = FakeSprite(world_x=120.0, world_y=105.0)
        manager.get_layer('player').add(player)
        manager.get_layer('cogs').add(first_cog)
        manager.get_layer('cogs').add(second_cog)
        collected = []

        def collect(_player, cog):
            collected.append(cog)
            manager.get_layer('cogs').remove(cog)

        manager.check_overlap('player', 'cogs', callback=collect)

        assert collected == [first_cog, second_cog]
        assert manager.get_layer('cogs').sprites == []

    def test_check_single_collects_two_overlapped_pickups_in_one_pass(self):
        """check_single iterates a snapshot too."""
        manager = CollisionManager()
        manager.add_layer('cogs')
        player = FakeSprite(world_x=100.0, world_y=100.0)
        first_cog = FakeSprite(world_x=110.0, world_y=110.0)
        second_cog = FakeSprite(world_x=120.0, world_y=105.0)
        manager.get_layer('cogs').add(first_cog)
        manager.get_layer('cogs').add(second_cog)
        collected = []

        def collect(_player, cog):
            collected.append(cog)
            manager.get_layer('cogs').remove(cog)

        manager.check_single(player, 'cogs', callback=collect)

        assert collected == [first_cog, second_cog]
