"""Nothing in the package reads input or time from outside the engine's doors.

Polled input goes through glitchygames/input/state.py, devices through
glitchygames/input/devices.py, events through glitchygames/sources.py, posted events through
glitchygames/recording.post_event, and time through glitchygames/clock.py (or Scene.game_time),
so a replay reaches all of it (plans/2026-10-19-gameplay-replay.md, section 3.4). Only the files
in ALLOWED_BYPASSES, and the functions in ALLOWED_FUNCTION_BYPASSES, use pygame's input, events or
timers directly, each for the reason given.

The engine provides time, and nothing else touches the ``time`` module: any use of it (a read,
``time.sleep``, a constant) and every ``datetime`` read of now are allowed in glitchygames/clock.py
alone, whose raw functions (``raw_counter_ns``, ``raw_sleep``, ...) pacing, measurement and
diagnostics call instead.

Every caller reaches the clock through the module (``from glitchygames import clock``, then
``clock.elapsed_seconds()``), never a function imported by name: then ``glitchygames.clock`` is
the one clock, and one patch on it reaches every reader (the owner's decision, 2026-10-28).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

from tests.ast_scanning import PROJECT_ROOT, import_bindings, qualified_name
from tests.engine_source import ENGINE_DIRECTORY
from tests.workspace_sources import scanned_source_files, write_project_with_member_module

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

# The repository's engine source (the scan reads source files, so it reads the checkout's)
PACKAGE = PROJECT_ROOT / ENGINE_DIRECTORY

# Modules whose names the scan resolves through imports and aliases
WATCHED_DOOR_MODULES = frozenset({
    'time',
    'datetime',
    'pygame',
    'pygame.key',
    'pygame.mouse',
    'pygame.event',
    'pygame.time',
    'pygame.joystick',
    'pygame._sdl2',
    'pygame._sdl2.controller',
    'pygame.controller',
    'pygame.fastevent',
})

# Any name in the time module counts (time.sleep, time.perf_counter, time.CLOCK_MONOTONIC, ...):
# the scan reports it under its own name, and only ANY_TIME_MODULE_USE in an allowance permits it
TIME_MODULE_PREFIX = 'time.'
ANY_TIME_MODULE_USE = 'time.*'

# datetime's reads of now (its other names format and parse, and stay free to use)
DATETIME_CLOCK_READS = frozenset({
    'datetime.datetime.now',
    'datetime.datetime.utcnow',
    'datetime.datetime.today',
    'datetime.date.today',
})

RAW_CLOCK_READS = DATETIME_CLOCK_READS | frozenset({'pygame.time.get_ticks'})

# pygame's own timers: a set_timer event arrives by real time, and a Clock's tick, get_time and
# get_fps read it (the scan cannot follow a Clock's methods, so it reports its construction)
REAL_TIME_TIMERS = frozenset({'pygame.time.set_timer', 'pygame.time.Clock'})

DOOR_BYPASSES = (
    RAW_CLOCK_READS
    | REAL_TIME_TIMERS
    | frozenset({
        'pygame.key.get_pressed',
        'pygame.key.get_mods',
        'pygame.mouse.get_pos',
        'pygame.mouse.get_pressed',
        'pygame.mouse.get_focused',
        'pygame.mouse.get_rel',
        'pygame.key.get_focused',
        'pygame.event.get',
        'pygame.event.poll',
        'pygame.event.wait',
        'pygame.event.peek',
        'pygame.event.post',
        'pygame.fastevent.get',
        'pygame.joystick.Joystick',
        'pygame._sdl2.controller.Controller',
        'pygame.controller.Controller',
        # Device enumeration is part of the devices door too (spec 1.3)
        'pygame.joystick.get_count',
        'pygame._sdl2.controller.get_count',
        'pygame._sdl2.controller.is_controller',
        'pygame._sdl2.controller.name_forindex',
        'pygame.controller.get_count',
        'pygame.controller.is_controller',
        'pygame.controller.name_forindex',
    })
)

# Files (or directories, ending in '/') allowed to use each bypass, with the reason
ALLOWED_BYPASSES: dict[str, frozenset[str]] = {
    # The doors themselves
    'input/state.py': frozenset({
        'pygame.key.get_pressed',
        'pygame.key.get_mods',
        'pygame.mouse.get_pos',
        'pygame.mouse.get_pressed',
        'pygame.mouse.get_focused',
    }),
    'input/devices.py': frozenset({
        'pygame.joystick.Joystick',
        'pygame.joystick.get_count',
        'pygame._sdl2.controller.Controller',
        'pygame._sdl2.controller.get_count',
        'pygame._sdl2.controller.is_controller',
        'pygame._sdl2.controller.name_forindex',
    }),
    'live_sources.py': frozenset({'pygame.event.get', 'pygame.fastevent.get'}),
    'recording.py': frozenset({'pygame.event.post'}),  # post_event, the one poster
    # The door for time: the clocks, and the raw functions pacing, measurement and diagnostics
    # call (the time module and datetime's now are read here and nowhere else)
    'clock.py': DATETIME_CLOCK_READS | {ANY_TIME_MODULE_USE},
}

# Functions (by file, then by name) allowed to use a bypass inside their body only, with the reason
ALLOWED_FUNCTION_BYPASSES: dict[str, dict[str, frozenset[str]]] = {
    'scenes/scene.py': {
        # The pacing fallback clock (SceneManager.__init__): it only paces (tick), its
        # get_time and get_fps are never read (SceneManager._track_performance says why)
        '__init__': frozenset({'pygame.time.Clock'}),
    },
    # The golden-trace harness is the scripted player and the host, outside the game: it posts
    # the input script's events into the real queue before each frame (the frame's pump reads
    # them through the door, as it reads a player's), and drops the host environment's events
    # by draining and reposting the rest. Moved from scripts/record_golden_traces.py unchanged
    # (Stage D, Task D4a)
    'replay/tools/golden_traces.py': {
        'record_trace': frozenset({'pygame.event.post'}),
        'discard_environment_events': frozenset({'pygame.event.get', 'pygame.event.post'}),
    },
}


# Allow-list entries whose file a later task creates (none now: the replay's doors read the real
# queue through LiveSources.pump_events, so replay/driver.py needs no entry)
PENDING_ALLOWED_PATHS: frozenset[str] = frozenset()


def _allowed(relative_path: str) -> frozenset[str]:
    return ALLOWED_BYPASSES.get(relative_path, frozenset())


def _is_bypass(name: str) -> bool:
    return name in DOOR_BYPASSES or name.startswith(TIME_MODULE_PREFIX)


def _is_allowed(*, name: str, allowed: frozenset[str]) -> bool:
    return name in allowed or (
        name.startswith(TIME_MODULE_PREFIX) and ANY_TIME_MODULE_USE in allowed
    )


def _allowed_inside_functions(
    *, tree: ast.Module, allowed_in_functions: Mapping[str, frozenset[str]]
) -> dict[int, frozenset[str]]:
    """Map each node inside an allowed function (by ``id``) to the bypasses it may use.

    Functions match by name anywhere in the file (a method or nested function of that name
    counts too), which is why the allowance is given per file.

    Returns:
        ``id(node)`` -> the bypasses allowed there.

    """
    allowed_by_node: dict[int, frozenset[str]] = {}
    for function in ast.walk(tree):
        if (
            isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
            and function.name in allowed_in_functions
        ):
            for node in ast.walk(function):
                allowed_by_node[id(node)] = allowed_in_functions[function.name]
    return allowed_by_node


def door_bypasses(
    *,
    source_path: Path,
    allowed: frozenset[str] = frozenset(),
    allowed_in_functions: Mapping[str, frozenset[str]] | None = None,
) -> list[str]:
    """Return 'line: name' for every bypass a module calls or references.

    Names resolve through the module's imports and aliases (``from pygame import key as
    keyboard``, a function-local ``import time as time_module``), so aliases are caught.

    Args:
        source_path: The Python file to scan.
        allowed: The bypasses this file may use anywhere (from ALLOWED_BYPASSES).
        allowed_in_functions: The bypasses this file may use only inside the named functions
            (from ALLOWED_FUNCTION_BYPASSES).

    Returns:
        The bypasses found, sorted, each once per line.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    bindings = import_bindings(tree=tree, watched_modules=WATCHED_DOOR_MODULES)
    allowed_by_node = _allowed_inside_functions(
        tree=tree, allowed_in_functions=allowed_in_functions or {}
    )
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Name)):
            name = qualified_name(
                node=node, bindings=bindings, watched_modules=WATCHED_DOOR_MODULES
            )
            if (
                name is not None
                and _is_bypass(name)
                and not _is_allowed(name=name, allowed=allowed)
                and not _is_allowed(name=name, allowed=allowed_by_node.get(id(node), frozenset()))
            ):
                found.append(f'{node.lineno}: {name}')
    return sorted(set(found))


