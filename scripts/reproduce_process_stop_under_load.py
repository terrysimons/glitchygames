"""Reproduce the process-stop tests that failed once in a full run, the way they ran there.

bugs/2026-11-20-process-stop-tests-failed-under-load.md: three tests that start real child
processes and check how they stop failed once in a full local run (xdist, 11 workers) and passed
alone, 80 of 80, even at a load average of 155. So this runs their three files whole, repeated,
under ``-n auto`` as the suite does, and keeps what each round leaves to read:

- the round's pytest output and JUnit report;
- its ``--basetemp``, so each test's ``tmp_path`` survives: the nested pytest run's log
  (``native.log``) and ``glitchygames record-trace``'s output (``command-output.txt``);
- the probe's event log (``events.jsonl``, scripts/process_stop_probe/sitecustomize.py): every
  signal any Python process of the round sent (sender, target, signal, where in the code),
  every Python-level handler installed and called, every process's start and normal exit.

A round that passes keeps only its output and events (its ``--basetemp`` is removed); a failing
round keeps everything. Rounds stop at ``--rounds`` or once ``--minutes`` have passed (the
round under way is stopped as Ctrl-C stops it). After each round every process naming its folder
is killed (``tests.child_process_guard.sweep_processes_naming``) and listed.

Usage (from the repository root, POSIX):

    uv run python -m scripts.reproduce_process_stop_under_load [--rounds N] [--minutes M]
        [--workers W] [--output DIRECTORY]

Exit status: SUCCESS (0) when every round passed, REPLAY_DIVERGED (1, the "found something"
code) when one failed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
import time
from pathlib import Path

from tests.child_process_guard import sweep_processes_naming

from glitchygames.exit_codes import ExitCode
from glitchygames.process import TimeoutExpired, start_command, stop_command

DESCRIPTION = 'Run the process-stop tests whole under xdist, repeated, logging who signals whom.'
# The three tests' files, run whole as the suite runs them
TEST_FILES = (
    'tests/test_driver_comparison.py',
    'tests/test_reproduce_orphaned_test_processes.py',
    'tests/replay/tools/test_command_crash_boundary.py',
)
PROBE_DIRECTORY = Path(__file__).resolve().parent / 'process_stop_probe'
PROBE_LOG_VARIABLE = 'PROCESS_STOP_PROBE_LOG'
DEFAULT_ROUNDS = 20
DEFAULT_MINUTES = 15.0
DEFAULT_OUTPUT = Path('build/process-stop-triage/under-xdist')
SECONDS_PER_MINUTE = 60.0


def round_command(*, round_directory: Path, workers: str) -> list[str]:
    """Build one round's pytest command.

    Args:
        round_directory: Where the round keeps its files.
        workers: xdist's ``-n`` value.

    Returns:
        The command.

    """
    return [
        sys.executable,
        '-m',
        'pytest',
        '--dummy-only',
        '--no-cov',
        '-p',
        'no:randomly',
        '-n',
        workers,
        '--basetemp',
        str(round_directory / 'basetemp'),
        '--junitxml',
        str(round_directory / 'junit.xml'),
        *TEST_FILES,
    ]


def round_environment(*, round_directory: Path) -> dict[str, str]:
    """Build one round's environment: the probe first on PYTHONPATH, logging to the round.

    Args:
        round_directory: Where the round keeps its files.

    Returns:
        The environment.

    """
    python_path = os.pathsep.join(
        part for part in (str(PROBE_DIRECTORY), os.environ.get('PYTHONPATH', '')) if part
    )
    return {
        **os.environ,
        'PYTHONPATH': python_path,
        PROBE_LOG_VARIABLE: str(round_directory / 'events.jsonl'),
    }


def run_round(*, round_directory: Path, workers: str, deadline: float) -> int | None:
    """Run one round, stopping it as Ctrl-C does at the deadline.

    Args:
        round_directory: Where the round keeps its files (made here).
        workers: xdist's ``-n`` value.
        deadline: The ``time.monotonic()`` reading the round must end by.

    Returns:
        The round's exit code, or None when the deadline stopped it.

    """
    round_directory.mkdir(parents=True)
    with (round_directory / 'pytest.log').open('w', encoding='utf-8') as output:
        running = start_command(
            command=round_command(round_directory=round_directory, workers=workers),
            environment=round_environment(round_directory=round_directory),
            output=output,
        )
        try:
            return running.wait(timeout=max(0.0, deadline - time.monotonic()))
        except TimeoutExpired:
            return None
        finally:
            stop_command(process=running, first_signal=signal.SIGINT)


def main(argv: list[str] | None = None) -> int:
    """Run the rounds and report each.

    Args:
        argv: The arguments (default: the command line's).

    Returns:
        The exit status.

    """
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('--rounds', type=int, default=DEFAULT_ROUNDS)
    parser.add_argument('--minutes', type=float, default=DEFAULT_MINUTES)
    parser.add_argument('--workers', default='auto')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    deadline = time.monotonic() + arguments.minutes * SECONDS_PER_MINUTE
    failed_rounds: list[int] = []
    for round_number in range(1, arguments.rounds + 1):
        if time.monotonic() >= deadline:
            break
        round_directory = arguments.output / f'round-{round_number:03d}'
        status = run_round(
            round_directory=round_directory, workers=arguments.workers, deadline=deadline
        )
        survivors = sweep_processes_naming(directory=round_directory)
        outcome = 'stopped at the deadline' if status is None else f'exit {status}'
        sys.stdout.write(f'round {round_number}: {outcome}, {len(survivors)} left running\n')
        for survivor in survivors:
            sys.stdout.write(f'  left running: {survivor}\n')
        if status is None:
            break
        if status == 0 and not survivors:
            shutil.rmtree(round_directory / 'basetemp', ignore_errors=True)
        else:
            failed_rounds.append(round_number)
    sys.stdout.write(f'failed rounds: {failed_rounds or "none"} (kept in {arguments.output})\n')
    return ExitCode.REPLAY_DIVERGED if failed_rounds else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
