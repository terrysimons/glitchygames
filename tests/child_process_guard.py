"""A test that leaves a process running fails, and the process is stopped (BUGS.md #275).

The harness (tests/harness.py ``no_child_process_left_running``) records, while each test runs,
every child it starts through ``subprocess.Popen`` (``run_command``, ``start_command``,
``subprocess.run`` and the rest all start one), keeping the ``Popen`` object and whether the
child led a group of its own (``start_new_session`` or ``process_group``). At the test's
teardown, after its own fixtures stopped what they started, it finds:

1. each recorded child still running (``poll()``: our own child, so a reused pid cannot fool
   it; a zombie the test never waited for is reaped by it and left out, since nothing runs);
2. every process in a group a recorded child led, which outlives its leader (a tool that ended
   with its game still running in its group: BUGS.md #275);
3. every descendant of either.

Each is killed (a group of its own as a whole, SIGKILL), our children are reaped, and the test
errors naming each command line. ``ps`` is called once, and only when a recorded child is still
running or led a group: most tests start no child, and a child that ran in this process's group
and ended left nothing behind.

Limits: POSIX only (on Windows the guard records nothing and checks nothing: no process
groups). A grandchild that both left its group (``setsid``) and lost its parent is not found.
A child started before the test's function-scoped fixtures (a module- or session-scoped
fixture's) is not the test's, and is not recorded. A child started without ``subprocess`` (a
``multiprocessing`` worker, ``os.fork``) is not recorded.
"""

from __future__ import annotations

import contextlib
import functools
import os
import re
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - records the suite's children; runs ps (fixed arguments, no shell)
import sys
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path

# What ps prints for every process: pid, parent, process group and the whole command line
PROCESS_LISTING_COMMAND = ('ps', '-A', '-ww', '-o', 'pid=,ppid=,pgid=,command=')
# How long a killed child of ours may take to be reaped
REAP_TIMEOUT_SECONDS = 10.0
# The fields before a listing row's command line
LISTING_FIELDS_BEFORE_COMMAND = 3


class ListedProcess(BaseModel):
    """One process of a ``ps`` listing."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    pid: int
    ppid: int
    pgid: int
    command: str


def parse_process_listing(*, listing: str) -> list[ListedProcess]:
    """Read ``PROCESS_LISTING_COMMAND``'s output.

    Returns:
        One entry per row; blank rows are skipped.

    """
    processes = []
    for line in listing.splitlines():
        fields = line.split(None, LISTING_FIELDS_BEFORE_COMMAND)
        if len(fields) <= LISTING_FIELDS_BEFORE_COMMAND:
            continue
        pid, ppid, pgid, command = fields
        processes.append(
            ListedProcess(pid=int(pid), ppid=int(ppid), pgid=int(pgid), command=command)
        )
    return processes


def leftover_processes(
    *,
    processes: Sequence[ListedProcess],
    running: Sequence[int],
    group_leaders: Sequence[int],
    own_pid: int,
    own_group: int,
) -> list[ListedProcess]:
    """Return the processes a test left: running children, their groups and descendants.

    Args:
        processes: Every process (``parse_process_listing``).
        running: The test's children still running.
        group_leaders: The test's children that led a group of their own, running or not.
        own_pid: This process (never a leftover).
        own_group: This process's group (never a leftover group: the xdist controller and
            every worker are in it).

    Returns:
        The leftovers, in the listing's order.

    """
    led_groups = {group for group in group_leaders if group != own_group}
    found = {process.pid for process in processes if process.pid in set(running)}
    found |= {process.pid for process in processes if process.pgid in led_groups}
    while True:
        descendants = {
            process.pid
            for process in processes
            if process.ppid in found and process.pid not in found
        }
        if not descendants:
            break
        found |= descendants
    found.discard(own_pid)
    return [process for process in processes if process.pid in found]


def list_processes() -> list[ListedProcess]:
    """List every process (``PROCESS_LISTING_COMMAND``).

    Returns:
        The processes.

    """
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - ps with fixed arguments, as an argument list
        PROCESS_LISTING_COMMAND, capture_output=True, text=True, check=True
    )
    return parse_process_listing(listing=result.stdout)


class RecordedChild(BaseModel):
    """A child a test started, and whether it led a group of its own."""

    model_config = ConfigDict(frozen=True, extra='forbid', arbitrary_types_allowed=True)

    process: subprocess.Popen[Any]
    leads_group: bool


class ChildProcessGuard:
    """Records the children started while it records; stops and names what they left running."""

    def __init__(self) -> None:
        """Start not recording, with nothing recorded."""
        self.children: list[RecordedChild] = []
        self.list_processes: Callable[[], list[ListedProcess]] = list_processes

    def start_recording(self) -> None:
        """Record every child started from now until ``stop_leftovers``."""
        install_popen_recorder()
        self.children = []
        RECORDING_GUARDS.append(self)

    def record(self, *, process: subprocess.Popen[Any], leads_group: bool) -> None:
        """Keep a child just started (``install_popen_recorder``'s hook)."""
        self.children.append(RecordedChild(process=process, leads_group=leads_group))

    def stop_leftovers(self) -> list[ListedProcess]:
        """Stop recording; kill and reap what the recorded children left running.

        Returns:
            The processes found left running (now killed), in the listing's order.

        """
        with contextlib.suppress(ValueError):
            RECORDING_GUARDS.remove(self)
        children, self.children = self.children, []
        if sys.platform == 'win32':
            return []
        running = [child.process for child in children if child.process.poll() is None]
        group_leaders = [child.process.pid for child in children if child.leads_group]
        if not running and not group_leaders:
            return []
        own_group = os.getpgrp()
        listing = self.list_processes()
        leftovers = leftover_processes(
            processes=listing,
            running=[process.pid for process in running],
            group_leaders=group_leaders,
            own_pid=os.getpid(),
            own_group=own_group,
        )
        kill_processes(processes=leftovers, every_process=listing, own_group=own_group)
        for process in running:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=REAP_TIMEOUT_SECONDS)
        return leftovers


