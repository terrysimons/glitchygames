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
    FrameTimeSummary,
    MeasurementRun,
    RunSummary,
    UnclassifiedFrameFieldError,
    add_frame_histories,
    budget_seconds_for,
    completed_summary,
    frame_content_hash,
    frame_time_summary,
    latest_measurement_run,
    recording_content_hash,
    recording_run_summaries,
    run_summary,
    slice_frame_count,
    slice_means,
    stacked_history,
    stacked_measurement_runs,
    summary_lacks_fields,
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


def timed_frames(*, run_times: list[list[object]], dt: float = 1 / 60) -> list[dict[str, Any]]:
    """Frames whose processing_seconds histories are the given lists (newest run first).

    Returns:
        The frames, each in scene ``Game`` except frame 2 (``Pause``).

    """
    return [
        {
            'frame': index,
            'scene': 'Pause' if index == 2 else 'Game',
            'dt': dt,
            PROCESSING_SECONDS_FIELD: history,
        }
        for index, history in enumerate(run_times)
    ]


class TestRunSummaries:
    """A run's processing times at a glance (RunSummary), for tools that should not scan frames."""

    def test_percentiles_worst_frame_and_budget(self):
        # Frame i took (i + 1) ms: 1 ms to 100 ms
        frames = timed_frames(run_times=[[(index + 1) / 1000] for index in range(100)])

        summary = run_summary(frames=frames, run_index=0, budget_seconds=1 / 60, live_run=False)

        assert summary == RunSummary(
            measured_frames=100,
            total_processing_seconds=5.05,
            p50_processing_seconds=0.05,
            p95_processing_seconds=0.095,
            p99_processing_seconds=0.099,
            max_processing_seconds=0.1,
            worst_frame=99,
            worst_frame_scene='Game',
            budget_seconds=1 / 60,
            # 17 ms to 100 ms are over a 16.7 ms budget
            frames_over_budget=84,
            frame_time=None,
            # 5% of 100 frames is 5: (96 + 97 + 98 + 99 + 100) / 5 ms and (1 + 2 + 3 + 4 + 5) / 5
            slowest_5_percent_mean_processing_seconds=0.098,
            fastest_5_percent_mean_processing_seconds=0.003,
        )

    def test_each_run_reads_its_own_index_and_skips_frames_without_a_time(self):
        frames = timed_frames(
            run_times=[[0.001, 0.009], [None, 0.002], [0.003, 0.004], [True], ['slow', 0.001]]
        )

        newest = run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=False)
        older = run_summary(frames=frames, run_index=1, budget_seconds=None, live_run=False)

        assert newest is not None
        assert older is not None
        assert (newest.measured_frames, newest.max_processing_seconds) == (2, 0.003)
        assert (newest.worst_frame, newest.worst_frame_scene) == (2, 'Pause')
        assert (older.measured_frames, older.max_processing_seconds, older.worst_frame) == (
            4,
            0.009,
            0,
        )
        assert newest.frames_over_budget is None

    def test_a_tie_names_the_first_frame_and_a_frame_without_a_scene_names_none(self):
        frames = [
            {'frame': 7, PROCESSING_SECONDS_FIELD: [0.002]},
            {PROCESSING_SECONDS_FIELD: [0.002]},
        ]

        summary = run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=False)

        assert summary is not None
        assert (summary.worst_frame, summary.worst_frame_scene) == (7, None)

    @pytest.mark.parametrize(
        'frames', [[], [{'frame': 0}], [{'frame': 0, PROCESSING_SECONDS_FIELD: 'fast'}]]
    )
    def test_no_times_no_summary(self, frames):
        assert run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=True) is None

    def test_the_live_run_summarises_its_frame_times(self):
        frames = timed_frames(run_times=[[0.001]] * 4, dt=1 / 60)
        frames[3]['dt'] = 0.05

        summary = run_summary(frames=frames, run_index=0, budget_seconds=1 / 60, live_run=True)

        assert summary is not None
        # The mean and slices leave out the first frame: (1/60 + 1/60 + 0.05) / 3
        assert summary.frame_time == FrameTimeSummary(
            p50_seconds=0.016667,
            p99_seconds=0.05,
            max_seconds=0.05,
            late_frames=1,
            mean_seconds=0.027778,
            slowest_5_percent_mean_seconds=0.05,
            fastest_5_percent_mean_seconds=0.016667,
        )

    def test_frame_times_need_a_dt_and_count_late_frames_only_with_a_budget(self):
        no_dt = [{'frame': 0, PROCESSING_SECONDS_FIELD: [0.001], 'dt': True}]
        uncapped = timed_frames(run_times=[[0.001]])

        assert run_summary(frames=no_dt, run_index=0, budget_seconds=None, live_run=True) == (
            run_summary(frames=no_dt, run_index=0, budget_seconds=None, live_run=False)
        )
        summary = run_summary(frames=uncapped, run_index=0, budget_seconds=None, live_run=True)
        assert summary is not None
        assert summary.frame_time is not None
        assert summary.frame_time.late_frames is None

    @pytest.mark.parametrize(
        ('header', 'expected'),
        [
            ({'options': {'target_fps': 60.0}}, 1 / 60),
            ({'options': {'target_fps': 0.0}}, None),
            ({'options': {'target_fps': True}}, None),
            ({'options': 'none'}, None),
            ({}, None),
        ],
    )
    def test_the_budget_comes_from_the_recorded_target_fps(self, header, expected):
        assert budget_seconds_for(header=header) == expected


