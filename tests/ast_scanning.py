"""Shared AST helpers for the package guard scans.

Resolve a name or attribute chain in a module's source to the fully qualified name it refers
to, following imports and aliases of the watched modules. The randomness guard
(tests/test_unseeded_randomness_guard.py) and the engine-doors guard
(tests/test_engine_doors.py) each pass their own set of watched modules. ``member_imports``
finds every import of a workspace member, for the guards that the engine's source
(tests/test_workspace_config.py) and the engine's tests (tests/test_suite_collection.py) import
none.

It imports no ``scripts.*`` (Part 3, Stage D, Task D9): what reads the workspace (the files the
source guards scan, the members' packages) is in tests/workspace_sources.py.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Self

if TYPE_CHECKING:
    from collections.abc import Mapping

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def import_bindings(*, tree: ast.Module, watched_modules: frozenset[str]) -> dict[str, str]:
    """Map each local name bound to a watched module (or a name in one) to its qualified name.

    ``import random as r`` binds ``r`` to ``random``; ``import numpy.random`` binds
    ``numpy``; ``from numpy import random as nr`` binds ``nr`` to ``numpy.random``;
    ``from random import Random`` binds ``Random`` to ``random.Random``. Bindings are
    module-wide: an import inside a function counts too, and shadowing is ignored.

    Args:
        tree: The parsed module.
        watched_modules: The modules whose bindings are followed.

    Returns:
        Local name -> fully qualified name.

    """
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None and alias.name in watched_modules:
                    bindings[alias.asname] = alias.name
                elif alias.asname is None and alias.name.split('.')[0] in watched_modules:
                    top_level_name = alias.name.split('.')[0]
                    bindings[top_level_name] = top_level_name
        elif isinstance(node, ast.ImportFrom) and node.module in watched_modules:
            for alias in node.names:
                bindings[alias.asname or alias.name] = f'{node.module}.{alias.name}'
    return bindings


def dynamic_import_name(*, node: ast.expr, watched_modules: frozenset[str]) -> str | None:
    """Return the watched module ``__import__('<module>')`` imports, else None.

    Args:
        node: The expression to inspect.
        watched_modules: The modules a dynamic import is reported for.

    Returns:
        The imported module's name, or None if the node is not ``__import__`` of a watched module.

    """
    is_dynamic_import = (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == '__import__'
        and bool(node.args)
    )
    if not is_dynamic_import:
        return None
    assert isinstance(node, ast.Call)
    module_argument = node.args[0]
    if isinstance(module_argument, ast.Constant) and module_argument.value in watched_modules:
        return str(module_argument.value)
    return None


def qualified_name(
    *, node: ast.expr, bindings: dict[str, str], watched_modules: frozenset[str]
) -> str | None:
    """Resolve a name or attribute chain through the import bindings.

    Args:
        node: The name, attribute chain or ``__import__`` call to resolve.
        bindings: The module's bindings, from ``import_bindings``.
        watched_modules: The modules ``__import__`` calls are resolved for.

    Returns:
        The fully qualified name (``random.uniform``), or None if it is not from a watched module.

    """
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute):
        owner = qualified_name(node=node.value, bindings=bindings, watched_modules=watched_modules)
        return None if owner is None else f'{owner}.{node.attr}'
    return dynamic_import_name(node=node, watched_modules=watched_modules)


# The calls that load (or, for find_spec, look up) a module named by a string. find_spec
# imports a dotted name's parent package, and a test that only looks a member up still
# depends on it, so it counts too
STRING_LOADS = frozenset({
    'builtins.__import__',
    'importlib.__import__',
    'importlib.import_module',
    'importlib.util.find_spec',
    'pytest.importorskip',
})

# The modules whose bindings resolve a STRING_LOADS call
STRING_LOAD_MODULES = frozenset({'builtins', 'importlib', 'importlib.util', 'pytest'})


class MemberImport(NamedTuple):
    """One import of a member's package in a module.

    Attributes:
        line: Its line.
        module: The module imported (``brave_adventurer.player``).
        name: The name a ``from`` import takes from it (``Player``); None for ``import`` and for a
            string load (``importlib.import_module('paddleslap')``).

    """

    line: int
    module: str
    name: str | None

    def describe(self: Self) -> str:
        """The import as the source spells it (``from brave_adventurer.player import Player``)."""
        if self.name is None:
            return f'import {self.module}'
        return f'from {self.module} import {self.name}'


def _string_loaded_module(*, call: ast.Call, bindings: dict[str, str]) -> str | None:
    """Return the module a call loads by a literal name, else None.

    Args:
        call: The call.
        bindings: The module's bindings of ``importlib``, from ``import_bindings``.

    Returns:
        The literal module name a ``STRING_LOADS`` call or ``__import__`` is given, else None.

    """
    is_dunder_import = isinstance(call.func, ast.Name) and call.func.id == '__import__'
    called = qualified_name(
        node=call.func, bindings=bindings, watched_modules=frozenset({'importlib'})
    )
    if not (is_dunder_import or called in STRING_LOADS) or not call.args:
        return None
    module_argument = call.args[0]
    if isinstance(module_argument, ast.Constant) and isinstance(module_argument.value, str):
        return module_argument.value
    return None


def member_imports(*, tree: ast.Module, member_packages: frozenset[str]) -> list[MemberImport]:
    """Return every import of a member package in a module, at any level, in line order.

    Module-level and function-level ``import`` and absolute ``from ... import`` count, and so does
    a string load (``importlib.import_module('<member>...')``, ``__import__('<member>...')``)
    with a literal name. A relative import is never a member's.

    Args:
        tree: The parsed module.
        member_packages: The members' import packages.

    Returns:
        The imports.

    """
    bindings = import_bindings(tree=tree, watched_modules=STRING_LOAD_MODULES)
    found: list[MemberImport] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                MemberImport(line=node.lineno, module=alias.name, name=None)
                for alias in node.names
                if alias.name.split('.')[0] in member_packages
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            if node.module.split('.')[0] in member_packages:
                found.extend(
                    MemberImport(line=node.lineno, module=node.module, name=alias.name)
                    for alias in node.names
                )
        elif isinstance(node, ast.Call):
            loaded = _string_loaded_module(call=node, bindings=bindings)
            if loaded is not None and loaded.split('.')[0] in member_packages:
                found.append(MemberImport(line=node.lineno, module=loaded, name=None))
    # A name of None (a plain import) sorts before any name on the same line and module
    return sorted(
        found,
        key=lambda member_import: (
            member_import.line,
            member_import.module,
            member_import.name or '',
        ),
    )


def module_name_of(*, relative: Path) -> str:
    """Return the module a Python file is imported as, from its path below its import root.

    Args:
        relative: Its path below the directory on ``sys.path`` (``tests/replay/helpers.py``).

    Returns:
        Its module (``tests.replay.helpers``; a package's ``__init__.py`` is the package).

    """
    parts = list(relative.with_suffix('').parts)
    if parts[-1] == '__init__':
        parts.pop()
    return '.'.join(parts)


def parent_modules(*, module: str) -> set[str]:
    """Return the packages above a module: importing it runs each of their ``__init__``.

    Returns:
        ``{'a', 'a.b'}`` for ``a.b.c``.

    """
    parts = module.split('.')
    return {'.'.join(parts[:depth]) for depth in range(1, len(parts))}


def pytest_plugin_names(*, tree: ast.Module) -> list[str]:
    """Return the plugins a conftest's module-level ``pytest_plugins`` names.

    Args:
        tree: The conftest's parsed source.

    Returns:
        The plugin module names: one string, or each string in a list or tuple, in order.

    """
    names: list[str] = []
    for node in tree.body:
        if not (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == 'pytest_plugins'
                for target in node.targets
            )
        ):
            continue
        values = node.value.elts if isinstance(node.value, (ast.List, ast.Tuple)) else [node.value]
        names.extend(
            value.value
            for value in values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    return names


def imported_module_names(
    *, tree: ast.Module, module: str, is_package: bool, followed: str, target: str
) -> set[str]:
    """Return every module of two packages a module may import, at any level.

    Absolute imports, relative imports (resolved against ``module``) and literal string loads
    (``importlib.import_module``, ``__import__``) count. For ``from X import y`` both ``X`` and
    ``X.y`` are named (``y`` may be a submodule). Every package above a ``followed`` module named,
    and above ``module`` itself, is named too: importing a module runs their ``__init__``.

    Args:
        tree: The module's parsed source.
        module: Its module name.
        is_package: Whether it is a package's ``__init__.py``.
        followed: The package whose modules a walk follows (``tests``, ``glitchygames``).
        target: The package a walk looks for (``scripts``).

    Returns:
        The module names (some may name no module: a function imported by ``from``).

    """
    named: set[str] = set()
    for found in member_imports(tree=tree, member_packages=frozenset({followed, target})):
        named.add(found.module)
        if found.name is not None:
            named.add(f'{found.module}.{found.name}')
    package = module if is_package else module.rpartition('.')[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            base = package.split('.')[: len(package.split('.')) - (node.level - 1)]
            resolved = '.'.join([*base, *([node.module] if node.module else [])])
            named.add(resolved)
            named.update(f'{resolved}.{alias.name}' for alias in node.names)
    followed_parents = {
        parent
        for name in named
        if name.partition('.')[0] == followed
        for parent in parent_modules(module=name)
    }
    return named | followed_parents | parent_modules(module=module)


def path_to_package(
    *, graph: Mapping[str, frozenset[str]], module: str, target: str
) -> list[str] | None:
    """Return the shortest chain of imports from a module to a module of ``target``.

    Only modules in ``graph`` are followed. Where one module names several of ``target``'s
    modules, the chain ends at the module imported: ``scripts.tool`` for ``from scripts.tool
    import THING`` (not ``scripts``, nor ``scripts.tool.THING``) and for ``from scripts import
    tool``; ``scripts`` only for a bare ``import scripts``.

    Args:
        graph: Module name -> the module names it imports.
        module: Where the chain starts.
        target: The package looked for (``scripts``).

    Returns:
        ``[module, ..., '<target>[.<name>]']``, or None when it reaches none.

    """
    came_from: dict[str, str | None] = {module: None}
    queue = [module]
    while queue:
        current = queue.pop(0)
        imported = sorted(graph.get(current, frozenset()))
        reached = [name for name in imported if name.partition('.')[0] == target]
        if reached:
            submodules = [name for name in reached if '.' in name] or reached
            chain = [min(submodules, key=lambda name: (len(name), name)), current]
            previous = came_from[current]
            while previous is not None:
                chain.append(previous)
                previous = came_from[previous]
            return chain[::-1]
        for name in imported:
            if name in graph and name not in came_from:
                came_from[name] = current
                queue.append(name)
    return None
