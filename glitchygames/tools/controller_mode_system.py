"""Controller Mode System for Multi-Controller Support.

This module provides mode switching capabilities for the multi-controller system,
allowing controllers to switch between film strip, canvas, and slider modes
using analog triggers (L2/R2).

Features:
- Mode state tracking per controller
- Analog trigger detection with threshold
- Mode switching with position preservation
- Visual indicator management per mode
"""

from dataclasses import dataclass
from enum import Enum

from glitchygames.tools.visual_collision_manager import LocationType

MAX_MODE_HISTORY_SIZE = 10


class ControllerMode(Enum):
    """Controller mode types."""

    FILM_STRIP = "film_strip"
    CANVAS = "canvas"
    R_SLIDER = "r_slider"
    G_SLIDER = "g_slider"
    B_SLIDER = "b_slider"


@dataclass
class ModePosition:
    """Position information for a specific mode."""

    position: tuple[int, int]
    frame: int = 0
    animation: str = ""
    is_valid: bool = True


@dataclass
class ControllerModeState:
    """Mode state for a single controller."""

    controller_id: int
    current_mode: ControllerMode
    mode_positions: dict[ControllerMode, ModePosition]
    mode_history: list[ControllerMode]
    last_mode_switch_time: float = 0.0

    def __init__(
        self, controller_id: int, initial_mode: ControllerMode = ControllerMode.FILM_STRIP
    ):
        """Initialize the controller mode state for a given controller."""
        self.controller_id = controller_id
        self.current_mode = initial_mode
        self.mode_positions = {
            ControllerMode.FILM_STRIP: ModePosition((0, 0)),
            ControllerMode.CANVAS: ModePosition((0, 0)),
            ControllerMode.R_SLIDER: ModePosition((0, 0)),
            ControllerMode.G_SLIDER: ModePosition((0, 0)),
            ControllerMode.B_SLIDER: ModePosition((0, 0)),
        }
        self.mode_history = [initial_mode]
        self.last_mode_switch_time = 0.0

    def switch_to_mode(self, new_mode: ControllerMode, current_time: float) -> None:
        """Switch to a new mode, preserving current position."""
        if new_mode == self.current_mode:
            return

        # Save current position for current mode
        self.save_current_position()

        # Switch to new mode
        self.current_mode = new_mode
        self.mode_history.append(new_mode)
        self.last_mode_switch_time = current_time

        # Limit history size
        if len(self.mode_history) > MAX_MODE_HISTORY_SIZE:
            self.mode_history = self.mode_history[-MAX_MODE_HISTORY_SIZE:]

    def save_current_position(
        self, position: tuple[int, int] = None, frame: int = None, animation: str = None
    ) -> None:
        """Save current position for the current mode."""
        if position is not None:
            self.mode_positions[self.current_mode].position = position
        if frame is not None:
            self.mode_positions[self.current_mode].frame = frame
        if animation is not None:
            self.mode_positions[self.current_mode].animation = animation
        self.mode_positions[self.current_mode].is_valid = True

    def get_current_position(self) -> ModePosition:
        """Get position information for current mode.

        Returns:
            ModePosition: The current position.

        """
        return self.mode_positions[self.current_mode]

    def get_position_for_mode(self, mode: ControllerMode) -> ModePosition:
        """Get position information for a specific mode.

        Returns:
            ModePosition: The position for mode.

        """
        return self.mode_positions[mode]

    def get_location_type(self) -> LocationType:
        """Get the LocationType corresponding to current mode.

        Returns:
            LocationType: The location type.

        """
        if self.current_mode == ControllerMode.FILM_STRIP:
            return LocationType.FILM_STRIP
        if self.current_mode == ControllerMode.CANVAS:
            return LocationType.CANVAS
        if self.current_mode in [
            ControllerMode.R_SLIDER,
            ControllerMode.G_SLIDER,
            ControllerMode.B_SLIDER,
        ]:
            return LocationType.SLIDER
        return LocationType.FILM_STRIP


class TriggerDetector:
    """Detects analog trigger presses for mode switching."""

    TRIGGER_THRESHOLD = 0.4  # Lowered from 0.5 to accommodate Linux trigger values
    DEBOUNCE_TIME = 0.1  # 100ms debounce

    def __init__(self):
        """Initialize the trigger detector with empty state tracking."""
        self.last_trigger_states: dict[int, dict[str, float]] = {}
        self.last_trigger_times: dict[int, dict[str, float]] = {}

    def detect_trigger_press(
        self, controller_id: int, trigger_value: float, trigger_type: str, current_time: float
    ) -> bool:
        """Detect if a trigger was pressed (crossed threshold).

        Args:
            controller_id: Controller ID
            trigger_value: Current trigger value (0.0 to 1.0)
            trigger_type: 'L2' or 'R2'
            current_time: Current time in seconds

        Returns:
            True if trigger was pressed (crossed threshold)

        """
        # Initialize controller state if needed
        if controller_id not in self.last_trigger_states:
            self.last_trigger_states[controller_id] = {"L2": 0.0, "R2": 0.0}
            self.last_trigger_times[controller_id] = {"L2": 0.0, "R2": 0.0}

        # Check if trigger crossed threshold
        last_value = self.last_trigger_states[controller_id][trigger_type]
        crossed_threshold = (
            last_value < self.TRIGGER_THRESHOLD and trigger_value >= self.TRIGGER_THRESHOLD
        )

        # Update state - always update the trigger state
        self.last_trigger_states[controller_id][trigger_type] = trigger_value

        # Check debounce only for threshold crossings
        if crossed_threshold:
            time_since_last = current_time - self.last_trigger_times[controller_id][trigger_type]
            if time_since_last < self.DEBOUNCE_TIME:
                return False
            self.last_trigger_times[controller_id][trigger_type] = current_time

        return crossed_threshold

    def get_trigger_state(self, controller_id: int, trigger_type: str) -> float:
        """Get current trigger state for a controller.

        Returns:
            float: The trigger state.

        """
        if controller_id not in self.last_trigger_states:
            return 0.0
        return self.last_trigger_states[controller_id].get(trigger_type, 0.0)


