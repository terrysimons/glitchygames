#!/usr/bin/env python3
"""The pre-commit hook that measures the golden replays on the code a commit holds.

Run by the pre-commit framework before each commit (``.pre-commit-config.yaml``, hook
``replay-metrics``), which stashes unstaged changes first, so the working tree is exactly what
is being committed. When the staged paths can change how the replays run (``touches_replays``),
it measures every golden replay and bundled demo on that code (``replay_metrics.py measure``,
named by its code tree: scripts/code_tree.py) and stages one row file per new row under
``quality/replay-ledger/``, so the commit carries its own measurements. The docs build publishes
the rows whose code landed on main (plans/2026-10-25-measured-rows-in-the-repository.md).

A commit that cannot change the replays (docs, plans, tests, tooling) is not measured. A failed
measurement refuses the commit, naming the recording; ``SKIP=replay-metrics git commit ...``
commits without measuring.

Usage (the framework runs it):
    uv run python scripts/measure_staged_replays.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.exit_codes import ExitCode
from scripts import replay_metrics
from scripts.code_tree import LEDGER_DIRECTORY, run_git, staged_code_tree

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROWS_DIRECTORY = PROJECT_ROOT / LEDGER_DIRECTORY
# Staged paths under these can change how the replays run: the engine, the games, demos and
# apps, and the recordings themselves
REPLAY_PATH_PREFIXES = ('glitchygames/', 'games/', 'demos/', 'apps/', 'tests/fixtures/replays/')
# Files that can too: the locked dependencies and the project's own configuration
REPLAY_FILES = frozenset({'uv.lock', 'pyproject.toml'})


def touches_replays(*, staged_paths: Sequence[str]) -> bool:
    """Return whether any staged path can change how the golden replays run.

    Args:
        staged_paths: The staged paths, repository-relative.

    Returns:
        True to measure.

    """
    return any(
        path in REPLAY_FILES or path.startswith(REPLAY_PATH_PREFIXES) for path in staged_paths
    )


def staged_paths(*, repository: Path) -> list[str]:
    """Return the paths the commit being made changes (added, changed, removed).

    Returns:
        The paths, repository-relative.

    """
    output = run_git(repository=repository, arguments=['diff', '--cached', '--name-only'])
    return [line for line in output.splitlines() if line]


def _row_files() -> set[Path]:
    return set(ROWS_DIRECTORY.glob('*.json')) if ROWS_DIRECTORY.is_dir() else set()


def main() -> int:
    """Measure the staged code if it can change the replays, and stage the new row files.

    Returns:
        The exit code: ``SUCCESS``, or the measurement's own failure code.

    """
    paths = staged_paths(repository=PROJECT_ROOT)
    if not touches_replays(staged_paths=paths):
        sys.stdout.write('replay-metrics: nothing staged can change the replays\n')
        return ExitCode.SUCCESS
    code_tree = staged_code_tree(repository=PROJECT_ROOT)
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
