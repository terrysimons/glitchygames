# Recording Content Hashes and Measurement History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every recorded frame carries a newest-first history of its content hash and processing
time across rebaselines, and every recording header a matching history of measurement runs, so
the baselines in the repository record behaviour and speed over time.

**Architecture:** A new leaf module, `glitchygames/recording_history.py` (no engine imports),
holds the field names, depth constants, the pydantic classification of frame fields, the hash
(`frame_content_hash`, `recording_content_hash`), the history stacking and the `MeasurementRun`
provenance model. `GameplayRecorder.record_frame` hashes each frame and stacks the histories
(over a replay, onto the replayed frame's); the engine builds each run's `MeasurementRun`
(`GameEngine.measurement_run`, the one raw clock read added) for live recordings and rebaselines;
the replay driver reads `[0]` of everything.

**Tech Stack:** Python 3.14, pydantic v2 (frozen, `extra='forbid'`), stdlib `hashlib`/`json`,
pytest with pytest-mock, pytest-benchmark.

**Spec:** `plans/2026-10-20-recording-content-hash-and-history.md` (the "Better" hashing option,
chosen 2026-10-21). Read it first: its field inventory is the contract for Task 1's
classification.

## Global Constraints

- Python 3.14; ruff (100-character lines), basedpyright and ty clean on every changed file; run
  linters before tests; never change lint or type-checker configuration.
- No lint or type suppressions (`# noqa`, `# type: ignore`, `# pyright: ignore`, `# ty: ignore`,
  `# ruff: ignore`) in new or changed lines.
- Keyword arguments at call sites; keyword-only (`*,`) parameters for new functions; full names,
  no abbreviations; Google-style docstrings.
- New data classes are pydantic `BaseModel` with `ConfigDict(frozen=True, extra='forbid')`.
- Tests: pytest assertions, the `mocker` fixture (never `unittest.mock`), new tests in existing
  files where one fits.
- Depth constants, each starting at 10: `PROCESSING_SECONDS_HISTORY_DEPTH`,
  `CONTENT_HASH_HISTORY_DEPTH`, `MEASUREMENT_RUNS_HISTORY_DEPTH`.
- Hash: SHA-256 of compact, key-sorted JSON (`separators=(',', ':')`, `sort_keys=True`), first 16
  hex digits (64 bits); `CONTENT_HASH_SCHEME = 1` names that definition.
- Every history list is newest first; a run inserts exactly one entry (a value or None) at `[0]`
  of every history list of every frame it writes, then cuts the list to its depth.
- No format version bump. `processing_seconds` becomes a list (no recording with the number has
  been committed or shipped); the top-level header fields `machine` and `processing_paced` are
  removed (same reason).
- Do not commit: the user commits. Each task ends with its changes staged for review.
- Out of scope (spec "What we are not doing"): stacking FPS or `dt`, keeping old sprites, fixed-dt
  re-records, hashing measurements or the header, a sidecar file, a replay comparing
  `content_hash`, unifying `--audit`'s digest, a git commit per run (the user has not decided),
  wiring C12.

## Review Focus

- A stored `content_hash[0]` equals the hash recomputed from the frame as read back from the
  file, including a frame holding a non-finite float (stored tagged), a tuple and non-ASCII
  text: the hash must describe what a reader gets, not only what the writer had (Task 2).
- Rebaselining a recording made before this change (today's golden fixtures: no histories, no
  `measurement_runs`) gives one-entry lists and one run, aligned (Task 3).
- Depths tuned apart (for example processing 3, hash 2, runs 1) keep index `i` meaning run `i`
  in every list that is long enough (Task 3).
- A frame whose processing time was not measured still gets its entry (`None`), so the lists stay
  aligned (Task 2).
- A rebaseline that ends before OLD's last frame stacks histories only for the frames it ran,
  and `recording_content_hash` then tells its run from OLD's (Task 3).

---

### Task 1: The history module (`glitchygames/recording_history.py`)

**Files:**
- Create: `glitchygames/recording_history.py`
- Test: `tests/test_recording_history.py` (new: the module is new)
- Modify: `tests/benchmarks/test_benchmarks.py` (one benchmark)

**Interfaces:**
- Consumes: nothing from the engine (a leaf module: stdlib and pydantic only).
- Produces:
  - Constants: `PROCESSING_SECONDS_FIELD = 'processing_seconds'`,
    `CONTENT_HASH_FIELD = 'content_hash'`, `MEASUREMENT_RUNS_HEADER_FIELD = 'measurement_runs'`,
    `PROCESSING_SECONDS_HISTORY_DEPTH = 10`, `CONTENT_HASH_HISTORY_DEPTH = 10`,
    `MEASUREMENT_RUNS_HISTORY_DEPTH = 10`, `CONTENT_HASH_SCHEME = 1`,
    `CONTENT_HASH_HEX_DIGITS = 16`, `PROCESSING_SECONDS_DIGITS = 6`,
    `MEASUREMENT_FRAME_FIELDS: frozenset[str]`.
  - `class FrameContent(BaseModel)`: the content fields (classification).
  - `class UnclassifiedFrameFieldError(ValueError)`.
  - `def frame_content_hash(*, frame_record: Mapping[str, Any]) -> str`
  - `def recording_content_hash(*, frames: Iterable[Mapping[str, Any]], run_index: int = 0) -> str | None`
  - `def stacked_history(*, newest: object, previous: object, depth: int) -> list[Any]`
  - `def add_frame_histories(*, frame_record: dict[str, Any], processing_seconds: float | None, previous_histories: Mapping[str, Any] | None) -> None`
  - `class MeasurementRun(BaseModel)` with `to_json() -> dict[str, Any]`
  - `def stacked_measurement_runs(*, newest: MeasurementRun, previous: object) -> list[dict[str, Any]]`
  - `def latest_measurement_run(*, header: Mapping[str, Any]) -> MeasurementRun | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_recording_history.py`:

```python
"""Content hashes and measurement history of recorded frames (glitchygames/recording_history.py)."""

from __future__ import annotations

import hashlib
import json

import pytest

from glitchygames import recording_history
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    CONTENT_HASH_HEX_DIGITS,
    CONTENT_HASH_SCHEME,
    MEASUREMENT_RUNS_HEADER_FIELD,
    PROCESSING_SECONDS_FIELD,
    FrameContent,
    MeasurementRun,
    UnclassifiedFrameFieldError,
    add_frame_histories,
    frame_content_hash,
    latest_measurement_run,
    recording_content_hash,
    stacked_history,
    stacked_measurement_runs,
)

FRAME = {
    'frame': 3,
    'dt': 0.016,
    'event_batches': [[{'type': 768, 'name': 'KeyDown', 'origin': 'external', 'attributes': {}}]],
    'scene': 'Game',
    'sprites': [{'id': 'Ball#0', 'rect': [1, 2, 3, 4], 'visible': True}],
}


def measurement_run(*, measured_at: str = '2026-10-21T12:00:00+00:00') -> MeasurementRun:
    """Return a run's provenance for the tests.

    Returns:
        The run.

    """
    return MeasurementRun(
        machine='macOS-27.0-arm64-arm-64bit',
        processing_paced=False,
        engine_version='1.0.0',
        pygame_version='2.5.8',
        python_version='3.14.8',
        measured_at=measured_at,
        rebaselined_from=None,
        hash_scheme=CONTENT_HASH_SCHEME,
    )


class TestTheContentHash:
    """SHA-256 of the frame's content as compact sorted JSON, 64 bits, measurements left out."""

    def test_the_hash_is_the_first_64_bits_of_sha256_of_sorted_compact_json(self):
        encoded = json.dumps(FRAME, sort_keys=True, separators=(',', ':')).encode('utf-8')
        expected = hashlib.sha256(encoded).hexdigest()[:CONTENT_HASH_HEX_DIGITS]
        assert frame_content_hash(frame_record=FRAME) == expected
        assert len(expected) == CONTENT_HASH_HEX_DIGITS

    def test_measurements_never_change_the_hash(self):
        measured = {**FRAME, PROCESSING_SECONDS_FIELD: [0.002], CONTENT_HASH_FIELD: ['abcd']}
        assert frame_content_hash(frame_record=measured) == frame_content_hash(frame_record=FRAME)

    @pytest.mark.parametrize(
        ('field', 'value'),
        [('sprites', [{'id': 'Ball#0', 'rect': [1, 3, 3, 4], 'visible': True}]), ('dt', 0.017)],
    )
    def test_any_content_change_changes_the_hash(self, field, value):
        changed = {**FRAME, field: value}
        assert frame_content_hash(frame_record=changed) != frame_content_hash(frame_record=FRAME)

    def test_key_order_does_not_matter(self):
        reordered = dict(reversed(list(FRAME.items())))
        assert frame_content_hash(frame_record=reordered) == frame_content_hash(frame_record=FRAME)

    def test_an_unclassified_field_fails_loudly(self):
        """Every frame field is content or a measurement (spec: classification is explicit)."""
        with pytest.raises(UnclassifiedFrameFieldError, match='future_field'):
            frame_content_hash(frame_record={**FRAME, 'future_field': 1})

    def test_the_classification_covers_every_field_a_recorder_writes(self):
        """The spec's inventory: these are the frame fields, content and measurements."""
        content_fields = {
            'frame', 'dt', 'event_batches', 'scene', 'sprites', 'input_changes',
            'control_events', 'devices_opened', 'saves_opened', 'device_enumeration',
            'scene_start', 'redelivered_events', 'resume_bridge', 'playback_answers',
        }
        assert set(FrameContent.model_fields) == content_fields
        assert recording_history.MEASUREMENT_FRAME_FIELDS == {
            PROCESSING_SECONDS_FIELD,
            CONTENT_HASH_FIELD,
        }


class TestTheRecordingHash:
    """A recording's hash is derived from its frames' hashes, for any run in their history."""

    def test_a_run_is_hashed_from_its_column_of_frame_hashes(self):
        frames = [{CONTENT_HASH_FIELD: ['aa', 'bb']}, {CONTENT_HASH_FIELD: ['cc', 'dd']}]
        newest = recording_content_hash(frames=frames)
        older = recording_content_hash(frames=frames, run_index=1)
        assert newest == hashlib.sha256(b'aa\ncc\n').hexdigest()[:CONTENT_HASH_HEX_DIGITS]
        assert older == hashlib.sha256(b'bb\ndd\n').hexdigest()[:CONTENT_HASH_HEX_DIGITS]

    @pytest.mark.parametrize(
        'frames',
        [[{}], [{CONTENT_HASH_FIELD: []}], [{CONTENT_HASH_FIELD: [None]}], [{CONTENT_HASH_FIELD: 'aa'}]],
        ids=['no_history', 'empty', 'not_hashed', 'not_a_list'],
    )
    def test_a_frame_without_that_runs_hash_gives_no_recording_hash(self, frames):
        assert recording_content_hash(frames=frames) is None


class TestStacking:
    """Newest first; one entry per run; cut to the depth from the tail."""

    def test_the_newest_goes_first(self):
        assert stacked_history(newest=3, previous=[2, 1], depth=10) == [3, 2, 1]

    def test_the_oldest_falls_off_at_the_depth(self):
        assert stacked_history(newest=3, previous=[2, 1], depth=2) == [3, 2]

    @pytest.mark.parametrize('previous', [None, 'not a list', 5])
    def test_no_previous_history_starts_one(self, previous):
        assert stacked_history(newest=3, previous=previous, depth=10) == [3]

    def test_an_unmeasured_value_keeps_its_place(self):
        assert stacked_history(newest=None, previous=[0.002], depth=10) == [None, 0.002]

    def test_a_frame_gets_both_histories(self):
        frame = dict(FRAME)
        add_frame_histories(
            frame_record=frame,
            processing_seconds=0.0012345678,
            previous_histories={PROCESSING_SECONDS_FIELD: [0.002], CONTENT_HASH_FIELD: ['old']},
        )
        assert frame[CONTENT_HASH_FIELD] == [frame_content_hash(frame_record=FRAME), 'old']
        # Rounded to the microsecond
        assert frame[PROCESSING_SECONDS_FIELD] == [0.001235, 0.002]

    def test_each_history_has_its_own_depth(self, mocker):
        mocker.patch.object(recording_history, 'PROCESSING_SECONDS_HISTORY_DEPTH', 3)
        mocker.patch.object(recording_history, 'CONTENT_HASH_HISTORY_DEPTH', 1)
        frame = dict(FRAME)
        add_frame_histories(
            frame_record=frame,
            processing_seconds=0.004,
            previous_histories={
                PROCESSING_SECONDS_FIELD: [0.003, 0.002, 0.001],
                CONTENT_HASH_FIELD: ['b', 'a'],
            },
        )
        assert frame[PROCESSING_SECONDS_FIELD] == [0.004, 0.003, 0.002]
        assert len(frame[CONTENT_HASH_FIELD]) == 1


class TestMeasurementRuns:
    """The header's newest-first provenance of each run (machine, pacing, versions, scheme)."""

    def test_runs_stack_newest_first_and_stop_at_their_depth(self, mocker):
        mocker.patch.object(recording_history, 'MEASUREMENT_RUNS_HISTORY_DEPTH', 2)
        first = measurement_run(measured_at='2026-10-21T01:00:00+00:00').to_json()
        second = measurement_run(measured_at='2026-10-21T02:00:00+00:00').to_json()
        newest = measurement_run(measured_at='2026-10-21T03:00:00+00:00')
        runs = stacked_measurement_runs(newest=newest, previous=[second, first])
        assert runs == [newest.to_json(), second]

    def test_the_latest_run_is_read_from_the_front(self):
        newest = measurement_run(measured_at='2026-10-21T03:00:00+00:00')
        header = {MEASUREMENT_RUNS_HEADER_FIELD: [newest.to_json(), measurement_run().to_json()]}
        assert latest_measurement_run(header=header) == newest

    @pytest.mark.parametrize(
        'header',
        [{}, {MEASUREMENT_RUNS_HEADER_FIELD: []}, {MEASUREMENT_RUNS_HEADER_FIELD: [{'machine': 1}]}],
        ids=['none', 'empty', 'malformed'],
    )
    def test_a_header_without_a_readable_run_has_no_latest(self, header):
        assert latest_measurement_run(header=header) is None

    def test_a_run_is_read_only_and_closed(self):
        with pytest.raises(ValueError, match='Extra inputs'):
            MeasurementRun.model_validate({**measurement_run().to_json(), 'extra': 1})
```

Add to `tests/benchmarks/test_benchmarks.py` a benchmark of the largest golden-fixture frame
(the per-frame cost the spec says to measure). The two imports join the file's import block at
the top (sorted by `ruff check --select I --fix`); the constant joins its constants; the test
goes at the end:

```python
from glitchygames.recording_history import frame_content_hash
from glitchygames.tracing import read_trace_result

BRAVE_ADVENTURER_GOLDEN = (
    Path(__file__).parent.parent / 'fixtures' / 'replays' / 'brave-adventurer' / 'golden.jsonl.gz'
)


def test_benchmark_frame_content_hash_of_the_largest_golden_frame(benchmark):
    """Hashing one frame (105 sprites, about 7 KB of JSON): measured 40 µs when designed."""
    frames = read_trace_result(path=BRAVE_ADVENTURER_GOLDEN).trace['frames']
    largest = max(frames, key=lambda frame: len(frame.get('sprites', [])))
    digest = benchmark(lambda: frame_content_hash(frame_record=largest))
    assert len(digest) == 16
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_recording_history.py -q --no-cov`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'glitchygames.recording_history'`.

- [ ] **Step 3: Write the module**

Create `glitchygames/recording_history.py`:

```python
"""Content hashes and measurement history of recorded frames (a leaf: no engine imports).

Design: plans/2026-10-20-recording-content-hash-and-history.md. Each frame a recorder writes
carries two newest-first history lists, and the header a third:

- ``content_hash``: the frame's content hash (``frame_content_hash``): SHA-256 of its content
  fields as compact, key-sorted JSON, cut to 64 bits (16 hex digits). Content is everything the
  game did or took in (``FrameContent``); measurements are left out
  (``MEASUREMENT_FRAME_FIELDS``). Replays and rebaselines of one recording reproduce it, unless
  the game's behaviour changed.
- ``processing_seconds``: the frame's processing time (glitchygames/replay/processing.py),
  rounded to the microsecond; None when it was not measured.
- ``measurement_runs`` (header): each run's provenance (``MeasurementRun``: machine, pacing,
  versions, when it measured, what it was rebaselined from, the hash scheme).

Index ``i`` means run ``i`` in every list: a run inserts exactly one entry at ``[0]`` of every
list of every frame it writes (``stacked_history``), and lists are only cut from the tail, at
each list's own depth constant. A recording's hash for run ``i`` is derived from its frames'
``content_hash[i]`` (``recording_content_hash``); it is not stored. ``CONTENT_HASH_SCHEME``
names the hash's definition: a later definition is a new scheme, so old entries are known to be
incomparable rather than changed.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Self

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

# The hash's definition: SHA-256 of compact, key-sorted JSON of the content fields, 64 bits
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
        The first 16 hex digits of the SHA-256 of its content as compact, key-sorted JSON.

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
    encoded = json.dumps(content, sort_keys=True, separators=(',', ':')).encode('utf-8')
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
        history = frame.get(CONTENT_HASH_FIELD)
        if not isinstance(history, list) or run_index >= len(history):
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
    earlier = list(previous) if isinstance(previous, list) else []
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

    def to_json(self: Self) -> dict[str, Any]:
        """Return the run as the header stores it.

        Returns:
            Its fields.

        """
        return self.model_dump(mode='json')


def stacked_measurement_runs(*, newest: MeasurementRun, previous: object) -> list[dict[str, Any]]:
    """Return the header's runs with ``newest`` in front, cut to ``MEASUREMENT_RUNS_HISTORY_DEPTH``.

    Earlier entries are kept as they are (an unreadable one keeps its place, so indexes stay
    aligned with the frames' histories).

    Args:
        newest: This run.
        previous: The earlier ``measurement_runs`` (anything but a list counts as none).

    Returns:
        The runs, newest first.

    """
    return stacked_history(
        newest=newest.to_json(), previous=previous, depth=MEASUREMENT_RUNS_HISTORY_DEPTH
    )


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
    try:
        return MeasurementRun.model_validate(runs[0])
    except ValidationError:
        return None
```

- [ ] **Step 4: Lint, then run the tests to verify they pass**

Run: `uv run ruff format glitchygames/recording_history.py tests/test_recording_history.py tests/benchmarks/test_benchmarks.py && uv run ruff check glitchygames/recording_history.py tests/test_recording_history.py tests/benchmarks/test_benchmarks.py && uv run basedpyright glitchygames/recording_history.py tests/test_recording_history.py && uv run ty check glitchygames/recording_history.py tests/test_recording_history.py`
Expected: no findings.
Run: `uv run pytest tests/test_recording_history.py -q --no-cov`
Expected: all pass.
Run: `uv run pytest tests/benchmarks/test_benchmarks.py -k frame_content_hash --benchmark-only -p no:xdist --no-cov`
Expected: PASS; mean in the tens of microseconds (about 40 µs on the designing machine). Report
the number; a mean above 200 µs is a finding for the spec's "Where it is computed" fallback.

- [ ] **Step 5: Stage for review** (do not commit: the user commits)

```bash
git add glitchygames/recording_history.py tests/test_recording_history.py tests/benchmarks/test_benchmarks.py
```

---

### Task 2: Recorders write the frame histories

**Files:**
- Modify: `glitchygames/recording.py` (`GameplayRecorder.record_frame`, `RecordingSources.end_frame`,
  `RecordedFrameFields`, `RecordedFrameFieldSource`, field constants, module docstring)
- Modify: `glitchygames/replay/driver.py` (`RecordedFrames.recorded_frame_histories`,
  `ReplaySources._compare_processing`)
- Test: `tests/test_recording.py`, `tests/world/test_gameplay_recording.py`,
  `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Consumes (Task 1): `add_frame_histories`, `frame_content_hash`, `PROCESSING_SECONDS_FIELD`,
  `CONTENT_HASH_FIELD`, `MEASUREMENT_FRAME_FIELDS`.
- Produces:
  - `GameplayRecorder.record_frame(*, dt: float, scene: Scene | None, processing_seconds: float | None = None, previous_histories: Mapping[str, Any] | None = None, **frame_fields: Unpack[RecordedFrameFields]) -> None`
  - `RecordedFrames.recorded_frame_histories(*, frame_index: int) -> dict[str, Any]` (and the
    same method on the `RecordedFrameFieldSource` protocol)
  - `recording.PROCESSING_SECONDS_FIELD` and `recording.CONTENT_HASH_FIELD` stay importable from
    `glitchygames.recording` (re-exported from `glitchygames.recording_history`).

- [ ] **Step 1: Write the failing tests**

In `tests/test_recording.py`, add to the imports `CONTENT_HASH_FIELD` and
`PROCESSING_SECONDS_FIELD` (from `glitchygames.recording`) and `frame_content_hash` (from
`glitchygames.recording_history`), then add this class after `TestRecorderWriteFailures`:

```python
class TestFrameHistories:
    """Each written frame carries its content hash and processing time, newest first."""

    def test_a_fresh_recording_starts_each_history_with_one_entry(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=None, processing_seconds=0.0021)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[PROCESSING_SECONDS_FIELD] == [0.0021]
        assert frame[CONTENT_HASH_FIELD] == [frame_content_hash(frame_record=frame)]

    def test_an_unmeasured_frame_keeps_its_place(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(dt=0.01, scene=None)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[PROCESSING_SECONDS_FIELD] == [None]

    def test_a_recording_over_a_replay_stacks_onto_the_replayed_frame(self, tmp_path):
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            recorder.record_frame(
                dt=0.01,
                scene=None,
                processing_seconds=0.003,
                previous_histories={
                    PROCESSING_SECONDS_FIELD: [0.002],
                    CONTENT_HASH_FIELD: ['0123456789abcdef'],
                },
            )
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[PROCESSING_SECONDS_FIELD] == [0.003, 0.002]
        assert frame[CONTENT_HASH_FIELD][1] == '0123456789abcdef'

    def test_the_stored_hash_is_the_hash_of_the_frame_read_back(self, tmp_path, event_queue):
        """A reader recomputes the hash from what it decodes: tagged floats, tuples, non-ASCII."""
        path = tmp_path / 'play.jsonl.gz'
        with GameplayRecorder(path=path, header={}) as recorder:
            post_event(
                pygame.event.Event(
                    pygame.USEREVENT, {'speed': float('inf'), 'pair': (1, 2), 'name': 'Ünïcødé'}
                )
            )
            _pump_batch(recorder)
            recorder.record_frame(dt=0.01, scene=None, processing_seconds=0.001)
        (frame,) = read_trace_result(path=path).trace['frames']
        assert frame[CONTENT_HASH_FIELD][0] == frame_content_hash(frame_record=frame)
```

In `tests/world/test_gameplay_recording.py`, add `CONTENT_HASH_FIELD` to the
`glitchygames.recording` imports and to `RECORDING_FRAME_FIELDS` (the recorder-only fields the
golden-harness comparison strips).

In `tests/world/test_gameplay_replay.py`, change `recorded_processing_times` to read the newest
entry:

```python
def recorded_processing_times(*, path: Path) -> list[float | None]:
    """Return each recorded frame's newest processing time (None where it has none).

    Returns:
        The times, in frame order.

    """
    return [
        (frame.get(PROCESSING_SECONDS_FIELD) or [None])[0]
        for frame in read_trace_result(path=path).trace['frames']
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_recording.py -k TestFrameHistories -q --no-cov`
Expected: FAIL: `record_frame() got an unexpected keyword argument 'previous_histories'` and
`assert [0.0021] ...` mismatches (today the field is a number).

- [ ] **Step 3: Implement**

In `glitchygames/recording.py`:

1. Replace the `PROCESSING_SECONDS_FIELD` and `PROCESSING_SECONDS_DIGITS` definitions (and their
   comments) with an import, and add `CONTENT_HASH_FIELD` to `RECORDING_FORMAT_THREE_FIELDS`
   after `PROCESSING_SECONDS_FIELD`:

```python
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    MEASUREMENT_FRAME_FIELDS,
    PROCESSING_SECONDS_FIELD,
    add_frame_histories,
)
```

2. Remove `processing_seconds: float | None` (and its `Attributes` line) from
   `RecordedFrameFields`: the recorder now builds that field itself.

3. Change `GameplayRecorder.record_frame` to take the measurement and the earlier histories, and
   add them after building the record:

```python
    def record_frame(
        self,
        *,
        dt: float,
        scene: Scene | None,
        processing_seconds: float | None = None,
        previous_histories: Mapping[str, Any] | None = None,
        **frame_fields: Unpack[RecordedFrameFields],
    ) -> None:
        """Write the frame just finished: its dt, its event batches and the scene's sprites.

        The format-3 fields (``RecordedFrameFields``, see the module docstring) are written
        only when given and not empty, so idle frames stay small. Every frame also gets its
        histories (glitchygames/recording_history.py): its content hash and processing time,
        in front of ``previous_histories`` (a rebaseline's: the replayed frame's).

        Args:
            dt: The frame's raw delta time (scene logic received it capped at the scene's
                MAX_FRAME_SECONDS, when the scene sets one).
            scene: The active scene at the end of the frame (None once the game has ended).
            processing_seconds: The frame's processing time, or None when not measured.
            previous_histories: The frame's earlier ``content_hash`` and ``processing_seconds``
                histories, or None for a fresh recording.
            **frame_fields: The frame's format-3 fields, by keyword.

        """
        if self._is_closed:
            # Abandoned after a failed write (or closed): nothing more is written
            return
        frame_record = recorded_frame(
            frame_number=self._writer.frame_count,
            scene=scene,
            sprite_ids=self._sprite_ids,
            dt=dt,
            event_batches=self._event_batches,
            **frame_fields,
        )
        add_frame_histories(
            frame_record=frame_record,
            processing_seconds=processing_seconds,
            previous_histories=previous_histories,
        )
        # (the rest of the method, from is_new_scene_object on, is unchanged)
```

4. In `RecordingSources.end_frame`, stop passing `processing_seconds=` inside the
   `record_frame(...)` keyword fields (delete the `processing_seconds=(None if ... else round(...))`
   argument and its comment) and pass the two new arguments instead:

```python
                # This run's own measurement, over a replay too (a rebaseline's NEW holds the
                # current code's times in front of OLD's)
                processing_seconds=processing_seconds,
                previous_histories=(
                    None
                    if self._replayed is None
                    else self._replayed.recording.recorded_frame_histories(
                        frame_index=self._recorder.frame_count
                    )
                ),
```

5. Add to the `RecordedFrameFieldSource` protocol:

```python
    def recorded_frame_histories(self, *, frame_index: int) -> dict[str, Any]:
        """Return a frame's recorded histories (``content_hash``, ``processing_seconds``).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Whichever the frame has; none past the end.

        """
        ...
```

In `glitchygames/replay/driver.py`:

6. Add to `RecordedFrames`, after `recorded_frame_fields`:

```python
    def recorded_frame_histories(self: Self, *, frame_index: int) -> dict[str, Any]:
        """Return the recorded frame's histories (a rebaseline stacks its own in front).

        Args:
            frame_index: The recording's frame index.

        Returns:
            Whichever of ``content_hash`` and ``processing_seconds`` the frame has; none past the
            end of the recording.

        """
        frame = self.frame(frame_index=frame_index)
        if frame is None:
            return {}
        return {name: frame[name] for name in MEASUREMENT_FRAME_FIELDS if name in frame}
```

   and import `MEASUREMENT_FRAME_FIELDS` from `glitchygames.recording_history`.

7. In `ReplaySources._compare_processing`, read the newest entry of the list:

```python
        history = frame.get(PROCESSING_SECONDS_FIELD)
        recorded_value = history[0] if isinstance(history, list) and history else None
        recorded_seconds: float | None = None
        if isinstance(recorded_value, (int, float)) and not isinstance(recorded_value, bool):
            recorded_seconds = float(recorded_value)
```

   (replacing the `recorded_value = frame.get(PROCESSING_SECONDS_FIELD)` line; the rest is
   unchanged).

8. In `tests/world/test_gameplay_replay.py`, `test_an_unchanged_recording_rebaselines_to_the_same_frames`:
   strip both measurement fields before comparing, and check the history stacked:

```python
        def without_measurements(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [
                {name: value for name, value in frame.items() if name not in MEASUREMENT_FRAME_FIELDS}
                for frame in frames
            ]

        assert without_measurements(new_trace['frames']) == without_measurements(
            old_trace['frames']
        )
        # Unchanged behaviour: this run's hash equals OLD's, now one entry deeper
        assert all(
            frame[CONTENT_HASH_FIELD][0] == frame[CONTENT_HASH_FIELD][1]
            for frame in new_trace['frames']
        )
```

   (replacing the `without_processing_times` helper and its two asserts; import
   `MEASUREMENT_FRAME_FIELDS` and `CONTENT_HASH_FIELD`).

- [ ] **Step 4: Lint, then run the tests**

Run: `uv run ruff format glitchygames/recording.py glitchygames/replay/driver.py tests/test_recording.py tests/world/test_gameplay_recording.py tests/world/test_gameplay_replay.py && uv run ruff check glitchygames tests && uv run basedpyright glitchygames/recording.py glitchygames/replay/driver.py tests/test_recording.py`
Expected: no findings.
Run: `uv run pytest tests/test_recording.py tests/world tests/replay -q --no-cov -n auto -p no:randomly`
Expected: all pass. If a golden-harness comparison hangs, it is comparing frames that still hold a
measurement field: add the field to that test's stripped set (it is pytest's diff of hundreds of
frames that is slow, not the code).

- [ ] **Step 5: Stage for review**

```bash
git add glitchygames/recording.py glitchygames/replay/driver.py tests/test_recording.py tests/world/test_gameplay_recording.py tests/world/test_gameplay_replay.py
```

---

### Task 3: Measurement runs in the header, and rebaselines that stack

**Files:**
- Modify: `glitchygames/engine/game_engine.py` (`trace_recording_header`, new `measurement_run`,
  the `Rebaseline(...)` construction in `__init__`)
- Modify: `glitchygames/replay/rebaseline.py` (`Rebaseline.__init__`, `rebaseline_header`)
- Modify: `glitchygames/replay/driver.py` (`_recorded_machine`, `_recorded_paced`)
- Modify: `glitchygames/recording.py` (remove `MACHINE_HEADER_FIELD`, `PROCESSING_PACED_HEADER_FIELD`)
- Modify: `tests/test_engine_doors.py` (one allow-list entry)
- Test: `tests/world/test_gameplay_replay.py`

**Interfaces:**
- Consumes (Task 1): `MeasurementRun`, `stacked_measurement_runs`, `latest_measurement_run`,
  `recording_content_hash`, `MEASUREMENT_RUNS_HEADER_FIELD`, `CONTENT_HASH_SCHEME`; (Task 2) the
  frame histories.
- Produces:
  - `GameEngine.measurement_run(self, *, processing_paced: bool, rebaselined_from: str | None) -> MeasurementRun`
  - `Rebaseline.__init__(self, *, replay_sources: ReplaySources, source_path: Path, destination: Path, measurement_run: MeasurementRun) -> None`
  - `rebaseline_header(*, original_header: Mapping[str, Any], original_path: Path, measurement_run: MeasurementRun, source_truncated: bool = False) -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests**

In `tests/world/test_gameplay_replay.py` (imports: `MEASUREMENT_RUNS_HEADER_FIELD`,
`CONTENT_HASH_FIELD`, `latest_measurement_run`, `recording_content_hash` and `recording_history`
the module, from `glitchygames.recording_history`), replace the three header assertions in
`TestProcessingComparison` (`header[MACHINE_HEADER_FIELD]`, `header[PROCESSING_PACED_HEADER_FIELD]`
in `test_a_recording_holds_each_frames_processing_time_and_its_machine`,
`test_a_run_with_a_target_fps_says_its_frames_are_paced` and
`test_a_rebaseline_records_its_own_processing_times`) with reads of the latest run, for example:

```python
        run = latest_measurement_run(header=read_trace_result(path=recording_path).trace)
        assert run is not None
        assert run.machine == machine_description()
        # The harness runs uncapped (--target-fps 0): its frames are not paced
        assert run.processing_paced is False
        assert run.rebaselined_from is None
```

(`is True` for the 60 FPS test; for the rebaseline test, `new_run.processing_paced is False` and
`new_run.rebaselined_from == str(recording_path)`), and add this class after
`TestProcessingComparison`:

```python
class TestRebaselineHistory:
    """Each rebaseline puts its run in front: frames' histories and the header's runs align."""

    def rebaselined(self, *, mocker, tmp_path, source: Path, name: str) -> Path:
        """Rebaseline ``source`` to ``tmp_path / name`` and return it (exit SUCCESS expected).

        Returns:
            NEW's path.

        """
        new_path = tmp_path / name
        exit_status = rebaseline_session(recording_path=source, new_path=new_path, mocker=mocker)
        assert exit_status == ExitCode.SUCCESS
        return new_path

    def test_two_rebaselines_stack_three_aligned_runs(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        first = self.rebaselined(mocker=mocker, tmp_path=tmp_path, source=recording_path, name='a.jsonl.gz')
        second = self.rebaselined(mocker=mocker, tmp_path=tmp_path, source=first, name='b.jsonl.gz')
        trace = read_trace_result(path=second).trace
        runs = trace[MEASUREMENT_RUNS_HEADER_FIELD]
        assert [run['rebaselined_from'] for run in runs] == [str(first), str(recording_path), None]
        for frame in trace['frames']:
            assert len(frame[CONTENT_HASH_FIELD]) == 3
            assert len(frame[PROCESSING_SECONDS_FIELD]) == 3
            # Unchanged code: every run's hash is the same
            assert len(set(frame[CONTENT_HASH_FIELD])) == 1
        assert recording_content_hash(frames=trace['frames'], run_index=0) == (
            recording_content_hash(frames=trace['frames'], run_index=2)
        )

    def test_a_recording_from_before_histories_starts_one(self, mocker, tmp_path):
        """Today's golden fixtures: no histories and no runs; NEW gets one of each, aligned."""
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)

        def forget_the_history(trace: dict[str, Any]) -> None:
            trace.pop(MEASUREMENT_RUNS_HEADER_FIELD, None)
            for frame in trace['frames']:
                for name in (CONTENT_HASH_FIELD, PROCESSING_SECONDS_FIELD):
                    frame.pop(name, None)

        rewrite_recording(recording_path=recording_path, change=forget_the_history)
        new_path = self.rebaselined(mocker=mocker, tmp_path=tmp_path, source=recording_path, name='a.jsonl.gz')
        trace = read_trace_result(path=new_path).trace
        assert len(trace[MEASUREMENT_RUNS_HEADER_FIELD]) == 1
        assert all(len(frame[CONTENT_HASH_FIELD]) == 1 for frame in trace['frames'])

    def test_depths_tuned_apart_keep_the_indexes_aligned(self, mocker, tmp_path):
        mocker.patch.object(recording_history, 'PROCESSING_SECONDS_HISTORY_DEPTH', 3)
        mocker.patch.object(recording_history, 'CONTENT_HASH_HISTORY_DEPTH', 2)
        mocker.patch.object(recording_history, 'MEASUREMENT_RUNS_HISTORY_DEPTH', 1)
        path = record_session(tmp_path=tmp_path, mocker=mocker)
        for name in ('a.jsonl.gz', 'b.jsonl.gz', 'c.jsonl.gz'):
            path = self.rebaselined(mocker=mocker, tmp_path=tmp_path, source=path, name=name)
        trace = read_trace_result(path=path).trace
        assert len(trace[MEASUREMENT_RUNS_HEADER_FIELD]) == 1
        frame = trace['frames'][0]
        assert len(frame[PROCESSING_SECONDS_FIELD]) == 3
        assert len(frame[CONTENT_HASH_FIELD]) == 2
        # Index 0 is the newest run everywhere
        assert trace[MEASUREMENT_RUNS_HEADER_FIELD][0]['rebaselined_from'] == str(tmp_path / 'b.jsonl.gz')

    def test_changed_behaviour_changes_exactly_the_frames_it_touched(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)

        def move_the_marker() -> None:
            # The current code draws the departure scene's marker elsewhere from this frame on
            scene = SceneManager().active_scene
            assert isinstance(scene, DepartureRecordedScene)
            scene.marker.rect.y = 99

        rebaseline_session(
            recording_path=recording_path,
            new_path=tmp_path / 'changed.jsonl.gz',
            mocker=mocker,
            action=move_the_marker,
            action_frame=ACTION_FRAME,
        )
        frames = read_trace_result(path=tmp_path / 'changed.jsonl.gz').trace['frames']
        changed = [
            index
            for index, frame in enumerate(frames)
            if frame[CONTENT_HASH_FIELD][0] != frame[CONTENT_HASH_FIELD][1]
        ]
        assert changed
        assert changed[0] == ACTION_FRAME

    def test_a_rebaseline_that_ends_early_stacks_only_the_frames_it_ran(self, mocker, tmp_path):
        recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
        new_path = tmp_path / 'short.jsonl.gz'
        rebaseline_session(
            recording_path=recording_path,
            new_path=new_path,
            mocker=mocker,
            action=lambda: SceneManager().quit_game(),
            action_frame=1,
        )
        old_frames = read_trace_result(path=recording_path).trace['frames']
        new_frames = read_trace_result(path=new_path).trace['frames']
        assert len(new_frames) < len(old_frames)
        assert all(len(frame[CONTENT_HASH_FIELD]) == 2 for frame in new_frames)
        assert recording_content_hash(frames=new_frames, run_index=1) != recording_content_hash(
            frames=old_frames
        )
