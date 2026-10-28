"""Recordings under .../fixtures/replays/<console-script>/ become pytest items.

The plugin is glitchygames/testing/replays.py. It registers itself through the engine's
``pytest11`` entry point (named after its module), so every pytest run with glitchygames
installed loads it, this suite's and each pytester run's alike. Most pytester runs here also
name it with ``-p``, which loading it explicitly must still allow. They run pytest in a fresh
interpreter: this one has already imported the plugin, so an in-process run that names it would
warn that it cannot rewrite the plugin's assertions (the in-process runs below name none).
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.replay.tools import children
from glitchygames.testing.replays import bundled_demo_paths
from glitchygames.tracing import REPLAY_FIXTURES_PATH_PARTS
from tests.replay.replay_helpers import tamper_first_sprite_rect
from tests.stand_in_games import (
    StandInGame,
    record_stand_in_game,
    use_stand_in_game,
    write_stand_in_distribution,
    write_stand_in_game,
    write_stand_in_package,
    write_stand_in_recording,
)
from tests.workspace_expectations import MEMBER_PACKAGES

if TYPE_CHECKING:
    from pathlib import Path

PLUGIN_MODULE = 'glitchygames.testing.replays'
# The plugin's name as the engine's pytest11 entry point registers it (pyproject.toml): its
# module's, so an explicit load by that name is the same plugin, and ``-p no:<it>`` blocks it
PLUGIN_ENTRY_POINT_NAME = PLUGIN_MODULE
# The distribution pytest's header names for the entry point's plugin (``plugins: ...``)
ENGINE_DISTRIBUTION = 'glitchygames'
# pygame's banner variable: unset for the runs that check the plugin prints no banner
PYGAME_BANNER_VARIABLE = 'PYGAME_HIDE_SUPPORT_PROMPT'
# Loads the plugin module alone in a fresh interpreter and prints, as JSON, which of the modules
# that would print pygame's banner (or import it) are then imported, and every glitchygames
# module the load imported
PLUGIN_LOAD_IMPORTS_SCRIPT = f"""
import json
import sys
already_imported = set(sys.modules)
import {PLUGIN_MODULE}
print(json.dumps({{
    'banner_modules': sorted(
        name for name in ('pygame', 'glitchygames.replay') if name in sys.modules
    ),
    'engine_modules': sorted(
        name
        for name in set(sys.modules) - already_imported
        if name == 'glitchygames' or name.startswith('glitchygames.')
    ),
}}))
"""
# The engine modules the plugin imports when it loads: pygame-free leaves. pytest loads an entry
# point plugin before pytest-cov starts measuring, so these modules' top-level lines run before
# coverage does in every run of this suite (test_a_fresh_load_of_the_plugin_... loads them again)
PLUGIN_LOAD_MODULES = (
    PLUGIN_MODULE,
    'glitchygames.bundled_demos',
    'glitchygames.exit_codes',
    'glitchygames.tracing',
)
# The packages a load of the plugin imports on the way to it: docstring-only, nothing to measure
PLUGIN_PARENT_PACKAGES = ('glitchygames', 'glitchygames.testing')
# The engine's replay tools, which import pygame: the plugin imports them only for a recording
REPLAY_TOOLS_PACKAGE = 'glitchygames.replay'
# The start of pygame's banner (``pygame-ce 2.5.8 (SDL 2.32.10, Python 3.14.8)``)
PYGAME_BANNER_START = f'pygame-ce {pygame.version.ver}'
# The top directory of pytester's copy of the fixture layout (fixtures/replays/<console-script>/)
FIXTURES_DIRECTORY_NAME = REPLAY_FIXTURES_PATH_PARTS[0]
# A pytest run of one recording takes a few seconds
SUBPROCESS_TIMEOUT_SECONDS = 300
# The frame a tampered copy of the fixture first differs from the engine at (the stand-in game
# draws a sprite on it and every frame after it)
TAMPERED_FRAME = 10
# A stand-in recording only collected, never replayed: a bookmark on frame 2 needs at least 2
# frames
COLLECTED_ONLY_RECORDING_FRAMES = 3
# The collection error for a recording that is not directly in a game's directory
MISPLACED_RECORDING_LINE = '*recordings go in fixtures/replays/<console-script>/*'
# A conftest for the inner run that deletes each collected recording before it runs
DELETE_RECORDINGS_AFTER_COLLECTION = """
def pytest_collection_finish(session):
    for item in session.items:
        item.path.unlink()
