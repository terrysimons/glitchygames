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
there (at the load's end, that leaves the spec's ``_initializing`` True, which importlib alone would
not). After a callback has read the dictionary it makes no call, so CPython's eval loop has no point
in it to switch threads or collect garbage before the pop. That is read from the bytecode (a test
checks it), not proven of the interpreter.

Caveat: an instrumented function does not run as the plain one does. Its calls take CPython's
instrumented path in place of the specialised one (and no JIT trace of it is used), and the
callbacks add points where threads switch and garbage is collected. If the failure is a fault of the
interpreter's on the plain path, or needs exact timing, the probe may hide it: failures stopping
once it is in is NOT evidence that anything was fixed.

Tests: tests/test_import_load_probe.py.
"""

from __future__ import annotations

import collections
import contextlib
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
NO_FUNCTION = 'importlib has no Python _load_unlocked'
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

# Reported when the events cannot be matched with the error
NO_FAILED_POP = (
    'not recorded: no failed pop matches this traceback (the probe sees no load run inside one of '
    "its own or another tool's callbacks, and none begun before it was installed)"
)

# Those a failed pop's report shows, in order
POINTS_TO_THE_RAISE = (STORED, POP_LINE, POP_CALLED, POP_RAISED)

# What a reading found under the module's name (whatever object it is)
PRESENT = 'present'
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
    '  rules out only the collections still in the ring (a reference count runs finalizers too)',
    "- another thread alive at the pop may have done it, and so may the module's own code: nothing",
    '  here tells those two apart unless the recorded removals section names the call',
    '- what is read of another thread is approximate: the order of events on two threads, and a',
    "  collection's readings of a module loading on another thread, which goes on meanwhile",
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
    """Return the one item found; refuse none, or more than one.

    Raises:
        UnrecognisedShapeError: As refused.

    """
    items = tuple(found)
    if len(items) != 1:
        raise UnrecognisedShapeError(what, found=len(items))
    return items[0]


def is_modules_call(instructions: list[dis.Instruction], index: int) -> bool:
    """Tell whether the six instructions there are ``sys.modules.pop(spec.name)``'s."""
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
    """Return an instruction's line; refuse one without.

    Raises:
        UnrecognisedShapeError: As refused.

    """
    if instruction.line_number is None:
        raise UnrecognisedShapeError(LINES_UNRECOGNISED)
    return instruction.line_number


def first_line_after(
    store: dis.Instruction, *, line_starts: list[dis.Instruction]
) -> dis.Instruction:
    """Find the first line after the store that does something.

    A bare ``try:`` is a NOP, outside the block that cleans up after a failed execution.

    Raises:
        UnrecognisedShapeError: There is none.

    """
    for instruction in line_starts:
        if instruction.offset > store.offset and instruction.opname != 'NOP':
            return instruction
    raise UnrecognisedShapeError(LINES_UNRECOGNISED)


def find_load_points(code: CodeType | None) -> LoadPoints:
    """Find the events' places in ``_load_unlocked``'s code, whatever its line numbers.

    Raises:
        UnrecognisedShapeError: The code is not one store of ``sys.modules[spec.name]``, the
            module's execution, one ``sys.modules.pop(spec.name)`` with a line to itself, a second
            store, and one line clearing ``_initializing``, in that order.

    """
    if code is None:
        raise UnrecognisedShapeError(NO_FUNCTION)
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
    """Find ``_load_unlocked``'s code object (None: importlib has no such Python function)."""
    return getattr(getattr(importlib._bootstrap, '_load_unlocked', None), '__code__', None)


def key_of(spec: object) -> str | None:
    """Read a spec's name from its ``__dict__``, where ModuleSpec keeps it, running no code of its.

    None unless it is exactly a ``str``: looking up anything else runs its own hash and comparison.
    """
    name = object.__getattribute__(spec, '__dict__')['name']
    return name if type(name) is str else None


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
    dictionary_id: int
    found: str


type ReadingFields = tuple[int, str, int, int, str, int, int, str]


class Collection(NamedTuple):
    """One garbage collection, and the entry of the module being loaded before and after it.

    The module is the collecting thread's innermost, or another thread's when it is loading none:
    that thread may run between the readings, so they are approximate.
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
        'spec',
        'thread_ident',
    )

    def __init__(
        self, *, spec: object, number: int, thread_ident: int, enclosing: list[Load]
    ) -> None:
        """Start a load, nested in those its thread has in progress."""
        self.key = key_of(spec)
        self.name = '<a name that is not a str>' if self.key is None else self.key
        # Held, so that no later spec can have its id and be taken for it
        self.spec = spec
        self.number = number
        self.thread_ident = thread_ident
        # No cycle: an enclosing load never points at those inside it
        self.enclosing = enclosing[-1] if enclosing else None
        self.nesting = [load.name for load in enclosing]
        self.episode = enclosing[0].episode if enclosing else Episode(self.name)
        self.readings: dict[str, ReadingFields] = {}
        # The spec's name is no longer the one stored under
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
    """Describe what every other thread runs now, innermost frames first, reading no source."""
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
    """Read what a pop's exception will change as it unwinds."""
    return FailedPop(
        load=load,
        found_by_iteration=load.key in [name for name in tuple(sys.modules) if type(name) is str],
        missing=tuple(name for name in load.episode.loaded if name not in sys.modules),
        other_threads=other_thread_stacks(load.thread_ident),
    )


