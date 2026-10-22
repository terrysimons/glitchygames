"""Tests for GameEngine initialization functionality.

This module tests GameEngine initialization, icon setup, argument parsing,
and class variables.
"""

import argparse
import math
import os
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.record_golden_traces import GoldenTraceEngine

from glitchygames import engine as engine_package
from glitchygames import timing
from glitchygames.bitmappy.editor import BitmapEditorScene
from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import DEFAULT_TARGET_FPS
from glitchygames.exit_codes import ExitCode
from glitchygames.scenes import Scene
from glitchygames.timing import GIL_SWITCH_INTERVAL_SECONDS, FastTimer

EXPECTED_DEFAULT_TARGET_FPS = 60.01
EXPECTED_DEFAULT_PERIOD_NS = 16_663_889  # round(1e9 / 60.01)

# Icons the tests save and load
ICON_SIZE = (32, 32)
ICON_COLOR = (200, 40, 120)
OTHER_ICON_COLOR = (10, 220, 30)

# GameEngine.set_cursor's default arrow is 24x24
DEFAULT_CURSOR_SIZE = 24

# GameEngine parses sys.argv when it is constructed: a small window (the conftest puts the
# 800x600 test display back after the test), no frame pacing, quiet logs
ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')


class InitializationTestGame(Scene):
    """The game scene the engine here is built with."""

    NAME = 'InitializationTestGame'
    VERSION = '1.0'


def assert_active_cursor(cursor: list[str], *, black: str, white: str, xor: str) -> None:
    """Assert the display's cursor is ``cursor`` compiled with these characters, hotspot 0,0."""
    cursor_data, cursor_mask = pygame.cursors.compile(cursor, black=black, white=white, xor=xor)
    size, hotspot, active_data, active_mask = pygame.mouse.get_cursor().data
    assert size == (len(cursor[0]), len(cursor))
    assert hotspot == (0, 0)
    assert active_data == tuple(cursor_data)
    assert active_mask == tuple(cursor_mask)


def save_icon_file(directory: Path, *, color: tuple[int, int, int]) -> Path:
    """Save a real ICON_SIZE PNG filled with ``color`` in ``directory``.

    Returns:
        Path: The file.

    """
    icon_surface = pygame.Surface(ICON_SIZE)
    icon_surface.fill(color)
    icon_path = directory / 'icon.png'
    pygame.image.save(icon_surface, icon_path)
    return icon_path


def surface_rgb(surface: pygame.Surface) -> set[tuple[int, int, int]]:
    """Return the distinct RGB colors of a surface (alpha left out: formats differ).

    Returns:
        set[tuple[int, int, int]]: The colors.

    """
    pixels = pygame.surfarray.array3d(surface)
    return {tuple(int(channel) for channel in color) for color in pixels.reshape(-1, 3).tolist()}


