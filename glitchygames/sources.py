"""The engine's doors: every input the engine takes from the outside world.

The engine reads events, frame time, polled input, devices, saves, the clocks and the random seed
only through the active ``EngineSources``. Live play uses ``LiveSources``
(glitchygames/live_sources.py); ``--record-trace`` wraps them in ``RecordingSources``
(glitchygames/recording.py); ``--replay-trace`` installs ``ReplaySources``
(glitchygames/replay/driver.py). Everything downstream of the doors runs unchanged, so a replay
goes through the real engine.

The registry is module state, like glitchygames/randomness.py's streams, so engine code, games
and widgets reach the active sources without an engine reference. ``install_sources`` may only be
called before the first frame (a run never mixes live and recorded input); in-game playback pushes
scoped sources on top instead (``push_scoped_sources``; glitchygames/replay/playback.py), which
are active until popped (``pop_scoped_sources``). ``GameEngine.__init__`` calls
``reset_sources()`` so each run starts with fresh doors.

This module is a leaf (see the layering rule in plans/2026-10-19-gameplay-replay-core.md, Task
2): any module may import it, and it imports no package module at module level except
glitchygames.randomness.
"""

from __future__ import annotations

import dataclasses
import weakref
from typing import TYPE_CHECKING, Protocol

from glitchygames.randomness import engine_random_seed

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    import pygame

    # Type only: glitchygames.input's package __init__ imports input.rumble, which comes to
    # import this module, so a runtime import here would be a cycle (this module is a leaf)
    from glitchygames.input.devices import DeviceRegistry
    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene

    # Type only: glitchygames.state's package __init__ imports state.sandbox, which imports
    # this module, so a runtime import here would be a cycle (this module is a leaf);
    # state.manager also imports glitchygames.clock, which imports this module
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent


class SourcesAlreadyRunningError(RuntimeError):
    """install_sources() was called after the first frame started."""


class SourcesAlreadyInstalledError(RuntimeError):
    """install_sources() or push_scoped_sources() was given sources already in use.

    Installed, or pushed as scoped sources: using them again would tell them ``on_installed``
    twice without an ``on_uninstalled`` between (and ``reset_sources`` would uninstall them
    twice).
    """


class NoScopedSourcesError(RuntimeError):
    """pop_scoped_sources() was called with no scoped sources pushed."""


class EngineSources(Protocol):
    """The doors (see the module docstring)."""

    random_seed: int

    @property
    def opened_save_namespaces(self) -> Mapping[str, SaveManager]:
        """Every save store these doors opened so far, by namespace (a recording's header)."""
        ...

    @property
    def captures_scene_starts(self) -> bool:
        """True when scenes constructed now capture their starts (glitchygames/scene_start.py).

        Only while a start can be used: a run recorded with ``--record-trace`` from its start
        (so the first scene's start is in frame 0) and while recording, a ``--rebaseline``
        replay (its new recording holds them) and in-game playback. Live play and a plain replay
        capture nothing.
        """
        ...

    @property
    def stop_requested(self) -> bool:
        """True when the sources want the run to end (a replay reached its end)."""
        ...

    def on_installed(self) -> None:
        """Called by install_sources() when these sources become the run's doors."""
        ...

    def on_uninstalled(self) -> None:
        """Called by reset_sources() when these sources stop being the run's doors."""
        ...

    def pump_events(self) -> list[pygame.event.Event]:
        """Return the next batch of events (the only read of the event queue)."""
        ...

    def frame_seconds(self, *, measured: float) -> float:
        """Return the frame time logic receives, given the measured start-to-start time."""
        ...

    def performance_frame_seconds(self, *, measured: float, frame_seconds: float) -> float:
        """Return the frame time FPS events and the performance statistics use.

        ``frame_seconds`` is what ``frame_seconds()`` returned for the same measurement: live
        play and a ``--replay-fps recorded`` replay use it, a ``--replay-fps real`` replay uses
        ``measured`` (glitchygames/replay/driver.py).
        """
        ...

    def paced_frame_seconds(self) -> float | None:
        """Return how long the frame starting now is paced to, asked once per frame.

        ``None`` paces to the target FPS as always (live play); ``0.0`` does not pace at all (a
        headless replay: its frame times come from the recording, so waiting would only take
        real time; a watched replay, which paces itself by holding the loop in ``hold_frame``);
        a positive number of seconds paces to that period instead of the target's
        (SceneManager._handle_frame_pacing).
        """
        ...

    def hold_frame(self) -> bool:
        """Return True to run no frame now, asked before each frame starts.

        Live play never holds. A watched replay is driven by its viewer's outer tick
        (glitchygames/replay/viewer.py): a call with no tick open sleeps until the next one (so
        the loop never spins) and reads the viewer's keys; the open tick then answers False for
        each recorded frame its accumulator pays for and True when it closes (also at the start
        screen, while paused but for a step, and at the end or a divergence).
        ``SceneManager.start`` presents the latest frame then instead of running one.
        """
        ...

    @property
    def presents_frames(self) -> bool:
        """False when the frames the loop runs are not presented as they run.

        A watched replay runs its recorded frames in full but presents only the latest, once
        per outer tick of its viewer (glitchygames/replay/viewer.py), as a held frame.
        """
        ...

    @property
    def draws_overlay(self) -> bool:
        """True when ``draw_overlay`` draws anything (a watched replay's status bar).

        ``SceneManager._present_frame`` then presents a copy of each frame with it drawn on,
        as for the debug overlay; when False it never calls ``draw_overlay``.
        """
        ...

    def draw_overlay(self, *, surface: pygame.Surface) -> None:
        """Draw these doors' own overlay on the presented frame, after the debug overlay.

        Never on a screenshot or a traced frame (SceneManager._present_frame).
        """
        ...

    def input_snapshot(self) -> InputSnapshot:
        """Return this frame's polled input, asked once per frame right after the first pump."""
        ...

    def devices(self) -> DeviceRegistry:
        """Return the device registry (every joystick/controller enumeration and opening)."""
        ...

    def saves(self, *, namespace: str) -> SaveManager:
        """Return the save store for ``namespace`` (a game's app name; glitchygames/state)."""
        ...

    def wall_clock_time(self) -> datetime:
        """Return the current wall-clock time (timezone-aware UTC); glitchygames/clock.py."""
        ...

    def control_events_for_frame(self, *, frame_number: int) -> list[ControlEvent]:
        """Return the control events to apply at frame ``frame_number``'s supervisor slot.

        Live play has none; a replay returns the ones its recording holds for that frame
        (glitchygames/supervision.py).
        """
        ...

    def end_frame(
        self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
    ) -> None:
        """Called once after each frame (recording writes it, replay compares it).

        ``control_events`` are the control events recorded in the frame, in order.
        """
        ...


