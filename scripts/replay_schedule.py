"""Simulate a watched replay's schedule: which recorded frames each viewer tick runs and shows.

A watched replay (glitchygames/replay/viewer.py, whose module docstring is the contract) runs
recorded frames from an accumulator: each 60 Hz outer tick owes the inner game one tick of real
time (times the speed), and the tick runs recorded frames while the accumulator holds their
recorded durations, presenting only the last one it ran. So a tick that runs two frames never
presents the first. Up to 1x a tick runs a second frame only when the replay is genuinely
behind (rule 2), so short frames (pacing catching up after a slow one) no longer hide a frame;
a recording made faster than 60 FPS, or any replay above 1x, still runs several a tick.

This drives the viewer's REAL accumulator (``ReplayViewer.accrue`` and
``ReplayViewer.should_run_inner_frame``, with their constants), never a copy of it, on an ideal
clock: every tick exactly ``CONTROL_TICK_SECONDS`` after the last, inner frames costing no time
(so the tick's real-time budget is never spent). It checks the viewer's schedule rule, not real
wake-up jitter: a real viewer's ticks wake a little early or late, and it counts a tick within
``TICK_SNAP_WINDOW_SECONDS`` of one period as exactly one period (the error carried), which an
ideal clock never needs. The viewer is ticked as a browser ticks it
(``ticks_externally``: it never sleeps); its accumulator is the same. The run is modelled as a
watched replay runs: the start screen lets frame 0 run first, Space is pressed on the next tick
(as tests/replay/tools/test_compare_trace.py's ``watched_replay`` presses it while the viewer
waits), and the inner game runs on to the end of the recording. Each inner frame lasts its
next frame's recorded dt (the last frame its own), as ``ReplaySources._inner_frame_seconds``
gives them (glitchygames/replay/driver.py, rule 4).

A frame is never presented when a later frame ran in the same tick. A frame may go unshown only
when the replay was genuinely behind: it is hidden (a failure) when the extra frame right after
it in that tick ran while the replay was NOT behind. The tool decides behind itself, from the
schedule and its own constant, never from the viewer's helper (which rule 2's limit is built on,
so a broken helper would hide frames and call them behind): the inner time owed before a frame
(the viewer's accumulator after allowing it, plus its duration) is at least the frame's duration
plus a whole tick of inner time (the speed times ``CONTROL_TICK_SECONDS``). The viewer's own
report (``ReplayViewer.last_inner_frame_ran_behind``) is a cross-check: a frame it disagrees on
is a failure too. Otherwise a frame not presented is skipped by design: a recording faster than
the tick, a stall's catch-up, the 60.01 FPS rate mismatch. Above 1x no frame is hidden:
fast-forward runs several frames a tick by design, and their extra frames are not behind by that
condition (a tick owes speed times a tick), so frames not presented are reported as skipped and
the recording passes. The last frame is presented by the tick that runs it; a recording that
quits in its last frame ends the real run there, so that frame is not shown in a real replay,
which this does not model. Frame 0 runs behind the start screen's message.

Output per recording: each tick's time, the frames it ran and the accumulator after it; the
hidden frames and the ones skipped by design; every frame's recorded dt in milliseconds.
``--summary`` prints one line per recording instead: its name, frame count, hidden and skipped
frames and shortest and longest dt.

Exit codes (glitchygames/exit_codes.py): ``SUCCESS`` when no recording hides a frame;
``REPLAY_DIVERGED`` when some frame is hidden or the viewer disagrees on behind (the watched
replay's sequence of shown frames differs from the recording's: the replay check's failure, not
an engine error, and no other member names a failed check of a recording); ``MISSING_INPUT`` for
a recording that does not exist; ``UNUSABLE_INPUT`` for one that cannot be read (not a trace, a
directory, no frames, a frame without a numeric dt). Every recording is reported; the exit code
is the first failure's. A speed outside the viewer's range is argparse's usage error.

Usage:
    uv run python -m scripts.replay_schedule PATH [PATH ...] [--speed X] [--summary]
"""

from __future__ import annotations

import argparse
import functools
import sys
from pathlib import Path
from typing import Self

import pygame
from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.recording import DT_FIELD
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, ReplayControls
from glitchygames.replay.viewer import ReplayViewer
from glitchygames.tracing import FRAMES_FIELD, TraceFormatError, read_trace_result

