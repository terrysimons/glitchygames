"""Tests for Camera2D viewport system."""

import pygame
import pytest

from glitchygames.camera import Camera2D
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
