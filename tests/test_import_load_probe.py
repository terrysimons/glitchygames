"""Tests for tests/import_load_probe.py: where an import's sys.modules entry was lost."""

from __future__ import annotations

import _thread
import dis
import gc
import importlib
import importlib.machinery
import inspect
import sys
import threading
import types
from pathlib import Path

import pytest

from tests import import_load_probe
from tests.import_load_probe import (
    ABSENT,
    COLLECTIONS_KEPT,
    ENDED,
    EVENTS_KEPT,
    EVIDENCE_NOT_A_FIX,
    FAULTS,
    HOW_TO_READ,
    LOADED_NAMES_KEPT,
    NOT_READ,
    POP_CALLED,
    POP_LINE,
    POP_RAISED,
    POP_RETURNED,
    PRESENT,
    STORED,
    TOOL_IDS,
    Load,
    LoadProbe,
    Reading,
    UnrecognisedShapeError,
    find_load_points,
    interpreter_report,
    load_code,
    load_probe_report,
    verdict_of,
)

PACKAGE = 'import_load_probe_stand_in'
GONE_WHILE_RUNNING = "left between the store and the pop's line"
WENT_IN_COLLECTION = 'THE ENTRY WENT DURING THIS COLLECTION'
DELETE_ITSELF = 'import sys\ndel sys.modules[__name__]\n'


@pytest.fixture
def probe():
    """A probe of the test's own on the real importlib, beside the run's.

    Yields:
        It, installed.

    """
    own = LoadProbe(code=load_code())
    own.install()
    assert own.not_recorded is None
    yield own
    own.uninstall()
    remove_stand_ins()


def remove_stand_ins() -> None:
    """Take every stand-in module out of sys.modules."""
    for name in [name for name in sys.modules if str(name).startswith(PACKAGE)]:
        sys.modules.pop(name)


@pytest.fixture
def module(tmp_path, monkeypatch):
    """Importable modules written by the test, gone from sys.modules at the end.

    Yields:
        A function that writes one and returns its name.

    """
    monkeypatch.syspath_prepend(tmp_path)

    def write(source: str, *, name: str = PACKAGE) -> str:
        path = tmp_path / f'{name.replace(".", "/")}.py'
        path.parent.mkdir(exist_ok=True)
        path.write_text(source)
        return name

    yield write
    remove_stand_ins()


def events_of(probe: LoadProbe, name: str) -> list[Reading]:
    """One module's events, oldest first."""
    return [event for event in probe.events() if event.name == name]


def found_at(probe: LoadProbe, name: str) -> dict[str, str]:
    """What was found at each point of a module's only load."""
    return {event.point: event.found for event in events_of(probe, name)}


def failed_import(name: str) -> KeyError:
    """Import a module whose pop must really fail."""
    with pytest.raises(KeyError) as excinfo:
        importlib.import_module(name)
    return excinfo.value


def report_of(probe: LoadProbe, error: BaseException, *, failed_name: str | None = PACKAGE) -> str:
    """Write the section for an error."""
    return load_probe_report(
        probe=probe, failed_name=failed_name, traceback_object=error.__traceback__
    )


def verdict_line(report: str) -> str:
    """The report's one verdict."""
    (line,) = [line for line in report.splitlines() if line.startswith('VERDICT')]
    return line


def test_a_normal_import_is_present_until_its_pop_and_again_after(probe, module):
    """The points come in order, each reading the entry, and nothing is left in progress."""
    importlib.import_module(module(''))

    events = events_of(probe, PACKAGE)
    assert [(event.point, event.found) for event in events] == [
        (STORED, PRESENT),
        (POP_LINE, PRESENT),
        (POP_CALLED, PRESENT),
        (POP_RETURNED, ABSENT),
        (ENDED, PRESENT),
    ]
    assert [event.order for event in events] == sorted({event.order for event in events})
    assert {event.thread_ident for event in events} == {threading.get_ident()}
    assert all(event.dictionary_is_sys_modules for event in events)
    assert probe._stacks == {}
    assert list(probe.failed_pops) == []
    assert list(probe.ended_before_pop) == []
    assert probe.faults == 0
    assert probe.newest_order >= events[-1].order


def test_a_module_that_removes_itself_is_placed_in_its_own_code(probe, module):
    """A real KeyError: present after the store, absent at the pop, with no collection to blame."""
    importlib.import_module(module('', name=f'{PACKAGE}_before'))
    gc.disable()
    try:
        error = failed_import(module(DELETE_ITSELF))
    finally:
        gc.enable()

    assert found_at(probe, PACKAGE) == {
        STORED: PRESENT,
        POP_LINE: ABSENT,
        POP_CALLED: ABSENT,
        POP_RAISED: ABSENT,
        ENDED: ABSENT,
    }
    report = report_of(probe, error)
    assert GONE_WHILE_RUNNING in verdict_line(report)
    assert WENT_IN_COLLECTION not in report
    assert 'as the pop raised: ABSENT by hash, NOT found by iteration' in report
    assert 'loading inside: nothing' in report
    assert f'{PACKAGE}_before' not in report
    assert EVIDENCE_NOT_A_FIX in report
    for line in HOW_TO_READ:
        assert line in report


