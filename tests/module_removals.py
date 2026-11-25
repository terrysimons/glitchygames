"""Record the known ways test code takes modules out of ``sys.modules``, for the triage report.

Triage tool for bugs/2026-11-20-httpcore2-import-keyerror-on-windows.md: an import fails with
``KeyError`` when its module leaves ``sys.modules`` while the module's own code runs, and the
failure does not say what removed it. tests/import_failure_threads.py installs this record for the
run and reports it. The calls recorded are wrapped in Python (``wrapped_methods``):

- ``unittest.mock``'s ``patch.dict(sys.modules)`` (and ``'sys.modules'``): its end, which clears
  the whole dictionary and puts its snapshot back, and its start when given ``clear=True``.
- pytester's ``SysModulesSnapshot.restore`` (the end of every ``runpytest_inprocess``): the same.
- ``monkeypatch.delitem(sys.modules, ...)``, and ``monkeypatch.undo`` when it changed
  ``sys.modules``.

``NOT_RECORDED`` is what this cannot see. CPython's dictionary watchers would see everything, but
must not be used: their callback runs inside the dictionary operation, between CPython finding the
entry's index and deleting by it, so Python code there lets another thread or a finalizer resize
the dictionary, and the process crashes (measured; the bug record has the details).

A wrapped call does what it did before, raising included, and a fault in the recording is counted
(``RemovalRecorder.recording_errors``), never raised; a method that is not there is reported as not
recorded. An entry is kept before the call runs and
completed after it, so an import that fails during the call still finds the entry. The names
removed are the keys missing after the call, so another thread's changes meanwhile count in it.

One recorder per process: ``install`` returns the one whose wrappers are in place, found on the
wrapped methods themselves, so a second copy of this module (pytester runs the plugin again in the
same process, and restoring ``sys.modules`` can drop this module) shares it. The last ``release``
puts the original methods back. Tests: tests/test_module_removals.py.
"""

from __future__ import annotations

import contextlib
import enum
import functools
import itertools
import sys
import threading
from typing import TYPE_CHECKING, Any, NamedTuple
from unittest import mock

import pytest
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from types import FrameType, TracebackType

# What a removal (or a thread) outside any test is marked with
OUTSIDE_ANY_TEST = 'outside any test'

# How many removals are kept, names listed per removal, and stack lines kept per removal
REMOVALS_KEPT = 50
NAMES_KEPT = 20
STACK_LINES_KEPT = 12

# What the record cannot see, said in every report
NOT_RECORDED = (
    "Not recorded: direct `del sys.modules[...]` and `sys.modules.pop(...)`, third-party code's "
    "own changes, and importlib's own delete when a module's import fails."
)

# What the marks are worth, said in every report
MARKS_ARE_SAMPLES = (
    'Imports in progress are read just before and just after each call: one marked may overlap it, '
    'and a missing mark proves nothing.'
)

# Where importlib's ``_load_unlocked`` runs a module's code
LOAD_FILENAME = '<frozen importlib._bootstrap>'
LOAD_FUNCTION = '_load_unlocked'

# The attribute a wrapper carries: the recorder it records to
RECORDER_ATTRIBUTE = '_glitchygames_removal_recorder'


class LoadInProgress(BaseModel):
    """A module some thread was executing when a removal began."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    module: str
    same_thread: bool


class Removal(BaseModel):
    """One recorded call that removed, or may have removed, names from ``sys.modules``."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    order: int
    made_by: str
    # True for a call that clears the dictionary before refilling it: every name leaves it a while
    whole_dictionary: bool
    thread_name: str
    on_main_thread: bool
    test_node_id: str
    stack: tuple[str, ...]
    loads_in_progress: tuple[LoadInProgress, ...]
    # Those that were in progress after the call and not before
    loads_after: tuple[LoadInProgress, ...] = ()
    # The names gone after the call (at most NAMES_KEPT) and how many; None while the call runs
    names_removed: tuple[str, ...] | None = None
    removed_count: int = 0
    # The loads in progress (before or after the call) that it may have overlapped: those whose
    # module it removed, and every one for a whole dictionary
    may_overlap: tuple[LoadInProgress, ...] = ()


