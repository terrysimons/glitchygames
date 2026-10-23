"""Tests for Camera2D viewport system."""

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.display_mode import set_display_mode
from glitchygames.effects.shake import Shake, ShakeAxis, ShakeStyle


class TestCamera2DApply:
    """World-to-screen coordinate conversion."""

    def test_apply_at_origin(self):
        """At camera origin, world coords equal screen coords."""
        camera = Camera2D(screen_width=800, screen_height=600)
        assert camera.apply(0.0, 0.0) == (0, 0)
        assert camera.apply(100.0, 200.0) == (100, 200)

    def test_apply_with_camera_offset(self):
        """Objects shift left/up by camera position."""
        camera = Camera2D(screen_width=800, screen_height=600)
        camera.world_x = 100.0
        camera.world_y = 50.0
        assert camera.apply(150.0, 75.0) == (50, 25)

    def test_apply_rounds_to_pixels(self):
        """Subpixel world coordinates are rounded to integer screen coords."""
        camera = Camera2D(screen_width=800, screen_height=600)
        camera.world_x = 0.3
        assert camera.apply(10.0, 0.0) == (10, 0)


class TestCamera2DHasBeenApplied:
    """Tracking whether any sprite is positioned through the camera."""

    def test_flips_on_first_apply(self):
        camera = Camera2D(screen_width=800, screen_height=600)
        assert camera.has_been_applied is False
        camera.apply(1.0, 2.0)
        assert camera.has_been_applied is True

    def test_world_to_screen_does_not_flip(self):
        """world_to_screen is for read-only tools and never marks the camera as applied."""
        camera = Camera2D(screen_width=800, screen_height=600)
        camera.world_to_screen(1.0, 2.0)
        assert camera.has_been_applied is False


class TestCamera2DUpdate:
    """Smooth follow behavior."""

    def test_moves_toward_target(self):
        """Camera moves toward target position over time."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=0.5)
        camera.update(target_x=500.0, target_y=300.0, dt=1.0 / 60.0)
        assert camera.world_x > 0.0
        assert camera.world_y > 0.0

    def test_smooth_factor_one_snaps(self):
        """With smooth_factor=1.0, camera snaps instantly to target."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=1.0)
        camera.update(target_x=500.0, target_y=300.0, dt=1.0 / 60.0)
        assert camera.world_x == pytest.approx(500.0, abs=0.1)
        assert camera.world_y == pytest.approx(300.0, abs=0.1)

    def test_lead_offset_applied(self):
        """Lead offsets the target so the tracked object isn't at viewport edge."""
        camera = Camera2D(
            screen_width=800,
            screen_height=600,
            smooth_factor=1.0,
            lead_x=250.0,
            lead_y=100.0,
        )
        camera.update(target_x=500.0, target_y=300.0, dt=1.0 / 60.0)
        # Target 500 minus lead 250 = 250
        assert camera.world_x == pytest.approx(250.0, abs=0.1)
        assert camera.world_y == pytest.approx(200.0, abs=0.1)

    def test_converges_over_multiple_frames(self):
        """Camera converges to target over many frames."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=0.1)
        for _ in range(300):
            camera.update(target_x=500.0, target_y=0.0, dt=1.0 / 60.0)
        assert camera.world_x == pytest.approx(500.0, abs=0.5)


class TestCamera2DBounds:
    """World bounds clamping."""

    def test_min_x_clamp(self):
        """Camera doesn't scroll left past min_x."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=1.0)
        camera.set_bounds(min_x=0.0)
        camera.update(target_x=-100.0, target_y=0.0, dt=1.0 / 60.0)
        assert camera.world_x == 0.0

    def test_min_y_clamp(self):
        """Camera doesn't scroll up past min_y."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=1.0)
        camera.set_bounds(min_y=0.0)
        camera.update(target_x=0.0, target_y=-100.0, dt=1.0 / 60.0)
        assert camera.world_y == 0.0

    def test_max_x_clamp(self):
        """Camera doesn't scroll right past max_x."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=1.0)
        camera.set_bounds(max_x=1000.0)
        camera.update(target_x=2000.0, target_y=0.0, dt=1.0 / 60.0)
        assert camera.world_x == 1000.0

    def test_no_bounds_by_default(self):
        """Without bounds, camera can go anywhere."""
        camera = Camera2D(screen_width=800, screen_height=600, smooth_factor=1.0)
        camera.update(target_x=-500.0, target_y=-300.0, dt=1.0 / 60.0)
        assert camera.world_x < 0.0
        assert camera.world_y < 0.0

    def test_bounds_property_reports_configured_edges(self):
        """Bounds returns (min_x, min_y, max_x, max_y), with None for unbounded edges."""
        camera = Camera2D(screen_width=200, screen_height=100)
        assert camera.bounds == (None, None, None, None)
        camera.set_bounds(min_x=0.0, max_x=400.0)
        assert camera.bounds == (0.0, None, 400.0, None)


