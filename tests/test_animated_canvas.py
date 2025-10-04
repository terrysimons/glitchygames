#!/usr/bin/env python3
"""
Test suite for AnimatedCanvasSprite functionality.

This module tests the new AnimatedCanvasSprite class that allows the bitmap editor
to work with animated sprites, including frame selection, editing, and film strip integration.
"""

import unittest
import pygame
import sys
import os
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glitchygames.sprites import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import AnimatedCanvasSprite
from glitchygames.tools.canvas_interfaces import (
    AnimatedCanvasInterface, 
    AnimatedSpriteSerializer, 
    AnimatedCanvasRenderer
)
from glitchygames.tools.film_strip import FilmStripWidget


class TestAnimatedCanvasSprite(unittest.TestCase):
    """Test suite for AnimatedCanvasSprite functionality."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Initialize pygame with display for each test
        pygame.init()
        pygame.display.set_mode((800, 600))
        
        # Create a test animated sprite
        self.animated_sprite = self._create_test_animated_sprite()
        
        # Create a test animated canvas
        self.canvas = AnimatedCanvasSprite(
            animated_sprite=self.animated_sprite,
            name="Test Animated Canvas",
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
    
    def _create_test_animated_sprite(self):
        """Create a test animated sprite with multiple animations and frames."""
        # Create frames for idle animation
        idle_surface1 = pygame.Surface((8, 8))
        idle_surface1.fill((255, 0, 0))  # Red
        idle_frame1 = SpriteFrame(idle_surface1)
        idle_frame1.pixels = [(255, 0, 0)] * 64  # 8x8 = 64 pixels
        
        idle_surface2 = pygame.Surface((8, 8))
        idle_surface2.fill((0, 255, 0))  # Green
        idle_frame2 = SpriteFrame(idle_surface2)
        idle_frame2.pixels = [(0, 255, 0)] * 64
        
        # Create frames for walk animation
        walk_surface1 = pygame.Surface((8, 8))
        walk_surface1.fill((0, 0, 255))  # Blue
        walk_frame1 = SpriteFrame(walk_surface1)
        walk_frame1.pixels = [(0, 0, 255)] * 64
        
        walk_surface2 = pygame.Surface((8, 8))
        walk_surface2.fill((255, 255, 0))  # Yellow
        walk_frame2 = SpriteFrame(walk_surface2)
        walk_frame2.pixels = [(255, 255, 0)] * 64
        
        # Create animated sprite
        animated_sprite = AnimatedSprite()
        # Set frames using the internal structure
        animated_sprite._animations = {
            "idle": [idle_frame1, idle_frame2],
            "walk": [walk_frame1, walk_frame2]
        }
        
        return animated_sprite
    
    def test_animated_canvas_creation(self):
        """Test that AnimatedCanvasSprite is created correctly."""
        self.assertIsInstance(self.canvas, AnimatedCanvasSprite)
        self.assertEqual(self.canvas.animated_sprite, self.animated_sprite)
        self.assertEqual(self.canvas.current_animation, "idle")
        self.assertEqual(self.canvas.current_frame, 0)
    
    def test_interface_initialization(self):
        """Test that animated interfaces are initialized correctly."""
        self.assertIsInstance(self.canvas.canvas_interface, AnimatedCanvasInterface)
        self.assertIsInstance(self.canvas.sprite_serializer, AnimatedSpriteSerializer)
        self.assertIsInstance(self.canvas.canvas_renderer, AnimatedCanvasRenderer)
    
    def test_show_frame(self):
        """Test switching to different frames."""
        # Test switching to walk animation, frame 1
        self.canvas.show_frame("walk", 1)
        self.assertEqual(self.canvas.current_animation, "walk")
        self.assertEqual(self.canvas.current_frame, 1)
        
        # Test switching back to idle animation, frame 0
        self.canvas.show_frame("idle", 0)
        self.assertEqual(self.canvas.current_animation, "idle")
        self.assertEqual(self.canvas.current_frame, 0)
    
    def test_frame_editing(self):
        """Test editing pixels in the current frame."""
        # Set a pixel in the current frame
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 255, 255))
        
        # Verify the pixel was set
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        self.assertEqual(pixel_color, (255, 255, 255))
        
        # Verify it's set in the actual frame
        current_frame = self.animated_sprite.frames["idle"][0]
        frame_pixels = current_frame.get_pixel_data()
        self.assertEqual(frame_pixels[0], (255, 255, 255))
    
    def test_frame_isolation(self):
        """Test that editing one frame doesn't affect others."""
        # Edit frame 0 of idle animation
        self.canvas.show_frame("idle", 0)
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 0, 0))
        
        # Switch to frame 1 of idle animation
        self.canvas.show_frame("idle", 1)
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        self.assertEqual(pixel_color, (0, 255, 0))  # Should be green (original color)
        
        # Switch back to frame 0
        self.canvas.show_frame("idle", 0)
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        self.assertEqual(pixel_color, (255, 0, 0))  # Should be red (our edit)
    
    def test_animation_isolation(self):
        """Test that editing one animation doesn't affect others."""
        # Edit idle animation, frame 0
        self.canvas.show_frame("idle", 0)
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 0, 0))
        
        # Switch to walk animation, frame 0
        self.canvas.show_frame("walk", 0)
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        self.assertEqual(pixel_color, (0, 0, 255))  # Should be blue (original color)
    
    def test_frame_navigation(self):
        """Test navigating between frames."""
        # Test next frame
        self.canvas.next_frame()
        self.assertEqual(self.canvas.current_frame, 1)
        
        # Test previous frame
        self.canvas.previous_frame()
        self.assertEqual(self.canvas.current_frame, 0)
        
        # Test wrapping around
        self.canvas.previous_frame()
        self.assertEqual(self.canvas.current_frame, 1)  # Should wrap to last frame
    
    def test_animation_navigation(self):
        """Test navigating between animations."""
        # Test next animation
        self.canvas.next_animation()
        self.assertEqual(self.canvas.current_animation, "walk")
        self.assertEqual(self.canvas.current_frame, 0)  # Should reset to frame 0
        
        # Test previous animation
        self.canvas.previous_animation()
        self.assertEqual(self.canvas.current_animation, "idle")
        self.assertEqual(self.canvas.current_frame, 0)
    
    def test_film_strip_integration(self):
        """Test that film strip widget is created and integrated."""
        self.assertIsInstance(self.canvas.film_strip, FilmStripWidget)
        self.assertEqual(self.canvas.film_strip.animated_sprite, self.animated_sprite)
    
    def test_film_strip_frame_selection(self):
        """Test that clicking on film strip changes the current frame."""
        # Simulate clicking on walk animation, frame 1
        clicked_frame = self.canvas.film_strip.handle_click((100, 50))  # Mock position
        
        if clicked_frame:
            animation, frame_idx = clicked_frame
            self.canvas.show_frame(animation, frame_idx)
            self.assertEqual(self.canvas.current_animation, animation)
            self.assertEqual(self.canvas.current_frame, frame_idx)
    
    def test_keyboard_navigation(self):
        """Test keyboard navigation between frames."""
        # Test left arrow (previous frame)
        self.canvas.show_frame("idle", 1)
        self.canvas.handle_keyboard_event(pygame.K_LEFT)
        self.assertEqual(self.canvas.current_frame, 0)
        
        # Test right arrow (next frame)
        self.canvas.handle_keyboard_event(pygame.K_RIGHT)
        self.assertEqual(self.canvas.current_frame, 1)
        
        # Test up arrow (previous animation)
        self.canvas.handle_keyboard_event(pygame.K_UP)
        self.assertEqual(self.canvas.current_animation, "walk")
        
        # Test down arrow (next animation)
        self.canvas.handle_keyboard_event(pygame.K_DOWN)
        self.assertEqual(self.canvas.current_animation, "idle")
    
    def test_copy_paste_functionality(self):
        """Test copying and pasting between frames."""
        # Set a pixel in current frame
        self.canvas.canvas_interface.set_pixel_at(0, 0, (255, 255, 255))
        
        # Copy current frame
        self.canvas.copy_current_frame()
        
        # Switch to another frame
        self.canvas.show_frame("idle", 1)
        
        # Paste the copied frame
        self.canvas.paste_to_current_frame()
        
        # Verify the pixel was pasted
        pixel_color = self.canvas.canvas_interface.get_pixel_at(0, 0)
        self.assertEqual(pixel_color, (255, 255, 255))
    
    def test_save_load_animated_sprite(self):
        """Test saving and loading animated sprites."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            temp_filename = f.name
        
        try:
            # Save the animated sprite
            self.canvas.save_animated_sprite(temp_filename)
            
            # Load it back
            loaded_canvas = AnimatedCanvasSprite.from_file(
                filename=temp_filename,
                x=0, y=0,
                pixels_across=8, pixels_tall=8,
                pixel_width=16, pixel_height=16
            )
            
            # Verify it loaded correctly
            self.assertEqual(loaded_canvas.current_animation, "idle")
            self.assertEqual(loaded_canvas.current_frame, 0)
            self.assertEqual(len(loaded_canvas.animated_sprite.frames), 2)
            
        finally:
            # Clean up
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)
    
    def test_visual_display(self):
        """Test that the canvas displays the current frame correctly."""
        # Force redraw to update the display
        self.canvas.force_redraw()
        
        # Verify the canvas image is updated
        self.assertIsNotNone(self.canvas.image)
        self.assertEqual(self.canvas.image.get_size(), (128, 128))  # 8*16 x 8*16


class TestAnimatedCanvasSpriteEdgeCases(unittest.TestCase):
    """Test edge cases for AnimatedCanvasSprite."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        pygame.init()
        pygame.display.set_mode((800, 600))
    
    def tearDown(self):
        """Clean up after each test method."""
        pygame.quit()
    
    def test_empty_animated_sprite(self):
        """Test creating canvas with empty animated sprite."""
        empty_sprite = AnimatedSprite()
        empty_sprite._frames = {}
        empty_sprite._animations = {}
        
        canvas = AnimatedCanvasSprite(
            animated_sprite=empty_sprite,
            name="Empty Canvas",
            x=0, y=0,
            pixels_across=8, pixels_tall=8,
            pixel_width=16, pixel_height=16
        )
        
        # Should handle empty sprite gracefully
        self.assertEqual(canvas.current_animation, "idle")
        self.assertEqual(canvas.current_frame, 0)
    
    def test_single_frame_animation(self):
        """Test canvas with single frame animation."""
        surface = pygame.Surface((8, 8))
        surface.fill((255, 0, 0))
        frame = SpriteFrame(surface)
        frame.pixels = [(255, 0, 0)] * 64
        
        single_sprite = AnimatedSprite()
        single_sprite._animations = {"idle": [frame]}
        
        canvas = AnimatedCanvasSprite(
            animated_sprite=single_sprite,
            name="Single Frame Canvas",
            x=0, y=0,
            pixels_across=8, pixels_tall=8,
            pixel_width=16, pixel_height=16
        )
        
        # Should handle single frame correctly
        self.assertEqual(canvas.current_animation, "idle")
        self.assertEqual(canvas.current_frame, 0)
        
        # Navigation should wrap around
        canvas.next_frame()
        self.assertEqual(canvas.current_frame, 0)  # Should wrap to 0


def run_tests():
    """Run all tests and return success status."""
    print("Running Animated Canvas Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestAnimatedCanvasSprite))
    suite.addTests(loader.loadTestsFromTestCase(TestAnimatedCanvasSpriteEdgeCases))
    
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
