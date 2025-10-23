"""
Test suite for multi-controller system.

This module provides comprehensive tests for the multi-controller navigation system,
including controller assignment, selection management, visual collision avoidance,
and integration with the bitmappy tool.
"""

import pytest
import pygame
import time
from unittest.mock import Mock, patch, MagicMock
from glitchygames.tools.multi_controller_manager import MultiControllerManager, ControllerInfo, ControllerStatus
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager, VisualIndicator, IndicatorShape


class TestMultiControllerManager:
    """Test cases for MultiControllerManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = MultiControllerManager()
    
    def test_initialization(self):
        """Test manager initialization."""
        assert self.manager.controllers == {}
        assert self.manager.assigned_controllers == {}
        assert self.manager.next_controller_id == 0
        assert self.manager.MAX_CONTROLLERS == 4
    
    def test_controller_colors(self):
        """Test controller color scheme."""
        expected_colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
        ]
        assert self.manager.CONTROLLER_COLORS == expected_colors
    
    @patch('pygame.joystick.get_count')
    @patch('pygame.joystick.Joystick')
    def test_scan_for_controllers(self, mock_joystick_class, mock_get_count):
        """Test controller scanning."""
        # Mock pygame joystick
        mock_joystick = Mock()
        mock_joystick.get_init.return_value = True
        mock_joystick.get_instance_id.return_value = 0
        mock_joystick_class.return_value = mock_joystick
        mock_get_count.return_value = 1
        
        # Test scanning
        connected_ids = self.manager.scan_for_controllers()
        
        assert len(connected_ids) == 1
        assert 0 in connected_ids
        assert 0 in self.manager.controllers
    
    def test_controller_assignment(self):
        """Test controller assignment."""
        # Add a connected controller
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(255, 0, 0)
        )
        
        # Assign controller
        controller_id = self.manager.assign_controller(0)
        
        assert controller_id == 0
        assert 0 in self.manager.assigned_controllers
        assert self.manager.controllers[0].status == ControllerStatus.ASSIGNED
    
    def test_controller_activation(self):
        """Test controller activation."""
        # Add an assigned controller
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.ASSIGNED,
            color=(255, 0, 0)
        )
        self.manager.assigned_controllers[0] = 0
        
        # Activate controller
        result = self.manager.activate_controller(0)
        
        assert result is True
        assert self.manager.controllers[0].status == ControllerStatus.ACTIVE
    
    def test_controller_info_retrieval(self):
        """Test controller info retrieval."""
        # Add a controller
        controller_info = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(255, 0, 0)
        )
        self.manager.controllers[0] = controller_info
        
        # Test retrieval
        retrieved_info = self.manager.get_controller_info(0)
        assert retrieved_info == controller_info
        
        # Test non-existent controller
        assert self.manager.get_controller_info(999) is None
    
    def test_controller_color_retrieval(self):
        """Test controller color retrieval."""
        # Add a controller with color
        controller_info = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(255, 0, 0)
        )
        self.manager.controllers[0] = controller_info
        
        # Test color retrieval
        color = self.manager.get_controller_color(0)
        assert color == (255, 0, 0)
        
        # Test non-existent controller
        assert self.manager.get_controller_color(999) is None
    
    def test_activity_tracking(self):
        """Test controller activity tracking."""
        # Add a controller
        controller_info = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.ACTIVE,
            color=(255, 0, 0)
        )
        self.manager.controllers[0] = controller_info
        
        # Update activity
        self.manager.update_controller_activity(0)
        
        # Check that last_activity was updated
        assert self.manager.controllers[0].last_activity is not None
    
    def test_active_controllers(self):
        """Test active controller retrieval."""
        # Add controllers with different statuses
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.ACTIVE,
            color=(255, 0, 0)
        )
        self.manager.controllers[1] = ControllerInfo(
            controller_id=1,
            instance_id=1,
            status=ControllerStatus.CONNECTED,
            color=(0, 255, 0)
        )
        
        # Test active controllers
        active_controllers = self.manager.get_active_controllers()
        assert len(active_controllers) == 1
        assert 0 in active_controllers
    
    def test_cleanup_inactive_controllers(self):
        """Test cleanup of inactive controllers."""
        # Add a controller with old activity
        controller_info = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.ASSIGNED,
            color=(255, 0, 0),
            last_activity=time.time() - 10  # 10 seconds ago
        )
        self.manager.controllers[0] = controller_info
        self.manager.assigned_controllers[0] = 0
        
        # Cleanup inactive controllers
        self.manager.cleanup_inactive_controllers()
        
        # Check that controller was deactivated
        assert 0 not in self.manager.assigned_controllers
        assert self.manager.controllers[0].status == ControllerStatus.CONNECTED


class TestControllerSelection:
    """Test cases for ControllerSelection."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.controller_selection = ControllerSelection(controller_id=0, instance_id=0)
    
    def test_initialization(self):
        """Test controller selection initialization."""
        assert self.controller_selection.controller_id == 0
        assert self.controller_selection.instance_id == 0
        assert self.controller_selection.get_animation() == ""
        assert self.controller_selection.get_frame() == 0
        assert not self.controller_selection.is_active()
    
    def test_animation_selection(self):
        """Test animation selection."""
        self.controller_selection.set_animation("test_animation")
        
        assert self.controller_selection.get_animation() == "test_animation"
        assert len(self.controller_selection.get_navigation_history()) == 1
    
    def test_frame_selection(self):
        """Test frame selection."""
        self.controller_selection.set_frame(5)
        
        assert self.controller_selection.get_frame() == 5
    
    def test_combined_selection(self):
        """Test combined animation and frame selection."""
        self.controller_selection.set_selection("test_animation", 3)
        
        assert self.controller_selection.get_animation() == "test_animation"
        assert self.controller_selection.get_frame() == 3
    
    def test_activation_deactivation(self):
        """Test controller activation and deactivation."""
        # Test activation
        self.controller_selection.activate()
        assert self.controller_selection.is_active()
        
        # Test deactivation
        self.controller_selection.deactivate()
        assert not self.controller_selection.is_active()
    
    def test_frame_preservation(self):
        """Test frame preservation when switching animations."""
        # Set initial selection
        self.controller_selection.set_selection("animation1", 3)
        
        # Switch to new animation with frame preservation
        target_frame = self.controller_selection.preserve_frame_for_animation("animation2", 5)
        
        # Should preserve frame 3 if it's within range
        assert target_frame == 3
        
        # Test with frame out of range
        target_frame = self.controller_selection.preserve_frame_for_animation("animation3", 2)
        
        # Should clamp to available range
        assert target_frame == 1  # 2 - 1 = 1 (last available frame)
    
    def test_activity_tracking(self):
        """Test activity tracking."""
        initial_time = self.controller_selection.state.last_update_time
        
        # Update activity
        time.sleep(0.01)  # Small delay
        self.controller_selection.update_activity()
        
        # Check that time was updated
        assert self.controller_selection.state.last_update_time > initial_time
    
    def test_navigation_history(self):
        """Test navigation history tracking."""
        # Set multiple selections
        self.controller_selection.set_selection("animation1", 0)
        self.controller_selection.set_selection("animation2", 1)
        self.controller_selection.set_selection("animation3", 2)
        
        # Check history
        history = self.controller_selection.get_navigation_history()
        assert len(history) == 2  # Two transitions
        
        # Check history content
        assert history[0]['animation'] == "animation1"
        assert history[0]['frame'] == 0
        assert history[1]['animation'] == "animation2"
        assert history[1]['frame'] == 1
    
    def test_state_reset(self):
        """Test state reset."""
        # Set some state
        self.controller_selection.set_selection("test_animation", 5)
        self.controller_selection.activate()
        
        # Reset to default
        self.controller_selection.reset_to_default()
        
        # Check reset state
        assert self.controller_selection.get_animation() == ""
        assert self.controller_selection.get_frame() == 0
        assert not self.controller_selection.is_active()
        assert len(self.controller_selection.get_navigation_history()) == 0
    
    def test_state_cloning(self):
        """Test state cloning between controllers."""
        # Set up source controller
        self.controller_selection.set_selection("source_animation", 3)
        self.controller_selection.activate()
        
        # Create target controller
        target_controller = ControllerSelection(controller_id=1, instance_id=1)
        
        # Clone state
        self.controller_selection.clone_state_to(target_controller)
        
        # Check cloned state
        assert target_controller.get_animation() == "source_animation"
        assert target_controller.get_frame() == 3
        assert target_controller.is_active()


