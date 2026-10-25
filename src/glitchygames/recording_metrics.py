"""Metrics from recordings' histories: speed changes, behaviour changes and the run ledger.

A leaf beside glitchygames/recording_history.py (no engine imports), shared by
scripts/recording_report.py, scripts/replay_metrics.py and the docs site's performance graphs
(scripts/generate_performance_graphs.py). Designs:
plans/2026-10-23-recording-metrics-1-frame-performance-history.md (Part 1) and
plans/2026-10-23-recording-metrics-2-behaviour-change-map.md (Part 2).

Every comparison is between adjacent runs of one recording: newer run ``i`` and older run
``i + 1`` (index ``i`` is run ``i`` in every history, newest first):

- **Behaviour changes** (``behaviour_changes``): the frames whose ``content_hash`` differs
  between the two runs, grouped into spans of consecutive frames. A frame without a hash for
  either run is unknown, never changed.
- **Processing comparisons** (``processing_comparisons``): only frames whose content hash is
  equal in both runs did the same work, so only they can be faster or slower; a frame whose hash
  differs is "different work". A same-work frame got slower (faster) when its newer time exceeds
  (falls short of) its older time by more than the threshold ratio and by more than the minimum
  seconds (timer noise). Same-direction frames at most ``SPAN_GAP_FRAMES`` apart form a span;
  spans shorter than ``MINIMUM_SPAN_FRAMES`` are counted, not listed.

The run ledger holds one ``LedgerRow`` per recording per run, beyond the
``MEASUREMENT_RUNS_HISTORY_DEPTH`` runs a recording keeps: JSON Lines (``ledger_text``,
``parse_ledger``), published on the docs site's gh-pages branch, deduplicated by ``LedgerRow.key``
(``merge_ledgers``) and graphed per recording, machine and pacing (``performance_series``).
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self, cast

from pydantic import BaseModel, ConfigDict

from glitchygames.build_info import RevisionSource, SourceRevision
from glitchygames.process import TimeoutExpired, run_command
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    PROCESSING_SECONDS_FIELD,
    MeasurementRun,
    RunSummary,
    recorded_measurement_runs,
    recording_content_hash,
    recording_run_summaries,
)
from glitchygames.tracing import FRAMES_FIELD

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from glitchygames.code_tree import LandedCommit

LOG = logging.getLogger('game.recording_metrics')
LOG.addHandler(logging.NullHandler())

# Same-direction speed changes at most this many frames apart are one span
SPAN_GAP_FRAMES = 5
# Spans shorter than this are counted, not listed (a lone slow frame is usually noise)
MINIMUM_SPAN_FRAMES = 3
# A same-work frame changed speed when its time changed by more than this ratio...
DEFAULT_SPEED_CHANGE_RATIO = 0.25
# ...and by more than this (processing times are kept to the microsecond; below 0.2 ms a
# change is timer noise)
DEFAULT_MINIMUM_CHANGE_SECONDS = 0.0002
# How many hex digits of a commit the reports and graphs show
SHORT_COMMIT_DIGITS = 7
UNKNOWN_COMMIT = 'commit unknown'
MILLISECONDS_PER_SECOND = 1000.0
# Where the docs site publishes the ledger: docs/<this> in the docs tree, <this> on gh-pages
PUBLISHED_LEDGER_PATH = 'quality/metrics/replay-ledger.jsonl'
PUBLISHED_LEDGER_REF = 'origin/gh-pages'
# Where measured rows wait for a deploy to publish them, relative to the repository (gitignored)
PENDING_LEDGER_RELATIVE_PATH = Path('test-results') / 'replay-metrics' / 'pending.jsonl'
GIT_TIMEOUT_SECONDS = 30.0
# Recordings that moved, old repository path -> new: their ledger rows from before the move are
# the same series (performance_series groups by the new path), so a recording's history
# continues across its move (plans/2026-10-24-workspace-packages.md)
RECORDING_PATH_RENAMES: dict[str, str] = {
    'glitchygames/examples/paddleslap_demos/rally.jsonl.gz': (
        'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz'
    ),
}


def short_commit(*, run: MeasurementRun | None) -> str | None:
    """Return a run's commit, abbreviated.

    Args:
        run: The run, or None (unreadable).

    Returns:
        The first ``SHORT_COMMIT_DIGITS`` digits of its commit, or None when unknown.

    """
    if run is None or run.source_revision is None or run.source_revision.commit is None:
        return None
    return run.source_revision.commit[:SHORT_COMMIT_DIGITS]


def machine_label(*, run: MeasurementRun) -> str:
    """Return the name a run's machine is grouped by: its CPU model, else its platform.

    Args:
        run: The run.

    Returns:
        The label.

    """
    if run.machine_state is not None and run.machine_state.cpu_model is not None:
        return run.machine_state.cpu_model
    return run.machine


def _plural(count: int, noun: str) -> str:
    return f'{count} {noun}' if count == 1 else f'{count} {noun}s'


def _milliseconds(seconds: float) -> str:
    return f'{seconds * MILLISECONDS_PER_SECOND:.3f} ms'


def _change_percent(*, older: float, newer: float) -> str:
    return f'{(newer - older) / older * 100:+.1f}%'


class FrameSpan(BaseModel):
    """Neighbouring frames that share a finding.

    Attributes:
        first_frame: The first frame's number.
        last_frame: The last frame's number.
        frame_count: How many frames of the span have the finding (gaps not counted).
        first_scene: The first frame's scene, or None when it names none.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    first_frame: int
    last_frame: int
    frame_count: int
    first_scene: str | None

    def describe(self: Self) -> str:
        """Describe the span.

        Returns:
            ``frames 812-940 (scene Game)``, or ``frame 812`` for one frame without a scene.

        """
        where = (
            f'frame {self.first_frame}'
            if self.first_frame == self.last_frame
            else f'frames {self.first_frame}-{self.last_frame}'
        )
        return where if self.first_scene is None else f'{where} (scene {self.first_scene})'


