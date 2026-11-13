"""Reproduce BUGS.md #275: stop a pytest run mid-test, then list what its test left running.

A two-worker pytest run of one test (by default the crash-boundary test that once left a
``glitchygames record-trace`` tool and its game running) is started with a temporary directory
of its own, stopped at a chosen moment in a chosen way, and, once it has ended, every process
naming that directory is reported by its command line and killed. Each row of the triage's table
(plans/2026-11-11-orphaned-test-processes.md) is one invocation.

Usage (from the repository root, POSIX):

    uv run python -m scripts.reproduce_orphaned_test_processes MODE WHEN [--test NODE]
        [--trials N]

MODE, how the run is stopped:
    stop-command    ``process.stop_command`` with its default SIGTERM to the run's group (how
                    the driver comparison stopped its native run before the fix)
    sigint-group    SIGINT to the run's group (Ctrl-C; ``stop_command(first_signal=SIGINT)``)
    sigterm-leader  SIGTERM to the pytest controller alone
    sigkill-worker  SIGKILL to one xdist worker (a crash or the OOM killer)

WHEN, the moment it is stopped:
    tool            once the test has started its child (a process in a session of its own
                    naming the run's temporary directory)
    game            once a file named ``child.pid`` appears in the run's temporary directory
                    (the crash-boundary test's game writes it)

Each trial prints ``trial N: M left running`` and one line per survivor. Exit status: SUCCESS
(0) when no trial left anything running, REPLAY_DIVERGED (1, the "found something" code) when
one did, INTERNAL_ERROR (70) when a run never reached the moment.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from tests.child_process_guard import list_processes, sweep_processes_naming

from glitchygames import clock
from glitchygames.exit_codes import ExitCode
from glitchygames.process import TimeoutExpired, start_command, stop_command

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.process import RunningProcess

DESCRIPTION = 'Stop a pytest run mid-test, then list what its test left running (BUGS.md #275).'
MODES = ('stop-command', 'sigint-group', 'sigterm-leader', 'sigkill-worker')
WHENS = ('tool', 'game')
DEFAULT_TEST = (
    'tests/replay/tools/test_command_crash_boundary.py::'
    'test_a_signal_stops_and_reaps_the_commands_child_and_exits_with_its_code[15]'
)
# The file the crash-boundary test's game writes when it starts (WHEN game)
GAME_STARTED_FILE_NAME = 'child.pid'
# How long a run may take to reach the moment, and to end once stopped
MOMENT_TIMEOUT_SECONDS = 120.0
END_TIMEOUT_SECONDS = 60.0
POLL_SECONDS = 0.05
# The section the run's controller prints when its sweep killed anything (tests/harness.py)
SWEPT_SECTION_TITLE = 'processes left running by this run (now killed)'


def run_command_line(*, test: str, basetemp: Path) -> list[str]:
    """The stopped run's command: two xdist workers, dummy drivers' settings, no coverage.

    Returns:
        The command.

    """
    return [
        sys.executable,
        '-m',
        'pytest',
        test,
        '-n',
        '2',
        '-p',
        'no:randomly',
        '-p',
        'no:cacheprovider',
        '--no-cov',
        '-q',
        f'--basetemp={basetemp}',
    ]


def reached(*, when: str, run: RunningProcess[str], temporary: Path) -> bool:
    """Tell whether the run's test has reached the moment ``when``.

    Returns:
        True once it has.

    """
    if when == 'game':
        return any(temporary.rglob(GAME_STARTED_FILE_NAME))
    return any(
        process.pgid != run.pid and str(temporary) in process.command
        for process in list_processes()
    )


def worker_running_the_test(*, run: RunningProcess[str], temporary: Path) -> int | None:
    """Return the xdist worker running the test: the one whose child names the directory.

    Returns:
        Its pid, or None when no worker has such a child (the test started none yet).

    """
    processes = list_processes()
    workers = {
        process.pid for process in processes if process.ppid == run.pid and process.pgid == run.pid
    }
    for process in processes:
        if process.ppid in workers and str(temporary) in process.command:
            return process.ppid
    return None


def stop(*, mode: str, run: RunningProcess[str], temporary: Path) -> None:
    """Stop the run as ``mode`` says, then wait for it to end (killing it if it does not)."""
    if mode == 'stop-command':
        stop_command(process=run)
    elif mode == 'sigint-group':
        os.killpg(run.pid, signal.SIGINT)
    elif mode == 'sigterm-leader':
        os.kill(run.pid, signal.SIGTERM)
    else:
        worker = worker_running_the_test(run=run, temporary=temporary)
        if worker is not None:
            os.kill(worker, signal.SIGKILL)
    try:
        run.wait(timeout=END_TIMEOUT_SECONDS)
    except TimeoutExpired:
        stop_command(process=run)


class TrialResult(BaseModel):
    """What one trial found."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # Left running after the run ended (now killed by this script)
    left_running: list[str]
    # Killed by the stopped run's own controller at its end (tests/harness.py's sweep), as its
    # log lists them
    swept_by_the_run: list[str]


