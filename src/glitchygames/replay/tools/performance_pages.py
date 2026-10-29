"""The ``performance-pages`` tool: the run ledger's graph pages, one per recording.

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md; moved here from
scripts/generate_performance_graphs.py (Part 3, Stage D, Task D7), which keeps only our docs
site's paths and the snippet its page includes, and calls this module:

1. ``merged_ledger``: the project's ledger rows from every source, each row once
   (``glitchygames.recording_metrics.merge_ledgers``), driven by its ``[tool.glitchygames]``
   settings (passed in, never read here from any one project): the row files in its
   ``ledger-directory`` (labelled with the commit their code landed in: ``landed_rows``, by the
   git history of the ``measured-paths``), the ledger it publishes (``published-ledger``,
   ``git show REF:PATH`` of the local ref; nothing is fetched) and its ``pending-ledger``. Rows
   measured on uncommitted changes (``LedgerRow.from_uncommitted_changes``), and row files whose
   code never landed, are left out of a build that is published (``include_uncommitted_changes``
   False) and shown, labelled, in a local one;
2. ``write_performance_pages``: the merged ledger as one file (``ledger_file_name``: the
   published ledger's name, so a deploy publishes it where it is read back), then one graph page
   per recording (``<console-script>-<name>.html``): processing time per frame (p50, p99 and
   max) by commit, frames over budget by commit, and the live runs' frame times (how steady
   pacing was), one line per machine and kind of run (``performance_series``: times compare only
   on one machine, and paced frames process slower than replayed ones); FPS by commit
   (``fps_charts``: live runs' achieved FPS solid, replays' headroom FPS dashed, each point the
   average with its 5% low and 5% high as an error bar, and a line at the target FPS from
   ``budget_seconds``); and the machines view (``machines_chart``: each machine's latest replay
   as a bar of average headroom FPS with its 5% low and high, CI machines marked). FPS is read
   from the rows' seconds with ``fps_from_seconds``; rows from before the slice means
   (2026-10-28) have no FPS point. The x axis is the
   commits in commit-date order, labelled with their short hash; plotly.js comes from jsDelivr
   (``PLOTLY_JS_URL``), so rendering imports nothing beyond the engine's own dependencies. Then a
   frame x commit heatmap per machine from the rows' per-frame profiles (``FrameProfile``: each
   bucket's slowest frame); rows without one (older rows, a recording's own runs) have no
   heatmap line.

A file is rewritten only when its text changed (``write_if_changed``), and graph pages of
recordings no longer in the ledger are removed.

``build_performance_pages`` is one build, local or published: the tool and our docs site's
mkdocs hook (scripts/generate_performance_graphs.py: published for ``gh-deploy``) both build
through it, so a deploy's pages are the tool's ``--published`` ones.

The front ends (glitchygames/replay/tools/registry.py) write the project's pages into DIRECTORY:
a local build (rows from uncommitted changes shown, labelled), or with ``--published`` what a
deploy publishes. They run no game:

- **On the game**: ``mygame --performance-pages DIRECTORY [--published]``
  (``performance_pages_on_the_game``) runs from ``GameEngine.__init__``, before the engine
  starts pygame: the game is neither built nor shown.
- **The command**: ``glitchygames performance-pages DIRECTORY [--published]``
  (``performance_pages_command``).

Both find the project as verify does (``verify.verify_project_root``) and read its settings from
there; a DIRECTORY in the project's local directory (``.glitchygames/``) is made through
``settings.ensure_local_directory`` (``measure.ensure_directory``).

Exit codes: ``SUCCESS``; ``UNUSABLE_INPUT`` for settings that can't be read, a pending ledger
that can't be read (no permission, not UTF-8: ``UnreadableLedgerError``, naming it), or row files
git can't date (no repository); ``CANNOT_WRITE_OUTPUT`` when DIRECTORY can't be written.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict

from glitchygames.code_tree import landed_code_trees
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_metrics import (
    MILLISECONDS_PER_SECOND,
    FrameProfile,
    LedgerRow,
    PerformanceSeries,
    fps_from_seconds,
    landed_rows,
    ledger_text,
    merge_ledgers,
    parse_ledger,
    performance_series,
    publishable_rows,
    published_ledger_text,
    read_ledger_file,
    read_row_files,
    short_commit,
)
from glitchygames.replay.tools.measure import (
    UnreadableLedgerError,
    ensure_directory,
    pending_path_of,
    read_settings,
)
from glitchygames.replay.tools.settings import ProjectSettingsError
from glitchygames.replay.tools.verify import verify_project_root

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence

    from glitchygames.replay.tools.registry import Tool
    from glitchygames.replay.tools.settings import ProjectSettings
    from glitchygames.scenes import Scene

LOG = logging.getLogger(__name__)

GRAPH_PAGE_SUFFIX = '.html'
# The ledger file's name when the project publishes none ([tool.glitchygames] published-ledger)
DEFAULT_LEDGER_NAME = 'replay-ledger.jsonl'
# The plotly.js the complexity graphs load (plotly 5.24.1 writes plotly.js 2.35.2), on jsDelivr
PLOTLY_JS_URL = 'https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js'
MICROSECONDS_PER_MILLISECOND = 1000.0
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
# Each statistic of one series is told apart by its dash, so color only names the series
STATISTIC_DASHES = {'p50': 'solid', 'p99': 'dash', 'max': 'dot'}
# On the FPS chart the dash tells the kind of run instead (each series' statistics are one line:
# the average, with the 5% low and 5% high as its error bar)
LIVE_RUN_DASH = 'solid'
REPLAY_DASH = 'dash'
# How a machine that measured in continuous integration is labelled (its virtual runner's
# timings are noisy)
CONTINUOUS_INTEGRATION_LABEL = ' (CI)'


class LedgerSources(BaseModel):
    """A project's ledger rows from every source, merged (``merged_ledger``).

    Attributes:
        rows: Ledger rows after merging (and, for a published build, leaving out trials).
        repository_rows: Row files read from the project's ledger directory, landed or not.
        published_rows: Rows read from the published ledger.
        pending_rows: Rows read from the pending file.
        unreadable_lines: Lines of either that were not a readable row (skipped).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    rows: tuple[LedgerRow, ...]
    repository_rows: int
    published_rows: int
    pending_rows: int
    unreadable_lines: int


