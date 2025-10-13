"""Test suite for legacy sprite loader universal character set implementation.

This module tests the legacy sprite loader with the universal character set
to ensure it properly uses the new character mapping system.
"""

import tempfile
import unittest
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites import SPRITE_GLYPHS
from scripts.raw_sprite_loader import BitmappyLegacySprite
from tests.mocks.test_mock_factory import MockFactory

# Constants for test values
MAX_RGB_VALUE = 255
TEST_SMALL_SIZE = 4
TEST_MEDIUM_SIZE = 2
TEST_PATTERN_SIZE = 3
TEST_GRAYSCALE_SIZE = 4


class TestLegacySpriteGlyphs(unittest.TestCase):
    """Test legacy sprite loader universal character set implementation."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()
        
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    @staticmethod
    def test_legacy_sprite_basic_save():
        """Test basic legacy sprite save with universal character set."""
        # Create a test surface with multiple colors
        surface = pygame.Surface((4, 4))

        # Fill with different colors
        colors = [
            (255, 0, 0),  # Red
            (0, 255, 0),  # Green
            (0, 0, 255),  # Blue
            (255, 255, 255),  # White
        ]

        for y in range(4):
            for x in range(4):
                color_index = (x + y) % len(colors)
                surface.set_at((x, y), colors[color_index])

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_legacy"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Check that it uses universal character set
        glyphs = SPRITE_GLYPHS
        sections = config.sections()

        # Should have sprite section
        assert "sprite" in sections
        assert config.get("sprite", "name") == "test_legacy"

        # Color sections should use universal characters
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]
        assert len(color_sections) > 0, "Should have color sections using universal characters"

        # Check that color sections have proper RGB values
        for char in color_sections:
            assert config.has_option(char, "red")
            assert config.has_option(char, "green")
            assert config.has_option(char, "blue")

            # Values should be valid integers
            red = int(config.get(char, "red"))
            green = int(config.get(char, "green"))
            blue = int(config.get(char, "blue"))

            assert red >= 0
            assert red <= MAX_RGB_VALUE
            assert green >= 0
            assert green <= MAX_RGB_VALUE
            assert blue >= 0
            assert blue <= MAX_RGB_VALUE

    @staticmethod
    def test_legacy_sprite_character_mapping():
        """Test that legacy sprite uses correct character mapping."""
        # Create surface with specific colors
        surface = pygame.Surface((2, 2))
        surface.set_at((0, 0), (0, 0, 0))  # Black
        surface.set_at((1, 0), (255, 0, 0))  # Red
        surface.set_at((0, 1), (0, 255, 0))  # Green
        surface.set_at((1, 1), (0, 0, 255))  # Blue

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_mapping"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Check that it uses universal character set
        glyphs = SPRITE_GLYPHS
        sections = config.sections()

        # Should have 4 color sections (one for each unique color)
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]
        assert len(color_sections) == TEST_SMALL_SIZE, "Should have 4 color sections"

        # Check that universal characters are used (starting with '.')
        assert "." in color_sections  # Black should map to '.'
        assert "a" in color_sections  # Red should map to 'a'

        # Check that other colors use universal characters
        other_colors = [s for s in color_sections if s not in {".", "a"}]
        assert len(other_colors) == TEST_MEDIUM_SIZE, "Should have 2 other color sections"

        for char in other_colors:
            assert char in glyphs, f"Character '{char}' should be in universal glyphs"

    @staticmethod
    def test_legacy_sprite_character_limit():
        """Test character limit enforcement in legacy sprites."""
        # Create surface with exactly 65 colors (more than 64 limit)
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
        legacy_sprite.name = "test_limit"

        # Should raise ValueError when trying to deflate
        with pytest.raises(ValueError, match="Too many colors"):
            legacy_sprite.deflate()

    def test_legacy_sprite_single_color(self):
        """Test legacy sprite with single color."""
        # Create surface with single color
        surface = pygame.Surface((4, 4))
        surface.fill((255, 0, 0))  # All red
        surface._test_single_color = True  # Mark as single color for mock

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_single_color"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Should have only one color section
        glyphs = SPRITE_GLYPHS
        sections = config.sections()
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]

        assert len(color_sections) == 1, "Should have only one color section"

        # Should use universal character for red
        assert "." in color_sections, "Red should map to '.'"

        # Check RGB values
        red = int(config.get(".", "red"))
        green = int(config.get(".", "green"))
        blue = int(config.get(".", "blue"))

        assert red == MAX_RGB_VALUE
        assert green == 0
        assert blue == 0

    @staticmethod
    def test_legacy_sprite_pixel_data_consistency():
        """Test that pixel data is consistent with character mapping."""
        # Create surface with known pattern
        surface = pygame.Surface((3, 3))
        surface.set_at((0, 0), (255, 0, 0))  # Red
        surface.set_at((1, 0), (0, 255, 0))  # Green
        surface.set_at((2, 0), (0, 0, 255))  # Blue
        surface.set_at((0, 1), (255, 0, 0))  # Red
        surface.set_at((1, 1), (0, 255, 0))  # Green
        surface.set_at((2, 1), (0, 0, 255))  # Blue
        surface.set_at((0, 2), (255, 0, 0))  # Red
        surface.set_at((1, 2), (0, 255, 0))  # Green
        surface.set_at((2, 2), (0, 0, 255))  # Blue

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_consistency"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Check that pixel data is correctly encoded
        pixels = config.get("sprite", "pixels")
        assert pixels is not None

        # Should be 3 rows of 3 characters each
        rows = pixels.split("\n")
        assert len(rows) == TEST_PATTERN_SIZE, "Should have 3 rows"

        for row in rows:
            assert len(row) == TEST_PATTERN_SIZE, "Each row should have 3 characters"

        # Check that characters are from universal set
        glyphs = SPRITE_GLYPHS
        for row in rows:
            for char in row:
                assert char in glyphs, f"Character '{char}' should be in universal glyphs"

    @staticmethod
    def test_legacy_sprite_empty_surface():
        """Test legacy sprite with empty surface."""
        # Create empty surface
        surface = pygame.Surface((0, 0))

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_empty"

        # Should not crash when deflating
        config = legacy_sprite.deflate()

        # Should have sprite section
        assert config.has_section("sprite")
        assert config.get("sprite", "name") == "test_empty"

        # Should have no color sections
        glyphs = SPRITE_GLYPHS
        sections = config.sections()
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]
        assert len(color_sections) == 0, "Should have no color sections"

    @staticmethod
    def test_legacy_sprite_grayscale():
        """Test legacy sprite with grayscale colors."""
        # Create surface with grayscale colors
        surface = pygame.Surface((2, 2))
        surface.set_at((0, 0), (0, 0, 0))  # Black
        surface.set_at((1, 0), (128, 128, 128))  # Gray
        surface.set_at((0, 1), (255, 255, 255))  # White
        surface.set_at((1, 1), (64, 64, 64))  # Dark gray

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_grayscale"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Should have 4 color sections
        glyphs = SPRITE_GLYPHS
        sections = config.sections()
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]

        assert len(color_sections) == TEST_GRAYSCALE_SIZE, "Should have 4 color sections"

        # Find which character maps to black (0, 0, 0)
        black_char = None
        for char in color_sections:
            red = int(config.get(char, "red"))
            green = int(config.get(char, "green"))
            blue = int(config.get(char, "blue"))
            if red == 0 and green == 0 and blue == 0:
                black_char = char
                break

        assert black_char is not None, "Black color (0,0,0) should be mapped to a character"
        assert black_char in SPRITE_GLYPHS, (
            f"Black should map to a universal character, got {black_char}"
        )

    @staticmethod
    def test_legacy_sprite_character_order():
        """Test that characters are assigned in the correct order."""
        # Create surface with specific colors
        surface = pygame.Surface((2, 2))
        surface.set_at((0, 0), (0, 0, 0))  # Black
        surface.set_at((1, 0), (255, 0, 0))  # Red
        surface.set_at((0, 1), (0, 255, 0))  # Green
        surface.set_at((1, 1), (0, 0, 255))  # Blue

        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_order"

        # Test deflate method
        config = legacy_sprite.deflate()

        # Check that characters are assigned in universal order
        glyphs = SPRITE_GLYPHS
        sections = config.sections()
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]

        # Should use first 4 characters from universal set
        expected_chars = glyphs[:4]
        for char in expected_chars:
            assert char in color_sections, f"Character '{char}' should be used"

        # Check that black and red use universal characters
        assert "." in color_sections, "Black should map to '.'"
        assert "a" in color_sections, "Red should map to 'a'"

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
        glyphs = SPRITE_GLYPHS
        sections = config.sections()

        # Should have sprite section and color sections
        assert "sprite" in sections

        # Color sections should use universal characters
        color_sections = [s for s in sections if len(s) == 1 and s in glyphs]
        assert len(color_sections) > 0, "Should have color sections using universal characters"

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
