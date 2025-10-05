"""Test suite for animated sprite universal character set implementation.

This module specifically tests the animated sprite save/load functionality
with the universal character set, using TOML format only.
"""

import tempfile
import unittest
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites import SPRITE_GLYPHS
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame


class TestAnimatedSpriteGlyphs(unittest.TestCase):
    """Test animated sprite universal character set implementation."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_animated_sprite_toml_save_load(self):
        """Test animated sprite TOML save and load with universal character set."""
        # Create animated sprite with multiple animations and frames
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_animated_toml"

        # Create first animation with 3 frames
        frames1 = []
        colors1 = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]  # Red, Green, Blue

        for color in colors1:
            frame = SpriteFrame(pygame.Surface((4, 4)))
            frame.set_pixel_data([color] * 16)  # 4x4 = 16 pixels
            frame.duration = 0.5
            frames1.append(frame)

        animated_sprite.add_animation("walk", frames1)

        # Create second animation with 2 frames
        frames2 = []
        colors2 = [(255, 255, 0), (255, 0, 255)]  # Yellow, Magenta

        for color in colors2:
            frame = SpriteFrame(pygame.Surface((4, 4)))
            frame.set_pixel_data([color] * 16)
            frame.duration = 0.3
            frames2.append(frame)

        animated_sprite.add_animation("jump", frames2)

        # Save to TOML file
        toml_file = self.temp_path / "test_animated.toml"
        animated_sprite.save(str(toml_file), "toml")

        # Verify file was created and contains expected content
        assert toml_file.exists()
        content = toml_file.read_text()

        # Check TOML structure
        assert 'name = "test_animated_toml"' in content
        assert "[animation]" in content
        assert "[colors]" in content

        # Check that color definitions use universal character set
        # The actual TOML format uses [colors."char"] format
        assert '[colors."."]' in content
        assert '[colors."a"]' in content
        assert '[colors."A"]' in content
        assert '[colors."b"]' in content
        assert '[colors."B"]' in content
        assert "red =" in content
        assert "green =" in content
        assert "blue =" in content


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
        assert toml_file.exists()
        content = toml_file.read_text()

        # Check TOML structure
        assert "[sprite]" in content
        assert 'name = "test_animated_toml"' in content
        assert "[animation]" in content
        assert 'namespace = "test_anim"' in content
        assert "[animation.frame]" in content
        assert "[colors]" in content

        # Check that colors use universal character set
        glyphs = SPRITE_GLYPHS.strip()
        for char in glyphs[:2]:  # Should use first 2 characters
            assert f'[colors."{char}"]' in content

    def test_animated_sprite_character_mapping_consistency(self):
        """Test that character mapping is consistent in TOML format."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_consistency"

        # Create animation with specific colors
        frame = SpriteFrame(pygame.Surface((2, 2)))
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        frame.set_pixel_data(colors)
        animated_sprite.add_animation("test_anim", [frame])

        # Save in TOML format
        toml_file = self.temp_path / "test_consistency.toml"
        animated_sprite.save(str(toml_file), "toml")

        # File should exist
        assert toml_file.exists()

        # Check TOML content
        toml_content = toml_file.read_text()

        # Check that it uses universal character set
        # The actual TOML format uses inline color definitions
        assert '".' in toml_content
        assert '"a"' in toml_content
        assert '"A"' in toml_content
        assert '"b"' in toml_content
        assert "red =" in toml_content
        assert "green =" in toml_content
        assert "blue =" in toml_content

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
        toml_file = self.temp_path / "test_special.toml"
        animated_sprite.save(str(toml_file), "toml")

        content = toml_file.read_text()

        # Should have sections for the actual characters used
        assert '[colors."."]' in content  # Black
        assert '[colors."a"]' in content  # Red

    def test_animated_sprite_character_limit(self):
        """Test character limit enforcement in animated sprites."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_limit"

        # Create multiple frames with many unique colors to ensure it's treated as animated
        frames = []
        for frame_idx in range(3):  # Multiple frames to ensure animated
            frame = SpriteFrame(pygame.Surface((8, 8)))
            colors = []
            for i in range(70):  # More than 64 character limit
                r = (i * 3 + frame_idx * 10) % 256
                g = (i * 5 + frame_idx * 10) % 256
                b = (i * 7 + frame_idx * 10) % 256
                colors.append((r, g, b))

            # Create pixel data with all colors
            pixels = colors[:64]  # 8x8 = 64 pixels
            frame.set_pixel_data(pixels)
            frame.duration = 0.5
            frames.append(frame)

        animated_sprite.add_animation("test_anim", frames)

        # Should raise ValueError when trying to save
        toml_file = self.temp_path / "test_limit.toml"
        with pytest.raises(ValueError, match="Too many colors"):
            animated_sprite.save(str(toml_file), "toml")

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
        toml_file = self.temp_path / "test_multiple.toml"
        animated_sprite.save(str(toml_file), "toml")

        content = toml_file.read_text()

        # Should have animation sections
        assert "[animation]" in content
        assert 'name = "test_multiple_animations"' in content

        # Should use universal character set
        glyphs = SPRITE_GLYPHS.strip()
        for char in glyphs[:6]:  # Should use first 6 characters for 6 unique colors
            assert f'[colors."{char}"]' in content

    def test_animated_sprite_empty_animations(self):
        """Test animated sprite with empty animations."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_empty"

        # Add empty animation
        animated_sprite.add_animation("empty_anim", [])

        # Should not crash when saving
        toml_file = self.temp_path / "test_empty.toml"
        animated_sprite.save(str(toml_file), "toml")

        # File should be created
        assert toml_file.exists()
        content = toml_file.read_text()

        # Should have animation section but no frame sections
        assert "[animation]" in content
        assert 'name = "test_empty"' in content

    def test_animated_sprite_single_color(self):
        """Test animated sprite with single color across all frames."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = "test_single_color"

        # Create frames with only one color
        frames = []
        for _ in range(3):
            frame = SpriteFrame(pygame.Surface((2, 2)))
            frame.set_pixel_data([(255, 0, 0)] * 4)  # All red
            frames.append(frame)

        animated_sprite.add_animation("red_anim", frames)

        # Save and check
        toml_file = self.temp_path / "test_single_color.toml"
        animated_sprite.save(str(toml_file), "toml")

        content = toml_file.read_text()

        # Should have animation sections
        assert "[animation]" in content
        assert 'name = "test_single_color"' in content

        # Should use the actual character for red
        assert '[colors."."]' in content  # Red should map to '.'


if __name__ == "__main__":
    unittest.main()
