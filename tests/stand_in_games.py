"""Stand-in games and distributions for engine tests that once ran a real game.

An engine test that needs a game installed (a console script to replay through, a package with
bundled demos, a game a child process starts) uses a stand-in written to ``tmp_path`` instead,
so the engine's tests import no workspace member and run no member's code:

- ``write_stand_in_distribution``: an installed distribution's metadata (a dist-info) holding
  only console scripts, which ``importlib.metadata`` finds as it finds an installed member's.
- ``write_stand_in_package``: an import package holding files in its ``demos/`` directory.
- ``write_stand_in_recording``: a small recording written with the trace writer (no game ran).
- ``write_stand_in_game``: a tiny game package and its distribution with one console script.
  Its facts are fixed and stated here, so each test can name the ones it relies on:

  - **one scene** (``StandInGame.scene_name``): the recording's header ``game`` and every
    ``scene_start`` name that one scene;
  - **a sprite on every frame**: one 4x4 mover, drawn from frame 0 on, so a recording holds a
    sprite on frame 10 and every frame after it;
  - **seeded and deterministic**: the mover steps right each frame by an amount drawn from the
    engine's seeded random stream (``glitchygames.randomness.random_stream``), so a replay
    under the recorded seed reproduces every frame and ``--audit`` passes;
  - **no input**: it binds no control and polls nothing;
  - **it quits itself** after ``frames_before_quit`` frames;
  - **its layer**, only when ``layer`` is given: its package registers itself in
    ``glitchygames.logical_names.MEMBER_LAYERS`` when imported, so its logical names are
    layered (``games.<package>:<Scene>``) as a member's are. Only the child processes that run
    it import it: this process must not (it would leave the entry in the global dict).

- ``stamp_stand_in_game``: give a stand-in's package a build stamp naming a revision, so its runs
  name that commit as the game's (``MeasurementRun.game_source_revision``): with the engine's
  revision, it stands for a game of this checkout, as ours are. Without one, a stand-in in
  ``tmp_path`` is in no checkout, so its runs name an unknown game revision.
- ``use_stand_in_game``: put a stand-in's install directory on ``sys.path`` (for the metadata
  lookups this process makes) and on ``PYTHONPATH`` (for the child processes that start it).
- ``record_stand_in_game``: record a stand-in game's session in a child process
  (``--record-trace``), as a player's live run would: uncapped, unless the test needs it paced.
- ``record_stand_in_game_once``: the same, for a module- or session-scoped fixture whose
  recording many tests read; ``copy_recording`` hands each test its own copy.
- ``GameThatIsNeverBuilt``: a scene class whose constructor fails, for the in-process tests of
  the tools that run in place of the game (from ``GameEngine.__init__``).
"""

from __future__ import annotations

import dataclasses
import gzip
import json
import os
import shutil
import sys
from typing import TYPE_CHECKING

import pytest

from glitchygames.build_info import BUILD_STAMP_FILE_NAME
from glitchygames.bundled_demos import BUNDLED_DEMO_DIRECTORY_NAME, CONSOLE_SCRIPTS_GROUP
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.scenes import Scene
from glitchygames.tracing import REPLAY_FIXTURES_PATH_PARTS, TRACE_FORMAT_VERSION, write_trace

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.build_info import SourceRevision

# How many frames a stand-in game runs before it quits itself: enough for a tampered frame 10
# and the frames after it
STAND_IN_GAME_FRAMES = 20
# A recording of a stand-in game takes a second or two; a hung child is killed after this long
RECORD_TIMEOUT_SECONDS = 120.0
# The stand-in game's window: small, since nothing in it is looked at
STAND_IN_GAME_RESOLUTION = '320x240'
# A paced live recording (``record_stand_in_game(paced=True)``) runs at this rate, as a
# player's run is
STAND_IN_GAME_TARGET_FPS = '60'
# Every other live recording is uncapped (``--target-fps 0``): its frames never wait, and the
# engine never measures this machine's sleep model (it does as a paced live game starts), so a
# 20-frame recording takes its child's start-up and no more. Its frame times are whatever the
# frames took, which only a test of pacing, or of what reads recorded frame times, looks at
UNPACED_TARGET_FPS = '0'
# A "game" that never ends (an editor or a server among a project's [project.scripts], given a
# tool flag it ignores): it writes its process id into never-ending.pid beside itself, then waits
NEVER_ENDING_GAME_SOURCE = """\
import os
import pathlib
import time

pathlib.Path(__file__).with_name('never-ending.pid').write_text(str(os.getpid()), encoding='utf-8')
while True:
    time.sleep(1)
"""
# The game-timeout-seconds a project with the never-ending game sets: short, for the tests
NEVER_ENDING_GAME_TIMEOUT_SECONDS = 2.0


