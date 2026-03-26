"""Tests for Scene class functionality."""

import sys
from pathlib import Path

import pygame
import pytest

from glitchygames.color import BLUE, RED
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.scene import JITTER_SAMPLE_BUFFER_MAX_SIZE

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestScene:
    """Test Scene class functionality."""

    def test_scene_initialization_default(self, mock_pygame_patches, mocker):
        """Test Scene initialization with default parameters."""
        scene = Scene()

        # Check basic attributes
        assert scene.target_fps == 0
        assert scene.fps == 0
        assert scene.dt == 0
        assert scene.dt_timer == 0
        assert scene.dirty == 1
        assert scene.options == {'debug_events': False, 'no_unhandled_events': False}
        assert scene.name is type(scene)
        assert scene._background_color == (0, 0, 0, 0)  # BLACK color
        assert scene.next_scene == scene
        assert scene.rects is None
        assert scene.screen is not None
        assert scene.screen_width > 0
        assert scene.screen_height > 0
        assert scene.all_sprites is not None
        assert scene.background is not None
        assert scene.image is not None
        assert scene.rect is not None

    def test_scene_initialization_with_options(self, mock_pygame_patches, mocker):
        """Test Scene initialization with options."""
        options = {'test': 'value'}
        scene = Scene(options=options)

        assert scene.options == options

    def test_scene_initialization_with_groups(self, mock_pygame_patches, mocker):
        """Test Scene initialization with sprite groups."""
        mock_groups = mocker.Mock()
        scene = Scene(groups=mock_groups)

        assert scene.all_sprites == mock_groups

    def test_scene_screenshot_property(self, mock_pygame_patches, mocker):
        """Test Scene screenshot property."""
        scene = Scene()

        # Test screenshot property
        screenshot = scene.screenshot
        assert screenshot is not None
        assert hasattr(screenshot, 'get_size')

    def test_scene_background_color_property(self, mock_pygame_patches, mocker):
        """Test Scene background_color property."""
        scene = Scene()

        # Test getting background color
        assert scene.background_color is not None

        # Test setting background color (RGB gets normalized to RGBA with alpha=0)
        scene.background_color = RED
        assert scene.background_color == (*RED, 0)

    def test_scene_background_color_setter(self, mock_pygame_patches, mocker):
        """Test Scene background_color setter."""
        scene = Scene()

        # Test setting background color (RGB gets normalized to RGBA with alpha=0)
        scene.background_color = BLUE
        assert scene.background_color == (*BLUE, 0)

    def test_scene_setup_method(self, mock_pygame_patches, mocker):
        """Test Scene setup method."""
        scene = Scene()

        # Test setup method (should not raise exceptions)
        scene.setup()

    def test_scene_update_method(self, mock_pygame_patches, mocker):
        """Test Scene update method."""
        scene = Scene()

        # Test update method (should not raise exceptions)
        scene.update()

    def test_scene_render_method(self, mock_pygame_patches, mocker):
        """Test Scene render method."""
        scene = Scene()
        mock_screen = mocker.Mock()

        # Mock the sprite group methods to prevent hanging
        # The centralized mocks should handle pygame.display.get_surface() properly
        scene.all_sprites.clear = mocker.Mock()
        scene.all_sprites.draw = mocker.Mock(return_value=[])

        # Test render method (should not raise exceptions)
        scene.render(mock_screen)

        # Verify the methods were called
        scene.all_sprites.clear.assert_called_once_with(mock_screen, scene.background)
        scene.all_sprites.draw.assert_called_once_with(mock_screen)

    def test_scene_cleanup_method(self, mock_pygame_patches, mocker):
        """Test Scene cleanup method."""
        scene = Scene()

        # Test cleanup method (should not raise exceptions)
        scene.cleanup()

    def test_scene_on_user_event(self, mock_pygame_patches, mocker):
        """Test Scene on_user_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test user event handling
        scene.on_user_event(mock_event)

    def test_scene_on_quit_event(self, mock_pygame_patches, mocker):
        """Test Scene on_quit_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test quit event handling
        scene.on_quit_event(mock_event)

    def test_scene_on_fps_event(self, mock_pygame_patches, mocker):
        """Test Scene on_fps_event method."""
        scene = Scene()
        mock_event = mocker.Mock()
        mock_event.fps = 60

        # Test FPS event handling
        scene.on_fps_event(mock_event)

    def test_scene_on_game_event(self, mock_pygame_patches, mocker):
        """Test Scene on_game_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test game event handling
        scene.on_game_event(mock_event)

    def test_scene_on_key_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_key_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test key down event handling
        scene.on_key_down_event(mock_event)

    def test_scene_on_key_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_key_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test key up event handling
        scene.on_key_up_event(mock_event)

    def test_scene_on_mouse_button_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_mouse_button_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()
        mock_event.pos = (100, 100)  # Provide proper position

        # Test mouse button down event handling
        scene.on_mouse_button_down_event(mock_event)

    def test_scene_on_mouse_button_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_mouse_button_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test mouse button up event handling
        scene.on_mouse_button_up_event(mock_event)

    def test_scene_on_mouse_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_mouse_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test mouse motion event handling
        scene.on_mouse_motion_event(mock_event)

    def test_scene_on_mouse_wheel_event(self, mock_pygame_patches, mocker):
        """Test Scene on_mouse_wheel_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test mouse wheel event handling
        scene.on_mouse_wheel_event(mock_event)

    def test_scene_on_joy_axis_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_axis_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick axis motion event handling
        scene.on_joy_axis_motion_event(mock_event)

    def test_scene_on_joy_button_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_button_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick button down event handling
        scene.on_joy_button_down_event(mock_event)

    def test_scene_on_joy_button_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_button_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick button up event handling
        scene.on_joy_button_up_event(mock_event)

    def test_scene_on_joy_hat_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_hat_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick hat motion event handling
        scene.on_joy_hat_motion_event(mock_event)

    def test_scene_on_joy_ball_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_ball_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick ball motion event handling
        scene.on_joy_ball_motion_event(mock_event)

    def test_scene_on_joy_device_added_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_device_added_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick device added event handling
        scene.on_joy_device_added_event(mock_event)

    def test_scene_on_joy_device_removed_event(self, mock_pygame_patches, mocker):
        """Test Scene on_joy_device_removed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test joystick device removed event handling
        scene.on_joy_device_removed_event(mock_event)

    def test_scene_on_controller_axis_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_axis_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller axis motion event handling
        scene.on_controller_axis_motion_event(mock_event)

    def test_scene_on_controller_button_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_button_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller button down event handling
        scene.on_controller_button_down_event(mock_event)

    def test_scene_on_controller_button_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_button_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller button up event handling
        scene.on_controller_button_up_event(mock_event)

    def test_scene_on_controller_device_added_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_device_added_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller device added event handling
        scene.on_controller_device_added_event(mock_event)

    def test_scene_on_controller_device_removed_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_device_removed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller device removed event handling
        scene.on_controller_device_removed_event(mock_event)

    def test_scene_on_controller_device_remapped_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_device_remapped_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller device remapped event handling
        scene.on_controller_device_remapped_event(mock_event)

    def test_scene_on_controller_touchpad_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_touchpad_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller touchpad down event handling
        scene.on_controller_touchpad_down_event(mock_event)

    def test_scene_on_controller_touchpad_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_touchpad_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller touchpad motion event handling
        scene.on_controller_touchpad_motion_event(mock_event)

    def test_scene_on_controller_touchpad_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_controller_touchpad_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test controller touchpad up event handling
        scene.on_controller_touchpad_up_event(mock_event)

    def test_scene_on_audio_device_added_event(self, mock_pygame_patches, mocker):
        """Test Scene on_audio_device_added_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test audio device added event handling
        scene.on_audio_device_added_event(mock_event)

    def test_scene_on_audio_device_removed_event(self, mock_pygame_patches, mocker):
        """Test Scene on_audio_device_removed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test audio device removed event handling
        scene.on_audio_device_removed_event(mock_event)

    def test_scene_on_window_close_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_close_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window close event handling
        scene.on_window_close_event(mock_event)

    def test_scene_on_window_enter_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_enter_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window enter event handling
        scene.on_window_enter_event(mock_event)

    def test_scene_on_window_leave_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_leave_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window leave event handling
        scene.on_window_leave_event(mock_event)

    def test_scene_on_window_focus_gained_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_focus_gained_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window focus gained event handling
        scene.on_window_focus_gained_event(mock_event)

    def test_scene_on_window_focus_lost_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_focus_lost_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window focus lost event handling
        scene.on_window_focus_lost_event(mock_event)

    def test_scene_on_window_resized_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_resized_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window resized event handling
        scene.on_window_resized_event(mock_event)

    def test_scene_on_window_moved_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_moved_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window moved event handling
        scene.on_window_moved_event(mock_event)

    def test_scene_on_window_minimized_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_minimized_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window minimized event handling
        scene.on_window_minimized_event(mock_event)

    def test_scene_on_window_maximized_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_maximized_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window maximized event handling
        scene.on_window_maximized_event(mock_event)

    def test_scene_on_window_restored_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_restored_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window restored event handling
        scene.on_window_restored_event(mock_event)

    def test_scene_on_window_shown_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_shown_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window shown event handling
        scene.on_window_shown_event(mock_event)

    def test_scene_on_window_hidden_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_hidden_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window hidden event handling
        scene.on_window_hidden_event(mock_event)

    def test_scene_on_window_exposed_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_exposed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window exposed event handling
        scene.on_window_exposed_event(mock_event)

    def test_scene_on_window_take_focus_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_take_focus_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window take focus event handling
        scene.on_window_take_focus_event(mock_event)

    def test_scene_on_window_size_changed_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_size_changed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window size changed event handling
        scene.on_window_size_changed_event(mock_event)

    def test_scene_on_window_hit_test_event(self, mock_pygame_patches, mocker):
        """Test Scene on_window_hit_test_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test window hit test event handling
        scene.on_window_hit_test_event(mock_event)

    def test_scene_on_touch_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_touch_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test touch down event handling
        scene.on_touch_down_event(mock_event)

    def test_scene_on_touch_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_touch_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test touch motion event handling
        scene.on_touch_motion_event(mock_event)

    def test_scene_on_touch_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_touch_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test touch up event handling
        scene.on_touch_up_event(mock_event)

    def test_scene_on_multi_touch_down_event(self, mock_pygame_patches, mocker):
        """Test Scene on_multi_touch_down_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test multi touch down event handling
        scene.on_multi_touch_down_event(mock_event)

    def test_scene_on_multi_touch_motion_event(self, mock_pygame_patches, mocker):
        """Test Scene on_multi_touch_motion_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test multi touch motion event handling
        scene.on_multi_touch_motion_event(mock_event)

    def test_scene_on_multi_touch_up_event(self, mock_pygame_patches, mocker):
        """Test Scene on_multi_touch_up_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test multi touch up event handling
        scene.on_multi_touch_up_event(mock_event)

    def test_scene_on_drop_begin_event(self, mock_pygame_patches, mocker):
        """Test Scene on_drop_begin_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop begin event handling
        scene.on_drop_begin_event(mock_event)

    def test_scene_on_drop_file_event(self, mock_pygame_patches, mocker):
        """Test Scene on_drop_file_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop file event handling
        scene.on_drop_file_event(mock_event)

    def test_scene_on_drop_text_event(self, mock_pygame_patches, mocker):
        """Test Scene on_drop_text_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop text event handling
        scene.on_drop_text_event(mock_event)

    def test_scene_on_drop_complete_event(self, mock_pygame_patches, mocker):
        """Test Scene on_drop_complete_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test drop complete event handling
        scene.on_drop_complete_event(mock_event)

    def test_scene_on_text_input_event(self, mock_pygame_patches, mocker):
        """Test Scene on_text_input_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test text input event handling
        scene.on_text_input_event(mock_event)

    def test_scene_on_text_editing_event(self, mock_pygame_patches, mocker):
        """Test Scene on_text_editing_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test text editing event handling
        scene.on_text_editing_event(mock_event)

    def test_scene_on_midi_in_event(self, mock_pygame_patches, mocker):
        """Test Scene on_midi_in_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test MIDI in event handling
        scene.on_midi_in_event(mock_event)

    def test_scene_on_midi_out_event(self, mock_pygame_patches, mocker):
        """Test Scene on_midi_out_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test MIDI out event handling
        scene.on_midi_out_event(mock_event)

    def test_scene_on_font_changed_event(self, mock_pygame_patches, mocker):
        """Test Scene on_font_changed_event method."""
        scene = Scene()
        mock_event = mocker.Mock()

        # Test font changed event handling
        scene.on_font_changed_event(mock_event)


class TestSceneDtTick:
    """Test Scene.dt_tick() method."""

    def test_dt_tick_updates_dt_and_timer(self, mock_pygame_patches):
        """Test dt_tick accumulates delta time."""
        scene = Scene()
        assert scene.dt == 0
        assert scene.dt_timer == 0

        scene.dt_tick(0.016)
        assert abs(scene.dt - 0.016) < 1e-9
        assert abs(scene.dt_timer - 0.016) < 1e-9

        scene.dt_tick(0.017)
        assert abs(scene.dt - 0.017) < 1e-9
        assert abs(scene.dt_timer - 0.033) < 0.001


class TestSceneCleanup:
    """Test Scene.cleanup() method."""

    def test_cleanup_runs_without_error(self, mock_pygame_patches):
        """Test cleanup() can be called without error."""
        scene = Scene()
        scene.cleanup()  # Base implementation is a no-op


class TestSceneLoadResources:
    """Test Scene.load_resources() method."""

    def test_load_resources_runs_without_error(self, mock_pygame_patches):
        """Test load_resources() can be called without error."""
        scene = Scene()
        scene.load_resources()  # Base implementation logs a debug message


class TestSceneSpritesAtPosition:
    """Test Scene.sprites_at_position() method."""

    def test_sprites_at_position_returns_list(self, mock_pygame_patches):
        """Test sprites_at_position returns a list."""
        scene = Scene()
        result = scene.sprites_at_position((100, 100))
        assert isinstance(result, list)

    def test_sprites_at_position_empty(self, mock_pygame_patches):
        """Test sprites_at_position returns empty list when no sprites."""
        scene = Scene()
        result = scene.sprites_at_position((100, 100))
        assert result == []


class TestSceneFocusManagement:
    """Test Scene focus management helper methods."""

    def test_get_collided_sprites(self, mock_pygame_patches):
        """Test _get_collided_sprites delegates to sprites_at_position."""
        scene = Scene()
        result = scene._get_collided_sprites((100, 100))
        assert isinstance(result, list)

    def test_get_focusable_sprites_empty(self, mock_pygame_patches):
        """Test _get_focusable_sprites with no focusable sprites."""
        scene = Scene()
        result = scene._get_focusable_sprites([])
        assert result == []

    def test_get_focusable_sprites_filters(self, mock_pygame_patches, mocker):
        """Test _get_focusable_sprites filters correctly."""
        scene = Scene()

        focusable = mocker.Mock()
        focusable.focusable = True

        non_focusable = mocker.Mock(spec=[])  # No focusable attribute

        result = scene._get_focusable_sprites([focusable, non_focusable])
        assert len(result) == 1
        assert result[0] == focusable

    def test_get_focused_sprites_empty(self, mock_pygame_patches):
        """Test _get_focused_sprites with no focused sprites."""
        scene = Scene()
        result = scene._get_focused_sprites()
        assert result == []

    def test_has_focusable_sprites_false(self, mock_pygame_patches):
        """Test _has_focusable_sprites returns False for empty list."""
        scene = Scene()
        assert scene._has_focusable_sprites([]) is False

    def test_has_focusable_sprites_true(self, mock_pygame_patches, mocker):
        """Test _has_focusable_sprites returns True when focusable present."""
        scene = Scene()
        sprite = mocker.Mock()
        sprite.focusable = True
        assert scene._has_focusable_sprites([sprite]) is True

    def test_unfocus_sprites(self, mock_pygame_patches, mocker):
        """Test _unfocus_sprites deactivates sprites."""
        scene = Scene()

        sprite = mocker.Mock()
        sprite.active = True
        sprite.on_focus_lost = mocker.Mock()

        scene._unfocus_sprites([sprite])

        assert sprite.active is False
        sprite.on_focus_lost.assert_called_once()

    def test_unfocus_sprites_without_on_focus_lost(self, mock_pygame_patches, mocker):
        """Test _unfocus_sprites with sprite that lacks on_focus_lost."""
        scene = Scene()

        sprite = mocker.Mock(spec=['active'])
        sprite.active = True

        scene._unfocus_sprites([sprite])
        assert sprite.active is False

    def test_handle_focus_management_unfocuses_when_no_focusable(self, mock_pygame_patches, mocker):
        """Test _handle_focus_management unfocuses when no focusable sprites."""
        scene = Scene()

        # Add a mock focused sprite to all_sprites
        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_focus_lost = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        # Click on non-focusable sprites
        scene._handle_focus_management([])

        assert focused_sprite.active is False


class TestSceneHandleQuitKeyPress:
    """Test Scene._handle_quit_key_press() method."""

    def test_handle_quit_key_press_posts_quit_event(self, mock_pygame_patches, mocker):
        """Test quit key press posts a QUIT event."""
        scene = Scene()

        mock_post = mocker.patch('pygame.event.post')
        scene._handle_quit_key_press()
        mock_post.assert_called_once()


class TestSceneKeyUpEvent:
    """Test Scene.on_key_up_event() method."""

    def test_key_up_q_quits_when_no_focused_sprites(self, mock_pygame_patches, mocker):
        """Test 'q' key up triggers quit when no sprites are focused."""
        scene = Scene()
        mock_post = mocker.patch('pygame.event.post')

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_up_event(event)

        mock_post.assert_called_once()

    def test_key_up_escape_quits_when_no_focused_sprites(self, mock_pygame_patches, mocker):
        """Test escape key up triggers quit when no sprites are focused."""
        scene = Scene()
        mock_post = mocker.patch('pygame.event.post')

        event = mocker.Mock()
        event.key = pygame.K_ESCAPE

        scene.on_key_up_event(event)

        mock_post.assert_called_once()

    def test_key_up_does_not_quit_when_sprites_focused(self, mock_pygame_patches, mocker):
        """Test key up does not quit when sprites are focused."""
        scene = Scene()
        mock_post = mocker.patch('pygame.event.post')

        # Add a focused sprite
        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_up_event(event)

        mock_post.assert_not_called()


class TestSceneKeyDownEvent:
    """Test Scene.on_key_down_event() method."""

    def test_key_down_q_sets_quit_requested(self, mock_pygame_patches, mocker):
        """Test 'q' key down sets quit_requested."""
        scene = Scene()

        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)

        assert scene.quit_requested is True

    def test_key_down_handled_by_focused_sprite(self, mock_pygame_patches, mocker):
        """Test key down is handled by focused sprite first."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_key_down_event = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)

        focused_sprite.on_key_down_event.assert_called_once_with(event)


