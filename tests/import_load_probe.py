"""Record where a module's ``sys.modules`` entry was while importlib loaded it (triage evidence).

Triage tool for bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md, part of the recorder
(tests/module_removals.py installs it, tests/import_failure_threads.py reports it). An import fails
with ``KeyError`` at ``module = sys.modules.pop(spec.name)`` in importlib's ``_load_unlocked``. This
places the loss of the entry: before the first line after the store, while the module's code ran,
between that and the pop, or not at all (the entry there as the pop was called, which nothing in
Python explains). It is evidence for the next failure, not a fix, and it names no culprit.

How: ``sys.monitoring`` events set on ``_load_unlocked``'s code object alone, under a tool id that
was free when the recording began (never coverage's, the profiler's, the debugger's or the
optimizer's). ``find_load_points`` finds the lines and the pop's call in the code object's
instructions, so a patch release that moves them changes nothing; a shape it does not recognise,
or no free tool id, is reported as not recorded. A ``gc.callbacks`` entry records each collection.

What a callback may do: read, and write into the fixed-size rings here. It replaces nothing in
importlib or ``sys.modules`` and sets no dictionary watcher (tests/module_removals.py: why not).
The errors its own reading can raise (``FAULTS``) are counted, never raised; anything else (a signal
handler's exception, Ctrl-C) is not the probe's, and goes on, as it would from any Python code run
there. After a callback has read the dictionary it makes no call, so CPython's eval loop has no
point in it to switch threads or collect garbage before the pop. That is read from the bytecode (a
test checks it), not proven of the interpreter.

Caveat: an instrumented function does not run as the plain one does. Its calls take CPython's
instrumented path in place of the specialised one (and no JIT trace of it is used), and the
callbacks add points where threads switch and garbage is collected. If the failure is a fault of the
interpreter's on the plain path, or needs exact timing, the probe may hide it: failures stopping
once it is in is NOT evidence that anything was fixed.

Tests: tests/test_import_load_probe.py.
"""

from __future__ import annotations

import _thread
import collections
import dis
import gc
import importlib._bootstrap
import itertools
import platform
import sys
import sysconfig
import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from types import CodeType, FrameType, TracebackType

# What an unrecognised shape is reported as
STORES_UNRECOGNISED = 'not one store into sys.modules before the pop and one after'
EXECUTION_UNRECOGNISED = "the module's execution is not between the store and the pop"
LINES_UNRECOGNISED = 'the lines of the store, the pop and the end are not distinct'

# How much is kept: events, collections, failed pops, loads that never reached the pop, the names
# one outermost import finished loading, and the frames of each other thread at a failed pop
EVENTS_KEPT = 400
COLLECTIONS_KEPT = 100
FAILURES_KEPT = 8
LOADED_NAMES_KEPT = 500
FRAMES_KEPT = 4

# How many lines of the rings one report shows
LINES_REPORTED = 60

# The ids sys.monitoring names for nobody (0 to 2 and 5 are the debugger's, coverage's, the
# profiler's and the optimizer's)
TOOL_IDS = (4, 3)
TOOL_NAME = 'glitchygames import load probe'

# What a callback's reading can raise; nothing else in one is the probe's own fault
FAULTS = (AttributeError, LookupError, TypeError, ValueError, RuntimeError, MemoryError)

# The points of a load, in the order they come
STORED = 'after the store'
POP_LINE = "at the pop's line"
POP_CALLED = "at the pop's call"
POP_RETURNED = 'the pop returned'
POP_RAISED = 'the pop raised'
ENDED = 'the load ended'

# Those a failed pop's report shows, in order
POINTS_TO_THE_RAISE = (STORED, POP_LINE, POP_CALLED, POP_RAISED)

# What a reading found under the module's name
PRESENT = 'present'
ANOTHER_OBJECT = 'present, but another object'
ABSENT = 'ABSENT'
NOT_READ = 'not read (the name is not a str, or the dictionary not a dict)'

# Said in every report
EVIDENCE_NOT_A_FIX = (
    'Evidence, not a fix and no culprit. Instrumenting _load_unlocked takes it off the '
    "interpreter's specialised path and adds points where threads switch and garbage is collected, "
    'so the probe may hide an interpreter fault: no more failures would prove nothing fixed.'
)

