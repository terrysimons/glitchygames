#!/usr/bin/env python3
"""Tests for film strip operation tracking."""

import pytest

from glitchygames.tools.undo_redo_manager import UndoRedoManager
from glitchygames.tools.operation_history import FilmStripOperationTracker


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
        assert operation.operation_type.value == "film_strip_frame_add"
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
        assert operation.operation_type.value == "film_strip_frame_delete"
        assert "Deleted frame 1 from 'run_animation'" in operation.description
    
    def test_add_frame_reordered(self):
        """Test tracking frame reordering."""
        self.tracker.add_frame_reordered(0, 2, "jump_animation")
        
        assert len(self.manager.undo_stack) == 1
        operation = self.manager.undo_stack[0]
        assert operation.operation_type.value == "film_strip_frame_reorder"
        assert "Moved frame 0 to 2 in 'jump_animation'" in operation.description
    
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
        assert operation.operation_type.value == "film_strip_animation_add"
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
        assert operation.operation_type.value == "film_strip_animation_delete"
        assert "Deleted animation 'old_animation'" in operation.description