class TestSceneEventHandlers:
    """Test various Scene event handler stubs."""

    def test_on_audio_device_added_event(self, mock_pygame_patches, mocker):
        """Test audio device added event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_audio_device_added_event(event)  # Should not raise

    def test_on_audio_device_removed_event(self, mock_pygame_patches, mocker):
        """Test audio device removed event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_audio_device_removed_event(event)

    def test_on_controller_button_down_event(self, mock_pygame_patches, mocker):
        """Test controller button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_controller_button_down_event(event)

    def test_on_controller_button_up_event(self, mock_pygame_patches, mocker):
        """Test controller button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_controller_button_up_event(event)

    def test_on_joy_button_down_event(self, mock_pygame_patches, mocker):
        """Test joy button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_joy_button_down_event(event)

    def test_on_joy_button_up_event(self, mock_pygame_patches, mocker):
        """Test joy button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_joy_button_up_event(event)

    def test_on_menu_item_event(self, mock_pygame_patches, mocker):
        """Test menu item event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_menu_item_event(event)

    def test_on_sys_wm_event(self, mock_pygame_patches, mocker):
        """Test sys wm event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_sys_wm_event(event)

    def test_on_text_editing_event(self, mock_pygame_patches, mocker):
        """Test text editing event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_text_editing_event(event)

    def test_on_text_input_event(self, mock_pygame_patches, mocker):
        """Test text input event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_text_input_event(event)

    def test_on_touch_down_event(self, mock_pygame_patches, mocker):
        """Test touch down event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_touch_down_event(event)

    def test_on_touch_motion_event(self, mock_pygame_patches, mocker):
        """Test touch motion event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_touch_motion_event(event)

    def test_on_touch_up_event(self, mock_pygame_patches, mocker):
        """Test touch up event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_touch_up_event(event)

    def test_on_user_event(self, mock_pygame_patches, mocker):
        """Test user event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_user_event(event)

    def test_on_video_expose_event(self, mock_pygame_patches, mocker):
        """Test video expose event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_video_expose_event(event)

    def test_on_video_resize_event(self, mock_pygame_patches, mocker):
        """Test video resize event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_video_resize_event(event)

    def test_on_window_close_event(self, mock_pygame_patches, mocker):
        """Test window close event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_close_event(event)

    def test_on_window_enter_event(self, mock_pygame_patches, mocker):
        """Test window enter event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_enter_event(event)

    def test_on_window_exposed_event(self, mock_pygame_patches, mocker):
        """Test window exposed event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_exposed_event(event)

    def test_on_window_focus_gained_event(self, mock_pygame_patches, mocker):
        """Test window focus gained event handler."""
        scene = Scene()
        event = mocker.Mock()
        scene.on_window_focus_gained_event(event)


class TestSceneMouseEventHandlers:
    """Test mouse-related event handlers on Scene."""

    def test_on_mouse_button_down_event(self, mock_pygame_patches, mocker):
        """Test mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_mouse_button_down_event(event)

    def test_on_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_mouse_drag_event(event, trigger)

    def test_on_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_mouse_drop_event(event, trigger)

    def test_on_left_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test left mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_left_mouse_drag_event(event, trigger)

    def test_on_left_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test left mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_left_mouse_drop_event(event, trigger)

    def test_on_middle_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test middle mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_middle_mouse_drag_event(event, trigger)

    def test_on_middle_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test middle mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_middle_mouse_drop_event(event, trigger)

    def test_on_right_mouse_drag_event(self, mock_pygame_patches, mocker):
        """Test right mouse drag event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_right_mouse_drag_event(event, trigger)

    def test_on_right_mouse_drop_event(self, mock_pygame_patches, mocker):
        """Test right mouse drop event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        trigger = mocker.Mock()
        scene.on_right_mouse_drop_event(event, trigger)

    def test_on_left_mouse_button_up_event(self, mock_pygame_patches, mocker):
        """Test left mouse button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_left_mouse_button_up_event(event)

    def test_on_middle_mouse_button_up_event(self, mock_pygame_patches, mocker):
        """Test middle mouse button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_middle_mouse_button_up_event(event)

    def test_on_right_mouse_button_up_event(self, mock_pygame_patches, mocker):
        """Test right mouse button up event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_right_mouse_button_up_event(event)

    def test_on_left_mouse_button_down_event(self, mock_pygame_patches, mocker):
        """Test left mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_left_mouse_button_down_event(event)

    def test_on_middle_mouse_button_down_event(self, mock_pygame_patches, mocker):
        """Test middle mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_middle_mouse_button_down_event(event)

    def test_on_right_mouse_button_down_event(self, mock_pygame_patches, mocker):
        """Test right mouse button down event handler."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (100, 100)
        scene.on_right_mouse_button_down_event(event)


