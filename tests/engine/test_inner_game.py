"""A game's own command replayed inside its own engine context (glitchygames/inner_game.py).

``InnerGame.replay`` calls an installed command's entry point, unchanged, in a fresh engine
context with a render target and a private event queue; the host steps its frames one at a time
and reads how it ended from ``InnerGame.outcome`` (plans/2026-11-12-arcade-3-inner-game.md, Task
3). The game is a stand-in installed as a command (tests/stand_in_games.py), recorded once in a
child process; the inner game imports its package through the command's entry point, as an
installed console script would.

The plan's Review Focus is tested here: a recorded quit ends only its inner game (1), a
divergence ends it with the report and writes nothing to stdout (2), and a game that raises or
exits while building or stepping fails alone, the default context current afterwards (3).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.engine import GameEngine
from glitchygames.engine.game_engine import CURRENT_ENGINE_SLOT
from glitchygames.engine_context import current_context, default_context
from glitchygames.inner_game import (
    REFUSED_FLAGS,
    REFUSED_SHORT_FLAG_LETTERS,
    SHORT_FLAGS_TAKING_A_VALUE,
    InnerGame,
    InnerGameOutcome,
    InnerGameRefusedError,
    InnerGameState,
    is_refused_argument,
    is_refused_short_flag_cluster,
)
from glitchygames.render_target import render_target
from glitchygames.replay.input_blocking import REAL_INPUT_EVENT_TYPES
from glitchygames.scenes import Scene, SceneManager
from tests.replay.replay_helpers import tamper_first_sprite_rect
from tests.stand_in_games import (
    STAND_IN_GAME_RESOLUTION,
    StandInGame,
    copy_recording,
    record_stand_in_game_once,
    write_stand_in_distribution,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from pytest_mock import MockerFixture

# The stand-in's package: a name no other test's stand-in uses, since this process imports it
STAND_IN_PACKAGE = 'inner_game_rally'
# A command whose entry point returns without starting an engine
COMMAND_THAT_STARTS_NOTHING = 'inner-game-starts-nothing'
COMMAND_THAT_STARTS_NOTHING_PACKAGE = 'inner_game_starts_nothing'
# The render target: the recording's screen size (a replay opens at its recorded size)
TARGET_SIZE = (
    int(STAND_IN_GAME_RESOLUTION.split('x')[0]),
    int(STAND_IN_GAME_RESOLUTION.split('x')[1]),
)
# A size the recording was not made at: the replay refuses it (rule 1 of replay/driver.py)
ANOTHER_SIZE = (TARGET_SIZE[0] + 16, TARGET_SIZE[1])
# The frame a tampered copy first differs at
TAMPERED_FRAME = 10
# More steps than any stand-in recording holds: a loop that never ends fails instead of hanging
MOST_STEPS = 500
# Quiet inner engines: their INFO lines would only crowd a failing test's output
QUIET = ('--log-level', 'error')
# SDL's driver variables, which an inner game never changes
SDL_DRIVER_VARIABLES = ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')
# A user event the tests leave in SDL's queue: an inner game must neither take it nor add to it
SENTINEL_EVENT_TYPE = pygame.USEREVENT + 7


@pytest.fixture(scope='module')
def recorded_stand_in(tmp_path_factory: pytest.TempPathFactory) -> tuple[StandInGame, Path]:
    """Record the stand-in game once per module (and xdist worker).

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-game')
    game = write_stand_in_game(directory=root / 'site-packages', package=STAND_IN_PACKAGE)
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    return game, recording


