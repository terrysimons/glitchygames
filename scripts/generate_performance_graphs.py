#!/usr/bin/env python3
"""Generate the docs site's performance graphs from the run ledger (docs/quality/performance.md).

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md. Every mkdocs build
runs this through the hook scripts/mkdocs_hooks.py, after the complexity graphs:

1. the ledger published with the site (``git show origin/gh-pages:quality/metrics/
   replay-ledger.jsonl``; a missing ref or file is an empty ledger, and nothing is fetched here:
   ``nox -s docs-deploy`` fetches first) is merged with the rows ``nox -s replay-metrics``
   measured since (``test-results/replay-metrics/pending.jsonl``), each row once
   (``glitchygames.recording_metrics.merge_ledgers``);
2. the merged ledger is written into the docs tree (``docs/quality/metrics/replay-ledger.jsonl``,
   gitignored), so the deploy publishes it at the same path: publishing is how the history
   persists;
3. one graph page per recording (``<console-script>-<name>.html``): processing time per frame
   (p50, p99 and max) by commit, frames over budget by commit, and the live runs' frame times
   (how steady pacing was), one line per machine and kind of run (``performance_series``: times
   compare only on one machine, and paced frames process slower than replayed ones). The x axis
   is the commits in commit-date order, labelled with their short hash; plotly.js comes from
   jsDelivr, as the complexity graphs' does;
4. the snippet docs/quality/performance.md includes (``performance_graphs.md``): the latest
   measurement of each recording on each machine, then each recording's graphs.

A file is rewritten only when its text changed (so ``mkdocs serve`` does not rebuild in a loop),
and graph pages of recordings no longer in the ledger are removed.

Usage:
    uv run python scripts/generate_performance_graphs.py

Output (gitignored): docs/quality/metrics/
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from glitchygames.recording_metrics import (
    MILLISECONDS_PER_SECOND,
    PENDING_LEDGER_RELATIVE_PATH,
    PUBLISHED_LEDGER_PATH,
    LedgerRow,
    PerformanceSeries,
    ledger_text,
    merge_ledgers,
    parse_ledger,
    performance_series,
    published_ledger_text,
    read_ledger_file,
    short_commit,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

LOG = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# docs/<the published ledger's directory>: the deploy publishes it at PUBLISHED_LEDGER_PATH
METRICS_DIR = PROJECT_ROOT / 'docs' / Path(PUBLISHED_LEDGER_PATH).parent
LEDGER_NAME = Path(PUBLISHED_LEDGER_PATH).name
PENDING_LEDGER_PATH = PROJECT_ROOT / PENDING_LEDGER_RELATIVE_PATH
SNIPPET_NAME = 'performance_graphs.md'
GRAPH_PAGE_SUFFIX = '.html'
# The plotly.js the complexity graphs load (plotly 5.24.1 writes plotly.js 2.35.2), on jsDelivr
PLOTLY_JS_URL = 'https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js'
# The page is served at quality/performance/ (mkdocs use_directory_urls), the graphs at
# quality/metrics/
GRAPHS_URL_FROM_PAGE = '../metrics'
# A markdown link is resolved from the page's source (docs/quality/performance.md) instead
LEDGER_LINK_FROM_PAGE_SOURCE = f'{METRICS_DIR.name}/{LEDGER_NAME}'
GRAPH_FRAME_HEIGHT_PIXELS = 1100
RECORDING_SUFFIX = '.jsonl.gz'

# The categorical palette (the dataviz skill's reference palette: light, dark), in fixed order;
# a series keeps its slot by its place in the recording's series
SERIES_COLORS_LIGHT = (
    '#2a78d6',
    '#eb6834',
    '#1baf7a',
    '#eda100',
    '#e87ba4',
    '#008300',
    '#6250d6',
    '#e34948',
)
SERIES_COLORS_DARK = (
    '#3987e5',
    '#d95926',
    '#199e70',
    '#c98500',
    '#d55181',
    '#008300',
    '#9085e9',
    '#e66767',
)
# Each statistic of one series is told apart by its dash, so colour only names the series
STATISTIC_DASHES = {'p50': 'solid', 'p99': 'dash', 'max': 'dot'}


class PerformancePage(BaseModel):
    """What one generation produced.

    Attributes:
        rows: Ledger rows after merging.
        published_rows: Rows read from the published ledger.
        pending_rows: Rows read from the pending file.
        unreadable_lines: Lines of either that were not a readable row (skipped).
        graph_pages: The graph pages, one per recording.
        written: The files whose text changed (and were written).
        removed: Graph pages removed (their recording left the ledger).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    rows: int
    published_rows: int
    pending_rows: int
    unreadable_lines: int
    graph_pages: tuple[str, ...]
    written: tuple[str, ...]
    removed: tuple[str, ...]


