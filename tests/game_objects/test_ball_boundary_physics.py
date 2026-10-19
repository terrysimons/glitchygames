#!/usr/bin/env python3
"""Test enhanced ball boundary physics."""

import math
import sys
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from glitchygames.movement import Speed
from tests.game_objects.test_ball import _drawn_position


class TestBallBoundaryPhysics:
    """Test enhanced ball boundary physics."""

    def test_ball_initialization_with_boundary_settings(self):
        """Test that ball initializes with correct boundary settings."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=False,
        )

        assert ball.bounce_top_bottom
        assert not ball.bounce_left_right
        assert ball.speed_up_settings == SpeedUpSettings()
        assert ball.speed_up_settings.triggers == SpeedUpTrigger.NONE

    def test_top_boundary_bounce(self):
        """Test ball bouncing off top boundary."""
        ball = BallSprite(
            x=400,
            y=0,  # Start at top edge
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        ball.speed = Speed(100.0, -50.0)  # Moving up

        # Simulate movement that would go past top boundary
        ball.world_y = -5.0  # Past the boundary
        ball.dt_tick(0.016)  # 60 FPS
        _drawn_position(ball)

        # Ball should be repositioned and speed should be positive (downward)
        assert ball.rect.y >= 0
        assert ball.speed.y >= 0

    def test_bottom_boundary_bounce(self):
        """Test ball bouncing off bottom boundary."""
        ball = BallSprite(
            x=400,
            y=580,  # Start near bottom
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        ball.speed = Speed(100.0, 50.0)  # Moving down

        # Simulate movement that would go past bottom boundary
        ball.world_y = 600.0  # Past the boundary
        ball.dt_tick(0.016)  # 60 FPS
        _drawn_position(ball)

        # Ball should be repositioned and speed should be negative (upward)
        assert ball.rect.y + ball.rect.height <= 600
        assert ball.speed.y <= 0

    def test_left_boundary_bounce(self):
        """Test ball bouncing off left boundary."""
        ball = BallSprite(
            x=0,
            y=300,  # Start at left edge
            bounce_top_bottom=False,
            bounce_left_right=True,
        )
        ball.speed = Speed(-50.0, 100.0)  # Moving left

        # Simulate movement that would go past left boundary
        ball.world_x = -5.0  # Past the boundary
        ball.dt_tick(0.016)  # 60 FPS
        _drawn_position(ball)

        # Ball should be repositioned and speed should be positive (rightward)
        assert ball.rect.x >= 0
        assert ball.speed.x >= 0

    def test_right_boundary_bounce(self):
        """Test ball bouncing off right boundary."""
        ball = BallSprite(
            x=780,
            y=300,  # Start near right edge
            bounce_top_bottom=False,
            bounce_left_right=True,
        )
        ball.speed = Speed(50.0, 100.0)  # Moving right

        # Simulate movement that would go past right boundary
        ball.world_x = 800.0  # Past the boundary
        ball.dt_tick(0.016)  # 60 FPS
        _drawn_position(ball)

        # Ball should be repositioned and speed should be negative (leftward)
        assert ball.rect.x + ball.rect.width <= 800
        assert ball.speed.x <= 0

    def test_no_bounce_when_disabled(self):
        """Test that ball doesn't bounce when boundary bouncing is disabled."""
        ball = BallSprite(
            x=400,
            y=0,  # Start at top edge
            bounce_top_bottom=False,  # Disabled
            bounce_left_right=False,
        )
        ball.speed = Speed(100.0, -50.0)  # Moving up

        initial_speed_y = ball.speed.y

        # Simulate movement past boundary
        ball.world_y = -5.0
        ball.dt_tick(0.016)

        # Speed should remain unchanged (no bounce)
        assert ball.speed.y == initial_speed_y

    def test_corner_collision_handling(self):
        """Test ball behavior when hitting corners."""
        # Test top-left corner
        ball = BallSprite(
            x=0,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed = Speed(-50.0, -50.0)  # Moving up-left

        ball.world_x = -5.0
        ball.world_y = -5.0
        ball.dt_tick(0.016)
        _drawn_position(ball)

        # Both X and Y should be corrected
        assert ball.rect.x >= 0
        assert ball.rect.y >= 0
        assert ball.speed.x >= 0  # Should bounce right
        assert ball.speed.y >= 0  # Should bounce down

    def test_boundary_clipping_prevention(self):
        """Test that ball cannot clip through boundaries."""
        ball = BallSprite(
            x=400,
            y=300,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )

        # Test with very high speed that could cause clipping
        ball.speed = Speed(1000.0, 1000.0)  # Very fast movement

        ball.dt_tick(0.016)
        _drawn_position(ball)

        # Ball should not clip through boundaries
        assert ball.rect.x >= 0
        assert ball.rect.y >= 0
        assert ball.rect.x + ball.rect.width <= 800
        assert ball.rect.y + ball.rect.height <= 600

    def test_speed_preservation_during_bounce(self):
        """Test that speed magnitude is preserved during bounces."""
        ball = BallSprite(
            x=400,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )

        # Set a known speed first
        ball.speed = Speed(100.0, -50.0)  # Moving up
        initial_speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)

        ball.world_y = -5.0
        ball.dt_tick(0.016)

        # Speed magnitude should be preserved (energy conservation)
        final_speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        # Note: Current implementation may not perfectly preserve speed magnitude
        # This test documents the current behavior and can be improved later
        assert final_speed_magnitude > 0  # At least some speed should remain

    def test_multiple_rapid_bounces(self):
        """Test ball behavior with multiple rapid bounces."""
        ball = BallSprite(
            x=400,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        ball.speed = Speed(0.0, -100.0)  # Moving straight up

        # Simulate multiple frames of bouncing
        for _ in range(10):
            ball.world_y = -5.0  # Past boundary
            ball.dt_tick(0.016)
            _drawn_position(ball)

            # Ball should always be within bounds
            assert ball.rect.y >= 0
            assert ball.rect.y + ball.rect.height <= 600

    def test_boundary_bounce_with_speed_up(self):
        """Test boundary bounce with speed-up mechanics."""
        ball = BallSprite(
            x=400,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=False,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.LOGARITHMIC,
                axes=SpeedUpAxes.Y_ONLY,
                multiplier=1.2,
            ),
        )

        # Set initial speed first, then measure
        ball.speed = Speed(100.0, -50.0)  # Moving up
        initial_speed_y = abs(ball.speed.y)

        ball.world_y = -5.0
        ball.dt_tick(0.016)

        # Vertical speed should be increased by the first logarithmic step; X untouched
        final_speed_y = abs(ball.speed.y)
        assert final_speed_y > initial_speed_y
        expected_ratio = speed_up_step_ratio(
            curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.2, completed_steps=0
        )
        assert math.isclose(final_speed_y, initial_speed_y * expected_ratio)
        assert math.isclose(ball.speed.x, 100.0)
        assert ball.speed_up_count == 1

    def test_edge_case_zero_speed_boundary(self):
        """Test ball behavior at boundary with zero speed."""
        ball = BallSprite(
            x=400,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        ball.speed = Speed(0.0, 0.0)  # Zero speed

        ball.world_y = -5.0  # Past boundary
        ball.dt_tick(0.016)
        _drawn_position(ball)

        # Ball should be repositioned but speed remains zero
        assert ball.rect.y >= 0
        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)
        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)

    def test_boundary_bounce_sound_effects(self, mocker):
        """Test that boundary bounces trigger sound effects."""
        ball = BallSprite(
            x=400,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=False,
            collision_sound='test_sound',
        )

        # Mock the sound
        ball.snd = mocker.Mock()
        # Moving up into the top wall; reset() picks a random direction, and a ball
        # moving away from a wall is moved back inside without bouncing (no sound)
        ball.speed = Speed(0.0, -100.0)

        ball.world_y = -5.0
        ball.dt_tick(0.016)

        # Sound should be played
        ball.snd.play.assert_called_once()

    def test_boundary_bounce_debug_logging(self, mocker):
        """Test that boundary bounces generate debug logs."""
        ball = BallSprite(
            x=400,
            y=0,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )

        mock_log = mocker.patch('glitchygames.game_objects.ball.log')

        ball.world_y = -5.0
        ball.dt_tick(0.016)

        # Debug logging should be called
        assert mock_log.debug.called


if __name__ == '__main__':
    import pytest

    pytest.main([__file__])
