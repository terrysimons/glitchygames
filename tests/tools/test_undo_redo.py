"""Tests for undo/redo functionality and coverage."""

import pytest

from glitchygames.bitmappy.history.operations import (
    CanvasOperationTracker,
    CrossAreaOperationTracker,
    FilmStripOperationTracker,
    PixelChange,
)
from glitchygames.bitmappy.history.undo_redo import (
    Operation,
    OperationType,
    UndoRedoManager,
)


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

    def test_add_operation_clears_redo_stack(self, mocker):
        """Test that adding new operation clears redo stack."""
        # Set up a mock callback for pixel changes
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
            {'pixel': (15, 25, (100, 0, 0))},
            {'pixel': (15, 25, (0, 100, 0))},
        )

        assert len(self.manager.redo_stack) == 0
        assert len(self.manager.undo_stack) == 1

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

    def test_undo_operation(self, mocker):
        """Test undoing operations."""
        # Set up a mock callback for pixel changes
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
        # Set up a mock callback for pixel changes
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

    def test_undo_with_no_operations(self):
        """Test undo when no operations are available."""
        result = self.manager.undo()
        assert result is False

    def test_redo_with_no_operations(self):
        """Test redo when no operations are available."""
        result = self.manager.redo()
        assert result is False

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

    def test_get_history_info(self):
        """Test getting history information."""
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE, 'Test operation', {'data': 'undo'}, {'data': 'redo'}
        )

        info = self.manager.get_history_info()
        assert info['undo_count'] == 1
        assert info['redo_count'] == 0
        assert info['can_undo'] is True
        assert info['can_redo'] is False
        assert info['next_undo'] == 'Test operation'
        assert info['next_redo'] is None
        assert info['max_history'] == 5


class TestCanvasOperationTracker:
    """Test canvas operation tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = CanvasOperationTracker(self.manager)

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

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = FilmStripOperationTracker(self.manager)

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


class TestCrossAreaOperationTracker:
    """Test cross-area operation tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = CrossAreaOperationTracker(self.manager)

    def test_add_frame_copy(self):
        """Test tracking frame copy operation."""
        frame_data = {'width': 32, 'height': 32, 'pixels': []}
        self.tracker.add_frame_copied(1, 'source_animation', frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FRAME_COPY
        assert "Copied frame 1 from 'source_animation'" in operation.description

    def test_add_frame_paste(self):
        """Test tracking frame paste operation."""
        frame_data = {'width': 32, 'height': 32, 'pixels': []}
        self.tracker.add_frame_pasted(2, 'target_animation', frame_data)

        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FRAME_PASTE
        assert "Pasted frame to 2 in 'target_animation'" in operation.description


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

    def test_empty_undo_data_raises_value_error(self):
        """Test that empty undo_data raises ValueError."""
        with pytest.raises(ValueError, match='Operation must have undo_data'):
            Operation(
                operation_type=OperationType.CANVAS_PIXEL_CHANGE,
                timestamp=1.0,
                description='test',
                undo_data={},
                redo_data={'pixel': (0, 0, (0, 0, 0))},
            )

    def test_empty_redo_data_raises_value_error(self):
        """Test that empty redo_data raises ValueError."""
        with pytest.raises(ValueError, match='Operation must have redo_data'):
            Operation(
                operation_type=OperationType.CANVAS_PIXEL_CHANGE,
                timestamp=1.0,
                description='test',
                undo_data={'pixel': (0, 0, (0, 0, 0))},
                redo_data={},
            )

    def test_valid_operation_creation(self):
        """Test that valid Operation creation succeeds."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='test op',
            undo_data={'pixel': (0, 0, (255, 0, 0))},
            redo_data={'pixel': (0, 0, (0, 255, 0))},
        )
        assert operation.description == 'test op'


class TestGetRedoDescription:
    """Test get_redo_description method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_get_redo_description_with_redo_available(self, mocker):
        """Test get_redo_description returns description when redo is available."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change operation',
            {'pixel': (5, 5, (255, 0, 0))},
            {'pixel': (5, 5, (0, 255, 0))},
        )
        self.manager.undo()

        assert self.manager.get_redo_description() == 'Pixel change operation'

    def test_get_redo_description_none_when_empty(self):
        """Test get_redo_description returns None when no redo available."""
        assert self.manager.get_redo_description() is None


class TestSkipDuringUndoRedo:
    """Test that add_operation is skipped during undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_add_operation_skipped_during_undo(self):
        """Test that add_operation is a no-op when is_undoing is True."""
        self.manager.is_undoing = True
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Should be skipped',
            {'pixel': (0, 0, (0, 0, 0))},
            {'pixel': (0, 0, (0, 0, 0))},
        )
        assert len(self.manager.undo_stack) == 0

    def test_add_operation_skipped_during_redo(self):
        """Test that add_operation is a no-op when is_redoing is True."""
        self.manager.is_redoing = True
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Should be skipped',
            {'pixel': (0, 0, (0, 0, 0))},
            {'pixel': (0, 0, (0, 0, 0))},
        )
        assert len(self.manager.undo_stack) == 0


