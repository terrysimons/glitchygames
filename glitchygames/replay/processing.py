"""Compare a replay's processing time with its recording's, frame by frame.

A recording made through the engine (``--record-trace``, ``--rebaseline``, the scripted
sessions) holds each frame's processing time (``processing_seconds``, a newest-first history
across rebaselines: glitchygames/recording_history.py; this module compares ``[0]``): the
frame's work
(logic, events, frame services, positioning and rendering), without presenting it, without
the doors' own ``end_frame`` (writing the recording, comparing the replay) and without the
pacing sleep. It is a diagnostic field: a replay never compares it and never serves it to the
game (it is measured with ``clock.measured_seconds``). The header's latest measurement run
(``measurement_runs[0]``) names the machine that measured them (``machine_description``, never
the host name).

``--replay-trace PATH --headless --compare-processing`` measures this machine's processing time
for every replayed frame the same way and reports how the two compare
(``ProcessingSummary.describe``), after the replay's own report. ``--max-processing-slowdown
PERCENT`` (which implies ``--compare-processing``) turns it into a check: a replay that matched
but whose total processing time exceeds the recording's by more than PERCENT exits
``ExitCode.PROCESSING_SLOWER``; a recording with no processing times cannot be checked
(``ExitCode.UNUSABLE_INPUT``). Live runs are paced and headless replays are not, so totals of
wall-clock time would not compare; processing times do. They only compare on the same machine
(CI against a baseline recorded on its hardware): the report says when the machines differ.

Pacing changes processing time too: between paced frames the processor idles and slows down,
so a live recording's frames take longer than the same work in an unpaced replay (a 330-frame
Clockwork Keep session measured about 65% faster replayed than recorded live, on one machine).
The latest measurement run says whether it paced its frames as recording began
(``processing_paced``: a live run with a target FPS, True; a ``--rebaseline``, a headless
replay, False). The fair baseline is a ``--rebaseline`` of the session made on the machine that
checks it: its times are measured unpaced, as a replay's are (the same session then compares
within about 1%). Comparing against a paced recording, the report says so.
"""

from __future__ import annotations

import platform
import statistics
from typing import Self

from pydantic import BaseModel, ConfigDict

# How many of the frames that grew most the report names
SLOWEST_FRAME_COUNT = 3
MILLISECONDS_PER_SECOND = 1000.0
PERCENT = 100.0


def machine_description() -> str:
    """Describe this machine for a recording's header: its system, version and architecture.

    Returns:
        ``platform.platform()``, e.g. ``macOS-27.0-arm64-arm-64bit`` (no host name: recordings
        are shared, and bundled demos ship in the wheel).

    """
    return platform.platform()


class SlowerFrame(BaseModel):
    """A frame the replay spent longer on than the recording did.

    Attributes:
        frame: The recording's frame index.
        extra_seconds: How much longer, in seconds.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    frame: int
    extra_seconds: float


class ProcessingSummary(BaseModel):
    """How a replay's processing time compared with its recording's.

    Attributes:
        frames_compared: Frames with both a recorded and a replayed time.
        frames_without_recorded_time: Replayed frames whose recording held no time.
        recorded_total_seconds: The compared frames' recorded processing time.
        replayed_total_seconds: The compared frames' processing time in this replay.
        recorded_median_seconds: The median recorded frame (None when nothing was compared).
        replayed_median_seconds: The median replayed frame (None when nothing was compared).
        slowest_frames: The frames that grew most, most first (only frames that grew).
        recorded_machine: The machine the recording's latest run names, or None.
        replay_machine: This machine.
        recorded_paced: Whether the recording's latest run paced its frames
            (``measurement_runs[0]``), or None when it does not say.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    frames_compared: int
    frames_without_recorded_time: int
    recorded_total_seconds: float
    replayed_total_seconds: float
    recorded_median_seconds: float | None
    replayed_median_seconds: float | None
    slowest_frames: tuple[SlowerFrame, ...]
    recorded_machine: str | None
    replay_machine: str
    recorded_paced: bool | None

    @property
    def change_percent(self: Self) -> float | None:
        """How much longer (positive) or shorter (negative) the replay took, in percent.

        None when nothing was compared, or the recorded total is zero.
        """
        if self.frames_compared == 0 or self.recorded_total_seconds <= 0.0:
            return None
        return (self.replayed_total_seconds / self.recorded_total_seconds - 1.0) * PERCENT

    def exceeds(self: Self, *, max_slowdown_percent: float) -> bool:
        """Report whether the replay took more than ``max_slowdown_percent`` longer.

        Args:
            max_slowdown_percent: The allowed slowdown, in percent.

        Returns:
            True when it did; False when it did not, or nothing was compared.

        """
        change_percent = self.change_percent
        return change_percent is not None and change_percent > max_slowdown_percent

    def describe(self: Self) -> str:
        """Describe the comparison on one line (printed after the replay's report).

        Returns:
            ``Processing: the replay took 14.2% longer than the recording (...)``, or why
            nothing was compared.

        """
        change_percent = self.change_percent
        if change_percent is None:
            return (
                'Processing: nothing to compare: the recording holds no processing times '
                f'({self.frames_without_recorded_time} frames replayed)'
            )
        if change_percent > 0:
            change = f'{change_percent:.1f}% longer than'
        elif change_percent < 0:
            change = f'{-change_percent:.1f}% less time than'
        else:
            change = 'the same time as'
        # Frames were compared (change_percent is not None), so both medians exist
        replayed_median_seconds = self.replayed_median_seconds
        recorded_median_seconds = self.recorded_median_seconds
        assert replayed_median_seconds is not None
        assert recorded_median_seconds is not None
        totals = (
            f'Processing: the replay took {change} the recording ({self.frames_compared} '
            f'frames: {self.replayed_total_seconds:.3f} s against '
            f'{self.recorded_total_seconds:.3f} s; median frame '
            f'{_milliseconds(replayed_median_seconds)} against '
            f'{_milliseconds(recorded_median_seconds)})'
        )
        parts = [totals]
        if self.slowest_frames:
            slowest = ', '.join(
                f'frame {frame.frame} +{frame.extra_seconds * MILLISECONDS_PER_SECOND:.3f} ms'
                for frame in self.slowest_frames
            )
            parts.append(f'slowest against the recording: {slowest}')
        if self.frames_without_recorded_time:
            count = self.frames_without_recorded_time
            parts.append(f'{count} frame{"" if count == 1 else "s"} had no recorded time')
        if self.recorded_machine is None:
            parts.append('the recording does not name its machine')
        elif self.recorded_machine != self.replay_machine:
            parts.append(
                f'recorded on {self.recorded_machine}, replayed on {self.replay_machine}: '
                'times from different machines do not compare'
            )
        if self.recorded_paced is True:
            parts.append(
                'the recording was measured in a paced run, which runs slower than an unpaced '
                'replay: compare against a --rebaseline of it made on this machine'
            )
        return '; '.join(parts)


