"""The built-in scene backgrounds (glitchygames/backgrounds.py), drawn on real surfaces."""

from __future__ import annotations

from fractions import Fraction

import pygame
import pytest

from glitchygames.backgrounds import (
    BAR_BLUE,
    BAR_GREY,
    BAR_MAGENTA,
    BOTTOM_BLOCKS,
    DEFAULT_BACKGROUND_PATTERN,
    OSD_GREEN,
    REVERSED_BARS,
    SETUP_BLACK,
    TOP_BARS,
    VCR_BLUE,
    BackgroundPattern,
    active_default_background_pattern,
    background_pattern_surface,
    paint_default_background,
    set_active_default_background_pattern,
)

PATTERN_SIZE = (800, 600)
ODD_SIZES = [(1, 1), (7, 3), (13, 29), (641, 479)]


def rgb_at(surface: pygame.Surface, *, x: int, y: int) -> tuple[int, int, int]:
    """Return a pixel's red, green and blue.

    Args:
        surface: The surface read.
        x: The column.
        y: The row.

    Returns:
        The pixel's RGB.

    """
    color = surface.get_at((x, y))
    return (color.r, color.g, color.b)


def column_in_the_middle_of(*, left: Fraction, right: Fraction, width: int) -> int:
    """Return the pixel column halfway between two fractions of a width.

    Returns:
        The column.

    """
    return int(width * (left + right) / 2)


class TestTestPattern:
    """The SMPTE-style colour bars, strip by strip."""

    def test_the_top_two_thirds_hold_the_seven_bars(self):
        """Each of the seven 75% bars, grey to blue, fills its seventh of the width."""
        surface = background_pattern_surface(
            pattern=BackgroundPattern.TEST_PATTERN, size=PATTERN_SIZE
        )
        width, height = PATTERN_SIZE
        row = height // 3
        for index, color in enumerate(TOP_BARS):
            column = column_in_the_middle_of(
                left=Fraction(index, 7), right=Fraction(index + 1, 7), width=width
            )
            assert rgb_at(surface, x=column, y=row) == color

    def test_the_thin_strip_holds_the_reversed_bars(self):
        """Below the bars: blue, black, magenta, black, cyan, black, grey."""
        surface = background_pattern_surface(
            pattern=BackgroundPattern.TEST_PATTERN, size=PATTERN_SIZE
        )
        width, height = PATTERN_SIZE
        row = int(height * Fraction(17, 24))  # halfway between 2/3 and 3/4
        for index, color in enumerate(REVERSED_BARS):
            column = column_in_the_middle_of(
                left=Fraction(index, 7), right=Fraction(index + 1, 7), width=width
            )
            assert rgb_at(surface, x=column, y=row) == color
        assert REVERSED_BARS[0] == BAR_BLUE
        assert REVERSED_BARS[2] == BAR_MAGENTA
        assert REVERSED_BARS[-1] == BAR_GREY

    def test_the_bottom_row_holds_i_white_q_black_and_the_pluge(self):
        """-I, white, +Q, black, the three PLUGE steps and black, left to right."""
        surface = background_pattern_surface(
            pattern=BackgroundPattern.TEST_PATTERN, size=PATTERN_SIZE
        )
        width, height = PATTERN_SIZE
        row = height - 1
        left = Fraction(0)
        for right, color in BOTTOM_BLOCKS:
            column = column_in_the_middle_of(left=left, right=right, width=width)
            assert rgb_at(surface, x=column, y=row) == color
            left = right
        assert BOTTOM_BLOCKS[-1] == (Fraction(1), SETUP_BLACK)

    @pytest.mark.parametrize('size', [size for size in ODD_SIZES if size[0] >= len(TOP_BARS)])
    def test_any_size_is_covered_edge_to_edge(self, size):
        """At any size the bars meet the edges: the corners are the first and last blocks."""
        surface = background_pattern_surface(pattern=BackgroundPattern.TEST_PATTERN, size=size)
        width, height = size

        assert surface.get_size() == size
        assert rgb_at(surface, x=0, y=0) == TOP_BARS[0]
        assert rgb_at(surface, x=width - 1, y=height - 1) == SETUP_BLACK

    def test_a_single_pixel_shows_the_bar_at_its_centre(self):
        """Narrower than seven bars, a pixel shows the bar its centre falls in (green, at 1x1)."""
        surface = background_pattern_surface(pattern=BackgroundPattern.TEST_PATTERN, size=(1, 1))

        assert rgb_at(surface, x=0, y=0) == TOP_BARS[3]


class TestChannelThree:
    """The channel 3 blue screen with its green digit."""

    def test_blue_with_a_green_digit_in_the_upper_right(self):
        """The corners are blue; green pixels are only in the upper-right quarter."""
        surface = background_pattern_surface(
            pattern=BackgroundPattern.CHANNEL_THREE, size=PATTERN_SIZE
        )
        width, height = PATTERN_SIZE
        green_mask = pygame.mask.from_threshold(surface, (*OSD_GREEN, 255), (1, 1, 1, 255))
        upper_right = pygame.mask.Mask((width, height))
        upper_right.draw(pygame.mask.Mask((width // 2, height // 2), fill=True), (width // 2, 0))

        assert rgb_at(surface, x=0, y=0) == VCR_BLUE
        assert rgb_at(surface, x=0, y=height - 1) == VCR_BLUE
        assert green_mask.count() > 0
        assert green_mask.overlap_area(upper_right, (0, 0)) == green_mask.count()

    @pytest.mark.parametrize('size', ODD_SIZES)
    def test_any_size_draws(self, size):
        """Tiny and odd sizes draw without error, blue in the bottom-left corner."""
        surface = background_pattern_surface(pattern=BackgroundPattern.CHANNEL_THREE, size=size)

        assert surface.get_size() == size
        assert rgb_at(surface, x=0, y=size[1] - 1) == VCR_BLUE


class TestCacheAndDefault:
    """The per-size cache, the process-wide default, and painting a new display."""

    def test_a_pattern_is_drawn_once_per_size(self):
        """The same pattern at the same size is the same cached surface."""
        first = background_pattern_surface(pattern=BackgroundPattern.TEST_PATTERN, size=(32, 24))
        again = background_pattern_surface(pattern=BackgroundPattern.TEST_PATTERN, size=(32, 24))
        other = background_pattern_surface(pattern=BackgroundPattern.TEST_PATTERN, size=(33, 24))

        assert first is again
        assert other is not first

    def test_the_default_is_the_test_pattern_and_can_be_changed(self):
        """The engine default is the test pattern; set_active_default... changes it."""
        assert DEFAULT_BACKGROUND_PATTERN is BackgroundPattern.TEST_PATTERN

        set_active_default_background_pattern(pattern=BackgroundPattern.CHANNEL_THREE)

        assert active_default_background_pattern() is BackgroundPattern.CHANNEL_THREE

    def test_paint_default_background_covers_the_surface_with_the_default(self):
        """paint_default_background copies the active default pattern at the surface's size."""
        set_active_default_background_pattern(pattern=BackgroundPattern.CHANNEL_THREE)
        surface = pygame.Surface((40, 30))

        paint_default_background(surface=surface)

        expected = background_pattern_surface(
            pattern=BackgroundPattern.CHANNEL_THREE, size=(40, 30)
        )
        assert pygame.image.tobytes(surface, 'RGB') == pygame.image.tobytes(expected, 'RGB')

    def test_the_choices_are_the_option_values(self):
        """The patterns' values are the --default-background choices."""
        assert [pattern.value for pattern in BackgroundPattern] == ['test-pattern', 'channel-3']
