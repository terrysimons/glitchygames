"""At a per-test limit (pytest-timeout's thread method), the test's children are stopped first.

The native run (noxfile.py ``_NATIVE_RUN_TIMEOUT_ARGUMENTS``) ends a test that runs past its
limit with pytest-timeout's thread method, which ends the worker with ``os._exit``: no
fixture teardown runs, so ``no_child_process_left_running`` (tests/harness.py) never stops what
the test started, and a child it was waiting on (a game replay in ``run_command``) was left
running with no parent (bugs/2026-11-20-process-stop-tests-failed-under-load.md, reproduced
2026-11-22). The controller's sweep (tests/child_process_guard.py ``controller_sweep_lines``)
catches only a child whose command line names the run's temporary directory.

This plugin starts pytest-timeout's thread-method timer itself: when it fires, every child the
recording guards hold (tests/child_process_guard.py ``RECORDING_GUARDS``: each running child,
every process in a group one led, their descendants) is killed and reaped, then
pytest-timeout's own expiry ends the worker as before. The signal method, and a run without
pytest-timeout or without a limit, are left to pytest-timeout alone.

The line naming what was stopped goes to the standard error the run started with
(tests/original_standard_error.py), taken when the plugin configures. Written to descriptor 2 (or
``sys.__stderr__``) it landed in the test's captured output and was lost whenever the test was
reported before pytest-timeout's dump read that capture (#287's Linux job 5171).
"""

from __future__ import annotations

import contextlib
import os
import threading
from typing import Any

import pytest
import pytest_timeout

from tests.child_process_guard import RECORDING_GUARDS
from tests.original_standard_error import original_standard_error

# pytest-timeout's method that ends the worker (the one this plugin times)
THREAD_METHOD = 'thread'
# Where each test's running timer is kept, to be cancelled when the test ends in time
CANCEL_TIMER = pytest.StashKey[threading.Timer]()
# The run's original standard error (a descriptor this plugin owns), taken at configure
ORIGINAL_STANDARD_ERROR = pytest.StashKey[int]()


def stop_the_recorded_children() -> list[str]:
    """Kill and reap what every recording guard's children left running.

    Returns:
        One line per process stopped, naming it.

    """
    return [
        f'pid {process.pid}: {process.command}'
        for guard in list(RECORDING_GUARDS)
        for process in guard.stop_leftovers()
    ]


def end_the_test(*, item: pytest.Item, settings: Any) -> None:
    """At the limit: stop the test's children, name them, then end the worker as pytest-timeout.

    Nothing is stopped while a debugger is attached, as pytest-timeout then does nothing.

    Args:
        item: The test past its limit.
        settings: pytest-timeout's settings for it.

    """
    if not settings.disable_debugger_detection and pytest_timeout.is_debugging():
        return
    try:
        stopped = stop_the_recorded_children()
    except Exception as error:  # ruff: ignore[blind-except] - the worker must still end below
        stopped = [f'stopping them failed: {error!r}']
    if stopped:
        # The run's original stderr: an xdist worker does not forward its terminal writer, and
        # descriptor 2 is the test's capture now. From this thread pytest's capture is not
        # touched (it is not thread-safe); a failed write must not keep the worker from ending
        message = '\n'.join([
            f'{item.nodeid} ran past its {settings.timeout:g} s limit; its children, stopped:',
            *(f'  {line}' for line in stopped),
        ])
        with contextlib.suppress(OSError):
            os.write(
                item.config.stash[ORIGINAL_STANDARD_ERROR],
                f'{message}\n'.encode(errors='replace'),
            )
    pytest_timeout.timeout_timer(item, settings)


def pytest_configure(config: pytest.Config) -> None:
    """Take the run's original standard error now, while pytest's capture still holds it."""
    config.stash[ORIGINAL_STANDARD_ERROR] = original_standard_error(config=config)


def pytest_unconfigure(config: pytest.Config) -> None:
    """Close the original standard error's duplicate this plugin took."""
    descriptor = config.stash.get(ORIGINAL_STANDARD_ERROR, None)
    if descriptor is not None:
        del config.stash[ORIGINAL_STANDARD_ERROR]
        os.close(descriptor)


@pytest.hookimpl(optionalhook=True, tryfirst=True)
def pytest_timeout_set_timer(item: pytest.Item, settings: Any) -> bool | None:
    """Time a thread-method limit here, so its expiry stops the test's children first.

    Returns:
        True when this plugin started the timer; None leaves it to pytest-timeout.

    """
    if settings.method != THREAD_METHOD:
        return None
    timer = threading.Timer(
        settings.timeout, end_the_test, kwargs={'item': item, 'settings': settings}
    )
    timer.name = f'{__name__} {item.nodeid}'
    item.stash[CANCEL_TIMER] = timer
    timer.start()
    return True


@pytest.hookimpl(optionalhook=True, tryfirst=True)
def pytest_timeout_cancel_timer(item: pytest.Item) -> bool | None:
    """Cancel the timer ``pytest_timeout_set_timer`` started for this test, if it did.

    Returns:
        True when this plugin's timer was cancelled; None leaves it to pytest-timeout.

    """
    timer = item.stash.get(CANCEL_TIMER, None)
    if timer is None:
        return None
    del item.stash[CANCEL_TIMER]
    timer.cancel()
    timer.join()
    return True
