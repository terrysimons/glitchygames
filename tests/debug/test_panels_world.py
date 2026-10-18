"""Tests for the debug overlay collision and physics panels (real pygame surfaces)."""

import types

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.collision.layers import CollisionManager, get_sprite_collision_rect
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
from glitchygames.game_objects.ball import BallSprite

SURFACE_SIZE = (400, 300)


class WorldSprite:
    """A tiny sprite positioned in world space, drawn as if the camera were unscrolled."""

    def __init__(self, *, world_x, world_y, width=20, height=20):
        """Initialize the test double."""
        self.world_x = world_x
        self.world_y = world_y
        self.rect = pygame.Rect(round(world_x), round(world_y), width, height)


def place_through_camera(sprite, camera):
    """Position a world sprite's drawn rect through the camera, as games do every frame."""
    sprite.rect.topleft = camera.world_to_screen(sprite.world_x, sprite.world_y)


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
def ball():
    """A real BallSprite (needs a display for its image and screen size).

    Returns:
        A BallSprite.

    """
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode(SURFACE_SIZE)
    return BallSprite()


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
    draw_collision_panel(surface=surface, scene=scene, screen_offset=screen_offset, font=font)


class TestScreenRectFor:
    """World to screen conversion."""

    def test_world_sprite_converted_through_scrolled_camera(self, camera):
        """A sprite at world x=100 with the camera at 50 sits at screen x=50."""
        camera.world_x = 50
        sprite = WorldSprite(world_x=100, world_y=30)
        place_through_camera(sprite, camera)
        rect = screen_rect_for(sprite=sprite, screen_offset=(0, 0))
        assert (rect.x, rect.y) == (50, 30)
        assert (rect.width, rect.height) == (20, 20)

    def test_fractional_camera_outline_matches_drawn_sprite(self):
        """World x=100.6 with camera x=0.4 is drawn at 100; the outline must be at 100 too.

        Rounding the world position (101) and then converting it through the camera rounds
        twice and lands one pixel right of the sprite.
        """
        camera = Camera2D(SURFACE_SIZE[0], SURFACE_SIZE[1])
        camera.world_x = 0.4
        sprite = WorldSprite(world_x=100.6, world_y=30.0)
        sprite.rect.topleft = camera.apply(sprite.world_x, sprite.world_y)
        assert sprite.rect.x == 100

        rect = screen_rect_for(sprite=sprite, screen_offset=(0, 0))
        assert rect.left == sprite.rect.x
        assert rect.top == sprite.rect.y

    def test_ball_outline_uses_its_snap_mode_and_visible_pixels(self, ball):
        """A NEAREST_HALF_UP ball at x=10.5 is drawn at 11; its circle box starts at 11 + 5."""
        ball.world_x = 10.5
        ball.world_y = 20.0
        assert ball.rect.x == 11

        collision_rect = get_sprite_collision_rect(ball)
        assert collision_rect == pygame.Rect(16, 25, 10, 10)
        outline_rect = screen_rect_for(sprite=ball, screen_offset=(0, 0))
        assert outline_rect == pygame.Rect(16, 25, 10, 10)

    def test_outline_follows_world_shaken_sprite_rect(self):
        """The outline follows the drawn rect, so a WORLD shake moves it with the sprite."""
        sprite = WorldSprite(world_x=100, world_y=30)
        sprite.rect.topleft = (97, 32)  # drawn through a shaken camera
        rect = screen_rect_for(sprite=sprite, screen_offset=(0, 0))
        assert rect.topleft == (97, 32)

    def test_screen_sprite_used_as_is_plus_offset(self, camera):
        """A screen-space sprite ignores the camera; the offset still applies."""
        camera.world_x = 50
        sprite = ScreenSprite(x=10, y=20)
        rect = screen_rect_for(sprite=sprite, screen_offset=(5, 3))
        assert (rect.x, rect.y) == (15, 23)

    def test_does_not_mutate_sprite_rect(self, camera):
        """The sprite's own rect is never modified."""
        sprite = ScreenSprite(x=10, y=20)
        screen_rect_for(sprite=sprite, screen_offset=(5, 3))
        assert (sprite.rect.x, sprite.rect.y) == (10, 20)