MILLISECONDS_PER_SECOND = 1000.0
# The owed time before a frame is read back as the accumulator after it plus its duration, which
# may round by a few ulps: within this of the behind threshold the tool counts the frame behind,
# and never counts a disagreement with the viewer's report
BEHIND_TOLERANCE_SECONDS = 1e-9


class UnusableRecordingError(ValueError):
    """A recording this tool cannot simulate (no frames, or a frame without a numeric dt)."""


class ScheduledTick(BaseModel):
    """One outer tick of the simulated watched replay.

    Attributes:
        tick_index: The tick's number (0 is the first, at the start screen).
        seconds: The tick's time on the ideal clock.
        frames_run: The recorded frames it ran, in order (it presents the last).
        owed_before_seconds: For each frame run, the inner time the viewer owed just before
            it ran (its accumulator after allowing the frame, plus the frame's duration): what
            the tool's own behind condition reads (``RecordingSchedule.ran_behind``).
        viewer_reported_behind: For each frame run, the viewer's own report of whether it ran
            behind (``ReplayViewer.last_inner_frame_ran_behind``), kept only as a cross-check
            (``RecordingSchedule.behind_disagreements``).
        accumulated_seconds: The accumulator after the tick.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    tick_index: int
    seconds: float
    frames_run: tuple[int, ...]
    owed_before_seconds: tuple[float, ...]
    viewer_reported_behind: tuple[bool, ...]
    accumulated_seconds: float


class RecordingSchedule(BaseModel):
    """A recording's simulated watched replay.

    Attributes:
        frame_seconds: Every frame's recorded dt, in seconds.
        speed: The replay speed simulated.
        ticks: Every outer tick, until the one that ran the last frame.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    frame_seconds: tuple[float, ...]
    speed: float
    ticks: tuple[ScheduledTick, ...]

    @property
    def never_presented(self: Self) -> tuple[int, ...]:
        """The frames that ran in a tick where a later frame ran too, in order."""
        return tuple(frame for tick in self.ticks for frame in tick.frames_run[:-1])

    def duration_seconds(self: Self, *, frame: int) -> float:
        """Return how long a frame lasted when recorded (its next frame's dt; rule 4).

        Returns:
            Seconds.

        """
        return inner_frame_seconds(frame_seconds=self.frame_seconds, frame_index=frame)

    def _behind_threshold_seconds(self: Self, *, frame: int) -> float:
        """Return what the replay must owe before a frame to be behind: the frame plus a tick.

        The tool's own condition, written here and never taken from the viewer: the frame's
        recorded duration plus a whole tick of inner time (the speed times
        ``CONTROL_TICK_SECONDS``).

        Returns:
            Seconds.

        """
        return self.duration_seconds(frame=frame) + self.speed * CONTROL_TICK_SECONDS

    def _frames_with_owed(self: Self) -> list[tuple[int, float, bool]]:
        """Return every frame run with the inner time owed before it and the viewer's report.

        Returns:
            ``(frame, owed seconds, viewer reported behind)``, in order.

        """
        return [
            entry
            for tick in self.ticks
            for entry in zip(
                tick.frames_run,
                tick.owed_before_seconds,
                tick.viewer_reported_behind,
                strict=True,
            )
        ]

    def ran_behind(self: Self, *, frame: int) -> bool:
        """Whether a frame ran while the replay was behind, by the tool's own condition.

        Behind: the inner time owed before it is at least the frame plus a tick of inner time
        (``BEHIND_TOLERANCE_SECONDS`` absorbs the rounding of reading the owed time back).

        Returns:
            True when behind; False for a frame that never ran.

        """
        owed_seconds = self._owed_before_by_frame.get(frame)
        if owed_seconds is None:
            return False
        return self._owes_beyond_a_tick(frame=frame, owed_seconds=owed_seconds)

    @functools.cached_property
    def _owed_before_by_frame(self: Self) -> dict[int, float]:
        """The inner time owed before each frame run, by frame (read once).

        Returns:
            Seconds by frame.

        """
        return {frame: owed_seconds for frame, owed_seconds, _ in self._frames_with_owed()}

    def _owes_beyond_a_tick(self: Self, *, frame: int, owed_seconds: float) -> bool:
        """The tool's behind condition for a frame owing ``owed_seconds`` before it ran.

        Returns:
            True when behind.

        """
        threshold_seconds = self._behind_threshold_seconds(frame=frame)
        return owed_seconds >= threshold_seconds - BEHIND_TOLERANCE_SECONDS

    @property
    def behind_disagreements(self: Self) -> tuple[int, ...]:
        """The frames the viewer's own behind report disagrees on with the tool's (a failure).

        Frames owing within ``BEHIND_TOLERANCE_SECONDS`` of the threshold are left out (the
        owed time read back may round either way there).
        """
        return tuple(
            frame
            for frame, owed_seconds, viewer_reported in self._frames_with_owed()
            if viewer_reported != self._owes_beyond_a_tick(frame=frame, owed_seconds=owed_seconds)
            and abs(owed_seconds - self._behind_threshold_seconds(frame=frame))
            > BEHIND_TOLERANCE_SECONDS
        )

    @property
    def hidden(self: Self) -> tuple[int, ...]:
        """The frames never presented that the replay hid while not behind (a failure).

        A frame is never presented when a later frame ran in the same tick; it is hidden when
        the frame right after it in that tick (the extra frame that hid it) ran while the replay
        was NOT behind, by the tool's own condition (``ran_behind``). Up to 1x only: above it a
        tick runs several frames by design (fast-forward presents the last), and those extra
        frames are not behind by that condition, so none counts.
        """
        if self.speed > 1:
            return ()
        hidden_frames: list[int] = []
        for tick in self.ticks:
            for frame, extra_frame, extra_owed_seconds in zip(
                tick.frames_run[:-1],
                tick.frames_run[1:],
                tick.owed_before_seconds[1:],
                strict=True,
            ):
                if not self._owes_beyond_a_tick(frame=extra_frame, owed_seconds=extra_owed_seconds):
                    hidden_frames.append(frame)
        return tuple(hidden_frames)

    @property
    def skipped_by_design(self: Self) -> tuple[int, ...]:
        """The frames never presented that are not hidden (expected, never a failure).

        The replay was behind when the extra frame ran (a recording faster than the tick, a
        stall's catch-up, the 60.01 FPS rate mismatch), or the speed is above 1x.
        """
        hidden = set(self.hidden)
        return tuple(frame for frame in self.never_presented if frame not in hidden)

    @property
    def fails(self: Self) -> bool:
        """True when a frame is hidden or the viewer disagrees on whether one ran behind."""
        return bool(self.hidden or self.behind_disagreements)


