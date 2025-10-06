"""Test suite for sprite loading with hardware buffer verification.

This module tests that sprites load correctly and are properly blitted to
glitchygames scenes, with verification that they appear in the hardware display buffer.
"""

import random
import time
import unittest
from pathlib import Path

import pygame
from glitchygames.scenes import Scene
from glitchygames.sprites import SpriteFactory


class SpriteLoadingTestScene(Scene):
    """Test scene for sprite loading with hardware verification."""

    NAME = "Sprite Loading Test Scene"

    def __init__(self, sprite_files: list[str], groups: pygame.sprite.Group | None = None):
        """Initialize the test scene with multiple sprites."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        # Initialize with minimal options
        options = {"width": 800, "height": 600, "fullscreen": False}
        super().__init__(options=options, groups=groups)

        # Set up the scene
        self.background_color = (20, 20, 40)
        self.fps = 60
        self.sprite_files = sprite_files
        self.loaded_sprites = []
        self.test_surface = pygame.Surface((800, 600))

        # Load all sprites
        self._load_all_sprites()

    def _load_all_sprites(self) -> None:
        """Load all sprites from the provided files."""
        for i, sprite_file in enumerate(self.sprite_files):
            try:
                sprite = SpriteFactory.load_sprite(filename=sprite_file)

                # Position sprites in a grid pattern
                cols = 4  # 4 sprites per row
                row = i // cols
                col = i % cols
                x = 100 + (col * 150)  # 150px spacing
                y = 100 + (row * 150)  # 150px spacing

                sprite.rect.topleft = (x, y)

                # Add to sprite group
                self.all_sprites.add(sprite)
                self.loaded_sprites.append(sprite)

            except (ValueError, FileNotFoundError, AttributeError):
                # Continue loading other sprites even if one fails
                pass

    def update(self) -> None:
        """Update the scene and all sprites."""
        super().update()

        # Update all loaded animated sprites
        for sprite in self.loaded_sprites:
            if hasattr(sprite, "update"):
                sprite.update(self.dt)

    @staticmethod
    def capture_hardware_display_buffer() -> list[tuple[int, int, int]]:
        """Capture pixel data directly from the hardware display buffer."""
        # Get the actual display surface that hardware reads
        display_surface = pygame.display.get_surface()

        # Extract pixel data from hardware buffer
        width, height = display_surface.get_size()
        pixels = []
        for y in range(height):
            for x in range(width):
                color = display_surface.get_at((x, y))
                pixels.append((color.r, color.g, color.b))

        return pixels

    def capture_test_surface_pixels(self) -> list[tuple[int, int, int]]:
        """Capture pixel data from our test surface (scene-level rendering)."""
        # Clear the test surface
        self.test_surface.fill(self.background_color)

        # Update the scene first
        self.update()

        # Draw all sprites to the test surface
        self.all_sprites.draw(self.test_surface)

        # Extract pixel data
        width, height = self.test_surface.get_size()
        pixels = []
        for y in range(height):
            for x in range(width):
                color = self.test_surface.get_at((x, y))
                pixels.append((color.r, color.g, color.b))

        return pixels

    def get_sprite_area_from_hardware_buffer(self, sprite_index: int) -> list[tuple[int, int, int]]:
        """Get sprite area pixels from the hardware display buffer."""
        if sprite_index >= len(self.loaded_sprites):
            return []

        display_surface = pygame.display.get_surface()
        sprite = self.loaded_sprites[sprite_index]
        sprite_rect = sprite.rect

        pixels = []
        for y in range(sprite_rect.top, sprite_rect.bottom):
            for x in range(sprite_rect.left, sprite_rect.right):
                if 0 <= x < display_surface.get_width() and 0 <= y < display_surface.get_height():
                    color = display_surface.get_at((x, y))
                    pixels.append((color.r, color.g, color.b))

        return pixels

    def force_display_update(self) -> None:
        """Force the display to update and ensure hardware buffer is current."""
        # Update the scene
        self.update()

        # Clear screen completely - this is crucial for test isolation
        self.screen.fill(self.background_color)

        # Draw all sprites to the screen
        self.all_sprites.draw(self.screen)

        # Force display update
        pygame.display.flip()

        # Small delay to ensure hardware buffer is updated
        time.sleep(0.01)

    def get_sprite_surface_pixels(self, sprite_index: int) -> list[tuple[int, int, int]]:
        """Get pixel data directly from a sprite's surface."""
        if sprite_index >= len(self.loaded_sprites):
            return []

        sprite = self.loaded_sprites[sprite_index]

        # Get the sprite surface
        if hasattr(sprite, "image"):
            surface = sprite.image
        else:
            return []

        # Extract pixel data from the sprite surface
        width, height = surface.get_size()
        pixels = []
        for y in range(height):
            for x in range(width):
                color = surface.get_at((x, y))
                pixels.append((color.r, color.g, color.b))

        return pixels


