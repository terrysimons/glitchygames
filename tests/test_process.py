"""glitchygames/process.py: ``run_command`` runs a child; ``start_command`` and ``stop_command``.

The children are real Python processes. A child that starts a grandchild shows that stopping
ends the whole group (a pytest run's xdist workers with it).
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - a stand-in child raises its TimeoutExpired; Popen names the type
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from glitchygames import process
from glitchygames.process import ErrorOutput, OutputCapture, start_command, stop_command

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


def child_reporting_its_signal(*, ignored: tuple[str, ...]) -> str:
    """A child that ignores the named signals, prints which other one ended it, and exits 0.

    It prints ``ready`` once its handlers are in place, then ``interrupted`` (SIGINT) or
    ``terminated`` (SIGTERM) as it ends; SIGKILL ends it with no words.

    Returns:
        The child's source.

    """
    return (
        'import signal, sys, time\n'
        'def ended_by(words):\n'
        '    def handler(signal_number, frame):\n'
        '        print(words, flush=True)\n'
        '        sys.exit(0)\n'
        '    return handler\n'
        "signal.signal(signal.SIGINT, ended_by('interrupted'))\n"
        "signal.signal(signal.SIGTERM, ended_by('terminated'))\n"
        f'for name in {list(ignored)!r}:\n'
        '    signal.signal(getattr(signal, name), signal.SIG_IGN)\n'
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

    def test_piped_errors_are_read_apart_from_the_output(self, tmp_path):
        """With ``errors=PIPED`` the file gets standard output only; ``stderr`` is read on its own.

        A child whose standard error is a channel (Chrome prints its DevTools address there) is
        started like any other, so it is stopped and reaped like any other.
        """
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=[
                    sys.executable,
                    '-c',
                    "import sys; print('out'); print('err', file=sys.stderr)",
                ],
                environment=os.environ,
                output=output,
                errors=ErrorOutput.PIPED,
            )
            try:
                assert child.stderr is not None
                errors = child.stderr.read()
            finally:
                stop_command(process=child)

        assert errors == 'err\n'
        assert output_path.read_text(encoding='utf-8') == 'out\n'

    @pytest.mark.parametrize(
        'source', ['import time; time.sleep(60)', 'pass'], ids=['running', 'ended-first']
    )
    def test_stop_command_closes_the_childs_pipes_once_it_is_reaped(self, tmp_path, source):
        """No pipe outlives the stop: the caller cannot leak it, and cannot read past the stop.

        ``stop_command`` reaped a child but left its pipes for the garbage collector (Chrome's
        standard error in measure_browser_frames, 2026-11-22). An ended child is stopped by an
        early return, so it is checked too.
        """
        with (tmp_path / 'output.txt').open('w', encoding='utf-8') as output:
            child = start_command(
                command=[sys.executable, '-c', source],
                environment=os.environ,
                output=output,
                errors=ErrorOutput.PIPED,
            )
            if source == 'pass':
                child.wait(timeout=WAIT_SECONDS)

            stop_command(process=child)

        assert child.returncode is not None
        assert child.stderr is not None
        assert child.stderr.closed

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


class StandInGroup:
    """``os.killpg`` for a stand-in child's process group, answering as a real group does.

    Every signal is recorded in ``calls``. Once the child (the group's leader) has been reaped,
    the group has no members (a stand-in child starts nothing), so every signal then raises
    ``ProcessLookupError``, as killpg does for a group that is gone. Before that each call
    answers with the next of ``answers`` (None: delivered; an exception class: raised), and
    with delivery once they run out. Build it after the child's ``wait`` is configured: it
    wraps that wait to learn when the child is reaped.
    """

    def __init__(self, *, child, answers=()):
        """Wrap the child's wait, and keep the answers for the calls before it is reaped."""
        self.calls: list[tuple[int, int]] = []
        self._answers = list(answers)
        self._reaped = False
        configured = child.wait.side_effect
        returned = child.wait.return_value
        # Mock keeps a list side_effect as an iterator
        outcomes = configured if hasattr(configured, '__next__') else None

        def reaping_wait(*args, **kwargs):
            if outcomes is not None:
                outcome = next(outcomes)
            elif configured is not None:
                outcome = configured
            else:
                outcome = returned
            if isinstance(outcome, BaseException) or (
                isinstance(outcome, type) and issubclass(outcome, BaseException)
            ):
                raise outcome
            self._reaped = True
            return outcome

        child.wait.side_effect = reaping_wait

    def __call__(self, group: int, signal_number: int) -> None:
        self.calls.append((group, signal_number))
        if self._reaped:
            raise ProcessLookupError
        if self._answers:
            answer = self._answers.pop(0)
            if answer is not None:
                raise answer


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

    def test_an_ended_child_is_not_signalled_and_its_empty_group_once(self, mocker, platform):
        """Ended already: never waited for again; on POSIX its group is asked once, and is gone.

        What an ended child left in its group would get the stop's first signal (the
        real-process test covers that); a group already gone answers ESRCH, and that is all.
        """
        child = mocker.Mock(pid=4242)
        child.poll.return_value = 0
        group_signal = mocker.patch.object(
            process.os, 'killpg', create=True, side_effect=ProcessLookupError
        )

        stop_command(process=child)

        child.wait.assert_not_called()
        child.terminate.assert_not_called()
        if platform == 'win32':
            group_signal.assert_not_called()
        else:
            assert [call.args for call in group_signal.call_args_list] == [(4242, signal.SIGTERM)]

    @pytest.mark.parametrize(
        'first_answer',
        [None, PermissionError],
        ids=['a-member-still-runs', 'only-zombies-left'],
    )
    def test_an_ended_childs_group_that_is_still_there_is_emptied(
        self, mocker, platform, first_answer
    ):
        """Ended already, but its group still answers: what it left gets the signal, then looked at.

        Delivered: a member the child forked still runs. PermissionError: macOS answers EPERM for
        a group left with only an unreaped zombie. Either way the group is then looked at (signal
        0) until it is gone. Only the real-process test reached this before, and only when the
        child's end and the stop fell in the right order, so CI's coverage missed it (#263).
        """
        child = mocker.Mock(pid=4242)
        child.poll.return_value = 0
        group = StandInGroup(child=child, answers=[first_answer, ProcessLookupError])
        group_signal = mocker.patch.object(process.os, 'killpg', create=True, side_effect=group)

        stop_command(process=child)

        child.wait.assert_not_called()
        child.terminate.assert_not_called()
        if platform == 'win32':
            group_signal.assert_not_called()
        else:
            assert group.calls == [(4242, signal.SIGTERM), (4242, 0)]

    def test_a_child_that_ends_at_the_first_request_is_only_reaped(self, mocker, platform):
        """Asked once and ended within the grace: waited for once, never asked again or killed.

        On POSIX only the real-process tests (skipped on Windows) took this path, so the Windows
        job left its ``return`` uncovered (#192's build-and-test-windows).
        """
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        group = StandInGroup(child=child)
        group_signal = mocker.patch.object(process.os, 'killpg', create=True, side_effect=group)

        stop_command(process=child)

        child.wait.assert_called_once_with(timeout=process.STOP_GRACE_SECONDS)
        if platform == 'win32':
            child.terminate.assert_called_once_with()
            child.kill.assert_not_called()
            group_signal.assert_not_called()
        else:
            # Asked once, then the group is looked at (signal 0) and found gone
            assert group.calls == [(4242, signal.SIGTERM), (4242, 0)]

    def test_a_child_that_outlives_the_grace_period_is_killed_and_reaped(self, mocker, platform):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = [process.TimeoutExpired(cmd='game', timeout=1.0), 0]
        group = StandInGroup(child=child)
        group_signal = mocker.patch.object(process.os, 'killpg', create=True, side_effect=group)

        stop_command(process=child)

        # Asked to end, waited for, then killed and reaped: by its group on POSIX, itself on
        # Windows
        assert child.wait.call_count == 2
        if platform == 'win32':
            child.terminate.assert_called_once_with()
            child.kill.assert_called_once_with()
            group_signal.assert_not_called()
        else:
            # After the kill, whatever is left in the group is killed at once: nothing is
            assert group.calls == [
                (4242, signal.SIGTERM),
                (4242, SIGKILL_NUMBER),
                (4242, SIGKILL_NUMBER),
            ]

    def test_a_first_signal_that_does_not_end_it_is_followed_by_sigterm_then_the_kill(
        self, mocker, platform
    ):
        """SIGINT first (a pytest run's Ctrl-C), then SIGTERM, then SIGKILL, a grace apart.

        Windows has no group SIGINT here: it terminates, then kills, as before.
        """
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        # Every wait but the last outlives the grace: Windows waits after terminating and after
        # killing, POSIX after each of SIGINT, SIGTERM and SIGKILL
        graces_outlived = 1 if platform == 'win32' else 2
        child.wait.side_effect = [
            *[process.TimeoutExpired(cmd='pytest', timeout=1.0)] * graces_outlived,
            0,
        ]
        group = StandInGroup(child=child)
        group_signal = mocker.patch.object(process.os, 'killpg', create=True, side_effect=group)

        stop_command(process=child, first_signal=signal.SIGINT)

        if platform == 'win32':
            child.terminate.assert_called_once_with()
            child.kill.assert_called_once_with()
            group_signal.assert_not_called()
        else:
            assert group.calls == [
                (4242, signal.SIGINT),
                (4242, signal.SIGTERM),
                (4242, SIGKILL_NUMBER),
                (4242, SIGKILL_NUMBER),
            ]
            assert child.wait.call_count == 3


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
        group = StandInGroup(child=child, answers=[error])
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=group)

        stop_command(process=child)

        # Signalled once (no SIGKILL), waited for, then the group is looked at and found gone
        assert group.calls == [(4242, signal.SIGTERM), (4242, 0)]
        child.wait.assert_called_once_with(timeout=process.STOP_GRACE_SECONDS)

    @pytest.mark.parametrize('error', [PermissionError, ProcessLookupError])
    def test_a_child_ending_as_the_sigkill_is_sent_is_only_reaped(self, mocker, error):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = [process.TimeoutExpired(cmd='game', timeout=1.0), 0]
        group = StandInGroup(child=child, answers=[None, error])
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=group)

        stop_command(process=child)

        assert child.wait.call_count == 2
        # The kill raced the child's end: whatever is left is killed at once, and nothing is
        assert group.calls[-1] == (4242, SIGKILL_NUMBER)

    def test_a_signal_refused_while_the_child_keeps_running_is_raised(self, mocker):
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = process.TimeoutExpired(cmd='game', timeout=1.0)
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=PermissionError)

        with pytest.raises(PermissionError):
            stop_command(process=child)

    def test_a_child_still_running_when_the_stop_raises_keeps_its_pipes(self, mocker):
        """Only a reaped child's pipes are closed: one still running may yet be read or stopped."""
        child = mocker.Mock(pid=4242, returncode=None)
        child.poll.return_value = None
        child.wait.side_effect = process.TimeoutExpired(cmd='game', timeout=1.0)
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=PermissionError)

        with pytest.raises(PermissionError):
            stop_command(process=child)

        child.stdout.close.assert_not_called()
        child.stderr.close.assert_not_called()
        child.stdin.close.assert_not_called()


