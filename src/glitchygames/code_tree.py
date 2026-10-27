"""The code a replay measurement measured: a git tree of only what can change the replays.

A measured row (the project's ledger directory, plans/2026-10-25-measured-rows-in-the-repository.md)
names the code it measured by tree, not by commit: the measuring pre-commit hook runs before its
commit exists, an amend or a squash merge gives the same code another commit, but the tree of
the code stays the same. The tree holds only the project's measured paths (``CodeTreePaths``:
``[tool.glitchygames]`` ``measured-paths``; ours are ``src/``, the engine, games, demos and apps;
the recordings, the locked dependencies and the project configuration), less its unmeasured paths
(``unmeasured-paths``; ours are the workspace members' tests, ``src/<layer>/<member>/tests/``, but
for their recordings, ``tests/fixtures/replays/`` there, as at the root): a later docs, plans or
tests commit leaves it unchanged, so the last measured tree is still the one that lands on main,
and the ledger's own rows never change the tree they name.

Both are git pathspecs, read by git itself (``git rm``, ``git ls-files``), so their magic
(``:(glob)``, ``:(exclude)``) means what git says it means.

The tree functions work on a temporary index (``GIT_INDEX_FILE``), so the real one, and with it
whatever is staged, is never touched. A failing git command raises ``RuntimeError`` naming it.
Which commits count as landed is the project's ``landed-ref`` (ours: ``origin/main``).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from glitchygames.process import OutputCapture, run_command

GIT_TIMEOUT_SECONDS = 60.0


class CodeTreePaths(BaseModel):
    """What a code tree holds: git pathspecs, relative to the repository.

    Attributes:
        measured: The paths a code tree holds (``[tool.glitchygames]`` ``measured-paths``).
        unmeasured: The paths left out of them (``unmeasured-paths``; none by default).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    measured: tuple[str, ...]
    unmeasured: tuple[str, ...] = ()


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
        capture_output=OutputCapture.TOGETHER,
        working_directory=repository,
    )
    if completed.returncode != 0:
        message = f'{" ".join(command)} failed in {repository}: {completed.stdout.strip()}'
        raise RuntimeError(message)
    return completed.stdout.strip()


def untracked_measured_files(*, repository: Path, paths: CodeTreePaths) -> list[str]:
    """Return the untracked (not ignored) files a code tree of the working tree would hold.

    git lists the untracked files under the measured paths, and those under the unmeasured ones
    are left out, so the pathspecs mean exactly what they mean to the tree functions.

    Args:
        repository: The repository's working directory.
        paths: What a code tree holds.

    Returns:
        Their repository-relative paths, ``/``-separated, in git's order.

    """
    untracked = ['ls-files', '--others', '--exclude-standard', '--']
    measured = run_git(repository=repository, arguments=[*untracked, *paths.measured])
    unmeasured: set[str] = (
        set(run_git(repository=repository, arguments=[*untracked, *paths.unmeasured]).splitlines())
        if paths.unmeasured
        else set()
    )
    return [line for line in measured.splitlines() if line and line not in unmeasured]


def _measured_tree(*, repository: Path, index_file: Path, paths: CodeTreePaths) -> str:
    """Drop all but the measured paths from a temporary index and return the index's tree.

    The measured paths are kept, then the unmeasured ones dropped (ours: the members' tests,
    but for their recordings).

    Returns:
        The tree hash.

    """
    kept = [f':(exclude){path}' for path in paths.measured]
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
    # git rm with no pathspec is refused ("No pathspec was given"): nothing to drop then
    if paths.unmeasured:
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
                *paths.unmeasured,
            ],
            index_file=index_file,
        )
    return run_git(repository=repository, arguments=['write-tree'], index_file=index_file)


def staged_code_tree(*, repository: Path, paths: CodeTreePaths) -> str:
    """Return the code tree of what is staged (the measured paths the next commit will hold).

    Args:
        repository: The repository's working directory.
        paths: What a code tree holds.

    Returns:
        The tree hash.

    """
    real_index = Path(
        run_git(
            repository=repository,
            arguments=['rev-parse', '--path-format=absolute', '--git-path', 'index'],
        )
    )
    with tempfile.TemporaryDirectory(prefix='code-tree-') as directory_name:
        index_file = Path(directory_name) / 'index'
        if real_index.exists():
            shutil.copyfile(real_index, index_file)
        return _measured_tree(repository=repository, index_file=index_file, paths=paths)


