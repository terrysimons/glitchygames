"""Tests for glitchygames.bitmappy.toml_processing.

Covers the permissive regex TOML parser's edge cases, the color-field repair helpers, and the
shared color quantization, glyph mapping and TOML generation utilities used by the PNG import
(file_io) and the AI integration (ai_manager).
"""

import logging
import tomllib

import numpy as np
import pygame
import pytest

from glitchygames.bitmappy.constants import MAGENTA_TRANSPARENT, TRANSPARENT_GLYPH
from glitchygames.bitmappy.toml_processing import (
    _ensure_array_of_tables,
    _fix_comma_separated_color_field,
    _fix_list_color_field,
    _is_sub_path,
    _parse_toml_with_regex,
    _strip_inline_comment,
    build_color_to_glyph_mapping,
    build_pixel_string_from_pixels,
    collect_unique_colors_from_pixels,
    color_distance,
    generate_pixel_string,
    generate_toml_content,
    normalize_toml_data,
    quantize_colors_if_needed,
)
from glitchygames.sprites import SPRITE_GLYPHS

LOG = logging.getLogger('test.toml_processing')


def _pixel_array_from_rows(rows: list[list[tuple[int, int, int]]]) -> np.ndarray:
    """Build a pygame-style (x, y, rgb) pixel array from row-major color rows.

    Returns:
        A numpy array indexed as array[x, y] like pygame.surfarray.array3d.

    """
    return np.array(rows, dtype=np.uint8).transpose(1, 0, 2)


# ---------------------------------------------------------------------------
# Regex parser edge cases
# ---------------------------------------------------------------------------


class TestParseTomlWithRegexEdgeCases:
    """Edge cases of the last-resort regex TOML parser."""

    def test_section_under_an_array_of_tables_nests_in_its_last_entry(self):
        """A [animation.extra] header after [[animation]] goes into the last animation."""
        content = '[[animation]]\nnamespace = "idle"\n[animation.extra]\nspeed = 2\n'

        data = _parse_toml_with_regex(content, LOG)

        assert data == {'animation': [{'namespace': 'idle', 'extra': {'speed': 2}}]}

    def test_section_outside_the_array_path_leaves_the_array(self):
        """A [colors] header after [[animation]] starts a top-level table again."""
        content = '[[animation]]\nnamespace = "idle"\n[colors]\ncount = 1\n'

        data = _parse_toml_with_regex(content, LOG)

        assert data == {'animation': [{'namespace': 'idle'}], 'colors': {'count': 1}}

    def test_key_under_a_scalar_section_is_skipped_with_a_warning(self, caplog):
        """A key whose section path runs through a scalar value cannot be stored."""
        content = '[a]\nb = 1\n[a.b]\nc = 2\n'

        with caplog.at_level(logging.WARNING, logger=LOG.name):
            data = _parse_toml_with_regex(content, LOG)

        assert data == {'a': {'b': 1}}
        assert any('Failed to parse line 4' in message for message in caplog.messages)

    def test_unterminated_multiline_string_reads_to_the_end(self):
        """A triple-quoted string with no closing quotes takes every remaining line."""
        content = '[sprite]\npixels = """\n##\n..'

        data = _parse_toml_with_regex(content, LOG)

        assert data == {'sprite': {'pixels': '\n##\n..'}}

    def test_unrecognized_line_is_ignored(self, caplog):
        """A line that is neither a header nor key = value is reported and skipped."""
        with caplog.at_level(logging.WARNING, logger=LOG.name):
            data = _parse_toml_with_regex('[sprite]\njunk\n', LOG)

        assert data == {'sprite': {}}
        assert any('Unrecognized line 2' in message for message in caplog.messages)


class TestIsSubPath:
    """Test _is_sub_path."""

    def test_longer_path_with_the_same_prefix_is_a_sub_path(self):
        """['animation', 'frame'] is under ['animation']."""
        assert _is_sub_path(['animation'], ['animation', 'frame']) is True

    def test_longer_path_with_a_different_prefix_is_not_a_sub_path(self):
        """['colors', 'x'] is not under ['animation']."""
        assert _is_sub_path(['animation'], ['colors', 'x']) is False

    def test_same_length_path_is_not_a_sub_path(self):
        """A path is not a sub path of itself."""
        assert _is_sub_path(['animation'], ['animation']) is False