# How to read the verdict: hints, each with what it leaves open
HOW_TO_READ = (
    'How to read this (hints, not proof):',
    '- gone while the code ran: removed by the module, by what it called, by a finalizer or by',
    '  another thread. The narrowing lines say between which events; a collection that saw the',
    '  entry go suggests a finalizer (another thread can run inside one), and no collection listed',
    '  rules out only the garbage collector (a reference count reaching 0 runs finalizers too)',
    "- another thread alive at the pop may have done it, and so may the module's own code: nothing",
    '  here tells those two apart unless the recorded removals section names the call; thread',
    '  counts that differ mean one started or ended meanwhile',
    '- present at the pop call, and the pop raised: perhaps an interpreter or dictionary fault.',
    '  Left open: a removal between the reading and the pop, which no Python code should be able',
    '  to make on this thread (another thread without the GIL, or C code, could)',
    '- absent straight after the store: perhaps the store was lost, or a removal in that short gap',
    '- modules loaded earlier in the same outermost import missing: perhaps a whole-dictionary',
    '  restore (some modules remove or replace themselves on purpose)',
)


class LoadPoints(NamedTuple):
    """Where the events of interest are in ``_load_unlocked``'s code."""

    stored_line: int
    pop_line: int
    pop_call_offset: int
    ended_line: int


class UnrecognisedShapeError(Exception):
    """The code is not the ``_load_unlocked`` this probe knows how to read."""

    def __init__(self, what: str, *, found: int | None = None) -> None:
        """Say what was looked for, and how many there were where there should be one."""
        super().__init__(what if found is None else f'{what}: expected one, found {found}')


def only[T](found: Iterable[T], *, what: str) -> T:
    """Return the one item found.

    Raises:
        UnrecognisedShapeError: There is none, or more than one.

    """
    items = tuple(found)
    if len(items) != 1:
        raise UnrecognisedShapeError(what, found=len(items))
    return items[0]


def is_modules_call(instructions: list[dis.Instruction], index: int) -> bool:
    """Tell whether ``sys.modules.pop(spec.name)`` begins at an instruction.

    Returns:
        True when the six instructions there are that call's.

    """
    expected = (
        ('LOAD_GLOBAL', 'sys'),
        ('LOAD_ATTR', 'modules'),
        ('LOAD_ATTR', 'pop'),
        ('LOAD_FAST', 'spec'),
        ('LOAD_ATTR', 'name'),
        ('CALL', 1),
    )
    window = instructions[index : index + len(expected)]
    return len(window) == len(expected) and all(
        instruction.opname.startswith(opname) and instruction.argval == argval
        for instruction, (opname, argval) in zip(window, expected, strict=True)
    )


def line_of(instruction: dis.Instruction) -> int:
    """Return an instruction's line.

    Raises:
        UnrecognisedShapeError: It has none.

    """
    if instruction.line_number is None:
        raise UnrecognisedShapeError(LINES_UNRECOGNISED)
    return instruction.line_number


def first_line_after(
    store: dis.Instruction, *, line_starts: list[dis.Instruction]
) -> dis.Instruction:
    """Find the first line after the store that does something.

    A bare ``try:`` is a NOP, outside the block that cleans up after a failed execution.

    Returns:
        The instruction the line starts with.

    Raises:
        UnrecognisedShapeError: No line starts after the store.

    """
    for instruction in line_starts:
        if instruction.offset > store.offset and instruction.opname != 'NOP':
            return instruction
    raise UnrecognisedShapeError(LINES_UNRECOGNISED)


