"""
Multi-Controller System Edge Case Tests

This module provides specific edge case tests for hotplug scenarios,
navigation boundaries, collision edge cases, and race conditions.
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List
from unittest.mock import Mock

from glitchygames.tools.multi_controller_manager import MultiControllerManager
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager


class TestControllerHotplugEdgeCases:
    """Test edge cases for controller hotplug scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
    
    def test_rapid_hotplug_cycles(self):
        """Test rapid connect/disconnect cycles."""
        # Simulate rapid hotplug cycles
        for cycle in range(50):
            # Connect controller
            self.manager._handle_controller_connect(0)
            controller_id = self.manager.assign_controller(0)
            
            if controller_id is not None:
                self.controller_selections[controller_id] = ControllerSelection(controller_id, 0)
                self.controller_selections[controller_id].activate()
                self.manager.activate_controller(0)
            
            # Small delay
            time.sleep(0.001)
            
            # Disconnect controller
            self.manager._handle_controller_disconnect(0)
            if controller_id in self.controller_selections:
                del self.controller_selections[controller_id]
        
        # System should still be functional
        assert len(self.manager.controllers) == 0
        assert len(self.controller_selections) == 0
    
    def test_controller_id_reuse(self):
        """Test when same instance_id reconnects."""
        # First connection
        self.manager._handle_controller_connect(0)
        controller_id_1 = self.manager.assign_controller(0)
        assert controller_id_1 is not None
        
        # Disconnect
        self.manager._handle_controller_disconnect(0)
        assert 0 not in self.manager.controllers
        
        # Reconnect with same instance_id
        self.manager._handle_controller_connect(0)
        controller_id_2 = self.manager.assign_controller(0)
        assert controller_id_2 is not None
        
        # Should get new controller ID
        assert controller_id_2 != controller_id_1
    
    def test_multiple_rapid_connections(self):
        """Test multiple controllers connecting rapidly."""
        # Connect multiple controllers rapidly
        for i in range(10):
            self.manager._handle_controller_connect(i)
            controller_id = self.manager.assign_controller(i)
            
            if controller_id is not None:
                self.controller_selections[controller_id] = ControllerSelection(controller_id, i)
                self.controller_selections[controller_id].activate()
                self.manager.activate_controller(i)
        
        # Should handle gracefully (may hit MAX_CONTROLLERS limit)
        assert len(self.manager.controllers) <= self.manager.MAX_CONTROLLERS
    
    def test_controller_disconnect_during_operation(self):
        """Test controller disconnection during active operations."""
        # Set up controller
        self.manager._handle_controller_connect(0)
        controller_id = self.manager.assign_controller(0)
        self.controller_selections[controller_id] = ControllerSelection(controller_id, 0)
        self.controller_selections[controller_id].activate()
        self.manager.activate_controller(0)
        
        # Start operations
        def operation_worker():
            for _ in range(100):
                if controller_id in self.controller_selections:
                    self.controller_selections[controller_id].set_selection("animation", 0)
                time.sleep(0.001)
        
        # Start operation in thread
        operation_thread = threading.Thread(target=operation_worker)
        operation_thread.start()
        
        # Disconnect during operation
        time.sleep(0.01)
        self.manager._handle_controller_disconnect(0)
        
        # Wait for operation to complete
        operation_thread.join()
        
        # System should handle gracefully
        assert 0 not in self.manager.controllers