class TestEnsureArrayOfTables:
    """Test _ensure_array_of_tables."""

    def test_missing_intermediate_key_is_created_as_a_table(self):
        """[[animation.frame]] with no animation yet creates animation as a table."""
        data: dict = {}

        _ensure_array_of_tables(data, ['animation', 'frame'])

        assert data == {'animation': {'frame': [{}]}}

    def test_existing_scalar_table_is_replaced_by_an_array(self):
        """A key that already holds a table becomes a one-entry array."""
        data: dict = {'frame': {'old': 1}}

        _ensure_array_of_tables(data, ['frame'])

        assert data == {'frame': [{}]}

    def test_intermediate_array_navigates_into_its_last_entry(self):
        """[[animation.frame]] appends to the frame list of the last animation."""
        data: dict = {'animation': [{'namespace': 'a'}, {'namespace': 'b'}]}

        _ensure_array_of_tables(data, ['animation', 'frame'])

        assert data == {'animation': [{'namespace': 'a'}, {'namespace': 'b', 'frame': [{}]}]}


class TestStripInlineComment:
    """Test _strip_inline_comment."""

    def test_unquoted_value_is_cut_at_the_comment(self):
        """An unquoted value loses everything from the first '#'."""
        assert _strip_inline_comment('5 # five') == '5'

    def test_quoted_value_keeps_hashes_inside_the_quotes(self):
        """A '#' inside the quoted string is part of the value."""
        assert _strip_inline_comment('"#" # glyph') == '"#"'

    def test_quoted_value_without_a_comment_is_unchanged(self):
        """A quoted value with nothing after it is returned as is."""
        assert _strip_inline_comment('"abc"') == '"abc"'

    def test_unclosed_quote_is_returned_unchanged(self):
        """A value with no closing quote cannot hold a comment."""
        assert _strip_inline_comment('"abc # not a comment') == '"abc # not a comment'

    def test_unquoted_value_without_a_comment_is_unchanged(self):
        """An unquoted value with no '#' is returned as is."""
        assert _strip_inline_comment('42') == '42'


# ---------------------------------------------------------------------------
# Color field repair
# ---------------------------------------------------------------------------


class TestFixCommaSeparatedColorFieldBranches:
    """Branches of _fix_comma_separated_color_field not covered elsewhere."""

    def test_field_other_than_red_green_or_blue_sets_nothing(self):
        """An alpha field with comma-separated values is not one this repair handles."""
        fixed_color: dict = {}

        _fix_comma_separated_color_field('alpha', '1, 2', fixed_color, 'x', LOG)

        assert fixed_color == {}

    def test_unparseable_value_keeps_the_raw_string(self):
        """'7,' has an empty second value, so red keeps the raw string."""
        fixed_color: dict = {}

        _fix_comma_separated_color_field('red', '7,', fixed_color, 'x', LOG)

        assert fixed_color == {'red': '7,'}


class TestFixListColorField:
    """Test _fix_list_color_field."""

    def test_red_with_three_values_splits_into_all_fields(self):
        """[255, 128, 0] under red becomes red, green and blue."""
        fixed_color: dict = {}

        _fix_list_color_field('red', [255, 128, 0], fixed_color, 'x', LOG)

        assert fixed_color == {'red': 255, 'green': 128, 'blue': 0}

    def test_red_with_one_value_sets_only_red(self):
        """[9] under red sets red alone."""
        fixed_color: dict = {}

        _fix_list_color_field('red', [9], fixed_color, 'x', LOG)

        assert fixed_color == {'red': 9}

    def test_red_with_two_values_sets_red_and_green(self):
        """[9, 8] under red sets red and green."""
        fixed_color: dict = {}

        _fix_list_color_field('red', [9, 8], fixed_color, 'x', LOG)

        assert fixed_color == {'red': 9, 'green': 8}

    def test_green_and_blue_take_their_first_value(self):
        """Lists under green and blue keep their first number."""
        fixed_color: dict = {}

        _fix_list_color_field('green', [10, 11], fixed_color, 'x', LOG)
        _fix_list_color_field('blue', [12.7], fixed_color, 'x', LOG)

        assert fixed_color == {'green': 10, 'blue': 12}

    def test_list_without_numbers_sets_nothing(self):
        """A list of strings has no usable value."""
        fixed_color: dict = {}

        _fix_list_color_field('blue', ['x'], fixed_color, 'x', LOG)
        _fix_list_color_field('red', ['x'], fixed_color, 'x', LOG)

        assert fixed_color == {}


