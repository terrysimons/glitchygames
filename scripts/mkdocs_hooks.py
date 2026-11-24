"""mkdocs hooks (zensical.yml ``hooks``): make the graphs first, free the API caches after.

Every ``mkdocs build``, ``mkdocs serve`` and ``mkdocs gh-deploy`` (so ``nox -s docs-deploy``,
``docs-serve`` and ``lint-docs`` too) runs ``on_pre_build`` first, which:

1. fills docs/quality/graphs/ with scripts/generate_complexity_graphs.py. Only a deploy
   (``mkdocs gh-deploy``, so ``nox -s docs-deploy`` and CircleCI's deploy-docs after a merge to
   main) generates the complexity graphs, when they are missing or were made from another commit
   (``generate_if_stale``: wily over HEAD's whole history, about 490 s on CircleCI). Every other
   build (``mkdocs build`` and ``serve``: ``nox -s lint``'s strict build, ``lint-docs``,
   ``docs-serve``) keeps graphs generated from HEAD and otherwise writes a labelled placeholder
   (``write_placeholder_unless_current``: a snippet and explorer data saying nothing was
   measured, in well under a second), unless ``GLITCHYGAMES_DOCS_COMPLEXITY_GRAPHS=1``
   (``complexity_graphs_wanted``; the owner, 2026-11-23). A failed generation stops the build
   with the failed tool's output;
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

After the build, ``on_post_build`` copies the browser games (build/browser/site, from
``python -m scripts.build_browser_bundle all``) into the site as play/. A deploy (``gh-deploy``,
however it is run: ``nox -s docs-deploy`` or a bare ``mkdocs gh-deploy``) builds them afresh
first, every time, as a game may have changed (the owner, 2026-11-19), and publishes them only
when the site's stamp (``SITE_STAMP_NAME``) says they were built from this commit with every game
it lists; otherwise the deploy stops before anything is pushed (2026-11-19: a deploy copied a
games site built six days earlier, and Zombies Ain't My Neighbors' play/ page vanished). A local
build (``lint-docs``, ``docs-serve``) builds no games, as that needs the pygame-ce wheel's
WebAssembly toolchain: it copies a games site built from this commit and otherwise leaves play/
out, saying why.

Last, ``on_post_build`` checks the explorers' pages (``EXPLORER_PAGES``: requirements, replay
performance, code complexity) without a browser: each built page must hold its explorer, and
every local script, stylesheet and ``data-source`` the page names must be a file of the built
site (``missing_explorer_files``), or the build stops naming what is missing.
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
import logging
import os
import posixpath
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, override

from mkdocs.exceptions import PluginError

from glitchygames import clock
from glitchygames.process import run_command
from glitchygames.replay.tools.performance_pages import UnreadableLedgerError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
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
# A local build generates the complexity graphs too when this is COMPLEXITY_GRAPHS_ON (a deploy
# always does; complexity_graphs_wanted): GLITCHYGAMES_DOCS_COMPLEXITY_GRAPHS=1 uv run mkdocs ...
COMPLEXITY_GRAPHS_VARIABLE = 'GLITCHYGAMES_DOCS_COMPLEXITY_GRAPHS'
COMPLEXITY_GRAPHS_ON = '1'
COMPLEXITY_GRAPHS_SETTINGS = frozenset({'', '0', COMPLEXITY_GRAPHS_ON})
# The browser games' site (python -m scripts.build_browser_bundle all) and where the docs serve it
BROWSER_GAMES_DIRECTORY = SCRIPTS_DIRECTORY.parent / 'build' / 'browser' / 'site'
PLAY_DIRECTORY_NAME = 'play'
# The games site's stamp, written by the builder (scripts/build_browser_bundle.py, whose
# SITE_STAMP_NAME a test holds equal: mkdocs loads this file by path, so it cannot import it)
SITE_STAMP_NAME = 'site_build.json'
# The builder's command, run from the repository root, and how long a deploy waits for it (the
# first build of the pygame-ce wheel takes several minutes)
BROWSER_GAMES_BUILD = ('-m', 'scripts.build_browser_bundle', 'all')
BROWSER_GAMES_BUILD_TIMEOUT_SECONDS = 60 * 60

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


@contextlib.contextmanager
def logged_stage(name: str) -> Generator[None]:
    """Log a slow stage's start, and its end with the seconds it took (failed or done).

    At INFO on the hook's logger, which mkdocs prints: a build is never silent for the whole of
    a stage, and its log shows where the time went. CircleCI kills a step after 10 minutes with
    no output (job 5089, #261: the graphs generated silently inside the strict docs build).

    Args:
        name: The stage, as the lines name it.

    Yields:
        Nothing; the stage runs inside.

    """
    LOG.info('%s: started', name)
    started = clock.measured_seconds()
    try:
        yield
    except BaseException:
        LOG.info('%s: failed after %.1f s', name, clock.measured_seconds() - started)
        raise
    LOG.info('%s: done in %.1f s', name, clock.measured_seconds() - started)


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


def publishing() -> bool:
    """Return whether this mkdocs invocation publishes the site.

    ``gh-deploy`` does; ``build`` and ``serve`` (``LOCAL_BUILD_COMMANDS``) do not, and neither
    does a build whose command is unknown (no startup event: mkdocs before 1.4, or a hook called
    directly).

    Returns:
        True only when ``on_startup`` saw a command other than a local build's.

    """
    return BUILD_STATE.command not in {*LOCAL_BUILD_COMMANDS, None}


def complexity_graphs_wanted() -> bool:
    """Return whether this build generates the complexity graphs (the owner, 2026-11-23).

    A publishing build (``publishing``: ``mkdocs gh-deploy``, so ``nox -s docs-deploy``)
    generates them. A local one (``mkdocs build``, ``serve``: ``nox -s lint``, ``lint-docs``,
    ``docs-serve``) does not, as measuring the whole history took about 490 s of the strict
    docs build's 830 on CircleCI, unless ``COMPLEXITY_GRAPHS_VARIABLE`` is ``1``.

    Returns:
        True to generate them, False to write the placeholder.

    Raises:
        PluginError: ``COMPLEXITY_GRAPHS_VARIABLE`` holds a value other than unset, empty,
            ``0`` or ``1``.

    """
    setting = os.environ.get(COMPLEXITY_GRAPHS_VARIABLE, '')
    if setting not in COMPLEXITY_GRAPHS_SETTINGS:
        message = (
            f'{COMPLEXITY_GRAPHS_VARIABLE}={setting!r}: use 1 to generate the complexity '
            'graphs on any build, or 0 (or leave it unset) to generate them only on deploy'
        )
        raise PluginError(message)
    return publishing() or setting == COMPLEXITY_GRAPHS_ON


def make_complexity_graphs(*, graph_script: ModuleType) -> None:
    """Generate the complexity graphs when this build wants them, else keep or write a placeholder.

    Args:
        graph_script: The complexity graph script (``load_graph_script``).

    """
    if complexity_graphs_wanted():
        graph_script.generate_if_stale(
            project_root=graph_script.PROJECT_ROOT, graphs_directory=graph_script.GRAPHS_DIR
        )
    elif graph_script.write_placeholder_unless_current(
        project_root=graph_script.PROJECT_ROOT, graphs_directory=graph_script.GRAPHS_DIR
    ):
        LOG.info(
            'Complexity graphs: a placeholder (only a deploy generates them; '
            '%s=1 generates them here)',
            COMPLEXITY_GRAPHS_VARIABLE,
        )
    else:
        LOG.info('Complexity graphs: kept, generated from this commit')


def on_pre_build(config: MkDocsConfig) -> None:
    """Generate the complexity graphs (or their placeholder), then the performance graphs.

    mkdocs runs this before a build. A build that wants the graphs (``complexity_graphs_wanted``)
    generates them unless current (``generate_if_stale``); any other keeps graphs generated from
    HEAD and otherwise writes the placeholder (``write_placeholder_unless_current``), whose page
    still holds the explorer, so ``missing_explorer_files`` checks it as it checks a deploy's.

    Args:
        config: The mkdocs configuration (unused: the graphs' places are fixed by the scripts).

    Raises:
        PluginError: The complexity generation failed (git, radon or wily), or
            ``COMPLEXITY_GRAPHS_VARIABLE`` is not a known setting; the build stops.

    """
    del config
    graph_script = load_graph_script()
    with logged_stage('Complexity graphs'):
        try:
            make_complexity_graphs(graph_script=graph_script)
        except graph_script.ComplexityGraphError as error:
            message = f'Could not generate the complexity graphs: {error}'
            raise PluginError(message) from error
    with logged_stage('Performance graphs'):
        generate_performance_graphs()


def repository_head_commit() -> str:
    """Return the commit the docs are built from (the repository's HEAD).

    Returns:
        Its full hash.

    """
    graph_script = load_graph_script()
    return graph_script.head_commit(project_root=graph_script.PROJECT_ROOT)


def build_browser_games() -> None:
    """Build every browser game afresh (``python -m scripts.build_browser_bundle all``).

    Its output goes to this process's, so a deploy shows the build's progress.

    Raises:
        PluginError: The build failed; the deploy stops before anything is pushed.

    """
    result = run_command(
        command=[sys.executable, *BROWSER_GAMES_BUILD],
        environment=os.environ,
        timeout_seconds=BROWSER_GAMES_BUILD_TIMEOUT_SECONDS,
        working_directory=SCRIPTS_DIRECTORY.parent,
    )
    if result.returncode != 0:
        message = (
            f'python {" ".join(BROWSER_GAMES_BUILD)} failed (exit status {result.returncode}): '
            'no browser games to publish'
        )
        raise PluginError(message)


def games_site_problem(*, games_directory: Path, head_commit: str) -> str | None:
    """Return why a games site is not this commit's games, or None when it is.

    Returns:
        The reason (no site, no stamp, another commit's, a game it lists missing), or None.

    """
    if not (games_directory / 'index.html').is_file():
        return f'No browser games in {games_directory}'
    stamp_path = games_directory / SITE_STAMP_NAME
    if not stamp_path.is_file():
        return (
            f'{games_directory} has no {SITE_STAMP_NAME}: it was built before games sites '
            'were stamped'
        )
    stamp = json.loads(stamp_path.read_text(encoding='utf-8'))
    if stamp.get('commit') != head_commit:
        return f'{games_directory} was built from {stamp.get("commit")}, not {head_commit}'
    missing = [
        game
        for game in stamp.get('games', [])
        if not (games_directory / game / 'index.html').is_file()
    ]
    if missing:
        return f'{games_directory} lacks games its stamp lists: {", ".join(missing)}'
    return None


def copy_browser_games(
    *, games_directory: Path, site_directory: Path, head_commit: str, publishing: bool
) -> bool:
    """Copy the browser games' site into the docs site as play/, when it is this commit's.

    Args:
        games_directory: The games' site (``python -m scripts.build_browser_bundle all``).
        site_directory: The built docs site.
        head_commit: The commit the docs are built from.
        publishing: Whether the site is being deployed: then games that are not this commit's
            stop the build rather than leave play/ out.

    Returns:
        Whether the games were copied (False: none built from this commit, on a local build).

    Raises:
        PluginError: A deploy's games site is not this commit's (``games_site_problem``).

    """
    problem = games_site_problem(games_directory=games_directory, head_commit=head_commit)
    if problem is not None:
        if publishing:
            message = (
                f'Not publishing {PLAY_DIRECTORY_NAME}/: {problem}. Build the games with '
                f'uv run python {" ".join(BROWSER_GAMES_BUILD)}'
            )
            raise PluginError(message)
        LOG.info('%s: the site has no %s/', problem, PLAY_DIRECTORY_NAME)
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

    mkdocs runs this after a build, before ``gh-deploy`` publishes the site. The games: a deploy
    builds them afresh (``build_browser_games``), then ``copy_browser_games``; the caches
    would keep this build alive (see the module docstring);
    the explorers: ``missing_explorer_files``.

    Args:
        config: The mkdocs configuration (its ``site_dir``).

    Raises:
        PluginError: A deploy's games failed to build or are not this commit's, or an
            explorer's page, its explorer or a file it names is missing from the built site.

    """
    site_directory = Path(config.site_dir)
    publishing_site = publishing()
    if publishing_site:
        with logged_stage('Browser games build'):
            build_browser_games()
    copy_browser_games(
        games_directory=BROWSER_GAMES_DIRECTORY,
        site_directory=site_directory,
        head_commit=repository_head_commit(),
        publishing=publishing_site,
    )
    for cache in documentation_caches():
        cache.cache_clear()
    missing = missing_explorer_files(site_directory=site_directory)
    if missing:
        message = "The explorers' pages name files the built site lacks:\n" + '\n'.join(missing)
        raise PluginError(message)
