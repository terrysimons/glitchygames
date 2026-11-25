"""Keep faulthandler on from one test to the next (used by tests/harness.py's autouse fixture).

pytest turns faulthandler on for the whole run, so a crash prints every thread's traceback. A test
that leaves it off takes that from every later test on its worker, and fails any that reads it
(bugs/2026-11-24-faulthandler-test-reads-the-process-state.md). A pytest run inside a test does
so when it ends before its own faulthandler plugin is configured: the plugin's cleanup still turns
faulthandler off, and has nothing saved to turn back on.
"""

from __future__ import annotations

import contextlib
import sys

# The functions themselves: a test's fake of faulthandler's may still be in place when its
# teardown is checked (the fatal-signal tests fake is_enabled and enable)
from faulthandler import enable, is_enabled
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

LEFT_OFF = (
    'the test left faulthandler off (now on again): a crash later on this worker would print no '
    'traceback. A pytest run inside a test that ends while it is being configured does this; '
    'give that run `-p no:faulthandler`'
)


@contextlib.contextmanager
def faulthandler_left_on() -> Generator[None]:
    """Fail the test inside if it turned faulthandler off, after turning it back on.

    Faulthandler that was off before is left as it is (a run with ``-p no:faulthandler``). It comes
    back on the process's own stderr: Python does not say which stream it was writing to.

    Yields:
        None, while the test runs.

    """
    was_on = is_enabled()
    try:
        yield
    finally:
        turned_off = was_on and not is_enabled()
        # None in a process with no stderr, where there is nowhere to write
        if turned_off and sys.__stderr__ is not None:
            enable(file=sys.__stderr__)
    if turned_off:
        pytest.fail(LEFT_OFF, pytrace=False)