# ---------------------------------------------------------------------------
# Shared color utilities
# ---------------------------------------------------------------------------


class TestNormalizeTomlDataErrors:
    """Error handling of normalize_toml_data."""

    def test_malformed_sprite_section_returns_the_input_unchanged(self):
        """A sprite section that is not a table cannot be normalized."""
        config_data = {'sprite': None}

        assert normalize_toml_data(config_data) is config_data


class TestColorDistance:
    """Test color_distance."""

    def test_returns_the_squared_euclidean_distance(self):
        """(0, 0, 0) to (1, 2, 3) is 1 + 4 + 9."""
        assert color_distance((0, 0, 0), (1, 2, 3)) == 14

    def test_identical_colors_are_zero_apart(self):
        """A color is at distance 0 from itself."""
        assert color_distance((5, 6, 7), (5, 6, 7)) == 0


class TestQuantizeColorsIfNeeded:
    """Test quantize_colors_if_needed."""

    def test_colors_within_the_limit_are_returned_unchanged(self):
        """Fewer colors than the limit need no quantization."""
        colors = {(0, 0, 0), (255, 255, 255)}

        assert quantize_colors_if_needed(colors, has_transparency=False, max_colors=2) is colors

    def test_transparency_reserves_one_slot(self):
        """Two colors with transparency and a limit of two must be quantized to one group."""
        colors = {(0, 0, 0), (1, 1, 1)}

        result = quantize_colors_if_needed(colors, has_transparency=True, max_colors=2)

        assert len(result) == 1
        assert result <= colors

    def test_near_colors_merge_into_one_group(self):
        """Colors closer than the grouping threshold collapse into one representative."""
        colors = {(10, 10, 10), (11, 11, 11), (12, 12, 12), (250, 250, 250)}

        result = quantize_colors_if_needed(colors, has_transparency=False, max_colors=3)

        assert len(result) == 2
        assert (250, 250, 250) in result
        assert len(result & {(10, 10, 10), (11, 11, 11), (12, 12, 12)}) == 1

    def test_far_colors_beyond_the_group_limit_join_the_closest_group(self):
        """When every group slot is used, a far color still joins its closest group."""
        colors = {(0, 0, 0), (255, 0, 0), (0, 255, 0), (0, 0, 255)}

        result = quantize_colors_if_needed(colors, has_transparency=False, max_colors=2)

        assert len(result) == 2
        assert result <= colors

    def test_logs_through_the_given_logger(self, caplog):
        """Quantization reports its result on the logger passed in."""
        colors = {(0, 0, 0), (255, 255, 255)}

        with caplog.at_level(logging.INFO, logger=LOG.name):
            quantize_colors_if_needed(colors, has_transparency=False, max_colors=1, log=LOG)

        assert any('Quantized to 1 representative colors' in m for m in caplog.messages)