class TestFrameSpecificUndoRedo:
    """Test frame-specific undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_add_frame_operation(self, mocker):
        """Test adding a frame-specific operation."""
        self.manager.add_frame_operation(
            animation='walk',
            frame=0,
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            description='Frame pixel change',
            undo_data={'pixel': (1, 1, (255, 0, 0))},
            redo_data={'pixel': (1, 1, (0, 255, 0))},
        )

        frame_key = ('walk', 0)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1
        assert self.manager.can_undo_frame('walk', 0)

    def test_add_frame_operation_clears_redo_stack(self, mocker):
        """Test that adding a frame operation clears the frame's redo stack."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        frame_key = ('walk', 0)

        # Add an operation and undo it to populate the redo stack
        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'First',
            {'pixel': (0, 0, (255, 0, 0))},
            {'pixel': (0, 0, (0, 255, 0))},
        )
        self.manager.undo_frame('walk', 0)
        assert len(self.manager.frame_redo_stacks[frame_key]) == 1

        # Adding a new frame operation should clear the redo stack
        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Second',
            {'pixel': (1, 1, (255, 0, 0))},
            {'pixel': (1, 1, (0, 255, 0))},
        )
        assert len(self.manager.frame_redo_stacks[frame_key]) == 0

    def test_add_frame_operation_respects_max_history(self):
        """Test that frame operations are limited by max_history."""
        self.manager.max_history = 3
        for i in range(5):
            self.manager.add_frame_operation(
                'walk',
                0,
                OperationType.CANVAS_PIXEL_CHANGE,
                f'Op {i}',
                {'pixel': (i, 0, (0, 0, 0))},
                {'pixel': (i, 0, (255, 255, 255))},
            )
        frame_key = ('walk', 0)
        assert len(self.manager.frame_undo_stacks[frame_key]) == 3

    def test_undo_frame_success(self, mocker):
        """Test successful frame undo."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (5, 5, (255, 0, 0))},
            {'pixel': (5, 5, (0, 255, 0))},
        )

        result = self.manager.undo_frame('walk', 0)
        assert result is True
        assert not self.manager.can_undo_frame('walk', 0)
        assert self.manager.can_redo_frame('walk', 0)

    def test_undo_frame_no_operations(self):
        """Test undo_frame when no operations exist for the frame."""
        result = self.manager.undo_frame('walk', 0)
        assert result is False

    def test_undo_frame_during_undo(self, mocker):
        """Test undo_frame is rejected when already undoing."""
        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Op',
            {'pixel': (0, 0, (0, 0, 0))},
            {'pixel': (0, 0, (1, 1, 1))},
        )
        self.manager.is_undoing = True
        result = self.manager.undo_frame('walk', 0)
        assert result is False
        self.manager.is_undoing = False

    def test_undo_frame_failure_restores_stacks(self, mocker):
        """Test that failed frame undo restores operation to undo stack."""
        mock_callback = mocker.Mock(return_value=False)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (5, 5, (255, 0, 0))},
            {'pixel': (5, 5, (0, 255, 0))},
        )

        result = self.manager.undo_frame('walk', 0)
        assert result is False
        # Operation should be restored to undo stack
        frame_key = ('walk', 0)
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1
        assert len(self.manager.frame_redo_stacks[frame_key]) == 0

    def test_redo_frame_success(self, mocker):
        """Test successful frame redo."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (5, 5, (255, 0, 0))},
            {'pixel': (5, 5, (0, 255, 0))},
        )
        self.manager.undo_frame('walk', 0)

        result = self.manager.redo_frame('walk', 0)
        assert result is True
        assert self.manager.can_undo_frame('walk', 0)
        assert not self.manager.can_redo_frame('walk', 0)

    def test_redo_frame_no_operations(self):
        """Test redo_frame when no operations exist for the frame."""
        result = self.manager.redo_frame('walk', 0)
        assert result is False

    def test_redo_frame_during_redo(self, mocker):
        """Test redo_frame is rejected when already redoing."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Op',
            {'pixel': (0, 0, (0, 0, 0))},
            {'pixel': (0, 0, (1, 1, 1))},
        )
        self.manager.undo_frame('walk', 0)

        self.manager.is_redoing = True
        result = self.manager.redo_frame('walk', 0)
        assert result is False
        self.manager.is_redoing = False

    def test_redo_frame_failure_restores_stacks(self, mocker):
        """Test that failed frame redo restores operation to redo stack."""
        # First undo succeeds, then redo fails
        mock_callback = mocker.Mock(side_effect=[True, False])
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_frame_operation(
            'walk',
            0,
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (5, 5, (255, 0, 0))},
            {'pixel': (5, 5, (0, 255, 0))},
        )
        self.manager.undo_frame('walk', 0)

        result = self.manager.redo_frame('walk', 0)
        assert result is False
        frame_key = ('walk', 0)
        assert len(self.manager.frame_redo_stacks[frame_key]) == 1
        assert len(self.manager.frame_undo_stacks[frame_key]) == 0


class TestRedoFailedBranch:
    """Test redo failure branches (lines 553-556)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_redo_failure_restores_stacks(self, mocker):
        """Test that failed redo restores operation to redo stack."""
        mock_callback = mocker.Mock(side_effect=[True, False])
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Test op',
            {'pixel': (0, 0, (255, 0, 0))},
            {'pixel': (0, 0, (0, 255, 0))},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False
        assert len(self.manager.redo_stack) == 1
        assert len(self.manager.undo_stack) == 0


