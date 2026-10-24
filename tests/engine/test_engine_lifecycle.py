"""Tests for GameEngine lifecycle functionality.

This module tests GameEngine start/stop, game loop, and quit functionality. Every engine here is
real: real pygame, the real display, real event managers and the real SceneManager loop. A game
ends its own run in its first frame, by quitting or by raising; only failures a game cannot
cause (a teardown or an event manager that breaks) are simulated with targeted mocks.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, ClassVar

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.record_golden_traces import GoldenTraceEngine

from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.events.audio import AudioEventManager
from glitchygames.events.joystick import JoystickEventManager
from glitchygames.events.keyboard import KeyboardEventManager
from glitchygames.events.mouse import MouseEventManager
from glitchygames.exit_codes import ExitCode
from glitchygames.host import HostSources
from glitchygames.live_sources import LiveSources
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sources import active_sources

# GameEngine parses sys.argv when it is constructed: a small window (the conftest puts the
# 800x600 test display back after the test), no frame pacing, quiet logs
ENGINE_ARGUMENTS = ('--resolution', '320x240', '--log-level', 'warning', '--target-fps', '0')

# What the engine's log line names when no scene can be found (_resolve_scene_name_for_error)
NO_SCENE_NAME = 'None'

# Why GameWhoseConstructorRaises cannot be built
CONSTRUCTOR_ERROR_MESSAGE = 'the game could not be built'

# What cProfile's print_stats() prints first
PROFILE_REPORT_MARKER = 'function calls'


class FirstFrameGame(Scene):
    """A game that ends the run in its first frame: it quits, or raises RUN_ERROR."""

    NAME = 'FirstFrameGame'
    VERSION = '1.0'
    # Raised from the first frame's logic; None quits the game instead
    RUN_ERROR: ClassVar[BaseException | None] = None

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Start counting the frames whose logic ran."""
        super().__init__(options=options, groups=groups)
        self.frames_run = 0

    def dt_tick(self, dt: float) -> None:
        """Run one frame of logic: raise RUN_ERROR, or ask the scene manager to quit."""
        super().dt_tick(dt)
        self.frames_run += 1
        if self.RUN_ERROR is not None:
            raise self.RUN_ERROR
        self.scene_manager.quit()


def first_frame_game(*, run_error: BaseException | None = None) -> type[FirstFrameGame]:
    """Return a FirstFrameGame class whose first frame raises ``run_error`` (None: quits).

    Returns:
        A new subclass, so no test changes the class another test uses.

    """
    return type('FirstFrameGame', (FirstFrameGame,), {'RUN_ERROR': run_error})


class NextSceneGame(FirstFrameGame):
    """A game whose first frame switches to its NEXT_SCENE_CLASS instead of ending the run."""

    NAME = 'NextSceneGame'
    NEXT_SCENE_CLASS: ClassVar[type[Scene]] = FirstFrameGame

    def dt_tick(self, dt: float) -> None:
        """Switch to the next scene (the scene manager switches at the end of the frame)."""
        self.frames_run += 1
        self.next_scene = self.NEXT_SCENE_CLASS(options=self.options)


class GameWhoseConstructorRaises(Scene):
    """A game that fails before any scene is active: its constructor raises."""

    NAME = 'GameWhoseConstructorRaises'
    VERSION = '1.0'

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Fail at once.

        Raises:
            RuntimeError: Always.

        """
        raise RuntimeError(CONSTRUCTOR_ERROR_MESSAGE)


@pytest.fixture
def engine_run_environment(mocker):
    """Let a test construct and start a real engine, leaving pygame usable for later tests.

    GameEngine._shutdown quits the display and pygame at the end of a run; every later test on
    the worker still needs them (the conftest keeps one pygame and one display for the run). The
    engine also writes SDL hints to the environment and its event managers block and allow
    event types: all of it is put back afterwards.

    Yields:
        None, while the environment is in place.

    """
    mocker.patch.object(pygame, 'quit')
    mocker.patch.object(pygame.display, 'quit')
    mocker.patch.dict(os.environ)
    blocked_before = [
        pygame.event.get_blocked(event_type) for event_type in range(pygame.NUMEVENTS)
    ]
    yield
    pygame.event.clear()
    for event_type, was_blocked in enumerate(blocked_before):
        if was_blocked:
            pygame.event.set_blocked(event_type)
        else:
            pygame.event.set_allowed(event_type)


def build_engine(mocker, *, game: type[Scene], extra_arguments: tuple[str, ...] = ()):
    """Construct a real engine for ``game`` on ENGINE_ARGUMENTS plus ``extra_arguments``.

    The engine is GoldenTraceEngine (scripts/record_golden_traces.py): GameEngine opening a
    plain window, because SDL's dummy video driver warns "no fast renderer available" for
    GameEngine's SCALED window, an error under pytest's filterwarnings.

    Returns:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_engine_lifecycle', *ENGINE_ARGUMENTS, *extra_arguments])
    return GoldenTraceEngine(game=game)


