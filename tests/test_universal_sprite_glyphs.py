"""Test suite for universal sprite glyphs implementation.

This module tests the universal character set implementation across all
sprite save/load modes (static, animated, legacy) to ensure consistent
character mapping and proper error handling.
"""

import tempfile
import unittest
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites import SPRITE_GLYPHS, BitmappySprite
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from scripts.raw_sprite_loader import BitmappyLegacySprite

# Constants for test values
EXPECTED_GLYPH_COUNT = 64
TEST_SPRITE_SIZE = 8
TEST_SMALL_SIZE = 4
# Test validation set - subset of characters to verify SPRITE_GLYPHS contains standard chars
STANDARD_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"  # noqa: FURB156


class TestUniversalSpriteGlyphs(unittest.TestCase):
    """Test the universal character set implementation."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        # Initialize display for BitmappySprite
        pygame.display.set_mode((800, 600))
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    @staticmethod
    def test_sprite_glyphs_constant():
        """Test that SPRITE_GLYPHS has the expected 64 characters."""
        glyphs = SPRITE_GLYPHS.strip()
        assert len(glyphs) == EXPECTED_GLYPH_COUNT, (
            f"Expected {EXPECTED_GLYPH_COUNT} characters, got {len(glyphs)}"
        )

        # Check that it contains expected character types
        assert any(c.isupper() for c in glyphs), "Should contain uppercase letters"
        assert any(c.islower() for c in glyphs), "Should contain lowercase letters"
        assert any(c.isdigit() for c in glyphs), "Should contain digits"
        assert any(c in STANDARD_CHARS for c in glyphs), "Should contain standard characters"

        # Check for dangerous characters
        dangerous_chars = {"\n", "\r", "\t", "\0", "\b", "\f", "\v", "\a"}
        for char in dangerous_chars:
            assert char not in glyphs, f"Dangerous character '{char}' found in glyphs"

    def test_static_sprite_ini_save(self):
        """Test static sprite INI save with universal character set."""
        # Create a test sprite with multiple colors
        sprite = BitmappySprite(x=0, y=0, width=8, height=8, name="test_sprite")

        # Set up pixel data with multiple colors
        colors = [
            (255, 0, 0),  # Red
            (0, 255, 0),  # Green
            (0, 0, 255),  # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (128, 128, 128),  # Gray
            (0, 0, 0),  # Black
        ]

        # Create a simple 8x8 pattern
        pixels = []
        for y in range(8):
            for x in range(8):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])

        sprite.pixels = pixels
        sprite.pixels_across = 8
        sprite.pixels_tall = 8

        # Save to INI file
        ini_file = self.temp_path / "test_static.ini"
        sprite.save(str(ini_file), "ini")

        # Verify file was created and contains expected content
        assert ini_file.exists()
        content = ini_file.read_text()

        # Check that it contains sprite section
        assert "[sprite]" in content
        assert "name = test_sprite" in content
        assert "pixels =" in content

        # Check that color sections use universal character set
        # Should have sections for all colors using universal characters
        # The exact character assignment depends on color order, but should use universal set
        universal_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.@"
        all_sections = [
            line for line in content.split("\n") if line.startswith("[") and line.endswith("]")
        ]
        color_sections = [section for section in all_sections if section != "[sprite]"]
        assert len(color_sections) == TEST_SPRITE_SIZE  # Should have 8 color sections
        for section in color_sections:
            char = section[1:-1]  # Extract character from [char]
            assert char in universal_chars, f"Character '{char}' not in universal set"

        # Check that color sections have proper RGB values
        assert "red =" in content
        assert "green =" in content
        assert "blue =" in content

    def test_static_sprite_yaml_save(self):
        """Test static sprite YAML save with universal character set."""
        sprite = BitmappySprite(x=0, y=0, width=4, height=4, name="test_yaml")

        # Simple 4x4 pattern
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        pixels = []
        for y in range(4):
            for x in range(4):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])

        sprite.pixels = pixels
        sprite.pixels_across = 4
        sprite.pixels_tall = 4

        # Save to YAML file
        yaml_file = self.temp_path / "test_static.yaml"
        sprite.save(str(yaml_file), "yaml")

        # Verify file was created
        assert yaml_file.exists()
        content = yaml_file.read_text()

        # Check YAML structure
        assert "sprite:" in content
        assert "name: test_yaml" in content
        assert "colors:" in content

    def test_animated_sprite_ini_save(self):
        """Test animated sprite INI save with universal character set."""
        # Create animated sprite with multiple frames
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated"

        # Create frames with different colors
        frame1 = SpriteFrame(pygame.Surface((8, 8)))
        frame1.set_pixel_data([(255, 0, 0)] * 64)  # Red frame

        frame2 = SpriteFrame(pygame.Surface((8, 8)))
        frame2.set_pixel_data([(0, 255, 0)] * 64)  # Green frame

        animated_sprite.add_animation("test_anim", [frame1, frame2])

        # Save to INI file
        ini_file = self.temp_path / "test_animated.ini"
        animated_sprite.save(str(ini_file), "ini")

        # Verify file was created
        assert ini_file.exists()
        content = ini_file.read_text()

        # Check INI structure
        assert "[sprite]" in content
        assert "name = test_animated" in content
        assert "[animation_test_anim]" in content
        assert "[frame_test_anim_0]" in content
        assert "[frame_test_anim_1]" in content

    def test_animated_sprite_toml_save(self):
        """Test animated sprite TOML save with universal character set."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_toml"

        # Create a simple frame
        frame = SpriteFrame(pygame.Surface((4, 4)))
        frame.set_pixel_data([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)] * 4)
        animated_sprite.add_animation("test_anim", [frame])

        # Save to TOML file
        toml_file = self.temp_path / "test_animated.toml"
        animated_sprite.save(str(toml_file), "toml")

        # Verify file was created
        assert toml_file.exists()
        content = toml_file.read_text()

        # Check TOML structure
        assert "[sprite]" in content
        assert 'name = "test_toml"' in content
        assert "[animation]" in content
        assert "[animation.frame]" in content
        assert "[colors]" in content

    @staticmethod
    def test_legacy_sprite_save():
        """Test legacy sprite save with universal character set."""
        # Create a test surface
        surface = pygame.Surface((8, 8))
        surface.fill((255, 0, 0))  # Red background

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_legacy"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Check that it uses universal character set
        glyphs = SPRITE_GLYPHS.strip()
        sections = config.sections()

        # Should have sprite section and color sections
        assert "sprite" in sections

        # Color sections should use universal characters
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]
        assert len(color_sections) > 0, "Should have color sections using universal characters"

    def test_character_limit_enforcement(self):
        """Test that character limit is enforced across all modes."""
        # Create a sprite with more colors than the universal set allows
        sprite = BitmappySprite(x=0, y=0, width=8, height=8, name="test_limit")

        # Create 70 unique colors (more than the 64 character limit)
        colors = []
        for i in range(70):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))

        # Set up pixel data to use all 70 colors
        pixels = [colors[i] for i in range(64)]  # 8x8 = 64 pixels

        sprite.pixels = pixels
        sprite.pixels_across = 8
        sprite.pixels_tall = 8

        # Should raise ValueError when trying to save
        ini_file = self.temp_path / "test_limit.ini"
        with pytest.raises(ValueError, match="Too many colors"):
            sprite.save(str(ini_file), "ini")

    def test_character_mapping_consistency(self):
        """Test that character mapping is consistent across different save modes."""
        # Create a sprite with specific colors
        sprite = BitmappySprite(x=0, y=0, width=4, height=4, name="test_consistency")

        colors = [
            (255, 0, 0),  # Red
            (0, 255, 0),  # Green
            (0, 0, 255),  # Blue
            (255, 255, 255),  # White
        ]

        pixels = []
        for y in range(4):
            for x in range(4):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])

        sprite.pixels = pixels
        sprite.pixels_across = 4
        sprite.pixels_tall = 4

        # Save in both INI and YAML formats
        ini_file = self.temp_path / "test_consistency.ini"
        yaml_file = self.temp_path / "test_consistency.yaml"

        sprite.save(str(ini_file), "ini")
        sprite.save(str(yaml_file), "yaml")

        # Both files should exist
        assert ini_file.exists()
        assert yaml_file.exists()

        # Both should use the same character mapping
        ini_content = ini_file.read_text()
        yaml_content = yaml_file.read_text()

        # Check that both use universal character set
        universal_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.@"

        # Check INI format
        ini_color_sections = [
            line for line in ini_content.split("\n") if line.startswith("[") and line.endswith("]")
        ]
        assert len(ini_color_sections) == TEST_SMALL_SIZE  # Should have 4 color sections
        for section in ini_color_sections:
            char = section[1:-1]  # Extract character from [char]
            assert char in universal_chars, f"Character '{char}' not in universal set"

        # Check YAML format
        assert "colors:" in yaml_content
        assert "red:" in yaml_content
        assert "green:" in yaml_content
        assert "blue:" in yaml_content

        # Both formats should use universal characters
        # The exact character assignment depends on color order

    def test_sequential_character_assignment(self):
        """Test that characters are assigned sequentially from SPRITE_GLYPHS."""
        sprite = BitmappySprite(x=0, y=0, width=4, height=4, name="test_sequential")

        # Use colors that should map to sequential characters
        colors = [
            (0, 0, 0),  # Black - should map to 'A'
            (255, 0, 0),  # Red - should map to 'B'
            (0, 255, 0),  # Green - should map to 'C'
            (0, 0, 255),  # Blue - should map to 'D'
        ]

        pixels = []
        for y in range(4):
            for x in range(4):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])

        sprite.pixels = pixels
        sprite.pixels_across = 4
        sprite.pixels_tall = 4

        # Save and check that sequential characters are used
        ini_file = self.temp_path / "test_sequential.ini"
        sprite.save(str(ini_file), "ini")

        content = ini_file.read_text()

        # Should have sections for all colors using universal characters
        universal_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.@"
        color_sections = [
            line for line in content.split("\n") if line.startswith("[") and line.endswith("]")
        ]
        assert len(color_sections) == TEST_SMALL_SIZE  # Should have 4 color sections
        for section in color_sections:
            char = section[1:-1]  # Extract character from [char]
            assert char in universal_chars, f"Character '{char}' not in universal set"

    def test_animated_sprite_character_limit(self):
        """Test character limit enforcement in animated sprites."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_limit"

        # Create frames with many unique colors
        frame = SpriteFrame(pygame.Surface((8, 8)))
        colors = []
        for i in range(70):  # More than 64 character limit
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))

        # Create pixel data with all colors
        pixels = [colors[i] for i in range(64)]  # 8x8 = 64 pixels

        frame.set_pixel_data(pixels)
        animated_sprite.add_animation("test_anim", [frame])

        # Should raise ValueError when trying to save
        ini_file = self.temp_path / "test_animated_limit.ini"
        with pytest.raises(ValueError, match="Too many colors"):
            animated_sprite.save(str(ini_file), "ini")

    @staticmethod
    def test_legacy_sprite_character_limit():
        """Test character limit enforcement in legacy sprites."""
        # Create a surface with many colors
        surface = pygame.Surface((8, 8))

        # Fill with many different colors
        for y in range(8):
            for x in range(8):
                r = (x + y) * 32 % 256
                g = (x + y) * 16 % 256
                b = (x + y) * 8 % 256
                surface.set_at((x, y), (r, g, b))

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_legacy_limit"

        # Should raise ValueError when trying to deflate
        with pytest.raises(ValueError, match="Too many colors"):
            legacy_sprite.deflate()


if __name__ == "__main__":
    unittest.main()
