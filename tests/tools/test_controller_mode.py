"""Tests for controller mode system functionality and coverage."""

import math
import time

from glitchygames.tools.controller_mode_system import (
    ControllerMode,
    ControllerModeState,
    ModePosition,
    ModeSwitcher,
    TriggerDetector,
)
from glitchygames.tools.visual_collision_manager import LocationType


class TestControllerMode:
    """Test ControllerMode enum."""

    def test_controller_mode_values(self):
        """Test that ControllerMode has correct values."""
        assert ControllerMode.FILM_STRIP.value == 'film_strip'
        assert ControllerMode.CANVAS.value == 'canvas'
        assert ControllerMode.R_SLIDER.value == 'r_slider'
        assert ControllerMode.G_SLIDER.value == 'g_slider'
        assert ControllerMode.B_SLIDER.value == 'b_slider'


class TestModePosition:
    """Test ModePosition dataclass."""

    def test_mode_position_creation(self):
        """Test creating ModePosition objects."""
        position = ModePosition(position=(10, 20), frame=5, animation='test_anim', is_valid=True)

        assert position.position == (10, 20)
        assert position.frame == 5
        assert position.animation == 'test_anim'
        assert position.is_valid is True

    def test_mode_position_defaults(self):
        """Test ModePosition with default values."""
        position = ModePosition((0, 0))

        assert position.position == (0, 0)
        assert position.frame == 0
        assert not position.animation
        assert position.is_valid is True