def find_load_points(code: CodeType) -> LoadPoints:
    """Find the events' places in ``_load_unlocked``'s code, whatever its line numbers.

    Args:
        code: The function's code object.

    Returns:
        The lines and the offset to watch.

    Raises:
        UnrecognisedShapeError: The code is not one store of ``sys.modules[spec.name]``, the
            module's execution, one ``sys.modules.pop(spec.name)`` with a line to itself, a second
            store, and one line clearing ``_initializing``, in that order.

    """
    instructions = list(dis.get_instructions(code))
    pop_start = only(
        (index for index in range(len(instructions)) if is_modules_call(instructions, index)),
        what='calls of sys.modules.pop(spec.name)',
    )
    pop_call = instructions[pop_start + 5]
    stores = [
        index
        for index, instruction in enumerate(instructions)
        if instruction.opname == 'STORE_SUBSCR'
    ]
    if len(stores) != 2 or not stores[0] < pop_start < stores[1]:
        raise UnrecognisedShapeError(STORES_UNRECOGNISED)
    execution = only(
        (
            index
            for index, instruction in enumerate(instructions)
            if instruction.argval == 'exec_module'
        ),
        what='uses of exec_module',
    )
    if not stores[0] < execution < pop_start:
        raise UnrecognisedShapeError(EXECUTION_UNRECOGNISED)

    line_starts = [instruction for instruction in instructions if instruction.starts_line]
    stored = first_line_after(instructions[stores[0]], line_starts=line_starts)
    clearing = {
        line_of(instruction)
        for instruction in instructions
        if instruction.opname == 'STORE_ATTR'
        and instruction.argval == '_initializing'
        and instruction.offset > pop_call.offset
    }
    ended_line = only(clearing, what='lines clearing _initializing')
    stored_line, pop_line = line_of(stored), line_of(pop_call)
    started = collections.Counter(instruction.line_number for instruction in line_starts)
    each_once = started[stored_line] == started[pop_line] == 1
    distinct = len({stored_line, pop_line, ended_line}) == 3
    in_place = (
        instructions[pop_start].starts_line and stored.offset < instructions[execution].offset
    )
    if not (each_once and distinct and in_place):
        raise UnrecognisedShapeError(LINES_UNRECOGNISED)
    return LoadPoints(
        stored_line=stored_line,
        pop_line=pop_line,
        pop_call_offset=pop_call.offset,
        ended_line=ended_line,
    )


def load_code() -> CodeType | None:
    """Find ``_load_unlocked``'s code object.

    Returns:
        It, or None when importlib has no such Python function.

    """
    return getattr(getattr(importlib._bootstrap, '_load_unlocked', None), '__code__', None)


def shown_name(key: object) -> str:
    """Return a module's name for the report, running no code of the name's own.

    Returns:
        The name, or its type when it is not exactly a ``str``.

    """
    return key if type(key) is str else f'<a {type(key).__name__}, not a str>'


def spec_name(spec: object) -> object:
    """Read a spec's name from its own ``__dict__``, where ModuleSpec keeps it, running no code.

    Returns:
        The name.

    """
    return object.__getattribute__(spec, '__dict__')['name']


def is_same_name(name: object, key: str) -> bool:
    """Compare a name with the one stored under, running no code of the name's own.

    Returns:
        True when it is exactly a ``str`` and equal.

    """
    return type(name) is str and name == key


class Reading(NamedTuple):
    """One event: what was under the module's name, and how big the dictionary was.

    The rings hold these as plain tuples (making a NamedTuple is a call, which a callback must not
    do after its reading); the report makes them ``Reading`` again.
    """

    order: int
    point: str
    thread_ident: int
    load_number: int
    name: str
    entries: int
    dictionary_is_sys_modules: bool
    threads: int
    found: str


type ReadingFields = tuple[int, str, int, int, str, int, bool, int, str]


class Collection(NamedTuple):
    """One garbage collection, and the entry of the module being loaded before and after it.

    The module is the collecting thread's innermost, or another thread's when it is loading none.
    """

    order: int
    ended_order: int
    generation: int
    collected: int
    thread_ident: int
    name: str | None
    loading_thread_ident: int | None
    before: str
    after: str


class Episode:
    """One thread's outermost import: the modules that finished loading during it."""

    __slots__ = ('loaded', 'loaded_count', 'outermost')

    def __init__(self, outermost: str) -> None:
        """Start with nothing loaded."""
        self.outermost = outermost
        self.loaded: collections.deque[str] = collections.deque(maxlen=LOADED_NAMES_KEPT)
        self.loaded_count = 0


class Load:
    """One module being loaded: made at every import, so slots, and no reference to the module."""

    __slots__ = (
        'absent_at',
        'enclosing',
        'episode',
        'key',
        'name',
        'nesting',
        'number',
        'present_at',
        'readings',
        'renamed',
        'spec_id',
        'thread_ident',
    )

    def __init__(
        self, *, key: object, spec_id: int, number: int, thread_ident: int, enclosing: list[Load]
    ) -> None:
        """Start a load, nested in those its thread has in progress."""
        # Exactly str: looking up anything else would run its own hash and comparison
        self.key = key if type(key) is str else None
        self.name = shown_name(key)
        self.spec_id = spec_id
        self.number = number
        self.thread_ident = thread_ident
        # No cycle: an enclosing load never points at those inside it
        self.enclosing = enclosing[-1] if enclosing else None
        self.nesting = [load.name for load in enclosing]
        self.episode = enclosing[0].episode if enclosing else Episode(self.name)
        self.readings: dict[str, ReadingFields] = {}
        # The spec's name is no longer the one stored under: the readings are of another entry
        self.renamed = False
        # Seen from the events of the loads inside this one
        self.present_at: ReadingFields | None = None
        self.absent_at: ReadingFields | None = None


