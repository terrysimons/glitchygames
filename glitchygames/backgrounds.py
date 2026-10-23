"""The built-in scene backgrounds: a TV test pattern (the default) and a channel 3 blue screen.

A scene that sets no background (no ``background_color``, no ``background_pattern``) gets the
active default pattern, so a scene that draws nothing is visibly "on the air" instead of black:
black cannot be told from "nothing rendered", and an entirely black frame is treated as a
rendering bug (the test suite fails a test that ends on one, tests/conftest.py).

- ``BackgroundPattern.TEST_PATTERN``: SMPTE-style colour bars (the engine default). The top
  two thirds hold the seven 75% bars (grey, yellow, cyan, green, magenta, red, blue), then a
  thin strip of the reversed bars (blue, black, magenta, black, cyan, black, grey), then the
  bottom row: -I, 100% white and +Q blocks, black, and the PLUGE steps (below black, black,
  above black) before the last black block. Layout after SMPTE ECR 1-1978 / EG 1-1990
  (https://en.wikipedia.org/wiki/SMPTE_color_bars), in 8-bit RGB.
- ``BackgroundPattern.CHANNEL_THREE``: the classic VCR "no signal" blue screen with a chunky,
  bright green "3" in the upper-right corner, like a VCR's or TV's on-screen channel display
  (the bundled Bitstream Vera Sans Bold, hard-edged and thickened).

Both are drawn procedurally at any size, opaque, and cached per size
(``background_pattern_surface``): a scene copies the cached surface into its own background,
which costs about what a fill does. The default is process-wide
(``set_active_default_background_pattern``); ``--default-background`` sets it for a run.
"""

from __future__ import annotations

import functools
from enum import StrEnum
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable

# The bundled bold font (the debug overlay finds Vera.ttf the same way): this module is a leaf,
# so it does not import the font manager
CHANNEL_THREE_FONT_PATH = Path(__file__).parent / 'fonts' / 'bitstream_vera' / 'VeraBd.ttf'

# 75% colour bars, 8-bit RGB (191 = 75% of 255)
BAR_GREY = (191, 191, 191)
BAR_YELLOW = (191, 191, 0)
BAR_CYAN = (0, 191, 191)
BAR_GREEN = (0, 191, 0)
BAR_MAGENTA = (191, 0, 191)
BAR_RED = (191, 0, 0)
BAR_BLUE = (0, 0, 191)
# Black at 7.5% setup, and the PLUGE steps 4% below and above it
SETUP_BLACK = (19, 19, 19)
PLUGE_BELOW_BLACK = (9, 9, 9)
PLUGE_ABOVE_BLACK = (29, 29, 29)
MINUS_I = (0, 33, 76)
FULL_WHITE = (255, 255, 255)
PLUS_Q = (50, 0, 106)

TOP_BARS = (BAR_GREY, BAR_YELLOW, BAR_CYAN, BAR_GREEN, BAR_MAGENTA, BAR_RED, BAR_BLUE)
REVERSED_BARS = (
    BAR_BLUE,
    SETUP_BLACK,
    BAR_MAGENTA,
    SETUP_BLACK,
    BAR_CYAN,
    SETUP_BLACK,
    BAR_GREY,
)
# The bottom row's blocks as (right edge as a fraction of the width, colour), left to right:
# -I, white and +Q are each 5/4 of a bar wide (a bar is 1/7), black fills to the fifth bar's
# edge, the three PLUGE steps share the sixth bar, and black fills the seventh
BOTTOM_BLOCKS = (
    (Fraction(5, 28), MINUS_I),
    (Fraction(10, 28), FULL_WHITE),
    (Fraction(15, 28), PLUS_Q),
    (Fraction(5, 7), SETUP_BLACK),
    (Fraction(16, 21), PLUGE_BELOW_BLACK),
    (Fraction(17, 21), SETUP_BLACK),
    (Fraction(6, 7), PLUGE_ABOVE_BLACK),
    (Fraction(1), SETUP_BLACK),
)
# Where the strips end, as fractions of the height
TOP_BARS_BOTTOM = Fraction(2, 3)
REVERSED_BARS_BOTTOM = Fraction(3, 4)

# The classic VCR / TV "no signal" blue: solid, fully saturated
VCR_BLUE = (0, 0, 255)
# The on-screen display's bright green digit, and the black edge OSD characters were drawn with
OSD_GREEN = (0, 255, 0)
OSD_SHADOW = (0, 0, 0)
CHANNEL_THREE_TEXT = '3'
# The digit's font size and its margin from the top-right corner, as fractions of the height
CHANNEL_THREE_FONT_FRACTION = Fraction(1, 4)
CHANNEL_THREE_MARGIN_FRACTION = Fraction(1, 20)
CHANNEL_THREE_SHADOW_FRACTION = Fraction(1, 100)
# How far the digit is stamped right and down to thicken it (chunky, like an OSD character
# generator), as a fraction of the font size
CHANNEL_THREE_STROKE_FRACTION = Fraction(1, 14)
# Patterns kept per (pattern, size): a game normally uses one screen size
PATTERN_CACHE_SIZE = 8


class BackgroundPattern(StrEnum):
    """A built-in scene background (the values are the ``--default-background`` choices)."""

    TEST_PATTERN = 'test-pattern'
    CHANNEL_THREE = 'channel-3'


DEFAULT_BACKGROUND_PATTERN = BackgroundPattern.TEST_PATTERN


class _ActiveBackgroundSettings:
    """Holds the process-wide default background (what a scene that sets none gets)."""

    default_pattern: BackgroundPattern = DEFAULT_BACKGROUND_PATTERN


