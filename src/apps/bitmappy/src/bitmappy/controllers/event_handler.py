"""Controller and joystick event handling for the Bitmappy editor.

Manages all controller/joystick input, multi-controller support, visual indicators,
continuous movement, and mode switching. Extracted from BitmapEditorScene to reduce
class complexity.

Domain-specific operations are provided by composition delegates:
- CanvasOperations: Canvas painting, erasing, movement, line drawing
- SliderOperations: Slider navigation and value adjustment
- VisualIndicators: Visual indicator rendering and collision avoidance
- FilmStripOperations: Film strip navigation and frame selection
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pygame

from bitmappy.constants import (
    HAT_INPUT_MAGNITUDE_THRESHOLD,
    JOYSTICK_HAT_DOWN,
    JOYSTICK_HAT_LEFT,
    JOYSTICK_HAT_RIGHT,
    JOYSTICK_HAT_UP,
    JOYSTICK_LEFT_SHOULDER_BUTTON,
)
from bitmappy.controllers.canvas_operations import CanvasOperations
from bitmappy.controllers.film_strip_operations import FilmStripOperations
from bitmappy.controllers.modes import ControllerMode
from bitmappy.controllers.selection import (
    ControllerSelection,
)
from bitmappy.controllers.slider_operations import SliderOperations
from bitmappy.controllers.visual_indicators import VisualIndicators
from glitchygames import (
    clock,
    events,
)
from glitchygames.input.state import current_input

if TYPE_CHECKING:
    from bitmappy.controllers.manager import ControllerInfo
    from bitmappy.protocols import EditorContext
    from glitchygames.sprites import BitmappySprite

# The hat positions that name a direction (diagonals name none)
HAT_DIRECTION_NAMES: dict[tuple[int, int], str] = {
    JOYSTICK_HAT_UP: 'up',
    JOYSTICK_HAT_RIGHT: 'right',
    JOYSTICK_HAT_DOWN: 'down',
    JOYSTICK_HAT_LEFT: 'left',
}


class ControllerEventHandler:  # ruff: ignore[too-many-public-methods]
    """Manages controller/joystick event handling for the Bitmappy editor.

    Handles all controller input, multi-controller support, visual indicators,
    continuous movement, and mode switching. Operates on editor state via
    the editor reference passed at construction time.

    Domain-specific operations are provided by composition delegates:
    - canvas: Canvas painting, erasing, movement, line drawing
    - slider: Slider navigation and value adjustment
    - indicators: Visual indicator rendering and collision avoidance
    - film_strip: Film strip navigation and frame selection
    """

    def __init__(self, editor: EditorContext) -> None:
        """Initialize the ControllerEventHandler.

        Args:
            editor: The editor context providing access to shared state.

        """
        self.editor = editor
        self.log = logging.getLogger('game.tools.bitmappy.controllers.event_handler')
        self.log.addHandler(logging.NullHandler())

        # Controller-specific state
        self.controller_drags: dict[int, dict[str, Any]] = {}
        self.slider_continuous_adjustments: dict[int, dict[str, Any]] = {}
        self.canvas_continuous_movements: dict[int, dict[str, Any]] = {}
        self.slider_indicator_sprites: dict[int, Any] = {}
        self.slider_indicators: dict[int, BitmappySprite] = {}
        self.film_strip_controller_selections: dict[str, Any] = {}

        # Axis tracking state
        self._controller_axis_deadzone = 500
        self._controller_axis_hat_threshold = 500
        self._controller_axis_last_values: dict[tuple[int, int], float] = {}
        self._controller_axis_cooldown: dict[tuple[int, int], float] = {}
        self._controller_axis_cooldown_duration = 0.2

        # Composition delegates
        self.canvas = CanvasOperations(handler=self)
        self.slider = SliderOperations(handler=self)
        self.indicators = VisualIndicators(handler=self)
        self.film_strip = FilmStripOperations(handler=self)

    # ──────────────────────────────────────────────────────────────────────
    # Public interface for editor delegation
    # ──────────────────────────────────────────────────────────────────────

    def render_visual_indicators(self) -> None:
        """Render visual indicators (called from editor render)."""
        self.indicators.render_visual_indicators()

    def update_continuous_movements(self) -> None:
        """Update continuous canvas movements (called from editor update)."""
        self.canvas.update_canvas_continuous_movements()

    def update_continuous_adjustments(self) -> None:
        """Update continuous slider adjustments (called from editor update)."""
        self.slider.update_slider_continuous_adjustments()

    # ──────────────────────────────────────────────────────────────────────
    # Public delegation to canvas operations
    # ──────────────────────────────────────────────────────────────────────

    def handle_controller_drag_end(self, controller_id: int) -> None:
        """Handle the end of a controller drag operation."""
        self.canvas.handle_controller_drag_end(controller_id)

    def canvas_paint_at_controller_position(
        self,
        controller_id: int,
        *,
        force: bool = False,
    ) -> None:
        """Paint at the controller's current canvas position."""
        self.canvas.canvas_paint_at_controller_position(controller_id, force=force)

    def start_canvas_continuous_movement(
        self,
        controller_id: int,
        dx: int,
        dy: int,
    ) -> None:
        """Start continuous canvas movement with acceleration."""
        self.canvas.start_canvas_continuous_movement(controller_id, dx, dy)

    def stop_canvas_continuous_movement(self, controller_id: int) -> None:
        """Stop continuous canvas movement."""
        self.canvas.stop_canvas_continuous_movement(controller_id)

    def canvas_paint_horizontal_line(self, controller_id: int, distance: int) -> None:
        """Paint a horizontal line of pixels starting from the controller's current position."""
        self.canvas.canvas_paint_horizontal_line(controller_id, distance)

    def canvas_paint_vertical_line(self, controller_id: int, distance: int) -> None:
        """Paint a vertical line of pixels starting from the controller's current position."""
        self.canvas.canvas_paint_vertical_line(controller_id, distance)

    def canvas_jump_horizontal(self, controller_id: int, distance: int) -> None:
        """Jump horizontally without painting pixels."""
        self.canvas.canvas_jump_horizontal(controller_id, distance)

    def canvas_jump_vertical(self, controller_id: int, distance: int) -> None:
        """Jump vertically without painting pixels."""
        self.canvas.canvas_jump_vertical(controller_id, distance)

    # ──────────────────────────────────────────────────────────────────────
    # Public delegation to slider operations
    # ──────────────────────────────────────────────────────────────────────

    def handle_slider_mode_navigation(
        self,
        direction: str,
        controller_id: int | None = None,
    ) -> None:
        """Handle arrow key navigation between slider modes."""
        self.slider.handle_slider_mode_navigation(direction, controller_id)

    def start_slider_continuous_adjustment(
        self,
        controller_id: int,
        direction: int,
    ) -> None:
        """Start continuous slider adjustment with acceleration."""
        self.slider.start_slider_continuous_adjustment(controller_id, direction)

    def stop_slider_continuous_adjustment(self, controller_id: int) -> None:
        """Stop continuous slider adjustment."""
        self.slider.stop_slider_continuous_adjustment(controller_id)

    # ──────────────────────────────────────────────────────────────────────
    # Public delegation to visual indicators
    # ──────────────────────────────────────────────────────────────────────

    def update_controller_visual_indicator_for_mode(
        self,
        controller_id: int,
        new_mode: ControllerMode,
    ) -> None:
        """Update visual indicator for controller's new mode."""
        self.indicators.update_controller_visual_indicator_for_mode(controller_id, new_mode)

    def update_controller_canvas_visual_indicator(self, controller_id: int) -> None:
        """Update the visual indicator for a controller's canvas position."""
        self.indicators.update_controller_canvas_visual_indicator(controller_id)

    # ──────────────────────────────────────────────────────────────────────
    # Public delegation to film strip operations
    # ──────────────────────────────────────────────────────────────────────

    def multi_controller_activate(self, controller_id: int) -> None:
        """Activate a controller for navigation."""
        self.film_strip.multi_controller_activate(controller_id)

    def multi_controller_previous_frame(self, controller_id: int) -> None:
        """Move to previous frame for a controller."""
        self.film_strip.multi_controller_previous_frame(controller_id)

    def multi_controller_next_frame(self, controller_id: int) -> None:
        """Move to next frame for a controller."""
        self.film_strip.multi_controller_next_frame(controller_id)

    def multi_controller_previous_animation(self, controller_id: int) -> None:
        """Move to previous animation for a controller."""
        self.film_strip.multi_controller_previous_animation(controller_id)

    def multi_controller_next_animation(self, controller_id: int) -> None:
        """Move to next animation for a controller."""
        self.film_strip.multi_controller_next_animation(controller_id)

    def multi_controller_select_current_frame(self, controller_id: int) -> None:
        """Select the current frame that the controller is pointing to."""
        self.film_strip.multi_controller_select_current_frame(controller_id)

    def multi_controller_toggle_onion_skinning(self, controller_id: int) -> None:
        """Toggle onion skinning for the controller's selected frame."""
        self.film_strip.multi_controller_toggle_onion_skinning(controller_id)

    def multi_controller_toggle_selected_frame_visibility(self, controller_id: int) -> None:
        """Toggle visibility of the selected frame on the canvas for comparison."""
        self.film_strip.multi_controller_toggle_selected_frame_visibility(controller_id)

    def reinitialize_multi_controller_system(
        self,
        preserved_controller_selections: dict[int, tuple[str, int]] | None = None,
    ) -> None:
        """Reinitialize the multi-controller system when film strips are reconstructed."""
        self.film_strip.reinitialize_multi_controller_system(preserved_controller_selections)

    # ──────────────────────────────────────────────────────────────────────
    # Core controller event dispatch
    # ──────────────────────────────────────────────────────────────────────

    def on_controller_button_down_event(self, event: events.ControllerButtonEvent) -> None:
        """Handle controller button down events for multi-controller system.

        Args:
            event (ControllerButtonEvent): The controller button down event.

        """
        # Scan for controllers and update manager
        self.editor.multi_controller_manager.scan_for_controllers()

        # Get controller info
        instance_id = event.instance_id
        controller_info = self.editor.multi_controller_manager.get_controller_info(instance_id)

        if not controller_info:
            return

        self.log.debug('Controller button down: %s', event.button)

        # Handle controller assignment on first button press
        if controller_info.status.value == 'connected':
            controller_id = self.editor.multi_controller_manager.assign_controller(instance_id)
            # A known, connected controller is always assigned
            assert controller_id is not None
            # Create controller selection for this controller
            self.editor.controller_selections[controller_id] = ControllerSelection(
                controller_id,
                instance_id,
            )

        # Get controller ID for this instance
        controller_id = self.editor.multi_controller_manager.get_controller_id(instance_id)
        if controller_id is None:
            return

        # Get or create controller selection
        if controller_id not in self.editor.controller_selections:
            self.editor.controller_selections[controller_id] = ControllerSelection(
                controller_id,
                instance_id,
            )

        controller_selection = self.editor.controller_selections[controller_id]

        # Update controller activity
        self.editor.multi_controller_manager.update_controller_activity(instance_id)
        controller_selection.update_activity()

        # Handle button presses

        # Dispatch to mode-specific strategy
        strategy = self.editor.mode_switcher.get_strategy(controller_id)
        if strategy is not None:
            strategy.handle_button_down(controller_id, event.button)
        else:
            # Fallback for controllers without a registered mode
            self.log.debug('Controller %s: no strategy found, skipping button press', controller_id)

    def on_controller_button_up_event(self, event: events.ControllerButtonEvent) -> None:
        """Handle controller button up events.

        Args:
            event (ControllerButtonEvent): The controller button up event.

        """
        instance_id = event.instance_id

        # Get controller ID for this instance
        controller_id = self.editor.multi_controller_manager.get_controller_id(instance_id)
        if controller_id is None:
            return

        # Dispatch to mode-specific strategy for button release
        strategy = self.editor.mode_switcher.get_strategy(controller_id)
        if strategy is not None:
            strategy.handle_button_up(controller_id, event.button)

    # ──────────────────────────────────────────────────────────────────────
    # Joystick event handling
    # ──────────────────────────────────────────────────────────────────────

    def on_joy_button_down_event(self, event: events.JoyButtonEvent) -> None:
        """Handle joystick button down events (for controllers detected as joysticks).

        Args:
            event (JoyButtonEvent): The joystick button down event.

        """
        # Map joystick buttons to controller actions
        # Button 9 is likely LEFT SHOULDER button, not START
        if event.button == JOYSTICK_LEFT_SHOULDER_BUTTON:
            # Left shoulder button: Currently unhandled to prevent reset behavior
            pass
        elif event.button == 0:  # A button
            # Use new multi-controller system instead of old single-controller system
            controller_id = getattr(event, 'instance_id', 0)
            self.multi_controller_select_current_frame(controller_id)
        elif event.button == 1:  # B button
            self.film_strip.controller_cancel()
        else:
            # Unknown joystick button - not handled
            pass

    def on_joy_button_up_event(self, event: events.JoyButtonEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (JoyButtonEvent): The joystick button up event.

        """

    def on_joy_hat_motion_event(self, event: events.JoyHatEvent) -> None:
        """Handle joystick hat motion events - requires threshold to prevent jittery behavior.

        Args:
            event (JoyHatEvent): The joystick hat motion event.

        """
        self.log.debug('DEBUG: Joystick hat motion: hat=%s, value=%s', event.hat, event.value)

        # Only respond to strong hat inputs (threshold > 0.5). pygame reports a hat's position
        # as an (x, y) tuple: (0, 0) centered, (0, 1) up, (1, 0) right, (0, -1) down, (-1, 0)
        # left (the directions were compared with integer bitmasks, which never matched)
        hat_x, hat_y = event.value
        hat_magnitude = (hat_x**2 + hat_y**2) ** 0.5
        if hat_magnitude < HAT_INPUT_MAGNITUDE_THRESHOLD:
            self.log.debug('DEBUG: Joystick hat motion below threshold, ignoring')
            return

        # Map hat directions to controller actions: each is disabled (the multi-controller
        # system handles them); a diagonal matches no direction
        direction = HAT_DIRECTION_NAMES.get(event.value)
        if direction is not None:
            self.log.debug(
                'DEBUG: Joystick hat %s - DISABLED (use multi-controller system)', direction
            )

    def on_joy_axis_motion_event(self, event: events.JoyAxisEvent) -> None:
        """Handle joystick axis motion events - disabled to prevent jittery behavior.

        Args:
            event (JoyAxisEvent): The joystick axis motion event.

        """
        # Handle trigger axis motion for mode switching (axes 4 and 5)
        if event.axis in {4, 5}:  # TRIGGERLEFT and TRIGGERRIGHT
            self.log.debug(
                'DEBUG: Trigger axis motion detected: axis=%s, value=%s',
                event.axis,
                event.value,
            )
            self._handle_trigger_axis_motion(event)
            return

        self.log.debug(
            'DEBUG: Joystick axis motion (DISABLED): axis=%s, value=%s',
            event.axis,
            event.value,
        )
        # Disabled to prevent jittery behavior

    def on_joy_ball_motion_event(self, event: events.JoyBallEvent) -> None:
        """Handle joystick ball motion events - disabled to prevent jittery behavior.

        Args:
            event (JoyBallEvent): The joystick ball motion event.

        """
        self.log.debug(
            'DEBUG: Joystick ball motion (DISABLED): ball=%s, rel=%s',
            event.ball,
            event.rel,
        )
        # Disabled to prevent jittery behavior

    # ──────────────────────────────────────────────────────────────────────
    # Controller axis motion
    # ──────────────────────────────────────────────────────────────────────

    def on_controller_axis_motion_event(self, event: events.ControllerAxisEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (ControllerAxisEvent): The controller axis motion event.

        """
        # Handle trigger axis motion for mode switching
        if event.axis in {pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT}:
            self._handle_trigger_axis_motion(event)
            return

        # Stick axis motion disabled to prevent jittery behavior.
        # Re-enable by calling self._handle_stick_axis_motion(event) here.
        return

    def _handle_stick_axis_motion(self, event: events.HashableEvent) -> None:
        """Handle stick axis motion events (currently disabled).

        Args:
            event (pygame.event.Event): The controller axis motion event.

        """
        self.log.debug('DEBUG: Controller axis motion: axis=%s, value=%s', event.axis, event.value)
        self.log.debug('DEBUG: LEFT_X axis constant: %s', pygame.CONTROLLER_AXIS_LEFTX)
        self.log.debug('DEBUG: LEFT_Y axis constant: %s', pygame.CONTROLLER_AXIS_LEFTY)
        self.log.debug('DEBUG: RIGHT_X axis constant: %s', pygame.CONTROLLER_AXIS_RIGHTX)
        self.log.debug('DEBUG: RIGHT_Y axis constant: %s', pygame.CONTROLLER_AXIS_RIGHTY)
        self.log.debug(
            'DEBUG: Controller selection active: %s',
            getattr(self, 'controller_selection_active', False),
        )

        # Left stick for fine frame navigation (only if controller selection is active)
        if not hasattr(self, 'controller_selection_active') or not self.controller_selection_active:  # type: ignore[attr-defined]
            self.log.debug('DEBUG: Controller selection not active, ignoring analog stick input')
            return

        current_time = clock.elapsed_seconds()

        if event.axis == pygame.CONTROLLER_AXIS_LEFTX:
            self._handle_left_stick_x_axis(event, current_time)
        elif event.axis == pygame.CONTROLLER_AXIS_LEFTY:
            self._handle_left_stick_y_axis(event, current_time)

    def _handle_left_stick_x_axis(self, event: events.HashableEvent, current_time: float) -> None:
        """Handle left stick X axis motion.

        Args:
            event: The axis motion event.
            current_time: Current timestamp.

        """
        if not self._check_axis_deadzone_and_cooldown(event, current_time):
            return

        if event.value < -self._controller_axis_hat_threshold:
            self.log.debug('DEBUG: Left stick left - DISABLED (use multi-controller system)')
            return
        if event.value > self._controller_axis_hat_threshold:
            self.log.debug('DEBUG: Left stick right - DISABLED (use multi-controller system)')
            return

        self._controller_axis_last_values[event.axis] = event.value

    def _handle_left_stick_y_axis(self, event: events.HashableEvent, current_time: float) -> None:
        """Handle left stick Y axis motion.

        Args:
            event: The axis motion event.
            current_time: Current timestamp.

        """
        if not self._check_axis_deadzone_and_cooldown(event, current_time):
            return

        if event.value < -self._controller_axis_hat_threshold:
            self.log.debug('DEBUG: Left stick up - DISABLED (use multi-controller system)')
            return
        if event.value > self._controller_axis_hat_threshold:
            self.log.debug('DEBUG: Left stick down - DISABLED (use multi-controller system)')
            return

        self._controller_axis_last_values[event.axis] = event.value

    def _check_axis_deadzone_and_cooldown(
        self,
        event: events.HashableEvent,
        current_time: float,
    ) -> bool:
        """Check deadzone, cooldown, and direction change for an axis event.

        Args:
            event: The axis motion event.
            current_time: Current timestamp.

        Returns:
            True if the event should be processed, False if it should be ignored.

        """
        # Apply deadzone
        if abs(event.value) < self._controller_axis_deadzone:
            # No cooldown (-inf), whatever elapsed_seconds() reads (the frame clock)
            self._controller_axis_cooldown[event.axis] = float('-inf')
            self._controller_axis_last_values[event.axis] = 0
            return False

        # Check cooldown
        if (
            event.axis in self._controller_axis_cooldown
            and current_time - self._controller_axis_cooldown[event.axis]
            < self._controller_axis_cooldown_duration
        ):
            return False

        # Check if direction changed (prevents rapid back-and-forth)
        last_value = self._controller_axis_last_values.get(event.axis, 0)
        if (last_value < 0 and event.value > 0) or (last_value > 0 and event.value < 0):
            self._controller_axis_cooldown[event.axis] = current_time
            self._controller_axis_last_values[event.axis] = event.value
            return False

        return True

    # ──────────────────────────────────────────────────────────────────────
    # Trigger handling
    # ──────────────────────────────────────────────────────────────────────

    def _handle_trigger_axis_motion(self, event: events.HashableEvent) -> None:
        """Handle trigger axis motion for mode switching.

        Args:
            event (pygame.event.Event): The controller/joystick axis motion event.

        """
        controller_id = self._get_controller_id_from_event(event)
        if controller_id is None:
            self.log.debug('DEBUG: No controller ID found for event')
            return

        # Register controller with mode switcher if not already registered
        if controller_id not in self.editor.mode_switcher.controller_modes:
            self.editor.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
            self.log.debug('DEBUG: Registered controller %s with mode switcher', controller_id)

        current_time = clock.elapsed_seconds()

        l2_value, r2_value = self._read_trigger_values(event, controller_id)

        # Read the mode before handle_trigger_input switches it, so undo can restore it
        # (BUGS.md #95)
        old_mode = self.editor.mode_switcher.get_controller_mode(controller_id)

        # Handle mode switching
        new_mode = self.editor.mode_switcher.handle_trigger_input(
            controller_id,
            l2_value,
            r2_value,
            current_time,
        )

        if new_mode:
            self.log.debug(
                'DEBUG: Controller %s switched to mode: %s', controller_id, new_mode.value
            )
            self._track_controller_mode_change(controller_id, new_mode, old_mode=old_mode)
            self.indicators.update_controller_visual_indicator_for_mode(controller_id, new_mode)
        else:
            self.log.debug(
                'DEBUG: No mode switch for controller %s - L2: %.2f, R2: %.2f',
                controller_id,
                l2_value,
                r2_value,
            )

    def _get_controller_id_from_event(self, event: events.HashableEvent) -> int | None:
        """Extract the controller ID from a controller or joystick event.

        Args:
            event: The pygame event.

        Returns:
            The controller ID, or None if not found.

        """
        if hasattr(event, 'instance_id') and event.instance_id is not None:
            instance_id = event.instance_id
            controller_id = self.editor.multi_controller_manager.get_controller_id(instance_id)
            self.log.debug(
                'DEBUG: Controller event - instance_id=%s, controller_id=%s',
                instance_id,
                controller_id,
            )
            return controller_id

        # Joystick event - use device index directly
        device_index = event.joy
        self.log.debug(
            'DEBUG: Joystick event - using device index %s as controller ID %s',
            device_index,
            device_index,
        )
        return device_index

    def _read_trigger_values(
        self,
        event: events.HashableEvent,
        controller_id: int,
    ) -> tuple[float, float]:
        """Read L2 and R2 trigger values from a controller or joystick event.

        Args:
            event: The pygame event.
            controller_id: The controller ID.

        Returns:
            Tuple of (l2_value, r2_value) normalized to 0.0..1.0 range.

        """
        if hasattr(event, 'instance_id'):
            return self._read_controller_trigger_values(event, controller_id)
        return self._read_joystick_trigger_values(event, controller_id)

    def _read_controller_trigger_values(
        self,
        event: events.HashableEvent,
        controller_id: int,
    ) -> tuple[float, float]:
        """Read trigger values from a controller event.

        Args:
            event: The pygame controller event.
            controller_id: The controller ID.

        Returns:
            Tuple of (l2_value, r2_value) normalized to 0.0..1.0 range.

        """
        if not hasattr(self.editor, 'multi_controller_manager'):
            return 0.0, 0.0

        controller_info = self.editor.multi_controller_manager.get_controller_info(
            event.instance_id,
        )
        self.log.debug(
            'DEBUG: Controller info lookup - instance_id=%s, controller_info=%s',
            event.instance_id,
            controller_info,
        )
        if not controller_info:
            self.log.debug('DEBUG: No controller info found for instance_id=%s', event.instance_id)
            return 0.0, 0.0

        # The frame's input snapshot (glitchygames/input/state.py) holds the joystick-layer
        # axes by instance id. (This used to open a pygame joystick with the event's instance
        # id, but pygame's joystick constructor takes a device index, which differs from the
        # instance id after a reconnect, so it read the wrong device or raised pygame.error.)
        snapshot = current_input()
        # Convert pygame trigger values (-1.0 to 1.0) to our expected range (0.0 to 1.0)
        l2_raw = snapshot.axis(device_id=event.instance_id, axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT)
        r2_raw = snapshot.axis(
            device_id=event.instance_id, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT
        )
        l2_value = (l2_raw + 1.0) / 2.0
        r2_value = (r2_raw + 1.0) / 2.0
        self.log.debug(
            'DEBUG: Controller %s triggers - L2: %.2f, R2: %.2f',
            controller_id,
            l2_value,
            r2_value,
        )
        return l2_value, r2_value

    def _read_joystick_trigger_values(
        self,
        event: events.HashableEvent,
        controller_id: int,
    ) -> tuple[float, float]:
        """Read trigger values from a joystick event.

        Args:
            event: The pygame joystick event.
            controller_id: The controller ID.

        Returns:
            Tuple of (l2_value, r2_value) normalized to 0.0..1.0 range.

        """
        self.log.debug(
            'DEBUG: Processing joystick event for controller %s, joy=%s',
            controller_id,
            event.joy,
        )
        # The frame's input snapshot (glitchygames/input/state.py), never the device mid-frame.
        # Only events without an instance id come here (_read_trigger_values), so ``joy`` is
        # the only id they carry.
        snapshot = current_input()
        l2_raw = snapshot.axis(device_id=event.joy, axis=4)  # TRIGGERLEFT
        r2_raw = snapshot.axis(device_id=event.joy, axis=5)  # TRIGGERRIGHT

        # Convert pygame 2's joystick axis values (-1.0 to 1.0) to 0.0..1.0, as the controller
        # path does (this used pygame 1's -32768..32767 scale, so every position read about 0.5:
        # BUGS.md #67)
        l2_value = max(0.0, min(1.0, (l2_raw + 1.0) / 2.0))
        r2_value = max(0.0, min(1.0, (r2_raw + 1.0) / 2.0))

        self.log.debug(
            'DEBUG: Joystick %s raw values - L2: %.2f, R2: %.2f',
            controller_id,
            l2_raw,
            r2_raw,
        )
        self.log.debug(
            'DEBUG: Joystick %s triggers - L2: %.2f, R2: %.2f',
            controller_id,
            l2_value,
            r2_value,
        )
        return l2_value, r2_value

    def _track_controller_mode_change(
        self,
        controller_id: int,
        new_mode: ControllerMode,
        *,
        old_mode: ControllerMode | None = None,
    ) -> None:
        """Track a controller mode change for undo/redo.

        Args:
            controller_id: The controller ID.
            new_mode: The new ControllerMode.
            old_mode: The mode switched from. A caller that has already switched the mode
                must pass it (BUGS.md #95); when None, the controller's current mode is read,
                which is right only before the switch.

        """
        if getattr(self, 'applying_undo_redo', False):
            return
        if not hasattr(self.editor, 'controller_position_operation_tracker'):
            return

        if old_mode is None:
            old_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
        if old_mode:
            self.editor.controller_position_operation_tracker.add_controller_mode_change(
                controller_id,
                old_mode.value,
                new_mode.value,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Utility methods
    # ──────────────────────────────────────────────────────────────────────

    def is_controller_button_held(self, controller_id: int, button: int) -> bool:
        """Check if a controller button is currently held down.

        Reads the frame's input snapshot (glitchygames/input/state.py) by the controller's
        instance id. (This used to open a pygame joystick with the controller id, but the
        controller id is Bitmappy's slot number, not a device index.)

        Args:
            controller_id: Bitmappy's controller slot.
            button: The joystick button index.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        controller_info = self.find_controller_info(controller_id)
        if controller_info is None:
            return False
        return current_input().button(device_id=controller_info.instance_id, button=button)

    def find_controller_info(self, controller_id: int) -> ControllerInfo | None:
        """Find controller info by controller ID.

        This method is public because it is used by composition delegates
        that need to look up controller info.

        Args:
            controller_id: The controller ID to look up.

        Returns:
            The controller info object, or None if not found.

        """
        if not hasattr(self.editor, 'multi_controller_manager'):
            return None

        for info in self.editor.multi_controller_manager.controllers.values():
            if info.controller_id == controller_id:
                return info
        return None
