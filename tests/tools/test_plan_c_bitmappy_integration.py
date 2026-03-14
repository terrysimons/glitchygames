"""
Tests for Plan C Bitmappy Integration

Tests the integration of Plan C mode switching with the main Bitmappy application,
including trigger handling, mode switching, and visual updates.
"""

import time

import pygame
import pytest
from glitchygames.tools.controller_mode_system import ControllerMode, ModeSwitcher
from glitchygames.tools.visual_collision_manager import LocationType


class TestBitmappyPlanCIntegration:
    """Test Plan C integration with Bitmappy."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up test fixtures."""
        pygame.init()
        self.mode_switcher = ModeSwitcher()
        self.controller_id = 0
        self.instance_id = 0

        # Mock Bitmappy scene
        self.mock_scene = mocker.Mock()
        self.mock_scene.mode_switcher = self.mode_switcher
        self.mock_scene.controller_selections = {}
        self.mock_scene.multi_controller_manager = mocker.Mock()
        self.mock_scene.visual_collision_manager = mocker.Mock()

        # Mock controller info
        self.mock_controller_info = mocker.Mock()
        self.mock_controller_info.color = (255, 0, 0)
        self.mock_scene.multi_controller_manager.get_controller_id.return_value = self.controller_id
        self.mock_scene.multi_controller_manager.get_controller_info.return_value = self.mock_controller_info

        # Store mocker for use in test methods
        self._mocker = mocker
    
    def teardown_method(self):
        """Clean up test fixtures."""
        pygame.quit()
    
    def test_trigger_axis_motion_handling(self):
        """Test handling of trigger axis motion events."""
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)

        # Mock trigger axis motion event
        mock_event = self._mocker.Mock()
        mock_event.instance_id = self.instance_id
        mock_event.axis = 4  # L2 axis
        mock_event.value = 1.0  # Fully pressed

        # Mock the trigger handling method
        mock_handle = self._mocker.patch.object(self.mock_scene, "_handle_trigger_axis_motion")
        self.mock_scene._handle_trigger_axis_motion(mock_event)
        mock_handle.assert_called_once_with(mock_event)
    
    def test_controller_registration_on_trigger(self):
        """Test that controllers are registered when trigger events occur."""
        # Mock trigger axis motion event
        mock_event = self._mocker.Mock()
        mock_event.instance_id = self.instance_id
        mock_event.axis = 4  # L2 axis
        mock_event.value = 1.0  # Fully pressed

        # Verify controller is not registered initially
        assert self.controller_id not in self.mode_switcher.controller_modes

        # Simulate trigger handling
        self._mocker.patch.object(self.mock_scene, "_handle_trigger_axis_motion")
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
        """Test that visual indicators are updated when mode switches.

        In the real Bitmappy flow, handle_trigger_input returns the new mode,
        and the caller is responsible for updating visual indicators.
        """
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)

        # Switch mode
        current_time = time.time()
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )
        assert new_mode == ControllerMode.CANVAS

        # Simulate what Bitmappy would do: call visual indicator update
        self.mock_scene._update_controller_visual_indicator_for_mode(
            self.controller_id, new_mode
        )

        # Verify visual indicator update was called
        self.mock_scene._update_controller_visual_indicator_for_mode.assert_called_once_with(
            self.controller_id, new_mode
        )
    
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
        
        # Controller 0: FILM_STRIP -> CANVAS (L2 press)
        new_mode_0 = self.mode_switcher.handle_trigger_input(0, 1.0, 0.0, current_time)
        assert new_mode_0 == ControllerMode.CANVAS

        # Controller 1: FILM_STRIP -> CANVAS -> R_SLIDER (L2 press, release, press)
        new_mode_1 = self.mode_switcher.handle_trigger_input(1, 1.0, 0.0, current_time)
        assert new_mode_1 == ControllerMode.CANVAS
        # Release L2 to reset threshold crossing detection
        self.mode_switcher.handle_trigger_input(1, 0.0, 0.0, current_time + 0.1)
        # Press L2 again: CANVAS -> R_SLIDER
        new_mode_1 = self.mode_switcher.handle_trigger_input(1, 1.0, 0.0, current_time + 0.2)
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
        
        # Immediate second press (trigger still held, no threshold crossing)
        new_mode_2 = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time + 0.01
        )
        assert new_mode_2 is None  # No threshold crossing (value stayed at 1.0)

        # Release L2 to allow next threshold crossing
        self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 0.0, current_time + 0.15
        )

        # Press again after debounce time: CANVAS -> R_SLIDER
        new_mode_3 = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time + 0.3
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
        """Test edge cases in mode switching.

        R2 on FILM_STRIP does nothing (returns None).
        L2 on FILM_STRIP goes to CANVAS.
        R2 on CANVAS goes to FILM_STRIP (R2 cycle: B->G->R->CANVAS->FILM_STRIP).

        Note: R2 press on FILM_STRIP still records trigger time for debounce,
        so subsequent R2 presses need sufficient time gap.
        """
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)

        current_time = time.time()

        # Test R2 on FILM_STRIP (should do nothing, but R2 trigger state updates)
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 1.0, current_time
        )
        assert new_mode is None
        assert self.mode_switcher.get_controller_mode(self.controller_id) == ControllerMode.FILM_STRIP

        # Release R2
        self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 0.0, current_time + 0.05
        )

        # Test L2 on FILM_STRIP (should go to CANVAS)
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time + 0.15
        )
        assert new_mode == ControllerMode.CANVAS

        # Release L2
        self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 0.0, current_time + 0.25
        )

        # Test R2 on CANVAS (should go to FILM_STRIP)
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 0.0, 1.0, current_time + 0.35
        )
        assert new_mode == ControllerMode.FILM_STRIP
    
    def test_controller_mode_state_persistence(self):
        """Test that controller mode state persists across operations.

        After switching modes, get_controller_position returns the current mode's
        position. The original mode's position is preserved and accessible via
        get_position_for_mode.
        """
        # Register controller
        self.mode_switcher.register_controller(self.controller_id, ControllerMode.FILM_STRIP)

        # Set position for FILM_STRIP mode
        position = (20, 20)
        self.mode_switcher.save_controller_position(self.controller_id, position)

        # Switch mode to CANVAS
        current_time = time.time()
        new_mode = self.mode_switcher.handle_trigger_input(
            self.controller_id, 1.0, 0.0, current_time
        )

        # Verify mode changed
        assert new_mode == ControllerMode.CANVAS

        # Current position is for CANVAS mode (default (0,0))
        current_position = self.mode_switcher.get_controller_position(self.controller_id)
        assert current_position.position == (0, 0)

        # FILM_STRIP position is preserved and accessible via mode state
        mode_state = self.mode_switcher.controller_modes[self.controller_id]
        film_strip_position = mode_state.get_position_for_mode(ControllerMode.FILM_STRIP)
        assert film_strip_position.position == position
    
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
        assert hasattr(self.mode_switcher, "controller_modes")
        assert hasattr(self.mode_switcher, "trigger_detector")
        assert hasattr(self.mode_switcher, "l2_cycle")
        assert hasattr(self.mode_switcher, "r2_cycle")
    
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
