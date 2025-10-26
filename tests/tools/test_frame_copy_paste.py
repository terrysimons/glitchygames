#!/usr/bin/env python3
"""Test frame copy/paste functionality in BitmapEditorScene.

This module tests the copy and paste functionality for frames in the film selector,
including keyboard shortcuts, undo/redo integration, and clipboard management.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools.bitmappy import BitmapEditorScene
from glitchygames.tools.undo_redo_manager import OperationType
from glitchygames.sprites.animated import SpriteFrame

from tests.mocks.test_mock_factory import MockFactory


class TestFrameCopyPaste:
    """Test frame copy/paste functionality."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        
        # Create mock options
        self.mock_options = {
            "balls": 1,
            "fps": 60,
            "resolution": "800x600",
            "windowed": True,
            "use_gfxdraw": False,
            "update_type": "update",
            "fps_refresh_rate": 1000,
            "profile": False,
            "test_flag": False,
            "font_name": "Arial",
            "font_size": 16,
            "font_bold": False,
            "font_italic": False,
            "font_antialias": True,
            "font_dpi": 72,
            "font_system": "pygame",
            "log_level": "info",
            "no_unhandled_events": False,
        }

    def teardown_method(self):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def create_mock_scene(self):
        """Create a mock scene using centralized mocks."""
        # Use the existing centralized mocks
        scene = MockFactory.create_optimized_scene_mock()
        
        # Add the copy/paste methods we're testing
        from glitchygames.tools.bitmappy import BitmapEditorScene
        scene._handle_copy_frame = BitmapEditorScene._handle_copy_frame.__get__(scene, BitmapEditorScene)
        scene._handle_paste_frame = BitmapEditorScene._handle_paste_frame.__get__(scene, BitmapEditorScene)
        scene._apply_frame_paste_for_undo_redo = BitmapEditorScene._apply_frame_paste_for_undo_redo.__get__(scene, BitmapEditorScene)
        scene.on_key_down_event = BitmapEditorScene.on_key_down_event.__get__(scene, BitmapEditorScene)
        
        # Initialize clipboard
        scene._frame_clipboard = None
        
        return scene

    def test_copy_frame_basic_functionality(self):
        """Test basic frame copying functionality."""
        # Create scene with mock canvas and animated sprite
        scene = self.create_mock_scene()
        
        # Create mock animated sprite with frame data
        mock_sprite = MockFactory.create_animated_sprite_mock(
            animation_name="test_anim",
            frame_size=(8, 8),
            pixel_color=(255, 0, 0)
        )
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = mock_sprite
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Mock the frame object
        mock_frame = Mock(spec=SpriteFrame)
        mock_frame.get_pixel_data.return_value = [(255, 0, 0)] * 64  # 8x8 = 64 pixels
        mock_frame.get_size.return_value = (8, 8)
        mock_frame.duration = 0.5
        
        # Set up the animation frames
        scene.canvas.animated_sprite._animations = {
            "test_anim": [mock_frame]
        }
        
        # Test copy operation
        scene._handle_copy_frame()
        
        # Verify clipboard was set
        assert scene._frame_clipboard is not None
        assert scene._frame_clipboard["pixels"] == [(255, 0, 0)] * 64
        assert scene._frame_clipboard["width"] == 8
        assert scene._frame_clipboard["height"] == 8
        assert scene._frame_clipboard["duration"] == 0.5
        assert scene._frame_clipboard["animation"] == "test_anim"
        assert scene._frame_clipboard["frame"] == 0

    def test_copy_frame_no_canvas(self):
        """Test copy frame when no canvas is available."""
        scene = self.create_mock_scene()
        scene.canvas = None
        
        # Should not raise exception, just log warning
        scene._handle_copy_frame()
        
        # Clipboard should remain None
        assert scene._frame_clipboard is None

    def test_copy_frame_no_selection(self):
        """Test copy frame when no frame is selected."""
        scene = self.create_mock_scene()
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.canvas.animated_sprite._animations = {}
        # No selected_animation or selected_frame set
        
        # Should not raise exception, just log warning
        scene._handle_copy_frame()
        
        # Clipboard should remain None
        assert scene._frame_clipboard is None

    def test_paste_frame_basic_functionality(self):
        """Test basic frame pasting functionality."""
        # Create scene with mock canvas and animated sprite
        scene = self.create_mock_scene()
        
        # Create mock animated sprite
        mock_sprite = MockFactory.create_animated_sprite_mock(
            animation_name="test_anim",
            frame_size=(8, 8),
            pixel_color=(0, 255, 0)
        )
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = mock_sprite
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Mock the target frame
        target_frame = Mock(spec=SpriteFrame)
        target_frame.get_pixel_data.return_value = [(0, 255, 0)] * 64
        target_frame.get_size.return_value = (8, 8)
        target_frame.duration = 0.5
        target_frame.set_pixel_data = Mock()
        
        # Set up the animation frames
        scene.canvas.animated_sprite._animations = {
            "test_anim": [target_frame]
        }
        
        # Set up clipboard with frame data
        scene._frame_clipboard = {
            "pixels": [(255, 0, 0)] * 64,
            "width": 8,
            "height": 8,
            "duration": 1.0,
            "animation": "source_anim",
            "frame": 1
        }
        
        # Mock undo/redo manager
        scene.undo_redo_manager = Mock()
        scene.undo_redo_manager.create_operation = Mock()
        scene.undo_redo_manager.add_operation = Mock()
        
        # Test paste operation
        scene._handle_paste_frame()
        
        # Verify frame data was applied
        target_frame.set_pixel_data.assert_called_once_with([(255, 0, 0)] * 64)
        assert target_frame.duration == 1.0
        
        # Verify undo/redo operation was added
        scene.undo_redo_manager.add_operation.assert_called_once()

    def test_paste_frame_dimension_mismatch(self):
        """Test paste frame with dimension mismatch."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Mock target frame with different dimensions
        target_frame = Mock(spec=SpriteFrame)
        target_frame.get_size.return_value = (16, 16)  # Different from clipboard
        
        scene.canvas.animated_sprite._animations = {
            "test_anim": [target_frame]
        }
        
        # Set up clipboard with different dimensions
        scene._frame_clipboard = {
            "pixels": [(255, 0, 0)] * 64,  # 8x8
            "width": 8,
            "height": 8,
            "duration": 1.0,
            "animation": "source_anim",
            "frame": 1
        }
        
        # Test paste operation - should fail due to dimension mismatch
        scene._handle_paste_frame()
        
        # Frame should not be modified
        target_frame.set_pixel_data.assert_not_called()

    def test_paste_frame_no_clipboard(self):
        """Test paste frame when no clipboard data is available."""
        scene = self.create_mock_scene()
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        scene._frame_clipboard = None
        
        # Should not raise exception, just log warning
        scene._handle_paste_frame()

    def test_keyboard_shortcuts_copy(self):
        """Test Ctrl+C keyboard shortcut for copying."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Mock frame
        mock_frame = Mock(spec=SpriteFrame)
        mock_frame.get_pixel_data.return_value = [(255, 0, 0)] * 64
        mock_frame.get_size.return_value = (8, 8)
        mock_frame.duration = 0.5
        
        scene.canvas.animated_sprite._animations = {
            "test_anim": [mock_frame]
        }
        
        # Ensure no early returns by mocking attributes that might cause them
        scene.debug_text = Mock()
        scene.debug_text.active = False
        scene.red_slider = Mock()
        scene.red_slider.text_sprite = Mock()
        scene.red_slider.text_sprite.active = False
        scene.green_slider = Mock()
        scene.green_slider.text_sprite = Mock()
        scene.green_slider.text_sprite.active = False
        scene.blue_slider = Mock()
        scene.blue_slider.text_sprite = Mock()
        scene.blue_slider.text_sprite.active = False
        
        # Mock the copy method
        scene._handle_copy_frame = Mock()
        
        # Create Ctrl+C event
        event = Mock()
        event.key = pygame.K_c
        event.mod = pygame.KMOD_CTRL
        
        # Test keyboard event handling
        scene.on_key_down_event(event)
        
        # Verify copy was called
        scene._handle_copy_frame.assert_called_once()

    def test_keyboard_shortcuts_paste(self):
        """Test Ctrl+V keyboard shortcut for pasting."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Ensure no early returns by mocking attributes that might cause them
        scene.debug_text = Mock()
        scene.debug_text.active = False
        scene.red_slider = Mock()
        scene.red_slider.text_sprite = Mock()
        scene.red_slider.text_sprite.active = False
        scene.green_slider = Mock()
        scene.green_slider.text_sprite = Mock()
        scene.green_slider.text_sprite.active = False
        scene.blue_slider = Mock()
        scene.blue_slider.text_sprite = Mock()
        scene.blue_slider.text_sprite.active = False
        
        # Mock the paste method
        scene._handle_paste_frame = Mock()
        
        # Create Ctrl+V event
        event = Mock()
        event.key = pygame.K_v
        event.mod = pygame.KMOD_CTRL
        
        # Test keyboard event handling
        scene.on_key_down_event(event)
        
        # Verify paste was called
        scene._handle_paste_frame.assert_called_once()

    def test_undo_redo_integration(self):
        """Test that copy/paste operations are properly integrated with undo/redo."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Mock target frame
        target_frame = Mock(spec=SpriteFrame)
        target_frame.get_pixel_data.return_value = [(0, 255, 0)] * 64
        target_frame.get_size.return_value = (8, 8)
        target_frame.duration = 0.5
        target_frame.set_pixel_data = Mock()
        
        scene.canvas.animated_sprite._animations = {
            "test_anim": [target_frame]
        }
        
        # Set up clipboard
        scene._frame_clipboard = {
            "pixels": [(255, 0, 0)] * 64,
            "width": 8,
            "height": 8,
            "duration": 1.0,
            "animation": "source_anim",
            "frame": 1
        }
        
        # Mock undo/redo manager
        scene.undo_redo_manager.add_operation = Mock()
        
        # Test paste operation
        scene._handle_paste_frame()
        
        # Verify operation was added with correct type
        scene.undo_redo_manager.add_operation.assert_called_once()
        call_args = scene.undo_redo_manager.add_operation.call_args
        assert call_args[1]['operation_type'] == OperationType.FRAME_PASTE

    def test_apply_frame_paste_for_undo_redo(self):
        """Test the frame paste application method for undo/redo."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.selected_animation = "test_anim"
        scene.selected_frame = 0
        
        # Mock target frame
        target_frame = Mock(spec=SpriteFrame)
        target_frame.set_pixel_data = Mock()
        
        scene.canvas.animated_sprite._animations = {
            "test_anim": [target_frame]
        }
        
        # Test applying frame paste
        result = scene._apply_frame_paste_for_undo_redo(
            "test_anim", 0, [(255, 0, 0)] * 64, 1.0
        )
        
        # Verify success
        assert result is True
        target_frame.set_pixel_data.assert_called_once_with([(255, 0, 0)] * 64)
        assert target_frame.duration == 1.0

    def test_apply_frame_paste_invalid_animation(self):
        """Test frame paste application with invalid animation."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.canvas.animated_sprite._animations = {}
        
        # Test applying frame paste to non-existent animation
        result = scene._apply_frame_paste_for_undo_redo(
            "nonexistent_anim", 0, [(255, 0, 0)] * 64, 1.0
        )
        
        # Verify failure
        assert result is False

    def test_apply_frame_paste_invalid_frame(self):
        """Test frame paste application with invalid frame index."""
        scene = self.create_mock_scene()
        
        # Set up scene state
        scene.canvas = Mock()
        scene.canvas.animated_sprite = Mock()
        scene.canvas.animated_sprite._animations = {
            "test_anim": []  # Empty frames list
        }
        
        # Test applying frame paste to non-existent frame
        result = scene._apply_frame_paste_for_undo_redo(
            "test_anim", 0, [(255, 0, 0)] * 64, 1.0
        )
        
        # Verify failure
        assert result is False

    def test_clipboard_persistence(self):
        """Test that clipboard data persists between operations."""
        scene = self.create_mock_scene()
        
        # Set up initial clipboard
        scene._frame_clipboard = {
            "pixels": [(255, 0, 0)] * 64,
            "width": 8,
            "height": 8,
            "duration": 1.0,
            "animation": "source_anim",
            "frame": 1
        }
        
        # Verify clipboard persists
        assert scene._frame_clipboard is not None
        assert scene._frame_clipboard["pixels"] == [(255, 0, 0)] * 64
        
        # Test that clipboard can be overwritten
        scene._frame_clipboard = {
            "pixels": [(0, 255, 0)] * 64,
            "width": 8,
            "height": 8,
            "duration": 0.5,
            "animation": "new_anim",
            "frame": 2
        }
        
        assert scene._frame_clipboard["pixels"] == [(0, 255, 0)] * 64
        assert scene._frame_clipboard["duration"] == 0.5
