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
# Re-send when the rumble already sent has this many seconds (or less) left, so the motor is
# refreshed just before SDL expires it instead of stopping and restarting a frame later.
RESEND_TIME_MARGIN = 0.05
# A sustained level has no natural end, so it is sent in short slices and refreshed by the
# time-left margin above. If the game stops updating (crash, hang), the motor stops within
# this many seconds instead of buzzing forever.
SUSTAINED_SEND_DURATION = 0.25


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
    joysticks: list[RumbleDevice] = []
    for index in range(pygame.joystick.get_count()):
        try:
            joysticks.append(pygame.joystick.Joystick(index))
        except pygame.error:
            # Unplugged between get_count() and construction; skip it, keep the others
            log.debug('Joystick %d vanished before it could be opened', index, exc_info=True)
    return joysticks


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
        self._sustained_levels = (0.0, 0.0)

    @property
    def sustained_levels(self) -> tuple[float, float]:
        """The sustained (low frequency, high frequency) motor levels, (0.0, 0.0) if none."""
        return self._sustained_levels

    def set_sustained(self, *, low_frequency: float, high_frequency: float) -> None:
        """Hold a rumble level until changed or cleared (e.g. an elevator's hum).

        Args:
            low_frequency: Low-frequency (heavy) motor level, 0.0-1.0.
            high_frequency: High-frequency (light) motor level, 0.0-1.0.

        Raises:
            ValueError: If either level is outside 0.0-1.0.

        """
        for field_name, value in (
            ('low_frequency', low_frequency),
            ('high_frequency', high_frequency),
        ):
            if not 0.0 <= value <= 1.0:
                message = f'{field_name} must be between 0.0 and 1.0, got {value}'
                raise ValueError(message)
        self._sustained_levels = (low_frequency, high_frequency)

    def clear_sustained(self) -> None:
        """Stop holding a sustained level (shake rumble is unaffected)."""
        self._sustained_levels = (0.0, 0.0)

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
        sustained_low, sustained_high = self._sustained_levels
        low = max((shaker.rumble_levels[0] for shaker in shakers), default=0.0)
        low = max(low, sustained_low) * self._intensity
        high = max((shaker.rumble_levels[1] for shaker in shakers), default=0.0)
        high = max(high, sustained_high) * self._intensity
        remaining = max((shaker.rumble_remaining for shaker in shakers), default=0.0)
        # Only shakes have a real end; the sustained slice must not look like "shakes outlast
        # what was sent" every frame, or it would be re-sent every frame.
        send_remaining = remaining
        if max(sustained_low, sustained_high) > 0.0:
            send_remaining = max(remaining, SUSTAINED_SEND_DURATION)

        if max(low, high) <= 0.0:
            if self._sent_levels != (0.0, 0.0):
                self._stop_rumble(devices=devices)
                self._sent_levels = (0.0, 0.0)
            return

        level_change = max(abs(low - self._sent_levels[0]), abs(high - self._sent_levels[1]))
        sent_rumble_about_to_run_out = self._sent_time_left <= RESEND_TIME_MARGIN
        sent_rumble_ends_before_shakes = remaining > self._sent_time_left + RESEND_TIME_MARGIN
        if (
            level_change <= RESEND_LEVEL_THRESHOLD
            and not sent_rumble_about_to_run_out
            and not sent_rumble_ends_before_shakes
        ):
            return

        duration_milliseconds = max(1, math.ceil(send_remaining * MILLISECONDS_PER_SECOND))
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
