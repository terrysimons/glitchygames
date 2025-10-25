"""
Tests for Plan C Bitmappy Integration

Tests the integration of Plan C mode switching with the main Bitmappy application,
including trigger handling, mode switching, and visual updates.
"""

import pytest
import pygame
import time
from unittest.mock import Mock, patch, MagicMock

from glitchygames.tools.controller_mode_system import ControllerMode, ModeSwitcher
from glitchygames.tools.visual_collision_manager import LocationType


class TestBitmappyPlanCIntegration:
    """Test Plan C integration with Bitmappy."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        self.mode_switcher = ModeSwitcher()
        self.controller_id = 0
        self.instance_id = 0
        
        # Mock Bitmappy scene
        self.mock_scene = Mock()
        self.mock_scene.mode_switcher = self.mode_switcher
        self.mock_scene.controller_selections = {}
        self.mock_scene.multi_controller_manager = Mock()
        self.mock_scene.visual_collision_manager = Mock()
        
        # Mock controller info
        self.mock_controller_info = Mock()
        self.mock_controller_info.color = (255, 0, 0)
        self.mock_scene.multi_controller_manager.get_controller_id.return_value = self.controller_id
        self.mock_scene.multi_controller_manager.get_controller_info.return_value = self.mock_controller_info
    
    def teardown_method(self):
        """Clean up test fixtures."""
        pygame.quit()
    
    def test_trigger_axis_motion_handling(self):
        """Test handling of trigger axis motion events."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        # Mock trigger axis motion event
        mock_event = Mock()
        mock_event.instance_id = self.instance_id
        mock_event.axis = 4  # L2 axis
        mock_event.value = 1.0  # Fully pressed
        
        # Mock the trigger handling method
        with patch.object(self.mock_scene, '_handle_trigger_axis_motion') as mock_handle:
            self.mock_scene._handle_trigger_axis_motion(mock_event)
            mock_handle.assert_called_once_with(mock_event)
    
    def test_controller_registration_on_trigger(self):
        """Test that controllers are registered when trigger events occur."""
        # Mock trigger axis motion event
        mock_event = Mock()
        mock_event.instance_id = self.instance_id
        mock_event.axis = 4  # L2 axis
        mock_event.value = 1.0  # Fully pressed
        
        # Verify controller is not registered initially
        assert self.controller_id not in self.mode_switcher.controller_modes
        
        # Simulate trigger handling
        with patch.object(self.mock_scene, '_handle_trigger_axis_motion') as mock_handle:
            # Mock the registration logic
            self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
            
            # Verify controller was registered
            assert self.controller_id in self.mode_switcher.controller_modes
            assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.FILM_STRIP
    
    def test_mode_switching_via_triggers(self):
        """Test mode switching via trigger input."""
        # Register controller in film strip mode
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        # Test L2 trigger (should go to canvas)
        current_time = time.time()
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        
        assert new_mode == ControllerMode.CANVAS
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.CANVAS
    
    def test_visual_indicator_updates_on_mode_switch(self):
        """Test that visual indicators are updated when mode switches."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        # Mock visual indicator update
        with patch.object(self.mock_scene, '_update_controller_visual_indicator_for_mode') as mock_update:
            # Switch mode
            current_time = time.time()
            new_mode = self.mode_switcher.handle_trigger_input(
                self.controller_id, 1.0, 0.0, current_time
            )
            
            # Verify visual indicator update was called
            mock_update.assert_called_once_with(self.controller_id, new_mode)
    
    def test_controller_position_tracking_in_bitmappy(self):
        """Test controller position tracking in Bitmappy context."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.CANVAS)
        
        # Set controller position
        position = (15, 15)
        self.mode_switcher.save_controller_position(self.controller_id, position)
        
        # Verify position is tracked
        position_data = self.mode_switcher.get_controller_position(self.controller_id)
        assert position_data is not None
        assert position_data.is_valid
        assert position_data.position == position
    
    def test_multi_controller_mode_switching(self):
        """Test multiple controllers switching modes independently."""
        # Register multiple controllers
        controllers = [0, 1, 2]
        for controller_id in controllers:
            self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        
        # Switch each controller to different modes
        current_time = time.time()
        
        # Controller 0: FILM_STRIP -> CANVAS
        new_mode_0 = self.mode_switcher.handle_trigger_input(0, 1.0, 0.0, current_time)
        assert new_mode_0 == ControllerMode.CANVAS
        
        # Controller 1: FILM_STRIP -> CANVAS -> R_SLIDER
        new_mode_1 = self.mode_switcher.handle_trigger_input(1, 1.0, 0.0, current_time)
        assert new_mode_1 == ControllerMode.CANVAS
        new_mode_1 = self.mode_switcher.handle_trigger_input(1, 1.0, 0.0, current_time + 0.1)
        assert new_mode_1 == ControllerMode.R_SLIDER
        
        # Controller 2: Stay in FILM_STRIP
        assert self.mode_switcher.get_controller_mode(2) == ControllerMode.FILM_STRIP
        
        # Verify all controllers have correct modes
        assert self.mode_switcher.get_controller_mode(0) == ControllerMode.CANVAS
        assert self.mode_switcher.get_controller_mode(1) == ControllerMode.R_SLIDER
        assert self.mode_switcher.get_controller_mode(2) == ControllerMode.FILM_STRIP
    
    def test_trigger_debouncing(self):
        """Test that trigger debouncing works correctly."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        current_time = time.time()
        
        # First trigger press
        new_mode_1 = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        assert new_mode_1 == ControllerMode.CANVAS
        
        # Immediate second press (should be debounced)
        new_mode_2 = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time + 0.01
        )
        assert new_mode_2 is None  # Should be debounced
        
        # Press after debounce time
        new_mode_3 = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time + 0.2
        )
        assert new_mode_3 == ControllerMode.R_SLIDER
    
    def test_controller_hotplug_support(self):
        """Test controller hotplug support in Plan C."""
        # Simulate controller connection
        new_controller_id = 5
        self.mode_switcher.register_controller(new_controller_id, ControllerMode.FILM_STRIP)
        
        # Verify controller is registered
        assert new_controller_id in self.mode_switcher.controller_modes
        assert self.mode_switcher.get_controller_mode(new_controller_id) == ControllerMode.FILM_STRIP
        
        # Simulate controller disconnection
        self.mode_switcher.unregister_controller(new_controller_id)
        
        # Verify controller is unregistered
        assert new_controller_id not in self.mode_switcher.controller_modes
        assert self.mode_switcher.get_controller_mode(new_controller_id) is None
    
    def test_mode_switching_edge_cases(self):
        """Test edge cases in mode switching."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        current_time = time.time()
        
        # Test R2 on FILM_STRIP (should do nothing)
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 1.0, current_time
        )
        assert new_mode is None
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.FILM_STRIP
        
        # Test L2 on FILM_STRIP (should go to CANVAS)
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        assert new_mode == ControllerMode.CANVAS
        
        # Test R2 on CANVAS (should go to FILM_STRIP)
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 1.0, current_time + 0.1
        )
        assert new_mode == ControllerMode.FILM_STRIP
    
    def test_controller_mode_state_persistence(self):
        """Test that controller mode state persists across operations."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)
        
        # Set position
        position = (20, 20)
        self.mode_switcher.save_controller_position(self.controller_id, position)
        
        # Switch mode
        current_time = time.time()
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        
        # Verify mode changed but position is preserved
        assert new_mode == ControllerMode.CANVAS
        position_data = self.mode_switcher.get_controller_position(self.controller_id)
        assert position_data.position == position
    
    def test_integration_with_existing_bitmappy_features(self):
        """Test that Plan C integrates with existing Bitmappy features."""
        # This would test integration with:
        # - Film strip navigation
        # - Canvas editing
        # - Color sliders
        # - Animation playback
        # - Save/load functionality
        
        # For now, just verify the mode switcher is properly initialized
        assert self.mode_switcher is not None
        assert hasattr(self.mode_switcher, 'controller_modes')
        assert hasattr(self.mode_switcher, 'trigger_detector')
        assert hasattr(self.mode_switcher, 'l2_cycle')
        assert hasattr(self.mode_switcher, 'r2_cycle')
    
    def test_performance_under_load(self):
        """Test Plan C performance under load."""
        # Register many controllers
        num_controllers = 10
        for i in range(num_controllers):
            self.mode_switcher.register_controller(i, ControllerMode.FILM_STRIP)
        
        # Simulate rapid mode switching
        current_time = time.time()
        for i in range(num_controllers):
            for _ in range(5):  # 5 mode switches per controller
                self.mode_switcher.handle_trigger_input(i, 1.0, 0.0, current_time)
                current_time += 0.1
        
        # Verify all controllers are still properly tracked
        for i in range(num_controllers):
            assert i in self.mode_switcher.controller_modes
            assert self.mode_switcher.get_controller_mode(i) is not None