def test_a_finalizer_in_a_collection_is_placed_in_that_collection(probe, module):
    """The same verdict, and the collection that saw the entry go is marked."""
    error = failed_import(
        module(
            'import gc, sys\n'
            'class Cycle:\n'
            '    def __del__(self, modules=sys.modules, name=__name__):\n'
            '        modules.pop(name)\n'
            'cycle = Cycle()\n'
            'cycle.itself = cycle\n'
            'del cycle\n'
            'gc.collect()\n'
        )
    )

    report = report_of(probe, error)
    assert GONE_WHILE_RUNNING in verdict_line(report)
    (marked,) = [line for line in report.splitlines() if WENT_IN_COLLECTION in line]
    assert 'garbage collection of generation 2 on MainThread' in marked
    assert f'{PACKAGE} (loading on the same thread) {PRESENT} before, {ABSENT} after' in marked


def paused_import(probe: LoadProbe, module, *, while_paused) -> KeyError:
    """Import a module on a thread; run something here while its code is paused."""
    name = module(
        'import sys\n'
        f"meeting = sys.modules['{PACKAGE}_meeting']\n"
        'meeting.ENTERED.set()\n'
        'if not meeting.GO_ON.wait(timeout=30):\n'
        "    raise RuntimeError('never told to go on')\n"
    )
    meeting = types.ModuleType(f'{PACKAGE}_meeting')
    entered, go_on = threading.Event(), threading.Event()
    vars(meeting).update(ENTERED=entered, GO_ON=go_on)
    sys.modules[meeting.__name__] = meeting
    errors: list[KeyError] = []

    def import_it() -> None:
        try:
            importlib.import_module(name)
        except KeyError as error:
            errors.append(error)

    thread = threading.Thread(target=import_it, name='importer')
    thread.start()
    try:
        assert entered.wait(timeout=30)
        while_paused(name)
    finally:
        go_on.set()
        thread.join()
    return errors[0]


def test_another_threads_removal_is_placed_in_the_code_with_that_thread_alive(probe, module):
    """The remover was alive at the pop: named with its stack, and not told from the module."""
    error = paused_import(probe, module, while_paused=sys.modules.pop)

    report = report_of(probe, error)
    assert GONE_WHILE_RUNNING in verdict_line(report)
    assert 'alive as the pop raised: MainThread in ' in report
    assert WENT_IN_COLLECTION not in report
    assert 'nothing\n  here tells those two apart' in report


def test_a_collection_on_another_thread_names_the_load_it_interrupted(probe, module):
    """With nothing loading on its own thread, a collection reads the other thread's load."""

    def collect_and_remove(name: str) -> None:
        gc.collect()
        sys.modules.pop(name)

    report = report_of(probe, paused_import(probe, module, while_paused=collect_and_remove))

    assert f'{PACKAGE} (loading on another thread) {PRESENT} before, {PRESENT} after' in report


def test_a_thread_threading_does_not_know_is_named_by_ident(probe, module):
    """Started through _thread: its ident stands in the report."""
    release = _thread.allocate_lock()
    release.acquire()
    started, ended = threading.Event(), threading.Event()

    def wait() -> None:
        started.set()
        release.acquire()
        ended.set()

    ident = _thread.start_new_thread(wait, ())
    assert started.wait(timeout=30)
    try:
        report = report_of(probe, failed_import(module(DELETE_ITSELF)))
    finally:
        release.release()
        assert ended.wait(timeout=30)

    assert f'alive as the pop raised: ident {ident} in {__file__}:' in report


def test_a_failing_import_ends_before_its_pop(probe, module):
    """The module's own exception: no pop was called, and the report says that."""
    name = module("raise ImportError('its own', name=__name__)\n")
    with pytest.raises(ImportError) as excinfo:
        importlib.import_module(name)

    assert found_at(probe, name) == {STORED: PRESENT, ENDED: ABSENT}
    report = report_of(probe, excinfo.value)
    assert verdict_line(report).endswith('no failed pop was recorded for a load in this traceback')
    assert f'the newest load of {PACKAGE} ended with its pop not seen' in report
    assert f'{PACKAGE}, after the store: present' in report
    assert list(probe.failed_pops) == []


def test_another_error_claims_nothing(probe, module):
    """A KeyError of the module's own, after a failed pop of that same name, is not that pop."""
    failed_import(module(DELETE_ITSELF))
    error = KeyError(PACKAGE)
    report = report_of(probe, error)

    assert verdict_line(report).endswith('no failed pop was recorded for a load in this traceback')
    assert 'ended with' not in report


def test_nested_imports_narrow_where_the_outer_entry_went(probe, module):
    """Seen present by the first module inside, absent by the second; each load is its own."""
    module('', name=f'{PACKAGE}_first')
    module('', name=f'{PACKAGE}_second')
    error = failed_import(
        module(f'import sys, {PACKAGE}_first\ndel sys.modules[__name__]\nimport {PACKAGE}_second\n')
    )

    report = report_of(probe, error)
    lines = report.splitlines()
    (present,) = [line for line in lines if line.startswith('last seen present from inside')]
    (absent,) = [line for line in lines if line.startswith('first seen absent from inside')]
    assert f'{PACKAGE}_first, {ENDED}' in present
    assert f'{PACKAGE}_second, {STORED}' in absent
    assert f'since the outermost import ({PACKAGE}) began, 2 modules finished' in report
    assert 'missing as the pop raised: none; missing now: none' in report
    assert found_at(probe, f'{PACKAGE}_first')[POP_CALLED] == PRESENT


