"""The suite never inherits a git hook's repository (tests/git_environment.py)."""

from __future__ import annotations

import os

from glitchygames.process import OutputCapture, run_command
from tests.git_environment import GIT_REPOSITORY_VARIABLES, clear_git_repository_variables


def test_no_repository_variable_reaches_a_test():
    """Whatever started the run (a pre-push hook exports GIT_DIR), tests see none of them."""
    assert [name for name in GIT_REPOSITORY_VARIABLES if name in os.environ] == []


def test_clearing_removes_only_the_set_ones(monkeypatch):
    """Only the variables that were set are named and removed."""
    monkeypatch.setenv('GIT_DIR', '/somewhere/.git')
    monkeypatch.setenv('GIT_WORK_TREE', '/somewhere')
    monkeypatch.delenv('GIT_INDEX_FILE', raising=False)

    cleared = clear_git_repository_variables()

    assert cleared == ('GIT_DIR', 'GIT_WORK_TREE')
    assert 'GIT_DIR' not in os.environ


def test_git_outside_a_repository_fails_in_a_temporary_directory(tmp_path):
    """What three tests rely on: with nothing pointing git elsewhere, it finds no repository."""
    result = run_command(
        command=['git', 'rev-parse', '--git-dir'],
        environment=os.environ,
        timeout_seconds=60.0,
        capture_output=OutputCapture.TOGETHER,
        working_directory=tmp_path,
    )

    assert result.returncode != 0
