"""The golden-trace harness (glitchygames/replay/tools/golden_traces.py) and its tool.

The harness runs a game by its scene class and an input script, so every test here runs a
stand-in game. The ``record-golden-trace`` tool is run end to end on the stand-in game of
tests/stand_in_games.py through both front ends: as the game's own flag and as the
``glitchygames`` command, with the input script in the stand-in's own project.

Moved here with the harness (Part 3, Stage D, Task D4a): the lazy scene mapping's tests (from
tests/test_record_golden_traces.py), the seeded-reproducibility test (from
tests/world/test_golden_traces.py) and the early-stop replay test (from
tests/world/test_gameplay_replay.py).
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, override

import pygame
import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import logical_name
from glitchygames.process import OutputCapture, run_command
from glitchygames.randomness import random_stream
from glitchygames.replay.driver import LENGTH_DIVERGENCE, RANDOM_SEED_HEADER_FIELD
from glitchygames.replay.tools import command
from glitchygames.replay.tools.golden_traces import (
    GOLDEN_TRACE_SOURCE,
    RANDOM_SEED,
    GameSceneClasses,
    InputScript,
    InputScriptError,
    golden_game,
    load_input_script,
    record_trace,
    replay_golden_recording,
)
from glitchygames.replay.tools.registry import run_game_flag_tool
from glitchygames.scenes import Scene, SceneManager
from glitchygames.tracing import read_trace
from tests.stand_in_games import (
    STAND_IN_GAME_RESOLUTION,
    StandInGame,
    use_stand_in_game,
    write_stand_in_game,
)
from tests.stand_in_harness_games import TowerFloorScene, tower_script

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

# A child that records a stand-in's few frames ends in seconds
CHILD_TIMEOUT_SECONDS = 120.0

# The stand-in project's input script: a module in the project's root, run from there. Its one
# placement nudges the stand-in game's mover down by NUDGE_PIXELS before frame NUDGE_FRAME, so a
# trace shows the script ran
STAND_IN_INPUTS_MODULE = 'stand_in_inputs'
STAND_IN_INPUT_SCRIPT = f'{STAND_IN_INPUTS_MODULE}:rally_script'
NUDGE_FRAME = 5
NUDGE_PIXELS = 7
STAND_IN_INPUTS_SOURCE = f'''\
"""The stand-in project's golden input script (tests/replay/tools/test_golden_trace_harness.py)."""

from glitchygames.replay.tools.golden_traces import InputScript

NOT_A_SCRIPT = 'a string'


def nudge_mover(scene):
    """Move the stand-in game's mover down."""
    scene.mover.rect.y += {NUDGE_PIXELS}


def rally_script():
    """Return the stand-in game's input script: one nudge."""
    script = InputScript()
    script.place({NUDGE_FRAME}, nudge_mover)
    return script


def not_a_script():
    """Return something that is not an input script."""
    return 'a string'
