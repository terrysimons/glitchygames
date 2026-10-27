"""Recordings under .../fixtures/replays/<console-script>/ become pytest items.

The plugin is glitchygames/testing/replays.py. The root conftest loads it for this suite; the
pytester runs here have their own configuration, so they load it with ``-p``. They run pytest in
a fresh interpreter: this one has already imported the plugin, so an in-process run would warn
that it cannot rewrite the plugin's assertions.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from scripts.record_scripted_session import fixture_path

from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.replay.tools.children import REPLAY_FIXTURES_PATH_PARTS
from glitchygames.testing.replays import bundled_demo_paths
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
# A golden's bytes, for the tests whose recording is never replayed (only where it lies matters)
REPO_FIXTURE = fixture_path(game_key='paddleslap')
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
    *, pytester: pytest.Pytester, console_script: str, name: str, source: Path = REPO_FIXTURE
) -> Path:
    """Copy a recording to ``fixtures/replays/<console_script>/<name>``.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.
        console_script: The game directory's name.
        name: The copy's file name.
        source: The recording copied (the PaddleSlap golden's bytes when only its place
            matters, never replayed).

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


def test_unknown_game_directory_fails_at_collection(pytester):
    """A directory that names no console script is a collection error that says so."""
    copy_fixture_into(pytester=pytester, console_script='no-such-game', name='rally.jsonl.gz')

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


def test_misplaced_recordings_fail_at_collection(pytester):
    """A recording under fixtures/replays/ but not directly in a game's directory is an error."""
    replays_directory = pytester.path.joinpath(*REPLAY_FIXTURES_PATH_PARTS)
    nested_directory = replays_directory / 'paddleslap' / 'old'
    nested_directory.mkdir(parents=True)
    shutil.copy(REPO_FIXTURE, replays_directory / 'stray.jsonl.gz')
    shutil.copy(REPO_FIXTURE, nested_directory / 'rally.jsonl.gz')

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


# A conftest for an in-process inner run: it takes the plugin's collection hook by import, so
# the inner run collects recordings without loading (and asking to rewrite) the plugin module,
# which this interpreter has already imported. In-process, the coverage of the collector and the
# item is measured, and the child replay can be replaced at its boundary.
IN_PROCESS_PLUGIN_CONFTEST = """
from glitchygames.testing.replays import pytest_collect_file
"""


def run_pytest_in_process(*, pytester: pytest.Pytester) -> pytest.RunResult:
    """Run pytest over ``fixtures`` in this interpreter, with the plugin's collection hook.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.

    Returns:
        pytester's run result.

    """
    pytester.makeconftest(IN_PROCESS_PLUGIN_CONFTEST)
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
        pytester.makeconftest(IN_PROCESS_PLUGIN_CONFTEST)

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
        from glitchygames.testing import replays

        write_collected_only_recording(
            pytester=pytester, console_script=stand_in_game.console_script, name='rally.jsonl.gz'
        )
        replay_child = mocker.patch.object(
            replays,
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
        from glitchygames.testing import replays

        write_collected_only_recording(
            pytester=pytester, console_script=stand_in_game.console_script, name='rally.jsonl.gz'
        )
        mocker.patch.object(
            replays,
            'replay_recording_headless',
            return_value=CompletedProcess(args=[], returncode=int(ExitCode.SUCCESS), stdout=''),
        )

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(passed=1)
