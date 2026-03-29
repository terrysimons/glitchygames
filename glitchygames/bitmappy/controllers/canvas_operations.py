"""Canvas-related controller operations for the Bitmappy editor.

Provides the CanvasOperations delegate with methods for painting, erasing,
cursor movement, line drawing, jumping, continuous movement, and
drag-pixel tracking on the editor canvas.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from glitchygames.bitmappy.constants import (
    CONTROLLER_ACCEL_LEVEL1_TIME,
    CONTROLLER_ACCEL_LEVEL2_TIME,
    CONTROLLER_ACCEL_LEVEL3_TIME,
)

if TYPE_CHECKING:
    from glitchygames.bitmappy.controllers.event_handler import ControllerEventHandler

log = logging.getLogger('game.tools.bitmappy.controllers.canvas_operations')
log.addHandler(logging.NullHandler())


class CanvasOperations:
    """Delegate providing canvas-related controller operations.

    All handler state is accessed via self.handler (the ControllerEventHandler).
    """

    def __init__(self, handler: ControllerEventHandler) -> None:
        """Initialize the canvas operations delegate.

        Args:
            handler: The ControllerEventHandler that owns this delegate.

        """
        self.handler = handler

    # ------------------------------------------------------------------
    # Drag operations
    # ------------------------------------------------------------------

    def handle_controller_drag_end(self, controller_id: int) -> None:
        """Handle the end of a controller drag operation.

        Args:
            controller_id: The controller that released the A button.

        """
        if not (
            hasattr(self.handler, 'controller_drags')
            and controller_id in self.handler.controller_drags
        ):
            return

        drag_info = self.handler.controller_drags[controller_id]
        if not drag_info['active']:
            return

        # End the drag operation
        drag_info['active'] = False
        drag_info['end_time'] = time.time()
        drag_info['end_position'] = self.handler.editor.mode_switcher.get_controller_position(
            controller_id,
        )

        self.handler.log.debug(
            f'DEBUG: Controller {controller_id}: Drag operation drew'
            f' {len(drag_info["pixels_drawn"])} pixels',
        )

        if not drag_info['pixels_drawn']:
            return

        self.handler.log.debug(
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
        if (
            hasattr(self.handler.editor, 'undo_redo_manager')
            and self.handler.editor.undo_redo_manager
        ):
            self.handler.log.debug(
                'DEBUG: Undo stack before merging has'
                f' {len(self.handler.editor.undo_redo_manager.undo_stack)} operations',
            )
            for i, op in enumerate(self.handler.editor.undo_redo_manager.undo_stack):
                self.handler.log.debug(
                    f'DEBUG:   Operation {i}: {op.operation_type} - {op.description}',
                )

        # Absorb any pending single pixel operation from canvas interface
        # This merges the initial A button pixel with the drag pixels
        if (
            hasattr(self.handler.editor, 'current_pixel_changes')
            and self.handler.editor.current_pixel_changes
        ):
            pending_count = len(self.handler.editor.current_pixel_changes)
            self.handler.log.debug(
                f'DEBUG: Absorbing {pending_count} pending pixel(s) from canvas interface',
            )
            self.handler.log.debug(
                f'DEBUG: Pending pixels: {self.handler.editor.current_pixel_changes}',
            )
            # Add the pending pixels to the beginning of the controller drag pixels
            pixel_changes = self.handler.editor.current_pixel_changes + pixel_changes
            self.handler.log.debug(
                f'DEBUG: Merged pixel_changes now has {len(pixel_changes)} pixels',
            )
            # Clear the pending pixels to prevent duplicate undo operation
            self.handler.editor.current_pixel_changes = []

            # Remove the old single pixel entry from the undo stack
            # This prevents having two separate undo operations
            if (
                hasattr(self.handler.editor, 'undo_redo_manager')
                and self.handler.editor.undo_redo_manager
            ):
                if self.handler.editor.undo_redo_manager.undo_stack:
                    removed_operation = self.handler.editor.undo_redo_manager.undo_stack.pop()
                    self.handler.log.debug(
                        'DEBUG: Removed single pixel operation from undo stack:'
                        f' {removed_operation.operation_type}',
                    )
                    self.handler.log.debug(
                        'DEBUG: Undo stack after removal has'
                        f' {len(self.handler.editor.undo_redo_manager.undo_stack)} operations',
                    )
                else:
                    self.handler.log.debug('DEBUG: No operations in undo stack to remove')
        else:
            self.handler.log.debug('DEBUG: No pending pixels to absorb from canvas interface')

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
        if not pixel_changes or not hasattr(self.handler.editor, 'canvas_operation_tracker'):
            return

        # Get current frame information for frame-specific tracking
        current_animation = None
        current_frame = None
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            current_animation = getattr(self.handler.editor.canvas, 'current_animation', None)
            current_frame = getattr(self.handler.editor.canvas, 'current_frame', None)

        # Use frame-specific tracking if we have frame information
        if current_animation is not None and current_frame is not None:
            self.handler.editor.canvas_operation_tracker.add_frame_pixel_changes(
                current_animation,
                current_frame,
                pixel_changes,  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            )
            self.handler.log.debug(
                f'Controller {controller_id}: Submitted {len(pixel_changes)} pixel'
                f' changes for frame {current_animation}[{current_frame}] undo/redo',
            )
        else:
            # Fall back to global tracking
            self.handler.editor.canvas_operation_tracker.add_pixel_changes(pixel_changes)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            self.handler.log.debug(
                f'Controller {controller_id}: Submitted {len(pixel_changes)} pixel'
                f' changes for global undo/redo',
            )

    # ------------------------------------------------------------------
    # Painting and erasing
    # ------------------------------------------------------------------

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
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} has no valid canvas position',
            )
            return

        # Get current color from the color picker
        current_color = self.handler.editor.get_current_color()
        self.handler.log.debug(
            f'DEBUG: canvas_paint_at_controller_position() got color: {current_color}',
        )

        # Check if pixel is already the selected color (debouncing)
        if not force:
            current_pixel_color = self._get_canvas_pixel_color(
                position.position[0],
                position.position[1],
            )
            if current_pixel_color == current_color:
                self.handler.log.debug(
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

        self.handler.log.debug(
            f'DEBUG: Painted at canvas position {position.position} with color {current_color}',
        )

    def _get_canvas_pixel_color(
        self,
        x: int,
        y: int,
    ) -> tuple[int, ...] | None:
        """Get the color of a pixel on the canvas.

        Args:
            x: X coordinate.
            y: Y coordinate.

        Returns:
            The pixel color tuple, or None if unavailable.

        """
        if not (hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas):
            return None

        if hasattr(self.handler.editor.canvas, 'canvas_interface'):
            try:
                return self.handler.editor.canvas.canvas_interface.get_pixel_at(x, y)
            except (IndexError, AttributeError, TypeError) as pixel_error:
                self.handler.log.debug(f'Could not get pixel color: {pixel_error}')
                return (0, 0, 0)

        if (
            0 <= x < self.handler.editor.canvas.pixels_across
            and 0 <= y < self.handler.editor.canvas.pixels_tall
        ):
            pixel_num = y * self.handler.editor.canvas.pixels_across + x
            return self.handler.editor.canvas.pixels[pixel_num]
        return None

    def _set_canvas_pixel(
        self,
        x: int,
        y: int,
        color: tuple[int, ...],
    ) -> None:
        """Set a pixel color on the canvas.

        Args:
            x: X coordinate.
            y: Y coordinate.
            color: The color tuple to set.

        """
        if not (hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas):
            return

        if hasattr(self.handler.editor.canvas, 'canvas_interface'):
            self.handler.editor.canvas.canvas_interface.set_pixel_at(x, y, color)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
        elif (
            0 <= x < self.handler.editor.canvas.pixels_across
            and 0 <= y < self.handler.editor.canvas.pixels_tall
        ):
            pixel_num = y * self.handler.editor.canvas.pixels_across + x
            self.handler.editor.canvas.pixels[pixel_num] = color
            self.handler.editor.canvas.dirty_pixels[pixel_num] = True
            self.handler.editor.canvas.dirty = 1

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
        if not (
            hasattr(self.handler, 'controller_drags')
            and controller_id in self.handler.controller_drags
        ):
            self.handler.log.debug(
                f'DEBUG: No controller drags or controller {controller_id} not in controller_drags',
            )
            return

        drag_info = self.handler.controller_drags[controller_id]
        if not drag_info['active']:
            self.handler.log.debug(
                f'DEBUG: Controller drag not active for controller {controller_id}',
            )
            return

        pixel_info = {
            'position': position,
            'color': current_color,
            'old_color': old_color,  # Store the original color for undo
            'timestamp': time.time(),
        }
        drag_info['pixels_drawn'].append(pixel_info)
        self.handler.log.debug(
            f'DEBUG: Controller drag tracking pixel at {position}, total'
            f' pixels: {len(drag_info["pixels_drawn"])}',
        )

    def _canvas_erase_at_controller_position(
        self,
        controller_id: int,
    ) -> None:
        """Erase at the controller's current canvas position."""
        # Get controller's canvas position
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.handler.log.debug(
                f'DEBUG: Controller {controller_id} has no valid canvas position',
            )
            return

        # Erase at the position (paint with background color)
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            background_color = (0, 0, 0)  # Black background
            # Use the canvas interface to set the pixel
            if hasattr(self.handler.editor.canvas, 'canvas_interface'):
                self.handler.editor.canvas.canvas_interface.set_pixel_at(
                    position.position[0],
                    position.position[1],
                    background_color,
                )
            else:
                # Fallback: directly set pixel if interface not available
                x, y = position.position[0], position.position[1]
                if (
                    0 <= x < self.handler.editor.canvas.pixels_across
                    and 0 <= y < self.handler.editor.canvas.pixels_tall
                ):
                    pixel_num = y * self.handler.editor.canvas.pixels_across + x
                    self.handler.editor.canvas.pixels[pixel_num] = background_color
                    self.handler.editor.canvas.dirty_pixels[pixel_num] = True
                    self.handler.editor.canvas.dirty = 1
            self.handler.log.debug(f'DEBUG: Erased at canvas position {position.position}')

    # ------------------------------------------------------------------
    # Cursor movement
    # ------------------------------------------------------------------

    def _canvas_move_cursor(
        self,
        controller_id: int,
        dx: int,
        dy: int,
    ) -> None:
        """Move the controller's canvas cursor."""
        # Get current position
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position:
            # Initialize at (0, 0) if no position
            old_position = (0, 0)
            new_position = (0, 0)
        else:
            old_position = position.position
            new_position = (position.position[0] + dx, position.position[1] + dy)

        # Clamp to canvas bounds
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            canvas_width = getattr(self.handler.editor.canvas, 'width', 32)
            canvas_height = getattr(self.handler.editor.canvas, 'height', 32)
            new_position = (
                max(0, min(canvas_width - 1, new_position[0])),
                max(0, min(canvas_height - 1, new_position[1])),
            )

        # Track controller position change for undo/redo (only if position actually changed and not
        # in continuous movement)
        if (
            old_position != new_position
            and not getattr(self.handler, '_applying_undo_redo', False)
            and not self._is_controller_in_continuous_movement(controller_id)
            and hasattr(self.handler.editor, 'controller_position_operation_tracker')
        ):
            # Get current mode for context
            current_mode = self.handler.editor.mode_switcher.get_controller_mode(controller_id)
            mode_str = current_mode.value if current_mode else None

            self.handler.editor.controller_position_operation_tracker.add_controller_position_change(
                controller_id,
                old_position,
                new_position,
                mode_str,
                mode_str,
            )

        # Update position
        self.handler.editor.mode_switcher.save_controller_position(controller_id, new_position)

        # If controller is in an active drag operation, paint at the new position
        # (the paint method will check if the pixel needs painting)
        if (
            hasattr(self.handler, 'controller_drags')
            and controller_id in self.handler.controller_drags
        ):
            drag_info = self.handler.controller_drags[controller_id]
            if drag_info['active']:
                self.handler.log.debug(
                    f'DEBUG: Controller {controller_id}: In active drag, painting at new position'
                    f' {new_position}',
                )
                self.canvas_paint_at_controller_position(controller_id)

        # Update visual indicator
        self.handler.indicators.update_controller_canvas_visual_indicator(controller_id)

        self.handler.log.debug(
            f'DEBUG: Controller {controller_id} canvas cursor moved to {new_position}',
        )

    def _is_controller_in_continuous_movement(
        self,
        controller_id: int,
    ) -> bool:
        """Check if a controller is currently in continuous movement mode.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # Check for canvas continuous movement
        if (
            hasattr(self.handler, 'canvas_continuous_movements')
            and controller_id in self.handler.canvas_continuous_movements
        ):
            return True

        # Check for slider continuous adjustment
        return bool(
            hasattr(self.handler, 'slider_continuous_adjustments')
            and controller_id in self.handler.slider_continuous_adjustments,
        )

    # ------------------------------------------------------------------
    # Continuous canvas movement
    # ------------------------------------------------------------------

    def start_canvas_continuous_movement(
        self,
        controller_id: int,
        dx: int,
        dy: int,
    ) -> None:
        """Start continuous canvas movement with acceleration."""
        # Do the first movement immediately for responsive feel
        self._canvas_move_cursor(controller_id, dx, dy)

        # Get starting position for undo/redo tracking
        start_position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        start_x, start_y = start_position.position if start_position else (0, 0)

        # Initialize continuous movement for this controller
        current_time = time.time()
        self.handler.canvas_continuous_movements[controller_id] = {
            'dx': dx,
            'dy': dy,
            'start_time': current_time,
            'last_movement': current_time,
            'acceleration_level': 0,
            'start_x': start_x,
            'start_y': start_y,
        }
        self.handler.log.debug(
            f'DEBUG: Started continuous canvas movement for controller {controller_id}, direction'
            f' ({dx}, {dy}) (immediate first movement)',
        )

    def stop_canvas_continuous_movement(
        self,
        controller_id: int,
    ) -> None:
        """Stop continuous canvas movement."""
        if (
            hasattr(self.handler, 'canvas_continuous_movements')
            and controller_id in self.handler.canvas_continuous_movements
        ):
            # Track the final position change for undo/redo
            if hasattr(self.handler.editor, 'controller_position_operation_tracker'):
                # Get the starting position from the movement data
                movement_data = self.handler.canvas_continuous_movements[controller_id]
                start_position = (movement_data.get('start_x', 0), movement_data.get('start_y', 0))

                # Get current position
                current_position = self.handler.editor.mode_switcher.get_controller_position(
                    controller_id,
                )
                current_pos = current_position.position if current_position else (0, 0)

                # Only track if position actually changed
                if start_position != current_pos:
                    current_mode = self.handler.editor.mode_switcher.get_controller_mode(
                        controller_id,
                    )
                    mode_str = current_mode.value if current_mode else None

                    self.handler.editor.controller_position_operation_tracker.add_controller_position_change(
                        controller_id,
                        start_position,
                        current_pos,
                        mode_str,
                        mode_str,
                    )

            del self.handler.canvas_continuous_movements[controller_id]
            self.handler.log.debug(
                f'DEBUG: Stopped continuous canvas movement for controller {controller_id}',
            )

    def update_canvas_continuous_movements(self) -> None:
        """Update continuous canvas movements with acceleration."""
        if not hasattr(self.handler, 'canvas_continuous_movements'):
            return

        current_time = time.time()

        for controller_id, movement_data in list(self.handler.canvas_continuous_movements.items()):
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
                self.handler.log.debug(
                    f'DEBUG: Controller {controller_id} canvas movement acceleration level'
                    f' {acceleration_level}',
                )

            # Check if enough time has passed for next movement
            if time_since_last >= interval:
                # Calculate movement delta based on acceleration level (1, 2, 4, 8)
                dx = movement_data['dx'] * (2**acceleration_level)
                dy = movement_data['dy'] * (2**acceleration_level)
                dx = max(-8, min(8, dx))  # Cap at +/-8
                dy = max(-8, min(8, dy))  # Cap at +/-8

                # Apply the movement
                self._canvas_move_cursor(controller_id, dx, dy)

                # If this controller has an active drag operation, paint at the new position
                if (
                    hasattr(self.handler, 'controller_drags')
                    and controller_id in self.handler.controller_drags
                    and self.handler.controller_drags[controller_id]['active']
                ):
                    self.canvas_paint_at_controller_position(controller_id)

                # Update last movement time
                movement_data['last_movement'] = current_time

    # ------------------------------------------------------------------
    # Line drawing
    # ------------------------------------------------------------------

    def canvas_paint_horizontal_line(
        self,
        controller_id: int,
        distance: int,
    ) -> None:
        """Paint a horizontal line of pixels starting from the controller's current position."""
        self.handler.log.debug(
            f'DEBUG: canvas_paint_horizontal_line called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.handler.log.debug(
                f'DEBUG: No valid position found for controller {controller_id}',
            )
            return

        start_x, start_y = position.position
        current_color = self.handler.editor.get_current_color()

        self.handler.log.debug(
            f'DEBUG: Painting horizontal line from ({start_x}, {start_y}) with distance {distance},'
            f' color {current_color}',
        )

        canvas_width, canvas_height = self._get_canvas_dimensions()
        self.handler.log.debug(f'DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}')

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
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            self.handler.editor.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_x = start_x + distance
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))
        if canvas_height > 0:
            start_y = max(0, min(start_y, canvas_height - 1))

        self.handler.editor.mode_switcher.save_controller_position(
            controller_id,
            (end_x, start_y),
        )
        self.handler.log.debug(
            f'DEBUG: Updated controller {controller_id} position to ({end_x}, {start_y}) (clamped'
            f' to canvas bounds)',
        )

    def canvas_paint_vertical_line(
        self,
        controller_id: int,
        distance: int,
    ) -> None:
        """Paint a vertical line of pixels starting from the controller's current position."""
        self.handler.log.debug(
            f'DEBUG: canvas_paint_vertical_line called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.handler.log.debug(
                f'DEBUG: No valid position found for controller {controller_id}',
            )
            return

        start_x, start_y = position.position
        current_color = self.handler.editor.get_current_color()

        self.handler.log.debug(
            f'DEBUG: Painting vertical line from ({start_x}, {start_y}) with distance {distance},'
            f' color {current_color}',
        )

        canvas_width, canvas_height = self._get_canvas_dimensions()
        self.handler.log.debug(f'DEBUG: Canvas dimensions: {canvas_width}x{canvas_height}')

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
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            self.handler.editor.canvas.force_redraw()

        # Update controller position to the end of the line (clamped to canvas bounds)
        end_y = start_y + distance
        if canvas_width > 0:
            start_x = max(0, min(start_x, canvas_width - 1))
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        self.handler.editor.mode_switcher.save_controller_position(
            controller_id,
            (start_x, end_y),
        )
        self.handler.log.debug(
            f'DEBUG: Updated controller {controller_id} position to ({start_x}, {end_y}) (clamped'
            f' to canvas bounds)',
        )

    def _get_canvas_dimensions(self) -> tuple[int, int]:
        """Get the canvas dimensions.

        Returns:
            Tuple of (width, height), or (0, 0) if no canvas is available.

        """
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            return (
                getattr(self.handler.editor.canvas, 'pixels_across', 0),
                getattr(self.handler.editor.canvas, 'pixels_tall', 0),
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
            hasattr(self.handler.editor, 'canvas')
            and self.handler.editor.canvas
            and hasattr(self.handler.editor.canvas, 'canvas_interface')
        ):
            canvas_interface = self.handler.editor.canvas.canvas_interface
            canvas_interface.set_pixel_at(pixel_x, pixel_y, current_color)  # type: ignore[arg-type] # ty: ignore[invalid-argument-type]
            self.handler.log.debug(
                f'DEBUG: Painted pixel at ({pixel_x}, {pixel_y}) with color {current_color}',
            )
            self._track_controller_drag_pixel(
                controller_id,
                (pixel_x, pixel_y),
                current_color,
                old_color,
            )
        else:
            self.handler.log.debug('DEBUG: No canvas or canvas_interface available')

    # ------------------------------------------------------------------
    # Canvas jumps
    # ------------------------------------------------------------------

    def canvas_jump_horizontal(
        self,
        controller_id: int,
        distance: int,
    ) -> None:
        """Jump horizontally without painting pixels."""
        self.handler.log.debug(
            f'DEBUG: canvas_jump_horizontal called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.handler.log.debug(
                f'DEBUG: No valid position found for controller {controller_id}',
            )
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_width = 0
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            canvas_width = getattr(self.handler.editor.canvas, 'pixels_across', 0)

        # Calculate new position
        end_x = start_x + distance

        # Clamp to canvas bounds
        if canvas_width > 0:
            end_x = max(0, min(end_x, canvas_width - 1))

        # Update controller position
        self.handler.editor.mode_switcher.save_controller_position(
            controller_id,
            (end_x, start_y),
        )
        self.handler.log.debug(
            f'DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({end_x},'
            f' {start_y})',
        )

    def canvas_jump_vertical(
        self,
        controller_id: int,
        distance: int,
    ) -> None:
        """Jump vertically without painting pixels."""
        self.handler.log.debug(
            f'DEBUG: canvas_jump_vertical called for controller {controller_id}, distance'
            f' {distance}',
        )

        # Get controller position from mode switcher
        position = self.handler.editor.mode_switcher.get_controller_position(controller_id)
        if not position or not position.is_valid:
            self.handler.log.debug(
                f'DEBUG: No valid position found for controller {controller_id}',
            )
            return

        start_x, start_y = position.position

        # Get canvas dimensions for boundary checking
        canvas_height = 0
        if hasattr(self.handler.editor, 'canvas') and self.handler.editor.canvas:
            canvas_height = getattr(self.handler.editor.canvas, 'pixels_tall', 0)

        # Calculate new position
        end_y = start_y + distance

        # Clamp to canvas bounds
        if canvas_height > 0:
            end_y = max(0, min(end_y, canvas_height - 1))

        # Update controller position
        self.handler.editor.mode_switcher.save_controller_position(
            controller_id,
            (start_x, end_y),
        )
        self.handler.log.debug(
            f'DEBUG: Controller {controller_id} jumped from ({start_x}, {start_y}) to ({start_x},'
            f' {end_y})',
        )
