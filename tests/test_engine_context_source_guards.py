"""The engine context's rules over the engine's and every member's source.

No module reads a context as it is imported (rule 2), and every slot the engine and the members
declare has an isolation check: the engine's in ``ISOLATION_CHECKS`` (tests/test_engine_context.py),
each member's in a ``MEMBER_ISOLATION_CHECKS`` dict in its own tests, found by AST so the engine's
tests never import a member. Both scan
every workspace member's source (tests/workspace_sources.py reads the members from the
workspace), so they are tests of this repository; moved here unchanged from
tests/test_engine_context.py (Part 3, Stage D, Task D9 fix round 1), which tests the engine alone.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest
from scripts.workspace_packages import workspace_members

from glitchygames.engine_context import declared_context_slots
from tests.ast_scanning import PROJECT_ROOT, qualified_name
from tests.engine_source import ENGINE_DIRECTORY
from tests.test_engine_context import (
    ENGINE_SLOT_PREFIX,
    ISOLATION_CHECKS,
    called_name,
    import_time_context_reads,
)
from tests.test_read_only_views import (
    absolute_import_module,
    engine_source_files,
    import_bindings_of,
    module_name_of_file,
    scanned_file,
)
from tests.workspace_sources import scanned_source_files, write_project_with_member_module

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# The dict a member's tests name their slots' isolation checks in (CLAUDE.md, Engine Context)
MEMBER_ISOLATION_CHECKS_NAME = 'MEMBER_ISOLATION_CHECKS'

# A module that reads a module view as it is imported: a module-level import (line 4), module-level
# attribute reads (lines 6 and 7) and a class-body read (line 14). The reads in a function body
# (lines 10 and 11) are fine, and so is the lazy import of line 3: glitchygames.audio's
# __getattr__ answers VoiceAssistant without the view mark (as Brave Adventurer's game.py imports
# it), so it is no view
PLANTED_IMPORT_TIME_VIEW_READS = """\
import glitchygames.performance
from glitchygames import performance
from glitchygames.audio import VoiceAssistant
from glitchygames.performance import AdaptiveClamping, performance_manager

MANAGER = performance.performance_manager
STATS = glitchygames.performance.performance_manager.get_performance_stats

def later():
    from glitchygames.performance import performance_manager as local_manager
    return local_manager, performance.performance_manager

class Holder:
    held = performance.performance_manager