def _frame_number(*, frames: Sequence[Mapping[str, Any]], position: int) -> int:
    number = frames[position].get('frame')
    return number if isinstance(number, int) else position


def frame_spans(
    *, frames: Sequence[Mapping[str, Any]], positions: Sequence[int], gap_frames: int
) -> list[FrameSpan]:
    """Group frames into spans of neighbours.

    Args:
        frames: The recording's decoded frames.
        positions: The frames to group (indexes into ``frames``, ascending).
        gap_frames: How many frame numbers may lie between two frames of one span.

    Returns:
        The spans, in frame order.

    """
    spans: list[FrameSpan] = []
    group: list[int] = []
    for position in positions:
        if group and (
            _frame_number(frames=frames, position=position)
            - _frame_number(frames=frames, position=group[-1])
            - 1
            > gap_frames
        ):
            spans.append(_span_of(frames=frames, group=group))
            group = []
        group.append(position)
    if group:
        spans.append(_span_of(frames=frames, group=group))
    return spans


def _span_of(*, frames: Sequence[Mapping[str, Any]], group: Sequence[int]) -> FrameSpan:
    scene = frames[group[0]].get('scene')
    return FrameSpan(
        first_frame=_frame_number(frames=frames, position=group[0]),
        last_frame=_frame_number(frames=frames, position=group[-1]),
        frame_count=len(group),
        first_scene=scene if isinstance(scene, str) else None,
    )


def _history_entry(*, frame: Mapping[str, Any], field: str, run_index: int) -> object:
    history = frame.get(field)
    if not isinstance(history, list):
        return None
    entries = cast('list[Any]', history)
    return entries[run_index] if run_index < len(entries) else None


def _frame_hash(*, frame: Mapping[str, Any], run_index: int) -> str | None:
    entry = _history_entry(frame=frame, field=CONTENT_HASH_FIELD, run_index=run_index)
    return entry if isinstance(entry, str) else None


def _frame_seconds(*, frame: Mapping[str, Any], run_index: int) -> float | None:
    entry = _history_entry(frame=frame, field=PROCESSING_SECONDS_FIELD, run_index=run_index)
    if isinstance(entry, int | float) and not isinstance(entry, bool):
        return float(entry)
    return None


def _run_count(*, header: Mapping[str, Any], frames: Sequence[Mapping[str, Any]]) -> int:
    """Return how many runs the header or any frame's history holds."""
    depths = [len(recorded_measurement_runs(header=header))]
    for frame in frames:
        for field in (CONTENT_HASH_FIELD, PROCESSING_SECONDS_FIELD):
            history = frame.get(field)
            if isinstance(history, list):
                depths.append(len(cast('list[Any]', history)))
    return max(depths)


def _run_pair_label(
    *, newer_run: int, older_run: int, newer_commit: str | None, older_commit: str | None
) -> str:
    return (
        f'run {older_run} -> run {newer_run} '
        f'({older_commit or UNKNOWN_COMMIT} -> {newer_commit or UNKNOWN_COMMIT})'
    )


def _commits(*, header: Mapping[str, Any], count: int) -> list[str | None]:
    runs = recorded_measurement_runs(header=header)
    return [short_commit(run=runs[index] if index < len(runs) else None) for index in range(count)]


