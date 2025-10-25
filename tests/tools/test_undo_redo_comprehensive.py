#!/usr/bin/env python3
"""Comprehensive tests for the updated undo/redo system with frame-specific operations."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from glitchygames.tools.undo_redo_manager import (
    UndoRedoManager, OperationType, Operation
)
from glitchygames.tools.operation_history import (
    CanvasOperationTracker, FilmStripOperationTracker, CrossAreaOperationTracker,
    PixelChange, BrushStroke, FrameOperation
)


class TestUndoRedoManagerBasic:
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
        undo_data = {"pixel": (10, 20, (255, 0, 0))}
        redo_data = {"pixel": (10, 20, (0, 255, 0))}

        self.manager.add_operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            description="Test pixel change",
            undo_data=undo_data,
            redo_data=redo_data
        )

        assert len(self.manager.undo_stack) == 1
        assert len(self.manager.redo_stack) == 0
        assert self.manager.can_undo()
        assert not self.manager.can_redo()
        assert self.manager.get_undo_description() == "Test pixel change"

    def test_undo_operation(self):
        """Test undoing operations."""
        # Mock the callback to return True
        mock_callback = Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "Test operation",
            {"pixel": (10, 20, (255, 0, 0))},
            {"pixel": (10, 20, (0, 255, 0))}
        )

        result = self.manager.undo()
        assert result is True
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 1
        assert not self.manager.can_undo()
        assert self.manager.can_redo()

    def test_redo_operation(self):
        """Test redoing operations."""
        # Mock the callback to return True
        mock_callback = Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "Test operation",
            {"pixel": (10, 20, (255, 0, 0))},
            {"pixel": (10, 20, (0, 255, 0))}
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


class TestFrameSpecificUndoRedo:
    """Test frame-specific undo/redo functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()

    def test_set_current_frame(self):
        """Test setting the current frame."""
        self.manager.set_current_frame("walk_animation", 2)
        assert self.manager.current_frame == ("walk_animation", 2)

    def test_add_frame_operation(self):
        """Test adding operations to frame-specific stacks."""
        self.manager.add_frame_operation(
            animation="walk_animation",
            frame=1,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description="Frame-specific brush stroke",
            undo_data={"pixels": [(10, 20, (255, 0, 0))]},
            redo_data={"pixels": [(10, 20, (0, 255, 0))]}
        )

        frame_key = ("walk_animation", 1)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1
        assert len(self.manager.frame_redo_stacks[frame_key]) == 0

    def test_can_undo_frame(self):
        """Test checking if frame-specific undo is available."""
        # No operations initially
        assert not self.manager.can_undo_frame("walk_animation", 1)

        # Add frame operation
        self.manager.add_frame_operation(
            animation="walk_animation",
            frame=1,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description="Test operation",
            undo_data={"pixels": []},
            redo_data={"pixels": []}
        )

        assert self.manager.can_undo_frame("walk_animation", 1)
        assert not self.manager.can_undo_frame("run_animation", 1)  # Different animation
        assert not self.manager.can_undo_frame("walk_animation", 2)  # Different frame

    def test_can_redo_frame(self):
        """Test checking if frame-specific redo is available."""
        # Add and undo frame operation
        self.manager.add_frame_operation(
            animation="walk_animation",
            frame=1,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description="Test operation",
            undo_data={"pixels": []},
            redo_data={"pixels": []}
        )

        assert not self.manager.can_redo_frame("walk_animation", 1)

        # Undo the operation
        self.manager.undo_frame("walk_animation", 1)

        assert self.manager.can_redo_frame("walk_animation", 1)
        assert not self.manager.can_redo_frame("run_animation", 1)  # Different animation
        assert not self.manager.can_redo_frame("walk_animation", 2)  # Different frame

    def test_undo_frame(self):
        """Test frame-specific undo."""
        # Mock the callback
        mock_callback = Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        # Add frame operation
        self.manager.add_frame_operation(
            animation="walk_animation",
            frame=1,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description="Test operation",
            undo_data={"pixels": [(10, 20, (255, 0, 0))]},
            redo_data={"pixels": [(10, 20, (0, 255, 0))]}
        )

        # Undo the operation
        result = self.manager.undo_frame("walk_animation", 1)

        assert result is True
        frame_key = ("walk_animation", 1)
        assert len(self.manager.frame_undo_stacks[frame_key]) == 0
        assert len(self.manager.frame_redo_stacks[frame_key]) == 1
        mock_callback.assert_called_once()

    def test_redo_frame(self):
        """Test frame-specific redo."""
        # Mock the callback
        mock_callback = Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        # Add frame operation and undo it
        self.manager.add_frame_operation(
            animation="walk_animation",
            frame=1,
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            description="Test operation",
            undo_data={"pixels": [(10, 20, (255, 0, 0))]},
            redo_data={"pixels": [(10, 20, (0, 255, 0))]}
        )

        self.manager.undo_frame("walk_animation", 1)

        # Redo the operation
        result = self.manager.redo_frame("walk_animation", 1)

        assert result is True
        frame_key = ("walk_animation", 1)
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1
        assert len(self.manager.frame_redo_stacks[frame_key]) == 0
        assert mock_callback.call_count == 2  # Once for undo, once for redo