class WrittenPages(BaseModel):
    """What ``write_performance_pages`` wrote.

    Attributes:
        series: Every graph series, by recording.
        pages: Each recording's graph page name, in the series' recording order.
        written: The files whose text changed (and were written).
        removed: Graph pages removed (their recording left the ledger).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    series: tuple[PerformanceSeries, ...]
    pages: dict[str, str]
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
    # The game's commit date, as the row's commit is the game's
    revision = row.run.game_or_engine_revision
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


def _rounded_fps(seconds: float | None) -> float | None:
    fps = fps_from_seconds(seconds=seconds)
    return None if fps is None else round(fps, 1)


class FpsPoint(BaseModel):
    """One row's FPS: its average and its 5% low and 5% high (``fps_point``).

    Attributes:
        average: 1 / the mean time.
        low: 1 / the mean of the slowest 5% (``recording_history.slice_frame_count``).
        high: 1 / the mean of the fastest 5%.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    average: float
    low: float
    high: float


def fps_point(*, row: LedgerRow, paced: bool) -> FpsPoint | None:
    """Return a row's FPS: achieved (a paced live run's frame times) or headroom (a replay's).

    A paced run's processing times are no headroom (the processor slows between paced frames:
    glitchygames/replay/processing.py), so a paced row gives its frame times and an unpaced
    one its processing times, each read as FPS with ``fps_from_seconds``.

    Args:
        row: The row.
        paced: Whether its series paced its frames.

    Returns:
        The point, or None when the row lacks the figures (a row from before the slice means, a
        paced row without frame times) or a time is zero.

    """
    summary = row.summary
    if summary is None:
        return None
    if paced:
        frame_time = summary.frame_time
        if frame_time is None:
            return None
        mean, slowest, fastest = (
            frame_time.mean_seconds,
            frame_time.slowest_5_percent_mean_seconds,
            frame_time.fastest_5_percent_mean_seconds,
        )
    else:
        mean, slowest, fastest = (
            summary.mean_processing_seconds,
            summary.slowest_5_percent_mean_processing_seconds,
            summary.fastest_5_percent_mean_processing_seconds,
        )
    average, low, high = _rounded_fps(mean), _rounded_fps(slowest), _rounded_fps(fastest)
    if average is None or low is None or high is None:
        return None
    return FpsPoint(average=average, low=low, high=high)