class TestBuildColorToGlyphMapping:
    """Test build_color_to_glyph_mapping."""

    def test_colors_get_glyphs_in_sorted_color_order(self):
        """Colors are assigned SPRITE_GLYPHS in ascending color order."""
        mapping = build_color_to_glyph_mapping({(9, 9, 9), (1, 1, 1)}, has_transparency=False)

        assert mapping == {(1, 1, 1): SPRITE_GLYPHS[0], (9, 9, 9): SPRITE_GLYPHS[1]}

    def test_magenta_gets_the_transparent_glyph_with_transparency(self):
        """With transparency, magenta maps to the block glyph and is not given another."""
        mapping = build_color_to_glyph_mapping(
            {MAGENTA_TRANSPARENT, (0, 0, 0)},
            has_transparency=True,
        )

        assert mapping == {MAGENTA_TRANSPARENT: TRANSPARENT_GLYPH, (0, 0, 0): SPRITE_GLYPHS[0]}

    def test_magenta_is_an_ordinary_color_without_transparency(self):
        """Without transparency magenta gets a regular glyph."""
        mapping = build_color_to_glyph_mapping(
            {MAGENTA_TRANSPARENT},
            has_transparency=False,
            log=LOG,
        )

        assert mapping == {MAGENTA_TRANSPARENT: SPRITE_GLYPHS[0]}

    def test_colors_beyond_the_single_char_glyphs_share_the_closest_glyph(self):
        """With 64 glyphs, the 65th color reuses the glyph of its nearest mapped color."""
        colors = {(index, 0, 0) for index in range(64)} | {(63, 0, 1)}

        mapping = build_color_to_glyph_mapping(
            colors,
            has_transparency=False,
            force_single_char_glyphs=True,
        )

        assert len(mapping) == 65
        assert len(set(mapping.values())) == 64
        assert set(mapping.values()) == set(SPRITE_GLYPHS[:64])
        # (63, 0, 1) sorts after (63, 0, 0), so it is the one left over
        assert mapping[63, 0, 1] == mapping[63, 0, 0]


class TestGeneratePixelString:
    """Test generate_pixel_string."""

    def test_rows_use_the_glyphs_of_the_mapping(self):
        """Each pixel becomes its color's glyph, one row per line."""
        pixel_array = _pixel_array_from_rows([
            [(0, 0, 0), (255, 255, 255)],
            [(255, 255, 255), (0, 0, 0)],
        ])
        mapping = {(0, 0, 0): '#', (255, 255, 255): '.'}

        pixel_string = generate_pixel_string(
            pixel_array,
            2,
            2,
            has_transparency=False,
            original_image=None,
            color_mapping=mapping,
        )

        assert pixel_string == '#.\n.#'

    def test_transparent_pixels_of_the_original_image_become_magenta(self):
        """A pixel whose original alpha is below the threshold uses the magenta glyph."""
        pixel_array = _pixel_array_from_rows([[(0, 0, 0), (0, 0, 0)]])
        original_image = pygame.Surface((2, 1), pygame.SRCALPHA)
        original_image.fill((0, 0, 0, 255))
        original_image.set_at((1, 0), (0, 0, 0, 0))
        mapping = {(0, 0, 0): '#', MAGENTA_TRANSPARENT: TRANSPARENT_GLYPH}

        pixel_string = generate_pixel_string(
            pixel_array,
            2,
            1,
            has_transparency=True,
            original_image=original_image,
            color_mapping=mapping,
        )

        assert pixel_string == f'#{TRANSPARENT_GLYPH}'

    def test_unmapped_color_uses_the_closest_mapped_glyph(self):
        """A color missing from the mapping is added with its nearest color's glyph."""
        pixel_array = _pixel_array_from_rows([[(250, 250, 250), (5, 5, 5)]])
        mapping = {(0, 0, 0): '#', (255, 255, 255): '.'}

        pixel_string = generate_pixel_string(
            pixel_array,
            2,
            1,
            has_transparency=False,
            original_image=None,
            color_mapping=mapping,
            log=LOG,
        )

        assert pixel_string == '.#'
        assert mapping[250, 250, 250] == '.'
        assert mapping[5, 5, 5] == '#'

    def test_tall_images_log_progress(self, caplog):
        """Images taller than the progress threshold log every tenth of their rows."""
        height = 40
        pixel_array = _pixel_array_from_rows([[(0, 0, 0)] for _ in range(height)])

        with caplog.at_level(logging.INFO, logger=LOG.name):
            pixel_string = generate_pixel_string(
                pixel_array,
                1,
                height,
                has_transparency=False,
                original_image=None,
                color_mapping={(0, 0, 0): '#'},
                log=LOG,
            )

        assert pixel_string == '\n'.join(['#'] * height)
        progress_messages = [m for m in caplog.messages if m.startswith('Progress:')]
        assert len(progress_messages) == 10


