"""A test that leaves process-wide state changed fails by name (tests/leaked_state_guard.py).

Each kind of leak is planted in a real pytest run with the harness loaded, in this process, so
what is judged is this process's own state: a test that leaks, then one that must find the state
as it was.
"""

from __future__ import annotations

import gc
import logging
import os
import random
import signal
import sys
import threading
from typing import TYPE_CHECKING

import pygame
import pytest

from tests import leaked_state_guard
from tests.leaked_state_guard import (
    NUMPY_GLOBAL_RANDOM,
    numpy_random_state,
    watch_environment,
    watch_key_repeat,
    watch_process_state,
    watch_settings,
    watch_signals,
    watch_threads,
)

if TYPE_CHECKING:
    from collections.abc import Generator

# A variable no one sets, and the value planted in it: the failure must never show a value
PLANTED_VARIABLE = 'GLITCHYGAMES_PLANTED_LEAK'
PLANTED_VALUE = 'planted-secret-value'
# The time given to a planted thread that never ends
SHORT_GRACE_SECONDS = 0.05

# Each planted leak: its name, the leaking test's body, what the test after it asserts, and what the
# failure must tell. The names used are imported by INNER_HEADER
PLANTED_LEAKS = {
    'a variable set': (
        f"os.environ['{PLANTED_VARIABLE}'] = '{PLANTED_VALUE}'",
        f"'{PLANTED_VARIABLE}' not in os.environ",
        f'the environment variable {PLANTED_VARIABLE} was set',
    ),
    'a variable removed': (
        "del os.environ['PATH']",
        "os.environ['PATH']",
        'the environment variable PATH was removed',
    ),
    'a variable changed': (
        f"os.environ['PATH'] = '{PLANTED_VALUE}'",
        f"os.environ['PATH'] != '{PLANTED_VALUE}'",
        'the environment variable PATH was changed',
    ),
    'os.environ replaced': (
        'os.environ = dict(os.environ)',
        'os.environ is leaked_state_guard.ENVIRONMENT',
        'os.environ (the object itself) was changed',
    ),
    'key repeat': (
        'pygame.key.set_repeat(500, 50)',
        'pygame.key.get_repeat() == (0, 0)',
        'key repeat was (0, 0) and is (500, 50)',
    ),
    'a thread': (
        "threading.Thread(target=END_PLANTED_THREAD.wait, name='planted', daemon=True).start()",
        'True',
        "the thread 'planted' still runs",
    ),
    'random': (
        'random.random()',
        'random.getstate() == RANDOM_BEFORE',
        "random's global state moved",
    ),
    'numpy.random': (
        'np.random.random()',
        'numpy_random_is_as_before()',
        "numpy.random's global state moved",
    ),
    'sys.excepthook': (
        'sys.excepthook = print',
        'sys.excepthook is not print',
        'sys.excepthook was changed',
    ),
    'sys.unraisablehook': (
        'sys.unraisablehook = print',
        'sys.unraisablehook is not print',
        'sys.unraisablehook was changed',
    ),
    'sys.displayhook': (
        'sys.displayhook = print',
        'sys.displayhook is not print',
        'sys.displayhook was changed',
    ),
    'threading.excepthook': (
        'threading.excepthook = print',
        'threading.excepthook is not print',
        'threading.excepthook was changed',
    ),
    'sys.path': (
        "sys.path.append('/planted')",
        "'/planted' not in sys.path",
        'sys.path was changed',
    ),
    'sys.argv': (
        "sys.argv.append('--planted')",
        "'--planted' not in sys.argv",
        'sys.argv was changed',
    ),
    'the recursion limit': (
        'sys.setrecursionlimit(1999)',
        'sys.getrecursionlimit() != 1999',
        'the recursion limit was changed',
    ),
    'the working directory': (
        'os.chdir(Path.cwd().anchor)',
        'Path.cwd() != Path(Path.cwd().anchor)',
        'the working directory was changed',
    ),
    'the collector off': (
        'gc.disable()',
        'gc.isenabled()',
        'whether the garbage collector runs was changed',
    ),
    'the collector thresholds': (
        'gc.set_threshold(501)',
        'gc.get_threshold()[0] != 501',
        'the garbage collector thresholds was changed',
    ),
    'logging.disable': (
        'logging.disable(logging.INFO)',
        'logging.root.manager.disable == logging.NOTSET',
        'logging.disable was called',
    ),
    "the root logger's level": (
        'logging.root.setLevel(37)',
        'logging.root.level != 37',
        "the logger 'root' was changed",
    ),
    "a logger's handler": (
        "logging.getLogger('planted_handler').addHandler(logging.StreamHandler())",
        "not logging.getLogger('planted_handler').handlers",
        "the logger 'planted_handler' was changed",
    ),
    "a logger's propagation": (
        "logging.getLogger('game').propagate = False",
        "logging.getLogger('game').propagate",
        "the logger 'game' was changed",
    ),
}
# Windows has no signal but the ones the harness puts back and faulthandler's own
if sys.platform != 'win32':
    PLANTED_LEAKS['a signal handler'] = (
        'signal.signal(signal.SIGUSR1, print)',
        'signal.getsignal(signal.SIGUSR1) is not print',
        f'the handler of signal {int(signal.SIGUSR1)} was changed',
    )