class TestVisualCollisionManager:
    """Test cases for VisualCollisionManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()
    
    def test_initialization(self):
        """Test manager initialization."""
        assert self.manager.indicators == {}
        assert self.manager.collision_groups == {}
        assert self.manager.position_cache == {}
    
    def test_add_controller_indicator(self):
        """Test adding controller indicators."""
        indicator = self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(100, 100)
        )
        
        assert indicator.controller_id == 0
        assert indicator.instance_id == 0
        assert indicator.color == (255, 0, 0)
        assert indicator.position == (100, 100)
        assert 0 in self.manager.indicators
    
    def test_remove_controller_indicator(self):
        """Test removing controller indicators."""
        # Add indicator
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Remove indicator
        self.manager.remove_controller_indicator(0)
        
        assert 0 not in self.manager.indicators
    
    def test_update_controller_position(self):
        """Test updating controller position."""
        # Add indicator
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Update position
        self.manager.update_controller_position(0, (200, 200))
        
        assert self.manager.indicators[0].position == (200, 200)
    
    def test_collision_avoidance(self):
        """Test collision avoidance for multiple indicators."""
        # Add multiple indicators at same position
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        self.manager.add_controller_indicator(1, 1, (0, 255, 0), (100, 100))
        self.manager.add_controller_indicator(2, 2, (0, 0, 255), (100, 100))
        
        # Check collision groups
        assert (100, 100) in self.manager.collision_groups
        assert len(self.manager.collision_groups[(100, 100)]) == 3
        
        # Check that offsets were applied
        for controller_id in [0, 1, 2]:
            indicator = self.manager.indicators[controller_id]
            assert indicator.offset != (0, 0)  # Should have offset applied
    
    def test_final_position_calculation(self):
        """Test final position calculation with offsets."""
        # Add indicator with offset
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        self.manager.indicators[0].offset = (10, -5)
        
        # Get final position
        final_pos = self.manager.get_final_position(0)
        
        assert final_pos == (110, 95)  # (100 + 10, 100 - 5)
    
    def test_visibility_control(self):
        """Test indicator visibility control."""
        # Add indicator
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Test visibility
        assert self.manager.indicators[0].is_visible is True
        
        # Hide indicator
        self.manager.set_indicator_visibility(0, False)
        assert self.manager.indicators[0].is_visible is False
    
    def test_color_customization(self):
        """Test indicator color customization."""
        # Add indicator
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Change color
        self.manager.set_indicator_color(0, (0, 255, 0))
        
        assert self.manager.indicators[0].color == (0, 255, 0)
    
    def test_shape_customization(self):
        """Test indicator shape customization."""
        # Add indicator
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Change shape
        self.manager.set_indicator_shape(0, IndicatorShape.CIRCLE)
        
        assert self.manager.indicators[0].shape == IndicatorShape.CIRCLE
    
    def test_size_customization(self):
        """Test indicator size customization."""
        # Add indicator
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Change size
        self.manager.set_indicator_size(0, 20)
        
        assert self.manager.indicators[0].size == 20
    
    def test_clear_all_indicators(self):
        """Test clearing all indicators."""
        # Add multiple indicators
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        self.manager.add_controller_indicator(1, 1, (0, 255, 0), (200, 200))
        
        # Clear all
        self.manager.clear_all_indicators()
        
        assert len(self.manager.indicators) == 0
        assert len(self.manager.collision_groups) == 0
        assert len(self.manager.position_cache) == 0
    
    def test_optimize_positioning(self):
        """Test positioning optimization."""
        # Add indicators with collisions
        self.manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        self.manager.add_controller_indicator(1, 1, (0, 255, 0), (100, 100))
        
        # Optimize positioning
        self.manager.optimize_positioning()
        
        # Check that positioning was recalculated
        assert (100, 100) in self.manager.collision_groups


class TestMultiControllerIntegration:
    """Integration tests for the multi-controller system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections = {}
    
    def test_full_controller_lifecycle(self):
        """Test complete controller lifecycle from connection to deactivation."""
        # Simulate controller connection
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.CONNECTED,
            color=(255, 0, 0)
        )
        
        # Assign controller
        controller_id = self.manager.assign_controller(0)
        assert controller_id == 0
        
        # Create controller selection
        self.controller_selections[0] = ControllerSelection(0, 0)
        self.controller_selections[0].activate()
        self.controller_selections[0].set_selection("test_animation", 0)
        
        # Add visual indicator
        self.visual_manager.add_controller_indicator(0, 0, (255, 0, 0), (100, 100))
        
        # Verify state
        assert self.manager.is_controller_active(0)
        assert self.controller_selections[0].is_active()
        assert 0 in self.visual_manager.indicators
        
        # Deactivate controller
        self.controller_selections[0].deactivate()
        self.visual_manager.remove_controller_indicator(0)
        
        # Verify deactivation
        assert not self.controller_selections[0].is_active()
        assert 0 not in self.visual_manager.indicators
    
    def test_multiple_controller_collision_avoidance(self):
        """Test collision avoidance with multiple controllers."""
        # Add multiple controllers at same position
        for i in range(4):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=self.manager.CONTROLLER_COLORS[i],
                position=(100, 100)
            )
        
        # Check collision groups
        assert (100, 100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100, 100)]) == 4
        
        # Check that all indicators have offsets
        for i in range(4):
            indicator = self.visual_manager.indicators[i]
            assert indicator.offset != (0, 0)
    
    def test_controller_state_preservation(self):
        """Test controller state preservation across operations."""
        # Create controller selection
        controller_selection = ControllerSelection(0, 0)
        controller_selection.activate()
        controller_selection.set_selection("animation1", 3)
        
        # Simulate navigation
        controller_selection.set_selection("animation2", 1)
        controller_selection.set_selection("animation3", 5)
        
        # Check navigation history
        history = controller_selection.get_navigation_history()
        assert len(history) == 2
        assert history[0]['animation'] == "animation1"
        assert history[0]['frame'] == 3
        assert history[1]['animation'] == "animation2"
        assert history[1]['frame'] == 1
        
        # Test frame preservation
        target_frame = controller_selection.preserve_frame_for_animation("animation1", 2)
        assert target_frame == 1  # Clamped to available range


if __name__ == "__main__":
    pytest.main([__file__])
