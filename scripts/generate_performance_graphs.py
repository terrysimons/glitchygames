#!/usr/bin/env python3
"""Generate the docs site's performance pages from the run ledger (docs/quality/performance.md).

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md. Every mkdocs build
runs this through the hook scripts/mkdocs_hooks.py, after the complexity graphs. The pages
themselves are the engine's ``performance-pages`` tool (glitchygames/replay/tools/
performance_pages.py, moved there in Part 3, Stage D, Task D7); this script keeps only what is
our docs site's:

1. where the pages go: docs/<the published ledger's directory> (``METRICS_DIR``: our
   ``[tool.glitchygames]`` ``published-ledger`` is ``origin/gh-pages:quality/metrics/
   replay-ledger.jsonl``), so the deploy publishes the merged ledger at the path it is read back
   from: publishing is how the history persists. The engine merges our row files, the ledger
   published with the site (``git show`` of the local ref; a missing ref or file is an empty
   ledger, and nothing is fetched here: ``nox -s docs-deploy`` fetches first) and the rows
   ``nox -s replay-metrics`` measured since (our ``pending-ledger``), and writes the ledger file
   and one graph page per recording. Rows measured on uncommitted changes are left out of a
   published build (``include_uncommitted_changes`` False: the hook's ``gh-deploy``) and shown,
   labelled, in a local one; they stay in the pending file, since ``glitchygames
   clear-published`` removes only rows gh-pages holds;
2. the snippet docs/quality/performance.md includes (``performance_graphs.md``,
   ``performance_snippet``): the latest measurement of each recording on each machine, then
   the explorer (one chart with pickers for the recording, grouped by game, the chart, the
   statistics and the machines; docs/js/performance.js draws it from
   ``performance-explorer.json``, ``explorer_data``; ``?game=`` in the page's address picks
   a game's first recording, so a game can be linked), then a link to each recording's own
   graph page, by game.

Our settings are read once, from this repository's pyproject.toml, for the docs paths; the
functions are given them (``settings=``), never read them for another project.

Usage:
    uv run python scripts/generate_performance_graphs.py

Output (gitignored): docs/quality/metrics/
"""

from __future__ import annotations

import json
import logging
import tomllib
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from glitchygames.recording_metrics import (
    MILLISECONDS_PER_SECOND,
    fps_from_seconds,
    short_commit,
)
from glitchygames.replay.tools.performance_pages import (
    PLOTLY_JS_URL,
    SERIES_COLORS_DARK,
    SERIES_COLORS_LIGHT,
    build_performance_pages,
    recording_charts,
    write_if_changed,
)
from glitchygames.replay.tools.settings import ProjectSettings, load_project_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from glitchygames.recording_history import RunSummary
    from glitchygames.recording_metrics import PerformanceSeries

LOG = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# This repository's [tool.glitchygames]: the ledgers, what a code tree holds, the moved recordings
PROJECT_SETTINGS = load_project_settings(project_root=PROJECT_ROOT)


def published_ledger_path(*, settings: ProjectSettings) -> str:
    """Return where the project publishes its ledger (the path of its ``published-ledger``).

    Args:
        settings: The project's settings.

    Returns:
        The path on the published ref.

    Raises:
        ValueError: If the project publishes no ledger (the docs pages are generated beside it).

    """
    path = settings.published_ledger_path
    if path is None:
        message = (
            '[tool.glitchygames] has no published-ledger: the performance pages are generated '
            'beside the published ledger'
        )
        raise ValueError(message)
    return path


