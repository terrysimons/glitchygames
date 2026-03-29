#!/usr/bin/env python3
"""Integration tests for undo/redo workflows and edge cases."""

import pytest

from glitchygames.bitmappy.history.operations import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
    PixelChange,
)
from glitchygames.bitmappy.history.undo_redo import UndoRedoManager


class TestUndoRedoCallbacks:
    """Test undo/redo callback functionality."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, mocker):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        self.mock_pixel_callback = mocker.Mock(return_value=True)
        self.mock_add_frame_callback = mocker.Mock(return_value=True)
        self.mock_delete_frame_callback = mocker.Mock(return_value=True)
        self.mock_reorder_frame_callback = mocker.Mock(return_value=True)
        self.mock_add_animation_callback = mocker.Mock(return_value=True)
        self.mock_delete_animation_callback = mocker.Mock(return_value=True)

        self.manager.set_pixel_change_callback(self.mock_pixel_callback)
        self.manager.set_film_strip_callbacks(
            add_frame_callback=self.mock_add_frame_callback,
            delete_frame_callback=self.mock_delete_frame_callback,
            reorder_frame_callback=self.mock_reorder_frame_callback,
            add_animation_callback=self.mock_add_animation_callback,
            delete_animation_callback=self.mock_delete_animation_callback,
        )

    def test_canvas_operation_callbacks(self):
        """Test that canvas operations call the correct callbacks."""
        # Test brush stroke undo
        from glitchygames.bitmappy.history.undo_redo import OperationType

        self.manager.add_operation(
            OperationType.CANVAS_BRUSH_STROKE,
            'Test brush stroke',
            {'pixels': [(10, 20, (0, 255, 0), (255, 0, 0))]},  # (x, y, new_color, old_color)
            {'pixels': [(10, 20, (255, 0, 0), (0, 255, 0))]},  # (x, y, old_color, new_color)
        )

        self.manager.undo()
        self.mock_pixel_callback.assert_called()

    def test_film_strip_operation_callbacks(self):
        """Test that film strip operations call the correct callbacks."""
        from glitchygames.bitmappy.history.undo_redo import OperationType

        # Test frame add undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_ADD,
            'Test frame add',
            {'frame_index': 1, 'animation_name': 'test', 'frame_data': {}},
            {'frame_index': 1, 'animation_name': 'test', 'frame_data': {}},
        )

        self.manager.undo()
        self.mock_delete_frame_callback.assert_called()

        # Test frame delete undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_FRAME_DELETE,
            'Test frame delete',
            {'frame_index': 1, 'animation_name': 'test', 'frame_data': {}},
            {'frame_index': 1, 'animation_name': 'test', 'frame_data': {}},
        )

        self.manager.undo()
        self.mock_add_frame_callback.assert_called()

        # Test animation add undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_ADD,
            'Test animation add',
            {'animation_name': 'test', 'animation_data': {}},
            {'animation_name': 'test', 'animation_data': {}},
        )

        self.manager.undo()
        self.mock_delete_animation_callback.assert_called()

        # Test animation delete undo
        self.manager.add_operation(
            OperationType.FILM_STRIP_ANIMATION_DELETE,
            'Test animation delete',
            {'animation_name': 'test', 'animation_data': {}},
            {'animation_name': 'test', 'animation_data': {}},
        )

        self.manager.undo()
        self.mock_add_animation_callback.assert_called()


class TestIntegrationScenarios:
    """Test complex integration scenarios."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self, mocker):
        """Set up test fixtures."""
        self.manager = UndoRedoManager()
        # Create a mock editor so command objects can access editor._applying_undo_redo
        # and editor.canvas.canvas_interface.set_pixel_at()
        self.mock_editor = mocker.Mock()
        self.mock_editor._applying_undo_redo = False
        # Use a real dict for _animations so FrameAddCommand._delete_frame can check membership
        self.mock_editor.canvas.animated_sprite._animations = {}
        self.mock_editor.canvas.animated_sprite._is_playing = False
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
        self.mock_editor.canvas.animated_sprite._animations = {
            'walk_animation': [placeholder, added_frame],
        }
        self.mock_editor.canvas.animated_sprite.frame_manager = mocker.Mock()
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
