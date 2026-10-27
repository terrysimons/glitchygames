"""Report how the working tree's changes move code complexity, without touching the working tree.

``nox -s code-complexity`` runs this. ``wily build`` measures a repository's history by checking
each old revision out in the directory it runs in, so running it in the working tree rewrites the
files being worked on while it runs. Here the history is measured in a temporary detached worktree
of HEAD (``detached_checkout``, shared with scripts/generate_complexity_graphs.py) into a
temporary wily cache, and only then is the working tree compared with it: ``wily diff`` reads the
working files and checks nothing out, against HEAD (named: wily 1.25's default is the oldest
revision it indexed, so the old session compared with a commit up to 50 back). ``--rank`` also
ranks the modules by complexity (from the cache). Nothing is written outside the temporary
directory, and the worktree is removed.

Exit codes: ``SUCCESS``; ``INTERNAL_ERROR`` when git or wily fails (its output is printed).

Usage (from the project root):
    uv run python -m scripts.complexity_report [--rank]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, run_command
from scripts.generate_complexity_graphs import (
    TOOL_TIMEOUT_SECONDS,
    WILY_BUILD_TIMEOUT_SECONDS,
    ComplexityGraphError,
    detached_checkout,
    run_tool,
    wily_command,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# What the diff compares (each that exists): the package and the scripts
DIFF_PATHS = ('src/glitchygames', 'scripts')
RANKED_PATH = 'src/glitchygames'
RANK_LIMIT = 20
# wily diff exits 1 when it has changes to report
WILY_DIFF_EXIT_STATUSES = frozenset({0, 1})
# wily sizes its tables to the terminal: wide enough that file names stay on one line
REPORT_COLUMNS = '200'


def complexity_report(*, project_root: Path, rank: bool) -> str:
    """Measure HEAD's history in a temporary worktree, then compare the working tree with it.

    Args:
        project_root: The repository (its wily.cfg says what to measure).
        rank: Also rank the package's modules by cyclomatic complexity.

    Returns:
        wily's diff of the working tree against HEAD (and the ranking).

    Raises:
        ComplexityGraphError: git or wily failed (with its output).

    """
    with tempfile.TemporaryDirectory(prefix='complexity-report-') as temporary_name:
        temporary_directory = Path(temporary_name)
        cache_directory = temporary_directory / 'wily-cache'
        with detached_checkout(
            project_root=project_root, checkout_directory=temporary_directory / 'checkout'
        ) as checkout:
            run_tool(
                command=wily_command(cache_directory=cache_directory, arguments=['build']),
                working_directory=checkout,
                timeout_seconds=WILY_BUILD_TIMEOUT_SECONDS,
            )
        # Against HEAD, named: wily 1.25's default target is the oldest revision it indexed
        head = run_tool(
            command=['git', 'rev-parse', 'HEAD'],
            working_directory=project_root,
            timeout_seconds=TOOL_TIMEOUT_SECONDS,
        ).strip()
        diff_paths = [path for path in DIFF_PATHS if (project_root / path).exists()]
        completed = run_command(
            command=wily_command(
                cache_directory=cache_directory,
                arguments=['diff', *diff_paths, '--changes-only', '--revision', head],
            ),
            environment={**os.environ, 'COLUMNS': REPORT_COLUMNS},
            timeout_seconds=TOOL_TIMEOUT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
            working_directory=project_root,
        )
        if completed.returncode not in WILY_DIFF_EXIT_STATUSES:
            message = (
                f'wily diff failed with exit status {completed.returncode}:\n{completed.stdout}'
            )
            raise ComplexityGraphError(message)
        report = completed.stdout
        if rank:
            report += run_tool(
                command=wily_command(
                    cache_directory=cache_directory,
                    arguments=[
                        'rank',
                        '--limit',
                        str(RANK_LIMIT),
                        '--revision',
                        head,
                        RANKED_PATH,
                        'cyclomatic.complexity',
                    ],
                ),
                working_directory=project_root,
                timeout_seconds=TOOL_TIMEOUT_SECONDS,
            )
        return report


def main(arguments: Sequence[str] | None = None) -> None:
    """Print the complexity report (``--rank`` adds the ranking).

    Args:
        arguments: The command line (None: ``sys.argv[1:]``).

    """
    parser = argparse.ArgumentParser(
        description='Report how the working tree changes code complexity, against HEAD.'
    )
    parser.add_argument('--rank', action='store_true', help='also rank the modules by complexity')
    options = parser.parse_args(arguments)
    try:
        report = complexity_report(project_root=PROJECT_ROOT, rank=options.rank)
    except ComplexityGraphError as error:
        # The failed tool's own output is the useful part; a traceback would bury it
        sys.stderr.write(f'{error}\n')
        sys.exit(ExitCode.INTERNAL_ERROR)
    sys.stdout.write(report)


if __name__ == '__main__':
    main()