INNER_HEADER = """\
import gc
import logging
import os
import random
import signal
import sys
import threading
from pathlib import Path

import numpy as np
import pygame

from tests import leaked_state_guard
from tests.test_leaked_state_guard import END_PLANTED_THREAD

RANDOM_BEFORE = random.getstate()
NUMPY_RANDOM_BEFORE = leaked_state_guard.numpy_random_state()


def numpy_random_is_as_before():
    return leaked_state_guard.same_numpy_state(
        leaked_state_guard.numpy_random_state(), NUMPY_RANDOM_BEFORE
    )
"""
INNER_TESTS = """

def test_leaks():
    {leak}


def test_after_it():
    assert {clean}
"""
# The run around them: the harness (its autouse fixtures ask for pytest-mock's), in written order
INNER_OPTIONS = ('-p', 'tests.harness', '-p', 'no:randomly', '-p', 'no:cacheprovider')
END_PLANTED_THREAD = threading.Event()


@pytest.fixture
def planted_thread_ends() -> Generator[None]:
    """End the planted thread after the test, and wait for it."""
    END_PLANTED_THREAD.clear()
    yield
    END_PLANTED_THREAD.set()
    for thread in threading.enumerate():
        if thread.name == 'planted':
            thread.join()


def run_inner_tests(*, pytester: pytest.Pytester, source: str) -> pytest.RunResult:
    """Run a file of tests in this process, with the harness.

    Returns:
        Its result.

    """
    pytester.makepyfile(test_inner=source)
    return pytester.runpytest_inprocess(*INNER_OPTIONS)


@pytest.mark.parametrize('kind', PLANTED_LEAKS)
def test_a_leak_fails_the_test_that_made_it_and_only_that_one(
    kind, pytester, mocker, planted_thread_ends
):
    """Its error names it and the state; the test after it finds the state as it was."""
    leak, clean, told = PLANTED_LEAKS[kind]
    mocker.patch.object(leaked_state_guard, 'THREAD_GRACE_SECONDS', SHORT_GRACE_SECONDS)

    result = run_inner_tests(
        pytester=pytester, source=INNER_HEADER + INNER_TESTS.format(leak=leak, clean=clean)
    )

    result.assert_outcomes(passed=2, errors=1)
    output = result.stdout.str()
    assert 'test_inner.py::test_leaks left process-wide state changed' in output
    assert told in output
    # Names only: a variable's value, left or put back, may be a secret
    assert PLANTED_VALUE not in output
    assert os.environ['PATH'] not in output


def test_a_run_that_leaks_nothing_passes(pytester):
    """State changed and put back within a test is the test's own business."""
    source = (
        INNER_HEADER
        + """

def test_puts_everything_back(monkeypatch):
    monkeypatch.setenv('GLITCHYGAMES_PLANTED_LEAK', '1')
    monkeypatch.chdir(Path.cwd().anchor)
    pygame.key.set_repeat(500, 50)
    pygame.key.set_repeat(0, 0)
    thread = threading.Thread(target=print, name='planted')
    thread.start()
    logging.getLogger('planted_null').addHandler(logging.NullHandler())
"""
    )

    run_inner_tests(pytester=pytester, source=source).assert_outcomes(passed=1)


def test_a_failing_teardown_keeps_its_error_and_tells_the_leak(pytester):
    """Both are told, and the state is put back."""
    source = (
        INNER_HEADER
        + """
import pytest


@pytest.fixture
def fails_in_teardown():
    yield
    raise RuntimeError('the teardown itself')


def test_leaks(fails_in_teardown):
    sys.setrecursionlimit(1999)


def test_after_it():
    assert sys.getrecursionlimit() != 1999
"""
    )

    result = run_inner_tests(pytester=pytester, source=source)

    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines(['*the teardown itself*', '*the recursion limit was changed*'])


def test_an_item_that_is_not_a_function_is_judged(pytester):
    """A golden replay's item, which no autouse fixture reaches, is judged as every other."""
    pytester.makeconftest("""
import os
import pytest


class LeavesAVariable(pytest.Item):
    def runtest(self):
        os.environ['GLITCHYGAMES_PLANTED_LEAK'] = '1'


class ItemFile(pytest.File):
    def collect(self):
        yield LeavesAVariable.from_parent(self, name='leaves_a_variable')


def pytest_collect_file(file_path, parent):
    if file_path.suffix == '.item':
        return ItemFile.from_parent(parent, path=file_path)
    return None
""")
    (pytester.path / 'custom.item').write_text('', encoding='utf-8')

    result = pytester.runpytest_inprocess(*INNER_OPTIONS)

    result.assert_outcomes(passed=1, errors=1)
    assert PLANTED_VARIABLE not in os.environ


