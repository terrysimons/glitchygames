"""A test that leaves process-wide state changed fails by name, and the state is put back.

What a test leaves behind, every later test on its worker meets: a variable naming a deleted
temporary folder, key repeat turned on, a thread still running, a random state that makes the next
test's draws depend on the order. tests/harness.py starts a watch before each item's setup and
checks it after all of its teardown (a fixture is too early: pytest undoes ``mocker`` and
``monkeypatch`` after an autouse fixture's own teardown, and an undone patch can itself be the
leak). Each kind of state (``watch_process_state``) is put back where it can be, so one leak fails
one test.

What it judges: the environment (names only are told, never values), key repeat, live threads, the
global random states, the interpreter's settings (``SETTINGS``), logging and signal handlers. It
does not judge what pytest or the harness puts back itself (warnings filters, sys.stdout, the SDL
driver variables, faulthandler, child processes), nor what running an engine changes, which is
reset (tests/engine_written_state.py).

Limits: a fixture wider than one test must not hold a change of these states between its tests (its
first test would be failed, and the state put back under it). The umask is not read (reading it
sets it), nor open files, SDL's input grab or asyncio's event loop policy. A NullHandler is not a
change: a library adds its own as it is imported, which a test may be the first to do. In a run
with pytest-timeout's signal method a failing test is also told its SIGALRM handler was changed:
pytest-timeout cancels its timer as the failure is reported (our runs use its thread method).
"""

from __future__ import annotations

import contextlib
import gc
import logging
import os
import random
import signal
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pygame

from glitchygames import clock

if TYPE_CHECKING:
    from collections.abc import Callable

    # Compares the state with its start, puts back what differs, and describes each difference
    type LeakCheck = Callable[[], list[str]]

# The process's environment itself (a test may replace the name os.environ), and the dictionary it
# keeps the encoded names and values in: copying that decodes nothing, a 60th of dict(os.environ)
ENVIRONMENT = os.environ
RAW_ENVIRONMENT: dict[Any, Any] = vars(ENVIRONMENT)['_data']
# pytest's own: the test and phase running
PYTEST_CURRENT_TEST = 'PYTEST_CURRENT_TEST'
# How long all of a test's leftover threads together may take to end. Only a test that leaves one
# waits. Short, so a stop that is slow fails as one that never comes does (the AI link once slept on
# for up to a second after its stop gave up). Windows needs longer: a connect to a closed loopback
# port, which no stop can end, takes seconds there (CI job 4022)
THREAD_GRACE_SECONDS = 5.0 if sys.platform == 'win32' else 0.5
# Key repeat as pygame starts: off
NO_KEY_REPEAT = (0, 0)
# What numpy.random's own functions draw from
NUMPY_GLOBAL_RANDOM = np.random.mtrand._rand
# The signals whose handlers Python can read and set
SIGNALS = sorted(signal.valid_signals())


def environment_holds(*, name: str, value: str | None) -> bool:
    """Return whether a variable holds a value, for a test to assert.

    Never assert on os.environ itself (``in``, ``get``, an argument): pytest prints all of it, every
    secret, when that fails. tests/test_leaked_state_guard.py looks for such assertions: a tripwire,
    not a proof (it sees no alias of os.environ).

    Args:
        name: The variable.
        value: What it must hold; None when it must not be set.

    Returns:
        Whether it does.

    """
    return ENVIRONMENT.get(name) == value


def watch_environment() -> LeakCheck:
    """Watch os.environ, raw.

    Returns:
        The check; it tells names only, as a value may be a secret.

    """
    before = RAW_ENVIRONMENT.copy()

    def check() -> list[str]:
        leaks: list[str] = []
        if before == RAW_ENVIRONMENT:
            return leaks
        for raw_name in sorted(before.keys() | RAW_ENVIRONMENT.keys()):
            if before.get(raw_name) == RAW_ENVIRONMENT.get(raw_name):
                continue
            name = ENVIRONMENT.decodekey(raw_name)
            if name == PYTEST_CURRENT_TEST:
                continue
            if raw_name not in before:
                change = 'set'
                del ENVIRONMENT[name]
            else:
                change = 'changed' if raw_name in RAW_ENVIRONMENT else 'removed'
                ENVIRONMENT[name] = ENVIRONMENT.decodevalue(before[raw_name])
            leaks.append(f'the environment variable {name} was {change}')
        return leaks

    return check


def key_repeat() -> tuple[int, int]:
    """Return key repeat's delay and interval; off when there is no display to have any.

    Returns:
        Both in milliseconds.

    """
    return pygame.key.get_repeat() if pygame.display.get_init() else NO_KEY_REPEAT


def watch_key_repeat() -> LeakCheck:
    """Watch key repeat (a text box turns it on when it gets the focus).

    Returns:
        The check.

    """
    before = key_repeat()

    def check() -> list[str]:
        after = key_repeat()
        # A test that quit pygame left no key repeat to put back
        if after == before or not pygame.display.get_init():
            return []
        pygame.key.set_repeat(*before)
        return [f'key repeat was {before} and is {after}']

    return check