"""

# A conftest for the inner run that skips every item by marker, reported at the item's location
SKIP_EVERY_ITEM_BY_MARKER = """
import pytest


def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker(pytest.mark.skip(reason='skipped by marker'))
"""


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Its facts: one console script (``stand-in-rally``), one scene, a sprite on every frame,
    seeded and deterministic, no input; it quits itself after 20 frames.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


@pytest.fixture
def placed_only_recording(tmp_path_factory) -> Path:
    """Return a stand-in recording for the tests where only where a copy lies matters.

    It is never replayed (its directories name no game, or the wrong depth), so a recording the
    trace writer makes (``write_stand_in_recording``, no game run) is enough.

    Returns:
        Its path (outside pytester's directory).

    """
    path = tmp_path_factory.mktemp('placed-only') / 'rally.jsonl.gz'
    write_stand_in_recording(path=path, frame_count=COLLECTED_ONLY_RECORDING_FRAMES)
    return path


@pytest.fixture
def stand_in_recording(stand_in_game, tmp_path_factory) -> Path:
    """Return a recording of the stand-in game's session, made by a child ``--record-trace``.

    Returns:
        Its path (outside pytester's directory).

    """
    return record_stand_in_game(
        game=stand_in_game, path=tmp_path_factory.mktemp('recorded') / 'rally.jsonl.gz'
    )


def game_directory(*, pytester: pytest.Pytester, console_script: str) -> Path:
    """Make ``fixtures/replays/<console_script>/`` under pytester's path (if it is not there).

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.
        console_script: The game directory's name.

    Returns:
        The directory.

    """
    directory = pytester.path.joinpath(*REPLAY_FIXTURES_PATH_PARTS, console_script)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def copy_fixture_into(
    *, pytester: pytest.Pytester, console_script: str, name: str, source: Path
) -> Path:
    """Copy a recording to ``fixtures/replays/<console_script>/<name>``.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.
        console_script: The game directory's name.
        name: The copy's file name.
        source: The recording copied (``placed_only_recording`` when only its place matters,
            never replayed).

    Returns:
        The copy's path.

    """
    target = game_directory(pytester=pytester, console_script=console_script) / name
    shutil.copy(source, target)
    return target


def write_collected_only_recording(
    *, pytester: pytest.Pytester, console_script: str, name: str
) -> Path:
    """Write a stand-in recording to ``fixtures/replays/<console_script>/<name>``, never replayed.

    Returns:
        Its path.

    """
    path = game_directory(pytester=pytester, console_script=console_script) / name
    write_stand_in_recording(path=path, frame_count=COLLECTED_ONLY_RECORDING_FRAMES)
    return path


def run_pytest(
    *, pytester: pytest.Pytester, arguments: tuple[str, ...] = (FIXTURES_DIRECTORY_NAME,)
) -> pytest.RunResult:
    """Run pytest with the plugin in a fresh interpreter, by default over ``fixtures``.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.
        arguments: pytest's arguments after the plugin options.

    Returns:
        pytester's run result.

    """
    return pytester.runpytest_subprocess(
        '-p',
        PLUGIN_MODULE,
        '-p',
        'no:cacheprovider',
        *arguments,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def test_matching_recording_passes(pytester, stand_in_game, stand_in_recording):
    """A recording the game still reproduces is one passing item, named <console-script>/<name>.

    The stand-in game is seeded and deterministic, so its child replay reproduces every frame.
    """
    script = stand_in_game.console_script
    copy_fixture_into(
        pytester=pytester, console_script=script, name='rally.jsonl.gz', source=stand_in_recording
    )

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(passed=1)
    collected = run_pytest(
        pytester=pytester, arguments=('--collect-only', '-q', FIXTURES_DIRECTORY_NAME)
    )
    collected.stdout.fnmatch_lines([f'fixtures/replays/{script}/rally.jsonl.gz::{script}/rally'])


def test_a_recording_can_be_skipped_from_a_marker(pytester, stand_in_game):
    """A skip reported at the item's location works for a recording (as --benchmark-only does).

    pytest reports such a skip at ``reportinfo()``'s line, which must not be None. Only the
    stand-in's console script and one recording file are needed: the item is skipped, so no
    child replays it.
    """
    write_collected_only_recording(
        pytester=pytester, console_script=stand_in_game.console_script, name='rally.jsonl.gz'
    )
    pytester.makeconftest(SKIP_EVERY_ITEM_BY_MARKER)

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(skipped=1)
    assert 'INTERNALERROR' not in result.stdout.str()


def test_unknown_game_directory_fails_at_collection(pytester, placed_only_recording):
    """A directory that names no console script is a collection error that says so."""
    copy_fixture_into(
        pytester=pytester,
        console_script='no-such-game',
        name='rally.jsonl.gz',
        source=placed_only_recording,
    )

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(errors=1)
    result.stdout.fnmatch_lines(['*no-such-game*not a console script*'])


def test_other_files_are_not_collected(pytester, stand_in_game, stand_in_recording):
    """Only .jsonl.gz files in a game's directory under fixtures/replays/ are recordings.

    The one collected recording is the deterministic stand-in game's, which replays clean; the
    stray copies are the same file.
    """
    script = stand_in_game.console_script
    for name in ('rally.jsonl.gz', 'notes.txt'):
        copy_fixture_into(
            pytester=pytester, console_script=script, name=name, source=stand_in_recording
        )
    for elsewhere in (pytester.path / 'replays' / script, pytester.path / 'recordings' / script):
        elsewhere.mkdir(parents=True)
        shutil.copy(stand_in_recording, elsewhere / 'rally.jsonl.gz')

    result = run_pytest(pytester=pytester, arguments=())

    # Only fixtures/replays/<script>/rally.jsonl.gz
    result.assert_outcomes(passed=1)


def test_a_bookmarked_copy_is_not_collected(pytester, stand_in_game):
    """S on a watched fixture writes x.bookmarked.jsonl.gz beside it: not a regression test.

    The stand-in recording has 3 frames, so frame 2 can be bookmarked; it is only collected.
    """
    script = stand_in_game.console_script
    fixture = write_collected_only_recording(
        pytester=pytester, console_script=script, name='rally.jsonl.gz'
    )
    copy = fixture.with_name('rally.bookmarked.jsonl.gz')
    write_bookmarked_copy(recording_path=fixture, bookmarks=[2], destination=copy)

    collected = run_pytest(
        pytester=pytester, arguments=('--collect-only', '-q', FIXTURES_DIRECTORY_NAME)
    )

    collected.stdout.fnmatch_lines([f'fixtures/replays/{script}/rally.jsonl.gz::{script}/rally'])
    collected.stdout.no_fnmatch_line('*rally.bookmarked*')


def test_misplaced_recordings_fail_at_collection(pytester, placed_only_recording):
    """A recording under fixtures/replays/ but not directly in a game's directory is an error."""
    replays_directory = pytester.path.joinpath(*REPLAY_FIXTURES_PATH_PARTS)
    nested_directory = replays_directory / 'paddleslap' / 'old'
    nested_directory.mkdir(parents=True)
    shutil.copy(placed_only_recording, replays_directory / 'stray.jsonl.gz')
    shutil.copy(placed_only_recording, nested_directory / 'rally.jsonl.gz')

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(errors=2)
    result.stdout.fnmatch_lines([MISPLACED_RECORDING_LINE, MISPLACED_RECORDING_LINE])


def test_tampered_recording_fails_with_the_report(pytester, stand_in_game, stand_in_recording):
    """A recording the game no longer reproduces fails with the replay's divergence report.

    The stand-in game draws a sprite on every frame from frame 0, so moving the first sprite
    1 px from TAMPERED_FRAME on diverges there.
    """
    script = stand_in_game.console_script
    path = copy_fixture_into(
        pytester=pytester,
        console_script=script,
        name='tampered.jsonl.gz',
        source=stand_in_recording,
    )
    tamper_first_sprite_rect(recording_path=path, frame_number=TAMPERED_FRAME)

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        f'*{script}/tampered: the replay exited REPLAY_DIVERGED (1)',
        f'*Replay diverged at frame {TAMPERED_FRAME}*',
    ])


