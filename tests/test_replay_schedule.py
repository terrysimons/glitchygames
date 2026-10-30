"""scripts/replay_schedule.py: a watched replay's schedule, simulated on the viewer's accumulator.

Synthetic recordings (written with the project's trace writer) whose frame times are chosen:
steady frames present every frame, and so do short catch-up frames after a slow one (up to 1x a
tick runs one frame unless the replay is genuinely behind: glitchygames/replay/viewer.py, rule
2); a recording made faster than the viewer's 60 Hz runs several frames a tick, so all but the
last of each tick are never presented, skipped by design (shorter than a tick). Only a frame
lasting at least a tick at the speed counts as hidden, a failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts import replay_schedule
from scripts.replay_schedule import (
    RecordingSchedule,
    ScheduledTick,
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
# A recording made at 240 FPS: four frames to each 60 Hz tick, so a 1x replay is behind
FAST_FRAME_SECONDS = (0.0, *([1 / 240] * 12))
# A recording made at about 67 FPS (15 ms frames), watched at 1x: the replay owes 1.7 ms more
# each tick, so every so often a tick runs two frames (frames 15 and 16 first) and hides the
# first, which lasted more than 3/4 of a tick
FIFTEEN_MILLISECOND_FRAME_SECONDS = (0.0, *([0.015] * 20))


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


def test_a_slow_frame_0_with_short_catch_up_frames_presents_every_frame():
    """Frames 1 and 2 last 5 ms each: the first running tick owes both but runs one."""
    schedule = simulate_schedule(frame_seconds=SLOW_START_FRAME_SECONDS, speed=1.0)

    assert frames_per_tick(schedule=schedule)[:3] == [(0,), (1,), (2,)]
    assert schedule.never_presented == ()


def test_a_long_middle_frame_followed_by_a_short_one_presents_the_long_one():
    """Frame 2 lasts 40 ms: 1 ms frame 3 waits for the next tick, so frame 2 is shown."""
    schedule = simulate_schedule(frame_seconds=LONG_MIDDLE_FRAME_SECONDS, speed=1.0)

    assert frames_per_tick(schedule=schedule)[:5] == [(0,), (1,), (), (2,), (3,)]
    assert schedule.never_presented == ()


def test_a_recording_faster_than_the_viewer_runs_several_frames_a_tick():
    """240 FPS at 1x is genuinely behind: four frames a tick, the last of each presented."""
    schedule = simulate_schedule(frame_seconds=FAST_FRAME_SECONDS, speed=1.0)

    assert frames_per_tick(schedule=schedule) == [
        (0,),
        (1,),
        (2, 3, 4),
        (5, 6, 7, 8),
        (9, 10, 11, 12),
    ]
    assert schedule.never_presented == (2, 3, 5, 6, 7, 9, 10, 11)
    # Each lasted 4.2 ms, under a tick: skipped by design, none hidden
    assert schedule.skipped_by_design == schedule.never_presented
    assert schedule.hidden == ()


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
    assert '  hidden: none' in output
    assert '  skipped by design (under 3/4 of a tick, or above 1x): none' in output
    assert 'frame 1: 16.67 ms' in output


def test_a_recording_hiding_a_frame_fails_naming_it(tmp_path, capsys):
    """A hidden frame exits REPLAY_DIVERGED: the watched sequence differs."""
    path = write_recording(
        path=tmp_path / 'behind.jsonl.gz', frame_seconds=FIFTEEN_MILLISECOND_FRAME_SECONDS
    )

    exit_code = main(arguments=[str(path)])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert 'tick 15 (250.00 ms): ran 15, 16; accumulator 17.50 ms' in output
    assert '  hidden: 15' in output
    assert '  skipped by design (under 3/4 of a tick, or above 1x): none' in output
    assert 'frame 16: 15.00 ms' in output


def test_the_summary_is_one_line_per_recording(tmp_path, capsys):
    """--summary: name, frame count, hidden and skipped frames, the shortest and longest dt."""
    fast = write_recording(path=tmp_path / 'fast.jsonl.gz', frame_seconds=FAST_FRAME_SECONDS)
    behind = write_recording(
        path=tmp_path / 'behind.jsonl.gz', frame_seconds=FIFTEEN_MILLISECOND_FRAME_SECONDS
    )

    exit_code = main(arguments=[str(fast), str(behind), '--summary'])

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert lines == [
        (
            f'{fast.as_posix()}: 13 frames, hidden: none, '
            'skipped by design: 2, 3, 5, 6, 7, 9, 10, 11, dt min 0.00 ms max 4.17 ms'
        ),
        (
            f'{behind.as_posix()}: 21 frames, hidden: 15, skipped by design: none, '
            'dt min 0.00 ms max 15.00 ms'
        ),
    ]


def test_the_speed_option_is_simulated(tmp_path, capsys):
    """--speed 2 runs the schedule at 2x: steady frames two to a tick, skipped by design."""
    path = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)

    exit_code = main(arguments=[str(path), '--speed', '2', '--summary'])

    assert exit_code == ExitCode.SUCCESS
    assert 'hidden: none, skipped by design: 1, 3, 5' in capsys.readouterr().out


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
    behind = write_recording(
        path=tmp_path / 'behind.jsonl.gz', frame_seconds=FIFTEEN_MILLISECOND_FRAME_SECONDS
    )
    absent = tmp_path / 'absent.jsonl.gz'

    exit_code = main(arguments=[str(behind), str(absent), '--summary'])

    captured = capsys.readouterr()
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert behind.as_posix() in captured.out
    assert absent.as_posix() in captured.err


def test_main_exits_with_the_code(mocker, tmp_path):
    """The module's command line exits with what main returns."""
    path = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)
    mocker.patch.object(replay_schedule.sys, 'argv', ['replay_schedule', str(path), '--summary'])

    with pytest.raises(SystemExit) as exit_info:
        replay_schedule.command_line()

    assert exit_info.value.code == ExitCode.SUCCESS


