"""tests/child_process_guard.py: a test that leaves a process running fails, and it is stopped.

The guard records every child a test starts (``subprocess.Popen``) and, at the test's teardown,
finds each one still running, every process in a group one of them leads, and every
descendant of either; it kills them and names them. The decisions are checked on a listing
given to them; the guard itself on real processes (POSIX: process groups).
"""

from __future__ import annotations

import os
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - the guard records real children; these start them
import sys
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from tests.child_process_guard import (
    ChildProcessGuard,
    KillPlan,
    ListedProcess,
    controller_sweep_lines,
    kill_plan,
    leftover_processes,
    parse_process_listing,
    processes_to_sweep,
    sweep_processes_naming,
)

if TYPE_CHECKING:
    from pathlib import Path

# How long a test waits for a child to write its line, or for a stopped process to be gone
WAIT_SECONDS = 10.0
POLL_SECONDS = 0.05
OWN_PID = 1000
OWN_GROUP = 900
# A child in a session of its own that starts a grandchild (in its group), prints the
# grandchild's pid, then waits
SESSION_CHILD_WITH_GRANDCHILD = (
    'import subprocess, sys, time\n'
    "grandchild = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    'print(grandchild.pid, flush=True)\n'
    'time.sleep(60)\n'
)


def listed(*, pid: int, ppid: int, pgid: int, command: str = 'python') -> ListedProcess:
    """One row of a process listing.

    Returns:
        The row.

    """
    return ListedProcess(pid=pid, ppid=ppid, pgid=pgid, command=command)


class TestLeftoverProcesses:
    """Which processes a test left: decided on a listing, so on any host."""

    def test_a_running_child_and_its_descendants_are_left_over(self):
        processes = [
            listed(pid=2000, ppid=OWN_PID, pgid=OWN_GROUP, command='child'),
            listed(pid=2001, ppid=2000, pgid=OWN_GROUP, command='grandchild'),
            listed(pid=2002, ppid=2001, pgid=OWN_GROUP, command='great-grandchild'),
            listed(pid=3000, ppid=1, pgid=3000, command='unrelated'),
        ]

        leftovers = leftover_processes(
            processes=processes,
            running=[2000],
            group_leaders=[],
            own_pid=OWN_PID,
            own_group=OWN_GROUP,
        )

        assert [process.command for process in leftovers] == [
            'child',
            'grandchild',
            'great-grandchild',
        ]

    def test_a_group_outlives_the_child_that_led_it(self):
        """The leader ended (reaped); its game, reparented to init, is found by its group."""
        processes = [
            listed(pid=2001, ppid=1, pgid=2000, command='game'),
            listed(pid=2002, ppid=2001, pgid=2000, command="game's child"),
            listed(pid=3000, ppid=1, pgid=3000, command='unrelated'),
        ]

        leftovers = leftover_processes(
            processes=processes,
            running=[],
            group_leaders=[2000],
            own_pid=OWN_PID,
            own_group=OWN_GROUP,
        )

        assert [process.command for process in leftovers] == ['game', "game's child"]

    def test_this_process_and_its_own_group_are_never_left_over(self):
        """A child that ran in this process's group leads nothing: the group is ours."""
        processes = [
            listed(pid=OWN_PID, ppid=1, pgid=OWN_GROUP, command='pytest'),
            listed(pid=OWN_GROUP, ppid=1, pgid=OWN_GROUP, command='xdist controller'),
            listed(pid=4000, ppid=OWN_GROUP, pgid=OWN_GROUP, command='another worker'),
        ]

        leftovers = leftover_processes(
            processes=processes,
            running=[],
            group_leaders=[OWN_GROUP],
            own_pid=OWN_PID,
            own_group=OWN_GROUP,
        )

        assert leftovers == []

    def test_a_listing_is_read_with_command_lines_that_hold_spaces(self):
        listing = (
            '  2000  1000   900 /usr/bin/python -c import time; time.sleep(60)\n'
            '  2001  2000   900 sleep 60\n'
            '\n'
        )

        assert parse_process_listing(listing=listing) == [
            listed(
                pid=2000,
                ppid=1000,
                pgid=900,
                command='/usr/bin/python -c import time; time.sleep(60)',
            ),
            listed(pid=2001, ppid=2000, pgid=900, command='sleep 60'),
        ]


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


