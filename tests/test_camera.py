"""Tests for Camera2D viewport system."""

import pytest

from glitchygames.camera import Camera2D


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