class SaveStoreOpenedObserver(Protocol):
    """Told each time a game opens a save store (``open_saves``), before it can write to it."""

    def on_save_store_opened(self, *, namespace: str, store: SaveManager) -> None:
        """Look at ``store`` as opened (a scene start in capture snapshots it; scene_start.py).

        Args:
            namespace: The store's namespace (the game's app name).
            store: The store the doors returned.

        """
        ...


@dataclasses.dataclass
class _SourcesRegistry:
    installed: EngineSources | None = None
    scoped: list[EngineSources] = dataclasses.field(default_factory=list)
    frames_started: bool = False
    frame_clock_seconds: float = 0.0
    # Weak: an observer nobody else keeps (a scene built and dropped before its setup) goes away
    save_store_observers: weakref.WeakSet[SaveStoreOpenedObserver] = dataclasses.field(
        default_factory=weakref.WeakSet
    )


_REGISTRY = _SourcesRegistry()


def active_sources() -> EngineSources:
    """Return the doors in use: scoped sources, else installed ones, else fresh live ones.

    The fresh live sources take the run's master seed from
    ``glitchygames.randomness.engine_random_seed()``, which draws (and sets) one if nothing has
    seeded the engine random streams yet.

    Returns:
        The active sources.

    """
    if _REGISTRY.scoped:
        return _REGISTRY.scoped[-1]
    if _REGISTRY.installed is None:
        # The one function-level import of the door modules, deferred on purpose: this module
        # is a leaf, and live_sources is not. Today live_sources imports only pygame, but later
        # tasks give it the input, devices and saves modules, which import this module, so a
        # top-level import here would become a cycle. It runs only when nothing was installed
        # (unit tests, tools).
        from glitchygames.live_sources import LiveSources

        _REGISTRY.installed = LiveSources(random_seed=engine_random_seed())
    return _REGISTRY.installed


def install_sources(*, sources: EngineSources) -> None:
    """Make ``sources`` the run's doors; allowed only before the first frame.

    Sources installed earlier are told they are replaced (``on_uninstalled``) before the new ones
    are told they are installed (``on_installed``). Installing the sources that are already
    installed is refused rather than ignored, so ``on_installed`` never runs twice without an
    ``on_uninstalled`` between.

    Args:
        sources: The doors to read from.

    Raises:
        SourcesAlreadyRunningError: If a frame has already started.
        SourcesAlreadyInstalledError: If ``sources`` are already the installed sources.

    """
    if _REGISTRY.frames_started:
        message = 'install_sources() is allowed only before the first frame'
        raise SourcesAlreadyRunningError(message)
    if _REGISTRY.installed is sources:
        message = 'install_sources() was given the sources that are already installed'
        raise SourcesAlreadyInstalledError(message)
    if _REGISTRY.installed is not None:
        _REGISTRY.installed.on_uninstalled()
    _REGISTRY.installed = sources
    sources.on_installed()


