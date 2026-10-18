"""Tests for robust TOML parsing functionality."""

from unittest.mock import Mock

import pytest

from glitchygames.bitmappy.toml_processing import (
    _fix_color_format_in_toml_data,
    _parse_toml_permissively,
    _parse_toml_value,
    _parse_toml_with_regex,
    parse_toml_robustly,
)


class TestRobustTomlParser:
    """Test robust TOML parsing with duplicate key handling."""

    def test_parse_valid_toml(self):
        """Test parsing valid TOML content."""
        content = """
[sprite]
name = "test_sprite"
pixels = \"\"\"
.#.
#.#
.#.
\"\"\"

[colors."."]
red = 0
green = 0
blue = 0

[colors."#"]
red = 255
green = 255
blue = 255
"""
        result = parse_toml_robustly(content)

        assert 'sprite' in result
        assert 'colors' in result
        assert result['sprite']['name'] == 'test_sprite'
        assert result['colors']['.']['red'] == 0
        assert result['colors']['#']['red'] == 255

    def test_parse_toml_with_duplicate_keys(self):
        """Test parsing TOML with duplicate keys (last value wins)."""
        content = """
[sprite]
name = "first_name"
name = "second_name"

[colors."."]
red = 100
red = 200
green = 50
"""
        mock_log = Mock()
        result = parse_toml_robustly(content, mock_log)

        # Should use the last value for duplicate keys
        assert result['sprite']['name'] == 'second_name'
        assert result['colors']['.']['red'] == 200
        assert result['colors']['.']['green'] == 50

        # Should log warnings about duplicates
        assert mock_log.warning.called

    def test_parse_toml_with_duplicate_color_definitions(self):
        """Test parsing TOML with duplicate color character definitions."""
        content = """
[sprite]
name = "test"

[colors]
"." = {red = 0, green = 0, blue = 0}
"." = {red = 255, green = 255, blue = 255}
"#" = {red = 128, green = 128, blue = 128}
"""
        mock_log = Mock()
        result = parse_toml_robustly(content, mock_log)

        # Should use the last definition for duplicate "."
        assert result['colors']['.']['red'] == 255
        assert result['colors']['.']['green'] == 255
        assert result['colors']['.']['blue'] == 255
        assert result['colors']['#']['red'] == 128

    def test_parse_toml_with_malformed_content(self):
        """Test parsing severely malformed TOML content."""
        content = """
[sprite
name = "test"
pixels = \"\"\"
.#
#.
\"\"\"

[colors."."]
red = 0
green = 0
blue = 0
"""
        mock_log = Mock()
        result = parse_toml_robustly(content, mock_log)

        # Should still parse despite malformed section header
        assert 'sprite' in result
        assert 'colors' in result
        assert result['sprite']['name'] == 'test'

    def test_parse_toml_with_comments_and_whitespace(self):
        """Test parsing TOML with comments and extra whitespace."""
        content = """
# This is a comment
[sprite]
    name = "test_sprite"  # Another comment
    pixels = \"\"\"
    .#.
    #.#
    .#.
    \"\"\"

[colors."."]
    red = 0
    green = 0
    blue = 0
"""
        result = parse_toml_robustly(content)

        assert result['sprite']['name'] == 'test_sprite'
        assert result['colors']['.']['red'] == 0


class TestColorFormatFixing:
    """Test color format fixing functionality."""

    def test_fix_comma_separated_colors(self):
        """Test fixing comma-separated color values."""
        data = {
            'colors': {
                '.': {'red': '255, 0, 0', 'green': '0, 255, 0', 'blue': '0, 0, 255'},
                '#': {'red': 128, 'green': 64, 'blue': 32},
            }
        }

        mock_log = Mock()
        result = _fix_color_format_in_toml_data(data, mock_log)

        # Should fix comma-separated values
        assert result['colors']['.']['red'] == 255
        assert result['colors']['.']['green'] == 0
        assert result['colors']['.']['blue'] == 0

        # Should preserve already correct values
        assert result['colors']['#']['red'] == 128
        assert result['colors']['#']['green'] == 64
        assert result['colors']['#']['blue'] == 32

        # Should log warnings about fixes
        assert mock_log.warning.called

    def test_fix_partial_comma_separated_colors(self):
        """Test fixing partially comma-separated color values."""
        data = {
            'colors': {
                '.': {
                    'red': '255, 0, 0',  # Comma-separated
                    'green': 0,  # Already correct
                    'blue': 0,  # Already correct
                }
            }
        }

        mock_log = Mock()
        result = _fix_color_format_in_toml_data(data, mock_log)

        # Should fix the comma-separated red value
        assert result['colors']['.']['red'] == 255
        assert result['colors']['.']['green'] == 0
        assert result['colors']['.']['blue'] == 0

    def test_fix_invalid_comma_separated_colors(self):
        """Test handling invalid comma-separated color values."""
        data = {'colors': {'.': {'red': 'invalid, values, here', 'green': 0, 'blue': 0}}}

        mock_log = Mock()
        result = _fix_color_format_in_toml_data(data, mock_log)

        # Should keep original invalid value and log warning
        assert result['colors']['.']['red'] == 'invalid, values, here'
        assert mock_log.warning.called

    def test_fix_colors_with_no_colors_section(self):
        """Test fixing colors when no colors section exists."""
        data = {'sprite': {'name': 'test'}}

        mock_log = Mock()
        result = _fix_color_format_in_toml_data(data, mock_log)

        # Should return data unchanged
        assert result == data

    def test_fix_colors_with_non_dict_color_data(self):
        """Test fixing colors when color data is not a dictionary."""
        data = {'colors': {'.': 'some_string_value', '#': 123}}

        mock_log = Mock()
        result = _fix_color_format_in_toml_data(data, mock_log)

        # Should preserve non-dict values
        assert result['colors']['.'] == 'some_string_value'
        assert result['colors']['#'] == 123


