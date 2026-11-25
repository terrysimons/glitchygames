"""A test that leaves process-wide state changed fails by name (tests/leaked_state_guard.py).

Each kind of leak is planted in a real pytest run with the harness loaded, in this process, so
what is judged is this process's own state: a test that leaks, then one that must find the state
as it was.
"""

from __future__ import annotations

import _thread
import ast
import gc
import logging
import os
import random
import re
import signal
import sys
import textwrap
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import clock
from tests import leaked_state_guard
from tests.harness import PROCESS_STATE_CHECK_KEY, end_of_item_leaks
from tests.leaked_state_guard import (
    NUMPY_GLOBAL_RANDOM,
    drop_patches_to_put_back,
    environment_holds,
    numpy_random_state,
    watch_environment,
    watch_global_random,
    watch_key_repeat,
    watch_list,
    watch_process_state,
    watch_settings,
    watch_signals,
    watch_threads,
)
from tests.test_engine_written_state import PLANTED as PLANTED_ENGINE_STATE

if TYPE_CHECKING:
    from collections.abc import Generator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBPROCESS_TIMEOUT_SECONDS = 120.0
# An assertion of a text that is no Python on its own: one that names environ, not subscripted
DUMPING_ASSERTION_LINE = re.compile(r'\s*assert\b.*\benviron\b(?!\[)')
# A variable no one sets, and the value planted in it: the failure must never show a value
PLANTED_VARIABLE = 'GLITCHYGAMES_PLANTED_LEAK'
PLANTED_VALUE = 'planted-secret-value'
# A variable set before the test that leaks, and its value
EXISTING_VARIABLE = 'GLITCHYGAMES_PLANTED_BEFORE'
EXISTING_VALUE = 'planted-secret-before'
# No engine state to reset, for a watch of a test's own
NOTHING_TO_RESET = list
# The time given to a planted thread that never ends
SHORT_GRACE_SECONDS = 0.05

