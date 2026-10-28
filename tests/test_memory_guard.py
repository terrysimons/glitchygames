"""Tests for tests/memory_guard.py: stopping a run that outgrows its memory limit, naming the test.

The memory is a stand-in sampler (a list of readings) and the stop a recorder, so nothing here
reads ``/proc`` or ends the process.
"""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING

import pytest

from tests.memory_guard import (
    BYTES_PER_MEBIBYTE,
    CGROUP_SOURCE,
    LIMIT_EXIT_STATUS,
    LIMIT_VARIABLE,
    STATM_SOURCE,
    ResidentMemoryGuard,
    cgroup_memory_reader,
    cgroup_reclaimable_slab_reader,
    guard_from_environment,
    memory_reader,
    original_standard_error,
    statm_resident_reader,
    stop_the_run,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

LIMIT_BYTES = 100 * BYTES_PER_MEBIBYTE
# How long the sampling thread may take to see a reading past the limit (it samples every few
# milliseconds here; the wait ends as soon as it stops)
THREAD_WAIT_SECONDS = 30.0
# A thread interval short enough that the test never waits on it
SHORT_INTERVAL_SECONDS = 0.001


def mebibytes(count: int) -> int:
    """Return ``count`` mebibytes in bytes.

    Returns:
        The byte count.

    """
    return count * BYTES_PER_MEBIBYTE


class StandInSampler:
    """Returns the readings given, one per call, then the last one forever."""

    def __init__(self, *readings: int) -> None:
        """Hold the readings.

        Args:
            readings: Resident sizes in bytes, in order.

        """
        self._readings = list(readings)

    def __call__(self) -> int:
        """Return the next reading.

        Returns:
            Bytes.

        """
        if len(self._readings) > 1:
            return self._readings.pop(0)
        return self._readings[0]


class RecordedStops:
    """Records each stop's message, and signals the first."""

    def __init__(self) -> None:
        """Record nothing yet."""
        self.messages: list[str] = []
        self.stopped = threading.Event()

    def __call__(self, message: str) -> None:
        """Record a stop.

        Args:
            message: The guard's message.

        """
        self.messages.append(message)
        self.stopped.set()


def make_guard(
    *, read_resident_bytes: Callable[[], int], stop: RecordedStops
) -> ResidentMemoryGuard:
    """Return a guard with the 100 MiB limit.

    Returns:
        The guard (not started).

    """
    return ResidentMemoryGuard(
        limit_bytes=LIMIT_BYTES,
        read_resident_bytes=read_resident_bytes,
        stop=stop,
        interval_seconds=SHORT_INTERVAL_SECONDS,
    )


def test_a_sample_past_the_limit_stops_the_run_naming_the_test_running():
    """A spike inside a test: the message names it, its growth, the reading and the limit."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(mebibytes(40), mebibytes(150)), stop=stops
    )
    guard.test_started(nodeid='tests/test_big.py::test_spike')

    assert guard.check() is True

    (message,) = stops.messages
    assert message.startswith(
        f'{LIMIT_VARIABLE}: {STATM_SOURCE} reached 150 MiB, past the limit of 100 MiB, in '
        'tests/test_big.py::test_spike (+110 MiB since it started); the run was stopped'
    )


def test_the_message_lists_the_largest_increases_by_finished_tests():
    """The finished tests that grew the memory most are listed, the most first."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(
            mebibytes(10),
            mebibytes(30),  # test_a: +20
            mebibytes(30),
            mebibytes(35),  # test_b: +5
            mebibytes(35),
            mebibytes(95),  # test_c: +60
            mebibytes(95),
            mebibytes(101),
        ),
        stop=stops,
    )
    for name in ('test_a', 'test_b', 'test_c'):
        guard.test_started(nodeid=f'tests/test_x.py::{name}')
        guard.test_finished(nodeid=f'tests/test_x.py::{name}')
    guard.test_started(nodeid='tests/test_x.py::test_d')

    assert guard.check() is True

    (message,) = stops.messages
    assert message.splitlines()[1:] == [
        'Largest increases by a finished test so far:',
        '  +60 MiB tests/test_x.py::test_c',
        '  +20 MiB tests/test_x.py::test_a',
        '  +5 MiB tests/test_x.py::test_b',
    ]


