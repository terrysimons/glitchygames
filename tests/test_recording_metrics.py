"""Metrics from recordings' histories (glitchygames/recording_metrics.py).

Design: plans/2026-10-23-recording-metrics-1-frame-performance-history.md (processing
comparisons, the run ledger, the graphs' series) and
plans/2026-10-23-recording-metrics-2-behaviour-change-map.md (behaviour changes).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from glitchygames.build_info import RevisionSource, SourceRevision
from glitchygames.code_tree import LandedCommit
from glitchygames.machine_state import MachineState, PowerSource
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    CONTENT_HASH_SCHEME,
    MEASUREMENT_RUNS_HEADER_FIELD,
    PROCESSING_SECONDS_FIELD,
    MeasurementRun,
    RunSummary,
    recorded_measurement_runs,
    recording_content_hash,
)
from glitchygames.recording_metrics import (
    PROFILE_BUCKET_COUNT,
    BehaviourChange,
    FrameProfile,
    FrameSpan,
    LedgerOrigin,
    LedgerRow,
    SpeedChange,
    behaviour_changes,
    frame_profile,
    frame_spans,
    is_measured,
    landed_rows,
    ledger_rows_from_rebaseline,
    ledger_text,
    machine_label,
    merge_ledgers,
    parse_ledger,
    performance_series,
    processing_comparisons,
    publishable_rows,
    read_row_files,
    row_file_name,
    short_commit,
    write_row_files,
)
from glitchygames.tracing import FRAMES_FIELD, read_trace

# A stand-in project's moved recording, old path -> new ([tool.glitchygames] recording-renames)
STAND_IN_RECORDING_RENAMES = {
    'tests/fixtures/replays/a-game/golden.jsonl.gz': (
        'src/games/a-game/tests/fixtures/replays/golden.jsonl.gz'
    ),
}

# PaddleSlap's golden replay, in its workspace member
GOLDEN_PADDLESLAP = (
    Path(__file__).resolve().parent.parent
    / 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
)
NEWER_COMMIT = 'def5678000000000000000000000000000000000'
OLDER_COMMIT = 'abc1234000000000000000000000000000000000'


def run(
    *,
    commit: str | None = None,
    committed_at: str = '2026-10-23T12:00:00-07:00',
    measured_at: str = '2026-10-23T20:00:00+00:00',
    cpu_model: str | None = 'Apple M4 Max',
    **fields: Any,
) -> MeasurementRun:
    """Return a run's provenance for the tests (``fields``: other MeasurementRun fields).

    Returns:
        The run.

    """
    return MeasurementRun(
        machine='macOS-27.0-arm64-arm-64bit',
        processing_paced=fields.pop('processing_paced', False),
        engine_version='1.0.0',
        pygame_version='2.5.8',
        python_version='3.14.8',
        measured_at=measured_at,
        rebaselined_from=fields.pop(
            'rebaselined_from', 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
        ),
        hash_scheme=CONTENT_HASH_SCHEME,
        source_revision=(
            None
            if commit is None
            else SourceRevision(
                source=RevisionSource.GIT_CHECKOUT,
                commit=commit,
                committed_at=committed_at,
                uncommitted_changes=False,
            )
        ),
        machine_state=MachineState(
            cpu_model=cpu_model,
            logical_cpu_count=16,
            memory_bytes=1 << 30,
            power_source=PowerSource.MAINS,
            thermal_report=None,
            continuous_integration=False,
        ),
        **fields,
    )


def with_uncommitted_changes(measurement_run: MeasurementRun) -> MeasurementRun:
    """Return the run as measured on a checkout with uncommitted changes.

    Returns:
        The run.

    """
    revision = measurement_run.source_revision
    assert revision is not None
    return measurement_run.model_copy(
        update={'source_revision': revision.model_copy(update={'uncommitted_changes': True})}
    )


def frame(
    *, number: int, hashes: list[Any], times: list[Any] | None = None, scene: str = 'Game'
) -> dict[str, Any]:
    """Return a decoded frame with the given histories (newest first).

    Returns:
        The frame.

    """
    record: dict[str, Any] = {'frame': number, 'dt': 0.016, 'scene': scene}
    record[CONTENT_HASH_FIELD] = hashes
    if times is not None:
        record[PROCESSING_SECONDS_FIELD] = times
    return record


def header(*runs: MeasurementRun | object) -> dict[str, Any]:
    """Return a header holding the runs (newest first) and a 60 FPS target.

    Returns:
        The header fields.

    """
    return {
        'options': {'target_fps': 60.0},
        MEASUREMENT_RUNS_HEADER_FIELD: [
            entry.to_json() if isinstance(entry, MeasurementRun) else entry for entry in runs
        ],
    }


class TestReadingRuns:
    """Every run a header names is read leniently, its index kept."""

    def test_unreadable_entries_keep_their_place_and_unknown_fields_are_dropped(self):
        newest = {**run(commit=NEWER_COMMIT).to_json(), 'from_the_future': 1}
        runs = recorded_measurement_runs(header=header(newest, 'not a run', {'machine': 3}))
        assert runs[0] == run(commit=NEWER_COMMIT)
        assert runs[1:] == [None, None]

    def test_a_header_without_runs_has_none(self):
        assert recorded_measurement_runs(header={MEASUREMENT_RUNS_HEADER_FIELD: 'no'}) == []

    def test_short_commit_and_machine_label(self):
        assert short_commit(run=run(commit=NEWER_COMMIT)) == 'def5678'
        assert short_commit(run=run()) is None
        assert short_commit(run=None) is None
        assert machine_label(run=run()) == 'Apple M4 Max'
        assert machine_label(run=run(cpu_model=None)) == 'macOS-27.0-arm64-arm-64bit'


class TestFrameSpans:
    """Frames are grouped into spans of neighbours, at most a gap apart."""

    def test_neighbours_join_and_a_wider_gap_splits(self):
        frames = [frame(number=number, hashes=[], scene=f'S{number}') for number in range(10)]
        spans = frame_spans(frames=frames, positions=[1, 2, 3, 7, 9], gap_frames=1)
        assert spans == [
            FrameSpan(first_frame=1, last_frame=3, frame_count=3, first_scene='S1'),
            FrameSpan(first_frame=7, last_frame=9, frame_count=2, first_scene='S7'),
        ]
        assert spans[0].describe() == 'frames 1-3 (scene S1)'

    def test_a_single_frame_and_a_frame_without_scene_or_number(self):
        spans = frame_spans(frames=[{'scene': None}], positions=[0], gap_frames=0)
        assert spans == [FrameSpan(first_frame=0, last_frame=0, frame_count=1, first_scene=None)]
        assert spans[0].describe() == 'frame 0'

    def test_no_positions_no_spans(self):
        assert frame_spans(frames=[], positions=[], gap_frames=0) == []


class TestBehaviourChanges:
    """Adjacent runs' content hashes differ in spans of frames: the behaviour-change map."""

    def test_changed_frames_are_spans_with_the_first_scene_and_both_commits(self):
        frames = [
            frame(number=0, hashes=['a', 'a', 'a']),
            frame(number=1, hashes=['b', 'x', 'x'], scene='Pause'),
            frame(number=2, hashes=['c', 'y', 'y']),
            frame(number=3, hashes=['d', 'd', 'z']),
            frame(number=4, hashes=['e', 'w', 'w']),
            frame(number=5, hashes=['f']),
        ]
        changes = behaviour_changes(
            header=header(run(commit=NEWER_COMMIT), run(commit=OLDER_COMMIT), run()),
            frames=frames,
        )
        newest = changes[0]
        assert (newest.newer_run, newest.older_run) == (0, 1)
        assert (newest.frames_compared, newest.frames_changed, newest.frames_unknown) == (5, 3, 1)
        assert [span.describe() for span in newest.spans] == [
            'frames 1-2 (scene Pause)',
            'frame 4 (scene Game)',
        ]
        assert newest.describe() == (
            'run 1 -> run 0 (abc1234 -> def5678): behaviour changed in frames 1-2 (scene Pause), '
            '2 spans, 3 frames'
        )
        older = changes[1]
        assert (older.frames_changed, older.frames_unknown) == (1, 1)
        assert older.describe() == (
            'run 2 -> run 1 (commit unknown -> abc1234): behaviour changed in frame 3 '
            '(scene Game), 1 span, 1 frame'
        )

    def test_unchanged_runs_say_so_and_a_single_run_has_no_pairs(self):
        frames = [frame(number=0, hashes=['a', 'a'])]
        unchanged = behaviour_changes(header=header(run(), run()), frames=frames)
        assert unchanged == [
            BehaviourChange(
                newer_run=0,
                older_run=1,
                newer_commit=None,
                older_commit=None,
                frames_compared=1,
                frames_changed=0,
                frames_unknown=0,
                spans=(),
            )
        ]
        assert unchanged[0].describe() == (
            'run 1 -> run 0 (commit unknown -> commit unknown): no behaviour change in 1 frame'
        )
        assert behaviour_changes(header=header(run()), frames=[frame(number=0, hashes=['a'])]) == []

    def test_hashes_deeper_than_the_runs_still_pair_and_non_strings_are_unknown(self):
        frames = [frame(number=0, hashes=['a', 7]), {'frame': 1, CONTENT_HASH_FIELD: 'bad'}]
        (change,) = behaviour_changes(header={}, frames=frames)
        assert (change.frames_compared, change.frames_unknown) == (0, 2)