class TestTomlValueParsing:
    """Test TOML value parsing functionality."""

    def test_parse_quoted_strings(self):
        """Test parsing quoted string values."""
        assert _parse_toml_value('"hello world"') == 'hello world'
        assert _parse_toml_value('"123"') == '123'

    def test_parse_triple_quoted_strings(self):
        """Test parsing triple-quoted string values."""
        assert _parse_toml_value('"""multiline\nstring"""') == 'multiline\nstring'

    def test_parse_boolean_values(self):
        """Test parsing boolean values."""
        assert _parse_toml_value('true') is True
        assert _parse_toml_value('false') is False
        assert _parse_toml_value('TRUE') is True
        assert _parse_toml_value('FALSE') is False

    def test_parse_numeric_values(self):
        """Test parsing numeric values."""
        assert _parse_toml_value('123') == 123
        assert _parse_toml_value('123.45') == 123.45
        assert _parse_toml_value('-123') == -123
        assert _parse_toml_value('-123.45') == -123.45

    def test_parse_array_values(self):
        """Test parsing comma-separated array values."""
        result = _parse_toml_value('1, 2, 3')
        assert result == [1, 2, 3]

        result = _parse_toml_value('red, green, blue')
        assert result == ['red', 'green', 'blue']

        result = _parse_toml_value('1.5, 2.5, 3.5')
        assert result == [1.5, 2.5, 3.5]

    def test_parse_string_fallback(self):
        """Test parsing falls back to string for unrecognized values."""
        assert _parse_toml_value('hello') == 'hello'
        assert _parse_toml_value('unknown_value') == 'unknown_value'


class TestPermissiveParsing:
    """Test permissive TOML parsing functionality."""

    def test_parse_permissively_with_duplicates(self):
        """Test permissive parsing handles duplicate keys."""
        content = """
[sprite]
name = "first"
name = "second"

[colors."."]
red = 100
red = 200
"""
        mock_log = Mock()
        result = _parse_toml_permissively(content, mock_log)

        # Should handle duplicates by keeping last value
        assert result['sprite']['name'] == 'second'
        assert result['colors']['.']['red'] == 200

    def test_parse_permissively_with_comments(self):
        """Test permissive parsing handles comments."""
        content = """
# Comment at start
[sprite]
name = "test"  # Inline comment
# Another comment
pixels = \"\"\"
.#.
#.#
\"\"\"
"""
        mock_log = Mock()
        result = _parse_toml_permissively(content, mock_log)

        assert result['sprite']['name'] == 'test'
        assert '.#.' in result['sprite']['pixels']

    def test_parse_permissively_fallback_to_regex(self):
        """Test permissive parsing falls back to regex parsing."""
        content = """
[sprite
name = "test"
pixels = \"\"\"
.#
#.
\"\"\"
"""
        mock_log = Mock()
        result = _parse_toml_permissively(content, mock_log)

        # Should fall back to regex parsing for malformed content
        assert 'sprite' in result
        assert result['sprite']['name'] == 'test'