class FailedPop(NamedTuple):
    """A pop that raised, with what was read as it did (before the exception unwound anything)."""

    load: Load
    found_by_iteration: bool
    missing: tuple[str, ...]
    other_threads: tuple[tuple[int, tuple[str, ...]], ...]


def other_thread_stacks(this_thread: int) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Describe what every other thread runs now, innermost frames first, reading no source.

    Returns:
        Each thread's ident and at most ``FRAMES_KEPT`` lines.

    """
    described: list[tuple[int, tuple[str, ...]]] = []
    innermost: FrameType | None = None
    frame: FrameType | None = None
    try:
        for ident, innermost in sys._current_frames().items():
            if ident == this_thread:
                continue
            lines: list[str] = []
            frame = innermost
            while frame is not None and len(lines) < FRAMES_KEPT:
                lines.append(f'{frame.f_code.co_filename}:{frame.f_lineno} {frame.f_code.co_name}')
                frame = frame.f_back
            described.append((ident, tuple(lines)))
    finally:
        # One of these is this function's own frame: kept in its own locals it would be a cycle
        innermost = frame = None
    return tuple(described)


def failed_pop(load: Load) -> FailedPop:
    """Read what a pop's exception will change as it unwinds.

    Returns:
        The failed pop.

    """
    by_iteration = load.key is not None and any(
        is_same_name(name, load.key) for name in tuple(sys.modules)
    )
    return FailedPop(
        load=load,
        found_by_iteration=by_iteration,
        missing=tuple(name for name in load.episode.loaded if name not in sys.modules),
        other_threads=other_thread_stacks(load.thread_ident),
    )


class LoadProbe:
    """The events of every module load in this process, in rings, and the callbacks that feed them.

    Args:
        code: ``_load_unlocked``'s code object (None: there is none to watch).
        tool_ids: The ``sys.monitoring`` tool ids to try, in order.

    """

    def __init__(self, *, code: CodeType | None, tool_ids: tuple[int, ...] = TOOL_IDS) -> None:
        """Start with nothing recorded and nothing watched."""
        self.code = code
        self.tool_ids = tool_ids
        self.tool_id: int | None = None
        self.not_recorded: str | None = 'the probe was not installed'
        self.faults = 0
        self.newest_order = 0
        self._points = LoadPoints(-1, -1, -1, -1)
        self._orders = itertools.count(1)
        self._load_numbers = itertools.count(1)
        self._line_points: dict[int, str] = {}
        # Each thread's loads in progress, outermost first; an idle thread has no entry
        self._stacks: dict[int, list[Load]] = {}
        # Rings: each slot's write is one bytecode, so no lock is needed (a finalizer importing
        # on a thread that held one would deadlock)
        self._events: list[ReadingFields | None] = [None] * EVENTS_KEPT
        self._collections: list[Collection | None] = [None] * COLLECTIONS_KEPT
        self._collection_numbers = itertools.count()
        self._collecting: tuple[int, int, Load | None, str] | None = None
        self.failed_pops: collections.deque[FailedPop] = collections.deque(maxlen=FAILURES_KEPT)
        self.ended_before_pop: collections.deque[Load] = collections.deque(maxlen=FAILURES_KEPT)

    def install(self) -> None:
        """Set the events on the code, under a free tool id; otherwise say why not."""
        if self.code is None:
            self.not_recorded = 'importlib has no Python _load_unlocked'
            return
        try:
            self._points = find_load_points(self.code)
        except UnrecognisedShapeError as error:
            self.not_recorded = f"_load_unlocked's shape is not recognised ({error})"
            return
        self._line_points = {
            self._points.stored_line: STORED,
            self._points.pop_line: POP_LINE,
            self._points.ended_line: ENDED,
        }
        self.tool_id = self._claim_tool_id()
        if self.tool_id is None:
            self.not_recorded = 'no sys.monitoring tool id was free'
            return
        for event, callback in self._callbacks().items():
            sys.monitoring.register_callback(self.tool_id, event, callback)
        # Local to this one code object: no other code runs any slower. CALL brings the pop's
        # C_RETURN and C_RAISE with it
        events = sys.monitoring.events
        sys.monitoring.set_local_events(self.tool_id, self.code, events.LINE | events.CALL)
        gc.callbacks.append(self.on_collection)
        self.not_recorded = None

    def uninstall(self) -> None:
        """Take the events and the callbacks away, and free the tool id (no-op if not installed)."""
        if self.tool_id is None or self.code is None:
            return
        self.not_recorded = 'the probe was uninstalled'
        gc.callbacks.remove(self.on_collection)
        sys.monitoring.set_local_events(self.tool_id, self.code, 0)
        for event in self._callbacks():
            sys.monitoring.register_callback(self.tool_id, event, None)
        sys.monitoring.free_tool_id(self.tool_id)
        self.tool_id = None

    def _callbacks(self) -> Mapping[int, Any]:
        """List the callback for each event.

        Returns:
            The callbacks by event.

        """
        events = sys.monitoring.events
        return {
            events.LINE: self.on_line,
            events.CALL: self.on_call,
            events.C_RETURN: self.on_c_return,
            events.C_RAISE: self.on_c_raise,
        }

    def _claim_tool_id(self) -> int | None:
        """Take the first free tool id.

        Returns:
            The id, or None when every one tried is in use.

        """
        for tool_id in self.tool_ids:
            if sys.monitoring.get_tool(tool_id) is None:
                sys.monitoring.use_tool_id(tool_id, TOOL_NAME)
                return tool_id
        return None

    def on_line(self, code: CodeType, line: int) -> object:
        """Read at a line of interest; switch the event off at any other.

        Returns:
            ``sys.monitoring.DISABLE`` for a line of no interest, else None.

        """
        del code
        point = self._line_points.get(line)
        if point is None:
            return sys.monitoring.DISABLE
        try:
            self._record(point, sys._getframe(1), sys.modules)
        except FAULTS:
            self.faults += 1
        return None

    def on_call(self, code: CodeType, offset: int, function: object, dictionary: object) -> object:
        """Read as the pop is called; switch the event off at any other call.

        Returns:
            ``sys.monitoring.DISABLE`` for another call, else None.

        """
        del code, function
        if offset != self._points.pop_call_offset:
            return sys.monitoring.DISABLE
        try:
            self._record(POP_CALLED, sys._getframe(1), dictionary)
        except FAULTS:
            self.faults += 1
        return None

    def on_c_return(
        self, code: CodeType, offset: int, function: object, dictionary: object
    ) -> None:
        """Read as the pop returns."""
        del code, function
        if offset != self._points.pop_call_offset:
            return
        try:
            self._record(POP_RETURNED, sys._getframe(1), dictionary)
        except FAULTS:
            self.faults += 1

    def on_c_raise(self, code: CodeType, offset: int, function: object, dictionary: object) -> None:
        """Read as the pop raises, and keep what the unwinding will change."""
        del code, function
        if offset != self._points.pop_call_offset:
            return
        try:
            load = self._record(POP_RAISED, sys._getframe(1), dictionary)
            if load is not None:
                self.failed_pops.append(failed_pop(load))
        except FAULTS:
            self.faults += 1

    def _record(self, point: str, frame: FrameType, modules: Any) -> Load | None:
        """Read what is under the loading module's name, and keep it.

        Nothing after the line marked below is a call, so nothing can run between the
        reading and this function's return.

        Args:
            point: Which of the load's points this is.
            frame: ``_load_unlocked``'s frame.
            modules: The dictionary: the pop's own at the pop, else ``sys.modules``.

        Returns:
            The load, or None for one that began before the probe was installed.

        """
        variables = frame.f_locals
        module = variables['module']
        load, before_reading = self._prepare(point=point, spec=variables['spec'], modules=modules)
        if load is None:
            return None
        enclosing = load.enclosing if point in {STORED, ENDED} else None
        key, readable = load.key, type(modules) is dict
        # The reading: from here to the return, no call
        found = NOT_READ
        if readable and key is not None:
            if key in modules:
                found = PRESENT if modules[key] is module else ANOTHER_OBJECT
            else:
                found = ABSENT
        reading = (*before_reading, found)
        load.readings[point] = reading
        self._events[reading[0] % EVENTS_KEPT] = reading
        self.newest_order = reading[0]
        if enclosing is not None and readable and enclosing.key is not None:
            if enclosing.key in modules:
                enclosing.present_at = reading
            elif enclosing.absent_at is None:
                enclosing.absent_at = reading
        return load

    def _prepare(
        self, *, point: str, spec: object, modules: Any
    ) -> tuple[Load | None, tuple[int, str, int, int, str, int, bool, int]]:
        """Do everything a reading needs that makes calls.

        Returns:
            The load (None for one that began before the probe was installed), and the reading's
            fields but the last.

        """
        ident = threading.get_ident()
        order = next(self._orders)
        if point == STORED:
            load = self._begin(spec=spec, ident=ident)
        else:
            load = self._in_progress(spec_id=id(spec), ident=ident)
        if load is None:
            return None, (order, point, ident, 0, '', 0, False, 0)
        if load.key is not None and not is_same_name(spec_name(spec), load.key):
            load.renamed = True
        if point == POP_RETURNED:
            load.episode.loaded.append(load.name)
            load.episode.loaded_count += 1
        if point == ENDED:
            self._end(load)
        same = modules is sys.modules
        fields = (order, point, ident, load.number, load.name, len(modules), same, _thread._count())
        return load, fields

    def _begin(self, *, spec: object, ident: int) -> Load:
        """Put a new load on its thread's stack.

        Returns:
            The load.

        """
        stack = self._stacks.get(ident)
        if stack is None:
            stack = self._stacks[ident] = []
        load = Load(
            key=spec_name(spec),
            spec_id=id(spec),
            number=next(self._load_numbers),
            thread_ident=ident,
            enclosing=stack,
        )
        stack.append(load)
        return load

    def _in_progress(self, *, spec_id: int, ident: int) -> Load | None:
        """Find this thread's load of a spec, dropping any inside it whose end was not seen.

        Returns:
            The load, or None when it is not on the stack.

        """
        stack = self._stacks.get(ident, ())
        while stack:
            if stack[-1].spec_id == spec_id:
                return stack[-1]
            stack.pop()
        self._stacks.pop(ident, None)
        return None

    def _end(self, load: Load) -> None:
        """Take a load off its thread's stack, keeping one whose pop was not seen."""
        stack = self._stacks[load.thread_ident]
        stack.pop()
        if not stack:
            del self._stacks[load.thread_ident]
        if load.readings.keys().isdisjoint({POP_LINE, POP_CALLED, POP_RETURNED, POP_RAISED}):
            self.ended_before_pop.append(load)

    def _innermost(self, ident: int) -> Load | None:
        """Find the load a collection on a thread is inside, else another thread's newest.

        Returns:
            The load, or None when nothing is being loaded.

        """
        stack = self._stacks.get(ident)
        if stack:
            return stack[-1]
        innermost = [stack[-1] for stack in tuple(self._stacks.values()) if stack]
        return max(innermost, key=lambda load: load.number, default=None)

    def on_collection(self, phase: str, information: Mapping[str, int]) -> None:
        """Read the innermost loading module's entry as a collection starts and as it stops."""
        try:
            if phase == 'start':
                self._begin_collection()
            else:
                self._keep_collection(information)
        except FAULTS:
            self.faults += 1

    def _begin_collection(self) -> None:
        """Read the entry as a collection starts (CPython runs one collection at a time)."""
        ident = threading.get_ident()
        order = next(self._orders)
        load = self._innermost(ident)
        self._collecting = (order, ident, load, entry_of(load))

    def _keep_collection(self, information: Mapping[str, int]) -> None:
        """Keep a collection that ended (one that began before the probe is not kept)."""
        began, self._collecting = self._collecting, None
        if began is None:
            return
        ended_order = next(self._orders)
        order, ident, load, before = began
        self._collections[next(self._collection_numbers) % COLLECTIONS_KEPT] = Collection(
            order=order,
            ended_order=ended_order,
            generation=information['generation'],
            collected=information['collected'],
            thread_ident=ident,
            name=None if load is None else load.name,
            loading_thread_ident=None if load is None else load.thread_ident,
            before=before,
            after=entry_of(load),
        )

    def events(self) -> list[Reading]:
        """Return the events kept, oldest first."""
        return sorted(Reading._make(event) for event in tuple(self._events) if event is not None)

    def collections(self) -> list[Collection]:
        """Return the collections kept, oldest first."""
        return sorted(kept for kept in tuple(self._collections) if kept is not None)