class TestProcessingComparisons:
    """Same-work frames that got slower or faster between adjacent runs, by span."""

    def test_slower_and_faster_spans_and_different_work(self):
        slow = [0.004, 0.001]
        fast = [0.001, 0.004]
        same = [0.001, 0.001]
        frames = [
            frame(number=0, hashes=['a', 'a'], times=same),
            *(frame(number=number, hashes=['a', 'a'], times=slow) for number in range(1, 5)),
            frame(number=5, hashes=['a', 'a'], times=same),
            *(frame(number=number, hashes=['a', 'a'], times=fast) for number in range(6, 9)),
            # One slower frame alone: counted, but too short to list
            frame(number=20, hashes=['a', 'a'], times=slow),
            # Different work is never a speed change
            frame(number=21, hashes=['b', 'a'], times=slow),
            # Unmeasured in one run
            frame(number=22, hashes=['a', 'a'], times=[None, 0.001]),
            frame(number=23, hashes=['a', 'a'], times=[0.001]),
            # No hash for the older run: neither same nor different work
            frame(number=24, hashes=['a'], times=[0.001, 0.001]),
        ]
        (comparison,) = processing_comparisons(
            header=header(run(commit=NEWER_COMMIT), run(commit=OLDER_COMMIT)), frames=frames
        )
        assert comparison.frames_same_work == 10
        assert comparison.frames_different_work == 1
        assert comparison.frames_unmeasured == 3
        assert (comparison.frames_slower, comparison.frames_faster) == (5, 3)
        assert comparison.short_spans == 1
        assert [(span.direction, span.span.first_frame) for span in comparison.spans] == [
            (SpeedChange.SLOWER, 1),
            (SpeedChange.FASTER, 6),
        ]
        assert comparison.spans[0].describe() == (
            'frames 1-4 (scene Game): slower, 4.000 ms -> 16.000 ms (+300.0%)'
        )
        assert comparison.spans[1].describe() == (
            'frames 6-8 (scene Game): faster, 12.000 ms -> 3.000 ms (-75.0%)'
        )
        assert comparison.describe() == (
            'run 1 -> run 0 (abc1234 -> def5678): 10 frames of the same work took 19.000 ms -> '
            '25.000 ms (+31.6%); 5 slower, 3 faster (1 span too short to list); '
            '1 frame different work; 3 frames unmeasured'
        )

    def test_changes_below_the_minimum_seconds_are_noise(self):
        frames = [
            frame(number=number, hashes=['a', 'a'], times=[0.00002, 0.00001]) for number in range(5)
        ]
        (comparison,) = processing_comparisons(header=header(run(), run()), frames=frames)
        assert (comparison.frames_slower, comparison.spans) == (0, ())
        assert comparison.describe() == (
            'run 1 -> run 0 (commit unknown -> commit unknown): 5 frames of the same work took '
            '0.050 ms -> 0.100 ms (+100.0%); 0 slower, 0 faster'
        )

    def test_no_same_work_has_no_ratio(self):
        frames = [frame(number=0, hashes=['b', 'a'], times=[0.001, 0.001])]
        (comparison,) = processing_comparisons(header=header(run(), run()), frames=frames)
        assert comparison.describe() == (
            'run 1 -> run 0 (commit unknown -> commit unknown): no frames of the same work; '
            '1 frame different work'
        )


