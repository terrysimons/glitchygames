#!/usr/bin/env python3
"""Comprehensive tests for the updated undo/redo system with frame-specific operations."""

import pytest

from bitmappy.history.operations import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
    PixelChange,
)
from bitmappy.history.undo_redo import OperationType, UndoRedoManager


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


class TestCanvasOperationTracker:
    """Test canvas operation tracking with frame-specific operations."""

    @pytest.fixture(autouse=True)
    def set_up_tracker(self, bitmap_editor):
        """Set up a tracker for a real editor, on its own undo/redo manager."""
        self.manager = UndoRedoManager()
        self.tracker = CanvasOperationTracker(self.manager, editor=bitmap_editor)

    def test_add_frame_pixel_changes(self):
        """Test adding frame-specific pixel changes."""
        pixels = [
            PixelChange(10, 20, (255, 0, 0), (0, 255, 0)),
            PixelChange(11, 20, (255, 0, 0), (0, 255, 0)),
        ]

        self.tracker.add_frame_pixel_changes('walk_animation', 1, pixels)

        frame_key = ('walk_animation', 1)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1

        operation = self.manager.frame_undo_stacks[frame_key][0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        # BrushStrokeCommand generates description based on pixel count, not animation name
        assert 'Brush stroke' in operation.description or 'Pixel change' in operation.description

    def test_add_frame_pixel_changes_with_tuples(self):
        """Test adding frame-specific pixel changes with tuple format."""
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0)), (11, 20, (255, 0, 0), (0, 255, 0))]

        self.tracker.add_frame_pixel_changes('run_animation', 2, pixels)

        frame_key = ('run_animation', 2)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1

        operation = self.manager.frame_undo_stacks[frame_key][0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        # BrushStrokeCommand generates description based on pixel count, not animation name
        assert 'Brush stroke' in operation.description or 'Pixel change' in operation.description

    def test_add_pixel_changes_global_fallback(self):
        """Test that global tracking still works as fallback."""
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0))]

        self.tracker.add_pixel_changes(pixels)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE


class TestFilmStripOperationTracker:
    """Test film strip operation tracking."""

    @pytest.fixture(autouse=True)
    def set_up_tracker(self, bitmap_editor):
        """Set up a tracker for a real editor, on its own undo/redo manager."""
        self.manager = UndoRedoManager()
        self.tracker = FilmStripOperationTracker(self.manager, editor=bitmap_editor)

    def test_add_frame_added(self):
        """Test tracking frame addition."""
        frame_data = {'width': 32, 'height': 32, 'pixels': [255, 0, 0] * 32 * 32, 'duration': 1.0}
        self.tracker.add_frame_added(2, 'walk_animation', frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_ADD
        assert "Added frame 2 to 'walk_animation'" in operation.description

    def test_add_frame_deleted(self):
        """Test tracking frame deletion."""
        frame_data = {'width': 32, 'height': 32, 'pixels': [255, 0, 0] * 32 * 32, 'duration': 1.0}
        self.tracker.add_frame_deleted(1, 'run_animation', frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_DELETE
        assert "Deleted frame 1 from 'run_animation'" in operation.description

    def test_add_animation_added(self):
        """Test tracking animation addition."""
        animation_data = {
            'frames': [
                {'width': 32, 'height': 32, 'pixels': [255, 0, 0] * 32 * 32, 'duration': 1.0},
                {'width': 32, 'height': 32, 'pixels': [0, 255, 0] * 32 * 32, 'duration': 1.0},
            ],
        }
        self.tracker.add_animation_added('new_animation', animation_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_ADD
        assert "Added animation 'new_animation'" in operation.description

    def test_add_animation_deleted(self):
        """Test tracking animation deletion."""
        animation_data = {
            'frames': [
                {'width': 32, 'height': 32, 'pixels': [255, 0, 0] * 32 * 32, 'duration': 1.0},
            ],
        }
        self.tracker.add_animation_deleted('old_animation', animation_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_DELETE
        assert "Deleted animation 'old_animation'" in operation.description


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
        assert not self.manager.can_undo_frame('test_animation', 1)
        assert self.manager.undo_frame('test_animation', 1) is False

    def test_frame_redo_with_no_operations(self):
        """Test frame redo when no operations are available."""
        assert not self.manager.can_redo_frame('test_animation', 1)
        assert self.manager.redo_frame('test_animation', 1) is False
