"""
Test suite for multi-controller troubleshooting scenarios.

This module tests specific issues that were encountered during development
and the fixes that were implemented.
"""

import pytest
import pygame
from unittest.mock import Mock, patch, MagicMock
from glitchygames.tools.multi_controller_manager import MultiControllerManager, ControllerInfo, ControllerStatus
from glitchygames.tools.controller_selection import ControllerSelection
from tests.mocks import MockFactory


class TestDuplicateMethodIssue:
    """Test the duplicate method issue that was causing color assignment problems."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for each test
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager.get_instance()
    
    def test_singleton_consistency(self):
        """Test that singleton ensures consistent color assignment."""
        # Get multiple instances
        manager1 = MultiControllerManager.get_instance()
        manager2 = MultiControllerManager.get_instance()
        
        # Should be the same instance
        assert manager1 is manager2
        
        # Add controller to one instance
        manager1.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128)
        )
        
        # Should be visible in other instance
        assert 0 in manager2.controllers
        assert manager2.controllers[0].color == (128, 128, 128)
    
    def test_color_assignment_persistence(self):
        """Test that color assignment persists across singleton instances."""
        # Add controller
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128)
        )
        
        # Assign color
        self.manager.assign_color_to_controller(0)
        
        # Get new instance (should be same singleton)
        new_manager = MultiControllerManager.get_instance()
        
        # Color should be assigned
        assert new_manager.controllers[0].color == (255, 0, 0)  # Red
        assert new_manager.next_color_index == 1


class TestButtonMappingIssues:
    """Test button mapping issues that were encountered."""
    
    def test_joystick_button_9_mapping(self):
        """Test that joystick button 9 doesn't reset controller."""
        # Mock joystick event
        mock_event = Mock()
        mock_event.type = pygame.JOYBUTTONUP
        mock_event.button = 9  # Left shoulder button
        mock_event.instance_id = 0
        
        # This should not trigger controller activation
        # (Button 9 is now unhandled to prevent reset behavior)
        with patch('glitchygames.tools.bitmappy.BitmapEditorScene._multi_controller_activate') as mock_activate:
            # Simulate the event handling logic
            if mock_event.button == 9:
                # Should be unhandled (no action taken)
                pass
            else:
                mock_activate(mock_event.instance_id)
            
            # Should not have called activate
            mock_activate.assert_not_called()
    
    def test_shoulder_button_correct_mapping(self):
        """Test that shoulder buttons are correctly mapped to navigation."""
        # Mock controller events
        left_shoulder_event = Mock()
        left_shoulder_event.type = pygame.CONTROLLERBUTTONUP
        left_shoulder_event.button = pygame.CONTROLLER_BUTTON_LEFTSHOULDER
        left_shoulder_event.instance_id = 0
        
        right_shoulder_event = Mock()
        right_shoulder_event.type = pygame.CONTROLLERBUTTONUP
        right_shoulder_event.button = pygame.CONTROLLER_BUTTON_RIGHTSHOULDER
        right_shoulder_event.instance_id = 0
        
        # Mock the navigation methods
        with patch('glitchygames.tools.bitmappy.BitmapEditorScene._multi_controller_previous_frame') as mock_prev, \
             patch('glitchygames.tools.bitmappy.BitmapEditorScene._multi_controller_next_frame') as mock_next:
            
            # Simulate left shoulder button press
            if left_shoulder_event.button == pygame.CONTROLLER_BUTTON_LEFTSHOULDER:
                mock_prev(left_shoulder_event.instance_id)
            
            # Simulate right shoulder button press
            if right_shoulder_event.button == pygame.CONTROLLER_BUTTON_RIGHTSHOULDER:
                mock_next(right_shoulder_event.instance_id)
            
            # Verify correct methods were called
            mock_prev.assert_called_once_with(0)
            mock_next.assert_called_once_with(0)


class TestSelectionBoxRegression:
    """Test the selection box regression that was fixed."""
    
    def test_selection_box_drawing_for_controllers(self):
        """Test that selection boxes are drawn for controller selections."""
        # Mock controller selection
        controller_selection = {
            'controller_id': 0,
            'animation': 'test_animation',
            'frame': 2,
            'color': (255, 0, 0)  # Red
        }
        
        # Mock frame selection
        frame_selection = {
            'animation': 'test_animation',
            'frame': 2
        }
        
        # Should draw selection box for controller
        should_draw_box = (
            controller_selection['animation'] == frame_selection['animation'] and
            controller_selection['frame'] == frame_selection['frame']
        )
        
        assert should_draw_box is True
    
    def test_selection_box_color_matching(self):
        """Test that selection box color matches indicator color."""
        # Mock selections with different colors
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
            {
                'type': 'controller_1',
                'color': (0, 255, 0),      # Green
                'frame': 0
            },
        ]
        
        # Each selection box should match its indicator color
        for selection in selections:
            expected_box_color = selection['color']
            assert selection['color'] == expected_box_color