class TestScenePauseAndResume:
    """Test Scene pause/resume/game_over methods."""

    def test_pause_creates_pause_scene(self, mock_pygame_patches, mocker):
        """Test pause() creates and switches to a PauseScene."""
        scene = Scene()
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.pause()

        scene.scene_manager.switch_to_scene.assert_called_once()

    def test_resume_switches_to_previous_scene(self, mock_pygame_patches, mocker):
        """Test resume() switches back to the previous scene."""
        scene = Scene()
        previous = Scene()
        scene.scene_manager.previous_scene = previous
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.resume()

        scene.scene_manager.switch_to_scene.assert_called_once_with(previous)

    def test_resume_without_previous_scene(self, mock_pygame_patches, mocker):
        """Test resume() when no previous scene exists."""
        scene = Scene()
        scene.scene_manager.previous_scene = None
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.resume()

        scene.scene_manager.switch_to_scene.assert_not_called()

    def test_game_over_creates_game_over_scene(self, mock_pygame_patches, mocker):
        """Test game_over() creates and switches to GameOverScene."""
        scene = Scene()
        scene.scene_manager.switch_to_scene = mocker.Mock()

        scene.game_over()

        scene.scene_manager.switch_to_scene.assert_called_once()


class TestSceneOnFpsEvent:
    """Test Scene.on_fps_event() method."""

    def test_on_fps_event_updates_fps(self, mock_pygame_patches, mocker):
        """Test FPS event updates the scene's fps attribute."""
        scene = Scene()
        event = mocker.Mock()
        event.fps = 59.5

        scene.on_fps_event(event)

        assert abs(scene.fps - 59.5) < 1e-9


class TestSceneOnTextSubmitEvent:
    """Test Scene.on_text_submit_event() method."""

    def test_on_text_submit_event_logs(self, mock_pygame_patches, mocker):
        """Test text submit event is handled."""
        scene = Scene()
        scene.on_text_submit_event('Hello World')


