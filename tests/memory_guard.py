"""Stop a test run that outgrows a memory limit, naming the test, before the kernel kills it.

CircleCI's Linux job (``resource_class: small``, 2 GB, serial) was killed with signal 9 when a
test ran the process out of memory (BUGS.md #235): the job log ended mid-test, with no test named
and no hint of what grew. This plugin is on only when ``GLITCHYGAMES_TEST_RSS_LIMIT_MB`` is set
(the Linux job sets 1600). A background thread samples the process's resident memory every
``SAMPLE_INTERVAL_SECONDS`` (``/proc/self/statm``'s resident pages), and each test's start and end
are checked too. Past the limit it stops the run (``os._exit``, ``LIMIT_EXIT_STATUS``) after
writing, to the real standard error, the test running then (with how much it grew since it
started) and the largest per-test increases so far. A per-test check alone would miss a spike
inside one test, which is what #235 was (1.7 GB to 4.7 GB in one benchmark), hence the thread.

Where ``/proc/self/statm`` cannot be read (macOS, Windows) the plugin does nothing, even with the
variable set: the limit is Linux's. Test tooling only: the thread is the honest choice in a
desktop test process, and the engine never imports this module (the browser build has no
threads, and nothing of the engine's web path may start one).

Registered in the root conftest.py's ``pytest_plugins``. Tests: tests/test_memory_guard.py.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Self

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

LIMIT_VARIABLE = 'GLITCHYGAMES_TEST_RSS_LIMIT_MB'
SAMPLE_INTERVAL_SECONDS = 0.25
# /proc/self/statm: sizes in pages; the second field is the resident set
STATM_PATH = Path('/proc/self/statm')
STATM_RESIDENT_FIELD = 1
BYTES_PER_MEGABYTE = 1024 * 1024
# The per-test increases named in the message
LARGEST_INCREASES_SHOWN = 5
# The run was stopped, as pytest's own status for an interrupted run
LIMIT_EXIT_STATUS = int(pytest.ExitCode.INTERRUPTED)
THREAD_NAME = 'memory-guard'

# The guard of this pytest run, when it is on
GUARD_KEY = pytest.StashKey['ResidentMemoryGuard']()


def _megabytes(byte_count: int) -> str:
    return f'{byte_count / BYTES_PER_MEGABYTE:.0f} MB'


class ResidentMemoryGuard:
    """Watches the resident memory and stops the run past a limit, naming the test."""

    def __init__(
        self: Self,
        *,
        limit_bytes: int,
        read_resident_bytes: Callable[[], int],
        stop: Callable[[str], None],
        interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        """Watch nothing yet: ``start`` starts the sampling thread.

        Args:
            limit_bytes: The resident memory the run may not pass.
            read_resident_bytes: Returns the process's resident memory now, in bytes.
            stop: Ends the run with the message (``stop_the_run`` in a real run; it does not
                return there).
            interval_seconds: How long the thread waits between samples.

        """
        self._limit_bytes = limit_bytes
        self._read_resident_bytes = read_resident_bytes
        self._stop = stop
        self._interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._current_test: str | None = None
        self._resident_at_test_start = 0
        # Each finished test's growth (resident at its end less at its start), by node ID
        self._increases: dict[str, int] = {}
        self._stopped = False
        self._finished = threading.Event()
        self._thread: threading.Thread | None = None

    def test_started(self: Self, *, nodeid: str) -> None:
        """Note the test now running and the memory it starts from, then check the limit.

        Args:
            nodeid: The test's node ID.

        """
        resident = self._read_resident_bytes()
        with self._lock:
            self._current_test = nodeid
            self._resident_at_test_start = resident
        self._check_resident(resident=resident)

    def test_finished(self: Self, *, nodeid: str) -> None:
        """Record how much the test grew the memory, then check the limit.

        Args:
            nodeid: The test's node ID.

        """
        resident = self._read_resident_bytes()
        with self._lock:
            self._increases[nodeid] = resident - self._resident_at_test_start
            self._current_test = None
        self._check_resident(resident=resident)

    def check(self: Self) -> bool:
        """Sample the memory and stop the run if it is past the limit.

        Returns:
            Whether the limit was passed (``stop`` was called).

        """
        return self._check_resident(resident=self._read_resident_bytes())

    def _check_resident(self: Self, *, resident: int) -> bool:
        if resident <= self._limit_bytes:
            return False
        with self._lock:
            # Once: the thread and a test's end may both see it
            if self._stopped:
                return True
            self._stopped = True
            message = self._message(resident=resident)
        self._stop(message)
        return True

    def _message(self: Self, *, resident: int) -> str:
        """Describe the run past its limit (called holding the lock).

        Returns:
            The message: the limit, the test running then, the largest increases so far.

        """
        if self._current_test is None:
            running = 'between tests'
        else:
            grown = resident - self._resident_at_test_start
            running = f'in {self._current_test} (+{_megabytes(grown)} since it started)'
        lines = [
            (
                f'{LIMIT_VARIABLE}: resident memory {_megabytes(resident)} passed the limit of '
                f'{_megabytes(self._limit_bytes)} {running}; the run was stopped'
            ),
        ]
        largest = sorted(self._increases.items(), key=lambda item: (-item[1], item[0]))
        if largest:
            lines.append('Largest increases by a finished test so far:')
            lines.extend(
                f'  +{_megabytes(increase)} {nodeid}'
                for nodeid, increase in largest[:LARGEST_INCREASES_SHOWN]
            )
        return '\n'.join(lines)

    def start(self: Self) -> None:
        """Start sampling on a daemon thread (until ``finish`` or the limit is passed)."""
        self._thread = threading.Thread(target=self._sample, name=THREAD_NAME, daemon=True)
        self._thread.start()

    def _sample(self: Self) -> None:
        while not self._finished.wait(self._interval_seconds):
            if self.check():
                return

    def sampling(self: Self) -> bool:
        """Tell whether this guard's sampling thread is running.

        Returns:
            True between ``start`` and the thread's end.

        """
        return self._thread is not None and self._thread.is_alive()

    def finish(self: Self) -> None:
        """Stop sampling and wait for the thread to end."""
        self._finished.set()
        if self._thread is not None:
            self._thread.join()


def statm_resident_reader(*, path: Path = STATM_PATH) -> Callable[[], int] | None:
    """Return a reader of this process's resident memory from ``/proc/self/statm``.

    Args:
        path: The statm file.

    Returns:
        The reader (bytes), or None where the file cannot be read (not Linux).

    """
    try:
        path.read_text(encoding='ascii')
    except OSError:
        return None
    page_bytes = os.sysconf('SC_PAGE_SIZE')

    def read_resident_bytes() -> int:
        return int(path.read_text(encoding='ascii').split()[STATM_RESIDENT_FIELD]) * page_bytes

    return read_resident_bytes


def guard_from_environment(
    *,
    environment: Mapping[str, str],
    read_resident_bytes: Callable[[], int] | None,
    stop: Callable[[str], None],
) -> ResidentMemoryGuard | None:
    """Return the guard ``GLITCHYGAMES_TEST_RSS_LIMIT_MB`` asks for, or None when it is off.

    Args:
        environment: The process's environment.
        read_resident_bytes: The memory reader, or None where none works.
        stop: Ends the run with a message.

    Returns:
        The guard (not started), or None when the variable is unset or empty, or there is no
        reader.

    Raises:
        pytest.UsageError: If the variable is set to anything but a positive whole number.

    """
    value = environment.get(LIMIT_VARIABLE, '').strip()
    if not value or read_resident_bytes is None:
        return None
    if not value.isdigit() or int(value) == 0:
        message = f'{LIMIT_VARIABLE} must be a positive whole number of megabytes, not {value!r}'
        raise pytest.UsageError(message)
    return ResidentMemoryGuard(
        limit_bytes=int(value) * BYTES_PER_MEGABYTE,
        read_resident_bytes=read_resident_bytes,
        stop=stop,
    )


def stop_the_run(*, config: pytest.Config, message: str) -> None:
    """Write the message to the real standard error and end the process at once.

    pytest captures file descriptor 2 during a test, so the capture is suspended first (as its
    debugger support does), or the message would go to a capture file nobody reads. ``os._exit``:
    the thread cannot raise into the test, and memory is about to run out.

    Args:
        config: The run's configuration (for its capture manager).
        message: What passed the limit, and where.

    """
    capture = config.pluginmanager.get_plugin('capturemanager')
    if capture is not None:
        capture.suspend_global_capture(in_=False)
    sys.stderr.write(f'\n{message}\n')
    sys.stderr.flush()
    os._exit(LIMIT_EXIT_STATUS)


def pytest_configure(config: pytest.Config) -> None:
    """Start the guard when ``GLITCHYGAMES_TEST_RSS_LIMIT_MB`` is set and the memory is readable."""

    def stop(message: str) -> None:
        stop_the_run(config=config, message=message)

    guard = guard_from_environment(
        environment=os.environ,
        read_resident_bytes=statm_resident_reader(path=STATM_PATH),
        stop=stop,
    )
    if guard is None:
        return
    config.stash[GUARD_KEY] = guard
    guard.start()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Stop the guard's thread at the end of the run."""
    guard = config.stash.get(GUARD_KEY, None)
    if guard is not None:
        guard.finish()


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(item: pytest.Item) -> Generator[None, object, object]:
    """Tell the guard which test runs, and how much it grew the memory.

    Returns:
        The protocol's result.

    Yields:
        To the test's protocol (setup, call, teardown).

    """
    guard = item.config.stash.get(GUARD_KEY, None)
    if guard is None:
        return (yield)
    guard.test_started(nodeid=item.nodeid)
    try:
        return (yield)
    finally:
        guard.test_finished(nodeid=item.nodeid)