# The guards recording now: every child started is recorded by each (a test of the guard records
# with a guard of its own while the harness's records the test)
RECORDING_GUARDS: list[ChildProcessGuard] = []


class KillPlan(BaseModel):
    """How ``kill_processes`` kills: whole groups, and single processes."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    groups: tuple[int, ...]
    pids: tuple[int, ...]


def kill_plan(
    *,
    processes: Sequence[ListedProcess],
    every_process: Sequence[ListedProcess],
    own_group: int,
) -> KillPlan:
    """Decide how to kill ``processes``: a group whole only when every member of it is one.

    A group with a member not being killed (a terminal job whose pager names a run's file; this
    process's own group, the xdist controller and workers) loses only the processes chosen.

    Args:
        processes: The processes to kill.
        every_process: Every process (to see each group's other members).
        own_group: This process's group (never killed whole).

    Returns:
        The groups to kill whole and the other processes to kill one by one, each sorted.

    """
    chosen = {process.pid for process in processes}
    whole_groups = {
        group
        for group in {process.pgid for process in processes}
        if group != own_group
        and all(member.pid in chosen for member in every_process if member.pgid == group)
    }
    return KillPlan(
        groups=tuple(sorted(whole_groups)),
        pids=tuple(
            sorted(process.pid for process in processes if process.pgid not in whole_groups)
        ),
    )


def kill_processes(
    *,
    processes: Sequence[ListedProcess],
    every_process: Sequence[ListedProcess],
    own_group: int,
) -> None:
    """SIGKILL each process as ``kill_plan`` decides; one already gone is no error.

    Args:
        processes: The processes to kill.
        every_process: Every process (the listing ``processes`` came from).
        own_group: This process's group.

    """
    plan = kill_plan(processes=processes, every_process=every_process, own_group=own_group)
    for group in plan.groups:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(group, signal.SIGKILL)
    for pid in plan.pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


def processes_to_sweep(
    *, processes: Sequence[ListedProcess], names: Sequence[str], own_pid: int
) -> list[ListedProcess]:
    """Choose what a sweep kills: processes naming a directory, and their descendants.

    A name matches as a whole path: after the start, a space, ``=`` or a quote, and before the
    end, a separator, a space or a quote (``pytest-5`` is not ``pytest-52``). This process and
    its ancestors are never chosen: ``uv run pytest --basetemp=DIR`` names the directory too
    (the final review, 2026-11-13, saw ``uv`` killed).

    Args:
        processes: Every process (``list_processes``).
        names: The directory's spellings (as given and resolved).
        own_pid: This process.

    Returns:
        The processes chosen, in the listing's order.

    """
    by_pid = {process.pid: process for process in processes}
    ancestors: set[int] = set()
    pid = own_pid
    while pid in by_pid and pid not in ancestors:
        ancestors.add(pid)
        pid = by_pid[pid].ppid
    ancestors.add(own_pid)
    pattern = re.compile(
        '|'.join(rf'(?:^|[\s=\'"]){re.escape(name)}(?=$|[/\s\'"])' for name in names)
    )
    chosen = {
        process.pid
        for process in processes
        if process.pid not in ancestors and pattern.search(process.command)
    }
    while True:
        descendants = {
            process.pid
            for process in processes
            if process.ppid in chosen and process.pid not in chosen | ancestors
        }
        if not descendants:
            break
        chosen |= descendants
    return [process for process in processes if process.pid in chosen]


def sweep_processes_naming(
    *, directory: Path, list_every_process: Callable[[], list[ListedProcess]] | None = None
) -> list[ListedProcess]:
    """Kill every process whose command line names ``directory``, with its descendants.

    The backstop for a run that died hard (SIGKILL, a crash, ``os._exit``): nothing in it
    unwound, so neither its tests' cleanup nor the guard ran, and a child a test started in a
    session of its own outlived it. Called with the run's temporary directory once the run has
    ended: a test's children name its ``tmp_path`` (their scripts, files and outputs), and the
    directory is the run's alone. The path is matched as given and resolved (macOS's
    ``/var`` is ``/private/var``), as a whole path (``processes_to_sweep``), never in this
    process or its ancestors; a group is killed whole only when every member is swept
    (``kill_plan``). POSIX only: on Windows nothing is swept.

    Args:
        directory: The ended run's temporary directory.
        list_every_process: Lists every process (tests pass a stand-in); None is
            ``list_processes`` (``ps``).

    Returns:
        The processes killed, in the listing's order.

    """
    if sys.platform == 'win32':
        return []
    listing = (list_processes if list_every_process is None else list_every_process)()
    swept = processes_to_sweep(
        processes=listing,
        names=sorted({str(directory), str(directory.resolve())}),
        own_pid=os.getpid(),
    )
    kill_processes(processes=swept, every_process=listing, own_group=os.getpgrp())
    return swept


def controller_sweep_lines(*, config: Any) -> list[str]:
    """Sweep the run's temporary directory once its workers are done; name what was found.

    Called by the run's controller at its terminal summary (tests/harness.py), after every
    xdist worker ended: a worker killed outright (SIGKILL, the OOM killer, a crash) ran no
    cleanup, and its tests' children name their ``tmp_path``, inside the controller's
    temporary directory (each worker's is ``popen-gwN`` in it). Not in a worker, and not for a
    run that made no temporary directory (``getbasetemp`` would make one).

    Args:
        config: pytest's configuration (``pytest.Config``; its temporary-path factory).

    Returns:
        One line per process found (now killed), naming it.

    """
    if hasattr(config, 'workerinput'):
        return []
    # pytest's own record of the directory it made (private: pytest has no public way to ask
    # whether the run made one), read so that none is made only to sweep it
    basetemp = config._tmp_path_factory._basetemp
    if basetemp is None:
        return []
    return [
        f'pid {process.pid}: {process.command}'
        for process in sweep_processes_naming(directory=basetemp)
    ]


@functools.cache
def install_popen_recorder() -> None:
    """Wrap ``subprocess.Popen.__init__`` once per process to tell the recording guards.

    Each child started is passed, with whether it leads a group of its own, to every guard in
    ``RECORDING_GUARDS``; with none recording, the wrapper only starts the child.
    """
    original_init = subprocess.Popen.__init__

    @functools.wraps(original_init)
    def recording_init(self: subprocess.Popen[Any], *arguments: Any, **options: Any) -> None:
        original_init(self, *arguments, **options)
        leads_group = bool(options.get('start_new_session')) or (
            options.get('process_group') is not None
        )
        for guard in RECORDING_GUARDS:
            guard.record(process=self, leads_group=leads_group)

    subprocess.Popen.__init__ = recording_init  # type: ignore[method-assign]
