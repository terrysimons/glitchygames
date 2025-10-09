"""Comprehensive test coverage for Movement module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.movement import Horizontal, Speed, Vertical


class TestSpeedCoverage(unittest.TestCase):
    """Comprehensive test coverage for Speed class."""

    def test_speed_initialization_default(self):
        """Test Speed initialization with default values."""
        speed = Speed()
        self.assertEqual(speed.x, 0)
        self.assertEqual(speed.y, 0)
        self.assertEqual(speed.increment, 0.2)

    def test_speed_initialization_custom(self):
        """Test Speed initialization with custom values."""
        speed = Speed(x=5, y=10, increment=0.5)
        self.assertEqual(speed.x, 5)
        self.assertEqual(speed.y, 10)
        self.assertEqual(speed.increment, 0.5)

    def test_speed_up(self):
        """Test speed_up method calls both horizontal and vertical speed up."""
        speed = Speed(x=1, y=2, increment=0.3)
        original_x = speed.x
        original_y = speed.y
        
        speed.speed_up()
        
        # Should have called both horizontal and vertical speed up
        self.assertNotEqual(speed.x, original_x)
        self.assertNotEqual(speed.y, original_y)

    def test_speed_up_horizontal_positive(self):
        """Test speed_up_horizontal with positive x value."""
        speed = Speed(x=1, increment=0.3)
        original_x = speed.x
        
        speed.speed_up_horizontal()
        
        self.assertEqual(speed.x, original_x + 0.3)

    def test_speed_up_horizontal_negative(self):
        """Test speed_up_horizontal with negative x value."""
        speed = Speed(x=-1, increment=0.3)
        original_x = speed.x
        
        speed.speed_up_horizontal()
        
        self.assertEqual(speed.x, original_x - 0.3)

    def test_speed_up_horizontal_zero(self):
        """Test speed_up_horizontal with zero x value."""
        speed = Speed(x=0, increment=0.3)
        original_x = speed.x
        
        speed.speed_up_horizontal()
        
        self.assertEqual(speed.x, original_x + 0.3)

    def test_speed_up_vertical_positive(self):
        """Test speed_up_vertical with positive y value."""
        speed = Speed(y=1, increment=0.3)
        original_y = speed.y
        
        speed.speed_up_vertical()
        
        self.assertEqual(speed.y, original_y + 0.3)

    def test_speed_up_vertical_negative(self):
        """Test speed_up_vertical with negative y value."""
        speed = Speed(y=-1, increment=0.3)
        original_y = speed.y
        
        speed.speed_up_vertical()
        
        self.assertEqual(speed.y, original_y - 0.3)

    def test_speed_up_vertical_zero(self):
        """Test speed_up_vertical with zero y value."""
        speed = Speed(y=0, increment=0.3)
        original_y = speed.y
        
        speed.speed_up_vertical()
        
        self.assertEqual(speed.y, original_y + 0.3)

    def test_mul_operator(self):
        """Test multiplication operator."""
        speed = Speed(x=2, y=3, increment=0.5)
        result = speed * 2.0
        
        self.assertIsInstance(result, Speed)
        self.assertEqual(result.x, 4.0)
        self.assertEqual(result.y, 6.0)
        self.assertEqual(result.increment, 0.5)
        # Original should be unchanged
        self.assertEqual(speed.x, 2)
        self.assertEqual(speed.y, 3)

    def test_imul_operator(self):
        """Test in-place multiplication operator."""
        speed = Speed(x=2, y=3, increment=0.5)
        result = speed.__imul__(2.0)
        
        self.assertIs(result, speed)  # Should return self
        self.assertEqual(speed.x, 4.0)
        self.assertEqual(speed.y, 6.0)
        self.assertEqual(speed.increment, 0.5)

    def test_imul_operator_with_float(self):
        """Test in-place multiplication with float scalar."""
        speed = Speed(x=1.5, y=2.5, increment=0.3)
        speed *= 1.5
        
        self.assertEqual(speed.x, 2.25)
        self.assertEqual(speed.y, 3.75)
        self.assertEqual(speed.increment, 0.3)


class TestHorizontalCoverage(unittest.TestCase):
    """Comprehensive test coverage for Horizontal class."""

    def test_horizontal_initialization(self):
        """Test Horizontal initialization."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)
        
        self.assertEqual(horizontal.speed, speed)
        self.assertEqual(horizontal.current_speed, 5)

    def test_change_speed(self):
        """Test _change_speed method."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)
        
        horizontal._change_speed(10)
        self.assertEqual(horizontal.current_speed, 10)

    def test_left_movement(self):
        """Test left movement."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)
        
        horizontal.left()
        self.assertEqual(horizontal.current_speed, -5)

    def test_right_movement(self):
        """Test right movement."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)
        
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 5)

    def test_stop_movement(self):
        """Test stop movement."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)
        
        horizontal.stop()
        self.assertEqual(horizontal.current_speed, 0)

    def test_movement_sequence(self):
        """Test sequence of movements."""
        speed = Speed(x=3, y=7)
        horizontal = Horizontal(speed)
        
        # Start with right
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 3)
        
        # Then left
        horizontal.left()
        self.assertEqual(horizontal.current_speed, -3)
        
        # Then stop
        horizontal.stop()
        self.assertEqual(horizontal.current_speed, 0)
        
        # Then right again
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 3)