def test_a_test_ending_past_the_limit_stops_the_run_between_tests():
    """The check at a test's end catches growth the thread has not sampled yet."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(mebibytes(50), mebibytes(120)), stop=stops
    )
    guard.test_started(nodeid='tests/test_x.py::test_grows')
    guard.test_finished(nodeid='tests/test_x.py::test_grows')

    (message,) = stops.messages
    assert 'past the limit of 100 MiB, between tests' in message
    assert '  +70 MiB tests/test_x.py::test_grows' in message.splitlines()


def test_below_the_limit_nothing_happens():
    """Readings at or under the limit never stop the run."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(mebibytes(100)), stop=stops)
    guard.test_started(nodeid='tests/test_x.py::test_small')

    assert guard.check() is False
    guard.test_finished(nodeid='tests/test_x.py::test_small')
    assert stops.messages == []


def test_the_run_is_stopped_once():
    """Past the limit, a later check does not stop it again."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(mebibytes(200)), stop=stops)

    assert guard.check() is True
    assert guard.check() is True
    assert len(stops.messages) == 1


def test_the_thread_samples_until_the_limit_is_passed():
    """The sampling thread stops the run on its own, during a test, then ends."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(mebibytes(10), mebibytes(10), mebibytes(500)),
        stop=stops,
    )
    guard.test_started(nodeid='tests/test_x.py::test_long')

    guard.start()
    stopped = stops.stopped.wait(THREAD_WAIT_SECONDS)
    guard.finish()

    assert stopped
    (message,) = stops.messages
    assert 'in tests/test_x.py::test_long (+490 MiB since it started)' in message
    assert not guard.sampling()


def test_finish_ends_the_thread_below_the_limit():
    """Under the limit the thread keeps sampling until the run finishes, and stops nothing."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(mebibytes(10)), stop=stops)

    guard.start()
    sampling_before_finish = guard.sampling()
    guard.finish()

    assert sampling_before_finish

    assert stops.messages == []
    assert not guard.sampling()


@pytest.mark.parametrize('environment', [{}, {LIMIT_VARIABLE: ''}, {LIMIT_VARIABLE: '  '}])
def test_unset_the_plugin_does_nothing(environment):
    """No limit (unset or empty): no guard, so no thread and no checks."""
    assert (
        guard_from_environment(
            environment=environment,
            read_resident_bytes=StandInSampler(mebibytes(10_000)),
            stop=RecordedStops(),
        )
        is None
    )


def test_without_a_memory_reader_the_plugin_does_nothing():
    """Where /proc/self/statm cannot be read (macOS, Windows), a set limit turns nothing on."""
    assert (
        guard_from_environment(
            environment={LIMIT_VARIABLE: '1600'}, read_resident_bytes=None, stop=RecordedStops()
        )
        is None
    )


def test_a_set_limit_makes_a_guard_with_it_in_mebibytes():
    """1600 is 1600 MiB: a reading just over it stops the run."""
    stops = RecordedStops()
    guard = guard_from_environment(
        environment={LIMIT_VARIABLE: '1600'},
        read_resident_bytes=StandInSampler(mebibytes(1600), mebibytes(1601)),
        stop=stops,
    )

    assert guard is not None
    assert guard.check() is False
    assert guard.check() is True


@pytest.mark.parametrize('value', ['0', '-5', '1.5', 'lots'])
def test_a_limit_that_is_not_a_positive_whole_number_is_refused(value):
    """A mistyped limit fails the run's start instead of silently guarding nothing."""
    with pytest.raises(pytest.UsageError, match=f'{LIMIT_VARIABLE} must be a positive whole'):
        guard_from_environment(
            environment={LIMIT_VARIABLE: value},
            read_resident_bytes=StandInSampler(0),
            stop=RecordedStops(),
        )


def test_the_statm_reader_reads_the_resident_pages(tmp_path: Path):
    """The second statm field, in pages, times the page size (given: Windows has no sysconf)."""
    statm = tmp_path / 'statm'
    statm.write_text('5000 300 40 1 0 200 0\n', encoding='ascii')

    reader = statm_resident_reader(path=statm, page_bytes=lambda: 4096)

    assert reader is not None
    assert reader() == 300 * 4096


def test_the_statm_reader_is_none_without_the_file(tmp_path: Path):
    """No statm file (not Linux): no reader."""
    assert statm_resident_reader(path=tmp_path / 'missing') is None


PLUGIN_RUN_TESTS = """
def test_first():
    pass


def test_second():
    pass
"""


