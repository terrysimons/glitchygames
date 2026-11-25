"""Tests for tests/import_failure_state.py: what sys.modules looked like at an import failure."""

from __future__ import annotations

import gc
import importlib
import sys
import types
from collections import UserDict

import pytest

from tests import import_failure_state
from tests.import_failure_state import HOW_TO_READ, collections_report, modules_state_report

PACKAGE = 'import_state_probe'


@pytest.fixture
def package(tmp_path, monkeypatch):
    """A package of modules written by the test, importable, gone from sys.modules at the end.

    Yields:
        A function that writes one of its modules.

    """
    (tmp_path / PACKAGE).mkdir()
    monkeypatch.syspath_prepend(tmp_path)

    def write(*, name: str, source: str) -> None:
        (tmp_path / PACKAGE / f'{name}.py').write_text(source)

    yield write
    for name in [name for name in sys.modules if name.partition('.')[0] == PACKAGE]:
        sys.modules.pop(name)


def state_of(error: BaseException, **changes) -> str:
    """Write the state section for an error.

    Returns:
        Its text.

    """
    return modules_state_report(**{
        'error': error,
        'traceback_object': error.__traceback__,
        'startup_modules': sys.modules,
        'collections_before': gc.get_stats(),
        **changes,
    })


def import_failure() -> BaseException:
    """Import the package, which must fail with KeyError.

    Returns:
        The error.

    """
    with pytest.raises(KeyError) as excinfo:
        importlib.import_module(PACKAGE)
    return excinfo.value


def test_a_targeted_delete_leaves_the_siblings_in_place(package, monkeypatch):
    """Only the failed name is gone; the package went as the exception unwound."""
    monkeypatch.setitem(sys.modules, f'{PACKAGE}_lookalike', types.ModuleType('lookalike'))
    package(name='__init__', source='from . import first\nfrom . import second\n')
    package(name='first', source='')
    package(name='second', source='import sys\ndel sys.modules[__name__]\n')

    state = state_of(import_failure())

    assert f'{PACKAGE}.second in sys.modules: NOT found by hash, NOT found by iteration' in state
    assert f'{PACKAGE}.second is being loaded by 1 frames and its own code is run by 0' in state
    position = list(sys.modules).index(f'{PACKAGE}.first')
    module = sys.modules[f'{PACKAGE}.first']
    assert (
        f'  [{position}] {PACKAGE}.first: id {id(module):#x}, _initializing False, '
        f"the same object as {PACKAGE}'s attribute"
    ) in state
    assert f'] {PACKAGE}:' not in state
    assert f'{PACKAGE}.first: NOT in' not in state
    assert f'] {PACKAGE}_lookalike:' not in state
    assert '] sys:' not in state
    for line in HOW_TO_READ:
        assert line in state


def test_a_whole_restore_shows_the_sibling_only_the_package_holds(package):
    """A sibling loaded before is gone too, found through the failing package's own attributes."""
    package(name='__init__', source='from . import first\nfrom . import second\n')
    package(name='first', source='')
    package(
        name='second',
        source=(
            'import sys\n'
            f'for name in [n for n in sys.modules if n.startswith("{PACKAGE}.")]:\n'
            '    del sys.modules[name]\n'
        ),
    )

    state = state_of(import_failure())

    assert f"{PACKAGE}.first: NOT in sys.modules, held by {PACKAGE}'s attribute" in state


def test_a_load_inside_another_of_the_same_name_shows(package):
    """A load of the same name inside the first shows as a load under that name's own code."""
    package(name='__init__', source='from . import twice\n')
    package(
        name='twice',
        source=(
            'import sys\n'
            'import importlib.util\n'
            'if not hasattr(sys.modules[__package__], "again"):\n'
            '    sys.modules[__package__].again = True\n'
            '    del sys.modules[__name__]\n'
            '    import importlib._bootstrap as bootstrap\n'
            '    bootstrap._load_unlocked(importlib.util.find_spec(__name__))\n'
            'else:\n'
            '    del sys.modules[__name__]\n'
        ),
    )

    state = state_of(import_failure())

    assert f'{PACKAGE}.twice is being loaded by 1 frames and its own code is run by 1' in state