def set_active_default_background_pattern(*, pattern: BackgroundPattern) -> None:
    """Set the background a scene gets when it sets none.

    Args:
        pattern: The new default (the engine sets it from ``--default-background``).

    """
    _ActiveBackgroundSettings.default_pattern = pattern


def active_default_background_pattern() -> BackgroundPattern:
    """Return the background a scene gets when it sets none.

    Returns:
        BackgroundPattern: The active default (initially the test pattern).

    """
    return _ActiveBackgroundSettings.default_pattern


def _scaled_edge(*, length: int, fraction: Fraction) -> int:
    """Return the pixel edge at a fraction of a length (rounded half up, exactly).

    Args:
        length: The width or height in pixels.
        fraction: Where the edge falls, from 0 to 1.

    Returns:
        int: The edge's pixel coordinate.

    """
    return int(length * fraction + Fraction(1, 2))


def _fill_strip(
    *,
    surface: pygame.Surface,
    blocks: tuple[tuple[Fraction, tuple[int, int, int]], ...],
    top: int,
    bottom: int,
) -> None:
    """Fill a horizontal strip with blocks given by their right edges.

    Args:
        surface: The surface drawn on.
        blocks: Each block's right edge (a fraction of the width) and colour, left to right.
        top: The strip's top row.
        bottom: The row below the strip.

    """
    width = surface.get_width()
    left = 0
    for right_fraction, color in blocks:
        right = _scaled_edge(length=width, fraction=right_fraction)
        surface.fill(color, pygame.Rect(left, top, right - left, bottom - top))
        left = right


def _equal_blocks(
    colors: tuple[tuple[int, int, int], ...],
) -> tuple[tuple[Fraction, tuple[int, int, int]], ...]:
    """Return blocks of equal width, one per colour.

    Args:
        colors: The colours, left to right.

    Returns:
        The blocks as (right edge fraction, colour).

    """
    return tuple((Fraction(index + 1, len(colors)), color) for index, color in enumerate(colors))


def draw_test_pattern(*, surface: pygame.Surface) -> None:
    """Draw the SMPTE-style colour bars over the whole surface.

    Args:
        surface: The surface drawn on.

    """
    height = surface.get_height()
    top_bars_bottom = _scaled_edge(length=height, fraction=TOP_BARS_BOTTOM)
    reversed_bars_bottom = _scaled_edge(length=height, fraction=REVERSED_BARS_BOTTOM)
    _fill_strip(surface=surface, blocks=_equal_blocks(TOP_BARS), top=0, bottom=top_bars_bottom)
    _fill_strip(
        surface=surface,
        blocks=_equal_blocks(REVERSED_BARS),
        top=top_bars_bottom,
        bottom=reversed_bars_bottom,
    )
    _fill_strip(surface=surface, blocks=BOTTOM_BLOCKS, top=reversed_bars_bottom, bottom=height)


def draw_channel_three(*, surface: pygame.Surface) -> None:
    """Draw the channel 3 blue screen: blue, with a big green "3" in the upper-right corner.

    pygame.font must be started (pygame.init() starts it).

    Args:
        surface: The surface drawn on.

    """
    surface.fill(VCR_BLUE)
    width, height = surface.get_size()
    font_size = max(1, _scaled_edge(length=height, fraction=CHANNEL_THREE_FONT_FRACTION))
    font = pygame.font.Font(CHANNEL_THREE_FONT_PATH, font_size)
    # Not antialiased: an OSD's character generator drew hard-edged pixels
    digit = font.render(CHANNEL_THREE_TEXT, antialias=False, color=OSD_GREEN)
    shadow = font.render(CHANNEL_THREE_TEXT, antialias=False, color=OSD_SHADOW)
    margin = _scaled_edge(length=height, fraction=CHANNEL_THREE_MARGIN_FRACTION)
    shadow_offset = max(1, _scaled_edge(length=height, fraction=CHANNEL_THREE_SHADOW_FRACTION))
    stroke = _scaled_edge(length=font_size, fraction=CHANNEL_THREE_STROKE_FRACTION)
    digit_rect = digit.get_rect(topright=(width - margin - shadow_offset - stroke, margin))
    for stamped, offset in ((shadow, shadow_offset), (digit, 0)):
        for stroke_x in range(stroke + 1):
            for stroke_y in range(stroke + 1):
                surface.blit(stamped, digit_rect.move(offset + stroke_x, offset + stroke_y))


# How each pattern is drawn
PATTERN_DRAWERS: dict[BackgroundPattern, Callable[..., None]] = {
    BackgroundPattern.TEST_PATTERN: draw_test_pattern,
    BackgroundPattern.CHANNEL_THREE: draw_channel_three,
}


@functools.lru_cache(maxsize=PATTERN_CACHE_SIZE)
def background_pattern_surface(
    *, pattern: BackgroundPattern, size: tuple[int, int]
) -> pygame.Surface:
    """Return the pattern drawn at a size, from a per-size cache.

    The surface is shared: copy it (blit it) and never draw on it.

    Args:
        pattern: The pattern.
        size: The width and height in pixels.

    Returns:
        pygame.Surface: The opaque pattern.

    """
    surface = pygame.Surface(size)
    PATTERN_DRAWERS[pattern](surface=surface)
    return surface


def paint_default_background(*, surface: pygame.Surface) -> None:
    """Cover a surface with the active default pattern (a new display, before any scene draws).

    Args:
        surface: The surface painted, at its own size.

    """
    surface.blit(
        background_pattern_surface(
            pattern=active_default_background_pattern(), size=surface.get_size()
        ),
        (0, 0),
    )
