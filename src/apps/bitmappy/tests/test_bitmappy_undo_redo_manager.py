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

    def test_add_operation(self):
        """Test adding operations to history."""
        undo_data = {'pixel': (10, 20, (255, 0, 0))}
        redo_data = {'pixel': (10, 20, (0, 255, 0))}

        self.manager.add_operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            description='Test pixel change',
            undo_data=undo_data,
            redo_data=redo_data,
        )

        assert len(self.manager.undo_stack) == 1
        assert len(self.manager.redo_stack) == 0
        assert self.manager.can_undo()
        assert not self.manager.can_redo()
        assert self.manager.get_undo_description() == 'Test pixel change'

    def test_undo_operation(self, mocker):
        """Test undoing operations."""
        # Mock the callback to return True
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Test operation',
            {'pixel': (10, 20, (255, 0, 0))},
            {'pixel': (10, 20, (0, 255, 0))},
        )

        result = self.manager.undo()
        assert result is True
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 1
        assert not self.manager.can_undo()
        assert self.manager.can_redo()

    def test_redo_operation(self, mocker):
        """Test redoing operations."""
        # Mock the callback to return True
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Test operation',
            {'pixel': (10, 20, (255, 0, 0))},
            {'pixel': (10, 20, (0, 255, 0))},
        )

        # Undo first
        self.manager.undo()

        # Then redo
        result = self.manager.redo()
        assert result is True
        assert len(self.manager.undo_stack) == 1
        assert len(self.manager.redo_stack) == 0
        assert self.manager.can_undo()
        assert not self.manager.can_redo()

    def test_add_operation_clears_redo_stack(self, mocker):
        """Test that adding new operation clears redo stack."""
        # Mock the callback to return True
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        # Add initial operation
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'First operation',
            {'pixel': (10, 20, (255, 0, 0))},
            {'pixel': (10, 20, (0, 255, 0))},
        )

        # Undo it to create redo stack
        self.manager.undo()
        assert len(self.manager.redo_stack) == 1

        # Add new operation - should clear redo stack
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Second operation',
            {'pixel': (15, 25, (255, 0, 0))},
            {'pixel': (15, 25, (0, 255, 0))},
        )

        # Adding a new operation always clears the redo stack (we're branching off)
        assert len(self.manager.redo_stack) == 0  # Redo stack is cleared
        assert len(self.manager.undo_stack) == 1  # Second operation is in undo stack

    def test_max_history_limit(self):
        """Test that history is limited to max_history."""
        # Add more operations than max_history
        for i in range(7):  # More than max_history of 5
            self.manager.add_operation(
                OperationType.CANVAS_PIXEL_CHANGE,
                f'Operation {i}',
                {'data': f'undo{i}'},
                {'data': f'redo{i}'},
            )

        assert len(self.manager.undo_stack) == 5  # Should be limited to max_history
        assert self.manager.undo_stack[0].description == 'Operation 2'  # First 2 should be removed

    def test_undo_with_no_operations(self):
        """Test undo when no operations are available."""
        assert not self.manager.can_undo()
        assert self.manager.undo() is False

    def test_redo_with_no_operations(self):
        """Test redo when no operations are available."""
        assert not self.manager.can_redo()
        assert self.manager.redo() is False

    def test_clear_history(self):
        """Test clearing all history."""
        # Add some operations
        for i in range(3):
            self.manager.add_operation(
                OperationType.CANVAS_PIXEL_CHANGE,
                f'Operation {i}',
                {'data': f'undo{i}'},
                {'data': f'redo{i}'},
            )

        assert len(self.manager.undo_stack) == 3

        # Clear history
        self.manager.clear_history()
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 0

    def test_clear_history_clears_every_frames_stacks(self):
        """Test clearing history also forgets the per-frame stacks, keeping the current frame.

        They are keyed by animation name and frame index only, so a stroke left there was
        undone into the next sprite with the same names (BUGS.md #150).
        """
        for frame_index in range(2):
            self.manager.add_frame_operation(
                animation='idle',
                frame=frame_index,
                operation_type=OperationType.CANVAS_PIXEL_CHANGE,
                description=f'Paint frame {frame_index}',
                undo_data={'data': 'undo'},
                redo_data={'data': 'redo'},
            )
        self.manager.undo_frame(animation='idle', frame=1)
        self.manager.set_current_frame(animation='idle', frame=1)

        self.manager.clear_history()

        assert self.manager.frame_undo_stacks == {}
        assert self.manager.frame_redo_stacks == {}
        assert not self.manager.can_undo_frame(animation='idle', frame=0)
        assert not self.manager.can_redo_frame(animation='idle', frame=1)
        assert self.manager.current_frame == ('idle', 1)

    def test_get_history_info(self):
        """Test getting history information."""
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Test operation',
            {'data': 'undo'},
            {'data': 'redo'},
        )

        info = self.manager.get_history_info()
        assert info['undo_count'] == 1
        assert info['redo_count'] == 0
        assert info['can_undo'] is True
        assert info['can_redo'] is False
        assert info['next_undo'] == 'Test operation'
        assert info['next_redo'] is None
        assert info['max_history'] == 5

    def test_operation_with_failed_callback(self, mocker):
        """Test handling of failed callbacks."""
        # Mock a callback that returns False
        mock_callback = mocker.Mock(return_value=False)
        self.manager.set_pixel_change_callback(mock_callback)

        # Add operation
        self.manager.add_operation(
            OperationType.CANVAS_BRUSH_STROKE,
            'Test operation',
            {'pixels': [(10, 20, (0, 255, 0), (255, 0, 0))]},  # (x, y, new_color, old_color)
            {'pixels': [(10, 20, (255, 0, 0), (0, 255, 0))]},  # (x, y, old_color, new_color)
        )

        # Undo should fail
        result = self.manager.undo()
        assert result is False
        # Operation should still be in undo stack since undo failed
        assert len(self.manager.undo_stack) == 1

    def test_flood_fill_with_failed_callback_stays_undoable(self):
        """A flood fill whose pixel callback refuses pixels fails to undo and stays on the stack."""
        painted_pixels = []

        def refuse_pixel(x, y, color):
            painted_pixels.append((x, y, color))
            return False

        self.manager.set_pixel_change_callback(refuse_pixel)
        self.manager.add_operation(
            OperationType.CANVAS_FLOOD_FILL,
            'Flood fill',
            {'affected_pixels': [(1, 2), (3, 4)], 'old_color': (0, 0, 0)},
            {'affected_pixels': [(1, 2), (3, 4)], 'new_color': (9, 9, 9)},
        )

        assert self.manager.undo() is False
        assert painted_pixels == [(1, 2, (0, 0, 0)), (3, 4, (0, 0, 0))]
        assert len(self.manager.undo_stack) == 1

    def test_flood_fill_without_a_recorded_color_paints_nothing(self):
        """A flood fill whose undo data has no old color undoes without painting any pixel."""
        painted_pixels = []

        def paint_pixel(x, y, color):
            painted_pixels.append((x, y, color))
            return True

        self.manager.set_pixel_change_callback(paint_pixel)
        self.manager.add_operation(
            OperationType.CANVAS_FLOOD_FILL,
            'Flood fill',
            {'affected_pixels': [(1, 2)]},
            {'affected_pixels': [(1, 2)], 'new_color': (9, 9, 9)},
        )

        assert self.manager.undo() is True
        assert painted_pixels == []

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
