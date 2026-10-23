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
import contextlib
import logging
import sys
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, override

import pygame
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames import events
from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.engine.game_engine import non_negative_int, non_negative_percent, unit_interval
from glitchygames.exit_codes import ExitCode
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sources import advance_frame_clock, install_sources
from tests.replay.replay_helpers import tamper_first_sprite_rect
from tests.world.test_gameplay_replay import (
    press_keys_while_held,
    record_session,
    replay_session_with_arguments,
)

# The command line every engine in this file starts from: the default display's size
ENGINE_TEST_ARGUMENTS = ('--resolution', '800x600', '--log-level', 'info')
# A custom event type no engine handler maps (pygame refuses types past NUMEVENTS)
UNMAPPED_EVENT_TYPE = pygame.NUMEVENTS - 1
# Another one, for tests that need two
OTHER_UNMAPPED_EVENT_TYPE = pygame.NUMEVENTS - 2
GAME_NAME = 'TestGame'
GAME_VERSION = '1.0'


class EngineTestGame(Scene):
    """A real game scene class for the engine to configure (the engine never builds it here)."""

    NAME = GAME_NAME
    VERSION = GAME_VERSION

    @classmethod
    def args(cls, parser: argparse._ArgumentGroup) -> argparse._ArgumentGroup:
        """Add the game's own command-line option, as a game does.

        Returns:
            The argument group.

        """
        parser.add_argument('--test-flag', action='store_true', help='a game option')
        return parser


class NoIconGame(EngineTestGame):
    """A game whose icon is None: the engine falls back to its own purple icon."""

    icon = None


class PlainWindowEngine(GameEngine):
    """The real GameEngine, opening a plain window instead of a SCALED (or FULLSCREEN) one.

    SDL's dummy video driver has no renderer for SCALED, so pygame warns "no fast renderer
    available" (an error under pytest's filterwarnings); on a real driver (cocoa, x11) SCALED and
    FULLSCREEN would change the display every later test on the worker draws on, and FULLSCREEN
    would take over the screen. mode_flags keeps what the engine chose, so tests can check it;
    scripts/record_golden_traces.py's GoldenTraceEngine opens its window the same way.
    """

    @override
    def initialize_display(self) -> None:
        """Open the display with no flags, keeping the engine's chosen mode_flags."""
        requested_mode_flags = self.mode_flags
        self.mode_flags = 0
        try:
            super().initialize_display()
        finally:
            self.mode_flags = requested_mode_flags


def _override_parsed_options(mocker, option_overrides: dict[str, object]) -> None:
    """Parse the real command line, then set options no command line can give.

    Args:
        mocker: pytest-mock's fixture.
        option_overrides: Option names and the values to give them after parsing.

    """
    real_parse_args = argparse.ArgumentParser.parse_args

    def parse_args_with_overrides(parser, *args, **kwargs):
        namespace = real_parse_args(parser, *args, **kwargs)
        for option_name, value in option_overrides.items():
            setattr(namespace, option_name, value)
        return namespace

    mocker.patch.object(argparse.ArgumentParser, 'parse_args', parse_args_with_overrides)


def _make_engine(
    mocker,
    *arguments: str,
    option_overrides: dict[str, object] | None = None,
    icon: pygame.Surface | None = None,
    game: type[Scene] = EngineTestGame,
):
    """Construct the real engine for EngineTestGame on the real display.

    Args:
        mocker: pytest-mock's fixture.
        *arguments: Command-line arguments after ENGINE_TEST_ARGUMENTS.
        option_overrides: Options to set after parsing (values no command line can give).
        icon: The icon to construct the engine with.
        game: The game scene class.

    Returns:
        PlainWindowEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_game_engine', *ENGINE_TEST_ARGUMENTS, *arguments])
    if option_overrides:
        _override_parsed_options(mocker, option_overrides)
    return PlainWindowEngine(game=game, icon=icon)


def _raw_event(event_type, **attributes):
    """Build a real raw pygame event, as the live doors read from SDL's queue.

    Returns:
        pygame.event.Event: The event.

    """
    return pygame.event.Event(event_type, **attributes)


def _assert_active_cursor_is(cursor: list[str]) -> None:
    """Check SDL's active mouse cursor is the bitmap set_cursor compiles from these rows."""
    cursor_data, cursor_mask = pygame.cursors.compile(cursor, black='.', white='X', xor='o')
    active_cursor = pygame.mouse.get_cursor()
    assert active_cursor.type == 'bitmap'
    assert active_cursor.data == (
        (len(cursor[0]), len(cursor)),
        (0, 0),
        tuple(cursor_data),
        tuple(cursor_mask),
    )


@contextlib.contextmanager
def controller_subsystem(*, initialized: bool) -> Generator[None]:
    """Run with SDL's real game controller subsystem started or stopped, then put it back.

    Args:
        initialized: Whether the subsystem is running inside the block.

    Yields:
        None, while the subsystem is in the asked state.

    """
    was_initialized = pygame._sdl2.controller.get_init()
    if initialized:
        pygame._sdl2.controller.init()
    else:
        pygame._sdl2.controller.quit()
    try:
        yield
    finally:
        if was_initialized:
            pygame._sdl2.controller.init()
        else:
            pygame._sdl2.controller.quit()


# ---------------------------------------------------------------------------
# From test_engine_coverage.py
# ---------------------------------------------------------------------------


class TestGameEngineInitializeArguments:
    """Test GameEngine.initialize_arguments method on real command lines."""

    def test_initialize_arguments_parses_options(self, mocker):
        """initialize_arguments parses the command line into the options it returns."""
        mocker.patch.object(
            sys,
            'argv',
            ['test_game_engine', '--resolution', '640x480', '--update-type', 'flip', '-f', '30'],
        )

        result = GameEngine.initialize_arguments(EngineTestGame)

        assert result['test_flag'] is False
        assert result['resolution'] == '640x480'
        assert result['update_type'] == 'flip'
        assert result['target_fps'] == 30.0
        assert result['log_level'] == 'info'
        assert EngineTestGame.options is result

    def test_initialize_arguments_adds_the_game_options(self, mocker):
        """A game's args() class method adds its options to the engine's command line."""
        mocker.patch.object(sys, 'argv', ['test_game_engine', '--test-flag'])

        result = GameEngine.initialize_arguments(EngineTestGame)

        assert result['test_flag'] is True

    def test_initialize_arguments_game_without_args_method(self, mocker, caplog):
        """A game without an args() class method gets the engine's options only."""

        class NoArgsGame:
            NAME = 'NoArgsGame'
            VERSION = '1.0'
            TARGET_FPS = None

        mocker.patch.object(sys, 'argv', ['test_game_engine'])

        with caplog.at_level(logging.INFO, logger=GameEngine.log.name):
            result = GameEngine.initialize_arguments(NoArgsGame)

        assert result['resolution'] == '800x480'
        assert 'Game does not implement arguments' in caplog.text

    @pytest.mark.parametrize('log_level', ['DEBUG', 'ERROR', 'CRITICAL'])
    def test_upper_case_debug_levels_enable_debug_events(self, mocker, log_level):
        """An upper-case DEBUG, ERROR or CRITICAL level in the options enables debug_events.

        A real command line can never give one (--log-level lower-cases its value: see
        test_command_line_debug_levels_enable_debug_events), so the parsed options are set
        directly: this keeps the branch the engine compares against tested.
        """
        mocker.patch.object(sys, 'argv', ['test_game_engine'])
        _override_parsed_options(mocker, {'log_level': log_level})

        result = GameEngine.initialize_arguments(EngineTestGame)

        assert result['debug_events'] is True

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'Production bug: --log-level lower-cases its value (glitchygames/events/game.py: '
            'type=str.lower), but GameEngine.initialize_arguments compares it with '
            "{'DEBUG', 'CRITICAL', 'ERROR'}, so no command line ever enables debug_events"
        ),
    )
    @pytest.mark.parametrize('log_level', ['debug', 'error', 'critical'])
    def test_command_line_debug_levels_enable_debug_events(self, mocker, log_level):
        """--log-level debug, error or critical enables debug_events."""
        mocker.patch.object(sys, 'argv', ['test_game_engine', '--log-level', log_level])

        result = GameEngine.initialize_arguments(EngineTestGame)

        assert result['debug_events'] is True

    @pytest.mark.parametrize('log_level', ['info', 'warning'])
    def test_initialize_arguments_info_mode(self, mocker, log_level):
        """--log-level info or warning leaves debug_events off."""
        mocker.patch.object(sys, 'argv', ['test_game_engine', '--log-level', log_level])

        result = GameEngine.initialize_arguments(EngineTestGame)

        assert result['debug_events'] is False


