"""Only the doors' event pumps read SDL's event queue, in the engine and every member.

A recording must see every batch the engine reads, and a replay must be able to substitute
every batch, so no other code calls ``pygame.event.get/poll/wait/peek/pump/clear``. The guard
scans the engine's and every workspace member's source (tests/workspace_sources.py reads the
members from the workspace), so it is a test of this repository; moved here unchanged from
tests/test_recording.py (Part 3, Stage D, Task D9 fix round 1), which tests the engine alone.
"""

from __future__ import annotations

import ast
from pathlib import Path

from glitchygames import recording
from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files

# Calls that read (or drain) SDL's event queue. Only the doors' event pumps may use them, each
# named by (file relative to the package, qualified function name); GameEngine._pump_events
# reads through the active sources. A new pump (e.g. a replay's) is added here on purpose.
# set_display_mode only pumps (pygame.event.pump), before the first frame, so the window system's
# answer to a resize is processed: it reads and drops nothing, and the events it moves into SDL's
# queue are read by the doors' pump on the first frame (glitchygames/display_mode.py)
_PUMP_SEAMS = frozenset({
    ('live_sources.py', 'LiveSources.pump_events'),
    ('display_mode.py', 'set_display_mode'),
    # The golden-trace harness stands outside the game, as the host does: between frames it
    # drops the events the host environment posted (window focus, audio devices) and, when a
    # run ends, empties the queue for the next one. Moved from scripts/record_golden_traces.py
    # unchanged (Stage D, Task D4a); the frame's own pump still reads every batch it records
    ('replay/tools/golden_traces.py', 'discard_environment_events'),
    ('replay/tools/golden_traces.py', 'golden_game'),
    # The scripted-session recorder stands outside the game too: before and after a session it
    # empties the queue a caller (a test) left, so the session records none of it. Moved from
    # scripts/record_scripted_session.py (Stage D, Task D4b), the same clear in a helper
    ('replay/tools/scripted_sessions.py', 'clear_events_left_queued'),
})

_QUEUE_READING_ATTRIBUTES = frozenset({'get', 'poll', 'wait', 'peek', 'pump', 'clear'})

_EVENT_MODULE_NAMES = frozenset({'event', 'fastevent'})

_GETATTR_MINIMUM_ARGUMENTS = 2


def _is_pygame_event_module(node: ast.AST) -> bool:
    """Report whether a node is ``pygame.event``/``pygame.fastevent`` or a getattr of one."""
    if isinstance(node, ast.Attribute):
        return (
            node.attr in _EVENT_MODULE_NAMES
            and isinstance(node.value, ast.Name)
            and node.value.id == 'pygame'
        )
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr':
        # getattr(object, name[, default]): fewer arguments cannot name a module
        if len(node.args) < _GETATTR_MINIMUM_ARGUMENTS:
            return False
        target, name = node.args[0], node.args[1]
        return (
            isinstance(target, ast.Name)
            and target.id == 'pygame'
            and isinstance(name, ast.Constant)
            and name.value in _EVENT_MODULE_NAMES
        )
    return False


def _event_module_aliases(tree: ast.AST) -> set[str]:
    """Return the names the file binds to a pygame event module (``x = getattr(pygame, ...)``).

    Returns:
        Every name assigned a pygame event module anywhere in the file.

    """
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_pygame_event_module(node.value):
            aliases.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and _is_pygame_event_module(node.value)
            and isinstance(node.target, ast.Name)
        ):
            aliases.add(node.target.id)
    return aliases


def _queue_read_description(*, node: ast.AST, aliases: set[str]) -> str | None:
    """Describe a queue read (``pygame.event.get``, or ``<alias>.get`` through an alias).

    Returns:
        The read as written, or None when the node is not a queue read.

    """
    if not isinstance(node, ast.Attribute) or node.attr not in _QUEUE_READING_ATTRIBUTES:
        return None
    module = node.value
    if _is_pygame_event_module(module) and isinstance(module, ast.Attribute):
        return f'pygame.{module.attr}.{node.attr}'
    if isinstance(module, ast.Name) and module.id in aliases:
        return f'{module.id}.{node.attr}'
    return None