class BehaviourChange(BaseModel):
    """Where two adjacent runs of a recording did different things (their hashes differ).

    Attributes:
        newer_run: The newer run's index.
        older_run: The older run's index (``newer_run + 1``).
        newer_commit: The newer run's commit, abbreviated, or None when unknown.
        older_commit: The older run's commit, abbreviated, or None when unknown.
        frames_compared: Frames with a hash for both runs.
        frames_changed: Those whose hashes differ.
        frames_unknown: Frames without a hash for either run.
        spans: The changed frames, grouped into spans of consecutive frames.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    newer_run: int
    older_run: int
    newer_commit: str | None
    older_commit: str | None
    frames_compared: int
    frames_changed: int
    frames_unknown: int
    spans: tuple[FrameSpan, ...]

    def describe(self: Self) -> str:
        """Describe the change on one line.

        Returns:
            ``run 1 -> run 0 (abc1234 -> def5678): behaviour changed in frames 812-940 (scene
            Game), 3 spans, 140 frames``, or ``...: no behaviour change in N frames``.

        """
        pair = _run_pair_label(
            newer_run=self.newer_run,
            older_run=self.older_run,
            newer_commit=self.newer_commit,
            older_commit=self.older_commit,
        )
        if not self.spans:
            return f'{pair}: no behaviour change in {_plural(self.frames_compared, "frame")}'
        return (
            f'{pair}: behaviour changed in {self.spans[0].describe()}, '
            f'{_plural(len(self.spans), "span")}, {_plural(self.frames_changed, "frame")}'
        )


def behaviour_changes(
    *, header: Mapping[str, Any], frames: Sequence[Mapping[str, Any]]
) -> list[BehaviourChange]:
    """Return the behaviour-change map: for each adjacent pair of runs, the frames that changed.

    Args:
        header: The recording's header fields (the runs' commits).
        frames: Its decoded frames (their ``content_hash`` histories).

    Returns:
        One entry per adjacent pair, newest pair (run 0 against run 1) first.

    """
    run_count = _run_count(header=header, frames=frames)
    commits = _commits(header=header, count=run_count)
    changes: list[BehaviourChange] = []
    for newer_run in range(run_count - 1):
        older_run = newer_run + 1
        changed: list[int] = []
        compared = 0
        for position, frame in enumerate(frames):
            newer_hash = _frame_hash(frame=frame, run_index=newer_run)
            older_hash = _frame_hash(frame=frame, run_index=older_run)
            if newer_hash is None or older_hash is None:
                continue
            compared += 1
            if newer_hash != older_hash:
                changed.append(position)
        changes.append(
            BehaviourChange(
                newer_run=newer_run,
                older_run=older_run,
                newer_commit=commits[newer_run],
                older_commit=commits[older_run],
                frames_compared=compared,
                frames_changed=len(changed),
                frames_unknown=len(frames) - compared,
                spans=tuple(frame_spans(frames=frames, positions=changed, gap_frames=0)),
            )
        )
    return changes


class SpeedChange(StrEnum):
    """Which way a span's processing time moved."""

    SLOWER = 'slower'
    FASTER = 'faster'


class ProcessingSpan(BaseModel):
    """A span of same-work frames that got slower or faster between two runs.

    Attributes:
        direction: Slower or faster.
        span: The frames.
        older_seconds: Their total processing time in the older run.
        newer_seconds: Their total in the newer run.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    direction: SpeedChange
    span: FrameSpan
    older_seconds: float
    newer_seconds: float

    def describe(self: Self) -> str:
        """Describe the span.

        Returns:
            ``frames 10-40 (scene Game): slower, 1.200 ms -> 2.000 ms (+66.7%)``.

        """
        return (
            f'{self.span.describe()}: {self.direction}, {_milliseconds(self.older_seconds)} -> '
            f'{_milliseconds(self.newer_seconds)} '
            f'({_change_percent(older=self.older_seconds, newer=self.newer_seconds)})'
        )


class ProcessingComparison(BaseModel):
    """How two adjacent runs' processing times compare, over the frames that did the same work.

    Attributes:
        newer_run: The newer run's index.
        older_run: The older run's index.
        newer_commit: The newer run's commit, abbreviated, or None.
        older_commit: The older run's commit, abbreviated, or None.
        frames_same_work: Frames with equal hashes and a time in both runs.
        frames_different_work: Frames whose hashes differ.
        frames_unmeasured: Frames with equal hashes but a time missing in either run, or
            without a hash for either run.
        older_seconds: The same-work frames' total time in the older run.
        newer_seconds: Their total in the newer run.
        frames_slower: Same-work frames that got slower.
        frames_faster: Same-work frames that got faster.
        spans: The listed spans (at least ``MINIMUM_SPAN_FRAMES`` frames), in frame order.
        short_spans: Spans too short to list.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    newer_run: int
    older_run: int
    newer_commit: str | None
    older_commit: str | None
    frames_same_work: int
    frames_different_work: int
    frames_unmeasured: int
    older_seconds: float
    newer_seconds: float
    frames_slower: int
    frames_faster: int
    spans: tuple[ProcessingSpan, ...]
    short_spans: int

    def describe(self: Self) -> str:
        """Describe the comparison on one line.

        Returns:
            ``run 1 -> run 0 (abc1234 -> def5678): 600 frames of the same work took 50.000 ms
            -> 48.000 ms (-4.0%); 3 slower, 2 faster`` then the short spans, the different work
            and the unmeasured frames when there are any.

        """
        pair = _run_pair_label(
            newer_run=self.newer_run,
            older_run=self.older_run,
            newer_commit=self.newer_commit,
            older_commit=self.older_commit,
        )
        if self.frames_same_work == 0:
            parts = [f'{pair}: no frames of the same work']
        else:
            speeds = f'{self.frames_slower} slower, {self.frames_faster} faster'
            if self.short_spans:
                speeds = f'{speeds} ({_plural(self.short_spans, "span")} too short to list)'
            parts = [
                (
                    f'{pair}: {_plural(self.frames_same_work, "frame")} of the same work took '
                    f'{_milliseconds(self.older_seconds)} -> {_milliseconds(self.newer_seconds)} '
                    f'({_change_percent(older=self.older_seconds, newer=self.newer_seconds)})'
                ),
                speeds,
            ]
        if self.frames_different_work:
            parts.append(f'{_plural(self.frames_different_work, "frame")} different work')
        if self.frames_unmeasured:
            parts.append(f'{_plural(self.frames_unmeasured, "frame")} unmeasured')
        return '; '.join(parts)


