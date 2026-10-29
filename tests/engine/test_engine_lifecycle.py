"""Tests for GameEngine lifecycle functionality.

This module tests GameEngine start/stop, game loop, and quit functionality. Every engine here is
real: real pygame, the real display, real event managers and the real SceneManager loop. A game
ends its own run in its first frame, by quitting or by raising; only failures a game cannot
cause (a teardown or an event manager that breaks) are simulated with targeted mocks.
"""

import asyncio
import errno
import itertools
import logging
import os
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import pygame
import pytest

from glitchygames.crt_power_on import PowerOnOutcome
from glitchygames.engine import GameEngine
from glitchygames.engine import game_engine as game_engine_module
from glitchygames.events.audio import AudioEventManager
from glitchygames.events.joystick import JoystickEventManager
from glitchygames.events.keyboard import KeyboardEventManager
from glitchygames.events.mouse import MouseEventManager
from glitchygames.exit_codes import BUG_REPORT_HINT, ExitCode
from glitchygames.host import HostSources
from glitchygames.input import device_listing
from glitchygames.live_sources import LiveSources
from glitchygames.recording import RecordingWriteError
from glitchygames.replay.tools import registry
from glitchygames.replay.tools.golden_traces import GoldenTraceEngine
from glitchygames.replay.tools.registry import Tool
from glitchygames.scenes import Scene, SceneManager
from glitchygames.sources import active_sources
from glitchygames.timing import FastTimer
from tests.input.stand_in_devices import STAND_IN_PAD, STAND_IN_STICK, install_stand_in_devices

if TYPE_CHECKING:
    import argparse

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

    The engine is GoldenTraceEngine (glitchygames/replay/tools/golden_traces.py): GameEngine
    opening a plain window, because SDL's dummy video driver warns "no fast renderer available"
    for GameEngine's SCALED window, an error under pytest's filterwarnings.

    Returns:
        GoldenTraceEngine: The engine, constructed (not started).

    """
    mocker.patch.object(sys, 'argv', ['test_engine_lifecycle', *ENGINE_ARGUMENTS, *extra_arguments])
    return GoldenTraceEngine(game=game)


def bug_report_hints_follow_each_traceback(caplog) -> bool:
    """Tell whether every record with a traceback is followed by the bug-report hint at ERROR.

    Returns:
        True when there is at least one traceback and the next record after each is
        ``BUG_REPORT_HINT``, logged at ERROR.

    """
    records = caplog.records
    traceback_positions = [index for index, record in enumerate(records) if record.exc_info]
    return bool(traceback_positions) and all(
        index + 1 < len(records)
        and records[index + 1].getMessage() == BUG_REPORT_HINT
        and records[index + 1].levelno == logging.ERROR
        for index in traceback_positions
    )


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
        # Exit 70: the player is told how to report it, after the traceback
        assert bug_report_hints_follow_each_traceback(caplog)

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
        assert BUG_REPORT_HINT not in caplog.text

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
        assert bug_report_hints_follow_each_traceback(caplog)
        assert f'Exiting with {ExitCode.INTERNAL_ERROR.describe()}' in caplog.text


# Outer ticks for start_async: 60 Hz timestamps, and a cap so a run that never ends fails
ASYNC_TICK_SECONDS = 1 / 60
ASYNC_TICK_LIMIT = 600
# A paced game whose timer calibrates when made to (--timer-backend auto)
PACED_ARGUMENTS = ('--target-fps', '60', '--timer-backend', 'auto')


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
        """A run with neither a host nor a watched replay's viewer cannot start async."""
        engine = build_engine(mocker, game=first_frame_game())
        engine.host = None
        _, wait_for_tick = async_ticks()

        with pytest.raises(RuntimeError, match='runs live games and watched replays only'):
            asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

    def test_start_calibrates_a_paced_games_timer(self, mocker):
        """The blocking run paces with the timer, so --timer-backend auto measures it first."""
        engine = build_engine(mocker, game=first_frame_game(), extra_arguments=PACED_ARGUMENTS)
        calibrate = mocker.spy(FastTimer, 'calibrate')

        engine.start()

        # Again at its first paced frame (FastTimer.start_frame), where it does nothing
        calibrate.assert_called()

    def test_start_async_never_calibrates_the_timer(self, mocker):
        """The async run's outer tick is its wait: the timer never paces it, so it is not measured.

        The timer is still made: a recording names it (uncalibrated) in its provenance.
        """
        engine = build_engine(mocker, game=first_frame_game(), extra_arguments=PACED_ARGUMENTS)
        calibrate = mocker.spy(FastTimer, 'calibrate')
        _, wait_for_tick = async_ticks()

        asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

        calibrate.assert_not_called()
        assert isinstance(engine.timer, FastTimer)
        assert engine.timer.pacing_timer().sleep_model is None