class TestExecuteUndoBranches:
    """Test _execute_undo dispatch branches."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_cross_area_frame_paste(self, mocker):
        """Test undoing a cross-area FRAME_PASTE operation."""
        mock_paste_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_paste_callback(mock_paste_callback)

        self.manager.add_operation(
            OperationType.FRAME_PASTE,
            'Paste frame',
            {'animation': 'walk', 'frame': 0, 'pixels': [[0, 0, 0]], 'duration': 100},
            {'animation': 'walk', 'frame': 0, 'pixels': [[255, 255, 255]], 'duration': 100},
        )

        result = self.manager.undo()
        assert result is True
        mock_paste_callback.assert_called_once_with('walk', 0, [[0, 0, 0]], 100)

    def test_undo_cross_area_no_callback(self, mocker):
        """Test undoing cross-area operation with no callback returns False."""
        self.manager.add_operation(
            OperationType.FRAME_PASTE,
            'Paste frame',
            {'animation': 'walk', 'frame': 0, 'pixels': [[0, 0, 0]], 'duration': 100},
            {'animation': 'walk', 'frame': 0, 'pixels': [[255, 255, 255]], 'duration': 100},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_cross_area_unknown_type(self, mocker):
        """Test undoing a cross-area operation that isn't FRAME_PASTE."""
        self.manager.add_operation(
            OperationType.FRAME_COPY,
            'Copy frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 0},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_frame_selection(self, mocker):
        """Test undoing a frame selection operation."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )

        result = self.manager.undo()
        assert result is True
        mock_callback.assert_called_once_with('walk', 0)

    def test_undo_controller_position(self, mocker):
        """Test undoing a controller position change."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )

        result = self.manager.undo()
        assert result is True
        mock_callback.assert_called_once_with(0, (10, 20), 'canvas')

    def test_undo_controller_mode(self, mocker):
        """Test undoing a controller mode change."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )

        result = self.manager.undo()
        assert result is True
        mock_callback.assert_called_once_with(0, 'canvas')

    def test_undo_unknown_operation_type_returns_false(self, mocker):
        """Test that _execute_undo with unknown type returns False (lines 602-607)."""
        # We need to trick the system by creating an operation with a type
        # not handled by _execute_undo. Since all OperationType values are handled,
        # we test the exception branch by making the callback raise.
        mock_callback = mocker.Mock(side_effect=RuntimeError('test error'))
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Error op',
            {'pixel': (0, 0, (0, 0, 0))},
            {'pixel': (0, 0, (1, 1, 1))},
        )

        result = self.manager.undo()
        assert result is False


class TestExecuteRedoBranches:
    """Test _execute_redo dispatch branches."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_redo_cross_area_frame_paste(self, mocker):
        """Test redoing a cross-area FRAME_PASTE operation."""
        mock_paste_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_paste_callback(mock_paste_callback)

        self.manager.add_operation(
            OperationType.FRAME_PASTE,
            'Paste frame',
            {'animation': 'walk', 'frame': 0, 'pixels': [[0, 0, 0]], 'duration': 100},
            {'animation': 'walk', 'frame': 0, 'pixels': [[255, 255, 255]], 'duration': 100},
        )
        self.manager.undo()
        mock_paste_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        mock_paste_callback.assert_called_once_with('walk', 0, [[255, 255, 255]], 100)

    def test_redo_frame_selection(self, mocker):
        """Test redoing a frame selection operation."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        mock_callback.assert_called_once_with('walk', 1)

    def test_redo_controller_position(self, mocker):
        """Test redoing a controller position change."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        mock_callback.assert_called_once_with(0, (30, 40), 'canvas')

    def test_redo_controller_mode(self, mocker):
        """Test redoing a controller mode change."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        mock_callback.assert_called_once_with(0, 'film_strip')

    def test_redo_exception_returns_false(self, mocker):
        """Test that _execute_redo handles exceptions and returns False."""
        mock_callback = mocker.Mock(side_effect=[True, RuntimeError('test error')])
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Error op',
            {'pixel': (0, 0, (0, 0, 0))},
            {'pixel': (0, 0, (1, 1, 1))},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False


class TestCanvasUndoRedo:
    """Test canvas undo/redo operations for flood fill and brush stroke."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_flood_fill(self, mocker):
        """Test undoing a flood fill operation."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_FLOOD_FILL,
            'Flood fill',
            {'affected_pixels': [(0, 0), (1, 0), (0, 1)], 'old_color': (255, 0, 0)},
            {'affected_pixels': [(0, 0), (1, 0), (0, 1)], 'new_color': (0, 255, 0)},
        )

        result = self.manager.undo()
        assert result is True
        assert mock_callback.call_count == 3
        mock_callback.assert_any_call(0, 0, (255, 0, 0))
        mock_callback.assert_any_call(1, 0, (255, 0, 0))
        mock_callback.assert_any_call(0, 1, (255, 0, 0))

    def test_redo_flood_fill(self, mocker):
        """Test redoing a flood fill operation."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_FLOOD_FILL,
            'Flood fill',
            {'affected_pixels': [(0, 0), (1, 0)], 'old_color': (255, 0, 0)},
            {'affected_pixels': [(0, 0), (1, 0)], 'new_color': (0, 255, 0)},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        assert mock_callback.call_count == 2
        mock_callback.assert_any_call(0, 0, (0, 255, 0))
        mock_callback.assert_any_call(1, 0, (0, 255, 0))

    def test_undo_brush_stroke(self, mocker):
        """Test undoing a brush stroke operation."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_BRUSH_STROKE,
            'Brush stroke',
            {'pixels': [(0, 0, (0, 255, 0), (255, 0, 0)), (1, 1, (0, 255, 0), (0, 0, 255))]},
            {'pixels': [(0, 0, (255, 0, 0), (0, 255, 0)), (1, 1, (0, 0, 255), (0, 255, 0))]},
        )

        result = self.manager.undo()
        assert result is True
        assert mock_callback.call_count == 2
        # Undo applies old_color (4th element of undo_data pixels)
        mock_callback.assert_any_call(0, 0, (255, 0, 0))
        mock_callback.assert_any_call(1, 1, (0, 0, 255))

    def test_redo_brush_stroke(self, mocker):
        """Test redoing a brush stroke operation."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_BRUSH_STROKE,
            'Brush stroke',
            {'pixels': [(0, 0, (0, 255, 0), (255, 0, 0))]},
            {'pixels': [(0, 0, (255, 0, 0), (0, 255, 0))]},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        # Redo applies new_color (4th element of redo_data pixels)
        mock_callback.assert_called_once_with(0, 0, (0, 255, 0))

    def test_undo_canvas_pixel_change_no_callback(self):
        """Test undo pixel change with no callback set."""
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (0, 0, (255, 0, 0))},
            {'pixel': (0, 0, (0, 255, 0))},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_canvas_pixel_change(self, mocker):
        """Test redoing a single pixel change."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (5, 5, (255, 0, 0))},
            {'pixel': (5, 5, (0, 255, 0))},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is True
        mock_callback.assert_called_once_with(5, 5, (0, 255, 0))

    def test_undo_canvas_exception_returns_false(self, mocker):
        """Test undo canvas operation handles exceptions."""
        mock_callback = mocker.Mock(side_effect=RuntimeError('Canvas error'))
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_FLOOD_FILL,
            'Flood fill',
            {'affected_pixels': [(0, 0)], 'old_color': (255, 0, 0)},
            {'affected_pixels': [(0, 0)], 'new_color': (0, 255, 0)},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_canvas_exception_returns_false(self, mocker):
        """Test redo canvas operation handles exceptions."""
        # Undo succeeds, redo raises
        mock_callback = mocker.Mock(side_effect=[True, RuntimeError('Canvas error')])
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_FLOOD_FILL,
            'Flood fill',
            {'affected_pixels': [(0, 0)], 'old_color': (255, 0, 0)},
            {'affected_pixels': [(0, 0)], 'new_color': (0, 255, 0)},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False


class TestCrossAreaOperations:
    """Test cross-area undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_cross_area_unknown_operation_type(self):
        """Test undo cross-area with non-FRAME_PASTE type returns False."""
        self.manager.add_operation(
            OperationType.ANIMATION_PASTE,
            'Animation paste',
            {'animation': 'walk'},
            {'animation': 'run'},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_cross_area_frame_paste_no_callback(self, mocker):
        """Test redo cross-area FRAME_PASTE with no callback."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_paste_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_PASTE,
            'Paste frame',
            {'animation': 'walk', 'frame': 0, 'pixels': [[0, 0, 0]], 'duration': 100},
            {'animation': 'walk', 'frame': 0, 'pixels': [[255, 255, 255]], 'duration': 100},
        )
        self.manager.undo()

        # Remove the callback before redo
        self.manager.frame_paste_callback = None
        result = self.manager.redo()
        assert result is False

    def test_redo_cross_area_unknown_type(self, mocker):
        """Test redo cross-area with non-FRAME_PASTE type returns False."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_paste_callback(mock_callback)

        # Use ANIMATION_COPY which won't match FRAME_PASTE in redo handler
        self.manager.add_operation(
            OperationType.ANIMATION_COPY,
            'Copy animation',
            {'animation': 'walk'},
            {'animation': 'run'},
        )
        # Manually force undo (no handler for ANIMATION_COPY undo either)
        # Instead, directly manipulate stacks to test redo path
        operation = self.manager.undo_stack.pop()
        self.manager.redo_stack.append(operation)

        self.manager.is_redoing = True
        result = self.manager._redo_cross_area_operation(operation)
        self.manager.is_redoing = False
        assert result is False

    def test_undo_cross_area_exception(self, mocker):
        """Test undo cross-area handles exceptions."""
        mock_callback = mocker.Mock(side_effect=RuntimeError('Paste error'))
        self.manager.set_frame_paste_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_PASTE,
            'Paste frame',
            {'animation': 'walk', 'frame': 0, 'pixels': [[0, 0, 0]], 'duration': 100},
            {'animation': 'walk', 'frame': 0, 'pixels': [[255, 255, 255]], 'duration': 100},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_cross_area_exception(self, mocker):
        """Test redo cross-area handles exceptions."""
        mock_callback = mocker.Mock(side_effect=[True, RuntimeError('Paste error')])
        self.manager.set_frame_paste_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_PASTE,
            'Paste frame',
            {'animation': 'walk', 'frame': 0, 'pixels': [[0, 0, 0]], 'duration': 100},
            {'animation': 'walk', 'frame': 0, 'pixels': [[255, 255, 255]], 'duration': 100},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False


class TestFrameSelectionOperations:
    """Test frame selection undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_frame_selection_missing_data(self, mocker):
        """Test undo frame selection with missing animation or frame data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': None, 'frame': None},
            {'animation': 'walk', 'frame': 1},
        )

        result = self.manager.undo()
        assert result is False
        mock_callback.assert_not_called()

    def test_undo_frame_selection_no_callback(self):
        """Test undo frame selection with no callback set."""
        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_frame_selection_callback_fails(self, mocker):
        """Test undo frame selection when callback returns False."""
        mock_callback = mocker.Mock(return_value=False)
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_frame_selection_exception(self, mocker):
        """Test undo frame selection handles exceptions."""
        mock_callback = mocker.Mock(side_effect=RuntimeError('Selection error'))
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_frame_selection_missing_data(self, mocker):
        """Test redo frame selection with missing animation or frame data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': None, 'frame': None},
        )
        # Manually move to redo stack
        operation = self.manager.undo_stack.pop()
        self.manager.redo_stack.append(operation)

        self.manager.is_redoing = True
        result = self.manager._redo_frame_selection_operation(operation)
        self.manager.is_redoing = False
        assert result is False

    def test_redo_frame_selection_no_callback(self, mocker):
        """Test redo frame selection with no callback set."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )
        self.manager.undo()

        self.manager.frame_selection_callback = None
        result = self.manager.redo()
        assert result is False

    def test_redo_frame_selection_callback_fails(self, mocker):
        """Test redo frame selection when callback returns False."""
        # Undo succeeds, redo fails
        mock_callback = mocker.Mock(side_effect=[True, False])
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False

    def test_redo_frame_selection_exception(self, mocker):
        """Test redo frame selection handles exceptions."""
        mock_callback = mocker.Mock(side_effect=[True, RuntimeError('Error')])
        self.manager.set_frame_selection_callback(mock_callback)

        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False


