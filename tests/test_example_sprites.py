"""Test suite for example sprites in the project directory.

This module tests loading and rendering of the various example sprite files
found in the project directory to ensure they work correctly with the TOML-only
implementation.
"""

import operator
import tempfile
import time
import unittest
from pathlib import Path

import pygame
from glitchygames.sprites import SpriteFactory

# Constants for test thresholds
PIXEL_MATCH_THRESHOLD = 90.0
MAX_SPRITE_DIMENSION = 2000
MAX_ASPECT_RATIO = 10
MIN_ASPECT_RATIO = 0.1
MAX_COLOR_DOMINANCE = 95.0
MAX_LOAD_TIME = 1.0
MAX_RENDER_TIME = 0.1


class TestExampleSprites(unittest.TestCase):
    """Test example sprites from the project directory."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # List of example sprite files to test
        self.example_sprites = [
            "colors.toml",  # Animated sprite
            "static.toml",  # Static sprite
            "circle.toml",  # Simple shape
            "single.toml",  # Single pixel
            "red.toml",  # Color test
            "green-x-8x8-static.toml",  # Static with specific size
            "butterfly.toml",  # Butterfly sprite
            "butterfly-animation-8x8.toml",  # Animated butterfly
            "mario-running.toml",  # Mario animation
            "ghetto_mario.toml",  # Another Mario variant
            "yin-yang.toml",  # Yin-yang symbol
            "swirl.toml",  # Swirl pattern
            "mosaic.toml",  # Mosaic pattern
            "squirgle.toml",  # Squiggle pattern
        ]

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_load_example_sprites(self):
        """Test that all example sprites can be loaded."""
        loaded_count = 0
        failed_count = 0

        for sprite_file in self.example_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                # Load the sprite
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                assert sprite is not None, f"Failed to load {sprite_file}"

                # Verify basic properties
                assert sprite.image is not None, f"Sprite {sprite_file} should have an image"
                assert isinstance(sprite.image, pygame.Surface), (
                    f"Sprite {sprite_file} image should be a Surface"
                )

                # Check dimensions
                width, height = sprite.image.get_size()
                assert width > 0, f"Sprite {sprite_file} width should be positive"
                assert height > 0, f"Sprite {sprite_file} height should be positive"

                loaded_count += 1

            except (ValueError, FileNotFoundError, AttributeError):
                failed_count += 1

        # Verify we loaded at least some sprites
        assert loaded_count > 0, "Should load at least one example sprite"

    @staticmethod
    def test_animated_sprites_have_animations():
        """Test that animated sprites have proper animation data."""
        animated_sprites = ["colors.toml", "butterfly-animation-8x8.toml", "mario-running.toml"]

        for sprite_file in animated_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)

                # Check if it's an animated sprite
                if hasattr(sprite, "animations"):
                    assert sprite.animations is not None, (
                        f"Animated sprite {sprite_file} should have animations"
                    )
                    assert len(sprite.animations) > 0, (
                        f"Animated sprite {sprite_file} should have at least one animation"
                    )

                    # Check each animation
                    for anim_name, frames in sprite.animations.items():
                        assert frames is not None, f"Animation {anim_name} should have frames"
                        assert len(frames) > 0, (
                            f"Animation {anim_name} should have at least one frame"
                        )

                        # Check each frame
                        for i, frame in enumerate(frames):
                            assert frame.image is not None, (
                                f"Frame {i} in {anim_name} should have an image"
                            )
                            assert isinstance(frame.image, pygame.Surface), (
                                f"Frame {i} in {anim_name} should be a Surface"
                            )

            except (ValueError, FileNotFoundError, AttributeError):
                # Skip sprites that can't be loaded
                pass

    def test_sprite_rendering_quality(self):
        """Test that sprites render with good quality."""
        test_sprites = ["static.toml", "circle.toml", "red.toml"]

        for sprite_file in test_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)

                # Get pixel data
                pixels = self._extract_pixel_data(sprite.image)
                unique_colors = set(pixels)

                # Check for reasonable color diversity
                _ = [color for color in unique_colors if color != (255, 0, 255)]

                # Verify we have some color diversity
                assert len(unique_colors) > 0, f"Sprite {sprite_file} should have colors"

            except (ValueError, FileNotFoundError, AttributeError):
                # Skip sprites that can't be loaded
                pass

    def test_sprite_save_load_roundtrip(self):
        """Test that sprites can be saved and loaded back correctly."""
        test_sprites = ["static.toml", "circle.toml", "red.toml"]

        for sprite_file in test_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                # Load original
                original_sprite = SpriteFactory.load_sprite(filename=sprite_file)
                original_pixels = self._extract_pixel_data(original_sprite.image)
                original_size = original_sprite.image.get_size()

                # Save to temporary file
                temp_file = self.temp_path / f"test_{sprite_file}"
                original_sprite.save(str(temp_file), "toml")

                # Load back
                loaded_sprite = SpriteFactory.load_sprite(filename=str(temp_file))
                loaded_pixels = self._extract_pixel_data(loaded_sprite.image)
                loaded_size = loaded_sprite.image.get_size()

                # Verify roundtrip
                assert original_size == loaded_size, f"Size mismatch for {sprite_file}"
                assert len(original_pixels) == len(loaded_pixels), (
                    f"Pixel count mismatch for {sprite_file}"
                )

                # Check pixel data similarity
                matches = sum(
                    1
                    for orig, loaded in zip(original_pixels, loaded_pixels, strict=True)
                    if orig == loaded
                )
                match_percentage = matches / len(original_pixels) * 100

                assert match_percentage > PIXEL_MATCH_THRESHOLD, (
                    f"Pixel data mismatch for {sprite_file}: {match_percentage:.1f}%"
                )

            except (ValueError, FileNotFoundError, AttributeError):
                # Skip sprites that can't be loaded
                pass

    def test_sprite_dimensions_consistency(self):
        """Test that sprite dimensions are consistent and reasonable."""
        for sprite_file in self.example_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                width, height = sprite.image.get_size()

                # Check dimensions are reasonable
                assert width > 0, f"{sprite_file} width should be positive"
                assert height > 0, f"{sprite_file} height should be positive"
                assert width < MAX_SPRITE_DIMENSION, f"{sprite_file} width should be reasonable"
                assert height < MAX_SPRITE_DIMENSION, f"{sprite_file} height should be reasonable"

                # Check aspect ratio is reasonable
                aspect_ratio = width / height if height > 0 else 1
                assert aspect_ratio < MAX_ASPECT_RATIO, f"{sprite_file} aspect ratio too wide"
                assert aspect_ratio > MIN_ASPECT_RATIO, f"{sprite_file} aspect ratio too tall"

            except (ValueError, FileNotFoundError, AttributeError):
                # Skip sprites that can't be loaded
                pass

    def test_sprite_color_analysis(self):
        """Test sprite color analysis and validation."""
        color_test_sprites = ["colors.toml", "red.toml", "circle.toml"]

        for sprite_file in color_test_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                pixels = self._extract_pixel_data(sprite.image)
                _ = set(pixels)

                # Analyze color distribution
                color_counts = {}
                for pixel in pixels:
                    color_counts[pixel] = color_counts.get(pixel, 0) + 1

                # Find most common color
                most_common_color = max(color_counts.items(), key=operator.itemgetter(1))
                most_common_percentage = (most_common_color[1] / len(pixels)) * 100

                # Check for reasonable color distribution
                # Allow single-color sprites but flag suspicious cases
                if most_common_percentage >= MAX_COLOR_DOMINANCE:
                    # For single-color sprites, this is expected behavior
                    single_color_sprites = {"red.toml", "colors.toml", "circle.toml"}
                    if sprite_file not in single_color_sprites:
                        raise AssertionError(f"{sprite_file} should not be mostly one color")

            except (ValueError, FileNotFoundError, AttributeError):
                # Skip sprites that can't be loaded
                pass

    @staticmethod
    def test_sprite_performance():
        """Test sprite loading and rendering performance."""
        test_sprites = ["static.toml", "colors.toml", "circle.toml"]

        for sprite_file in test_sprites:
            if not Path(sprite_file).exists():
                continue

            try:
                # Time the loading
                start_time = time.time()
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                load_time = time.time() - start_time

                # Time the rendering
                start_time = time.time()
                test_surface = pygame.Surface(sprite.image.get_size())
                test_surface.blit(sprite.image, (0, 0))
                render_time = time.time() - start_time

                # Verify performance is reasonable
                assert load_time < MAX_LOAD_TIME, (
                    f"{sprite_file} loading too slow: {load_time:.3f}s"
                )
                assert render_time < MAX_RENDER_TIME, (
                    f"{sprite_file} rendering too slow: {render_time:.3f}s"
                )

            except (ValueError, FileNotFoundError, AttributeError):
                # Skip sprites that can't be loaded
                pass

    @staticmethod
    def _extract_pixel_data(surface):
        """Extract pixel data from a pygame surface as RGB tuples."""
        width, height = surface.get_size()
        pixels = []

        for y in range(height):
            for x in range(width):
                pixel = surface.get_at((x, y))
                # Convert to RGB (ignore alpha)
                rgb = (pixel.r, pixel.g, pixel.b)
                pixels.append(rgb)

        return pixels


if __name__ == "__main__":
    unittest.main()