def logged_crash_scene_names(caplog) -> list[str]:
    """Return the scene names the engine logged with 'Runtime error during game execution'.

    Returns:
        list[str]: One name per crash logged.

    """
    return [
        record.args[0]
        for record in caplog.records
        if record.msg.startswith('Runtime error during game execution')
    ]


@pytest.mark.usefixtures('engine_run_environment')
class TestEngineLifecycle:
    """Test GameEngine lifecycle functionality."""

    def test_game_engine_quit_game(self, mocker):
        """quit_game posts a QUIT event, and processing it asks the scene manager to stop."""
        engine = build_engine(mocker, game=first_frame_game())
        engine.install_game(scene_class=first_frame_game())
        pygame.event.clear()

        engine.quit_game()

        assert pygame.event.peek(pygame.QUIT)
        assert engine.scene_manager.quit_requested is False
        engine.process_events()
        assert engine.scene_manager.quit_requested is True

    def test_game_engine_start_runs_the_game_until_it_quits(self, mocker):
        """start() builds the game, runs its frames until it quits, and returns normally."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class)
        shutdown = mocker.spy(engine, '_shutdown')

        engine.start()

        assert isinstance(engine.game, game_class)
        assert engine.game.frames_run == 1
        # The scene manager ended its loop by switching away from the game
        assert engine.scene_manager.active_scene is None
        shutdown.assert_called_once_with(run_ended_by=None)

    def test_game_engine_start_with_profiling(self, mocker, capsys):
        """A --profile run profiles the whole run and prints the profile after the teardown."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class, extra_arguments=('--profile',))

        engine.start()

        assert engine.game.frames_run == 1
        assert PROFILE_REPORT_MARKER in capsys.readouterr().out

    def test_game_engine_start_without_profiling_prints_no_profile(self, mocker, capsys):
        """Without --profile, no profile is printed."""
        engine = build_engine(mocker, game=first_frame_game())

        engine.start()

        assert PROFILE_REPORT_MARKER not in capsys.readouterr().out

    def test_game_engine_start_with_exception(self, mocker, caplog):
        """An exception in the game's logic ends the run as an internal error, logged."""
        run_error = RuntimeError('Test exception')
        engine = build_engine(mocker, game=first_frame_game(run_error=run_error))

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()

        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is run_error

    def test_start_method_initializes_real_managers(self, mocker):
        """start() makes the game and the engine's event managers, wired to the scene manager."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class)

        engine.start()

        assert isinstance(engine.game, game_class)
        assert SceneManager.OPTIONS is GameEngine.OPTIONS
        assert engine.scene_manager.game_engine is engine
        for manager, manager_class in (
            (engine.audio_manager, AudioEventManager),
            (engine.joystick_manager, JoystickEventManager),
            (engine.keyboard_manager, KeyboardEventManager),
            (engine.mouse_manager, MouseEventManager),
        ):
            assert isinstance(manager, manager_class)
            assert manager.game is engine.scene_manager
        # The devices the game sees follow the managers' (whatever hardware is attached)
        assert engine.scene_manager.input_devices is engine.input_devices
        assert len(engine.input_devices) <= len(engine.joystick_manager.joysticks)

    def test_start_prints_the_profile_of_a_run_that_failed_at_once(self, mocker, caplog, capsys):
        """A --profile run that fails at its first step still prints the profile it took."""
        engine = build_engine(mocker, game=first_frame_game(), extra_arguments=('--profile',))
        install_error = RuntimeError('no handlers')
        # Simulated: the first step of the run fails
        mocker.patch.object(engine, '_install_signal_handlers', side_effect=install_error)

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()

        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is install_error
        assert PROFILE_REPORT_MARKER in capsys.readouterr().out

    def test_start_method_exception_handling(self, mocker, caplog):
        """An event manager that fails to start ends the run as an internal error, logged."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class)
        manager_error = Exception('AudioEventManager failed')
        # Simulated, after construction (which reads AudioEventManager.args): the audio event
        # manager cannot be made
        mocker.patch.object(game_engine_module, 'AudioEventManager', side_effect=manager_error)

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()

        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is manager_error
        crash_records = [record for record in caplog.records if record.exc_info is not None]
        assert [record.exc_info[1] for record in crash_records] == [manager_error]
        # The game was built before the managers, and never ran a frame
        assert isinstance(engine.game, game_class)
        assert engine.game.frames_run == 0

    def test_start_method_error_message_with_current_scene(self, mocker, caplog):
        """A crash in the active scene's logic is logged with that scene's name."""
        game_class = first_frame_game(run_error=RuntimeError('Test exception'))
        engine = build_engine(mocker, game=game_class)

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit):
            engine.start()

        assert logged_crash_scene_names(caplog) == [game_class.NAME]

    def test_start_method_error_message_with_previous_scene(self, mocker, caplog):
        """A crash in the scene switched to is logged with its name, not the previous scene's."""
        crashing_scene_class = first_frame_game(run_error=RuntimeError('Test exception'))
        crashing_scene_class.NAME = 'CrashingScene'
        game_class = type(
            'NextSceneGame', (NextSceneGame,), {'NEXT_SCENE_CLASS': crashing_scene_class}
        )
        engine = build_engine(mocker, game=game_class)

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit):
            engine.start()

        # The switch happened: the game scene ran, then the scene it switched to
        assert engine.scene_manager.previous_scene is engine.game
        assert logged_crash_scene_names(caplog) == ['CrashingScene']

    def test_start_method_error_message_with_no_scenes(self, mocker, caplog):
        """A crash before any scene is active (the game cannot be built) is logged as 'None'."""
        engine = build_engine(mocker, game=GameWhoseConstructorRaises)

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()

        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert engine.scene_manager.active_scene is None
        assert engine.scene_manager.previous_scene is None
        assert logged_crash_scene_names(caplog) == [NO_SCENE_NAME]