def commit_code_tree(*, repository: Path, commit: str, paths: CodeTreePaths) -> str:
    """Return the code tree of a commit (its measured paths).

    Args:
        repository: The repository's working directory.
        commit: Any commit-ish (``HEAD``, a hash, ``origin/main``).
        paths: What a code tree holds.

    Returns:
        The tree hash.

    """
    with tempfile.TemporaryDirectory(prefix='code-tree-') as directory_name:
        index_file = Path(directory_name) / 'index'
        run_git(repository=repository, arguments=['read-tree', commit], index_file=index_file)
        return _measured_tree(repository=repository, index_file=index_file, paths=paths)


class LandedCommit(BaseModel):
    """The commit a measured code tree landed in: the first one adding rows of that tree.

    Attributes:
        commit: The full commit hash.
        committed_at: Its commit date (ISO 8601 with its offset).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    commit: str
    committed_at: str


def landed_code_trees(
    *, repository: Path, ledger_directory: str, paths: CodeTreePaths, revision: str = 'HEAD'
) -> dict[str, LandedCommit]:
    """Return each code tree that landed, with the first commit it landed in.

    A row lands with the commit that adds its file (on main: the squash merge); the code it
    measured landed only if that commit's code tree is the row's. So every commit in
    ``revision``'s history that added a row file is looked up, oldest first, and its code tree
    kept with the earliest such commit. A row of an intermediate commit or of a branch that was
    behind main names another tree: it matches none.

    Args:
        repository: The repository's working directory.
        ledger_directory: Where the row files are, relative to the repository
            (``[tool.glitchygames]`` ``ledger-directory``).
        paths: What a code tree holds.
        revision: Whose history (``HEAD``: the checkout's).

    Returns:
        Code tree -> the commit it landed in.

    """
    output = run_git(
        repository=repository,
        arguments=['log', '--format=%H %cI', '--diff-filter=A', revision, '--', ledger_directory],
    )
    landed: dict[str, LandedCommit] = {}
    for line in reversed(output.splitlines()):
        commit, committed_at = line.split(' ', maxsplit=1)
        tree = commit_code_tree(repository=repository, commit=commit, paths=paths)
        landed.setdefault(tree, LandedCommit(commit=commit, committed_at=committed_at))
    return landed


def _git_succeeds(*, repository: Path, arguments: list[str]) -> bool:
    """Return whether a git command exits 0 (any failure, an unknown commit included, is False).

    Returns:
        True when git exited 0.

    """
    completed = run_command(
        command=['git', *arguments],
        environment=dict(os.environ),
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=repository,
    )
    return completed.returncode == 0


def landed_ref_exists(*, repository: Path, landed_ref: str) -> bool:
    """Return whether the repository has the landed ref (a fresh clone may lack ``origin/main``).

    Args:
        repository: The repository's working directory.
        landed_ref: The ref whose commits count as landed (``[tool.glitchygames]`` ``landed-ref``).

    Returns:
        True when the ref resolves to a commit.

    """
    return _git_succeeds(
        repository=repository,
        arguments=['rev-parse', '--verify', '--quiet', f'{landed_ref}^{{commit}}'],
    )


def commit_has_landed(*, repository: Path, commit: str, landed_ref: str) -> bool:
    """Return whether a commit is the landed ref or one of its ancestors.

    ``git merge-base --is-ancestor`` exits 1 for "not an ancestor" and 128 for a commit or ref
    this repository does not have; neither has landed here, so both answer False.

    Args:
        repository: The repository's working directory.
        commit: The full commit hash.
        landed_ref: The ref whose commits count as landed (``[tool.glitchygames]`` ``landed-ref``).

    Returns:
        True when the commit is on the landed ref.

    """
    return _git_succeeds(
        repository=repository, arguments=['merge-base', '--is-ancestor', commit, landed_ref]
    )
