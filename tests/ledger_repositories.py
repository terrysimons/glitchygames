"""Throwaway git repositories for the ledger tests: one whose origin publishes a ledger.

Moved out of tests/test_replay_metrics.py (Part 3, Stage D, Task D6) when its tests moved to
tests/replay/tools/test_measure.py, so the other tests that read a published ledger
(tests/test_generate_performance_graphs.py, tests/replay/tools/test_performance_pages.py,
tests/test_import_published_ledger.py) need not import an engine test. Nothing here touches
this repository's remotes or the network.
"""

from __future__ import annotations

import os
from pathlib import Path

from glitchygames.process import OutputCapture, run_command
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GIT_TIMEOUT_SECONDS = 60.0
# Where this repository publishes its ledger on its ref ([tool.glitchygames] published-ledger):
# what reads it (scripts/generate_performance_graphs.py, import_published_ledger.py)
# read it there
_OUR_PUBLISHED_LEDGER_PATH = load_project_settings(project_root=PROJECT_ROOT).published_ledger_path
assert _OUR_PUBLISHED_LEDGER_PATH is not None, 'this repository publishes its ledger'
OUR_PUBLISHED_LEDGER_PATH: str = _OUR_PUBLISHED_LEDGER_PATH


def git(*, repository: Path, arguments: list[str]) -> str:
    """Run git in a throwaway repository (fixed author, no signing).

    Returns:
        git's standard output.

    """
    completed = run_command(
        command=[
            'git',
            '-c',
            'user.name=Metrics Test',
            '-c',
            'user.email=metrics@example.com',
            '-c',
            'commit.gpgsign=false',
            *arguments,
        ],
        environment=os.environ,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
        capture_output=OutputCapture.TOGETHER,
        working_directory=repository,
    )
    assert completed.returncode == 0, completed.stdout
    return completed.stdout or ''


def clone_with_published_ledger(
    *, tmp_path: Path, ledger: str, published_path: str = OUR_PUBLISHED_LEDGER_PATH
) -> Path:
    """Make an origin whose gh-pages branch publishes ``ledger``, and clone it.

    Args:
        tmp_path: Where the origin and the clone go.
        ledger: The published ledger's text.
        published_path: Its path on gh-pages (this repository's unless given).

    Returns:
        The clone (its ``origin/gh-pages`` holds the ledger).

    """
    origin = tmp_path / 'origin'
    origin.mkdir()
    git(repository=origin, arguments=['init', '--quiet', '--initial-branch', 'main'])
    (origin / 'README').write_text('main\n', encoding='utf-8')
    git(repository=origin, arguments=['add', 'README'])
    git(repository=origin, arguments=['commit', '--quiet', '-m', 'main'])
    git(repository=origin, arguments=['checkout', '--quiet', '--orphan', 'gh-pages'])
    git(repository=origin, arguments=['rm', '--quiet', '-r', '-f', '.'])
    published = origin / published_path
    published.parent.mkdir(parents=True)
    published.write_text(ledger, encoding='utf-8')
    git(repository=origin, arguments=['add', published_path])
    git(repository=origin, arguments=['commit', '--quiet', '-m', 'site'])
    git(repository=origin, arguments=['checkout', '--quiet', 'main'])
    clone = tmp_path / 'clone'
    git(repository=tmp_path, arguments=['clone', '--quiet', str(origin), str(clone)])
    return clone
