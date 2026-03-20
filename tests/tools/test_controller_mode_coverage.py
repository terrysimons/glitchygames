"""Tests to increase coverage for glitchygames/tools/controller_mode_system.py.

Targets uncovered lines in mode switching and trigger detection.
"""

from glitchygames.tools.controller_mode_system import (
    ControllerMode,
    ControllerModeState,
    ModeSwitcher,
    TriggerDetector,
)
from glitchygames.tools.visual_collision_manager import LocationType


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