def ledger_row(
    *,
    recording: str = 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz',
    commit: str | None = NEWER_COMMIT,
    committed_at: str = '2026-10-23T12:00:00-07:00',
    measured_at: str = '2026-10-23T20:00:00+00:00',
    p50: float = 0.0001,
) -> LedgerRow:
    """Return a ledger row for the tests (a summary with the given median).

    Returns:
        The row.

    """
    return LedgerRow(
        recording=recording,
        console_script='paddleslap',
        origin=LedgerOrigin.REPLAY_METRICS,
        run=run(commit=commit, committed_at=committed_at, measured_at=measured_at),
        summary=RunSummary(
            measured_frames=10,
            total_processing_seconds=p50 * 10,
            p50_processing_seconds=p50,
            p95_processing_seconds=p50,
            p99_processing_seconds=p50 * 2,
            max_processing_seconds=p50 * 3,
            worst_frame=4,
            worst_frame_scene='Game',
            budget_seconds=1 / 60,
            frames_over_budget=0,
            frame_time=None,
        ),
        content_hash='0123456789abcdef',
        frame_count=10,
        frames_changed=0,
        rebaseline_exit='SUCCESS (0)',
        allowed_uncommitted_changes=False,
    )


class TestTheLedger:
    """Ledger rows: keyed, read leniently, merged without duplicates, in commit order."""

    def test_the_key_names_the_recording_the_measurement_and_the_machine(self):
        row = ledger_row()
        assert row.key == (
            'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz|2026-10-23T20:00:00+00:00|'
            'macOS-27.0-arm64-arm-64bit'
        )
        assert row.commit == NEWER_COMMIT
        assert row.machine == 'Apple M4 Max'
        assert ledger_row(commit=None).commit is None

    def test_text_round_trips_and_unreadable_lines_are_counted(self):
        rows = [ledger_row(), ledger_row(measured_at='2026-10-24T20:00:00+00:00')]
        text = ledger_text(rows=rows)
        assert text.endswith('\n')
        parsed = parse_ledger(text=f'{text}\nnot json\n{json.dumps({"recording": 1})}\n[]\n')
        assert parsed.rows == tuple(rows)
        assert parsed.unreadable_lines == 3
        assert not ledger_text(rows=[])

    def test_merging_keeps_the_first_of_each_key_in_commit_then_measurement_order(self):
        older = ledger_row(
            commit=OLDER_COMMIT,
            committed_at='2026-10-22T23:00:00-07:00',
            measured_at='2026-10-24T09:00:00+00:00',
        )
        # Committed later, in an earlier offset: 2026-10-23T06:30Z, after the older's 06:00Z
        newer = ledger_row(committed_at='2026-10-23T08:30:00+02:00', p50=0.002)
        duplicate = ledger_row(committed_at='2026-10-23T08:30:00+02:00', p50=0.009)
        unknown = ledger_row(commit=None, measured_at='2026-10-01T00:00:00+00:00')
        merged = merge_ledgers(ledgers=[[newer], [older, duplicate, unknown]])
        assert merged == [unknown, older, newer]

    def test_an_unreadable_time_sorts_first_and_a_time_without_offset_is_utc(self):
        unreadable = ledger_row(committed_at='yesterday')
        naive = ledger_row(committed_at='2026-10-23T05:00:00', measured_at='2026-10-23T21:00:00')
        aware = ledger_row(committed_at='2026-10-23T05:30:00+00:00', measured_at='later')
        assert merge_ledgers(ledgers=[[aware, naive, unreadable]]) == [unreadable, naive, aware]

    def test_measured_means_same_recording_commit_and_machine_from_replay_metrics(self):
        rows = [
            ledger_row(),
            ledger_row(recording='other').model_copy(update={'origin': LedgerOrigin.RECORDING}),
        ]
        recording = 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
        assert is_measured(
            rows=rows, recording=recording, commit=NEWER_COMMIT, machine='Apple M4 Max'
        )
        assert not is_measured(
            rows=rows, recording=recording, commit=OLDER_COMMIT, machine='Apple M4 Max'
        )
        assert not is_measured(rows=rows, recording=recording, commit=NEWER_COMMIT, machine='Other')
        assert not is_measured(
            rows=rows, recording='other', commit=NEWER_COMMIT, machine='Apple M4 Max'
        )
        # A trial on a changed checkout never stands for its commit
        trial = ledger_row().model_copy(update={'allowed_uncommitted_changes': True})
        assert not is_measured(
            rows=[trial], recording=recording, commit=NEWER_COMMIT, machine='Apple M4 Max'
        )
        changed = ledger_row().model_copy(
            update={'run': with_uncommitted_changes(run(commit=NEWER_COMMIT))}
        )
        assert changed.measured_uncommitted_changes
        assert not ledger_row(commit=None).measured_uncommitted_changes