def test_pytest_randomlys_own_seeding_is_not_a_leak(pytester):
    """A shuffled run seeds the global states around every test, so none is judged there."""
    pytester.makepyfile(
        test_inner=INNER_HEADER + INNER_TESTS.format(leak='random.random()', clean='True')
    )
    random_before, numpy_before = random.getstate(), numpy_random_state()

    try:
        # -p pytest_randomly: the harness blocks it in inner runs, which a name given later undoes
        result = pytester.runpytest_inprocess(*INNER_OPTIONS[:2], '-p', 'randomly')
    finally:
        random.setstate(random_before)
        NUMPY_GLOBAL_RANDOM.set_state(numpy_before)

    result.assert_outcomes(passed=2)


def test_mocker_is_undone_before_monkeypatch(pytester):
    """An os.environ snapshot made after a monkeypatch change never puts the change back.

    55 tests once left PYTHONPATH or GIT_EDITOR changed, as the harness's autouse fixtures made
    mocker first, so monkeypatch was undone first.
    """
    source = (
        INNER_HEADER
        + f"""

def test_changes_the_environment_both_ways(monkeypatch, mocker):
    monkeypatch.setenv('{PLANTED_VARIABLE}', '1')
    mocker.patch.dict(os.environ, {{'GLITCHYGAMES_ANOTHER_PLANTED_LEAK': '2'}})


def test_after_it():
    assert '{PLANTED_VARIABLE}' not in os.environ
"""
    )

    run_inner_tests(pytester=pytester, source=source).assert_outcomes(passed=2)


def test_the_watch_changes_nothing():
    """Watching, checking and watching again find and change nothing."""
    before = (
        dict(os.environ),
        random.getstate(),
        NUMPY_GLOBAL_RANDOM.get_state()[1].tolist(),
        [signal.getsignal(number) for number in signal.valid_signals()],
        list(sys.path),
        gc.get_threshold(),
        logging.root.level,
    )

    check = watch_process_state(random_reseeded_for_each_test=False)

    assert check() == []
    assert check() == []
    assert before == (
        dict(os.environ),
        random.getstate(),
        NUMPY_GLOBAL_RANDOM.get_state()[1].tolist(),
        [signal.getsignal(number) for number in signal.valid_signals()],
        list(sys.path),
        gc.get_threshold(),
        logging.root.level,
    )


def test_a_thread_that_ends_within_the_grace_is_not_a_leak():
    """It is waited for, so it cannot reach the next test."""
    check = watch_threads()
    release = threading.Event()
    thread = threading.Thread(target=release.wait)
    thread.start()
    threading.Timer(0.01, release.set).start()

    assert check() == []
    assert not thread.is_alive()


def test_only_pytests_own_variable_is_not_judged(monkeypatch):
    """PYTEST_CURRENT_TEST changes with every phase."""
    check = watch_environment()
    monkeypatch.setenv('PYTEST_CURRENT_TEST', 'another phase')

    assert check() == []


def test_key_repeat_of_a_display_a_test_quit_is_no_leak(mocker):
    """There is none to put back; the next display starts with it off."""
    pygame.key.set_repeat(500, 50)
    check = watch_key_repeat()
    mocker.patch.object(pygame.display, 'get_init', return_value=False)

    assert check() == []

    mocker.stopall()
    pygame.key.set_repeat(0, 0)


def test_a_directory_deleted_before_the_test_is_left(mocker, tmp_path, monkeypatch):
    """With no working directory to go back to, the one the test went to stays."""
    mocker.patch.object(leaked_state_guard.Path, 'cwd', side_effect=FileNotFoundError)
    check = watch_settings()
    mocker.stopall()
    monkeypatch.chdir(tmp_path)

    assert check() == ['the working directory was changed']


def test_a_handler_not_set_from_python_is_told_but_not_put_back(mocker):
    """signal.getsignal answers None for one, which signal.signal refuses."""
    mocker.patch.object(signal, 'getsignal', return_value=None)
    check = watch_signals()
    mocker.patch.object(signal, 'getsignal', return_value=signal.SIG_DFL)
    put_back = mocker.patch.object(signal, 'signal')

    leaks = check()

    assert len(leaks) == len(leaked_state_guard.SIGNALS)
    put_back.assert_not_called()


def test_a_collector_off_before_the_test_is_off_after_it():
    """What the test found is what is put back, whichever it was."""
    gc.disable()
    try:
        check = watch_settings()
        gc.enable()

        assert check() == ['whether the garbage collector runs was changed']
        assert not gc.isenabled()
    finally:
        gc.enable()
