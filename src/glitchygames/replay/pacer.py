"""Pacing a recording's frames to real time: the recorded-frame pacer and the tick budget.

A player of a recording (the watched replay's viewer, glitchygames/replay/viewer.py; later an
Arcade tile) ticks at its own rate and, each tick, runs the recorded frames that are owed. The
rules are the viewer's contract (its module docstring, rules 1 and 2), carried here so every
player shares one implementation:

- ``RecordedFramePacer`` owes frames. Each tick the player pays it the real time since its last
  tick, times the speed (``pay``); then, frame by frame, it answers whether the next frame runs
  now (``should_run_frame``) and consumes that frame's recorded duration. It owns the
  accumulator, the half-frame phase, the owed limit (``MAX_OWED_INNER_FRAMES``), rule 2's one
  frame a tick unless behind, the behind window and the effective speed. It is told the speed,
  the nominal tick period and whether the player is running, and reads no clock of its own: the
  elapsed time is the caller's, and the tick's real-time allowance is a ``TickBudget``. It only
  decides when recorded frames run, never what they do.
- ``TickBudget`` is "this much real time, then yield": started with a length, it answers
  ``is_spent`` and ``remaining_seconds`` from an injectable clock (``clock.measured_seconds`` by
  default). One budget can be handed to several consumers in turn, so what one leaves the next
  gets.

Frames are never skipped: a player that cannot keep up plays in slow motion (``is_behind``,
``effective_speed``), and owed time, never a frame, is dropped past the owed limit
(``dropped_seconds``).
"""

from __future__ import annotations

import collections
from typing import TYPE_CHECKING, Self

from glitchygames import clock

if TYPE_CHECKING:
    from collections.abc import Callable

# The owed limit in frames: the accumulator never owes more than this many and a half of the next
# frame's duration, or that frame plus two ticks of inner time when that is more, so a stall runs
# one bounded burst (no frame count limits a tick: only INNER_FRAME_BUDGET_SECONDS does)
MAX_OWED_INNER_FRAMES = 32
# The real time an outer tick may spend running inner frames (of its 16.7 ms), so the tick's
# keys, status line and presenting keep their 60 Hz
INNER_FRAME_BUDGET_SECONDS = 0.011
# The effective speed (and being behind) is judged over the last second of ticks
EFFECTIVE_SPEED_WINDOW_TICKS = 60
# Behind, the status bar shows the real speed only when it is below this fraction of the speed
BEHIND_SPEED_FRACTION = 0.95
# A tick paying for more real time than this was a stall (the process stopped, a window drag):
# it restarts the effective-speed window instead of reading as a slow second
STALL_TICK_SECONDS = 0.25


class TickBudget:
    """A real-time allowance: this much time from its start, then yield.

    A plain class, not a data model: one is made every tick of every player.

    Attributes:
        length_seconds: The allowance.
        started_at_seconds: The clock reading it started at.

    """

    def __init__(
        self: Self,
        *,
        length_seconds: float,
        measured_seconds: Callable[[], float] | None = None,
        started_at_seconds: float | None = None,
    ) -> None:
        """Start the allowance.

        Args:
            length_seconds: How much real time it allows.
            measured_seconds: The real-time clock; None is
                ``glitchygames.clock.measured_seconds``, looked up at each read.
            started_at_seconds: The clock reading it starts at, when the caller has just read
                it (the clock is then not read again); None reads the clock now.

        """
        self.length_seconds = length_seconds
        self._measured_seconds = measured_seconds
        self.started_at_seconds = (
            self._read_measured_seconds() if started_at_seconds is None else started_at_seconds
        )

    def _read_measured_seconds(self: Self) -> float:
        """Read the budget's clock (the one given, else the engine's).

        Returns:
            Seconds (only differences mean anything).

        """
        if self._measured_seconds is None:
            return clock.measured_seconds()
        return self._measured_seconds()

    @property
    def is_spent(self: Self) -> bool:
        """True once its length of real time has passed since it started."""
        return self._read_measured_seconds() - self.started_at_seconds >= self.length_seconds

    @property
    def remaining_seconds(self: Self) -> float:
        """The real time left of its length, never below zero."""
        spent_seconds = self._read_measured_seconds() - self.started_at_seconds
        return max(0.0, self.length_seconds - spent_seconds)