def process_exists(*, pid: int) -> bool:
    """Tell whether a process (not an unreaped zombie of this one) still exists.

    Returns:
        True while signal 0 reaches it.

    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.mark.skipif(sys.platform == 'win32', reason='the guard checks process groups (POSIX)')
class TestChildProcessGuard:
    """The guard on real processes."""

    def test_a_session_child_and_its_grandchild_left_running_are_stopped_and_named(self, tmp_path):
        guard = ChildProcessGuard()
        output_path = tmp_path / 'output.txt'
        with output_path.open('w', encoding='utf-8') as output:
            guard.start_recording()
            child = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - sys.executable and fixed source, as an argument list
                [sys.executable, '-c', SESSION_CHILD_WITH_GRANDCHILD],
                stdout=output,
                start_new_session=True,
            )
            grandchild_pid = int(first_line(path=output_path))
            try:
                leftovers = guard.stop_leftovers()
            finally:
                for pid in (child.pid, grandchild_pid):
                    if process_exists(pid=pid):
                        os.kill(pid, signal.SIGKILL)
                child.wait()

        assert sorted(process.pid for process in leftovers) == sorted([child.pid, grandchild_pid])
        assert child.returncode == -signal.SIGKILL
        deadline = time.monotonic() + WAIT_SECONDS
        while process_exists(pid=grandchild_pid) and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        assert not process_exists(pid=grandchild_pid)

    def test_children_that_all_ended_leave_nothing_and_list_no_processes(self, mocker):
        """A test whose children ran in this group and ended pays for no ``ps``."""
        guard = ChildProcessGuard()
        list_processes = mocker.Mock()
        guard.list_processes = list_processes

        guard.start_recording()
        subprocess.run([sys.executable, '-c', 'pass'], check=True)

        assert guard.stop_leftovers() == []
        list_processes.assert_not_called()

    def test_a_test_that_started_nothing_lists_no_processes(self, mocker):
        guard = ChildProcessGuard()
        list_processes = mocker.Mock()
        guard.list_processes = list_processes

        guard.start_recording()

        assert guard.stop_leftovers() == []
        list_processes.assert_not_called()

    def test_children_started_while_not_recording_are_not_the_tests(self, tmp_path):
        """A child started outside a test (a session fixture's, the guard's own ``ps``)."""
        guard = ChildProcessGuard()
        with (tmp_path / 'output.txt').open('w', encoding='utf-8') as output:
            child = subprocess.Popen(
                [sys.executable, '-c', 'import time; time.sleep(60)'],
                stdout=output,
                start_new_session=True,
            )
            try:
                guard.start_recording()

                assert guard.stop_leftovers() == []
                assert child.poll() is None
            finally:
                child.kill()
                child.wait()


RUN_DIRECTORY = '/runs/pytest-of-someone/pytest-5'


class TestWhatASweepKills:
    """Which processes a sweep takes, and how it kills them: decided on a listing.

    The final review (2026-11-13) reproduced the first: ``uv run pytest --basetemp=DIR`` names
    the directory, so the controller's sweep killed ``uv``, its own ancestor (the run exited -9
    though its tests passed).
    """

    def test_this_process_and_its_ancestors_are_never_swept_though_they_name_it(self):
        processes = [
            listed(
                pid=10, ppid=1, pgid=10, command=f'zsh -c uv run pytest --basetemp={RUN_DIRECTORY}'
            ),
            listed(pid=11, ppid=10, pgid=10, command=f'uv run pytest --basetemp={RUN_DIRECTORY}'),
            listed(
                pid=OWN_PID,
                ppid=11,
                pgid=10,
                command=f'python -m pytest --basetemp={RUN_DIRECTORY}',
            ),
            listed(
                pid=2000, ppid=1, pgid=2000, command=f'python {RUN_DIRECTORY}/popen-gw0/game.py'
            ),
        ]

        swept = processes_to_sweep(processes=processes, names=[RUN_DIRECTORY], own_pid=OWN_PID)

        assert [process.pid for process in swept] == [2000]

    @pytest.mark.parametrize(
        ('command', 'is_swept'),
        [
            (f'python {RUN_DIRECTORY}/popen-gw0/game.py', True),
            (f'python {RUN_DIRECTORY}', True),
            (f'tool --output={RUN_DIRECTORY}/run.jsonl.gz', True),
            (f"python -c 'x' '{RUN_DIRECTORY}/game.py'", True),
            (f'python {RUN_DIRECTORY}2/popen-gw0/game.py', False),
            (f'python {RUN_DIRECTORY}-old/game.py', False),
            (f'python /elsewhere{RUN_DIRECTORY}/game.py', False),
        ],
        ids=['inside', 'itself', 'after-equals', 'quoted', 'a-longer-name', 'a-suffix', 'deeper'],
    )
    def test_the_directory_is_matched_as_a_whole_path(self, command, is_swept):
        """``pytest-5`` is not ``pytest-52``: the name ends at a separator, a space or the end."""
        processes = [listed(pid=2000, ppid=1, pgid=2000, command=command)]

        swept = processes_to_sweep(processes=processes, names=[RUN_DIRECTORY], own_pid=OWN_PID)

        assert bool(swept) is is_swept

    def test_a_swept_processs_descendants_are_swept_with_it(self):
        processes = [
            listed(pid=2000, ppid=1, pgid=2000, command=f'tool {RUN_DIRECTORY}/run.jsonl.gz'),
            listed(pid=2001, ppid=2000, pgid=2000, command='python game.py'),
        ]

        swept = processes_to_sweep(processes=processes, names=[RUN_DIRECTORY], own_pid=OWN_PID)

        assert [process.pid for process in swept] == [2000, 2001]

    def test_a_group_is_killed_whole_only_when_every_member_is_swept(self):
        """A pager in a terminal's job naming a log there loses only itself, not its shell's job."""
        every_process = [
            listed(pid=2000, ppid=1, pgid=2000, command='tool'),
            listed(pid=2001, ppid=2000, pgid=2000, command='game'),
            listed(pid=3000, ppid=1, pgid=3000, command='zsh'),
            listed(pid=3001, ppid=3000, pgid=3000, command='less log'),
            listed(pid=4000, ppid=OWN_PID, pgid=OWN_GROUP, command='a child in our group'),
        ]
        swept = [every_process[0], every_process[1], every_process[3], every_process[4]]

        plan = kill_plan(processes=swept, every_process=every_process, own_group=OWN_GROUP)

        assert plan == KillPlan(groups=(2000,), pids=(3001, 4000))


@pytest.mark.skipif(sys.platform == 'win32', reason='the sweep kills process groups (POSIX)')
class TestSweepingARunsTemporaryDirectory:
    """After a run ends, every process naming its temporary directory is killed and listed.

    The backstop for a hard death (SIGKILL, a crash, ``os._exit``): nothing in the run's own
    process unwinds, so neither the test's cleanup nor the guard runs. A test's children name
    its ``tmp_path`` (their scripts, files and outputs are there).
    """

    def test_a_process_naming_the_directory_is_killed_and_one_elsewhere_is_left(self, tmp_path):
        run_temporary = tmp_path / 'run-temporary'
        run_temporary.mkdir()
        elsewhere = tmp_path / 'elsewhere'
        elsewhere.mkdir()
        sleeper = 'import sys, time; time.sleep(60)'
        with (tmp_path / 'output.txt').open('w', encoding='utf-8') as output:
            left_behind = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - sys.executable, fixed source
                [sys.executable, '-c', sleeper, str(run_temporary / 'game.py')],
                stdout=output,
                start_new_session=True,
            )
            unrelated = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - sys.executable, fixed source
                [sys.executable, '-c', sleeper, str(elsewhere / 'game.py')],
                stdout=output,
                start_new_session=True,
            )
            try:
                swept = sweep_processes_naming(directory=run_temporary)

                left_behind.wait(timeout=WAIT_SECONDS)
                assert [process.pid for process in swept] == [left_behind.pid]
                assert str(run_temporary) in swept[0].command
                assert left_behind.returncode == -signal.SIGKILL
                assert unrelated.poll() is None
            finally:
                for child in (left_behind, unrelated):
                    if child.poll() is None:
                        child.kill()
                    child.wait()

    def test_nothing_naming_the_directory_is_nothing_swept(self, tmp_path):
        assert sweep_processes_naming(directory=tmp_path / 'never-used') == []


@pytest.mark.skipif(sys.platform == 'win32', reason='the sweep kills process groups (POSIX)')
class TestTheControllersSweep:
    """At the run's end its controller sweeps the run's temporary directory (its workers' too)."""

    @staticmethod
    def run_configuration(*, basetemp: Path | None, worker: bool = False) -> SimpleNamespace:
        """A stand-in pytest configuration: its temporary directory, and whether it is a worker.

        Returns:
            The configuration.

        """
        configuration = SimpleNamespace(_tmp_path_factory=SimpleNamespace(_basetemp=basetemp))
        if worker:
            configuration.workerinput = {'workerid': 'gw0'}
        return configuration

    def test_a_process_naming_the_runs_temporary_directory_is_killed_and_named(self, tmp_path):
        game = tmp_path / 'popen-gw3' / 'test_a0' / 'game.py'
        game.parent.mkdir(parents=True)
        with (tmp_path / 'output.txt').open('w', encoding='utf-8') as output:
            left_behind = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] - sys.executable, fixed source
                [sys.executable, '-c', 'import time; time.sleep(60)', str(game)],
                stdout=output,
                start_new_session=True,
            )
            try:
                lines = controller_sweep_lines(config=self.run_configuration(basetemp=tmp_path))

                left_behind.wait(timeout=WAIT_SECONDS)
            finally:
                if left_behind.poll() is None:
                    left_behind.kill()
                left_behind.wait()

        assert lines == [
            f'pid {left_behind.pid}: {sys.executable} -c import time; time.sleep(60) {game}'
        ]
        assert left_behind.returncode == -signal.SIGKILL

    def test_a_worker_and_a_run_that_made_no_temporary_directory_sweep_nothing(
        self, tmp_path, mocker
    ):
        sweep = mocker.patch('tests.child_process_guard.sweep_processes_naming')

        assert (
            controller_sweep_lines(config=self.run_configuration(basetemp=tmp_path, worker=True))
            == []
        )
        assert controller_sweep_lines(config=self.run_configuration(basetemp=None)) == []
        sweep.assert_not_called()
