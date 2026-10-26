# Engine Context, Sub-plan 1: State — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task (execution is subagent-driven: the owner, 2026-10-25). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `EngineContext` with a default context, and move the six smallest pieces of
process-wide state a running game depends on (audit rows C1-C6 of the master plan: the default
snap mode, the default background, the polled input, the random streams, the doors with the
frame clock, and the `SceneManager` singleton) into it, one task per piece, ending with a test
that runs two contexts in one process and proves none of them leaks.

**Architecture:** A leaf module, `src/glitchygames/engine_context.py` (standard library only),
holds `ContextSlot[T]` (a declared piece of per-context state: a unique name and a factory),
`EngineContext` (a value per slot, made on first read; `with context.active():` makes it
current through a `contextvars.ContextVar`), the default context and `current_context()`. Each
module that owns state declares its slot next to its code and reads
`current_context().value(slot=...)` where it used to read its module global; every public
function keeps its signature. Ordinary games never switch, so they, and every existing test,
run in the default context exactly as before.

**Tech Stack:** Python 3.14 (`contextvars`, PEP 695 generics), pygame-ce, pytest + pytest-mock +
xdist + pytest-cov, ruff, basedpyright, ty.

**Spec:** [2026-10-25-engine-context.md](2026-10-25-engine-context.md) (the master plan: the
audit, the design, the sub-plans). This is its sub-plan 1.

## Global Constraints

- Branch `feature/engine-context-1-state` from the latest `main`. Another branch is moving the
  games into `src/games/`; nothing in this plan names a game, a game's module or a game's path.
  Tests use stand-in scenes, stand-in doors and stand-in names inside `tests/` only.
- Python 3.14. New frozen data classes are pydantic models with
  `model_config = ConfigDict(frozen=True, extra='forbid')`; this plan adds none (its holders are
  mutable registries, written as `@dataclasses.dataclass` like the existing `_SourcesRegistry`
  and `EngineRandomState`, and `ContextSlot`, a declaration compared by identity).
- pytest-mock (`mocker`) only, never `unittest.mock`; keyword arguments in every call we write;
  full names (no abbreviations).
- No `# noqa`, no `# ruff: ignore`, no new `# type: ignore` / `# ty: ignore` / `# pyright:
  ignore`, no lint or type-checker configuration loosened. Task 7 removes one existing
  `# type: ignore[return-value] # ty: ignore[invalid-return-type]` (replaced by `cast`).
- Coverage stays at 100% (`--cov-fail-under=100` in `pyproject.toml`).
- Lint before tests: `ruff format`, `ruff check`, `basedpyright`, `ty check` on the touched files,
  then the tests. TDD: write the failing test, run it and see it fail for the stated reason, then
  implement.
- Every existing test function, golden replay, golden trace and bundled demo passes unchanged:
  that is the guard. Existing test files only gain tests and imports; the one change to test
  infrastructure is in `tests/harness.py` (a new fixture in Task 1, the `fresh_random_streams`
  fixture in Task 5, which patched `randomness._STATE`, a name this plan removes).
- Recordings are never re-recorded or rebaselined; no `*.jsonl.gz` file changes.
- Commits: stage explicitly by path (never `git add -A` or `git add .`), message ending with the
  trailer `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`; never push;
  never restore files from git.
- The pre-commit `replay-metrics` hook measures every golden replay and bundled demo on a commit
  that changes the measured paths (all of `src/`), about 15 s, and stages its ledger rows
  (`quality/replay-ledger/`) into the same commit. Never `--no-verify`, never `SKIP=`. Keep no
  untracked files under `src/` at commit time (the hook refuses them).