@pytest.mark.usefixtures('engine_run_environment')
class TestListInputDevices:
    """--list-input-devices replaces the run (glitchygames/input/device_listing.py)."""

    def test_the_listing_replaces_the_game(self, mocker, capsys):
        """The devices are printed and the run ends normally; the game's scene is never built."""
        engine = build_engine(
            mocker, game=GameWhoseConstructorRaises, extra_arguments=('--list-input-devices',)
        )
        install_stand_in_devices(descriptors=[STAND_IN_STICK, STAND_IN_PAD])
        # A clock past the settling time at its second reading: one pump, no wait
        mocker.patch(
            'glitchygames.clock.measured_seconds', side_effect=itertools.count(start=0.0, step=5.0)
        )

        frames_started = mocker.spy(engine.scene_manager, 'start')

        engine.start()

        frames_started.assert_not_called()
        output = capsys.readouterr().out.splitlines()
        assert '  index 1  instance 9  Stand-in Game Pad' in output
        assert '  index 0  instance 5  Stand-in Flight Stick' in output
        assert output[-1] == '2 devices (1 game controller, 1 joystick only)'

    def test_an_async_run_lists_too_and_runs_no_frames(self, mocker, capsys):
        """start_async (a browser host) lists the devices and ends without a frame."""
        engine = build_engine(
            mocker, game=GameWhoseConstructorRaises, extra_arguments=('--list-input-devices',)
        )
        install_stand_in_devices(descriptors=[STAND_IN_STICK, STAND_IN_PAD])
        mocker.patch(
            'glitchygames.clock.measured_seconds', side_effect=itertools.count(start=0.0, step=5.0)
        )
        ticks, wait_for_tick = async_ticks()

        asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

        assert ticks == []
        assert capsys.readouterr().out.splitlines()[-1] == (
            '2 devices (1 game controller, 1 joystick only)'
        )

    @pytest.mark.parametrize(
        ('stdin_is_a_terminal', 'stdout_is_a_terminal'), [(False, True), (True, False)]
    )
    def test_it_never_prompts_without_a_terminal(
        self, mocker, stdin_is_a_terminal, stdout_is_a_terminal
    ):
        """A script, a pipe or CI gets the listing at once: no prompt, so no wait."""
        mocker.patch.object(sys.stdin, 'isatty', return_value=stdin_is_a_terminal)
        mocker.patch.object(sys.stdout, 'isatty', return_value=stdout_is_a_terminal)

        assert game_engine_module.input_device_prompt() is None

    def test_at_a_terminal_it_prompts_on_stdout(self, mocker, capsys):
        """At a terminal the prompt is written to stdout as its own line."""
        mocker.patch.object(sys.stdin, 'isatty', return_value=True)
        mocker.patch.object(sys.stdout, 'isatty', return_value=True)
        prompt = game_engine_module.input_device_prompt()
        assert prompt is not None

        prompt(device_listing.NO_DEVICES_PROMPT)

        assert capsys.readouterr().out == f'{device_listing.NO_DEVICES_PROMPT}\n'

    @pytest.mark.parametrize('flag', ['--replay-trace', '--record-trace'])
    def test_it_is_refused_with_a_replay_or_a_recording(self, mocker, tmp_path, caplog, flag):
        """There is no run to replay or record: OPTIONS_REFUSED, naming the option."""
        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--list-input-devices', flag, str(tmp_path / 'run.jsonl.gz')),
            )

        assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
        assert f'Cannot list input devices with {flag}: the listing replaces the run' in caplog.text


