#!/usr/bin/env python3
"""Test linear speed-up behavior for BallSprite."""

import unittest
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory


class TestBallLinearSpeedUp(unittest.TestCase):
    """Test BallSprite linear speed-up behavior."""

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

    def test_linear_speed_up_preserves_direction(self):
        """Test that linear speed-up preserves ball direction."""
        ball = BallSprite()
        # Set a specific direction
        ball.speed = Speed(100.0, 200.0)  # 45-degree angle-ish
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply linear speed-up
        ball.speed_up(multiplier=1.5, speed_up_type="linear")
        
        # Check that direction is preserved
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, new_direction, places=10)
        
        # Check that magnitude increased
        initial_magnitude = math.sqrt(100.0**2 + 200.0**2)
        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        expected_magnitude = initial_magnitude * 1.5
        self.assertAlmostEqual(new_magnitude, expected_magnitude, places=10)

    def test_linear_speed_up_with_bounce(self):
        """Test linear speed-up behavior with wall bouncing."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LINEAR,
            speed_up_multiplier=1.2
        )
        
        # Set initial speed
        ball.speed = Speed(150.0, 100.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Simulate wall bounce
        ball.rect.y = 0  # Hit top wall
        ball._do_bounce()
        
        # Check that speed increased and direction changed appropriately
        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        expected_magnitude = initial_magnitude * 1.2
        self.assertAlmostEqual(new_magnitude, expected_magnitude, places=10)
        
        # Y speed should be positive (downward) after top bounce
        self.assertGreater(ball.speed.y, 0)

    def test_linear_speed_up_with_paddle_bounce(self):
        """Test linear speed-up behavior with paddle bouncing."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.ON_BOUNCE_LINEAR,
            speed_up_multiplier=1.3
        )
        
        # Set initial speed
        ball.speed = Speed(200.0, 150.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Simulate paddle bounce
        ball.on_paddle_bounce()
        
        # Check that speed increased
        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        expected_magnitude = initial_magnitude * 1.3
        self.assertAlmostEqual(new_magnitude, expected_magnitude, places=10)

    def test_linear_continuous_speed_up(self):
        """Test continuous linear speed-up over time."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1
        )
        
        # Set initial speed
        ball.speed = Speed(100.0, 100.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Simulate time passing
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)  # Should trigger speed-up
        
        # Check that speed increased and direction preserved
        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        expected_magnitude = initial_magnitude * 1.1
        self.assertAlmostEqual(new_magnitude, expected_magnitude, places=10)
        
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, new_direction, places=10)

    def test_linear_speed_up_multiple_applications(self):
        """Test that multiple linear speed-ups compound correctly."""
        ball = BallSprite()
        
        # Set initial speed
        ball.speed = Speed(50.0, 50.0)
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Apply speed-up multiple times
        for i in range(3):
            ball.speed_up(multiplier=1.2, speed_up_type="linear")
        
        # Check final magnitude
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        expected_magnitude = initial_magnitude * (1.2 ** 3)
        self.assertAlmostEqual(final_magnitude, expected_magnitude, places=10)

    def test_linear_speed_up_with_zero_speed(self):
        """Test linear speed-up behavior with zero initial speed."""
        ball = BallSprite()
        
        # Set zero speed
        ball.speed = Speed(0.0, 0.0)
        
        # Apply linear speed-up
        ball.speed_up(multiplier=1.5, speed_up_type="linear")
        
        # Should remain zero
        self.assertEqual(ball.speed.x, 0.0)
        self.assertEqual(ball.speed.y, 0.0)

    def test_linear_speed_up_direction_preservation_accuracy(self):
        """Test that linear speed-up preserves direction with high precision."""
        ball = BallSprite()
        
        # Test with various angles
        test_angles = [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]
        
        for angle_degrees in test_angles:
            with self.subTest(angle=angle_degrees):
                # Set speed at specific angle
                angle_radians = math.radians(angle_degrees)
                speed_magnitude = 100.0
                ball.speed.x = speed_magnitude * math.cos(angle_radians)
                ball.speed.y = speed_magnitude * math.sin(angle_radians)
                
                initial_direction = math.atan2(ball.speed.y, ball.speed.x)
                
                # Apply linear speed-up
                ball.speed_up(multiplier=1.5, speed_up_type="linear")
                
                # Check direction preservation
                new_direction = math.atan2(ball.speed.y, ball.speed.x)
                self.assertAlmostEqual(initial_direction, new_direction, places=12,
                                     msg=f"Direction not preserved for angle {angle_degrees}°")


if __name__ == "__main__":
    unittest.main()