class ProcessingComparison:
    """Collects each replayed frame's processing time beside the recorded one."""

    def __init__(
        self: Self,
        *,
        recorded_machine: str | None,
        replay_machine: str,
        recorded_paced: bool | None,
    ) -> None:
        """Start with no frames.

        Args:
            recorded_machine: The machine the recording's latest run names
                (``measurement_runs[0]``).
            replay_machine: This machine (``machine_description``).
            recorded_paced: Whether the recording's latest run paced its frames, or None when
                it does not say.

        """
        self._recorded_machine = recorded_machine
        self._replay_machine = replay_machine
        self._recorded_paced = recorded_paced
        # (frame index, recorded seconds, replayed seconds) of each compared frame
        self._frames: list[tuple[int, float, float]] = []
        self._frames_without_recorded_time = 0

    def add_frame(
        self: Self, *, frame_index: int, recorded_seconds: float | None, replayed_seconds: float
    ) -> None:
        """Add a replayed frame.

        Args:
            frame_index: The recording's frame index.
            recorded_seconds: Its recorded processing time, or None when the recording has none.
            replayed_seconds: Its processing time in this replay.

        """
        if recorded_seconds is None:
            self._frames_without_recorded_time += 1
            return
        self._frames.append((frame_index, recorded_seconds, replayed_seconds))

    def summary(self: Self) -> ProcessingSummary:
        """Return how the frames added so far compare.

        Returns:
            The summary.

        """
        recorded = [recorded_seconds for _frame, recorded_seconds, _replayed in self._frames]
        replayed = [replayed_seconds for _frame, _recorded, replayed_seconds in self._frames]
        grown = sorted(
            (
                SlowerFrame(frame=frame, extra_seconds=replayed_seconds - recorded_seconds)
                for frame, recorded_seconds, replayed_seconds in self._frames
                if replayed_seconds > recorded_seconds
            ),
            key=lambda slower_frame: slower_frame.extra_seconds,
            reverse=True,
        )
        return ProcessingSummary(
            frames_compared=len(self._frames),
            frames_without_recorded_time=self._frames_without_recorded_time,
            recorded_total_seconds=sum(recorded),
            replayed_total_seconds=sum(replayed),
            recorded_median_seconds=statistics.median(recorded) if recorded else None,
            replayed_median_seconds=statistics.median(replayed) if replayed else None,
            slowest_frames=tuple(grown[:SLOWEST_FRAME_COUNT]),
            recorded_machine=self._recorded_machine,
            replay_machine=self._replay_machine,
            recorded_paced=self._recorded_paced,
        )


def _milliseconds(seconds: float) -> str:
    """Format seconds as milliseconds for the report.

    Returns:
        ``3.100 ms``.

    """
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f} ms'
