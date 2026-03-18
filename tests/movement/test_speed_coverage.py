"""Extended test coverage for Speed class arithmetic operators and apply_dt."""

import math
import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.movement import Speed

# Constants for test values
SPEED_X = 10.0
SPEED_Y = 5.0
SPEED_INCREMENT = 0.3
OTHER_X = 3.0
OTHER_Y = 2.0
SCALAR_VALUE = 2.5
DELTA_TIME = 0.016


class TestSpeedRadd:
    """Tests for __radd__ (right addition) operator."""

    def test_radd_with_int(self):
        """Test right addition with an integer value."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = 7 + speed
        assert result == 7 + SPEED_Y

    def test_radd_with_float(self):
        """Test right addition with a float value."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = 3.5 + speed
        assert math.isclose(result, 8.5)

    def test_radd_with_non_numeric_returns_not_implemented(self):
        """Test right addition with non-numeric type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        # Use direct dunder call since operators don't expose NotImplemented
        result = Speed.__radd__(speed, 'not a number')
        assert result is NotImplemented


class TestSpeedNeg:
    """Tests for __neg__ (negation) operator."""

    def test_neg_positive_values(self):
        """Test negation of positive speed values."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = -speed
        assert result.x == -SPEED_X
        assert result.y == -SPEED_Y
        assert result.increment == SPEED_INCREMENT

    def test_neg_negative_values(self):
        """Test negation of negative speed values produces positive."""
        speed = Speed(x=-SPEED_X, y=-SPEED_Y, increment=SPEED_INCREMENT)
        result = -speed
        assert result.x == SPEED_X
        assert result.y == SPEED_Y

    def test_neg_zero_values(self):
        """Test negation of zero speed values."""
        speed = Speed(x=0, y=0, increment=SPEED_INCREMENT)
        result = -speed
        assert result.x == 0
        assert result.y == 0

    def test_neg_does_not_mutate_original(self):
        """Test that negation creates a new Speed and does not mutate the original."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        _result = -speed
        assert speed.x == SPEED_X
        assert speed.y == SPEED_Y


class TestSpeedSub:
    """Tests for __sub__ (subtraction) operator."""

    def test_sub_with_speed_object(self):
        """Test subtraction of one Speed from another."""
        speed_a = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        speed_b = Speed(x=OTHER_X, y=OTHER_Y, increment=SPEED_INCREMENT)
        result = speed_a - speed_b
        assert result.x == SPEED_X - OTHER_X
        assert result.y == SPEED_Y - OTHER_Y
        assert result.increment == SPEED_INCREMENT

    def test_sub_with_float(self):
        """Test subtraction of a float scalar from Speed."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed - SCALAR_VALUE
        assert result.x == SPEED_X - SCALAR_VALUE
        assert result.y == SPEED_Y - SCALAR_VALUE
        assert result.increment == SPEED_INCREMENT

    def test_sub_with_int(self):
        """Test subtraction of an integer scalar from Speed."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed - 3
        assert result.x == SPEED_X - 3
        assert result.y == SPEED_Y - 3

    def test_sub_with_non_numeric_returns_not_implemented(self):
        """Test subtraction with non-numeric type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = Speed.__sub__(speed, 'not a number')
        assert result is NotImplemented

    def test_sub_does_not_mutate_original(self):
        """Test that subtraction creates a new Speed and does not mutate the original."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        _result = speed - 1.0
        assert speed.x == SPEED_X
        assert speed.y == SPEED_Y


class TestSpeedMulNotImplemented:
    """Tests for __mul__ with non-numeric types."""

    def test_mul_with_non_numeric_returns_not_implemented(self):
        """Test multiplication with non-numeric type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = Speed.__mul__(speed, 'not a number')
        assert result is NotImplemented

    def test_mul_with_list_returns_not_implemented(self):
        """Test multiplication with list type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = Speed.__mul__(speed, [1, 2, 3])
        assert result is NotImplemented


class TestSpeedAdd:
    """Tests for __add__ (addition) operator."""

    def test_add_with_speed_object(self):
        """Test addition of two Speed objects."""
        speed_a = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        speed_b = Speed(x=OTHER_X, y=OTHER_Y, increment=SPEED_INCREMENT)
        result = speed_a + speed_b
        assert result.x == SPEED_X + OTHER_X
        assert result.y == SPEED_Y + OTHER_Y
        assert result.increment == SPEED_INCREMENT

    def test_add_with_float(self):
        """Test addition of a float scalar to Speed."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed + SCALAR_VALUE
        assert result.x == SPEED_X + SCALAR_VALUE
        assert result.y == SPEED_Y + SCALAR_VALUE
        assert result.increment == SPEED_INCREMENT

    def test_add_with_int(self):
        """Test addition of an integer scalar to Speed."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed + 3
        assert result.x == SPEED_X + 3
        assert result.y == SPEED_Y + 3

    def test_add_with_non_numeric_returns_not_implemented(self):
        """Test addition with non-numeric type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = Speed.__add__(speed, 'not a number')
        assert result is NotImplemented

    def test_add_does_not_mutate_original(self):
        """Test that addition creates a new Speed and does not mutate the original."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        _result = speed + 1.0
        assert speed.x == SPEED_X
        assert speed.y == SPEED_Y


class TestSpeedTruediv:
    """Tests for __truediv__ (true division) operator."""

    def test_truediv_with_float(self):
        """Test division of Speed by a float scalar."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed / SCALAR_VALUE
        assert result.x == SPEED_X / SCALAR_VALUE
        assert result.y == SPEED_Y / SCALAR_VALUE
        assert result.increment == SPEED_INCREMENT

    def test_truediv_with_int(self):
        """Test division of Speed by an integer scalar."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed / 2
        assert math.isclose(result.x, 5.0)
        assert math.isclose(result.y, 2.5)

    def test_truediv_by_zero_raises_error(self):
        """Test division of Speed by zero raises ZeroDivisionError."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        with pytest.raises(ZeroDivisionError, match='Cannot divide Speed by zero'):
            _result = speed / 0

    def test_truediv_with_non_numeric_returns_not_implemented(self):
        """Test division with non-numeric type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = Speed.__truediv__(speed, 'not a number')
        assert result is NotImplemented


class TestSpeedMod:
    """Tests for __mod__ (modulo) operator."""

    def test_mod_with_float(self):
        """Test modulo of Speed by a float scalar."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed % 3.0
        assert math.isclose(result.x, 1.0)
        assert math.isclose(result.y, 2.0)
        assert result.increment == SPEED_INCREMENT

    def test_mod_with_int(self):
        """Test modulo of Speed by an integer scalar."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed % 3
        assert math.isclose(result.x, 1.0)
        assert math.isclose(result.y, 2.0)

    def test_mod_by_zero_raises_error(self):
        """Test modulo of Speed by zero raises ZeroDivisionError."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        with pytest.raises(ZeroDivisionError, match='Cannot modulo Speed by zero'):
            _result = speed % 0

    def test_mod_with_non_numeric_returns_not_implemented(self):
        """Test modulo with non-numeric type returns NotImplemented."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = Speed.__mod__(speed, 'not a number')
        assert result is NotImplemented


class TestSpeedApplyDt:
    """Tests for apply_dt method."""

    def test_apply_dt_standard(self):
        """Test apply_dt with a standard delta time value."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed.apply_dt(DELTA_TIME)
        assert result.x == SPEED_X * DELTA_TIME
        assert result.y == SPEED_Y * DELTA_TIME
        assert result.increment == SPEED_INCREMENT

    def test_apply_dt_zero(self):
        """Test apply_dt with zero delta time."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed.apply_dt(0.0)
        assert math.isclose(result.x, 0.0, abs_tol=1e-9)
        assert math.isclose(result.y, 0.0, abs_tol=1e-9)

    def test_apply_dt_one_second(self):
        """Test apply_dt with one second delta time returns original speed values."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        result = speed.apply_dt(1.0)
        assert result.x == SPEED_X
        assert result.y == SPEED_Y

    def test_apply_dt_does_not_mutate_original(self):
        """Test that apply_dt creates a new Speed and does not mutate the original."""
        speed = Speed(x=SPEED_X, y=SPEED_Y, increment=SPEED_INCREMENT)
        _result = speed.apply_dt(DELTA_TIME)
        assert speed.x == SPEED_X
        assert speed.y == SPEED_Y