def _error_bars(*, points: Sequence[FpsPoint], width: int) -> dict[str, Any]:
    """Return plotly error bars from each point's 5% low to its 5% high."""
    return {
        'type': 'data',
        'symmetric': False,
        'array': [round(point.high - point.average, 1) for point in points],
        'arrayminus': [round(point.average - point.low, 1) for point in points],
        'thickness': 1.5,
        'width': width,
    }


def _slices_hover(*, point: FpsPoint) -> str:
    return f'5% low {point.low:.0f}, 5% high {point.high:.0f} fps'


def _fps_trace(
    *, series: PerformanceSeries, slot: int, points: Sequence[tuple[str, FpsPoint, str]]
) -> dict[str, Any]:
    kind = 'achieved FPS' if series.paced else 'headroom FPS'
    return {
        'type': 'scatter',
        'mode': 'lines+markers',
        'name': f'{series.label}: {kind}',
        'x': [label for label, _, _ in points],
        'y': [point.average for _, point, _ in points],
        'customdata': [f'{_slices_hover(point=point)}<br>{detail}' for _, point, detail in points],
        'error_y': _error_bars(points=[point for _, point, _ in points], width=4),
        'meta': slot,
        'line': {'width': 2, 'dash': LIVE_RUN_DASH if series.paced else REPLAY_DASH},
        'marker': {'size': 8},
        'hovertemplate': '%{x}: avg %{y} fps, %{customdata}<extra>%{fullData.name}</extra>',
    }


def target_fps(*, series_list: Sequence[PerformanceSeries]) -> float | None:
    """Return the target FPS the FPS charts draw a line at: 1 / the latest row's budget.

    Args:
        series_list: The recording's series.

    Returns:
        The target FPS of the latest row with a budget (``budget_seconds``), to 0.1, or None
        when no row has one (an uncapped recording).

    """
    budgets = [
        row.summary.budget_seconds
        for row in merge_ledgers(ledgers=[[row for series in series_list for row in series.rows]])
        if row.summary is not None and row.summary.budget_seconds is not None
    ]
    return _rounded_fps(budgets[-1]) if budgets else None


def fps_charts(*, series_list: Sequence[PerformanceSeries]) -> list[dict[str, Any]]:
    """Return the FPS-by-commit traces: one per series with any row that has the figures.

    A paced series (live runs) plots its achieved FPS, solid; an unpaced one (replays) its
    headroom FPS, dashed (``fps_point``). Each point is the average, its error bar running from
    the 5% low to the 5% high. Rows without the figures are left out.

    Args:
        series_list: The recording's series.

    Returns:
        The plotly traces.

    """
    traces: list[dict[str, Any]] = []
    for slot, series in enumerate(series_list):
        points = [
            (short_commit(run=row.run) or '', point, _hover_detail(row=row))
            for row in series.rows
            if (point := fps_point(row=row, paced=series.paced)) is not None
        ]
        if points:
            traces.append(_fps_trace(series=series, slot=slot, points=points))
    return traces


