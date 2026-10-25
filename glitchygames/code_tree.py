"""The code a replay measurement measured: a git tree of only what can change the replays.

A measured row (``quality/replay-ledger/``, plans/2026-10-25-measured-rows-in-the-repository.md)
names the code it measured by tree, not by commit: the measuring pre-commit hook runs before its
commit exists, an amend or a squash merge gives the same code another commit, but the tree of
the code stays the same. The tree holds only ``MEASURED_PATHS`` (the engine, games, demos, apps,
recordings, the locked dependencies and the project configuration): a later docs, plans or tests
commit leaves it unchanged, so the last measured tree is still the one that lands on main, and
the ledger's own rows never change the tree they name.

Both functions work on a temporary index (``GIT_INDEX_FILE``), so the real one, and with it
whatever is staged, is never touched. A failing git command raises ``RuntimeError`` naming it.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from glitchygames.process import run_command

# Where the measured rows live (not a measured path, so never part of a code tree)
LEDGER_DIRECTORY = 'quality/replay-ledger'
# What can change how the golden replays run: the only paths a code tree holds
MEASURED_PATHS = (
    'glitchygames',
    'games',
    'demos',
    'apps',
    'tests/fixtures/replays',
    'uv.lock',
    'pyproject.toml',
)
GIT_TIMEOUT_SECONDS = 60.0


def run_git(*, repository: Path, arguments: list[str], index_file: Path | None = None) -> str:
    """Run git in ``repository``, on ``index_file`` when given, and return its output.

    Returns:
        Standard output, stripped.

    Raises:
        RuntimeError: If git fails (the command and its output in the message).

    """
    environment = dict(os.environ)
    if index_file is not None:
        environment['GIT_INDEX_FILE'] = str(index_file)
    command = ['git', *arguments]
    completed = run_command(
        command=command,
        environment=environment,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=repository,
    )
    if completed.returncode != 0:
        message = f'{" ".join(command)} failed in {repository}: {completed.stdout.strip()}'
        raise RuntimeError(message)
    return completed.stdout.strip()


def _measured_tree(*, repository: Path, index_file: Path) -> str:
    """Drop all but ``MEASURED_PATHS`` from a temporary index and return the index's tree.

    Returns:
        The tree hash.

    """
    kept = [f':(exclude){path}' for path in MEASURED_PATHS]
    # --force: git rm refuses a file whose staged content differs from both the working tree
    # and HEAD (a partly staged edit); only this temporary index is changed, never a file
    run_git(
        repository=repository,
        arguments=[
            'rm',
            '-r',
            '--cached',
            '--force',
            '--ignore-unmatch',
            '--quiet',
            '--',
            '.',
            *kept,
        ],
        index_file=index_file,
    )
    return run_git(repository=repository, arguments=['write-tree'], index_file=index_file)


def staged_code_tree(*, repository: Path) -> str:
    """Return the code tree of what is staged (the measured paths the next commit will hold).

    Args:
        repository: The repository's working directory.

    Returns:
        The tree hash.

    """
    real_index = Path(
        run_git(repository=repository, arguments=['rev-parse', '--git-path', 'index'])
    )
    if not real_index.is_absolute():
        real_index = repository / real_index
    with tempfile.TemporaryDirectory(prefix='code-tree-') as directory_name:
        index_file = Path(directory_name) / 'index'
        if real_index.exists():
            shutil.copyfile(real_index, index_file)
        return _measured_tree(repository=repository, index_file=index_file)


def commit_code_tree(*, repository: Path, commit: str) -> str:
    """Return the code tree of a commit (its measured paths).

    Args:
        repository: The repository's working directory.
        commit: Any commit-ish (``HEAD``, a hash, ``origin/main``).

    Returns:
        The tree hash.

    """
    with tempfile.TemporaryDirectory(prefix='code-tree-') as directory_name:
        index_file = Path(directory_name) / 'index'
        run_git(repository=repository, arguments=['read-tree', commit], index_file=index_file)
        return _measured_tree(repository=repository, index_file=index_file)


class LandedCommit(BaseModel):
    """The commit a measured code tree landed in: the first one adding rows of that tree.

    Attributes:
        commit: The full commit hash.
        committed_at: Its commit date (ISO 8601 with its offset).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    commit: str
    committed_at: str


def landed_code_trees(*, repository: Path, revision: str = 'HEAD') -> dict[str, LandedCommit]:
    """Return each code tree that landed, with the first commit it landed in.

    A row lands with the commit that adds its file (on main: the squash merge); the code it
    measured landed only if that commit's code tree is the row's. So every commit in
    ``revision``'s history that added a row file is looked up, oldest first, and its code tree
    kept with the earliest such commit. A row of an intermediate commit or of a branch that was
    behind main names another tree: it matches none.

    Args:
        repository: The repository's working directory.
        revision: Whose history (``HEAD``: the checkout's).

    Returns:
        Code tree -> the commit it landed in.

    """
    output = run_git(
        repository=repository,
        arguments=['log', '--format=%H %cI', '--diff-filter=A', revision, '--', LEDGER_DIRECTORY],
    )
    landed: dict[str, LandedCommit] = {}
    for line in reversed(output.splitlines()):
        commit, committed_at = line.split(' ', maxsplit=1)
        tree = commit_code_tree(repository=repository, commit=commit)
        landed.setdefault(tree, LandedCommit(commit=commit, committed_at=committed_at))
    return landed
