"""Free a test's garbage before the next test allocates, when memory climbs (BUGS.md #85).

A finished test's scene, sprites and groups are reference cycles (pygame's sprite <-> group
links), so they wait for the cycle collector. It runs by object counts, not bytes, and these
few Python objects hold megabytes of SDL surfaces, so a serial run piled them up past the Linux
CI job's 2 GB: 2.3 GB peak. Collecting after every test fixed that but took 27 minutes over the
suite. Collecting only when the process's peak has grown ``COLLECTION_STEP_BYTES`` since the
last collection costs about 6 s in 44 collections and keeps the peak at 1.4 GB (macOS, serial,
coverage on, 2026-10-24); between those, freed memory is reused and the peak does not move.

The peak alone let garbage fill the process up to whatever its peak had been: after one large
test, later tests' scenes piled up uncollected until they reached that peak, so the process sat
there, and a replay child the suite started then counted on top of it in the Linux job's
container (2026-10-28: pytest at about 1.1 GB beside a 322 MiB replay child). So a second
trigger reads malloc's bytes in use (``malloc_bytes_in_use_reader``: glibc's ``mallinfo2``,
macOS's ``mstats``), where the SDL surfaces live: when they grew ``HEAP_COLLECTION_STEP_BYTES``
since the last collection, it collects too. Brave Adventurer's both-editions tests alone (macOS,
150 tests): 483 MiB resident at the end with the peak trigger only, 353 MiB with both (33
collections, about 1 s), 303 MiB collecting after every test.

pytest keeps every test function's class instance for the whole run (``Function.instance``,
pytest 9.1: each test gets a fresh one, and the item holds it), so whatever a test class's
``setup_method`` put on ``self`` stayed alive to the end, whatever the collector did: after
Bitmappy's tests, 79 ``BitmapEditorScene``s and 230 MiB of their surfaces (macOS), the Linux
job's serial run climbing to its peak in its last tests. ``release_test_instance`` empties the
instance once the test's reports are made; then 3 MiB of surfaces were left.

``tests/harness.py``'s ``pytest_runtest_protocol`` wrapper calls ``release_test_instance``, then
``after_test``, once per test: by then pytest has dropped the test's fixture values, so its
scene is garbage. Never ``gc.freeze()`` here: Hypothesis warns about a ``register_random``
object frozen out of view.
"""

from __future__ import annotations

import ctypes
import gc
import sys
import unittest
from typing import TYPE_CHECKING, Self

import pytest

try:
    import resource
except ImportError:  # Windows has no resource module
    resource = None

if TYPE_CHECKING:
    from collections.abc import Callable

COLLECTION_STEP_BYTES = 16 * 1024 * 1024
HEAP_COLLECTION_STEP_BYTES = 32 * 1024 * 1024
# The C libraries that report malloc's bytes in use, by platform
GLIBC_NAME = 'libc.so.6'
MACOS_SYSTEM_LIBRARY = '/usr/lib/libSystem.B.dylib'


class PeakMemoryCollector:
    """Collects garbage after a test when the peak, or malloc's bytes in use, grew a step."""

    def __init__(
        self: Self,
        *,
        step_bytes: int,
        read_peak_bytes: Callable[[], int],
        collect: Callable[[], int] = gc.collect,
        read_heap_bytes: Callable[[], int] | None = None,
        heap_step_bytes: int = HEAP_COLLECTION_STEP_BYTES,
    ) -> None:
        """Remember the peak (and the heap) now; the first steps count from here.

        Args:
            step_bytes: How far the peak may grow before a collection.
            read_peak_bytes: Returns the process's peak resident memory in bytes.
            collect: Runs the cycle collector.
            read_heap_bytes: Returns malloc's bytes in use, or None to watch the peak alone.
            heap_step_bytes: How far malloc's bytes in use may grow before a collection.

        """
        self._step_bytes = step_bytes
        self._read_peak_bytes = read_peak_bytes
        self._collect = collect
        self._read_heap_bytes = read_heap_bytes
        self._heap_step_bytes = heap_step_bytes
        self._peak_at_last_collection = read_peak_bytes()
        self._heap_at_last_collection = 0 if read_heap_bytes is None else read_heap_bytes()

    def _heap_grew_a_step(self: Self) -> bool:
        if self._read_heap_bytes is None:
            return False
        return self._read_heap_bytes() - self._heap_at_last_collection > self._heap_step_bytes

    def after_test(self: Self) -> bool:
        """Collect if the peak, or malloc's bytes in use, grew more than a step since the last.

        Returns:
            Whether it collected.

        """
        peak_grew = self._read_peak_bytes() - self._peak_at_last_collection > self._step_bytes
        if not peak_grew and not self._heap_grew_a_step():
            return False
        self._collect()
        self._peak_at_last_collection = self._read_peak_bytes()
        if self._read_heap_bytes is not None:
            self._heap_at_last_collection = self._read_heap_bytes()
        return True


