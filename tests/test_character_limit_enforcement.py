#!/usr/bin/env python3
"""
Test suite for character limit enforcement across all sprite modes.

This module tests that the 64-character limit is properly enforced
across static sprites, animated sprites, and legacy sprites.
"""

import tempfile
import unittest
from pathlib import Path

import pygame

from glitchygames.sprites import SPRITE_GLYPHS, BitmappySprite
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from scripts.raw_sprite_loader import BitmappyLegacySprite


class TestCharacterLimitEnforcement(unittest.TestCase):
    """Test character limit enforcement across all sprite modes."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        pygame.quit()

    def test_character_limit_constant(self):
        """Test that the character limit is properly defined."""
        glyphs = SPRITE_GLYPHS.strip()
        self.assertEqual(len(glyphs), 64, "SPRITE_GLYPHS should contain exactly 64 characters")
        
        # Test that we can create exactly 64 unique colors
        colors = []
        for i in range(64):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # All colors should be unique
        self.assertEqual(len(set(colors)), 64, "Should be able to create 64 unique colors")

    def test_static_sprite_character_limit(self):
        """Test character limit enforcement in static sprites."""
        # Create sprite with exactly 64 colors (should work)
        sprite = BitmappySprite(x=0, y=0, width=8, height=8, name="test_64_colors")
        
        colors = []
        for i in range(64):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # Set up pixel data
        pixels = []
        for y in range(8):
            for x in range(8):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])
        
        sprite.pixels = pixels
        sprite.pixels_across = 8
        sprite.pixels_tall = 8
        
        # Should not raise error
        ini_file = self.temp_path / "test_64_colors.ini"
        sprite.save(str(ini_file), "ini")
        self.assertTrue(ini_file.exists())
        
        # Test with 65 colors (should fail)
        sprite.pixels = colors + [(255, 255, 255)]  # Add one more color
        sprite.pixels_across = 9
        sprite.pixels_tall = 9
        
        with self.assertRaises(ValueError) as context:
            sprite.save(str(ini_file), "ini")
        
        self.assertIn("Too many colors", str(context.exception))

    def test_animated_sprite_character_limit(self):
        """Test character limit enforcement in animated sprites."""
        # Create animated sprite with exactly 64 colors (should work)
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_64_colors_animated"
        
        # Create colors
        colors = []
        for i in range(64):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # Create frame with all colors
        frame = SpriteFrame(pygame.Surface((8, 8)))
        pixels = []
        for i in range(64):  # 8x8 = 64 pixels
            pixels.append(colors[i])
        
        frame.set_pixel_data(pixels)
        animated_sprite.add_animation("test_anim", [frame])
        
        # Should not raise error
        ini_file = self.temp_path / "test_64_colors_animated.ini"
        animated_sprite.save(str(ini_file), "ini")
        self.assertTrue(ini_file.exists())
        
        # Test with 65 colors (should fail)
        frame.set_pixel_data(colors + [(255, 255, 255)])  # Add one more color
        
        with self.assertRaises(ValueError) as context:
            animated_sprite.save(str(ini_file), "ini")
        
        self.assertIn("Too many colors", str(context.exception))

    def test_legacy_sprite_character_limit(self):
        """Test character limit enforcement in legacy sprites."""
        # Create surface with exactly 64 colors (should work)
        surface = pygame.Surface((8, 8))
        
        colors = []
        for i in range(64):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # Fill surface with colors
        for y in range(8):
            for x in range(8):
                color_index = (x + y) % len(colors)
                surface.set_at((x, y), colors[color_index])
        
        # Create legacy sprite
        legacy_sprite = BitmappyLegacySprite.__new__(BitmappyLegacySprite)
        legacy_sprite.image = surface
        legacy_sprite.rect = surface.get_rect()
        legacy_sprite.name = "test_64_colors_legacy"
        
        # Should not raise error
        config = legacy_sprite.deflate()
        self.assertIsNotNone(config)
        
        # Test with 65 colors (should fail)
        surface.set_at((0, 0), (255, 255, 255))  # Add one more unique color
        
        with self.assertRaises(ValueError) as context:
            legacy_sprite.deflate()
        
        self.assertIn("Too many colors", str(context.exception))

    def test_mixed_animation_character_limit(self):
        """Test character limit enforcement across multiple animations."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_mixed_animations"
        
        # Create first animation with 32 colors
        colors1 = []
        for i in range(32):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors1.append((r, g, b))
        
        frame1 = SpriteFrame(pygame.Surface((4, 4)))
        frame1.set_pixel_data(colors1[:16])  # Use first 16 colors
        animated_sprite.add_animation("anim1", [frame1])
        
        # Create second animation with 32 different colors
        colors2 = []
        for i in range(32):
            r = (i * 4) % 256
            g = (i * 6) % 256
            b = (i * 8) % 256
            colors2.append((r, g, b))
        
        frame2 = SpriteFrame(pygame.Surface((4, 4)))
        frame2.set_pixel_data(colors2[:16])  # Use first 16 colors
        animated_sprite.add_animation("anim2", [frame2])
        
        # Total unique colors should be 64 (should work)
        ini_file = self.temp_path / "test_mixed_animations.ini"
        animated_sprite.save(str(ini_file), "ini")
        self.assertTrue(ini_file.exists())
        
        # Add third animation with one more color (should fail)
        frame3 = SpriteFrame(pygame.Surface((2, 2)))
        frame3.set_pixel_data([(255, 255, 255)] * 4)  # Add one more unique color
        animated_sprite.add_animation("anim3", [frame3])
        
        with self.assertRaises(ValueError) as context:
            animated_sprite.save(str(ini_file), "ini")
        
        self.assertIn("Too many colors", str(context.exception))

    def test_character_limit_edge_cases(self):
        """Test character limit enforcement with edge cases."""
        # Test with exactly 64 colors in different arrangements
        test_cases = [
            (1, 64),   # 1x64 grid
            (2, 32),   # 2x32 grid
            (4, 16),   # 4x16 grid
            (8, 8),    # 8x8 grid
            (16, 4),   # 16x4 grid
            (32, 2),   # 32x2 grid
            (64, 1),   # 64x1 grid
        ]
        
        for width, height in test_cases:
            with self.subTest(width=width, height=height):
                sprite = BitmappySprite(x=0, y=0, width=width, height=height, name=f"test_{width}x{height}")
                
                # Create 64 unique colors
                colors = []
                for i in range(64):
                    r = (i * 3) % 256
                    g = (i * 5) % 256
                    b = (i * 7) % 256
                    colors.append((r, g, b))
                
                # Set up pixel data
                pixels = []
                for y in range(height):
                    for x in range(width):
                        color_index = (x + y) % len(colors)
                        pixels.append(colors[color_index])
                
                sprite.pixels = pixels
                sprite.pixels_across = width
                sprite.pixels_tall = height
                
                # Should not raise error
                ini_file = self.temp_path / f"test_{width}x{height}.ini"
                sprite.save(str(ini_file), "ini")
                self.assertTrue(ini_file.exists())

    def test_character_limit_error_messages(self):
        """Test that character limit error messages are informative."""
        # Test static sprite error message
        sprite = BitmappySprite(x=0, y=0, width=8, height=8, name="test_error")
        
        # Create 65 colors
        colors = []
        for i in range(65):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        sprite.pixels = colors
        sprite.pixels_across = 9
        sprite.pixels_tall = 9
        
        with self.assertRaises(ValueError) as context:
            sprite.save(str(self.temp_path / "test_error.ini"), "ini")
        
        error_msg = str(context.exception)
        self.assertIn("Too many colors", error_msg)
        self.assertIn("64", error_msg)  # Should mention the limit

    def test_character_limit_with_reserved_characters(self):
        """Test character limit enforcement with reserved characters."""
        # Test that reserved characters (# and @) don't count against the limit
        sprite = BitmappySprite(x=0, y=0, width=8, height=8, name="test_reserved")
        
        # Create 64 colors including black and red (which map to reserved characters)
        colors = []
        colors.append((0, 0, 0))      # Black - maps to '#'
        colors.append((255, 0, 0))    # Red - maps to '@'
        
        for i in range(62):  # Add 62 more colors
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # Set up pixel data
        pixels = []
        for y in range(8):
            for x in range(8):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])
        
        sprite.pixels = pixels
        sprite.pixels_across = 8
        sprite.pixels_tall = 8
        
        # Should not raise error (64 total colors including reserved)
        ini_file = self.temp_path / "test_reserved.ini"
        sprite.save(str(ini_file), "ini")
        self.assertTrue(ini_file.exists())
        
        # Check that reserved characters are used
        content = ini_file.read_text()
        self.assertIn("[#]", content)  # Black should map to '#'
        self.assertIn("[@]", content)  # Red should map to '@'

    def test_character_limit_performance(self):
        """Test that character limit enforcement is efficient."""
        import time
        
        # Create sprite with many colors to test performance
        sprite = BitmappySprite(x=0, y=0, width=16, height=16, name="test_performance")
        
        # Create 100 colors (more than limit)
        colors = []
        for i in range(100):
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # Set up pixel data
        pixels = []
        for y in range(16):
            for x in range(16):
                color_index = (x + y) % len(colors)
                pixels.append(colors[color_index])
        
        sprite.pixels = pixels
        sprite.pixels_across = 16
        sprite.pixels_tall = 16
        
        # Measure time to detect limit violation
        start_time = time.time()
        
        with self.assertRaises(ValueError):
            sprite.save(str(self.temp_path / "test_performance.ini"), "ini")
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should be fast (less than 1 second)
        self.assertLess(execution_time, 1.0, "Character limit enforcement should be fast")


if __name__ == "__main__":
    unittest.main()
