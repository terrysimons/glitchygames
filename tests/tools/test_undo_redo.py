#!/usr/bin/env python3
"""Tests for the undo/redo system."""

import pytest
import time
from unittest.mock import Mock, patch

from glitchygames.tools.undo_redo_manager import (
    UndoRedoManager, OperationType, Operation
)
from glitchygames.tools.operation_history import (
    CanvasOperationTracker, FilmStripOperationTracker, CrossAreaOperationTracker,
    PixelChange, BrushStroke, FrameOperation
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
    
    def test_add_operation_clears_redo_stack(self):
        """Test that adding new operation clears redo stack."""
        # Add initial operation
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "First operation",
            {"data": "undo1"},
            {"data": "redo1"}
        )
        
        # Undo it to create redo stack
        self.manager.undo()
        assert len(self.manager.redo_stack) == 1
        
        # Add new operation - should clear redo stack
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "Second operation",
            {"data": "undo2"},
            {"data": "redo2"}
        )
        
        assert len(self.manager.redo_stack) == 0
        assert len(self.manager.undo_stack) == 1
    
    def test_max_history_limit(self):
        """Test that history is limited to max_history."""
        # Add more operations than max_history
        for i in range(7):  # More than max_history of 5
            self.manager.add_operation(
                OperationType.CANVAS_PIXEL_CHANGE,
                f"Operation {i}",
                {"data": f"undo{i}"},
                {"data": f"redo{i}"}
            )
        
        assert len(self.manager.undo_stack) == 5  # Should be limited to max_history
        assert self.manager.undo_stack[0].description == "Operation 2"  # First 2 should be removed
    
    def test_undo_operation(self):
        """Test undoing operations."""
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "Test operation",
            {"data": "undo"},
            {"data": "redo"}
        )
        
        result = self.manager.undo()
        assert result is True
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 1
        assert not self.manager.can_undo()
        assert self.manager.can_redo()
    
    def test_redo_operation(self):
        """Test redoing operations."""
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "Test operation",
            {"data": "undo"},
            {"data": "redo"}
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
                f"Operation {i}",
                {"data": f"undo{i}"},
                {"data": f"redo{i}"}
            )
        
        assert len(self.manager.undo_stack) == 3
        
        # Clear history
        self.manager.clear_history()
        assert len(self.manager.undo_stack) == 0
        assert len(self.manager.redo_stack) == 0
    
    def test_get_history_info(self):
        """Test getting history information."""
        self.manager.add_operation(
            OperationType.CANVAS_PIXEL_CHANGE,
            "Test operation",
            {"data": "undo"},
            {"data": "redo"}
        )
        
        info = self.manager.get_history_info()
        assert info["undo_count"] == 1
        assert info["redo_count"] == 0
        assert info["can_undo"] is True
        assert info["can_redo"] is False
        assert info["next_undo"] == "Test operation"
        assert info["next_redo"] is None
        assert info["max_history"] == 5