```

(`DepartureRecordedScene`, already imported from `tests.world.test_gameplay_recording`, keeps its
sprite in `self.marker`; the scripted `action` runs in its `dt_tick` on `action_frame`, during
the recording and the rebaseline alike, so here only the rebaseline's run draws the marker at
y = 99.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/world/test_gameplay_replay.py -k "TestRebaselineHistory or TestProcessingComparison" -q --no-cov -n auto`
Expected: FAIL: `KeyError: 'measurement_runs'` / `latest_measurement_run(...) is None`.

- [ ] **Step 3: Implement**

1. In `glitchygames/engine/game_engine.py`, add the run's provenance (the one new raw clock read):

```python
    def measurement_run(
        self: Self, *, processing_paced: bool, rebaselined_from: str | None
    ) -> MeasurementRun:
        """Return this run's provenance for a recording's ``measurement_runs`` (newest first).

        Its ``measured_at`` is the real time now: provenance only, never replayed or served to
        the game (tests/test_engine_doors.py allows this read for that reason).

        Args:
            processing_paced: Whether the run paces its frames (a live run with a target FPS; a
                rebaseline, a headless replay, is not paced).
            rebaselined_from: The recording this run rebaselines, or None for a fresh recording.

        Returns:
            The run.

        """
        return MeasurementRun(
            machine=machine_description(),
            processing_paced=processing_paced,
            engine_version=installed_engine_version(),
            pygame_version=pygame.version.ver,
            python_version=platform.python_version(),
            measured_at=datetime.now(tz=UTC).isoformat(),
            rebaselined_from=rebaselined_from,
            hash_scheme=CONTENT_HASH_SCHEME,
        )
```

   In `trace_recording_header`, replace the `MACHINE_HEADER_FIELD` and
   `PROCESSING_PACED_HEADER_FIELD` entries (and their comments) with:

