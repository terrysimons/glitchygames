#!/usr/bin/env python3
"""Tests for exponential speed-up modes in BallSprite."""

import math
import unittest
from unittest.mock import Mock, patch

from tests.mocks.test_mock_factory import MockFactory
from glitchygames.game_objects.ball import BallSprite, SpeedUpMode


class TestBallExponentialSpeedUp(unittest.TestCase):
    """Test exponential speed-up functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_exponential_x_speed_up(self):
        """Test exponential X speed-up."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed.x = 100.0
        ball.speed.y = 50.0
        
        # Apply exponential speed-up
        ball.speed_up(speed_up_type="exponential_x")
        
        # X speed should be exponentially increased
        expected_x = 100.0 * (1.2 ** (100.0 / 100.0))  # 100 * 1.2^1 = 120
        self.assertAlmostEqual(ball.speed.x, expected_x, places=5)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 50.0)

    def test_exponential_y_speed_up(self):
        """Test exponential Y speed-up."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.5,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed.x = 200.0
        ball.speed.y = 150.0
        
        # Apply exponential speed-up
        ball.speed_up(speed_up_type="exponential_y")
        
        # X speed should remain unchanged
        self.assertEqual(ball.speed.x, 200.0)
        # Y speed should be exponentially increased
        expected_y = 150.0 * (1.5 ** (150.0 / 100.0))  # 150 * 1.5^1.5 ≈ 275.6
        self.assertAlmostEqual(ball.speed.y, expected_y, places=1)

    def test_exponential_both_speed_up(self):
        """Test exponential both X and Y speed-up."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X | SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.3,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed.x = 80.0
        ball.speed.y = 120.0
        
        # Apply exponential speed-up
        ball.speed_up(speed_up_type="exponential_both")
        
        # Both speeds should be exponentially increased
        expected_x = 80.0 * (1.3 ** (80.0 / 100.0))  # 80 * 1.3^0.8 ≈ 100.4
        expected_y = 120.0 * (1.3 ** (120.0 / 100.0))  # 120 * 1.3^1.2 ≈ 156.0
        
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        self.assertAlmostEqual(ball.speed.y, expected_y, places=1)

    def test_exponential_speed_up_with_zero_speed(self):
        """Test exponential speed-up with zero speed components."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1
        )
        
        # Set initial speed with zero X component
        ball.speed.x = 0.0
        ball.speed.y = 100.0
        
        # Apply exponential speed-up
        ball.speed_up(speed_up_type="exponential_x")
        
        # X speed should remain zero (no change for zero speed)
        self.assertEqual(ball.speed.x, 0.0)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 100.0)

    def test_continuous_exponential_speed_up(self):
        """Test continuous exponential speed-up."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed.x = 50.0
        ball.speed.y = 75.0
        
        # Simulate time passing and trigger continuous speed-up
        current_time = 0.2  # More than speed_up_interval
        ball._last_speed_up_time = 0.0
        
        ball._check_continuous_speed_up(current_time)
        
        # X speed should be exponentially increased
        expected_x = 50.0 * (1.1 ** (50.0 / 100.0))  # 50 * 1.1^0.5 ≈ 52.4
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 75.0)

    def test_paddle_bounce_exponential_speed_up(self):
        """Test paddle bounce exponential speed-up."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X,
            speed_up_multiplier=1.4,
            speed_up_interval=1.0
        )
        
        # Set initial speed
        ball.speed.x = 200.0
        ball.speed.y = 100.0
        
        # Trigger paddle bounce speed-up
        ball._check_bounce_speed_up("paddle")
        
        # X speed should be exponentially increased
        expected_x = 200.0 * (1.4 ** (200.0 / 100.0))  # 200 * 1.4^2 = 392
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 100.0)

    def test_wall_bounce_exponential_speed_up(self):
        """Test wall bounce exponential speed-up."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_EXPONENTIAL_Y,
            speed_up_multiplier=1.3,
            speed_up_interval=1.0
        )
        
        # Set initial speed
        ball.speed.x = 150.0
        ball.speed.y = 80.0
        
        # Trigger wall bounce speed-up
        ball._check_bounce_speed_up("wall")
        
        # X speed should remain unchanged
        self.assertEqual(ball.speed.x, 150.0)
        # Y speed should be exponentially increased
        expected_y = 80.0 * (1.3 ** (80.0 / 100.0))  # 80 * 1.3^0.8 ≈ 100.4
        self.assertAlmostEqual(ball.speed.y, expected_y, places=1)

    def test_combined_exponential_modes(self):
        """Test combined exponential X and Y modes."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X | SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed.x = 100.0
        ball.speed.y = 200.0
        
        # Simulate time passing and trigger continuous speed-up
        current_time = 0.2
        ball._last_speed_up_time = 0.0
        
        ball._check_continuous_speed_up(current_time)
        
        # Both speeds should be exponentially increased
        expected_x = 100.0 * (1.2 ** (100.0 / 100.0))  # 100 * 1.2^1 = 120
        expected_y = 200.0 * (1.2 ** (200.0 / 100.0))  # 200 * 1.2^2 = 288
        
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        self.assertAlmostEqual(ball.speed.y, expected_y, places=1)

    def test_exponential_speed_up_priority(self):
        """Test that exponential speed-up has higher priority than logarithmic."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X | SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed.x = 100.0
        ball.speed.y = 50.0
        
        # Simulate time passing and trigger continuous speed-up
        current_time = 0.2
        ball._last_speed_up_time = 0.0
        
        ball._check_continuous_speed_up(current_time)
        
        # Should use exponential (higher priority), not logarithmic
        expected_x = 100.0 * (1.2 ** (100.0 / 100.0))  # 100 * 1.2^1 = 120
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 50.0)

    def test_exponential_speed_up_extreme_values(self):
        """Test exponential speed-up with extreme speed values."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1
        )
        
        # Set very high initial speed
        ball.speed.x = 1000.0
        ball.speed.y = 500.0
        
        # Apply exponential speed-up
        ball.speed_up(speed_up_type="exponential_x")
        
        # X speed should be exponentially increased (very large)
        expected_x = 1000.0 * (1.1 ** (1000.0 / 100.0))  # 1000 * 1.1^10 ≈ 2593.7
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 500.0)

    def test_exponential_speed_up_negative_speed(self):
        """Test exponential speed-up with negative speed values."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.2,
            speed_up_interval=0.1
        )
        
        # Set negative initial speed
        ball.speed.x = -100.0
        ball.speed.y = 50.0
        
        # Apply exponential speed-up
        ball.speed_up(speed_up_type="exponential_x")
        
        # X speed should be exponentially increased (using absolute value)
        expected_x = -100.0 * (1.2 ** (100.0 / 100.0))  # -100 * 1.2^1 = -120
        self.assertAlmostEqual(ball.speed.x, expected_x, places=1)
        # Y speed should remain unchanged
        self.assertEqual(ball.speed.y, 50.0)


if __name__ == "__main__":
    unittest.main()
