"""Recordings under .../fixtures/replays/<console-script>/ become pytest items.

The plugin is glitchygames/testing/replays.py. The root conftest loads it for this suite; the
pytester runs here have their own configuration, so they load it with ``-p``. They run pytest in
a fresh interpreter: this one has already imported the plugin, so an in-process run would warn
that it cannot rewrite the plugin's assertions.
"""

from __future__ import annotations

import gzip
import json
import shutil
from importlib.metadata import EntryPoint
from typing import TYPE_CHECKING

import pytest
from scripts.record_scripted_session import fixture_path

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import write_bookmarked_copy
from glitchygames.testing.replays import (
    BUNDLED_DEMO_DIRECTORY_SUFFIX,
    CONSOLE_SCRIPTS_GROUP,
    REPLAY_FIXTURES_PATH_PARTS,
    bundled_demo_paths,
    console_script_for_game_module,
    game_entry_point,
    rebaseline_recording_headless,
    recording_console_script,
    replay_recording_headless,
)
from glitchygames.tracing import TRACE_FORMAT_VERSION
from tests.replay.replay_helpers import tamper_first_sprite_rect

if TYPE_CHECKING:
    from pathlib import Path

PLUGIN_MODULE = 'glitchygames.testing.replays'
REPO_FIXTURE = fixture_path(game_key='paddleslap')
# The top directory of pytester's copy of the fixture layout (fixtures/replays/<console-script>/)
FIXTURES_DIRECTORY_NAME = REPLAY_FIXTURES_PATH_PARTS[0]
# A pytest run of one recording takes a few seconds
SUBPROCESS_TIMEOUT_SECONDS = 300
# The frame a tampered copy of the fixture first differs from the engine at
TAMPERED_FRAME = 10
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


def copy_fixture_into(*, pytester: pytest.Pytester, console_script: str, name: str) -> Path:
    """Copy the PaddleSlap fixture to ``fixtures/replays/<console_script>/<name>``.

    Args:
        pytester: pytest's fixture for running pytest in a temporary directory.
        console_script: The game directory's name.
        name: The copy's file name.

    Returns:
        The copy's path.

    """
    target = game_directory(pytester=pytester, console_script=console_script) / name
    shutil.copy(REPO_FIXTURE, target)
    return target


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


def test_game_entry_point_reads_the_console_script():
    """A console script's entry point comes from the package metadata."""
    entry_point = game_entry_point(console_script='paddleslap')

    assert entry_point.value == 'glitchygames.examples.paddleslap:main'
    assert entry_point.group == 'console_scripts'


def test_matching_recording_passes(pytester):
    """A recording the game still reproduces is one passing item, named <console-script>/<name>."""
    copy_fixture_into(pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz')

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(passed=1)
    collected = run_pytest(
        pytester=pytester, arguments=('--collect-only', '-q', FIXTURES_DIRECTORY_NAME)
    )
    collected.stdout.fnmatch_lines(['fixtures/replays/paddleslap/rally.jsonl.gz::paddleslap/rally'])


def test_a_recording_can_be_skipped_from_a_marker(pytester):
    """A skip reported at the item's location works for a recording (as --benchmark-only does).

    pytest reports such a skip at ``reportinfo()``'s line, which must not be None.
    """
    copy_fixture_into(pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz')
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


def test_other_files_are_not_collected(pytester):
    """Only .jsonl.gz files in a game's directory under fixtures/replays/ are recordings."""
    copy_fixture_into(pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz')
    copy_fixture_into(pytester=pytester, console_script='paddleslap', name='notes.txt')
    for elsewhere in (
        pytester.path / 'replays' / 'paddleslap',
        pytester.path / 'recordings' / 'paddleslap',
    ):
        elsewhere.mkdir(parents=True)
        shutil.copy(REPO_FIXTURE, elsewhere / 'rally.jsonl.gz')

    result = run_pytest(pytester=pytester, arguments=())

    # Only fixtures/replays/paddleslap/rally.jsonl.gz
    result.assert_outcomes(passed=1)


def test_a_bookmarked_copy_is_not_collected(pytester):
    """S on a watched fixture writes x.bookmarked.jsonl.gz beside it: not a regression test."""
    fixture = copy_fixture_into(
        pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz'
    )
    copy = fixture.with_name('rally.bookmarked.jsonl.gz')
    write_bookmarked_copy(recording_path=fixture, bookmarks=[2], destination=copy)

    collected = run_pytest(
        pytester=pytester, arguments=('--collect-only', '-q', FIXTURES_DIRECTORY_NAME)
    )

    collected.stdout.fnmatch_lines(['fixtures/replays/paddleslap/rally.jsonl.gz::paddleslap/rally'])
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


def test_tampered_recording_fails_with_the_report(pytester):
    """A recording the game no longer reproduces fails with the replay's divergence report."""
    path = copy_fixture_into(
        pytester=pytester, console_script='paddleslap', name='tampered.jsonl.gz'
    )
    tamper_first_sprite_rect(recording_path=path, frame_number=TAMPERED_FRAME)

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        '*paddleslap/tampered: the replay exited REPLAY_DIVERGED (1)',
        f'*Replay diverged at frame {TAMPERED_FRAME}*',
    ])


def test_unusable_recording_fails_with_the_exit_code(pytester):
    """A file the replay refuses (not a recording) fails as an unusable recording."""
    directory = game_directory(pytester=pytester, console_script='paddleslap')
    (directory / 'garbage.jsonl.gz').write_bytes(b'not gzip')

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        '*paddleslap/garbage: the replay exited UNUSABLE_INPUT (65) (unusable recording)'
    ])


