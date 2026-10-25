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

Each except measured_seconds() reads the active sources (glitchygames/sources.py) or the frame
clock they drive, so a replay serves them exactly: the frame clock comes from recorded frame
times and the wall clock is the recording's start time plus the frame clock. Only
measured_seconds(), pacing, the performance statistics, the audio-glitch probe and the
recording's own start stamp read the raw clock (tests/test_engine_doors.py lists them).

This module is a leaf like glitchygames/sources.py (the layering rule in
plans/2026-10-19-gameplay-replay-core.md, Task 2): it imports only the standard library and
glitchygames.sources, so any module (glitchygames.state.manager included) may import it without
a cycle.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from glitchygames.sources import active_sources, frame_clock_seconds

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    'elapsed_seconds',
    'frame_clock_milliseconds',
    'frame_clock_seconds',
    'measured_seconds',
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
    serves to the game: each frame's processing time (glitchygames/replay/processing.py). It
    is the one raw clock read the doors guard allows in this module.

    Returns:
        ``time.monotonic()``.

    """
    return time.monotonic()