class TestSceneManagerHelpers:
    """Test SceneManager helper methods."""

    def test_scene_manager_stop(self, mock_pygame_patches, mocker):
        """Test SceneManager.stop() calls terminate."""
        manager = SceneManager()
        manager.switch_to_scene = mocker.Mock()
        manager.stop()
        manager.switch_to_scene.assert_called_once_with(None)

    def test_scene_manager_quit(self, mock_pygame_patches, mocker):
        """Test SceneManager.quit() posts QUIT event."""
        manager = SceneManager()
        mock_post = mocker.patch('pygame.event.post')
        manager.quit()
        mock_post.assert_called_once()

    def test_scene_manager_on_quit_event(self, mock_pygame_patches, mocker):
        """Test SceneManager.on_quit_event sets quit_requested."""
        manager = SceneManager()
        event = mocker.Mock()

        manager.on_quit_event(event)

        assert manager.quit_requested is True

    def test_scene_manager_all_sprites_with_active_scene(self, mock_pygame_patches, mocker):
        """Test SceneManager.all_sprites returns active scene's sprites."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        assert manager.all_sprites == scene.all_sprites

    def test_scene_manager_all_sprites_without_active_scene(self, mock_pygame_patches):
        """Test SceneManager.all_sprites returns None without active scene."""
        manager = SceneManager()
        manager.active_scene = None

        assert manager.all_sprites is None


class TestLogJitterStats:
    """Test SceneManager._log_jitter_stats() method."""

    def test_log_jitter_stats_initializes_buffer_on_first_call(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats initializes jitter buffer on first call."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 1000

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 1_000_000_000

        # First call should create _jitter_samples
        manager._log_jitter_stats(mock_timer, wake_ns=1_000_100, deadline_ns=1_000_000)

        assert hasattr(manager, '_jitter_samples')
        assert len(manager._jitter_samples) == 1
        assert manager._jitter_samples[0] == 100  # jitter_ns = wake - deadline

    def test_log_jitter_stats_accumulates_samples(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats accumulates jitter samples."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 1000

        mock_timer = mocker.Mock()
        # Return increasing timestamps, but not enough to trigger interval log
        mock_timer.ns_now.return_value = 100_000_000

        for i in range(5):
            manager._log_jitter_stats(mock_timer, wake_ns=1000 + i * 50, deadline_ns=1000)

        assert len(manager._jitter_samples) == 5

    def test_log_jitter_stats_trims_buffer_when_exceeds_max(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats trims buffer when it exceeds max size."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 100_000  # Large interval to avoid triggering log

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 100_000_000

        # Pre-fill the buffer beyond max
        manager._jitter_samples = list(range(JITTER_SAMPLE_BUFFER_MAX_SIZE + 100))
        manager._jitter_last_log_ns = 0
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 0

        manager._log_jitter_stats(mock_timer, wake_ns=2000, deadline_ns=1000)

        # Buffer should be trimmed to max size
        assert len(manager._jitter_samples) <= JITTER_SAMPLE_BUFFER_MAX_SIZE

    def test_log_jitter_stats_counts_late_frames(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats counts late frames when jitter > 0."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 100_000  # Large to avoid triggering log

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 100_000_000

        # Call with positive jitter
        manager._log_jitter_stats(mock_timer, wake_ns=2000, deadline_ns=1000)
        manager._log_jitter_stats(mock_timer, wake_ns=3000, deadline_ns=1000)

        assert manager._jitter_late_frames == 2

    def test_log_jitter_stats_zero_jitter_not_late(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats does not count zero jitter as late."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 100_000

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 100_000_000

        # Call with zero jitter (wake == deadline)
        manager._log_jitter_stats(mock_timer, wake_ns=1000, deadline_ns=1000)

        assert manager._jitter_late_frames == 0

    def test_log_jitter_stats_triggers_interval_log(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats triggers interval log when time exceeds interval."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 1  # 1ms interval (very short)

        mock_timer = mocker.Mock()
        # First call initializes
        mock_timer.ns_now.return_value = 0
        manager._log_jitter_stats(mock_timer, wake_ns=100, deadline_ns=0)

        # Second call exceeds interval (2ms later = 2_000_000 ns)
        mock_timer.ns_now.return_value = 2_000_000
        mock_log = mocker.patch.object(manager, 'log')
        manager._log_jitter_stats(mock_timer, wake_ns=2_000_100, deadline_ns=2_000_000)

        mock_log.info.assert_called()

    def test_log_jitter_stats_handles_exception_gracefully(self, mock_pygame_patches, mocker):
        """Test that _log_jitter_stats handles exceptions without crashing."""
        manager = SceneManager()
        manager.fps_log_interval_ms = 'invalid'  # type: ignore[invalid-assignment]  # Will cause ValueError in float()

        mock_timer = mocker.Mock()
        mock_timer.ns_now.return_value = 1_000_000_000

        # Should not raise
        manager._log_jitter_stats(mock_timer, wake_ns=2000, deadline_ns=1000)


class TestLogJitterInterval:
    """Test SceneManager._log_jitter_interval() method."""

    def test_log_jitter_interval_with_data(self, mock_pygame_patches, mocker):
        """Test _log_jitter_interval logs percentile statistics."""
        manager = SceneManager()
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 5

        mock_log = mocker.patch.object(manager, 'log')

        buffer = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
        manager._log_jitter_interval(buffer, now_ns=1_000_000_000)

        mock_log.info.assert_called_once()
        call_args = mock_log.info.call_args[0][0]
        assert 'p50=' in call_args
        assert 'p95=' in call_args
        assert 'p99=' in call_args
        assert 'max=' in call_args
        assert 'avg_fps=' in call_args
        assert 'late=' in call_args

    def test_log_jitter_interval_resets_counters(self, mock_pygame_patches, mocker):
        """Test _log_jitter_interval resets counters after logging."""
        manager = SceneManager()
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 10
        mocker.patch.object(manager, 'log')

        now_ns = 5_000_000_000
        manager._log_jitter_interval([100, 200], now_ns=now_ns)

        assert manager._jitter_last_log_ns == now_ns
        assert manager._jitter_interval_start_ns == now_ns
        assert manager._jitter_late_frames == 0

    def test_log_jitter_interval_empty_buffer(self, mock_pygame_patches, mocker):
        """Test _log_jitter_interval with empty buffer does not log."""
        manager = SceneManager()
        manager._jitter_interval_start_ns = 0
        manager._jitter_late_frames = 0

        mock_log = mocker.patch.object(manager, 'log')
        manager._log_jitter_interval([], now_ns=1_000_000_000)

        # info should not be called since count is 0
        mock_log.info.assert_not_called()


class TestHandleFramePacing:
    """Test SceneManager._handle_frame_pacing() method."""

    def test_handle_frame_pacing_with_timer(self, mock_pygame_patches, mocker):
        """Test frame pacing delegates to timer when available."""
        manager = SceneManager()
        type(manager).OPTIONS = {'log_timer_jitter': False}

        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 2_000_000
        mock_timer.sleep_until_next.return_value = 2_000_100

        manager._handle_frame_pacing(
            timer=mock_timer,
            period_ns=16_666_667,
            prev_deadline_ns=1_000_000,
            frame_start_ns=1_000_000,
        )

        mock_timer.compute_deadline.assert_called_once()
        mock_timer.sleep_until_next.assert_called_once()
        assert manager._timer_prev_deadline_ns == 2_000_000

    def test_handle_frame_pacing_with_timer_and_jitter_logging(self, mock_pygame_patches, mocker):
        """Test frame pacing calls jitter logging when enabled."""
        manager = SceneManager()
        type(manager).OPTIONS = {'log_timer_jitter': True}
        manager.fps_log_interval_ms = 100_000

        mock_timer = mocker.Mock()
        mock_timer.compute_deadline.return_value = 2_000_000
        mock_timer.sleep_until_next.return_value = 2_000_100
        mock_timer.ns_now.return_value = 100_000

        mock_log_jitter = mocker.patch.object(manager, '_log_jitter_stats')

        manager._handle_frame_pacing(
            timer=mock_timer,
            period_ns=16_666_667,
            prev_deadline_ns=1_000_000,
            frame_start_ns=1_000_000,
        )

        mock_log_jitter.assert_called_once_with(mock_timer, 2_000_100, 2_000_000)

    def test_handle_frame_pacing_fallback_with_target_fps(self, mock_pygame_patches, mocker):
        """Test frame pacing falls back to clock.tick when no timer but target_fps > 0."""
        manager = SceneManager()
        manager.target_fps = 60

        mock_clock_tick = mocker.patch.object(manager.clock, 'tick')

        manager._handle_frame_pacing(
            timer=None, period_ns=0, prev_deadline_ns=None, frame_start_ns=0,
        )

        mock_clock_tick.assert_called_once_with(60)

    def test_handle_frame_pacing_fallback_unlimited_fps(self, mock_pygame_patches, mocker):
        """Test frame pacing falls back to clock.tick() when no timer and target_fps is 0."""
        manager = SceneManager()
        manager.target_fps = 0

        mock_clock_tick = mocker.patch.object(manager.clock, 'tick')

        manager._handle_frame_pacing(
            timer=None, period_ns=0, prev_deadline_ns=None, frame_start_ns=0,
        )

        mock_clock_tick.assert_called_once_with()


class TestPostFpsEvent:
    """Test SceneManager._post_fps_event() method."""

    def test_post_fps_event_uses_dt_when_available(self, mock_pygame_patches, mocker):
        """Test _post_fps_event computes FPS from dt when dt > 0."""
        manager = SceneManager()
        manager.dt = 0.016  # ~62.5 FPS

        mock_post = mocker.patch('pygame.event.post')

        manager._post_fps_event()

        mock_post.assert_called_once()

    def test_post_fps_event_falls_back_to_clock(self, mock_pygame_patches, mocker):
        """Test _post_fps_event falls back to clock.get_fps when dt is 0."""
        manager = SceneManager()
        manager.dt = 0  # dt is zero, should fall back

        mocker.patch.object(manager.clock, 'get_fps', return_value=60.0)
        mock_post = mocker.patch('pygame.event.post')

        manager._post_fps_event()

        mock_post.assert_called_once()


class TestTickClock:
    """Test SceneManager._tick_clock() method."""

    def test_tick_clock_with_target_fps(self, mock_pygame_patches, mocker):
        """Test _tick_clock calls clock.tick with target_fps when > 0."""
        manager = SceneManager()
        manager.target_fps = 60
        manager.dt = 0.016

        mock_clock_tick = mocker.patch.object(manager.clock, 'tick')
        mocker.patch.object(manager.clock, 'get_fps', return_value=60.0)
        # Mock performance_manager import to avoid ImportError
        mocker.patch(
            'glitchygames.scenes.scene.SceneManager._tick_clock.__module__',
            create=True,
        )

        manager._tick_clock()

        mock_clock_tick.assert_called_once_with(60)

    def test_tick_clock_unlimited_fps(self, mock_pygame_patches, mocker):
        """Test _tick_clock calls clock.tick without args when target_fps is 0."""
        manager = SceneManager()
        manager.target_fps = 0

        mock_clock_tick = mocker.patch.object(manager.clock, 'tick')

        manager._tick_clock()

        mock_clock_tick.assert_called_once_with()

    def test_tick_clock_performance_manager_import_error(self, mock_pygame_patches, mocker):
        """Test _tick_clock handles ImportError for performance module gracefully."""
        manager = SceneManager()
        manager.target_fps = 60
        manager.dt = 0.016

        mocker.patch.object(manager.clock, 'tick')
        mocker.patch.object(manager.clock, 'get_fps', return_value=60.0)

        # Mock the import to raise ImportError
        original_import = (
            __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__
        )

        def mock_import(name, *args, **kwargs):
            if name == 'glitchygames.performance':
                raise ImportError('No module named glitchygames.performance')
            return original_import(name, *args, **kwargs)

        mocker.patch('builtins.__import__', side_effect=mock_import)

        # Should not raise
        manager._tick_clock()


class TestTrackPerformance:
    """Test SceneManager._track_performance() method."""

    def test_track_performance_with_timer(self, mock_pygame_patches, mocker):
        """Test _track_performance computes FPS from dt when timer is present."""
        manager = SceneManager()
        manager.dt = 0.016

        mock_perf_manager = mocker.Mock()
        mocker.patch(
            'glitchygames.performance.performance_manager',
            mock_perf_manager,
            create=True,
        )

        mock_timer = mocker.Mock()
        manager._track_performance(timer=mock_timer, period_ns=16_666_667, processing_time=0.008)

    def test_track_performance_without_timer(self, mock_pygame_patches, mocker):
        """Test _track_performance uses clock when no timer."""
        manager = SceneManager()
        mocker.patch.object(manager.clock, 'get_fps', return_value=60.0)

        mock_perf_manager = mocker.Mock()
        mocker.patch(
            'glitchygames.performance.performance_manager',
            mock_perf_manager,
            create=True,
        )

        manager._track_performance(timer=None, period_ns=0, processing_time=0.008)


class TestSceneManagerOnFpsEvent:
    """Test SceneManager.on_fps_event() method."""

    def test_on_fps_event_delegates_to_active_scene(self, mock_pygame_patches, mocker):
        """Test on_fps_event delegates to active scene."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene
        mock_on_fps = mocker.patch.object(scene, 'on_fps_event')

        event = mocker.Mock()
        event.fps = 60.0

        manager.on_fps_event(event)

        mock_on_fps.assert_called_once_with(event)

    def test_on_fps_event_no_active_scene(self, mock_pygame_patches, mocker):
        """Test on_fps_event does nothing when no active scene."""
        manager = SceneManager()
        manager.active_scene = None

        event = mocker.Mock()
        event.fps = 60.0

        # Should not raise
        manager.on_fps_event(event)


