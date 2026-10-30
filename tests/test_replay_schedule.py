"""scripts/replay_schedule.py: a watched replay's schedule, simulated on the viewer's accumulator.

Synthetic recordings (written with the project's trace writer) whose frame times are chosen:
steady frames present every frame; a slow frame 0 whose catch-up frames are short runs two
frames in one tick, so the earlier is never presented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import replay_schedule
from scripts.replay_schedule import (
    RecordingSchedule,
    main,
    recorded_frame_seconds,
    simulate_schedule,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.controls import CONTROL_TICK_SECONDS
from glitchygames.tracing import write_trace

if TYPE_CHECKING:
    from pathlib import Path

STEADY_SECONDS = 1 / 60
# Pacing catching up after a slow frame 0: frame 1's dt is frame 0's duration
SLOW_START_FRAME_SECONDS = (0.0, 0.050, 0.005, 0.005, *([STEADY_SECONDS] * 4))
# A long frame 2 (frame 3's dt) followed by a very short frame 3 (frame 4's dt)
LONG_MIDDLE_FRAME_SECONDS = (
    0.0,
    STEADY_SECONDS,
    STEADY_SECONDS,
    0.040,
    0.001,
    *([STEADY_SECONDS] * 3),
)
STEADY_FRAME_SECONDS = (0.0, *([STEADY_SECONDS] * 7))


def write_recording(*, path: Path, frame_seconds: tuple[float, ...]) -> Path:
    """Write a recording whose frames have the given recorded dts (nothing else of note).

    Returns:
        ``path``.

    """
    write_trace(
        trace={
            'game': 'stand_in',
            'frames': [
                {'frame': frame_index, 'dt': dt, 'scene': 'StandInScene', 'sprites': []}
                for frame_index, dt in enumerate(frame_seconds)
            ],
        },
        path=path,
    )
    return path


def frames_per_tick(*, schedule: RecordingSchedule) -> list[tuple[int, ...]]:
    """Return the frames each tick ran, in order.

    Returns:
        One tuple per tick.

    """
    return [tick.frames_run for tick in schedule.ticks]


def test_steady_frames_are_each_presented():
    """1/60 s frames at 1x: frame 0 behind the start screen, then one frame a tick."""
    schedule = simulate_schedule(frame_seconds=STEADY_FRAME_SECONDS, speed=1.0)

    assert frames_per_tick(schedule=schedule) == [(index,) for index in range(8)]
    assert schedule.never_presented == ()
    # The half-frame phase stays in the accumulator
    assert schedule.ticks[-1].accumulated_seconds == pytest.approx(STEADY_SECONDS / 2)


def test_a_slow_frame_0_with_short_catch_up_frames_never_presents_frame_1():
    """Frames 1 and 2 last 5 ms each: the first running tick owes both, presenting only 2."""
    schedule = simulate_schedule(frame_seconds=SLOW_START_FRAME_SECONDS, speed=1.0)

    assert frames_per_tick(schedule=schedule)[:3] == [(0,), (1, 2), (3,)]
    assert schedule.never_presented == (1,)


def test_a_long_middle_frame_followed_by_a_short_one_never_presents_the_long_one():
    """Frame 2 lasts 40 ms: its tick's leftover pays for 1 ms frame 3 too, hiding frame 2."""
    schedule = simulate_schedule(frame_seconds=LONG_MIDDLE_FRAME_SECONDS, speed=1.0)

    assert frames_per_tick(schedule=schedule)[:5] == [(0,), (1,), (), (2, 3), (4,)]
    assert schedule.never_presented == (2,)


def test_twice_the_speed_runs_two_frames_a_tick():
    """At 2x each tick runs two steady frames: the first of each pair is never presented."""
    schedule = simulate_schedule(frame_seconds=STEADY_FRAME_SECONDS, speed=2.0)

    assert frames_per_tick(schedule=schedule) == [(0,), (1, 2), (3, 4), (5, 6), (7,)]
    assert schedule.never_presented == (1, 3, 5)


def test_an_ideal_tick_is_exactly_the_viewers_period():
    """Each tick is one period after the last (the ideal clock)."""
    schedule = simulate_schedule(frame_seconds=STEADY_FRAME_SECONDS, speed=1.0)

    assert [tick.seconds for tick in schedule.ticks] == pytest.approx([
        tick_index * CONTROL_TICK_SECONDS for tick_index in range(len(schedule.ticks))
    ])


def test_the_recorded_frame_times_are_read_from_the_recording(tmp_path):
    """Every frame's recorded dt, in order."""
    path = write_recording(path=tmp_path / 'slow.jsonl.gz', frame_seconds=SLOW_START_FRAME_SECONDS)

    assert recorded_frame_seconds(path=path) == pytest.approx(SLOW_START_FRAME_SECONDS)


