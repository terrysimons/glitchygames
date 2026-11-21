"""Child processes: ``run_command`` and ``start_command``, the engine's child-process launchers.

``run_command`` waits for its child: used by the determinism audit's replays
(glitchygames/replay/audit.py), a watched replay's restarts (glitchygames/replay/rebuild.py),
the replay pytest plugin (glitchygames/testing/replays.py) and the driver comparison's tools
(scripts/build_sdl_x11.py, scripts/driver_configurations.py). ``start_command`` does not: the test
suite's driver comparison (tests/driver_comparison.py) runs the suite on the native driver
alongside the dummy run, and ``stop_command`` ends that child with every process it started.
Children get an argument list, never a shell, with the environment in place before the child's
interpreter starts.

The engine's child commands are its own command line with options changed, and the helpers here
are the one way they are changed (``without_option``, ``with_options_appended``): options are
added after the command's options and before any bare ``--``, after which nothing is an option.

This module is a leaf: it imports only the standard library (no engine, no pygame), so the pytest
plugin can import it at configuration time.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] — runs the engine's own game commands (argument list, no shell)
import sys
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple, TextIO

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

# What run_command raises for a child that outlives its timeout (subprocess's own exception,
# named here so callers need not import subprocess)
TimeoutExpired = subprocess.TimeoutExpired
# What run_command returns (subprocess's own class, named here for callers' annotations)
CompletedProcess = subprocess.CompletedProcess
# What start_command returns (subprocess's own class, named here for callers' annotations)
RunningProcess = subprocess.Popen
# How long stop_command lets a child end on its own before killing it
STOP_GRACE_SECONDS = 10.0
# How often stop_command looks again whether a stopped child's process group is gone
GROUP_LOOK_SECONDS = 0.01
# ps, by its full path (macOS and Linux keep it in /bin), to name a group's members in an error
PROCESS_LISTER = '/bin/ps'
# The fields of each row _list_group asks ps for: pid, process group, state, command line
GROUP_LISTING_FIELDS = 4
# ps's state letter for a zombie: a process that has exited and waits for its parent to reap it
ZOMBIE_STATE = 'Z'

LOG = logging.getLogger(__name__)


def is_zombie_state(state: str) -> bool:
    """Tell whether a ``ps`` state is a zombie's (it has exited: it runs nothing).

    The one rule ``stop_command`` and the test suite's child-process guard both judge by.

    Args:
        state: ``ps``'s ``stat`` (its first letter is the state; the rest are flags).

    Returns:
        True for a zombie.

    """
    return state.startswith(ZOMBIE_STATE)


class GroupMember(NamedTuple):
    """One process of a process group, as ``ps`` lists it."""

    pid: int
    state: str
    command: str


class ProcessGroupSurvivedError(RuntimeError):
    """A stopped child's process group still has processes a grace after it was killed."""


class OutputCapture(StrEnum):
    """What ``run_command`` does with a child's standard output and error.

    Attributes:
        NONE: Neither is captured: the child writes to this process's.
        TOGETHER: Both are captured together, in the result's ``stdout``.
        APART: Each is captured on its own, in ``stdout`` and ``stderr`` (a child whose
            standard output is a listing: ``glitchygames unmeasured``'s).

    """

    NONE = 'none'
    TOGETHER = 'together'
    APART = 'apart'


# The subprocess settings (stdout, stderr) that make each capture
OUTPUT_STREAMS: dict[OutputCapture, tuple[int | None, int | None]] = {
    OutputCapture.NONE: (None, None),
    OutputCapture.TOGETHER: (subprocess.PIPE, subprocess.STDOUT),
    OutputCapture.APART: (subprocess.PIPE, subprocess.PIPE),
}
# Arguments after a bare -- are not options: appended options go before it
END_OF_OPTIONS = '--'


def split_at_end_of_options(*, arguments: Sequence[str]) -> tuple[list[str], list[str]]:
    """Split a command line before its first bare ``--``.

    Args:
        arguments: A command line.

    Returns:
        The arguments before the ``--``, and the ``--`` with everything after it (empty when
        there is none).

    """
    if END_OF_OPTIONS in arguments:
        index = list(arguments).index(END_OF_OPTIONS)
        return list(arguments[:index]), list(arguments[index:])
    return list(arguments), []


