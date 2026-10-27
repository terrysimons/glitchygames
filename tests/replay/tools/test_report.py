"""The ``report`` tool (replay/tools/report.py): a recording's runs, speed and behaviour changes.

Moved from tests/test_recording_report.py with scripts/recording_report.py (Part 3, Stage D, Task
D7). Design: plans/2026-10-23-recording-metrics-2-behaviour-change-map.md. The real recording is a
stand-in game's (tests/stand_in_games.py) live recording rebaselined twice through its console
script (two runs stacked on the run it already holds), so its runs are all of the same work; the
behaviour change is a hand-built recording written with the trace writer. Each front end is
tested: the ``glitchygames report`` command, and ``--report`` on a game in this process, with a
scene that must never be built (and on the stand-in game in a child, in
tests/replay/tools/test_performance_pages.py: both tools as a flag and a command).
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, Any

import pygame
import pytest

from glitchygames.build_info import source_revision
from glitchygames.exit_codes import ExitCode
from glitchygames.recording_history import (
    CONTENT_HASH_FIELD,
    CONTENT_HASH_SCHEME,
    MEASUREMENT_RUNS_HEADER_FIELD,
    PROCESSING_SECONDS_FIELD,
    MeasurementRun,
    RunSummary,
)
from glitchygames.recording_metrics import SHORT_COMMIT_DIGITS
from glitchygames.replay.tools import command
from glitchygames.replay.tools.children import rebaseline_recording_headless
from glitchygames.replay.tools.registry import add_game_flags, build_command_parser, tool_named
from glitchygames.replay.tools.report import describe_run, describe_summary, report_lines
from glitchygames.scenes import Scene
from glitchygames.tracing import FRAMES_FIELD, read_trace, write_trace
from tests.stand_in_games import (
    StandInGame,
    record_stand_in_game,
    stamp_stand_in_game,
    use_stand_in_game,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from pathlib import Path


class GameThatIsNeverBuilt(Scene):
    """A game for the in-process engine test: its scene must never be built for ``--report``."""

    NAME = 'GameThatIsNeverBuilt'
    VERSION = '1.0'

    def __init__(self, options=None, groups=None) -> None:
        """Fail at once: reporting reads the recording, never this scene.

        Raises:
            AssertionError: Always.

        """
        message = '--report built the scene'
        raise AssertionError(message)


def report_through_the_command(*, arguments: list[str]) -> int:
    """Run ``glitchygames report`` in this process.

    Returns:
        Its exit status.

    """
    return command.main(['report', *arguments])


def rebaselined_twice(*, game: StandInGame, recording: Path, tmp_path: Path) -> Path:
    """Rebaseline a stand-in game's recording through its console script, then the result again.

    Returns:
        The second rebaseline's recording (the recording's runs plus two).

    """
    first = tmp_path / 'first.jsonl.gz'
    second = tmp_path / 'second.jsonl.gz'
    for source, target in ((recording, first), (first, second)):
        completed = rebaseline_recording_headless(
            console_script=game.console_script, path=source, new_path=target
        )
        assert completed.returncode == ExitCode.SUCCESS, completed.stdout
    return second


def test_a_real_recording_reports_every_run_and_no_behaviour_change(tmp_path, capsys, monkeypatch):
    """Two new runs of the same work: provenance, summaries, no change in behaviour.

    The stand-in game is seeded and deterministic, so every run of its recording did the same
    work (no frame-0 history change, unlike a golden recorded before its game moved). Its
    recording holds one earlier run of its own: a paced live run, which measured frame times.
    """
    install_directory = tmp_path / 'site-packages'
    game = write_stand_in_game(directory=install_directory)
    # A game of this checkout, as ours are: its runs name the engine's commit as the game's
    stamp_stand_in_game(game=game, revision=source_revision())
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    recording = record_stand_in_game(game=game, path=tmp_path / 'recorded.jsonl.gz')
    recorded_header = read_trace(path=recording)[MEASUREMENT_RUNS_HEADER_FIELD]
    recorded_runs = len(recorded_header)
    recorded_rebaselines = sum(
        1 for recorded_run in recorded_header if recorded_run.get('rebaselined_from')
    )
    path = rebaselined_twice(game=game, recording=recording, tmp_path=tmp_path)

    assert report_through_the_command(arguments=[str(path)]) == ExitCode.SUCCESS

    output = capsys.readouterr().out
    frame_count = len(read_trace(path=path)[FRAMES_FIELD])
    assert f'{path}: {frame_count} frames, {recorded_runs + 2} runs' in output
    assert output.count('rebaselined from') == 2 + recorded_rebaselines
    # The two new runs name the game's commit (its stamp: this checkout's, as the engine they ran
    # names), never an unknown one
    engine_commit = source_revision().commit
    assert engine_commit is not None
    for new_run in range(2):
        assert f'run {new_run}: {engine_commit[:SHORT_COMMIT_DIGITS]}' in output
    # Each child also named its own engine's revision (this checkout's, or the build stamp's
    # under a built install), never an unknown one
    new_runs = read_trace(path=path)[MEASUREMENT_RUNS_HEADER_FIELD][:2]
    assert [new_run['source_revision']['commit'] for new_run in new_runs] == [engine_commit] * 2
    assert 'paced live run' in output
    assert 'frame time p50' in output
    assert 'processing p50' in output
    assert 'Behaviour changes (content hash, adjacent runs):' in output
    # Every adjacent pair of the recording's runs and the two new ones did the same work
    assert output.count('no behaviour change in') == recorded_runs + 1
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

    assert report_through_the_command(
        arguments=[str(path), '--threshold', '50', '--minimum-ms', '0.5']
    ) == (ExitCode.SUCCESS)

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
    assert (
        report_through_the_command(arguments=[str(tmp_path / 'missing.jsonl.gz')])
        == ExitCode.MISSING_INPUT
    )
    not_a_recording = tmp_path / 'not.jsonl.gz'
    not_a_recording.write_text('hello', encoding='utf-8')
    assert report_through_the_command(arguments=[str(not_a_recording)]) == ExitCode.UNUSABLE_INPUT
    errors = capsys.readouterr().err
    assert 'missing.jsonl.gz: no such recording' in errors
    assert 'not a gzip trace' in errors


def test_report_never_builds_the_game(mocker, tmp_path, capsys):
    """``--report`` on a game runs while the engine is built: no pygame, no scene, SUCCESS.

    The scene's constructor raises, so building it would fail the run; the report is printed
    instead, the same report the command prints.
    """
    from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

    path = tmp_path / 'changed.jsonl.gz'
    hand_built_recording(path=path)
    assert report_through_the_command(arguments=[str(path), '--spans', '0']) == ExitCode.SUCCESS
    command_output = capsys.readouterr().out
    pygame_started = mocker.spy(pygame, 'init')
    mocker.patch.object(sys, 'argv', ['the-game', '--report', str(path), '--spans', '0'])

    with pytest.raises(SystemExit) as exit_information:
        GoldenTraceEngine(game=GameThatIsNeverBuilt)

    assert exit_information.value.code == ExitCode.SUCCESS
    pygame_started.assert_not_called()
    assert capsys.readouterr().out == command_output
    assert '    ... and 1 more span' in command_output


def test_the_game_flag_reports_a_missing_or_unreadable_recording(mocker, tmp_path, capsys):
    """``--report`` exits with the command's codes for a missing file and one that is no trace."""
    from glitchygames.replay.tools.golden_traces import GoldenTraceEngine

    not_a_recording = tmp_path / 'not.jsonl.gz'
    not_a_recording.write_text('hello', encoding='utf-8')
    exit_codes = []
    for path in (tmp_path / 'missing.jsonl.gz', not_a_recording):
        mocker.patch.object(sys, 'argv', ['the-game', '--report', str(path)])
        with pytest.raises(SystemExit) as exit_information:
            GoldenTraceEngine(game=GameThatIsNeverBuilt)
        exit_codes.append(exit_information.value.code)

    assert exit_codes == [ExitCode.MISSING_INPUT, ExitCode.UNUSABLE_INPUT]
    errors = capsys.readouterr().err
    assert 'missing.jsonl.gz: no such recording' in errors
    assert 'not a gzip trace' in errors


