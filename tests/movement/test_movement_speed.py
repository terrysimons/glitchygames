"""Test coverage for Speed class."""

import sys
import unittest
from pathlib import Path

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Speed

# Constants for magic values
DEFAULT_INCREMENT = 0.2
CUSTOM_X = 5
CUSTOM_Y = 10
CUSTOM_INCREMENT = 0.5
MULTIPLIER_2 = 2.0
RESULT_4_0 = 4.0
RESULT_6_0 = 6.0
INCREMENT_0_5 = 0.5
RESULT_1_5 = 1.5
RESULT_3_0 = 3.0
INCREMENT_0_3 = 0.3
RESULT_NEG_7_5 = -7.5
RESULT_NEG_4_5 = -4.5
INCREMENT_0_2 = 0.2
ORIGINAL_X_5 = 5
ORIGINAL_Y_3 = 3
RESULT_3_0_FRACTION = 3.0
RESULT_2_0_FRACTION = 2.0
ORIGINAL_X_6 = 6
ORIGINAL_Y_4 = 4
RESULT_NEG_8_0 = -8.0
RESULT_NEG_4_0 = -4.0


class TestSpeedCoverage(unittest.TestCase):
    """Comprehensive test coverage for Speed class."""

    def test_speed_initialization_default(self):
        """Test Speed initialization with default values."""
        speed = Speed()
        assert speed.x == 0
        assert speed.y == 0
        assert speed.increment == DEFAULT_INCREMENT

    def test_speed_initialization_custom(self):
        """Test Speed initialization with custom values."""
        speed = Speed(x=5, y=10, increment=0.5)
        assert speed.x == CUSTOM_X
        assert speed.y == CUSTOM_Y
        assert speed.increment == CUSTOM_INCREMENT

    def test_speed_up(self):
        """Test speed_up method calls both horizontal and vertical speed up."""
        speed = Speed(x=1, y=2, increment=0.3)
        original_x = speed.x
        original_y = speed.y

        speed.speed_up()

        # Should have called both horizontal and vertical speed up
        assert speed.x != original_x
        assert speed.y != original_y

    def test_speed_up_horizontal_positive(self):
        """Test speed_up_horizontal with positive x value."""
        speed = Speed(x=1, increment=0.3)
        original_x = speed.x

        speed.speed_up_horizontal()

        assert speed.x == original_x + 0.3

    def test_speed_up_horizontal_negative(self):
        """Test speed_up_horizontal with negative x value."""
        speed = Speed(x=-1, increment=0.3)
        original_x = speed.x

        speed.speed_up_horizontal()

        assert speed.x == original_x - 0.3

    def test_speed_up_horizontal_zero(self):
        """Test speed_up_horizontal with zero x value."""
        speed = Speed(x=0, increment=0.3)
        original_x = speed.x

        speed.speed_up_horizontal()

        assert speed.x == original_x + 0.3

    def test_speed_up_vertical_positive(self):
        """Test speed_up_vertical with positive y value."""
        speed = Speed(y=1, increment=0.3)
        original_y = speed.y

        speed.speed_up_vertical()

        assert speed.y == original_y + 0.3

    def test_speed_up_vertical_negative(self):
        """Test speed_up_vertical with negative y value."""
        speed = Speed(y=-1, increment=0.3)
        original_y = speed.y

        speed.speed_up_vertical()

        assert speed.y == original_y - 0.3

    def test_speed_up_vertical_zero(self):
        """Test speed_up_vertical with zero y value."""
        speed = Speed(y=0, increment=0.3)
        original_y = speed.y

        speed.speed_up_vertical()

        assert speed.y == original_y + 0.3

    def test_mul_operator(self):
        """Test multiplication operator."""
        speed = Speed(x=2, y=3, increment=0.5)
        result = speed * 2.0

        assert result.x == RESULT_4_0
        assert result.y == RESULT_6_0
        assert result.increment == CUSTOM_INCREMENT

    def test_imul_operator(self):
        """Test in-place multiplication operator."""
        speed = Speed(x=2, y=3, increment=0.5)
        speed *= 2.0

        assert speed.x == RESULT_4_0
        assert speed.y == RESULT_6_0
        assert speed.increment == CUSTOM_INCREMENT

    def test_imul_operator_with_float(self):
        """Test in-place multiplication with float."""
        speed = Speed(x=1, y=2, increment=0.3)
        speed *= 1.5

        assert speed.x == RESULT_1_5
        assert speed.y == RESULT_3_0
        assert speed.increment == INCREMENT_0_3

    def test_speed_multiplication_with_negative_scalar(self):
        """Test Speed multiplication with negative scalar."""
        speed = Speed(x=5, y=3, increment=0.2)
        result = speed * -1.5

        assert result.x == RESULT_NEG_7_5
        assert result.y == RESULT_NEG_4_5
        assert result.increment == DEFAULT_INCREMENT
        # Original should be unchanged
        assert speed.x == CUSTOM_X
        assert speed.y == ORIGINAL_Y_3

    def test_speed_multiplication_with_zero(self):
        """Test Speed multiplication with zero."""
        speed = Speed(x=5, y=3, increment=0.2)
        result = speed * 0.0

        assert result.x == 0.0
        assert result.y == 0.0
        assert result.increment == DEFAULT_INCREMENT
        # Original should be unchanged
        assert speed.x == CUSTOM_X
        assert speed.y == ORIGINAL_Y_3

    def test_speed_multiplication_with_fraction(self):
        """Test Speed multiplication with fractional scalar."""
        speed = Speed(x=6, y=4, increment=0.2)
        result = speed * 0.5

        assert result.x == RESULT_3_0
        assert result.y == RESULT_2_0_FRACTION
        assert result.increment == DEFAULT_INCREMENT
        # Original should be unchanged
        assert speed.x == ORIGINAL_X_6
        assert speed.y == ORIGINAL_Y_4

    def test_speed_inplace_multiplication_with_negative(self):
        """Test Speed in-place multiplication with negative scalar."""
        speed = Speed(x=4, y=2, increment=0.2)
        speed *= -2.0

        assert speed.x == RESULT_NEG_8_0
        assert speed.y == RESULT_NEG_4_0
        assert speed.increment == DEFAULT_INCREMENT

    def test_speed_inplace_multiplication_with_zero(self):
        """Test Speed in-place multiplication with zero."""
        speed = Speed(x=4, y=2, increment=0.2)
        speed *= 0.0

        assert speed.x == 0.0
        assert speed.y == 0.0
        assert speed.increment == DEFAULT_INCREMENT