def test_package_reads_input_and_time_only_through_the_doors():
    """No module in glitchygames/ or a member package bypasses a door except the allowed ones."""
    offenders = {
        allowlist_key: bypasses
        for allowlist_key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (
            bypasses := door_bypasses(
                source_path=path,
                allowed=_allowed(allowlist_key),
                allowed_in_functions=ALLOWED_FUNCTION_BYPASSES.get(allowlist_key),
            )
        )
    }
    assert offenders == {}


CLOCK_MODULE = 'glitchygames.clock'


def _imported_module(*, node: ast.ImportFrom, allowlist_key: str, is_engine_file: bool) -> str:
    """Return the module a ``from ... import`` names, a relative one resolved in the engine.

    Returns:
        The absolute module name (a member's relative import keeps its bare name).

    """
    module = node.module or ''
    if node.level == 0 or not is_engine_file:
        return module
    package_parts = ['glitchygames', *allowlist_key.split('/')[:-1]]
    base = package_parts[: len(package_parts) - (node.level - 1)]
    return '.'.join([*base, module] if module else base)


def clock_functions_imported_by_name(
    *, source_path: Path, allowlist_key: str = '', is_engine_file: bool = False
) -> list[str]:
    """Return 'line: from glitchygames.clock import name' for each by-name import of the clock.

    Args:
        source_path: The Python file to scan.
        allowlist_key: Its key (an engine file's path under ``src/glitchygames/``), to resolve
            a relative import.
        is_engine_file: Whether it is an engine file (a relative import can reach the clock).

    Returns:
        Each name imported from ``glitchygames.clock``, at any level, sorted by line.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and _imported_module(
                node=node, allowlist_key=allowlist_key, is_engine_file=is_engine_file
            )
            == CLOCK_MODULE
        ):
            found.extend(
                (node.lineno, f'{node.lineno}: from {CLOCK_MODULE} import {alias.name}')
                for alias in node.names
            )
    return [entry for _line, entry in sorted(found)]


def test_every_caller_reaches_the_clock_through_the_module():
    """No module imports a clock function by name: callers write ``clock.<function>()``."""
    engine_directory = PROJECT_ROOT / ENGINE_DIRECTORY
    offenders = {
        allowlist_key: imports
        for allowlist_key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (
            imports := clock_functions_imported_by_name(
                source_path=path,
                allowlist_key=allowlist_key,
                is_engine_file=path.is_relative_to(engine_directory),
            )
        )
    }
    assert offenders == {}


BY_NAME_CLOCK_SOURCE = """\
from glitchygames import clock
from glitchygames.clock import elapsed_seconds