def graph_page_name(*, recording: str, console_script: str) -> str:
    """Return a recording's graph page name (``paddleslap-golden.html``).

    Returns:
        The file name.

    """
    name = Path(recording).name.removesuffix(RECORDING_SUFFIX)
    return f'{console_script}-{name}{GRAPH_PAGE_SUFFIX}'


def _milliseconds(seconds: float) -> float:
    return round(seconds * MILLISECONDS_PER_SECOND, 3)


def _hover_detail(*, row: LedgerRow) -> str:
    revision = row.run.source_revision
    committed = '' if revision is None or revision.committed_at is None else revision.committed_at
    parts = [f'committed {committed[:10]}', f'measured {row.run.measured_at[:16]}']
    if row.frame_count is not None:
        parts.append(f'{row.frame_count} frames')
    if row.measured_uncommitted_changes:
        parts.append('uncommitted changes')
    return ', '.join(parts)


def _trace(
    *,
    series: PerformanceSeries,
    slot: int,
    statistic: str,
    points: Sequence[tuple[str, float, str]],
) -> dict[str, Any]:
    return {
        'type': 'scatter',
        'mode': 'lines+markers',
        'name': f'{series.label}: {statistic}' if statistic else series.label,
        'x': [label for label, _, _ in points],
        'y': [value for _, value, _ in points],
        'customdata': [detail for _, _, detail in points],
        'meta': slot,
        'line': {'width': 2, 'dash': STATISTIC_DASHES.get(statistic, 'solid')},
        'marker': {'size': 8},
        'hovertemplate': '%{x}: %{y}<br>%{customdata}<extra>%{fullData.name}</extra>',
    }


def recording_charts(*, series_list: Sequence[PerformanceSeries]) -> dict[str, Any]:
    """Return a recording's charts as plotly traces, and the commits' order.

    Args:
        series_list: The recording's series.

    Returns:
        ``commits`` (short hashes, commit-date order) and ``processing``, ``over_budget`` and
        ``frame_time`` trace lists (``frame_time`` empty when no live run has a commit).

    """
    commits: list[str] = []
    processing: list[dict[str, Any]] = []
    over_budget: list[dict[str, Any]] = []
    frame_time: list[dict[str, Any]] = []
    ordered_rows = merge_ledgers(ledgers=[[row for series in series_list for row in series.rows]])
    for row in ordered_rows:
        label = short_commit(run=row.run)
        if label is not None and label not in commits:
            commits.append(label)
    for slot, series in enumerate(series_list):
        rows = [(short_commit(run=row.run) or '', row) for row in series.rows]
        summaries = [(label, row, row.summary) for label, row in rows if row.summary is not None]
        for statistic, field in (
            ('p50', 'p50_processing_seconds'),
            ('p99', 'p99_processing_seconds'),
            ('max', 'max_processing_seconds'),
        ):
            points = [
                (label, _milliseconds(getattr(summary, field)), _hover_detail(row=row))
                for label, row, summary in summaries
            ]
            processing.append(_trace(series=series, slot=slot, statistic=statistic, points=points))
        budget_points = [
            (label, float(summary.frames_over_budget), _hover_detail(row=row))
            for label, row, summary in summaries
            if summary.frames_over_budget is not None
        ]
        if budget_points:
            over_budget.append(_trace(series=series, slot=slot, statistic='', points=budget_points))
        timed = [
            (label, row, summary.frame_time)
            for label, row, summary in summaries
            if summary.frame_time is not None
        ]
        if not timed:
            continue
        for statistic, field in (
            ('p50', 'p50_seconds'),
            ('p99', 'p99_seconds'),
            ('max', 'max_seconds'),
        ):
            points = [
                (label, _milliseconds(getattr(times, field)), _hover_detail(row=row))
                for label, row, times in timed
            ]
            frame_time.append(_trace(series=series, slot=slot, statistic=statistic, points=points))
    return {
        'commits': commits,
        'processing': processing,
        'over_budget': over_budget,
        'frame_time': frame_time,
    }