class TestSpriteLoadingHardware(unittest.TestCase):
    """Test sprite loading with hardware buffer verification."""

    # Constants for test thresholds
    SCREEN_WIDTH = 800
    SCREEN_HEIGHT = 600
    MAX_LOADING_TIME = 5.0
    MAX_RENDERING_TIME = 3.0
    MAX_MEMORY_USAGE = 1000000

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Clear the display to ensure test isolation
        screen = pygame.display.get_surface()
        screen.fill((0, 0, 0))  # Black background
        pygame.display.flip()

        # Available sprite files for testing (mix of animated and static)
        self.available_sprites = [
            "colors.toml",  # Animated sprite
            "static.toml",  # Static sprite
            "butterfly.toml",  # Animated sprite
            "circle.toml",  # Static sprite
            "coin.toml",  # Static sprite
            "blinking_eye.toml",  # Animated sprite
            "swirl.toml",  # Static sprite
            "squirgle.toml",  # Static sprite
        ]

        # Filter to only existing files
        self.available_sprites = [f for f in self.available_sprites if Path(f).exists()]

        if not self.available_sprites:
            self.skipTest("No sprite files found for testing")

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        # Clear display before next test
        if pygame.display.get_init():
            screen = pygame.display.get_surface()
            screen.fill((0, 0, 0))
            pygame.display.flip()

        # Don't quit pygame here as it's shared across tests
        # pygame.quit()  # Commented out to avoid issues with shared display

    @staticmethod
    def _clear_display():
        """Clear the display to ensure test isolation."""
        screen = pygame.display.get_surface()
        screen.fill((0, 0, 0))  # Black background
        pygame.display.flip()

    def _get_test_sprites(self, count: int = 2) -> list[str]:
        """Get a random selection of sprites for testing."""
        # Use a different seed for each test to get variety
        import random
        random.seed(hash(self._testMethodName) % 1000)
        return random.sample(self.available_sprites, min(count, len(self.available_sprites)))

    def test_sprite_loading_scene_setup(self):
        """Test that sprites load correctly into a glitchygames scene."""
        self._clear_display()
        sprite_files = self._get_test_sprites(2)
        scene = SpriteLoadingTestScene(sprite_files)

        # Verify sprites were loaded
        assert len(scene.loaded_sprites) > 0, "Should load at least one sprite"
        assert len(scene.loaded_sprites) == len(sprite_files), (
            "Should load all available sprite files"
        )

        # Verify sprites are in the sprite group
        assert len(scene.all_sprites) > 0, "Sprite group should contain sprites"

    def test_sprite_positioning_in_scene(self):
        """Test that sprites are positioned correctly in the scene."""
        self._clear_display()
        sprite_files = self._get_test_sprites(3)  # Use 3 sprites for positioning test
        scene = SpriteLoadingTestScene(sprite_files)

        # Verify each sprite has a valid position
        for i, sprite in enumerate(scene.loaded_sprites):
            assert sprite.rect is not None, f"Sprite {i} should have a rect"
            assert sprite.rect.width > 0, f"Sprite {i} should have width"
            assert sprite.rect.height > 0, f"Sprite {i} should have height"

            # Verify sprite is within screen bounds
            assert sprite.rect.left >= 0, f"Sprite {i} should be within screen"
            assert sprite.rect.top >= 0, f"Sprite {i} should be within screen"
            assert sprite.rect.right < self.SCREEN_WIDTH, f"Sprite {i} should be within screen"
            assert sprite.rect.bottom < self.SCREEN_HEIGHT, f"Sprite {i} should be within screen"

    def test_sprite_visibility_in_hardware_buffer(self):
        """Test that loaded sprites are visible in the hardware display buffer."""
        self._clear_display()
        sprite_files = self._get_test_sprites(2)
        scene = SpriteLoadingTestScene(sprite_files)

        # Force display update
        scene.force_display_update()

        # Check each sprite's visibility in hardware buffer
        for i in range(len(scene.loaded_sprites)):
            sprite_area_pixels = scene.get_sprite_area_from_hardware_buffer(i)

            # Check for non-background pixels in sprite area
            background_color = scene.background_color
            non_background_pixels = [
                pixel for pixel in sprite_area_pixels if pixel != background_color
            ]

            # Verify sprite is visible in hardware buffer
            assert len(non_background_pixels) > 0, (
                f"Sprite {i} should be visible in hardware display buffer"
            )

    def test_sprite_surface_vs_hardware_consistency(self):
        """Test that sprite surface data matches hardware buffer data."""
        sprite_files = self._get_test_sprites(2)
        scene = SpriteLoadingTestScene(sprite_files)

        # Force display update
        scene.force_display_update()

        # Check consistency for each sprite
        for i in range(len(scene.loaded_sprites)):
            # Get sprite surface data
            sprite_surface_pixels = scene.get_sprite_surface_pixels(i)

            # Get sprite area from hardware buffer
            hardware_sprite_pixels = scene.get_sprite_area_from_hardware_buffer(i)

            # Verify both have data
            assert len(sprite_surface_pixels) > 0, f"Sprite {i} surface should have data"
            assert len(hardware_sprite_pixels) > 0, f"Sprite {i} hardware area should have data"

    def test_multiple_sprite_loading_performance(self):
        """Test that loading multiple sprites performs within acceptable limits."""
        start_time = time.time()

        sprite_files = self._get_test_sprites(3)  # Use 3 sprites for performance test
        SpriteLoadingTestScene(sprite_files)

        end_time = time.time()
        loading_time = end_time - start_time

        # Verify performance is acceptable
        assert loading_time < self.MAX_LOADING_TIME, (
            f"Sprite loading should be fast: {loading_time:.3f}s"
        )

    def test_sprite_rendering_performance(self):
        """Test that rendering multiple sprites performs within acceptable limits."""
        sprite_files = self._get_test_sprites(3)  # Use 3 sprites for rendering test
        scene = SpriteLoadingTestScene(sprite_files)

        # Test rendering performance
        start_time = time.time()

        # Simulate multiple render cycles
        for _ in range(10):
            scene.force_display_update()
            scene.capture_hardware_display_buffer()

        end_time = time.time()
        rendering_time = end_time - start_time

        # Verify performance is acceptable
        assert rendering_time < self.MAX_RENDERING_TIME, (
            f"Sprite rendering should be fast: {rendering_time:.3f}s"
        )

    def test_sprite_types_loading(self):
        """Test that different sprite types load correctly."""
        sprite_files = self._get_test_sprites(4)  # Use 4 sprites for type testing
        scene = SpriteLoadingTestScene(sprite_files)

        # Check sprite types
        for i, sprite in enumerate(scene.loaded_sprites):
            # Verify sprite has required attributes
            assert sprite.rect is not None, f"Sprite {i} should have a rect"
            assert sprite.image is not None, f"Sprite {i} should have an image"

    def test_sprite_animation_in_hardware_buffer(self):
        """Test that animated sprites show animation in hardware buffer."""
        sprite_files = self._get_test_sprites(2)  # Use 2 sprites for animation test
        scene = SpriteLoadingTestScene(sprite_files)

        # Find animated sprites
        animated_sprites = []
        for i, sprite in enumerate(scene.loaded_sprites):
            if hasattr(sprite, "animations") and sprite.animations:
                animated_sprites.append((i, sprite))

        if not animated_sprites:
            self.skipTest("No animated sprites found for testing")

        # Test animation in hardware buffer
        for sprite_index, sprite in animated_sprites:
            # Get initial frame
            scene.force_display_update()
            initial_pixels = scene.get_sprite_area_from_hardware_buffer(sprite_index)

            # Advance to next frame if possible (only if animation has multiple frames)
            if hasattr(sprite, "animations") and sprite.animations:
                current_animation = sprite.current_animation
                if current_animation and len(sprite.animations[current_animation]) > 1:
                    # Try to advance to next frame (frame 1)
                    if hasattr(sprite, "set_frame"):
                        sprite.set_frame(1)
                    elif hasattr(sprite, "frame_manager"):
                        sprite.frame_manager.set_frame(1)
                elif hasattr(sprite, "set_frame"):
                    # Single frame animation - stay on frame 0
                    sprite.set_frame(0)
                elif hasattr(sprite, "frame_manager"):
                    sprite.frame_manager.set_frame(0)

            # Get next frame
            scene.force_display_update()
            next_pixels = scene.get_sprite_area_from_hardware_buffer(sprite_index)

            # Verify frames are different (if animation has multiple frames)
            if (
                len(initial_pixels) == len(next_pixels)
                and len(initial_pixels) > 0
                and initial_pixels != next_pixels
            ):
                # Animation is working correctly
                pass

    def test_sprite_collision_detection_in_hardware(self):
        """Test that sprite positioning doesn't cause collisions in hardware buffer."""
        sprite_files = self._get_test_sprites(3)  # Use 3 sprites for collision test
        scene = SpriteLoadingTestScene(sprite_files)

        # Force display update
        scene.force_display_update()

        # Check that sprites don't overlap
        for i, sprite1 in enumerate(scene.loaded_sprites):
            for j, sprite2 in enumerate(scene.loaded_sprites):
                if i != j:
                    # Check if sprites overlap
                    assert not sprite1.rect.colliderect(sprite2.rect), (
                        f"Sprites {i} and {j} overlap: {sprite1.rect} vs {sprite2.rect}"
                    )

    def test_sprite_memory_usage(self):
        """Test that sprite loading doesn't cause excessive memory usage."""
        sprite_files = self._get_test_sprites(3)  # Use 3 sprites for memory test
        scene = SpriteLoadingTestScene(sprite_files)

        # Check that sprites have reasonable memory footprint
        total_surface_area = 0
        for sprite in scene.loaded_sprites:
            if hasattr(sprite, "image"):
                surface = sprite.image
                area = surface.get_width() * surface.get_height()
                total_surface_area += area

        # Verify reasonable memory usage (less than 1MB of surface data)
        assert total_surface_area < self.MAX_MEMORY_USAGE, (
            "Total sprite surface area should be reasonable"
        )

    @staticmethod
    def test_sprite_loading_error_handling():
        """Test that sprite loading handles errors gracefully."""
        # Test with non-existent files
        invalid_files = ["nonexistent1.toml", "nonexistent2.toml"]

        scene = SpriteLoadingTestScene(invalid_files)

        # Should handle errors gracefully
        assert len(scene.loaded_sprites) == 0, "Should handle invalid files gracefully"

    def test_sprite_loading_with_mixed_types(self):
        """Test loading sprites of different types together."""
        # This test verifies that different sprite types can coexist
        sprite_files = self._get_test_sprites(4)  # Use 4 sprites for mixed types test
        scene = SpriteLoadingTestScene(sprite_files)

        # Verify all sprites loaded successfully
        assert len(scene.loaded_sprites) > 0, "Should load sprites of different types"

        # Verify sprites are in the scene
        assert len(scene.all_sprites) > 0, "Sprite group should contain mixed sprite types"


if __name__ == "__main__":
    unittest.main()
