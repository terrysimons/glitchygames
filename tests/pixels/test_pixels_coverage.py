"""Comprehensive test coverage for Pixels module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

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


class TestPixelsCoverage:
    """Test coverage for Pixels module."""

    def test_indexed_rgb_triplet_generator(self):
        """Test indexed_rgb_triplet_generator function."""
        # Test with valid pixel data
        pixel_data = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        result = list(indexed_rgb_triplet_generator(pixel_data))
        assert result == [255, 0, 0]

        # Test with empty data
        result = list(indexed_rgb_triplet_generator([]))
        assert result == []

        # Test with single item
        pixel_data = [(128, 64, 32)]
        result = list(indexed_rgb_triplet_generator(pixel_data))
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
        pixel_data = b"\xff\x00\x00\x00\xff\x00\x00\x00\xff"  # RGB triplets
        result = list(rgb_triplet_generator(pixel_data))
        assert len(result) == RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)
        assert result[2] == (0, 0, 255)

        # Test with empty data - should raise ValueError
        with pytest.raises(ValueError, match="Empty data"):
            list(rgb_triplet_generator(b""))

        # Test with single triplet
        pixel_data = b"\x80\x40\x20"  # Single RGB triplet
        result = list(rgb_triplet_generator(pixel_data))
        assert len(result) == 1
        assert result[0] == (128, 64, 32)

    def test_image_from_pixels(self):
        """Test image_from_pixels function."""
        with patch("pygame.Surface") as mock_surface:
            # Mock the surface
            mock_surface_instance = Mock()
            mock_surface.return_value = mock_surface_instance

            # Test with valid pixel data
            pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
            width, height = 2, 2

            image_from_pixels(pixels, width, height)

            # Verify pygame.Surface was called with correct parameters
            mock_surface.assert_called_once_with((width, height))

            # Verify image.fill was called for each pixel
            assert mock_surface_instance.fill.call_count == len(pixels)

            # Test with empty pixels
            image_from_pixels([], 0, 0)
            mock_surface.assert_called_with((0, 0))

    def test_pixels_from_data(self):
        """Test pixels_from_data function."""
        # Test with valid data
        pixel_data = [255, 0, 0, 0, 255, 0, 0, 0, 255]  # RGB values
        result = pixels_from_data(pixel_data)
        assert len(result) == RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)
        assert result[2] == (0, 0, 255)

        # Test with empty data - should raise ValueError
        with pytest.raises(ValueError, match="Empty data"):
            pixels_from_data([])

        # Test with single pixel
        pixel_data = [128, 64, 32]
        result = pixels_from_data(pixel_data)
        assert len(result) == 1
        assert result[0] == (128, 64, 32)

        # Test with incomplete pixel (not divisible by 3) - should raise ValueError
        pixel_data = [255, 0]  # Only 2 values, need 3 for RGB
        with pytest.raises(ValueError, match="Invalid data length"):
            pixels_from_data(pixel_data)

    def test_pixels_from_path(self):
        """Test pixels_from_path function."""
        with patch("pathlib.Path.open", unittest.mock.mock_open(
            read_data=b"\xff\x00\x00\x00\xff\x00\x00\x00\xff"
        )):
            # Test with valid file path
            result = pixels_from_path("test_file.txt")
            assert len(result) == RGB_COMPONENTS_PER_PIXEL
            assert result[0] == (255, 0, 0)
            assert result[1] == (0, 255, 0)
            assert result[2] == (0, 0, 255)

        # Test with empty file - should raise ValueError
        with patch("pathlib.Path.open", unittest.mock.mock_open(read_data=b"")), \
             pytest.raises(ValueError, match="Empty file"):
            pixels_from_path("empty_file.txt")

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
        pixel_data = b"\xff\x00"  # Only 2 bytes, need 3 for RGB
        with pytest.raises(ValueError, match="Invalid data length"):
            list(rgb_triplet_generator(pixel_data))

        # Test image_from_pixels with zero dimensions
        with patch("pygame.Surface") as mock_surface, \
             patch("pygame.PixelArray") as mock_pixel_array:
            mock_surface_instance = Mock()
            mock_surface.return_value = mock_surface_instance
            mock_pixel_array_instance = Mock()
            mock_pixel_array.return_value = mock_pixel_array_instance

            image_from_pixels([], 0, 0)
            mock_surface.assert_called_with((0, 0))

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
        pixel_data = [255, 0, 0]
        result = pixels_from_data(pixel_data)
        assert len(result) == 1
        assert result[0] == (255, 0, 0)

        # Test with 6 values (two pixels)
        pixel_data = [255, 0, 0, 0, 255, 0]
        result = pixels_from_data(pixel_data)
        assert len(result) == TWO_PIXEL_COMPONENTS // RGB_COMPONENTS_PER_PIXEL
        assert result[0] == (255, 0, 0)
        assert result[1] == (0, 255, 0)

        # Test with 1 value (incomplete pixel) - should raise ValueError
        pixel_data = [255]
        with pytest.raises(ValueError, match="Invalid data length"):
            pixels_from_data(pixel_data)

        # Test with 2 values (incomplete pixel) - should raise ValueError
        pixel_data = [255, 0]
        with pytest.raises(ValueError, match="Invalid data length"):
            pixels_from_data(pixel_data)

    def test_pixels_from_path_edge_cases(self):
        """Test pixels_from_path edge cases."""
        # Test with file containing invalid data (not divisible by 3)
        with patch("pathlib.Path.open", unittest.mock.mock_open(
            read_data=b"\xff\x00"
        )), patch("pathlib.Path.exists", return_value=True), \
             pytest.raises(ValueError, match="Invalid data length"):
            pixels_from_path("invalid_file.txt")

        # Test with file containing valid data
        with patch("pathlib.Path.open", unittest.mock.mock_open(
            read_data=b"\xff\x00\x00\x00\xff\x00"
        )), patch("pathlib.Path.exists", return_value=True):
            result = pixels_from_path("valid_file.txt")
            assert len(result) == TWO_PIXEL_BYTES // RGB_BYTES_PER_PIXEL
            assert result[0] == (255, 0, 0)
            assert result[1] == (0, 255, 0)