def test_an_inner_failure_names_what_it_was_loading_inside(probe, module):
    """The nesting, outermost first, and the outer load ending before its own pop."""
    module('', name=f'{PACKAGE}.sibling')
    module(DELETE_ITSELF, name=f'{PACKAGE}.inner')
    module(
        f'from . import sibling\nimport sys\ndel sys.modules["{PACKAGE}.sibling"]\n'
        'from . import inner\n',
        name=f'{PACKAGE}.__init__',
    )
    report = report_of(probe, failed_import(PACKAGE))

    assert verdict_line(report).startswith(f'VERDICT for {PACKAGE}.inner: ')
    assert f'loading inside: {PACKAGE}\n' in report
    assert f'missing as the pop raised: {PACKAGE}.sibling; missing now: ' in report
    assert [load.name for load in probe.ended_before_pop] == [PACKAGE]
    assert probe._stacks == {}


class ProbeLoader:
    """A loader that runs a function as the module's code."""

    def __init__(self, execute=lambda module: None):
        """Run this."""
        self.execute = execute

    def create_module(self, spec):
        """Make a plain module."""
        return types.ModuleType(PACKAGE)

    def exec_module(self, module):
        """Run the function."""
        self.execute(module)


# A name that is a str, but not exactly
PlainStr = types.new_class('PlainStr', (str,))


@pytest.mark.parametrize('name', [3, PlainStr(PACKAGE)], ids=['int', 'str-subclass'])
def test_a_name_that_is_not_exactly_a_str_is_not_looked_up(probe, name):
    """Its hash and comparison are its own code: shown as its type, and not read."""
    spec = importlib.machinery.ModuleSpec(name, ProbeLoader(lambda _: sys.modules.pop(name)))
    with pytest.raises(KeyError) as excinfo:
        importlib._bootstrap._load_unlocked(spec)

    shown = f'<a {type(name).__name__}, not a str>'
    assert found_at(probe, shown) == dict.fromkeys(
        (STORED, POP_LINE, POP_CALLED, POP_RAISED, ENDED), NOT_READ
    )
    report = report_of(probe, excinfo.value)
    assert f'VERDICT for {shown}: not recorded' in report
    assert 'NOT found by iteration' in report
    assert probe.faults == 0


def test_a_name_that_is_not_a_str_is_nobodys_enclosing_entry(probe, module):
    """A module loaded inside one whose name cannot be read narrows nothing, and is itself read."""
    module('')
    spec = importlib.machinery.ModuleSpec(
        3, ProbeLoader(lambda _: importlib.import_module(PACKAGE))
    )
    importlib._bootstrap._load_unlocked(spec)
    sys.modules.pop(3)

    assert found_at(probe, PACKAGE)[POP_CALLED] == PRESENT
    assert probe.faults == 0


def spec_class(read):
    """A spec whose name runs a function at each read, its __dict__ holding the name as ever."""

    def keep(spec, value):
        vars(spec)['name'] = value

    return types.new_class(
        'ReadSpec',
        (importlib.machinery.ModuleSpec,),
        exec_body=lambda body: body.update(name=property(read, keep)),
    )


def reading_name_at_pop(act):
    """A name property that acts when read after the module's code ran."""

    def read(spec):
        if getattr(spec, 'ran', False):
            return act(spec)
        return vars(spec)['name']

    return read


def load_with_spec(spec) -> KeyError:
    """Load a spec whose pop must fail."""
    with pytest.raises(KeyError) as excinfo:
        importlib._bootstrap._load_unlocked(spec)
    sys.modules.pop(PACKAGE, None)
    return excinfo.value


def test_an_entry_gone_between_the_pops_line_and_its_call_is_placed_there(probe):
    """A name property that removes the entry when the pop's line reads it: a real KeyError."""

    def remove(spec):
        sys.modules.pop(PACKAGE, None)
        return PACKAGE

    loader = ProbeLoader()
    spec = spec_class(reading_name_at_pop(remove))(PACKAGE, loader)
    loader.execute = lambda _: setattr(spec, 'ran', True)
    report = report_of(probe, load_with_spec(spec))

    assert "left between the start of the pop's line and the call" in verdict_line(report)


def test_a_pop_that_raises_with_the_entry_there_says_so_and_what_that_leaves_open(probe):
    """A simulated interpreter fault (the pop is really given another name): present throughout."""
    loader = ProbeLoader()
    spec = spec_class(reading_name_at_pop(lambda _: 'never-imported'))(PACKAGE, loader)
    loader.execute = lambda _: setattr(spec, 'ran', True)
    report = report_of(probe, load_with_spec(spec))

    assert 'present when pop was called, and pop raised' in verdict_line(report)
    assert 'as the pop raised: present by hash, found by iteration' in report
    assert 'perhaps an interpreter or dictionary fault' in report


def test_a_spec_renamed_during_its_load_is_not_recorded(probe):
    """The pop then looks for a name nothing was stored under: no claim about an entry."""
    loader = ProbeLoader()
    spec = importlib.machinery.ModuleSpec(PACKAGE, loader)
    loader.execute = lambda _: setattr(spec, 'name', 'never-imported')
    error = load_with_spec(spec)
    verdict = verdict_of(probe.failed_pops[-1].load)

    assert verdict == 'not recorded: the spec was renamed during the load'
    assert verdict_line(report_of(probe, error)).endswith('load in this traceback')


def test_another_object_under_the_name_is_told_from_the_module(probe, module):
    """A module that puts something else in its own place."""
    importlib.import_module(
        module(
            'import sys, types\nsys.modules[__name__] = types.SimpleNamespace(__spec__=__spec__)\n'
        )
    )

    assert found_at(probe, PACKAGE)[POP_CALLED] == 'present, but another object'


