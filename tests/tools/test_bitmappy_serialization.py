"""Tests for bitmappy serialization: TOML parsing, color conversion, format detection."""

import logging
from typing import cast

import pytest

from glitchygames.bitmappy.ai_worker import _extract_example_size
from glitchygames.bitmappy.alpha import (
    _convert_animation_colors_to_rgba,
    _convert_colors_to_rgba,
    _detect_alpha_channel,
    _detect_alpha_channel_in_animation,
    convert_sprite_to_alpha_format,
)
from glitchygames.bitmappy.pixel_ops import (
    _build_ascii_grid,
    _build_color_to_glyph_map,
    _build_renderer_color_dict,
)
from glitchygames.bitmappy.toml_processing import (
    _fix_color_entry,
    _fix_color_format_in_toml_data,
    _fix_comma_separated_color_field,
    _normalize_animation_pixels,
    _normalize_escaped_newlines,
    _parse_toml_value,
    _parse_toml_with_regex,
    normalize_toml_data,
    parse_toml_robustly,
)
from glitchygames.bitmappy.utils import detect_file_format


class TestDetectFileFormat:
    """Test the detect_file_format utility function."""

    def test_detect_toml_format(self):
        """Test detection of .toml files."""
        assert detect_file_format('sprite.toml') == 'toml'

    def test_detect_toml_uppercase(self):
        """Test detection of .TOML files (case insensitive)."""
        assert detect_file_format('sprite.TOML') == 'toml'

    def test_detect_no_extension_defaults_to_toml(self):
        """Test that files with no extension default to toml."""
        assert detect_file_format('sprite') == 'toml'

    def test_detect_unsupported_format_raises(self):
        """Test that unsupported formats raise ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.yaml')

    def test_detect_json_raises(self):
        """Test that JSON format raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.json')

    def test_detect_ini_raises(self):
        """Test that INI format raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.ini')

    def test_detect_png_raises(self):
        """Test that PNG format raises ValueError."""
        with pytest.raises(ValueError, match='Unsupported file format'):
            detect_file_format('sprite.png')

    def test_detect_with_path_prefix(self):
        """Test detection with full path."""
        assert detect_file_format('/some/path/sprite.toml') == 'toml'


class TestDetectAlphaChannel:
    """Test the _detect_alpha_channel function."""

    def test_no_alpha_in_rgb_colors(self):
        """Test detection when colors are plain RGB."""
        colors = {
            '#': {'red': 0, 'green': 0, 'blue': 0},
            '.': {'red': 255, 'green': 255, 'blue': 255},
        }
        assert _detect_alpha_channel(colors) is False

    def test_alpha_key_present(self):
        """Test detection when alpha key is explicitly present."""
        colors = {
            '#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 128},
        }
        assert _detect_alpha_channel(colors) is True

    def test_short_alpha_key_present(self):
        """Test detection when short 'a' key is present."""
        colors = {
            '#': {'r': 0, 'g': 0, 'b': 0, 'a': 128},
        }
        assert _detect_alpha_channel(colors) is True

    def test_magenta_transparency_detected(self):
        """Test detection of magenta (255, 0, 255) as transparency."""
        colors = {
            '@': {'red': 255, 'green': 0, 'blue': 255},
        }
        assert _detect_alpha_channel(colors) is True

    def test_non_dict_color_data_ignored(self):
        """Test that non-dict color values are skipped."""
        colors = {
            '#': 'red',
            '.': 42,
        }
        assert _detect_alpha_channel(colors) is False

    def test_empty_colors(self):
        """Test with empty colors dictionary."""
        assert _detect_alpha_channel({}) is False

    def test_four_component_color_detected(self):
        """Test detection of RGBA (4-component) color definitions."""
        colors = {
            '#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 255},
        }
        assert _detect_alpha_channel(colors) is True

    def test_magenta_with_short_keys(self):
        """Test magenta detection using short key names."""
        colors = {
            '@': {'r': 255, 'g': 0, 'b': 255},
        }
        assert _detect_alpha_channel(colors) is True


class TestDetectAlphaChannelInAnimation:
    """Test _detect_alpha_channel_in_animation function."""

    def test_dict_animation_with_alpha(self):
        """Test alpha detection in dict-based animation data."""
        animation_data = {
            'walk': {
                'colors': {'#': {'red': 0, 'green': 0, 'blue': 0, 'alpha': 128}},
            },
        }
        assert _detect_alpha_channel_in_animation(animation_data) is True

    def test_dict_animation_without_alpha(self):
        """Test no alpha in dict-based animation data."""
        animation_data = {
            'walk': {
                'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
            },
        }
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_list_animation_with_alpha(self):
        """Test alpha detection in list-based animation data."""
        animation_data = [
            {'colors': {'#': {'red': 255, 'green': 0, 'blue': 255}}},
        ]
        assert _detect_alpha_channel_in_animation(animation_data) is True

    def test_list_animation_without_alpha(self):
        """Test no alpha in list-based animation data."""
        animation_data = [
            {'colors': {'#': {'red': 100, 'green': 100, 'blue': 100}}},
        ]
        assert _detect_alpha_channel_in_animation(animation_data) is False

    def test_empty_dict_animation(self):
        """Test with empty dict animation data."""
        assert _detect_alpha_channel_in_animation({}) is False

    def test_empty_list_animation(self):
        """Test with empty list animation data."""
        assert _detect_alpha_channel_in_animation([]) is False

    def test_animation_without_colors_key(self):
        """Test animation data without 'colors' key in frames."""
        animation_data = {
            'walk': {'pixels': '##\n##'},
        }
        assert _detect_alpha_channel_in_animation(animation_data) is False


class TestConvertColorsToRGBA:
    """Test _convert_colors_to_rgba function."""

    def test_rgb_to_rgba_opaque(self):
        """Test converting RGB colors to RGBA with default opaque alpha."""
        colors = {'#': {'red': 100, 'green': 150, 'blue': 200}}
        result = _convert_colors_to_rgba(colors)
        assert result['#'] == {'red': 100, 'green': 150, 'blue': 200, 'alpha': 255}

    def test_magenta_becomes_fully_transparent(self):
        """Test that magenta (255, 0, 255) gets alpha 0."""
        colors = {'@': {'red': 255, 'green': 0, 'blue': 255}}
        result = _convert_colors_to_rgba(colors)
        assert result['@']['alpha'] == 0

    def test_existing_alpha_preserved(self):
        """Test that existing alpha values are preserved."""
        colors = {'#': {'red': 100, 'green': 150, 'blue': 200, 'alpha': 128}}
        result = _convert_colors_to_rgba(colors)
        assert result['#']['alpha'] == 128

    def test_short_key_names(self):
        """Test conversion with short key names (r, g, b)."""
        colors = {'#': {'r': 50, 'g': 100, 'b': 150}}
        result = _convert_colors_to_rgba(colors)
        assert result['#'] == {'red': 50, 'green': 100, 'blue': 150, 'alpha': 255}

    def test_non_dict_color_data_passed_through(self):
        """Test that non-dict color values are passed through unchanged."""
        colors = {'#': 'some_string_value'}
        result = _convert_colors_to_rgba(colors)
        assert result['#'] == 'some_string_value'

    def test_empty_colors(self):
        """Test conversion of empty colors dictionary."""
        result = _convert_colors_to_rgba({})
        assert result == {}

    def test_multiple_colors_converted(self):
        """Test conversion of multiple color entries."""
        colors = {
            '#': {'red': 0, 'green': 0, 'blue': 0},
            '.': {'red': 255, 'green': 255, 'blue': 255},
            '@': {'red': 255, 'green': 0, 'blue': 255},
        }
        result = _convert_colors_to_rgba(colors)
        assert result['#']['alpha'] == 255
        assert result['.']['alpha'] == 255
        assert result['@']['alpha'] == 0


class TestConvertAnimationColorsToRGBA:
    """Test _convert_animation_colors_to_rgba function."""

    def test_convert_animation_frame_colors(self):
        """Test converting animation frame colors to RGBA."""
        animations = {
            'walk': {
                'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
                'pixels': '##',
            },
        }
        result = _convert_animation_colors_to_rgba(animations)
        assert result['walk']['colors']['#']['alpha'] == 255

    def test_frame_without_colors_passed_through(self):
        """Test frames without colors are passed through."""
        animations = {
            'idle': {'pixels': '..'},
        }
        result = _convert_animation_colors_to_rgba(animations)
        assert result['idle'] == {'pixels': '..'}

    def test_non_dict_frame_data_passed_through(self):
        """Test non-dict frame data is passed through."""
        animations = {
            'walk': 'some_string',
        }
        result = _convert_animation_colors_to_rgba(animations)
        assert result['walk'] == 'some_string'

    def test_empty_animations(self):
        """Test conversion of empty animations dict."""
        result = _convert_animation_colors_to_rgba({})
        assert result == {}


class TestConvertSpriteToAlphaFormat:
    """Test convert_sprite_to_alpha_format function."""

    def test_no_alpha_passes_through(self):
        """Test sprite data without alpha is passed through."""
        sprite_data = {
            'name': 'test',
            'has_alpha': False,
            'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
        }
        result = convert_sprite_to_alpha_format(sprite_data)
        assert result['colors'] == sprite_data['colors']

    def test_with_alpha_converts_colors(self):
        """Test sprite data with alpha converts colors to RGBA."""
        sprite_data = {
            'name': 'test',
            'has_alpha': True,
            'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
        }
        result = convert_sprite_to_alpha_format(sprite_data)
        assert result['colors']['#']['alpha'] == 255

    def test_with_alpha_converts_animations(self):
        """Test sprite data with alpha converts animation colors."""
        sprite_data = {
            'name': 'test',
            'has_alpha': True,
            'animations': {
                'walk': {'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}}},
            },
        }
        result = convert_sprite_to_alpha_format(sprite_data)
        assert result['animations']['walk']['colors']['#']['alpha'] == 255

    def test_original_data_not_mutated(self):
        """Test that original sprite data dictionary is not mutated."""
        sprite_data = {
            'name': 'test',
            'has_alpha': True,
            'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
        }
        original_colors = sprite_data['colors'].copy()
        convert_sprite_to_alpha_format(sprite_data)
        # The outer dict is copied, but the inner 'colors' may be modified
        # because the conversion replaces the 'colors' key entirely
        assert sprite_data['colors'] == original_colors


class TestParseTomlValue:
    """Test the _parse_toml_value function."""

    def test_parse_quoted_string(self):
        """Test parsing a quoted string value."""
        assert _parse_toml_value('"hello"') == 'hello'

    def test_parse_triple_quoted_string(self):
        """Test parsing a triple-quoted string value."""
        assert _parse_toml_value('"""content"""') == 'content'

    def test_parse_boolean_true(self):
        """Test parsing boolean true."""
        assert _parse_toml_value('true') is True

    def test_parse_boolean_false(self):
        """Test parsing boolean false."""
        assert _parse_toml_value('false') is False

    def test_parse_boolean_case_insensitive(self):
        """Test parsing boolean is case insensitive."""
        assert _parse_toml_value('True') is True
        assert _parse_toml_value('FALSE') is False

    def test_parse_integer(self):
        """Test parsing integer value."""
        assert _parse_toml_value('42') == 42

    def test_parse_negative_integer(self):
        """Test parsing negative integer value."""
        assert _parse_toml_value('-7') == -7

    def test_parse_float(self):
        """Test parsing float value."""
        assert _parse_toml_value('3.14') == pytest.approx(3.14)  # noqa: FURB152

    def test_parse_comma_separated_list(self):
        """Test parsing comma-separated values as list."""
        result = _parse_toml_value('1, 2, 3')
        assert result == [1, 2, 3]

    def test_parse_bare_string(self):
        """Test parsing bare string (no quotes, not number or bool)."""
        assert _parse_toml_value('some_value') == 'some_value'

    def test_parse_zero(self):
        """Test parsing zero."""
        assert _parse_toml_value('0') == 0

    def test_parse_whitespace_stripped(self):
        """Test that whitespace is stripped."""
        assert _parse_toml_value('  42  ') == 42


class TestParseTomlWithRegex:
    """Test _parse_toml_with_regex fallback parser."""

    def test_parse_simple_section(self):
        """Test parsing a simple section with key-value pairs."""
        content = '[sprite]\nname = "test"\n'
        log = logging.getLogger('test')
        result = _parse_toml_with_regex(content, log)
        assert 'sprite' in result
        assert result['sprite']['name'] == 'test'

    def test_parse_numeric_values(self):
        """Test parsing numeric values in sections."""
        content = '[colors]\nred = 255\ngreen = 0\nblue = 128\n'
        log = logging.getLogger('test')
        result = _parse_toml_with_regex(content, log)
        assert result['colors']['red'] == 255
        assert result['colors']['green'] == 0
        assert result['colors']['blue'] == 128

    def test_skip_comments(self):
        """Test that comments are skipped."""
        content = '# This is a comment\n[sprite]\nname = "test"\n'
        log = logging.getLogger('test')
        result = _parse_toml_with_regex(content, log)
        assert result['sprite']['name'] == 'test'

    def test_skip_empty_lines(self):
        """Test that empty lines are skipped."""
        content = '\n\n[sprite]\n\nname = "test"\n\n'
        log = logging.getLogger('test')
        result = _parse_toml_with_regex(content, log)
        assert result['sprite']['name'] == 'test'

    def test_key_value_without_section(self):
        """Test key-value pairs without a section header."""
        content = 'name = "global"\nvalue = 42\n'
        log = logging.getLogger('test')
        result = _parse_toml_with_regex(content, log)
        assert result['name'] == 'global'
        assert result['value'] == 42


class TestParseTomlRobustly:
    """Test the parse_toml_robustly function."""

    def test_parse_valid_toml(self):
        """Test parsing valid TOML content."""
        content = '[sprite]\nname = "test"\n\n[colors."#"]\nred = 0\ngreen = 0\nblue = 0\n'
        result = parse_toml_robustly(content)
        assert result['sprite']['name'] == 'test'
        assert result['colors']['#']['red'] == 0

    def test_parse_with_explicit_logger(self):
        """Test parsing with an explicitly provided logger."""
        content = '[sprite]\nname = "test"\n'
        log = logging.getLogger('test_parser')
        result = parse_toml_robustly(content, log=log)
        assert result['sprite']['name'] == 'test'

    def test_parse_fixes_comma_separated_colors(self):
        """Test that comma-separated color values are fixed."""
        content = '[sprite]\nname = "test"\n\n[colors."#"]\nred = "255, 128, 64"\n'
        result = parse_toml_robustly(content)
        # The fix should split comma-separated values
        assert result['colors']['#']['red'] == 255
        assert result['colors']['#']['green'] == 128
        assert result['colors']['#']['blue'] == 64


class TestNormalizeEscapedNewlines:
    """Test _normalize_escaped_newlines function."""

    def test_single_escaped_newline(self):
        """Test converting single escaped newlines."""
        assert _normalize_escaped_newlines('line1\\nline2') == 'line1\nline2'

    def test_double_escaped_newline(self):
        """Test converting double escaped newlines."""
        assert _normalize_escaped_newlines('line1\\\\nline2') == 'line1\nline2'

    def test_no_escaped_newlines(self):
        """Test string without escaped newlines."""
        assert _normalize_escaped_newlines('hello world') == 'hello world'

    def test_multiple_escaped_newlines(self):
        """Test string with multiple escaped newlines."""
        result = _normalize_escaped_newlines('a\\nb\\nc')
        assert result == 'a\nb\nc'

    def test_empty_string(self):
        """Test empty string."""
        assert not _normalize_escaped_newlines('')


class TestNormalizeAnimationPixels:
    """Test _normalize_animation_pixels function."""

    def test_normalize_frame_pixels(self):
        """Test normalizing pixel strings in animation frames."""
        animation_list = [
            {
                'frame': [
                    {'pixels': 'row1\\nrow2'},
                ],
            },
        ]
        _normalize_animation_pixels(animation_list)
        assert animation_list[0]['frame'][0]['pixels'] == 'row1\nrow2'

    def test_skip_non_dict_animations(self):
        """Test that non-dict items in animation list are skipped."""
        animation_list = ['not_a_dict']
        _normalize_animation_pixels(animation_list)
        assert animation_list[0] == 'not_a_dict'

    def test_skip_animations_without_frame_key(self):
        """Test that animations without 'frame' key are skipped."""
        animation_list = [{'namespace': 'walk'}]
        _normalize_animation_pixels(animation_list)
        assert animation_list[0] == {'namespace': 'walk'}

    def test_skip_non_string_pixels(self):
        """Test that non-string pixel values are not normalized."""
        animation_list = [
            {'frame': [{'pixels': 42}]},
        ]
        _normalize_animation_pixels(animation_list)
        assert animation_list[0]['frame'][0]['pixels'] == 42

    def test_empty_animation_list(self):
        """Test with empty animation list."""
        animation_list = []
        _normalize_animation_pixels(animation_list)
        assert animation_list == []


class TestNormalizeTomlData:
    """Test normalize_toml_data function."""

    def test_normalize_sprite_pixels(self):
        """Test normalizing sprite pixel strings."""
        config_data = {
            'sprite': {'pixels': 'row1\\nrow2'},
        }
        result = normalize_toml_data(config_data)
        assert result['sprite']['pixels'] == 'row1\nrow2'

    def test_normalize_animation_pixels(self):
        """Test normalizing animation frame pixel strings."""
        config_data = {
            'animation': [
                {'frame': [{'pixels': 'a\\nb'}]},
            ],
        }
        result = normalize_toml_data(config_data)
        assert result['animation'][0]['frame'][0]['pixels'] == 'a\nb'

    def test_no_sprite_section(self):
        """Test with data that has no sprite section."""
        config_data = {'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}}}
        result = normalize_toml_data(config_data)
        assert 'sprite' not in result

    def test_non_string_pixels_unchanged(self):
        """Test that non-string pixel values are unchanged."""
        config_data = {
            'sprite': {'pixels': 42, 'name': 'test'},
        }
        result = normalize_toml_data(config_data)
        assert result['sprite']['pixels'] == 42

    def test_error_returns_original_data(self):
        """Test that errors return original data unchanged."""
        config_data = None
        result = normalize_toml_data(config_data)  # type: ignore[invalid-argument-type]
        assert result is None


class TestFixCommaSeparatedColorField:
    """Test _fix_comma_separated_color_field function."""

    def test_fix_red_with_three_values(self):
        """Test parsing comma-separated RGB from red field."""
        fixed_color = {}
        log = logging.getLogger('test')
        _fix_comma_separated_color_field('red', '255, 128, 64', fixed_color, '#', log)
        assert fixed_color['red'] == 255
        assert fixed_color['green'] == 128
        assert fixed_color['blue'] == 64

    def test_fix_red_with_two_values(self):
        """Test parsing two comma-separated values from red field."""
        fixed_color = {}
        log = logging.getLogger('test')
        _fix_comma_separated_color_field('red', '200, 100', fixed_color, '#', log)
        assert fixed_color['red'] == 200
        assert fixed_color['green'] == 100
        assert 'blue' not in fixed_color

    def test_fix_red_with_single_value(self):
        """Test parsing single comma-separated value from red field."""
        fixed_color = {}
        log = logging.getLogger('test')
        _fix_comma_separated_color_field('red', '200', fixed_color, '#', log)
        assert fixed_color['red'] == 200

    def test_fix_green_field(self):
        """Test parsing comma-separated green field."""
        fixed_color = {}
        log = logging.getLogger('test')
        _fix_comma_separated_color_field('green', '128', fixed_color, '.', log)
        assert fixed_color['green'] == 128

    def test_fix_blue_field(self):
        """Test parsing comma-separated blue field."""
        fixed_color = {}
        log = logging.getLogger('test')
        _fix_comma_separated_color_field('blue', '64', fixed_color, '.', log)
        assert fixed_color['blue'] == 64

    def test_invalid_value_stored_as_is(self):
        """Test that unparseable values are stored as-is."""
        fixed_color = {}
        log = logging.getLogger('test')
        _fix_comma_separated_color_field('red', 'not_a_number', fixed_color, '#', log)
        assert fixed_color['red'] == 'not_a_number'


class TestFixColorEntry:
    """Test _fix_color_entry function."""

    def test_fix_comma_separated_entry(self):
        """Test fixing a color entry with comma-separated values."""
        color_data = {'red': '255, 128, 64'}
        log = logging.getLogger('test')
        result = _fix_color_entry(color_data, '#', log)
        assert result['red'] == 255
        assert result['green'] == 128
        assert result['blue'] == 64

    def test_normal_entry_unchanged(self):
        """Test that normal integer values pass through."""
        color_data = {'red': 100, 'green': 150, 'blue': 200}
        log = logging.getLogger('test')
        result = _fix_color_entry(color_data, '#', log)
        assert result == {'red': 100, 'green': 150, 'blue': 200}

    def test_partial_fields(self):
        """Test entry with only some color fields."""
        color_data = {'red': 100}
        log = logging.getLogger('test')
        result = _fix_color_entry(color_data, '#', log)
        assert result == {'red': 100}

    def test_empty_entry(self):
        """Test fixing an empty color entry."""
        color_data = {}
        log = logging.getLogger('test')
        result = _fix_color_entry(color_data, '#', log)
        assert result == {}


class TestFixColorFormatInTomlData:
    """Test _fix_color_format_in_toml_data function."""

    def test_no_colors_section(self):
        """Test data without colors section passes through."""
        data = {'sprite': {'name': 'test'}}
        log = logging.getLogger('test')
        result = _fix_color_format_in_toml_data(data, log)
        assert result == data

    def test_fix_comma_separated_colors(self):
        """Test fixing comma-separated color values."""
        data = {
            'colors': {
                '#': {'red': '255, 128, 64'},
            },
        }
        log = logging.getLogger('test')
        result = _fix_color_format_in_toml_data(data, log)
        assert result['colors']['#']['red'] == 255
        assert result['colors']['#']['green'] == 128
        assert result['colors']['#']['blue'] == 64

    def test_non_dict_color_data_passed_through(self):
        """Test non-dict color data is passed through."""
        data = {
            'colors': {
                '#': 'some_value',
            },
        }
        log = logging.getLogger('test')
        result = _fix_color_format_in_toml_data(data, log)
        assert result['colors']['#'] == 'some_value'


class TestExtractExampleSize:
    """Test _extract_example_size function."""

    def test_extract_from_pixels_field(self):
        """Test extracting size from a pixels string."""
        example = {'pixels': '##\n##'}
        result = _extract_example_size(example)
        assert result == (2, 2)

    def test_extract_from_larger_pixels(self):
        """Test extracting size from larger pixel grid."""
        example = {'pixels': '####\n####\n####'}
        result = _extract_example_size(example)
        assert result == (4, 3)

    def test_no_pixels_or_animations(self):
        """Test when neither pixels nor animations are present."""
        example = {'name': 'test'}
        result = _extract_example_size(example)
        assert result is None

    def test_single_line_pixels_no_newline(self):
        """Test pixels without newlines returns None."""
        example = {'pixels': '####'}
        result = _extract_example_size(example)
        assert result is None

    def test_non_string_pixels(self):
        """Test non-string pixels field returns None."""
        example = {'pixels': 42}
        result = _extract_example_size(example)
        assert result is None

    def test_extract_from_animation_frames(self):
        """Test extracting size from animation frame data."""
        example = {
            'animations': [
                {
                    'frame': [
                        {'pixels': '###\n###\n###\n###'},
                    ],
                },
            ],
        }
        result = _extract_example_size(example)
        assert result == (3, 4)

    def test_empty_pixels_string(self):
        """Test with empty pixels string."""
        example = {'pixels': '\n'}
        result = _extract_example_size(example)
        # Strip produces empty string, split gives [''], height=1, width=0
        assert result == (0, 1)


class TestBuildColorToGlyphMap:
    """Test _build_color_to_glyph_map function."""

    def test_single_color(self):
        """Test mapping a single color to a glyph."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (255, 0, 0)])
        result = _build_color_to_glyph_map(pixels)
        assert len(result) == 1
        assert (255, 0, 0) in result

    def test_multiple_colors(self):
        """Test mapping multiple distinct colors."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        result = _build_color_to_glyph_map(pixels)
        assert len(result) == 3

    def test_rgba_pixels_mapped_by_rgb(self):
        """Test that RGBA pixels are mapped by their RGB components."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 128), (255, 0, 0, 255)])
        result = _build_color_to_glyph_map(pixels)
        # Both share the same RGB, so only 1 entry
        assert len(result) == 1
        assert (255, 0, 0) in result

    def test_empty_pixel_list(self):
        """Test with empty pixel list."""
        result = _build_color_to_glyph_map([])
        assert result == {}

    def test_glyphs_are_unique(self):
        """Test that different colors get different glyphs."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        result = _build_color_to_glyph_map(pixels)
        glyphs = list(result.values())
        assert len(set(glyphs)) == len(glyphs)


class TestBuildAsciiGrid:
    """Test _build_ascii_grid function."""

    def test_simple_grid(self):
        """Test building a simple 2x2 ASCII grid."""
        pixels = cast(
            'list[tuple[int, ...]]',
            [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)],
        )
        color_map = cast(
            'dict[tuple[int, ...], str]',
            {
                (255, 0, 0): '#',
                (0, 255, 0): '.',
                (0, 0, 255): '@',
                (255, 255, 0): '*',
            },
        )
        result = _build_ascii_grid(pixels, 2, 2, color_map)
        assert result == '#.\n@*'

    def test_single_pixel(self):
        """Test building a 1x1 grid."""
        pixels = cast('list[tuple[int, ...]]', [(0, 0, 0)])
        color_map = cast('dict[tuple[int, ...], str]', {(0, 0, 0): '#'})
        result = _build_ascii_grid(pixels, 1, 1, color_map)
        assert result == '#'

    def test_rgba_pixels_use_rgb_key(self):
        """Test that RGBA pixels use their RGB portion as key."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0, 128)])
        color_map = cast('dict[tuple[int, ...], str]', {(255, 0, 0): 'R'})
        result = _build_ascii_grid(pixels, 1, 1, color_map)
        assert result == 'R'

    def test_unmapped_color_uses_space(self):
        """Test that unmapped colors produce a space character."""
        pixels = cast('list[tuple[int, ...]]', [(99, 99, 99)])
        color_map = cast('dict[tuple[int, ...], str]', {(0, 0, 0): '#'})
        result = _build_ascii_grid(pixels, 1, 1, color_map)
        assert result == ' '

    def test_empty_pixels(self):
        """Test with empty pixel list and zero dimensions."""
        result = _build_ascii_grid([], 0, 0, {})
        assert not result