class TestSceneManagerOnGameEvent:
    """Test SceneManager.on_game_event() method."""

    def test_on_game_event_calls_registered_callback(self, mock_pygame_patches, mocker):
        """Test on_game_event calls the registered callback."""
        manager = SceneManager()
        mock_engine = mocker.Mock()
        callback = mocker.Mock()
        mock_engine.registered_events = {'my_event': callback}
        manager._game_engine = mock_engine

        event = mocker.Mock()
        event.subtype = 'my_event'

        manager.on_game_event(event)

        callback.assert_called_once_with(event)

    def test_on_game_event_unregistered_logs_error(self, mock_pygame_patches, mocker):
        """Test on_game_event logs error for unregistered event."""
        manager = SceneManager()
        mock_engine = mocker.Mock()
        mock_engine.registered_events = {}
        manager._game_engine = mock_engine

        event = mocker.Mock()
        event.subtype = 'unknown_event'

        mock_log = mocker.patch.object(manager, 'log')

        manager.on_game_event(event)

        mock_log.error.assert_called_once()


class TestSceneManagerHandleEvent:
    """Test SceneManager.handle_event() method."""

    def test_handle_event_quit(self, mock_pygame_patches, mocker):
        """Test handle_event sets quit_requested for QUIT events."""
        manager = SceneManager()
        mock_log = mocker.patch.object(manager, 'log')

        event = mocker.Mock()
        event.type = pygame.QUIT

        manager.handle_event(event)

        assert manager.quit_requested is True

    def test_handle_event_with_focused_sprite_keydown(self, mock_pygame_patches, mocker):
        """Test handle_event returns early when focused sprite gets KEYDOWN."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.type = pygame.KEYDOWN

        # Should return early without setting quit_requested
        manager.handle_event(event)
        assert manager.quit_requested is False

    def test_handle_event_no_active_scene(self, mock_pygame_patches, mocker):
        """Test handle_event does not crash when no active scene."""
        manager = SceneManager()
        manager.active_scene = None

        event = mocker.Mock()
        event.type = pygame.KEYDOWN

        # Should not raise
        manager.handle_event(event)


class TestSceneManagerGetattr:
    """Test SceneManager.__getattr__() proxy method."""

    def test_getattr_proxies_event_to_active_scene(self, mock_pygame_patches, mocker):
        """Test __getattr__ proxies on_*_event calls to active scene."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        # This should resolve to the scene's method
        method = manager.on_key_down_event
        assert callable(method)

    def test_getattr_raises_for_non_event_attrs(self, mock_pygame_patches, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        manager = SceneManager()

        with pytest.raises(AttributeError, match='object has no attribute'):
            _ = manager.nonexistent_attribute

    def test_getattr_falls_back_to_game_engine(self, mock_pygame_patches, mocker):
        """Test __getattr__ falls back to game engine when scene doesn't have method."""
        manager = SceneManager()
        manager.active_scene = None

        mock_engine = mocker.Mock()
        mock_engine.on_custom_event = mocker.Mock()
        manager._game_engine = mock_engine

        # When active_scene is None, getattr on it raises AttributeError,
        # so it falls through to game_engine
        method = manager.on_custom_event
        assert callable(method)


class TestSceneManagerShouldPostFpsEvent:
    """Test SceneManager._should_post_fps_event() method."""

    def test_should_post_fps_event_true(self, mock_pygame_patches, mocker):
        """Test returns True when time exceeds half the log interval."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # 600ms has passed, half of 1000ms = 500ms
        result = manager._should_post_fps_event(current_time=1.0, previous_fps_time=0.4)
        assert result is True

    def test_should_post_fps_event_false(self, mock_pygame_patches, mocker):
        """Test returns False when time does not exceed half the log interval."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # Only 100ms has passed, half of 1000ms = 500ms
        result = manager._should_post_fps_event(current_time=1.0, previous_fps_time=0.9)
        assert result is False


class TestSceneManagerPlay:
    """Test SceneManager.play() method."""

    def test_play_delegates_to_start(self, mock_pygame_patches, mocker):
        """Test play() calls start()."""
        manager = SceneManager()
        mock_start = mocker.patch.object(manager, 'start')

        manager.play()

        mock_start.assert_called_once()


class TestSceneManagerQuitGame:
    """Test SceneManager.quit_game() method."""

    def test_quit_game_posts_quit_event(self, mock_pygame_patches, mocker):
        """Test quit_game() posts a QUIT event to the pygame event queue."""
        manager = SceneManager()
        mock_post = mocker.patch('pygame.event.post')

        manager.quit_game()

        mock_post.assert_called_once()


class TestSceneManagerUpdateTiming:
    """Test SceneManager._update_timing() method."""

    def test_update_timing_returns_updated_times(self, mock_pygame_patches, mocker):
        """Test _update_timing returns tuple of updated times."""
        manager = SceneManager()
        mocker.patch('time.perf_counter', return_value=1.5)

        result = manager._update_timing(previous_time=1.0, current_time=0.5)

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert abs(manager.dt - 0.5) < 0.01


class TestSceneManagerGetattrDeeper:
    """Test SceneManager.__getattr__ proxy method."""

    def test_getattr_proxies_event_method_to_active_scene(self, mock_pygame_patches, mocker):
        """Test __getattr__ proxies on_*_event calls to active scene."""
        manager = SceneManager()
        scene = Scene()
        scene.on_custom_test_event = mocker.Mock()  # type: ignore[unresolved-attribute]
        manager.active_scene = scene

        handler = manager.on_custom_test_event
        assert handler is scene.on_custom_test_event  # type: ignore[unresolved-attribute]

    def test_getattr_raises_for_non_event_attributes(self, mock_pygame_patches, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        manager = SceneManager()
        with pytest.raises(AttributeError):
            _ = manager.some_random_attribute

    def test_getattr_falls_back_to_game_engine(self, mock_pygame_patches, mocker):
        """Test __getattr__ falls back to game_engine when scene has no handler."""
        manager = SceneManager()
        # Create a scene mock that raises AttributeError for on_some_obscure_event
        scene = mocker.Mock()
        del scene.on_some_obscure_event  # Force AttributeError on this attribute
        manager.active_scene = scene

        # Set _game_engine directly to avoid the setter's OPTIONS subscription
        mock_engine = mocker.Mock()
        mock_handler = mocker.Mock()
        mock_engine.on_some_obscure_event = mock_handler
        manager._game_engine = mock_engine

        handler = manager.on_some_obscure_event
        assert handler is mock_handler


class TestSceneManagerHandleEventDeeper:
    """Test SceneManager.handle_event method."""

    def test_handle_event_quit_sets_flag(self, mock_pygame_patches, mocker):
        """Test handle_event with QUIT event sets quit_requested."""
        manager = SceneManager()
        manager.active_scene = mocker.Mock()
        manager.active_scene.all_sprites = []

        event = mocker.Mock()
        event.type = pygame.QUIT

        manager.handle_event(event)
        assert manager.quit_requested is True

    def test_handle_event_keydown_with_focused_sprites(self, mock_pygame_patches, mocker):
        """Test handle_event KEYDOWN routes through to scene when sprites are focused."""
        manager = SceneManager()
        scene = Scene()
        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        scene.all_sprites.add(focused_sprite)
        manager.active_scene = scene

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_a

        # This should not quit since there are focused sprites
        manager.handle_event(event)
        # quit_requested should remain False (not a quit event)
        assert manager.quit_requested is not True


class TestSceneManagerShouldPostFpsEventDeeper:
    """Test SceneManager._should_post_fps_event method."""

    def test_should_post_fps_event_true(self, mock_pygame_patches, mocker):
        """Test returns True when enough time has elapsed."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # 1 second elapsed, interval is 500ms (half of 1000)
        result = manager._should_post_fps_event(current_time=2.0, previous_fps_time=1.0)
        assert result is True

    def test_should_post_fps_event_false(self, mock_pygame_patches, mocker):
        """Test returns False when not enough time has elapsed."""
        manager = SceneManager()
        type(manager).OPTIONS = {'fps_log_interval_ms': 1000}

        # 0.1 second elapsed, interval is 500ms
        result = manager._should_post_fps_event(current_time=1.1, previous_fps_time=1.0)
        assert result is False


class TestSceneManagerPostFpsEvent:
    """Test SceneManager._post_fps_event method."""

    def test_post_fps_event_with_dt(self, mock_pygame_patches, mocker):
        """Test _post_fps_event posts event based on dt."""
        manager = SceneManager()
        manager.dt = 0.016  # ~60 FPS
        manager.clock = mocker.Mock()

        mock_post = mocker.patch('pygame.event.post')
        manager._post_fps_event()
        mock_post.assert_called_once()

    def test_post_fps_event_with_zero_dt(self, mock_pygame_patches, mocker):
        """Test _post_fps_event falls back to clock.get_fps when dt is 0."""
        manager = SceneManager()
        manager.dt = 0
        manager.clock = mocker.Mock()
        manager.clock.get_fps.return_value = 60.0

        mock_post = mocker.patch('pygame.event.post')
        manager._post_fps_event()
        mock_post.assert_called_once()


class TestSceneManagerUpdateDisplay:
    """Test SceneManager._update_display method."""

    def test_update_display_update_with_rects(self, mock_pygame_patches, mocker):
        """Test _update_display with 'update' type and rects."""
        manager = SceneManager()
        manager.update_type = 'update'
        rects = [pygame.Rect(0, 0, 100, 100)]
        manager.active_scene = mocker.Mock()
        manager.active_scene.rects = rects

        # Should not raise
        manager._update_display()

    def test_update_display_update_without_rects(self, mock_pygame_patches, mocker):
        """Test _update_display with 'update' type and no rects."""
        manager = SceneManager()
        manager.update_type = 'update'
        manager.active_scene = mocker.Mock()
        manager.active_scene.rects = []

        # Empty rects triggers full display update
        manager._update_display()

    def test_update_display_flip(self, mock_pygame_patches, mocker):
        """Test _update_display with 'flip' type."""
        manager = SceneManager()
        manager.update_type = 'flip'
        manager.active_scene = mocker.Mock()

        # Should not raise
        manager._update_display()


class TestSceneManagerLogQuitInfo:
    """Test SceneManager._log_quit_info method."""

    def test_log_quit_info_does_not_raise(self, mock_pygame_patches, mocker):
        """Test _log_quit_info runs without error."""
        manager = SceneManager()
        manager.active_scene = mocker.Mock()
        manager.quit_requested = False
        # Should not raise
        manager._log_quit_info()


class TestSceneManagerTerminate:
    """Test SceneManager.terminate method."""

    def test_terminate_calls_switch_to_none(self, mock_pygame_patches, mocker):
        """Test terminate switches to None scene."""
        manager = SceneManager()
        manager.switch_to_scene = mocker.Mock()
        manager.terminate()
        manager.switch_to_scene.assert_called_once_with(None)


class TestSceneManagerQuitGameDeeper:
    """Test SceneManager.quit_game method."""

    def test_quit_game_posts_quit_event(self, mock_pygame_patches, mocker):
        """Test quit_game posts a QUIT event."""
        manager = SceneManager()
        mock_post = mocker.patch('pygame.event.post')
        manager.quit_game()
        mock_post.assert_called_once()

    def test_quit_alias_calls_quit_game(self, mock_pygame_patches, mocker):
        """Test quit() is an alias for quit_game."""
        manager = SceneManager()
        mock_post = mocker.patch('pygame.event.post')
        manager.quit()
        mock_post.assert_called_once()


class TestSceneManagerOnFpsEventDeeper:
    """Test SceneManager.on_fps_event method."""

    def test_on_fps_event_with_active_scene(self, mock_pygame_patches, mocker):
        """Test on_fps_event delegates to active scene."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager.active_scene = scene

        event = mocker.Mock()
        event.fps = 60.0

        manager.on_fps_event(event)
        scene.on_fps_event.assert_called_once_with(event)

    def test_on_fps_event_without_active_scene(self, mock_pygame_patches, mocker):
        """Test on_fps_event does nothing without active scene."""
        manager = SceneManager()
        manager.active_scene = None

        event = mocker.Mock()
        event.fps = 60.0

        # Should not raise
        manager.on_fps_event(event)


class TestSceneScreenshotProperty:
    """Test Scene.screenshot property."""

    def test_screenshot_returns_surface(self, mock_pygame_patches):
        """Test screenshot returns a pygame Surface."""
        scene = Scene()
        screenshot = scene.screenshot
        assert isinstance(screenshot, pygame.Surface)

    def test_screenshot_has_correct_size(self, mock_pygame_patches):
        """Test screenshot has the same size as the screen."""
        scene = Scene()
        screenshot = scene.screenshot
        assert screenshot.get_width() == scene.screen_width
        assert screenshot.get_height() == scene.screen_height


class TestSceneBackgroundColor:
    """Test Scene.background_color property."""

    def test_background_color_getter(self, mock_pygame_patches):
        """Test background_color getter returns current color."""
        scene = Scene()
        # Default is BLACK
        assert scene.background_color is not None

    def test_background_color_setter(self, mock_pygame_patches):
        """Test background_color setter updates the color."""
        scene = Scene()
        # RGB gets normalized to RGBA with alpha=0
        scene.background_color = (255, 0, 0)
        assert scene.background_color == (255, 0, 0, 0)


class TestSceneUpdate:
    """Test Scene.update() method."""

    def test_update_with_dirty_sprites(self, mock_pygame_patches, mocker):
        """Test update calls update on dirty sprites."""
        scene = Scene()
        mock_sprite = mocker.Mock()
        mock_sprite.dirty = 1
        mock_sprite.update_nested_sprites = mocker.Mock()
        mock_sprite.update = mocker.Mock()
        mock_sprite.name = 'test'
        scene.all_sprites.add(mock_sprite)

        scene.update()
        mock_sprite.update_nested_sprites.assert_called()
        mock_sprite.update.assert_called()

    def test_update_forces_redraw_when_scene_dirty(self, mock_pygame_patches, mocker):
        """Test update forces redraw on all sprites when scene is dirty."""
        scene = Scene()
        scene.dirty = 1
        mock_sprite = mocker.Mock()
        mock_sprite.dirty = 0
        mock_sprite.update_nested_sprites = mocker.Mock()
        mock_sprite.name = 'test'
        scene.all_sprites.add(mock_sprite)

        scene.update()
        # Sprite should be marked dirty after scene update
        assert mock_sprite.dirty == 1


class TestSceneRender:
    """Test Scene.render() method."""

    def test_render_calls_draw(self, mock_pygame_patches, mocker):
        """Test render calls all_sprites.draw."""
        scene = Scene()
        mock_draw = mocker.patch.object(scene.all_sprites, 'draw', return_value=[])
        mock_clear = mocker.patch.object(scene.all_sprites, 'clear')

        assert scene.screen is not None
        scene.render(scene.screen)
        mock_clear.assert_called_once()
        mock_draw.assert_called_once_with(scene.screen)


class TestSceneOnKeyDownEventDeeper:
    """Test Scene.on_key_down_event with non-quit keys."""

    def test_key_down_q_sets_quit(self, mock_pygame_patches, mocker):
        """Test q key sets quit_requested on scene."""
        scene = Scene()
        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)
        assert scene.quit_requested is True

    def test_key_down_non_quit_key(self, mock_pygame_patches, mocker):
        """Test non-quit key does not set quit_requested when no focused sprites."""
        scene = Scene()
        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)


