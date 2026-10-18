"""Tests for the audio glitch diagnostics (BUGS.md #27)."""

import math
import sys
import threading

import numpy as np
import pytest

from glitchygames.audio import diagnostics
from glitchygames.audio.diagnostics import (
    EdgeReport,
    LockWaitReport,
    describe_edges,
    dropout_risk,
    find_discontinuities,
    find_silent_gaps,
    measure_lock_wait,
)

SAMPLE_RATE = 44100
BUFFER_SAMPLES = 512
BUFFER_MILLISECONDS = BUFFER_SAMPLES / SAMPLE_RATE * 1000.0  # 11.61 ms


def _sine(count=4000, frequency=220.0):
    return np.sin(2 * np.pi * frequency * np.arange(count) / SAMPLE_RATE) * 0.5


class TestFindSilentGaps:
    """Tests for find_silent_gaps."""

    def test_gap_inside_sound_is_reported_but_edges_are_not(self):
        samples = _sine()
        samples[:100] = 0.0  # Leading silence
        samples[-100:] = 0.0  # Trailing silence
        samples[1000:1040] = 0.0  # A real gap

        assert find_silent_gaps(samples) == [(1000, 40)]

    def test_gap_threshold_boundary(self):
        samples = _sine()
        samples[500:531] = 0.0  # 31 zeros
        samples[2000:2032] = 0.0  # 32 zeros

        assert find_silent_gaps(samples) == [(2000, 32)]

    def test_silence_only_has_no_gaps(self):
        assert find_silent_gaps(np.zeros(1000)) == []


class TestFindDiscontinuities:
    """Tests for find_discontinuities."""

    def test_clean_sine_has_none(self):
        assert find_discontinuities(_sine()) == []

    def test_injected_step_is_found(self):
        samples = _sine()
        samples[2000:] += 0.4

        found = find_discontinuities(samples)

        assert any(abs(index - 2000) <= 1 for index in found)


class TestDescribeEdges:
    """Tests for describe_edges."""

    def test_abrupt_cut_has_a_large_cut_ratio(self):
        samples = np.concatenate([_sine(), np.zeros(500)])

        report = describe_edges(samples)

        assert isinstance(report, EdgeReport)
        assert abs(report.cut_ratio) > 1.0

    def test_fade_has_a_small_cut_ratio(self):
        samples = _sine() * np.linspace(1.0, 0.0, 4000)
        samples = np.concatenate([samples, np.zeros(500)])

        report = describe_edges(samples)

        assert abs(report.cut_ratio) < 1.0


class TestDropoutRisk:
    """Tests for dropout_risk: the p99 wait against half the mixer buffer."""

    @staticmethod
    def _report(*, p99_milliseconds, maximum_milliseconds=None):
        return LockWaitReport(
            median_milliseconds=0.1,
            p99_milliseconds=p99_milliseconds,
            maximum_milliseconds=(
                p99_milliseconds if maximum_milliseconds is None else maximum_milliseconds
            ),
            sample_count=100,
        )

    def test_p99_exactly_half_the_buffer_is_a_risk(self):
        assert dropout_risk(self._report(p99_milliseconds=BUFFER_MILLISECONDS * 0.5)) is True

    def test_p99_just_below_half_the_buffer_is_safe(self):
        assert (
            dropout_risk(self._report(p99_milliseconds=BUFFER_MILLISECONDS * 0.5 - 0.01)) is False
        )

    def test_high_maximum_with_low_p99_is_safe(self):
        """OS scheduling noise can spike the maximum; only the p99 decides."""
        report = self._report(p99_milliseconds=2.0, maximum_milliseconds=50.0)

        assert dropout_risk(report) is False


class TestMeasureLockWait:
    """Tests for measure_lock_wait."""

    def test_restores_switch_interval_and_returns_samples(self):
        previous_interval = sys.getswitchinterval()

        report = measure_lock_wait(
            frames=10,
            target_fps=200.0,
            game_logic_seconds=0.001,
            switch_interval_seconds=0.0005,
        )

        assert math.isclose(sys.getswitchinterval(), previous_interval, rel_tol=1e-6)
        assert report.sample_count > 0
        assert report.maximum_milliseconds >= report.median_milliseconds >= 0.0

    def test_without_spin_yield_still_measures(self):
        previous_interval = sys.getswitchinterval()

        report = measure_lock_wait(
            frames=5,
            target_fps=200.0,
            game_logic_seconds=0.001,
            yield_in_spin=False,
        )

        assert report.sample_count > 0
        assert math.isclose(sys.getswitchinterval(), previous_interval, rel_tol=1e-6)

    def test_restores_interval_and_stops_thread_when_frame_loop_raises(self, mocker):
        previous_interval = sys.getswitchinterval()
        mocker.patch.object(diagnostics, 'busy_python_work', side_effect=RuntimeError('boom'))

        with pytest.raises(RuntimeError, match='boom'):
            measure_lock_wait(
                frames=3,
                target_fps=200.0,
                game_logic_seconds=0.001,
                switch_interval_seconds=0.0005,
            )

        assert math.isclose(sys.getswitchinterval(), previous_interval, rel_tol=1e-6)
        assert not any(thread.name == 'lock-wait-listener' for thread in threading.enumerate())
