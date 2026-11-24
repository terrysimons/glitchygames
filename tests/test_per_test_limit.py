"""A test ended at its per-test limit leaves no child running (tests/per_test_limit.py)."""

from __future__ import annotations

import ast
import os
import signal
import sys
import textwrap
import time
from pathlib import Path

import pytest

from glitchygames.process import OutputCapture, run_command

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The inner run's limit: long enough for its test to start its child and record it
INNER_LIMIT_SECONDS = 3
INNER_RUN_TIMEOUT_SECONDS = 120.0
WAIT_SECONDS = 30.0
POLL_SECONDS = 0.1
GIT_TIMEOUT_SECONDS = 60.0
# The test files whose waits are checked against the native run's per-test limit
TEST_FILE_GLOBS = ('tests/*.py', 'src/*/*/tests/*.py')
# Timeouts at or past the limit that are not a test's wait on a child, by file and name (a
# constant, or the called function of a ``timeout=`` argument), each with why
NOT_A_TESTS_WAIT_ON_A_CHILD = {
    ('tests/driver_comparison.py', 'NATIVE_RUN_TIMEOUT_SECONDS'): (
        'the whole native run, waited on by the comparison outside any test'
    ),
    ('tests/driver_comparison.py', 'IMAGE_RUN_TIMEOUT_SECONDS'): (
        'the image re-runs, waited on by the comparison outside any test'
    ),
    ('tests/replay/tools/test_settings.py', 'DEFAULT_GAME_TIMEOUT_SECONDS'): (
        'the settings default the test checks, not a wait'
    ),
    ('tests/test_generate_complexity_graphs.py', 'build.join'): (
        'a thread: a worker ended at the limit takes its threads with it'
    ),
}
# The stand-in: records its child as the harness's guard does, then waits on it in run_command
# (as the Mr. Muncher replay test did) far past the limit
TEST_WAITING_ON_A_CHILD = textwrap.dedent(
    """
    import os
    import sys
    from pathlib import Path

    from glitchygames.process import OutputCapture, run_command
    from tests.child_process_guard import ChildProcessGuard


    def test_waits_on_its_child_past_the_limit():
        guard = ChildProcessGuard()
        guard.start_recording()
        run_command(
            command=[
                sys.executable,
                '-c',
                'import os, sys, time; '
                'open(sys.argv[1], "w").write(str(os.getpid())); time.sleep(120)',
                os.environ['STAND_IN_CHILD_PID'],
            ],
            environment=os.environ,
            working_directory=Path.cwd(),
            capture_output=OutputCapture.APART,
            timeout_seconds=300,
        )
    """
)


# The stand-in's test goes on a moment after its child is stopped, so the plugin's line is
# written while the test's output is still captured
TEST_GOING_ON_AFTER_ITS_CHILD_IS_STOPPED = TEST_WAITING_ON_A_CHILD + textwrap.indent(
    textwrap.dedent(
        """
        import time

        time.sleep(1)
        """
    ),
    '    ',
)
# The inner run's conftest: pytest-timeout's end of the worker waits until the test has been
# reported, so the test's captured output is collected (and, as it passed, dropped) first.
# That is the order job 5171 met (bugs/2026-11-23-...): a line written into the capture was lost
DUMP_AFTER_THE_TEST_IS_REPORTED = textwrap.dedent(
    """
    import threading

    import pytest_timeout

    REPORTED = threading.Event()
    end_the_worker = pytest_timeout.timeout_timer


    def end_the_worker_once_reported(item, settings):
        REPORTED.wait(timeout=30)
        end_the_worker(item, settings)


    pytest_timeout.timeout_timer = end_the_worker_once_reported


    def pytest_runtest_logreport(report):
        if report.when == 'call':
            REPORTED.set()
    """
)


# Two tests, each shorter than the inner limit but together longer: a timer left running after
# the first would end the second
TESTS_ENDING_IN_TIME = textwrap.dedent(
    """
    import time


    def test_first():
        time.sleep(2)


    def test_second():
        time.sleep(2)
    """
)