class TestCamera2DVisibility:
    """Viewport visibility culling."""

    def test_onscreen_object_visible(self):
        """Object within viewport is visible."""
        camera = Camera2D(screen_width=800, screen_height=600)
        assert camera.is_visible(world_x=100.0, width=50.0) is True

    def test_offscreen_left_not_visible(self):
        """Object far to the left is not visible."""
        camera = Camera2D(screen_width=800, screen_height=600)
        camera.world_x = 1000.0
        assert camera.is_visible(world_x=0.0, width=50.0) is False

    def test_offscreen_right_not_visible(self):
        """Object far to the right is not visible."""
        camera = Camera2D(screen_width=800, screen_height=600)
        assert camera.is_visible(world_x=2000.0, width=50.0) is False

    def test_margin_allows_near_edge(self):
        """Objects just outside the viewport are visible within the margin."""
        camera = Camera2D(
            screen_width=800,
            screen_height=600,
            visibility_margin=100.0,
        )
        # Object at x=-90 with width=50 is within 100px margin of left edge
        assert camera.is_visible(world_x=-90.0, width=50.0) is True

    def test_x_only_check_when_no_height(self):
        """With height=0, only X-axis is checked (backward compatible)."""
        camera = Camera2D(screen_width=800, screen_height=600)
        # Object in X range but way off in Y -- still visible with height=0
        assert camera.is_visible(world_x=100.0, width=50.0, world_y=9999.0) is True

    def test_y_check_when_height_provided(self):
        """With height > 0, both axes are checked."""
        camera = Camera2D(screen_width=800, screen_height=600)
        # Object in X range but way off in Y
        assert (
            camera.is_visible(
                world_x=100.0,
                width=50.0,
                world_y=9999.0,
                height=50.0,
            )
            is False
        )


class TestCamera2DParallax:
    """Parallax layers follow the camera (regression for BUGS.md #21)."""

    @staticmethod
    def _add_recording_layer(camera, mocker):
        if not pygame.get_init():
            pygame.init()
        layer = camera.add_background_layer(
            scroll_factor=0.5,
            draw_function=lambda surface, offset_x, offset_y: None,
            layer_depth=0,
            groups=pygame.sprite.LayeredDirty(),
        )
        return mocker.patch.object(layer, 'update_scroll')

    def test_update_scrolls_parallax_layers(self, mocker):
        """update() passes the new camera position to every parallax layer."""
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        update_scroll = self._add_recording_layer(camera, mocker)
        camera.update(target_x=300.0, target_y=40.0, dt=1.0 / 60.0)
        update_scroll.assert_called_once_with(
            pytest.approx(camera.world_x), pytest.approx(camera.world_y)
        )

    def test_snap_to_scrolls_parallax_layers_once(self, mocker):
        """snap_to() updates each layer exactly once (the duplicate loop is gone)."""
        camera = Camera2D(screen_width=200, screen_height=100)
        update_scroll = self._add_recording_layer(camera, mocker)
        camera.snap_to(target_x=120.0, target_y=30.0)
        update_scroll.assert_called_once_with(120.0, 30.0)