class TestStopCommandEmptiesTheGroup:
    """When stop_command returns, nothing is left in the child's process group (POSIX).

    The group answers through a stand-in killpg built from its contract: a signal reaches every
    member present, ESRCH (ProcessLookupError) once no member is left, and on macOS EPERM
    (PermissionError) while every member left is ending. The grace is five looks long, and the
    looks do not sleep.

    ``ps``, which names what is left, is a stand-in too, printing a canned listing in its
    ``-o pid=,pgid=,stat=,command=`` format: Windows has no ``/bin/ps`` (these tests failed there
    with WinError 2, #263), and a real listing could hold a real group 4242.
    """

    LOOKS_IN_A_GRACE = 5
    # Processes of other groups only, as ps right-aligns its numbers: none is in group 4242
    OTHER_GROUPS = (
        '    1     1 Ss   /sbin/launchd\n  812   812 S+   /usr/bin/python3 -m http.server 8000\n'
    )

    @pytest.fixture(autouse=True)
    def posix(self, mocker):
        mocker.patch.object(process.sys, 'platform', 'linux')
        mocker.patch.object(
            process, 'signal', SimpleNamespace(SIGTERM=signal.SIGTERM, SIGKILL=SIGKILL_NUMBER)
        )
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.05)
        mocker.patch.object(process, 'GROUP_LOOK_SECONDS', 0.01)
        mocker.patch('glitchygames.clock.raw_sleep')
        self._ps_lists(mocker, listing=self.OTHER_GROUPS)

    @staticmethod
    def _ps_lists(mocker, *, listing):
        """Make ``ps`` print ``listing``, as ``_list_group`` runs it."""

        def stand_in_ps(command, **options):
            assert command == [
                process.PROCESS_LISTER,
                '-A',
                '-ww',
                '-o',
                'pid=,pgid=,stat=,command=',
            ]
            assert options == {'capture_output': True, 'text': True, 'check': False}
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=listing)

        mocker.patch.object(process.subprocess, 'run', side_effect=stand_in_ps)

    @staticmethod
    def _group_answering(answers):
        """Return a stand-in killpg answering each call with the next answer, and its calls.

        Returns:
            The stand-in and the list it records each (group, signal) call in.
        """
        calls = []
        remaining = list(answers)

        def killpg(group: int, signal_number: int) -> None:
            calls.append((group, signal_number))
            answer = remaining.pop(0)
            if answer is not None:
                raise answer

        return killpg, calls

    def test_a_member_left_after_a_gentle_stop_gets_the_grace_then_is_killed(self, mocker):
        """It may still be handling the signal: looked at for the grace, then killed."""
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        looks = [None] * self.LOOKS_IN_A_GRACE
        killpg, calls = self._group_answering([None, *looks, None, ProcessLookupError])
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=killpg)

        stop_command(process=child)

        assert calls == [
            (4242, signal.SIGTERM),
            *[(4242, 0)] * self.LOOKS_IN_A_GRACE,
            (4242, SIGKILL_NUMBER),
            (4242, SIGKILL_NUMBER),
        ]

    def test_killing_after_a_gentle_stop_is_logged(self, mocker, caplog):
        """A member still tearing down loses its cleanup to the kill: said, so it can be found."""
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        looks = [None] * self.LOOKS_IN_A_GRACE
        killpg, _ = self._group_answering([None, *looks, ProcessLookupError])
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=killpg)

        with caplog.at_level(logging.WARNING, logger=process.__name__):
            stop_command(process=child)

        assert [record.getMessage() for record in caplog.records] == [
            (
                'Process group 4242 still has processes a grace after the gentle stop; '
                'killing: none listed'
            )
        ]

    def test_a_group_that_outlives_the_kill_raises_naming_it(self, mocker):
        """Never a silent return: the error names the group and how to list what is left."""
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        killpg, calls = self._group_answering([None] * (1 + 2 * self.LOOKS_IN_A_GRACE))
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=killpg)

        # No real process is in a stand-in group, so ps lists none of it
        with pytest.raises(
            process.ProcessGroupSurvivedError,
            match=r'Process group 4242 still has processes a grace after SIGKILL: none listed',
        ):
            stop_command(process=child)

        assert calls[-self.LOOKS_IN_A_GRACE :] == [(4242, SIGKILL_NUMBER)] * self.LOOKS_IN_A_GRACE

    def test_the_error_names_each_survivor_by_pid_and_command_line(self, mocker):
        """What ps lists in the group is named, so the survivor can be found and stopped."""
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        killpg, _ = self._group_answering([None] * (1 + 2 * self.LOOKS_IN_A_GRACE))
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=killpg)
        self._ps_lists(
            mocker,
            listing=(
                self.OTHER_GROUPS
                + ' 4250  4242 S    /bin/sleep 60\n'
                + ' 4251  4242 R+   /usr/bin/python3 worker.py --role audio\n'
            ),
        )

        with pytest.raises(process.ProcessGroupSurvivedError) as survived:
            stop_command(process=child)

        assert str(survived.value) == (
            'Process group 4242 still has processes a grace after SIGKILL: '
            '4250 /bin/sleep 60; 4251 /usr/bin/python3 worker.py --role audio'
        )

    def test_a_group_ps_lists_only_zombies_of_is_not_a_survivor(self, mocker):
        """Zombies run nothing: a group still answering with only zombies in it ends quietly.

        The stand-in counterpart of the real-process zombie test, which cannot run on Windows.
        """
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        killpg, calls = self._group_answering([None] * (1 + 2 * self.LOOKS_IN_A_GRACE))
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=killpg)
        self._ps_lists(mocker, listing=self.OTHER_GROUPS + ' 4250  4242 Z+   (true)\n')

        stop_command(process=child)

        assert calls[-1] == (4242, SIGKILL_NUMBER)

    def test_a_group_of_ending_members_is_looked_at_until_it_is_gone(self, mocker):
        """A group whose members are all ending refuses signals on macOS: no error, look again."""
        child = mocker.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0
        killpg, calls = self._group_answering([
            None,
            PermissionError,
            PermissionError,
            ProcessLookupError,
        ])
        mocker.patch.object(process.os, 'killpg', create=True, side_effect=killpg)

        stop_command(process=child)

        assert calls == [(4242, signal.SIGTERM), (4242, 0), (4242, 0), (4242, 0)]


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

    @pytest.mark.parametrize(
        ('ignored', 'last_words', 'returncode'),
        [
            ((), 'interrupted', 0),
            (('SIGINT',), 'terminated', 0),
            (('SIGINT', 'SIGTERM'), '', -SIGKILL_NUMBER),
        ],
        ids=['sigint-ends-it', 'sigterm-after-the-grace', 'killed-after-both'],
    )
    def test_a_stop_that_starts_with_sigint_escalates_only_as_far_as_needed(
        self, tmp_path, mocker, ignored, last_words, returncode
    ):
        """``first_signal=SIGINT``: the group gets SIGINT, then SIGTERM, then SIGKILL.

        A pytest run turns SIGINT into an orderly KeyboardInterrupt in every worker, so every
        test's cleanup runs; SIGTERM (no handler in pytest) killed workers without any.
        """
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.5)
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=[sys.executable, '-c', child_reporting_its_signal(ignored=ignored)],
                environment=os.environ,
                output=output,
            )
            assert first_line(path=output_path) == 'ready'

            stop_command(process=child, first_signal=signal.SIGINT)

        assert child.returncode == returncode
        assert output_path.read_text(encoding='utf-8').splitlines()[1:] == (
            [last_words] if last_words else []
        )

    # By name, read in the test: the parameters are built at collection, also on Windows, whose
    # signal module has no SIGKILL (the class is skipped there, its parameters are not)
    @pytest.mark.parametrize('first_signal_name', ['SIGTERM', 'SIGKILL'])
    def test_a_member_the_group_signal_missed_is_stopped_too(
        self, tmp_path, mocker, first_signal_name
    ):
        """When stop_command returns, nothing is left in the child's group.

        On macOS a group signal can miss a member the group forks while the signal is
        delivered (bugs/2026-11-20-killpg-misses-a-process-forked-during-it-on-macos.md): the
        leader dies and the new member runs on, holding the child's pipes. The stand-in signal
        follows killpg's contract for that case: the first one reaches the leader only, as if
        the member were forked during its delivery; every later one is the real killpg.
        """
        first_signal = getattr(signal, first_signal_name)
        real_killpg = os.killpg
        missed = []

        def killpg_missing_a_forked_member(group: int, signal_number: int) -> None:
            if not missed and signal_number != 0:
                missed.append(signal_number)
                os.kill(group, signal_number)
                return
            real_killpg(group, signal_number)

        mocker.patch.object(process.os, 'killpg', side_effect=killpg_missing_a_forked_member)
        # A gently stopped group's member gets the grace before the kill: keep it short
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.5)
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=['/bin/sh', '-c', 'sleep 60 & echo "$!"; wait'],
                environment=os.environ,
                output=output,
            )
            member_pid = int(first_line(path=output_path))

            stop_command(process=child, first_signal=first_signal)

        assert missed == [first_signal]
        assert child.returncode is not None
        with pytest.raises(ProcessLookupError):
            real_killpg(child.pid, 0)
        assert not is_running(pid=member_pid)

    def test_a_child_that_ended_first_has_its_group_emptied(self, tmp_path, mocker):
        """The leader alone was stopped (SIGTERM to it, not its group); its member is not left.

        As the orphaned-process reproducer's sigterm-leader mode leaves a pytest run: the
        controller gone, its workers still in its group. stop_command, called after, finds the
        child ended and empties its group (it no longer returns at the reap alone).
        """
        # The member left gets the grace before the kill: keep it short
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.2)
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=['/bin/sh', '-c', 'sleep 60 & echo "$!"; wait'],
                environment=os.environ,
                output=output,
            )
            member_pid = int(first_line(path=output_path))
            os.kill(child.pid, signal.SIGTERM)
            child.wait()

            stop_command(process=child)

        with pytest.raises(ProcessLookupError):
            os.killpg(child.pid, 0)
        assert not is_running(pid=member_pid)

    def test_a_group_that_outlives_the_kill_is_named_with_its_members(self, tmp_path, mocker):
        """The error lists each process left in the group: its pid and command line.

        A process in uninterruptible sleep (state D) dies only when it wakes, whatever it is
        sent: the stand-in killpg answers as for a delivered signal and delivers nothing, so
        the group's sleep outlives the grace after the kill as such a process would.
        """
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.05)
        real_killpg = os.killpg

        def killpg_reaching_the_leader_only(group: int, signal_number: int) -> None:
            if signal_number != 0:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(group, signal_number)

        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            child = start_command(
                command=['/bin/sh', '-c', 'sleep 60 & echo "$!"; wait'],
                environment=os.environ,
                output=output,
            )
            member_pid = int(first_line(path=output_path))
            mocker.patch.object(process.os, 'killpg', side_effect=killpg_reaching_the_leader_only)
            try:
                with pytest.raises(process.ProcessGroupSurvivedError) as raised:
                    stop_command(process=child, first_signal=signal.SIGKILL)
            finally:
                with contextlib.suppress(ProcessLookupError):
                    real_killpg(child.pid, signal.SIGKILL)

        assert f'Process group {child.pid} still has processes' in str(raised.value)
        assert f'{member_pid} sleep 60' in str(raised.value)

    def test_a_group_left_with_only_an_unreaped_zombie_counts_as_empty(self, mocker):
        """A zombie runs nothing: a group holding only zombies is not a group that survived.

        The member's parent is this process, outside the group, and has not reaped it yet, so
        the zombie stays in the group after its leader is stopped (macOS answers the group's
        signals with EPERM, Linux delivers them to nobody). The same zombie rule as the
        child-process guard's (glitchygames.process.is_zombie_state).
        """
        mocker.patch.object(process, 'STOP_GRACE_SECONDS', 0.05)
        leader = subprocess.Popen(['/bin/sleep', '60'], process_group=0, text=True)
        member = subprocess.Popen(['/usr/bin/true'], process_group=leader.pid)
        try:
            os.waitid(os.P_PID, member.pid, os.WEXITED | os.WNOWAIT)

            stop_command(process=leader)

            assert leader.returncode == -signal.SIGTERM
        finally:
            with contextlib.suppress(ProcessLookupError):
                leader.kill()
            leader.wait()
            member.wait()

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