class TestSceneOnKeyUpEventDeeper:
    """Test Scene.on_key_up_event with non-quit keys."""

    def test_key_up_non_quit_key_no_effect(self, mock_pygame_patches, mocker):
        """Test non-quit key up has no quit effect."""
        scene = Scene()
        mock_post = mocker.patch('pygame.event.post')
        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_up_event(event)
        mock_post.assert_not_called()


class TestSceneHandleFocusManagementWithFocusable:
    """Test Scene._handle_focus_management with focusable sprites."""

    def test_handle_focus_management_keeps_focused_when_focusable_clicked(
        self, mock_pygame_patches, mocker,
    ):
        """Test focus is maintained when clicking on a focusable sprite."""
        scene = Scene()

        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_focus_lost = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        focusable_sprite = mocker.Mock()
        focusable_sprite.focusable = True

        # Click on a focusable sprite - should NOT unfocus existing sprites
        scene._handle_focus_management([focusable_sprite])
        focused_sprite.on_focus_lost.assert_not_called()


class TestSceneOnMouseButtonDownEventDeeper:
    """Test Scene.on_mouse_button_down_event with sprite collisions."""

    def test_mouse_button_down_logs_collision_info(self, mock_pygame_patches, mocker):
        """Test mouse button down logs collision info."""
        scene = Scene()
        event = mocker.Mock()
        event.pos = (50, 50)

        # Should not raise even with no sprites
        scene.on_mouse_button_down_event(event)


