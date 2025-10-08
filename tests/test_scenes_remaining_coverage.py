"""Comprehensive tests for remaining Scenes module coverage.

This module targets the remaining missing lines to achieve 100% coverage.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesRemainingCoverage(unittest.TestCase):
    """Comprehensive tests for remaining Scenes functionality to achieve 100% coverage."""

    def setUp(self):
        """Set up test fixtures using centralized MockFactory."""
        # Use the centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_scene_manager_start_method_terminate_return(self):
        """Test SceneManager start method terminate return (lines 147-148)."""
        scene_manager = SceneManager()
        scene_manager.active_scene = None  # No active scene to exit immediately
        scene_manager.quit_requested = False
        
        with patch.object(scene_manager, "terminate") as mock_terminate:
            mock_terminate.return_value = "terminated"
            
            result = scene_manager.start()
            
            # Should return the result of terminate
            self.assertEqual(result, "terminated")

    def test_scene_manager_handle_event_quit_event(self):
        """Test SceneManager handle_event with quit event (lines 281-283)."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        # Create a quit event
        mock_event = Mock()
        mock_event.type = 256  # pygame.QUIT
        
        with patch.object(scene_manager, "quit") as mock_quit:
            scene_manager.handle_event(mock_event)
            
            # Should call quit
            mock_quit.assert_called_once()

    def test_scene_manager_handle_event_non_quit_event(self):
        """Test SceneManager handle_event with non-quit event (lines 329, 333, 347)."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        # Create a non-quit event
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(scene_manager, "quit") as mock_quit:
            scene_manager.handle_event(mock_event)
            
            # Should not call quit
            mock_quit.assert_not_called()

    def test_scene_manager_handle_event_key_down_event(self):
        """Test SceneManager handle_event with key down event (lines 356-363)."""
        scene_manager = SceneManager()
        scene_manager.active_scene = Mock()
        
        # Create a key down event
        mock_event = Mock()
        mock_event.type = 2  # pygame.KEYDOWN
        
        with patch.object(scene_manager.active_scene, "on_key_down_event") as mock_key_down:
            scene_manager.handle_event(mock_event)
            
            # Should call on_key_down_event
            mock_key_down.assert_called_once_with(mock_event)

    def test_scene_manager_get_focused_sprites_property(self):
        """Test SceneManager _get_focused_sprites method (line 501)."""
        scene_manager = SceneManager()
        
        # Create mock sprites
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

    def test_scene_key_up_event_quit_keys(self):
        """Test Scene on_key_up_event with quit keys (lines 1062-1065)."""
        scene = Scene()
        scene.all_sprites = []  # No focused sprites
        
        # Create a quit key event
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        with patch("pygame.event.post") as mock_post, \
             patch.object(scene, "log") as mock_log:
            
            scene.on_key_up_event(mock_event)
            
            # Should post quit event and log
            mock_post.assert_called_once()
            mock_log.info.assert_called_with("Quit requested")

    def test_scene_key_up_event_escape_key(self):
        """Test Scene on_key_up_event with escape key (lines 1062-1065)."""
        scene = Scene()
        scene.all_sprites = []  # No focused sprites
        
        # Create an escape key event
        mock_event = Mock()
        mock_event.key = 27  # pygame.K_ESCAPE
        
        with patch("pygame.event.post") as mock_post, \
             patch.object(scene, "log") as mock_log:
            
            scene.on_key_up_event(mock_event)
            
            # Should post quit event and log
            mock_post.assert_called_once()
            mock_log.info.assert_called_with("Quit requested")

    def test_scene_key_up_event_with_focused_sprites(self):
        """Test Scene on_key_up_event with focused sprites (lines 1062-1065)."""
        scene = Scene()
        
        # Create focused sprites
        focused_sprite = Mock()
        focused_sprite.active = True
        scene.all_sprites = [focused_sprite]
        
        # Create a quit key event
        mock_event = Mock()
        mock_event.key = 113  # pygame.K_q
        
        with patch("pygame.event.post") as mock_post, \
             patch.object(scene, "log") as mock_log:
            
            scene.on_key_up_event(mock_event)
            
            # Should NOT post quit event when sprites are focused
            mock_post.assert_not_called()
            mock_log.info.assert_not_called()

    def test_scene_mouse_button_down_event(self):
        """Test Scene on_mouse_button_down_event method (lines 1119-1133)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
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

    def test_scene_left_mouse_drag_event(self):
        """Test Scene on_left_mouse_drag_event method (lines 1203-1207)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite = Mock()
        mock_sprite.on_left_mouse_drag_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite])
        
        trigger = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_left_mouse_drag_event(mock_event, trigger)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handler was called
            mock_sprite.on_left_mouse_drag_event.assert_called_once_with(mock_event, trigger)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_left_mouse_drop_event(self):
        """Test Scene on_left_mouse_drop_event method (lines 1220-1224)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_left_mouse_drop_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_left_mouse_drop_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        trigger = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_left_mouse_drop_event(mock_event, trigger)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_left_mouse_drop_event.assert_called_once_with(mock_event, trigger)
            mock_sprite2.on_left_mouse_drop_event.assert_called_once_with(mock_event, trigger)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_middle_mouse_drag_event(self):
        """Test Scene on_middle_mouse_drag_event method (lines 1239-1243)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite = Mock()
        mock_sprite.on_middle_mouse_drag_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite])
        
        trigger = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_middle_mouse_drag_event(mock_event, trigger)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handler was called
            mock_sprite.on_middle_mouse_drag_event.assert_called_once_with(mock_event, trigger)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_middle_mouse_drop_event(self):
        """Test Scene on_middle_mouse_drop_event method (lines 1258-1262)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_middle_mouse_drop_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_middle_mouse_drop_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        trigger = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_middle_mouse_drop_event(mock_event, trigger)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_middle_mouse_drop_event.assert_called_once_with(mock_event, trigger)
            mock_sprite2.on_middle_mouse_drop_event.assert_called_once_with(mock_event, trigger)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_right_mouse_drag_event(self):
        """Test Scene on_right_mouse_drag_event method (lines 1275-1279)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite = Mock()
        mock_sprite.on_right_mouse_drag_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite])
        
        trigger = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_right_mouse_drag_event(mock_event, trigger)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handler was called
            mock_sprite.on_right_mouse_drag_event.assert_called_once_with(mock_event, trigger)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_right_mouse_drop_event(self):
        """Test Scene on_right_mouse_drop_event method (lines 1292-1296)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_right_mouse_drop_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_right_mouse_drop_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        trigger = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_right_mouse_drop_event(mock_event, trigger)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_right_mouse_drop_event.assert_called_once_with(mock_event, trigger)
            mock_sprite2.on_right_mouse_drop_event.assert_called_once_with(mock_event, trigger)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_mouse_motion_event(self):
        """Test Scene on_mouse_motion_event method (lines 1309-1314)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_mouse_motion_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_mouse_motion_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_mouse_motion_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_mouse_motion_event.assert_called_once_with(mock_event)
            mock_sprite2.on_mouse_motion_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_mouse_wheel_event(self):
        """Test Scene on_mouse_wheel_event method (lines 1327-1332)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_mouse_wheel_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_mouse_wheel_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_mouse_wheel_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_mouse_wheel_event.assert_called_once_with(mock_event)
            mock_sprite2.on_mouse_wheel_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_left_mouse_button_up_event(self):
        """Test Scene on_left_mouse_button_up_event method (lines 1345-1350)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
        # Create mock sprites
        mock_sprite1 = Mock()
        mock_sprite1.on_left_mouse_button_up_event = Mock()
        
        mock_sprite2 = Mock()
        mock_sprite2.on_left_mouse_button_up_event = Mock()
        
        # Mock the sprites_at_position method
        scene.sprites_at_position = Mock(return_value=[mock_sprite1, mock_sprite2])
        
        with patch.object(scene, "log") as mock_log:
            scene.on_left_mouse_button_up_event(mock_event)
            
            # Verify sprites_at_position was called
            scene.sprites_at_position.assert_called_once_with(pos=(100, 200))
            
            # Verify sprite event handlers were called
            mock_sprite1.on_left_mouse_button_up_event.assert_called_once_with(mock_event)
            mock_sprite2.on_left_mouse_button_up_event.assert_called_once_with(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_middle_mouse_button_up_event(self):
        """Test Scene on_middle_mouse_button_up_event method (lines 1367-1381)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
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

    def test_scene_right_mouse_button_up_event(self):
        """Test Scene on_right_mouse_button_up_event method (lines 1394-1399)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
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

    def test_scene_right_mouse_button_down_event(self):
        """Test Scene on_right_mouse_button_down_event method (lines 1412-1417)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.pos = (100, 200)
        
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

    def test_scene_text_input_event(self):
        """Test Scene on_text_input_event method (lines 1522, 1534, 1546)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.text = "Hello"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_text_input_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_down_event(self):
        """Test Scene on_touch_down_event method (lines 1598, 1611, 1624)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.touch = 1
        mock_event.pos = (100, 200)
        
        with patch.object(scene, "log") as mock_log:
            scene.on_touch_down_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_motion_event(self):
        """Test Scene on_touch_motion_event method (lines 1598, 1611, 1624)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.touch = 1
        mock_event.pos = (100, 200)
        
        with patch.object(scene, "log") as mock_log:
            scene.on_touch_motion_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_up_event(self):
        """Test Scene on_touch_up_event method (lines 1598, 1611, 1624)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.touch = 1
        mock_event.pos = (100, 200)
        
        with patch.object(scene, "log") as mock_log:
            scene.on_touch_up_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_resized_event(self):
        """Test Scene on_window_resized_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.size = (800, 600)
        mock_event.w = 800
        mock_event.h = 600
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_resized_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_restored_event(self):
        """Test Scene on_window_restored_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_restored_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_gained_event(self):
        """Test Scene on_window_focus_gained_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_gained_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_lost_event(self):
        """Test Scene on_window_focus_lost_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_lost_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_added_event(self):
        """Test Scene on_audio_device_added_event method (lines 1926)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = "audio_device"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_added_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_removed_event(self):
        """Test Scene on_audio_device_removed_event method (lines 1926)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = "audio_device"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_removed_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()


if __name__ == "__main__":
    unittest.main()
