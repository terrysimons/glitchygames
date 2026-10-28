"""Stop a test run that outgrows a memory limit, naming the test, before the kernel kills it.

CircleCI's Linux job (``resource_class: small``, 2 GB, serial) was killed with signal 9 when a
test ran the process out of memory (BUGS.md #235): the job log ended mid-test, with no test named
and no hint of what grew. This plugin is on only when ``GLITCHYGAMES_TEST_RSS_LIMIT_MB`` is set
(the Linux job sets 1900; mebibytes, so 1900 is 1992 MB). A background thread samples the memory
every ``SAMPLE_INTERVAL_SECONDS``, and each test's start and end are checked too. Past the limit it
stops the run (``os._exit``, ``LIMIT_EXIT_STATUS``) after writing, straight to the original
standard error, which memory passed it, the test running then (with how much it grew since it
started) and the largest per-test increases so far. A per-test check alone would miss a spike
inside one test, which is what #235 was (1.7 GB to 4.7 GB in one benchmark), hence the thread.

What it measures, the first that works:

1. **The container's memory** (cgroup v2: ``/sys/fs/cgroup/memory.current``, where
   ``memory.max`` sets a limit), less the page cache the kernel reclaims before it kills
   (``memory.stat``'s ``file``, shared memory excepted: it is not reclaimable without swap). That
   is what the 2 GB kill counts: every process in the container, the children the suite starts
   (replays, import probes) included.
2. **This process's resident memory** (``/proc/self/statm``), where there is no such cgroup (a
   Linux machine outside a container): children are not counted.

Neither exists on macOS or Windows, so there the plugin does nothing, even with the variable set.
Under pytest-xdist the workers make no guard (each would hold the whole limit for itself): the
controller's, reading the container's memory, sees every worker.

What it cannot see: the thread needs the GIL, so a C call that holds it, or growth faster than the
headroom in one interval (about 1.6 GB/s for 400 MiB in 0.25 s), can pass 2 GB between samples;
the check at the test's end then names it only if the kernel has not killed the run first.

Test tooling only: the thread is the honest choice in a desktop test process, and the engine never
imports this module (the browser build has no threads, and nothing of the engine's web path may
start one). Registered in the root conftest.py's ``pytest_plugins``. Tests:
tests/test_memory_guard.py.
"""

from __future__ import annotations

import contextlib
import functools
import os
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
# cgroup v2, as a container sees its own cgroup
CGROUP_DIRECTORY = Path('/sys/fs/cgroup')
CGROUP_NO_LIMIT = 'max'
# Mebibytes: the limit and the message count in them
BYTES_PER_MEBIBYTE = 1024 * 1024
# What each source measures, as the stop message names it
CGROUP_SOURCE = "the container's memory (cgroup memory.current, page cache left out)"
STATM_SOURCE = "this process's resident memory (/proc/self/statm)"
# The per-test increases named in the message
LARGEST_INCREASES_SHOWN = 5
# The run was stopped, as pytest's own status for an interrupted run
LIMIT_EXIT_STATUS = int(pytest.ExitCode.INTERRUPTED)
THREAD_NAME = 'memory-guard'

# The guard of this pytest run, when it is on
GUARD_KEY = pytest.StashKey['ResidentMemoryGuard']()


def _mebibytes(byte_count: int) -> str:
    return f'{byte_count / BYTES_PER_MEBIBYTE:.0f} MiB'