class TestCollisionPanel:
    """Hitbox outlines and legend."""

    def test_outline_follows_scrolled_camera(self, surface, camera, font):
        """Review focus 1: with the camera scrolled, the outline is at the screen position."""
        camera.world_x = 50
        sprite = WorldSprite(world_x=100, world_y=40)
        place_through_camera(sprite, camera)
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
        layered = WorldSprite(world_x=300, world_y=200)
        scene = build_scene(camera=camera, layers={'a': [layered]}, extra_sprites=[loose])
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

    def test_scene_with_no_layers_draws_nothing(self, surface, camera, font):
        """A collision manager with no layers draws no outlines and no legend."""
        loose = ScreenSprite(x=60, y=70)
        scene = build_scene(camera=camera, extra_sprites=[loose])
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((60, 70))[:3] == (0, 0, 0)
        font.render.assert_not_called()

    def test_unlayered_world_sprite_outlined_at_converted_position(self, surface, camera, font):
        """An unlayered world sprite follows the scrolled camera too."""
        camera.world_x = 50
        loose = WorldSprite(world_x=100, world_y=40)
        far_sprite = WorldSprite(world_x=300, world_y=200)
        place_through_camera(loose, camera)
        place_through_camera(far_sprite, camera)
        scene = build_scene(camera=camera, layers={'a': [far_sprite]}, extra_sprites=[loose])
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((50, 40))[:3] == UNLAYERED_COLOR

    def test_sprite_in_two_layers_uses_first_layer_color(self, surface, camera, font):
        """A sprite in two layers is outlined once, in the first layer's colour."""
        shared = WorldSprite(world_x=10, world_y=10)
        scene = build_scene(camera=camera, layers={'a': [shared], 'b': [shared]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((10, 10))[:3] == LAYER_PALETTE[0]


class TestPhysicsPanel:
    """Velocity arrows, ground bar and velocity text."""

    def draw_physics(self, *, surface, scene, camera, font, screen_offset=(0, 0)):
        """Call draw_physics_panel with keyword arguments."""
        draw_physics_panel(surface=surface, scene=scene, screen_offset=screen_offset, font=font)

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
        place_through_camera(sprite, camera)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((60 + 30, 110))[:3] == ARROW_COLOR

    def test_arrow_shifted_by_screen_offset(self, surface, camera, font):
        """screen_offset=(5, 3) moves the arrow start by (5, 3)."""
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(
            surface=surface, scene=scene, camera=camera, font=font, screen_offset=(5, 3)
        )
        assert surface.get_at((115, 113))[:3] == ARROW_COLOR
        assert surface.get_at((145, 113))[:3] == ARROW_COLOR
        assert surface.get_at((110, 110))[:3] != ARROW_COLOR

    def test_ground_bar_is_two_pixels_tall(self, surface, camera, font):
        """The ground bar spans exactly two rows under the sprite."""
        sprite = PhysicsSprite(body=Body(on_ground=True), world_x=10, world_y=10)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        self.draw_physics(surface=surface, scene=scene, camera=camera, font=font)
        assert surface.get_at((20, 31))[:3] == GROUNDED_COLOR
        assert surface.get_at((20, 32))[:3] != GROUNDED_COLOR

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


class TestRealFont:
    """Both panels work with a real pygame font, not just a mock."""

    def test_both_panels_draw_with_real_font(self, surface, camera):
        """A render() signature mismatch cannot hide behind a mock."""
        pygame.font.init()
        real_font = pygame.font.Font(None, 16)
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=real_font)
        draw_physics_panel(surface=surface, scene=scene, screen_offset=(0, 0), font=real_font)
        assert surface.get_at((100, 100))[:3] == LAYER_PALETTE[0]


class TestReadOnlyCamera:
    """The panels never mark the camera as applied."""

    def test_panels_leave_camera_unapplied(self, surface, camera, font):
        """Drawing both panels must not flip Camera2D.has_been_applied."""
        sprite = PhysicsSprite(body=Body(velocity_x=300), world_x=100, world_y=100)
        scene = build_scene(camera=camera, layers={'a': [sprite]})
        draw_collision(surface=surface, scene=scene, camera=camera, font=font)
        draw_physics_panel(surface=surface, scene=scene, screen_offset=(0, 0), font=font)
        assert camera.has_been_applied is False
