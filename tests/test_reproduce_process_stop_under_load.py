"""Tests for the process-stop triage's reproducer and its probe.

The probe (scripts/process_stop_probe/sitecustomize.py) is checked in real processes, as the
reproducer runs it: a parent that terminates its child must log the send before the child logs
its receipt, with each process's start and exit.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from typing import TYPE_CHECKING

import pytest
from scripts import reproduce_process_stop_under_load as reproducer

from glitchygames.process import OutputCapture, run_command, start_command, stop_command
from tests.stoppable_children import SIGNALS_INTERRUPT_NO_SLEEP, WAIT_TO_BE_STOPPED

if TYPE_CHECKING:
    from pathlib import Path

needs_posix = pytest.mark.skipif(sys.platform == 'win32', reason='the probe logs POSIX signals')

# How long a test waits for a child to be ready or gone, how often it looks, and how long a
# ready child is given to reach its sleep
CHILD_WAIT_SECONDS = 10.0
STEP_SECONDS = 0.05
ASLEEP_SECONDS = 0.3
# A child that ends when terminated, once it has written the file it is given
CHILD_THAT_ENDS_WHEN_TERMINATED = (
    'import signal, sys\n'
    'from pathlib import Path\n'
    'signal.signal(signal.SIGTERM, lambda number, frame: sys.exit(0))\n'
    'Path(sys.argv[1]).write_text("ready")\n'
) + WAIT_TO_BE_STOPPED
# A parent that starts the child it is given, terminates it once its handler is in place, and
# waits for it
PARENT_TERMINATING_ITS_CHILD = """
import subprocess
import sys
from pathlib import Path

ready = Path(sys.argv[1])
child = subprocess.Popen([sys.executable, '-c', sys.argv[2], str(ready)])
while not ready.exists():
    pass
child.terminate()
child.wait()
"""


def probed_run(*, tmp_path: Path, log: Path | None) -> list[dict[str, object]]:
    """Run the terminating parent with the probe on PYTHONPATH, logging to ``log`` if given.

    Returns:
        The events logged, in order.

    """
    environment = {
        **os.environ,
        'PYTHONPATH': str(reproducer.PROBE_DIRECTORY),
    }
    environment.pop(reproducer.PROBE_LOG_VARIABLE, None)
    if log is not None:
        environment[reproducer.PROBE_LOG_VARIABLE] = str(log)
    result = run_command(
        command=[
            sys.executable,
            '-c',
            PARENT_TERMINATING_ITS_CHILD,
            str(tmp_path / 'ready'),
            CHILD_THAT_ENDS_WHEN_TERMINATED,
        ],
        environment=environment,
        timeout_seconds=60,
        capture_output=OutputCapture.APART,
    )
    assert result.returncode == 0, result.stderr
    if log is None or not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]


@needs_posix
def test_the_probe_logs_the_send_before_the_receipt_it_caused(tmp_path: Path):
    """Each process logs its start and exit; the parent's send precedes the child's receipt."""
    events = probed_run(tmp_path=tmp_path, log=tmp_path / 'events.jsonl')

    starts = [event for event in events if event['kind'] == 'start']
    parent, child = (event['pid'] for event in starts)
    kinds = [(event['kind'], event['pid']) for event in events if event['kind'] != 'handler']
    send = next(event for event in events if event['kind'] == 'send')
    assert send['pid'] == parent
    assert send['target'] == child
    assert send['signal'] == 15
    assert kinds.index(('send', parent)) < kinds.index(('receive', child))
    assert ('exit', child) in kinds
    assert ('exit', parent) in kinds
    # The whole command line, not the '-c' alone that sys.argv holds while site runs
    parent_command, child_command = (start['command'] for start in starts)
    assert parent_command == [
        sys.executable,
        '-c',
        PARENT_TERMINATING_ITS_CHILD,
        str(tmp_path / 'ready'),
        CHILD_THAT_ENDS_WHEN_TERMINATED,
    ]
    assert isinstance(child_command, list)
    assert child_command[0] == sys.executable


@needs_posix
def test_the_probe_does_nothing_without_its_log_variable(tmp_path: Path):
    """With no PROCESS_STOP_PROBE_LOG the processes run unprobed and nothing is written."""
    assert probed_run(tmp_path=tmp_path, log=None) == []
    assert list(tmp_path.iterdir()) in ([], [tmp_path / 'ready'])


@needs_posix
def test_the_probed_child_acts_on_a_signal_that_interrupts_no_sleep(tmp_path: Path):
    """A SIGTERM landing just before the child's sleep ends it at its next step, not after 60 s."""
    ready = tmp_path / 'ready'
    with (tmp_path / 'output.txt').open('w', encoding='utf-8') as output:
        child = start_command(
            command=[
                sys.executable,
                '-c',
                SIGNALS_INTERRUPT_NO_SLEEP + CHILD_THAT_ENDS_WHEN_TERMINATED,
                str(ready),
            ],
            environment=os.environ,
            output=output,
        )
        try:
            deadline = time.monotonic() + CHILD_WAIT_SECONDS
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(STEP_SECONDS)
            # Sent at once, the signal can land before the child reaches its wait, which proves
            # nothing: the child is given time to be asleep
            time.sleep(ASLEEP_SECONDS)
            child.terminate()
            returncode = child.wait(timeout=CHILD_WAIT_SECONDS)
        finally:
            stop_command(process=child, first_signal=signal.SIGKILL)

    assert returncode == 0