def test_a_dictionary_that_is_not_plain_is_not_read(probe, module, monkeypatch):
    """Its lookups would be its own code; a Python pop gives no outcome either."""

    def pop(modules, name):
        return dict.pop(modules, name)

    modules_class = types.new_class('Modules', (dict,), exec_body=lambda body: body.update(pop=pop))
    name = module('')
    monkeypatch.setattr(sys, 'modules', modules_class(sys.modules))
    importlib._bootstrap._load_unlocked(importlib.util.find_spec(name))
    monkeypatch.undo()

    assert found_at(probe, PACKAGE)[STORED] == NOT_READ
    assert POP_RETURNED not in found_at(probe, PACKAGE)


def test_a_pop_on_a_rebound_dictionary_reads_the_one_popped(probe, monkeypatch):
    """sys.modules rebound by the module's code: the new one, seen as sys.modules, lacks it."""
    loader = ProbeLoader(lambda _: monkeypatch.setattr(sys, 'modules', dict(original)))
    original = dict(sys.modules)
    with pytest.raises(KeyError):
        importlib._bootstrap._load_unlocked(importlib.machinery.ModuleSpec(PACKAGE, loader))
    monkeypatch.undo()

    assert found_at(probe, PACKAGE)[STORED] == PRESENT
    assert found_at(probe, PACKAGE)[POP_CALLED] == ABSENT


def reading(point: str, found: str) -> tuple:
    """One event's fields."""
    return (1, point, 1, 1, PACKAGE, 1, True, 0, found)


def test_a_store_that_left_nothing_is_its_own_verdict(probe):
    """No Python runs between the store and the next line: the readings are written by hand."""
    load = Load(key=PACKAGE, spec_id=1, number=1, thread_ident=1, enclosing=[])
    load.readings = {point: reading(point, ABSENT) for point in (STORED, POP_LINE, POP_CALLED)}

    assert verdict_of(load) == 'the entry was already absent at the first line after the store'

    load.readings.pop(POP_LINE)
    assert verdict_of(load).startswith('not recorded')


def test_a_dictionary_that_is_not_sys_modules_is_said():
    """The pop's own dictionary is compared with sys.modules."""
    fields = (1, POP_CALLED, 7, 1, PACKAGE, 3, False, 0, PRESENT)

    line = import_load_probe.reading_line(fields, names={})
    assert 'ident 7, 3 entries, a dictionary that is NOT sys.modules' in line


def test_the_rings_keep_only_the_newest(probe, module):
    """Past the bound the oldest events, collections and finished names go."""
    inner = [module('', name=f'{PACKAGE}_{index}') for index in range(LOADED_NAMES_KEPT + 5)]
    error = failed_import(
        module(
            f'import importlib, sys\n'
            f'for index in range({len(inner)}):\n'
            f"    importlib.import_module(f'{PACKAGE}_{{index}}')\n"
            'del sys.modules[__name__]\n'
        )
    )
    for _ in range(COLLECTIONS_KEPT + 5):
        gc.collect(0)

    assert len(probe.events()) == EVENTS_KEPT
    assert len(probe.collections()) == COLLECTIONS_KEPT
    assert probe.events()[-1].order - probe.events()[0].order >= EVENTS_KEPT - 1
    report = report_of(probe, error)
    listed = [line for line in report.splitlines() if line.startswith('  #')]
    assert len(listed) == import_load_probe.LINES_REPORTED
    assert f'{PACKAGE}, {POP_RAISED}' in listed[-1]
    # The load keeps its own readings, whatever the ring has lost
    assert f'{PACKAGE}, after the store: present' in report
    assert GONE_WHILE_RUNNING in verdict_line(report)
    assert f'{len(inner)} modules finished loading (the newest {LOADED_NAMES_KEPT} kept)' in report


def test_a_collection_is_kept_with_nothing_loading(probe):
    """Its generation and thread, and no module."""
    gc.collect(1)

    newest = probe.collections()[-1]
    assert (newest.generation, newest.name, newest.before) == (1, None, NOT_READ)
    assert 'nothing being loaded' in import_load_probe.collection_line(newest, names={})


def test_a_collection_that_began_before_the_probe_is_not_kept(probe):
    """Only its end is seen."""
    kept = probe.collections()
    probe.on_collection('stop', {'generation': 0, 'collected': 0})

    assert probe.collections() == kept
    assert probe.faults == 0


def test_a_load_that_began_before_the_probe_is_not_kept(module):
    """Installed by the module's own code: its later events belong to no load."""
    own = LoadProbe(code=load_code())
    installer = types.ModuleType(f'{PACKAGE}_installer')
    installer.install = own.install
    sys.modules[installer.__name__] = installer
    try:
        importlib.import_module(module(f'import {PACKAGE}_installer as i\ni.install()\n'))
        assert own.not_recorded is None
        assert events_of(own, PACKAGE) == []
    finally:
        own.uninstall()
    assert own.faults == 0


def test_a_failed_pop_of_a_load_that_began_before_the_probe_is_not_kept(module):
    """The raise is seen, but there is no load to put it in."""
    own = LoadProbe(code=load_code())
    installer = types.ModuleType(f'{PACKAGE}_installer')
    installer.install = own.install
    sys.modules[installer.__name__] = installer
    try:
        failed_import(module(f'import {PACKAGE}_installer as i\ni.install()\n{DELETE_ITSELF}'))
        assert list(own.failed_pops) == []
    finally:
        own.uninstall()
    assert own.faults == 0