# A killed child's status on POSIX (-SIGKILL), written out: Windows' signal module has no SIGKILL
KILLED_STATUS = -9


class ChildThatOutlivesTheGracePeriod:
    """Stands in for a child that ignores the request to stop: only the kill ends it.

    A real one cannot exist on Windows (``terminate`` is ``TerminateProcess`` there), so the
    kill path is checked with this on every platform.
    """

    def __init__(self) -> None:
        """Record nothing yet."""
        self.calls: list[tuple[str, float | None]] = []

    def terminate(self) -> None:
        """Record the request to stop (and ignore it)."""
        self.calls.append(('terminate', None))

    def kill(self) -> None:
        """Record the kill."""
        self.calls.append(('kill', None))

    def wait(self, timeout: float | None = None) -> int:
        """Time out while given a timeout (still running); else end, killed.

        Returns:
            The killed child's status.

        Raises:
            subprocess.TimeoutExpired: While given a timeout.

        """
        self.calls.append(('wait', timeout))
        if timeout is not None:
            raise subprocess.TimeoutExpired(cmd='game', timeout=timeout)
        return KILLED_STATUS


def test_a_child_still_running_after_the_grace_period_is_killed_then_reaped():
    """Asked to stop, still running STOP_GRACE_SECONDS later: killed, then waited for."""
    child = ChildThatOutlivesTheGracePeriod()

    process.stop_and_reap(process=cast('subprocess.Popen[str]', child))

    assert child.calls == [
        ('terminate', None),
        ('wait', process.STOP_GRACE_SECONDS),
        ('kill', None),
        ('wait', None),
    ]