def cooldown_ready(last_seconds):
    from glitchygames.clock import raw_sleep as pause
    pause(0)
    return elapsed_seconds() - last_seconds > 1.0 and clock.measured_seconds() > 0
"""


def test_a_clock_function_imported_by_name_is_reported(tmp_path):
    """A by-name import is reported, aliased or function-local; the module import is not."""
    path = tmp_path / 'by_name.py'
    path.write_text(BY_NAME_CLOCK_SOURCE, encoding='utf-8')
    assert clock_functions_imported_by_name(source_path=path) == [
        '2: from glitchygames.clock import elapsed_seconds',
        '5: from glitchygames.clock import raw_sleep',
    ]


def test_a_relative_import_of_a_clock_function_in_the_engine_is_reported(tmp_path):
    """Inside the engine, ``from ..clock import`` names glitchygames.clock too."""
    path = tmp_path / 'relative.py'
    path.write_text('from ..clock import frame_clock_seconds\nfrom . import clock\n')
    assert clock_functions_imported_by_name(
        source_path=path, allowlist_key='ui/inputs.py', is_engine_file=True
    ) == ['1: from glitchygames.clock import frame_clock_seconds']
    # A member's relative import never reaches the engine
    assert clock_functions_imported_by_name(source_path=path, allowlist_key='game.py') == []


def test_a_bypass_in_a_member_package_is_reported_under_its_repository_path(tmp_path):
    """The guard's walk reads a member's file, keyed by its path from the repository root."""
    member_key = write_project_with_member_module(
        project_root=tmp_path,
        source='import time\n\n\ndef now():\n    return time.monotonic()\n',
    )

    offenders = {
        allowlist_key: bypasses
        for allowlist_key, path in scanned_source_files(project_root=tmp_path)
        if (bypasses := door_bypasses(source_path=path, allowed=_allowed(allowlist_key)))
    }

    assert offenders == {member_key: ['5: time.monotonic']}


MEASURING_SOURCE = """\
import time

