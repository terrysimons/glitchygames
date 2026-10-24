"""Tests for tests/garbage_collection.py: collecting a test's garbage when memory climbs."""

from __future__ import annotations

import sys

import pytest

from tests.garbage_collection import PeakMemoryCollector, process_peak_memory_collector

STEP_BYTES = 16


class FakeProcess:
    """A process whose peak memory the test sets, counting collections."""

    def __init__(self) -> None:
        """Start at a 100-byte peak, with no collections."""
        self.peak_bytes = 100
        self.collections = 0

    def read_peak_bytes(self) -> int:
        return self.peak_bytes

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


@pytest.mark.skipif(sys.platform == 'win32', reason='Windows has no resource module')
def test_a_dummy_audio_run_gets_a_collector_reading_its_real_peak():
    """Off Windows, on the dummy audio driver, a collector starts from this process's peak."""
    collector = process_peak_memory_collector(audio_driver='dummy')

    assert collector is not None
    # The peak only grows, so a fresh collector has not grown a step yet
    assert not collector.after_test()


def test_a_real_audio_driver_gets_no_collector():
    """A run on a real audio driver (coreaudio) is left to the collector's own schedule."""
    assert process_peak_memory_collector(audio_driver='coreaudio') is None


@pytest.mark.skipif(sys.platform != 'win32', reason='only Windows lacks the resource module')
def test_windows_gets_no_collector():
    """Windows cannot read the peak, so there is no collector."""
    assert process_peak_memory_collector(audio_driver='dummy') is None
