"""Deeper coverage tests for glitchygames/scenes/scene.py.

Targets uncovered areas NOT covered by existing scene test files:
- SceneManager.switch_to_scene full lifecycle
- SceneManager._cleanup_current_scene
- SceneManager._setup_new_scene
- SceneManager._configure_active_scene and sub-methods
- SceneManager._log_blocked_events
- SceneManager._set_display_caption with NAME and VERSION
- SceneManager._configure_scene_fps
- SceneManager._log_scene_rendering_info
- SceneManager._setup_event_proxies
- SceneManager._force_scene_redraw
- SceneManager._redraw_scene_background
- SceneManager._apply_scene_fps
- SceneManager.register_game_event
- SceneManager.on_game_event (registered and unregistered)
- SceneManager.play delegates to start
- SceneManager.update_screen
- Scene.on_key_down_event with focused sprites (non-quit key)
- Scene.on_key_down_event escape key
- Scene.update with Film Strip sprite name
- Scene.on_text_submit_event
"""

import sys
from pathlib import Path

import pygame
import pytest  # noqa: F401  # used by fixtures

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.scenes import Scene, SceneManager


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
        manager.OPTIONS = manager._game_engine.OPTIONS
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
        assert scene.game_engine is manager._game_engine

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
        assert film_strip._last_dt == 0.016
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


class TestSceneManagerPlay:
    """Test SceneManager.play delegates to start."""

    def test_play_calls_start(self, mock_pygame_patches, mocker):
        """Test play() delegates to start()."""
        manager = SceneManager()
        manager.start = mocker.Mock()
        manager.play()
        manager.start.assert_called_once()