class TestSummariesWhenRunsStack:
    """Earlier runs get their summaries when the next run stacks (their headers came first)."""

    def test_every_earlier_run_without_one_gets_its_summary(self):
        frames = timed_frames(run_times=[[0.002, 0.001], [0.004, 0.003]])
        stored = {'measured_frames': 1, 'kept': 'as it was'}
        previous = [
            {**measurement_run().to_json(), 'rebaselined_from': 'older.jsonl.gz'},
            {**measurement_run().to_json(), 'summary': stored},
            'unreadable',
        ]

        runs = stacked_measurement_runs(
            newest=measurement_run(),
            previous=previous,
            previous_frame_count=2,
            previous_frames=frames,
            budget_seconds=None,
        )

        assert runs[0]['summary'] is None
        assert runs[1]['summary'] == run_summary(
            frames=frames, run_index=0, budget_seconds=None, live_run=False
        ).model_dump(mode='json')
        assert runs[2]['summary'] == stored
        assert runs[3] == 'unreadable'

    def test_a_run_with_no_times_in_the_frames_gets_none(self):
        runs = stacked_measurement_runs(
            newest=measurement_run(),
            previous=[measurement_run().to_json()],
            previous_frame_count=1,
            previous_frames=[{'frame': 0}],
        )

        assert runs[1]['summary'] is None

    def test_every_runs_summary_is_read_stored_or_computed(self):
        frames = timed_frames(run_times=[[0.002, 0.001]])
        stored = run_summary(frames=frames, run_index=1, budget_seconds=None, live_run=True)
        assert stored is not None
        header = {
            MEASUREMENT_RUNS_HEADER_FIELD: [
                {**measurement_run().to_json(), 'rebaselined_from': 'old.jsonl.gz'},
                {**measurement_run().to_json(), 'summary': stored.model_dump(mode='json')},
                {**measurement_run().to_json(), 'summary': {'not': 'a summary'}},
                'unreadable',
            ]
        }

        summaries = recording_run_summaries(header=header, frames=frames)

        assert summaries == [
            run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=False),
            stored,
            None,
            None,
        ]
        assert recording_run_summaries(header={}, frames=frames) == []

    def test_a_header_from_before_summaries_reads_without_one(self):
        latest = latest_measurement_run(
            header={MEASUREMENT_RUNS_HEADER_FIELD: [measurement_run().to_json()]}
        )

        assert latest is not None
        assert latest.summary is None


class TestSliceMeans:
    """The "5% low" and "5% high" slices (slice_frame_count, the one definition), by hand."""

    @pytest.mark.parametrize(
        ('frame_count', 'expected'),
        [(1, 1), (2, 1), (19, 1), (20, 1), (21, 2), (40, 2), (41, 3), (472, 24), (2072, 104)],
    )
    def test_a_slice_is_five_percent_of_the_frames_rounded_up_and_at_least_one(
        self, frame_count, expected
    ):
        assert slice_frame_count(frame_count=frame_count) == expected

    def test_one_frame_is_both_slices(self):
        assert slice_means(sorted_values=[0.004]) == (0.004, 0.004)

    def test_nineteen_and_twenty_frames_average_one_frame_each(self):
        """ceil(0.95) and ceil(1.0) are both 1: the single slowest and fastest frame."""
        nineteen = [index / 1000 for index in range(1, 20)]
        twenty = [index / 1000 for index in range(1, 21)]

        assert slice_means(sorted_values=nineteen) == (0.019, 0.001)
        assert slice_means(sorted_values=twenty) == (0.020, 0.001)

    def test_twenty_one_frames_average_two_frames_each(self):
        twenty_one = [index / 1000 for index in range(1, 22)]

        slowest, fastest = slice_means(sorted_values=twenty_one)

        # (20 + 21) / 2 ms and (1 + 2) / 2 ms
        assert slowest == pytest.approx(0.0205)
        assert fastest == pytest.approx(0.0015)

    def test_a_one_frame_run_summarises_its_frame_as_both_slices(self):
        frames = timed_frames(run_times=[[0.004]])

        summary = run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=True)

        assert summary is not None
        assert summary.slowest_5_percent_mean_processing_seconds == 0.004
        assert summary.fastest_5_percent_mean_processing_seconds == 0.004
        assert summary.mean_processing_seconds == 0.004
        # Its one frame time is its first: no mean or slices of frame times
        assert summary.frame_time is not None
        assert summary.frame_time.mean_seconds is None
        assert summary.frame_time.slowest_5_percent_mean_seconds is None
        assert summary.frame_time.fastest_5_percent_mean_seconds is None

    def test_pause_frames_count_like_any_other(self):
        """Frame 2 of timed_frames is in the Pause scene; it is the slowest here, and counted."""
        frames = timed_frames(run_times=[[0.001], [0.001], [0.009]])

        summary = run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=False)

        assert summary is not None
        assert summary.slowest_5_percent_mean_processing_seconds == 0.009

    def test_the_first_frame_time_is_left_out_of_the_mean_and_slices_only(self):
        """Its dt runs from the clock's start (about a microsecond), not from a frame before."""
        frames = [{'frame': 0, 'dt': 0.000001}] + [
            {'frame': index, 'dt': index / 1000} for index in range(1, 21)
        ]

        summary = frame_time_summary(frames=frames, budget_seconds=None)

        assert summary is not None
        # 20 frames after the first: one frame per slice, 1 ms to 20 ms, mean 10.5 ms
        assert summary.mean_seconds == 0.0105
        assert summary.slowest_5_percent_mean_seconds == 0.02
        assert summary.fastest_5_percent_mean_seconds == 0.001
        # The percentiles still read every frame: the median of 21 is the 11th, 10 ms
        assert summary.p50_seconds == 0.01

    def test_no_measured_frames_has_no_mean(self):
        summary = run_summary(
            frames=timed_frames(run_times=[[0.001]]),
            run_index=0,
            budget_seconds=None,
            live_run=False,
        )
        assert summary is not None

        assert summary.model_copy(update={'measured_frames': 0}).mean_processing_seconds is None


