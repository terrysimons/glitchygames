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
scoped sources on top instead (``push_scoped_sources``, Part 3 of
plans/2026-10-19-gameplay-replay-implementation.md). ``GameEngine.__init__`` calls
``reset_sources()`` so each run starts with fresh doors.

This module is a leaf (see the layering rule in plans/2026-10-19-gameplay-replay-core.md, Task
2): any module may import it, and it imports no package module at module level except
glitchygames.randomness.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Protocol

from glitchygames.randomness import engine_random_seed

if TYPE_CHECKING:
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


class SourcesAlreadyRunningError(RuntimeError):
    """install_sources() was called after the first frame started."""


class SourcesAlreadyInstalledError(RuntimeError):
    """install_sources() was called with the sources that are already installed."""


class EngineSources(Protocol):
    """The doors (see the module docstring)."""

    random_seed: int

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

    def elapsed_seconds(self) -> float:
        """Return a monotonic reading in seconds (only differences mean anything)."""
        ...

    def end_frame(self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        """Called once after each frame (recording writes it, replay compares it)."""
        ...


@dataclasses.dataclass
class _SourcesRegistry:
    installed: EngineSources | None = None
    scoped: list[EngineSources] = dataclasses.field(default_factory=list)
    frames_started: bool = False
    frame_clock_seconds: float = 0.0


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


def mark_frames_started() -> None:
    """Record that the frame loop has started (install_sources is refused from now on)."""
    _REGISTRY.frames_started = True


def advance_frame_clock(*, seconds: float) -> None:
    """Add one closed frame's dt to the frame clock (SceneManager._finish_frame)."""
    _REGISTRY.frame_clock_seconds += seconds


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
