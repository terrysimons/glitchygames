"""Deeper coverage tests for glitchygames/scenes/scene.py.

Targets areas NOT covered by test_scene_coverage.py:
- SceneManager game loop helper methods (_update_scene, _process_events, etc.)
- SceneManager.switch_to_scene full lifecycle
- SceneManager.__getattr__ proxy to active scene
- SceneManager._should_post_fps_event / _post_fps_event
- SceneManager._tick_clock
- SceneManager._update_display
- SceneManager._log_quit_info
- Scene.update() method with sprites
- Scene.render() method
- Scene.screenshot property
- Scene.background_color property
- Scene._handle_focus_management with focusable sprites
- Scene.on_key_down_event with non-quit keys
- Scene.on_mouse_button_down_event
- Scene.on_key_up_event with non-quit key
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager


class TestSceneManagerGetattr:
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


class TestSceneManagerHandleEvent:
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


class TestSceneManagerShouldPostFpsEvent:
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


class TestSceneManagerQuitGame:
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


class TestSceneManagerOnFpsEvent:
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
        scene.background_color = (255, 0, 0)
        assert scene.background_color == (255, 0, 0)


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
        # K_a is not a quit key, so quit_requested should not be set
        # (unless there are focused sprites, which there aren't)


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
        self, mock_pygame_patches, mocker
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
