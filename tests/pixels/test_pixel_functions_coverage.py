"""Tests for glitchygames.pixels.pixel module - pixel data handling functions."""

import pygame
import pytest

from glitchygames.pixels.pixel import (
    image_from_pixels,
    indexed_rgb_triplet_generator,
    pixels_from_data,
    rgb_555_triplet_generator,
    rgb_565_triplet_generator,
    rgb_triplet_generator,
)


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

    def test_1x1(self):
        pixels = [(128, 64, 32)]
        surface = image_from_pixels(pixels, width=1, height=1)
        assert surface.get_size() == (1, 1)

    def test_3x1(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        surface = image_from_pixels(pixels, width=3, height=1)
        assert surface.get_size() == (3, 1)

    def test_1x3(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        surface = image_from_pixels(pixels, width=1, height=3)
        assert surface.get_size() == (1, 3)