def watch_threads() -> LeakCheck:
    """Watch the threads Python started (a C thread's stand-in, ``_DummyThread``, has no end).

    Returns:
        The check; a thread cannot be ended, so the next test's watch starts with it.

    """
    before = set(threading.enumerate())

    def check() -> list[str]:
        started = [
            thread
            for thread in threading.enumerate()
            if thread not in before and not isinstance(thread, threading._DummyThread)
        ]
        deadline = clock.raw_counter_seconds() + THREAD_GRACE_SECONDS
        for thread in started:
            thread.join(timeout=max(0.0, deadline - clock.raw_counter_seconds()))
        return [f'the thread {thread.name!r} still runs' for thread in started if thread.is_alive()]

    return check


def numpy_random_state() -> dict[str, Any]:
    """Read numpy's global random state.

    Returns:
        What its ``set_state`` takes.

    """
    return dict(NUMPY_GLOBAL_RANDOM.get_state(legacy=False))


def same_numpy_state(one: dict[str, Any], other: dict[str, Any]) -> bool:
    """Compare two of numpy's random states: == has no one answer for their arrays.

    Returns:
        Whether they are the same.

    """
    return (one['has_gauss'], one['gauss']) == (other['has_gauss'], other['gauss']) and all(
        np.array_equal(part, other['state'][name]) for name, part in one['state'].items()
    )


def watch_global_random(*, reseeded_for_each_test: bool) -> LeakCheck:
    """Watch the global random states: the standard library's and numpy's.

    Args:
        reseeded_for_each_test: Whether pytest-randomly seeds both as each test starts and ends
            (a shuffled run): no state then reaches the next test, and each differs here.

    Returns:
        The check.

    """
    if reseeded_for_each_test:
        return list
    before = random.getstate()
    numpy_generator = NUMPY_GLOBAL_RANDOM._bit_generator
    numpy_before = numpy_random_state()

    def check() -> list[str]:
        leaks: list[str] = []
        if random.getstate() != before:
            random.setstate(before)
            leaks.append("random's global state moved (draw from a random.Random)")
        if NUMPY_GLOBAL_RANDOM._bit_generator is not numpy_generator:
            # First: another kind of generator has another state, which ours is not compared with
            np.random.set_bit_generator(numpy_generator)
            leaks.append("numpy.random's bit generator was replaced")
        if not same_numpy_state(numpy_random_state(), numpy_before):
            NUMPY_GLOBAL_RANDOM.set_state(numpy_before)
            leaks.append("numpy.random's global state moved (draw from numpy's default_rng)")
        return leaks

    return check


def current_directory() -> Path | None:
    """Return the working directory, or None when it has been deleted.

    Returns:
        Its path.

    """
    with contextlib.suppress(FileNotFoundError):
        return Path.cwd()
    return None


def put_back_directory(directory: Path | None) -> None:
    """Go back to a working directory, unless there was none."""
    if directory is not None:
        os.chdir(directory)


def put_back_collecting(enabled: object) -> None:
    """Turn the garbage collector on or off."""
    if enabled:
        gc.enable()
    else:
        gc.disable()


def put_back_thresholds(thresholds: tuple[int, int, int]) -> None:
    """Put the garbage collector's thresholds back."""
    gc.set_threshold(*thresholds)


def attribute(owner: object, name: str) -> tuple[Callable[[], Any], Callable[[Any], None]]:
    """Return what reads and what puts back an attribute.

    Returns:
        Both functions.

    """
    return (lambda: getattr(owner, name), lambda value: setattr(owner, name, value))


# The interpreter's settings: each one's name, what reads it and what puts it back
SETTINGS: tuple[tuple[str, Callable[[], Any], Callable[[Any], None]], ...] = (
    # Which object os.environ is: comparing two would decode every variable
    (
        'os.environ (the object itself)',
        lambda: os.environ is ENVIRONMENT,
        lambda _same: attribute(os, 'environ')[1](ENVIRONMENT),
    ),
    ('sys.excepthook', *attribute(sys, 'excepthook')),
    ('sys.unraisablehook', *attribute(sys, 'unraisablehook')),
    ('sys.displayhook', *attribute(sys, 'displayhook')),
    ('threading.excepthook', *attribute(threading, 'excepthook')),
    ('the recursion limit', sys.getrecursionlimit, sys.setrecursionlimit),
    ('the working directory', current_directory, put_back_directory),
    ('whether the garbage collector runs', gc.isenabled, put_back_collecting),
    ('the garbage collector thresholds', gc.get_threshold, put_back_thresholds),
)


