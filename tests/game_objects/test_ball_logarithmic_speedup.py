#!/usr/bin/env python3
"""Test logarithmic speed-up behavior for BallSprite."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory


class TestBallLogarithmicSpeedUp:
    """Test BallSprite logarithmic speed-up behavior."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        # Mock screen dimensions for consistent testing
        self.screen_width = 800
        self.screen_height = 600

    def test_logarithmic_x_speed_up(self):
        """Test logarithmic X speed-up now scales both components equally."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Apply logarithmic X speed-up (now scales BOTH components to preserve direction)
        ball.speed_up(multiplier=1.2, speed_up_type='logarithmic_x')

        # Both should increase by the same multiplier
        assert ball.speed.x == pytest.approx(initial_x * 1.2)
        assert ball.speed.y == pytest.approx(initial_y * 1.2)

    def test_logarithmic_y_speed_up(self):
        """Test logarithmic Y speed-up now scales both components equally."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Apply logarithmic Y speed-up (now scales BOTH components to preserve direction)
        ball.speed_up(multiplier=1.3, speed_up_type='logarithmic_y')

        # Both should increase by the same multiplier
        assert ball.speed.x == pytest.approx(initial_x * 1.3)
        assert ball.speed.y == pytest.approx(initial_y * 1.3)

    def test_logarithmic_both_speed_up(self):
        """Test logarithmic both X and Y speed-up."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Apply logarithmic both speed-up
        ball.speed_up(multiplier=1.15, speed_up_type='logarithmic_both')

        # Both should increase
        assert ball.speed.x == pytest.approx(initial_x * 1.15)
        assert ball.speed.y == pytest.approx(initial_y * 1.15)

    def test_logarithmic_x_speed_up_with_wall_bounce(self):
        """Test logarithmic X speed-up with wall bouncing scales both components."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.25,
        )

        ball.speed = Speed(150.0, 100.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Simulate wall bounce (must set world_y for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0
        ball._do_bounce()

        # Both components scaled by multiplier, Y reversed by bounce
        assert ball.speed.x == pytest.approx(initial_x * 1.25)
        assert ball.speed.y == pytest.approx(abs(initial_y) * 1.25)

    def test_logarithmic_y_speed_up_with_wall_bounce(self):
        """Test logarithmic Y speed-up with wall bouncing scales both components."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.3,
        )

        ball.speed = Speed(150.0, 100.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Simulate wall bounce (must set world_y for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0
        ball._do_bounce()

        # Both components scaled by multiplier, Y reversed by bounce
        assert ball.speed.x == pytest.approx(initial_x * 1.3)
        assert ball.speed.y == pytest.approx(abs(initial_y) * 1.3)

    def test_logarithmic_both_speed_up_with_wall_bounce(self):
        """Test logarithmic both speed-up with wall bouncing."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X
            | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.2,
        )

        ball.speed = Speed(150.0, 100.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Simulate wall bounce (must set world_y for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0
        ball._do_bounce()

        # Both should be affected (logarithmic_both scales both equally)
        assert ball.speed.x == pytest.approx(initial_x * 1.2)
        assert ball.speed.y == pytest.approx(abs(initial_y) * 1.2)

    def test_logarithmic_x_speed_up_with_paddle_bounce(self):
        """Test logarithmic X speed-up with paddle bouncing scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.4,
        )

        ball.speed = Speed(200.0, 150.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Simulate paddle bounce (logarithmic_x now scales BOTH components equally)
        ball.on_paddle_bounce()

        # Both should increase by the same multiplier (direction preserved)
        assert ball.speed.x == pytest.approx(initial_x * 1.4)
        assert ball.speed.y == pytest.approx(initial_y * 1.4)

    def test_logarithmic_y_speed_up_with_paddle_bounce(self):
        """Test logarithmic Y speed-up with paddle bouncing scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.35,
        )

        ball.speed = Speed(200.0, 150.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Simulate paddle bounce (logarithmic_y now scales BOTH components equally)
        ball.on_paddle_bounce()

        # Both should increase by the same multiplier (direction preserved)
        assert ball.speed.x == pytest.approx(initial_x * 1.35)
        assert ball.speed.y == pytest.approx(initial_y * 1.35)

    def test_logarithmic_continuous_speed_up(self):
        """Test continuous logarithmic speed-up scales both components."""
        # Test X continuous (now scales BOTH components equally)
        ball_x = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1,
        )
        ball_x.speed = Speed(100.0, 200.0)
        ball_x._last_speed_up_time = 0.0
        ball_x._check_continuous_speed_up(0.1)

        assert ball_x.speed.x == pytest.approx(100.0 * 1.1)
        assert ball_x.speed.y == pytest.approx(200.0 * 1.1)

        # Test Y continuous (now scales BOTH components equally)
        ball_y = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y,
            speed_up_multiplier=1.15,
            speed_up_interval=0.1,
        )
        ball_y.speed = Speed(100.0, 200.0)
        ball_y._last_speed_up_time = 0.0
        ball_y._check_continuous_speed_up(0.1)

        assert ball_y.speed.x == pytest.approx(100.0 * 1.15)
        assert ball_y.speed.y == pytest.approx(200.0 * 1.15)

    def test_logarithmic_speed_up_preserves_direction(self):
        """Test that logarithmic speed-up now preserves direction."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply logarithmic X speed-up (now scales both components equally)
        ball.speed_up(multiplier=1.5, speed_up_type='logarithmic_x')

        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        # Direction should be preserved (both components scaled equally)
        assert initial_direction == pytest.approx(new_direction, abs=1e-12)

    def test_logarithmic_speed_up_multiple_applications(self):
        """Test that multiple logarithmic speed-ups compound correctly on both components."""
        ball = BallSprite()
        ball.speed = Speed(50.0, 50.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        # Apply X speed-up multiple times (now scales BOTH components each time)
        for i in range(3):
            ball.speed_up(multiplier=1.2, speed_up_type='logarithmic_x')

        # Both components should compound equally
        expected_x = initial_x * (1.2**3)
        expected_y = initial_y * (1.2**3)
        assert ball.speed.x == pytest.approx(expected_x)
        assert ball.speed.y == pytest.approx(expected_y)

    def test_logarithmic_speed_up_with_negative_speeds(self):
        """Test logarithmic speed-up with negative speeds scales both components."""
        ball = BallSprite()
        ball.speed = Speed(-100.0, -200.0)

        # Apply logarithmic X speed-up (now scales BOTH components equally)
        ball.speed_up(multiplier=1.3, speed_up_type='logarithmic_x')

        # Both should become more negative
        assert ball.speed.x == pytest.approx(-100.0 * 1.3)
        assert ball.speed.y == pytest.approx(-200.0 * 1.3)

    def test_logarithmic_speed_up_with_zero_component(self):
        """Test logarithmic speed-up with zero speed component scales both."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 0.0)

        # Apply logarithmic Y speed-up (now scales BOTH components equally)
        ball.speed_up(multiplier=1.5, speed_up_type='logarithmic_y')

        # Y stays zero (0 * 1.5 = 0), X is scaled
        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)
        assert ball.speed.x == pytest.approx(100.0 * 1.5)

    def test_logarithmic_speed_up_precision(self):
        """Test logarithmic speed-up precision with various multipliers scales both."""
        ball = BallSprite()

        multipliers = [1.01, 1.05, 1.1, 1.15, 1.2, 1.5, 2.0]

        for multiplier in multipliers:
            ball.speed = Speed(100.0, 200.0)
            initial_x = ball.speed.x
            initial_y = ball.speed.y

            # Apply logarithmic X speed-up (now scales BOTH components equally)
            ball.speed_up(multiplier=multiplier, speed_up_type='logarithmic_x')

            # Check precision -- both components scale equally
            assert ball.speed.x == pytest.approx(initial_x * multiplier)
            assert ball.speed.y == pytest.approx(initial_y * multiplier)
