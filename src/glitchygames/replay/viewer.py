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
2. Tick open: run one more inner frame (``should_run_inner_frame`` True) while the accumulator holds
   the frame's recorded duration, which it then consumes, only within the tick's real-time work
   budget (``INNER_FRAME_BUDGET_SECONDS``, 11 ms of the 16.7 ms tick), so keys, the status line and
   presenting stay at 60 Hz however costly inner frames are. The budget is the only per-tick limit
   at every speed (no frame count), so on a real machine an uncapped recording whose frames cost
   what they did live may still not keep up, and "can't keep up" then means exactly that.

   Rule 2, one frame a tick unless behind: up to 1x (speed <= 1) a tick runs at most one inner frame
   unless the replay is genuinely behind: a second (or later) frame in the same tick runs only when
   the accumulator holds its recorded duration plus a whole 60 Hz tick of inner time (the speed
   times ``CONTROL_TICK_SECONDS``); otherwise the tick closes and the frame runs next tick, the owed
   time carried. So a live frame that ran long and the short frame its pacing caught up with never
   share a tick (which would show only the short one): each is presented. After such a catch-up the
   replay stays about a tick behind real time: a constant lag, not a drift (it never grows), which a
   pause resets. A recording faster than 60 FPS (frames shorter than a tick) owes more than that
   every tick, so a tick still runs several of its frames and presents the last. Above 1x the same
   limit applies after a frame lasting at least a tick of inner time at that speed (its recorded
   duration at least the speed times the tick period: a 60 Hz refresh or more of real time), so
   fast-forward still shows it; after shorter frames a tick runs several and presents the last.

   The owed limit: the accumulator never owes more than ``MAX_OWED_INNER_FRAMES`` and a half of the
   next frame's duration (about half a second of 60 FPS frames), and never less than the floor: the
   frame plus a 60 Hz tick plus the tick paid for (the real time since the last tick, at least a
   60 Hz tick; a stall over ``STALL_TICK_SECONDS`` counts as a 60 Hz tick), in inner time, so a
   recording of very short frames, or a slower display's ticks, keep their rate. The excess is
   dropped (a long stall runs one bounded burst), and while frames are dropped or the budget cuts
   ticks short the viewer is behind (``is_behind``): the status bar then shows the real speed
   (``effective_speed``). So 1x runs one inner frame a tick for a 60 FPS recording (but for the true
   rate mismatch), 8x eight, 1/4x one every fourth tick, paused none. While paused a step (``.``)
   runs exactly one inner frame. The start screen lets frame 0 run first, so its picture is behind
   the message.
3. Otherwise the tick closes: the doors refresh the status line, the loop presents the outer
   frame and asks again (step 1).

The owing (rule 1's accumulator and all of rule 2 but the paused step and the start screen) is
``RecordedFramePacer`` (glitchygames/replay/pacer.py), shared with every player of a recording;
the viewer keeps the cadence, the keys, the snapping of tick times and the start screen, and
tells the pacer the speed (``ReplayControls.speed``) and its tick period
(``CONTROL_TICK_SECONDS``). Each tick's work budget is a ``TickBudget`` on the viewer's clock.

The accumulator only decides when inner frames run, never what they do, so a watched replay is
as exact as a headless one. Headless replays have no viewer loop: they never hold and run
unpaced. Step back restarts the replay process instead, which rebuilds the inner game up to
frame N-1 before the viewer's first tick (glitchygames/replay/rebuild.py; no outer tick opens
during the rebuild). Later users of the same contract: Part 3's playback scopes (an inner replay
under a live outer game) and audio/video capture (inner frames handed to a sink rather than
presented).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

from glitchygames import clock
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, ControlCadence, ReplayControls

# The pacing constants moved to glitchygames/replay/pacer.py with the owing; importing them here
# keeps `from glitchygames.replay.viewer import MAX_OWED_INNER_FRAMES` (and the others) working,
# so __all__ re-exports them.
from glitchygames.replay.pacer import (
    BEHIND_SPEED_FRACTION,
    EFFECTIVE_SPEED_WINDOW_TICKS,
    INNER_FRAME_BUDGET_SECONDS,
    MAX_OWED_INNER_FRAMES,
    STALL_TICK_SECONDS,
    RecordedFramePacer,
    TickBudget,
)
from glitchygames.timing import FastTimer

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from glitchygames.scenes import SceneManager

__all__ = [
    'BEHIND_SPEED_FRACTION',
    'EFFECTIVE_SPEED_WINDOW_TICKS',
    'INNER_FRAME_BUDGET_SECONDS',
    'MAX_OWED_INNER_FRAMES',
    'NANOSECONDS_PER_SECOND',
    'STALL_TICK_SECONDS',
    'TICK_SNAP_WINDOW_SECONDS',
    'ReplayViewer',
    'run_watched_replay_async',
    'sleep_coarsely',
    'sleep_for',
]

# A tick this close to one period after the last counts as exactly one period (error carried)
TICK_SNAP_WINDOW_SECONDS = 0.002
NANOSECONDS_PER_SECOND = 1_000_000_000

# The viewer's sleeps: the engine's sleep-then-spin timer (finer than pygame.time.wait's
# whole milliseconds); it keeps no state between sleeps
_SLEEP_TIMER = FastTimer()


