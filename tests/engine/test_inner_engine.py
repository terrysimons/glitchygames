"""A replay engine built inside an inner context: the hosted start (glitchygames/render_target.py).

An inner context (one with a render target) shares the process's window and drivers with every
other context, so building an engine there changes none of them (rows S1 and S2 of
plans/2026-10-25-engine-context.md). Its game's own entry point is called unchanged:
``GameEngine.start()`` builds the game up to its first frame and returns, and the host takes the
engine with ``take_started_engine()`` (plans/2026-11-12-arcade-3-inner-game.md, Task 1). The game
is a stand-in (tests/stand_in_games.py), recorded once in a child process; this process imports
its package to call its entry point, as a host does.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.engine import GameEngine
from glitchygames.engine_context import EngineContext
from glitchygames.exit_codes import ExitCode
from glitchygames.render_target import (
    hosted_start_requested,
    set_render_target,
    take_started_engine,
)
from glitchygames.replay.tools.golden_traces import command_line
from glitchygames.scenes import Scene
from tests.replay.replay_helpers import replay_through_engine
from tests.stand_in_games import (
    STAND_IN_GAME_RESOLUTION,
    StandInGame,
    copy_recording,
    record_stand_in_game_once,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from types import ModuleType

    from pytest_mock import MockerFixture

# The stand-in's package: a name no other test's stand-in uses, since this process imports it
STAND_IN_PACKAGE = 'inner_engine_rally'
# The render target: the recording's screen size (a replay opens at its recorded size)
TARGET_SIZE = tuple(int(side) for side in STAND_IN_GAME_RESOLUTION.split('x'))
# SDL's driver variables, which an inner engine never changes (--headless would)
SDL_DRIVER_VARIABLES = ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER')


@pytest.fixture(scope='module')
def recorded_stand_in(tmp_path_factory: pytest.TempPathFactory) -> tuple[StandInGame, Path]:
    """Record the stand-in game once per module (and xdist worker).

    Returns:
        The stand-in game and its recording (each test copies it before reading it).

    """
    root = tmp_path_factory.mktemp('inner-engine')
    game = write_stand_in_game(directory=root / 'site-packages', package=STAND_IN_PACKAGE)
    recording = record_stand_in_game_once(game=game, path=root / 'recorded.jsonl.gz')
    return game, recording


@pytest.fixture
def stand_in_package(
    recorded_stand_in: tuple[StandInGame, Path], monkeypatch: pytest.MonkeyPatch
) -> Generator[ModuleType]:
    """Import the stand-in's package in this process, as a host calling its entry point does.

    Yields:
        The package; it is forgotten afterwards, so no later test finds it imported.

    """
    game, _recording = recorded_stand_in
    monkeypatch.syspath_prepend(game.install_directory)
    try:
        yield importlib.import_module(game.package)
    finally:
        sys.modules.pop(game.package, None)


def window_state() -> tuple[tuple[int, int], tuple[str, str], tuple[str | None, ...]]:
    """Return what an inner engine must leave alone: the window's size and caption, the drivers.

    Returns:
        The window's size, its caption and icon title, and SDL's driver variables.

    """
    window = pygame.display.get_surface()
    assert window is not None
    return (
        window.get_size(),
        pygame.display.get_caption(),
        tuple(os.environ.get(variable) for variable in SDL_DRIVER_VARIABLES),
    )


def start_inner_replay(
    *, package: ModuleType, recording: Path, context: EngineContext, target: pygame.Surface
) -> GameEngine | None:
    """Call the stand-in's entry point in an inner context, replaying a recording headless.

    Args:
        package: The stand-in's package (its ``main`` builds and starts a ``GameEngine``).
        recording: The recording.
        context: The inner context.
        target: Its render target.

    Returns:
        The engine the hosted start handed over (``take_started_engine``).

    """
    with context.active():
        set_render_target(surface=target)
        with command_line(['--log-level', 'error', '--replay-trace', str(recording), '--headless']):
            package.main()
        return take_started_engine()


class TestAHostedStart:
    """start() in an inner context builds the game and hands the engine to its host."""

    def test_building_inner_leaves_the_window_the_drivers_and_the_icon_alone(
        self,
        stand_in_package: ModuleType,
        recorded_stand_in: tuple[StandInGame, Path],
        tmp_path: Path,
        mocker: MockerFixture,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """No set_mode, icon or caption call; the window's size and SDL's variables unchanged.

        The audio driver's variable is unset first: --headless would set it to ``dummy``, so a
        change shows even on the test run's dummy drivers (the mixer already runs on its own).
        """
        monkeypatch.delenv('SDL_AUDIODRIVER', raising=False)
        _game, shared_recording = recorded_stand_in
        recording = copy_recording(recording=shared_recording, path=tmp_path / 'replay.jsonl.gz')
        set_mode = mocker.spy(pygame.display, 'set_mode')
        set_icon = mocker.spy(pygame.display, 'set_icon')
        set_caption = mocker.spy(pygame.display, 'set_caption')
        before = window_state()

        engine = start_inner_replay(
            package=stand_in_package,
            recording=recording,
            context=EngineContext(name='inner'),
            target=pygame.Surface(TARGET_SIZE),
        )

        assert engine is not None
        assert window_state() == before
        assert 'SDL_AUDIODRIVER' not in os.environ
        set_mode.assert_not_called()
        set_icon.assert_not_called()
        set_caption.assert_not_called()

    def test_the_game_is_built_on_the_target_and_its_engine_handed_over_once(
        self,
        stand_in_package: ModuleType,
        recorded_stand_in: tuple[StandInGame, Path],
        tmp_path: Path,
    ):
        """The engine draws on the render target, its scene is set up, and it is taken once."""
        _game, shared_recording = recorded_stand_in
        recording = copy_recording(recording=shared_recording, path=tmp_path / 'replay.jsonl.gz')
        context = EngineContext(name='inner')
        target = pygame.Surface(TARGET_SIZE)

        engine = start_inner_replay(
            package=stand_in_package, recording=recording, context=context, target=target
        )
        with context.active():
            taken_again = take_started_engine()
            requested = hosted_start_requested()

        assert isinstance(engine, GameEngine)
        assert engine.screen is target
        assert engine.scene_manager.screen is target
        active_scene = engine.scene_manager.active_scene
        assert isinstance(active_scene, Scene)
        assert type(active_scene).__name__ == recorded_stand_in[0].scene_name
        assert active_scene.screen is target
        assert engine.replay_sources is not None
        assert taken_again is None
        assert requested
        # The default context's own start was never asked to hand anything over
        assert take_started_engine() is None


class TestTheDefaultContextsStart:
    """The default context's start() is unchanged: it runs the replay to its end and exits."""

    def test_a_replay_in_the_default_context_runs_and_exits_as_always(
        self,
        stand_in_package: ModuleType,
        recorded_stand_in: tuple[StandInGame, Path],
        tmp_path: Path,
        mocker: MockerFixture,
    ):
        """The blocking loop runs to the recording's end, exits SUCCESS, and hands nothing over."""
        game, shared_recording = recorded_stand_in
        recording = copy_recording(recording=shared_recording, path=tmp_path / 'replay.jsonl.gz')
        scene_class = getattr(stand_in_package, game.scene_name)
        assert issubclass(scene_class, Scene)

        replay = replay_through_engine(mocker=mocker, scene_class=scene_class, path=recording)

        assert replay.exit_status == ExitCode.SUCCESS, replay.result.report()
        assert replay.result.divergence is None
        assert not hosted_start_requested()
        assert take_started_engine() is None
