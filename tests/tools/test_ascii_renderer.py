"""Tests for ascii_renderer module - ASCII rendering of BitmappySprite data."""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools.ascii_renderer import ASCIIRenderer


@pytest.fixture
def renderer_with_color(mocker):
    """Create an ASCIIRenderer with color support mocked as enabled.

    Returns:
        ASCIIRenderer: Renderer configured with true color support.

    """
    renderer = ASCIIRenderer()
    mocker.patch.object(renderer.detector, 'has_color_support', return_value=True)
    mocker.patch.object(renderer.color_mapper.detector, 'has_color_support', return_value=True)
    # Default to true color for predictable escape codes
    renderer.color_mapper._capability = 'true_color'
    return renderer


@pytest.fixture
def renderer_without_color(mocker):
    """Create an ASCIIRenderer with color support mocked as disabled.

    Returns:
        ASCIIRenderer: Renderer configured without color support.

    """
    renderer = ASCIIRenderer()
    mocker.patch.object(renderer.detector, 'has_color_support', return_value=False)
    mocker.patch.object(renderer.color_mapper.detector, 'has_color_support', return_value=False)
    return renderer


class TestExtractColorsFromTOML:
    """Test ASCIIRenderer._extract_colors_from_toml method."""

    def test_extract_basic_rgb_colors(self):
        """Test extraction of basic RGB color mappings."""
        renderer = ASCIIRenderer()
        toml_data = {
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0},
                '@': {'red': 0, 'green': 255, 'blue': 0},
            }
        }
        colors = renderer._extract_colors_from_toml(toml_data)
        assert colors['#'] == (255, 0, 0, 255)
        assert colors['@'] == (0, 255, 0, 255)

    def test_extract_magenta_transparency(self):
        """Test that magenta (255, 0, 255) is detected as fully transparent."""
        renderer = ASCIIRenderer()
        toml_data = {
            'colors': {
                '.': {'red': 255, 'green': 0, 'blue': 255},
            }
        }
        colors = renderer._extract_colors_from_toml(toml_data)
        assert colors['.'] == (255, 0, 255, 0)

    def test_extract_explicit_alpha(self):
        """Test extraction of explicit alpha channel value."""
        renderer = ASCIIRenderer()
        toml_data = {
            'colors': {
                '#': {'red': 100, 'green': 100, 'blue': 100, 'alpha': 127},
            }
        }
        colors = renderer._extract_colors_from_toml(toml_data)
        assert colors['#'] == (100, 100, 100, 127)

    def test_extract_alpha_via_a_key(self):
        """Test extraction of alpha via shorthand 'a' key."""
        renderer = ASCIIRenderer()
        toml_data = {
            'colors': {
                '#': {'red': 50, 'green': 50, 'blue': 50, 'a': 64},
            }
        }
        colors = renderer._extract_colors_from_toml(toml_data)
        assert colors['#'] == (50, 50, 50, 64)

    def test_extract_no_colors_section(self):
        """Test extraction with no colors section returns empty dict."""
        renderer = ASCIIRenderer()
        toml_data = {'sprite': {'name': 'test'}}
        colors = renderer._extract_colors_from_toml(toml_data)
        assert colors == {}

    def test_extract_skips_invalid_color_entries(self):
        """Test that entries missing required RGB keys are skipped."""
        renderer = ASCIIRenderer()
        toml_data = {
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0},
                '@': {'red': 100},  # Missing green and blue
                '%': 'not_a_dict',  # Not a dict at all
            }
        }
        colors = renderer._extract_colors_from_toml(toml_data)
        assert '#' in colors
        assert '@' not in colors
        assert '%' not in colors

    def test_extract_default_alpha_is_opaque(self):
        """Test that default alpha is 255 (opaque) when not specified."""
        renderer = ASCIIRenderer()
        toml_data = {
            'colors': {
                '#': {'red': 0, 'green': 0, 'blue': 0},
            }
        }
        colors = renderer._extract_colors_from_toml(toml_data)
        assert colors['#'][3] == 255


