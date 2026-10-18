"""Tests for GameEngine initialization functionality.

This module tests GameEngine initialization, icon setup, argument parsing,
and class variables.
"""

import argparse
import math
import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import engine as engine_package
from glitchygames import timing
from glitchygames.bitmappy.editor import BitmapEditorScene
from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import DEFAULT_TARGET_FPS
from glitchygames.scenes import Scene
from glitchygames.timing import GIL_SWITCH_INTERVAL_SECONDS, FastTimer
from tests.mocks import MockFactory

EXPECTED_DEFAULT_TARGET_FPS = 60.5
EXPECTED_DEFAULT_PERIOD_NS = 16_528_926  # round(1e9 / 60.5)


class TestEngineInitialization:
    """Test GameEngine initialization functionality."""

    def _create_mock_args(self, mocker):
        """Create mock command line arguments.

        Returns:
            object: The result.

        """
        mock_args = mocker.Mock()
        mock_args.fps = 60
        mock_args.resolution = (800, 600)
        mock_args.windowed = True
        mock_args.use_gfxdraw = False
        mock_args.update_type = 'update'
        mock_args.fps_refresh_rate = 1
        mock_args.profile = False
        mock_args.test_flag = False
        mock_args.unknown_args = []
        return mock_args

    def test_game_engine_initialize_icon_with_surface(self, mocker):
        """Test GameEngine.initialize_icon with pygame.Surface."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = self._create_mock_args(mocker)

        # Create a mock surface using the centralized mock factory
        mock_icon = MockFactory.create_pygame_surface_mock(32, 32)

        # Mock pygame.image.load to return our mock surface
        mocker.patch('pygame.image.load', return_value=mock_icon)
        # Test the class method
        GameEngine.initialize_icon(mock_icon)

        # Verify the icon was set (it will be the result of pygame.image.load, which is our mock)
        assert GameEngine.icon == mock_icon

    def test_game_engine_initialize_icon_with_path(self, mocker):
        """Test GameEngine.initialize_icon with Path."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = self._create_mock_args(mocker)

        # Create a mock path
        mock_path = mocker.Mock()
        mock_path.__fspath__ = mocker.Mock(return_value='/path/to/icon.png')

        # Mock pygame.image.load to return a mock surface
        mock_surface = MockFactory.create_pygame_surface_mock(32, 32)
        mocker.patch('pygame.image.load', return_value=mock_surface)
        # Test the class method
        GameEngine.initialize_icon(mock_path)

        # Verify the icon was set
        assert GameEngine.icon == mock_surface

    def test_game_engine_initialize_icon_with_none(self, mocker):
        """Test GameEngine.initialize_icon with None."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = self._create_mock_args(mocker)

        # Test the class method with None
        GameEngine.initialize_icon(None)

        # Verify the icon remains unchanged (should be the default)
        assert GameEngine.icon is not None

    def test_game_engine_icon_file_not_found(self, mocker):
        """Test GameEngine.initialize_icon when file is not found."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = self._create_mock_args(mocker)

        # Create a mock path that will cause FileNotFoundError
        mock_path = mocker.Mock()
        mock_path.__fspath__ = mocker.Mock(return_value='/nonexistent/path.png')

        # Mock pygame.image.load to raise FileNotFoundError
        mocker.patch('pygame.image.load', side_effect=FileNotFoundError)
        # Test the class method - should handle FileNotFoundError gracefully
        GameEngine.initialize_icon(mock_path)

        # Verify the icon remains unchanged (should be the default)
        assert GameEngine.icon is not None

    def test_game_engine_icon_with_string_path(self, mocker):
        """Test GameEngine.initialize_icon with string path."""
        # Mock argument parsing to prevent command line argument issues
        mock_parse_args = mocker.patch('argparse.ArgumentParser.parse_args')
        mock_parse_args.return_value = self._create_mock_args(mocker)

        # Mock pygame.image.load to return a mock surface
        mock_surface = MockFactory.create_pygame_surface_mock(32, 32)
        mocker.patch('pygame.image.load', return_value=mock_surface)
        # Test the class method with string path
        GameEngine.initialize_icon('/path/to/icon.png')

        # Verify the icon was set
        assert GameEngine.icon == mock_surface

    def test_game_engine_args(self):
        """Test GameEngine.args method."""
        # Create an argument parser
        parser = argparse.ArgumentParser()

        # Test that GameEngine.args returns a parser with expected arguments
        result_parser = GameEngine.args(parser)

        # Verify parser is returned
        assert result_parser is not None
        assert result_parser == parser

        # Test parsing with known arguments
        args = result_parser.parse_args(['--log-level', 'debug', '--profile'])
        assert args.log_level == 'debug'
        assert args.profile

    def test_game_engine_class_variables(self):
        """Test GameEngine class variables."""
        # Test that class variables are properly set
        assert GameEngine.NAME == 'Boilerplate Adventures'
        assert GameEngine.VERSION == '1.0'
        assert isinstance(GameEngine.OPTIONS, dict)
        assert isinstance(GameEngine.LAST_EVENT_MISS, str)
        assert isinstance(GameEngine.MISSING_EVENTS, list)
        assert isinstance(GameEngine.UNIMPLEMENTED_EVENTS, list)
        assert isinstance(GameEngine.USE_FASTEVENTS, bool)
        assert isinstance(GameEngine.EVENT_HANDLERS, dict)

    def test_game_engine_logger(self):
        """Test GameEngine logger."""
        # Test that logger is properly configured
        assert GameEngine.log is not None
        assert GameEngine.log.name == 'game.engine'

    def test_initialize_icon_with_path(self, mocker):
        """Test GameEngine.initialize_icon with Path object."""
        # Create a mock icon file
        mock_icon_path = Path('test_icon.png')

        mock_load = mocker.patch('pygame.image.load')
        mock_surface = mocker.Mock()
        mock_load.return_value = mock_surface

        # Test with Path object
        GameEngine.initialize_icon(mock_icon_path)

        # Verify pygame.image.load was called with the path
        mock_load.assert_called_once_with(mock_icon_path)
        assert GameEngine.icon == mock_surface

    def test_initialize_icon_with_none(self):
        """Test GameEngine.initialize_icon with None."""
        original_icon = GameEngine.icon

        # Test with None (should not change icon)
        GameEngine.initialize_icon(None)

        # Verify icon was not changed
        assert GameEngine.icon == original_icon

    def test_initialize_icon_file_not_found(self, mocker):
        """Test GameEngine.initialize_icon with non-existent file."""
        mock_icon_path = Path('nonexistent_icon.png')

        mock_load = mocker.patch('pygame.image.load')
        mock_load.side_effect = FileNotFoundError()

        # Test with non-existent file (should suppress error)
        GameEngine.initialize_icon(mock_icon_path)

        # Verify pygame.image.load was called but error was suppressed
        mock_load.assert_called_once_with(mock_icon_path)

    def test_set_cursor_basic(self, mocker):
        """Test GameEngine.set_cursor with basic cursor."""
        # Use cursor data that's divisible by 8
        cursor_data = [
            '........',
            'XXXXXXXX',
            '........',
            '........',
            '........',
            '........',
            '........',
            '........',
        ]

        # Mock pygame.mouse.set_cursor to avoid video system initialization
        mock_set_cursor = mocker.patch('pygame.mouse.set_cursor')
        result = GameEngine.set_cursor(cursor_data)

        # Verify cursor was set and returned
        assert result == cursor_data
        mock_set_cursor.assert_called_once()

    def test_set_cursor_with_colors(self, mocker):
        """Test GameEngine.set_cursor with custom colors."""
        # Use cursor data that's divisible by 8
        cursor_data = [
            'BBBBBBBB',
            'WWWWWWWW',
            'OOOOOOOO',
            'BBBBBBBB',
            'WWWWWWWW',
            'OOOOOOOO',
            'BBBBBBBB',
            'WWWWWWWW',
        ]

        # Mock pygame.mouse.set_cursor to avoid video system initialization
        mock_set_cursor = mocker.patch('pygame.mouse.set_cursor')
        result = GameEngine.set_cursor(
            cursor_data,
            cursor_black='B',
            cursor_white='W',
            cursor_xor='O',
        )

        # Verify cursor was set with custom colors
        assert result == cursor_data
        mock_set_cursor.assert_called_once()

    def test_engine_options_initialization(self):
        """Test that engine options are properly initialized."""
        # Test that OPTIONS class variable exists and is a dict.
        # OPTIONS starts empty and is populated during GameEngine.__init__().
        assert hasattr(GameEngine, 'OPTIONS')
        assert isinstance(GameEngine.OPTIONS, dict)

    def test_engine_constants(self):
        """Test that engine constants are properly set."""
        # Test class constants
        assert GameEngine.NAME == 'Boilerplate Adventures'
        assert GameEngine.VERSION == '1.0'
        assert hasattr(GameEngine, 'icon')
        assert hasattr(GameEngine, 'log')

    def test_engine_missing_events_tracking(self):
        """Test missing events tracking."""
        # Test that missing events tracking exists
        assert hasattr(GameEngine, 'LAST_EVENT_MISS')
        assert hasattr(GameEngine, 'MISSING_EVENTS')
        assert hasattr(GameEngine, 'UNIMPLEMENTED_EVENTS')

        # Test that they are properly initialized
        assert isinstance(GameEngine.MISSING_EVENTS, list)
        assert isinstance(GameEngine.UNIMPLEMENTED_EVENTS, list)