def test_a_recording_presenting_every_frame_succeeds(tmp_path, capsys):
    """The detail: each tick's frames and accumulator, nothing hidden, and every frame's dt."""
    path = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)

    exit_code = main(arguments=[str(path)])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.SUCCESS
    assert f'{path.as_posix()}: 8 frames at 1x' in output
    assert 'tick 1 (16.67 ms): ran 1; accumulator 8.33 ms' in output
    assert 'never presented: none' in output
    assert 'frame 1: 16.67 ms' in output


def test_a_recording_hiding_a_frame_fails_naming_it(tmp_path, capsys):
    """A frame never presented exits REPLAY_DIVERGED: the watched sequence differs."""
    path = write_recording(path=tmp_path / 'slow.jsonl.gz', frame_seconds=SLOW_START_FRAME_SECONDS)

    exit_code = main(arguments=[str(path)])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert 'tick 1 (16.67 ms): ran 1, 2; accumulator 9.17 ms' in output
    assert 'never presented: 1' in output
    assert 'frame 1: 50.00 ms' in output


def test_the_summary_is_one_line_per_recording(tmp_path, capsys):
    """--summary: name, frame count, the frames never presented, the shortest and longest dt."""
    steady = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)
    slow = write_recording(path=tmp_path / 'slow.jsonl.gz', frame_seconds=SLOW_START_FRAME_SECONDS)

    exit_code = main(arguments=[str(steady), str(slow), '--summary'])

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert lines == [
        f'{steady.as_posix()}: 8 frames, never presented: none, dt min 0.00 ms max 16.67 ms',
        f'{slow.as_posix()}: 8 frames, never presented: 1, dt min 0.00 ms max 50.00 ms',
    ]


def test_the_speed_option_is_simulated(tmp_path, capsys):
    """--speed 2 runs the schedule at 2x."""
    path = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)

    exit_code = main(arguments=[str(path), '--speed', '2', '--summary'])

    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert 'never presented: 1, 3, 5' in capsys.readouterr().out


@pytest.mark.parametrize('speed', ['0', '-1', '9', 'fast'])
def test_a_speed_the_viewer_cannot_play_at_is_refused(tmp_path, speed):
    """Speeds outside the viewer's range are a usage error (argparse's)."""
    path = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)

    with pytest.raises(SystemExit) as exit_info:
        main(arguments=[str(path), '--speed', speed])

    assert exit_info.value.code == ExitCode.ARGUMENT_PARSER_ERROR


def test_a_missing_recording_is_missing_input(tmp_path, capsys):
    """A file that does not exist: MISSING_INPUT, named on stderr."""
    path = tmp_path / 'absent.jsonl.gz'

    exit_code = main(arguments=[str(path)])

    assert exit_code == ExitCode.MISSING_INPUT
    assert f'{path.as_posix()}: no such recording' in capsys.readouterr().err


@pytest.mark.parametrize('kind', ['not_gzip', 'directory', 'no_frames', 'no_dt'])
def test_an_unreadable_recording_is_unusable_input(tmp_path, capsys, kind):
    """Not a trace, a directory, no frames or a frame without a dt: UNUSABLE_INPUT."""
    path = tmp_path / 'bad.jsonl.gz'
    if kind == 'not_gzip':
        path.write_text('not a recording', encoding='utf-8')
    elif kind == 'directory':
        path.mkdir()
    elif kind == 'no_frames':
        write_recording(path=path, frame_seconds=())
    else:
        write_trace(
            trace={
                'game': 'stand_in',
                'frames': [{'frame': 0, 'scene': 'StandInScene', 'sprites': []}],
            },
            path=path,
        )

    exit_code = main(arguments=[str(path)])

    assert exit_code == ExitCode.UNUSABLE_INPUT
    assert path.as_posix() in capsys.readouterr().err


def test_the_first_failure_decides_the_exit_code(tmp_path, capsys):
    """Every recording is reported; the exit code is the first failure's."""
    slow = write_recording(path=tmp_path / 'slow.jsonl.gz', frame_seconds=SLOW_START_FRAME_SECONDS)
    absent = tmp_path / 'absent.jsonl.gz'

    exit_code = main(arguments=[str(slow), str(absent), '--summary'])

    captured = capsys.readouterr()
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert slow.as_posix() in captured.out
    assert absent.as_posix() in captured.err


def test_main_exits_with_the_code(mocker, tmp_path):
    """The module's command line exits with what main returns."""
    path = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)
    mocker.patch.object(replay_schedule.sys, 'argv', ['replay_schedule', str(path), '--summary'])

    with pytest.raises(SystemExit) as exit_info:
        replay_schedule.command_line()

    assert exit_info.value.code == ExitCode.SUCCESS