def entry_of(load: Load | None) -> str:
    """Read whether a load's entry is in ``sys.modules``.

    Returns:
        ``PRESENT``, ``ABSENT`` or ``NOT_READ``.

    """
    modules = sys.modules
    if load is None or load.key is None or type(modules) is not dict:
        return NOT_READ
    return PRESENT if load.key in modules else ABSENT


def loads_in_traceback(
    *, code: CodeType | None, traceback_object: TracebackType | None
) -> list[tuple[int, str]]:
    """Find the loads a traceback passes through.

    Returns:
        Each one's spec, by id, and module name. Each spec is alive, held by its frame.

    """
    found: list[tuple[int, str]] = []
    for frame, _ in traceback.walk_tb(traceback_object):
        if frame.f_code is code:
            spec = frame.f_locals['spec']
            found.append((id(spec), shown_name(spec_name(spec))))
    return found


def thread_names() -> dict[int | None, str]:
    """Name each thread threading knows, registering none.

    Returns:
        The names by ident.

    """
    return {thread.ident: thread.name for thread in threading.enumerate()}


def reading_line(reading: ReadingFields, *, names: Mapping[int | None, str]) -> str:
    """Describe one event.

    Returns:
        Its line.

    """
    event = Reading._make(reading)
    dictionary = '' if event.dictionary_is_sys_modules else ', a dictionary that is NOT sys.modules'
    return (
        f'#{event.order} {event.name}, {event.point}: {event.found} (load {event.load_number}, '
        f'{names.get(event.thread_ident, f"ident {event.thread_ident}")}, {event.entries} entries'
        f'{dictionary}, {event.threads} started threads alive)'
    )


