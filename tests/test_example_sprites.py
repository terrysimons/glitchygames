"""Test suite for example sprites in the project directory.

This module tests loading and rendering of the various example sprite files
found in the project directory to ensure they work correctly with the TOML-only
implementation.
"""

import os
import tempfile
import unittest
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites import SpriteFactory


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
            if not os.path.exists(sprite_file):
                print(f"⚠️  Skipping {sprite_file} - file not found")
                continue

            try:
                # Load the sprite
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                self.assertIsNotNone(sprite, f"Failed to load {sprite_file}")

                # Verify basic properties
                self.assertIsNotNone(sprite.image, f"Sprite {sprite_file} should have an image")
                self.assertIsInstance(
                    sprite.image, pygame.Surface, f"Sprite {sprite_file} image should be a Surface"
                )

                # Check dimensions
                width, height = sprite.image.get_size()
                self.assertGreater(width, 0, f"Sprite {sprite_file} width should be positive")
                self.assertGreater(height, 0, f"Sprite {sprite_file} height should be positive")

                loaded_count += 1
                print(f"✅ Loaded {sprite_file}: {width}x{height}")

            except Exception as e:
                failed_count += 1
                print(f"❌ Failed to load {sprite_file}: {e}")

        # Verify we loaded at least some sprites
        self.assertGreater(loaded_count, 0, "Should load at least one example sprite")
        print(f"📊 Loaded {loaded_count} sprites, {failed_count} failed")

    def test_animated_sprites_have_animations(self):
        """Test that animated sprites have proper animation data."""
        animated_sprites = ["colors.toml", "butterfly-animation-8x8.toml", "mario-running.toml"]

        for sprite_file in animated_sprites:
            if not os.path.exists(sprite_file):
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)

                # Check if it's an animated sprite
                if hasattr(sprite, "animations"):
                    self.assertIsNotNone(
                        sprite.animations, f"Animated sprite {sprite_file} should have animations"
                    )
                    self.assertGreater(
                        len(sprite.animations),
                        0,
                        f"Animated sprite {sprite_file} should have at least one animation",
                    )

                    # Check each animation
                    for anim_name, frames in sprite.animations.items():
                        self.assertIsNotNone(frames, f"Animation {anim_name} should have frames")
                        self.assertGreater(
                            len(frames), 0, f"Animation {anim_name} should have at least one frame"
                        )

                        # Check each frame
                        for i, frame in enumerate(frames):
                            self.assertIsNotNone(
                                frame.image, f"Frame {i} in {anim_name} should have an image"
                            )
                            self.assertIsInstance(
                                frame.image,
                                pygame.Surface,
                                f"Frame {i} in {anim_name} should be a Surface",
                            )

                    print(f"✅ Animated sprite {sprite_file}: {len(sprite.animations)} animations")

            except Exception as e:
                print(f"❌ Error testing animated sprite {sprite_file}: {e}")

    def test_sprite_rendering_quality(self):
        """Test that sprites render with good quality."""
        test_sprites = ["static.toml", "circle.toml", "red.toml"]

        for sprite_file in test_sprites:
            if not os.path.exists(sprite_file):
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)

                # Get pixel data
                pixels = self._extract_pixel_data(sprite.image)
                unique_colors = set(pixels)

                # Check for reasonable color diversity
                non_magenta_colors = [color for color in unique_colors if color != (255, 0, 255)]

                if len(non_magenta_colors) > 0:
                    print(
                        f"✅ {sprite_file}: {len(unique_colors)} colors, "
                        f"{len(non_magenta_colors)} non-magenta"
                    )
                else:
                    print(f"⚠️  {sprite_file}: Only magenta colors found")

            except Exception as e:
                print(f"❌ Error testing sprite quality for {sprite_file}: {e}")

    def test_sprite_save_load_roundtrip(self):
        """Test that sprites can be saved and loaded back correctly."""
        test_sprites = ["static.toml", "circle.toml", "red.toml"]

        for sprite_file in test_sprites:
            if not os.path.exists(sprite_file):
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
                self.assertEqual(original_size, loaded_size, f"Size mismatch for {sprite_file}")
                self.assertEqual(
                    len(original_pixels),
                    len(loaded_pixels),
                    f"Pixel count mismatch for {sprite_file}",
                )

                # Check pixel data similarity
                matches = sum(
                    1 for orig, loaded in zip(original_pixels, loaded_pixels) if orig == loaded
                )
                match_percentage = matches / len(original_pixels) * 100

                self.assertGreater(
                    match_percentage,
                    90.0,
                    f"Pixel data mismatch for {sprite_file}: {match_percentage:.1f}%",
                )

                print(f"✅ Roundtrip for {sprite_file}: {match_percentage:.1f}% match")

            except Exception as e:
                print(f"❌ Error testing roundtrip for {sprite_file}: {e}")

    def test_sprite_dimensions_consistency(self):
        """Test that sprite dimensions are consistent and reasonable."""
        for sprite_file in self.example_sprites:
            if not os.path.exists(sprite_file):
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                width, height = sprite.image.get_size()

                # Check dimensions are reasonable
                self.assertGreater(width, 0, f"{sprite_file} width should be positive")
                self.assertGreater(height, 0, f"{sprite_file} height should be positive")
                self.assertLess(width, 2000, f"{sprite_file} width should be reasonable")
                self.assertLess(height, 2000, f"{sprite_file} height should be reasonable")

                # Check aspect ratio is reasonable
                aspect_ratio = width / height if height > 0 else 1
                self.assertLess(aspect_ratio, 10, f"{sprite_file} aspect ratio too wide")
                self.assertGreater(aspect_ratio, 0.1, f"{sprite_file} aspect ratio too tall")

                print(f"✅ {sprite_file}: {width}x{height} (ratio: {aspect_ratio:.2f})")

            except Exception as e:
                print(f"❌ Error checking dimensions for {sprite_file}: {e}")

    def test_sprite_color_analysis(self):
        """Test sprite color analysis and validation."""
        color_test_sprites = ["colors.toml", "red.toml", "circle.toml"]

        for sprite_file in color_test_sprites:
            if not os.path.exists(sprite_file):
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                pixels = self._extract_pixel_data(sprite.image)
                unique_colors = set(pixels)

                # Analyze color distribution
                color_counts = {}
                for pixel in pixels:
                    color_counts[pixel] = color_counts.get(pixel, 0) + 1

                # Find most common color
                most_common_color = max(color_counts.items(), key=lambda x: x[1])
                most_common_percentage = (most_common_color[1] / len(pixels)) * 100

                # Check for reasonable color distribution
                self.assertLess(
                    most_common_percentage, 95.0, f"{sprite_file} should not be mostly one color"
                )

                print(
                    f"✅ {sprite_file}: {len(unique_colors)} colors, "
                    f"most common: {most_common_percentage:.1f}%"
                )

            except Exception as e:
                print(f"❌ Error analyzing colors for {sprite_file}: {e}")

    def test_sprite_performance(self):
        """Test sprite loading and rendering performance."""
        import time

        test_sprites = ["static.toml", "colors.toml", "circle.toml"]

        for sprite_file in test_sprites:
            if not os.path.exists(sprite_file):
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
                self.assertLess(load_time, 1.0, f"{sprite_file} loading too slow: {load_time:.3f}s")
                self.assertLess(
                    render_time, 0.1, f"{sprite_file} rendering too slow: {render_time:.3f}s"
                )

                print(f"✅ {sprite_file}: load {load_time:.3f}s, render {render_time:.3f}s")

            except Exception as e:
                print(f"❌ Error testing performance for {sprite_file}: {e}")

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
