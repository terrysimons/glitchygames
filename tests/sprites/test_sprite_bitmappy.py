"""Bitmappy sprite functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import BitmappySprite, SingletonBitmappySprite, FocusableSingletonBitmappySprite
from mocks.test_mock_factory import MockFactory


class TestBitmappySprite(unittest.TestCase):
    """Test BitmappySprite functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_bitmappy_sprite_initialization_with_filename(self):
        """Test BitmappySprite initialization with filename."""
        sprite = BitmappySprite(filename="test.toml")
        
        self.assertIsInstance(sprite, BitmappySprite)
        self.assertEqual(sprite.filename, "test.toml")

    def test_bitmappy_sprite_initialization_without_filename(self):
        """Test BitmappySprite initialization without filename."""
        sprite = BitmappySprite()
        
        self.assertIsInstance(sprite, BitmappySprite)
        self.assertEqual(sprite.filename, "")

    def test_bitmappy_sprite_initialization_with_focusable(self):
        """Test BitmappySprite initialization with focusable."""
        sprite = BitmappySprite(focusable=True)
        
        self.assertIsInstance(sprite, BitmappySprite)
        self.assertTrue(sprite.focusable)

    def test_bitmappy_sprite_initialization_with_zero_dimensions(self):
        """Test BitmappySprite initialization with zero dimensions."""
        sprite = BitmappySprite(x=0, y=0, width=0, height=0)
        
        self.assertEqual(sprite.width, 0)
        self.assertEqual(sprite.height, 0)

    def test_bitmappy_sprite_load_method(self):
        """Test BitmappySprite load method."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite._load_static_only') as mock_load:
            with patch('glitchygames.sprites.SpriteFactory.load_sprite') as mock_factory:
                mock_factory.side_effect = ValueError("Factory failed")
                sprite.load("test.toml")
                mock_load.assert_called_once_with("test.toml")

    def test_bitmappy_sprite_load_method_with_frame(self):
        """Test BitmappySprite load method with frame."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite._load_static_only') as mock_load:
            with patch('glitchygames.sprites.SpriteFactory.load_sprite') as mock_factory:
                mock_factory.side_effect = ValueError("Factory failed")
                sprite.load("test.toml")
                mock_load.assert_called_once_with("test.toml")

    def test_bitmappy_sprite_load_method_fallback(self):
        """Test BitmappySprite load method fallback."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite._load_static_only') as mock_load:
            with patch('glitchygames.sprites.SpriteFactory.load_sprite') as mock_factory:
                mock_factory.side_effect = ValueError("Factory failed")
                mock_load.side_effect = Exception("Load failed")
                with self.assertRaises(Exception):
                    sprite.load("test.toml")

    def test_bitmappy_sprite_save_method(self):
        """Test BitmappySprite save method."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite._save_static_only') as mock_save:
            sprite.save("test.toml")
            mock_save.assert_called_once_with("test.toml", "toml")

    def test_bitmappy_sprite_deflate_method(self):
        """Test BitmappySprite deflate method."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (255, 0, 0), 'B': (0, 255, 0), 'X': (255, 0, 255)}
            result = sprite.deflate("toml")
            self.assertIsNotNone(result)

    def test_bitmappy_sprite_deflate_method_unsupported_format(self):
        """Test BitmappySprite deflate method with unsupported format."""
        sprite = BitmappySprite()
        
        with self.assertRaises(ValueError):
            sprite.deflate("json")

    def test_bitmappy_sprite_deflate_method_too_many_colors(self):
        """Test BitmappySprite deflate method with too many colors."""
        sprite = BitmappySprite()
        # Create sprite with too many colors
        sprite.pixels = [(i, i, i) for i in range(100)]
        
        with self.assertRaises(ValueError):
            sprite.deflate("toml")

    def test_bitmappy_sprite_deflate_pads_and_truncates_pixels(self):
        """Test BitmappySprite deflate method padding and truncating pixels."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (255, 0, 0), 'B': (0, 255, 0), 'C': (0, 0, 255), 'X': (255, 0, 255)}
            result = sprite.deflate("toml")
            self.assertIsNotNone(result)

    def test_bitmappy_sprite_deflate_dangerous_char_replacement(self):
        """Test BitmappySprite deflate method dangerous character replacement."""
        sprite = BitmappySprite()
        sprite.pixels = [(1, 1, 1)]  # Dangerous character
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (1, 1, 1), 'X': (255, 0, 255)}
            result = sprite.deflate("toml")
            self.assertIsNotNone(result)

    def test_bitmappy_sprite_deflate_missing_color_in_map(self):
        """Test BitmappySprite deflate method with missing color in map."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (255, 0, 0), 'X': (255, 0, 255)}  # Missing second color
            result = sprite.deflate("toml")
            self.assertIsNotNone(result)

    def test_bitmappy_sprite_inflate_method(self):
        """Test BitmappySprite inflate method."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite._inflate_toml') as mock_inflate:
            mock_inflate.return_value = {'pixels': [(255, 0, 0)]}
            result = sprite.inflate("test.toml")
            self.assertIsNotNone(result)

    def test_bitmappy_sprite_save_static_only_method(self):
        """Test BitmappySprite save_static_only method."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite.deflate') as mock_deflate:
            mock_deflate.return_value = {'sprite': {'pixels': []}}
            with patch('pathlib.Path.open') as mock_open:
                sprite._save_static_only("test.toml")
                mock_open.assert_called_once()

    def test_bitmappy_sprite_save_static_only_method_unsupported_format(self):
        """Test BitmappySprite save_static_only method with unsupported format."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite.deflate') as mock_deflate:
            mock_deflate.side_effect = ValueError("Unsupported format: xml")
            with self.assertRaises(ValueError):
                sprite._save_static_only("test.xml")

    def test_bitmappy_sprite_create_toml_config_coverage(self):
        """Test BitmappySprite create_toml_config coverage."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (255, 0, 0), 'B': (0, 255, 0), 'X': (255, 0, 255)}
            result = sprite._create_toml_config()
            self.assertIn('sprite', result)

    def test_bitmappy_sprite_process_pixel_rows_missing_color(self):
        """Test BitmappySprite process_pixel_rows with missing color."""
        sprite = BitmappySprite(width=2, height=2)  # 2x2 = 4 pixels
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # 4 pixels
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (255, 0, 0), 'X': (255, 0, 255)}  # Missing second color
            color_map = mock_color_map.return_value
            result = sprite._process_pixel_rows(color_map)
            self.assertIsNotNone(result)

    def test_bitmappy_sprite_save_static_only_unsupported_format_error(self):
        """Test BitmappySprite save_static_only with unsupported format error."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite.deflate') as mock_deflate:
            mock_deflate.side_effect = ValueError("Unsupported format: xml")
            with self.assertRaises(ValueError):
                sprite._save_static_only("test.xml")

    def test_bitmappy_sprite_save_static_only_method_unsupported_format(self):
        """Test BitmappySprite save_static_only method with unsupported format."""
        sprite = BitmappySprite()
        
        with patch('glitchygames.sprites.BitmappySprite.deflate') as mock_deflate:
            mock_deflate.side_effect = ValueError("Unsupported format: json")
            with self.assertRaises(ValueError):
                sprite._save_static_only("test.json")

    def test_get_pixel_string_method(self):
        """Test get_pixel_string method."""
        sprite = BitmappySprite(width=2, height=2)  # 2x2 = 4 pixels
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # 4 pixels
        
        with patch('glitchygames.sprites.BitmappySprite._create_color_map') as mock_color_map:
            mock_color_map.return_value = {'A': (255, 0, 0), 'B': (0, 255, 0), 'X': (255, 0, 255)}
            result = sprite._get_pixel_string()
            self.assertIsNotNone(result)

    def test_get_pixel_string_method_no_pixels(self):
        """Test get_pixel_string method with no pixels."""
        sprite = BitmappySprite()
        sprite.pixels = []
        
        result = sprite._get_pixel_string()
        self.assertEqual(result, "")

    def test_get_color_map_method(self):
        """Test get_color_map method."""
        sprite = BitmappySprite()
        sprite.pixels = [(255, 0, 0), (0, 255, 0)]
        
        result = sprite._get_color_map()
        self.assertIsInstance(result, dict)

    def test_get_color_map_method_no_pixels(self):
        """Test get_color_map method with no pixels."""
        sprite = BitmappySprite()
        sprite.pixels = []
        
        result = sprite._get_color_map()
        self.assertEqual(result, {})