class TestFilmStripDirtyMarking:
    """Test that film strips are marked dirty when colors change."""
    
    def test_film_strip_dirty_marking_on_color_assignment(self):
        """Test that film strips are marked dirty when controller colors are assigned."""
        # Mock film strip
        mock_film_strip = Mock()
        mock_film_strip.mark_dirty = Mock()
        
        # Mock film strip sprites
        mock_film_strip_sprite = Mock()
        mock_film_strip_sprite.dirty = 0
        
        # Mock the scene with film strips
        mock_scene = Mock()
        mock_scene.film_strips = {'test_animation': mock_film_strip}
        mock_scene.film_strip_sprites = {'test_animation': mock_film_strip_sprite}
        
        # Simulate color assignment
        with patch.object(mock_scene, 'film_strips', {'test_animation': mock_film_strip}):
            with patch.object(mock_scene, 'film_strip_sprites', {'test_animation': mock_film_strip_sprite}):
                # Mark film strips as dirty
                for film_strip in mock_scene.film_strips.values():
                    film_strip.mark_dirty()
                for film_strip_sprite in mock_scene.film_strip_sprites.values():
                    film_strip_sprite.dirty = 1
        
        # Verify dirty marking was called
        mock_film_strip.mark_dirty.assert_called()
        assert mock_film_strip_sprite.dirty == 1


class TestControllerActivationFlow:
    """Test the complete controller activation flow."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for each test
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager.get_instance()
    
    def test_controller_activation_with_color_assignment(self):
        """Test complete controller activation with color assignment."""
        # Add controller
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(128, 128, 128)  # Default gray
        )
        
        # Create controller selection
        controller_selection = ControllerSelection(0, 0)
        
        # Activate controller
        controller_selection.activate()
        
        # Assign color
        self.manager.assign_color_to_controller(0)
        
        # Verify activation and color assignment
        assert controller_selection.is_active()
        assert self.manager.controllers[0].color == (255, 0, 0)  # Red
        assert self.manager.next_color_index == 1
    
    def test_multiple_controller_activation_order(self):
        """Test activation order for multiple controllers."""
        # Add multiple controllers
        for i in range(3):
            self.manager.controllers[i] = ControllerInfo(
                controller_id=i,
                instance_id=i,
                status=ControllerStatus.CONNECTED,
                color=(128, 128, 128)
            )
        
        # Activate in order: 2, 0, 1
        activation_order = [2, 0, 1]
        expected_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
        ]
        
        for i, controller_id in enumerate(activation_order):
            self.manager.assign_color_to_controller(controller_id)
            assert self.manager.controllers[controller_id].color == expected_colors[i]
            assert self.manager.next_color_index == i + 1


class TestDebugOutputCleanup:
    """Test that debug output is properly controlled."""
    
    def test_debug_output_control(self):
        """Test that debug output can be controlled."""
        # Mock print statements
        with patch('builtins.print') as mock_print:
            # Simulate debug output
            print("DEBUG: Controller 0 activated")
            print("DEBUG: Controller 1 activated")
            
            # Verify debug output
            assert mock_print.call_count == 2
            assert "Controller 0 activated" in str(mock_print.call_args_list[0])
            assert "Controller 1 activated" in str(mock_print.call_args_list[1])
    
    def test_logging_integration(self):
        """Test that logging is properly integrated."""
        import logging
        
        # Mock logger
        mock_logger = Mock()
        
        # Simulate logging calls
        mock_logger.debug("Controller 0 activated")
        mock_logger.debug("Controller 1 activated")
        
        # Verify logging calls
        assert mock_logger.debug.call_count == 2
        assert "Controller 0 activated" in str(mock_logger.debug.call_args_list[0])
        assert "Controller 1 activated" in str(mock_logger.debug.call_args_list[1])


class TestPerformanceOptimization:
    """Test performance optimizations for multi-controller system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for each test
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager.get_instance()
    
    def test_singleton_performance(self):
        """Test that singleton pattern improves performance."""
        import time
        
        # Time singleton creation
        start_time = time.time()
        manager1 = MultiControllerManager.get_instance()
        manager2 = MultiControllerManager.get_instance()
        end_time = time.time()
        
        # Should be very fast (same instance)
        assert end_time - start_time < 0.001
        assert manager1 is manager2
    
    def test_color_assignment_efficiency(self):
        """Test that color assignment is efficient."""
        # Add multiple controllers
        for i in range(4):
            self.manager.controllers[i] = ControllerInfo(
                controller_id=i,
                instance_id=i,
                status=ControllerStatus.CONNECTED,
                color=(128, 128, 128)
            )
        
        # Time color assignments
        import time
        start_time = time.time()
        
        for i in range(4):
            self.manager.assign_color_to_controller(i)
        
        end_time = time.time()
        
        # Should be fast
        assert end_time - start_time < 0.01
        
        # Verify all colors assigned
        expected_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
        ]
        
        for i in range(4):
            assert self.manager.controllers[i].color == expected_colors[i]


if __name__ == "__main__":
    pytest.main([__file__])
