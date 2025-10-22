#!/usr/bin/env python3
"""Test coverage for BallSprite bounce configuration."""

import math
import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite
from tests.mocks.test_mock_factory import MockFactory


class TestBallBounceConfiguration(unittest.TestCase):
    """Test BallSprite bounce configuration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Centralized mocks are handled by conftest.py
        pass

    def tearDown(self):
        """Clean up test fixtures."""
        # Centralized mocks are handled by conftest.py
        pass

    def test_default_bounce_settings(self):
        """Test that default bounce settings are correct."""
        ball = BallSprite()
        
        # Default should be top/bottom bounce enabled, left/right disabled
        self.assertTrue(ball.bounce_top_bottom)
        self.assertFalse(ball.bounce_left_right)

    def test_custom_bounce_settings(self):
        """Test that custom bounce settings are applied correctly."""
        # Test all combinations
        ball1 = BallSprite(bounce_top_bottom=True, bounce_left_right=True)
        self.assertTrue(ball1.bounce_top_bottom)
        self.assertTrue(ball1.bounce_left_right)
        
        ball2 = BallSprite(bounce_top_bottom=True, bounce_left_right=False)
        self.assertTrue(ball2.bounce_top_bottom)
        self.assertFalse(ball2.bounce_left_right)
        
        ball3 = BallSprite(bounce_top_bottom=False, bounce_left_right=True)
        self.assertFalse(ball3.bounce_top_bottom)
        self.assertTrue(ball3.bounce_left_right)
        
        ball4 = BallSprite(bounce_top_bottom=False, bounce_left_right=False)
        self.assertFalse(ball4.bounce_top_bottom)
        self.assertFalse(ball4.bounce_left_right)

    def test_top_bottom_bounce_behavior(self):
        """Test that top/bottom bouncing works correctly."""
        ball = BallSprite(bounce_top_bottom=True, bounce_left_right=False)
        
        # Test top bounce
        ball.rect.y = 0
        ball.speed.y = -100.0  # Moving up
        initial_speed_x = ball.speed.x
        
        ball._do_bounce()
        
        # Should reverse Y direction and stay at boundary
        self.assertEqual(ball.rect.y, 1)
        self.assertGreater(ball.speed.y, 0)  # Now moving down
        self.assertEqual(ball.speed.x, initial_speed_x)  # X unchanged
        
        # Test bottom bounce
        ball.rect.y = ball.screen_height - ball.height
        ball.speed.y = 100.0  # Moving down
        initial_speed_x = ball.speed.x
        
        ball._do_bounce()
        
        # Should reverse Y direction and stay at boundary
        self.assertEqual(ball.rect.y, ball.screen_height - ball.height - 1)
        self.assertLess(ball.speed.y, 0)  # Now moving up
        self.assertEqual(ball.speed.x, initial_speed_x)  # X unchanged

    def test_left_right_bounce_behavior(self):
        """Test that left/right bouncing works correctly."""
        ball = BallSprite(bounce_top_bottom=False, bounce_left_right=True)
        
        # Test left bounce
        ball.rect.x = 0
        ball.speed.x = -100.0  # Moving left
        initial_speed_y = ball.speed.y
        
        ball._do_bounce()
        
        # Should reverse X direction and stay at boundary
        self.assertEqual(ball.rect.x, 1)
        self.assertGreater(ball.speed.x, 0)  # Now moving right
        self.assertEqual(ball.speed.y, initial_speed_y)  # Y unchanged
        
        # Test right bounce
        ball.rect.x = ball.screen_width - ball.width
        ball.speed.x = 100.0  # Moving right
        initial_speed_y = ball.speed.y
        
        ball._do_bounce()
        
        # Should reverse X direction and stay at boundary
        self.assertEqual(ball.rect.x, ball.screen_width - ball.width - 1)
        self.assertLess(ball.speed.x, 0)  # Now moving left
        self.assertEqual(ball.speed.y, initial_speed_y)  # Y unchanged

    def test_no_bounce_behavior(self):
        """Test that disabled bouncing doesn't affect position."""
        ball = BallSprite(bounce_top_bottom=False, bounce_left_right=False)
        
        # Test that no bouncing occurs
        original_x, original_y = ball.rect.x, ball.rect.y
        original_speed_x, original_speed_y = ball.speed.x, ball.speed.y
        
        ball._do_bounce()
        
        # Position and speed should be unchanged
        self.assertEqual(ball.rect.x, original_x)
        self.assertEqual(ball.rect.y, original_y)
        self.assertEqual(ball.speed.x, original_speed_x)
        self.assertEqual(ball.speed.y, original_speed_y)

    def test_ball_death_behavior(self):
        """Test that ball dies when hitting side boundaries with left/right bounce disabled."""
        ball = BallSprite(bounce_left_right=False)
        
        # Move ball off screen
        ball.rect.x = ball.screen_width + 10
        
        # Should be alive before dt_tick
        self.assertTrue(ball.alive())
        
        # dt_tick should kill the ball
        ball.dt_tick(1.0/60.0)
        
        # Should be dead after dt_tick
        self.assertFalse(ball.alive())

    def test_ball_survival_with_bounce(self):
        """Test that ball survives when left/right bouncing is enabled."""
        ball = BallSprite(bounce_left_right=True)
        
        # Move ball to edge
        ball.rect.x = ball.screen_width - ball.width
        ball.speed.x = 100.0  # Moving right
        
        # Should be alive before dt_tick
        self.assertTrue(ball.alive())
        
        # dt_tick should bounce, not kill
        ball.dt_tick(1.0/60.0)
        
        # Should still be alive after dt_tick
        self.assertTrue(ball.alive())
        
        # Should have bounced
        self.assertLess(ball.speed.x, 0)  # Now moving left

    def test_speed_direction_reversal(self):
        """Test that speed direction is correctly reversed during bounces."""
        ball = BallSprite(bounce_top_bottom=True, bounce_left_right=True)
        
        # Test top bounce - should reverse Y direction
        ball.rect.y = 0
        ball.speed.y = -100.0
        initial_speed_x = ball.speed.x
        
        ball._do_bounce()
        
        # Y should be positive (downward), X should be unchanged
        self.assertGreater(ball.speed.y, 0)
        self.assertEqual(ball.speed.x, initial_speed_x)
        
        # Test left bounce - should reverse X direction
        ball.rect.x = 0
        ball.speed.x = -100.0
        initial_speed_y = ball.speed.y
        
        ball._do_bounce()
        
        # X should be positive (rightward), Y should be unchanged
        self.assertGreater(ball.speed.x, 0)
        self.assertEqual(ball.speed.y, initial_speed_y)


if __name__ == "__main__":
    unittest.main()
