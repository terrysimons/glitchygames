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

1. No tick open: sleep until the next tick is due (while inner frames run, ``sleep_for``: the
   engine's high-resolution sleep-then-spin timer, glitchygames/timing.py ``FastTimer``; paused,
   at the start screen or over, ``sleep_coarsely``, which never spins), open it, let the doors
   run the tick's work (keys), then add the real time since the last tick, times the speed, to
   the accumulator. A tick within ``TICK_SNAP_WINDOW_SECONDS`` of one period counts as exactly
   one period, the error carried to the next tick, so wake-up jitter does not turn 1x into ticks
   of 0 and 2 frames. Only while the inner game is running: paused, at the start screen or over,
   the accumulator empties, and a restart seeds it with half a frame (so frame boundaries never
   sit on a tick boundary).
2. Tick open: run one more inner frame (``should_run_inner_frame`` True) while the accumulator
   holds the frame's recorded duration, which it then consumes; at most
   ``MAX_INNER_FRAMES_PER_TICK`` per tick, and only within the tick's real-time budget
   (``INNER_FRAME_BUDGET_SECONDS``), so keys, the status line and presenting stay at 60 Hz
   however costly inner frames are. The accumulator never owes more than one tick's worth of
   frames: the excess is dropped (a long stall runs one bounded burst), and while frames are
   dropped or the budget cuts ticks short the viewer is behind (``is_behind``): the status bar
   then shows the real speed (``effective_speed``). So 1x runs one inner frame a tick for a
   60 FPS recording (but for the true rate mismatch), 8x eight, 1/4x one every fourth tick,
   paused none. While paused a step (``.``) runs exactly one inner frame. The start screen
   lets frame 0 run first, so its picture is behind the message.
3. Otherwise the tick closes: the doors refresh the status line, the loop presents the outer
   frame and asks again (step 1).