class TestTargetFpsArguments:
    """Tests for the --target-fps argument and DEFAULT_TARGET_FPS."""

    def test_target_fps_defaults_to_engine_default(self):
        """Test that --target-fps is None when not passed (resolved later to 60.5)."""
        parser = GameEngine.args(argparse.ArgumentParser())

        args = parser.parse_args([])

        assert DEFAULT_TARGET_FPS == EXPECTED_DEFAULT_TARGET_FPS
        assert args.target_fps is None

    def test_engine_and_timing_share_the_same_default_target_fps(self):
        """Test that the engine re-exports the timing module's DEFAULT_TARGET_FPS."""
        assert engine_package.DEFAULT_TARGET_FPS is timing.DEFAULT_TARGET_FPS
        assert DEFAULT_TARGET_FPS is timing.DEFAULT_TARGET_FPS

    def test_target_fps_zero_means_uncapped(self):
        """Test that an explicit --target-fps 0 parses to 0.0 (uncapped)."""
        parser = GameEngine.args(argparse.ArgumentParser())

        args = parser.parse_args(['--target-fps', '0'])

        assert math.isclose(args.target_fps, 0.0, abs_tol=1e-9)

    def test_target_fps_accepts_custom_value(self):
        """Test that a custom --target-fps value parses as a float."""
        parser = GameEngine.args(argparse.ArgumentParser())

        args = parser.parse_args(['--target-fps', '144.5'])

        assert math.isclose(args.target_fps, 144.5, abs_tol=1e-9)

    def test_default_target_fps_period_in_nanoseconds(self):
        """Test that the default target yields a 16.53 ms frame period."""
        assert FastTimer().start_frame(DEFAULT_TARGET_FPS) == EXPECTED_DEFAULT_PERIOD_NS