def test_the_plugin_stops_a_run_past_the_limit_naming_its_test(pytester, monkeypatch, tmp_path):
    """Through pytest's hooks: the first test's start is past the limit, and named."""
    statm = tmp_path / 'statm'
    statm.write_text('5000 300 40 1 0 200 0\n', encoding='ascii')
    stops = RecordedStops()
    monkeypatch.setattr('tests.memory_guard.STATM_PATH', statm)
    # No container cgroup here, wherever this runs (the Linux CI job has one)
    monkeypatch.setattr('tests.memory_guard.CGROUP_DIRECTORY', tmp_path / 'no-cgroup')
    monkeypatch.setattr('tests.memory_guard.system_page_bytes', lambda: BYTES_PER_MEBIBYTE)
    monkeypatch.setattr(
        'tests.memory_guard.stop_the_run', lambda *, error_descriptor, message: stops(message)
    )
    monkeypatch.setenv(LIMIT_VARIABLE, '200')
    pytester.makepyfile(test_inner_run=PLUGIN_RUN_TESTS)

    # --assert=plain: this process imported the plugin already, so pytest could not rewrite it
    # (PytestAssertRewriteWarning); it asserts nothing
    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=2)
    (message,) = stops.messages
    assert f'{STATM_SOURCE} reached 300 MiB, past the limit of 200 MiB, in ' in message
    assert 'test_inner_run.py::test_first (+0 MiB since it started)' in message


def test_the_plugin_does_nothing_unset(pytester, monkeypatch):
    """Through pytest's hooks, unset: no guard is made (so no thread starts) and nothing stops.

    Checked by the inner run's stash, not by thread names: this process may run the real guard
    (the Linux CI job sets the variable).
    """
    monkeypatch.delenv(LIMIT_VARIABLE, raising=False)
    monkeypatch.setattr(
        'tests.memory_guard.stop_the_run',
        lambda *, error_descriptor, message: pytest.fail(f'stopped: {message}'),
    )
    pytester.makepyfile(
        test_inner_run=(
            'from tests.memory_guard import GUARD_KEY\n'
            'def test_no_guard(request):\n'
            '    assert GUARD_KEY not in request.config.stash\n'
        )
    )

    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=1)


def write_cgroup(  # ruff: ignore[too-many-arguments]
    directory: Path,
    *,
    limit: str,
    current: int,
    file: int,
    shmem: int,
    slab_reclaimable: int | None = None,
) -> Path:
    """Write the cgroup v2 files the container reader reads.

    Args:
        directory: Where to write them.
        limit: ``memory.max``.
        current: ``memory.current``.
        file: ``memory.stat``'s page cache.
        shmem: ``memory.stat``'s shared memory.
        slab_reclaimable: ``memory.stat``'s reclaimable kernel slab, or None to leave it out
            (an older kernel).

    Returns:
        The directory.

    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'memory.max').write_text(f'{limit}\n', encoding='ascii')
    (directory / 'memory.current').write_text(f'{current}\n', encoding='ascii')
    slab = '' if slab_reclaimable is None else f'slab_reclaimable {slab_reclaimable}\n'
    (directory / 'memory.stat').write_text(
        f'anon {current - file}\nfile {file}\nkernel 1000\nshmem {shmem}\n{slab}',
        encoding='ascii',
    )
    return directory


def test_the_cgroup_reader_leaves_out_the_reclaimable_page_cache(tmp_path: Path):
    """memory.current less memory.stat's file, plus its shmem (not reclaimable without swap)."""
    cgroup = write_cgroup(
        tmp_path / 'cgroup',
        limit='2147483648',
        current=mebibytes(1900),
        file=mebibytes(600),
        shmem=mebibytes(50),
    )

    reader = cgroup_memory_reader(directory=cgroup)

    assert reader is not None
    assert reader() == mebibytes(1900 - 600 + 50)


@pytest.mark.parametrize('limit', ['max', None], ids=['no limit', 'no cgroup'])
def test_without_a_limited_cgroup_there_is_no_container_reader(tmp_path: Path, limit):
    """No memory limit (not a container's cgroup), or no cgroup files: no reader."""
    cgroup = tmp_path / 'cgroup'
    if limit is not None:
        write_cgroup(cgroup, limit=limit, current=mebibytes(10), file=0, shmem=0)

    assert cgroup_memory_reader(directory=cgroup) is None


