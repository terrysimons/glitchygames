"""Set the display mode and wait until the window has really taken its new size.

Resizing an existing window is asynchronous on SDL's x11 driver: ``SDL_SetWindowSize`` asks
the window manager, waits at most 100 ms for an answer (``X11_SetWindowSize`` in SDL 2.32's
``src/video/x11/SDL_x11window.c``), then gives up and keeps the old size. pygame-ce then warns
"Requested window was forcibly resized by the OS" and returns a display surface of the old
size, and the requested size arrives later, when a pump processes the X server's
ConfigureNotify (``pygame.display.get_surface()`` then follows it). On a loaded machine, or an X
server over the network (Docker forwarding to XQuartz), the window manager regularly takes
longer than 100 ms, so a game would be set up (scenes and sprites read the display size when
built) on a size the window is about to leave.

``set_display_mode`` keeps that wait going: when pygame warns and the display still has the size
it had before, it pumps SDL's queue until the size changes (to the requested size, or any other
the window manager chose, as SDL itself stops at any change) or the polls run out. Only a window
that still differs from the requested size at the end is reported, with pygame-ce's warning
naming the size it ended at. A first window (none before) is never waited for: there is no old
size to wait out. The pumped window events stay in SDL's queue for the game's first frame.
"""

from __future__ import annotations

import time
import warnings

import pygame

# The start of pygame-ce's warning when the window did not take the requested size, raised by
# pg_set_mode in its src_c/display.c
FORCIBLY_RESIZED_MESSAGE = 'Requested window was forcibly resized by the OS'

# How long one poll waits before pumping again, and how many polls at most (at least 10 s).
# Measured 2026-10-23 (SDL 2.32.10, XQuartz 2.8, 8 Linux containers' processes resizing at once
# over TCP): every resize came late, settling after 0.8-3.4 s (up to 219 polls); an idle
# machine's resizes all landed within SDL's own 100 ms. A window manager that refuses a size
# outright changes the window to another (XQuartz: at least 72 wide), which ends the wait at once
SETTLE_POLL_SECONDS = 0.01
DEFAULT_SETTLE_POLLS = 1000


def _is_forcibly_resized(caught: warnings.WarningMessage) -> bool:
    return issubclass(caught.category, RuntimeWarning) and str(caught.message).startswith(
        FORCIBLY_RESIZED_MESSAGE
    )


def set_display_mode(
    *, size: tuple[int, int], flags: int = 0, settle_polls: int = DEFAULT_SETTLE_POLLS
) -> pygame.Surface:
    """Set the display mode, waiting for a resize the window manager answers late.

    Args:
        size: The requested window size.
        flags: pygame's display flags.
        settle_polls: How many times at most to pump and look again (each after
            ``SETTLE_POLL_SECONDS``).

    Returns:
        pygame.Surface: The display surface, at the size the window has when this returns.

    """
    previous_surface = pygame.display.get_surface()
    previous_size = None if previous_surface is None else previous_surface.get_size()
    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter('always')
        surface = pygame.display.set_mode(size, flags)
    resize_refused = False
    for caught in caught_warnings:
        if _is_forcibly_resized(caught):
            resize_refused = True
        else:
            warnings.warn_explicit(
                message=caught.message,
                category=caught.category,
                filename=caught.filename,
                lineno=caught.lineno,
            )
    if not resize_refused:
        return surface

    requested_size = (int(size[0]), int(size[1]))
    if previous_size is not None:
        for _poll in range(settle_polls):
            if surface.get_size() != previous_size:
                break
            time.sleep(SETTLE_POLL_SECONDS)
            pygame.event.pump()
            # Reading the display surface refreshes it to the window's current size
            current_surface = pygame.display.get_surface()
            if current_surface is None:  # pragma: no cover - the display closed while waiting
                break
            surface = current_surface
    if surface.get_size() != requested_size:
        warnings.warn(
            f'{FORCIBLY_RESIZED_MESSAGE}.\n\tRequested window size: {requested_size}\n'
            f'\tNew window size: {surface.get_size()}',
            RuntimeWarning,
            stacklevel=2,
        )
    return surface
