"""Comprehensive test coverage for Color/Palette module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
import configparser
import json
import tempfile
import os

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.color import NES, SYSTEM, VGA, Default, YELLOW, PURPLE, BLUE, GREEN, WHITE, BLACK, BLACKLUCENT, BLUELUCENT, RED
from glitchygames.color.palette import ColorPalette, PaletteUtility, System, Vga


class TestColorConstantsCoverage(unittest.TestCase):
    """Test coverage for color constants and imports."""

    def test_color_constants_import(self):
        """Test that color constants are properly imported."""
        self.assertEqual(NES, "nes")
        self.assertEqual(SYSTEM, "system")
        self.assertEqual(VGA, "vga")

    def test_default_color_constants(self):
        """Test that default color constants are available."""
        # These should be pygame Color objects or tuples representing RGB values
        self.assertIsNotNone(YELLOW)
        self.assertIsNotNone(PURPLE)
        self.assertIsNotNone(BLUE)
        self.assertIsNotNone(GREEN)
        self.assertIsNotNone(WHITE)
        self.assertIsNotNone(BLACK)
        self.assertIsNotNone(BLACKLUCENT)
        self.assertIsNotNone(BLUELUCENT)
        self.assertIsNotNone(RED)

    def test_default_palette_instantiation(self):
        """Test Default palette instantiation."""
        default = Default()
        self.assertIsInstance(default, ColorPalette)
        self.assertIsNotNone(default.YELLOW)
        self.assertIsNotNone(default.PURPLE)
        self.assertIsNotNone(default.BLUE)
        self.assertIsNotNone(default.GREEN)
        self.assertIsNotNone(default.WHITE)
        self.assertIsNotNone(default.BLACK)
        self.assertIsNotNone(default.BLACKLUCENT)
        self.assertIsNotNone(default.BLUELUCENT)
        self.assertIsNotNone(default.RED)


class TestColorPaletteCoverage(unittest.TestCase):
    """Comprehensive test coverage for ColorPalette class."""

    def test_color_palette_initialization_with_colors(self):
        """Test ColorPalette initialization with colors list."""
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        palette = ColorPalette(colors=colors)
        
        self.assertEqual(palette._colors, colors)
        self.assertEqual(palette._size, 2)  # len(colors) - 1

    def test_color_palette_initialization_with_filename(self):
        """Test ColorPalette initialization with filename."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('glitchygames.color.palette.PaletteUtility.load_palette_from_file') as mock_load:
                mock_load.return_value = [(255, 0, 0), (0, 255, 0)]
                
                palette = ColorPalette(colors=None, filename="test")
                
                self.assertEqual(palette._colors, [(255, 0, 0), (0, 255, 0)])
                self.assertEqual(palette._size, 1)

    def test_color_palette_initialization_empty(self):
        """Test ColorPalette initialization with no colors or filename."""
        palette = ColorPalette(colors=None)
        
        self.assertIsNone(palette._colors)
        self.assertEqual(palette._size, 0)

    def test_get_color_with_valid_index(self):
        """Test get_color with valid palette index."""
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        palette = ColorPalette(colors=colors)
        
        result = palette.get_color(1)
        self.assertEqual(result, (0, 255, 0))

    def test_get_color_with_invalid_index(self):
        """Test get_color with invalid palette index."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors=colors)
        
        result = palette.get_color(5)  # Index out of range
        self.assertIsNone(result)

    def test_get_color_with_no_colors(self):
        """Test get_color when no colors are set."""
        palette = ColorPalette(colors=None)
        
        result = palette.get_color(0)
        self.assertEqual(result, (255, 0, 255))  # Magenta fallback

    def test_get_color_with_empty_colors(self):
        """Test get_color with empty colors list."""
        palette = ColorPalette(colors=[])
        
        result = palette.get_color(0)
        self.assertEqual(result, (255, 0, 255))  # Magenta fallback

    def test_set_color_with_valid_index(self):
        """Test set_color with valid palette index."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors=colors)
        
        palette.set_color(0, (128, 128, 128))
        self.assertEqual(palette._colors[0], (128, 128, 128))

    def test_set_color_with_invalid_index(self):
        """Test set_color with invalid palette index (should append)."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors=colors)
        
        palette.set_color(5, (128, 128, 128))
        self.assertEqual(palette._colors[2], (128, 128, 128))
        self.assertEqual(len(palette._colors), 3)


class TestPaletteUtilityCoverage(unittest.TestCase):
    """Comprehensive test coverage for PaletteUtility class."""

    def test_load_palette_from_config(self):
        """Test load_palette_from_config method."""
        config = configparser.ConfigParser()
        config['default'] = {'colors': '2'}
        config['0'] = {'red': '255', 'green': '0', 'blue': '0', 'alpha': '255'}
        config['1'] = {'red': '0', 'green': '255', 'blue': '0', 'alpha': '128'}
        
        colors = PaletteUtility.load_palette_from_config(config)
        
        self.assertEqual(len(colors), 2)
        self.assertEqual(colors[0].r, 255)
        self.assertEqual(colors[0].g, 0)
        self.assertEqual(colors[0].b, 0)
        self.assertEqual(colors[0].a, 255)
        self.assertEqual(colors[1].r, 0)
        self.assertEqual(colors[1].g, 255)
        self.assertEqual(colors[1].b, 0)
        self.assertEqual(colors[1].a, 128)

    def test_load_palette_from_config_without_alpha(self):
        """Test load_palette_from_config method without alpha values."""
        config = configparser.ConfigParser()
        config['default'] = {'colors': '1'}
        config['0'] = {'red': '128', 'green': '64', 'blue': '192'}
        
        colors = PaletteUtility.load_palette_from_config(config)
        
        self.assertEqual(len(colors), 1)
        self.assertEqual(colors[0].r, 128)
        self.assertEqual(colors[0].g, 64)
        self.assertEqual(colors[0].b, 192)
        self.assertEqual(colors[0].a, 255)  # Default alpha

    def test_load_palette_from_file(self):
        """Test load_palette_from_file method."""
        config_content = """[default]
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
alpha = 128
"""
        
        with patch('pathlib.Path.open', mock_open(read_data=config_content)):
            with patch('configparser.ConfigParser.read_file'):
                with patch('glitchygames.color.palette.PaletteUtility.load_palette_from_config') as mock_load:
                    mock_load.return_value = [(255, 0, 0), (0, 255, 0)]
                    
                    result = PaletteUtility.load_palette_from_file(Path("test.palette"))
                    mock_load.assert_called_once()

    def test_write_palette_to_file(self):
        """Test write_palette_to_file method."""
        config_data = {"test": "data"}
        output_file = Path("test_output.palette")
        
        with patch('pathlib.Path.open', mock_open()) as mock_file:
            PaletteUtility.write_palette_to_file(config_data, output_file)
            
            # The method calls Path.open(Path(output_file), "w"), so we need to check the call
            # The actual call is Path.open(Path(output_file), "w"), so we need to check for the Path object
            mock_file.assert_called_once_with(output_file, 'w')
            mock_file().write.assert_called_once_with(json.dumps(config_data))

    def test_parse_rgb_data_in_file(self):
        """Test parse_rgb_data_in_file method."""
        rgb_content = "255,0,0\n0,255,0\n0,0,255\n255,0,0\n"  # Last line is duplicate
        
        with patch('builtins.open', mock_open(read_data=rgb_content)):
            with patch('pathlib.Path.open', mock_open(read_data=rgb_content)):
                colors = PaletteUtility.parse_rgb_data_in_file(Path("test_rgb.txt"))
                
                self.assertEqual(len(colors), 3)  # Duplicate should be removed
                self.assertEqual(colors[0].r, 255)
                self.assertEqual(colors[0].g, 0)
                self.assertEqual(colors[0].b, 0)
                self.assertEqual(colors[1].r, 0)
                self.assertEqual(colors[1].g, 255)
                self.assertEqual(colors[1].b, 0)
                self.assertEqual(colors[2].r, 0)
                self.assertEqual(colors[2].g, 0)
                self.assertEqual(colors[2].b, 255)

    def test_parse_rgb_data_in_file_with_alpha(self):
        """Test parse_rgb_data_in_file method with alpha values."""
        rgb_content = "255,0,0,128\n0,255,0,64\n"
        
        with patch('builtins.open', mock_open(read_data=rgb_content)):
            with patch('pathlib.Path.open', mock_open(read_data=rgb_content)):
                colors = PaletteUtility.parse_rgb_data_in_file(Path("test_rgb.txt"))
                
                self.assertEqual(len(colors), 2)
                self.assertEqual(colors[0].r, 255)
                self.assertEqual(colors[0].g, 0)
                self.assertEqual(colors[0].b, 0)
                self.assertEqual(colors[0].a, 128)
                self.assertEqual(colors[1].r, 0)
                self.assertEqual(colors[1].g, 255)
                self.assertEqual(colors[1].b, 0)
                self.assertEqual(colors[1].a, 64)

    def test_create_palette_data(self):
        """Test create_palette_data method."""
        from pygame import Color
        colors = [Color(255, 0, 0, 255), Color(0, 255, 0, 128)]
        
        config = PaletteUtility.create_palette_data(colors)
        
        self.assertEqual(config['default']['colors'], '2')
        self.assertEqual(config['0']['red'], '255')
        self.assertEqual(config['0']['green'], '0')
        self.assertEqual(config['0']['blue'], '0')
        self.assertEqual(config['0']['alpha'], '255')
        self.assertEqual(config['1']['red'], '0')
        self.assertEqual(config['1']['green'], '255')
        self.assertEqual(config['1']['blue'], '0')
        self.assertEqual(config['1']['alpha'], '128')


class TestSystemPaletteCoverage(unittest.TestCase):
    """Test coverage for System palette class."""

    def test_system_palette_initialization(self):
        """Test System palette initialization."""
        with patch('glitchygames.color.palette.ColorPalette.__init__') as mock_init:
            with patch('glitchygames.color.palette.ColorPalette.get_color') as mock_get_color:
                mock_init.return_value = None
                mock_get_color.return_value = (0, 0, 0)  # Mock color return
                
                system = System()
                
                # Manually set the _size attribute that would be set by parent __init__
                system._size = 0
                
                mock_init.assert_called_once_with(filename=SYSTEM)
                self.assertIsInstance(system, ColorPalette)

    def test_system_palette_colors(self):
        """Test System palette color properties."""
        with patch('glitchygames.color.palette.ColorPalette.__init__') as mock_init:
            with patch('glitchygames.color.palette.ColorPalette.get_color') as mock_get_color:
                mock_get_color.return_value = (255, 0, 0)
                mock_init.return_value = None
                
                system = System()
                
                # Test that color properties are set
                self.assertIsInstance(system.BLACK, tuple)
                self.assertIsInstance(system.MAROON, tuple)
                self.assertIsInstance(system.GREEN, tuple)
                self.assertIsInstance(system.OLIVE, tuple)
                self.assertIsInstance(system.NAVY, tuple)
                self.assertIsInstance(system.PURPLE, tuple)
                self.assertIsInstance(system.TEAL, tuple)
                self.assertIsInstance(system.SILVER, tuple)
                self.assertIsInstance(system.GREY, tuple)
                self.assertIsInstance(system.RED, tuple)
                self.assertIsInstance(system.LIME, tuple)
                self.assertIsInstance(system.YELLOW, tuple)
                self.assertIsInstance(system.BLUE, tuple)
                self.assertIsInstance(system.MAGENTA, tuple)
                self.assertIsInstance(system.CYAN, tuple)
                self.assertIsInstance(system.WHITE, tuple)


class TestVgaPaletteCoverage(unittest.TestCase):
    """Test coverage for Vga palette class."""

    def test_vga_palette_initialization(self):
        """Test Vga palette initialization."""
        with patch('glitchygames.color.palette.ColorPalette.__init__') as mock_init:
            mock_init.return_value = None
            
            vga = Vga()
            
            mock_init.assert_called_once_with(filename=VGA)
            self.assertIsInstance(vga, ColorPalette)


class TestColorPaletteEdgeCasesCoverage(unittest.TestCase):
    """Edge cases and error handling for Color/Palette module."""

    def test_color_palette_file_not_found(self):
        """Test ColorPalette when palette file is not found."""
        with patch('pathlib.Path.exists', return_value=False):
            palette = ColorPalette(colors=None, filename="nonexistent")
            
            self.assertIsNone(palette._colors)
            self.assertEqual(palette._size, 0)

    def test_get_color_boundary_conditions(self):
        """Test get_color with boundary conditions."""
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        palette = ColorPalette(colors=colors)
        
        # Test exact boundary
        result = palette.get_color(2)  # Last valid index
        self.assertEqual(result, (0, 0, 255))
        
        # Test just beyond boundary
        result = palette.get_color(3)  # First invalid index
        self.assertIsNone(result)

    def test_set_color_boundary_conditions(self):
        """Test set_color with boundary conditions."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors=colors)
        
        # Test exact boundary - index 0 should be within _size (1)
        palette.set_color(0, (128, 128, 128))  # Last valid index
        self.assertEqual(palette._colors[0], (128, 128, 128))
        
        # Test beyond boundary - should append
        palette.set_color(1, (64, 64, 64))  # Beyond current size
        self.assertEqual(palette._colors[2], (64, 64, 64))  # Appends at index 2
        self.assertEqual(len(palette._colors), 3)

    def test_parse_rgb_data_with_empty_file(self):
        """Test parse_rgb_data_in_file with empty file."""
        with patch('builtins.open', mock_open(read_data="")):
            with patch('pathlib.Path.open', mock_open(read_data="")):
                colors = PaletteUtility.parse_rgb_data_in_file(Path("empty.txt"))
                
                self.assertEqual(len(colors), 0)

    def test_parse_rgb_data_with_malformed_line(self):
        """Test parse_rgb_data_in_file with malformed data."""
        rgb_content = "255,0,0\ninvalid_line\n0,255,0\n"
        
        with patch('builtins.open', mock_open(read_data=rgb_content)):
            with patch('pathlib.Path.open', mock_open(read_data=rgb_content)):
                # This should raise a ValueError due to invalid int conversion
                with self.assertRaises(ValueError):
                    PaletteUtility.parse_rgb_data_in_file(Path("malformed.txt"))

    def test_create_palette_data_with_empty_list(self):
        """Test create_palette_data with empty colors list."""
        colors = []
        config = PaletteUtility.create_palette_data(colors)
        
        self.assertEqual(config['default']['colors'], '0')
        self.assertEqual(len(config.sections()), 1)  # Only 'default' section

    def test_color_palette_with_none_colors_and_filename(self):
        """Test ColorPalette with both colors=None and filename."""
        with patch('pathlib.Path.exists', return_value=True):
            with patch('glitchygames.color.palette.PaletteUtility.load_palette_from_file') as mock_load:
                mock_load.return_value = [(255, 0, 0)]
                
                palette = ColorPalette(colors=None, filename="test")
                
                # Should use filename since colors is None
                self.assertEqual(palette._colors, [(255, 0, 0)])
                self.assertEqual(palette._size, 0)

    def test_color_palette_with_colors_and_filename(self):
        """Test ColorPalette with both colors and filename provided."""
        colors = [(255, 0, 0), (0, 255, 0)]
        palette = ColorPalette(colors=colors, filename="test")
        
        # Should use colors since it's provided
        self.assertEqual(palette._colors, colors)
        self.assertEqual(palette._size, 1)


if __name__ == "__main__":
    unittest.main()