def call_stack(frame: FrameType | None) -> tuple[str, ...]:
    """Describe a stack as text, innermost first, reading no source.

    Returns:
        ``file:line function`` for at most ``STACK_LINES_KEPT`` frames.

    """
    lines: list[str] = []
    while frame is not None and len(lines) < STACK_LINES_KEPT:
        lines.append(f'{frame.f_code.co_filename}:{frame.f_lineno} {frame.f_code.co_name}')
        frame = frame.f_back
    return tuple(lines)


def loads_in_progress() -> tuple[LoadInProgress, ...]:
    """Find every module any thread is executing in importlib's ``_load_unlocked`` now.

    Returns:
        Each such module, and whether it is this thread that is executing it.

    """
    this_thread = threading.get_ident()
    found: list[LoadInProgress] = []
    innermost: FrameType | None = None
    frame: FrameType | None = None
    try:
        for thread_ident, innermost in sys._current_frames().items():
            frame = innermost
            while frame is not None:
                code = frame.f_code
                if code.co_name == LOAD_FUNCTION and code.co_filename == LOAD_FILENAME:
                    found.append(
                        LoadInProgress(
                            module=frame.f_locals['spec'].name,
                            same_thread=thread_ident == this_thread,
                        )
                    )
                frame = frame.f_back
    finally:
        # One of these frames is this function's own: kept in its own locals, it would be a
        # reference cycle keeping every caller's locals alive until a garbage collection
        innermost = frame = None
    return tuple(found)


def thread_name(thread_ident: int) -> str:
    """Name a thread without registering it (``current_thread`` makes a dummy for a foreign one).

    Returns:
        The thread's name, or its ident when threading does not know it.

    """
    for thread in threading.enumerate():
        if thread.ident == thread_ident:
            return thread.name
    return f'unregistered thread {thread_ident}'


