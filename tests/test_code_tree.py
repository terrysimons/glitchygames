"""glitchygames/code_tree.py: the code a measurement measured: a git tree of what can change it.

The paths a tree holds, the ledger directory and the landed ref are this repository's
(``[tool.glitchygames]`` in the root pyproject.toml), read once here, so these tests measure our
layout as the pre-commit hook does; a project with no unmeasured paths is tested too.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from glitchygames import code_tree
from glitchygames.code_tree import (
    CodeTreePaths,
    commit_code_tree,
    commit_has_landed,
    landed_ref_exists,
    landed_row_files,
    staged_code_tree,
    untracked_measured_files,
)
from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# This repository's settings: what a code tree holds, where the rows are, what counts as landed
OUR_SETTINGS = load_project_settings(project_root=PROJECT_ROOT)
PATHS = OUR_SETTINGS.code_tree_paths
LEDGER_DIRECTORY = OUR_SETTINGS.ledger_directory
LANDED_REF = OUR_SETTINGS.landed_ref


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
        capture_output=OutputCapture.TOGETHER,
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
def test_untracked_measured_files_leave_out_members_tests_but_their_recordings(
    repository, path, measured
):
    """Under the measured paths, less a member's tests/, but for its tests/fixtures/replays/."""
    untracked = repository / path
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text('untracked\n', encoding='utf-8')

    assert (path in untracked_measured_files(repository=repository, paths=PATHS)) is measured


def test_a_project_without_unmeasured_paths_measures_everything_under_its_measured_paths(
    repository,
):
    """No unmeasured paths (the default): a member's tests change the tree and are listed."""
    paths = CodeTreePaths(measured=('src',))
    member_test = 'src/games/mr-muncher/tests/test_mr_muncher.py'
    before = staged_code_tree(repository=repository, paths=paths)
    (repository / 'src/games/mr-muncher/tests').mkdir(parents=True)
    (repository / member_test).write_text('untracked\n', encoding='utf-8')

    assert untracked_measured_files(repository=repository, paths=paths) == [member_test]
    git(repository=repository, arguments=['add', member_test])
    assert staged_code_tree(repository=repository, paths=paths) != before


def test_the_staged_code_tree_is_the_commits_once_committed(repository):
    """What the hook measures before the commit is what the commit holds."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 2\n')
    staged = staged_code_tree(repository=repository, paths=PATHS)
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Faster'])

    assert commit_code_tree(repository=repository, commit='HEAD', paths=PATHS) == staged


def test_ledger_rows_never_change_the_code_tree(repository):
    """A row file added (as the hook adds its rows) leaves the code it measured the same."""
    before = staged_code_tree(repository=repository, paths=PATHS)
    write(repository=repository, relative_path=f'{LEDGER_DIRECTORY}/second.json', text='{}\n')

    assert staged_code_tree(repository=repository, paths=PATHS) == before
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'A row'])
    assert commit_code_tree(repository=repository, commit='HEAD', paths=PATHS) == before
    assert commit_code_tree(repository=repository, commit='HEAD~1', paths=PATHS) == before


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
    before = staged_code_tree(repository=repository, paths=PATHS)
    write(repository=repository, relative_path=relative_path, text='changed\n')

    assert staged_code_tree(repository=repository, paths=PATHS) != before


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
    before = staged_code_tree(repository=repository, paths=PATHS)
    write(repository=repository, relative_path=relative_path, text='notes\n')

    assert staged_code_tree(repository=repository, paths=PATHS) == before


def test_the_real_index_is_left_alone(repository):
    """The tree is computed on a copy of the index: nothing staged is unstaged."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 3\n')
    status_before = git(repository=repository, arguments=['status', '--porcelain'])

    staged_code_tree(repository=repository, paths=PATHS)
    commit_code_tree(repository=repository, commit='HEAD', paths=PATHS)

    assert git(repository=repository, arguments=['status', '--porcelain']) == status_before


def test_a_failing_git_command_names_itself(tmp_path):
    """Outside a repository: an error naming the git command, not a silent wrong tree."""
    with pytest.raises(RuntimeError, match='git'):
        staged_code_tree(repository=tmp_path, paths=PATHS)


def landed_files(repository: Path) -> dict[str, code_tree.LandedRowFile]:
    """Return the repository's landed row files with this repository's settings.

    Returns:
        Row file name -> where it landed.

    """
    return landed_row_files(repository=repository, ledger_directory=LEDGER_DIRECTORY, paths=PATHS)


def commit_row(*, repository: Path, row: str, message: str) -> str:
    """Add a row file and commit everything staged.

    Returns:
        The commit's full hash.

    """
    write(repository=repository, relative_path=f'{LEDGER_DIRECTORY}/{row}', text='{}\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', message])
    return git(repository=repository, arguments=['rev-parse', 'HEAD'])


