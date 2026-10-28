"""Content hashes and measurement history of recorded frames (a leaf: no engine imports).

Design: plans/2026-10-20-recording-content-hash-and-history.md. Each frame a recorder writes
carries two newest-first history lists, and the header a third:

- ``content_hash``: the frame's content hash (``frame_content_hash``): SHA-256 of its content
  fields, as a JSON reader decodes them (string keys, lists), encoded as compact, key-sorted
  JSON, cut to 64 bits (16 hex digits). So the hash a recorder stores is the hash a reader
  recomputes from the decoded frame. Content is everything the
  game did or took in (``FrameContent``); measurements are left out
  (``MEASUREMENT_FRAME_FIELDS``). Replays and rebaselines of one recording reproduce it, unless
  the game's behaviour changed.
- ``processing_seconds``: the frame's processing time (glitchygames/replay/processing.py),
  rounded to the microsecond; None when it was not measured.
- ``measurement_runs`` (header): each run's provenance (``MeasurementRun``: machine, pacing and
  its timer, versions, when it measured, what it was rebaselined from, the hash scheme).

A hash entry deeper than ``measurement_runs`` reaches (when ``MEASUREMENT_RUNS_HISTORY_DEPTH``
is tuned below ``CONTENT_HASH_HISTORY_DEPTH``) has no ``hash_scheme`` to consult: tools must
treat its scheme as unknown, never assume ``CONTENT_HASH_SCHEME``. Index ``i`` means run ``i``
in every list: a run inserts exactly one entry at ``[0]`` of every
list of every frame it writes (``stacked_history``), and lists are only cut from the tail, at
each list's own depth constant. A recording's hash for run ``i`` is derived from its frames'
``content_hash[i]`` (``recording_content_hash``); it is not stored. ``CONTENT_HASH_SCHEME``
names the hash's definition: a later definition is a new scheme, so old entries are known to be
incomparable rather than changed.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import TYPE_CHECKING, Any, Self, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from glitchygames.build_info import (
    SourceRevision,  # ruff: ignore[typing-only-first-party-import] - pydantic resolves MeasurementRun.source_revision at runtime
)
from glitchygames.machine_state import (
    MachineState,  # ruff: ignore[typing-only-first-party-import] - pydantic resolves MeasurementRun.machine_state at runtime
)
from glitchygames.timing import (
    PacingTimer,  # ruff: ignore[typing-only-first-party-import] - pydantic resolves MeasurementRun.pacing_timer at runtime
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

# Frame fields that hold histories, and the header field of the runs' provenance
PROCESSING_SECONDS_FIELD = 'processing_seconds'
CONTENT_HASH_FIELD = 'content_hash'
MEASUREMENT_RUNS_HEADER_FIELD = 'measurement_runs'

# How many runs each history keeps (newest first; read at call time, so tests can tune them)
PROCESSING_SECONDS_HISTORY_DEPTH = 10
CONTENT_HASH_HISTORY_DEPTH = 10
MEASUREMENT_RUNS_HISTORY_DEPTH = 10

# The hash's definition: SHA-256 of the content fields as JSON decodes them, encoded as compact,
# key-sorted JSON, 64 bits
CONTENT_HASH_SCHEME = 1
CONTENT_HASH_HEX_DIGITS = 16
# Processing times are kept to the microsecond: finer is noise, and every digit costs file size
PROCESSING_SECONDS_DIGITS = 6

# Frame fields that are measurements: never hashed
MEASUREMENT_FRAME_FIELDS: frozenset[str] = frozenset({PROCESSING_SECONDS_FIELD, CONTENT_HASH_FIELD})


class UnclassifiedFrameFieldError(ValueError):
    """A frame holds a field that is neither content (``FrameContent``) nor a measurement."""


class FrameContent(BaseModel):
    """The content fields of a recorded frame: everything the hash covers.

    A field a recorder writes must be declared here or in ``MEASUREMENT_FRAME_FIELDS``;
    ``frame_content_hash`` refuses any other, so a new field cannot be left out of (or slip into)
    the hash unnoticed. The types are loose (the trace format's own readers validate the values);
    the model is the classification.

    Attributes:
        frame: The frame's index.
        dt: Its raw delta time.
        event_batches: Its pumped event batches.
        scene: The active scene's class name, or None.
        sprites: The sampled sprites, in draw order.
        input_changes: Its polled-input changes.
        control_events: Its control events.
        devices_opened: Devices opened in it.
        saves_opened: Save namespaces first opened in it.
        device_enumeration: Enumeration answers given in it.
        scene_start: The start of a scene that began in it.
        redelivered_events: Events a playback scope held and delivered before its first pump.
        resume_bridge: What a scene resumed with (the instant-replay journal only).
        playback_answers: What playback requests got (the instant-replay journal only).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    frame: int
    dt: float | None = None
    event_batches: list[Any] | None = None
    scene: str | None = None
    sprites: list[Any] | None = None
    input_changes: dict[str, Any] | None = None
    control_events: list[Any] | None = None
    devices_opened: list[Any] | None = None
    saves_opened: dict[str, Any] | None = None
    device_enumeration: list[Any] | None = None
    scene_start: dict[str, Any] | None = None
    redelivered_events: list[Any] | None = None
    resume_bridge: dict[str, Any] | None = None
    playback_answers: list[Any] | None = None


def frame_content_hash(*, frame_record: Mapping[str, Any]) -> str:
    """Return a frame's content hash (scheme ``CONTENT_HASH_SCHEME``).

    Args:
        frame_record: The frame, as a recorder writes it or a reader decodes it (measurement
            fields are ignored).

    Returns:
        The first 16 hex digits of the SHA-256 of its content, as a JSON reader decodes it
        (string keys, lists), encoded as compact, key-sorted JSON.

    Raises:
        UnclassifiedFrameFieldError: If the frame holds a field that is neither content nor a
            measurement.

    """
    content = {
        name: value for name, value in frame_record.items() if name not in MEASUREMENT_FRAME_FIELDS
    }
    unclassified = sorted(set(content) - set(FrameContent.model_fields))
    if unclassified:
        message = (
            f'Frame fields {unclassified} are neither content nor measurements: classify them '
            'in glitchygames/recording_history.py'
        )
        raise UnclassifiedFrameFieldError(message)
    # The content as a reader decodes it: JSON makes every key a string (and every tuple a
    # list), so int keys sort as the strings a reader gets, and mixed key types sort at all
    as_read = json.loads(json.dumps(content, separators=(',', ':')))
    encoded = json.dumps(as_read, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()[:CONTENT_HASH_HEX_DIGITS]


def recording_content_hash(
    *, frames: Iterable[Mapping[str, Any]], run_index: int = 0
) -> str | None:
    """Return a recording's hash for one run: the hash of its frames' hashes, in frame order.

    Args:
        frames: The recording's frames.
        run_index: Which run (0: the newest).

    Returns:
        The first 16 hex digits of the SHA-256 of each frame's ``content_hash[run_index]`` and a
        newline, or None when a frame has no hash for that run.

    """
    digest = hashlib.sha256()
    for frame in frames:
        recorded = frame.get(CONTENT_HASH_FIELD)
        if not isinstance(recorded, list):
            return None
        history = cast('list[Any]', recorded)
        if run_index >= len(history):
            return None
        frame_hash = history[run_index]
        if not isinstance(frame_hash, str):
            return None
        digest.update(f'{frame_hash}\n'.encode('ascii'))
    return digest.hexdigest()[:CONTENT_HASH_HEX_DIGITS]


def stacked_history(*, newest: object, previous: object, depth: int) -> list[Any]:
    """Return a history with ``newest`` in front of ``previous``, cut to ``depth`` from the tail.

    Args:
        newest: This run's value (None when it was not measured: it keeps its place).
        previous: The earlier history (anything but a list counts as none).
        depth: How many entries to keep (at least 1).

    Returns:
        The new history, newest first.

    """
    earlier = cast('list[Any]', previous) if isinstance(previous, list) else []
    return [newest, *earlier][:depth]


def add_frame_histories(
    *,
    frame_record: dict[str, Any],
    processing_seconds: float | None,
    previous_histories: Mapping[str, Any] | None,
) -> None:
    """Add this run's content hash and processing time to a frame record, in front of its past.

    Args:
        frame_record: The frame about to be written (gets ``content_hash`` and
            ``processing_seconds``).
        processing_seconds: This run's processing time for it, or None when not measured.
        previous_histories: The frame's earlier histories (a rebaseline's: the replayed frame's
            ``content_hash`` and ``processing_seconds``), or None.

    """
    previous = previous_histories or {}
    content_hash = frame_content_hash(frame_record=frame_record)
    frame_record[CONTENT_HASH_FIELD] = stacked_history(
        newest=content_hash,
        previous=previous.get(CONTENT_HASH_FIELD),
        depth=CONTENT_HASH_HISTORY_DEPTH,
    )
    frame_record[PROCESSING_SECONDS_FIELD] = stacked_history(
        newest=None
        if processing_seconds is None
        else round(processing_seconds, PROCESSING_SECONDS_DIGITS),
        previous=previous.get(PROCESSING_SECONDS_FIELD),
        depth=PROCESSING_SECONDS_HISTORY_DEPTH,
    )


# A frame took longer than its budget times this to count as late (a missed frame at 60 FPS)
LATE_FRAME_BUDGET_FACTOR = 1.5
RUN_SUMMARY_FIELD = 'summary'


class FrameTimeSummary(BaseModel):
    """How steady a live run's frame times (its frames' recorded ``dt``) were.

    Only the run that recorded the frames live measured them: a rebaseline replays the recorded
    ``dt``, so its runs have none.

    Attributes:
        p50_seconds: The median frame time.
        p99_seconds: The 99th percentile frame time.
        max_seconds: The longest frame.
        late_frames: Frames longer than ``LATE_FRAME_BUDGET_FACTOR`` budgets, or None without a
            budget (an uncapped run).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    p50_seconds: float
    p99_seconds: float
    max_seconds: float
    late_frames: int | None


class RunSummary(BaseModel):
    """One run's processing times at a glance, so tools need not read every frame.

    Attributes:
        measured_frames: Frames with a processing time for this run.
        total_processing_seconds: Their sum.
        p50_processing_seconds: The median.
        p95_processing_seconds: The 95th percentile.
        p99_processing_seconds: The 99th percentile.
        max_processing_seconds: The slowest frame's time.
        worst_frame: The slowest frame's index (the first, on a tie).
        worst_frame_scene: Its scene, or None when the frame names none.
        budget_seconds: One frame's budget (1 / the recording's target FPS), or None when
            uncapped.
        frames_over_budget: Frames whose processing took longer than the budget, or None
            without one.
        frame_time: The live run's frame times, or None (a rebaseline's run, or no ``dt``).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    measured_frames: int
    total_processing_seconds: float
    p50_processing_seconds: float
    p95_processing_seconds: float
    p99_processing_seconds: float
    max_processing_seconds: float
    worst_frame: int
    worst_frame_scene: str | None
    budget_seconds: float | None
    frames_over_budget: int | None
    frame_time: FrameTimeSummary | None