class TestGenerateTomlContent:
    """Test generate_toml_content."""

    def test_content_parses_to_the_sprite_and_its_colors(self):
        """The generated TOML names the sprite after the file and defines every glyph."""
        mapping = {(0, 0, 0): '#', (255, 255, 255): '.'}

        content = generate_toml_content('/some/dir/hero.png', '#.\n.#', mapping)
        data = tomllib.loads(content)

        assert data['sprite']['name'] == 'imported_from_hero'
        assert data['sprite']['pixels'] == '#.\n.#\n'
        assert data['colors'] == {
            '#': {'red': 0, 'green': 0, 'blue': 0},
            '.': {'red': 255, 'green': 255, 'blue': 255},
        }

    def test_shared_glyph_is_defined_once_from_its_first_color(self):
        """Two colors sharing a glyph produce one color definition."""
        mapping = {(0, 0, 0): '#', (1, 1, 1): '#'}

        content = generate_toml_content('a.png', '##', mapping, log=LOG)

        assert tomllib.loads(content)['colors'] == {'#': {'red': 0, 'green': 0, 'blue': 0}}

    def test_each_glyph_takes_the_color_mapped_to_it(self):
        """A glyph's definition comes from its own color even when other colors come first."""
        mapping = {(0, 0, 0): 'b', (9, 9, 9): 'a'}

        content = generate_toml_content('a.png', 'ab', mapping)

        assert tomllib.loads(content)['colors'] == {
            'a': {'red': 9, 'green': 9, 'blue': 9},
            'b': {'red': 0, 'green': 0, 'blue': 0},
        }

    def test_empty_mapping_raises_value_error(self):
        """A sprite with no colors cannot be generated."""
        with pytest.raises(ValueError, match='No colors found'):
            generate_toml_content('a.png', '', {})


class TestCollectUniqueColorsFromPixels:
    """Test collect_unique_colors_from_pixels."""

    def test_collects_rgb_of_rgb_and_rgba_pixels(self):
        """RGBA pixels contribute their RGB part; duplicates collapse."""
        pixels = [(1, 2, 3), (1, 2, 3, 255), (4, 5, 6, 0)]

        assert collect_unique_colors_from_pixels(pixels) == {(1, 2, 3), (4, 5, 6)}

    def test_short_pixels_are_skipped(self):
        """Pixels with fewer than three components are not colors."""
        assert collect_unique_colors_from_pixels([(1, 2), (7, 8, 9)]) == {(7, 8, 9)}


class TestBuildPixelStringFromPixels:
    """Test build_pixel_string_from_pixels."""

    def test_flat_pixels_become_rows_of_glyphs(self):
        """Pixels are read row-major into width-long rows."""
        mapping = {(0, 0, 0): '#', (255, 255, 255): '.'}
        pixels = [(0, 0, 0), (255, 255, 255), (255, 255, 255, 255), (0, 0, 0)]

        pixel_string = build_pixel_string_from_pixels(pixels, 2, 2, mapping, sorted(mapping))

        assert pixel_string == '#.\n.#'

    def test_unmapped_color_uses_the_closest_glyph(self):
        """A pixel color missing from the mapping takes its nearest color's glyph."""
        mapping = {(0, 0, 0): '#', (255, 255, 255): '.'}

        pixel_string = build_pixel_string_from_pixels(
            [(240, 240, 240), (10, 0, 0)],
            2,
            1,
            mapping,
            sorted(mapping),
            force_single_char_glyphs=True,
        )

        assert pixel_string == '.#'

    def test_missing_pixels_are_filled_with_the_transparent_glyph(self):
        """Positions beyond the pixel list are transparent."""
        mapping = {(0, 0, 0): '#'}

        pixel_string = build_pixel_string_from_pixels([(0, 0, 0)], 2, 2, mapping, sorted(mapping))

        assert pixel_string == f'#{TRANSPARENT_GLYPH}\n{TRANSPARENT_GLYPH * 2}'