def test_a_round_runs_the_three_files_whole_under_xdist_keeping_its_temporary_files(
    tmp_path: Path,
):
    """The round's command runs every test file named, with the workers and the round's basetemp."""
    command = reproducer.round_command(
        round_directory=tmp_path, basetemp=tmp_path / 'outside' / 'basetemp', workers='4'
    )

    assert command[-len(reproducer.TEST_FILES) :] == list(reproducer.TEST_FILES)
    assert command[command.index('-n') + 1] == '4'
    assert command[command.index('--basetemp') + 1] == str(tmp_path / 'outside' / 'basetemp')
    assert command[command.index('-p') + 1] == 'no:randomly'


def test_a_rounds_processes_load_the_probe_and_log_into_the_round(tmp_path: Path):
    """The probe's folder leads PYTHONPATH, ahead of any the caller had, and logs to the round."""
    environment = reproducer.round_environment(round_directory=tmp_path)

    assert environment['PYTHONPATH'].split(os.pathsep)[0] == str(reproducer.PROBE_DIRECTORY)
    assert environment[reproducer.PROBE_LOG_VARIABLE] == str(tmp_path / 'events.jsonl')


def test_a_round_counts_as_probed_only_once_a_nested_run_logged_its_start(tmp_path: Path):
    """An empty or outer-only log is not evidence; a nested run under the basetemp is."""
    events = tmp_path / 'events.jsonl'

    basetemp = tmp_path / 'outside' / 'basetemp'
    nothing_logged = reproducer.probe_reached_a_nested_run(
        round_directory=tmp_path, basetemp=basetemp
    )
    events.write_text(
        json.dumps({'kind': 'start', 'pid': 1, 'command': ['python', '-m', 'pytest']}) + '\n',
        encoding='utf-8',
    )
    outer_only = reproducer.probe_reached_a_nested_run(round_directory=tmp_path, basetemp=basetemp)
    nested = ['python', '-m', 'pytest', '-c', str(basetemp / 'test0' / 'pytest.ini')]
    with events.open('a', encoding='utf-8') as log:
        log.write(json.dumps({'kind': 'start', 'pid': 2, 'command': nested}) + '\n')

    assert nothing_logged is False
    assert outer_only is False
    assert reproducer.probe_reached_a_nested_run(round_directory=tmp_path, basetemp=basetemp)