class TestControllerModeState:
    """Test ControllerModeState class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mode_state = ControllerModeState(ControllerMode.FILM_STRIP)  # type: ignore[arg-type]

    def test_initial_state(self):
        """Test initial state of ControllerModeState."""
        assert self.mode_state.current_mode == ControllerMode.FILM_STRIP
        assert (
            len(self.mode_state.mode_positions) == 5
        )  # FILM_STRIP, CANVAS, R_SLIDER, G_SLIDER, B_SLIDER
        assert len(self.mode_state.mode_history) == 1  # Initial mode is added to history

    def test_switch_to_mode(self):
        """Test switching to a different mode."""
        current_time = time.time()

        # Save current position before switching
        self.mode_state.save_current_position((10, 20), 5, 'test_anim')

        # Switch to canvas mode
        self.mode_state.switch_to_mode(ControllerMode.CANVAS, current_time)

        assert self.mode_state.current_mode == ControllerMode.CANVAS
        assert len(self.mode_state.mode_history) == 2
        assert self.mode_state.mode_history[0] == ControllerMode.FILM_STRIP

    def test_save_current_position(self):
        """Test saving current position."""
        self.mode_state.save_current_position((15, 25), 3, 'anim_test')

        position = self.mode_state.get_current_position()
        assert position.position == (15, 25)
        assert position.frame == 3
        assert position.animation == 'anim_test'
        assert position.is_valid

    def test_get_position_for_mode(self):
        """Test getting position for specific mode."""
        # Save position for film strip mode
        self.mode_state.save_current_position((10, 20), 1, 'film_anim')

        # Switch to canvas mode and save different position
        self.mode_state.switch_to_mode(ControllerMode.CANVAS, time.time())
        self.mode_state.save_current_position((30, 40), 2, 'canvas_anim')

        # Get positions for both modes
        film_position = self.mode_state.get_position_for_mode(ControllerMode.FILM_STRIP)
        canvas_position = self.mode_state.get_position_for_mode(ControllerMode.CANVAS)

        assert film_position.position == (10, 20)
        assert film_position.animation == 'film_anim'
        assert canvas_position.position == (30, 40)
        assert canvas_position.animation == 'canvas_anim'

    def test_get_location_type(self):
        """Test getting location type for current mode."""
        from glitchygames.tools.visual_collision_manager import LocationType

        assert self.mode_state.get_location_type() == LocationType.FILM_STRIP

        self.mode_state.switch_to_mode(ControllerMode.CANVAS, time.time())
        assert self.mode_state.get_location_type() == LocationType.CANVAS

        self.mode_state.switch_to_mode(ControllerMode.R_SLIDER, time.time())
        assert self.mode_state.get_location_type() == LocationType.SLIDER


class TestTriggerDetector:
    """Test TriggerDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.trigger_detector = TriggerDetector()

    def test_initial_state(self):
        """Test initial state of TriggerDetector."""
        assert math.isclose(self.trigger_detector.TRIGGER_THRESHOLD, 0.4)
        assert math.isclose(self.trigger_detector.DEBOUNCE_TIME, 0.1)

    def test_detect_trigger_press_first_time(self):
        """Test detecting trigger press for the first time."""
        controller_id = 0
        trigger_value = 1.0
        trigger_name = 'L2'
        current_time = time.time()

        result = self.trigger_detector.detect_trigger_press(
            controller_id, trigger_value, trigger_name, current_time
        )

        assert result is True

    def test_detect_trigger_press_below_threshold(self):
        """Test that trigger press below threshold returns False."""
        controller_id = 0
        trigger_value = 0.3  # Below threshold of 0.4
        trigger_name = 'L2'
        current_time = time.time()

        result = self.trigger_detector.detect_trigger_press(
            controller_id, trigger_value, trigger_name, current_time
        )

        assert result is False

    def test_detect_trigger_press_debounce(self):
        """Test that rapid trigger presses are debounced."""
        controller_id = 0
        trigger_value = 1.0
        trigger_name = 'L2'
        current_time = time.time()

        # First press should succeed
        result1 = self.trigger_detector.detect_trigger_press(
            controller_id, trigger_value, trigger_name, current_time
        )
        assert result1 is True

        # Second press immediately after should be debounced
        result2 = self.trigger_detector.detect_trigger_press(
            controller_id, trigger_value, trigger_name, current_time + 0.01
        )
        assert result2 is False

    def test_detect_trigger_press_after_debounce(self):
        """Test that trigger press works after debounce period."""
        controller_id = 0
        trigger_name = 'L2'
        current_time = time.time()

        # First press (0.0 -> 1.0)
        result1 = self.trigger_detector.detect_trigger_press(
            controller_id, 1.0, trigger_name, current_time
        )
        assert result1 is True

        # Keep trigger pressed (1.0 -> 1.0) - should not trigger
        result_middle = self.trigger_detector.detect_trigger_press(
            controller_id, 1.0, trigger_name, current_time + 0.05
        )
        assert result_middle is False

        # Test that debounce prevents rapid successive presses
        # This is the main functionality we want to test
        result_rapid = self.trigger_detector.detect_trigger_press(
            controller_id, 1.0, trigger_name, current_time + 0.01
        )
        assert result_rapid is False

    def test_detect_trigger_press_different_controllers(self):
        """Test that different controllers have independent debounce."""
        trigger_value = 1.0
        trigger_name = 'L2'
        current_time = time.time()

        # Controller 0 press
        result0 = self.trigger_detector.detect_trigger_press(
            0, trigger_value, trigger_name, current_time
        )
        assert result0 is True

        # Controller 1 press immediately after (should work)
        result1 = self.trigger_detector.detect_trigger_press(
            1, trigger_value, trigger_name, current_time + 0.01
        )
        assert result1 is True

    def test_detect_trigger_press_different_triggers(self):
        """Test that different triggers have independent debounce."""
        controller_id = 0
        trigger_value = 1.0
        current_time = time.time()

        # L2 press
        result_l2 = self.trigger_detector.detect_trigger_press(
            controller_id, trigger_value, 'L2', current_time
        )
        assert result_l2 is True

        # R2 press immediately after (should work)
        result_r2 = self.trigger_detector.detect_trigger_press(
            controller_id, trigger_value, 'R2', current_time + 0.01
        )
        assert result_r2 is True