def tool_that_runs_no_game(*, calls: list[dict[str, Any]], exit_code: ExitCode) -> Tool:
    """A tool that runs instead of the game (``--report-thing PATH``), recording its calls.

    The real table holds only tools that run the game until later tasks add the others.

    Returns:
        The tool.

    """

    def handle(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
        calls.append({'path': options['report_thing'], 'game': game})
        return exit_code

    def never_run_as_a_command(
        *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
    ) -> int:
        raise AssertionError(tool.name)

    return Tool(
        name='report-thing',
        help='report on a recording',
        options=(),
        runs_game=False,
        game_handler=handle,
        command_handler=never_run_as_a_command,
    )


def tool_with_handler(*, handler: registry.GameHandler) -> Tool:
    """A tool that runs instead of the game (``--report-thing PATH``) with the given handler.

    Returns:
        The tool.

    """

    def never_run_as_a_command(
        *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
    ) -> int:
        raise AssertionError(tool.name)

    return Tool(
        name='report-thing',
        help='report on a recording',
        options=(),
        runs_game=False,
        game_handler=handler,
        command_handler=never_run_as_a_command,
    )


def raising_tool(*, error: BaseException) -> Tool:
    """A tool that runs instead of the game and raises ``error``.

    Returns:
        The tool.

    """

    def raise_error(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
        del options, game
        raise error

    return tool_with_handler(handler=raise_error)


@pytest.mark.usefixtures('engine_run_environment')
class TestGameFlagTools:
    """A tool flag with a game handler runs in place of the game (``run_game_flag_tool``).

    It runs while the engine is built, before the engine starts pygame or opens a window (Stage
    D, Task D4b: a harness tool builds its own engine, so a second one inside the game's must
    never start), and the process ends with the tool's exit code.
    """

    def test_the_tool_replaces_the_game(self, mocker):
        """The tool runs with the game and its options; pygame is never started for the game."""
        calls: list[dict[str, Any]] = []
        tool = tool_that_runs_no_game(calls=calls, exit_code=ExitCode.SUCCESS)
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, tool))
        pygame_started = mocker.spy(pygame, 'init')

        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--report-thing', 'run.jsonl.gz'),
            )

        assert exit_information.value.code == ExitCode.SUCCESS
        assert calls == [{'path': 'run.jsonl.gz', 'game': GameWhoseConstructorRaises}]
        pygame_started.assert_not_called()

    def test_a_tool_that_fails_ends_the_run_with_its_exit_code(self, mocker):
        """Any other exit code than SUCCESS ends the run with it, the game never built."""
        calls: list[dict[str, Any]] = []
        tool = tool_that_runs_no_game(calls=calls, exit_code=ExitCode.UNUSABLE_INPUT)
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, tool))

        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--report-thing', 'run.jsonl.gz'),
            )

        assert exit_information.value.code == ExitCode.UNUSABLE_INPUT
        assert len(calls) == 1

    def test_a_headless_tool_puts_the_sdl_driver_variables_back(self, mocker):
        """``--headless`` chose the dummy drivers for the tool; they are put back after it."""
        calls: list[dict[str, Any]] = []
        tool = tool_that_runs_no_game(calls=calls, exit_code=ExitCode.SUCCESS)
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, tool))
        mocker.patch.dict(os.environ, {'SDL_VIDEODRIVER': 'a-driver-of-its-own'})

        with pytest.raises(SystemExit):
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--headless', '--report-thing', 'run.jsonl.gz'),
            )

        assert len(calls) == 1
        assert os.environ['SDL_VIDEODRIVER'] == 'a-driver-of-its-own'

    def test_a_tool_that_crashes_exits_internal_error_as_the_run_would(self, mocker, caplog):
        """A tool's uncaught exception ends the process INTERNAL_ERROR, logged, as start()'s run."""
        tool = raising_tool(error=RuntimeError('the tool broke'))
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, tool))

        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--report-thing', 'run.jsonl.gz'),
            )

        assert exit_information.value.code == ExitCode.INTERNAL_ERROR
        assert 'the tool broke' in caplog.text
        # A game takes --log-level, so its tool's crash tells the player to rerun it at info
        assert bug_report_hints_follow_each_traceback(caplog)

    def test_ctrl_c_in_a_tool_exits_interrupted(self, mocker):
        """Ctrl-C (KeyboardInterrupt) during a tool exits INTERRUPTED, as during a run."""
        tool = raising_tool(error=KeyboardInterrupt())
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, tool))

        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--report-thing', 'run.jsonl.gz'),
            )

        assert exit_information.value.code == ExitCode.INTERRUPTED

    def test_a_tool_whose_recording_fails_part_way_exits_cannot_write_output(self, mocker):
        """A recording write that fails part way exits CANNOT_WRITE_OUTPUT, as during a run."""
        failure = RecordingWriteError(
            path=Path('run.jsonl.gz'), cause=OSError(errno.ENOSPC, 'No space left on device')
        )
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, raising_tool(error=failure)))

        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--report-thing', 'run.jsonl.gz'),
            )

        assert exit_information.value.code == ExitCode.CANNOT_WRITE_OUTPUT

    def test_sigterm_in_a_tool_exits_with_the_signals_code(self, mocker):
        """SIGTERM during a tool ends it through the engine's handler; the handler goes after."""
        mocker.patch.object(signal, 'getsignal', return_value=signal.SIG_DFL)
        installed = mocker.patch.object(signal, 'signal')

        def send_sigterm(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
            del options, game
            # The handler the engine installed for SIGTERM, called as the signal would call it
            handlers = {call.args[0]: call.args[1] for call in installed.call_args_list}
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            return ExitCode.SUCCESS

        tool = tool_with_handler(handler=send_sigterm)
        mocker.patch.object(registry, 'TOOLS', (*registry.TOOLS, tool))

        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--report-thing', 'run.jsonl.gz'),
            )

        assert exit_information.value.code == ExitCode.for_signal(signal.SIGTERM)
        # Put back to the default once the tool ended
        assert installed.call_args_list[-1].args[1] is signal.SIG_DFL

    def test_a_golden_trace_of_a_game_that_crashes_exits_internal_error(self, mocker, tmp_path):
        """``--record-golden-trace`` of a game whose scene raises: INTERNAL_ERROR, as on BASE."""
        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=(
                    '--record-golden-trace',
                    str(tmp_path / 'golden.jsonl.gz'),
                    '--input-script',
                    'glitchygames.replay.tools.golden_traces:InputScript',
                    '--frame-count',
                    '1',
                ),
            )

        assert exit_information.value.code == ExitCode.INTERNAL_ERROR


