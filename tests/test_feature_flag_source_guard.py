"""No feature switch is a constant, and no module reads a feature flag as it is imported.

A feature is switched by a declared flag (glitchygames/feature_flags.py, whose docstring is the
contract; plans/2026-11-24-feature-flags-and-lucid-circuit-switch.md, "The guard"), read where it
is used: a constant, or a flag read at import, is set before any command line is, and is every
game's in the process. The scan reads the engine's and every workspace member's source
(tests/workspace_sources.py), so it is a test of this repository.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Self, override

import pytest

from tests.ast_scanning import PROJECT_ROOT
from tests.workspace_sources import scanned_source_files, write_project_with_member_module

if TYPE_CHECKING:
    from pathlib import Path

# The one module that may name a constant so: it declares FEATURE_FLAGS
DECLARING_MODULE = 'feature_flags.py'
# Looks like a feature switch by its name, and is not one: (module, Class.name) -> why
ALLOWED_NAMES: dict[tuple[str, str], str] = {
    ('game_objects/ball.py', 'BallSpawnMode.SPEED_CHECK_ENABLED'): (
        'an int bit mask, one of BallSpawnMode (a plain class of them), which a game combines into '
        'the value it passes: it switches nothing by itself'
    ),
    ('game_objects/ball.py', 'BallSpawnMode.COOLDOWN_ENABLED'): 'another of its bit masks',
}

# Each reads the flags, or a feature's gate on one, of the engine context current at the call
FLAG_READERS = frozenset({
    'ai_off_reason',
    'flag_state',
    'flag_state_lines',
    'reason_lucid_circuit_is_off',
})

# Far fewer than there are, and far more than one package holds: a scan below it lost its files
MINIMUM_ENGINE_FILES = 150
MINIMUM_MEMBER_FILES = 100


def looks_like_a_feature_switch(*, name: str) -> bool:
    """Return whether a constant is named as a feature switch is (a private one too)."""
    bare_name = name.lstrip('_')
    return bare_name.endswith('_ENABLED') or bare_name.startswith(('ENABLE_', 'FEATURE_'))


def flag_reader_names(*, tree: ast.Module) -> frozenset[str]:
    """Return the names a module calls a flag reader by, as far as the scan follows them.

    Their own names, one it is imported as (``from glitchygames.feature_flags import flag_state as
    read``, or relatively), and one it is assigned to (``read = feature_flags.flag_state``), at
    any level, through a chain of them in any order.
    """
    names = set(FLAG_READERS)
    renames: list[tuple[str, ast.expr]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(
                alias.asname
                for alias in node.names
                if alias.name in FLAG_READERS and alias.asname is not None
            )
        elif isinstance(node, ast.Assign):
            renames.extend(
                (target.id, node.value) for target in node.targets if isinstance(target, ast.Name)
            )
        elif (
            isinstance(node, (ast.AnnAssign, ast.NamedExpr))
            and node.value is not None
            and isinstance(node.target, ast.Name)
        ):
            renames.append((node.target.id, node.value))
    found_another = True
    while found_another:
        found = {name for name, value in renames if _refers_to(value, names)} - names
        names |= found
        found_another = bool(found)
    return frozenset(names)


def _refers_to(node: ast.expr, names: set[str] | frozenset[str]) -> bool:
    # An attribute is a reader by its own name, whatever module or alias it is taken from
    if isinstance(node, ast.Attribute):
        return node.attr in FLAG_READERS
    return isinstance(node, ast.Name) and node.id in names


class ImportTimeScan(ast.NodeVisitor):
    """Visits what a module runs as it is imported, and keeps what the guard refuses.

    That is its module and class bodies, with what a function's definition runs (its decorators
    and default arguments), not the function's own body.

    Attributes:
        names: ``(line, column, name)`` for each name that looks like a feature switch, a class's
            with its classes (``Outer.Inner.NAME``).
        calls: ``(line, column, what)`` for each call of a flag reader.

    """

    def __init__(self: Self, *, readers: frozenset[str]) -> None:
        """Keep the names the module calls a flag reader by."""
        self.readers = readers
        self.class_names: list[str] = []
        self.names: list[tuple[int, int, str]] = []
        self.calls: list[tuple[int, int, str]] = []

    def check_name(
        self: Self,
        node: ast.stmt | ast.expr | ast.alias | ast.pattern | ast.ExceptHandler,
        name: str | None,
    ) -> None:
        """Keep a bound name that looks like a feature switch."""
        if name is not None and looks_like_a_feature_switch(name=name):
            qualified_name = '.'.join([*self.class_names, name])
            self.names.append((node.lineno, node.col_offset, qualified_name))

    @override
    def visit_Name(self: Self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.check_name(node, node.id)

    @override
    def visit_Attribute(self: Self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Store):
            self.check_name(node, node.attr)
        self.generic_visit(node)

    @override
    def visit_ExceptHandler(self: Self, node: ast.ExceptHandler) -> None:
        self.check_name(node, node.name)
        self.generic_visit(node)

    @override
    def visit_MatchAs(self: Self, node: ast.MatchAs) -> None:
        self.check_name(node, node.name)
        self.generic_visit(node)

    @override
    def visit_MatchStar(self: Self, node: ast.MatchStar) -> None:
        self.check_name(node, node.name)

    @override
    def visit_MatchMapping(self: Self, node: ast.MatchMapping) -> None:
        self.check_name(node, node.rest)
        self.generic_visit(node)

    @override
    def visit_alias(self: Self, node: ast.alias) -> None:
        # Imported under its own name, it is refused where it is declared
        self.check_name(node, node.asname)

    @override
    def visit_comprehension(self: Self, node: ast.comprehension) -> None:
        # Its target is the comprehension's own name, not the module's or the class's
        for expression in (node.iter, *node.ifs):
            self.visit(expression)

    @override
    def visit_Call(self: Self, node: ast.Call) -> None:
        if _refers_to(node.func, self.readers):
            self.calls.append((
                node.lineno,
                node.col_offset,
                f'{ast.unparse(node.func)}() at import',
            ))
        if isinstance(node.func, ast.Lambda):
            # Called where it is written, so its body runs too
            self.visit(node.func.body)
        self.generic_visit(node)

    @override
    def visit_Lambda(self: Self, node: ast.Lambda) -> None:
        self.visit_defaults(node.args)

    @override
    def visit_FunctionDef(self: Self, node: ast.FunctionDef) -> None:
        self.visit_definition(node)

    @override
    def visit_AsyncFunctionDef(self: Self, node: ast.AsyncFunctionDef) -> None:
        self.visit_definition(node)

    @override
    def visit_ClassDef(self: Self, node: ast.ClassDef) -> None:
        self.check_name(node, node.name)
        # Its decorators and bases run outside it
        for expression in (*node.decorator_list, *node.bases, *node.keywords):
            self.visit(expression)
        self.class_names.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.class_names.pop()

    def visit_definition(self: Self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Visit what defining a function runs."""
        self.check_name(node, node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        self.visit_defaults(node.args)

    def visit_defaults(self: Self, arguments: ast.arguments) -> None:
        """Visit a function's default arguments."""
        for default in (*arguments.defaults, *arguments.kw_defaults):
            if default is not None:
                self.visit(default)


def feature_switches(source_path: Path, *, allowlist_key: str) -> list[str]:
    """List each feature switch that is a constant, and each flag read at import, in a module.

    A name is refused where the module or a class binds it by an assignment (a tuple's, an
    annotated one, an augmented one, a walrus), a loop, a ``match`` capture, ``except ... as``, an
    import's ``as``, a function's or class's definition, or an attribute set (``settings.X``), and
    where a function declares it ``global``. A call that runs at import is refused under the names
    ``flag_reader_names`` finds, and as an attribute so named.

    Not detected:

    - Names: one set through ``setattr`` or ``globals()``, or on a class by its method
      (``cls.X_ENABLED = ...``); a functional enum's (``Enum('Mode', 'X_ENABLED')``).
    - Calls: a reader passed to something that calls it (``map``, ``functools.partial``); an alias
      made by a conditional (``read = flag_state if ... else ...``) or a tuple (``read, other =
      flag_state, ...``); a lambda called through a name; and any other function that reads a
      flag, called as the module is imported, but for the ``FLAG_READERS``.

    Args:
        source_path: The Python file to scan.
        allowlist_key: How the allowlist and ``DECLARING_MODULE`` spell the file.

    Returns:
        ``<path>:<line> <what>`` for each, in source order.

    """
    tree = ast.parse(source_path.read_text(encoding='utf-8'), filename=str(source_path))
    scan = ImportTimeScan(readers=flag_reader_names(tree=tree))
    scan.visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names:
                scan.check_name(node, name)
    refused_names = [
        found
        for found in scan.names
        if allowlist_key != DECLARING_MODULE and (allowlist_key, found[-1]) not in ALLOWED_NAMES
    ]
    return [
        f'{source_path}:{line} {what}'
        for line, _column, what in sorted([*refused_names, *scan.calls])
    ]


def scan_source(tmp_path: Path, source: str, *, allowlist_key: str = 'planted.py') -> list[str]:
    """Scan a planted module.

    Returns:
        ``<line> <what>`` for each offender.

    """
    source_path = tmp_path / 'planted.py'
    source_path.write_text(source, encoding='utf-8')
    return [
        offender.removeprefix(f'{source_path}:')
        for offender in feature_switches(source_path, allowlist_key=allowlist_key)
    ]


def test_no_feature_switch_is_a_constant_and_no_flag_is_read_at_import():
    """The engine's and every member's source: declare a flag, and read it where it is used.

    It counts the files it read, so a scan that read none, or lost a package, does not pass.
    """
    offenders: list[str] = []
    keys: list[str] = []
    for allowlist_key, source_path in scanned_source_files(project_root=PROJECT_ROOT):
        offenders.extend(feature_switches(source_path, allowlist_key=allowlist_key))
        keys.append(allowlist_key)

    member_keys = [key for key in keys if key.startswith('src/')]
    assert offenders == []
    assert len(keys) - len(member_keys) >= MINIMUM_ENGINE_FILES
    assert len(member_keys) >= MINIMUM_MEMBER_FILES
    assert {DECLARING_MODULE, 'ai_link.py'} <= set(keys)
    assert 'src/apps/bitmappy/src/bitmappy/ai_manager.py' in keys


def test_every_allowed_name_is_still_there(mocker):
    """An allowlist entry whose name is gone goes too."""
    allowed = dict(ALLOWED_NAMES)
    mocker.patch.dict(ALLOWED_NAMES, clear=True)
    found = {
        (key, offender.rpartition(' ')[2])
        for key, source_path in scanned_source_files(project_root=PROJECT_ROOT)
        for offender in feature_switches(source_path, allowlist_key=key)
    }

    assert found == set(allowed)


def test_a_switch_in_a_member_is_reported_under_its_repository_path(tmp_path):
    """The walk reads a member's file."""
    member_key = write_project_with_member_module(
        project_root=tmp_path, source='import sys\n\nAI_ENABLED = sys.platform != "emscripten"\n'
    )

    offenders = {
        key: found
        for key, source_path in scanned_source_files(project_root=tmp_path)
        if (found := feature_switches(source_path, allowlist_key=key))
    }

    assert list(offenders) == [member_key]
    assert offenders[member_key][0].endswith(':3 AI_ENABLED')


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        ('AI_ENABLED = True', ['1 AI_ENABLED']),
        ('ENABLE_AI = True', ['1 ENABLE_AI']),
        ('FEATURE_AI = True', ['1 FEATURE_AI']),
        ('_AI_ENABLED = True', ['1 _AI_ENABLED']),
        ('_ENABLE_AI = _FEATURE_AI = True', ['1 _ENABLE_AI', '1 _FEATURE_AI']),
        ('AI_ENABLED: bool = True', ['1 AI_ENABLED']),
        ('AI_ENABLED: bool', ['1 AI_ENABLED']),
        ('AI_ENABLED = 1\nAI_ENABLED += 1', ['1 AI_ENABLED', '2 AI_ENABLED']),
        ('A = AI_ENABLED = True', ['1 AI_ENABLED']),
        ('A, (ENABLE_B, *FEATURE_C) = 1, (2, 3)', ['1 ENABLE_B', '1 FEATURE_C']),
        ('print(AI_ENABLED := True)', ['1 AI_ENABLED']),
        ('if True:\n    AI_ENABLED = True', ['2 AI_ENABLED']),
        ('try:\n    AI_ENABLED = True\nfinally:\n    pass', ['2 AI_ENABLED']),
        ('for AI_ENABLED in (1,):\n    pass', ['1 AI_ENABLED']),
        ('class A:\n    class B:\n        AI_ENABLED = True', ['3 A.B.AI_ENABLED']),
        ('match 1:\n    case AI_ENABLED:\n        pass', ['2 AI_ENABLED']),
        ('match 1:\n    case [*AI_ENABLED]:\n        pass', ['2 AI_ENABLED']),
        ('match 1:\n    case {**AI_ENABLED}:\n        pass', ['2 AI_ENABLED']),
        ('try:\n    pass\nexcept ValueError as AI_ENABLED:\n    pass', ['3 AI_ENABLED']),
        # Reported in the source's order, though a function's global is found after the rest
        (
            'def f():\n    global B_ENABLED\nA_ENABLED = flag_state(name="a")',
            ['2 B_ENABLED', '3 A_ENABLED', '3 flag_state() at import'],
        ),
        ('from settings import AI as AI_ENABLED', ['1 AI_ENABLED']),
        ('import settings.ai as FEATURE_AI', ['1 FEATURE_AI']),
        ('import settings\nsettings.AI_ENABLED = True', ['2 AI_ENABLED']),
        ('def ENABLE_AI():\n    pass', ['1 ENABLE_AI']),
        ('class FEATURE_AI:\n    pass', ['1 FEATURE_AI']),
        ('def turn_on():\n    global AI_ENABLED\n    AI_ENABLED = True', ['2 AI_ENABLED']),
    ],
)
def test_a_feature_switch_that_is_a_constant_is_found(tmp_path, source, expected):
    """Each way ``feature_switches`` says it finds one."""
    assert scan_source(tmp_path, f'{source}\n') == expected


