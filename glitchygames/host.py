"""The game host: an outer game grafted on top of every live run (the inner game).

The host is transparent: the inner game (its scenes and the scene manager) never sees it, and
today it changes nothing. It is where an outer layer can later act on the game without the
game knowing (AI input, event and call injection; plans/2026-10-23-game-host-and-browser-runner.md).
It has two parts:

- ``HostSources``: doors (glitchygames/sources.py) installed around a live run's doors,
  beneath the recorder. A live run reads through ``HostSources(inner=LiveSources)``, and with
  ``--record-trace`` through ``RecordingSources(inner=HostSources(inner=LiveSources))``. Every
  member forwards to ``inner`` unchanged. Being beneath the recorder, whatever the host adds,
  hides or rewrites later is what a recording holds, so the recording replays exactly without
  the host. Replays keep their own doors: there the replay viewer (glitchygames/replay/viewer.py)
  is the outer game.
- ``GameHost``: owns those doors and drives the inner game's frames. ``run`` is the blocking
  frame loop (``SceneManager.start``, paced by the engine's timer); ``run_async`` gives control
  back between frames (a browser), running at most one inner frame per outer tick, paced by
  ``TickPacer`` at the game's target frame rate whatever the tick rate (a 60 FPS game runs every
  second tick of a 120 Hz display). Its ticks come from the caller, as timestamps, so the host
  never reads a clock itself.

As in the replay viewer (an inner replay under an outer viewer), the outer tick only decides
when inner frames run, never what they do.
"""

from __future__ import annotations

import collections
import logging
import statistics
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

from glitchygames.live_sources import LiveSources
from glitchygames.sources import active_sources

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from datetime import datetime

    import pygame

    from glitchygames.input.devices import DeviceRegistry
    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene, SceneManager
    from glitchygames.sources import EngineSources
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent

LOG = logging.getLogger('game.host')
LOG.addHandler(logging.NullHandler())

# How many recent outer ticks the measured tick interval (a display's refresh) is taken over
TICK_INTERVAL_SAMPLES = 240
# The measured tick rate is logged once, after this many ticks (startup hitches have passed)
TICKS_BEFORE_LOGGING_RATE = 120


