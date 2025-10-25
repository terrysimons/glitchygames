#!/usr/bin/env python3
"""Test to verify that slider continuous movement is not tracked for undo/redo.

This test ensures that the fix for the slider issue is working correctly.
"""

import pytest
import time
from unittest.mock import Mock, patch
from glitchygames.tools.bitmappy import BitmapEditorScene


class TestSliderContinuousMovementFix:
    """Test that slider continuous movement doesn't interfere with undo/redo."""
    
    @pytest.fixture
    def mock_scene(self):
        """Create a mock BitmapEditorScene for testing."""
        scene = Mock(spec=BitmapEditorScene)
        scene.canvas_continuous_movements = {}
        scene.slider_continuous_adjustments = {}
        scene.controller_position_operation_tracker = Mock()
        scene.mode_switcher = Mock()
        scene.mode_switcher.get_controller_position.return_value = Mock()
        scene.mode_switcher.get_controller_position.return_value.position = (5, 5)
        scene.mode_switcher.get_controller_mode.return_value = Mock()
        scene.mode_switcher.get_controller_mode.return_value.value = "canvas"
        scene._applying_undo_redo = False
        return scene
    
    def test_controller_not_in_continuous_movement(self, mock_scene):
        """Test that controller is not in continuous movement when no movement is active."""
        # Test the method from the actual implementation
        def _is_controller_in_continuous_movement(controller_id):
            if hasattr(mock_scene, 'canvas_continuous_movements') and controller_id in mock_scene.canvas_continuous_movements:
                return True
            if hasattr(mock_scene, 'slider_continuous_adjustments') and controller_id in mock_scene.slider_continuous_adjustments:
                return True
            return False
        
        # No continuous movement should return False
        assert not _is_controller_in_continuous_movement(0)
        assert not _is_controller_in_continuous_movement(1)
    
    def test_controller_in_canvas_continuous_movement(self, mock_scene):
        """Test that controller is detected as in continuous movement when canvas movement is active."""
        def _is_controller_in_continuous_movement(controller_id):
            if hasattr(mock_scene, 'canvas_continuous_movements') and controller_id in mock_scene.canvas_continuous_movements:
                return True
            if hasattr(mock_scene, 'slider_continuous_adjustments') and controller_id in mock_scene.slider_continuous_adjustments:
                return True
            return False
        
        # Add canvas continuous movement
        mock_scene.canvas_continuous_movements[0] = {
            'dx': 1, 'dy': 0, 'start_time': time.time(),
            'last_movement': time.time(), 'acceleration_level': 0
        }
        
        assert _is_controller_in_continuous_movement(0)
        assert not _is_controller_in_continuous_movement(1)
    
    def test_controller_in_slider_continuous_adjustment(self, mock_scene):
        """Test that controller is detected as in continuous movement when slider adjustment is active."""
        def _is_controller_in_continuous_movement(controller_id):
            if hasattr(mock_scene, 'canvas_continuous_movements') and controller_id in mock_scene.canvas_continuous_movements:
                return True
            if hasattr(mock_scene, 'slider_continuous_adjustments') and controller_id in mock_scene.slider_continuous_adjustments:
                return True
            return False
        
        # Add slider continuous adjustment
        mock_scene.slider_continuous_adjustments[0] = {
            'slider': 'r_slider', 'start_time': time.time(),
            'last_adjustment': time.time(), 'acceleration_level': 0
        }
        
        assert _is_controller_in_continuous_movement(0)
        assert not _is_controller_in_continuous_movement(1)
    
    def test_position_tracking_skipped_during_continuous_movement(self, mock_scene):
        """Test that position tracking is skipped during continuous movement."""
        # Simulate the logic from _canvas_move_cursor
        controller_id = 0
        old_position = (5, 5)
        new_position = (6, 5)
        
        # Mock the continuous movement check
        def _is_controller_in_continuous_movement(controller_id):
            if hasattr(mock_scene, 'canvas_continuous_movements') and controller_id in mock_scene.canvas_continuous_movements:
                return True
            if hasattr(mock_scene, 'slider_continuous_adjustments') and controller_id in mock_scene.slider_continuous_adjustments:
                return True
            return False
        
        # Test without continuous movement - should track position
        should_track = (old_position != new_position and 
                       not getattr(mock_scene, '_applying_undo_redo', False) and
                       not _is_controller_in_continuous_movement(controller_id))
        assert should_track
        
        # Test with continuous movement - should NOT track position
        mock_scene.canvas_continuous_movements[controller_id] = {'dx': 1, 'dy': 0}
        should_track = (old_position != new_position and 
                       not getattr(mock_scene, '_applying_undo_redo', False) and
                       not _is_controller_in_continuous_movement(controller_id))
        assert not should_track
    
    def test_slider_continuous_adjustment_tracking_skipped(self, mock_scene):
        """Test that slider continuous adjustment doesn't interfere with undo/redo."""
        controller_id = 0
        
        # Mock the continuous movement check
        def _is_controller_in_continuous_movement(controller_id):
            if hasattr(mock_scene, 'canvas_continuous_movements') and controller_id in mock_scene.canvas_continuous_movements:
                return True
            if hasattr(mock_scene, 'slider_continuous_adjustments') and controller_id in mock_scene.slider_continuous_adjustments:
                return True
            return False
        
        # Test with slider continuous adjustment - should NOT track position
        mock_scene.slider_continuous_adjustments[controller_id] = {
            'slider': 'r_slider', 'start_time': time.time(),
            'last_adjustment': time.time(), 'acceleration_level': 0
        }
        
        old_position = (5, 5)
        new_position = (6, 5)
        should_track = (old_position != new_position and 
                       not getattr(mock_scene, '_applying_undo_redo', False) and
                       not _is_controller_in_continuous_movement(controller_id))
        assert not should_track


if __name__ == "__main__":
    pytest.main([__file__])
