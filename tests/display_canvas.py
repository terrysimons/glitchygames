"""The test display rule's canvas and black-frame check (a helper for conftest and tests).

Every test starts on a display showing the canvas: the engine's default background pattern
(glitchygames/backgrounds.py), the TV test pattern, or the channel 3 blue screen when
GLITCHYGAMES_TEST_CANVAS=channel-3. A test that draws nothing therefore shows the pattern
(intentional), and a test whose last frame is entirely black fails: black cannot be told from
"nothing rendered", so it is a rendering bug (tests/conftest.py runs the check).

Tests that assert pixels they never drew name the canvas with ``canvas_color_at``. (Helpers
here are not named ``test_*``: pytest would collect them as tests where they are imported.)
"""

from __future__ import annotations

import contextlib
import os

import pygame

from glitchygames.backgrounds import (
    DEFAULT_BACKGROUND_PATTERN,
    BackgroundPattern,
    background_pattern_surface,
)

TEST_CANVAS_VARIABLE = 'GLITCHYGAMES_TEST_CANVAS'
TEST_DISPLAY_SIZE = (800, 600)

# The real display functions, captured before any test can patch them
_REAL_DISPLAY_GET_SURFACE = pygame.display.get_surface
_REAL_DISPLAY_FLIP = pygame.display.flip


def _canvas_pattern_from_environment() -> BackgroundPattern:
    """Read the canvas pattern from GLITCHYGAMES_TEST_CANVAS (default: the engine default).

    Returns:
        BackgroundPattern: The pattern the run's canvas and default scene backgrounds show.

    Raises:
        ValueError: The variable names no pattern.

    """
    requested = os.environ.get(TEST_CANVAS_VARIABLE, DEFAULT_BACKGROUND_PATTERN.value)
    try:
        return BackgroundPattern(requested)
    except ValueError:
        choices = ', '.join(pattern.value for pattern in BackgroundPattern)
        message = f'{TEST_CANVAS_VARIABLE}={requested!r} names no background pattern ({choices})'
        raise ValueError(message) from None


CANVAS_PATTERN = _canvas_pattern_from_environment()


def canvas_color_at(*, x: int, y: int, size: tuple[int, int] = TEST_DISPLAY_SIZE) -> pygame.Color:
    """Return the canvas colour at a pixel: what an untouched display (or scene) shows there.

    Args:
        x: The pixel's column.
        y: The pixel's row.
        size: The display (or scene background) size the pattern is drawn at.

    Returns:
        pygame.Color: The canvas pattern's opaque colour at (x, y).

    """
    return background_pattern_surface(pattern=CANVAS_PATTERN, size=size).get_at((x, y))


def real_display_surface() -> pygame.Surface | None:
    """Return the real display surface, or None when pygame or its display is not running.

    Returns:
        pygame.Surface | None: The display surface, through the real (unpatched) function.

    """
    if not pygame.get_init():
        return None
    try:
        display_surface = _REAL_DISPLAY_GET_SURFACE()
    except pygame.error:
        return None
    return display_surface if isinstance(display_surface, pygame.Surface) else None


def present_display() -> None:
    """Present the display through the real (unpatched) flip, if it can be presented.

    A test may leave a display mode that cannot flip (an OpenGL mode without a context).
    """
    with contextlib.suppress(pygame.error):
        _REAL_DISPLAY_FLIP()


def show_canvas() -> None:
    """Draw the canvas over the whole display and present it: what every test starts on.

    The pattern surface is opaque, so the copy is opaque on a display with per-pixel alpha
    (cocoa's) too.
    """
    display_surface = real_display_surface()
    if display_surface is None:
        return
    display_surface.blit(
        background_pattern_surface(pattern=CANVAS_PATTERN, size=display_surface.get_size()),
        (0, 0),
    )
    present_display()


def display_is_entirely_black(display_surface: pygame.Surface) -> bool:
    """Tell whether every pixel of the display has red, green and blue all zero.

    The average colour (about 0.1 ms for 800x600) settles almost every frame: any non-zero
    average means some pixel is not black. Only a zero average, which a few dim pixels can
    round down to, is checked pixel by pixel (about 0.8 ms).

    Args:
        display_surface: The display surface.

    Returns:
        bool: True when no pixel has any red, green or blue.

    """
    red, green, blue, _alpha = pygame.transform.average_color(display_surface)
    if red or green or blue:
        return False
    color_planes = pygame.surfarray.pixels3d(display_surface)
    try:
        return not color_planes.any()
    finally:
        # The view locks the display surface until it is released
        del color_planes


def show_canvas_on_new_display(*, size: tuple[int, int] = TEST_DISPLAY_SIZE) -> pygame.Surface:
    """Set a new display mode and show the canvas on it (a new display is black).

    For a test that sets the display mode itself (or restores the default one after quitting
    pygame) and draws nothing on it.

    Args:
        size: The display size.

    Returns:
        pygame.Surface: The new display surface.

    """
    display_surface = pygame.display.set_mode(size)
    show_canvas()
    return display_surface
