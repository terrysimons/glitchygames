"""Tests to increase coverage for glitchygames/scenes/scene.py.

Focuses on uncovered methods: property accessors, scene lifecycle,
event handler stubs, focus management, and helper methods.
"""

import pygame

from glitchygames.scenes import Scene, SceneManager


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
        # Should not raise


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