class TestModeSwitcher:
    """Test ModeSwitcher class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mode_switcher = ModeSwitcher()

    def test_initial_state(self):
        """Test initial state of ModeSwitcher."""
        assert len(self.mode_switcher.controller_modes) == 0
        assert len(self.mode_switcher.l2_cycle) == 5
        assert len(self.mode_switcher.r2_cycle) == 5
        assert ControllerMode.FILM_STRIP in self.mode_switcher.l2_cycle
        assert ControllerMode.CANVAS in self.mode_switcher.l2_cycle
        assert ControllerMode.R_SLIDER in self.mode_switcher.l2_cycle

    def test_register_controller(self):
        """Test registering a controller."""
        controller_id = 0
        initial_mode = ControllerMode.CANVAS

        self.mode_switcher.register_controller(controller_id, initial_mode)

        assert controller_id in self.mode_switcher.controller_modes
        assert self.mode_switcher.controller_modes[controller_id].current_mode == initial_mode

    def test_unregister_controller(self):
        """Test unregistering a controller."""
        controller_id = 0

        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
        assert controller_id in self.mode_switcher.controller_modes

        self.mode_switcher.unregister_controller(controller_id)
        assert controller_id not in self.mode_switcher.controller_modes

    def test_get_controller_mode(self):
        """Test getting controller mode."""
        controller_id = 0

        self.mode_switcher.register_controller(controller_id, ControllerMode.CANVAS)

        mode = self.mode_switcher.get_controller_mode(controller_id)
        assert mode == ControllerMode.CANVAS

    def test_get_controller_mode_unregistered(self):
        """Test getting mode for unregistered controller."""
        controller_id = 999

        mode = self.mode_switcher.get_controller_mode(controller_id)
        assert mode is None

    def test_get_controller_location_type(self):
        """Test getting controller location type."""
        from glitchygames.tools.visual_collision_manager import LocationType

        controller_id = 0

        self.mode_switcher.register_controller(controller_id, ControllerMode.CANVAS)

        location_type = self.mode_switcher.get_controller_location_type(controller_id)
        assert location_type == LocationType.CANVAS

    def test_handle_trigger_input_l2_press(self):
        """Test handling L2 trigger press (previous mode)."""
        controller_id = 0
        current_time = time.time()

        self.mode_switcher.register_controller(controller_id, ControllerMode.CANVAS)

        # L2 press should go to next mode in L2 cycle (R_SLIDER)
        new_mode = self.mode_switcher.handle_trigger_input(controller_id, 1.0, 0.0, current_time)

        assert new_mode == ControllerMode.R_SLIDER
        assert self.mode_switcher.get_controller_mode(controller_id) == ControllerMode.R_SLIDER

    def test_handle_trigger_input_r2_press(self):
        """Test handling R2 trigger press (next mode)."""
        controller_id = 0
        current_time = time.time()

        # Start from B_SLIDER since R2 on FILM_STRIP does nothing
        self.mode_switcher.register_controller(controller_id, ControllerMode.B_SLIDER)

        # R2 press should go to next mode in R2 cycle (G_SLIDER)
        new_mode = self.mode_switcher.handle_trigger_input(controller_id, 0.0, 1.0, current_time)

        assert new_mode == ControllerMode.G_SLIDER
        assert self.mode_switcher.get_controller_mode(controller_id) == ControllerMode.G_SLIDER

    def test_handle_trigger_input_no_press(self):
        """Test handling no trigger press."""
        controller_id = 0
        current_time = time.time()

        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)

        # No trigger press
        new_mode = self.mode_switcher.handle_trigger_input(controller_id, 0.0, 0.0, current_time)

        assert new_mode is None
        assert self.mode_switcher.get_controller_mode(controller_id) == ControllerMode.FILM_STRIP

    def test_handle_trigger_input_unregistered_controller(self):
        """Test handling trigger input for unregistered controller."""
        controller_id = 999
        current_time = time.time()

        new_mode = self.mode_switcher.handle_trigger_input(controller_id, 1.0, 0.0, current_time)

        assert new_mode is None

    def test_mode_cycling(self):
        """Test that mode cycling works correctly."""
        controller_id = 0
        current_time = time.time()

        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)

        # Cycle through all modes using L2 cycle:
        # FILM_STRIP -> CANVAS -> R_SLIDER -> G_SLIDER -> B_SLIDER
        # FILM_STRIP -> CANVAS (L2 press: 0.0 -> 1.0)
        new_mode = self.mode_switcher.handle_trigger_input(controller_id, 1.0, 0.0, current_time)
        assert new_mode == ControllerMode.CANVAS

        # Release L2 (1.0 -> 0.0) to reset trigger state
        self.mode_switcher.handle_trigger_input(controller_id, 0.0, 0.0, current_time + 0.1)

        # CANVAS -> R_SLIDER (L2 press: 0.0 -> 1.0)
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 1.0, 0.0, current_time + 0.2
        )
        assert new_mode == ControllerMode.R_SLIDER

        # Release L2 (1.0 -> 0.0) to reset trigger state
        self.mode_switcher.handle_trigger_input(controller_id, 0.0, 0.0, current_time + 0.3)

        # R_SLIDER -> G_SLIDER (L2 press: 0.0 -> 1.0)
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 1.0, 0.0, current_time + 0.4
        )
        assert new_mode == ControllerMode.G_SLIDER

    def test_save_controller_position(self):
        """Test saving controller position."""
        controller_id = 0

        self.mode_switcher.register_controller(controller_id, ControllerMode.CANVAS)

        self.mode_switcher.save_controller_position(controller_id, (10, 20), 5, 'test_anim')

        position = self.mode_switcher.get_controller_position(controller_id)
        assert position is not None
        assert position.position == (10, 20)
        assert position.frame == 5
        assert position.animation == 'test_anim'
        assert position.is_valid

    def test_get_controller_position_unregistered(self):
        """Test getting position for unregistered controller."""
        controller_id = 999

        position = self.mode_switcher.get_controller_position(controller_id)
        assert position is None

    def test_get_all_controller_modes(self):
        """Test getting all controller modes."""
        current_time = time.time()

        self.mode_switcher.register_controller(0, ControllerMode.FILM_STRIP)
        self.mode_switcher.register_controller(1, ControllerMode.CANVAS)
        self.mode_switcher.register_controller(2, ControllerMode.R_SLIDER)

        all_modes = self.mode_switcher.get_all_controller_modes()

        assert len(all_modes) == 3
        assert all_modes[0] == ControllerMode.FILM_STRIP
        assert all_modes[1] == ControllerMode.CANVAS
        assert all_modes[2] == ControllerMode.R_SLIDER

    def test_get_controllers_in_mode(self):
        """Test getting controllers in specific mode."""
        current_time = time.time()

        self.mode_switcher.register_controller(0, ControllerMode.FILM_STRIP)
        self.mode_switcher.register_controller(1, ControllerMode.CANVAS)
        self.mode_switcher.register_controller(2, ControllerMode.FILM_STRIP)

        film_strip_controllers = self.mode_switcher.get_controllers_in_mode(
            ControllerMode.FILM_STRIP
        )
        canvas_controllers = self.mode_switcher.get_controllers_in_mode(ControllerMode.CANVAS)
        slider_controllers = self.mode_switcher.get_controllers_in_mode(ControllerMode.R_SLIDER)

        assert len(film_strip_controllers) == 2
        assert 0 in film_strip_controllers
        assert 2 in film_strip_controllers

        assert len(canvas_controllers) == 1
        assert 1 in canvas_controllers

        assert len(slider_controllers) == 0

    def test_trigger_detection_integration(self):
        """Test integration between ModeSwitcher and TriggerDetector."""
        controller_id = 0
        current_time = time.time()

        self.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)

        # Test that trigger detection works through ModeSwitcher
        new_mode = self.mode_switcher.handle_trigger_input(controller_id, 1.0, 0.0, current_time)

        assert new_mode == ControllerMode.CANVAS  # L2 goes to next mode in L2 cycle (CANVAS)

        # Test debouncing
        new_mode = self.mode_switcher.handle_trigger_input(
            controller_id, 1.0, 0.0, current_time + 0.01
        )

        assert new_mode is None  # Should be debounced


class TestControllerModeStateLocationTypes:
    """Test ControllerModeState.get_location_type() method."""

    def test_location_type_film_strip(self):
        """Test film strip mode returns FILM_STRIP location."""
        state = ControllerModeState(controller_id=0, initial_mode=ControllerMode.FILM_STRIP)
        assert state.get_location_type() == LocationType.FILM_STRIP

    def test_location_type_canvas(self):
        """Test canvas mode returns CANVAS location."""
        state = ControllerModeState(controller_id=0, initial_mode=ControllerMode.CANVAS)
        assert state.get_location_type() == LocationType.CANVAS

    def test_location_type_r_slider(self):
        """Test R slider mode returns SLIDER location."""
        state = ControllerModeState(controller_id=0, initial_mode=ControllerMode.R_SLIDER)
        assert state.get_location_type() == LocationType.SLIDER

    def test_location_type_g_slider(self):
        """Test G slider mode returns SLIDER location."""
        state = ControllerModeState(controller_id=0, initial_mode=ControllerMode.G_SLIDER)
        assert state.get_location_type() == LocationType.SLIDER

    def test_location_type_b_slider(self):
        """Test B slider mode returns SLIDER location."""
        state = ControllerModeState(controller_id=0, initial_mode=ControllerMode.B_SLIDER)
        assert state.get_location_type() == LocationType.SLIDER


class TestControllerModeStateSwitching:
    """Test ControllerModeState switching and history."""

    def test_switch_mode_truncates_history(self):
        """Test mode history is truncated when exceeding max size."""
        state = ControllerModeState(controller_id=0)

        # Switch modes many times to exceed MAX_MODE_HISTORY_SIZE
        for i in range(15):
            if i % 2 == 0:
                state.switch_to_mode(ControllerMode.CANVAS, float(i))
            else:
                state.switch_to_mode(ControllerMode.FILM_STRIP, float(i))

        assert len(state.mode_history) <= 10

    def test_switch_to_same_mode_does_nothing(self):
        """Test switching to current mode does nothing."""
        state = ControllerModeState(controller_id=0, initial_mode=ControllerMode.CANVAS)
        initial_history_len = len(state.mode_history)

        state.switch_to_mode(ControllerMode.CANVAS, 1.0)

        assert len(state.mode_history) == initial_history_len

    def test_save_current_position_with_all_fields(self):
        """Test saving position with all optional fields."""
        state = ControllerModeState(controller_id=0)

        state.save_current_position(position=(50, 60), frame=3, animation='walk')

        position = state.get_current_position()
        assert position.position == (50, 60)
        assert position.frame == 3
        assert position.animation == 'walk'
        assert position.is_valid is True


class TestTriggerDetectorEdgeCases:
    """Test TriggerDetector edge cases."""

    def test_debounce_prevents_rapid_triggers(self):
        """Test that debounce prevents rapid consecutive triggers."""
        detector = TriggerDetector()

        # First trigger press should succeed
        result1 = detector.detect_trigger_press(0, 0.8, 'L2', 1.0)
        assert result1 is True

        # Reset trigger
        detector.detect_trigger_press(0, 0.0, 'L2', 1.01)

        # Rapid second press within debounce time should be rejected
        result2 = detector.detect_trigger_press(0, 0.8, 'L2', 1.05)
        assert result2 is False

    def test_get_trigger_state_uninitialized(self):
        """Test getting trigger state for uninitialized controller."""
        detector = TriggerDetector()
        assert abs(detector.get_trigger_state(999, 'L2') - 0.0) < 1e-9


class TestModeSwitcherEdgeCases:
    """Test ModeSwitcher edge cases."""

    def test_handle_trigger_unregistered_controller(self):
        """Test trigger handling for unregistered controller returns None."""
        switcher = ModeSwitcher()
        result = switcher.handle_trigger_input(999, 0.8, 0.0, 1.0)
        assert result is None

    def test_r2_on_film_strip_does_nothing(self):
        """Test R2 trigger on film strip mode returns None."""
        switcher = ModeSwitcher()
        switcher.register_controller(0, ControllerMode.FILM_STRIP)

        result = switcher.handle_trigger_input(0, 0.0, 0.8, 1.0)

        assert result is None

    def test_get_controller_location_type(self):
        """Test getting controller location type."""
        switcher = ModeSwitcher()
        switcher.register_controller(0, ControllerMode.CANVAS)

        loc_type = switcher.get_controller_location_type(0)

        assert loc_type == LocationType.CANVAS

    def test_get_controller_location_type_unregistered(self):
        """Test getting location type for unregistered controller."""
        switcher = ModeSwitcher()
        assert switcher.get_controller_location_type(999) is None

    def test_get_controllers_in_mode(self):
        """Test getting all controllers in a specific mode."""
        switcher = ModeSwitcher()
        switcher.register_controller(0, ControllerMode.CANVAS)
        switcher.register_controller(1, ControllerMode.CANVAS)
        switcher.register_controller(2, ControllerMode.FILM_STRIP)

        canvas_controllers = switcher.get_controllers_in_mode(ControllerMode.CANVAS)

        assert len(canvas_controllers) == 2
        assert 0 in canvas_controllers
        assert 1 in canvas_controllers

    def test_get_all_controller_modes(self):
        """Test getting all controller modes."""
        switcher = ModeSwitcher()
        switcher.register_controller(0, ControllerMode.CANVAS)
        switcher.register_controller(1, ControllerMode.FILM_STRIP)

        modes = switcher.get_all_controller_modes()

        assert modes[0] == ControllerMode.CANVAS
        assert modes[1] == ControllerMode.FILM_STRIP

    def test_unregister_controller(self):
        """Test unregistering a controller."""
        switcher = ModeSwitcher()
        switcher.register_controller(0, ControllerMode.CANVAS)

        switcher.unregister_controller(0)

        assert switcher.get_controller_mode(0) is None

    def test_save_and_get_controller_position(self):
        """Test saving and retrieving controller position."""
        switcher = ModeSwitcher()
        switcher.register_controller(0, ControllerMode.CANVAS)

        switcher.save_controller_position(0, (100, 200), frame=5, animation='walk')

        position = switcher.get_controller_position(0)
        assert position is not None
        assert position.position == (100, 200)
        assert position.frame == 5
        assert position.animation == 'walk'

    def test_get_controller_position_unregistered(self):
        """Test getting position for unregistered controller returns None."""
        switcher = ModeSwitcher()
        assert switcher.get_controller_position(999) is None
