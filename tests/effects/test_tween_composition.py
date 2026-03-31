"""Tests for TweenSequence and TweenGroup composition."""

from dataclasses import dataclass

from glitchygames.effects.tween import Tween, TweenGroup, TweenSequence


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


class TestTweenSequence:
    """Serial tween execution."""

    def test_runs_tweens_in_order(self):
        """Sequence runs first tween, then second."""
        target = SimpleTarget(value=0.0)
        sequence = TweenSequence(
            _make_tween(target, end_value=50.0, duration=0.5),
            _make_tween(target, end_value=100.0, duration=0.5, start_value=50.0),
        )
        sequence.update(0.5)  # First tween completes
        assert target.value == 50.0
        sequence.update(0.5)  # Second tween completes
        assert target.value == 100.0
        assert sequence.is_complete is True

    def test_not_complete_until_all_done(self):
        """Sequence is not complete until last tween finishes."""
        target = SimpleTarget(value=0.0)
        sequence = TweenSequence(
            _make_tween(target, end_value=50.0, duration=0.5),
            _make_tween(target, end_value=100.0, duration=0.5, start_value=50.0),
        )
        sequence.update(0.5)
        assert sequence.is_complete is False
        assert sequence.is_active is True

    def test_empty_sequence_is_complete(self):
        """Empty sequence is immediately complete."""
        sequence = TweenSequence()
        assert sequence.is_complete is True

    def test_cancel_stops_all(self):
        """Cancel stops the entire sequence."""
        target = SimpleTarget(value=0.0)
        sequence = TweenSequence(
            _make_tween(target, end_value=50.0, duration=1.0),
            _make_tween(target, end_value=100.0, duration=1.0, start_value=50.0),
        )
        sequence.update(0.3)
        sequence.cancel()
        assert sequence.is_complete is True
        assert sequence.is_active is False


class TestTweenGroup:
    """Parallel tween execution."""

    def test_runs_tweens_simultaneously(self):
        """Group updates all tweens at once."""
        target_x = SimpleTarget(value=0.0)
        target_y = SimpleTarget(value=0.0)
        group = TweenGroup(
            _make_tween(target_x, end_value=100.0, duration=1.0),
            _make_tween(target_y, end_value=200.0, duration=1.0),
        )
        group.update(0.5)
        assert target_x.value == 50.0
        assert target_y.value == 100.0

    def test_complete_when_all_done(self):
        """Group completes when ALL tweens finish."""
        target_fast = SimpleTarget(value=0.0)
        target_slow = SimpleTarget(value=0.0)
        group = TweenGroup(
            _make_tween(target_fast, end_value=100.0, duration=0.5),
            _make_tween(target_slow, end_value=100.0, duration=1.0),
        )
        group.update(0.5)
        assert group.is_complete is False  # slow tween still running
        group.update(0.5)
        assert group.is_complete is True

    def test_empty_group_is_complete(self):
        """Empty group is immediately complete."""
        group = TweenGroup()
        assert group.is_complete is True

    def test_cancel_stops_all(self):
        """Cancel stops all tweens in the group."""
        target = SimpleTarget(value=0.0)
        group = TweenGroup(
            _make_tween(target, end_value=100.0, duration=1.0),
        )
        group.update(0.3)
        group.cancel()
        assert group.is_complete is True