def _percentile(*, sorted_values: Sequence[float], percent: float) -> float:
    """Return a nearest-rank percentile of sorted values.

    Args:
        sorted_values: The values, ascending (at least one).
        percent: The percentile, 0 to 100.

    Returns:
        The smallest value with at least ``percent`` of the values at or below it.

    """
    rank = max(1, math.ceil(percent / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def _rounded(seconds: float) -> float:
    return round(seconds, PROCESSING_SECONDS_DIGITS)


def frame_time_summary(
    *, frames: Sequence[Mapping[str, Any]], budget_seconds: float | None
) -> FrameTimeSummary | None:
    """Summarise a recording's frame times (each frame's ``dt``).

    Args:
        frames: The decoded frames.
        budget_seconds: One frame's budget, or None when uncapped.

    Returns:
        The summary, or None when no frame has a numeric ``dt``.

    """
    frame_seconds = sorted(
        float(frame['dt'])
        for frame in frames
        if isinstance(frame.get('dt'), int | float) and not isinstance(frame.get('dt'), bool)
    )
    if not frame_seconds:
        return None
    late_frames = (
        None
        if budget_seconds is None
        else sum(
            1 for seconds in frame_seconds if seconds > budget_seconds * LATE_FRAME_BUDGET_FACTOR
        )
    )
    return FrameTimeSummary(
        p50_seconds=_rounded(_percentile(sorted_values=frame_seconds, percent=50)),
        p99_seconds=_rounded(_percentile(sorted_values=frame_seconds, percent=99)),
        max_seconds=_rounded(frame_seconds[-1]),
        late_frames=late_frames,
    )


def run_summary(
    *,
    frames: Sequence[Mapping[str, Any]],
    run_index: int,
    budget_seconds: float | None,
    live_run: bool,
) -> RunSummary | None:
    """Summarise one run's processing times from its recording's frames.

    Args:
        frames: The decoded frames (each with its ``processing_seconds`` history).
        run_index: The run's index in the histories (0 = the newest).
        budget_seconds: One frame's budget, or None when uncapped.
        live_run: True for the run that recorded the frames live (it measured their ``dt``).

    Returns:
        The summary, or None when no frame holds a time for the run.

    """
    timed_frames: list[tuple[float, int, Mapping[str, Any]]] = []
    for index, frame in enumerate(frames):
        history = frame.get(PROCESSING_SECONDS_FIELD)
        if not isinstance(history, list):
            continue
        run_times = cast('list[Any]', history)
        if len(run_times) <= run_index:
            continue
        seconds = run_times[run_index]
        if isinstance(seconds, int | float) and not isinstance(seconds, bool):
            timed_frames.append((float(seconds), index, frame))
    if not timed_frames:
        return None
    times = sorted(seconds for seconds, _, _ in timed_frames)
    worst_seconds, worst_index, worst = max(timed_frames, key=lambda timed: (timed[0], -timed[1]))
    scene = worst.get('scene')
    return RunSummary(
        measured_frames=len(times),
        total_processing_seconds=_rounded(math.fsum(times)),
        p50_processing_seconds=_rounded(_percentile(sorted_values=times, percent=50)),
        p95_processing_seconds=_rounded(_percentile(sorted_values=times, percent=95)),
        p99_processing_seconds=_rounded(_percentile(sorted_values=times, percent=99)),
        max_processing_seconds=_rounded(worst_seconds),
        worst_frame=int(worst.get('frame', worst_index)),
        worst_frame_scene=scene if isinstance(scene, str) else None,
        budget_seconds=budget_seconds,
        frames_over_budget=(
            None
            if budget_seconds is None
            else sum(1 for seconds in times if seconds > budget_seconds)
        ),
        frame_time=(
            frame_time_summary(frames=frames, budget_seconds=budget_seconds) if live_run else None
        ),
    )


def budget_seconds_for(*, header: Mapping[str, Any]) -> float | None:
    """Return one frame's budget from a recording's target FPS (its header's options).

    Args:
        header: The recording's header fields.

    Returns:
        1 / target FPS, or None when uncapped (0) or not recorded.

    """
    options = header.get('options')
    target_fps = (
        cast('dict[str, Any]', options).get('target_fps') if isinstance(options, dict) else None
    )
    if isinstance(target_fps, int | float) and not isinstance(target_fps, bool) and target_fps > 0:
        return 1.0 / float(target_fps)
    return None


class MeasurementRun(BaseModel):
    """One run's provenance: what measured a recording's processing times and drew its frames.

    Attributes:
        machine: The machine (``glitchygames.replay.processing.machine_description``).
        processing_paced: Whether the run paced its frames as recording began (paced frames
            process slower: no fair baseline for an unpaced replay).
        pacing_timer: The run's frame-pacing timer (``glitchygames.timing.PacingTimer``: the
            backend, its final spin, the sleep model ``--timer-backend auto`` measured, or None
            for a run that never paced), named whether or not the run paced
            (``processing_paced``); None only for a run from before this field.
        engine_version: The engine's version, or None when not installed.
        pygame_version: pygame's version.
        python_version: Python's version.
        measured_at: When the run began, ISO 8601 with its offset.
        rebaselined_from: The recording the run rebaselined, or None for a fresh recording.
        hash_scheme: The content hash's definition (``CONTENT_HASH_SCHEME``).
        frame_count: How many frames the run wrote, filled in when the next run stacks onto
            its recording (``stacked_measurement_runs``); None for the newest run, whose count
            is its file's frames.
        source_revision: The engine's source revision (glitchygames/build_info.py: the commit,
            whether the checkout had uncommitted changes, and how that is known); None only for
            a run from before this field.
        game_source_revision: The game's source revision, looked up the same way in the
            directory of the game's package (``glitchygames.replay.tools.identity``); None for a
            run from before this field, or of a game whose package was not found. A ledger row
            names its commit (``game_or_engine_revision``).
        machine_state: The machine's state as the run started (glitchygames/machine_state.py:
            CPU, memory, mains or battery, thermal report, continuous integration); None only
            for a run from before this field.
        summary: The run's processing times at a glance (``RunSummary``), filled in when the
            next run stacks onto its recording (its header is written before its frames); None
            for the newest run (``recording_run_summaries`` computes it) and runs from before
            this field.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    machine: str
    processing_paced: bool
    engine_version: str | None
    pygame_version: str
    python_version: str
    measured_at: str
    rebaselined_from: str | None
    hash_scheme: int
    frame_count: int | None = None
    pacing_timer: PacingTimer | None = None
    source_revision: SourceRevision | None = None
    game_source_revision: SourceRevision | None = None
    machine_state: MachineState | None = None
    summary: RunSummary | None = None

    @property
    def game_or_engine_revision(self: Self) -> SourceRevision | None:
        """The revision of the code the run measured: the game's, else the engine's.

        The game's (``game_source_revision``) whenever it is recorded, even unknown: a game
        outside this repository never takes the engine's commit. The engine's for a run from
        before the field, or of a game whose package was not found. In this repository the two
        are one checkout, so they name the same commit.
        """
        return (
            self.source_revision if self.game_source_revision is None else self.game_source_revision
        )

    def to_json(self: Self) -> dict[str, Any]:
        """Return the run as the header stores it.

        Returns:
            Its fields.

        """
        return self.model_dump(mode='json')


def stacked_measurement_runs(
    *,
    newest: MeasurementRun,
    previous: object,
    previous_frame_count: int | None,
    previous_frames: Sequence[Mapping[str, Any]] = (),
    budget_seconds: float | None = None,
) -> list[dict[str, Any]]:
    """Return the header's runs with ``newest`` in front, cut to ``MEASUREMENT_RUNS_HISTORY_DEPTH``.

    Earlier entries are kept as they are (an unreadable one keeps its place, so indexes stay
    aligned with the frames' histories), but the run before gets its ``frame_count``: only now,
    with its recording read, is it known (a run's own header is written before its frames).
    Likewise every earlier run without a ``summary`` gets one from the earlier frames (its own
    index in their ``processing_seconds`` histories), when they hold any of its times.

    Args:
        newest: This run.
        previous: The earlier ``measurement_runs`` (anything but a list counts as none).
        previous_frame_count: How many complete frames the earlier recording holds, or None.
        previous_frames: The earlier recording's decoded frames (none: no summaries added).
        budget_seconds: One frame's budget (``budget_seconds_for``), or None when uncapped.

    Returns:
        The runs, newest first.

    """
    earlier = list(cast('list[Any]', previous)) if isinstance(previous, list) else []
    if earlier and isinstance(earlier[0], dict) and previous_frame_count is not None:
        earlier[0] = {**cast('dict[str, Any]', earlier[0]), 'frame_count': previous_frame_count}
    for run_index, run in enumerate(earlier):
        if not isinstance(run, dict):
            continue
        run_fields = cast('dict[str, Any]', run)
        if run_fields.get(RUN_SUMMARY_FIELD) is not None:
            continue
        summary = run_summary(
            frames=previous_frames,
            run_index=run_index,
            budget_seconds=budget_seconds,
            live_run=run_fields.get('rebaselined_from') is None,
        )
        if summary is not None:
            earlier[run_index] = {**run_fields, RUN_SUMMARY_FIELD: summary.model_dump(mode='json')}
    return stacked_history(
        newest=newest.to_json(), previous=earlier, depth=MEASUREMENT_RUNS_HISTORY_DEPTH
    )


def recording_run_summaries(
    *, header: Mapping[str, Any], frames: Sequence[Mapping[str, Any]]
) -> list[RunSummary | None]:
    """Return every run's summary: the stored one, else computed from the frames.

    The newest run never has one stored (see ``MeasurementRun.summary``); runs from before
    summaries existed have none either.

    Args:
        header: The recording's header fields.
        frames: Its decoded frames.

    Returns:
        One entry per ``measurement_runs`` entry, newest first (None when neither the header
        nor the frames give one).

    """
    runs = header.get(MEASUREMENT_RUNS_HEADER_FIELD)
    if not isinstance(runs, list):
        return []
    budget_seconds = budget_seconds_for(header=header)
    summaries: list[RunSummary | None] = []
    for run_index, run in enumerate(cast('list[Any]', runs)):
        run_fields = cast('dict[str, Any]', run) if isinstance(run, dict) else {}
        try:
            stored = RunSummary.model_validate(run_fields[RUN_SUMMARY_FIELD])
        except KeyError, ValidationError:
            stored = None
        summaries.append(
            stored
            or run_summary(
                frames=frames,
                run_index=run_index,
                budget_seconds=budget_seconds,
                live_run=run_fields.get('rebaselined_from') is None,
            )
        )
    return summaries


def latest_measurement_run(*, header: Mapping[str, Any]) -> MeasurementRun | None:
    """Return the newest run a header names (``measurement_runs[0]``).

    Args:
        header: A recording's header fields.

    Returns:
        The run, or None when the header has none or it is unreadable.

    """
    runs = header.get(MEASUREMENT_RUNS_HEADER_FIELD)
    if not isinstance(runs, list) or not runs:
        return None
    return measurement_run_from(run=cast('list[Any]', runs)[0])


def measurement_run_from(*, run: object) -> MeasurementRun | None:
    """Read one ``measurement_runs`` entry leniently.

    A newer run's extra fields (one this reader does not know) must not hide what this reader
    knows of it, so unknown fields are dropped; writing stays strict (extra='forbid').

    Args:
        run: The entry, as the header holds it.

    Returns:
        The run, or None when it is not a mapping or its known fields are unreadable.

    """
    if not isinstance(run, dict):
        return None
    run_fields = cast('dict[str, Any]', run)
    known_fields = {
        name: value for name, value in run_fields.items() if name in MeasurementRun.model_fields
    }
    try:
        return MeasurementRun.model_validate(known_fields)
    except ValidationError:
        return None


def recorded_measurement_runs(*, header: Mapping[str, Any]) -> list[MeasurementRun | None]:
    """Return every run a header names, newest first, each read leniently.

    Args:
        header: A recording's header fields.

    Returns:
        One entry per ``measurement_runs`` entry (None for an unreadable one, so indexes stay
        aligned with the frames' histories); empty when the header has none.

    """
    runs = header.get(MEASUREMENT_RUNS_HEADER_FIELD)
    if not isinstance(runs, list):
        return []
    return [measurement_run_from(run=run) for run in cast('list[Any]', runs)]