class TestRegexParsing:
    """Test regex-based TOML parsing functionality."""

    def test_parse_with_regex_basic(self):
        """Test basic regex parsing functionality."""
        content = """
[sprite]
name = "test"
pixels = \"\"\"
.#.
#.#
\"\"\"

[colors."."]
red = 0
green = 0
blue = 0
"""
        mock_log = Mock()
        result = _parse_toml_with_regex(content, mock_log)

        assert result['sprite']['name'] == 'test'
        assert result['colors']['.']['red'] == 0

    def test_parse_with_regex_malformed_sections(self):
        """Test regex parsing handles malformed section headers."""
        content = """
[sprite
name = "test"
pixels = \"\"\"
.#
#.
\"\"\"

[colors."."]
red = 0
green = 0
blue = 0
"""
        mock_log = Mock()
        result = _parse_toml_with_regex(content, mock_log)

        # Should still parse despite malformed section
        assert 'sprite' in result
        assert result['sprite']['name'] == 'test'

    def test_parse_with_regex_quoted_keys(self):
        """Test regex parsing handles quoted keys."""
        content = """
[colors."."]
red = 0
green = 0
blue = 0

[colors."#"]
red = 255
green = 255
blue = 255
"""
        mock_log = Mock()
        result = _parse_toml_with_regex(content, mock_log)

        assert result['colors']['.']['red'] == 0
        assert result['colors']['#']['red'] == 255

    def test_parse_with_regex_ignores_comments(self):
        """Test regex parsing ignores comments."""
        content = """
# This is a comment
[sprite]
name = "test"  # Inline comment
# Another comment
pixels = \"\"\"
.#.
#.#
\"\"\"
"""
        mock_log = Mock()
        result = _parse_toml_with_regex(content, mock_log)

        assert result['sprite']['name'] == 'test'
        assert '.#.' in result['sprite']['pixels']

    def test_parse_with_regex_handles_errors(self):
        """Test regex parsing handles parsing errors gracefully."""
        content = """
[sprite]
name = "test"
invalid_line_without_equals
pixels = \"\"\"
.#.
#.#
\"\"\"
"""
        mock_log = Mock()
        result = _parse_toml_with_regex(content, mock_log)

        # Should parse valid lines and log errors for invalid ones
        assert result['sprite']['name'] == 'test'
        assert mock_log.warning.called


class TestIntegration:
    """Test integration of robust TOML parsing with real-world scenarios."""

    def test_ai_generated_sprite_with_duplicates_and_bad_colors(self):
        """Test parsing AI-generated sprite with both duplicate keys and bad color format."""
        content = """
[sprite]
name = "red_hat"
pixels = \"\"\"
    .@@@.
   @@@@@
  @      @
  @      @
   @@@@@
  @     @
\"\"\"

[colors."."]
red = 255, 0, 0
black = 0, 0, 0

[colors."@"]
red = 255, 0, 0
red = 128, 0, 0
green = 0, 255, 0
blue = 0, 0, 255
"""
        mock_log = Mock()
        result = parse_toml_robustly(content, mock_log)

        # Should fix color format
        assert result['colors']['.']['red'] == 255
        assert result['colors']['.']['green'] == 0
        assert result['colors']['.']['blue'] == 0

        # Should handle duplicate keys (last value wins)
        assert result['colors']['@']['red'] == 128
        assert result['colors']['@']['green'] == 0
        assert result['colors']['@']['blue'] == 0

        # Should log warnings about fixes
        assert mock_log.warning.called

    def test_complex_animated_sprite(self):
        """Test parsing complex animated sprite with various issues."""
        content = """
[sprite]
name = "animated_test"

[[animation]]
namespace = "walk"
frame_interval = 100
loop = true

[[animation.frame]]
namespace = "walk"
frame_index = 0
pixels = \"\"\"
.#.
#.#
.#.
\"\"\"

[[animation.frame]]
namespace = "walk"
frame_index = 1
pixels = \"\"\"
#.#
.#.
#.#
\"\"\"

[colors."."]
red = 0, 0, 0
green = 0, 0, 0
blue = 0, 0, 0

[colors."#"]
red = 255, 255, 255
green = 255, 255, 255
blue = 255, 255, 255
"""
        mock_log = Mock()
        result = parse_toml_robustly(content, mock_log)

        # Should parse animation structure
        assert len(result['animation']) == 1
        assert result['animation'][0]['namespace'] == 'walk'
        assert len(result['animation'][0]['frame']) == 2

        # Should fix color format
        assert result['colors']['.']['red'] == 0
        assert result['colors']['#']['red'] == 255

        # Should log warnings about fixes
        assert mock_log.warning.called

    def test_edge_case_empty_content(self):
        """Test parsing empty content."""
        result = parse_toml_robustly('')
        assert result == {}

    def test_edge_case_whitespace_only(self):
        """Test parsing whitespace-only content."""
        result = parse_toml_robustly('   \n  \t  \n  ')
        assert result == {}

    def test_edge_case_comments_only(self):
        """Test parsing comments-only content."""
        content = """
# This is a comment
# Another comment
# Yet another comment
"""
        result = parse_toml_robustly(content)
        assert result == {}


if __name__ == '__main__':
    pytest.main([__file__])
