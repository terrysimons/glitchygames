"""Reproduce the macOS killpg race: a process group killed as it forks can keep a member running.

bugs/2026-11-20-killpg-misses-a-process-forked-during-it-on-macos.md. Each trial starts a shell
in a session of its own (as the Ansible lock tests start setup.sh, whose fake curl logs its call,
then forks ``sleep``) that logs a line and then forks MEMBERS ``sleep`` processes in the
background, one after another; it waits for the log line, stops the group while the shell is
forking, and waits for the child's pipe to close. A member left running holds it open: the trial
counts an escape and names what is left. The lock tests' single fork made the window narrow (a
few trials in a hundred, and none when the timing shifts); forking MEMBERS times keeps the kill
inside a fork on most trials.

Usage (from the repository root, POSIX):

    uv run python -m scripts.reproduce_killpg_fork_race MODE [--trials N]

MODE, how the group is stopped:
    killpg          ``os.killpg(SIGKILL)`` once, as the lock tests did before the fix: on macOS
                    about a third of the trials leave a forked ``sleep`` running (0 on Linux)
    stop-command    ``process.stop_command(first_signal=SIGKILL)``, which kills whatever the
                    group signal missed: no trial leaves anything

Each trial that leaves something prints ``trial N: escaped`` and the members it found; the last
line counts the escapes. Exit status: SUCCESS (0) when no trial left anything running,
REPLAY_DIVERGED (1, the "found something" code) when one did.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import select
import signal
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from tests.child_process_guard import list_processes

from glitchygames import clock
from glitchygames.exit_codes import ExitCode
from glitchygames.process import start_command, stop_command

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.process import RunningProcess

DESCRIPTION = 'Stop a process group as it forks, and count the members left running (macOS).'
MODES = ('killpg', 'stop-command')
# How long a trial waits for its pipe to close once the group was stopped (the lock tests' wait)
PIPES_CLOSE_SECONDS = 10.0
# How long each forked member would run if nothing stopped it, and how many the shell forks
MEMBER_SECONDS = 30
MEMBERS = 200
POLL_SECONDS = 0.001


def stop_the_group(*, mode: str, child: RunningProcess[str]) -> None:
    """Stop the child's process group the way MODE names, and reap the child."""
    if mode == 'killpg':
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
        child.wait()
    else:
        stop_command(process=child, first_signal=signal.SIGKILL)


def pipe_closed(*, read_end: int, within: float) -> bool:
    """Read the child's output pipe until every writer has closed it, waiting at most WITHIN.

    The child writes nothing, so each wait either sees the pipe's end or runs out. Waits use
    ``select``'s own timeout, not a clock (a test's clock may be a stand-in that never moves).

    Returns:
        True when the pipe reached its end (no process holds it any more).

    """
    readable, _, _ = select.select([read_end], [], [], within)
    while readable:
        if not os.read(read_end, 4096):
            return True
        readable, _, _ = select.select([read_end], [], [], within)
    return False


def run_trial(*, mode: str) -> list[str]:
    """Start the group, stop it as it forks, and name what is left in it.

    Returns:
        Each member left running ("pid command"); empty when the pipe closed in time.

    """
    with tempfile.TemporaryDirectory() as folder:
        log = Path(folder) / 'log'
        read_end, write_end = os.pipe()
        try:
            with os.fdopen(write_end, 'w', encoding='utf-8') as output:
                child = start_command(
                    command=[
                        '/bin/sh',
                        '-c',
                        (
                            f'printf "started\\n" >> "$1"; i=0; while [ "$i" -lt {MEMBERS} ]; do '
                            f'sleep {MEMBER_SECONDS} & i=$((i + 1)); done; wait'
                        ),
                        'sh',
                        str(log),
                    ],
                    environment=os.environ,
                    output=output,
                )
            while not (log.exists() and log.stat().st_size):
                clock.raw_sleep(POLL_SECONDS)
            stop_the_group(mode=mode, child=child)
            if pipe_closed(read_end=read_end, within=PIPES_CLOSE_SECONDS):
                return []
            left = [
                f'{listed.pid} {listed.command}'
                for listed in list_processes()
                if listed.pgid == child.pid
            ]
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            return left or ['(the pipe stayed open, but nothing was listed in the group)']
        finally:
            os.close(read_end)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the trials and count the escapes.

    Returns:
        The exit status (see the module docstring).

    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('mode', choices=MODES)
    parser.add_argument('--trials', type=int, default=100, help='how many times (default 100)')
    arguments = parser.parse_args(argv)
    escapes = 0
    for trial in range(1, arguments.trials + 1):
        left = run_trial(mode=arguments.mode)
        if left:
            escapes += 1
            sys.stdout.write(f'trial {trial}: escaped\n')
            for member in left:
                sys.stdout.write(f'  left running: {member}\n')
    sys.stdout.write(
        f'{arguments.mode}: {escapes} of {arguments.trials} trials left a member running\n'
    )
    return ExitCode.REPLAY_DIVERGED if escapes else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
