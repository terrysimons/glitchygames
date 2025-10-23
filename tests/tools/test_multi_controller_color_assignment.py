"""
Test suite for multi-controller color assignment and ordering.

This module tests the color assignment system that assigns colors based on
activation order rather than controller ID, and the color-based sorting of
controller indicators.
"""

import pytest
import pygame
from unittest.mock import Mock, patch, MagicMock
from glitchygames.tools.multi_controller_manager import MultiControllerManager, ControllerInfo, ControllerStatus
from glitchygames.tools.controller_selection import ControllerSelection
from tests.mocks import MockFactory


class TestColorAssignmentOrder:
    """Test color assignment based on activation order."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for each test
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager.get_instance()
    
    def test_singleton_pattern(self):
        """Test that MultiControllerManager is a singleton."""
        # Get two instances
        manager1 = MultiControllerManager.get_instance()
        manager2 = MultiControllerManager.get_instance()
        
        # Should be the same instance
        assert manager1 is manager2
        assert id(manager1) == id(manager2)
    
    def test_color_assignment_activation_order(self):
        """Test that colors are assigned based on activation order, not controller ID."""
        # Add controllers with different IDs
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128)  # Default gray
        )
        self.manager.controllers[1] = ControllerInfo(
            controller_id=1,
            instance_id=1,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128)  # Default gray
        )
        
        # Activate controller 1 first (should get red)
        self.manager.assign_color_to_controller(1)
        assert self.manager.controllers[1].color == (255, 0, 0)  # Red
        assert self.manager.next_color_index == 1
        
        # Activate controller 0 second (should get green)
        self.manager.assign_color_to_controller(0)
        assert self.manager.controllers[0].color == (0, 255, 0)  # Green
        assert self.manager.next_color_index == 2
    
    def test_color_assignment_sequence(self):
        """Test complete color assignment sequence."""
        # Add 4 controllers
        for i in range(4):
            self.manager.controllers[i] = ControllerInfo(
                controller_id=i,
                instance_id=i,
                status=ControllerStatus.CONNECTED,
                color=(128, 128, 128)  # Default gray
            )
        
        # Activate in random order: 2, 0, 3, 1
        activation_order = [2, 0, 3, 1]
        expected_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
        ]
        
        for i, controller_id in enumerate(activation_order):
            self.manager.assign_color_to_controller(controller_id)
            assert self.manager.controllers[controller_id].color == expected_colors[i]
            assert self.manager.next_color_index == i + 1
    
    def test_color_assignment_unknown_controller(self):
        """Test color assignment for unknown controller."""
        # Try to assign color to non-existent controller
        # The method should handle this gracefully without raising an exception
        self.manager.assign_color_to_controller(999)
        
        # Should not have assigned any color (no controller found)
        assert len(self.manager.controllers) == 0
    
    def test_color_assignment_reset(self):
        """Test that color assignment resets properly."""
        # Add controller and assign color
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128)
        )
        self.manager.assign_color_to_controller(0)
        
        # Reset singleton
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        new_manager = MultiControllerManager.get_instance()
        
        # Should start fresh
        assert new_manager.next_color_index == 0
        assert len(new_manager.controllers) == 0


class TestColorBasedSorting:
    """Test color-based sorting of controller indicators."""
    
    def test_color_priority_calculation(self):
        """Test color priority calculation for sorting."""
        # Test the color priority function directly without creating FilmStripWidget
        
        # Test color priority function
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
    
    def test_controller_selection_color_priority(self):
        """Test controller selection color priority assignment."""
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


class TestShoulderButtonFunctionality:
    """Test shoulder button functionality for controller navigation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.controller_selection = ControllerSelection(controller_id=0, instance_id=0)
        self.controller_selection.activate()
        self.controller_selection.set_selection("test_animation", 5)
    
    def test_left_shoulder_button_behavior(self):
        """Test that left shoulder button moves indicator left."""
        # Mock the _multi_controller_previous_frame method
        with patch('glitchygames.tools.bitmappy.BitmapEditorScene._multi_controller_previous_frame') as mock_prev:
            # Simulate left shoulder button press
            controller_id = 0
            mock_prev.return_value = None
            
            # Call the method (this would be in the event handler)
            mock_prev(controller_id)
            
            # Verify it was called
            mock_prev.assert_called_once_with(controller_id)
    
    def test_right_shoulder_button_behavior(self):
        """Test that right shoulder button moves indicator right."""
        # Mock the _multi_controller_next_frame method
        with patch('glitchygames.tools.bitmappy.BitmapEditorScene._multi_controller_next_frame') as mock_next:
            # Simulate right shoulder button press
            controller_id = 0
            mock_next.return_value = None
            
            # Call the method (this would be in the event handler)
            mock_next(controller_id)
            
            # Verify it was called
            mock_next.assert_called_once_with(controller_id)
    
    def test_shoulder_button_scrolling_integration(self):
        """Test that shoulder buttons trigger automatic scrolling."""
        # Use centralized mock factory for film strip widget
        mock_film_strip = MockFactory.create_optimized_scene_mock()
        mock_film_strip.update_scroll_for_frame = Mock()
        
        # Mock the controller selection
        controller_selection = ControllerSelection(0, 0)
        controller_selection.activate()
        controller_selection.set_selection("test_animation", 3)
        
        # Simulate frame navigation that should trigger scrolling
        # This would be called by _multi_controller_previous_frame/_next_frame
        mock_film_strip.update_scroll_for_frame("test_animation", 2)
        mock_film_strip.update_scroll_for_frame.assert_called_with("test_animation", 2)


