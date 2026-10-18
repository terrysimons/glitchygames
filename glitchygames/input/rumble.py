"""Controller rumble driven by active shakes.

SDL replaces a running rumble whenever a new one starts and treats a duration of 0 as
"forever", so this controller sends one combined level (per-motor maximum over all shakers)
and only re-sends when that level changes noticeably or the sent rumble is about to expire.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Protocol

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.effects.shake import ScreenShake

log: logging.Logger = logging.getLogger('game.input.rumble')

RESEND_LEVEL_THRESHOLD = 0.05
MILLISECONDS_PER_SECOND = 1000


class RumbleDevice(Protocol):
    """Anything with SDL-style rumble: controller proxies and pygame joysticks."""

    def rumble(self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        """Start rumble; duration in milliseconds (0 = forever)."""
        ...

    def stop_rumble(self) -> None:
        """Stop rumble."""
        ...


def connected_rumble_devices(controller_manager: object | None) -> list[RumbleDevice]:
    """Return every device that can rumble in the current input mode.

    Args:
        controller_manager: GameEngine.controller_manager; None in joystick mode (the
            pygame-ce default), where joysticks are opened directly.

    Returns:
        The devices.

    """
    if controller_manager is not None:
        controllers: dict[int, RumbleDevice] = getattr(controller_manager, 'controllers', {})
        return list(controllers.values())
    return [pygame.joystick.Joystick(index) for index in range(pygame.joystick.get_count())]


class RumbleController:
    """Sends the combined rumble of all shakers to every connected device."""

    def __init__(self, *, intensity: float = 1.0) -> None:
        """Initialize with nothing sent.

        Args:
            intensity: Player setting 0.0-1.0 multiplying both motors (0 disables).

        """
        self._intensity = 1.0
        self.intensity = intensity
        self._sent_levels = (0.0, 0.0)
        self._sent_time_left = 0.0

    @property
    def intensity(self) -> float:
        """Player setting 0.0-1.0 multiplying both motors."""
        return self._intensity

    @intensity.setter
    def intensity(self, value: float) -> None:
        if not 0.0 <= value <= 1.0:
            message = f'intensity must be between 0.0 and 1.0, got {value}'
            raise ValueError(message)
        self._intensity = value

    def update(
        self,
        *,
        shakers: Sequence[ScreenShake],
        dt: float,
        devices: Callable[[], list[RumbleDevice]],
    ) -> None:
        """Send, re-send or stop rumble to match the shakers.

        Args:
            shakers: Every active ScreenShake (screen and the active scene's camera).
            dt: Seconds since the last update.
            devices: Called only when something must be sent.

        """
        self._sent_time_left -= dt
        low = max((shaker.rumble_levels[0] for shaker in shakers), default=0.0) * self._intensity
        high = max((shaker.rumble_levels[1] for shaker in shakers), default=0.0) * self._intensity
        remaining = max((shaker.rumble_remaining for shaker in shakers), default=0.0)

        if max(low, high) <= 0.0:
            if self._sent_levels != (0.0, 0.0):
                self._stop_rumble(devices=devices)
                self._sent_levels = (0.0, 0.0)
            return

        level_change = max(abs(low - self._sent_levels[0]), abs(high - self._sent_levels[1]))
        if level_change <= RESEND_LEVEL_THRESHOLD and self._sent_time_left > 0.0:
            return

        duration_milliseconds = max(1, math.ceil(remaining * MILLISECONDS_PER_SECOND))
        self._send_rumble(
            devices=devices,
            levels=(low, high),
            duration_milliseconds=duration_milliseconds,
        )
        self._sent_levels = (low, high)
        self._sent_time_left = duration_milliseconds / MILLISECONDS_PER_SECOND

    @staticmethod
    def _send_rumble(
        *,
        devices: Callable[[], list[RumbleDevice]],
        levels: tuple[float, float],
        duration_milliseconds: int,
    ) -> None:
        for device in devices():
            try:
                # Positional: pygame's C Joystick.rumble does not take keywords
                device.rumble(levels[0], levels[1], duration_milliseconds)
            except pygame.error, AttributeError, OSError:
                # A device unplugged mid-rumble must not stop the others
                log.debug('Rumble failed on %r', device, exc_info=True)

    @staticmethod
    def _stop_rumble(*, devices: Callable[[], list[RumbleDevice]]) -> None:
        for device in devices():
            try:
                device.stop_rumble()
            except pygame.error, AttributeError, OSError:
                # A device unplugged mid-rumble must not stop the others
                log.debug('Stop rumble failed on %r', device, exc_info=True)
