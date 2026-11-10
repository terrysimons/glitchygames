"""Tests for undo/redo functionality and coverage."""

import pytest

from bitmappy.history.operations import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
    PixelChange,
)
from bitmappy.history.undo_redo import (
    OperationType,
    UndoRedoManager,
)


class TestUndoRedoManager:
    """Test the core undo/redo manager functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=5)

    def test_undo_with_no_operations(self):
        """Test undo when no operations are available."""
        result = self.manager.undo()
        assert result is False

    def test_redo_with_no_operations(self):
        """Test redo when no operations are available."""
        result = self.manager.redo()
        assert result is False


class TestCanvasOperationTracker:
    """Test canvas operation tracking."""

    @pytest.fixture(autouse=True)
    def set_up_tracker(self, bitmap_editor):
        """Set up a tracker for a real editor, on its own undo/redo manager."""
        self.manager = UndoRedoManager()
        self.tracker = CanvasOperationTracker(self.manager, editor=bitmap_editor)

    def test_start_brush_stroke(self):
        """Test starting a brush stroke."""
        self.tracker.start_brush_stroke()

        assert len(self.tracker._current_brush_pixels) == 0

    def test_add_pixel_change(self):
        """Test adding pixel changes to a stroke."""
        self.tracker.start_brush_stroke()
        self.tracker.add_pixel_change(10, 20, (255, 0, 0), (0, 255, 0))

        assert len(self.tracker._current_brush_pixels) == 1
        pixel = self.tracker._current_brush_pixels[0]
        assert pixel == (10, 20, (255, 0, 0), (0, 255, 0))

    def test_end_brush_stroke(self):
        """Test ending a brush stroke."""
        self.tracker.start_brush_stroke()
        self.tracker.add_pixel_change(5, 10, (0, 0, 0), (255, 255, 255))
        self.tracker.add_pixel_change(6, 10, (0, 0, 0), (255, 255, 255))

        self.tracker.end_brush_stroke()

        assert len(self.tracker._current_brush_pixels) == 0
        assert len(self.manager.undo_stack) == 1

        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        assert 'Brush stroke' in operation.description

    def test_end_brush_stroke_no_pixels(self):
        """Test ending a brush stroke with no pixel changes."""
        self.tracker.start_brush_stroke()
        # Don't add any pixels

        self.tracker.end_brush_stroke()

        assert len(self.tracker._current_brush_pixels) == 0
        assert len(self.manager.undo_stack) == 0  # No operation should be created

    def test_add_single_pixel_change(self):
        """Test adding a single pixel change operation."""
        self.tracker.add_single_pixel_change(15, 25, (100, 100, 100), (200, 200, 200))

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert (
            operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        )  # Single pixel uses brush stroke type
        assert 'Pixel change at (15, 25)' in operation.description

    def test_add_flood_fill(self):
        """Test adding a flood fill operation."""
        affected_pixels = [(10, 10), (11, 10), (10, 11), (11, 11)]
        self.tracker.add_flood_fill(10, 10, (0, 0, 0), (255, 255, 255), affected_pixels)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_FLOOD_FILL
        assert 'Flood fill at (10, 10)' in operation.description
        assert '4 pixels' in operation.description


class TestFilmStripOperationTracker:
    """Test film strip operation tracking."""

    @pytest.fixture(autouse=True)
    def set_up_tracker(self, bitmap_editor):
        """Set up a tracker for a real editor, on its own undo/redo manager."""
        self.manager = UndoRedoManager()
        self.tracker = FilmStripOperationTracker(self.manager, editor=bitmap_editor)

    def test_add_frame_added(self):
        """Test tracking frame addition."""
        frame_data = {'width': 32, 'height': 32, 'pixels': []}
        self.tracker.add_frame_added(2, 'walk_animation', frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_ADD
        assert "Added frame 2 to 'walk_animation'" in operation.description

    def test_add_frame_deleted(self):
        """Test tracking frame deletion."""
        frame_data = {'width': 32, 'height': 32, 'pixels': []}
        self.tracker.add_frame_deleted(1, 'run_animation', frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_DELETE
        assert "Deleted frame 1 from 'run_animation'" in operation.description

    def test_add_frame_reordered(self):
        """Test tracking frame reordering."""
        self.tracker.add_frame_reordered(0, 2, 'jump_animation')

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_REORDER
        assert "Moved frame 0 to 2 in 'jump_animation'" in operation.description

    def test_add_animation_added(self):
        """Test tracking animation addition."""
        animation_data = {'frames': 5, 'duration': 1000}
        self.tracker.add_animation_added('new_animation', animation_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_ADD
        assert "Added animation 'new_animation'" in operation.description

    def test_add_animation_deleted(self):
        """Test tracking animation deletion."""
        animation_data = {'frames': 3, 'duration': 500}
        self.tracker.add_animation_deleted('old_animation', animation_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_DELETE
        assert "Deleted animation 'old_animation'" in operation.description


class TestOperationTypes:
    """Test operation type definitions."""

    def test_operation_type_values(self):
        """Test that operation types have correct values."""
        assert OperationType.CANVAS_PIXEL_CHANGE.value == 'canvas_pixel_change'
        assert OperationType.CANVAS_BRUSH_STROKE.value == 'canvas_brush_stroke'
        assert OperationType.CANVAS_FLOOD_FILL.value == 'canvas_flood_fill'
        assert OperationType.CANVAS_COLOR_CHANGE.value == 'canvas_color_change'

        assert OperationType.FILM_STRIP_FRAME_ADD.value == 'film_strip_frame_add'
        assert OperationType.FILM_STRIP_FRAME_DELETE.value == 'film_strip_frame_delete'
        assert OperationType.FILM_STRIP_FRAME_REORDER.value == 'film_strip_frame_reorder'
        assert OperationType.FILM_STRIP_ANIMATION_ADD.value == 'film_strip_animation_add'
        assert OperationType.FILM_STRIP_ANIMATION_DELETE.value == 'film_strip_animation_delete'

        assert OperationType.FRAME_COPY.value == 'frame_copy'
        assert OperationType.FRAME_PASTE.value == 'frame_paste'
        assert OperationType.ANIMATION_COPY.value == 'animation_copy'
        assert OperationType.ANIMATION_PASTE.value == 'animation_paste'


class TestDataClasses:
    """Test data class functionality."""

    def test_pixel_change_creation(self):
        """Test PixelChange data class."""
        pixel = PixelChange(10, 20, (255, 0, 0), (0, 255, 0))

        assert pixel.x == 10
        assert pixel.y == 20
        assert pixel.old_color == (255, 0, 0)
        assert pixel.new_color == (0, 255, 0)
        # Note: PixelChange no longer has timestamp attribute


class TestGetRedoDescription:
    """Test get_redo_description method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_get_redo_description_none_when_empty(self):
        """Test get_redo_description returns None when no redo available."""
        assert self.manager.get_redo_description() is None


class TestFrameSpecificUndoRedo:
    """Test frame-specific undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_frame_no_operations(self):
        """Test undo_frame when no operations exist for the frame."""
        result = self.manager.undo_frame('walk', 0)
        assert result is False

    def test_redo_frame_no_operations(self):
        """Test redo_frame when no operations exist for the frame."""
        result = self.manager.redo_frame('walk', 0)
        assert result is False

        # pixel_data is None, _apply_pixel_change not called


class TestSetCurrentFrame:
    """Test set_current_frame method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_set_current_frame(self):
        """Test setting the current frame."""
        self.manager.set_current_frame('walk', 3)
        assert self.manager.current_frame == ('walk', 3)

    def test_set_current_frame_updates(self):
        """Test updating the current frame."""
        self.manager.set_current_frame('walk', 0)
        self.manager.set_current_frame('run', 2)
        assert self.manager.current_frame == ('run', 2)
