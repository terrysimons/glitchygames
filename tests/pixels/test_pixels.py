"""Comprehensive test coverage for Pixels module."""

from typing import cast

import pygame
import pytest

from glitchygames.pixels import (
    image_from_pixels,
    indexed_rgb_triplet_generator,
    pixels_from_data,
    pixels_from_path,
    rgb_555_triplet_generator,
    rgb_565_triplet_generator,
    rgb_triplet_generator,
)

# Constants for magic values
RGB_COMPONENTS_PER_PIXEL = 3
SINGLE_PIXEL_COMPONENTS = 3
TWO_PIXEL_COMPONENTS = 6
RGB_BYTES_PER_PIXEL = 3
TWO_PIXEL_BYTES = 6


def _rgb_rows(image):
    """Return an image's RGB pixels, row by row.

    Returns:
        list[list[tuple[int, int, int]]]: ``rows[y][x]``.

    """
    rows = pygame.surfarray.array3d(image).transpose(1, 0, 2).tolist()
    return [[tuple(pixel) for pixel in row] for row in rows]


class TestPixelsCoverage:
    """Test coverage for Pixels module."""

    def test_indexed_rgb_triplet_generator(self):
        """Test indexed_rgb_triplet_generator function."""
        # Test with valid pixel data
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0), (0, 255, 0), (0, 0, 255)])
        result = list(indexed_rgb_triplet_generator(pixel_data))  # type: ignore[invalid-argument-type]
        assert result == [255, 0, 0]

        # Test with empty data
        result = list(indexed_rgb_triplet_generator([]))
        assert result == []

        # Test with single item
        pixel_data = cast('list[tuple[int, ...]]', [(128, 64, 32)])
        result = list(indexed_rgb_triplet_generator(pixel_data))  # type: ignore[invalid-argument-type]
        assert result == [128]

    def test_rgb_555_triplet_generator(self):
        """Test rgb_555_triplet_generator function."""
        # Test with 555 format data - Red=31 (max), Green=0, Blue=0
        # In 555 format: RRRRRGGGGGBBBBB (5 bits each)
        pixel_data = [(0b1111100000000000,)]  # Red=31, Green=0, Blue=0
        result = list(rgb_555_triplet_generator(pixel_data))
        assert len(result) == 1
        # Red=31*8+7=255, Green=0, Blue=0
        assert result[0] == (255, 0, 0)

        # Test with green - Red=0, Green=31, Blue=0
        pixel_data = [(0b0000011111000000,)]  # Red=0, Green=31, Blue=0
        result = list(rgb_555_triplet_generator(pixel_data))
        assert len(result) == 1
        # Red=0, Green=31*8+7=255, Blue=0
        assert result[0] == (0, 255, 0)

        # Test with blue - Red=0, Green=0, Blue=31
        # In 555 format: RRRRRGGGGGBBBBB (5 bits each)
        # Blue is at bits 10-14 (0-indexed)
        pixel_data = [(0b0000000000011111,)]  # Red=0, Green=0, Blue=31 at bits 10-14
        result = list(rgb_555_triplet_generator(pixel_data))
        assert len(result) == 1
        # Red=0, Green=0, Blue=31*4+7=127 (not 255)
        assert result[0] == (0, 0, 127)

        # Test with empty data
        result = list(rgb_555_triplet_generator([]))
        assert result == []

    def test_rgb_565_triplet_generator(self):
        """Test rgb_565_triplet_generator function."""
        # Test with 565 format data
        pixel_data = [(0b1111100000000000,)]  # Red=31, Green=0, Blue=0
        result = list(rgb_565_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (255, 0, 0)  # Red should be max

        # Test with green (6 bits)
        pixel_data = [(0b0000011111100000,)]  # Red=0, Green=63, Blue=0
        result = list(rgb_565_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (0, 255, 0)  # Green should be max

        # Test with blue
        pixel_data = [(0b0000000000011111,)]  # Red=0, Green=0, Blue=31
        result = list(rgb_565_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (0, 0, 255)  # Blue should be max

        # Test with empty data
        result = list(rgb_565_triplet_generator([]))
        assert result == []

    def test_rgb_triplet_generator(self):
        """Test rgb_triplet_generator function."""
        # Test with valid bytes data
        pixel_data = b'\xff\x00\x00\x00\xff\x00\x00\x00\xff'  # RGB triplets
        result = list(rgb_triplet_generator(pixel_data))
        assert len(result) == RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)
        assert result[2] == (0, 0, 255)

        # Test with empty data - should raise ValueError
        with pytest.raises(ValueError, match='Empty pixel data'):
            list(rgb_triplet_generator(b''))

        # Test with single triplet
        pixel_data = b'\x80\x40\x20'  # Single RGB triplet
        result = list(rgb_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (128, 64, 32)

    def test_image_from_pixels(self):
        """image_from_pixels draws the pixels left to right, then top to bottom."""
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        width, height = 2, 2

        image = image_from_pixels(pixels, width, height)

        assert image.get_size() == (width, height)
        assert _rgb_rows(image) == [
            [(255, 0, 0), (0, 255, 0)],
            [(0, 0, 255), (255, 255, 255)],
        ]

        # Test with empty pixels: an empty surface
        assert image_from_pixels([], 0, 0).get_size() == (0, 0)

    def test_pixels_from_data(self):
        """Test pixels_from_data function."""
        # Test with valid data
        pixel_data = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255])  # RGB values
        result = pixels_from_data(pixel_data)
        assert len(result) == RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)
        assert result[2] == (0, 0, 255)

        # Test with empty data - should raise ValueError
        with pytest.raises(ValueError, match='Empty pixel data'):
            pixels_from_data(b'')

        # Test with single pixel
        pixel_data = bytes([128, 64, 32])
        result = pixels_from_data(pixel_data)
        assert len(result) == 1
        assert result[0] == (128, 64, 32)

        # Test with incomplete pixel (not divisible by 3) - should raise ValueError
        pixel_data = bytes([255, 0])  # Only 2 values, need 3 for RGB
        with pytest.raises(ValueError, match='Pixel data length \\(2\\) is not divisible by 3'):
            pixels_from_data(pixel_data)

    def test_pixels_from_path(self, tmp_path):
        """Test pixels_from_path function."""
        pixel_file = tmp_path / 'test_file.txt'
        pixel_file.write_bytes(b'\xff\x00\x00\x00\xff\x00\x00\x00\xff')
        # Test with valid file path
        result = pixels_from_path(str(pixel_file))
        assert len(result) == RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)
        assert result[2] == (0, 0, 255)

    def test_pixels_from_path_empty_file(self, tmp_path):
        """Test pixels_from_path with empty file."""
        # Test with empty file - should raise ValueError
        pixel_file = tmp_path / 'empty_file.txt'
        pixel_file.write_bytes(b'')
        with pytest.raises(ValueError, match='Empty pixel data'):
            pixels_from_path(str(pixel_file))

    def test_edge_cases(self):
        """Test edge cases for all functions."""
        # Test indexed_rgb_triplet_generator with empty data
        result = list(indexed_rgb_triplet_generator([]))
        assert result == []

        # Test rgb_555_triplet_generator with zero values
        pixel_data = [(0,)]  # All zeros
        result = list(rgb_555_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (0, 0, 0)

        # Test rgb_565_triplet_generator with zero values
        pixel_data = [(0,)]  # All zeros
        result = list(rgb_565_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (0, 0, 0)

        # Test rgb_triplet_generator with odd number of bytes - should raise ValueError
        pixel_data = b'\xff\x00'  # Only 2 bytes, need 3 for RGB
        with pytest.raises(ValueError, match='Pixel data length \\(2\\) is not divisible by 3'):
            list(rgb_triplet_generator(pixel_data))

    def test_edge_cases_image_from_pixels(self):
        """image_from_pixels with zero dimensions returns an empty surface."""
        image = image_from_pixels([], 0, 0)
        assert isinstance(image, pygame.Surface)
        assert image.get_size() == (0, 0)

    def test_rgb_555_edge_cases(self):
        """Test rgb_555_triplet_generator edge cases."""
        # Test with maximum values (all 1s)
        pixel_data = [(0b1111111111111111,)]  # All bits set
        result = list(rgb_555_triplet_generator(pixel_data))
        assert len(result) == 1
        # Red=31, Green=31, Blue=31 -> should be (255, 255, 255)
        assert result[0] == (255, 255, 255)

        # Test with minimum values (all 0s)
        pixel_data = [(0b0000000000000000,)]  # All bits clear
        result = list(rgb_555_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (0, 0, 0)

    def test_rgb_565_edge_cases(self):
        """Test rgb_565_triplet_generator edge cases."""
        # Test with maximum values (all 1s)
        pixel_data = [(0b1111111111111111,)]  # All bits set
        result = list(rgb_565_triplet_generator(pixel_data))
        assert len(result) == 1
        # Red=31, Green=63, Blue=31 -> should be (255, 255, 255)
        assert result[0] == (255, 255, 255)

        # Test with minimum values (all 0s)
        pixel_data = [(0b0000000000000000,)]  # All bits clear
        result = list(rgb_565_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (0, 0, 0)

    def test_pixels_from_data_edge_cases(self):
        """Test pixels_from_data edge cases."""
        # Test with exactly 3 values (single pixel)
        pixel_data = bytes([255, 0, 0])
        result = pixels_from_data(pixel_data)
        assert len(result) == 1
        assert result[0] == (255, 0, 0)

        # Test with 6 values (two pixels)
        pixel_data = bytes([255, 0, 0, 0, 255, 0])
        result = pixels_from_data(pixel_data)
        assert len(result) == TWO_PIXEL_COMPONENTS // RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)

        # Test with 1 value (incomplete pixel) - should raise ValueError
        pixel_data = bytes([255])
        with pytest.raises(ValueError, match='Pixel data length \\(1\\) is not divisible by 3'):
            pixels_from_data(pixel_data)

        # Test with 2 values (incomplete pixel) - should raise ValueError
        pixel_data = bytes([255, 0])
        with pytest.raises(ValueError, match='Pixel data length \\(2\\) is not divisible by 3'):
            pixels_from_data(pixel_data)

    def test_pixels_from_path_edge_cases(self, tmp_path):
        """Test pixels_from_path edge cases."""
        # Test with file containing invalid data (not divisible by 3)
        pixel_file = tmp_path / 'invalid_file.txt'
        pixel_file.write_bytes(b'\xff\x00')
        with pytest.raises(ValueError, match='Pixel data length \\(2\\) is not divisible by 3'):
            pixels_from_path(str(pixel_file))

    def test_pixels_from_path_edge_cases_valid(self, tmp_path):
        """Test pixels_from_path edge cases with valid data."""
        # Test with file containing valid data
        pixel_file = tmp_path / 'valid_file.txt'
        pixel_file.write_bytes(b'\xff\x00\x00\x00\xff\x00')
        result = pixels_from_path(str(pixel_file))
        assert len(result) == TWO_PIXEL_BYTES // RGB_BYTES_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)


# ---------------------------------------------------------------------------
# Tests from test_pixel_functions_coverage.py
# Covers: individual generator/function classes with focused test methods.
# ---------------------------------------------------------------------------


class TestIndexedRgbTripletGenerator:
    """Test indexed_rgb_triplet_generator."""

    def test_basic_triplets(self):
        data = [((255, 0, 0),), ((0, 255, 0),), ((0, 0, 255),)]
        result = list(indexed_rgb_triplet_generator(data))
        assert result == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    def test_empty_data(self):
        result = list(indexed_rgb_triplet_generator([]))
        assert result == []

    def test_single_pixel(self):
        data = [((128, 64, 32),)]
        result = list(indexed_rgb_triplet_generator(data))
        assert result == [(128, 64, 32)]


class TestRgb555TripletGenerator:
    """Test rgb_555_triplet_generator."""

    def test_basic_white(self):
        # 555: all ones = 0x7FFF = 32767
        # Red: 11111 -> 248 + 7 = 255
        # Green: 11111 -> 248 + 7 = 255
        # Blue: 11111 -> 248 + 7 = 255
        data = [(0x7FFF,)]
        result = list(rgb_555_triplet_generator(data))
        assert len(result) == 1
        red, green, blue = result[0]
        assert red > 0
        assert green > 0
        assert blue > 0

    def test_black(self):
        # All zeros
        data = [(0,)]
        result = list(rgb_555_triplet_generator(data))
        assert len(result) == 1
        red, green, blue = result[0]
        assert red == 0
        assert green == 0
        assert blue == 0

    def test_empty_data(self):
        result = list(rgb_555_triplet_generator([]))
        assert result == []

    def test_multiple_pixels(self):
        data = [(0,), (0x7FFF,)]
        result = list(rgb_555_triplet_generator(data))
        assert len(result) == 2


class TestRgb565TripletGenerator:
    """Test rgb_565_triplet_generator."""

    def test_basic_white(self):
        # 565: all ones = 0xFFFF = 65535
        data = [(0xFFFF,)]
        result = list(rgb_565_triplet_generator(data))
        assert len(result) == 1
        red, green, blue = result[0]
        assert red > 0
        assert green > 0
        assert blue > 0

    def test_black(self):
        data = [(0,)]
        result = list(rgb_565_triplet_generator(data))
        assert len(result) == 1
        red, green, blue = result[0]
        assert red == 0
        assert green == 0
        assert blue == 0

    def test_empty_data(self):
        result = list(rgb_565_triplet_generator([]))
        assert result == []


class TestRgbTripletGenerator:
    """Test rgb_triplet_generator."""

    def test_basic(self):
        data = bytes([255, 0, 0, 0, 255, 0, 0, 0, 255])
        result = list(rgb_triplet_generator(data))
        assert result == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    def test_empty_raises(self):
        with pytest.raises(ValueError, match='Empty pixel data'):
            list(rgb_triplet_generator(b''))

    def test_not_divisible_by_3_raises(self):
        with pytest.raises(ValueError, match='not divisible by 3'):
            list(rgb_triplet_generator(bytes([1, 2])))

    def test_single_triplet(self):
        data = bytes([128, 64, 32])
        result = list(rgb_triplet_generator(data))
        assert result == [(128, 64, 32)]


class TestPixelsFromData:
    """Test pixels_from_data."""

    def test_basic(self):
        data = bytes([255, 0, 0, 0, 255, 0])
        result = pixels_from_data(data)
        assert result == [(255, 0, 0), (0, 255, 0)]

    def test_returns_list(self):
        data = bytes([1, 2, 3])
        result = pixels_from_data(data)
        assert isinstance(result, list)


class TestImageFromPixels:
    """Test image_from_pixels."""

    def test_basic_2x2(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        surface = image_from_pixels(pixels, width=2, height=2)
        assert isinstance(surface, pygame.Surface)
        assert surface.get_size() == (2, 2)
        assert _rgb_rows(surface) == [
            [(255, 0, 0), (0, 255, 0)],
            [(0, 0, 255), (255, 255, 0)],
        ]

    def test_1x1(self):
        pixels = [(128, 64, 32)]
        surface = image_from_pixels(pixels, width=1, height=1)
        assert surface.get_size() == (1, 1)
        assert _rgb_rows(surface) == [[(128, 64, 32)]]

    def test_3x1(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        surface = image_from_pixels(pixels, width=3, height=1)
        assert surface.get_size() == (3, 1)
        assert _rgb_rows(surface) == [[(255, 0, 0), (0, 255, 0), (0, 0, 255)]]

    def test_1x3(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        surface = image_from_pixels(pixels, width=1, height=3)
        assert surface.get_size() == (1, 3)
        assert _rgb_rows(surface) == [[(255, 0, 0)], [(0, 255, 0)], [(0, 0, 255)]]
