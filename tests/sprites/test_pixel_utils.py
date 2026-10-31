"""Test suite for pixel utility functions.

Tests bounding box computation, pixel transparency detection,
envelope bounding box calculation, and the pixel-row rule (normalize_pixel_rows).
"""

import pytest

from glitchygames.sprites.pixel_utils import (
    compute_bounding_box,
    compute_bounding_box_from_pixels,
    compute_envelope_bounding_box,
    convert_pixels_to_rgb_if_possible,
    create_alpha_surface,
    create_indexed_surface,
    extract_pixel_colors,
    is_color_transparent,
    is_pixel_transparent,
    lookup_rgba_pixel_char,
    needs_alpha_channel,
    normalize_pixel_rows,
    palette_key_problems,
)


class TestIsPixelTransparent:
    """Test pixel transparency detection across RGB and RGBA modes."""

    def test_rgb_magenta_is_transparent(self):
        """Magenta (255, 0, 255) in RGB mode is transparent."""
        color_map = {'X': (255, 0, 255)}
        assert is_pixel_transparent('X', color_map) is True

    def test_rgb_non_magenta_is_opaque(self):
        """Non-magenta RGB colors are opaque."""
        color_map = {'R': (255, 0, 0)}
        assert is_pixel_transparent('R', color_map) is False

    def test_rgb_black_is_opaque(self):
        """Black (0, 0, 0) in RGB mode is opaque, not transparent."""
        color_map = {'.': (0, 0, 0)}
        assert is_pixel_transparent('.', color_map) is False

    def test_rgba_alpha_zero_is_transparent(self):
        """RGBA with alpha=0 is fully transparent."""
        color_map = {'.': (0, 0, 0, 0)}
        assert is_pixel_transparent('.', color_map) is True

    def test_rgba_magenta_alpha_255_is_transparent(self):
        """RGBA magenta with alpha=255 is transparent (magenta key stored as RGBA)."""
        color_map = {'X': (255, 0, 255, 255)}
        assert is_pixel_transparent('X', color_map) is True

    def test_rgba_semi_transparent_is_opaque(self):
        """Semi-transparent pixels (alpha 1-254) are treated as opaque for hitbox purposes."""
        color_map = {'S': (255, 0, 0, 128)}
        assert is_pixel_transparent('S', color_map) is False

    def test_rgba_alpha_one_is_opaque(self):
        """Even alpha=1 (barely visible) is treated as opaque."""
        color_map = {'S': (100, 100, 100, 1)}
        assert is_pixel_transparent('S', color_map) is False

    def test_rgba_alpha_254_is_opaque(self):
        """Alpha=254 is treated as opaque."""
        color_map = {'S': (100, 100, 100, 254)}
        assert is_pixel_transparent('S', color_map) is False

    def test_rgba_fully_opaque_non_magenta_is_opaque(self):
        """RGBA non-magenta with alpha=255 is opaque."""
        color_map = {'R': (255, 0, 0, 255)}
        assert is_pixel_transparent('R', color_map) is False

    def test_undefined_character_is_transparent(self):
        """Characters not in color map default to magenta = transparent."""
        color_map = {'R': (255, 0, 0)}
        assert is_pixel_transparent('?', color_map) is True

    def test_rgba_non_magenta_alpha_zero_is_transparent(self):
        """Any RGBA color with alpha=0 is transparent, regardless of RGB values."""
        color_map = {'X': (255, 0, 0, 0)}
        assert is_pixel_transparent('X', color_map) is True

    def test_empty_color_map_all_transparent(self):
        """With empty color map, all characters are transparent (default to magenta)."""
        color_map: dict[str, tuple[int, ...]] = {}
        assert is_pixel_transparent('A', color_map) is True
        assert is_pixel_transparent('.', color_map) is True