def machine_name(*, row: LedgerRow) -> str:
    """Return the machines view's name for a row's machine: its label, marked when in CI.

    Returns:
        ``LedgerRow.machine``, with ``CONTINUOUS_INTEGRATION_LABEL`` when the run was in
        continuous integration (``MachineState.continuous_integration``).

    """
    state = row.run.machine_state
    in_continuous_integration = state is not None and state.continuous_integration
    return f'{row.machine}{CONTINUOUS_INTEGRATION_LABEL if in_continuous_integration else ""}'


def machines_chart(*, series_list: Sequence[PerformanceSeries]) -> dict[str, Any] | None:
    """Return the machines view: each machine's latest replay as a bar of headroom FPS.

    Replays only (unpaced series): paced runs' times include the wait for the frame deadline.
    Each machine's latest row in commit order that has the figures (``fps_point``) is one bar of
    its average headroom FPS, with an error bar from its 5% low to its 5% high, so machines
    compare at a glance. A machine that measured in CI is marked (``machine_name``).

    Args:
        series_list: The recording's series.

    Returns:
        One plotly bar trace (``meta``: each bar's series slot, for its color), or None when no
        replay row has the figures.

    """
    bars: list[tuple[int, LedgerRow, FpsPoint]] = []
    for slot, series in enumerate(series_list):
        if series.paced:
            continue
        measured = [
            (row, point)
            for row in series.rows
            if (point := fps_point(row=row, paced=False)) is not None
        ]
        if measured:
            row, point = measured[-1]
            bars.append((slot, row, point))
    if not bars:
        return None
    return {
        'type': 'bar',
        'name': 'headroom FPS, latest replay',
        'x': [machine_name(row=row) for _, row, _ in bars],
        'y': [point.average for _, _, point in bars],
        'customdata': [
            f'{_slices_hover(point=point)}<br>commit {short_commit(run=row.run) or ""}, '
            f'{_hover_detail(row=row)}'
            for _, row, point in bars
        ],
        'error_y': _error_bars(points=[point for _, _, point in bars], width=6),
        'meta': [slot for slot, _, _ in bars],
        'marker': {},
        'hovertemplate': '%{x}: avg %{y} fps, %{customdata}<extra></extra>',
    }


def recording_charts(*, series_list: Sequence[PerformanceSeries]) -> dict[str, Any]:
    """Return a recording's charts as plotly traces, and the commits' order.

    Args:
        series_list: The recording's series.

    Returns:
        ``commits`` (short hashes, commit-date order), ``processing``, ``over_budget`` and
        ``frame_time`` trace lists (``frame_time`` empty when no live run has a commit),
        ``fps`` (``fps_charts``), ``machines`` (``machines_chart``, or None), ``target_fps``
        (``target_fps``, or None) and ``heatmaps`` (``profile_heatmap``, one per series with a
        profiled row).

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
        'fps': fps_charts(series_list=series_list),
        'machines': machines_chart(series_list=series_list),
        'target_fps': target_fps(series_list=series_list),
        'heatmaps': [
            heatmap
            for series in series_list
            if (heatmap := profile_heatmap(series=series)) is not None
        ],
    }


def _bucket_hover(*, profile: FrameProfile, bucket: int) -> str:
    first, last = profile.bucket_frames(bucket=bucket)
    scene = profile.bucket_scene(bucket=bucket)
    maximum = profile.max_microseconds[bucket]
    parts = [f'frames {first}-{last}']
    if scene is not None:
        parts.append(f'scene {scene}')
    parts.append(
        'not timed' if maximum is None else f'max {maximum / MICROSECONDS_PER_MILLISECOND:.3f} ms'
    )
    return ', '.join(parts)


def _bucket_milliseconds(*, profile: FrameProfile, bucket: int) -> float | None:
    """Return a bucket's slowest time in milliseconds (None: untimed, or past the profile)."""
    if bucket >= len(profile.max_microseconds):
        return None
    maximum = profile.max_microseconds[bucket]
    return None if maximum is None else maximum / MICROSECONDS_PER_MILLISECOND