class ResidentMemoryGuard:
    """Watches the resident memory and stops the run past a limit, naming the test."""

    def __init__(
        self: Self,
        *,
        limit_bytes: int,
        read_resident_bytes: Callable[[], int],
        stop: Callable[[str], None],
        source: str = STATM_SOURCE,
        interval_seconds: float = SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        """Watch nothing yet: ``start`` starts the sampling thread.

        Args:
            limit_bytes: The memory the run may not pass.
            read_resident_bytes: Returns the memory now, in bytes.
            source: What ``read_resident_bytes`` measures (named in the message).
            stop: Ends the run with the message (``stop_the_run`` in a real run; it does not
                return there).
            interval_seconds: How long the thread waits between samples.

        """
        self._limit_bytes = limit_bytes
        self._read_resident_bytes = read_resident_bytes
        self._stop = stop
        self._source = source
        self._interval_seconds = interval_seconds
        self._lock = threading.Lock()
        self._current_test: str | None = None
        self._resident_at_test_start = 0
        # Each finished test's growth (resident at its end less at its start), by node ID
        self._increases: dict[str, int] = {}
        self._stopped = False
        # The highest reading so far (the run's summary names it)
        self._peak_bytes = 0
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
        with self._lock:
            self._peak_bytes = max(self._peak_bytes, resident)
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
            running = f'in {self._current_test} (+{_mebibytes(grown)} since it started)'
        lines = [
            (
                f'{LIMIT_VARIABLE}: {self._source} reached {_mebibytes(resident)}, past the '
                f'limit of {_mebibytes(self._limit_bytes)}, {running}; the run was stopped'
            ),
        ]
        largest = sorted(self._increases.items(), key=lambda item: (-item[1], item[0]))
        if largest:
            lines.append('Largest increases by a finished test so far:')
            lines.extend(
                f'  +{_mebibytes(increase)} {nodeid}'
                for nodeid, increase in largest[:LARGEST_INCREASES_SHOWN]
            )
        return '\n'.join(lines)

    def describe_peak(self: Self) -> str:
        """Describe the highest reading so far, for the run's summary.

        Returns:
            ``memory guard: peak N MiB of <source>, limit M MiB``.

        """
        with self._lock:
            peak = self._peak_bytes
        return (
            f'memory guard: peak {_mebibytes(peak)} of {self._source}, limit '
            f'{_mebibytes(self._limit_bytes)}'
        )

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


def system_page_bytes() -> int:
    """Return the system's page size (``os.sysconf``, which exists only off Windows).

    Returns:
        Bytes per page.

    """
    return os.sysconf('SC_PAGE_SIZE')


def statm_resident_reader(
    *, path: Path = STATM_PATH, page_bytes: Callable[[], int] = system_page_bytes
) -> Callable[[], int] | None:
    """Return a reader of this process's resident memory from ``/proc/self/statm``.

    Args:
        path: The statm file.
        page_bytes: Returns the page size (read once, only when the file exists).

    Returns:
        The reader (bytes), or None where the file cannot be read (not Linux).

    """
    try:
        path.read_text(encoding='ascii')
    except OSError:
        return None
    page_size = page_bytes()

    def read_resident_bytes() -> int:
        return int(path.read_text(encoding='ascii').split()[STATM_RESIDENT_FIELD]) * page_size

    return read_resident_bytes


def _cgroup_unreclaimable_bytes(*, directory: Path) -> int:
    """Return a cgroup's memory less the page cache the kernel can reclaim.

    Returns:
        ``memory.current`` less ``memory.stat``'s ``file`` plus its ``shmem`` (shared memory
        counts as file but cannot be reclaimed without swap).

    """
    current = int((directory / 'memory.current').read_text(encoding='ascii'))
    statistics = {
        name: int(value)
        for name, value in (
            line.split()
            for line in (directory / 'memory.stat').read_text(encoding='ascii').splitlines()
        )
    }
    return current - statistics['file'] + statistics['shmem']


def cgroup_memory_reader(*, directory: Path = CGROUP_DIRECTORY) -> Callable[[], int] | None:
    """Return a reader of the container's memory, page cache left out (cgroup v2).

    Args:
        directory: The cgroup's directory (a container sees its own at /sys/fs/cgroup).

    Returns:
        The reader (bytes), or None where there is no cgroup with a memory limit there (not in
        a container, cgroup v1, or no limit).

    """
    try:
        limit = (directory / 'memory.max').read_text(encoding='ascii').strip()
        _cgroup_unreclaimable_bytes(directory=directory)
    except OSError, KeyError, ValueError:
        return None
    if limit == CGROUP_NO_LIMIT:
        return None
    return functools.partial(_cgroup_unreclaimable_bytes, directory=directory)


def memory_reader(
    *, cgroup_directory: Path, statm_path: Path, page_bytes: Callable[[], int]
) -> tuple[Callable[[], int], str] | None:
    """Return the reader the guard uses and what it measures: the container's, else this process's.

    Args:
        cgroup_directory: Where the cgroup's files are.
        statm_path: This process's statm file.
        page_bytes: Returns the page size (for statm).

    Returns:
        ``(reader, source)``, or None where neither can be read.

    """
    container = cgroup_memory_reader(directory=cgroup_directory)
    if container is not None:
        return container, CGROUP_SOURCE
    process = statm_resident_reader(path=statm_path, page_bytes=page_bytes)
    if process is not None:
        return process, STATM_SOURCE
    return None


def guard_from_environment(
    *,
    environment: Mapping[str, str],
    read_resident_bytes: Callable[[], int] | None,
    stop: Callable[[str], None],
    source: str = STATM_SOURCE,
) -> ResidentMemoryGuard | None:
    """Return the guard ``GLITCHYGAMES_TEST_RSS_LIMIT_MB`` asks for, or None when it is off.

    Args:
        environment: The process's environment.
        read_resident_bytes: The memory reader, or None where none works.
        stop: Ends the run with a message.
        source: What the reader measures.

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
        message = f'{LIMIT_VARIABLE} must be a positive whole number of mebibytes, not {value!r}'
        raise pytest.UsageError(message)
    return ResidentMemoryGuard(
        limit_bytes=int(value) * BYTES_PER_MEBIBYTE,
        read_resident_bytes=read_resident_bytes,
        stop=stop,
        source=source,
    )


def original_standard_error(*, config: pytest.Config) -> int:
    """Return a file descriptor of the standard error the run started with.

    pytest's capture has already moved file descriptor 2 to its own file when plugins configure,
    and keeps the original as its error capture's ``targetfd_save`` (pytest's own name, read
    defensively). A run without capture (``-s``) still has the original as descriptor 2.

    Returns:
        A duplicate of it, owned by the caller.

    """
    capture = config.pluginmanager.get_plugin('capturemanager')
    global_capturing = getattr(capture, '_global_capturing', None)
    error_capture = getattr(global_capturing, 'err', None)
    saved = getattr(error_capture, 'targetfd_save', None)
    return os.dup(saved if isinstance(saved, int) else 2)


def stop_the_run(*, error_descriptor: int, message: str) -> None:
    """Write the message to the original standard error and end the process at once, always.

    From the sampling thread: pytest's capture is not touched (it is not thread-safe), the write
    goes straight to the descriptor, and ``os._exit`` runs even if the write fails, so the guard
    can never die on its thread and leave the run to the kernel's kill.

    Args:
        error_descriptor: The original standard error (``original_standard_error``).
        message: What passed the limit, and where.

    """
    try:
        with contextlib.suppress(OSError):
            os.write(error_descriptor, f'\n{message}\n'.encode(errors='replace'))
    finally:
        os._exit(LIMIT_EXIT_STATUS)


def pytest_configure(config: pytest.Config) -> None:
    """Start the guard when ``GLITCHYGAMES_TEST_RSS_LIMIT_MB`` is set and the memory is readable.

    Never in a pytest-xdist worker (``workerinput``): each would hold the whole limit for itself.
    The stop is bound now, with the original standard error, so nothing patched later changes
    what a tripped guard does.
    """
    if hasattr(config, 'workerinput'):
        return
    reader = memory_reader(
        cgroup_directory=CGROUP_DIRECTORY, statm_path=STATM_PATH, page_bytes=system_page_bytes
    )
    environment_reader, source = (None, STATM_SOURCE) if reader is None else reader
    # Bound here: the function as it is now, and the descriptor once a guard is made
    stop_function = stop_the_run
    error_descriptors: list[int] = []

    def stop(message: str) -> None:
        stop_function(error_descriptor=error_descriptors[0], message=message)

    guard = guard_from_environment(
        environment=os.environ, read_resident_bytes=environment_reader, stop=stop, source=source
    )
    if guard is None:
        return
    error_descriptors.append(original_standard_error(config=config))
    config.stash[GUARD_KEY] = guard
    guard.start()


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    """Name the highest memory the guard saw, so a healthy run shows its headroom."""
    guard = config.stash.get(GUARD_KEY, None)
    if guard is not None:
        terminalreporter.write_line(guard.describe_peak())


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