class RemovalRecorder:
    """The process's record of removals, and the wrappers that feed it."""

    def __init__(self) -> None:
        """Start with nothing recorded and nothing wrapped."""
        self.running_test_node_id = OUTSIDE_ANY_TEST
        self.recording_errors = 0
        self.installs = 0
        self.not_wrapped: list[str] = []
        self.startup_modules = sys.modules
        self._orders = itertools.count(1)
        # A ring: removal N is in slot N % REMOVALS_KEPT. Each read and write of a slot is atomic
        # under the GIL, so no lock is needed (a finalizer recording on a thread that held one
        # would deadlock)
        self._slots: list[Removal | None] = [None] * REMOVALS_KEPT
        self._wrapped: list[tuple[type, str, Any, Any]] = []

    def removals(self) -> list[Removal]:
        """Return the removals kept, newest first."""
        kept = [removal for removal in tuple(self._slots) if removal is not None]
        return sorted(kept, key=lambda removal: removal.order, reverse=True)

    def is_modules(self, dictionary: object) -> bool:
        """Tell whether an object is ``sys.modules``, as it is now or as it was at startup.

        Returns:
            True for either dictionary.

        """
        return dictionary is sys.modules or dictionary is self.startup_modules

    def __enter__(self) -> None:
        """Guard one piece of recording: nothing it raises may reach the call being recorded."""

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback_object: TracebackType | None,
    ) -> bool:
        """Count a fault in the recording, and keep it from the call being recorded.

        Returns:
            True for an ``Exception``; a ``KeyboardInterrupt`` or an exit goes on.

        """
        del error_type, traceback_object
        if isinstance(error, Exception):
            self.recording_errors += 1
            return True
        return False

    def begin(
        self, *, made_by: str, whole_dictionary: bool, caller: FrameType | None
    ) -> tuple[Removal, set[str]] | None:
        """Keep an entry for a call about to run.

        Returns:
            The entry and the names in ``sys.modules`` now; None when recording failed.

        """
        with self:
            this_thread = threading.get_ident()
            name = thread_name(this_thread)
            stack = call_stack(caller)
            loads = loads_in_progress()
            # Taken last, so a fault above uses no number
            order = next(self._orders)
            removal = Removal(
                order=order,
                made_by=made_by,
                whole_dictionary=whole_dictionary,
                thread_name=name,
                on_main_thread=this_thread == threading.main_thread().ident,
                test_node_id=self.running_test_node_id,
                stack=stack,
                loads_in_progress=loads,
                may_overlap=loads if whole_dictionary else (),
            )
            self._slots[order % REMOVALS_KEPT] = removal
            return removal, set(sys.modules)
        return None

    def complete(self, begun: tuple[Removal, set[str]] | None) -> None:
        """Add what a call removed to its entry, unless a newer entry has replaced it."""
        if begun is None:
            return
        with self:
            removal, names_before = begun
            removed = names_before.difference(sys.modules)
            before = removal.loads_in_progress
            after = tuple(load for load in loads_in_progress() if load not in before)
            completed = removal.model_copy(
                update={
                    'names_removed': tuple(sorted(removed)[:NAMES_KEPT]),
                    'removed_count': len(removed),
                    'loads_after': after,
                    'may_overlap': tuple(
                        load
                        for load in (*before, *after)
                        if removal.whole_dictionary or load.module in removed
                    ),
                }
            )
            slot = removal.order % REMOVALS_KEPT
            if self._slots[slot] is removal:
                self._slots[slot] = completed

    def wrapping(
        self, *, original: Callable[..., Any], made_by: str, decide: Decision
    ) -> Callable[..., Any]:
        """Wrap a method so the calls that change ``sys.modules`` are recorded.

        Args:
            original: The method as it was.
            made_by: What the entry says made the removal.
            decide: Given the recorder and the call's arguments, how to record it.

        Returns:
            The wrapper: it calls the original with the same arguments, and returns or raises what
            the original does.

        """

        @functools.wraps(original)
        def recorded(*args: Any, **keywords: Any) -> Any:
            __tracebackhide__ = True
            result: Any = None
            begun: tuple[Removal, set[str]] | None = None
            # Nothing in the recording, Ctrl-C included, may skip the call or hide what it raises
            try:
                recorded_as = Recorded.NOT
                if self.installs:
                    with self:
                        recorded_as = decide(self, args, keywords)
                if recorded_as is not Recorded.NOT:
                    begun = self.begin(
                        made_by=made_by,
                        whole_dictionary=recorded_as is Recorded.WHOLE_DICTIONARY,
                        caller=sys._getframe(1),
                    )
            finally:
                call_raised = True
                try:
                    result = original(*args, **keywords)
                    call_raised = False
                finally:
                    with EveryFault(self) if call_raised else self:
                        self.complete(begun)
            return result

        vars(recorded)[RECORDER_ATTRIBUTE] = self
        return recorded

    def wrap_methods(self) -> None:
        """Put the wrappers in place of ``wrapped_methods``, noting each that cannot be.

        A private method that a new pytest or Python renamed must not stop the run.
        """
        wrapped_all = False
        try:
            for method in wrapped_methods():
                self.not_wrapped.append(method.made_by)
                with self:
                    owner = method.find_owner()
                    original = vars(owner)[method.name]
                    wrapper = self.wrapping(
                        original=original, made_by=method.made_by, decide=method.decide
                    )
                    setattr(owner, method.name, wrapper)
                    self._wrapped.append((owner, method.name, original, wrapper))
                    self.not_wrapped.remove(method.made_by)
            wrapped_all = True
        finally:
            if not wrapped_all:
                self.unwrap_methods()

    def unwrap_methods(self) -> None:
        """Put the original methods back (leaving alone one that something else replaced since)."""
        for owner, name, original, wrapper in self._wrapped:
            if vars(owner).get(name) is wrapper:
                setattr(owner, name, original)
        self._wrapped.clear()


class EveryFault:
    """Guards recording while the recorded call's own exception is on its way out.

    A Ctrl-C then is dropped and counted: raised, it would replace that exception.
    """

    def __init__(self, recorder: RemovalRecorder) -> None:
        """Count into a recorder."""
        self.recorder = recorder

    def __enter__(self) -> None:
        """Guard one piece of recording."""

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback_object: TracebackType | None,
    ) -> bool:
        """Count a fault in the recording, and keep it from the call being recorded.

        Returns:
            Always True.

        """
        del error_type, traceback_object
        if error is not None:
            self.recorder.recording_errors += 1
        return True