class IdealClock:
    """The viewer's measured clock in the simulation: moved by hand, a tick at a time."""

    def __init__(self: Self) -> None:
        """Start at 0 seconds."""
        self.seconds = 0.0

    def read(self: Self) -> float:
        """Return the clock's time.

        Returns:
            Seconds.

        """
        return self.seconds


def recorded_frame_seconds(*, path: Path) -> tuple[float, ...]:
    """Read every frame's recorded dt.

    Args:
        path: The recording.

    Returns:
        Seconds, one per frame.

    Raises:
        UnusableRecordingError: The recording has no frames, or a frame has no numeric dt.

    """
    frames = read_trace_result(path=path, share_records=True).trace[FRAMES_FIELD]
    if not frames:
        message = f'{path.as_posix()}: the recording holds no frames'
        raise UnusableRecordingError(message)
    frame_seconds: list[float] = []
    for frame_index, frame in enumerate(frames):
        dt = frame.get(DT_FIELD)
        if isinstance(dt, bool) or not isinstance(dt, int | float):
            message = f'{path.as_posix()}: frame {frame_index} has no numeric {DT_FIELD}'
            raise UnusableRecordingError(message)
        frame_seconds.append(float(dt))
    return tuple(frame_seconds)


def inner_frame_seconds(*, frame_seconds: tuple[float, ...], frame_index: int) -> float:
    """Return how long an inner frame lasted when recorded, as the replay driver gives it.

    The same rule as ``ReplaySources._inner_frame_seconds`` (glitchygames/replay/driver.py,
    rule 4): a frame lasts its next frame's dt, the last frame its own; 0.0 past the end.

    Args:
        frame_seconds: Every frame's recorded dt.
        frame_index: The frame that would run.

    Returns:
        Seconds.

    """
    for index in (frame_index + 1, frame_index):
        if index < len(frame_seconds):
            return frame_seconds[index]
    return 0.0


