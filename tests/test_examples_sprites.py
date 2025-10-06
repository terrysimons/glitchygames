"""Test suite for example sprites in glitchygames/examples/resources/sprites.

This module tests loading all the TOML sprite files from the examples directory
and verifies they work correctly with the TOML-only implementation.
"""

import tempfile
import time
import unittest
from pathlib import Path

import pygame
from glitchygames.sprites import SpriteFactory

# Constants for test thresholds
PIXEL_INTEGRITY_THRESHOLD = 95.0
MAX_REASONABLE_DIMENSION = 1000
MAX_ASPECT_RATIO = 10.0
MIN_ASPECT_RATIO = 0.1
MAX_LOAD_TIME = 1.0
MAX_RENDER_TIME = 0.1


class TestExamplesSprites(unittest.TestCase):
    """Test example sprites from the glitchygames/examples/resources/sprites directory."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

        # Path to the examples sprites directory
        self.sprites_dir = Path("glitchygames/examples/resources/sprites")

        # Get all TOML files in the directory
        self.toml_files = []
        if self.sprites_dir.exists():
            for file_path in self.sprites_dir.glob("*.toml"):
                self.toml_files.append(file_path)

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_load_all_toml_sprites(self):
        """Test that all TOML sprite files can be loaded."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        loaded_count = 0
        failed_count = 0
        results = []

        for sprite_file in self.toml_files:
            try:
                # Load the sprite
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
                assert sprite is not None, f"Failed to load {sprite_file.name}"

                # Verify basic properties
                assert sprite.image is not None, f"Sprite {sprite_file.name} should have an image"
                assert isinstance(sprite.image, pygame.Surface), (
                    f"Sprite {sprite_file.name} image should be a Surface"
                )

                # Check dimensions
                width, height = sprite.image.get_size()
                assert width > 0, f"Sprite {sprite_file.name} width should be positive"
                assert height > 0, f"Sprite {sprite_file.name} height should be positive"

                loaded_count += 1
                results.append((sprite_file.name, "SUCCESS", f"{width}x{height}"))

            except (ValueError, FileNotFoundError, AttributeError) as e:
                # Log expected errors and record as failed
                self.log.warning(f"Failed to load sprite {sprite_file.name}: {e}")
                failed_count += 1
                results.append((sprite_file.name, "FAILED", str(e)))
            except Exception as e:
                # Fail fast on unexpected errors
                self.fail(f"Unexpected error loading sprite {sprite_file.name}: {e}")

        # Verify we loaded at least some sprites
        assert loaded_count > 0, "Should load at least one example sprite"

    def test_sprite_pixel_integrity(self):
        """Test pixel data integrity for a sample of sprites."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        # Test a sample of sprites for pixel integrity
        test_sprites = [
            "battle_axe.toml",
            "berry_bush.toml",
            "big_heart.toml",
            "book.toml",
            "colors.toml",
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            try:
                # Load sprite
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))

                # Test pixel integrity
                original_pixels = self._extract_pixel_data(sprite.image)

                # Draw to test surface
                test_surface = pygame.Surface(sprite.image.get_size())
                test_surface.fill((0, 0, 0))
                test_surface.blit(sprite.image, (0, 0))

                drawn_pixels = self._extract_pixel_data(test_surface)

                # Calculate match percentage
                matches = sum(
                    1
                    for orig, drawn in zip(original_pixels, drawn_pixels, strict=True)
                    if orig == drawn
                )
                match_percentage = matches / len(original_pixels) * 100

                assert match_percentage > PIXEL_INTEGRITY_THRESHOLD, (
                    f"Pixel integrity too low for {sprite_name}: {match_percentage:.1f}%"
                )

            except (ValueError, FileNotFoundError, AttributeError) as e:
                # Log expected errors and skip
                self.log.warning(f"Skipping sprite {sprite_file.name} due to expected error: {e}")
                continue
            except Exception as e:
                # Fail fast on unexpected errors
                self.fail(f"Unexpected error processing sprite {sprite_file.name}: {e}")

    def test_sprite_dimensions_consistency(self):
        """Test that sprite dimensions are consistent and reasonable."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        # Test a sample of sprites
        test_sprites = [
            "battle_axe.toml",
            "berry_bush.toml",
            "big_heart.toml",
            "book.toml",
            "colors.toml",
            "dirt.toml",
            "grass1.toml",
            "key.toml",
            "sword.toml",
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
                width, height = sprite.image.get_size()

                # Check dimensions are reasonable
                assert width > 0, f"{sprite_name} width should be positive"
                assert height > 0, f"{sprite_name} height should be positive"
                assert width < MAX_REASONABLE_DIMENSION, f"{sprite_name} width should be reasonable"
                assert height < MAX_REASONABLE_DIMENSION, (
                    f"{sprite_name} height should be reasonable"
                )

                # Check aspect ratio is reasonable
                aspect_ratio = width / height if height > 0 else 1
                assert aspect_ratio < MAX_ASPECT_RATIO, f"{sprite_name} aspect ratio too wide"
                assert aspect_ratio > MIN_ASPECT_RATIO, f"{sprite_name} aspect ratio too tall"

            except (ValueError, FileNotFoundError, AttributeError) as e:
                # Log expected errors and skip
                self.log.warning(f"Skipping sprite {sprite_file.name} due to expected error: {e}")
                continue
            except Exception as e:
                # Fail fast on unexpected errors
                self.fail(f"Unexpected error processing sprite {sprite_file.name}: {e}")

    def test_animated_sprites(self):
        """Test animated sprites in the examples directory."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        # Look for animated sprites (colors.toml is known to be animated)
        animated_sprites = ["colors.toml"]

        for sprite_name in animated_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            try:
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))

                # Check if it's an animated sprite
                if hasattr(sprite, "animations"):
                    assert sprite.animations is not None, (
                        f"Animated sprite {sprite_name} should have animations"
                    )
                    assert len(sprite.animations) > 0, (
                        f"Animated sprite {sprite_name} should have at least one animation"
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

            except (ValueError, FileNotFoundError, AttributeError) as e:
                # Log expected errors and skip
                self.log.warning(f"Skipping sprite {sprite_file.name} due to expected error: {e}")
                continue
            except Exception as e:
                # Fail fast on unexpected errors
                self.fail(f"Unexpected error processing sprite {sprite_file.name}: {e}")

    def test_sprite_performance(self):
        """Test sprite loading and rendering performance."""
        if not self.sprites_dir.exists():
            self.skipTest(f"Sprites directory {self.sprites_dir} not found")

        # Test a sample of sprites for performance
        test_sprites = [
            "battle_axe.toml",
            "berry_bush.toml",
            "big_heart.toml",
            "book.toml",
            "colors.toml",
        ]

        for sprite_name in test_sprites:
            sprite_file = self.sprites_dir / sprite_name
            if not sprite_file.exists():
                continue

            try:
                # Time the loading
                start_time = time.time()
                sprite = SpriteFactory.load_sprite(filename=str(sprite_file))
                load_time = time.time() - start_time

                # Time the rendering
                start_time = time.time()
                test_surface = pygame.Surface(sprite.image.get_size())
                test_surface.blit(sprite.image, (0, 0))
                render_time = time.time() - start_time

                # Verify performance is reasonable
                assert load_time < MAX_LOAD_TIME, (
                    f"{sprite_name} loading too slow: {load_time:.3f}s"
                )
                assert render_time < MAX_RENDER_TIME, (
                    f"{sprite_name} rendering too slow: {render_time:.3f}s"
                )

            except (ValueError, FileNotFoundError, AttributeError) as e:
                # Log expected errors and skip
                self.log.warning(f"Skipping sprite {sprite_file.name} due to expected error: {e}")
                continue
            except Exception as e:
                # Fail fast on unexpected errors
                self.fail(f"Unexpected error processing sprite {sprite_file.name}: {e}")

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