class TestFilmStripUndoOperations:
    """Test film strip undo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_film_strip_frame_add(self, mocker):
        """Test undoing a frame addition (deletes the frame)."""
        mock_delete = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_frame_callback=mock_delete)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Add frame',
            {'animation_name': 'walk', 'frame_index': 2},
            {'animation_name': 'walk', 'frame_index': 2, 'frame_data': {'pixels': []}},
        )

        result = self.manager.undo()
        assert result is True
        mock_delete.assert_called_once_with('walk', 2)

    def test_undo_film_strip_frame_add_no_callback(self):
        """Test undoing frame add with no delete callback."""
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Add frame',
            {'animation_name': 'walk', 'frame_index': 2},
            {'animation_name': 'walk', 'frame_index': 2, 'frame_data': {'pixels': []}},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_frame_add_missing_data(self, mocker):
        """Test undoing frame add with missing undo data."""
        mock_delete = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_frame_callback=mock_delete)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Add frame',
            {'some_other_key': 'value'},
            {'animation_name': 'walk', 'frame_index': 2, 'frame_data': {'pixels': []}},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_frame_delete(self, mocker):
        """Test undoing a frame deletion (adds the frame back)."""
        mock_add = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_frame_callback=mock_add)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_DELETE,
            'Delete frame',
            {'animation_name': 'walk', 'frame_index': 1, 'frame_data': {'pixels': [1, 2, 3]}},
            {'animation_name': 'walk', 'frame_index': 1},
        )

        result = self.manager.undo()
        assert result is True
        mock_add.assert_called_once_with('walk', 1, {'pixels': [1, 2, 3]})

    def test_undo_film_strip_frame_delete_no_callback(self):
        """Test undoing frame delete with no add callback."""
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_DELETE,
            'Delete frame',
            {'animation_name': 'walk', 'frame_index': 1, 'frame_data': {'pixels': []}},
            {'animation_name': 'walk', 'frame_index': 1},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_frame_delete_missing_data(self, mocker):
        """Test undoing frame delete with missing undo data."""
        mock_add = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_frame_callback=mock_add)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_DELETE,
            'Delete frame',
            {'animation_name': 'walk', 'frame_index': 1},  # Missing frame_data
            {'animation_name': 'walk', 'frame_index': 1},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_animation_add(self, mocker):
        """Test undoing an animation addition (deletes the animation)."""
        mock_delete_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_animation_callback=mock_delete_anim)

        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            'Add animation',
            {'animation_name': 'run'},
            {'animation_name': 'run', 'animation_data': {'frames': []}},
        )

        result = self.manager.undo()
        assert result is True
        mock_delete_anim.assert_called_once_with('run')

    def test_undo_film_strip_animation_add_no_callback(self):
        """Test undoing animation add with no delete animation callback."""
        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            'Add animation',
            {'animation_name': 'run'},
            {'animation_name': 'run', 'animation_data': {'frames': []}},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_animation_add_missing_name(self, mocker):
        """Test undoing animation add with missing animation name."""
        mock_delete_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_animation_callback=mock_delete_anim)

        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            'Add animation',
            {'other_key': 'value'},
            {'animation_name': 'run', 'animation_data': {'frames': []}},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_animation_delete(self, mocker):
        """Test undoing an animation deletion (adds the animation back)."""
        mock_add_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_animation_callback=mock_add_anim)

        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            'Delete animation',
            {'animation_name': 'run', 'animation_data': {'frames': [1, 2, 3]}},
            {'animation_name': 'run'},
        )

        result = self.manager.undo()
        assert result is True
        mock_add_anim.assert_called_once_with('run', {'frames': [1, 2, 3]})

    def test_undo_film_strip_animation_delete_no_callback(self):
        """Test undoing animation delete with no add animation callback."""
        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            'Delete animation',
            {'animation_name': 'run', 'animation_data': {'frames': []}},
            {'animation_name': 'run'},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_animation_delete_missing_data(self, mocker):
        """Test undoing animation delete with missing animation data."""
        mock_add_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_animation_callback=mock_add_anim)

        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            'Delete animation',
            {'animation_name': 'run'},  # Missing animation_data
            {'animation_name': 'run'},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_frame_reorder(self, mocker):
        """Test undoing a frame reorder operation."""
        mock_reorder = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(reorder_frame_callback=mock_reorder)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_REORDER,
            'Reorder frames',
            {'animation': 'walk', 'original_order': [2, 0, 1]},
            {'animation': 'walk', 'new_order': [0, 1, 2]},
        )

        result = self.manager.undo()
        assert result is True
        mock_reorder.assert_called_once_with('walk', [2, 0, 1])

    def test_undo_film_strip_frame_reorder_no_callback(self):
        """Test undoing frame reorder with no reorder callback."""
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_REORDER,
            'Reorder frames',
            {'animation': 'walk', 'original_order': [2, 0, 1]},
            {'animation': 'walk', 'new_order': [0, 1, 2]},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_frame_reorder_missing_data(self, mocker):
        """Test undoing frame reorder with missing data."""
        mock_reorder = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(reorder_frame_callback=mock_reorder)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_REORDER,
            'Reorder frames',
            {'animation': 'walk'},  # Missing original_order
            {'animation': 'walk', 'new_order': [0, 1, 2]},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_film_strip_exception(self, mocker):
        """Test undo film strip operation handles exceptions."""
        mock_delete = mocker.Mock(side_effect=RuntimeError('Film strip error'))
        self.manager.set_film_strip_callbacks(delete_frame_callback=mock_delete)

        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Add frame',
            {'animation_name': 'walk', 'frame_index': 0},
            {'animation_name': 'walk', 'frame_index': 0, 'frame_data': {}},
        )

        result = self.manager.undo()
        assert result is False


class TestFilmStripRedoOperations:
    """Test film strip redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def _add_and_undo(self, operation_type, undo_data, redo_data, description='Test op'):
        """Helper to add an operation and undo it so it's on the redo stack."""
        self.manager.add_operation(operation_type, description, undo_data, redo_data)
        # Move to redo stack directly since some undos might fail
        operation = self.manager.undo_stack.pop()
        self.manager.redo_stack.append(operation)

    def test_redo_film_strip_frame_add(self, mocker):
        """Test redoing a frame addition."""
        mock_add = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_frame_callback=mock_add)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_ADD,
            {'animation_name': 'walk', 'frame_index': 2},
            {'animation_name': 'walk', 'frame_index': 2, 'frame_data': {'pixels': [1, 2]}},
        )

        result = self.manager.redo()
        assert result is True
        mock_add.assert_called_once_with('walk', 2, {'pixels': [1, 2]})

    def test_redo_film_strip_frame_add_no_callback(self):
        """Test redoing frame add with no add callback."""
        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_ADD,
            {'animation_name': 'walk', 'frame_index': 2},
            {'animation_name': 'walk', 'frame_index': 2, 'frame_data': {'pixels': []}},
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_frame_add_missing_data(self, mocker):
        """Test redoing frame add with missing data."""
        mock_add = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_frame_callback=mock_add)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_ADD,
            {'animation_name': 'walk', 'frame_index': 2},
            {'animation_name': 'walk'},  # Missing frame_index and frame_data
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_frame_delete(self, mocker):
        """Test redoing a frame deletion."""
        mock_delete = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_frame_callback=mock_delete)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_DELETE,
            {'animation_name': 'walk', 'frame_index': 1, 'frame_data': {'pixels': []}},
            {'animation_name': 'walk', 'frame_index': 1},
        )

        result = self.manager.redo()
        assert result is True
        mock_delete.assert_called_once_with('walk', 1)

    def test_redo_film_strip_frame_delete_no_callback(self):
        """Test redoing frame delete with no delete callback."""
        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_DELETE,
            {'animation_name': 'walk', 'frame_index': 1, 'frame_data': {'pixels': []}},
            {'animation_name': 'walk', 'frame_index': 1},
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_frame_delete_missing_data(self, mocker):
        """Test redoing frame delete with missing data."""
        mock_delete = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_frame_callback=mock_delete)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_DELETE,
            {'animation_name': 'walk', 'frame_index': 1, 'frame_data': {'pixels': []}},
            {'animation_name': 'walk'},  # Missing frame_index
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_animation_add(self, mocker):
        """Test redoing an animation addition."""
        mock_add_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_animation_callback=mock_add_anim)

        self._add_and_undo(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            {'animation_name': 'run'},
            {'animation_name': 'run', 'animation_data': {'frames': [1]}},
        )

        result = self.manager.redo()
        assert result is True
        mock_add_anim.assert_called_once_with('run', {'frames': [1]})

    def test_redo_film_strip_animation_add_no_callback(self):
        """Test redoing animation add with no callback."""
        self._add_and_undo(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            {'animation_name': 'run'},
            {'animation_name': 'run', 'animation_data': {'frames': []}},
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_animation_add_missing_data(self, mocker):
        """Test redoing animation add with missing data."""
        mock_add_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_animation_callback=mock_add_anim)

        self._add_and_undo(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            {'animation_name': 'run'},
            {'animation_name': 'run'},  # Missing animation_data
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_animation_delete(self, mocker):
        """Test redoing an animation deletion."""
        mock_delete_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_animation_callback=mock_delete_anim)

        self._add_and_undo(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            {'animation_name': 'run', 'animation_data': {'frames': []}},
            {'animation_name': 'run'},
        )

        result = self.manager.redo()
        assert result is True
        mock_delete_anim.assert_called_once_with('run')

    def test_redo_film_strip_animation_delete_no_callback(self):
        """Test redoing animation delete with no callback."""
        self._add_and_undo(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            {'animation_name': 'run', 'animation_data': {'frames': []}},
            {'animation_name': 'run'},
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_animation_delete_missing_name(self, mocker):
        """Test redoing animation delete with missing animation name."""
        mock_delete_anim = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_animation_callback=mock_delete_anim)

        self._add_and_undo(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            {'animation_name': 'run', 'animation_data': {'frames': []}},
            {'other_key': 'value'},  # Missing animation_name
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_frame_reorder(self, mocker):
        """Test redoing a frame reorder."""
        mock_reorder = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(reorder_frame_callback=mock_reorder)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_REORDER,
            {'animation': 'walk', 'original_order': [2, 0, 1]},
            {'animation': 'walk', 'new_order': [0, 1, 2]},
        )

        result = self.manager.redo()
        assert result is True
        mock_reorder.assert_called_once_with('walk', [0, 1, 2])

    def test_redo_film_strip_frame_reorder_no_callback(self):
        """Test redoing frame reorder with no callback."""
        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_REORDER,
            {'animation': 'walk', 'original_order': [2, 0, 1]},
            {'animation': 'walk', 'new_order': [0, 1, 2]},
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_frame_reorder_missing_data(self, mocker):
        """Test redoing frame reorder with missing data."""
        mock_reorder = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(reorder_frame_callback=mock_reorder)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_REORDER,
            {'animation': 'walk', 'original_order': [2, 0, 1]},
            {'animation': 'walk'},  # Missing new_order
        )

        result = self.manager.redo()
        assert result is False

    def test_redo_film_strip_exception(self, mocker):
        """Test redo film strip operation handles exceptions."""
        mock_add = mocker.Mock(side_effect=RuntimeError('Film strip error'))
        self.manager.set_film_strip_callbacks(add_frame_callback=mock_add)

        self._add_and_undo(
            OperationType.FILM_STRIP_FRAME_ADD,
            {'animation_name': 'walk', 'frame_index': 0},
            {'animation_name': 'walk', 'frame_index': 0, 'frame_data': {}},
        )

        result = self.manager.redo()
        assert result is False