def simulate_schedule(*, frame_seconds: tuple[float, ...], speed: float) -> RecordingSchedule:
    """Run the viewer's accumulator over a recording's frame times on the ideal clock.

    Args:
        frame_seconds: Every frame's recorded dt.
        speed: The replay speed.

    Returns:
        The schedule.

    """
    ideal_clock = IdealClock()
    frame_count = len(frame_seconds)
    controls = ReplayControls(total_frames=frame_count, awaiting_start=True)
    controls.speed = speed
    viewer = ReplayViewer(controls=controls, measured_seconds=ideal_clock.read)
    viewer.ticks_externally = True
    frame_index = 0
    ticks: list[ScheduledTick] = []
    while True:
        # Ticked externally, the viewer never waits, so how it would wait does not matter
        now = viewer.begin_tick(is_inner_running=False)
        # Every tick before closed (should_run_inner_frame returned False), so one opens
        assert now is not None
        if controls.awaiting_start and frame_index > 0:
            # Frame 0 ran behind the start screen: Space starts the replay
            viewer.queue_key_event(event_type=pygame.KEYDOWN, key=pygame.K_SPACE)
            viewer.queue_key_event(event_type=pygame.KEYUP, key=pygame.K_SPACE)
        viewer.apply_key_events(now=now)
        viewer.accrue(
            now=now,
            is_inner_running=frame_index < frame_count
            and not (controls.awaiting_start or controls.paused),
        )
        frames_run: list[int] = []
        owed_before_seconds: list[float] = []
        viewer_reported_behind: list[bool] = []
        while viewer.should_run_inner_frame(
            inner_frame_seconds=inner_frame_seconds(
                frame_seconds=frame_seconds, frame_index=frame_index
            ),
            is_inner_over=frame_index >= frame_count,
            is_first_inner_frame=frame_index == 0,
        ):
            frames_run.append(frame_index)
            owed_before_seconds.append(
                viewer.accumulated_seconds
                + inner_frame_seconds(frame_seconds=frame_seconds, frame_index=frame_index)
            )
            viewer_reported_behind.append(viewer.last_inner_frame_ran_behind)
            frame_index += 1
        ticks.append(
            ScheduledTick(
                tick_index=len(ticks),
                seconds=now,
                frames_run=tuple(frames_run),
                owed_before_seconds=tuple(owed_before_seconds),
                viewer_reported_behind=tuple(viewer_reported_behind),
                accumulated_seconds=viewer.accumulated_seconds,
            )
        )
        if frame_index >= frame_count:
            return RecordingSchedule(frame_seconds=frame_seconds, speed=speed, ticks=tuple(ticks))
        ideal_clock.seconds += CONTROL_TICK_SECONDS


def milliseconds(*, seconds: float) -> str:
    """Return seconds as milliseconds with two decimals.

    Returns:
        For example ``'16.67 ms'``.

    """
    return f'{seconds * MILLISECONDS_PER_SECOND:.2f} ms'


def frame_list(*, frames: tuple[int, ...]) -> str:
    """Return frame numbers as a comma-separated list.

    Returns:
        ``'1, 3, 5'``, or ``'none'``.

    """
    return ', '.join(str(frame) for frame in frames) if frames else 'none'


def summary_line(*, name: str, schedule: RecordingSchedule) -> str:
    """Return a recording's one-line summary.

    Returns:
        Name, frame count, never-presented frames, shortest and longest dt.

    """
    return (
        f'{name}: {len(schedule.frame_seconds)} frames, '
        f'hidden: {frame_list(frames=schedule.hidden)}, '
        f'skipped by design: {frame_list(frames=schedule.skipped_by_design)}, '
        f'dt min {milliseconds(seconds=min(schedule.frame_seconds))} '
        f'max {milliseconds(seconds=max(schedule.frame_seconds))}'
        f'{disagreement_note(schedule=schedule)}'
    )


def disagreement_note(*, schedule: RecordingSchedule) -> str:
    """Return the frames the viewer's behind report disagrees on, for the summary line.

    Returns:
        ``', viewer disagrees on behind: 5, 6'``, or nothing when it agrees on every frame.

    """
    disagreements = schedule.behind_disagreements
    if not disagreements:
        return ''
    return f', viewer disagrees on behind: {frame_list(frames=disagreements)}'


def behind_note(*, schedule: RecordingSchedule, tick: ScheduledTick) -> str:
    """Return the frames a tick ran while the replay was behind, for its detail line.

    Returns:
        ``'; behind: 5, 6'`` (the tool's own condition), or nothing when none did.

    """
    behind_frames = tuple(frame for frame in tick.frames_run if schedule.ran_behind(frame=frame))
    return f'; behind: {frame_list(frames=behind_frames)}' if behind_frames else ''