class TestVerticalCoverage(unittest.TestCase):
    """Comprehensive test coverage for Vertical class."""

    def test_vertical_initialization(self):
        """Test Vertical initialization."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)
        
        self.assertEqual(vertical.speed, speed)
        self.assertEqual(vertical.current_speed, 10)

    def test_change_speed(self):
        """Test _change_speed method."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)
        
        vertical._change_speed(15)
        self.assertEqual(vertical.current_speed, 15)

    def test_up_movement(self):
        """Test up movement."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)
        
        vertical.up()
        self.assertEqual(vertical.current_speed, -10)

    def test_down_movement(self):
        """Test down movement."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)
        
        vertical.down()
        self.assertEqual(vertical.current_speed, 10)

    def test_stop_movement(self):
        """Test stop movement."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)
        
        vertical.stop()
        self.assertEqual(vertical.current_speed, 0)

    def test_movement_sequence(self):
        """Test sequence of movements."""
        speed = Speed(x=3, y=7)
        vertical = Vertical(speed)
        
        # Start with down
        vertical.down()
        self.assertEqual(vertical.current_speed, 7)
        
        # Then up
        vertical.up()
        self.assertEqual(vertical.current_speed, -7)
        
        # Then stop
        vertical.stop()
        self.assertEqual(vertical.current_speed, 0)
        
        # Then down again
        vertical.down()
        self.assertEqual(vertical.current_speed, 7)


class TestMovementIntegrationCoverage(unittest.TestCase):
    """Integration tests for Movement module."""

    def test_speed_with_horizontal_movement(self):
        """Test Speed class with Horizontal movement."""
        speed = Speed(x=2, y=3, increment=0.1)
        horizontal = Horizontal(speed)
        
        # Test initial state
        self.assertEqual(horizontal.current_speed, 2)
        
        # Test movement
        horizontal.left()
        self.assertEqual(horizontal.current_speed, -2)
        
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 2)
        
        # Test speed up
        speed.speed_up_horizontal()
        self.assertEqual(speed.x, 2.1)
        
        # Test movement after speed up
        horizontal.left()
        self.assertEqual(horizontal.current_speed, -2.1)

    def test_speed_with_vertical_movement(self):
        """Test Speed class with Vertical movement."""
        speed = Speed(x=2, y=3, increment=0.1)
        vertical = Vertical(speed)
        
        # Test initial state
        self.assertEqual(vertical.current_speed, 3)
        
        # Test movement
        vertical.up()
        self.assertEqual(vertical.current_speed, -3)
        
        vertical.down()
        self.assertEqual(vertical.current_speed, 3)
        
        # Test speed up
        speed.speed_up_vertical()
        self.assertEqual(speed.y, 3.1)
        
        # Test movement after speed up
        vertical.up()
        self.assertEqual(vertical.current_speed, -3.1)

    def test_speed_multiplication_with_movement(self):
        """Test Speed multiplication with movement classes."""
        speed = Speed(x=2, y=3, increment=0.1)
        horizontal = Horizontal(speed)
        vertical = Vertical(speed)
        
        # Test original speeds
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 2)
        vertical.down()
        self.assertEqual(vertical.current_speed, 3)
        
        # Multiply speed
        speed *= 2.0
        
        # Test new speeds
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 4.0)
        vertical.down()
        self.assertEqual(vertical.current_speed, 6.0)

    def test_movement_with_zero_speed(self):
        """Test movement classes with zero speed."""
        speed = Speed(x=0, y=0, increment=0.1)
        horizontal = Horizontal(speed)
        vertical = Vertical(speed)
        
        # Test movements with zero speed
        horizontal.left()
        self.assertEqual(horizontal.current_speed, 0)
        horizontal.right()
        self.assertEqual(horizontal.current_speed, 0)
        
        vertical.up()
        self.assertEqual(vertical.current_speed, 0)
        vertical.down()
        self.assertEqual(vertical.current_speed, 0)

    def test_movement_with_negative_speed(self):
        """Test movement classes with negative speed."""
        speed = Speed(x=-2, y=-3, increment=0.1)
        horizontal = Horizontal(speed)
        vertical = Vertical(speed)
        
        # Test movements with negative speed
        horizontal.left()
        self.assertEqual(horizontal.current_speed, 2)  # -(-2) = 2
        horizontal.right()
        self.assertEqual(horizontal.current_speed, -2)
        
        vertical.up()
        self.assertEqual(vertical.current_speed, 3)  # -(-3) = 3
        vertical.down()
        self.assertEqual(vertical.current_speed, -3)


class TestMovementEdgeCasesCoverage(unittest.TestCase):
    """Edge cases and error handling for Movement module."""

    def test_speed_with_very_small_increment(self):
        """Test Speed with very small increment."""
        speed = Speed(x=1, y=1, increment=0.001)
        
        speed.speed_up_horizontal()
        self.assertEqual(speed.x, 1.001)
        
        speed.speed_up_vertical()
        self.assertEqual(speed.y, 1.001)

    def test_speed_with_large_increment(self):
        """Test Speed with large increment."""
        speed = Speed(x=1, y=1, increment=10.0)
        
        speed.speed_up_horizontal()
        self.assertEqual(speed.x, 11.0)
        
        speed.speed_up_vertical()
        self.assertEqual(speed.y, 11.0)

    def test_speed_multiplication_with_zero(self):
        """Test Speed multiplication with zero."""
        speed = Speed(x=5, y=3, increment=0.2)
        result = speed * 0
        
        self.assertEqual(result.x, 0)
        self.assertEqual(result.y, 0)
        self.assertEqual(result.increment, 0.2)

    def test_speed_multiplication_with_negative(self):
        """Test Speed multiplication with negative scalar."""
        speed = Speed(x=2, y=3, increment=0.1)
        result = speed * -1
        
        self.assertEqual(result.x, -2)
        self.assertEqual(result.y, -3)
        self.assertEqual(result.increment, 0.1)

    def test_movement_with_float_speed(self):
        """Test movement classes with float speed values."""
        speed = Speed(x=2.5, y=3.7, increment=0.1)
        horizontal = Horizontal(speed)
        vertical = Vertical(speed)
        
        horizontal.left()
        self.assertEqual(horizontal.current_speed, -2.5)
        
        vertical.up()
        self.assertEqual(vertical.current_speed, -3.7)


if __name__ == "__main__":
    unittest.main()