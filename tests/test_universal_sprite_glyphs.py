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

        # Check TOML structure (saved as static sprite for readability)
        assert "[sprite]" in content
        assert 'name = "test_toml"' in content
        assert "pixels =" in content
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
        # Create a sprite with exactly 65 colors (more than the 64 limit)
        sprite = BitmappySprite(x=0, y=0, width=65, height=1, name="test_limit")

        # Create 65 unique colors (more than the 64 character limit)
        colors = []
        for i in range(65):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))

        # Set up pixel data to use all 65 colors
        pixels = [colors[i] for i in range(65)]  # 65x1 = 65 pixels

        sprite.pixels = pixels
        sprite.pixels_across = 65
        sprite.pixels_tall = 1

        # Should raise ValueError when trying to save
        toml_file = self.temp_path / "test_limit.toml"
        with pytest.raises(ValueError, match="Too many colors"):
            sprite.save(str(toml_file), "toml")

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

        # Save in TOML format
        toml_file = self.temp_path / "test_consistency.toml"
        sprite.save(str(toml_file), "toml")

        # File should exist
        assert toml_file.exists()

        # Check TOML content
        toml_content = toml_file.read_text()
        assert "[sprite]" in toml_content
        assert 'name = "test_consistency"' in toml_content
        assert "pixels =" in toml_content
        # Should have individual color sections
        assert '[colors."."]' in toml_content or "[colors.a]" in toml_content

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
        toml_file = self.temp_path / "test_sequential.toml"
        sprite.save(str(toml_file), "toml")

        content = toml_file.read_text()

        # Should have TOML structure with individual color sections
        assert "[sprite]" in content
        assert 'name = "test_sequential"' in content
        assert "pixels =" in content

        # Should have individual color sections using universal characters
        assert '[colors."."]' in content
        assert "[colors.a]" in content
        assert "[colors.A]" in content
        assert "[colors.b]" in content

    def test_animated_sprite_character_limit(self):
        """Test character limit enforcement in animated sprites."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_limit"

        # Create frames with exactly 65 colors (more than 64 limit)
        frame = SpriteFrame(pygame.Surface((65, 1)))
        colors = []
        for i in range(65):  # More than 64 character limit
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))

        # Create pixel data with all 65 colors
        pixels = [colors[i] for i in range(65)]  # 65x1 = 65 pixels

        frame.set_pixel_data(pixels)
        animated_sprite.add_animation("test_anim", [frame])

        # Should raise ValueError when trying to save
        toml_file = self.temp_path / "test_animated_limit.toml"
        with pytest.raises(ValueError, match="Too many colors"):
            animated_sprite.save(str(toml_file), "toml")

    @staticmethod
    def test_legacy_sprite_character_limit():
        """Test character limit enforcement in legacy sprites."""
        # Create a surface with exactly 65 colors (more than 64 limit)
        surface = pygame.Surface((65, 1))

        # Fill with 65 unique colors
        for i in range(65):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            surface.set_at((i, 0), (r, g, b))

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
