"""
Multi-Controller Animation Loading Tests

This module tests the scenario where animations are loaded while controllers
are active, ensuring proper state management and visual indicator updates.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from typing import Dict

from glitchygames.tools.multi_controller_manager import MultiControllerManager, ControllerInfo, ControllerStatus
from glitchygames.tools.controller_selection import ControllerSelection
from glitchygames.tools.visual_collision_manager import VisualCollisionManager


class TestMultiControllerAnimationLoading:
    """Test animation loading scenarios with active controllers."""
    
    def setup_method(self):
        """Set up test fixtures."""
        MultiControllerManager._instance = None
        MultiControllerManager._initialized = False
        
        self.manager = MultiControllerManager()
        self.visual_manager = VisualCollisionManager()
        self.controller_selections: Dict[int, ControllerSelection] = {}
        
        # Mock bitmappy scene
        self.scene = Mock()
        self.scene.film_strips = {}
        self.scene.film_strip_sprites = {}
        self.scene.controller_selections = self.controller_selections
        self.scene.visual_collision_manager = self.visual_manager
        self.scene.multi_controller_manager = self.manager
    
    def test_load_animation_with_active_controllers(self):
        """Test loading a new animation when controllers are already active."""
        # Set up active controllers
        for i in range(2):
            instance_id = i
            controller_id = i
            
            # Set up controller in manager
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=controller_id,
                instance_id=instance_id,
                status=ControllerStatus.ACTIVE,
                color=self.manager.CONTROLLER_COLORS[controller_id]
            )
            self.manager.assigned_controllers[instance_id] = controller_id
            
            # Set up controller selection
            self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
            self.controller_selections[controller_id].activate()
            self.controller_selections[controller_id].set_selection(f"existing_animation_{i}", i)
            
            # Set up visual indicators
            self.visual_manager.add_controller_indicator(
                controller_id=controller_id,
                instance_id=instance_id,
                color=self.manager.CONTROLLER_COLORS[controller_id],
                position=(100 + i * 50, 100)
            )
        
        # Verify initial state
        assert len(self.controller_selections) == 2
        assert len(self.visual_manager.indicators) == 2
        
        # Simulate loading a new animation
        new_animation_name = "new_loaded_animation"
        self._simulate_animation_loading(new_animation_name)
        
        # Verify controllers are still active
        for controller_id in range(2):
            assert self.controller_selections[controller_id].is_active()
            assert controller_id in self.visual_manager.indicators
        
        # Verify visual indicators are still positioned correctly
        for controller_id in range(2):
            indicator = self.visual_manager.indicators[controller_id]
            assert indicator.is_visible
            assert indicator.color == self.manager.CONTROLLER_COLORS[controller_id]
    
    def test_load_animation_controller_state_preservation(self):
        """Test that controller states are preserved when loading new animations."""
        # Set up controller with specific state
        controller_id = 0
        instance_id = 0
        
        self.manager.controllers[instance_id] = ControllerInfo(
            controller_id=controller_id,
            instance_id=instance_id,
            status=ControllerStatus.ACTIVE,
            color=self.manager.CONTROLLER_COLORS[controller_id]
        )
        self.manager.assigned_controllers[instance_id] = controller_id
        
        self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        self.controller_selections[controller_id].activate()
        self.controller_selections[controller_id].set_selection("original_animation", 5)
        
        # Record initial state
        initial_animation, initial_frame = self.controller_selections[controller_id].get_selection()
        initial_history_length = len(self.controller_selections[controller_id].get_navigation_history())
        
        # Simulate loading new animation
        self._simulate_animation_loading("loaded_animation")
        
        # Verify controller state is preserved
        current_animation, current_frame = self.controller_selections[controller_id].get_selection()
        assert current_animation == initial_animation  # Should not change
        assert current_frame == initial_frame  # Should not change
        
        # Verify navigation history is preserved
        current_history_length = len(self.controller_selections[controller_id].get_navigation_history())
        assert current_history_length == initial_history_length
        
        # Verify controller is still active
        assert self.controller_selections[controller_id].is_active()
    
    def test_load_animation_visual_indicator_updates(self):
        """Test that visual indicators are updated when loading new animations."""
        # Set up controller with visual indicator
        controller_id = 0
        instance_id = 0
        
        self.manager.controllers[instance_id] = ControllerInfo(
            controller_id=controller_id,
            instance_id=instance_id,
            status=ControllerStatus.ACTIVE,
            color=self.manager.CONTROLLER_COLORS[controller_id]
        )
        self.manager.assigned_controllers[instance_id] = controller_id
        
        self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        self.controller_selections[controller_id].activate()
        self.controller_selections[controller_id].set_selection("animation_1", 2)
        
        # Add visual indicator
        self.visual_manager.add_controller_indicator(
            controller_id=controller_id,
            instance_id=instance_id,
            color=self.manager.CONTROLLER_COLORS[controller_id],
            position=(100, 100)
        )
        
        # Verify initial indicator
        assert controller_id in self.visual_manager.indicators
        initial_indicator = self.visual_manager.indicators[controller_id]
        assert initial_indicator.is_visible
        assert initial_indicator.color == self.manager.CONTROLLER_COLORS[controller_id]
        
        # Simulate loading new animation
        self._simulate_animation_loading("animation_2")
        
        # Verify indicator is still present and updated
        assert controller_id in self.visual_manager.indicators
        updated_indicator = self.visual_manager.indicators[controller_id]
        assert updated_indicator.is_visible
        assert updated_indicator.color == self.manager.CONTROLLER_COLORS[controller_id]
        
        # Verify position might be updated based on new animation
        # (This would depend on the specific implementation of position calculation)
        assert updated_indicator.position is not None
    
    def test_load_animation_multiple_controllers_collision_handling(self):
        """Test collision handling when loading animations with multiple active controllers."""
        # Set up multiple controllers at same position
        for i in range(3):
            instance_id = i
            controller_id = i
            
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=controller_id,
                instance_id=instance_id,
                status=ControllerStatus.ACTIVE,
                color=self.manager.CONTROLLER_COLORS[controller_id]
            )
            self.manager.assigned_controllers[instance_id] = controller_id
            
            self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
            self.controller_selections[controller_id].activate()
            self.controller_selections[controller_id].set_selection(f"animation_{i}", i)
            
            # Add indicators at same position to test collision
            self.visual_manager.add_controller_indicator(
                controller_id=controller_id,
                instance_id=instance_id,
                color=self.manager.CONTROLLER_COLORS[controller_id],
                position=(100, 100)  # Same position for all
            )
        
        # Verify collision groups are created
        assert (100, 100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100, 100)]) == 3
        
        # Simulate loading new animation
        self._simulate_animation_loading("new_animation")
        
        # Verify all controllers are still active
        for i in range(3):
            assert self.controller_selections[i].is_active()
            assert i in self.visual_manager.indicators
        
        # Verify collision handling is still working
        assert (100, 100) in self.visual_manager.collision_groups
        assert len(self.visual_manager.collision_groups[(100, 100)]) == 3
        
        # Verify indicators have proper offsets
        for i in range(3):
            indicator = self.visual_manager.indicators[i]
            assert indicator.is_visible
            # First controller should have (0,0) offset, others should have offsets
            if i == 0:
                assert indicator.offset == (0, 0)
            else:
                assert indicator.offset != (0, 0)
    
    def test_load_animation_controller_navigation_continuity(self):
        """Test that controller navigation continues to work after loading new animations."""
        # Set up controller
        controller_id = 0
        instance_id = 0
        
        self.manager.controllers[instance_id] = ControllerInfo(
            controller_id=controller_id,
            instance_id=instance_id,
            status=ControllerStatus.ACTIVE,
            color=self.manager.CONTROLLER_COLORS[controller_id]
        )
        self.manager.assigned_controllers[instance_id] = controller_id
        
        self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        self.controller_selections[controller_id].activate()
        self.controller_selections[controller_id].set_selection("animation_1", 0)
        
        # Simulate loading new animation
        self._simulate_animation_loading("animation_2")
        
        # Test that navigation still works
        # Navigate to next frame
        current_animation, current_frame = self.controller_selections[controller_id].get_selection()
        self.controller_selections[controller_id].set_selection(current_animation, current_frame + 1)
        
        # Verify navigation worked
        new_animation, new_frame = self.controller_selections[controller_id].get_selection()
        assert new_animation == current_animation
        assert new_frame == current_frame + 1
        
        # Test animation switching
        self.controller_selections[controller_id].set_selection("animation_2", 0)
        final_animation, final_frame = self.controller_selections[controller_id].get_selection()
        assert final_animation == "animation_2"
        assert final_frame == 0
    
    def test_load_animation_error_handling(self):
        """Test error handling when loading animations with active controllers."""
        # Set up controller
        controller_id = 0
        instance_id = 0
        
        self.manager.controllers[instance_id] = ControllerInfo(
            controller_id=controller_id,
            instance_id=instance_id,
            status=ControllerStatus.ACTIVE,
            color=self.manager.CONTROLLER_COLORS[controller_id]
        )
        self.manager.assigned_controllers[instance_id] = controller_id
        
        self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
        self.controller_selections[controller_id].activate()
        self.controller_selections[controller_id].set_selection("animation_1", 0)
        
        # Simulate loading animation with error
        with patch.object(self.scene, '_on_sprite_loaded', side_effect=Exception("Loading error")):
            try:
                self._simulate_animation_loading("error_animation")
            except Exception:
                pass  # Expected to fail
        
        # Verify controller state is preserved despite error
        assert self.controller_selections[controller_id].is_active()
        animation, frame = self.controller_selections[controller_id].get_selection()
        assert animation == "animation_1"  # Should be unchanged
        assert frame == 0  # Should be unchanged
        
        # Verify visual indicator is still present
        assert controller_id in self.visual_manager.indicators
    
    def test_load_animation_performance_impact(self):
        """Test performance impact of loading animations with active controllers."""
        # Set up multiple controllers
        num_controllers = 4
        for i in range(num_controllers):
            instance_id = i
            controller_id = i
            
            self.manager.controllers[instance_id] = ControllerInfo(
                controller_id=controller_id,
                instance_id=instance_id,
                status=ControllerStatus.ACTIVE,
                color=self.manager.CONTROLLER_COLORS[controller_id]
            )
            self.manager.assigned_controllers[instance_id] = controller_id
            
            self.controller_selections[controller_id] = ControllerSelection(controller_id, instance_id)
            self.controller_selections[controller_id].activate()
            self.controller_selections[controller_id].set_selection(f"animation_{i}", i)
            
            self.visual_manager.add_controller_indicator(
                controller_id=controller_id,
                instance_id=instance_id,
                color=self.manager.CONTROLLER_COLORS[controller_id],
                position=(100 + i * 10, 100 + i * 10)
            )
        
        # Measure time for loading animation
        start_time = time.time()
        self._simulate_animation_loading("performance_test_animation")
        end_time = time.time()
        
        # Should complete quickly (less than 1 second)
        assert end_time - start_time < 1.0
        
        # Verify all controllers are still active
        for i in range(num_controllers):
            assert self.controller_selections[i].is_active()
            assert i in self.visual_manager.indicators
    
    def _simulate_animation_loading(self, animation_name: str) -> None:
        """Simulate loading a new animation in the scene.
        
        Args:
            animation_name: Name of the animation to load
        """
        # Simulate adding new animation to film strips
        self.scene.film_strips[animation_name] = Mock()
        self.scene.film_strip_sprites[animation_name] = Mock()
        
        # Simulate the scene's animation loading process
        # This would typically involve:
        # 1. Creating film strip for new animation
        # 2. Updating visual indicators
        # 3. Notifying controllers of new animation
        
        # Update visual indicators for all active controllers
        for controller_id, selection in self.controller_selections.items():
            if selection.is_active():
                # Simulate position update based on new animation
                animation, frame = selection.get_selection()
                position = (100 + controller_id * 50, 100 + frame * 20)
                self.visual_manager.update_controller_position(controller_id, position)
        
        # Simulate collision optimization
        self.visual_manager.optimize_positioning()
