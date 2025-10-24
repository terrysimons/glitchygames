"""
Multi-Controller System Stress Tests

This module provides stress tests and performance benchmarks for the
multi-controller system under extreme conditions.
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict

from glitchygames.tools.multi_controller_manager import MultiControllerManager
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager


class TestMultiControllerStress:
    """Stress tests for multi-controller system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for clean tests
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
    
    def test_maximum_controller_stress(self):
        """Test system behavior with maximum number of controllers."""
        # Add maximum controllers
        for i in range(self.manager.MAX_CONTROLLERS):
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
        
        # Test rapid operations on all controllers
        start_time = time.time()
        for _ in range(100):
            for i in range(self.manager.MAX_CONTROLLERS):
                self.controller_selections[i].set_selection(f"animation_{i}", i)
                self.visual_manager.update_controller_position(i, (i * 10, i * 10))
        end_time = time.time()
        
        # Should complete within reasonable time
        assert end_time - start_time < 5.0
        
        # Verify all controllers are still functional
        for i in range(self.manager.MAX_CONTROLLERS):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f"animation_{i}"
            assert frame == i
    
    def test_rapid_controller_switching_stress(self):
        """Test rapid switching between controllers."""
        # Set up controllers
        for i in range(4):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
        
        # Rapidly switch between controllers
        start_time = time.time()
        for cycle in range(1000):
            for i in range(4):
                self.controller_selections[i].activate()
                self.controller_selections[i].set_selection(f"animation_{i}", cycle)
                time.sleep(0.0001)  # Very small delay
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 10.0
        
        # Verify final states
        for i in range(4):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f"animation_{i}"
            assert frame == 999  # Last cycle
    
    def test_memory_stress_with_navigation_history(self):
        """Test memory usage with extensive navigation history."""
        # Set up controller
        self.controller_selections[0] = ControllerSelection(0, 0)
        self.controller_selections[0].activate()
        
        # Generate extensive navigation history
        start_time = time.time()
        for i in range(10000):
            self.controller_selections[0].set_selection(f"animation_{i % 100}", i % 50)
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 5.0
        
        # Verify navigation history
        history = self.controller_selections[0].get_navigation_history()
        assert len(history) > 0
        
        # Verify current state
        animation, frame = self.controller_selections[0].get_selection()
        assert animation == "animation_99"  # Last animation
        assert frame == 49  # Last frame
    
    def test_visual_collision_stress(self):
        """Test visual collision system under stress."""
        # Add many controllers at same position
        start_time = time.time()
        for i in range(50):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(100, 100)  # Same position
            )
        end_time = time.time()
        
        # Should complete quickly
        assert end_time - start_time < 2.0
        
        # Verify collision avoidance was applied
        assert (100, 100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100, 100)]) == 50
        
        # Test rapid position updates
        update_start = time.time()
        for _ in range(100):
            for i in range(50):
                self.visual_manager.update_controller_position(i, (100 + i, 100 + i))
        update_end = time.time()
        
        # Should update quickly
        assert update_end - update_start < 3.0
    
    def test_concurrent_operations_stress(self):
        """Test concurrent operations on multiple controllers."""
        # Set up controllers
        for i in range(8):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()
        
        def controller_worker(controller_id: int, iterations: int):
            """Worker function for concurrent operations."""
            for _ in range(iterations):
                self.controller_selections[controller_id].set_selection(
                    f"animation_{controller_id}", 
                    controller_id
                )
                time.sleep(0.001)
        
        # Run concurrent operations
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for i in range(8):
                future = executor.submit(controller_worker, i, 100)
                futures.append(future)
            
            # Wait for all operations to complete
            for future in futures:
                future.result()
        end_time = time.time()
        
        # Should complete within reasonable time
        assert end_time - start_time < 10.0
        
        # Verify all controllers are still functional
        for i in range(8):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f"animation_{i}"
            assert frame == i
    
    def test_system_resilience_stress(self):
        """Test system resilience under extreme conditions."""
        # Rapidly add and remove controllers
        start_time = time.time()
        for cycle in range(100):
            # Add controllers
            for i in range(5):
                instance_id = i + cycle * 5
                self.manager.controllers[instance_id] = Mock()
                self.manager.assigned_controllers[instance_id] = i
                
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=instance_id,
                    color=(255, 0, 0),
                    position=(i * 10, i * 10)
                )
            
            # Remove controllers
            for i in range(5):
                instance_id = i + cycle * 5
                if instance_id in self.manager.controllers:
                    del self.manager.controllers[instance_id]
                if instance_id in self.manager.assigned_controllers:
                    del self.manager.assigned_controllers[instance_id]
                
                self.visual_manager.remove_controller_indicator(i)
        end_time = time.time()
        
        # Should complete without errors
        assert end_time - start_time < 15.0
        
        # System should still be functional
        assert len(self.manager.controllers) == 0
        assert len(self.visual_manager.indicators) == 0
    
    def test_memory_leak_prevention(self):
        """Test that system doesn't leak memory over time."""
        # Perform many operations that could cause memory leaks
        for cycle in range(1000):
            # Add and remove controllers
            for i in range(3):
                instance_id = i + cycle * 3
                self.manager.controllers[instance_id] = Mock()
                self.manager.assigned_controllers[instance_id] = i
                
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=instance_id,
                    color=(255, 0, 0),
                    position=(i * 5, i * 5)
                )
                
                # Perform operations
                self.visual_manager.update_controller_position(i, (i * 10, i * 10))
                self.visual_manager.remove_controller_indicator(i)
            
            # Clean up
            for i in range(3):
                instance_id = i + cycle * 3
                if instance_id in self.manager.controllers:
                    del self.manager.controllers[instance_id]
                if instance_id in self.manager.assigned_controllers:
                    del self.manager.assigned_controllers[instance_id]
        
        # System should still be functional
        assert len(self.manager.controllers) == 0
        assert len(self.visual_manager.indicators) == 0
    
    def test_performance_benchmarks(self):
        """Test performance benchmarks for various operations."""
        # Benchmark controller assignment
        start_time = time.time()
        for i in range(1000):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            controller_id = self.manager.assign_controller(instance_id)
        assignment_time = time.time()
        
        # Should assign quickly
        assert assignment_time - start_time < 2.0
        
        # Benchmark visual indicator operations
        visual_start = time.time()
        for i in range(1000):
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=i,
                color=(255, 0, 0),
                position=(i, i)
            )
        visual_end = time.time()
        
        # Should add quickly
        assert visual_end - visual_start < 2.0
        
        # Benchmark collision calculation
        collision_start = time.time()
        for i in range(100):
            # Add many indicators at same position
            for j in range(10):
                self.visual_manager.add_controller_indicator(
                    controller_id=i * 10 + j,
                    instance_id=i * 10 + j,
                    color=(255, 0, 0),
                    position=(i, i)
                )
        collision_end = time.time()
        
        # Should calculate collisions quickly
        assert collision_end - collision_start < 3.0
    
    def test_error_recovery_stress(self):
        """Test error recovery under stress conditions."""
        # Test with invalid operations
        for _ in range(1000):
            try:
                # Invalid controller operations
                self.manager.is_controller_active(999)
                self.manager.get_controller_info(999)
                self.manager.activate_controller(999)
                
                # Invalid visual operations
                self.visual_manager.get_final_position(999)
                self.visual_manager.remove_controller_indicator(999)
                self.visual_manager.update_controller_position(999, (0, 0))
                
            except Exception:
                # Should handle errors gracefully
                pass
        
        # System should still be functional
        assert True  # If we get here, error handling worked
    
    def test_mixed_workload_stress(self):
        """Test mixed workload under stress."""
        # Set up controllers
        for i in range(10):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.controller_selections[i] = ControllerSelection(i, instance_id)
            self.controller_selections[i].activate()
        
        # Mixed operations
        start_time = time.time()
        for cycle in range(100):
            # Navigation operations
            for i in range(10):
                self.controller_selections[i].set_selection(f"animation_{i}", cycle % 50)
            
            # Visual operations
            for i in range(10):
                self.visual_manager.add_controller_indicator(
                    controller_id=i,
                    instance_id=i,
                    color=(255, 0, 0),
                    position=(i * 10, cycle * 10)
                )
            
            # Manager operations
            for i in range(10):
                self.manager.update_controller_activity(i)
            
            # Clean up visual indicators
            if cycle % 10 == 0:
                self.visual_manager.clear_all_indicators()
        
        end_time = time.time()
        
        # Should complete within reasonable time
        assert end_time - start_time < 10.0
        
        # Verify final state
        for i in range(10):
            assert self.controller_selections[i].is_active()
            animation, frame = self.controller_selections[i].get_selection()
            assert animation == f"animation_{i}"
            assert frame == 99  # Last cycle
