"""The engine context (glitchygames.engine_context): the state one running game owns.

Every test runs in the default context and switches only inside ``with context.active():``;
the harness fails a test that leaves another context current (tests/harness.py).
"""

from __future__ import annotations

import ast
import asyncio
import contextvars
import random
import re
import sys
import threading
from typing import TYPE_CHECKING, override

import numpy as np
import pygame
import pytest
from pydantic import BaseModel, ConfigDict

from glitchygames.backgrounds import (
    DEFAULT_BACKGROUND_PATTERN,
    BackgroundPattern,
    active_default_background_pattern,
    set_active_default_background_pattern,
)
from glitchygames.engine_context import (
    DEFAULT_CONTEXT_NAME,
    ContextSlot,
    DuplicateContextSlotError,
    EngineContext,
    current_context,
    declared_context_slots,
    default_context,
)
from glitchygames.game_frames import game_frame_clock
from glitchygames.input.devices import JOYSTICK_COUNT_CALL, EnumerationAnswer
from glitchygames.input.state import IDLE_INPUT, current_input, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.pixel_snap import (
    PixelSnapMode,
    active_default_snap_mode,
    set_active_default_snap_mode,
)
from glitchygames.randomness import (
    NUMPY_STREAM_KIND,
    RANDOM_STREAM_KIND,
    engine_random_seed,
    numpy_stream,
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
    discard_scope_posts,
    frame_clock_seconds,
    has_scoped_sources,
    install_sources,
    mark_frames_started,
    notify_device_answer,
    notify_save_store_opened,
    observe_device_answers,
    observe_save_store_openings,
    pending_redelivered_events,
    pop_scoped_sources,
    push_scoped_sources,
    redeliver_events,
    reset_sources,
    stop_observing_device_answers,
    stop_observing_save_store_openings,
    without_discarded_scope_posts,
)
from glitchygames.state import MemorySaveManager, SaveManager, open_saves
from tests.ast_scanning import PROJECT_ROOT
from tests.engine_source import ENGINE_DIRECTORY
from tests.input.test_input_state import snapshot_with

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from glitchygames.input.devices import DeviceDescriptor

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


# The two stand-in games' master seeds, and what each holds
FIRST_SEED = 1
SECOND_SEED = 2
DRAWS_STREAM = 'tests.engine_context.draws'
STAND_IN_GAME = 'stand-in-game'
SAVE_SLOT = 'progress'
FIRST_NAMESPACE = 'stand-in-game-first'
SECOND_NAMESPACE = 'stand-in-game-second'
# Draws per stream in the random-streams check, and the numpy draws' exclusive upper bound
DRAW_ROUNDS = 3
NUMPY_DRAW_LIMIT = 1000
# The two-games test: frames each game runs, its frame time and first frame number per seed
STAND_IN_FRAME_COUNT = 4
FRAME_SECONDS_PER_SEED = 0.25
FRAME_NUMBER_START_PER_SEED = 100
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
        """Return the in-memory store for ``namespace``, made empty on first use.

        Args:
            namespace: The game's save namespace.

        Returns:
            The store.

        """
        store = self.memory_stores.get(namespace)
        if store is None:
            store = MemorySaveManager(app_name=namespace, snapshot={})
            self.memory_stores[namespace] = store
        return store


class StandInGame(BaseModel):
    """One stand-in game's settings: what it sets up in its context and holds each frame."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    seed: int
    snap_mode: PixelSnapMode
    pattern: BackgroundPattern
    scancode: int


class StandInFrameReadings(BaseModel):
    """What one frame of a stand-in game read from its context (compared run against run)."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    doors_seed: int
    engine_seed: int
    snap_mode: PixelSnapMode
    pattern: BackgroundPattern
    held_scancodes_before: frozenset[int]
    frame_number: int
    random_draw: float
    numpy_draw: int
    frame_clock_seconds: float
    saved_frames: list[int]


class HeardObserver:
    """An observer of save-store openings and device answers that keeps what it was told."""

    def __init__(self) -> None:
        """Start having heard nothing."""
        self.heard_namespaces: list[str] = []
        self.heard_answers: list[EnumerationAnswer] = []

    def on_save_store_opened(self, *, namespace: str, store: SaveManager) -> None:
        """Keep the namespace of a store opened.

        Args:
            namespace: The store's namespace.
            store: The store (unused).

        """
        del store
        self.heard_namespaces.append(namespace)

    def on_device_answer(
        self, *, answer: EnumerationAnswer, opened: DeviceDescriptor | None
    ) -> None:
        """Keep an answer given.

        Args:
            answer: The answer.
            opened: The opened device's descriptor (unused).

        """
        del opened
        self.heard_answers.append(answer)