class InstallFault:
    """Turns whatever stops the installing into the reason nothing is recorded."""

    def __init__(self, probe: LoadProbe) -> None:
        """Say it of this probe."""
        self.probe = probe

    def __enter__(self) -> None:
        """Guard the installing: a triage tool stops no run."""

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback_object: TracebackType | None,
    ) -> bool:
        """Keep the reason; a ``KeyboardInterrupt`` or an exit goes on."""
        del error_type, traceback_object
        if not isinstance(error, Exception):
            return False
        # Never the error's own __str__, which may raise
        reason = ''.join(traceback.format_exception_only(error)).strip()
        self.probe.not_recorded = f'install failed: {reason}'
        return True


class LoadProbe:
    """The events of every module load in this process, in rings, and the callbacks that feed them.

    Args:
        code: ``_load_unlocked``'s code object (None: there is none to watch).

    """

    def __init__(self, *, code: CodeType | None) -> None:
        """Start with nothing recorded and nothing watched."""
        self.code = code
        self.tool_id: int | None = None
        # Its own, so that uninstalling never frees another tool's id
        self.tool_name = f'{TOOL_NAME} {id(self):#x}'
        self.not_recorded: str | None = 'the probe was not installed'
        self.faults = 0
        self.newest_order = 0
        self.points = LoadPoints(-1, -1, -1, -1)
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
        """Set the events on the code, under a free tool id; whatever stops that is the reason."""
        self.not_recorded = None
        with InstallFault(self):
            self.points = find_load_points(self.code)
            self._line_points = {
                self.points.stored_line: STORED,
                self.points.pop_line: POP_LINE,
                self.points.ended_line: ENDED,
            }
            self._watch()
        if self.not_recorded is not None:
            self.uninstall()

    def _watch(self) -> None:
        """Claim the first free tool id, and set the events and the collector's hook."""
        for tool_id in TOOL_IDS:
            if sys.monitoring.get_tool(tool_id) is None:
                sys.monitoring.use_tool_id(tool_id, self.tool_name)
                self.tool_id = tool_id
                break
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

    def uninstall(self) -> None:
        """Take the events and the callbacks away, each whatever became of the others."""
        if self.not_recorded is None:
            self.not_recorded = 'the probe was uninstalled'
        with contextlib.suppress(Exception):
            gc.callbacks.remove(self.on_collection)
        tool_id, self.tool_id = self.tool_id, None
        if tool_id is None or sys.monitoring.get_tool(tool_id) != self.tool_name:
            return
        with contextlib.suppress(Exception):
            # Freeing the id clears the callbacks, but leaves a code object's own events set
            sys.monitoring.set_local_events(tool_id, self.code, 0)
        with contextlib.suppress(Exception):
            sys.monitoring.free_tool_id(tool_id)

    def _callbacks(self) -> Mapping[int, Any]:
        """List the callback for each event."""
        events = sys.monitoring.events
        return {
            events.LINE: self.on_line,
            events.CALL: self.on_call,
            events.C_RETURN: self.on_c_return,
            events.C_RAISE: self.on_c_raise,
        }

    def on_line(self, code: CodeType, line: int) -> object:
        """Read at a line of interest; switch the event off at any other."""
        del code
        point = self._line_points.get(line)
        if point is None:
            return sys.monitoring.DISABLE
        try:
            self._record(point, sys._getframe(1), sys.modules)
        except FAULTS:
            self.faults += 1
        finally:
            # Whatever became of the reading
            if point == ENDED:
                self._end(sys._getframe(1))
        return None

    def on_call(self, code: CodeType, offset: int, function: object, dictionary: object) -> object:
        """Read as the pop is called; switch the event off at any other call."""
        del code, function
        if offset != self.points.pop_call_offset:
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
        if offset != self.points.pop_call_offset:
            return
        try:
            self._record(POP_RETURNED, sys._getframe(1), dictionary)
        except FAULTS:
            self.faults += 1

    def on_c_raise(self, code: CodeType, offset: int, function: object, dictionary: object) -> None:
        """Read as the pop raises, and keep what the unwinding will change."""
        del code, function
        if offset != self.points.pop_call_offset:
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

        ``modules`` is the dictionary: the pop's own at the pop, else ``sys.modules``. Returns None
        for a load that began before the probe was installed.
        """
        load, before_reading = self._prepare(point=point, frame=frame, modules=modules)
        if load is None:
            return None
        enclosing = load.enclosing if point in {STORED, ENDED} else None
        key, readable = load.key, type(modules) is dict
        # The reading: from here to the return, no call
        found = NOT_READ
        if readable and key is not None:
            found = PRESENT if key in modules else ABSENT
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
        self, *, point: str, frame: FrameType, modules: Any
    ) -> tuple[Load | None, tuple[int, str, int, int, str, int, int]]:
        """Do everything a reading needs that makes calls: the load, and all fields but the last."""
        spec = frame.f_locals['spec']
        ident = threading.get_ident()
        order = next(self._orders)
        if point == STORED:
            load = self._begin(spec=spec, ident=ident, frame=frame)
        else:
            load = self._in_progress(spec=spec, ident=ident)
        if load is None:
            return None, (order, point, ident, 0, '', 0, 0)
        if key_of(spec) != load.key:
            load.renamed = True
        if point == POP_RETURNED and load.key is not None:
            load.episode.loaded.append(load.key)
            load.episode.loaded_count += 1
        return load, (order, point, ident, load.number, load.name, len(modules), id(modules))

    def _begin(self, *, spec: object, ident: int, frame: FrameType) -> Load:
        """Put a new load on its thread's stack, dropping any there whose end was missed."""
        stack = self._stacks.get(ident, [])
        # Nothing to walk for an outermost import; else the nearest load's frame is a few up
        outer = frame.f_back if stack else None
        while outer is not None and outer.f_code is not self.code:
            outer = outer.f_back
        enclosing_spec = None if outer is None else outer.f_locals['spec']
        while stack and stack[-1].spec is not enclosing_spec:
            stack.pop()
        self._stacks[ident] = stack
        load = Load(spec=spec, number=next(self._load_numbers), thread_ident=ident, enclosing=stack)
        stack.append(load)
        return load

    def _in_progress(self, *, spec: object, ident: int) -> Load | None:
        """Find this thread's load of a spec, dropping any inside it whose end was missed."""
        stack = self._stacks.get(ident, [])
        while stack:
            if stack[-1].spec is spec:
                return stack[-1]
            stack.pop()
        self._stacks.pop(ident, None)
        return None

    def _end(self, frame: FrameType) -> None:
        """Take a load off its thread's stack, keeping one whose pop was not seen."""
        ident = threading.get_ident()
        load = None
        try:
            load = self._in_progress(spec=frame.f_locals['spec'], ident=ident)
        except FAULTS:
            self.faults += 1
        if load is None:
            return
        self._stacks[ident].pop()
        if not self._stacks[ident]:
            del self._stacks[ident]
        if load.readings.keys().isdisjoint({POP_LINE, POP_CALLED, POP_RETURNED, POP_RAISED}):
            self.ended_before_pop.append(load)

    def _innermost(self, ident: int) -> Load | None:
        """Find the load a collection on a thread is inside, else another thread's newest."""
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
    """Read whether a load's entry is in ``sys.modules``."""
    modules = sys.modules
    if load is None or load.key is None or type(modules) is not dict:
        return NOT_READ
    return PRESENT if load.key in modules else ABSENT


