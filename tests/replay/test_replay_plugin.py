"""Recordings under .../fixtures/replays/<console-script>/ become pytest items.

The plugin is glitchygames/testing/replays.py. The root conftest loads it for this suite; the
pytester runs here have their own configuration, so they load it with ``-p``. They run pytest in
a fresh interpreter: this one has already imported the plugin, so an in-process run would warn
that it cannot rewrite the plugin's assertions.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from scripts.record_scripted_session import fixture_path

from glitchygames.testing.replays import REPLAY_FIXTURES_PATH_PARTS, game_entry_point
from tests.replay.replay_helpers import tamper_first_sprite_rect

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

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
