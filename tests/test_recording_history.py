"""Content hashes and measurement history of recorded frames (glitchygames/recording_history.py)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from glitchygames import recording_history
from glitchygames.recording import RecordedFrameFields
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
from glitchygames.timing import PacingTimer, SleepModel

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
        """Derived from what recorders write, so a new frame field fails here, at test time.

        ``recorded_frame`` (glitchygames/recording.py) writes the sampled frame (frame, scene,
        sprites), dt and the event batches, then the ``RecordedFrameFields``; the recorder adds
        the measurements.
        """
        written_fields = {
            'frame',
            'scene',
            'sprites',
            'dt',
            'event_batches',
            *RecordedFrameFields.__required_keys__,
            *RecordedFrameFields.__optional_keys__,
        }
        assert set(FrameContent.model_fields) == written_fields
        measurement_fields = recording_history.MEASUREMENT_FRAME_FIELDS
        assert measurement_fields == {PROCESSING_SECONDS_FIELD, CONTENT_HASH_FIELD}
        assert not measurement_fields & written_fields


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
        [
            [{}],
            [{CONTENT_HASH_FIELD: []}],
            [{CONTENT_HASH_FIELD: [None]}],
            [{CONTENT_HASH_FIELD: 'aa'}],
        ],
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
        frame: dict[str, Any] = dict(FRAME)
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
        frame: dict[str, Any] = dict(FRAME)
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
        runs = stacked_measurement_runs(
            newest=newest, previous=[second, first], previous_frame_count=7
        )
        assert runs == [newest.to_json(), {**second, 'frame_count': 7}]

    def test_the_latest_run_is_read_from_the_front(self):
        newest = measurement_run(measured_at='2026-10-21T03:00:00+00:00')
        header = {MEASUREMENT_RUNS_HEADER_FIELD: [newest.to_json(), measurement_run().to_json()]}
        assert latest_measurement_run(header=header) == newest

    @pytest.mark.parametrize(
        'header',
        [
            {},
            {MEASUREMENT_RUNS_HEADER_FIELD: []},
            {MEASUREMENT_RUNS_HEADER_FIELD: [{'machine': 1}]},
        ],
        ids=['none', 'empty', 'malformed'],
    )
    def test_a_header_without_a_readable_run_has_no_latest(self, header):
        assert latest_measurement_run(header=header) is None

    def test_a_newer_run_with_more_fields_is_still_read(self):
        """A future field (the undecided git commit) must not make today's reader drop the run."""
        newest = measurement_run()
        header = {MEASUREMENT_RUNS_HEADER_FIELD: [{**newest.to_json(), 'git_commit': 'abc123'}]}
        assert latest_measurement_run(header=header) == newest

    def test_a_run_from_before_the_pacing_timer_reads_as_naming_none(self):
        """Recordings made before pacing_timer existed: their runs read with it None."""
        newest = measurement_run()
        stored = newest.to_json()
        del stored['pacing_timer']
        run = latest_measurement_run(header={MEASUREMENT_RUNS_HEADER_FIELD: [stored]})
        assert run is not None
        assert run.pacing_timer is None

    def test_a_paced_run_stores_its_pacing_timer(self):
        """The timer a paced run used is written with it, and reads back as it was."""
        pacing = PacingTimer(
            backend='fast',
            sleep_granularity_ns=1_000_000,
            sleep_model=SleepModel(constant_ns=0, fraction=0.25),
        )
        paced = measurement_run().model_copy(
            update={'processing_paced': True, 'pacing_timer': pacing}
        )
        header = {MEASUREMENT_RUNS_HEADER_FIELD: [paced.to_json()]}
        run = latest_measurement_run(header=header)
        assert run is not None
        assert run.pacing_timer == pacing

    def test_the_run_before_gets_the_frame_count_of_its_recording(self):
        """Known only once the next run reads it: the newest run's count is its file's."""
        older = measurement_run(measured_at='2026-10-21T01:00:00+00:00').to_json()
        runs = stacked_measurement_runs(
            newest=measurement_run(), previous=[older], previous_frame_count=600
        )
        assert runs[0]['frame_count'] is None
        assert runs[1]['frame_count'] == 600
        assert {**runs[1], 'frame_count': None} == older

    def test_a_run_is_read_only_and_closed(self):
        with pytest.raises(ValueError, match='Extra inputs'):
            MeasurementRun.model_validate({**measurement_run().to_json(), 'extra': 1})
