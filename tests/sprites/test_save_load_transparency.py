"""Tests for sprite save/load functionality with transparency handling."""

import tempfile
import unittest
from pathlib import Path

import pygame

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.sprites.constants import DEFAULT_FILE_FORMAT
from tests.mocks.test_mock_factory import MockFactory


class TestSaveLoadTransparency(unittest.TestCase):
    """Test save/load functionality with proper transparency handling."""

    def setUp(self):
        """Set up test fixtures."""
        # Initialize pygame properly
        if not pygame.get_init():
            pygame.init()

        # Set up a minimal display for pygame surfaces
        pygame.display.set_mode((100, 100))

        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers.values():
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_single_frame_rgb_save_load(self):
        """Test saving and loading a single frame sprite with RGB (indexed color) mode."""
        # Create a single frame sprite with RGB pixels
        sprite = AnimatedSprite()
        sprite.name = 'test_single_frame_rgb'

        # Create a 3x3 frame with RGB pixels
        surface = pygame.Surface((3, 3))
        surface.fill((255, 0, 255))  # Magenta background

        # Add some colored pixels
        surface.set_at((0, 0), (255, 0, 0))  # Red
        surface.set_at((1, 1), (0, 255, 0))  # Green
        surface.set_at((2, 2), (0, 0, 255))  # Blue

        frame = SpriteFrame(surface)
        # Use RGB pixels (no alpha channel)
        frame.pixels = [
            (255, 0, 0),
            (255, 0, 255),
            (255, 0, 255),  # Row 0: Red, Magenta, Magenta
            (255, 0, 255),
            (0, 255, 0),
            (255, 0, 255),  # Row 1: Magenta, Green, Magenta
            (255, 0, 255),
            (255, 0, 255),
            (0, 0, 255),  # Row 2: Magenta, Magenta, Blue
        ]

        sprite.add_animation('idle', [frame])

        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)

            # Load the sprite back
            loaded_sprite = AnimatedSprite()
            loaded_sprite.load(temp_path)

            # Verify the loaded sprite
            assert loaded_sprite.name == 'test_single_frame_rgb'
            assert len(loaded_sprite._animations) == 1
            # Single-frame format uses the sprite's name as the animation key
            assert 'test_single_frame_rgb' in loaded_sprite._animations

            loaded_frame = loaded_sprite._animations['test_single_frame_rgb'][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # Verify pixel data (should be RGB or RGBA)
            assert len(loaded_pixels) == 9  # 3x3 = 9 pixels

            # Check specific colored pixels (handle both RGB and RGBA)
            assert loaded_pixels[0][:3] == (255, 0, 0)  # Red at (0,0)
            assert loaded_pixels[4][:3] == (0, 255, 0)  # Green at (1,1)
            assert loaded_pixels[8][:3] == (0, 0, 255)  # Blue at (2,2)

            # Check transparent pixels (should be magenta)
            transparent_indices = [1, 2, 3, 5, 6, 7]
            for idx in transparent_indices:
                assert loaded_pixels[idx][:3] == (255, 0, 255), (
                    f'Expected magenta transparency at index {idx}, got {loaded_pixels[idx]}'
                )

            # Verify TOML content has [colors] and uses reserved glyphs for colors
            toml_content = Path(temp_path).read_text(encoding='utf-8')

            # Magenta transparency key is written as a normal color entry
            assert '"█"' in toml_content
            assert 'red = 255' in toml_content
            assert 'green = 0' in toml_content
            assert 'blue = 255' in toml_content

            # Should not contain [alpha] section
            assert '[alpha]' not in toml_content

        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)

    def test_single_frame_rgba_save_load(self):
        """Test saving and loading a single frame sprite with RGBA (alpha) mode."""
        # Create a single frame sprite with RGBA pixels
        sprite = AnimatedSprite()
        sprite.name = 'test_single_frame_rgba'

        # Create a 2x2 frame with RGBA pixels
        surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        surface.fill((255, 0, 255, 255))  # Magenta background (opaque)

        # Add some colored pixels with different alpha values
        surface.set_at((0, 0), (255, 255, 255, 255))  # White (opaque)
        surface.set_at((1, 1), (255, 0, 0, 128))  # Red (semi-transparent)

        frame = SpriteFrame(surface)
        # Use RGBA pixels (with alpha channel)
        frame.pixels = [
            (255, 255, 255, 255),
            (255, 0, 255, 255),  # Row 0: White, Magenta
            (255, 0, 255, 255),
            (255, 0, 0, 128),  # Row 1: Magenta, Red (semi-transparent)
        ]

        sprite.add_animation('idle', [frame])

        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)

            # Load the sprite back
            loaded_sprite = AnimatedSprite()
            loaded_sprite.load(temp_path)

            # Verify the loaded sprite
            assert loaded_sprite.name == 'test_single_frame_rgba'
            assert len(loaded_sprite._animations) == 1
            # Single-frame format uses the sprite's name as the animation key
            assert 'test_single_frame_rgba' in loaded_sprite._animations

            loaded_frame = loaded_sprite._animations['test_single_frame_rgba'][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # Verify pixel data (should be RGBA)
            assert len(loaded_pixels) == 4  # 2x2 = 4 pixels

            # Check specific colored pixels
            assert loaded_pixels[0] == (255, 255, 255, 255)  # White at (0,0)
            assert loaded_pixels[3] == (255, 0, 0, 128)  # Red at (1,1)

            # Check transparent pixels (should be magenta)
            assert loaded_pixels[1][:3] == (255, 0, 255)  # Magenta at (0,1)
            assert loaded_pixels[2][:3] == (255, 0, 255)  # Magenta at (1,0)

            # Verify TOML content
            toml_content = Path(temp_path).read_text(encoding='utf-8')

            # Magenta transparency key is written as a normal color entry
            assert '"█"' in toml_content
            assert 'red = 255' in toml_content
            assert 'green = 0' in toml_content
            assert 'blue = 255' in toml_content

            # Should contain alpha values for semi-transparent pixels
            assert 'alpha = 128' in toml_content

            # Should not contain [alpha] section
            assert '[alpha]' not in toml_content

        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)

    def test_animated_sprite_rgb_save_load(self):
        """Test saving and loading an animated sprite with RGB (indexed color) mode."""
        # Create an animated sprite with 2 frames
        sprite = AnimatedSprite()
        sprite.name = 'test_animated_rgb'

        frames = []
        for frame_idx in range(2):
            surface = pygame.Surface((2, 2))
            surface.fill((255, 0, 255))  # Magenta background

            # Add different colored pixels for each frame
            if frame_idx == 0:
                surface.set_at((0, 0), (255, 0, 0))  # Red
            else:
                surface.set_at((1, 1), (0, 255, 0))  # Green

            frame = SpriteFrame(surface, duration=0.5)

            # Create pixel data with RGB (no alpha)
            pixels = [(255, 0, 255)] * 4  # All transparent initially
            if frame_idx == 0:
                pixels[0] = (255, 0, 0)  # Red at (0,0)
            else:
                pixels[3] = (0, 255, 0)  # Green at (1,1)

            frame.pixels = pixels
            frames.append(frame)

        sprite.add_animation('walk', frames)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)

            # Load the sprite back
            loaded_sprite = AnimatedSprite()
            loaded_sprite.load(temp_path)

            # Verify the loaded sprite
            assert loaded_sprite.name == 'test_animated_rgb'
            assert len(loaded_sprite._animations) == 1
            assert 'walk' in loaded_sprite._animations

            loaded_frames = loaded_sprite._animations['walk']
            assert len(loaded_frames) == 2

            # Verify each frame
            for frame_idx, loaded_frame in enumerate(loaded_frames):
                loaded_pixels = loaded_frame.get_pixel_data()
                assert len(loaded_pixels) == 4  # 2x2 = 4 pixels

                # Check the colored pixel for this frame
                if frame_idx == 0:
                    assert loaded_pixels[0][:3] == (255, 0, 0)  # Red
                else:
                    assert loaded_pixels[3][:3] == (0, 255, 0)  # Green

                # Check that other pixels are transparent (magenta)
                transparent_indices = [1, 2] if frame_idx == 0 else [0, 1, 2]
                for idx in transparent_indices:
                    assert loaded_pixels[idx][:3] == (255, 0, 255), (
                        f'Frame {frame_idx}, pixel {idx} should be magenta'
                    )

            # Verify TOML content
            toml_content = Path(temp_path).read_text(encoding='utf-8')

            # Magenta transparency key is written as a normal color entry
            assert '"█"' in toml_content
            assert 'red = 255' in toml_content
            assert 'green = 255' in toml_content
            assert 'blue = 0' in toml_content

            # Should contain other color definitions
            assert '[colors."."]' in toml_content  # Red
            assert '[colors."a"]' in toml_content  # Green

            # Should not contain [alpha] section
            assert '[alpha]' not in toml_content

        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)

    def test_animated_sprite_rgba_save_load(self):
        """Test saving and loading an animated sprite with RGBA (alpha) mode."""
        # Create an animated sprite with 2 frames
        sprite = AnimatedSprite()
        sprite.name = 'test_animated_rgba'

        frames = []
        for frame_idx in range(2):
            surface = pygame.Surface((2, 2), pygame.SRCALPHA)
            surface.fill((255, 0, 255, 255))  # Magenta background

            # Add different colored pixels for each frame
            if frame_idx == 0:
                surface.set_at((0, 0), (255, 255, 255, 255))  # White (opaque)
            else:
                surface.set_at((1, 1), (255, 0, 0, 128))  # Red (semi-transparent)

            frame = SpriteFrame(surface, duration=0.5)

            # Create pixel data with RGBA (with alpha)
            pixels = [(255, 0, 255, 255)] * 4  # All transparent initially
            if frame_idx == 0:
                pixels[0] = (255, 255, 255, 255)  # White at (0,0)
            else:
                pixels[3] = (255, 0, 0, 128)  # Red at (1,1)

            frame.pixels = pixels
            frames.append(frame)

        sprite.add_animation('walk', frames)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)

            # Load the sprite back
            loaded_sprite = AnimatedSprite()
            loaded_sprite.load(temp_path)

            # Verify the loaded sprite
            assert loaded_sprite.name == 'test_animated_rgba'
            assert len(loaded_sprite._animations) == 1
            assert 'walk' in loaded_sprite._animations

            loaded_frames = loaded_sprite._animations['walk']
            assert len(loaded_frames) == 2

            # Verify each frame
            for frame_idx, loaded_frame in enumerate(loaded_frames):
                loaded_pixels = loaded_frame.get_pixel_data()
                assert len(loaded_pixels) == 4  # 2x2 = 4 pixels

                # Check the colored pixel for this frame
                if frame_idx == 0:
                    assert loaded_pixels[0] == (255, 255, 255, 255)  # White
                else:
                    assert loaded_pixels[3] == (255, 0, 0, 128)  # Red (semi-transparent)

                # Check that other pixels are transparent (magenta)
                transparent_indices = [1, 2, 3] if frame_idx == 0 else [0, 1, 2]
                for idx in transparent_indices:
                    if (frame_idx == 0 and idx == 3) or (frame_idx == 1 and idx == 3):
                        continue  # Skip the colored pixel
                    assert loaded_pixels[idx][:3] == (255, 0, 255), (
                        f'Frame {frame_idx}, pixel {idx} should be magenta'
                    )

            # Verify TOML content
            toml_content = Path(temp_path).read_text(encoding='utf-8')

            # Magenta transparency key is written as a normal color entry
            assert '"█"' in toml_content
            assert 'red = 255' in toml_content
            assert 'green = 0' in toml_content
            assert 'blue = 0' in toml_content

            # Should contain alpha values for semi-transparent pixels
            assert 'alpha = 128' in toml_content

            # Should not contain [alpha] section
            assert '[alpha]' not in toml_content

        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)

    def test_empty_frame_handling(self):
        """Test that empty frames (all transparent) are handled correctly."""
        # Create a sprite with an empty frame (all transparent)
        sprite = AnimatedSprite()
        sprite.name = 'empty_frame_test'

        surface = pygame.Surface((2, 2))
        surface.fill((255, 0, 255))  # All magenta

        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 255)] * 4  # All transparent

        sprite.add_animation('empty', [frame])

        # Save and load
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            sprite.save(temp_path, DEFAULT_FILE_FORMAT)

            loaded_sprite = AnimatedSprite()
            loaded_sprite.load(temp_path)

            loaded_frame = loaded_sprite._animations['empty_frame_test'][0]
            loaded_pixels = loaded_frame.get_pixel_data()

            # All pixels should be magenta
            for pixel in loaded_pixels:
                assert pixel[:3] == (255, 0, 255)

            # Verify TOML content uses block characters
            toml_content = Path(temp_path).read_text(encoding='utf-8')

            # Magenta transparency key is written as a normal color entry
            assert '"█"' in toml_content

            # Should not contain other color definitions
            assert '[colors."a"]' not in toml_content
            assert '[colors."b"]' not in toml_content

        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)

    def test_transparency_consistency_multiple_cycles(self):
        """Test that transparency is handled consistently across multiple save/load cycles."""
        # Create a sprite with mixed transparency
        sprite = AnimatedSprite()
        sprite.name = 'transparency_test'

        surface = pygame.Surface((2, 2))
        surface.fill((255, 0, 255))  # Magenta background
        surface.set_at((0, 0), (255, 255, 255))  # White pixel

        frame = SpriteFrame(surface)
        frame.pixels = [
            (255, 255, 255),
            (255, 0, 255),  # Row 0: White, Transparent
            (255, 0, 255),
            (255, 0, 255),  # Row 1: Transparent, Transparent
        ]

        sprite.add_animation('test', [frame])

        # Save and load multiple times to ensure consistency
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.toml', delete=False, encoding='utf-8'
        ) as f:
            temp_path = f.name

        try:
            for _cycle in range(3):
                sprite.save(temp_path, DEFAULT_FILE_FORMAT)

                # Load back
                loaded_sprite = AnimatedSprite()
                loaded_sprite.load(temp_path)

                loaded_frame = loaded_sprite._animations['transparency_test'][0]
                loaded_pixels = loaded_frame.get_pixel_data()

                # Verify consistency
                assert len(loaded_pixels) == 4
                assert loaded_pixels[0][:3] == (255, 255, 255)  # White
                assert loaded_pixels[1][:3] == (255, 0, 255)  # Magenta
                assert loaded_pixels[2][:3] == (255, 0, 255)  # Magenta
                assert loaded_pixels[3][:3] == (255, 0, 255)  # Magenta

                # Update sprite for next cycle
                sprite = loaded_sprite

        finally:
            # Clean up temporary file
            Path(temp_path).unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
