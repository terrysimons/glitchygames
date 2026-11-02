#!/usr/bin/env python3
"""Tests for the core UndoRedoManager functionality."""

import pytest

from bitmappy.history.undo_redo import OperationType, UndoRedoManager


class TestUndoRedoManager:
    """Test the core undo/redo manager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=5)

    def test_initialization(self):
        """Test manager initialization."""
        assert self.manager.max_history == 5
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 0
        assert not self.manager.can_undo()
        assert not self.manager.can_redo()
        assert self.manager.get_undo_description() is None
        assert self.manager.get_redo_description() is None

    def test_undo_with_no_operations(self):
        """Test undo when no operations are available."""
        assert not self.manager.can_undo()
        assert self.manager.undo() is False

    def test_redo_with_no_operations(self):
        """Test redo when no operations are available."""
        assert not self.manager.can_redo()
        assert self.manager.redo() is False

    def test_frame_command_pushed_while_undoing_keeps_the_frame_redo_history(self):
        """A frame command pushed by an undo in progress does not clear that frame's redos."""

        class FrameCommand:
            """A frame command that only names itself."""

            operation_type = OperationType.CANVAS_BRUSH_STROKE
            timestamp = 0.0

            def __init__(self, description):
                self.description = description

            def execute(self):
                return True

            def undo(self):
                return True

        manager = self.manager
        frame_redo = FrameCommand('frame redo')
        manager.push_frame_command('walk', 0, FrameCommand('frame stroke'))
        manager.frame_redo_stacks['walk', 0].append(frame_redo)

        class PushesFrameCommandOnUndo(FrameCommand):
            """A global command whose undo records a frame command, as nested edits do."""

            def undo(self):
                manager.push_frame_command('walk', 0, FrameCommand('pushed during undo'))
                return True

        manager.push_command(PushesFrameCommandOnUndo('global stroke'))

        assert manager.undo() is True
        assert manager.frame_redo_stacks['walk', 0] == [frame_redo]
        assert [command.description for command in manager.frame_undo_stacks['walk', 0]] == [
            'frame stroke',
            'pushed during undo',
        ]


class _FailingCommand:
    """A command whose undo and execute fail by raising or by returning False."""

    operation_type = OperationType.CANVAS_BRUSH_STROKE
    timestamp = 0.0
    description = 'failing command'

    def __init__(self, *, raises: bool) -> None:
        self.raises = raises

    def _fail(self) -> bool:
        if self.raises:
            msg = 'command broke'
            raise RuntimeError(msg)
        return False

    def execute(self) -> bool:
        return self._fail()

    def undo(self) -> bool:
        return self._fail()


class TestFailedCommandsStayInTheHistory:
    """A command that fails its undo or redo is put back, raised or not (BUGS.md #178.11)."""

    @pytest.mark.parametrize('raises', [True, False], ids=['raises', 'returns_false'])
    def test_a_failed_global_undo_and_redo_keep_the_command(self, raises):
        manager = UndoRedoManager()
        command = _FailingCommand(raises=raises)
        manager.push_command(command)

        assert manager.undo() is False
        assert manager.undo_stack == [command]
        assert not manager.is_undoing

        manager.undo_stack.clear()
        manager.redo_stack.append(command)
        assert manager.redo() is False
        assert manager.redo_stack == [command]
        assert not manager.is_redoing

    @pytest.mark.parametrize('raises', [True, False], ids=['raises', 'returns_false'])
    def test_a_failed_frame_undo_and_redo_keep_the_command(self, raises):
        manager = UndoRedoManager()
        command = _FailingCommand(raises=raises)
        manager.push_frame_command('idle', 0, command)

        assert manager.undo_frame('idle', 0) is False
        assert manager.frame_undo_stacks['idle', 0] == [command]

        manager.frame_undo_stacks['idle', 0].clear()
        manager.frame_redo_stacks['idle', 0].append(command)
        assert manager.redo_frame('idle', 0) is False
        assert manager.frame_redo_stacks['idle', 0] == [command]
        assert not (manager.is_undoing or manager.is_redoing)

    def test_a_raising_undo_is_logged(self, caplog):
        manager = UndoRedoManager()
        manager.push_command(_FailingCommand(raises=True))

        manager.undo()

        assert 'Error undoing failing command' in caplog.text
