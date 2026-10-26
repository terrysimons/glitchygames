"""Nothing in the package reads input or time from outside the engine's doors.

Polled input goes through glitchygames/input/state.py, devices through
glitchygames/input/devices.py, events through glitchygames/sources.py, posted events through
glitchygames/recording.post_event, and time through glitchygames/clock.py (or Scene.game_time),
so a replay reaches all of it (plans/2026-10-19-gameplay-replay.md, section 3.4). Only the files
in ALLOWED_BYPASSES, and the functions in ALLOWED_FUNCTION_BYPASSES, read the raw clock or pygame
directly, each for the reason given.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from scripts.workspace_packages import ENGINE_DIRECTORY

from tests.ast_scanning import (
    PROJECT_ROOT,
    import_bindings,
    qualified_name,
    scanned_source_files,
    write_project_with_member_module,
)

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

RAW_CLOCK_READS = frozenset({
    'time.time',
    'time.time_ns',
    'time.monotonic',
    'time.monotonic_ns',
    'time.perf_counter',
    'time.perf_counter_ns',
    'datetime.datetime.now',
    'datetime.datetime.utcnow',
    'datetime.datetime.today',
    'datetime.date.today',
    'time.process_time',
    'time.process_time_ns',
    'time.clock_gettime',
    'time.clock_gettime_ns',
    'pygame.time.get_ticks',
})

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
    'live_sources.py': frozenset({
        'pygame.event.get',
        'pygame.fastevent.get',
        'datetime.datetime.now',
    }),
    'recording.py': frozenset({'pygame.event.post'}),  # post_event, the one poster
    # Pacing measures the real run; logic gets frame time only through the frame-time door
    'timing.py': RAW_CLOCK_READS,
    # Performance statistics and the debug HUD describe the real run; never compared
    'performance/': RAW_CLOCK_READS,
    'debug/': RAW_CLOCK_READS,
    # The audio-glitch probe measures the real machine (scripts/audio_glitch_probe.py)
    'audio/diagnostics.py': RAW_CLOCK_READS,
}

# Functions (by file, then by name) allowed to use a bypass inside their body only, with the reason
ALLOWED_FUNCTION_BYPASSES: dict[str, dict[str, frozenset[str]]] = {
    # Real durations for diagnostics only, never replayed (glitchygames/clock.py)
    'clock.py': {'measured_seconds': frozenset({'time.monotonic'})},
    'scenes/scene.py': {
        # The frame loop measures each frame's real time; logic gets it only through the
        # frame-time door (SceneManager.begin_frames, run_frame_step and _finish_frame: the
        # steps SceneManager.start and an outer driver, glitchygames/host.py, both run)
        'begin_frames': frozenset({'time.perf_counter'}),
        'run_frame_step': frozenset({'time.perf_counter'}),
        '_finish_frame': frozenset({'time.perf_counter'}),
        # The pacing fallback clock (SceneManager.__init__): it only paces (tick), its
        # get_time and get_fps are never read (SceneManager._track_performance says why)
        '__init__': frozenset({'pygame.time.Clock'}),
    },
    # The recording's own start stamp (header recorded_at, the replay wall clock's origin), and
    # each run's measured_at (measurement_runs provenance; never replayed or served)
    'engine/game_engine.py': {
        'trace_recording_header': frozenset({'datetime.datetime.now'}),
        'measurement_run': frozenset({'datetime.datetime.now'}),
    },
}


# Allow-list entries whose file a later task creates (none now: the replay's doors read the real
# queue through LiveSources.pump_events, so replay/driver.py needs no entry)
PENDING_ALLOWED_PATHS: frozenset[str] = frozenset()


def _allowed(relative_path: str) -> frozenset[str]:
    allowed: set[str] = set()
    for location, names in ALLOWED_BYPASSES.items():
        if relative_path == location or (
            location.endswith('/') and relative_path.startswith(location)
        ):
            allowed |= names
    return frozenset(allowed)


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
                name in DOOR_BYPASSES
                and name not in allowed
                and name not in allowed_by_node.get(id(node), frozenset())
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


def test_measured_seconds_is_the_clock_modules_only_raw_read():
    """glitchygames/clock.py reads the raw clock in measured_seconds() and nowhere else."""
    clock_path = PACKAGE / 'clock.py'
    assert _allowed('clock.py') == frozenset()
    unallowed = door_bypasses(source_path=clock_path)
    assert [entry.split(': ', 1)[1] for entry in unallowed] == ['time.monotonic']
    assert (
        door_bypasses(
            source_path=clock_path, allowed_in_functions=ALLOWED_FUNCTION_BYPASSES['clock.py']
        )
        == []
    )


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
        'pygame.event.poll',
        'pygame.event.wait',
        'pygame.event.peek',
        'pygame.mouse.get_rel',
        'pygame.key.get_focused',
        'pygame.time.set_timer',
        'pygame.time.Clock',
    }


def test_every_allowed_path_exists_unless_pending():
    """Each allow-list entry names a real file (or directory, ending in '/') in the package.

    A pending entry must not exist yet, so the task that creates it also removes its marker.
    """
    for location in ALLOWED_BYPASSES:
        path = PACKAGE / location
        exists = path.is_dir() if location.endswith('/') else path.is_file()
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


def test_allowed_files_are_exact_paths_or_directories():
    """An allow-list entry matches its exact path, or everything under a directory entry."""
    assert _allowed('timing.py') == RAW_CLOCK_READS
    assert _allowed('performance/adaptive_clamping.py') == RAW_CLOCK_READS
    assert _allowed('bitmappy/editor.py') == frozenset()