def game_with_its_own_argument(*flags: str) -> type[Scene]:
    """A game whose own ``args`` adds an argument with these flags.

    Returns:
        The game's class.

    """

    class GameWithItsOwnArgument(Scene):
        NAME = 'GameWithItsOwnArgument'
        VERSION = '1.0'

        @classmethod
        def args(cls, parser: argparse._ArgumentGroup) -> None:
            parser.add_argument(*flags, action='store_true', help="the game's own")

    return GameWithItsOwnArgument


@pytest.mark.usefixtures('engine_run_environment')
class TestAGameArgumentTheEngineReserves:
    """A game argument named as one of the engine's: a clear refusal, never a traceback.

    Every tool's flag and option is added to every game (``registry.add_game_flags``), so an
    unseen game that already has ``--force`` (``--measure``'s) fails to build its parser. The
    refusal names the flag, says the engine reserves it, and exits ``OPTIONS_REFUSED`` (64), the
    engine's usage-error code, on every run of the game.
    """

    def test_a_tool_option_is_named_as_reserved_for_the_engines_tools(self, mocker, capsys):
        """``--force`` in the game: refused, naming ``--force`` and the tools' help."""
        with pytest.raises(SystemExit) as exit_information:
            build_engine(mocker, game=game_with_its_own_argument('--force'))

        assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
        error = capsys.readouterr().err
        assert (
            "GameWithItsOwnArgument's argument --force: --force is reserved by the engine for its "
            'tools (glitchygames --help lists them)'
        ) in error
        assert 'Traceback' not in error

    def test_an_engine_option_is_named_as_reserved_for_the_engine(self, mocker, capsys):
        """``--resolution`` in the game: refused, naming it as the engine's own option."""
        with pytest.raises(SystemExit) as exit_information:
            build_engine(mocker, game=game_with_its_own_argument('--resolution'))

        assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
        error = capsys.readouterr().err
        assert '--resolution is reserved by the engine (an option of every game' in error


@pytest.mark.usefixtures('engine_run_environment')
class TestTheRunsSeedIsLogged:
    """Every run logs the seed it uses, rolled or given, so a plain run can be reproduced."""

    def test_a_run_without_a_seed_logs_the_one_it_rolled(self, mocker, caplog):
        """No ``--random-seed``: the rolled seed is logged at INFO."""
        caplog.set_level(logging.INFO)

        engine = build_engine(mocker, game=first_frame_game())

        assert f'Random seed {engine.random_seed} (rolled)' in caplog.text

    def test_a_run_given_a_seed_logs_it(self, mocker, caplog):
        """``--random-seed N``: N is logged at INFO."""
        caplog.set_level(logging.INFO)

        engine = build_engine(
            mocker, game=first_frame_game(), extra_arguments=('--random-seed', '5')
        )

        assert engine.random_seed == 5
        assert 'Random seed 5 (given)' in caplog.text