```python
            # Each run's provenance, newest first (glitchygames/recording_history.py): this one
            # paces its frames when it has a target FPS (0 is uncapped)
            MEASUREMENT_RUNS_HEADER_FIELD: [
                self.measurement_run(
                    processing_paced=self.scene_manager.target_fps > 0, rebaselined_from=None
                ).to_json()
            ],
```

   In `__init__`, pass the rebaseline its run (inside the existing `Rebaseline(...)` call, so no
   statement is added):

```python
            else Rebaseline(
                replay_sources=self.replay_sources,
                source_path=Path(options['replay_trace']),
                destination=Path(rebaseline_path),
                # A headless replay: its frames are not paced
                measurement_run=self.measurement_run(
                    processing_paced=False, rebaselined_from=options['replay_trace']
                ),
            )
```

   Imports: `MeasurementRun`, `MEASUREMENT_RUNS_HEADER_FIELD` and `CONTENT_HASH_SCHEME` from
   `glitchygames.recording_history`; `installed_engine_version` from `glitchygames.replay.driver`
   if not already imported; drop `MACHINE_HEADER_FIELD` and `PROCESSING_PACED_HEADER_FIELD`.

2. In `tests/test_engine_doors.py`, extend the `engine/game_engine.py` entry of
   `ALLOWED_FUNCTION_BYPASSES`:

