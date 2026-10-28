"""Frame operations for the Bitmappy editor.

Handles frame copy/paste, canvas panning, pixel change submission,
and single-click timer logic. Extracted from BitmapEditorScene to reduce
class complexity.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from glitchygames.clock import frame_clock_seconds

from .constants import (
    PIXEL_CHANGE_DEBOUNCE_SECONDS,
)
from .history.commands import CanvasPanCommand, FramePasteCommand

if TYPE_CHECKING:
    from .protocols import EditorContext


class FrameOperationManager:
    """Manages frame operations for the Bitmappy editor.

    Handles frame copy/paste, canvas panning, pixel change
    submission, and single-click debounce timing. Operates on editor
    state via the editor reference passed at construction time.
    """

    def __init__(self, editor: EditorContext) -> None:
        """Initialize the FrameOperationManager.

        Args:
            editor: The editor context providing access to shared state.

        """
        self.editor = editor
        self.log = logging.getLogger('game.tools.bitmappy.frame_operations')
        self.log.addHandler(logging.NullHandler())

        # State owned by FrameOperationManager
        self._frame_clipboard: dict[str, Any] | None = None

    # ──────────────────────────────────────────────────────────────────────
    # Canvas panning (see src/apps/bitmappy/src/bitmappy/panning.py)
    # ──────────────────────────────────────────────────────────────────────

    def handle_canvas_panning(self, delta_x: int, delta_y: int) -> None:
        """Move the shown frame's pixels one step (Ctrl+Shift+Arrow).

        A gesture still in progress on another frame (the frame was switched while the
        keys were held) is finished first, so it stays undoable.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)

        """
        canvas = self.editor.canvas
        if not canvas:
            self.log.warning('No canvas available for panning')
            return

        session = canvas.pan_session
        if session is not None and not session.is_for(
            animation=canvas.current_animation,
            frame_index=canvas.current_frame,
        ):
            self.finish_canvas_panning()

        canvas.pan_canvas(delta_x, delta_y)

    def finish_canvas_panning(self) -> None:
        """End the pan gesture in progress and record it as one undoable step.

        The frame already holds the panned pixels (each step writes them), so finishing
        only pushes the undo command. A gesture that left the frame as it was records
        nothing.
        """
        canvas = self.editor.canvas
        if not canvas:
            return

        session = canvas.end_panning()
        if session is None or not session.changed_the_frame:
            return

        pan_command = CanvasPanCommand(
            editor=self.editor,
            animation=session.animation,
            frame=session.frame_index,
            old_pixels=session.pixels_before,
            new_pixels=session.panned_pixels,
        )
        self.editor.undo_redo_manager.push_frame_command(
            session.animation,
            session.frame_index,
            pan_command,
        )
        self.log.debug('Recorded pan of %s[%s] for undo', session.animation, session.frame_index)

    # ──────────────────────────────────────────────────────────────────────
    # Frame copy/paste
    # ──────────────────────────────────────────────────────────────────────

    def handle_copy_frame(self) -> None:
        """Handle copying the current frame to clipboard."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            self.log.warning('No canvas available for frame copying')
            return

        if not hasattr(self.editor, 'selected_animation') or not hasattr(
            self.editor, 'selected_frame'
        ):
            self.log.warning('No frame selected for copying')
            return

        animation = self.editor.selected_animation
        frame = self.editor.selected_frame

        if animation is None or frame is None:
            self.log.warning('No animation or frame selected for copying')
            return

        if (
            not hasattr(self.editor.canvas, 'animated_sprite')
            or not self.editor.canvas.animated_sprite
        ):
            self.log.warning('No animated sprite available for frame copying')
            return

        # Get the frame data
        if animation not in self.editor.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.warning("Animation '%s' not found for copying", animation)
            return

        frames = self.editor.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning("Frame %s not found in animation '%s'", frame, animation)
            return

        frame_obj = frames[frame]

        # Create a deep copy of the frame data for the clipboard

        # Get pixel data
        pixels = frame_obj.get_pixel_data()

        # Get frame dimensions
        width, height = frame_obj.get_size()

        # Get frame duration
        duration = frame_obj.duration

        # Store frame data in clipboard
        self._frame_clipboard = {
            'pixels': pixels.copy(),
            'width': width,
            'height': height,
            'duration': duration,
            'animation': animation,
            'frame': frame,
        }

        self.log.debug("Copied frame %s from animation '%s' to clipboard", frame, animation)

    def handle_paste_frame(self) -> None:  # ruff: ignore[too-many-return-statements]
        """Handle pasting a frame from clipboard to the current frame."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            self.log.warning('No canvas available for frame pasting')
            return

        if not hasattr(self.editor, 'selected_animation') or not hasattr(
            self.editor, 'selected_frame'
        ):
            self.log.warning('No frame selected for pasting')
            return

        if not self._frame_clipboard:
            self.log.warning('No frame data in clipboard to paste')
            return

        animation = self.editor.selected_animation
        frame = self.editor.selected_frame

        if animation is None or frame is None:
            self.log.warning('No animation or frame selected for pasting')
            return

        if (
            not hasattr(self.editor.canvas, 'animated_sprite')
            or not self.editor.canvas.animated_sprite
        ):
            self.log.warning('No animated sprite available for frame pasting')
            return

        # Get the target frame
        if animation not in self.editor.canvas.animated_sprite._animations:  # type: ignore[reportPrivateUsage]
            self.log.warning("Animation '%s' not found for pasting", animation)
            return

        frames = self.editor.canvas.animated_sprite._animations[animation]  # type: ignore[reportPrivateUsage]
        if frame >= len(frames):
            self.log.warning("Frame %s not found in animation '%s'", frame, animation)
            return

        target_frame = frames[frame]

        # Check if dimensions match
        clipboard_width = self._frame_clipboard['width']
        clipboard_height = self._frame_clipboard['height']
        target_width, target_height = target_frame.get_size()

        if clipboard_width != target_width or clipboard_height != target_height:
            self.log.warning(
                'Cannot paste frame: dimension mismatch (clipboard: %sx%s, target: %sx%s)',
                clipboard_width,
                clipboard_height,
                target_width,
                target_height,
            )
            return

        # Store original frame data for undo
        original_pixels = target_frame.get_pixel_data()
        original_duration = target_frame.duration

        # Create and execute a FramePasteCommand
        paste_command = FramePasteCommand(
            editor=self.editor,
            animation=animation,
            frame=frame,
            old_pixels=original_pixels,
            old_duration=original_duration,
            new_pixels=self._frame_clipboard['pixels'],
            new_duration=self._frame_clipboard['duration'],
        )
        paste_command.execute()

        # Push onto the undo stack
        self.editor.undo_redo_manager.push_command(paste_command)

        # Update canvas display
        if hasattr(self.editor.canvas, 'force_redraw'):
            self.editor.canvas.force_redraw()

        self.log.debug('Pasted frame from clipboard to %s[%s]', animation, frame)

    # ──────────────────────────────────────────────────────────────────────
    # Pixel change submission
    # ──────────────────────────────────────────────────────────────────────

    def submit_pixel_changes_if_ready(self) -> None:
        """Submit collected pixel changes if they're ready (single click or drag ended)."""
        # Convert dict to list format for submission (dict is used for efficient O(1) deduplication
        # during drag)
        pixel_changes_list = []
        if (
            hasattr(self.editor, 'current_pixel_changes_dict')
            and self.editor.current_pixel_changes_dict
        ):
            # Convert dict values to list format
            pixel_changes_list = list(self.editor.current_pixel_changes_dict.values())
            # Clear the dict after conversion
            self.editor.current_pixel_changes_dict.clear()
        elif hasattr(self.editor, 'current_pixel_changes') and self.editor.current_pixel_changes:
            # Fallback to list if dict doesn't exist (backward compatibility)
            pixel_changes_list = self.editor.current_pixel_changes

        if pixel_changes_list and hasattr(self.editor, 'canvas_operation_tracker'):
            pixel_count = len(pixel_changes_list)

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
                    pixel_changes_list,
                )
                self.log.debug(
                    'Submitted %s pixel changes for frame %s[%s] undo/redo tracking',
                    pixel_count,
                    current_animation,
                    current_frame,
                )
            else:
                # Fall back to global tracking
                self.editor.canvas_operation_tracker.add_pixel_changes(pixel_changes_list)
                self.log.debug(
                    'Submitted %s pixel changes for global undo/redo tracking',
                    pixel_count,
                )

            # Clear both collections after submission
            if hasattr(self.editor, 'current_pixel_changes'):
                self.editor.current_pixel_changes = []
            if hasattr(self.editor, 'current_pixel_changes_dict'):
                self.editor.current_pixel_changes_dict.clear()

    def check_single_click_timer(self) -> None:
        """Check if we should submit a single click based on timer."""
        # Check dict first (new optimized path), then fallback to list
        pixel_count = 0
        if (
            hasattr(self.editor, 'current_pixel_changes_dict')
            and self.editor.current_pixel_changes_dict
        ):
            pixel_count = len(self.editor.current_pixel_changes_dict)
        elif hasattr(self.editor, 'current_pixel_changes') and self.editor.current_pixel_changes:
            pixel_count = len(self.editor.current_pixel_changes)

        # When the first pixel changed (frame clock), or None; compared with 'is not None'
        # because the frame clock reads 0.0 until the first frame closes
        pixel_change_timer = self.editor.pixel_change_timer
        if pixel_count == 1 and pixel_change_timer is not None:  # Only for single pixels
            current_time = frame_clock_seconds()
            # If more than 0.1 seconds have passed since the first pixel change, submit it
            if current_time - pixel_change_timer > PIXEL_CHANGE_DEBOUNCE_SECONDS:
                self.submit_pixel_changes_if_ready()
                self.editor.pixel_change_timer = None
