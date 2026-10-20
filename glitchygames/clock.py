"""The engine's clocks: every time a game, widget or editor reads comes from here.

Pick by what the time is for:

- ``Scene.game_time`` (on the scene): gameplay timers and cooldowns; pauses with the scene.
- ``frame_clock_seconds()``: blinks, animation timing, FPS events, "how long since" in UI; the
  sum of frame times, never pauses.
- ``wall_clock_time()`` / ``wall_clock_epoch_seconds()``: timestamps (undo history, save and
  file metadata, log records, ids).
- ``elapsed_seconds()``: durations, metrics, controller and input timing; only differences
  between two readings mean anything.

Each reads the active sources (glitchygames/sources.py), so a replay serves them exactly: the
frame clock comes from recorded frame times, the wall clock is the recording's start time plus
the frame clock, and elapsed seconds are the frame clock. Only pacing, the performance statistics,
the audio-glitch probe and the recording's own start stamp read the raw clock
(tests/test_engine_doors.py lists them).

This module is a leaf like glitchygames/sources.py (the layering rule in
plans/2026-10-19-gameplay-replay-core.md, Task 2): it imports only glitchygames.sources, so any
module (glitchygames.state.manager included) may import it without a cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from glitchygames.sources import active_sources, frame_clock_seconds

if TYPE_CHECKING:
    from datetime import datetime

__all__ = [
    'elapsed_seconds',
    'frame_clock_milliseconds',
    'frame_clock_seconds',
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
    """Return a monotonic reading in seconds; subtract two readings for a duration.

    Returns:
        ``time.monotonic()`` live; the frame clock in a replay.

    """
    return active_sources().elapsed_seconds()