```python
    # The recording's own start stamp (header recorded_at, the replay wall clock's origin), and
    # each run's measured_at (measurement_runs provenance; never replayed or served)
    'engine/game_engine.py': {
        'trace_recording_header': frozenset({'datetime.datetime.now'}),
        'measurement_run': frozenset({'datetime.datetime.now'}),
    },
```

3. In `glitchygames/replay/rebaseline.py`: `Rebaseline.__init__` takes and keeps
   `measurement_run: MeasurementRun` (documented in its Args), and `start_recording` passes
   `measurement_run=self._measurement_run` to `rebaseline_header`. In `rebaseline_header`, add
   the parameter (documented), delete the `MACHINE_HEADER_FIELD` and
   `PROCESSING_PACED_HEADER_FIELD` lines, and stack the run:

```python
    # Each run's provenance, newest first; NEW's frames stack this run's histories the same way
    # (glitchygames/recording_history.py)
    header[MEASUREMENT_RUNS_HEADER_FIELD] = stacked_measurement_runs(
        newest=measurement_run, previous=original_header.get(MEASUREMENT_RUNS_HEADER_FIELD)
    )
```

   Update the import from `glitchygames.recording` back to
   `from glitchygames.recording import GameplayRecorder, RecordingSources`, drop the
   `machine_description` import, and import `MeasurementRun`, `MEASUREMENT_RUNS_HEADER_FIELD` and
   `stacked_measurement_runs` from `glitchygames.recording_history`. Update the existing unit test
   `test_rebaselined_header_keeps_the_seed_and_names_the_original` to pass a `MeasurementRun`
   (build it as `measurement_run()` does in `tests/test_recording_history.py`).