def engine_whose_run_raises(*, mocker, run_error: BaseException | None) -> GameEngine:
    """Build a real engine whose game's first frame raises ``run_error`` (None: quits).

    Returns:
        The engine, with ``_shutdown`` spied on.

    """
    engine = build_engine(mocker, game=first_frame_game(run_error=run_error))
    mocker.spy(engine, '_shutdown')
    return engine


@pytest.mark.usefixtures('engine_run_environment')
class TestStartExitStatus:
    """How GameEngine.start() ends: crashes exit as internal errors, deliberate exits pass."""

    def test_an_uncaught_exception_exits_as_an_internal_error_after_teardown(self, mocker, caplog):
        run_error = RuntimeError('the game broke')
        engine = engine_whose_run_raises(mocker=mocker, run_error=run_error)
        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is run_error
        assert f'Exiting with {ExitCode.INTERNAL_ERROR.describe()}' in caplog.text
        engine._shutdown.assert_called_once_with(run_ended_by=ExitCode.INTERNAL_ERROR.describe())
        crash_records = [record for record in caplog.records if record.exc_info is not None]
        assert len(crash_records) == 1
        assert crash_records[0].exc_info[1] is run_error

    def test_a_deliberate_system_exit_passes_through_unchanged(self, mocker):
        engine = engine_whose_run_raises(
            mocker=mocker, run_error=SystemExit(ExitCode.REPLAY_DIVERGED)
        )
        with pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.REPLAY_DIVERGED
        engine._shutdown.assert_called_once_with(
            run_ended_by=ExitCode.describe_status(ExitCode.REPLAY_DIVERGED)
        )

    def test_a_keyboard_interrupt_exits_as_interrupted_after_teardown(self, mocker, caplog):
        """Ctrl-C is never an internal error: it exits INTERRUPTED once teardown has run."""
        engine = engine_whose_run_raises(mocker=mocker, run_error=KeyboardInterrupt())
        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERRUPTED
        engine._shutdown.assert_called_once_with(run_ended_by=ExitCode.INTERRUPTED.describe())
        assert f'Exiting with {ExitCode.INTERRUPTED.describe()}' in caplog.text
        assert all(record.exc_info is None for record in caplog.records)

    def test_signal_handlers_are_restored_even_when_the_teardown_does_not(self, mocker):
        """start() restores what it installed itself, so a mocked _shutdown leaks nothing."""
        handlers_before = {
            signal_number: signal.getsignal(signal_number)
            for signal_number in game_engine_module.terminating_signals()
        }
        engine = engine_whose_run_raises(mocker=mocker, run_error=None)
        # Simulated: a teardown that restores nothing
        mocker.patch.object(engine, '_shutdown')
        engine.start()
        assert {
            signal_number: signal.getsignal(signal_number) for signal_number in handlers_before
        } == handlers_before

    @pytest.mark.parametrize(
        'run_error', [None, RuntimeError('the game broke')], ids=['clean run', 'crashed run']
    )
    def test_a_teardown_failure_exits_as_an_internal_error(self, mocker, caplog, run_error):
        """A _shutdown that raises never leaves Python to exit 1; every error is logged."""
        teardown_error = RuntimeError('the teardown broke')
        engine = engine_whose_run_raises(mocker=mocker, run_error=run_error)
        # Simulated: the teardown fails
        mocker.patch.object(engine, '_shutdown', side_effect=teardown_error)
        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            engine.start()
        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is teardown_error
        logged_errors = [record.exc_info[1] for record in caplog.records if record.exc_info]
        expected_errors = [teardown_error] if run_error is None else [run_error, teardown_error]
        assert logged_errors == expected_errors
        assert f'Exiting with {ExitCode.INTERNAL_ERROR.describe()}' in caplog.text


