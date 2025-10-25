#!/usr/bin/env python3
"""Tests for frame-specific undo/redo functionality."""

import pytest
from unittest.mock import Mock

from glitchygames.tools.undo_redo_manager import (
    UndoRedoManager, OperationType, Operation
)


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
    
    def test_frame_undo_with_no_operations(self):
        """Test frame undo when no operations are available."""
        assert not self.manager.can_undo_frame("test_animation", 1)
        assert self.manager.undo_frame("test_animation", 1) is False
    
    def test_frame_redo_with_no_operations(self):
        """Test frame redo when no operations are available."""
        assert not self.manager.can_redo_frame("test_animation", 1)
        assert self.manager.redo_frame("test_animation", 1) is False
