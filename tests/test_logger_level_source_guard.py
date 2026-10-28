"""No source sets a logger level; logging.basicConfig only where a command starts (BUGS.md #236).

The level is the command line's: ``--log-level`` (the engine's ``logging.basicConfig``,
``GameEngine.initialize_arguments``) sets the root logger's level, and a logger with a level of
its own ignores it. A module's ``logging.getLogger('game').setLevel(...)`` at import made every
``game.*`` logger of any process that imported it log what ``--log-level`` dropped (#235: the
serial Linux CI run killed at 2 GB); set at run time (Bitmappy's ``main()``, a handler's
``__init__``) it outlived the command line's level the same way. A ``logging.basicConfig`` at
import configures the root before the engine's own call, which then does nothing.

So this scans the engine's, every member's (tests/workspace_sources.py) and ``scripts/``'s
source (``level_settings`` says exactly what it finds): a logger's level set anywhere, logging
turned off anywhere, and logging configured where the module is imported. Configuring inside a
function is a command's own start (``glitchygames``'s, the sprite API server's, a script's
``main()``). A handler's level is its own (a receiver whose source names a handler).

What an AST scan cannot see: a call it cannot resolve by name (a function assigned to another
name, ``logging.basicConfig`` stored in a variable, a level set in another module's function
called at import, a method called at import, ``exec`` or ``importlib`` of a string), a
receiver named otherwise than it is (a handler not named handler is flagged; a logger named
like one is not), and configuration from the environment. Three other checks cover what it
cannot: the import guard (tests/test_logger_levels_at_import.py) checks what importing every
engine and member module really does; the collection check (tests/collection_logger_levels.py)
that every ``game*``/``glitchygames*`` logger is still at NOTSET, and logging not disabled, once
the suite has imported everything it collects, ``scripts/`` included; the replay guard
(tests/replay/test_replays_log_quietly.py) what a replay really emits.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

import pytest

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


# Calls that configure logging: a command's own start may make them, never an import
CONFIGURING_CALLS = frozenset({'basicConfig', 'dictConfig', 'fileConfig'})
# What sets a level or turns logging off wherever it is
LEVEL_METHOD = 'setLevel'
LEVEL_ATTRIBUTE = 'level'
DISABLE = 'disable'
# A receiver whose source holds this is a handler, whose level is its own business
HANDLER_MARK = 'handler'


def _is_handler(receiver: ast.expr) -> bool:
    """Tell whether an expression is a handler (``console_handler``, ``StreamHandler()``).

    Returns:
        True when its source names a handler.

    """
    return HANDLER_MARK in ast.unparse(receiver).lower()


def _logging_aliases(tree: ast.Module) -> dict[str, str]:
    """Return the names a module imports logging's configuring functions under.

    ``from logging import basicConfig as configure`` makes ``configure`` mean ``basicConfig``.

    Returns:
        Each local name -> the function it is.

    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or '').startswith('logging'):
            for imported in node.names:
                if imported.name in CONFIGURING_CALLS | {DISABLE}:
                    aliases[imported.asname or imported.name] = imported.name
    return aliases