class ModeSwitcher:
    """Handles mode switching for controllers."""

    def __init__(self):
        """Initialize the mode switcher with empty controller mode tracking."""
        self.controller_modes: dict[int, ControllerModeState] = {}
        self.trigger_detector = TriggerDetector()
        # R2 cycle: B -> G -> R -> canvas -> film strip
        self.r2_cycle = [
            ControllerMode.B_SLIDER,
            ControllerMode.G_SLIDER,
            ControllerMode.R_SLIDER,
            ControllerMode.CANVAS,
            ControllerMode.FILM_STRIP,
        ]
        # L2 cycle: film strip -> canvas -> R -> G -> B
        self.l2_cycle = [
            ControllerMode.FILM_STRIP,
            ControllerMode.CANVAS,
            ControllerMode.R_SLIDER,
            ControllerMode.G_SLIDER,
            ControllerMode.B_SLIDER,
        ]

    def register_controller(
        self, controller_id: int, initial_mode: ControllerMode = ControllerMode.CANVAS
    ) -> None:
        """Register a new controller with mode state."""
        self.controller_modes[controller_id] = ControllerModeState(controller_id, initial_mode)

    def unregister_controller(self, controller_id: int) -> None:
        """Unregister a controller."""
        if controller_id in self.controller_modes:
            del self.controller_modes[controller_id]

    def get_controller_mode(self, controller_id: int) -> ControllerMode | None:
        """Get current mode for a controller.

        Returns:
            ControllerMode | None: The controller mode.

        """
        if controller_id in self.controller_modes:
            return self.controller_modes[controller_id].current_mode
        return None

    def get_controller_location_type(self, controller_id: int) -> LocationType | None:
        """Get LocationType for a controller's current mode.

        Returns:
            LocationType | None: The controller location type.

        """
        if controller_id in self.controller_modes:
            return self.controller_modes[controller_id].get_location_type()
        return None

    def handle_trigger_input(
        self, controller_id: int, l2_value: float, r2_value: float, current_time: float
    ) -> ControllerMode | None:
        """Handle trigger input and return new mode if switched.

        Args:
            controller_id: Controller ID
            l2_value: L2 trigger value (0.0 to 1.0)
            r2_value: R2 trigger value (0.0 to 1.0)
            current_time: Current time in seconds

        Returns:
            New mode if switched, None otherwise

        """
        if controller_id not in self.controller_modes:
            return None

        # Check for trigger presses
        l2_pressed = self.trigger_detector.detect_trigger_press(
            controller_id, l2_value, "L2", current_time
        )
        r2_pressed = self.trigger_detector.detect_trigger_press(
            controller_id, r2_value, "R2", current_time
        )

        if not (l2_pressed or r2_pressed):
            return None

        # Determine new mode
        current_mode = self.controller_modes[controller_id].current_mode

        # Special case: R2 on film strip does nothing
        if r2_pressed and current_mode == ControllerMode.FILM_STRIP:
            return None

        if l2_pressed:  # L2 cycle: film strip -> canvas -> R -> G -> B
            if current_mode not in self.l2_cycle:
                return None
            current_index = self.l2_cycle.index(current_mode)
            new_index = (current_index + 1) % len(self.l2_cycle)
            new_mode = self.l2_cycle[new_index]
        else:  # R2 cycle: B -> G -> R -> canvas -> film strip
            if current_mode not in self.r2_cycle:
                return None
            current_index = self.r2_cycle.index(current_mode)
            new_index = (current_index + 1) % len(self.r2_cycle)
            new_mode = self.r2_cycle[new_index]

        # Switch mode
        self.controller_modes[controller_id].switch_to_mode(new_mode, current_time)

        return new_mode

    def save_controller_position(
        self,
        controller_id: int,
        position: tuple[int, int],
        frame: int = None,
        animation: str = None,
    ) -> None:
        """Save current position for a controller's current mode."""
        if controller_id in self.controller_modes:
            self.controller_modes[controller_id].save_current_position(position, frame, animation)

    def get_controller_position(self, controller_id: int) -> ModePosition | None:
        """Get current position for a controller's current mode.

        Returns:
            ModePosition | None: The controller position.

        """
        if controller_id in self.controller_modes:
            return self.controller_modes[controller_id].get_current_position()
        return None

    def get_all_controller_modes(self) -> dict[int, ControllerMode]:
        """Get all controller modes.

        Returns:
            dict[int, ControllerMode]: The all controller modes.

        """
        return {cid: mode_state.current_mode for cid, mode_state in self.controller_modes.items()}

    def get_controllers_in_mode(self, mode: ControllerMode) -> list[int]:
        """Get all controllers currently in a specific mode.

        Returns:
            list[int]: The controllers in mode.

        """
        return [
            cid
            for cid, mode_state in self.controller_modes.items()
            if mode_state.current_mode == mode
        ]
