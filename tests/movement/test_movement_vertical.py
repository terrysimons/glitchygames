"""Test coverage for Vertical class."""

import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Speed, Vertical


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
        
        # Change to up
        vertical.up()
        self.assertEqual(vertical.current_speed, -7)
        
        # Stop
        vertical.stop()
        self.assertEqual(vertical.current_speed, 0)
        
        # Test with zero speed
        speed_zero = Speed(x=0, y=0)
        vertical_zero = Vertical(speed_zero)
        vertical_zero.down()
        self.assertEqual(vertical_zero.current_speed, 0)