class TestEngineInitialization:
    """Test GameEngine initialization functionality."""

    def test_game_engine_initialize_icon_with_surface(self):
        """A pygame.Surface icon is used as is."""
        icon_surface = pygame.Surface(ICON_SIZE)
        icon_surface.fill(ICON_COLOR)

        GameEngine.initialize_icon(icon_surface)

        assert GameEngine.icon is icon_surface

    def test_game_engine_initialize_icon_with_path(self, tmp_path):
        """A Path icon is loaded from the image file."""
        icon_path = save_icon_file(tmp_path, color=ICON_COLOR)

        GameEngine.initialize_icon(icon_path)

        assert isinstance(GameEngine.icon, pygame.Surface)
        assert GameEngine.icon.get_size() == ICON_SIZE
        assert surface_rgb(GameEngine.icon) == {ICON_COLOR}

    def test_game_engine_initialize_icon_with_none(self):
        """None leaves the default icon in place."""
        default_icon = GameEngine.icon

        GameEngine.initialize_icon(None)

        assert GameEngine.icon is default_icon
        assert isinstance(GameEngine.icon, pygame.Surface)

    def test_game_engine_icon_file_not_found(self, tmp_path):
        """A missing icon file is ignored: the default icon stays."""
        default_icon = GameEngine.icon

        GameEngine.initialize_icon(tmp_path / 'nonexistent.png')

        assert GameEngine.icon is default_icon

    def test_game_engine_icon_with_string_path(self, tmp_path):
        """A str icon is a path, loaded like a Path."""
        icon_path = save_icon_file(tmp_path, color=ICON_COLOR)

        GameEngine.initialize_icon(str(icon_path))

        assert GameEngine.icon.get_size() == ICON_SIZE
        assert surface_rgb(GameEngine.icon) == {ICON_COLOR}

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

    def test_initialize_icon_with_path(self, tmp_path):
        """A Path icon replaces the previous icon with the loaded image."""
        default_icon = GameEngine.icon
        icon_path = save_icon_file(tmp_path, color=OTHER_ICON_COLOR)

        GameEngine.initialize_icon(icon_path)

        assert GameEngine.icon is not default_icon
        assert surface_rgb(GameEngine.icon) == {OTHER_ICON_COLOR}

    def test_initialize_icon_with_none(self):
        """Test GameEngine.initialize_icon with None."""
        original_icon = GameEngine.icon

        # Test with None (should not change icon)
        GameEngine.initialize_icon(None)

        # Verify icon was not changed
        assert GameEngine.icon == original_icon

    def test_initialize_icon_file_not_found(self, tmp_path):
        """A missing icon file after a loaded one keeps the loaded one (the error is ignored)."""
        GameEngine.initialize_icon(save_icon_file(tmp_path, color=ICON_COLOR))
        loaded_icon = GameEngine.icon

        GameEngine.initialize_icon(Path(tmp_path / 'nonexistent_icon.png'))

        assert GameEngine.icon is loaded_icon

    def test_set_cursor_basic(self):
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

        result = GameEngine.set_cursor(cursor_data)

        # The cursor is returned and is the display's cursor now
        assert result == cursor_data
        assert_active_cursor(cursor_data, black='.', white='X', xor='o')

    def test_set_cursor_with_colors(self):
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

        result = GameEngine.set_cursor(
            cursor_data,
            cursor_black='B',
            cursor_white='W',
            cursor_xor='O',
        )

        # The cursor, compiled with the custom characters, is the display's cursor now
        assert result == cursor_data
        assert_active_cursor(cursor_data, black='B', white='W', xor='O')

    def test_set_cursor_default(self):
        """No cursor sets and returns the engine's 24x24 default arrow."""
        result = GameEngine.set_cursor(None)

        assert len(result) == len(result[0]) == DEFAULT_CURSOR_SIZE
        assert_active_cursor(result, black='.', white='X', xor='o')

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
        """Test that --target-fps is None when not passed (resolved later to 60.01)."""
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
        """Test that the default target yields a 16.664 ms frame period."""
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
        with pytest.raises(SystemExit) as exit_info:
            parser.parse_args(['--target-fps', invalid_text])
        assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
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

    def test_engine_initialization_sets_switch_interval(self, mocker):
        """GameEngine sets the interval before pygame.init() starts audio."""
        sys.setswitchinterval(GIL_SWITCH_INTERVAL_SECONDS * 10)
        intervals_at_pygame_init: list[float] = []
        real_pygame_init = pygame.init

        def pygame_init_noting_the_interval() -> tuple[int, int]:
            intervals_at_pygame_init.append(sys.getswitchinterval())
            return real_pygame_init()

        mocker.patch.object(pygame, 'init', side_effect=pygame_init_noting_the_interval)
        mocker.patch.object(sys, 'argv', ['test_engine_initialization', *ENGINE_ARGUMENTS])
        # The engine writes SDL hints to the environment; the test's own values come back after
        mocker.patch.dict(os.environ)

        GoldenTraceEngine(game=InitializationTestGame)

        assert intervals_at_pygame_init == [pytest.approx(GIL_SWITCH_INTERVAL_SECONDS)]
        assert sys.getswitchinterval() == pytest.approx(GIL_SWITCH_INTERVAL_SECONDS)
