"""Tests for glitchygames.movement module - Speed, Horizontal, Vertical."""

import pytest

from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.speed import Speed
from glitchygames.movement.vertical import Vertical


class TestSpeed:
    """Test Speed class arithmetic and utility methods."""

    def test_init_defaults(self):
        speed = Speed()
        assert speed.x == 0
        assert speed.y == 0
        assert speed.increment == pytest.approx(0.2)

    def test_init_custom(self):
        speed = Speed(x=100.0, y=50.0, increment=0.5)
        assert speed.x == pytest.approx(100.0)
        assert speed.y == pytest.approx(50.0)
        assert speed.increment == pytest.approx(0.5)

    def test_speed_up(self):
        speed = Speed(x=10.0, y=5.0, increment=1.0)
        speed.speed_up()
        assert speed.x == pytest.approx(11.0)
        assert speed.y == pytest.approx(6.0)

    def test_speed_up_horizontal_positive(self):
        speed = Speed(x=10.0, y=0.0, increment=2.0)
        speed.speed_up_horizontal()
        assert speed.x == pytest.approx(12.0)

    def test_speed_up_horizontal_negative(self):
        speed = Speed(x=-10.0, y=0.0, increment=2.0)
        speed.speed_up_horizontal()
        assert speed.x == pytest.approx(-12.0)

    def test_speed_up_vertical_positive(self):
        speed = Speed(x=0.0, y=10.0, increment=2.0)
        speed.speed_up_vertical()
        assert speed.y == pytest.approx(12.0)

    def test_speed_up_vertical_negative(self):
        speed = Speed(x=0.0, y=-10.0, increment=2.0)
        speed.speed_up_vertical()
        assert speed.y == pytest.approx(-12.0)

    def test_imul(self):
        speed = Speed(x=10.0, y=5.0)
        speed *= 2.0
        assert speed.x == pytest.approx(20.0)
        assert speed.y == pytest.approx(10.0)

    def test_mul(self):
        speed = Speed(x=10.0, y=5.0)
        result = speed * 3.0
        assert result.x == pytest.approx(30.0)
        assert result.y == pytest.approx(15.0)
        # Original unchanged
        assert speed.x == pytest.approx(10.0)

    def test_mul_not_implemented(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(TypeError):
            speed * 'invalid'  # type: ignore[operator]

    def test_add_speed(self):
        speed1 = Speed(x=10.0, y=5.0)
        speed2 = Speed(x=3.0, y=2.0)
        result = speed1 + speed2
        assert result.x == pytest.approx(13.0)
        assert result.y == pytest.approx(7.0)

    def test_add_scalar(self):
        speed = Speed(x=10.0, y=5.0)
        result = speed + 2.0
        assert result.x == pytest.approx(12.0)
        assert result.y == pytest.approx(7.0)

    def test_add_not_implemented(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(TypeError):
            speed + 'invalid'  # type: ignore[operator]

    def test_radd(self):
        speed = Speed(x=10.0, y=5.0)
        result = 3.0 + speed
        assert result == pytest.approx(8.0)  # 3.0 + speed.y

    def test_radd_not_implemented(self):
        speed = Speed(x=10.0, y=5.0)
        result = speed.__radd__('invalid')  # type: ignore[invalid-argument-type]
        assert result is NotImplemented

    def test_neg(self):
        speed = Speed(x=10.0, y=-5.0, increment=0.5)
        result = -speed
        assert result.x == pytest.approx(-10.0)
        assert result.y == pytest.approx(5.0)
        assert result.increment == pytest.approx(0.5)

    def test_sub_speed(self):
        speed1 = Speed(x=10.0, y=5.0)
        speed2 = Speed(x=3.0, y=2.0)
        result = speed1 - speed2
        assert result.x == pytest.approx(7.0)
        assert result.y == pytest.approx(3.0)

    def test_sub_scalar(self):
        speed = Speed(x=10.0, y=5.0)
        result = speed - 2.0
        assert result.x == pytest.approx(8.0)
        assert result.y == pytest.approx(3.0)

    def test_sub_not_implemented(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(TypeError):
            speed - 'invalid'  # type: ignore[operator]


class TestSpeedArithmetic:
    """Test Speed class division, modulo, and delta-time operations."""

    def test_truediv(self):
        speed = Speed(x=10.0, y=6.0)
        result = speed / 2.0
        assert result.x == pytest.approx(5.0)
        assert result.y == pytest.approx(3.0)

    def test_truediv_zero(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(ZeroDivisionError, match='Cannot divide Speed by zero'):
            _ = speed / 0

    def test_truediv_not_implemented(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(TypeError):
            speed / 'invalid'  # type: ignore[operator]

    def test_mod(self):
        speed = Speed(x=10.0, y=7.0)
        result = speed % 3.0
        assert result.x == pytest.approx(1.0)
        assert result.y == pytest.approx(1.0)

    def test_mod_zero(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(ZeroDivisionError, match='Cannot modulo Speed by zero'):
            _ = speed % 0

    def test_mod_not_implemented(self):
        speed = Speed(x=10.0, y=5.0)
        with pytest.raises(TypeError):
            speed % 'invalid'  # type: ignore[operator]

    def test_apply_dt(self):
        speed = Speed(x=100.0, y=50.0)
        result = speed.apply_dt(0.016)
        assert result.x == pytest.approx(1.6)
        assert result.y == pytest.approx(0.8)


class TestHorizontal:
    """Test Horizontal movement class."""

    def test_init(self):
        speed = Speed(x=100.0, y=50.0)
        horizontal = Horizontal(speed)
        assert horizontal.current_speed == pytest.approx(100.0)

    def test_left(self):
        speed = Speed(x=100.0, y=50.0)
        horizontal = Horizontal(speed)
        horizontal.left()
        assert horizontal.current_speed == pytest.approx(-100.0)

    def test_right(self):
        speed = Speed(x=100.0, y=50.0)
        horizontal = Horizontal(speed)
        horizontal.right()
        assert horizontal.current_speed == pytest.approx(100.0)

    def test_stop(self):
        speed = Speed(x=100.0, y=50.0)
        horizontal = Horizontal(speed)
        horizontal.left()
        horizontal.stop()
        assert horizontal.current_speed == 0

    def test_get_movement_with_dt(self):
        speed = Speed(x=100.0, y=50.0)
        horizontal = Horizontal(speed)
        movement = horizontal.get_movement_with_dt(0.016)
        assert movement == pytest.approx(1.6)


class TestVertical:
    """Test Vertical movement class."""

    def test_init(self):
        speed = Speed(x=100.0, y=50.0)
        vertical = Vertical(speed)
        assert vertical.current_speed == pytest.approx(50.0)

    def test_up(self):
        speed = Speed(x=100.0, y=50.0)
        vertical = Vertical(speed)
        vertical.up()
        assert vertical.current_speed == pytest.approx(-50.0)

    def test_down(self):
        speed = Speed(x=100.0, y=50.0)
        vertical = Vertical(speed)
        vertical.down()
        assert vertical.current_speed == pytest.approx(50.0)

    def test_stop(self):
        speed = Speed(x=100.0, y=50.0)
        vertical = Vertical(speed)
        vertical.up()
        vertical.stop()
        assert vertical.current_speed == 0

    def test_get_movement_with_dt(self):
        speed = Speed(x=100.0, y=200.0)
        vertical = Vertical(speed)
        movement = vertical.get_movement_with_dt(0.016)
        assert movement == pytest.approx(3.2)