def measured_seconds():
    return time.monotonic()

def cooldown_ready(last_seconds):
    return time.monotonic() - last_seconds > 1.0
"""


def test_function_allowance_covers_only_that_function(tmp_path):
    """A bypass allowed in one function is still reported anywhere else in the file."""
    path = tmp_path / 'measuring.py'
    path.write_text(MEASURING_SOURCE, encoding='utf-8')
    assert door_bypasses(source_path=path) == ['4: time.monotonic', '7: time.monotonic']
    assert door_bypasses(
        source_path=path,
        allowed_in_functions={'measured_seconds': frozenset({'time.monotonic'})},
    ) == ['7: time.monotonic']


def test_the_clock_module_is_the_only_reader_of_time():
    """Only glitchygames/clock.py may use the time module or read datetime's now.

    Its raw reads are each found by the scan without its allowance (so the allowance is not
    vacuous), and no other file or function has any time allowance.
    """
    clock_path = PACKAGE / 'clock.py'
    unallowed = {entry.split(': ', 1)[1] for entry in door_bypasses(source_path=clock_path)}
    assert unallowed == {
        'time.monotonic',
        'time.perf_counter_ns',
        'time.perf_counter',
        'time.sleep',
        'datetime.datetime.now',
    }
    assert door_bypasses(source_path=clock_path, allowed=_allowed('clock.py')) == []
    time_allowances = DATETIME_CLOCK_READS | {ANY_TIME_MODULE_USE}
    assert {
        location for location, names in ALLOWED_BYPASSES.items() if names & time_allowances
    } == {'clock.py'}
    assert not any(
        names & time_allowances or any(name.startswith(TIME_MODULE_PREFIX) for name in names)
        for functions in ALLOWED_FUNCTION_BYPASSES.values()
        for names in functions.values()
    )


SLEEPING_SOURCE = """\
import time
from time import sleep as pause

def wait_a_frame():
    time.sleep(1 / 60)

def wait_again():
    pause(0)
