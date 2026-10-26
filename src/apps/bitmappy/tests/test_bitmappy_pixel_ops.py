"""Tests for bitmappy.pixel_ops: alpha blending, compositing and ASCII layout."""

import os

import pygame
import pytest

from bitmappy.pixel_ops import (
    _alpha_blend_pixel,
    _combine_row_frames,
    _composite_frames_with_alpha,
    _create_composite_frame_from_pixels,
    render_frame_to_ascii,
    render_frames_side_by_side,
)
from glitchygames.sprites.animated import SpriteFrame


class PassThroughRenderer:
    """An ASCII renderer stand-in that returns the glyph grid without colour codes."""

    def colorize_pixels(self, pixels: str, colors: dict[str, tuple[int, int, int, int]]) -> str:
        """Return the glyph grid unchanged.

        Args:
            pixels: The glyph grid.
            colors: The glyph-to-colour map (ignored).

        Returns:
            The glyph grid.

        """
        del colors
        return pixels


class FailingRenderer:
    """An ASCII renderer stand-in whose colouring always fails."""

    def colorize_pixels(self, pixels: str, colors: dict[str, tuple[int, int, int, int]]) -> str:
        """Raise the error a broken colour map would raise.

        Args:
            pixels: The glyph grid (ignored).
            colors: The glyph-to-colour map (ignored).

        Raises:
            KeyError: Always.

        """
        del pixels, colors
        message = 'missing glyph'
        raise KeyError(message)


def make_frame(*, pixels: list[tuple[int, ...]], width: int, height: int) -> SpriteFrame:
    """Build a SpriteFrame holding the given pixels.

    Args:
        pixels: Row-major pixel tuples.
        width: Frame width.
        height: Frame height.

    Returns:
        The frame.

    """
    frame = SpriteFrame(pygame.Surface((width, height), pygame.SRCALPHA))
    frame.set_pixel_data(pixels)
    return frame


class TestAlphaBlendPixel:
    """Test _alpha_blend_pixel."""

    def test_negative_additional_alpha_gives_transparent_black(self):
        """A negative alpha multiplier leaves no coverage, so the result is transparent black."""
        blended = _alpha_blend_pixel(
            source=(10, 20, 30, 255),
            destination=(0, 0, 0, 0),
            additional_alpha=-1.0,
        )
        assert blended == (0, 0, 0, 0)

    def test_rgb_source_is_treated_as_opaque(self):
        """An RGB source pixel is fully opaque, so it replaces the destination."""
        blended = _alpha_blend_pixel(
            source=(10, 20, 30),
            destination=(200, 200, 200, 255),
            additional_alpha=1.0,
        )
        assert blended == (10, 20, 30, 255)


class TestCompositeFramesWithAlpha:
    """Test _composite_frames_with_alpha."""

    def test_no_frames_gives_no_pixels(self):
        """Compositing nothing gives an empty pixel list."""
        assert _composite_frames_with_alpha(frames=[]) == []

    def test_magenta_and_transparent_pixels_leave_the_composite_untouched(self):
        """Magenta and fully transparent pixels are skipped; opaque ones blend in."""
        frame = make_frame(
            pixels=[(255, 0, 255, 255), (10, 20, 30, 0), (100, 50, 0, 255)],
            width=3,
            height=1,
        )

        composite = _composite_frames_with_alpha(frames=[frame], additional_alpha=1.0)

        assert composite == [(0, 0, 0, 0), (0, 0, 0, 0), (100, 50, 0, 255)]

    def test_second_frame_blends_over_the_first(self):
        """A half-alpha second frame is composited over the first one."""
        first_frame = make_frame(pixels=[(0, 0, 0, 255)], width=1, height=1)
        second_frame = make_frame(pixels=[(200, 100, 50, 255)], width=1, height=1)

        composite = _composite_frames_with_alpha(
            frames=[first_frame, second_frame],
            additional_alpha=0.5,
        )

        # The first frame at half alpha gives (0, 0, 0, 127); the second at half alpha over it
        red, green, blue, alpha = composite[0]
        assert alpha > 127
        assert 0 < red < 200
        assert 0 < green < 100
        assert 0 < blue < 50


class TestCreateCompositeFrameFromPixels:
    """Test _create_composite_frame_from_pixels."""

    def test_pixels_are_drawn_and_kept(self):
        """The frame's surface shows the pixels and the frame keeps the pixel list."""
        pixels: list[tuple[int, ...]] = [(255, 0, 0, 255), (0, 255, 0, 128)]

        frame = _create_composite_frame_from_pixels(pixels=pixels, width=2, height=1, duration=0.25)

        assert frame.get_size() == (2, 1)
        assert frame.duration == pytest.approx(0.25)
        assert frame.pixels == pixels
        assert tuple(frame.image.get_at((0, 0))) == (255, 0, 0, 255)
        assert tuple(frame.image.get_at((1, 0))) == (0, 255, 0, 128)

    def test_pixels_beyond_the_height_are_ignored(self):
        """Pixels that would fall below the last row are not drawn."""
        pixels: list[tuple[int, ...]] = [(1, 2, 3, 255), (4, 5, 6, 255), (7, 8, 9, 255)]

        frame = _create_composite_frame_from_pixels(pixels=pixels, width=2, height=1)

        assert frame.get_size() == (2, 1)
        assert tuple(frame.image.get_at((1, 0))) == (4, 5, 6, 255)