def collection_line(collection: Collection, *, names: Mapping[int | None, str]) -> str:
    """Describe one collection.

    Returns:
        Its line, marked when the entry went during it.

    """
    on = names.get(collection.thread_ident, f'ident {collection.thread_ident}')
    went = collection.before == PRESENT and collection.after == ABSENT
    mark = ' *** THE ENTRY WENT DURING THIS COLLECTION ***' if went else ''
    if collection.name is None:
        loading = 'nothing being loaded'
    else:
        whose = (
            'the same thread'
            if collection.loading_thread_ident == collection.thread_ident
            else 'another thread'
        )
        loading = (
            f'{collection.name} (loading on {whose}) {collection.before} before, '
            f'{collection.after} after'
        )
    return (
        f'#{collection.order}-{collection.ended_order} garbage collection of generation '
        f'{collection.generation} on {on}, {collection.collected} objects: {loading}{mark}'
    )


def verdict_of(load: Load) -> str:
    """Say where the entry of a load whose pop raised was lost, as far as the readings go.

    Returns:
        The verdict.

    """
    if load.renamed:
        return 'not recorded: the spec was renamed during the load'
    found = {
        point: Reading._make(load.readings[point]).found if point in load.readings else NOT_READ
        for point in (STORED, POP_LINE, POP_CALLED)
    }
    if NOT_READ in found.values():
        return 'not recorded: at least one point of this load was not read'
    if found[STORED] == ABSENT:
        return 'the entry was already absent at the first line after the store'
    if found[POP_LINE] == ABSENT:
        return "the entry left between the store and the pop's line: while exec_module ran it"
    if found[POP_CALLED] == ABSENT:
        return "the entry left between the start of the pop's line and the call of pop"
    return 'the entry was present when pop was called, and pop raised'