def _speed_spans(
    *,
    frames: Sequence[Mapping[str, Any]],
    positions: Sequence[int],
    direction: SpeedChange,
    times: Mapping[int, tuple[float, float]],
) -> tuple[list[ProcessingSpan], int]:
    listed: list[ProcessingSpan] = []
    short = 0
    for span in frame_spans(frames=frames, positions=positions, gap_frames=SPAN_GAP_FRAMES):
        if span.frame_count < MINIMUM_SPAN_FRAMES:
            short += 1
            continue
        members = [
            position
            for position in positions
            if span.first_frame
            <= _frame_number(frames=frames, position=position)
            <= span.last_frame
        ]
        listed.append(
            ProcessingSpan(
                direction=direction,
                span=span,
                older_seconds=math.fsum(times[position][0] for position in members),
                newer_seconds=math.fsum(times[position][1] for position in members),
            )
        )
    return listed, short


def _same_work_times(
    *, frames: Sequence[Mapping[str, Any]], newer_run: int, older_run: int
) -> tuple[dict[int, tuple[float, float]], int]:
    """Return the same-work frames' times (older, newer) by position, and the different work.

    Args:
        frames: The recording's decoded frames.
        newer_run: The newer run's index.
        older_run: The older run's index.

    Returns:
        The times of frames with equal hashes and a time in both runs, in frame order, and how
        many frames' hashes differ.

    """
    times: dict[int, tuple[float, float]] = {}
    different_work = 0
    for position, frame in enumerate(frames):
        newer_hash = _frame_hash(frame=frame, run_index=newer_run)
        older_hash = _frame_hash(frame=frame, run_index=older_run)
        if newer_hash is None or older_hash is None:
            continue
        if newer_hash != older_hash:
            different_work += 1
            continue
        newer_seconds = _frame_seconds(frame=frame, run_index=newer_run)
        older_seconds = _frame_seconds(frame=frame, run_index=older_run)
        if newer_seconds is not None and older_seconds is not None:
            times[position] = (older_seconds, newer_seconds)
    return times, different_work


def _first_frame_of(processing_span: ProcessingSpan) -> int:
    return processing_span.span.first_frame


def processing_comparisons(
    *,
    header: Mapping[str, Any],
    frames: Sequence[Mapping[str, Any]],
    speed_change_ratio: float = DEFAULT_SPEED_CHANGE_RATIO,
    minimum_change_seconds: float = DEFAULT_MINIMUM_CHANGE_SECONDS,
) -> list[ProcessingComparison]:
    """Compare each adjacent pair of runs' processing times over their same-work frames.

    Args:
        header: The recording's header fields (the runs' commits).
        frames: Its decoded frames (``content_hash`` and ``processing_seconds`` histories).
        speed_change_ratio: How much a frame's time must change, as a fraction of the older
            time, to count as slower or faster.
        minimum_change_seconds: How much it must change in seconds too.

    Returns:
        One entry per adjacent pair, newest pair first.

    """
    run_count = _run_count(header=header, frames=frames)
    commits = _commits(header=header, count=run_count)
    comparisons: list[ProcessingComparison] = []
    for newer_run in range(run_count - 1):
        older_run = newer_run + 1
        times, different_work = _same_work_times(
            frames=frames, newer_run=newer_run, older_run=older_run
        )
        slower: list[int] = []
        faster: list[int] = []
        for position, (older_seconds, newer_seconds) in times.items():
            change = newer_seconds - older_seconds
            if abs(change) <= minimum_change_seconds or abs(change) <= (
                older_seconds * speed_change_ratio
            ):
                continue
            (slower if change > 0 else faster).append(position)
        slower_spans, short_slower = _speed_spans(
            frames=frames, positions=slower, direction=SpeedChange.SLOWER, times=times
        )
        faster_spans, short_faster = _speed_spans(
            frames=frames, positions=faster, direction=SpeedChange.FASTER, times=times
        )
        comparisons.append(
            ProcessingComparison(
                newer_run=newer_run,
                older_run=older_run,
                newer_commit=commits[newer_run],
                older_commit=commits[older_run],
                frames_same_work=len(times),
                frames_different_work=different_work,
                frames_unmeasured=len(frames) - len(times) - different_work,
                older_seconds=math.fsum(older for older, _ in times.values()),
                newer_seconds=math.fsum(newer for _, newer in times.values()),
                frames_slower=len(slower),
                frames_faster=len(faster),
                spans=tuple(sorted([*slower_spans, *faster_spans], key=_first_frame_of)),
                short_spans=short_slower + short_faster,
            )
        )
    return comparisons


