"""
Test film strip canvas synchronization.

This test verifies that the film strip updates to show the current canvas content
when drawing on the canvas, rather than showing stale frame data.
"""

import os
import tempfile
from pathlib import Path

import pygame
import pytest
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import AnimatedCanvasSprite
from glitchygames.tools.film_strip import FilmStripWidget


class TestFilmStripCanvasSync:
    """Test film strip canvas synchronization."""

    def setup_method(self):
        """Set up test environment."""
        # Initialize pygame
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Create a temporary animated sprite
        self.animated_sprite = AnimatedSprite()

        # Create a test frame with some initial content
        test_surface = pygame.Surface((32, 32))
        test_surface.fill((255, 0, 255))  # Magenta background
        test_surface.fill((0, 0, 0), (10, 10, 12, 12))  # Black square

        frame = SpriteFrame(test_surface, duration=1.0)
        self.animated_sprite._animations = {"idle": [frame]}
        self.animated_sprite.frame_manager.current_animation = "idle"
        self.animated_sprite.frame_manager.current_frame = 0

        # Create film strip widget
        self.film_strip = FilmStripWidget(x=0, y=0, width=400, height=100)
        self.film_strip.set_animated_sprite(self.animated_sprite)

        # Create a mock canvas
        self.canvas = MockCanvas()
        self.film_strip.set_parent_canvas(self.canvas)

    def teardown_method(self):
        """Clean up test environment."""
        pygame.quit()

    def test_film_strip_shows_canvas_content(self):
        """Test that film strip shows current canvas content, not stored frame data."""
        # Get initial film strip content
        initial_surface = self.film_strip.render()
        initial_pixels = self._get_surface_pixels(initial_surface)

        # Modify canvas content (simulate drawing)
        self.canvas.set_pixel(15, 15, (255, 255, 0))  # Yellow pixel
        self.canvas.set_pixel(16, 16, (0, 255, 0))  # Green pixel

        # Force film strip to update
        self.film_strip.update_layout()

        # Get updated film strip content
        updated_surface = self.film_strip.render()
        updated_pixels = self._get_surface_pixels(updated_surface)

        # The film strip should show different content after canvas changes
        assert initial_pixels != updated_pixels, (
            "Film strip should update when canvas content changes"
        )

        # Verify the film strip contains the new canvas content
        # Look for the yellow and green pixels we added
        has_yellow = any((255, 255, 0) in pixel_row for pixel_row in updated_pixels)
        has_green = any((0, 255, 0) in pixel_row for pixel_row in updated_pixels)

        assert has_yellow, "Film strip should contain yellow pixel from canvas"
        assert has_green, "Film strip should contain green pixel from canvas"

    def test_film_strip_updates_on_canvas_changes(self):
        """Test that film strip updates when canvas pixels change."""
        # Get initial state
        initial_surface = self.film_strip.render()
        initial_hash = hash(initial_surface.get_buffer().raw)

        # Make multiple canvas changes
        for i in range(5):
            self.canvas.set_pixel(10 + i, 10 + i, (255, 0, 0))  # Red diagonal line

        # Force film strip update
        self.film_strip.update_layout()

        # Get updated state
        updated_surface = self.film_strip.render()
        updated_hash = hash(updated_surface.get_buffer().raw)

        # The film strip should be different after canvas changes
        assert initial_hash != updated_hash, "Film strip should update when canvas pixels change"

    def test_film_strip_frame_thumbnail_uses_canvas(self):
        """Test that frame thumbnail rendering uses canvas data."""
        # Create a frame for testing
        frame = self.animated_sprite._animations["idle"][0]

        # Modify canvas content
        self.canvas.set_pixel(5, 5, (255, 0, 0))  # Red
        self.canvas.set_pixel(6, 6, (0, 255, 0))  # Green
        self.canvas.set_pixel(7, 7, (0, 0, 255))  # Blue

        # Render frame thumbnail
        thumbnail = self.film_strip.render_frame_thumbnail(
            frame, is_selected=True, is_hovered=False
        )
        thumbnail_pixels = self._get_surface_pixels(thumbnail)

        # The thumbnail should contain the canvas colors
        has_red = any((255, 0, 0) in pixel_row for pixel_row in thumbnail_pixels)
        has_green = any((0, 255, 0) in pixel_row for pixel_row in thumbnail_pixels)
        has_blue = any((0, 0, 255) in pixel_row for pixel_row in thumbnail_pixels)

        assert has_red, "Frame thumbnail should contain red pixel from canvas"
        assert has_green, "Frame thumbnail should contain green pixel from canvas"
        assert has_blue, "Frame thumbnail should contain blue pixel from canvas"

    def _get_surface_pixels(self, surface):
        """Extract pixel data from a surface for comparison."""
        pixels = []
        for y in range(surface.get_height()):
            row = []
            for x in range(surface.get_width()):
                color = surface.get_at((x, y))
                row.append((color.r, color.g, color.b))
            pixels.append(row)
        return pixels


class MockCanvas:
    """Mock canvas for testing film strip integration."""

    def __init__(self):
        self.pixels_across = 32
        self.pixels_tall = 32
        self.pixels = [(255, 0, 255)] * (32 * 32)  # Initial magenta background

    def get_canvas_surface(self):
        """Get current canvas surface for film strip."""
        surface = pygame.Surface((self.pixels_across, self.pixels_tall))
        for y in range(self.pixels_tall):
            for x in range(self.pixels_across):
                pixel_num = y * self.pixels_across + x
                if pixel_num < len(self.pixels):
                    color = self.pixels[pixel_num]
                    surface.set_at((x, y), color)
        return surface

    def set_pixel(self, x, y, color):
        """Set a pixel in the canvas."""
        if 0 <= x < self.pixels_across and 0 <= y < self.pixels_tall:
            pixel_num = y * self.pixels_across + x
            self.pixels[pixel_num] = color


if __name__ == "__main__":
    pytest.main([__file__])