def test_the_container_is_measured_where_it_can_be_else_the_process(tmp_path: Path):
    """The cgroup when there is one (it counts the children too), else /proc/self/statm."""
    cgroup = write_cgroup(
        tmp_path / 'cgroup', limit='2147483648', current=mebibytes(700), file=0, shmem=0
    )
    statm = tmp_path / 'statm'
    statm.write_text('5000 300 40 1 0 200 0\n', encoding='ascii')

    container = memory_reader(cgroup_directory=cgroup, statm_path=statm, page_bytes=lambda: 1)
    process = memory_reader(
        cgroup_directory=tmp_path / 'none', statm_path=statm, page_bytes=lambda: 1
    )
    neither = memory_reader(
        cgroup_directory=tmp_path / 'none', statm_path=tmp_path / 'none', page_bytes=lambda: 1
    )

    assert container is not None
    assert (container[0](), container[1]) == (mebibytes(700), CGROUP_SOURCE)
    assert process is not None
    assert (process[0](), process[1]) == (300, STATM_SOURCE)
    assert neither is None


def test_the_message_names_the_container_source():
    """A guard reading the cgroup says it was the container's memory that passed the limit."""
    stops = RecordedStops()
    guard = ResidentMemoryGuard(
        limit_bytes=LIMIT_BYTES,
        read_resident_bytes=StandInSampler(mebibytes(101)),
        stop=stops,
        source=CGROUP_SOURCE,
    )

    guard.check()

    assert stops.messages[0].startswith(f'{LIMIT_VARIABLE}: {CGROUP_SOURCE} reached 101 MiB')


def test_stopping_writes_to_the_descriptor_and_exits(mocker):
    """The message goes straight to the descriptor, then os._exit with the limit's status."""
    exits = mocker.patch('tests.memory_guard.os._exit')
    read_end, write_end = os.pipe()
    try:
        stop_the_run(error_descriptor=write_end, message='over the limit')
        written = os.read(read_end, 1000)
    finally:
        os.close(read_end)
        os.close(write_end)

    assert written == b'\nover the limit\n'
    exits.assert_called_once_with(LIMIT_EXIT_STATUS)


def test_stopping_exits_even_when_the_write_fails(mocker):
    """A failed write (a closed descriptor) still ends the process: the guard never dies."""
    exits = mocker.patch('tests.memory_guard.os._exit')
    read_end, write_end = os.pipe()
    os.close(read_end)
    os.close(write_end)

    stop_the_run(error_descriptor=write_end, message='over the limit')

    exits.assert_called_once_with(LIMIT_EXIT_STATUS)


def test_the_original_standard_error_is_a_new_descriptor(pytestconfig):
    """A duplicate of the run's original standard error (pytest's saved one when capturing)."""
    descriptor = original_standard_error(config=pytestconfig)
    try:
        assert descriptor > 2
        os.fstat(descriptor)
    finally:
        os.close(descriptor)


def test_an_xdist_worker_makes_no_guard(pytester, monkeypatch, tmp_path):
    """A worker (its config has workerinput) makes none: the controller's sees the container."""
    statm = tmp_path / 'statm'
    statm.write_text('5000 300 40 1 0 200 0\n', encoding='ascii')
    monkeypatch.setattr('tests.memory_guard.STATM_PATH', statm)
    monkeypatch.setattr('tests.memory_guard.CGROUP_DIRECTORY', tmp_path / 'no-cgroup')
    monkeypatch.setattr('tests.memory_guard.system_page_bytes', lambda: 1)
    monkeypatch.setenv(LIMIT_VARIABLE, '1600')
    pytester.makeconftest(
        'import pytest\n'
        '@pytest.hookimpl(tryfirst=True)\n'
        'def pytest_configure(config):\n'
        "    config.workerinput = {'workerid': 'gw0'}\n"
    )
    pytester.makepyfile(
        test_inner_run=(
            'from tests.memory_guard import GUARD_KEY\n'
            'def test_no_guard(request):\n'
            '    assert GUARD_KEY not in request.config.stash\n'
        )
    )

    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=1)


