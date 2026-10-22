"""The processing-time comparison of a replay with its recording (replay/processing.py)."""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING

import pytest

from glitchygames.replay.processing import (
    SLOWEST_FRAME_COUNT,
    ProcessingComparison,
    machine_description,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

MACHINE = 'macOS-27.0-arm64-arm-64bit'
OTHER_MACHINE = 'Linux-6.8-x86_64-with-glibc2.39'


def compared(
    frames: Sequence[tuple[float | None, float]],
    *,
    recorded_machine: str | None = MACHINE,
    recorded_paced: bool | None = False,
) -> ProcessingComparison:
    """Return a comparison of (recorded, replayed) seconds, one pair per frame.

    Returns:
        The comparison.

    """
    comparison = ProcessingComparison(
        recorded_machine=recorded_machine, replay_machine=MACHINE, recorded_paced=recorded_paced
    )
    for frame_index, (recorded_seconds, replayed_seconds) in enumerate(frames):
        comparison.add_frame(
            frame_index=frame_index,
            recorded_seconds=recorded_seconds,
            replayed_seconds=replayed_seconds,
        )
    return comparison


class TestTheSummary:
    """Totals, medians and the frames that grew most."""

    def test_a_slower_replay_is_reported_with_its_totals_medians_and_slowest_frames(self):
        summary = compared([(0.002, 0.003), (0.004, 0.004), (0.002, 0.007), (0.004, 0.004)])
        summary = summary.summary()
        assert summary.frames_compared == 4
        assert summary.recorded_total_seconds == pytest.approx(0.012)
        assert summary.replayed_total_seconds == pytest.approx(0.018)
        assert summary.change_percent == pytest.approx(50.0)
        assert summary.recorded_median_seconds == pytest.approx(0.003)
        assert summary.replayed_median_seconds == pytest.approx(0.004)
        assert [frame.frame for frame in summary.slowest_frames] == [2, 0]
        assert summary.slowest_frames[0].extra_seconds == pytest.approx(0.005)
        assert summary.describe() == (
            'Processing: the replay took 50.0% longer than the recording (4 frames: 0.018 s '
            'against 0.012 s; median frame 4.000 ms against 3.000 ms); slowest against the '
            'recording: frame 2 +5.000 ms, frame 0 +1.000 ms'
        )

    def test_a_faster_replay_says_less_time_and_names_no_slower_frames(self):
        summary = compared([(0.004, 0.002), (0.004, 0.003)]).summary()
        assert summary.change_percent == pytest.approx(-37.5)
        assert summary.slowest_frames == ()
        assert summary.describe().startswith(
            'Processing: the replay took 37.5% less time than the recording (2 frames:'
        )

    def test_only_the_slowest_few_frames_are_named(self):
        frames = [(0.001, 0.001 + 0.0001 * index) for index in range(1, 10)]
        summary = compared(frames).summary()
        assert len(summary.slowest_frames) == SLOWEST_FRAME_COUNT
        assert summary.slowest_frames[0].frame == len(frames) - 1

    def test_frames_without_a_recorded_time_are_counted_not_compared(self):
        summary = compared([(None, 0.5), (0.002, 0.002)]).summary()
        assert summary.frames_compared == 1
        assert summary.frames_without_recorded_time == 1
        assert summary.replayed_total_seconds == pytest.approx(0.002)
        assert summary.describe().endswith('; 1 frame had no recorded time')

    def test_a_recording_with_no_times_compares_nothing(self):
        summary = compared([(None, 0.002), (None, 0.003)]).summary()
        assert summary.frames_compared == 0
        assert summary.change_percent is None
        assert summary.describe() == (
            'Processing: nothing to compare: the recording holds no processing times '
            '(2 frames replayed)'
        )


class TestTheMachines:
    """Times from different machines do not compare, and the report says so."""

    def test_another_machine_is_named(self):
        summary = compared([(0.002, 0.002)], recorded_machine=OTHER_MACHINE).summary()
        assert summary.describe().endswith(
            f'; recorded on {OTHER_MACHINE}, replayed on {MACHINE}: times from different '
            'machines do not compare'
        )

    def test_a_recording_that_names_no_machine_is_said_so(self):
        summary = compared([(0.002, 0.002)], recorded_machine=None).summary()
        assert summary.describe().endswith('; the recording does not name its machine')

    def test_the_machine_description_names_no_host(self):
        description = machine_description()
        assert description
        assert platform.node() not in description


class TestPacedRecordings:
    """A live run paces its frames, and paced frames run slower than an unpaced replay's."""

    def test_a_paced_recording_is_said_to_be_no_fair_baseline(self):
        summary = compared([(0.006, 0.002)], recorded_paced=True).summary()
        assert summary.describe().endswith(
            '; the recording was measured in a paced run, which runs slower than an unpaced '
            'replay: compare against a --rebaseline of it made on this machine'
        )

    @pytest.mark.parametrize('recorded_paced', [False, None])
    def test_an_unpaced_or_unknown_recording_gets_no_note(self, recorded_paced):
        summary = compared([(0.002, 0.002)], recorded_paced=recorded_paced).summary()
        assert 'paced' not in summary.describe()


class TestTheAllowedSlowdown:
    """--max-processing-slowdown PERCENT: more than that is a failed check."""

    @pytest.mark.parametrize(
        ('replayed_seconds', 'exceeds'),
        [(0.0110, False), (0.0111, True), (0.009, False)],
    )
    def test_the_slowdown_is_checked_against_the_percentage(self, replayed_seconds, exceeds):
        summary = compared([(0.010, replayed_seconds)]).summary()
        assert summary.exceeds(max_slowdown_percent=10.0) is exceeds

    def test_nothing_compared_never_exceeds(self):
        """The engine refuses that case itself (UNUSABLE_INPUT): there is nothing to check."""
        summary = compared([(None, 0.5)]).summary()
        assert summary.exceeds(max_slowdown_percent=0.0) is False
