"""Test ball paddle collision detection and clipping prevention."""

import unittest
from unittest.mock import Mock, patch

from glitchygames.game_objects.ball import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle
from tests.mocks.test_mock_factory import MockFactory


class TestBallPaddleCollision(unittest.TestCase):
    """Test ball paddle collision detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_paddle_collision_detection(self):
        """Test that ball detects collision with paddle."""
        # Create a ball and paddle with collision sound
        import pygame
        group = pygame.sprite.Group()
        
        ball = BallSprite(x=100, y=100, groups=group)
        paddle = VerticalPaddle("Test Paddle", (20, 100), (50, 50), (255, 255, 255), 400, collision_sound="test.wav", groups=group)
        
        # Position ball so it overlaps with paddle
        ball.rect.x = 55  # Overlaps with paddle at x=50, width=20
        ball.rect.y = 75  # Within paddle's y range
        
        # Mock the paddle detection
        with patch.object(ball, '_adjust_position_for_paddle_collision') as mock_adjust:
            ball._check_paddle_collisions()
            mock_adjust.assert_called_once_with(paddle)

    def test_paddle_collision_position_adjustment(self):
        """Test that ball position is adjusted to prevent clipping."""
        # Create a ball and paddle
        ball = BallSprite(x=100, y=100)
        paddle = Mock()
        paddle.rect = Mock()
        paddle.rect.left = 50
        paddle.rect.right = 70
        paddle.rect.centerx = 60
        
        # Position ball so it's on the left side of paddle
        ball.rect.centerx = 55  # Left of paddle center
        ball.rect.right = 65    # Overlapping with paddle
        
        # Adjust position
        ball._adjust_position_for_paddle_collision(paddle)
        
        # Ball should be positioned to the left of paddle
        self.assertEqual(ball.rect.right, paddle.rect.left)

    def test_paddle_collision_position_adjustment_right_side(self):
        """Test that ball position is adjusted when on right side of paddle."""
        # Create a ball and paddle
        ball = BallSprite(x=100, y=100)
        paddle = Mock()
        paddle.rect = Mock()
        paddle.rect.left = 50
        paddle.rect.right = 70
        paddle.rect.centerx = 60
        
        # Position ball so it's on the right side of paddle
        ball.rect.centerx = 65  # Right of paddle center
        ball.rect.left = 55     # Overlapping with paddle
        
        # Adjust position
        ball._adjust_position_for_paddle_collision(paddle)
        
        # Ball should be positioned to the right of paddle
        self.assertEqual(ball.rect.left, paddle.rect.right)

    def test_no_collision_when_not_overlapping(self):
        """Test that no adjustment occurs when ball and paddle don't overlap."""
        # Create a ball and paddle with collision sound
        ball = BallSprite(x=100, y=100)
        paddle = VerticalPaddle("Test Paddle", (20, 100), (50, 50), (255, 255, 255), 400, collision_sound="test.wav")
        
        # Add both to a real pygame group
        import pygame
        group = pygame.sprite.Group()
        group.add(ball, paddle)
        
        # Position ball so it doesn't overlap with paddle
        ball.rect.x = 100  # Far from paddle at x=50
        ball.rect.y = 75
        
        # Mock the paddle detection
        with patch.object(ball, '_adjust_position_for_paddle_collision') as mock_adjust:
            ball._check_paddle_collisions()
            mock_adjust.assert_not_called()

    def test_paddle_collision_bounce_behavior(self):
        """Test that ball bounces off paddle correctly."""
        # Create a ball and paddle with collision sound
        import pygame
        group = pygame.sprite.Group()
        
        ball = BallSprite(x=100, y=100, groups=group)
        paddle = VerticalPaddle("Test Paddle", (20, 100), (50, 50), (255, 255, 255), 400, collision_sound="test.wav", groups=group)
        
        # Position ball so it overlaps with paddle
        ball.rect.x = 55  # Overlaps with paddle at x=50, width=20
        ball.rect.y = 75  # Within paddle's y range
        
        # Set initial speed (moving right)
        ball.speed.x = 100.0
        ball.speed.y = 50.0
        
        # Call the collision adjustment directly
        ball._adjust_position_for_paddle_collision(paddle)
        
        # Ball should be positioned to the right of paddle
        self.assertEqual(ball.rect.left, paddle.rect.right)
        # Ball should bounce (X speed should be positive after hitting right side)
        self.assertGreater(ball.speed.x, 0)
        # Y speed should be unchanged
        self.assertEqual(ball.speed.y, 50.0)
        # Ball should be marked as dirty
        self.assertEqual(ball.dirty, 2)


if __name__ == "__main__":
    unittest.main()