class TestResolveTargetFps:
    """Tests for the target FPS resolution order (command line > TARGET_FPS > default)."""

    @staticmethod
    def _scene_class(target_fps):
        class _GameScene(Scene):
            TARGET_FPS = target_fps

        return _GameScene

    def test_no_command_line_and_no_game_target_uses_engine_default(self):
        result = GameEngine.resolve_target_fps(
            command_line_target_fps=None, game=self._scene_class(None)
        )
        assert math.isclose(result, DEFAULT_TARGET_FPS, abs_tol=1e-9)

    def test_game_target_of_zero_is_uncapped(self):
        result = GameEngine.resolve_target_fps(
            command_line_target_fps=None, game=self._scene_class(0.0)
        )
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_game_target_is_used_without_command_line(self):
        result = GameEngine.resolve_target_fps(
            command_line_target_fps=None, game=self._scene_class(120.0)
        )
        assert math.isclose(result, 120.0, abs_tol=1e-9)

    def test_command_line_overrides_game_target(self):
        result = GameEngine.resolve_target_fps(
            command_line_target_fps=30.0, game=self._scene_class(120.0)
        )
        assert math.isclose(result, 30.0, abs_tol=1e-9)

    def test_command_line_zero_overrides_game_target(self):
        result = GameEngine.resolve_target_fps(
            command_line_target_fps=0.0, game=self._scene_class(120.0)
        )
        assert math.isclose(result, 0.0, abs_tol=1e-9)

    def test_scene_without_target_declaration_gets_engine_default(self):
        assert Scene.TARGET_FPS is None
        result = GameEngine.resolve_target_fps(command_line_target_fps=None, game=Scene)
        assert math.isclose(result, DEFAULT_TARGET_FPS, abs_tol=1e-9)

    def test_initialize_arguments_stores_resolved_float(self, mocker):
        mocker.patch(
            'argparse.ArgumentParser.parse_args',
            return_value=argparse.Namespace(log_level='INFO', target_fps=None),
        )
        options = GameEngine.initialize_arguments(self._scene_class(120.0))
        assert math.isclose(options['target_fps'], 120.0, abs_tol=1e-9)

    def test_bitmappy_gets_engine_default(self, mocker):
        mocker.patch(
            'argparse.ArgumentParser.parse_args',
            return_value=argparse.Namespace(log_level='INFO', target_fps=None),
        )
        options = GameEngine.initialize_arguments(BitmapEditorScene)
        assert math.isclose(options['target_fps'], DEFAULT_TARGET_FPS, abs_tol=1e-9)

    @pytest.mark.parametrize('invalid_target_fps', ['120', True, False, b'60'])
    def test_non_numeric_game_target_raises_type_error(self, invalid_target_fps):
        with pytest.raises(TypeError, match='TARGET_FPS'):
            GameEngine.resolve_target_fps(
                command_line_target_fps=None, game=self._scene_class(invalid_target_fps)
            )

    @pytest.mark.parametrize('invalid_target_fps', [-1, -0.5, float('nan'), float('inf')])
    def test_out_of_range_game_target_raises_value_error(self, invalid_target_fps):
        with pytest.raises(ValueError, match='TARGET_FPS'):
            GameEngine.resolve_target_fps(
                command_line_target_fps=None, game=self._scene_class(invalid_target_fps)
            )

    @pytest.mark.parametrize('valid_target_fps', [0, 120])
    def test_valid_game_target_is_accepted(self, valid_target_fps):
        result = GameEngine.resolve_target_fps(
            command_line_target_fps=None, game=self._scene_class(valid_target_fps)
        )
        assert math.isclose(result, float(valid_target_fps), abs_tol=1e-9)

    def test_error_names_the_scene_class(self):
        with pytest.raises(TypeError, match='_GameScene'):
            GameEngine.resolve_target_fps(
                command_line_target_fps=None, game=self._scene_class('120')
            )


