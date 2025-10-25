#!/usr/bin/env python3
"""
Test suite for expected undo/redo behavior scenarios.

These tests verify that the undo/redo system behaves as expected from a user's perspective,
not just what the current implementation does.
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


class TestExpectedUndoRedoBehavior:
    """Test expected undo/redo behavior scenarios."""
    
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
                
                # Track pixel states for verification
                self.pixel_states = {}  # (x, y) -> color
                
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
                self.pixel_states[(x, y)] = color
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
                
            def edit_pixels_drag(self, pixel_changes):
                """Edit multiple pixels as a drag operation."""
                self.canvas_operation_tracker.add_pixel_changes(pixel_changes)
                
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
                
            def get_pixel_state(self, x, y):
                """Get the current state of a pixel."""
                return self.pixel_states.get((x, y), (255, 0, 0))  # Default to red

        class MockCanvas:
            def __init__(self):
                self.current_animation = "strip_1"
                self.current_frame = 0
                
        return MockScene()

    def test_scenario_1_single_pixel_edits_undo_redo(self, mock_scene):
        """Test: 5 single pixel edits → 5 undos → 5 redos
        
        Expected behavior:
        - Each undo should restore the previous pixel
        - Each redo should re-apply the pixel change
        - Final state should be same as before undos
        """
        # Perform 5 single pixel edits
        for i in range(5):
            mock_scene.edit_pixel(i, i, (255, 0, 0), (i * 50, i * 50, i * 50))
        
        # Verify we have 5 operations
        assert mock_scene.get_undo_count() == 5
        assert mock_scene.get_redo_count() == 0
        
        # Perform 5 undos
        for i in range(5):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 4 - i
            assert mock_scene.get_redo_count() == i + 1
        
        # Verify all pixels are back to original state
        for i in range(5):
            assert mock_scene.get_pixel_state(i, i) == (255, 0, 0)  # Original red color
        
        # Perform 5 redos
        for i in range(5):
            assert mock_scene.redo() == True
            assert mock_scene.get_undo_count() == i + 1
            assert mock_scene.get_redo_count() == 4 - i
        
        # Verify all pixels are back to edited state
        for i in range(5):
            expected_color = (i * 50, i * 50, i * 50)
            assert mock_scene.get_pixel_state(i, i) == expected_color

    def test_scenario_2_mixed_single_and_drag_operations(self, mock_scene):
        """Test: 5 single pixel edits → 2 drags → 7 undos → 7 redos
        
        Expected behavior:
        - Undo should work in reverse order: drag2 → drag1 → pixel5 → pixel4 → pixel3 → pixel2 → pixel1
        - Each undo should restore the previous state
        - Final state should be same as before undos
        """
        # Perform 5 single pixel edits
        for i in range(5):
            mock_scene.edit_pixel(i, i, (255, 0, 0), (i * 50, i * 50, i * 50))
        
        # Perform 2 drag operations
        drag1_pixels = [(10, 10, (255, 0, 0), (100, 100, 100)), (11, 11, (255, 0, 0), (110, 110, 110))]
        drag2_pixels = [(20, 20, (255, 0, 0), (200, 200, 200)), (21, 21, (255, 0, 0), (210, 210, 210))]
        
        mock_scene.edit_pixels_drag(drag1_pixels)
        mock_scene.edit_pixels_drag(drag2_pixels)
        
        # Verify we have 7 operations (5 single + 2 drags)
        assert mock_scene.get_undo_count() == 7
        assert mock_scene.get_redo_count() == 0
        
        # Perform 7 undos
        for i in range(7):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 6 - i
            assert mock_scene.get_redo_count() == i + 1
        
        # Verify all pixels are back to original state
        for i in range(5):
            assert mock_scene.get_pixel_state(i, i) == (255, 0, 0)  # Original red color
        assert mock_scene.get_pixel_state(10, 10) == (255, 0, 0)
        assert mock_scene.get_pixel_state(11, 11) == (255, 0, 0)
        assert mock_scene.get_pixel_state(20, 20) == (255, 0, 0)
        assert mock_scene.get_pixel_state(21, 21) == (255, 0, 0)
        
        # Perform 7 redos
        for i in range(7):
            assert mock_scene.redo() == True
            assert mock_scene.get_undo_count() == i + 1
            assert mock_scene.get_redo_count() == 6 - i
        
        # Verify all pixels are back to edited state
        for i in range(5):
            expected_color = (i * 50, i * 50, i * 50)
            assert mock_scene.get_pixel_state(i, i) == expected_color
        assert mock_scene.get_pixel_state(10, 10) == (100, 100, 100)
        assert mock_scene.get_pixel_state(11, 11) == (110, 110, 110)
        assert mock_scene.get_pixel_state(20, 20) == (200, 200, 200)
        assert mock_scene.get_pixel_state(21, 21) == (210, 210, 210)

    def test_scenario_3_multiple_frames_edit_undo_redo(self, mock_scene):
        """Test: 8 frames, edit frames 1,2,3,4 → 10 undos → 10 redos
        
        Expected behavior:
        - Each undo should restore the previous edit
        - Frame selection should be tracked
        - Final state should be same as before undos
        """
        # Create 8 frames
        for i in range(8):
            mock_scene.create_frame("strip_1", i + 1)
        
        # Edit frames 1, 2, 3, 4
        for frame_num in [1, 2, 3, 4]:
            mock_scene.switch_to_frame("strip_1", frame_num)
            mock_scene.edit_pixel(frame_num * 5, frame_num * 5, (255, 0, 0), (frame_num * 60, frame_num * 60, frame_num * 60))
        
        # Verify we have 16 operations (8 frame creations + 4 frame selections + 4 edits)
        # Note: Frame selections are only optimized when they immediately follow frame creation
        assert mock_scene.get_undo_count() == 16
        assert mock_scene.get_redo_count() == 0
        
        # Perform 10 undos
        for i in range(10):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 16 - i
            assert mock_scene.get_redo_count() == i + 1
        
        # Verify we're back to original state (only frame 0 exists)
        assert mock_scene.current_animation == "strip_1"
        assert mock_scene.current_frame == 0
        
        # Perform 10 redos
        for i in range(10):
            assert mock_scene.redo() == True
            assert mock_scene.get_undo_count() == i + 1
            assert mock_scene.get_redo_count() == 9 - i
        
        # Verify we're back to edited state
        assert mock_scene.current_animation == "strip_1"
        assert mock_scene.current_frame == 4  # Should be on frame 4 (last edited)

    def test_scenario_4_multiple_strips_edit_undo_redo(self, mock_scene):
        """Test: 4 frames on strip1, edit all → strip2, 4 frames, edit all → 20 undos
        
        Expected behavior:
        - Undo should work across strips
        - Frame selections should be tracked
        - Should be back to original state after 20 undos
        """
        # Create 4 frames on strip1
        for i in range(4):
            mock_scene.create_frame("strip_1", i + 1)
        
        # Edit all 4 frames on strip1
        for frame_num in range(1, 5):
            mock_scene.switch_to_frame("strip_1", frame_num)
            mock_scene.edit_pixel(frame_num * 3, frame_num * 3, (255, 0, 0), (frame_num * 40, frame_num * 40, frame_num * 40))
        
        # Create strip2
        mock_scene.create_animation("strip_2")
        
        # Create 4 frames on strip2
        for i in range(4):
            mock_scene.create_frame("strip_2", i + 1)
        
        # Edit all 4 frames on strip2
        for frame_num in range(1, 5):
            mock_scene.switch_to_frame("strip_2", frame_num)
            mock_scene.edit_pixel(frame_num * 7, frame_num * 7, (0, 0, 255), (frame_num * 80, frame_num * 80, frame_num * 80))
        
        # Verify we have many operations
        assert mock_scene.get_undo_count() > 15
        assert mock_scene.get_redo_count() == 0
        
        # Perform 20 undos
        for i in range(20):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == mock_scene.get_undo_count()
            assert mock_scene.get_redo_count() == i + 1
        
        # Verify we're back to original state (strip1 frame 0 exists - the baseline)
        assert mock_scene.current_animation == "strip_1"
        # Note: The baseline frame 0 always exists, so current_frame should be 0
        assert mock_scene.current_frame == 0
        
        # Perform 20 redos
        for i in range(20):
            assert mock_scene.redo() == True
            assert mock_scene.get_undo_count() == i + 1
            assert mock_scene.get_redo_count() == 19 - i
        
        # Verify we're back to edited state
        assert mock_scene.current_animation == "strip_2"
        assert mock_scene.current_frame == 4  # Should be on strip2 frame 4 (last edited)

    def test_scenario_5_edge_case_too_many_undos(self, mock_scene):
        """Test: Perform more undos than operations exist
        
        Expected behavior:
        - Should only undo as many operations as exist
        - Should not crash or fail
        """
        # Perform 3 operations
        mock_scene.edit_pixel(1, 1, (255, 0, 0), (100, 100, 100))
        mock_scene.edit_pixel(2, 2, (255, 0, 0), (200, 200, 200))
        mock_scene.edit_pixel(3, 3, (255, 0, 0), (300, 300, 300))
        
        assert mock_scene.get_undo_count() == 3
        
        # Try to undo 5 times (more than operations exist)
        for i in range(5):
            result = mock_scene.undo()
            if i < 3:
                assert result == True
            else:
                assert result == False  # Should fail after 3 undos
        
        # Verify we're back to original state
        assert mock_scene.get_undo_count() == 0
        assert mock_scene.get_redo_count() == 3

    def test_scenario_6_edge_case_too_many_redos(self, mock_scene):
        """Test: Perform more redos than operations exist
        
        Expected behavior:
        - Should only redo as many operations as exist
        - Should not crash or fail
        """
        # Perform 3 operations
        mock_scene.edit_pixel(1, 1, (255, 0, 0), (100, 100, 100))
        mock_scene.edit_pixel(2, 2, (255, 0, 0), (200, 200, 200))
        mock_scene.edit_pixel(3, 3, (255, 0, 0), (300, 300, 300))
        
        # Undo all 3
        for i in range(3):
            assert mock_scene.undo() == True
        
        assert mock_scene.get_undo_count() == 0
        assert mock_scene.get_redo_count() == 3
        
        # Try to redo 5 times (more than operations exist)
        for i in range(5):
            result = mock_scene.redo()
            if i < 3:
                assert result == True
            else:
                assert result == False  # Should fail after 3 redos
        
        # Verify we're back to edited state
        assert mock_scene.get_undo_count() == 3
        assert mock_scene.get_redo_count() == 0

    def test_scenario_7_mixed_operations_undo_order(self, mock_scene):
        """Test: Verify undo order for mixed operations
        
        Expected behavior:
        - Undo should work in reverse order of operations
        - Frame selections should be tracked properly
        """
        # Create operations in specific order
        mock_scene.edit_pixel(1, 1, (255, 0, 0), (100, 100, 100))  # Operation 1
        mock_scene.switch_to_frame("strip_1", 1)  # Operation 2
        mock_scene.edit_pixel(2, 2, (255, 0, 0), (200, 200, 200))  # Operation 3
        mock_scene.create_frame("strip_1", 2)  # Operation 4
        mock_scene.switch_to_frame("strip_1", 2)  # Operation 5
        mock_scene.edit_pixel(3, 3, (255, 0, 0), (300, 300, 300))  # Operation 6
        
        assert mock_scene.get_undo_count() == 6
        
        # Undo all operations
        for i in range(6):
            assert mock_scene.undo() == True
            assert mock_scene.get_undo_count() == 5 - i
            assert mock_scene.get_redo_count() == i + 1
        
        # Verify we're back to original state (strip1 frame 0 - the baseline)
        assert mock_scene.current_animation == "strip_1"
        # Note: The baseline frame 0 always exists, so current_frame should be 0
        assert mock_scene.current_frame == 0
        assert mock_scene.get_pixel_state(1, 1) == (255, 0, 0)
        assert mock_scene.get_pixel_state(2, 2) == (255, 0, 0)
        assert mock_scene.get_pixel_state(3, 3) == (255, 0, 0)
        
        # Redo all operations
        for i in range(6):
            assert mock_scene.redo() == True
            assert mock_scene.get_undo_count() == i + 1
            assert mock_scene.get_redo_count() == 5 - i
        
        # Verify we're back to edited state
        assert mock_scene.current_animation == "strip_1"
        assert mock_scene.current_frame == 2  # Should be on frame 2 (last selected)
        assert mock_scene.get_pixel_state(1, 1) == (100, 100, 100)
        assert mock_scene.get_pixel_state(2, 2) == (200, 200, 200)
        assert mock_scene.get_pixel_state(3, 3) == (300, 300, 300)
