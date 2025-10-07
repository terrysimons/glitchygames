"""Test Speed class multiplication operators."""

# Add the project root to the path
import sys
import unittest
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).parent.parent))

from glitchygames.movement.speed import Speed

# Constants for test values
INITIAL_X = 5
INITIAL_Y = 3
INCREMENT = 0.2
MULTIPLIER_2 = 2.0
EXPECTED_X_10 = 10.0
EXPECTED_Y_6 = 6.0
MULTIPLIER_NEGATIVE = -1.5
EXPECTED_X_NEGATIVE = -7.5
EXPECTED_Y_NEGATIVE = -4.5
MULTIPLIER_ZERO = 0.0
EXPECTED_ZERO = 0.0
INITIAL_X_6 = 6
INITIAL_Y_4 = 4
MULTIPLIER_FRACTION = 0.5
EXPECTED_X_3 = 3.0
EXPECTED_Y_2 = 2.0
INITIAL_X_4 = 4
INITIAL_Y_2 = 2
MULTIPLIER_NEGATIVE_2 = -2.0
EXPECTED_X_NEGATIVE_8 = -8.0
EXPECTED_Y_NEGATIVE_4 = -4.0


class TestSpeedOperators(unittest.TestCase):
    """Test Speed class multiplication operators."""

    def test_speed_multiplication(self):  # noqa: PLR6301
        """Test Speed multiplication with scalar."""
        speed = Speed(x=INITIAL_X, y=INITIAL_Y, increment=INCREMENT)
        result = speed * MULTIPLIER_2
        assert result.x == EXPECTED_X_10
        assert result.y == EXPECTED_Y_6
        assert result.increment == INCREMENT  # increment should be preserved
        # Original should be unchanged
        assert speed.x == INITIAL_X
        assert speed.y == INITIAL_Y

    def test_speed_inplace_multiplication(self):  # noqa: PLR6301
        """Test Speed in-place multiplication with scalar."""
        speed = Speed(x=INITIAL_X, y=INITIAL_Y, increment=INCREMENT)
        speed *= MULTIPLIER_2
        assert speed.x == EXPECTED_X_10
        assert speed.y == EXPECTED_Y_6
        assert speed.increment == INCREMENT  # increment should be preserved

    def test_speed_multiplication_with_negative_scalar(self):  # noqa: PLR6301
        """Test Speed multiplication with negative scalar."""
        speed = Speed(x=INITIAL_X, y=INITIAL_Y, increment=INCREMENT)
        result = speed * MULTIPLIER_NEGATIVE
        assert result.x == EXPECTED_X_NEGATIVE
        assert result.y == EXPECTED_Y_NEGATIVE
        assert result.increment == INCREMENT

    def test_speed_multiplication_with_zero(self):  # noqa: PLR6301
        """Test Speed multiplication with zero."""
        speed = Speed(x=INITIAL_X, y=INITIAL_Y, increment=INCREMENT)
        result = speed * MULTIPLIER_ZERO
        assert result.x == EXPECTED_ZERO
        assert result.y == EXPECTED_ZERO
        assert result.increment == INCREMENT

    def test_speed_multiplication_with_fraction(self):  # noqa: PLR6301
        """Test Speed multiplication with fractional scalar."""
        speed = Speed(x=INITIAL_X_6, y=INITIAL_Y_4, increment=INCREMENT)
        result = speed * MULTIPLIER_FRACTION
        assert result.x == EXPECTED_X_3
        assert result.y == EXPECTED_Y_2
        assert result.increment == INCREMENT

    def test_speed_inplace_multiplication_with_negative(self):  # noqa: PLR6301
        """Test Speed in-place multiplication with negative scalar."""
        speed = Speed(x=INITIAL_X_4, y=INITIAL_Y_2, increment=INCREMENT)
        speed *= MULTIPLIER_NEGATIVE_2
        assert speed.x == EXPECTED_X_NEGATIVE_8
        assert speed.y == EXPECTED_Y_NEGATIVE_4
        assert speed.increment == INCREMENT

    def test_speed_inplace_multiplication_with_zero(self):  # noqa: PLR6301
        """Test Speed in-place multiplication with zero."""
        speed = Speed(x=INITIAL_X_4, y=INITIAL_Y_2, increment=INCREMENT)
        speed *= MULTIPLIER_ZERO
        assert speed.x == EXPECTED_ZERO
        assert speed.y == EXPECTED_ZERO
        assert speed.increment == INCREMENT


if __name__ == "__main__":
    unittest.main()
