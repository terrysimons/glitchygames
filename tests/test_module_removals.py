"""Tests for tests/module_removals.py: the record of known removals from sys.modules."""

from __future__ import annotations

import gc
import importlib.util
import itertools
import sys
import threading
import types
from pathlib import Path

import pytest
from _pytest.pytester import SysModulesSnapshot

from tests import module_removals
from tests.module_removals import (
    NAMES_KEPT,
    NOT_RECORDED,
    RECORDER_ATTRIBUTE,
    REMOVALS_KEPT,
    STACK_LINES_KEPT,
    LoadInProgress,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# A stand-in module's name: nothing imports it
STAND_IN = 'module_removals_stand_in'


@pytest.fixture
def recorder(monkeypatch):
    """Install the process's recorder for this test, empty; what the run had recorded comes back.

    Yields:
        The recorder, its wrappers in place.

    """
    installed = module_removals.install()
    monkeypatch.setattr(installed, '_slots', [None] * REMOVALS_KEPT)
    monkeypatch.setattr(installed, '_orders', itertools.count(1))
    yield installed
    module_removals.release(installed)


@pytest.fixture
def stand_in(monkeypatch):
    """A stand-in module in sys.modules, gone again at the end.

    Returns:
        Its name.

    """
    monkeypatch.setitem(sys.modules, STAND_IN, types.ModuleType(STAND_IN))
    return STAND_IN


def newest_order(recorder) -> int:
    """The newest removal's order number (0 with none recorded)."""
    return max((removal.order for removal in recorder.removals()), default=0)


def test_a_patch_dict_end_records_what_it_removed_and_where(recorder, mocker, request):
    """The entry names the call, the names, the thread, the test and the calling line."""
    mocker.patch.dict(sys.modules)
    sys.modules[STAND_IN] = types.ModuleType(STAND_IN)
    mocker.stopall()

    removal = recorder.removals()[0]
    assert removal.made_by.startswith('patch.dict(sys.modules) ending')
    assert STAND_IN in removal.names_removed
    assert removal.removed_count == len(removal.names_removed)
    assert removal.whole_dictionary
    assert removal.on_main_thread
    assert removal.thread_name == threading.main_thread().name
    assert removal.test_node_id == request.node.nodeid
    assert any(line.startswith(f'{__file__}:') for line in removal.stack)
    assert len(removal.stack) <= STACK_LINES_KEPT
    assert STAND_IN not in sys.modules


def test_a_patch_dict_ending_as_a_block_or_a_decorator_is_recorded(recorder, mocker):
    """Every form of patch.dict ends the same way, and only some call its stop."""
    patch_dict = mocker.mock_module.patch.dict

    def add_the_stand_in() -> None:
        sys.modules[STAND_IN] = types.ModuleType(STAND_IN)

    with patch_dict(sys.modules):
        add_the_stand_in()
    as_a_block = recorder.removals()[0]
    patch_dict('sys.modules')(add_the_stand_in)()
    as_a_decorator = recorder.removals()[0]

    assert as_a_decorator.order == as_a_block.order + 1
    for removal in (as_a_block, as_a_decorator):
        assert removal.made_by.startswith('patch.dict(sys.modules) ending')
        assert STAND_IN in removal.names_removed


def test_a_patch_dict_start_is_recorded_only_when_it_clears(recorder, mocker):
    """clear=True empties the dictionary at once, by object and by name; a plain start does not."""
    before = newest_order(recorder)
    mocker.patch.dict(sys.modules)
    assert newest_order(recorder) == before
    mocker.stopall()

    for target in (sys.modules, 'sys.modules'):
        # The dictionary is put back at once: nothing may be imported while it is empty
        mocker.patch.dict(target, dict(sys.modules), clear=True)
        started = recorder.removals()[0]
        mocker.stopall()
        assert started.made_by == 'patch.dict(sys.modules, clear=True) starting'
        assert started.names_removed == ()


def test_a_pytester_restore_is_recorded(recorder, mocker):
    """The snapshot pytester's in-process runs restore is a whole-dictionary removal too."""
    snapshot = SysModulesSnapshot()
    sys.modules[STAND_IN] = types.ModuleType(STAND_IN)
    snapshot.restore()

    removal = recorder.removals()[0]
    assert removal.made_by.startswith('pytester SysModulesSnapshot.restore')
    assert STAND_IN in removal.names_removed


@pytest.mark.parametrize('by_keyword', [False, True])
def test_a_monkeypatch_delitem_is_recorded(recorder, stand_in, by_keyword):
    """Its removal is recorded however the dictionary is passed."""
    with pytest.MonkeyPatch.context() as context:
        if by_keyword:
            context.delitem(dic=sys.modules, name=stand_in)
        else:
            context.delitem(sys.modules, stand_in)
        removal = recorder.removals()[0]

    assert removal.made_by == 'monkeypatch.delitem(sys.modules, ...)'
    assert removal.names_removed == (stand_in,)
    assert not removal.whole_dictionary


def test_a_monkeypatch_undo_is_recorded(recorder):
    """Undoing a setitem removes the name the setitem added, other changes beside it or not."""
    with pytest.MonkeyPatch.context() as context:
        context.setitem({}, 'other', 1)
        context.setitem(sys.modules, STAND_IN, types.ModuleType(STAND_IN))

    removal = recorder.removals()[0]
    assert removal.made_by == 'monkeypatch.undo of changes to sys.modules'
    assert removal.names_removed == (STAND_IN,)


def test_other_dictionaries_and_ordinary_imports_record_nothing(
    recorder, mocker, tmp_path, monkeypatch
):
    """Only sys.modules counts, and importing a module is no removal."""
    (tmp_path / 'ordinary_import_probe.py').write_text('VALUE = 1\n')
    monkeypatch.syspath_prepend(tmp_path)
    before = newest_order(recorder)
    other = {'key': 1}

    mocker.patch.dict(other, {'more': 2}, clear=True)
    mocker.stopall()
    with pytest.MonkeyPatch.context() as context:
        context.delitem(other, 'key')
    try:
        assert importlib.import_module('ordinary_import_probe').VALUE == 1
    finally:
        sys.modules.pop('ordinary_import_probe', None)

    assert other == {'key': 1}
    assert newest_order(recorder) == before


def test_a_wrapped_call_raises_what_it_raised_before(recorder):
    """A delitem of a missing name still raises KeyError, and the entry says nothing left."""
    with pytest.MonkeyPatch.context() as context, pytest.raises(KeyError, match=STAND_IN):
        context.delitem(sys.modules, STAND_IN)

    removal = recorder.removals()[0]
    assert removal.names_removed == ()
    assert 'removed nothing for good' in module_removals.removal_report(removal)


def test_an_entry_is_kept_while_its_call_still_runs(recorder, stand_in, mocker):
    """A failure during the call finds the entry, said to be running: seen from inside a call."""
    seen = []

    def look(*args):
        seen.append(module_removals.removal_report(recorder.removals()[0]))

    method = recorder.wrapping(
        original=look,
        made_by='a probe',
        decide=lambda *_: module_removals.Recorded.WHOLE_DICTIONARY,
    )
    method()

    assert 'a probe' in seen[0]
    assert 'still running when this was written' in seen[0]


@pytest.mark.parametrize('failing', ['loads_in_progress', 'call_stack', 'thread_name'])
def test_a_fault_before_the_call_is_counted_and_the_call_still_runs(
    recorder, stand_in, mocker, failing
):
    """The recording failing changes nothing the caller sees."""
    mocker.patch.object(module_removals, failing, side_effect=RuntimeError('planted'))
    faults, before = recorder.recording_errors, newest_order(recorder)

    with pytest.MonkeyPatch.context() as context:
        context.delitem(sys.modules, stand_in)
        assert stand_in not in sys.modules
        assert recorder.recording_errors == faults + 1

    assert stand_in in sys.modules
    mocker.stopall()
    begun = recorder.begin(made_by='next', whole_dictionary=False, caller=None)
    assert begun is not None
    assert begun[0].order == before + 1  # the fault used no order number


def test_a_fault_after_the_call_is_counted_and_the_call_still_returns(recorder, stand_in, mocker):
    """Completing the entry failing changes nothing the caller sees either."""
    mocker.patch.object(module_removals.Removal, 'model_copy', side_effect=RuntimeError('planted'))
    faults = recorder.recording_errors

    with pytest.MonkeyPatch.context() as context:
        context.delitem(sys.modules, stand_in)
        assert recorder.recording_errors == faults + 1


def test_a_fault_deciding_is_counted_and_the_call_still_runs(recorder, mocker):
    """A pytest or mock whose insides changed leaves the call as it was."""
    faults = recorder.recording_errors

    method = recorder.wrapping(
        original=lambda value: value * 2,
        made_by='a probe',
        decide=mocker.Mock(side_effect=RuntimeError('planted')),
    )

    assert method(21) == 42
    assert recorder.recording_errors == faults + 1


def test_an_interrupt_in_the_recording_is_not_swallowed(recorder, mocker):
    """Ctrl-C while recording still reaches the run."""
    mocker.patch.object(module_removals, 'loads_in_progress', side_effect=KeyboardInterrupt)

    with pytest.raises(KeyboardInterrupt):
        recorder.begin(made_by='a probe', whole_dictionary=False, caller=None)

    mocker.stopall()


def test_only_the_newest_removals_and_some_of_their_names_are_kept(recorder):
    """Both are bounded; the count of names is not."""
    before = newest_order(recorder)
    with pytest.MonkeyPatch.context() as context:
        for index in range(NAMES_KEPT + 5):
            context.setitem(sys.modules, f'{STAND_IN}_{index}', types.ModuleType(STAND_IN))
    removal = recorder.removals()[0]

    assert removal.removed_count == NAMES_KEPT + 5
    assert len(removal.names_removed) == NAMES_KEPT
    assert 'and 5 more' in module_removals.removal_report(removal)

    for _ in range(REMOVALS_KEPT + 7):
        with pytest.MonkeyPatch.context() as context:
            context.setitem(sys.modules, STAND_IN, types.ModuleType(STAND_IN))
    orders = [kept.order for kept in recorder.removals()]
    newest = before + 1 + REMOVALS_KEPT + 7
    assert orders == list(range(newest, newest - REMOVALS_KEPT, -1))


def test_an_entry_pushed_out_before_its_call_ended_stays_out(recorder):
    """Completing an old entry does not overwrite the newer one in its place."""
    begun = recorder.begin(made_by='old', whole_dictionary=False, caller=None)
    for _ in range(REMOVALS_KEPT):
        recorder.complete(recorder.begin(made_by='new', whole_dictionary=False, caller=None))
    recorder.complete(begun)

    assert {removal.made_by for removal in recorder.removals()} == {'new'}


def test_removals_on_several_threads_are_all_recorded(recorder):
    """Each is kept once, with its own order number and its own thread's name."""
    barrier = threading.Barrier(4)
    each = REMOVALS_KEPT // 8
    before = newest_order(recorder)

    def record() -> None:
        barrier.wait(timeout=30)
        for _ in range(each):
            recorder.complete(recorder.begin(made_by='t', whole_dictionary=False, caller=None))

    threads = [threading.Thread(target=record, name=f'recording-{n}') for n in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    made = [removal for removal in recorder.removals() if removal.order > before]
    assert [removal.order for removal in made] == list(range(before + 4 * each, before, -1))
    assert not any(removal.on_main_thread for removal in made)
    for thread in threads:
        assert sum(removal.thread_name == thread.name for removal in made) == each


# A module whose own import removes it through monkeypatch, on the importing thread
REMOVES_ITSELF = (
    'import sys, pytest\ncontext = pytest.MonkeyPatch()\ncontext.delitem(sys.modules, __name__)\n'
)

# The same from a finalizer the collector runs during the import
FINALIZER_REMOVES_IT = (
    'import gc, sys, pytest\n'
    'name = __name__\n'
    'class Finalized:\n'
    '    def __del__(self, delitem=pytest.MonkeyPatch().delitem, modules=sys.modules, name=name):\n'
    '        delitem(modules, name)\n'
    'cycle = Finalized()\n'
    'cycle.itself = cycle\n'
    'del cycle\n'
    'gc.collect()\n'
)


@pytest.mark.parametrize(
    ('source', 'function'),
    [
        pytest.param(REMOVES_ITSELF, '<module>', id='own-code'),
        pytest.param(FINALIZER_REMOVES_IT, '__del__', id='finalizer'),
    ],
)
def test_a_removal_by_the_importing_thread_is_marked_same_thread(
    recorder, tmp_path, monkeypatch, source, function
):
    """Code the import runs, a finalizer included, shows as the same thread, with its stack."""
    (tmp_path / 'removed_by_itself.py').write_text(source)
    monkeypatch.syspath_prepend(tmp_path)

    with pytest.raises(KeyError, match='removed_by_itself'):
        importlib.import_module('removed_by_itself')

    removal = recorder.removals()[0]
    assert removal.names_removed == ('removed_by_itself',)
    assert removal.overlaps == (LoadInProgress(module='removed_by_itself', same_thread=True),)
    assert removal.stack[0].endswith(f' {function}')
    report = module_removals.removal_report(removal)
    assert 'OVERLAPS AN IMPORT' in report
    assert 'overlapped: removed_by_itself (the same thread)' in report


def test_a_removal_of_something_else_during_an_import_is_not_an_overlap(
    recorder, stand_in, tmp_path, monkeypatch
):
    """A module executing is listed, unmarked, when the call removed only another module."""
    (tmp_path / 'removes_another.py').write_text(
        'import sys, pytest\n'
        'context = pytest.MonkeyPatch()\n'
        f'context.delitem(sys.modules, {stand_in!r})\n'
    )
    monkeypatch.syspath_prepend(tmp_path)
    try:
        importlib.import_module('removes_another')
    finally:
        sys.modules.pop('removes_another', None)

    removal = recorder.removals()[0]
    assert removal.overlaps == ()
    report = module_removals.removal_report(removal)
    assert 'OVERLAPS' not in report
    assert 'other modules executing: removes_another (the same thread)' in report


def test_a_thread_unknown_to_threading_is_named_by_its_ident():
    """No dummy thread is registered for it."""
    threads = threading.enumerate()

    assert module_removals.thread_name(-1) == 'unregistered thread -1'
    assert threading.enumerate() == threads


def test_an_empty_record_says_so_and_what_is_not_recorded():
    """The limits are said even with nothing to show."""
    report = module_removals.removals_report(module_removals.RemovalRecorder())

    assert NOT_RECORDED in report
    assert 'none recorded' in report


@pytest.mark.parametrize(
    ('error', 'expected'),
    [
        (KeyError('sys.missing_part'), ['sys.missing_part: NOT in sys.modules', 'sys: in']),
        (ImportError('x', name='sys'), ['sys: in sys.modules']),
        (ImportError('x'), ['the failure names no module']),
        (KeyError(3), ['the failure names no module']),
        (ValueError('x'), ['the failure names no module']),
    ],
)
def test_the_state_says_whether_the_module_and_its_packages_are_present(error, expected):
    """The name comes from KeyError or ImportError; each parent package is looked up too."""
    report = module_removals.modules_state_report(
        error=error, recorder=module_removals.RemovalRecorder()
    )

    for line in expected:
        assert line in report
    assert 'sys.modules is the dictionary seen at startup' in report


def test_the_state_says_when_sys_modules_was_rebound(monkeypatch):
    """A new dictionary in sys.modules's place is named as such; both count as sys.modules."""
    recorder = module_removals.RemovalRecorder()
    original = sys.modules
    monkeypatch.setattr(sys, 'modules', dict(sys.modules))

    report = module_removals.modules_state_report(error=KeyError('sys'), recorder=recorder)

    assert 'sys.modules is NOT the dictionary seen at startup' in report
    assert recorder.is_modules(original)
    assert recorder.is_modules(sys.modules)


@pytest.mark.parametrize(('enabled', 'word'), [(True, 'enabled'), (False, 'disabled')])
def test_the_state_says_whether_garbage_collection_is_on(mocker, enabled, word):
    """Off, no finalizer of a cycle could have run by itself."""
    mocker.patch.object(gc, 'isenabled', return_value=enabled)

    report = module_removals.modules_state_report(
        error=KeyError('sys'), recorder=module_removals.RemovalRecorder()
    )

    assert f'garbage collection: {word}' in report


def wrapped_now() -> list[object]:
    """The methods now in place where the wrappers go."""
    return [vars(method.owner)[method.name] for method in module_removals.wrapped_methods()]


def test_installing_again_shares_the_wrappers(recorder):
    """The second install wraps nothing more; its release leaves the first one's wrappers."""
    in_place = wrapped_now()

    again = module_removals.install()
    assert again is recorder
    assert wrapped_now() == in_place
    module_removals.release(again)

    assert wrapped_now() == in_place


def test_a_second_copy_of_the_module_shares_the_wrappers(recorder):
    """An inner run whose snapshot dropped this module imports it again: still one recorder."""
    specification = importlib.util.spec_from_file_location(
        'second_copy_of_module_removals', module_removals.__file__
    )
    assert specification is not None
    assert specification.loader is not None
    copy = importlib.util.module_from_spec(specification)
    # pydantic looks its module up to resolve the annotations
    sys.modules[specification.name] = copy
    try:
        specification.loader.exec_module(copy)
        in_place = wrapped_now()
        installs = recorder.installs

        shared = copy.install()
        assert shared is recorder
        assert recorder.installs == installs + 1
        copy.release(shared)
    finally:
        del sys.modules[specification.name]

    assert wrapped_now() == in_place


CHILD_RUNS = 20


def test_twenty_runs_in_this_process_leave_nothing_behind(pytester, monkeypatch, recorder):
    """With the outer run's wrappers in place, each inner run shares and gives them back."""
    pytester.makepyfile(test_inner='def test_passes():\n    pass\n')
    in_place, installs, start = wrapped_now(), recorder.installs, threading.Thread.start
    node_id = recorder.running_test_node_id

    for _ in range(CHILD_RUNS):
        result = pytester.runpytest_inprocess(
            '-p', 'tests.import_failure_threads', '-p', 'no:cacheprovider', '-o', 'addopts='
        )
        result.assert_outcomes(passed=1)

    assert wrapped_now() == in_place
    assert recorder.installs == installs
    assert recorder.running_test_node_id == node_id
    assert threading.Thread.start is start


def test_the_last_release_puts_the_original_methods_back(pytester, monkeypatch):
    """In a run without the plugin, twenty inner runs with it each restore every method.

    Each inner run imports the plugin anew there: pytester's restore drops it after the run. A
    method something else replaced meanwhile is left alone.
    """
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    pytester.makepyfile(
        test_outer=f"""
import threading
import pytest
from _pytest.pytester import SysModulesSnapshot
from unittest import mock

PATCH_DICT = type(mock.patch.dict({{}}))
def methods():
    return [vars(PATCH_DICT)['_patch_dict'], vars(PATCH_DICT)['_unpatch_dict'],
            vars(SysModulesSnapshot)['restore'], vars(pytest.MonkeyPatch)['delitem'],
            vars(pytest.MonkeyPatch)['undo'], threading.Thread.start]

ORIGINALS = methods()

def test_inner_runs(pytester):
    pytester.makepyfile(test_inner='''
import pytest
def test_is_wrapped():
    assert hasattr(pytest.MonkeyPatch.undo, {RECORDER_ATTRIBUTE!r})
''')
    for _ in range({CHILD_RUNS}):
        result = pytester.runpytest_inprocess(
            '-p', 'tests.import_failure_threads', '-p', 'no:cacheprovider')
        result.assert_outcomes(passed=1)
        assert methods() == ORIGINALS

def test_a_replaced_method_is_left_alone(monkeypatch):
    from tests import module_removals
    recorder = module_removals.install()
    replacement = lambda snapshot: None
    wrapper, SysModulesSnapshot.restore = SysModulesSnapshot.restore, replacement
    module_removals.release(recorder)
    assert SysModulesSnapshot.restore is replacement
    wrapper(SysModulesSnapshot())
    assert recorder.removals() == []
    SysModulesSnapshot.restore = ORIGINALS[2]
    assert methods() == ORIGINALS
"""
    )

    result = pytester.runpytest_subprocess(
        '-p', 'pytester', '-p', 'no:cacheprovider', '-n', '0', '--no-cov', '-o', 'addopts='
    )

    result.assert_outcomes(passed=2)
