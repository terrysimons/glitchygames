"""Test coverage for movement integration and edge cases."""

import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Horizontal, Speed, Vertical

# Constants for magic values
SPEED_2 = 2
SPEED_2_5 = 2.5
SPEED_3 = 3
SPEED_3_5 = 3.5
SPEED_4 = 4
SPEED_6 = 6
SPEED_NEG_2 = -2
SPEED_NEG_3 = -3
SPEED_1_001 = 1.001
SPEED_11_0 = 11.0
SPEED_2_5_FLOAT = 2.5
SPEED_3_7_FLOAT = 3.7


class TestMovementIntegrationCoverage(unittest.TestCase):
    """Comprehensive test coverage for movement integration."""

    def test_speed_with_horizontal_movement(self):
        """Test Speed class with Horizontal movement integration."""
        speed = Speed(x=2, y=0, increment=0.5)
        horizontal = Horizontal(speed)

        # Test horizontal movement with speed
        horizontal.right()

        assert horizontal.current_speed == SPEED_2

        # Test speed up with horizontal movement
        speed.speed_up_horizontal()
        horizontal = Horizontal(speed)  # Create new instance with updated speed

        assert horizontal.current_speed == SPEED_2_5

    def test_speed_with_vertical_movement(self):
        """Test Speed class with Vertical movement integration."""
        speed = Speed(x=0, y=3, increment=0.5)
        vertical = Vertical(speed)

        # Test vertical movement with speed
        vertical.down()

        assert vertical.current_speed == SPEED_3

        # Test speed up with vertical movement
        speed.speed_up_vertical()
        vertical = Vertical(speed)  # Create new instance with updated speed

        assert vertical.current_speed == SPEED_3_5

    def test_speed_multiplication_with_movement(self):
        """Test speed multiplication with movement classes."""
        speed = Speed(x=2, y=3, increment=0.5)

        # Apply multiplication
        speed *= 2

        # Test with horizontal movement
        horizontal = Horizontal(speed)
        horizontal.right()
        assert horizontal.current_speed == SPEED_4

        # Test with vertical movement
        vertical = Vertical(speed)
        vertical.down()
        assert vertical.current_speed == SPEED_6

    def test_movement_with_zero_speed(self):
        """Test movement classes with zero speed."""
        speed_zero = Speed(x=0, y=0)
        horizontal = Horizontal(speed_zero)
        vertical = Vertical(speed_zero)

        # Test horizontal with zero speed
        horizontal.right()
        assert horizontal.current_speed == 0

        # Test vertical with zero speed
        vertical.down()
        assert vertical.current_speed == 0

    def test_movement_with_negative_speed(self):
        """Test movement classes with negative speed."""
        speed_neg = Speed(x=-2, y=-3)
        horizontal = Horizontal(speed_neg)
        vertical = Vertical(speed_neg)

        # Test horizontal with negative speed
        horizontal.right()
        assert horizontal.current_speed == SPEED_NEG_2

        # Test vertical with negative speed
        vertical.down()
        assert vertical.current_speed == SPEED_NEG_3


class TestMovementEdgeCasesCoverage(unittest.TestCase):
    """Comprehensive test coverage for movement edge cases."""

    def test_speed_with_very_small_increment(self):
        """Test speed with very small increment."""
        speed = Speed(x=1, y=1, increment=0.001)
        speed.speed_up()

        assert speed.x == SPEED_1_001
        assert speed.y == SPEED_1_001

    def test_speed_with_large_increment(self):
        """Test speed with large increment."""
        speed = Speed(x=1, y=1, increment=10.0)
        speed.speed_up()

        assert speed.x == SPEED_11_0
        assert speed.y == SPEED_11_0

    def test_speed_multiplication_with_zero(self):
        """Test speed multiplication with zero."""
        speed = Speed(x=5, y=3, increment=0.5)
        speed *= 0

        assert speed.x == 0
        assert speed.y == 0

    def test_speed_multiplication_with_negative(self):
        """Test speed multiplication with negative number."""
        speed = Speed(x=2, y=3, increment=0.5)
        speed *= -1

        assert speed.x == SPEED_NEG_2
        assert speed.y == SPEED_NEG_3

    def test_movement_with_float_speed(self):
        """Test movement with float speed values."""
        speed_float = Speed(x=2.5, y=3.7)
        horizontal = Horizontal(speed_float)
        vertical = Vertical(speed_float)

        # Test with float speed
        horizontal.right()
        assert horizontal.current_speed == SPEED_2_5

        vertical.down()
        assert vertical.current_speed == SPEED_3_7_FLOAT
