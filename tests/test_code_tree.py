"""glitchygames/code_tree.py: the code a measurement measured: a git tree of what can change it."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from glitchygames.code_tree import (
    LEDGER_DIRECTORY,
    commit_code_tree,
    commit_is_on_origin_main,
    is_measured_path,
    landed_code_trees,
    origin_main_exists,
    staged_code_tree,
)
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
    write(repository=tmp_path, relative_path='src/glitchygames/game.py', text='speed = 1\n')
    write(repository=tmp_path, relative_path=f'{LEDGER_DIRECTORY}/first.json', text='{}\n')
    git(repository=tmp_path, arguments=['commit', '--quiet', '-m', 'First'])
    return tmp_path


@pytest.mark.parametrize(
    ('path', 'measured'),
    [
        ('src/glitchygames/world.py', True),
        ('src/games/mr-muncher/src/mr_muncher/game.py', True),
        ('src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz', True),
        # The root's recordings (no game's since every game is a member; a stand-in's path)
        ('tests/fixtures/replays/a-game/golden.jsonl.gz', True),
        # A demo bundled in a member's package (package data)
        ('src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz', True),
        ('uv.lock', True),
        ('src/games/mr-muncher/tests/test_mr_muncher.py', False),
        ('src/games/mr-muncher/tests/fixtures/sprites.toml', False),
        ('tests/test_world.py', False),
        ('README.md', False),
        # Not a member: the engine's own package is not a layer
        ('src/glitchygames/tests/helper.py', True),
    ],
)
def test_is_measured_path_leaves_out_members_tests_but_their_recordings(path, measured):
    """Under MEASURED_PATHS, less a member's tests/, but for its tests/fixtures/replays/."""
    assert is_measured_path(path=path) is measured


def test_the_staged_code_tree_is_the_commits_once_committed(repository):
    """What the hook measures before the commit is what the commit holds."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 2\n')
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
        'src/glitchygames/world.py',
        'src/games/mr-muncher/src/mr_muncher/game.py',
        'src/demos/joystick-demo/joystick_demo/demo.py',
        'src/apps/bitmappy/src/bitmappy/editor.py',
        # A recording at the root (no game's since every game is a member; a stand-in's path)
        'tests/fixtures/replays/a-game/golden.jsonl.gz',
        # A member's golden replay, in its own tests/fixtures/replays/
        'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz',
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
    [
        'README.md',
        'BUGS.md',
        'plans/future-features.md',
        'docs/index.md',
        'tests/test_world.py',
        # A member's tests (but its recordings) are tests too
        'src/games/mr-muncher/tests/test_mr_muncher.py',
        'src/games/mr-muncher/tests/conftest.py',
        'src/demos/joystick-demo/tests/helpers/devices.py',
    ],
)
def test_docs_plans_and_tests_leave_the_code_tree_alone(repository, relative_path):
    """A docs commit after the last measured one keeps the measured tree the one that lands."""
    before = staged_code_tree(repository=repository)
    write(repository=repository, relative_path=relative_path, text='notes\n')

    assert staged_code_tree(repository=repository) == before


def test_the_real_index_is_left_alone(repository):
    """The tree is computed on a copy of the index: nothing staged is unstaged."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 3\n')
    status_before = git(repository=repository, arguments=['status', '--porcelain'])

    staged_code_tree(repository=repository)
    commit_code_tree(repository=repository, commit='HEAD')

    assert git(repository=repository, arguments=['status', '--porcelain']) == status_before


def test_a_failing_git_command_names_itself(tmp_path):
    """Outside a repository: an error naming the git command, not a silent wrong tree."""
    with pytest.raises(RuntimeError, match='git'):
        staged_code_tree(repository=tmp_path)


def test_landed_code_trees_name_the_commit_each_measured_tree_arrived_in(repository):
    """A row lands with the commit that adds its file; the earliest such commit per tree.

    The fixture's first commit already added a row with its code (so it landed); a code change
    with a row lands too; a later docs commit adding a row adds no new tree.
    """
    first_tree = commit_code_tree(repository=repository, commit='HEAD')
    first_commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 5\n')
    write(repository=repository, relative_path=f'{LEDGER_DIRECTORY}/fast.json', text='{}\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Faster, measured'])
    faster_tree = commit_code_tree(repository=repository, commit='HEAD')
    faster_commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    write(repository=repository, relative_path='README.md', text='# notes\n')
    write(repository=repository, relative_path=f'{LEDGER_DIRECTORY}/again.json', text='{}\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Docs, measured again'])

    landed = landed_code_trees(repository=repository)

    assert set(landed) == {first_tree, faster_tree}
    assert landed[first_tree].commit == first_commit
    assert landed[faster_tree].commit == faster_commit
    assert landed[faster_tree].committed_at


def test_a_tree_measured_but_never_committed_has_not_landed(repository):
    """An intermediate commit's tree is not any row-adding commit's tree."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 7\n')
    intermediate_tree = staged_code_tree(repository=repository)
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Unmeasured'])

    assert intermediate_tree not in landed_code_trees(repository=repository)


def test_a_file_staged_one_way_and_edited_another_does_not_stop_it(repository):
    """Staged content differing from both the file and HEAD (a partly staged edit).

    git rm --cached refuses such a file unless forced; the code tree drops it from a temporary
    index only, so it must not be stopped by it.
    """
    write(repository=repository, relative_path='README.md', text='# committed\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Readme'])
    write(repository=repository, relative_path='README.md', text='# staged\n')
    (repository / 'README.md').write_text('# edited after staging\n', encoding='utf-8')

    staged = staged_code_tree(repository=repository)

    assert staged == commit_code_tree(repository=repository, commit='HEAD')


def test_a_repository_with_nothing_staged_yet_has_the_empty_code_tree(tmp_path):
    """A new repository has no index file yet: nothing is staged, so nothing is measured code."""
    git(repository=tmp_path, arguments=['init', '--quiet'])
    empty_tree = git(repository=tmp_path, arguments=['hash-object', '-t', 'tree', '/dev/null'])

    assert staged_code_tree(repository=tmp_path) == empty_tree


def test_there_is_no_origin_main_in_a_repository_without_that_ref(repository):
    """A fresh clone without the remote ref, or a test repository."""
    assert not origin_main_exists(repository=repository)


def test_origin_main_exists_once_the_ref_does(repository):
    """The remote-tracking ref makes it exist."""
    commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', commit])

    assert origin_main_exists(repository=repository)


def test_a_commit_on_origin_main_is_on_it_and_a_branch_commit_is_not(repository):
    """Equal to origin/main or one of its ancestors counts; a commit ahead of it does not."""
    landed = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', landed])
    write(repository=repository, relative_path='README.md', text='# branch work\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Branch'])
    branch_commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])

    assert commit_is_on_origin_main(repository=repository, commit=landed)
    assert not commit_is_on_origin_main(repository=repository, commit=branch_commit)


def test_an_ancestor_of_origin_main_is_on_it(repository):
    """An older commit of the branch has landed too."""
    first = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    write(repository=repository, relative_path='README.md', text='# second\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Second'])
    second = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', second])

    assert commit_is_on_origin_main(repository=repository, commit=first)


def test_a_commit_this_repository_never_had_is_not_on_origin_main(repository):
    """A row measured in another clone: its commit is unknown here, so it has not landed."""
    commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', commit])

    assert not commit_is_on_origin_main(repository=repository, commit='0' * 40)
