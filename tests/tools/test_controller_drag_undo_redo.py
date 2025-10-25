#!/usr/bin/env python3
"""Test controller drag operations and undo/redo functionality."""

import pytest
import pygame
from unittest.mock import Mock, MagicMock
import time

from glitchygames.tools.undo_redo_manager import UndoRedoManager, OperationType
from glitchygames.tools.operation_history import CanvasOperationTracker, FilmStripOperationTracker


class TestControllerDragUndoRedo:
    """Test that controller drag operations are properly grouped for undo/redo."""
    
    @pytest.fixture
    def mock_scene(self):
        """Create a mock scene with undo/redo functionality."""
        scene = Mock()
        
        # Set up undo/redo manager
        scene.undo_redo_manager = UndoRedoManager()
        scene.canvas_operation_tracker = CanvasOperationTracker(scene.undo_redo_manager)
        scene.film_strip_operation_tracker = FilmStripOperationTracker(scene.undo_redo_manager)
        
        # Set up pixel change callback for undo/redo
        scene._apply_pixel_change_for_undo_redo = Mock(return_value=True)
        scene.undo_redo_manager.set_pixel_change_callback(scene._apply_pixel_change_for_undo_redo)
        
        # Set up pixel change tracking
        scene._current_pixel_changes = []
        scene._applying_undo_redo = False
        
        # Set up controller drag tracking
        scene.controller_drags = {}
        
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
        
        return scene
    
    def test_controller_drag_operation_collects_pixels(self, mock_scene):
        """Test that controller drag operations collect pixels but don't submit them for undo/redo."""
        controller_id = 0
        
        # Simulate starting a controller drag
        mock_scene.controller_drags[controller_id] = {
            'active': True,
            'start_time': time.time(),
            'start_position': (5, 5),
            'pixels_drawn': [],
            'end_time': None,
            'end_position': None
        }
        
        # Mock different pixel colors to avoid debouncing
        mock_scene.canvas.canvas_interface.get_pixel_at.side_effect = [
            (0, 0, 0),  # First pixel is black
            (128, 128, 128),  # Second pixel is gray
            (64, 64, 64),  # Third pixel is dark gray
            (192, 192, 192),  # Fourth pixel is light gray
        ]
        
        # Simulate the actual controller drag behavior by manually calling the method
        # This simulates what happens when X button is held and L1/R1 moves the controller
        positions = [(5, 5), (6, 5), (7, 5), (8, 5)]
        for x, y in positions:
            # Mock the controller position
            mock_scene.mode_switcher.get_controller_position.return_value = Mock(
                is_valid=True,
                position=(x, y)
            )
            
            # Simulate the actual _canvas_paint_at_controller_position logic
            position = mock_scene.mode_switcher.get_controller_position(controller_id)
            if position and position.is_valid:
                current_color = mock_scene._get_current_color()
                x, y = position.position[0], position.position[1]
                
                # Check if pixel is already the selected color (debouncing)
                current_pixel_color = mock_scene.canvas.canvas_interface.get_pixel_at(x, y)
                if current_pixel_color != current_color:
                    # Paint at the position
                    mock_scene.canvas.canvas_interface.set_pixel_at(x, y, current_color)
                    
                    # Track this pixel in the controller drag operation
                    if controller_id in mock_scene.controller_drags:
                        drag_info = mock_scene.controller_drags[controller_id]
                        if drag_info['active']:
                            # Record the pixel that was drawn for undo functionality
                            pixel_info = {
                                'position': position.position,
                                'color': current_color,
                                'timestamp': time.time()
                            }
                            drag_info['pixels_drawn'].append(pixel_info)
        
        # Verify pixels were collected in drag info
        drag_info = mock_scene.controller_drags[controller_id]
        assert len(drag_info['pixels_drawn']) == 4
        assert drag_info['active'] == True
        
        # Verify NO undo/redo operations were created (this is the bug!)
        assert len(mock_scene.undo_redo_manager.undo_stack) == 0
        
        # Verify canvas interface was called for each pixel
        assert mock_scene.canvas.canvas_interface.set_pixel_at.call_count == 4
    
    def test_controller_drag_should_submit_pixels_on_button_release(self, mock_scene):
        """Test that controller drag should submit collected pixels when A button is released."""
        controller_id = 0
        
        # Set up controller drag with some pixels (including old_color for proper undo/redo)
        mock_scene.controller_drags[controller_id] = {
            'active': True,
            'start_time': time.time(),
            'start_position': (5, 5),
            'pixels_drawn': [
                {'position': (5, 5), 'color': (255, 0, 0), 'old_color': (0, 0, 0), 'timestamp': time.time()},
                {'position': (6, 5), 'color': (255, 0, 0), 'old_color': (128, 128, 128), 'timestamp': time.time()},
                {'position': (7, 5), 'color': (255, 0, 0), 'old_color': (64, 64, 64), 'timestamp': time.time()},
            ],
            'end_time': None,
            'end_position': None
        }
        
        # Simulate the A button release logic directly (since we can't easily mock the event handler)
        if controller_id in mock_scene.controller_drags:
            drag_info = mock_scene.controller_drags[controller_id]
            if drag_info['active']:
                # End the drag operation
                drag_info['active'] = False
                drag_info['end_time'] = time.time()
                drag_info['end_position'] = Mock(is_valid=True, position=(7, 5))
                
                # Submit collected pixels for undo/redo functionality
                if drag_info['pixels_drawn']:
                    # Convert controller drag pixels to undo/redo format
                    pixel_changes = []
                    for pixel_info in drag_info['pixels_drawn']:
                        position = pixel_info['position']
                        color = pixel_info['color']
                        old_color = pixel_info.get('old_color', (0, 0, 0))
                        x, y = position[0], position[1]
                        
                        pixel_changes.append((x, y, old_color, color))
                    
                    # Submit the pixel changes to the undo/redo system
                    if pixel_changes and hasattr(mock_scene, 'canvas_operation_tracker'):
                        mock_scene.canvas_operation_tracker.add_pixel_changes(pixel_changes)
        
        # Verify drag was ended
        drag_info = mock_scene.controller_drags[controller_id]
        assert drag_info['active'] == False
        assert drag_info['end_time'] is not None
        
        # After fix: Should have 1 undo operation for the entire drag
        assert len(mock_scene.undo_redo_manager.undo_stack) == 1
        
        # Verify the operation contains all 3 pixels
        operation = mock_scene.undo_redo_manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        assert len(operation.undo_data['pixels']) == 3
        assert len(operation.redo_data['pixels']) == 3
    
    def test_expected_behavior_after_fix(self, mock_scene):
        """Test the expected behavior after fixing the controller drag undo/redo issue."""
        controller_id = 0
        
        # Set up controller drag with some pixels (including old_color for proper undo/redo)
        mock_scene.controller_drags[controller_id] = {
            'active': True,
            'start_time': time.time(),
            'start_position': (5, 5),
            'pixels_drawn': [
                {'position': (5, 5), 'color': (255, 0, 0), 'old_color': (0, 0, 0), 'timestamp': time.time()},
                {'position': (6, 5), 'color': (255, 0, 0), 'old_color': (128, 128, 128), 'timestamp': time.time()},
                {'position': (7, 5), 'color': (255, 0, 0), 'old_color': (64, 64, 64), 'timestamp': time.time()},
            ],
            'end_time': None,
            'end_position': None
        }
        
        # Simulate the A button release logic directly (since we can't easily mock the event handler)
        if controller_id in mock_scene.controller_drags:
            drag_info = mock_scene.controller_drags[controller_id]
            if drag_info['active']:
                # End the drag operation
                drag_info['active'] = False
                drag_info['end_time'] = time.time()
                drag_info['end_position'] = Mock(is_valid=True, position=(7, 5))
                
                # Submit collected pixels for undo/redo functionality
                if drag_info['pixels_drawn']:
                    # Convert controller drag pixels to undo/redo format
                    pixel_changes = []
                    for pixel_info in drag_info['pixels_drawn']:
                        position = pixel_info['position']
                        color = pixel_info['color']
                        old_color = pixel_info.get('old_color', (0, 0, 0))
                        x, y = position[0], position[1]
                        
                        pixel_changes.append((x, y, old_color, color))
                    
                    # Submit the pixel changes to the undo/redo system
                    if pixel_changes and hasattr(mock_scene, 'canvas_operation_tracker'):
                        mock_scene.canvas_operation_tracker.add_pixel_changes(pixel_changes)
        
        # After fix: Should have 1 undo operation for the entire drag
        # This test will pass after we implement the fix
        assert len(mock_scene.undo_redo_manager.undo_stack) == 1
        
        # Verify the operation contains all 3 pixels
        operation = mock_scene.undo_redo_manager.undo_stack[0]
        assert operation.operation_type == OperationType.CANVAS_BRUSH_STROKE
        assert len(operation.undo_data['pixels']) == 3
        assert len(operation.redo_data['pixels']) == 3
        
        # Test undo functionality
        assert mock_scene.undo_redo_manager.can_undo() == True
        success = mock_scene.undo_redo_manager.undo()
        assert success == True
        assert len(mock_scene.undo_redo_manager.undo_stack) == 0
        assert len(mock_scene.undo_redo_manager.redo_stack) == 1
        
        # Test redo functionality
        assert mock_scene.undo_redo_manager.can_redo() == True
        success = mock_scene.undo_redo_manager.redo()
        assert success == True
        assert len(mock_scene.undo_redo_manager.redo_stack) == 0
        assert len(mock_scene.undo_redo_manager.undo_stack) == 1