class Recorded(enum.Enum):
    """How a wrapped call is recorded."""

    NOT = 'not recorded: it does not touch sys.modules'
    WHOLE_DICTIONARY = 'it clears sys.modules'
    SOME_ENTRIES = 'it changes entries of sys.modules'


type Decision = Callable[[RemovalRecorder, tuple[Any, ...], Mapping[str, Any]], Recorded]


class WrappedMethod(NamedTuple):
    """A method whose calls are recorded."""

    find_owner: Callable[[], type]
    name: str
    made_by: str
    decide: Decision


def patch_start(
    recorder: RemovalRecorder, args: tuple[Any, ...], keywords: Mapping[str, Any]
) -> Recorded:
    """Decide for ``patch.dict``'s start: it removes names only when given ``clear=True``.

    Returns:
        How to record the call.

    """
    del keywords
    patcher = args[0]
    if not patcher.clear:
        return Recorded.NOT
    target = patcher.in_dict
    # Only a string is compared: a dictionary-like target's __eq__ is the test's own code
    named = isinstance(target, str) and target == 'sys.modules'
    return Recorded.WHOLE_DICTIONARY if named or recorder.is_modules(target) else Recorded.NOT


def patch_end(
    recorder: RemovalRecorder, args: tuple[Any, ...], keywords: Mapping[str, Any]
) -> Recorded:
    """Decide for ``patch.dict``'s end (its start resolved the string form to the dictionary).

    Returns:
        How to record the call.

    """
    del keywords
    return Recorded.WHOLE_DICTIONARY if recorder.is_modules(args[0].in_dict) else Recorded.NOT


def snapshot_restore(
    recorder: RemovalRecorder, args: tuple[Any, ...], keywords: Mapping[str, Any]
) -> Recorded:
    """Decide for pytester's restore: always a whole-dictionary one.

    Returns:
        How to record the call.

    """
    del recorder, args, keywords
    return Recorded.WHOLE_DICTIONARY


def monkeypatch_delitem(
    recorder: RemovalRecorder, args: tuple[Any, ...], keywords: Mapping[str, Any]
) -> Recorded:
    """Decide for ``monkeypatch.delitem`` (its first argument may be given as ``dic=``).

    Returns:
        How to record the call.

    """
    dictionary = args[1] if len(args) > 1 else keywords.get('dic')
    return Recorded.SOME_ENTRIES if recorder.is_modules(dictionary) else Recorded.NOT


def monkeypatch_undo(
    recorder: RemovalRecorder, args: tuple[Any, ...], keywords: Mapping[str, Any]
) -> Recorded:
    """Decide for ``monkeypatch.undo``: recorded when it will change ``sys.modules``.

    Returns:
        How to record the call.

    """
    del keywords
    changed = any(recorder.is_modules(dictionary) for dictionary, _, _ in args[0]._setitem)
    return Recorded.SOME_ENTRIES if changed else Recorded.NOT


def patch_dict_class() -> type:
    """Find the class behind ``patch.dict``.

    Returns:
        ``unittest.mock``'s ``_patch_dict``.

    """
    return type(mock.patch.dict({}))


def snapshot_class() -> type:
    """Find pytester's snapshot class, importing pytester only now.

    Imported at the top of a plugin, pytester would come before ``-p pytester`` could ask for it,
    and pytest would warn that it is too late to rewrite its asserts.

    Returns:
        ``SysModulesSnapshot``.

    """
    from _pytest.pytester import SysModulesSnapshot

    return SysModulesSnapshot


def monkeypatch_class() -> type:
    """Find the class behind ``monkeypatch``.

    Returns:
        ``pytest.MonkeyPatch``.

    """
    return pytest.MonkeyPatch


