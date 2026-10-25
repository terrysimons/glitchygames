"""Free a test's garbage before the next test allocates, when memory climbs (BUGS.md #85).

A finished test's scene, sprites and groups are reference cycles (pygame's sprite <-> group
links), so they wait for the cycle collector. It runs by object counts, not bytes, and these
few Python objects hold megabytes of SDL surfaces, so a serial run piled them up past the Linux
CI job's 2 GB: 2.3 GB peak. Collecting after every test fixed that but took 27 minutes over the
suite. Collecting only when the process's peak has grown ``COLLECTION_STEP_BYTES`` since the
last collection costs about 6 s in 44 collections and keeps the peak at 1.4 GB (macOS, serial,
coverage on, 2026-10-24); between those, freed memory is reused and the peak does not move.

``tests/harness.py``'s ``pytest_runtest_logfinish`` calls ``after_test`` once per test: by
then pytest has dropped the test's fixture values, so its scene is garbage. Never
``gc.freeze()`` here: Hypothesis warns about a ``register_random`` object frozen out of view.
"""

from __future__ import annotations

import gc
import sys
from typing import TYPE_CHECKING, Self

try:
    import resource
except ImportError:  # Windows has no resource module
    resource = None

if TYPE_CHECKING:
    from collections.abc import Callable

COLLECTION_STEP_BYTES = 16 * 1024 * 1024


class PeakMemoryCollector:
    """Collects garbage after a test whenever the peak grew more than a step since the last."""

    def __init__(
        self: Self,
        *,
        step_bytes: int,
        read_peak_bytes: Callable[[], int],
        collect: Callable[[], int] = gc.collect,
    ) -> None:
        """Remember the peak now; the first step counts from here.

        Args:
            step_bytes: How far the peak may grow before a collection.
            read_peak_bytes: Returns the process's peak resident memory in bytes.
            collect: Runs the cycle collector.

        """
        self._step_bytes = step_bytes
        self._read_peak_bytes = read_peak_bytes
        self._collect = collect
        self._peak_at_last_collection = read_peak_bytes()

    def after_test(self: Self) -> bool:
        """Collect if the peak grew more than a step since the last collection.

        Returns:
            Whether it collected.

        """
        if self._read_peak_bytes() - self._peak_at_last_collection <= self._step_bytes:
            return False
        self._collect()
        self._peak_at_last_collection = self._read_peak_bytes()
        return True


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

    return PeakMemoryCollector(step_bytes=COLLECTION_STEP_BYTES, read_peak_bytes=read_peak_bytes)
