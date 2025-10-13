"""Test coverage for Vertical class."""

import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Speed, Vertical

# Constants for magic values
SPEED_10 = 10
SPEED_15 = 15
SPEED_NEG_10 = -10
SPEED_7 = 7
SPEED_NEG_7 = -7


class TestVerticalCoverage(unittest.TestCase):
    """Comprehensive test coverage for Vertical class."""

    def test_vertical_initialization(self):
        """Test Vertical initialization."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)

        assert vertical.speed == speed
        assert vertical.current_speed == SPEED_10

    def test_change_speed(self):
        """Test _change_speed method."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)

        vertical._change_speed(15)
        assert vertical.current_speed == SPEED_15

    def test_up_movement(self):
        """Test up movement."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)

        vertical.up()
        assert vertical.current_speed == SPEED_NEG_10

    def test_down_movement(self):
        """Test down movement."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)

        vertical.down()
        assert vertical.current_speed == SPEED_10

    def test_stop_movement(self):
        """Test stop movement."""
        speed = Speed(x=5, y=10)
        vertical = Vertical(speed)

        vertical.stop()
        assert vertical.current_speed == 0

    def test_movement_sequence(self):
        """Test sequence of movements."""
        speed = Speed(x=3, y=7)
        vertical = Vertical(speed)

        # Start with down
        vertical.down()
        assert vertical.current_speed == SPEED_7

        # Change to up
        vertical.up()
        assert vertical.current_speed == SPEED_NEG_7

        # Stop
        vertical.stop()
        assert vertical.current_speed == 0

        # Test with zero speed
        speed_zero = Speed(x=0, y=0)
        vertical_zero = Vertical(speed_zero)
        vertical_zero.down()
        assert vertical_zero.current_speed == 0
