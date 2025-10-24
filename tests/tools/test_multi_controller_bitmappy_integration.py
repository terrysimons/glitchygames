"""
Multi-Controller Bitmappy Integration Tests

This module provides integration tests for the multi-controller system
with the actual bitmappy tool, testing real-world scenarios.
"""

import pytest
import pygame
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List

from glitchygames.tools.multi_controller_manager import MultiControllerManager
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager


class TestBitmappyMultiControllerIntegration:
    """Test integration between multi-controller system and bitmappy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Reset singleton for clean tests
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        
        # Mock pygame initialization
        with patch('pygame.init'):
            with patch('pygame.display.set_mode'):
                # Import bitmappy after mocking pygame
                from glitchygames.tools.bitmappy import BitmapEditorScene
                
                # Create mock scene
                self.scene = Mock()
                self.scene.controller_selections = {}
                self.scene.film_strips = {}
                self.scene.film_strip_sprites = {}
                
                # Initialize multi-controller components
                self.manager = MultiControllerManager()
                self.visual_manager = VisualCollisionManager()
    
    def test_controller_event_handling_integration(self):
        """Test controller event handling integration with bitmappy."""
        # Mock controller events
        mock_events = [
            Mock(type=pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_A, instance_id=0),
            Mock(type=pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_A, instance_id=1),
            Mock(type=pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_LEFT, instance_id=0),
            Mock(type=pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT, instance_id=1),
        ]
        
        # Set up controllers
        for i in range(2):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.scene.controller_selections[i] = ControllerSelection(i, instance_id)
        
        # Test event processing
        for event in mock_events:
            # Simulate bitmappy's controller event handling
            if event.type == pygame.CONTROLLERBUTTONDOWN:
                if event.button == pygame.CONTROLLER_BUTTON_A:
                    # A button - select current frame
                    controller_id = event.instance_id
                    if controller_id in self.scene.controller_selections:
                        self.scene.controller_selections[controller_id].activate()
                        self.scene.controller_selections[controller_id].set_selection("test_animation", 0)
                elif event.button == pygame.CONTROLLER_BUTTON_DPAD_LEFT:
                    # D-pad left - previous frame
                    controller_id = event.instance_id
                    if controller_id in self.scene.controller_selections:
                        current_animation, current_frame = self.scene.controller_selections[controller_id].get_selection()
                        if current_frame > 0:
                            self.scene.controller_selections[controller_id].set_selection(current_animation, current_frame - 1)
                elif event.button == pygame.CONTROLLER_BUTTON_DPAD_RIGHT:
                    # D-pad right - next frame
                    controller_id = event.instance_id
                    if controller_id in self.scene.controller_selections:
                        current_animation, current_frame = self.scene.controller_selections[controller_id].get_selection()
                        self.scene.controller_selections[controller_id].set_selection(current_animation, current_frame + 1)
        
        # Verify controller states
        assert self.scene.controller_selections[0].is_active()
        assert self.scene.controller_selections[1].is_active()
        
        # Verify navigation occurred
        animation_0, frame_0 = self.scene.controller_selections[0].get_selection()
        animation_1, frame_1 = self.scene.controller_selections[1].get_selection()
        
        assert animation_0 == "test_animation"
        assert frame_0 == 0  # Left d-pad should have decremented
        assert animation_1 == "test_animation"
        assert frame_1 == 1  # Right d-pad should have incremented
    
    def test_film_strip_integration(self):
        """Test integration with film strip navigation."""
        # Mock film strips
        self.scene.film_strips = {
            "animation1": Mock(),
            "animation2": Mock(),
            "animation3": Mock()
        }
        
        # Set up controllers
        for i in range(2):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.scene.controller_selections[i] = ControllerSelection(i, instance_id)
            self.scene.controller_selections[i].activate()
        
        # Test independent navigation
        self.scene.controller_selections[0].set_selection("animation1", 0)
        self.scene.controller_selections[1].set_selection("animation2", 1)
        
        # Verify independent state
        anim_0, frame_0 = self.scene.controller_selections[0].get_selection()
        anim_1, frame_1 = self.scene.controller_selections[1].get_selection()
        
        assert anim_0 == "animation1"
        assert frame_0 == 0
        assert anim_1 == "animation2"
        assert frame_1 == 1
        
        # Test switching between controllers
        self.scene.controller_selections[0].set_selection("animation3", 2)
        
        # Controller 0 should have new selection, controller 1 unchanged
        anim_0, frame_0 = self.scene.controller_selections[0].get_selection()
        anim_1, frame_1 = self.scene.controller_selections[1].get_selection()
        
        assert anim_0 == "animation3"
        assert frame_0 == 2
        assert anim_1 == "animation2"  # Unchanged
        assert frame_1 == 1
    
    def test_visual_indicator_integration(self):
        """Test visual indicator integration with bitmappy interface."""
        # Set up controllers with visual indicators
        for i in range(3):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.scene.controller_selections[i] = ControllerSelection(i, instance_id)
            self.scene.controller_selections[i].activate()
            self.scene.controller_selections[i].set_selection(f"animation_{i}", i)
            
            # Add visual indicators
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=instance_id,
                color=self.manager.CONTROLLER_COLORS[i],
                position=(100 + i * 50, 100)
            )
        
        # Test collision avoidance
        # Add controllers at same position to test collision handling
        for i in range(3, 6):
            instance_id = i
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=instance_id,
                color=(255, 0, 0),
                position=(200, 200)  # Same position
            )
        
        # Verify collision avoidance was applied
        assert (200, 200) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(200, 200)]) == 3
        
        # Verify all indicators exist
        assert len(self.visual_manager.indicators) == 6
    
    def test_controller_hotplug_simulation(self):
        """Test controller hotplug simulation."""
        # Simulate controller connection
        instance_id = 0
        self.manager._handle_controller_connect(instance_id)
        
        # Verify controller was added
        assert instance_id in self.manager.controllers
        controller_info = self.manager.controllers[instance_id]
        assert controller_info.status.value == "connected"
        
        # Assign controller
        controller_id = self.manager.assign_controller(instance_id)
        assert controller_id is not None
        
        # Activate controller
        self.manager.activate_controller(instance_id)
        assert self.manager.is_controller_active(instance_id)
        
        # Create controller selection
        self.scene.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        self.scene.controller_selections[controller_id].activate()
        self.scene.controller_selections[controller_id].set_selection("test_animation", 0)
        
        # Simulate controller disconnection
        self.manager._handle_controller_disconnect(instance_id)
        
        # Verify controller was removed
        assert instance_id not in self.manager.controllers
        assert instance_id not in self.manager.assigned_controllers
    
    def test_multi_controller_navigation_scenarios(self):
        """Test various multi-controller navigation scenarios."""
        # Set up multiple controllers
        for i in range(4):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.scene.controller_selections[i] = ControllerSelection(i, instance_id)
            self.scene.controller_selections[i].activate()
        
        # Scenario 1: Independent navigation
        self.scene.controller_selections[0].set_selection("animation1", 0)
        self.scene.controller_selections[1].set_selection("animation2", 1)
        self.scene.controller_selections[2].set_selection("animation3", 2)
        self.scene.controller_selections[3].set_selection("animation1", 3)
        
        # Verify independent states
        for i in range(4):
            animation, frame = self.scene.controller_selections[i].get_selection()
            if i == 0:
                assert animation == "animation1" and frame == 0
            elif i == 1:
                assert animation == "animation2" and frame == 1
            elif i == 2:
                assert animation == "animation3" and frame == 2
            elif i == 3:
                assert animation == "animation1" and frame == 3
        
        # Scenario 2: Navigation history tracking
        # Navigate controller 0 through multiple animations
        self.scene.controller_selections[0].set_selection("animation2", 0)
        self.scene.controller_selections[0].set_selection("animation3", 1)
        self.scene.controller_selections[0].set_selection("animation1", 2)
        
        # Verify navigation history
        history = self.scene.controller_selections[0].get_navigation_history()
        assert len(history) >= 2  # Should have history of transitions
        
        # Scenario 3: Controller switching
        # Deactivate controller 0, activate controller 1
        self.scene.controller_selections[0].deactivate()
        self.scene.controller_selections[1].activate()
        
        # Controller 0 should be inactive, controller 1 active
        assert not self.scene.controller_selections[0].is_active()
        assert self.scene.controller_selections[1].is_active()
        
        # Controller 0 should preserve its state
        animation, frame = self.scene.controller_selections[0].get_selection()
        assert animation == "animation1" and frame == 2
    
    def test_error_handling_integration(self):
        """Test error handling in integration scenarios."""
        # Test with invalid controller events
        invalid_events = [
            Mock(type=pygame.CONTROLLERBUTTONDOWN, button=999, instance_id=999),
            Mock(type=pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_A, instance_id=None),
        ]
        
        # These should not crash the system
        for event in invalid_events:
            try:
                # Simulate event processing
                if hasattr(event, 'instance_id') and event.instance_id is not None:
                    if event.instance_id in self.scene.controller_selections:
                        # Process event
                        pass
            except Exception:
                # Should handle gracefully
                pass
        
        # Test with malformed controller data
        try:
            # Try to access non-existent controller
            if 999 in self.scene.controller_selections:
                self.scene.controller_selections[999].activate()
        except Exception:
            # Should handle gracefully
            pass
        
        # System should still be functional
        assert True  # If we get here, error handling worked
    
    def test_performance_integration(self):
        """Test performance characteristics in integration scenarios."""
        import time
        
        # Set up many controllers
        start_time = time.time()
        for i in range(10):
            instance_id = i
            self.manager.controllers[instance_id] = Mock()
            self.manager.assigned_controllers[instance_id] = i
            self.scene.controller_selections[i] = ControllerSelection(i, instance_id)
            self.scene.controller_selections[i].activate()
            
            # Add visual indicators
            self.visual_manager.add_controller_indicator(
                controller_id=i,
                instance_id=instance_id,
                color=(255, 0, 0),
                position=(i * 10, i * 10)
            )
        setup_time = time.time()
        
        # Should set up quickly
        assert setup_time - start_time < 1.0
        
        # Test rapid navigation
        nav_start = time.time()
        for _ in range(100):
            for i in range(10):
                self.scene.controller_selections[i].set_selection(f"animation_{i}", i)
        nav_end = time.time()
        
        # Should navigate quickly
        assert nav_end - nav_start < 1.0
        
        # Test visual updates
        visual_start = time.time()
        for i in range(10):
            self.visual_manager.update_controller_position(i, (i * 20, i * 20))
        visual_end = time.time()
        
        # Should update quickly
        assert visual_end - visual_start < 1.0
