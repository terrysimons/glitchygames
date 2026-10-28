"""Tests for tests/garbage_collection.py: collecting a test's garbage when memory climbs."""

from __future__ import annotations

import sys

import pytest

from tests.garbage_collection import (
    PeakMemoryCollector,
    malloc_bytes_in_use_reader,
    process_peak_memory_collector,
)

STEP_BYTES = 16
HEAP_STEP_BYTES = 32


class FakeProcess:
    """A process whose peak memory the test sets, counting collections."""

    def __init__(self) -> None:
        """Start at a 100-byte peak and 1000 heap bytes in use, with no collections."""
        self.peak_bytes = 100
        self.heap_bytes = 1000
        self.collections = 0

    def read_peak_bytes(self) -> int:
        return self.peak_bytes

    def read_heap_bytes(self) -> int:
        return self.heap_bytes

    def collect(self) -> int:
        self.collections += 1
        return 0


def collector_for(process: FakeProcess) -> PeakMemoryCollector:
    """Return a collector reading the fake process, with a STEP_BYTES step.

    Returns:
        The collector.

    """
    return PeakMemoryCollector(
        step_bytes=STEP_BYTES, read_peak_bytes=process.read_peak_bytes, collect=process.collect
    )


def test_nothing_is_collected_while_the_peak_holds():
    """A peak grown by no more than a step is left alone."""
    process = FakeProcess()
    collector = collector_for(process)

    process.peak_bytes += STEP_BYTES
    assert not collector.after_test()

    assert process.collections == 0


def test_a_peak_more_than_a_step_higher_is_collected_once():
    """A peak more than a step higher collects, once."""
    process = FakeProcess()
    collector = collector_for(process)

    process.peak_bytes += STEP_BYTES + 1
    assert collector.after_test()
    # Measured again from the peak after collecting: the same peak does not collect again
    assert not collector.after_test()

    assert process.collections == 1


def test_the_next_step_counts_from_the_last_collection():
    """After a collection, the next step is measured from the peak it left."""
    process = FakeProcess()
    collector = collector_for(process)
    process.peak_bytes += STEP_BYTES + 1
    collector.after_test()

    process.peak_bytes += STEP_BYTES
    assert not collector.after_test()
    process.peak_bytes += 1
    assert collector.after_test()

    assert process.collections == 2


def heap_collector_for(process: FakeProcess) -> PeakMemoryCollector:
    """Return a collector reading the fake process's peak and heap, with both steps.

    Returns:
        The collector.

    """
    return PeakMemoryCollector(
        step_bytes=STEP_BYTES,
        read_peak_bytes=process.read_peak_bytes,
        collect=process.collect,
        read_heap_bytes=process.read_heap_bytes,
        heap_step_bytes=HEAP_STEP_BYTES,
    )


def test_heap_growth_within_a_step_is_left_alone():
    """Heap bytes in use grown by no more than its step, at a steady peak, collect nothing."""
    process = FakeProcess()
    collector = heap_collector_for(process)

    process.heap_bytes += HEAP_STEP_BYTES
    assert not collector.after_test()

    assert process.collections == 0


def test_heap_growth_past_a_step_collects_at_a_steady_peak():
    """Garbage below the old peak still collects once malloc's bytes in use grew a step."""
    process = FakeProcess()
    collector = heap_collector_for(process)

    process.heap_bytes += HEAP_STEP_BYTES + 1
    assert collector.after_test()
    # Counted again from the heap after collecting: the same heap does not collect again
    assert not collector.after_test()

    assert process.collections == 1


def test_the_next_heap_step_counts_from_what_the_collection_left():
    """After a collection, heap growth is measured from the bytes in use it left."""
    process = FakeProcess()
    collector = heap_collector_for(process)
    process.heap_bytes += HEAP_STEP_BYTES + 1
    collector.after_test()

    process.heap_bytes += HEAP_STEP_BYTES
    assert not collector.after_test()
    process.heap_bytes += 1
    assert collector.after_test()

    assert process.collections == 2


def test_a_peak_collection_also_restarts_the_heap_step():
    """A collection the peak asked for counts the heap's step from then too."""
    process = FakeProcess()
    collector = heap_collector_for(process)
    process.heap_bytes += HEAP_STEP_BYTES
    process.peak_bytes += STEP_BYTES + 1
    assert collector.after_test()

    process.heap_bytes += 1
    assert not collector.after_test()

    assert process.collections == 1


@pytest.mark.skipif(
    not (sys.platform == 'darwin' or sys.platform.startswith('linux')),
    reason='malloc reports its bytes in use on glibc and macOS only',
)
def test_malloc_reports_its_bytes_in_use_here():
    """On glibc and macOS the reader reads malloc's bytes in use, which a large block raises."""
    read_heap_bytes = malloc_bytes_in_use_reader()

    assert read_heap_bytes is not None
    before = read_heap_bytes()
    # Large enough that malloc maps it on its own: counted at once, and freed by del
    block = bytearray(64 * 1024 * 1024)
    assert read_heap_bytes() - before >= len(block)
    del block


def test_no_heap_reader_where_malloc_reports_nothing():
    """Windows (or any other platform) has no reader: the peak trigger works alone."""
    assert malloc_bytes_in_use_reader(platform='win32') is None


def test_a_c_library_without_the_call_gives_no_heap_reader(mocker):
    """A Linux C library without mallinfo2 (musl, or glibc before 2.33) gives no reader."""
    mocker.patch('tests.garbage_collection.ctypes.CDLL', side_effect=OSError('no such library'))

    assert malloc_bytes_in_use_reader(platform='linux') is None


@pytest.mark.skipif(sys.platform == 'win32', reason='Windows has no resource module')
def test_every_run_gets_a_collector_reading_its_real_peak():
    """Off Windows, every run collects, the native coreaudio run too (BUGS.md #212).

    The native run once stalled with these collections; that no longer reproduces (#212's
    record), so its memory is bounded the same way as the dummy run's.
    """
    collector = process_peak_memory_collector()

    assert collector is not None
    # The peak only grows, so a fresh collector has not grown a step yet
    assert not collector.after_test()


@pytest.mark.skipif(sys.platform != 'win32', reason='only Windows lacks the resource module')
def test_windows_gets_no_collector():
    """Windows cannot read the peak, so there is no collector."""
    assert process_peak_memory_collector() is None