# How many buckets a run's per-frame profile has (a shorter recording keeps one per frame)
PROFILE_BUCKET_COUNT = 100
MICROSECONDS_PER_SECOND = 1_000_000


class FrameProfile(BaseModel):
    """A run's processing times across its recording, bucketed: compact enough for every row.

    The frames are cut into ``len(max_microseconds)`` buckets of consecutive frames (positions in
    the recording; ``bucket_frames``), and each bucket keeps its slowest frame's time. About 100
    small integers: a few hundred bytes of JSON.

    Attributes:
        frame_count: How many frames the run's recording holds.
        max_microseconds: Each bucket's slowest processing time, in whole microseconds, or None
            when no frame of the bucket was timed.
        scene_runs: ``(bucket, scene)`` wherever a bucket's first frame names another scene than
            the bucket before (the first entry is bucket 0): the scenes, run-length encoded.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    frame_count: int
    max_microseconds: tuple[int | None, ...]
    scene_runs: tuple[tuple[int, str | None], ...]

    def bucket_frames(self: Self, *, bucket: int) -> tuple[int, int]:
        """Return a bucket's first and last frame position.

        Returns:
            The positions, inclusive.

        """
        return _bucket_bounds(
            bucket=bucket, frame_count=self.frame_count, bucket_count=len(self.max_microseconds)
        )

    def bucket_scene(self: Self, *, bucket: int) -> str | None:
        """Return the scene of a bucket's first frame.

        Returns:
            The scene, or None when the frame names none.

        """
        scene: str | None = None
        for first_bucket, run_scene in self.scene_runs:
            if first_bucket > bucket:
                break
            scene = run_scene
        return scene


def _bucket_bounds(*, bucket: int, frame_count: int, bucket_count: int) -> tuple[int, int]:
    return (bucket * frame_count // bucket_count, (bucket + 1) * frame_count // bucket_count - 1)


def frame_profile(
    *,
    frames: Sequence[Mapping[str, Any]],
    run_index: int,
    bucket_count: int = PROFILE_BUCKET_COUNT,
) -> FrameProfile | None:
    """Bucket one run's per-frame processing times (``FrameProfile``).

    Args:
        frames: The recording's decoded frames.
        run_index: The run's index in their histories.
        bucket_count: How many buckets (fewer when the recording has fewer frames).

    Returns:
        The profile, or None when no frame holds a time for the run.

    """
    buckets = min(bucket_count, len(frames))
    maxima: list[int | None] = []
    scene_runs: list[tuple[int, str | None]] = []
    for bucket in range(buckets):
        first, last = _bucket_bounds(bucket=bucket, frame_count=len(frames), bucket_count=buckets)
        times = [
            seconds
            for frame in frames[first : last + 1]
            if (seconds := _frame_seconds(frame=frame, run_index=run_index)) is not None
        ]
        maxima.append(round(max(times) * MICROSECONDS_PER_SECOND) if times else None)
        scene = frames[first].get('scene')
        scene_name = scene if isinstance(scene, str) else None
        if not scene_runs or scene_runs[-1][1] != scene_name:
            scene_runs.append((bucket, scene_name))
    if all(maximum is None for maximum in maxima):
        return None
    return FrameProfile(
        frame_count=len(frames), max_microseconds=tuple(maxima), scene_runs=tuple(scene_runs)
    )


class LedgerOrigin(StrEnum):
    """Where a ledger row's run came from."""

    # Measured by nox -s replay-metrics (a rebaseline on this machine)
    REPLAY_METRICS = 'replay-metrics'
    # A run the recording itself held (its live recording, or an earlier rebaseline)
    RECORDING = 'recording'