def test_missing_recording_fails_as_unusable(pytester):
    """A recording gone by the time its item runs fails with MISSING_INPUT, as unusable."""
    copy_fixture_into(pytester=pytester, console_script='paddleslap', name='gone.jsonl.gz')
    pytester.makeconftest(DELETE_RECORDINGS_AFTER_COLLECTION)

    result = run_pytest(pytester=pytester)

    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        '*paddleslap/gone: the replay exited MISSING_INPUT (66) (unusable recording)'
    ])


def test_bundled_demo_paths_pairs_each_demo_with_its_games_console_script(tmp_path):
    """Every <game>_demos/*.jsonl.gz is a demo of the console script whose entry point is there."""
    demo_directory = tmp_path / f'paddleslap{BUNDLED_DEMO_DIRECTORY_SUFFIX}'
    demo_directory.mkdir()
    for name in ('serve.jsonl.gz', 'rally.jsonl.gz', 'notes.txt'):
        (demo_directory / name).write_bytes(b'')
    (tmp_path / 'paddleslap_sprites').mkdir()
    (tmp_path / 'paddleslap_sprites' / 'ball.jsonl.gz').write_bytes(b'')

    demos = bundled_demo_paths(examples_directory=tmp_path)

    assert demos == [
        ('paddleslap', demo_directory / 'rally.jsonl.gz'),
        ('paddleslap', demo_directory / 'serve.jsonl.gz'),
    ]


def test_bundled_demo_paths_refuses_a_demo_of_a_game_without_a_console_script(tmp_path):
    """A demo no console script can replay is an error, not a demo left untested."""
    demo_directory = tmp_path / f'no_such_game{BUNDLED_DEMO_DIRECTORY_SUFFIX}'
    demo_directory.mkdir()
    (demo_directory / 'rally.jsonl.gz').write_bytes(b'')

    with pytest.raises(ValueError, match=r'glitchygames\.examples\.no_such_game'):
        bundled_demo_paths(examples_directory=tmp_path)


def test_bundled_demo_paths_reads_the_examples_package_by_default():
    """Without a directory, the demos come from glitchygames/examples/."""
    demos = bundled_demo_paths()

    assert demos
    assert all(path.parent.parent.name == 'examples' for _console_script, path in demos)


def test_replay_recording_headless_returns_the_finished_replay(tmp_path):
    """The child replay's exit code and output (with the divergence report) come back."""
    tampered_path = tmp_path / 'tampered.jsonl.gz'
    shutil.copy(REPO_FIXTURE, tampered_path)
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)

    completed = replay_recording_headless(console_script='paddleslap', path=tampered_path)

    assert completed.returncode == ExitCode.REPLAY_DIVERGED
    assert f'Replay diverged at frame {TAMPERED_FRAME}' in completed.stdout


def test_rebaseline_recording_headless_writes_the_new_recording(tmp_path):
    """The child rebaselines through the console script and prints its summary."""
    new_path = tmp_path / 'rebaselined.jsonl.gz'

    completed = rebaseline_recording_headless(
        console_script='paddleslap', path=REPO_FIXTURE, new_path=new_path
    )

    assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    assert f'to {new_path}: no frames differ' in completed.stdout
    assert new_path.is_file()


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


def test_game_entry_point_of_an_unknown_console_script_raises():
    """A name no installed package has as a console script is a KeyError naming it."""
    with pytest.raises(KeyError, match='no-such-game'):
        game_entry_point(console_script='no-such-game')


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


def test_a_member_with_several_console_scripts_replays_through_the_recorded_games_script(
    tmp_path,
):
    """The header's game (a logical name) names the module, whose console script replays it.

    The engine's own distribution has several console scripts; a PaddleSlap recording is
    replayed by the one whose entry point is in PaddleSlap's module.
    """
    recording = member_recording_path(tmp_path=tmp_path, distribution='glitchygames')
    write_header_only_recording(path=recording, header={'game': 'games.paddleslap:Game'})

    assert recording_console_script(path=recording) == 'paddleslap'


def test_a_game_module_inside_the_entry_points_package_is_its_game():
    """A scene in <package>.game is the game of the console script <package>:main."""
    entry_points = [
        EntryPoint(name='classic', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP),
        EntryPoint(name='papyrus', value='space_game_papyrus:main', group=CONSOLE_SCRIPTS_GROUP),
    ]

    assert (
        console_script_for_game_module(entry_points=entry_points, game_module='space_game.game')
        == 'classic'
    )
    assert (
        console_script_for_game_module(
            entry_points=entry_points, game_module='space_game_papyrus.game'
        )
        == 'papyrus'
    )