# Each planted leak: its name, the leaking test's body, what the test after it asserts, and what the
# failure must tell. The names used are imported by INNER_HEADER
PLANTED_LEAKS = {
    'a variable set': (
        f"os.environ['{PLANTED_VARIABLE}'] = '{PLANTED_VALUE}'",
        f"environment_holds(name='{PLANTED_VARIABLE}', value=None)",
        f'the environment variable {PLANTED_VARIABLE} was set',
    ),
    'a variable removed': (
        f"del os.environ['{EXISTING_VARIABLE}']",
        f"environment_holds(name='{EXISTING_VARIABLE}', value='{EXISTING_VALUE}')",
        f'the environment variable {EXISTING_VARIABLE} was removed',
    ),
    'a variable changed': (
        f"os.environ['{EXISTING_VARIABLE}'] = '{PLANTED_VALUE}'",
        f"environment_holds(name='{EXISTING_VARIABLE}', value='{EXISTING_VALUE}')",
        f'the environment variable {EXISTING_VARIABLE} was changed',
    ),
    'os.environ replaced': (
        'os.environ = dict(os.environ)',
        'environment_is_the_process_s()',
        'os.environ (the object itself) changed',
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
    "numpy.random's generator": (
        'np.random.set_bit_generator(np.random.PCG64(1))',
        'numpy_random_is_as_before()',
        "numpy.random's bit generator was replaced",
    ),
    'sys.excepthook': (
        'sys.excepthook = print',
        'sys.excepthook is not print',
        'sys.excepthook changed',
    ),
    'sys.unraisablehook': (
        'sys.unraisablehook = print',
        'sys.unraisablehook is not print',
        'sys.unraisablehook changed',
    ),
    'sys.displayhook': (
        'sys.displayhook = print',
        'sys.displayhook is not print',
        'sys.displayhook changed',
    ),
    'threading.excepthook': (
        'threading.excepthook = print',
        'threading.excepthook is not print',
        'threading.excepthook changed',
    ),
    'sys.path': (
        "sys.path.append('/planted')",
        "'/planted' not in sys.path",
        'sys.path changed',
    ),
    'sys.argv': (
        "sys.argv.append('--planted')",
        "'--planted' not in sys.argv",
        'sys.argv changed',
    ),
    'sys.path replaced': (
        'sys.path = [*sys.path]',
        'sys.path is SYS_PATH',
        'sys.path changed',
    ),
    'the recursion limit': (
        'sys.setrecursionlimit(1999)',
        'sys.getrecursionlimit() != 1999',
        'the recursion limit changed',
    ),
    'the working directory': (
        'os.chdir(Path.cwd().anchor)',
        'Path.cwd() != Path(Path.cwd().anchor)',
        'the working directory changed',
    ),
    'the collector off': (
        'gc.disable()',
        'gc.isenabled()',
        'whether the garbage collector runs changed',
    ),
    'the collector thresholds': (
        'gc.set_threshold(501)',
        'gc.get_threshold()[0] != 501',
        'the garbage collector thresholds changed',
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
    "a logger's disabling": (
        "logging.getLogger('game').disabled = True",
        "not logging.getLogger('game').disabled",
        "the logger 'game' was changed",
    ),
    "a logger's filter": (
        "logging.getLogger('game').addFilter(print)",
        "not logging.getLogger('game').filters",
        "the logger 'game' was changed",
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
from tests.leaked_state_guard import environment_holds
from tests.test_leaked_state_guard import END_PLANTED_THREAD, environment_is_the_process_s

SYS_PATH = sys.path

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


def environment_is_the_process_s() -> bool:
    """Return whether os.environ is the process's own, for a planted test to assert.

    Returns:
        Whether it is.

    """
    return os.environ is leaked_state_guard.ENVIRONMENT


@pytest.fixture
def planted_thread_ends() -> Generator[None]:
    """End the planted thread after the test, and wait for it."""
    END_PLANTED_THREAD.clear()
    yield
    END_PLANTED_THREAD.set()
    for thread in threading.enumerate():
        if thread.name == 'planted':
            thread.join()


def secrets_shown(*, texts: list[str]) -> list[str]:
    """Return the planted variables whose values some output shows: names, never the output.

    Args:
        texts: The output.

    Returns:
        The variables' names.

    """
    planted = {PLANTED_VARIABLE: PLANTED_VALUE, EXISTING_VARIABLE: EXISTING_VALUE}
    return [name for name, value in planted.items() if any(value in text for text in texts)]


def run_inner_tests(*, pytester: pytest.Pytester, source: str) -> pytest.RunResult:
    """Run a file of tests in this process, with the harness.

    Returns:
        Its result.

    """
    pytester.makepyfile(test_inner=source)
    return pytester.runpytest_inprocess(*INNER_OPTIONS)


@pytest.mark.parametrize('kind', PLANTED_LEAKS)
def test_a_leak_fails_the_test_that_made_it_and_only_that_one(
    kind, pytester, mocker, monkeypatch, planted_thread_ends
):
    """Its error names it and the state; the test after it finds the state as it was."""
    leak, clean, told = PLANTED_LEAKS[kind]
    mocker.patch.object(leaked_state_guard, 'THREAD_GRACE_SECONDS', SHORT_GRACE_SECONDS)
    monkeypatch.setenv(EXISTING_VARIABLE, EXISTING_VALUE)

    result = run_inner_tests(
        pytester=pytester, source=INNER_HEADER + INNER_TESTS.format(leak=leak, clean=clean)
    )

    result.assert_outcomes(passed=2, errors=1)
    output = result.stdout.str()
    assert 'test_inner.py::test_leaks left process-wide state changed' in output
    assert told in output
    # Names only: a variable's value, left or put back, may be a secret
    assert secrets_shown(texts=[output]) == []


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
    result.stdout.fnmatch_lines(['*the teardown itself*', '*the recursion limit changed*'])


def test_an_item_that_is_not_a_function_is_judged(pytester):
    """An item a collector makes, which no autouse fixture reaches, is judged as every other."""
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
    assert environment_holds(name=PLANTED_VARIABLE, value=None)


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
    assert environment_holds(name='{PLANTED_VARIABLE}', value=None)
"""
    )

    run_inner_tests(pytester=pytester, source=source).assert_outcomes(passed=2)


def state_of_every_kind() -> dict[str, object]:
    """Read the state apart from the guard, by kind.

    Returns:
        The state.

    """
    return {
        'environment': dict(os.environ),
        'random': random.getstate(),
        'numpy.random': NUMPY_GLOBAL_RANDOM.get_state()[1].tolist(),
        'signals': [signal.getsignal(number) for number in signal.valid_signals()],
        'sys.path': list(sys.path),
        'thresholds': gc.get_threshold(),
        'root level': logging.root.level,
    }


def test_the_watch_changes_nothing():
    """Watching and checking, twice, find and change nothing."""
    before = state_of_every_kind()

    check = watch_process_state(random_reseeded_for_each_test=False, reset=NOTHING_TO_RESET)

    assert check() == []
    assert check() == []
    after = state_of_every_kind()
    # The kinds' names alone: the values hold the environment
    changed_kinds = [kind for kind in before if before[kind] != after[kind]]
    assert changed_kinds == []


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

    assert check() == ['the working directory changed']


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

        assert check() == ['whether the garbage collector runs changed']
        assert not gc.isenabled()
    finally:
        gc.enable()


def test_a_variable_a_tests_thread_sets_late_is_the_tests(pytester):
    """The threads are waited for before anything else is read: the next test finds it unset."""
    source = INNER_HEADER + INNER_TESTS.format(
        leak=(
            'threading.Timer(0.1, os.environ.__setitem__, '
            f"('{PLANTED_VARIABLE}', '{PLANTED_VALUE}')).start()"
        ),
        clean=f"environment_holds(name='{PLANTED_VARIABLE}', value=None)",
    )

    result = run_inner_tests(pytester=pytester, source=source)

    result.assert_outcomes(passed=2, errors=1)
    told = f'the environment variable {PLANTED_VARIABLE} was set' in result.stdout.str()
    assert told


def test_the_reset_comes_after_the_threads():
    """A thread's late change of what running an engine changes is reset too."""
    events: list[str] = []
    thread = threading.Timer(0.05, events.append, ['the thread ended'])
    check = watch_process_state(
        random_reseeded_for_each_test=False, reset=lambda: events.append('reset')
    )
    thread.start()

    assert check() == []
    assert events == ['the thread ended', 'reset']


# The only variables of the process an inner run of planted secrets gets: what finds its programs
# and folders. Its output must hold no real secret, however it fails
KEPT_VARIABLES = ('PATH', 'HOME', 'SYSTEMROOT', 'TEMP', 'TMP', 'TMPDIR', 'USERPROFILE')
# Every assertion a test of these files makes about the environment, failing, after a leak
FAILING_TESTS = f"""

def test_leaks_all_three():
    os.environ['{PLANTED_VARIABLE}'] = '{PLANTED_VALUE}'
    os.environ['{EXISTING_VARIABLE}'] = '{PLANTED_VALUE}'


def test_fails_as_a_test_of_the_environment_would():
    assert environment_holds(name='{EXISTING_VARIABLE}', value=None)


def test_fails_as_a_test_of_the_object_would():
    os.environ = dict(os.environ)
    assert environment_is_the_process_s()


def test_fails_as_a_test_of_the_watch_would():
    from tests.test_leaked_state_guard import state_of_every_kind
    before = state_of_every_kind()
    os.environ['{PLANTED_VARIABLE}'] = '{PLANTED_VALUE}'
    after = state_of_every_kind()
    changed_kinds = [kind for kind in before if before[kind] != after[kind]]
    assert changed_kinds == []
"""


def test_no_value_reaches_the_output_or_the_junit_report(pytester, mocker):
    """With CI set, pytest truncates nothing: whatever fails, no variable's value is told."""
    kept = {name: os.environ[name] for name in KEPT_VARIABLES if name in os.environ}
    kept |= {
        'CI': '1',
        'PYTHONPATH': str(PROJECT_ROOT),
        'SDL_VIDEODRIVER': 'dummy',
        'SDL_AUDIODRIVER': 'dummy',
        EXISTING_VARIABLE: EXISTING_VALUE,
    }
    mocker.patch.dict(os.environ, kept, clear=True)
    # The values are looked for in what pytest prints of them, never in its lines of source
    source = INNER_HEADER + FAILING_TESTS.replace(
        PLANTED_VALUE, "'.join(['planted-', 'secret-', 'value']) + '"
    )
    pytester.makepyfile(test_inner=source)
    report = pytester.path / 'junit.xml'

    result = pytester.runpytest_subprocess(
        *INNER_OPTIONS, '-vv', f'--junitxml={report}', timeout=SUBPROCESS_TIMEOUT_SECONDS
    )

    outcomes = result.parseoutcomes()
    assert (outcomes['failed'], outcomes['passed'], outcomes['errors']) == (3, 1, 3)
    texts = [result.stdout.str(), result.stderr.str(), report.read_text(encoding='utf-8')]
    assert secrets_shown(texts=texts) == []


def assertions_dumping_the_environment(*, source: str) -> list[int]:
    """Return the lines of the assertions that print the whole environment when they fail.

    Those naming environ, but for its subscript: pytest prints what ``os.environ['A']`` is, one
    value, and for any other use all of them.

    Args:
        source: Python; an inner test's text, its lines looked at one by one, when it is not.

    Returns:
        The lines.

    """
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return [
            number
            for number, line in enumerate(source.splitlines(), start=1)
            if DUMPING_ASSERTION_LINE.match(line)
        ]
    lines: list[int] = []
    for statement in ast.walk(tree):
        if not isinstance(statement, ast.Assert):
            continue
        parts = list(ast.walk(statement.test))
        subscripted = {id(part.value) for part in parts if isinstance(part, ast.Subscript)}
        if any(
            isinstance(part, ast.Attribute | ast.Name)
            and (part.attr if isinstance(part, ast.Attribute) else part.id) == 'environ'
            and id(part) not in subscripted
            for part in parts
        ):
            lines.append(statement.lineno)
    return lines


def texts_in(*, source: str) -> list[tuple[int, str]]:
    """Return a file's strings that name environ, an f-string's values as ``x``.

    Args:
        source: Python.

    Returns:
        Each string's line and text.

    """
    tree = ast.parse(source)
    inside = {
        id(part)
        for string in ast.walk(tree)
        if isinstance(string, ast.JoinedStr)
        for part in string.values
    }
    texts: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = ''.join(
                str(part.value) if isinstance(part, ast.Constant) else 'x' for part in node.values
            )
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = '' if id(node) in inside else node.value
        else:
            continue
        if 'environ' in text:
            texts.append((node.lineno, text))
    return texts


def test_an_assertion_dumping_the_environment_is_found():
    """The scan below finds what it looks for: in code, in an inner test, in an f-string."""
    name = 'environ'
    source = (
        f"x = 1\nassert 'A' not in os.{name}\nassert {name}.get('A')\nassert x == 1\n"
        f"assert os.{name}['A'] == 'a'\nassert f(os.{name})\n"
    )
    inner = f'    import os\n    assert {{NAME!r}} in os.{name}\n'

    assert assertions_dumping_the_environment(source=source) == [2, 3, 6]
    assert assertions_dumping_the_environment(source=f'not python\nassert 1 in {name}\n') == [2]
    texts = [text for _line, text in texts_in(source=f"NAME = 'A'\nTEXT = f{inner!r}\n")]
    assert [assertions_dumping_the_environment(source=text) for text in texts] == [[2]]


def test_no_assertion_of_any_test_dumps_the_environment():
    """A failing one prints every variable's value into the log and the junit report.

    Every test file's own assertions, and those of the inner tests it holds as text. A tripwire,
    not a proof: an alias of os.environ, or an inner test put together from pieces, is not seen.
    """
    paths = [
        path
        for directory in ('tests', 'src/games', 'src/demos', 'src/apps')
        for path in sorted((PROJECT_ROOT / directory).rglob('*.py'))
        if 'tests' in path.relative_to(PROJECT_ROOT).parts
    ]
    found: list[str] = []
    for path in paths:
        source = path.read_text(encoding='utf-8')
        if 'environ' not in source:
            continue
        lines = assertions_dumping_the_environment(source=source)
        lines += [
            line
            for line, text in texts_in(source=source)
            if assertions_dumping_the_environment(source=text)
        ]
        found += [f'{path.relative_to(PROJECT_ROOT).as_posix()}:{line}' for line in lines]

    assert len(paths) > 100
    assert found == []


def test_no_planted_assertion_dumps_the_environment():
    """Nor those these files put together from pieces."""
    planted = [clean for _leak, clean, _told in PLANTED_LEAKS.values()]
    planted += [clean for _leaves, clean in PLANTED_ENGINE_STATE.values()]
    sources = [f'assert {clean}' for clean in planted] + [FAILING_TESTS]

    assert [text for text in sources if assertions_dumping_the_environment(source=text)] == []


# What the tests of monkeypatch and mocker patch, and the functions there before
PATCHED_HEADER = (
    INNER_HEADER
    + """
import pytest
from types import SimpleNamespace


class Target:
    def method(self):
        return 1


TARGET = SimpleNamespace(function=Target.method)
TABLE = {'key': len}
METHOD = Target.method
"""
)
PATCHED_AFTER = """

def test_after_it():
    assert Target.method is METHOD
    assert TARGET.function is METHOD
    assert TABLE == {'key': len}
"""


@pytest.mark.parametrize(
    'body',
    [
        "mocker.patch.object(Target, 'method'); monkeypatch.setattr(Target, 'method', print)",
        "mocker.patch.object(Target, 'method', 5); monkeypatch.setattr(Target, 'method', print)",
        "mocker.spy(Target, 'method'); monkeypatch.setattr(Target, 'method', print)",
        "mocker.spy(TARGET, 'function'); monkeypatch.setattr(TARGET, 'function', print)",
        (
            "mocker.patch.object(Target, 'method', autospec=True); "
            "monkeypatch.setattr(Target, 'method', print)"
        ),
        "mocker.patch.dict(TABLE, {'key': mocker.Mock()}); monkeypatch.setitem(TABLE, 'key', 1)",
    ],
    ids=['mock', 'value', 'spy', 'module spy', 'autospec', 'dict'],
)
def test_a_patch_monkeypatch_would_put_back_fails_the_test(body, pytester):
    """Mocker is undone first, so monkeypatch must not undo to the patch it found."""
    source = f'{PATCHED_HEADER}\n\ndef test_both(mocker, monkeypatch):\n    {body}\n'

    result = run_inner_tests(pytester=pytester, source=source + PATCHED_AFTER)

    result.assert_outcomes(passed=2, errors=1)
    result.stdout.fnmatch_lines(['*would have put back what mocker patched*'])


def test_a_mock_mocker_did_not_put_there_is_put_back(pytester):
    """A mock of the test's own, or a wider fixture's patch, is monkeypatch's to put back."""
    source = (
        PATCHED_HEADER
        + """

@pytest.fixture(scope='module')
def patched_for_the_module(module_mocker):
    return module_mocker.patch.object(TARGET, 'function')


def test_own_mocks(mocker, monkeypatch):
    game = SimpleNamespace(on_event=mocker.Mock())
    monkeypatch.setattr(game, 'on_event', print)
    table = {'key': mocker.MagicMock()}
    monkeypatch.setitem(table, 'key', 1)
    target = Target()
    target.method = mocker.Mock()
    monkeypatch.setattr(target, 'method', print)
    mock = mocker.Mock()
    monkeypatch.setattr(mock, 'attribute', 1)
    elsewhere = SimpleNamespace(method=mocker.patch.object(Target, 'method'))
    monkeypatch.setattr(elsewhere, 'method', print)
    monkeypatch.setattr(TARGET, 'function', mock)
    monkeypatch.setattr(TARGET, 'function', print)


def test_monkeypatch_first(mocker, monkeypatch):
    monkeypatch.setattr(Target, 'method', print)
    mocker.patch.object(Target, 'method')
    monkeypatch.setattr(Target, 'method', len)


def test_nothing_is_left():
    assert Target.method is METHOD
    assert TABLE == {'key': len}


def test_over_a_module_patch(patched_for_the_module, monkeypatch):
    monkeypatch.setattr(TARGET, 'function', print)


def test_the_module_patch_is_still_there(patched_for_the_module):
    assert TARGET.function is patched_for_the_module
"""
    )

    run_inner_tests(pytester=pytester, source=source).assert_outcomes(passed=5)


def test_a_pytest_mock_without_its_cache_checks_nothing(mocker, monkeypatch):
    """The cache is private: a version that renames it must not break a run."""
    assert drop_patches_to_put_back(monkeypatch=monkeypatch, mocker=mocker.Mock(spec=[])) == []


def test_threads_share_one_deadline(mocker):
    """A thread that ends at once leaves its share of the grace to the others."""
    mocker.patch.object(leaked_state_guard, 'THREAD_GRACE_SECONDS', SUBPROCESS_TIMEOUT_SECONDS)
    check = watch_threads()
    threads = [
        mocker.Mock(
            spec=threading.Thread,
            join=mocker.Mock(),
            is_alive=lambda: False,
        )
        for _ in range(2)
    ]
    mocker.patch.object(threading, 'enumerate', return_value=threads)
    mocker.patch.object(clock, 'raw_counter_seconds', side_effect=[100.0, 100.0, 130.0])

    assert check() == []
    joined = [thread.join.call_args.kwargs['timeout'] for thread in threads]
    assert joined == [SUBPROCESS_TIMEOUT_SECONDS, SUBPROCESS_TIMEOUT_SECONDS - 30.0]


def test_a_thread_c_started_is_not_judged():
    """Python gives it a stand-in, which has no end to wait for."""
    release, named = threading.Event(), threading.Event()

    def run_in_c_thread() -> None:
        threading.current_thread()
        named.set()
        release.wait()

    check = watch_threads()
    _thread.start_new_thread(run_in_c_thread, ())
    assert named.wait(timeout=SUBPROCESS_TIMEOUT_SECONDS)
    stand_ins = [
        thread for thread in threading.enumerate() if isinstance(thread, threading._DummyThread)
    ]

    leaks = check()

    release.set()
    assert stand_ins
    assert leaks == []


@pytest.fixture
def numpy_random_put_back() -> Generator[None]:
    """Put numpy's global random state back, whatever the test does to it."""
    before = numpy_random_state()
    yield
    NUMPY_GLOBAL_RANDOM.set_state(before)


def test_a_draw_that_only_empties_numpys_gauss_is_seen(numpy_random_put_back):
    """The second normal of a pair moves neither the key nor the position."""
    NUMPY_GLOBAL_RANDOM.standard_normal()
    check = watch_global_random(reseeded_for_each_test=False)
    NUMPY_GLOBAL_RANDOM.standard_normal()

    assert len(check()) == 1
    assert numpy_random_state()['has_gauss'] == 1


def test_another_seed_at_the_same_position_is_seen(numpy_random_put_back):
    """Only the key tells two fresh seeds apart."""
    NUMPY_GLOBAL_RANDOM.seed(1)
    check = watch_global_random(reseeded_for_each_test=False)
    NUMPY_GLOBAL_RANDOM.seed(2)

    assert len(check()) == 1


def test_sys_path_is_put_back_in_the_list_it_is():
    """Code that took the list finds the put-back entries in it."""
    path = sys.path
    check = watch_list(name='path')
    sys.path = ['/planted']
    path.append('/planted')

    assert check() == ['sys.path changed']
    assert sys.path is path
    assert '/planted' not in path


class ItemsSeen:
    """A plugin that keeps the run's items."""

    def __init__(self) -> None:
        """Start with none."""
        self.items: list[pytest.Item] = []

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        """Keep them."""
        self.items = session.items


def test_an_item_keeps_no_copy_of_the_state(pytester):
    """Pytest keeps every item for the whole run."""
    pytester.makepyfile(test_inner='def test_passes():\n    pass\n')
    seen = ItemsSeen()

    pytester.inline_run(*INNER_OPTIONS, plugins=[seen])

    assert len(seen.items) == 1
    assert PROCESS_STATE_CHECK_KEY not in seen.items[0].stash


def test_an_item_whose_watch_never_began_has_nothing_to_check(mocker):
    """Its setup's error is what is told, not a KeyError."""
    item = mocker.Mock(stash=pytest.Stash())

    assert end_of_item_leaks(item=item) == []
