"""Find project modules loaded twice: a module object other than ``sys.modules``' still in use.

A module is loaded twice when its entry leaves ``sys.modules`` while modules already hold it,
and it is imported again. The holders keep the first copy (``from glitchygames import
pixel_snap`` binds it in the importer's globals, and a package keeps its submodules as
attributes); everything imported afterwards gets the second. Each copy has its own module
state, its own ``ContextSlot`` objects among it, so a reset of one (the harness's) misses the
other (the game's).

coverage does this to the project when a run names a dotted source
(``--cov=glitchygames.sprites.hud_label``): it imports the source's parents to find the module
inside ``sys_modules_saved()`` (coverage/inorout.py, 7.17.3), which deletes every module imported
in the block from ``sys.modules`` afterwards. The project's pytest plugin has imported
``glitchygames`` before coverage starts, so the package keeps the deleted submodules as
attributes, and the harness binds them from there. 2026-11-27: 8 Brave Adventurer tests failed
that way (bugs/2026-11-27-a-dotted-coverage-source-loaded-the-engine-twice.md).

``modules_loaded_twice`` looks where a first copy stays: every project module's globals and
every package's attributes, for a project module that is not the one ``sys.modules`` holds by its
name. tests/harness.py stops the run at its start when it finds any (``pytest_sessionstart``).
Tests: tests/test_module_copies_guard.py.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterable

# What the run is told when it stops, after the modules' names
MODULES_LOADED_TWICE_ADVICE = (
    'Each copy keeps its own state, so the harness resets one while the code under test reads '
    'the other, and tests fail on state another test left. The usual cause is a dotted --cov '
    '(such as --cov=glitchygames.sprites.hud_label): coverage imports the source package to find '
    'the module and then takes what it imported out of sys.modules. Measure with the package, '
    '--cov=glitchygames (or the member package), and read one file with '
    '`coverage report --include=<path>`.'
)

# How many of the modules' names the message lists
NAMES_LISTED = 5


def _is_under(*, module: object, roots: tuple[Path, ...]) -> bool:
    """Tell whether a module's file is in one of the roots (a module without a file is not)."""
    file = getattr(module, '__file__', None)
    if not isinstance(file, str):
        return False
    path = Path(file).resolve()
    return any(path.is_relative_to(root) for root in roots)


def modules_loaded_twice(*, roots: Iterable[Path]) -> list[str]:
    """Return the project modules some project module holds in a copy ``sys.modules`` does not.

    Args:
        roots: The directories whose modules are the project's (the checkout's ``src`` and
            ``tests``, and the installed engine's directory).

    Returns:
        The copied modules' names, sorted, each once.

    """
    resolved_roots = tuple(root.resolve() for root in roots)
    project_modules = [
        module
        for module in list(sys.modules.values())
        if _is_under(module=module, roots=resolved_roots)
    ]
    twice: set[str] = set()
    for holder in project_modules:
        # Not vars(): a library may put an object without a __dict__ in sys.modules
        for value in list(getattr(holder, '__dict__', {}).values()):
            if (
                isinstance(value, types.ModuleType)
                and _is_under(module=value, roots=resolved_roots)
                and sys.modules.get(value.__name__) is not value
            ):
                twice.add(value.__name__)
    return sorted(twice)


def modules_loaded_twice_message(*, names: list[str]) -> str:
    """Say which modules are loaded twice, why that breaks tests, and what to run instead.

    Args:
        names: The modules (``modules_loaded_twice``), at least one.

    Returns:
        The message.

    """
    listed = ', '.join(names[:NAMES_LISTED])
    more = f' and {len(names) - NAMES_LISTED} more' if len(names) > NAMES_LISTED else ''
    return f'{listed}{more} loaded twice. {MODULES_LOADED_TWICE_ADVICE}'


def stop_if_modules_are_loaded_twice(*, roots: Iterable[Path]) -> None:
    """End the run before any test when a project module is loaded twice.

    Args:
        roots: The directories whose modules are the project's.

    """
    names = modules_loaded_twice(roots=roots)
    if names:
        pytest.exit(
            modules_loaded_twice_message(names=names), returncode=pytest.ExitCode.USAGE_ERROR
        )
