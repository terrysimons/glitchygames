"""Tests for tests/garbage_collection.py: collecting a test's garbage when memory climbs."""

from __future__ import annotations

import ctypes
import gc
import os
import sys
import weakref
from pathlib import Path

import pytest

from tests.garbage_collection import (
    AfterTestMemoryRelease,
    PeakMemoryCollector,
    malloc_bytes_in_use_reader,
    malloc_trimmer,
    process_memory_release,
    process_peak_memory_collector,
    release_test_instance,
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
        self.events: list[str] = []

    def read_peak_bytes(self) -> int:
        return self.peak_bytes

    def read_heap_bytes(self) -> int:
        return self.heap_bytes

    def collect(self) -> int:
        self.collections += 1
        self.events.append('collect')
        return 0

    def trim_heap(self) -> int:
        self.events.append('trim')
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


def release_for(process: FakeProcess) -> AfterTestMemoryRelease:
    """Return a release collecting and trimming the fake process.

    Returns:
        The release.

    """
    return AfterTestMemoryRelease(collector=collector_for(process), trim_heap=process.trim_heap)


def test_the_heap_is_trimmed_after_every_test():
    """The free heap goes back to the system after every test, collected or not."""
    process = FakeProcess()
    release = release_for(process)

    release.after_test()
    release.after_test()

    assert process.events == ['trim', 'trim']


def test_the_heap_is_trimmed_after_the_collection():
    """A collection frees the garbage first, so the trim hands back what it freed too."""
    process = FakeProcess()
    release = release_for(process)

    process.peak_bytes += STEP_BYTES + 1
    release.after_test()

    assert process.events == ['collect', 'trim']


def test_without_a_trimmer_the_release_only_collects():
    """Off glibc Linux (macOS, musl) there is no trimmer: the release only collects."""
    process = FakeProcess()
    release = AfterTestMemoryRelease(collector=collector_for(process), trim_heap=None)

    process.peak_bytes += STEP_BYTES + 1
    release.after_test()

    assert process.events == ['collect']


def test_without_a_collector_the_release_only_trims():
    """A release with no collector (none on Windows) still trims, given a trimmer."""
    process = FakeProcess()
    release = AfterTestMemoryRelease(collector=None, trim_heap=process.trim_heap)

    release.after_test()

    assert process.events == ['trim']


def test_a_release_with_neither_does_nothing():
    """Windows has neither a collector nor a trimmer: the release does nothing, and is safe."""
    AfterTestMemoryRelease(collector=None, trim_heap=None).after_test()


def resident_bytes() -> int:
    """Return this process's resident memory, from Linux's ``/proc/self/statm``.

    Returns:
        The resident bytes.

    """
    resident_pages = int(Path('/proc/self/statm').read_text(encoding='utf-8').split()[1])
    return resident_pages * os.sysconf('SC_PAGE_SIZE')


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='malloc_trim is glibc only')
def test_the_trimmer_hands_freed_heap_back_to_the_system():
    """Blocks freed below the heap's top stay resident until the trim hands them back.

    glibc returns freed memory at the heap's top on its own, but not freed memory under a block
    still in use: thousands of small blocks freed beneath one kept block stay resident, which
    ``malloc_trim`` releases (glibc malloc/malloc.c ``mtrim``).
    """
    trim_heap = malloc_trimmer()
    assert trim_heap is not None
    # Small blocks (under the 128 KiB mmap threshold) come from the heap; 64 MiB of them
    blocks = [ctypes.create_string_buffer(4096) for _ in range(16 * 1024)]
    kept_at_the_top = ctypes.create_string_buffer(4096)
    for block in blocks:
        ctypes.memset(block, 1, 4096)
    del blocks
    before = resident_bytes()

    trim_heap()

    assert before - resident_bytes() >= 32 * 1024 * 1024
    del kept_at_the_top


def test_no_trimmer_off_linux():
    """Off Linux there is no malloc_trim: macOS's and Windows' allocators return memory."""
    assert malloc_trimmer(platform='darwin') is None
    assert malloc_trimmer(platform='win32') is None


def test_a_c_library_without_malloc_trim_gives_no_trimmer(mocker):
    """A Linux C library without glibc (musl) gives no trimmer."""
    mocker.patch('tests.garbage_collection.ctypes.CDLL', side_effect=OSError('no such library'))

    assert malloc_trimmer(platform='linux') is None


def test_a_glibc_without_the_call_gives_no_trimmer(mocker):
    """A C library that loads but has no malloc_trim gives no trimmer."""
    mocker.patch('tests.garbage_collection.ctypes.CDLL', return_value=object())

    assert malloc_trimmer(platform='linux') is None


def test_a_trimmer_calls_malloc_trim_keeping_no_padding(mocker):
    """The trimmer asks glibc to keep no padding at the heap's top (``malloc_trim(0)``)."""
    library = mocker.Mock()
    library.malloc_trim.return_value = 1
    mocker.patch('tests.garbage_collection.ctypes.CDLL', return_value=library)

    trim_heap = malloc_trimmer(platform='linux')

    assert trim_heap is not None
    assert trim_heap() == 1
    library.malloc_trim.assert_called_once_with(0)


def test_the_process_release_trims_with_this_platforms_trimmer(mocker):
    """The suite's release trims with ``malloc_trimmer``'s answer for this platform."""
    process = FakeProcess()
    mocker.patch('tests.garbage_collection.malloc_trimmer', return_value=process.trim_heap)

    process_memory_release().after_test()

    assert process.events == ['trim']


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


RELEASE_TESTS = """
import unittest


class TestInAClass:
    def setup_method(self):
        self.editor = object()

    def test_it(self):
        pass


def test_outside_a_class():
    pass


class TestCaseStyle(unittest.TestCase):
    def test_it(self):
        pass
"""


class Held:
    """Something a test class's instance holds (weak-referenceable, unlike object())."""


class NotAFunction(pytest.Item):
    """An item that is not a test function (as a non-Python test file's items are)."""

    def runtest(self) -> None:
        """Nothing to run."""


def test_a_finished_test_class_instance_is_emptied(pytester):
    """What a test put on its class instance is let go: pytest keeps the instance itself."""
    class_test = next(
        item for item in pytester.getitems(RELEASE_TESTS) if item.parent.name == 'TestInAClass'
    )
    held = Held()
    class_test.instance.editor = held
    held_reference = weakref.ref(held)
    del held

    release_test_instance(item=class_test)
    gc.collect()

    assert vars(class_test.instance) == {}
    assert held_reference() is None


def test_a_test_outside_a_class_has_nothing_to_release(pytester):
    """A module-level test function has no instance: releasing it does nothing."""
    item = next(
        item for item in pytester.getitems(RELEASE_TESTS) if item.name == 'test_outside_a_class'
    )
    assert item.instance is None

    release_test_instance(item=item)


def test_a_unittest_test_case_is_left_to_pytest(pytester):
    """A TestCase is left to pytest's unittest support, which releases it itself."""
    item = next(
        item for item in pytester.getitems(RELEASE_TESTS) if item.parent.name == 'TestCaseStyle'
    )
    test_case = item.instance
    test_case.kept = True

    release_test_instance(item=item)

    assert test_case.kept is True


def test_an_item_that_is_not_a_test_function_is_left_alone(pytester):
    """Only pytest's Function items have class instances."""
    module = pytester.getmodulecol(RELEASE_TESTS)
    item = NotAFunction.from_parent(module, name='not_a_function')

    release_test_instance(item=item)
