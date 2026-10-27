"""A game's identity, read from the game object alone: its package, directory and console script.

The game passes itself to the engine (``GameEngine(game=Game)``) and declares nothing else
(stage D's decision 13); the tools find what they need about it from that object:

- **package**: the top-level package of the scene class's module (``paddleslap`` for
  ``paddleslap.game``; ``__main__`` for a game run as a script);
- **package directory**: where that package is, from ``importlib.util.find_spec`` (looked up,
  never imported), or the loaded module's file when the import system can't find it (a script's
  ``__main__``);
- **console script**: the installed console script whose entry point (``module:function``) is
  in that package and starts the game's module (``children.console_script_for_game_module``);
- **distribution**: the installed distribution that holds the package
  (``importlib.metadata.packages_distributions``), else the console script's distribution (an
  editable install's metadata lists no packages, only its ``.pth`` file);
- **source revision** (``game_source_revision``): the package directory's commit, looked up as
  the engine's own is; each run records it beside the engine's, and a ledger row names it.

Whatever isn't found is None: a game no console script starts, or one no distribution holds, still
has an identity.
"""

from __future__ import annotations

import dataclasses
import importlib.metadata
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from glitchygames.build_info import package_source_revision
from glitchygames.replay.tools.children import (
    console_script_for_game_module,
    installed_console_scripts,
)

if TYPE_CHECKING:
    from importlib.machinery import ModuleSpec
    from importlib.metadata import EntryPoint

    from glitchygames.build_info import SourceRevision
    from glitchygames.scenes import Scene

# What separates an entry point's module from its callable (``paddleslap:main``)
ENTRY_POINT_SEPARATOR = ':'
# The module of a game run as a script (python mygame.py)
SCRIPT_MODULE = '__main__'


@dataclasses.dataclass(frozen=True)
class GameIdentity:
    """What the tools know about a game from its scene class.

    Attributes:
        package: The top-level package of the scene class's module.
        package_directory: Where that package is, or None when it can't be found.
        console_script: The installed console script that starts the game, or None.
        distribution: The installed distribution holding the package, or None.

    """

    package: str
    package_directory: Path | None
    console_script: str | None
    distribution: str | None


def _specification(*, package: str) -> ModuleSpec | None:
    """Return the import system's spec of a top-level package, without importing it.

    Returns:
        The spec, or None when it isn't found (or is loaded without one: ``find_spec`` raises
        ``ValueError`` for a module in ``sys.modules`` whose ``__spec__`` is None).

    """
    try:
        return importlib.util.find_spec(package)
    except ValueError:
        return None


def package_directory_of(*, package: str) -> Path | None:
    """Return where a top-level package (or module) is.

    The import system's spec first: a package's directory, or a single module's file's
    directory. A game run as a script (``__main__``) is not looked up there (under
    ``python -m``, ``__main__``'s spec names the module that was run, not this game): its
    loaded module's file is used, as for any module the import system can't find.

    Returns:
        The directory, or None when neither finds a file.

    """
    specification = None if package == SCRIPT_MODULE else _specification(package=package)
    if specification is not None and specification.submodule_search_locations:
        return Path(next(iter(specification.submodule_search_locations)))
    if specification is not None and specification.has_location and specification.origin:
        return Path(specification.origin).parent
    loaded = sys.modules.get(package)
    module_file = None if loaded is None else getattr(loaded, '__file__', None)
    return None if module_file is None else Path(module_file).parent


def starting_entry_point(*, package: str, game_module: str) -> EntryPoint | None:
    """Return the installed console script in a package that starts a game module.

    Returns:
        Its entry point, or None when none or more than one does.

    """
    in_package = [
        entry_point
        for entry_point in installed_console_scripts()
        if entry_point.value.partition(ENTRY_POINT_SEPARATOR)[0].partition('.')[0] == package
    ]
    try:
        name = console_script_for_game_module(entry_points=in_package, game_module=game_module)
    except KeyError:
        return None
    return next(entry_point for entry_point in in_package if entry_point.name == name)


def distribution_of(*, package: str, entry_point: EntryPoint | None) -> str | None:
    """Return the installed distribution holding a package.

    Returns:
        The first distribution the metadata lists the package in, else the starting console
        script's distribution (an editable install lists only its ``.pth`` file), else None.

    """
    listed = importlib.metadata.packages_distributions().get(package)
    if listed:
        return listed[0]
    return None if entry_point is None or entry_point.dist is None else entry_point.dist.name


def game_identity(*, game: type[Scene] | Scene) -> GameIdentity:
    """Return a game's identity from its scene class (or a scene of that class).

    Args:
        game: The game's scene class, as passed to ``GameEngine(game=...)``, or a scene.

    Returns:
        Its package, package directory, console script and distribution (see the module
        docstring); each of the last three is None when not found.

    """
    scene_class = game if isinstance(game, type) else type(game)
    game_module = scene_class.__module__
    package = game_module.partition('.')[0]
    entry_point = starting_entry_point(package=package, game_module=game_module)
    return GameIdentity(
        package=package,
        package_directory=package_directory_of(package=package),
        console_script=None if entry_point is None else entry_point.name,
        distribution=distribution_of(package=package, entry_point=entry_point),
    )


def game_source_revision(*, game: type[Scene] | Scene) -> SourceRevision | None:
    """Return the source revision of a game's package: the commit a ledger row names.

    Looked up in the game's package directory (``GameIdentity.package_directory``) as the
    engine's is in its own (``glitchygames.build_info.package_source_revision``: a checkout
    that tracks the package, then an archive, then a build stamp, else unknown), so a game
    outside this repository names its own commit. Only the directory is looked up here, with
    the function ``game_identity`` uses for it: the console script and distribution lookups
    scan every installed distribution (a third of a second), and a run looks this up as it
    starts.

    Args:
        game: The game's scene class, as passed to ``GameEngine(game=...)``, or a scene.

    Returns:
        The revision (``UNKNOWN_REVISION`` when none answered), or None when the game's package
        directory can't be found: the run then names only the engine's.

    """
    scene_class = game if isinstance(game, type) else type(game)
    package_directory = package_directory_of(package=scene_class.__module__.partition('.')[0])
    if package_directory is None:
        return None
    return package_source_revision(package_directory=package_directory)
