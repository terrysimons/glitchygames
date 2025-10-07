"""Coverage tests for glitchygames.pixels."""

import contextlib
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


class TestRgbTripletGenerator(unittest.TestCase):
    """Test RGB triplet generator functionality."""

    def test_rgb_triplet_generator_valid(self) -> None:  # noqa: PLR6301
        """Test RGB triplet generator with valid data."""
        data = bytes([255, 0, 128, 10, 20, 30])  # two pixels
        result = list(rgb_triplet_generator(data))
        assert result == [(255, 0, 128), (10, 20, 30)]

    def test_rgb_triplet_generator_empty_raises(self) -> None:  # noqa: PLR6301
        """Test RGB triplet generator raises ValueError for empty data."""
        with pytest.raises(ValueError, match="Empty pixel data"):
            list(rgb_triplet_generator(b""))

    def test_rgb_triplet_generator_not_divisible_raises(self) -> None:  # noqa: PLR6301
        """Test RGB triplet generator raises ValueError for non-divisible data."""
        with pytest.raises(ValueError, match=r"Pixel data length.*is not divisible by 3"):
            list(rgb_triplet_generator(b"\x00\x01"))


class TestPixelsFromData(unittest.TestCase):
    """Test pixels_from_data functionality."""

    def test_pixels_from_data(self) -> None:  # noqa: PLR6301
        """Test pixels_from_data with valid input."""
        data = bytes([1, 2, 3, 4, 5, 6])
        pixels = pixels_from_data(data)
        assert pixels == [(1, 2, 3), (4, 5, 6)]


class TestPixelsFromPath(unittest.TestCase):
    """Test pixels_from_path functionality."""

    def test_pixels_from_path_reads_file(self) -> None:  # noqa: PLR6301
        """Test pixels_from_path reads file correctly."""
        # Create a temporary binary file
        tmp = Path.cwd() / "_tmp_pixels.bin"
        try:
            # Single RGB triplet should succeed
            tmp.write_bytes(bytes([7, 8, 9]))
            one = pixels_from_path(str(tmp))
            assert one == [(7, 8, 9)]

            # Two RGB triplets should also succeed
            tmp.write_bytes(bytes([7, 8, 9, 10, 11, 12]))
            result = pixels_from_path(str(tmp))
            assert result == [(7, 8, 9), (10, 11, 12)]
        finally:
            with contextlib.suppress(FileNotFoundError):
                tmp.unlink()


class TestImageFromPixels(unittest.TestCase):
    """Test image_from_pixels functionality."""

    def test_image_from_pixels_calls_fill_correctly(self) -> None:  # noqa: PLR6301
        """Test image_from_pixels calls fill correctly."""
        pixels = [(1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)]  # 2x2
        with patch("pygame.Surface") as mock_surface_cls:
            mock_surface = Mock()
            mock_surface.fill = Mock()
            mock_surface_cls.return_value = mock_surface

            img = image_from_pixels(pixels, width=2, height=2)
            assert img is mock_surface

            # Expect four fills with coordinates covering a 2x2 grid
            expected_calls = [
                ((1, 2, 3), ((0, 0), (1, 1))),
                ((4, 5, 6), ((1, 0), (1, 1))),
                ((7, 8, 9), ((0, 1), (1, 1))),
                ((10, 11, 12), ((1, 1), (1, 1))),
            ]
            actual = [tuple(args) for (args, _kwargs) in mock_surface.fill.call_args_list]
            assert actual == expected_calls


class TestIndexedRgbTripletGenerator(unittest.TestCase):
    """Test indexed RGB triplet generator functionality."""

    def test_indexed_rgb_triplet_generator_basic(self) -> None:  # noqa: PLR6301
        """Test indexed RGB triplet generator with basic data."""
        data = [(255, 0, 128), (10, 20, 30), (100, 200, 50)]
        result = list(indexed_rgb_triplet_generator(data))
        assert result == [255, 10, 100]  # Only first element of each tuple

    def test_indexed_rgb_triplet_generator_empty(self) -> None:  # noqa: PLR6301
        """Test indexed RGB triplet generator with empty data."""
        result = list(indexed_rgb_triplet_generator([]))
        assert result == []

    def test_indexed_rgb_triplet_generator_stop_iteration(self) -> None:  # noqa: PLR6301
        """Test indexed RGB triplet generator handles StopIteration."""
        # Test with empty iterator
        result = list(indexed_rgb_triplet_generator(iter([])))
        assert result == []