# Where the deploy publishes the ledger on gh-pages (our published-ledger's path)
PUBLISHED_LEDGER_PATH = published_ledger_path(settings=PROJECT_SETTINGS)
# docs/<the published ledger's directory>: the deploy publishes it at PUBLISHED_LEDGER_PATH
METRICS_DIR = PROJECT_ROOT / 'docs' / Path(PUBLISHED_LEDGER_PATH).parent
LEDGER_NAME = Path(PUBLISHED_LEDGER_PATH).name
PENDING_LEDGER_PATH = PROJECT_ROOT / PROJECT_SETTINGS.pending_ledger
SNIPPET_NAME = 'performance_graphs.md'
# The page is served at quality/performance/ (mkdocs use_directory_urls), the graphs at
# quality/metrics/
GRAPHS_URL_FROM_PAGE = '../metrics'
# A markdown link is resolved from the page's source (docs/quality/performance.md) instead
LEDGER_LINK_FROM_PAGE_SOURCE = f'{METRICS_DIR.name}/{LEDGER_NAME}'
# What the page's explorer draws (docs/js/performance.js), written beside the graph pages
EXPLORER_DATA_NAME = 'performance-explorer.json'
# A game's recordings live under src/games/<its directory>/
GAMES_PATH_PARTS = ('src', 'games')
# Where a recording outside that goes, so that it is still on the page
OTHER_RECORDINGS_SLUG = 'other-recordings'
OTHER_RECORDINGS_NAME = 'Other recordings'


class PerformancePage(BaseModel):
    """What one generation produced.

    Attributes:
        rows: Ledger rows after merging.
        repository_rows: Row files read from the repository (quality/replay-ledger/), landed or
            not.
        published_rows: Rows read from the published ledger.
        pending_rows: Rows read from the pending file.
        unreadable_lines: Lines of either that were not a readable row (skipped).
        graph_pages: The graph pages, one per recording.
        written: The files whose text changed (and were written).
        removed: Graph pages removed (their recording left the ledger).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    rows: int
    repository_rows: int
    published_rows: int
    pending_rows: int
    unreadable_lines: int
    graph_pages: tuple[str, ...]
    written: tuple[str, ...]
    removed: tuple[str, ...]


class GameGraphs(BaseModel):
    """One game's entry in the page's list.

    Attributes:
        slug: Its directory under src/games/, which names it in the page's URL.
        name: What the list shows.
        pages: Each of its recordings' graph page name.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    slug: str
    name: str
    pages: dict[str, str]


def _game_slug(*, recording: str) -> str:
    parts = PurePosixPath(recording).parts
    games_parts = len(GAMES_PATH_PARTS)
    if parts[:games_parts] == GAMES_PATH_PARTS and len(parts) > games_parts + 1:
        return parts[games_parts]
    return OTHER_RECORDINGS_SLUG


def _game_name(*, slug: str, project_root: Path) -> str:
    """Return a game's name: its package description up to the colon, or else its directory.

    Returns:
        The name.

    """
    if slug == OTHER_RECORDINGS_SLUG:
        return OTHER_RECORDINGS_NAME
    pyproject = project_root.joinpath(*GAMES_PATH_PARTS, slug, 'pyproject.toml')
    if not pyproject.is_file():
        return slug
    description = tomllib.loads(pyproject.read_text(encoding='utf-8'))['project']['description']
    name, separator, _ = description.partition(':')
    return name if separator else slug


def games_with_graphs(*, pages: dict[str, str], project_root: Path) -> list[GameGraphs]:
    """Return the games the recordings belong to, by name.

    Args:
        pages: Each recording's graph page name.
        project_root: The repository, whose games name themselves.

    Returns:
        One entry per game, its recordings in the order given.

    """
    pages_by_slug: dict[str, dict[str, str]] = {}
    for recording, page_name in pages.items():
        pages_by_slug.setdefault(_game_slug(recording=recording), {})[recording] = page_name
    games = [
        GameGraphs(
            slug=slug, name=_game_name(slug=slug, project_root=project_root), pages=game_pages
        )
        for slug, game_pages in pages_by_slug.items()
    ]
    return sorted(games, key=lambda game: game.name.casefold())


def _cell_milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f}'