def test_a_child_still_running_at_its_timeout_raises_once_stopped(tmp_path):
    """On every platform (Windows too): the timeout raises TimeoutExpired after the stop.

    Whether the child is gone is checked on POSIX only (``TestRunCommandStoppedAtTimeout``):
    signal 0 to a process id is POSIX.
    """
    with pytest.raises(process.TimeoutExpired):
        process.run_command_stopped_at_timeout(
            command=[sys.executable, '-c', CHILD_THAT_NEVER_ENDS, str(tmp_path / 'child.pid')],
            environment=os.environ,
            timeout_seconds=SHORT_TIMEOUT_SECONDS,
        )


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


# A child that writes its process id to the file it is given, then, asked to stop (SIGTERM),
# writes 'terminated' there and ends: the gentle stop a game's engine turns into its teardown
CHILD_THAT_SAYS_IT_WAS_TERMINATED = (
    'import os, pathlib, signal, sys, time\n'
    'path = pathlib.Path(sys.argv[1])\n'
    'def terminated(signal_number, frame):\n'
    "    with path.open('a', encoding='utf-8') as file:\n"
    "        file.write('terminated\\n')\n"
    '    sys.exit(0)\n'
    'signal.signal(signal.SIGTERM, terminated)\n'
    "path.write_text(f'{os.getpid()}\\n', encoding='utf-8')\n"
    'time.sleep(60)\n'
)
# A child that writes whether it was started with SIGHUP ignored, then ends
CHILD_REPORTING_SIGHUP = (
    'import pathlib, signal, sys\n'
    'ignored = signal.getsignal(signal.SIGHUP) == signal.SIG_IGN\n'
    "pathlib.Path(sys.argv[1]).write_text(f'{ignored}\\n', encoding='utf-8')\n"
)
# Long enough that only the interrupt ends a launch
LAUNCH_TIMEOUT_SECONDS = 60.0
# The signals the launchers defer while a child is created, as this platform has them
LAUNCH_DEFERRED_SIGNALS = [
    getattr(signal, name) for name in ('SIGINT', 'SIGTERM', 'SIGHUP') if hasattr(signal, name)
]


