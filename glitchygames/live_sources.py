"""The live doors (glitchygames/sources.py).

Pygame's queue, the measured frame time, pygame's polled input, real devices, real save files
on disk and the real wall clock.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.input.devices import LiveDeviceRegistry
from glitchygames.input.state import capture_live_snapshot
from glitchygames.state.manager import DiskSaveManager

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene
    from glitchygames.state.manager import SaveManager
    from glitchygames.supervision import ControlEvent


class LiveSources:
    """The live doors (implements glitchygames.sources.EngineSources)."""

    def __init__(self: Self, *, random_seed: int, use_fastevents: bool = False) -> None:
        """Create the live doors.

        Args:
            random_seed: The run's master seed (glitchygames/randomness.py).
            use_fastevents: Read events with pygame.fastevent when pygame has it
                (``GameEngine.USE_FASTEVENTS``; pygame < 2.2 only).

        """
        self.random_seed = random_seed
        self._use_fastevents = use_fastevents
        self._devices = LiveDeviceRegistry()
        # Stores games opened, by namespace (opened_save_namespaces)
        self._opened_save_namespaces: dict[str, DiskSaveManager] = {}

    @property
    def opened_save_namespaces(self: Self) -> Mapping[str, SaveManager]:
        """Every store opened so far, by namespace (read-only; a recording's header)."""
        return MappingProxyType(self._opened_save_namespaces)

    @property
    def stop_requested(self: Self) -> bool:
        """Live play never asks to stop."""
        return False

    def on_installed(self: Self) -> None:
        """Nothing to start for live play."""

    def on_uninstalled(self: Self) -> None:
        """Nothing to stop for live play."""

    def pump_events(self: Self) -> list[pygame.event.Event]:
        """Take every event from SDL's queue.

        Returns:
            The batch, in queue order.

        """
        # To use events in a different thread, use the fastevent package from pygame.
        # if you're using pygame < 2.2, you'll need to use pygame.fastevent.
        fastevent = getattr(pygame, 'fastevent', None)
        if self._use_fastevents and fastevent is not None:
            return list(fastevent.get())
        return list(pygame.event.get())

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
        return store

    def wall_clock_time(self: Self) -> datetime:
        """Return now, in UTC (the live wall-clock provider).

        Returns:
            ``datetime.now(tz=UTC)``.

        """
        return datetime.now(tz=UTC)

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
    ) -> None:
        """Discard the frame's device answers and descriptors nobody took.

        A recorder (Task 11 of the gameplay replay plan) takes them before this runs.
        """
        # The frame itself needs nothing from live play (EngineSources signature)
        del frame_number, dt, scene, control_events
        self._devices.discard_untaken()