class LedgerRow(BaseModel):
    """One run of one recording, as the run ledger keeps it.

    Attributes:
        recording: The recording's path, relative to the repository.
        console_script: The game's console script, which replays it.
        origin: Where the run came from.
        run: The run's provenance.
        summary: Its processing times at a glance, or None when it measured none.
        content_hash: The recording's content hash for the run, or None when a frame lacks one.
        frame_count: How many frames the run wrote, or None when unknown.
        frames_changed: Frames whose content hash the run changed against the run before it
            (a rebaseline's: against the recording's newest run), or None when not compared.
        rebaseline_exit: The rebaseline's exit (``ExitCode.describe``) for a measured run;
            None for a run the recording held.
        allowed_uncommitted_changes: Whether the measurement was allowed on a checkout with
            uncommitted changes (``--allow-dirty``).
        profile: The run's per-frame times, bucketed (``FrameProfile``), for a measured run;
            None for a run the recording held and rows from before profiles.
        code_tree: The code the run measured, as a git tree of what can change the replays
            (glitchygames/code_tree.py), for a run the measuring pre-commit hook made; None for
            every other row (it names its code by commit instead).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    recording: str
    console_script: str
    origin: LedgerOrigin
    run: MeasurementRun
    summary: RunSummary | None
    content_hash: str | None
    frame_count: int | None
    frames_changed: int | None
    rebaseline_exit: str | None
    allowed_uncommitted_changes: bool
    profile: FrameProfile | None = None
    code_tree: str | None = None

    @property
    def from_uncommitted_changes(self: Self) -> bool:
        """Whether the row measured other code than its commit: a trial or a changed checkout.

        A row naming its code tree measured exactly that code (the pre-commit hook measures
        the staged code, uncommitted by definition), so it never counts.
        """
        if self.code_tree is not None:
            return False
        return self.allowed_uncommitted_changes or self.measured_uncommitted_changes

    @property
    def key(self: Self) -> str:
        """The row's identity: the recording, when the run measured and on which machine."""
        return f'{self.recording}|{self.run.measured_at}|{self.run.machine}'

    @property
    def commit(self: Self) -> str | None:
        """The run's full commit, or None when unknown."""
        revision = self.run.source_revision
        return None if revision is None else revision.commit

    @property
    def measured_uncommitted_changes(self: Self) -> bool:
        """Whether the run's checkout had uncommitted changes (unknown counts as none)."""
        revision = self.run.source_revision
        return revision is not None and bool(revision.uncommitted_changes)

    @property
    def machine(self: Self) -> str:
        """The run's machine label (``machine_label``)."""
        return machine_label(run=self.run)