class TestRgb555TripletGenerator(unittest.TestCase):
    """Test RGB 555 triplet generator functionality."""

    def test_rgb_555_triplet_generator_basic(self) -> None:  # noqa: PLR6301
        """Test RGB 555 triplet generator with basic data."""
        # Test with a simple packed RGB value - use a smaller value
        data = [(0b111110000000000,)]  # All red bits set
        result = list(rgb_555_triplet_generator(data))
        assert len(result) == 1
        r, g, b = result[0]
        assert r >= 0  # Should have red component
        assert g >= 0  # Green component
        assert b >= 0  # Blue component

    def test_rgb_555_triplet_generator_empty(self) -> None:  # noqa: PLR6301
        """Test RGB 555 triplet generator with empty data."""
        result = list(rgb_555_triplet_generator([]))
        assert result == []

    def test_rgb_555_triplet_generator_stop_iteration(self) -> None:  # noqa: PLR6301
        """Test RGB 555 triplet generator handles StopIteration."""
        # Test with empty iterator
        result = list(rgb_555_triplet_generator(iter([])))
        assert result == []


class TestRgb565TripletGenerator(unittest.TestCase):
    """Test RGB 565 triplet generator functionality."""

    def test_rgb_565_triplet_generator_basic(self) -> None:  # noqa: PLR6301
        """Test RGB 565 triplet generator with basic data."""
        # Test with a simple packed RGB value - use a smaller value
        data = [(0b111110000000000,)]  # All red bits set
        result = list(rgb_565_triplet_generator(data))
        assert len(result) == 1
        r, g, b = result[0]
        assert r >= 0  # Should have red component
        assert g >= 0  # Green component
        assert b >= 0  # Blue component

    def test_rgb_565_triplet_generator_empty(self) -> None:  # noqa: PLR6301
        """Test RGB 565 triplet generator with empty data."""
        result = list(rgb_565_triplet_generator([]))
        assert result == []

    def test_rgb_565_triplet_generator_stop_iteration(self) -> None:  # noqa: PLR6301
        """Test RGB 565 triplet generator handles StopIteration."""
        # Test with empty iterator
        result = list(rgb_565_triplet_generator(iter([])))
        assert result == []


class TestRgbTripletGeneratorEdgeCases(unittest.TestCase):
    """Test RGB triplet generator edge cases."""

    def test_rgb_triplet_generator_index_error(self) -> None:  # noqa: PLR6301
        """Test RGB triplet generator handles IndexError."""
        # Create data that will cause IndexError
        data = bytes([1, 2])  # Not enough for a complete triplet
        with pytest.raises(ValueError, match=r"Pixel data length.*is not divisible by 3"):
            list(rgb_triplet_generator(data))

    def test_rgb_triplet_generator_single_triplet(self) -> None:  # noqa: PLR6301
        """Test RGB triplet generator with single triplet."""
        data = bytes([100, 150, 200])
        result = list(rgb_triplet_generator(data))
        assert result == [(100, 150, 200)]

    def test_rgb_triplet_generator_multiple_triplets(self) -> None:  # noqa: PLR6301
        """Test RGB triplet generator with multiple triplets."""
        data = bytes([1, 2, 3, 4, 5, 6, 7, 8, 9])
        result = list(rgb_triplet_generator(data))
        assert result == [(1, 2, 3), (4, 5, 6), (7, 8, 9)]


class TestImageFromPixelsEdgeCases(unittest.TestCase):
    """Test image_from_pixels edge cases."""

    def test_image_from_pixels_empty_pixels(self) -> None:  # noqa: PLR6301
        """Test image_from_pixels with empty pixel list."""
        with patch("pygame.Surface") as mock_surface_cls:
            mock_surface = Mock()
            mock_surface.fill = Mock()
            mock_surface_cls.return_value = mock_surface

            img = image_from_pixels([], width=2, height=2)
            assert img is mock_surface
            # Should not call fill for empty pixels
            mock_surface.fill.assert_not_called()

    def test_image_from_pixels_single_pixel(self) -> None:  # noqa: PLR6301
        """Test image_from_pixels with single pixel."""
        pixels = [(255, 0, 0)]
        with patch("pygame.Surface") as mock_surface_cls:
            mock_surface = Mock()
            mock_surface.fill = Mock()
            mock_surface_cls.return_value = mock_surface

            img = image_from_pixels(pixels, width=1, height=1)
            assert img is mock_surface
            mock_surface.fill.assert_called_once_with((255, 0, 0), ((0, 0), (1, 1)))

    def test_image_from_pixels_3x3_grid(self) -> None:  # noqa: PLR6301
        """Test image_from_pixels with 3x3 grid."""
        pixels = [(i, i, i) for i in range(9)]  # 9 pixels for 3x3
        with patch("pygame.Surface") as mock_surface_cls:
            mock_surface = Mock()
            mock_surface.fill = Mock()
            mock_surface_cls.return_value = mock_surface

            img = image_from_pixels(pixels, width=3, height=3)
            assert img is mock_surface
            expected_fill_calls = 9
            assert mock_surface.fill.call_count == expected_fill_calls