class TestExtractPixelsFromTOML:
    """Test ASCIIRenderer._extract_pixels_from_toml method."""

    def test_extract_static_sprite_pixels(self):
        """Test extraction of pixels from a static sprite."""
        renderer = ASCIIRenderer()
        toml_data = {
            'sprite': {'name': 'test', 'pixels': '##\n##'},
        }
        pixels = renderer._extract_pixels_from_toml(toml_data)
        assert pixels == '##\n##'

    def test_extract_animated_sprite_first_frame(self):
        """Test extraction of pixels from the first frame of an animated sprite."""
        renderer = ASCIIRenderer()
        toml_data = {
            'animation': [
                {
                    'namespace': 'walk',
                    'frame': [
                        {'pixels': 'AB\nCD'},
                        {'pixels': 'EF\nGH'},
                    ],
                }
            ]
        }
        pixels = renderer._extract_pixels_from_toml(toml_data)
        assert pixels == 'AB\nCD'

    def test_extract_returns_none_when_no_pixels(self):
        """Test that None is returned when no pixels data exists."""
        renderer = ASCIIRenderer()
        toml_data = {'sprite': {'name': 'test'}}
        pixels = renderer._extract_pixels_from_toml(toml_data)
        assert pixels is None

    def test_extract_returns_none_for_empty_data(self):
        """Test that None is returned for completely empty data."""
        renderer = ASCIIRenderer()
        pixels = renderer._extract_pixels_from_toml({})
        assert pixels is None

    def test_extract_returns_none_for_empty_animation(self):
        """Test that None is returned when animation list is empty."""
        renderer = ASCIIRenderer()
        toml_data = {'animation': []}
        pixels = renderer._extract_pixels_from_toml(toml_data)
        assert pixels is None

    def test_extract_returns_none_for_animation_no_frames(self):
        """Test that None is returned when animation has no frames."""
        renderer = ASCIIRenderer()
        toml_data = {'animation': [{'namespace': 'walk', 'frame': []}]}
        pixels = renderer._extract_pixels_from_toml(toml_data)
        assert pixels is None


class TestColorizePixels:
    """Test ASCIIRenderer._colorize_pixels method."""

    def test_colorize_returns_raw_pixels_without_color_support(self, renderer_without_color):
        """Test that pixels are returned unmodified without color support."""
        pixels = '##\n##'
        colors = {'#': (255, 0, 0, 255)}
        result = renderer_without_color._colorize_pixels(pixels, colors)
        assert result == pixels

    def test_colorize_opaque_pixels(self, renderer_with_color):
        """Test colorization of fully opaque pixels."""
        pixels = '#'
        colors = {'#': (255, 0, 0, 255)}
        result = renderer_with_color._colorize_pixels(pixels, colors)
        # Should contain color code, block char, and reset code
        assert '\033[38;2;255;0;0m' in result
        assert '\033[0m' in result

    def test_colorize_transparent_pixels(self, renderer_with_color):
        """Test colorization of fully transparent pixels (alpha=0)."""
        pixels = '.'
        colors = {'.': (255, 0, 255, 0)}
        result = renderer_with_color._colorize_pixels(pixels, colors)
        # Transparent pixels use light grey (192, 192, 192)
        assert '\033[38;2;192;192;192m' in result

    def test_colorize_semi_transparent_below_threshold(self, renderer_with_color):
        """Test colorization of semi-transparent pixels below alpha threshold."""
        pixels = '#'
        # Alpha = 50, which is below ALPHA_TRANSPARENCY_THRESHOLD (128)
        colors = {'#': (200, 100, 50, 50)}
        result = renderer_with_color._colorize_pixels(pixels, colors)
        # Should use transparency char with adjusted colors
        assert '\033[' in result
        assert '\033[0m' in result

    def test_colorize_semi_transparent_above_threshold(self, renderer_with_color):
        """Test colorization of semi-transparent pixels above alpha threshold."""
        pixels = '#'
        # Alpha = 200, above ALPHA_TRANSPARENCY_THRESHOLD but below 255
        colors = {'#': (200, 100, 50, 200)}
        result = renderer_with_color._colorize_pixels(pixels, colors)
        # Should use pixel char with alpha-adjusted color
        adjusted_r = int(200 * (200 / 255))
        adjusted_g = int(100 * (200 / 255))
        adjusted_b = int(50 * (200 / 255))
        assert f'\033[38;2;{adjusted_r};{adjusted_g};{adjusted_b}m' in result

    def test_colorize_multiline_pixels(self, renderer_with_color):
        """Test colorization of multiline pixel data."""
        pixels = '#@\n@#'
        colors = {
            '#': (255, 0, 0, 255),
            '@': (0, 255, 0, 255),
        }
        result = renderer_with_color._colorize_pixels(pixels, colors)
        lines = result.split('\n')
        assert len(lines) == 2

    def test_colorize_unmapped_character(self, renderer_with_color):
        """Test that unmapped characters are handled via _colorize_non_mapped_char."""
        pixels = 'X'
        colors = {'#': (255, 0, 0, 255)}
        result = renderer_with_color._colorize_pixels(pixels, colors)
        # 'X' is not in colors, should pass through
        assert 'X' in result


