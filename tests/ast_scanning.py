"""Shared AST helpers for the package guard scans.

Resolve a name or attribute chain in a module's source to the fully qualified name it refers
to, following imports and aliases of the watched modules. The randomness guard
(tests/test_randomness.py) and the engine-doors guard (tests/test_engine_doors.py) each pass
their own set of watched modules. ``member_imports`` finds every import of a workspace member,
for the guards that the engine's source (tests/test_workspace_config.py) and the engine's tests
(tests/test_suite_collection.py) import none.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Self

from scripts.workspace_packages import ENGINE_DIRECTORY, source_package_directories

if TYPE_CHECKING:
    from collections.abc import Sequence

    from scripts.workspace_packages import WorkspaceMember

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


def scanned_source_files(*, project_root: Path) -> list[tuple[str, Path]]:
    """Return every Python file the guards scan, with the key the allowlists spell it by.

    The engine's files are keyed relative to ``src/glitchygames/`` (``clock.py``); a workspace
    member's files relative to the repository (``src/games/mr-muncher/src/mr_muncher/game.py``), so
    the two never clash.

    Args:
        project_root: The repository.

    Returns:
        ``(allowlist key, path)`` for each file, in scan order.

    """
    engine_directory = project_root / ENGINE_DIRECTORY
    scanned: list[tuple[str, Path]] = []
    for package_directory in source_package_directories(project_root=project_root):
        key_base = engine_directory if package_directory == engine_directory else project_root
        scanned.extend(
            (source_path.relative_to(key_base).as_posix(), source_path)
            for source_path in sorted(package_directory.rglob('*.py'))
        )
    return scanned


def write_project_with_member_module(*, project_root: Path, source: str) -> str:
    """Write a small workspace project whose one member module holds ``source``.

    The project has an empty ``src/glitchygames/`` and the member ``src/games/space-game`` with
    the package ``space_game`` and its module ``game.py``.

    Args:
        project_root: Where to write the project (a temporary directory).
        source: The member module's source.

    Returns:
        The key the guards' allowlists would spell the member module by.

    """
    (project_root / ENGINE_DIRECTORY).mkdir(parents=True)
    (project_root / 'pyproject.toml').write_text(
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n', encoding='utf-8'
    )
    member_directory = project_root / 'src' / 'games' / 'space-game'
    (member_directory / 'space_game').mkdir(parents=True)
    (member_directory / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["space_game"]\n',
        encoding='utf-8',
    )
    (member_directory / 'space_game' / 'game.py').write_text(source, encoding='utf-8')
    return 'src/games/space-game/space_game/game.py'


# The calls that load a module named by a string
STRING_LOADS = frozenset({'importlib.import_module'})


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


def member_import_packages(*, members: Sequence[WorkspaceMember]) -> frozenset[str]:
    """Return every import package the members hold."""
    return frozenset(package for member in members for package in member.import_packages)


def _string_loaded_module(*, call: ast.Call, bindings: dict[str, str]) -> str | None:
    """Return the module a call loads by a literal name, else None.

    Args:
        call: The call.
        bindings: The module's bindings of ``importlib``, from ``import_bindings``.

    Returns:
        The literal module name ``importlib.import_module`` or ``__import__`` is given, else None.

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
    bindings = import_bindings(tree=tree, watched_modules=frozenset({'importlib'}))
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
