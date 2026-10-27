#!/usr/bin/env python3
"""The pre-commit hook that measures the golden replays on the code a commit holds.

Run by the pre-commit framework before each commit (``.pre-commit-config.yaml``, hook
``replay-metrics``), which stashes unstaged changes to tracked files first, so the tracked files
are exactly what is being committed. When this machine has no rows yet for the staged code tree
(glitchygames/code_tree.py: only the paths that can change how the replays run), it measures
every golden replay and bundled demo on that code (``glitchygames measure``, named by its code
tree) and stages the row files under ``quality/replay-ledger/``, so the commit carries its own
measurements. The docs build publishes the rows whose code landed on main
(plans/2026-10-25-measured-rows-in-the-repository.md). This script keeps only git staging and
its refusals; what is unmeasured and the measuring itself are the engine's
(``glitchygames unmeasured`` and ``glitchygames measure``, glitchygames/replay/tools/measure.py),
run in this process through the command's ``main``.

The rules (a code review's findings, 2026-10-25):

1. Measured once per code tree per machine (every golden replay and bundled demo has its row for
   the tree here: ``glitchygames unmeasured`` lists none; a retry measures only the recordings
   still lacking one): a docs commit after a measured one is instant, while
   code that arrived without the hook (a branch updated from main: no merge, rebase or GitHub
   "Update branch" runs the pre-commit stage) is measured by the next commit, whatever it
   changes. After updating a branch, run this script by hand and commit what it stages.
2. Every row file of the staged code tree is staged, not only new ones: rows written before a
   measurement failed (the commit was refused) are staged on the retry. So is every row file the
   measurement wrote (found by comparing the rows directory before and after), the history
   rows among them: a recording's earlier runs that landed on origin/main, written as
   ``history-...`` files (``measure.rows_to_write``: never a run of code that did not
   land, never a run a row already holds under the recording's old path). Other untracked
   files in the directory are left alone.
3. Refused when measuring is needed and the result could not be committed as measured:
   untracked files under the measured paths (the framework stashes only tracked changes, so they
   would be measured though not committed), and a partial commit (``git commit <path>``: rows
   staged into its temporary index never reach the real one, and the next commit would delete
   them).
4. A failed measurement refuses the commit, naming the recording. The row files it wrote
   before failing are staged anyway (valid measurements); the retry measures the rest.

The repository's settings (``[tool.glitchygames]``: what a code tree holds) are read from the
repository given, never from a module-level read of this one's (the controller's note to Task D6).

``SKIP=replay-metrics git commit ...`` commits without measuring.

Usage (the framework runs it; by hand after updating a branch, then commit):
    uv run python -m scripts.measure_staged_replays
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

from glitchygames.code_tree import run_git, staged_code_tree, untracked_measured_files
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_metrics import ROW_FILE_SUFFIX, ROW_FILE_TREE_CHARACTERS
from glitchygames.replay.tools import command
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The temporary index git commits through for ``git commit <path>`` (a partial commit)
PARTIAL_COMMIT_INDEX_PREFIX = 'next-index'


def glitchygames(*, arguments: list[str]) -> int:
    """Run a ``glitchygames`` subcommand in this process (glitchygames/replay/tools/command.py).

    Args:
        arguments: The command line after ``glitchygames``.

    Returns:
        Its exit status.

    """
    return command.main(arguments)


def _tree_row_files(*, rows_directory: Path, code_tree: str) -> list[Path]:
    """Return the row files of a code tree (their names lead with it).

    Returns:
        The files, sorted.

    """
    prefix = code_tree[:ROW_FILE_TREE_CHARACTERS]
    if not rows_directory.is_dir():
        return []
    return sorted(rows_directory.glob(f'{prefix}-*{ROW_FILE_SUFFIX}'))


def _row_file_names(*, rows_directory: Path) -> set[str]:
    """Return the names of the row files in the directory (none when it is missing).

    Returns:
        The file names.

    """
    if not rows_directory.is_dir():
        return set()
    return {path.name for path in rows_directory.glob(f'*{ROW_FILE_SUFFIX}')}


def _unmeasured(*, repository: Path, rows_directory: Path, code_tree: str) -> list[str] | None:
    """Return the recordings with no row for the code tree on this machine.

    ``glitchygames unmeasured --code-tree TREE --rows-directory DIR``, its standard output (one
    ledger name per line) read here.

    Returns:
        The recordings (none when every one is measured), or None when the command failed (a
        game that isn't installed, settings that can't be read): measuring then says why.

    """
    listing = io.StringIO()
    with contextlib.redirect_stdout(listing):
        exit_code = glitchygames(
            arguments=[
                'unmeasured',
                '--code-tree',
                code_tree,
                '--rows-directory',
                str(rows_directory),
                '--project-root',
                str(repository),
            ]
        )
    if exit_code != ExitCode.SUCCESS:
        return None
    return [line for line in listing.getvalue().splitlines() if line]


def _is_partial_commit() -> bool:
    """Return whether git is making a partial commit (``git commit <path>``, ``--only``).

    Returns:
        True when the hook runs on git's temporary next-index.

    """
    index_file = os.environ.get('GIT_INDEX_FILE')
    return index_file is not None and Path(index_file).name.startswith(PARTIAL_COMMIT_INDEX_PREFIX)


def _stage(*, repository: Path, paths: list[Path]) -> None:
    """Stage files (a no-op for those already staged unchanged)."""
    if paths:
        run_git(repository=repository, arguments=['add', '--', *(str(path) for path in paths)])


def measure_staged(*, repository: Path, rows_directory: Path) -> int:
    """Measure the staged code tree unless measured on this machine, and stage its rows.

    This machine is the one the engine names (``measure.this_machine``), as ``glitchygames
    unmeasured`` and ``measure`` judge by it.

    Args:
        repository: The repository (its ``[tool.glitchygames]`` says what a code tree holds).
        rows_directory: Where the row files are (quality/replay-ledger/).

    Returns:
        ``SUCCESS``; ``OPTIONS_REFUSED`` for a commit whose measurement could not be committed
        (untracked measured files, a partial commit); or the measurement's failure code.

    """
    paths = load_project_settings(project_root=repository).code_tree_paths
    code_tree = staged_code_tree(repository=repository, paths=paths)
    unmeasured = _unmeasured(
        repository=repository, rows_directory=rows_directory, code_tree=code_tree
    )
    if unmeasured == []:
        # Rows written before a refused commit are staged now (rule 2)
        _stage(
            repository=repository,
            paths=_tree_row_files(rows_directory=rows_directory, code_tree=code_tree),
        )
        sys.stdout.write(f'replay-metrics: code tree {code_tree[:12]} already measured here\n')
        return ExitCode.SUCCESS
    if _is_partial_commit():
        sys.stderr.write(
            'replay-metrics: this commit needs measuring, which a partial commit '
            '(git commit <path>) cannot carry; stage the files and run git commit, or skip it: '
            'SKIP=replay-metrics git commit ...\n'
        )
        return ExitCode.OPTIONS_REFUSED
    # Untracked files under the measured paths, less the unmeasured ones (a member's tests)
    untracked = untracked_measured_files(repository=repository, paths=paths)
    if untracked:
        sys.stderr.write(
            'replay-metrics: untracked files would be measured though not committed; add them '
            'or move them away: ' + ', '.join(untracked) + '\n'
        )
        return ExitCode.OPTIONS_REFUSED
    files_before = _row_file_names(rows_directory=rows_directory)
    exit_code = glitchygames(
        arguments=[
            'measure',
            '--allow-dirty',
            '--code-tree',
            code_tree,
            '--rows-directory',
            str(rows_directory),
            '--project-root',
            str(repository),
        ]
    )
    # The files this measurement wrote are valid measurements even when it failed partway
    # (history rows among them: their names lead with "history", not the tree), plus every row
    # file of the tree already on disk (rule 2): staged now, so a retry commits them
    written = sorted(_row_file_names(rows_directory=rows_directory) - files_before)
    _stage(
        repository=repository,
        paths=[
            *(rows_directory / name for name in written),
            *_tree_row_files(rows_directory=rows_directory, code_tree=code_tree),
        ],
    )
    if exit_code != ExitCode.SUCCESS:
        sys.stderr.write(
            'replay-metrics: measuring the staged code failed (above); fix it and commit again '
            '(the recordings measured so far are staged, the retry measures the rest), or '
            'commit without measuring: SKIP=replay-metrics git commit ...\n'
        )
        return exit_code
    return ExitCode.SUCCESS


def main() -> int:
    """Run the hook on this repository, its rows in its ledger directory.

    Returns:
        ``measure_staged``'s exit code.

    """
    settings = load_project_settings(project_root=PROJECT_ROOT)
    return measure_staged(
        repository=PROJECT_ROOT, rows_directory=PROJECT_ROOT / settings.ledger_directory
    )


if __name__ == '__main__':
    sys.exit(main())
