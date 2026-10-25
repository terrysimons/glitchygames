"""The code a replay measurement measured: a git tree hash with the ledger left out.

A measured row (``quality/replay-ledger/``, plans/2026-10-25-measured-rows-in-the-repository.md)
names the code it measured by tree, not by commit: the measuring pre-commit hook runs before its
commit exists, an amend or a squash merge gives the same code another commit, but the tree of
the code stays the same. The ledger directory is left out, since the rows the hook adds would
otherwise change the tree they name.

Both functions work on a temporary index (``GIT_INDEX_FILE``), so the real one, and with it
whatever is staged, is never touched. A failing git command raises ``RuntimeError`` naming it.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from glitchygames.process import run_command

# Where the measured rows live: left out of every code tree
LEDGER_DIRECTORY = 'quality/replay-ledger'
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


def _tree_without_the_ledger(*, repository: Path, index_file: Path) -> str:
    """Drop the ledger directory from a temporary index and return the index's tree.

    Returns:
        The tree hash.

    """
    run_git(
        repository=repository,
        arguments=['rm', '-r', '--cached', '--ignore-unmatch', '--quiet', LEDGER_DIRECTORY],
        index_file=index_file,
    )
    return run_git(repository=repository, arguments=['write-tree'], index_file=index_file)


def staged_code_tree(*, repository: Path) -> str:
    """Return the code tree of what is staged (what the next commit will hold, minus the ledger).

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
        return _tree_without_the_ledger(repository=repository, index_file=index_file)


def commit_code_tree(*, repository: Path, commit: str) -> str:
    """Return the code tree of a commit (its tree, minus the ledger).

    Args:
        repository: The repository's working directory.
        commit: Any commit-ish (``HEAD``, a hash, ``origin/main``).

    Returns:
        The tree hash.

    """
    with tempfile.TemporaryDirectory(prefix='code-tree-') as directory_name:
        index_file = Path(directory_name) / 'index'
        run_git(repository=repository, arguments=['read-tree', commit], index_file=index_file)
        return _tree_without_the_ledger(repository=repository, index_file=index_file)
