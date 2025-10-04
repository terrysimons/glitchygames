"""Test suite for Canvas Interface refactoring.

This module tests the new canvas interfaces that allow the bitmap editor to work
with both static BitmappySprites and animated sprites through a unified API.

Tests cover:
- StaticCanvasInterface functionality
- StaticSpriteSerializer operations
- StaticCanvasRenderer rendering
- Backwards compatibility with existing CanvasSprite API
"""

import sys
import unittest
from pathlib import Path

import pygame

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from glitchygames.tools.bitmappy import CanvasSprite
from glitchygames.tools.canvas_interfaces import (
    StaticCanvasInterface,
    StaticCanvasRenderer,
    StaticSpriteSerializer,
)

# Constants for test values
CANVAS_SIZE = 8
CANVAS_PIXEL_COUNT = 64  # 8x8 = 64 pixels
PIXEL_SIZE = 16
SMALL_CANVAS_SIZE = 4
SMALL_CANVAS_PIXEL_COUNT = 16  # 4x4 = 16 pixels


class TestCanvasInterfaces(unittest.TestCase):
    """Test suite for canvas interface functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize pygame with display for each test
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Create a test canvas
        self.canvas = CanvasSprite(
            name="Test Canvas",
            x=0,
            y=0,
            pixels_across=8,
            pixels_tall=8,
            pixel_width=16,
            pixel_height=16,
        )

    @staticmethod
    def tearDown():
        """Clean up after each test method."""
        pygame.quit()

    def _display_canvas_visual(self, title="Canvas Display"):
        """Display the canvas visually tiled across the screen for verification."""
        screen = pygame.display.get_surface()
        screen_width, screen_height = screen.get_size()

        # Clear screen with dark background
        screen.fill((20, 20, 40))

        # Get canvas dimensions
        canvas_width = self.canvas.rect.width
        canvas_height = self.canvas.rect.height

        # Calculate how many canvases fit across and down
        tiles_x = screen_width // canvas_width
        tiles_y = screen_height // canvas_height

        # Tile the canvas across the screen
        for y in range(tiles_y):
            for x in range(tiles_x):
                screen.blit(self.canvas.image, (x * canvas_width, y * canvas_height))

        # Add title text
        font = pygame.font.Font(None, 36)
        title_surface = font.render(title, antialias=True, color=(255, 255, 255))
        screen.blit(title_surface, (10, 10))

        # Add canvas info
        info_font = pygame.font.Font(None, 24)
        info_text = (
            f"Canvas: {self.canvas.pixels_across}x{self.canvas.pixels_tall} pixels, "
            f"{canvas_width}x{canvas_height} display"
        )
        info_surface = info_font.render(info_text, antialias=True, color=(200, 200, 200))
        screen.blit(info_surface, (10, 50))

        # Update display and wait a bit
        pygame.display.flip()
        # DEBUG: Displaying canvas for 3 seconds
        pygame.time.wait(3000)  # Show for 3 seconds
        # DEBUG: Additional 2 second pause
        pygame.time.wait(2000)  # Additional 2 second timeout

    def test_canvas_interface_creation(self):
        """Test that canvas interface is created correctly."""
        interface = self.canvas.get_canvas_interface()
        assert isinstance(interface, StaticCanvasInterface)

    def test_canvas_interface_dimensions(self):
        """Test canvas interface dimension methods."""
        interface = self.canvas.get_canvas_interface()

        # Test getting dimensions
        width, height = interface.get_dimensions()
        assert width == CANVAS_SIZE
        assert height == CANVAS_SIZE

    def test_canvas_interface_pixel_operations(self):
        """Test canvas interface pixel manipulation."""
        interface = self.canvas.get_canvas_interface()

        # Test setting and getting individual pixels
        interface.set_pixel_at(0, 0, (255, 0, 0))  # Red pixel
        interface.set_pixel_at(1, 1, (0, 255, 0))  # Green pixel

        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 1)

        assert red_pixel == (255, 0, 0)
        assert green_pixel == (0, 255, 0)

    def test_canvas_interface_pixel_data(self):
        """Test canvas interface pixel data operations."""
        interface = self.canvas.get_canvas_interface()

        # Test getting all pixel data
        pixel_data = interface.get_pixel_data()
        assert len(pixel_data) == CANVAS_PIXEL_COUNT  # 8x8 = 64 pixels

        # Test setting all pixel data
        new_pixels = [(128, 128, 128)] * CANVAS_PIXEL_COUNT  # Gray pixels
        interface.set_pixel_data(new_pixels)

        # Verify the change
        updated_pixel = interface.get_pixel_at(0, 0)
        assert updated_pixel == (128, 128, 128)

    def test_sprite_serializer_creation(self):
        """Test that sprite serializer is created correctly."""
        serializer = self.canvas.get_sprite_serializer()
        assert isinstance(serializer, StaticSpriteSerializer)

    def test_canvas_renderer_creation(self):
        """Test that canvas renderer is created correctly."""
        renderer = self.canvas.get_canvas_renderer()
        assert isinstance(renderer, StaticCanvasRenderer)

    def test_canvas_renderer_pixel_size(self):
        """Test canvas renderer pixel size method."""
        renderer = self.canvas.get_canvas_renderer()
        pixel_width, pixel_height = renderer.get_pixel_size()

        assert pixel_width == PIXEL_SIZE
        assert pixel_height == PIXEL_SIZE

    def test_canvas_renderer_rendering(self):
        """Test canvas renderer rendering methods."""
        renderer = self.canvas.get_canvas_renderer()

        # Test rendering
        surface = renderer.render(self.canvas)
        assert surface.get_size() == (128, 128)  # 8*16 x 8*16

        # Test force redraw
        redraw_surface = renderer.force_redraw(self.canvas)
        assert redraw_surface.get_size() == (128, 128)

    def test_backwards_compatibility(self):
        """Test that existing CanvasSprite functionality still works."""
        # Test that old attributes still exist
        assert hasattr(self.canvas, "pixels")
        assert hasattr(self.canvas, "pixels_across")
        assert hasattr(self.canvas, "pixels_tall")
        assert hasattr(self.canvas, "active_color")

        # Test that old methods still work
        assert hasattr(self.canvas, "force_redraw")
        assert hasattr(self.canvas, "on_save_file_event")

        # Test setting pixels the old way
        self.canvas.pixels[0] = (255, 0, 0)  # Red pixel
        self.canvas.pixels[1] = (0, 255, 0)  # Green pixel

        # Test that the interface reflects the changes
        interface = self.canvas.get_canvas_interface()
        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 0)

        assert red_pixel == (255, 0, 0)
        assert green_pixel == (0, 255, 0)

        # Force redraw to update the canvas image with the new pixels
        self.canvas.force_redraw()

        # Visual test: display the canvas with colored pixels
        self._display_canvas_visual("Canvas Backwards Compatibility - Red/Green Pixels")

    def test_interface_integration(self):
        """Test that all interfaces work together correctly."""
        # Get all interface components
        interface = self.canvas.get_canvas_interface()
        renderer = self.canvas.get_canvas_renderer()

        # Test that they all work together
        interface.set_pixel_at(2, 2, (0, 0, 255))  # Blue pixel
        surface = renderer.render(self.canvas)

        # Verify the pixel was set correctly
        blue_pixel = interface.get_pixel_at(2, 2)
        assert blue_pixel == (0, 0, 255)

        # Verify the surface was rendered
        assert surface is not None
        assert surface.get_size() == (128, 128)

        # Force redraw to update the canvas image with the new pixel
        self.canvas.force_redraw()

        # Visual test: display the canvas with blue pixel
        self._display_canvas_visual("Canvas Interface Integration - Blue Pixel")


class TestCanvasInterfaceEdgeCases(unittest.TestCase):
    """Test edge cases for canvas interfaces."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        pygame.init()
        pygame.display.set_mode((800, 600))

        self.canvas = CanvasSprite(
            name="Test Canvas",
            x=0,
            y=0,
            pixels_across=4,
            pixels_tall=4,
            pixel_width=16,
            pixel_height=16,
        )

    @staticmethod
    def tearDown():
        """Clean up after each test method."""
        pygame.quit()

    def test_out_of_bounds_pixel_access(self):
        """Test accessing pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()

        # Test out-of-bounds access
        out_of_bounds_pixel = interface.get_pixel_at(10, 10)
        assert out_of_bounds_pixel == (255, 0, 255)  # Should return magenta

    def test_out_of_bounds_pixel_setting(self):
        """Test setting pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()

        # Test setting out-of-bounds pixel (should not crash)
        interface.set_pixel_at(10, 10, (255, 0, 0))

        # Verify the canvas wasn't corrupted
        assert len(self.canvas.pixels) == SMALL_CANVAS_PIXEL_COUNT  # 4x4 = 16 pixels


def run_tests():
    """Run all tests and return success status."""
    # Running Canvas Interface Tests...
    # ==================================================

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCanvasInterfaces))
    suite.addTests(loader.loadTestsFromTestCase(TestCanvasInterfaceEdgeCases))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # ==================================================
    # Return success status directly
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