"""


def test_a_raw_sleep_outside_the_clock_module_is_reported(tmp_path):
    """time.sleep is a bypass anywhere but glitchygames/clock.py, under its name or an alias."""
    path = tmp_path / 'sleeping.py'
    path.write_text(SLEEPING_SOURCE, encoding='utf-8')
    assert door_bypasses(source_path=path, allowed=_allowed('timing.py')) == [
        '5: time.sleep',
        '8: time.sleep',
    ]
    assert door_bypasses(source_path=path, allowed=_allowed('clock.py')) == []


OFFENDING_SOURCE = """\
import time
import pygame
from pygame import key as keyboard
from datetime import datetime as clock

def poll():
    return pygame.key.get_pressed(), keyboard.get_mods(), time.time(), clock.now()

def measure():
    import time as time_module
    return time_module.perf_counter(), pygame.time.get_ticks()

def enumerate_devices():
    from pygame._sdl2 import controller as sdl2_controller
    return pygame.joystick.get_count(), sdl2_controller.is_controller(0)

def post():
    pygame.event.post(pygame.event.Event(pygame.USEREVENT))

def other_clocks():
    import datetime
    return (clock.today(), datetime.date.today(), time.process_time(),
            time.clock_gettime(time.CLOCK_MONOTONIC))

def other_input():
    from pygame import event as pygame_event
    return (pygame_event.poll(), pygame.event.wait(100), pygame.event.peek(),
            pygame.mouse.get_rel(), pygame.key.get_focused())

def real_time_timers():
    pygame.time.set_timer(pygame.USEREVENT, 1000)
    return pygame.time.Clock()
"""


@pytest.fixture
def offending_file(tmp_path) -> Path:
    """A module using each kind of bypass, through aliases and function-local imports.

    Returns:
        The path of the written file.

    """
    path = tmp_path / 'offending.py'
    path.write_text(OFFENDING_SOURCE, encoding='utf-8')
    return path


def test_scan_finds_every_kind(offending_file):
    """The scan reports each bypass, aliased or not (so the package scan is not vacuous)."""
    names = {entry.split(': ', 1)[1] for entry in door_bypasses(source_path=offending_file)}
    assert names == {
        'pygame.key.get_pressed',
        'pygame.key.get_mods',
        'time.time',
        'datetime.datetime.now',
        'time.perf_counter',
        'pygame.time.get_ticks',
        'pygame.event.post',
        'pygame.joystick.get_count',
        'pygame._sdl2.controller.is_controller',
        'datetime.datetime.today',
        'datetime.date.today',
        'time.process_time',
        'time.clock_gettime',
        'time.CLOCK_MONOTONIC',
        'pygame.event.poll',
        'pygame.event.wait',
        'pygame.event.peek',
        'pygame.mouse.get_rel',
        'pygame.key.get_focused',
        'pygame.time.set_timer',
        'pygame.time.Clock',
    }


def test_every_allowed_path_exists_unless_pending():
    """Each allow-list entry names a real file in the package.

    A pending entry must not exist yet, so the task that creates it also removes its marker.
    """
    for location in ALLOWED_BYPASSES:
        exists = (PACKAGE / location).is_file()
        if location in PENDING_ALLOWED_PATHS:
            assert not exists, f'{location} exists now: remove it from PENDING_ALLOWED_PATHS'
        else:
            assert exists, location


def test_every_allowed_function_exists():
    """Each function allowance names a function defined in its file."""
    for location, functions in ALLOWED_FUNCTION_BYPASSES.items():
        tree = ast.parse((PACKAGE / location).read_text(encoding='utf-8'))
        defined = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert set(functions) <= defined, location


def test_allowed_files_are_exact_paths():
    """An allow-list entry matches its exact path only (no directory is exempt)."""
    assert _allowed('clock.py') == DATETIME_CLOCK_READS | {ANY_TIME_MODULE_USE}
    assert _allowed('scenes/clock.py') == frozenset()
    assert _allowed('timing.py') == frozenset()
    assert _allowed('bitmappy/editor.py') == frozenset()
