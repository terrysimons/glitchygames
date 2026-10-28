"""No source sets a logger level; logging.basicConfig only where a command starts (BUGS.md #236).

The level is the command line's: ``--log-level`` (the engine's ``logging.basicConfig``,
``GameEngine.initialize_arguments``) sets the root logger's level, and a logger with a level of
its own ignores it. A module's ``logging.getLogger('game').setLevel(...)`` at import made every
``game.*`` logger of any process that imported it log what ``--log-level`` dropped (#235: the
serial Linux CI run killed at 2 GB); set at run time (Bitmappy's ``main()``, a handler's
``__init__``) it outlived the command line's level the same way. A ``logging.basicConfig`` at
import configures the root before the engine's own call, which then does nothing.

So this scans the engine's, every member's (tests/workspace_sources.py) and ``scripts/``'s
source and fails on any ``.setLevel(...)`` call, and on a ``basicConfig(...)`` call that runs at
import: outside every function and outside ``if __name__ == '__main__':``. Inside a function it
is a command's own start (``glitchygames``'s, the sprite API server's, a script's ``main()``).
The import guard (tests/test_logger_levels_at_import.py) checks what imports really do; the
replay guard (tests/replay/test_replays_log_quietly.py) what a replay really emits; this
catches run-time settings neither can reach.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files, write_project_with_member_module

if TYPE_CHECKING:
    from pathlib import Path

SCRIPTS_DIRECTORY = 'scripts'

OFFENDING_SOURCE = """\
import logging

logging.getLogger('game').setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger('game.space')


class Handler:
    def __init__(self, level):
        LOG.setLevel(level)


def main():
    logging.basicConfig(level=logging.INFO)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
"""


def _is_main_guard(node: ast.If) -> bool:
    """Tell whether an ``if`` is ``if __name__ == '__main__':``.

    Returns:
        True for that test, either way round.

    """
    test = node.test
    if not isinstance(test, ast.Compare) or len(test.comparators) != 1:
        return False
    sides = [test.left, test.comparators[0]]
    names = [side.id for side in sides if isinstance(side, ast.Name)]
    constants = [side.value for side in sides if isinstance(side, ast.Constant)]
    return names == ['__name__'] and constants == ['__main__']


def _called_name(call: ast.Call) -> str | None:
    """Return the attribute or name a call calls (``setLevel``, ``basicConfig``).

    Returns:
        The name, or None for any other callee.

    """
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def level_settings(*, source: str) -> list[str]:
    """Return a module's level settings: every ``setLevel`` call, every import-time ``basicConfig``.

    Args:
        source: The module's source.

    Returns:
        ``line N: setLevel`` or ``line N: basicConfig at import`` for each, in line order.

    """
    found: list[tuple[int, str]] = []

    def visit(node: ast.AST, *, at_import: bool) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            at_import = False
        elif isinstance(node, ast.If) and at_import and _is_main_guard(node):
            for child in node.body:
                visit(child, at_import=False)
            for child in node.orelse:
                visit(child, at_import=at_import)
            visit(node.test, at_import=at_import)
            return
        if isinstance(node, ast.Call):
            name = _called_name(node)
            if name == 'setLevel':
                found.append((node.lineno, 'setLevel'))
            elif name == 'basicConfig' and at_import:
                found.append((node.lineno, 'basicConfig at import'))
        for child in ast.iter_child_nodes(node):
            visit(child, at_import=at_import)

    visit(ast.parse(source), at_import=True)
    return [f'line {line}: {what}' for line, what in sorted(found)]


def scanned_files(*, project_root: Path) -> list[tuple[str, Path]]:
    """Return the engine's and members' source files, then ``scripts/``'s.

    Returns:
        ``(key, path)`` for each: the engine's relative to its package, the others to the
        repository.

    """
    scripts = sorted((project_root / SCRIPTS_DIRECTORY).rglob('*.py'))
    return [
        *scanned_source_files(project_root=project_root),
        *((path.relative_to(project_root).as_posix(), path) for path in scripts),
    ]


def project_level_settings(*, project_root: Path) -> list[str]:
    """Return every level setting in a project's scanned source.

    Returns:
        ``<key> line N: <what>`` for each.

    """
    return [
        f'{key} {setting}'
        for key, path in scanned_files(project_root=project_root)
        for setting in level_settings(source=path.read_text(encoding='utf-8'))
    ]


def test_no_source_sets_a_logger_level_or_configures_logging_at_import():
    """The engine, every member and every script leave the level to the command line."""
    assert project_level_settings(project_root=PROJECT_ROOT) == []


def test_every_kind_of_level_setting_is_found():
    """Import-time and run-time setLevel and an import-time basicConfig; a command's is not."""
    assert level_settings(source=OFFENDING_SOURCE) == [
        'line 3: setLevel',
        'line 4: basicConfig at import',
        'line 10: setLevel',
    ]


def test_a_members_level_setting_is_named_by_its_repository_path(tmp_path):
    """A member module is scanned too, and reported under its path from the repository."""
    member_key = write_project_with_member_module(project_root=tmp_path, source=OFFENDING_SOURCE)

    assert project_level_settings(project_root=tmp_path) == [
        f'{member_key} line 3: setLevel',
        f'{member_key} line 4: basicConfig at import',
        f'{member_key} line 10: setLevel',
    ]


def test_scripts_are_scanned(tmp_path):
    """A script that sets a level at import is named under scripts/."""
    write_project_with_member_module(project_root=tmp_path, source='')
    (tmp_path / SCRIPTS_DIRECTORY).mkdir()
    (tmp_path / SCRIPTS_DIRECTORY / 'demo.py').write_text(
        "import logging\nlogging.getLogger('game').setLevel(logging.DEBUG)\n", encoding='utf-8'
    )

    assert project_level_settings(project_root=tmp_path) == ['scripts/demo.py line 2: setLevel']