class TestSceneManagerAllSprites:
    """Test SceneManager.all_sprites property edge cases."""

    def test_all_sprites_with_scene(self, mock_pygame_patches, mocker):
        """Test all_sprites returns scene's sprites."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene
        assert manager.all_sprites is scene.all_sprites

    def test_all_sprites_without_scene(self, mock_pygame_patches):
        """Test all_sprites returns None without active scene."""
        manager = SceneManager()
        manager.active_scene = None
        assert manager.all_sprites is None


class TestSceneSetup:
    """Test Scene.setup() method."""

    def test_setup_does_not_raise(self, mock_pygame_patches):
        """Test setup() can be called without error."""
        scene = Scene()
        scene.setup()  # Base implementation is a no-op


class TestSceneManagerSwitchToScene:
    """Test SceneManager.switch_to_scene full lifecycle."""

    def test_switch_to_scene_tracks_previous(self, mock_pygame_patches, mocker):
        """Test switch_to_scene records previous scene."""
        manager = SceneManager()
        first_scene = Scene()
        manager.active_scene = first_scene

        second_scene = Scene()
        second_scene.NAME = 'SecondScene'
        second_scene.VERSION = '2.0'

        # Mock sub-methods to prevent side effects
        manager._game_engine = mocker.Mock()
        manager._game_engine.OPTIONS = {
            'update_type': 'update',
            'fps_log_interval_ms': 1000,
            'target_fps': 60,
        }
        type(manager).OPTIONS = manager._game_engine.OPTIONS
        manager.target_fps = 60

        manager.switch_to_scene(second_scene)

        assert manager.previous_scene is first_scene
        assert manager.active_scene is second_scene

    def test_switch_to_same_scene_does_nothing(self, mock_pygame_patches, mocker):
        """Test switch_to_scene with same scene is a no-op."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene
        old_previous = manager.previous_scene

        manager.switch_to_scene(scene)
        # previous_scene should not change
        assert manager.previous_scene is old_previous

    def test_switch_to_none_terminates(self, mock_pygame_patches, mocker):
        """Test switch_to_scene with None sets active_scene to None."""
        manager = SceneManager()
        scene = Scene()
        manager.active_scene = scene

        manager.switch_to_scene(None)
        assert manager.active_scene is None


class TestSceneManagerCleanupAndSetup:
    """Test SceneManager cleanup and setup helper methods."""

    def test_cleanup_current_scene_calls_cleanup(self, mock_pygame_patches, mocker):
        """Test _cleanup_current_scene calls active scene cleanup."""
        manager = SceneManager()
        scene = Scene()
        scene.cleanup = mocker.Mock()
        manager.active_scene = scene

        manager._cleanup_current_scene()
        scene.cleanup.assert_called_once()

    def test_cleanup_current_scene_none(self, mock_pygame_patches):
        """Test _cleanup_current_scene does nothing with None scene."""
        manager = SceneManager()
        manager.active_scene = None
        manager._cleanup_current_scene()  # Should not raise

    def test_setup_new_scene_calls_setup(self, mock_pygame_patches, mocker):
        """Test _setup_new_scene calls new scene setup."""
        manager = SceneManager()
        scene = Scene()
        scene.setup = mocker.Mock()
        manager._game_engine = mocker.Mock()

        manager._setup_new_scene(scene)
        scene.setup.assert_called_once()
        assert scene.game_engine is manager._game_engine  # type: ignore[unresolved-attribute]

    def test_setup_new_scene_none(self, mock_pygame_patches):
        """Test _setup_new_scene does nothing with None scene."""
        manager = SceneManager()
        manager._setup_new_scene(None)  # Should not raise