def sleep_coarsely(*, seconds: float, sleep: Callable[[float], None] | None = None) -> None:
    """Sleep ``seconds`` without spinning (one plain sleep): the wait while nothing runs.

    Args:
        seconds: How long (nothing happens when not positive).
        sleep: The sleep (tests pass a fake); None is glitchygames/clock.py's raw sleep, looked
            up when called.

    """
    if seconds > 0:
        (clock.raw_sleep if sleep is None else sleep)(seconds)


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
        ticks_externally: True when something outside waits for each tick (a browser's
            animation frames, ``run_watched_replay_async``): a tick then opens at once, never
            sleeping or following ``cadence``, and owes the real time since the last, so the
            replay keeps its speed at any display rate.

    """

    def __init__(
        self: Self,
        *,
        controls: ReplayControls,
        measured_seconds: Callable[[], float] | None = None,
    ) -> None:
        """Start with no tick open; the first tick is due at once.

        Args:
            controls: The viewer's controls.
            measured_seconds: The viewer's real-time clock; None is
                ``glitchygames.clock.measured_seconds``, looked up when read. The schedule tool
                (scripts/replay_schedule.py) gives an ideal clock, so the real accumulator runs
                without a display or real time.

        """
        self.controls = controls
        self._measured_seconds = measured_seconds
        self.cadence = ControlCadence()
        self.ticks_externally = False
        self._is_tick_open = False
        # The owing (rules 1 and 2), told the speed and the viewer's 60 Hz tick period
        self._pacer = RecordedFramePacer(nominal_tick_seconds=CONTROL_TICK_SECONDS)
        # The open tick's real-time work budget (INNER_FRAME_BUDGET_SECONDS), on the viewer's clock
        self._tick_budget = TickBudget(
            length_seconds=INNER_FRAME_BUDGET_SECONDS,
            measured_seconds=measured_seconds,
            started_at_seconds=0.0,
        )
        # The tick time the next tick's elapsed time is measured from (snapping carries error)
        self._last_tick_seconds: float | None = None
        # The viewer's key presses and releases (event type, key) read since the last tick
        self._key_events: list[tuple[int, int]] = []

    @property
    def accumulated_seconds(self: Self) -> float:
        """Inner game time owed to the inner game (the pacer's accumulator).

        Real time times speed, consumed by each inner frame's recorded duration. Settable, so a
        test can owe a chosen amount.
        """
        return self._pacer.accumulated_seconds

    @accumulated_seconds.setter
    def accumulated_seconds(self: Self, seconds: float) -> None:
        self._pacer.accumulated_seconds = seconds

    @property
    def last_inner_frame_ran_behind(self: Self) -> bool:
        """Whether the inner frame ``should_run_inner_frame`` last allowed ran while behind.

        The accumulator owed the frame's recorded duration plus a whole tick of inner time (the
        speed times ``CONTROL_TICK_SECONDS``), read before the frame consumed it; False for a
        frame run without the accumulator (a paused step, frame 0 at the start screen). Rule 2's
        one-frame limit uses the same condition; the schedule tool (scripts/replay_schedule.py)
        derives behind itself and checks this against it.
        """
        return self._pacer.last_frame_ran_behind

    @property
    def is_behind(self: Self) -> bool:
        """True while the inner game cannot keep up with the speed (in the last second)."""
        return self._pacer.is_behind

    def effective_speed(self: Self) -> float:
        """Return the speed the inner game really ran at over the last second of ticks.

        Returns:
            Inner seconds run over real seconds passed (0.0 before any time passed).

        """
        return self._pacer.effective_speed()

    def real_speed_if_behind(self: Self) -> float | None:
        """Return the real speed when the inner game meaningfully cannot keep up, for the status.

        Returns:
            ``effective_speed()`` while behind and below ``BEHIND_SPEED_FRACTION`` of the
            speed, else None (keeping up, slightly slow, or no running ticks measured yet).

        """
        return self._pacer.real_speed_if_behind(speed=self.controls.speed)

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
        now = self._read_measured_seconds()
        if self.ticks_externally:
            return self._open_tick(now=now)
        remaining_seconds = self.cadence.next_tick_seconds(now=now) - now
        if remaining_seconds > 0:
            if is_inner_running:
                sleep_for(seconds=remaining_seconds)
            else:
                sleep_coarsely(seconds=remaining_seconds)
            now = self._read_measured_seconds()
        self.cadence.tick_is_due(now=now)
        return self._open_tick(now=now)

    def _read_measured_seconds(self: Self) -> float:
        """Read the viewer's real-time clock (the one given, else the engine's).

        Returns:
            Seconds (only differences mean anything).

        """
        if self._measured_seconds is None:
            return clock.measured_seconds()
        return self._measured_seconds()

    def _open_tick(self: Self, *, now: float) -> float:
        """Open a tick at ``now``.

        Returns:
            ``now``.

        """
        self._is_tick_open = True
        self._tick_budget = TickBudget(
            length_seconds=INNER_FRAME_BUDGET_SECONDS,
            measured_seconds=self._measured_seconds,
            started_at_seconds=now,
        )
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
        self._pacer.pay(
            elapsed_seconds=elapsed_seconds,
            speed=self.controls.speed,
            is_running=is_inner_running,
        )

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
        self._pacer.last_frame_ran_behind = False
        if is_inner_over:
            controls.take_step()
            return self._close_tick()
        if controls.awaiting_start:
            # Frame 0 runs first, so the start screen shows its picture
            return is_first_inner_frame or self._close_tick()
        if controls.paused:
            return controls.take_step() or self._close_tick()
        if self._pacer.should_run_frame(
            frame_seconds=inner_frame_seconds, speed=controls.speed, budget=self._tick_budget
        ):
            return True
        # The pacer closed its tick (not owed yet, rule 2, or the budget is spent)
        self._is_tick_open = False
        return False

    def _close_tick(self: Self) -> bool:
        """Close the open tick: the loop presents the outer frame next.

        The pacer closes its tick too (``RecordedFramePacer.close_tick``: the effective-speed
        window).

        Returns:
            False (no inner frame runs).

        """
        self._is_tick_open = False
        return self._pacer.close_tick()


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
