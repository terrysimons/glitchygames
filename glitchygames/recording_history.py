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
- ``measurement_runs`` (header): each run's provenance (``MeasurementRun``: machine, pacing,
  versions, when it measured, what it was rebaselined from, the hash scheme).

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
from typing import TYPE_CHECKING, Any, Self, cast

from pydantic import BaseModel, ConfigDict, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

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


class MeasurementRun(BaseModel):
    """One run's provenance: what measured a recording's processing times and drew its frames.

    Attributes:
        machine: The machine (``glitchygames.replay.processing.machine_description``).
        processing_paced: Whether the run paced its frames as recording began (paced frames
            process slower: no fair baseline for an unpaced replay).
        engine_version: The engine's version, or None when not installed.
        pygame_version: pygame's version.
        python_version: Python's version.
        measured_at: When the run began, ISO 8601 with its offset.
        rebaselined_from: The recording the run rebaselined, or None for a fresh recording.
        hash_scheme: The content hash's definition (``CONTENT_HASH_SCHEME``).
        frame_count: How many frames the run wrote, filled in when the next run stacks onto
            its recording (``stacked_measurement_runs``); None for the newest run, whose count
            is its file's frames.

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

    def to_json(self: Self) -> dict[str, Any]:
        """Return the run as the header stores it.

        Returns:
            Its fields.

        """
        return self.model_dump(mode='json')


def stacked_measurement_runs(
    *, newest: MeasurementRun, previous: object, previous_frame_count: int | None
) -> list[dict[str, Any]]:
    """Return the header's runs with ``newest`` in front, cut to ``MEASUREMENT_RUNS_HISTORY_DEPTH``.

    Earlier entries are kept as they are (an unreadable one keeps its place, so indexes stay
    aligned with the frames' histories), but the run before gets its ``frame_count``: only now,
    with its recording read, is it known (a run's own header is written before its frames).

    Args:
        newest: This run.
        previous: The earlier ``measurement_runs`` (anything but a list counts as none).
        previous_frame_count: How many complete frames the earlier recording holds, or None.

    Returns:
        The runs, newest first.

    """
    earlier = list(cast('list[Any]', previous)) if isinstance(previous, list) else []
    if earlier and isinstance(earlier[0], dict) and previous_frame_count is not None:
        earlier[0] = {**cast('dict[str, Any]', earlier[0]), 'frame_count': previous_frame_count}
    return stacked_history(
        newest=newest.to_json(), previous=earlier, depth=MEASUREMENT_RUNS_HISTORY_DEPTH
    )


def latest_measurement_run(*, header: Mapping[str, Any]) -> MeasurementRun | None:
    """Return the newest run a header names (``measurement_runs[0]``).

    Args:
        header: A recording's header fields.

    Returns:
        The run, or None when the header has none or it is unreadable.

    """
    runs = header.get(MEASUREMENT_RUNS_HEADER_FIELD)
    if not isinstance(runs, list) or not runs or not isinstance(runs[0], dict):
        return None
    # Read leniently: a newer run's extra fields (a git commit, say) must not hide what this
    # reader knows of it; writing stays strict (extra='forbid')
    latest = cast('dict[str, Any]', runs[0])
    known_fields = {
        name: value for name, value in latest.items() if name in MeasurementRun.model_fields
    }
    try:
        return MeasurementRun.model_validate(known_fields)
    except ValidationError:
        return None
