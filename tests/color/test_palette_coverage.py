"""Tests for glitchygames.color.palette module - ColorPalette and PaletteUtility."""

import configparser
import tempfile
from pathlib import Path

import pytest
from pygame import Color

from glitchygames.color.palette import ColorLike, ColorPalette, PaletteUtility, System, Vga


class TestColorPalette:
    """Test ColorPalette class."""

    def test_init_with_colors(self):
        colors: list[ColorLike] = [Color(255, 0, 0), Color(0, 255, 0)]
        palette = ColorPalette(colors=colors)
        assert palette._size == 1  # len - 1

    def test_init_empty(self):
        palette = ColorPalette(colors=[])
        assert palette._size == 0

    def test_get_color_valid_index(self):
        colors: list[ColorLike] = [Color(255, 0, 0), Color(0, 255, 0), Color(0, 0, 255)]
        palette = ColorPalette(colors=colors)
        assert palette.get_color(0) == Color(255, 0, 0)
        assert palette.get_color(1) == Color(0, 255, 0)

    def test_get_color_out_of_range(self):
        colors: list[ColorLike] = [Color(255, 0, 0), Color(0, 255, 0)]
        palette = ColorPalette(colors=colors)
        # Index > size returns None
        result = palette.get_color(5)
        assert result is None

    def test_get_color_empty_palette_returns_magenta(self):
        palette = ColorPalette(colors=[])
        result = palette.get_color(0)
        assert result == (255, 0, 255)

    def test_set_color_existing_index(self):
        colors: list[ColorLike] = [Color(255, 0, 0), Color(0, 255, 0)]
        palette = ColorPalette(colors=colors)
        palette.set_color(0, Color(128, 128, 128))
        assert palette._colors[0] == Color(128, 128, 128)  # type: ignore[not-subscriptable]

    def test_set_color_appends(self):
        colors: list[ColorLike] = [Color(255, 0, 0)]
        palette = ColorPalette(colors=colors)
        palette.set_color(5, Color(0, 0, 255))
        assert Color(0, 0, 255) in palette._colors  # type: ignore[unsupported-operator]


class TestPaletteUtility:
    """Test PaletteUtility class."""

    def test_load_palette_from_config(self):
        config = configparser.ConfigParser()
        config['default'] = {'colors': '2'}
        config['0'] = {'red': '255', 'green': '0', 'blue': '0'}
        config['1'] = {'red': '0', 'green': '255', 'blue': '0'}

        colors = PaletteUtility.load_palette_from_config(config)
        assert len(colors) == 2
        assert colors[0].r == 255
        assert colors[1].g == 255

    def test_create_palette_data(self):
        colors: list[Color] = [Color(255, 0, 0, 255), Color(0, 255, 0, 255)]
        config = PaletteUtility.create_palette_data(colors)
        assert config['default']['colors'] == '2'
        assert config['0']['red'] == '255'
        assert config['1']['green'] == '255'

    def test_write_and_load_palette_file(self):
        # Create palette data
        config_data = {'colors': 2, '0': {'r': 255, 'g': 0, 'b': 0}}

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.palette', delete=False, encoding='utf-8'
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)

        try:
            PaletteUtility.write_palette_to_file(config_data, tmp_path)
            assert tmp_path.exists()
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_load_palette_from_file(self):
        # Create a valid palette file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.palette', delete=False, encoding='utf-8'
        ) as tmp_file:
            tmp_file.write('[default]\ncolors = 1\n[0]\nred = 128\ngreen = 64\nblue = 32\n')
            tmp_path = Path(tmp_file.name)

        try:
            colors = PaletteUtility.load_palette_from_file(tmp_path)
            assert len(colors) == 1
            assert colors[0].r == 128
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_parse_rgb_data_in_file(self):
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.txt', delete=False, encoding='utf-8'
        ) as tmp_file:
            tmp_file.write('255,0,0,255\n0,255,0,255\n255,0,0,255\n')
            tmp_path = Path(tmp_file.name)

        try:
            colors = PaletteUtility.parse_rgb_data_in_file(tmp_path)
            assert len(colors) == 2  # No duplicates
        finally:
            tmp_path.unlink(missing_ok=True)


class TestBuiltInPalettes:
    """Test built-in palette classes."""

    def test_system_palette_init_requires_colors_arg(self):
        """System.__init__ calls super().__init__(filename=SYSTEM) without colors arg.

        This is a bug - System and Vga classes are missing colors=[] in their
        super().__init__() calls. This test documents the current behavior.
        """
        with pytest.raises(TypeError, match='missing 1 required positional argument'):
            System()

    def test_vga_palette_init_requires_colors_arg(self):
        """Vga.__init__ calls super().__init__(filename=VGA) without colors arg.

        Same bug as System - missing colors=[] argument.
        """
        with pytest.raises(TypeError, match='missing 1 required positional argument'):
            Vga()
