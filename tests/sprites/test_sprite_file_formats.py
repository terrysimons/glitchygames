"""Test suite for TOML-only file format support.

This module tests that the sprite loading system now only supports TOML format
and properly rejects YAML/INI formats after the cleanup.
"""

import tempfile
from pathlib import Path
from typing import cast

import pygame
import pytest

from glitchygames.sprites import BitmappySprite, SpriteFactory
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame

# Constants for magic values
EXPECTED_ERROR_COUNT_2 = 2


class TestTOMLOnlySupport:
    """Test that only TOML format is supported after cleanup."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    @staticmethod
    def test_file_format_detection_toml_only():
        """Test that file format detection supports multiple formats."""
        # Test TOML detection
        toml_format = SpriteFactory.detect_file_format('test.toml')
        assert toml_format == 'toml'

        # Test YAML detection
        yaml_format = SpriteFactory.detect_file_format('test.yaml')
        assert yaml_format == 'yaml'

        # Test INI detection (should return unknown since INI support removed)
        ini_format = SpriteFactory.detect_file_format('test.ini')
        assert ini_format == 'unknown'

        # Test unknown format
        unknown_format = SpriteFactory.detect_file_format('test.unknown')
        assert unknown_format == 'unknown'

    def test_static_sprite_toml_save_load(self):
        """Test that static sprites can save and load in TOML format."""
        # Create a test sprite
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='test_toml')
        sprite.pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        # Save to TOML
        toml_file = self.temp_path / 'test_static.toml'
        sprite.save(str(toml_file), 'toml')

        # Verify file was created
        assert toml_file.exists()
        content = toml_file.read_text(encoding='utf-8')

        # Check TOML structure
        assert '[sprite]' in content
        assert 'name = "test_toml"' in content
        # TOML uses individual color sections like [colors."."]
        assert 'red =' in content  # Should have color definitions

        # Load it back
        loaded_sprite = SpriteFactory.load_sprite(filename=str(toml_file))
        assert loaded_sprite.name == 'test_toml'
        # Check that the sprite was loaded correctly
        assert hasattr(loaded_sprite, 'image')
        assert loaded_sprite.image is not None
        assert loaded_sprite.image.get_size() == (2, 2)
        # The loaded image draws the saved pixels (red, green / blue, white)
        assert pygame.surfarray.array3d(loaded_sprite.image).transpose(1, 0, 2).tolist() == [
            [[255, 0, 0], [0, 255, 0]],
            [[0, 0, 255], [255, 255, 255]],
        ]

    def test_animated_sprite_toml_save_load(self):
        """Test that animated sprites can save and load in TOML format."""
        # Create an animated sprite
        animated_sprite = AnimatedSprite()
        animated_sprite.name = 'test_animated_toml'

        # Create frames
        frame1 = SpriteFrame(pygame.Surface((2, 2)))
        red_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)  # Red frame
        frame1.set_pixel_data(red_pixels)

        frame2 = SpriteFrame(pygame.Surface((2, 2)))
        green_pixels = cast('list[tuple[int, ...]]', [(0, 255, 0)] * 4)  # Green frame
        frame2.set_pixel_data(green_pixels)

        animated_sprite.add_animation('test_anim', [frame1, frame2])

        # Save to TOML
        toml_file = self.temp_path / 'test_animated.toml'
        animated_sprite.save(str(toml_file), 'toml')

        # Verify file was created
        assert toml_file.exists()
        content = toml_file.read_text(encoding='utf-8')

        # Check TOML structure
        assert '[sprite]' in content
        assert 'name = "test_animated_toml"' in content
        assert '[animation]' in content
        # TOML uses individual color sections like [colors."."]
        assert 'red =' in content  # Should have color definitions

        # Load it back
        loaded_sprite = SpriteFactory.load_sprite(filename=str(toml_file))
        assert loaded_sprite.name == 'test_animated_toml'
        assert 'test_anim' in loaded_sprite.animations
        # Both frames come back and draw their own color
        frame_colors = [
            pygame.surfarray.array3d(frame.image).reshape(-1, 3).tolist()
            for frame in loaded_sprite.animations['test_anim']
        ]
        assert frame_colors == [[[255, 0, 0]] * 4, [[0, 255, 0]] * 4]

    def test_yaml_format_rejected(self, mocker):
        """Test that YAML format is properly rejected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='test')
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        sprite.pixels = pixel_data
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        yaml_file = self.temp_path / 'test.yaml'

        # Patch the sprite's logger to check what it logs (and keep the output quiet)
        mock_log = mocker.patch.object(sprite, 'log')
        # Should raise error when trying to save as YAML
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.save(str(yaml_file), 'yaml')

        # Verify the EXCEPTION log messages were called (inside except blocks)
        assert mock_log.exception.call_count == EXPECTED_ERROR_COUNT_2
        # Check that the log messages contain the expected content
        first_call = mock_log.exception.call_args_list[0][0][0]
        second_call = mock_log.exception.call_args_list[1][0][0]
        assert 'Error in deflate' in first_call
        assert 'Error in save' in second_call

    def test_ini_format_rejected(self, mocker):
        """Test that INI format is properly rejected."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='test')
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        sprite.pixels = pixel_data
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        ini_file = self.temp_path / 'test.ini'

        # Patch the sprite's logger to check what it logs (and keep the output quiet)
        mock_log = mocker.patch.object(sprite, 'log')
        # Should raise error when trying to save as INI
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.save(str(ini_file), 'ini')

        # Verify the EXCEPTION log messages were called (inside except blocks)
        assert mock_log.exception.call_count == EXPECTED_ERROR_COUNT_2
        # Check that the log messages contain the expected content
        first_call = mock_log.exception.call_args_list[0][0][0]
        second_call = mock_log.exception.call_args_list[1][0][0]
        assert 'Error in deflate' in first_call
        assert 'Error in save' in second_call

    def test_animated_sprite_yaml_rejected(self):
        """Test that animated sprites reject YAML format."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = 'test'

        frame = SpriteFrame(pygame.Surface((2, 2)))
        yaml_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        frame.set_pixel_data(yaml_pixels)
        animated_sprite.add_animation('test_anim', [frame])

        yaml_file = self.temp_path / 'test.yaml'

        # Should raise error when trying to save as YAML
        with pytest.raises(ValueError, match='Unsupported format'):
            animated_sprite.save(str(yaml_file), 'yaml')

    def test_animated_sprite_ini_rejected(self):
        """Test that animated sprites reject INI format."""
        animated_sprite = AnimatedSprite()
        animated_sprite.name = 'test'

        frame = SpriteFrame(pygame.Surface((2, 2)))
        ini_pixels = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        frame.set_pixel_data(ini_pixels)
        animated_sprite.add_animation('test_anim', [frame])

        ini_file = self.temp_path / 'test.ini'

        # Should raise error when trying to save as INI
        with pytest.raises(ValueError, match='Unsupported format'):
            animated_sprite.save(str(ini_file), 'ini')

    def test_default_format_is_toml(self):
        """Test that default file format is TOML."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='test')
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        sprite.pixels = pixel_data
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        toml_file = self.temp_path / 'test.toml'

        # Should work with default format (TOML)
        sprite.save(str(toml_file))
        assert toml_file.exists()

    @staticmethod
    def test_unsupported_format_error_message(mocker):
        """Test that unsupported format error messages are clear."""
        sprite = BitmappySprite(x=0, y=0, width=2, height=2, name='test')
        pixel_data = cast('list[tuple[int, ...]]', [(255, 0, 0)] * 4)
        sprite.pixels = pixel_data
        sprite.pixels_across = 2
        sprite.pixels_tall = 2

        # Patch the sprite's logger to check what it logs (and keep the output quiet)
        mock_log = mocker.patch.object(sprite, 'log')
        # Test error message for unsupported format
        with pytest.raises(ValueError, match='Unsupported format'):
            sprite.save('test.json', 'json')

        # Verify the EXCEPTION log messages were called (inside except blocks)
        assert mock_log.exception.call_count == EXPECTED_ERROR_COUNT_2
        # Check that the log messages contain the expected content
        first_call = mock_log.exception.call_args_list[0][0][0]
        second_call = mock_log.exception.call_args_list[1][0][0]
        assert 'Error in deflate' in first_call
        assert 'Error in save' in second_call