def test_the_run_summary_names_the_peak_the_guard_saw(pytester, monkeypatch, tmp_path):
    """A healthy run (under the limit) ends with the highest reading and its source."""
    statm = tmp_path / 'statm'
    statm.write_text('5000 300 40 1 0 200 0\n', encoding='ascii')
    monkeypatch.setattr('tests.memory_guard.STATM_PATH', statm)
    monkeypatch.setattr('tests.memory_guard.CGROUP_DIRECTORY', tmp_path / 'no-cgroup')
    monkeypatch.setattr('tests.memory_guard.system_page_bytes', lambda: BYTES_PER_MEBIBYTE)
    monkeypatch.setenv(LIMIT_VARIABLE, '1600')
    pytester.makepyfile(test_inner_run=PLUGIN_RUN_TESTS)

    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=2)
    result.stdout.fnmatch_lines([f'memory guard: peak 300 MiB of {STATM_SOURCE}, limit 1600 MiB'])


def test_the_slab_reader_reads_the_reclaimable_kernel_slab(tmp_path: Path):
    """memory.stat's slab_reclaimable, in bytes (the container's reading counts it)."""
    cgroup = write_cgroup(
        tmp_path / 'cgroup',
        limit='2147483648',
        current=mebibytes(1400),
        file=0,
        shmem=0,
        slab_reclaimable=mebibytes(290),
    )

    reader = cgroup_reclaimable_slab_reader(directory=cgroup)

    assert reader is not None
    assert reader() == mebibytes(290)


@pytest.mark.parametrize('cgroup_files', [True, False], ids=['no slab line', 'no cgroup'])
def test_without_a_slab_line_there_is_no_slab_reader(tmp_path: Path, cgroup_files):
    """An older kernel's memory.stat without slab_reclaimable, or no cgroup at all: no reader."""
    cgroup = tmp_path / 'cgroup'
    if cgroup_files:
        write_cgroup(cgroup, limit='2147483648', current=mebibytes(10), file=0, shmem=0)

    assert cgroup_reclaimable_slab_reader(directory=cgroup) is None


def test_the_summary_names_the_slab_at_the_peak():
    """The slab read with the highest reading, not with a later, lower one."""
    guard = ResidentMemoryGuard(
        limit_bytes=LIMIT_BYTES,
        read_resident_bytes=StandInSampler(mebibytes(60), mebibytes(90), mebibytes(70)),
        stop=RecordedStops(),
        source=CGROUP_SOURCE,
        read_reclaimable_slab_bytes=StandInSampler(mebibytes(20), mebibytes(30), mebibytes(99)),
    )

    for _ in range(3):
        guard.check()

    assert guard.describe_peak() == (
        f'memory guard: peak 90 MiB of {CGROUP_SOURCE}, limit 100 MiB '
        '(30 MiB of it reclaimable kernel slab)'
    )


def test_a_stop_names_the_slab_in_its_reading():
    """Past the limit, the message says how much of the reading the kernel could reclaim."""
    stops = RecordedStops()
    guard = ResidentMemoryGuard(
        limit_bytes=LIMIT_BYTES,
        read_resident_bytes=StandInSampler(mebibytes(150)),
        stop=stops,
        source=CGROUP_SOURCE,
        read_reclaimable_slab_bytes=StandInSampler(mebibytes(40)),
    )

    guard.check()

    (message,) = stops.messages
    assert message.splitlines()[1] == 'Of that reading, 40 MiB is reclaimable kernel slab'


def test_without_a_slab_reader_neither_names_a_slab():
    """The process's own reading (statm) counts no slab: the summary and the stop say nothing."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(mebibytes(150)), stop=stops)

    guard.check()

    assert 'slab' not in guard.describe_peak()
    assert 'slab' not in stops.messages[0]


def test_the_run_summary_names_the_containers_slab(pytester, monkeypatch, tmp_path):
    """Through pytest's hooks, in a container: the peak, then the slab counted in it."""
    cgroup = write_cgroup(
        tmp_path / 'cgroup',
        limit='2147483648',
        current=mebibytes(1400),
        file=mebibytes(100),
        shmem=0,
        slab_reclaimable=mebibytes(290),
    )
    monkeypatch.setattr('tests.memory_guard.CGROUP_DIRECTORY', cgroup)
    monkeypatch.setenv(LIMIT_VARIABLE, '1600')
    pytester.makepyfile(test_inner_run=PLUGIN_RUN_TESTS)

    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=2)
    expected = (
        f'memory guard: peak 1300 MiB of {CGROUP_SOURCE}, limit 1600 MiB '
        '(290 MiB of it reclaimable kernel slab)'
    )
    result.stdout.fnmatch_lines([expected])