class TestSceneManagerConfigureActiveScene:
    """Test SceneManager._configure_active_scene and sub-methods."""

    def test_configure_active_scene_sets_caption(self, mock_pygame_patches, mocker):
        """Test _configure_active_scene sets display caption."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'TestGame'
        scene.VERSION = '1.0'
        scene.target_fps = 60
        scene.dirty = 0
        manager.active_scene = scene
        manager.target_fps = 60

        # pygame.display is already mocked by mock_pygame_patches,
        # so access set_caption via the mock display object
        import pygame

        pygame.display.set_caption.reset_mock()  # type: ignore[union-attr]
        manager._configure_active_scene()
        pygame.display.set_caption.assert_called_once()  # type: ignore[union-attr]
        call_args = pygame.display.set_caption.call_args[0][0]  # type: ignore[union-attr]
        assert 'TestGame' in call_args
        assert '1.0' in call_args

    def test_configure_active_scene_none(self, mock_pygame_patches):
        """Test _configure_active_scene does nothing with None scene."""
        manager = SceneManager()
        manager.active_scene = None
        manager._configure_active_scene()  # Should not raise

    def test_set_display_caption_name_only(self, mock_pygame_patches, mocker):
        """Test _set_display_caption with NAME but no VERSION."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'MyGame'
        scene.VERSION = ''
        manager.active_scene = scene

        # pygame.display is already mocked by mock_pygame_patches,
        # so access set_caption via the mock display object
        import pygame

        pygame.display.set_caption.reset_mock()  # type: ignore[union-attr]
        manager._set_display_caption()
        pygame.display.set_caption.assert_called_once()  # type: ignore[union-attr]
        call_args = pygame.display.set_caption.call_args[0][0]  # type: ignore[union-attr]
        assert call_args == 'MyGame'

    def test_configure_scene_fps(self, mock_pygame_patches, mocker):
        """Test _configure_scene_fps sets target_fps on scene."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.target_fps = 0
        manager.active_scene = scene
        manager.target_fps = 120

        manager._configure_scene_fps()
        assert scene.target_fps == 120

    def test_log_scene_rendering_info_unlimited_fps(self, mock_pygame_patches, mocker):
        """Test _log_scene_rendering_info with unlimited FPS."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'UnlimitedGame'
        scene.target_fps = 0
        manager.active_scene = scene

        # Should not raise
        manager._log_scene_rendering_info()

    def test_log_scene_rendering_info_fixed_fps(self, mock_pygame_patches, mocker):
        """Test _log_scene_rendering_info with fixed FPS."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.NAME = 'FixedGame'
        scene.target_fps = 60
        manager.active_scene = scene

        manager._log_scene_rendering_info()

    def test_setup_event_proxies(self, mock_pygame_patches, mocker):
        """Test _setup_event_proxies sets proxies list."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager.active_scene = scene

        manager._setup_event_proxies()
        assert len(manager.proxies) == 2
        assert manager.proxies[0] is manager
        assert manager.proxies[1] is scene

    def test_force_scene_redraw(self, mock_pygame_patches, mocker):
        """Test _force_scene_redraw marks scene dirty."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.dirty = 0
        manager.active_scene = scene

        manager._force_scene_redraw()
        assert scene.dirty == 1

    def test_apply_scene_fps_is_noop(self, mock_pygame_patches, mocker):
        """Test _apply_scene_fps is a no-op (intentionally)."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager.active_scene = scene

        # Should not raise or modify anything
        manager._apply_scene_fps()


class TestSceneManagerLogBlockedEvents:
    """Test SceneManager._log_blocked_events."""

    def test_log_blocked_events_with_scene(self, mock_pygame_patches, mocker):
        """Test _log_blocked_events logs for active scene."""
        manager = SceneManager()
        scene = mocker.Mock()
        scene.name = 'TestScene'
        manager._log_blocked_events(scene)  # Should not raise

    def test_log_blocked_events_none(self, mock_pygame_patches):
        """Test _log_blocked_events with None scene does nothing."""
        manager = SceneManager()
        manager._log_blocked_events(None)  # Should not raise


class TestSceneManagerGameEvents:
    """Test SceneManager game event handling."""

    def test_on_game_event_registered(self, mock_pygame_patches, mocker):
        """Test on_game_event calls registered callback."""
        manager = SceneManager()
        manager._game_engine = mocker.Mock()
        callback = mocker.Mock()
        manager._game_engine.registered_events = {42: callback}

        event = mocker.Mock()
        event.subtype = 42

        manager.on_game_event(event)
        callback.assert_called_once_with(event)

    def test_on_game_event_unregistered(self, mock_pygame_patches, mocker):
        """Test on_game_event logs error for unregistered event."""
        manager = SceneManager()
        manager._game_engine = mocker.Mock()
        manager._game_engine.registered_events = {}

        event = mocker.Mock()
        event.subtype = 999

        # Should not raise, logs error
        manager.on_game_event(event)

    def test_register_game_event_delegates(self, mock_pygame_patches, mocker):
        """Test register_game_event delegates to game engine."""
        manager = SceneManager()
        manager._game_engine = mocker.Mock()

        callback = mocker.Mock()
        manager.register_game_event(42, callback)
        manager._game_engine.register_game_event.assert_called_once_with(
            event_type=42,
            callback=callback,
        )


class TestSceneManagerUpdateScreen:
    """Test SceneManager.update_screen."""

    def test_update_screen_when_none(self, mock_pygame_patches, mocker):
        """Test update_screen gets surface when screen is None."""
        manager = SceneManager()
        manager.screen = None

        manager.update_screen()
        assert manager.screen is not None

    def test_update_screen_when_already_set(self, mock_pygame_patches, mocker):
        """Test update_screen does nothing when screen exists."""
        manager = SceneManager()
        original_screen = manager.screen

        manager.update_screen()
        assert manager.screen is original_screen


class TestSceneManagerTickClock:
    """Test SceneManager._tick_clock."""

    def test_tick_clock_with_target_fps(self, mock_pygame_patches, mocker):
        """Test _tick_clock limits to target FPS."""
        manager = SceneManager()
        manager.target_fps = 60
        manager.dt = 0.016

        manager._tick_clock()  # Should not raise

    def test_tick_clock_unlimited_fps(self, mock_pygame_patches, mocker):
        """Test _tick_clock without FPS limit."""
        manager = SceneManager()
        manager.target_fps = 0
        manager.dt = 0.001

        manager._tick_clock()  # Should not raise


class TestSceneOnKeyDownWithFocusedSprites:
    """Test Scene.on_key_down_event with focused sprites for non-quit keys."""

    def test_key_down_q_sets_quit(self, mock_pygame_patches, mocker):
        """Test Q key sets quit_requested on Scene."""
        scene = Scene()
        event = mocker.Mock()
        event.key = pygame.K_q

        scene.on_key_down_event(event)
        assert scene.quit_requested is True

    def test_key_down_non_quit_with_focused_sprite(self, mock_pygame_patches, mocker):
        """Test non-quit key is dispatched to focused sprite."""
        scene = Scene()
        focused_sprite = mocker.Mock()
        focused_sprite.active = True
        focused_sprite.on_key_down_event = mocker.Mock()
        scene.all_sprites.add(focused_sprite)

        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)
        focused_sprite.on_key_down_event.assert_called_once_with(event)

    def test_key_down_non_quit_no_focused_sprites(self, mock_pygame_patches, mocker):
        """Test non-quit key with no focused sprites does not quit."""
        scene = Scene()
        event = mocker.Mock()
        event.key = pygame.K_a

        scene.on_key_down_event(event)
        # Should not set quit_requested for non-quit key
        assert not hasattr(scene, 'quit_requested') or scene.quit_requested is not True


class TestSceneUpdateWithFilmStrip:
    """Test Scene.update with Film Strip sprite name."""

    def test_update_with_film_strip_sprite(self, mock_pygame_patches, mocker):
        """Test update handles Film Strip sprite specially."""
        scene = Scene()
        scene.dt = 0.016

        film_strip = mocker.Mock()
        film_strip.name = 'Film Strip'
        film_strip.dirty = 1
        film_strip.update_nested_sprites = mocker.Mock()
        film_strip.update = mocker.Mock()
        film_strip._last_dt = 0

        scene.all_sprites.add(film_strip)
        scene.update()

        # Film strip should have _last_dt set and update called
        assert film_strip._last_dt == pytest.approx(0.016)
        # update() is called both in dirty loop and film strip loop
        assert film_strip.update.call_count >= 1


class TestSceneManagerResetSceneTimers:
    """Test SceneManager._reset_scene_timers."""

    def test_reset_scene_timers(self, mock_pygame_patches):
        """Test _reset_scene_timers zeroes dt and timer."""
        manager = SceneManager()
        manager.dt = 0.5
        manager.timer = 10.0

        manager._reset_scene_timers()
        assert manager.dt == 0
        assert manager.timer == 0


class TestSceneManagerLogSceneSwitch:
    """Test SceneManager._log_scene_switch."""

    def test_log_scene_switch_does_not_raise(self, mock_pygame_patches, mocker):
        """Test _log_scene_switch runs without error."""
        manager = SceneManager()
        scene = mocker.Mock()
        manager._log_scene_switch(scene)  # Should not raise


class TestSceneManagerPlayDeeperCoverage:
    """Test SceneManager.play delegates to start."""

    def test_play_calls_start(self, mock_pygame_patches, mocker):
        """Test play() delegates to start()."""
        manager = SceneManager()
        manager.start = mocker.Mock()
        manager.play()
        manager.start.assert_called_once()