def test_unusable_recording_fails_with_the_exit_code(pytester, stand_in_game):
    """A file the replay refuses (not a recording) fails as an unusable recording.

    Only the stand-in's console script is needed: its child refuses the garbage file.
    """
    script = stand_in_game.console_script
    directory = game_directory(pytester=pytester, console_script=script)
    (directory / 'garbage.jsonl.gz').write_bytes(b'not gzip')

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        f'*{script}/garbage: the replay exited UNUSABLE_INPUT (65) (unusable recording)'
    ])


def test_missing_recording_fails_as_unusable(pytester, stand_in_game):
    """A recording gone by the time its item runs fails with MISSING_INPUT, as unusable.

    Only the stand-in's console script and a recording deleted after collection are needed.
    """
    script = stand_in_game.console_script
    write_collected_only_recording(pytester=pytester, console_script=script, name='gone.jsonl.gz')
    pytester.makeconftest(DELETE_RECORDINGS_AFTER_COLLECTION)

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        f'*{script}/gone: the replay exited MISSING_INPUT (66) (unusable recording)'
    ])


def collect_only(*, pytester: pytest.Pytester, plugin_options: tuple[str, ...]) -> pytest.RunResult:
    """Collect ``fixtures`` in a fresh interpreter, loading the plugin only as told.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.
        plugin_options: The options about the plugin (none: it loads by its entry point alone).

    Returns:
        pytester's run result.

    """
    return pytester.runpytest_subprocess(
        *plugin_options,
        '-p',
        'no:cacheprovider',
        '--collect-only',
        '-q',
        FIXTURES_DIRECTORY_NAME,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


def test_the_plugin_loads_without_a_conftest_line(pytester, stand_in_game):
    """With glitchygames installed, a project's recordings are collected with no conftest line.

    The engine's pytest11 entry point registers the plugin: the run names it nowhere, and the
    recording is one item (only collected, never replayed).
    """
    script = stand_in_game.console_script
    write_collected_only_recording(pytester=pytester, console_script=script, name='rally.jsonl.gz')

    collected = collect_only(pytester=pytester, plugin_options=())

    collected.stdout.fnmatch_lines([f'fixtures/replays/{script}/rally.jsonl.gz::{script}/rally'])
    collected.stdout.fnmatch_lines(['1 test collected*'])


@pytest.mark.parametrize(
    ('plugin_options', 'conftest_plugins'),
    [
        pytest.param(('-p', PLUGIN_MODULE), (), id='by -p'),
        pytest.param((), (PLUGIN_MODULE,), id='by a conftest'),
    ],
)
def test_loading_the_plugin_explicitly_too_collects_each_recording_once(
    pytester, stand_in_game, plugin_options, conftest_plugins
):
    """A project that still loads the plugin by name gets each recording once, and no error.

    The entry point registers it as well, so an explicit load must not register it twice
    (pluggy refuses one module under two names; the entry point has the module's name, which
    pytest skips as already registered) or collect each recording twice.
    """
    script = stand_in_game.console_script
    write_collected_only_recording(pytester=pytester, console_script=script, name='rally.jsonl.gz')
    pytester.makeconftest(f'pytest_plugins = {list(conftest_plugins)!r}\n')

    collected = collect_only(pytester=pytester, plugin_options=plugin_options)

    assert collected.ret == pytest.ExitCode.OK, collected.stdout.str()
    collected.stdout.fnmatch_lines([f'fixtures/replays/{script}/rally.jsonl.gz::{script}/rally'])
    collected.stdout.fnmatch_lines(['1 test collected*'])


def test_p_no_glitchygames_testing_replays_disables_the_plugin(pytester, stand_in_game):
    """``-p no:glitchygames.testing.replays`` blocks the entry point: a recording is no item."""
    script = stand_in_game.console_script
    write_collected_only_recording(pytester=pytester, console_script=script, name='rally.jsonl.gz')

    collected = collect_only(
        pytester=pytester, plugin_options=('-p', f'no:{PLUGIN_ENTRY_POINT_NAME}')
    )

    assert collected.ret == pytest.ExitCode.NO_TESTS_COLLECTED, collected.stdout.str()
    collected.stdout.no_fnmatch_line('*rally.jsonl.gz*')


def test_loading_the_plugin_imports_neither_pygame_nor_the_engines_replay_tools():
    """Every pytest run loads the plugin, so loading it imports no pygame (nor its banner).

    The replay tools (``glitchygames.replay``, which imports pygame) are imported only once a
    recording is found. The engine modules it does import are exactly ``PLUGIN_LOAD_MODULES``
    (and their docstring-only packages). A fresh interpreter, so this suite's own imports do not
    count.
    """
    environment = {
        name: value for name, value in os.environ.items() if name != PYGAME_BANNER_VARIABLE
    }

    finished = run_command(
        command=[sys.executable, '-c', PLUGIN_LOAD_IMPORTS_SCRIPT],
        environment=environment,
        timeout_seconds=SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
    )

    assert finished.returncode == 0, finished.stdout
    imports = json.loads(finished.stdout)
    assert imports['banner_modules'] == []
    # PLUGIN_LOAD_MODULES must name every engine module the load imports (the fresh-load test
    # below measures exactly those): a new eager import fails here, by name
    assert imports['engine_modules'] == sorted({*PLUGIN_PARENT_PACKAGES, *PLUGIN_LOAD_MODULES})


def test_a_fresh_load_of_the_plugin_imports_only_its_pygame_free_leaves(monkeypatch):
    """Loading the plugin in this interpreter imports the leaves it names, not the replay tools.

    The plugin, its leaves and every ``glitchygames.replay`` module are taken out of
    ``sys.modules`` (``monkeypatch`` puts them, and the packages' attributes naming them, back
    afterwards), then the plugin is imported as its entry point imports it. The fresh load runs
    their top-level lines while coverage measures, which the entry point's own load (before
    pytest-cov starts) never does.
    """
    removed_names = [
        name
        for name in sys.modules
        if name in PLUGIN_LOAD_MODULES
        or name == REPLAY_TOOLS_PACKAGE
        or name.startswith(f'{REPLAY_TOOLS_PACKAGE}.')
    ]
    for name in removed_names:
        parent_name, _, child_name = name.rpartition('.')
        parent = sys.modules.get(parent_name)
        if parent is not None and hasattr(parent, child_name):
            monkeypatch.setattr(parent, child_name, getattr(parent, child_name))
        monkeypatch.delitem(sys.modules, name)

    importlib.import_module(PLUGIN_MODULE)

    assert [name for name in PLUGIN_LOAD_MODULES if name not in sys.modules] == []
    assert [
        name
        for name in sys.modules
        if name == REPLAY_TOOLS_PACKAGE or name.startswith(f'{REPLAY_TOOLS_PACKAGE}.')
    ] == []


def test_a_project_with_no_recordings_and_no_settings_gets_no_items_and_no_output(
    pytester, monkeypatch, placed_only_recording
):
    """A project that is no game gets nothing from the auto-registered plugin.

    The project has no ``fixtures/replays/`` and no ``pyproject.toml`` (so no
    ``[tool.glitchygames]``); a ``.jsonl.gz`` outside ``fixtures/replays/`` is no recording of
    the plugin's. pygame's banner variable is unset, as in a project that never heard of it:
    the plugin is loaded (pytest lists it among its plugins), yet nothing is collected, pygame's
    banner is nowhere in the output, and the project's files are unchanged.
    """
    monkeypatch.delenv(PYGAME_BANNER_VARIABLE, raising=False)
    project = pytester.mkdir('project')
    shutil.copy(placed_only_recording, project / 'notes.jsonl.gz')
    (project / 'data').mkdir()
    shutil.copy(placed_only_recording, project / 'data' / 'rally.jsonl.gz')
    files_before = sorted(path.relative_to(project) for path in project.rglob('*'))

    result = pytester.runpytest_subprocess(
        '-p', 'no:cacheprovider', str(project), timeout=SUBPROCESS_TIMEOUT_SECONDS
    )

    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED, result.stdout.str()
    result.stdout.fnmatch_lines([f'plugins:*{ENGINE_DISTRIBUTION}-*'])
    result.stdout.fnmatch_lines(['*no tests ran*'])
    assert PYGAME_BANNER_START not in result.stdout.str()
    assert PYGAME_BANNER_START not in result.stderr.str()
    assert not result.stderr.lines
    assert sorted(path.relative_to(project) for path in project.rglob('*')) == files_before


def test_bundled_demo_paths_pairs_each_demo_with_its_games_console_script(tmp_path, monkeypatch):
    """A package's demos/*.jsonl.gz are demos of the console script whose entry point is in it.

    A stand-in package with one demo, and a stand-in distribution whose console script's entry
    point is in that package.
    """
    demo_directory = write_stand_in_package(
        directory=tmp_path, package='stand_in_rally', demo_names=('rally.jsonl.gz',)
    )
    write_stand_in_distribution(
        directory=tmp_path,
        distribution='stand-in-rally',
        console_scripts={'stand-in-rally': 'stand_in_rally:main'},
    )
    monkeypatch.syspath_prepend(tmp_path)

    demos = bundled_demo_paths(packages=('stand_in_rally',))

    assert demos == [('stand-in-rally', demo_directory / 'rally.jsonl.gz')]


def test_bundled_demo_paths_refuses_a_demo_of_a_game_without_a_console_script(
    tmp_path, monkeypatch
):
    """A demo no console script can replay is an error, not a demo left untested."""
    write_stand_in_package(
        directory=tmp_path, package='stand_in_game_without_a_script', demo_names=('rally.jsonl.gz',)
    )
    monkeypatch.syspath_prepend(tmp_path)

    with pytest.raises(ValueError, match=r'no console script .* in stand_in_game_without_a_script'):
        bundled_demo_paths(packages=('stand_in_game_without_a_script',))


def test_bundled_demo_paths_are_exactly_the_engines_bundled_demos():
    """The plugin reports the engine's lookup (glitchygames.bundled_demos), nothing of its own."""
    assert bundled_demo_paths(packages=MEMBER_PACKAGES) == [
        (demo.console_script, demo.path) for demo in bundled_demos(packages=MEMBER_PACKAGES)
    ]


def run_pytest_in_process(*, pytester: pytest.Pytester) -> pytest.RunResult:
    """Run pytest over ``fixtures`` in this interpreter, with the plugin its entry point loads.

    In-process, the coverage of the collector and the item is measured, and the child replay can
    be replaced at its boundary (``children.replay_recording_headless``, which the item imports
    when it runs). The inner run registers the module this interpreter has already imported, by
    its entry point; it names no plugin, so it asks to rewrite nothing already imported.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.

    Returns:
        pytester's run result.

    """
    return pytester.runpytest_inprocess('-p', 'no:cacheprovider', FIXTURES_DIRECTORY_NAME)


class TestPluginInProcess:
    """The collector and the item, run in this interpreter with the child replay stubbed out."""

    def test_an_unknown_game_directory_is_a_collection_error(self, pytester):
        """A directory that names no console script fails collection, saying so."""
        directory = game_directory(pytester=pytester, console_script='no-such-game')
        (directory / 'rally.jsonl.gz').write_bytes(b'')

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines(["*'no-such-game' is not a console script*"])

    def test_a_misplaced_recording_is_a_collection_error(self, pytester):
        """A recording directly in fixtures/replays/ of no workspace member fails collection.

        Directly in ``fixtures/replays/`` is a member's layout: the directory above ``tests/``
        names the member's distribution, and pytester's temporary directory is none.
        """
        replays_directory = pytester.path.joinpath(*REPLAY_FIXTURES_PATH_PARTS)
        replays_directory.mkdir(parents=True)
        (replays_directory / 'stray.jsonl.gz').write_bytes(b'')

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines([MISPLACED_RECORDING_LINE])

    def test_a_recording_nested_below_a_game_directory_is_a_collection_error(self, pytester):
        """A recording in neither layout (below a game's directory) fails collection."""
        nested_directory = game_directory(pytester=pytester, console_script='paddleslap') / 'old'
        nested_directory.mkdir()
        (nested_directory / 'rally.jsonl.gz').write_bytes(b'')

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(errors=1)
        result.stdout.fnmatch_lines([MISPLACED_RECORDING_LINE])

    def test_a_bookmarked_copy_is_not_collected(self, pytester, stand_in_game):
        """A viewer's bookmarked copy beside a fixture is not an item of its own.

        The stand-in recording has frames to bookmark; it is only collected.
        """
        fixture = write_collected_only_recording(
            pytester=pytester, console_script=stand_in_game.console_script, name='rally.jsonl.gz'
        )
        write_bookmarked_copy(
            recording_path=fixture,
            bookmarks=[2],
            destination=fixture.with_name('rally.bookmarked.jsonl.gz'),
        )
        result = pytester.runpytest_inprocess(
            '-p', 'no:cacheprovider', '--collect-only', '-q', FIXTURES_DIRECTORY_NAME
        )

        result.stdout.fnmatch_lines([f'*rally.jsonl.gz::{stand_in_game.console_script}/rally'])
        result.stdout.no_fnmatch_line('*rally.bookmarked*')

    @pytest.mark.parametrize(
        ('exit_code', 'expected_line'),
        [
            (
                ExitCode.REPLAY_DIVERGED,
                '*stand-in-rally/rally: the replay exited REPLAY_DIVERGED (1)',
            ),
            (
                ExitCode.UNUSABLE_INPUT,
                '*stand-in-rally/rally: the replay exited UNUSABLE_INPUT (65) (unusable recording)',
            ),
        ],
    )
    def test_a_failed_replay_fails_the_item_with_its_exit_code_and_output(
        self, pytester, mocker, stand_in_game, exit_code, expected_line
    ):
        """A child that does not exit SUCCESS fails the item with its exit code and output.

        Only the stand-in's console script is needed: the child is replaced.
        """
        from glitchygames.process import CompletedProcess

        write_collected_only_recording(
            pytester=pytester, console_script=stand_in_game.console_script, name='rally.jsonl.gz'
        )
        replay_child = mocker.patch.object(
            children,
            'replay_recording_headless',
            return_value=CompletedProcess(
                args=[], returncode=int(exit_code), stdout='the child said this\n'
            ),
        )

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(failed=1)
        result.stdout.fnmatch_lines([expected_line, '*the child said this*'])
        assert replay_child.call_args.kwargs['console_script'] == stand_in_game.console_script

    def test_a_successful_replay_passes_the_item(self, pytester, mocker, stand_in_game):
        """A child that exits SUCCESS passes the item.

        Only the stand-in's console script is needed: the child is replaced.
        """
        from glitchygames.process import CompletedProcess

        write_collected_only_recording(
            pytester=pytester, console_script=stand_in_game.console_script, name='rally.jsonl.gz'
        )
        mocker.patch.object(
            children,
            'replay_recording_headless',
            return_value=CompletedProcess(args=[], returncode=int(ExitCode.SUCCESS), stdout=''),
        )

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(passed=1)