class TestBuildRendererColorDict:
    """Test _build_renderer_color_dict function."""

    def test_rgb_pixels_get_alpha_255(self):
        """Test that RGB pixels default to alpha 255."""
        pixels = cast('list[tuple[int, ...]]', [(100, 150, 200)])
        color_map = cast('dict[tuple[int, ...], str]', {(100, 150, 200): '#'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['#'] == (100, 150, 200, 255)

    def test_rgba_pixels_preserve_alpha(self):
        """Test that RGBA pixels preserve their alpha value."""
        pixels = cast('list[tuple[int, ...]]', [(100, 150, 200, 128)])
        color_map = cast('dict[tuple[int, ...], str]', {(100, 150, 200): '#'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['#'] == (100, 150, 200, 128)

    def test_magenta_becomes_white(self):
        """Test that magenta (255, 0, 255) renders as white blocks."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 255)])
        color_map = cast('dict[tuple[int, ...], str]', {(255, 0, 255): '@'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['@'] == (255, 255, 255, 255)

    def test_empty_inputs(self):
        """Test with empty inputs."""
        result = _build_renderer_color_dict([], {})
        assert result == {}

    def test_multiple_colors(self):
        """Test building dict for multiple colors."""
        pixels = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0)])
        color_map = cast('dict[tuple[int, ...], str]', {(255, 0, 0): 'R', (0, 255, 0): 'G'})
        result = _build_renderer_color_dict(pixels, color_map)
        assert result['R'] == (255, 0, 0, 255)
        assert result['G'] == (0, 255, 0, 255)