def raise_system_exit(signal_number: int, _frame: object) -> None:
    """Stand in for the engine's ``exit_on_signal``: a terminating signal raises SystemExit.

    Raises:
        SystemExit: Always, with 128 + the signal.

    """
    signal.signal(signal_number, signal.SIG_IGN)
    raise SystemExit(128 + signal_number)


def launch_with_run_command(*, command: list[str]) -> None:
    """Launch with ``run_command``, its output not captured (record-trace's launch)."""
    process.run_command(
        command=command,
        environment=os.environ,
        timeout_seconds=None,
        capture_output=OutputCapture.NONE,
    )


def launch_with_run_command_capturing(*, command: list[str]) -> None:
    """Launch with ``run_command``, its output captured (through pipes) and a timeout."""
    process.run_command(
        command=command,
        environment=os.environ,
        timeout_seconds=LAUNCH_TIMEOUT_SECONDS,
        capture_output=OutputCapture.APART,
    )


def launch_stopped_at_timeout(*, command: list[str]) -> None:
    """Launch with ``run_command_stopped_at_timeout`` (verify's and measure's launch)."""
    process.run_command_stopped_at_timeout(
        command=command, environment=os.environ, timeout_seconds=LAUNCH_TIMEOUT_SECONDS
    )


LAUNCHERS = pytest.mark.parametrize(
    'launch',
    [launch_with_run_command, launch_with_run_command_capturing, launch_stopped_at_timeout],
    ids=['run_command', 'run_command capturing', 'run_command_stopped_at_timeout'],
)


