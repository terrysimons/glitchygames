#!/usr/bin/env python3
"""Test direction preservation for BallSprite speed-up modes."""

import unittest
import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory


class TestBallDirectionPreservation(unittest.TestCase):
    """Test BallSprite direction preservation across different speed-up modes."""

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
        """Test that linear speed-up preserves direction at all angles."""
        ball = BallSprite()
        
        # Test various angles
        test_angles = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 
                      195, 210, 225, 240, 255, 270, 285, 300, 315, 330, 345]
        
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

    def test_logarithmic_x_speed_up_changes_direction(self):
        """Test that logarithmic X speed-up changes direction."""
        ball = BallSprite()
        
        # Test with non-zero Y component
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply logarithmic X speed-up
        ball.speed_up(multiplier=1.5, speed_up_type="logarithmic_x")
        
        # Direction should change
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertNotAlmostEqual(initial_direction, new_direction, places=5,
                                msg="Direction should change with logarithmic X speed-up")

    def test_logarithmic_y_speed_up_changes_direction(self):
        """Test that logarithmic Y speed-up changes direction."""
        ball = BallSprite()
        
        # Test with non-zero X component
        ball.speed = Speed(200.0, 100.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply logarithmic Y speed-up
        ball.speed_up(multiplier=1.3, speed_up_type="logarithmic_y")
        
        # Direction should change
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertNotAlmostEqual(initial_direction, new_direction, places=5,
                                msg="Direction should change with logarithmic Y speed-up")

    def test_logarithmic_both_speed_up_changes_direction(self):
        """Test that logarithmic both speed-up preserves direction (scales both components equally)."""
        ball = BallSprite()
        
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply logarithmic both speed-up
        ball.speed_up(multiplier=1.2, speed_up_type="logarithmic_both")
        
        # Direction should be preserved (both components scaled equally)
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, new_direction, places=10,
                              msg="Direction should be preserved with logarithmic both speed-up")

    def test_direction_preservation_with_bouncing(self):
        """Test direction preservation with bouncing and speed-up."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LINEAR,
            speed_up_multiplier=1.2
        )
        
        # Set initial speed
        ball.speed = Speed(150.0, 100.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Simulate wall bounce with linear speed-up
        ball.rect.y = 0  # Hit top wall
        ball._do_bounce()
        
        # Y should be reversed, but direction should be preserved relative to the bounce
        # The bounce itself changes direction, but the speed-up should preserve the relative direction
        self.assertGreater(ball.speed.y, 0)  # Should be positive after top bounce
        self.assertAlmostEqual(ball.speed.x, 150.0 * 1.2, places=10)  # X should be scaled

    def test_direction_change_with_logarithmic_bouncing(self):
        """Test direction change with logarithmic bouncing."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.3
        )
        
        # Set initial speed
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Simulate wall bounce with logarithmic X speed-up
        ball.rect.y = 0  # Hit top wall
        ball._do_bounce()
        
        # Direction should change due to logarithmic X scaling
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertNotAlmostEqual(initial_direction, new_direction, places=5,
                                msg="Direction should change with logarithmic X bounce speed-up")

    def test_combined_linear_and_logarithmic_direction_behavior(self):
        """Test direction behavior with combined linear and logarithmic modes."""
        ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.15
        )
        
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Test continuous linear (should preserve direction)
        ball._last_speed_up_time = 0.0
        ball._check_continuous_speed_up(0.1)
        
        linear_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, linear_direction, places=10,
                             msg="Linear speed-up should preserve direction")
        
        # Test paddle bounce logarithmic X (should change direction)
        ball.on_paddle_bounce()
        
        bounce_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertNotAlmostEqual(linear_direction, bounce_direction, places=5,
                                msg="Logarithmic X speed-up should change direction")

    def test_direction_preservation_with_multiple_linear_speed_ups(self):
        """Test that multiple linear speed-ups preserve direction."""
        ball = BallSprite()
        
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply multiple linear speed-ups
        for i in range(5):
            ball.speed_up(multiplier=1.1, speed_up_type="linear")
        
        # Direction should still be preserved
        final_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, final_direction, places=12,
                             msg="Multiple linear speed-ups should preserve direction")

    def test_direction_change_with_multiple_logarithmic_speed_ups(self):
        """Test that multiple logarithmic speed-ups change direction."""
        ball = BallSprite()
        
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply multiple logarithmic X speed-ups
        for i in range(3):
            ball.speed_up(multiplier=1.2, speed_up_type="logarithmic_x")
        
        # Direction should change
        final_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertNotAlmostEqual(initial_direction, final_direction, places=5,
                                msg="Multiple logarithmic speed-ups should change direction")

    def test_edge_case_pure_horizontal_movement(self):
        """Test direction preservation with pure horizontal movement."""
        ball = BallSprite()
        
        # Pure horizontal movement
        ball.speed = Speed(100.0, 0.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Linear speed-up should preserve direction
        ball.speed_up(multiplier=1.5, speed_up_type="linear")
        linear_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, linear_direction, places=12)
        
        # Logarithmic Y speed-up should not affect direction (Y is already 0)
        ball.speed = Speed(100.0, 0.0)
        ball.speed_up(multiplier=1.5, speed_up_type="logarithmic_y")
        self.assertEqual(ball.speed.y, 0.0)  # Should remain 0
        self.assertAlmostEqual(ball.speed.x, 100.0, places=10)  # Should remain unchanged

    def test_edge_case_pure_vertical_movement(self):
        """Test direction preservation with pure vertical movement."""
        ball = BallSprite()
        
        # Pure vertical movement
        ball.speed = Speed(0.0, 100.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Linear speed-up should preserve direction
        ball.speed_up(multiplier=1.5, speed_up_type="linear")
        linear_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, linear_direction, places=12)
        
        # Logarithmic X speed-up should not affect direction (X is already 0)
        ball.speed = Speed(0.0, 100.0)
        ball.speed_up(multiplier=1.5, speed_up_type="logarithmic_x")
        self.assertEqual(ball.speed.x, 0.0)  # Should remain 0
        self.assertAlmostEqual(ball.speed.y, 100.0, places=10)  # Should remain unchanged

    def test_direction_preservation_precision(self):
        """Test high-precision direction preservation."""
        ball = BallSprite()
        
        # Use a very specific angle
        angle_radians = math.radians(33.7)  # A non-standard angle
        speed_magnitude = 100.0
        ball.speed.x = speed_magnitude * math.cos(angle_radians)
        ball.speed.y = speed_magnitude * math.sin(angle_radians)
        
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Apply linear speed-up
        ball.speed_up(multiplier=1.234567, speed_up_type="linear")
        
        # Check very high precision
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        self.assertAlmostEqual(initial_direction, new_direction, places=15,
                             msg="High-precision direction preservation failed")


if __name__ == "__main__":
    unittest.main()