def test_each_row_file_lands_with_the_commit_that_added_it(repository):
    """A row file lands with its adding commit, and that commit's code tree.

    The fixture's first commit added a row with its code; a code change with a row lands
    with its own tree; a later docs commit adding a row lands with the unchanged tree.
    """
    first_tree = commit_code_tree(repository=repository, commit='HEAD', paths=PATHS)
    first_commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 5\n')
    faster_commit = commit_row(repository=repository, row='fast.json', message='Faster, measured')
    faster_tree = commit_code_tree(repository=repository, commit='HEAD', paths=PATHS)
    write(repository=repository, relative_path='README.md', text='# notes\n')
    docs_commit = commit_row(repository=repository, row='again.json', message='Docs, measured')

    landed = landed_files(repository)

    assert {name: (file.commit, file.code_tree) for name, file in landed.items()} == {
        'first.json': (first_commit, first_tree),
        'fast.json': (faster_commit, faster_tree),
        'again.json': (docs_commit, faster_tree),
    }
    assert landed['fast.json'].committed_at


def test_code_returning_to_an_earlier_tree_dates_its_rows_by_their_own_commit(repository):
    """A revert's rows land with the revert, not the tree's first landing (BUGS.md #220.3)."""
    first_tree = commit_code_tree(repository=repository, commit='HEAD', paths=PATHS)
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 9\n')
    commit_row(repository=repository, row='changed.json', message='Changed, measured')
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 1\n')
    revert_commit = commit_row(repository=repository, row='reverted.json', message='Reverted')

    landed = landed_files(repository)

    assert landed['reverted.json'].code_tree == first_tree
    assert landed['reverted.json'].commit == revert_commit
    assert landed['first.json'].commit != revert_commit


def test_a_commits_tree_is_taken_with_its_own_measured_paths(repository):
    """A measured path added later leaves earlier commits' trees as they were (BUGS.md #220.5).

    The first commit names only src/ as measured; a later commit adds tools/. The first
    commit's tree is still taken without tools/, so its rows (measured that way) still land.
    """
    only_src = CodeTreePaths(measured=('src',))
    write(
        repository=repository,
        relative_path='pyproject.toml',
        text='[tool.glitchygames]\nmeasured-paths = ["src"]\n',
    )
    write(repository=repository, relative_path='tools/measure.py', text='rounds = 1\n')
    src_commit = commit_row(repository=repository, row='src-only.json', message='src only')
    src_only_tree = commit_code_tree(repository=repository, commit='HEAD', paths=only_src)
    write(
        repository=repository,
        relative_path='pyproject.toml',
        text='[tool.glitchygames]\nmeasured-paths = ["src", "tools"]\n',
    )
    commit_row(repository=repository, row='with-tools.json', message='tools measured')
    with_tools = CodeTreePaths(measured=('src', 'tools'))

    landed = landed_row_files(
        repository=repository, ledger_directory=LEDGER_DIRECTORY, paths=with_tools
    )

    assert landed['src-only.json'].commit == src_commit
    assert landed['src-only.json'].code_tree == src_only_tree
    assert landed['with-tools.json'].code_tree == commit_code_tree(
        repository=repository, commit='HEAD', paths=with_tools
    )


@pytest.mark.parametrize(
    'pyproject',
    [
        None,
        'not [valid toml',
        '[project]\nname = "no-settings"\n',
        'tool = 5\n',
        '[tool]\nglitchygames = 5\n',
        '[tool.glitchygames]\nmeasured-paths = "src"\n',
        '[tool.glitchygames]\nmeasured-paths = ["src"]\nunmeasured-paths = [1]\n',
    ],
)
def test_a_commit_naming_no_usable_measured_paths_uses_the_current_ones(repository, pyproject):
    """No pyproject.toml, no settings or a malformed table: the fallback (the current paths)."""
    if pyproject is not None:
        write(repository=repository, relative_path='pyproject.toml', text=pyproject)
        git(repository=repository, arguments=['commit', '--quiet', '-m', 'Settings'])

    assert (
        code_tree.commit_code_tree_paths(repository=repository, commit='HEAD', fallback=PATHS)
        == PATHS
    )


def test_a_commits_own_measured_and_unmeasured_paths_are_read(repository):
    """Both keys come from the commit's table."""
    write(
        repository=repository,
        relative_path='pyproject.toml',
        text=(
            '[tool.glitchygames]\nmeasured-paths = ["src", "uv.lock"]\n'
            'unmeasured-paths = [":(glob)src/*/tests/**"]\n'
        ),
    )
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Settings'])

    assert code_tree.commit_code_tree_paths(
        repository=repository, commit='HEAD', fallback=PATHS
    ) == CodeTreePaths(measured=('src', 'uv.lock'), unmeasured=(':(glob)src/*/tests/**',))


