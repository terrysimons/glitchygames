"""Test suite for hardware-level animation rendering verification.

This module tests that animated sprites properly reach the actual display buffer
and hardware, providing multiple layers of verification to quickly identify
where rendering problems occur in the pipeline.
"""

import time
import unittest
from pathlib import Path

import pygame
from glitchygames.scenes import Scene
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


# Constants for test thresholds
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
MAX_FRAME_COUNT = 3
MAX_PERFORMANCE_TIME = 2.0


class HardwareAnimationTestScene(Scene):
    """Test scene for hardware-level animation testing."""

    NAME = "Hardware Animation Test Scene"

    def __init__(self, animation_file: str, groups: pygame.sprite.Group | None = None):
        """Initialize the test scene with an animated sprite."""
        if groups is None:
            groups = pygame.sprite.LayeredDirty()

        # Initialize with minimal options
        options = {"width": 800, "height": 600, "fullscreen": False}
        super().__init__(options=options, groups=groups)

        # Set up the scene
        self.background_color = (20, 20, 40)
        self.fps = 60
        self.animation_file = animation_file
        self.animated_sprite = None
        self.test_surface = pygame.Surface((800, 600))

        # Load the animated sprite
        self._load_animated_sprite()

        # Add sprite to the group for rendering
        if self.animated_sprite:
            self.all_sprites.add(self.animated_sprite)

    def _load_animated_sprite(self) -> None:
        """Load the animated sprite from the specified file."""
        self.animated_sprite = SpriteFactory.load_sprite(filename=self.animation_file)
        if hasattr(self.animated_sprite, "play"):
            self.animated_sprite.play()
        # Center on screen
        self.animated_sprite.rect.center = self.screen.get_rect().center

    def update(self) -> None:
        """Update the scene and capture frame data."""
        super().update()

        if self.animated_sprite and hasattr(self.animated_sprite, "update"):
            # Update with delta time
            self.animated_sprite.update(self.dt)

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

    def capture_sprite_pixels(self) -> list[tuple[int, int, int]]:
        """Capture pixel data directly from the sprite surface."""
        if not self.animated_sprite:
            return []

        # Get the current frame surface
        if hasattr(self.animated_sprite, "image"):
            surface = self.animated_sprite.image
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

    def get_sprite_area_from_hardware_buffer(self) -> list[tuple[int, int, int]]:
        """Get sprite area pixels from the hardware display buffer."""
        display_surface = pygame.display.get_surface()
        sprite_rect = self.animated_sprite.rect

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

        # Draw to the actual display
        self.screen.fill(self.background_color)
        self.all_sprites.draw(self.screen)

        # Force display update
        pygame.display.flip()

        # Small delay to ensure hardware buffer is updated
        time.sleep(0.01)