class TestRowsFromARebaseline:
    """A rebaselined recording gives its measurement's row and one row per run it held."""

    def test_rows_from_a_real_golden_replay(self):
        trace = read_trace(path=GOLDEN_PADDLESLAP)
        frames = trace['frames']
        # As a rebaseline stacks it: one more run in front, the frames' hashes stacked too
        rebaselined_frames = [
            {
                **recorded,
                CONTENT_HASH_FIELD: [
                    recorded[CONTENT_HASH_FIELD][0],
                    *recorded[CONTENT_HASH_FIELD],
                ],
                PROCESSING_SECONDS_FIELD: [0.0005, *recorded[PROCESSING_SECONDS_FIELD]],
            }
            for recorded in frames
        ]
        rebaselined_header = {
            **trace,
            MEASUREMENT_RUNS_HEADER_FIELD: [
                with_uncommitted_changes(run(commit=NEWER_COMMIT)).to_json(),
                # A rebaseline fills in the run before's frame count as it stacks
                {**trace[MEASUREMENT_RUNS_HEADER_FIELD][0], 'frame_count': len(frames)},
                *trace[MEASUREMENT_RUNS_HEADER_FIELD][1:],
            ],
        }
        rows = ledger_rows_from_rebaseline(
            recording='src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz',
            console_script='paddleslap',
            trace={**rebaselined_header, FRAMES_FIELD: rebaselined_frames},
            rebaseline_exit='SUCCESS (0)',
            allowed_uncommitted_changes=True,
        )
        measured, recorded, *older_recorded = rows
        assert len(older_recorded) + 1 == len(trace[MEASUREMENT_RUNS_HEADER_FIELD])
        assert measured.origin == LedgerOrigin.REPLAY_METRICS
        assert measured.frame_count == len(frames)
        assert measured.frames_changed == 0
        assert measured.summary is not None
        assert measured.summary.p50_processing_seconds == pytest.approx(0.0005)
        assert measured.content_hash == recording_content_hash(frames=frames)
        assert measured.allowed_uncommitted_changes
        assert recorded.origin == LedgerOrigin.RECORDING
        assert recorded.rebaseline_exit is None
        assert recorded.frames_changed is None
        assert recorded.content_hash == measured.content_hash
        # The golden's oldest run was live: its frame times are summarised
        live_run = older_recorded[-1]
        assert live_run.summary is not None
        assert live_run.summary.frame_time is not None
        assert recorded.frame_count == len(frames)
        # Only the measurement carries a per-frame profile (its own run's times)
        assert measured.profile is not None
        assert measured.profile.frame_count == len(frames)
        assert measured.profile.max_microseconds[0] == 500
        assert recorded.profile is None

    def test_an_unreadable_run_gives_no_row(self):
        frames = [frame(number=0, hashes=['a', 'a'], times=[0.001, 0.001])]
        rows = ledger_rows_from_rebaseline(
            recording='r',
            console_script='paddleslap',
            trace={**header(run(commit=NEWER_COMMIT), 'unreadable'), FRAMES_FIELD: frames},
            rebaseline_exit='SUCCESS (0)',
            allowed_uncommitted_changes=False,
        )
        assert [row.origin for row in rows] == [LedgerOrigin.REPLAY_METRICS]

    def test_a_recording_without_runs_gives_no_rows(self):
        rows = ledger_rows_from_rebaseline(
            recording='r',
            console_script='paddleslap',
            trace={FRAMES_FIELD: []},
            rebaseline_exit='SUCCESS (0)',
            allowed_uncommitted_changes=False,
        )
        assert rows == []