class _LevelSettingScan:
    """Walks a module, knowing at each node whether it runs at import."""

    def __init__(self, *, tree: ast.Module) -> None:
        """Scan nothing yet.

        Args:
            tree: The module's syntax tree.

        """
        self.tree = tree
        self.aliases = _logging_aliases(tree)
        self.module_functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # Module functions a call at import runs, so their bodies run at import too
        self.import_time_functions: set[str] = set()
        self.called_at_import: set[str] = set()
        self.found: set[tuple[int, str]] = set()

    def scan(self) -> list[tuple[int, str]]:
        """Walk until the functions run at import stop growing, then return the findings.

        Returns:
            ``(line, what)`` for each finding, in line order.

        """
        while True:
            self.called_at_import = set()
            self.found = set()
            for statement in self.tree.body:
                self.visit(statement, at_import=True)
            grown = self.import_time_functions | (
                self.called_at_import & set(self.module_functions)
            )
            if grown == self.import_time_functions:
                return sorted(self.found)
            self.import_time_functions = grown

    def visit(self, node: ast.AST, *, at_import: bool) -> None:
        """Note what a node does, then visit its children.

        Args:
            node: The node.
            at_import: Whether it runs when the module is imported.

        """
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.visit_function(node, at_import=at_import)
            return
        if isinstance(node, ast.Lambda):
            self.visit(node.body, at_import=False)
            return
        if isinstance(node, ast.If) and at_import and _is_main_guard(node):
            self.visit(node.test, at_import=at_import)
            for statement in node.body:
                self.visit(statement, at_import=False)
            for statement in node.orelse:
                self.visit(statement, at_import=at_import)
            return
        if isinstance(node, ast.Call):
            self.note_call(node, at_import=at_import)
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                self.note_assignment(target)
        for child in ast.iter_child_nodes(node):
            self.visit(child, at_import=at_import)

    def visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, at_import: bool
    ) -> None:
        """Visit a function: its decorators and defaults where it is defined, its body if run.

        Decorators and defaults run where the function is defined; the body runs when it is
        called (at import, when a call at import runs this module function).
        """
        for evaluated in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
            if evaluated is not None:
                self.visit(evaluated, at_import=at_import)
        body_at_import = node.name in self.import_time_functions and node in (
            self.module_functions.values()
        )
        for statement in node.body:
            self.visit(statement, at_import=body_at_import)

    def note_call(self, call: ast.Call, *, at_import: bool) -> None:
        """Note a call that sets a level, turns logging off, or configures it at import."""
        function = call.func
        if isinstance(function, ast.Lambda) and at_import:
            # Called where it stands: its body runs now
            self.visit(function.body, at_import=True)
        if isinstance(function, ast.Name):
            self.note_name_call(call, name=function.id, at_import=at_import)
            return
        if not isinstance(function, ast.Attribute):
            return
        if function.attr == LEVEL_METHOD and not _is_handler(function.value):
            self.found.add((call.lineno, LEVEL_METHOD))
        elif function.attr == DISABLE and ast.unparse(function.value) == 'logging':
            self.found.add((call.lineno, 'logging.disable'))
        elif function.attr in CONFIGURING_CALLS and at_import:
            self.found.add((call.lineno, f'{function.attr} at import'))

    def note_name_call(self, call: ast.Call, *, name: str, at_import: bool) -> None:
        """Note a call of a bare name: an imported logging function, getattr or setattr."""
        if at_import:
            self.called_at_import.add(name)
        imported = self.aliases.get(name)
        if imported == DISABLE:
            self.found.add((call.lineno, 'logging.disable'))
        elif imported is not None and at_import:
            self.found.add((call.lineno, f'{imported} at import'))
        elif name == 'getattr' and self._names(call, position=1, name=LEVEL_METHOD):
            self.found.add((call.lineno, 'setLevel through getattr'))
        elif name == 'setattr' and self._names(call, position=1, name=LEVEL_ATTRIBUTE):
            self.found.add((call.lineno, 'level assigned'))

    def note_assignment(self, target: ast.expr) -> None:
        """Note an assignment to a logger's ``level`` or to the logging manager's ``disable``."""
        if not isinstance(target, ast.Attribute):
            return
        if target.attr == LEVEL_ATTRIBUTE and not _is_handler(target.value):
            self.found.add((target.lineno, 'level assigned'))
        elif target.attr == DISABLE and ast.unparse(target.value).endswith('manager'):
            self.found.add((target.lineno, 'logging.disable'))

    @staticmethod
    def _names(call: ast.Call, *, position: int, name: str) -> bool:
        """Tell whether a call's argument at ``position`` is the string ``name``.

        Returns:
            True when it is.

        """
        if len(call.args) <= position:
            return False
        argument = call.args[position]
        return isinstance(argument, ast.Constant) and argument.value == name