def joystick_count_answer(*, count: int) -> EnumerationAnswer:
    """Return the devices door's answer to a joystick count.

    Args:
        count: The count answered.

    Returns:
        The answer.

    """
    return EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=count)


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


def check_game_frame_clock(*, first: EngineContext, second: EngineContext) -> None:
    """Each context counts its own game frames, and the default context its own."""
    default_clock = game_frame_clock()
    with first.active():
        game_frame_clock().begin_frame(logic_scene=None)
        game_frame_clock().begin_frame(logic_scene=None)
    with second.active():
        assert game_frame_clock().shown_game_frame is None
        game_frame_clock().begin_frame(logic_scene=None)
    with first.active():
        assert game_frame_clock().shown_game_frame == 1
    with second.active():
        assert game_frame_clock().shown_game_frame == 0
    assert game_frame_clock() is default_clock


def check_current_input(*, first: EngineContext, second: EngineContext) -> None:
    """Each context keeps its own polled input, and the default context its own."""
    default_snapshot = current_input()
    with first.active():
        set_current_input(snapshot=snapshot_with(pressed_scancodes=frozenset({SPACE_SCANCODE})))
    with second.active():
        assert current_input() is IDLE_INPUT
        set_current_input(snapshot=snapshot_with(pressed_scancodes=frozenset({RETURN_SCANCODE})))
    with first.active():
        assert current_input().pressed_scancodes == frozenset({SPACE_SCANCODE})
    with second.active():
        assert current_input().pressed_scancodes == frozenset({RETURN_SCANCODE})
    assert current_input() is default_snapshot


def check_random_streams(*, first: EngineContext, second: EngineContext) -> None:
    """Each context draws its own numbers, as it would alone, and the default keeps its seed."""
    default_seed = engine_random_seed()
    random_draws: dict[int, list[float]] = {FIRST_SEED: [], SECOND_SEED: []}
    numpy_draws: dict[int, list[int]] = {FIRST_SEED: [], SECOND_SEED: []}
    for context, seed in ((first, FIRST_SEED), (second, SECOND_SEED)):
        with context.active():
            reset_streams(seed=seed)
    # Alternate the contexts draw by draw
    for _round in range(DRAW_ROUNDS):
        for context, seed in ((first, FIRST_SEED), (second, SECOND_SEED)):
            with context.active():
                assert engine_random_seed() == seed
                random_draws[seed].append(random_stream(name=DRAWS_STREAM).random())
                numpy_draws[seed].append(
                    int(numpy_stream(name=DRAWS_STREAM).integers(low=0, high=NUMPY_DRAW_LIMIT))
                )

    for seed in (FIRST_SEED, SECOND_SEED):
        random_reference = random.Random(
            stream_seed(kind=RANDOM_STREAM_KIND, master_seed=seed, name=DRAWS_STREAM)
        )
        numpy_reference = np.random.default_rng(
            stream_seed(kind=NUMPY_STREAM_KIND, master_seed=seed, name=DRAWS_STREAM)
        )
        assert random_draws[seed] == [random_reference.random() for _round in range(DRAW_ROUNDS)]
        assert numpy_draws[seed] == [
            int(numpy_reference.integers(low=0, high=NUMPY_DRAW_LIMIT))
            for _round in range(DRAW_ROUNDS)
        ]
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
        redeliver_events(
            events=[(pygame.event.Event(pygame.USEREVENT, code=FIRST_SEED), 'internal')]
        )
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


def check_scoped_sources(*, first: EngineContext, second: EngineContext) -> None:
    """Doors pushed in one context are never the other's, and popping restores its own."""
    first_doors = MemorySavesSources(random_seed=FIRST_SEED)
    first_scoped_doors = MemorySavesSources(random_seed=FIRST_SEED)
    second_doors = MemorySavesSources(random_seed=SECOND_SEED)
    second_scoped_doors = MemorySavesSources(random_seed=SECOND_SEED)
    with first.active():
        install_sources(sources=first_doors)
        push_scoped_sources(sources=first_scoped_doors)
    with second.active():
        assert not has_scoped_sources()
        install_sources(sources=second_doors)
        assert active_sources() is second_doors
        push_scoped_sources(sources=second_scoped_doors)
    with first.active():
        assert active_sources() is first_scoped_doors
        assert pop_scoped_sources() is first_scoped_doors
        assert active_sources() is first_doors
        assert not has_scoped_sources()
    with second.active():
        assert has_scoped_sources()
        assert active_sources() is second_scoped_doors
        assert pop_scoped_sources() is second_scoped_doors
        assert active_sources() is second_doors
    assert not has_scoped_sources()
    for context in (first, second):
        with context.active():
            reset_sources()


