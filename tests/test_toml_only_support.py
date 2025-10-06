"""Test suite for TOML-only file format support.

This module tests that the sprite loading system now only supports TOML format
and properly rejects YAML/INI formats after the cleanup.
"""

import tempfile
import unittest
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites import BitmappySprite, SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame


class TestTOMLOnlySupport(unittest.TestCase):
    """Test that only TOML format is supported after cleanup."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    @staticmethod
    def test_file_format_detection_toml_only():
        """Test that file format detection only supports TOML."""
        # Test TOML detection
        toml_format = SpriteFactory._detect_file_format("test.toml")
        assert toml_format == "toml"

        # Test that YAML/INI are not detected
        yaml_format = SpriteFactory._detect_file_format("test.yaml")
        assert yaml_format == "toml"  # Should default to TOML

        ini_format = SpriteFactory._detect_file_format("test.ini")
        assert ini_format == "toml"  # Should default to TOML

    def test_static_sprite_toml_save_load(self):
        """Test that static sprites can save and load in TOML format."""
        # Create a test sprite
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name="test_toml")
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        # Save to TOML
        toml_file = self.temp_path / "test_static.toml"
        sprite.save(str(toml_file), "toml")

        # Verify file was created
        assert toml_file.exists()
        content = toml_file.read_text()

        # Check TOML structure
        assert "[sprite]" in content
        assert 'name = "test_toml"' in content
        # TOML uses individual color sections like [colors."."]
        assert "red =" in content  # Should have color definitions

        # Load it back
        loaded_sprite = SpriteFactory.load_sprite(filename=str(toml_file))
        assert loaded_sprite.name == "test_toml"
        # Check that the sprite was loaded correctly
        assert hasattr(loaded_sprite, "image")
        assert loaded_sprite.image.get_size() == (2, 2)

    def test_animated_sprite_toml_save_load(self):
        """Test that animated sprites can save and load in TOML format."""
        # Create an animated sprite
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_toml"

        # Create frames
        frame1 = SpriteFrame(pygame.Surface((2, 2)))
        frame1.set_pixel_data([(255, 0, 0)] * 4)  # Red frame

        frame2 = SpriteFrame(pygame.Surface((2, 2)))
        frame2.set_pixel_data([(0, 255, 0)] * 4)  # Green frame

        animated_sprite.add_animation("test_anim", [frame1, frame2])

        # Save to TOML
        toml_file = self.temp_path / "test_animated.toml"
        animated_sprite.save(str(toml_file), "toml")

        # Verify file was created
        assert toml_file.exists()
        content = toml_file.read_text()

        # Check TOML structure
        assert "[sprite]" in content
        assert 'name = "test_animated_toml"' in content
        assert "[animation]" in content
        # TOML uses individual color sections like [colors."."]
        assert "red =" in content  # Should have color definitions

        # Load it back
        loaded_sprite = SpriteFactory.load_sprite(filename=str(toml_file))
        assert loaded_sprite.name == "test_animated_toml"
        assert "test_anim" in loaded_sprite.animations

    def test_yaml_format_rejected(self):
        """Test that YAML format is properly rejected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name="test")
        sprite.pixels = [(255, 0, 0)] * 4
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        yaml_file = self.temp_path / "test.yaml"

        # Should raise error when trying to save as YAML
        with pytest.raises(ValueError, match="Unsupported format"):
            sprite.save(str(yaml_file), "yaml")

    def test_ini_format_rejected(self):
        """Test that INI format is properly rejected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name="test")
        sprite.pixels = [(255, 0, 0)] * 4
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        ini_file = self.temp_path / "test.ini"

        # Should raise error when trying to save as INI
        with pytest.raises(ValueError, match="Unsupported format"):
            sprite.save(str(ini_file), "ini")

    def test_animated_sprite_yaml_rejected(self):
        """Test that animated sprites reject YAML format."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test"

        frame = SpriteFrame(pygame.Surface((2, 2)))
        frame.set_pixel_data([(255, 0, 0)] * 4)
        animated_sprite.add_animation("test_anim", [frame])

        yaml_file = self.temp_path / "test.yaml"

        # Should raise error when trying to save as YAML
        with pytest.raises(ValueError, match="Unsupported format"):
            animated_sprite.save(str(yaml_file), "yaml")

    def test_animated_sprite_ini_rejected(self):
        """Test that animated sprites reject INI format."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test"

        frame = SpriteFrame(pygame.Surface((2, 2)))
        frame.set_pixel_data([(255, 0, 0)] * 4)
        animated_sprite.add_animation("test_anim", [frame])

        ini_file = self.temp_path / "test.ini"

        # Should raise error when trying to save as INI
        with pytest.raises(ValueError, match="Unsupported format"):
            animated_sprite.save(str(ini_file), "ini")

    def test_default_format_is_toml(self):
        """Test that default file format is TOML."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name="test")
        sprite.pixels = [(255, 0, 0)] * 4
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        toml_file = self.temp_path / "test.toml"

        # Should work with default format (TOML)
        sprite.save(str(toml_file))
        assert toml_file.exists()

    @staticmethod
    def test_unsupported_format_error_message():
        """Test that unsupported format error messages are clear."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name="test")
        sprite.pixels = [(255, 0, 0)] * 4
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        # Test error message for unsupported format
        with pytest.raises(ValueError, match="Unsupported format"):
            sprite.save("test.json", "json")


if __name__ == "__main__":
    unittest.main()
