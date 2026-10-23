"""glitchygames/process.py: ``start_command`` starts a child, ``stop_command`` ends it.

The children are real Python processes. A child that starts a grandchild shows that stopping
ends the whole group (a pytest run's xdist workers with it).
"""

from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING

import pytest

from glitchygames import process
from glitchygames.process import start_command, stop_command

if TYPE_CHECKING:
    from pathlib import Path

# How long a test waits for a child to write its line, or for a stopped process to be gone
WAIT_SECONDS = 10.0
POLL_SECONDS = 0.05
# A child that starts a grandchild, prints the grandchild's pid, then waits to be stopped
CHILD_WITH_GRANDCHILD = (
    'import subprocess, sys, time\n'
    "grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    'print(grandchild.pid, flush=True)\n'
    'time.sleep(60)\n'
)
# A child that ignores SIGTERM (so only the kill ends it), then says it is ready
CHILD_IGNORING_TERMINATE = (
    'import signal, time\n'
    'signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
    "print('ready', flush=True)\n"
    'time.sleep(60)\n'
)


def first_line(*, path: Path) -> str:
    """Wait for a child's output file to hold a whole first line; return it.

    Returns:
        The line, without its newline.

    Raises:
        AssertionError: If no whole line arrives within WAIT_SECONDS.

    """
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        text = path.read_text(encoding='utf-8')
        if '\n' in text:
            return text.split('\n', 1)[0]
        time.sleep(POLL_SECONDS)
    message = f'{path}: no line within {WAIT_SECONDS} s'
    raise AssertionError(message)


def is_running(*, pid: int) -> bool:
    """Tell whether a process (not a zombie this process could reap) still exists.

    Returns:
        True while signal 0 reaches it.

    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


class TestStartCommand:
    """start_command returns at once; the child writes to the given file."""

    def test_the_child_runs_and_writes_its_output(self, tmp_path):
        """Standard output and error both go to the file; wait() gives the exit code."""
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=[
                    sys.executable,
                    '-c',
                    "import sys; print('out'); print('err', file=sys.stderr); sys.exit(3)",
                ],
                environment=os.environ,
                output=output,
            )
            assert child.wait(timeout=WAIT_SECONDS) == 3

        assert sorted(output_path.read_text(encoding='utf-8').split()) == ['err', 'out']

    def test_the_child_gets_the_given_environment(self, tmp_path):
        """The environment is the child's whole environment."""
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=[sys.executable, '-c', "import os; print(os.environ['PROCESS_TEST'])"],
                environment={**os.environ, 'PROCESS_TEST': 'given'},
                output=output,
            )
            child.wait(timeout=WAIT_SECONDS)

        assert output_path.read_text(encoding='utf-8').strip() == 'given'


@pytest.mark.skipif(sys.platform == 'win32', reason='process groups are POSIX')
class TestStopCommand:
    """stop_command ends the child's whole group and reaps the child."""

    def test_the_child_and_its_grandchild_are_stopped(self, tmp_path):
        """SIGTERM to the group ends both."""
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=[sys.executable, '-c', CHILD_WITH_GRANDCHILD],
                environment=os.environ,
                output=output,
            )
            grandchild_pid = int(first_line(path=output_path))

            stop_command(process=child)

        assert child.returncode is not None
        deadline = time.monotonic() + WAIT_SECONDS
        while is_running(pid=grandchild_pid) and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        assert not is_running(pid=grandchild_pid)

    def test_a_child_ignoring_sigterm_is_killed(self, tmp_path, mocker):
        """After the grace period the group is killed."""
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.2)
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=[sys.executable, '-c', CHILD_IGNORING_TERMINATE],
                environment=os.environ,
                output=output,
            )
            assert first_line(path=output_path) == 'ready'

            stop_command(process=child)

        assert child.returncode == -9

    def test_a_finished_child_is_only_reaped(self, tmp_path):
        """Nothing is signalled once the child has ended."""
        with (tmp_path / 'output.txt').open('w', encoding='utf-8') as output:
            child = start_command(
                command=[sys.executable, '-c', 'pass'], environment=os.environ, output=output
            )
            child.wait(timeout=WAIT_SECONDS)

            stop_command(process=child)

        assert child.returncode == 0