@pytest.mark.usefixtures('engine_run_environment')
class TestCrtPowerOnOption:
    """--crt-power-on chooses when the power-on sequence plays (glitchygames/crt_power_on.py)."""

    def test_the_option_is_unset_by_default(self, mocker):
        """Unset, the environment then auto decide (crt_power_on.resolve_mode)."""
        build_engine(mocker, game=first_frame_game())

        assert GameEngine.OPTIONS['crt_power_on'] is None

    @pytest.mark.parametrize('flag', ['--replay-trace', '--record-trace'])
    def test_forcing_it_on_is_refused_with_a_replay_or_a_recording(
        self, mocker, tmp_path, caplog, flag
    ):
        """Before frame 0 of a recorded or replayed run, nothing may happen."""
        with pytest.raises(SystemExit) as exit_information:
            build_engine(
                mocker,
                game=GameWhoseConstructorRaises,
                extra_arguments=('--crt-power-on', 'on', flag, str(tmp_path / 'run.jsonl.gz')),
            )

        assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
        assert f'Cannot play the CRT power-on sequence with {flag}' in caplog.text


def game_noting_when_it_is_built(*, run_log: list[str]) -> type[FirstFrameGame]:
    """Return a FirstFrameGame class that notes ``'game built'`` in ``run_log`` when constructed.

    Returns:
        A new subclass.

    """

    class LoggingFirstFrameGame(FirstFrameGame):
        """Notes when it is built."""

        def __init__(self, options: dict[str, Any], groups: Any = None) -> None:
            """Note the construction, then build as FirstFrameGame does."""
            run_log.append('game built')
            super().__init__(options=options, groups=groups)

    return LoggingFirstFrameGame


@pytest.mark.usefixtures('engine_run_environment')
class TestCrtPowerOnBeforeEveryGame:
    """The power-on sequence plays on the game's canvas before the game is built."""

    def test_start_plays_it_before_the_game_is_built(self, mocker):
        run_log: list[str] = []
        engine = build_engine(
            mocker,
            game=game_noting_when_it_is_built(run_log=run_log),
            extra_arguments=('--crt-power-on', 'on'),
        )
        mocker.patch.object(
            game_engine_module,
            'play_power_on',
            side_effect=lambda **_arguments: run_log.append('power on') or PowerOnOutcome.FINISHED,
        )

        engine.start()

        assert run_log == ['power on', 'game built']

    def test_start_async_plays_the_async_sequence_first(self, mocker):
        run_log: list[str] = []
        engine = build_engine(
            mocker,
            game=game_noting_when_it_is_built(run_log=run_log),
            extra_arguments=('--crt-power-on', 'on'),
        )

        async def play_async(**_arguments):
            await asyncio.sleep(0)
            run_log.append('power on (async)')
            return PowerOnOutcome.FINISHED

        mocker.patch.object(game_engine_module, 'play_power_on_async', side_effect=play_async)
        _, wait_for_tick = async_ticks()

        asyncio.run(engine.start_async(wait_for_tick=wait_for_tick))

        assert run_log == ['power on (async)', 'game built']

    def test_the_game_is_handed_its_screen_and_doors(self, mocker):
        engine = build_engine(
            mocker, game=first_frame_game(), extra_arguments=('--crt-power-on', 'on')
        )
        player = mocker.patch.object(
            game_engine_module, 'play_power_on', return_value=PowerOnOutcome.FINISHED
        )

        engine.start()

        player.assert_called_once_with(screen=engine.screen, sources=active_sources())

    def test_closing_the_window_during_it_quits_the_game(self, mocker):
        """The QUIT is handed back to the game, which then ends the run normally."""
        engine = build_engine(
            mocker, game=first_frame_game(), extra_arguments=('--crt-power-on', 'on')
        )
        mocker.patch.object(game_engine_module, 'play_power_on', return_value=PowerOnOutcome.QUIT)
        posted = mocker.spy(game_engine_module, 'post_input_event')

        engine.start()

        (call,) = posted.call_args_list
        assert call.kwargs['event'].type == pygame.QUIT

    def test_a_skip_hands_nothing_to_the_game(self, mocker):
        engine = build_engine(
            mocker, game=first_frame_game(), extra_arguments=('--crt-power-on', 'on')
        )
        mocker.patch.object(
            game_engine_module, 'play_power_on', return_value=PowerOnOutcome.SKIPPED
        )
        posted = mocker.spy(game_engine_module, 'post_input_event')

        engine.start()

        posted.assert_not_called()

    def test_by_default_it_never_plays_on_the_test_driver(self, mocker):
        """Auto on SDL's dummy driver: no test pays for the sequence."""
        engine = build_engine(mocker, game=first_frame_game())
        player = mocker.spy(game_engine_module, 'play_power_on')

        engine.start()

        player.assert_not_called()