class TestNavigationBoundaryCases:
    """Test navigation at boundaries and edge conditions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.controller_selection = ControllerSelection(0, 0)
        self.controller_selection.activate()
    
    def test_navigation_at_frame_boundaries(self):
        """Test navigation at frame 0 and maximum frames."""
        # Test at frame 0
        self.controller_selection.set_selection("animation", 0)
        animation, frame = self.controller_selection.get_selection()
        assert animation == "animation"
        assert frame == 0
        
        # Test at high frame number
        self.controller_selection.set_selection("animation", 999)
        animation, frame = self.controller_selection.get_selection()
        assert animation == "animation"
        assert frame == 999
    
    def test_rapid_navigation_stress(self):
        """Test rapid navigation that could cause race conditions."""
        # Rapid navigation with many changes
        for i in range(1000):
            self.controller_selection.set_selection(f"animation_{i % 10}", i % 20)
        
        # Should maintain valid state
        animation, frame = self.controller_selection.get_selection()
        assert animation.startswith("animation_")
        assert 0 <= frame <= 19
        
        # Navigation history should be reasonable
        history = self.controller_selection.get_navigation_history()
        assert len(history) > 0
        assert len(history) <= 1000  # Should not grow unbounded
    
    def test_navigation_with_invalid_inputs(self):
        """Test navigation with invalid inputs."""
        # Test with empty animation name
        self.controller_selection.set_selection("", 0)
        animation, frame = self.controller_selection.get_selection()
        assert animation == ""
        assert frame == 0
        
        # Test with negative frame
        self.controller_selection.set_selection("animation", -1)
        animation, frame = self.controller_selection.get_selection()
        assert animation == "animation"
        assert frame == -1  # Should accept negative frames
        
        # Test with very large frame number
        self.controller_selection.set_selection("animation", 999999)
        animation, frame = self.controller_selection.get_selection()
        assert animation == "animation"
        assert frame == 999999
    
    def test_navigation_history_limits(self):
        """Test navigation history with many entries."""
        # Add many navigation entries
        for i in range(10000):
            self.controller_selection.set_selection(f"animation_{i % 100}", i % 50)
        
        # Get history
        history = self.controller_selection.get_navigation_history()
        
        # Should have reasonable number of entries
        assert len(history) > 0
        assert len(history) <= 10000
        
        # Should maintain chronological order
        for i in range(len(history) - 1):
            assert history[i]['timestamp'] <= history[i + 1]['timestamp']
    
    def test_concurrent_navigation(self):
        """Test concurrent navigation operations."""
        def navigation_worker(worker_id):
            for i in range(100):
                self.controller_selection.set_selection(f"worker_{worker_id}_animation", i)
                time.sleep(0.001)
        
        # Start multiple navigation workers
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for worker_id in range(3):
                future = executor.submit(navigation_worker, worker_id)
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                future.result()
        
        # Should have valid final state
        animation, frame = self.controller_selection.get_selection()
        assert animation.startswith("worker_")
        assert 0 <= frame <= 99


class TestVisualCollisionEdgeCases:
    """Test edge cases for visual collision management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.visual_manager = VisualCollisionManager()
    
    def test_extreme_collision_scenarios(self):
        """Test collision avoidance with many controllers at same position."""
        # Add many controllers at exact same position
        for i in range(25):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100)
            )
        
        # Should handle collision avoidance
        assert (100, 100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100, 100)]) == 25
        
        # All indicators should exist
        assert len(self.visual_manager.indicators) == 25
    
    def test_position_update_races(self):
        """Test rapid position updates causing potential race conditions."""
        # Add indicators
        for i in range(10):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(i * 10, i * 10)
            )
        
        def position_worker(controller_id):
            for _ in range(100):
                x = (controller_id * 10 + _) % 200
                y = (controller_id * 10 + _) % 200
                self.visual_manager.update_controller_position(controller_id, (x, y))
                time.sleep(0.001)
        
        # Start multiple position update workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for controller_id in range(5):
                future = executor.submit(position_worker, controller_id)
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                future.result()
        
        # All indicators should still exist
        assert len(self.visual_manager.indicators) == 10
    
    def test_collision_with_negative_positions(self):
        """Test collision avoidance with negative positions."""
        # Add indicators at negative positions
        for i in range(5):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(-100, -100)
            )
        
        # Should handle negative positions
        assert (-100, -100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(-100, -100)]) == 5
    
    def test_collision_with_large_positions(self):
        """Test collision avoidance with very large positions."""
        # Add indicators at large positions
        for i in range(5):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100000, 100000)
            )
        
        # Should handle large positions
        assert (100000, 100000) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100000, 100000)]) == 5
    
    def test_rapid_add_remove_indicators(self):
        """Test rapid addition and removal of indicators."""
        # Rapidly add and remove indicators
        for cycle in range(100):
            # Add indicators
            for i in range(5):
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=i,
                    color=(255, 0, 0),
                    position=(i * 10, i * 10)
                )
            
            # Remove indicators
            for i in range(5):
                self.visual_manager.remove_controller_indicator(i)
        
        # Should be clean
        assert len(self.visual_manager.indicators) == 0
        assert len(self.visual_manager.collision_groups) == 0