GRAPH_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<script src="{plotly_url}"></script>
<style>
:root {{
  color-scheme: light;
  --surface: #fcfcfb;
  --text-primary: #0b0b0b;
  --text-secondary: #52514e;
  --grid: #e4e3df;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --surface: #1a1a19;
    --text-primary: #f0efec;
    --text-secondary: #c3c2b7;
    --grid: #33332f;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --surface: #1a1a19;
  --text-primary: #f0efec;
  --text-secondary: #c3c2b7;
  --grid: #33332f;
}}
body {{
  background: var(--surface);
  color: var(--text-primary);
  font-family: system-ui, sans-serif;
  margin: 0 16px;
}}
h2 {{ font-size: 1.05rem; margin: 1.2rem 0 0.2rem; }}
p {{ color: var(--text-secondary); margin: 0.2rem 0; font-size: 0.9rem; }}
.chart {{ width: 100%; height: 320px; }}
</style>
</head>
<body>
<h2>Processing time per frame (ms): p50 solid, p99 dashed, max dotted</h2>
<div class="chart" id="processing"></div>
<h2>Frames over budget</h2>
<div class="chart" id="over_budget"></div>
<h2>Live frame time (ms): how steady pacing was</h2>
<div class="chart" id="frame_time"></div>
<script>
const charts = {charts};
const dark = window.matchMedia('(prefers-color-scheme: dark)').matches
  && document.documentElement.dataset.theme !== 'light';