def line_once_written(*, path: Path) -> str:
    """Wait for a file a child creates to hold a whole first line; return it.

    Returns:
        The line, without its newline.

    Raises:
        AssertionError: If no whole line arrives within WAIT_SECONDS.

    """
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if path.is_file() and '\n' in (text := path.read_text(encoding='utf-8')):
            return text.split('\n', 1)[0]
        time.sleep(POLL_SECONDS)
    message = f'{path}: no line within {WAIT_SECONDS} s'
    raise AssertionError(message)


def was_reaped(*, pid: int) -> bool:
    """Tell whether this process's child ``pid`` has been reaped (nothing left to wait for).

    A child killed but not waited for is a zombie this process can still reap: ``waitpid``
    then succeeds (and reaps it) instead of raising ``ChildProcessError``.

    Returns:
        True when the child was already reaped.

    """
    try:
        os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        return True
    return False


def kill_if_running(*, pid: int) -> None:
    """Kill a child a failing launcher left running, so the test leaves nothing behind."""
    if pid and is_running(pid=pid):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, SIGKILL_NUMBER)
        with contextlib.suppress(ChildProcessError):
            os.waitpid(pid, 0)


@pytest.fixture
def handlers_put_back():
    """Put back this process's handlers of the deferred signals after the test, as they were.

    Yields:
        The handlers as they were before the test, by signal.

    """
    before = {
        signal_number: signal.getsignal(signal_number) for signal_number in LAUNCH_DEFERRED_SIGNALS
    }
    yield before
    for signal_number, handler in before.items():
        signal.signal(signal_number, handler)