def process_exists(*, pid: int) -> bool:
    """Tell whether a process still exists.

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


@pytest.mark.skipif(sys.platform == 'win32', reason='the guard records children on POSIX only')
def test_a_test_ended_at_its_limit_has_its_child_stopped_first(tmp_path):
    """The worker still ends at the limit, and the child it waited on is gone with it.

    Without the plugin, pytest-timeout's ``os._exit`` left the child running with no parent
    (reproduced 2026-11-22: a ``sleep`` still running, parent 1, after the run had exited).
    """
    (tmp_path / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    (tmp_path / 'test_stand_in.py').write_text(TEST_WAITING_ON_A_CHILD, encoding='utf-8')
    child_pid_path = tmp_path / 'child.pid'

    finished = run_command(
        command=[
            *inner_run_arguments(directory=tmp_path, test_file=tmp_path / 'test_stand_in.py'),
            '-n',
            '1',
        ],
        environment={**inner_run_environment(), 'STAND_IN_CHILD_PID': str(child_pid_path)},
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.TOGETHER,
        timeout_seconds=INNER_RUN_TIMEOUT_SECONDS,
    )
    child_pid = int(child_pid_path.read_text(encoding='utf-8'))
    try:
        deadline = time.monotonic() + WAIT_SECONDS
        while process_exists(pid=child_pid) and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)

        assert "worker 'gw0' crashed" in finished.stdout, finished.stdout
        assert not process_exists(pid=child_pid), finished.stdout
        assert f'ran past its {INNER_LIMIT_SECONDS} s limit; its children, stopped' in (
            finished.stdout
        )
    finally:
        if process_exists(pid=child_pid):
            os.kill(child_pid, signal.SIGKILL)


@pytest.mark.skipif(sys.platform == 'win32', reason='the guard records children on POSIX only')
def test_the_line_naming_the_stopped_children_survives_the_tests_own_capture(tmp_path):
    """The line goes to the run's own standard error, never into the test's captured output.

    Written while the test still captured (pytest moves descriptor 2 to its file then), it
    reached the terminal only when pytest-timeout dumped that capture before the test's report
    collected it: job 5171 lost it, and a Linux container lost it in 6 of 6 plain runs.
    """
    (tmp_path / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    (tmp_path / 'conftest.py').write_text(DUMP_AFTER_THE_TEST_IS_REPORTED, encoding='utf-8')
    test_file = tmp_path / 'test_stand_in.py'
    test_file.write_text(TEST_GOING_ON_AFTER_ITS_CHILD_IS_STOPPED, encoding='utf-8')
    child_pid_path = tmp_path / 'child.pid'

    finished = run_command(
        command=[*inner_run_arguments(directory=tmp_path, test_file=test_file), '-n', '1'],
        environment={**inner_run_environment(), 'STAND_IN_CHILD_PID': str(child_pid_path)},
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.TOGETHER,
        timeout_seconds=INNER_RUN_TIMEOUT_SECONDS,
    )
    child_pid = int(child_pid_path.read_text(encoding='utf-8'))
    try:
        assert f'ran past its {INNER_LIMIT_SECONDS} s limit; its children, stopped' in (
            finished.stdout
        ), finished.stdout
    finally:
        if process_exists(pid=child_pid):
            os.kill(child_pid, signal.SIGKILL)


def inner_run_environment() -> dict[str, str]:
    """This process's environment without ``PYTEST_ADDOPTS``, as pytester removes it.

    An inherited ``-s`` would turn the inner run's capture off, and the line under test would
    then reach the terminal however it was written.

    Returns:
        The environment for an inner run.

    """
    return {name: value for name, value in os.environ.items() if name != 'PYTEST_ADDOPTS'}


def inner_run_arguments(*, directory: Path, test_file: Path) -> list[str]:
    """Build a pytest run of ``test_file`` with this plugin and the inner per-test limit.

    Returns:
        The command.

    """
    return [
        sys.executable,
        '-m',
        'pytest',
        '-c',
        str(directory / 'pytest.ini'),
        '--rootdir',
        str(directory),
        '-p',
        'no:cacheprovider',
        '-p',
        'tests.per_test_limit',
        f'--timeout={INNER_LIMIT_SECONDS}',
        '--timeout-method=thread',
        str(test_file),
    ]


def test_tests_that_end_in_time_have_their_timers_cancelled(tmp_path):
    """Each test's timer is cancelled when it ends: two in a row outlast one limit and pass."""
    (tmp_path / 'pytest.ini').write_text('[pytest]\n', encoding='utf-8')
    test_file = tmp_path / 'test_in_time.py'
    test_file.write_text(TESTS_ENDING_IN_TIME, encoding='utf-8')

    finished = run_command(
        command=inner_run_arguments(directory=tmp_path, test_file=test_file),
        environment=inner_run_environment(),
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.TOGETHER,
        timeout_seconds=INNER_RUN_TIMEOUT_SECONDS,
    )

    assert finished.returncode == 0, finished.stdout
    assert '2 passed' in finished.stdout, finished.stdout


def long_waits(*, source: str, limit: float) -> list[tuple[str, float]]:
    """Find the timeouts in a module at or past ``limit``.

    A timeout is a numeric constant whose name holds TIMEOUT, or a numeric ``timeout`` or
    ``timeout_seconds`` argument (named by the function called).

    Returns:
        Each one's name and seconds, in the source's order.

    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            found.extend(
                (node.lineno, target.id, node.value.value)
                for target in node.targets
                if isinstance(target, ast.Name) and 'TIMEOUT' in target.id
            )
        elif isinstance(node, ast.Call):
            found.extend(
                (node.lineno, ast.unparse(node.func), keyword.value.value)
                for keyword in node.keywords
                if keyword.arg in {'timeout', 'timeout_seconds'}
                and isinstance(keyword.value, ast.Constant)
            )
    return [
        (name, seconds)
        for _line, name, seconds in sorted(found)
        if isinstance(seconds, int | float) and not isinstance(seconds, bool) and seconds >= limit
    ]


def test_every_tests_wait_on_a_child_ends_before_the_native_runs_limit():
    """A test's own timeout stops and reaps its child; the per-test limit must not come first."""
    import noxfile

    listed = run_command(
        command=['git', 'ls-files', '-z', '--', *TEST_FILE_GLOBS],
        environment=os.environ,
        working_directory=PROJECT_ROOT,
        capture_output=OutputCapture.APART,
        timeout_seconds=GIT_TIMEOUT_SECONDS,
    )
    found = {
        (name, wait): seconds
        for name in listed.stdout.split('\0')
        if name
        for wait, seconds in long_waits(
            source=(PROJECT_ROOT / name).read_text(encoding='utf-8'),
            limit=noxfile._NATIVE_RUN_TIMEOUT_SECONDS,
        )
    }

    assert set(found) == set(NOT_A_TESTS_WAIT_ON_A_CHILD), found


def test_a_wait_at_the_limit_is_found_and_one_below_is_not():
    """Constants and arguments, at the limit and below it."""
    source = (
        'CHILD_TIMEOUT_SECONDS = 360.0\n'
        'SHORT_TIMEOUT_SECONDS = 359\n'
        'run(timeout_seconds=400)\n'
        'child.wait(timeout=10)\n'
        'NOT_A_WAIT = 999\n'
    )

    assert long_waits(source=source, limit=360) == [
        ('CHILD_TIMEOUT_SECONDS', 360.0),
        ('run', 400),
    ]
