"""Test coverage for the color/palette module.

This module tests the ColorPalette and PaletteUtility classes which are
essential for color management in the game engine. These classes handle:

1. Color palette loading from files
2. Color palette creation and manipulation
3. Color indexing and retrieval
4. Palette utility functions for file operations

Without these tests, the color/palette module coverage remains incomplete
as the core color management functionality is not exercised.
"""

import configparser
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from glitchygames.color.palette import ColorPalette, PaletteUtility


class TestColorPaletteCoverage:
    """Test coverage for ColorPalette class."""

    def test_color_palette_initialization_with_colors(self):  # noqa: PLR6301
        """Test ColorPalette initialization with colors list."""
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        palette = ColorPalette(colors)

        assert palette._colors == colors
        expected_size = 2  # len(colors) - 1
        assert palette._size == expected_size

    def test_color_palette_initialization_with_filename(self):  # noqa: PLR6301
        """Test ColorPalette initialization with filename."""
        mock_colors = [(255, 0, 0), (0, 255, 0)]

        with patch.object(
            PaletteUtility, "load_palette_from_file", return_value=mock_colors
        ) as mock_load, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("sys.argv", ["/fake/script.py"]):

            palette = ColorPalette(colors=None, filename="test_palette")

            mock_load.assert_called_once()
            assert palette._colors == mock_colors
            assert palette._size == 1

    def test_color_palette_initialization_no_colors_no_filename(self):  # noqa: PLR6301
        """Test ColorPalette initialization with no colors and no filename."""
        palette = ColorPalette(colors=None, filename=None)

        assert palette._colors is None
        assert palette._size == 0

    def test_color_palette_initialization_filename_not_found(self):  # noqa: PLR6301
        """Test ColorPalette initialization when filename is not found."""
        with patch("pathlib.Path.exists", return_value=False), \
             patch("sys.argv", ["/fake/script.py"]):

            palette = ColorPalette(colors=None, filename="nonexistent")

            assert palette._colors is None
            assert palette._size == 0

    def test_get_color_valid_index(self):  # noqa: PLR6301
        """Test get_color with valid index."""
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        palette = ColorPalette(colors)

        result = palette.get_color(1)
        assert result == (0, 255, 0)

    def test_get_color_invalid_index(self):  # noqa: PLR6301
        """Test get_color with invalid index."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors)

        result = palette.get_color(5)
        assert result is None  # Returns None for invalid index

    def test_get_color_no_colors(self):  # noqa: PLR6301
        """Test get_color when no colors are set."""
        palette = ColorPalette(colors=None)

        result = palette.get_color(0)
        assert result == (255, 0, 255)  # Magenta fallback

    def test_set_color_valid_index(self):  # noqa: PLR6301
        """Test set_color with valid index."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors)

        palette.set_color(0, (128, 128, 128))  # Use index 0 instead of 1
        assert palette._colors[0] == (128, 128, 128)

    def test_set_color_invalid_index(self):  # noqa: PLR6301
        """Test set_color with invalid index (appends to list)."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors)

        palette.set_color(5, (128, 128, 128))
        assert palette._colors[2] == (128, 128, 128)
        expected_length = 3
        assert len(palette._colors) == expected_length


class TestPaletteUtilityCoverage:
    """Test coverage for PaletteUtility class."""

    def test_load_palette_from_config(self):  # noqa: PLR6301
        """Test loading palette from ConfigParser."""
        config = configparser.ConfigParser()
        config["default"] = {"colors": "2"}
        config["0"] = {"red": "255", "green": "0", "blue": "0", "alpha": "255"}
        config["1"] = {"red": "0", "green": "255", "blue": "0", "alpha": "255"}

        result = PaletteUtility.load_palette_from_config(config)
        expected = [(255, 0, 0), (0, 255, 0)]
        assert result == expected

    def test_load_palette_from_file_ini_format(self):  # noqa: PLR6301
        """Test loading palette from INI file."""
        ini_content = """[default]
colors = 2

[0]
red = 255
green = 0
blue = 0
alpha = 255

[1]
red = 0
green = 255
blue = 0
alpha = 255
"""

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".palette", delete=False, encoding="utf-8"
        ) as f:
            f.write(ini_content)
            temp_path = Path(f.name)

        try:
            result = PaletteUtility.load_palette_from_file(temp_path)
            expected = [(255, 0, 0), (0, 255, 0)]
            assert result == expected
        finally:
            temp_path.unlink()

    def test_load_palette_from_file_unsupported_format(self):  # noqa: PLR6301
        """Test loading palette from unsupported format."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("unsupported format")
            temp_path = Path(f.name)

        try:
            # The function tries to parse as INI first, which will raise MissingSectionHeaderError
            with pytest.raises(Exception, match=r".*"):  # Catch any parsing error
                PaletteUtility.load_palette_from_file(temp_path)
        finally:
            temp_path.unlink()

    def test_write_palette_to_file(self):  # noqa: PLR6301
        """Test writing palette to file."""
        config_data = {"colors": [{"r": 255, "g": 0, "b": 0}]}

        with tempfile.NamedTemporaryFile(suffix=".palette", delete=False) as f:
            temp_path = Path(f.name)

        try:
            PaletteUtility.write_palette_to_file(config_data, temp_path)

            # Verify the file was created
            assert temp_path.exists()
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_parse_rgb_data_in_file(self):  # noqa: PLR6301
        """Test parsing RGB data from file."""
        rgb_content = "255,0,0\n0,255,0\n0,0,255\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(rgb_content)
            temp_path = Path(f.name)

        try:
            result = PaletteUtility.parse_rgb_data_in_file(temp_path)
            expected = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
            assert result == expected
        finally:
            temp_path.unlink()

    def test_create_palette_data(self):  # noqa: PLR6301
        """Test creating palette data from colors."""
        from pygame import Color  # noqa: PLC0415

        # Use pygame Color objects instead of tuples
        colors = [Color(255, 0, 0), Color(0, 255, 0)]

        result = PaletteUtility.create_palette_data(colors)

        # Verify it returns a ConfigParser object
        assert hasattr(result, "sections")
        assert "default" in result.sections()
        assert result["default"]["colors"] == "2"