'''
# How many frames the tool records: fewer than the stand-in game runs before it quits itself
GOLDEN_FRAME_COUNT = 12
# What the engine logs when it is built after pygame was started: a second engine would
WARNING_OF_A_SECOND_ENGINE = 'pygame was initialized before the engine'
# What the engine logs once per engine it builds (print_game_info)
ONE_LINE_PER_ENGINE = 'Game Title: '

# The lazy scene mapping's stand-in game module, written to tmp_path: its import is visible in
# sys.modules
STAND_IN_MODULE = 'stand_in_lazy_scene'
STAND_IN_SOURCE = """
from glitchygames.scenes import Scene


class LazyScene(Scene):
    pass
"""
STAND_IN_REFERENCE = f'{STAND_IN_MODULE}:LazyScene'

# The seeded-reproducibility test: --random-seed value and frames per run
SEEDED_TRACE_SEED = 123
SEEDED_TRACE_FRAME_COUNT = 120
# Its stand-in game's sprite: where it starts, its size, and its random step's range (pixels)
WANDERER_START = (400, 240)
WANDERER_SIZE = 8
WANDER_STEP_PIXELS = 3
WANDER_RANDOM_STREAM = 'stand_in.wander'

# The early-stop replay: frames recorded, and the frame the harness stops replaying at
EARLY_STOP_RECORDED_FRAMES = 30
EARLY_STOP_FRAME_LIMIT = 10


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Its facts: one console script (``stand-in-rally``) in package ``stand_in_rally``, one scene
    whose mover is a sprite on every frame, seeded and deterministic, no input; it quits itself
    after 20 frames.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


@pytest.fixture
def stand_in_project(tmp_path, monkeypatch) -> Generator[Path]:
    """Write the stand-in project's input script module; forget it again afterwards.

    Yields:
        The project's directory (the module is in its root).

    """
    project = tmp_path / 'project'
    project.mkdir()
    (project / f'{STAND_IN_INPUTS_MODULE}.py').write_text(STAND_IN_INPUTS_SOURCE, encoding='utf-8')
    monkeypatch.delitem(sys.modules, STAND_IN_INPUTS_MODULE, raising=False)
    yield project
    sys.modules.pop(STAND_IN_INPUTS_MODULE, None)


def mover_rects(*, path: Path) -> list[list[int]]:
    """Return the stand-in game's mover's rect on each frame of a golden trace.

    Returns:
        One rect per frame.

    """
    trace = read_trace(path=path)
    return [frame['sprites'][0]['rect'] for frame in trace['frames']]


def test_record_golden_trace_on_a_stand_in_game_as_a_flag_and_a_command(
    stand_in_game, stand_in_project, tmp_path, capfd
):
    """``--record-golden-trace`` on the game and ``glitchygames record-golden-trace``: the same.

    Each runs the stand-in game in a child in the stand-in's project, with the project's input
    script (``stand_in_inputs:rally_script``): the trace holds the frames asked for, the
    script's nudge, the golden source and the scene's logical name, and both front ends write
    the same bytes (the same default seed, the same script).
    """
    flag_trace = tmp_path / 'flag.jsonl.gz'
    command_trace = tmp_path / 'command.jsonl.gz'
    tool_arguments = [
        '--input-script',
        STAND_IN_INPUT_SCRIPT,
        '--frame-count',
        str(GOLDEN_FRAME_COUNT),
        # The stand-in's mover steps by a seeded random amount: both front ends under one seed
        '--random-seed',
        str(RANDOM_SEED),
        '--headless',
    ]

    flag_run = run_command(
        command=[
            sys.executable,
            '-c',
            f'import {stand_in_game.package}; {stand_in_game.package}.main()',
            '--log-level',
            'info',
            '--resolution',
            STAND_IN_GAME_RESOLUTION,
            '--record-golden-trace',
            str(flag_trace),
            *tool_arguments,
        ],
        environment=os.environ,
        timeout_seconds=CHILD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=stand_in_project,
    )
    command_status = command.main([
        'record-golden-trace',
        stand_in_game.console_script,
        str(command_trace),
        *tool_arguments,
        '--project-root',
        str(stand_in_project),
        '--',
        '--log-level',
        'error',
    ])

    errors = capfd.readouterr().err
    assert flag_run.returncode == ExitCode.SUCCESS, flag_run.stdout
    # One engine: the harness's, built before anything started pygame (the game's own engine
    # dispatches the tool before it starts pygame or opens a window)
    assert WARNING_OF_A_SECOND_ENGINE not in flag_run.stdout
    assert flag_run.stdout.count(ONE_LINE_PER_ENGINE) == 1, flag_run.stdout
    assert command_status == ExitCode.SUCCESS, errors
    assert (
        f'glitchygames record-golden-trace: running {stand_in_game.console_script} '
        '(an installed console script)'
    ) in errors
    trace = read_trace(path=flag_trace)
    assert trace['source'] == GOLDEN_TRACE_SOURCE
    assert trace['game'] == stand_in_game.logical_name
    rects = mover_rects(path=flag_trace)
    assert len(rects) == GOLDEN_FRAME_COUNT
    assert {rect[1] for rect in rects[:NUDGE_FRAME]} == {0}
    assert {rect[1] for rect in rects[NUDGE_FRAME:]} == {NUDGE_PIXELS}
    assert command_trace.read_bytes() == flag_trace.read_bytes()


class Wanderer(pygame.sprite.DirtySprite):
    """A small sprite the seeded stand-in moves by random steps."""

    def __init__(self) -> None:
        """Create the sprite at WANDERER_START."""
        super().__init__()
        self.image = pygame.Surface((WANDERER_SIZE, WANDERER_SIZE))
        self.rect = self.image.get_rect(topleft=WANDERER_START)

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it."""


class SeededWanderScene(Scene):
    """A stand-in game whose sprite moves by draws from the engine's seeded random streams.

    It stands in for a game whose serves, spawn places and colors all come from the run's
    seeded streams (``glitchygames.randomness.random_stream``). Every frame draws a step for the
    sprite, so a different seed moves it differently from the first frame on.
    """

    NAME = 'Seeded Wander'
    VERSION = '1.0'

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the wandering sprite."""
        super().__init__(options=options, groups=groups)
        self.wanderer = Wanderer()
        self.all_sprites.add(self.wanderer)

    @override
    def dt_tick(self, dt: float) -> None:
        """Move the sprite by a step drawn from its seeded stream."""
        super().dt_tick(dt)
        steps = random_stream(WANDER_RANDOM_STREAM)
        self.wanderer.rect.move_ip(
            steps.randint(-WANDER_STEP_PIXELS, WANDER_STEP_PIXELS),
            steps.randint(-WANDER_STEP_PIXELS, WANDER_STEP_PIXELS),
        )
        self.wanderer.dirty = 1


def test_same_random_seed_gives_identical_traces():
    """--random-seed 123 twice plays a seeded game identically; seed 124 plays differently.

    The game is a stand-in (SeededWanderScene): every random draw comes from the run's seeded
    streams, so the harness needs no patching of a game's randomness.
    """
    first_run = record_trace(
        scene_class=SeededWanderScene,
        script=InputScript(),
        frame_count=SEEDED_TRACE_FRAME_COUNT,
        random_seed=SEEDED_TRACE_SEED,
    )
    second_run = record_trace(
        scene_class=SeededWanderScene,
        script=InputScript(),
        frame_count=SEEDED_TRACE_FRAME_COUNT,
        random_seed=SEEDED_TRACE_SEED,
    )
    other_seed_run = record_trace(
        scene_class=SeededWanderScene,
        script=InputScript(),
        frame_count=SEEDED_TRACE_FRAME_COUNT,
        random_seed=SEEDED_TRACE_SEED + 1,
    )

    # The draws change the sprite within the run's frames: it does not stay where it started
    first_run_rects = {tuple(frame['sprites'][0]['rect']) for frame in first_run['frames']}
    assert len(first_run_rects) > 1
    assert second_run == first_run
    assert other_seed_run['frames'] != first_run['frames']


def test_a_trace_names_its_game_by_the_scenes_logical_name():
    """The trace's ``game`` is the scene class's logical name; its frame time is fixed."""
    trace = record_trace(scene_class=SeededWanderScene, script=InputScript(), frame_count=1)

    assert trace['game'] == logical_name(scene_class=SeededWanderScene)
    assert trace['frame_seconds'] == 1.0 / 60.0
    assert len(trace['frames']) == 1


def test_golden_harness_stopped_early_reports_a_length_divergence(tmp_path):
    """A harness replay stopped before the recording's last frame reports a length divergence."""
    recording_path = tmp_path / 'tower.jsonl.gz'
    record_trace(
        scene_class=TowerFloorScene,
        script=tower_script(),
        frame_count=EARLY_STOP_RECORDED_FRAMES,
        recording_path=recording_path,
    )
    result = replay_golden_recording(
        scene_class=TowerFloorScene,
        script=tower_script(),
        path=recording_path,
        frame_limit=EARLY_STOP_FRAME_LIMIT,
    )
    assert result.end_reason == 'diverged'
    divergence = result.divergence
    assert divergence is not None
    assert (divergence.kind, divergence.expected, divergence.actual) == (
        LENGTH_DIVERGENCE,
        EARLY_STOP_RECORDED_FRAMES,
        EARLY_STOP_FRAME_LIMIT,
    )


def nudged_script() -> InputScript:
    """Return the in-process stand-in's input script: one nudge of its mover, a placement.

    Returns:
        The input script.

    """

    def nudge(scene: Scene) -> None:
        assert isinstance(scene, NudgedScene)
        scene.mover.rect.y += NUDGE_PIXELS
        scene.mover.dirty = 1

    script = InputScript()
    script.place(NUDGE_FRAME, nudge)
    return script


def test_a_harness_replay_applies_the_scripts_placements_again(tmp_path):
    """A placement moves a sprite, which no recorded input does: the replay applies it again.

    So a recording of a placed run replays through the harness without diverging.
    """
    recording_path = tmp_path / 'nudged.jsonl.gz'
    record_trace(
        scene_class=NudgedScene,
        script=nudged_script(),
        frame_count=GOLDEN_FRAME_COUNT,
        recording_path=recording_path,
    )

    result = replay_golden_recording(
        scene_class=NudgedScene, script=nudged_script(), path=recording_path
    )

    assert result.divergence is None
    assert result.frames_replayed == GOLDEN_FRAME_COUNT


def test_a_run_whose_engine_is_gone_still_tears_down():
    """The harness's teardown needs no engine: the queue is emptied, the manager uninstalled."""
    with golden_game(scene_class=NudgedScene, random_seed=RANDOM_SEED) as manager:
        pygame.event.post(pygame.event.Event(pygame.USEREVENT))
        manager.game_engine = None

    assert pygame.event.peek(pygame.USEREVENT) is False
    assert SceneManager() is not manager


def golden_trace_options(
    *, path: Path, input_script: str = STAND_IN_INPUT_SCRIPT, random_seed: int | None = None
) -> dict[str, object]:
    """Return a game's parsed options with ``--record-golden-trace`` given.

    Returns:
        The options ``run_game_flag_tool`` reads.

    """
    return {
        'record_golden_trace': str(path),
        'input_script': input_script,
        'frame_count': GOLDEN_FRAME_COUNT,
        'random_seed': random_seed,
    }


class NudgedScene(Scene):
    """A stand-in game for the in-process tool runs: a mover the input script nudges."""

    NAME = 'Nudged'
    VERSION = '1.0'

    def __init__(self, options: dict[str, Any] | None = None, groups: Any = None) -> None:
        """Add the mover (the stand-in script's placement moves ``mover``)."""
        super().__init__(options=options, groups=groups)
        self.mover = Wanderer()
        self.all_sprites.add(self.mover)


def test_the_game_flag_records_a_golden_trace_in_place_of_the_game(
    stand_in_project, tmp_path, monkeypatch
):
    """``--record-golden-trace`` runs the harness on the game's scene class and writes the trace.

    Under the same ``--random-seed`` it equals ``record_trace``'s own run under the golden
    source; a scene the game passed in is run by its class.
    """
    monkeypatch.chdir(stand_in_project)
    path = tmp_path / 'golden.jsonl.gz'
    expected = record_trace(
        scene_class=NudgedScene,
        script=load_input_script(reference=STAND_IN_INPUT_SCRIPT),
        frame_count=GOLDEN_FRAME_COUNT,
        random_seed=RANDOM_SEED,
    )

    exit_code = run_game_flag_tool(
        options=golden_trace_options(path=path, random_seed=RANDOM_SEED), game=NudgedScene
    )

    assert exit_code == ExitCode.SUCCESS
    assert read_trace(path=path) == {'source': GOLDEN_TRACE_SOURCE, **expected}
    scene_path = tmp_path / 'scene.jsonl.gz'
    assert (
        run_game_flag_tool(
            options=golden_trace_options(path=scene_path, random_seed=RANDOM_SEED),
            game=NudgedScene(options={}),
        )
        == ExitCode.SUCCESS
    )
    assert scene_path.read_bytes() == path.read_bytes()


def test_the_game_flags_random_seed_reaches_the_harness(stand_in_project, tmp_path, monkeypatch):
    """``--random-seed N`` with ``--record-golden-trace``: the run is the harness's under N."""
    monkeypatch.chdir(stand_in_project)
    path = tmp_path / 'golden.jsonl.gz'
    expected = record_trace(
        scene_class=SeededWanderScene,
        script=InputScript(),
        frame_count=GOLDEN_FRAME_COUNT,
        random_seed=SEEDED_TRACE_SEED,
    )

    exit_code = run_game_flag_tool(
        options=golden_trace_options(
            path=path,
            input_script='glitchygames.replay.tools.golden_traces:InputScript',
            random_seed=SEEDED_TRACE_SEED,
        ),
        game=SeededWanderScene,
    )

    assert exit_code == ExitCode.SUCCESS
    assert read_trace(path=path)['frames'] == expected['frames']


def test_a_golden_trace_made_without_a_seed_names_the_seed_it_rolled(
    stand_in_project, tmp_path, monkeypatch
):
    """No ``--random-seed``: the golden names the seed it rolled, so it can be made again.

    Decision 17, row 1: a run with no seed rolls one, kept in what it records. The trace's
    ``random_seed`` is that seed: recorded again under it, the frames are the same (the trace
    loads, and compares, in the harness). A golden made under a given seed names none, so ours
    (always seeded: ``RANDOM_SEED``) keep their bytes.
    """
    monkeypatch.chdir(stand_in_project)
    rolled_path = tmp_path / 'rolled.jsonl.gz'
    again_path = tmp_path / 'again.jsonl.gz'
    input_script = 'glitchygames.replay.tools.golden_traces:InputScript'

    rolled_status = run_game_flag_tool(
        options=golden_trace_options(path=rolled_path, input_script=input_script),
        game=SeededWanderScene,
    )
    rolled = read_trace(path=rolled_path)
    again_status = run_game_flag_tool(
        options=golden_trace_options(
            path=again_path,
            input_script=input_script,
            random_seed=rolled[RANDOM_SEED_HEADER_FIELD],
        ),
        game=SeededWanderScene,
    )
    again = read_trace(path=again_path)

    assert rolled_status == again_status == ExitCode.SUCCESS
    assert isinstance(rolled[RANDOM_SEED_HEADER_FIELD], int)
    assert again['frames'] == rolled['frames']
    assert RANDOM_SEED_HEADER_FIELD not in again


def test_an_input_script_that_names_none_is_refused_and_nothing_runs(
    stand_in_project, tmp_path, monkeypatch, caplog
):
    """A ``--input-script`` naming no input script: ``OPTIONS_REFUSED``, said, no trace."""
    monkeypatch.chdir(stand_in_project)
    path = tmp_path / 'golden.jsonl.gz'

    exit_code = run_game_flag_tool(
        options=golden_trace_options(path=path, input_script=f'{STAND_IN_INPUTS_MODULE}:nothing'),
        game=NudgedScene,
    )

    assert exit_code == ExitCode.OPTIONS_REFUSED
    assert "has no callable 'nothing'" in caplog.text
    assert not path.exists()


def test_a_golden_trace_that_cannot_be_written_is_cannot_write_output(
    stand_in_project, tmp_path, monkeypatch, caplog
):
    """A trace path that is a directory: ``CANNOT_WRITE_OUTPUT``, said."""
    monkeypatch.chdir(stand_in_project)
    path = tmp_path / 'golden.jsonl.gz'
    path.mkdir()

    exit_code = run_game_flag_tool(options=golden_trace_options(path=path), game=NudgedScene)

    assert exit_code == ExitCode.CANNOT_WRITE_OUTPUT
    assert str(path) in caplog.text


def test_an_input_script_is_found_in_the_current_directory(stand_in_project, monkeypatch):
    """``MODULE`` is searched for in the current directory first, which is then off the path."""
    monkeypatch.chdir(stand_in_project)
    assert str(stand_in_project) not in sys.path

    script = load_input_script(reference=STAND_IN_INPUT_SCRIPT)

    assert isinstance(script, InputScript)
    assert list(script.placements) == [NUDGE_FRAME]
    assert str(stand_in_project) not in sys.path


def test_a_current_directory_already_on_the_path_stays_there(stand_in_project, monkeypatch):
    """A current directory the path already held is left on it."""
    monkeypatch.chdir(stand_in_project)
    monkeypatch.syspath_prepend(stand_in_project)

    load_input_script(reference=STAND_IN_INPUT_SCRIPT)

    assert sys.path[0] == str(stand_in_project)


@pytest.mark.parametrize(
    ('reference', 'message'),
    [
        ('no_separator', "'no_separator' is not MODULE:NAME"),
        (':rally_script', "':rally_script' is not MODULE:NAME"),
        (f'{STAND_IN_INPUTS_MODULE}:', f"'{STAND_IN_INPUTS_MODULE}:' is not MODULE:NAME"),
        ('stand_in_no_such_module:script', "module 'stand_in_no_such_module' does not import"),
        (f'{STAND_IN_INPUTS_MODULE}:missing', "has no callable 'missing'"),
        (f'{STAND_IN_INPUTS_MODULE}:NOT_A_SCRIPT', "has no callable 'NOT_A_SCRIPT'"),
        (f'{STAND_IN_INPUTS_MODULE}:not_a_script', 'returned a str, not an InputScript'),
    ],
)
def test_a_reference_that_names_no_input_script_is_refused(
    reference, message, stand_in_project, monkeypatch
):
    """Each way a reference can miss names the reference and why."""
    monkeypatch.chdir(stand_in_project)

    with pytest.raises(InputScriptError, match=message):
        load_input_script(reference=reference)


def test_a_game_is_imported_when_it_is_first_looked_up(lazy_scene_module):
    """Keys, length and membership import nothing; the lookup imports the class, once."""
    scenes = GameSceneClasses({'stand_in': STAND_IN_REFERENCE})

    assert list(scenes) == ['stand_in']
    assert len(scenes) == 1
    assert 'stand_in' in scenes
    assert 'other' not in scenes
    assert lazy_scene_module not in sys.modules
    scene_class = scenes['stand_in']
    assert lazy_scene_module in sys.modules
    assert scene_class.__name__ == 'LazyScene'
    assert issubclass(scene_class, Scene)
    assert scenes['stand_in'] is scene_class


def test_a_reference_that_is_not_a_scene_class_is_refused():
    """A reference to anything but a Scene subclass fails at its lookup, naming it."""
    scenes = GameSceneClasses({'not_a_scene': 'glitchygames.scenes:SceneManager'})

    with pytest.raises(TypeError, match=r"'glitchygames\.scenes:SceneManager' is not a Scene"):
        scenes['not_a_scene']


def test_patching_registers_a_stand_in_and_restores_without_importing(mocker, lazy_scene_module):
    """mocker.patch.dict adds and removes a key: nothing is imported.

    Its copy, clear and update keep the other games as references, so a test that registers a
    stand-in game imports no game at all.
    """
    scenes = GameSceneClasses({'stand_in': STAND_IN_REFERENCE})

    class RegisteredScene(Scene):
        pass

    mocker.patch.dict(scenes, {'registered': RegisteredScene})
    assert scenes['registered'] is RegisteredScene
    assert sorted(scenes) == ['registered', 'stand_in']
    mocker.stopall()

    assert list(scenes) == ['stand_in']
    assert lazy_scene_module not in sys.modules


def test_a_copy_keeps_references_and_resolved_classes_apart(lazy_scene_module):
    """A copy is a new mapping: deleting from it leaves the original."""
    scenes = GameSceneClasses({'stand_in': STAND_IN_REFERENCE})
    copied = scenes.copy()

    del copied['stand_in']

    assert list(scenes) == ['stand_in']
    assert list(copied) == []
    assert lazy_scene_module not in sys.modules


@pytest.fixture
def lazy_scene_module(tmp_path, monkeypatch):
    """Write the lazy mapping's stand-in game module to tmp_path; forget it again afterwards.

    Yields:
        The module's name.

    """
    (tmp_path / f'{STAND_IN_MODULE}.py').write_text(STAND_IN_SOURCE, encoding='utf-8')
    monkeypatch.syspath_prepend(tmp_path)
    monkeypatch.delitem(sys.modules, STAND_IN_MODULE, raising=False)
    yield STAND_IN_MODULE
    sys.modules.pop(STAND_IN_MODULE, None)
