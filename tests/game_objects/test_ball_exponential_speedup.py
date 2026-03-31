#!/usr/bin/env python3
"""Tests for exponential speed-up modes in BallSprite."""

import math

import pytest

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from tests.mocks.test_mock_factory import MockFactory


class TestBallExponentialSpeedUp:
    """Test exponential speed-up functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_exponential_x_speed_up(self):
        """Test exponential X speed-up scales both components equally."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1,
        )

        # Set initial speed
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Apply exponential speed-up
        ball.speed_up(speed_up_type='exponential_x')

        # Both components scaled by same effective_multiplier (exponent from X magnitude)
        # exponent = min(abs(100.0) / 100.0, 2.0) = 1.0
        # effective_multiplier = 1.2 ** 1.0 = 1.2
        expected_multiplier = 1.2 ** (100.0 / 100.0)
        assert ball.speed.x == pytest.approx(100.0 * expected_multiplier, abs=1e-5)
        assert ball.speed.y == pytest.approx(50.0 * expected_multiplier, abs=1e-5)

    def test_exponential_y_speed_up(self):
        """Test exponential Y speed-up scales both components equally."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.5,
            speed_up_interval=0.1,
        )

        # Set initial speed
        ball.speed.x = 200.0
        ball.speed.y = 150.0

        # Apply exponential speed-up
        ball.speed_up(speed_up_type='exponential_y')

        # Both components scaled by same effective_multiplier (exponent from Y magnitude)
        # exponent = min(abs(150.0) / 100.0, 2.0) = 1.5
        # effective_multiplier = 1.5 ** 1.5 ~= 1.837
        expected_multiplier = 1.5 ** (150.0 / 100.0)
        assert ball.speed.x == pytest.approx(200.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(150.0 * expected_multiplier, abs=0.1)

    def test_exponential_both_speed_up(self):
        """Test exponential both X and Y speed-up uses average exponent."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X
            | SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.3,
            speed_up_interval=0.1,
        )

        # Set initial speed
        ball.speed.x = 80.0
        ball.speed.y = 120.0

        # Apply exponential speed-up
        ball.speed_up(speed_up_type='exponential_both')

        # exponential_both uses average of both exponents, applied uniformly
        x_exponent = min(abs(80.0) / 100.0, 2.0)  # 0.8
        y_exponent = min(abs(120.0) / 100.0, 2.0)  # 1.2
        average_exponent = (x_exponent + y_exponent) / 2.0  # 1.0
        effective_multiplier = 1.3**average_exponent
        expected_x = 80.0 * effective_multiplier
        expected_y = 120.0 * effective_multiplier

        assert ball.speed.x == pytest.approx(expected_x, abs=0.1)
        assert ball.speed.y == pytest.approx(expected_y, abs=0.1)

    def test_exponential_speed_up_with_zero_speed(self):
        """Test exponential speed-up with zero X speed component."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1,
        )

        # Set initial speed with zero X component
        ball.speed.x = 0.0
        ball.speed.y = 100.0

        # Apply exponential speed-up
        ball.speed_up(speed_up_type='exponential_x')

        # exponent = min(abs(0.0) / 100.0, 2.0) = 0.0
        # effective_multiplier = 1.2 ** 0.0 = 1.0 (no scaling at all)
        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)  # 0 * 1.0 = 0
        assert math.isclose(ball.speed.y, 100.0)  # 100 * 1.0 = 100

    def test_continuous_exponential_speed_up(self):
        """Test continuous exponential speed-up scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1,
        )

        # Set initial speed
        ball.speed.x = 50.0
        ball.speed.y = 75.0

        # Simulate time passing and trigger continuous speed-up
        current_time = 0.2  # More than speed_up_interval
        ball._last_speed_up_time = 0.0

        ball._check_continuous_speed_up(current_time)

        # Both components scaled by same effective_multiplier (exponent from X magnitude)
        # exponent = min(abs(50.0) / 100.0, 2.0) = 0.5
        # effective_multiplier = 1.1 ** 0.5 ~= 1.0488
        expected_multiplier = 1.1 ** (50.0 / 100.0)
        assert ball.speed.x == pytest.approx(50.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(75.0 * expected_multiplier, abs=0.1)

    def test_paddle_bounce_exponential_speed_up(self):
        """Test paddle bounce exponential speed-up scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X,
            speed_up_multiplier=1.4,
            speed_up_interval=1.0,
        )

        # Set initial speed
        ball.speed.x = 200.0
        ball.speed.y = 100.0

        # Trigger paddle bounce speed-up
        ball._check_bounce_speed_up('paddle')

        # Both components scaled by same effective_multiplier (exponent from X magnitude)
        # exponent = min(abs(200.0) / 100.0, 2.0) = 2.0 (capped)
        # effective_multiplier = 1.4 ** 2.0 = 1.96
        expected_multiplier = 1.4 ** min(200.0 / 100.0, 2.0)
        assert ball.speed.x == pytest.approx(200.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(100.0 * expected_multiplier, abs=0.1)

    def test_wall_bounce_exponential_speed_up(self):
        """Test wall bounce exponential speed-up scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_Y,
            speed_up_multiplier=1.3,
            speed_up_interval=1.0,
        )

        # Set initial speed
        ball.speed.x = 150.0
        ball.speed.y = 80.0

        # Trigger wall bounce speed-up
        ball._check_bounce_speed_up('wall')

        # Both components scaled by same effective_multiplier (exponent from Y magnitude)
        # exponent: min(abs(80.0) / 100.0, 2.0) gives 0.8
        # effective_multiplier: 1.3 raised to 0.8
        expected_multiplier = 1.3 ** (80.0 / 100.0)
        assert ball.speed.x == pytest.approx(150.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(80.0 * expected_multiplier, abs=0.1)

    def test_combined_exponential_modes(self):
        """Test combined exponential X and Y modes uses exponential_both."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X
            | SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1,
        )

        # Set initial speed
        ball.speed.x = 100.0
        ball.speed.y = 200.0

        # Simulate time passing and trigger continuous speed-up
        current_time = 0.2
        ball._last_speed_up_time = 0.0

        ball._check_continuous_speed_up(current_time)

        # When both X and Y exponential flags are set, exponential_both is used
        # which uses average of both exponents, applied uniformly
        x_exponent = min(abs(100.0) / 100.0, 2.0)  # 1.0
        y_exponent = min(abs(200.0) / 100.0, 2.0)  # 2.0 (capped)
        average_exponent = (x_exponent + y_exponent) / 2.0  # 1.5
        expected_multiplier = 1.2**average_exponent

        assert ball.speed.x == pytest.approx(100.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(200.0 * expected_multiplier, abs=0.1)

    def test_exponential_speed_up_priority(self):
        """Test that exponential speed-up has higher priority than logarithmic."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X
            | SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1,
        )

        # Set initial speed
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Simulate time passing and trigger continuous speed-up
        current_time = 0.2
        ball._last_speed_up_time = 0.0

        ball._check_continuous_speed_up(current_time)

        # Should use exponential_x (higher priority), which scales BOTH components
        # exponent = min(abs(100.0) / 100.0, 2.0) = 1.0
        # effective_multiplier = 1.2 ** 1.0 = 1.2
        expected_multiplier = 1.2 ** (100.0 / 100.0)
        assert ball.speed.x == pytest.approx(100.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(50.0 * expected_multiplier, abs=0.1)

    def test_exponential_speed_up_extreme_values(self):
        """Test exponential speed-up with extreme speed values scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1,
        )

        # Set very high initial speed
        ball.speed.x = 1000.0
        ball.speed.y = 500.0

        # Apply exponential speed-up
        ball.speed_up(speed_up_type='exponential_x')

        # Both components scaled by same effective_multiplier
        # exponent = min(abs(1000.0) / 100.0, 2.0) = 2.0 (capped)
        # effective_multiplier = 1.1 ** 2.0 = 1.21
        expected_multiplier = 1.1**2.0
        assert ball.speed.x == pytest.approx(1000.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(500.0 * expected_multiplier, abs=0.1)

    def test_exponential_speed_up_negative_speed(self):
        """Test exponential speed-up with negative speed values scales both components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1,
        )

        # Set negative initial speed
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        # Apply exponential speed-up
        ball.speed_up(speed_up_type='exponential_x')

        # Both components scaled by same effective_multiplier (exponent from abs(X))
        # exponent = min(abs(-100.0) / 100.0, 2.0) = 1.0
        # effective_multiplier = 1.2 ** 1.0 = 1.2
        expected_multiplier = 1.2 ** (100.0 / 100.0)
        assert ball.speed.x == pytest.approx(-100.0 * expected_multiplier, abs=0.1)
        assert ball.speed.y == pytest.approx(50.0 * expected_multiplier, abs=0.1)
