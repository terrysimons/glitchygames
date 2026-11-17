"""Measure what each test file keeps in the test process, for memory triage.

A test file's "kept" is how much this process's resident memory grew from the file's first test
to its last, with garbage collected at both ends; its "peak rise" is the most it held above that
start while its tests ran (read after every test, without collecting). Both are this process
only: children a test starts are not counted (tests/memory_guard.py reads the container's).

Off unless ``GLITCHYGAMES_MEMORY_BY_FILE`` names the JSON file to write; the rows are rewritten
after every file, so a run stopped part way (the memory guard, a kill) still leaves its rows.
Resident memory comes from ``/proc/self/statm`` on Linux and ``task_info`` on macOS; elsewhere the
plugin does nothing and says so once.

Kept for later triage (the owner, 2026-11-17: "Keep that plugin if it works").
"""

from __future__ import annotations

import ctypes
import gc
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

OUTPUT_VARIABLE = 'GLITCHYGAMES_MEMORY_BY_FILE'
MEBIBYTE = 1024 * 1024
PROC_STATM = Path('/proc/self/statm')
# task_info's flavor for mach_task_basic_info (<mach/task_info.h>)
MACH_TASK_BASIC_INFO = 20


class _MachTaskBasicInfo(ctypes.Structure):
    _fields_ = (
        ('virtual_size', ctypes.c_uint64),
        ('resident_size', ctypes.c_uint64),
        ('resident_size_max', ctypes.c_uint64),
        ('user_time', ctypes.c_uint64),
        ('system_time', ctypes.c_uint64),
        ('policy', ctypes.c_int),
        ('suspend_count', ctypes.c_int),
    )


def _linux_resident_mebibytes() -> float:
    resident_pages = int(PROC_STATM.read_text(encoding='ascii').split()[1])
    return resident_pages * os.sysconf('SC_PAGE_SIZE') / MEBIBYTE


def _macos_resident_mebibytes() -> float:
    system = ctypes.CDLL('/usr/lib/libSystem.dylib')
    info = _MachTaskBasicInfo()
    count = ctypes.c_uint(ctypes.sizeof(info) // ctypes.sizeof(ctypes.c_uint))
    system.task_info(
        system.mach_task_self(), MACH_TASK_BASIC_INFO, ctypes.byref(info), ctypes.byref(count)
    )
    return info.resident_size / MEBIBYTE


def resident_reader() -> Callable[[], float] | None:
    """This platform's resident-memory reader, or None where there is none.

    Returns:
        A function returning this process's resident memory in MiB, or None.
    """
    if sys.platform == 'linux' and PROC_STATM.exists():
        return _linux_resident_mebibytes
    if sys.platform == 'darwin':
        return _macos_resident_mebibytes
    return None


class FileMemoryRecorder:
    """Rows of what each test file kept, written to ``output`` after every file.

    Registered as a pytest plugin by ``pytest_configure``: its ``pytest_*`` methods are hooks.
    """

    def __init__(self, *, output: Path, read_resident: Callable[[], float]) -> None:
        """Record to ``output``, reading resident memory with ``read_resident``.

        Args:
            output: The JSON file the rows are written to.
            read_resident: Returns this process's resident memory in MiB.
        """
        self.output = output
        self.read_resident = read_resident
        self.file: str | None = None
        self.start = 0.0
        self.peak = 0.0
        self.rows: list[dict[str, object]] = []

    def pytest_runtest_logstart(self, nodeid: str) -> None:
        """At a new file's first test, finish the last file and start measuring this one.

        Args:
            nodeid: The starting test's id.
        """
        file = nodeid.split('::', maxsplit=1)[0]
        if file == self.file:
            return
        self.finish_file()
        gc.collect()
        self.file = file
        self.start = self.read_resident()
        self.peak = self.start

    def pytest_runtest_logfinish(self) -> None:
        """After each test, note the most the process has held during this file."""
        self.peak = max(self.peak, self.read_resident())

    def pytest_sessionfinish(self) -> None:
        """Finish the last file."""
        self.finish_file()

    def finish_file(self) -> None:
        """Append the current file's row and rewrite the output, if a file is being measured."""
        if self.file is None:
            return
        gc.collect()
        after = self.read_resident()
        self.rows.append({
            'file': self.file,
            'kept': round(after - self.start, 1),
            'peak_rise': round(self.peak - self.start, 1),
            'after': round(after, 1),
        })
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.rows, indent=1), encoding='utf-8')
        self.file = None


def pytest_configure(config: pytest.Config) -> None:
    """Register a recorder when ``GLITCHYGAMES_MEMORY_BY_FILE`` names an output file.

    Args:
        config: pytest's configuration.
    """
    output = os.environ.get(OUTPUT_VARIABLE, '').strip()
    if not output:
        return
    reader = resident_reader()
    if reader is None:
        sys.stderr.write(f'memory_by_file: no resident-memory reader on {sys.platform}; off\n')
        return
    config.pluginmanager.register(
        FileMemoryRecorder(output=Path(output), read_resident=reader), name='memory_by_file'
    )