def detail_lines(*, name: str, schedule: RecordingSchedule) -> list[str]:
    """Return a recording's full schedule.

    Returns:
        The heading, each tick, the never-presented frames, then every frame's recorded dt.

    """
    lines = [f'{name}: {len(schedule.frame_seconds)} frames at {schedule.speed:g}x']
    lines.extend(
        f'  tick {tick.tick_index} ({milliseconds(seconds=tick.seconds)}): '
        f'ran {", ".join(str(frame) for frame in tick.frames_run) or "nothing"}; '
        f'accumulator {milliseconds(seconds=tick.accumulated_seconds)}'
        f'{behind_note(schedule=schedule, tick=tick)}'
        for tick in schedule.ticks
    )
    lines.extend((
        f'  hidden: {frame_list(frames=schedule.hidden)}',
        (
            '  skipped by design (the replay was behind, or above 1x): '
            f'{frame_list(frames=schedule.skipped_by_design)}'
        ),
        f'  viewer disagrees on behind: {frame_list(frames=schedule.behind_disagreements)}',
        '  recorded dt:',
    ))
    lines.extend(
        f'    frame {frame_index}: {milliseconds(seconds=seconds)}'
        for frame_index, seconds in enumerate(schedule.frame_seconds)
    )
    return lines


def schedule_recording(*, path: Path, speed: float, summary: bool) -> ExitCode:
    """Simulate one recording and print its schedule.

    Args:
        path: The recording.
        speed: The replay speed.
        summary: True for the one-line summary.

    Returns:
        The recording's exit code (module docstring).

    """
    name = path.as_posix()
    if not path.exists():
        sys.stderr.write(f'{name}: no such recording\n')
        return ExitCode.MISSING_INPUT
    try:
        frame_seconds = recorded_frame_seconds(path=path)
    except (TraceFormatError, UnusableRecordingError, OSError) as error:
        sys.stderr.write(f'{name}: unusable recording: {error}\n')
        return ExitCode.UNUSABLE_INPUT
    schedule = simulate_schedule(frame_seconds=frame_seconds, speed=speed)
    lines = (
        [summary_line(name=name, schedule=schedule)]
        if summary
        else detail_lines(name=name, schedule=schedule)
    )
    sys.stdout.write('\n'.join(lines) + '\n')
    return ExitCode.REPLAY_DIVERGED if schedule.fails else ExitCode.SUCCESS


def viewer_speed(value: str) -> float:
    """Parse a speed the viewer can play at (``ReplayControls.MIN_SPEED`` to ``MAX_SPEED``).

    Returns:
        The speed.

    Raises:
        argparse.ArgumentTypeError: Not a number, or outside the viewer's range.

    """
    try:
        speed = float(value)
    except ValueError as error:
        message = f'not a number: {value!r}'
        raise argparse.ArgumentTypeError(message) from error
    if not ReplayControls.MIN_SPEED <= speed <= ReplayControls.MAX_SPEED:
        message = (
            f'{value} is outside the viewer speeds '
            f'{ReplayControls.MIN_SPEED:g} to {ReplayControls.MAX_SPEED:g}'
        )
        raise argparse.ArgumentTypeError(message)
    return speed


def main(*, arguments: list[str]) -> ExitCode:
    """Simulate each recording named on the command line (module docstring).

    Args:
        arguments: The command-line arguments (without the program name).

    Returns:
        The first failure's exit code, else ``SUCCESS``.

    """
    parser = argparse.ArgumentParser(
        prog='python -m scripts.replay_schedule',
        description="Simulate a watched replay's schedule on the viewer's accumulator.",
    )
    parser.add_argument('paths', nargs='+', type=Path, metavar='PATH', help='a recording')
    parser.add_argument('--speed', type=viewer_speed, default=1.0, help='the replay speed')
    parser.add_argument('--summary', action='store_true', help='one line per recording')
    options = parser.parse_args(arguments)
    exit_code = ExitCode.SUCCESS
    for path in options.paths:
        recording_exit_code = schedule_recording(
            path=path, speed=options.speed, summary=options.summary
        )
        if exit_code == ExitCode.SUCCESS:
            exit_code = recording_exit_code
    return exit_code


def command_line() -> None:
    """Command line: see the module docstring."""
    sys.exit(main(arguments=sys.argv[1:]))


if __name__ == '__main__':
    command_line()
