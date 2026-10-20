"""Nothing in the package reads input or time from outside the engine's doors.

Polled input goes through glitchygames/input/state.py, devices through
glitchygames/input/devices.py, events through glitchygames/sources.py, posted events through
glitchygames/recording.post_event, and time through glitchygames/clock.py (or Scene.game_time),
so a replay reaches all of it (plans/2026-10-19-gameplay-replay.md, section 3.4). Only the files
in ALLOWED_BYPASSES read the raw clock or pygame directly, each for the reason given.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.ast_scanning import import_bindings, qualified_name

PACKAGE = Path(__file__).resolve().parent.parent / 'glitchygames'

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

DOOR_BYPASSES = RAW_CLOCK_READS | frozenset({
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
        'time.monotonic',
        'datetime.datetime.now',
    }),
    'replay/driver.py': frozenset({'pygame.event.get'}),  # drains the real queue during replay
    'recording.py': frozenset({'pygame.event.post'}),  # post_event, the one poster
    # Pacing measures the real run; logic gets frame time only through the frame-time door
    'timing.py': RAW_CLOCK_READS,
    'scenes/scene.py': frozenset({'time.perf_counter'}),  # SceneManager.start/_finish_frame
    # Performance statistics and the debug HUD describe the real run; never compared
    'performance/': RAW_CLOCK_READS,
    'debug/': RAW_CLOCK_READS,
    # The audio-glitch probe measures the real machine (scripts/audio_glitch_probe.py)
    'audio/diagnostics.py': RAW_CLOCK_READS,
    # The recording's own start stamp (header recorded_at, the replay wall clock's origin)
    'engine/game_engine.py': frozenset({'datetime.datetime.now'}),
    # Signs requests to a real server, which needs real time
    'api/client.py': frozenset({'time.time'}),
}


# Allow-list entries whose file a later task creates. Pending until Task 12 of the gameplay
# replay plan creates replay/driver.py; that task removes it from here
PENDING_ALLOWED_PATHS = frozenset({'replay/driver.py'})


def _allowed(relative_path: str) -> frozenset[str]:
    allowed: set[str] = set()
    for location, names in ALLOWED_BYPASSES.items():
        if relative_path == location or (
            location.endswith('/') and relative_path.startswith(location)
        ):
            allowed |= names
    return frozenset(allowed)


def door_bypasses(*, source_path: Path, allowed: frozenset[str] = frozenset()) -> list[str]:
    """Return 'line: name' for every bypass a module calls or references.

    Names resolve through the module's imports and aliases (``from pygame import key as
    keyboard``, a function-local ``import time as time_module``), so aliases are caught.

    Args:
        source_path: The Python file to scan.
        allowed: The bypasses this file may use (from ALLOWED_BYPASSES).

    Returns:
        The bypasses found, sorted, each once per line.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    bindings = import_bindings(tree=tree, watched_modules=WATCHED_DOOR_MODULES)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Name)):
            name = qualified_name(
                node=node, bindings=bindings, watched_modules=WATCHED_DOOR_MODULES
            )
            if name in DOOR_BYPASSES and name not in allowed:
                found.append(f'{node.lineno}: {name}')
    return sorted(set(found))


def test_package_reads_input_and_time_only_through_the_doors():
    """No module in glitchygames/ bypasses a door except the allowed files, for their reasons."""
    offenders = {
        str(path.relative_to(PACKAGE)): bypasses
        for path in sorted(PACKAGE.rglob('*.py'))
        if (
            bypasses := door_bypasses(
                source_path=path, allowed=_allowed(path.relative_to(PACKAGE).as_posix())
            )
        )
    }
    assert offenders == {}


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


def test_allowed_files_are_exact_paths_or_directories():
    """An allow-list entry matches its exact path, or everything under a directory entry."""
    assert _allowed('timing.py') == RAW_CLOCK_READS
    assert _allowed('performance/adaptive_clamping.py') == RAW_CLOCK_READS
    assert _allowed('bitmappy/editor.py') == frozenset()
