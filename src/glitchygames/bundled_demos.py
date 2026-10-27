"""Bundled demos: the recordings a game ships inside its installed package.

A bundled demo is ``<package>/demos/<name>.jsonl.gz`` in a workspace member's import package
(package data, so it ships with the package: PaddleSlap's ``paddleslap/demos/rally.jsonl.gz``),
and its game is the console script whose entry point is in the module ``<package>`` itself
(``paddleslap:main``). ``bundled_demos`` finds them where the packages are installed
(``importlib.util.find_spec``, which imports no game): the repository's sources under a
development install (``uv sync`` installs editable), ``site-packages`` under a built one. It is
the one lookup: the replay pytest plugin (``glitchygames.testing.replays.bundled_demo_paths``)
and a game's own recordings (``glitchygames.replay.tools.recordings``, which ``--verify`` and
``--measure`` take) call it, each with its own reaction to a demo no console script replays (the
plugin raises; a game's recordings are those its own console script replays). Each caller
names the packages it searches: there is no default (an unseen game's package is no workspace
member's, Stage D, Task D5).

A leaf of the engine for tools: it imports neither pygame nor a game.
"""

from __future__ import annotations

import dataclasses
import importlib.metadata
import importlib.util
import operator
from pathlib import Path

from glitchygames.tracing import is_bookmarked_copy

CONSOLE_SCRIPTS_GROUP = 'console_scripts'
# A demo's directory inside its import package, and a recording's suffix
BUNDLED_DEMO_DIRECTORY_NAME = 'demos'
DEMO_SUFFIX = '.jsonl.gz'


@dataclasses.dataclass(frozen=True)
class BundledDemo:
    """A demo bundled in an installed package.

    Attributes:
        package: The top-level import package holding it (``paddleslap``).
        console_script: The installed console script whose entry point is in that package
            (``paddleslap``), or None when no installed console script is.
        path: Where it is installed.
        install_name: Its path relative to the directory the package is installed in
            (``paddleslap/demos/rally.jsonl.gz``), the same under any install.

    """

    package: str
    console_script: str | None
    path: Path
    install_name: str


def console_script_in_module(*, module: str) -> str | None:
    """Return the name of the first console script whose entry point is in a module.

    Distributions are searched in ``sys.path`` order (``importlib.metadata.distributions``).

    Args:
        module: A module's dotted name, for example ``paddleslap``.

    Returns:
        The console script's name, or None if no installed console script is in the module.

    """
    for distribution in importlib.metadata.distributions():
        for entry_point in distribution.entry_points.select(group=CONSOLE_SCRIPTS_GROUP):
            if entry_point.module == module:
                return entry_point.name
    return None


def package_demo_paths(*, package_directory: Path) -> list[Path]:
    """Return the demos bundled in an import package: ``<package directory>/demos/*.jsonl.gz``.

    A bookmarked copy (``glitchygames.tracing.is_bookmarked_copy``: what S saves beside a
    recording a watched replay plays) is no demo, and is left out.

    Args:
        package_directory: The import package's directory (where its ``__init__.py`` is).

    Returns:
        The demos' paths, sorted.

    """
    return sorted(
        path
        for path in (package_directory / BUNDLED_DEMO_DIRECTORY_NAME).glob(f'*{DEMO_SUFFIX}')
        if not is_bookmarked_copy(path=path)
    )


def bundled_demos(*, packages: tuple[str, ...]) -> list[BundledDemo]:
    """Return every demo bundled in an installed package, with the console script that replays it.

    A package that is not installed has no demos to find (``uv sync --all-packages`` installs
    every member), nor has a plain module (no directory to hold ``demos/``).

    Args:
        packages: The top-level import packages to search (a game's own: its identity's
            ``package``; this repository's members: ``glitchygames.logical_names.MEMBER_LAYERS``).

    Returns:
        The demos, sorted by path.

    """
    demos: list[BundledDemo] = []
    for package in packages:
        specification = importlib.util.find_spec(package)
        if specification is None:
            continue
        # None for a plain module; a package's own directory otherwise
        for location in specification.submodule_search_locations or ():
            package_directory = Path(location)
            demo_paths = package_demo_paths(package_directory=package_directory)
            if not demo_paths:
                continue
            console_script = console_script_in_module(module=package)
            demos.extend(
                BundledDemo(
                    package=package,
                    console_script=console_script,
                    path=path,
                    install_name=path.relative_to(package_directory.parent).as_posix(),
                )
                for path in demo_paths
            )
    return sorted(demos, key=operator.attrgetter('path'))
