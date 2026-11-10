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
    inner_frame_seconds,
    main,
    recorded_frame_seconds,
    simulate_schedule,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.controls import CONTROL_TICK_SECONDS
from glitchygames.replay.viewer import ReplayViewer
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
# Brave Adventurer golden-classic's stutter (frame 2 lasts 34.02 ms, frame 3 7.44 ms): with rule
# 2's one-frame limit off (the viewer as it was before it), tick 3 runs both while the replay is
# not behind and hides frame 2
STUTTER_FRAME_SECONDS = (
    0.0,
    STEADY_SECONDS,
    STEADY_SECONDS,
    0.03402,
    0.00744,
    *([STEADY_SECONDS] * 3),
)


@pytest.fixture
def without_rule_two(mocker):
    """Turn rule 2's one-frame limit off (glitchygames/replay/viewer.py), as before it existed.

    The behind condition the viewer reports stays; only the deferral that uses it goes, so the
    tool must still find the frames that limit protects.
    """
    mocker.patch.object(ReplayViewer, '_defers_to_the_next_tick', return_value=False)


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
    assert (
        '  skipped by design (the replay was behind, or shorter than a tick above 1x): none'
        in output
    )
    assert 'frame 1: 16.67 ms' in output


def test_a_recording_hiding_a_frame_fails_naming_it(tmp_path, capsys, without_rule_two):
    """A hidden frame exits REPLAY_DIVERGED: the watched sequence differs."""
    path = write_recording(path=tmp_path / 'stutter.jsonl.gz', frame_seconds=STUTTER_FRAME_SECONDS)

    exit_code = main(arguments=[str(path)])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert 'tick 3 (50.00 ms): ran 2, 3; accumulator 0.21 ms' in output
    assert '  hidden: 2' in output
    assert (
        '  skipped by design (the replay was behind, or shorter than a tick above 1x): none'
        in output
    )
    assert 'frame 3: 34.02 ms' in output


