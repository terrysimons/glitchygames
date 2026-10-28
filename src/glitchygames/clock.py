"""The engine's clocks: every time a game, widget or editor reads comes from here.

Pick by what the time is for:

- ``Scene.game_time`` (on the scene): gameplay timers and cooldowns; pauses with the scene.
- ``frame_clock_seconds()``: blinks, animation timing, FPS events, "how long since" in UI; the
  sum of frame times, never pauses.
- ``wall_clock_time()`` / ``wall_clock_epoch_seconds()``: timestamps (undo history, save and
  file metadata, log records, ids).
- ``elapsed_seconds()``: throttles, cooldowns, debounces, repeat and scan intervals, activity
  ages, timeouts; only differences between two readings mean anything. It is the frame clock,
  live and replayed, so it advances once per frame and every timer that changes behaviour reads
  the same values in a replay as it did live.
- ``measured_seconds()``: real durations for logs, metrics and diagnostics displays only (an AI
  request's duration, an operation's cost). It is ``time.monotonic()`` and is never replayed, so
  its readings must never decide anything that changes what is drawn, played or recorded.

The raw functions below are not clocks a game reads. They are the real machine's time, never
replayed, for the engine's own pacing, measurement and diagnostics, and they are the only reads
of the ``time`` module (and of ``datetime``'s now) in the package:

- ``raw_counter_ns()`` / ``raw_counter_seconds()``: the high-resolution performance counter
  (``time.perf_counter_ns()`` / ``time.perf_counter()``). Frame pacing (glitchygames/timing.py),
  the frame loop's measurement of each frame (``SceneManager``; a replay's frame-time door
  answers with the recorded dt instead), the audio-glitch probe, the performance statistics'
  log interval and a measurement tool's summary time.
- ``raw_sleep(seconds)``: ``time.sleep``. Pacing's coarse sleep, the replay viewer's wait,
  the power-on sequence's frames, retries and polls that wait for the real world (a window
  manager, a microphone, a controller's speaker, an AI service).
- ``raw_wall_clock_time()``: now, timezone-aware UTC (``datetime.now(tz=UTC)``). The live doors'
  wall clock (glitchygames/live_sources.py, which ``wall_clock_time()`` reads live), and a
  recording's own stamps (its ``recorded_at``, the replay wall clock's origin, and each run's
  ``measured_at``).

A function or class that waits or measures takes the raw function as a parameter where that is
clean (``FastTimer(read_counter_ns=..., sleep=...)``, ``play_power_on(sleep=...)``), with the
raw function as the default, so a test passes a fake instead of patching a clock.

Each clock except measured_seconds() reads the active sources (glitchygames/sources.py) or the
frame clock they drive, so a replay serves them exactly: the frame clock comes from recorded
frame times and the wall clock is the recording's start time plus the frame clock.
tests/test_engine_doors.py allows ``time`` and ``datetime``'s now in this module only.

This module is a leaf like glitchygames/sources.py (the layering rule in
plans/2026-10-19-gameplay-replay-core.md, Task 2): it imports only the standard library and
glitchygames.sources, so any module (glitchygames.state.manager included) may import it without
a cycle.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from glitchygames.sources import active_sources, frame_clock_seconds

__all__ = [
    'elapsed_seconds',
    'frame_clock_milliseconds',
    'frame_clock_seconds',
    'measured_seconds',
    'raw_counter_ns',
    'raw_counter_seconds',
    'raw_sleep',
    'raw_wall_clock_time',
    'wall_clock_epoch_seconds',
    'wall_clock_time',
]


def frame_clock_milliseconds() -> int:
    """Return the frame clock in whole milliseconds (widget blink and update timers).

    Returns:
        ``round(frame_clock_seconds() * 1000)``.

    """
    return round(frame_clock_seconds() * 1000)


def wall_clock_time() -> datetime:
    """Return the current wall-clock time (timezone-aware UTC) from the active sources.

    Returns:
        Now, live; the recording's start time plus the frame clock, in a replay.

    """
    return active_sources().wall_clock_time()


def wall_clock_epoch_seconds() -> float:
    """Return ``wall_clock_time()`` as seconds since the Unix epoch (what ``time.time()`` gave).

    Returns:
        Seconds since 1970-01-01 UTC.

    """
    return wall_clock_time().timestamp()


def elapsed_seconds() -> float:
    """Return the frame clock, for timers that change behaviour; subtract two readings.

    It is the frame clock live and in a replay (it advances once per frame, in
    ``SceneManager._finish_frame``), so a throttle or cooldown near its threshold decides the
    same way in a replay as it did live. Readings within one frame are equal.

    Returns:
        ``frame_clock_seconds()``.

    """
    return frame_clock_seconds()


def measured_seconds() -> float:
    """Return real monotonic time, for measuring durations that only reach logs or metrics.

    Never replayed: a replay reads the real machine's time here, so a reading must never feed a
    decision that changes what is drawn, played or recorded (use ``elapsed_seconds()`` for
    that). The one exception is a diagnostic a recording stores but no replay compares or
    serves to the game: each frame's processing time (glitchygames/replay/processing.py).

    Returns:
        ``time.monotonic()``.

    """
    return time.monotonic()


def raw_counter_ns() -> int:
    """Return the raw high-resolution performance counter in nanoseconds (never replayed).

    For pacing and measuring the real run only (FastTimer's deadlines, the audio-glitch probe);
    only differences between two readings mean anything.

    Returns:
        ``time.perf_counter_ns()``.

    """
    return time.perf_counter_ns()


def raw_counter_seconds() -> float:
    """Return the raw high-resolution performance counter in seconds (never replayed).

    For measuring the real run only: the frame loop's start-to-start reading of each frame
    (which reaches logic only through the frame-time door, answered in a replay with the
    recorded dt), diagnostics and tool summaries. Only differences mean anything.

    Returns:
        ``time.perf_counter()``.

    """
    return time.perf_counter()


def raw_sleep(seconds: float) -> None:
    """Sleep for real (never replayed): pacing, and waits for the real world.

    Args:
        seconds: How long to sleep; 0 only yields the GIL.

    """
    time.sleep(seconds)


def raw_wall_clock_time() -> datetime:
    """Return the real machine's now, timezone-aware UTC (never replayed).

    For the live doors' wall clock (``LiveSources.wall_clock_time``, which
    ``wall_clock_time()`` reads live) and a recording's own stamps (``recorded_at``,
    ``measured_at``) only; everything else reads ``wall_clock_time()``.

    Returns:
        ``datetime.now(tz=UTC)``.

    """
    return datetime.now(tz=UTC)
