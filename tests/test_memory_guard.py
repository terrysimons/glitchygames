"""Tests for tests/memory_guard.py: stopping a run that outgrows its memory limit, naming the test.

The memory is a stand-in sampler (a list of readings) and the stop a recorder, so nothing here
reads ``/proc`` or ends the process.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from tests.memory_guard import (
    BYTES_PER_MEGABYTE,
    LIMIT_VARIABLE,
    THREAD_NAME,
    ResidentMemoryGuard,
    guard_from_environment,
    statm_resident_reader,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

LIMIT_BYTES = 100 * BYTES_PER_MEGABYTE
# How long the sampling thread may take to see a reading past the limit (it samples every few
# milliseconds here; the wait ends as soon as it stops)
THREAD_WAIT_SECONDS = 30.0
# A thread interval short enough that the test never waits on it
SHORT_INTERVAL_SECONDS = 0.001


def megabytes(count: int) -> int:
    """Return ``count`` megabytes in bytes.

    Returns:
        The byte count.

    """
    return count * BYTES_PER_MEGABYTE


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
    """Return a guard with the 100 MB limit.

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
        read_resident_bytes=StandInSampler(megabytes(40), megabytes(150)), stop=stops
    )
    guard.test_started(nodeid='tests/test_big.py::test_spike')

    assert guard.check() is True

    (message,) = stops.messages
    assert message.startswith(
        f'{LIMIT_VARIABLE}: resident memory 150 MB passed the limit of 100 MB in '
        'tests/test_big.py::test_spike (+110 MB since it started); the run was stopped'
    )


def test_the_message_lists_the_largest_increases_by_finished_tests():
    """The finished tests that grew the memory most are listed, the most first."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(
            megabytes(10),
            megabytes(30),  # test_a: +20
            megabytes(30),
            megabytes(35),  # test_b: +5
            megabytes(35),
            megabytes(95),  # test_c: +60
            megabytes(95),
            megabytes(101),
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
        '  +60 MB tests/test_x.py::test_c',
        '  +20 MB tests/test_x.py::test_a',
        '  +5 MB tests/test_x.py::test_b',
    ]


def test_a_test_ending_past_the_limit_stops_the_run_between_tests():
    """The check at a test's end catches growth the thread has not sampled yet."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(megabytes(50), megabytes(120)), stop=stops
    )
    guard.test_started(nodeid='tests/test_x.py::test_grows')
    guard.test_finished(nodeid='tests/test_x.py::test_grows')

    (message,) = stops.messages
    assert 'passed the limit of 100 MB between tests' in message
    assert '  +70 MB tests/test_x.py::test_grows' in message.splitlines()


def test_below_the_limit_nothing_happens():
    """Readings at or under the limit never stop the run."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(megabytes(100)), stop=stops)
    guard.test_started(nodeid='tests/test_x.py::test_small')

    assert guard.check() is False
    guard.test_finished(nodeid='tests/test_x.py::test_small')
    assert stops.messages == []


def test_the_run_is_stopped_once():
    """Past the limit, a later check does not stop it again."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(megabytes(200)), stop=stops)

    assert guard.check() is True
    assert guard.check() is True
    assert len(stops.messages) == 1


def test_the_thread_samples_until_the_limit_is_passed():
    """The sampling thread stops the run on its own, during a test, then ends."""
    stops = RecordedStops()
    guard = make_guard(
        read_resident_bytes=StandInSampler(megabytes(10), megabytes(10), megabytes(500)),
        stop=stops,
    )
    guard.test_started(nodeid='tests/test_x.py::test_long')

    guard.start()
    stopped = stops.stopped.wait(THREAD_WAIT_SECONDS)
    guard.finish()

    assert stopped
    (message,) = stops.messages
    assert 'in tests/test_x.py::test_long (+490 MB since it started)' in message
    assert not any(thread.name == THREAD_NAME for thread in threading.enumerate())


def test_finish_ends_the_thread_below_the_limit():
    """Under the limit the thread keeps sampling until the run finishes, and stops nothing."""
    stops = RecordedStops()
    guard = make_guard(read_resident_bytes=StandInSampler(megabytes(10)), stop=stops)

    guard.start()
    guard.finish()

    assert stops.messages == []
    assert not any(thread.name == THREAD_NAME for thread in threading.enumerate())


@pytest.mark.parametrize('environment', [{}, {LIMIT_VARIABLE: ''}, {LIMIT_VARIABLE: '  '}])
def test_unset_the_plugin_does_nothing(environment):
    """No limit (unset or empty): no guard, so no thread and no checks."""
    assert (
        guard_from_environment(
            environment=environment,
            read_resident_bytes=StandInSampler(megabytes(10_000)),
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


def test_a_set_limit_makes_a_guard_with_it_in_megabytes():
    """1600 is 1600 MB: a reading just over it stops the run."""
    stops = RecordedStops()
    guard = guard_from_environment(
        environment={LIMIT_VARIABLE: '1600'},
        read_resident_bytes=StandInSampler(megabytes(1600), megabytes(1601)),
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


def test_the_statm_reader_reads_the_resident_pages(tmp_path: Path, mocker):
    """The second statm field, in pages, times the page size."""
    statm = tmp_path / 'statm'
    statm.write_text('5000 300 40 1 0 200 0\n', encoding='ascii')
    mocker.patch('tests.memory_guard.os.sysconf', return_value=4096)

    reader = statm_resident_reader(path=statm)

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
    monkeypatch.setattr('tests.memory_guard.os.sysconf', lambda _name: BYTES_PER_MEGABYTE)
    monkeypatch.setattr(
        'tests.memory_guard.stop_the_run', lambda *, config, message: stops(message)
    )
    monkeypatch.setenv(LIMIT_VARIABLE, '200')
    pytester.makepyfile(test_inner_run=PLUGIN_RUN_TESTS)

    # --assert=plain: this process imported the plugin already, so pytest could not rewrite it
    # (PytestAssertRewriteWarning); it asserts nothing
    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=2)
    (message,) = stops.messages
    assert 'resident memory 300 MB passed the limit of 200 MB in ' in message
    assert 'test_inner_run.py::test_first (+0 MB since it started)' in message


def test_the_plugin_does_nothing_unset(pytester, monkeypatch):
    """Through pytest's hooks, unset: the tests run, no guard thread runs and nothing stops."""
    monkeypatch.delenv(LIMIT_VARIABLE, raising=False)
    monkeypatch.setattr(
        'tests.memory_guard.stop_the_run',
        lambda *, config, message: pytest.fail(f'stopped: {message}'),
    )
    pytester.makepyfile(
        test_inner_run=(
            'import threading\n'
            'def test_no_guard_thread():\n'
            f'    assert {THREAD_NAME!r} not in [thread.name for thread in threading.enumerate()]\n'
        )
    )

    result = pytester.runpytest_inprocess('-p', 'tests.memory_guard', '--assert=plain')

    result.assert_outcomes(passed=1)