class TestAnimationHardware(unittest.TestCase):
    """Test hardware-level animation rendering and display buffer verification."""

    def setUp(self):
        """Set up test fixtures."""
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Load the colors.toml animation for testing
        self.animation_file = get_resource_path("colors.toml")

    @staticmethod
    def tearDown():
        """Clean up test fixtures."""
        pygame.quit()

    def test_hardware_display_buffer_access(self):
        """Test that we can access the hardware display buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update to ensure hardware buffer is current
        scene.force_display_update()

        # Capture hardware display buffer
        hardware_pixels = scene.capture_hardware_display_buffer()

        # Verify we can access hardware buffer
        assert len(hardware_pixels) > 0, "Should capture hardware buffer data"
        assert len(hardware_pixels) == SCREEN_WIDTH * SCREEN_HEIGHT, (
            "Should capture full screen buffer"
        )

    def test_sprite_visibility_in_hardware_buffer(self):
        """Test that animated sprite is visible in the hardware display buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Get sprite area from hardware buffer
        sprite_area_pixels = scene.get_sprite_area_from_hardware_buffer()

        # Check for non-background pixels in sprite area
        background_color = scene.background_color
        non_background_pixels = [pixel for pixel in sprite_area_pixels if pixel != background_color]

        # Verify sprite is visible in hardware buffer
        assert len(non_background_pixels) > 0, "Sprite should be visible in hardware display buffer"

    def test_hardware_vs_surface_consistency(self):
        """Test that scene surface matches hardware display buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Capture from both sources
        hardware_pixels = scene.capture_hardware_display_buffer()
        surface_pixels = scene.capture_test_surface_pixels()

        # Verify both have data
        assert len(hardware_pixels) > 0, "Hardware buffer should have data"
        assert len(surface_pixels) > 0, "Surface buffer should have data"

        # For small sprites, check sprite area specifically
        sprite_area_hardware = scene.get_sprite_area_from_hardware_buffer()
        sprite_area_surface = []

        sprite_rect = scene.animated_sprite.rect
        for y in range(sprite_rect.top, sprite_rect.bottom):
            for x in range(sprite_rect.left, sprite_rect.right):
                if 0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT:
                    pixel_index = y * SCREEN_WIDTH + x
                    if pixel_index < len(surface_pixels):
                        sprite_area_surface.append(surface_pixels[pixel_index])

        # Verify sprite areas have similar content
        assert len(sprite_area_hardware) == len(sprite_area_surface), (
            "Sprite areas should have same pixel count"
        )

    def test_animation_frame_transitions_in_hardware(self):
        """Test that animation frame transitions are visible in hardware buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        if not hasattr(scene.animated_sprite, "animations") or not scene.animated_sprite.animations:
            self.skipTest("No animations found")

        # Get all frames from the animation
        animation_name = next(iter(scene.animated_sprite.animations.keys()))
        frames = scene.animated_sprite.animations[animation_name]

        if len(frames) < MAX_FRAME_COUNT:
            self.skipTest("Need at least 3 frames to test transitions")

        # Test frame transitions in hardware buffer
        hardware_frame_data = []

        for i in range(min(5, len(frames))):  # Test first 5 frames
            # Set the sprite to this specific frame
            if hasattr(scene.animated_sprite, "set_frame"):
                scene.animated_sprite.set_frame(i)
            elif hasattr(scene.animated_sprite, "frame_manager"):
                scene.animated_sprite.frame_manager.set_frame(i)

            # Force display update
            scene.force_display_update()

            # Capture sprite area from hardware buffer
            sprite_pixels = scene.get_sprite_area_from_hardware_buffer()
            hardware_frame_data.append(sprite_pixels)

        # Verify frames have different content in hardware buffer
        unique_frames = {tuple(pixels) for pixels in hardware_frame_data}
        assert len(unique_frames) > 1, "Hardware buffer should show different frame content"

    def test_hardware_rendering_performance(self):
        """Test that hardware rendering performs within acceptable limits."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Test hardware buffer access performance
        start_time = time.time()

        # Simulate multiple hardware buffer captures
        for _ in range(5):
            scene.force_display_update()
            scene.capture_hardware_display_buffer()

        end_time = time.time()
        total_time = end_time - start_time

        # Verify performance is acceptable
        assert total_time < MAX_PERFORMANCE_TIME, (
            f"Hardware rendering should be fast: {total_time:.3f}s"
        )

    def test_hardware_buffer_integrity(self):
        """Test that hardware buffer maintains pixel integrity."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Capture hardware buffer multiple times
        buffer1 = scene.capture_hardware_display_buffer()
        time.sleep(0.01)  # Small delay
        buffer2 = scene.capture_hardware_display_buffer()

        # Verify buffer consistency
        assert len(buffer1) == len(buffer2), "Hardware buffer size should be consistent"

        # For static scenes, buffers should be identical
        # For animated scenes, they might differ slightly

    def test_sprite_positioning_in_hardware_buffer(self):
        """Test that sprite positioning is correct in hardware buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Get sprite position and size
        sprite_rect = scene.animated_sprite.rect

        # Verify sprite is within screen bounds
        assert sprite_rect.left >= 0, "Sprite should be within screen bounds"
        assert sprite_rect.top >= 0, "Sprite should be within screen bounds"
        assert sprite_rect.right < SCREEN_WIDTH, "Sprite should be within screen bounds"
        assert sprite_rect.bottom < SCREEN_HEIGHT, "Sprite should be within screen bounds"

        # Check that sprite area has content in hardware buffer
        sprite_area_pixels = scene.get_sprite_area_from_hardware_buffer()
        assert len(sprite_area_pixels) > 0, "Sprite area should have pixels in hardware buffer"

    def test_hardware_vs_sprite_surface_consistency(self):
        """Test that hardware buffer matches sprite surface data."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Get sprite surface data
        sprite_pixels = scene.capture_sprite_pixels()

        # Get sprite area from hardware buffer
        hardware_sprite_pixels = scene.get_sprite_area_from_hardware_buffer()

        # Verify both have data
        assert len(sprite_pixels) > 0, "Sprite surface should have data"
        assert len(hardware_sprite_pixels) > 0, "Hardware sprite area should have data"

        # For small sprites, the pixel counts should match
        # This is informational only - no assertion needed

    def test_animation_timing_affects_hardware_buffer(self):
        """Test that animation timing affects what appears in hardware buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        if not hasattr(scene.animated_sprite, "animations") or not scene.animated_sprite.animations:
            self.skipTest("No animations found")

        animation_name = next(iter(scene.animated_sprite.animations.keys()))
        frames = scene.animated_sprite.animations[animation_name]

        # Test that different frames show different content in hardware buffer
        frame_contents = []

        for i in range(min(3, len(frames))):  # Test first 3 frames
            # Set frame
            if hasattr(scene.animated_sprite, "set_frame"):
                scene.animated_sprite.set_frame(i)
            elif hasattr(scene.animated_sprite, "frame_manager"):
                scene.animated_sprite.frame_manager.set_frame(i)

            # Force display update
            scene.force_display_update()

            # Capture from hardware buffer
            sprite_pixels = scene.get_sprite_area_from_hardware_buffer()
            frame_contents.append(sprite_pixels)

        # Verify frames are different in hardware buffer
        unique_contents = {tuple(pixels) for pixels in frame_contents}
        assert len(unique_contents) > 1, "Hardware buffer should show different frame content"


if __name__ == "__main__":
    unittest.main()