class TestPerformanceSeries:
    """The graphs' series: per recording, machine and pacing, the latest row of each commit."""

    def test_series_group_order_and_keep_the_latest_measurement_per_commit(self):
        older = ledger_row(commit=OLDER_COMMIT, committed_at='2026-10-22T12:00:00-07:00')
        first = ledger_row(measured_at='2026-10-23T20:00:00+00:00', p50=0.001)
        remeasured = ledger_row(measured_at='2026-10-23T21:00:00+00:00', p50=0.002)
        other_machine = ledger_row(p50=0.003).model_copy(
            update={'run': run(commit=NEWER_COMMIT, cpu_model='Intel')}
        )
        other_recording = ledger_row(
            recording='src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
        )
        no_commit = ledger_row(commit=None)
        series = performance_series(
            rows=[remeasured, first, older, other_machine, other_recording, no_commit],
            recording_renames={},
        )
        assert [(entry.recording, entry.machine, entry.paced) for entry in series] == [
            ('src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz', 'Apple M4 Max', False),
            ('src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz', 'Apple M4 Max', False),
            ('src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz', 'Intel', False),
        ]
        assert series[1].rows == (older, remeasured)
        assert series[1].label == 'Apple M4 Max, unpaced replay'

    def test_a_recording_that_moved_keeps_one_series(self):
        """Rows from before a move (old path) and after (new path) are one series, new path."""
        old_path, new_path = next(iter(STAND_IN_RECORDING_RENAMES.items()))
        before = ledger_row(
            commit=OLDER_COMMIT, committed_at='2026-10-22T12:00:00-07:00', recording=old_path
        )
        after = ledger_row(recording=new_path)

        (moved,) = performance_series(
            rows=[before, after], recording_renames=STAND_IN_RECORDING_RENAMES
        )
        (only_old,) = performance_series(
            rows=[before], recording_renames=STAND_IN_RECORDING_RENAMES
        )

        assert moved.recording == new_path
        assert [row.recording for row in moved.rows] == [old_path, new_path]
        assert only_old.recording == new_path

    def test_rows_without_a_summary_are_left_out_and_paced_runs_are_their_own_series(self):
        unsummarised = ledger_row().model_copy(update={'summary': None})
        paced = ledger_row().model_copy(
            update={'run': run(commit=NEWER_COMMIT, processing_paced=True)}
        )
        (series,) = performance_series(rows=[unsummarised, paced], recording_renames={})
        assert series.paced
        assert series.label == 'Apple M4 Max, paced live run'


