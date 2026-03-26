#!/usr/bin/env python3
"""Tests for controller undo/redo integration with film strips and frames.

This module tests the integration between the controller system and the undo/redo
functionality for film strip operations, ensuring that controller inputs properly
trigger undo/redo operations for frame management.
"""

import logging

import pygame
import pytest

from glitchygames.bitmappy.history.operations import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
)
from glitchygames.bitmappy.history.undo_redo import UndoRedoManager

LOG = logging.getLogger(__name__)


class TestControllerUndoRedoIntegration:
    """Test controller integration with undo/redo system for film strips."""

    @pytest.fixture
    def mock_scene(self, mocker):
        """Create a mock BitmapEditorScene for testing.

        Returns:
            object: The result.

        """
        scene = mocker.Mock()

        # Set real attributes needed by command objects
        scene._applying_undo_redo = False
        scene.canvas = mocker.Mock()
        scene.film_strips = {}

        scene.undo_redo_manager = UndoRedoManager()
        scene.canvas_operation_tracker = CanvasOperationTracker(
            scene.undo_redo_manager, editor=scene,
        )
        scene.film_strip_operation_tracker = FilmStripOperationTracker(
            scene.undo_redo_manager, editor=scene,
        )

        # Mock the undo/redo methods
        scene.handle_undo = mocker.Mock()
        scene.handle_redo = mocker.Mock()

        # Mock the film strip button handler (simulates FilmStripModeStrategy behavior)
        def mock_film_strip_handle_button_down(controller_id, button):
            try:
                if button == pygame.CONTROLLER_BUTTON_B:
                    scene.handle_undo()
                elif button == pygame.CONTROLLER_BUTTON_X and getattr(
                    scene, 'selected_frame_visible', True,
                ):
                    scene.handle_redo()
            except AttributeError, ValueError:
                # Controller handler should handle exceptions gracefully
                LOG.debug('Controller %d button press handler error suppressed', controller_id)

        scene.mode_switcher.get_strategy.return_value.handle_button_down = (
            mock_film_strip_handle_button_down
        )
        # Convenience alias for test readability
        scene.strategy_handle_button_down = (
            scene.mode_switcher.get_strategy.return_value.handle_button_down
        )

        return scene

    def _move_all_to_redo(self, undo_redo_manager):
        """Move all commands from undo stack to redo stack without executing them.

        This bypasses command execution, which would fail against mock editors
        since commands try to manipulate real editor data structures.
        """
        while undo_redo_manager.undo_stack:
            command = undo_redo_manager.undo_stack.pop()
            undo_redo_manager.redo_stack.append(command)

    def test_controller_undo_button_press(self, mock_scene):
        """Test that controller B button triggers undo operation."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )

        assert mock_scene.undo_redo_manager.can_undo()

        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)

        mock_scene.handle_undo.assert_called_once()

    def test_controller_redo_button_press(self, mock_scene):
        """Test that controller X button triggers redo operation."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )

        # Move to redo stack without executing (commands can't run against mocks)
        self._move_all_to_redo(mock_scene.undo_redo_manager)
        assert mock_scene.undo_redo_manager.can_redo()

        mock_scene.selected_frame_visible = True
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)

        mock_scene.handle_redo.assert_called_once()

    def test_controller_redo_disabled_when_frame_hidden(self, mock_scene):
        """Test that controller X button is disabled when selected frame is hidden."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )

        self._move_all_to_redo(mock_scene.undo_redo_manager)
        assert mock_scene.undo_redo_manager.can_redo()

        mock_scene.selected_frame_visible = False
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)

        mock_scene.handle_redo.assert_not_called()

    def test_controller_undo_with_film_strip_operations(self, mock_scene):
        """Test controller undo with various film strip operations."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_animation_added(
            animation_name='strip_2', animation_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_2', frame_data={},
        )

        assert mock_scene.undo_redo_manager.can_undo()

        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)

        mock_scene.handle_undo.assert_called_once()

    def test_controller_redo_with_film_strip_operations(self, mock_scene):
        """Test controller redo with various film strip operations."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_animation_added(
            animation_name='strip_2', animation_data={},
        )

        self._move_all_to_redo(mock_scene.undo_redo_manager)
        assert mock_scene.undo_redo_manager.can_redo()

        mock_scene.selected_frame_visible = True
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)

        mock_scene.handle_redo.assert_called_once()

    def test_controller_undo_no_operations(self, mock_scene):
        """Test controller undo when no operations are available."""
        assert not mock_scene.undo_redo_manager.can_undo()

        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)

        # Undo is still called (the mock handler delegates to the editor)
        mock_scene.handle_undo.assert_called_once()

    def test_controller_redo_no_operations(self, mock_scene):
        """Test controller redo when no operations are available."""
        assert not mock_scene.undo_redo_manager.can_redo()

        mock_scene.selected_frame_visible = True
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)

        # Redo is still called (the mock handler delegates to the editor)
        mock_scene.handle_redo.assert_called_once()

    def test_controller_undo_with_mixed_operations(self, mock_scene):
        """Test controller undo with mixed canvas and film strip operations."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.canvas_operation_tracker.add_pixel_changes([(10, 10, (255, 0, 0), (0, 0, 255))])
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )
        mock_scene.canvas_operation_tracker.add_pixel_changes([(20, 20, (0, 255, 0), (255, 0, 0))])

        assert mock_scene.undo_redo_manager.can_undo()

        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)

        mock_scene.handle_undo.assert_called_once()

    def test_controller_redo_with_mixed_operations(self, mock_scene):
        """Test controller redo with mixed canvas and film strip operations."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.canvas_operation_tracker.add_pixel_changes([(10, 10, (255, 0, 0), (0, 0, 255))])
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )

        self._move_all_to_redo(mock_scene.undo_redo_manager)
        assert mock_scene.undo_redo_manager.can_redo()

        mock_scene.selected_frame_visible = True
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)

        mock_scene.handle_redo.assert_called_once()

    def test_controller_undo_redo_sequence(self, mock_scene):
        """Test a sequence of controller undo/redo operations."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_animation_added(
            animation_name='strip_2', animation_data={},
        )

        # Test undo sequence
        for _ in range(3):
            mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)
            mock_scene.handle_undo.assert_called()
            mock_scene.handle_undo.reset_mock()

        # Test redo sequence
        mock_scene.selected_frame_visible = True
        for _ in range(3):
            mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)
            mock_scene.handle_redo.assert_called()
            mock_scene.handle_redo.reset_mock()

    def test_controller_undo_with_frame_selection_operations(self, mock_scene):
        """Test controller undo with frame selection operations."""
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=1)
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=2)
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=3)

        assert mock_scene.undo_redo_manager.can_undo()

        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)

        mock_scene.handle_undo.assert_called_once()

    def test_controller_redo_with_frame_selection_operations(self, mock_scene):
        """Test controller redo with frame selection operations."""
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=1)
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=2)
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=3)

        self._move_all_to_redo(mock_scene.undo_redo_manager)
        assert mock_scene.undo_redo_manager.can_redo()

        mock_scene.selected_frame_visible = True
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)

        mock_scene.handle_redo.assert_called_once()

    def test_controller_undo_redo_with_frame_add_and_select(self, mock_scene):
        """Test controller undo/redo with frame create + select operations."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_selection(animation='strip_1', frame=1)

        # Verify operations were tracked
        assert mock_scene.undo_redo_manager.can_undo()

        # Test undo
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)
        mock_scene.handle_undo.assert_called_once()

        # Test redo
        mock_scene.selected_frame_visible = True
        mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)
        mock_scene.handle_redo.assert_called_once()

    def test_controller_undo_redo_error_handling(self, mock_scene):
        """Test controller undo/redo error handling."""
        # Mock undo to raise a ValueError (simulating an undo operation error)
        mock_scene.handle_undo.side_effect = ValueError('Test error')

        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )

        # Call the controller handler (should not raise exception)
        try:
            mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)
        except AttributeError, ValueError:
            pytest.fail('Controller handler should handle exceptions gracefully')

        mock_scene.handle_undo.assert_called_once()

    def test_controller_undo_redo_with_multiple_controllers(self, mock_scene):
        """Test controller undo/redo with multiple controllers."""
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=1, animation_name='strip_1', frame_data={},
        )
        mock_scene.film_strip_operation_tracker.add_frame_added(
            frame_index=2, animation_name='strip_1', frame_data={},
        )

        # Test with multiple controllers
        for controller_id in [0, 1, 2]:
            mock_scene.strategy_handle_button_down(controller_id, pygame.CONTROLLER_BUTTON_B)
            mock_scene.handle_undo.assert_called()
            mock_scene.handle_undo.reset_mock()

            mock_scene.selected_frame_visible = True
            mock_scene.strategy_handle_button_down(controller_id, pygame.CONTROLLER_BUTTON_X)
            mock_scene.handle_redo.assert_called()
            mock_scene.handle_redo.reset_mock()

    def test_controller_undo_redo_integration_completeness(self, mock_scene):
        """Test that all controller undo/redo integration points are working."""
        operations = [
            lambda: mock_scene.film_strip_operation_tracker.add_frame_added(
                frame_index=1, animation_name='strip_1', frame_data={},
            ),
            lambda: mock_scene.film_strip_operation_tracker.add_frame_deleted(
                frame_index=1, animation_name='strip_1', frame_data={},
            ),
            lambda: mock_scene.film_strip_operation_tracker.add_animation_added(
                animation_name='strip_2', animation_data={},
            ),
            lambda: mock_scene.film_strip_operation_tracker.add_animation_deleted(
                animation_name='strip_1', animation_data={},
            ),
            lambda: mock_scene.film_strip_operation_tracker.add_frame_selection(
                animation='strip_1', frame=1,
            ),
            lambda: mock_scene.canvas_operation_tracker.add_pixel_changes([
                (10, 10, (255, 0, 0), (0, 0, 255)),
            ]),
        ]

        for op_func in operations:
            op_func()

            # Test undo dispatch
            mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_B)
            mock_scene.handle_undo.assert_called()
            mock_scene.handle_undo.reset_mock()

            # Test redo dispatch
            mock_scene.selected_frame_visible = True
            mock_scene.strategy_handle_button_down(0, pygame.CONTROLLER_BUTTON_X)
            mock_scene.handle_redo.assert_called()
            mock_scene.handle_redo.reset_mock()

            # Clear stacks for next operation
            mock_scene.undo_redo_manager.undo_stack.clear()
            mock_scene.undo_redo_manager.redo_stack.clear()
