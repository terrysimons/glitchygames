"""The test display rule: every test starts on the canvas, and an all-black last frame fails.

The rule lives in tests/harness.py (the canvas before each test, the present and the guard
after the body) and tests/display_canvas.py (the canvas and the black check).
"""

from __future__ import annotations

import pygame
import pytest

from glitchygames.backgrounds import BackgroundPattern, background_pattern_surface
from tests import display_canvas
from tests.display_canvas import (
    CANVAS_PATTERN,
    TEST_CANVAS_VARIABLE,
    TEST_DISPLAY_SIZE,
    canvas_color_at,
    display_looks_entirely_black,
    real_display_surface,
    show_canvas,
    show_canvas_on_new_display,
)
from tests.harness import _fail_on_entirely_black_frame

BLACK_RGB = (0, 0, 0)
# A colour dim enough that a few pixels of it average down to black
DIM_GREY = (1, 1, 1)


class TestTheCanvas:
    """What a test sees before it draws anything."""

    def test_every_test_starts_on_the_opaque_canvas(self):
        """The display shows the canvas pattern, opaque, before the test draws."""
        display = real_display_surface()
        assert display is not None
        expected = background_pattern_surface(pattern=CANVAS_PATTERN, size=display.get_size())

        assert pygame.image.tobytes(display, 'RGB') == pygame.image.tobytes(expected, 'RGB')
        assert display.get_at((0, 0)).a == 255

    def test_canvas_color_at_names_an_untouched_pixel(self):
        """canvas_color_at gives the colour the display shows where nothing was drawn."""
        display = real_display_surface()
        assert display is not None

        for position in [(0, 0), (400, 300), (799, 599), (650, 520)]:
            x, y = position
            assert display.get_at(position)[:3] == canvas_color_at(x=x, y=y)[:3]

    def test_a_new_display_gets_the_canvas(self):
        """show_canvas_on_new_display sets the mode and shows the canvas at the new size."""
        # Wider than a window manager's smallest window (XQuartz widens 64 pixels to 72)
        size = (96, 64)
        display = show_canvas_on_new_display(size=size)

        assert display.get_size() == size
        assert display.get_at((95, 63))[:3] == canvas_color_at(x=95, y=63, size=size)[:3]

    def test_the_canvas_is_skipped_without_a_display(self):
        """With the display module stopped there is nothing to draw on or present."""
        pygame.display.quit()
        try:
            assert real_display_surface() is None
            show_canvas()  # nothing to draw on: no error
        finally:
            pygame.display.init()
            show_canvas_on_new_display(size=TEST_DISPLAY_SIZE)

    def test_the_canvas_variable_names_a_pattern(self, monkeypatch):
        """GLITCHYGAMES_TEST_CANVAS picks the pattern; a name that is none is refused."""
        monkeypatch.setenv(TEST_CANVAS_VARIABLE, BackgroundPattern.CHANNEL_THREE.value)
        assert display_canvas._canvas_pattern_from_environment() is BackgroundPattern.CHANNEL_THREE

        monkeypatch.setenv(TEST_CANVAS_VARIABLE, 'snow')
        with pytest.raises(ValueError, match='names no background pattern'):
            display_canvas._canvas_pattern_from_environment()


class TestTheBlackFrameCheck:
    """display_looks_entirely_black, and the guard failing a test that ends looking black."""

    def test_black_is_entirely_black(self):
        """A display filled black is entirely black."""
        surface = pygame.Surface((32, 24))
        surface.fill(BLACK_RGB)

        assert display_looks_entirely_black(surface)

    def test_a_few_dim_pixels_are_not_black(self):
        """A dim pixel the average rounds away is still found, pixel by pixel."""
        surface = pygame.Surface((800, 600))
        surface.fill(BLACK_RGB)
        surface.set_at((799, 599), DIM_GREY)

        assert pygame.transform.average_color(surface)[:3] == BLACK_RGB
        assert not display_looks_entirely_black(surface)

    def test_colours_under_alpha_0_look_black(self):
        """On a display with per-pixel alpha (cocoa's) the window shows alpha 0 as black.

        Built as a SRCALPHA surface so the rule is tested on the dummy driver too.
        """
        surface = pygame.Surface((32, 24), pygame.SRCALPHA)
        surface.fill((200, 100, 50, 0))

        assert display_looks_entirely_black(surface)

    def test_one_coloured_pixel_under_alpha_0_still_looks_black(self):
        """An opaque black frame whose only colour has alpha 0 looks entirely black."""
        surface = pygame.Surface((800, 600), pygame.SRCALPHA)
        surface.fill((*BLACK_RGB, 255))
        surface.set_at((5, 5), (200, 100, 50, 0))

        assert display_looks_entirely_black(surface)

    def test_one_visible_pixel_among_transparent_ones_does_not_look_black(self):
        """A coloured pixel with any alpha shows; the rest of the frame looking black is fine."""
        surface = pygame.Surface((800, 600), pygame.SRCALPHA)
        surface.fill((200, 100, 50, 0))
        surface.set_at((799, 599), (*DIM_GREY, 1))

        assert not display_looks_entirely_black(surface)

    def test_an_opaque_coloured_frame_with_per_pixel_alpha_does_not_look_black(self):
        """The usual frame on cocoa: opaque colours (alpha 255 everywhere)."""
        surface = pygame.Surface((32, 24), pygame.SRCALPHA)
        surface.fill((*DIM_GREY, 255))

        assert not display_looks_entirely_black(surface)

    def test_the_guard_fails_a_frame_that_only_looks_black(self, request):
        """The guard judges what the window shows: colours under alpha 0 are a black frame."""
        transparent_frame = pygame.Surface(TEST_DISPLAY_SIZE, pygame.SRCALPHA)
        transparent_frame.fill((200, 100, 50, 0))

        with pytest.raises(pytest.fail.Exception, match='looks entirely black'):
            _fail_on_entirely_black_frame(item=request.node, display_surface=transparent_frame)

    def test_the_guard_fails_a_test_whose_last_frame_is_black(self, request):
        """The guard fails with the rendering-bug message when the display is all black."""
        display = real_display_surface()
        assert display is not None
        display.fill(BLACK_RGB)
        try:
            with pytest.raises(pytest.fail.Exception, match='rendering bug'):
                _fail_on_entirely_black_frame(item=request.node)
        finally:
            show_canvas()

    def test_the_guard_passes_a_frame_with_anything_on_it(self, request):
        """A black display with one dim pixel on it is not a rendering bug."""
        display = real_display_surface()
        assert display is not None
        display.fill(BLACK_RGB)
        display.set_at((0, 0), DIM_GREY)

        _fail_on_entirely_black_frame(item=request.node)

    @pytest.mark.black_frame_expected(reason='checks the opt-out marker itself')
    def test_the_marker_opts_a_test_out(self, request):
        """A test marked black_frame_expected may end on an all-black frame."""
        display = real_display_surface()
        assert display is not None
        display.fill(BLACK_RGB)

        _fail_on_entirely_black_frame(item=request.node)