@pytest.mark.parametrize(
    'source',
    [
        'def use():\n    AI_ENABLED = True\n    return AI_ENABLED',
        'class A:\n    def use(self):\n        self.AI_ENABLED = True',
        'ai_enabled = True',
        'ENABLED = True',
        'DISABLED_FEATURE = FEATURES = THE_FEATURE_NAME = AI_ENABLED_REASON = True',
        'A = [AI_ENABLED for AI_ENABLED in (1, 2)]',
        'import settings\nprint(settings.AI_ENABLED)',
        'from settings import AI_ENABLED',
    ],
)
def test_another_name_passes(tmp_path, source):
    """A function's own, one that only resembles a switch, and one only read or imported."""
    assert scan_source(tmp_path, f'{source}\n') == []


def test_only_the_flags_own_module_names_its_constants_so(tmp_path):
    """Its calls are not exempt, and neither is a member's module of the same file name."""
    source = 'FEATURE_FLAGS = {}\nSTATE = flag_state(name="a")\n'

    assert scan_source(tmp_path, source, allowlist_key=DECLARING_MODULE) == [
        '2 flag_state() at import'
    ]
    assert scan_source(
        tmp_path, source, allowlist_key='src/apps/bitmappy/src/bitmappy/feature_flags.py'
    ) == ['1 FEATURE_FLAGS', '2 flag_state() at import']


