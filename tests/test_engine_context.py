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

# The harness's leak check (tests/harness.py) and the autouse fixtures that need not be torn
# down after it, each with its reason: every other autouse fixture resets or restores engine
# state, so the leak check requests it and pytest tears the leak check down first
LEAK_CHECK_FIXTURE_NAME = 'every_test_ends_in_the_default_engine_context'
PROCESS_STATE_AUTOUSE_FIXTURES = {
    'restore_signal_handlers': 'signal handlers are one per process, never per context',
    'restore_gil_switch_interval': 'the GIL switch interval is one per process',
    'ensure_pygame_graceful_quit': 'pygame, the display and the mixer are one per process',
}


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


def is_autouse_fixture(function: ast.FunctionDef) -> bool:
    """Return whether a function is decorated ``@pytest.fixture(autouse=True)``.

    Args:
        function: The function.

    Returns:
        True for an autouse fixture.

    """
    return any(
        isinstance(decorator, ast.Call)
        and called_name(decorator) == 'fixture'
        and any(
            keyword.arg == 'autouse'
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in decorator.keywords
        )
        for decorator in function.decorator_list
    )


def test_the_harness_leak_check_is_torn_down_before_every_engine_state_reset():
    """The leak check requests each engine-state reset, so it is caught before they reset.

    pytest orders a plugin's autouse fixtures of one scope by name, not by definition, so only a
    request puts the leak check's teardown first. A new autouse fixture must be requested by it
    or listed in PROCESS_STATE_AUTOUSE_FIXTURES with its reason.
    """
    tree = ast.parse((PROJECT_ROOT / 'tests' / 'harness.py').read_text(encoding='utf-8'))
    fixtures = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and any(
            called_name(decorator) == 'fixture'
            if isinstance(decorator, ast.Call)
            else isinstance(decorator, ast.Attribute) and decorator.attr == 'fixture'
            for decorator in node.decorator_list
        )
    }
    autouse_fixtures = {name for name, node in fixtures.items() if is_autouse_fixture(node)}
    # Everything the leak check requests, directly or through the fixtures it requests
    requested: set[str] = set()
    pending = [LEAK_CHECK_FIXTURE_NAME]
    while pending:
        for argument in fixtures[pending.pop()].args.args:
            if argument.arg in fixtures and argument.arg not in requested:
                requested.add(argument.arg)
                pending.append(argument.arg)

    engine_state_fixtures = (
        autouse_fixtures - {LEAK_CHECK_FIXTURE_NAME} - set(PROCESS_STATE_AUTOUSE_FIXTURES)
    )

    assert set(PROCESS_STATE_AUTOUSE_FIXTURES) <= autouse_fixtures
    assert engine_state_fixtures
    assert requested & autouse_fixtures == engine_state_fixtures


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
        plain_thread = threading.Thread(target=read_into, kwargs={'key': 'plain'})
        given_thread = threading.Thread(
            target=read_into, kwargs={'key': 'given'}, context=contextvars.copy_context()
        )
        for thread in (plain_thread, given_thread):
            thread.start()
            thread.join()

    assert seen['given'] is second
    expected_plain = second if sys.flags.thread_inherit_context else default_context()
    assert seen['plain'] is expected_plain


def test_an_asyncio_task_made_inside_a_switch_keeps_its_context():
    """An asyncio task gets a copy of the current context as it is made."""
    second = EngineContext(name='second')

    async def read_context() -> EngineContext:
        # Read after yielding: the switch in run() has ended by then, the task's copy has not
        await asyncio.sleep(0)
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
        # Read before yielding: this runs while run() holds its switch across the await
        seen.append(current_context())
        await asyncio.sleep(0)

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
