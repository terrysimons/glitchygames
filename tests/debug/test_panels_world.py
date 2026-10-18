"""Tests for the debug overlay collision and physics panels (real pygame surfaces)."""

import types

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.collision.layers import CollisionManager
from glitchygames.debug.panels import (
    AIRBORNE_COLOR,
    ARROW_COLOR,
    GROUNDED_COLOR,
    LAYER_PALETTE,
    OVERLAP_COLOR,
    UNLAYERED_COLOR,
    draw_collision_panel,
    draw_physics_panel,
    screen_rect_for,
)

SURFACE_SIZE = (400, 300)


class WorldSprite:
    """A tiny sprite positioned in world space."""

    def __init__(self, *, world_x, world_y, width=20, height=20):
        """Initialize the test double."""
        self.world_x = world_x
        self.world_y = world_y
        self.rect = pygame.Rect(0, 0, width, height)


class ScreenSprite:
    """A tiny sprite positioned in screen space only."""

    def __init__(self, *, x, y, width=20, height=20):
        """Initialize the test double."""
        self.rect = pygame.Rect(x, y, width, height)


class Body:
    """A tiny physics body."""

    def __init__(self, *, velocity_x=0.0, velocity_y=0.0, on_ground=False):
        """Initialize the test double."""
        self.velocity_x = velocity_x
        self.velocity_y = velocity_y
        self.world_x = 0.0
        self.world_y = 0.0
        self.on_ground = on_ground


class PhysicsSprite(WorldSprite):
    """A world sprite with a physics body."""

    def __init__(self, *, body, **kwargs):
        """Initialize the test double."""
        super().__init__(**kwargs)
        self.physics = body


@pytest.fixture
def surface():
    """A real, black surface.

    Returns:
        A pygame.Surface.

    """
    return pygame.Surface(SURFACE_SIZE)


@pytest.fixture
def camera():
    """An unscrolled camera.

    Returns:
        A Camera2D.

    """
    return Camera2D(SURFACE_SIZE[0], SURFACE_SIZE[1])


@pytest.fixture
def font(mocker):
    """A font whose render returns a small real surface.

    Returns:
        A mock font.

    """
    mock_font = mocker.Mock()
    mock_font.render.side_effect = lambda *args, **kwargs: pygame.Surface((4, 4))
    return mock_font


def build_scene(*, camera, layers=None, extra_sprites=()):
    """Build a scene namespace with a real CollisionManager.

    Args:
        camera: The camera.
        layers: Mapping of layer name to sprite list, in creation order.
        extra_sprites: Sprites present in all_sprites but in no layer.

    Returns:
        A SimpleNamespace scene.

    """
    collisions = CollisionManager()
    all_sprites = list(extra_sprites)
    for name, sprites in (layers or {}).items():
        layer = collisions.add_layer(name)
        for sprite in sprites:
            layer.add(sprite)
            all_sprites.append(sprite)
    return types.SimpleNamespace(collisions=collisions, all_sprites=all_sprites, camera=camera)


def draw_collision(*, surface, scene, camera, font, screen_offset=(0, 0)):
    """Call draw_collision_panel with keyword arguments."""
    draw_collision_panel(
        surface=surface, scene=scene, camera=camera, screen_offset=screen_offset, font=font
    )


class TestScreenRectFor:
    """World to screen conversion."""

    def test_world_sprite_converted_through_scrolled_camera(self, camera):
        """A sprite at world x=100 with the camera at 50 sits at screen x=50."""
        camera.world_x = 50
        sprite = WorldSprite(world_x=100, world_y=30)
        rect = screen_rect_for(sprite=sprite, camera=camera, screen_offset=(0, 0))
        assert (rect.x, rect.y) == (50, 30)
        assert (rect.width, rect.height) == (20, 20)

    def test_screen_sprite_used_as_is_plus_offset(self, camera):
        """A screen-space sprite ignores the camera; the offset still applies."""
        camera.world_x = 50
        sprite = ScreenSprite(x=10, y=20)
        rect = screen_rect_for(sprite=sprite, camera=camera, screen_offset=(5, 3))
        assert (rect.x, rect.y) == (15, 23)

    def test_does_not_mutate_sprite_rect(self, camera):
        """The sprite's own rect is never modified."""
        sprite = ScreenSprite(x=10, y=20)
        screen_rect_for(sprite=sprite, camera=camera, screen_offset=(5, 3))
        assert (sprite.rect.x, sprite.rect.y) == (10, 20)