@pytest.mark.skipif(sys.platform == 'win32', reason='signals to a thread and waitpid are POSIX')
class TestAnInterruptedLaunchStopsAndReapsItsChild:
    """However a launch ends, its child is stopped and reaped before the launcher returns.

    bugs/2026-11-20-process-stop-tests-failed-under-load.md: ``subprocess.run`` answers Ctrl-C
    with SIGKILL and no wait (CPython's bpo-25942), so ``glitchygames record-trace`` exited with
    its game a zombie. The stop is the gentle one (SIGTERM, then the kill after the grace), so a
    game's engine can close its recording; and a signal that arrives while the child is being
    created is handled once the launcher holds the child, never before.
    """

    @LAUNCHERS
    @pytest.mark.parametrize(
        'interrupt',
        [
            (signal.SIGINT, signal.default_int_handler, KeyboardInterrupt),
            (signal.SIGTERM, raise_system_exit, SystemExit),
        ],
        ids=['ctrl-c', 'sigterm'],
    )
    def test_an_interrupt_while_waiting_stops_the_child_gently_and_reaps_it(
        self, tmp_path, handlers_put_back, launch, interrupt
    ):
        """The interrupt is raised after the child said it was terminated and was reaped."""
        del handlers_put_back
        signal_number, handler, raised = interrupt
        signal.signal(signal_number, handler)
        pid_file = tmp_path / 'child.pid'
        main_thread = threading.main_thread().ident
        child_pid = 0

        def interrupt_once_the_child_runs() -> None:
            line_once_written(path=pid_file)
            signal.pthread_kill(cast('int', main_thread), signal_number)

        interrupter = threading.Thread(target=interrupt_once_the_child_runs, daemon=True)
        interrupter.start()
        try:
            with pytest.raises(raised):
                launch(
                    command=[sys.executable, '-c', CHILD_THAT_SAYS_IT_WAS_TERMINATED, str(pid_file)]
                )
            interrupter.join(timeout=WAIT_SECONDS)
            child_pid = int(line_once_written(path=pid_file))
            reaped = was_reaped(pid=child_pid)
        finally:
            kill_if_running(pid=child_pid)

        assert reaped
        assert pid_file.read_text(encoding='utf-8').splitlines()[1:] == ['terminated']

    @LAUNCHERS
    def test_a_signal_while_the_child_is_created_is_handled_once_it_is_held(
        self, tmp_path, mocker, handlers_put_back, launch
    ):
        """Ctrl-C that lands inside ``Popen`` (after the fork): the child is stopped and reaped.

        Raised there, before the launcher held the child, it left the child running: the
        failure seen as the crash-boundary test's SIGTERM case (a candidate there, not proven).
        """
        del handlers_put_back
        signal.signal(signal.SIGINT, signal.default_int_handler)
        pid_file = tmp_path / 'child.pid'
        started: list[int] = []
        real_popen = subprocess.Popen

        def popen_interrupted_as_it_returns(
            *arguments: Any, **keywords: Any
        ) -> subprocess.Popen[str]:
            """``Popen`` with Ctrl-C landing after the child started, before it returns.

            Returns:
                The started child.

            """
            child = real_popen(*arguments, **keywords)
            started.append(child.pid)
            line_once_written(path=pid_file)
            signal.raise_signal(signal.SIGINT)
            return child

        mocker.patch.object(subprocess, 'Popen', popen_interrupted_as_it_returns)
        try:
            with pytest.raises(KeyboardInterrupt):
                launch(
                    command=[sys.executable, '-c', CHILD_THAT_SAYS_IT_WAS_TERMINATED, str(pid_file)]
                )
            reaped = was_reaped(pid=started[0])
        finally:
            for pid in started:
                kill_if_running(pid=pid)

        assert reaped
        assert pid_file.read_text(encoding='utf-8').splitlines()[1:] == ['terminated']

    def test_run_commands_timeout_kills_the_child_at_once_and_reaps_it(self, tmp_path):
        """At its timeout ``run_command`` kills (no gentle stop: that is the other launcher's)."""
        pid_file = tmp_path / 'child.pid'
        child_pid = 0
        try:
            with pytest.raises(process.TimeoutExpired):
                process.run_command(
                    command=[
                        sys.executable,
                        '-c',
                        CHILD_THAT_SAYS_IT_WAS_TERMINATED,
                        str(pid_file),
                    ],
                    environment=os.environ,
                    # Time for the child to write its pid first, as the stop test above gives it
                    timeout_seconds=SHORT_TIMEOUT_SECONDS * 3,
                    capture_output=OutputCapture.TOGETHER,
                )
            child_pid = int(line_once_written(path=pid_file))
            reaped = was_reaped(pid=child_pid)
        finally:
            kill_if_running(pid=child_pid)

        assert reaped
        assert pid_file.read_text(encoding='utf-8').splitlines()[1:] == []

    @LAUNCHERS
    def test_the_handlers_are_put_back_after_a_launch_that_ends_and_one_interrupted(
        self, tmp_path, mocker, handlers_put_back, launch
    ):
        """The deferral's handlers are gone once the launcher returns, however it returns."""
        before = handlers_put_back

        launch(command=[sys.executable, '-c', 'pass'])
        after_an_ended_launch = {number: signal.getsignal(number) for number in before}
        mocker.patch.object(subprocess, 'Popen', side_effect=FileNotFoundError('no such game'))
        with pytest.raises(FileNotFoundError):
            launch(command=[sys.executable, '-c', 'pass'])
        after_a_failed_launch = {number: signal.getsignal(number) for number in before}

        assert after_an_ended_launch == before
        assert after_a_failed_launch == before

    @LAUNCHERS
    def test_a_signal_this_process_ignores_stays_ignored_in_the_child(
        self, tmp_path, handlers_put_back, launch
    ):
        """An ignored signal is not deferred: ``nohup``'s ignored SIGHUP reaches the child."""
        del handlers_put_back
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        report = tmp_path / 'sighup.txt'

        launch(command=[sys.executable, '-c', CHILD_REPORTING_SIGHUP, str(report)])

        assert line_once_written(path=report) == 'True'

    def test_a_launch_from_another_thread_defers_nothing_and_runs(self, tmp_path):
        """Handlers can be set from the main thread only: elsewhere the launch runs as it is."""
        statuses: list[int] = []

        def launch_here() -> None:
            statuses.append(
                process.run_command(
                    command=[sys.executable, '-c', 'import sys; sys.exit(3)'],
                    environment=os.environ,
                    timeout_seconds=WAIT_SECONDS,
                ).returncode
            )

        launcher = threading.Thread(target=launch_here)
        launcher.start()
        launcher.join(timeout=WAIT_SECONDS)

        assert statuses == [3]


