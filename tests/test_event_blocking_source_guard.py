"""Only two engine files change which event types SDL blocks (plans/future-work.md, Arcade 3).

Every engine call that blocks or allows event types goes through ``events.set_event_types_allowed``
(``events/base.py``), which changes nothing in an inner context, or is ``EventTypeBlock``
(``replay/input_blocking.py``), the replay's own block. A direct ``pygame.event.set_allowed`` or
``set_blocked`` anywhere else, in the engine or a workspace member, would change SDL's state for
the whole process from inside an inner game, and bring back the bug that helper fixed. Same scan
as tests/test_pump_seam_guard.py (it reads the engine's and every member's source), and the same
limit: a call it cannot resolve by name (``getattr(pygame.event, name)``, a stored function) is
not seen.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.ast_scanning import PROJECT_ROOT
from tests.test_pump_seam_guard import _event_module_aliases, _is_pygame_event_module
from tests.workspace_sources import scanned_source_files

if TYPE_CHECKING:
    from pathlib import Path

# The files allowed to call them, by the key scanned_source_files gives (relative to the engine)
ALLOWED_FILES = frozenset({'events/base.py', 'replay/input_blocking.py'})
BLOCKING_ATTRIBUTES = frozenset({'set_allowed', 'set_blocked'})


def event_blocking_calls(*, source_path: Path) -> list[str]:
    """List each ``set_allowed``/``set_blocked`` call in a file, aliases of the event module too.

    Returns:
        One ``line call`` entry per call.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    aliases = _event_module_aliases(tree)
    calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in BLOCKING_ATTRIBUTES:
            continue
        module = node.func.value
        is_event_module = _is_pygame_event_module(module) or (
            isinstance(module, ast.Name) and module.id in aliases
        )
        if is_event_module:
            calls.append(f'{node.lineno} {ast.unparse(node.func)}')
    return calls


def test_only_the_named_engine_files_change_the_blocked_event_types():
    """No engine or member file but the two named calls pygame.event.set_allowed or set_blocked."""
    offenders = [
        f'{allowlist_key}:{call}'
        for allowlist_key, source_path in scanned_source_files(project_root=PROJECT_ROOT)
        if allowlist_key not in ALLOWED_FILES
        for call in event_blocking_calls(source_path=source_path)
    ]

    assert offenders == []


def test_every_allowed_file_still_makes_such_a_call():
    """The allowlist cannot go stale: each named file still calls one."""
    keyed_paths = dict(scanned_source_files(project_root=PROJECT_ROOT))

    for allowed_file in ALLOWED_FILES:
        assert event_blocking_calls(source_path=keyed_paths[allowed_file]), allowed_file


def test_the_scan_catches_a_planted_call_and_its_alias(tmp_path):
    """Direct, through ``from``-less alias and getattr alias: each is reported; others are not."""
    source_path = tmp_path / 'planted.py'
    source_path.write_text(
        'import pygame\n'
        '\n'
        'def direct():\n'
        '    pygame.event.set_blocked([pygame.KEYDOWN])\n'
        '\n'
        'def through_an_alias():\n'
        "    queue = getattr(pygame, 'event')\n"
        '    queue.set_allowed(None)\n'
        '\n'
        'def unrelated():\n'
        '    pygame.event.post(None)\n'
        '    other.set_blocked([])\n',
        encoding='utf-8',
    )

    assert event_blocking_calls(source_path=source_path) == [
        '4 pygame.event.set_blocked',
        '8 queue.set_allowed',
    ]