def check_observers(*, first: EngineContext, second: EngineContext) -> None:
    """An observer hears its own context's save openings and device answers only."""
    first_observer = HeardObserver()
    second_observer = HeardObserver()
    default_observer = HeardObserver()
    observe_save_store_openings(observer=default_observer)
    observe_device_answers(observer=default_observer)
    for context, observer in ((first, first_observer), (second, second_observer)):
        with context.active():
            observe_save_store_openings(observer=observer)
            observe_device_answers(observer=observer)
    with second.active():
        notify_save_store_opened(
            namespace=SECOND_NAMESPACE,
            store=MemorySaveManager(app_name=SECOND_NAMESPACE, snapshot={}),
        )
        notify_device_answer(answer=joystick_count_answer(count=SECOND_SEED), opened=None)
        stop_observing_save_store_openings(observer=second_observer)
        stop_observing_device_answers(observer=second_observer)
    with first.active():
        assert first_observer.heard_namespaces == []
        assert first_observer.heard_answers == []
        # Stopping in the second context left the first's observing
        notify_save_store_opened(
            namespace=FIRST_NAMESPACE,
            store=MemorySaveManager(app_name=FIRST_NAMESPACE, snapshot={}),
        )
        notify_device_answer(answer=joystick_count_answer(count=FIRST_SEED), opened=None)
        stop_observing_save_store_openings(observer=first_observer)
        stop_observing_device_answers(observer=first_observer)
    with second.active():
        # Stopped: the second's observer no longer hears its own context
        notify_save_store_opened(
            namespace=SECOND_NAMESPACE,
            store=MemorySaveManager(app_name=SECOND_NAMESPACE, snapshot={}),
        )
        notify_device_answer(answer=joystick_count_answer(count=SECOND_SEED), opened=None)

    assert first_observer.heard_namespaces == [FIRST_NAMESPACE]
    assert first_observer.heard_answers == [joystick_count_answer(count=FIRST_SEED)]
    assert second_observer.heard_namespaces == [SECOND_NAMESPACE]
    assert second_observer.heard_answers == [joystick_count_answer(count=SECOND_SEED)]
    assert default_observer.heard_namespaces == []
    assert default_observer.heard_answers == []
    stop_observing_save_store_openings(observer=default_observer)
    stop_observing_device_answers(observer=default_observer)
    for context in (first, second):
        with context.active():
            reset_sources()


def check_discarded_scope_posts(*, first: EngineContext, second: EngineContext) -> None:
    """A scope's posts discarded in one context are dropped from that context's batch only."""

    def first_seed_batch() -> list[pygame.event.Event]:
        """Return a new batch holding the discarded post's event."""
        return [pygame.event.Event(pygame.USEREVENT, code=FIRST_SEED)]

    with first.active():
        discard_scope_posts(posts=[(pygame.USEREVENT, {'code': FIRST_SEED})])
    with second.active():
        assert [
            event.code for event in without_discarded_scope_posts(events=first_seed_batch())
        ] == [FIRST_SEED]
    assert [event.code for event in without_discarded_scope_posts(events=first_seed_batch())] == [
        FIRST_SEED
    ]
    with first.active():
        assert without_discarded_scope_posts(events=first_seed_batch()) == []
    for context in (first, second):
        with context.active():
            reset_sources()


def check_sources_registry(*, first: EngineContext, second: EngineContext) -> None:
    """Every member of the sources registry stays in its own context."""
    check_doors_and_frame_clock(first=first, second=second)
    check_scoped_sources(first=first, second=second)
    check_observers(first=first, second=second)
    check_discarded_scope_posts(first=first, second=second)


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
    'glitchygames.game_frames.clock': check_game_frame_clock,
    'glitchygames.input.state.current_input': check_current_input,
    'glitchygames.randomness.streams': check_random_streams,
    'glitchygames.sources.registry': check_sources_registry,
    'glitchygames.scenes.scene.scene_managers': check_scene_managers,
}