def _cell_fps(*, paced: bool, summary: RunSummary) -> str:
    """Return a run's FPS cell: its average, then its 5% low and 5% high when it has them.

    The same FPS the graphs plot (docs/quality/performance.md, "FPS by commit"): a live (paced)
    run's achieved FPS, 1 / its frame times; a replay's headroom, 1 / its processing times.

    Args:
        paced: Whether the run paced its frames (a live recording) or not (a replay).
        summary: The run's summary.

    Returns:
        ``110 (77-337)``, whole frames per second; the average alone when either slice is
        unknown; empty when the average is (a live run without frame times, or from before
        their mean).

    """
    if paced:
        frame_time = summary.frame_time
        if frame_time is None:
            return ''
        mean_seconds = frame_time.mean_seconds
        slowest_seconds = frame_time.slowest_5_percent_mean_seconds
        fastest_seconds = frame_time.fastest_5_percent_mean_seconds
    else:
        mean_seconds = summary.mean_processing_seconds
        slowest_seconds = summary.slowest_5_percent_mean_processing_seconds
        fastest_seconds = summary.fastest_5_percent_mean_processing_seconds
    average = fps_from_seconds(seconds=mean_seconds)
    if average is None:
        return ''
    low = fps_from_seconds(seconds=slowest_seconds)
    high = fps_from_seconds(seconds=fastest_seconds)
    if low is None or high is None:
        return f'{average:.0f}'
    return f'{average:.0f} ({low:.0f}-{high:.0f})'