@pytest.fixture
def stand_in(
    recorded_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[StandInGame]:
    """Install the stand-in as a command in this process (its dist-info on ``sys.path``).

    Yields:
        The stand-in game; its package is forgotten afterwards, so no later test finds it.

    """
    game, _recording = recorded_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield game
    finally:
        sys.modules.pop(game.package, None)


@pytest.fixture
def recording(recorded_stand_in: tuple[StandInGame, Path], tmp_path: Path) -> Path:
    """Return this test's own copy of the stand-in's recording.

    Returns:
        The copy's path.

    """
    _game, shared_recording = recorded_stand_in
    return copy_recording(recording=shared_recording, path=tmp_path / 'replay.jsonl.gz')


@pytest.fixture
def sentinel_in_sdl_queue() -> Generator[pygame.event.Event]:
    """Leave one event in SDL's otherwise empty queue for the test's length.

    Yields:
        The event; the queue is emptied afterwards.

    """
    pygame.event.clear()
    sentinel = pygame.event.Event(SENTINEL_EVENT_TYPE, {'marker': 'outer'})
    pygame.event.post(sentinel)
    try:
        yield sentinel
    finally:
        pygame.event.clear()


def process_state() -> dict[str, object]:
    """Return what an inner game must leave as it found it in the process.

    Returns:
        SDL's blocked input types, the window's size and caption, SDL's driver variables, the
        current context and the default context's engine.

    """
    window = pygame.display.get_surface()
    assert window is not None
    return {
        'blocked': {
            event_type: pygame.event.get_blocked(event_type)
            for event_type in (*REAL_INPUT_EVENT_TYPES, pygame.QUIT)
        },
        'window_size': window.get_size(),
        'caption': pygame.display.get_caption(),
        'drivers': tuple(os.environ.get(variable) for variable in SDL_DRIVER_VARIABLES),
        'context': current_context(),
        'engine': default_context().value(slot=CURRENT_ENGINE_SLOT).engine,
    }


def queued_without_pumping() -> list[tuple[int, dict[str, object]]]:
    """Take every event in SDL's queue without pumping it (nothing new is read from the OS).

    Returns:
        Each event's type and attributes, in order.

    """
    return [(event.type, dict(event.dict)) for event in pygame.event.get(pump=False)]


def play_to_the_end(inner_game: InnerGame) -> int:
    """Step an inner game until it ends or fails.

    Returns:
        How many steps returned True.

    """
    for running_steps in range(MOST_STEPS):
        if not inner_game.step():
            return running_steps
    pytest.fail(f'{inner_game.context.name} did not end in {MOST_STEPS} steps')


def replay_stand_in(
    *,
    game: StandInGame,
    path: Path,
    name: str = 'tile',
    size: tuple[int, int] = TARGET_SIZE,
    arguments: tuple[str, ...] = QUIET,
) -> InnerGame:
    """Start the stand-in's replay as an inner game.

    Returns:
        The inner game.

    """
    return InnerGame.replay(
        command=game.console_script, path=path, name=name, size=size, arguments=arguments
    )


class TestAReplayInsideItsContext:
    """The command's own entry point replays the recording in the inner game's context."""

    def test_it_plays_to_its_end_and_matches(self, stand_in: StandInGame, recording: Path):
        """Every frame runs, the replay matches, and the outcome says so."""
        inner_game = replay_stand_in(game=stand_in, path=recording)

        assert inner_game.outcome == InnerGameOutcome(
            state=InnerGameState.RUNNING, frames_run=0, report=None, error=None
        )
        running_steps = play_to_the_end(inner_game)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.ENDED, outcome
        assert outcome.error is None
        assert outcome.report is not None
        assert outcome.report.startswith('Replay matched'), outcome.report
        # The step that ran the last frame returned False: the game ended there
        assert outcome.frames_run == running_steps + 1
        assert inner_game.context.name == 'tile'
        assert current_context() is default_context()

    def test_it_draws_on_its_own_surface_of_the_size_asked_for(
        self, stand_in: StandInGame, recording: Path
    ):
        """The surface is the context's render target, in the display's format."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            target = render_target()

        surface = inner_game.surface
        display = pygame.display.get_surface()
        assert display is not None
        assert surface.get_size() == TARGET_SIZE
        assert surface.get_bitsize() == display.get_bitsize()
        assert surface is not display
        assert target is surface
        inner_game.finish()

    def test_finishing_is_idempotent_and_steps_after_it_run_nothing(
        self, stand_in: StandInGame, recording: Path
    ):
        """finish() twice gives the same outcome; a step after it returns False and runs nothing."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        first = inner_game.finish()
        second = inner_game.finish()

        assert first == second == inner_game.outcome
        assert not inner_game.step()
        assert inner_game.outcome == first

    def test_finishing_before_the_end_ends_it_with_where_it_stopped(
        self, stand_in: StandInGame, recording: Path
    ):
        """The host may end a replay early: ENDED, its report the length divergence."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()

        outcome = inner_game.finish()

        assert outcome.state is InnerGameState.ENDED
        assert outcome.frames_run == 1
        assert outcome.report is not None
        assert outcome.report.startswith('Replay diverged at frame 1'), outcome.report

    def test_a_game_whose_timer_failed_to_start_still_finishes(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """The engine runs without a timer when its backend fails (injected): nothing to close."""
        mocker.patch(
            'glitchygames.engine.game_engine.create_timer', side_effect=ValueError('no timer')
        )
        inner_game = replay_stand_in(game=stand_in, path=recording)

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert inner_game.outcome.report is not None
        assert inner_game.outcome.report.startswith('Replay matched')

    def test_two_inner_games_play_side_by_side(self, stand_in: StandInGame, recording: Path):
        """Stepped in turn, each in its own context, both match."""
        first = replay_stand_in(game=stand_in, path=recording, name='first')
        second = replay_stand_in(game=stand_in, path=recording, name='second')

        for _step in range(MOST_STEPS):
            first_running = first.step()
            second_running = second.step()
            if not (first_running or second_running):
                break

        for inner_game in (first, second):
            outcome = inner_game.outcome
            assert outcome.state is InnerGameState.ENDED, outcome
            assert outcome.report is not None
            assert outcome.report.startswith('Replay matched'), outcome.report
        assert first.context is not second.context


class TestARecordedQuit:
    """Review Focus 1: the recording's quit ends only its inner game."""

    def test_it_ends_the_inner_game_and_never_reaches_sdl(
        self,
        stand_in: StandInGame,
        recording: Path,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """ENDED and matched; SDL's queue holds only the outer game's event; no outer quit."""
        outer_scene_manager = SceneManager()
        outer_quit_requested = outer_scene_manager.quit_requested
        inner_game = replay_stand_in(game=stand_in, path=recording)

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]
        assert SceneManager() is outer_scene_manager
        assert outer_scene_manager.quit_requested == outer_quit_requested


class TestADivergence:
    """Review Focus 2: a replay that diverges inside an inner game ends it, reported."""

    def test_it_ends_with_the_report_and_writes_nothing_to_stdout(
        self,
        stand_in: StandInGame,
        recording: Path,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ):
        """ENDED (not FAILED) with the divergence report, logged at INFO; stdout empty."""
        tamper_first_sprite_rect(recording_path=recording, frame_number=TAMPERED_FRAME)
        capsys.readouterr()
        caplog.set_level('INFO', logger='game.inner_game')

        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.ENDED, outcome
        assert outcome.error is None
        assert outcome.report is not None
        assert outcome.report.startswith(f'Replay diverged at frame {TAMPERED_FRAME}')
        assert not capsys.readouterr().out
        assert any(
            record.levelname == 'INFO' and outcome.report in record.getMessage()
            for record in caplog.records
        )


class TestAFailure:
    """Review Focus 3: a game that raises or exits fails alone; the default context goes on."""

    def test_a_replay_refused_while_building_fails_with_its_exit(
        self,
        stand_in: StandInGame,
        recording: Path,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """A target of another size than recorded: the replay's refusal (a SystemExit) is FAILED.

        Nothing is left behind: no engine current in the inner context, nothing in the process.
        """
        before = process_state()

        inner_game = replay_stand_in(game=stand_in, path=recording, size=ANOTHER_SIZE)

        outcome = inner_game.outcome
        assert outcome.state is InnerGameState.FAILED
        assert outcome.frames_run == 0
        assert outcome.report is None
        assert outcome.error == 'the game exited with UNUSABLE_INPUT (65)'
        assert not inner_game.step()
        assert inner_game.finish() == outcome
        with inner_game.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]

    def test_an_argument_the_game_refuses_fails_with_its_exit(
        self, stand_in: StandInGame, recording: Path
    ):
        """An unknown flag: argparse's own exit is FAILED, never the host's exit."""
        inner_game = replay_stand_in(
            game=stand_in, path=recording, arguments=(*QUIET, '--no-such-flag')
        )

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with ARGUMENT_PARSER_ERROR (2)'
        assert current_context() is default_context()

    def test_a_game_raising_while_stepping_fails_alone(
        self,
        stand_in: StandInGame,
        recording: Path,
        mocker: MockerFixture,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """The raising game is FAILED with its error; the other inner game goes on and matches."""
        before = process_state()
        failing = replay_stand_in(game=stand_in, path=recording, name='failing')
        healthy = replay_stand_in(game=stand_in, path=recording, name='healthy')
        failing.step()
        healthy.step()
        with failing.context.active():
            scene = SceneManager().active_scene
        assert isinstance(scene, Scene)
        # An injected failure, on the failing game's scene alone
        mocker.patch.object(scene, 'dt_tick', side_effect=RuntimeError('the scene broke'))

        assert not failing.step()
        play_to_the_end(healthy)

        failed = failing.outcome
        assert failed.state is InnerGameState.FAILED
        assert failed.error == 'RuntimeError: the scene broke'
        assert failed.frames_run == 1
        assert failed.report is not None
        assert failed.report.startswith('Replay stopped at frame'), failed.report
        assert 'the run ended with RuntimeError: the scene broke' in failed.report
        assert healthy.outcome.state is InnerGameState.ENDED
        assert healthy.outcome.report is not None
        assert healthy.outcome.report.startswith('Replay matched')
        with failing.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]

    def test_a_game_exiting_while_stepping_fails_alone(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """A game's own sys.exit() in a frame is FAILED, never the host's exit."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=SystemExit(0))

        assert not inner_game.step()

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with SUCCESS (0)'

    def test_a_game_exiting_without_a_number_is_described_as_it_exited(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """sys.exit('message') carries no exit code: the outcome names what it carried."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=SystemExit('gave up'))

        inner_game.step()

        assert inner_game.outcome.error == "the game exited with SystemExit('gave up')"

    def test_a_failing_finish_is_failed_and_the_rest_of_the_finish_still_runs(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """end_frames raising: FAILED with its error; the replay is still settled and reported."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        mocker.patch.object(SceneManager, 'end_frames', side_effect=RuntimeError('no end'))

        outcome = inner_game.finish()

        assert outcome.state is InnerGameState.FAILED
        assert outcome.error == 'RuntimeError: no end'
        assert outcome.report is not None
        assert outcome.report.startswith('Replay stopped at frame 1')
        assert current_context() is default_context()

    def test_a_failure_while_finishing_a_failed_game_keeps_the_first_error(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """The step's error stays the outcome's; the finish's own failure is only logged."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=RuntimeError('first'))
        mocker.patch.object(SceneManager, 'end_frames', side_effect=RuntimeError('second'))

        inner_game.step()

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'RuntimeError: first'

    def test_a_keyboard_interrupt_is_not_contained(
        self, stand_in: StandInGame, recording: Path, mocker: MockerFixture
    ):
        """Ctrl-C is the host's (decision 4): it propagates out of step()."""
        inner_game = replay_stand_in(game=stand_in, path=recording)
        inner_game.step()
        with inner_game.context.active():
            scene = SceneManager().active_scene
        mocker.patch.object(scene, 'dt_tick', side_effect=KeyboardInterrupt)

        with pytest.raises(KeyboardInterrupt):
            inner_game.step()
        assert current_context() is default_context()

    def test_an_unknown_command_fails(self, recording: Path):
        """No installed command of that name: FAILED, saying so."""
        inner_game = InnerGame.replay(
            command='no-such-inner-game', path=recording, name='tile', size=TARGET_SIZE
        )

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == "no installed command is named 'no-such-inner-game'"

    def test_a_command_that_starts_no_engine_fails(
        self, recording: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """An entry point that returns without starting a game: FAILED, saying so."""
        install_directory = tmp_path / 'site-packages'
        package_directory = install_directory / COMMAND_THAT_STARTS_NOTHING_PACKAGE
        package_directory.mkdir(parents=True)
        (package_directory / '__init__.py').write_text(
            'def main():\n    """Start nothing."""\n', encoding='utf-8'
        )
        write_stand_in_distribution(
            directory=install_directory,
            distribution=COMMAND_THAT_STARTS_NOTHING,
            console_scripts={
                COMMAND_THAT_STARTS_NOTHING: f'{COMMAND_THAT_STARTS_NOTHING_PACKAGE}:main'
            },
        )
        monkeypatch.syspath_prepend(install_directory)
        monkeypatch.delitem(sys.modules, COMMAND_THAT_STARTS_NOTHING_PACKAGE, raising=False)

        inner_game = InnerGame.replay(
            command=COMMAND_THAT_STARTS_NOTHING, path=recording, name='tile', size=TARGET_SIZE
        )
        sys.modules.pop(COMMAND_THAT_STARTS_NOTHING_PACKAGE, None)

        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == (
            f'{COMMAND_THAT_STARTS_NOTHING} started no game engine in its context'
        )


class TestTheProcessAfterwards:
    """An inner game leaves the process as it found it (no leftovers once it has finished)."""

    def test_a_finished_inner_game_leaves_the_process_as_it_was(
        self,
        stand_in: StandInGame,
        recording: Path,
        sentinel_in_sdl_queue: pygame.event.Event,
    ):
        """Blocked types, SDL's queue, the window, the drivers, sys.argv, the default context."""
        before = process_state()
        argv_before = list(sys.argv)

        inner_game = replay_stand_in(game=stand_in, path=recording)
        play_to_the_end(inner_game)

        assert process_state() == before
        assert queued_without_pumping() == [
            (sentinel_in_sdl_queue.type, dict(sentinel_in_sdl_queue.dict))
        ]
        with inner_game.context.active():
            assert current_context().value(slot=CURRENT_ENGINE_SLOT).engine is None
        assert sys.argv == argv_before


class TestRefusals:
    """Decision 5: only recordings run inner; what would do anything else is refused first."""

    @pytest.mark.parametrize(
        'arguments',
        [
            ('--record-trace', 'new.jsonl.gz'),
            ('--replay-trace', 'other.jsonl.gz'),
            ('--rebaseline', 'new.jsonl.gz'),
            ('--audit',),
            ('--compare-trace', 'old.jsonl.gz'),
            ('--verify',),
            ('--measure',),
            ('--record-session', 'new.jsonl.gz'),
            ('--replay-frame-stream', '1234:token'),
            ('--replay-restart-handoff', 'handoff.json'),
            ('--replay-viewer-state', '{}'),
            ('--profile',),
            ('--list-input-devices',),
            ('--help',),
            ('-h',),
            ('-p',),
            ('-v',),
            ('--version',),
            ('--ver',),
            ('-ph',),
            ('-wp',),
            ('-wv',),
            ('--rebase', 'new.jsonl.gz'),
            ('--record-trace=new.jsonl.gz',),
            ('--log-level', 'error', '--audit'),
        ],
    )
    def test_it_is_refused_before_anything_is_built(
        self, stand_in: StandInGame, recording: Path, arguments: tuple[str, ...]
    ):
        """InnerGameRefusedError naming the argument; the command's package is never imported."""
        with pytest.raises(InnerGameRefusedError, match='cannot run inside another game'):
            replay_stand_in(game=stand_in, path=recording, arguments=arguments)

        assert stand_in.package not in sys.modules
        assert current_context() is default_context()

    def test_a_cluster_whose_value_holds_a_refused_letter_is_the_games(
        self, stand_in: StandInGame, recording: Path
    ):
        """-l takes the rest of its cluster as its value: no letter after it is a flag."""
        inner_game = replay_stand_in(game=stand_in, path=recording, arguments=('-lerror',))

        play_to_the_end(inner_game)

        assert inner_game.outcome.state is InnerGameState.ENDED, inner_game.outcome
        assert not is_refused_short_flag_cluster(cluster='fp')
        assert not is_refused_short_flag_cluster(cluster='rhv')
        assert is_refused_short_flag_cluster(cluster='wph')

    def test_no_engine_flag_is_refused_but_the_refused_ones(self):
        """Every flag of the engine's parser: refused exactly when it is a refused flag.

        ``--no-audit`` (the audit switched off) is allowed though ``--audit`` is refused.

        Also the short letters: the engine's short forms of refused flags are refused letters,
        and the engine's short flags that take a value are exactly SHORT_FLAGS_TAKING_A_VALUE.
        """
        parser = GameEngine.args(argparse.ArgumentParser())
        wrongly_judged: list[str] = []
        value_letters: set[str] = set()
        for action in parser._actions:
            long_flags = [flag for flag in action.option_strings if flag.startswith('--')]
            short_flags = [flag for flag in action.option_strings if not flag.startswith('--')]
            should_refuse = any(flag in REFUSED_FLAGS for flag in long_flags)
            # A long flag on its own (--no-audit, the audit switched off, may run); a short
            # flag as its action's long flags are
            wrongly_judged.extend(
                flag
                for flag in long_flags
                if is_refused_argument(argument=flag) != (flag in REFUSED_FLAGS)
            )
            wrongly_judged.extend(
                flag for flag in short_flags if is_refused_argument(argument=flag) != should_refuse
            )
            if action.nargs != 0:
                value_letters.update(flag[1:] for flag in short_flags)
            if should_refuse:
                assert {flag[1:] for flag in short_flags} <= REFUSED_SHORT_FLAG_LETTERS

        assert wrongly_judged == []
        assert value_letters == SHORT_FLAGS_TAKING_A_VALUE

    def test_the_refusal_names_every_refused_argument(self, stand_in: StandInGame, recording: Path):
        """Each refused argument is named once, in the order given."""
        with pytest.raises(InnerGameRefusedError) as refusal:
            replay_stand_in(
                game=stand_in, path=recording, arguments=('--audit', '--profile=yes', '--audit')
            )

        assert str(refusal.value) == (
            '--audit, --profile=yes cannot run inside another game: an inner game only replays '
            'a recording headless'
        )

    def test_arguments_after_a_bare_separator_are_the_games(
        self, stand_in: StandInGame, recording: Path
    ):
        """After ``--`` nothing is a flag (argparse's rule): the game gets them as positionals."""
        inner_game = replay_stand_in(
            game=stand_in, path=recording, arguments=(*QUIET, '--', '--audit')
        )

        # The stand-in takes no positional: argparse refuses it, which is the game's failure
        assert inner_game.outcome.state is InnerGameState.FAILED
        assert inner_game.outcome.error == 'the game exited with ARGUMENT_PARSER_ERROR (2)'