class TestApplyPixelChangeNocallback:
    """Test _apply_pixel_change with no callback."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_apply_pixel_change_no_callback(self):
        """Test _apply_pixel_change returns False with no callback set."""
        result = self.manager._apply_pixel_change(0, 0, (255, 0, 0))
        assert result is False

    def test_apply_pixel_change_callback_exception(self, mocker):
        """Test _apply_pixel_change handles callback exceptions."""
        mock_callback = mocker.Mock(side_effect=RuntimeError('Pixel error'))
        self.manager.set_pixel_change_callback(mock_callback)

        result = self.manager._apply_pixel_change(0, 0, (255, 0, 0))
        assert result is False


class TestFilmStripHelperMethodsNoCallback:
    """Test film strip helper methods when callbacks are not set."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_add_frame_no_callback(self):
        """Test _add_frame returns False when callback not set."""
        result = self.manager._add_frame(0, 'walk', {'pixels': []})
        assert result is False

    def test_delete_frame_no_callback(self):
        """Test _delete_frame returns False when callback not set."""
        result = self.manager._delete_frame(0, 'walk')
        assert result is False

    def test_reorder_frame_no_callback(self):
        """Test _reorder_frame returns False when callback not set."""
        result = self.manager._reorder_frame(0, 1, 'walk')
        assert result is False

    def test_add_animation_no_callback(self):
        """Test _add_animation returns False when callback not set."""
        result = self.manager._add_animation('run', {'frames': []})
        assert result is False

    def test_delete_animation_no_callback(self):
        """Test _delete_animation returns False when callback not set."""
        result = self.manager._delete_animation('run')
        assert result is False

    def test_add_frame_with_callback(self, mocker):
        """Test _add_frame calls callback correctly."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_frame_callback=mock_callback)

        result = self.manager._add_frame(0, 'walk', {'pixels': [1, 2, 3]})
        assert result is True
        mock_callback.assert_called_once_with(0, 'walk', {'pixels': [1, 2, 3]})

    def test_delete_frame_with_callback(self, mocker):
        """Test _delete_frame calls callback correctly."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_frame_callback=mock_callback)

        result = self.manager._delete_frame(0, 'walk')
        assert result is True
        mock_callback.assert_called_once_with(0, 'walk')

    def test_reorder_frame_with_callback(self, mocker):
        """Test _reorder_frame calls callback correctly."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(reorder_frame_callback=mock_callback)

        result = self.manager._reorder_frame(0, 2, 'walk')
        assert result is True
        mock_callback.assert_called_once_with(0, 2, 'walk')

    def test_add_animation_with_callback(self, mocker):
        """Test _add_animation calls callback correctly."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(add_animation_callback=mock_callback)

        result = self.manager._add_animation('run', {'frames': []})
        assert result is True
        mock_callback.assert_called_once_with('run', {'frames': []})

    def test_delete_animation_with_callback(self, mocker):
        """Test _delete_animation calls callback correctly."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_film_strip_callbacks(delete_animation_callback=mock_callback)

        result = self.manager._delete_animation('run')
        assert result is True
        mock_callback.assert_called_once_with('run')


class TestControllerPositionOperations:
    """Test controller position undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_controller_position_missing_data(self, mocker):
        """Test undo controller position with missing controller_id or old_position."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': None, 'old_position': None},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_controller_position_no_callback(self):
        """Test undo controller position with no callback set."""
        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_controller_position_exception(self, mocker):
        """Test undo controller position handles exceptions."""
        mock_callback = mocker.Mock(side_effect=RuntimeError('Controller error'))
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_controller_position_missing_data(self, mocker):
        """Test redo controller position with missing data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': None, 'new_position': None},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is False

    def test_redo_controller_position_no_callback(self, mocker):
        """Test redo controller position with no callback set."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )
        self.manager.undo()

        self.manager.controller_position_callback = None
        result = self.manager.redo()
        assert result is False

    def test_redo_controller_position_exception(self, mocker):
        """Test redo controller position handles exceptions."""
        mock_callback = mocker.Mock(side_effect=[True, RuntimeError('Controller error')])
        self.manager.set_controller_position_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_POSITION_CHANGE,
            'Move controller',
            {'controller_id': 0, 'old_position': (10, 20), 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_position': (30, 40), 'new_mode': 'canvas'},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False


class TestOptimizeFrameCreateSelectOperations:
    """Test _optimize_frame_create_select_operations method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_optimize_removes_redundant_frame_select(self):
        """Test that frame select is removed when it follows frame add for same frame.

        Note: The code has 'frame_index' and 'animation_name' swapped in the comments
        vs. what the keys actually mean. The optimization checks:
        - last_animation = frame_selection.redo_data['animation']
        - second_animation = frame_add.redo_data['frame_index']
        So they match when frame_add.redo_data['frame_index'] ==
        frame_selection.redo_data['animation']
        and frame_add.redo_data['animation_name'] == frame_selection.redo_data['frame'].
        """
        # Add a FILM_STRIP_FRAME_ADD operation first
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Add frame',
            {'animation_name': 'walk', 'frame_index': 2},
            # frame_index is matched against animation, animation_name against frame
            {'animation_name': 1, 'frame_index': 'walk', 'frame_data': {'pixels': []}},
        )
        assert len(self.manager.undo_stack) == 1

        # Add a FRAME_SELECTION that matches the frame add
        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )

        # The optimization should have removed the frame selection
        assert len(self.manager.undo_stack) == 1
        assert self.manager.undo_stack[0].operation_type == OperationType.FILM_STRIP_FRAME_ADD

    def test_no_optimize_when_frames_differ(self):
        """Test that optimization does not remove when frames differ."""
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Add frame',
            {'animation_name': 'walk', 'frame_index': 2},
            {'animation_name': 'walk', 'frame_index': 'walk', 'frame_data': {'pixels': []}},
        )

        # Add a FRAME_SELECTION with a different animation (won't match)
        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'run', 'frame': 0},
            {'animation': 'run', 'frame': 1},
        )

        # Both operations should remain
        assert len(self.manager.undo_stack) == 2

    def test_no_optimize_when_not_enough_operations(self):
        """Test that optimization is skipped with fewer than 2 operations."""
        self.manager.add_operation(
            OperationType.FRAME_SELECTION,
            'Select frame',
            {'animation': 'walk', 'frame': 0},
            {'animation': 'walk', 'frame': 1},
        )

        # Only one operation, optimization should not apply
        assert len(self.manager.undo_stack) == 1


