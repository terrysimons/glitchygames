#!/usr/bin/env python3
"""
Test suite for Canvas Interface refactoring.

This module tests the new canvas interfaces that allow the bitmap editor to work
with both static BitmappySprites and animated sprites through a unified API.

Tests cover:
- StaticCanvasInterface functionality
- StaticSpriteSerializer operations  
- StaticCanvasRenderer rendering
- Backwards compatibility with existing CanvasSprite API
"""

import unittest
import pygame
import sys
import os
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glitchygames.tools.bitmappy import CanvasSprite
from glitchygames.tools.canvas_interfaces import (
    StaticCanvasInterface, 
    StaticSpriteSerializer, 
    StaticCanvasRenderer
)


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
            pixel_height=16
        )
    
    def tearDown(self):
        """Clean up after each test method."""
        pygame.quit()
    
    def test_canvas_interface_creation(self):
        """Test that canvas interface is created correctly."""
        interface = self.canvas.get_canvas_interface()
        self.assertIsInstance(interface, StaticCanvasInterface)
    
    def test_canvas_interface_dimensions(self):
        """Test canvas interface dimension methods."""
        interface = self.canvas.get_canvas_interface()
        
        # Test getting dimensions
        width, height = interface.get_dimensions()
        self.assertEqual(width, 8)
        self.assertEqual(height, 8)
    
    def test_canvas_interface_pixel_operations(self):
        """Test canvas interface pixel manipulation."""
        interface = self.canvas.get_canvas_interface()
        
        # Test setting and getting individual pixels
        interface.set_pixel_at(0, 0, (255, 0, 0))  # Red pixel
        interface.set_pixel_at(1, 1, (0, 255, 0))  # Green pixel
        
        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 1)
        
        self.assertEqual(red_pixel, (255, 0, 0))
        self.assertEqual(green_pixel, (0, 255, 0))
    
    def test_canvas_interface_pixel_data(self):
        """Test canvas interface pixel data operations."""
        interface = self.canvas.get_canvas_interface()
        
        # Test getting all pixel data
        pixel_data = interface.get_pixel_data()
        self.assertEqual(len(pixel_data), 64)  # 8x8 = 64 pixels
        
        # Test setting all pixel data
        new_pixels = [(128, 128, 128)] * 64  # Gray pixels
        interface.set_pixel_data(new_pixels)
        
        # Verify the change
        updated_pixel = interface.get_pixel_at(0, 0)
        self.assertEqual(updated_pixel, (128, 128, 128))
    
    def test_sprite_serializer_creation(self):
        """Test that sprite serializer is created correctly."""
        serializer = self.canvas.get_sprite_serializer()
        self.assertIsInstance(serializer, StaticSpriteSerializer)
    
    def test_canvas_renderer_creation(self):
        """Test that canvas renderer is created correctly."""
        renderer = self.canvas.get_canvas_renderer()
        self.assertIsInstance(renderer, StaticCanvasRenderer)
    
    def test_canvas_renderer_pixel_size(self):
        """Test canvas renderer pixel size method."""
        renderer = self.canvas.get_canvas_renderer()
        pixel_width, pixel_height = renderer.get_pixel_size()
        
        self.assertEqual(pixel_width, 16)
        self.assertEqual(pixel_height, 16)
    
    def test_canvas_renderer_rendering(self):
        """Test canvas renderer rendering methods."""
        renderer = self.canvas.get_canvas_renderer()
        
        # Test rendering
        surface = renderer.render(self.canvas)
        self.assertEqual(surface.get_size(), (128, 128))  # 8*16 x 8*16
        
        # Test force redraw
        redraw_surface = renderer.force_redraw(self.canvas)
        self.assertEqual(redraw_surface.get_size(), (128, 128))
    
    def test_backwards_compatibility(self):
        """Test that existing CanvasSprite functionality still works."""
        # Test that old attributes still exist
        self.assertTrue(hasattr(self.canvas, 'pixels'))
        self.assertTrue(hasattr(self.canvas, 'pixels_across'))
        self.assertTrue(hasattr(self.canvas, 'pixels_tall'))
        self.assertTrue(hasattr(self.canvas, 'active_color'))
        
        # Test that old methods still work
        self.assertTrue(hasattr(self.canvas, 'force_redraw'))
        self.assertTrue(hasattr(self.canvas, 'on_save_file_event'))
        
        # Test setting pixels the old way
        self.canvas.pixels[0] = (255, 0, 0)  # Red pixel
        self.canvas.pixels[1] = (0, 255, 0)  # Green pixel
        
        # Test that the interface reflects the changes
        interface = self.canvas.get_canvas_interface()
        red_pixel = interface.get_pixel_at(0, 0)
        green_pixel = interface.get_pixel_at(1, 0)
        
        self.assertEqual(red_pixel, (255, 0, 0))
        self.assertEqual(green_pixel, (0, 255, 0))
    
    def test_interface_integration(self):
        """Test that all interfaces work together correctly."""
        # Get all interface components
        interface = self.canvas.get_canvas_interface()
        serializer = self.canvas.get_sprite_serializer()
        renderer = self.canvas.get_canvas_renderer()
        
        # Test that they all work together
        interface.set_pixel_at(2, 2, (0, 0, 255))  # Blue pixel
        surface = renderer.render(self.canvas)
        
        # Verify the pixel was set correctly
        blue_pixel = interface.get_pixel_at(2, 2)
        self.assertEqual(blue_pixel, (0, 0, 255))
        
        # Verify the surface was rendered
        self.assertIsNotNone(surface)
        self.assertEqual(surface.get_size(), (128, 128))


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
            pixel_height=16
        )
    
    def tearDown(self):
        """Clean up after each test method."""
        pygame.quit()
    
    def test_out_of_bounds_pixel_access(self):
        """Test accessing pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()
        
        # Test out-of-bounds access
        out_of_bounds_pixel = interface.get_pixel_at(10, 10)
        self.assertEqual(out_of_bounds_pixel, (255, 0, 255))  # Should return magenta
    
    def test_out_of_bounds_pixel_setting(self):
        """Test setting pixels outside canvas bounds."""
        interface = self.canvas.get_canvas_interface()
        
        # Test setting out-of-bounds pixel (should not crash)
        interface.set_pixel_at(10, 10, (255, 0, 0))
        
        # Verify the canvas wasn't corrupted
        self.assertEqual(len(self.canvas.pixels), 16)  # 4x4 = 16 pixels


def run_tests():
    """Run all tests and return success status."""
    print("Running Canvas Interface Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestCanvasInterfaces))
    suite.addTests(loader.loadTestsFromTestCase(TestCanvasInterfaceEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("=" * 50)
    if result.wasSuccessful():
        print("🎉 All tests passed!")
        return True
    else:
        print(f"❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        return False


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)