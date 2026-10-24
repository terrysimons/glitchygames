"""Tests for scripts/complexity_report.py (nox -s code-complexity).

The report runs on a throwaway repository (the graph script's fixture: two commits, then an
uncommitted edit) with the real git and wily: the working tree must come out exactly as it went
in, the edit must show in the report, and the temporary worktree must be gone.
"""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import pytest
from scripts import complexity_report
from scripts.complexity_report import complexity_report as make_complexity_report
from scripts.complexity_report import main
from scripts.generate_complexity_graphs import ComplexityGraphError

from glitchygames.exit_codes import ExitCode
from tests.test_generate_complexity_graphs import BRANCHY_MODULE, fixture_repository, git

if TYPE_CHECKING:
    from pathlib import Path

# The fixture's simple.py, made branchier and left uncommitted
EDITED_SIMPLE_MODULE = BRANCHY_MODULE.replace('def branchy', 'def simple')

__all__ = ['fixture_repository']


def posix_paths(report: str) -> str:
    """Return wily's report with Windows path separators written as /, as on the other hosts.

    Returns:
        The report.

    """
    return report.replace('\\', '/')


def working_tree_state(*, repository: Path) -> tuple[str, str, str]:
    """Return what the report must not change: the status, the edited file and the worktrees.

    Returns:
        ``git status --porcelain``, simple.py's text and ``git worktree list``.

    """
    return (
        git(repository=repository, arguments=['status', '--porcelain']),
        (repository / 'glitchygames' / 'simple.py').read_text(encoding='utf-8'),
        git(repository=repository, arguments=['worktree', 'list']),
    )


def test_the_report_compares_the_working_tree_without_changing_it(fixture_repository):
    (fixture_repository / 'glitchygames' / 'simple.py').write_text(
        EDITED_SIMPLE_MODULE, encoding='utf-8'
    )
    before = working_tree_state(repository=fixture_repository)

    report = posix_paths(make_complexity_report(project_root=fixture_repository, rank=False))

    assert 'glitchygames/simple.py' in report
    # Compared with HEAD, where branchy.py already is what it is now: unchanged, not reported
    assert 'branchy' not in report
    assert working_tree_state(repository=fixture_repository) == before


def test_the_report_can_rank_the_modules(fixture_repository):
    report = posix_paths(make_complexity_report(project_root=fixture_repository, rank=True))

    # Ranked at HEAD, where branchy.py's complexity is 3 (1 at the first commit)
    # (the table's border is | on Windows and a box-drawing line elsewhere)
    assert re.search(r'glitchygames/branchy\.py\s*[|\u2502]\s*3\b', report)


def test_main_prints_the_report(fixture_repository, mocker):
    mocker.patch.object(complexity_report, 'PROJECT_ROOT', fixture_repository)
    output = mocker.patch.object(complexity_report.sys, 'stdout', new=io.StringIO())

    main(['--rank'])

    assert 'glitchygames/branchy.py' in posix_paths(output.getvalue())


def test_main_exits_internal_error_when_a_tool_fails(fixture_repository, mocker):
    mocker.patch.object(complexity_report, 'PROJECT_ROOT', fixture_repository)
    mocker.patch.object(
        complexity_report,
        'complexity_report',
        side_effect=ComplexityGraphError('wily failed: no such revision'),
    )
    errors = mocker.patch.object(complexity_report.sys, 'stderr', new=io.StringIO())

    with pytest.raises(SystemExit) as exit_info:
        main([])

    assert exit_info.value.code == ExitCode.INTERNAL_ERROR
    assert 'wily failed: no such revision' in errors.getvalue()
