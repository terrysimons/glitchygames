#!/usr/bin/env python3
"""
Test suite for animated sprite universal character set implementation.

This module specifically tests the animated sprite save/load functionality
with the universal character set, including INI, YAML, and TOML formats.
"""

import tempfile
import unittest
from pathlib import Path

import pygame

from glitchygames.sprites import SPRITE_GLYPHS
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame


class TestAnimatedSpriteGlyphs(unittest.TestCase):
    """Test animated sprite universal character set implementation."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        pygame.quit()

    def test_animated_sprite_ini_save_load(self):
        """Test animated sprite INI save and load with universal character set."""
        # Create animated sprite with multiple animations and frames
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_ini"
        
        # Create first animation with 3 frames
        frames1 = []
        colors1 = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # Red, Green, Blue
        
        for i, color in enumerate(colors1):
            frame = SpriteFrame(pygame.Surface((4, 4)))
            frame.set_pixel_data([color] * 16)  # 4x4 = 16 pixels
            frame.duration = 0.5
            frames1.append(frame)
        
        animated_sprite.add_animation("walk", frames1)
        
        # Create second animation with 2 frames
        frames2 = []
        colors2 = [(255, 255, 0), (255, 0, 255)]  # Yellow, Magenta
        
        for i, color in enumerate(colors2):
            frame = SpriteFrame(pygame.Surface((4, 4)))
            frame.set_pixel_data([color] * 16)
            frame.duration = 0.3
            frames2.append(frame)
        
        animated_sprite.add_animation("jump", frames2)
        
        # Save to INI file
        ini_file = self.temp_path / "test_animated.ini"
        animated_sprite.save(str(ini_file), "ini")
        
        # Verify file was created and contains expected content
        self.assertTrue(ini_file.exists())
        content = ini_file.read_text()
        
        # Check INI structure
        self.assertIn("[sprite]", content)
        self.assertIn("name = test_animated_ini", content)
        self.assertIn("[animation_walk]", content)
        self.assertIn("[animation_jump]", content)
        self.assertIn("[frame_walk_0]", content)
        self.assertIn("[frame_walk_1]", content)
        self.assertIn("[frame_walk_2]", content)
        self.assertIn("[frame_jump_0]", content)
        self.assertIn("[frame_jump_1]", content)
        
        # Check that color sections use universal character set
        glyphs = SPRITE_GLYPHS.strip()
        for char in glyphs[:5]:  # Should use first 5 characters for 5 unique colors
            self.assertIn(f"[{char}]", content)
            self.assertIn("red =", content)
            self.assertIn("green =", content)
            self.assertIn("blue =", content)

    def test_animated_sprite_yaml_save(self):
        """Test animated sprite YAML save with universal character set."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_yaml"
        
        # Create animation with multiple frames
        frames = []
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        
        for color in colors:
            frame = SpriteFrame(pygame.Surface((3, 3)))
            frame.set_pixel_data([color] * 9)  # 3x3 = 9 pixels
            frame.duration = 0.4
            frames.append(frame)
        
        animated_sprite.add_animation("test_anim", frames)
        
        # Save to YAML file
        yaml_file = self.temp_path / "test_animated.yaml"
        animated_sprite.save(str(yaml_file), "yaml")
        
        # Verify file was created
        self.assertTrue(yaml_file.exists())
        content = yaml_file.read_text()
        
        # Check YAML structure
        self.assertIn("sprite:", content)
        self.assertIn("name: test_animated_yaml", content)
        self.assertIn("type: animated", content)
        self.assertIn("animations:", content)
        self.assertIn("test_anim:", content)
        self.assertIn("frames:", content)

    def test_animated_sprite_toml_save(self):
        """Test animated sprite TOML save with universal character set."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_toml"
        
        # Create animation with frames
        frames = []
        colors = [(255, 0, 0), (0, 255, 0)]
        
        for color in colors:
            frame = SpriteFrame(pygame.Surface((2, 2)))
            frame.set_pixel_data([color] * 4)  # 2x2 = 4 pixels
            frame.duration = 0.6
            frames.append(frame)
        
        animated_sprite.add_animation("test_anim", frames)
        
        # Save to TOML file
        toml_file = self.temp_path / "test_animated.toml"
        animated_sprite.save(str(toml_file), "toml")
        
        # Verify file was created
        self.assertTrue(toml_file.exists())
        content = toml_file.read_text()
        
        # Check TOML structure
        self.assertIn("[sprite]", content)
        self.assertIn('name = "test_animated_toml"', content)
        self.assertIn("[animation]", content)
        self.assertIn('namespace = "test_anim"', content)
        self.assertIn("[animation.frame]", content)
        self.assertIn("[colors]", content)
        
        # Check that colors use universal character set
        glyphs = SPRITE_GLYPHS.strip()
        for char in glyphs[:2]:  # Should use first 2 characters
            self.assertIn(f'[colors."{char}"]', content)

    def test_animated_sprite_character_mapping_consistency(self):
        """Test that character mapping is consistent across different formats."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_consistency"
        
        # Create animation with specific colors
        frame = SpriteFrame(pygame.Surface((2, 2)))
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        frame.set_pixel_data(colors)
        animated_sprite.add_animation("test_anim", [frame])
        
        # Save in all three formats
        ini_file = self.temp_path / "test_consistency.ini"
        yaml_file = self.temp_path / "test_consistency.yaml"
        toml_file = self.temp_path / "test_consistency.toml"
        
        animated_sprite.save(str(ini_file), "ini")
        animated_sprite.save(str(yaml_file), "yaml")
        animated_sprite.save(str(toml_file), "toml")
        
        # All files should exist
        self.assertTrue(ini_file.exists())
        self.assertTrue(yaml_file.exists())
        self.assertTrue(toml_file.exists())
        
        # All should use the same character mapping
        ini_content = ini_file.read_text()
        yaml_content = yaml_file.read_text()
        toml_content = toml_file.read_text()
        
        # Check that all use universal character set
        glyphs = SPRITE_GLYPHS.strip()
        for char in glyphs[:4]:  # Should use first 4 characters
            self.assertIn(f"[{char}]", ini_content)
            self.assertIn(f'"{char}":', yaml_content)
            self.assertIn(f'[colors."{char}"]', toml_content)

    def test_animated_sprite_special_character_reservation(self):
        """Test that special characters are properly reserved in animated sprites."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_special_chars"
        
        # Create frames with colors that should map to reserved characters
        frame1 = SpriteFrame(pygame.Surface((2, 2)))
        frame1.set_pixel_data([(0, 0, 0)] * 4)  # Black - should map to '#'
        
        frame2 = SpriteFrame(pygame.Surface((2, 2)))
        frame2.set_pixel_data([(255, 0, 0)] * 4)  # Red - should map to '@'
        
        animated_sprite.add_animation("test_anim", [frame1, frame2])
        
        # Save and check that reserved characters are used
        ini_file = self.temp_path / "test_special.ini"
        animated_sprite.save(str(ini_file), "ini")
        
        content = ini_file.read_text()
        
        # Should have sections for reserved characters
        self.assertIn("[#]", content)  # Black
        self.assertIn("[@]", content)  # Red

    def test_animated_sprite_character_limit(self):
        """Test character limit enforcement in animated sprites."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_limit"
        
        # Create frame with many unique colors
        frame = SpriteFrame(pygame.Surface((8, 8)))
        colors = []
        for i in range(70):  # More than 64 character limit
            r = (i * 3) % 256
            g = (i * 5) % 256
            b = (i * 7) % 256
            colors.append((r, g, b))
        
        # Create pixel data with all colors
        pixels = []
        for i in range(64):  # 8x8 = 64 pixels
            pixels.append(colors[i])
        
        frame.set_pixel_data(pixels)
        animated_sprite.add_animation("test_anim", [frame])
        
        # Should raise ValueError when trying to save
        ini_file = self.temp_path / "test_limit.ini"
        with self.assertRaises(ValueError) as context:
            animated_sprite.save(str(ini_file), "ini")
        
        self.assertIn("Too many colors", str(context.exception))

    def test_animated_sprite_multiple_animations_character_sharing(self):
        """Test that multiple animations share character mappings efficiently."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_multiple_animations"
        
        # Create two animations with some shared colors
        frame1 = SpriteFrame(pygame.Surface((2, 2)))
        frame1.set_pixel_data([(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)])
        
        frame2 = SpriteFrame(pygame.Surface((2, 2)))
        frame2.set_pixel_data([(255, 0, 0), (0, 255, 0), (128, 128, 128), (0, 0, 0)])
        
        animated_sprite.add_animation("anim1", [frame1])
        animated_sprite.add_animation("anim2", [frame2])
        
        # Save and check that shared colors use the same characters
        ini_file = self.temp_path / "test_multiple.ini"
        animated_sprite.save(str(ini_file), "ini")
        
        content = ini_file.read_text()
        
        # Should have sections for both animations
        self.assertIn("[animation_anim1]", content)
        self.assertIn("[animation_anim2]", content)
        self.assertIn("[frame_anim1_0]", content)
        self.assertIn("[frame_anim2_0]", content)
        
        # Should use universal character set
        glyphs = SPRITE_GLYPHS.strip()
        for char in glyphs[:6]:  # Should use first 6 characters for 6 unique colors
            self.assertIn(f"[{char}]", content)

    def test_animated_sprite_empty_animations(self):
        """Test animated sprite with empty animations."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_empty"
        
        # Add empty animation
        animated_sprite.add_animation("empty_anim", [])
        
        # Should not crash when saving
        ini_file = self.temp_path / "test_empty.ini"
        animated_sprite.save(str(ini_file), "ini")
        
        # File should be created
        self.assertTrue(ini_file.exists())
        content = ini_file.read_text()
        
        # Should have animation section but no frame sections
        self.assertIn("[animation_empty_anim]", content)
        self.assertNotIn("[frame_empty_anim_0]", content)

    def test_animated_sprite_single_color(self):
        """Test animated sprite with single color across all frames."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_single_color"
        
        # Create frames with only one color
        frames = []
        for i in range(3):
            frame = SpriteFrame(pygame.Surface((2, 2)))
            frame.set_pixel_data([(255, 0, 0)] * 4)  # All red
            frames.append(frame)
        
        animated_sprite.add_animation("red_anim", frames)
        
        # Save and check
        ini_file = self.temp_path / "test_single_color.ini"
        animated_sprite.save(str(ini_file), "ini")
        
        content = ini_file.read_text()
        
        # Should have minimal color sections
        self.assertIn("[animation_red_anim]", content)
        self.assertIn("[frame_red_anim_0]", content)
        self.assertIn("[frame_red_anim_1]", content)
        self.assertIn("[frame_red_anim_2]", content)
        
        # Should use reserved character for red
        self.assertIn("[@]", content)  # Red should map to '@'


if __name__ == "__main__":
    unittest.main()
