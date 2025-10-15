"""Test coverage for Horizontal class."""

import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Horizontal, Speed

# Constants for magic values
SPEED_5 = 5
SPEED_10 = 10
SPEED_NEG_5 = -5
SPEED_3 = 3
SPEED_NEG_3 = -3


class TestHorizontalCoverage(unittest.TestCase):
    """Comprehensive test coverage for Horizontal class."""

    def test_horizontal_initialization(self):
        """Test Horizontal initialization."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)

        assert horizontal.speed == speed
        assert horizontal.current_speed == SPEED_5

    def test_change_speed(self):
        """Test _change_speed method."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)

        horizontal._change_speed(10)
        assert horizontal.current_speed == SPEED_10

    def test_left_movement(self):
        """Test left movement."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)

        horizontal.left()
        assert horizontal.current_speed == SPEED_NEG_5

    def test_right_movement(self):
        """Test right movement."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)

        horizontal.right()
        assert horizontal.current_speed == SPEED_5

    def test_stop_movement(self):
        """Test stop movement."""
        speed = Speed(x=5, y=10)
        horizontal = Horizontal(speed)

        horizontal.stop()
        assert horizontal.current_speed == 0

    def test_movement_sequence(self):
        """Test sequence of movements."""
        speed = Speed(x=3, y=7)
        horizontal = Horizontal(speed)

        # Start with right
        horizontal.right()
        assert horizontal.current_speed == SPEED_3

        # Change to left
        horizontal.left()
        assert horizontal.current_speed == SPEED_NEG_3

        # Stop
        horizontal.stop()
        assert horizontal.current_speed == 0

        # Test with zero speed
        speed_zero = Speed(x=0, y=0)
        horizontal_zero = Horizontal(speed_zero)
        horizontal_zero.right()
        assert horizontal_zero.current_speed == 0
