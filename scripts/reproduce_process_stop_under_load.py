"""Reproduce the process-stop tests that failed once in a full run, the way they ran there.

bugs/2026-11-20-process-stop-tests-failed-under-load.md: three tests that start real child
processes and check how they stop failed once in a full local run (xdist, 11 workers) and passed
alone, 80 of 80, even at a load average of 155. So this runs their three files whole, repeated,
under ``-n auto`` as the suite does, and keeps what each round leaves to read:

- the round's pytest output and JUnit report;
- its ``--basetemp``, so each test's ``tmp_path`` survives: the nested pytest run's log
  (``native.log``) and ``glitchygames record-trace``'s output (``command-output.txt``). It is a
  fresh folder outside the repository (``tempfile.mkdtemp``), moved into the round's folder only
  when the round fails: three of tests/test_driver_comparison.py's end-to-end tests fail when
  their temporary folder is inside the repository
  (bugs/2026-11-20-driver-comparison-end-to-end-tests-fail-inside-the-repository.md);
- the probe's event log (``events.jsonl``, scripts/process_stop_probe/sitecustomize.py): every
  signal any Python process of the round sent (sender, target, signal, where in the code),
  every Python-level handler installed and called, every process's start and normal exit.

A round that passes keeps only its output and events (its ``--basetemp`` is removed); a failing
round keeps everything. Rounds stop at ``--rounds`` or once ``--minutes`` have passed (the
round under way is stopped as Ctrl-C stops it). After each round every process naming its folder
or its ``--basetemp`` is killed (``tests.child_process_guard.sweep_processes_naming``) and
listed.

Usage (from the repository root, POSIX):

    uv run python -m scripts.reproduce_process_stop_under_load [--rounds N] [--minutes M]
        [--workers W] [--output DIRECTORY]

Each round also checks that the probe loaded in a test's nested pytest run (a start event naming
a file under the round's ``--basetemp``); without that its log would prove nothing. Logging
before each ``os.kill`` changes timing slightly, so a failure rate with the probe is not
necessarily the rate without it.

Exit status: SUCCESS (0) when every round passed, REPLAY_DIVERGED (1, the "found something"
code) when one failed, INTERNAL_ERROR (70) when the probe did not load in a nested run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

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


def round_command(*, round_directory: Path, basetemp: Path, workers: str) -> list[str]:
    """Build one round's pytest command.

    Args:
        round_directory: Where the round keeps its files.
        basetemp: The round's pytest ``--basetemp`` (outside the repository).
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
        str(basetemp),
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


def probe_reached_a_nested_run(*, round_directory: Path, basetemp: Path) -> bool:
    """Tell whether the probe logged the start of a nested pytest run of the round.

    An empty log is evidence only once the probe is known to have loaded where it matters: a
    test's nested pytest run (its command names the test's ``pytest.ini``, under the round's
    ``--basetemp``). A ``sitecustomize`` earlier on the path, or a child that resets PYTHONPATH,
    would leave it out silently.

    Args:
        round_directory: The round's folder, which holds the probe's log.
        basetemp: The round's pytest ``--basetemp``.

    Returns:
        True when some start event's command names a file under the round's basetemp.

    """
    events = round_directory / 'events.jsonl'
    if not events.exists():
        return False
    basetemp_text = str(basetemp)
    for line in events.read_text(encoding='utf-8').splitlines():
        event = json.loads(line)
        command = event.get('command') if event.get('kind') == 'start' else None
        if not isinstance(command, list):
            continue
        words = cast('list[object]', command)
        if any(basetemp_text in str(word) for word in words):
            return True
    return False


def run_round(
    *, round_directory: Path, basetemp: Path, workers: str, deadline: float
) -> int | None:
    """Run one round, stopping it as Ctrl-C does at the deadline.

    Args:
        round_directory: Where the round keeps its files (made here).
        basetemp: The round's pytest ``--basetemp`` (outside the repository).
        workers: xdist's ``-n`` value.
        deadline: The ``time.monotonic()`` reading the round must end by.

    Returns:
        The round's exit code, or None when the deadline stopped it.

    """
    round_directory.mkdir(parents=True)
    with (round_directory / 'pytest.log').open('w', encoding='utf-8') as output:
        running = start_command(
            command=round_command(
                round_directory=round_directory, basetemp=basetemp, workers=workers
            ),
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
        basetemp = Path(tempfile.mkdtemp(prefix='process-stop-round-')) / 'basetemp'
        status = run_round(
            round_directory=round_directory,
            basetemp=basetemp,
            workers=arguments.workers,
            deadline=deadline,
        )
        survivors = [
            *sweep_processes_naming(directory=round_directory),
            *sweep_processes_naming(directory=basetemp),
        ]
        probed = probe_reached_a_nested_run(round_directory=round_directory, basetemp=basetemp)
        outcome = 'stopped at the deadline' if status is None else f'exit {status}'
        sys.stdout.write(
            f'round {round_number}: {outcome}, {len(survivors)} left running, '
            f'probe {"in" if probed else "MISSING from"} the nested runs\n'
        )
        for survivor in survivors:
            sys.stdout.write(f'  left running: {survivor}\n')
        if status is None:
            break
        if not probed:
            sys.stdout.write('the probe did not load in a nested run: its log proves nothing\n')
            return ExitCode.INTERNAL_ERROR
        if status == 0 and not survivors:
            shutil.rmtree(basetemp.parent, ignore_errors=True)
        else:
            shutil.move(basetemp, round_directory / 'basetemp')
            failed_rounds.append(round_number)
    sys.stdout.write(f'failed rounds: {failed_rounds or "none"} (kept in {arguments.output})\n')
    return ExitCode.REPLAY_DIVERGED if failed_rounds else ExitCode.SUCCESS


if __name__ == '__main__':
    sys.exit(main())
