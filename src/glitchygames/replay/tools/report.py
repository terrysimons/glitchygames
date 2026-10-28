"""The ``report`` tool: a recording's runs, speed changes and behaviour-change map.

Design: plans/2026-10-23-recording-metrics-2-behaviour-change-map.md (Part 2 of
plans/2026-10-23-recording-metrics.md); moved here whole from scripts/recording_report.py (Part 3,
Stage D, Task D7). A recording holds up to ten runs (each ``--rebaseline`` stacks one;
glitchygames/recording_history.py); this prints, newest first:

1. **Runs:** each run's commit (abbreviated, with ``uncommitted changes`` when the checkout had
   them), machine (CPU model), power source, when it measured and what it rebaselined, then its
   summary (stored in the header, else computed from the frames): processing p50/p95/p99/max,
   the worst frame and its scene, frames over budget, and a live run's frame times.
2. **Processing:** for each adjacent pair of runs, the frames that did the same work (equal
   content hashes) and how their time changed; spans of frames that got slower or faster by
   more than ``--threshold`` percent and ``--minimum-ms`` milliseconds. Frames whose hash
   changed are different work, never a speed change.
3. **Behaviour changes:** for each adjacent pair of runs, the spans of frames whose content hash
   differs, with the first changed frame's scene and both runs' commits: where to look, and the
   commit range to bisect.

The analysis is glitchygames/recording_metrics.py; this is its command line, on both front ends
(glitchygames/replay/tools/registry.py). It runs no game:

- **On the game**: ``mygame --report PATH [--threshold PERCENT] [--minimum-ms MS] [--spans N]``
  (``report_on_the_game``) runs from ``GameEngine.__init__``, before the engine starts pygame:
  the game is neither built nor shown.
- **The command**: ``glitchygames report PATH [same options]`` (``report_command``).

Usage:
    uv run glitchygames report src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz
    uv run glitchygames report PATH --threshold 10 --minimum-ms 0.1 --spans 50

Exit codes: ``SUCCESS``; ``MISSING_INPUT`` when the file does not exist; ``UNUSABLE_INPUT`` when
it is not a readable recording.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from glitchygames.exit_codes import ExitCode
from glitchygames.recording_history import (
    RunSummary,
    recorded_measurement_runs,
    recording_run_summaries,
)
from glitchygames.recording_metrics import (
    DEFAULT_MINIMUM_CHANGE_SECONDS,
    DEFAULT_SPEED_CHANGE_RATIO,
    MILLISECONDS_PER_SECOND,
    UNKNOWN_COMMIT,
    behaviour_changes,
    machine_label,
    processing_comparisons,
    short_commit,
)
from glitchygames.tracing import FRAMES_FIELD, TraceFormatError, read_trace

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence

    from glitchygames.recording_history import MeasurementRun
    from glitchygames.recording_metrics import FrameSpan, ProcessingSpan
    from glitchygames.replay.tools.registry import Tool
    from glitchygames.scenes import Scene

# How many spans each comparison lists before condensing the rest into a count
DEFAULT_SPAN_LIMIT = 20
PERCENT = 100.0
# --threshold's and --minimum-ms's defaults (the registry's options), as the script's parser had
# them: recording_metrics' defaults, in percent and milliseconds
DEFAULT_THRESHOLD_PERCENT = DEFAULT_SPEED_CHANGE_RATIO * PERCENT
DEFAULT_MINIMUM_MS = DEFAULT_MINIMUM_CHANGE_SECONDS * MILLISECONDS_PER_SECOND


def _milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f} ms'


def describe_run(*, run_index: int, run: MeasurementRun | None) -> str:
    """Describe one run's provenance on one line.

    Args:
        run_index: The run's index (0: the newest).
        run: The run, or None when its header entry is unreadable.

    Returns:
        ``run 0: def5678 (uncommitted changes), machine Apple M4 Max, power mains, measured
        2026-10-23T20:00:00+00:00, rebaselined from OLD``.

    """
    if run is None:
        return f'run {run_index}: unreadable'
    commit = short_commit(run=run) or UNKNOWN_COMMIT
    revision = run.game_or_engine_revision
    if revision is not None and revision.uncommitted_changes:
        commit = f'{commit} (uncommitted changes)'
    power = (
        run.machine_state.power_source
        if run.machine_state is not None and run.machine_state.power_source is not None
        else 'unknown'
    )
    origin = (
        f'rebaselined from {run.rebaselined_from}'
        if run.rebaselined_from is not None
        else f'{"paced" if run.processing_paced else "unpaced"} live run'
    )
    return (
        f'run {run_index}: {commit}, machine {machine_label(run=run)}, power {power}, '
        f'measured {run.measured_at}, {origin}'
    )


def describe_summary(*, summary: RunSummary | None) -> str:
    """Describe a run's summary on one line.

    Args:
        summary: The summary, or None when the run measured no times.

    Returns:
        The frames, processing percentiles, worst frame, frames over budget and (for a live
        run) its frame times.

    """
    if summary is None:
        return 'no processing times'
    scene = '' if summary.worst_frame_scene is None else f', scene {summary.worst_frame_scene}'
    line = (
        f'{summary.measured_frames} frames, processing p50 '
        f'{_milliseconds(summary.p50_processing_seconds)}, p95 '
        f'{_milliseconds(summary.p95_processing_seconds)}, p99 '
        f'{_milliseconds(summary.p99_processing_seconds)}, max '
        f'{_milliseconds(summary.max_processing_seconds)} (frame {summary.worst_frame}{scene})'
    )
    if summary.budget_seconds is not None:
        line = (
            f'{line}, {summary.frames_over_budget} over the '
            f'{_milliseconds(summary.budget_seconds)} budget'
        )
    frame_time = summary.frame_time
    if frame_time is not None:
        late = '' if frame_time.late_frames is None else f', {frame_time.late_frames} late'
        line = (
            f'{line}; frame time p50 {_milliseconds(frame_time.p50_seconds)}, p99 '
            f'{_milliseconds(frame_time.p99_seconds)}, max '
            f'{_milliseconds(frame_time.max_seconds)}{late}'
        )
    return line


def _span_lines(*, spans: Sequence[FrameSpan | ProcessingSpan], span_limit: int) -> list[str]:
    lines = [f'    {span.describe()}' for span in spans[:span_limit]]
    hidden = len(spans) - span_limit
    if hidden > 0:
        lines.append(f'    ... and {hidden} more span{"" if hidden == 1 else "s"}')
    return lines


def report_lines(
    *,
    path: Path,
    trace: dict[str, Any],
    threshold_percent: float,
    minimum_ms: float,
    span_limit: int,
) -> list[str]:
    """Return the report's lines for a read recording.

    Args:
        path: The recording's path (named in the first line, with ``/`` separators on every
            platform, as ``measure`` and ``verify`` name recordings).
        trace: The recording, read (header fields plus ``frames``).
        threshold_percent: How much a same-work frame's time must change, in percent.
        minimum_ms: How much it must change in milliseconds too.
        span_limit: How many spans each comparison lists.

    Returns:
        The lines.

    """
    frames: list[dict[str, Any]] = trace[FRAMES_FIELD]
    runs = recorded_measurement_runs(header=trace)
    summaries = recording_run_summaries(header=trace, frames=frames)
    lines = [
        f'{path.as_posix()}: {len(frames)} frames, {len(runs)} runs',
        '',
        'Runs (newest first):',
    ]
    for run_index, run in enumerate(runs):
        lines.extend((
            f'  {describe_run(run_index=run_index, run=run)}',
            f'    {describe_summary(summary=summaries[run_index])}',
        ))
    lines.extend((
        '',
        (
            f'Processing (same work only; slower or faster by more than '
            f'{threshold_percent:g}% and {minimum_ms:g} ms):'
        ),
    ))
    comparisons = processing_comparisons(
        header=trace,
        frames=frames,
        speed_change_ratio=threshold_percent / PERCENT,
        minimum_change_seconds=minimum_ms / MILLISECONDS_PER_SECOND,
    )
    for comparison in comparisons:
        lines.append(f'  {comparison.describe()}')
        lines.extend(_span_lines(spans=comparison.spans, span_limit=span_limit))
    lines.extend(('', 'Behaviour changes (content hash, adjacent runs):'))
    for change in behaviour_changes(header=trace, frames=frames):
        lines.append(f'  {change.describe()}')
        lines.extend(_span_lines(spans=change.spans, span_limit=span_limit))
    return lines


def report(*, path: Path, threshold_percent: float, minimum_ms: float, span_limit: int) -> ExitCode:
    """Print the report for a recording.

    Args:
        path: The recording (named, as given but with ``/`` separators, in the report's first
            line).
        threshold_percent: How much a same-work frame's time must change, in percent.
        minimum_ms: How much it must change in milliseconds too.
        span_limit: How many spans each comparison lists.

    Returns:
        The exit code (see the module docstring).

    """
    if not path.is_file():
        sys.stderr.write(f'{path.as_posix()}: no such recording\n')
        return ExitCode.MISSING_INPUT
    try:
        trace = read_trace(path=path)
    except TraceFormatError as error:
        sys.stderr.write(f'{error}\n')
        return ExitCode.UNUSABLE_INPUT
    lines = report_lines(
        path=path,
        trace=trace,
        threshold_percent=threshold_percent,
        minimum_ms=minimum_ms,
        span_limit=span_limit,
    )
    sys.stdout.write('\n'.join(lines) + '\n')
    return ExitCode.SUCCESS


def report_on_the_game(*, options: dict[str, Any], game: type[Scene] | Scene) -> ExitCode:
    """Run ``--report PATH`` on a game (the game takes no part: the recording is read).

    Args:
        options: The game's parsed options (``report``, ``threshold``, ``minimum_ms``,
            ``spans``).
        game: The game (unused).

    Returns:
        ``report``'s exit code.

    """
    del game
    return report(
        path=Path(options['report']),
        threshold_percent=options['threshold'],
        minimum_ms=options['minimum_ms'],
        span_limit=options['spans'],
    )


def report_command(*, tool: Tool, arguments: argparse.Namespace, game_arguments: list[str]) -> int:
    """Run ``glitchygames report PATH [--threshold PERCENT] [--minimum-ms MS] [--spans N]``.

    Args:
        tool: The report tool (unused: the report names no tool).
        arguments: The subcommand's parsed arguments.
        game_arguments: Always empty (the tool runs no game).

    Returns:
        ``report``'s exit code.

    """
    del tool, game_arguments
    return report(
        path=Path(arguments.report),
        threshold_percent=arguments.threshold,
        minimum_ms=arguments.minimum_ms,
        span_limit=arguments.spans,
    )