class HostSources:  # ruff: ignore[too-many-public-methods] - every EngineSources member
    """Doors that forward everything to ``inner`` (implements EngineSources).

    The host's layer of the doors: installed around a live run's doors, beneath the recorder.
    Today every member forwards unchanged.

    Attributes:
        inner: The doors read through (the run's live doors).
        random_seed: The run's master seed (``inner``'s).

    """

    def __init__(self: Self, *, inner: EngineSources) -> None:
        """Wrap ``inner``.

        Args:
            inner: The doors to read through.

        """
        self.inner = inner
        self.random_seed = inner.random_seed

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """Every save store ``inner`` opened so far, by namespace."""
        return self.inner.opened_save_namespaces

    @property
    def first_open_save_snapshots(self: Self) -> Mapping[str, dict[str, Any]]:
        """``inner``'s first-open save snapshots, when they are live doors (a recorded run).

        ``GameEngine.start_trace_recording`` reads them through the host
        (``LiveSources.first_open_save_snapshots``); other doors keep none.
        """
        if isinstance(self.inner, LiveSources):
            return self.inner.first_open_save_snapshots
        return MappingProxyType({})

    @property
    def captures_scene_starts(self: Self) -> bool:
        """Whether ``inner`` captures scene starts."""
        return self.inner.captures_scene_starts

    @property
    def stop_requested(self: Self) -> bool:
        """Whether ``inner`` wants the run to end."""
        return self.inner.stop_requested

    def on_installed(self: Self) -> None:
        """Tell ``inner`` it is the run's doors, behind these."""
        self.inner.on_installed()

    def on_uninstalled(self: Self) -> None:
        """Tell ``inner`` it stopped being the run's doors."""
        self.inner.on_uninstalled()

    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Return ``inner``'s next batch, unchanged.

        Returns:
            The batch, in queue order.

        """
        return self.inner.pump_events()

    def frame_seconds(self: Self, *, measured: float) -> float:
        """Return ``inner``'s frame time for logic.

        Returns:
            Seconds.

        """
        return self.inner.frame_seconds(measured=measured)

    def performance_frame_seconds(self: Self, *, measured: float, frame_seconds: float) -> float:
        """Return ``inner``'s frame time for FPS events and the performance statistics.

        Returns:
            Seconds.

        """
        return self.inner.performance_frame_seconds(measured=measured, frame_seconds=frame_seconds)

    def paced_frame_seconds(self: Self) -> float | None:
        """Return how ``inner`` paces the frame starting now.

        Returns:
            Seconds, or None for the target FPS.

        """
        return self.inner.paced_frame_seconds()

    def hold_frame(self: Self) -> bool:
        """Return whether ``inner`` holds the frame.

        Returns:
            True to run no frame now.

        """
        return self.inner.hold_frame()

    @property
    def presents_frames(self: Self) -> bool:
        """Whether ``inner`` presents the frames as they run."""
        return self.inner.presents_frames

    @property
    def draws_overlay(self: Self) -> bool:
        """Whether ``inner`` draws an overlay of its own."""
        return self.inner.draws_overlay

    def draw_overlay(self: Self, *, surface: pygame.Surface) -> None:
        """Let ``inner`` draw its overlay."""
        self.inner.draw_overlay(surface=surface)

    def input_snapshot(self: Self) -> InputSnapshot:
        """Return ``inner``'s polled input, unchanged.

        Returns:
            The snapshot.

        """
        return self.inner.input_snapshot()

    def devices(self: Self) -> DeviceRegistry:
        """Return ``inner``'s device registry.

        Returns:
            The registry.

        """
        return self.inner.devices()

    def saves(self: Self, *, namespace: str) -> SaveManager:
        """Return ``inner``'s save store for ``namespace``.

        Args:
            namespace: The game's app name.

        Returns:
            The store.

        """
        return self.inner.saves(namespace=namespace)

    def wall_clock_time(self: Self) -> datetime:
        """Return ``inner``'s wall-clock time.

        Returns:
            Timezone-aware time.

        """
        return self.inner.wall_clock_time()

    def control_events_for_frame(self: Self, *, frame_number: int) -> list[ControlEvent]:
        """Return the control events ``inner`` schedules for ``frame_number``.

        Returns:
            The control events.

        """
        return self.inner.control_events_for_frame(frame_number=frame_number)

    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        processing_seconds: float | None = None,
    ) -> None:
        """Let ``inner`` end the frame."""
        self.inner.end_frame(
            frame_number=frame_number,
            dt=dt,
            scene=scene,
            control_events=control_events,
            processing_seconds=processing_seconds,
        )


class TickPacer:
    """Decides, at each outer tick, whether the inner game runs a frame (``GameHost.run_async``).

    Each tick adds the time since the previous tick to an accumulator. A frame runs when it
    holds at least the frame period less half a tick (so a period that is a whole number of
    ticks runs exactly every that many ticks, despite jitter), and then pays one period. A frame
    owed more than one period after paying (a stall: a background tab, a hitch) re-anchors
    instead of running a burst of frames, as the engine's own pacing does. A period of 0 or less
    runs a frame every tick. The first tick always runs one.

    It also keeps the median of the recent tick intervals: the rate the outer ticks really
    come at (a browser's animation frames follow the display's refresh, or Safari's 60 Hz cap).
    """

    def __init__(self: Self) -> None:
        """Start with no tick seen."""
        self._previous_tick_seconds: float | None = None
        self._accumulated_seconds = 0.0
        self._tick_intervals: collections.deque[float] = collections.deque(
            maxlen=TICK_INTERVAL_SAMPLES
        )

    def should_run_frame(self: Self, *, tick_seconds: float, period_seconds: float) -> bool:
        """Account for one outer tick and return whether an inner frame runs on it.

        Args:
            tick_seconds: The tick's timestamp (any monotonic clock, in seconds).
            period_seconds: The inner game's frame period (0 or less: every tick).

        Returns:
            True when an inner frame runs on this tick.

        """
        if self._previous_tick_seconds is None:
            self._previous_tick_seconds = tick_seconds
            return True
        interval_seconds = tick_seconds - self._previous_tick_seconds
        self._previous_tick_seconds = tick_seconds
        self._tick_intervals.append(interval_seconds)
        if period_seconds <= 0.0:
            return True
        self._accumulated_seconds += interval_seconds
        half_tick_seconds = self.measured_tick_seconds() / 2
        if self._accumulated_seconds < period_seconds - half_tick_seconds:
            return False
        self._accumulated_seconds -= period_seconds
        if self._accumulated_seconds >= period_seconds:
            # More than a whole frame behind after this one: start over rather than burst
            self._accumulated_seconds = 0.0
        return True

    def measured_tick_seconds(self: Self) -> float:
        """Return the median recent tick interval (0.0 before two ticks).

        Returns:
            Seconds.

        """
        if not self._tick_intervals:
            return 0.0
        return statistics.median(self._tick_intervals)

    @property
    def tick_count(self: Self) -> int:
        """How many tick intervals have been measured (ticks seen, less the first)."""
        return len(self._tick_intervals)


class GameHost:
    """The outer game on top of a live run: its doors (``HostSources``) and its frame drivers."""

    def __init__(self: Self, *, sources: HostSources) -> None:
        """Host a run that reads through ``sources``.

        Args:
            sources: The host's doors, installed as (or beneath) the run's doors.

        """
        self.sources = sources
        self.pacer = TickPacer()

    def run(self: Self, *, scene_manager: SceneManager) -> None:
        """Run the inner game's frames in the blocking loop, paced by the engine's timer.

        Args:
            scene_manager: The inner game's scene manager.

        """
        scene_manager.start()

    async def run_async(
        self: Self,
        *,
        scene_manager: SceneManager,
        wait_for_tick: Callable[[], Awaitable[float]],
    ) -> None:
        """Run the inner game's frames, giving control back to the caller between ticks.

        Each outer tick is one awaited ``wait_for_tick()`` (in a browser: the next animation
        frame), which returns the tick's timestamp in seconds. ``TickPacer`` decides whether
        the tick runs an inner frame, at the doors' pacing (``paced_frame_seconds``) or the
        scene manager's ``target_fps``. Frames run unpaced (``run_frame_step(paced=False)``):
        the wait for the tick is their pacing.

        Args:
            scene_manager: The inner game's scene manager.
            wait_for_tick: Waits for the next outer tick and returns its timestamp (seconds).

        """
        frame_start_seconds = scene_manager.begin_frames()
        logged_rate = False
        while scene_manager.should_run_frames():
            tick_seconds = await wait_for_tick()
            if not self.pacer.should_run_frame(
                tick_seconds=tick_seconds,
                period_seconds=_frame_period_seconds(scene_manager=scene_manager),
            ):
                continue
            frame_start_seconds = scene_manager.run_frame_step(
                frame_start_seconds=frame_start_seconds, paced=False
            )
            if not logged_rate and self.pacer.tick_count >= TICKS_BEFORE_LOGGING_RATE:
                logged_rate = True
                tick_seconds_measured = self.pacer.measured_tick_seconds()
                LOG.info(
                    'Outer ticks at %.1f Hz (measured); inner frames target %s FPS',
                    1.0 / tick_seconds_measured if tick_seconds_measured > 0 else 0.0,
                    scene_manager.target_fps,
                )
        scene_manager.end_frames()


def _frame_period_seconds(*, scene_manager: SceneManager) -> float:
    """Return the inner game's frame period: the doors' pacing, else the target FPS's.

    Returns:
        Seconds (0.0: every tick, for an uncapped target or unpaced doors).

    """
    paced_seconds = active_sources().paced_frame_seconds()
    if paced_seconds is not None:
        return paced_seconds
    if scene_manager.target_fps <= 0:
        return 0.0
    return 1.0 / scene_manager.target_fps