- Code comments name modules by dotted name (`glitchygames.engine_context`), plans by path.
- Tests of moved state (the owner's decision 1 in the master plan): a test that reached the
  private module state this plan moves tests the behaviour where it is observable, and reads
  through the current context (`current_context().value(slot=...)`) only where the state has
  no observable effect; the engine gets no test-only module accessors. Here it applies to one
  line: the harness fixture `fresh_random_streams` patched `randomness._STATE`; a per-test
  reset has no behaviour of its own, so Task 5 resets the slot through the default context
  (`default_context().reset_value(slot=randomness.ENGINE_RANDOM_STATE_SLOT)`). No test function
  reaches `_STATE`, `_REGISTRY`, `_CURRENT`, `_ActiveSnapSettings`,
  `_ActiveBackgroundSettings` or `SceneManager._instance` (checked at 53869ac4), so no other
  test line changes. (Non-test code did reach `SceneManager._instance`:
  `scripts/record_golden_traces.py` set it; Task 7 changed that script to write through the
  context.)
- `ContextSlot` is internal to the engine (the owner's decision 3): only engine modules declare
  slots; the tests' own `COUNTER_SLOT` exists to test the class. The slot constants are named
  without an underscore so the harness and tests can name them, not as API for games.

## Review Focus

The five failure modes most likely to bite that the tasks' own TDD tests would not exercise,
each with the pinning test the owning task adds:

1. **A slot read as a module is imported.** A module-level, class-body or default-argument read
   of `current_context()` (or `.value(slot=...)`) holds the default context's value for every
   context, silently. Pinned by `test_no_module_reads_a_context_as_it_is_imported` (a scan of
   the engine and every member) and `test_the_import_time_scan_finds_module_class_and_default_argument_reads`
   (Task 1).
2. **A switch that does not unwind.** An exception inside a block, nested switches, or a test
   that enters a context by hand and never leaves leaves the wrong context current for the rest
   of the worker. Pinned by `test_switches_nest_and_unwind_in_order`,
   `test_an_exception_inside_a_switch_propagates_and_the_previous_context_is_back` and the
   harness fixture `every_test_ends_in_the_default_engine_context` (Task 1).
3. **Tasks and threads.** In the browser the game is one asyncio task whose ticks are awaited: a
   switch held across an `await` must not be seen by another task, a task made inside a switch
   keeps it, and a thread sees it only when given a copied context. Pinned by
   `test_a_switch_held_across_an_await_is_not_seen_by_another_task`,
   `test_an_asyncio_task_made_inside_a_switch_keeps_its_context` and
   `test_a_thread_sees_the_context_current_where_it_starts_only_when_given_it` (Task 1).
4. **The singleton's inherited lookup.** `SceneManager._instance` was a class attribute, so a
   subclass with no entry of its own answered with its base class's manager, and `_reset()` on a
   subclass uninitialized the base's manager but cleared only the subclass's entry
   (tests/world/test_finish_frame.py relies on a subclass singleton). Pinned by
   `test_a_scene_manager_subclass_keeps_the_singleton_rules_of_the_class_attribute`, which passes
   on today's code and must still pass after (Task 7).
5. **State that crosses slots.** The doors made lazily by `active_sources()` take the master
   seed from the random streams: in a second context they must take that context's seed; and
   `restore_stream_states` restores in place, which must touch only the current context's stream
   objects. Pinned by `test_a_contexts_first_live_doors_take_that_contexts_master_seed` (Task 6)
   and `test_restoring_stream_states_in_one_context_never_touches_another_contexts_streams`
   (Task 5).

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `src/glitchygames/engine_context.py` | Create (Task 1) | `ContextSlot`, `EngineContext`, `DuplicateContextSlotError`, the default context, `current_context()`, `default_context()`, `declared_context_slots()` |
| `src/glitchygames/pixel_snap.py` | Modify (Task 2) | `SNAP_SETTINGS_SLOT` replaces `_ActiveSnapSettings` |
| `src/glitchygames/backgrounds.py` | Modify (Task 3) | `BACKGROUND_SETTINGS_SLOT` replaces `_ActiveBackgroundSettings` |
| `src/glitchygames/input/state.py` | Modify (Task 4) | `CURRENT_INPUT_SLOT` replaces `_CURRENT` |
| `src/glitchygames/randomness.py` | Modify (Task 5) | `ENGINE_RANDOM_STATE_SLOT` replaces `_STATE` |
| `src/glitchygames/sources.py` | Modify (Task 6) | `SOURCES_REGISTRY_SLOT` replaces `_REGISTRY` |
| `src/glitchygames/scenes/scene.py` | Modify (Task 7) | `SCENE_MANAGERS_SLOT` replaces `SceneManager._instance` |
| `tests/test_engine_context.py` | Create (Task 1), extend (Task 8) | the module's tests, the import-time scan, the two-context isolation tests |
| `tests/harness.py` | Modify (Tasks 1, 5) | fixture `every_test_ends_in_the_default_engine_context`; `fresh_random_streams` resets the default context's slot |
| `tests/world/test_positioning.py` | Add a test (Task 2) | snap mode per context |
| `tests/test_backgrounds.py` | Add a test (Task 3) | background per context |
| `tests/input/test_input_state.py` | Add a test (Task 4) | polled input per context |
| `tests/test_randomness.py` | Add tests (Task 5) | streams per context |
| `tests/test_clock.py` | Add tests (Task 6) | doors, frame clock, observers per context |
| `tests/scenes/test_scene_manager.py` | Add tests (Task 7) | scene manager per context, subclass rules |
| `docs/architecture/engine_context.md` | Create (Task 9) | the user-facing rules |
| `mkdocs.yml` | Modify (Task 9) | nav entry |
| `CLAUDE.md` | Modify (Task 9) | an Engine Context section; the doors bullet; the Singleton pattern line |
| `plans/2026-10-25-engine-context.md` | Modify (Task 9) | status |
| `plans/future-features.md` | Modify (Task 9) | #43 status |

---

### Task 1: The engine context module

**Files:**
- Create: `src/glitchygames/engine_context.py`
- Create: `tests/test_engine_context.py`
- Modify: `tests/harness.py` (imports; one new autouse fixture)

**Interfaces:**
- Consumes: `tests.ast_scanning.PROJECT_ROOT`, `tests.ast_scanning.scanned_source_files(*,
  project_root: Path) -> list[tuple[str, Path]]`, `scripts.workspace_packages.ENGINE_DIRECTORY`.
- Produces:
  ```python
  # src/glitchygames/engine_context.py
  DEFAULT_CONTEXT_NAME: str = 'default'
  class DuplicateContextSlotError(ValueError): ...
  class ContextSlot[T]:
      def __init__(self, *, name: str, factory: Callable[[], T]) -> None: ...
      name: str
      factory: Callable[[], T]
  class EngineContext:
      def __init__(self, *, name: str) -> None: ...
      name: str
      def value[T](self, *, slot: ContextSlot[T]) -> T: ...
      def reset_value[T](self, *, slot: ContextSlot[T]) -> T: ...
      @contextlib.contextmanager
      def active(self) -> Iterator[Self]: ...
  def current_context() -> EngineContext: ...
  def default_context() -> EngineContext: ...
  def declared_context_slots() -> tuple[ContextSlot[Any], ...]: ...
  ```
  Test helpers in `tests/test_engine_context.py` (Task 8 uses them):
  `calls_run_at_import(node: ast.AST) -> Iterator[ast.Call]`,
  `called_name(call: ast.Call) -> str | None`,
  `import_time_context_reads(*, source_path: Path) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_engine_context.py`:

```python
"""The engine context (glitchygames.engine_context): the state one running game owns.

Every test runs in the default context and switches only inside ``with context.active():``;
the harness fails a test that leaves another context current (tests/harness.py).
"""

from __future__ import annotations

import ast
import asyncio
import contextvars
import re
import sys
import threading
from typing import TYPE_CHECKING

import pytest
from scripts.workspace_packages import ENGINE_DIRECTORY

from glitchygames.engine_context import (
    DEFAULT_CONTEXT_NAME,
    ContextSlot,
    DuplicateContextSlotError,
    EngineContext,
    current_context,
    declared_context_slots,
    default_context,
)
from tests.ast_scanning import PROJECT_ROOT, scanned_source_files

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# A slot of this test module's own (declared once, as the module is imported, like every slot)
COUNTER_SLOT_NAME = 'tests.engine_context.counter'
COUNTER_SLOT: ContextSlot[list[int]] = ContextSlot(name=COUNTER_SLOT_NAME, factory=list)

# The functions that read an engine context (rule 2 of glitchygames.engine_context)
CONTEXT_READERS = frozenset({'current_context', 'default_context'})
# The EngineContext methods that read a slot's value (called with slot=...)
SLOT_READERS = frozenset({'value', 'reset_value'})

# A module that reads a context as it is imported: at module level (line 3), in a default
# argument (line 5) and in a class body (line 9); the read in the function body (line 6) is fine
PLANTED_IMPORT_TIME_READS = """\
from glitchygames.engine_context import current_context

STATE = current_context()

def later(default=current_context()):
    return current_context()

class Holder:
    held = current_context()
"""


class SwitchedAwayError(RuntimeError):
    """Raised inside a switch, to see the switch unwind."""


@pytest.fixture(autouse=True)
def fresh_default_counter():
    """Start and end each test with an empty counter in the default context."""
    default_context().reset_value(slot=COUNTER_SLOT)
    yield
    default_context().reset_value(slot=COUNTER_SLOT)


def switch_and_raise(*, context: EngineContext) -> None:
    """Switch to ``context`` and raise inside the switch.

    Args:
        context: The context switched to.

    Raises:
        SwitchedAwayError: Always, from inside the switch.

    """
    with context.active():
        raise SwitchedAwayError


def calls_run_at_import(node: ast.AST) -> Iterator[ast.Call]:
    """Yield every call evaluated as a module is imported (not in a function or lambda body).

    Module and class bodies run at import; so do decorators and default arguments.

    Args:
        node: The node to search (a whole module, at the top).

    Yields:
        Each call, in source order.

    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        evaluated_at_definition: list[ast.expr] = [
            *node.args.defaults,
            *(default for default in node.args.kw_defaults if default is not None),
        ]
        if not isinstance(node, ast.Lambda):
            evaluated_at_definition.extend(node.decorator_list)
        for expression in evaluated_at_definition:
            yield from calls_run_at_import(expression)
        return
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from calls_run_at_import(child)


def called_name(call: ast.Call) -> str | None:
    """Return the name a call calls (``f()`` -> ``f``, ``a.b.f()`` -> ``f``), else None.

    Args:
        call: The call.

    Returns:
        The name, or None for a call of anything else (a subscript, a call's result).

    """
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def import_time_context_reads(*, source_path: Path) -> list[str]:
    """Return ``'<line>: <name>'`` for each engine-context read run as the file is imported.

    Args:
        source_path: A Python file.

    Returns:
        The reads, by line.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    reads: list[tuple[int, str]] = []
    for call in calls_run_at_import(tree):
        name = called_name(call)
        reads_a_slot = name in SLOT_READERS and any(
            keyword.arg == 'slot' for keyword in call.keywords
        )
        if name is not None and (name in CONTEXT_READERS or reads_a_slot):
            reads.append((call.lineno, name))
    return [f'{line}: {name}' for line, name in sorted(reads)]


def test_the_default_context_is_current_outside_every_switch():
    """Ordinary games and every test run in the default context (rule 4)."""
    assert current_context() is default_context()
    assert default_context().name == DEFAULT_CONTEXT_NAME


def test_a_context_is_current_inside_its_switch_and_the_previous_one_after():
    """``with context.active():`` makes it current and puts the previous one back (rule 5)."""
    second = EngineContext(name='second')

    with second.active() as switched_to:
        assert switched_to is second
        assert current_context() is second

    assert current_context() is default_context()


def test_switches_nest_and_unwind_in_order():
    """Each block restores what was current when it began, the same context nested included."""
    first = EngineContext(name='first')
    second = EngineContext(name='second')

    with first.active():
        with second.active():
            with first.active():
                assert current_context() is first
            assert current_context() is second
        assert current_context() is first

    assert current_context() is default_context()


def test_an_exception_inside_a_switch_propagates_and_the_previous_context_is_back():
    """An exception leaves the block with the previous context current (rule 5)."""
    first = EngineContext(name='first')
    second = EngineContext(name='second')

    with first.active():
        with pytest.raises(SwitchedAwayError):
            switch_and_raise(context=second)
        assert current_context() is first

    assert current_context() is default_context()


def test_a_slot_value_is_made_by_its_factory_on_first_read_and_kept():
    """A context makes a slot's value once (rule 3) and returns the same object after."""
    second = EngineContext(name='second')

    second_counter = second.value(slot=COUNTER_SLOT)
    second_counter.append(1)

    assert second.value(slot=COUNTER_SLOT) is second_counter
    assert second.value(slot=COUNTER_SLOT) == [1]


def test_each_context_has_its_own_value_of_a_slot():
    """A value written in one context is never seen in another."""
    second = EngineContext(name='second')

    default_context().value(slot=COUNTER_SLOT).append(1)
    with second.active():
        current_context().value(slot=COUNTER_SLOT).append(2)

    assert default_context().value(slot=COUNTER_SLOT) == [1]
    assert second.value(slot=COUNTER_SLOT) == [2]


def test_reset_value_gives_a_context_a_fresh_value():
    """reset_value replaces the context's value with a new one from the factory."""
    second = EngineContext(name='second')
    old_counter = second.value(slot=COUNTER_SLOT)
    old_counter.append(3)

    fresh_counter = second.reset_value(slot=COUNTER_SLOT)

    assert fresh_counter == []
    assert fresh_counter is not old_counter
    assert second.value(slot=COUNTER_SLOT) is fresh_counter


def test_a_second_slot_of_a_declared_name_is_refused():
    """Slot names are unique (rule 1)."""
    with pytest.raises(DuplicateContextSlotError, match=re.escape(COUNTER_SLOT_NAME)):
        ContextSlot(name=COUNTER_SLOT_NAME, factory=list)


def test_every_declared_slot_is_listed_once():
    """declared_context_slots() lists each slot made, once."""
    names = [slot.name for slot in declared_context_slots()]

    assert COUNTER_SLOT in declared_context_slots()
    assert len(names) == len(set(names))


def test_contexts_and_slots_name_themselves():
    """Their reprs name them (logs and failures)."""
    assert repr(EngineContext(name='second')) == "EngineContext(name='second')"
    assert repr(COUNTER_SLOT) == f'ContextSlot(name={COUNTER_SLOT_NAME!r})'


def test_a_thread_sees_the_context_current_where_it_starts_only_when_given_it():
    """A thread gets the switch only through a copied context (or the interpreter's flag)."""
    second = EngineContext(name='second')
    seen: dict[str, EngineContext] = {}

    def read_into(key: str) -> None:
        seen[key] = current_context()

    with second.active():
        plain_thread = threading.Thread(target=read_into, args=('plain',))
        given_thread = threading.Thread(
            target=read_into, args=('given',), context=contextvars.copy_context()
        )
        for thread in (plain_thread, given_thread):
            thread.start()
            thread.join()

    assert seen['given'] is second
    expected_plain = second if sys.flags.thread_inherit_context else default_context()
    assert seen['plain'] is expected_plain


def test_an_asyncio_task_made_inside_a_switch_keeps_its_context():
    """asyncio copies the current context into a task as it makes it."""
    second = EngineContext(name='second')

    async def read_context() -> EngineContext:
        return current_context()

    async def run() -> EngineContext:
        with second.active():
            task = asyncio.create_task(read_context())
        return await task

    assert asyncio.run(run()) is second
    assert current_context() is default_context()


def test_a_switch_held_across_an_await_is_not_seen_by_another_task():
    """The browser's case: one thread, the game's ticks awaited (glitchygames.host)."""
    second = EngineContext(name='second')
    seen: list[EngineContext] = []

    async def read_context() -> None:
        seen.append(current_context())

    async def run() -> None:
        other_task = asyncio.create_task(read_context())
        with second.active():
            # The other task runs here, while this task is switched
            await asyncio.sleep(0)
        await other_task

    asyncio.run(run())

    assert seen == [default_context()]


def test_no_module_reads_a_context_as_it_is_imported():
    """Rule 2, over the engine and every workspace member."""
    offenders = {
        allowlist_key: reads
        for allowlist_key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (reads := import_time_context_reads(source_path=path))
    }

    assert offenders == {}


def test_the_import_time_scan_finds_module_class_and_default_argument_reads(tmp_path):
    """The scan reports reads run at import and leaves function bodies alone."""
    planted_path = tmp_path / 'planted.py'
    planted_path.write_text(PLANTED_IMPORT_TIME_READS, encoding='utf-8')

    assert import_time_context_reads(source_path=planted_path) == [
        '3: current_context',
        '5: current_context',
        '9: current_context',
    ]


def test_the_engine_context_module_imports_only_the_standard_library():
    """A leaf: every module, sources.py and randomness.py included, may import it."""
    source_path = PROJECT_ROOT / ENGINE_DIRECTORY / 'engine_context.py'
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module.split('.')[0])

    assert imported
    assert imported <= sys.stdlib_module_names
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_context.py`
Expected: FAIL at collection: `ModuleNotFoundError: No module named 'glitchygames.engine_context'`.

- [ ] **Step 3: Write the module**

Create `src/glitchygames/engine_context.py`:

```python
"""The engine context: the state one running game owns, so several can run in one process.

plans/2026-10-25-engine-context.md is the design (the audit of every piece of process-wide
state, the shared resources, the sub-plans). Rules:

1. Per-context state is declared where it is used, as a ``ContextSlot`` (a unique dotted name
   and a factory), once, at module level::

       ENGINE_RANDOM_STATE_SLOT = ContextSlot(
           name='glitchygames.randomness.streams', factory=EngineRandomState
       )

   A second slot of the same name is refused (``DuplicateContextSlotError``).
2. Code reads a slot when it needs it, ``current_context().value(slot=...)``, never as its
   module is imported (at module level, in a class body or in a default argument): a value read
   then would be the default context's for every context. tests/test_engine_context.py scans
   the engine and every workspace member for such reads.
3. A context makes each slot's value with the slot's factory the first time it is read there,
   so a new context starts as a fresh process would. ``reset_value`` makes a fresh one.
4. ``current_context()`` is the context switched to last in this thread or asyncio task, else
   the default context. Ordinary games and every test run in the default context and never
   switch.
5. ``with context.active():`` makes the context current and puts back the one that was current
   when the block began, when it ends normally or by an exception (which propagates). Switches
   nest. The current context is a ``contextvars.ContextVar``: an asyncio task made inside a
   switch keeps that context (asyncio copies the context into a task as it makes it), and a
   switch held across an ``await`` is never seen by another task. A ``threading.Thread`` sees
   the context current where it is started only when started with
   ``context=contextvars.copy_context()`` (or on an interpreter whose
   ``sys.flags.thread_inherit_context`` is set); otherwise it sees the default context.
6. A context owns only what its slots hold. Objects are not bound to a context (a stream, a set
   of doors, a scene keeps its own state wherever it is used); only the module-level lookups
   follow the current context. The display, the mixer, SDL's event queue and the joystick
   subsystem are one per process, arbitrated by the master plan's later sub-plans, never
   switched.

This module is a leaf: it imports only the standard library, so any module may import it.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING, Any, Self, cast

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

# The name of the context every game runs in unless it switches (rule 4)
DEFAULT_CONTEXT_NAME = 'default'


class DuplicateContextSlotError(ValueError):
    """A ContextSlot was declared with the name of a slot declared before (rule 1)."""


# Every slot declared so far, by name: written once per slot, as its module is imported
_DECLARED_SLOTS: dict[str, ContextSlot[Any]] = {}


class ContextSlot[T]:
    """One piece of per-context state: its name and the factory a context makes it with.

    Compared by identity (it is a dictionary key in every context), never by name.
    """

    __slots__ = ('factory', 'name')

    def __init__(self: Self, *, name: str, factory: Callable[[], T]) -> None:
        """Declare the slot (rule 1).

        Args:
            name: Unique: the declaring module's dotted name and what it holds
                (``'glitchygames.randomness.streams'``).
            factory: Makes the slot's value for a context, the first time it is read there.

        Raises:
            DuplicateContextSlotError: If a slot of this name was declared before.

        """
        if name in _DECLARED_SLOTS:
            message = f'A context slot named {name!r} is already declared'
            raise DuplicateContextSlotError(message)
        self.name = name
        self.factory = factory
        _DECLARED_SLOTS[name] = self

    def __repr__(self: Self) -> str:
        """Return ``ContextSlot(name='...')``.

        Returns:
            The repr.

        """
        return f'ContextSlot(name={self.name!r})'


class EngineContext:
    """The state one running game owns: a value for each slot, made on first read (rule 3)."""

    def __init__(self: Self, *, name: str) -> None:
        """Make a context holding no values yet.

        Args:
            name: What logs and failures call it (``'default'``, ``'demo player 3'``).

        """
        self.name = name
        self._values: dict[ContextSlot[Any], object] = {}

    def __repr__(self: Self) -> str:
        """Return ``EngineContext(name='...')``.

        Returns:
            The repr.

        """
        return f'EngineContext(name={self.name!r})'

    def value[T](self: Self, *, slot: ContextSlot[T]) -> T:
        """Return this context's value of ``slot``, made by the slot's factory on first read.

        Args:
            slot: The slot.

        Returns:
            The value: the same object on every read until ``reset_value``.

        """
        values = self._values
        if slot in values:
            return cast('T', values[slot])
        made_value = slot.factory()
        values[slot] = made_value
        return made_value

    def reset_value[T](self: Self, *, slot: ContextSlot[T]) -> T:
        """Replace this context's value of ``slot`` with a fresh one from the factory.

        Args:
            slot: The slot.

        Returns:
            The fresh value.

        """
        made_value = slot.factory()
        self._values[slot] = made_value
        return made_value

    @contextlib.contextmanager
    def active(self: Self) -> Iterator[Self]:
        """Make this the current context until the block ends (rule 5).

        Yields:
            This context.

        """
        token = _CURRENT_CONTEXT.set(self)
        try:
            yield self
        finally:
            _CURRENT_CONTEXT.reset(token)


# The context switched to last in this thread or asyncio task; None means the default (rule 4)
_CURRENT_CONTEXT: contextvars.ContextVar[EngineContext | None] = contextvars.ContextVar(
    'glitchygames_engine_context', default=None
)

_DEFAULT_CONTEXT = EngineContext(name=DEFAULT_CONTEXT_NAME)


def current_context() -> EngineContext:
    """Return the context switched to last in this thread or task, else the default one.

    Returns:
        The current context.

    """
    switched_to = _CURRENT_CONTEXT.get()
    return _DEFAULT_CONTEXT if switched_to is None else switched_to


def default_context() -> EngineContext:
    """Return the default context (every game's, unless it switches).

    Returns:
        The default context.

    """
    return _DEFAULT_CONTEXT


def declared_context_slots() -> tuple[ContextSlot[Any], ...]:
    """Return every slot declared so far, in the order declared.

    Returns:
        The slots.

    """
    return tuple(_DECLARED_SLOTS.values())
```

- [ ] **Step 4: Add the harness fixture**

In `tests/harness.py`, change the import line

```python
from glitchygames import pixel_snap, randomness, sources
```

to

```python
from glitchygames import engine_context, pixel_snap, randomness, sources
```

add, after `from glitchygames.engine import GameEngine`:

```python
from glitchygames.engine_context import current_context, default_context
```

and add this fixture directly after the `restore_signal_handlers` fixture:

```python
@pytest.fixture(autouse=True)
def every_test_ends_in_the_default_engine_context():
    """Fail a test that leaves another engine context current (glitchygames.engine_context).

    Every test starts in the default context. A switch that never unwound (a context manager
    entered by hand and never exited) would leave its context current for every later test on
    the worker, so the leak is undone before the test is failed.
    """
    yield
    leaked_context = current_context()
    if leaked_context is not default_context():
        engine_context._CURRENT_CONTEXT.set(None)
        pytest.fail(f'the test left the engine context {leaked_context.name!r} current')
```

- [ ] **Step 5: Lint**

Run:
```bash
uv run ruff format src/glitchygames/engine_context.py tests/test_engine_context.py tests/harness.py
uv run ruff check src/glitchygames/engine_context.py tests/test_engine_context.py tests/harness.py
uv run basedpyright src/glitchygames/engine_context.py tests/test_engine_context.py tests/harness.py
uv run ty check src/glitchygames/engine_context.py tests/test_engine_context.py tests/harness.py
```
Expected: ruff `All checks passed!`; basedpyright `0 errors, 0 warnings, 0 notes`; ty `All
checks passed!`.

- [ ] **Step 6: Run the tests**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_context.py`
Expected: `16 passed`.

- [ ] **Step 7: Run the whole suite (the guard)**

Run: `uv run pytest --dummy-only`
Expected: every test passes, `Required test coverage of 100% reached`.

- [ ] **Step 8: Commit**

```bash
git add src/glitchygames/engine_context.py tests/test_engine_context.py tests/harness.py
git commit -m "$(cat <<'EOF'
Engine context: EngineContext, context slots, the default context and switching

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the `replay-metrics` hook measures (about 15 s) and adds its rows under
`quality/replay-ledger/`; `git show --stat HEAD` lists them with the three files.

---

### Task 2: The default snap mode per context (audit C1)

**Files:**
- Modify: `src/glitchygames/pixel_snap.py`
- Test: `tests/world/test_positioning.py`

**Interfaces:**
- Consumes: `ContextSlot`, `current_context`, `EngineContext` (Task 1).
- Produces: `SNAP_SETTINGS_SLOT: ContextSlot[_SnapSettings]` (name
  `'glitchygames.pixel_snap.default_mode'`); `set_active_default_snap_mode(mode: PixelSnapMode)
  -> None`, `active_default_snap_mode() -> PixelSnapMode`, `resolve_snap_mode(sprite: object) ->
  PixelSnapMode` unchanged in signature, now per context. `_ActiveSnapSettings` is removed.

- [ ] **Step 1: Write the failing test**

In `tests/world/test_positioning.py`, add to the imports:

```python
from glitchygames.engine_context import EngineContext
```

and add at the end of the file:

```python
def test_each_engine_context_has_its_own_default_snap_mode():
    """The running scene's snap mode in one context never changes another's (audit C1)."""
    second = EngineContext(name='second')
    set_active_default_snap_mode(mode=PixelSnapMode.FLOOR)

    with second.active():
        assert active_default_snap_mode() is PixelSnapMode.NEAREST_HALF_UP
        set_active_default_snap_mode(mode=PixelSnapMode.CEIL)
        assert resolve_snap_mode(object()) is PixelSnapMode.CEIL

    assert active_default_snap_mode() is PixelSnapMode.FLOOR
    assert resolve_snap_mode(object()) is PixelSnapMode.FLOOR
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/world/test_positioning.py -k engine_context`
Expected: `1 failed`: `assert <PixelSnapMode.FLOOR: 'floor'> is <PixelSnapMode.NEAREST_HALF_UP:
'nearest_half_up'>` (the snap mode is process-wide).

- [ ] **Step 3: Implement**

In `src/glitchygames/pixel_snap.py`, replace the imports

```python
import math
from enum import Enum
from typing import assert_never
```

with

```python
import dataclasses
import math
from enum import Enum
from typing import assert_never

from glitchygames.engine_context import ContextSlot, current_context
```

Replace

```python
class _ActiveSnapSettings:
    """Holds the engine-wide default snap mode (the running scene's PIXEL_SNAP_MODE)."""

    default_mode: PixelSnapMode = PixelSnapMode.NEAREST_HALF_UP


def set_active_default_snap_mode(mode: PixelSnapMode) -> None:
    """Set the snap mode used by sprites that do not choose their own.

    Args:
        mode: The new default (normally the active scene's PIXEL_SNAP_MODE).

    """
    _ActiveSnapSettings.default_mode = mode


def active_default_snap_mode() -> PixelSnapMode:
    """Return the snap mode used by sprites that do not choose their own.

    Returns:
        PixelSnapMode: The active default (initially NEAREST_HALF_UP).

    """
    return _ActiveSnapSettings.default_mode
```

with

```python
@dataclasses.dataclass
class _SnapSettings:
    """Holds an engine context's default snap mode (the running scene's PIXEL_SNAP_MODE)."""

    default_mode: PixelSnapMode = PixelSnapMode.NEAREST_HALF_UP


# Each engine context's default snap mode (glitchygames.engine_context)
SNAP_SETTINGS_SLOT: ContextSlot[_SnapSettings] = ContextSlot(
    name='glitchygames.pixel_snap.default_mode', factory=_SnapSettings
)


def set_active_default_snap_mode(mode: PixelSnapMode) -> None:
    """Set the snap mode used by sprites that do not choose their own, in this engine context.

    Args:
        mode: The new default (normally the active scene's PIXEL_SNAP_MODE).

    """
    current_context().value(slot=SNAP_SETTINGS_SLOT).default_mode = mode


def active_default_snap_mode() -> PixelSnapMode:
    """Return the snap mode used by sprites that do not choose their own, in this engine context.

    Returns:
        PixelSnapMode: The active default (initially NEAREST_HALF_UP).

    """
    return current_context().value(slot=SNAP_SETTINGS_SLOT).default_mode
```

and at the end of `resolve_snap_mode` replace

```python
        return sprite_mode
    return _ActiveSnapSettings.default_mode
```

with

```python
        return sprite_mode
    return current_context().value(slot=SNAP_SETTINGS_SLOT).default_mode
```

Check: `grep -n "_ActiveSnapSettings" -r src tests` prints nothing.

In `tests/harness.py`, fixture `reset_default_snap_mode`, replace the docstring sentence
`The active default is process-global (glitchygames/pixel_snap.py) and scene setup sets it` with
`The active default is per engine context (glitchygames.pixel_snap) and scene setup sets it`.

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff format src/glitchygames/pixel_snap.py tests/world/test_positioning.py tests/harness.py
uv run ruff check src/glitchygames/pixel_snap.py tests/world/test_positioning.py tests/harness.py
uv run basedpyright src/glitchygames/pixel_snap.py tests/world/test_positioning.py
uv run ty check src/glitchygames/pixel_snap.py tests/world/test_positioning.py
```
Expected: no errors.

- [ ] **Step 5: Run the test, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/world/test_positioning.py -k engine_context`
Expected: `1 passed`.
Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/pixel_snap.py tests/world/test_positioning.py tests/harness.py
git commit -m "$(cat <<'EOF'
Engine context: the default snap mode belongs to the context

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 3: The default background pattern per context (audit C2)

**Files:**
- Modify: `src/glitchygames/backgrounds.py`
- Test: `tests/test_backgrounds.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `BACKGROUND_SETTINGS_SLOT: ContextSlot[_BackgroundSettings]` (name
  `'glitchygames.backgrounds.default_pattern'`); `set_active_default_background_pattern(*,
  pattern: BackgroundPattern) -> None`, `active_default_background_pattern() ->
  BackgroundPattern`, `paint_default_background(*, surface: pygame.Surface) -> None` unchanged
  in signature, now per context. `_ActiveBackgroundSettings` is removed. The pattern cache
  (`background_pattern_surface`, audit R7) stays shared.

- [ ] **Step 1: Write the failing test**

In `tests/test_backgrounds.py`, add to the imports:

```python
from glitchygames.engine_context import EngineContext
```

and add at the end of the file:

```python
def test_each_engine_context_has_its_own_default_background():
    """One context's --default-background never changes another's scenes (audit C2)."""
    second = EngineContext(name='second')
    set_active_default_background_pattern(pattern=BackgroundPattern.CHANNEL_THREE)

    with second.active():
        assert active_default_background_pattern() is DEFAULT_BACKGROUND_PATTERN
        second_surface = pygame.Surface(PATTERN_SIZE)
        paint_default_background(surface=second_surface)
        assert rgb_at(second_surface, x=0, y=0) == BAR_GREY

    assert active_default_background_pattern() is BackgroundPattern.CHANNEL_THREE
    default_surface = pygame.Surface(PATTERN_SIZE)
    paint_default_background(surface=default_surface)
    assert rgb_at(default_surface, x=0, y=0) == VCR_BLUE
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_backgrounds.py -k engine_context`
Expected: `1 failed`: `assert <BackgroundPattern.CHANNEL_THREE: 'channel-3'> is
<BackgroundPattern.TEST_PATTERN: 'test-pattern'>`.

- [ ] **Step 3: Implement**

In `src/glitchygames/backgrounds.py`, replace in the module docstring

```text
which costs about what a fill does. The default is process-wide
(``set_active_default_background_pattern``); ``--default-background`` sets it for a run.
```

with

```text
which costs about what a fill does. The default belongs to the engine context
(glitchygames.engine_context; ``set_active_default_background_pattern``);
``--default-background`` sets it for a run.
```

Replace the imports

```python
import functools
from enum import StrEnum
```

with

```python
import dataclasses
import functools
from enum import StrEnum
```

and add, before `from glitchygames.opacity import make_opaque`:

```python
from glitchygames.engine_context import ContextSlot, current_context
```

Replace

```python
class _ActiveBackgroundSettings:
    """Holds the process-wide default background (what a scene that sets none gets)."""

    default_pattern: BackgroundPattern = DEFAULT_BACKGROUND_PATTERN


def set_active_default_background_pattern(*, pattern: BackgroundPattern) -> None:
    """Set the background a scene gets when it sets none.

    Args:
        pattern: The new default (the engine sets it from ``--default-background``).

    """
    _ActiveBackgroundSettings.default_pattern = pattern


def active_default_background_pattern() -> BackgroundPattern:
    """Return the background a scene gets when it sets none.

    Returns:
        BackgroundPattern: The active default (initially the test pattern).

    """
    return _ActiveBackgroundSettings.default_pattern
```

with

```python
@dataclasses.dataclass
class _BackgroundSettings:
    """Holds an engine context's default background (what a scene that sets none gets)."""

    default_pattern: BackgroundPattern = DEFAULT_BACKGROUND_PATTERN


# Each engine context's default background (glitchygames.engine_context)
BACKGROUND_SETTINGS_SLOT: ContextSlot[_BackgroundSettings] = ContextSlot(
    name='glitchygames.backgrounds.default_pattern', factory=_BackgroundSettings
)


def set_active_default_background_pattern(*, pattern: BackgroundPattern) -> None:
    """Set the background a scene gets when it sets none, in this engine context.

    Args:
        pattern: The new default (the engine sets it from ``--default-background``).

    """
    current_context().value(slot=BACKGROUND_SETTINGS_SLOT).default_pattern = pattern


def active_default_background_pattern() -> BackgroundPattern:
    """Return the background a scene gets when it sets none, in this engine context.

    Returns:
        BackgroundPattern: The active default (initially the test pattern).

    """
    return current_context().value(slot=BACKGROUND_SETTINGS_SLOT).default_pattern
```

Check: `grep -n "_ActiveBackgroundSettings" -r src tests` prints nothing.

In `tests/harness.py`, fixture `reset_default_background_pattern`, replace `The default is
process-global (glitchygames/backgrounds.py) and GameEngine sets it from` with `The default is
per engine context (glitchygames.backgrounds) and GameEngine sets it from`.

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff format src/glitchygames/backgrounds.py tests/test_backgrounds.py tests/harness.py
uv run ruff check src/glitchygames/backgrounds.py tests/test_backgrounds.py tests/harness.py
uv run basedpyright src/glitchygames/backgrounds.py tests/test_backgrounds.py
uv run ty check src/glitchygames/backgrounds.py tests/test_backgrounds.py
```
Expected: no errors.

- [ ] **Step 5: Run the test, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_backgrounds.py -k engine_context`
Expected: `1 passed`.
Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/backgrounds.py tests/test_backgrounds.py tests/harness.py
git commit -m "$(cat <<'EOF'
Engine context: the default background belongs to the context

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 4: The polled input per context (audit C3)

**Files:**
- Modify: `src/glitchygames/input/state.py`
- Test: `tests/input/test_input_state.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `CURRENT_INPUT_SLOT: ContextSlot[_CurrentInput]` (name
  `'glitchygames.input.state.current_input'`); `current_input() -> InputSnapshot`,
  `set_current_input(*, snapshot: InputSnapshot) -> None`, `reset_current_input() -> None`
  unchanged in signature, now per context. `_CURRENT` is removed.

- [ ] **Step 1: Write the failing test**

In `tests/input/test_input_state.py`, add to the imports:

```python
from glitchygames.engine_context import EngineContext
from glitchygames.input.state import reset_current_input
```

and add at the end of the file:

```python
# SDL scancodes of Space and Return (physical positions, the same on every layout)
SPACE_SCANCODE = 44
RETURN_SCANCODE = 40


def snapshot_holding(*, scancode: int) -> InputSnapshot:
    """Return a snapshot with one key held and the mouse idle.

    Args:
        scancode: The SDL scancode held.

    Returns:
        The snapshot.

    """
    return InputSnapshot(
        pressed_scancodes=frozenset({scancode}),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
    )


def test_each_engine_context_has_its_own_polled_input():
    """A frame's snapshot in one context is never another context's input (audit C3)."""
    second = EngineContext(name='second')
    set_current_input(snapshot=snapshot_holding(scancode=SPACE_SCANCODE))

    with second.active():
        assert current_input() is IDLE_INPUT
        set_current_input(snapshot=snapshot_holding(scancode=RETURN_SCANCODE))
        assert current_input().pressed_scancodes == frozenset({RETURN_SCANCODE})

    assert current_input().pressed_scancodes == frozenset({SPACE_SCANCODE})
    reset_current_input()
    assert current_input() is IDLE_INPUT
    with second.active():
        assert current_input().pressed_scancodes == frozenset({RETURN_SCANCODE})
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/input/test_input_state.py -k engine_context`
Expected: `1 failed`: `assert InputSnapshot(pressed_scancodes=frozenset({44}), ...) is
InputSnapshot(pressed_scancodes=frozenset(), ...)`.

- [ ] **Step 3: Implement**

In `src/glitchygames/input/state.py`, add to the first-party imports (ruff orders them):

```python
from glitchygames.engine_context import ContextSlot, current_context
```

Replace

```python
_CURRENT: list[InputSnapshot] = [IDLE_INPUT]
```

with

```python
@dataclasses.dataclass
class _CurrentInput:
    """Holds an engine context's polled input this frame (current_input)."""

    snapshot: InputSnapshot = IDLE_INPUT


# Each engine context's polled input (glitchygames.engine_context)
CURRENT_INPUT_SLOT: ContextSlot[_CurrentInput] = ContextSlot(
    name='glitchygames.input.state.current_input', factory=_CurrentInput
)
```

In `current_input`, replace `    return _CURRENT[0]` with

```python
    return current_context().value(slot=CURRENT_INPUT_SLOT).snapshot
```

In `set_current_input`, replace `    _CURRENT[0] = snapshot` with

```python
    current_context().value(slot=CURRENT_INPUT_SLOT).snapshot = snapshot
```

In `reset_current_input`, replace `    _CURRENT[0] = IDLE_INPUT` with

```python
    current_context().value(slot=CURRENT_INPUT_SLOT).snapshot = IDLE_INPUT
```

Check: `grep -nw "_CURRENT" -r src tests` prints nothing.

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff format src/glitchygames/input/state.py tests/input/test_input_state.py
uv run ruff check src/glitchygames/input/state.py tests/input/test_input_state.py
uv run basedpyright src/glitchygames/input/state.py tests/input/test_input_state.py
uv run ty check src/glitchygames/input/state.py tests/input/test_input_state.py
```
Expected: no errors.

- [ ] **Step 5: Run the test, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/input/test_input_state.py -k engine_context`
Expected: `1 passed`.
Run: `uv run pytest --dummy-only --no-cov -q tests/test_clock.py -k imports_alone`
Expected: every door module still imports alone (`11 passed`).
Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/input/state.py tests/input/test_input_state.py
git commit -m "$(cat <<'EOF'
Engine context: the frame's polled input belongs to the context

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 5: The random streams per context (audit C4)

**Files:**
- Modify: `src/glitchygames/randomness.py`
- Modify: `tests/harness.py` (fixture `fresh_random_streams`)
- Test: `tests/test_randomness.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `ENGINE_RANDOM_STATE_SLOT: ContextSlot[EngineRandomState]` (name
  `'glitchygames.randomness.streams'`); `reset_streams(*, seed: int)`, `seed_engine_random(*,
  seed: int | None = None) -> int`, `engine_random_seed() -> int`, `random_stream(name: str) ->
  random.Random`, `numpy_stream(name: str) -> np.random.Generator`, `engine_random()`,
  `capture_stream_states() -> dict[str, Any]`, `restore_stream_states(*, states: dict[str,
  Any]) -> None` unchanged in signature, now per context. `_STATE` is removed.

- [ ] **Step 1: Write the failing tests**

In `tests/test_randomness.py`, add to the imports:

```python
from glitchygames.engine_context import EngineContext
from glitchygames.randomness import NUMPY_STREAM_KIND, RANDOM_STREAM_KIND
```

and add at the end of the file:

```python
# Master seeds of the two contexts below, and the streams they draw from
FIRST_CONTEXT_SEED = 5
SECOND_CONTEXT_SEED = 6
CONTEXT_DRAWS_STREAM = 'tests.context_draws'
CONTEXT_NOISE_STREAM = 'tests.context_noise'
CONTEXT_DRAW_COUNT = 3


def reference_random(*, master_seed: int) -> random.Random:
    """Return the draws stream as a fresh process with this master seed would make it.

    Args:
        master_seed: The master seed.

    Returns:
        A new random.Random.

    """
    return random.Random(
        stream_seed(kind=RANDOM_STREAM_KIND, master_seed=master_seed, name=CONTEXT_DRAWS_STREAM)
    )


def test_each_engine_context_has_its_own_master_seed_and_streams():
    """A seed and its streams in one context are never another's (audit C4)."""
    second = EngineContext(name='second')
    reset_streams(seed=FIRST_CONTEXT_SEED)
    default_stream = random_stream(CONTEXT_DRAWS_STREAM)

    with second.active():
        reset_streams(seed=SECOND_CONTEXT_SEED)
        second_stream = random_stream(CONTEXT_DRAWS_STREAM)
        assert second_stream is not default_stream
        assert engine_random_seed() == SECOND_CONTEXT_SEED

    assert engine_random_seed() == FIRST_CONTEXT_SEED
    assert random_stream(CONTEXT_DRAWS_STREAM) is default_stream


def test_interleaved_draws_in_two_contexts_equal_each_context_drawing_alone():
    """Drawing in turn in two contexts gives each the numbers it would draw on its own."""
    second = EngineContext(name='second')
    reset_streams(seed=FIRST_CONTEXT_SEED)
    with second.active():
        reset_streams(seed=SECOND_CONTEXT_SEED)

    default_draws: list[float] = []
    second_draws: list[float] = []
    default_noise: list[int] = []
    second_noise: list[int] = []
    for _ in range(CONTEXT_DRAW_COUNT):
        default_draws.append(random_stream(CONTEXT_DRAWS_STREAM).random())
        default_noise.append(int(numpy_stream(CONTEXT_NOISE_STREAM).integers(0, 1000)))
        with second.active():
            second_draws.append(random_stream(CONTEXT_DRAWS_STREAM).random())
            second_noise.append(int(numpy_stream(CONTEXT_NOISE_STREAM).integers(0, 1000)))

    default_reference = reference_random(master_seed=FIRST_CONTEXT_SEED)
    second_reference = reference_random(master_seed=SECOND_CONTEXT_SEED)
    assert default_draws == [default_reference.random() for _ in range(CONTEXT_DRAW_COUNT)]
    assert second_draws == [second_reference.random() for _ in range(CONTEXT_DRAW_COUNT)]
    for master_seed, noise in ((FIRST_CONTEXT_SEED, default_noise), (SECOND_CONTEXT_SEED, second_noise)):
        noise_reference = np.random.default_rng(
            stream_seed(kind=NUMPY_STREAM_KIND, master_seed=master_seed, name=CONTEXT_NOISE_STREAM)
        )
        assert noise == [int(noise_reference.integers(0, 1000)) for _ in range(CONTEXT_DRAW_COUNT)]


def test_restoring_stream_states_in_one_context_never_touches_another_contexts_streams():
    """Review Focus 5: a restore works in place, on the current context's streams only."""
    second = EngineContext(name='second')
    reset_streams(seed=FIRST_CONTEXT_SEED)
    default_stream = random_stream(CONTEXT_DRAWS_STREAM)
    default_stream.random()
    default_state_before = default_stream.getstate()
    captured = capture_stream_states()

    with second.active():
        restore_stream_states(states=captured)
        second_stream = random_stream(CONTEXT_DRAWS_STREAM)
        assert second_stream is not default_stream
        assert second_stream.getstate() == default_state_before
        second_stream.random()
        restore_stream_states(states=captured)
        assert random_stream(CONTEXT_DRAWS_STREAM) is second_stream
        assert engine_random_seed() == FIRST_CONTEXT_SEED

    assert random_stream(CONTEXT_DRAWS_STREAM) is default_stream
    assert default_stream.getstate() == default_state_before
```

(`stream_seed`, `random_stream`, `numpy_stream`, `reset_streams`, `engine_random_seed`,
`capture_stream_states`, `restore_stream_states`, `random` and `np` are already imported there.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_randomness.py -k context`
Expected: `3 failed`: each on `assert ... is not ...` (one stream object) or on the draws
(the second context's `reset_streams` reseeded the shared streams).

- [ ] **Step 3: Implement**

In `src/glitchygames/randomness.py`, add after the paragraph of the module docstring that begins
``reset_streams(seed=...)`` sets a new master seed``:

```text
The master seed and the streams belong to the current engine context
(glitchygames.engine_context): each context has its own, made unseeded the first time it draws.
```

Add, after `import numpy as np`:

```python

from glitchygames.engine_context import ContextSlot, current_context
```

Replace

```python
_STATE = EngineRandomState()
```

with

```python
# Each engine context's master seed and streams (glitchygames.engine_context)
ENGINE_RANDOM_STATE_SLOT: ContextSlot[EngineRandomState] = ContextSlot(
    name='glitchygames.randomness.streams', factory=EngineRandomState
)


def _engine_random_state() -> EngineRandomState:
    """Return the current engine context's master seed and streams.

    Returns:
        The state (made unseeded on first read).

    """
    return current_context().value(slot=ENGINE_RANDOM_STATE_SLOT)
```

Then change the bodies (docstrings unchanged) so no `_STATE` remains:

`reset_streams`:
```python
    engine_state = _engine_random_state()
    engine_state.seed = seed
    engine_state.random_streams.clear()
    engine_state.numpy_streams.clear()
```

`engine_random_seed`:
```python
    seed = _engine_random_state().seed
    if seed is None:
        seed = seed_engine_random()
    return seed
```

`random_stream`:
```python
    random_streams = _engine_random_state().random_streams
    generator = random_streams.get(name)
    if generator is None:
        generator = random.Random(
            stream_seed(kind=RANDOM_STREAM_KIND, master_seed=engine_random_seed(), name=name)
        )
        random_streams[name] = generator
    return generator
```

(`engine_random_seed()` may seed the context, whose `reset_streams` clears the same dictionary
object in place, so the new stream is kept, as before.)

`numpy_stream`:
```python
    numpy_streams = _engine_random_state().numpy_streams
    generator = numpy_streams.get(name)
    if generator is None:
        generator = np.random.default_rng(
            stream_seed(kind=NUMPY_STREAM_KIND, master_seed=engine_random_seed(), name=name)
        )
        numpy_streams[name] = generator
    return generator
```

`capture_stream_states`:
```python
    engine_state = _engine_random_state()
    random_states: dict[str, Any] = {}
    for name, generator in engine_state.random_streams.items():
        version, internal_state, gauss_next = generator.getstate()
        random_states[name] = [version, list(internal_state), gauss_next]
    return {
        SEED_STATE_FIELD: engine_state.seed,
        RANDOM_STATES_FIELD: random_states,
        NUMPY_STATES_FIELD: {
            # default_rng's PCG64 state is a dict of Python ints and strings, JSON-safe as is
            name: generator.bit_generator.state
            for name, generator in engine_state.numpy_streams.items()
        },
    }
```

`restore_stream_states`:
```python
    engine_state = _engine_random_state()
    seed: int | None = states[SEED_STATE_FIELD]
    engine_state.seed = seed
    random_states: dict[str, Any] = states[RANDOM_STATES_FIELD]
    numpy_states: dict[str, Any] = states[NUMPY_STATES_FIELD]
    for name in [name for name in engine_state.random_streams if name not in random_states]:
        if seed is None:
            del engine_state.random_streams[name]
        else:
            engine_state.random_streams[name].seed(
                stream_seed(kind=RANDOM_STREAM_KIND, master_seed=seed, name=name)
            )
    for name in [name for name in engine_state.numpy_streams if name not in numpy_states]:
        if seed is None:
            del engine_state.numpy_streams[name]
        else:
            engine_state.numpy_streams[name].bit_generator.state = np.random.default_rng(
                stream_seed(kind=NUMPY_STREAM_KIND, master_seed=seed, name=name)
            ).bit_generator.state
    for name, (version, internal_state, gauss_next) in random_states.items():
        generator = engine_state.random_streams.get(name)
        if generator is None:
            generator = random.Random(RESTORED_STREAM_PLACEHOLDER_SEED)
            engine_state.random_streams[name] = generator
        generator.setstate((version, tuple(internal_state), gauss_next))
    for name, bit_generator_state in numpy_states.items():
        numpy_generator = engine_state.numpy_streams.get(name)
        if numpy_generator is None:
            numpy_generator = np.random.default_rng(RESTORED_STREAM_PLACEHOLDER_SEED)
            engine_state.numpy_streams[name] = numpy_generator
        numpy_generator.bit_generator.state = bit_generator_state
```

Check: `grep -nw "_STATE" -r src tests` prints nothing.

In `tests/harness.py`, replace

```python
@pytest.fixture(autouse=True)
def fresh_random_streams(mocker):
    """Give each test an unseeded set of engine random streams (glitchygames/randomness.py).

    GameEngine and reset_streams() set the process-wide master seed and cache streams; without
    this, one test's seed and half-used streams would carry into the next test on the worker.
    """
    mocker.patch.object(randomness, '_STATE', randomness.EngineRandomState())
```

with

```python
@pytest.fixture(autouse=True)
def fresh_random_streams():
    """Give each test an unseeded set of engine random streams (glitchygames.randomness).

    GameEngine and reset_streams() set the master seed and cache streams in the current engine
    context, the default one for every test (glitchygames.engine_context); without this, one
    test's seed and half-used streams would carry into the next test on the worker.
    """
    default_context().reset_value(slot=randomness.ENGINE_RANDOM_STATE_SLOT)
    yield
    default_context().reset_value(slot=randomness.ENGINE_RANDOM_STATE_SLOT)
```

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff format src/glitchygames/randomness.py tests/test_randomness.py tests/harness.py
uv run ruff check src/glitchygames/randomness.py tests/test_randomness.py tests/harness.py
uv run basedpyright src/glitchygames/randomness.py tests/test_randomness.py tests/harness.py
uv run ty check src/glitchygames/randomness.py tests/test_randomness.py tests/harness.py
```
Expected: no errors.

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_randomness.py`
Expected: every test passes (the three new ones included; the randomness guard scan unchanged).
Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/randomness.py tests/test_randomness.py tests/harness.py
git commit -m "$(cat <<'EOF'
Engine context: the master seed and random streams belong to the context

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 6: The doors, the frame clock and their observers per context (audit C5)

**Files:**
- Modify: `src/glitchygames/sources.py`
- Test: `tests/test_clock.py`

**Interfaces:**
- Consumes: Task 1; Task 5 (the lazily made live doors read `engine_random_seed()` of the
  current context).
- Produces: `SOURCES_REGISTRY_SLOT: ContextSlot[_SourcesRegistry]` (name
  `'glitchygames.sources.registry'`); every public function of `glitchygames.sources`
  (`active_sources`, `install_sources`, `push_scoped_sources`, `pop_scoped_sources`,
  `has_scoped_sources`, `redeliver_events`, `pending_redelivered_events`,
  `take_redelivered_events`, `discard_scope_posts`, `without_discarded_scope_posts`,
  `mark_frames_started`, `advance_frame_clock`, `set_frame_clock_seconds`,
  `frame_clock_seconds`, the observe/stop/notify functions, `reset_sources`) unchanged in
  signature, now per context. `_REGISTRY` is removed. `glitchygames.clock` is unchanged (it reads
  through these functions).

- [ ] **Step 1: Write the failing tests**

In `tests/test_clock.py`, add to the imports:

```python
import pygame

from glitchygames.engine_context import EngineContext
from glitchygames.input.devices import JOYSTICK_COUNT_CALL, EnumerationAnswer
from glitchygames.randomness import seed_engine_random
from glitchygames.sources import (
    SourcesAlreadyRunningError,
    active_sources,
    has_scoped_sources,
    mark_frames_started,
    notify_device_answer,
    notify_save_store_opened,
    observe_device_answers,
    observe_save_store_openings,
    pending_redelivered_events,
    push_scoped_sources,
    redeliver_events,
    reset_sources,
)
from glitchygames.state import MemorySaveManager
```

(merge them with the existing `from glitchygames.sources import advance_frame_clock,
install_sources`; `ruff check --select I --fix` orders the block) and add at the end of the file:

```python
# Master seeds of the contexts' doors below
DEFAULT_DOORS_SEED = 11
SECOND_DOORS_SEED = 22


class HeardAnswers:
    """Keeps every save-store opening and device answer it is told of."""

    def __init__(self) -> None:
        """Start having heard nothing."""
        self.save_namespaces: list[str] = []
        self.device_answers: list[EnumerationAnswer] = []

    def on_save_store_opened(self, *, namespace, store) -> None:
        """Keep the namespace."""
        self.save_namespaces.append(namespace)

    def on_device_answer(self, *, answer, opened) -> None:
        """Keep the answer."""
        self.device_answers.append(answer)


def test_each_engine_context_has_its_own_doors_frame_clock_and_held_events():
    """Doors, frames started, the frame clock and held events are per context (audit C5)."""
    second = EngineContext(name='second')
    default_doors = LiveSources(random_seed=DEFAULT_DOORS_SEED)
    install_sources(sources=default_doors)
    advance_frame_clock(seconds=0.25)
    mark_frames_started()
    redeliver_events(events=[(pygame.event.Event(pygame.USEREVENT, code=1), 'internal')])

    with second.active():
        assert clock.frame_clock_seconds() == 0.0
        assert pending_redelivered_events() == []
        # This context's frames have not started, whatever the default context's did
        second_doors = LiveSources(random_seed=SECOND_DOORS_SEED)
        install_sources(sources=second_doors)
        push_scoped_sources(sources=FixedClockSources(random_seed=SECOND_DOORS_SEED))
        assert has_scoped_sources()
        advance_frame_clock(seconds=1.0)

    assert active_sources() is default_doors
    assert not has_scoped_sources()
    assert clock.frame_clock_seconds() == 0.25
    assert [event.code for event, _origin in pending_redelivered_events()] == [1]
    with pytest.raises(SourcesAlreadyRunningError):
        install_sources(sources=LiveSources(random_seed=DEFAULT_DOORS_SEED))
    with second.active():
        assert has_scoped_sources()
        assert clock.frame_clock_seconds() == 1.0
        reset_sources()
        assert active_sources() is not second_doors


def test_a_contexts_first_live_doors_take_that_contexts_master_seed():
    """Review Focus 5: doors made on first use read the master seed of their own context."""
    second = EngineContext(name='second')
    seed_engine_random(seed=DEFAULT_DOORS_SEED)

    with second.active():
        seed_engine_random(seed=SECOND_DOORS_SEED)
        assert active_sources().random_seed == SECOND_DOORS_SEED
        reset_sources()

    assert active_sources().random_seed == DEFAULT_DOORS_SEED


def test_observers_hear_only_their_own_contexts_openings_and_answers():
    """A save-store or device-answer observer is told only of its own context's."""
    second = EngineContext(name='second')
    heard = HeardAnswers()
    observe_save_store_openings(observer=heard)
    observe_device_answers(observer=heard)
    answer = EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=1)

    with second.active():
        notify_save_store_opened(
            namespace='second-game', store=MemorySaveManager(app_name='second-game', snapshot={})
        )
        notify_device_answer(answer=answer, opened=None)
    notify_save_store_opened(
        namespace='default-game', store=MemorySaveManager(app_name='default-game', snapshot={})
    )
    notify_device_answer(answer=answer, opened=None)

    assert heard.save_namespaces == ['default-game']
    assert heard.device_answers == [answer]
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_clock.py -k context`
Expected: `2 failed, 1 passed`: `assert 0.25 == 0.0` (one frame clock) and
`assert ['second-game', 'default-game'] == ['default-game']` (one set of observers). The seed test
already passes (the random streams moved in Task 5 and the shared registry was empty); it pins
the cross-slot rule once the registry moves.

- [ ] **Step 3: Implement**

In `src/glitchygames/sources.py`, replace in the module docstring

```text
The registry is module state, like glitchygames/randomness.py's streams, so engine code, games
and widgets reach the active sources without an engine reference. ``install_sources`` may only be
called before the first frame (a run never mixes live and recorded input); in-game playback pushes
```

with

```text
The registry belongs to the current engine context (glitchygames.engine_context), like
glitchygames.randomness's streams, so engine code, games and widgets reach the active sources
without an engine reference, and each context has its own doors, frame clock, held events and
observers. ``install_sources`` may only be called before the context's first frame (a run never
mixes live and recorded input); in-game playback pushes
```

and in its last paragraph replace `it imports no package module at module level except
glitchygames.randomness.` (wrapped after `except` in the file) with `it imports no package module at module level except
glitchygames.randomness and glitchygames.engine_context (both leaves).`

Add, after `from glitchygames.randomness import engine_random_seed`:

```python
from glitchygames.engine_context import ContextSlot, current_context
```

(ruff orders it before `glitchygames.randomness`.)

Replace

```python
_REGISTRY = _SourcesRegistry()
```

with

```python
# Each engine context's doors, frame clock, held events and observers
# (glitchygames.engine_context)
SOURCES_REGISTRY_SLOT: ContextSlot[_SourcesRegistry] = ContextSlot(
    name='glitchygames.sources.registry', factory=_SourcesRegistry
)


def _registry() -> _SourcesRegistry:
    """Return the current engine context's registry.

    Returns:
        The registry (made empty on first read).

    """
    return current_context().value(slot=SOURCES_REGISTRY_SLOT)
```

Then every function reads `_registry()` instead of `_REGISTRY`, bound once to `registry` where it
is used more than once. The bodies (docstrings and comments unchanged):

`active_sources`:
```python
    registry = _registry()
    if registry.scoped:
        return registry.scoped[-1]
    if registry.installed is None:
        # (the existing comment above the import, unchanged)
        from glitchygames.live_sources import LiveSources

        registry.installed = LiveSources(random_seed=engine_random_seed())
    return registry.installed
```

`install_sources`:
```python
    registry = _registry()
    if registry.frames_started:
        message = 'install_sources() is allowed only before the first frame'
        raise SourcesAlreadyRunningError(message)
    if registry.installed is sources:
        message = 'install_sources() was given the sources that are already installed'
        raise SourcesAlreadyInstalledError(message)
    if registry.installed is not None:
        registry.installed.on_uninstalled()
    registry.installed = sources
    sources.on_installed()
```

`push_scoped_sources`:
```python
    registry = _registry()
    if sources is registry.installed or any(
        scoped_sources is sources for scoped_sources in registry.scoped
    ):
        message = 'push_scoped_sources() was given sources that are already in use'
        raise SourcesAlreadyInstalledError(message)
    sources.on_installed()
    registry.scoped.append(sources)
```

`pop_scoped_sources`:
```python
    registry = _registry()
    if not registry.scoped:
        message = 'pop_scoped_sources() was called with no scoped sources pushed'
        raise NoScopedSourcesError(message)
    sources = registry.scoped.pop()
    sources.on_uninstalled()
    return sources
```

`has_scoped_sources`: `    return bool(_registry().scoped)`

`redeliver_events`: `    _registry().redelivered_events.extend(events)`

`pending_redelivered_events`: `    return list(_registry().redelivered_events)`

`take_redelivered_events`:
```python
    registry = _registry()
    events = list(registry.redelivered_events)
    registry.redelivered_events.clear()
    return events
```

`discard_scope_posts`: `    _registry().discarded_scope_posts.extend(posts)`

`without_discarded_scope_posts` (the loop after these lines unchanged):
```python
    registry = _registry()
    if not registry.discarded_scope_posts:
        return events
    discarded_posts = list(registry.discarded_scope_posts)
    registry.discarded_scope_posts.clear()
```

`mark_frames_started`: `    _registry().frames_started = True`

`advance_frame_clock`: `    _registry().frame_clock_seconds += seconds`

`observe_save_store_openings`: `    _registry().save_store_observers.add(observer)`

`stop_observing_save_store_openings`: `    _registry().save_store_observers.discard(observer)`

`notify_save_store_opened` (comment unchanged):
```python
    for observer in list(_registry().save_store_observers):
        observer.on_save_store_opened(namespace=namespace, store=store)
```

`observe_device_answers`: `    _registry().device_answer_observers.add(observer)`

`stop_observing_device_answers`: `    _registry().device_answer_observers.discard(observer)`

`notify_device_answer` (comment unchanged):
```python
    for observer in list(_registry().device_answer_observers):
        observer.on_device_answer(answer=answer, opened=opened)
```

`set_frame_clock_seconds`: `    _registry().frame_clock_seconds = seconds`

`frame_clock_seconds`: `    return _registry().frame_clock_seconds`

`reset_sources` (its docstring's first line becomes `Forget the current engine context's
installed and scoped sources and frame clock (a new run, or a test).`):
```python
    registry = _registry()
    for sources in [*registry.scoped, registry.installed]:
        if sources is not None:
            sources.on_uninstalled()
    registry.installed = None
    registry.scoped.clear()
    registry.frames_started = False
    registry.frame_clock_seconds = 0.0
    registry.redelivered_events.clear()
    registry.discarded_scope_posts.clear()
    registry.save_store_observers.clear()
    registry.device_answer_observers.clear()
```

Check: `grep -n "_REGISTRY" src/glitchygames/sources.py` prints nothing.

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff check --select I --fix tests/test_clock.py src/glitchygames/sources.py
uv run ruff format src/glitchygames/sources.py tests/test_clock.py
uv run ruff check src/glitchygames/sources.py tests/test_clock.py
uv run basedpyright src/glitchygames/sources.py tests/test_clock.py
uv run ty check src/glitchygames/sources.py tests/test_clock.py
```
Expected: no errors.

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_clock.py`
Expected: every test passes (the three new ones and every door module importing alone).
Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/sources.py tests/test_clock.py
git commit -m "$(cat <<'EOF'
Engine context: the doors, the frame clock and their observers belong to the context

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 7: The SceneManager singleton per context (audit C6)

**Files:**
- Modify: `src/glitchygames/scenes/scene.py`
- Test: `tests/scenes/test_scene_manager.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `SCENE_MANAGERS_SLOT: ContextSlot[dict[type[SceneManager], SceneManager | None]]`
  (name `'glitchygames.scenes.scene.scene_managers'`); `SceneManager()` returns the current
  context's manager of that class; `SceneManager._reset()` resets it in the current context.
  `SceneManager._instance` is removed. `SceneManager.OPTIONS` stays a class attribute (audit
  C7, sub-plan 2).

- [ ] **Step 1: Write the tests**

In `tests/scenes/test_scene_manager.py`, add to the imports:

```python
from glitchygames.engine_context import EngineContext
```

and add at the end of the file:

```python
class SubclassedSceneManager(SceneManager):
    """A scene manager subclass (tests/world/test_finish_frame.py makes one too)."""


def test_each_engine_context_has_its_own_scene_manager():
    """SceneManager() is one per context; resetting one never touches another's (audit C6)."""
    second = EngineContext(name='second')
    default_manager = SceneManager()
    default_manager.frame_number = 7

    with second.active():
        second_manager = SceneManager()
        assert second_manager is not default_manager
        assert second_manager.frame_number == 0
        assert SceneManager() is second_manager
        SceneManager._reset()
        assert SceneManager() is not second_manager

    assert SceneManager() is default_manager
    assert default_manager.frame_number == 7
    assert default_manager._initialized


def test_a_scene_manager_subclass_keeps_the_singleton_rules_of_the_class_attribute():
    """Review Focus 4: the class attribute's inherited lookup, kept exactly.

    A subclass with no entry of its own answers with its base class's manager; its _reset()
    uninitializes the manager it answered with and gives it an entry of its own (None).
    """
    base_manager = SceneManager()
    assert SubclassedSceneManager() is base_manager

    SubclassedSceneManager._reset()
    assert not base_manager._initialized
    subclass_manager = SubclassedSceneManager()
    assert type(subclass_manager) is SubclassedSceneManager
    assert SceneManager() is base_manager
    assert base_manager._initialized

    SubclassedSceneManager._reset()
    assert not subclass_manager._initialized
    assert base_manager._initialized
    assert SceneManager() is base_manager
    assert SubclassedSceneManager() is not subclass_manager
    SubclassedSceneManager._reset()
```

- [ ] **Step 2: Run them**

Run: `uv run pytest --dummy-only --no-cov -q tests/scenes/test_scene_manager.py -k "engine_context or subclass"`
Expected: `1 failed, 1 passed`: the first fails on `assert second_manager is not
default_manager` (one singleton per process); the subclass test passes, pinning today's rules.

- [ ] **Step 3: Implement**

In `src/glitchygames/scenes/scene.py`, add after `from glitchygames.effects.tween import
TweenManager`:

```python
from glitchygames.engine_context import ContextSlot, current_context
```

Add, between the end of `required_scene` and `class SceneManager(SceneInterface,
events.EventManager):`:

```python
def _no_scene_managers() -> dict[type[SceneManager], SceneManager | None]:
    """Return an engine context's scene managers before any is made: none.

    Returns:
        An empty dict.

    """
    return {}


# Each engine context's scene managers, by the class constructed (glitchygames.engine_context).
# A class answers with its own entry, else its nearest base class's along its MRO, as the class
# attribute SceneManager._instance it replaces did (a subclass without an entry of its own got
# its base class's manager)
SCENE_MANAGERS_SLOT: ContextSlot[dict[type[SceneManager], SceneManager | None]] = ContextSlot(
    name='glitchygames.scenes.scene.scene_managers', factory=_no_scene_managers
)


def _scene_manager_for_class(*, scene_manager_class: type[SceneManager]) -> SceneManager | None:
    """Return the current context's manager for a class, looked up along its MRO.

    The first class of the MRO with an entry decides, even when the entry is None.

    Args:
        scene_manager_class: The class constructed (SceneManager or a subclass).

    Returns:
        The manager, or None when there is none yet.

    """
    scene_managers = current_context().value(slot=SCENE_MANAGERS_SLOT)
    for base_class in scene_manager_class.__mro__:
        if issubclass(base_class, SceneManager) and base_class in scene_managers:
            return scene_managers[base_class]
    return None
```

In `class SceneManager`, delete the line

```python
    _instance: ClassVar[SceneManager | None] = None
```

and replace

```python
    def __new__(cls) -> Self:
        """Create a new instance or return the existing singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value] # ty: ignore[invalid-return-type]
```

with

```python
    def __new__(cls) -> Self:
        """Return this engine context's scene manager of this class, made on first use."""
        instance = _scene_manager_for_class(scene_manager_class=cls)
        if instance is None:
            instance = super().__new__(cls)
            current_context().value(slot=SCENE_MANAGERS_SLOT)[cls] = instance
        return cast('Self', instance)
```

and replace

```python
        Clears the singleton instance so the next call to SceneManager()
        creates a freshly initialized instance. This should only be used
        in tests.
        """
        instance = cls._instance
        if instance is not None:
            instance._initialized = False
        cls._instance = None
```

with

```python
        Clears the singleton instance of the current engine context so the next call to
        SceneManager() there creates a freshly initialized instance. This should only be used
        in tests.
        """
        instance = _scene_manager_for_class(scene_manager_class=cls)
        if instance is not None:
            instance._initialized = False
        current_context().value(slot=SCENE_MANAGERS_SLOT)[cls] = None
```

Check: `grep -n "_instance\b" src/glitchygames/scenes/scene.py` prints nothing.

- [ ] **Step 4: Lint**

Run:
```bash
uv run ruff format src/glitchygames/scenes/scene.py tests/scenes/test_scene_manager.py
uv run ruff check src/glitchygames/scenes/scene.py tests/scenes/test_scene_manager.py
uv run basedpyright src/glitchygames/scenes/scene.py tests/scenes/test_scene_manager.py
uv run ty check src/glitchygames/scenes/scene.py tests/scenes/test_scene_manager.py
```
Expected: no errors (in particular no `reportUnnecessaryCast` and no `invalid-return-type`; if
either checker refuses `cast('Self', instance)`, stop and report: the plan allows no new ignore).

- [ ] **Step 5: Run the tests, then the suite**

Run: `uv run pytest --dummy-only --no-cov -q tests/scenes/test_scene_manager.py tests/world/test_finish_frame.py`
Expected: every test passes (both new ones; the subclass scene manager of
`tests/world/test_finish_frame.py` unchanged).
Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 6: Commit**

```bash
git add src/glitchygames/scenes/scene.py tests/scenes/test_scene_manager.py
git commit -m "$(cat <<'EOF'
Engine context: the SceneManager singleton is one per context

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: the hook measures and stages its rows.

---

### Task 8: Two contexts in one process, no state leaks

**Files:**
- Test: `tests/test_engine_context.py` (append)

**Interfaces:**
- Consumes: every slot of Tasks 2-7; `called_name` (Task 1);
  `glitchygames.state.open_saves(*, app_name: str) -> SaveManager`; `MemorySaveManager(*,
  app_name: str, snapshot: dict[str, dict[str, Any]])`; `LiveSources(*, random_seed: int)`.
- Produces: `ISOLATION_CHECKS: dict[str, Callable[..., None]]` (slot name to its check),
  `declared_slot_names_in_source(*, source_path: Path) -> list[str]`, the stand-in doors
  `MemorySavesSources`.

- [ ] **Step 1: Write the tests**

In `tests/test_engine_context.py`, add to the imports:

```python
from typing import Any, override

import pygame

from glitchygames.backgrounds import (
    DEFAULT_BACKGROUND_PATTERN,
    BackgroundPattern,
    active_default_background_pattern,
    set_active_default_background_pattern,
)
from glitchygames.input.state import IDLE_INPUT, InputSnapshot, current_input, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.pixel_snap import (
    PixelSnapMode,
    active_default_snap_mode,
    set_active_default_snap_mode,
)
from glitchygames.randomness import (
    RANDOM_STREAM_KIND,
    engine_random_seed,
    random_stream,
    reset_streams,
    seed_engine_random,
    stream_seed,
)
from glitchygames.scenes import SceneManager
from glitchygames.sources import (
    SourcesAlreadyRunningError,
    active_sources,
    advance_frame_clock,
    frame_clock_seconds,
    install_sources,
    mark_frames_started,
    pending_redelivered_events,
    redeliver_events,
    reset_sources,
)
from glitchygames.state import MemorySaveManager, SaveManager, open_saves
```

and, under `if TYPE_CHECKING:`, `from collections.abc import Callable, Iterator` (replacing the
`Iterator` import there). Add `import random` to the standard-library imports. Then append:

```python
# The two stand-in games' master seeds, and what each holds
FIRST_SEED = 1
SECOND_SEED = 2
DRAWS_STREAM = 'tests.engine_context.draws'
STAND_IN_GAME = 'stand-in-game'
SAVE_SLOT = 'progress'
# SDL scancodes of Space and Return
SPACE_SCANCODE = 44
RETURN_SCANCODE = 40
# Engine slot names start with the engine's package name (this file's own slot does not)
ENGINE_SLOT_PREFIX = 'glitchygames.'


class MemorySavesSources(LiveSources):
    """Live doors whose saves stay in memory, so no test touches the player's save files."""

    def __init__(self, *, random_seed: int) -> None:
        """Make the doors with no stores open.

        Args:
            random_seed: The master seed they report.

        """
        super().__init__(random_seed=random_seed)
        self.memory_stores: dict[str, MemorySaveManager] = {}

    @override
    def saves(self, *, namespace: str) -> SaveManager:
        """Return the in-memory store for ``namespace``, made empty on first use."""
        store = self.memory_stores.get(namespace)
        if store is None:
            store = MemorySaveManager(app_name=namespace, snapshot={})
            self.memory_stores[namespace] = store
        return store


def snapshot_holding(*, scancode: int) -> InputSnapshot:
    """Return a snapshot with one key held and the mouse idle.

    Args:
        scancode: The SDL scancode held.

    Returns:
        The snapshot.

    """
    return InputSnapshot(
        pressed_scancodes=frozenset({scancode}),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
    )


def check_default_snap_mode(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own default snap mode, and the default context its own."""
    default_mode = active_default_snap_mode()
    with first.active():
        set_active_default_snap_mode(mode=PixelSnapMode.FLOOR)
    with second.active():
        assert active_default_snap_mode() is PixelSnapMode.NEAREST_HALF_UP
        set_active_default_snap_mode(mode=PixelSnapMode.CEIL)
    with first.active():
        assert active_default_snap_mode() is PixelSnapMode.FLOOR
    with second.active():
        assert active_default_snap_mode() is PixelSnapMode.CEIL
    assert active_default_snap_mode() is default_mode


def check_default_background(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own default background, and the default context its own."""
    default_pattern = active_default_background_pattern()
    with first.active():
        set_active_default_background_pattern(pattern=BackgroundPattern.CHANNEL_THREE)
    with second.active():
        assert active_default_background_pattern() is DEFAULT_BACKGROUND_PATTERN
    with first.active():
        assert active_default_background_pattern() is BackgroundPattern.CHANNEL_THREE
    assert active_default_background_pattern() is default_pattern


def check_current_input(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own polled input, and the default context its own."""
    default_snapshot = current_input()
    with first.active():
        set_current_input(snapshot=snapshot_holding(scancode=SPACE_SCANCODE))
    with second.active():
        assert current_input() is IDLE_INPUT
        set_current_input(snapshot=snapshot_holding(scancode=RETURN_SCANCODE))
    with first.active():
        assert current_input().pressed_scancodes == frozenset({SPACE_SCANCODE})
    with second.active():
        assert current_input().pressed_scancodes == frozenset({RETURN_SCANCODE})
    assert current_input() is default_snapshot


def check_random_streams(*, first: EngineContext, second: EngineContext) -> None:
    """Each context draws its own numbers, as it would alone, and the default keeps its seed."""
    default_seed = engine_random_seed()
    with first.active():
        reset_streams(seed=FIRST_SEED)
        first_draw = random_stream(DRAWS_STREAM).random()
    with second.active():
        reset_streams(seed=SECOND_SEED)
        second_draw = random_stream(DRAWS_STREAM).random()
    with first.active():
        assert engine_random_seed() == FIRST_SEED
        following_first_draw = random_stream(DRAWS_STREAM).random()
    first_reference = random.Random(
        stream_seed(kind=RANDOM_STREAM_KIND, master_seed=FIRST_SEED, name=DRAWS_STREAM)
    )
    second_reference = random.Random(
        stream_seed(kind=RANDOM_STREAM_KIND, master_seed=SECOND_SEED, name=DRAWS_STREAM)
    )
    assert [first_draw, following_first_draw] == [first_reference.random(), first_reference.random()]
    assert second_draw == second_reference.random()
    assert engine_random_seed() == default_seed


def check_doors_and_frame_clock(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own doors, frames started, frame clock and held events."""
    default_doors = active_sources()
    default_clock = frame_clock_seconds()
    with first.active():
        first_doors = MemorySavesSources(random_seed=FIRST_SEED)
        install_sources(sources=first_doors)
        advance_frame_clock(seconds=0.5)
        mark_frames_started()
        redeliver_events(events=[(pygame.event.Event(pygame.USEREVENT, code=FIRST_SEED), 'internal')])
    with second.active():
        assert frame_clock_seconds() == 0.0
        assert pending_redelivered_events() == []
        second_doors = MemorySavesSources(random_seed=SECOND_SEED)
        install_sources(sources=second_doors)
        advance_frame_clock(seconds=2.0)
    with first.active():
        assert active_sources() is first_doors
        assert frame_clock_seconds() == 0.5
        assert [event.code for event, _origin in pending_redelivered_events()] == [FIRST_SEED]
        with pytest.raises(SourcesAlreadyRunningError):
            install_sources(sources=MemorySavesSources(random_seed=FIRST_SEED))
        reset_sources()
    with second.active():
        assert active_sources() is second_doors
        assert frame_clock_seconds() == 2.0
        reset_sources()
    assert active_sources() is default_doors
    assert frame_clock_seconds() == default_clock


def check_scene_managers(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own scene manager, and the default context its own."""
    default_manager = SceneManager()
    with first.active():
        first_manager = SceneManager()
        first_manager.frame_number = FIRST_SEED
    with second.active():
        second_manager = SceneManager()
        assert second_manager is not first_manager
        assert second_manager.frame_number == 0
    with first.active():
        assert SceneManager() is first_manager
        assert first_manager.frame_number == FIRST_SEED
    assert SceneManager() is default_manager
    assert default_manager is not first_manager
    assert default_manager is not second_manager


# Every engine slot, with the check that proves its values never leak between contexts
ISOLATION_CHECKS: dict[str, Callable[..., None]] = {
    'glitchygames.pixel_snap.default_mode': check_default_snap_mode,
    'glitchygames.backgrounds.default_pattern': check_default_background,
    'glitchygames.input.state.current_input': check_current_input,
    'glitchygames.randomness.streams': check_random_streams,
    'glitchygames.sources.registry': check_doors_and_frame_clock,
    'glitchygames.scenes.scene.scene_managers': check_scene_managers,
}


def declared_slot_names_in_source(*, source_path: Path) -> list[str]:
    """Return the name of every ContextSlot a file declares.

    Args:
        source_path: A Python file.

    Returns:
        The names, in source order.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    names: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and called_name(node) == 'ContextSlot'):
            continue
        name_values = [keyword.value for keyword in node.keywords if keyword.arg == 'name']
        assert len(name_values) == 1, f'{source_path}:{node.lineno}: a ContextSlot needs name='
        name_value = name_values[0]
        assert isinstance(name_value, ast.Constant), (
            f'{source_path}:{node.lineno}: a ContextSlot name must be a string literal'
        )
        assert isinstance(name_value.value, str), (
            f'{source_path}:{node.lineno}: a ContextSlot name must be a string literal'
        )
        names.append(name_value.value)
    return names


def engine_slot_names() -> set[str]:
    """Return the name of every slot the engine and the workspace members declare.

    Returns:
        The names.

    """
    return {
        name
        for _allowlist_key, path in scanned_source_files(project_root=PROJECT_ROOT)
        for name in declared_slot_names_in_source(source_path=path)
    }


def test_every_engine_slot_has_an_isolation_check():
    """A slot added without a check here fails (every piece of state moved is proven)."""
    assert engine_slot_names() == set(ISOLATION_CHECKS)


def test_the_slot_scan_agrees_with_the_slots_declared_at_run_time():
    """The scan misses no slot: every engine slot declared at run time is in it."""
    declared_engine_slot_names = {
        slot.name
        for slot in declared_context_slots()
        if slot.name.startswith(ENGINE_SLOT_PREFIX)
    }

    assert declared_engine_slot_names == engine_slot_names()


@pytest.mark.parametrize('slot_name', sorted(ISOLATION_CHECKS))
def test_no_slot_value_leaks_between_two_contexts(slot_name):
    """Two contexts beside the default one: each keeps its own value of the slot."""
    ISOLATION_CHECKS[slot_name](
        first=EngineContext(name='first'), second=EngineContext(name='second')
    )


def test_two_contexts_hold_two_games_worth_of_state_without_leaking():
    """Two stand-in games set up side by side keep every piece apart, saves included."""
    games: list[dict[str, Any]] = [
        {
            'context': EngineContext(name='first game'),
            'seed': FIRST_SEED,
            'snap_mode': PixelSnapMode.FLOOR,
            'pattern': BackgroundPattern.CHANNEL_THREE,
            'scancode': SPACE_SCANCODE,
        },
        {
            'context': EngineContext(name='second game'),
            'seed': SECOND_SEED,
            'snap_mode': PixelSnapMode.CEIL,
            'pattern': BackgroundPattern.TEST_PATTERN,
            'scancode': RETURN_SCANCODE,
        },
    ]
    default_manager = SceneManager()
    default_clock = frame_clock_seconds()

    for game in games:
        with game['context'].active():
            seed_engine_random(seed=game['seed'])
            install_sources(sources=MemorySavesSources(random_seed=game['seed']))
            set_active_default_snap_mode(mode=game['snap_mode'])
            set_active_default_background_pattern(pattern=game['pattern'])
            set_current_input(snapshot=snapshot_holding(scancode=game['scancode']))
            SceneManager().frame_number = game['seed'] * 100
            open_saves(app_name=STAND_IN_GAME).save(slot_name=SAVE_SLOT, data={'seed': game['seed']})
            advance_frame_clock(seconds=game['seed'] * 0.5)

    for game in games:
        with game['context'].active():
            assert engine_random_seed() == game['seed']
            assert active_sources().random_seed == game['seed']
            assert active_default_snap_mode() is game['snap_mode']
            assert active_default_background_pattern() is game['pattern']
            assert current_input().pressed_scancodes == frozenset({game['scancode']})
            assert SceneManager().frame_number == game['seed'] * 100
            assert open_saves(app_name=STAND_IN_GAME).load(slot_name=SAVE_SLOT) == {
                'seed': game['seed']
            }
            assert frame_clock_seconds() == game['seed'] * 0.5
            reset_sources()

    assert SceneManager() is default_manager
    assert frame_clock_seconds() == default_clock
    assert current_input() is IDLE_INPUT
```

- [ ] **Step 2: Lint**

Run:
```bash
uv run ruff check --select I --fix tests/test_engine_context.py
uv run ruff format tests/test_engine_context.py
uv run ruff check tests/test_engine_context.py
uv run basedpyright tests/test_engine_context.py
uv run ty check tests/test_engine_context.py
```
Expected: no errors.

- [ ] **Step 3: Run the tests**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_engine_context.py`
Expected: `25 passed` (16 from Task 1, 2 completeness tests, 6 parametrized checks, 1 two-game
test). These pass at once because Tasks 2-7 moved the state; to see the guard bite, delete
`'glitchygames.scenes.scene.scene_managers'` from `ISOLATION_CHECKS` temporarily: Expected
`test_every_engine_slot_has_an_isolation_check` fails naming it; put it back.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest --dummy-only`
Expected: every test passes, coverage 100%.

- [ ] **Step 5: Commit**

```bash
git add tests/test_engine_context.py
git commit -m "$(cat <<'EOF'
Engine context: two contexts in one process keep every piece of moved state apart

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```
Expected: no measuring (no measured path changed); the commit holds the one file.

---

### Task 9: Documentation

**Files:**
- Create: `docs/architecture/engine_context.md`
- Modify: `mkdocs.yml`, `CLAUDE.md`, `plans/2026-10-25-engine-context.md`,
  `plans/future-features.md`

**Interfaces:**
- Consumes: Tasks 1-8 as built.
- Produces: documentation only.

- [ ] **Step 1: Write the architecture page**

Create `docs/architecture/engine_context.md`:

```markdown
# Engine Context

An engine context is the state one running game owns, so several games can run in one process
(the Arcade's demo tiles; design: `plans/2026-10-25-engine-context.md`). Ordinary games never
create one: they run in the default context, exactly as before.

## Rules

1. Per-context state is a `ContextSlot` (`src/glitchygames/engine_context.py`), declared once at
   module level with a unique dotted name and a factory.
2. Code reads a slot when it needs it, `current_context().value(slot=...)`, never as its module
   is imported: the test suite scans the engine and every workspace member for such reads.
3. A context makes each value with the slot's factory the first time it is read there.
4. `current_context()` is the context switched to last in this thread or asyncio task, else the
   default context.
5. `with context.active():` makes a context current and puts the previous one back when the
   block ends, also by an exception; switches nest. An asyncio task made inside a switch keeps
   it, a switch held across an `await` is never seen by another task, and a thread sees it only
   when started with `context=contextvars.copy_context()`.
6. A context owns only what its slots hold. The display, the mixer, SDL's event queue and the
   joystick subsystem are one per process.

## What belongs to a context today

| Slot | Module | Public functions |
|---|---|---|
| `glitchygames.pixel_snap.default_mode` | `src/glitchygames/pixel_snap.py` | `set_active_default_snap_mode`, `active_default_snap_mode`, `resolve_snap_mode` |
| `glitchygames.backgrounds.default_pattern` | `src/glitchygames/backgrounds.py` | `set_active_default_background_pattern`, `active_default_background_pattern`, `paint_default_background` |
| `glitchygames.input.state.current_input` | `src/glitchygames/input/state.py` | `current_input`, `set_current_input`, `reset_current_input` |
| `glitchygames.randomness.streams` | `src/glitchygames/randomness.py` | `random_stream`, `numpy_stream`, `reset_streams`, `seed_engine_random`, `engine_random_seed`, `capture_stream_states`, `restore_stream_states` |
| `glitchygames.sources.registry` | `src/glitchygames/sources.py` | `active_sources`, `install_sources`, the scoped sources, the frame clock, held events, observers |
| `glitchygames.scenes.scene.scene_managers` | `src/glitchygames/scenes/scene.py` | `SceneManager()`, `SceneManager._reset()` |

`tests/test_engine_context.py` proves, for every slot, that two contexts in one process never
see each other's values; a slot added without such a check fails the suite.
```

- [ ] **Step 2: Add the nav entry**

In `mkdocs.yml`, after the line
`    - Gameplay Recording and Replay: "architecture/gameplay_replay.md"`, add:

```yaml
    - Engine Context: "architecture/engine_context.md"
```

- [ ] **Step 3: CLAUDE.md**

Insert before the line that begins `**Source revision** (`:

```markdown
**Engine Context** (`src/glitchygames/engine_context.py`; design `plans/2026-10-25-engine-context.md`)
- The state one running game owns, so several games can run in one process (the Arcade's demo
  tiles). Ordinary games never create one and run in the default context
  (`default_context()`), exactly as before
- Per-context state is a `ContextSlot(name=..., factory=...)` declared once at module level in
  the module that owns it; code reads `current_context().value(slot=...)` when it needs it,
  never at import (`tests/test_engine_context.py` scans the engine and every member)
- `with context.active():` switches (a `contextvars.ContextVar`: per thread and asyncio task;
  nests; restores on exceptions). Slots today: the default snap mode, the default background,
  the polled input, the random streams, the doors with the frame clock and observers, and the
  `SceneManager` singleton; each has an isolation check in `tests/test_engine_context.py`
  (`ISOLATION_CHECKS`), and a slot without one fails the suite
- The harness fails a test that leaves another context current
  (`every_test_ends_in_the_default_engine_context`)

```

Replace

```markdown
  random seed only through the active `EngineSources`. `src/glitchygames/sources.py` is the leaf
  registry: `active_sources()`, `install_sources(sources=...)` (only before the first frame,
```

with

```markdown
  random seed only through the active `EngineSources`. `src/glitchygames/sources.py` is the leaf
  registry (one per engine context): `active_sources()`, `install_sources(sources=...)` (only
  before the context's first frame,
```

and replace `- **Singleton**: `SceneManager`, `FontManager`` with
`- **Singleton**: `SceneManager` (one per engine context), `FontManager``.

- [ ] **Step 4: Statuses**

In `plans/2026-10-25-engine-context.md`, replace the first paragraph's
`Status: PLANNED (written 2026-10-25), not started.` with `Status: IN PROGRESS. Sub-plan 1
(State) DONE on feature/engine-context-1-state, verified by its Task 10.`, followed by the range
of the branch's commits as `git log --oneline main..HEAD` prints them (oldest..newest hash).

In `plans/future-features.md`, entry 43, replace `  First sub-plan: the engine context (one
per demo player)` with `  First sub-plan: the engine context (one per demo player); its sub-plan
1 (state: EngineContext, the default context, six pieces of state moved) is done`.

- [ ] **Step 5: Check the docs**

Run: `uv run pytest --dummy-only --no-cov -q tests/test_suite_collection.py -k living_documentation`
Expected: passes (every path in the living documentation is written from the repository root).
Run: `nox -s lint-docs`
Expected: the strict mkdocs build succeeds.

- [ ] **Step 6: Commit**

```bash
git add docs/architecture/engine_context.md mkdocs.yml CLAUDE.md plans/2026-10-25-engine-context.md plans/future-features.md
git commit -m "$(cat <<'EOF'
Docs: the engine context (rules, slots, isolation checks)

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Whole-branch verification

**Files:** none changed (a failure here is fixed in the task that owns it, then this task runs
again from Step 1).

- [ ] **Step 1: Lint everything**

Run: `nox -s lint`
Expected: every lint session succeeds (code, docs, YAML, TOML, CI configs, dependencies, dead
code, CVEs).

- [ ] **Step 2: Static analysis**

Run: `nox -s static-analysis`
Expected: basedpyright `0 errors, 0 warnings, 0 notes`; ty `All checks passed!`.

- [ ] **Step 3: The CI suite**

Run: `CI=true nox -s test`
Expected: every test passes on the dummy driver, `Required test coverage of 100% reached`.

- [ ] **Step 4: Both drivers**

Run: `uv run pytest`
Expected: every test passes on the dummy driver and on the native driver, the driver comparison
reports no differing frame, coverage 100%.

- [ ] **Step 5: Every golden replay, golden trace and bundled demo**

Run: `uv run pytest --dummy-only --no-cov -k "jsonl.gz"`
Expected: every golden replay item (collected wherever its package keeps it) passes.
Run: `uv run pytest --dummy-only --no-cov tests/world/test_golden_traces.py tests/replay/test_golden_replays.py tests/replay/test_bundled_demos.py`
Expected: every test passes.

- [ ] **Step 6: Nothing existing changed**

Run: `git diff main --stat -- '*.jsonl.gz'`
Expected: no output (no recording changed).
Run: `git diff main -- tests/ ':!tests/harness.py' ':!tests/test_engine_context.py' | grep '^-[^-]'`
Expected: no output (existing test files only gained lines).
Run: `grep -rnw "_STATE\|_REGISTRY\|_CURRENT\|_ActiveSnapSettings\|_ActiveBackgroundSettings" src/glitchygames/randomness.py src/glitchygames/sources.py src/glitchygames/input/state.py src/glitchygames/pixel_snap.py src/glitchygames/backgrounds.py`
Expected: no output.

- [ ] **Step 7: Report**

Report the branch's commits (`git log --oneline main..HEAD`), the test and coverage summaries
from Steps 3-5, and any slowdown the replay-metrics rows staged by Tasks 1-7 show against main's
latest rows for the same machine (informational: sub-plan 7 of the master plan measures the
contexts' cost on purpose).
