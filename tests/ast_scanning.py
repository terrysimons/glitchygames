"""Shared AST helpers for the package guard scans.

Resolve a name or attribute chain in a module's source to the fully qualified name it refers
to, following imports and aliases of the watched modules. The randomness guard
(tests/test_randomness.py) and the engine-doors guard (tests/test_engine_doors.py) each pass
their own set of watched modules.
"""

from __future__ import annotations

import ast


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