def wrapped_methods() -> tuple[WrappedMethod, ...]:
    """List the methods wrapped.

    Returns:
        Every method whose calls are recorded.

    """
    return (
        WrappedMethod(
            find_owner=patch_dict_class,
            name='_patch_dict',
            made_by='patch.dict(sys.modules, clear=True) starting',
            decide=patch_start,
        ),
        WrappedMethod(
            find_owner=patch_dict_class,
            name='_unpatch_dict',
            made_by='patch.dict(sys.modules) ending (clears the dictionary, then refills it)',
            decide=patch_end,
        ),
        WrappedMethod(
            find_owner=snapshot_class,
            name='restore',
            made_by='pytester SysModulesSnapshot.restore (clears the dictionary, then refills it)',
            decide=snapshot_restore,
        ),
        WrappedMethod(
            find_owner=monkeypatch_class,
            name='delitem',
            made_by='monkeypatch.delitem(sys.modules, ...)',
            decide=monkeypatch_delitem,
        ),
        WrappedMethod(
            find_owner=monkeypatch_class,
            name='undo',
            made_by='monkeypatch.undo of changes to sys.modules',
            decide=monkeypatch_undo,
        ),
    )


def recorder_in_place() -> RemovalRecorder | None:
    """Find the recorder whose wrappers are in place.

    Returns:
        The recorder any wrapped method carries, or None.

    """
    for method in wrapped_methods():
        with contextlib.suppress(ImportError, AttributeError):
            return getattr(getattr(method.find_owner(), method.name), RECORDER_ATTRIBUTE)
    return None


def install() -> RemovalRecorder:
    """Wrap the methods, or share the wrappers already in place.

    Returns:
        The process's recorder; each install needs one ``release``.

    """
    recorder = recorder_in_place()
    if recorder is None:
        recorder = RemovalRecorder()
        recorder.wrap_methods()
    recorder.installs += 1
    return recorder


def release(recorder: RemovalRecorder) -> None:
    """Undo one install; the last one puts the original methods back."""
    recorder.installs -= 1
    if recorder.installs == 0:
        recorder.unwrap_methods()


def load_report(load: LoadInProgress) -> str:
    """Describe a load in progress.

    Returns:
        The module, and which thread was executing it.

    """
    return f'{load.module} ({"the same thread" if load.same_thread else "another thread"})'


def removal_report(removal: Removal) -> str:
    """Describe one removal.

    Returns:
        What made it, where, what it removed, the loads it overlapped, and its stack.

    """
    mark = ' *** MAY OVERLAP AN IMPORT ***' if removal.may_overlap else ''
    main = 'the main thread' if removal.on_main_thread else 'not the main thread'
    if removal.names_removed is None:
        removed = 'still running when this was written'
    elif removal.removed_count:
        more = removal.removed_count - len(removal.names_removed)
        removed = f'removed {removal.removed_count}: {", ".join(removal.names_removed)}'
        removed += f' and {more} more' if more else ''
    else:
        removed = 'removed nothing for good'
    lines = [
        f'#{removal.order} {removal.made_by}{mark}',
        f'  {removed}',
        f'  thread: {removal.thread_name} ({main}), during: {removal.test_node_id}',
    ]
    if removal.may_overlap:
        lines.append(f'  may overlap: {", ".join(map(load_report, removal.may_overlap))}')
    others = [
        load
        for load in (*removal.loads_in_progress, *removal.loads_after)
        if load not in removal.may_overlap
    ]
    if others:
        lines.append(f'  other modules executing: {", ".join(map(load_report, others))}')
    lines.extend(f'    {line}' for line in removal.stack)
    return '\n'.join(lines)


def removals_report(recorder: RemovalRecorder) -> str:
    """Describe every removal kept, newest first, and what is not recorded.

    Returns:
        The section's text.

    """
    removals = recorder.removals()
    blocks = [
        NOT_RECORDED,
        *(f'not recorded: {name} (its method was not found)' for name in recorder.not_wrapped),
        MARKS_ARE_SAMPLES,
        f'The newest {REMOVALS_KEPT} are kept',
        f'Faults in the recording: {recorder.recording_errors}',
        *(removal_report(removal) for removal in removals),
    ]
    if not removals:
        blocks.append('none recorded')
    return '\n'.join(blocks)
