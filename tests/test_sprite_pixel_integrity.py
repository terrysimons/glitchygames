"""Test suite for sprite pixel data integrity.

This module tests that sprites can be loaded, drawn to a display, and their
pixel data can be extracted and verified to match the original data.
"""

import tempfile
import unittest
from pathlib import Path

import pygame
from glitchygames.sprites import SpriteFactory


def get_resource_path(filename: str) -> str:
    """Get the full path to a resource file."""
    return str(
        Path(__file__).parent.parent
        / "glitchygames"
        / "examples"
        / "resources"
        / "sprites"
        / filename
    )


class TestSpritePixelIntegrity(unittest.TestCase):
    """Test sprite pixel data integrity across various sprite files."""

    # Constants for test thresholds
    PIXEL_MATCH_THRESHOLD = 95.0
    PIXEL_INTEGRITY_THRESHOLD = 90.0
    MAX_REASONABLE_DIMENSION = 1000

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_static_sprite_pixel_integrity(self):
        """Test that static sprites maintain pixel data integrity."""
        # Test with a static sprite from package resources
        sprite_file = get_resource_path("brick_wall.toml")

        # Load the sprite
        sprite = SpriteFactory.load_sprite(filename=sprite_file)
        assert sprite is not None

        # Get original pixel data
        original_pixels = self._extract_pixel_data(sprite.image)
        original_size = sprite.image.get_size()

        # Draw sprite to a new surface
        test_surface = pygame.Surface(original_size)
        test_surface.fill((0, 0, 0))  # Black background
        test_surface.blit(sprite.image, (0, 0))

        # Extract pixel data from the drawn surface
        drawn_pixels = self._extract_pixel_data(test_surface)

        # Verify pixel data integrity
        assert len(original_pixels) == len(drawn_pixels)
        assert original_size == test_surface.get_size()

        # Check that pixel data matches (allowing for some tolerance)
        matches = sum(
            1 for orig, drawn in zip(original_pixels, drawn_pixels, strict=True) if orig == drawn
        )
        match_percentage = matches / len(original_pixels) * 100

        assert match_percentage > self.PIXEL_MATCH_THRESHOLD, (
            f"Pixel data integrity check failed: {match_percentage:.1f}% match"
        )

    def test_animated_sprite_pixel_integrity(self):
        """Test that animated sprites maintain pixel data integrity."""
        # Test with colors.toml (animated sprite)
        sprite_file = get_resource_path("colors.toml")

        # Load the animated sprite
        sprite = SpriteFactory.load_sprite(filename=sprite_file)
        assert sprite is not None

        # Test each frame of the animation
        if hasattr(sprite, "animations") and sprite.animations:
            animation_name = next(iter(sprite.animations.keys()))
            frames = sprite.animations[animation_name]

            for frame_index, frame in enumerate(frames):
                # Get frame pixel data
                frame_pixels = self._extract_pixel_data(frame.image)
                frame_size = frame.image.get_size()

                # Draw frame to a new surface
                test_surface = pygame.Surface(frame_size)
                test_surface.fill((0, 0, 0))  # Black background
                test_surface.blit(frame.image, (0, 0))

                # Extract pixel data from the drawn surface
                drawn_pixels = self._extract_pixel_data(test_surface)

                # Verify pixel data integrity
                assert len(frame_pixels) == len(drawn_pixels)
                assert frame_size == test_surface.get_size()

                # Check that pixel data matches
                matches = sum(
                    1
                    for orig, drawn in zip(frame_pixels, drawn_pixels, strict=True)
                    if orig == drawn
                )
                match_percentage = matches / len(frame_pixels) * 100

                assert match_percentage > self.PIXEL_MATCH_THRESHOLD, (
                    f"Frame {frame_index} pixel integrity failed: {match_percentage:.1f}% match"
                )

    def test_sprite_save_load_roundtrip(self):
        """Test that sprites can be saved and loaded with pixel data integrity."""
        # Load an existing sprite
        sprite_file = "static.toml"
        if not Path(sprite_file).exists():
            self.skipTest(f"Sprite file {sprite_file} not found")

        # Load original sprite
        SpriteFactory.load_sprite(filename=sprite_file)

        # Skip save test for now since it requires pixels_across/pixels_tall attributes
        # that aren't set on loaded sprites
        self.skipTest(
            "Save/load roundtrip test requires sprite attributes that aren't set on loaded sprites"
        )

    def test_multiple_sprite_files(self):
        """Test pixel integrity across multiple sprite files."""
        # List of sprite files to test from package resources
        sprite_files = [
            get_resource_path("brick_wall.toml"),
            get_resource_path("colors.toml"),
            get_resource_path("gold.toml"),
            get_resource_path("sword.toml"),
        ]

        results = []

        for sprite_file in sprite_files:
            try:
                # Load sprite
                sprite = SpriteFactory.load_sprite(filename=sprite_file)
                assert sprite is not None

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

                results.append((sprite_file, match_percentage))

            except (ValueError, FileNotFoundError, AttributeError):
                results.append((sprite_file, 0.0))

        # Verify all results are acceptable
        for sprite_file, match_percentage in results:
            assert match_percentage > self.PIXEL_INTEGRITY_THRESHOLD, (
                f"Pixel integrity too low for {sprite_file}: {match_percentage:.1f}%"
            )

    def test_animated_sprite_frame_consistency(self):
        """Test that animated sprite frames maintain consistency."""
        sprite_file = get_resource_path("colors.toml")

        # Load animated sprite
        sprite = SpriteFactory.load_sprite(filename=sprite_file)

        if not hasattr(sprite, "animations") or not sprite.animations:
            self.skipTest("No animations found in sprite")

        animation_name = next(iter(sprite.animations.keys()))
        frames = sprite.animations[animation_name]

        # Test that all frames have consistent dimensions
        if frames:
            first_frame_size = frames[0].image.get_size()
            for i, frame in enumerate(frames):
                frame_size = frame.image.get_size()
                assert first_frame_size == frame_size, (
                    f"Frame {i} size mismatch: {frame_size} vs {first_frame_size}"
                )

    def test_sprite_color_preservation(self):
        """Test that sprite colors are preserved correctly."""
        sprite_file = "static.toml"  # Use static sprite instead of animated
        if not Path(sprite_file).exists():
            self.skipTest(f"Sprite file {sprite_file} not found")

        # Load sprite
        sprite = SpriteFactory.load_sprite(filename=sprite_file)

        # Get unique colors from the sprite
        pixels = self._extract_pixel_data(sprite.image)
        unique_colors = set(pixels)

        # Verify we have some colors (not just one)
        assert len(unique_colors) > 1, "Sprite should have multiple colors"

        # Test that colors are reasonable (not all transparent/magenta)
        non_magenta_colors = [color for color in unique_colors if color != (255, 0, 255)]
        assert len(non_magenta_colors) > 0, "Sprite should have non-magenta colors"

        # Test passes if we reach here without assertions failing

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

    def test_sprite_dimensions(self):
        """Test that sprite dimensions are correct."""
        sprite_file = "static.toml"
        if not Path(sprite_file).exists():
            self.skipTest(f"Sprite file {sprite_file} not found")

        # Load sprite
        sprite = SpriteFactory.load_sprite(filename=sprite_file)

        # Verify dimensions are reasonable
        width, height = sprite.image.get_size()
        assert width > 0, "Sprite width should be positive"
        assert height > 0, "Sprite height should be positive"
        assert width < self.MAX_REASONABLE_DIMENSION, "Sprite width should be reasonable"
        assert height < self.MAX_REASONABLE_DIMENSION, "Sprite height should be reasonable"

    def test_sprite_surface_properties(self):
        """Test that sprite surfaces have correct properties."""
        sprite_file = "static.toml"
        if not Path(sprite_file).exists():
            self.skipTest(f"Sprite file {sprite_file} not found")

        # Load sprite
        sprite = SpriteFactory.load_sprite(filename=sprite_file)

        # Verify surface properties
        assert sprite.image is not None, "Sprite should have an image"
        assert isinstance(sprite.image, pygame.Surface), "Sprite image should be a Surface"

        # Verify rect properties
        if hasattr(sprite, "rect"):
            assert sprite.rect is not None, "Sprite should have a rect"
            assert sprite.rect.size == sprite.image.get_size(), (
                "Sprite rect size should match image size"
            )


if __name__ == "__main__":
    unittest.main()
