"""Tests for TweenManager."""

from dataclasses import dataclass

import pytest

from glitchygames.effects.tween import Tween, TweenManager


@dataclass
class SimpleTarget:
    """Test target with a numeric property."""

    value: float = 0.0


def _make_tween(
    target: SimpleTarget,
    end_value: float,
    duration: float,
    start_value: float = 0.0,
) -> Tween:
    """Create a simple value tween for testing."""
    return Tween(
        target=target,
        property_name='value',
        end_value=end_value,
        duration=duration,
        start_value=start_value,
    )


class TestTweenManagerBasics:
    """Core TweenManager behavior."""

    def test_create_and_update_tween(self):
        """Manager creates tweens that update on manager.update()."""
        manager = TweenManager()
        target = SimpleTarget(value=0.0)
        manager.tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        manager.update(dt=0.5)
        assert target.value == pytest.approx(50.0)

    def test_tween_returns_instance(self):
        """Manager.tween() returns the created Tween."""
        manager = TweenManager()
        target = SimpleTarget(value=0.0)
        result = manager.tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
        )
        assert isinstance(result, Tween)

    def test_active_count(self):
        """active_count tracks the number of running tweens."""
        manager = TweenManager()
        target = SimpleTarget(value=0.0)
        assert manager.active_count == 0
        manager.tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
        )
        assert manager.active_count == 1

    def test_completed_tweens_removed(self):
        """Completed tweens are removed from the active list."""
        manager = TweenManager()
        target = SimpleTarget(value=0.0)
        manager.tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=0.5,
            start_value=0.0,
        )
        assert manager.active_count == 1
        manager.update(dt=0.5)
        assert manager.active_count == 0

    def test_multiple_tweens(self):
        """Manager handles multiple simultaneous tweens."""
        manager = TweenManager()
        target_a = SimpleTarget(value=0.0)
        target_b = SimpleTarget(value=0.0)
        manager.tween(
            target=target_a,
            property_name='value',
            end_value=100.0,
            duration=1.0,
            start_value=0.0,
        )
        manager.tween(
            target=target_b,
            property_name='value',
            end_value=200.0,
            duration=1.0,
            start_value=0.0,
        )
        manager.update(dt=0.5)
        assert target_a.value == pytest.approx(50.0)
        assert target_b.value == pytest.approx(100.0)


class TestTweenManagerCancel:
    """TweenManager cancellation behavior."""

    def test_cancel_all(self):
        """cancel_all() stops and removes all tweens."""
        manager = TweenManager()
        target = SimpleTarget(value=0.0)
        manager.tween(
            target=target,
            property_name='value',
            end_value=100.0,
            duration=1.0,
        )
        manager.tween(
            target=target,
            property_name='value',
            end_value=200.0,
            duration=2.0,
        )
        manager.cancel_all()
        assert manager.active_count == 0

    def test_cancel_by_target(self):
        """cancel_all(target) only cancels tweens on that target."""
        manager = TweenManager()
        target_a = SimpleTarget(value=0.0)
        target_b = SimpleTarget(value=0.0)
        manager.tween(
            target=target_a,
            property_name='value',
            end_value=100.0,
            duration=1.0,
        )
        manager.tween(
            target=target_b,
            property_name='value',
            end_value=200.0,
            duration=1.0,
        )
        manager.cancel_all(target=target_a)
        # target_b's tween should still update
        manager.update(dt=0.5)
        assert target_b.value == pytest.approx(100.0)


class TestTweenManagerComposition:
    """Manager sequence and group creation."""

    def test_sequence_creation(self):
        """Manager.sequence() creates and registers a sequence."""
        manager = TweenManager()
        target = SimpleTarget(value=0.0)
        sequence = manager.sequence(
            _make_tween(target, end_value=50.0, duration=0.5),
            _make_tween(target, end_value=100.0, duration=0.5, start_value=50.0),
        )
        assert manager.active_count == 1
        assert sequence.is_active is True

    def test_group_creation(self):
        """Manager.group() creates and registers a group."""
        manager = TweenManager()
        target_a = SimpleTarget(value=0.0)
        target_b = SimpleTarget(value=0.0)
        group = manager.group(
            _make_tween(target_a, end_value=100.0, duration=1.0),
            _make_tween(target_b, end_value=200.0, duration=1.0),
        )
        assert manager.active_count == 1
        assert group.is_active is True
        manager.update(dt=1.0)
        assert target_a.value == pytest.approx(100.0)
        assert target_b.value == pytest.approx(200.0)
        assert manager.active_count == 0