def profile_heatmap(*, series: PerformanceSeries) -> dict[str, Any] | None:
    """Return a series' frame x commit heatmap (each bucket's slowest frame, by commit).

    Args:
        series: One recording on one machine, in commit order.

    Returns:
        A plotly heatmap trace (``y``: the commits whose row has a profile; ``x``: bucket
        positions; ``z``: milliseconds, None where untimed or past a shorter profile), or None
        when no row has a profile.

    """
    profiled = [
        (short_commit(run=row.run) or '', row.profile)
        for row in series.rows
        if row.profile is not None
    ]
    if not profiled:
        return None
    width = max(len(profile.max_microseconds) for _, profile in profiled)
    values: list[list[float | None]] = []
    hovers: list[list[str]] = []
    for _, profile in profiled:
        buckets = len(profile.max_microseconds)
        values.append([
            _bucket_milliseconds(profile=profile, bucket=bucket) for bucket in range(width)
        ])
        hovers.append([
            _bucket_hover(profile=profile, bucket=bucket) if bucket < buckets else ''
            for bucket in range(width)
        ])
    return {
        'type': 'heatmap',
        'name': series.label,
        'x': list(range(width)),
        'y': [label for label, _ in profiled],
        'z': values,
        'customdata': hovers,
        'hoverongaps': False,
        'hovertemplate': '%{y}: %{customdata}<extra></extra>',
        'colorbar': {'title': {'text': 'ms'}},
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
<h2>FPS by commit: achieved by live runs (solid), headroom of replays (dashed)</h2>
<p>Each point is the average; its bar runs from the 5% low (the slowest 5% of frames, averaged)
to the 5% high. Live runs are paced, so they never pass the target (the dotted line); a replay's
headroom is 1 / its processing time, how fast the work alone could run. Log scale.</p>
<div class="chart" id="fps"></div>
<h2>Machines: headroom FPS of each machine's latest replay</h2>
<p>Replays only (never paced runs). The bar is the average, its error bar the 5% low to the 5%
high. Machines marked (CI) measured on continuous integration's virtual runners: noisy.</p>
<div class="chart" id="machines"></div>
<h2>Slowest frame across the recording, by commit (ms)</h2>
<p>Each cell is the slowest frame of a stretch of the recording (about 1% of it). The heatmap
shows time only: whether the work changed (a frame whose content hash differs) is what the
behaviour-change map shows (<code>glitchygames report</code>).</p>
<div id="heatmaps"></div>
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
  fps: 'No measurements with FPS figures yet: rows from before the 5% slices have none.',
}};
const target = charts.target_fps;
const targetLine = target === null ? [] : [{{
  type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: target, y1: target,
  line: {{ color: muted, width: 1.5, dash: 'dot' }},
}}];
// A log axis places annotations by the value's logarithm
const targetLabel = (logarithmic) => target === null ? [] : [{{
  xref: 'paper', x: 1, xanchor: 'right', yref: 'y', y: logarithmic ? Math.log10(target) : target,
  yanchor: 'bottom', text: 'target ' + target + ' fps', showarrow: false,
  font: {{ color: muted, size: 11 }},
}}];
for (const name of ['processing', 'over_budget', 'frame_time', 'fps']) {{
  const traces = charts[name];
  const element = document.getElementById(name);
  if (traces.length === 0) {{
    element.outerHTML = '<p>' + empty[name] + '</p>';
    continue;
  }}
  for (const trace of traces) {{
    trace.line.color = palette[trace.meta % palette.length];
    trace.marker.color = trace.line.color;
    if (trace.error_y) {{
      trace.error_y.color = trace.line.color;
    }}
  }}
  const fps = name === 'fps';
  Plotly.newPlot(element, traces, {{
    shapes: fps ? targetLine : [],
    annotations: fps ? targetLabel(true) : [],
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
    yaxis: fps
      ? {{ type: 'log', title: {{ text: 'fps' }}, gridcolor: grid, linecolor: grid }}
      : {{ rangemode: 'tozero', gridcolor: grid, linecolor: grid, zerolinecolor: grid }},
  }}, {{ responsive: true, displaylogo: false }});
}}
const machinesElement = document.getElementById('machines');
if (charts.machines === null) {{
  machinesElement.outerHTML = '<p>No replays with FPS figures yet.</p>';
}} else {{
  const bars = charts.machines;
  bars.marker.color = bars.meta.map((slot) => palette[slot % palette.length]);
  bars.error_y.color = muted;
  Plotly.newPlot(machinesElement, [bars], {{
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: {{ color: ink }},
    margin: {{ l: 56, r: 16, t: 24, b: 72 }},
    hovermode: 'closest',
    showlegend: false,
    shapes: targetLine,
    annotations: targetLabel(false),
    xaxis: {{ type: 'category', gridcolor: grid, linecolor: grid }},
    yaxis: {{
      rangemode: 'tozero', title: {{ text: 'headroom fps' }}, gridcolor: grid, linecolor: grid,
      zerolinecolor: grid,
    }},
  }}, {{ responsive: true, displaylogo: false }});
}}
const heatmapScale = dark
  ? [[0, '#1d2b3f'], [1, '#9cc4f5']]
  : [[0, '#e8f0fb'], [1, '#0d3b7a']];
