"""Tests to increase coverage for glitchygames/scenes/scene.py.

Focuses on uncovered methods: jitter stats logging, frame pacing fallbacks,
_post_fps_event, _tick_clock ImportError handling, performance tracking,
handle_event, scene manager helpers, and event routing.
"""

import pygame
import pytest

from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.scene import JITTER_SAMPLE_BUFFER_MAX_SIZE


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
            timer=None, period_ns=0, prev_deadline_ns=None, frame_start_ns=0
        )

        mock_clock_tick.assert_called_once_with(60)

    def test_handle_frame_pacing_fallback_unlimited_fps(self, mock_pygame_patches, mocker):
        """Test frame pacing falls back to clock.tick() when no timer and target_fps is 0."""
        manager = SceneManager()
        manager.target_fps = 0

        mock_clock_tick = mocker.patch.object(manager.clock, 'tick')

        manager._handle_frame_pacing(
            timer=None, period_ns=0, prev_deadline_ns=None, frame_start_ns=0
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
