"""Test suite for pixel utility functions.

Tests bounding box computation, pixel transparency detection,
and envelope bounding box calculation.
"""

from glitchygames.sprites.pixel_utils import (
    compute_bounding_box,
    compute_envelope_bounding_box,
    is_pixel_transparent,
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