def _nodes_with_qualified_names(*, node: ast.AST, qualified_name: str) -> list[tuple[ast.AST, str]]:
    """List every node under ``node`` with the qualified name of the def/class enclosing it.

    Returns:
        (node, qualified name) pairs; module-level nodes have the name ''.

    """
    pairs: list[tuple[ast.AST, str]] = []
    for child in ast.iter_child_nodes(node):
        child_qualified_name = qualified_name
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            child_qualified_name = (
                f'{qualified_name}.{child.name}' if qualified_name else child.name
            )
        pairs.append((child, child_qualified_name))
        pairs.extend(_nodes_with_qualified_names(node=child, qualified_name=child_qualified_name))
    return pairs


def _queue_reads_outside_the_pump_seam(*, source_path: Path, relative_path: str) -> list[str]:
    """List each queue read in a file outside the pump seams named in ``_PUMP_SEAMS``.

    Args:
        source_path: The file to scan.
        relative_path: Its path relative to the package root, as ``_PUMP_SEAMS`` names it.

    Returns:
        One ``path:line qualified.name read`` entry per offending read.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    aliases = _event_module_aliases(tree)
    offenders: list[str] = []
    for node, qualified_name in _nodes_with_qualified_names(node=tree, qualified_name=''):
        description = _queue_read_description(node=node, aliases=aliases)
        if description is None or (relative_path, qualified_name) in _PUMP_SEAMS:
            continue
        line_number = getattr(node, 'lineno', 0)
        offenders.append(f'{relative_path}:{line_number} {qualified_name} {description}')
    return offenders


def test_pump_seam_is_the_only_place_the_engine_reads_sdl_queue():
    """Every read of SDL's queue in the package goes through the doors' event pump.

    A recording must see every batch, and a replay must be able to substitute every batch,
    so no other code may call pygame.event.get/poll/wait/peek/pump/clear (directly or through
    an alias such as ``getattr(pygame, 'fastevent')``).
    """
    offenders = [
        offender
        for allowlist_key, source_path in scanned_source_files(project_root=PROJECT_ROOT)
        for offender in _queue_reads_outside_the_pump_seam(
            source_path=source_path, relative_path=allowlist_key
        )
    ]

    assert offenders == []


def test_every_pump_seam_still_reads_the_queue():
    """Each allowed seam exists and reads the queue (the allow list cannot go stale)."""
    package_root = Path(recording.__file__).parent
    for relative_path, qualified_name in _PUMP_SEAMS:
        source_path = package_root / relative_path
        tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
        aliases = _event_module_aliases(tree)
        seam_reads = [
            description
            for node, node_qualified_name in _nodes_with_qualified_names(
                node=tree, qualified_name=''
            )
            if node_qualified_name == qualified_name
            and (description := _queue_read_description(node=node, aliases=aliases)) is not None
        ]
        # LiveSources.pump_events reads pygame.event.get and the fastevent alias's get
        assert seam_reads, (relative_path, qualified_name)


_OFFENDER_FIXTURE = """import pygame


class LiveSources:
    def pump_events(self):
        fastevent = getattr(pygame, 'fastevent', None)
        if fastevent is not None:
            return list(fastevent.get())
        return list(pygame.event.get())


class OtherSources:
    def pump_events(self):
        return pygame.event.get()


def elsewhere():
    return pygame.event.poll()


def sneaky():
    queue = getattr(pygame, 'event')
    return queue.peek()
"""


def test_pump_seam_scan_allows_only_the_named_seam(tmp_path):
    """The scan reports reads outside the named (file, function), aliases included."""
    source_path = tmp_path / 'live_sources.py'
    source_path.write_text(_OFFENDER_FIXTURE, encoding='utf-8')

    assert _queue_reads_outside_the_pump_seam(
        source_path=source_path, relative_path='live_sources.py'
    ) == [
        'live_sources.py:14 OtherSources.pump_events pygame.event.get',
        'live_sources.py:18 elsewhere pygame.event.poll',
        'live_sources.py:23 sneaky queue.peek',
    ]


def test_pump_seam_scan_names_the_file_too(tmp_path):
    """The same LiveSources.pump_events in another file is not a seam."""
    source_path = tmp_path / 'reader.py'
    source_path.write_text(_OFFENDER_FIXTURE, encoding='utf-8')

    offenders = _queue_reads_outside_the_pump_seam(
        source_path=source_path, relative_path='reader.py'
    )

    assert offenders[:2] == [
        'reader.py:8 LiveSources.pump_events fastevent.get',
        'reader.py:9 LiveSources.pump_events pygame.event.get',
    ]
    assert len(offenders) == 5