def test_the_summary_is_one_line_per_recording(tmp_path, capsys, without_rule_two):
    """--summary: name, frame count, hidden and skipped frames, the shortest and longest dt."""
    steady = write_recording(path=tmp_path / 'steady.jsonl.gz', frame_seconds=STEADY_FRAME_SECONDS)
    stutter = write_recording(
        path=tmp_path / 'stutter.jsonl.gz', frame_seconds=STUTTER_FRAME_SECONDS
    )

    exit_code = main(arguments=[str(steady), str(stutter), '--summary'])

    lines = capsys.readouterr().out.splitlines()
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert lines == [
        (
            f'{steady.as_posix()}: 8 frames, hidden: none, skipped by design: none, '
            'dt min 0.00 ms max 16.67 ms'
        ),
        (
            f'{stutter.as_posix()}: 8 frames, hidden: 2, skipped by design: none, '
            'dt min 0.00 ms max 34.02 ms'
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


def test_the_first_failure_decides_the_exit_code(tmp_path, capsys, without_rule_two):
    """Every recording is reported; the exit code is the first failure's."""
    stutter = write_recording(
        path=tmp_path / 'stutter.jsonl.gz', frame_seconds=STUTTER_FRAME_SECONDS
    )
    absent = tmp_path / 'absent.jsonl.gz'

    exit_code = main(arguments=[str(stutter), str(absent), '--summary'])

    captured = capsys.readouterr()
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert stutter.as_posix() in captured.out
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
    *,
    frame_seconds: tuple[float, ...],
    speed: float,
    frames_by_tick: list[tuple[int, ...]],
    behind_frames: frozenset[int] = frozenset(),
) -> RecordingSchedule:
    """Return a schedule with the given ticks (a rule other than the viewer's, by hand).

    Args:
        frame_seconds: Every frame's recorded dt.
        speed: The replay speed.
        frames_by_tick: The frames each tick ran.
        behind_frames: The frames that ran while the replay was behind.

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
                owed_before_seconds=tuple(
                    (
                        inner_frame_seconds(frame_seconds=frame_seconds, frame_index=frame)
                        + (speed * CONTROL_TICK_SECONDS if frame in behind_frames else 0.0)
                    )
                    for frame in frames_run
                ),
                viewer_reported_behind=tuple(frame in behind_frames for frame in frames_run),
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
    assert (
        '  skipped by design (the replay was behind, or shorter than a tick above 1x): ' in output
    )


@pytest.mark.parametrize(
    ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
)
def test_a_stutter_pair_sharing_a_tick_hides_the_long_frame(long_seconds, short_seconds):
    """The old rule ran the long frame (2) and its catch-up frame (3), not behind: hidden."""
    schedule = schedule_from_ticks(
        frame_seconds=(0.0, STEADY_SECONDS, STEADY_SECONDS, long_seconds, short_seconds),
        speed=1.0,
        frames_by_tick=[(0,), (1,), (), (2, 3), (4,)],
    )

    assert schedule.hidden == (2,)
    assert schedule.skipped_by_design == ()


def test_a_frame_hidden_by_an_extra_frame_that_ran_behind_is_skipped_by_design():
    """The same tick, but frame 3 ran while the replay was behind: frame 2 is not a failure."""
    schedule = schedule_from_ticks(
        frame_seconds=(0.0, STEADY_SECONDS, STEADY_SECONDS, 0.03402, 0.00744),
        speed=1.0,
        frames_by_tick=[(0,), (1,), (), (2, 3), (4,)],
        behind_frames=frozenset({3}),
    )

    assert schedule.hidden == ()
    assert schedule.skipped_by_design == (2,)


@pytest.mark.parametrize(
    ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
)
def test_without_rule_two_the_viewer_hides_the_long_frame(
    long_seconds, short_seconds, without_rule_two
):
    """Trap 1: the viewer's own behind condition, not the limit built on it, finds the frame."""
    schedule = simulate_schedule(
        frame_seconds=(
            0.0,
            STEADY_SECONDS,
            STEADY_SECONDS,
            long_seconds,
            short_seconds,
            *([STEADY_SECONDS] * 3),
        ),
        speed=1.0,
    )

    assert schedule.hidden == (2,)


def every_extra_frame_ran_behind(*, schedule: RecordingSchedule) -> bool:
    """Whether every frame a tick ran after its first ran while the replay was behind.

    Returns:
        True when so (vacuously for a schedule with no such frame).

    """
    return all(
        schedule.ran_behind(frame=frame) for tick in schedule.ticks for frame in tick.frames_run[1:]
    )


def test_a_long_60_01_fps_recording_passes_its_unshown_frames_behind():
    """Trap 2: 200 s at the default 60.01 FPS on the 60 Hz tick: its extra frame ran behind."""
    schedule = simulate_schedule(frame_seconds=(0.0, *([1 / 60.01] * 12_002)), speed=1.0)

    assert schedule.hidden == ()
    assert schedule.never_presented
    assert every_extra_frame_ran_behind(schedule=schedule)


def test_a_70_fps_recording_passes_its_unshown_frames_behind():
    """Trap 3: 70 FPS frames, more than the 60 Hz tick shows; each extra frame ran behind."""
    schedule = simulate_schedule(frame_seconds=(0.0, *([1 / 70] * 700)), speed=1.0)

    assert schedule.hidden == ()
    assert schedule.never_presented
    assert every_extra_frame_ran_behind(schedule=schedule)


def test_a_genuine_stall_presents_its_long_frame_and_bursts_behind():
    """Trap 4: a 100 ms frame (10), then the live pacing's backlog of 1 ms frames.

    The long frame is presented in its own tick; the short frames that follow run several to a
    tick, each extra one while the replay is behind; the recording passes.
    """
    frame_seconds = (
        0.0,
        *([STEADY_SECONDS] * 10),
        0.100,
        *([0.001] * 100),
        *([STEADY_SECONDS] * 20),
    )

    schedule = simulate_schedule(frame_seconds=frame_seconds, speed=1.0)

    assert 10 not in schedule.never_presented
    assert any(len(tick.frames_run) > 1 for tick in schedule.ticks)
    assert every_extra_frame_ran_behind(schedule=schedule)
    assert schedule.hidden == ()


@pytest.mark.parametrize('speed', [0.25, 0.5, 1.0, 2.0])
def test_zero_length_frames_never_fail(speed):
    """Trap 5: frames recorded with no duration, singly and in runs, at any speed."""
    frame_seconds = (
        0.0,
        *([0.0 if frame % 10 == 0 else STEADY_SECONDS for frame in range(300)]),
        *([0.0] * 20),
        *([STEADY_SECONDS] * 20),
    )

    schedule = simulate_schedule(frame_seconds=frame_seconds, speed=speed)

    assert schedule.hidden == ()


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


def test_the_tool_derives_behind_from_the_schedule_itself():
    """Owed before each frame run, the tool's own condition: owed >= frame + speed x tick."""
    schedule = simulate_schedule(frame_seconds=FAST_FRAME_SECONDS, speed=1.0)

    for tick in schedule.ticks:
        for frame, owed_seconds in zip(tick.frames_run, tick.owed_before_seconds, strict=True):
            duration_seconds = inner_frame_seconds(
                frame_seconds=schedule.frame_seconds, frame_index=frame
            )
            assert schedule.ran_behind(frame=frame) == (
                owed_seconds >= duration_seconds + CONTROL_TICK_SECONDS
            )
    assert schedule.behind_disagreements == ()


def without_the_speed_in_owes_beyond_a_tick(
    viewer: ReplayViewer, *, inner_frame_seconds: float
) -> bool:
    """A broken behind condition: a whole real tick of inner time, not the speed times it.

    Returns:
        True when the accumulator holds the frame plus CONTROL_TICK_SECONDS.

    """
    return viewer.accumulated_seconds >= inner_frame_seconds + CONTROL_TICK_SECONDS


def test_a_behind_condition_without_the_speed_fails_at_half_speed(mocker, tmp_path, capsys):
    """At 0.5x the viewer's flag then disagrees with the tool's own condition: a failure."""
    mocker.patch.object(
        ReplayViewer,
        '_owes_beyond_a_tick',
        autospec=True,
        side_effect=without_the_speed_in_owes_beyond_a_tick,
    )
    path = write_recording(path=tmp_path / 'fast.jsonl.gz', frame_seconds=FAST_FRAME_SECONDS)

    exit_code = main(arguments=[str(path), '--speed', '0.5'])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert '  viewer disagrees on behind: none' not in output
    assert '  viewer disagrees on behind: ' in output


def test_above_normal_speed_a_long_frame_sharing_a_tick_is_hidden(mocker):
    """Rule 2 off: at 2x the 34.02 ms frame (17 ms real, over a tick) shares a tick, hidden."""
    mocker.patch.object(ReplayViewer, '_defers_to_the_next_tick', return_value=False)

    schedule = simulate_schedule(frame_seconds=STUTTER_FRAME_SECONDS, speed=2.0)

    assert schedule.hidden == (2,)