class RecordedFramePacer:
    """Owes a player's recorded frames from the real time it pays (module docstring).

    A plain class, not a data model: its state changes every frame of every player.

    Each tick: ``pay`` once, then ``should_run_frame`` for each next frame until it answers
    False, which ends the tick's frames (the tick is closed). A player that ends a tick for its
    own reasons (paused, a step, over) without asking calls ``close_tick``.

    Attributes:
        nominal_tick_seconds: The player's tick period (the viewer's 60 Hz, a display's 120 Hz):
            rule 2's "tick of inner time" is the speed times it, and a stall counts as one.
        accumulated_seconds: Inner time owed (real time paid times the speed, consumed by each
            frame's recorded duration).
        last_frame_ran_behind: Whether the frame ``should_run_frame`` last allowed ran while
            behind: the accumulator owed the frame's recorded duration plus a whole tick of inner
            time, read before the frame consumed it. False for a frame its player ran without
            asking (it sets it so: a paused step, a start screen's frame 0).
        dropped_seconds: All the inner time dropped past the owed limit so far.

    """

    def __init__(self: Self, *, nominal_tick_seconds: float) -> None:
        """Start owing nothing, with the half-frame phase still to add.

        Args:
            nominal_tick_seconds: The player's tick period.

        """
        self.nominal_tick_seconds = nominal_tick_seconds
        self.accumulated_seconds = 0.0
        self.last_frame_ran_behind = False
        self.dropped_seconds = 0.0
        self._frames_this_tick = 0
        # The recorded duration of the tick's last frame (rule 2 above 1x)
        self._last_frame_seconds = 0.0
        # True when the player (re)starts running: the accumulator gets half a frame
        self._needs_phase_offset = True
        # Ticks left during which the pacer counts as behind (time dropped or budgets spent)
        self._behind_ticks_left = 0
        # Per running tick over the last second: its real seconds and the inner seconds it ran
        self._recent_real_seconds: collections.deque[float] = collections.deque(
            maxlen=EFFECTIVE_SPEED_WINDOW_TICKS
        )
        self._recent_inner_seconds: collections.deque[float] = collections.deque(
            maxlen=EFFECTIVE_SPEED_WINDOW_TICKS
        )
        # The open tick: whether the player runs in it, the real time it pays for and the inner
        # seconds it ran
        self._tick_is_running = False
        self._tick_elapsed_seconds = 0.0
        self._inner_seconds_this_tick = 0.0

    @property
    def is_behind(self: Self) -> bool:
        """True while the frames cannot keep up with the speed (in the last second)."""
        return self._behind_ticks_left > 0

    def effective_speed(self: Self) -> float:
        """Return the speed the frames really ran at over the last second of ticks.

        Returns:
            Inner seconds run over real seconds passed (0.0 before any time passed).

        """
        real_seconds = sum(self._recent_real_seconds)
        if real_seconds <= 0:
            return 0.0
        return sum(self._recent_inner_seconds) / real_seconds

    def real_speed_if_behind(self: Self, *, speed: float) -> float | None:
        """Return the real speed when the frames meaningfully cannot keep up.

        Args:
            speed: The speed asked for.

        Returns:
            ``effective_speed()`` while behind and below ``BEHIND_SPEED_FRACTION`` of
            ``speed``, else None (keeping up, slightly slow, or no running ticks measured yet).

        """
        if not self.is_behind or not self._recent_real_seconds:
            return None
        real_speed = self.effective_speed()
        if real_speed >= speed * BEHIND_SPEED_FRACTION:
            return None
        return real_speed

    def pay(self: Self, *, elapsed_seconds: float, speed: float, is_running: bool) -> None:
        """Begin a tick: owe the real time since the last tick, times the speed.

        Args:
            elapsed_seconds: The real time since the player's last tick.
            speed: The playback speed.
            is_running: False while paused, at a start screen or over: the accumulator empties
                instead, the behind window forgets, and the next run starts with half a frame.

        """
        self._frames_this_tick = 0
        self._behind_ticks_left = max(0, self._behind_ticks_left - 1)
        self._tick_is_running = is_running
        self._tick_elapsed_seconds = elapsed_seconds
        self._inner_seconds_this_tick = 0.0
        if not is_running:
            self.accumulated_seconds = 0.0
            self._needs_phase_offset = True
            self._recent_real_seconds.clear()
            self._recent_inner_seconds.clear()
            self._behind_ticks_left = 0
            return
        self.accumulated_seconds += elapsed_seconds * speed

    def should_run_frame(
        self: Self, *, frame_seconds: float, speed: float, budget: TickBudget
    ) -> bool:
        """Decide whether the tick runs the next frame now; if not, close the tick.

        Args:
            frame_seconds: The recorded duration of the frame that would run.
            speed: The playback speed.
            budget: The tick's real-time allowance for running frames.

        Returns:
            True to run the frame now (its duration is consumed); False when it is not owed
            yet, waits for the next tick (rule 2), the budget is spent, or the player is not
            running.

        """
        self.last_frame_ran_behind = False
        if not self._tick_is_running:
            return self.close_tick()
        if self._needs_phase_offset:
            self._needs_phase_offset = False
            self.accumulated_seconds += frame_seconds / 2
        # Never owe more than the owed limit (keeping the half-frame phase): drop the excess
        # (frames recorded with no duration owe nothing and never fall behind)
        owed_limit_seconds = self._owed_limit_seconds(frame_seconds=frame_seconds, speed=speed)
        if frame_seconds > 0 and self.accumulated_seconds > owed_limit_seconds:
            self.dropped_seconds += self.accumulated_seconds - owed_limit_seconds
            self.accumulated_seconds = owed_limit_seconds
            self._fall_behind()
        if self.accumulated_seconds < frame_seconds or self._defers_to_the_next_tick(
            frame_seconds=frame_seconds, speed=speed
        ):
            # Not owed yet, or (not behind) it runs and is presented next tick, the owed time
            # carried
            return self.close_tick()
        if budget.is_spent:
            # Owed but out of time this tick: carried to the next
            if frame_seconds > 0:
                self._fall_behind()
            return self.close_tick()
        self.last_frame_ran_behind = self._owes_beyond_a_tick(
            frame_seconds=frame_seconds, speed=speed
        )
        self.accumulated_seconds -= frame_seconds
        self._frames_this_tick += 1
        self._inner_seconds_this_tick += frame_seconds
        self._last_frame_seconds = frame_seconds
        return True

    def close_tick(self: Self) -> bool:
        """Close the tick: no more frames run in it.

        A running tick joins the effective-speed window with its own real time and the inner
        seconds it ran; a stall (``STALL_TICK_SECONDS``) restarts the window instead, so it does
        not read as a slow second.

        Returns:
            False (no frame runs).

        """
        if self._tick_elapsed_seconds > STALL_TICK_SECONDS:
            self._recent_real_seconds.clear()
            self._recent_inner_seconds.clear()
        elif self._tick_is_running and self._tick_elapsed_seconds > 0:
            self._recent_real_seconds.append(self._tick_elapsed_seconds)
            self._recent_inner_seconds.append(self._inner_seconds_this_tick)
        self._tick_is_running = False
        return False

    def _owed_limit_seconds(self: Self, *, frame_seconds: float, speed: float) -> float:
        """Return the most inner time the accumulator may owe; the excess is dropped (rule 2).

        ``MAX_OWED_INNER_FRAMES`` and a half frames, and never less than the floor: the frame
        plus a nominal tick of inner time (what rule 2's one-frame limit may carry) plus the
        inner time of the tick paid for (the speed times the real time since the last tick, at
        least a nominal tick). Below that, a recording whose frames are short (an uncapped game)
        would be capped every tick, fall behind every tick and play in slow motion; a tick
        slower than nominal (a browser on a slower display, a late blocking tick) pays for more
        than a nominal tick, so the floor follows it. A stall (a tick paying for more than
        ``STALL_TICK_SECONDS``, as the effective-speed window counts it) is not a display rate:
        it counts as a nominal tick, so its burst stays as bounded as at the nominal rate.

        Args:
            frame_seconds: The recorded duration of the frame that would run.
            speed: The playback speed.

        Returns:
            Seconds.

        """
        nominal_tick_seconds = self.nominal_tick_seconds
        frames_limit_seconds = (MAX_OWED_INNER_FRAMES + 0.5) * frame_seconds
        tick_paid_for_seconds = (
            nominal_tick_seconds
            if self._tick_elapsed_seconds > STALL_TICK_SECONDS
            else max(nominal_tick_seconds, self._tick_elapsed_seconds)
        )
        floor_seconds = frame_seconds + speed * (nominal_tick_seconds + tick_paid_for_seconds)
        return max(frames_limit_seconds, floor_seconds)

    def _defers_to_the_next_tick(self: Self, *, frame_seconds: float, speed: float) -> bool:
        """Decide whether a later frame in the tick waits for the next tick (rule 2).

        A tick presents only its last frame, so a second (or later) frame runs in the same tick
        only when the player is genuinely behind (``_owes_beyond_a_tick``): up to 1x after any
        frame, and above 1x after a frame lasting at least a tick of inner time at that speed
        (its recorded duration at least the speed times ``nominal_tick_seconds``, so it lasts a
        tick or more of real time). Otherwise a live frame that ran long and the short one its
        pacing caught up with would share a tick, and the long one would never be shown. After
        a frame shorter than that, above 1x, a tick runs several frames and presents the last
        (fast-forward).

        Args:
            frame_seconds: The recorded duration of the frame that would run.
            speed: The playback speed.

        Returns:
            True when the frame waits for the next tick.

        """
        if self._frames_this_tick == 0:
            return False
        if speed > 1 and self._last_frame_seconds < speed * self.nominal_tick_seconds:
            return False
        return not self._owes_beyond_a_tick(frame_seconds=frame_seconds, speed=speed)

    def _owes_beyond_a_tick(self: Self, *, frame_seconds: float, speed: float) -> bool:
        """Whether the player is behind: it owes the frame plus a whole tick of inner time.

        Args:
            frame_seconds: The recorded duration of the frame that would run.
            speed: The playback speed.

        Returns:
            True when the accumulator holds at least the frame's duration plus the speed times
            ``nominal_tick_seconds``.

        """
        return self.accumulated_seconds >= frame_seconds + speed * self.nominal_tick_seconds

    def _fall_behind(self: Self) -> None:
        """Count as behind for the next second of ticks."""
        self._behind_ticks_left = EFFECTIVE_SPEED_WINDOW_TICKS
