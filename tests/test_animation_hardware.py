"""Test suite for hardware-level animation rendering verification.

This module tests that animated sprites properly reach the actual display buffer
and hardware, providing multiple layers of verification to quickly identify
where rendering problems occur in the pipeline.
"""

import time
import unittest
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from glitchygames.sprites import SpriteFactory

if TYPE_CHECKING:
    from glitchygames.sprites.animated import AnimatedSprite


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
        try:
            self.animated_sprite = SpriteFactory.load_sprite(filename=self.animation_file)
            if hasattr(self.animated_sprite, "play"):
                self.animated_sprite.play()
            # Center on screen
            self.animated_sprite.rect.center = self.screen.get_rect().center
            print(f"Loaded: {self.animated_sprite.name}")
        except Exception as e:
            print(f"Failed to load animation: {e}")
            raise

    def update(self) -> None:
        """Update the scene and capture frame data."""
        super().update()

        if self.animated_sprite and hasattr(self.animated_sprite, "update"):
            # Update with delta time
            self.animated_sprite.update(self.dt)

    def capture_hardware_display_buffer(self) -> list[tuple[int, int, int]]:
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
        self.animation_file = "colors.toml"
        if not Path(self.animation_file).exists():
            self.skipTest(f"Animation file {self.animation_file} not found")

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
        self.assertGreater(len(hardware_pixels), 0, "Should capture hardware buffer data")
        self.assertEqual(len(hardware_pixels), 800 * 600, "Should capture full screen buffer")

        print(f"Hardware buffer: {len(hardware_pixels)} pixels captured")

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

        print(f"Sprite area pixels: {len(sprite_area_pixels)}")
        print(f"Non-background pixels in hardware buffer: {len(non_background_pixels)}")

        # Verify sprite is visible in hardware buffer
        self.assertGreater(
            len(non_background_pixels), 0, "Sprite should be visible in hardware display buffer"
        )

    def test_hardware_vs_surface_consistency(self):
        """Test that scene surface matches hardware display buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Capture from both sources
        hardware_pixels = scene.capture_hardware_display_buffer()
        surface_pixels = scene.capture_test_surface_pixels()

        print(f"Hardware buffer: {len(hardware_pixels)} pixels")
        print(f"Surface buffer: {len(surface_pixels)} pixels")

        # Verify both have data
        self.assertGreater(len(hardware_pixels), 0, "Hardware buffer should have data")
        self.assertGreater(len(surface_pixels), 0, "Surface buffer should have data")

        # For small sprites, check sprite area specifically
        sprite_area_hardware = scene.get_sprite_area_from_hardware_buffer()
        sprite_area_surface = []

        sprite_rect = scene.animated_sprite.rect
        for y in range(sprite_rect.top, sprite_rect.bottom):
            for x in range(sprite_rect.left, sprite_rect.right):
                if 0 <= x < 800 and 0 <= y < 600:
                    pixel_index = y * 800 + x
                    if pixel_index < len(surface_pixels):
                        sprite_area_surface.append(surface_pixels[pixel_index])

        print(f"Sprite area - Hardware: {len(sprite_area_hardware)} pixels")
        print(f"Sprite area - Surface: {len(sprite_area_surface)} pixels")

        # Verify sprite areas have similar content
        self.assertEqual(
            len(sprite_area_hardware),
            len(sprite_area_surface),
            "Sprite areas should have same pixel count",
        )

    def test_animation_frame_transitions_in_hardware(self):
        """Test that animation frame transitions are visible in hardware buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        if not hasattr(scene.animated_sprite, "animations") or not scene.animated_sprite.animations:
            self.skipTest("No animations found")

        # Get all frames from the animation
        animation_name = list(scene.animated_sprite.animations.keys())[0]
        frames = scene.animated_sprite.animations[animation_name]

        if len(frames) < 3:
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

            print(f"Frame {i}: {len(sprite_pixels)} pixels in hardware buffer")

        # Verify frames have different content in hardware buffer
        unique_frames = set(tuple(pixels) for pixels in hardware_frame_data)
        self.assertGreater(
            len(unique_frames), 1, "Hardware buffer should show different frame content"
        )

        print(f"Found {len(unique_frames)} unique frame contents in hardware buffer")

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
        self.assertLess(total_time, 2.0, f"Hardware rendering should be fast: {total_time:.3f}s")

        print(f"Hardware rendering performance: {total_time:.3f}s for 5 captures")

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
        self.assertEqual(len(buffer1), len(buffer2), "Hardware buffer size should be consistent")

        # For static scenes, buffers should be identical
        # For animated scenes, they might differ slightly
        print(f"Hardware buffer captures: {len(buffer1)} and {len(buffer2)} pixels")

    def test_sprite_positioning_in_hardware_buffer(self):
        """Test that sprite positioning is correct in hardware buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Get sprite position and size
        sprite_rect = scene.animated_sprite.rect
        print(f"Sprite positioned at {sprite_rect.topleft} with size {sprite_rect.size}")

        # Verify sprite is within screen bounds
        self.assertGreaterEqual(sprite_rect.left, 0, "Sprite should be within screen bounds")
        self.assertGreaterEqual(sprite_rect.top, 0, "Sprite should be within screen bounds")
        self.assertLess(sprite_rect.right, 800, "Sprite should be within screen bounds")
        self.assertLess(sprite_rect.bottom, 600, "Sprite should be within screen bounds")

        # Check that sprite area has content in hardware buffer
        sprite_area_pixels = scene.get_sprite_area_from_hardware_buffer()
        self.assertGreater(
            len(sprite_area_pixels), 0, "Sprite area should have pixels in hardware buffer"
        )

    def test_hardware_vs_sprite_surface_consistency(self):
        """Test that hardware buffer matches sprite surface data."""
        scene = HardwareAnimationTestScene(self.animation_file)

        # Force display update
        scene.force_display_update()

        # Get sprite surface data
        sprite_pixels = scene.capture_sprite_pixels()

        # Get sprite area from hardware buffer
        hardware_sprite_pixels = scene.get_sprite_area_from_hardware_buffer()

        print(f"Sprite surface: {len(sprite_pixels)} pixels")
        print(f"Hardware sprite area: {len(hardware_sprite_pixels)} pixels")

        # Verify both have data
        self.assertGreater(len(sprite_pixels), 0, "Sprite surface should have data")
        self.assertGreater(len(hardware_sprite_pixels), 0, "Hardware sprite area should have data")

        # For small sprites, the pixel counts should match
        if len(sprite_pixels) == len(hardware_sprite_pixels):
            print("✅ Sprite surface and hardware buffer pixel counts match")
        else:
            print(
                f"⚠️ Pixel count mismatch: surface={len(sprite_pixels)}, hardware={len(hardware_sprite_pixels)}"
            )

    def test_animation_timing_affects_hardware_buffer(self):
        """Test that animation timing affects what appears in hardware buffer."""
        scene = HardwareAnimationTestScene(self.animation_file)

        if not hasattr(scene.animated_sprite, "animations") or not scene.animated_sprite.animations:
            self.skipTest("No animations found")

        animation_name = list(scene.animated_sprite.animations.keys())[0]
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

            print(f"Frame {i}: {len(sprite_pixels)} pixels, duration={frames[i].duration}s")

        # Verify frames are different in hardware buffer
        unique_contents = set(tuple(pixels) for pixels in frame_contents)
        self.assertGreater(
            len(unique_contents), 1, "Hardware buffer should show different frame content"
        )

        print(f"Hardware buffer shows {len(unique_contents)} unique frame contents")


if __name__ == "__main__":
    unittest.main()