4. In `glitchygames/replay/driver.py`, read the latest run:

```python
def _recorded_machine(*, header: dict[str, Any]) -> str | None:
    """Return the machine the header's latest run names (``measurement_runs[0]``), or None.

    Returns:
        The machine's description, or None (older recordings name none).

    """
    run = latest_measurement_run(header=header)
    return None if run is None else run.machine


def _recorded_paced(*, header: dict[str, Any]) -> bool | None:
    """Return whether the header's latest run paced its frames, or None when it does not say.

    Returns:
        True or False, or None.

    """
    run = latest_measurement_run(header=header)
    return None if run is None else run.processing_paced
```

   and drop the `MACHINE_HEADER_FIELD` and `PROCESSING_PACED_HEADER_FIELD` imports.

5. In `glitchygames/recording.py`, delete `MACHINE_HEADER_FIELD` and
   `PROCESSING_PACED_HEADER_FIELD` (and their comments).

- [ ] **Step 4: Lint, then run the tests**

Run: `uv run ruff format glitchygames tests && uv run ruff check glitchygames tests && uv run basedpyright glitchygames/engine/game_engine.py glitchygames/replay/rebaseline.py glitchygames/replay/driver.py tests/world/test_gameplay_replay.py tests/test_engine_doors.py`
Expected: no findings (`GameEngine.__init__` and `start` are at their lint limits: the plan adds
no statement or branch to either; if ruff reports one, move the new code into a helper rather
than suppressing).
Run: `uv run pytest -n auto -q -p no:randomly`
Expected: the whole suite passes.

