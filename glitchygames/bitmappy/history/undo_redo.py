#!/usr/bin/env python3
"""Undo/Redo Manager for Bitmappy Editor.

This module provides a comprehensive undo/redo system that works across both
canvas (pixel-level) and film strip (frame-level) operations.

Commands implement the UndoRedoCommand protocol (see commands.py) and carry
their own execute/undo logic so the manager only pushes, pops, and invokes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from glitchygames.bitmappy.history.commands import UndoRedoCommand

LOG = logging.getLogger(__name__)

MIN_UNDO_STACK_SIZE_FOR_COLLAPSE = 2


class OperationType(Enum):
    """Types of operations that can be undone/redone."""

    # Canvas operations
    CANVAS_PIXEL_CHANGE = 'canvas_pixel_change'
    CANVAS_BRUSH_STROKE = 'canvas_brush_stroke'
    CANVAS_FLOOD_FILL = 'canvas_flood_fill'
    CANVAS_COLOR_CHANGE = 'canvas_color_change'

    # Film strip operations
    FILM_STRIP_FRAME_ADD = 'film_strip_frame_add'
    FILM_STRIP_FRAME_DELETE = 'film_strip_frame_delete'
    FILM_STRIP_FRAME_REORDER = 'film_strip_frame_reorder'
    FILM_STRIP_ANIMATION_ADD = 'film_strip_animation_add'
    FILM_STRIP_ANIMATION_DELETE = 'film_strip_animation_delete'

    # Cross-area operations
    FRAME_COPY = 'frame_copy'
    FRAME_PASTE = 'frame_paste'
    ANIMATION_COPY = 'animation_copy'
    ANIMATION_PASTE = 'animation_paste'

    # Frame selection operations
    FRAME_SELECTION = 'frame_selection'

    # Controller position operations
    CONTROLLER_POSITION_CHANGE = 'controller_position_change'
    CONTROLLER_MODE_CHANGE = 'controller_mode_change'


# ---------------------------------------------------------------------------
# Legacy Operation dataclass — kept for backward compatibility with tests
# that construct Operation objects directly. New code should use commands.
# ---------------------------------------------------------------------------


@dataclass
class Operation:
    """Represents a single operation in the undo/redo history (legacy).

    Prefer creating concrete command objects from ``commands.py`` instead.
    This dataclass is retained so that existing tests continue to work.
    """

    operation_type: OperationType
    timestamp: float
    description: str
    undo_data: dict[str, Any]
    redo_data: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate operation data after initialization.

        Raises:
            ValueError: If undo_data or redo_data is empty.

        """
        if not self.undo_data:
            raise ValueError('Operation must have undo_data')
        if not self.redo_data:
            raise ValueError('Operation must have redo_data')


# ---------------------------------------------------------------------------
# UndoRedoManager
# ---------------------------------------------------------------------------


