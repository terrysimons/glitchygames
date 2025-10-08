"""Enhanced tests for Scenes module using comprehensive pygame mocking.

This module uses the enhanced MockFactory to target the remaining edge cases.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesEnhancedPygame(unittest.TestCase):
    """Enhanced tests for Scenes functionality using comprehensive pygame mocking."""

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

    def test_scene_manager_getattr_fallback_to_game_engine_enhanced(self):
        """Test SceneManager __getattr__ fallback to game engine with enhanced mocking."""
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

    def test_scene_manager_handle_event_quit_event_enhanced(self):
        """Test SceneManager handle_event with quit event using enhanced mocking."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        # Create a quit event with proper pygame constant
        mock_event = Mock()
        mock_event.type = 256  # pygame.QUIT
        
        with patch.object(scene_manager, "quit") as mock_quit:
            scene_manager.handle_event(mock_event)
            
            # Should call quit
            mock_quit.assert_called_once()

    def test_scene_manager_handle_event_key_down_enhanced(self):
        """Test SceneManager handle_event with key down event using enhanced mocking."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        # Create a key down event with proper pygame constant
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(scene_manager.active_scene, "on_key_down_event") as mock_key_down:
            scene_manager.handle_event(mock_event)
            
            # Should call on_key_down_event
            mock_key_down.assert_called_once_with(mock_event)

    def test_scene_key_up_event_quit_keys_enhanced(self):
        """Test Scene on_key_up_event with quit keys using enhanced pygame constants."""
        scene = Scene()
        scene.all_sprites = []  # No focused sprites
        
        # Create a quit key event with proper pygame constant
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        with patch("pygame.event.post") as mock_post, \
             patch.object(scene, "log") as mock_log:
            
            scene.on_key_up_event(mock_event)
            
            # Should post quit event and log
            mock_post.assert_called_once()
            mock_log.info.assert_called_with("Quit requested")

    def test_scene_key_up_event_escape_key_enhanced(self):
        """Test Scene on_key_up_event with escape key using enhanced pygame constants."""
        scene = Scene()
        scene.all_sprites = []  # No focused sprites
        
        # Create an escape key event with proper pygame constant
        mock_event = Mock()
        mock_event.key = 27  # pygame.K_ESCAPE
        
        with patch("pygame.event.post") as mock_post, \
             patch.object(scene, "log") as mock_log:
            
            scene.on_key_up_event(mock_event)
            
            # Should post quit event and log
            mock_post.assert_called_once()
            mock_log.info.assert_called_with("Quit requested")

    def test_scene_mouse_button_down_event_enhanced(self):
        """Test Scene on_mouse_button_down_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.pos = (100, 200)
        mock_event.type = 5  # pygame.MOUSEBUTTONDOWN
        
        # Create mock sprites
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

    def test_scene_middle_mouse_button_up_event_enhanced(self):
        """Test Scene on_middle_mouse_button_up_event with enhanced pygame constants."""
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

    def test_scene_right_mouse_button_up_event_enhanced(self):
        """Test Scene on_right_mouse_button_up_event with enhanced pygame constants."""
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

    def test_scene_right_mouse_button_down_event_enhanced(self):
        """Test Scene on_right_mouse_button_down_event with enhanced pygame constants."""
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

    def test_scene_text_input_event_enhanced(self):
        """Test Scene on_text_input_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.text = "Hello"
        mock_event.type = 771  # pygame.TEXTINPUT
        
        with patch.object(scene, "log") as mock_log:
            scene.on_text_input_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_down_event_enhanced(self):
        """Test Scene on_touch_down_event with enhanced pygame constants."""
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

    def test_scene_touch_motion_event_enhanced(self):
        """Test Scene on_touch_motion_event with enhanced pygame constants."""
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

    def test_scene_touch_up_event_enhanced(self):
        """Test Scene on_touch_up_event with enhanced pygame constants."""
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

    def test_scene_window_resized_event_enhanced(self):
        """Test Scene on_window_resized_event with enhanced pygame constants."""
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

    def test_scene_window_restored_event_enhanced(self):
        """Test Scene on_window_restored_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.type = 32769  # pygame.WINDOWRESTORED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_restored_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_gained_event_enhanced(self):
        """Test Scene on_window_focus_gained_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.type = 32770  # pygame.WINDOWFOCUSGAINED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_gained_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_lost_event_enhanced(self):
        """Test Scene on_window_focus_lost_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.type = 32771  # pygame.WINDOWFOCUSLOST
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_lost_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_added_event_enhanced(self):
        """Test Scene on_audio_device_added_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.device = "audio_device"
        mock_event.type = 32784  # pygame.AUDIODEVICEADDED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_added_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_removed_event_enhanced(self):
        """Test Scene on_audio_device_removed_event with enhanced pygame constants."""
        scene = Scene()
        
        # Create mock event with proper pygame constants
        mock_event = Mock()
        mock_event.device = "audio_device"
        mock_event.type = 32785  # pygame.AUDIODEVICEREMOVED
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_removed_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_manager_fps_event_posting_enhanced(self):
        """Test SceneManager FPS event posting with enhanced pygame constants."""
        scene_manager = SceneManager()
        scene_manager.OPTIONS = {"fps_refresh_rate": 1000}
        scene_manager.clock = Mock()
        scene_manager.clock.get_fps.return_value = 60.0
        
        with patch("pygame.event.post") as mock_post, \
             patch("pygame.event.Event") as mock_event_class:
            
            # Mock the event class to return a mock event
            mock_event = Mock()
            mock_event_class.return_value = mock_event
            
            scene_manager._post_fps_event()
            
            # Verify event was posted
            mock_post.assert_called_once()
            mock_event_class.assert_called_once()

    def test_scene_manager_should_post_fps_event_enhanced(self):
        """Test SceneManager _should_post_fps_event with enhanced timing."""
        scene_manager = SceneManager()
        scene_manager.OPTIONS = {"fps_refresh_rate": 1000}
        
        # Test with timing that should trigger FPS event
        current_time = 1.0
        previous_fps_time = 0.0
        
        result = scene_manager._should_post_fps_event(current_time, previous_fps_time)
        
        # Should return True since 1000ms have passed
        self.assertTrue(result)

    def test_scene_manager_process_events_enhanced(self):
        """Test SceneManager _process_events with enhanced game engine mocking."""
        scene_manager = SceneManager()
        scene_manager.game_engine = Mock()
        
        scene_manager._process_events()
        
        # Verify game engine process_events was called
        scene_manager.game_engine.process_events.assert_called_once()


if __name__ == "__main__":
    unittest.main()