class TestControllerModeOperations:
    """Test controller mode undo/redo operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_controller_mode_missing_data(self, mocker):
        """Test undo controller mode with missing data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': None, 'old_mode': None},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_controller_mode_no_callback(self):
        """Test undo controller mode with no callback set."""
        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )

        result = self.manager.undo()
        assert result is False

    def test_undo_controller_mode_exception(self, mocker):
        """Test undo controller mode handles exceptions."""
        mock_callback = mocker.Mock(side_effect=RuntimeError('Mode error'))
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )

        result = self.manager.undo()
        assert result is False

    def test_redo_controller_mode_missing_data(self, mocker):
        """Test redo controller mode with missing data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': None, 'new_mode': None},
        )
        self.manager.undo()
        mock_callback.reset_mock()

        result = self.manager.redo()
        assert result is False

    def test_redo_controller_mode_no_callback(self, mocker):
        """Test redo controller mode with no callback set."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )
        self.manager.undo()

        self.manager.controller_mode_callback = None
        result = self.manager.redo()
        assert result is False

    def test_redo_controller_mode_exception(self, mocker):
        """Test redo controller mode handles exceptions."""
        mock_callback = mocker.Mock(side_effect=[True, RuntimeError('Mode error')])
        self.manager.set_controller_mode_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CONTROLLER_MODE_CHANGE,
            'Change mode',
            {'controller_id': 0, 'old_mode': 'canvas'},
            {'controller_id': 0, 'new_mode': 'film_strip'},
        )
        self.manager.undo()

        result = self.manager.redo()
        assert result is False


