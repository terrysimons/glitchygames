#!/usr/bin/env python3
"""Undo/Redo Manager for Bitmappy Editor.

This module provides a comprehensive undo/redo system that works across both
canvas (pixel-level) and film strip (frame-level) operations.

Commands implement the UndoRedoCommand protocol (see commands.py) and carry
their own execute/undo logic so the manager only pushes, pops, and invokes.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from bitmappy.history.commands import UndoRedoCommand

LOG = logging.getLogger(__name__)

MIN_UNDO_STACK_SIZE_FOR_COLLAPSE = 2


class OperationType(Enum):
    """Types of operations that can be undone/redone."""

    # Canvas operations
    CANVAS_PIXEL_CHANGE = 'canvas_pixel_change'
    CANVAS_BRUSH_STROKE = 'canvas_brush_stroke'
    CANVAS_FLOOD_FILL = 'canvas_flood_fill'
    CANVAS_COLOR_CHANGE = 'canvas_color_change'
    CANVAS_PAN = 'canvas_pan'

    # Film strip operations
    FILM_STRIP_FRAME_ADD = 'film_strip_frame_add'
    FILM_STRIP_FRAME_DELETE = 'film_strip_frame_delete'
    FILM_STRIP_FRAME_REORDER = 'film_strip_frame_reorder'
    FILM_STRIP_ANIMATION_ADD = 'film_strip_animation_add'
    FILM_STRIP_ANIMATION_DELETE = 'film_strip_animation_delete'
    FILM_STRIP_ANIMATION_RENAME = 'film_strip_animation_rename'

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
            LOG.debug('Clearing %s redo commands', len(self.redo_stack))
            self.redo_stack.clear()

        self.undo_stack.append(command)

        # Collapse redundant frame-create + frame-select pairs
        self._optimize_frame_create_select_commands()

        # Maintain history limit
        if len(self.undo_stack) > self.max_history:
            removed = self.undo_stack.pop(0)
            LOG.debug('Removed oldest command: %s', removed.description)

        self.at_head_of_history = True
        LOG.debug(
            'Pushed command: %s (undo stack size: %s)',
            command.description,
            len(self.undo_stack),
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

        LOG.debug('Pushed frame command for %s[%s]: %s', animation, frame, command.description)

    @staticmethod
    def _run_command_step(step: Callable[[], bool], action: str, command: UndoRedoCommand) -> bool:
        """Run a command's undo or execute, treating an exception as a failed step.

        Deliberately broad: an undo or redo must never crash the editor. The caller puts a
        failed command back on its stack, so one that raises is kept like one that returns
        False (BUGS.md #178 item 11: a raising frame command used to be dropped from the
        history, and a raising global one escaped to the caller and was lost).

        Args:
            step: command.undo or command.execute.
            action: 'undoing' or 'redoing', for the log.
            command: The command, for the log.

        Returns:
            The step's result, or False if it raised.

        """
        try:
            return step()
        except Exception:
            LOG.exception('Error %s %s', action, command.description)
            return False

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
            LOG.debug('Undoing: %s', command.description)

            success = self._run_command_step(command.undo, 'undoing', command)

            if success:
                self.redo_stack.append(command)
                self.at_head_of_history = False
                LOG.debug('Successfully undone: %s', command.description)
            else:
                LOG.warning('Failed to undo: %s', command.description)
                # Put it back if it failed (raised or returned False): history is never lost
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
            LOG.debug('Redoing: %s', command.description)

            success = self._run_command_step(command.execute, 'redoing', command)

            if success:
                self.undo_stack.append(command)
                if not self.redo_stack:
                    self.at_head_of_history = True
                LOG.debug('Successfully redone: %s', command.description)
            else:
                LOG.warning('Failed to redo: %s', command.description)
                # Put it back if it failed (raised or returned False): history is never lost
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

        command = self.frame_undo_stacks[frame_key].pop()
        self.is_undoing = True
        try:
            success = self._run_command_step(command.undo, 'undoing', command)
            if success:
                self.frame_redo_stacks[frame_key].append(command)
                LOG.debug(
                    'Undid frame command for %s[%s]: %s', animation, frame, command.description
                )
            else:
                LOG.warning('Failed to undo frame command for %s[%s]', animation, frame)
                # Put back whether it raised or returned False (BUGS.md #178 item 11)
                self.frame_undo_stacks[frame_key].append(command)
            return success
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

        command = self.frame_redo_stacks[frame_key].pop()
        self.is_redoing = True
        try:
            success = self._run_command_step(command.execute, 'redoing', command)
            if success:
                self.frame_undo_stacks[frame_key].append(command)
                LOG.debug(
                    'Redid frame command for %s[%s]: %s', animation, frame, command.description
                )
            else:
                LOG.warning('Failed to redo frame command for %s[%s]', animation, frame)
                # Put back whether it raised or returned False (BUGS.md #178 item 11)
                self.frame_redo_stacks[frame_key].append(command)
            return success
        finally:
            self.is_redoing = False

    # -- History management -------------------------------------------------

    def clear_history(self) -> None:
        """Clear all undo/redo history: the global stacks and every frame's stacks.

        The frame stacks are keyed by animation name and frame index only, so a stroke kept
        there would be undone (or redone) into any later sprite with the same names
        (BUGS.md #150). The current frame is kept: it is where the editor is, not a step, and
        the next frame selection records it as the frame to go back to.
        """
        LOG.debug('Clearing undo/redo history')
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.frame_undo_stacks.clear()
        self.frame_redo_stacks.clear()
        self.at_head_of_history = True

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
            # Each command names its frame: FrameSelectionCommand the frame selected,
            # FrameAddCommand the frame added
            last_animation = getattr(last_command, 'new_animation', None)
            last_frame = getattr(last_command, 'new_frame', None)
            second_animation = getattr(second_last_command, 'animation_name', None)
            second_frame = getattr(second_last_command, 'frame_index', None)

            if last_animation == second_animation and last_frame == second_frame:
                self.undo_stack.pop()
                LOG.debug(
                    'Optimized: removed redundant frame select for %s[%s]',
                    last_animation,
                    last_frame,
                )
