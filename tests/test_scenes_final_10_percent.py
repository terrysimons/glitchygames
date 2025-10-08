"""Final tests for the remaining 10% of Scenes module coverage.

This module targets the final 48 missing lines to achieve 100% coverage.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.scenes import Scene, SceneManager

from test_mock_factory import MockFactory


class TestScenesFinal10Percent(unittest.TestCase):
    """Final tests for the remaining 10% of Scenes functionality to achieve 100% coverage."""

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

    def test_scene_manager_handle_event_quit_event_lines_281_283(self):
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

    def test_scene_manager_handle_event_non_quit_event_lines_329_333_347(self):
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

    def test_scene_manager_handle_event_key_down_event_lines_356_363(self):
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

    def test_scene_manager_get_focused_sprites_property_line_501(self):
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

    def test_scene_key_up_event_quit_keys_lines_1062_1065(self):
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

    def test_scene_mouse_button_down_event_lines_1119_1133(self):
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

    def test_scene_middle_mouse_button_up_event_lines_1367_1381(self):
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

    def test_scene_right_mouse_button_up_event_lines_1394_1399(self):
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

    def test_scene_right_mouse_button_down_event_lines_1416_1417(self):
        """Test Scene on_right_mouse_button_down_event method (lines 1416-1417)."""
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

    def test_scene_text_input_event_lines_1522_1534(self):
        """Test Scene on_text_input_event method (lines 1522, 1534)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.text = "Hello"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_text_input_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_touch_down_event_lines_1598_1611_1624(self):
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

    def test_scene_touch_motion_event_lines_1598_1611_1624(self):
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

    def test_scene_touch_up_event_lines_1598_1611_1624(self):
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

    def test_scene_window_resized_event_lines_1845_1858_1859(self):
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

    def test_scene_window_restored_event_lines_1845_1858_1859(self):
        """Test Scene on_window_restored_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_restored_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_gained_event_lines_1845_1858_1859(self):
        """Test Scene on_window_focus_gained_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_gained_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_window_focus_lost_event_lines_1845_1858_1859(self):
        """Test Scene on_window_focus_lost_event method (lines 1845, 1858-1859)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        
        with patch.object(scene, "log") as mock_log:
            scene.on_window_focus_lost_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_added_event_line_1926(self):
        """Test Scene on_audio_device_added_event method (line 1926)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = "audio_device"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_added_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_audio_device_removed_event_line_1926(self):
        """Test Scene on_audio_device_removed_event method (line 1926)."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = "audio_device"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_audio_device_removed_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_controller_axis_motion_event(self):
        """Test Scene on_controller_axis_motion_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.controller = 0
        mock_event.axis = 0
        mock_event.value = 0.5
        
        with patch.object(scene, "log") as mock_log:
            scene.on_controller_axis_motion_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_controller_button_down_event(self):
        """Test Scene on_controller_button_down_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.controller = 0
        mock_event.button = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_controller_button_down_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_controller_button_up_event(self):
        """Test Scene on_controller_button_up_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.controller = 0
        mock_event.button = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_controller_button_up_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_controller_device_added_event(self):
        """Test Scene on_controller_device_added_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_controller_device_added_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_controller_device_removed_event(self):
        """Test Scene on_controller_device_removed_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_controller_device_removed_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_controller_device_remapped_event(self):
        """Test Scene on_controller_device_remapped_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_controller_device_remapped_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_axis_motion_event(self):
        """Test Scene on_joystick_axis_motion_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.joy = 0
        mock_event.axis = 0
        mock_event.value = 0.5
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_axis_motion_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_ball_motion_event(self):
        """Test Scene on_joystick_ball_motion_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.joy = 0
        mock_event.ball = 0
        mock_event.rel = (1, 1)
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_ball_motion_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_button_down_event(self):
        """Test Scene on_joystick_button_down_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.joy = 0
        mock_event.button = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_button_down_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_button_up_event(self):
        """Test Scene on_joystick_button_up_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.joy = 0
        mock_event.button = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_button_up_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_hat_motion_event(self):
        """Test Scene on_joystick_hat_motion_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.joy = 0
        mock_event.hat = 0
        mock_event.value = (0, 0)
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_hat_motion_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_device_added_event(self):
        """Test Scene on_joystick_device_added_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_device_added_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_joystick_device_removed_event(self):
        """Test Scene on_joystick_device_removed_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = 0
        
        with patch.object(scene, "log") as mock_log:
            scene.on_joystick_device_removed_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_drop_begin_event(self):
        """Test Scene on_drop_begin_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.file = "test.txt"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_drop_begin_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_drop_complete_event(self):
        """Test Scene on_drop_complete_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.file = "test.txt"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_drop_complete_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_drop_file_event(self):
        """Test Scene on_drop_file_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.file = "test.txt"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_drop_file_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_drop_text_event(self):
        """Test Scene on_drop_text_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.text = "Hello World"
        
        with patch.object(scene, "log") as mock_log:
            scene.on_drop_text_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()

    def test_scene_midi_in_event(self):
        """Test Scene on_midi_in_event method."""
        scene = Scene()
        
        # Create mock event
        mock_event = Mock()
        mock_event.device = 0
        mock_event.status = 0x90
        mock_event.data1 = 60
        mock_event.data2 = 100
        
        with patch.object(scene, "log") as mock_log:
            scene.on_midi_in_event(mock_event)
            
            # Verify logging
            mock_log.debug.assert_called()


if __name__ == "__main__":
    unittest.main()