class TestFrameProfiles:
    """A run's per-frame times, bucketed: each bucket's slowest frame, in whole microseconds."""

    def test_a_long_recording_is_cut_into_the_bucket_count(self):
        frames = [
            frame(number=number, hashes=['a'], times=[number / 1_000_000], scene=scene)
            for number, scene in zip(range(250), ['Title'] * 30 + ['Game'] * 220, strict=True)
        ]
        profile = frame_profile(frames=frames, run_index=0)
        assert profile is not None
        assert len(profile.max_microseconds) == PROFILE_BUCKET_COUNT
        # Bucket 0 holds frames 0-1 (250 frames in 100 buckets), bucket 99 frames 247-249
        assert profile.bucket_frames(bucket=0) == (0, 1)
        assert profile.bucket_frames(bucket=99) == (247, 249)
        assert profile.max_microseconds[0] == 1
        assert profile.max_microseconds[99] == 249
        assert profile.scene_runs == ((0, 'Title'), (12, 'Game'))
        assert profile.bucket_scene(bucket=11) == 'Title'
        assert profile.bucket_scene(bucket=50) == 'Game'
        # Well under a kilobyte of JSON per row
        assert len(profile.model_dump_json()) < 1000

    def test_a_short_recording_keeps_a_bucket_per_frame_and_gaps_stay_empty(self):
        frames = [
            frame(number=0, hashes=['a'], times=[0.0000014], scene='Game'),
            frame(number=1, hashes=['a'], times=[None]),
            {'frame': 2, PROCESSING_SECONDS_FIELD: [0.003]},
        ]
        profile = frame_profile(frames=frames, run_index=0)
        assert profile == FrameProfile(
            frame_count=3, max_microseconds=(1, None, 3000), scene_runs=((0, 'Game'), (2, None))
        )
        assert profile.bucket_frames(bucket=1) == (1, 1)

    def test_no_times_no_profile(self):
        frames = [frame(number=0, hashes=['a'], times=[None, 0.001])]
        assert frame_profile(frames=frames, run_index=0) is None
        assert frame_profile(frames=[], run_index=0) is None
        # Another run's times
        assert frame_profile(frames=frames, run_index=1) is not None

    def test_old_rows_without_a_profile_still_parse(self):
        row = ledger_row()
        old_fields = row.model_dump(mode='json')
        del old_fields['profile']
        (parsed,) = parse_ledger(text=json.dumps(old_fields)).rows
        assert parsed.profile is None