def test_landed_row_files_refuses_a_shallow_clone(repository, tmp_path_factory):
    """A shallow clone's log stops at its depth: refused, not read as fewer landed rows (#220.8)."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 6\n')
    commit_row(repository=repository, row='six.json', message='Measured')
    shallow = tmp_path_factory.mktemp('clones') / 'shallow'
    # --depth needs a transport: a plain path clones locally and ignores it
    git(
        repository=shallow.parent,
        arguments=['clone', '--quiet', '--depth', '1', repository.as_uri(), str(shallow)],
    )

    with pytest.raises(RuntimeError, match='shallow clone'):
        landed_files(shallow)


def test_landed_row_files_reads_each_commits_tree_once(mocker, repository):
    """A commit's tree never changes: a second build (a mkdocs serve rebuild) reads none again."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 8\n')
    commit_row(repository=repository, row='eight.json', message='Measured')
    read_trees = mocker.spy(code_tree, 'commit_code_tree')

    first = landed_files(repository)
    read_after_first = read_trees.call_count
    again = landed_files(repository)

    assert again == first
    assert read_after_first == 2  # the fixture's row-adding commit, then this one
    assert read_trees.call_count == read_after_first


def test_a_tree_measured_but_never_committed_has_not_landed(repository):
    """An intermediate commit's tree is no row file's landing tree."""
    write(repository=repository, relative_path='src/glitchygames/game.py', text='speed = 7\n')
    intermediate_tree = staged_code_tree(repository=repository, paths=PATHS)
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Unmeasured'])

    assert intermediate_tree not in {file.code_tree for file in landed_files(repository).values()}


def test_a_file_staged_one_way_and_edited_another_does_not_stop_it(repository):
    """Staged content differing from both the file and HEAD (a partly staged edit).

    git rm --cached refuses such a file unless forced; the code tree drops it from a temporary
    index only, so it must not be stopped by it.
    """
    write(repository=repository, relative_path='README.md', text='# committed\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Readme'])
    write(repository=repository, relative_path='README.md', text='# staged\n')
    (repository / 'README.md').write_text('# edited after staging\n', encoding='utf-8')

    staged = staged_code_tree(repository=repository, paths=PATHS)

    assert staged == commit_code_tree(repository=repository, commit='HEAD', paths=PATHS)


def test_a_repository_with_nothing_staged_yet_has_the_empty_code_tree(tmp_path):
    """A new repository has no index file yet: nothing is staged, so nothing is measured code."""
    git(repository=tmp_path, arguments=['init', '--quiet'])
    empty_tree = git(repository=tmp_path, arguments=['hash-object', '-t', 'tree', '/dev/null'])

    assert staged_code_tree(repository=tmp_path, paths=PATHS) == empty_tree


def test_there_is_no_origin_main_in_a_repository_without_that_ref(repository):
    """A fresh clone without the remote ref, or a test repository."""
    assert not landed_ref_exists(repository=repository, landed_ref=LANDED_REF)


def test_the_landed_ref_exists_once_the_ref_does(repository):
    """The remote-tracking ref makes it exist."""
    commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', commit])

    assert landed_ref_exists(repository=repository, landed_ref=LANDED_REF)


def test_a_commit_on_origin_main_is_on_it_and_a_branch_commit_is_not(repository):
    """Equal to origin/main or one of its ancestors counts; a commit ahead of it does not."""
    landed = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', landed])
    write(repository=repository, relative_path='README.md', text='# branch work\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Branch'])
    branch_commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])

    assert commit_has_landed(repository=repository, commit=landed, landed_ref=LANDED_REF)
    assert not commit_has_landed(repository=repository, commit=branch_commit, landed_ref=LANDED_REF)


def test_an_ancestor_of_origin_main_is_on_it(repository):
    """An older commit of the branch has landed too."""
    first = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    write(repository=repository, relative_path='README.md', text='# second\n')
    git(repository=repository, arguments=['commit', '--quiet', '-m', 'Second'])
    second = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', second])

    assert commit_has_landed(repository=repository, commit=first, landed_ref=LANDED_REF)


def test_a_commit_this_repository_never_had_is_not_on_origin_main(repository):
    """A row measured in another clone: its commit is unknown here, so it has not landed."""
    commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/origin/main', commit])

    assert not commit_has_landed(repository=repository, commit='0' * 40, landed_ref=LANDED_REF)


def test_the_landed_ref_is_the_projects_own(repository):
    """A project whose shared branch is another (``landed-ref``) lands on that ref, not main."""
    commit = git(repository=repository, arguments=['rev-parse', 'HEAD'])
    git(repository=repository, arguments=['update-ref', 'refs/remotes/upstream/trunk', commit])

    assert landed_ref_exists(repository=repository, landed_ref='upstream/trunk')
    assert commit_has_landed(repository=repository, commit=commit, landed_ref='upstream/trunk')
    assert not landed_ref_exists(repository=repository, landed_ref=LANDED_REF)