def write_never_ending_game_project(*, directory: Path) -> Path:
    """Write a project whose settings give each game NEVER_ENDING_GAME_TIMEOUT_SECONDS.

    It holds the never-ending game as a script, ``never_ending_game.py`` (named on the command
    by its path).

    Returns:
        The script.

    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'pyproject.toml').write_text(
        f'[tool.glitchygames]\ngame-timeout-seconds = {NEVER_ENDING_GAME_TIMEOUT_SECONDS}\n',
        encoding='utf-8',
    )
    script = directory / 'never_ending_game.py'
    script.write_text(NEVER_ENDING_GAME_SOURCE, encoding='utf-8')
    return script


class GameThatIsNeverBuilt(Scene):
    """A game whose scene must never be built: a tool given as its game flag runs in its place.

    The in-process engine tests of the tools that run from ``GameEngine.__init__`` (``--verify``,
    ``--measure``, ``--report``, ``--performance-pages``, ...) pass it as the game: building it
    fails the run.
    """

    NAME = 'GameThatIsNeverBuilt'
    VERSION = '1.0'

    def __init__(self, options=None, groups=None) -> None:
        """Fail at once: the tool reads, or runs children, never this scene.

        Raises:
            AssertionError: Always.

        """
        message = 'a tool given as a game flag built the scene'
        raise AssertionError(message)


@dataclasses.dataclass(frozen=True)
class StandInGame:
    """A stand-in game written by ``write_stand_in_game``.

    Attributes:
        package: Its import package (``stand_in_rally``).
        distribution: Its distribution, whose one console script starts it.
        console_script: That console script's name.
        scene_name: Its one scene's class name.
        install_directory: The directory holding the package and the dist-info (a ``sys.path``
            entry once ``use_stand_in_game`` puts it there).
        layer: The layer it registers its package in when imported, or None.

    """

    package: str
    distribution: str
    console_script: str
    scene_name: str
    install_directory: Path
    layer: str | None

    @property
    def logical_name(self) -> str:
        """The logical name its recordings give its scene (``glitchygames.logical_names``).

        Returns:
            ``<layer>.<package>:<Scene>`` when it registers a layer, else ``<package>:<Scene>``.

        """
        module = self.package if self.layer is None else f'{self.layer}.{self.package}'
        return f'{module}:{self.scene_name}'


def write_stand_in_distribution(
    *, directory: Path, distribution: str, console_scripts: dict[str, str]
) -> None:
    """Write an installed distribution's metadata (a dist-info), holding only console scripts.

    With ``directory`` on ``sys.path``, ``importlib.metadata.distribution`` finds it as it finds
    an installed member's.

    Args:
        directory: Where it is installed (a sys.path entry).
        distribution: Its name.
        console_scripts: Console script name -> entry point (``package:function``).

    """
    dist_info = directory / f'{distribution.replace("-", "_")}-1.0.0.dist-info'
    dist_info.mkdir(parents=True)
    (dist_info / 'METADATA').write_text(
        f'Metadata-Version: 2.1\nName: {distribution}\nVersion: 1.0.0\n', encoding='utf-8'
    )
    entry_points = ''.join(f'{name} = {value}\n' for name, value in console_scripts.items())
    (dist_info / 'entry_points.txt').write_text(
        f'[{CONSOLE_SCRIPTS_GROUP}]\n{entry_points}', encoding='utf-8'
    )


def write_stand_in_package(*, directory: Path, package: str, demo_names: tuple[str, ...]) -> Path:
    """Write an import package with no console script, holding files in its demos/ directory.

    The files are empty unless the caller writes them.

    Returns:
        The package's demos directory.

    """
    demo_directory = directory / package / BUNDLED_DEMO_DIRECTORY_NAME
    demo_directory.mkdir(parents=True)
    (directory / package / '__init__.py').write_text('', encoding='utf-8')
    for name in demo_names:
        (demo_directory / name).write_bytes(b'')
    return demo_directory


def member_recording_path(*, tmp_path: Path, distribution: str) -> Path:
    """Return where a member distribution's recording goes: <member>/tests/fixtures/replays/.

    Returns:
        The recording's path (its directory made).

    """
    directory = tmp_path.joinpath(distribution, 'tests', *REPLAY_FIXTURES_PATH_PARTS)
    directory.mkdir(parents=True)
    return directory / 'golden.jsonl.gz'


def write_header_only_recording(*, path: Path, header: dict[str, object]) -> None:
    """Write a recording that is only a header line (all a console script's choice reads).

    Args:
        path: Where to write it.
        header: The header's fields, besides ``format_version``.

    """
    with gzip.open(path, 'wt', encoding='utf-8') as recording:
        recording.write(json.dumps({'format_version': TRACE_FORMAT_VERSION, **header}) + '\n')


def write_stand_in_recording(*, path: Path, frame_count: int) -> None:
    """Write a small recording with the trace writer: frames with no sprites, no game ran.

    Enough for what reads a recording without replaying it (a bookmarked copy needs as many
    frames as its bookmark's number).

    Args:
        path: Where to write it.
        frame_count: How many frames it holds.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_trace(
        trace={
            'game': 'stand_in_game',
            'frame_seconds': 1.0 / 60.0,
            'frames': [
                {'frame': frame_number, 'scene': 'Rally', 'sprites': []}
                for frame_number in range(frame_count)
            ],
        },
        path=path,
    )


def stand_in_game_source(
    *, package: str, scene_name: str, frames_before_quit: int, layer: str | None
) -> str:
    """Return a stand-in game package's ``__init__.py`` (the facts in this module's docstring).

    Returns:
        The source.

    """
    layer_registration = (
        ''
        if layer is None
        else (
            'from glitchygames import logical_names\n\n'
            '# Register this package in its layer as a workspace member is '
            '(glitchygames/logical_names.py)\n'
            f'logical_names.MEMBER_LAYERS[__name__] = {layer!r}\n'
        )
    )
    return f'''\
"""A stand-in game for the engine's tests (written by tests/stand_in_games.py)."""

import pygame

from glitchygames.engine import GameEngine
from glitchygames.randomness import random_stream
from glitchygames.scenes import Scene
{layer_registration}
FRAMES_BEFORE_QUIT = {frames_before_quit}
MOVER_SIZE = 4
MOVER_LARGEST_STEP = 3


class Mover(pygame.sprite.DirtySprite):
    """A small square drawn on every frame."""

    def __init__(self):
        super().__init__()
        self.image = pygame.Surface((MOVER_SIZE, MOVER_SIZE))
        self.rect = self.image.get_rect()
        self.dirty = 2

    def update_nested_sprites(self):
        pass


class {scene_name}(Scene):
    """The stand-in's one scene: the mover steps right by a seeded random amount each frame."""

    NAME = {scene_name!r}

    def __init__(self, options=None, groups=None):
        super().__init__(options=options, groups=groups)
        self.steps = random_stream({package + '.mover'!r})
        self.mover = Mover()
        self.all_sprites.add(self.mover)
        self.frames = 0

    def dt_tick(self, dt):
        self.frames += 1
        self.mover.rect.x += self.steps.randint(1, MOVER_LARGEST_STEP)
        if self.frames == FRAMES_BEFORE_QUIT:
            GameEngine.quit_game()


def main():
    """The console script's entry point."""
    GameEngine(game={scene_name}).start()
'''


def write_stand_in_game(
    *,
    directory: Path,
    package: str = 'stand_in_rally',
    console_script: str | None = None,
    frames_before_quit: int = STAND_IN_GAME_FRAMES,
    layer: str | None = None,
) -> StandInGame:
    """Write a stand-in game package and its distribution with one console script.

    Args:
        directory: The install directory (it holds the package and the dist-info).
        package: The import package's name.
        console_script: The console script's name (the package's, kebab-case, by default); the
            distribution is named the same.
        frames_before_quit: How many frames it runs before it quits itself.
        layer: The layer its package registers itself in when imported, or None for none.

    Returns:
        The stand-in game.

    """
    script = console_script or package.replace('_', '-')
    scene_name = ''.join(part.title() for part in package.split('_')) + 'Scene'
    package_directory = directory / package
    package_directory.mkdir(parents=True)
    (package_directory / '__init__.py').write_text(
        stand_in_game_source(
            package=package,
            scene_name=scene_name,
            frames_before_quit=frames_before_quit,
            layer=layer,
        ),
        encoding='utf-8',
    )
    write_stand_in_distribution(
        directory=directory, distribution=script, console_scripts={script: f'{package}:main'}
    )
    return StandInGame(
        package=package,
        distribution=script,
        console_script=script,
        scene_name=scene_name,
        install_directory=directory,
        layer=layer,
    )


def stamp_stand_in_game(*, game: StandInGame, revision: SourceRevision) -> None:
    """Write a build stamp into a stand-in game's package, naming ``revision``.

    The stamp is read as an engine's is (``glitchygames.build_info.stamped_revision``), when no
    checkout tracks the package and it holds no archive file: a stand-in in ``tmp_path``. Its
    uncommitted-changes flag is ``revision``'s, fixed when the stamp is written (not a live
    ``git status`` in the child that runs the game).

    Args:
        game: The stand-in game.
        revision: The revision its runs name as the game's (its ``source`` is not stored: a
            stamp's is always ``BUILD_STAMP``).

    """
    stamp_fields = revision.to_json()
    del stamp_fields['source']
    (game.install_directory / game.package / BUILD_STAMP_FILE_NAME).write_text(
        json.dumps(stamp_fields, indent=2, sort_keys=True) + '\n', encoding='utf-8'
    )


def use_stand_in_game(*, install_directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put an install directory on ``sys.path`` and the child processes' ``PYTHONPATH``.

    Both are restored when the test ends.

    Args:
        install_directory: The directory a stand-in game or distribution is installed in.
        monkeypatch: pytest's fixture.

    """
    monkeypatch.syspath_prepend(install_directory)
    inherited = os.environ.get('PYTHONPATH')
    monkeypatch.setenv(
        'PYTHONPATH',
        str(install_directory)
        if not inherited
        else os.pathsep.join((str(install_directory), inherited)),
    )


def record_stand_in_game(
    *,
    game: StandInGame,
    path: Path,
    extra_arguments: tuple[str, ...] = (),
    paced: bool = False,
) -> Path:
    """Record a stand-in game's live session in a child process, headless.

    The child starts the game through its package's ``main`` (its console script's entry
    point), with this process's environment (``use_stand_in_game`` must have put its install
    directory on ``PYTHONPATH``).

    Args:
        game: The stand-in game.
        path: Where the recording goes.
        extra_arguments: More command-line arguments for the child.
        paced: Pace the run at ``STAND_IN_GAME_TARGET_FPS`` (60), as a player's is: for a test
            that reads the recorded frame times (a watched replay presents frames by them) or
            the run's pacing (``processing_paced``, its live frame times). Otherwise the run is
            uncapped (``UNPACED_TARGET_FPS``): the same frames and sprites, recorded at once.

    Returns:
        The recording's path.

    """
    completed = run_command(
        command=[
            sys.executable,
            '-c',
            f'import {game.package}; {game.package}.main()',
            '--log-level',
            'error',
            '--resolution',
            STAND_IN_GAME_RESOLUTION,
            '--target-fps',
            STAND_IN_GAME_TARGET_FPS if paced else UNPACED_TARGET_FPS,
            '--headless',
            '--record-trace',
            str(path),
            *extra_arguments,
        ],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )
    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    return path


def record_stand_in_game_once(
    *,
    game: StandInGame,
    path: Path,
    extra_arguments: tuple[str, ...] = (),
    paced: bool = False,
) -> Path:
    """Record a stand-in game's live session for many tests to read (``record_stand_in_game``).

    For a module- or session-scoped fixture, which has no test's ``monkeypatch``: the game's
    install directory is on ``sys.path`` and ``PYTHONPATH`` only while the child records. Each
    test that reads the recording takes its own copy (``copy_recording``), so one that changes
    its copy, or writes beside it, changes nothing another test reads.

    Args:
        game: The stand-in game (installed where no test changes it).
        path: Where the recording goes.
        extra_arguments: More command-line arguments for the child.
        paced: As ``record_stand_in_game``'s.

    Returns:
        The recording's path.

    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        use_stand_in_game(install_directory=game.install_directory, monkeypatch=monkeypatch)
        return record_stand_in_game(
            game=game, path=path, extra_arguments=extra_arguments, paced=paced
        )


def copy_recording(*, recording: Path, path: Path) -> Path:
    """Copy a shared recording (``record_stand_in_game_once``) to a test's own path.

    Returns:
        The copy's path (its directory made).

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(recording, path)
    return path
