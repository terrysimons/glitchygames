#!/usr/bin/env python3
"""Tests for controller position undo/redo functionality.

This module tests the integration between controller position tracking and the undo/redo
system, ensuring that controller movements and mode changes can be undone and redone.
"""

import pytest

from glitchygames.bitmappy.controllers.modes import ControllerMode
from glitchygames.bitmappy.history.operations import ControllerPositionOperationTracker
from glitchygames.bitmappy.history.undo_redo import OperationType, UndoRedoManager


class TestControllerPositionUndoRedo:
    """Test controller position undo/redo functionality."""

    @pytest.fixture
    def mock_scene(self, mocker):
        """Create a mock BitmapEditorScene for testing.

        Returns:
            object: The result.

        """
        scene = mocker.Mock()
        scene.undo_redo_manager = UndoRedoManager()
        scene._applying_undo_redo = False

        # Create the tracker with editor=scene so commands can reference the editor
        scene.controller_position_operation_tracker = ControllerPositionOperationTracker(
            scene.undo_redo_manager, editor=scene,
        )

        # Mock the undo/redo methods
        scene.handle_undo = mocker.Mock()
        scene.handle_redo = mocker.Mock()

        # Mock mode switcher — commands call mode_switcher methods directly
        scene.mode_switcher = mocker.Mock()
        scene.mode_switcher.get_controller_mode = mocker.Mock(return_value=ControllerMode.CANVAS)
        scene.mode_switcher.save_controller_position = mocker.Mock()
        scene.mode_switcher.get_controller_position = mocker.Mock(
            return_value=mocker.Mock(position=(5, 5)),
        )
        scene.mode_switcher.controller_modes = {}

        # Mock controller handler — commands call controller_handler methods directly
        scene.controller_handler = mocker.Mock()
        scene.controller_handler.update_controller_canvas_visual_indicator = mocker.Mock()
        scene.controller_handler.update_controller_visual_indicator_for_mode = mocker.Mock()

        # Legacy mocks (kept for backward compatibility)
        scene.update_controller_canvas_visual_indicator = mocker.Mock()
        scene.update_controller_visual_indicator_for_mode = mocker.Mock()

        return scene

    def test_controller_position_change_tracking(self, mock_scene):
        """Test that controller position changes are tracked for undo/redo."""
        controller_id = 0
        old_position = (5, 5)
        new_position = (10, 10)

        # Track controller position change
        mock_scene.controller_position_operation_tracker.add_controller_position_change(
            controller_id, old_position, new_position,
        )

        # Verify operation was added to undo stack
        assert len(mock_scene.undo_redo_manager.undo_stack) == 1
        operation = mock_scene.undo_redo_manager.undo_stack[0]
        assert operation.operation_type == OperationType.CONTROLLER_POSITION_CHANGE
        assert operation.controller_id == controller_id
        assert operation.old_position == old_position
        assert operation.new_position == new_position

    def test_controller_mode_change_tracking(self, mock_scene):
        """Test that controller mode changes are tracked for undo/redo."""
        controller_id = 0
        old_mode = 'canvas'
        new_mode = 'film_strip'

        # Track controller mode change
        mock_scene.controller_position_operation_tracker.add_controller_mode_change(
            controller_id, old_mode, new_mode,
        )

        # Verify operation was added to undo stack
        assert len(mock_scene.undo_redo_manager.undo_stack) == 1
        operation = mock_scene.undo_redo_manager.undo_stack[0]
        assert operation.operation_type == OperationType.CONTROLLER_MODE_CHANGE
        assert operation.controller_id == controller_id
        assert operation.old_mode == old_mode
        assert operation.new_mode == new_mode

    def test_controller_position_undo(self, mock_scene):
        """Test that controller position can be undone."""
        controller_id = 0
        old_position = (5, 5)
        new_position = (10, 10)

        # Track controller position change
        mock_scene.controller_position_operation_tracker.add_controller_position_change(
            controller_id, old_position, new_position,
        )

        # Verify we can undo
        assert mock_scene.undo_redo_manager.can_undo()

        # Perform undo — the command calls mode_switcher.save_controller_position directly
        success = mock_scene.undo_redo_manager.undo()
        assert success

        # Verify mode_switcher was called with the old position
        mock_scene.mode_switcher.save_controller_position.assert_called_once_with(
            controller_id, old_position,
        )

    def test_controller_position_redo(self, mock_scene):
        """Test that controller position can be redone."""
        controller_id = 0
        old_position = (5, 5)
        new_position = (10, 10)

        # Track controller position change
        mock_scene.controller_position_operation_tracker.add_controller_position_change(
            controller_id, old_position, new_position,
        )

        # Undo first
        mock_scene.undo_redo_manager.undo()

        # Verify we can redo
        assert mock_scene.undo_redo_manager.can_redo()

        # Perform redo — the command calls mode_switcher.save_controller_position directly
        success = mock_scene.undo_redo_manager.redo()
        assert success

        # Verify mode_switcher was called with the new position (most recent call)
        mock_scene.mode_switcher.save_controller_position.assert_called_with(
            controller_id, new_position,
        )

    def test_controller_mode_undo(self, mock_scene):
        """Test that controller mode can be undone."""
        controller_id = 0
        old_mode = 'canvas'
        new_mode = 'film_strip'

        # Set up the controller_modes dict so the command can call switch_to_mode
        mock_controller_mode_state = mock_scene.mode_switcher.controller_modes.setdefault(
            controller_id, mock_scene.mode_switcher,
        )

        # Track controller mode change
        mock_scene.controller_position_operation_tracker.add_controller_mode_change(
            controller_id, old_mode, new_mode,
        )

        # Verify we can undo
        assert mock_scene.undo_redo_manager.can_undo()

        # Perform undo — the command calls mode_switcher.controller_modes[id].switch_to_mode
        success = mock_scene.undo_redo_manager.undo()
        assert success

        # Verify switch_to_mode was called with the old mode
        mock_controller_mode_state.switch_to_mode.assert_called_once()
        call_args = mock_controller_mode_state.switch_to_mode.call_args
        assert call_args[0][0] == ControllerMode(old_mode)

    def test_controller_mode_redo(self, mock_scene):
        """Test that controller mode can be redone."""
        controller_id = 0
        old_mode = 'canvas'
        new_mode = 'film_strip'

        # Set up the controller_modes dict so the command can call switch_to_mode
        mock_controller_mode_state = mock_scene.mode_switcher.controller_modes.setdefault(
            controller_id, mock_scene.mode_switcher,
        )

        # Track controller mode change
        mock_scene.controller_position_operation_tracker.add_controller_mode_change(
            controller_id, old_mode, new_mode,
        )

        # Undo first
        mock_scene.undo_redo_manager.undo()

        # Verify we can redo
        assert mock_scene.undo_redo_manager.can_redo()

        # Perform redo — the command calls mode_switcher.controller_modes[id].switch_to_mode
        success = mock_scene.undo_redo_manager.redo()
        assert success

        # Verify switch_to_mode was called with the new mode (most recent call)
        last_call_args = mock_controller_mode_state.switch_to_mode.call_args
        assert last_call_args[0][0] == ControllerMode(new_mode)

    def test_controller_position_undo_redo_sequence(self, mock_scene):
        """Test a sequence of controller position undo/redo operations."""
        controller_id = 0

        # Track multiple position changes
        positions = [(5, 5), (10, 10), (15, 15), (20, 20)]
        for i in range(len(positions) - 1):
            mock_scene.controller_position_operation_tracker.add_controller_position_change(
                controller_id, positions[i], positions[i + 1],
            )

        # Verify we have operations to undo
        assert len(mock_scene.undo_redo_manager.undo_stack) == 3

        # Test undo sequence
        for i in range(3):
            assert mock_scene.undo_redo_manager.can_undo()
            success = mock_scene.undo_redo_manager.undo()
            assert success

        # Test redo sequence
        for i in range(3):
            assert mock_scene.undo_redo_manager.can_redo()
            success = mock_scene.undo_redo_manager.redo()
            assert success

    def test_controller_position_with_mode_context(self, mock_scene):
        """Test controller position tracking with mode context."""
        controller_id = 0
        old_position = (5, 5)
        new_position = (10, 10)
        old_mode = 'canvas'
        new_mode = 'canvas'

        # Track controller position change with mode context
        mock_scene.controller_position_operation_tracker.add_controller_position_change(
            controller_id, old_position, new_position, old_mode, new_mode,
        )

        # Verify operation was added with mode context as direct attributes
        operation = mock_scene.undo_redo_manager.undo_stack[0]
        assert operation.old_mode == old_mode
        assert operation.new_mode == new_mode

    def test_controller_position_undo_with_callback_error(self, mock_scene):
        """Test controller position undo when the editor raises an error."""
        controller_id = 0
        old_position = (5, 5)
        new_position = (10, 10)

        # Track controller position change
        mock_scene.controller_position_operation_tracker.add_controller_position_change(
            controller_id, old_position, new_position,
        )

        # Mock mode_switcher.save_controller_position to raise an error
        # The command catches AttributeError, KeyError, TypeError — use one of those
        mock_scene.mode_switcher.save_controller_position.side_effect = AttributeError('Test error')

        # Perform undo — should handle error gracefully
        success = mock_scene.undo_redo_manager.undo()
        assert not success  # Should return False due to error

    def test_controller_position_operation_descriptions(self, mock_scene):
        """Test that controller position operations have proper descriptions."""
        controller_id = 0
        old_position = (5, 5)
        new_position = (10, 10)
        old_mode = 'canvas'
        new_mode = 'film_strip'

        # Track controller position change
        mock_scene.controller_position_operation_tracker.add_controller_position_change(
            controller_id, old_position, new_position, old_mode, new_mode,
        )

        # Track controller mode change
        mock_scene.controller_position_operation_tracker.add_controller_mode_change(
            controller_id, old_mode, new_mode,
        )

        # Verify descriptions - check both operations
        operations = mock_scene.undo_redo_manager.undo_stack

        # Find the position change operation
        position_operation = None
        mode_operation = None

        for op in operations:
            if op.operation_type.value == 'controller_position_change':
                position_operation = op
            elif op.operation_type.value == 'controller_mode_change':
                mode_operation = op

        assert position_operation is not None
        assert mode_operation is not None

        assert 'Controller 0 moved from (5, 5) to (10, 10)' in position_operation.description
        assert 'Controller 0 mode changed from canvas to film_strip' in mode_operation.description

    def test_controller_position_undo_redo_integration(self, mock_scene):
        """Test integration between controller position tracking and undo/redo system."""
        controller_id = 0

        # Set up the controller_modes dict for mode commands
        mock_scene.mode_switcher.controller_modes.setdefault(
            controller_id, mock_scene.mode_switcher,
        )

        # Simulate controller movement
        positions = [(0, 0), (5, 5), (10, 10), (15, 15)]
        for i in range(len(positions) - 1):
            mock_scene.controller_position_operation_tracker.add_controller_position_change(
                controller_id, positions[i], positions[i + 1],
            )

        # Simulate mode changes
        modes = ['canvas', 'film_strip', 'canvas']
        for i in range(len(modes) - 1):
            mock_scene.controller_position_operation_tracker.add_controller_mode_change(
                controller_id, modes[i], modes[i + 1],
            )

        # Verify we have all operations
        assert len(mock_scene.undo_redo_manager.undo_stack) == 5  # 3 position + 2 mode changes

        # Test undo all operations
        undo_count = 0
        while mock_scene.undo_redo_manager.can_undo():
            success = mock_scene.undo_redo_manager.undo()
            assert success
            undo_count += 1

        assert undo_count == 5

        # Test redo all operations
        redo_count = 0
        while mock_scene.undo_redo_manager.can_redo():
            success = mock_scene.undo_redo_manager.redo()
            assert success
            redo_count += 1

        assert redo_count == 5