def test_a_load_whose_end_was_missed_does_not_take_the_next_ones_events(probe):
    """A stale inner load is dropped when the one outside it goes on."""
    outer, inner = (importlib.machinery.ModuleSpec(name, None) for name in ('outer', 'inner'))
    ident = threading.get_ident()
    load = probe._begin(spec=outer, ident=ident)
    probe._begin(spec=inner, ident=ident)

    assert probe._in_progress(spec_id=id(outer), ident=ident) is load
    assert probe._stacks[ident] == [load]
    assert probe._in_progress(spec_id=id(inner), ident=ident) is None
    assert probe._stacks == {}


@pytest.fixture
def bootstrap_source():
    """The source of this Python's _load_unlocked."""
    return inspect.getsource(importlib._bootstrap._load_unlocked)


def compiled(source: str) -> types.CodeType:
    """Compile a function's source and return the function's code."""
    (code,) = [
        constant
        for constant in compile(source, 'shape', 'exec').co_consts
        if isinstance(constant, types.CodeType)
    ]
    return code


def test_this_pythons_shape_is_recognised_wherever_it_is(bootstrap_source):
    """The points follow the code, not a line number."""
    points = find_load_points(compiled(bootstrap_source))
    moved = find_load_points(compiled('\n' * 58 + bootstrap_source))
    lines = bootstrap_source.splitlines()

    assert lines[points.stored_line - 1].strip() == 'if spec.loader is None:'
    assert lines[points.pop_line - 1].strip() == 'module = sys.modules.pop(spec.name)'
    assert lines[points.ended_line - 1].strip() == 'spec._initializing = False'
    assert moved.pop_line == points.pop_line + 58
    assert moved.pop_call_offset == points.pop_call_offset


POP = 'module = sys.modules.pop(spec.name)'
STORE = 'sys.modules[spec.name] = module'


@pytest.mark.parametrize(
    ('old', 'new'),
    [
        pytest.param(POP, 'module = sys.modules[spec.name]', id='no-pop'),
        pytest.param(POP, f'{POP}; {POP}', id='two-pops'),
        pytest.param(POP, 'module = sys.modules.pop(spec.name, None)', id='pop-with-a-default'),
        pytest.param(f'{POP}\n        {STORE}', POP, id='no-second-store'),
        pytest.param(f'{STORE}\n        try:', 'try:', id='no-first-store'),
        pytest.param(f'{STORE}\n        try:', f'{STORE}; {STORE}\n        try:', id='two-stores'),
        pytest.param('spec.loader.exec_module(module)', 'run(spec, module)', id='no-execution'),
        pytest.param(
            f'{POP}\n', f'{POP}; spec.loader.exec_module\n', id='execution-after-the-pop-too'
        ),
        pytest.param('spec.loader.exec_module(module)', f'if spec: {POP}', id='pop-in-execution'),
        pytest.param(POP, f'print(spec); {POP}', id='pop-not-at-its-lines-start'),
        pytest.param(
            f'{POP}\n        {STORE}',
            f'{POP}; {STORE}; spec._initializing = False',
            id='end-on-the-pops-line-and-another',
        ),
        pytest.param('spec._initializing = False', 'pass', id='no-end'),
        pytest.param(
            'if spec.loader is None:',
            'if spec.loader.exec_module is None:',
            id='execution-named-twice',
        ),
        pytest.param('spec.loader.exec_module(module)', 'pass', id='nothing-executed'),
    ],
)
def test_an_unrecognised_shape_is_refused(bootstrap_source, old, new):
    """Anything but the shape known: no points, so no claim."""
    assert old in bootstrap_source
    with pytest.raises(UnrecognisedShapeError):
        find_load_points(compiled(bootstrap_source.replace(old, new, 1)))


def test_execution_outside_the_store_and_the_pop_is_refused(bootstrap_source):
    """The module's code run after the pop."""
    moved = bootstrap_source.replace('spec.loader.exec_module(module)', 'pass').replace(
        POP, f'{POP}\n        spec.loader.exec_module(module)'
    )
    with pytest.raises(UnrecognisedShapeError, match='execution is not between'):
        find_load_points(compiled(moved))


@pytest.mark.parametrize(
    ('changes', 'reason'),
    [
        pytest.param(
            {
                f'{STORE}\n        try:': f'{STORE}; {STORE}\n        try:',
                f'{POP}\n        {STORE}': POP,
            },
            'not one store',
            id='both-stores-before-the-pop',
        ),
        pytest.param(
            {
                'spec._initializing = False': 'pass',
                f'{POP}\n        {STORE}': f'{POP}; {STORE}; spec._initializing = False',
            },
            'not distinct',
            id='the-end-on-the-pops-line',
        ),
        pytest.param(
            {'if spec.loader is None:': 'for spec in spec.loader:'},
            'not distinct',
            id='the-line-after-the-store-starts-twice',
        ),
    ],
)
def test_points_out_of_place_are_refused(bootstrap_source, changes, reason):
    """Every piece is there, but not where its events would say what they are taken to say."""
    for old, new in changes.items():
        assert bootstrap_source.count(old) == 1
        bootstrap_source = bootstrap_source.replace(old, new)
    with pytest.raises(UnrecognisedShapeError, match=reason):
        find_load_points(compiled(bootstrap_source))


def on_one_line(source: str) -> types.CodeType:
    """Compile a function, then put all its instructions on one line."""
    code = compiled(source)
    # One location entry per run of at most 8 code units, each on the function's first line
    units = len(code.co_code) // 2
    table = bytearray()
    while units:
        run = min(units, 8)
        table += bytes([0x80 | (13 << 3) | (run - 1), 0])
        units -= run
    return code.replace(co_linetable=bytes(table))


