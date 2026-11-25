"""A test that fails inside Python's import machinery reports its threads and the known removals.

Triage tool for bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md: CircleCI's Windows job
once failed ``tests/test_ai_model_comparison.py`` with ``KeyError: 'httpcore2._synchronization'``
raised from ``<frozen importlib._bootstrap>``. importlib raises that when a module's entry leaves
``sys.modules`` while the module's own code is still running. Another thread can remove it (a
``sys.modules`` restore elsewhere reproduces the error exactly), and so can code the import itself
runs on the same thread (the module's own, or a finalizer). The failure's traceback shows neither,
so this plugin adds the rest:

- While each test runs, every ``threading.Thread`` started is marked with that test's node id
  (``Thread.start`` is wrapped; a thread started outside a test is marked ``outside any test``).
- While the run lasts, the known ways test code removes modules are recorded
  (tests/module_removals.py: what it records, and what it cannot see).
- When a test's setup, call or teardown fails with an exception raised from the import machinery,
  its report gains three sections: ``live threads at the import failure`` (each live thread's name,
  whether it is a daemon, the test that started it, and its current stack), ``recorded sys.modules
  removals`` (newest first, those overlapping an import marked) and ``sys.modules at the import
  failure`` (tests/import_failure_state.py: what is there under the failed module's package, whether
  the dictionary was rebound, and the garbage collector's state).

It adds nothing to a passing test, or to a failure raised elsewhere, and it logs nothing (warnings
are errors in this suite). The stacks are taken when the report is made, just after the test's
phase ended, so a thread that finished in between is missing from them. Registered in the root
conftest.py's ``pytest_plugins``. Tests: tests/test_import_failure_threads.py.
"""

from __future__ import annotations

import gc
import sys
import threading
import traceback
from typing import TYPE_CHECKING, Any

import pytest

from tests import import_failure_state, module_removals
from tests.module_removals import OUTSIDE_ANY_TEST

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable
    from types import TracebackType

# Where CPython's import machinery runs (frozen modules have no file)
IMPORT_MACHINERY_FILENAMES = frozenset({
    '<frozen importlib._bootstrap>',
    '<frozen importlib._bootstrap_external>',
})

# The report sections' titles
SECTION_TITLE = 'live threads at the import failure'
REMOVALS_SECTION_TITLE = 'recorded sys.modules removals'
STATE_SECTION_TITLE = 'sys.modules at the import failure'

# The attribute a started thread carries: the node id of the test that started it
STARTED_DURING_ATTRIBUTE = '_glitchygames_started_during_test'


class RunningTest:
    """The test running now: its node id, for the threads it starts, and where its gc began."""

    def __init__(self) -> None:
        """Start with no test running."""
        self.node_id = OUTSIDE_ANY_TEST
        self.collections_before = gc.get_stats()


RUNNING_TEST_KEY = pytest.StashKey[RunningTest]()
RECORDER_KEY = pytest.StashKey[module_removals.RemovalRecorder]()


def raised_by_import_machinery(traceback_object: TracebackType | None) -> bool:
    """Tell whether an exception passed through CPython's import machinery.

    Args:
        traceback_object: The exception's traceback.

    Returns:
        True when any of its frames is in ``importlib._bootstrap`` (or ``_bootstrap_external``).

    """
    return any(
        frame.f_code.co_filename in IMPORT_MACHINERY_FILENAMES
        for frame, _ in traceback.walk_tb(traceback_object)
    )


def started_during(thread: threading.Thread) -> str:
    """Return the node id of the test that started a thread.

    Returns:
        The node id, or ``outside any test`` (also for a thread started before this plugin).

    """
    return getattr(thread, STARTED_DURING_ATTRIBUTE, OUTSIDE_ANY_TEST)


def live_thread_report(*, threads: Iterable[threading.Thread], frames: dict[int, Any]) -> str:
    """Describe each live thread: name, daemon or not, the test that started it, its stack.

    Args:
        threads: The live threads (``threading.enumerate()``).
        frames: Each thread's current frame by ident (``sys._current_frames()``).

    Returns:
        One block per thread, in the order given.

    """
    blocks = []
    for thread in threads:
        kind = 'daemon' if thread.daemon else 'not a daemon'
        header = f'{thread.name} ({kind}), started during: {started_during(thread)}'
        frame = frames.get(thread.ident) if thread.ident is not None else None
        stack = ''.join(traceback.format_stack(frame)) if frame is not None else '  (no stack)\n'
        blocks.append(f'{header}\n{stack}')
    return '\n'.join(blocks)


