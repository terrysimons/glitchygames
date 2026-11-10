#!/usr/bin/env python3
"""Generate the complexity explorer's data for the documentation site (docs/quality/complexity.md).

The data is generated, never committed: every mkdocs build (``mkdocs build``, ``serve``,
``gh-deploy``, so ``nox -s docs-deploy`` and ``docs-serve`` too) generates it first through the
hook scripts/mkdocs_hooks.py, which calls ``generate_if_stale`` (regenerated only when HEAD
changed); running this script regenerates it unconditionally. The steps:

1. check the current commit (HEAD) out in a temporary detached git worktree: wily checks every
   revision it measures out in the working tree it runs in (and refuses a dirty one), so it never
   runs in the checkout being worked in. Uncommitted changes are not measured;
2. rank the ``glitchygames`` modules by their total cyclomatic complexity at HEAD (the sum over
   their functions and methods, measured by radon, the library wily measures with): the
   explorer's order, which shows the top ``TOP_MODULE_COUNT`` first. (``wily rank`` ranks only
   the files the newest measured revision changed, which ranked whatever the last commit
   happened to touch.);
3. build a wily cache of the whole git history, in a temporary directory (``wily build -n``
   with the commit count; about a minute for this repository's history);
4. join each moved module's history (``join_moved_paths``): wily keys its history by file
   path, so a module that moved (the engine's ``glitchygames/`` became ``src/glitchygames/``,
   ``MOVED_PATH_PREFIXES``) would start a new series at the move. Each revision's measurements
   under a former path are renamed to the current path in the cache, so the module's series
   runs through the whole history;
5. read each metric in ``METRICS`` from the cache for every ranked module and every package
   (directory) of ``RANKED_PACKAGE`` at HEAD, keeping only the commits that changed a value
   (``complexity_history``), and write it as ``EXPLORER_DATA_NAME``: docs/js/complexity.js draws
   it with plotly.js (``PLOTLY_JS_URL``, the version the performance pages load), one line per
   module or package, picked by metric, kind, path filter and count;
6. write ``GRAPHS_SNIPPET_NAME``, the markdown docs/quality/complexity.md includes (pymdownx
   snippets; zensical.yml's ``exclude_docs`` keeps it from becoming a page of its own). Without it
   the page builds with its own text only, so ``mkdocs build --strict`` passes either way.

Everything is made in a staging directory inside the output directory
(``STAGING_DIRECTORY_PREFIX``, hidden from mkdocs); each finished file then replaces its
published one in one step, and published files the generation no longer makes (the wily graph
pages earlier generations wrote) are removed. So a docs build reading the data mid-generation
sees the previous files or the new ones, never a half-made one. Generations take a lock
(``GENERATION_LOCK_NAME``, a ``filelock`` lock: released when its process ends, however it
ends), so two builds never generate into one directory at once: a running ``mkdocs serve`` and
the pre-push hook's ``mkdocs build`` both seeing a new HEAD each rewrote the other's pages and
one failed (BUGS.md #214). The second waits, then finds the graphs current. A crashed
generation's staging directory is removed by the next one.

Usage:
    uv run python scripts/generate_complexity_graphs.py

Output (gitignored):
    docs/quality/graphs/complexity-explorer.json  -- what the explorer draws
    docs/quality/graphs/complexity_graphs.md      -- the snippet complexity.md includes

Exit codes: ``SUCCESS``; ``INTERNAL_ERROR`` when git, radon or wily fails (its output is logged).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from filelock import FileLock, Timeout
from pydantic import BaseModel, ConfigDict

from glitchygames.exit_codes import ExitCode
from glitchygames.process import OutputCapture, TimeoutExpired, run_command
from glitchygames.replay.tools.performance_pages import PLOTLY_JS_URL

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

LOG = logging.getLogger(__name__)

# How many modules the explorer shows first: the highest total cyclomatic complexity first
TOP_MODULE_COUNT = 15

# The package whose modules are ranked and graphed
RANKED_PACKAGE = 'src/glitchygames'

# Paths that moved: each revision's measurements under a former prefix are joined to the
# current one (join_moved_paths), so a moved module's series is one line through its history.
# The engine moved to src/ in 4ec9becd (plans/2026-10-24-workspace-packages.md)
MOVED_PATH_PREFIXES: tuple[tuple[str, str], ...] = (('glitchygames/', 'src/glitchygames/'),)
# wily's cache of git revisions (one <revision>.json each) and its index of them
WILY_ARCHIVER_DIRECTORY_NAME = 'git'
WILY_INDEX_NAME = 'index.json'

# The radon block types whose complexity a module's total sums (radon also reports each class,
# whose complexity repeats its methods')
RANKED_BLOCK_TYPES = frozenset({'function', 'method'})

# The explorer's metrics (wily metric name: operator.key, its label)
METRICS = [
    ('maintainability.mi', 'Maintainability Index'),
    ('cyclomatic.complexity', 'Cyclomatic Complexity'),
    ('raw.loc', 'Lines of Code'),
    ('halstead.effort', 'Halstead Effort'),
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / 'docs' / 'quality'
GRAPHS_DIR = DOCS_DIR / 'graphs'

# The markdown docs/quality/complexity.md includes from GRAPHS_DIR
GRAPHS_SNIPPET_NAME = 'complexity_graphs.md'
# What the explorer draws (docs/js/complexity.js), beside the snippet
EXPLORER_DATA_NAME = 'complexity-explorer.json'
# The page is served at quality/complexity/ (mkdocs use_directory_urls), the data at
# quality/graphs/
EXPLORER_DATA_URL_FROM_PAGE = f'../graphs/{EXPLORER_DATA_NAME}'
# How many decimal places a measurement keeps in the explorer's data
MEASUREMENT_DECIMAL_PLACES = 2
# How many characters of a commit's hash name it
SHORT_COMMIT_LENGTH = 7

# The commit the graphs in GRAPHS_DIR were generated from (generate_if_stale)
GENERATED_FROM_NAME = 'generated-from-commit.txt'
# The lock a generation holds, in the output directory (hidden from mkdocs, gitignored with it)
GENERATION_LOCK_NAME = '.generation.lock'
# How long a build waits for another's generation before giving up
GENERATION_LOCK_TIMEOUT_SECONDS = 3600.0
# A generation's staging directory, in the output directory (hidden from mkdocs)
STAGING_DIRECTORY_PREFIX = '.staging-'

# How long one git or radon command may take
TOOL_TIMEOUT_SECONDS = 300.0
# How long the wily cache build may take (about a minute for this repository's history)
WILY_BUILD_TIMEOUT_SECONDS = 1800.0


class RadonBlock(TypedDict):
    """One function, method or class in ``radon cc --json``'s report (the fields ranked on)."""

    type: str
    complexity: int