def without_lines(source: str) -> types.CodeType:
    """Compile a function, then take its line numbers away."""
    code = compiled(source)
    units = len(code.co_code) // 2
    table = bytearray()
    while units:
        run = min(units, 8)
        table += bytes([0x80 | (15 << 3) | (run - 1)])
        units -= run
    return code.replace(co_linetable=bytes(table))


@pytest.mark.parametrize('strip', [on_one_line, without_lines])
def test_lines_that_cannot_place_the_points_are_refused(bootstrap_source, strip):
    """Stripped or merged line numbers: the shape is the same, the places are not known."""
    with pytest.raises(UnrecognisedShapeError):
        find_load_points(strip(bootstrap_source))


def test_an_instruction_without_a_line_is_refused(bootstrap_source):
    """The compiler gives its own cleanup none."""
    instruction = next(dis.get_instructions(without_lines(bootstrap_source)))
    with pytest.raises(UnrecognisedShapeError):
        import_load_probe.line_of(instruction)


def drive(probe: LoadProbe, *, spec, module, callback: str, arguments: tuple) -> object:
    """Call a callback as the interpreter does, this frame standing for _load_unlocked's.

    Coverage cannot see a callback the interpreter calls (monitoring is off inside one).
    """
    return getattr(probe, callback)(load_code(), *arguments)


def drive_load(probe: LoadProbe, *, spec, execute=lambda: None, dictionary=None) -> KeyError | None:
    """Run _load_unlocked's steps by hand, with its callbacks. Returns the pop's error."""
    module = types.ModuleType('driven')
    points = probe._points
    modules = sys.modules if dictionary is None else dictionary
    error = None

    def at(callback: str, *arguments) -> None:
        drive(probe, spec=spec, module=module, callback=callback, arguments=arguments)

    sys.modules[spec.name] = module
    at('on_line', points.stored_line)
    execute()
    at('on_line', points.pop_line)
    at('on_call', points.pop_call_offset, dict.pop, modules)
    try:
        popped = modules.pop(spec.name)
    except KeyError as raised:
        error = raised
        at('on_c_raise', points.pop_call_offset, dict.pop, modules)
    else:
        at('on_c_return', points.pop_call_offset, dict.pop, modules)
        sys.modules[spec.name] = popped
    at('on_line', points.ended_line)
    return error


def spec_named(name: object) -> importlib.machinery.ModuleSpec:
    """A spec with nothing to load."""
    return importlib.machinery.ModuleSpec(name, None)


def test_driven_by_hand_the_callbacks_read_what_the_interpreters_do(probe, module):
    """The same readings for a normal load and a failed pop as the real events gave."""
    importlib.import_module(module('', name=f'{PACKAGE}_a'))
    failed_import(module(DELETE_ITSELF, name=f'{PACKAGE}_b'))
    real = [found_at(probe, f'{PACKAGE}_{letter}') for letter in 'ab']

    assert drive_load(probe, spec=spec_named(f'{PACKAGE}_c')) is None
    gone = f'{PACKAGE}_d'
    assert drive_load(probe, spec=spec_named(gone), execute=lambda: sys.modules.pop(gone)).args == (
        gone,
    )

    assert [found_at(probe, f'{PACKAGE}_{letter}') for letter in 'cd'] == real
    assert probe.failed_pops[-1].load.name == gone
    assert probe.faults == 0


def test_driven_by_hand_an_enclosing_load_is_narrowed(probe):
    """Present from the first inside, absent from the second; another object and a rename told."""
    outer, first, second, third = (f'{PACKAGE}_{index}' for index in range(4))

    def execute() -> None:
        drive_load(probe, spec=spec_named(first))
        sys.modules.pop(outer)
        drive_load(probe, spec=spec_named(second))
        drive_load(probe, spec=spec_named(third))

    drive_load(probe, spec=spec_named(outer), execute=execute)
    load = probe.failed_pops[-1].load
    assert load.present_at[1:5:3] == (ENDED, first)
    assert load.absent_at[1:5:3] == (STORED, second)

    def replace() -> None:
        sys.modules[first] = types.ModuleType('another')

    sys.modules.pop(first)
    drive_load(probe, spec=spec_named(first), execute=replace)
    assert import_load_probe.ANOTHER_OBJECT in {event.found for event in events_of(probe, first)}


def test_driven_by_hand_what_cannot_be_read_is_not(probe):
    """A name not a str, with a load inside it; a dictionary of another type; a renamed spec."""
    inner = spec_named(f'{PACKAGE}_inner')
    drive_load(probe, spec=spec_named(3), execute=lambda: drive_load(probe, spec=inner))
    sys.modules.pop(3)
    assert set(found_at(probe, '<a int, not a str>').values()) == {NOT_READ}

    renamed = spec_named(PACKAGE)
    drive_load(probe, spec=renamed, execute=lambda: setattr(renamed, 'name', 'never-imported'))
    assert probe.failed_pops[-1].load.renamed

    other = spec_named(f'{PACKAGE}_other')
    drive_load(probe, spec=other, dictionary=types.MappingProxyType({}).copy() | {other.name: 1})
    assert found_at(probe, other.name)[POP_CALLED] == import_load_probe.ANOTHER_OBJECT
    assert probe.faults == 0