def loads_stopped_at_pop(
    *, probe: LoadProbe, traceback_object: TracebackType | None
) -> list[object]:
    """Find the specs whose loads a traceback left at their pop's line."""
    return [
        frame.f_locals['spec']
        for frame, line in traceback.walk_tb(traceback_object)
        if frame.f_code is probe.code and line == probe.points.pop_line
    ]


def without_home(text: str) -> str:
    """Hide the home folder's name."""
    return text.replace(str(Path.home()), '~')


def thread_names() -> dict[int | None, str]:
    """Name each thread threading knows, by ident, registering none."""
    return {thread.ident: thread.name for thread in threading.enumerate()}


def reading_line(reading: ReadingFields, *, names: Mapping[int | None, str]) -> str:
    """Describe one event."""
    event = Reading._make(reading)
    return (
        f'#{event.order} {event.name}, {event.point}: {event.found} (load {event.load_number}, '
        f'{names.get(event.thread_ident, f"ident {event.thread_ident}")}, {event.entries} entries '
        f'of dictionary {event.dictionary_id:#x})'
    )


def collection_line(collection: Collection, *, names: Mapping[int | None, str]) -> str:
    """Describe one collection, marked when the entry went during it."""
    on = names.get(collection.thread_ident, f'ident {collection.thread_ident}')
    loading, mark = 'nothing being loaded', ''
    if collection.name is not None:
        same = collection.loading_thread_ident == collection.thread_ident
        whose = 'the same thread' if same else 'another thread, approximate'
        loading = f'{collection.name} (loading on {whose}) {collection.before} before'
        loading += f', {collection.after} after'
    if collection.before == PRESENT and collection.after == ABSENT:
        mark = ' *** THE ENTRY WENT DURING THIS COLLECTION ***'
    return (
        f'#{collection.order}-{collection.ended_order} garbage collection of generation '
        f'{collection.generation} on {on}, {collection.collected} objects: {loading}{mark}'
    )


