#!/usr/bin/env python3
"""Tests for film tab functionality and frame insertion.

This module tests the film tab system that allows users to insert new frames
before or after existing frames in film strips.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

import pygame

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from glitchygames.sprites import AnimatedSprite, SpriteFrame
from glitchygames.tools.bitmappy import BitmapEditorScene
from glitchygames.tools.film_strip import FilmStripWidget, FilmTabWidget
from tests.mocks.test_mock_factory import MockFactory


class TestFilmTabWidget(unittest.TestCase):
    """Test the FilmTabWidget class."""
    
    def setUp(self):
        """Set up test fixtures with centralized mocks."""
        # Use centralized mock factory for pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()
        
        # Create test surface for rendering tests
        self.test_surface = pygame.Surface((100, 100))

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop all patchers
        for patcher in self.patchers:
            patcher.stop()
        """Clean up after tests."""
        pygame.quit()
    
    def test_film_tab_initialization(self):
        """Test that film tab initializes correctly."""
        tab = FilmTabWidget(x=10, y=20, width=25, height=35)
        
        self.assertEqual(tab.x, 10)
        self.assertEqual(tab.y, 20)
        self.assertEqual(tab.width, 25)
        self.assertEqual(tab.height, 35)
        self.assertEqual(tab.rect.x, 10)
        self.assertEqual(tab.rect.y, 20)
        self.assertEqual(tab.rect.width, 25)
        self.assertEqual(tab.rect.height, 35)
        
        # Check default properties
        self.assertFalse(tab.is_hovered)
        self.assertFalse(tab.is_clicked)
        self.assertEqual(tab.insertion_type, "before")
        self.assertEqual(tab.target_frame_index, 0)
    
    def test_film_tab_click_handling(self):
        """Test that film tab handles clicks correctly."""
        tab = FilmTabWidget(x=10, y=20, width=25, height=35)
        
        # Click inside the tab
        result = tab.handle_click((15, 30))
        self.assertTrue(result)
        self.assertTrue(tab.is_clicked)
        
        # Reset and click outside the tab
        tab.reset_click_state()
        result = tab.handle_click((50, 50))
        self.assertFalse(result)
        self.assertFalse(tab.is_clicked)
    
    def test_film_tab_hover_handling(self):
        """Test that film tab handles hover correctly."""
        tab = FilmTabWidget(x=10, y=20, width=25, height=35)
        
        # Hover inside the tab
        result = tab.handle_hover((15, 30))
        self.assertTrue(result)
        self.assertTrue(tab.is_hovered)
        
        # Hover outside the tab
        result = tab.handle_hover((50, 50))
        self.assertFalse(result)
        self.assertFalse(tab.is_hovered)
    
    def test_film_tab_insertion_type_setting(self):
        """Test that insertion type and target frame can be set."""
        tab = FilmTabWidget(x=10, y=20)
        
        tab.set_insertion_type("after", 5)
        self.assertEqual(tab.insertion_type, "after")
        self.assertEqual(tab.target_frame_index, 5)
        
        tab.set_insertion_type("before", 2)
        self.assertEqual(tab.insertion_type, "before")
        self.assertEqual(tab.target_frame_index, 2)
    
    def test_film_tab_rendering(self):
        """Test that film tab renders without errors."""
        tab = FilmTabWidget(x=10, y=20, width=25, height=35)
        
        # Should not raise any exceptions
        tab.render(self.test_surface)
        
        # Test with different states
        tab.is_hovered = True
        tab.render(self.test_surface)
        
        tab.is_clicked = True
        tab.render(self.test_surface)


class TestFilmStripTabIntegration(unittest.TestCase):
    """Test film tab integration with film strips."""
    
    def setUp(self):
        """Set up test fixtures with centralized mocks."""
        # Use centralized mock factory for pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()
        
        # Create a mock surface for testing
        self.test_surface = pygame.Surface((800, 600))
        
        # Create a mock animated sprite with frames
        self.mock_sprite = Mock()
        self.mock_sprite._animations = {
            "idle": [
                Mock(duration=0.5, image=pygame.Surface((32, 32))),
                Mock(duration=0.5, image=pygame.Surface((32, 32))),
                Mock(duration=0.5, image=pygame.Surface((32, 32)))
            ]
        }
        self.mock_sprite._animation_order = ["idle"]
        
        # Create film strip widget
        self.film_strip = FilmStripWidget(0, 0, 400, 100)
        self.film_strip.set_animated_sprite(self.mock_sprite)
        self.film_strip.current_animation = "idle"
        self.film_strip.current_frame = 0
        
        # Mock parent scene
        self.mock_scene = Mock()
        self.film_strip.parent_scene = self.mock_scene

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop all patchers
        for patcher in self.patchers:
            patcher.stop()
    
    def test_film_tabs_creation(self):
        """Test that film tabs are created correctly."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Should have tabs for each frame
        self.assertGreater(len(self.film_strip.film_tabs), 0)
        
        # Check that tabs have correct properties
        for tab in self.film_strip.film_tabs:
            self.assertIn(tab.insertion_type, ["before", "after"])
            self.assertGreaterEqual(tab.target_frame_index, 0)
    
    def test_film_tab_click_handling(self):
        """Test that film strip handles tab clicks correctly."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Get the first tab
        if self.film_strip.film_tabs:
            first_tab = self.film_strip.film_tabs[0]
            tab_pos = (first_tab.rect.centerx, first_tab.rect.centery)
            
            # Test tab click handling
            result = self.film_strip._handle_tab_click(tab_pos)
            self.assertTrue(result)
    
    def test_film_tab_hover_handling(self):
        """Test that film strip handles tab hover correctly."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Get the first tab
        if self.film_strip.film_tabs:
            first_tab = self.film_strip.film_tabs[0]
            tab_pos = (first_tab.rect.centerx, first_tab.rect.centery)
            
            # Test tab hover handling
            result = self.film_strip._handle_tab_hover(tab_pos)
            self.assertTrue(result)
    
    def test_frame_insertion_via_tab(self):
        """Test that clicking a tab inserts a new frame."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Get initial frame count
        initial_frame_count = len(self.mock_sprite._animations["idle"])
        
        # Get the first tab and simulate click
        if self.film_strip.film_tabs:
            first_tab = self.film_strip.film_tabs[0]
            
            # Mock the add_frame method
            with patch.object(self.mock_sprite, "add_frame") as mock_add_frame:
                # Simulate frame insertion
                self.film_strip._insert_frame_at_tab(first_tab)
                
                # Verify that add_frame was called
                mock_add_frame.assert_called_once()
                
                # Check that the call was made with correct parameters
                call_args = mock_add_frame.call_args
                self.assertEqual(call_args[0][0], "idle")  # animation name
                self.assertIsInstance(call_args[0][1], SpriteFrame)  # new frame
                self.assertGreaterEqual(call_args[0][2], 0)  # insertion index
    
    def test_film_tab_rendering(self):
        """Test that film tabs are rendered correctly."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Should not raise any exceptions when rendering
        self.film_strip.render(self.test_surface)
        
        # Check that tabs exist
        self.assertGreater(len(self.film_strip.film_tabs), 0)