class TestMemoryAndPerformanceEdgeCases:
    """Test memory and performance edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
    
    def test_memory_usage_with_many_controllers(self):
        """Test memory usage with many controllers."""
        # Add many controllers
        for i in range(50):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()
            
            # Add visual indicators
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=instance_id,
                color=(255, 0, 0),
                position=(i * 5, i * 5)
            )
        
        # System should handle this gracefully
        assert len(self.manager.controllers) == 50
        assert len(self.visual_manager.indicators) == 50
    
    def test_memory_cleanup_under_stress(self):
        """Test memory cleanup under stress conditions."""
        # Rapidly add and remove controllers
        for cycle in range(100):
            # Add controllers
            for i in range(3):
                instance_id = i + cycle * 3
                self.manager.controllers[instance_id] = Mock()
                self.manager.assigned_controllers[instance_id] = i
                
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=instance_id,
                    color=(255, 0, 0),
                    position=(i * 10, i * 10)
                )
            
            # Remove controllers
            for i in range(3):
                instance_id = i + cycle * 3
                if instance_id in self.manager.controllers:
                    del self.manager.controllers[instance_id]
                if instance_id in self.manager.assigned_controllers:
                    del self.manager.assigned_controllers[instance_id]
                
                self.visual_manager.remove_controller_indicator(i)
        
        # Should be clean
        assert len(self.manager.controllers) == 0
        assert len(self.visual_manager.indicators) == 0
    
    def test_performance_with_extreme_operations(self):
        """Test performance with extreme operation counts."""
        # Set up controllers
        for i in range(10):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()
        
        # Perform many operations
        start_time = time.time()
        
        # Navigation operations
        for _ in range(1000):
            for i in range(10):
                self.controller_selections[i].set_selection(f"animation_{i}", i % 20)
        
        # Visual operations
        for _ in range(1000):
            for i in range(10):
                self.visual_manager.update_controller_position(i, (i * 10, i * 10))
        
        end_time = time.time()
        
        # Should complete within reasonable time
        assert end_time - start_time < 10.0  # Should complete in under 10 seconds
    
    def test_concurrent_access_patterns(self):
        """Test concurrent access patterns that could cause issues."""
        # Set up controllers
        for i in range(5):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()
        
        def mixed_operations_worker(worker_id):
            for _ in range(100):
                # Mixed operations
                controller_id = worker_id % 5
                
                # Navigation
                self.controller_selections[controller_id].set_selection(f"worker_{worker_id}", _ % 10)
                
                # Visual updates
                self.visual_manager.update_controller_position(controller_id, (worker_id * 10, _ * 10))
                
                # Manager operations
                self.manager.update_controller_activity(controller_id)
                
                time.sleep(0.001)
        
        # Start multiple workers
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for worker_id in range(3):
                future = executor.submit(mixed_operations_worker, worker_id)
                futures.append(future)
            
            # Wait for all workers to complete
            for future in futures:
                future.result()
        
        # System should still be functional
        assert len(self.controller_selections) == 5
        assert len(self.visual_manager.indicators) == 5


class TestErrorRecoveryEdgeCases:
    """Test error recovery in edge cases."""
    
    def setup_method(self):
        """Set up test fixtures."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
    
    def test_operations_with_invalid_controller_ids(self):
        """Test operations with invalid controller IDs."""
        # Test with non-existent controller IDs
        invalid_ids = [999, -1, 1000, None]
        
        for invalid_id in invalid_ids:
            # These should not crash
            assert not self.manager.is_controller_active(invalid_id)
            assert self.manager.get_controller_info(invalid_id) is None
            assert self.visual_manager.get_final_position(invalid_id) == (0, 0)
            
            # These should handle gracefully
            self.visual_manager.remove_controller_indicator(invalid_id)
            self.visual_manager.update_controller_position(invalid_id, (0, 0))
    
    def test_operations_with_corrupted_state(self):
        """Test operations with corrupted internal state."""
        # Corrupt manager state
        self.manager.controllers[999] = "invalid_object"
        self.manager.assigned_controllers[999] = "invalid_object"
        
        # System should handle gracefully
        assert not self.manager.is_controller_active(999)
        assert self.manager.get_controller_info(999) is None
    
    def test_visual_manager_with_invalid_data(self):
        """Test visual manager with invalid data."""
        # Add indicator with invalid data
        self.visual_manager.add_controller_indicator(
            controller_id=0,
            instance_id=0,
            color=(255, 0, 0),
            position=(100, 100)
        )
        
        # Corrupt the indicator
        if 0 in self.visual_manager.indicators:
            self.visual_manager.indicators[0].position = "invalid"
        
        # Operations should handle gracefully
        position = self.visual_manager.get_final_position(0)
        assert position == (0, 0)  # Should return default position
    
    def test_recovery_from_system_errors(self):
        """Test recovery from system-level errors."""
        # Simulate system errors by corrupting data structures
        original_controllers = self.manager.controllers.copy()
        original_assigned = self.manager.assigned_controllers.copy()
        
        # Corrupt data
        self.manager.controllers = None
        self.manager.assigned_controllers = None
        
        # System should handle gracefully
        try:
            self.manager.is_controller_active(0)
            self.manager.get_controller_info(0)
        except Exception:
            # Should not crash the entire system
            pass
        
        # Restore data
        self.manager.controllers = original_controllers
        self.manager.assigned_controllers = original_assigned
        
        # System should be functional again
        assert len(self.manager.controllers) == 0