class TestGameEngineSuggestedResolution:
    """Test GameEngine.suggested_resolution for different platforms."""

    def test_suggested_resolution_returns_tuple(self, mocker):
        """Test suggested_resolution returns a tuple of ints."""
        engine = _make_engine(mocker)
        result = engine.suggested_resolution(1024, 768)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result == (1024, 768)

    def test_suggested_resolution_linux_arm(self, mocker):
        """Test suggested_resolution on Linux ARM forces 800x480."""
        engine = _make_engine(mocker)

        mocker.patch('platform.system', return_value='Linux')
        mocker.patch('platform.machine', return_value='armv7l')

        result = engine.suggested_resolution(1024, 768)
        assert result == (800, 480)


class TestGameEngineResolveSceneName:
    """Test GameEngine._resolve_scene_name_for_error method."""

    def test_resolve_with_active_scene(self, mocker):
        """Test _resolve_scene_name_for_error with an active scene."""
        engine = _make_engine(mocker)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.NAME = 'ActiveScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'ActiveScene'

    def test_resolve_with_active_scene_no_name(self, mocker):
        """Test _resolve_scene_name_for_error when the active scene has no NAME."""
        engine = _make_engine(mocker)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.NAME = None
        engine.scene_manager.active_scene.__class__.__name__ = 'FallbackScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'FallbackScene'

    def test_resolve_with_previous_scene(self, mocker):
        """Test _resolve_scene_name_for_error falls back to previous scene."""
        engine = _make_engine(mocker)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.active_scene = None
        engine.scene_manager.previous_scene = mocker.Mock()
        engine.scene_manager.previous_scene.NAME = 'PrevScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'PrevScene'

    def test_resolve_with_no_scenes(self, mocker):
        """Test _resolve_scene_name_for_error with no scenes returns 'None'."""
        engine = _make_engine(mocker)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.active_scene = None
        engine.scene_manager.previous_scene = None

        result = engine._resolve_scene_name_for_error()
        assert result == 'None'


class TestGameEngineDisplayMethods:
    """Test GameEngine display-related methods."""

    def test_screen_width_property(self, mocker):
        """Test GameEngine screen_width property."""
        engine = _make_engine(mocker)
        assert engine.screen_width == 800
        assert engine.screen_width == pygame.display.get_surface().get_width()

    def test_screen_height_property(self, mocker):
        """Test GameEngine screen_height property."""
        engine = _make_engine(mocker)
        assert engine.screen_height == 600
        assert engine.screen_height == pygame.display.get_surface().get_height()

    def test_initialize_display_update_mode(self, mocker):
        """initialize_display opens the real display at the resolution and presents by update."""
        engine = _make_engine(mocker, '--resolution', '640x480')
        assert engine.display_update == pygame.display.update
        assert engine.screen is pygame.display.get_surface()
        assert engine.screen.get_size() == (640, 480)
        assert engine.scene_manager.screen is engine.screen
        # Windowed: the engine asks for a scaled, resizable window, never fullscreen
        assert engine.mode_flags & pygame.SCALED
        assert not engine.mode_flags & pygame.FULLSCREEN

    def test_initialize_display_flip_mode(self, mocker):
        """Test GameEngine initialize_display with flip update type."""
        engine = _make_engine(mocker, '--update-type', 'flip')
        assert engine.display_update == pygame.display.flip


