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
   each recording's graphs, framed from the page's URL.

Our settings are read once, from this repository's pyproject.toml, for the docs paths; the
functions are given them (``settings=``), never read them for another project.

Usage:
    uv run python scripts/generate_performance_graphs.py

Output (gitignored): docs/quality/metrics/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from glitchygames.recording_metrics import MILLISECONDS_PER_SECOND, short_commit
from glitchygames.replay.tools.performance_pages import build_performance_pages, write_if_changed
from glitchygames.replay.tools.settings import ProjectSettings, load_project_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

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
GRAPH_FRAME_HEIGHT_PIXELS = 1550


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


def _cell_milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f}'


def latest_table(*, series_list: Sequence[PerformanceSeries]) -> list[str]:
    """Return the markdown table of each series' latest measurement.

    Returns:
        The table's lines.

    """
    lines = [
        '| Recording | Machine | Commit | Frames | p50 ms | p99 ms | Max ms | Over budget |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |',
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
            f'{_cell_milliseconds(summary.max_processing_seconds)} | {over_budget} |'
        )
    return lines


def performance_snippet(
    *, page: PerformancePage, series_list: Sequence[PerformanceSeries], pages: dict[str, str]
) -> str:
    """Return the markdown docs/quality/performance.md includes.

    Args:
        page: The generation's counts.
        series_list: Every series.
        pages: Each recording's graph page name.

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
    lines.extend(('## Latest measurements', '', *latest_table(series_list=series_list), ''))
    for recording, name in pages.items():
        lines.extend((
            f'## `{recording}`',
            '',
            (
                f'<iframe src="{GRAPHS_URL_FROM_PAGE}/{name}" width="100%" '
                f'height="{GRAPH_FRAME_HEIGHT_PIXELS}" frameborder="0"></iframe>'
            ),
            '',
        ))
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
    snippet = performance_snippet(page=counts, series_list=pages.series, pages=pages.pages)
    if write_if_changed(path=metrics_directory / SNIPPET_NAME, text=snippet):
        counts = counts.model_copy(update={'written': (*pages.written, SNIPPET_NAME)})
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