class TestSingleton(unittest.TestCase):
    """Test Singleton functionality."""

    def test_singleton_creation(self):
        """Test singleton creation."""
        from glitchygames.sprites import Singleton
        
        singleton = Singleton()
        self.assertIsInstance(singleton, Singleton)


class TestSingletonBitmappySprite(unittest.TestCase):
    """Test SingletonBitmappySprite functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_singleton_bitmappy_sprite_creation(self):
        """Test SingletonBitmappySprite creation."""
        sprite = SingletonBitmappySprite()
        
        self.assertIsInstance(sprite, SingletonBitmappySprite)
        # Test that it has BitmappySprite attributes instead of isinstance check
        # (Centralized mocks interfere with isinstance() checks)
        self.assertTrue(hasattr(sprite, 'filename'))
        self.assertTrue(hasattr(sprite, 'focusable'))
        self.assertTrue(hasattr(sprite, 'pixels'))
        self.assertTrue(hasattr(sprite, 'pixels_across'))
        self.assertTrue(hasattr(sprite, 'pixels_tall'))


class TestFocusableSingletonBitmappySprite(unittest.TestCase):
    """Test FocusableSingletonBitmappySprite functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_focusable_singleton_bitmappy_sprite_creation(self):
        """Test FocusableSingletonBitmappySprite creation."""
        sprite = FocusableSingletonBitmappySprite()
        
        self.assertIsInstance(sprite, FocusableSingletonBitmappySprite)
        # Test that it has BitmappySprite attributes instead of isinstance check
        # (Centralized mocks interfere with isinstance() checks)
        self.assertTrue(hasattr(sprite, 'filename'))
        self.assertTrue(hasattr(sprite, 'focusable'))
        self.assertTrue(hasattr(sprite, 'pixels'))
        self.assertTrue(hasattr(sprite, 'pixels_across'))
        self.assertTrue(hasattr(sprite, 'pixels_tall'))
        self.assertTrue(sprite.focusable)


if __name__ == "__main__":
    unittest.main()