const palette = dark ? {dark_colors} : {light_colors};
const style = getComputedStyle(document.documentElement);
const ink = style.getPropertyValue('--text-primary').trim();
const muted = style.getPropertyValue('--text-secondary').trim();
const grid = style.getPropertyValue('--grid').trim();
const empty = {{
  processing: 'No measurements with a known commit yet.',
  over_budget: 'No measurements with a frame budget yet.',
  frame_time: 'No live runs with a known commit yet: the recordings were made before runs '
    + 'named their commit.',
}};
for (const name of ['processing', 'over_budget', 'frame_time']) {{
  const traces = charts[name];
  const element = document.getElementById(name);
  if (traces.length === 0) {{
    element.outerHTML = '<p>' + empty[name] + '</p>';
    continue;
  }}
  for (const trace of traces) {{
    trace.line.color = palette[trace.meta % palette.length];
    trace.marker.color = trace.line.color;
  }}
  Plotly.newPlot(element, traces, {{
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: {{ color: ink }},
    margin: {{ l: 56, r: 16, t: 40, b: 48 }},
    hovermode: 'closest',
    legend: {{ orientation: 'h', x: 0, y: 1.02, yanchor: 'bottom', font: {{ color: muted }} }},
    xaxis: {{
      type: 'category', categoryorder: 'array', categoryarray: charts.commits,
      title: {{ text: 'commit' }}, gridcolor: grid, linecolor: grid,
    }},
    yaxis: {{ rangemode: 'tozero', gridcolor: grid, linecolor: grid, zerolinecolor: grid }},
  }}, {{ responsive: true, displaylogo: false }});
}}
</script>
</body>
</html>
"""


def _script_json(value: object) -> str:
    # JSON inside <script>: a "</" would end the element
    return json.dumps(value, separators=(',', ':')).replace('</', '<\\/')


def graph_page_html(*, recording: str, series_list: Sequence[PerformanceSeries]) -> str:
    """Return a recording's graph page.

    Args:
        recording: The recording's repository-relative path.
        series_list: Its series.

    Returns:
        The page's HTML.

    """
    return GRAPH_PAGE_TEMPLATE.format(
        title=f'{recording} performance',
        plotly_url=PLOTLY_JS_URL,
        charts=_script_json(recording_charts(series_list=series_list)),
        dark_colors=_script_json(list(SERIES_COLORS_DARK)),
        light_colors=_script_json(list(SERIES_COLORS_LIGHT)),
    )


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
            f'Generated from {page.rows} ledger rows ({page.published_rows} published, '
            f'{page.pending_rows} pending). The ledger: '
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


def _write_if_changed(*, path: Path, text: str) -> bool:
    if path.is_file() and path.read_text(encoding='utf-8') == text:
        return False
    path.write_text(text, encoding='utf-8')
    return True


def generate_performance_page(
    *, project_root: Path, metrics_directory: Path, pending_path: Path
) -> PerformancePage:
    """Merge the ledgers and write the ledger, graph pages and snippet (see the docstring).

    Args:
        project_root: The repository (its ``origin/gh-pages`` holds the published ledger).
        metrics_directory: Where the files go (created when missing).
        pending_path: The pending rows.

    Returns:
        What was generated.

    """
    published = parse_ledger(text=published_ledger_text(project_root=project_root))
    pending = read_ledger_file(path=pending_path)
    rows = merge_ledgers(ledgers=[published.rows, pending.rows])
    series_list = performance_series(rows=rows)
    by_recording: dict[str, list[PerformanceSeries]] = {}
    for series in series_list:
        by_recording.setdefault(series.recording, []).append(series)
    pages = {
        recording: graph_page_name(recording=recording, console_script=series[0].console_script)
        for recording, series in by_recording.items()
    }
    files = {LEDGER_NAME: ledger_text(rows=rows)}
    for recording, name in pages.items():
        files[name] = graph_page_html(recording=recording, series_list=by_recording[recording])
    metrics_directory.mkdir(parents=True, exist_ok=True)
    removed = [
        stale.name
        for stale in sorted(metrics_directory.glob(f'*{GRAPH_PAGE_SUFFIX}'))
        if stale.name not in files
    ]
    for name in removed:
        (metrics_directory / name).unlink()
    counts = PerformancePage(
        rows=len(rows),
        published_rows=len(published.rows),
        pending_rows=len(pending.rows),
        unreadable_lines=published.unreadable_lines + pending.unreadable_lines,
        graph_pages=tuple(pages.values()),
        written=(),
        removed=tuple(removed),
    )
    files[SNIPPET_NAME] = performance_snippet(page=counts, series_list=series_list, pages=pages)
    written = tuple(
        name
        for name, text in files.items()
        if _write_if_changed(path=metrics_directory / name, text=text)
    )
    if counts.unreadable_lines:
        LOG.warning('Skipped %d unreadable ledger lines', counts.unreadable_lines)
    return counts.model_copy(update={'written': written})


def main() -> None:
    """Generate the performance graphs for the documentation site."""
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    page = generate_performance_page(
        project_root=PROJECT_ROOT, metrics_directory=METRICS_DIR, pending_path=PENDING_LEDGER_PATH
    )
    LOG.info(
        'Graphed %d recordings from %d ledger rows (%d published, %d pending) into %s',
        len(page.graph_pages),
        page.rows,
        page.published_rows,
        page.pending_rows,
        METRICS_DIR,
    )


if __name__ == '__main__':
    main()
