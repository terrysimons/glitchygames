"""mkdocs hooks (mkdocs.yml ``hooks``): generate the graphs first, free the API caches after.

Every ``mkdocs build``, ``mkdocs serve`` and ``mkdocs gh-deploy`` (so ``nox -s docs-deploy``,
``docs-serve`` and ``lint-docs`` too) runs ``on_pre_build`` first, which:

1. generates docs/quality/graphs/ with scripts/generate_complexity_graphs.py when they are
   missing or were made from another commit (``generate_if_stale``: about a minute; a rebuild
   with the same HEAD, such as each ``mkdocs serve`` reload, costs only a ``git rev-parse``). A
   failed generation stops the build with the failed tool's output;
2. generates docs/quality/metrics/ with scripts/generate_performance_graphs.py: the run ledger
   published on gh-pages merged with the pending rows ``nox -s replay-metrics`` measured, and
   its graphs (a ``git show`` and a few small files; rewritten only when they changed). Rows
   measured on uncommitted changes are left out of a build that is published (``mkdocs
   gh-deploy``) and shown, labelled, in a local one (``build``, ``serve``): ``on_startup``
   learns which. Without a startup event (unknown), they are left out.

After every build, ``on_post_build`` empties griffe's and mkdocstrings' module-level caches
(``documentation_caches``). Some are unbounded ``functools.cache``s keyed by one build's objects
(griffe's ``_dataclass_parameters`` by its classes, mkdocstrings-python's
``_test_existing_template`` by its Jinja environment), and ``mkdocs serve`` makes all of those
afresh for each rebuild, so every old build stayed alive: about 330 MB per rebuild, a server
at 14.5 GB after a long session (griffe 2.4.1, mkdocstrings-python 2.0.10; BUGS.md #213). They only
speed up work within a build, so emptying them between builds costs nothing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

from mkdocs.exceptions import PluginError

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from mkdocs.config.defaults import MkDocsConfig

# mkdocs loads this file by path, so its sibling scripts are loaded by path too
SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
GRAPH_SCRIPT_PATH = SCRIPTS_DIRECTORY / 'generate_complexity_graphs.py'
GRAPH_SCRIPT_MODULE_NAME = 'generate_complexity_graphs'
PERFORMANCE_SCRIPT_PATH = SCRIPTS_DIRECTORY / 'generate_performance_graphs.py'
PERFORMANCE_SCRIPT_MODULE_NAME = 'generate_performance_graphs'
# The mkdocs commands whose site stays on this machine (gh-deploy publishes it)
LOCAL_BUILD_COMMANDS = frozenset({'build', 'serve'})
# The packages whose module caches ``on_post_build`` empties (the griffe and mkdocstrings
# distributions, mkdocstrings-python's handler package included)
DOCUMENTATION_CACHE_PACKAGES = ('griffe', 'mkdocstrings')


class ModuleCache(Protocol):
    """A ``functools.cache`` or ``functools.lru_cache`` function: its entries can be emptied."""

    cache_clear: Callable[[], None]


class BuildState:
    """What this mkdocs invocation is: set once by ``on_startup``.

    Attributes:
        command: The mkdocs command (``build``, ``gh-deploy`` or ``serve``), or None before
            ``on_startup`` ran.

    """

    def __init__(self) -> None:
        """Start with the command unknown."""
        self.command: str | None = None


BUILD_STATE = BuildState()


def load_script(*, path: Path, module_name: str) -> ModuleType:
    """Return a sibling script as a module (loaded once, then reused).

    Args:
        path: The script.
        module_name: The name it is loaded under.

    Returns:
        The module.

    """
    loaded = sys.modules.get(module_name)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(module_name, path)
    assert specification is not None, f'{path} is not a Python module'
    assert specification.loader is not None, f'{path} has no loader'
    module = importlib.util.module_from_spec(specification)
    sys.modules[module_name] = module
    specification.loader.exec_module(module)
    return module


def load_graph_script() -> ModuleType:
    """Return the complexity graph script as a module (loaded once, then reused).

    Returns:
        The module.

    """
    return load_script(path=GRAPH_SCRIPT_PATH, module_name=GRAPH_SCRIPT_MODULE_NAME)


def load_performance_script() -> ModuleType:
    """Return the performance graph script as a module (loaded once, then reused).

    Returns:
        The module.

    """
    return load_script(path=PERFORMANCE_SCRIPT_PATH, module_name=PERFORMANCE_SCRIPT_MODULE_NAME)


def generate_performance_graphs() -> None:
    """Generate the performance graphs into the script's ``METRICS_DIR``.

    Raises:
        PluginError: A file could not be read or written; the build stops.

    """
    performance_script = load_performance_script()
    try:
        performance_script.generate_performance_page(
            project_root=performance_script.PROJECT_ROOT,
            metrics_directory=performance_script.METRICS_DIR,
            pending_path=performance_script.PENDING_LEDGER_PATH,
            include_uncommitted_changes=BUILD_STATE.command in LOCAL_BUILD_COMMANDS,
        )
    except OSError as error:
        message = f'Could not generate the performance graphs: {error}'
        raise PluginError(message) from error


def on_startup(*, command: Literal['build', 'gh-deploy', 'serve'], dirty: bool) -> None:
    """Remember which mkdocs command runs (mkdocs calls this once, before any build).

    The ``startup`` event is new in MkDocs 1.4 (``mkdocs.plugins.BasePlugin.on_startup``, keyword
    arguments ``command`` and ``dirty``; mkdocs/__main__.py passes ``'build'`` and
    ``'gh-deploy'``, mkdocs/commands/serve.py ``'serve'``), and a hooks file's functions are
    registered as plugin events (``mkdocs.config.config_options.Hooks``).

    Args:
        command: The mkdocs command.
        dirty: Whether ``--dirty`` was passed (unused).

    """
    del dirty
    BUILD_STATE.command = command


def on_pre_build(config: MkDocsConfig) -> None:
    """Generate the complexity graphs unless current, then the performance graphs.

    mkdocs runs this before a build.

    Args:
        config: The mkdocs configuration (unused: the graphs' places are fixed by the scripts).

    Raises:
        PluginError: The complexity generation failed (git, radon or wily); the build stops.

    """
    del config
    graph_script = load_graph_script()
    try:
        graph_script.generate_if_stale(
            project_root=graph_script.PROJECT_ROOT, graphs_directory=graph_script.GRAPHS_DIR
        )
    except graph_script.ComplexityGraphError as error:
        message = f'Could not generate the complexity graphs: {error}'
        raise PluginError(message) from error
    generate_performance_graphs()


def documentation_caches() -> list[ModuleCache]:
    """Return the module-level caches of the loaded griffe and mkdocstrings modules.

    Returns:
        Every module attribute with ``cache_clear`` and ``cache_info`` (a ``functools`` cache),
        found by scanning the modules, not by name, so a renamed cache upstream is still found.

    """
    caches: list[ModuleCache] = []
    for module_name, module in list(sys.modules.items()):
        if module_name.split('.', maxsplit=1)[0].startswith(DOCUMENTATION_CACHE_PACKAGES):
            caches.extend(
                value
                for value in list(vars(module).values())
                if callable(getattr(value, 'cache_clear', None)) and hasattr(value, 'cache_info')
            )
    return caches


def on_post_build(config: MkDocsConfig) -> None:
    """Empty the documentation caches, which would keep this build alive (see the docstring).

    mkdocs runs this after a build.

    Args:
        config: The mkdocs configuration (unused).

    """
    del config
    for cache in documentation_caches():
        cache.cache_clear()