# A value no options block may show: the --api-key of GameWithASecretOption
VALUE_NEVER_SHOWN = 'not-a-real-key-0123456789'


class GameWithASecretOption(FirstFrameGame):
    """A game with an option whose name suggests a secret (``--api-key``)."""

    NAME = 'GameWithASecretOption'

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add ``--api-key``.

        Returns:
            The parser.

        """
        parser.add_argument('--api-key', default=None)
        return parser


def startup_option_records(caplog, *, game_name: str) -> list[logging.LogRecord]:
    """Return the startup options blocks the engine logged for a game.

    Returns:
        The records whose message starts with the block's heading.

    """
    return [
        record
        for record in caplog.records
        if record.name == 'game.engine'
        and record.getMessage().startswith(f'Options for {game_name} ')
    ]


def option_shown(*, record: logging.LogRecord, name: str) -> str:
    """Return what a startup options block shows for one top-level option.

    Returns:
        The text after ``=`` on the option's line.

    """
    (line,) = [
        line
        for line in record.getMessage().splitlines()[1:]
        if line.split('=', 1)[0].strip() == name
    ]
    return line.split('=', 1)[1].strip()


@pytest.mark.usefixtures('engine_run_environment')
class TestStartupOptions:
    """Every engine start logs the run's options once, at CRITICAL (the owner, 2026-10-28)."""

    @pytest.mark.parametrize('level', ['debug', 'info', 'warning', 'error', 'critical'])
    def test_the_options_show_once_at_every_level(self, mocker, caplog, level):
        """At any --log-level, the default warning included, one CRITICAL block per start."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class, extra_arguments=('--log-level', level))

        # The logging level the run asked for (basicConfig is a no-op under pytest's handlers)
        with caplog.at_level(level.upper()):
            engine.start()

        (record,) = startup_option_records(caplog, game_name=game_class.NAME)
        assert record.levelno == logging.CRITICAL
        assert option_shown(record=record, name='log_level') == repr(level)

    def test_a_secret_looking_option_is_redacted(self, mocker, caplog):
        """--api-key's value never reaches the log; the block shows <redacted> in its place."""
        engine = build_engine(
            mocker,
            game=GameWithASecretOption,
            extra_arguments=('--api-key', VALUE_NEVER_SHOWN),
        )

        with caplog.at_level(logging.WARNING):
            engine.start()

        (record,) = startup_option_records(caplog, game_name=GameWithASecretOption.NAME)
        assert VALUE_NEVER_SHOWN not in caplog.text
        assert option_shown(record=record, name='api_key') == (
            game_engine_module.REDACTED_OPTION_VALUE
        )

    def test_a_rolled_seed_is_shown_as_the_seed_the_run_uses(self, mocker, caplog):
        """No --random-seed: the block shows the rolled seed, not None, so the run can be redone.

        The owner, 2026-10-28: "The seed should definitely be in the options".
        """
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class)

        with caplog.at_level(logging.WARNING):
            engine.start()

        (record,) = startup_option_records(caplog, game_name=game_class.NAME)
        assert option_shown(record=record, name='random_seed') == str(engine.random_seed)

    def test_a_given_seed_is_shown(self, mocker, caplog):
        """--random-seed 5: the block shows 5."""
        game_class = first_frame_game()
        engine = build_engine(mocker, game=game_class, extra_arguments=('--random-seed', '5'))

        with caplog.at_level(logging.WARNING):
            engine.start()

        (record,) = startup_option_records(caplog, game_name=game_class.NAME)
        assert option_shown(record=record, name='random_seed') == '5'