- [ ] **Step 5: Stage for review**

```bash
git add glitchygames/engine/game_engine.py glitchygames/replay/rebaseline.py glitchygames/replay/driver.py glitchygames/recording.py tests/test_engine_doors.py tests/world/test_gameplay_replay.py
```

---

### Task 4: Documentation

**Files:**
- Modify: `glitchygames/recording.py` (module docstring: the frame and header field lists)
- Modify: `glitchygames/replay/processing.py` (module docstring: reads `[0]`; the header's
  `measurement_runs` instead of `machine` and `processing_paced`)
- Modify: `glitchygames/replay/rebaseline.py` (module docstring rule 3: NEW stacks its run)
- Modify: `docs/architecture/gameplay_replay.md` (Recording, Rebaselining, Comparing processing
  time)
- Modify: `CLAUDE.md` (Gameplay Recording and Replay: the format-3 fields, Processing time)
- Modify: `plans/2026-10-20-recording-content-hash-and-history.md` (Status: implemented)
- Modify: `plans/future-work.md` (the item: done; follow-ups: C12 via `recording_content_hash`,
  a git commit per run if the user decides, rebaselining the golden fixtures)

**Interfaces:** none (prose only).

- [ ] **Step 1: Update each file**

Each doc names the three history fields, newest first with the depth constants, the
classification rule (content or measurement, enforced by `frame_content_hash`), the hash
definition (scheme 1: SHA-256 of compact sorted JSON, 64 bits), that the recording-level hash is
derived (`recording_content_hash`, any run), and that `--compare-processing` reads
`processing_seconds[0]` and the latest run's machine and pacing. Remove every mention of the
top-level header fields `machine` and `processing_paced` (grep:
`rg -n "processing_paced|'machine'|MACHINE_HEADER" docs CLAUDE.md glitchygames plans`).

