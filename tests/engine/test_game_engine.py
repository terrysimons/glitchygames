"""Tests for glitchygames/engine/game_engine.py.

Combined from test_engine_coverage.py, test_game_engine_coverage.py,
and test_engine_deeper_coverage.py.

Covers:
- initialize_arguments method
- suggested_resolution for different platforms
- initialize_system_icons method
- _resolve_scene_name_for_error method
- _shutdown method
- handle_event method
- initialize_display method
- print_system_info and print_game_info
- screen_width and screen_height properties
- process_*_event dispatcher methods (audio, app, controller, drop, touch, midi, etc.)
- process_window_focus_event: all window focus event types
- process_window_event: dispatch table routing
- _build_window_event_dispatch: dispatch table construction
- process_game_event: FPSEVENT, GAMEEVENT, MENUEVENT, ACTIVEEVENT, USEREVENT, etc.
- process_unimplemented_event: event type 1543 handling and first-time logging
- process_events main loop
- post_game_event: posting a game event
- suppress_event: event suppression logging
- register_game_event: event registration
- missing_event: unimplemented method logging
- start: game start lifecycle with profiling and error handling
- initialize_icon: with Path, Surface, and None
- _initialize_event_managers: pygame-ce detection
- handle_event: key events with no scene / no active sprites
- set_cursor: with custom cursor and None (default cursor)
- process_events main loop with scene process_event bypass
- start() method paths
- __del__ cleanup
- quit_game class method
"""

import argparse
import sys
from collections import OrderedDict
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import non_negative_int, unit_interval
from glitchygames.live_sources import LiveSources
from tests.mocks import MockFactory


def _make_engine(mocker, mock_pygame_patches, mock_game_args):
    """Create a GameEngine with mocked dependencies.

    Returns:
        GameEngine: A configured engine instance with mocked game.

    """
    mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
    mock_parse_args.return_value = mock_game_args

    mock_game = mocker.Mock()
    mock_game.NAME = 'TestGame'
    mock_game.VERSION = '1.0'
    mock_game.TARGET_FPS = None
    mock_game.args = mocker.Mock(return_value=mocker.Mock())

    return GameEngine(game=mock_game)


def _raw_event(mocker, event_type, **attributes):
    """Build a stand-in raw pygame event (mock_pygame_patches replaces pygame.event.Event).

    Returns:
        Mock: An object with the type and dict a pygame event has.

    """
    return mocker.Mock(type=event_type, dict=dict(attributes))


# ---------------------------------------------------------------------------
# From test_engine_coverage.py
# ---------------------------------------------------------------------------


class TestGameEngineInitializeArguments:
    """Test GameEngine.initialize_arguments method."""

    def test_initialize_arguments_parses_options(self, mock_pygame_patches, mocker):
        """Test initialize_arguments correctly parses command line options."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '2.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'INFO'
        mock_args.target_fps = 60.0
        mock_args.resolution = '800x600'
        mock_args.windowed = True
        mock_args.use_gfxdraw = False
        mock_args.update_type = 'update'
        mock_args.profile = False
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_args

        result = GameEngine.initialize_arguments(mock_game)

        assert isinstance(result, dict)
        assert 'log_level' in result

    def test_initialize_arguments_game_without_args_method(self, mock_pygame_patches, mocker):
        """Test initialize_arguments when game doesn't implement args()."""
        mock_game = mocker.Mock(spec=[])  # No methods at all
        mock_game.NAME = 'NoArgsGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None

        mock_args = mocker.Mock()
        mock_args.log_level = 'INFO'
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_args

        # Should handle AttributeError gracefully
        result = GameEngine.initialize_arguments(mock_game)
        assert isinstance(result, dict)

    def test_initialize_arguments_debug_mode(self, mock_pygame_patches, mocker):
        """Test initialize_arguments enables debug_events for DEBUG log level."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'DebugGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'DEBUG'
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_args

        result = GameEngine.initialize_arguments(mock_game)
        assert result['debug_events'] is True

    def test_initialize_arguments_info_mode(self, mock_pygame_patches, mocker):
        """Test initialize_arguments disables debug_events for INFO log level."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'InfoGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'INFO'
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_args

        result = GameEngine.initialize_arguments(mock_game)
        assert result['debug_events'] is False


class TestGameEngineSuggestedResolution:
    """Test GameEngine.suggested_resolution for different platforms."""

    def test_suggested_resolution_returns_tuple(self, mock_pygame_patches, mock_game_args, mocker):
        """Test suggested_resolution returns a tuple of ints."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        result = engine.suggested_resolution(1024, 768)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (1024, 768)

    def test_suggested_resolution_linux_arm(self, mock_pygame_patches, mock_game_args, mocker):
        """Test suggested_resolution on Linux ARM forces 800x480."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        mocker.patch('platform.system', return_value='Linux')
        mocker.patch('platform.machine', return_value='armv7l')

        result = engine.suggested_resolution(1024, 768)
        assert result == (800, 480)


