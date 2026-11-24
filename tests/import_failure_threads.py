"""A test that fails inside Python's import machinery reports every live thread, and who started it.

Triage tool for bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md: CircleCI's Windows job
once failed ``tests/test_ai_model_comparison.py`` with ``KeyError: 'httpcore2._synchronization'``
raised from ``<frozen importlib._bootstrap>``. importlib raises that when a module's entry leaves
``sys.modules`` while the module's own code is still running, which takes a second thread (a
``sys.modules`` restore elsewhere reproduces it exactly). The failure's traceback shows only the
importing thread, so this plugin adds the rest:

- While each test runs, every ``threading.Thread`` started is marked with that test's node id
  (``Thread.start`` is wrapped; a thread started outside a test is marked ``outside any test``).
- When a test's call fails with an exception raised from the import machinery, its report gains
  one section, ``live threads at the import failure``: each live thread's name, whether it is a
  daemon, the test that started it, and its current stack.

It adds nothing to a passing test, or to a failure raised elsewhere, and it logs nothing (warnings
are errors in this suite). The stacks are taken when the report is made, just after the test's
call ended, so a thread that finished in between is missing from them. Registered in the root
conftest.py's ``pytest_plugins``. Tests: tests/test_import_failure_threads.py.
"""

from __future__ import annotations

import sys
import threading
import traceback
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable
    from types import TracebackType

# Where CPython's import machinery runs (frozen modules have no file)
IMPORT_MACHINERY_FILENAMES = frozenset({
    '<frozen importlib._bootstrap>',
    '<frozen importlib._bootstrap_external>',
})

# The report section's title
SECTION_TITLE = 'live threads at the import failure'

# What a thread started outside any test is marked with
OUTSIDE_ANY_TEST = 'outside any test'

# The attribute a started thread carries: the node id of the test that started it
STARTED_DURING_ATTRIBUTE = '_glitchygames_started_during_test'


class RunningTest:
    """The node id of the test running now, for the threads it starts to be marked with."""

    def __init__(self) -> None:
        """Start with no test running."""
        self.node_id = OUTSIDE_ANY_TEST


RUNNING_TEST_KEY = pytest.StashKey[RunningTest]()


def raised_by_import_machinery(traceback_object: TracebackType | None) -> bool:
    """Tell whether an exception passed through CPython's import machinery.

    Args:
        traceback_object: The exception's traceback.

    Returns:
        True when any of its frames is in ``importlib._bootstrap`` (or ``_bootstrap_external``).

    """
    return any(
        frame.filename in IMPORT_MACHINERY_FILENAMES
        for frame in traceback.extract_tb(traceback_object)
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
    """Keep the running test's node id, and mark every thread started from now on."""
    running_test = RunningTest()
    config.stash[RUNNING_TEST_KEY] = running_test
    original_start = threading.Thread.start
    setattr(threading.Thread, 'start', marking_start(original_start, running_test))  # ruff: ignore[set-attr-with-constant] - replacing a method
    config.add_cleanup(lambda: setattr(threading.Thread, 'start', original_start))


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
    try:
        return (yield)
    finally:
        running_test.node_id = OUTSIDE_ANY_TEST


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    """Add the live threads to a call that failed inside the import machinery.

    Returns:
        The report, with the section added when the failure was the import machinery's.

    """
    del item
    report = yield
    if (
        call.when == 'call'
        and call.excinfo is not None
        and raised_by_import_machinery(call.excinfo.tb)
    ):
        report.sections.append((
            SECTION_TITLE,
            live_thread_report(threads=threading.enumerate(), frames=sys._current_frames()),  # type: ignore[reportPrivateUsage]
        ))
    return report
