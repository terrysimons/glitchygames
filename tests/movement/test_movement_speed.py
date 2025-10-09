"""Test coverage for Speed class."""

import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Speed


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
        
        self.assertEqual(result.x, 4.0)
        self.assertEqual(result.y, 6.0)
        self.assertEqual(result.increment, 0.5)

    def test_imul_operator(self):
        """Test in-place multiplication operator."""
        speed = Speed(x=2, y=3, increment=0.5)
        speed *= 2.0
        
        self.assertEqual(speed.x, 4.0)
        self.assertEqual(speed.y, 6.0)
        self.assertEqual(speed.increment, 0.5)

    def test_imul_operator_with_float(self):
        """Test in-place multiplication with float."""
        speed = Speed(x=1, y=2, increment=0.3)
        speed *= 1.5
        
        self.assertEqual(speed.x, 1.5)
        self.assertEqual(speed.y, 3.0)
        self.assertEqual(speed.increment, 0.3)

    def test_speed_multiplication_with_negative_scalar(self):
        """Test Speed multiplication with negative scalar."""
        speed = Speed(x=5, y=3, increment=0.2)
        result = speed * -1.5
        
        self.assertEqual(result.x, -7.5)
        self.assertEqual(result.y, -4.5)
        self.assertEqual(result.increment, 0.2)
        # Original should be unchanged
        self.assertEqual(speed.x, 5)
        self.assertEqual(speed.y, 3)

    def test_speed_multiplication_with_zero(self):
        """Test Speed multiplication with zero."""
        speed = Speed(x=5, y=3, increment=0.2)
        result = speed * 0.0
        
        self.assertEqual(result.x, 0.0)
        self.assertEqual(result.y, 0.0)
        self.assertEqual(result.increment, 0.2)
        # Original should be unchanged
        self.assertEqual(speed.x, 5)
        self.assertEqual(speed.y, 3)

    def test_speed_multiplication_with_fraction(self):
        """Test Speed multiplication with fractional scalar."""
        speed = Speed(x=6, y=4, increment=0.2)
        result = speed * 0.5
        
        self.assertEqual(result.x, 3.0)
        self.assertEqual(result.y, 2.0)
        self.assertEqual(result.increment, 0.2)
        # Original should be unchanged
        self.assertEqual(speed.x, 6)
        self.assertEqual(speed.y, 4)

    def test_speed_inplace_multiplication_with_negative(self):
        """Test Speed in-place multiplication with negative scalar."""
        speed = Speed(x=4, y=2, increment=0.2)
        speed *= -2.0
        
        self.assertEqual(speed.x, -8.0)
        self.assertEqual(speed.y, -4.0)
        self.assertEqual(speed.increment, 0.2)

    def test_speed_inplace_multiplication_with_zero(self):
        """Test Speed in-place multiplication with zero."""
        speed = Speed(x=4, y=2, increment=0.2)
        speed *= 0.0
        
        self.assertEqual(speed.x, 0.0)
        self.assertEqual(speed.y, 0.0)
        self.assertEqual(speed.increment, 0.2)