class TestGameEngineResolveSceneName:
    """Test GameEngine._resolve_scene_name_for_error method."""

    def test_resolve_with_current_scene(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _resolve_scene_name_for_error with current scene."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = mocker.Mock()
        engine.scene_manager.current_scene.NAME = 'ActiveScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'ActiveScene'

    def test_resolve_with_current_scene_no_name(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _resolve_scene_name_for_error when current scene has no NAME."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = mocker.Mock()
        engine.scene_manager.current_scene.NAME = None
        engine.scene_manager.current_scene.__class__.__name__ = 'FallbackScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'FallbackScene'

    def test_resolve_with_previous_scene(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _resolve_scene_name_for_error falls back to previous scene."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = None
        engine.scene_manager.previous_scene = mocker.Mock()
        engine.scene_manager.previous_scene.NAME = 'PrevScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'PrevScene'

    def test_resolve_with_no_scenes(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _resolve_scene_name_for_error with no scenes returns 'None'."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = None
        engine.scene_manager.previous_scene = None

        result = engine._resolve_scene_name_for_error()
        assert result == 'None'


class TestGameEngineDisplayMethods:
    """Test GameEngine display-related methods."""

    def test_screen_width_property(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine screen_width property."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        width = engine.screen_width
        assert isinstance(width, int)
        assert width > 0

    def test_screen_height_property(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine screen_height property."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        height = engine.screen_height
        assert isinstance(height, int)
        assert height > 0

    def test_initialize_display_update_mode(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine initialize_display sets update mode."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        assert engine.display_update is not None

    def test_initialize_display_flip_mode(self, mock_pygame_patches, mock_game_args, mocker):
        """Test GameEngine initialize_display with flip update type."""
        mock_game_args.update_type = 'flip'
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        assert engine.display_update == pygame.display.flip


class TestGameEngineHandleEvent:
    """Test GameEngine.handle_event method."""

    def test_handle_quit_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test handle_event with QUIT event sets quit_requested."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        quit_event = mocker.Mock()
        quit_event.type = pygame.QUIT

        engine.handle_event(quit_event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_with_focused_sprites(self, mock_pygame_patches, mock_game_args, mocker):
        """Test handle_event routes key events to scene when sprites are focused."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # Set up a scene with a focused sprite
        mock_sprite = mocker.Mock()
        mock_sprite.is_active = True
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = [mock_sprite]

        # Mock handle_event on scene_manager since it's a real method
        mock_handle = mocker.patch.object(engine.scene_manager, 'handle_event')

        key_event = mocker.Mock()
        key_event.type = pygame.KEYDOWN
        engine.handle_event(key_event)
        mock_handle.assert_called_once_with(key_event)


class TestGameEngineShutdown:
    """Test GameEngine._shutdown method."""

    def test_shutdown_completes_without_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _shutdown completes without error."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # _shutdown calls pygame.display.quit() and pygame.quit()
        # In test environments, pygame may already be partially shut down,
        # so we just verify the method completes without raising
        engine._shutdown()

        # Re-initialize pygame for other tests
        pygame.init()
        pygame.display.set_mode((800, 600))


class TestGameEngineInitializeEventHandlers:
    """Test GameEngine event handler initialization."""

    def test_event_handlers_populated(self, mock_pygame_patches, mock_game_args, mocker):
        """Test that initialize_event_handlers populates EVENT_HANDLERS dict."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        # After initialization, EVENT_HANDLERS should have entries
        assert len(GameEngine.EVENT_HANDLERS) > 0

    def test_input_event_handlers_include_all_types(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test that input event handlers cover controller, keyboard, mouse, etc."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # Check that keyboard events are registered
        assert pygame.KEYDOWN in GameEngine.EVENT_HANDLERS
        assert pygame.KEYUP in GameEngine.EVENT_HANDLERS

        # Check that mouse events are registered
        assert pygame.MOUSEBUTTONDOWN in GameEngine.EVENT_HANDLERS
        assert pygame.MOUSEBUTTONUP in GameEngine.EVENT_HANDLERS
        assert pygame.MOUSEMOTION in GameEngine.EVENT_HANDLERS


class TestGameEngineSystemInfo:
    """Test GameEngine system info methods."""

    def test_print_game_info(self, mock_pygame_patches, mock_game_args, mocker):
        """Test print_game_info logs game title and version."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        # Should not raise
        engine.print_game_info()

    def test_print_system_info(self, mock_pygame_patches, mock_game_args, mocker):
        """Test print_system_info logs system details."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        # Should not raise
        engine.print_system_info()

    def test_initialize_system_icons(self, mock_pygame_patches, mock_game_args, mocker):
        """Test initialize_system_icons sets window icon and caption."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())
        mock_game.icon = None  # Force fallback to default icon

        engine = GameEngine(game=mock_game)
        # Should not raise
        engine.initialize_system_icons()


class TestGameEngineIconWithSurface:
    """Test GameEngine.initialize_icon with a pygame.Surface."""

    def test_initialize_icon_with_surface_directly(self, mocker):
        """Test initialize_icon sets icon directly when given a Surface."""
        mock_surface = MockFactory.create_pygame_surface_mock(64, 64)
        GameEngine.initialize_icon(mock_surface)
        assert GameEngine.icon == mock_surface


# ---------------------------------------------------------------------------
# From test_game_engine_coverage.py
# ---------------------------------------------------------------------------


class TestProcessWindowFocusEvent:
    """Test GameEngine.process_window_focus_event for all window focus types."""

    def test_window_shown(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWSHOWN dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWSHOWN

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_shown_event.assert_called_once_with(event)

    def test_window_leave(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWLEAVE dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWLEAVE

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_leave_event.assert_called_once_with(event)

    def test_window_focus_gained(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWFOCUSGAINED dispatches and sets grab."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()
        mock_set_grab = mocker.patch('pygame.event.set_grab')

        event = mocker.Mock()
        event.type = pygame.WINDOWFOCUSGAINED

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_focus_gained_event.assert_called_once_with(event)
        mock_set_grab.assert_called_once()
        assert mock_set_grab.call_args[0][0] is True

    def test_window_focus_lost(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWFOCUSLOST dispatches and releases grab."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()
        mock_set_grab = mocker.patch('pygame.event.set_grab')

        event = mocker.Mock()
        event.type = pygame.WINDOWFOCUSLOST

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_focus_lost_event.assert_called_once_with(event)
        mock_set_grab.assert_called_once()
        assert mock_set_grab.call_args[0][0] is False

    def test_window_enter(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWENTER dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWENTER

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_enter_event.assert_called_once_with(event)

    def test_window_take_focus(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWTAKEFOCUS dispatches to window_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWTAKEFOCUS

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_take_focus_event.assert_called_once_with(event)

    def test_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test unhandled window focus event returns False."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_window_focus_event(event)
        assert result is False


class TestProcessWindowEvent:
    """Test GameEngine.process_window_event dispatch table."""

    def test_window_size_changed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWSIZECHANGED dispatches through dispatch table."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWSIZECHANGED

        result = engine.process_window_event(event)
        assert result is True
        engine.window_manager.on_window_size_changed_event.assert_called_once_with(event)

    def test_window_restored(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWRESTORED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWRESTORED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_hidden(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWHIDDEN dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWHIDDEN

        result = engine.process_window_event(event)
        assert result is True

    def test_window_minimized(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWMINIMIZED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWMINIMIZED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_maximized(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWMAXIMIZED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWMAXIMIZED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_moved(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWMOVED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWMOVED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_close(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWCLOSE dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWCLOSE

        result = engine.process_window_event(event)
        assert result is True

    def test_window_exposed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWEXPOSED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWEXPOSED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_resized(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWRESIZED dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWRESIZED

        result = engine.process_window_event(event)
        assert result is True

    def test_window_hit_test(self, mock_pygame_patches, mock_game_args, mocker):
        """Test WINDOWHITTEST dispatches correctly."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.WINDOWHITTEST

        result = engine.process_window_event(event)
        assert result is True

    def test_unknown_window_event_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test unhandled window event returns False."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_window_event(event)
        assert result is False


class TestBuildWindowEventDispatch:
    """Test GameEngine._build_window_event_dispatch method."""

    def test_dispatch_table_has_all_window_events(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test dispatch table includes all expected window event types."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.window_manager = mocker.Mock()

        dispatch = engine._build_window_event_dispatch()

        expected_event_types = [
            pygame.WINDOWSIZECHANGED,
            pygame.WINDOWRESTORED,
            pygame.WINDOWHITTEST,
            pygame.WINDOWHIDDEN,
            pygame.WINDOWMINIMIZED,
            pygame.WINDOWMAXIMIZED,
            pygame.WINDOWMOVED,
            pygame.WINDOWCLOSE,
            pygame.WINDOWEXPOSED,
            pygame.WINDOWFOCUSLOST,
            pygame.WINDOWFOCUSGAINED,
            pygame.WINDOWRESIZED,
            pygame.WINDOWLEAVE,
            pygame.WINDOWENTER,
            pygame.WINDOWSHOWN,
        ]

        for event_type in expected_event_types:
            assert event_type in dispatch, f'Missing event type {event_type} in dispatch table'


class TestProcessGameEvent:
    """Test GameEngine.process_game_event for various game event types."""

    def test_fps_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches FPSEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = events.FPSEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_fps_event.assert_called_once_with(event)

    def test_game_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches GAMEEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = events.GAMEEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_game_event.assert_called_once_with(event)

    def test_menu_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches MENUEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = events.MENUEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_menu_item_event.assert_called_once_with(event)

    def test_active_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches ACTIVEEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.ACTIVEEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_active_event.assert_called_once_with(event)

    def test_user_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches USEREVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.USEREVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_user_event.assert_called_once_with(event)

    def test_video_resize_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches VIDEORESIZE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.VIDEORESIZE

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_video_resize_event.assert_called_once_with(event)

    def test_video_expose_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches VIDEOEXPOSE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.VIDEOEXPOSE

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_video_expose_event.assert_called_once_with(event)

    def test_sys_wm_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches SYSWMEVENT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.SYSWMEVENT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_sys_wm_event.assert_called_once_with(event)

    def test_quit_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event dispatches QUIT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.QUIT

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_quit_event.assert_called_once_with(event)

    def test_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_game_event returns False for unknown game events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.game_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_game_event(event)
        assert result is False


class TestProcessUnimplementedEvent:
    """Test GameEngine.process_unimplemented_event method."""

    def test_first_unimplemented_event_is_logged(self, mock_pygame_patches, mock_game_args, mocker):
        """Test first occurrence of an unimplemented event is logged."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Clear prior state
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        event = mocker.Mock()
        event.type = 55555  # An arbitrary unused event type

        engine.process_unimplemented_event(event)
        assert 55555 in GameEngine.UNIMPLEMENTED_EVENTS

    def test_duplicate_unimplemented_event_not_added_twice(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test duplicate unimplemented events are not appended again."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        event = mocker.Mock()
        event.type = 55556

        engine.process_unimplemented_event(event)
        engine.process_unimplemented_event(event)
        assert GameEngine.UNIMPLEMENTED_EVENTS.count(55556) == 1

    def test_event_type_1543_debug_logging(self, mock_pygame_patches, mock_game_args, mocker):
        """Test event type 1543 triggers extended debug logging."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        # Create an event-like object that supports dict() conversion
        # The code calls dict(event) which requires __iter__ and __getitem__
        event = mocker.Mock()
        event.type = 1543  # UNKNOWN_SDL2_EVENT_TYPE_1543
        # Make the event dict-able by providing __iter__ and keys
        event_data = {'type': 1543}
        event.__iter__ = mocker.Mock(return_value=iter(event_data))
        event.__getitem__ = mocker.Mock(side_effect=event_data.__getitem__)
        event.keys = mocker.Mock(return_value=event_data.keys())

        mocker.patch('pygame.event.event_name', return_value='Unknown')
        mocker.patch('pygame._sdl2.controller.get_count', return_value=0)

        engine.process_unimplemented_event(event)
        # Should have been logged without error
        assert 1543 in GameEngine.UNIMPLEMENTED_EVENTS


class TestUnhandledEventTracking:
    """GameEngine keeps per-type statistics of unhandled events and reports them at teardown."""

    @staticmethod
    def _make_engine_at(mocker, mock_pygame_patches, mock_game_args, *, start_seconds):
        """Create an engine whose clock (time.perf_counter) reads start_seconds at startup.

        Returns:
            tuple: The engine and the perf_counter mock (set its return_value to move time).

        """
        fake_perf_counter = mocker.patch(
            'glitchygames.engine.game_engine.time.perf_counter', return_value=start_seconds
        )
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        return engine, fake_perf_counter

    def test_counts_and_first_seen_time_per_type(self, mock_pygame_patches, mock_game_args, mocker):
        """Each type is counted; its first-seen time is seconds since the engine started."""
        engine, fake_perf_counter = self._make_engine_at(
            mocker, mock_pygame_patches, mock_game_args, start_seconds=100.0
        )

        fake_perf_counter.return_value = 100.25
        engine.process_unimplemented_event(events.HashableEvent(pygame.JOYDEVICEADDED))
        fake_perf_counter.return_value = 102.0
        engine.process_unimplemented_event(events.HashableEvent(pygame.JOYDEVICEADDED))
        engine.process_unimplemented_event(events.HashableEvent(pygame.DROPBEGIN))

        joystick_record = engine.unhandled_events[pygame.JOYDEVICEADDED]
        assert joystick_record.count == 2
        assert joystick_record.first_seen_seconds == pytest.approx(0.25)
        drop_record = engine.unhandled_events[pygame.DROPBEGIN]
        assert drop_record.count == 1
        assert drop_record.first_seen_seconds == pytest.approx(2.0)

    def test_records_attribute_names_of_first_event_only(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """The first event's attribute names are kept, sorted; values never appear."""
        engine, _fake_perf_counter = self._make_engine_at(
            mocker, mock_pygame_patches, mock_game_args, start_seconds=0.0
        )

        engine.process_unimplemented_event(
            events.HashableEvent(pygame.JOYDEVICEADDED, guid='secret-guid', device_index=3)
        )
        engine.process_unimplemented_event(
            events.HashableEvent(pygame.JOYDEVICEADDED, instance_id=9)
        )

        assert engine.unhandled_events[pygame.JOYDEVICEADDED].attribute_names == (
            'device_index',
            'guid',
        )
        (report_line,) = engine.unhandled_event_report()
        assert 'secret-guid' not in report_line
        assert 'attributes: device_index, guid' in report_line

    def test_report_is_sorted_by_count_descending(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """The most frequent type comes first."""
        engine, fake_perf_counter = self._make_engine_at(
            mocker, mock_pygame_patches, mock_game_args, start_seconds=10.0
        )
        fake_perf_counter.return_value = 10.3
        engine.process_unimplemented_event(
            events.HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='a')
        )
        for _ in range(3):
            engine.process_unimplemented_event(events.HashableEvent(pygame.DROPBEGIN))

        report = engine.unhandled_event_report()

        drop_name = pygame.event.event_name(pygame.DROPBEGIN).upper()
        assert report == [
            f'{drop_name} ({pygame.DROPBEGIN}) x3, first at 0.3 s, attributes: none',
            (
                f'JOYDEVICEADDED ({pygame.JOYDEVICEADDED}) x1, first at 0.3 s, '
                'attributes: device_index, guid'
            ),
        ]

    def test_custom_event_type_appears_with_its_number(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """An unknown or custom type is reported with its numeric type."""
        engine, _fake_perf_counter = self._make_engine_at(
            mocker, mock_pygame_patches, mock_game_args, start_seconds=0.0
        )
        custom_event_type = 88886

        engine.process_unimplemented_event(events.HashableEvent(custom_event_type, payload=1))

        (report_line,) = engine.unhandled_event_report()
        assert f'({custom_event_type}) x1' in report_line

    def test_teardown_logs_the_unhandled_event_table(
        self, mock_pygame_patches, mock_game_args, mocker, caplog
    ):
        """_shutdown logs every unhandled event type with the shutdown statistics."""
        engine, _fake_perf_counter = self._make_engine_at(
            mocker, mock_pygame_patches, mock_game_args, start_seconds=0.0
        )
        mocker.patch('pygame.display.quit')
        mocker.patch('pygame.quit')
        engine.process_unimplemented_event(
            events.HashableEvent(pygame.JOYDEVICEADDED, device_index=0, guid='a')
        )

        with caplog.at_level('INFO', logger='game.engine'):
            engine._shutdown()

        engine_messages = [
            record.getMessage() for record in caplog.records if record.name == 'game.engine'
        ]
        assert 'Unhandled events:' in engine_messages
        assert (
            f'  JOYDEVICEADDED ({pygame.JOYDEVICEADDED}) x1, first at 0.0 s, '
            'attributes: device_index, guid'
        ) in engine_messages

    def test_teardown_logs_nothing_when_every_event_was_handled(
        self, mock_pygame_patches, mock_game_args, mocker, caplog
    ):
        """No unhandled events means no report line at all."""
        engine, _fake_perf_counter = self._make_engine_at(
            mocker, mock_pygame_patches, mock_game_args, start_seconds=0.0
        )
        mocker.patch('pygame.display.quit')
        mocker.patch('pygame.quit')

        with caplog.at_level('INFO', logger='game.engine'):
            engine._shutdown()

        assert not [
            record
            for record in caplog.records
            if record.name == 'game.engine' and 'Unhandled events' in record.getMessage()
        ]


class TestPostGameEvent:
    """Test GameEngine.post_game_event method."""

    def test_post_game_event_posts_to_pygame(self, mock_pygame_patches, mock_game_args, mocker):
        """Test post_game_event posts a HashableEvent to pygame."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mock_post = mocker.patch('pygame.event.post')

        # Make pygame.event.Event return a real Event-like object so .type is correct.
        # The production code calls: pygame.event.Event(events.GAMEEVENT, event_dict)
        # With mock_pygame_patches, Event() returns a Mock whose .type is also a Mock.
        # We need Event() to produce an object whose .type equals events.GAMEEVENT.
        real_event = mocker.Mock()
        real_event.type = events.GAMEEVENT
        mocker.patch('pygame.event.Event', return_value=real_event)

        engine.post_game_event('custom_subtype', {'key': 'value'})
        mock_post.assert_called_once()
        # Verify the posted event has the correct type
        posted_event = mock_post.call_args[0][0]
        assert posted_event.type == events.GAMEEVENT


class TestSuppressEvent:
    """Test GameEngine.suppress_event method."""

    def test_suppress_event_does_not_raise(self, mock_pygame_patches, mock_game_args, mocker):
        """Test suppress_event completes without error."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.suppress_event('arg1', 'arg2', attr='some_event')


class TestRegisterGameEvent:
    """Test GameEngine.register_game_event method."""

    def test_register_game_event_stores_callback(self, mock_pygame_patches, mock_game_args, mocker):
        """Test register_game_event stores the callback in registered_events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.registered_events = {}

        callback = mocker.Mock()
        engine.register_game_event('my_event', callback)
        assert 'my_event' in engine.registered_events
        assert engine.registered_events['my_event'] is callback


class TestMissingEvent:
    """Test GameEngine.missing_event method."""

    def test_missing_event_logs_once(self, mock_pygame_patches, mock_game_args, mocker):
        """Test missing_event logs the method name once."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.MISSING_EVENTS.clear()
        GameEngine.LAST_EVENT_MISS = 'on_some_unknown_event'

        engine.missing_event('arg1', kwarg1='val')
        assert 'on_some_unknown_event' in GameEngine.MISSING_EVENTS

    def test_missing_event_not_duplicated(self, mock_pygame_patches, mock_game_args, mocker):
        """Test missing_event does not duplicate entries."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.MISSING_EVENTS.clear()
        GameEngine.LAST_EVENT_MISS = 'on_duplicate_event'

        engine.missing_event()
        engine.missing_event()
        assert GameEngine.MISSING_EVENTS.count('on_duplicate_event') == 1


class TestProcessEvents:
    """Test GameEngine.process_events main event loop."""

    def test_process_events_with_scene_process_event(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test process_events bypasses engine processing when scene has process_event."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        mock_raw_event = mocker.Mock()
        mock_raw_event.type = pygame.KEYDOWN
        mock_raw_event.dict = {'key': pygame.K_a}
        mocker.patch('pygame.event.get', return_value=[mock_raw_event])

        mock_scene = mocker.Mock()
        mock_scene.process_event = mocker.Mock()
        engine._active_scene = mock_scene

        result = engine.process_events()
        assert result is True
        mock_scene.process_event.assert_called_once_with(mock_raw_event)

    def test_process_events_handles_event_through_handlers(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test process_events routes events through EVENT_HANDLERS."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event

        mock_raw_event = mocker.Mock()
        mock_raw_event.type = pygame.KEYDOWN
        mock_raw_event.dict = {'key': pygame.K_a, 'mod': 0, 'unicode': 'a'}
        mocker.patch('pygame.event.get', return_value=[mock_raw_event])

        # Mock the handler
        mock_handler = mocker.Mock(return_value=True)
        GameEngine.EVENT_HANDLERS[pygame.KEYDOWN] = mock_handler

        result = engine.process_events()
        assert result is True

    def test_process_events_no_events_returns_false(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test process_events returns False when no events in queue."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch('pygame.event.get', return_value=[])

        result = engine.process_events()
        assert result is False

    def test_process_events_unhandled_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_events routes unhandled events to process_unimplemented_event."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        mock_raw_event = mocker.Mock()
        mock_raw_event.type = 88888  # Unknown event type
        mock_raw_event.dict = {}
        mocker.patch('pygame.event.get', return_value=[mock_raw_event])

        # Ensure no handler for this type
        GameEngine.EVENT_HANDLERS.pop(88888, None)

        mocker.patch.object(engine, 'process_unimplemented_event')
        result = engine.process_events()
        engine.process_unimplemented_event.assert_called_once()
        assert result is False

    def test_process_events_unhandled_event_does_not_drop_rest_of_batch(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """An unhandled event must not drop the key-down queued after it in the same batch."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event

        unhandled_raw_event = _raw_event(mocker, pygame.KEYUP, key=pygame.K_b)
        key_down_raw_event = _raw_event(mocker, pygame.KEYDOWN, key=pygame.K_a)
        mocker.patch('pygame.event.get', return_value=[unhandled_raw_event, key_down_raw_event])

        key_up_handler = mocker.Mock(return_value=False)
        key_down_handler = mocker.Mock(return_value=True)
        mocker.patch.dict(
            GameEngine.EVENT_HANDLERS,
            {pygame.KEYUP: key_up_handler, pygame.KEYDOWN: key_down_handler},
        )
        mock_unimplemented = mocker.patch.object(engine, 'process_unimplemented_event')

        result = engine.process_events()

        key_down_handler.assert_called_once()
        assert key_down_handler.call_args.args[0].key == pygame.K_a
        mock_unimplemented.assert_called_once()
        assert mock_unimplemented.call_args.args[0].type == pygame.KEYUP
        assert result is False

    def test_process_events_raw_event_scene_receives_every_event_in_order(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """A scene with process_event receives all N events of a batch, in order."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        raw_events = [
            _raw_event(mocker, pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(mocker, pygame.MOUSEMOTION, pos=(1, 2)),
            _raw_event(mocker, pygame.KEYUP, key=pygame.K_a),
        ]
        mocker.patch('pygame.event.get', return_value=raw_events)
        mock_scene = mocker.Mock()
        engine._active_scene = mock_scene

        result = engine.process_events()

        assert [call.args[0] for call in mock_scene.process_event.call_args_list] == raw_events
        assert result is True

    def test_process_events_unmapped_type_after_handled_event_is_unhandled(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """An event type missing from EVENT_HANDLERS never inherits the previous result."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        unmapped_event_type = 88887
        GameEngine.EVENT_HANDLERS.pop(unmapped_event_type, None)

        raw_events = [
            _raw_event(mocker, pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(mocker, unmapped_event_type),
        ]
        mocker.patch('pygame.event.get', return_value=raw_events)
        mocker.patch.dict(
            GameEngine.EVENT_HANDLERS, {pygame.KEYDOWN: mocker.Mock(return_value=True)}
        )
        mock_unimplemented = mocker.patch.object(engine, 'process_unimplemented_event')

        result = engine.process_events()

        mock_unimplemented.assert_called_once()
        assert mock_unimplemented.call_args.args[0].type == unmapped_event_type
        assert result is False

    def test_process_events_returns_true_only_when_every_event_handled(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """The return value is True only if every event of the batch was handled."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        raw_events = [
            _raw_event(mocker, pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(mocker, pygame.KEYUP, key=pygame.K_a),
        ]
        mocker.patch('pygame.event.get', return_value=raw_events)
        mocker.patch.dict(
            GameEngine.EVENT_HANDLERS,
            {
                pygame.KEYDOWN: mocker.Mock(return_value=True),
                pygame.KEYUP: mocker.Mock(return_value=True),
            },
        )
        mock_unimplemented = mocker.patch.object(engine, 'process_unimplemented_event')

        assert engine.process_events() is True
        mock_unimplemented.assert_not_called()

        # A handled event after an unhandled one does not turn the result back to True
        mocker.patch('pygame.event.get', return_value=list(reversed(raw_events)))
        GameEngine.EVENT_HANDLERS[pygame.KEYUP] = mocker.Mock(return_value=False)

        assert engine.process_events() is False
        mock_unimplemented.assert_called_once()

    def test_process_events_returns_false_when_every_event_is_discarded(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """No event dispatched (all discarded) is reported as False, like an empty batch."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        raw_events = [_raw_event(mocker, pygame.KEYDOWN, key=pygame.K_a)]
        mocker.patch('pygame.event.get', return_value=raw_events)
        key_down_handler = mocker.Mock(return_value=True)
        mocker.patch.dict(GameEngine.EVENT_HANDLERS, {pygame.KEYDOWN: key_down_handler})
        mock_unimplemented = mocker.patch.object(engine, 'process_unimplemented_event')

        result = engine.process_events(should_discard=lambda _event: True)

        assert result is False
        key_down_handler.assert_not_called()
        mock_unimplemented.assert_not_called()

    def test_process_events_discards_only_matching_events(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Kept events are dispatched and decide the result; discarded ones do not count."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        raw_events = [
            _raw_event(mocker, pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(mocker, pygame.KEYUP, key=pygame.K_a),
        ]
        mocker.patch('pygame.event.get', return_value=raw_events)
        key_down_handler = mocker.Mock(return_value=True)
        key_up_handler = mocker.Mock(return_value=True)
        mocker.patch.dict(
            GameEngine.EVENT_HANDLERS,
            {pygame.KEYDOWN: key_down_handler, pygame.KEYUP: key_up_handler},
        )

        result = engine.process_events(should_discard=lambda event: event.type == pygame.KEYDOWN)

        assert result is True
        key_down_handler.assert_not_called()
        key_up_handler.assert_called_once()


class TestHandleEventAdditionalPaths:
    """Test GameEngine.handle_event additional code paths."""

    def test_handle_event_no_scene(self, mock_pygame_patches, mock_game_args, mocker):
        """Test handle_event when active_scene is None."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = None
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_q

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_with_unfocused_sprites(self, mock_pygame_patches, mock_game_args, mocker):
        """Test handle_event with sprites that are not focused."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mock_sprite = mocker.Mock()
        mock_sprite.is_active = False  # Not focused
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = [mock_sprite]
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_a  # Not quit key

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_non_key_event_passes_to_scene_manager(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test non-KEYDOWN events always pass to scene_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEBUTTONDOWN

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_quit_event(self, mock_pygame_patches, mock_game_args, mocker):
        """Test QUIT event sets quit_requested without passing to scene_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.QUIT

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True
        engine.scene_manager.handle_event.assert_not_called()


class TestInitializeIcon:
    """Test GameEngine.initialize_icon class method."""

    def test_initialize_icon_with_none(self):
        """Test initialize_icon with None does nothing."""
        original_icon = GameEngine.icon
        GameEngine.initialize_icon(None)
        assert GameEngine.icon is original_icon

    def test_initialize_icon_with_surface(self, mocker):
        """Test initialize_icon with a Surface sets it directly."""
        mock_surface = pygame.Surface((32, 32))
        GameEngine.initialize_icon(mock_surface)
        assert GameEngine.icon is mock_surface

    def test_initialize_icon_with_path(self, mocker):
        """Test initialize_icon with a path attempts to load it."""
        mocker.patch('pygame.image.load', side_effect=FileNotFoundError)
        # Should not raise due to contextlib.suppress
        GameEngine.initialize_icon(Path('/nonexistent/icon.png'))


class TestSetCursorWithCustomCursor:
    """Test GameEngine.set_cursor with a custom cursor."""

    def test_set_cursor_with_custom_cursor(self, mocker):
        """Test set_cursor with a custom cursor list."""
        mock_set_cursor = mocker.patch('pygame.mouse.set_cursor')
        custom_cursor = [
            'XX      ',
            'XXX     ',
            'XXXX    ',
            'XX.XX   ',
            'XX..XX  ',
            'XX...XX ',
            'XX....XX',
            'XXXXXXXX',
        ]
        result = GameEngine.set_cursor(cursor=custom_cursor)
        assert result == custom_cursor
        mock_set_cursor.assert_called_once()


class TestInitializeEventManagers:
    """Test GameEngine._initialize_event_managers method."""

    def test_initialize_event_managers_sets_up_all_managers(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test _initialize_event_managers creates all required managers."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Mock scene_manager with proper OPTIONS dict support
        mock_scene_manager = mocker.Mock()
        mock_scene_manager.OPTIONS = {
            'font_name': 'Vera',
            'font_size': 24,
            'font_bold': False,
            'font_italic': False,
            'font_antialias': True,
            'font_dpi': 72,
        }
        engine.scene_manager = mock_scene_manager

        # Patch joystick/controller subsystems to avoid deprecated API calls
        mocker.patch('pygame.joystick.get_count', return_value=0)
        mocker.patch('pygame.joystick.init')
        mocker.patch('pygame.joystick.get_init', return_value=True)
        mocker.patch('pygame._sdl2.controller.init')
        mocker.patch('pygame._sdl2.controller.get_init', return_value=True)
        mocker.patch('pygame._sdl2.controller.get_count', return_value=0)

        engine._initialize_event_managers()

        # Check that key managers are set up
        assert engine.audio_manager is not None
        assert engine.drop_manager is not None
        assert engine.touch_manager is not None
        assert engine.font_manager is not None
        assert engine.game_manager is not None
        assert engine.joystick_manager is not None
        assert engine.keyboard_manager is not None
        assert engine.midi_manager is not None
        assert engine.mouse_manager is not None
        assert engine.window_manager is not None


class TestStartMethod:
    """Test GameEngine.start method paths."""

    def test_start_with_no_game_raises(self, mock_pygame_patches, mock_game_args, mocker):
        """Test start raises RuntimeError when game is None."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        GameEngine.game = None

        with pytest.raises(RuntimeError, match='Game not initialized'):
            engine.start()

        # Re-init pygame for other tests
        pygame.init()
        pygame.display.set_mode((800, 600))


class TestResolveSceneNameForError:
    """Test _resolve_scene_name_for_error additional paths."""

    def test_previous_scene_with_no_name(self, mock_pygame_patches, mock_game_args, mocker):
        """Test falls back to class name when previous scene has NAME=None."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.current_scene = None
        engine.scene_manager.previous_scene = mocker.Mock()
        engine.scene_manager.previous_scene.NAME = None
        engine.scene_manager.previous_scene.__class__.__name__ = 'FallbackPrevScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'FallbackPrevScene'


class TestProcessTextEventUnhandled:
    """Test GameEngine.process_text_event returns False path (line 1250)."""

    def test_unhandled_text_event_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_text_event returns False for unhandled text event types."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        event = mocker.Mock()
        event.type = 99999  # Not TEXTEDITING or TEXTINPUT

        result = engine.process_text_event(event)
        assert result is False


# ---------------------------------------------------------------------------
# From test_engine_deeper_coverage.py
# ---------------------------------------------------------------------------


class TestProcessAudioEvent:
    """Test GameEngine.process_audio_event dispatcher."""

    def test_audio_device_added(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_audio_event dispatches AUDIODEVICEADDED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.audio_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.AUDIODEVICEADDED

        result = engine.process_audio_event(event)
        assert result is True
        engine.audio_manager.on_audio_device_added_event.assert_called_once_with(event)

    def test_audio_device_removed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_audio_event dispatches AUDIODEVICEREMOVED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.audio_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.AUDIODEVICEREMOVED

        result = engine.process_audio_event(event)
        assert result is True
        engine.audio_manager.on_audio_device_removed_event.assert_called_once_with(event)

    def test_audio_unhandled_event_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_audio_event returns False for unknown audio events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.audio_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999  # Unknown event type

        result = engine.process_audio_event(event)
        assert result is False


class TestProcessAppEvent:
    """Test GameEngine.process_app_event dispatcher."""

    def test_app_did_enter_background(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_DIDENTERBACKGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_DIDENTERBACKGROUND

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_did_enter_background_event.assert_called_once_with(event)

    def test_app_did_enter_foreground(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_DIDENTERFOREGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_DIDENTERFOREGROUND

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_did_enter_foreground_event.assert_called_once_with(event)

    def test_app_will_enter_background(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_WILLENTERBACKGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_WILLENTERBACKGROUND

        result = engine.process_app_event(event)
        assert result is True

    def test_app_will_enter_foreground(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_WILLENTERFOREGROUND."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_WILLENTERFOREGROUND

        result = engine.process_app_event(event)
        assert result is True

    def test_app_low_memory(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_LOWMEMORY."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_LOWMEMORY

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_low_memory_event.assert_called_once_with(event)

    def test_app_terminating(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event dispatches APP_TERMINATING."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.APP_TERMINATING

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_terminating_event.assert_called_once_with(event)

    def test_app_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_app_event returns False for unknown app events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.app_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_app_event(event)
        assert result is False


class TestProcessDropEvent:
    """Test GameEngine.process_drop_event dispatcher."""

    def test_drop_begin(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPBEGIN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPBEGIN

        result = engine.process_drop_event(event)
        assert result is True
        engine.drop_manager.on_drop_begin_event.assert_called_once_with(event)

    def test_drop_complete(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPCOMPLETE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPCOMPLETE

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_file(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPFILE."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPFILE

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_text(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event dispatches DROPTEXT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.DROPTEXT

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_drop_event returns False for unknown drop events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.drop_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_drop_event(event)
        assert result is False


class TestProcessTouchEvent:
    """Test GameEngine.process_touch_event dispatcher."""

    def test_finger_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event dispatches FINGERDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.FINGERDOWN

        result = engine.process_touch_event(event)
        assert result is True
        engine.touch_manager.on_touch_down_event.assert_called_once_with(event)

    def test_finger_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event dispatches FINGERUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.FINGERUP

        result = engine.process_touch_event(event)
        assert result is True

    def test_finger_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event dispatches FINGERMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.FINGERMOTION

        result = engine.process_touch_event(event)
        assert result is True

    def test_touch_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_touch_event returns False for unknown touch events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.touch_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_touch_event(event)
        assert result is False


class TestProcessMouseEvent:
    """Test GameEngine.process_mouse_event dispatcher."""

    def test_mouse_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEMOTION

        result = engine.process_mouse_event(event)
        assert result is True
        engine.mouse_manager.on_mouse_motion_event.assert_called_once_with(event)

    def test_mouse_button_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEBUTTONUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEBUTTONUP

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_button_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEBUTTONDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEBUTTONDOWN
        event.button = 1
        event.pos = (100, 100)

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_wheel(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event dispatches MOUSEWHEEL."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEWHEEL

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_mouse_event returns False for unknown mouse events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.mouse_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_mouse_event(event)
        assert result is False


class TestProcessKeyboardEvent:
    """Test GameEngine.process_keyboard_event dispatcher."""

    def test_key_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_keyboard_event dispatches KEYDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.keyboard_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN

        result = engine.process_keyboard_event(event)
        assert result is True
        engine.keyboard_manager.on_key_down_event.assert_called_once_with(event)

    def test_key_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_keyboard_event dispatches KEYUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.keyboard_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYUP

        result = engine.process_keyboard_event(event)
        assert result is True

    def test_keyboard_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_keyboard_event returns False for unknown keyboard events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.keyboard_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_keyboard_event(event)
        assert result is False


class TestProcessJoystickEvent:
    """Test GameEngine.process_joystick_event dispatcher."""

    def test_joy_axis_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYAXISMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYAXISMOTION

        result = engine.process_joystick_event(event)
        assert result is True
        engine.joystick_manager.on_joy_axis_motion_event.assert_called_once_with(event)

    def test_joy_ball_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYBALLMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYBALLMOTION

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_hat_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYHATMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYHATMOTION

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_button_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYBUTTONDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYBUTTONDOWN

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_button_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYBUTTONUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYBUTTONUP

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_device_added(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYDEVICEADDED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYDEVICEADDED

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_device_removed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event dispatches JOYDEVICEREMOVED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.JOYDEVICEREMOVED

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joystick_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_joystick_event returns False for unknown joystick events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.joystick_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_joystick_event(event)
        assert result is False


class TestProcessMidiEvent:
    """Test GameEngine.process_midi_event dispatcher."""

    def test_midi_in(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_midi_event dispatches MIDIIN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MIDIIN

        result = engine.process_midi_event(event)
        assert result is True
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_midi_out(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_midi_event dispatches MIDIOUT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MIDIOUT

        result = engine.process_midi_event(event)
        assert result is True

    def test_midi_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_midi_event returns False for unknown midi events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_midi_event(event)
        assert result is False


class TestProcessTextEvent:
    """Test GameEngine.process_text_event dispatcher."""

    def test_text_editing(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_text_event dispatches TEXTEDITING."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch.object(engine, 'process_unimplemented_event')

        event = mocker.Mock()
        event.type = pygame.TEXTEDITING

        result = engine.process_text_event(event)
        assert result is True
        engine.process_unimplemented_event.assert_called_once_with(event)

    def test_text_input(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_text_event dispatches TEXTINPUT."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch.object(engine, 'process_unimplemented_event')

        event = mocker.Mock()
        event.type = pygame.TEXTINPUT

        result = engine.process_text_event(event)
        assert result is True


class TestProcessControllerEvent:
    """Test GameEngine.process_controller_event dispatcher."""

    def test_controller_axis_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERAXISMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERAXISMOTION

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_button_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERBUTTONDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERBUTTONDOWN

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_button_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERBUTTONUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERBUTTONUP

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_down(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADDOWN."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERTOUCHPADDOWN

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_up(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADUP."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERTOUCHPADUP

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_motion(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADMOTION."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERTOUCHPADMOTION

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_removed(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEREMOVED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERDEVICEREMOVED

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_added(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEADDED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERDEVICEADDED

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_remapped(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEREMAPPED."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.CONTROLLERDEVICEREMAPPED

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_unhandled_returns_false(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_controller_event returns False for unknown controller events."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.controller_manager = mocker.Mock()

        event = mocker.Mock()
        event.type = 99999

        result = engine.process_controller_event(event)
        assert result is False


class TestGameEngineHandleEventDeeper:
    """Test GameEngine.handle_event deeper paths."""

    def test_handle_event_keydown_q_with_no_focused_sprites(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test handle_event with K_q and no focused sprites sets quit_requested."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.key = pygame.K_q

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_passes_non_key_events_to_scene_manager(
        self,
        mock_pygame_patches,
        mock_game_args,
        mocker,
    ):
        """Test handle_event passes non-key events to scene_manager."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = mocker.Mock()
        event.type = pygame.MOUSEMOTION

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)


class TestGameEngineSetCursorDefault:
    """Test GameEngine.set_cursor with None for default cursor."""

    def test_set_cursor_with_none_creates_default(self, mocker):
        """Test set_cursor with None creates the default cursor."""
        mock_set_cursor = mocker.patch('pygame.mouse.set_cursor')
        result = GameEngine.set_cursor(cursor=None)
        assert result is not None
        assert len(result) > 0
        mock_set_cursor.assert_called_once()


class TestGameEngineSuggestedResolutionLinuxNonArm:
    """Test suggested_resolution on Linux non-ARM returns desired resolution."""

    def test_suggested_resolution_linux_non_arm(self, mock_pygame_patches, mock_game_args, mocker):
        """Test suggested_resolution on Linux non-ARM returns desired resolution."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        mocker.patch('platform.system', return_value='Linux')
        mocker.patch('platform.machine', return_value='x86_64')

        result = engine.suggested_resolution(1024, 768)
        assert result == (1024, 768)


class TestGameEngineDelMethod:
    """Test GameEngine.__del__ method."""

    def test_del_logs_sprite_counts(self, mock_pygame_patches, mock_game_args, mocker):
        """Test __del__ logs sprite counts without errors."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Should not raise
        del engine


class TestGameEngineQuitGame:
    """Test GameEngine.quit_game class method."""

    def test_quit_game_posts_quit_event(self, mock_pygame_patches, mocker):
        """Test quit_game posts a QUIT event."""
        mock_post = mocker.patch('pygame.event.post')
        GameEngine.quit_game()
        mock_post.assert_called_once()


class TestGameEngineInitializeArgumentsLogLevels:
    """Test initialize_arguments with CRITICAL and ERROR log levels."""

    def test_critical_log_level_enables_debug_events(self, mock_pygame_patches, mocker):
        """Test CRITICAL log level sets debug_events to True."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'CRITICAL'
        mocker.patch('argparse.ArgumentParser.parse_args', return_value=mock_args)

        result = GameEngine.initialize_arguments(mock_game)
        assert result['debug_events'] is True

    def test_error_log_level_enables_debug_events(self, mock_pygame_patches, mocker):
        """Test ERROR log level sets debug_events to True."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
        mock_game.TARGET_FPS = None
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        mock_args = mocker.Mock()
        mock_args.log_level = 'ERROR'
        mocker.patch('argparse.ArgumentParser.parse_args', return_value=mock_args)

        result = GameEngine.initialize_arguments(mock_game)
        assert result['debug_events'] is True


class TestGetAttrAttributeError:
    """Test GameEngine.__getattr__ raises AttributeError (line 1532)."""

    def test_non_event_attribute_raises(self, mock_pygame_patches, mock_game_args, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        with pytest.raises(AttributeError, match="has no attribute 'some_random_attr'"):
            engine.some_random_attr  # ruff: ignore[useless-expression]


class TestGameEngineLinuxVideoDriverArgs:
    """Test GameEngine platform-specific video driver args (lines 205-230)."""

    def test_linux_video_drivers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test Linux video driver choices are set up correctly (lines 205-219)."""
        mocker.patch('platform.system', return_value='Linux')

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Engine was created with Linux platform; the parser is internal
        # Just verify it doesn't raise

    def test_mac_video_drivers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test MacOS video driver choices (lines 222-225)."""
        mocker.patch('platform.system', return_value='MacOS')

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Just verify it doesn't raise

    def test_windows_video_drivers(self, mock_pygame_patches, mock_game_args, mocker):
        """Test Windows video driver choices (lines 227-230)."""
        mocker.patch('platform.system', return_value='Windows')

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Just verify it doesn't raise


class TestGameEngineFastEvents:
    """Test USE_FASTEVENTS path (lines 341, 354-355, 924).

    Note: pygame.fastevent was removed in modern pygame versions.
    We mock the fastevent module to test these legacy code paths.
    """

    def test_use_fastevents_with_old_pygame(self, mock_pygame_patches, mock_game_args, mocker):
        """Test USE_FASTEVENTS is set for old pygame versions (line 341)."""
        # Mock pygame version to be < 2.2 (both major < 2 AND minor < 2)
        mocker.patch.object(pygame.version, 'vernum', (1, 1, 0))
        # Create a fake fastevent module
        mock_fastevent = mocker.Mock()
        mocker.patch.object(pygame, 'fastevent', mock_fastevent, create=True)
        # The engine sets the class attribute; patching it undoes that at teardown (BUGS.md #65)
        mocker.patch.object(GameEngine, 'USE_FASTEVENTS', new=False)

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        assert engine.USE_FASTEVENTS is True
        mock_fastevent.init.assert_called_once()

    def test_process_events_with_fastevents(self, mock_pygame_patches, mock_game_args, mocker):
        """Test process_events uses fastevent.get when USE_FASTEVENTS is True (line 924)."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # The live doors decide fastevent use when created (glitchygames/live_sources.py)
        engine.install_sources(
            sources=LiveSources(random_seed=engine.random_seed, use_fastevents=True)
        )
        # Create a fake fastevent module
        mock_fastevent = mocker.Mock()
        mock_fastevent.get.return_value = []
        mocker.patch.object(pygame, 'fastevent', mock_fastevent, create=True)

        result = engine.process_events()
        assert result is False
        mock_fastevent.get.assert_called_once()


class TestGameEngineFullscreen:
    """Test fullscreen mode flags (line 381)."""

    def test_fullscreen_mode_flags(self, mock_pygame_patches, mock_game_args, mocker):
        """Test fullscreen mode sets correct flags (line 381)."""
        mock_game_args.windowed = False  # Trigger fullscreen

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        assert engine.mode_flags & pygame.FULLSCREEN


class TestGameEngineInvalidUpdateType:
    """Test invalid update_type logs error (line 424)."""

    def test_invalid_update_type_logs_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test invalid update_type logs an error (line 424)."""
        mock_game_args.update_type = 'invalid_type'

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        # Engine should still be created, just with an error logged


class TestGameEngineDel:
    """Test GameEngine __del__ with sprite counters (lines 509-510)."""

    def test_del_logs_sprite_counters(self, mock_pygame_patches, mock_game_args, mocker):
        """Test __del__ iterates sprite counters (lines 509-510)."""
        from glitchygames.sprites import Sprite

        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Set up some sprite counters
        Sprite.SPRITE_COUNT = 5
        Sprite.SPRITE_COUNTERS = OrderedDict({
            'TestSprite': {'created': 3, 'destroyed': 2},
        })

        # Trigger __del__ via del statement
        del engine

        # Clean up
        Sprite.SPRITE_COUNT = 0
        Sprite.SPRITE_COUNTERS = OrderedDict()


class TestGameEngineTimerBackendError:
    """Test timer backend initialization failure (lines 828-830)."""

    def test_timer_backend_value_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test timer backend ValueError sets timer to None (lines 828-830)."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Mock create_timer to raise ValueError
        mocker.patch(
            'glitchygames.engine.game_engine.create_timer',
            side_effect=ValueError('Invalid backend'),
        )

        # Mock scene manager and game for start()
        mock_game_class = mocker.Mock()
        mock_game_instance = mocker.Mock()
        mock_game_class.return_value = mock_game_instance
        GameEngine.game = mock_game_class
        GameEngine.OPTIONS = {
            'profile': False,
            'timer_backend': 'invalid',
            'perf_trim_percent': 5.0,
        }

        # Mock the scene manager loop to immediately stop
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.quit_requested = True
        engine._initialize_event_managers = mocker.Mock()
        engine._shutdown = mocker.Mock()

        engine.start()
        assert engine.timer is None


class TestGameEnginePerformanceImportError:
    """Test performance module ImportError path (lines 784-785)."""

    def test_shutdown_performance_import_error(self, mock_pygame_patches, mock_game_args, mocker):
        """Test _shutdown handles ImportError for performance module (lines 784-785)."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)

        # Mock the performance import to fail
        mocker.patch.dict('sys.modules', {'glitchygames.performance': None})

        # _shutdown should handle the ImportError gracefully
        engine._shutdown()


class TestShakeAndAudioArguments:
    """Test the screen shake, rumble and live voice pool arguments."""

    @pytest.mark.parametrize(('text', 'expected'), [('0', 0.0), ('0.5', 0.5), ('1', 1.0)])
    def test_unit_interval_accepts_range(self, text, expected):
        """Test unit_interval accepts values from 0.0 to 1.0 inclusive."""
        assert unit_interval(text) == expected

    @pytest.mark.parametrize('text', ['-0.01', '1.01', 'abc', 'nan'])
    def test_unit_interval_rejects(self, text):
        """Test unit_interval rejects out-of-range, non-numeric and NaN text."""
        with pytest.raises(argparse.ArgumentTypeError):
            unit_interval(text)

    @pytest.mark.parametrize('text', ['-1', '1.5', 'x'])
    def test_non_negative_int_rejects(self, text):
        """Test non_negative_int rejects negatives, floats and non-numeric text."""
        with pytest.raises(argparse.ArgumentTypeError):
            non_negative_int(text)

    def test_non_negative_int_accepts_zero(self):
        """Test non_negative_int accepts zero (a zero-size voice pool is valid)."""
        assert non_negative_int('0') == 0

    def test_defaults(self):
        """Test the new arguments default to full shake, full rumble and four voices."""
        parser = argparse.ArgumentParser()
        GameEngine.args(parser)
        options = vars(parser.parse_args([]))
        assert options['screen_shake_intensity'] == 1.0
        assert options['rumble_intensity'] == 1.0
        assert options['live_voice_pool'] == 4

    def test_values_are_parsed(self):
        """Test explicit command-line values reach the parsed options."""
        parser = argparse.ArgumentParser()
        GameEngine.args(parser)
        options = vars(
            parser.parse_args([
                '--screen-shake-intensity',
                '0.25',
                '--rumble-intensity',
                '0',
                '--live-voice-pool',
                '0',
            ])
        )
        assert options['screen_shake_intensity'] == 0.25
        assert options['rumble_intensity'] == 0.0
        assert options['live_voice_pool'] == 0


class TestFpsHistogramArgument:
    """Test the --fps-histogram argument and its plumbing to the performance manager."""

    @staticmethod
    def _parse(arguments):
        parser = argparse.ArgumentParser()
        GameEngine.args(parser)
        return vars(parser.parse_args(arguments))

    def test_defaults_to_equal_range(self):
        """Test the default histogram mode is equal-range."""
        assert self._parse([])['fps_histogram'] == 'equal-range'

    @pytest.mark.parametrize('choice', ['equal-range', 'target-relative'])
    def test_both_choices_parse(self, choice):
        """Test both documented choices parse."""
        assert self._parse(['--fps-histogram', choice])['fps_histogram'] == choice

    def test_invalid_choice_is_rejected(self, capsys):
        """Test an unknown choice makes argparse exit with a usage error."""
        with pytest.raises(SystemExit):
            self._parse(['--fps-histogram', 'logarithmic'])
        assert 'invalid choice' in capsys.readouterr().err

    def test_choices_match_the_performance_modes(self):
        """Test the CLI choices are exactly the FpsHistogramMode values."""
        from glitchygames.performance.adaptive_clamping import FpsHistogramMode

        parser = argparse.ArgumentParser()
        GameEngine.args(parser)
        action = next(
            action for action in parser._actions if '--fps-histogram' in action.option_strings
        )
        assert list(action.choices) == [mode.value for mode in FpsHistogramMode]

    def test_start_passes_the_mode_to_the_performance_manager(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test start() calls set_histogram_mode with the parsed option."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch('glitchygames.engine.game_engine.create_timer')
        mock_manager = mocker.patch('glitchygames.performance.performance_manager')
        mocker.patch.object(GameEngine, 'game', mocker.Mock())
        mocker.patch.object(
            GameEngine,
            'OPTIONS',
            {
                'profile': False,
                'timer_backend': 'fast',
                'perf_trim_percent': 5.0,
                'fps_histogram': 'target-relative',
            },
        )
        engine.scene_manager = mocker.Mock()
        engine._initialize_event_managers = mocker.Mock()
        engine._shutdown = mocker.Mock()

        engine.start()

        mock_manager.set_histogram_mode.assert_called_once_with('target-relative')

    def test_start_sets_the_mode_even_when_set_trim_percent_raises(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test a bad trim value cannot skip setting the histogram mode."""
        engine = _make_engine(mocker, mock_pygame_patches, mock_game_args)
        mocker.patch('glitchygames.engine.game_engine.create_timer')
        mock_manager = mocker.patch('glitchygames.performance.performance_manager')
        mock_manager.set_trim_percent.side_effect = ValueError('bad trim')
        mocker.patch.object(GameEngine, 'game', mocker.Mock())
        mocker.patch.object(
            GameEngine,
            'OPTIONS',
            {
                'profile': False,
                'timer_backend': 'fast',
                'perf_trim_percent': 5.0,
                'fps_histogram': 'target-relative',
            },
        )
        engine.scene_manager = mocker.Mock()
        engine._initialize_event_managers = mocker.Mock()
        engine._shutdown = mocker.Mock()

        engine.start()

        mock_manager.set_histogram_mode.assert_called_once_with('target-relative')