# ``radon cc --json``: each module's blocks, or {"error": ...} for a module radon cannot parse
type RadonReport = dict[str, list[RadonBlock] | dict[str, str]]


class ComplexityGraphError(Exception):
    """A tool the graphs need (git, radon or wily) failed."""


class ComplexityGraphs(BaseModel):
    """What one generation produced."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # The commit measured last (HEAD), abbreviated, and its commit date (YYYY-MM-DD)
    commit: str
    commit_date: str
    # How many commits the wily cache measured (the whole history)
    commit_count: int
    # The explorer's modules, highest total cyclomatic complexity first
    modules: tuple[str, ...]
    # The explorer's packages (RANKED_PACKAGE and each directory in it at HEAD), by path
    packages: tuple[str, ...]


def run_tool(*, command: Sequence[str], working_directory: Path, timeout_seconds: float) -> str:
    """Run a tool and return its output (standard output and error together).

    Args:
        command: The program and its arguments.
        working_directory: Where it runs.
        timeout_seconds: How long it may take.

    Returns:
        The tool's output.

    Raises:
        ComplexityGraphError: The tool exited with a failure status or outlived its timeout.

    """
    try:
        completed = run_command(
            command=command,
            environment=os.environ,
            timeout_seconds=timeout_seconds,
            capture_output=OutputCapture.TOGETHER,
            working_directory=working_directory,
        )
    except TimeoutExpired as error:
        message = f'{" ".join(command)} did not finish within {timeout_seconds:.0f} seconds'
        raise ComplexityGraphError(message) from error
    output = completed.stdout or ''
    if completed.returncode != 0:
        message = f'{" ".join(command)} failed with exit status {completed.returncode}:\n{output}'
        raise ComplexityGraphError(message)
    return output


def wily_command(*, cache_directory: Path, arguments: Sequence[str]) -> list[str]:
    """Return the command line that runs wily, with its cache in ``cache_directory``.

    Args:
        cache_directory: Where wily keeps its cache (never the default, ``~/.wily/<hash>``).
        arguments: The wily subcommand and its arguments.

    Returns:
        The command line (this interpreter's wily module).

    """
    return [sys.executable, '-m', 'wily', '--cache', str(cache_directory), *arguments]


@contextmanager
def detached_checkout(*, project_root: Path, checkout_directory: Path) -> Generator[Path]:
    """Check HEAD out in a detached git worktree; remove the worktree afterwards.

    Args:
        project_root: The repository.
        checkout_directory: Where the worktree goes (it must not exist yet).

    Yields:
        The worktree's directory.

    """
    run_tool(
        command=['git', 'worktree', 'add', '--detach', str(checkout_directory), 'HEAD'],
        working_directory=project_root,
        timeout_seconds=TOOL_TIMEOUT_SECONDS,
    )
    try:
        yield checkout_directory
    finally:
        run_tool(
            command=['git', 'worktree', 'remove', '--force', str(checkout_directory)],
            working_directory=project_root,
            timeout_seconds=TOOL_TIMEOUT_SECONDS,
        )


def rank_modules(*, radon_report: RadonReport, module_count: int | None = None) -> list[str]:
    """Rank modules by their total cyclomatic complexity, highest first.

    Args:
        radon_report: ``radon cc --json`` output: each module's blocks, or ``{"error": ...}``
            for a module radon could not parse (left out).
        module_count: How many modules to keep, or None for every one.

    Returns:
        The top ``module_count`` module paths; equal totals keep path order.

    """
    totals: dict[str, int] = {}
    for module_path, blocks in sorted(radon_report.items()):
        if not isinstance(blocks, list):
            LOG.warning('radon could not measure %s: %s', module_path, blocks)
            continue
        totals[module_path] = sum(
            block['complexity'] for block in blocks if block['type'] in RANKED_BLOCK_TYPES
        )
    ranked = sorted(totals, key=lambda module_path: -totals[module_path])
    return ranked[:module_count]


def measure_ranked_modules(*, checkout: Path, report_path: Path) -> list[str]:
    """Measure the checkout's ``RANKED_PACKAGE`` modules with radon and rank them.

    Args:
        checkout: The checked-out commit.
        report_path: Where radon writes its JSON report.

    Returns:
        Every module radon measured, highest total cyclomatic complexity first (paths relative
        to the checkout, ``/``-separated).

    Raises:
        ComplexityGraphError: If the checkout has no ``RANKED_PACKAGE`` (this script and HEAD
            disagree on where the engine lives).

    """
    if not (checkout / RANKED_PACKAGE).is_dir():
        message = (
            f'The checked-out commit has no {RANKED_PACKAGE}/ to rank: RANKED_PACKAGE and HEAD '
            'disagree on where the engine lives'
        )
        raise ComplexityGraphError(message)
    run_tool(
        command=[
            sys.executable,
            '-m',
            'radon',
            'cc',
            '--json',
            '--output-file',
            str(report_path),
            RANKED_PACKAGE,
        ],
        working_directory=checkout,
        timeout_seconds=TOOL_TIMEOUT_SECONDS,
    )
    radon_report: RadonReport = json.loads(report_path.read_text(encoding='utf-8'))
    modules = rank_modules(radon_report=radon_report)
    # radon names modules with the platform's separator; wily's paths use /
    return [Path(module_path).as_posix() for module_path in modules]


def current_path(*, path: str) -> str:
    """Return where a measured file is now: its path with a moved prefix replaced.

    Args:
        path: A file's or directory's path as a revision measured it
            (``glitchygames/scenes/scene.py``, or the moved directory itself: ``glitchygames``).

    Returns:
        Its current path (``src/glitchygames/scenes/scene.py``, ``src/glitchygames``), or
        ``path`` when it did not move. wily names files with the platform's separator
        (backslashes on Windows), so a prefix matches in the separator the path uses, and the
        result keeps it.

    """
    separator = '\\' if '\\' in path else '/'
    for former_prefix, current_prefix in MOVED_PATH_PREFIXES:
        former = former_prefix.replace('/', separator)
        current = current_prefix.replace('/', separator)
        if path.startswith(former):
            return current + path.removeprefix(former)
        # The moved directory's own measurement (wily measures directories without a separator)
        if path == former.removesuffix(separator):
            return current.removesuffix(separator)
    return path


def joined_operator_data(
    *, operator_data: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    """Return one revision's measurements with every former path renamed to its current one.

    Args:
        operator_data: A wily revision's ``operator_data``: each operator's measurements by
            file path.

    Returns:
        The same measurements by current path. A revision measuring a file under both paths
        keeps the current path's.

    """
    joined: dict[str, dict[str, object]] = {}
    for operator, measurements in operator_data.items():
        renamed: dict[str, object] = {}
        for path, value in measurements.items():
            moved_to = current_path(path=path)
            # The current path's own measurement wins over a former path's
            if moved_to == path or moved_to not in measurements:
                renamed[moved_to] = value
        joined[operator] = renamed
    return joined


def join_moved_paths(*, cache_directory: Path) -> int:
    """Join each moved module's history in a built wily cache (``MOVED_PATH_PREFIXES``).

    Every revision's measurements and the index's ``tracked_files`` name former paths by their
    current ones, so ``wily graph`` draws a moved module's whole history as one series.

    Args:
        cache_directory: The built wily cache.

    Returns:
        How many revisions held measurements under a former path.

    """
    archiver_directory = cache_directory / WILY_ARCHIVER_DIRECTORY_NAME
    joined_revisions = 0
    for revision_path in sorted(archiver_directory.glob('*.json')):
        revision = json.loads(revision_path.read_text(encoding='utf-8'))
        if revision_path.name == WILY_INDEX_NAME:
            for entry in revision:
                entry['tracked_files'] = sorted({
                    current_path(path=path) for path in entry.get('tracked_files', [])
                })
        else:
            operator_data = revision['operator_data']
            joined = joined_operator_data(operator_data=operator_data)
            if joined == operator_data:
                continue
            joined_revisions += 1
            revision['operator_data'] = joined
        revision_path.write_text(json.dumps(revision), encoding='utf-8')
    return joined_revisions


def wily_revisions(*, cache_directory: Path) -> list[dict[str, Any]]:
    """Return the built cache's revisions, oldest first, each with its measurements.

    Args:
        cache_directory: The built (and joined: ``join_moved_paths``) wily cache.

    Returns:
        Each revision's index entry (``key``, ``date`` in epoch seconds, ``message``) with its
        ``operator_data`` added; a revision without a measurement file is left out. wily's index
        lists the newest first; equal dates keep the index's order, reversed.

    """
    archiver_directory = cache_directory / WILY_ARCHIVER_DIRECTORY_NAME
    index = json.loads((archiver_directory / WILY_INDEX_NAME).read_text(encoding='utf-8'))
    revisions: list[dict[str, Any]] = []
    for entry in reversed(index):
        revision_path = archiver_directory / f'{entry["key"]}.json'
        if not revision_path.is_file():
            continue
        revision = json.loads(revision_path.read_text(encoding='utf-8'))
        revisions.append({**entry, 'operator_data': revision['operator_data']})
    return sorted(revisions, key=itemgetter('date'))


def measurement(
    *, operator_data: dict[str, dict[str, Any]], path: str, metric: str
) -> float | None:
    """Return one file's or directory's measurement of a wily metric in one revision.

    Args:
        operator_data: The revision's measurements: each operator's, by path.
        path: The file or directory.
        metric: The wily metric (``operator.key``: ``raw.loc``).

    Returns:
        Its ``total`` value, rounded to ``MEASUREMENT_DECIMAL_PLACES``, or None when the
        revision did not measure it (the path did not exist yet, or the value is not a number).

    """
    operator, key = metric.split('.', maxsplit=1)
    entry = operator_data.get(operator, {}).get(path)
    if not isinstance(entry, dict):
        return None
    value = entry.get('total', {}).get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return round(float(value), MEASUREMENT_DECIMAL_PLACES)


def packages_at_head(*, revisions: Sequence[dict[str, Any]]) -> list[str]:
    """Return ``RANKED_PACKAGE`` and each directory in it, as the newest revision measured them.

    Args:
        revisions: The cache's revisions, oldest first (``wily_revisions``).

    Returns:
        The directories' paths, sorted; empty when there are no revisions.

    """
    if not revisions:
        return []
    paths = {
        path for measurements in revisions[-1]['operator_data'].values() for path in measurements
    }
    return sorted(
        path
        for path in paths
        if (path == RANKED_PACKAGE or path.startswith(f'{RANKED_PACKAGE}/'))
        and not path.endswith('.py')
    )


def complexity_history(
    *, revisions: Sequence[dict[str, Any]], modules: Sequence[str], packages: Sequence[str]
) -> dict[str, Any]:
    """Return the explorer's data: each module's and package's metrics through the history.

    A path's series of one metric holds a point only at the commits that changed its value (the
    first measurement included), as ``[commit index, value]``: the explorer draws each as a step
    that holds until the next change.

    Args:
        revisions: The cache's revisions, oldest first (``wily_revisions``).
        modules: The modules, in the explorer's order (``measure_ranked_modules``).
        packages: The packages (``packages_at_head``).

    Returns:
        ``commits`` (``commit``, ``date``, ``message``: its first line, oldest first),
        ``metrics`` (``key``, ``label``), ``modules``, ``packages``, ``default_count``,
        ``plotly`` (the plotly.js URL) and ``series`` (by path, then by metric).

    """
    commits = [
        {
            'commit': revision['key'][:SHORT_COMMIT_LENGTH],
            'date': datetime.fromtimestamp(revision['date'], tz=UTC).date().isoformat(),
            'message': str(revision.get('message', '')).split('\n', maxsplit=1)[0],
        }
        for revision in revisions
    ]
    series: dict[str, dict[str, list[list[float]]]] = {}
    for path in (*modules, *packages):
        by_metric: dict[str, list[list[float]]] = {}
        for metric, _label in METRICS:
            points: list[list[float]] = []
            for commit_index, revision in enumerate(revisions):
                value = measurement(
                    operator_data=revision['operator_data'], path=path, metric=metric
                )
                if value is not None and (not points or points[-1][1] != value):
                    points.append([commit_index, value])
            by_metric[metric] = points
        series[path] = by_metric
    return {
        'commits': commits,
        'metrics': [{'key': metric, 'label': label} for metric, label in METRICS],
        'modules': list(modules),
        'packages': list(packages),
        'default_count': TOP_MODULE_COUNT,
        'plotly': PLOTLY_JS_URL,
        'series': series,
    }


def graphs_snippet(*, graphs: ComplexityGraphs) -> str:
    """Return the markdown docs/quality/complexity.md includes: what was measured, the explorer.

    Returns:
        The markdown.

    """
    return '\n'.join((
        (
            f'Generated at commit `{graphs.commit}` ({graphs.commit_date}) from all '
            f'{graphs.commit_count} commits: {len(graphs.modules)} modules and '
            f'{len(graphs.packages)} packages of `{RANKED_PACKAGE}`.'
        ),
        '',
        f'<div class="complexity-explorer" data-source="{EXPLORER_DATA_URL_FROM_PAGE}"></div>',
        '',
    ))


@contextmanager
def generation_lock(*, graphs_directory: Path) -> Generator[None]:
    """Hold the graphs directory's generation lock (made with the directory if missing).

    Args:
        graphs_directory: The output directory.

    Yields:
        While the lock is held.

    Raises:
        ComplexityGraphError: Another generation held it for ``GENERATION_LOCK_TIMEOUT_SECONDS``.

    """
    graphs_directory.mkdir(parents=True, exist_ok=True)
    lock = FileLock(graphs_directory / GENERATION_LOCK_NAME)
    try:
        lock.acquire(timeout=GENERATION_LOCK_TIMEOUT_SECONDS)
    except Timeout as error:
        message = (
            f'Another complexity graph generation held {lock.lock_file} for '
            f'{GENERATION_LOCK_TIMEOUT_SECONDS:.0f} s'
        )
        raise ComplexityGraphError(message) from error
    try:
        yield
    finally:
        lock.release()


def publish_staged_graphs(*, staging_directory: Path, graphs_directory: Path) -> None:
    """Replace the published graphs with the staged ones, file by file, each in one step.

    Published files the staging directory does not hold are removed afterwards, except the
    lock, the commit marker and staging directories (leftovers of a crashed generation are
    removed too: the caller holds the lock, so no other generation is running).

    Args:
        staging_directory: The finished explorer data and snippet.
        graphs_directory: The published files.

    """
    staged_names = {path.name for path in staging_directory.iterdir()}
    for name in sorted(staged_names):
        (staging_directory / name).replace(graphs_directory / name)
    for path in graphs_directory.iterdir():
        if path.name.startswith(STAGING_DIRECTORY_PREFIX):
            shutil.rmtree(path, ignore_errors=True)
        elif path.name not in staged_names | {GENERATION_LOCK_NAME, GENERATED_FROM_NAME}:
            path.unlink()


def generate_complexity_graphs(*, project_root: Path, graphs_directory: Path) -> ComplexityGraphs:
    """Measure HEAD's history and publish the explorer's data and snippet in ``graphs_directory``.

    The caller holds ``generation_lock``. The files are made in a staging directory and
    published only when all are done (``publish_staged_graphs``).

    Args:
        project_root: The repository.
        graphs_directory: Where the explorer's data and snippet are published.

    Returns:
        What was generated.

    """
    graphs_directory.mkdir(parents=True, exist_ok=True)
    staging_directory = Path(
        tempfile.mkdtemp(prefix=STAGING_DIRECTORY_PREFIX, dir=graphs_directory)
    )
    try:
        graphs = _generate_into(project_root=project_root, staging_directory=staging_directory)
        publish_staged_graphs(
            staging_directory=staging_directory, graphs_directory=graphs_directory
        )
    finally:
        shutil.rmtree(staging_directory, ignore_errors=True)
    LOG.info('Wrote %s', graphs_directory / GRAPHS_SNIPPET_NAME)
    return graphs


def _generate_into(*, project_root: Path, staging_directory: Path) -> ComplexityGraphs:
    """Measure HEAD's history and write the explorer's data and snippet into ``staging_directory``.

    Returns:
        What was generated.

    """
    with tempfile.TemporaryDirectory(prefix='complexity-graphs-') as temporary_name:
        temporary_directory = Path(temporary_name)
        cache_directory = temporary_directory / 'wily-cache'
        with detached_checkout(
            project_root=project_root, checkout_directory=temporary_directory / 'checkout'
        ) as checkout:
            commit, commit_date = run_tool(
                command=['git', 'log', '-1', '--format=%h %cs'],
                working_directory=checkout,
                timeout_seconds=TOOL_TIMEOUT_SECONDS,
            ).split()
            commit_count = int(
                run_tool(
                    command=['git', 'rev-list', '--count', 'HEAD'],
                    working_directory=checkout,
                    timeout_seconds=TOOL_TIMEOUT_SECONDS,
                )
            )
            modules = measure_ranked_modules(
                checkout=checkout, report_path=temporary_directory / 'radon.json'
            )
            LOG.info('Building the wily cache from %d commits...', commit_count)
            run_tool(
                command=wily_command(
                    cache_directory=cache_directory,
                    arguments=['build', '--max-revisions', str(commit_count)],
                ),
                working_directory=checkout,
                timeout_seconds=WILY_BUILD_TIMEOUT_SECONDS,
            )
            joined_revisions = join_moved_paths(cache_directory=cache_directory)
            LOG.info("Joined moved modules' histories in %d revisions", joined_revisions)
        revisions = wily_revisions(cache_directory=cache_directory)
        packages = packages_at_head(revisions=revisions)
        history = complexity_history(revisions=revisions, modules=modules, packages=packages)
    (staging_directory / EXPLORER_DATA_NAME).write_text(
        json.dumps(history, separators=(',', ':')), encoding='utf-8'
    )
    graphs = ComplexityGraphs(
        commit=commit,
        commit_date=commit_date,
        commit_count=commit_count,
        modules=tuple(modules),
        packages=tuple(packages),
    )
    (staging_directory / GRAPHS_SNIPPET_NAME).write_text(
        graphs_snippet(graphs=graphs), encoding='utf-8'
    )
    return graphs


def head_commit(*, project_root: Path) -> str:
    """Return the current commit's hash (``git rev-parse HEAD``).

    Args:
        project_root: The repository.

    Returns:
        The full commit hash.

    """
    return run_tool(
        command=['git', 'rev-parse', 'HEAD'],
        working_directory=project_root,
        timeout_seconds=TOOL_TIMEOUT_SECONDS,
    ).strip()


def generate_if_stale(*, project_root: Path, graphs_directory: Path) -> bool:
    """Generate the graphs unless they were already generated from the current commit.

    The graphs measure committed history only, so they change only when HEAD does: the commit
    they were made from is kept in ``GENERATED_FROM_NAME`` next to them, and a build with the
    same HEAD (every ``mkdocs serve`` rebuild, a second ``mkdocs build``) skips the minute the
    generation takes. The check and the generation hold ``generation_lock``, so a build that
    waited for another's generation finds the graphs current.

    Args:
        project_root: The repository.
        graphs_directory: Where the graphs are (and are generated).

    Returns:
        True when the graphs were generated, False when they were current.

    """
    commit = head_commit(project_root=project_root)
    generated_from_path = graphs_directory / GENERATED_FROM_NAME
    with generation_lock(graphs_directory=graphs_directory):
        if (
            generated_from_path.is_file()
            and generated_from_path.read_text(encoding='utf-8').strip() == commit
        ):
            LOG.info('Complexity graphs are current (commit %s)', commit[:12])
            return False
        generate_complexity_graphs(project_root=project_root, graphs_directory=graphs_directory)
        generated_from_path.write_text(f'{commit}\n', encoding='utf-8')
    return True


def main() -> None:
    """Generate the complexity graphs for the documentation site."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    try:
        with generation_lock(graphs_directory=GRAPHS_DIR):
            graphs = generate_complexity_graphs(
                project_root=PROJECT_ROOT, graphs_directory=GRAPHS_DIR
            )
    except ComplexityGraphError as error:
        # The failed tool's own output is the useful part; a traceback would bury it
        sys.stderr.write(f'{error}\n')
        sys.exit(ExitCode.INTERNAL_ERROR)
    LOG.info(
        'Measured %d metrics for %d modules and %d packages from %d commits.',
        len(METRICS),
        len(graphs.modules),
        len(graphs.packages),
        graphs.commit_count,
    )


if __name__ == '__main__':
    main()