class TestPublishing:
    """Rows from a checkout with uncommitted changes are never published, only built locally."""

    def test_trials_and_changed_checkouts_are_left_out(self):
        clean = ledger_row()
        trial = ledger_row(measured_at='2026-10-24T01:00:00+00:00').model_copy(
            update={'allowed_uncommitted_changes': True}
        )
        changed_run = ledger_row(measured_at='2026-10-24T02:00:00+00:00').model_copy(
            update={'run': with_uncommitted_changes(run(commit=NEWER_COMMIT))}
        )
        assert not clean.from_uncommitted_changes
        assert trial.from_uncommitted_changes
        assert changed_run.from_uncommitted_changes
        assert publishable_rows(rows=[clean, trial, changed_run]) == [clean]


TREE = '0123456789abcdef0123456789abcdef01234567'


class TestRowFiles:
    """Measured rows as tracked files (quality/replay-ledger/): one file per row, never edited."""

    def test_a_row_round_trips_through_its_file(self, tmp_path):
        row = ledger_row().model_copy(update={'code_tree': TREE})

        (path,) = write_row_files(rows=[row], directory=tmp_path)

        assert path.parent == tmp_path
        assert read_row_files(directory=tmp_path) == [row]

    def test_file_names_differ_by_recording_machine_and_time(self):
        rows = [
            ledger_row(),
            ledger_row(measured_at='2026-10-23T21:00:00+00:00'),
            ledger_row(recording='tests/fixtures/replays/mr-muncher/golden.jsonl.gz'),
        ]

        names = {row_file_name(row=row) for row in rows}

        assert len(names) == len(rows)
        assert all(name.endswith('.json') and '/' not in name for name in names)

    def test_the_code_tree_leads_the_file_name(self):
        """Rows of one measured code sort together."""
        row = ledger_row().model_copy(update={'code_tree': TREE})

        assert row_file_name(row=row).startswith(TREE[:12])

    def test_the_file_names_the_machine_by_its_label(self):
        """The machine label the metrics show (e.g. Apple M4 Max), not the platform string."""
        row = ledger_row()
        label = row.machine.lower().replace(' ', '-')

        assert f'-{label}-' in row_file_name(row=row)

    def test_reading_returns_every_row_in_name_order(self, tmp_path):
        rows = [ledger_row(measured_at=f'2026-10-23T2{hour}:00:00+00:00') for hour in (3, 1, 2)]
        write_row_files(rows=rows, directory=tmp_path)

        assert [row.run.measured_at for row in read_row_files(directory=tmp_path)] == [
            '2026-10-23T21:00:00+00:00',
            '2026-10-23T22:00:00+00:00',
            '2026-10-23T23:00:00+00:00',
        ]

    def test_a_missing_directory_has_no_rows(self, tmp_path):
        assert read_row_files(directory=tmp_path / 'none') == []

    def test_a_row_written_before_code_trees_still_reads(self):
        """Published history rows have no code_tree."""
        legacy = ledger_row().model_dump(mode='json')
        legacy.pop('code_tree', None)

        assert LedgerRow.model_validate(legacy).code_tree is None

    def test_a_row_naming_its_code_tree_measured_that_code_exactly(self):
        """The hook measures staged (uncommitted) code, but the tree says exactly which."""
        row = ledger_row().model_copy(
            update={'code_tree': TREE, 'allowed_uncommitted_changes': True}
        )

        assert not row.from_uncommitted_changes