class TestSummariesFromBeforeTheSliceMeans:
    """Rows and recordings written before the slice means read, and get them when runs stack."""

    def old_summary(self) -> dict[str, Any]:
        """Return a live run's stored summary as written before the slice means (2026-10-28).

        Returns:
            The summary's JSON.

        """
        frames = timed_frames(run_times=[[0.002], [0.001], [0.003]])
        summary = run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=True)
        assert summary is not None
        fields = summary.model_dump(mode='json')
        for name in (
            'slowest_5_percent_mean_processing_seconds',
            'fastest_5_percent_mean_processing_seconds',
        ):
            del fields[name]
        for name in (
            'mean_seconds',
            'slowest_5_percent_mean_seconds',
            'fastest_5_percent_mean_seconds',
        ):
            del fields['frame_time'][name]
        return fields

    def test_an_old_summary_reads_without_the_new_figures(self):
        summary = RunSummary.model_validate(self.old_summary())

        assert summary.slowest_5_percent_mean_processing_seconds is None
        assert summary.fastest_5_percent_mean_processing_seconds is None
        assert summary.frame_time is not None
        assert summary.frame_time.mean_seconds is None
        assert summary_lacks_fields(summary=self.old_summary())

    @pytest.mark.parametrize(
        'summary', ['not a mapping', {'measured_frames': 1}, {'frame_time': None}]
    )
    def test_an_unreadable_summary_lacks_nothing(self, summary):
        """It is left as it is: completing it would not make it readable."""
        assert not summary_lacks_fields(summary=summary)

    def test_a_current_summary_lacks_nothing(self):
        frames = timed_frames(run_times=[[0.002], [0.001]])
        summary = run_summary(frames=frames, run_index=0, budget_seconds=None, live_run=True)
        assert summary is not None

        assert not summary_lacks_fields(summary=summary.model_dump(mode='json'))
        rebaselined = summary.model_copy(update={'frame_time': None})
        assert not summary_lacks_fields(summary=rebaselined.model_dump(mode='json'))

    def test_an_old_summary_gets_the_new_figures_and_keeps_its_own(self):
        frames = timed_frames(run_times=[[0.002, 0.005], [0.001, 0.006], [0.003, 0.007]])
        stored = {**self.old_summary(), 'p50_processing_seconds': 0.123}
        previous = [
            {**measurement_run().to_json(), 'rebaselined_from': 'older.jsonl.gz'},
            {**measurement_run().to_json(), 'summary': stored},
        ]

        runs = stacked_measurement_runs(
            newest=measurement_run(),
            previous=previous,
            previous_frame_count=3,
            previous_frames=frames,
            budget_seconds=None,
        )

        completed = RunSummary.model_validate(runs[2]['summary'])
        # Its stored figures are kept, even one the frames would now give otherwise
        assert completed.p50_processing_seconds == 0.123
        # The new ones come from its own column of the frames' histories (index 1)
        assert completed.slowest_5_percent_mean_processing_seconds == 0.007
        assert completed.fastest_5_percent_mean_processing_seconds == 0.005
        assert completed.frame_time is not None
        assert completed.frame_time.mean_seconds == round(1 / 60, 6)

    def test_a_stored_frame_time_of_none_stays_none(self):
        stored = {**self.old_summary(), 'frame_time': None}
        computed = {**self.old_summary(), 'frame_time': {'mean_seconds': 1.0}}

        assert completed_summary(stored=stored, computed=computed)['frame_time'] is None
