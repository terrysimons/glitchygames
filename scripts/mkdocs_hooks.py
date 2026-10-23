"""mkdocs hooks (mkdocs.yml ``hooks``): generate the complexity graphs before every build.

Every ``mkdocs build``, ``mkdocs serve`` and ``mkdocs gh-deploy`` (so ``nox -s docs-deploy``,
``docs-serve`` and ``lint-docs`` too) runs ``on_pre_build`` first, which generates
docs/quality/graphs/ with scripts/generate_complexity_graphs.py when they are missing or were made
from another commit (``generate_if_stale``: about a minute; a rebuild with the same HEAD, such as
each ``mkdocs serve`` reload, costs only a ``git rev-parse``). A failed generation stops the build
with the failed tool's output.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from mkdocs.exceptions import PluginError

if TYPE_CHECKING:
    from types import ModuleType

    from mkdocs.config.defaults import MkDocsConfig

# mkdocs loads this file by path, so its sibling script is loaded by path too
GRAPH_SCRIPT_PATH = Path(__file__).resolve().parent / 'generate_complexity_graphs.py'
GRAPH_SCRIPT_MODULE_NAME = 'generate_complexity_graphs'


def load_graph_script() -> ModuleType:
    """Return the complexity graph script as a module (loaded once, then reused).

    Returns:
        The module.

    """
    loaded = sys.modules.get(GRAPH_SCRIPT_MODULE_NAME)
    if loaded is not None:
        return loaded
    specification = importlib.util.spec_from_file_location(
        GRAPH_SCRIPT_MODULE_NAME, GRAPH_SCRIPT_PATH
    )
    assert specification is not None, f'{GRAPH_SCRIPT_PATH} is not a Python module'
    assert specification.loader is not None, f'{GRAPH_SCRIPT_PATH} has no loader'
    module = importlib.util.module_from_spec(specification)
    sys.modules[GRAPH_SCRIPT_MODULE_NAME] = module
    specification.loader.exec_module(module)
    return module


def on_pre_build(config: MkDocsConfig) -> None:
    """Generate the complexity graphs unless they are current (mkdocs runs this before a build).

    Args:
        config: The mkdocs configuration (unused: the graphs' place is fixed by the script).

    Raises:
        PluginError: The generation failed (git, radon or wily); the build stops.

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