class _GlibcMallinfo2(ctypes.Structure):
    """glibc's ``struct mallinfo2`` (malloc.h, glibc 2.33 and later): ten ``size_t`` fields."""

    _fields_ = (
        ('arena', ctypes.c_size_t),
        ('ordblks', ctypes.c_size_t),
        ('smblks', ctypes.c_size_t),
        ('hblks', ctypes.c_size_t),
        ('hblkhd', ctypes.c_size_t),
        ('usmblks', ctypes.c_size_t),
        ('fsmblks', ctypes.c_size_t),
        ('uordblks', ctypes.c_size_t),
        ('fordblks', ctypes.c_size_t),
        ('keepcost', ctypes.c_size_t),
    )


class _MacosMstats(ctypes.Structure):
    """macOS's ``struct mstats`` (malloc/malloc.h): five ``size_t`` fields."""

    _fields_ = (
        ('bytes_total', ctypes.c_size_t),
        ('chunks_used', ctypes.c_size_t),
        ('bytes_used', ctypes.c_size_t),
        ('chunks_free', ctypes.c_size_t),
        ('bytes_free', ctypes.c_size_t),
    )


def _macos_bytes_in_use_reader() -> Callable[[], int]:
    mstats = ctypes.CDLL(MACOS_SYSTEM_LIBRARY).mstats
    mstats.restype = _MacosMstats
    mstats.argtypes = ()

    def read_macos_bytes_in_use() -> int:
        return mstats().bytes_used

    return read_macos_bytes_in_use


def _glibc_bytes_in_use_reader() -> Callable[[], int]:
    mallinfo2 = ctypes.CDLL(GLIBC_NAME).mallinfo2
    mallinfo2.restype = _GlibcMallinfo2
    mallinfo2.argtypes = ()

    def read_glibc_bytes_in_use() -> int:
        information = mallinfo2()
        return information.uordblks + information.hblkhd

    return read_glibc_bytes_in_use


def malloc_bytes_in_use_reader(*, platform: str = sys.platform) -> Callable[[], int] | None:
    """Return a reader of malloc's bytes in use (what the SDL surfaces take), where there is one.

    On Linux (glibc), ``mallinfo2``: the heap's bytes in use (``uordblks``) plus the large
    blocks malloc mapped on their own (``hblkhd``). On macOS, ``mstats``'s ``bytes_used``.
    Neither counts Python's own small objects (pymalloc maps its arenas itself): the peak
    trigger covers those.

    Args:
        platform: ``sys.platform``.

    Returns:
        The reader (bytes), or None elsewhere (Windows, or a C library without the call).

    """
    if platform == 'darwin':
        make_reader = _macos_bytes_in_use_reader
    elif platform.startswith('linux'):
        make_reader = _glibc_bytes_in_use_reader
    else:
        return None
    try:
        return make_reader()
    except OSError, AttributeError:
        # No such library (musl), or no such call (glibc before 2.33)
        return None


def release_test_instance(*, item: pytest.Item) -> None:
    """Empty a finished test's class instance, which pytest keeps for the rest of the run.

    Call it once the test's reports are made (its teardown, ``teardown_method`` included, has
    run). A test function outside a class has no instance, and a ``unittest.TestCase`` is left
    to pytest's unittest support, which releases it itself.

    Args:
        item: The finished test.

    """
    if not isinstance(item, pytest.Function):
        return
    instance: object = item.instance
    if instance is None or isinstance(instance, unittest.TestCase):
        return
    vars(instance).clear()


def process_peak_memory_collector() -> PeakMemoryCollector | None:
    """Return this process's collector, off Windows: every run's, the native coreaudio run too.

    A local run's native child (cocoa with coreaudio, next to the dummy run) once stalled about
    30 s at a time and lost its mixer with these collections, so only dummy-audio runs
    collected. That no longer reproduces in any configuration tried, the original command
    included (BUGS.md #212's record), so every run's memory is bounded again.

    Returns:
        The collector, or None on Windows (no ``resource`` module; its CI has the memory).

    """
    if resource is None:
        return None
    # ru_maxrss is bytes on macOS and kibibytes on Linux
    scale = 1 if sys.platform == 'darwin' else 1024

    # Read here, past the None check (a nested function would not see it narrowed)
    get_resource_usage = resource.getrusage
    this_process = resource.RUSAGE_SELF

    def read_peak_bytes() -> int:
        return get_resource_usage(this_process).ru_maxrss * scale

    return PeakMemoryCollector(
        step_bytes=COLLECTION_STEP_BYTES,
        read_peak_bytes=read_peak_bytes,
        read_heap_bytes=malloc_bytes_in_use_reader(),
    )