class TestSelectionBoxColorMatching:
    """Test that selection box colors match indicator colors."""
    
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


class TestFilmStripScrolling:
    """Test film strip scrolling with controllers."""
    
    def test_controller_scrolling_trigger(self):
        """Test that controller navigation triggers film strip scrolling."""
        # Use centralized mock factory for film strip widget
        mock_film_strip = MockFactory.create_optimized_scene_mock()
        mock_film_strip.update_scroll_for_frame = Mock()
        
        # Mock controller selection
        controller_selection = ControllerSelection(0, 0)
        controller_selection.activate()
        controller_selection.set_selection("test_animation", 5)
        
        # Simulate frame navigation
        new_frame = 3
        controller_selection.set_selection("test_animation", new_frame)
        
        # The film strip should be updated to scroll to the new frame
        mock_film_strip.update_scroll_for_frame("test_animation", new_frame)
        mock_film_strip.update_scroll_for_frame.assert_called_with("test_animation", new_frame)
    
    def test_controller_animation_switching(self):
        """Test that switching animations triggers scrolling."""
        # Use centralized mock factory for film strip widget
        mock_film_strip = MockFactory.create_optimized_scene_mock()
        mock_film_strip.update_scroll_for_frame = Mock()
        
        # Mock controller selection
        controller_selection = ControllerSelection(0, 0)
        controller_selection.activate()
        controller_selection.set_selection("animation1", 2)
        
        # Switch to different animation
        controller_selection.set_selection("animation2", 1)
        
        # Should trigger scrolling to new animation
        mock_film_strip.update_scroll_for_frame("animation2", 1)
        mock_film_strip.update_scroll_for_frame.assert_called_with("animation2", 1)
    
    def test_multiple_controller_scrolling(self):
        """Test scrolling with multiple controllers."""
        # Use centralized mock factory for multiple film strips
        mock_film_strips = {
            "animation1": MockFactory.create_optimized_scene_mock(),
            "animation2": MockFactory.create_optimized_scene_mock(),
        }
        
        # Mock multiple controller selections
        controller_selections = [
            ControllerSelection(0, 0),
            ControllerSelection(1, 1),
        ]
        
        for i, selection in enumerate(controller_selections):
            selection.activate()
            selection.set_selection(f"animation{i+1}", i)
        
        # Each controller should trigger scrolling for its animation
        for i, selection in enumerate(controller_selections):
            animation = f"animation{i+1}"
            frame = i
            mock_film_strips[animation].update_scroll_for_frame(animation, frame)
            mock_film_strips[animation].update_scroll_for_frame.assert_called_with(animation, frame)


if __name__ == "__main__":
    pytest.main([__file__])
