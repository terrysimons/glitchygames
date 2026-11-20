"""mkdocs hooks (zensical.yml ``hooks``): generate the graphs first, free the API caches after.

Every ``mkdocs build``, ``mkdocs serve`` and ``mkdocs gh-deploy`` (so ``nox -s docs-deploy``,
``docs-serve`` and ``lint-docs`` too) runs ``on_pre_build`` first, which:

1. generates docs/quality/graphs/ with scripts/generate_complexity_graphs.py when they are
   missing or were made from another commit (``generate_if_stale``: about a minute; a rebuild
   with the same HEAD, such as each ``mkdocs serve`` reload, costs only a ``git rev-parse``). A
   failed generation stops the build with the failed tool's output;
2. generates docs/quality/metrics/ with scripts/generate_performance_graphs.py, which calls the
   engine's ``performance-pages`` tool (glitchygames/replay/tools/performance_pages.py) and adds
   our page's snippet: the run ledger (our row files and the ledger published on gh-pages,
   merged with the pending rows ``nox -s replay-metrics`` measured) and its graphs (a ``git
   show`` and a few small files; rewritten only when they changed). Rows
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

After the build, ``on_post_build`` copies the browser games (build/browser/site, which
``nox -s docs-deploy`` builds first with
``python -m scripts.build_browser_bundle all``) into the site as play/. A build without them
(``lint-docs``, ``docs-serve``) leaves play/ out: building them needs the pygame-ce wheel's
WebAssembly toolchain.

Last, ``on_post_build`` checks the explorers' pages (``EXPLORER_PAGES``: requirements, replay
performance, code complexity) without a browser: each built page must hold its explorer, and
every local script, stylesheet and ``data-source`` the page names must be a file of the built
site (``missing_explorer_files``), or the build stops naming what is missing.
"""

from __future__ import annotations

import importlib.util
import logging
import posixpath
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, override

from mkdocs.exceptions import PluginError

from glitchygames.replay.tools.performance_pages import UnreadableLedgerError

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
# The browser games' site (python -m scripts.build_browser_bundle all) and where the docs serve it
BROWSER_GAMES_DIRECTORY = SCRIPTS_DIRECTORY.parent / 'build' / 'browser' / 'site'
PLAY_DIRECTORY_NAME = 'play'

LOG = logging.getLogger('mkdocs.hooks.glitchygames')
# The packages whose module caches ``on_post_build`` empties (the griffe and mkdocstrings
# distributions, mkdocstrings-python's handler package included)
DOCUMENTATION_CACHE_PACKAGES = ('griffe', 'mkdocstrings')
# Each explorer's built page (from the site's root) and the class of the element it draws into,
# whose data-source names the JSON it reads (docs/js/requirements.js, performance.js, complexity.js)
EXPLORER_PAGES: dict[str, str] = {
    'requirements/index.html': 'requirements-explorer',
    'quality/performance/index.html': 'performance-explorer',
    'quality/complexity/index.html': 'complexity-explorer',
}
# A reference with one of these is not a file of the site (another site's script or font)
EXTERNAL_REFERENCE_PREFIXES = ('http://', 'https://', '//', 'data:')


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
        PluginError: A file could not be read or written (a pending ledger that can't be read
            too: ``UnreadableLedgerError``); the build stops.

    """
    performance_script = load_performance_script()
    try:
        performance_script.generate_performance_page(
            project_root=performance_script.PROJECT_ROOT,
            # Our settings, given: the script reads them once, from this repository
            settings=performance_script.PROJECT_SETTINGS,
            metrics_directory=performance_script.METRICS_DIR,
            pending_path=performance_script.PENDING_LEDGER_PATH,
            include_uncommitted_changes=BUILD_STATE.command in LOCAL_BUILD_COMMANDS,
        )
    except (OSError, UnreadableLedgerError) as error:
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


def copy_browser_games(*, games_directory: Path, site_directory: Path) -> bool:
    """Copy the browser games' site into the docs site as play/, when it was built.

    Args:
        games_directory: The games' site (``python -m scripts.build_browser_bundle all``).
        site_directory: The built docs site.

    Returns:
        Whether the games were copied (False: none built).

    """
    if not (games_directory / 'index.html').is_file():
        LOG.info(
            'No browser games in %s: the site has no %s/', games_directory, PLAY_DIRECTORY_NAME
        )
        return False
    shutil.copytree(games_directory, site_directory / PLAY_DIRECTORY_NAME, dirs_exist_ok=True)
    return True


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


class PageReferences(HTMLParser):
    """The files a built page names: its scripts, its stylesheets and its elements' data-source.

    Attributes:
        references: Each ``<script src>``, ``<link rel="stylesheet" href>`` and
            ``data-source``, as written in the page, in order.
        classes: Every class any element of the page has.

    """

    def __init__(self) -> None:
        """Start with nothing found."""
        super().__init__()
        self.references: list[str] = []
        self.classes: set[str] = set()

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Note what one start tag names.

        Args:
            tag: The element's name.
            attrs: Its attributes, as written.

        """
        attributes = {name: value or '' for name, value in attrs}
        self.classes.update(attributes.get('class', '').split())
        if tag == 'script' and attributes.get('src'):
            self.references.append(attributes['src'])
        if tag == 'link' and 'stylesheet' in attributes.get('rel', '').split():
            self.references.append(attributes.get('href', ''))
        if attributes.get('data-source'):
            self.references.append(attributes['data-source'])