class LedgerParse(BaseModel):
    """A ledger's text, read.

    Attributes:
        rows: The readable rows, in file order.
        unreadable_lines: Non-blank lines that were not a readable row (skipped).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    rows: tuple[LedgerRow, ...]
    unreadable_lines: int


def parse_ledger(*, text: str) -> LedgerParse:
    """Read a ledger's JSON Lines leniently: an unreadable line is skipped and counted.

    Args:
        text: The ledger's text.

    Returns:
        Its rows.

    """
    rows: list[LedgerRow] = []
    unreadable = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rows.append(LedgerRow.model_validate(json.loads(line)))
        # Not JSON (json.JSONDecodeError) or not a row (pydantic's ValidationError): both are
        # ValueErrors
        except ValueError:
            unreadable += 1
    return LedgerParse(rows=tuple(rows), unreadable_lines=unreadable)


# Row files: how many of a code tree's characters lead a row file's name
ROW_FILE_TREE_CHARACTERS = 12
# The name part of a row file for a row without a code tree (published history)
ROW_FILE_HISTORY_PREFIX = 'history'
ROW_FILE_SUFFIX = '.json'


def _file_name_part(text: str) -> str:
    """Return ``text`` as a file-name part: letters and digits, runs of anything else as ``-``.

    Returns:
        The part, lower case.

    """
    return re.sub(r'[^A-Za-z0-9]+', '-', text).strip('-').lower()


def row_file_name(*, row: LedgerRow) -> str:
    """Return the file a row is kept in (quality/replay-ledger/): unique per row, never reused.

    ``<code tree, 12>-<machine>-<measured at>-<recording>.json``: the code tree leads, so one
    measured code's rows sort together (``history`` for a row without one).

    Returns:
        The file name.

    """
    tree = (
        ROW_FILE_HISTORY_PREFIX
        if row.code_tree is None
        else row.code_tree[:ROW_FILE_TREE_CHARACTERS]
    )
    recording = _file_name_part(row.recording.removesuffix('.jsonl.gz'))
    measured_at = re.sub(r'[^0-9]', '', row.run.measured_at)
    return f'{tree}-{_file_name_part(row.machine)}-{measured_at}-{recording}{ROW_FILE_SUFFIX}'


def write_row_files(*, rows: Iterable[LedgerRow], directory: Path) -> list[Path]:
    """Write each row to its own file in ``directory`` (made if missing), in the ledger's format.

    Returns:
        The files written.

    """
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for row in rows:
        path = directory / row_file_name(row=row)
        path.write_text(ledger_text(rows=[row]), encoding='utf-8')
        paths.append(path)
    return paths


def read_row_files(*, directory: Path) -> list[LedgerRow]:
    """Read every row file in ``directory``, in file-name order (none when it is missing).

    Returns:
        The rows; an unreadable file is skipped as ``parse_ledger`` skips a line.

    """
    if not directory.is_dir():
        return []
    rows: list[LedgerRow] = []
    for path in sorted(directory.glob(f'*{ROW_FILE_SUFFIX}')):
        rows.extend(parse_ledger(text=path.read_text(encoding='utf-8')).rows)
    return rows


def landed_rows(
    *, rows: Iterable[LedgerRow], landed: Mapping[str, LandedCommit], keep_unlanded: bool
) -> list[LedgerRow]:
    """Return the rows whose measured code landed, each labelled with the commit it landed in.

    A row naming a code tree that landed (``code_tree.landed_code_trees``) takes that commit
    and its date, as committed code. A row naming one that did not (an intermediate commit's, a
    branch's that never merged or was behind main) is left out, unless ``keep_unlanded`` (a
    local build, showing a branch's rows before it merges). A row naming no code tree (the
    history measured by commit) passes through.

    Args:
        rows: The rows.
        landed: Code tree -> the commit it landed in.
        keep_unlanded: Keep the rows whose code did not land, unchanged.

    Returns:
        The rows, in their order.

    """
    kept: list[LedgerRow] = []
    for row in rows:
        if row.code_tree is None:
            kept.append(row)
            continue
        landing = landed.get(row.code_tree)
        if landing is None:
            if keep_unlanded:
                kept.append(row)
            continue
        revision = row.run.source_revision
        landed_revision = (
            SourceRevision(source=RevisionSource.GIT_CHECKOUT) if revision is None else revision
        ).model_copy(
            update={
                'commit': landing.commit,
                'committed_at': landing.committed_at,
                'uncommitted_changes': False,
            }
        )
        kept.append(
            row.model_copy(
                update={'run': row.run.model_copy(update={'source_revision': landed_revision})}
            )
        )
    return kept


def ledger_text(*, rows: Iterable[LedgerRow]) -> str:
    """Write rows as the ledger's JSON Lines (one compact, key-sorted object per line).

    Args:
        rows: The rows, in the order to write.

    Returns:
        The text (empty for no rows).

    """
    return ''.join(
        json.dumps(row.model_dump(mode='json'), sort_keys=True, separators=(',', ':')) + '\n'
        for row in rows
    )


def _instant(text: str | None) -> datetime:
    """Return an ISO 8601 time as an aware instant (the earliest one when unreadable)."""
    earliest = datetime.min.replace(tzinfo=UTC)
    if text is None:
        return earliest
    try:
        instant = datetime.fromisoformat(text)
    except ValueError:
        return earliest
    return instant if instant.tzinfo is not None else instant.replace(tzinfo=UTC)


def _row_order(row: LedgerRow) -> tuple[datetime, datetime]:
    revision = row.run.source_revision
    return (
        _instant(None if revision is None else revision.committed_at),
        _instant(row.run.measured_at),
    )


def merge_ledgers(*, ledgers: Iterable[Iterable[LedgerRow]]) -> list[LedgerRow]:
    """Merge ledgers: the first row of each key wins; ordered by commit date, then measurement.

    Args:
        ledgers: The ledgers, the most trusted first (the published one before pending rows).

    Returns:
        The merged rows (rows without a commit date first).

    """
    merged: dict[str, LedgerRow] = {}
    for rows in ledgers:
        for row in rows:
            merged.setdefault(row.key, row)
    return sorted(merged.values(), key=_row_order)


def published_ledger_text(*, project_root: Path, ref: str = PUBLISHED_LEDGER_REF) -> str:
    """Return the ledger published on gh-pages, as the local ``ref`` holds it.

    Args:
        project_root: The repository.
        ref: The published branch's local ref (fetched by docs-deploy; never fetched here).

    Returns:
        The ledger's text; empty when git, the ref or the file is missing.

    """
    try:
        completed = run_command(
            command=['git', 'show', f'{ref}:{PUBLISHED_LEDGER_PATH}'],
            environment=os.environ,
            timeout_seconds=GIT_TIMEOUT_SECONDS,
            capture_output=True,
            working_directory=project_root,
        )
    except OSError, TimeoutExpired:
        return ''
    return (completed.stdout or '') if completed.returncode == 0 else ''


def read_ledger_file(*, path: Path) -> LedgerParse:
    """Read a ledger file (a missing one is empty).

    Args:
        path: The ledger file.

    Returns:
        Its rows.

    """
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    return parse_ledger(text=text)


def publishable_rows(*, rows: Iterable[LedgerRow]) -> list[LedgerRow]:
    """Return the rows a published site may hold: none measured other code than its commit.

    Args:
        rows: The ledger's rows.

    Returns:
        The rows without ``from_uncommitted_changes``, in order.

    """
    return [row for row in rows if not row.from_uncommitted_changes]


def is_measured(*, rows: Iterable[LedgerRow], recording: str, commit: str, machine: str) -> bool:
    """Tell whether replay-metrics already measured a recording at a commit on a machine.

    Args:
        rows: The ledger's rows (published and pending).
        recording: The recording's repository-relative path.
        commit: The full commit.
        machine: The machine label (``machine_label``).

    Returns:
        True when a ``LedgerOrigin.REPLAY_METRICS`` row matches all three and was not a trial
        allowed on uncommitted changes (``allowed_uncommitted_changes``: it measured other code
        than its commit, so it never stands for the commit).

    """
    return any(
        row.origin == LedgerOrigin.REPLAY_METRICS
        and not row.allowed_uncommitted_changes
        and row.recording == recording
        and row.commit == commit
        and row.machine == machine
        for row in rows
    )


def ledger_rows_from_rebaseline(
    *,
    recording: str,
    console_script: str,
    trace: Mapping[str, Any],
    rebaseline_exit: str,
    allowed_uncommitted_changes: bool,
) -> list[LedgerRow]:
    """Return the ledger rows of a rebaselined recording: its newest run, then each it held.

    Args:
        recording: The original recording's repository-relative path.
        console_script: The game's console script.
        trace: The rebaselined recording, read (its header fields plus ``frames``).
        rebaseline_exit: How the rebaseline exited (``ExitCode.describe``).
        allowed_uncommitted_changes: Whether the measurement ran with ``--allow-dirty``.

    Returns:
        One row per readable run, newest first: run 0 is ``LedgerOrigin.REPLAY_METRICS``, the
        others ``LedgerOrigin.RECORDING``.

    """
    frames: Sequence[Mapping[str, Any]] = trace[FRAMES_FIELD]
    summaries = recording_run_summaries(header=trace, frames=frames)
    changes = behaviour_changes(header=trace, frames=frames)
    rows: list[LedgerRow] = []
    for run_index, run in enumerate(recorded_measurement_runs(header=trace)):
        if run is None:
            continue
        measured = run_index == 0
        rows.append(
            LedgerRow(
                recording=recording,
                console_script=console_script,
                origin=LedgerOrigin.REPLAY_METRICS if measured else LedgerOrigin.RECORDING,
                run=run,
                summary=summaries[run_index],
                content_hash=recording_content_hash(frames=frames, run_index=run_index),
                frame_count=len(frames) if measured else run.frame_count,
                frames_changed=changes[0].frames_changed if measured and changes else None,
                rebaseline_exit=rebaseline_exit if measured else None,
                allowed_uncommitted_changes=allowed_uncommitted_changes and measured,
                profile=frame_profile(frames=frames, run_index=run_index) if measured else None,
            )
        )
    return rows


class PerformanceSeries(BaseModel):
    """One graph line's rows: a recording on one machine, paced or not, in commit order.

    Processing times compare only on one machine, and paced frames process slower than
    unpaced ones, so each (recording, machine, pacing) is its own series.

    Attributes:
        recording: The recording's repository-relative path.
        console_script: Its game's console script.
        machine: The machine label.
        paced: Whether the runs paced their frames (live recordings) or not (replays).
        rows: The latest row of each commit, oldest commit first.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    recording: str
    console_script: str
    machine: str
    paced: bool
    rows: tuple[LedgerRow, ...]

    @property
    def label(self: Self) -> str:
        """The series' legend label: the machine and the kind of run."""
        kind = 'paced live run' if self.paced else 'unpaced replay'
        return f'{self.machine}, {kind}'


def performance_series(*, rows: Iterable[LedgerRow]) -> list[PerformanceSeries]:
    """Group ledger rows into graph series (rows without a commit or summary are left out).

    A recording that moved (``RECORDING_PATH_RENAMES``) is one series under its new path.

    Args:
        rows: The ledger's rows.

    Returns:
        The series, by recording, machine and pacing.

    """
    grouped: dict[tuple[str, str, bool], dict[str, LedgerRow]] = {}
    console_scripts: dict[str, str] = {}
    for row in sorted(rows, key=_row_order):
        if row.commit is None or row.summary is None:
            continue
        # A moved recording's rows from before the move join its series under the new path
        recording = RECORDING_PATH_RENAMES.get(row.recording, row.recording)
        series_key = (recording, row.machine, row.run.processing_paced)
        # Sorted by measurement within a commit, so the latest measurement of a commit wins
        grouped.setdefault(series_key, {})[row.commit] = row
        console_scripts[recording] = row.console_script
    return [
        PerformanceSeries(
            recording=recording,
            console_script=console_scripts[recording],
            machine=machine,
            paced=paced,
            rows=tuple(sorted(by_commit.values(), key=_row_order)),
        )
        for (recording, machine, paced), by_commit in sorted(grouped.items())
    ]