class TestTargetFpsArgumentValidation:
    """Tests for the --target-fps argparse type."""

    @pytest.mark.parametrize('invalid_text', ['-5', 'nan', 'inf', '-inf', 'fast'])
    def test_invalid_values_are_rejected(self, invalid_text, capsys):
        parser = GameEngine.args(argparse.ArgumentParser())
        with pytest.raises(SystemExit):
            parser.parse_args(['--target-fps', invalid_text])
        assert '--target-fps' in capsys.readouterr().err

    @pytest.mark.parametrize(('text', 'expected'), [('0', 0.0), ('60.5', 60.5)])
    def test_valid_values_are_accepted(self, text, expected):
        parser = GameEngine.args(argparse.ArgumentParser())
        args = parser.parse_args(['--target-fps', text])
        assert math.isclose(args.target_fps, expected, abs_tol=1e-9)


class TestGilSwitchInterval:
    """Tests for the GIL switch interval set during engine initialization (BUGS.md #27)."""

    def test_gil_switch_interval_is_half_a_millisecond(self):
        """Test the constant: 0.5 ms keeps audio callbacks within the 11.6 ms mixer buffer."""
        assert math.isclose(GIL_SWITCH_INTERVAL_SECONDS, 0.0005, abs_tol=1e-12)

    def test_engine_initialization_sets_switch_interval(
        self, mocker, mock_pygame_patches, mock_game_args
    ):
        """Test that GameEngine sets the interval once, before pygame.init() starts audio."""
        mocker.patch('argparse.ArgumentParser.parse_args', return_value=mock_game_args)
        set_switch_interval = mocker.patch('sys.setswitchinterval')
        mock_game = MockFactory.create_game_mock()

        GameEngine(game=mock_game)

        set_switch_interval.assert_called_once_with(GIL_SWITCH_INTERVAL_SECONDS)