class FaultAsLine:
    """Turns an exception raised while writing a section into the section's text."""

    def __init__(self, lines: list[str]) -> None:
        """Write into these lines."""
        self.lines = lines

    def __enter__(self) -> None:
        """Guard the writing of one section."""

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback_object: TracebackType | None,
    ) -> bool:
        """Add the fault's line.

        Returns:
            True for an ``Exception``; a ``KeyboardInterrupt`` or an exit goes on.

        """
        del error_type, traceback_object
        if isinstance(error, Exception):
            fault = ''.join(traceback.format_exception_only(error)).strip()
            self.lines.append(f'this section could not be written: {fault}')
            return True
        return False


def section_text(write: Callable[[], str]) -> str:
    """Write one section: a fault in the writing is its text, never an error of pytest's own.

    Returns:
        What the writer returns, or the fault.

    """
    lines: list[str] = []
    with FaultAsLine(lines):
        lines.append(write())
    return '\n'.join(lines)


def marking_start(
    original_start: Callable[[threading.Thread], None], running_test: RunningTest
) -> Callable[[threading.Thread], None]:
    """Wrap ``Thread.start`` so each thread is marked with the test running when it started.

    Args:
        original_start: ``threading.Thread.start`` as it was.
        running_test: Where the running test's node id is kept.

    Returns:
        The wrapper.

    """

    def start(thread: threading.Thread) -> None:
        setattr(thread, STARTED_DURING_ATTRIBUTE, running_test.node_id)
        original_start(thread)

    return start


def pytest_configure(config: pytest.Config) -> None:
    """Keep the running test's node id, mark every thread started, and record removals."""
    running_test = RunningTest()
    config.stash[RUNNING_TEST_KEY] = running_test
    original_start = threading.Thread.start
    setattr(threading.Thread, 'start', marking_start(original_start, running_test))  # ruff: ignore[set-attr-with-constant] - replacing a method
    config.add_cleanup(lambda: setattr(threading.Thread, 'start', original_start))
    recorder = module_removals.install()
    config.stash[RECORDER_KEY] = recorder
    config.add_cleanup(lambda: module_removals.release(recorder))


@pytest.hookimpl(wrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item, nextitem: pytest.Item | None
) -> Generator[None, object, object]:
    """Name this test as the running one while it runs (setup, call and teardown).

    Returns:
        The protocol's own result.

    """
    del nextitem
    running_test = item.config.stash[RUNNING_TEST_KEY]
    running_test.node_id = item.nodeid
    running_test.collections_before = gc.get_stats()
    # The recorder is the process's: a run inside a test gives the outer test's id back
    recorder = item.config.stash[RECORDER_KEY]
    outer_node_id = recorder.running_test_node_id
    recorder.running_test_node_id = item.nodeid
    try:
        return (yield)
    finally:
        running_test.node_id = OUTSIDE_ANY_TEST
        recorder.running_test_node_id = outer_node_id


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Add the sections to a setup, call or teardown that failed inside the import machinery.

    Returns:
        The report, with the sections added when the failure was the import machinery's.

    """
    report = yield
    if report.failed and call.excinfo is not None and raised_by_import_machinery(call.excinfo.tb):
        error, traceback_object = call.excinfo.value, call.excinfo.tb
        recorder = item.config.stash[RECORDER_KEY]
        running_test = item.config.stash[RUNNING_TEST_KEY]
        report.sections.extend((
            (
                SECTION_TITLE,
                section_text(
                    lambda: live_thread_report(
                        threads=threading.enumerate(),
                        frames=sys._current_frames(),  # type: ignore[reportPrivateUsage]
                    )
                ),
            ),
            (
                REMOVALS_SECTION_TITLE,
                section_text(lambda: module_removals.removals_report(recorder)),
            ),
            (
                STATE_SECTION_TITLE,
                section_text(
                    lambda: import_failure_state.modules_state_report(
                        error=error,
                        traceback_object=traceback_object,
                        startup_modules=recorder.startup_modules,
                        collections_before=running_test.collections_before,
                    )
                ),
            ),
        ))
    return report