class RecordingDrawFunction:
    """A real layer draw function: records each call and draws whatever the game state says.

    The marker's color comes from `color` (game state the camera knows nothing about), so a
    layer that redraws after it changes shows the new color, and one that did not keeps the old.
    """

    def __init__(self) -> None:
        """Start with no calls recorded and a red marker."""
        self.calls: list[tuple[float, float]] = []
        self.color = (200, 40, 40)

    def __call__(self, surface: pygame.Surface, offset_x: float, offset_y: float) -> None:
        self.calls.append((offset_x, offset_y))
        pygame.draw.rect(surface, self.color, (round(offset_x) % 150, round(offset_y) % 60, 20, 20))


def _add_layer(*, camera, scroll_factor, animated=False):
    """Add a layer drawn by a RecordingDrawFunction; return (layer, draw function, group)."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(200, 100))
    draw_function = RecordingDrawFunction()
    group = pygame.sprite.LayeredDirty()
    layer = camera.add_background_layer(
        scroll_factor=scroll_factor,
        draw_function=draw_function,
        layer_depth=0,
        groups=group,
        animated=animated,
    )
    return layer, draw_function, group


def _rendered_pixels(group) -> bytes:
    """Draw the layer group onto a fresh opaque surface and return its RGBA pixels."""
    target = pygame.Surface((200, 100), depth=32)
    target.fill((0, 0, 0))
    group.draw(target)
    return pygame.image.tobytes(target, 'RGBA')


class TestParallaxLayerRedrawsOnlyOnChange:
    """A layer redraws when its offset changes; an animated layer redraws every frame."""

    def test_still_camera_does_not_redraw_a_scrolling_layer(self):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        _layer, draw_function, _group = _add_layer(camera=camera, scroll_factor=0.5)

        camera.snap_to(target_x=100.0, target_y=20.0)
        camera.snap_to(target_x=100.0, target_y=20.0)
        camera.update(target_x=100.0, target_y=20.0, dt=1.0 / 60.0)
        camera.advance_shake(dt=1.0 / 60.0)

        assert draw_function.calls == [(50.0, 10.0)]

    def test_camera_move_within_the_same_pixel_does_not_redraw(self):
        """Layers scroll from the snapped camera, so a sub-pixel move changes no offset."""
        camera = Camera2D(screen_width=200, screen_height=100)
        _layer, draw_function, _group = _add_layer(camera=camera, scroll_factor=0.5)

        camera.snap_to(target_x=100.0, target_y=0.0)
        camera.snap_to(target_x=100.2, target_y=0.0)

        assert draw_function.calls == [(50.0, 0.0)]

    def test_moved_camera_redraws_a_scrolling_layer(self):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        _layer, draw_function, _group = _add_layer(camera=camera, scroll_factor=0.5)

        camera.snap_to(target_x=100.0, target_y=0.0)
        camera.update(target_x=101.0, target_y=0.0, dt=1.0 / 60.0)

        assert draw_function.calls == [(50.0, 0.0), (50.5, 0.0)]

    def test_static_layer_draws_once(self):
        camera = Camera2D(screen_width=200, screen_height=100)
        layer, draw_function, _group = _add_layer(camera=camera, scroll_factor=0.0)

        camera.snap_to(target_x=100.0, target_y=0.0)
        camera.snap_to(target_x=300.0, target_y=0.0)

        assert draw_function.calls == [(0.0, 0.0)]
        assert layer.dirty == 1

    def test_animated_scrolling_layer_redraws_every_frame_on_a_still_camera(self):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        layer, draw_function, _group = _add_layer(camera=camera, scroll_factor=0.5, animated=True)
        assert layer.animated is True

        camera.snap_to(target_x=100.0, target_y=0.0)
        camera.update(target_x=100.0, target_y=0.0, dt=1.0 / 60.0)
        camera.begin_frame()
        camera.advance_shake(dt=1.0 / 60.0)  # the engine's still-camera step: no aim, no shake

        assert draw_function.calls == [(50.0, 0.0)] * 3

    def test_animated_static_layer_redraws_every_frame(self):
        camera = Camera2D(screen_width=200, screen_height=100)
        layer, draw_function, _group = _add_layer(camera=camera, scroll_factor=0.0, animated=True)

        camera.snap_to(target_x=100.0, target_y=0.0)
        camera.advance_shake(dt=1.0 / 60.0)

        assert draw_function.calls == [(0.0, 0.0)] * 3
        assert layer.dirty == 2

    def test_still_frame_keeps_the_previous_frames_pixels(self):
        """Without a redraw the layer shows exactly what it drew last frame."""
        camera = Camera2D(screen_width=200, screen_height=100)
        _layer, draw_function, group = _add_layer(camera=camera, scroll_factor=0.5)
        camera.snap_to(target_x=100.0, target_y=20.0)
        first_frame_pixels = _rendered_pixels(group)

        draw_function.color = (40, 200, 40)  # a redraw now would draw green
        camera.snap_to(target_x=100.0, target_y=20.0)

        assert _rendered_pixels(group) == first_frame_pixels
        camera.snap_to(target_x=101.0, target_y=20.0)
        assert _rendered_pixels(group) != first_frame_pixels

    def test_animated_layer_shows_the_new_state_on_a_still_camera(self):
        camera = Camera2D(screen_width=200, screen_height=100)
        _layer, draw_function, group = _add_layer(camera=camera, scroll_factor=0.5, animated=True)
        camera.snap_to(target_x=100.0, target_y=20.0)
        first_frame_pixels = _rendered_pixels(group)

        draw_function.color = (40, 200, 40)
        camera.snap_to(target_x=100.0, target_y=20.0)

        assert _rendered_pixels(group) != first_frame_pixels


def _bounce(strength=10.0):
    return Shake(
        style=ShakeStyle.BOUNCE,
        strength=strength,
        duration=1.0,
        frequency=2.0,
        axis=ShakeAxis.VERTICAL,
    )


class TestCamera2DShake:
    """Screen shake applied to world sprites and parallax layers."""

    def test_apply_includes_shake_offset(self):
        camera = Camera2D(screen_width=200, screen_height=100)
        camera.shake_effect.add(_bounce())
        assert camera.apply(50.0, 50.0) == (50, 40)

    def test_world_to_screen_matches_apply_when_scrolled_and_shaken(self):
        camera = Camera2D(screen_width=200, screen_height=100)
        camera.world_x = 30.0
        camera.world_y = 5.0
        camera.shake_effect.add(_bounce())
        expected = camera.apply(50.0, 50.0)
        assert camera.world_to_screen(50.0, 50.0) == expected

    def test_update_advances_shake(self):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        camera.shake_effect.add(_bounce())
        camera.update(target_x=0.0, target_y=0.0, dt=1.0)
        assert not camera.shake_effect.is_active

    def test_world_position_is_unshaken(self):
        """Collision and visibility use world_x/world_y, which shake never changes."""
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        camera.shake_effect.add(_bounce())
        camera.update(target_x=30.0, target_y=0.0, dt=1.0 / 60.0)
        assert camera.world_x == pytest.approx(30.0, abs=0.1)

    def test_shake_intensity_zero_disables(self):
        camera = Camera2D(screen_width=200, screen_height=100, shake_intensity=0.0)
        camera.shake_effect.add(_bounce())
        assert camera.apply(50.0, 50.0) == (50, 50)

    def test_parallax_receives_shaken_position(self, mocker):
        camera = Camera2D(screen_width=200, screen_height=100, smooth_factor=1.0)
        update_scroll = TestCamera2DParallax._add_recording_layer(camera, mocker)
        camera.shake_effect.add(_bounce())
        camera.update(target_x=0.0, target_y=0.0, dt=0.0)
        update_scroll.assert_called_once_with(pytest.approx(0.0), pytest.approx(10.0))

    def test_snap_to_ignores_shake(self, mocker):
        camera = Camera2D(screen_width=200, screen_height=100)
        update_scroll = TestCamera2DParallax._add_recording_layer(camera, mocker)
        camera.shake_effect.add(_bounce())
        camera.snap_to(target_x=0.0, target_y=0.0)
        update_scroll.assert_called_once_with(0.0, 0.0)
