"""scripts/reproduce_orphaned_test_processes.py: stop a pytest run mid-test, list what it left.

Driven with a stand-in test (a test that starts a child in a session of its own and waits), so
it needs no game: stopped with SIGTERM to its group, the run leaves the child running (BUGS.md
#275); stopped with SIGINT, the test's cleanup ends it.
"""

from __future__ import annotations

import os
import signal
import sys
import textwrap
import time
from typing import TYPE_CHECKING

import pytest
from scripts import reproduce_orphaned_test_processes as reproducer
from scripts.reproduce_orphaned_test_processes import main, run_trial, swept_by_the_run

from glitchygames.exit_codes import ExitCode

if TYPE_CHECKING:
    from pathlib import Path

# How long a killed process may take to be reaped by launchd (or init)
GONE_WITHIN_SECONDS = 10.0
# A stand-in test: a child in a session of its own (naming the test's tmp_path, as a test's
# children do), its pid written to child.pid, then a wait; its cleanup ends the child
STAND_IN_TEST = textwrap.dedent(
    """
    import subprocess
    import sys
    import time


    def test_starts_a_session_child_and_waits(tmp_path):
        child = subprocess.Popen(
            [sys.executable, '-c', 'import time; time.sleep(120)', str(tmp_path / 'tool')],
            start_new_session=True,
        )
        try:
            (tmp_path / 'child.pid').write_text(str(child.pid), encoding='utf-8')
            time.sleep(120)
        finally:
            child.kill()
            child.wait()
    """
)


@pytest.fixture
def stand_in_test(tmp_path) -> str:
    """Write the stand-in test.

    Returns:
        Its path, as the script's ``--test``.

    """
    path = tmp_path / 'test_stand_in.py'
    path.write_text(STAND_IN_TEST, encoding='utf-8')
    return str(path)


@pytest.mark.skipif(sys.platform == 'win32', reason='process groups and SIGINT are POSIX')
class TestTrials:
    """A trial against the stand-in test, stopped two ways."""

    def test_sigterm_to_the_runs_group_leaves_the_tests_child_running(self, stand_in_test):
        """The bug, reproduced: no worker unwinds, so the test's cleanup never runs."""
        result = run_trial(mode='stop-command', when='game', test=stand_in_test)

        assert result is not None
        assert len(result.left_running) == 1
        assert 'time.sleep(120)' in result.left_running[0]

    def test_sigint_to_the_runs_group_leaves_nothing(self, stand_in_test):
        """The fix: every worker unwinds as on Ctrl-C, and the test's cleanup ends its child."""
        result = run_trial(mode='sigint-group', when='game', test=stand_in_test)

        assert result is not None
        assert result.left_running == []

    def test_the_command_reports_each_trial_and_exits_on_what_it_found(self, stand_in_test, capsys):
        status = main(['stop-command', 'game', '--test', stand_in_test])

        assert status == ExitCode.REPLAY_DIVERGED
        printed = capsys.readouterr().out
        assert printed.startswith('trial 1: 1 left running, 0 swept by the run itself\n')
        assert '  left running: ' in printed


def test_the_runs_own_sweep_is_read_from_its_terminal_summary():
    """What the stopped run's controller swept (tests/harness.py's section) is listed apart."""
    log_text = (
        '1 passed\n'
        '==== processes left running by this run (now killed) ====\n'
        'pid 12: python tool.py\n'
        'pid 13: python game.py\n'
        '==== short test summary info ====\n'
    )

    assert swept_by_the_run(log_text=log_text) == [
        'pid 12: python tool.py',
        'pid 13: python game.py',
    ]
    assert swept_by_the_run(log_text='1 passed\n') == []


def test_a_run_that_never_reaches_the_moment_is_reported(tmp_path: Path, capsys):
    """A test that ends before it starts a child: INTERNAL_ERROR, said in one line."""
    path = tmp_path / 'test_quick.py'
    path.write_text('def test_quick():\n    pass\n', encoding='utf-8')

    status = main(['sigint-group', 'game', '--test', str(path)])

    assert status == ExitCode.INTERNAL_ERROR
    assert capsys.readouterr().out == "trial 1: the run never reached 'game'\n"


@pytest.mark.skipif(sys.platform == 'win32', reason='process groups and SIGINT are POSIX')
def test_a_run_that_never_reaches_the_moment_leaves_nothing_running(tmp_path, mocker):
    """Giving up still sweeps: the script must not leave the orphans it measures (final review).

    The stand-in starts its child, never writes ``child.pid`` (the ``game`` moment), and waits;
    the script gives up after its (shortened) wait, stops the run and sweeps before the run's
    temporary directory is removed.
    """
    mocker.patch.object(reproducer, 'MOMENT_TIMEOUT_SECONDS', 5.0)
    child_pid_path = tmp_path / 'stand-in-child.pid'
    test_path = tmp_path / 'test_never_ready.py'
    test_path.write_text(
        textwrap.dedent(
            f"""
            import subprocess
            import sys
            import time
            from pathlib import Path


            def test_starts_a_child_and_never_gets_ready(tmp_path):
                child = subprocess.Popen(
                    [sys.executable, '-c', 'import time; time.sleep(120)', str(tmp_path / 'tool')],
                    start_new_session=True,
                )
                Path({str(child_pid_path)!r}).write_text(str(child.pid), encoding='utf-8')
                time.sleep(120)
            """
        ),
        encoding='utf-8',
    )

    status = main(['stop-command', 'game', '--test', str(test_path)])

    assert status == ExitCode.INTERNAL_ERROR
    child_pid = int(child_pid_path.read_text(encoding='utf-8'))
    # A killed process lingers as a zombie until launchd (or init) reaps it: wait for it to go
    deadline = time.monotonic() + GONE_WITHIN_SECONDS
    while time.monotonic() < deadline:
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.05)
    os.kill(child_pid, signal.SIGKILL)
    pytest.fail("the script left the stand-in test's child running")
