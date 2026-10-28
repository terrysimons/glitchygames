"""glitchygames/process.py: ``run_command`` runs a child; ``start_command`` and ``stop_command``.

The children are real Python processes. A child that starts a grandchild shows that stopping
ends the whole group (a pytest run's xdist workers with it).
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from glitchygames import process
from glitchygames.process import OutputCapture, start_command, stop_command

# SIGKILL's number on POSIX (Windows' signal module has no SIGKILL)
SIGKILL_NUMBER = 9

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


class TestRunCommand:
    """``run_command`` runs a child, by default in this process's working directory."""

    def test_the_child_runs_in_the_given_working_directory(self, tmp_path):
        completed = process.run_command(
            command=[sys.executable, '-c', 'import os; print(os.getcwd())'],
            environment=os.environ,
            timeout_seconds=WAIT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
            working_directory=tmp_path,
        )

        assert completed.returncode == 0
        assert completed.stdout.strip() == str(tmp_path.resolve())

    def test_without_a_working_directory_the_child_inherits_this_one(self):
        completed = process.run_command(
            command=[sys.executable, '-c', 'import os; print(os.getcwd())'],
            environment=os.environ,
            timeout_seconds=WAIT_SECONDS,
            capture_output=OutputCapture.TOGETHER,
        )

        assert completed.stdout.strip() == str(Path.cwd().resolve())

    @pytest.mark.parametrize(
        ('capture', 'captured_output', 'captured_error'),
        [
            (OutputCapture.NONE, None, None),
            (OutputCapture.TOGETHER, 'out\nerr\n', None),
            (OutputCapture.APART, 'out\n', 'err\n'),
        ],
    )
    def test_each_capture_keeps_what_it_says(self, capture, captured_output, captured_error):
        """None: neither stream; together: both in stdout; apart: each in its own."""
        completed = process.run_command(
            command=[
                sys.executable,
                '-c',
                'import sys; print("out", flush=True); print("err", file=sys.stderr, flush=True)',
            ],
            environment=os.environ,
            timeout_seconds=WAIT_SECONDS,
            capture_output=capture,
        )

        assert completed.stdout == captured_output
        assert completed.stderr == captured_error
        assert list(OutputCapture) == [
            OutputCapture.NONE,
            OutputCapture.TOGETHER,
            OutputCapture.APART,
        ]


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


class TestStopCommandOnEveryPlatform:
    """stop_command's steps with a stand-in child, for both platforms' branches on every host.

    The platform and the signals are faked (Windows has no SIGKILL or killpg), so each CI host
    runs the other's branch too and nothing real is signalled.
    """

    @pytest.fixture(params=['linux', 'win32'])
    def platform(self, request, mocker):
        mocker.patch.object(process.sys, 'platform', request.param)
        mocker.patch.object(
            process, 'signal', SimpleNamespace(SIGTERM=signal.SIGTERM, SIGKILL=SIGKILL_NUMBER)
        )
        return request.param

    def test_an_ended_child_is_left_alone(self, mocker, platform):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = 0
        group_signal = mocker.patch.object(process.os, 'killpg', create=True)

        stop_command(process=child)

        child.wait.assert_not_called()
        group_signal.assert_not_called()

    def test_a_child_that_outlives_the_grace_period_is_killed_and_reaped(self, mocker, platform):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = [process.TimeoutExpired(cmd='game', timeout=1.0), 0]
        group_signal = mocker.patch.object(process.os, 'killpg', create=True)

        stop_command(process=child)

        # Asked to end, waited for, then killed and reaped: by its group on POSIX, itself on
        # Windows
        assert child.wait.call_count == 2
        if platform == 'win32':
            child.terminate.assert_called_once_with()
            child.kill.assert_called_once_with()
            group_signal.assert_not_called()
        else:
            assert [call.args for call in group_signal.call_args_list] == [
                (4242, signal.SIGTERM),
                (4242, SIGKILL_NUMBER),
            ]


