#!/usr/bin/env python3
"""Operation trackers that create Command objects for the undo/redo system.

Each tracker is a thin factory: it accepts the raw data about what happened
and creates the appropriate command, then pushes it onto the UndoRedoManager.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from .commands import (
    AnimationAddCommand,
    AnimationDeleteCommand,
    BrushStrokeCommand,
    ControllerModeCommand,
    ControllerPositionCommand,
    FloodFillCommand,
    FrameAddCommand,
    FrameCopyCommand,
    FrameDeleteCommand,
    FrameReorderCommand,
    FrameSelectionCommand,
)
from .undo_redo import OperationType, UndoRedoManager

# Type alias for pixel change tuples: (x, y, old_color, new_color)
type PixelChangeTuple = tuple[int, int, tuple[int, int, int], tuple[int, int, int]]

LOG = logging.getLogger(__name__)
LOG.addHandler(logging.NullHandler())


class PixelChange:
    """Represents a single pixel change."""

    def __init__(
        self,
        x: int,
        y: int,
        old_color: tuple[int, int, int],
        new_color: tuple[int, int, int],
    ) -> None:
        """Initialize a pixel change record with position and color data."""
        self.x = x
        self.y = y
        self.old_color = old_color
        self.new_color = new_color


class CanvasOperationTracker:
    """Tracks canvas operations for undo/redo by creating command objects."""

    def __init__(self, undo_redo_manager: UndoRedoManager, editor: Any = None) -> None:
        """Initialize the canvas operation tracker.

        Args:
            undo_redo_manager: The undo/redo manager to push commands onto.
            editor: The editor context (needed by command objects).

        """
        self.undo_redo_manager = undo_redo_manager
        self.editor = editor
        self._current_brush_pixels: list[PixelChangeTuple] = []
        LOG.debug('CanvasOperationTracker initialized')

    def add_pixel_changes(
        self,
        pixels: list[tuple[int, int, tuple[int, int, int], tuple[int, int, int]]],
    ) -> None:
        """Add pixel changes to the undo/redo history.

        Args:
            pixels: List of (x, y, old_color, new_color) tuples.

        """
        if not pixels:
            return

        command = BrushStrokeCommand(
            editor=self.editor,
            pixels=pixels,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked pixel changes: {command.description}')

    def add_single_pixel_change(
        self,
        x: int,
        y: int,
        old_color: tuple[int, int, int],
        new_color: tuple[int, int, int],
    ) -> None:
        """Add a single pixel change operation.

        Args:
            x: X coordinate of the pixel.
            y: Y coordinate of the pixel.
            old_color: Previous color of the pixel.
            new_color: New color of the pixel.

        """
        self.add_pixel_changes([(x, y, old_color, new_color)])

    def start_brush_stroke(self) -> None:
        """Start tracking a brush stroke (backward-compatible API).

        Call add_pixel_change() to add pixels, then end_brush_stroke() to commit.
        """
        self._current_brush_pixels = []
        LOG.debug('Started brush stroke tracking')

    def add_pixel_change(
        self,
        x: int,
        y: int,
        old_color: tuple[int, int, int],
        new_color: tuple[int, int, int],
    ) -> None:
        """Add a pixel to the current brush stroke (backward-compatible API).

        Args:
            x: X coordinate of the pixel.
            y: Y coordinate of the pixel.
            old_color: Previous color of the pixel.
            new_color: New color of the pixel.

        """
        self._current_brush_pixels.append((x, y, old_color, new_color))
        LOG.debug('Added pixel to brush stroke: (%s, %s)', x, y)

    def end_brush_stroke(self) -> None:
        """End brush stroke and commit to history (backward-compatible API)."""
        if self._current_brush_pixels:
            self.add_pixel_changes(self._current_brush_pixels)
            LOG.debug(f'Ended brush stroke: {len(self._current_brush_pixels)} pixels')
            self._current_brush_pixels = []
        else:
            LOG.debug('Ended brush stroke with no pixels')

    def add_flood_fill(
        self,
        x: int,
        y: int,
        old_color: tuple[int, int, int],
        new_color: tuple[int, int, int],
        affected_pixels: list[tuple[int, int]],
    ) -> None:
        """Add a flood fill operation.

        Args:
            x: Starting X coordinate.
            y: Starting Y coordinate.
            old_color: Color that was replaced.
            new_color: Color that was filled.
            affected_pixels: List of all pixels that were changed.

        """
        command = FloodFillCommand(
            editor=self.editor,
            start_x=x,
            start_y=y,
            old_color=old_color,
            new_color=new_color,
            affected_pixels=affected_pixels,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked flood fill: {command.description}')

    def add_frame_pixel_changes(
        self,
        animation: str,
        frame: int,
        pixels: Sequence[PixelChange | PixelChangeTuple],
    ) -> None:
        """Add pixel changes for a specific frame.

        Args:
            animation: Name of the animation.
            frame: Frame index.
            pixels: List of pixel changes (PixelChange objects or tuples).

        """
        if not pixels:
            return

        # Normalise to tuple format
        pixel_tuples: list[PixelChangeTuple] = []
        for pixel in pixels:
            if isinstance(pixel, PixelChange):
                pixel_tuples.append((pixel.x, pixel.y, pixel.old_color, pixel.new_color))
            else:
                pixel_tuples.append(pixel)

        command = BrushStrokeCommand(
            editor=self.editor,
            pixels=pixel_tuples,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
        )

        self.undo_redo_manager.push_frame_command(animation, frame, command)
        LOG.debug(f'Tracked frame pixel changes: {command.description}')


class FilmStripOperationTracker:
    """Tracks film strip operations for undo/redo by creating command objects."""

    def __init__(self, undo_redo_manager: UndoRedoManager, editor: Any = None) -> None:
        """Initialize the film strip operation tracker.

        Args:
            undo_redo_manager: The undo/redo manager to push commands onto.
            editor: The editor context (needed by command objects).

        """
        self.undo_redo_manager = undo_redo_manager
        self.editor = editor
        LOG.debug('FilmStripOperationTracker initialized')

    def add_frame_added(
        self,
        frame_index: int,
        animation_name: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Track when a frame is added.

        Args:
            frame_index: Index where the frame was added.
            animation_name: Name of the animation.
            frame_data: Data about the added frame.

        """
        command = FrameAddCommand(
            editor=self.editor,
            frame_index=frame_index,
            animation_name=animation_name,
            frame_data=frame_data,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked frame addition: {command.description}')

    def add_frame_deleted(
        self,
        frame_index: int,
        animation_name: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Track when a frame is deleted.

        Args:
            frame_index: Index of the deleted frame.
            animation_name: Name of the animation.
            frame_data: Data about the deleted frame.

        """
        command = FrameDeleteCommand(
            editor=self.editor,
            frame_index=frame_index,
            animation_name=animation_name,
            frame_data=frame_data,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked frame deletion: {command.description}')

    def add_frame_reordered(self, old_index: int, new_index: int, animation_name: str) -> None:
        """Track when a frame is reordered.

        Args:
            old_index: Original index of the frame.
            new_index: New index of the frame.
            animation_name: Name of the animation.

        """
        command = FrameReorderCommand(
            editor=self.editor,
            old_index=old_index,
            new_index=new_index,
            animation_name=animation_name,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked frame reorder: {command.description}')

    def add_animation_added(self, animation_name: str, animation_data: dict[str, Any]) -> None:
        """Track when an animation is added.

        Args:
            animation_name: Name of the animation that was added.
            animation_data: Data about the added animation.

        """
        command = AnimationAddCommand(
            editor=self.editor,
            animation_name=animation_name,
            animation_data=animation_data,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked animation addition: {command.description}')

    def add_animation_deleted(self, animation_name: str, animation_data: dict[str, Any]) -> None:
        """Track when an animation is deleted.

        Args:
            animation_name: Name of the animation that was deleted.
            animation_data: Data about the deleted animation.

        """
        command = AnimationDeleteCommand(
            editor=self.editor,
            animation_name=animation_name,
            animation_data=animation_data,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked animation deletion: {command.description}')

    def add_frame_selection(self, animation: str, frame: int) -> None:
        """Track when a frame is selected.

        Args:
            animation: Name of the animation being selected.
            frame: Frame index being selected.

        """
        # Determine previous selection
        previous_animation = None
        previous_frame = None
        if self.undo_redo_manager.current_frame:
            previous_animation, previous_frame = self.undo_redo_manager.current_frame

        # Skip if selection unchanged
        if previous_animation == animation and previous_frame == frame:
            LOG.debug('Frame selection unchanged: %s[%s]', animation, frame)
            return

        if previous_animation is None or previous_frame is None:
            previous_animation, previous_frame = 'strip_1', 0

        command = FrameSelectionCommand(
            editor=self.editor,
            old_animation=previous_animation,
            old_frame=previous_frame,
            new_animation=animation,
            new_frame=frame,
        )

        self.undo_redo_manager.push_command(command)

        # Update current frame tracking
        self.undo_redo_manager.current_frame = (animation, frame)
        LOG.debug(f'Tracked frame selection: {command.description}')


class CrossAreaOperationTracker:
    """Tracks cross-area operations (copy/paste between frames/animations)."""

    def __init__(self, undo_redo_manager: UndoRedoManager, editor: Any = None) -> None:
        """Initialize the cross-area operation tracker.

        Args:
            undo_redo_manager: The undo/redo manager to push commands onto.
            editor: The editor context (needed by command objects).

        """
        self.undo_redo_manager = undo_redo_manager
        self.editor = editor
        LOG.debug('CrossAreaOperationTracker initialized')

    def add_frame_copied(
        self,
        source_frame: int,
        source_animation: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Track when a frame is copied.

        Args:
            source_frame: Index of the source frame.
            source_animation: Name of the source animation.
            frame_data: Data about the copied frame.

        """
        command = FrameCopyCommand(
            editor=self.editor,
            source_frame=source_frame,
            source_animation=source_animation,
            frame_data=frame_data,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked frame copy: {command.description}')

    def add_frame_pasted(
        self,
        target_frame: int,
        target_animation: str,
        frame_data: dict[str, Any],
    ) -> None:
        """Track when a frame is pasted.

        Args:
            target_frame: Index of the target frame.
            target_animation: Name of the target animation.
            frame_data: Data about the pasted frame.

        """
        # NOTE: Frame paste is now handled via FramePasteCommand created
        # directly by the editor. This method is kept for backward compatibility
        # with code that calls it, but it uses the legacy add_operation path.
        undo_data = {
            'target_frame': target_frame,
            'target_animation': target_animation,
            'action': 'paste',
        }

        redo_data = {
            'target_frame': target_frame,
            'target_animation': target_animation,
            'action': 'paste',
            'frame_data': frame_data,
        }

        description = f"Pasted frame to {target_frame} in '{target_animation}'"
        self.undo_redo_manager.add_operation(
            operation_type=OperationType.FRAME_PASTE,
            description=description,
            undo_data=undo_data,
            redo_data=redo_data,
        )

        LOG.debug('Tracked frame paste: %s', description)


class ControllerPositionOperationTracker:
    """Tracks controller position and mode changes for undo/redo."""

    def __init__(self, undo_redo_manager: UndoRedoManager, editor: Any = None) -> None:
        """Initialize the controller position operation tracker.

        Args:
            undo_redo_manager: The undo/redo manager to push commands onto.
            editor: The editor context (needed by command objects).

        """
        self.undo_redo_manager = undo_redo_manager
        self.editor = editor
        LOG.debug('ControllerPositionOperationTracker initialized')

    def add_controller_position_change(
        self,
        controller_id: int,
        old_position: tuple[int, int],
        new_position: tuple[int, int],
        old_mode: str | None = None,
        new_mode: str | None = None,
    ) -> None:
        """Track when a controller position changes.

        Args:
            controller_id: ID of the controller.
            old_position: Previous position (x, y).
            new_position: New position (x, y).
            old_mode: Previous mode (optional).
            new_mode: New mode (optional).

        """
        command = ControllerPositionCommand(
            editor=self.editor,
            controller_id=controller_id,
            old_position=old_position,
            new_position=new_position,
            old_mode=old_mode,
            new_mode=new_mode,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked controller position change: {command.description}')

    def add_controller_mode_change(self, controller_id: int, old_mode: str, new_mode: str) -> None:
        """Track when a controller mode changes.

        Args:
            controller_id: ID of the controller.
            old_mode: Previous mode.
            new_mode: New mode.

        """
        command = ControllerModeCommand(
            editor=self.editor,
            controller_id=controller_id,
            old_mode=old_mode,
            new_mode=new_mode,
        )

        self.undo_redo_manager.push_command(command)
        LOG.debug(f'Tracked controller mode change: {command.description}')