class TestColorizeNonMappedChar:
    """Test ASCIIRenderer._colorize_non_mapped_char method."""

    def test_dot_with_magenta_in_colors(self, renderer_with_color):
        """Test that '.' with magenta in colors is treated as transparency."""
        colors = {'.': (255, 0, 255, 0)}
        result = renderer_with_color._colorize_non_mapped_char('.', colors)
        # Should render as transparent with light grey
        assert '\033[38;2;192;192;192m' in result

    def test_dot_without_magenta_in_colors(self, renderer_with_color):
        """Test that '.' without magenta colors passes through unchanged."""
        colors = {'#': (255, 0, 0, 255)}
        result = renderer_with_color._colorize_non_mapped_char('.', colors)
        assert result == '.'

    def test_non_dot_char_passes_through(self, renderer_with_color):
        """Test that non-dot unmapped characters pass through unchanged."""
        colors = {'#': (255, 0, 255, 0)}
        result = renderer_with_color._colorize_non_mapped_char('X', colors)
        assert result == 'X'

    def test_space_passes_through(self, renderer_with_color):
        """Test that space characters pass through unchanged."""
        colors = {'#': (255, 0, 0, 255)}
        result = renderer_with_color._colorize_non_mapped_char(' ', colors)
        assert result == ' '


class TestColorizeColorsSection:
    """Test ASCIIRenderer._colorize_colors_section method."""

    def test_plain_format_without_color_support(self, renderer_without_color):
        """Test plain TOML format when colors are not supported."""
        colors = {'#': (255, 0, 0)}
        result = renderer_without_color._colorize_colors_section(colors)
        assert '[colors]' in result
        assert '[colors."#"]' in result
        assert 'red = 255' in result
        assert 'green = 0' in result
        assert 'blue = 0' in result

    def test_colorized_format_with_color_support(self, renderer_with_color):
        """Test colorized output when colors are supported."""
        colors = {'#': (255, 0, 0)}
        result = renderer_with_color._colorize_colors_section(colors)
        assert '[colors]' in result
        assert '\033[38;2;255;0;0m' in result
        assert '\033[0m' in result
        assert 'red = 255' in result

    def test_multiple_colors_section(self, renderer_without_color):
        """Test colors section with multiple color entries."""
        colors = {
            '#': (255, 0, 0),
            '@': (0, 255, 0),
        }
        result = renderer_without_color._colorize_colors_section(colors)
        assert '[colors."#"]' in result
        assert '[colors."@"]' in result

    def test_empty_colors_section(self, renderer_without_color):
        """Test colors section with no color entries."""
        result = renderer_without_color._colorize_colors_section({})
        assert result == '[colors]'


class TestGetTransparencyChar:
    """Test ASCIIRenderer._get_transparency_char method."""

    def test_with_color_support(self, renderer_with_color):
        """Test transparency char is full block with color support."""
        assert renderer_with_color._get_transparency_char() == '\u2588'

    def test_without_color_support(self, renderer_without_color):
        """Test transparency char is space without color support."""
        assert renderer_without_color._get_transparency_char() == ' '