class TestLandedRows:
    """Published rows are those whose measured code landed on main, labelled with its commit."""

    LANDED_TREE = '1111111111111111111111111111111111111111'
    UNLANDED_TREE = '2222222222222222222222222222222222222222'
    LANDED_COMMIT = 'abc0000000000000000000000000000000000000'

    def landed(self) -> dict[str, LandedCommit]:
        """Return one landed tree (the squash commit's)."""
        return {
            self.LANDED_TREE: LandedCommit(
                commit=self.LANDED_COMMIT, committed_at='2026-10-25T10:00:00-07:00'
            )
        }

    def test_a_landed_row_is_labelled_with_the_commit_it_landed_in(self):
        row = ledger_row().model_copy(
            update={'code_tree': self.LANDED_TREE, 'allowed_uncommitted_changes': True}
        )

        (published,) = landed_rows(rows=[row], landed=self.landed(), keep_unlanded=False)

        assert published.commit == self.LANDED_COMMIT
        assert published.run.source_revision is not None
        assert published.run.source_revision.committed_at == '2026-10-25T10:00:00-07:00'
        assert published.run.source_revision.uncommitted_changes is False

    def test_an_unlanded_row_is_left_out_of_a_published_build(self):
        """An intermediate commit's, or a branch's that never merged."""
        row = ledger_row().model_copy(update={'code_tree': self.UNLANDED_TREE})

        assert landed_rows(rows=[row], landed=self.landed(), keep_unlanded=False) == []

    def test_a_local_build_keeps_unlanded_rows_as_they_are(self):
        """So a branch's measurements show before it merges."""
        row = ledger_row().model_copy(update={'code_tree': self.UNLANDED_TREE})

        assert landed_rows(rows=[row], landed=self.landed(), keep_unlanded=True) == [row]

    def test_rows_without_a_code_tree_pass_through(self):
        """The history measured before rows named their code tree."""
        row = ledger_row()

        assert landed_rows(rows=[row], landed=self.landed(), keep_unlanded=False) == [row]
