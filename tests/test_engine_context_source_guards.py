"""The engine context's rules over the engine's and every member's source.

No module reads a context as it is imported (rule 2), and every slot the engine and the members
declare has an isolation check (``ISOLATION_CHECKS`` in tests/test_engine_context.py). Both scan
every workspace member's source (tests/workspace_sources.py reads the members from the
workspace), so they are tests of this repository; moved here unchanged from
tests/test_engine_context.py (Part 3, Stage D, Task D9 fix round 1), which tests the engine alone.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from glitchygames.engine_context import declared_context_slots
from tests.ast_scanning import PROJECT_ROOT
from tests.test_engine_context import (
    ENGINE_SLOT_PREFIX,
    ISOLATION_CHECKS,
    called_name,
    import_time_context_reads,
)
from tests.workspace_sources import scanned_source_files

if TYPE_CHECKING:
    from pathlib import Path


def test_no_module_reads_a_context_as_it_is_imported():
    """Rule 2, over the engine and every workspace member."""
    offenders = {
        allowlist_key: reads
        for allowlist_key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (reads := import_time_context_reads(source_path=path))
    }

    assert offenders == {}


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
        # One check, one message (BUGS.md #228 item 18)
        assert isinstance(name_value, ast.Constant) and isinstance(name_value.value, str), (
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
        slot.name for slot in declared_context_slots() if slot.name.startswith(ENGINE_SLOT_PREFIX)
    }

    assert declared_engine_slot_names == engine_slot_names()