def swept_by_the_run(*, log_text: str) -> list[str]:
    """Return the processes the run's controller swept, from its terminal summary's section.

    Returns:
        Their lines (``pid N: command``), or none when the run printed no such section.

    """
    lines = log_text.splitlines()
    starts = [index for index, line in enumerate(lines) if SWEPT_SECTION_TITLE in line]
    if not starts:
        return []
    swept: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if not line.startswith('pid '):
            break
        swept.append(line)
    return swept


def run_trial(*, mode: str, when: str, test: str) -> TrialResult | None:
    """Run, stop and sweep one trial.

    Returns:
        What it found, or None when the run never reached the moment.

    """
    with tempfile.TemporaryDirectory(prefix='glitchygames-orphans-') as directory:
        temporary = Path(directory)
        basetemp = temporary / 'basetemp'
        environment = {
            **os.environ,
            'TMPDIR': str(temporary),
            'SDL_VIDEODRIVER': 'dummy',
            'SDL_AUDIODRIVER': 'dummy',
        }
        with (temporary / 'run.log').open('w', encoding='utf-8') as log:
            run = start_command(
                command=run_command_line(test=test, basetemp=basetemp),
                environment=environment,
                output=log,
            )
            try:
                deadline = clock.raw_counter_seconds() + MOMENT_TIMEOUT_SECONDS
                while not reached(when=when, run=run, temporary=temporary):
                    if run.poll() is not None or clock.raw_counter_seconds() > deadline:
                        return None
                    clock.raw_sleep(POLL_SECONDS)
                stop(mode=mode, run=run, temporary=temporary)
            finally:
                stop_command(process=run)
        left_running = [process.command for process in sweep_processes_naming(directory=temporary)]
        return TrialResult(
            left_running=left_running,
            swept_by_the_run=swept_by_the_run(
                log_text=(temporary / 'run.log').read_text(encoding='utf-8')
            ),
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the trials and print what each left running.

    Returns:
        The exit status (see the module docstring).

    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('mode', choices=MODES)
    parser.add_argument('when', choices=WHENS)
    parser.add_argument('--test', default=DEFAULT_TEST, help='the test node to run and stop')
    parser.add_argument('--trials', type=int, default=1, help='how many times (default 1)')
    arguments = parser.parse_args(argv)
    found = False
    for trial in range(1, arguments.trials + 1):
        result = run_trial(mode=arguments.mode, when=arguments.when, test=arguments.test)
        if result is None:
            print(f'trial {trial}: the run never reached {arguments.when!r}')  # ruff: ignore[print] - the tool's output
            return ExitCode.INTERNAL_ERROR
        print(  # ruff: ignore[print] - the tool's output
            f'trial {trial}: {len(result.left_running)} left running, '
            f'{len(result.swept_by_the_run)} swept by the run itself'
        )
        for command in result.left_running:
            print(f'  left running: {command}')  # ruff: ignore[print] - the tool's output
        for line in result.swept_by_the_run:
            print(f'  swept by the run: {line}')  # ruff: ignore[print] - the tool's output
        found = found or bool(result.left_running)
    return ExitCode.REPLAY_DIVERGED if found else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