class TestCanvasOperationTracker:
    """Test canvas operation tracking with frame-specific operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = CanvasOperationTracker(self.manager)

    def test_add_frame_pixel_changes(self):
        """Test adding frame-specific pixel changes."""
        pixels = [
            PixelChange(10, 20, (255, 0, 0), (0, 255, 0)),
            PixelChange(11, 20, (255, 0, 0), (0, 255, 0))
        ]

        self.tracker.add_frame_pixel_changes("walk_animation", 1, pixels)

        frame_key = ("walk_animation", 1)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1

        operation = self.manager.frame_undo_stacks[frame_key][0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        assert "walk_animation[1]" in operation.description

    def test_add_frame_pixel_changes_with_tuples(self):
        """Test adding frame-specific pixel changes with tuple format."""
        pixels = [
            (10, 20, (255, 0, 0), (0, 255, 0)),
            (11, 20, (255, 0, 0), (0, 255, 0))
        ]

        self.tracker.add_frame_pixel_changes("run_animation", 2, pixels)

        frame_key = ("run_animation", 2)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1

        operation = self.manager.frame_undo_stacks[frame_key][0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        assert "run_animation[2]" in operation.description

    def test_add_pixel_changes_global_fallback(self):
        """Test that global tracking still works as fallback."""
        pixels = [
            (10, 20, (255, 0, 0), (0, 255, 0))
        ]

        self.tracker.add_pixel_changes(pixels)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE


class TestFilmStripOperationTracker:
    """Test film strip operation tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = FilmStripOperationTracker(self.manager)

    def test_add_frame_added(self):
        """Test tracking frame addition."""
        frame_data = {
            "width": 32,
            "height": 32,
            "pixels": [255, 0, 0] * 32 * 32,
            "duration": 1.0
        }
        self.tracker.add_frame_added(2, "walk_animation", frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_ADD
        assert "Added frame 2 to 'walk_animation'" in operation.description

    def test_add_frame_deleted(self):
        """Test tracking frame deletion."""
        frame_data = {
            "width": 32,
            "height": 32,
            "pixels": [255, 0, 0] * 32 * 32,
            "duration": 1.0
        }
        self.tracker.add_frame_deleted(1, "run_animation", frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_DELETE
        assert "Deleted frame 1 from 'run_animation'" in operation.description

    def test_add_animation_added(self):
        """Test tracking animation addition."""
        animation_data = {
            "frames": [
                {"width": 32, "height": 32, "pixels": [255, 0, 0] * 32 * 32, "duration": 1.0},
                {"width": 32, "height": 32, "pixels": [0, 255, 0] * 32 * 32, "duration": 1.0}
            ]
        }
        self.tracker.add_animation_added("new_animation", animation_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_ADD
        assert "Added animation 'new_animation'" in operation.description

    def test_add_animation_deleted(self):
        """Test tracking animation deletion."""
        animation_data = {
            "frames": [
                {"width": 32, "height": 32, "pixels": [255, 0, 0] * 32 * 32, "duration": 1.0}
            ]
        }
        self.tracker.add_animation_deleted("old_animation", animation_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_DELETE
        assert "Deleted animation 'old_animation'" in operation.description


class TestUndoRedoCallbacks:
    """Test undo/redo callback functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.mock_pixel_callback = Mock(return_value=True)
        self.mock_add_frame_callback = Mock(return_value=True)
        self.mock_delete_frame_callback = Mock(return_value=True)
        self.mock_reorder_frame_callback = Mock(return_value=True)
        self.mock_add_animation_callback = Mock(return_value=True)
        self.mock_delete_animation_callback = Mock(return_value=True)

        self.manager.set_pixel_change_callback(self.mock_pixel_callback)
        self.manager.set_film_strip_callbacks(
            add_frame_callback=self.mock_add_frame_callback,
            delete_frame_callback=self.mock_delete_frame_callback,
            reorder_frame_callback=self.mock_reorder_frame_callback,
            add_animation_callback=self.mock_add_animation_callback,
            delete_animation_callback=self.mock_delete_animation_callback
        )

    def test_canvas_operation_callbacks(self):
        """Test that canvas operations call the correct callbacks."""
        # Test brush stroke undo
        self.manager.add_operation(
            OperationType.CANVAS_BRUSH_STROKE,
            "Test brush stroke",
            {"pixels": [(10, 20, (255, 0, 0))]},
            {"pixels": [(10, 20, (0, 255, 0))]}
        )

        self.manager.undo()
        self.mock_pixel_callback.assert_called()

    def test_film_strip_operation_callbacks(self):
        """Test that film strip operations call the correct callbacks."""
        # Test frame add undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            "Test frame add",
            {"frame_index": 1, "animation_name": "test", "frame_data": {}},
            {"frame_index": 1, "animation_name": "test", "frame_data": {}}
        )

        self.manager.undo()
        self.mock_delete_frame_callback.assert_called()

        # Test frame delete undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_DELETE,
            "Test frame delete",
            {"frame_index": 1, "animation_name": "test", "frame_data": {}},
            {"frame_index": 1, "animation_name": "test", "frame_data": {}}
        )

        self.manager.undo()
        self.mock_add_frame_callback.assert_called()

        # Test animation add undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            "Test animation add",
            {"animation_name": "test", "animation_data": {}},
            {"animation_name": "test", "animation_data": {}}
        )

        self.manager.undo()
        self.mock_delete_animation_callback.assert_called()

        # Test animation delete undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            "Test animation delete",
            {"animation_name": "test", "animation_data": {}},
            {"animation_name": "test", "animation_data": {}}
        )

        self.manager.undo()
        self.mock_add_animation_callback.assert_called()


class TestIntegrationScenarios:
    """Test complex integration scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.canvas_tracker = CanvasOperationTracker(self.manager)
        self.film_tracker = FilmStripOperationTracker(self.manager)

    def test_mixed_operations_undo_sequence(self):
        """Test undoing a sequence of mixed canvas and film strip operations."""
        # Set up callbacks
        mock_pixel_callback = Mock(return_value=True)
        mock_add_frame_callback = Mock(return_value=True)
        mock_delete_frame_callback = Mock(return_value=True)

        self.manager.set_pixel_change_callback(mock_pixel_callback)
        self.manager.set_film_strip_callbacks(
            add_frame_callback=mock_add_frame_callback,
            delete_frame_callback=mock_delete_frame_callback,
            reorder_frame_callback=Mock(return_value=True),
            add_animation_callback=Mock(return_value=True),
            delete_animation_callback=Mock(return_value=True)
        )

        # Add canvas operation
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0))]
        self.canvas_tracker.add_pixel_changes(pixels)

        # Add frame operation
        frame_data = {"width": 32, "height": 32, "pixels": [], "duration": 1.0}
        self.film_tracker.add_frame_added(1, "walk_animation", frame_data)

        # Add another canvas operation
        pixels2 = [(15, 25, (0, 0, 255), (255, 255, 0))]
        self.canvas_tracker.add_pixel_changes(pixels2)

        # Should have 3 operations in global stack
        assert len(self.manager.undo_stack) == 3

        # Undo all operations
        assert self.manager.undo() is True  # Canvas operation
        assert self.manager.undo() is True  # Frame operation
        assert self.manager.undo() is True  # Canvas operation

        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 3

    def test_frame_specific_vs_global_operations(self):
        """Test that frame-specific and global operations work independently."""
        # Add global operation
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0))]
        self.canvas_tracker.add_pixel_changes(pixels)

        # Add frame-specific operation
        frame_pixels = [PixelChange(15, 25, (0, 0, 255), (255, 255, 0))]
        self.canvas_tracker.add_frame_pixel_changes("walk_animation", 1, frame_pixels)

        # Global stack should have 1 operation
        assert len(self.manager.undo_stack) == 1

        # Frame-specific stack should have 1 operation
        frame_key = ("walk_animation", 1)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1

        # Can undo both independently
        assert self.manager.can_undo()
        assert self.manager.can_undo_frame("walk_animation", 1)

    def test_operation_descriptions(self):
        """Test that operation descriptions are informative."""
        # Test canvas operation description
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0))]
        self.canvas_tracker.add_pixel_changes(pixels)

        operation = self.manager.undo_stack[0]
        assert "Pixel change" in operation.description
        assert "(10, 20)" in operation.description

        # Test frame-specific operation description
        frame_pixels = [PixelChange(15, 25, (0, 0, 255), (255, 255, 0))]
        self.canvas_tracker.add_frame_pixel_changes("walk_animation", 1, frame_pixels)

        frame_key = ("walk_animation", 1)
        frame_operation = self.manager.frame_undo_stacks[frame_key][0]
        assert "walk_animation[1]" in frame_operation.description
        assert "pixel changes" in frame_operation.description


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()

    def test_undo_with_no_operations(self):
        """Test undo when no operations are available."""
        assert not self.manager.can_undo()
        assert self.manager.undo() is False

    def test_redo_with_no_operations(self):
        """Test redo when no operations are available."""
        assert not self.manager.can_redo()
        assert self.manager.redo() is False

    def test_frame_undo_with_no_operations(self):
        """Test frame undo when no operations are available."""
        assert not self.manager.can_undo_frame("test_animation", 1)
        assert self.manager.undo_frame("test_animation", 1) is False

    def test_frame_redo_with_no_operations(self):
        """Test frame redo when no operations are available."""
        assert not self.manager.can_redo_frame("test_animation", 1)
        assert self.manager.redo_frame("test_animation", 1) is False

    def test_max_history_limit(self):
        """Test that history is limited to max_history."""
        manager = UndoRedoManager(max_history=3)

        # Add more operations than max_history
        for i in range(5):
            manager.add_operation(
                OperationType.CANVAS_PIXEL_CHANGE,
                f"Operation {i}",
                {"data": f"undo{i}"},
                {"data": f"redo{i}"}
            )

        assert len(manager.undo_stack) == 3  # Should be limited to max_history
        assert manager.undo_stack[0].description == "Operation 2"  # First 2 should be removed

    def test_clear_history(self):
        """Test clearing all history."""
        # Add some operations
        for i in range(3):
            self.manager.add_operation(
                OperationType.CANVAS_PIXEL_CHANGE,
                f"Operation {i}",
                {"data": f"undo{i}"},
                {"data": f"redo{i}"}
            )

        assert len(self.manager.undo_stack) == 3

        # Clear history
        self.manager.clear_history()
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 0

    def test_operation_with_failed_callback(self):
        """Test handling of failed callbacks."""
        # Mock a callback that returns False
        mock_callback = Mock(return_value=False)
        self.manager.set_pixel_change_callback(mock_callback)

        # Add operation
        self.manager.add_operation(
            OperationType.CANVAS_BRUSH_STROKE,
            "Test operation",
            {"pixels": [(10, 20, (255, 0, 0))]},
            {"pixels": [(10, 20, (0, 255, 0))]}
        )

        # Undo should fail
        result = self.manager.undo()
        assert result is False
        # Operation should still be in undo stack since undo failed
        assert len(self.manager.undo_stack) == 1
