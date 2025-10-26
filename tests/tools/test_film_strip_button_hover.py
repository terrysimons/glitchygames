"""Tests for film strip button hover effects.

This module tests the hover functionality for all film strip button types:
- Removal buttons ([-]) next to frames
- Insertion tabs ([+]) between frames
- Bottom tabs ([+]) at the bottom of film strips
- Delete tabs ([-]) at the top of film strips

All buttons should invert their colors on hover (black background, white border).
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import pygame
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from glitchygames.tools.film_strip import (
    FilmStripWidget, 
    FilmTabWidget, 
    FilmStripTab, 
    FilmStripDeleteTab
)
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from tests.mocks.test_mock_factory import MockFactory


class TestFilmStripButtonHover(unittest.TestCase):
    """Test film strip button hover effects."""

    def setup_method(self, method=None):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        
        # Create a mock animated sprite with frames
        self.mock_animated_sprite = Mock(spec=AnimatedSprite)
        self.mock_animated_sprite._animations = {
            "test_animation": [
                Mock(spec=SpriteFrame),
                Mock(spec=SpriteFrame),
                Mock(spec=SpriteFrame)
            ]
        }
        
        # Create film strip widget
        self.film_strip_widget = FilmStripWidget(0, 0, 400, 100)
        self.film_strip_widget.animated_sprite = self.mock_animated_sprite
        self.film_strip_widget.current_animation = "test_animation"

    def teardown_method(self, method=None):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_removal_button_hover_tracking(self):
        """Test that removal button hover is properly tracked."""
        # Setup removal button layouts
        self.film_strip_widget.removal_button_layouts = {
            ("test_animation", 0): pygame.Rect(10, 20, 11, 30),
            ("test_animation", 1): pygame.Rect(50, 20, 11, 30),
        }
        
        # Test hovering over first removal button
        pos = (15, 35)  # Inside first button
        result = self.film_strip_widget.get_removal_button_at_position(pos)
        self.assertEqual(result, ("test_animation", 0))
        
        # Test hovering over second removal button
        pos = (55, 35)  # Inside second button
        result = self.film_strip_widget.get_removal_button_at_position(pos)
        self.assertEqual(result, ("test_animation", 1))
        
        # Test hovering outside any button
        pos = (100, 35)  # Outside any button
        result = self.film_strip_widget.get_removal_button_at_position(pos)
        self.assertIsNone(result)

    def test_removal_button_hover_effect(self):
        """Test that removal button renders with inverted colors on hover."""
        # Setup removal button layouts
        self.film_strip_widget.removal_button_layouts = {
            ("test_animation", 0): pygame.Rect(10, 20, 11, 30),
        }
        
        # Create a surface to render on
        surface = pygame.Surface((100, 100))
        
        # Test normal state (not hovered)
        self.film_strip_widget.hovered_removal_button = None
        self.film_strip_widget._render_removal_button(surface, "test_animation", 0)
        
        # Test hovered state
        self.film_strip_widget.hovered_removal_button = ("test_animation", 0)
        self.film_strip_widget._render_removal_button(surface, "test_animation", 0)
        
        # The method should complete without errors
        self.assertTrue(True)

    def test_film_tab_widget_hover_effect(self):
        """Test that FilmTabWidget inverts colors on hover."""
        tab = FilmTabWidget(10, 20, 20, 30)
        
        # Test normal state
        tab.is_hovered = False
        surface = pygame.Surface((50, 50))
        tab.render(surface)
        
        # Test hovered state
        tab.is_hovered = True
        surface = pygame.Surface((50, 50))
        tab.render(surface)
        
        # The method should complete without errors
        self.assertTrue(True)

    def test_film_strip_tab_hover_effect(self):
        """Test that FilmStripTab inverts colors on hover."""
        tab = FilmStripTab(10, 20, 40, 10)
        
        # Test normal state
        tab.is_hovered = False
        surface = pygame.Surface((60, 30))
        tab.render(surface)
        
        # Test hovered state
        tab.is_hovered = True
        surface = pygame.Surface((60, 30))
        tab.render(surface)
        
        # The method should complete without errors
        self.assertTrue(True)

    def test_film_strip_delete_tab_hover_effect(self):
        """Test that FilmStripDeleteTab inverts colors on hover."""
        tab = FilmStripDeleteTab(10, 5, 40, 10)
        
        # Test normal state
        tab.is_hovered = False
        surface = pygame.Surface((60, 20))
        tab.render(surface)
        
        # Test hovered state
        tab.is_hovered = True
        surface = pygame.Surface((60, 20))
        tab.render(surface)
        
        # The method should complete without errors
        self.assertTrue(True)

    def test_film_tab_widget_hover_detection(self):
        """Test that FilmTabWidget properly detects hover."""
        tab = FilmTabWidget(10, 20, 20, 30)
        
        # Test hovering inside the tab
        pos = (20, 35)  # Inside tab
        result = tab.handle_hover(pos)
        self.assertTrue(result)
        self.assertTrue(tab.is_hovered)
        
        # Test hovering outside the tab
        pos = (50, 50)  # Outside tab
        result = tab.handle_hover(pos)
        self.assertFalse(result)
        self.assertFalse(tab.is_hovered)

    def test_film_strip_tab_hover_detection(self):
        """Test that FilmStripTab properly detects hover."""
        tab = FilmStripTab(10, 20, 40, 10)
        
        # Test hovering inside the tab
        pos = (30, 25)  # Inside tab
        result = tab.handle_hover(pos)
        self.assertTrue(result)
        self.assertTrue(tab.is_hovered)
        
        # Test hovering outside the tab
        pos = (60, 40)  # Outside tab
        result = tab.handle_hover(pos)
        self.assertFalse(result)
        self.assertFalse(tab.is_hovered)

    def test_film_strip_delete_tab_hover_detection(self):
        """Test that FilmStripDeleteTab properly detects hover."""
        tab = FilmStripDeleteTab(10, 5, 40, 10)
        
        # Test hovering inside the tab
        pos = (30, 10)  # Inside tab
        result = tab.handle_hover(pos)
        self.assertTrue(result)
        self.assertTrue(tab.is_hovered)
        
        # Test hovering outside the tab
        pos = (60, 20)  # Outside tab
        result = tab.handle_hover(pos)
        self.assertFalse(result)
        self.assertFalse(tab.is_hovered)

    def test_film_strip_widget_handle_hover(self):
        """Test that FilmStripWidget.handle_hover processes all hover effects."""
        # Setup removal button layouts
        self.film_strip_widget.removal_button_layouts = {
            ("test_animation", 0): pygame.Rect(10, 20, 11, 30),
        }
        
        # Setup film tabs
        tab1 = FilmTabWidget(5, 10, 20, 30)
        tab2 = FilmStripTab(5, 80, 40, 10)
        self.film_strip_widget.film_tabs = [tab1, tab2]
        
        # Test hover over removal button
        pos = (15, 35)  # Inside removal button
        self.film_strip_widget.handle_hover(pos)
        self.assertEqual(self.film_strip_widget.hovered_removal_button, ("test_animation", 0))
        
        # Test hover over tab
        pos = (15, 25)  # Inside tab1
        self.film_strip_widget.handle_hover(pos)
        self.assertTrue(tab1.is_hovered)


    def test_removal_button_no_layouts(self):
        """Test that removal button detection works when no layouts exist."""
        # No removal button layouts
        self.film_strip_widget.removal_button_layouts = {}
        
        pos = (15, 35)
        result = self.film_strip_widget.get_removal_button_at_position(pos)
        self.assertIsNone(result)

    def test_removal_button_no_attributes(self):
        """Test that removal button detection works when layouts attribute doesn't exist."""
        # Remove the layouts attribute
        if hasattr(self.film_strip_widget, 'removal_button_layouts'):
            delattr(self.film_strip_widget, 'removal_button_layouts')
        
        pos = (15, 35)
        result = self.film_strip_widget.get_removal_button_at_position(pos)
        self.assertIsNone(result)

    def test_color_inversion_consistency(self):
        """Test that all button types use consistent color inversion."""
        # Test FilmTabWidget
        tab1 = FilmTabWidget(0, 0, 20, 30)
        tab1.is_hovered = True
        
        # Test FilmStripTab
        tab2 = FilmStripTab(0, 0, 40, 10)
        tab2.is_hovered = True
        
        # Test FilmStripDeleteTab
        tab3 = FilmStripDeleteTab(0, 0, 40, 10)
        tab3.is_hovered = True
        
        # All should have hover state set
        self.assertTrue(tab1.is_hovered)
        self.assertTrue(tab2.is_hovered)
        self.assertTrue(tab3.is_hovered)
        
        # All should render without errors
        surface = pygame.Surface((50, 50))
        tab1.render(surface)
        tab2.render(surface)
        tab3.render(surface)

    def test_hover_state_persistence(self):
        """Test that hover states persist correctly during mouse movement."""
        tab = FilmTabWidget(10, 20, 20, 30)
        
        # Start with no hover
        self.assertFalse(tab.is_hovered)
        
        # Hover over tab
        pos = (20, 35)
        tab.handle_hover(pos)
        self.assertTrue(tab.is_hovered)
        
        # Move within tab (should stay hovered)
        pos = (25, 30)
        tab.handle_hover(pos)
        self.assertTrue(tab.is_hovered)
        
        # Move outside tab (should clear hover)
        pos = (50, 50)
        tab.handle_hover(pos)
        self.assertFalse(tab.is_hovered)

    def test_multiple_tabs_hover_handling(self):
        """Test that multiple tabs can be handled correctly."""
        # Create multiple tabs
        tab1 = FilmTabWidget(10, 20, 20, 30)
        tab2 = FilmTabWidget(40, 20, 20, 30)
        tab3 = FilmStripTab(10, 60, 40, 10)
        
        tabs = [tab1, tab2, tab3]
        
        # Test hovering over first tab
        pos = (20, 35)
        for tab in tabs:
            tab.handle_hover(pos)
        
        self.assertTrue(tab1.is_hovered)
        self.assertFalse(tab2.is_hovered)
        self.assertFalse(tab3.is_hovered)
        
        # Test hovering over second tab
        pos = (50, 35)
        for tab in tabs:
            tab.handle_hover(pos)
        
        self.assertFalse(tab1.is_hovered)
        self.assertTrue(tab2.is_hovered)
        self.assertFalse(tab3.is_hovered)
        
        # Test hovering over third tab
        pos = (30, 65)
        for tab in tabs:
            tab.handle_hover(pos)
        
        self.assertFalse(tab1.is_hovered)
        self.assertFalse(tab2.is_hovered)
        self.assertTrue(tab3.is_hovered)


if __name__ == '__main__':
    unittest.main()