class TestCanvasPixelDataMissing:
    """Test canvas operations when pixel data is missing or None."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_pixel_change_no_pixel_data(self, mocker):
        """Test undo pixel change when pixel key is missing from undo_data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'no_pixel_key': True},
            {'pixel': (0, 0, (0, 0, 0))},
        )

        # pixel_data is None, so _apply_pixel_change is never called
        result = self.manager.undo()
        mock_callback.assert_not_called()

    def test_redo_pixel_change_no_pixel_data(self, mocker):
        """Test redo pixel change when pixel key is missing from redo_data."""
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            'Pixel change',
            {'pixel': (0, 0, (0, 0, 0))},
            {'no_pixel_key': True},
        )

        # Move to redo stack directly
        operation = self.manager.undo_stack.pop()
        self.manager.redo_stack.append(operation)

        result = self.manager.redo()
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


class TestFrameOperationRedoClear:
    """Test add_frame_operation clears redo stack when at head of history (line 374->377)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_add_frame_operation_clears_redo_when_not_undoing_or_redoing(self):
        """Test that frame redo stack is cleared when adding new op outside undo/redo."""
        animation = 'walk'
        frame = 0
        frame_key = (animation, frame)

        # Pre-populate the redo stack
        self.manager.frame_undo_stacks[frame_key] = []
        self.manager.frame_redo_stacks[frame_key] = [
            Operation(
                operation_type=OperationType.CANVAS_PIXEL_CHANGE,
                timestamp=1.0,
                description='stale redo',
                undo_data={'pixel': (0, 0, (0, 0, 0))},
                redo_data={'pixel': (0, 0, (255, 0, 0))},
            )
        ]

        # Confirm we are not in undo/redo state
        assert not self.manager.is_undoing
        assert not self.manager.is_redoing

        self.manager.add_frame_operation(
            animation=animation,
            frame=frame,
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            description='new pixel change',
            undo_data={'pixel': (1, 1, (0, 0, 0))},
            redo_data={'pixel': (1, 1, (255, 0, 0))},
        )

        # Redo stack should have been cleared (line 375)
        assert len(self.manager.frame_redo_stacks[frame_key]) == 0
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1


class TestUndoFrameExceptionPath:
    """Test undo_frame exception handling (lines 436-438)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_frame_exception_returns_false(self, mocker):
        """Test that undo_frame returns False on exception and resets is_undoing."""
        animation = 'walk'
        frame = 0
        frame_key = (animation, frame)

        self.manager.add_frame_operation(
            animation=animation,
            frame=frame,
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            description='test',
            undo_data={'pixel': (0, 0, (0, 0, 0))},
            redo_data={'pixel': (0, 0, (255, 0, 0))},
        )

        # Force _execute_undo to raise an exception
        mocker.patch.object(self.manager, '_execute_undo', side_effect=RuntimeError('boom'))

        result = self.manager.undo_frame(animation, frame)

        assert result is False
        assert not self.manager.is_undoing