The accumulator only decides when inner frames run, never what they do, so a watched replay is
as exact as a headless one. Headless replays have no viewer loop: they never hold and run
unpaced. Step back restarts the replay process instead, which rebuilds the inner game up to
frame N-1 before the viewer's first tick (glitchygames/replay/rebuild.py; no outer tick opens
during the rebuild). Later users of the same contract: Part 3's playback scopes (an inner replay
under a live outer game) and audio/video capture (inner frames handed to a sink rather than
presented).
"""

from __future__ import annotations

import collections
import time
from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.clock import measured_seconds
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, ControlCadence, ReplayControls
from glitchygames.timing import FastTimer

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from glitchygames.scenes import SceneManager

# The most inner frames one outer tick runs; the accumulator never owes more than this many
MAX_INNER_FRAMES_PER_TICK = 32
# The real time an outer tick may spend running inner frames (of its 16.7 ms), so the tick's
# keys, status line and presenting keep their 60 Hz
INNER_FRAME_BUDGET_SECONDS = 0.011
# A tick this close to one period after the last counts as exactly one period (error carried)
TICK_SNAP_WINDOW_SECONDS = 0.002
# The effective speed (and being behind) is judged over the last second of ticks
EFFECTIVE_SPEED_WINDOW_TICKS = 60
# Behind, the status bar shows the real speed only when it is below this fraction of the speed
BEHIND_SPEED_FRACTION = 0.95
# A tick paying for more real time than this was a stall (the process stopped, a window drag):
# it restarts the effective-speed window instead of reading as a slow second
STALL_TICK_SECONDS = 0.25
NANOSECONDS_PER_SECOND = 1_000_000_000

# The viewer's sleeps: the engine's sleep-then-spin timer (finer than pygame.time.wait's
# whole milliseconds); it keeps no state between sleeps
_SLEEP_TIMER = FastTimer()


def sleep_coarsely(*, seconds: float) -> None:
    """Sleep ``seconds`` without spinning (``time.sleep``): the wait while nothing runs.

    Args:
        seconds: How long (nothing happens when not positive).

    """
    if seconds > 0:
        time.sleep(seconds)


def sleep_for(*, seconds: float) -> None:
    """Sleep ``seconds`` with the engine's high-resolution timer (glitchygames/timing.py).

    It spins for the last millisecond or two, so it is used only while inner frames run.

    Args:
        seconds: How long (nothing happens when not positive).

    """
    if seconds > 0:
        _SLEEP_TIMER.sleep_until_next(
            _SLEEP_TIMER.ns_now() + round(seconds * NANOSECONDS_PER_SECOND)
        )


class ReplayViewer:
    """The outer loop of a watched replay (module docstring).

    Attributes:
        controls: The viewer's controls (keys, state and status bar).
        cadence: The outer tick's real-time cadence.
        accumulated_seconds: Inner game time owed to the inner game (real time times speed,
            consumed by each inner frame's recorded duration).
        ticks_externally: True when something outside waits for each tick (a browser's
            animation frames, ``run_watched_replay_async``): a tick then opens at once, never
            sleeping or following ``cadence``, and owes the real time since the last, so the
            replay keeps its speed at any display rate.

    """

    def __init__(self: Self, *, controls: ReplayControls) -> None:
        """Start with no tick open; the first tick is due at once.

        Args:
            controls: The viewer's controls.

        """
        self.controls = controls
        self.cadence = ControlCadence()
        self.accumulated_seconds = 0.0
        self.ticks_externally = False
        self._is_tick_open = False
        self._inner_frames_this_tick = 0
        self._tick_start_seconds = 0.0
        # The tick time the next tick's elapsed time is measured from (snapping carries error)
        self._last_tick_seconds: float | None = None
        # True when the inner game (re)starts running: the accumulator gets half a frame
        self._needs_phase_offset = True
        # Ticks left during which the viewer counts as behind (frames dropped or cut short)
        self._behind_ticks_left = 0
        # Per running tick over the last second: its real seconds and the inner seconds it ran
        self._recent_real_seconds: collections.deque[float] = collections.deque(
            maxlen=EFFECTIVE_SPEED_WINDOW_TICKS
        )
        self._recent_inner_seconds: collections.deque[float] = collections.deque(
            maxlen=EFFECTIVE_SPEED_WINDOW_TICKS
        )
        # The open tick: whether the inner game runs in it, the real time it pays for and the
        # inner seconds it ran
        self._tick_is_running = False
        self._tick_elapsed_seconds = 0.0
        self._inner_seconds_this_tick = 0.0
        # The viewer's key presses and releases (event type, key) read since the last tick
        self._key_events: list[tuple[int, int]] = []

    @property
    def is_behind(self: Self) -> bool:
        """True while the inner game cannot keep up with the speed (in the last second)."""
        return self._behind_ticks_left > 0

    def effective_speed(self: Self) -> float:
        """Return the speed the inner game really ran at over the last second of ticks.

        Returns:
            Inner seconds run over real seconds passed (0.0 before any time passed).

        """
        real_seconds = sum(self._recent_real_seconds)
        if real_seconds <= 0:
            return 0.0
        return sum(self._recent_inner_seconds) / real_seconds

    def real_speed_if_behind(self: Self) -> float | None:
        """Return the real speed when the inner game meaningfully cannot keep up, for the status.

        Returns:
            ``effective_speed()`` while behind and below ``BEHIND_SPEED_FRACTION`` of the
            speed, else None (keeping up, slightly slow, or no running ticks measured yet).

        """
        if not self.is_behind or not self._recent_real_seconds:
            return None
        real_speed = self.effective_speed()
        if real_speed >= self.controls.speed * BEHIND_SPEED_FRACTION:
            return None
        return real_speed

    def queue_key_event(self: Self, *, event_type: int, key: int) -> None:
        """Keep a real KEYDOWN or KEYUP for the next tick (keys act once per tick at most).

        Args:
            event_type: ``pygame.KEYDOWN`` or ``pygame.KEYUP``.
            key: The key.

        """
        self._key_events.append((event_type, key))

    def begin_tick(self: Self, *, is_inner_running: bool) -> float | None:
        """Open the next outer tick if none is open, first sleeping until it is due.

        Args:
            is_inner_running: Whether the inner game was running when the last tick closed:
                the wait spins only then (``sleep_for``); paused, at the start screen or over
                it is a plain sleep (``sleep_coarsely``).

        Returns:
            The tick's measured time when a tick was opened (the doors then run its work and
            call ``accrue``), or None while a tick is open.

        """
        if self._is_tick_open:
            return None
        now = measured_seconds()
        if self.ticks_externally:
            return self._open_tick(now=now)
        remaining_seconds = self.cadence.next_tick_seconds(now=now) - now
        if remaining_seconds > 0:
            if is_inner_running:
                sleep_for(seconds=remaining_seconds)
            else:
                sleep_coarsely(seconds=remaining_seconds)
            now = measured_seconds()
        self.cadence.tick_is_due(now=now)
        return self._open_tick(now=now)

    def _open_tick(self: Self, *, now: float) -> float:
        """Open a tick at ``now``.

        Returns:
            ``now``.

        """
        self._is_tick_open = True
        self._inner_frames_this_tick = 0
        self._tick_start_seconds = now
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
        if self._last_tick_seconds is None:
            elapsed_seconds = 0.0
            self._last_tick_seconds = now
        else:
            elapsed_seconds = now - self._last_tick_seconds
            if abs(elapsed_seconds - CONTROL_TICK_SECONDS) <= TICK_SNAP_WINDOW_SECONDS:
                # On time within the window: exactly one period, the error carried
                elapsed_seconds = CONTROL_TICK_SECONDS
                self._last_tick_seconds += CONTROL_TICK_SECONDS
            else:
                self._last_tick_seconds = now
        self._behind_ticks_left = max(0, self._behind_ticks_left - 1)
        self._tick_is_running = is_inner_running
        self._tick_elapsed_seconds = elapsed_seconds
        self._inner_seconds_this_tick = 0.0
        if not is_inner_running:
            self.accumulated_seconds = 0.0
            self._needs_phase_offset = True
            self._recent_real_seconds.clear()
            self._recent_inner_seconds.clear()
            self._behind_ticks_left = 0
            return
        self.accumulated_seconds += elapsed_seconds * self.controls.speed

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
        if self._needs_phase_offset:
            self._needs_phase_offset = False
            self.accumulated_seconds += inner_frame_seconds / 2
        # Never owe more than one tick's worth (keeping the half-frame phase): drop the excess
        # (frames recorded with no duration owe nothing and never fall behind)
        owed_limit_seconds = (MAX_INNER_FRAMES_PER_TICK + 0.5) * inner_frame_seconds
        if inner_frame_seconds > 0 and self.accumulated_seconds > owed_limit_seconds:
            self.accumulated_seconds = owed_limit_seconds
            self._fall_behind()
        if self.accumulated_seconds < inner_frame_seconds:
            return self._close_tick()
        if (
            self._inner_frames_this_tick >= MAX_INNER_FRAMES_PER_TICK
            or measured_seconds() - self._tick_start_seconds >= INNER_FRAME_BUDGET_SECONDS
        ):
            # Owed but out of frames or time this tick: carried to the next
            if inner_frame_seconds > 0:
                self._fall_behind()
            return self._close_tick()
        self.accumulated_seconds -= inner_frame_seconds
        self._inner_frames_this_tick += 1
        self._inner_seconds_this_tick += inner_frame_seconds
        return True

    def _fall_behind(self: Self) -> None:
        """Count as behind for the next second of ticks."""
        self._behind_ticks_left = EFFECTIVE_SPEED_WINDOW_TICKS

    def _close_tick(self: Self) -> bool:
        """Close the open tick: the loop presents the outer frame next.

        A running tick joins the effective-speed window with its own real time and the inner
        seconds it ran; a stall (``STALL_TICK_SECONDS``) restarts the window instead, so it does
        not read as a slow second.

        Returns:
            False (no inner frame runs).

        """
        self._is_tick_open = False
        if self._tick_elapsed_seconds > STALL_TICK_SECONDS:
            self._recent_real_seconds.clear()
            self._recent_inner_seconds.clear()
        elif self._tick_is_running and self._tick_elapsed_seconds > 0:
            self._recent_real_seconds.append(self._tick_elapsed_seconds)
            self._recent_inner_seconds.append(self._inner_seconds_this_tick)
        self._tick_is_running = False
        return False


async def run_watched_replay_async(
    *,
    scene_manager: SceneManager,
    viewer: ReplayViewer,
    wait_for_tick: Callable[[], Awaitable[float]],
) -> None:
    """Run a watched replay's frames, giving control back to the caller between outer ticks.

    For a host that must not block (a browser). Each awaited ``wait_for_tick()`` is one outer
    tick of ``viewer`` (``ticks_externally``: the viewer never sleeps): the tick's inner frames
    run, then the viewer holds and the outer frame is presented (``SceneManager.run_frame_step``
    steps until ``last_step_was_held``). Frames run unpaced, as the blocking loop runs them in a
    watched replay: the viewer's accumulator decides when they run.

    Args:
        scene_manager: The replayed game's scene manager.
        viewer: The watched replay's viewer.
        wait_for_tick: Waits for the next outer tick (a browser animation frame).

    """
    viewer.ticks_externally = True
    frame_start_seconds = scene_manager.begin_frames()
    while scene_manager.should_run_frames():
        await wait_for_tick()
        while scene_manager.should_run_frames():
            frame_start_seconds = scene_manager.run_frame_step(
                frame_start_seconds=frame_start_seconds, paced=False
            )
            if scene_manager.last_step_was_held:
                break
    scene_manager.end_frames()
