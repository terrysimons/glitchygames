"""Command Pattern classes for the Bitmappy undo/redo system.

Each command encapsulates an operation and knows how to execute (redo) and undo itself.
Commands hold typed data instead of loose dict[str, Any] and carry a reference to the
EditorContext so they can apply changes directly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from glitchygames.clock import elapsed_seconds, wall_clock_epoch_seconds

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from glitchygames.bitmappy.history.undo_redo import OperationType
    from glitchygames.bitmappy.protocols import EditorContext
    from glitchygames.sprites.animated import SpriteFrame

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


# ---------------------------------------------------------------------------
# Command protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class UndoRedoCommand(Protocol):
    """Protocol that all undo/redo command objects must satisfy."""

    operation_type: OperationType
    timestamp: float
    description: str

    def execute(self) -> bool:
        """Apply (or re-apply) the change.

        Returns:
            True on success, False on failure.

        """
        ...

    def undo(self) -> bool:
        """Reverse the change.

        Returns:
            True on success, False on failure.

        """
        ...


# ---------------------------------------------------------------------------
# Mixin for commands that need to guard against recursive undo tracking
# ---------------------------------------------------------------------------


class _ApplyingUndoRedoGuard:
    """Mixin that sets ``editor._applying_undo_redo`` around a block."""

    # ``editor`` is ``Any``: see "Protected-member access" at the end of this module.
    def _guard_execute(self, editor: Any, action: Callable[[], bool]) -> bool:
        """Run *action* while ``editor._applying_undo_redo`` is True.

        Args:
            editor: The editor context.
            action: A callable that returns bool.

        Returns:
            The bool returned by *action*.

        """
        editor._applying_undo_redo = True
        try:
            return action()
        finally:
            editor._applying_undo_redo = False


# ---------------------------------------------------------------------------
# Canvas commands
# ---------------------------------------------------------------------------


class BrushStrokeCommand(_ApplyingUndoRedoGuard):
    """Command for a brush stroke (one or more pixel changes on the canvas)."""

    def __init__(
        self,
        editor: EditorContext,
        pixels: list[tuple[int, int, tuple[int, int, int], tuple[int, int, int]]],
        operation_type: OperationType,
    ) -> None:
        """Initialize a brush-stroke command.

        Args:
            editor: The editor context (satisfies EditorContext protocol).
            pixels: List of (x, y, old_color, new_color) tuples.
            operation_type: The OperationType for this command.

        """
        self.editor = editor
        self.pixels = pixels
        self.operation_type = operation_type
        self.timestamp: float = wall_clock_epoch_seconds()

        if len(pixels) == 1:
            self.description = f'Pixel change at ({pixels[0][0]}, {pixels[0][1]})'
        else:
            self.description = f'Brush stroke ({len(pixels)} pixels)'

    # -- UndoRedoCommand interface ------------------------------------------

    def execute(self) -> bool:
        """Re-apply the brush stroke (set each pixel to new_color).

        Returns:
            True on success, False on failure.



        """

        def _apply() -> bool:
            success = True
            for x, y, _old_color, new_color in self.pixels:
                if not self._set_pixel(x, y, new_color):
                    success = False
            return success

        return self._guard_execute(self.editor, _apply)

    def undo(self) -> bool:
        """Reverse the brush stroke (set each pixel back to old_color).

        Returns:
            True on success, False on failure.



        """

        def _apply() -> bool:
            success = True
            for x, y, old_color, _new_color in self.pixels:
                if not self._set_pixel(x, y, old_color):
                    success = False
            return success

        return self._guard_execute(self.editor, _apply)

    # -- internal -----------------------------------------------------------

    def _set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> bool:
        try:
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.canvas_interface.set_pixel_at(x, y, color)
                return True
            LOG.warning('Canvas not available for pixel change')
            return False  # ruff: ignore[try-consider-else]
        except Exception:
            LOG.exception('Error setting pixel at (%s, %s)', x, y)
            return False


class FloodFillCommand(_ApplyingUndoRedoGuard):
    """Command for a flood fill operation."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        editor: EditorContext,
        *,
        start_x: int,
        start_y: int,
        old_color: tuple[int, int, int],
        new_color: tuple[int, int, int],
        affected_pixels: list[tuple[int, int]],
    ) -> None:
        """Initialize a flood-fill command.

        Args:
            editor: The editor context.
            start_x: Starting X coordinate.
            start_y: Starting Y coordinate.
            old_color: Color that was replaced.
            new_color: Color that was filled.
            affected_pixels: List of all (x, y) positions that were changed.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.start_x = start_x
        self.start_y = start_y
        self.old_color = old_color
        self.new_color = new_color
        self.affected_pixels = affected_pixels
        self.operation_type = OperationType.CANVAS_FLOOD_FILL
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f'Flood fill at ({start_x}, {start_y}) - {len(affected_pixels)} pixels'

    def execute(self) -> bool:
        """Re-apply the flood fill (set all affected pixels to new_color).

        Returns:
            True on success, False on failure.



        """

        def _apply() -> bool:
            success = True
            for x, y in self.affected_pixels:
                if not self._set_pixel(x, y, self.new_color):
                    success = False
            return success

        return self._guard_execute(self.editor, _apply)

    def undo(self) -> bool:
        """Reverse the flood fill (set all affected pixels back to old_color).

        Returns:
            True on success, False on failure.



        """

        def _apply() -> bool:
            success = True
            for x, y in self.affected_pixels:
                if not self._set_pixel(x, y, self.old_color):
                    success = False
            return success

        return self._guard_execute(self.editor, _apply)

    def _set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> bool:
        try:
            if hasattr(self.editor, 'canvas') and self.editor.canvas:
                self.editor.canvas.canvas_interface.set_pixel_at(x, y, color)
                return True
            LOG.warning('Canvas not available for pixel change')
            return False  # ruff: ignore[try-consider-else]
        except Exception:
            LOG.exception('Error setting pixel at (%s, %s)', x, y)
            return False


class CanvasPanCommand(_ApplyingUndoRedoGuard):
    """Command for one pan gesture (Ctrl+Shift+Arrow) that moved a frame's pixels."""

    def __init__(
        self,
        editor: EditorContext,
        *,
        animation: str,
        frame: int,
        old_pixels: Sequence[tuple[int, ...]],
        new_pixels: Sequence[tuple[int, ...]],
    ) -> None:
        """Initialize a canvas-pan command.

        Args:
            editor: The editor context.
            animation: Animation name.
            frame: Frame index.
            old_pixels: The frame's pixels before the pan (for undo).
            new_pixels: The frame's pixels after the pan (for execute/redo).

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.animation = animation
        self.frame = frame
        self.old_pixels = tuple(old_pixels)
        self.new_pixels = tuple(new_pixels)
        self.operation_type = OperationType.CANVAS_PAN
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f'Pan {animation}[{frame}]'

    def execute(self) -> bool:
        """Re-apply the pan (set the frame's pixels to the panned pixels).

        Returns:
            True on success, False on failure.

        """
        return self._guard_execute(self.editor, lambda: self._apply_pixels(self.new_pixels))

    def undo(self) -> bool:
        """Reverse the pan (restore the frame's pixels from before it).

        Returns:
            True on success, False on failure.

        """
        return self._guard_execute(self.editor, lambda: self._apply_pixels(self.old_pixels))

    def _apply_pixels(self, pixels: Sequence[tuple[int, ...]]) -> bool:
        if not self.editor.canvas:
            LOG.warning('Canvas not available for undoing or redoing a pan')
            return False
        return self.editor.canvas.replace_frame_pixels(
            animation=self.animation,
            frame_index=self.frame,
            pixels=pixels,
        )


# ---------------------------------------------------------------------------
# Frame selection command
# ---------------------------------------------------------------------------


class FrameSelectionCommand(_ApplyingUndoRedoGuard):
    """Command for changing the selected frame."""

    def __init__(
        self,
        editor: EditorContext,
        old_animation: str,
        old_frame: int,
        new_animation: str,
        new_frame: int,
    ) -> None:
        """Initialize a frame-selection command.

        Args:
            editor: The editor context.
            old_animation: Previously selected animation name.
            old_frame: Previously selected frame index.
            new_animation: Newly selected animation name.
            new_frame: Newly selected frame index.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.old_animation = old_animation
        self.old_frame = old_frame
        self.new_animation = new_animation
        self.new_frame = new_frame
        self.operation_type = OperationType.FRAME_SELECTION
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f'Selected frame {new_animation}[{new_frame}]'

    def execute(self) -> bool:
        """Re-apply the frame selection (switch to new_animation[new_frame]).

        Returns:
            True on success, False on failure.



        """
        return self._switch_to(self.new_animation, self.new_frame)

    def undo(self) -> bool:
        """Reverse the frame selection (switch back to old_animation[old_frame]).

        Returns:
            True on success, False on failure.



        """
        return self._switch_to(self.old_animation, self.old_frame)

    def _switch_to(self, animation: str, frame: int) -> bool:
        def _apply() -> bool:
            try:
                if hasattr(self.editor, 'canvas') and self.editor.canvas:
                    self.editor.canvas.show_frame(animation, frame)
                    LOG.debug('Applied frame selection: %s[%s]', animation, frame)
                    return True
                LOG.warning('Canvas not available for frame selection')
                return False  # ruff: ignore[try-consider-else]
            except AttributeError, IndexError, KeyError, TypeError, ValueError:
                LOG.exception('Error applying frame selection')
                return False

        return self._guard_execute(self.editor, _apply)


# ---------------------------------------------------------------------------
# Frame paste command
# ---------------------------------------------------------------------------


class FramePasteCommand(_ApplyingUndoRedoGuard):
    """Command for pasting pixel data into a frame."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        editor: EditorContext,
        *,
        animation: str,
        frame: int,
        old_pixels: list[tuple[int, ...]],
        old_duration: float,
        new_pixels: list[tuple[int, ...]],
        new_duration: float,
    ) -> None:
        """Initialize a frame-paste command.

        Args:
            editor: The editor context.
            animation: Animation name.
            frame: Frame index.
            old_pixels: Original pixel data (for undo).
            old_duration: Original frame duration (for undo).
            new_pixels: Pasted pixel data (for execute/redo).
            new_duration: Pasted frame duration (for execute/redo).

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.animation = animation
        self.frame = frame
        self.old_pixels = old_pixels
        self.old_duration = old_duration
        self.new_pixels = new_pixels
        self.new_duration = new_duration
        self.operation_type = OperationType.FRAME_PASTE
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f'Paste frame to {animation}[{frame}]'

    def execute(self) -> bool:
        """Re-apply the paste (set pixel data and duration to new values).

        Returns:
            True on success, False on failure.



        """
        return self._apply_frame_data(self.new_pixels, self.new_duration)

    def undo(self) -> bool:
        """Reverse the paste (restore original pixel data and duration).

        Returns:
            True on success, False on failure.



        """
        return self._apply_frame_data(self.old_pixels, self.old_duration)

    def _apply_frame_data(self, pixels: list[tuple[int, ...]], duration: float) -> bool:
        # Deliberately broad: undo and redo must never crash the editor, so any error setting
        # the frame is logged and reported as a failed step
        try:
            applied = self._write_frame_data(pixels=pixels, duration=duration)
        except AttributeError, IndexError, KeyError, TypeError, ValueError:
            LOG.exception('Error applying frame paste')
            return False
        return applied

    def _write_frame_data(self, *, pixels: list[tuple[int, ...]], duration: float) -> bool:
        """Set the target frame's pixels and duration, and the canvas when it shows that frame.

        Args:
            pixels: The frame's pixel data.
            duration: The frame's duration.

        Returns:
            True when the frame was set, False when the canvas, animation or frame is missing.

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.warning('Canvas or animated sprite not available for frame paste')
            return False

        animations = _animation_frames(self.editor.canvas.animated_sprite)
        if self.animation not in animations:
            LOG.warning("Animation '%s' not found for frame paste", self.animation)
            return False

        frames = animations[self.animation]
        if self.frame >= len(frames):
            LOG.warning("Frame %s not found in animation '%s'", self.frame, self.animation)
            return False

        target_frame = frames[self.frame]
        target_frame.set_pixel_data(pixels)
        target_frame.duration = duration

        # Update the canvas pixels if this is the currently displayed frame
        if (
            hasattr(self.editor, 'selected_animation')
            and hasattr(self.editor, 'selected_frame')
            and self.editor.selected_animation == self.animation
            and self.editor.selected_frame == self.frame
            and hasattr(self.editor.canvas, 'pixels')
        ):
            self.editor.canvas.pixels = pixels.copy()
            if hasattr(self.editor.canvas, 'dirty_pixels'):
                self.editor.canvas.dirty_pixels = [True] * len(pixels)
            if hasattr(self.editor.canvas, 'dirty'):
                self.editor.canvas.dirty = 1

        LOG.debug('Applied frame paste to %s[%s]', self.animation, self.frame)
        return True


# ---------------------------------------------------------------------------
# Film strip frame commands
# ---------------------------------------------------------------------------


class FrameAddCommand:
    """Command for adding a frame to an animation."""

    def __init__(
        self,
        editor: EditorContext,
        frame_index: int,
        animation_name: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Initialize a frame-add command.

        Args:
            editor: The editor context.
            frame_index: Index where the frame was/will be added.
            animation_name: Name of the animation.
            frame_data: Serialised frame data (pixels, width, height, duration, and an
                optional explicit hitbox as an (x, y, width, height) tuple).

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.frame_index = frame_index
        self.animation_name = animation_name
        self.frame_data = frame_data
        self.operation_type = OperationType.FILM_STRIP_FRAME_ADD
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Added frame {frame_index} to '{animation_name}'"

    def execute(self) -> bool:
        """Add the frame (redo).

        Returns:
            True on success, False on failure.



        """
        return self._add_frame()

    def undo(self) -> bool:
        """Remove the frame (undo the addition).

        Returns:
            True on success, False on failure.



        """
        return self._delete_frame()

    # -- internal -----------------------------------------------------------

    def _add_frame(self) -> bool:
        import pygame

        # Deliberately broad: undo and redo must never crash the editor, so any error rebuilding
        # or inserting the frame is logged and reported as a failed step
        try:
            added = self._insert_frame()
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            ValueError,
            pygame.error,
        ):
            LOG.exception('Error adding frame')
            return False
        return added

    def _insert_frame(self) -> bool:
        """Rebuild the frame from frame_data and insert it at frame_index.

        Returns:
            True when the frame was inserted, False when the canvas or sprite is missing.

        """
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.warning('Canvas or animated sprite not available for frame addition')
            return False

        # SRCALPHA like the editor's own frames (FilmStripCoordinator._create_blank_frame),
        # so restored pixels keep their alpha
        surface = pygame.Surface(
            (self.frame_data['width'], self.frame_data['height']),
            pygame.SRCALPHA,
        )
        # Only an explicit frame hitbox is recorded; None keeps the hitbox fallback
        hitbox_data = self.frame_data.get('hitbox')
        new_frame = SpriteFrame(
            surface=surface,
            duration=self.frame_data.get('duration', 1.0),
            hitbox=None if hitbox_data is None else pygame.Rect(hitbox_data),
        )
        if self.frame_data.get('pixels'):
            # Row-major pixels; also keeps frame.pixels, which saves read. (PixelArray
            # has no .flat, so the previous copy raised and every restore failed; see
            # BUGS.md #51 for the same fix in AnimationAddCommand.)
            new_frame.set_pixel_data(self.frame_data['pixels'])

        self.editor.canvas.animated_sprite.add_frame(
            self.animation_name,
            new_frame,
            self.frame_index,
        )

        # Adjust canvas frame index if viewing this animation
        frame_manager = self.editor.canvas.animated_sprite.frame_manager
        if frame_manager.current_animation == self.animation_name:
            if frame_manager.current_frame >= self.frame_index:
                frame_manager.current_frame += 1

            max_frame = (
                len(_animation_frames(self.editor.canvas.animated_sprite)[self.animation_name]) - 1
            )
            if frame_manager.current_frame > max_frame:
                frame_manager.current_frame = max(0, max_frame)

            self.editor.canvas.show_frame(self.animation_name, frame_manager.current_frame)

        self.editor.film_strip_coordinator.refresh_all_film_strip_widgets(self.animation_name)
        self.editor.film_strip_coordinator.on_frame_inserted(
            self.animation_name,
            self.frame_index,
        )

        LOG.debug("Added frame %s to '%s'", self.frame_index, self.animation_name)
        return True

    def _delete_frame(self) -> bool:
        # Deliberately broad: undo and redo must never crash the editor, so any error removing
        # the frame is logged and reported as a failed step
        try:
            deleted = self._remove_frame()
        except AttributeError, IndexError, KeyError, TypeError, ValueError:
            LOG.exception('Error deleting frame')
            return False
        return deleted

    def _remove_frame(self) -> bool:
        """Remove the frame at frame_index and keep the canvas on a valid frame.

        Returns:
            True when the frame was removed, False when the canvas, animation or frame is
            missing.

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.warning('Canvas or animated sprite not available for frame deletion')
            return False

        animations = _animation_frames(self.editor.canvas.animated_sprite)
        if self.animation_name not in animations:
            LOG.warning("Animation '%s' not found", self.animation_name)
            return False

        frames = animations[self.animation_name]
        if not (0 <= self.frame_index < len(frames)):
            LOG.warning(
                "Frame index %s out of range for '%s'",
                self.frame_index,
                self.animation_name,
            )
            return False

        _stop_animation_and_adjust_frame_before_deletion(
            self.editor,
            self.animation_name,
            self.frame_index,
        )

        frames.pop(self.frame_index)

        _adjust_canvas_frame_after_deletion(self.editor, self.animation_name, self.frame_index)

        self.editor.film_strip_coordinator.refresh_all_film_strip_widgets(self.animation_name)
        self.editor.film_strip_coordinator.on_frame_removed(
            self.animation_name,
            self.frame_index,
        )

        LOG.debug("Deleted frame %s from '%s'", self.frame_index, self.animation_name)
        return True


class FrameDeleteCommand:
    """Command for deleting a frame from an animation."""

    def __init__(
        self,
        editor: EditorContext,
        frame_index: int,
        animation_name: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Initialize a frame-delete command.

        Args:
            editor: The editor context.
            frame_index: Index of the deleted frame.
            animation_name: Name of the animation.
            frame_data: Saved frame data so the frame can be restored on undo.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.frame_index = frame_index
        self.animation_name = animation_name
        self.frame_data = frame_data
        self.operation_type = OperationType.FILM_STRIP_FRAME_DELETE
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Deleted frame {frame_index} from '{animation_name}'"

    def execute(self) -> bool:
        """Delete the frame (redo).

        Returns:
            True on success, False on failure.

        """
        # FrameAddCommand.undo() performs deletion
        inverse = FrameAddCommand(
            self.editor,
            self.frame_index,
            self.animation_name,
            self.frame_data,
        )
        return inverse.undo()

    def undo(self) -> bool:
        """Re-add the frame (undo the deletion).

        Returns:
            True on success, False on failure.

        """
        # FrameAddCommand.execute() performs addition
        inverse = FrameAddCommand(
            self.editor,
            self.frame_index,
            self.animation_name,
            self.frame_data,
        )
        return inverse.execute()


class FrameReorderCommand:
    """Command for reordering a frame within an animation."""

    def __init__(
        self,
        editor: EditorContext,
        old_index: int,
        new_index: int,
        animation_name: str,
    ) -> None:
        """Initialize a frame-reorder command.

        Args:
            editor: The editor context.
            old_index: Original frame index.
            new_index: Destination frame index.
            animation_name: Name of the animation.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.old_index = old_index
        self.new_index = new_index
        self.animation_name = animation_name
        self.operation_type = OperationType.FILM_STRIP_FRAME_REORDER
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Moved frame {old_index} to {new_index} in '{animation_name}'"

    def execute(self) -> bool:
        """Reorder from old_index -> new_index (redo).

        Returns:
            True on success, False on failure.



        """
        return self._reorder(self.old_index, self.new_index)

    def undo(self) -> bool:
        """Reorder from new_index -> old_index (undo).

        Returns:
            True on success, False on failure.



        """
        return self._reorder(self.new_index, self.old_index)

    def _reorder(self, source: int, destination: int) -> bool:
        # Deliberately broad: undo and redo must never crash the editor, so any error moving
        # the frame is logged and reported as a failed step
        try:
            moved = self._move_frame(source=source, destination=destination)
        except AttributeError, IndexError, KeyError, TypeError:
            LOG.exception('Error reordering frame')
            return False
        return moved

    def _move_frame(self, *, source: int, destination: int) -> bool:
        """Move the frame at source to destination and refresh the film strip.

        Args:
            source: The frame's index before the move.
            destination: The frame's index after the move.

        Returns:
            True when the frame was moved, False when the canvas, animation or an index is
            missing.

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.warning('Canvas or animated sprite not available for frame reorder')
            return False

        animations = _animation_frames(self.editor.canvas.animated_sprite)
        if self.animation_name not in animations:
            LOG.warning("Animation '%s' not found", self.animation_name)
            return False

        frames = animations[self.animation_name]
        if not (0 <= source < len(frames) and 0 <= destination < len(frames)):
            LOG.warning("Frame indices out of range for '%s'", self.animation_name)
            return False

        frame = frames.pop(source)
        frames.insert(destination, frame)

        # Refresh the film strip widget
        if hasattr(self.editor, 'film_strip_widget') and self.editor.film_strip_widget:
            _refresh_film_strip_widget(self.editor.film_strip_widget, recalculate_layout=False)

        LOG.debug("Reordered frame %s -> %s in '%s'", source, destination, self.animation_name)
        return True


# ---------------------------------------------------------------------------
# Animation commands
# ---------------------------------------------------------------------------


def _refresh_film_strip_widgets(editor: EditorContext) -> None:
    """Refresh all film strip widgets after animation changes.

    Args:
        editor: The editor context.

    """
    if hasattr(editor, 'film_strip_widget') and editor.film_strip_widget:
        _refresh_film_strip_widget(editor.film_strip_widget, recalculate_layout=False)

    if hasattr(editor, 'film_strip_sprites') and editor.film_strip_sprites:
        for film_strip_sprite in editor.film_strip_sprites.values():
            if (
                hasattr(film_strip_sprite, 'film_strip_widget')
                and film_strip_sprite.film_strip_widget
            ):
                _refresh_film_strip_widget(
                    film_strip_sprite.film_strip_widget,
                    recalculate_layout=True,
                )
                film_strip_sprite.dirty = 1


class AnimationAddCommand:
    """Command for adding an animation."""

    def __init__(
        self,
        editor: EditorContext,
        animation_name: str,
        animation_data: dict[str, Any],
    ) -> None:
        """Initialize an animation-add command.

        Args:
            editor: The editor context.
            animation_name: Name of the animation.
            animation_data: Serialised animation data (list of frame dicts).

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.animation_name = animation_name
        self.animation_data = animation_data
        self.operation_type = OperationType.FILM_STRIP_ANIMATION_ADD
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Added animation '{animation_name}'"

    def execute(self) -> bool:
        """Add the animation (redo).

        Returns:
            True on success, False on failure.



        """
        return self._add_animation()

    def undo(self) -> bool:
        """Remove the animation (undo the addition).

        Returns:
            True on success, False on failure.



        """
        return self._delete_animation()

    def _add_animation(self) -> bool:
        import pygame

        # Deliberately broad: undo and redo must never crash the editor, so any error rebuilding
        # the animation's frames is logged and reported as a failed step
        try:
            added = self._insert_animation()
        except (
            AttributeError,
            IndexError,
            KeyError,
            TypeError,
            ValueError,
            pygame.error,
        ):
            LOG.exception('Error adding animation')
            return False
        return added

    def _insert_animation(self) -> bool:
        """Rebuild the animation's frames from animation_data and add them to the sprite.

        Returns:
            True when the animation was added, False when the canvas or sprite is missing.

        """
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.warning('Canvas or animated sprite not available for animation add')
            return False

        animations = _animation_frames(self.editor.canvas.animated_sprite)
        for frame_data in self.animation_data.get('frames', []):
            surface = pygame.Surface((frame_data['width'], frame_data['height']))
            new_frame = SpriteFrame(surface=surface, duration=frame_data.get('duration', 1.0))
            if frame_data.get('pixels'):
                # Row-major pixels; also keeps frame.pixels, which saves read. (PixelArray
                # has no .flat, so the previous copy raised and every restore failed.)
                new_frame.set_pixel_data(frame_data['pixels'])

            animations[self.animation_name] = animations.get(self.animation_name, [])
            animations[self.animation_name].append(new_frame)

        _refresh_film_strip_widgets(self.editor)

        LOG.debug("Added animation '%s'", self.animation_name)
        return True

    def _delete_animation(self) -> bool:
        # Deliberately broad: undo and redo must never crash the editor, so any error removing
        # the animation is logged and reported as a failed step
        try:
            deleted = self._remove_animation()
        except AttributeError, KeyError, TypeError:
            LOG.exception('Error deleting animation')
            return False
        return deleted

    def _remove_animation(self) -> bool:
        """Remove the animation from the sprite and rebuild the film strips.

        Returns:
            True when the animation was removed, False when the canvas, sprite or animation is
            missing.

        """
        if (
            not hasattr(self.editor, 'canvas')
            or not self.editor.canvas
            or not hasattr(self.editor.canvas, 'animated_sprite')
        ):
            LOG.warning('Canvas or animated sprite not available for animation delete')
            return False

        animations = _animation_frames(self.editor.canvas.animated_sprite)
        if self.animation_name not in animations:
            LOG.warning("Animation '%s' not found", self.animation_name)
            return False

        del animations[self.animation_name]

        _refresh_film_strip_widgets(self.editor)

        # Recreate film strips to reflect the deleted animation
        self.editor.film_strip_coordinator.on_sprite_loaded(self.editor.canvas.animated_sprite)

        LOG.debug("Deleted animation '%s'", self.animation_name)
        return True


class AnimationDeleteCommand:
    """Command for deleting an animation."""

    def __init__(
        self,
        editor: EditorContext,
        animation_name: str,
        animation_data: dict[str, Any],
    ) -> None:
        """Initialize an animation-delete command.

        Args:
            editor: The editor context.
            animation_name: Name of the animation.
            animation_data: Saved animation data so it can be restored on undo.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.animation_name = animation_name
        self.animation_data = animation_data
        self.operation_type = OperationType.FILM_STRIP_ANIMATION_DELETE
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Deleted animation '{animation_name}'"

    def execute(self) -> bool:
        """Delete the animation (redo), dropping its transitions and settings again.

        Returns:
            True on success, False on failure.

        """
        # AnimationAddCommand.undo() performs deletion
        inverse = AnimationAddCommand(self.editor, self.animation_name, self.animation_data)
        if not inverse.undo():
            return False
        animated_sprite = self.editor.canvas.animated_sprite
        animated_sprite.remove_transitions_for_animation(self.animation_name)
        animated_sprite.forget_animation_settings(self.animation_name)
        return True

    def undo(self) -> bool:
        """Re-add the animation (undo the deletion).

        The frames go back in the animation's original place in the order, with its loop flag
        and frame interval, and the transitions the delete dropped return to their original
        positions in the transition order. Commands recorded without that data (older
        captures) restore only the frames.

        Returns:
            True on success, False on failure.

        """
        # AnimationAddCommand.execute() performs addition
        inverse = AnimationAddCommand(self.editor, self.animation_name, self.animation_data)
        if not inverse.execute():
            return False
        position = self.animation_data.get('position')
        if position is None:
            return True
        animated_sprite = self.editor.canvas.animated_sprite
        animated_sprite.restore_animation_settings(
            self.animation_name,
            position=position,
            loop_flag=self.animation_data.get('loop_flag'),
            frame_interval=self.animation_data.get('frame_interval'),
        )
        animated_sprite.restore_transitions(self.animation_data.get('transitions', []))
        return True


class AnimationRenameCommand:
    """Command for renaming an animation.

    The rename goes through the coordinator's on_animation_rename, which moves the
    animation's frames, loop flag, frame interval and transitions and renames its film
    strip, so undo (renaming back) restores all of them.
    """

    def __init__(self, editor: EditorContext, old_name: str, new_name: str) -> None:
        """Initialize an animation-rename command.

        Args:
            editor: The editor context.
            old_name: The animation's name before the rename.
            new_name: The animation's name after the rename.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.old_name = old_name
        self.new_name = new_name
        self.operation_type = OperationType.FILM_STRIP_ANIMATION_RENAME
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Renamed animation '{old_name}' to '{new_name}'"

    def execute(self) -> bool:
        """Rename the animation again (redo).

        Returns:
            True on success, False on failure.

        """
        return self._rename(from_name=self.old_name, to_name=self.new_name)

    def undo(self) -> bool:
        """Give the animation its old name back.

        Returns:
            True on success, False on failure.

        """
        return self._rename(from_name=self.new_name, to_name=self.old_name)

    def _rename(self, *, from_name: str, to_name: str) -> bool:
        animated_sprite = getattr(getattr(self.editor, 'canvas', None), 'animated_sprite', None)
        if animated_sprite is None:
            LOG.warning('Canvas or animated sprite not available for animation rename')
            return False
        animations = animated_sprite._animations
        if from_name not in animations or to_name in animations:
            LOG.warning("Cannot rename animation '%s' to '%s'", from_name, to_name)
            return False
        self.editor.film_strip_coordinator.on_animation_rename(from_name, to_name)
        return to_name in animated_sprite._animations


# ---------------------------------------------------------------------------
# Controller commands
# ---------------------------------------------------------------------------


class ControllerPositionCommand(_ApplyingUndoRedoGuard):
    """Command for a controller position change."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        editor: EditorContext,
        controller_id: int,
        *,
        old_position: tuple[int, int],
        new_position: tuple[int, int],
        old_mode: str | None = None,
        new_mode: str | None = None,
    ) -> None:
        """Initialize a controller-position command.

        Args:
            editor: The editor context.
            controller_id: ID of the controller.
            old_position: Previous position (x, y).
            new_position: New position (x, y).
            old_mode: Previous mode (optional).
            new_mode: New mode (optional).

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.controller_id = controller_id
        self.old_position = old_position
        self.new_position = new_position
        self.old_mode = old_mode
        self.new_mode = new_mode
        self.operation_type = OperationType.CONTROLLER_POSITION_CHANGE
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f'Controller {controller_id} moved from {old_position} to {new_position}'

    def execute(self) -> bool:
        """Apply the new position (redo).

        Returns:
            True on success, False on failure.



        """
        return self._apply_position(self.new_position)

    def undo(self) -> bool:
        """Restore the old position (undo).

        Returns:
            True on success, False on failure.



        """
        return self._apply_position(self.old_position)

    def _apply_position(self, position: tuple[int, int]) -> bool:
        def _apply() -> bool:
            # Deliberately broad: undo and redo must never crash the editor, so any error
            # moving the controller is logged and reported as a failed step
            try:
                saved = self._save_position(position=position)
            except AttributeError, KeyError, TypeError:
                LOG.exception('Error applying controller position')
                return False
            return saved

        return self._guard_execute(self.editor, _apply)

    def _save_position(self, *, position: tuple[int, int]) -> bool:
        """Save the controller's position and redraw its canvas indicator.

        Args:
            position: The controller's position (x, y).

        Returns:
            True when the position was saved, False when the editor has no mode switcher.

        """
        if not (hasattr(self.editor, 'mode_switcher') and self.editor.mode_switcher):
            LOG.warning('Mode switcher not available for controller position')
            return False

        self.editor.mode_switcher.save_controller_position(self.controller_id, position)

        if hasattr(self.editor, 'controller_handler'):
            self.editor.controller_handler.update_controller_canvas_visual_indicator(
                self.controller_id,
            )

        LOG.debug('Applied controller position: %s -> %s', self.controller_id, position)
        return True


class ControllerModeCommand(_ApplyingUndoRedoGuard):
    """Command for a controller mode change."""

    def __init__(
        self,
        editor: EditorContext,
        controller_id: int,
        old_mode: str,
        new_mode: str,
    ) -> None:
        """Initialize a controller-mode command.

        Args:
            editor: The editor context.
            controller_id: ID of the controller.
            old_mode: Previous mode string.
            new_mode: New mode string.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.controller_id = controller_id
        self.old_mode = old_mode
        self.new_mode = new_mode
        self.operation_type = OperationType.CONTROLLER_MODE_CHANGE
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f'Controller {controller_id} mode changed from {old_mode} to {new_mode}'

    def execute(self) -> bool:
        """Apply the new mode (redo).

        Returns:
            True on success, False on failure.



        """
        return self._apply_mode(self.new_mode)

    def undo(self) -> bool:
        """Restore the old mode (undo).

        Returns:
            True on success, False on failure.



        """
        return self._apply_mode(self.old_mode)

    def _apply_mode(self, mode: str) -> bool:
        def _apply() -> bool:
            # Deliberately broad: undo and redo must never crash the editor, so any error
            # switching the controller's mode is logged and reported as a failed step
            try:
                switched = self._switch_mode(mode=mode)
            except AttributeError, KeyError, TypeError, ValueError:
                LOG.exception('Error applying controller mode')
                return False
            return switched

        return self._guard_execute(self.editor, _apply)

    def _switch_mode(self, *, mode: str) -> bool:
        """Switch the controller to the mode and redraw its visual indicator.

        Args:
            mode: The mode's string value.

        Returns:
            True when the mode was switched, False when the editor has no mode switcher or
            the mode is not a ControllerMode.

        """
        if not (hasattr(self.editor, 'mode_switcher') and self.editor.mode_switcher):
            LOG.warning('Mode switcher not available for controller mode')
            return False

        from glitchygames.bitmappy.controllers.modes import ControllerMode

        try:
            controller_mode = ControllerMode(mode)
        except ValueError:
            LOG.warning('Invalid controller mode: %s', mode)
            return False

        current_time = elapsed_seconds()
        self.editor.mode_switcher.controller_modes[self.controller_id].switch_to_mode(
            controller_mode,
            current_time,
        )

        if hasattr(self.editor, 'controller_handler'):
            self.editor.controller_handler.update_controller_visual_indicator_for_mode(
                self.controller_id,
                controller_mode,
            )

        LOG.debug('Applied controller mode: %s -> %s', self.controller_id, mode)
        return True


# ---------------------------------------------------------------------------
# Cross-area commands (copy is informational-only, paste is actionable)
# ---------------------------------------------------------------------------


class FrameCopyCommand:
    """Command for copying a frame (informational — does not modify state)."""

    def __init__(
        self,
        editor: EditorContext,
        source_frame: int,
        source_animation: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Initialize a frame-copy command.

        Args:
            editor: The editor context.
            source_frame: Index of the source frame.
            source_animation: Name of the source animation.
            frame_data: Copied frame data.

        """
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.editor = editor
        self.source_frame = source_frame
        self.source_animation = source_animation
        self.frame_data = frame_data
        self.operation_type = OperationType.FRAME_COPY
        self.timestamp: float = wall_clock_epoch_seconds()
        self.description = f"Copied frame {source_frame} from '{source_animation}'"

    def execute(self) -> bool:
        """Copy is informational — always succeeds.

        Returns:
            True on success, False on failure.



        """
        return True

    def undo(self) -> bool:
        """Copy is informational — always succeeds.

        Returns:
            True on success, False on failure.



        """
        return True


# ---------------------------------------------------------------------------
# Helper functions used by frame add/delete commands
# ---------------------------------------------------------------------------


def _stop_animation_and_adjust_frame_before_deletion(
    editor: EditorContext,
    animation_name: str,
    frame_index: int,
) -> None:
    """Stop animation playback and adjust the frame index before frame deletion.

    Args:
        editor: The editor context.
        animation_name: Name of the animation being modified.
        frame_index: Index of the frame about to be deleted.

    """
    if not (
        hasattr(editor.canvas.animated_sprite, 'frame_manager')
        and editor.canvas.animated_sprite.frame_manager.current_animation == animation_name
    ):
        return

    _stop_playback(editor.canvas.animated_sprite)

    if editor.canvas.animated_sprite.frame_manager.current_frame >= frame_index:
        if editor.canvas.animated_sprite.frame_manager.current_frame > 0:
            editor.canvas.animated_sprite.frame_manager.current_frame -= 1
        else:
            editor.canvas.animated_sprite.frame_manager.current_frame = 0


def _adjust_canvas_frame_after_deletion(
    editor: EditorContext, animation_name: str, frame_index: int
) -> None:
    """Clamp and show the canvas frame after a frame has been deleted.

    The shown frame was already moved back past the deleted one by
    _stop_animation_and_adjust_frame_before_deletion; moving it back here too moved the
    canvas back two frames (BUGS.md #94), so this only clamps and shows it.

    Args:
        editor: The editor context.
        animation_name: Name of the animation that was modified.
        frame_index: Index of the frame that was deleted.

    """
    frame_manager = editor.canvas.animated_sprite.frame_manager
    if frame_manager.current_animation != animation_name:
        return

    LOG.debug('Showing frame %s after deleting frame %s', frame_manager.current_frame, frame_index)

    max_frame = len(_animation_frames(editor.canvas.animated_sprite)[animation_name]) - 1
    if frame_manager.current_frame > max_frame:
        frame_manager.current_frame = max(0, max_frame)

    editor.canvas.show_frame(animation_name, frame_manager.current_frame)


# ---------------------------------------------------------------------------
# Protected-member access
#
# The commands reach into protected members of AnimatedSprite (``_animations``,
# ``_is_playing``) and FilmStripWidget (``_initialize_preview_animations``,
# ``_calculate_layout``, ``_create_film_tabs``), and the guard writes the editor's protected
# ``_applying_undo_redo``. Their test stand-ins provide only these protected names, so the
# commands keep using them. With a typed receiver each access is a basedpyright
# reportPrivateUsage error, so these helpers (and ``_ApplyingUndoRedoGuard._guard_execute``)
# take ``Any``; everything else in this module is typed.
# ---------------------------------------------------------------------------


def _animation_frames(animated_sprite: Any) -> dict[str, list[SpriteFrame]]:
    """Return the sprite's own animation dict (``_animations``, not a copy).

    Args:
        animated_sprite: The canvas's AnimatedSprite.

    Returns:
        The animation name to frames mapping the sprite plays from.

    """
    return animated_sprite._animations


def _stop_playback(animated_sprite: Any) -> None:
    """Stop the sprite's playback without resetting its frame.

    Args:
        animated_sprite: The canvas's AnimatedSprite.

    """
    animated_sprite._is_playing = False


def _refresh_film_strip_widget(film_strip_widget: Any, *, recalculate_layout: bool) -> None:
    """Rebuild a film strip widget's previews, layout and film tabs, and mark it dirty.

    Args:
        film_strip_widget: The FilmStripWidget to refresh.
        recalculate_layout: Recalculate the frame layout before updating it.

    """
    film_strip_widget._initialize_preview_animations()
    if recalculate_layout:
        film_strip_widget._calculate_layout()
    film_strip_widget.update_layout()
    film_strip_widget._create_film_tabs()
    film_strip_widget.mark_dirty()