def verdict_of(load: Load) -> str:
    """Say where the entry of a load whose pop raised was lost, as far as the readings go."""
    if load.renamed:
        return 'not recorded: the spec was renamed during the load'
    found = {
        point: Reading._make(load.readings[point]).found if point in load.readings else NOT_READ
        for point in (STORED, POP_LINE, POP_CALLED)
    }
    dictionaries = {Reading._make(reading).dictionary_id for reading in load.readings.values()}
    if len(dictionaries) > 1:
        return 'not recorded: sys.modules was rebound during the load: no claim'
    if NOT_READ in found.values():
        return 'not recorded: at least one point of this load was not read'
    for point, verdict in (
        (STORED, 'the entry was already absent at the first line after the store'),
        (
            POP_LINE,
            "the entry left between the store and the pop's line: while its code (if any) ran",
        ),
        (POP_CALLED, "the entry left between the start of the pop's line and the call of pop"),
    ):
        if found[point] == ABSENT:
            return verdict
    return 'the entry was present when pop was called, and pop raised'


def failed_pop_report(
    *, failed: FailedPop, probe: LoadProbe, names: Mapping[int | None, str]
) -> list[str]:
    """Describe a failed pop: its points in order, what narrows it, and what else happened."""
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
        f'{", ".join(failed.missing) or "none"}'
    )
    for ident, stack in failed.other_threads:
        lines.append(
            f'alive as the pop raised: {names.get(ident, f"ident {ident}")} in '
            f'{without_home("; ".join(stack))}'
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
        f'events and collections from the store to the raise (at most the newest {LINES_REPORTED} '
        f'of the {len(between)} still in the rings; older ones are lost):'
    )
    lines.extend(f'  {line}' for line in between[-LINES_REPORTED:])
    return lines


def load_probe_report(
    *, probe: LoadProbe, failed_name: str | None, traceback_object: TracebackType | None
) -> str:
    """Describe what the probe recorded of a failed import of the module the error names."""
    lines = [EVIDENCE_NOT_A_FIX]
    if probe.not_recorded is not None:
        return '\n'.join((*lines, f'not recorded: {probe.not_recorded}'))
    lines.append(f'Faults in the recording: {probe.faults}')
    names = thread_names()
    stopped = loads_stopped_at_pop(probe=probe, traceback_object=traceback_object)
    for failed in reversed(tuple(probe.failed_pops)):
        if any(failed.load.spec is spec for spec in stopped):
            lines.extend(failed_pop_report(failed=failed, probe=probe, names=names))
            return '\n'.join((*lines, *HOW_TO_READ))
    lines.append(NO_FAILED_POP)
    ended = [load for load in tuple(probe.ended_before_pop) if load.name == failed_name]
    if ended:
        lines.append(
            f'the newest load of {failed_name} ended with its pop not seen: perhaps its own code '
            'raised, or the import was interrupted (matched by name alone)'
        )
        lines.extend(reading_line(reading, names=names) for reading in ended[-1].readings.values())
    return '\n'.join(lines)


def interpreter_report() -> str:
    """Describe the interpreter and how it was built, with no path but its own."""
    # Only whole words about features: the other configure arguments are paths
    configured = [
        word
        for word in str(sysconfig.get_config_var('CONFIG_ARGS')).replace("'", '').split()
        if word.startswith(('--with', '--enable')) and not {'/', '\\'} & set(word)
    ]
    jit: Any = getattr(sys, '_jit', None)
    variables = ', '.join(
        f'{name} {sysconfig.get_config_var(name)}'
        for name in ('Py_DEBUG', 'Py_GIL_DISABLED', 'Py_TAIL_CALL_INTERP')
    )
    build = f'build {platform.python_build()}, {platform.python_compiler()}'
    gil = 'on' if sys._is_gil_enabled() else 'off'
    jit_state = 'unknown' if jit is None else f'enabled: {jit.is_enabled()}'
    return '\n'.join((
        f'sys.version: {sys.version}',
        f'sys.executable: {without_home(sys.executable)}',
        f'platform: {sysconfig.get_platform()}, {build}',
        f'build settings (None: not given by this build): {variables}',
        f'the GIL: {gil}; the JIT: {jit_state}',
        f'configured with: {" ".join(configured) or "not given by this build"}',
    ))