def test_a_game_module_no_console_script_starts_is_refused():
    """None of the scripts' entry points holds the game module: no game to replay it with."""
    entry_points = [
        EntryPoint(name='classic', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP)
    ]

    with pytest.raises(KeyError, match=r"none of \['classic'\] starts other_game\.game"):
        console_script_for_game_module(entry_points=entry_points, game_module='other_game.game')


def test_a_game_module_several_console_scripts_start_is_refused():
    """Two scripts whose entry points both hold the game module: the choice is ambiguous."""
    entry_points = [
        EntryPoint(name='game', value='space_game:main', group=CONSOLE_SCRIPTS_GROUP),
        EntryPoint(name='scene', value='space_game.game:main', group=CONSOLE_SCRIPTS_GROUP),
    ]

    with pytest.raises(KeyError, match=r"\['game', 'scene'\] all start space_game\.game"):
        console_script_for_game_module(entry_points=entry_points, game_module='space_game.game')


def test_a_member_recording_whose_game_no_console_script_starts_is_refused(tmp_path):
    """A Mr. Muncher recording among the engine's scripts: none of them starts it."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='glitchygames')
    write_header_only_recording(
        path=recording, header={'game': 'games.mr_muncher.game:MrMuncherScene'}
    )

    with pytest.raises(KeyError, match=r"'glitchygames': none of .* starts mr_muncher\.game"):
        recording_console_script(path=recording)


def test_a_member_recording_without_a_game_in_its_header_is_refused(tmp_path):
    """A recording made before logical names names no game to choose a console script by."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='glitchygames')
    write_header_only_recording(
        path=recording, header={'game_module': 'glitchygames.examples.paddleslap'}
    )

    with pytest.raises(KeyError, match=r"no 'game' in its header"):
        recording_console_script(path=recording)


def test_a_member_recording_that_cannot_be_read_is_refused(tmp_path):
    """A missing recording of a several-script member: its header cannot choose the script."""
    recording = tmp_path.joinpath(
        'glitchygames', 'tests', *REPLAY_FIXTURES_PATH_PARTS, 'golden.jsonl.gz'
    )

    with pytest.raises(KeyError, match=r"header cannot be read to choose among 'glitchygames'"):
        recording_console_script(path=recording)


def test_a_member_distribution_without_console_scripts_is_refused(tmp_path):
    """An installed distribution with no console script names no game (pytest-mock has none)."""
    recording = member_recording_path(tmp_path=tmp_path, distribution='pytest-mock')

    with pytest.raises(KeyError, match=r"'pytest-mock' has no console scripts"):
        recording_console_script(path=recording)


def test_a_recording_whose_fixtures_are_not_under_tests_is_refused(tmp_path):
    """Only <member>/tests/fixtures/replays/ names a member: another project's layout does not.

    The plugin ships in the engine's wheel, so a project laid out otherwise
    (``<project>/integration/fixtures/replays/``) must not be read as a member named after the
    directory four levels up, even when a distribution of that name is installed.
    """
    recording = tmp_path.joinpath(
        'mr-muncher', 'integration', *REPLAY_FIXTURES_PATH_PARTS, 'golden.jsonl.gz'
    )

    with pytest.raises(KeyError, match=r"above fixtures/ is 'integration', not 'tests'"):
        recording_console_script(path=recording)


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

    def test_a_bookmarked_copy_is_not_collected(self, pytester):
        """A viewer's bookmarked copy beside a fixture is not an item of its own."""
        fixture = copy_fixture_into(
            pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz'
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

        result.stdout.fnmatch_lines(['*rally.jsonl.gz::paddleslap/rally'])
        result.stdout.no_fnmatch_line('*rally.bookmarked*')

    @pytest.mark.parametrize(
        ('exit_code', 'expected_line'),
        [
            (ExitCode.REPLAY_DIVERGED, '*paddleslap/rally: the replay exited REPLAY_DIVERGED (1)'),
            (
                ExitCode.UNUSABLE_INPUT,
                '*paddleslap/rally: the replay exited UNUSABLE_INPUT (65) (unusable recording)',
            ),
        ],
    )
    def test_a_failed_replay_fails_the_item_with_its_exit_code_and_output(
        self, pytester, mocker, exit_code, expected_line
    ):
        """A child that does not exit SUCCESS fails the item with its exit code and output."""
        from glitchygames.process import CompletedProcess
        from glitchygames.testing import replays

        copy_fixture_into(pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz')
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
        assert replay_child.call_args.kwargs['console_script'] == 'paddleslap'

    def test_a_successful_replay_passes_the_item(self, pytester, mocker):
        """A child that exits SUCCESS passes the item."""
        from glitchygames.process import CompletedProcess
        from glitchygames.testing import replays

        copy_fixture_into(pytester=pytester, console_script='paddleslap', name='rally.jsonl.gz')
        mocker.patch.object(
            replays,
            'replay_recording_headless',
            return_value=CompletedProcess(args=[], returncode=int(ExitCode.SUCCESS), stdout=''),
        )

        result = run_pytest_in_process(pytester=pytester)

        result.assert_outcomes(passed=1)