class UndoRedoManager:
    """Manages undo/redo command stacks for the Bitmappy editor.

    Commands are objects that implement the ``UndoRedoCommand`` protocol
    (``execute()`` and ``undo()`` methods).  The manager pushes and pops
    commands from the undo/redo stacks and invokes the appropriate method.
    """

    def __init__(self, max_history: int = 50) -> None:
        """Initialize the undo/redo manager.

        Args:
            max_history: Maximum number of commands to keep in history.

        """
        self.max_history = max_history

        # Global command stacks
        self.undo_stack: list[UndoRedoCommand] = []
        self.redo_stack: list[UndoRedoCommand] = []

        # Reentrancy guards
        self.is_undoing = False
        self.is_redoing = False
        self.at_head_of_history = True

        # Frame-specific command stacks for per-frame canvas edits
        self.frame_undo_stacks: dict[tuple[str, int], list[UndoRedoCommand]] = {}
        self.frame_redo_stacks: dict[tuple[str, int], list[UndoRedoCommand]] = {}

        # Current frame being edited — used by frame selection tracking
        self.current_frame: tuple[str, int] | None = None

        # Legacy callback attributes — used by _OperationAdapter for backward
        # compatibility with tests that call add_operation() + set_*_callback().
        self._pixel_change_callback: Any = None
        self._frame_selection_callback: Any = None
        self._controller_position_callback: Any = None
        self._controller_mode_callback: Any = None
        self._frame_paste_callback: Any = None
        self._add_frame_callback: Any = None
        self._delete_frame_callback: Any = None
        self._reorder_frame_callback: Any = None
        self._add_animation_callback: Any = None
        self._delete_animation_callback: Any = None

        LOG.debug('UndoRedoManager initialized with max_history=%s', max_history)

    # -- Query methods ------------------------------------------------------

    def can_undo(self) -> bool:
        """Check if undo is available.

        Returns:
            True if undo is available, False otherwise.

        """
        return len(self.undo_stack) > 0 and not self.is_undoing

    def can_redo(self) -> bool:
        """Check if redo is available.

        Returns:
            True if redo is available, False otherwise.

        """
        return len(self.redo_stack) > 0 and not self.is_redoing

    def can_undo_frame(self, animation: str, frame: int) -> bool:
        """Check if undo is available for a specific frame.

        Args:
            animation: Name of the animation.
            frame: Frame index.

        Returns:
            True if undo is available for this frame, False otherwise.

        """
        frame_key = (animation, frame)
        return (
            frame_key in self.frame_undo_stacks
            and len(self.frame_undo_stacks[frame_key]) > 0
            and not self.is_undoing
        )

    def can_redo_frame(self, animation: str, frame: int) -> bool:
        """Check if redo is available for a specific frame.

        Args:
            animation: Name of the animation.
            frame: Frame index.

        Returns:
            True if redo is available for this frame, False otherwise.

        """
        frame_key = (animation, frame)
        return (
            frame_key in self.frame_redo_stacks
            and len(self.frame_redo_stacks[frame_key]) > 0
            and not self.is_redoing
        )

    def get_undo_description(self) -> str | None:
        """Get description of the next undo operation.

        Returns:
            Description string, or None if nothing to undo.

        """
        if not self.can_undo():
            return None
        return self.undo_stack[-1].description

    def get_redo_description(self) -> str | None:
        """Get description of the next redo operation.

        Returns:
            Description string, or None if nothing to redo.

        """
        if not self.can_redo():
            return None
        return self.redo_stack[-1].description

    def set_current_frame(self, animation: str, frame: int) -> None:
        """Set the current frame being edited.

        Args:
            animation: Name of the animation.
            frame: Frame index.

        """
        self.current_frame = (animation, frame)
        LOG.debug('Current frame set to: %s[%s]', animation, frame)

    # -- Push commands onto stacks ------------------------------------------

    def push_command(self, command: UndoRedoCommand) -> None:
        """Push a command onto the global undo stack.

        This clears the redo stack (standard undo/redo branching semantics).

        Args:
            command: The command to push.

        """
        if self.is_undoing or self.is_redoing:
            LOG.debug('Skipping command push during undo/redo')
            return

        # Clear redo stack on new operation (standard branching)
        if self.redo_stack:
            LOG.debug(f'Clearing {len(self.redo_stack)} redo commands')
            self.redo_stack.clear()

        self.undo_stack.append(command)

        # Collapse redundant frame-create + frame-select pairs
        self._optimize_frame_create_select_commands()

        # Maintain history limit
        if len(self.undo_stack) > self.max_history:
            removed = self.undo_stack.pop(0)
            LOG.debug(f'Removed oldest command: {removed.description}')

        self.at_head_of_history = True
        LOG.debug(
            f'Pushed command: {command.description} (undo stack size: {len(self.undo_stack)})',
        )

    def push_frame_command(self, animation: str, frame: int, command: UndoRedoCommand) -> None:
        """Push a command onto a frame-specific undo stack.

        Args:
            animation: Animation name.
            frame: Frame index.
            command: The command to push.

        """
        frame_key = (animation, frame)

        if frame_key not in self.frame_undo_stacks:
            self.frame_undo_stacks[frame_key] = []
        if frame_key not in self.frame_redo_stacks:
            self.frame_redo_stacks[frame_key] = []

        if not self.is_undoing and not self.is_redoing:
            self.frame_redo_stacks[frame_key].clear()

        self.frame_undo_stacks[frame_key].append(command)

        if len(self.frame_undo_stacks[frame_key]) > self.max_history:
            self.frame_undo_stacks[frame_key].pop(0)

        LOG.debug(f'Pushed frame command for {animation}[{frame}]: {command.description}')

    # -- Legacy push (backward-compatible with Operation dataclass) ----------

    def add_operation(
        self,
        operation_type: OperationType,
        description: str,
        undo_data: dict[str, Any],
        redo_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Add a legacy Operation to the history (backward-compatible).

        Wraps the data in an ``_OperationAdapter`` that satisfies the
        ``UndoRedoCommand`` protocol by delegating execute/undo to callbacks
        registered via the legacy ``set_*_callback`` methods.

        .. deprecated::
            Prefer creating a concrete command from ``commands.py`` and
            calling ``push_command()`` directly.

        Args:
            operation_type: Type of operation.
            description: Human-readable description.
            undo_data: Data needed to undo the operation.
            redo_data: Data needed to redo the operation.
            context: Additional context information.

        """
        operation = Operation(
            operation_type=operation_type,
            timestamp=time.time(),
            description=description,
            undo_data=undo_data,
            redo_data=redo_data,
            context=context or {},
        )
        adapter = _OperationAdapter(operation, self)
        self.push_command(adapter)

    def add_frame_operation(
        self,
        animation: str,
        frame: int,
        operation_type: OperationType,
        description: str,
        undo_data: dict[str, Any],
        redo_data: dict[str, Any],
    ) -> None:
        """Add a legacy frame-specific Operation (backward-compatible).

        .. deprecated::
            Prefer creating a concrete command and calling
            ``push_frame_command()`` directly.

        Args:
            animation: Name of the animation.
            frame: Frame index.
            operation_type: Type of operation.
            description: Human-readable description.
            undo_data: Data needed to undo the operation.
            redo_data: Data needed to redo the operation.

        """
        operation = Operation(
            operation_type=operation_type,
            timestamp=time.time(),
            description=description,
            undo_data=undo_data,
            redo_data=redo_data,
            context={'frame': (animation, frame)},
        )
        adapter = _OperationAdapter(operation, self)
        self.push_frame_command(animation, frame, adapter)

    # -- Undo / Redo --------------------------------------------------------

    def undo(self) -> bool:
        """Undo the last global command.

        Returns:
            True if undo was successful, False otherwise.

        """
        if not self.can_undo():
            LOG.debug('Cannot undo: no commands available')
            return False

        self.is_undoing = True
        try:
            command = self.undo_stack.pop()
            LOG.debug(f'Undoing: {command.description}')

            success = command.undo()

            if success:
                self.redo_stack.append(command)
                self.at_head_of_history = False
                LOG.debug(f'Successfully undone: {command.description}')
            else:
                LOG.warning(f'Failed to undo: {command.description}')
                # Put it back if it failed
                self.undo_stack.append(command)

            return success
        finally:
            self.is_undoing = False

    def redo(self) -> bool:
        """Redo the last undone global command.

        Returns:
            True if redo was successful, False otherwise.

        """
        if not self.can_redo():
            LOG.debug('Cannot redo: no commands available')
            return False

        self.is_redoing = True
        try:
            command = self.redo_stack.pop()
            LOG.debug(f'Redoing: {command.description}')

            success = command.execute()

            if success:
                self.undo_stack.append(command)
                if not self.redo_stack:
                    self.at_head_of_history = True
                LOG.debug(f'Successfully redone: {command.description}')
            else:
                LOG.warning(f'Failed to redo: {command.description}')
                self.redo_stack.append(command)

            return success
        finally:
            self.is_redoing = False

    def undo_frame(self, animation: str, frame: int) -> bool:
        """Undo the last command for a specific frame.

        Args:
            animation: Name of the animation.
            frame: Frame index.

        Returns:
            True if undo was successful, False otherwise.

        """
        frame_key = (animation, frame)

        if frame_key not in self.frame_undo_stacks or not self.frame_undo_stacks[frame_key]:
            LOG.debug('No undo commands available for %s[%s]', animation, frame)
            return False

        if self.is_undoing or self.is_redoing:
            LOG.debug('Already in undo/redo operation')
            return False

        self.is_undoing = True
        try:
            command = self.frame_undo_stacks[frame_key].pop()
            success = command.undo()

            if success:
                self.frame_redo_stacks[frame_key].append(command)
                LOG.debug(f'Undid frame command for {animation}[{frame}]: {command.description}')
            else:
                LOG.warning('Failed to undo frame command for %s[%s]', animation, frame)
                self.frame_undo_stacks[frame_key].append(command)

            return success

        except Exception:
            LOG.exception('Error undoing frame command for %s[%s]', animation, frame)
            return False
        finally:
            self.is_undoing = False

    def redo_frame(self, animation: str, frame: int) -> bool:
        """Redo the last undone command for a specific frame.

        Args:
            animation: Name of the animation.
            frame: Frame index.

        Returns:
            True if redo was successful, False otherwise.

        """
        frame_key = (animation, frame)

        if frame_key not in self.frame_redo_stacks or not self.frame_redo_stacks[frame_key]:
            LOG.debug('No redo commands available for %s[%s]', animation, frame)
            return False

        if self.is_undoing or self.is_redoing:
            LOG.debug('Already in undo/redo operation')
            return False

        self.is_redoing = True
        try:
            command = self.frame_redo_stacks[frame_key].pop()
            success = command.execute()

            if success:
                self.frame_undo_stacks[frame_key].append(command)
                LOG.debug(f'Redid frame command for {animation}[{frame}]: {command.description}')
            else:
                LOG.warning('Failed to redo frame command for %s[%s]', animation, frame)
                self.frame_redo_stacks[frame_key].append(command)

            return success

        except Exception:
            LOG.exception('Error redoing frame command for %s[%s]', animation, frame)
            return False
        finally:
            self.is_redoing = False

    # -- History management -------------------------------------------------

    def clear_history(self) -> None:
        """Clear all undo/redo history."""
        LOG.debug('Clearing undo/redo history')
        self.undo_stack.clear()
        self.redo_stack.clear()

    def get_history_info(self) -> dict[str, Any]:
        """Get information about the current history state.

        Returns:
            Dictionary with history information.

        """
        return {
            'undo_count': len(self.undo_stack),
            'redo_count': len(self.redo_stack),
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo(),
            'next_undo': self.get_undo_description(),
            'next_redo': self.get_redo_description(),
            'max_history': self.max_history,
        }

    # -- Legacy callback setters (kept for backward-compatible tests) -------

    def set_pixel_change_callback(self, callback: Any) -> None:
        """Set the pixel change callback (legacy, used by _OperationAdapter).

        Args:
            callback: Function that takes (x, y, color) and applies the change.

        """
        self._pixel_change_callback = callback
        LOG.debug('Pixel change callback set')

    def set_film_strip_callbacks(
        self,
        add_frame_callback: Any | None = None,
        delete_frame_callback: Any | None = None,
        reorder_frame_callback: Any | None = None,
        add_animation_callback: Any | None = None,
        delete_animation_callback: Any | None = None,
    ) -> None:
        """Set film strip operation callbacks (legacy, used by _OperationAdapter).

        Args:
            add_frame_callback: Callback for adding frames.
            delete_frame_callback: Callback for deleting frames.
            reorder_frame_callback: Callback for reordering frames.
            add_animation_callback: Callback for adding animations.
            delete_animation_callback: Callback for deleting animations.

        """
        self._add_frame_callback = add_frame_callback
        self._delete_frame_callback = delete_frame_callback
        self._reorder_frame_callback = reorder_frame_callback
        self._add_animation_callback = add_animation_callback
        self._delete_animation_callback = delete_animation_callback
        LOG.debug('Film strip operation callbacks set')

    def set_frame_selection_callback(self, callback: Any) -> None:
        """Set the frame selection callback (legacy).

        Args:
            callback: Function to call for frame selection operations.

        """
        self._frame_selection_callback = callback
        LOG.debug('Frame selection callback set')

    def set_controller_position_callback(self, callback: Any) -> None:
        """Set the controller position callback (legacy).

        Args:
            callback: Function to call for controller position operations.

        """
        self._controller_position_callback = callback
        LOG.debug('Controller position callback set')

    def set_controller_mode_callback(self, callback: Any) -> None:
        """Set the controller mode callback (legacy).

        Args:
            callback: Function to call for controller mode operations.

        """
        self._controller_mode_callback = callback
        LOG.debug('Controller mode callback set')

    def set_frame_paste_callback(self, callback: Any) -> None:
        """Set the frame paste callback (legacy).

        Args:
            callback: Function to call for frame paste operations.

        """
        self._frame_paste_callback = callback
        LOG.debug('Frame paste callback set')

    # -- Internal -----------------------------------------------------------

    def _optimize_frame_create_select_commands(self) -> None:
        """Collapse redundant frame-create + frame-select pairs.

        If the last two commands are a FILM_STRIP_FRAME_ADD followed by a
        FRAME_SELECTION for the same frame, remove the selection since the
        creation implies it.
        """
        if len(self.undo_stack) < MIN_UNDO_STACK_SIZE_FOR_COLLAPSE:
            return

        last_command = self.undo_stack[-1]
        second_last_command = self.undo_stack[-2]

        if (
            last_command.operation_type == OperationType.FRAME_SELECTION
            and second_last_command.operation_type == OperationType.FILM_STRIP_FRAME_ADD
        ):
            # For command objects, compare attributes directly
            last_animation = getattr(last_command, 'new_animation', None)
            last_frame = getattr(last_command, 'new_frame', None)
            second_animation = getattr(second_last_command, 'animation_name', None)
            second_frame = getattr(second_last_command, 'frame_index', None)

            # Also support legacy _OperationAdapter objects
            if last_animation is None and isinstance(last_command, _OperationAdapter):
                last_animation = last_command.operation.redo_data.get('animation')
                last_frame = last_command.operation.redo_data.get('frame')
            if second_animation is None and isinstance(second_last_command, _OperationAdapter):
                second_animation = second_last_command.operation.redo_data.get('frame_index')
                second_frame = second_last_command.operation.redo_data.get('animation_name')

            if last_animation == second_animation and last_frame == second_frame:
                self.undo_stack.pop()
                LOG.debug(
                    'Optimized: removed redundant frame select for %s[%s]', last_animation, last_frame,
                )


# ---------------------------------------------------------------------------
# Legacy adapter — wraps an Operation dataclass so it satisfies the
# UndoRedoCommand protocol.  Used by add_operation() / add_frame_operation()
# for backward compatibility.
# ---------------------------------------------------------------------------


class _OperationAdapter:
    """Adapts a legacy ``Operation`` dataclass to the ``UndoRedoCommand`` protocol.

    This class allows old-style Operation objects (with dict-based undo_data /
    redo_data) to be pushed onto the new command stacks.  The actual execution
    is delegated to the callbacks registered on the UndoRedoManager, exactly
    like the old system worked.
    """

    def __init__(self, operation: Operation, manager: UndoRedoManager) -> None:
        """Initialize the adapter.

        Args:
            operation: The legacy Operation dataclass.
            manager: The UndoRedoManager (used to look up registered callbacks).

        """
        self._operation = operation
        self._manager = manager
        self.operation_type = operation.operation_type
        self.timestamp = operation.timestamp
        self.description = operation.description

    @property
    def operation(self) -> Operation:
        """Return the wrapped legacy Operation dataclass."""
        return self._operation

    def execute(self) -> bool:
        """Execute (redo) via the legacy dispatch path.

        Returns:
            True on success, False on failure.

        """
        return self._dispatch(is_undo=False)

    def undo(self) -> bool:
        """Undo via the legacy dispatch path.

        Returns:
            True on success, False on failure.

        """
        return self._dispatch(is_undo=True)

    def _dispatch(self, *, is_undo: bool) -> bool:
        """Route to the correct legacy callback based on operation type.

        Returns:
            True on success, False on failure.

        """
        operation = self._operation
        data = operation.undo_data if is_undo else operation.redo_data

        try:
            op_type = operation.operation_type

            # Canvas operations
            if op_type in {
                OperationType.CANVAS_PIXEL_CHANGE,
                OperationType.CANVAS_BRUSH_STROKE,
                OperationType.CANVAS_FLOOD_FILL,
                OperationType.CANVAS_COLOR_CHANGE,
            }:
                return self._dispatch_canvas(operation, data, is_undo=is_undo)

            # Film strip operations
            if op_type in {
                OperationType.FILM_STRIP_FRAME_ADD,
                OperationType.FILM_STRIP_FRAME_DELETE,
                OperationType.FILM_STRIP_FRAME_REORDER,
                OperationType.FILM_STRIP_ANIMATION_ADD,
                OperationType.FILM_STRIP_ANIMATION_DELETE,
            }:
                return self._dispatch_film_strip(operation, data, is_undo=is_undo)

            # Cross-area operations
            if op_type in {
                OperationType.FRAME_COPY,
                OperationType.FRAME_PASTE,
                OperationType.ANIMATION_COPY,
                OperationType.ANIMATION_PASTE,
            }:
                return self._dispatch_cross_area(operation, data, is_undo=is_undo)

            # Frame selection
            if op_type == OperationType.FRAME_SELECTION:
                return self._dispatch_frame_selection(data)

            # Controller position
            if op_type == OperationType.CONTROLLER_POSITION_CHANGE:
                return self._dispatch_controller_position(data, is_undo=is_undo)

            # Controller mode
            if op_type == OperationType.CONTROLLER_MODE_CHANGE:
                return self._dispatch_controller_mode(data, is_undo=is_undo)

            LOG.warning('Unknown operation type: %s', op_type)
            return False

        except Exception:
            label = 'undo' if is_undo else 'redo'
            LOG.exception(f'Error executing {label} for {operation.description}')
            return False

    # -- Canvas dispatch ----------------------------------------------------

    def _dispatch_canvas(
        self, operation: Operation, data: dict[str, Any], *, is_undo: bool,
    ) -> bool:
        callback = getattr(self._manager, '_pixel_change_callback', None)
        if not callback:
            LOG.warning('No pixel change callback set')
            return False

        if operation.operation_type == OperationType.CANVAS_PIXEL_CHANGE:
            pixel_data = data.get('pixel')
            if pixel_data:
                x, y, color = pixel_data
                result = callback(x, y, color)
                return result is not False
            return False

        if operation.operation_type == OperationType.CANVAS_BRUSH_STROKE:
            pixels = data.get('pixels', [])
            success = True
            for pixel_data in pixels:
                x, y, _other, color = pixel_data
                result = callback(x, y, color)
                if result is False:
                    success = False
            return success

        if operation.operation_type == OperationType.CANVAS_FLOOD_FILL:
            affected_pixels = data.get('affected_pixels', [])
            # Undo data stores old_color; redo data stores new_color
            color = data.get('old_color') if is_undo else data.get('new_color')
            success = True
            for x, y in affected_pixels:
                if color is not None:
                    result = callback(x, y, color)
                    if result is False:
                        success = False
            return success

        return False

    # -- Film strip dispatch ------------------------------------------------

    def _dispatch_film_strip(  # noqa: PLR0912, PLR0915
        self, operation: Operation, data: dict[str, Any], *, is_undo: bool,
    ) -> bool:
        op_type = operation.operation_type

        if op_type == OperationType.FILM_STRIP_FRAME_ADD:
            if is_undo:
                callback = getattr(self._manager, '_delete_frame_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    frame_index = data.get('frame_index')
                    if animation is not None and frame_index is not None:
                        return callback(animation, frame_index)
            else:
                callback = getattr(self._manager, '_add_frame_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    frame_index = data.get('frame_index')
                    frame_data = data.get('frame_data')
                    if animation is not None and frame_index is not None and frame_data is not None:
                        return callback(animation, frame_index, frame_data)
            return False

        if op_type == OperationType.FILM_STRIP_FRAME_DELETE:
            if is_undo:
                callback = getattr(self._manager, '_add_frame_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    frame_index = data.get('frame_index')
                    frame_data = data.get('frame_data')
                    if animation is not None and frame_index is not None and frame_data is not None:
                        return callback(animation, frame_index, frame_data)
            else:
                callback = getattr(self._manager, '_delete_frame_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    frame_index = data.get('frame_index')
                    if animation is not None and frame_index is not None:
                        return callback(animation, frame_index)
            return False

        if op_type == OperationType.FILM_STRIP_FRAME_REORDER:
            callback = getattr(self._manager, '_reorder_frame_callback', None)
            if callback:
                animation = data.get('animation')
                order = data.get('original_order') if is_undo else data.get('new_order')
                if animation and order:
                    return callback(animation, order)
            return False

        if op_type == OperationType.FILM_STRIP_ANIMATION_ADD:
            if is_undo:
                callback = getattr(self._manager, '_delete_animation_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    if animation:
                        return callback(animation)
            else:
                callback = getattr(self._manager, '_add_animation_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    animation_data = data.get('animation_data')
                    if animation and animation_data is not None:
                        return callback(animation, animation_data)
            return False

        if op_type == OperationType.FILM_STRIP_ANIMATION_DELETE:
            if is_undo:
                callback = getattr(self._manager, '_add_animation_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    animation_data = data.get('animation_data')
                    if animation and animation_data is not None:
                        return callback(animation, animation_data)
            else:
                callback = getattr(self._manager, '_delete_animation_callback', None)
                if callback:
                    animation = data.get('animation_name')
                    if animation:
                        return callback(animation)
            return False

        return False

    # -- Cross-area dispatch ------------------------------------------------

    def _dispatch_cross_area(
        self, operation: Operation, data: dict[str, Any], *, is_undo: bool,
    ) -> bool:
        if operation.operation_type == OperationType.FRAME_PASTE:
            callback = getattr(self._manager, '_frame_paste_callback', None)
            if callback:
                return callback(
                    data['animation'],
                    data['frame'],
                    data['pixels'],
                    data['duration'],
                )
            LOG.warning('No frame paste callback available')
            return False
        return False

    # -- Frame selection dispatch -------------------------------------------

    def _dispatch_frame_selection(self, data: dict[str, Any]) -> bool:
        callback = getattr(self._manager, '_frame_selection_callback', None)
        if callback:
            animation = data.get('animation')
            frame = data.get('frame')
            if animation is not None and frame is not None:
                success = callback(animation, frame)
                if success:
                    self._manager.current_frame = (animation, frame)
                return success
        LOG.warning('Frame selection callback not set')
        return False

    # -- Controller dispatch ------------------------------------------------

    def _dispatch_controller_position(self, data: dict[str, Any], *, is_undo: bool) -> bool:
        callback = getattr(self._manager, '_controller_position_callback', None)
        if callback:
            controller_id = data.get('controller_id')
            position = data.get('old_position') if is_undo else data.get('new_position')
            mode = data.get('old_mode') if is_undo else data.get('new_mode')
            if controller_id is not None and position is not None:
                return callback(controller_id, position, mode)
        LOG.warning('Controller position callback not set')
        return False

    def _dispatch_controller_mode(self, data: dict[str, Any], *, is_undo: bool) -> bool:
        callback = getattr(self._manager, '_controller_mode_callback', None)
        if callback:
            controller_id = data.get('controller_id')
            mode = data.get('old_mode') if is_undo else data.get('new_mode')
            if controller_id is not None and mode is not None:
                return callback(controller_id, mode)
        LOG.warning('Controller mode callback not set')
        return False