def latest_table(*, series_list: Sequence[PerformanceSeries]) -> list[str]:
    """Return the markdown table of each series' latest measurement.

    Its FPS column is the FPS the explorer's FPS chart plots (``_cell_fps``): a live run's
    achieved FPS, a replay's headroom, each its average with the 5% low and 5% high.

    Returns:
        The table's lines.

    """
    lines = [
        (
            '| Recording | Machine | Commit | Frames | p50 ms | p99 ms | Max ms | Over budget | '
            'FPS (5% low-high) |'
        ),
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for series in series_list:
        row = series.rows[-1]
        summary = row.summary
        assert summary is not None, 'performance_series keeps only summarised rows'
        commit = short_commit(run=row.run) or ''
        if row.measured_uncommitted_changes:
            commit = f'{commit} (uncommitted changes)'
        over_budget = '' if summary.frames_over_budget is None else str(summary.frames_over_budget)
        lines.append(
            f'| `{series.recording}` | {series.label} | `{commit}` | {summary.measured_frames} | '
            f'{_cell_milliseconds(summary.p50_processing_seconds)} | '
            f'{_cell_milliseconds(summary.p99_processing_seconds)} | '
            f'{_cell_milliseconds(summary.max_processing_seconds)} | {over_budget} | '
            f'{_cell_fps(paced=series.paced, summary=summary)} |'
        )
    return lines


def explorer_data(
    *, series_list: Sequence[PerformanceSeries], games: Sequence[GameGraphs]
) -> dict[str, Any]:
    """Return what the page's explorer draws: each recording's charts, as its graph page has them.

    The charts are the engine's (``recording_charts``, over the recording's series in the order
    its graph page groups them, so each trace's ``meta`` slot indexes ``series``), less the
    heatmaps, which stay on the recording's own page (``page``).

    Args:
        series_list: Every series.
        games: The games and their recordings' graph pages (``games_with_graphs``), in the
            order the explorer offers them.

    Returns:
        The plotly.js URL, the series palettes and one entry per recording, naming its game
        (``game``: the slug the page's ``?game=`` takes; ``game_name``: what the picker shows).

    """
    recordings: list[dict[str, Any]] = []
    offered = [(game, recording, name) for game in games for recording, name in game.pages.items()]
    for recording_game, recording, name in offered:
        recording_series = [series for series in series_list if series.recording == recording]
        charts = recording_charts(series_list=recording_series)
        del charts['heatmaps']
        recordings.append({
            'game': recording_game.slug,
            'game_name': recording_game.name,
            'recording': recording,
            'page': name,
            'series': [series.label for series in recording_series],
            'charts': charts,
        })
    return {
        'plotly': PLOTLY_JS_URL,
        'colors': {'light': list(SERIES_COLORS_LIGHT), 'dark': list(SERIES_COLORS_DARK)},
        'recordings': recordings,
    }


def performance_snippet(
    *,
    page: PerformancePage,
    series_list: Sequence[PerformanceSeries],
    games: Sequence[GameGraphs],
) -> str:
    """Return the markdown docs/quality/performance.md includes.

    Args:
        page: The generation's counts.
        series_list: Every series.
        games: The games and their recordings' graph pages (``games_with_graphs``).

    Returns:
        The markdown.

    """
    lines = [
        (
            f'Generated from {page.rows} ledger rows ({page.repository_rows} in the repository, '
            f'{page.published_rows} published, {page.pending_rows} pending). The ledger: '
            f'[{LEDGER_NAME}]({LEDGER_LINK_FROM_PAGE_SOURCE}).'
        ),
        '',
    ]
    if not series_list:
        lines.append(
            'No measurements yet: `nox -s replay-metrics` measures the recordings on this machine.'
        )
        return '\n'.join(lines) + '\n'
    lines.extend((
        '## Latest measurements',
        '',
        *latest_table(series_list=series_list),
        '',
    ))
    # One explorer instead of a frame per recording (docs/js/performance.js fills it)
    lines.extend((
        '## Explore',
        '',
        (
            f'<div class="performance-explorer" '
            f'data-source="{GRAPHS_URL_FROM_PAGE}/{EXPLORER_DATA_NAME}" '
            f'data-pages="{GRAPHS_URL_FROM_PAGE}/"></div>'
        ),
        '',
        '## Each recording on its own page',
        '',
        'Every chart at once, with the slowest-frame heatmap per machine:',
        '',
    ))
    lines.extend(
        f'- {game.name}: [`{recording}`]({METRICS_DIR.name}/{name})'
        for game in games
        for recording, name in game.pages.items()
    )
    lines.append('')
    return '\n'.join(lines)


def generate_performance_page(
    *,
    project_root: Path,
    settings: ProjectSettings,
    metrics_directory: Path,
    pending_path: Path,
    include_uncommitted_changes: bool,
) -> PerformancePage:
    """Write the engine's performance pages, then the snippet (see the module docstring).

    Args:
        project_root: The repository (its published ref holds the published ledger).
        settings: Its settings (the ledger directory, code-tree paths, published ledger and
            moved recordings): ``PROJECT_SETTINGS`` for ours.
        metrics_directory: Where the files go (created when missing).
        pending_path: The pending rows.
        include_uncommitted_changes: Keep rows that measured other code than their commit
            (``LedgerRow.from_uncommitted_changes``), labelled: a local build. False for a
            build that is published: they leave the ledger file and every graph.

    Returns:
        What was generated.

    """
    # The engine's one build: a deploy's pages are glitchygames performance-pages --published's
    build = build_performance_pages(
        project_root=project_root,
        settings=settings,
        directory=metrics_directory,
        pending_path=pending_path,
        published=not include_uncommitted_changes,
    )
    sources, pages = build.sources, build.pages
    counts = PerformancePage(
        rows=len(sources.rows),
        repository_rows=sources.repository_rows,
        published_rows=sources.published_rows,
        pending_rows=sources.pending_rows,
        unreadable_lines=sources.unreadable_lines,
        graph_pages=tuple(pages.pages.values()),
        written=pages.written,
        removed=pages.removed,
    )
    games = games_with_graphs(pages=pages.pages, project_root=project_root)
    explorer = json.dumps(
        explorer_data(series_list=pages.series, games=games), separators=(',', ':')
    )
    snippet = performance_snippet(page=counts, series_list=pages.series, games=games)
    written = [
        name
        for name, text in ((EXPLORER_DATA_NAME, explorer), (SNIPPET_NAME, snippet))
        if write_if_changed(path=metrics_directory / name, text=text)
    ]
    if written:
        counts = counts.model_copy(update={'written': (*pages.written, *written)})
    return counts


def main() -> None:
    """Generate the performance graphs for the documentation site."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    # Run by hand, this is a local build: rows from uncommitted changes are shown, labelled
    page = generate_performance_page(
        project_root=PROJECT_ROOT,
        settings=PROJECT_SETTINGS,
        metrics_directory=METRICS_DIR,
        pending_path=PENDING_LEDGER_PATH,
        include_uncommitted_changes=True,
    )
    LOG.info(
        'Graphed %d recordings from %d ledger rows (%d in the repository, %d published, '
        '%d pending) into %s',
        len(page.graph_pages),
        page.rows,
        page.repository_rows,
        page.published_rows,
        page.pending_rows,
        METRICS_DIR,
    )


if __name__ == '__main__':
    main()
