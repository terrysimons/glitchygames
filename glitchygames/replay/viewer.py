"""The replay viewer: a watched replay is a read-only game inside a game.

Two loops share the frame loop of ``SceneManager.start`` while a replay is watched
(glitchygames/replay/driver.py, rule 14):

- OUTER, the viewer (``ReplayViewer``): owns the window. It ticks at a fixed real-time rate
  (``CONTROL_TICKS_PER_SECOND``, on ``glitchygames.clock.measured_seconds``, never replayed),
  whatever the replay's speed and whether it is paused. Each tick it reads the viewer's keys
  (``ReplayControls``, once per press), refreshes the status line, and presents one frame: the
  inner game's latest, with the status bar, start screen and debug overlay drawn on a copy.
- INNER, the recorded game: steps at its recorded frame times and never receives viewer
  input. Its frames always run in full (events, logic, update, render), exactly as recorded;
  only their presentation is left to the outer tick (``ReplaySources.presents_frames`` is
  False while watched).

The contract between them, asked through ``EngineSources.hold_frame`` before each inner frame:

1. No tick open: wait until the next tick is due (sleeping, never spinning), open it, let the
   doors run the tick's work (keys, status line), then add the real time since the last tick,
   times the speed, to the accumulator (only while the inner game is running: paused, at the
   start screen or over, the accumulator empties).
2. Tick open: run one more inner frame (``should_run_inner_frame`` True) while the accumulator
   holds the frame's recorded duration, which it then consumes, and at most
   ``MAX_INNER_FRAMES_PER_TICK`` per tick (a long hitch carries its remainder to later ticks
   instead of running thousands of frames at once). So 1x runs about one inner frame a tick
   for a 60 FPS recording and is exact over time, 8x about eight, 1/4x one every fourth tick,
   paused none. While paused a step (``.``) runs exactly one inner frame. The start screen
   lets frame 0 run first, so its picture is behind the message.
3. Otherwise the tick closes: the loop presents the outer frame and asks again (step 1).

The accumulator only decides when inner frames run, never what they do, so a watched replay is
as exact as a headless one. Headless replays have no viewer loop: they never hold and run
unpaced. Later users of the same contract: Part 3's playback scopes (an inner replay under a
live outer game), step back (the outer loop re-simulating the inner game to frame N-1), and
audio/video capture (inner frames handed to a sink rather than presented).
"""

from __future__ import annotations

import math
from typing import Self

import pygame

from glitchygames.clock import measured_seconds
from glitchygames.replay.controls import ControlCadence, ReplayControls

# The most inner frames one outer tick runs (the accumulator keeps the rest for later ticks)
MAX_INNER_FRAMES_PER_TICK = 32
MILLISECONDS_PER_SECOND = 1000


class ReplayViewer:
    """The outer loop of a watched replay (module docstring).

    Attributes:
        controls: The viewer's controls (keys, state and status bar).
        cadence: The outer tick's real-time cadence.
        accumulated_seconds: Inner game time owed to the inner game (real time times speed,
            consumed by each inner frame's recorded duration).

    """

    def __init__(self: Self, *, controls: ReplayControls) -> None:
        """Start with no tick open; the first tick is due at once.

        Args:
            controls: The viewer's controls.

        """
        self.controls = controls
        self.cadence = ControlCadence()
        self.accumulated_seconds = 0.0
        self._is_tick_open = False
        self._inner_frames_this_tick = 0
        self._last_tick_seconds: float | None = None
        # The viewer's key presses and releases (event type, key) read since the last tick
        self._key_events: list[tuple[int, int]] = []

    def queue_key_event(self: Self, *, event_type: int, key: int) -> None:
        """Keep a real KEYDOWN or KEYUP for the next tick (keys act once per tick at most).

        Args:
            event_type: ``pygame.KEYDOWN`` or ``pygame.KEYUP``.
            key: The key.

        """
        self._key_events.append((event_type, key))

    def begin_tick(self: Self) -> float | None:
        """Open the next outer tick if none is open, first sleeping until it is due.

        Returns:
            The tick's measured time when a tick was opened (the doors then run its work and
            call ``accrue``), or None while a tick is open.

        """
        if self._is_tick_open:
            return None
        now = measured_seconds()
        remaining_seconds = self.cadence.next_tick_seconds(now=now) - now
        if remaining_seconds > 0:
            pygame.time.wait(math.ceil(remaining_seconds * MILLISECONDS_PER_SECOND))
            now = measured_seconds()
        self.cadence.tick_is_due(now=now)
        self._is_tick_open = True
        self._inner_frames_this_tick = 0
        return now

    def apply_key_events(self: Self, *, now: float) -> None:
        """Act on the keys read since the last tick, then repeat held step keys.

        Args:
            now: The tick's measured time.

        """
        for event_type, key in self._key_events:
            if event_type == pygame.KEYDOWN:
                self.controls.press_key(key=key, now=now)
            else:
                self.controls.release_key(key=key)
        self._key_events = []
        self.controls.repeat_held_keys(now=now)

    def accrue(self: Self, *, now: float, is_inner_running: bool) -> None:
        """Owe the inner game the real time since the last tick, times the speed.

        Args:
            now: The tick's measured time.
            is_inner_running: False while paused, at the start screen or over: the
                accumulator empties instead.

        """
        elapsed_seconds = 0.0 if self._last_tick_seconds is None else now - self._last_tick_seconds
        self._last_tick_seconds = now
        if is_inner_running:
            self.accumulated_seconds += elapsed_seconds * self.controls.speed
        else:
            self.accumulated_seconds = 0.0

    def should_run_inner_frame(
        self: Self, *, inner_frame_seconds: float, is_inner_over: bool, is_first_inner_frame: bool
    ) -> bool:
        """Decide whether the open tick runs one more inner frame; if not, close the tick.

        Args:
            inner_frame_seconds: The recorded duration of the inner frame that would run.
            is_inner_over: True once the replay stopped or the recording is used up (a step
                then does nothing).
            is_first_inner_frame: True before the inner game's frame 0.

        Returns:
            True to run one inner frame now.

        """
        controls = self.controls
        if is_inner_over:
            controls.take_step()
            return self._close_tick()
        if controls.awaiting_start:
            # Frame 0 runs first, so the start screen shows its picture
            return is_first_inner_frame or self._close_tick()
        if controls.paused:
            return controls.take_step() or self._close_tick()
        if self._inner_frames_this_tick >= MAX_INNER_FRAMES_PER_TICK:
            return self._close_tick()
        if self.accumulated_seconds < inner_frame_seconds:
            return self._close_tick()
        self.accumulated_seconds -= inner_frame_seconds
        self._inner_frames_this_tick += 1
        return True

    def _close_tick(self: Self) -> bool:
        """Close the open tick: the loop presents the outer frame next.

        Returns:
            False (no inner frame runs).

        """
        self._is_tick_open = False
        return False
