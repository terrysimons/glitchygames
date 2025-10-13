"""Sprite factory and loading tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.sprites import SpriteFactory

from mocks.test_mock_factory import MockFactory


class TestSpriteFactory(unittest.TestCase):
    """Test SpriteFactory functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_get_default_sprite_path(self):
        """Test getting default sprite path."""
        path = SpriteFactory._get_default_sprite_path()
        
        self.assertIsInstance(path, str)
        self.assertTrue(path.endswith(".toml"))

    def test_determine_type_animated(self):
        """Test determining animated sprite type."""
        analysis = {
            "has_sprite_pixels": False,
            "has_animation_sections": True,
            "has_frame_sections": False
        }
        
        sprite_type = SpriteFactory._determine_type(analysis)
        self.assertEqual(sprite_type, "animated")

    def test_determine_type_static(self):
        """Test determining static sprite type."""
        analysis = {
            "has_sprite_pixels": True,
            "has_animation_sections": False,
            "has_frame_sections": False
        }
        
        sprite_type = SpriteFactory._determine_type(analysis)
        self.assertEqual(sprite_type, "static")

    def test_determine_type_error(self):
        """Test determining sprite type with error."""
        analysis = {
            "has_sprite_pixels": False,
            "has_animation_sections": False,
            "has_frame_sections": False
        }
        
        sprite_type = SpriteFactory._determine_type(analysis)
        self.assertEqual(sprite_type, "error")

    def test_save_sprite_animated(self):
        """Test saving animated sprite."""
        mock_sprite = Mock()
        mock_sprite.animations = {}  # Make it look like an AnimatedSprite
        
        with patch("glitchygames.sprites.SpriteFactory._save_animated_sprite") as mock_save:
            SpriteFactory.save_sprite(sprite=mock_sprite, filename="test.toml", file_format="toml")
            mock_save.assert_called_once()

    def test_save_sprite_static(self):
        """Test saving static sprite."""
        mock_sprite = Mock()
        # Explicitly remove animations attribute to make it look like a BitmappySprite
        # hasattr(mock_sprite, 'animations') should return False
        del mock_sprite.animations  # Remove the default animations attribute
        mock_sprite._save = Mock()  # Add _save method to mock
        
        with patch("glitchygames.sprites.SpriteFactory._save_static_sprite") as mock_save:
            SpriteFactory.save_sprite(sprite=mock_sprite, filename="test.toml", file_format="toml")
            mock_save.assert_called_once_with(mock_sprite, "test.toml", "toml")

    def test_save_static_sprite(self):
        """Test saving static sprite directly."""
        mock_sprite = Mock()
        
        with patch("glitchygames.sprites.SpriteFactory._save_static_sprite") as mock_save:
            SpriteFactory._save_static_sprite(mock_sprite, "test.toml", "toml")
            mock_save.assert_called_once()

    def test_save_animated_sprite(self):
        """Test saving animated sprite directly."""
        mock_sprite = Mock()
        
        with patch("glitchygames.sprites.SpriteFactory._save_animated_sprite") as mock_save:
            SpriteFactory._save_animated_sprite(mock_sprite, "test.toml", "toml")
            mock_save.assert_called_once()

    def test_analyze_file_with_nonexistent_file(self):
        """Test analyzing nonexistent file."""
        with self.assertRaises(FileNotFoundError):
            SpriteFactory._analyze_file("nonexistent.toml")

    def test_analyze_toml_file_animation(self):
        """Test analyzing TOML file with animation."""
        with patch("pathlib.Path.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '''
            [sprite]
            pixels = [1, 2, 3]
            
            [animations.walk]
            frames = [1, 2, 3]
            '''
            
            result = SpriteFactory._get_toml_data("test.toml")
            self.assertIn("sprite", result)
            self.assertIn("animations", result)

    def test_analyze_toml_file_basic(self):
        """Test analyzing basic TOML file."""
        with patch("pathlib.Path.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '''
            [sprite]
            pixels = [1, 2, 3]
            '''
            
            result = SpriteFactory._get_toml_data("test.toml")
            self.assertIn("sprite", result)
            self.assertNotIn("animations", result)

    def test_analyze_toml_file_empty_pixels(self):
        """Test analyzing TOML file with empty pixels."""
        with patch("pathlib.Path.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '''
            [sprite]
            pixels = []
            '''
            
            result = SpriteFactory._get_toml_data("test.toml")
            self.assertIn("sprite", result)

    def test_detect_file_format_default(self):
        """Test detecting default file format."""
        format_type = SpriteFactory._detect_file_format("test.toml")
        self.assertEqual(format_type, "toml")

    def test_detect_file_format_unknown(self):
        """Test detecting unknown file format."""
        format_type = SpriteFactory._detect_file_format("test.unknown")
        self.assertEqual(format_type, "unknown")

    def test_load_sprite_invalid_file(self):
        """Test loading sprite from invalid file."""
        with self.assertRaises(FileNotFoundError):
            SpriteFactory.load_sprite(filename="nonexistent.toml")

    def test_load_sprite_mixed_content(self):
        """Test loading sprite with mixed content."""
        with patch("glitchygames.sprites.SpriteFactory._analyze_file") as mock_analyze:
            mock_analyze.return_value = {
                "has_sprite_pixels": True,
                "has_animation_sections": True,
                "has_frame_sections": False
            }
            
            with self.assertRaises(ValueError):
                SpriteFactory.load_sprite(filename="mixed.toml")

    def test_sprite_factory_load_sprite_invalid_file(self):
        """Test SpriteFactory load_sprite with invalid file."""
        with self.assertRaises(FileNotFoundError):
            SpriteFactory.load_sprite(filename="nonexistent.toml")

    def test_sprite_factory_analyze_toml_file_with_sprite_pixels(self):
        """Test analyzing TOML file with sprite pixels."""
        with patch("pathlib.Path.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = '''
            [sprite]
            pixels = [1, 2, 3, 4, 5, 6]
            '''
            
            result = SpriteFactory._get_toml_data("test.toml")
            self.assertIn("sprite", result)
            self.assertEqual(result["sprite"]["pixels"], [1, 2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()
