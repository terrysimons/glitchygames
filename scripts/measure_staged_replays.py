#!/usr/bin/env python3
"""The pre-commit hook that measures the golden replays on the code a commit holds.

Run by the pre-commit framework before each commit (``.pre-commit-config.yaml``, hook
``replay-metrics``), which stashes unstaged changes first, so the working tree is exactly what
is being committed. When the staged code tree differs from HEAD's (scripts/code_tree.py: only
the paths that can change how the replays run), it measures every golden replay and bundled
demo on that code (``replay_metrics.py measure``, named by its code tree) and stages one row
file per new row under ``quality/replay-ledger/``, so the commit carries its own measurements.
The docs build publishes the rows whose code landed on main
(plans/2026-10-25-measured-rows-in-the-repository.md).

A commit that cannot change the replays (docs, plans, tests, tooling: its code tree is HEAD's)
is not measured. A failed
measurement refuses the commit, naming the recording; ``SKIP=replay-metrics git commit ...``
commits without measuring.

Usage (the framework runs it):
    uv run python scripts/measure_staged_replays.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from glitchygames.exit_codes import ExitCode
from scripts import replay_metrics
from scripts.code_tree import LEDGER_DIRECTORY, commit_code_tree, run_git, staged_code_tree

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROWS_DIRECTORY = PROJECT_ROOT / LEDGER_DIRECTORY


def code_changes(*, repository: Path) -> str | None:
    """Return the staged code tree when it differs from HEAD's (the commit can change the replays).

    Returns:
        The staged code tree (scripts/code_tree.py), or None when it is HEAD's: the commit
        changes only what cannot change the replays (docs, plans, tests, tooling).

    """
    staged = staged_code_tree(repository=repository)
    try:
        head = commit_code_tree(repository=repository, commit='HEAD')
    except RuntimeError:
        # No HEAD yet (a new repository): everything staged is new code
        return staged
    return None if staged == head else staged


def _row_files() -> set[Path]:
    return set(ROWS_DIRECTORY.glob('*.json')) if ROWS_DIRECTORY.is_dir() else set()


def main() -> int:
    """Measure the staged code if it can change the replays, and stage the new row files.

    Returns:
        The exit code: ``SUCCESS``, or the measurement's own failure code.

    """
    code_tree = code_changes(repository=PROJECT_ROOT)
    if code_tree is None:
        sys.stdout.write('replay-metrics: nothing staged can change the replays\n')
        return ExitCode.SUCCESS
    before = _row_files()
    exit_code = replay_metrics.run(
        arguments=[
            'measure',
            '--allow-dirty',
            '--code-tree',
            code_tree,
            '--rows-directory',
            str(ROWS_DIRECTORY),
        ]
    )
    if exit_code != ExitCode.SUCCESS:
        sys.stderr.write(
            'replay-metrics: measuring the staged code failed (above); fix it, or commit '
            'without measuring: SKIP=replay-metrics git commit ...\n'
        )
        return exit_code
    for path in sorted(_row_files() - before):
        run_git(repository=PROJECT_ROOT, arguments=['add', '--', str(path)])
    return ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