class TestCombineRowFrames:
    """Test _combine_row_frames."""

    def test_shorter_frames_are_padded_to_the_tallest(self):
        """A shorter frame is padded with blank lines as wide as its first line."""
        row_lines = _combine_row_frames(row_frames=[['ab', 'cd'], ['xyz']], separator='|')

        assert row_lines == ['ab|xyz', 'cd|   ']

    def test_empty_frame_contributes_empty_parts(self):
        """A frame with no lines contributes an empty part to every line."""
        row_lines = _combine_row_frames(row_frames=[['ab', 'cd'], []], separator='|')

        assert row_lines == ['ab|', 'cd|']


class TestRenderFramesSideBySide:
    """Test render_frames_side_by_side."""

    def test_no_frames_renders_nothing(self):
        """No frames give an empty string."""
        assert not render_frames_side_by_side(frames=[], renderer=PassThroughRenderer())  # type: ignore[arg-type]

    def test_frames_that_fit_share_one_row(self, mocker):
        """Frames that fit in the terminal width are placed side by side."""
        mocker.patch('shutil.get_terminal_size', return_value=os.terminal_size((80, 24)))
        red_frame = make_frame(pixels=[(255, 0, 0, 255)] * 4, width=2, height=2)
        blue_frame = make_frame(pixels=[(0, 0, 255, 255)] * 4, width=2, height=2)

        output = render_frames_side_by_side(
            frames=[red_frame, blue_frame],
            renderer=PassThroughRenderer(),  # type: ignore[arg-type]
            separator='  ',
        )

        lines = output.split('\n')
        assert len(lines) == 2
        assert all(len(line) == 6 for line in lines)
        assert '\n\n' not in output

    def test_frames_wrap_to_the_terminal_width(self, mocker):
        """Frames that do not fit wrap into rows separated by a blank line."""
        mocker.patch('shutil.get_terminal_size', return_value=os.terminal_size((3, 24)))
        frames = [make_frame(pixels=[(255, 0, 0, 255)] * 4, width=2, height=2) for _ in range(3)]

        output = render_frames_side_by_side(frames=frames, renderer=PassThroughRenderer())  # type: ignore[arg-type]

        rows = output.split('\n\n')
        # A 3-column terminal holds one 2-wide frame per row (a second needs 2 + 2 + 2 columns)
        assert len(rows) == 3
        assert len(set(rows)) == 1
        assert [len(line) for line in rows[0].split('\n')] == [2, 2]

    def test_zero_height_frame_renders_nothing(self, mocker):
        """A frame with no rows has no pixels, so its placeholder has no lines."""
        mocker.patch('shutil.get_terminal_size', return_value=os.terminal_size((80, 24)))
        empty_frame = SpriteFrame(pygame.Surface((3, 0), pygame.SRCALPHA))

        output = render_frames_side_by_side(
            frames=[empty_frame],
            renderer=PassThroughRenderer(),  # type: ignore[arg-type]
        )

        assert not output

    def test_frame_without_pixels_renders_blank_placeholder_lines(self, mocker):
        """A frame that renders to an empty string contributes its width of blanks per row."""
        mocker.patch('shutil.get_terminal_size', return_value=os.terminal_size((80, 24)))
        mocker.patch('bitmappy.pixel_ops.render_frame_to_ascii', return_value='')
        frame = make_frame(pixels=[(1, 2, 3, 255)] * 6, width=3, height=2)

        output = render_frames_side_by_side(frames=[frame], renderer=PassThroughRenderer())  # type: ignore[arg-type]

        assert output == '   \n   '


class TestRenderFrameToAscii:
    """Test render_frame_to_ascii."""

    def test_colouring_failure_falls_back_to_plain_glyphs(self):
        """When the renderer cannot colour the grid, the plain glyph grid is returned."""
        frame = make_frame(pixels=[(10, 10, 10, 255), (20, 20, 20, 255)], width=2, height=1)

        output = render_frame_to_ascii(frame=frame, renderer=FailingRenderer())  # type: ignore[arg-type]

        assert len(output) == 2
        assert output[0] != output[1]

    def test_rendering_error_gives_empty_string(self, mocker):
        """An error reading the frame gives an empty string instead of raising."""
        frame = mocker.Mock()
        frame.get_pixel_data.side_effect = ValueError('bad frame')

        assert not render_frame_to_ascii(frame=frame, renderer=PassThroughRenderer())  # type: ignore[arg-type]

    def test_renderer_bug_outside_the_colouring_fallback_propagates(self, mocker):
        """A renderer error the plain-glyph fallback does not cover is raised, not hidden.

        Only reading and laying out the frame turns errors into an empty string; the renderer's
        colouring falls back to plain glyphs for AttributeError, KeyError and TypeError only.
        """
        frame = make_frame(pixels=[(10, 10, 10, 255), (20, 20, 20, 255)], width=2, height=1)
        renderer = PassThroughRenderer()
        mocker.patch.object(renderer, 'colorize_pixels', side_effect=ValueError('renderer bug'))

        with pytest.raises(ValueError, match='renderer bug'):
            render_frame_to_ascii(frame=frame, renderer=renderer)  # type: ignore[arg-type]

    def test_frame_without_pixels_gives_empty_string(self, mocker):
        """A frame with no pixel data renders as an empty string without colouring anything."""
        frame = mocker.Mock()
        frame.get_pixel_data.return_value = []
        renderer = PassThroughRenderer()
        colorize = mocker.spy(renderer, 'colorize_pixels')

        assert not render_frame_to_ascii(frame=frame, renderer=renderer)  # type: ignore[arg-type]
        assert colorize.call_count == 0