"""


@pytest.fixture(autouse=True, scope='module')
def parsed_files_freed_after_this_file() -> Iterator[None]:
    """Let go of every file ``scanned_file`` parsed when this file's tests are done.

    The syntax trees are about 100 MiB: kept for the rest of a serial run, they pushed CircleCI's
    2 GB Linux job past its memory limit (2026-11-17). tests/test_read_only_views.py has the twin.
    """
    yield
    scanned_file.cache_clear()


def engine_module_views() -> frozenset[str]:
    """Return every module view the engine declares, as ``'<module>.<name>'``.

    A module view is a name its module marks in ``READ_ONLY_MODULE_VIEWS`` (the rule of
    tests/test_read_only_views.py's ``declared_views``); a module ``__getattr__`` without the
    mark (a lazy import) declares none.

    Returns:
        The qualified names.

    """
    return frozenset(
        f'{scanned.module_name}.{name}'
        for source_path in engine_source_files()
        for scanned in [scanned_file(source_path)]
        for name in scanned.module_views
    )


def nodes_run_at_import(node: ast.AST) -> Iterator[ast.AST]:
    """Yield every node evaluated as a module is imported (not in a function or lambda body).

    Module and class bodies run at import; so do decorators and default arguments (as
    tests/test_engine_context.py's ``calls_run_at_import`` walks them, for every node).

    Args:
        node: The node to search (a whole module, at the top).

    Yields:
        Each node, parents before children.

    """
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        evaluated_at_definition: list[ast.expr] = [
            *node.args.defaults,
            *(default for default in node.args.kw_defaults if default is not None),
        ]
        if not isinstance(node, ast.Lambda):
            evaluated_at_definition.extend(node.decorator_list)
        for expression in evaluated_at_definition:
            yield from nodes_run_at_import(expression)
        return
    yield node
    for child in ast.iter_child_nodes(node):
        yield from nodes_run_at_import(child)


def import_time_module_view_reads(*, source_path: Path, module_views: frozenset[str]) -> list[str]:
    """Return ``'<line>: <view>'`` for each module view imported or read as the file is imported.

    A module view answers the current context's object when it is read: read at import, it
    would bind the module to the default context's object for good (rule 2).

    Args:
        source_path: A Python file.
        module_views: The module views, as ``'<module>.<name>'`` (``engine_module_views``).

    Returns:
        The reads, by line.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'))
    module_name = module_name_of_file(source_path=source_path)
    is_package = source_path.stem == '__init__'
    bindings = import_bindings_of(tree=tree, module_name=module_name, is_package=is_package)
    reads: list[tuple[int, str]] = []
    for node in nodes_run_at_import(tree):
        if isinstance(node, ast.ImportFrom):
            imported_from = absolute_import_module(
                node=node, module_name=module_name, is_package=is_package
            )
            reads.extend(
                (node.lineno, f'{imported_from}.{alias.name}')
                for alias in node.names
                if f'{imported_from}.{alias.name}' in module_views
            )
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
            read = qualified_name(node=node, bindings=bindings, watched_modules=frozenset())
            if read in module_views:
                reads.append((node.lineno, read))
    return [f'{line}: {read}' for line, read in sorted(reads)]


def test_no_module_reads_a_context_as_it_is_imported():
    """Rule 2, over the engine and every workspace member: no context read, no module view."""
    module_views = engine_module_views()
    offenders = {
        allowlist_key: reads
        for allowlist_key, path in scanned_source_files(project_root=PROJECT_ROOT)
        if (
            reads := [
                *import_time_context_reads(source_path=path),
                *import_time_module_view_reads(source_path=path, module_views=module_views),
            ]
        )
    }

    assert offenders == {}


def test_the_import_time_scan_finds_module_view_reads(tmp_path):
    """Module-level and class-body reads of a module view; not function bodies or lazy imports."""
    planted_path = tmp_path / 'planted.py'
    planted_path.write_text(PLANTED_IMPORT_TIME_VIEW_READS, encoding='utf-8')

    assert import_time_module_view_reads(
        source_path=planted_path, module_views=engine_module_views()
    ) == [
        '4: glitchygames.performance.performance_manager',
        '6: glitchygames.performance.performance_manager',
        '7: glitchygames.performance.performance_manager',
        '14: glitchygames.performance.performance_manager',
    ]


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
    """Return the name of every slot the engine declares.

    Returns:
        The names.

    """
    engine_directory = PROJECT_ROOT / ENGINE_DIRECTORY
    return {
        name
        for path in sorted(engine_directory.rglob('*.py'))
        for name in declared_slot_names_in_source(source_path=path)
    }


def member_isolation_check_names(*, tests_directory: Path) -> set[str]:
    """Return the slot names a member's tests list in a ``MEMBER_ISOLATION_CHECKS`` dict literal.

    Read by AST, so no member is imported (the engine's tests never import one).

    Args:
        tests_directory: The member's tests.

    Returns:
        The names.

    """
    names: set[str] = set()
    for path in sorted(tests_directory.rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            match node:
                case (
                    ast.Assign(targets=[ast.Name(id=target_name)], value=value)
                    | ast.AnnAssign(target=ast.Name(id=target_name), value=value)
                ) if target_name == MEMBER_ISOLATION_CHECKS_NAME:
                    assert isinstance(value, ast.Dict), (
                        f'{path}:{node.lineno}: {MEMBER_ISOLATION_CHECKS_NAME} must be a dict'
                    )
                    for key in value.keys:
                        assert isinstance(key, ast.Constant) and isinstance(key.value, str), (
                            f'{path}:{node.lineno}: {MEMBER_ISOLATION_CHECKS_NAME} keys must be '
                            'strings'
                        )
                        names.add(key.value)
                case _:
                    pass
    return names


def member_slots_without_matching_checks(*, project_root: Path) -> list[str]:
    """Return each member slot without an isolation check in its tests, and each orphan check.

    A member's slots are checked in the member's own tests (``MEMBER_ISOLATION_CHECKS``), since the
    engine's ``ISOLATION_CHECKS`` may not import a member.

    Args:
        project_root: The repository.

    Returns:
        One line per mismatch, empty when every member slot has exactly its check.

    """
    findings: list[str] = []
    for member in workspace_members(project_root=project_root):
        slots = {
            name
            for package_directory in member.package_directories
            for path in sorted(package_directory.rglob('*.py'))
            for name in declared_slot_names_in_source(source_path=path)
        }
        checks = member_isolation_check_names(tests_directory=member.directory / 'tests')
        findings.extend(
            f'{member.distribution}: slot {name!r} has no isolation check'
            for name in sorted(slots - checks)
        )
        findings.extend(
            f'{member.distribution}: isolation check {name!r} names no slot'
            for name in sorted(checks - slots)
        )
    return findings


def test_every_engine_slot_has_an_isolation_check():
    """A slot added without a check here fails (every piece of state moved is proven)."""
    assert engine_slot_names() == set(ISOLATION_CHECKS)


def test_every_member_slot_has_an_isolation_check_in_its_own_tests():
    """Each member's slots and its ``MEMBER_ISOLATION_CHECKS`` name the same slots."""
    assert member_slots_without_matching_checks(project_root=PROJECT_ROOT) == []


def test_the_member_slot_scan_reads_bitmappy():
    """Not a vacuous pass: Bitmappy's onion skinning slot is found, with its check."""
    bitmappy = next(
        member
        for member in workspace_members(project_root=PROJECT_ROOT)
        if member.distribution == 'bitmappy'
    )

    assert 'bitmappy.onion_skinning.manager' in member_isolation_check_names(
        tests_directory=bitmappy.directory / 'tests'
    )


def test_a_member_slot_without_a_check_and_a_check_without_a_slot_are_both_found(tmp_path):
    """A planted member slot with no check, and a planted check naming no slot, are reported."""
    write_project_with_member_module(
        project_root=tmp_path,
        source=(
            'from glitchygames.engine_context import ContextSlot\n'
            "PLANTED = ContextSlot(name='space_game.planted', factory=list)\n"
        ),
    )
    tests_directory = tmp_path / 'src' / 'games' / 'space-game' / 'tests'
    tests_directory.mkdir()
    (tests_directory / 'test_space_game.py').write_text(
        "MEMBER_ISOLATION_CHECKS = {'space_game.orphan': None}\n", encoding='utf-8'
    )

    assert member_slots_without_matching_checks(project_root=tmp_path) == [
        "space-game: slot 'space_game.planted' has no isolation check",
        "space-game: isolation check 'space_game.orphan' names no slot",
    ]


def test_the_slot_scan_agrees_with_the_slots_declared_at_run_time():
    """The scan misses no slot: every engine slot declared at run time is in it."""
    declared_engine_slot_names = {
        slot.name for slot in declared_context_slots() if slot.name.startswith(ENGINE_SLOT_PREFIX)
    }

    assert declared_engine_slot_names == engine_slot_names()
