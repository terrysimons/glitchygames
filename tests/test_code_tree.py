"""scripts/code_tree.py: the code a measurement measured: a git tree of what can change it."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from scripts.code_tree import LEDGER_DIRECTORY, commit_code_tree, staged_code_tree

from glitchygames.process import run_command

if TYPE_CHECKING:
    from pathlib import Path


def git(*, repository: Path, arguments: list[str]) -> str:
    """Run git in the repository (no signing, a fixed author).

    Returns:
        git's standard output, stripped.

    """
    completed = run_command(
        command=[
            'git',
            '-c',
            'user.name=Code Tree Test',
            '-c',
            'user.email=code-tree@example.invalid',
            '-c',
            'commit.gpgsign=false',
            *arguments,
        ],
        environment=os.environ,
        timeout_seconds=60.0,
        capture_output=True,
        working_directory=repository,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout.strip()


def write(*, repository: Path, relative_path: str, text: str) -> None:
    """Write a file in the repository and stage it."""
    path = repository / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    git(repository=repository, arguments=['add', relative_path])


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return a repository with one commit: some code and one ledger row.

    Returns:
        Its directory.

    """
    git(repository=tmp_path, arguments=['init', '--quiet'])
    write(repository=tmp_path, relative_path='glitchygames/game.py', text='speed = 1\n')
    write(repository=tmp_path, relative_path=f'{LEDGER_DIRECTORY}/first.json', text='{}\n')
    git(repository=tmp_path, arguments=['commit', '--quiet', '-m', 'First'])
    return tmp_path


def test_the_staged_code_tree_is_the_commits_once_committed(repository):
    """What the hook measures before the commit is what the commit holds."""
    write(repository=repository, relative_path='glitchygames/game.py', text='speed = 2\n')
    staged = staged_code_tree(repository=repository)
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Faster'])

    assert commit_code_tree(repository=repository, commit='HEAD') == staged


def test_ledger_rows_never_change_the_code_tree(repository):
    """A row file added (as the hook adds its rows) leaves the code it measured the same."""
    before = staged_code_tree(repository=repository)
    write(repository=repository, relative_path=f'{LEDGER_DIRECTORY}/second.json', text='{}\n')

    assert staged_code_tree(repository=repository) == before
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'A row'])
    assert commit_code_tree(repository=repository, commit='HEAD') == before
    assert commit_code_tree(repository=repository, commit='HEAD~1') == before


@pytest.mark.parametrize(
    'relative_path',
    [
        'glitchygames/world.py',
        'games/mr-muncher/mr_muncher/game.py',
        'demos/joystick-demo/joystick_demo/demo.py',
        'apps/bitmappy/bitmappy/editor.py',
        'tests/fixtures/replays/paddleslap/golden.jsonl.gz',
        'uv.lock',
        'pyproject.toml',
    ],
)
def test_a_change_that_can_change_the_replays_changes_the_code_tree(repository, relative_path):
    """The engine, games, demos, apps, recordings, dependencies and project configuration."""
    before = staged_code_tree(repository=repository)
    write(repository=repository, relative_path=relative_path, text='changed\n')

    assert staged_code_tree(repository=repository) != before


@pytest.mark.parametrize(
    'relative_path',
    ['README.md', 'BUGS.md', 'plans/future-features.md', 'docs/index.md', 'tests/test_world.py'],
)
def test_docs_plans_and_tests_leave_the_code_tree_alone(repository, relative_path):
    """A docs commit after the last measured one keeps the measured tree the one that lands."""
    before = staged_code_tree(repository=repository)
    write(repository=repository, relative_path=relative_path, text='notes\n')

    assert staged_code_tree(repository=repository) == before


def test_the_real_index_is_left_alone(repository):
    """The tree is computed on a copy of the index: nothing staged is unstaged."""
    write(repository=repository, relative_path='glitchygames/game.py', text='speed = 3\n')
    status_before = git(repository=repository, arguments=['status', '--porcelain'])

    staged_code_tree(repository=repository)
    commit_code_tree(repository=repository, commit='HEAD')

    assert git(repository=repository, arguments=['status', '--porcelain']) == status_before


def test_a_failing_git_command_names_itself(tmp_path):
    """Outside a repository: an error naming the git command, not a silent wrong tree."""
    with pytest.raises(RuntimeError, match='git'):
        staged_code_tree(repository=tmp_path)