def test_the_reports_options_read_as_the_scripts_did():
    """The defaults and types scripts/recording_report.py's parser had, on both front ends.

    Any number for the two thresholds and any integer for the span limit, as its ``float`` and
    ``int`` types took them (a negative value included), so a command line that worked still does.
    """
    game = argparse.ArgumentParser()
    add_game_flags(parser=game, tools=(tool_named(name='report'),))
    command_parser = build_command_parser()

    defaults = command_parser.parse_args(['report', 'run.jsonl.gz'])
    given = command_parser.parse_args([
        'report',
        'run.jsonl.gz',
        '--threshold',
        '-5',
        '--minimum-ms',
        '0.05',
        '--spans',
        '-1',
    ])
    on_the_game = vars(game.parse_args(['--report', 'run.jsonl.gz', '--threshold', '7.5']))

    assert (defaults.threshold, defaults.minimum_ms, defaults.spans) == (25.0, 0.2, 20)
    assert (given.threshold, given.minimum_ms, given.spans) == (-5.0, 0.05, -1)
    assert (on_the_game['threshold'], on_the_game['minimum_ms'], on_the_game['spans']) == (
        7.5,
        0.2,
        20,
    )


def test_an_unreadable_run_and_a_run_without_times_are_said_so():
    """A header entry that can't be read, and a run that measured no processing times."""
    assert describe_run(run_index=2, run=None) == 'run 2: unreadable'
    assert describe_summary(summary=None) == 'no processing times'


def test_a_summary_without_a_budget_or_frame_times_stops_at_its_worst_frame():
    """An uncapped replay's run: no budget to count against, no live frame times."""
    summary = RunSummary(
        measured_frames=3,
        total_processing_seconds=0.003,
        p50_processing_seconds=0.001,
        p95_processing_seconds=0.001,
        p99_processing_seconds=0.001,
        max_processing_seconds=0.001,
        worst_frame=0,
        worst_frame_scene=None,
        budget_seconds=None,
        frames_over_budget=None,
        frame_time=None,
    )

    assert describe_summary(summary=summary) == (
        '3 frames, processing p50 1.000 ms, p95 1.000 ms, p99 1.000 ms, max 1.000 ms (frame 0)'
    )
