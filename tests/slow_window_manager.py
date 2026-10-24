"""A stand-in for an X window manager that answers a resize late (a helper for tests).

On SDL's x11 driver a resize of an existing window is asynchronous: SDL waits 100 ms for the
window manager, then gives up and reports the old size (pygame-ce warns "Requested window was
forcibly resized by the OS"); the real size arrives on a later pump. The dummy driver resizes
at once, so tests stand the slow window manager in: pygame's set_mode answers with the old size
and the warning, and the resize lands on a chosen pump (glitchygames/display_mode.py).
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pygame

from glitchygames.display_mode import FORCIBLY_RESIZED_MESSAGE

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

REAL_SET_MODE = pygame.display.set_mode
REAL_PUMP = pygame.event.pump


def forcibly_resized_warning(*, requested: tuple[int, int], got: tuple[int, int]) -> None:
    """Warn as pygame-ce's set_mode does when the window did not take the requested size."""
    warnings.warn(
        f'{FORCIBLY_RESIZED_MESSAGE}.\n\tRequested window size: {requested}\n'
        f'\tNew window size: {got}',
        RuntimeWarning,
        stacklevel=2,
    )


class SlowWindowManager:
    """Stands in for an X window manager that applies a resize some pumps after set_mode."""

    def __init__(self, *, pumps_until_resized: int | None, final_size: tuple[int, int]) -> None:
        """Resize to final_size on that pump (None: never)."""
        self.pumps_until_resized = pumps_until_resized
        self.final_size = final_size
        self.pumps = 0

    def set_mode(self, size, flags=0):
        """Keep the old size, as SDL does when the window manager did not answer in time.

        Returns:
            pygame.Surface: The display surface, still at its old size.

        """
        old_size = pygame.display.get_surface().get_size()
        surface = REAL_SET_MODE(old_size, flags)
        forcibly_resized_warning(requested=tuple(size), got=old_size)
        return surface

    def pump(self) -> None:
        """Pump SDL's queue; the window manager's answer arrives on the chosen pump."""
        REAL_PUMP()
        self.pumps += 1
        if self.pumps == self.pumps_until_resized:
            REAL_SET_MODE(self.final_size)


def install_window_manager(mocker: MockerFixture, *, window_manager: SlowWindowManager) -> None:
    """Route pygame's set_mode and pump through the stand-in window manager.

    Args:
        mocker: pytest-mock's fixture.
        window_manager: The stand-in.

    """
    mocker.patch.object(pygame.display, 'set_mode', side_effect=window_manager.set_mode)
    mocker.patch.object(pygame.event, 'pump', side_effect=window_manager.pump)