def test_a_name_is_allowed_only_in_its_own_class(tmp_path):
    """The module's own constant, or another class's, of an allowed name is refused."""
    source = (
        'class BallSpawnMode:\n    COOLDOWN_ENABLED = 1 << 5\n'
        'class Ball:\n    COOLDOWN_ENABLED = True\n'
        'COOLDOWN_ENABLED = True\n'
        'class Outer:\n    class BallSpawnMode:\n        COOLDOWN_ENABLED = True\n'
    )

    assert scan_source(tmp_path, source, allowlist_key='game_objects/ball.py') == [
        '4 Ball.COOLDOWN_ENABLED',
        '5 COOLDOWN_ENABLED',
        '8 Outer.BallSpawnMode.COOLDOWN_ENABLED',
    ]


DIRECT_IMPORT = 'from glitchygames.feature_flags import flag_state\n'


@pytest.mark.parametrize(
    ('source', 'expected'),
    [
        (f'{DIRECT_IMPORT}AI = flag_state(name="a")', '2 flag_state'),
        (f'{DIRECT_IMPORT}AI = flag_state(name="a").on', '2 flag_state'),
        (f'{DIRECT_IMPORT}if flag_state(name="a").on:\n    import os', '2 flag_state'),
        (f'{DIRECT_IMPORT}class A:\n    on = flag_state(name="a")', '3 flag_state'),
        (f'{DIRECT_IMPORT}class A(base(flag_state(name="a"))):\n    pass', '2 flag_state'),
        (f'{DIRECT_IMPORT}@only_if(flag_state(name="a"))\ndef f():\n    pass', '2 flag_state'),
        (f'{DIRECT_IMPORT}@only_if(flag_state(name="a"))\nclass A:\n    pass', '2 flag_state'),
        (
            (
                f'{DIRECT_IMPORT}class A:\n    @only_if(flag_state(name="a"))\n'
                '    def f(self):\n        pass'
            ),
            '3 flag_state',
        ),
        (f'{DIRECT_IMPORT}def f(on=flag_state(name="a")):\n    pass', '2 flag_state'),
        (f'{DIRECT_IMPORT}def f(*, on=flag_state(name="a")):\n    pass', '2 flag_state'),
        (f'{DIRECT_IMPORT}async def f(on=flag_state(name="a")):\n    pass', '2 flag_state'),
        (f'{DIRECT_IMPORT}f = lambda on=flag_state(name="a"): on', '2 flag_state'),
        (f'{DIRECT_IMPORT}AI = (lambda: flag_state(name="a"))()', '2 flag_state'),
        (f'{DIRECT_IMPORT}AI = [flag_state(name=name) for name in NAMES]', '2 flag_state'),
        (f'{DIRECT_IMPORT}AI = [on for on in flag_state(name="a")]', '2 flag_state'),
        (f'{DIRECT_IMPORT}AI = [on for on in NAMES if flag_state(name=on)]', '2 flag_state'),
        (f'{DIRECT_IMPORT}read = flag_state\nAI = read(name="a")', '3 read'),
        # The alias is followed whatever order the assignments are written in
        (
            (
                f'{DIRECT_IMPORT}def f():\n    global two\n    two = one\none = flag_state\n'
                'f()\nAI = two(name="a")'
            ),
            '7 two',
        ),
        (
            (
                'from glitchygames.ai_link import reason_lucid_circuit_is_off\n'
                'AI = reason_lucid_circuit_is_off(options={}, in_replay=False)'
            ),
            '2 reason_lucid_circuit_is_off',
        ),
        (
            'from bitmappy import ai_manager\nAI = ai_manager.ai_off_reason()',
            '2 ai_manager.ai_off_reason',
        ),
        (f'{DIRECT_IMPORT}one = flag_state\ntwo = one\nAI = two(name="a")', '4 two'),
        (f'{DIRECT_IMPORT}read: object = flag_state\nAI = read(name="a")', '3 read'),
        (f'{DIRECT_IMPORT}AI = (read := flag_state) and read(name="a")', '2 read'),
        (
            'from glitchygames.feature_flags import flag_state as read\nAI = read(name="a")',
            '2 read',
        ),
        ('from .feature_flags import flag_state as read\nAI = read(name="a")', '2 read'),
        ('from glitchygames.feature_flags import *\nAI = flag_state(name="a")', '2 flag_state'),
        (
            'from glitchygames.feature_flags import flag_state_lines\nAI = flag_state_lines()',
            '2 flag_state_lines',
        ),
        (
            'from glitchygames import feature_flags\nAI = feature_flags.flag_state(name="a")',
            '2 feature_flags.flag_state',
        ),
        (
            'from . import feature_flags as flags\nAI = flags.flag_state(name="a")',
            '2 flags.flag_state',
        ),
        (
            (
                'import glitchygames.feature_flags\n'
                'AI = glitchygames.feature_flags.flag_state(name="a")'
            ),
            '2 glitchygames.feature_flags.flag_state',
        ),
        (
            'import glitchygames.feature_flags as flags\nAI = flags.flag_state(name="a")',
            '2 flags.flag_state',
        ),
        (
            (
                'import glitchygames.feature_flags as flags\nread = flags.flag_state\n'
                'AI = read(name="a")'
            ),
            '3 read',
        ),
    ],
)
def test_a_flag_read_at_import_is_found(tmp_path, source, expected):
    """At module or class level, in a decorator or a default, under any name."""
    assert scan_source(tmp_path, f'{source}\n') == [f'{expected}() at import']


@pytest.mark.parametrize(
    'body',
    [
        'def f():\n    return flag_state(name="a")',
        'async def f():\n    return flag_state(name="a")',
        'class A:\n    def f(self):\n        return flag_state(name="a").on',
        'f = lambda: flag_state(name="a")',
        'def f():\n    def g(on=flag_state(name="a")):\n        return on\n    return g()',
        'class A:\n    read = staticmethod(flag_state)',
        'read = flag_state\ndef f():\n    return read(name="a")',
    ],
)
def test_a_flag_read_where_it_is_used_passes(tmp_path, body):
    """Inside a function, however deep; naming the reader without calling it is no read."""
    assert scan_source(tmp_path, f'{DIRECT_IMPORT}{body}\n') == []
