"""Tests for Tween class."""

from dataclasses import dataclass, field

import pytest

from glitchygames.effects.tween import REPEAT_INFINITE, Tween


@dataclass
class SimpleTarget:
    """Test target with a numeric property."""

    value: float = 0.0


@dataclass
class DirtyTarget:
    """Test target with a dirty flag (simulates a sprite)."""

    value: float = 0.0
    dirty: int = field(default=0)


class TestTweenBasics:
    """Core tween interpolation behavior."""

    def test_linear_interpolation(self):
        """Tween linearly interpolates from start to end."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        tween.update(0.5)
        assert target.value == pytest.approx(50.0)

    def test_completes_at_duration(self):
        """Tween reaches end value and reports complete after duration."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        is_done = tween.update(1.0)
        assert is_done is True
        assert target.value == pytest.approx(100.0)
        assert tween.is_complete is True

    def test_not_complete_before_duration(self):
        """Tween is not complete before duration elapses."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        is_done = tween.update(0.5)
        assert is_done is False
        assert tween.is_complete is False
        assert tween.is_active is True

    def test_auto_start_value_from_current(self):
        """When start_value is None, uses current property value."""
        target = SimpleTarget(value=25.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=75.0,
            duration=1.0,
        )
        tween.update(0.5)
        assert target.value == pytest.approx(50.0)

    def test_easing_applied(self):
        """Non-linear easing produces different midpoint values."""
        target_linear = SimpleTarget(value=0.0)
        target_quad = SimpleTarget(value=0.0)
        tween_linear = Tween(
            target=target_linear,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
            easing='linear',
        )
        tween_quad = Tween(
            target=target_quad,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
            easing='ease_in_quad',
        )
        tween_linear.update(0.5)
        tween_quad.update(0.5)
        # ease_in_quad at 0.5 = 0.25, so value = 25.0
        assert target_linear.value == pytest.approx(50.0)
        assert target_quad.value == pytest.approx(25.0)

    def test_multiple_updates_accumulate(self):
        """Multiple small dt updates accumulate correctly despite float precision."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        # 0.1 is not exactly representable in IEEE 754, so 10 * 0.1 != 1.0.
        # The tween should still complete thanks to >= comparison on elapsed.
        for _ in range(10):
            tween.update(0.1)
        assert target.value == pytest.approx(100.0)
        assert tween.is_complete is True


class TestTweenDelay:
    """Tween delay behavior."""

    def test_delay_prevents_start(self):
        """Tween doesn't change value during delay period."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
            delay=0.5,
        )
        tween.update(0.3)
        assert target.value == pytest.approx(0.0)

    def test_delay_then_starts(self):
        """Tween begins after delay elapses."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
            delay=0.5,
        )
        tween.update(0.5)  # Delay consumed
        tween.update(0.5)  # Half of tween duration
        assert target.value == pytest.approx(50.0)


class TestTweenRepeat:
    """Tween repeat and ping-pong behavior."""

    def test_repeat_once(self):
        """Tween with repeat=1 plays twice total."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=0.5,
            start_value=0.0,
            repeat=1,
        )
        tween.update(0.5)  # First iteration complete
        assert tween.is_complete is False  # Still has one repeat
        tween.update(0.5)  # Second iteration complete
        assert tween.is_complete is True

    def test_infinite_repeat(self):
        """Tween with REPEAT_INFINITE never completes."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=0.1,
            start_value=0.0,
            repeat=REPEAT_INFINITE,
        )
        for _ in range(100):
            tween.update(0.1)
        assert tween.is_complete is False
        assert tween.is_active is True

    def test_ping_pong_reverses(self):
        """Ping-pong reverses direction on each repeat."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
            repeat=1,
            ping_pong=True,
        )
        tween.update(1.0)  # Forward complete: value = 100
        assert target.value == pytest.approx(100.0)
        tween.update(0.5)  # Reverse halfway: value = 50
        assert target.value == pytest.approx(50.0)
        tween.update(0.5)  # Reverse complete: value = 0
        assert target.value == pytest.approx(0.0)
        assert tween.is_complete is True


class TestTweenCallbacks:
    """Tween on_complete callback behavior."""

    def test_on_complete_fires(self):
        """on_complete is called when tween finishes."""
        called = [False]

        def callback():
            called[0] = True

        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=0.5,
            start_value=0.0,
            on_complete=callback,
        )
        tween.update(0.5)
        assert called[0] is True

    def test_on_complete_not_called_on_cancel(self):
        """on_complete is NOT called when tween is cancelled."""
        called = [False]

        def callback():
            called[0] = True

        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
            on_complete=callback,
        )
        tween.update(0.3)
        tween.cancel()
        assert called[0] is False
        assert tween.is_active is False


class TestTweenCancel:
    """Tween cancellation behavior."""

    def test_cancel_stops_updates(self):
        """Cancelled tween stops updating the property."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        tween.update(0.3)
        value_at_cancel = target.value
        tween.cancel()
        tween.update(0.5)  # Should have no effect
        assert target.value == pytest.approx(value_at_cancel)


class TestTweenDirtyFlag:
    """Dirty flag integration for sprite rendering."""

    def test_marks_target_dirty(self):
        """Tween sets dirty=1 on targets that have a dirty attribute."""
        target = DirtyTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        tween.update(0.1)
        assert target.dirty == 1

    def test_no_error_without_dirty(self):
        """Tween works fine on targets without dirty attribute."""
        target = SimpleTarget(value=0.0)
        tween = Tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        tween.update(0.1)  # Should not raise
        assert target.value > 0.0