class TestStopCommandRacingTheChildsEnd:
    """A child that ends between stop_command's poll() and its signal is only reaped (POSIX).

    macOS answers a signal to a group whose leader is exiting (or an unreaped zombie) with
    EPERM, even before poll() sees the exit, and a group already gone answers ESRCH: neither is
    a failure to stop the child, which is then waited for.
    """

    @pytest.fixture(autouse=True)
    def posix(self, mocker):
        mocker.patch.object(process.sys, 'platform', 'linux')
        mocker.patch.object(
            process, 'signal', SimpleNamespace(SIGTERM=signal.SIGTERM, SIGKILL=SIGKILL_NUMBER)
        )

    @pytest.mark.parametrize('error', [PermissionError, ProcessLookupError])
    def test_a_child_ending_as_the_sigterm_is_sent_is_only_reaped(self, mocker, error):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        group_signal = mocker.patch.object(process.os, 'killpg', create=True, side_effect=error)

        stop_command(process=child)

        # Signalled once (no SIGKILL), then waited for
        assert group_signal.call_count == 1
        child.wait.assert_called_once_with(timeout=process.STOP_GRACE_SECONDS)

    @pytest.mark.parametrize('error', [PermissionError, ProcessLookupError])
    def test_a_child_ending_as_the_sigkill_is_sent_is_only_reaped(self, mocker, error):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = [process.TimeoutExpired(cmd='game', timeout=1.0), 0]
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=[None, error])

        stop_command(process=child)

        assert child.wait.call_count == 2

    def test_a_signal_refused_while_the_child_keeps_running_is_raised(self, mocker):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = process.TimeoutExpired(cmd='game', timeout=1.0)
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=PermissionError)

        with pytest.raises(PermissionError):
            stop_command(process=child)


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


# A child that writes its process id to the file it is given, then never ends on its own
CHILD_THAT_NEVER_ENDS = (
    'import os, pathlib, sys, time\n'
    "pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()}\\n', encoding='utf-8')\n"
    'time.sleep(60)\n'
)
# The same, ignoring SIGTERM (so only the kill ends it)
CHILD_THAT_NEVER_ENDS_IGNORING_TERMINATE = (
    'import signal\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n' + CHILD_THAT_NEVER_ENDS
)
# How long the children above get before their timeout
SHORT_TIMEOUT_SECONDS = 1.0


@pytest.mark.skipif(sys.platform == 'win32', reason='signal 0 to a process id is POSIX')
class TestRunCommandStoppedAtTimeout:
    """``run_command_stopped_at_timeout`` stops a child that outlives its timeout, then reaps it.

    Asked to stop first (SIGTERM: a game's engine then ends its own children), killed only if
    it is still running after STOP_GRACE_SECONDS; either way reaped (no zombie is left), and the
    timeout raised.
    """

    def test_a_child_that_ends_in_time_gives_its_status(self, tmp_path):
        """Within its timeout: the child's exit status, in its working directory."""
        finished = process.run_command_stopped_at_timeout(
            command=[sys.executable, '-c', 'import sys; sys.exit(3)'],
            environment=os.environ,
            timeout_seconds=WAIT_SECONDS,
            working_directory=tmp_path,
        )

        assert finished.returncode == 3

    @pytest.mark.parametrize(
        'source',
        [CHILD_THAT_NEVER_ENDS, CHILD_THAT_NEVER_ENDS_IGNORING_TERMINATE],
        ids=['stopped by sigterm', 'killed after the grace period'],
    )
    def test_a_child_still_running_at_its_timeout_is_stopped_and_reaped(
        self, tmp_path, mocker, source
    ):
        """Its timeout raises TimeoutExpired, after the child is gone (not even a zombie)."""
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', SHORT_TIMEOUT_SECONDS)
        pid_file = tmp_path / 'child.pid'

        with pytest.raises(process.TimeoutExpired):
            process.run_command_stopped_at_timeout(
                command=[sys.executable, '-c', source, str(pid_file)],
                environment=os.environ,
                timeout_seconds=SHORT_TIMEOUT_SECONDS * 3,
            )

        child_pid = int(first_line(path=pid_file))
        assert not is_running(pid=child_pid)
