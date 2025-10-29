#!/usr/bin/env python3
"""Test ball speed behavior and speed-up modes."""

import math
import time
import unittest
from unittest.mock import Mock, patch

import pygame

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode


class TestBallSpeedBehavior(unittest.TestCase):
    """Test ball speed behavior and speed-up modes."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        self.screen = pygame.display.set_mode((800, 600))
        
    def tearDown(self):
        """Clean up after tests."""
        pygame.quit()

    def test_exponential_speedup_no_runaway_growth(self):
        """Test that exponential speed-up doesn't cause runaway growth."""
        # Create ball with exponential speed-up
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X | SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        # Get speed after reset() has been called
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Simulate speed-ups with small delays
        import time
        for i in range(20):
            ball.dt_tick(0.1)
            time.sleep(0.02)  # Small delay to ensure time passes
        
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Speed should increase significantly with capped exponential
        # With capped exponent (max 2.0), speed can grow substantially but not runaway
        self.assertGreater(final_magnitude, initial_magnitude * 2,
                          "Speed should increase significantly with exponential speed-up")
        
        # Speed should not exceed 100x initial speed (safety check for capped exponential)
        self.assertLess(final_magnitude, initial_magnitude * 100,
                       "Speed should not grow more than 100x initial speed with capped exponential")

    def test_logarithmic_speedup_behavior(self):
        """Test that logarithmic speed-up works correctly."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        # Get speed after reset() has been called
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        initial_magnitude = math.sqrt(initial_x**2 + initial_y**2)
        
        # Simulate speed-ups with small delays
        import time
        for i in range(20):  # More iterations to ensure we get enough speed-ups
            ball.dt_tick(0.1)
            time.sleep(0.02)  # Small delay to ensure time passes
        
        final_x = ball.speed.x
        final_y = ball.speed.y
        final_magnitude = math.sqrt(final_x**2 + final_y**2)
        
        # Speed should have increased significantly
        self.assertGreater(final_magnitude, initial_magnitude * 1.5, 
                          "Speed should increase significantly with logarithmic speed-up")
        
        # Direction should be preserved (signs should match)
        if initial_x != 0:
            self.assertEqual((final_x > 0), (initial_x > 0), "X direction should be preserved")
        if initial_y != 0:
            self.assertEqual((final_y > 0), (initial_y > 0), "Y direction should be preserved")

    def test_linear_speedup_behavior(self):
        """Test that linear speed-up preserves direction."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        # Get speed after reset() has been called
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Simulate 5 speed-ups with small delays
        import time
        for i in range(5):
            ball.dt_tick(0.1)
            time.sleep(0.02)  # Small delay to ensure time passes
        
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        final_direction = math.atan2(ball.speed.y, ball.speed.x)
        
        # Direction should be preserved
        self.assertAlmostEqual(initial_direction, final_direction, places=5)
        
        # Speed should have increased significantly
        self.assertGreater(final_magnitude, initial_magnitude * 1.2, 
                          "Speed should increase significantly with linear speed-up")

    def test_continuous_speedup_respects_interval(self):
        """Test that continuous speed-up respects the interval."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1  # Speed up every 0.1 seconds (shorter interval for testing)
        )
        
        # Get speed after reset() has been called
        initial_x = ball.speed.x
        
        # First dt_tick should not trigger speed-up (interval not reached)
        ball.dt_tick(0.05)  # Half the interval
        self.assertEqual(ball.speed.x, initial_x, "Speed should not change before interval")
        
        # After 2 dt_tick calls (0.1 seconds total), speed-up should trigger
        for i in range(2):
            ball.dt_tick(0.05)
        
        expected_x = initial_x * 1.1
        self.assertAlmostEqual(ball.speed.x, expected_x, delta=abs(expected_x) * 0.1)  # More tolerant delta

    def test_bounce_speedup_triggers(self):
        """Test that bounce-triggered speed-up works."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.1
        )
        
        # Get initial speed after reset() has been called
        initial_x = abs(ball.speed.x)  # Use absolute value since direction might change
        
        # Position ball to hit top boundary
        ball.rect.y = 1
        ball.speed.y = -100  # Moving up
        
        # This should trigger a bounce and speed-up
        ball.dt_tick(0.1)
        
        # Speed magnitude should have increased due to wall bounce
        final_x = abs(ball.speed.x)
        self.assertGreater(final_x, initial_x, f"Speed magnitude should increase on wall bounce: {initial_x:.3f} -> {final_x:.3f}")

    def test_speedup_mode_none_no_speedup(self):
        """Test that SpeedUpMode.NONE prevents any speed-up."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.NONE,
            speed_up_multiplier=1.1,
            speed_up_interval=0.1
        )
        
        # Get speed after reset() has been called
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate many dt_tick calls
        for i in range(50):
            ball.dt_tick(0.1)
        
        # Speed should remain unchanged
        self.assertEqual(ball.speed.x, initial_x)
        self.assertEqual(ball.speed.y, initial_y)

    def test_speedup_magnitude_bounds(self):
        """Test that speed doesn't grow beyond reasonable bounds."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Very frequent speed-up
        )
        
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Simulate 100 speed-ups (1 second at 0.01 interval)
        for i in range(100):
            ball.dt_tick(0.01)
        
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Speed should not grow more than 100x initial speed (safety check)
        self.assertLess(final_magnitude, initial_magnitude * 100,
                       f"Speed magnitude {final_magnitude:.3f} should not exceed 100x initial")

    def test_exponential_vs_logarithmic_comparison(self):
        """Test that both exponential and logarithmic speed-up modes work correctly."""
        # Create two balls with same settings but different speed-up modes
        exp_ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        log_ball = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        # Simulate speed-ups for both with small delays
        import time
        for i in range(10):
            exp_ball.dt_tick(0.1)
            log_ball.dt_tick(0.1)
            time.sleep(0.02)  # Small delay to ensure time passes
        
        # Both should have increased significantly (exact relationship may vary)
        exp_final = abs(exp_ball.speed.x)
        log_final = abs(log_ball.speed.x)
        
        # Both modes should show significant speed increase
        self.assertGreater(exp_final, 50, f"Exponential speed-up should show significant increase, got {exp_final:.3f}")
        self.assertGreater(log_final, 50, f"Logarithmic speed-up should show significant increase, got {log_final:.3f}")
        
        # Both should be reasonable (not runaway)
        self.assertLess(exp_final, 10000, f"Exponential speed-up should not be runaway, got {exp_final:.3f}")
        self.assertLess(log_final, 10000, f"Logarithmic speed-up should not be runaway, got {log_final:.3f}")

    def test_speedup_preserves_direction_components(self):
        """Test that speed-up preserves the direction of individual components."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,  # Only X component
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        # Get speed after reset() has been called
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate speed-up with small delays
        import time
        for i in range(5):
            ball.dt_tick(0.1)
            time.sleep(0.02)  # Small delay to ensure time passes
        
        # Only X should change, Y should remain the same
        self.assertNotEqual(ball.speed.x, initial_x, "X speed should change")
        self.assertEqual(ball.speed.y, initial_y, "Y speed should remain unchanged")

    def test_speedup_with_negative_speeds(self):
        """Test that speed-up works correctly with negative speeds."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y,
            speed_up_multiplier=1.1,
            speed_up_interval=0.01  # Much shorter interval for testing
        )
        
        # Set negative speeds (after reset() has been called)
        ball.speed.x = -100
        ball.speed.y = -50
        
        initial_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Simulate speed-up with small delays
        import time
        for i in range(5):
            ball.dt_tick(0.1)
            time.sleep(0.02)  # Small delay to ensure time passes
        
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        
        # Magnitude should increase, but signs should be preserved
        self.assertGreater(final_magnitude, initial_magnitude)
        self.assertLess(ball.speed.x, 0, "X speed should remain negative")
        self.assertLess(ball.speed.y, 0, "Y speed should remain negative")


if __name__ == "__main__":
    unittest.main()