class TestCollisionPanel:
    """Hitbox outlines and legend."""

    def test_outline_follows_scrolled_camera(self, surface, camera, font):
        """Review focus 1: with the camera scrolled, the outline is at the screen position."""
        camera.world_x = 50
        sprite = WorldSprite(world_x=100, world_y=40)
        scene = build_scene(camera=camera, layers={'player': [sprite]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((50, 40))[:3] == LAYER_PALETTE[0]
        assert surface.get_at((100, 40))[:3] != LAYER_PALETTE[0]

    def test_layers_use_distinct_palette_colors(self, surface, camera, font):
        """Each layer gets the next palette colour in creation order."""
        first = WorldSprite(world_x=10, world_y=10)
        second = WorldSprite(world_x=200, world_y=10)
        scene = build_scene(camera=camera, layers={'a': [first], 'b': [second]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((10, 10))[:3] == LAYER_PALETTE[0]
        assert surface.get_at((200, 10))[:3] == LAYER_PALETTE[1]

    def test_palette_has_distinct_colors(self):
        """The palette offers at least eight distinct colours."""
        assert len(set(LAYER_PALETTE)) >= 8

    def test_cross_layer_overlap_is_white(self, surface, camera, font):
        """Overlapping sprites in different layers are both outlined in OVERLAP_COLOR."""
        first = WorldSprite(world_x=10, world_y=10)
        second = WorldSprite(world_x=20, world_y=20)
        scene = build_scene(camera=camera, layers={'a': [first], 'b': [second]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((10, 10))[:3] == OVERLAP_COLOR
        assert surface.get_at((20, 20))[:3] == OVERLAP_COLOR

    def test_same_layer_overlap_keeps_layer_color(self, surface, camera, font):
        """Overlap inside one layer is not flagged."""
        first = WorldSprite(world_x=10, world_y=10)
        second = WorldSprite(world_x=20, world_y=20)
        scene = build_scene(camera=camera, layers={'a': [first, second]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((10, 10))[:3] == LAYER_PALETTE[0]
        assert surface.get_at((20, 20))[:3] == LAYER_PALETTE[0]

    def test_unlayered_sprite_gets_unlayered_color(self, surface, camera, font):
        """A sprite in all_sprites but in no layer is outlined at its rect."""
        loose = ScreenSprite(x=60, y=70)
        scene = build_scene(camera=camera, extra_sprites=[loose])
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((60, 70))[:3] == UNLAYERED_COLOR

    def test_legend_row_per_layer_with_count(self, surface, camera, font):
        """The legend writes each layer name with its sprite count."""
        scene = build_scene(
            camera=camera,
            layers={
                'player': [WorldSprite(world_x=10, world_y=10)],
                'enemies': [
                    WorldSprite(world_x=100, world_y=100),
                    WorldSprite(world_x=150, world_y=100),
                ],
            },
        )
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        rendered_texts = [call.args[0] for call in font.render.call_args_list]
        assert any('player' in text and '1' in text for text in rendered_texts)
        assert any('enemies' in text and '2' in text for text in rendered_texts)

    def test_screen_offset_shifts_outlines(self, surface, camera, font):
        """screen_offset=(5, 3) moves the outline by (5, 3)."""
        sprite = WorldSprite(world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font, screen_offset=(5, 3))
        assert surface.get_at((105, 103))[:3] == LAYER_PALETTE[0]
        assert surface.get_at((100, 100))[:3] != LAYER_PALETTE[0]

    def test_scene_without_collisions_draws_nothing(self, surface, camera, font):
        """No collisions attribute means no drawing and no error."""
        scene = types.SimpleNamespace(all_sprites=[ScreenSprite(x=60, y=70)], camera=camera)
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert pygame.mask.from_threshold(surface, (0, 0, 0), (1, 1, 1, 255)).count() == (
            SURFACE_SIZE[0] * SURFACE_SIZE[1]
        )
        font.render.assert_not_called()


class TestPhysicsPanel:
    """Velocity arrows, ground bar and velocity text."""

    def draw_physics(self, *, surface, scene, camera, font, screen_offset=(0, 0)):
        """Call draw_physics_panel with keyword arguments."""
        draw_physics_panel(
            surface=surface, scene=scene, camera=camera, screen_offset=screen_offset, font=font
        )

    def test_arrow_length_is_velocity_times_arrow_seconds(self, surface, camera, font):
        """Velocity (300, 0) gives a 30 px arrow from the rect centre."""
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        centre_x, centre_y = 110, 110
        assert surface.get_at((centre_x + 30, centre_y))[:3] == ARROW_COLOR
        assert surface.get_at((centre_x + 15, centre_y))[:3] == ARROW_COLOR
        assert surface.get_at((centre_x + 34, centre_y))[:3] != ARROW_COLOR

    def test_arrow_capped_at_maximum_pixels(self, surface, camera, font):
        """Velocity (5000, 0) is capped at 80 px."""
        sprite = PhysicsSprite(body=Body(velocity_x=5000), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((110 + 80, 110))[:3] == ARROW_COLOR
        assert surface.get_at((110 + 84, 110))[:3] != ARROW_COLOR

    def test_ground_bar_green_on_ground_red_airborne(self, surface, camera, font):
        """The bar under the sprite is green when grounded and red otherwise."""
        grounded = PhysicsSprite(body=Body(on_ground=True), world_x=10, world_y=10)
        airborne = PhysicsSprite(body=Body(on_ground=False), world_x=200, world_y=10)
        scene = build_scene(camera=camera, layers={'a': [grounded, airborne]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((20, 30))[:3] == GROUNDED_COLOR
        assert surface.get_at((210, 30))[:3] == AIRBORNE_COLOR

    def test_velocity_text_rendered(self, surface, camera, font):
        """The velocity is written as '(300, 0)'."""
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        rendered_texts = [call.args[0] for call in font.render.call_args_list]
        assert any('(300, 0)' in text for text in rendered_texts)

    def test_arrow_follows_scrolled_camera(self, surface, camera, font):
        """The arrow starts at the sprite's screen centre, not its world centre."""
        camera.world_x = 50
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((60 + 30, 110))[:3] == ARROW_COLOR

    def test_sprites_without_physics_are_skipped(self, surface, camera, font):
        """Sprites lacking a physics body draw nothing and raise nothing."""
        scene = build_scene(camera=camera, layers={'a': [WorldSprite(world_x=10, world_y=10)]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        font.render.assert_not_called()

    def test_scene_without_all_sprites_draws_nothing(self, surface, camera, font):
        """A scene lacking all_sprites is tolerated."""
        scene = types.SimpleNamespace(camera=camera)
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        font.render.assert_not_called()


class TestReadOnlyCamera:
    """The panels never mark the camera as applied."""

    def test_panels_leave_camera_unapplied(self, surface, camera, font):
        """Drawing both panels must not flip Camera2D.has_been_applied."""
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        draw_physics_panel(
            surface=surface, scene=scene, camera=camera, screen_offset=(0, 0), font=font
        )
        assert camera.has_been_applied is False