class TestComputeBoundingBox:
    """Test tight bounding box computation from pixel grids."""

    def test_simple_square(self):
        """Compute bounding box for a simple opaque square surrounded by transparency."""
        color_map = {
            '.': (255, 0, 255),
            'X': (255, 0, 0),
        }
        pixel_lines = [
            '....',
            '.XX.',
            '.XX.',
            '....',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 1, 'offset_y': 1, 'width': 2, 'height': 2}

    def test_full_frame_opaque(self):
        """When the entire frame is opaque, bounding box equals frame dimensions."""
        color_map = {'X': (255, 0, 0)}
        pixel_lines = [
            'XXX',
            'XXX',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 0, 'offset_y': 0, 'width': 3, 'height': 2}

    def test_fully_transparent_returns_none(self):
        """Fully transparent frame returns None."""
        color_map = {'.': (255, 0, 255)}
        pixel_lines = [
            '...',
            '...',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result is None

    def test_single_pixel(self):
        """Single opaque pixel gives 1x1 bounding box."""
        color_map = {
            '.': (255, 0, 255),
            'X': (255, 0, 0),
        }
        pixel_lines = [
            '....',
            '..X.',
            '....',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 2, 'offset_y': 1, 'width': 1, 'height': 1}

    def test_top_left_corner(self):
        """Pixel at top-left corner."""
        color_map = {
            '.': (255, 0, 255),
            'X': (255, 0, 0),
        }
        pixel_lines = [
            'X...',
            '....',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 0, 'offset_y': 0, 'width': 1, 'height': 1}

    def test_bottom_right_corner(self):
        """Pixel at bottom-right corner."""
        color_map = {
            '.': (255, 0, 255),
            'X': (255, 0, 0),
        }
        pixel_lines = [
            '....',
            '...X',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 3, 'offset_y': 1, 'width': 1, 'height': 1}

    def test_asymmetric_padding(self):
        """Bounding box with different padding on each side."""
        color_map = {
            '.': (255, 0, 255),
            'X': (0, 0, 255),
        }
        pixel_lines = [
            '......',
            '..XX..',
            '..XXX.',
            '..XX..',
            '......',
            '......',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 2, 'offset_y': 1, 'width': 3, 'height': 3}

    def test_rgba_alpha_zero_transparency(self):
        """Bounding box respects RGBA alpha=0 as transparent."""
        color_map = {
            '.': (0, 0, 0, 0),
            'X': (255, 0, 0, 255),
        }
        pixel_lines = [
            '....',
            '.XX.',
            '....',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 1, 'offset_y': 1, 'width': 2, 'height': 1}

    def test_semi_transparent_included_in_bounding_box(self):
        """Semi-transparent pixels (alpha 1-254) are included in the bounding box."""
        color_map = {
            '.': (0, 0, 0, 0),
            'S': (255, 0, 0, 128),
            'X': (255, 0, 0, 255),
        }
        pixel_lines = [
            '....',
            '.SX.',
            '....',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 1, 'offset_y': 1, 'width': 2, 'height': 1}

    def test_undefined_chars_are_transparent(self):
        """Characters not in color map are transparent (default to magenta)."""
        color_map = {
            'X': (255, 0, 0),
        }
        pixel_lines = [
            '????',
            '?XX?',
            '????',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 1, 'offset_y': 1, 'width': 2, 'height': 1}

    def test_brave_adventurer_style_magenta(self):
        """Test with the block character style used by brave adventurer sprites."""
        magenta_char = '\u2588'  # █
        color_map = {
            magenta_char: (255, 0, 255),
            'H': (40, 30, 20),
            'S': (180, 130, 80),
        }
        pixel_lines = [
            f'{magenta_char}{magenta_char}HH{magenta_char}{magenta_char}',
            f'{magenta_char}HHHH{magenta_char}',
            f'{magenta_char}HSSH{magenta_char}',
            f'{magenta_char}{magenta_char}HH{magenta_char}{magenta_char}',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 1, 'offset_y': 0, 'width': 4, 'height': 4}

    def test_empty_pixel_lines(self):
        """Empty pixel lines returns None."""
        color_map = {'X': (255, 0, 0)}
        result = compute_bounding_box([], color_map)
        assert result is None

    def test_inconsistent_row_widths(self):
        """Handles inconsistent row widths gracefully."""
        color_map = {
            '.': (255, 0, 255),
            'X': (255, 0, 0),
        }
        pixel_lines = [
            '.X',
            '.X...',
            '.X',
        ]
        result = compute_bounding_box(pixel_lines, color_map)
        assert result == {'offset_x': 1, 'offset_y': 0, 'width': 1, 'height': 3}


class TestComputeEnvelopeBoundingBox:
    """Test union envelope computation across multiple bounding boxes."""

    def test_identical_boxes(self):
        """Envelope of identical boxes equals the single box."""
        boxes = [
            {'offset_x': 2, 'offset_y': 1, 'width': 4, 'height': 3},
            {'offset_x': 2, 'offset_y': 1, 'width': 4, 'height': 3},
        ]
        result = compute_envelope_bounding_box(boxes)
        assert result == {'offset_x': 2, 'offset_y': 1, 'width': 4, 'height': 3}

    def test_overlapping_boxes(self):
        """Envelope encompasses both overlapping boxes."""
        boxes = [
            {'offset_x': 1, 'offset_y': 1, 'width': 3, 'height': 3},
            {'offset_x': 2, 'offset_y': 2, 'width': 4, 'height': 4},
        ]
        result = compute_envelope_bounding_box(boxes)
        assert result == {'offset_x': 1, 'offset_y': 1, 'width': 5, 'height': 5}

    def test_non_overlapping_boxes(self):
        """Envelope spans the gap between non-overlapping boxes."""
        boxes = [
            {'offset_x': 0, 'offset_y': 0, 'width': 2, 'height': 2},
            {'offset_x': 8, 'offset_y': 8, 'width': 2, 'height': 2},
        ]
        result = compute_envelope_bounding_box(boxes)
        assert result == {'offset_x': 0, 'offset_y': 0, 'width': 10, 'height': 10}

    def test_single_box(self):
        """Envelope of a single box equals that box."""
        boxes = [
            {'offset_x': 3, 'offset_y': 5, 'width': 10, 'height': 8},
        ]
        result = compute_envelope_bounding_box(boxes)
        assert result == {'offset_x': 3, 'offset_y': 5, 'width': 10, 'height': 8}

    def test_empty_list_returns_none(self):
        """Envelope of no boxes returns None."""
        result = compute_envelope_bounding_box([])
        assert result is None

    def test_many_frames(self):
        """Envelope of many frames finds the outer bounds."""
        boxes = [
            {'offset_x': 4, 'offset_y': 0, 'width': 12, 'height': 25},
            {'offset_x': 2, 'offset_y': 0, 'width': 14, 'height': 25},
            {'offset_x': 1, 'offset_y': 0, 'width': 17, 'height': 25},
            {'offset_x': 0, 'offset_y': 0, 'width': 18, 'height': 27},
        ]
        result = compute_envelope_bounding_box(boxes)
        assert result == {'offset_x': 0, 'offset_y': 0, 'width': 18, 'height': 27}


class TestNeedsAlphaChannel:
    """needs_alpha_channel looks at every pixel until one needs alpha."""

    def test_opaque_rgb_pixels_before_magenta_are_skipped(self):
        """Ordinary RGB pixels do not need alpha, but a later RGB magenta pixel does."""
        assert needs_alpha_channel(pixels=[(1, 2, 3), (4, 5, 6), (255, 0, 255)]) is True

    def test_all_opaque_pixels_need_no_alpha(self):
        """Only opaque non-magenta pixels (RGB or RGBA alpha 255) need no alpha channel."""
        assert needs_alpha_channel(pixels=[(1, 2, 3), (4, 5, 6, 255)]) is False

    def test_pixels_of_other_lengths_are_ignored(self):
        """A pixel that is neither RGB nor RGBA (here a 2-tuple) never asks for alpha."""
        assert needs_alpha_channel(pixels=[(255, 0), (1, 2, 3)]) is False


class TestConvertPixelsToRgbIfPossible:
    """Opaque RGBA pixels collapse to RGB."""

    def test_opaque_rgba_pixels_collapse_to_rgb(self):
        """All-opaque RGBA pixels become RGB; RGB pixels pass through unchanged."""
        converted = convert_pixels_to_rgb_if_possible(pixels=[(1, 2, 3, 255), (4, 5, 6)])

        assert converted == [(1, 2, 3), (4, 5, 6)]


class TestLookupRgbaPixelChar:
    """Magenta lookups fail clearly when the map has no magenta entry."""

    def test_magenta_pixel_without_a_magenta_entry_raises(self):
        """An RGBA magenta pixel with neither RGB nor RGBA magenta in the map is a KeyError."""
        with pytest.raises(KeyError, match='255, 0, 255'):
            lookup_rgba_pixel_char(
                pixel=(255, 0, 255, 255), color_map={(0, 0, 0): '.'}, map_uses_alpha=False
            )


class TestExtractPixelColors:
    """extract_pixel_colors reads characters through the color map."""

    def test_characters_outside_the_frame_read_as_magenta(self):
        """A row longer than the width, or rows past the height, are magenta, not mapped."""
        color_map: dict[str, tuple[int, ...]] = {'#': (10, 20, 30)}

        pixels = extract_pixel_colors(
            pixel_lines=['##', '#'], width=1, height=1, color_map=color_map
        )

        assert pixels == [(10, 20, 30), (255, 0, 255), (255, 0, 255)]

    def test_unmapped_characters_read_as_magenta(self):
        """A character with no color map entry defaults to the magenta transparency key."""
        pixels = extract_pixel_colors(pixel_lines=['?'], width=1, height=1, color_map={})

        assert pixels == [(255, 0, 255)]


class TestIsColorTransparent:
    """is_color_transparent applies the transparency rules to resolved color tuples."""

    def test_rgba_alpha_zero_is_transparent(self):
        """Any RGBA color with alpha 0 is transparent."""
        assert is_color_transparent(color=(12, 34, 56, 0)) is True

    def test_rgba_opaque_magenta_is_transparent(self):
        """Opaque RGBA magenta is the transparency key stored as RGBA."""
        assert is_color_transparent(color=(255, 0, 255, 255)) is True

    def test_semi_transparent_magenta_is_visible(self):
        """Magenta with a partial alpha is visibly drawn, so it counts as opaque."""
        assert is_color_transparent(color=(255, 0, 255, 128)) is False

    def test_rgb_magenta_is_transparent_and_other_rgb_is_not(self):
        """For RGB colors only magenta is transparent."""
        assert is_color_transparent(color=(255, 0, 255)) is True
        assert is_color_transparent(color=(255, 0, 254)) is False


class TestComputeBoundingBoxFromPixels:
    """The bounding box of resolved pixel data, without a color map."""

    MAGENTA = (255, 0, 255)

    def test_box_spans_the_visible_pixels(self):
        """A 4x3 frame with visible pixels at (1, 0) and (2, 2) is boxed from (1, 0), 2x3."""
        pixels: list[tuple[int, ...]] = [self.MAGENTA] * 12
        pixels[1] = (1, 1, 1)
        pixels[2 * 4 + 2] = (2, 2, 2, 255)

        assert compute_bounding_box_from_pixels(pixels=pixels, width=4, height=3) == {
            'offset_x': 1,
            'offset_y': 0,
            'width': 2,
            'height': 3,
        }

    def test_fully_transparent_frame_has_no_box(self):
        """A frame of only transparent pixels answers None."""
        pixels = [self.MAGENTA, (0, 0, 0, 0)]

        assert compute_bounding_box_from_pixels(pixels=pixels, width=2, height=1) is None

    def test_pixels_beyond_width_times_height_are_ignored(self):
        """Extra trailing pixels past width * height do not grow the box."""
        pixels = [(1, 1, 1), self.MAGENTA, (9, 9, 9)]

        assert compute_bounding_box_from_pixels(pixels=pixels, width=2, height=1) == {
            'offset_x': 0,
            'offset_y': 0,
            'width': 1,
            'height': 1,
        }


class TestSurfaceCreationClipsToTheFrame:
    """Characters outside width x height are not drawn on either surface kind."""

    def test_alpha_surface_ignores_characters_outside_the_frame(self):
        """A 1x1 alpha surface draws only the first character; the rest are dropped."""
        color_map = {'#': (10, 20, 30), '@': (40, 50, 60, 70)}

        surface = create_alpha_surface(
            width=1, height=1, pixel_lines=['#@', '@@'], color_map=color_map
        )

        assert surface.get_size() == (1, 1)
        assert tuple(surface.get_at((0, 0))) == (10, 20, 30, 255)

    def test_indexed_surface_ignores_characters_outside_the_frame(self):
        """A 1x1 indexed surface draws only the first character; the rest are dropped."""
        color_map = {'#': (10, 20, 30), '@': (40, 50, 60, 255)}

        surface = create_indexed_surface(
            width=1, height=1, pixel_lines=['#@', '@@'], color_map=color_map
        )

        assert surface.get_size() == (1, 1)
        assert tuple(surface.get_at((0, 0)))[:3] == (10, 20, 30)


class TestNormalizePixelRows:
    """The one rule for pixel rows (docs/specs/2026-10-30-unified-pixel-rows-design.md)."""

    def test_rectangle_is_unchanged_and_unreported(self):
        """Rows that already form a rectangle come back as they are, with no repairs."""
        result = normalize_pixel_rows('ab\nab', 'ab')
        assert result.rows == ('ab', 'ab')
        assert (result.width, result.height) == (2, 2)
        assert result.repairs == ()

    def test_long_row_widens_never_truncates(self):
        """A sword's crossguard widens the frame instead of being cut off."""
        result = normalize_pixel_rows('x\nxxxx\nx\nx', 'x')
        assert result.rows == ('x\0\0\0', 'xxxx', 'x\0\0\0', 'x\0\0\0')
        assert result.repairs == (
            'row widths differ (1, 4); short rows padded with transparent pixels to 4',
        )

    def test_mode_cannot_cut_a_row(self):
        """Two short rows don't outvote the long one: nothing is cut."""
        result = normalize_pixel_rows('abcd\nab\nab', 'abcd')
        assert result.rows[0] == 'abcd'

    def test_blank_interior_line_is_a_transparent_row(self):
        """A blank line between rows stays, as a transparent row, and is reported."""
        result = normalize_pixel_rows('ab\n\nab', 'ab')
        assert result.rows == ('ab', '\0\0', 'ab')
        assert result.repairs == ('blank line between rows (line 2); drawn as transparent rows',)

    def test_outer_blank_lines_and_trailing_whitespace_are_tidied(self):
        """Outer blank lines and trailing whitespace go without a report.

        'ab' is not short: before its trailing spaces were trimmed it was 'ab  ', length 4,
        at least the width of 3.
        """
        result = normalize_pixel_rows('\n\nab  \n ab\t\n\n', 'ab')
        assert result.rows == ('ab\0', ' ab')
        assert result.repairs == ()

    def test_shared_indentation_is_removed(self):
        """Indentation every row shares is TOML layout, not art."""
        result = normalize_pixel_rows('    ab\n    ab', 'ab')
        assert result.rows == ('ab', 'ab')
        assert result.repairs == ()

    def test_shared_tab_indentation_is_removed(self):
        """A shared tab prefix is removed like spaces."""
        result = normalize_pixel_rows('\tab\n\tab', 'ab')
        assert result.rows == ('ab', 'ab')
        assert result.repairs == ()

    def test_unshared_indentation_stays_and_is_not_reported(self):
        """A pyramid drawn with spaces as its transparent pixels stays a pyramid."""
        result = normalize_pixel_rows('  x  \n xxx \nxxxxx', 'x')
        assert result.rows == ('  x\0\0', ' xxx\0', 'xxxxx')
        assert result.repairs == ()

    def test_mixed_prefix_characters_are_not_shared(self):
        """A prefix is shared character for character; a tab is not a space."""
        result = normalize_pixel_rows(' \tab\n\t ab', 'ab')
        assert result.rows == (' \tab', '\t ab')
        assert result.repairs == ("glyphs not in the palette: '\\t'; drawn transparent",)

    def test_crlf_is_tidied_not_reported(self):
        """Windows line endings load like Unix ones."""
        result = normalize_pixel_rows('ab\r\nab\r\n', 'ab')
        assert result.rows == ('ab', 'ab')
        assert result.repairs == ()

    def test_unknown_glyph_is_reported_space_is_not(self):
        """A glyph missing from the palette is reported; a space never is."""
        result = normalize_pixel_rows('aq a\na  a', 'a')
        assert result.repairs == ("glyphs not in the palette: 'q'; drawn transparent",)

    @pytest.mark.parametrize('pixels', ['', '\n  \n'])
    def test_blank_text_has_no_rows(self, pixels):
        """Blank pixel text has no rows and nothing to report."""
        result = normalize_pixel_rows(pixels, 'a')
        assert result.rows == ()
        assert (result.width, result.height) == (0, 0)
        assert result.repairs == ()

    def test_each_code_point_is_one_pixel(self):
        """A combining mark and an emoji's variation selector are pixels of their own."""
        assert normalize_pixel_rows('ée', 'é').width == 3
        assert normalize_pixel_rows('❤️', '❤️').width == 2

    def test_strict_raises_with_every_repair(self):
        """Strict mode raises one error naming the block and every repair."""
        with pytest.raises(ValueError, match=r'^walk frame 0: row widths differ .*; blank line'):
            normalize_pixel_rows('ab\n\na', 'ab', strict=True, label='walk frame 0')

    def test_palette_key_problems(self):
        """Keys that aren't one code point, and U+0000 (the padding glyph), are reported."""
        expected = 'palette keys that are not one code point: ' + ', '.join(
            sorted([repr('\x00'), repr('❤️')])
        )
        assert palette_key_problems(['a', '❤️', '\x00', 'b']) == (expected,)
        assert palette_key_problems(['a']) == ()
