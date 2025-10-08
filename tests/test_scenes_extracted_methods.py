"""Tests for extracted methods in Scenes module to achieve 100% coverage.

This module tests the newly extracted methods to cover the remaining edge cases.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesExtractedMethods(unittest.TestCase):
    """Tests for extracted methods in Scenes functionality to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures using enhanced MockFactory."""
        # Use the enhanced centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_handle_quit_key_press(self):
        """Test Scene _handle_quit_key_press method (lines 545-548)."""
        scene = Scene()
        
        with patch("pygame.event.post") as mock_post, \
             patch("pygame.event.Event") as mock_event_class, \
             patch.object(scene, "log") as mock_log:
            
            # Mock the event class to return a mock event
            mock_event = Mock()
            mock_event_class.return_value = mock_event
            
            scene._handle_quit_key_press()
            
            # Verify logging and event posting
            mock_log.info.assert_called_with("Quit requested")
            mock_post.assert_called_once()
            mock_event_class.assert_called_once()

    def test_scene_manager_getattr_fallback_to_game_engine_extracted(self):
        """Test SceneManager __getattr__ fallback to game engine (lines 281-283)."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        scene_manager.game_engine = Mock()
        
        # Mock the event method on game engine (not on active scene)
        mock_event_handler = Mock()
        scene_manager.game_engine.on_test_event = mock_event_handler
        
        # Remove the method from active scene to trigger fallback
        del scene_manager.active_scene.on_test_event
        
        # Test event method proxying with fallback
        result = scene_manager.__getattr__("on_test_event")
        
        self.assertEqual(result, mock_event_handler)

    def test_scene_manager_process_events_extracted(self):
        """Test SceneManager _process_events (line 347)."""
        scene_manager = SceneManager()
        scene_manager.game_engine = Mock()
        
        scene_manager._process_events()
        
        # Verify game engine process_events was called
        scene_manager.game_engine.process_events.assert_called_once()

    def test_scene_manager_handle_event_key_down_extracted(self):
        """Test SceneManager handle_event with key down event (lines 356-363)."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        # Create a key down event with proper pygame constant
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(scene_manager.active_scene, "on_key_down_event") as mock_key_down:
            scene_manager.handle_event(mock_event)
            
            # Should call on_key_down_event
            mock_key_down.assert_called_once_with(mock_event)

    def test_scene_manager_get_focused_sprites_extracted(self):
        """Test SceneManager _get_focused_sprites (line 501)."""
        scene_manager = SceneManager()
        
        # Create mock sprites with complex state
        focused_sprite1 = Mock()
        focused_sprite1.active = True
        
        focused_sprite2 = Mock()
        focused_sprite2.active = True
        
        inactive_sprite = Mock()
        inactive_sprite.active = False
        
        # Mock the all_sprites property
        scene_manager.all_sprites = [focused_sprite1, inactive_sprite, focused_sprite2]
        
        result = scene_manager._get_focused_sprites()
        
        self.assertEqual(len(result), 2)
        self.assertIn(focused_sprite1, result)
        self.assertIn(focused_sprite2, result)
        self.assertNotIn(inactive_sprite, result)

    def test_scene_key_up_event_quit_keys_extracted(self):
        """Test Scene on_key_up_event with quit keys using extracted method (lines 1062-1065)."""
        scene = Scene()
        scene.all_sprites = []  # No focused sprites
        
        # Create a quit key event with proper pygame constant
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        with patch.object(scene, "_handle_quit_key_press") as mock_handle_quit:
            scene.on_key_up_event(mock_event)
            
            # Should call the extracted method
            mock_handle_quit.assert_called_once()

    def test_scene_key_up_event_escape_key_extracted(self):
        """Test Scene on_key_up_event with escape key using extracted method (lines 1062-1065)."""
        scene = Scene()
        scene.all_sprites = []  # No focused sprites
        
        # Create an escape key event with proper pygame constant
        mock_event = Mock()
        mock_event.key = 27  # pygame.K_ESCAPE
        
        with patch.object(scene, "_handle_quit_key_press") as mock_handle_quit:
            scene.on_key_up_event(mock_event)
            
            # Should call the extracted method
            mock_handle_quit.assert_called_once()

    def test_scene_key_up_event_with_focused_sprites_extracted(self):
        """Test Scene on_key_up_event with focused sprites using extracted method (lines 1062-1065)."""
        scene = Scene()
        
        # Create focused sprites
        focused_sprite = Mock()
        focused_sprite.active = True
        scene.all_sprites = [focused_sprite]
        
        # Create a quit key event
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        with patch.object(scene, "_handle_quit_key_press") as mock_handle_quit:
            scene.on_key_up_event(mock_event)
            
            # Should NOT call the extracted method when sprites are focused
            mock_handle_quit.assert_not_called()

    def test_scene_mouse_button_down_event_extracted(self):
        """Test Scene on_mouse_button_down_event using extracted methods (lines 1119-1133)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.pos = (100, 200)
        mock_event.type = 5  # pygame.MOUSEBUTTONDOWN
        
        # Create mock sprites with complex focus states
        mock_sprite1 = Mock()
        mock_sprite1.focusable = True
        mock_sprite1.on_mouse_button_down_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.focusable = False
        mock_sprite2.on_mouse_button_down_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_mouse_button_down_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_mouse_button_down_event.assert_called_once_with(mock_event)
            mock_sprite2.on_mouse_button_down_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_middle_mouse_button_up_event_extracted(self):
        """Test Scene on_middle_mouse_button_up_event using extracted methods (lines 1367-1381)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.pos = (100, 200)
        mock_event.type = 6  # pygame.MOUSEBUTTONUP
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_middle_mouse_button_up_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_middle_mouse_button_up_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_middle_mouse_button_up_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_middle_mouse_button_up_event.assert_called_once_with(mock_event)
            mock_sprite2.on_middle_mouse_button_up_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_right_mouse_button_up_event_extracted(self):
        """Test Scene on_right_mouse_button_up_event using extracted methods (lines 1394-1399)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.pos = (100, 200)
        mock_event.type = 6  # pygame.MOUSEBUTTONUP
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_right_mouse_button_up_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_right_mouse_button_up_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_right_mouse_button_up_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_right_mouse_button_up_event.assert_called_once_with(mock_event)
            mock_sprite2.on_right_mouse_button_up_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_right_mouse_button_down_event_extracted(self):
        """Test Scene on_right_mouse_button_down_event using extracted methods (lines 1416-1417)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.pos = (100, 200)
        mock_event.type = 5  # pygame.MOUSEBUTTONDOWN
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_right_mouse_button_down_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_right_mouse_button_down_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_right_mouse_button_down_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_right_mouse_button_down_event.assert_called_once_with(mock_event)
            mock_sprite2.on_right_mouse_button_down_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_text_input_event_extracted(self):
        """Test Scene on_text_input_event using extracted methods (lines 1522, 1534)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.text = "Hello"
        mock_event.type = 771  # pygame.TEXTINPUT
        
        with patch.object(scene, "log") as mock_log:
            scene.on_text_input_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_down_event_extracted(self):
        """Test Scene on_touch_down_event using extracted methods (lines 1598, 1611, 1624)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.touch = 1
        mock_event.pos = (100, 200)
        mock_event.type = 1024  # pygame.FINGERDOWN
        
        with patch.object(scene, "log") as mock_log:
            scene.on_touch_down_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_motion_event_extracted(self):
        """Test Scene on_touch_motion_event using extracted methods (lines 1598, 1611, 1624)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.touch = 1
        mock_event.pos = (100, 200)
        mock_event.type = 1026  # pygame.FINGERMOTION
        
        with patch.object(scene, "log") as mock_log:
            scene.on_touch_motion_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_up_event_extracted(self):
        """Test Scene on_touch_up_event using extracted methods (lines 1598, 1611, 1624)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.touch = 1
        mock_event.pos = (100, 200)
        mock_event.type = 1025  # pygame.FINGERUP
        
        with patch.object(scene, "log") as mock_log:
            scene.on_touch_up_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_resized_event_extracted(self):
        """Test Scene on_window_resized_event using extracted methods (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.size = (800, 600)
        mock_event.w = 800
        mock_event.h = 600
        mock_event.type = 32768  # pygame.WINDOWRESIZED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_resized_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_restored_event_extracted(self):
        """Test Scene on_window_restored_event using extracted methods (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.type = 32769  # pygame.WINDOWRESTORED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_restored_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_gained_event_extracted(self):
        """Test Scene on_window_focus_gained_event using extracted methods (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.type = 32770  # pygame.WINDOWFOCUSGAINED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_gained_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_lost_event_extracted(self):
        """Test Scene on_window_focus_lost_event using extracted methods (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.type = 32771  # pygame.WINDOWFOCUSLOST
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_lost_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_added_event_extracted(self):
        """Test Scene on_audio_device_added_event using extracted methods (line 1926)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.device = "audio_device"
        mock_event.type = 32784  # pygame.AUDIODEVICEADDED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_added_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_removed_event_extracted(self):
        """Test Scene on_audio_device_removed_event using extracted methods (line 1926)."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.device = "audio_device"
        mock_event.type = 32785  # pygame.AUDIODEVICEREMOVED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_removed_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()


if __name__ == "__main__":
    unittest.main()