const heatmapContainer = document.getElementById('heatmaps');
if (charts.heatmaps.length === 0) {{
  heatmapContainer.outerHTML = '<p>No measurements with a per-frame profile yet.</p>';
}}
for (const heatmap of charts.heatmaps) {{
  const heading = document.createElement('p');
  heading.textContent = heatmap.name;
  const element = document.createElement('div');
  element.className = 'chart';
  heatmapContainer.append(heading, element);
  heatmap.colorscale = heatmapScale;
  Plotly.newPlot(element, [heatmap], {{
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: {{ color: ink }},
    margin: {{ l: 72, r: 16, t: 8, b: 48 }},
    xaxis: {{ title: {{ text: 'position in the recording (start to end)' }}, showgrid: false }},
    yaxis: {{
      type: 'category', categoryorder: 'array', categoryarray: heatmap.y,
      title: {{ text: 'commit' }},
    }},
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


def write_if_changed(*, path: Path, text: str) -> bool:
    """Write a file only when its text changed (so ``mkdocs serve`` does not rebuild in a loop).

    Args:
        path: The file.
        text: Its text.

    Returns:
        Whether it was written.

    """
    if path.is_file() and path.read_text(encoding='utf-8') == text:
        return False
    path.write_text(text, encoding='utf-8')
    return True


def ledger_file_name(*, settings: ProjectSettings) -> str:
    """Return the merged ledger's file name: the published ledger's, else ``DEFAULT_LEDGER_NAME``.

    Args:
        settings: The project's settings.

    Returns:
        The file name.

    """
    path = settings.published_ledger_path
    return DEFAULT_LEDGER_NAME if path is None else Path(path).name


def merged_ledger(
    *,
    project_root: Path,
    settings: ProjectSettings,
    pending_path: Path,
    include_uncommitted_changes: bool,
) -> LedgerSources:
    """Merge the project's row files, published ledger and pending rows, each row once.

    Args:
        project_root: The project (a git repository when it has row files; its published ref
            holds the published ledger).
        settings: The project's settings (``ledger-directory``, ``measured-paths``,
            ``published-ledger``).
        pending_path: The pending rows.
        include_uncommitted_changes: Keep rows that measured other code than their commit
            (``LedgerRow.from_uncommitted_changes``) and row files whose code has not landed,
            labelled: a local build. False for a build that is published: they leave the ledger
            file and every graph.

    Returns:
        The rows and how many each source gave.

    Raises:
        UnreadableLedgerError: If the pending ledger exists but can't be read.

    """
    repository = read_row_files(directory=project_root / settings.ledger_directory)
    landed = (
        # Only when there are rows: a project without any needs no git
        landed_rows(
            rows=repository,
            landed=landed_code_trees(
                repository=project_root,
                ledger_directory=settings.ledger_directory,
                paths=settings.code_tree_paths,
            ),
            keep_unlanded=include_uncommitted_changes,
        )
        if repository
        else []
    )
    published = parse_ledger(
        text=published_ledger_text(
            project_root=project_root, published_ledger=settings.published_ledger
        )
    )
    try:
        pending = read_ledger_file(path=pending_path)
    except (OSError, UnicodeDecodeError) as error:
        raise UnreadableLedgerError(path=pending_path, cause=error) from error
    rows = merge_ledgers(ledgers=[landed, published.rows, pending.rows])
    if not include_uncommitted_changes:
        rows = publishable_rows(rows=rows)
    unreadable_lines = published.unreadable_lines + pending.unreadable_lines
    if unreadable_lines:
        LOG.warning('Skipped %d unreadable ledger lines', unreadable_lines)
    return LedgerSources(
        rows=tuple(rows),
        repository_rows=len(repository),
        published_rows=len(published.rows),
        pending_rows=len(pending.rows),
        unreadable_lines=unreadable_lines,
    )


def write_performance_pages(
    *, rows: Sequence[LedgerRow], directory: Path, settings: ProjectSettings
) -> WrittenPages:
    """Write the ledger file and a graph page per recording; remove stale graph pages.

    Args:
        rows: The ledger rows (``merged_ledger``'s).
        directory: Where the files go (created when missing).
        settings: The project's settings (``recording-renames``: a moved recording is one
            series; ``published-ledger``: the ledger file's name).

    Returns:
        What was written and removed.

    """
    series_list = performance_series(rows=rows, recording_renames=settings.recording_renames)
    by_recording: dict[str, list[PerformanceSeries]] = {}
    for series in series_list:
        by_recording.setdefault(series.recording, []).append(series)
    pages = {
        recording: graph_page_name(recording=recording, console_script=series[0].console_script)
        for recording, series in by_recording.items()
    }
    files = {ledger_file_name(settings=settings): ledger_text(rows=rows)}
    for recording, name in pages.items():
        files[name] = graph_page_html(recording=recording, series_list=by_recording[recording])
    directory.mkdir(parents=True, exist_ok=True)
    removed = [
        stale.name
        for stale in sorted(directory.glob(f'*{GRAPH_PAGE_SUFFIX}'))
        if stale.name not in files
    ]
    for name in removed:
        (directory / name).unlink()
    written = tuple(
        name for name, text in files.items() if write_if_changed(path=directory / name, text=text)
    )
    return WrittenPages(
        series=tuple(series_list), pages=pages, written=written, removed=tuple(removed)
    )


class PerformancePagesBuild(BaseModel):
    """What ``build_performance_pages`` merged and wrote.

    Attributes:
        sources: The merged rows and how many each source gave.
        pages: What was written and removed.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    sources: LedgerSources
    pages: WrittenPages


def build_performance_pages(
    *,
    project_root: Path,
    settings: ProjectSettings,
    directory: Path,
    pending_path: Path,
    published: bool,
) -> PerformancePagesBuild:
    """Merge the project's ledger and write its pages: one build, local or published.

    The tool (``--published`` or not) and our docs site's mkdocs hook (published for
    ``gh-deploy``, local for ``build`` and ``serve``: scripts/generate_performance_graphs.py)
    both build through this, so a deploy's pages are the tool's published ones. A pending
    ledger that can't be read raises ``merged_ledger``'s ``UnreadableLedgerError`` before
    anything is written.

    Args:
        project_root: The project.
        settings: Its settings.
        directory: Where the pages go (created when missing, after the rows are read).
        pending_path: Its pending ledger (``pending-ledger``, unless a caller says otherwise).
        published: Build what a deploy publishes: leave out rows measured on uncommitted
            changes and row files whose code has not landed (``merged_ledger``'s
            ``include_uncommitted_changes`` False). Otherwise a local build shows them, labelled.

    Returns:
        The merged rows and the pages written.

    """
    sources = merged_ledger(
        project_root=project_root,
        settings=settings,
        pending_path=pending_path,
        include_uncommitted_changes=not published,
    )
    # Made once the rows are read, so a build that can't read them writes nothing; one in the
    # project's local directory (.glitchygames/) gets its .gitignore
    ensure_directory(directory=directory, project_root=project_root)
    pages = write_performance_pages(rows=sources.rows, directory=directory, settings=settings)
    return PerformancePagesBuild(sources=sources, pages=pages)


def performance_pages_in(
    *, project_root: Path, directory: Path, published: bool, prefix: str
) -> ExitCode:
    """Write the project's performance pages into a directory (``build_performance_pages``).

    Args:
        project_root: The project.
        directory: Where the pages go.
        published: Build what a deploy publishes (``--published``), not a local build.
        prefix: What starts a line about a failure (the tool's).

    Returns:
        The exit code (see the module docstring).

    """
    try:
        settings = read_settings(project_root=project_root, prefix=prefix)
    except ProjectSettingsError as error:
        sys.stderr.write(f'{prefix} {error}\n')
        return ExitCode.UNUSABLE_INPUT
    try:
        build = build_performance_pages(
            project_root=project_root,
            settings=settings,
            directory=directory,
            pending_path=pending_path_of(given=None, settings=settings, project_root=project_root),
            published=published,
        )
    except UnreadableLedgerError as error:
        sys.stderr.write(f'{prefix} {error}\n')
        return ExitCode.UNUSABLE_INPUT
    except RuntimeError as error:
        # git could not date the row files (landed_code_trees): no repository, or a broken one
        sys.stderr.write(f'{prefix} {error}\n')
        return ExitCode.UNUSABLE_INPUT
    except OSError as error:
        sys.stderr.write(f'{prefix} could not write the performance pages: {error}\n')
        return ExitCode.CANNOT_WRITE_OUTPUT
    sources = build.sources
    sys.stdout.write(
        f'Graphed {len(build.pages.pages)} recordings from {len(sources.rows)} ledger rows '
        f'({sources.repository_rows} in the repository, {sources.published_rows} published, '
        f'{sources.pending_rows} pending) into {directory}\n'
    )
    return ExitCode.SUCCESS


def performance_pages_on_the_game(
    *, options: dict[str, Any], game: type[Scene] | Scene
) -> ExitCode:
    """Run ``--performance-pages DIRECTORY`` on a game (the game takes no part: the ledger does).

    Args:
        options: The game's parsed options (``performance_pages``, ``published``).
        game: The game (unused: the ledger is the project's).

    Returns:
        ``performance_pages_in``'s exit code.

    """
    del game
    return performance_pages_in(
        project_root=verify_project_root(given=None),
        directory=Path(options['performance_pages']),
        published=options['published'],
        prefix='performance-pages:',
    )


def performance_pages_command(
    *, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]
) -> int:
    """Run ``glitchygames performance-pages DIRECTORY [--published]``.

    Args:
        tool: The performance-pages tool.
        arguments: The subcommand's parsed arguments.
        game_arguments: Always empty (the tool runs no game).

    Returns:
        ``performance_pages_in``'s exit code.

    """
    del game_arguments
    return performance_pages_in(
        project_root=verify_project_root(given=arguments.project_root),
        directory=Path(arguments.performance_pages),
        published=arguments.published,
        prefix=f'glitchygames {tool.name}:',
    )
