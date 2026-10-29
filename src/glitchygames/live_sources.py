"""The live doors (glitchygames/sources.py).

Pygame's queue, the measured frame time, pygame's polled input, real devices, real save files
on disk and the real wall clock.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Self

import pygame

from glitchygames import clock
from glitchygames.input.devices import LiveDeviceRegistry
from glitchygames.input.state import capture_live_snapshot
from glitchygames.sources import without_discarded_scope_posts
from glitchygames.state.manager import DiskSaveManager
from glitchygames.state.sandbox import save_namespace_snapshot

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent


class LiveSources:
    """The live doors (implements glitchygames.sources.EngineSources)."""

    def __init__(
        self: Self,
        *,
        random_seed: int,
        use_fastevents: bool = False,
        captures_scene_starts: bool = False,
    ) -> None:
        """Create the live doors.

        Args:
            random_seed: The run's master seed (glitchygames/randomness.py).
            use_fastevents: Read events with pygame.fastevent when pygame has it
                (``GameEngine.USE_FASTEVENTS``; pygame < 2.2 only).
            captures_scene_starts: True when the run will be recorded (``--record-trace``):
                recording starts after the first scene is built and set up, so the live doors
                capture scene starts from the run's start and frame 0 holds the first scene's
                (glitchygames/scene_start.py). False for live play.

        """
        self.random_seed = random_seed
        # The EngineSources property, as a plain attribute: set once, for the whole run
        self.captures_scene_starts = captures_scene_starts
        self._use_fastevents = use_fastevents
        self._devices = LiveDeviceRegistry()
        # Stores games opened, by namespace (opened_save_namespaces)
        self._opened_save_namespaces: dict[str, DiskSaveManager] = {}
        # Each store as it was first opened, before the game could write to it, in a run that
        # will be recorded (first_open_save_snapshots)
        self._first_open_save_snapshots: dict[str, dict[str, Any]] = {}

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """Every store opened so far, by namespace (read-only; a recording's header)."""
        return MappingProxyType(self._opened_save_namespaces)

    @property
    def first_open_save_snapshots(self: Self) -> Mapping[str, dict[str, Any]]:
        """Each store as it was first opened, by namespace (read-only), in a recorded run.

        Kept only while ``captures_scene_starts`` (a run started with ``--record-trace``):
        recording starts once the first scene is built and set up, so a store that scene wrote
        to (a ``setup()`` that adds one to a saved count) is in the recording's header as it
        was before, which is what the replayed scene reads again
        (``GameEngine.start_trace_recording``). Empty otherwise.
        """
        return MappingProxyType(self._first_open_save_snapshots)

    @property
    def stop_requested(self: Self) -> bool:
        """Live play never asks to stop."""
        return False

    def on_installed(self: Self) -> None:
        """Nothing to start for live play."""

    def on_uninstalled(self: Self) -> None:
        """Nothing to stop for live play."""

    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Take every event from SDL's queue, but a playback scope's posts left behind.

        A playback scope's own posts still queued when it ended are dropped
        (``sources.without_discarded_scope_posts``; glitchygames/replay/playback.py, rule 4).

        Returns:
            The batch, in queue order.

        """
        # To use events in a different thread, use the fastevent package from pygame.
        # if you're using pygame < 2.2, you'll need to use pygame.fastevent.
        fastevent = getattr(pygame, 'fastevent', None)
        if self._use_fastevents and fastevent is not None:
            return without_discarded_scope_posts(events=list(fastevent.get()))
        return without_discarded_scope_posts(events=list(pygame.event.get()))

    def frame_seconds(self: Self, *, measured: float) -> float:
        """Live logic receives the measured frame time.

        Returns:
            ``measured``, unchanged.

        """
        return measured

    def performance_frame_seconds(self: Self, *, measured: float, frame_seconds: float) -> float:
        """Live statistics use logic's frame time (the measurement, as frame_seconds returns it).

        Returns:
            ``frame_seconds``, unchanged.

        """
        del measured
        return frame_seconds

    def paced_frame_seconds(self: Self) -> float | None:
        """Live play paces to the target FPS (``--headless`` included).

        Returns:
            None.

        """
        return None

    def hold_frame(self: Self) -> bool:
        """Live play never holds a frame.

        Returns:
            False.

        """
        return False

    @property
    def presents_frames(self: Self) -> bool:
        """Live play presents every frame."""
        return True

    @property
    def draws_overlay(self: Self) -> bool:
        """Live play draws no overlay of its own."""
        return False

    def draw_overlay(self: Self, *, surface: pygame.Surface) -> None:
        """Draw nothing (``draws_overlay`` is False, so the scene manager never calls this)."""
        # Live play has nothing to draw (EngineSources signature)
        del surface

    def input_snapshot(self: Self) -> InputSnapshot:
        """Read pygame's polled input and every opened device's positions (both layers) now.

        Returns:
            The live snapshot.

        """
        polled = self._devices.poll()
        return capture_live_snapshot(
            device_axes=polled.axes,
            device_buttons=polled.buttons,
            device_hats=polled.hats,
            controller_axes=polled.controller_axes,
            controller_buttons=polled.controller_buttons,
        )

    def devices(self: Self) -> LiveDeviceRegistry:
        """Return the live device registry (real devices).

        Returns:
            The registry.

        """
        return self._devices

    def saves(self: Self, *, namespace: str) -> SaveManager:
        """Open (or return the already opened) real save store for ``namespace``.

        Args:
            namespace: The game's app name (the save directory's name).

        Returns:
            The DiskSaveManager for ``namespace``.

        """
        store = self._opened_save_namespaces.get(namespace)
        if store is None:
            store = DiskSaveManager(app_name=namespace)
            self._opened_save_namespaces[namespace] = store
            if self.captures_scene_starts:
                self._first_open_save_snapshots[namespace] = save_namespace_snapshot(saves=store)
        return store

    def wall_clock_time(self: Self) -> datetime:
        """Return now, in UTC (the live wall-clock provider).

        Returns:
            glitchygames/clock.py's ``raw_wall_clock_time()`` (``datetime.now(tz=UTC)``).

        """
        return clock.raw_wall_clock_time()

    def control_events_for_frame(self: Self, *, frame_number: int) -> list[ControlEvent]:
        """Return no control events: live play schedules none.

        Returns:
            An empty list.

        """
        # Live play has no recording to schedule from (EngineSources signature)
        del frame_number
        return []

    def end_frame(
        self: Self,
        *,
        frame_number: int,
        dt: float,
        scene: Scene | None,
        control_events: list[ControlEvent],
        processing_seconds: float | None = None,
    ) -> None:
        """Discard the frame's device answers and descriptors nobody took.

        A recorder (Task 11 of the gameplay replay plan) takes them before this runs.
        """
        # The frame itself needs nothing from live play (EngineSources signature)
        del frame_number, dt, scene, control_events, processing_seconds
        self._devices.discard_untaken()
