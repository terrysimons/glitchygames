"""Coverage tests for glitchygames/engine/game_engine.py.

This module targets uncovered areas of GameEngine including:
- initialize_arguments method
- suggested_resolution for different platforms
- initialize_system_icons method
- _resolve_scene_name_for_error method
- _shutdown method
- handle_event method
- initialize_display method
- print_system_info and print_game_info
- screen_width and screen_height properties
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from tests.mocks import MockFactory


class TestGameEngineInitializeArguments:
    """Test GameEngine.initialize_arguments method."""

    def test_initialize_arguments_parses_options(self, mock_pygame_patches, mocker):
        """Test initialize_arguments correctly parses command line options."""
        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '2.0'
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
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)

        # Set up a scene with a focused sprite
        mock_sprite = mocker.Mock()
        mock_sprite.active = True
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
        mock_game.args = mocker.Mock(return_value=mocker.Mock())

        engine = GameEngine(game=mock_game)
        # After initialization, EVENT_HANDLERS should have entries
        assert len(GameEngine.EVENT_HANDLERS) > 0

    def test_input_event_handlers_include_all_types(
        self, mock_pygame_patches, mock_game_args, mocker
    ):
        """Test that input event handlers cover controller, keyboard, mouse, etc."""
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = mock_game_args

        mock_game = mocker.Mock()
        mock_game.NAME = 'TestGame'
        mock_game.VERSION = '1.0'
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