# Outer ticks for start_async: 60 Hz timestamps, and a cap so a run that never ends fails
ASYNC_TICK_SECONDS = 1 / 60
ASYNC_TICK_LIMIT = 600


def async_ticks() -> tuple[list[float], Any]:
    """Return a tick log and a wait_for_tick that appends 60 Hz timestamps to it.

    Returns:
        The tick timestamps so far, and the awaitable tick source.

    """
    ticks: list[float] = []

    async def wait_for_tick() -> float:
        await asyncio.sleep(0)
        ticks.append(len(ticks) * ASYNC_TICK_SECONDS)
        if len(ticks) > ASYNC_TICK_LIMIT:
            message = f'the run was still going after {ASYNC_TICK_LIMIT} ticks'
            raise AssertionError(message)
        return ticks[-1]

    return ticks, wait_for_tick


@pytest.mark.usefixtures('engine_run_environment')
class TestHostedRuns:
    """A live run is hosted (glitchygames/host.py); start_async drives it one tick at a time."""

    def test_a_live_run_reads_through_the_host_doors(self, mocker):
        """The installed doors are the host's, around the live doors."""
        engine = build_engine(mocker, game=first_frame_game())

        assert engine.host is not None
        assert active_sources() is engine.host.sources
        assert isinstance(engine.host.sources, HostSources)
        assert isinstance(engine.host.sources.inner, LiveSources)

    def test_start_async_runs_the_game_until_it_quits(self, mocker):
        """start_async builds the game, runs its frames on the ticks, and ends normally."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class)
        shutdown = mocker.spy(engine, '_shutdown')
        ticks, wait_for_tick = async_ticks()

        asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

        assert isinstance(engine.game, game_class)
        assert engine.game.frames_run == 1
        assert engine.scene_manager.active_scene is None
        assert ticks
        shutdown.assert_called_once_with(run_ended_by=None)

    def test_start_async_exits_like_start_after_an_uncaught_exception(self, mocker, caplog):
        """The async run shares start()'s crash boundary: the same exit code and cause."""
        run_error = RuntimeError('Test exception')
        engine = build_engine(mocker, game=first_frame_game(run_error=run_error))
        _, wait_for_tick = async_ticks()

        with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as exit_info:
            asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

        assert exit_info.value.code == ExitCode.INTERNAL_ERROR
        assert exit_info.value.__cause__ is run_error

    def test_start_async_refuses_an_unhosted_run(self, mocker):
        """Only live runs are hosted; a run without a host (a replay) cannot start async."""
        engine = build_engine(mocker, game=first_frame_game())
        engine.host = None
        _, wait_for_tick = async_ticks()

        with pytest.raises(RuntimeError, match='runs live games only'):
            asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))