class TestGetPixelChar:
    """Test ASCIIRenderer._get_pixel_char method."""

    def test_always_returns_block_char(self):
        """Test that _get_pixel_char always returns the full block character."""
        renderer = ASCIIRenderer()
        assert renderer._get_pixel_char('#') == '\u2588'
        assert renderer._get_pixel_char('@') == '\u2588'
        assert renderer._get_pixel_char('.') == '\u2588'


class TestRenderSprite:
    """Test ASCIIRenderer.render_sprite method."""

    def test_render_complete_sprite(self, renderer_without_color):
        """Test rendering a complete sprite without color support."""
        sprite_data = {
            'sprite': {'name': 'test_sprite', 'pixels': '##\n##'},
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0},
            },
        }
        result = renderer_without_color.render_sprite(sprite_data)
        assert '[sprite]' in result
        assert 'name = "test_sprite"' in result
        assert 'pixels = """' in result
        assert '##' in result
        assert '"""' in result

    def test_render_sprite_no_pixels(self, renderer_without_color):
        """Test rendering a sprite with no pixel data returns fallback message."""
        sprite_data = {
            'sprite': {'name': 'empty'},
            'colors': {},
        }
        result = renderer_without_color.render_sprite(sprite_data)
        assert result == 'No pixels data found'

    def test_render_sprite_caching(self, renderer_without_color):
        """Test that render_sprite caches results."""
        sprite_data = {
            'sprite': {'name': 'cached', 'pixels': '#'},
            'colors': {'#': {'red': 0, 'green': 0, 'blue': 0}},
        }
        first_result = renderer_without_color.render_sprite(sprite_data)
        second_result = renderer_without_color.render_sprite(sprite_data)
        assert first_result == second_result
        # Verify cache was populated
        assert len(renderer_without_color._render_cache) == 1

    def test_render_sprite_with_color_support(self, renderer_with_color):
        """Test rendering a sprite with color support produces escape codes."""
        sprite_data = {
            'sprite': {'name': 'colorful', 'pixels': '#'},
            'colors': {
                '#': {'red': 255, 'green': 0, 'blue': 0},
            },
        }
        result = renderer_with_color.render_sprite(sprite_data)
        assert '[sprite]' in result
        assert '\033[' in result  # Contains escape codes

    def test_render_sprite_without_sprite_section(self, renderer_without_color):
        """Test rendering when sprite_data has animation but no sprite section."""
        sprite_data = {
            'animation': [
                {
                    'namespace': 'walk',
                    'frame': [{'pixels': 'AB\nCD'}],
                }
            ],
            'colors': {
                'A': {'red': 255, 'green': 0, 'blue': 0},
                'B': {'red': 0, 'green': 255, 'blue': 0},
                'C': {'red': 0, 'green': 0, 'blue': 255},
                'D': {'red': 255, 'green': 255, 'blue': 0},
            },
        }
        result = renderer_without_color.render_sprite(sprite_data)
        # No [sprite] section, so output_lines is empty but pixels were found
        # The method only adds output when 'sprite' key is in sprite_data
        assert '[sprite]' not in result

    def test_render_sprite_with_name_only(self, renderer_without_color):
        """Test rendering a sprite with name and pixels but minimal colors."""
        sprite_data = {
            'sprite': {'pixels': '#'},
            'colors': {},
        }
        result = renderer_without_color.render_sprite(sprite_data)
        assert '[sprite]' in result
        assert 'name =' not in result  # No name key
        assert 'pixels = """' in result


class TestClearCache:
    """Test ASCIIRenderer.clear_cache method."""

    def test_clear_cache_empties_render_cache(self):
        """Test that clear_cache empties the render cache."""
        renderer = ASCIIRenderer()
        renderer._render_cache['test_key'] = 'test_value'
        renderer.color_mapper._color_cache[255, 0, 0] = '\033[31m'

        renderer.clear_cache()

        assert renderer._render_cache == {}
        assert renderer.color_mapper._color_cache == {}

    def test_clear_cache_also_clears_color_mapper(self):
        """Test that clear_cache also clears the color mapper's cache."""
        renderer = ASCIIRenderer()
        renderer.color_mapper._capability = 'true_color'

        renderer.clear_cache()

        assert renderer.color_mapper._capability is None