def test_driven_by_hand_every_callbacks_fault_is_counted(probe, mocker):
    """Each swallows its own."""
    mocker.patch.object(probe, '_record', side_effect=KeyError)
    drive_load(probe, spec=spec_named(PACKAGE))
    drive_load(probe, spec=spec_named(PACKAGE), execute=lambda: sys.modules.pop(PACKAGE))
    mocker.stopall()

    assert probe.faults == 10


def test_driven_by_hand_a_load_whose_code_raised_ends_before_its_pop(probe):
    """A store and an end, nothing between."""
    spec = spec_named(PACKAGE)
    for line in (probe._points.stored_line, probe._points.ended_line):
        drive(probe, spec=spec, module=None, callback='on_line', arguments=(line,))

    assert [load.name for load in probe.ended_before_pop] == [PACKAGE]


def test_a_load_whose_pop_calls_reading_failed_is_not_said_to_have_ended_early(
    probe, module, mocker
):
    """A fault at the pop's call: the load reached its pop, and is not claimed otherwise."""
    record = probe._record

    def fail_at_the_call(point, frame, modules):
        if point == POP_CALLED:
            raise ValueError
        return record(point, frame, modules)

    mocker.patch.object(probe, '_record', side_effect=fail_at_the_call)
    error = failed_import(module(DELETE_ITSELF))
    mocker.stopall()

    assert list(probe.ended_before_pop) == []
    assert probe.faults == 1
    assert verdict_line(report_of(probe, error)).endswith('was not read')


def test_driven_by_hand_events_of_no_load_are_dropped(probe):
    """A pop, its outcome and an end with no store seen."""
    for callback in ('on_call', 'on_c_return', 'on_c_raise'):
        drive(
            probe,
            spec=spec_named(PACKAGE),
            module=None,
            callback=callback,
            arguments=(probe._points.pop_call_offset, dict.pop, sys.modules),
        )

    assert events_of(probe, PACKAGE) == []
    assert probe.faults == 0


def not_recorded(probe: LoadProbe) -> str:
    """Install a probe that cannot record, and return its report."""
    callbacks = list(gc.callbacks)
    probe.install()
    assert probe.tool_id is None
    assert gc.callbacks == callbacks
    report = report_of(probe, KeyError(PACKAGE))
    probe.uninstall()
    assert 'VERDICT' not in report
    return report


def test_an_unrecognised_shape_is_reported_not_recorded():
    """Nothing is installed, and the report says why."""
    report = not_recorded(LoadProbe(code=compiled('def f(spec):\n    return spec\n')))

    assert "not recorded: _load_unlocked's shape is not recognised (calls of sys" in report


def test_no_python_load_unlocked_is_reported_not_recorded(mocker):
    """An importlib without the function."""
    mocker.patch.object(import_load_probe.importlib, '_bootstrap', types.SimpleNamespace())
    code = load_code()
    mocker.stopall()

    assert code is None
    assert 'not recorded: importlib has no Python' in not_recorded(LoadProbe(code=code))


def test_no_free_tool_id_is_reported_not_recorded():
    """Every id tried is another tool's, and stays theirs."""
    taken = [tool_id for tool_id in TOOL_IDS if sys.monitoring.get_tool(tool_id) is None]
    for tool_id in taken:
        sys.monitoring.use_tool_id(tool_id, 'another tool')
    try:
        report = not_recorded(LoadProbe(code=load_code()))
        owners = [sys.monitoring.get_tool(tool_id) for tool_id in taken]
    finally:
        for tool_id in taken:
            sys.monitoring.free_tool_id(tool_id)

    assert 'not recorded: no sys.monitoring tool id was free' in report
    assert owners == ['another tool'] * len(taken)


def test_a_probe_never_installed_says_so():
    """Its report claims nothing."""
    report = report_of(LoadProbe(code=load_code()), KeyError(PACKAGE))

    assert 'not recorded: the probe was not installed' in report


def test_the_named_tools_ids_are_never_tried():
    """Coverage's, the debugger's, the profiler's and the optimizer's."""
    named = {
        sys.monitoring.DEBUGGER_ID,
        sys.monitoring.COVERAGE_ID,
        sys.monitoring.PROFILER_ID,
        sys.monitoring.OPTIMIZER_ID,
    }

    assert named.isdisjoint(TOOL_IDS)


def monitoring_state() -> tuple:
    """Every tool, its events on the load's code, its global events, and the collector's hooks."""
    code = load_code()
    return (
        [
            (tool, sys.monitoring.get_tool(tool), sys.monitoring.get_events(tool),
             sys.monitoring.get_local_events(tool, code))
            for tool in range(6)
            if sys.monitoring.get_tool(tool) is not None
        ],
        list(gc.callbacks),
    )  # fmt: skip


def test_installing_changes_only_the_probes_own_tool_and_uninstalling_restores():
    """Coverage's tool, events and everyone else's are the same throughout."""
    before = monitoring_state()
    original = importlib._bootstrap._load_unlocked
    own = LoadProbe(code=load_code())
    own.install()
    during_tools, _ = monitoring_state()
    tool_id = own.tool_id
    own.uninstall()

    assert [tool for tool in during_tools if tool[0] != tool_id] == before[0]
    assert monitoring_state() == before
    assert sys.monitoring.get_tool(tool_id) is None
    assert importlib._bootstrap._load_unlocked is original
    sys.monitoring.use_tool_id(tool_id, 'another tool')
    try:
        for event in own._callbacks():
            assert sys.monitoring.register_callback(tool_id, event, None) is None
    finally:
        sys.monitoring.free_tool_id(tool_id)
    assert own.not_recorded == 'the probe was uninstalled'
    own.uninstall()
    assert monitoring_state() == before