def test_an_entry_put_back_is_found_and_compared(package):
    """The failed name present again, as an object its package does not hold, says so."""
    package(name='__init__', source='from . import first\n')
    package(name='first', source='')
    importlib.import_module(PACKAGE)
    sys.modules[f'{PACKAGE}.first'] = types.ModuleType('another')

    state = state_of(KeyError(f'{PACKAGE}.first'))

    assert f'{PACKAGE}.first in sys.modules: found by hash, found by iteration' in state
    assert f"_initializing unknown, NOT the object {PACKAGE}'s attribute" in state
    assert f'{PACKAGE}: id' in state
    assert 'top level' in state


def test_a_dictionary_whose_lookups_disagree_is_shown(mocker):
    """Found by iteration and not by hash: the two are asked separately."""

    class Disagreeing(UserDict):
        def __contains__(self, key):
            return False

    modules = Disagreeing(sys.modules)
    modules[PACKAGE] = types.ModuleType(PACKAGE)
    mocker.patch.object(import_failure_state.sys, 'modules', modules)
    state = state_of(KeyError(PACKAGE))
    mocker.stopall()

    assert f'{PACKAGE} in sys.modules: NOT found by hash, found by iteration' in state


@pytest.mark.parametrize(
    ('names', 'line'),
    [
        ([f'{PACKAGE}.part'], f'{PACKAGE} not found'),
        ([PACKAGE, f'{PACKAGE}.part'], f'{PACKAGE} has no attribute for it'),
    ],
)
def test_a_module_whose_package_cannot_be_compared_says_why(monkeypatch, names, line):
    """The package absent, or without the attribute; None in sys.modules is no fault."""
    for name in names:
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, f'{PACKAGE}.blocked', None)

    state = state_of(KeyError(f'{PACKAGE}.part'))

    assert line in state
    assert f'{PACKAGE}.blocked: id {id(None):#x}, _initializing unknown' in state


def test_a_lazy_module_is_not_loaded_by_looking(monkeypatch):
    """Its own __getattribute__ is never called."""

    class Lazy(types.ModuleType):
        def __getattribute__(self, name):
            pytest.fail(f'{name} was read')

    monkeypatch.setitem(sys.modules, PACKAGE, Lazy(PACKAGE))

    assert f'{PACKAGE}: id' in state_of(KeyError(PACKAGE))


@pytest.mark.parametrize('error', [ImportError('x'), KeyError(3), ValueError('x')])
def test_an_error_naming_no_module_says_so(error):
    """The rest of the section is still written."""
    state = state_of(error)

    assert 'the failure names no module' in state
    assert 'sys.modules is the dictionary seen at startup' in state


def test_an_import_errors_module_is_the_failed_one():
    """ImportError carries its name apart from its arguments."""
    assert 'sys in sys.modules: found by hash' in state_of(ImportError('x', name='sys'))


def test_a_rebound_sys_modules_is_said():
    """Any other dictionary than the one at startup."""
    assert 'sys.modules is NOT the dictionary seen at startup' in state_of(
        KeyError('sys'), startup_modules={}
    )


@pytest.mark.parametrize(('enabled', 'word'), [(True, 'enabled'), (False, 'disabled')])
def test_the_collections_since_the_test_began_are_counted(mocker, enabled, word):
    """Each generation's difference, and whether collection is on."""
    mocker.patch.object(gc, 'isenabled', return_value=enabled)
    mocker.patch.object(
        gc, 'get_stats', return_value=[{'collections': n, 'collected': 10 * n} for n in (5, 7, 9)]
    )
    before = [{'collections': 1, 'collected': 10}] * 3

    report = collections_report(before)

    assert f'garbage collection: {word}' in report
    assert 'generation 0: 4 collections, 40 objects' in report
    assert 'generation 2: 8 collections, 80 objects' in report
