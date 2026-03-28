"""Frame operations for the Bitmappy editor.

Handles frame copy/paste, canvas panning commits, pixel change submission,
and single-click timer logic. Extracted from BitmapEditorScene to reduce
class complexity.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import pygame

from .constants import (
    PIXEL_CHANGE_DEBOUNCE_SECONDS,
)
from .history.commands import FramePasteCommand

if TYPE_CHECKING:
    from .protocols import EditorContext


class FrameOperationManager:
    """Manages frame operations for the Bitmappy editor.

    Handles frame copy/paste, canvas panning commits, pixel change
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
    # Surface building
    # ──────────────────────────────────────────────────────────────────────

    def _build_surface_from_canvas_pixels(self) -> pygame.Surface:
        """Build a pygame Surface from the current canvas pixel data.

        Returns:
            A new SRCALPHA surface with the canvas pixels rendered onto it.

        """
        surface = pygame.Surface(
            (self.editor.canvas.pixels_across, self.editor.canvas.pixels_tall),
            pygame.SRCALPHA,
        )
        for y in range(self.editor.canvas.pixels_tall):
            for x in range(self.editor.canvas.pixels_across):
                pixel_num = y * self.editor.canvas.pixels_across + x
                if pixel_num < len(self.editor.canvas.pixels):
                    color = self.editor.canvas.pixels[pixel_num]
                    surface.set_at((x, y), color)
        return surface

    # ──────────────────────────────────────────────────────────────────────
    # Panning commit
    # ──────────────────────────────────────────────────────────────────────

    def _commit_panned_frame_pixels(self, current_animation: str, current_frame: int) -> None:
        """Commit panned pixel data to the animation frame and its surface.

        Args:
            current_animation: Name of the current animation.
            current_frame: Index of the current frame.

        """
        frame = self.editor.canvas.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not hasattr(frame, 'pixels'):
            return

        # The current self.editor.canvas.pixels already has the panned view
        frame.pixels = list(self.editor.canvas.pixels)

        # Also update the frame.image surface for film strip thumbnails with alpha support
        frame.image = self._build_surface_from_canvas_pixels()
        self.log.debug(
            'Committed panned pixels and image to frame %s[%s]',
            current_animation,
            current_frame,
        )

    def _commit_panned_film_strip_frame(self, current_animation: str, current_frame: int) -> None:
        """Commit panned pixel data to the film strip's animation frame.

        Args:
            current_animation: Name of the current animation.
            current_frame: Index of the current frame.

        """
        if not (
            hasattr(self.editor, 'film_strips')
            and self.editor.film_strips
            and current_animation in self.editor.film_strips
        ):
            return

        film_strip = self.editor.film_strips[current_animation]
        if not (
            hasattr(film_strip, 'animated_sprite')
            and film_strip.animated_sprite
            and current_animation in film_strip.animated_sprite._animations  # type: ignore[reportPrivateUsage]
            and current_frame < len(film_strip.animated_sprite._animations[current_animation])  # type: ignore[reportPrivateUsage]
        ):
            return

        # Update the film strip's animated sprite frame data
        film_strip_frame = film_strip.animated_sprite._animations[current_animation][current_frame]  # type: ignore[reportPrivateUsage]
        if not hasattr(film_strip_frame, 'pixels'):
            return

        film_strip_frame.pixels = list(self.editor.canvas.pixels)

        # Also update the film strip frame's image surface with alpha support
        film_strip_frame.image = self._build_surface_from_canvas_pixels()
        self.log.debug(
            'Updated film strip animated sprite frame %s[%s] with pixels and image',
            current_animation,
            current_frame,
        )

    def commit_panned_buffer(self) -> None:
        """Commit the panned buffer back to the real frame data."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            return

        # Get current frame key
        frame_key = self.editor.canvas._get_current_frame_key()  # type: ignore[reportPrivateUsage]

        # Check if this frame has active panning
        if frame_key not in self.editor.canvas._frame_panning:  # type: ignore[reportPrivateUsage]
            self.log.debug('No panning state for current frame')
            return

        frame_state = self.editor.canvas._frame_panning[frame_key]  # type: ignore[reportPrivateUsage]
        if not frame_state['active']:
            self.log.debug('No active panning to commit')
            return

        # Commit the current panned pixels back to the frame
        if not (
            hasattr(self.editor.canvas, 'animated_sprite')
            and self.editor.canvas.animated_sprite
        ):
            self.log.debug('Panned buffer committed, panning state preserved for continued panning')
            return

        current_animation = self.editor.canvas.current_animation
        current_frame = self.editor.canvas.current_frame

        animations = self.editor.canvas.animated_sprite._animations  # type: ignore[reportPrivateUsage]
        if not (
            current_animation in animations
            and current_frame < len(animations[current_animation])
        ):
            self.log.debug('Panned buffer committed, panning state preserved for continued panning')
            return

        self._commit_panned_frame_pixels(current_animation, current_frame)
        self._commit_panned_film_strip_frame(current_animation, current_frame)

        # Update the film strip to reflect the pixel data changes
        self.editor.film_strip_coordinator.update_film_strips_for_animated_sprite_update()
        self.log.debug('Updated film strip for frame %s[%s]', current_animation, current_frame)

    # ──────────────────────────────────────────────────────────────────────
    # Canvas panning
    # ──────────────────────────────────────────────────────────────────────

    def handle_canvas_panning(self, delta_x: int, delta_y: int) -> None:
        """Handle canvas panning with the given delta values.

        Args:
            delta_x: Horizontal panning delta (-1, 0, or 1)
            delta_y: Vertical panning delta (-1, 0, or 1)

        """
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            self.log.warning('No canvas available for panning')
            return

        # Delegate to canvas panning method
        if hasattr(self.editor.canvas, 'pan_canvas'):
            self.editor.canvas.pan_canvas(delta_x, delta_y)
        else:
            self.log.warning('Canvas does not support panning')

    # ──────────────────────────────────────────────────────────────────────
    # Frame copy/paste
    # ──────────────────────────────────────────────────────────────────────

    def handle_copy_frame(self) -> None:
        """Handle copying the current frame to clipboard."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            self.log.warning('No canvas available for frame copying')
            return

        if (
            not hasattr(self.editor, 'selected_animation')
            or not hasattr(self.editor, 'selected_frame')
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

    def handle_paste_frame(self) -> None:  # noqa: PLR0911
        """Handle pasting a frame from clipboard to the current frame."""
        if not hasattr(self.editor, 'canvas') or not self.editor.canvas:
            self.log.warning('No canvas available for frame pasting')
            return

        if (
            not hasattr(self.editor, 'selected_animation')
            or not hasattr(self.editor, 'selected_frame')
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

        if (
            pixel_count == 1  # Only for single pixels
            and hasattr(self.editor, '_pixel_change_timer')
            and self.editor._pixel_change_timer  # type: ignore[reportPrivateUsage]
        ):
            current_time = time.time()
            # If more than 0.1 seconds have passed since the first pixel change, submit it
            if current_time - self.editor._pixel_change_timer > PIXEL_CHANGE_DEBOUNCE_SECONDS:  # type: ignore[reportPrivateUsage]
                self.submit_pixel_changes_if_ready()
                self.editor._pixel_change_timer = None  # type: ignore[reportPrivateUsage]