# A recording made at 120 FPS: two frames to each 60 Hz tick, each shorter than a tick
ONE_HUNDRED_TWENTY_FPS_FRAME_SECONDS = (0.0, *([1 / 120] * 12))
# Committed recordings' stutters: (the long frame, the short catch-up frame after it)
STUTTER_PAIRS = {
    'brave_adventurer_golden_classic_frame_460': (0.03402, 0.00744),
    'paddleslap_rally_frame_286': (0.02863, 0.00151),
}


def schedule_from_ticks(
    *, frame_seconds: tuple[float, ...], speed: float, frames_by_tick: list[tuple[int, ...]]
) -> RecordingSchedule:
    """Return a schedule with the given ticks (a rule other than the viewer's, by hand).

    Returns:
        The schedule.

    """
    return RecordingSchedule(
        frame_seconds=frame_seconds,
        speed=speed,
        ticks=tuple(
            ScheduledTick(
                tick_index=tick_index,
                seconds=tick_index * CONTROL_TICK_SECONDS,
                frames_run=frames_run,
                accumulated_seconds=0.0,
            )
            for tick_index, frames_run in enumerate(frames_by_tick)
        ),
    )


def test_a_120_fps_recording_skips_frames_by_design_and_passes(tmp_path, capsys):
    """8.3 ms frames run two to a 60 Hz tick at 1x: skipped by design, not hidden."""
    path = write_recording(
        path=tmp_path / 'fast.jsonl.gz', frame_seconds=ONE_HUNDRED_TWENTY_FPS_FRAME_SECONDS
    )

    exit_code = main(arguments=[str(path)])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.SUCCESS
    assert '  hidden: none' in output
    assert '  skipped by design (under 3/4 of a tick, or above 1x): ' in output


@pytest.mark.parametrize(
    ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
)
def test_a_stutter_pair_sharing_a_tick_hides_the_long_frame(long_seconds, short_seconds):
    """The old rule ran the long frame (2) and its catch-up frame (3) in one tick: hidden."""
    schedule = schedule_from_ticks(
        frame_seconds=(0.0, STEADY_SECONDS, STEADY_SECONDS, long_seconds, short_seconds),
        speed=1.0,
        frames_by_tick=[(0,), (1,), (), (2, 3), (4,)],
    )

    assert schedule.hidden == (2,)
    assert schedule.skipped_by_design == ()


# The hidden threshold: three quarters of a tick of inner time at 1x
THREE_QUARTERS_OF_A_TICK_SECONDS = CONTROL_TICK_SECONDS * 3 / 4


@pytest.mark.parametrize(
    ('frame_two_seconds', 'expected_hidden'),
    [
        (THREE_QUARTERS_OF_A_TICK_SECONDS, (2,)),
        (THREE_QUARTERS_OF_A_TICK_SECONDS * 0.999, ()),
        (1 / 60.01, (2,)),
        (1 / 60, (2,)),
        (1 / 120, ()),
        (1 / 144, ()),
    ],
    ids=[
        'three_quarters_of_a_tick_is_hidden',
        'just_under_three_quarters_is_skipped',
        'a_default_60_01_fps_frame_is_hidden',
        'a_60_fps_frame_is_hidden',
        'a_120_fps_frame_is_skipped',
        'a_144_fps_frame_is_skipped',
    ],
)
def test_a_frame_counts_as_hidden_from_three_quarters_of_a_tick(frame_two_seconds, expected_hidden):
    """The threshold: a frame lasting at least 3/4 of a tick at the speed (speed x 12.5 ms)."""
    schedule = schedule_from_ticks(
        frame_seconds=(0.0, STEADY_SECONDS, STEADY_SECONDS, frame_two_seconds, 0.001),
        speed=1.0,
        frames_by_tick=[(0,), (1,), (2, 3), (4,)],
    )

    assert schedule.hidden == expected_hidden
    assert schedule.never_presented == (2,)


@pytest.mark.parametrize(
    ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
)
def test_above_normal_speed_a_stutter_pair_is_not_a_failure(
    tmp_path, capsys, long_seconds, short_seconds
):
    """Fast-forward presents the last frame of each tick: frames not presented, exit SUCCESS."""
    path = write_recording(
        path=tmp_path / 'stutter.jsonl.gz',
        frame_seconds=(
            0.0,
            STEADY_SECONDS,
            STEADY_SECONDS,
            long_seconds,
            short_seconds,
            *([STEADY_SECONDS] * 3),
        ),
    )

    exit_code = main(arguments=[str(path), '--speed', '2', '--summary'])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.SUCCESS
    assert 'hidden: none' in output
    assert 'skipped by design: none' not in output


def test_twice_the_speed_skips_steady_frames_by_design():
    """At 2x a tick is 33.3 ms of inner time: 16.7 ms frames run two to a tick, skipped."""
    schedule = simulate_schedule(frame_seconds=STEADY_FRAME_SECONDS, speed=2.0)

    assert schedule.hidden == ()
    assert schedule.skipped_by_design == (1, 3, 5)