- [ ] **Step 2: Build the docs**

Run: `uv run nox -s lint-docs`
Expected: the strict build succeeds.

- [ ] **Step 3: Stage for review**

```bash
git add glitchygames/recording.py glitchygames/replay/processing.py glitchygames/replay/rebaseline.py docs/architecture/gameplay_replay.md CLAUDE.md plans/2026-10-20-recording-content-hash-and-history.md plans/future-work.md
```

---

### Task 5: Rebaseline the golden fixtures and the bundled demo (needs the user's go-ahead)

Replacing a golden fixture is a reviewed step (CLAUDE.md, Golden replays): ask the user before
starting this task, and do not start it as part of Tasks 1-4.

**Files:**
- Modify: `tests/fixtures/replays/*/golden.jsonl.gz`,
  `glitchygames/examples/paddleslap_demos/rally.jsonl.gz`

- [ ] **Step 1: Rebaseline each recording beside itself, then check it**

For each console script and fixture (`paddleslap`, `clockwork-keep`, `brave-adventurer`,
`brave-adventurer-papyrus`, and `paddleslap` for `rally.jsonl.gz`):

```bash
uv run paddleslap --replay-trace tests/fixtures/replays/paddleslap/golden.jsonl.gz \
    --rebaseline /tmp/paddleslap-golden.jsonl.gz --headless
```

Expected: `Rebaselined N frames to ...: no frames differ` and exit 0. Any other summary stops the
task: report it to the user (the code changed behaviour, which the user reviews first).

- [ ] **Step 2: Replace the fixtures, run the suite**

Copy each new file over its fixture, then run `uv run pytest -n auto -q -p no:randomly` (the
golden replays and the bundled-demo tests replay them). Expected: all pass.

- [ ] **Step 3: Stage for review**

```bash
git add tests/fixtures/replays glitchygames/examples/paddleslap_demos/rally.jsonl.gz
```
