"""Test windows on a real video driver are hidden, so the machine's input never reaches a test.

A test's window on a real driver (the native run of a local ``uv run pytest``, tests/
driver_comparison.py; ``nox -s compare-drivers``' native runs) is a real window: when it opens
under the pointer, or takes the keyboard, the machine's mouse motion and keys reach the test as
events. The golden harness's discard (``discard_environment_events``) drops window and device
events but keeps input, which tests post themselves, so the host's input reached the scene: a
mouse motion over a test's plain sprite called ``on_mouse_focus_event`` on it and failed the
native run (BUGS.md #225; a native-only frame difference, #227, is likely the same channel).
Pads were kept out the same way (tests/sdl_defaults.py, its joystick drivers).

A hidden window receives no pointer or keyboard input, and draws and presents the same pixels
(checked on cocoa: the same pixel format and the same frame, shown or hidden). The dummy driver
has no host input and is left alone. ``GLITCHYGAMES_SHOW_TEST_WINDOWS=1`` shows the windows
again, to watch a run.
"""

from __future__ import annotations

import functools
import os
from typing import TYPE_CHECKING, Any

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

SHOW_TEST_WINDOWS_VARIABLE = 'GLITCHYGAMES_SHOW_TEST_WINDOWS'
# The driver with no host input: its windows are left as asked
DUMMY_VIDEO_DRIVER = 'dummy'


def hides_test_windows(*, environment: Mapping[str, str]) -> bool:
    """Return whether a run in this environment hides its test windows.

    Args:
        environment: The run's environment (its SDL driver variables are already defaulted,
            tests/sdl_defaults.py).

    Returns:
        True on a real video driver, unless ``GLITCHYGAMES_SHOW_TEST_WINDOWS=1``.

    """
    return (
        environment.get('SDL_VIDEODRIVER') != DUMMY_VIDEO_DRIVER
        and environment.get(SHOW_TEST_WINDOWS_VARIABLE) != '1'
    )


def hidden_set_mode(real_set_mode: Callable[..., pygame.Surface]) -> Callable[..., pygame.Surface]:
    """Return ``set_mode`` that opens every window hidden (``pygame.HIDDEN`` added to its flags).

    Args:
        real_set_mode: pygame's ``pygame.display.set_mode``.

    Returns:
        The wrapper, with the same arguments.

    """

    @functools.wraps(real_set_mode)
    def set_mode(size: Any = (0, 0), flags: int = 0, *args: Any, **kwargs: Any) -> pygame.Surface:
        return real_set_mode(size, flags | pygame.HIDDEN, *args, **kwargs)

    return set_mode


def hide_test_windows() -> bool:
    """Make pygame open hidden windows for the rest of the process, if this run hides them.

    Returns:
        True if windows are now hidden.

    """
    if not hides_test_windows(environment=os.environ):
        return False
    pygame.display.set_mode = hidden_set_mode(pygame.display.set_mode)
    return True
