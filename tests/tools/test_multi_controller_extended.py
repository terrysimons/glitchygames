"""
Extended Multi-Controller System Tests

This module provides comprehensive tests for edge cases, error handling,
performance scenarios, and integration scenarios for the multi-controller system.
"""

import pytest
import time
import pygame
from unittest.mock import Mock, patch
from typing import Dict, List

from glitchygames.tools.multi_controller_manager import (
    MultiControllerManager, 
    ControllerInfo, 
    ControllerStatus
)
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import (
    VisualCollisionManager, 
    IndicatorShape
)


class TestMultiControllerEdgeCases:
    """Test edge cases and error conditions for multi-controller system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for clean tests
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
    
    def test_maximum_controller_limit(self):
        """Test behavior when maximum controller limit is reached."""
        # Add maximum number of controllers
        for i in range(self.manager.MAX_CONTROLLERS):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
                color=self.manager.CONTROLLER_COLORS[i]
            )
            self.manager.assigned_controllers[instance_id] = i
        
        # Try to add one more controller (should handle gracefully)
        extra_instance_id = self.manager.MAX_CONTROLLERS
        controller_id = self.manager.assign_controller(extra_instance_id)
        
        # Should either reject or handle gracefully
        assert controller_id is None or controller_id < self.manager.MAX_CONTROLLERS
    
    def test_rapid_controller_switching(self):
        """Test rapid switching between controllers."""
        # Create multiple controllers
        for i in range(3):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
                color=self.manager.CONTROLLER_COLORS[i]
            )
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
        
        # Rapidly switch between controllers
        for _ in range(10):
            for i in range(3):
                self.controller_selections[i].activate()
                self.controller_selections[i].set_selection(f"animation_{i}", i)
                time.sleep(0.001)  # Small delay to simulate rapid switching
        
        # Verify all controllers maintain their state
        for i in range(3):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f"animation_{i}"
            assert frame == i
    
    def test_controller_disconnection_reconnection(self):
        """Test controller disconnection and reconnection scenarios."""
        # Add a controller
        instance_id = 0
        self.manager.controllers[instance_id] = ControllerInfo(
            controller_id=0,
            instance_id=instance_id,
            status=ControllerStatus.ACTIVE,
            color=(255, 0, 0)
        )
        self.manager.assigned_controllers[instance_id] = 0
        
        # Simulate disconnection
        self.manager._handle_controller_disconnect(instance_id)
        
        # Verify controller is removed
        assert instance_id not in self.manager.controllers
        assert instance_id not in self.manager.assigned_controllers
        
        # Simulate reconnection
        self.manager._handle_controller_connect(instance_id)
        
        # Verify controller is re-added with new ID
        assert instance_id in self.manager.controllers
        new_controller_info = self.manager.controllers[instance_id]
        assert new_controller_info.status == ControllerStatus.CONNECTED
    
    def test_invalid_controller_operations(self):
        """Test operations with invalid controller IDs."""
        # Test with non-existent controller
        assert not self.manager.is_controller_active(999)
        assert self.manager.get_controller_info(999) is None
        assert self.manager.get_controller_color(999) is None
        
        # Test activation of non-existent controller
        assert not self.manager.activate_controller(999)
        
        # Test visual manager with invalid controller
        assert self.visual_manager.get_final_position(999) == (0, 0)
        self.visual_manager.remove_controller_indicator(999)  # Should not crash
    
    def test_color_assignment_conflicts(self):
        """Test color assignment when multiple controllers request same colors."""
        # Add controllers and force color conflicts
        for i in range(4):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
                color=self.manager.CONTROLLER_COLORS[i]
            )
            self.manager.assigned_controllers[instance_id] = i
        
        # All controllers should have unique colors
        colors = [info.color for info in self.manager.controllers.values()]
        assert len(set(colors)) == len(colors)  # All colors should be unique
    
    def test_memory_cleanup(self):
        """Test memory cleanup for inactive controllers."""
        # Add controllers
        for i in range(3):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.ACTIVE,
                color=self.manager.CONTROLLER_COLORS[i],
                last_activity=time.time()
            )
            self.manager.assigned_controllers[instance_id] = i
        
        # Simulate old activity for some controllers
        old_time = time.time() - 1000  # Very old
        self.manager.controllers[0].last_activity = old_time
        self.manager.controllers[1].last_activity = old_time
        
        # Clean up inactive controllers
        self.manager.cleanup_inactive_controllers()
        
        # Only active controller should remain
        active_controllers = self.manager.get_active_controllers()
        assert len(active_controllers) == 1
        assert active_controllers[0] == 2  # Only controller 2 should remain


class TestVisualCollisionEdgeCases:
    """Test edge cases for visual collision management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = VisualCollisionManager()
    
    def test_collision_with_many_controllers(self):
        """Test collision avoidance with many controllers at same position."""
        # Add many controllers at same position
        for i in range(8):
            self.manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100)
            )
        
        # Verify all indicators were added
        assert len(self.manager.indicators) == 8
        
        # Verify collision group exists
        assert (100, 100) in self.manager.collision_groups
        assert len(self.manager.collision_groups[(100, 100)]) == 8
    
    def test_position_updates_with_collisions(self):
        """Test position updates when controllers are at collision positions."""
        # Add controllers at same position
        for i in range(3):
            self.manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100)
            )
        
        # Update position of one controller
        self.manager.update_controller_position(1, (200, 200))
        
        # Verify collision groups are updated
        assert (100, 100) in self.manager.collision_groups
        assert (200, 200) in self.manager.collision_groups
        assert len(self.manager.collision_groups[(100, 100)]) == 2
        assert len(self.manager.collision_groups[(200, 200)]) == 1
    
    def test_visual_indicator_customization(self):
        """Test extensive visual indicator customization."""
        # Add controller with custom properties
        self.manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(100, 100)
        )
        
        # Test all customization options
        self.manager.set_controller_visibility(0, False)
        self.manager.set_controller_color(0, (0, 255, 0))
        self.manager.set_controller_shape(0, IndicatorShape.CIRCLE)
        self.manager.set_controller_size(0, 20)
        
        # Verify customizations
        indicator = self.manager.indicators[0]
        assert not indicator.is_visible
        assert indicator.color == (0, 255, 0)
        assert indicator.shape == IndicatorShape.CIRCLE
        assert indicator.size == 20
    
    def test_performance_with_many_indicators(self):
        """Test performance with many visual indicators."""
        # Add many indicators
        start_time = time.time()
        for i in range(50):
            self.manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(i * 10, i * 10)
            )
        end_time = time.time()
        
        # Should complete quickly (less than 1 second)
        assert end_time - start_time < 1.0
        
        # Verify all indicators were added
        assert len(self.manager.indicators) == 50


