"""mkdocs hooks (mkdocs.yml ``hooks``): generate the complexity and performance graphs first.

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
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from mkdocs.exceptions import PluginError

if TYPE_CHECKING:
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
