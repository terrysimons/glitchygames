#!/usr/bin/env python3
"""Integration tests for undo/redo workflows and edge cases."""

import pytest

from bitmappy.history.operations import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
    PixelChange,
)
from bitmappy.history.undo_redo import UndoRedoManager
from glitchygames.sprites.animated import AnimatedSprite


class TestIntegrationScenarios:
    """Test complex integration scenarios."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, mocker):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        # Create a mock editor so command objects can access editor.applying_undo_redo
        # and editor.canvas.canvas_interface.set_pixel_at()
        self.mock_editor = mocker.Mock()
        self.mock_editor.applying_undo_redo = False
        # A real sprite, so FrameAddCommand._delete_frame finds its animations
        self.mock_editor.canvas.animated_sprite = AnimatedSprite()
        self.canvas_tracker = CanvasOperationTracker(self.manager, editor=self.mock_editor)
        self.film_tracker = FilmStripOperationTracker(self.manager, editor=self.mock_editor)

    def test_mixed_operations_undo_sequence(self, mocker):
        """Test undoing a sequence of mixed canvas and film strip operations."""
        # Add canvas operation
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0))]
        self.canvas_tracker.add_pixel_changes(pixels)

        # Pre-populate the animation so FrameAddCommand._delete_frame can find it
        import pygame

        from glitchygames.sprites.animated import SpriteFrame

        placeholder = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
        added_frame = SpriteFrame(surface=pygame.Surface((32, 32)), duration=1.0)
        self.mock_editor.canvas.animated_sprite.add_animation(
            'walk_animation',
            [placeholder, added_frame],
        )
        # The canvas shows another animation, so deleting the frame moves no shown frame
        self.mock_editor.canvas.animated_sprite.frame_manager.current_animation = ''

        # Add frame operation
        frame_data = {'width': 32, 'height': 32, 'pixels': [], 'duration': 1.0}
        self.film_tracker.add_frame_added(1, 'walk_animation', frame_data)

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
        self.canvas_tracker.add_frame_pixel_changes('walk_animation', 1, frame_pixels)

        # Global stack should have 1 operation
        assert len(self.manager.undo_stack) == 1

        # Frame-specific stack should have 1 operation
        frame_key = ('walk_animation', 1)
        assert frame_key in self.manager.frame_undo_stacks
        assert len(self.manager.frame_undo_stacks[frame_key]) == 1

        # Can undo both independently
        assert self.manager.can_undo()
        assert self.manager.can_undo_frame('walk_animation', 1)

    def test_operation_descriptions(self):
        """Test that operation descriptions are informative."""
        # Test canvas operation description
        pixels = [(10, 20, (255, 0, 0), (0, 255, 0))]
        self.canvas_tracker.add_pixel_changes(pixels)

        operation = self.manager.undo_stack[0]
        assert 'Pixel change' in operation.description
        assert '(10, 20)' in operation.description

        # Test frame-specific operation description
        frame_pixels = [PixelChange(15, 25, (0, 0, 255), (255, 255, 0))]
        self.canvas_tracker.add_frame_pixel_changes('walk_animation', 1, frame_pixels)

        frame_key = ('walk_animation', 1)
        frame_operation = self.manager.frame_undo_stacks[frame_key][0]
        # BrushStrokeCommand describes the pixel operation without animation prefix
        assert 'Pixel change' in frame_operation.description
        assert '(15, 25)' in frame_operation.description
