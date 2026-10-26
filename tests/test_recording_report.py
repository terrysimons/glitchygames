"""scripts/recording_report.py reports a recording's runs, speed changes and behaviour changes.

Design: plans/2026-10-23-recording-metrics-2-behaviour-change-map.md. The real recording is the
PaddleSlap golden replay rebaselined twice through its console script (two runs stacked on the
runs it already holds), so its two newest runs are of the same work; the behaviour change is a
hand-built recording written with the trace writer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from scripts.recording_report import report_lines, run

from glitchygames.exit_codes import ExitCode
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    CONTENT_HASH_SCHEME,
    MEASUREMENT_RUNS_HEADER_FIELD,
    PROCESSING_SECONDS_FIELD,
    MeasurementRun,
)
from glitchygames.testing.replays import rebaseline_recording_headless
from glitchygames.tracing import FRAMES_FIELD, read_trace, write_trace
from tests.replay.test_replay_plugin import REPO_FIXTURE

if TYPE_CHECKING:
    from pathlib import Path


def rebaselined_twice(*, tmp_path: Path) -> Path:
    """Rebaseline the PaddleSlap golden replay, then the result again.

    Returns:
        The second rebaseline's recording (the golden's runs plus two).

    """
    first = tmp_path / 'first.jsonl.gz'
    second = tmp_path / 'second.jsonl.gz'
    for source, target in ((REPO_FIXTURE, first), (first, second)):
        completed = rebaseline_recording_headless(
            console_script='paddleslap', path=source, new_path=target
        )
        assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    return second


def test_a_real_recording_reports_every_run_and_no_behaviour_change(tmp_path, capsys):
    """Two new runs of the same work: provenance, summaries, no change in behaviour."""
    path = rebaselined_twice(tmp_path=tmp_path)
    golden_header = read_trace(path=REPO_FIXTURE)[MEASUREMENT_RUNS_HEADER_FIELD]
    golden_runs = len(golden_header)
    golden_rebaselines = sum(
        1 for golden_run in golden_header if golden_run.get('rebaselined_from')
    )
    golden_frames = read_trace(path=REPO_FIXTURE)[FRAMES_FIELD]
    golden_unchanged_pairs = sum(
        1
        for newer_index in range(golden_runs - 1)
        if all(
            frame[CONTENT_HASH_FIELD][newer_index] == frame[CONTENT_HASH_FIELD][newer_index + 1]
            for frame in golden_frames
        )
    )

    assert run(arguments=[str(path)]) == ExitCode.SUCCESS

    output = capsys.readouterr().out
    frame_count = len(read_trace(path=path)[FRAMES_FIELD])
    assert f'{path}: {frame_count} frames, {golden_runs + 2} runs' in output
    # The rebaselines know their commit (this checkout); the golden's oldest run predates that
    assert output.count('rebaselined from') == 2 + golden_rebaselines
    assert f'run {golden_runs + 1}: commit unknown' in output
    assert 'paced live run' in output
    assert 'frame time p50' in output
    assert 'processing p50' in output
    assert 'Behaviour changes (content hash, adjacent runs):' in output
    assert output.count('no behaviour change in') == 2 + golden_unchanged_pairs
    assert 'Processing (same work only' in output


def hand_built_recording(*, path: Path) -> None:
    """Write a recording whose newest run changed frames 2-3 and made frames 4-8 slower."""
    runs = [
        MeasurementRun(
            machine='macOS-27.0-arm64-arm-64bit',
            processing_paced=False,
            engine_version='1.0.0',
            pygame_version='2.5.8',
            python_version='3.14.8',
            measured_at=measured_at,
            rebaselined_from='old.jsonl.gz',
            hash_scheme=CONTENT_HASH_SCHEME,
        ).to_json()
        for measured_at in ('2026-10-23T21:00:00+00:00', '2026-10-23T20:00:00+00:00')
    ]
    frames: list[dict[str, Any]] = []
    for number in range(10):
        changed = number in {2, 3}
        slower = 4 <= number <= 8
        frames.append({
            'frame': number,
            'dt': 0.016,
            'scene': 'Game',
            'sprites': [],
            CONTENT_HASH_FIELD: ['b' if changed else 'a', 'a'],
            PROCESSING_SECONDS_FIELD: [0.004 if slower else 0.001, 0.001],
        })
    write_trace(
        trace={
            'game': 'Test',
            'options': {'target_fps': 60.0},
            MEASUREMENT_RUNS_HEADER_FIELD: runs,
            FRAMES_FIELD: frames,
        },
        path=path,
    )


def test_a_changed_run_shows_its_spans_and_its_slower_frames(tmp_path, capsys):
    """The behaviour-change span and the slower span are both listed."""
    path = tmp_path / 'changed.jsonl.gz'
    hand_built_recording(path=path)

    assert run(arguments=[str(path), '--threshold', '50', '--minimum-ms', '0.5']) == (
        ExitCode.SUCCESS
    )

    output = capsys.readouterr().out
    assert (
        'run 1 -> run 0 (commit unknown -> commit unknown): behaviour changed in frames 2-3 '
        '(scene Game), 1 span, 2 frames'
    ) in output
    assert '    frames 2-3 (scene Game)' in output
    assert '5 slower, 0 faster' in output
    assert '    frames 4-8 (scene Game): slower, 5.000 ms -> 20.000 ms (+300.0%)' in output
    assert 'run 1: commit unknown, machine macOS-27.0-arm64-arm-64bit, power unknown' in output


def test_the_span_limit_condenses_long_lists(tmp_path):
    """Spans past the limit are counted on one line."""
    path = tmp_path / 'changed.jsonl.gz'
    hand_built_recording(path=path)
    trace = read_trace(path=path)

    lines = report_lines(path=path, trace=trace, threshold_percent=50, minimum_ms=0.5, span_limit=0)

    assert '    ... and 1 more span' in lines


def test_a_missing_file_and_a_file_that_is_not_a_recording(tmp_path, capsys):
    """Each exits with its own code and says why on standard error."""
    assert run(arguments=[str(tmp_path / 'missing.jsonl.gz')]) == ExitCode.MISSING_INPUT
    not_a_recording = tmp_path / 'not.jsonl.gz'
    not_a_recording.write_text('hello', encoding='utf-8')
    assert run(arguments=[str(not_a_recording)]) == ExitCode.UNUSABLE_INPUT
    errors = capsys.readouterr().err
    assert 'missing.jsonl.gz: no such recording' in errors
    assert 'not a gzip trace' in errors
