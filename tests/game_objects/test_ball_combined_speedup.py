#!/usr/bin/env python3
"""Test combined speed-up modes for BallSprite."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory


class TestBallCombinedSpeedUp:
    """Test BallSprite combined speed-up modes."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        # Mock screen dimensions for consistent testing
        self.screen_width = 800
        self.screen_height = 600

    def test_combined_linear_and_logarithmic_x(self):
        """Test combining linear and logarithmic X speed-up modes."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.05,  # Short interval for testing
        )

        ball.speed = Speed(100.0, 200.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Test continuous linear speed-up
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)

        # Should preserve direction (linear)
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction)

        # Test paddle bounce logarithmic X speed-up
        # logarithmic_x now scales BOTH components equally (preserves direction)
        pre_bounce_x = ball.speed.x
        pre_bounce_y = ball.speed.y
        ball.on_paddle_bounce()

        # Both components should be scaled by the multiplier (direction preserved)
        assert ball.speed.x == pytest.approx(pre_bounce_x * 1.2)
        assert ball.speed.y == pytest.approx(pre_bounce_y * 1.2)

    def test_combined_linear_and_logarithmic_y(self):
        """Test combining linear and logarithmic Y speed-up modes."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.15,
            speed_up_interval=0.05,  # Short interval for testing
        )

        ball.speed = Speed(150.0, 100.0)

        # Test continuous linear speed-up
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)

        # Record speeds after linear speed-up
        pre_bounce_x = ball.speed.x
        pre_bounce_y = ball.speed.y

        # Test paddle bounce logarithmic Y speed-up
        # logarithmic_y now scales BOTH components equally (preserves direction)
        ball.on_paddle_bounce()

        # Both components should be scaled by the multiplier (direction preserved)
        assert ball.speed.x == pytest.approx(pre_bounce_x * 1.15)
        assert ball.speed.y == pytest.approx(pre_bounce_y * 1.15)

    def test_combined_logarithmic_x_and_y(self):
        """Test combining logarithmic X and Y speed-up modes."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
            | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.25,
        )

        ball.speed = Speed(200.0, 150.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Test paddle bounce (logarithmic_x now scales BOTH components equally)
        ball.on_paddle_bounce()

        # Both components should be scaled equally (direction preserved)
        assert ball.speed.x == pytest.approx(initial_x * 1.25)
        assert ball.speed.y == pytest.approx(initial_y * 1.25)

        # Record speeds after paddle bounce for wall bounce comparison
        after_paddle_x = ball.speed.x
        after_paddle_y = ball.speed.y

        # Test wall bounce (logarithmic_y now scales BOTH components equally)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0  # Sub-pixel position must also be set
        ball._do_bounce()

        # Both components should be scaled by multiplier, Y should be reversed
        assert ball.speed.x == pytest.approx(after_paddle_x * 1.25)
        assert ball.speed.y == pytest.approx(abs(after_paddle_y) * 1.25)

    def test_all_linear_modes(self):
        """Test all linear speed-up modes combined."""
        ball = BallSprite(speed_up_mode=SpeedUpMode.ALL_LINEAR, speed_up_multiplier=1.1)

        ball.speed = Speed(100.0, 200.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Test continuous linear
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)

        # Test paddle bounce linear
        ball.on_paddle_bounce()

        # Test wall bounce linear (must set world_y for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0
        ball._do_bounce()

        # Direction should be preserved throughout (all linear)
        final_direction = math.atan2(ball.speed.y, ball.speed.x)
        # Note: wall bounce reverses Y, so we check if direction is preserved or reversed
        expected_direction = initial_direction if ball.speed.y > 0 else -initial_direction
        assert final_direction == pytest.approx(expected_direction)

    def test_all_logarithmic_x_modes(self):
        """Test all logarithmic X speed-up modes combined."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ALL_LOGARITHMIC_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.05,  # Short interval for testing
        )

        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Test continuous logarithmic X (now scales BOTH components equally)
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)

        # Both should be scaled equally (direction preserved)
        assert ball.speed.x == pytest.approx(initial_x * 1.2)
        assert ball.speed.y == pytest.approx(initial_y * 1.2)

        # Test paddle bounce logarithmic X (again scales BOTH)
        ball.on_paddle_bounce()

        # Both should be scaled again
        assert ball.speed.x == pytest.approx(initial_x * 1.2 * 1.2)
        assert ball.speed.y == pytest.approx(initial_y * 1.2 * 1.2)

    def test_all_logarithmic_y_modes(self):
        """Test all logarithmic Y speed-up modes combined."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ALL_LOGARITHMIC_Y,
            speed_up_multiplier=1.3,
            speed_up_interval=0.05,  # Short interval for testing
        )

        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Test continuous logarithmic Y (now scales BOTH components equally)
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)

        # Both should be scaled equally (direction preserved)
        assert ball.speed.x == pytest.approx(initial_x * 1.3)
        assert ball.speed.y == pytest.approx(initial_y * 1.3)

        # Test wall bounce logarithmic Y (again scales BOTH)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0  # Sub-pixel position must also be set
        ball._do_bounce()

        # Y should be reversed, both scaled again by multiplier
        assert ball.speed.x == pytest.approx(initial_x * 1.3 * 1.3)
        assert ball.speed.y == pytest.approx(abs(initial_y) * 1.3 * 1.3)

    def test_mixed_linear_and_logarithmic_modes(self):
        """Test mixed linear and logarithmic modes for different bounce types."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LINEAR | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.15,
        )

        ball.speed = Speed(150.0, 100.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Test paddle bounce (linear - scales both equally)
        ball.on_paddle_bounce()

        # Should preserve direction
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction)

        # Record after linear
        after_linear_x = ball.speed.x
        after_linear_y = ball.speed.y

        # Test wall bounce (logarithmic_x now scales BOTH components equally)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0  # Sub-pixel position must also be set
        ball._do_bounce()

        # Both components should be scaled, Y should be reversed
        assert ball.speed.x == pytest.approx(after_linear_x * 1.15)
        assert ball.speed.y == pytest.approx(abs(after_linear_y) * 1.15)

    def test_priority_handling(self):
        """Test that speed-up modes are handled with correct priority."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR | SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.1,
        )

        ball.speed = Speed(100.0, 200.0)
        ball._last_speed_up_time = 0.0

        # Should trigger linear (first in priority order)
        ball._check_continuous_speed_up(0.1)

        # Should preserve direction (linear was applied)
        initial_direction = math.atan2(200.0, 100.0)
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction)

    def test_combined_modes_with_bouncing(self):
        """Test combined modes with actual bouncing behavior."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
            | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.2,
        )

        ball.speed = Speed(100.0, 150.0)

        # Simulate paddle hit (logarithmic_x now scales BOTH components equally)
        ball.on_paddle_bounce()
        assert ball.speed.x == pytest.approx(100.0 * 1.2)
        assert ball.speed.y == pytest.approx(150.0 * 1.2)

        # Record after paddle bounce
        after_paddle_x = ball.speed.x
        after_paddle_y = ball.speed.y

        # Simulate wall hit (logarithmic_y now scales BOTH components equally)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0  # Sub-pixel position must also be set
        ball._do_bounce()
        assert ball.speed.x == pytest.approx(after_paddle_x * 1.2)  # Scaled
        assert ball.speed.y == pytest.approx(abs(after_paddle_y) * 1.2)  # Reversed and scaled

    def test_edge_case_zero_speeds(self):
        """Test combined modes with zero speed components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.5,
        )

        # When both X and Y logarithmic flags are set, logarithmic_both is used
        # (scales both components equally, preserving direction)

        # Test with zero X -- both components scale, zero stays zero
        ball.speed = Speed(0.0, 100.0)
        ball.on_paddle_bounce()
        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)  # Zero * anything = zero
        assert ball.speed.y == pytest.approx(100.0 * 1.5)  # Y should scale

        # Test with zero Y -- both components scale, zero stays zero
        ball.speed = Speed(100.0, 0.0)
        ball.on_paddle_bounce()
        assert ball.speed.x == pytest.approx(100.0 * 1.5)  # X should scale
        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)  # Zero * anything = zero