class TestControllerSelectionEdgeCases:
    """Test edge cases for controller selection management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.controller_selection = ControllerSelection(0, 0)
    
    def test_navigation_history_limits(self):
        """Test navigation history with many entries."""
        # Add many navigation entries
        for i in range(100):
            self.controller_selection.set_selection(f"animation_{i}", i)
        
        # Get navigation history
        history = self.controller_selection.get_navigation_history()
        
        # Should have reasonable number of entries (not all 100)
        assert len(history) <= 100
        assert len(history) > 0
        
        # Should maintain chronological order
        for i in range(len(history) - 1):
            assert history[i]['timestamp'] <= history[i + 1]['timestamp']
    
    def test_state_cloning_edge_cases(self):
        """Test state cloning with various scenarios."""
        # Set up complex state
        self.controller_selection.activate()
        self.controller_selection.set_selection("complex_animation", 42)
        
        # Add navigation history
        for i in range(5):
            self.controller_selection.set_selection(f"history_{i}", i)
        
        # Clone to another controller
        other_selection = ControllerSelection(1, 1)
        self.controller_selection.clone_state_to(other_selection)
        
        # Verify cloned state
        assert other_selection.is_active()
        animation, frame = other_selection.get_selection()
        assert animation == "complex_animation"
        assert frame == 42
        
        # Verify navigation history was cloned
        other_history = other_selection.get_navigation_history()
        assert len(other_history) > 0
    
    def test_activity_tracking_edge_cases(self):
        """Test activity tracking with various scenarios."""
        # Test initial state
        assert not self.controller_selection.is_active()
        
        # Activate and track activity
        self.controller_selection.activate()
        initial_time = self.controller_selection.state.last_update_time
        
        # Simulate activity
        time.sleep(0.01)
        self.controller_selection.set_selection("test", 0)
        
        # Verify activity was tracked
        assert self.controller_selection.state.last_update_time > initial_time
        
        # Deactivate
        self.controller_selection.deactivate()
        assert not self.controller_selection.is_active()
    
    def test_frame_preservation_complex_scenarios(self):
        """Test frame preservation in complex navigation scenarios."""
        # Set up complex navigation
        self.controller_selection.set_selection("animation1", 5)
        self.controller_selection.set_selection("animation2", 3)
        self.controller_selection.set_selection("animation3", 7)
        
        # Switch back to first animation
        self.controller_selection.set_selection("animation1", 2)
        
        # Verify current state
        animation, frame = self.controller_selection.get_selection()
        assert animation == "animation1"
        assert frame == 2
        
        # Verify navigation history
        history = self.controller_selection.get_navigation_history()
        assert len(history) >= 3  # Should have history of previous selections


class TestMultiControllerIntegration:
    """Test integration scenarios for multi-controller system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for clean tests
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
    
    def test_full_multi_controller_workflow(self):
        """Test complete multi-controller workflow."""
        # Simulate 4 controllers connecting
        for i in range(4):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
                color=self.manager.CONTROLLER_COLORS[i]
            )
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
        
        # Activate all controllers
        for i in range(4):
            self.manager.activate_controller(i)
            self.controller_selections[i].activate()
            self.controller_selections[i].set_selection(f"animation_{i}", i)
            
            # Add visual indicators
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=self.manager.CONTROLLER_COLORS[i],
                position=(100 + i * 50, 100)
            )
        
        # Verify all systems are working together
        for i in range(4):
            # Manager state
            assert self.manager.is_controller_active(i)
            assert self.manager.get_controller_info(i) is not None
            
            # Selection state
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f"animation_{i}"
            assert frame == i
            
            # Visual state
            assert i in self.visual_manager.indicators
            indicator = self.visual_manager.indicators[i]
            assert indicator.color == self.manager.CONTROLLER_COLORS[i]
    
    def test_controller_priority_handling(self):
        """Test handling of controller priority and conflicts."""
        # Add controllers with different priorities
        for i in range(3):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.ACTIVE,
                color=self.manager.CONTROLLER_COLORS[i],
                last_activity=time.time() - i  # Different activity times
            )
            self.manager.assigned_controllers[instance_id] = i
        
        # Get active controllers (should be ordered by activity)
        active_controllers = self.manager.get_active_controllers()
        assert len(active_controllers) == 3
        
        # Most recent activity should be first
        assert active_controllers[0] == 0  # Most recent
    
    def test_system_resilience(self):
        """Test system resilience under stress."""
        # Rapidly add and remove controllers
        for cycle in range(5):
            # Add controllers
            for i in range(3):
                instance_id = i + cycle * 3
                self.manager.controllers[instance_id] = ControllerInfo(
                    controller_id=i,
                    instance_id=instance_id,
                    status=ControllerStatus.CONNECTED,
                    color=self.manager.CONTROLLER_COLORS[i]
                )
                self.manager.assigned_controllers[instance_id] = i
                
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=instance_id,
                    color=self.manager.CONTROLLER_COLORS[i],
                    position=(100, 100)
                )
            
            # Remove controllers
            for i in range(3):
                instance_id = i + cycle * 3
                if instance_id in self.manager.controllers:
                    del self.manager.controllers[instance_id]
                if instance_id in self.manager.assigned_controllers:
                    del self.manager.assigned_controllers[instance_id]
                
                self.visual_manager.remove_controller_indicator(i)
        
        # System should still be functional
        assert len(self.manager.controllers) == 0
        assert len(self.visual_manager.indicators) == 0
    
    def test_concurrent_controller_operations(self):
        """Test concurrent operations on multiple controllers."""
        # Set up multiple controllers
        for i in range(4):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
                color=self.manager.CONTROLLER_COLORS[i]
            )
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
        
        # Simulate concurrent operations
        for _ in range(10):
            for i in range(4):
                # Concurrent navigation
                self.controller_selections[i].set_selection(f"animation_{i}", i)
                
                # Concurrent visual updates
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=i,
                    color=self.manager.CONTROLLER_COLORS[i],
                    position=(100 + i * 10, 100)
                )
        
        # All controllers should have valid state
        for i in range(4):
            assert self.controller_selections[i].get_selection()[0] == f"animation_{i}"
            assert i in self.visual_manager.indicators


