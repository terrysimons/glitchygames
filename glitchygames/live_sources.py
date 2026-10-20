"""The live doors (glitchygames/sources.py).

Pygame's queue, the measured frame time, and (from later tasks) pygame's polled input, real
devices, files on disk and the real clocks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.input.devices import LiveDeviceRegistry
from glitchygames.input.state import capture_live_snapshot

if TYPE_CHECKING:
    from glitchygames.input.state import InputSnapshot
    from glitchygames.scenes import Scene


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

    def input_snapshot(self: Self) -> InputSnapshot:
        """Read pygame's polled input and every opened device's positions now.

        Returns:
            The live snapshot.

        """
        axes, buttons, hats = self._devices.poll()
        return capture_live_snapshot(device_axes=axes, device_buttons=buttons, device_hats=hats)

    def devices(self: Self) -> LiveDeviceRegistry:
        """Return the live device registry (real devices).

        Returns:
            The registry.

        """
        return self._devices

    def end_frame(self: Self, *, frame_number: int, dt: float, scene: Scene | None) -> None:
        """Nothing to do after a live frame."""