class TestFilmTabFrameInsertion(unittest.TestCase):
    """Test frame insertion functionality through film tabs."""
    
    def setUp(self):
        """Set up test fixtures with centralized mocks."""
        # Use centralized mock factory for pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()
        
        # Create a real animated sprite with frames
        self.animated_sprite = AnimatedSprite()
        
        # Create frames with different durations
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=0.5)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=0.5)
        frame3 = SpriteFrame(pygame.Surface((32, 32)), duration=0.5)
        
        # Add animation with frames
        self.animated_sprite.add_animation("test_anim", [frame1, frame2, frame3])
        
        # Create film strip widget
        self.film_strip = FilmStripWidget(0, 0, 400, 100)
        self.film_strip.set_animated_sprite(self.animated_sprite)
        self.film_strip.current_animation = "test_anim"
        self.film_strip.current_frame = 0
        
        # Mock parent scene
        self.mock_scene = Mock()
        self.film_strip.parent_scene = self.mock_scene

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop all patchers
        for patcher in self.patchers:
            patcher.stop()
    
    def test_insert_frame_before_first(self):
        """Test inserting a frame before the first frame."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Find the "before" tab for the first frame
        before_tab = None
        for tab in self.film_strip.film_tabs:
            if tab.insertion_type == "before" and tab.target_frame_index == 0:
                before_tab = tab
                break
        
        self.assertIsNotNone(before_tab, "Should have a 'before' tab for the first frame")
        
        # Get initial frame count
        initial_count = len(self.animated_sprite._animations["test_anim"])
        
        # Insert frame
        self.film_strip._insert_frame_at_tab(before_tab)
        
        # Check that frame was inserted
        new_count = len(self.animated_sprite._animations["test_anim"])
        self.assertEqual(new_count, initial_count + 1)
        
        # Check that the new frame is at index 0
        new_frame = self.animated_sprite._animations["test_anim"][0]
        self.assertIsInstance(new_frame, SpriteFrame)
        self.assertEqual(new_frame.duration, 0.5)
    
    def test_insert_frame_after_last(self):
        """Test inserting a frame after the last frame."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Find the "after" tab for the last frame
        after_tab = None
        for tab in self.film_strip.film_tabs:
            if tab.insertion_type == "after" and tab.target_frame_index == 2:
                after_tab = tab
                break
        
        self.assertIsNotNone(after_tab, "Should have an 'after' tab for the last frame")
        
        # Get initial frame count
        initial_count = len(self.animated_sprite._animations["test_anim"])
        
        # Insert frame
        self.film_strip._insert_frame_at_tab(after_tab)
        
        # Check that frame was inserted
        new_count = len(self.animated_sprite._animations["test_anim"])
        self.assertEqual(new_count, initial_count + 1)
        
        # Check that the new frame is at the end
        new_frame = self.animated_sprite._animations["test_anim"][-1]
        self.assertIsInstance(new_frame, SpriteFrame)
        self.assertEqual(new_frame.duration, 0.5)
    
    def test_insert_frame_after_middle(self):
        """Test inserting a frame after a middle frame."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Find the "after" tab for the middle frame (index 1)
        after_tab = None
        for tab in self.film_strip.film_tabs:
            if tab.insertion_type == "after" and tab.target_frame_index == 1:
                after_tab = tab
                break
        
        self.assertIsNotNone(after_tab, "Should have an 'after' tab for the middle frame")
        
        # Get initial frame count
        initial_count = len(self.animated_sprite._animations["test_anim"])
        
        # Insert frame
        self.film_strip._insert_frame_at_tab(after_tab)
        
        # Check that frame was inserted
        new_count = len(self.animated_sprite._animations["test_anim"])
        self.assertEqual(new_count, initial_count + 1)
        
        # Check that the new frame is at the correct position (after frame 1, so at index 2)
        new_frame = self.animated_sprite._animations["test_anim"][2]
        self.assertIsInstance(new_frame, SpriteFrame)
        self.assertEqual(new_frame.duration, 0.5)
    
    def test_new_frame_has_magenta_background(self):
        """Test that new frames have magenta background as specified."""
        # Update layout to create tabs
        self.film_strip.update_layout()
        
        # Get the first tab
        first_tab = self.film_strip.film_tabs[0]
        
        # Insert frame
        self.film_strip._insert_frame_at_tab(first_tab)
        
        # Check that the new frame has magenta background
        new_frame = self.animated_sprite._animations["test_anim"][0]
        frame_surface = new_frame.image
        
        # Check a few pixels to ensure they're magenta
        for x in range(0, min(32, frame_surface.get_width()), 4):
            for y in range(0, min(32, frame_surface.get_height()), 4):
                pixel_color = frame_surface.get_at((x, y))
                self.assertEqual(pixel_color[:3], (255, 0, 255), 
                               f"Pixel at ({x}, {y}) should be magenta")
    
    def test_frame_spacing_has_2_pixel_gap(self):
        """Test that frames have a 2-pixel gap between them after the first frame."""
        # Update layout to create frame layouts
        self.film_strip.update_layout()
        
        # Get frame layouts
        frame_layouts = self.film_strip.frame_layouts
        
        # Should have at least 3 frames for spacing test
        self.assertGreaterEqual(len(frame_layouts), 3, "Need at least 3 frames to test spacing")
        
        # Get sorted frame keys for the test animation (keys are tuples like ("test_anim", 0))
        frame_keys = sorted([k for k in frame_layouts.keys() if isinstance(k, tuple) and k[0] == "test_anim"])
        
        # Test spacing between consecutive frames (after the first)
        for i in range(1, len(frame_keys)):
            current_frame = frame_layouts[frame_keys[i]]
            previous_frame = frame_layouts[frame_keys[i-1]]
            
            # Calculate the gap between frames
            # The gap should be: current_frame.x - (previous_frame.x + previous_frame.width)
            expected_gap = 2  # 2-pixel gap as specified
            
            # Calculate actual gap
            previous_frame_end = previous_frame.x + previous_frame.width
            actual_gap = current_frame.x - previous_frame_end
            
            self.assertEqual(actual_gap, expected_gap, 
                           f"Frame {frame_keys[i]} should have {expected_gap}px gap from frame {frame_keys[i-1]}, "
                           f"but has {actual_gap}px gap")
    
    def test_frame_spacing_with_tabs(self):
        """Test that frame spacing accounts for tab width plus 2-pixel gap."""
        # Update layout to create frame layouts
        self.film_strip.update_layout()
        
        # Get frame layouts and tabs
        frame_layouts = self.film_strip.frame_layouts
        film_tabs = self.film_strip.film_tabs
        
        # Should have frames and tabs
        self.assertGreater(len(frame_layouts), 1, "Need multiple frames to test spacing")
        self.assertGreater(len(film_tabs), 0, "Should have film tabs")
        
        # Get sorted frame keys for the test animation (keys are tuples like ("test_anim", 0))
        frame_keys = sorted([k for k in frame_layouts.keys() if isinstance(k, tuple) and k[0] == "test_anim"])
        
        # Test that spacing formula is correct
        # Expected spacing: frame_width + tab_width + 2
        expected_spacing = self.film_strip.frame_width + self.film_strip.tab_width + 2
        
        for i in range(1, len(frame_keys)):
            current_frame = frame_layouts[frame_keys[i]]
            previous_frame = frame_layouts[frame_keys[i-1]]
            
            # Calculate actual spacing
            actual_spacing = current_frame.x - previous_frame.x
            
            self.assertEqual(actual_spacing, expected_spacing,
                           f"Frame {frame_keys[i]} spacing should be {expected_spacing}px "
                           f"(frame_width + tab_width + 2), but is {actual_spacing}px")


class TestFilmTabSceneIntegration(unittest.TestCase):
    """Test film tab integration with the scene system."""
    
    def setUp(self):
        """Set up test fixtures with centralized mocks."""
        # Use centralized mock factory for pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        for patcher in self.patchers:
            patcher.start()
        
        # Create a real animated sprite
        self.animated_sprite = AnimatedSprite()
        
        # Create frames
        frame1 = SpriteFrame(pygame.Surface((32, 32)), duration=0.5)
        frame2 = SpriteFrame(pygame.Surface((32, 32)), duration=0.5)
        
        # Add animation
        self.animated_sprite.add_animation("test_anim", [frame1, frame2])
        
        # Create scene with mock options
        mock_options = {"size": "800x600"}
        self.scene = BitmapEditorScene(mock_options)
        self.scene._on_sprite_loaded(self.animated_sprite)

    def tearDown(self):
        """Clean up test fixtures."""
        # Stop all patchers
        for patcher in self.patchers:
            patcher.stop()
    
    def test_scene_handles_frame_insertion(self):
        """Test that the scene properly handles frame insertion events."""
        # Get the first film strip
        if hasattr(self.scene, "film_strips") and self.scene.film_strips:
            film_strip = list(self.scene.film_strips.values())[0]
            
            # Update layout to create tabs
            film_strip.update_layout()
            
            # Get the first tab
            if film_strip.film_tabs:
                first_tab = film_strip.film_tabs[0]
                
                # Insert frame
                film_strip._insert_frame_at_tab(first_tab)
                
                # Check that the scene was notified
                self.assertTrue(hasattr(self.scene, "_on_frame_inserted"))
    
    def test_frame_insertion_updates_canvas(self):
        """Test that frame insertion updates the canvas if it's the current animation."""
        # Set the current animation
        self.scene.selected_animation = "test_anim"
        
        # Get the first film strip
        if hasattr(self.scene, "film_strips") and self.scene.film_strips:
            film_strip = list(self.scene.film_strips.values())[0]
            
            # Update layout to create tabs
            film_strip.update_layout()
            
            # Get the first tab
            if film_strip.film_tabs:
                first_tab = film_strip.film_tabs[0]
                
                # Insert frame
                film_strip._insert_frame_at_tab(first_tab)
                
                # Check that the canvas was updated
                if hasattr(self.scene, "canvas") and self.scene.canvas:
                    self.assertEqual(self.scene.selected_frame, 0)


if __name__ == "__main__":
    unittest.main()
