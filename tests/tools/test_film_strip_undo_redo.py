#!/usr/bin/env python3
"""
Test suite for film strip undo/redo functionality.

Tests complex scenarios involving:
- Multiple animation strips
- Frame creation and editing
- Frame selection switching
- Strip creation and deletion
- Mixed undo/redo operations
"""

import pytest
import pygame
from unittest.mock import Mock, patch

from glitchygames.tools.undo_redo_manager import UndoRedoManager, OperationType
from glitchygames.tools.operation_history import (
    CanvasOperationTracker,
    FilmStripOperationTracker,
    CrossAreaOperationTracker
)
from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame


class TestFilmStripUndoRedo:
    """Test film strip undo/redo functionality."""
    
    @pytest.fixture
    def mock_scene(self):
        """Create a mock scene for testing."""
        class MockScene:
            def __init__(self):
                self.canvas = MockCanvas()
                self.undo_redo_manager = UndoRedoManager(max_history=50)
                self.canvas_operation_tracker = CanvasOperationTracker(self.undo_redo_manager)
                self.film_strip_operation_tracker = FilmStripOperationTracker(self.undo_redo_manager)
                self.cross_area_operation_tracker = CrossAreaOperationTracker(self.undo_redo_manager)
                
                # Set up callbacks
                self.undo_redo_manager.set_pixel_change_callback(self._apply_pixel_change)
                self.undo_redo_manager.set_film_strip_callbacks(
                    add_frame_callback=self._add_frame,
                    delete_frame_callback=self._delete_frame,
                    reorder_frame_callback=self._reorder_frame,
                    add_animation_callback=self._add_animation,
                    delete_animation_callback=self._delete_animation
                )
                self.undo_redo_manager.set_frame_selection_callback(self._apply_frame_selection)
                
                # Track current state
                self.current_animation = "strip_1"
                self.current_frame = 0
                self.animated_sprite = self._create_test_sprite()
                
            def _create_test_sprite(self):
                """Create a test animated sprite with initial data."""
                sprite = AnimatedSprite()
                
                # Create initial animation with one frame
                frame1 = SpriteFrame(
                    surface=pygame.Surface((32, 32)),
                    duration=1.0
                )
                frame1.pixels = [(255, 0, 0)] * (32 * 32)  # Red frame
                
                sprite._animations = {
                    "strip_1": [frame1]
                }
                
                return sprite
                
            def _apply_pixel_change(self, x, y, color):
                """Mock pixel change application."""
                return True
                
            def _add_frame(self, frame_index, animation_name, frame_data):
                """Mock frame addition."""
                return True
                
            def _delete_frame(self, frame_index, animation_name):
                """Mock frame deletion."""
                return True
                
            def _reorder_frame(self, old_index, new_index, animation_name):
                """Mock frame reordering."""
                return True
                
            def _add_animation(self, animation_name, animation_data):
                """Mock animation addition."""
                return True
                
            def _delete_animation(self, animation_name):
                """Mock animation deletion."""
                return True
                
            def _apply_frame_selection(self, animation, frame):
                """Mock frame selection."""
                self.current_animation = animation
                self.current_frame = frame
                return True
                
            def switch_to_frame(self, animation, frame):
                """Switch to a specific frame and track the selection."""
                self.film_strip_operation_tracker.add_frame_selection(animation, frame)
                
            def create_frame(self, animation, frame_index):
                """Create a new frame and track it."""
                frame_data = {
                    "width": 32,
                    "height": 32,
                    "pixels": [(0, 255, 0)] * (32 * 32),  # Green frame
                    "duration": 1.0
                }
                self.film_strip_operation_tracker.add_frame_added(frame_index, animation, frame_data)
                
            def create_animation(self, animation_name):
                """Create a new animation and track it."""
                animation_data = {
                    "frames": [{
                        "width": 32,
                        "height": 32,
                        "pixels": [(0, 0, 255)] * (32 * 32),  # Blue frame
                        "duration": 1.0
                    }],
                    "frame_count": 1
                }
                self.film_strip_operation_tracker.add_animation_added(animation_name, animation_data)
                
            def edit_pixel(self, x, y, old_color, new_color):
                """Edit a pixel and track it."""
                self.canvas_operation_tracker.add_single_pixel_change(x, y, old_color, new_color)
                
            def undo(self):
                """Perform undo operation."""
                return self.undo_redo_manager.undo()
                
            def redo(self):
                """Perform redo operation."""
                return self.undo_redo_manager.redo()
                
            def get_undo_count(self):
                """Get number of operations in undo stack."""
                return len(self.undo_redo_manager.undo_stack)
                
            def get_redo_count(self):
                """Get number of operations in redo stack."""
                return len(self.undo_redo_manager.redo_stack)

        class MockCanvas:
            def __init__(self):
                self.current_animation = "strip_1"
                self.current_frame = 0
                
        return MockScene()

    def test_basic_frame_editing_and_switching(self, mock_scene):
        """Test basic frame editing and switching operations."""
        # Edit some pixels
        mock_scene.edit_pixel(10, 10, (255, 0, 0), (255, 255, 0))
        mock_scene.edit_pixel(15, 15, (255, 0, 0), (255, 255, 0))
        
        assert mock_scene.get_undo_count() == 2
        
        # Switch to different frame (should create frame selection operation)
        mock_scene.switch_to_frame("strip_1", 0)
        
        assert mock_scene.get_undo_count() == 3
        
        # Undo the frame selection
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == 2
        assert mock_scene.get_redo_count() == 1

    def test_frame_creation_and_editing(self, mock_scene):
        """Test frame creation and editing operations."""
        # Create a new frame
        mock_scene.create_frame("strip_1", 1)
        assert mock_scene.get_undo_count() == 1
        
        # Switch to the new frame
        mock_scene.switch_to_frame("strip_1", 1)
        assert mock_scene.get_undo_count() == 2
        
        # Edit the new frame
        mock_scene.edit_pixel(20, 20, (0, 255, 0), (255, 0, 255))
        assert mock_scene.get_undo_count() == 3
        
        # Undo the edit
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == 2
        
        # Undo the frame creation
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == 1

    def test_animation_creation_and_frame_operations(self, mock_scene):
        """Test animation creation and frame operations."""
        # Create a new animation
        mock_scene.create_animation("strip_2")
        assert mock_scene.get_undo_count() == 1
        
        # Switch to the new animation
        mock_scene.switch_to_frame("strip_2", 0)
        assert mock_scene.get_undo_count() == 2
        
        # Create a frame in the new animation
        mock_scene.create_frame("strip_2", 1)
        assert mock_scene.get_undo_count() == 3
        
        # Switch to the new frame
        mock_scene.switch_to_frame("strip_2", 1)
        assert mock_scene.get_undo_count() == 4
        
        # Edit the frame
        mock_scene.edit_pixel(25, 25, (0, 0, 255), (255, 255, 255))
        assert mock_scene.get_undo_count() == 5

    def test_complex_undo_sequence(self, mock_scene):
        """Test complex undo sequence."""
        # Create operations
        mock_scene.create_animation("strip_2")
        mock_scene.switch_to_frame("strip_2", 0)
        mock_scene.create_frame("strip_2", 1)
        mock_scene.switch_to_frame("strip_2", 1)
        mock_scene.edit_pixel(25, 25, (0, 0, 255), (255, 255, 255))
        
        initial_undo_count = mock_scene.get_undo_count()
        
        # Undo the edit
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == initial_undo_count - 1
        
        # Undo the frame creation
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == initial_undo_count - 2
        
        # Undo the animation creation
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == initial_undo_count - 3

    def test_redo_sequence(self, mock_scene):
        """Test redo sequence."""
        # Create operations
        mock_scene.create_animation("strip_2")
        mock_scene.switch_to_frame("strip_2", 0)
        mock_scene.create_frame("strip_2", 1)
        
        initial_undo_count = mock_scene.get_undo_count()
        
        # Undo all operations
        assert mock_scene.undo() == True
        assert mock_scene.undo() == True
        assert mock_scene.undo() == True
        
        assert mock_scene.get_undo_count() == initial_undo_count - 3
        assert mock_scene.get_redo_count() == 3
        
        # Redo all operations
        assert mock_scene.redo() == True
        assert mock_scene.redo() == True
        assert mock_scene.redo() == True
        
        assert mock_scene.get_undo_count() == initial_undo_count
        assert mock_scene.get_redo_count() == 0

    def test_mixed_operations_with_frame_switching(self, mock_scene):
        """Test mixed operations with frame switching."""
        # Create operations
        mock_scene.create_animation("strip_2")
        mock_scene.switch_to_frame("strip_2", 0)
        mock_scene.create_frame("strip_2", 1)
        mock_scene.switch_to_frame("strip_2", 1)
        mock_scene.edit_pixel(25, 25, (0, 0, 255), (255, 255, 255))
        
        # Switch back to strip_1
        mock_scene.switch_to_frame("strip_1", 0)
        
        # Create another frame in strip_1
        mock_scene.create_frame("strip_1", 2)
        mock_scene.switch_to_frame("strip_1", 2)
        mock_scene.edit_pixel(30, 30, (255, 0, 0), (0, 255, 255))
        
        # Switch back to strip_2
        mock_scene.switch_to_frame("strip_2", 1)
        mock_scene.edit_pixel(5, 5, (0, 0, 255), (255, 0, 0))
        
        # Should have many operations
        assert mock_scene.get_undo_count() > 5

    def test_edge_case_multiple_rapid_operations(self, mock_scene):
        """Test edge case with multiple rapid operations."""
        # Rapid frame creation and switching
        mock_scene.create_frame("strip_1", 3)
        mock_scene.switch_to_frame("strip_1", 3)
        mock_scene.create_frame("strip_1", 4)
        mock_scene.switch_to_frame("strip_1", 4)
        mock_scene.edit_pixel(1, 1, (255, 0, 0), (0, 0, 0))
        
        # Should have 5 operations
        assert mock_scene.get_undo_count() == 5
        
        # Undo all operations
        for i in range(5):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 4 - i

    def test_animation_deletion_operations(self, mock_scene):
        """Test animation deletion operations."""
        # Create another animation
        mock_scene.create_animation("strip_3")
        mock_scene.switch_to_frame("strip_3", 0)
        mock_scene.create_frame("strip_3", 1)
        mock_scene.switch_to_frame("strip_3", 1)
        mock_scene.edit_pixel(10, 10, (0, 0, 255), (255, 255, 0))
        
        initial_undo_count = mock_scene.get_undo_count()
        
        # Undo the edit
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == initial_undo_count - 1
        
        # Undo the frame creation
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == initial_undo_count - 2
        
        # Undo the animation creation
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == initial_undo_count - 3

    def test_stress_test_many_operations(self, mock_scene):
        """Test stress test with many operations."""
        # Create many operations
        for i in range(10):
            mock_scene.create_frame("strip_1", i + 5)
            mock_scene.switch_to_frame("strip_1", i + 5)
            mock_scene.edit_pixel(i, i, (255, 0, 0), (i * 25, i * 25, i * 25))
        
        # Should have 30 operations (3 per iteration)
        assert mock_scene.get_undo_count() == 30
        
        # Undo all operations
        for i in range(30):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 29 - i

    def test_frame_selection_undo_redo(self, mock_scene):
        """Test frame selection undo/redo specifically."""
        # Switch between frames multiple times
        mock_scene.switch_to_frame("strip_1", 0)
        mock_scene.switch_to_frame("strip_1", 0)  # Same frame, should not create operation
        mock_scene.switch_to_frame("strip_1", 1)  # Different frame, should create operation
        
        # Should have 2 operations (first switch and second switch)
        assert mock_scene.get_undo_count() == 2
        
        # Undo frame selection
        assert mock_scene.undo() == True
        assert mock_scene.get_undo_count() == 1
        
        # Redo frame selection
        assert mock_scene.redo() == True
        assert mock_scene.get_undo_count() == 2

    def test_operation_descriptions(self, mock_scene):
        """Test that operations have proper descriptions."""
        # Create various operations
        mock_scene.edit_pixel(10, 10, (255, 0, 0), (255, 255, 0))
        mock_scene.create_frame("strip_1", 1)
        mock_scene.create_animation("strip_2")
        mock_scene.switch_to_frame("strip_1", 1)
        
        # Check operation descriptions
        operations = mock_scene.undo_redo_manager.undo_stack
        assert len(operations) == 4
        
        # Check that descriptions are meaningful
        assert "Pixel change" in operations[0].description
        assert "Added frame" in operations[1].description
        assert "Added animation" in operations[2].description
        assert "Selected frame" in operations[3].description

    def test_undo_redo_stack_limits(self, mock_scene):
        """Test that undo/redo stacks respect size limits."""
        # Create more operations than the limit
        for i in range(60):  # More than max_history of 50
            mock_scene.edit_pixel(i, i, (255, 0, 0), (i, i, i))
        
        # Should be limited to max_history
        assert mock_scene.get_undo_count() == 50
        
        # Undo all operations
        for i in range(50):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 49 - i

    def test_mixed_operation_types(self, mock_scene):
        """Test mixed operation types in undo stack."""
        # Create different types of operations
        mock_scene.edit_pixel(10, 10, (255, 0, 0), (255, 255, 0))  # Canvas operation
        mock_scene.create_frame("strip_1", 1)  # Film strip operation
        mock_scene.switch_to_frame("strip_1", 1)  # Frame selection operation
        mock_scene.create_animation("strip_2")  # Film strip operation
        
        # All operations should be in the same undo stack
        assert mock_scene.get_undo_count() == 4
        
        # Undo all operations
        for i in range(4):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 3 - i
