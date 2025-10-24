#!/usr/bin/env python3
"""Test coverage for BallSprite speed_up method."""

import math
import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import BallSprite
from tests.mocks.test_mock_factory import MockFactory

# Constants for magic values
MULTIPLIER_1_15 = 1.15
MULTIPLIER_1_1 = 1.1
TOLERANCE_1E_10 = 1e-10


class TestBallSpriteSpeedUp(unittest.TestCase):
    """Test BallSprite speed_up method for precision and consistency."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_speed_up_applies_correct_multiplier(self):
        """Test that speed_up applies the exact multiplier specified."""
        ball = BallSprite()
        initial_speed_x = ball.speed.x
        initial_speed_y = ball.speed.y
        initial_magnitude = math.sqrt(initial_speed_x**2 + initial_speed_y**2)

        # Apply 15% speed increase
        ball.speed_up(1.15)

        # Check that both components are multiplied by exactly 1.15
        assert abs(ball.speed.x - initial_speed_x * 1.15) < TOLERANCE_1E_10
        assert abs(ball.speed.y - initial_speed_y * 1.15) < TOLERANCE_1E_10

        # Check that speed magnitude is also multiplied by 1.15
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert abs(final_magnitude - initial_magnitude * 1.15) < TOLERANCE_1E_10

    def test_speed_up_preserves_direction(self):
        """Test that speed_up preserves the direction of movement."""
        ball = BallSprite()
        ball.speed.x = 100.0
        ball.speed.y = 50.0
        
        # Calculate initial direction
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        ball.speed_up(1.15)

        # Calculate final direction
        final_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Direction should be preserved (within floating point precision)
        assert abs(final_direction - initial_direction) < TOLERANCE_1E_10

    def test_speed_up_symmetric_scaling(self):
        """Test that speed_up scales both X and Y components identically."""
        ball = BallSprite()
        ball.speed.x = 200.0
        ball.speed.y = 150.0

        ball.speed_up(1.2)

        # Both components should be scaled by the same factor
        x_scale_factor = ball.speed.x / 200.0
        y_scale_factor = ball.speed.y / 150.0

        assert abs(x_scale_factor - y_scale_factor) < TOLERANCE_1E_10
        assert abs(x_scale_factor - 1.2) < TOLERANCE_1E_10

    def test_multiple_speed_up_calls(self):
        """Test that multiple speed_up calls work consistently."""
        ball = BallSprite()
        ball.speed.x = 100.0
        ball.speed.y = 100.0

        # Apply multiple speed increases
        for i in range(5):
            ball.speed_up(1.1)

        # Speed should be 100 * (1.1^5) = 161.051
        expected_speed = 100.0 * (1.1 ** 5)
        assert abs(ball.speed.x - expected_speed) < TOLERANCE_1E_10
        assert abs(ball.speed.y - expected_speed) < TOLERANCE_1E_10

    def test_speed_up_with_different_multipliers(self):
        """Test speed_up with various multiplier values."""
        multipliers = [1.05, 1.1, 1.15, 1.2, 1.5, 2.0]

        for multiplier in multipliers:
            ball = BallSprite()
            ball.speed.x = 50.0
            ball.speed.y = 75.0

            ball.speed_up(multiplier)

            # Check that both components are scaled by the exact multiplier
            assert abs(ball.speed.x - 50.0 * multiplier) < TOLERANCE_1E_10
            assert abs(ball.speed.y - 75.0 * multiplier) < TOLERANCE_1E_10

    def test_speed_up_with_negative_speeds(self):
        """Test speed_up with negative speed components."""
        ball = BallSprite()
        ball.speed.x = -100.0
        ball.speed.y = -50.0

        ball.speed_up(1.15)

        # Negative speeds should be scaled correctly
        assert abs(ball.speed.x - (-100.0 * 1.15)) < TOLERANCE_1E_10
        assert abs(ball.speed.y - (-50.0 * 1.15)) < TOLERANCE_1E_10

    def test_speed_up_with_mixed_signs(self):
        """Test speed_up with mixed positive/negative speed components."""
        ball = BallSprite()
        ball.speed.x = 100.0
        ball.speed.y = -50.0

        ball.speed_up(1.2)

        # Mixed signs should be handled correctly
        assert abs(ball.speed.x - (100.0 * 1.2)) < TOLERANCE_1E_10
        assert abs(ball.speed.y - (-50.0 * 1.2)) < TOLERANCE_1E_10

    def test_speed_up_preserves_speed_ratio(self):
        """Test that speed_up preserves the ratio between X and Y speeds."""
        ball = BallSprite()
        ball.speed.x = 300.0
        ball.speed.y = 400.0
        
        # Calculate initial ratio
        initial_ratio = ball.speed.y / ball.speed.x

        ball.speed_up(1.25)

        # Calculate final ratio
        final_ratio = ball.speed.y / ball.speed.x

        # Ratio should be preserved
        assert abs(final_ratio - initial_ratio) < TOLERANCE_1E_10

    def test_speed_up_no_precision_loss(self):
        """Test that speed_up doesn't introduce precision errors over many calls."""
        ball = BallSprite()
        ball.speed.x = 1.0
        ball.speed.y = 1.0

        # Apply many small speed increases
        for i in range(100):
            ball.speed_up(1.01)

        # Both components should be identical (no asymmetric precision loss)
        assert abs(ball.speed.x - ball.speed.y) < TOLERANCE_1E_10

        # Speed should be 1.0 * (1.01^100) ≈ 2.7048
        expected_speed = 1.0 * (1.01 ** 100)
        assert abs(ball.speed.x - expected_speed) < TOLERANCE_1E_10


if __name__ == "__main__":
    unittest.main()