def missing_explorer_files(*, site_directory: Path) -> list[str]:
    """Return what the explorers' built pages need and the built site lacks.

    A browser-free check of what a reader's browser would load: each page in ``EXPLORER_PAGES``
    must exist and hold its explorer's element, and each local script, stylesheet and
    ``data-source`` it names, resolved against the page's directory as a browser resolves it,
    must be a file of the site.

    Args:
        site_directory: The built docs site.

    Returns:
        ``<page>: <what is missing>`` for each, in ``EXPLORER_PAGES``' order; empty when all
        are there.

    """
    missing: list[str] = []
    for page, explorer_class in EXPLORER_PAGES.items():
        page_path = site_directory / page
        if not page_path.is_file():
            missing.append(f'{page}: the page itself')
            continue
        parser = PageReferences()
        parser.feed(page_path.read_text(encoding='utf-8'))
        if explorer_class not in parser.classes:
            missing.append(f'{page}: its explorer (an element of class {explorer_class})')
        page_directory = posixpath.dirname(page)
        for reference in parser.references:
            if reference.startswith(EXTERNAL_REFERENCE_PREFIXES):
                continue
            file_path = reference.split('#', maxsplit=1)[0].split('?', maxsplit=1)[0]
            site_path = posixpath.normpath(posixpath.join(page_directory, file_path))
            if site_path.startswith('..') or not (site_directory / site_path).is_file():
                missing.append(f'{page}: {reference} ({site_path})')
    return missing


def on_post_build(config: MkDocsConfig) -> None:
    """Copy the browser games in, empty the documentation caches, then check the explorers.

    mkdocs runs this after a build, before ``gh-deploy`` publishes the site. The games:
    ``copy_browser_games``; the caches would keep this build alive (see the module docstring);
    the explorers: ``missing_explorer_files``.

    Args:
        config: The mkdocs configuration (its ``site_dir``).

    Raises:
        PluginError: An explorer's page, its explorer or a file it names is missing from the
            built site.

    """
    site_directory = Path(config.site_dir)
    copy_browser_games(games_directory=BROWSER_GAMES_DIRECTORY, site_directory=site_directory)
    for cache in documentation_caches():
        cache.cache_clear()
    missing = missing_explorer_files(site_directory=site_directory)
    if missing:
        message = "The explorers' pages name files the built site lacks:\n" + '\n'.join(missing)
        raise PluginError(message)