def failed_pop_report(
    *, failed: FailedPop, probe: LoadProbe, names: Mapping[int | None, str]
) -> list[str]:
    """Describe a failed pop: its points in order, what narrows it, and what else happened.

    Returns:
        The lines.

    """
    load = failed.load
    at_raise = Reading._make(load.readings[POP_RAISED])
    by_iteration = 'found' if failed.found_by_iteration else 'NOT found'
    lines = [
        f'VERDICT for {load.name}: {verdict_of(load)}',
        *(
            reading_line(load.readings[point], names=names)
            for point in POINTS_TO_THE_RAISE
            if point in load.readings
        ),
        f'as the pop raised: {at_raise.found} by hash, {by_iteration} by iteration',
        f'loading inside: {" > ".join(load.nesting) or "nothing (it is the outermost)"}',
    ]
    if load.present_at is not None:
        lines.append(f'last seen present from inside: {reading_line(load.present_at, names=names)}')
    if load.absent_at is not None:
        lines.append(f'first seen absent from inside: {reading_line(load.absent_at, names=names)}')
    episode = load.episode
    lines.append(
        f'since the outermost import ({episode.outermost}) began, {episode.loaded_count} modules '
        f'finished loading (the newest {len(episode.loaded)} kept); missing as the pop raised: '
        f'{", ".join(failed.missing) or "none"}; missing now: '
        f'{", ".join(name for name in episode.loaded if name not in sys.modules) or "none"}'
    )
    for ident, stack in failed.other_threads:
        lines.append(
            f'alive as the pop raised: {names.get(ident, f"ident {ident}")} in {"; ".join(stack)}'
        )
    if not failed.other_threads:
        lines.append('no other Python thread was alive as the pop raised')
    began = load.readings[STORED][0] if STORED in load.readings else 0
    entries = [
        *((event.order, reading_line(event, names=names)) for event in probe.events()),
        *(
            (collection.order, collection_line(collection, names=names))
            for collection in probe.collections()
        ),
    ]
    between = [line for order, line in sorted(entries) if began <= order <= at_raise.order]
    lines.append(
        f'events and collections from the store to the raise (the newest {LINES_REPORTED} of '
        f'{len(between)} kept):'
    )
    lines.extend(f'  {line}' for line in between[-LINES_REPORTED:])
    return lines