def test_no_code_but_the_loads_has_events(probe):
    """The tool has no global event: nothing else in the process runs slower."""
    assert sys.monitoring.get_events(probe.tool_id) == 0


@pytest.mark.parametrize('fault', [*FAULTS, RecursionError, UnicodeError])
def test_a_fault_in_every_callback_is_counted_and_the_import_goes_on(probe, module, mocker, fault):
    """Reading is broken at every point: the import succeeds, a pop's own KeyError is the same."""
    mocker.patch.object(probe, '_record', side_effect=fault)
    importlib.import_module(module(''))
    succeeded = probe.faults
    error = failed_import(module(DELETE_ITSELF, name=f'{PACKAGE}_gone'))
    failed = probe.faults - succeeded
    mocker.stopall()

    # Three lines, the pop's call and its outcome, each
    assert (succeeded, failed) == (5, 5)
    assert error.args == (f'{PACKAGE}_gone',)
    assert 'Faults in the recording: 10' in report_of(probe, error)


def test_a_fault_reading_a_collection_is_counted(probe, mocker):
    """The collection goes on, and nothing is printed as unraisable."""
    mocker.patch.object(probe, '_begin_collection', side_effect=ValueError)
    faults = probe.faults
    gc.collect(0)
    mocker.stopall()

    assert probe.faults == faults + 1


def test_a_signal_handlers_exception_is_not_the_probes_to_swallow(probe, mocker):
    """Ctrl-C, and a test's own alarm, go on as they would from any code."""
    for raised in (KeyboardInterrupt, TimeoutError):
        mocker.patch.object(probe, '_record', side_effect=raised)
        with pytest.raises(raised):
            probe.on_line(load_code(), probe._points.pop_line)
        mocker.stopall()

    assert probe.faults == 0


@pytest.mark.parametrize('callback', ['on_c_return', 'on_c_raise'])
def test_another_calls_outcome_is_no_event(probe, callback):
    """Only the pop's."""
    events = probe.events()
    getattr(probe, callback)(load_code(), -1, len, sys.modules)

    assert probe.events() == events
    assert probe.faults == 0


def test_lines_and_calls_of_no_interest_are_switched_off(probe):
    """Each costs one callback, then nothing."""
    assert probe.on_line(load_code(), -1) is sys.monitoring.DISABLE
    assert probe.on_call(load_code(), -1, len, None) is sys.monitoring.DISABLE


def test_nothing_is_called_after_the_dictionary_is_read():
    """No point for a thread switch or a collection between the reading and the pop."""
    instructions = list(dis.get_instructions(LoadProbe._record))
    marker = max(
        index
        for index, instruction in enumerate(instructions)
        if instruction.opname == 'LOAD_GLOBAL' and instruction.argval == 'type'
    )
    assert instructions[marker].offset < min(
        one.offset
        for one in instructions
        if one.opname == 'CONTAINS_OP'
        and one.offset > 0
        and one.offset > instructions[marker].offset
    )
    after_preparing = [
        instruction.opname
        for instruction in instructions[marker:]
        if instruction.opname.startswith(('CALL', 'JUMP_BACKWARD', 'RESUME', 'SEND', 'YIELD'))
    ]
    # type(modules) itself, then nothing (the tuple is made by an intrinsic, not a call)
    assert [name for name in after_preparing if not name.startswith('CALL_INTRINSIC')] == ['CALL']


def test_the_pops_callback_calls_nothing_after_recording():
    """Between the reading and the pop, the callback only returns."""
    instructions = list(dis.get_instructions(LoadProbe.on_call))
    calls = [one for one in instructions if one.opname.startswith('CALL')]
    assert calls[-1].offset > next(one.offset for one in instructions if one.argval == '_record')
    recorded = instructions.index(calls[-1])

    following = [one.opname for one in instructions[recorded + 1 :]]
    until_return = following[: following.index('RETURN_VALUE')]
    assert set(until_return) <= {'POP_TOP', 'NOP', 'LOAD_COMMON_CONSTANT', 'LOAD_CONST'}


def test_the_interpreter_is_described_without_a_home_folder():
    """Version, executable and build, as far as this build tells."""
    report = interpreter_report()

    assert sys.version in report
    assert str(Path.home()) not in report
    for part in ('sys.executable: ', 'Py_GIL_DISABLED', 'the GIL: ', 'the JIT: ', 'configured'):
        assert part in report


def test_a_build_that_tells_nothing_is_described(mocker):
    """No settings (Windows), no JIT module."""
    mocker.patch.object(import_load_probe.sysconfig, 'get_config_var', return_value=None)
    mocker.patch.object(import_load_probe.sys, '_jit', None)
    mocker.patch.object(import_load_probe.sys, '_is_gil_enabled', return_value=False)
    report = interpreter_report()
    mocker.stopall()

    assert 'configured with: not given by this build' in report
    assert 'the GIL: off; the JIT: unknown' in report


def test_configure_arguments_with_paths_are_left_out(mocker):
    """Only the features."""
    mocker.patch.object(
        import_load_probe.sysconfig,
        'get_config_var',
        return_value=(
            "'--with-lto=full' '--prefix=/home/name' '--with-x=/home/name' '--enable-a=name\\c'"
        ),
    )
    report = interpreter_report()
    mocker.stopall()

    assert 'configured with: --with-lto=full' in report
    assert 'name' not in report.partition('configured')[2]