def watch_settings() -> LeakCheck:
    """Watch the interpreter's settings.

    Returns:
        The check.

    """
    before = [read() for _name, read, _put_back in SETTINGS]

    def check() -> list[str]:
        leaks: list[str] = []
        for (name, read, put_back), value in zip(SETTINGS, before, strict=True):
            if read() != value:
                put_back(value)
                leaks.append(f'{name} changed')
        return leaks

    return check


def watch_list(*, name: str) -> LeakCheck:
    """Watch a list of sys's: which object it is, and what it holds.

    Args:
        name: Its name in sys.

    Returns:
        The check.

    """
    original: list[str] = getattr(sys, name)
    before = original.copy()

    def check() -> list[str]:
        if getattr(sys, name) is original and original == before:
            return []
        original[:] = before
        setattr(sys, name, original)
        return [f'sys.{name} changed']

    return check


type LoggerState = tuple[int, bool, bool, tuple[logging.Handler, ...], tuple[Any, ...]]
# A logger nothing has set: the state, before a test, of one made during it
UNSET_LOGGER: LoggerState = (logging.NOTSET, True, False, (), ())


def logger_state(*, logger: logging.Logger) -> LoggerState:
    """Return a logger's level, propagation, disabling, handlers (no NullHandler) and filters.

    Returns:
        Its state.

    """
    handlers = tuple(
        handler for handler in logger.handlers if not isinstance(handler, logging.NullHandler)
    )
    return (logger.level, logger.propagate, logger.disabled, handlers, tuple(logger.filters))


def loggers_set() -> dict[str, LoggerState]:
    """Return the state of the root logger, and of each other one something has set.

    Returns:
        The states by name (the root's is 'root').

    """
    states = {logging.root.name: logger_state(logger=logging.root)}
    # A copy: another thread may be making a logger
    for name, logger in list(logging.root.manager.loggerDict.items()):
        if isinstance(logger, logging.Logger):
            state = logger_state(logger=logger)
            if state != UNSET_LOGGER:
                states[name] = state
    return states


def put_back_logger(*, logger: logging.Logger, state: LoggerState) -> None:
    """Set a logger as it was; its NullHandlers stay."""
    level, logger.propagate, logger.disabled, handlers, filters = state
    logger.setLevel(level)
    for handler in logger_state(logger=logger)[3]:
        logger.removeHandler(handler)
    for handler in handlers:
        logger.addHandler(handler)
    logger.filters[:] = filters


def watch_logging() -> LeakCheck:
    """Watch every logger's settings, and logging.disable.

    Returns:
        The check.

    """
    before = loggers_set()
    disabled_before = logging.root.manager.disable

    def check() -> list[str]:
        leaks: list[str] = []
        if logging.root.manager.disable != disabled_before:
            logging.disable(disabled_before)
            leaks.append('logging.disable was called')
        after = loggers_set()
        if after == before:
            return leaks
        for name in sorted(before.keys() | after.keys()):
            state = before.get(name, UNSET_LOGGER)
            if after.get(name, UNSET_LOGGER) != state:
                put_back_logger(logger=logging.getLogger(name), state=state)
                leaks.append(f'the logger {name!r} was changed (level, handlers, filters, ...)')
        return leaks

    return check


def watch_signals() -> LeakCheck:
    """Watch the signal handlers set from Python.

    Returns:
        The check.

    """
    before = [signal.getsignal(number) for number in SIGNALS]

    def check() -> list[str]:
        leaks: list[str] = []
        for number, handler in zip(SIGNALS, before, strict=True):
            if signal.getsignal(number) != handler:
                # None: a handler not set from Python, which cannot be put back
                if handler is not None:
                    signal.signal(number, handler)
                leaks.append(f'the handler of signal {int(number)} was changed')
        return leaks

    return check


def watch_process_state(
    *, random_reseeded_for_each_test: bool, reset: Callable[[], None]
) -> LeakCheck:
    """Start watching every kind of state, changing none.

    Args:
        random_reseeded_for_each_test: As ``watch_global_random`` takes it.
        reset: Resets what no test is failed for (tests/engine_written_state.py).

    Returns:
        The check: each difference from now, put back where it can be. It waits for the test's
        threads first, so what one changes as it ends is seen, then resets.

    """
    check_threads = watch_threads()
    checks = [
        watch_environment(),
        watch_key_repeat(),
        watch_global_random(reseeded_for_each_test=random_reseeded_for_each_test),
        watch_settings(),
        watch_list(name='path'),
        watch_list(name='argv'),
        watch_logging(),
        watch_signals(),
    ]

    def check() -> list[str]:
        thread_leaks = check_threads()
        reset()
        return thread_leaks + [leak for check_kind in checks for leak in check_kind()]

    return check


def leak_message(*, test: str, leaks: list[str]) -> str:
    """Say which test left what.

    Args:
        test: The test's node id.
        leaks: What the check returned.

    Returns:
        The failure's text.

    """
    named = '\n'.join(f'  {leak}' for leak in leaks)
    return (
        f'{test} left process-wide state changed for the tests after it '
        f'(put back, but for a thread):\n{named}'
    )