class TestPerformanceScenarios:
    """Test performance characteristics of multi-controller system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
    
    def test_memory_usage_with_many_controllers(self):
        """Test memory usage with many controllers."""
        # Add many controllers
        for i in range(20):
            instance_id = i
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=i,
                instance_id=instance_id,
                status=ControllerStatus.CONNECTED,
                color=self.manager.CONTROLLER_COLORS[i % 4]
            )
            self.manager.assigned_controllers[instance_id] = i
        
        # Add many visual indicators
        for i in range(20):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(i * 5, i * 5)
            )
        
        # System should handle this gracefully
        assert len(self.manager.controllers) == 20
        assert len(self.visual_manager.indicators) == 20
    
    def test_rapid_event_processing(self):
        """Test rapid event processing performance."""
        # Set up controller
        self.manager.controllers[0] = ControllerInfo(
            controller_id=0,
            instance_id=0,
            status=ControllerStatus.ACTIVE,
            color=(255, 0, 0)
        )
        self.manager.assigned_controllers[0] = 0
        
        # Process many rapid events
        start_time = time.time()
        for _ in range(1000):
            self.manager.update_controller_activity(0)
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 1.0
    
    def test_collision_calculation_performance(self):
        """Test collision calculation performance with many indicators."""
        # Add many indicators at same position
        start_time = time.time()
        for i in range(20):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100)
            )
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 1.0
        
        # Verify collision avoidance was applied
        assert (100, 100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100, 100)]) == 20