def without_option(*, arguments: Sequence[str], option: str, takes_value: bool) -> list[str]:
    """Return ``arguments`` without any occurrence of a long option before a bare ``--``.

    Args:
        arguments: A command line.
        option: The option, e.g. ``--replay-trace``.
        takes_value: True for an option given as ``option VALUE`` or ``option=VALUE`` (both
            removed); False for a flag.

    Returns:
        The other arguments, in order (after a ``--``, all of them).

    """
    options, rest = split_at_end_of_options(arguments=arguments)
    kept: list[str] = []
    skips_next = False
    for argument in options:
        if skips_next:
            skips_next = False
            continue
        if argument == option:
            skips_next = takes_value
            continue
        if takes_value and argument.startswith(f'{option}='):
            continue
        kept.append(argument)
    return [*kept, *rest]


def with_options_appended(*, arguments: Sequence[str], appended: Sequence[str]) -> list[str]:
    """Return ``arguments`` with ``appended`` added after its options (before a bare ``--``).

    Args:
        arguments: A command line.
        appended: Options and their values, in order.

    Returns:
        The command line.

    """
    options, rest = split_at_end_of_options(arguments=arguments)
    return [*options, *appended, *rest]


def run_command(
    *,
    command: Sequence[str],
    environment: Mapping[str, str],
    timeout_seconds: float | None,
    capture_output: OutputCapture = OutputCapture.NONE,
    working_directory: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command (an argument list, never a shell) as a child process and wait for it.

    The engine's one child-process launcher: the audit's replays use it, so do a watched
    replay's restarts (glitchygames/replay/rebuild.py), the replay pytest plugin and the
    end-to-end audit tests.

    Args:
        command: The program and its arguments.
        environment: The child's whole environment, in place before its interpreter starts.
        timeout_seconds: Kill the child (TimeoutExpired) after this long; None waits for as long
            as it runs (a restarted watched replay, glitchygames/replay/rebuild.py).
        capture_output: What is captured of the child's standard output and error
            (``OutputCapture``: none, together in ``stdout``, or apart in ``stdout`` and
            ``stderr``).
        working_directory: The child's working directory (None: this process's), e.g. a
            build's directory for SDL's configure script (scripts/build_sdl_x11.py).

    Returns:
        The finished process (``returncode``; ``stdout`` when captured, else None; ``stderr``
        when captured apart, else None).

    """
    standard_output, standard_error = OUTPUT_STREAMS[capture_output]
    return subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] — sys.executable with a game's command line plus fixed flags, as an argument list (no shell)
        list(command),
        env=dict(environment),
        stdout=standard_output,
        stderr=standard_error,
        text=True,
        check=False,
        timeout=timeout_seconds,
        cwd=working_directory,
    )


def run_command_stopped_at_timeout(
    *,
    command: Sequence[str],
    environment: Mapping[str, str],
    timeout_seconds: float,
    working_directory: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command as ``run_command`` does, its output not captured, stopping it gently.

    For a child that may start children of its own (a game given ``--verify`` or ``--measure``
    replays each recording in one): a child still running after ``timeout_seconds`` is asked to
    stop first (SIGTERM; on Windows, terminated), so its engine can stop and reap its own
    children as it ends (``exit_on_signal``), and is killed only if it is still running after
    STOP_GRACE_SECONDS. ``run_command`` kills a child at once, which would leave such a
    grandchild running. The child is stopped the same way, and reaped, however this process
    stops waiting (a signal's SystemExit, Ctrl-C).

    Args:
        command: The program and its arguments.
        environment: The child's whole environment, in place before its interpreter starts.
        timeout_seconds: Stop the child (TimeoutExpired) after this long.
        working_directory: The child's working directory (None: this process's).

    Returns:
        The finished process (``returncode``; ``stdout`` and ``stderr`` None: the child writes
        to this process's). A child that outlived ``timeout_seconds`` raises ``TimeoutExpired``
        once it is stopped and reaped.

    """
    child = subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] — sys.executable with a game's command line plus fixed flags, as an argument list (no shell)
        list(command),
        env=dict(environment),
        text=True,
        cwd=working_directory,
    )
    try:
        returncode = child.wait(timeout=timeout_seconds)
    except BaseException:
        # The timeout, or this process being stopped (a signal's SystemExit, Ctrl-C) while waiting
        stop_and_reap(process=child)
        raise
    return subprocess.CompletedProcess(args=list(command), returncode=returncode)