@LAUNCHERS
def test_a_signal_raised_while_the_child_is_created_is_handled_once_after_popen_returns(
    mocker, handlers_put_back, launch
):
    """The deferral records a signal that lands inside ``Popen`` and raises it once afterwards.

    Runs on every platform (``signal.raise_signal`` and a Python handler need no POSIX): the
    class above, which sends signals to a thread and reaps with waitpid, is POSIX only, and
    Windows' combined coverage missed the recording, and the raising again
    (coverage-combine-windows, #287).
    """
    del handlers_put_back
    events: list[str] = []

    def handle_interrupt(_signal_number: int, _frame: object) -> None:
        events.append('handled')

    signal.signal(signal.SIGINT, handle_interrupt)
    real_popen = subprocess.Popen

    def popen_interrupted_twice_as_it_returns(
        *arguments: Any, **keywords: Any
    ) -> subprocess.Popen[str]:
        """``Popen`` with two Ctrl-Cs landing after the child started, before it returns.

        Returns:
            The started child.

        """
        child = real_popen(*arguments, **keywords)
        signal.raise_signal(signal.SIGINT)
        signal.raise_signal(signal.SIGINT)
        events.append('popen returned')
        return child

    mocker.patch.object(subprocess, 'Popen', popen_interrupted_twice_as_it_returns)

    launch(command=[sys.executable, '-c', 'pass'])

    assert events == ['popen returned', 'handled']


@LAUNCHERS
def test_a_signal_this_process_ignores_stays_ignored_while_the_child_is_created(
    mocker, handlers_put_back, launch
):
    """An ignored SIGTERM is not deferred: it is still ignored inside ``Popen``, on every platform.

    The POSIX class's ``nohup`` test shows the effect in the child (SIGHUP, which Windows lacks);
    this one reads the handler where the child is created, so Windows covers the rule too.
    """
    del handlers_put_back
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    handlers_during_popen: list[object] = []
    real_popen = subprocess.Popen

    def popen_reading_the_terminate_handler(
        *arguments: Any, **keywords: Any
    ) -> subprocess.Popen[str]:
        """``Popen`` that notes SIGTERM's handler while the child is created.

        Returns:
            The started child.

        """
        handlers_during_popen.append(signal.getsignal(signal.SIGTERM))
        return real_popen(*arguments, **keywords)

    mocker.patch.object(subprocess, 'Popen', popen_reading_the_terminate_handler)

    launch(command=[sys.executable, '-c', 'pass'])

    assert handlers_during_popen == [signal.SIG_IGN]


class ChildInterruptedDuringItsGracePeriod(ChildThatOutlivesTheGracePeriod):
    """Stands in for a child whose grace wait a second Ctrl-C interrupts."""

    def wait(self, timeout: float | None = None) -> int:
        """Raise KeyboardInterrupt while given a timeout (the grace); else end, killed.

        Returns:
            The killed child's status.

        Raises:
            KeyboardInterrupt: While given a timeout.

        """
        self.calls.append(('wait', timeout))
        if timeout is not None:
            raise KeyboardInterrupt
        return KILLED_STATUS


def test_a_second_interrupt_during_the_grace_kills_and_reaps_before_it_is_raised():
    """Ctrl-C again while the child is given its grace: killed and reaped, then raised."""
    child = ChildInterruptedDuringItsGracePeriod()

    with pytest.raises(KeyboardInterrupt):
        process.stop_and_reap(process=cast('subprocess.Popen[str]', child))

    assert child.calls == [
        ('terminate', None),
        ('wait', process.STOP_GRACE_SECONDS),
        ('kill', None),
        ('wait', None),
    ]
