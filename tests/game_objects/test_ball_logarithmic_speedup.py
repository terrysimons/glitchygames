#!/usr/bin/env python3
"""Test logarithmic speed-up behavior for BallSprite."""

import unittest
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory


class TestBallLogarithmicSpeedUp(unittest.TestCase):
    """Test BallSprite logarithmic speed-up behavior."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()
        # Mock screen dimensions for consistent testing
        self.screen_width = 800
        self.screen_height = 600

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_logarithmic_x_speed_up(self):
        """Test logarithmic X-only speed-up."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Apply logarithmic X speed-up
        ball.speed_up(multiplier=1.2, speed_up_type="logarithmic_x")
        
        # X should increase, Y should remain unchanged
        self.assertAlmostEqual(ball.speed.x, initial_x * 1.2, places=10)
        self.assertAlmostEqual(ball.speed.y, initial_y, places=10)

    def test_logarithmic_y_speed_up(self):
        """Test logarithmic Y-only speed-up."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Apply logarithmic Y speed-up
        ball.speed_up(multiplier=1.3, speed_up_type="logarithmic_y")
        
        # Y should increase, X should remain unchanged
        self.assertAlmostEqual(ball.speed.x, initial_x, places=10)
        self.assertAlmostEqual(ball.speed.y, initial_y * 1.3, places=10)

    def test_logarithmic_both_speed_up(self):
        """Test logarithmic both X and Y speed-up."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Apply logarithmic both speed-up
        ball.speed_up(multiplier=1.15, speed_up_type="logarithmic_both")
        
        # Both should increase
        self.assertAlmostEqual(ball.speed.x, initial_x * 1.15, places=10)
        self.assertAlmostEqual(ball.speed.y, initial_y * 1.15, places=10)

    def test_logarithmic_x_speed_up_with_wall_bounce(self):
        """Test logarithmic X speed-up with wall bouncing."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.25
        )
        
        ball.speed = Speed(150.0, 100.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate wall bounce
        ball.rect.y = 0  # Hit top wall
        ball._do_bounce()
        
        # X should increase, Y should be reversed but not scaled
        self.assertAlmostEqual(ball.speed.x, initial_x * 1.25, places=10)
        self.assertAlmostEqual(ball.speed.y, abs(initial_y), places=10)  # Reversed but not scaled

    def test_logarithmic_y_speed_up_with_wall_bounce(self):
        """Test logarithmic Y speed-up with wall bouncing."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.3
        )
        
        ball.speed = Speed(150.0, 100.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate wall bounce
        ball.rect.y = 0  # Hit top wall
        ball._do_bounce()
        
        # X should remain unchanged, Y should be reversed and scaled
        self.assertAlmostEqual(ball.speed.x, initial_x, places=10)
        self.assertAlmostEqual(ball.speed.y, abs(initial_y) * 1.3, places=10)

    def test_logarithmic_both_speed_up_with_wall_bounce(self):
        """Test logarithmic both speed-up with wall bouncing."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.2
        )
        
        ball.speed = Speed(150.0, 100.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate wall bounce
        ball.rect.y = 0  # Hit top wall
        ball._do_bounce()
        
        # Both should be affected
        self.assertAlmostEqual(ball.speed.x, initial_x * 1.2, places=10)
        self.assertAlmostEqual(ball.speed.y, abs(initial_y) * 1.2, places=10)

    def test_logarithmic_x_speed_up_with_paddle_bounce(self):
        """Test logarithmic X speed-up with paddle bouncing."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.4
        )
        
        ball.speed = Speed(200.0, 150.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate paddle bounce
        ball.on_paddle_bounce()
        
        # X should increase, Y should remain unchanged
        self.assertAlmostEqual(ball.speed.x, initial_x * 1.4, places=10)
        self.assertAlmostEqual(ball.speed.y, initial_y, places=10)

    def test_logarithmic_y_speed_up_with_paddle_bounce(self):
        """Test logarithmic Y speed-up with paddle bouncing."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
            speed_up_multiplier=1.35
        )
        
        ball.speed = Speed(200.0, 150.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate paddle bounce
        ball.on_paddle_bounce()
        
        # Y should increase, X should remain unchanged
        self.assertAlmostEqual(ball.speed.x, initial_x, places=10)
        self.assertAlmostEqual(ball.speed.y, initial_y * 1.35, places=10)

    def test_logarithmic_continuous_speed_up(self):
        """Test continuous logarithmic speed-up over time."""
        # Test X-only continuous
        ball_x = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1
        )
        ball_x.speed = Speed(100.0, 200.0)
        ball_x._last_speed_up_time = 0.0
        ball_x._check_continuous_speed_up(0.1)
        
        self.assertAlmostEqual(ball_x.speed.x, 100.0 * 1.1, places=10)
        self.assertAlmostEqual(ball_x.speed.y, 200.0, places=10)
        
        # Test Y-only continuous
        ball_y = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y,
            speed_up_multiplier=1.15,
            speed_up_interval=0.1
        )
        ball_y.speed = Speed(100.0, 200.0)
        ball_y._last_speed_up_time = 0.0
        ball_y._check_continuous_speed_up(0.1)
        
        self.assertAlmostEqual(ball_y.speed.x, 100.0, places=10)
        self.assertAlmostEqual(ball_y.speed.y, 200.0 * 1.15, places=10)

    def test_logarithmic_speed_up_direction_change(self):
        """Test that logarithmic speed-up can change direction."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply logarithmic X speed-up (changes direction)
        ball.speed_up(multiplier=1.5, speed_up_type="logarithmic_x")
        
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        # Direction should have changed
        self.assertNotAlmostEqual(initial_direction, new_direction, places=5)

    def test_logarithmic_speed_up_multiple_applications(self):
        """Test that multiple logarithmic speed-ups compound correctly."""
        ball = BallSprite()
        ball.speed = Speed(50.0, 50.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Apply X speed-up multiple times
        for i in range(3):
            ball.speed_up(multiplier=1.2, speed_up_type="logarithmic_x")
        
        # Check final X speed
        expected_x = initial_x * (1.2 ** 3)
        self.assertAlmostEqual(ball.speed.x, expected_x, places=10)
        # Y should remain unchanged
        self.assertAlmostEqual(ball.speed.y, initial_y, places=10)

    def test_logarithmic_speed_up_with_negative_speeds(self):
        """Test logarithmic speed-up with negative speeds."""
        ball = BallSprite()
        ball.speed = Speed(-100.0, -200.0)
        
        # Apply logarithmic X speed-up
        ball.speed_up(multiplier=1.3, speed_up_type="logarithmic_x")
        
        # X should become more negative, Y should remain unchanged
        self.assertAlmostEqual(ball.speed.x, -100.0 * 1.3, places=10)
        self.assertAlmostEqual(ball.speed.y, -200.0, places=10)

    def test_logarithmic_speed_up_with_zero_component(self):
        """Test logarithmic speed-up with zero speed components."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 0.0)
        
        # Apply logarithmic Y speed-up (should have no effect)
        ball.speed_up(multiplier=1.5, speed_up_type="logarithmic_y")
        
        # Y should remain zero
        self.assertEqual(ball.speed.y, 0.0)
        self.assertAlmostEqual(ball.speed.x, 100.0, places=10)

    def test_logarithmic_speed_up_precision(self):
        """Test logarithmic speed-up precision with various multipliers."""
        ball = BallSprite()
        
        multipliers = [1.01, 1.05, 1.1, 1.15, 1.2, 1.5, 2.0]
        
        for multiplier in multipliers:
            with self.subTest(multiplier=multiplier):
                ball.speed = Speed(100.0, 200.0)
                initial_x = ball.speed.x
                initial_y = ball.speed.y
                
                # Apply logarithmic X speed-up
                ball.speed_up(multiplier=multiplier, speed_up_type="logarithmic_x")
                
                # Check precision
                self.assertAlmostEqual(ball.speed.x, initial_x * multiplier, places=10)
                self.assertAlmostEqual(ball.speed.y, initial_y, places=10)


if __name__ == "__main__":
    unittest.main()
