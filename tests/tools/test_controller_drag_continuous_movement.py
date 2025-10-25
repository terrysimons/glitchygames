#!/usr/bin/env python3
"""Test controller drag operations with continuous movement."""

import pytest
import pygame
from unittest.mock import Mock, MagicMock
import time

from glitchygames.tools.undo_redo_manager import UndoRedoManager, OperationType
from glitchygames.tools.operation_history import CanvasOperationTracker, FilmStripOperationTracker


class TestControllerDragContinuousMovement:
    """Test that controller drag operations work properly with continuous movement."""
    
    @pytest.fixture
    def mock_scene(self):
        """Create a mock scene with undo/redo functionality."""
        scene = Mock()
        
        # Set up undo/redo manager
        scene.undo_redo_manager = UndoRedoManager()
        scene.canvas_operation_tracker = CanvasOperationTracker(scene.undo_redo_manager)
        scene.film_strip_operation_tracker = FilmStripOperationTracker(scene.undo_redo_manager)
        
        # Set up pixel change tracking
        scene._current_pixel_changes = []
        scene._applying_undo_redo = False
        
        # Set up controller drag tracking
        scene.controller_drags = {}
        
        # Set up continuous movement tracking
        scene.canvas_continuous_movements = {}
        
        # Mock canvas interface
        scene.canvas = Mock()
        scene.canvas.canvas_interface = Mock()
        scene.canvas.canvas_interface.get_pixel_at = Mock(return_value=(0, 0, 0))  # Default black
        scene.canvas.canvas_interface.set_pixel_at = Mock()
        
        # Mock mode switcher
        scene.mode_switcher = Mock()
        scene.mode_switcher.get_controller_mode = Mock(return_value=Mock(value='canvas'))
        scene.mode_switcher.get_controller_position = Mock(return_value=Mock(
            is_valid=True,
            position=(5, 5)
        ))
        
        # Mock color getter
        scene._get_current_color = Mock(return_value=(255, 0, 0))  # Red
        
        # Mock canvas move cursor method
        scene._canvas_move_cursor = Mock()
        scene._canvas_paint_at_controller_position = Mock()
        
        return scene
    
    def test_controller_drag_with_continuous_movement(self, mock_scene):
        """Test that controller drag operations paint during continuous movement."""
        controller_id = 0
        
        # Start a controller drag
        mock_scene.controller_drags[controller_id] = {
            'active': True,
            'start_time': time.time(),
            'start_position': (5, 5),
            'pixels_drawn': [],
            'end_time': None,
            'end_position': None
        }
        
        # Set up continuous movement
        mock_scene.canvas_continuous_movements[controller_id] = {
            'start_time': time.time(),
            'last_movement': time.time() - 0.2,  # Ready for next movement
            'dx': 1,
            'dy': 0,
            'acceleration_level': 0
        }
        
        # Mock different positions for continuous movement
        positions = [(5, 5), (6, 5), (7, 5), (8, 5)]
        position_index = 0
        
        def mock_get_controller_position(controller_id):
            nonlocal position_index
            if position_index < len(positions):
                pos = positions[position_index]
                position_index += 1
                return Mock(is_valid=True, position=pos)
            return Mock(is_valid=True, position=(8, 5))
        
        mock_scene.mode_switcher.get_controller_position = mock_get_controller_position
        
        # Import the actual method from the real implementation
        from glitchygames.tools.bitmappy import BitmapEditorScene
        
        # Create a real scene instance to test the actual method
        real_scene = BitmapEditorScene.__new__(BitmapEditorScene)
        real_scene.controller_drags = mock_scene.controller_drags
        real_scene.canvas_continuous_movements = mock_scene.canvas_continuous_movements
        real_scene.mode_switcher = mock_scene.mode_switcher
        real_scene._canvas_move_cursor = mock_scene._canvas_move_cursor
        real_scene._canvas_paint_at_controller_position = mock_scene._canvas_paint_at_controller_position
        
        # Simulate continuous movement update using the real method
        real_scene._update_canvas_continuous_movements()
        
        # Verify that painting was called during continuous movement
        # Should be called once for each movement (1 time since we only have one movement ready)
        assert mock_scene._canvas_paint_at_controller_position.call_count == 1
        
        # Verify that cursor movement was called
        assert mock_scene._canvas_move_cursor.call_count == 1
    
    def test_controller_drag_without_continuous_movement(self, mock_scene):
        """Test that controller drag operations don't paint when not in continuous movement."""
        controller_id = 0
        
        # Start a controller drag
        mock_scene.controller_drags[controller_id] = {
            'active': True,
            'start_time': time.time(),
            'start_position': (5, 5),
            'pixels_drawn': [],
            'end_time': None,
            'end_position': None
        }
        
        # Don't set up continuous movement
        # mock_scene.canvas_continuous_movements = {}  # Empty
        
        # Simulate continuous movement update
        mock_scene._update_canvas_continuous_movements()
        
        # Verify that no painting was called
        assert mock_scene._canvas_paint_at_controller_position.call_count == 0
        assert mock_scene._canvas_move_cursor.call_count == 0
    
    def test_controller_drag_inactive_during_continuous_movement(self, mock_scene):
        """Test that no painting occurs when controller drag is inactive during continuous movement."""
        controller_id = 0
        
        # Set up continuous movement
        mock_scene.canvas_continuous_movements[controller_id] = {
            'start_time': time.time(),
            'last_movement': time.time() - 0.2,  # Ready for next movement
            'dx': 1,
            'dy': 0,
            'acceleration_level': 0
        }
        
        # Don't start a controller drag (no controller_drags entry)
        
        # Simulate continuous movement update
        mock_scene._update_canvas_continuous_movements()
        
        # Verify that cursor movement was called but no painting
        assert mock_scene._canvas_move_cursor.call_count == 1
        assert mock_scene._canvas_paint_at_controller_position.call_count == 0
    
    def test_controller_drag_ended_during_continuous_movement(self, mock_scene):
        """Test that no painting occurs when controller drag is ended during continuous movement."""
        controller_id = 0
        
        # Start a controller drag but mark it as inactive
        mock_scene.controller_drags[controller_id] = {
            'active': False,  # Inactive drag
            'start_time': time.time(),
            'start_position': (5, 5),
            'pixels_drawn': [],
            'end_time': time.time(),
            'end_position': (8, 5)
        }
        
        # Set up continuous movement
        mock_scene.canvas_continuous_movements[controller_id] = {
            'start_time': time.time(),
            'last_movement': time.time() - 0.2,  # Ready for next movement
            'dx': 1,
            'dy': 0,
            'acceleration_level': 0
        }
        
        # Simulate continuous movement update
        mock_scene._update_canvas_continuous_movements()
        
        # Verify that cursor movement was called but no painting
        assert mock_scene._canvas_move_cursor.call_count == 1
        assert mock_scene._canvas_paint_at_controller_position.call_count == 0
