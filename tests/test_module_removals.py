"""Tests for tests/module_removals.py: the record of known removals from sys.modules."""

from __future__ import annotations

import gc
import importlib.util
import itertools
import sys
import threading
import types
import weakref
from collections import UserDict
from pathlib import Path

import pytest
from _pytest.pytester import SysModulesSnapshot

from tests import module_removals
from tests.module_removals import (
    MARKS_ARE_SAMPLES,
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
    assert removal.may_overlap == (LoadInProgress(module='removed_by_itself', same_thread=True),)
    assert removal.stack[0].endswith(f' {function}')
    report = module_removals.removal_report(removal)
    assert 'MAY OVERLAP AN IMPORT' in report
    assert 'may overlap: removed_by_itself (the same thread)' in report


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
    assert removal.may_overlap == ()
    report = module_removals.removal_report(removal)
    assert 'MAY OVERLAP' not in report
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
    assert MARKS_ARE_SAMPLES in report
    assert 'none recorded' in report


def test_both_dictionaries_count_once_sys_modules_is_rebound(monkeypatch):
    """The one seen at startup and the one there now are both sys.modules."""
    recorder = module_removals.RemovalRecorder()
    original = sys.modules
    monkeypatch.setattr(sys, 'modules', dict(sys.modules))

    assert recorder.is_modules(original)
    assert recorder.is_modules(sys.modules)


def by_delitem() -> None:
    """Remove a name through monkeypatch."""
    sys.modules[STAND_IN] = types.ModuleType(STAND_IN)
    with pytest.MonkeyPatch.context() as context:
        context.delitem(sys.modules, STAND_IN)
    sys.modules.pop(STAND_IN)


def by_undo() -> None:
    """Remove a name by undoing a setitem."""
    with pytest.MonkeyPatch.context() as context:
        context.setitem(sys.modules, STAND_IN, types.ModuleType(STAND_IN))


class Held:
    """A caller's local that can be watched."""


@pytest.mark.parametrize('beside_another_thread', [False, True])
@pytest.mark.parametrize('remove', [by_delitem, by_undo, 'patch_dict'])
def test_recording_keeps_nothing_of_the_caller_alive(
    recorder, mocker, remove, beside_another_thread
):
    """With collection off, the caller's locals go when it returns, and nothing of ours is left."""
    patch_dict = mocker.mock_module.patch.dict

    def call_it() -> weakref.ref[Held]:
        held = Held()
        if remove == 'patch_dict':
            with patch_dict(sys.modules):
                pass
        else:
            remove()
        return weakref.ref(held)

    release = threading.Event()
    other = threading.Thread(target=release.wait, name='beside')
    if beside_another_thread:
        other.start()
    was_enabled = gc.isenabled()
    flags = gc.get_debug()
    gc.collect()
    gc.disable()
    try:
        held = call_it()
        assert held() is None
        gc.set_debug(gc.DEBUG_SAVEALL)
        gc.collect()
        ours = [
            found
            for found in gc.garbage
            if type(found).__module__ == module_removals.__name__
            or (
                isinstance(found, types.FrameType)
                and found.f_code.co_filename == module_removals.__file__
            )
        ]
        assert ours == []
    finally:
        gc.set_debug(flags)
        gc.garbage.clear()
        if was_enabled:
            gc.enable()
        release.set()
        if beside_another_thread:
            other.join()


def test_every_load_on_a_stack_is_found(recorder, stand_in, tmp_path, monkeypatch):
    """A module importing another is loading too: the scan goes past the first load it finds."""
    (tmp_path / 'outer_load_probe.py').write_text('import inner_load_probe\n')
    (tmp_path / 'inner_load_probe.py').write_text(
        'import sys, pytest\n'
        'pytest.MonkeyPatch().delitem(sys.modules, "outer_load_probe")\n'
        'sys.modules["outer_load_probe"] = sys.modules[__name__]\n'
    )
    monkeypatch.syspath_prepend(tmp_path)
    try:
        importlib.import_module('outer_load_probe')
    finally:
        sys.modules.pop('outer_load_probe', None)
        sys.modules.pop('inner_load_probe', None)

    removal = recorder.removals()[0]
    assert [load.module for load in removal.loads_in_progress] == [
        'inner_load_probe',
        'outer_load_probe',
    ]
    assert [load.module for load in removal.may_overlap] == ['outer_load_probe']


def test_a_whole_restore_may_overlap_a_load_it_removed_nothing_of(
    recorder, mocker, tmp_path, monkeypatch
):
    """The module was in the snapshot, so it came back; it was gone in between."""
    (tmp_path / 'restores_probe.py').write_text(
        'import sys\nfrom unittest import mock\nwith mock.patch.dict(sys.modules):\n    pass\n'
    )
    monkeypatch.syspath_prepend(tmp_path)
    try:
        importlib.import_module('restores_probe')
    finally:
        sys.modules.pop('restores_probe', None)

    removal = recorder.removals()[0]
    assert removal.names_removed == ()
    assert removal.may_overlap == (LoadInProgress(module='restores_probe', same_thread=True),)


def test_a_whole_restore_is_marked_before_it_ends(recorder, mocker):
    """An import failing while the restore still runs finds the mark already there."""
    load = LoadInProgress(module='a_load', same_thread=False)
    mocker.patch.object(module_removals, 'loads_in_progress', return_value=(load,))
    begun = recorder.begin(made_by='a probe', whole_dictionary=True, caller=None)

    assert recorder.removals()[0].may_overlap == (load,)
    mocker.stopall()
    recorder.complete(begun)


@pytest.mark.parametrize(('whole_dictionary', 'marked'), [(True, True), (False, False)])
def test_a_load_that_began_during_the_call_is_listed_too(
    recorder, mocker, whole_dictionary, marked
):
    """The loads are read again after the call; removing nothing of it, only a restore marks it."""
    load = LoadInProgress(module='a_load', same_thread=False)
    mocker.patch.object(module_removals, 'loads_in_progress', side_effect=[(), (load,)])
    recorder.complete(
        recorder.begin(made_by='a probe', whole_dictionary=whole_dictionary, caller=None)
    )
    mocker.stopall()

    removal = recorder.removals()[0]
    assert removal.loads_after == (load,)
    assert removal.may_overlap == ((load,) if marked else ())
    report = module_removals.removal_report(removal)
    assert ('MAY OVERLAP' in report) is marked
    assert ('other modules executing: a_load' in report) is not marked


def test_every_method_is_there_to_wrap(recorder):
    """A pytest or Python that renames one fails here, and nowhere else."""
    assert len(module_removals.wrapped_methods()) == 5
    assert recorder.not_wrapped == []
    for method in wrapped_now():
        assert vars(method)[RECORDER_ATTRIBUTE] is recorder


@pytest.mark.parametrize('missing', ['method', 'class'])
def test_a_missing_method_is_skipped_and_said(mocker, missing):
    """The rest are wrapped, and put back; the report names the one that is not."""
    in_place = wrapped_now()
    all_methods = module_removals.wrapped_methods()
    if missing == 'method':
        broken = all_methods[2]._replace(name='renamed_since')
    else:
        broken = all_methods[2]._replace(find_owner=mocker.Mock(side_effect=ImportError))
    mocker.patch.object(
        module_removals,
        'wrapped_methods',
        return_value=(*all_methods[:2], broken, *all_methods[3:]),
    )
    recorder = module_removals.RemovalRecorder()
    recorder.wrap_methods()
    try:
        assert recorder.not_wrapped == [broken.made_by]
        assert f'not recorded: {broken.made_by}' in module_removals.removals_report(recorder)
        assert vars(pytest.MonkeyPatch)['undo'] is not in_place[4]
        assert module_removals.recorder_in_place() is recorder
    finally:
        recorder.unwrap_methods()
        mocker.stopall()

    assert wrapped_now() == in_place


def test_a_mock_in_a_methods_place_is_not_taken_for_the_recorder(recorder, mocker):
    """A mock answers for every attribute: the search goes on to the real wrapper."""
    mocker.patch.object(module_removals.patch_dict_class(), '_patch_dict', mocker.MagicMock())
    found = module_removals.recorder_in_place()
    mocker.stopall()

    assert found is recorder


def test_no_method_at_all_shares_nothing(mocker):
    """With nothing to find, there is no recorder in place."""
    mocker.patch.object(module_removals, 'wrapped_methods', return_value=())

    assert module_removals.recorder_in_place() is None


def test_an_interrupted_install_puts_back_what_it_wrapped(mocker):
    """Ctrl-C half-way leaves no wrapper."""
    in_place = wrapped_now()
    all_methods = module_removals.wrapped_methods()
    stopped = all_methods[1]._replace(find_owner=mocker.Mock(side_effect=KeyboardInterrupt))
    mocker.patch.object(module_removals, 'wrapped_methods', return_value=(all_methods[0], stopped))

    with pytest.raises(KeyboardInterrupt):
        module_removals.RemovalRecorder().wrap_methods()
    mocker.stopall()

    assert wrapped_now() == in_place


class ComparedDictionary(UserDict):
    """A patch target whose comparison must never run."""

    __hash__ = None

    def __eq__(self, other):
        """Fail: the target is never compared."""
        pytest.fail('the target was compared')


def test_a_targets_own_comparison_is_never_run(recorder, mocker):
    """patch.dict is given any dictionary-like object; its __eq__ is the test's code."""
    faults = recorder.recording_errors
    target = ComparedDictionary(key=1)

    mocker.patch.dict(target, clear=True)
    assert len(target) == 0
    mocker.stopall()

    assert len(target) == 1
    assert recorder.recording_errors == faults


def test_the_wrappers_are_hidden_from_tracebacks(pytester, monkeypatch):
    """A test's own KeyError from delitem shows no frame of ours."""
    monkeypatch.setenv('PYTHONPATH', str(PROJECT_ROOT))
    pytester.makepyfile(
        test_hidden='import sys\n'
        'def test_it(monkeypatch):\n'
        "    monkeypatch.delitem(sys.modules, 'no_such_name')\n"
    )

    result = pytester.runpytest_subprocess(
        '-p', 'tests.import_failure_threads', '-p', 'no:cacheprovider', '-n', '0', '--no-cov',
        '-o', 'addopts=',
    )  # fmt: skip

    result.assert_outcomes(failed=1)
    assert 'module_removals.py' not in result.stdout.str()


@pytest.fixture
def unshared_recorder():
    """A recorder of the test's own: the harness's calls never reach its broken parts.

    Returns:
        It, recording.

    """
    own = module_removals.RemovalRecorder()
    own.installs = 1
    return own


@pytest.mark.parametrize('interrupted', ['decide', 'begin'])
def test_an_interrupt_before_the_call_does_not_skip_it(unshared_recorder, mocker, interrupted):
    """The restore still happens, and Ctrl-C still reaches the run."""
    recorder = unshared_recorder
    original = mocker.Mock(return_value='result')
    decide = mocker.Mock(return_value=module_removals.Recorded.WHOLE_DICTIONARY)
    if interrupted == 'decide':
        decide.side_effect = KeyboardInterrupt
    else:
        mocker.patch.object(recorder, 'begin', side_effect=KeyboardInterrupt)
    method = recorder.wrapping(original=original, made_by='a probe', decide=decide)

    with pytest.raises(KeyboardInterrupt):
        method('argument', key='value')

    original.assert_called_once_with('argument', key='value')


def test_an_interrupt_after_the_call_does_not_hide_what_it_raised(unshared_recorder, mocker):
    """The call's own exception is the one that gets out; the dropped Ctrl-C is counted."""
    recorder = unshared_recorder
    faults = recorder.recording_errors
    mocker.patch.object(recorder, 'complete', side_effect=KeyboardInterrupt)
    method = recorder.wrapping(
        original=mocker.Mock(side_effect=LookupError('its own')),
        made_by='a probe',
        decide=mocker.Mock(return_value=module_removals.Recorded.WHOLE_DICTIONARY),
    )

    with pytest.raises(LookupError, match='its own'):
        method()

    assert recorder.recording_errors == faults + 1


def test_an_interrupt_after_a_call_that_returned_goes_on(unshared_recorder, mocker):
    """Nothing is hidden by it, so it is raised."""
    recorder = unshared_recorder
    mocker.patch.object(recorder, 'complete', side_effect=KeyboardInterrupt)
    method = recorder.wrapping(
        original=mocker.Mock(),
        made_by='a probe',
        decide=mocker.Mock(return_value=module_removals.Recorded.WHOLE_DICTIONARY),
    )

    with pytest.raises(KeyboardInterrupt):
        method()


def wrapped_now() -> list[object]:
    """The methods now in place where the wrappers go."""
    return [vars(method.find_owner())[method.name] for method in module_removals.wrapped_methods()]


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