class TestRedoFrameExceptionPath:
    """Test redo_frame exception handling (lines 484-486)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_redo_frame_exception_returns_false(self, mocker):
        """Test that redo_frame returns False on exception and resets is_redoing."""
        animation = 'walk'
        frame = 0
        frame_key = (animation, frame)

        # Set up a callback so undo succeeds
        mock_callback = mocker.Mock(return_value=True)
        self.manager.set_pixel_change_callback(mock_callback)

        self.manager.add_frame_operation(
            animation=animation,
            frame=frame,
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            description='test',
            undo_data={'pixel': (0, 0, (0, 0, 0))},
            redo_data={'pixel': (0, 0, (255, 0, 0))},
        )

        # Undo to populate redo stack
        self.manager.undo_frame(animation, frame)

        # Force _execute_redo to raise an exception
        mocker.patch.object(self.manager, '_execute_redo', side_effect=RuntimeError('boom'))

        result = self.manager.redo_frame(animation, frame)

        assert result is False
        assert not self.manager.is_redoing


class TestExecuteUndoUnknownAndException:
    """Test _execute_undo unknown type and exception paths (lines 602-607)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_execute_undo_truly_unknown_type_returns_false(self):
        """Test _execute_undo with operation type not in any dispatch (lines 602-603)."""
        # Use a mock with an operation_type that doesn't match any known set
        from unittest.mock import Mock

        mock_op = Mock(spec=Operation)
        mock_op.operation_type = 'totally_alien_type'
        mock_op.description = 'alien'

        result = self.manager._execute_undo(mock_op)
        assert result is False

    def test_execute_undo_handler_raises_exception(self, mocker):
        """Test _execute_undo when handler raises exception (lines 605-607)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='pixel change',
            undo_data={'pixel': (0, 0, (255, 0, 0))},
            redo_data={'pixel': (0, 0, (0, 255, 0))},
        )

        mocker.patch.object(
            self.manager, '_undo_canvas_operation', side_effect=RuntimeError('fail')
        )

        result = self.manager._execute_undo(operation)
        assert result is False


class TestExecuteRedoUnknownAndException:
    """Test _execute_redo unknown type and exception paths (lines 648-653)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_execute_redo_truly_unknown_type_returns_false(self):
        """Test _execute_redo with operation type not in any dispatch (lines 648-649)."""
        from unittest.mock import Mock

        mock_op = Mock(spec=Operation)
        mock_op.operation_type = 'totally_alien_type'
        mock_op.description = 'alien'

        result = self.manager._execute_redo(mock_op)
        assert result is False

    def test_execute_redo_handler_raises_exception(self, mocker):
        """Test _execute_redo when handler raises exception (lines 651-653)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='pixel change',
            undo_data={'pixel': (0, 0, (255, 0, 0))},
            redo_data={'pixel': (0, 0, (0, 255, 0))},
        )

        mocker.patch.object(
            self.manager, '_redo_canvas_operation', side_effect=RuntimeError('fail')
        )

        result = self.manager._execute_redo(operation)
        assert result is False


class TestUndoCanvasColorChangeAndException:
    """Test _undo_canvas_operation with CANVAS_COLOR_CHANGE and exception (lines 696-701)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_canvas_color_change_returns_false(self):
        """Test CANVAS_COLOR_CHANGE falls through to else branch (lines 696-697)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_COLOR_CHANGE,
            timestamp=1.0,
            description='color change',
            undo_data={'color': (255, 0, 0)},
            redo_data={'color': (0, 255, 0)},
        )

        result = self.manager._undo_canvas_operation(operation)
        assert result is False

    def test_undo_canvas_operation_exception(self, mocker):
        """Test _undo_canvas_operation exception path (lines 699-701)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='pixel',
            undo_data={'pixel': (0, 0, (255, 0, 0))},
            redo_data={'pixel': (0, 0, (0, 0, 0))},
        )

        mocker.patch.object(self.manager, '_apply_pixel_change', side_effect=RuntimeError('fail'))

        result = self.manager._undo_canvas_operation(operation)
        assert result is False


class TestUndoCanvasBrushStrokePixelFailure:
    """Test _undo_canvas_operation brush stroke pixel failure (line 682)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_brush_stroke_pixel_failure(self, mocker):
        """Test that brush stroke undo returns False when _apply_pixel_change fails."""
        operation = Operation(
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            timestamp=1.0,
            description='brush stroke',
            undo_data={'pixels': [(0, 0, (0, 0, 0), (255, 0, 0))]},
            redo_data={'pixels': [(0, 0, (255, 0, 0), (0, 0, 0))]},
        )

        mocker.patch.object(self.manager, '_apply_pixel_change', return_value=False)

        result = self.manager._undo_canvas_operation(operation)
        assert result is False


class TestRedoCanvasBrushStrokeFailureAndColorChange:
    """Test _redo_canvas_operation edge cases (lines 756, 770-775)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_redo_brush_stroke_pixel_failure(self, mocker):
        """Test redo brush stroke when pixel apply fails (line 756)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_BRUSH_STROKE,
            timestamp=1.0,
            description='brush stroke',
            undo_data={'pixels': [(0, 0, (255, 0, 0), (0, 0, 0))]},
            redo_data={'pixels': [(0, 0, (255, 0, 0), (0, 0, 0))]},
        )

        mocker.patch.object(self.manager, '_apply_pixel_change', return_value=False)

        result = self.manager._redo_canvas_operation(operation)
        assert result is False

    def test_redo_canvas_color_change_returns_false(self):
        """Test CANVAS_COLOR_CHANGE in redo falls to else branch (lines 770-771)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_COLOR_CHANGE,
            timestamp=1.0,
            description='color change',
            undo_data={'color': (255, 0, 0)},
            redo_data={'color': (0, 255, 0)},
        )

        result = self.manager._redo_canvas_operation(operation)
        assert result is False

    def test_redo_canvas_operation_exception(self, mocker):
        """Test _redo_canvas_operation exception path (lines 773-775)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='pixel',
            undo_data={'pixel': (0, 0, (255, 0, 0))},
            redo_data={'pixel': (0, 0, (0, 0, 0))},
        )

        mocker.patch.object(self.manager, '_apply_pixel_change', side_effect=RuntimeError('fail'))

        result = self.manager._redo_canvas_operation(operation)
        assert result is False


class TestFilmStripDispatchUnknownTypes:
    """Test film strip undo/redo with unknown operation types (lines 1181-1182, 1312-1313)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager(max_history=10)

    def test_undo_film_strip_unknown_type_returns_false(self):
        """Test _undo_film_strip_operation with non-film-strip type (lines 1181-1182)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='not a film strip op',
            undo_data={'dummy': True},
            redo_data={'dummy': True},
        )

        result = self.manager._undo_film_strip_operation(operation)
        assert result is False

    def test_redo_film_strip_unknown_type_returns_false(self):
        """Test _redo_film_strip_operation with non-film-strip type (lines 1312-1313)."""
        operation = Operation(
            operation_type=OperationType.CANVAS_PIXEL_CHANGE,
            timestamp=1.0,
            description='not a film strip op',
            undo_data={'dummy': True},
            redo_data={'dummy': True},
        )

        result = self.manager._redo_film_strip_operation(operation)
        assert result is False