def push_scoped_sources(*, sources: EngineSources) -> None:
    """Make ``sources`` the active doors on top of the installed ones (in-game playback).

    Allowed at any time, frames started or not: a playback scope (glitchygames/replay/
    playback.py) serves a recording to a rebuilt scene while the run's doors stay installed
    underneath, and ``pop_scoped_sources`` ends it. ``sources`` are told they are installed
    (``on_installed``) before they become active.

    Args:
        sources: The scoped doors.

    Raises:
        SourcesAlreadyInstalledError: If ``sources`` are the installed sources or already
            pushed.

    """
    if sources is _REGISTRY.installed or any(
        scoped_sources is sources for scoped_sources in _REGISTRY.scoped
    ):
        message = 'push_scoped_sources() was given sources that are already in use'
        raise SourcesAlreadyInstalledError(message)
    sources.on_installed()
    _REGISTRY.scoped.append(sources)


def pop_scoped_sources() -> EngineSources:
    """Remove the scoped sources pushed last; they are told they are uninstalled.

    Returns:
        The sources removed.

    Raises:
        NoScopedSourcesError: If no scoped sources are pushed.

    """
    if not _REGISTRY.scoped:
        message = 'pop_scoped_sources() was called with no scoped sources pushed'
        raise NoScopedSourcesError(message)
    sources = _REGISTRY.scoped.pop()
    sources.on_uninstalled()
    return sources


def has_scoped_sources() -> bool:
    """Return True while scoped sources are pushed (a playback scope serves the frame).

    Returns:
        Whether ``active_sources()`` returns scoped sources rather than the installed ones.

    """
    return bool(_REGISTRY.scoped)


def mark_frames_started() -> None:
    """Record that the frame loop has started (install_sources is refused from now on)."""
    _REGISTRY.frames_started = True


def advance_frame_clock(*, seconds: float) -> None:
    """Add one closed frame's dt to the frame clock (SceneManager._finish_frame)."""
    _REGISTRY.frame_clock_seconds += seconds


def observe_save_store_openings(*, observer: SaveStoreOpenedObserver) -> None:
    """Tell ``observer`` of every save store opened from now on (held weakly).

    Args:
        observer: The observer.

    """
    _REGISTRY.save_store_observers.add(observer)


def stop_observing_save_store_openings(*, observer: SaveStoreOpenedObserver) -> None:
    """Stop telling ``observer`` of save stores opened (nothing if it was not observing).

    Args:
        observer: The observer.

    """
    _REGISTRY.save_store_observers.discard(observer)


def notify_save_store_opened(*, namespace: str, store: SaveManager) -> None:
    """Tell every observer a save store was opened (glitchygames.state.open_saves calls it).

    Args:
        namespace: The store's namespace.
        store: The store the doors returned.

    """
    # A copy: an observer may stop observing while it is told
    for observer in list(_REGISTRY.save_store_observers):
        observer.on_save_store_opened(namespace=namespace, store=store)


def set_frame_clock_seconds(*, seconds: float) -> None:
    """Set the frame clock (a scene rebuilt from its start; glitchygames/scene_start.py).

    Args:
        seconds: The frame clock's new reading.

    """
    _REGISTRY.frame_clock_seconds = seconds


def frame_clock_seconds() -> float:
    """Return the sum of every closed frame's dt this run.

    It replays exactly (dt comes through the frame-time door) and never pauses. Read it through
    glitchygames/clock.py, which re-exports it.

    Returns:
        Seconds.

    """
    return _REGISTRY.frame_clock_seconds


def reset_sources() -> None:
    """Forget every installed and scoped source and the frame clock (a new run, or a test).

    The frame's polled input is not reset here (this leaf may not import glitchygames.input):
    callers also call glitchygames.input.state.reset_current_input().
    """
    for sources in [*_REGISTRY.scoped, _REGISTRY.installed]:
        if sources is not None:
            sources.on_uninstalled()
    _REGISTRY.installed = None
    _REGISTRY.scoped.clear()
    _REGISTRY.frames_started = False
    _REGISTRY.frame_clock_seconds = 0.0
    _REGISTRY.save_store_observers.clear()