class TestGameEngineHandleEvent:
    """Test GameEngine.handle_event method."""

    def test_handle_quit_event(self, mocker):
        """Test handle_event with QUIT event sets quit_requested."""
        engine = _make_engine(mocker)
        quit_event = events.HashableEvent(pygame.QUIT)

        engine.handle_event(quit_event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_with_focused_sprites(self, mocker):
        """Test handle_event routes key events to scene when sprites are focused."""
        engine = _make_engine(mocker)

        # Set up a scene with a focused sprite
        mock_sprite = mocker.Mock()
        mock_sprite.is_active = True
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = [mock_sprite]

        # Mock handle_event on scene_manager since it's a real method
        mock_handle = mocker.patch.object(engine.scene_manager, 'handle_event')

        key_event = events.HashableEvent(pygame.KEYDOWN)
        engine.handle_event(key_event)
        mock_handle.assert_called_once_with(key_event)


class TestGameEngineShutdown:
    """Test GameEngine._shutdown method."""

    def test_shutdown_completes_without_error(self, mocker):
        """Test _shutdown completes without error."""
        engine = _make_engine(mocker)

        try:
            engine._shutdown()

            # _shutdown closes the display and quits pygame, for real
            assert not pygame.display.get_init()
            assert not pygame.get_init()
        finally:
            # Later tests on this worker need pygame and the default display
            pygame.init()
            pygame.display.set_mode((800, 600))


class TestGameEngineInitializeEventHandlers:
    """Test GameEngine event handler initialization."""

    def test_event_handlers_populated(self, mocker):
        """Test that initialize_event_handlers populates EVENT_HANDLERS dict."""
        engine = _make_engine(mocker)
        # After initialization, EVENT_HANDLERS should have entries
        assert len(GameEngine.EVENT_HANDLERS) > 0

    def test_input_event_handlers_include_all_types(
        self,
        mocker,
    ):
        """Test that input event handlers cover controller, keyboard, mouse, etc."""
        engine = _make_engine(mocker)

        # Check that keyboard events are registered
        assert pygame.KEYDOWN in GameEngine.EVENT_HANDLERS
        assert pygame.KEYUP in GameEngine.EVENT_HANDLERS

        # Check that mouse events are registered
        assert pygame.MOUSEBUTTONDOWN in GameEngine.EVENT_HANDLERS
        assert pygame.MOUSEBUTTONUP in GameEngine.EVENT_HANDLERS
        assert pygame.MOUSEMOTION in GameEngine.EVENT_HANDLERS


class TestGameEngineSystemInfo:
    """Test GameEngine system info methods."""

    def test_print_game_info(self, mocker, caplog):
        """Test print_game_info logs game title and version."""
        engine = _make_engine(mocker)

        with caplog.at_level(logging.INFO, logger=GameEngine.log.name):
            engine.print_game_info()

        assert f'Game Title: {GameEngine.NAME}' in caplog.text
        assert f'Game Version: {GameEngine.VERSION}' in caplog.text

    def test_print_system_info(self, mocker, caplog):
        """print_system_info logs the real display driver and resolution."""
        engine = _make_engine(mocker)

        with caplog.at_level(logging.INFO, logger=GameEngine.log.name):
            engine.print_system_info()

        assert f'Display Driver: {pygame.display.get_driver()}' in caplog.text
        assert 'Display inited: True' in caplog.text
        assert f'Initial Resolution: {engine.initial_resolution}' in caplog.text

    def test_initialize_system_icons(self, mocker):
        """initialize_system_icons sets the real window caption (a game with no icon)."""
        engine = _make_engine(mocker, game=NoIconGame)
        pygame.display.set_caption('something else')

        engine.initialize_system_icons()

        expected_caption = f'{GameEngine.NAME} v{GameEngine.VERSION}'
        assert pygame.display.get_caption() == (expected_caption, expected_caption)


class TestGameEngineIconWithSurface:
    """Test GameEngine.initialize_icon with a pygame.Surface."""

    def test_engine_constructed_with_a_surface_icon_keeps_it(self, mocker):
        """GameEngine(icon=surface) makes that real Surface the engine's icon."""
        icon = pygame.Surface((64, 64))
        icon.fill((10, 200, 30))

        _make_engine(mocker, icon=icon)

        assert GameEngine.icon is icon


# ---------------------------------------------------------------------------
# From test_game_engine_coverage.py
# ---------------------------------------------------------------------------


class TestProcessWindowFocusEvent:
    """Test GameEngine.process_window_focus_event for all window focus types."""

    def test_window_shown(self, mocker):
        """Test WINDOWSHOWN dispatches to window_manager."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWSHOWN)

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_shown_event.assert_called_once_with(event)

    def test_window_leave(self, mocker):
        """Test WINDOWLEAVE dispatches to window_manager."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWLEAVE)

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_leave_event.assert_called_once_with(event)

    def test_window_focus_gained(self, mocker):
        """Test WINDOWFOCUSGAINED dispatches and sets grab."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()
        # Mocked: a real grab would confine the mouse of whoever runs the suite on a real driver
        mock_set_grab = mocker.patch('pygame.event.set_grab')

        event = events.HashableEvent(pygame.WINDOWFOCUSGAINED)

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_focus_gained_event.assert_called_once_with(event)
        mock_set_grab.assert_called_once()
        assert mock_set_grab.call_args[0][0] is True

    def test_window_focus_lost(self, mocker):
        """Test WINDOWFOCUSLOST dispatches and releases grab."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()
        # Mocked: a real grab would confine the mouse of whoever runs the suite on a real driver
        mock_set_grab = mocker.patch('pygame.event.set_grab')

        event = events.HashableEvent(pygame.WINDOWFOCUSLOST)

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_focus_lost_event.assert_called_once_with(event)
        mock_set_grab.assert_called_once()
        assert mock_set_grab.call_args[0][0] is False

    def test_window_enter(self, mocker):
        """Test WINDOWENTER dispatches to window_manager."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWENTER)

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_enter_event.assert_called_once_with(event)

    def test_window_take_focus(self, mocker):
        """Test WINDOWTAKEFOCUS dispatches to window_manager."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWTAKEFOCUS)

        result = engine.process_window_focus_event(event)
        assert result is True
        engine.window_manager.on_window_take_focus_event.assert_called_once_with(event)

    def test_unhandled_returns_false(self, mocker):
        """Test unhandled window focus event returns False."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_window_focus_event(event)
        assert result is False


class TestProcessWindowEvent:
    """Test GameEngine.process_window_event dispatch table."""

    def test_window_size_changed(self, mocker):
        """Test WINDOWSIZECHANGED dispatches through dispatch table."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWSIZECHANGED)

        result = engine.process_window_event(event)
        assert result is True
        engine.window_manager.on_window_size_changed_event.assert_called_once_with(event)

    def test_window_restored(self, mocker):
        """Test WINDOWRESTORED dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWRESTORED)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_hidden(self, mocker):
        """Test WINDOWHIDDEN dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWHIDDEN)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_minimized(self, mocker):
        """Test WINDOWMINIMIZED dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWMINIMIZED)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_maximized(self, mocker):
        """Test WINDOWMAXIMIZED dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWMAXIMIZED)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_moved(self, mocker):
        """Test WINDOWMOVED dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWMOVED)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_close(self, mocker):
        """Test WINDOWCLOSE dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWCLOSE)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_exposed(self, mocker):
        """Test WINDOWEXPOSED dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWEXPOSED)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_resized(self, mocker):
        """Test WINDOWRESIZED dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWRESIZED)

        result = engine.process_window_event(event)
        assert result is True

    def test_window_hit_test(self, mocker):
        """Test WINDOWHITTEST dispatches correctly."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(pygame.WINDOWHITTEST)

        result = engine.process_window_event(event)
        assert result is True

    def test_unknown_window_event_returns_false(self, mocker):
        """Test unhandled window event returns False."""
        engine = _make_engine(mocker)
        engine.window_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_window_event(event)
        assert result is False


class TestBuildWindowEventDispatch:
    """Test GameEngine._build_window_event_dispatch method."""

    def test_dispatch_table_has_all_window_events(
        self,
        mocker,
    ):
        """Test dispatch table includes all expected window event types."""
        engine = _make_engine(mocker)
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

    def test_fps_event(self, mocker):
        """Test process_game_event dispatches FPSEVENT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(events.FPSEVENT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_fps_event.assert_called_once_with(event)

    def test_game_event(self, mocker):
        """Test process_game_event dispatches GAMEEVENT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(events.GAMEEVENT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_game_event.assert_called_once_with(event)

    def test_menu_event(self, mocker):
        """Test process_game_event dispatches MENUEVENT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(events.MENUEVENT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_menu_item_event.assert_called_once_with(event)

    def test_active_event(self, mocker):
        """Test process_game_event dispatches ACTIVEEVENT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(pygame.ACTIVEEVENT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_active_event.assert_called_once_with(event)

    def test_user_event(self, mocker):
        """Test process_game_event dispatches USEREVENT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(pygame.USEREVENT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_user_event.assert_called_once_with(event)

    def test_video_resize_event(self, mocker):
        """Test process_game_event dispatches VIDEORESIZE."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(pygame.VIDEORESIZE)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_video_resize_event.assert_called_once_with(event)

    def test_video_expose_event(self, mocker):
        """Test process_game_event dispatches VIDEOEXPOSE."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(pygame.VIDEOEXPOSE)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_video_expose_event.assert_called_once_with(event)

    def test_sys_wm_event(self, mocker):
        """Test process_game_event dispatches SYSWMEVENT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(pygame.SYSWMEVENT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_sys_wm_event.assert_called_once_with(event)

    def test_quit_event(self, mocker):
        """Test process_game_event dispatches QUIT."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(pygame.QUIT)

        result = engine.process_game_event(event)
        assert result is True
        engine.game_manager.on_quit_event.assert_called_once_with(event)

    def test_unhandled_returns_false(self, mocker):
        """Test process_game_event returns False for unknown game events."""
        engine = _make_engine(mocker)
        engine.game_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_game_event(event)
        assert result is False


class TestProcessUnimplementedEvent:
    """Test GameEngine.process_unimplemented_event method."""

    def test_first_unimplemented_event_is_logged(self, mocker):
        """Test first occurrence of an unimplemented event is logged."""
        engine = _make_engine(mocker)
        # Clear prior state
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        event = events.HashableEvent(55555)  # An arbitrary unused event type

        engine.process_unimplemented_event(event)
        assert 55555 in GameEngine.UNIMPLEMENTED_EVENTS

    def test_duplicate_unimplemented_event_not_added_twice(
        self,
        mocker,
    ):
        """Test duplicate unimplemented events are not appended again."""
        engine = _make_engine(mocker)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        event = events.HashableEvent(55556)

        engine.process_unimplemented_event(event)
        engine.process_unimplemented_event(event)
        assert GameEngine.UNIMPLEMENTED_EVENTS.count(55556) == 1

    def test_event_type_1543_debug_logging(self, mocker, caplog):
        """Event type 1543 is logged in detail: its contents, the controller count, its ids."""
        engine = _make_engine(mocker)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()
        event = events.HashableEvent(1543, device_index=2)  # UNKNOWN_SDL2_EVENT_TYPE_1543

        with (
            controller_subsystem(initialized=True),
            caplog.at_level(logging.DEBUG, logger='game.engine'),
        ):
            engine.process_unimplemented_event(event)

        assert 1543 in GameEngine.UNIMPLEMENTED_EVENTS
        assert "'device_index': 2" in caplog.text
        assert 'Current controller count when event 1543 received: ' in caplog.text
        assert 'Controller system not initialized' not in caplog.text
        assert 'Event has device_index: True' in caplog.text
        assert 'Event has guid: False' in caplog.text

    def test_event_type_1543_when_the_controller_system_cannot_answer(self, mocker, caplog):
        """SDL cannot count controllers (subsystem not initialized): logged, never raised."""
        engine = _make_engine(mocker)
        GameEngine.UNIMPLEMENTED_EVENTS.clear()
        event = events.HashableEvent(1543)

        with (
            controller_subsystem(initialized=False),
            caplog.at_level(logging.DEBUG, logger='game.engine'),
        ):
            engine.process_unimplemented_event(event)

        assert 'Controller system not initialized' in caplog.text
        assert 1543 in GameEngine.UNIMPLEMENTED_EVENTS


class TestUnhandledEventTracking:
    """GameEngine keeps per-type statistics of unhandled events and reports them at teardown."""

    def test_counts_and_first_seen_time_per_type(self, mocker):
        """Each type is counted; its first-seen time is the frame clock since the engine started."""
        engine = _make_engine(mocker)

        advance_frame_clock(seconds=0.25)
        engine.process_unimplemented_event(events.HashableEvent(pygame.JOYDEVICEADDED))
        advance_frame_clock(seconds=1.75)
        engine.process_unimplemented_event(events.HashableEvent(pygame.JOYDEVICEADDED))
        engine.process_unimplemented_event(events.HashableEvent(pygame.DROPBEGIN))

        joystick_record = engine.unhandled_events[pygame.JOYDEVICEADDED]
        assert joystick_record.count == 2
        assert joystick_record.first_seen_seconds == pytest.approx(0.25)
        drop_record = engine.unhandled_events[pygame.DROPBEGIN]
        assert drop_record.count == 1
        assert drop_record.first_seen_seconds == pytest.approx(2.0)

    def test_first_seen_times_count_from_this_engines_start(self, mocker):
        """An earlier run's frame clock never leaks in: the engine restarts it (reset_sources)."""
        advance_frame_clock(seconds=500.0)
        engine = _make_engine(mocker)

        advance_frame_clock(seconds=0.5)
        engine.process_unimplemented_event(events.HashableEvent(pygame.JOYDEVICEADDED))

        assert engine.unhandled_events[pygame.JOYDEVICEADDED].first_seen_seconds == pytest.approx(
            0.5
        )

    def test_records_attribute_names_of_first_event_only(self, mocker):
        """The first event's attribute names are kept, sorted; values never appear."""
        engine = _make_engine(mocker)

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

    def test_report_is_sorted_by_count_descending(self, mocker):
        """The most frequent type comes first."""
        engine = _make_engine(mocker)
        advance_frame_clock(seconds=0.3)
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

    def test_custom_event_type_appears_with_its_number(self, mocker):
        """An unknown or custom type is reported with its numeric type."""
        engine = _make_engine(mocker)
        custom_event_type = 88886

        engine.process_unimplemented_event(events.HashableEvent(custom_event_type, payload=1))

        (report_line,) = engine.unhandled_event_report()
        assert f'({custom_event_type}) x1' in report_line

    def test_teardown_logs_the_unhandled_event_table(self, mocker, caplog):
        """_shutdown logs every unhandled event type with the shutdown statistics."""
        engine = _make_engine(mocker)
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

    def test_teardown_logs_nothing_when_every_event_was_handled(self, mocker, caplog):
        """No unhandled events means no report line at all."""
        engine = _make_engine(mocker)
        mocker.patch('pygame.display.quit')
        mocker.patch('pygame.quit')

        with caplog.at_level('INFO', logger='game.engine'):
            engine._shutdown()

        assert not [
            record
            for record in caplog.records
            if record.name == 'game.engine' and 'Unhandled events' in record.getMessage()
        ]

    def test_teardown_without_an_fps_log_interval(self, mocker):
        """An engine without an FPS log interval leaves the performance manager's as it was.

        --fps-log-interval-ms always gives a number, so the parsed option is set directly.
        """
        from glitchygames.performance import performance_manager

        # The real manager is process-wide: put its settings back after the test
        mocker.patch.object(
            performance_manager, '_fps_log_interval_ms', performance_manager._fps_log_interval_ms
        )
        mocker.patch.object(performance_manager, '_target_fps', performance_manager._target_fps)
        performance_manager.set_fps_log_interval(250.0)
        engine = _make_engine(mocker, option_overrides={'fps_log_interval_ms': None})
        mocker.patch('pygame.display.quit')
        mocker.patch('pygame.quit')

        engine._shutdown()

        assert performance_manager._fps_log_interval_ms == 250.0
        assert performance_manager._target_fps == engine.fps


class TestPostGameEvent:
    """Test GameEngine.post_game_event method."""

    def test_post_game_event_posts_to_pygame(self, mocker):
        """post_game_event puts a GAMEEVENT with its subtype and data on SDL's real queue."""
        engine = _make_engine(mocker)
        pygame.event.clear(events.GAMEEVENT)

        engine.post_game_event('custom_subtype', {'key': 'value'})

        (posted_event,) = pygame.event.get(events.GAMEEVENT)
        assert posted_event.dict == {'subtype': 'custom_subtype', 'key': 'value'}


class TestSuppressEvent:
    """Test GameEngine.suppress_event method."""

    def test_suppress_event_does_not_raise(self, mocker):
        """Test suppress_event completes without error."""
        engine = _make_engine(mocker)
        engine.suppress_event('arg1', 'arg2', attr='some_event')


class TestRegisterGameEvent:
    """Test GameEngine.register_game_event method."""

    def test_register_game_event_stores_callback(self, mocker):
        """Test register_game_event stores the callback in registered_events."""
        engine = _make_engine(mocker)
        engine.registered_events = {}

        callback = mocker.Mock()
        engine.register_game_event('my_event', callback)
        assert 'my_event' in engine.registered_events
        assert engine.registered_events['my_event'] is callback


class TestMissingEvent:
    """Test GameEngine.missing_event method."""

    def test_missing_event_logs_once(self, mocker):
        """Test missing_event logs the method name once."""
        engine = _make_engine(mocker)
        GameEngine.MISSING_EVENTS.clear()
        GameEngine.LAST_EVENT_MISS = 'on_some_unknown_event'

        engine.missing_event('arg1', kwarg1='val')
        assert 'on_some_unknown_event' in GameEngine.MISSING_EVENTS

    def test_missing_event_not_duplicated(self, mocker):
        """Test missing_event does not duplicate entries."""
        engine = _make_engine(mocker)
        GameEngine.MISSING_EVENTS.clear()
        GameEngine.LAST_EVENT_MISS = 'on_duplicate_event'

        engine.missing_event()
        engine.missing_event()
        assert GameEngine.MISSING_EVENTS.count('on_duplicate_event') == 1

    def test_an_event_handler_nobody_has_reaches_missing_event(self, mocker):
        """A handler the engine does not have resolves to missing_event, which notes it once.

        The scene manager hands an on_*_event its active scene lacks to the engine
        (SceneManager.__getattr__), and the engine's __getattr__ answers it.
        """
        engine = _make_engine(mocker)
        mocker.patch.object(GameEngine, 'LAST_EVENT_MISS', GameEngine.LAST_EVENT_MISS)
        mocker.patch.object(GameEngine, 'MISSING_EVENTS', [])

        handler = engine.on_never_defined_event
        handler(events.HashableEvent(pygame.USEREVENT))

        assert handler == engine.missing_event
        assert GameEngine.LAST_EVENT_MISS == 'on_never_defined_event'
        assert GameEngine.MISSING_EVENTS == ['on_never_defined_event']

    def test_a_non_event_attribute_the_engine_lacks_raises(self, mocker):
        """Only on_*_event names fall back to missing_event; anything else is an error."""
        engine = _make_engine(mocker)

        with pytest.raises(AttributeError, match='not_an_event_handler'):
            _ = engine.not_an_event_handler


class TestProcessEvents:
    """Test GameEngine.process_events main event loop.

    pygame.event.get, which the live doors read SDL's queue with, is patched to hand over each
    test's real events: on a real video driver the OS queues events of its own (window, mouse)
    at any moment, which a test of exact batches cannot allow.
    """

    def test_process_events_with_scene_process_event(
        self,
        mocker,
    ):
        """Test process_events bypasses engine processing when scene has process_event."""
        engine = _make_engine(mocker)

        raw_event = _raw_event(pygame.KEYDOWN, key=pygame.K_a)
        # SDL's queue stands in for the keyboard: on a real driver the OS adds its own events
        mocker.patch('pygame.event.get', return_value=[raw_event])

        mock_scene = mocker.Mock()
        mock_scene.process_event = mocker.Mock()
        engine._active_scene = mock_scene

        result = engine.process_events()
        assert result is True
        mock_scene.process_event.assert_called_once_with(raw_event)

    def test_process_events_handles_event_through_handlers(
        self,
        mocker,
    ):
        """Test process_events routes events through EVENT_HANDLERS."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event

        raw_event = _raw_event(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        mocker.patch('pygame.event.get', return_value=[raw_event])

        key_down_handler = mocker.Mock(return_value=True)
        mocker.patch.dict(GameEngine.EVENT_HANDLERS, {pygame.KEYDOWN: key_down_handler})

        result = engine.process_events()
        assert result is True
        key_down_handler.assert_called_once()
        assert key_down_handler.call_args.args[0].key == pygame.K_a

    def test_process_events_no_events_returns_false(
        self,
        mocker,
    ):
        """Test process_events returns False when no events in queue."""
        engine = _make_engine(mocker)
        mocker.patch('pygame.event.get', return_value=[])

        result = engine.process_events()
        assert result is False

    def test_process_events_unhandled_event(self, mocker):
        """Test process_events routes unhandled events to process_unimplemented_event."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        GameEngine.UNIMPLEMENTED_EVENTS.clear()

        mocker.patch('pygame.event.get', return_value=[_raw_event(UNMAPPED_EVENT_TYPE)])
        assert UNMAPPED_EVENT_TYPE not in GameEngine.EVENT_HANDLERS

        result = engine.process_events()

        assert result is False
        assert engine.unhandled_events[UNMAPPED_EVENT_TYPE].count == 1
        assert UNMAPPED_EVENT_TYPE in GameEngine.UNIMPLEMENTED_EVENTS

    def test_process_events_unhandled_event_does_not_drop_rest_of_batch(self, mocker):
        """An unhandled event must not drop the key-down queued after it in the same batch."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event

        unhandled_raw_event = _raw_event(pygame.KEYUP, key=pygame.K_b)
        key_down_raw_event = _raw_event(pygame.KEYDOWN, key=pygame.K_a)
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

    def test_process_events_raw_event_scene_receives_every_event_in_order(self, mocker):
        """A scene with process_event receives all N events of a batch, in order."""
        engine = _make_engine(mocker)
        raw_events = [
            _raw_event(pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(pygame.MOUSEMOTION, pos=(1, 2)),
            _raw_event(pygame.KEYUP, key=pygame.K_a),
        ]
        mocker.patch('pygame.event.get', return_value=raw_events)
        mock_scene = mocker.Mock()
        engine._active_scene = mock_scene

        result = engine.process_events()

        assert [call.args[0] for call in mock_scene.process_event.call_args_list] == raw_events
        assert result is True

    def test_process_events_unmapped_type_after_handled_event_is_unhandled(self, mocker):
        """An event type missing from EVENT_HANDLERS never inherits the previous result."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        unmapped_event_type = OTHER_UNMAPPED_EVENT_TYPE
        assert unmapped_event_type not in GameEngine.EVENT_HANDLERS

        raw_events = [
            _raw_event(pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(unmapped_event_type),
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

    def test_process_events_returns_true_only_when_every_event_handled(self, mocker):
        """The return value is True only if every event of the batch was handled."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        raw_events = [
            _raw_event(pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(pygame.KEYUP, key=pygame.K_a),
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

    def test_process_events_returns_false_when_every_event_is_discarded(self, mocker):
        """No event dispatched (all discarded) is reported as False, like an empty batch."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        raw_events = [_raw_event(pygame.KEYDOWN, key=pygame.K_a)]
        mocker.patch('pygame.event.get', return_value=raw_events)
        key_down_handler = mocker.Mock(return_value=True)
        mocker.patch.dict(GameEngine.EVENT_HANDLERS, {pygame.KEYDOWN: key_down_handler})
        mock_unimplemented = mocker.patch.object(engine, 'process_unimplemented_event')

        result = engine.process_events(should_discard=lambda _event: True)

        assert result is False
        key_down_handler.assert_not_called()
        mock_unimplemented.assert_not_called()

    def test_process_events_discards_only_matching_events(self, mocker):
        """Kept events are dispatched and decide the result; discarded ones do not count."""
        engine = _make_engine(mocker)
        engine._active_scene = mocker.Mock(spec=[])  # No process_event
        raw_events = [
            _raw_event(pygame.KEYDOWN, key=pygame.K_a),
            _raw_event(pygame.KEYUP, key=pygame.K_a),
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

    def test_handle_event_no_scene(self, mocker):
        """Test handle_event when active_scene is None."""
        engine = _make_engine(mocker)
        engine.scene_manager.active_scene = None
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.KEYDOWN, key=pygame.K_q)

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_with_unfocused_sprites(self, mocker):
        """Test handle_event with sprites that are not focused."""
        engine = _make_engine(mocker)
        mock_sprite = mocker.Mock()
        mock_sprite.is_active = False  # Not focused
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = [mock_sprite]
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.KEYDOWN, key=pygame.K_a)

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_non_key_event_passes_to_scene_manager(
        self,
        mocker,
    ):
        """Test non-KEYDOWN events always pass to scene_manager."""
        engine = _make_engine(mocker)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.MOUSEBUTTONDOWN)

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_handle_event_quit_event(self, mocker):
        """Test QUIT event sets quit_requested without passing to scene_manager."""
        engine = _make_engine(mocker)
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.QUIT)

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

    def test_initialize_icon_with_path(self):
        """A missing icon file is ignored: the icon stays as it was."""
        original_icon = GameEngine.icon

        GameEngine.initialize_icon(Path('/nonexistent/icon.png'))

        assert GameEngine.icon is original_icon

    def test_initialize_icon_loads_an_image_file(self, tmp_path):
        """An icon path is loaded with the real image loader."""
        icon_path = tmp_path / 'icon.png'
        drawn_icon = pygame.Surface((16, 16))
        drawn_icon.fill((200, 40, 90))
        pygame.image.save(drawn_icon, icon_path)

        GameEngine.initialize_icon(str(icon_path))

        assert isinstance(GameEngine.icon, pygame.Surface)
        assert GameEngine.icon.get_size() == (16, 16)
        assert GameEngine.icon.get_at((8, 8))[:3] == (200, 40, 90)


class TestSetCursorWithCustomCursor:
    """Test GameEngine.set_cursor with a custom cursor."""

    def test_set_cursor_with_custom_cursor(self):
        """set_cursor makes a custom cursor the real active cursor."""
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
        _assert_active_cursor_is(custom_cursor)


class TestInitializeEventManagers:
    """Test GameEngine._initialize_event_managers method."""

    def test_initialize_event_managers_sets_up_all_managers(self, mocker):
        """_initialize_event_managers builds every manager on the real scene manager and devices.

        Input mode auto picks joystick on pygame-ce, which blocks controller events at SDL; their
        blocked state is put back afterwards, so later tests on this worker are unaffected.
        """
        from glitchygames.events.audio import AudioEventManager
        from glitchygames.events.keyboard import KeyboardEventManager
        from glitchygames.events.mouse import MouseEventManager
        from glitchygames.events.window import WindowEventManager

        engine = _make_engine(mocker)
        # As GameEngine.start() does before it builds the managers (put back after the test)
        mocker.patch.object(SceneManager, 'OPTIONS', GameEngine.OPTIONS)
        blocked_before = {
            event_type: pygame.event.get_blocked(event_type)
            for event_type in events.CONTROLLER_EVENTS
        }
        try:
            engine._initialize_event_managers()

            assert isinstance(engine.audio_manager, AudioEventManager)
            assert isinstance(engine.keyboard_manager, KeyboardEventManager)
            assert isinstance(engine.mouse_manager, MouseEventManager)
            assert isinstance(engine.window_manager, WindowEventManager)
            for manager in (
                engine.app_manager,
                engine.drop_manager,
                engine.touch_manager,
                engine.font_manager,
                engine.game_manager,
                engine.joystick_manager,
                engine.midi_manager,
            ):
                assert manager is not None
            # --input-mode auto picks joystick on pygame-ce: no controller manager, and SDL
            # drops controller events
            assert GameEngine.OPTIONS['input_mode'] == 'joystick'
            assert engine.controller_manager is None
            assert all(
                pygame.event.get_blocked(event_type) for event_type in events.CONTROLLER_EVENTS
            )
            # The joysticks are whatever real devices are attached (none on the dummy driver)
            assert engine.joystick_count == len(engine.joysticks)
        finally:
            for event_type, was_blocked in blocked_before.items():
                if was_blocked:
                    pygame.event.set_blocked(event_type)
                else:
                    pygame.event.set_allowed(event_type)


class TestStartMethod:
    """Test GameEngine.start method paths."""

    def test_start_with_no_game_raises(self, mocker):
        """Test start raises RuntimeError when game is None."""
        engine = _make_engine(mocker)
        GameEngine.game = None

        with pytest.raises(RuntimeError, match='Game not initialized'):
            engine.start()

        # Re-init pygame for other tests
        pygame.init()
        pygame.display.set_mode((800, 600))


class TestResolveSceneNameForError:
    """Test _resolve_scene_name_for_error additional paths."""

    def test_previous_scene_with_no_name(self, mocker):
        """Test falls back to class name when previous scene has NAME=None."""
        engine = _make_engine(mocker)
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.active_scene = None
        engine.scene_manager.previous_scene = mocker.Mock()
        engine.scene_manager.previous_scene.NAME = None
        engine.scene_manager.previous_scene.__class__.__name__ = 'FallbackPrevScene'

        result = engine._resolve_scene_name_for_error()
        assert result == 'FallbackPrevScene'


class TestProcessTextEventUnhandled:
    """Test GameEngine.process_text_event returns False path (line 1250)."""

    def test_unhandled_text_event_returns_false(self, mocker):
        """Test process_text_event returns False for unhandled text event types."""
        engine = _make_engine(mocker)

        event = events.HashableEvent(99999)  # Not TEXTEDITING or TEXTINPUT

        result = engine.process_text_event(event)
        assert result is False


# ---------------------------------------------------------------------------
# From test_engine_deeper_coverage.py
# ---------------------------------------------------------------------------


class TestProcessAudioEvent:
    """Test GameEngine.process_audio_event dispatcher."""

    def test_audio_device_added(self, mocker):
        """Test process_audio_event dispatches AUDIODEVICEADDED."""
        engine = _make_engine(mocker)
        engine.audio_manager = mocker.Mock()

        event = events.HashableEvent(pygame.AUDIODEVICEADDED)

        result = engine.process_audio_event(event)
        assert result is True
        engine.audio_manager.on_audio_device_added_event.assert_called_once_with(event)

    def test_audio_device_removed(self, mocker):
        """Test process_audio_event dispatches AUDIODEVICEREMOVED."""
        engine = _make_engine(mocker)
        engine.audio_manager = mocker.Mock()

        event = events.HashableEvent(pygame.AUDIODEVICEREMOVED)

        result = engine.process_audio_event(event)
        assert result is True
        engine.audio_manager.on_audio_device_removed_event.assert_called_once_with(event)

    def test_audio_unhandled_event_returns_false(self, mocker):
        """Test process_audio_event returns False for unknown audio events."""
        engine = _make_engine(mocker)
        engine.audio_manager = mocker.Mock()

        event = events.HashableEvent(99999)  # Unknown event type

        result = engine.process_audio_event(event)
        assert result is False


class TestProcessAppEvent:
    """Test GameEngine.process_app_event dispatcher."""

    def test_app_did_enter_background(self, mocker):
        """Test process_app_event dispatches APP_DIDENTERBACKGROUND."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(pygame.APP_DIDENTERBACKGROUND)

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_did_enter_background_event.assert_called_once_with(event)

    def test_app_did_enter_foreground(self, mocker):
        """Test process_app_event dispatches APP_DIDENTERFOREGROUND."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(pygame.APP_DIDENTERFOREGROUND)

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_did_enter_foreground_event.assert_called_once_with(event)

    def test_app_will_enter_background(self, mocker):
        """Test process_app_event dispatches APP_WILLENTERBACKGROUND."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(pygame.APP_WILLENTERBACKGROUND)

        result = engine.process_app_event(event)
        assert result is True

    def test_app_will_enter_foreground(self, mocker):
        """Test process_app_event dispatches APP_WILLENTERFOREGROUND."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(pygame.APP_WILLENTERFOREGROUND)

        result = engine.process_app_event(event)
        assert result is True

    def test_app_low_memory(self, mocker):
        """Test process_app_event dispatches APP_LOWMEMORY."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(pygame.APP_LOWMEMORY)

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_low_memory_event.assert_called_once_with(event)

    def test_app_terminating(self, mocker):
        """Test process_app_event dispatches APP_TERMINATING."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(pygame.APP_TERMINATING)

        result = engine.process_app_event(event)
        assert result is True
        engine.app_manager.on_app_terminating_event.assert_called_once_with(event)

    def test_app_unhandled_returns_false(self, mocker):
        """Test process_app_event returns False for unknown app events."""
        engine = _make_engine(mocker)
        engine.app_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_app_event(event)
        assert result is False


class TestProcessDropEvent:
    """Test GameEngine.process_drop_event dispatcher."""

    def test_drop_begin(self, mocker):
        """Test process_drop_event dispatches DROPBEGIN."""
        engine = _make_engine(mocker)
        engine.drop_manager = mocker.Mock()

        event = events.HashableEvent(pygame.DROPBEGIN)

        result = engine.process_drop_event(event)
        assert result is True
        engine.drop_manager.on_drop_begin_event.assert_called_once_with(event)

    def test_drop_complete(self, mocker):
        """Test process_drop_event dispatches DROPCOMPLETE."""
        engine = _make_engine(mocker)
        engine.drop_manager = mocker.Mock()

        event = events.HashableEvent(pygame.DROPCOMPLETE)

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_file(self, mocker):
        """Test process_drop_event dispatches DROPFILE."""
        engine = _make_engine(mocker)
        engine.drop_manager = mocker.Mock()

        event = events.HashableEvent(pygame.DROPFILE)

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_text(self, mocker):
        """Test process_drop_event dispatches DROPTEXT."""
        engine = _make_engine(mocker)
        engine.drop_manager = mocker.Mock()

        event = events.HashableEvent(pygame.DROPTEXT)

        result = engine.process_drop_event(event)
        assert result is True

    def test_drop_unhandled_returns_false(self, mocker):
        """Test process_drop_event returns False for unknown drop events."""
        engine = _make_engine(mocker)
        engine.drop_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_drop_event(event)
        assert result is False


class TestProcessTouchEvent:
    """Test GameEngine.process_touch_event dispatcher."""

    def test_finger_down(self, mocker):
        """Test process_touch_event dispatches FINGERDOWN."""
        engine = _make_engine(mocker)
        engine.touch_manager = mocker.Mock()

        event = events.HashableEvent(pygame.FINGERDOWN)

        result = engine.process_touch_event(event)
        assert result is True
        engine.touch_manager.on_touch_down_event.assert_called_once_with(event)

    def test_finger_up(self, mocker):
        """Test process_touch_event dispatches FINGERUP."""
        engine = _make_engine(mocker)
        engine.touch_manager = mocker.Mock()

        event = events.HashableEvent(pygame.FINGERUP)

        result = engine.process_touch_event(event)
        assert result is True

    def test_finger_motion(self, mocker):
        """Test process_touch_event dispatches FINGERMOTION."""
        engine = _make_engine(mocker)
        engine.touch_manager = mocker.Mock()

        event = events.HashableEvent(pygame.FINGERMOTION)

        result = engine.process_touch_event(event)
        assert result is True

    def test_touch_unhandled_returns_false(self, mocker):
        """Test process_touch_event returns False for unknown touch events."""
        engine = _make_engine(mocker)
        engine.touch_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_touch_event(event)
        assert result is False


class TestProcessMouseEvent:
    """Test GameEngine.process_mouse_event dispatcher."""

    def test_mouse_motion(self, mocker):
        """Test process_mouse_event dispatches MOUSEMOTION."""
        engine = _make_engine(mocker)
        engine.mouse_manager = mocker.Mock()

        event = events.HashableEvent(pygame.MOUSEMOTION)

        result = engine.process_mouse_event(event)
        assert result is True
        engine.mouse_manager.on_mouse_motion_event.assert_called_once_with(event)

    def test_mouse_button_up(self, mocker):
        """Test process_mouse_event dispatches MOUSEBUTTONUP."""
        engine = _make_engine(mocker)
        engine.mouse_manager = mocker.Mock()

        event = events.HashableEvent(pygame.MOUSEBUTTONUP)

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_button_down(self, mocker):
        """Test process_mouse_event dispatches MOUSEBUTTONDOWN."""
        engine = _make_engine(mocker)
        engine.mouse_manager = mocker.Mock()

        event = events.HashableEvent(pygame.MOUSEBUTTONDOWN)
        event.button = 1
        event.pos = (100, 100)

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_wheel(self, mocker):
        """Test process_mouse_event dispatches MOUSEWHEEL."""
        engine = _make_engine(mocker)
        engine.mouse_manager = mocker.Mock()

        event = events.HashableEvent(pygame.MOUSEWHEEL)

        result = engine.process_mouse_event(event)
        assert result is True

    def test_mouse_unhandled_returns_false(self, mocker):
        """Test process_mouse_event returns False for unknown mouse events."""
        engine = _make_engine(mocker)
        engine.mouse_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_mouse_event(event)
        assert result is False


class TestProcessKeyboardEvent:
    """Test GameEngine.process_keyboard_event dispatcher."""

    def test_key_down(self, mocker):
        """Test process_keyboard_event dispatches KEYDOWN."""
        engine = _make_engine(mocker)
        engine.keyboard_manager = mocker.Mock()

        event = events.HashableEvent(pygame.KEYDOWN)

        result = engine.process_keyboard_event(event)
        assert result is True
        engine.keyboard_manager.on_key_down_event.assert_called_once_with(event)

    def test_key_up(self, mocker):
        """Test process_keyboard_event dispatches KEYUP."""
        engine = _make_engine(mocker)
        engine.keyboard_manager = mocker.Mock()

        event = events.HashableEvent(pygame.KEYUP)

        result = engine.process_keyboard_event(event)
        assert result is True

    def test_keyboard_unhandled_returns_false(self, mocker):
        """Test process_keyboard_event returns False for unknown keyboard events."""
        engine = _make_engine(mocker)
        engine.keyboard_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_keyboard_event(event)
        assert result is False


class TestProcessJoystickEvent:
    """Test GameEngine.process_joystick_event dispatcher."""

    def test_joy_axis_motion(self, mocker):
        """Test process_joystick_event dispatches JOYAXISMOTION."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYAXISMOTION)

        result = engine.process_joystick_event(event)
        assert result is True
        engine.joystick_manager.on_joy_axis_motion_event.assert_called_once_with(event)

    def test_joy_ball_motion(self, mocker):
        """Test process_joystick_event dispatches JOYBALLMOTION."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYBALLMOTION)

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_hat_motion(self, mocker):
        """Test process_joystick_event dispatches JOYHATMOTION."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYHATMOTION)

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_button_down(self, mocker):
        """Test process_joystick_event dispatches JOYBUTTONDOWN."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYBUTTONDOWN)

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_button_up(self, mocker):
        """Test process_joystick_event dispatches JOYBUTTONUP."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYBUTTONUP)

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_device_added(self, mocker):
        """Test process_joystick_event dispatches JOYDEVICEADDED."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYDEVICEADDED)

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joy_device_removed(self, mocker):
        """Test process_joystick_event dispatches JOYDEVICEREMOVED."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(pygame.JOYDEVICEREMOVED)

        result = engine.process_joystick_event(event)
        assert result is True

    def test_joystick_unhandled_returns_false(self, mocker):
        """Test process_joystick_event returns False for unknown joystick events."""
        engine = _make_engine(mocker)
        engine.joystick_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_joystick_event(event)
        assert result is False


class TestProcessMidiEvent:
    """Test GameEngine.process_midi_event dispatcher."""

    def test_midi_in(self, mocker):
        """Test process_midi_event dispatches MIDIIN."""
        engine = _make_engine(mocker)
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.MIDIIN)

        result = engine.process_midi_event(event)
        assert result is True
        engine.scene_manager.handle_event.assert_called_once_with(event)

    def test_midi_out(self, mocker):
        """Test process_midi_event dispatches MIDIOUT."""
        engine = _make_engine(mocker)
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.MIDIOUT)

        result = engine.process_midi_event(event)
        assert result is True

    def test_midi_unhandled_returns_false(self, mocker):
        """Test process_midi_event returns False for unknown midi events."""
        engine = _make_engine(mocker)

        event = events.HashableEvent(99999)

        result = engine.process_midi_event(event)
        assert result is False


class TestProcessTextEvent:
    """Test GameEngine.process_text_event dispatcher."""

    def test_text_editing(self, mocker):
        """Test process_text_event dispatches TEXTEDITING."""
        engine = _make_engine(mocker)
        mocker.patch.object(engine, 'process_unimplemented_event')

        event = events.HashableEvent(pygame.TEXTEDITING)

        result = engine.process_text_event(event)
        assert result is True
        engine.process_unimplemented_event.assert_called_once_with(event)

    def test_text_input(self, mocker):
        """Test process_text_event dispatches TEXTINPUT."""
        engine = _make_engine(mocker)
        mocker.patch.object(engine, 'process_unimplemented_event')

        event = events.HashableEvent(pygame.TEXTINPUT)

        result = engine.process_text_event(event)
        assert result is True


class TestProcessControllerEvent:
    """Test GameEngine.process_controller_event dispatcher."""

    def test_controller_axis_motion(self, mocker):
        """Test process_controller_event dispatches CONTROLLERAXISMOTION."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERAXISMOTION)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_button_down(self, mocker):
        """Test process_controller_event dispatches CONTROLLERBUTTONDOWN."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERBUTTONDOWN)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_button_up(self, mocker):
        """Test process_controller_event dispatches CONTROLLERBUTTONUP."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERBUTTONUP)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_down(self, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADDOWN."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERTOUCHPADDOWN)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_up(self, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADUP."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERTOUCHPADUP)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_touchpad_motion(self, mocker):
        """Test process_controller_event dispatches CONTROLLERTOUCHPADMOTION."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERTOUCHPADMOTION)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_removed(self, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEREMOVED."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERDEVICEREMOVED)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_added(self, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEADDED."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERDEVICEADDED)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_device_remapped(self, mocker):
        """Test process_controller_event dispatches CONTROLLERDEVICEREMAPPED."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERDEVICEREMAPPED)

        result = engine.process_controller_event(event)
        assert result is True

    def test_controller_sensor_update(self, mocker):
        """CONTROLLERSENSORUPDATE goes to the controller manager's sensor handler."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(pygame.CONTROLLERSENSORUPDATE)

        result = engine.process_controller_event(event)
        assert result is True
        engine.controller_manager.on_controller_sensor_update_event.assert_called_once_with(event)

    def test_controller_event_in_joystick_mode_is_not_handled(self, mocker):
        """Joystick input mode has no controller manager: controller events are not handled."""
        engine = _make_engine(mocker)
        engine.controller_manager = None

        event = events.HashableEvent(pygame.CONTROLLERBUTTONDOWN)

        assert engine.process_controller_event(event) is False

    def test_controller_unhandled_returns_false(self, mocker):
        """Test process_controller_event returns False for unknown controller events."""
        engine = _make_engine(mocker)
        engine.controller_manager = mocker.Mock()

        event = events.HashableEvent(99999)

        result = engine.process_controller_event(event)
        assert result is False


class TestGameEngineHandleEventDeeper:
    """Test GameEngine.handle_event deeper paths."""

    def test_handle_event_keydown_q_with_no_focused_sprites(
        self,
        mocker,
    ):
        """Test handle_event with K_q and no focused sprites sets quit_requested."""
        engine = _make_engine(mocker)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.KEYDOWN, key=pygame.K_q)

        engine.handle_event(event)
        assert engine.scene_manager.quit_requested is True

    def test_handle_event_passes_non_key_events_to_scene_manager(
        self,
        mocker,
    ):
        """Test handle_event passes non-key events to scene_manager."""
        engine = _make_engine(mocker)
        engine.scene_manager.active_scene = mocker.Mock()
        engine.scene_manager.active_scene.all_sprites = []
        engine.scene_manager.handle_event = mocker.Mock()

        event = events.HashableEvent(pygame.MOUSEMOTION)

        engine.handle_event(event)
        engine.scene_manager.handle_event.assert_called_once_with(event)


class TestGameEngineSetCursorDefault:
    """Test GameEngine.set_cursor with None for default cursor."""

    def test_set_cursor_with_none_creates_default(self):
        """Test set_cursor with None creates the default cursor."""
        result = GameEngine.set_cursor(cursor=None)

        assert len(result) == 24
        assert all(len(row) == 24 for row in result)
        _assert_active_cursor_is(result)


class TestGameEngineSuggestedResolutionLinuxNonArm:
    """Test suggested_resolution on Linux non-ARM returns desired resolution."""

    def test_suggested_resolution_linux_non_arm(self, mocker):
        """Test suggested_resolution on Linux non-ARM returns desired resolution."""
        engine = _make_engine(mocker)

        mocker.patch('platform.system', return_value='Linux')
        mocker.patch('platform.machine', return_value='x86_64')

        result = engine.suggested_resolution(1024, 768)
        assert result == (1024, 768)


class TestGameEngineDelMethod:
    """Test GameEngine.__del__ method."""

    def test_del_logs_sprite_counts(self, mocker):
        """Test __del__ logs sprite counts without errors."""
        engine = _make_engine(mocker)
        # Should not raise
        del engine


class TestGameEngineQuitGame:
    """Test GameEngine.quit_game class method."""

    def test_quit_game_posts_quit_event(self):
        """quit_game puts one QUIT event on SDL's real queue."""
        pygame.event.clear(pygame.QUIT)

        GameEngine.quit_game()

        assert len(pygame.event.get(pygame.QUIT)) == 1


class TestGetAttrAttributeError:
    """Test GameEngine.__getattr__ raises AttributeError (line 1532)."""

    def test_non_event_attribute_raises(self, mocker):
        """Test __getattr__ raises AttributeError for non-event attributes."""
        engine = _make_engine(mocker)

        with pytest.raises(AttributeError, match="has no attribute 'some_random_attr'"):
            engine.some_random_attr  # ruff: ignore[useless-expression]


class TestGameEngineLinuxVideoDriverArgs:
    """Test GameEngine platform-specific video driver args (lines 205-230)."""

    @staticmethod
    def _video_driver_choices(mocker, *, system_name: str) -> list[str] | None:
        """Build the real argument parser as on system_name; return --video-driver's choices.

        Returns:
            The choices of the --video-driver option.

        """
        mocker.patch('platform.system', return_value=system_name)
        parser = GameEngine.args(argparse.ArgumentParser())
        (video_driver_action,) = [
            action for action in parser._actions if '--video-driver' in action.option_strings
        ]
        return video_driver_action.choices

    def test_linux_video_drivers(self, mocker):
        """On Linux, --video-driver offers the Linux drivers."""
        choices = self._video_driver_choices(mocker, system_name='Linux')
        assert choices is not None
        assert 'x11' in choices
        assert 'wayland' in choices

    def test_mac_video_drivers(self, mocker):
        """The 'MacOS' branch offers no drivers (platform.system() says 'Darwin' on a Mac)."""
        assert self._video_driver_choices(mocker, system_name='MacOS') == []

    def test_windows_video_drivers(self, mocker):
        """On Windows, --video-driver offers the Windows drivers."""
        choices = self._video_driver_choices(mocker, system_name='Windows')
        assert choices == ['windib', 'directx']


class TestGameEngineFastEvents:
    """Test USE_FASTEVENTS path (lines 341, 354-355, 924).

    Note: pygame.fastevent was removed in modern pygame versions.
    We mock the fastevent module to test these legacy code paths.
    """

    def test_use_fastevents_with_old_pygame(self, mocker):
        """Test USE_FASTEVENTS is set for old pygame versions (line 341)."""
        # Mock pygame version to be < 2.2 (both major < 2 AND minor < 2)
        mocker.patch.object(pygame.version, 'vernum', (1, 1, 0))
        # Create a fake fastevent module
        mock_fastevent = mocker.Mock()
        mocker.patch.object(pygame, 'fastevent', mock_fastevent, create=True)
        # The engine sets the class attribute; patching it undoes that at teardown (BUGS.md #65)
        mocker.patch.object(GameEngine, 'USE_FASTEVENTS', new=False)

        engine = _make_engine(mocker)
        assert engine.USE_FASTEVENTS is True
        mock_fastevent.init.assert_called_once()

    def test_process_events_with_fastevents(self, mocker):
        """Test process_events uses fastevent.get when USE_FASTEVENTS is True (line 924)."""
        engine = _make_engine(mocker)
        # The live doors decide fastevent use when created (glitchygames/live_sources.py)
        install_sources(sources=LiveSources(random_seed=engine.random_seed, use_fastevents=True))
        # Create a fake fastevent module
        mock_fastevent = mocker.Mock()
        mock_fastevent.get.return_value = []
        mocker.patch.object(pygame, 'fastevent', mock_fastevent, create=True)

        result = engine.process_events()
        assert result is False
        mock_fastevent.get.assert_called_once()


class TestGameEngineFullscreen:
    """Test fullscreen mode flags (line 381)."""

    def test_fullscreen_mode_flags(self, mocker):
        """Test fullscreen mode sets correct flags (line 381)."""
        # --windowed is a store_true flag that defaults to True, so no command line reaches
        # fullscreen: the parsed option is set directly. PlainWindowEngine never opens it
        engine = _make_engine(mocker, option_overrides={'windowed': False})
        assert engine.mode_flags & pygame.FULLSCREEN


class TestGameEngineInvalidUpdateType:
    """Test invalid update_type logs error (line 424)."""

    def test_invalid_update_type_logs_error(self, mocker, caplog):
        """Test invalid update_type logs an error (line 424)."""
        # --update-type only accepts update or flip, so the parsed option is set directly
        with caplog.at_level(logging.ERROR, logger=GameEngine.log.name):
            engine = _make_engine(mocker, option_overrides={'update_type': 'invalid_type'})

        assert 'Screen update type was neither "update" nor "flip".' in caplog.text
        # The display still opens
        assert engine.screen is pygame.display.get_surface()


class TestGameEngineDel:
    """Test GameEngine __del__ with sprite counters (lines 509-510)."""

    def test_del_logs_sprite_counters(self, mocker):
        """Test __del__ iterates sprite counters (lines 509-510)."""
        from glitchygames.sprites import Sprite

        engine = _make_engine(mocker)

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


class TestGameEngineTimerCalibration:
    """--timer-backend auto: a paced game calibrates its timer as the engine starts."""

    def _start_with_timer(self, *, engine, mocker, target_fps):
        """Start the engine with a mock timer and the given target FPS; return the order of calls.

        Returns:
            The calls, in order: 'calibrate' (the timer's) and 'first frame' (the scenes').

        """
        calls = []
        timer = mocker.Mock()
        timer.calibrate.side_effect = lambda: calls.append('calibrate')
        mocker.patch('glitchygames.engine.game_engine.create_timer', return_value=timer)
        mocker.patch('glitchygames.performance.performance_manager')
        mocker.patch.object(GameEngine, 'game', mocker.Mock())
        mocker.patch.object(
            GameEngine,
            'OPTIONS',
            {
                'profile': False,
                'timer_backend': 'auto',
                'target_fps': target_fps,
                'perf_trim_percent': 5.0,
            },
        )
        engine.scene_manager = mocker.Mock()
        engine.scene_manager.start.side_effect = lambda: calls.append('first frame')
        engine._initialize_event_managers = mocker.Mock()
        engine._shutdown = mocker.Mock()
        engine.start()
        return calls

    def test_a_paced_game_calibrates_before_its_first_frame(self, mocker):
        engine = _make_engine(mocker)
        calls = self._start_with_timer(engine=engine, mocker=mocker, target_fps=60.0)
        assert calls == ['calibrate', 'first frame']

    def test_an_uncapped_game_does_not_calibrate(self, mocker):
        engine = _make_engine(mocker)
        calls = self._start_with_timer(engine=engine, mocker=mocker, target_fps=0.0)
        assert calls == ['first frame']


class TestGameEngineTimerBackendError:
    """Test timer backend initialization failure (lines 828-830)."""

    def test_timer_backend_value_error(self, mocker):
        """Test timer backend ValueError sets timer to None (lines 828-830)."""
        engine = _make_engine(mocker)

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

    def test_shutdown_performance_import_error(self, mocker):
        """Test _shutdown handles ImportError for performance module (lines 784-785)."""
        engine = _make_engine(mocker)

        # Mock the performance import to fail
        mocker.patch.dict('sys.modules', {'glitchygames.performance': None})

        try:
            # _shutdown goes on past the ImportError: it still quits pygame, for real
            engine._shutdown()

            assert not pygame.get_init()
        finally:
            # Later tests on this worker need pygame and the default display
            pygame.init()
            pygame.display.set_mode((800, 600))


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

    @pytest.mark.parametrize(('text', 'expected'), [('0', 0.0), ('12.5', 12.5)])
    def test_non_negative_percent_accepts_zero_and_up(self, text, expected):
        """--max-processing-slowdown takes any finite percentage >= 0."""
        assert non_negative_percent(text) == expected

    @pytest.mark.parametrize(
        ('text', 'reason'),
        [
            ('fast', 'is not a number'),
            ('-1', 'must be a finite number >= 0'),
            ('inf', 'must be a finite number >= 0'),
            ('nan', 'must be a finite number >= 0'),
        ],
    )
    def test_non_negative_percent_rejects(self, text, reason):
        """Non-numeric, negative and non-finite text is refused with its reason."""
        with pytest.raises(argparse.ArgumentTypeError, match=reason):
            non_negative_percent(text)

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
        with pytest.raises(SystemExit) as exit_info:
            self._parse(['--fps-histogram', 'logarithmic'])
        assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR
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

    def test_start_passes_the_mode_to_the_performance_manager(self, mocker):
        """Test start() calls set_histogram_mode with the parsed option."""
        engine = _make_engine(mocker)
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

    def test_an_unknown_histogram_mode_is_logged_and_the_run_goes_on(self, mocker, caplog):
        """A mode the performance manager refuses (set in OPTIONS, not parsed) never ends a run."""
        from glitchygames.performance import performance_manager

        engine = _make_engine(mocker)
        mocker.patch('glitchygames.engine.game_engine.create_timer')
        # The real manager is process-wide: put its settings back after the test
        mocker.patch.object(performance_manager, '_trim_percent', performance_manager._trim_percent)
        mocker.patch.object(
            performance_manager, '_histogram_mode', performance_manager._histogram_mode
        )
        histogram_mode_before = performance_manager._histogram_mode
        mocker.patch.object(GameEngine, 'game', mocker.Mock())
        mocker.patch.object(
            GameEngine,
            'OPTIONS',
            {
                'profile': False,
                'timer_backend': 'fast',
                'perf_trim_percent': 7.5,
                'fps_histogram': 'sideways',
            },
        )
        engine.scene_manager = mocker.Mock()
        engine._initialize_event_managers = mocker.Mock()
        engine._shutdown = mocker.Mock()

        with caplog.at_level(logging.DEBUG, logger=engine.log.name):
            engine.start()

        assert 'FPS histogram mode configuration failed' in caplog.text
        assert "Unknown FPS histogram mode 'sideways'" in caplog.text
        assert performance_manager._histogram_mode == histogram_mode_before
        assert performance_manager._trim_percent == 7.5
        engine._shutdown.assert_called_once()

    def test_start_sets_the_mode_even_when_set_trim_percent_raises(self, mocker):
        """Test a bad trim value cannot skip setting the histogram mode."""
        engine = _make_engine(mocker)
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


class TestReplayRestartExitStatus:
    """A watched replay's restart exits with the status the restarted replays ended with."""

    def test_a_status_no_exit_code_names_is_passed_through(self, mocker, tmp_path, caplog):
        """A restarted replay that ends with a game's own status (42) ends this run with it."""
        game_own_exit_status = 42
        relaunch = mocker.patch.object(
            game_engine_module, 'relaunch_replay', return_value=game_own_exit_status
        )
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        tamper_first_sprite_rect(recording_path=recording_path, frame_number=3)
        # Space starts the replay; it pauses after the divergent frame 3, and , steps back
        press_keys_while_held(mocker=mocker, keys=(pygame.K_SPACE, pygame.K_COMMA))

        with (
            caplog.at_level(logging.INFO, logger=GameEngine.log.name),
            pytest.raises(SystemExit) as exit_info,
        ):
            replay_session_with_arguments(
                recording_path=recording_path, mocker=mocker, arguments=()
            )

        relaunch.assert_called_once()
        assert exit_info.value.code == game_own_exit_status
        assert f'Exiting with {ExitCode.describe_status(game_own_exit_status)}' in caplog.text