def level_settings(*, source: str) -> list[str]:
    """Return a module's level settings and import-time logging configuration.

    Found wherever they are: a ``setLevel`` call (also through ``getattr``) or a ``level``
    assignment (also through ``setattr``) on anything but a handler, and ``logging.disable``
    (or the manager's ``disable``). Found at import only: ``basicConfig``, ``dictConfig`` and
    ``fileConfig`` (under any name they are imported as) in the module body, a class body, a
    decorator, a default argument, a lambda called where it stands, or a module function a call
    at import runs (and the functions it runs), outside ``if __name__ == '__main__':``.

    Args:
        source: The module's source.

    Returns:
        ``line N: <what>`` for each, in line order.

    """
    found = _LevelSettingScan(tree=ast.parse(source)).scan()
    return [f'line {line}: {what}' for line, what in found]


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


def shifted_by_the_import(*, finding: str) -> str:
    """Return a finding one line further down (the scanned source starts with an import).

    Returns:
        ``line N+1: <what>``.

    """
    line, what = finding.removeprefix('line ').split(': ', 1)
    return f'line {int(line) + 1}: {what}'


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ("getattr(LOG, 'setLevel')(10)\n", ['line 1: setLevel through getattr']),
        ('LOG.level = 10\n', ['line 1: level assigned']),
        ("setattr(LOG, 'level', 10)\n", ['line 1: level assigned']),
        ('logging.disable(logging.INFO)\n', ['line 1: logging.disable']),
        ('logging.root.manager.disable = 50\n', ['line 1: logging.disable']),
        ("logging.config.dictConfig({'version': 1})\n", ['line 1: dictConfig at import']),
        ("logging.config.fileConfig('x.ini')\n", ['line 1: fileConfig at import']),
        (
            'from logging import basicConfig as configure\nconfigure(level=10)\n',
            ['line 2: basicConfig at import'],
        ),
        (
            'def _setup():\n    logging.basicConfig(level=10)\n_setup()\n',
            ['line 2: basicConfig at import'],
        ),
        (
            'def _setup():\n    logging.basicConfig()\ndef _outer():\n    _setup()\n_outer()\n',
            ['line 2: basicConfig at import'],
        ),
        (
            'def tag(function=logging.basicConfig()):\n    return function\n',
            ['line 1: basicConfig at import'],
        ),
        (
            '@decorate(logging.basicConfig())\ndef main():\n    pass\n',
            ['line 1: basicConfig at import'],
        ),
        ('(lambda: logging.basicConfig())()\n', ['line 1: basicConfig at import']),
        ('class Game:\n    logging.basicConfig()\n', ['line 2: basicConfig at import']),
        # Not import time: a command's own start, and a main guard written either way round
        ('def main():\n    logging.basicConfig()\n', []),
        ("if '__main__' == __name__:\n    logging.basicConfig()\n", []),
        ("if True:\n    if __name__ == '__main__':\n        logging.basicConfig()\n", []),
        # A handler's level is not a logger's
        ('handler = logging.StreamHandler()\nhandler.setLevel(logging.INFO)\n', []),
        ('logging.StreamHandler().setLevel(logging.INFO)\n', []),
        ('self.console_handler.level = 10\n', []),
    ],
    ids=[
        'getattr',
        'level attribute',
        'setattr level',
        'logging.disable',
        'manager.disable',
        'dictConfig',
        'fileConfig',
        'aliased basicConfig',
        'helper called at import',
        'helper of a helper',
        'default argument',
        'decorator',
        'called lambda',
        'class body',
        'in a function',
        'main guard reversed',
        'nested main guard',
        'handler variable',
        'handler call',
        'handler attribute',
    ],
)
def test_the_scan_sees_through_the_ways_round_it(source, expected):
    """Each way a level can be set or logging configured, as far as an AST scan can follow."""
    assert level_settings(source=f'import logging\n{source}') == [
        shifted_by_the_import(finding=finding) for finding in expected
    ]