def load_probe_report(
    *, probe: LoadProbe, failed_name: str | None, traceback_object: TracebackType | None
) -> str:
    """Describe what the probe recorded of a failed import.

    Args:
        probe: The process's probe.
        failed_name: The module the error names, or None.
        traceback_object: The error's traceback.

    Returns:
        The section's text.

    """
    lines = [EVIDENCE_NOT_A_FIX]
    if probe.not_recorded is not None:
        return '\n'.join((*lines, f'not recorded: {probe.not_recorded}'))
    lines.append(f'Faults in the recording: {probe.faults}')
    names = thread_names()
    in_traceback = loads_in_traceback(code=probe.code, traceback_object=traceback_object)
    failed = next(
        (
            failed
            for failed in reversed(tuple(probe.failed_pops))
            if (failed.load.spec_id, failed.load.name) in in_traceback
        ),
        None,
    )
    if failed is not None:
        lines.extend(failed_pop_report(failed=failed, probe=probe, names=names))
        lines.extend(HOW_TO_READ)
        return '\n'.join(lines)
    lines.append('VERDICT: no failed pop was recorded for a load in this traceback')
    ended = next(
        (load for load in reversed(tuple(probe.ended_before_pop)) if load.name == failed_name), None
    )
    if ended is not None:
        lines.append(
            f'the newest load of {failed_name} ended with its pop not seen: perhaps its own code '
            'raised, or the import was interrupted (matched by name alone)'
        )
        lines.extend(reading_line(reading, names=names) for reading in ended.readings.values())
    return '\n'.join(lines)


def interpreter_report() -> str:
    """Describe the interpreter and how it was built, with no path but its own.

    Returns:
        The section's text.

    """
    # Only whole words about features: the other configure arguments are paths
    configured = [
        word
        for word in str(sysconfig.get_config_var('CONFIG_ARGS')).replace("'", '').split()
        if word.startswith(('--with', '--enable')) and not {'/', '\\'} & set(word)
    ]
    jit: Any = getattr(sys, '_jit', None)
    executable = sys.executable.replace(str(Path.home()), '~')
    variables = ', '.join(
        f'{name} {sysconfig.get_config_var(name)}'
        for name in ('Py_DEBUG', 'Py_GIL_DISABLED', 'Py_TAIL_CALL_INTERP')
    )
    build = f'build {platform.python_build()}, {platform.python_compiler()}'
    gil = 'on' if sys._is_gil_enabled() else 'off'
    jit_state = 'unknown' if jit is None else f'enabled: {jit.is_enabled()}'
    return '\n'.join((
        f'sys.version: {sys.version}',
        f'sys.executable: {executable}',
        f'platform: {sysconfig.get_platform()}, {build}',
        f'build settings (None: not given by this build): {variables}',
        f'the GIL: {gil}; the JIT: {jit_state}',
        f'configured with: {" ".join(configured) or "not given by this build"}',
    ))
