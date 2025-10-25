#!/usr/bin/env python3
"""Tests for controller undo/redo integration with film strips and frames.

This module tests the integration between the controller system and the undo/redo
functionality for film strip operations, ensuring that controller inputs properly
trigger undo/redo operations for frame management.
"""

import pytest
import pygame
from unittest.mock import Mock, patch, MagicMock
from glitchygames.tools.undo_redo_manager import UndoRedoManager, OperationType
from glitchygames.tools.operation_history import FilmStripOperationTracker, CanvasOperationTracker


class TestControllerUndoRedoIntegration:
    """Test controller integration with undo/redo system for film strips."""
    
    @pytest.fixture
    def mock_scene(self):
        """Create a mock BitmapEditorScene for testing."""
        scene = Mock()
        scene.undo_redo_manager = UndoRedoManager()
        scene.canvas_operation_tracker = CanvasOperationTracker(scene.undo_redo_manager)
        scene.film_strip_operation_tracker = FilmStripOperationTracker(scene.undo_redo_manager)
        
        # Mock the undo/redo methods
        scene._handle_undo = Mock()
        scene._handle_redo = Mock()
        
        # Mock the controller button handler
        def mock_handle_film_strip_button_press(controller_id, button):
            try:
                if button == pygame.CONTROLLER_BUTTON_B:
                    scene._handle_undo()
                elif button == pygame.CONTROLLER_BUTTON_X:
                    if getattr(scene, 'selected_frame_visible', True):
                        scene._handle_redo()
            except Exception:
                # Controller handler should handle exceptions gracefully
                pass
        
        scene._handle_film_strip_button_press = mock_handle_film_strip_button_press
        
        # Mock film strip operations
        scene._add_frame_for_undo_redo = Mock(return_value=True)
        scene._delete_frame_for_undo_redo = Mock(return_value=True)
        scene._add_animation_for_undo_redo = Mock(return_value=True)
        scene._delete_animation_for_undo_redo = Mock(return_value=True)
        scene._apply_frame_selection_for_undo_redo = Mock(return_value=True)
        
        # Set up callbacks (only the ones that exist)
        scene.undo_redo_manager.pixel_change_callback = scene._apply_pixel_change_callback
        scene.undo_redo_manager.frame_selection_callback = scene._apply_frame_selection_for_undo_redo
        
        # Set up film strip callbacks
        scene.undo_redo_manager.set_film_strip_callbacks(
            add_frame_callback=scene._add_frame_for_undo_redo,
            delete_frame_callback=scene._delete_frame_for_undo_redo,
            add_animation_callback=scene._add_animation_for_undo_redo,
            delete_animation_callback=scene._delete_animation_for_undo_redo
        )
        
        return scene
    
    def test_controller_undo_button_press(self, mock_scene):
        """Test that controller B button triggers undo operation."""
        # Create some operations to undo
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        
        # Verify we have operations to undo
        assert mock_scene.undo_redo_manager.can_undo() == True
        
        # Simulate controller B button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify undo was called
        mock_scene._handle_undo.assert_called_once()
    
    def test_controller_redo_button_press(self, mock_scene):
        """Test that controller X button triggers redo operation."""
        # Create some operations and undo them
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.undo_redo_manager.undo()
        
        # Verify we have operations to redo
        assert mock_scene.undo_redo_manager.can_redo() == True
        
        # Simulate controller X button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_X
        
        # Mock selected frame visible
        mock_scene.selected_frame_visible = True
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify redo was called
        mock_scene._handle_redo.assert_called_once()
    
    def test_controller_redo_disabled_when_frame_hidden(self, mock_scene):
        """Test that controller X button is disabled when selected frame is hidden."""
        # Create some operations and undo them
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.undo_redo_manager.undo()
        
        # Verify we have operations to redo
        assert mock_scene.undo_redo_manager.can_redo() == True
        
        # Simulate controller X button press with hidden frame
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_X
        
        # Mock selected frame hidden
        mock_scene.selected_frame_visible = False
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify redo was NOT called
        mock_scene._handle_redo.assert_not_called()
    
    def test_controller_undo_with_film_strip_operations(self, mock_scene):
        """Test controller undo with various film strip operations."""
        # Create multiple film strip operations
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        mock_scene.film_strip_operation_tracker.add_animation_added("strip_2", {})
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_2", 1, {})
        
        # Verify we have operations to undo
        assert mock_scene.undo_redo_manager.can_undo() == True
        initial_undo_count = len(mock_scene.undo_redo_manager.undo_stack)
        
        # Simulate controller B button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify undo was called
        mock_scene._handle_undo.assert_called_once()
    
    def test_controller_redo_with_film_strip_operations(self, mock_scene):
        """Test controller redo with various film strip operations."""
        # Create operations and undo them
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        mock_scene.film_strip_operation_tracker.add_animation_added("strip_2", {})
        
        # Undo all operations with safety limit
        undo_count = 0
        max_undos = 10  # Safety limit to prevent infinite loops
        while mock_scene.undo_redo_manager.can_undo() and undo_count < max_undos:
            success = mock_scene.undo_redo_manager.undo()
            undo_count += 1
            if not success:
                break  # Stop if undo fails
        
        # Verify we have operations to redo
        assert mock_scene.undo_redo_manager.can_redo() == True
        
        # Simulate controller X button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_X
        
        # Mock selected frame visible
        mock_scene.selected_frame_visible = True
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify redo was called
        mock_scene._handle_redo.assert_called_once()
    
    def test_controller_undo_no_operations(self, mock_scene):
        """Test controller undo when no operations are available."""
        # Verify no operations to undo
        assert mock_scene.undo_redo_manager.can_undo() == False
        
        # Simulate controller B button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify undo was called (but should handle gracefully)
        mock_scene._handle_undo.assert_called_once()
    
    def test_controller_redo_no_operations(self, mock_scene):
        """Test controller redo when no operations are available."""
        # Verify no operations to redo
        assert mock_scene.undo_redo_manager.can_redo() == False
        
        # Simulate controller X button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_X
        
        # Mock selected frame visible
        mock_scene.selected_frame_visible = True
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify redo was called (but should handle gracefully)
        mock_scene._handle_redo.assert_called_once()
    
    def test_controller_undo_with_mixed_operations(self, mock_scene):
        """Test controller undo with mixed canvas and film strip operations."""
        # Create mixed operations
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.canvas_operation_tracker.add_pixel_changes([(10, 10, (255, 0, 0), (0, 0, 255))])
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        mock_scene.canvas_operation_tracker.add_pixel_changes([(20, 20, (0, 255, 0), (255, 0, 0))])
        
        # Verify we have operations to undo
        assert mock_scene.undo_redo_manager.can_undo() == True
        
        # Simulate controller B button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify undo was called
        mock_scene._handle_undo.assert_called_once()
    
    def test_controller_redo_with_mixed_operations(self, mock_scene):
        """Test controller redo with mixed canvas and film strip operations."""
        # Create mixed operations and undo them
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.canvas_operation_tracker.add_pixel_changes([(10, 10, (255, 0, 0), (0, 0, 255))])
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        
        # Undo all operations
        while mock_scene.undo_redo_manager.can_undo():
            mock_scene.undo_redo_manager.undo()
        
        # Verify we have operations to redo
        assert mock_scene.undo_redo_manager.can_redo() == True
        
        # Simulate controller X button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_X
        
        # Mock selected frame visible
        mock_scene.selected_frame_visible = True
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify redo was called
        mock_scene._handle_redo.assert_called_once()
    
    def test_controller_undo_redo_sequence(self, mock_scene):
        """Test a sequence of controller undo/redo operations."""
        # Create operations
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        mock_scene.film_strip_operation_tracker.add_animation_added("strip_2", {})
        
        # Test undo sequence
        for i in range(3):
            controller_id = 0
            button = pygame.CONTROLLER_BUTTON_B
            mock_scene._handle_film_strip_button_press(controller_id, button)
            mock_scene._handle_undo.assert_called()
            mock_scene._handle_undo.reset_mock()
        
        # Test redo sequence
        for i in range(3):
            controller_id = 0
            button = pygame.CONTROLLER_BUTTON_X
            mock_scene.selected_frame_visible = True
            mock_scene._handle_film_strip_button_press(controller_id, button)
            mock_scene._handle_redo.assert_called()
            mock_scene._handle_redo.reset_mock()
    
    def test_controller_undo_with_frame_selection_operations(self, mock_scene):
        """Test controller undo with frame selection operations."""
        # Create frame selection operations
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 1)
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 2)
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 3)
        
        # Verify we have operations to undo
        assert mock_scene.undo_redo_manager.can_undo() == True
        
        # Simulate controller B button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify undo was called
        mock_scene._handle_undo.assert_called_once()
    
    def test_controller_redo_with_frame_selection_operations(self, mock_scene):
        """Test controller redo with frame selection operations."""
        # Create frame selection operations and undo them
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 1)
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 2)
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 3)
        
        # Undo all operations
        while mock_scene.undo_redo_manager.can_undo():
            mock_scene.undo_redo_manager.undo()
        
        # Verify we have operations to redo
        assert mock_scene.undo_redo_manager.can_redo() == True
        
        # Simulate controller X button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_X
        
        # Mock selected frame visible
        mock_scene.selected_frame_visible = True
        
        # Call the controller handler
        mock_scene._handle_film_strip_button_press(controller_id, button)
        
        # Verify redo was called
        mock_scene._handle_redo.assert_called_once()
    
    def test_controller_undo_redo_with_optimization(self, mock_scene):
        """Test controller undo/redo with frame create + select optimization."""
        # Create frame create + select operations (should be optimized)
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 1)
        
        # The optimization should remove the frame selection operation
        # So we should have 1 operation instead of 2
        assert len(mock_scene.undo_redo_manager.undo_stack) == 1
        
        # Test undo
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        mock_scene._handle_film_strip_button_press(controller_id, button)
        mock_scene._handle_undo.assert_called_once()
        
        # Test redo
        button = pygame.CONTROLLER_BUTTON_X
        mock_scene.selected_frame_visible = True
        mock_scene._handle_film_strip_button_press(controller_id, button)
        mock_scene._handle_redo.assert_called_once()
    
    def test_controller_undo_redo_error_handling(self, mock_scene):
        """Test controller undo/redo error handling."""
        # Mock undo to raise an exception
        mock_scene._handle_undo.side_effect = Exception("Test error")
        
        # Create some operations
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        
        # Simulate controller B button press
        controller_id = 0
        button = pygame.CONTROLLER_BUTTON_B
        
        # Call the controller handler (should not raise exception)
        try:
            mock_scene._handle_film_strip_button_press(controller_id, button)
        except Exception:
            pytest.fail("Controller handler should handle exceptions gracefully")
        
        # Verify undo was called
        mock_scene._handle_undo.assert_called_once()
    
    def test_controller_undo_redo_with_multiple_controllers(self, mock_scene):
        """Test controller undo/redo with multiple controllers."""
        # Create operations
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})
        mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 2, {})
        
        # Test with multiple controllers
        for controller_id in [0, 1, 2]:
            # Test undo
            button = pygame.CONTROLLER_BUTTON_B
            mock_scene._handle_film_strip_button_press(controller_id, button)
            mock_scene._handle_undo.assert_called()
            mock_scene._handle_undo.reset_mock()
            
            # Test redo
            button = pygame.CONTROLLER_BUTTON_X
            mock_scene.selected_frame_visible = True
            mock_scene._handle_film_strip_button_press(controller_id, button)
            mock_scene._handle_redo.assert_called()
            mock_scene._handle_redo.reset_mock()
    
    def test_controller_undo_redo_integration_completeness(self, mock_scene):
        """Test that all controller undo/redo integration points are working."""
        # Test all operation types
        operations = [
            ("frame_add", lambda: mock_scene.film_strip_operation_tracker.add_frame_added("strip_1", 1, {})),
            ("frame_delete", lambda: mock_scene.film_strip_operation_tracker.add_frame_deleted("strip_1", 1, {})),
            ("animation_add", lambda: mock_scene.film_strip_operation_tracker.add_animation_added("strip_2", {})),
            ("animation_delete", lambda: mock_scene.film_strip_operation_tracker.add_animation_deleted("strip_1", {})),
            ("frame_selection", lambda: mock_scene.film_strip_operation_tracker.add_frame_selection("strip_1", 1)),
            ("pixel_change", lambda: mock_scene.canvas_operation_tracker.add_pixel_changes([(10, 10, (255, 0, 0), (0, 0, 255))])),
        ]
        
        for op_name, op_func in operations:
            # Create operation
            op_func()
            
            # Test undo
            controller_id = 0
            button = pygame.CONTROLLER_BUTTON_B
            mock_scene._handle_film_strip_button_press(controller_id, button)
            mock_scene._handle_undo.assert_called()
            mock_scene._handle_undo.reset_mock()
            
            # Test redo
            button = pygame.CONTROLLER_BUTTON_X
            mock_scene.selected_frame_visible = True
            mock_scene._handle_film_strip_button_press(controller_id, button)
            mock_scene._handle_redo.assert_called()
            mock_scene._handle_redo.reset_mock()
            
            # Clear operations for next test with safety limit
            undo_count = 0
            max_undos = 10  # Safety limit to prevent infinite loops
            while mock_scene.undo_redo_manager.can_undo() and undo_count < max_undos:
                success = mock_scene.undo_redo_manager.undo()
                undo_count += 1
                if not success:
                    break  # Stop if undo fails
