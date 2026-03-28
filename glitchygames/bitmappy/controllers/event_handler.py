"""Controller and joystick event handling for the Bitmappy editor.

Manages all controller/joystick input, multi-controller support, visual indicators,
continuous movement, and mode switching. Extracted from BitmapEditorScene to reduce
class complexity.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import pygame

from glitchygames import events
from glitchygames.bitmappy.constants import (
    CONTROLLER_ACCEL_LEVEL1_TIME,
    CONTROLLER_ACCEL_LEVEL2_TIME,
    CONTROLLER_ACCEL_LEVEL3_TIME,
    HAT_INPUT_MAGNITUDE_THRESHOLD,
    JOYSTICK_HAT_DOWN,
    JOYSTICK_HAT_LEFT,
    JOYSTICK_HAT_RIGHT,
    JOYSTICK_LEFT_SHOULDER_BUTTON,
)
from glitchygames.bitmappy.controllers.modes import ControllerMode
from glitchygames.bitmappy.controllers.selection import ControllerSelection
from glitchygames.sprites import BitmappySprite

if TYPE_CHECKING:
    from glitchygames.bitmappy.indicators import VisualIndicator
    from glitchygames.bitmappy.protocols import EditorContext


class ControllerEventHandler:  # noqa: PLR0904
    """Manages controller/joystick event handling for the Bitmappy editor.

    Handles all controller input, multi-controller support, visual indicators,
    continuous movement, and mode switching. Operates on editor state via
    the editor reference passed at construction time.
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
        self.canvas_controller_indicators: list[dict[str, Any]] = []

        # Axis tracking state
        self._controller_axis_deadzone = 500
        self._controller_axis_hat_threshold = 500
        self._controller_axis_last_values: dict[tuple[int, int], float] = {}
        self._controller_axis_cooldown: dict[tuple[int, int], float] = {}
        self._controller_axis_cooldown_duration = 0.2

    # ──────────────────────────────────────────────────────────────────────
    # Public interface for editor delegation
    # ──────────────────────────────────────────────────────────────────────

    def render_visual_indicators(self) -> None:
        """Render visual indicators (called from editor render)."""
        self._render_visual_indicators()

    def update_continuous_movements(self) -> None:
        """Update continuous canvas movements (called from editor update)."""
        self._update_canvas_continuous_movements()

    def update_continuous_adjustments(self) -> None:
        """Update continuous slider adjustments (called from editor update)."""
        self._update_slider_continuous_adjustments()

    # ──────────────────────────────────────────────────────────────────────
    # Extracted controller event handling methods
    # ──────────────────────────────────────────────────────────────────────

    def on_controller_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle controller button down events for multi-controller system.

        Args:
            event (pygame.event.Event): The controller button down event.

        """
        # Scan for controllers and update manager
        self.editor.multi_controller_manager.scan_for_controllers()

        # Get controller info
        instance_id = event.instance_id
        controller_info = self.editor.multi_controller_manager.get_controller_info(instance_id)

        if not controller_info:
            return

        self.log.debug(f'Controller button down: {event.button}')

        # Handle controller assignment on first button press
        if controller_info.status.value == 'connected':
            controller_id = self.editor.multi_controller_manager.assign_controller(instance_id)
            if controller_id is not None:
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
            self.log.debug(f'Controller {controller_id}: no strategy found, skipping button press')

    def on_controller_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (pygame.event.Event): The controller button up event.

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

    def handle_controller_drag_end(self, controller_id: int) -> None:
        """Handle the end of a controller drag operation.

        Args:
            controller_id: The controller that released the A button.

        """
        if not (hasattr(self, 'controller_drags') and controller_id in self.controller_drags):
            return

        drag_info = self.controller_drags[controller_id]
        if not drag_info['active']:
            return

        # End the drag operation
        drag_info['active'] = False
        drag_info['end_time'] = time.time()
        drag_info['end_position'] = self.editor.mode_switcher.get_controller_position(controller_id)

        self.log.debug(
            f'DEBUG: Controller {controller_id}: Drag operation drew'
            f' {len(drag_info["pixels_drawn"])} pixels',
        )

        if not drag_info['pixels_drawn']:
            return

        self.log.debug(
            f'Controller {controller_id}: Drag operation completed with'
            f' {len(drag_info["pixels_drawn"])} pixels drawn',
        )

        pixel_changes = self._collect_drag_pixel_changes(controller_id, drag_info)
        self._submit_drag_pixel_changes(controller_id, pixel_changes)

    def _collect_drag_pixel_changes(
        self,
        _controller_id: int,
        drag_info: dict[str, Any],
    ) -> list[tuple[int, tuple[int, ...], tuple[int, ...]]]:
        """Collect pixel changes from a drag operation, merging with pending changes.

        Args:
            _controller_id: The controller ID (unused, kept for API consistency).
            drag_info: The drag operation info dict.

        Returns:
            List of (x, y, old_color, new_color) tuples.

        """
        # Convert controller drag pixels to undo/redo format
        pixel_changes: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
        for pixel_info in drag_info['pixels_drawn']:
            position = pixel_info['position']
            color = pixel_info['color']
            old_color = pixel_info.get('old_color', (0, 0, 0))  # Use stored old color
            x, y = position[0], position[1]
            pixel_changes.append((x, y, old_color, color))  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

        # Debug: Show undo stack before merging
        if hasattr(self.editor, 'undo_redo_manager') and self.editor.undo_redo_manager:
            self.log.debug(
                'DEBUG: Undo stack before merging has'
                f' {len(self.editor.undo_redo_manager.undo_stack)} operations',
            )
            for i, op in enumerate(self.editor.undo_redo_manager.undo_stack):
                self.log.debug(f'DEBUG:   Operation {i}: {op.operation_type} - {op.description}')

        # Absorb any pending single pixel operation from canvas interface
        # This merges the initial A button pixel with the drag pixels
        if hasattr(self.editor, 'current_pixel_changes') and self.editor.current_pixel_changes:
            self.log.debug(
                f'DEBUG: Absorbing {len(self.editor.current_pixel_changes)} pending pixel(s)'
                f' from canvas interface',
            )
            self.log.debug(f'DEBUG: Pending pixels: {self.editor.current_pixel_changes}')
            # Add the pending pixels to the beginning of the controller drag pixels
            pixel_changes = self.editor.current_pixel_changes + pixel_changes
            self.log.debug(f'DEBUG: Merged pixel_changes now has {len(pixel_changes)} pixels')
            # Clear the pending pixels to prevent duplicate undo operation
            self.editor.current_pixel_changes = []

            # Remove the old single pixel entry from the undo stack
            # This prevents having two separate undo operations
            if hasattr(self.editor, 'undo_redo_manager') and self.editor.undo_redo_manager:
                if self.editor.undo_redo_manager.undo_stack:
                    removed_operation = self.editor.undo_redo_manager.undo_stack.pop()
                    self.log.debug(
                        'DEBUG: Removed single pixel operation from undo stack:'
                        f' {removed_operation.operation_type}',
                    )
                    self.log.debug(
                        'DEBUG: Undo stack after removal has'
                        f' {len(self.editor.undo_redo_manager.undo_stack)} operations',
                    )
                else:
                    self.log.debug('DEBUG: No operations in undo stack to remove')
        else:
            self.log.debug('DEBUG: No pending pixels to absorb from canvas interface')

        return pixel_changes

    def _submit_drag_pixel_changes(
        self,
        controller_id: int,
        pixel_changes: list[tuple[int, tuple[int, ...], tuple[int, ...]]],
    ) -> None:
        """Submit collected drag pixel changes to the undo/redo system.

        Args:
            controller_id: The controller ID.
            pixel_changes: List of (x, y, old_color, new_color) tuples.

        """
        if not pixel_changes or not hasattr(self.editor, 'canvas_operation_tracker'):
            return

        # Get current frame information for frame-specific tracking
        current_animation = None
        current_frame = None
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            current_animation = getattr(self.editor.canvas, 'current_animation', None)
            current_frame = getattr(self.editor.canvas, 'current_frame', None)

        # Use frame-specific tracking if we have frame information
        if current_animation is not None and current_frame is not None:
            self.editor.canvas_operation_tracker.add_frame_pixel_changes(
                current_animation,
                current_frame,
                pixel_changes,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            )
            self.log.debug(
                f'Controller {controller_id}: Submitted {len(pixel_changes)} pixel'
                f' changes for frame {current_animation}[{current_frame}] undo/redo',
            )
        else:
            # Fall back to global tracking
            self.editor.canvas_operation_tracker.add_pixel_changes(pixel_changes)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            self.log.debug(
                f'Controller {controller_id}: Submitted {len(pixel_changes)} pixel'
                f' changes for global undo/redo',
            )

    def canvas_paint_at_controller_position(
        self,
        controller_id: int,
        *,
        force: bool = False,
    ) -> None:
        """Paint at the controller's current canvas position.

        Args:
            controller_id: The ID of the controller
            force: If True, always paint regardless of current pixel color

        """
        # Get controller's canvas position
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: Controller {controller_id} has no valid canvas position')
            return

        # Get current color from the color picker
        current_color = self.editor.get_current_color()
        self.log.debug(f'DEBUG: canvas_paint_at_controller_position() got color: {current_color}')

        # Check if pixel is already the selected color (debouncing)
        if not force:
            current_pixel_color = self._get_canvas_pixel_color(
                position.position[0],
                position.position[1],
            )
            if current_pixel_color == current_color:
                self.log.debug(
                    f'DEBUG: Pixel at {position.position} is already {current_color}, skipping'
                    f' paint',
                )
                return

        # Get the old color BEFORE changing the pixel for undo functionality
        old_color = self._get_canvas_pixel_color(position.position[0], position.position[1])
        if old_color is None:
            old_color = (0, 0, 0)

        # Paint at the position
        self._set_canvas_pixel(position.position[0], position.position[1], current_color)

        # Track this pixel in the controller drag operation
        self._track_controller_drag_pixel(
            controller_id,
            position.position,
            current_color,
            old_color,
        )

        self.log.debug(
            f'DEBUG: Painted at canvas position {position.position} with color {current_color}',
        )

    def _get_canvas_pixel_color(self, x: int, y: int) -> tuple[int, ...] | None:
        """Get the color of a pixel on the canvas.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            The pixel color tuple, or None if unavailable.

        """
        if not (hasattr(self.editor, 'canvas') and self.editor.canvas):
            return None

        if hasattr(self.editor.canvas, 'canvas_interface'):
            try:
                return self.editor.canvas.canvas_interface.get_pixel_at(x, y)
            except (IndexError, AttributeError, TypeError) as pixel_error:
                self.log.debug(f'Could not get pixel color: {pixel_error}')
                return (0, 0, 0)

        if 0 <= x < self.editor.canvas.pixels_across and 0 <= y < self.editor.canvas.pixels_tall:
            pixel_num = y * self.editor.canvas.pixels_across + x
            return self.editor.canvas.pixels[pixel_num]
        return None

    def _set_canvas_pixel(self, x: int, y: int, color: tuple[int, ...]) -> None:
        """Set a pixel color on the canvas.

        Args:
            x: X coordinate.
            y: Y coordinate.
            color: The color tuple to set.

        """
        if not (hasattr(self.editor, 'canvas') and self.editor.canvas):
            return

        if hasattr(self.editor.canvas, 'canvas_interface'):
            self.editor.canvas.canvas_interface.set_pixel_at(x, y, color)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
        elif 0 <= x < self.editor.canvas.pixels_across and 0 <= y < self.editor.canvas.pixels_tall:
            pixel_num = y * self.editor.canvas.pixels_across + x
            self.editor.canvas.pixels[pixel_num] = color
            self.editor.canvas.dirty_pixels[pixel_num] = True
            self.editor.canvas.dirty = 1

    def _track_controller_drag_pixel(
        self,
        controller_id: int,
        position: tuple[int, int],
        current_color: tuple[int, ...],
        old_color: tuple[int, ...],
    ) -> None:
        """Track a painted pixel in the controller drag operation for undo.

        Args:
            controller_id: The controller ID.
            position: The (x, y) position of the painted pixel.
            current_color: The new color that was painted.
            old_color: The original color before painting.

        """
        if not (hasattr(self, 'controller_drags') and controller_id in self.controller_drags):
            self.log.debug(
                f'DEBUG: No controller drags or controller {controller_id} not in controller_drags',
            )
            return

        drag_info = self.controller_drags[controller_id]
        if not drag_info['active']:
            self.log.debug(f'DEBUG: Controller drag not active for controller {controller_id}')
            return

        pixel_info = {
            'position': position,
            'color': current_color,
            'old_color': old_color,  # Store the original color for undo
            'timestamp': time.time(),
        }
        drag_info['pixels_drawn'].append(pixel_info)
        self.log.debug(
            f'DEBUG: Controller drag tracking pixel at {position}, total'
            f' pixels: {len(drag_info["pixels_drawn"])}',
        )

    def _canvas_erase_at_controller_position(self, controller_id: int) -> None:
        """Erase at the controller's current canvas position."""
        # Get controller's canvas position
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: Controller {controller_id} has no valid canvas position')
            return

        # Erase at the position (paint with background color)
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            background_color = (0, 0, 0)  # Black background
            # Use the canvas interface to set the pixel
            if hasattr(self.editor.canvas, 'canvas_interface'):
                self.editor.canvas.canvas_interface.set_pixel_at(
                    position.position[0],
                    position.position[1],
                    background_color,
                )
            else:
                # Fallback: directly set pixel if interface not available
                x, y = position.position[0], position.position[1]
                if (
                    0 <= x < self.editor.canvas.pixels_across
                    and 0 <= y < self.editor.canvas.pixels_tall
                ):
                    pixel_num = y * self.editor.canvas.pixels_across + x
                    self.editor.canvas.pixels[pixel_num] = background_color
                    self.editor.canvas.dirty_pixels[pixel_num] = True
                    self.editor.canvas.dirty = 1
            self.log.debug(f'DEBUG: Erased at canvas position {position.position}')

    def _canvas_move_cursor(self, controller_id: int, dx: int, dy: int) -> None:
        """Move the controller's canvas cursor."""
        # Get current position
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position:
            # Initialize at (0, 0) if no position
            old_position = (0, 0)
            new_position = (0, 0)
        else:
            old_position = position.position
            new_position = (position.position[0] + dx, position.position[1] + dy)

        # Clamp to canvas bounds
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            canvas_width = getattr(self.editor.canvas, 'width', 32)
            canvas_height = getattr(self.editor.canvas, 'height', 32)
            new_position = (
                max(0, min(canvas_width - 1, new_position[0])),
                max(0, min(canvas_height - 1, new_position[1])),
            )

        # Track controller position change for undo/redo (only if position actually changed and not
        # in continuous movement)
        if (
            old_position != new_position
            and not getattr(self, '_applying_undo_redo', False)
            and not self._is_controller_in_continuous_movement(controller_id)
            and hasattr(self.editor, 'controller_position_operation_tracker')
        ):
            # Get current mode for context
            current_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
            mode_str = current_mode.value if current_mode else None

            self.editor.controller_position_operation_tracker.add_controller_position_change(
                controller_id,
                old_position,
                new_position,
                mode_str,
                mode_str,
            )

        # Update position
        self.editor.mode_switcher.save_controller_position(controller_id, new_position)

        # If controller is in an active drag operation, paint at the new position
        # (the paint method will check if the pixel needs painting)
        if hasattr(self, 'controller_drags') and controller_id in self.controller_drags:
            drag_info = self.controller_drags[controller_id]
            if drag_info['active']:
                self.log.debug(
                    f'DEBUG: Controller {controller_id}: In active drag, painting at new position'
                    f' {new_position}',
                )
                self.canvas_paint_at_controller_position(controller_id)

        # Update visual indicator
        self.update_controller_canvas_visual_indicator(controller_id)

        self.log.debug(f'DEBUG: Controller {controller_id} canvas cursor moved to {new_position}')

    def _is_controller_in_continuous_movement(self, controller_id: int) -> bool:
        """Check if a controller is currently in continuous movement mode.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # Check for canvas continuous movement
        if (
            hasattr(self, 'canvas_continuous_movements')
            and controller_id in self.canvas_continuous_movements
        ):
            return True

        # Check for slider continuous adjustment
        return bool(
            hasattr(self, 'slider_continuous_adjustments')
            and controller_id in self.slider_continuous_adjustments,
        )

    def update_controller_canvas_visual_indicator(self, controller_id: int) -> None:
        """Update the visual indicator for a controller's canvas position."""
        # Get controller info
        controller_info = self.editor.multi_controller_manager.get_controller_info(controller_id)
        if not controller_info:
            return

        # Get current canvas position
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position:
            return

        # Update visual indicator
        if hasattr(self.editor, 'visual_collision_manager'):
            # Remove old indicator
            self.editor.visual_collision_manager.remove_controller_indicator(controller_id)

            # Add new canvas indicator
            from glitchygames.bitmappy.indicators.collision import LocationType

            self.editor.visual_collision_manager.add_controller_indicator(
                controller_id,
                controller_info.instance_id,
                controller_info.color,
                position.position,
                LocationType.CANVAS,
            )

    def handle_slider_mode_navigation(
        self,
        direction: str,
        controller_id: int | None = None,
    ) -> None:
        """Handle arrow key navigation between slider modes."""
        if not hasattr(self.editor, 'mode_switcher'):
            return

        # If no specific controller provided, find the first controller in slider mode (for keyboard
        # navigation)
        if controller_id is None:
            target_controller_id = None
            for cid in self.editor.mode_switcher.controller_modes:
                controller_mode = self.editor.mode_switcher.get_controller_mode(cid)
                if controller_mode and controller_mode.value in {
                    'r_slider',
                    'g_slider',
                    'b_slider',
                }:
                    target_controller_id = cid
                    break
        else:
            # Use the specific controller (for D-pad navigation)
            target_controller_id = controller_id

        if target_controller_id is None:
            return

        current_mode = self.editor.mode_switcher.get_controller_mode(target_controller_id)
        if not current_mode:
            return

        # Define the slider mode cycle
        slider_cycle = [ControllerMode.R_SLIDER, ControllerMode.G_SLIDER, ControllerMode.B_SLIDER]

        # Find current position in cycle
        if current_mode not in slider_cycle:
            return

        current_index = slider_cycle.index(current_mode)

        # Calculate new index based on direction
        if direction == 'up':
            # B -> G -> R
            new_index = (current_index - 1) % len(slider_cycle)
        else:  # direction == "down"
            # R -> G -> B
            new_index = (current_index + 1) % len(slider_cycle)

        new_mode = slider_cycle[new_index]

        # Switch to new mode
        current_time = time.time()
        self.editor.mode_switcher.controller_modes[target_controller_id].switch_to_mode(
            new_mode,
            current_time,
        )

        self.log.debug(
            f'DEBUG: Slider mode navigation - switched controller {target_controller_id} from'
            f' {current_mode.value} to {new_mode.value}',
        )
        self.log.debug(
            f'Slider mode navigation - switched controller {target_controller_id} from'
            f' {current_mode.value} to {new_mode.value}',
        )

    def _slider_adjust_value(self, controller_id: int, delta: int) -> None:
        """Adjust the current slider's value."""
        self.log.debug(
            f'DEBUG: _slider_adjust_value called for controller {controller_id}, delta {delta}',
        )

        # Get the controller's current mode to determine which slider
        if hasattr(self.editor, 'mode_switcher'):
            controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
            self.log.debug(
                f'DEBUG: Controller {controller_id} mode:'
                f' {controller_mode.value if controller_mode else "None"}',
            )

            # Adjust the appropriate slider based on mode
            if controller_mode and controller_mode.value == 'r_slider':
                old_value = self.editor.red_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.log.debug(f'DEBUG: R slider: {old_value} -> {new_value}')
                # Update the slider value
                self.editor.red_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='R', value=new_value)
                self.editor.on_slider_event(events.HashableEvent(0), trigger)
                self.log.debug(f'DEBUG: Adjusted R slider to {new_value}')
            elif controller_mode and controller_mode.value == 'g_slider':
                old_value = self.editor.green_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.log.debug(f'DEBUG: G slider: {old_value} -> {new_value}')
                # Update the slider value
                self.editor.green_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='G', value=new_value)
                self.editor.on_slider_event(events.HashableEvent(0), trigger)
                self.log.debug(f'DEBUG: Adjusted G slider to {new_value}')
            elif controller_mode and controller_mode.value == 'b_slider':
                old_value = self.editor.blue_slider.value
                new_value = max(0, min(255, old_value + delta))
                self.log.debug(f'DEBUG: B slider: {old_value} -> {new_value}')
                # Update the slider value
                self.editor.blue_slider.value = new_value
                # Create a trigger event to properly update the color well
                trigger = events.HashableEvent(0, name='B', value=new_value)
                self.editor.on_slider_event(events.HashableEvent(0), trigger)
                self.log.debug(f'DEBUG: Adjusted B slider to {new_value}')
            else:
                self.log.debug(
                    'DEBUG: No matching slider mode for'
                    f' {controller_mode.value if controller_mode else "None"}',
                )
        else:
            self.log.debug('DEBUG: No mode_switcher found')

    def start_slider_continuous_adjustment(self, controller_id: int, direction: int) -> None:
        """Start continuous slider adjustment with acceleration."""
        # Do the first tick immediately for responsive feel
        self._slider_adjust_value(controller_id, direction)

        # Initialize continuous adjustment for this controller
        # Set last_adjustment to current time so the next adjustment waits for the full interval
        current_time = time.time()
        self.slider_continuous_adjustments[controller_id] = {
            'direction': direction,
            'start_time': current_time,
            'last_adjustment': current_time,
            'acceleration_level': 0,
        }
        self.log.debug(
            f'DEBUG: Started continuous slider adjustment for controller {controller_id}, direction'
            f' {direction} (immediate first tick)',
        )

    def stop_slider_continuous_adjustment(self, controller_id: int) -> None:
        """Stop continuous slider adjustment."""
        if (
            hasattr(self, 'slider_continuous_adjustments')
            and controller_id in self.slider_continuous_adjustments
        ):
            del self.slider_continuous_adjustments[controller_id]
            self.log.debug(
                f'DEBUG: Stopped continuous slider adjustment for controller {controller_id}',
            )

    def _update_slider_continuous_adjustments(self) -> None:
        """Update continuous slider adjustments with acceleration."""
        if not hasattr(self, 'slider_continuous_adjustments'):
            return

        current_time = time.time()

        for controller_id, adjustment_data in list(self.slider_continuous_adjustments.items()):
            # Calculate time since start and since last adjustment
            time_since_start = current_time - adjustment_data['start_time']
            time_since_last = current_time - adjustment_data['last_adjustment']

            # Calculate acceleration level (0-3)
            # 0-0.8s: level 0 (1 tick per 0.15s) - longer delay for precision
            # 0.8-1.5s: level 1 (2 ticks per 0.1s)
            # 1.5-2.5s: level 2 (4 ticks per 0.05s)
            # 2.5s+: level 3 (8 ticks per 0.025s)
            if time_since_start < CONTROLLER_ACCEL_LEVEL1_TIME:
                acceleration_level = 0
                interval = 0.15  # ~6.7 ticks per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL2_TIME:
                acceleration_level = 1
                interval = 0.1  # 10 ticks per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL3_TIME:
                acceleration_level = 2
                interval = 0.05  # 20 ticks per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 ticks per second

            # Update acceleration level if changed
            if acceleration_level != adjustment_data['acceleration_level']:
                adjustment_data['acceleration_level'] = acceleration_level
                self.log.debug(
                    f'DEBUG: Controller {controller_id} slider acceleration level'
                    f' {acceleration_level}',
                )

            # Check if enough time has passed for next adjustment
            if time_since_last >= interval:
                # Calculate delta based on acceleration level (1, 2, 4, 8)
                delta = adjustment_data['direction'] * (2**acceleration_level)
                delta = max(-8, min(8, delta))  # Cap at ±8

                # Apply the adjustment
                self._slider_adjust_value(controller_id, delta)

                # Update color well during continuous adjustment
                controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
                self.log.debug(
                    f'DEBUG: Continuous adjustment - controller {controller_id} mode:'
                    f' {controller_mode.value if controller_mode else "None"}',
                )
                if controller_mode and controller_mode.value in {
                    'r_slider',
                    'g_slider',
                    'b_slider',
                }:
                    self.log.debug(
                        'DEBUG: Calling _update_color_well_from_sliders during continuous '
                        'adjustment',
                    )
                    self.editor.update_color_well_from_sliders()
                else:
                    self.log.debug('DEBUG: Not updating color well - controller not in slider mode')

                # Update last adjustment time
                adjustment_data['last_adjustment'] = current_time

    def start_canvas_continuous_movement(self, controller_id: int, dx: int, dy: int) -> None:
        """Start continuous canvas movement with acceleration."""
        # Do the first movement immediately for responsive feel
        self._canvas_move_cursor(controller_id, dx, dy)

        # Get starting position for undo/redo tracking
        start_position = self.editor.mode_switcher.get_controller_position(controller_id)
        start_x, start_y = start_position.position if start_position else (0, 0)

        # Initialize continuous movement for this controller
        current_time = time.time()
        self.canvas_continuous_movements[controller_id] = {
            'dx': dx,
            'dy': dy,
            'start_time': current_time,
            'last_movement': current_time,
            'acceleration_level': 0,
            'start_x': start_x,
            'start_y': start_y,
        }
        self.log.debug(
            f'DEBUG: Started continuous canvas movement for controller {controller_id}, direction'
            f' ({dx}, {dy}) (immediate first movement)',
        )

    def stop_canvas_continuous_movement(self, controller_id: int) -> None:
        """Stop continuous canvas movement."""
        if (
            hasattr(self, 'canvas_continuous_movements')
            and controller_id in self.canvas_continuous_movements
        ):
            # Track the final position change for undo/redo
            if hasattr(self.editor, 'controller_position_operation_tracker'):
                # Get the starting position from the movement data
                movement_data = self.canvas_continuous_movements[controller_id]
                start_position = (movement_data.get('start_x', 0), movement_data.get('start_y', 0))

                # Get current position
                current_position = self.editor.mode_switcher.get_controller_position(controller_id)
                current_pos = current_position.position if current_position else (0, 0)

                # Only track if position actually changed
                if start_position != current_pos:
                    current_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
                    mode_str = current_mode.value if current_mode else None

                    self.editor.controller_position_operation_tracker.add_controller_position_change(
                        controller_id,
                        start_position,
                        current_pos,
                        mode_str,
                        mode_str,
                    )

            del self.canvas_continuous_movements[controller_id]
            self.log.debug(
                f'DEBUG: Stopped continuous canvas movement for controller {controller_id}',
            )

    def _update_canvas_continuous_movements(self) -> None:
        """Update continuous canvas movements with acceleration."""
        if not hasattr(self, 'canvas_continuous_movements'):
            return

        current_time = time.time()

        for controller_id, movement_data in list(self.canvas_continuous_movements.items()):
            # Calculate time since start and since last movement
            time_since_start = current_time - movement_data['start_time']
            time_since_last = current_time - movement_data['last_movement']

            # Calculate acceleration level (same as sliders)
            if time_since_start < CONTROLLER_ACCEL_LEVEL1_TIME:
                acceleration_level = 0
                interval = 0.15  # ~6.7 movements per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL2_TIME:
                acceleration_level = 1
                interval = 0.1  # 10 movements per second
            elif time_since_start < CONTROLLER_ACCEL_LEVEL3_TIME:
                acceleration_level = 2
                interval = 0.05  # 20 movements per second
            else:
                acceleration_level = 3
                interval = 0.025  # 40 movements per second

            # Update acceleration level if changed
            if acceleration_level != movement_data['acceleration_level']:
                movement_data['acceleration_level'] = acceleration_level
                self.log.debug(
                    f'DEBUG: Controller {controller_id} canvas movement acceleration level'
                    f' {acceleration_level}',
                )

            # Check if enough time has passed for next movement
            if time_since_last >= interval:
                # Calculate movement delta based on acceleration level (1, 2, 4, 8)
                dx = movement_data['dx'] * (2**acceleration_level)
                dy = movement_data['dy'] * (2**acceleration_level)
                dx = max(-8, min(8, dx))  # Cap at ±8
                dy = max(-8, min(8, dy))  # Cap at ±8

                # Apply the movement
                self._canvas_move_cursor(controller_id, dx, dy)

                # If this controller has an active drag operation, paint at the new position
                if (
                    hasattr(self, 'controller_drags')
                    and controller_id in self.controller_drags
                    and self.controller_drags[controller_id]['active']
                ):
                    self.canvas_paint_at_controller_position(controller_id)

                # Update last movement time
                movement_data['last_movement'] = current_time

    def canvas_paint_horizontal_line(self, controller_id: int, distance: int) -> None:
        """Paint a horizontal line of pixels starting from the controller's current position."""
        self.log.debug(
            f'DEBUG: canvas_paint_horizontal_line called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position
        current_color = self.editor.get_current_color()

        self.log.debug(
            f'DEBUG: Painting horizontal line from ({start_x}, {start_y}) with distance {distance},'
            f' color {current_color}',
        )

        canvas_width, canvas_height = self._get_canvas_dimensions()
        self.log.debug(f'DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}')

        # Paint pixels in a horizontal line
        for i in range(abs(distance)):
            pixel_x = start_x + i if distance > 0 else start_x - i
            pixel_y = start_y

            # Clamp coordinates to canvas bounds
            if canvas_width > 0:
                pixel_x = max(0, min(pixel_x, canvas_width - 1))
            if canvas_height > 0:
                pixel_y = max(0, min(pixel_y, canvas_height - 1))

            self._paint_and_track_pixel(controller_id, pixel_x, pixel_y, current_color)

        # Force canvas redraw
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self.editor.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_x = start_x + distance
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))
        if canvas_height > 0:
            start_y = max(0, min(start_y, canvas_height - 1))

        self.editor.mode_switcher.save_controller_position(controller_id, (end_x, start_y))
        self.log.debug(
            f'DEBUG: Updated controller {controller_id} position to ({end_x}, {start_y}) (clamped'
            f' to canvas bounds)',
        )

    def canvas_paint_vertical_line(self, controller_id: int, distance: int) -> None:
        """Paint a vertical line of pixels starting from the controller's current position."""
        self.log.debug(
            f'DEBUG: canvas_paint_vertical_line called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position
        current_color = self.editor.get_current_color()

        self.log.debug(
            f'DEBUG: Painting vertical line from ({start_x}, {start_y}) with distance {distance},'
            f' color {current_color}',
        )

        canvas_width, canvas_height = self._get_canvas_dimensions()
        self.log.debug(f'DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}')

        # Paint pixels in a vertical line
        for i in range(abs(distance)):
            pixel_y = start_y + i if distance > 0 else start_y - i
            pixel_x = start_x

            # Clamp coordinates to canvas bounds
            if canvas_width > 0:
                pixel_x = max(0, min(pixel_x, canvas_width - 1))
            if canvas_height > 0:
                pixel_y = max(0, min(pixel_y, canvas_height - 1))

            self._paint_and_track_pixel(controller_id, pixel_x, pixel_y, current_color)

        # Force canvas redraw
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self.editor.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_y = start_y + distance
        if canvas_width > 0:
            start_x = max(0, min(start_x, canvas_width - 1))
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        self.editor.mode_switcher.save_controller_position(controller_id, (start_x, end_y))
        self.log.debug(
            f'DEBUG: Updated controller {controller_id} position to ({start_x}, {end_y}) (clamped'
            f' to canvas bounds)',
        )

    def _get_canvas_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions.

        Returns:
            Tuple of (width, height), or (0, 0) if no canvas is available.

        """
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            return (
                getattr(self.editor.canvas, 'pixels_across', 0),
                getattr(self.editor.canvas, 'pixels_tall', 0),
            )
        return (0, 0)

    def _paint_and_track_pixel(
        self,
        controller_id: int,
        pixel_x: int,
        pixel_y: int,
        current_color: tuple[int, ...],
    ) -> None:
        """Paint a pixel and track it in the controller drag operation.

        Args:
            controller_id: The controller ID.
            pixel_x: X coordinate.
            pixel_y: Y coordinate.
            current_color: The color to paint.

        """
        old_color = self._get_canvas_pixel_color(pixel_x, pixel_y)
        if old_color is None:
            old_color = (0, 0, 0)

        if (
            hasattr(self.editor, 'canvas')
            and self.editor.canvas
            and hasattr(self.editor.canvas, 'canvas_interface')
        ):
            self.editor.canvas.canvas_interface.set_pixel_at(pixel_x, pixel_y, current_color)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            self.log.debug(
                f'DEBUG: Painted pixel at ({pixel_x}, {pixel_y}) with color {current_color}',
            )
            self._track_controller_drag_pixel(
                controller_id,
                (pixel_x, pixel_y),
                current_color,
                old_color,
            )
        else:
            self.log.debug('DEBUG: No canvas or canvas_interface available')

    def is_controller_button_held(self, controller_id: int, button: int) -> bool:
        """Check if a controller button is currently held down.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        try:
            # Get the controller instance
            controller = pygame.joystick.Joystick(controller_id)
            return controller.get_button(button)
        except pygame.error, ValueError:
            return False

    def canvas_jump_horizontal(self, controller_id: int, distance: int) -> None:
        """Jump horizontally without painting pixels."""
        self.log.debug(
            f'DEBUG: canvas_jump_horizontal called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_width = 0
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            canvas_width = getattr(self.editor.canvas, 'pixels_across', 0)

        # Calculate new position
        end_x = start_x + distance

        # Clamp to canvas bounds
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))

        # Update controller position
        self.editor.mode_switcher.save_controller_position(controller_id, (end_x, start_y))
        self.log.debug(
            f'DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({end_x},'
            f' {start_y})',
        )

    def canvas_jump_vertical(self, controller_id: int, distance: int) -> None:
        """Jump vertically without painting pixels."""
        self.log.debug(
            f'DEBUG: canvas_jump_vertical called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.log.debug(f'DEBUG: No valid position found for controller {controller_id}')
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_height = 0
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            canvas_height = getattr(self.editor.canvas, 'pixels_tall', 0)

        # Calculate new position
        end_y = start_y + distance

        # Clamp to canvas bounds
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        # Update controller position
        self.editor.mode_switcher.save_controller_position(controller_id, (start_x, end_y))
        self.log.debug(
            f'DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({start_x},'
            f' {end_y})',
        )

    def _slider_previous(self, controller_id: int) -> None:
        """Move to the previous slider (now handled by L2/R2 mode switching)."""
        self.log.debug(f'DEBUG: Controller {controller_id} moved to previous slider')
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility

    def _slider_next(self, controller_id: int) -> None:
        """Move to the next slider (now handled by L2/R2 mode switching)."""
        self.log.debug(f'DEBUG: Controller {controller_id} moved to next slider')
        # This is now handled by L2/R2 mode switching, so this is just for D-pad compatibility

    def on_joy_button_down_event(self, event: events.HashableEvent) -> None:
        """Handle joystick button down events (for controllers detected as joysticks).

        Args:
            event (pygame.event.Event): The joystick button down event.

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
            self._controller_cancel()
        else:
            # Unknown joystick button - not handled
            pass

    def on_joy_button_up_event(self, event: events.HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (pygame.event.Event): The joystick button up event.

        """

    def on_joy_hat_motion_event(self, event: events.HashableEvent) -> None:
        """Handle joystick hat motion events - requires threshold to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick hat motion event.

        """
        self.log.debug(f'DEBUG: Joystick hat motion: hat={event.hat}, value={event.value}')

        # Only respond to strong hat inputs (threshold > 0.5)
        # Hat values can be either:
        # - Integer bitmask: 0=center, 1=up, 2=right, 4=down, 8=left, etc.
        # - Tuple (x, y): (0,0)=center, (0,1)=up, (1,0)=right, (0,-1)=down, (-1,0)=left
        if isinstance(event.value, tuple):
            # For tuple, calculate magnitude
            hat_magnitude: float = (event.value[0] ** 2 + event.value[1] ** 2) ** 0.5  # type: ignore[index]
            if hat_magnitude < HAT_INPUT_MAGNITUDE_THRESHOLD:
                self.log.debug('DEBUG: Joystick hat motion below threshold, ignoring')
                return
        # For integer bitmask, use abs
        elif abs(event.value) < HAT_INPUT_MAGNITUDE_THRESHOLD:
            self.log.debug('DEBUG: Joystick hat motion below threshold, ignoring')
            return

        # Map hat directions to controller actions
        if event.value == 1:  # type: ignore[comparison-overlap]  # Up
            self.log.debug('DEBUG: Joystick hat up - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        if event.value == JOYSTICK_HAT_RIGHT:  # type: ignore[comparison-overlap]  # Right
            self.log.debug('DEBUG: Joystick hat right - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        if event.value == JOYSTICK_HAT_DOWN:  # type: ignore[comparison-overlap]  # Down
            self.log.debug('DEBUG: Joystick hat down - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return
        if event.value == JOYSTICK_HAT_LEFT:  # type: ignore[comparison-overlap]  # Left
            self.log.debug('DEBUG: Joystick hat left - DISABLED (use multi-controller system)')
            # OLD SYSTEM DISABLED - Use multi-controller system instead
            return

    def on_joy_axis_motion_event(self, event: events.HashableEvent) -> None:
        """Handle joystick axis motion events - disabled to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick axis motion event.

        """
        # Handle trigger axis motion for mode switching (axes 4 and 5)
        if event.axis in {4, 5}:  # TRIGGERLEFT and TRIGGERRIGHT
            self.log.debug(
                f'DEBUG: Trigger axis motion detected: axis={event.axis}, value={event.value}',
            )
            self._handle_trigger_axis_motion(event)
            return

        self.log.debug(
            f'DEBUG: Joystick axis motion (DISABLED): axis={event.axis}, value={event.value}',
        )
        # Disabled to prevent jittery behavior

    def on_joy_ball_motion_event(self, event: events.HashableEvent) -> None:
        """Handle joystick ball motion events - disabled to prevent jittery behavior.

        Args:
            event (pygame.event.Event): The joystick ball motion event.

        """
        self.log.debug(
            f'DEBUG: Joystick ball motion (DISABLED): ball={event.ball}, rel={event.rel}',
        )
        # Disabled to prevent jittery behavior

    def on_controller_axis_motion_event(self, event: events.HashableEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (pygame.event.Event): The controller axis motion event.

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
        self.log.debug(f'DEBUG: Controller axis motion: axis={event.axis}, value={event.value}')
        self.log.debug(f'DEBUG: LEFT_X axis constant: {pygame.CONTROLLER_AXIS_LEFTX}')
        self.log.debug(f'DEBUG: LEFT_Y axis constant: {pygame.CONTROLLER_AXIS_LEFTY}')
        self.log.debug(f'DEBUG: RIGHT_X axis constant: {pygame.CONTROLLER_AXIS_RIGHTX}')
        self.log.debug(f'DEBUG: RIGHT_Y axis constant: {pygame.CONTROLLER_AXIS_RIGHTY}')
        self.log.debug(
            'DEBUG: Controller selection active:'
            f' {getattr(self, "controller_selection_active", False)}',
        )

        # Left stick for fine frame navigation (only if controller selection is active)
        if not hasattr(self, 'controller_selection_active') or not self.controller_selection_active:  # type: ignore[attr-defined]
            self.log.debug('DEBUG: Controller selection not active, ignoring analog stick input')
            return

        import time

        current_time = time.time()

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
            self._controller_axis_cooldown[event.axis] = 0
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
            from glitchygames.bitmappy.controllers.modes import ControllerMode

            self.editor.mode_switcher.register_controller(controller_id, ControllerMode.FILM_STRIP)
            self.log.debug(f'DEBUG: Registered controller {controller_id} with mode switcher')

        import time

        current_time = time.time()

        l2_value, r2_value = self._read_trigger_values(event, controller_id)

        # Handle mode switching
        new_mode = self.editor.mode_switcher.handle_trigger_input(
            controller_id,
            l2_value,
            r2_value,
            current_time,
        )

        if new_mode:
            self.log.debug(f'DEBUG: Controller {controller_id} switched to mode: {new_mode.value}')
            self._track_controller_mode_change(controller_id, new_mode)
            self.update_controller_visual_indicator_for_mode(controller_id, new_mode)
        else:
            self.log.debug(
                f'DEBUG: No mode switch for controller {controller_id} - L2: {l2_value:.2f}, R2:'
                f' {r2_value:.2f}',
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
                f'DEBUG: Controller event - instance_id={instance_id},'
                f' controller_id={controller_id}',
            )
            return controller_id

        # Joystick event - use device index directly
        device_index = event.joy
        self.log.debug(
            f'DEBUG: Joystick event - using device index {device_index} as controller ID'
            f' {device_index}',
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
            f'DEBUG: Controller info lookup - instance_id={event.instance_id},'
            f' controller_info={controller_info}',
        )
        if not controller_info:
            self.log.debug(f'DEBUG: No controller info found for instance_id={event.instance_id}')
            return 0.0, 0.0

        try:
            controller = pygame.joystick.Joystick(event.instance_id)
            # Convert pygame trigger values (-1.0 to 1.0) to our expected range (0.0 to 1.0)
            l2_raw = controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT)
            r2_raw = controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT)
            l2_value = (l2_raw + 1.0) / 2.0
            r2_value = (r2_raw + 1.0) / 2.0
            self.log.debug(
                f'DEBUG: Controller {controller_id} triggers - L2: {l2_value:.2f}, R2:'
                f' {r2_value:.2f}',
            )
        except (pygame.error, OSError, AttributeError) as e:
            self.log.debug(
                f'DEBUG: Error getting controller object for instance_id={event.instance_id}: {e}',
            )
            return 0.0, 0.0
        else:
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
        try:
            joystick = pygame.joystick.Joystick(event.joy)
            self.log.debug(f'DEBUG: Created joystick object for joy {event.joy}')
            l2_raw = joystick.get_axis(4)  # TRIGGERLEFT
            r2_raw = joystick.get_axis(5)  # TRIGGERRIGHT

            # Convert joystick raw values to 0.0..1.0 range
            # Joystick values are typically in the range -32768 to 32767
            # We need to normalize them to 0.0 to 1.0
            l2_value = max(0.0, min(1.0, (l2_raw + 32768.0) / 65535.0))
            r2_value = max(0.0, min(1.0, (r2_raw + 32768.0) / 65535.0))

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
        except (pygame.error, OSError, AttributeError) as e:
            self.log.debug(f'DEBUG: Error getting joystick trigger values: {e}')
            return 0.0, 0.0
        else:
            return l2_value, r2_value

    def _track_controller_mode_change(self, controller_id: int, new_mode: ControllerMode) -> None:
        """Track a controller mode change for undo/redo.

        Args:
            controller_id: The controller ID.
            new_mode: The new ControllerMode.

        """
        if getattr(self, '_applying_undo_redo', False):
            return
        if not hasattr(self.editor, 'controller_position_operation_tracker'):
            return

        old_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
        if old_mode:
            self.editor.controller_position_operation_tracker.add_controller_mode_change(
                controller_id,
                old_mode.value,
                new_mode.value,
            )

    def update_controller_visual_indicator_for_mode(
        self,
        controller_id: int,
        new_mode: ControllerMode,
    ) -> None:
        """Update visual indicator for controller's new mode.

        Args:
            controller_id: Controller ID
            new_mode: New mode (ControllerMode enum)

        """
        self.log.debug(
            f'DEBUG: Updating visual indicator for controller {controller_id} to mode'
            f' {new_mode.value} (selected controller)',
        )

        # Get controller info
        controller_info = self.editor.multi_controller_manager.get_controller_info(controller_id)
        if not controller_info:
            self.log.debug(f'DEBUG: No controller info found for controller {controller_id}')
            return

        # Get location type for new mode
        location_type = self.editor.mode_switcher.get_controller_location_type(controller_id)
        if not location_type:
            self.log.debug(f'DEBUG: No location type found for controller {controller_id}')
            return

        self.log.debug(f'DEBUG: Location type for controller {controller_id}: {location_type}')

        position = self._get_controller_mode_position(controller_id, new_mode)

        self._update_visual_collision_indicator(
            controller_id,
            controller_info,
            position,
            location_type,
        )
        self._mark_dirty_for_mode_change(controller_id, location_type)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]

    def _get_controller_mode_position(
        self,
        controller_id: int,
        new_mode: ControllerMode,
    ) -> tuple[int, int]:
        """Get the position for a controller in its new mode.

        Args:
            controller_id: Controller ID.
            new_mode: New mode (ControllerMode enum).

        Returns:
            The (x, y) position tuple.

        """
        position_data = self.editor.mode_switcher.get_controller_position(controller_id)
        if position_data and position_data.is_valid:
            self.log.debug(
                f'DEBUG: Using saved position for controller {controller_id}:'
                f' {position_data.position}',
            )
            return position_data.position

        # Default position based on mode
        if new_mode.value == 'canvas':
            position = (0, 0)  # Start at top-left of canvas
        elif new_mode.value in {'r_slider', 'g_slider', 'b_slider'}:
            position = (0, 0)  # Start at top of slider
        else:  # film_strip
            position = (100, 100)  # Default position
        self.log.debug(f'DEBUG: Using default position for controller {controller_id}: {position}')
        return position

    def _update_visual_collision_indicator(
        self,
        controller_id: int,
        controller_info: Any,
        position: tuple[int, int],
        location_type: Any,
    ) -> None:
        """Update the visual collision manager indicator for a controller.

        Args:
            controller_id: Controller ID.
            controller_info: Controller info object with instance_id and color.
            position: The (x, y) position.
            location_type: The LocationType for the indicator.

        """
        if not hasattr(self.editor, 'visual_collision_manager'):
            self.log.debug('DEBUG: No visual_collision_manager found')
            return

        self.log.debug(
            f'DEBUG: Adding new indicator for controller {controller_id} at {position} with'
            f' location type {location_type}',
        )
        # Remove any existing indicator for this controller first
        self.editor.visual_collision_manager.remove_controller_indicator(controller_id)
        # Add new indicator for the new mode
        self.editor.visual_collision_manager.add_controller_indicator(
            controller_id,
            controller_info.instance_id,
            controller_info.color,
            position,
            location_type,
        )
        self.log.debug(
            f'DEBUG: Updated visual indicator for controller {controller_id} at {position}',
        )

    def _mark_dirty_for_mode_change(self, controller_id: int, location_type: str) -> None:
        """Mark appropriate areas as dirty after a controller mode change.

        Args:
            controller_id: Controller ID.
            location_type: The LocationType for the new mode.

        """
        self._mark_dirty_for_specific_mode(controller_id, location_type)

        # Also mark film strips as dirty to ensure old triangles are removed
        # This is needed because film strips use controller_selections, not
        # VisualCollisionManager
        if hasattr(self.editor, 'film_strips'):
            for strip_widget in self.editor.film_strips.values():
                strip_widget.mark_dirty()
            self.log.debug('DEBUG: Marked film strips as dirty to remove old indicators')

        # Also force canvas redraw to ensure old canvas indicators are removed
        # This is needed because canvas visual indicators are drawn on the canvas surface
        if hasattr(self.editor, 'canvas'):
            self.editor.canvas.force_redraw()
            self.log.debug('DEBUG: Forced canvas redraw to remove old indicators')

    def _mark_dirty_for_specific_mode(self, controller_id: int, location_type: str) -> None:
        """Mark mode-specific areas as dirty.

        Args:
            controller_id: Controller ID.
            location_type: The LocationType for the new mode.

        """
        from glitchygames.bitmappy.indicators.collision import LocationType

        if location_type == LocationType.CANVAS:
            if hasattr(self.editor, 'canvas'):
                self.editor.canvas.force_redraw()
                self.log.debug(f'DEBUG: Forced canvas redraw for controller {controller_id}')
        elif location_type == LocationType.SLIDER:
            if hasattr(self.editor, 'red_slider'):
                self.editor.red_slider.text_sprite.dirty = 2
            if hasattr(self.editor, 'green_slider'):
                self.editor.green_slider.text_sprite.dirty = 2
            if hasattr(self.editor, 'blue_slider'):
                self.editor.blue_slider.text_sprite.dirty = 2
            self.editor.dirty = 1
            self.log.debug(
                f'DEBUG: Marked sliders and scene as dirty for controller {controller_id}',
            )
        elif location_type == LocationType.FILM_STRIP:
            if hasattr(self.editor, 'film_strips'):
                for strip_widget in self.editor.film_strips.values():
                    strip_widget.mark_dirty()
            self.log.debug(f'DEBUG: Marked film strips as dirty for controller {controller_id}')

    def _render_visual_indicators(self) -> None:
        """Render visual indicators for multi-controller system."""
        # Initialize controller selections if needed
        if not hasattr(self.editor, 'controller_selections'):
            self.editor.controller_selections = {}

        # Initialize mode switcher if needed
        if not hasattr(self.editor, 'mode_switcher'):
            from glitchygames.bitmappy.controllers.modes import ModeSwitcher

            self.editor.mode_switcher = ModeSwitcher()

        # Initialize multi-controller manager if needed
        if not hasattr(self.editor, 'multi_controller_manager'):
            from glitchygames.bitmappy.controllers.manager import MultiControllerManager

            self.editor.multi_controller_manager = MultiControllerManager()

        # Scan for new controllers
        if hasattr(self.editor, 'multi_controller_manager'):
            self.editor.multi_controller_manager.scan_for_controllers()

        # Register any new controllers
        self._register_new_controllers()

        # Get the screen surface
        screen = pygame.display.get_surface()
        if not screen:
            return

        # Update all slider indicators with collision avoidance
        self._update_all_slider_indicators()

        # Update film strip controller selections
        self._update_film_strip_controller_selections()

        # Update canvas indicators
        self._update_canvas_indicators()

    def _create_slider_indicator_sprite(
        self,
        controller_id: int,
        color: tuple[int, ...],
        slider_rect: pygame.FRect | pygame.Rect,
    ) -> BitmappySprite:
        """Create a proper Bitmappy sprite for slider indicator.

        Returns:
            BitmappySprite: The result.

        """
        # Create a circular indicator sprite
        indicator_size = 16
        center_x = slider_rect.x + slider_rect.width / 2
        center_y = slider_rect.y + slider_rect.height / 2

        # Create the sprite
        indicator = BitmappySprite(
            name=f'SliderIndicator_{controller_id}',
            x=center_x - indicator_size // 2,
            y=center_y - indicator_size // 2,
            width=indicator_size,
            height=indicator_size,
            groups=self.editor.all_sprites,
        )

        # Make the background transparent
        indicator.image.set_colorkey((0, 0, 0))  # Make black transparent
        indicator.image.fill((0, 0, 0))  # Fill with black first

        # Draw the indicator on the sprite surface
        pygame.draw.circle(indicator.image, color, (indicator_size // 2, indicator_size // 2), 8)
        pygame.draw.circle(
            indicator.image,
            (255, 255, 255),
            (indicator_size // 2, indicator_size // 2),
            8,
            2,
        )

        return indicator

    def _update_slider_indicator(self, controller_id: int, color: tuple[int, ...]) -> None:
        """Update or create slider indicator for a controller."""
        # Remove any existing indicator for this controller
        self._remove_slider_indicator(controller_id)

        # Get the controller's current mode to determine which slider
        if hasattr(self.editor, 'mode_switcher'):
            controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)

            # Create indicator on the appropriate slider based on mode
            if (
                controller_mode
                and controller_mode.value == 'r_slider'
                and hasattr(self.editor, 'red_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.editor.red_slider.rect,
                )
                self.slider_indicators[controller_id] = indicator

            elif (
                controller_mode
                and controller_mode.value == 'g_slider'
                and hasattr(self.editor, 'green_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.editor.green_slider.rect,
                )
                self.slider_indicators[controller_id] = indicator

            elif (
                controller_mode
                and controller_mode.value == 'b_slider'
                and hasattr(self.editor, 'blue_slider')
            ):
                indicator = self._create_slider_indicator_sprite(
                    controller_id,
                    color,
                    self.editor.blue_slider.rect,
                )
                self.slider_indicators[controller_id] = indicator

    def _update_all_slider_indicators(self) -> None:
        """Update all slider indicators with collision avoidance."""
        # Clear all existing slider indicators
        for controller_id in list(self.slider_indicators.keys()):
            self._remove_slider_indicator(controller_id)

        slider_groups = self._group_controllers_by_slider()

        # Create indicators for each slider with collision avoidance
        for slider_mode, controllers in slider_groups.items():
            if controllers and len(controllers) > 0:
                self._create_slider_indicators_with_collision_avoidance(slider_mode, controllers)

    def _group_controllers_by_slider(self) -> dict[str, list[dict[str, Any]]]:
        """Group active controllers by their slider mode.

        Returns:
            Dict mapping slider mode strings to lists of controller info dicts.

        """
        slider_groups: dict[str, list[dict[str, Any]]] = {
            'r_slider': [],
            'g_slider': [],
            'b_slider': [],
        }

        for controller_id, controller_selection in self.editor.controller_selections.items():
            if not (controller_selection.is_active() and hasattr(self.editor, 'mode_switcher')):
                continue

            controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)
            if not (controller_mode and controller_mode.value in slider_groups):
                continue

            controller_info = self._find_controller_info(controller_id)
            if controller_info:
                slider_groups[controller_mode.value].append({
                    'controller_id': controller_id,
                    'color': controller_info.color,
                })

        return slider_groups

    def _create_slider_indicators_with_collision_avoidance(  # noqa: C901
        self,
        slider_mode: str,
        controllers: list[dict[str, Any]],
    ) -> None:
        """Create slider indicators with collision avoidance for multiple controllers."""
        # Get the appropriate slider
        slider = None
        if slider_mode == 'r_slider' and hasattr(self.editor, 'red_slider'):
            slider = self.editor.red_slider
        elif slider_mode == 'g_slider' and hasattr(self.editor, 'green_slider'):
            slider = self.editor.green_slider
        elif slider_mode == 'b_slider' and hasattr(self.editor, 'blue_slider'):
            slider = self.editor.blue_slider

        if not slider:
            return

        # Sort controllers by color priority (same as film strip)
        def get_color_priority(controller: dict[str, object]) -> int:
            color = controller['color']
            if color == (255, 0, 0):  # Red
                return 0
            if color == (0, 255, 0):  # Green
                return 1
            if color == (0, 0, 255):  # Blue
                return 2
            if color == (255, 255, 0):  # Yellow
                return 3
            return 999  # Unknown colors go last

        controllers.sort(key=get_color_priority)

        # Calculate positioning with collision avoidance
        indicator_size = 16
        indicator_spacing = 20  # Space between indicator centers

        # Calculate total width needed for all indicators
        total_width = (len(controllers) - 1) * indicator_spacing

        # Calculate starting position to center the group
        slider_rect = slider.rect
        assert slider_rect is not None
        start_x = int(slider_rect.centerx) - (total_width // 2)
        center_y = int(slider_rect.centery)

        # Create indicators with proper spacing
        current_x = start_x
        for controller in controllers:
            self._create_single_slider_indicator(
                controller,
                current_x,
                center_y,
                indicator_size,
            )
            current_x += indicator_spacing

    def _create_single_slider_indicator(
        self,
        controller: dict[str, Any],
        center_x: int,
        center_y: int,
        indicator_size: int,
    ) -> None:
        """Create a single slider indicator sprite for a controller.

        Args:
            controller: Controller info dict with 'controller_id' and 'color'.
            center_x: X center position for the indicator.
            center_y: Y center position for the indicator.
            indicator_size: Size of the indicator in pixels.

        """
        indicator = BitmappySprite(
            name=f'SliderIndicator_{controller["controller_id"]}',
            x=int(center_x - indicator_size // 2),
            y=int(center_y - indicator_size // 2),
            width=indicator_size,
            height=indicator_size,
            groups=self.editor.all_sprites,
        )

        # Make the background transparent
        indicator.image.set_colorkey((0, 0, 0))
        indicator.image.fill((0, 0, 0))

        # Draw the indicator
        half_size = indicator_size // 2
        pygame.draw.circle(
            indicator.image,
            controller['color'],
            (half_size, half_size),
            8,
        )
        pygame.draw.circle(
            indicator.image,
            (255, 255, 255),
            (half_size, half_size),
            8,
            2,
        )

        # Store the indicator
        self.slider_indicators[controller['controller_id']] = indicator

    def _update_film_strip_controller_selections(self) -> None:
        """Update film strip controller selections for all animations."""
        self.film_strip_controller_selections.clear()

        if not hasattr(self.editor, 'controller_selections'):
            return

        for controller_id, controller_selection in self.editor.controller_selections.items():
            self._process_film_strip_controller_selection(controller_id, controller_selection)

    def _process_film_strip_controller_selection(
        self,
        controller_id: int,
        controller_selection: ControllerSelection,
    ) -> None:
        """Process a single controller selection for film strip mode.

        Args:
            controller_id: The controller ID.
            controller_selection: The controller selection object.

        """
        if not controller_selection.is_active():
            return

        controller_mode = None
        if hasattr(self.editor, 'mode_switcher'):
            controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)

        if not (controller_mode and controller_mode.value == 'film_strip'):
            return

        animation, frame = controller_selection.get_selection()

        controller_info = self._find_controller_info(controller_id)
        if not controller_info:
            return

        # Only include controllers that have been properly initialized (not default gray)
        if not animation or controller_info.color == (128, 128, 128):
            return

        # Group by animation
        if animation not in self.film_strip_controller_selections:
            self.film_strip_controller_selections[animation] = {}

        self.film_strip_controller_selections[animation][controller_id] = {
            'controller_id': controller_id,
            'frame': frame,
            'color': controller_info.color,
        }

    def _find_controller_info(self, controller_id: int) -> Any:
        """Find controller info by controller ID.

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

    def _update_canvas_indicators(self) -> None:
        """Update canvas indicators for controllers in canvas mode."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            return

        canvas_controllers = self._collect_canvas_controllers()

        if canvas_controllers:
            self.canvas_controller_indicators = canvas_controllers
            if hasattr(self.editor.canvas, 'canvas_interface'):
                self.editor.canvas.canvas_interface.controller_indicators = canvas_controllers  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]
            self.editor.canvas.force_redraw()
        else:
            self.canvas_controller_indicators = []
            if hasattr(self.editor.canvas, 'canvas_interface'):
                self.editor.canvas.canvas_interface.controller_indicators = []  # type: ignore[attr-defined] # ty: ignore[invalid-assignment]

    def _collect_canvas_controllers(self) -> list[dict[str, Any]]:
        """Collect all active controllers in canvas mode with their positions.

        Returns:
            List of dicts with controller_id, position, and color.

        """
        canvas_controllers: list[dict[str, Any]] = []
        for controller_id, controller_selection in self.editor.controller_selections.items():
            if not controller_selection.is_active():
                continue

            controller_mode = None
            if hasattr(self.editor, 'mode_switcher'):
                controller_mode = self.editor.mode_switcher.get_controller_mode(controller_id)

            if not (controller_mode and controller_mode.value == 'canvas'):
                continue

            controller_info = self._find_controller_info(controller_id)
            if not controller_info:
                continue

            position = self.editor.mode_switcher.get_controller_position(controller_id)
            if position and position.is_valid:
                canvas_controllers.append({
                    'controller_id': controller_id,
                    'position': position.position,
                    'color': controller_info.color,
                })
        return canvas_controllers

    def _register_new_controllers(self) -> None:
        """Register any new controllers that have been detected."""
        if not hasattr(self.editor, 'multi_controller_manager'):
            return

        # Check for any controllers that aren't registered yet
        for (
            instance_id,
            controller_info,
        ) in self.editor.multi_controller_manager.controllers.items():
            controller_id = controller_info.controller_id
            if controller_id not in self.editor.controller_selections:
                # Register new controller
                from glitchygames.bitmappy.controllers.selection import ControllerSelection

                self.editor.controller_selections[controller_id] = ControllerSelection(
                    controller_id,
                    instance_id,
                )

                # Activate the controller
                self.editor.controller_selections[controller_id].activate()

                # Register with mode switcher
                if hasattr(self.editor, 'mode_switcher'):
                    from glitchygames.bitmappy.controllers.modes import ControllerMode

                    self.editor.mode_switcher.register_controller(
                        controller_id,
                        ControllerMode.FILM_STRIP,
                    )

                self.log.debug(
                    f'BitmapEditorScene: Registered and activated new controller {controller_id}'
                    f' (instance {instance_id})',
                )

    def _remove_slider_indicator(self, controller_id: int) -> None:
        """Remove slider indicator for a controller."""
        if hasattr(self, 'slider_indicators') and controller_id in self.slider_indicators:
            indicator = self.slider_indicators[controller_id]
            # Remove from sprite groups
            if hasattr(self.editor, 'all_sprites'):
                self.editor.all_sprites.remove(indicator)
            # Remove from tracking
            del self.slider_indicators[controller_id]

    def _draw_visual_indicator(self, screen: pygame.Surface, indicator: VisualIndicator) -> None:
        """Draw a single visual indicator on the screen."""
        if not indicator.is_visible:
            self.log.debug(
                f'DEBUG: Indicator for controller {indicator.controller_id} is not visible',
            )
            return

        # Calculate final position with offset
        final_x = indicator.position[0] + indicator.offset[0]
        final_y = indicator.position[1] + indicator.offset[1]

        self.log.debug(
            f'DEBUG: Drawing indicator for controller {indicator.controller_id} at ({final_x},'
            f' {final_y}) with shape {indicator.shape.value}',
        )

        # Draw based on shape
        if indicator.shape.value == 'triangle':
            # Draw triangle (film strip indicator)
            points = [
                (final_x, final_y - indicator.size // 2),
                (final_x - indicator.size // 2, final_y + indicator.size // 2),
                (final_x + indicator.size // 2, final_y + indicator.size // 2),
            ]
            pygame.draw.polygon(screen, indicator.color, points)
        elif indicator.shape.value == 'square':
            # Draw square (canvas indicator)
            rect = pygame.Rect(
                final_x - indicator.size // 2,
                final_y - indicator.size // 2,
                indicator.size,
                indicator.size,
            )
            pygame.draw.rect(screen, indicator.color, rect)
        elif indicator.shape.value == 'circle':
            # Draw circle (slider indicator)
            pygame.draw.circle(screen, indicator.color, (final_x, final_y), indicator.size // 2)

    def _select_current_frame(self) -> None:
        """Select the currently highlighted frame."""
        if not hasattr(self.editor, 'selected_animation') or not hasattr(
            self.editor,
            'selected_frame',
        ):
            return

        # Find the active film strip
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            for strip_name, strip_widget in self.editor.film_strips.items():
                if (
                    strip_name == self.editor.selected_animation
                    and self.editor.selected_animation is not None
                    and self.editor.selected_frame is not None
                ):
                    # Trigger frame selection
                    self.editor.on_film_strip_frame_selected(
                        strip_widget,
                        self.editor.selected_animation,
                        self.editor.selected_frame,
                    )
                    break

    def _controller_cancel(self) -> None:
        """Handle controller cancel action."""
        # For now, just log the action
        self.log.debug('Controller cancel action')

    def _controller_select_current_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_controller_select_current_frame called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_previous_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_controller_previous_frame called but DISABLED - use multi-controller system instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_next_frame(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_controller_next_frame called but DISABLED - use multi-controller system instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_previous_animation(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_controller_previous_animation called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_next_animation(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_controller_next_animation called but DISABLED - use multi-controller system instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _scroll_to_controller_animation(self, animation_name: str) -> None:
        """Scroll film strips to show the specified animation for multi-controller system."""
        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            return

        # Get all animation names in order
        animation_names = list(self.editor.film_strips.keys())
        if animation_name not in animation_names:
            return

        # Find the index of the target animation
        target_index = animation_names.index(animation_name)

        # Calculate the scroll offset needed to show this animation
        # We want to show the target animation in the visible area
        if target_index < self.editor.film_strip_scroll_offset:
            # Target animation is above the visible area, scroll up
            self.editor.film_strip_scroll_offset = target_index
        elif target_index >= self.editor.film_strip_scroll_offset + self.editor.max_visible_strips:
            # Target animation is below the visible area, scroll down
            self.editor.film_strip_scroll_offset = target_index - self.editor.max_visible_strips + 1

        # Update visibility and scroll arrows
        self.editor.update_film_strip_visibility()
        self.editor.update_scroll_arrows()

        self.log.debug(
            f"DEBUG: Scrolled to show animation '{animation_name}' at index {target_index}, scroll"
            f' offset: {self.editor.film_strip_scroll_offset}',
        )

    def _validate_controller_selection(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_validate_controller_selection called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _initialize_controller_selection(self) -> None:
        """Deprecate old single-controller system in favor of multi-controller system."""
        self.log.debug(
            '_initialize_controller_selection called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def _controller_select_frame(self, _animation: str, _frame: int) -> None:
        """Deprecate old single-controller system in favor of multi-controller system.

        This method is kept for compatibility but should not be used.
        Use the new multi-controller system instead.
        """
        self.log.debug(
            'DEBUG: _controller_select_frame called but DISABLED - use multi-controller system '
            'instead',
        )
        # OLD SYSTEM DISABLED - Use multi-controller system instead

    def multi_controller_activate(self, controller_id: int) -> None:
        """Activate a controller for navigation.

        Args:
            controller_id: Controller ID to activate

        """
        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for activation')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        controller_selection.activate()

        # Assign color based on activation order using singleton
        from .manager import MultiControllerManager

        manager = MultiControllerManager.get_instance()
        self.log.debug(f'DEBUG: About to assign color to controller {controller_id}')
        self.log.debug(
            f'DEBUG: Available controllers in manager: {list(manager.controllers.keys())}',
        )
        for instance_id, info in manager.controllers.items():
            self.log.debug(
                f'DEBUG: Controller instance_id={instance_id}, controller_id={info.controller_id},'
                f' color={info.color}',
            )
        manager.assign_color_to_controller(controller_id)

        # Initialize to first available animation if not set
        if (
            not controller_selection.get_animation()
            and hasattr(self.editor, 'film_strips')
            and self.editor.film_strips
        ):
            first_animation = next(iter(self.editor.film_strips.keys()))
            controller_selection.set_selection(first_animation, 0)
            self.log.debug(
                f"DEBUG: Controller {controller_id} initialized to '{first_animation}', frame 0",
            )

        # Update visual collision manager
        self._update_controller_visual_indicator(controller_id)

        # Mark all film strips as dirty to update colors
        if hasattr(self.editor, 'film_strips') and self.editor.film_strips:
            for film_strip in self.editor.film_strips.values():
                film_strip.mark_dirty()
        if hasattr(self.editor, 'film_strip_sprites') and self.editor.film_strip_sprites:
            for film_strip_sprite in self.editor.film_strip_sprites.values():
                film_strip_sprite.dirty = 1

        self.log.debug(f'DEBUG: Controller {controller_id} activated')

    def multi_controller_previous_frame(self, controller_id: int) -> None:
        """Move to previous frame for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for previous frame')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.editor.film_strips:
            self.log.debug(
                f'DEBUG: Controller {controller_id} has no valid animation for previous frame',
            )
            return

        strip_widget = self.editor.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame - 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                self.log.debug(
                    f'DEBUG: Controller {controller_id} previous frame: Scrolled film strip to show'
                    f' frame {new_frame}',
                )

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            self.log.debug(
                f'DEBUG: Controller {controller_id} previous frame: {frame} -> {new_frame}',
            )

    def multi_controller_next_frame(self, controller_id: int) -> None:
        """Move to next frame for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for next frame')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or animation not in self.editor.film_strips:
            self.log.debug(
                f'DEBUG: Controller {controller_id} has no valid animation for next frame',
            )
            return

        strip_widget = self.editor.film_strips[animation]
        if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
            frame_count = strip_widget.animated_sprite.current_animation_frame_count
            new_frame = (frame + 1) % frame_count
            controller_selection.set_frame(new_frame)

            # Scroll the film strip to show the selected frame if it's off-screen
            if hasattr(strip_widget, 'update_scroll_for_frame'):
                strip_widget.update_scroll_for_frame(new_frame)
                self.log.debug(
                    f'DEBUG: Controller {controller_id} next frame: Scrolled film strip to show'
                    f' frame {new_frame}',
                )

            # Update visual indicator
            self._update_controller_visual_indicator(controller_id)

            self.log.debug(f'DEBUG: Controller {controller_id} next frame: {frame} -> {new_frame}')

    def multi_controller_previous_animation(self, controller_id: int) -> None:
        """Move to previous animation for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for previous animation')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        current_animation, _current_frame = controller_selection.get_selection()

        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            self.log.debug(
                'DEBUG: No film strips available for controller %s previous animation',
                controller_id,
            )
            return

        # Get all animation names in order
        animation_names = list(self.editor.film_strips.keys())
        if not animation_names:
            self.log.debug(
                f'DEBUG: No animations available for controller {controller_id} previous animation',
            )
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to previous animation
        new_index = (current_index - 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        prev_strip_animated_sprite = self.editor.film_strips[new_animation].animated_sprite
        assert prev_strip_animated_sprite is not None
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            prev_strip_animated_sprite.current_animation_frame_count,
        )

        self.log.debug(
            f"DEBUG: Controller {controller_id} previous animation: Moving to '{new_animation}',"
            f' frame {target_frame}',
        )
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def multi_controller_next_animation(self, controller_id: int) -> None:
        """Move to next animation for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for next animation')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        current_animation, _current_frame = controller_selection.get_selection()

        if not hasattr(self.editor, 'film_strips') or not self.editor.film_strips:
            self.log.debug(
                f'DEBUG: No film strips available for controller {controller_id} next animation',
            )
            return

        # Get all animation names in order
        animation_names = list(self.editor.film_strips.keys())
        if not animation_names:
            self.log.debug(
                f'DEBUG: No animations available for controller {controller_id} next animation',
            )
            return

        # Find current animation index
        try:
            current_index = animation_names.index(current_animation)
        except ValueError:
            current_index = 0

        # Move to next animation
        new_index = (current_index + 1) % len(animation_names)
        new_animation = animation_names[new_index]

        # Try to preserve the frame index from the previous animation
        next_strip_animated_sprite = self.editor.film_strips[new_animation].animated_sprite
        assert next_strip_animated_sprite is not None
        target_frame = controller_selection.preserve_frame_for_animation(
            new_animation,
            next_strip_animated_sprite.current_animation_frame_count,
        )

        self.log.debug(
            f"DEBUG: Controller {controller_id} next animation: Moving to '{new_animation}', frame"
            f' {target_frame}',
        )
        controller_selection.set_selection(new_animation, target_frame)

        # Scroll the film strip view to show the selected animation if it's off-screen
        self._scroll_to_controller_animation(new_animation)

        # Update visual indicator
        self._update_controller_visual_indicator(controller_id)

    def _update_controller_visual_indicator(self, controller_id: int) -> None:
        """Update visual indicator for a controller.

        Args:
            controller_id: Controller ID

        """
        if controller_id not in self.editor.controller_selections:
            return

        controller_selection = self.editor.controller_selections[controller_id]
        animation, _frame = controller_selection.get_selection()

        if not animation or animation not in self.editor.film_strips:
            return

        # Get controller color
        controller_info = None
        for info in self.editor.multi_controller_manager.controllers.values():
            if info.controller_id == controller_id:
                controller_info = info
                break

        if not controller_info:
            return

        # Calculate position (this would need to be implemented based on your UI layout)
        # For now, we'll use a placeholder position
        position = (100 + controller_id * 50, 100)

        # Add or update visual indicator
        if controller_id not in self.editor.visual_collision_manager.indicators:
            self.editor.visual_collision_manager.add_controller_indicator(
                controller_id,
                controller_info.instance_id,
                controller_info.color,
                position,
            )
        else:
            self.editor.visual_collision_manager.update_controller_position(controller_id, position)

    def multi_controller_toggle_onion_skinning(self, controller_id: int) -> None:
        """Toggle onion skinning for the controller's selected frame.

        Args:
            controller_id: Controller ID to toggle onion skinning for

        """
        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found for onion skinning toggle')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        animation, frame = controller_selection.get_selection()

        if not animation or frame is None:  # type: ignore[reportUnnecessaryComparison]
            self.log.debug(
                f'DEBUG: Controller {controller_id} has no valid selection for onion skinning'
                f' toggle',
            )
            return

        # Get onion skinning manager
        from glitchygames.bitmappy.onion_skinning import get_onion_skinning_manager

        onion_manager = get_onion_skinning_manager()

        # Toggle onion skinning for this frame
        is_enabled = onion_manager.toggle_frame_onion_skinning(animation, frame)
        status = 'enabled' if is_enabled else 'disabled'

        self.log.debug(
            f'DEBUG: Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]',
        )
        self.log.debug(
            f'Controller {controller_id}: Onion skinning {status} for {animation}[{frame}]',
        )

        # Force redraw of the canvas to show the change
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self.editor.canvas.force_redraw()

    def multi_controller_toggle_selected_frame_visibility(self, controller_id: int) -> None:
        """Toggle visibility of the selected frame on the canvas for comparison.

        Args:
            controller_id: Controller ID (not used but kept for consistency)

        """
        # Toggle the selected frame visibility
        self.editor.selected_frame_visible = not self.editor.selected_frame_visible
        status = 'visible' if self.editor.selected_frame_visible else 'hidden'

        self.log.debug(f'DEBUG: Controller {controller_id}: Selected frame {status} on canvas')
        self.log.debug(f'Controller {controller_id}: Selected frame {status} on canvas')

        # Force redraw of the canvas to show the change
        if hasattr(self.editor, 'canvas') and self.editor.canvas:
            self.editor.canvas.force_redraw()

    def multi_controller_select_current_frame(self, controller_id: int) -> None:
        """Select the current frame that the controller is pointing to.

        Args:
            controller_id: The ID of the controller.

        """
        self.log.debug(
            f'DEBUG: multi_controller_select_current_frame called for controller {controller_id}',
        )

        if controller_id not in self.editor.controller_selections:
            self.log.debug(f'DEBUG: Controller {controller_id} not found in selections')
            return

        controller_selection = self.editor.controller_selections[controller_id]
        if not controller_selection.is_active():
            self.log.debug(f'DEBUG: Controller {controller_id} is not active')
            return

        animation, frame = controller_selection.get_selection()
        self.log.debug(
            f"DEBUG: Controller {controller_id} selecting frame {frame} in animation '{animation}'",
        )
        self.log.debug(
            'DEBUG: Current global selection before update:'
            f" animation='{getattr(self, 'selected_animation', 'None')}',"
            f' frame={getattr(self, "selected_frame", "None")}',
        )

        # Update the canvas to show this frame
        if animation in self.editor.film_strips:
            strip_widget = self.editor.film_strips[animation]
            if hasattr(strip_widget, 'animated_sprite') and strip_widget.animated_sprite:
                if animation in strip_widget.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
                    if frame < len(strip_widget.animated_sprite._animations[animation]):  # type: ignore[reportPrivateUsage]
                        # Update the canvas to show this frame using the same mechanism as keyboard
                        # selection
                        self.log.debug(
                            "DEBUG: Updating canvas to show animation '%s', frame %s",
                            animation,
                            frame,
                        )
                        self.editor.canvas.show_frame(animation, frame)

                        # Store global selection state (same as keyboard selection)
                        self.log.debug(
                            f"DEBUG: Setting global selection state to animation '{animation}',"
                            f' frame {frame}',
                        )
                        self.editor.selected_animation = animation
                        self.editor.selected_frame = frame

                        # Update film strip selection state (same as keyboard selection)
                        self.log.debug('DEBUG: Calling _update_film_strip_selection_state()')
                        self.editor.update_film_strip_selection_state()

                        self.log.debug(
                            'DEBUG: Controller selection updated keyboard selection to animation'
                            f" '{animation}', frame {frame}",
                        )
                        selected_anim = self.editor.selected_animation
                        selected_frm = self.editor.selected_frame
                        self.log.debug(
                            f"DEBUG: Final global selection: animation='{selected_anim}',"
                            f' frame={selected_frm}',
                        )
                    else:
                        self.log.debug(
                            f"DEBUG: Frame {frame} is out of bounds for animation '{animation}'"
                            f' (max:'
                            f' {len(strip_widget.animated_sprite._animations[animation]) - 1})',  # type: ignore[reportPrivateUsage]
                        )
                else:
                    self.log.debug(
                        f"DEBUG: Animation '{animation}' not found in"
                        f' strip_widget.animated_sprite._animations',
                    )
            else:
                self.log.debug(
                    'DEBUG: strip_widget has no animated_sprite or animated_sprite is None',
                )
        else:
            self.log.debug(f"DEBUG: Animation '{animation}' not found in film_strips")

    def _multi_controller_cancel(self, controller_id: int) -> None:
        """Cancel controller selection.

        Args:
            controller_id: The ID of the controller.

        """
        if controller_id not in self.editor.controller_selections:
            return

        controller_selection = self.editor.controller_selections[controller_id]
        controller_selection.deactivate()
        self.log.debug(f'DEBUG: Controller {controller_id} cancelled')

    def reinitialize_multi_controller_system(
        self,
        preserved_controller_selections: dict[int, tuple[str, int]] | None = None,
    ) -> None:
        """Reinitialize the multi-controller system when film strips are reconstructed.

        This ensures that existing controller selections are preserved and properly
        initialized when film strips are recreated (e.g., when loading an animation file).

        Args:
            preserved_controller_selections: Optional dict of preserved controller selections
                from before film strip reconstruction.

        """
        import sys

        if 'pytest' not in sys.modules:
            self.log.debug('DEBUG: Reinitializing multi-controller system')
            selection_keys = list(self.editor.controller_selections.keys())
            self.log.debug(f'DEBUG: Current controller_selections: {selection_keys}')
            self.log.debug(
                f'DEBUG: Current film_strips: {
                    list(self.editor.film_strips.keys())
                    if hasattr(self, "film_strips") and self.editor.film_strips
                    else "None"
                }',
            )

        if not self.editor.controller_selections:
            if 'pytest' not in sys.modules:
                self.log.debug('DEBUG: controller_selections is empty - scene was likely recreated')
            return

        active_controllers = self._get_active_controllers(preserved_controller_selections)
        self.log.debug(f'DEBUG: Found {len(active_controllers)} active controllers to preserve')

        self.editor.multi_controller_manager.scan_for_controllers()
        controller_count = len(self.editor.multi_controller_manager.controllers)
        self.log.debug(f'DEBUG: Found {controller_count} controllers in manager')

        self._reinitialize_controller_selections(active_controllers)

        selection_count = len(self.editor.controller_selections)
        self.log.debug(
            f'DEBUG: Multi-controller system reinitialized with'
            f' {selection_count} controller selections',
        )

    def _get_active_controllers(
        self,
        preserved_controller_selections: dict[int, tuple[str, int]] | None,
    ) -> dict[int, tuple[str, int]]:
        """Get the active controller state, either preserved or current.

        Args:
            preserved_controller_selections: Optional preserved selections.

        Returns:
            Dict mapping controller_id to (animation, frame) tuples.

        """
        if preserved_controller_selections is not None:
            self.log.debug(
                f'DEBUG: Using preserved controller selections: {preserved_controller_selections}',
            )
            return preserved_controller_selections

        active_controllers: dict[int, tuple[str, int]] = {}
        num_selections = len(self.editor.controller_selections)
        self.log.debug(f'DEBUG: Checking {num_selections} existing controller selections')
        for controller_id, controller_selection in self.editor.controller_selections.items():
            is_active = controller_selection.is_active()
            self.log.debug(f'DEBUG: Controller {controller_id} is_active: {is_active}')
            if is_active:
                animation, frame = controller_selection.get_selection()
                active_controllers[controller_id] = (animation, frame)
                self.log.debug(
                    f'DEBUG: Storing active controller {controller_id} with animation'
                    f" '{animation}', frame {frame}",
                )
        return active_controllers

    def _reinitialize_controller_selections(
        self,
        active_controllers: dict[int, tuple[str, int]],
    ) -> None:
        """Reinitialize controller selections from the multi-controller manager.

        Args:
            active_controllers: Dict mapping controller_id to (animation, frame) tuples.

        """
        for (
            instance_id,
            controller_info,
        ) in self.editor.multi_controller_manager.controllers.items():
            self.log.debug(
                f'DEBUG: Processing controller {instance_id}, status:'
                f' {controller_info.status.value}',
            )
            if controller_info.status.value not in {'connected', 'assigned', 'active'}:
                continue

            controller_id = controller_info.controller_id
            self._ensure_controller_selection_exists(controller_id, instance_id)
            self._restore_controller_active_state(controller_id, active_controllers)

    def _ensure_controller_selection_exists(self, controller_id: int, instance_id: int) -> None:
        """Ensure a controller selection exists for the given controller.

        Args:
            controller_id: The controller ID.
            instance_id: The instance ID for creating new selections.

        """
        if controller_id not in self.editor.controller_selections:
            self.editor.controller_selections[controller_id] = ControllerSelection(
                controller_id,
                instance_id,
            )
            self.log.debug(
                'DEBUG: Created new controller selection for controller %s (inactive)',
                controller_id,
            )
        else:
            controller_selection = self.editor.controller_selections[controller_id]
            controller_selection.update_activity()
            self.log.debug(
                f'DEBUG: Updated existing controller selection for controller {controller_id}',
            )

    def _restore_controller_active_state(
        self,
        controller_id: int,
        active_controllers: dict[int, tuple[str, int]],
    ) -> None:
        """Restore a controller's active state after reinitialization.

        Args:
            controller_id: The controller ID.
            active_controllers: Dict mapping controller_id to (animation, frame) tuples.

        """
        controller_selection = self.editor.controller_selections[controller_id]

        if controller_id not in active_controllers:
            self.log.debug(
                f'DEBUG: Controller {controller_id} was not active before reconstruction,'
                f' keeping it inactive',
            )
            return

        if not self.editor.film_strips:
            self.log.debug(f'DEBUG: No film strips available for active controller {controller_id}')
            return

        # Always reset to first strip and frame 0 when loading new files
        # since animation names and structure will be different
        first_animation = next(iter(self.editor.film_strips.keys()))
        controller_selection.set_selection(first_animation, 0)
        controller_selection.activate()
        self.log.debug(
            f'DEBUG: Reset active controller {controller_id} to first animation'
            f" '{first_animation}', frame 0 (ignoring previous selection)",
        )
        self.log.debug(
            f'DEBUG: Controller {controller_id} is now active: {controller_selection.is_active()}',
        )
        self.log.debug(
            f'DEBUG: Controller {controller_id} selection: {controller_selection.get_selection()}',
        )
        self.log.debug(f'DEBUG: Available film strips: {list(self.editor.film_strips.keys())}')