class TestCanvasOperationTracker:
    """Test canvas operation tracking."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = CanvasOperationTracker(self.manager)
    
    def test_start_brush_stroke(self):
        """Test starting a brush stroke."""
        self.tracker.start_brush_stroke(5, "round")
        
        assert self.tracker.current_stroke is not None
        assert self.tracker.current_stroke.brush_size == 5
        assert self.tracker.current_stroke.brush_type == "round"
        assert len(self.tracker.stroke_pixels) == 0
    
    def test_add_pixel_change(self):
        """Test adding pixel changes to a stroke."""
        self.tracker.start_brush_stroke(3, "square")
        self.tracker.add_pixel_change(10, 20, (255, 0, 0), (0, 255, 0))
        
        assert len(self.tracker.stroke_pixels) == 1
        pixel = self.tracker.stroke_pixels[0]
        assert pixel.x == 10
        assert pixel.y == 20
        assert pixel.old_color == (255, 0, 0)
        assert pixel.new_color == (0, 255, 0)
    
    def test_end_brush_stroke(self):
        """Test ending a brush stroke."""
        self.tracker.start_brush_stroke(2, "round")
        self.tracker.add_pixel_change(5, 10, (0, 0, 0), (255, 255, 255))
        self.tracker.add_pixel_change(6, 10, (0, 0, 0), (255, 255, 255))
        
        self.tracker.end_brush_stroke()
        
        assert self.tracker.current_stroke is None
        assert len(self.tracker.stroke_pixels) == 0
        assert len(self.manager.undo_stack) == 1
        
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        assert "Brush stroke" in operation.description
    
    def test_end_brush_stroke_no_pixels(self):
        """Test ending a brush stroke with no pixel changes."""
        self.tracker.start_brush_stroke(2, "round")
        # Don't add any pixels
        
        self.tracker.end_brush_stroke()
        
        assert self.tracker.current_stroke is None
        assert len(self.manager.undo_stack) == 0  # No operation should be created
    
    def test_add_single_pixel_change(self):
        """Test adding a single pixel change operation."""
        self.tracker.add_single_pixel_change(15, 25, (100, 100, 100), (200, 200, 200))
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_PIXEL_CHANGE
        assert "Pixel change at (15, 25)" in operation.description
    
    def test_add_flood_fill(self):
        """Test adding a flood fill operation."""
        affected_pixels = [(10, 10), (11, 10), (10, 11), (11, 11)]
        self.tracker.add_flood_fill(10, 10, (0, 0, 0), (255, 255, 255), affected_pixels)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_FLOOD_FILL
        assert "Flood fill at (10, 10)" in operation.description
        assert "4 pixels" in operation.description


class TestFilmStripOperationTracker:
    """Test film strip operation tracking."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.tracker = FilmStripOperationTracker(self.manager)
    
    def test_add_frame_added(self):
        """Test tracking frame addition."""
        frame_data = {"width": 32, "height": 32, "pixels": []}
        self.tracker.add_frame_added(2, "walk_animation", frame_data)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_ADD
        assert "Added frame 2 to 'walk_animation'" in operation.description
    
    def test_add_frame_deleted(self):
        """Test tracking frame deletion."""
        frame_data = {"width": 32, "height": 32, "pixels": []}
        self.tracker.add_frame_deleted(1, "run_animation", frame_data)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_DELETE
        assert "Deleted frame 1 from 'run_animation'" in operation.description
    
    def test_add_frame_reordered(self):
        """Test tracking frame reordering."""
        self.tracker.add_frame_reordered(0, 2, "jump_animation")
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_FRAME_REORDER
        assert "Moved frame 0 to 2 in 'jump_animation'" in operation.description
    
    def test_add_animation_added(self):
        """Test tracking animation addition."""
        animation_data = {"frames": 5, "duration": 1000}
        self.tracker.add_animation_added("new_animation", animation_data)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FILM_STRIP_ANIMATION_ADD
        assert "Added animation 'new_animation'" in operation.description
    
    def test_add_animation_deleted(self):
        """Test tracking animation deletion."""
        animation_data = {"frames": 3, "duration": 500}
        self.tracker.add_animation_deleted("old_animation", animation_data)
        
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
        frame_data = {"width": 32, "height": 32, "pixels": []}
        self.tracker.add_frame_copy(1, "source_animation", frame_data)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FRAME_COPY
        assert "Copied frame 1 from 'source_animation'" in operation.description
    
    def test_add_frame_paste(self):
        """Test tracking frame paste operation."""
        frame_data = {"width": 32, "height": 32, "pixels": []}
        self.tracker.add_frame_paste(2, "target_animation", frame_data)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type == OperationType.FRAME_PASTE
        assert "Pasted frame to 2 in 'target_animation'" in operation.description


class TestOperationTypes:
    """Test operation type definitions."""
    
    def test_operation_type_values(self):
        """Test that operation types have correct values."""
        assert OperationType.CANVAS_PIXEL_CHANGE.value == "canvas_pixel_change"
        assert OperationType.CANVAS_BRUSH_STROKE.value == "canvas_brush_stroke"
        assert OperationType.CANVAS_FLOOD_FILL.value == "canvas_flood_fill"
        assert OperationType.CANVAS_COLOR_CHANGE.value == "canvas_color_change"
        
        assert OperationType.FILM_STRIP_FRAME_ADD.value == "film_strip_frame_add"
        assert OperationType.FILM_STRIP_FRAME_DELETE.value == "film_strip_frame_delete"
        assert OperationType.FILM_STRIP_FRAME_REORDER.value == "film_strip_frame_reorder"
        assert OperationType.FILM_STRIP_ANIMATION_ADD.value == "film_strip_animation_add"
        assert OperationType.FILM_STRIP_ANIMATION_DELETE.value == "film_strip_animation_delete"
        
        assert OperationType.FRAME_COPY.value == "frame_copy"
        assert OperationType.FRAME_PASTE.value == "frame_paste"
        assert OperationType.ANIMATION_COPY.value == "animation_copy"
        assert OperationType.ANIMATION_PASTE.value == "animation_paste"


class TestDataClasses:
    """Test data class functionality."""
    
    def test_pixel_change_creation(self):
        """Test PixelChange data class."""
        pixel = PixelChange(10, 20, (255, 0, 0), (0, 255, 0))
        
        assert pixel.x == 10
        assert pixel.y == 20
        assert pixel.old_color == (255, 0, 0)
        assert pixel.new_color == (0, 255, 0)
        assert pixel.timestamp > 0
    
    def test_brush_stroke_creation(self):
        """Test BrushStroke data class."""
        pixels = [
            PixelChange(10, 20, (255, 0, 0), (0, 255, 0)),
            PixelChange(11, 20, (255, 0, 0), (0, 255, 0))
        ]
        stroke = BrushStroke(pixels, 3, "round")
        
        assert len(stroke.pixels) == 2
        assert stroke.brush_size == 3
        assert stroke.brush_type == "round"
        assert stroke.timestamp > 0
    
    def test_frame_operation_creation(self):
        """Test FrameOperation data class."""
        operation_data = {"width": 32, "height": 32}
        frame_op = FrameOperation(2, "test_animation", operation_data)
        
        assert frame_op.frame_index == 2
        assert frame_op.animation_name == "test_animation"
        assert frame_op.operation_data == operation_data
        assert frame_op.timestamp > 0
