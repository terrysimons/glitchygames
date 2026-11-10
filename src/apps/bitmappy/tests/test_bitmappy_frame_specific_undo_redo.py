#!/usr/bin/env python3
"""Tests for frame-specific undo/redo functionality."""

from bitmappy.history.undo_redo import UndoRedoManager


class TestFrameSpecificUndoRedo:
    """Test frame-specific undo/redo functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()

    def test_set_current_frame(self):
        """Test setting the current frame."""
        self.manager.set_current_frame('walk_animation', 2)
        assert self.manager.current_frame == ('walk_animation', 2)

    def test_frame_undo_with_no_operations(self):
        """Test frame undo when no operations are available."""
        assert not self.manager.can_undo_frame('test_animation', 1)
        assert self.manager.undo_frame('test_animation', 1) is False

    def test_frame_redo_with_no_operations(self):
        """Test frame redo when no operations are available."""
        assert not self.manager.can_redo_frame('test_animation', 1)
        assert self.manager.redo_frame('test_animation', 1) is False