@pytest.mark.parametrize('slot_name', sorted(ISOLATION_CHECKS))
def test_no_slot_value_leaks_between_two_contexts(slot_name):
    """Two contexts beside the default one: each keeps its own value of the slot."""
    ISOLATION_CHECKS[slot_name](
        first=EngineContext(name='first'), second=EngineContext(name='second')
    )


def set_up_stand_in_game(*, game: StandInGame) -> None:
    """Set up a stand-in game in the current context, as a game's start would.

    Args:
        game: The game.

    """
    seed_engine_random(seed=game.seed)
    install_sources(sources=MemorySavesSources(random_seed=game.seed))
    set_active_default_snap_mode(mode=game.snap_mode)
    set_active_default_background_pattern(pattern=game.pattern)
    SceneManager().frame_number = game.seed * FRAME_NUMBER_START_PER_SEED


def play_stand_in_frame(*, game: StandInGame, frame_index: int) -> StandInFrameReadings:
    """Run one frame of a stand-in game in the current context, touching every slot.

    Args:
        game: The game.
        frame_index: The frame's index (0 first).

    Returns:
        What the frame read.

    """
    held_scancodes_before = current_input().pressed_scancodes
    set_current_input(
        snapshot=snapshot_with(pressed_scancodes=frozenset({game.scancode, frame_index}))
    )
    scene_manager = SceneManager()
    scene_manager.frame_number += 1
    saves = open_saves(app_name=STAND_IN_GAME)
    # The first frame finds no save yet; each later one adds its index to the saved list
    previous_frames = saves.load(slot_name=SAVE_SLOT)['frames'] if frame_index > 0 else []
    saved_frames = [*previous_frames, frame_index]
    saves.save(slot_name=SAVE_SLOT, data={'frames': saved_frames})
    advance_frame_clock(seconds=game.seed * FRAME_SECONDS_PER_SEED)
    return StandInFrameReadings(
        doors_seed=active_sources().random_seed,
        engine_seed=engine_random_seed(),
        snap_mode=active_default_snap_mode(),
        pattern=active_default_background_pattern(),
        held_scancodes_before=held_scancodes_before,
        frame_number=scene_manager.frame_number,
        random_draw=random_stream(name=DRAWS_STREAM).random(),
        numpy_draw=int(numpy_stream(name=DRAWS_STREAM).integers(low=0, high=NUMPY_DRAW_LIMIT)),
        frame_clock_seconds=frame_clock_seconds(),
        saved_frames=saves.load(slot_name=SAVE_SLOT)['frames'],
    )


def test_two_contexts_hold_two_games_worth_of_state_without_leaking():
    """Two stand-in games run frame by frame in turn read exactly what each reads alone."""
    games = [
        StandInGame(
            seed=FIRST_SEED,
            snap_mode=PixelSnapMode.FLOOR,
            pattern=BackgroundPattern.CHANNEL_THREE,
            scancode=SPACE_SCANCODE,
        ),
        StandInGame(
            seed=SECOND_SEED,
            snap_mode=PixelSnapMode.CEIL,
            pattern=BackgroundPattern.TEST_PATTERN,
            scancode=RETURN_SCANCODE,
        ),
    ]
    default_manager = SceneManager()
    default_clock = frame_clock_seconds()
    default_seed = engine_random_seed()

    # Each game alone in a context of its own
    alone_readings: list[list[StandInFrameReadings]] = []
    for game in games:
        with EngineContext(name=f'game {game.seed} alone').active():
            set_up_stand_in_game(game=game)
            alone_readings.append([
                play_stand_in_frame(game=game, frame_index=frame_index)
                for frame_index in range(STAND_IN_FRAME_COUNT)
            ])
            reset_sources()
    # Both games in contexts side by side, one frame of each in turn
    contexts = [EngineContext(name=f'game {game.seed}') for game in games]
    side_by_side_readings: list[list[StandInFrameReadings]] = [[] for _game in games]
    for game, context in zip(games, contexts, strict=True):
        with context.active():
            set_up_stand_in_game(game=game)
    for frame_index in range(STAND_IN_FRAME_COUNT):
        for game, context, readings in zip(games, contexts, side_by_side_readings, strict=True):
            with context.active():
                readings.append(play_stand_in_frame(game=game, frame_index=frame_index))
    for context in contexts:
        with context.active():
            reset_sources()

    assert side_by_side_readings == alone_readings
    assert alone_readings[0] != alone_readings[1]
    assert SceneManager() is default_manager
    assert frame_clock_seconds() == default_clock
    assert engine_random_seed() == default_seed
    assert current_input() is IDLE_INPUT