def stop_and_reap(*, process: subprocess.Popen[str]) -> None:
    """Ask a child to stop, kill it if it is still running after STOP_GRACE_SECONDS, reap it.

    The child alone (``stop_command`` stops a child started in a session of its own with its
    whole group). SIGTERM lets a game end through its engine's teardown, which stops and reaps
    the children it is waiting for.

    Args:
        process: The child.

    """
    process.terminate()
    try:
        process.wait(timeout=STOP_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def start_command(
    *, command: Sequence[str], environment: Mapping[str, str], output: TextIO
) -> subprocess.Popen[str]:
    """Start a command (an argument list, never a shell) as a child process; do not wait.

    On POSIX the child leads a session of its own, so ``stop_command`` can end it with every
    process it started (a pytest run's xdist workers), and a terminal's Ctrl-C reaches only this
    process, which then stops the child.

    Args:
        command: The program and its arguments.
        environment: The child's whole environment, in place before its interpreter starts.
        output: Where the child's standard output and error go (an open file).

    Returns:
        The running process (``wait()`` for its ``returncode``).

    """
    return subprocess.Popen(  # ruff: ignore[subprocess-without-shell-equals-true] — sys.executable with the suite's own command line plus fixed flags, as an argument list (no shell)
        list(command),
        env=dict(environment),
        stdout=output,
        stderr=subprocess.STDOUT,
        text=True,
        # POSIX only (Windows ignores it): stop_command terminates a Windows child alone
        start_new_session=True,
    )


def stop_command(*, process: subprocess.Popen[str], first_signal: int = signal.SIGTERM) -> None:
    """End a child ``start_command`` started, with every process in its group, and reap it.

    On POSIX the group gets ``first_signal``, then, each after STOP_GRACE_SECONDS while the child
    still runs, SIGTERM (when the first signal was another) and SIGKILL. On Windows the child is
    terminated, then killed after the grace (no group signal there; ``first_signal`` is unused).
    A child that has already ended (on Windows) is left alone; on POSIX what it left in its group
    gets ``first_signal`` and is then emptied as below (the orphaned-process reproducer's
    sigterm-leader mode leaves a pytest run's workers so). A child ending between the check and
    a signal is reaped (``_signal_the_group``).

    On POSIX, once the child it signalled is reaped, nothing is left in its group when this
    returns (``_empty_the_group``): macOS can let a member forked during a group signal run on,
    so a member still there is given the grace (after a gentle stop) and then killed until the
    group is gone, or ``ProcessGroupSurvivedError`` is raised.

    The group signal reaches the child and every process it started that stayed in its group
    (a pytest run's xdist workers); a grandchild that started a session of its own is not in it.
    A pytest run should be stopped with ``first_signal=signal.SIGINT``: pytest turns it into an
    orderly KeyboardInterrupt in every worker, so each test's ``finally`` and fixture teardown
    stop what the test started. SIGTERM, which pytest does not handle, kills a worker at once,
    and a test's child in a session of its own is then left running (BUGS.md #275). A game
    keeps the default: its engine turns SIGTERM into its own teardown.

    Args:
        process: The child.
        first_signal: The first signal for the group (POSIX).

    """
    if sys.platform == 'win32':
        if process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        return
    if process.poll() is not None:
        # Ended already (its group signal missed nothing yet: none was sent): what it left in
        # its group gets first_signal, as a running child's group would
        try:
            os.killpg(process.pid, first_signal)
        except ProcessLookupError:
            return
        except PermissionError:
            pass
        _empty_the_group(process=process, killed=first_signal == signal.SIGKILL)
        return
    last_signal = _stop_the_leader(process=process, first_signal=first_signal)
    _empty_the_group(process=process, killed=last_signal == signal.SIGKILL)


def _stop_the_leader(*, process: subprocess.Popen[str], first_signal: int) -> int:
    """Signal a running child's group, escalating a grace apart, until the child ends (POSIX).

    Args:
        process: The child (its process group leader).
        first_signal: The first signal for the group.

    Returns:
        The last signal sent to the group (the one that ended the child, or that it was
        ending as it came).

    """
    escalation = [first_signal]
    if first_signal != signal.SIGTERM:
        escalation.append(signal.SIGTERM)
    for signal_number in escalation:
        if not _signal_the_group(process=process, signal_number=signal_number):
            return signal_number
        try:
            process.wait(timeout=STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            continue
        return signal_number
    if _signal_the_group(process=process, signal_number=signal.SIGKILL):
        process.wait()
    return signal.SIGKILL


def _empty_the_group(
    *, process: subprocess.Popen[str], killed: bool, sleep: Callable[[float], None] | None = None
) -> None:
    """Make sure nothing is left in a stopped child's process group (POSIX).

    A group signal can miss a member the group forks while it is delivered: macOS lets the new
    process run on (bugs/2026-11-20-killpg-misses-a-process-forked-during-it-on-macos.md), so
    the leader ends and the member keeps running, holding whatever the child held (its pipes).
    So after the leader is reaped the group is looked at, every GROUP_LOOK_SECONDS: a member
    still in it after a gentle stop gets the grace to end on its own (it may still be handling
    the signal), then the group is killed, again at each look until it is gone
    (``ProcessLookupError``). After a kill the group is killed at once. The bounds count looks,
    not seconds read from a clock, so the wait ends whatever a clock does. The group id stays
    the leader's pid while any member is left (no new process can take a pid a live group
    uses), so nothing outside the group is signalled then. Once the last member is gone the id
    is free until the next look (GROUP_LOOK_SECONDS): a new process given that pid that started
    a group of its own in that time would get the look's signal (a pid wrap within the look,
    left as is). A group left with only zombies (their parents outside it have not reaped
    them) counts as empty: they run nothing (``is_zombie_state``, the guard's rule too).

    macOS refuses a signal (``PermissionError``) to a group whose members are all ending
    (zombies until their new parent reaps them): the group is looked at again until it is gone.

    Args:
        process: The child, already reaped (its process group leader).
        killed: Whether the leader was stopped with SIGKILL.
        sleep: Sleeps between looks (None: ``glitchygames.clock.raw_sleep``).

    Raises:
        ProcessGroupSurvivedError: If the group is not gone a grace after it was first killed.

    """
    # Resolved at call time: this module imports nothing from the engine when imported (the
    # pytest plugin imports it at configuration time), and a test's patch on the clock applies
    from glitchygames import clock

    sleep = sleep or clock.raw_sleep
    looks_in_a_grace = max(1, round(STOP_GRACE_SECONDS / GROUP_LOOK_SECONDS))
    gentle_looks = 0 if killed else looks_in_a_grace
    for look in range(gentle_looks + looks_in_a_grace):
        if look == gentle_looks and gentle_looks:
            # A member still tearing down after the gentle stop loses its cleanup from here on:
            # named, so a test's child left running by it points here
            LOG.warning(
                'Process group %d still has processes a grace after the gentle stop; killing: %s',
                process.pid,
                _describe(members=_list_group(group=process.pid)),
            )
        try:
            os.killpg(process.pid, signal.SIGKILL if look >= gentle_looks else 0)
        except ProcessLookupError:
            return
        except PermissionError:
            pass
        sleep(GROUP_LOOK_SECONDS)
    members = _list_group(group=process.pid)
    living = [member for member in members if not is_zombie_state(member.state)]
    if members and not living:
        # Only zombies whose parents have not reaped them (a parent outside the group): they
        # run nothing, so nothing of the group survived
        return
    message = (
        f'Process group {process.pid} still has processes a grace after SIGKILL: '
        f'{_describe(members=living)}'
    )
    raise ProcessGroupSurvivedError(message)


def _list_group(*, group: int) -> list[GroupMember]:
    """List the processes in a process group (``ps``: pid, state, command line).

    Returns:
        The members, in ``ps``'s order; none when ``ps`` lists none (or fails).

    """
    listing = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - /bin/ps with fixed arguments, as an argument list (no shell)
        [PROCESS_LISTER, '-A', '-ww', '-o', 'pid=,pgid=,stat=,command='],
        capture_output=True,
        text=True,
        check=False,
    )
    members: list[GroupMember] = []
    for line in listing.stdout.splitlines():
        fields = line.split(None, GROUP_LISTING_FIELDS - 1)
        if len(fields) == GROUP_LISTING_FIELDS and fields[1] == str(group):
            members.append(GroupMember(pid=int(fields[0]), state=fields[2], command=fields[3]))
    return members


def _describe(*, members: list[GroupMember]) -> str:
    """Name processes for a message: each one's pid and command line.

    Returns:
        "pid command" for each, joined by "; ", or "none listed".

    """
    return '; '.join(f'{member.pid} {member.command}' for member in members) or 'none listed'


def _signal_the_group(*, process: subprocess.Popen[str], signal_number: int) -> bool:
    """Signal a running child's process group (POSIX), unless the child ended meanwhile.

    A child that is ending after ``stop_command`` asked whether it runs (exiting, or a zombie
    until reaped): macOS then answers a signal to its group with EPERM (``PermissionError``),
    even before ``poll()`` can see the exit, and any POSIX system answers ESRCH
    (``ProcessLookupError``) for a group already gone. Either is no failure to stop it, when
    the child ends within ``STOP_GRACE_SECONDS``: it is waited for and reaped here.

    Args:
        process: The child (its process group leader).
        signal_number: The signal.

    Returns:
        True when the group was signalled; False when the child was ending (it is reaped).

    Raises:
        PermissionError: If the signal is refused and the child does not end in time.
        ProcessLookupError: If the group is gone and the child does not end in time.

    """
    try:
        os.killpg(process.pid, signal_number)
    except (PermissionError, ProcessLookupError) as refusal:
        try:
            process.wait(timeout=STOP_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            raise refusal from None
        return False
    return True
