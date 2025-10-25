#!/usr/bin/env python3
"""Tests for canvas operation tracking."""

import pytest
from unittest.mock import Mock

from glitchygames.tools.undo_redo_manager import UndoRedoManager
from glitchygames.tools.operation_history import (
    CanvasOperationTracker, PixelChange
)


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
        assert operation.operation_type.value == "canvas_brush_stroke"
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
        assert operation.operation_type.value == "canvas_brush_stroke"
        assert "run_animation[2]" in operation.description
    
    def test_add_pixel_changes_global_fallback(self):
        """Test that global tracking still works as fallback."""
        pixels = [
            (10, 20, (255, 0, 0), (0, 255, 0))
        ]
        
        self.tracker.add_pixel_changes(pixels)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type.value == "canvas_brush_stroke"
    
    def test_add_single_pixel_change(self):
        """Test adding a single pixel change operation."""
        self.tracker.add_single_pixel_change(15, 25, (100, 100, 100), (200, 200, 200))
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type.value == "canvas_brush_stroke"  # Single pixels are treated as brush strokes
        assert "Pixel change at (15, 25)" in operation.description
    
    def test_add_flood_fill(self):
        """Test adding a flood fill operation."""
        affected_pixels = [(10, 10), (11, 10), (10, 11), (11, 11)]
        self.tracker.add_flood_fill(10, 10, (0, 0, 0), (255, 255, 255), affected_pixels)
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type.value == "canvas_flood_fill"
        assert "Flood fill at (10, 10)" in operation.description
        assert "4 pixels" in operation.description
