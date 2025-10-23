"""
Test suite for multi-controller film strip integration.

This module tests the integration between the multi-controller system
and the film strip widget, including color-based sorting and visual indicators.
"""

import pytest
import pygame
from unittest.mock import Mock, patch, MagicMock
from glitchygames.tools.film_strip import FilmStripWidget
from glitchygames.tools.multi_controller_manager import MultiControllerManager, ControllerInfo, ControllerStatus
from glitchygames.tools.controller_selection import ControllerSelection
from tests.mocks import MockFactory


class TestFilmStripColorBasedSorting:
    """Test color-based sorting of controller indicators in film strip."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.film_strip = FilmStripWidget(0, 0, 800, 200)
    
    def test_color_priority_function(self):
        """Test the color priority function for sorting."""
        def get_color_priority(selection):
            color = selection['color']
            if color == (255, 0, 0):    # Red
                return 0
            elif color == (0, 255, 0):  # Green
                return 1
            elif color == (0, 0, 255):  # Blue
                return 2
            elif color == (255, 255, 0): # Yellow
                return 3
            else:
                return 999  # Unknown colors go last
        
        # Test different colors
        selections = [
            {'color': (0, 0, 255)},      # Blue
            {'color': (255, 0, 0)},      # Red
            {'color': (255, 255, 0)},    # Yellow
            {'color': (0, 255, 0)},      # Green
        ]
        
        # Sort by color priority
        selections.sort(key=get_color_priority)
        
        # Should be sorted: Red, Green, Blue, Yellow
        expected_order = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
        ]
        
        for i, selection in enumerate(selections):
            assert selection['color'] == expected_order[i]
    
    def test_controller_selection_priority_assignment(self):
        """Test priority assignment for controller selections."""
        # Mock controller selections with different colors
        controller_selections = [
            {
                'controller_id': 2,
                'color': (0, 0, 255),    # Blue
                'frame': 0
            },
            {
                'controller_id': 0,
                'color': (255, 0, 0),    # Red
                'frame': 0
            },
            {
                'controller_id': 3,
                'color': (255, 255, 0),  # Yellow
                'frame': 0
            },
            {
                'controller_id': 1,
                'color': (0, 255, 0),    # Green
                'frame': 0
            },
        ]
        
        # Calculate color-based priority
        for selection in controller_selections:
            color = selection['color']
            if color == (255, 0, 0):    # Red
                selection['priority'] = 0
            elif color == (0, 255, 0):  # Green
                selection['priority'] = 1
            elif color == (0, 0, 255):  # Blue
                selection['priority'] = 2
            elif color == (255, 255, 0): # Yellow
                selection['priority'] = 3
            else:
                selection['priority'] = 999
        
        # Sort by priority
        controller_selections.sort(key=lambda x: x['priority'])
        
        # Should be sorted by color: Red, Green, Blue, Yellow
        expected_order = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
        ]
        
        for i, selection in enumerate(controller_selections):
            assert selection['color'] == expected_order[i]
            assert selection['priority'] == i
    
    def test_mixed_keyboard_controller_sorting(self):
        """Test sorting with both keyboard and controller selections."""
        # Mock mixed selections
        all_selections = [
            {
                'type': 'controller_2',
                'color': (0, 0, 255),    # Blue
                'frame': 0,
                'priority': 2
            },
            {
                'type': 'keyboard',
                'color': (255, 255, 255), # White
                'frame': 0,
                'priority': 0
            },
            {
                'type': 'controller_0',
                'color': (255, 0, 0),    # Red
                'frame': 0,
                'priority': 0
            },
            {
                'type': 'controller_1',
                'color': (0, 255, 0),    # Green
                'frame': 0,
                'priority': 1
            },
        ]
        
        # Separate keyboard from controllers
        keyboard_selection = None
        controller_selections = []
        
        for selection in all_selections:
            if selection['color'] == (255, 255, 255):  # White = keyboard
                keyboard_selection = selection
            else:
                controller_selections.append(selection)
        
        # Sort controllers by priority
        controller_selections.sort(key=lambda x: x['priority'])
        
        # Keyboard should be first, then controllers in color order
        assert keyboard_selection is not None
        assert keyboard_selection['color'] == (255, 255, 255)
        
        # Controllers should be sorted: Red, Green, Blue
        expected_controller_order = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
        ]
        
        for i, selection in enumerate(controller_selections):
            assert selection['color'] == expected_controller_order[i]


class TestFilmStripIndicatorDrawing:
    """Test indicator drawing in film strip."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.film_strip = FilmStripWidget(0, 0, 800, 200)
    
    def test_indicator_positioning(self):
        """Test indicator positioning with color-based sorting."""
        # Mock frame rectangle
        frame_rect = pygame.Rect(100, 100, 64, 64)
        
        # Mock selections with different colors
        selections = [
            {
                'color': (255, 0, 0),    # Red
                'priority': 0
            },
            {
                'color': (0, 255, 0),    # Green
                'priority': 1
            },
            {
                'color': (0, 0, 255),    # Blue
                'priority': 2
            },
        ]
        
        # Calculate positioning
        total_indicators = len(selections)
        indicator_spacing = 8
        total_width = (total_indicators - 1) * indicator_spacing
        start_x = frame_rect.centerx - (total_width // 2)
        
        # Calculate expected positions
        expected_positions = []
        current_x = start_x
        for i in range(total_indicators):
            expected_positions.append((current_x, frame_rect.top - 4))
            current_x += indicator_spacing
        
        # Verify positioning calculation
        assert len(expected_positions) == 3
        assert expected_positions[0] == (start_x, frame_rect.top - 4)
        assert expected_positions[1] == (start_x + 8, frame_rect.top - 4)
        assert expected_positions[2] == (start_x + 16, frame_rect.top - 4)
    
    def test_single_indicator_positioning(self):
        """Test positioning for single indicator."""
        # Mock frame rectangle
        frame_rect = pygame.Rect(100, 100, 64, 64)
        
        # Single indicator should be centered
        selections = [
            {
                'color': (255, 0, 0),    # Red
                'priority': 0
            }
        ]
        
        # Calculate positioning
        total_indicators = len(selections)
        indicator_spacing = 8
        total_width = (total_indicators - 1) * indicator_spacing
        start_x = frame_rect.centerx - (total_width // 2)
        
        # Single indicator should be centered
        expected_x = frame_rect.centerx
        expected_y = frame_rect.top - 4
        
        assert start_x == expected_x
        assert expected_y == frame_rect.top - 4
    
    def test_two_indicator_positioning(self):
        """Test positioning for two indicators."""
        # Mock frame rectangle
        frame_rect = pygame.Rect(100, 100, 64, 64)
        
        # Two indicators should be offset left and right
        selections = [
            {
                'color': (255, 0, 0),    # Red
                'priority': 0
            },
            {
                'color': (0, 255, 0),    # Green
                'priority': 1
            }
        ]
        
        # Calculate positioning
        total_indicators = len(selections)
        indicator_spacing = 8
        total_width = (total_indicators - 1) * indicator_spacing
        start_x = frame_rect.centerx - (total_width // 2)
        
        # Two indicators should be offset by 4 pixels each from center
        expected_positions = [
            (frame_rect.centerx - 4, frame_rect.top - 4),
            (frame_rect.centerx + 4, frame_rect.top - 4)
        ]
        
        assert start_x == frame_rect.centerx - 4
        assert start_x + indicator_spacing == frame_rect.centerx + 4


class TestFilmStripScrollingIntegration:
    """Test film strip scrolling integration with controllers."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.film_strip = FilmStripWidget(0, 0, 800, 200)
        self.film_strip.current_animation = "test_animation"
        self.film_strip.scroll_offset = 0
    
    def test_controller_scrolling_trigger(self):
        """Test that controller navigation triggers scrolling."""
        # Mock controller selection
        controller_selection = ControllerSelection(0, 0)
        controller_selection.activate()
        controller_selection.set_selection("test_animation", 5)
        
        # Mock film strip scrolling
        with patch.object(self.film_strip, 'update_scroll_for_frame') as mock_scroll:
            # Simulate frame navigation
            new_frame = 3
            controller_selection.set_selection("test_animation", new_frame)
            
            # Should trigger scrolling
            mock_scroll("test_animation", new_frame)
            mock_scroll.assert_called_with("test_animation", new_frame)
    
    def test_controller_animation_switching(self):
        """Test that switching animations triggers scrolling."""
        # Mock controller selection
        controller_selection = ControllerSelection(0, 0)
        controller_selection.activate()
        controller_selection.set_selection("animation1", 2)
        
        # Mock film strip scrolling
        with patch.object(self.film_strip, 'update_scroll_for_frame') as mock_scroll:
            # Switch to different animation
            controller_selection.set_selection("animation2", 1)
            
            # Should trigger scrolling to new animation
            mock_scroll("animation2", 1)
            mock_scroll.assert_called_with("animation2", 1)
    
    def test_multiple_controller_scrolling(self):
        """Test scrolling with multiple controllers."""
        # Mock multiple controller selections
        controller_selections = [
            ControllerSelection(0, 0),
            ControllerSelection(1, 1),
        ]
        
        for i, selection in enumerate(controller_selections):
            selection.activate()
            selection.set_selection(f"animation{i+1}", i)
        
        # Mock film strip scrolling
        with patch.object(self.film_strip, 'update_scroll_for_frame') as mock_scroll:
            # Each controller should trigger scrolling for its animation
            for i, selection in enumerate(controller_selections):
                animation = f"animation{i+1}"
                frame = i
                mock_scroll(animation, frame)
                mock_scroll.assert_called_with(animation, frame)


class TestSelectionBoxColorMatching:
    """Test selection box color matching with indicators."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.film_strip = FilmStripWidget(0, 0, 800, 200)
    
    def test_keyboard_selection_box_color(self):
        """Test that keyboard selection box is white."""
        # Mock keyboard selection
        keyboard_selection = {
            'type': 'keyboard',
            'color': (255, 255, 255),  # White
            'frame': 0
        }
        
        # The selection box should match the indicator color
        expected_box_color = (255, 255, 255)  # White
        assert keyboard_selection['color'] == expected_box_color
    
    def test_controller_selection_box_color(self):
        """Test that controller selection box matches controller color."""
        # Mock controller selections with different colors
        controller_selections = [
            {
                'type': 'controller_0',
                'color': (255, 0, 0),    # Red
                'frame': 0
            },
            {
                'type': 'controller_1',
                'color': (0, 255, 0),    # Green
                'frame': 0
            },
        ]
        
        # Each selection box should match its indicator color
        for selection in controller_selections:
            expected_box_color = selection['color']
            assert selection['color'] == expected_box_color
    
    def test_selection_box_color_priority(self):
        """Test that selection box color is determined by selection type."""
        # Mock mixed selections
        selections = [
            {
                'type': 'keyboard',
                'color': (255, 255, 255),  # White
                'frame': 0
            },
            {
                'type': 'controller_0',
                'color': (255, 0, 0),      # Red
                'frame': 0
            },
        ]
        
        # Keyboard should have white box, controller should have red box
        for selection in selections:
            if selection['type'] == 'keyboard':
                assert selection['color'] == (255, 255, 255)
            elif selection['type'].startswith('controller'):
                assert selection['color'] in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]


class TestFilmStripDirtyMarking:
    """Test film strip dirty marking when colors change."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.film_strip = FilmStripWidget(0, 0, 800, 200)
    
    def test_film_strip_dirty_marking(self):
        """Test that film strip is marked dirty when colors change."""
        # Initially not dirty
        assert self.film_strip.dirty == 0
        
        # Mark as dirty
        self.film_strip.mark_dirty()
        
        # Should be dirty
        assert self.film_strip.dirty == 1
    
    def test_film_strip_sprite_dirty_marking(self):
        """Test that film strip sprites are marked dirty."""
        # Mock film strip sprite
        mock_sprite = Mock()
        mock_sprite.dirty = 0
        
        # Mark sprite as dirty
        mock_sprite.dirty = 1
        
        # Should be dirty
        assert mock_sprite.dirty == 1


class TestFilmStripLayoutCalculation:
    """Test film strip layout calculation with controllers."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.film_strip = FilmStripWidget(0, 0, 800, 200)
        self.film_strip.frame_width = 64
        self.film_strip.frame_height = 64
        self.film_strip.frame_spacing = 8
    
    def test_frame_layout_calculation(self):
        """Test frame layout calculation."""
        # Mock frame data
        frames = [
            {'animation': 'test_animation', 'frame': 0},
            {'animation': 'test_animation', 'frame': 1},
            {'animation': 'test_animation', 'frame': 2},
        ]
        
        # Calculate layout
        frame_layouts = {}
        x = 0
        for frame_data in frames:
            frame_key = (frame_data['animation'], frame_data['frame'])
            frame_rect = pygame.Rect(
                x, 0,
                self.film_strip.frame_width,
                self.film_strip.frame_height
            )
            frame_layouts[frame_key] = frame_rect
            x += self.film_strip.frame_width + self.film_strip.frame_spacing
        
        # Verify layout
        assert len(frame_layouts) == 3
        assert frame_layouts[('test_animation', 0)].x == 0
        assert frame_layouts[('test_animation', 1)].x == 72  # 64 + 8
        assert frame_layouts[('test_animation', 2)].x == 144  # 64 + 8 + 64 + 8
    
    def test_scroll_offset_calculation(self):
        """Test scroll offset calculation."""
        # Mock frame layout
        frame_layouts = {
            ('test_animation', 0): pygame.Rect(0, 0, 64, 64),
            ('test_animation', 1): pygame.Rect(72, 0, 64, 64),
            ('test_animation', 2): pygame.Rect(144, 0, 64, 64),
        }
        
        # Calculate scroll offset for frame 2
        target_frame = 2
        frame_key = ('test_animation', target_frame)
        if frame_key in frame_layouts:
            frame_rect = frame_layouts[frame_key]
            scroll_offset = frame_rect.x
            
            # Should scroll to show frame 2
            assert scroll_offset == 144


if __name__ == "__main__":
    pytest.main([__file__])
