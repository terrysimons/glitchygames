"""The replay viewer's outer loop (glitchygames/replay/viewer.py), on a fake measured clock.

These drive ``ReplayViewer`` directly, as ``ReplaySources.hold_frame`` does, with inner frames
that cost a chosen amount of real time; tests/world/test_gameplay_replay.py drives it through a
real replay.
"""

from __future__ import annotations

import collections
import random
from time import perf_counter_ns
from typing import TYPE_CHECKING, Any, Self

import pytest
from pydantic import BaseModel, ConfigDict

from glitchygames.recording import DT_FIELD
from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, ReplayControls
from glitchygames.replay.driver import OPTIONS_HEADER_FIELD, RecordedFrames
from glitchygames.replay.viewer import (
    BEHIND_SPEED_FRACTION,
    EFFECTIVE_SPEED_WINDOW_TICKS,
    INNER_FRAME_BUDGET_SECONDS,
    MAX_INNER_FRAMES_PER_TICK,
    ReplayViewer,
)
from glitchygames.tracing import FRAMES_FIELD, read_trace_result, write_trace

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# A recording made at the engine's default target, 60.01 FPS: a hair off the 60 Hz viewer tick
RECORDED_FRAME_SECONDS = 1 / 60.01


class FakeTime:
    """A fake measured clock and sleep for the viewer; sleeps may wake up late."""

    def __init__(self, *, mocker, lateness_seconds: float = 0.0, seed: int = 1) -> None:
        """Patch the viewer's clock and sleep (undone with the test's mocker).

        Args:
            mocker: pytest-mock's fixture.
            lateness_seconds: Each sleep wakes up to this much late (uniformly, seeded).
            seed: The lateness's random seed.

        """
        self.now = 1.0e5
        self._lateness_seconds = lateness_seconds
        self._random = random.Random(seed)
        mocker.patch('glitchygames.clock.measured_seconds', side_effect=self.read)
        # Which sleep each wait used: 'fine' (sleep then spin) or 'coarse' (no spin)
        self.sleeps: list[str] = []
        mocker.patch.object(viewer_module, 'sleep_for', side_effect=self.sleep)
        mocker.patch.object(viewer_module, 'sleep_coarsely', side_effect=self.sleep_coarsely)

    def read(self) -> float:
        """Return the fake time.

        Returns:
            Seconds.

        """
        return self.now

    def sleep(self, *, seconds: float) -> None:
        """Sleep ``seconds``, waking up a little late at random (sleep_for's signature)."""
        self.sleeps.append('fine')
        self.now += seconds + self._random.uniform(0.0, self._lateness_seconds)

    def sleep_coarsely(self, *, seconds: float) -> None:
        """The coarse sleep (sleep_coarsely's signature)."""
        self.sleeps.append('coarse')
        self.now += seconds + self._random.uniform(0.0, self._lateness_seconds)


# The most inner frames a test lets one tick run: far above any tick's frames in these tests (50
# for a 3000 FPS recording at 1x), so a rule that never closes a tick fails at once instead of
# hanging the suite
MOST_INNER_FRAMES_A_TEST_TICK_RUNS = 10_000


def run_open_tick(
    *,
    viewer: ReplayViewer,
    inner_frame_seconds_for: Callable[[int], float],
    after_each_frame: Callable[[], None] | None = None,
) -> int:
    """Run the open tick's inner frames until the viewer closes it, as hold_frame asks.

    Args:
        viewer: The viewer, a tick open.
        inner_frame_seconds_for: The recorded duration of the tick's Nth frame (from 0).
        after_each_frame: Called after each frame runs (a frame costing real time), or None.

    Returns:
        How many frames the tick ran.

    """
    for frames_run in range(MOST_INNER_FRAMES_A_TEST_TICK_RUNS + 1):
        if not viewer.should_run_inner_frame(
            inner_frame_seconds=inner_frame_seconds_for(frames_run),
            is_inner_over=False,
            is_first_inner_frame=False,
        ):
            return frames_run
        if after_each_frame is not None:
            after_each_frame()
    pytest.fail(f'a tick ran more than {MOST_INNER_FRAMES_A_TEST_TICK_RUNS} inner frames')


def run_ticks(
    *,
    viewer: ReplayViewer,
    time: FakeTime,
    tick_count: int,
    inner_frame_cost_seconds: float = 0.0001,
    inner_frame_seconds: float = RECORDED_FRAME_SECONDS,
) -> collections.Counter[int]:
    """Run outer ticks as ReplaySources.hold_frame does, each inner frame costing real time.

    Returns:
        How many ticks ran each number of inner frames.

    """
    frames_per_tick: collections.Counter[int] = collections.Counter()
    for _ in range(tick_count):
        now = viewer.begin_tick(is_inner_running=True)
        assert now is not None
        viewer.apply_key_events(now=now)
        viewer.accrue(now=now, is_inner_running=True)

        def spend_the_frame_cost() -> None:
            time.now += inner_frame_cost_seconds

        frames = run_open_tick(
            viewer=viewer,
            inner_frame_seconds_for=lambda _frame: inner_frame_seconds,
            after_each_frame=spend_the_frame_cost,
        )
        frames_per_tick[frames] += 1
    return frames_per_tick


def new_viewer(*, speed: float = 1.0) -> ReplayViewer:
    """A viewer over a long recording, at ``speed``.

    Returns:
        The viewer.

    """
    controls = ReplayControls(total_frames=10**9)
    controls.speed = speed
    return ReplayViewer(controls=controls)


@pytest.mark.parametrize('lateness_seconds', [0.0, 0.0015], ids=['punctual', 'late_wakeups'])
def test_normal_speed_runs_one_frame_a_tick_but_for_the_rate_mismatch(mocker, lateness_seconds):
    """The reviewer's simulation, scaled down: 60.01 FPS shown on a 60 Hz tick for 6000 ticks.

    The true mismatch is one extra frame per 6000 ticks; sleeps that wake late (snapped to one
    period) must not turn into 0-frame and 2-frame ticks.
    """
    time = FakeTime(mocker=mocker, lateness_seconds=lateness_seconds)
    viewer = new_viewer()
    frames_per_tick = run_ticks(viewer=viewer, time=time, tick_count=6000)
    # The first tick owes nothing; then one frame a tick, plus the rate mismatch
    uneven_ticks = frames_per_tick[0] + frames_per_tick[2] - 1
    assert uneven_ticks <= 3
    assert set(frames_per_tick) <= {0, 1, 2}


def test_eight_times_runs_eight_frames_a_tick(mocker):
    """8x shows eight recorded frames a tick, late wake-ups included."""
    time = FakeTime(mocker=mocker, lateness_seconds=0.0015)
    viewer = new_viewer(speed=8.0)
    frames_per_tick = run_ticks(viewer=viewer, time=time, tick_count=600)
    assert frames_per_tick[8] >= 590


def test_the_tick_keeps_sixty_hertz_when_inner_frames_are_costly(mocker):
    """Each inner frame costs 5 ms: a tick stops after its budget and the tick stays on time."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer(speed=8.0)
    start = time.now
    frames_per_tick = run_ticks(
        viewer=viewer, time=time, tick_count=600, inner_frame_cost_seconds=0.005
    )
    elapsed = time.now - start
    assert elapsed == pytest.approx(600 * CONTROL_TICK_SECONDS, rel=0.01)
    # Each tick runs frames only until its budget is spent
    most_frames = int(INNER_FRAME_BUDGET_SECONDS / 0.005) + 1
    assert max(frames_per_tick) <= most_frames
    assert viewer.is_behind
    assert viewer.effective_speed() == pytest.approx(
        most_frames * RECORDED_FRAME_SECONDS / CONTROL_TICK_SECONDS, rel=0.35
    )


def test_the_owed_time_is_bounded_when_inner_frames_cannot_keep_up(mocker):
    """Costly inner frames never let the accumulator owe more than one tick's worth."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer(speed=8.0)
    run_ticks(viewer=viewer, time=time, tick_count=600, inner_frame_cost_seconds=0.005)
    assert viewer.accumulated_seconds <= MAX_INNER_FRAMES_PER_TICK * RECORDED_FRAME_SECONDS


def test_a_stall_runs_at_most_one_bounded_burst(mocker):
    """A two-second stall runs one bounded burst, then the normal pace.

    The owed time is capped at MAX_INNER_FRAMES_PER_TICK and a half frames; up to 1x the burst
    stops once the replay owes less than a frame plus a tick (rule 2), so it runs one frame
    fewer than the cap and the replay carries one tick behind.
    """
    time = FakeTime(mocker=mocker)
    viewer = new_viewer()
    run_ticks(viewer=viewer, time=time, tick_count=10)
    time.now += 2.0  # a two-second stall: 120 frames owed, at most one tick's worth are kept
    frames_per_tick = run_ticks(viewer=viewer, time=time, tick_count=30)
    assert frames_per_tick[MAX_INNER_FRAMES_PER_TICK - 1] == 1
    assert max(frames_per_tick) == MAX_INNER_FRAMES_PER_TICK - 1
    assert sum(count for frames, count in frames_per_tick.items() if frames > 2) == 1


@pytest.mark.parametrize(
    ('is_inner_running', 'expected_sleep'), [(True, 'fine'), (False, 'coarse')]
)
def test_the_wait_spins_only_while_the_inner_game_runs(mocker, is_inner_running, expected_sleep):
    """Paused, at the start screen or over, the wait is a plain sleep; running, sleep then spin."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer()
    viewer.begin_tick(is_inner_running=is_inner_running)
    viewer.accrue(now=time.now, is_inner_running=is_inner_running)
    viewer.should_run_inner_frame(
        inner_frame_seconds=RECORDED_FRAME_SECONDS, is_inner_over=False, is_first_inner_frame=False
    )
    viewer.begin_tick(is_inner_running=is_inner_running)
    assert time.sleeps == [expected_sleep]


def test_a_slightly_slow_game_at_normal_speed_is_not_labelled_behind(mocker):
    """12 ms inner frames at 1x: an occasional tick cut short is not 'can't keep up'."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer()
    run_ticks(viewer=viewer, time=time, tick_count=300, inner_frame_cost_seconds=0.012)
    assert viewer.real_speed_if_behind() is None


def test_after_a_stall_the_real_speed_is_not_skewed_low(mocker):
    """The stall tick restarts the window: no slow figure is shown for the next second."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer()
    run_ticks(viewer=viewer, time=time, tick_count=10)
    time.now += 2.0
    run_ticks(viewer=viewer, time=time, tick_count=5)
    assert viewer.real_speed_if_behind() is None
    assert viewer.effective_speed() == pytest.approx(1.0, rel=0.05)


def test_the_real_speed_is_shown_when_meaningfully_slower(mocker):
    """Costly frames at 8x: the real speed, well below 8x, is shown."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer(speed=8.0)
    run_ticks(viewer=viewer, time=time, tick_count=120, inner_frame_cost_seconds=0.005)
    real_speed = viewer.real_speed_if_behind()
    assert real_speed is not None
    assert real_speed < 8.0 * BEHIND_SPEED_FRACTION


def test_effective_speed_pairs_each_ticks_frames_with_its_own_time(mocker):
    """At 1/4x one frame runs every fourth tick: the window's speed is exactly the speed."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer(speed=0.25)
    run_ticks(viewer=viewer, time=time, tick_count=EFFECTIVE_SPEED_WINDOW_TICKS + 1)
    assert viewer.effective_speed() == pytest.approx(0.25, rel=0.1)


def test_frames_recorded_with_no_duration_do_not_fall_behind(mocker):
    """A recorded dt of 0.0 owes nothing: never behind."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer()
    run_ticks(viewer=viewer, time=time, tick_count=10, inner_frame_seconds=0.0)
    assert not viewer.is_behind


def test_keeping_up_is_not_behind(mocker):
    """A viewer that keeps up is not behind, and its effective speed is the speed."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer(speed=2.0)
    run_ticks(viewer=viewer, time=time, tick_count=120)
    assert not viewer.is_behind
    assert viewer.effective_speed() == pytest.approx(2.0, rel=0.05)


def test_effective_speed_is_zero_before_any_time_passed():
    """A new viewer has run nothing over no real time: its effective speed is 0.0."""
    viewer = new_viewer(speed=4.0)
    assert viewer.effective_speed() == 0.0
    assert viewer.real_speed_if_behind() is None


def test_sleep_coarsely_sleeps_only_for_a_positive_time(mocker):
    """The coarse sleep is one sleep of the time asked for; none for zero or less."""
    sleep = mocker.Mock()
    viewer_module.sleep_coarsely(seconds=0.0, sleep=sleep)
    viewer_module.sleep_coarsely(seconds=-0.5, sleep=sleep)
    sleep.assert_not_called()
    viewer_module.sleep_coarsely(seconds=0.002, sleep=sleep)
    sleep.assert_called_once_with(0.002)


def test_sleep_for_waits_at_least_the_time_asked_for():
    """The fine sleep (sleep then spin, on the perf_counter timer) returns no earlier than asked."""
    sleep_seconds = 0.003
    started_ns = perf_counter_ns()
    viewer_module.sleep_for(seconds=sleep_seconds)
    assert perf_counter_ns() - started_ns >= round(sleep_seconds * 1_000_000_000)


def test_sleep_for_does_not_sleep_for_zero_or_less(mocker):
    """No positive time to wait: the timer is never asked to sleep."""
    sleep_until_next = mocker.patch.object(viewer_module._SLEEP_TIMER, 'sleep_until_next')
    viewer_module.sleep_for(seconds=0.0)
    viewer_module.sleep_for(seconds=-0.1)
    sleep_until_next.assert_not_called()


class TestExternalTicks:
    """A viewer ticked from outside (a browser's animation frames) never sleeps.

    The outer tick is the wait (glitchygames/replay/viewer.py ``run_watched_replay_async``); the
    viewer opens a tick on each and owes the inner game the real time since the last one.
    """

    def test_it_never_sleeps(self, mocker):
        time = FakeTime(mocker=mocker)
        viewer = new_viewer()
        viewer.ticks_externally = True

        first_tick = viewer.begin_tick(is_inner_running=True)
        viewer.accrue(now=time.now, is_inner_running=True)
        viewer.should_run_inner_frame(
            inner_frame_seconds=RECORDED_FRAME_SECONDS,
            is_inner_over=False,
            is_first_inner_frame=False,
        )
        second_tick = viewer.begin_tick(is_inner_running=True)

        assert first_tick == second_tick == time.now
        assert not time.sleeps

    @pytest.mark.parametrize('display_hertz', [60, 120, 144])
    def test_normal_speed_follows_real_time_at_any_display_rate(self, mocker, display_hertz):
        """60.01 FPS at 1x runs as many inner frames as real time passed, whatever the rate."""
        time = FakeTime(mocker=mocker)
        viewer = new_viewer()
        viewer.ticks_externally = True
        tick_count = display_hertz * 20
        frames_run = 0
        for _ in range(tick_count):
            now = viewer.begin_tick(is_inner_running=True)
            viewer.accrue(now=now, is_inner_running=True)
            frames_run += run_open_tick(
                viewer=viewer, inner_frame_seconds_for=lambda _frame: RECORDED_FRAME_SECONDS
            )
            time.now += 1 / display_hertz

        real_seconds = (tick_count - 1) / display_hertz
        assert abs(frames_run - real_seconds / RECORDED_FRAME_SECONDS) <= 1
        assert not time.sleeps


class TestGivenClock:
    """A viewer given its own measured clock reads only that clock (scripts/replay_schedule.py).

    The schedule tool drives the viewer's real accumulator on an ideal clock: every tick exactly
    one period, inner frames costing no time.
    """

    def test_it_never_reads_the_engine_clock(self, mocker):
        engine_clock = mocker.patch('glitchygames.clock.measured_seconds', return_value=0.0)
        given = {'seconds': 5.0}
        viewer = ReplayViewer(
            controls=ReplayControls(total_frames=10**9), measured_seconds=lambda: given['seconds']
        )
        viewer.ticks_externally = True
        frames_run = 0
        for _ in range(10):
            now = viewer.begin_tick(is_inner_running=True)
            assert now == given['seconds']
            viewer.accrue(now=now, is_inner_running=True)
            frames_run += run_open_tick(
                viewer=viewer, inner_frame_seconds_for=lambda _frame: CONTROL_TICK_SECONDS
            )
            given['seconds'] += CONTROL_TICK_SECONDS

        # The first tick owes nothing but the half-frame phase; then one frame a tick
        assert frames_run == 9
        engine_clock.assert_not_called()

    def test_inner_frames_on_a_clock_that_stands_still_never_spend_the_budget(self):
        """The tick's budget is read on the given clock: frames costing nothing never end it."""
        controls = ReplayControls(total_frames=10**9)
        controls.speed = ReplayControls.MAX_SPEED
        viewer = ReplayViewer(controls=controls, measured_seconds=lambda: 0.0)
        viewer.ticks_externally = True
        now = viewer.begin_tick(is_inner_running=True)
        assert now is not None
        viewer.accrue(now=now, is_inner_running=True)
        viewer.accumulated_seconds = MAX_INNER_FRAMES_PER_TICK * RECORDED_FRAME_SECONDS
        frames_run = run_open_tick(
            viewer=viewer, inner_frame_seconds_for=lambda _frame: RECORDED_FRAME_SECONDS
        )
        assert frames_run == MAX_INNER_FRAMES_PER_TICK


def test_above_normal_speed_a_tick_runs_at_most_the_frame_cap():
    """Above 1x MAX_INNER_FRAMES_PER_TICK still ends a tick (up to 1x only the budget does).

    One 100 ms frame, then 1 ms frames, at 8x on a clock that stands still (no budget spent):
    the short frames' owed limit (32.5 of them) leaves more than the cap's worth, so the tick
    stops at the cap, not for want of owed time.
    """
    controls = ReplayControls(total_frames=10**9)
    controls.speed = ReplayControls.MAX_SPEED
    viewer = ReplayViewer(controls=controls, measured_seconds=lambda: 0.0)
    viewer.ticks_externally = True
    now = viewer.begin_tick(is_inner_running=True)
    assert now is not None
    viewer.accrue(now=now, is_inner_running=True)
    long_frame_seconds = 0.1
    short_frame_seconds = 0.001
    viewer.accumulated_seconds = 3.2
    frames_run = run_open_tick(
        viewer=viewer,
        inner_frame_seconds_for=lambda frame: (
            long_frame_seconds if frame == 0 else short_frame_seconds
        ),
    )
    assert frames_run == MAX_INNER_FRAMES_PER_TICK
    # Owed time was left: the cap, not the accumulator, closed the tick
    assert viewer.accumulated_seconds >= short_frame_seconds


# A steady 60 FPS recording's frame, for the schedules below
STEADY_FRAME_SECONDS = 1 / 60
# Committed recordings whose live run stuttered and whose pacing caught up with a short next
# frame (scripts/replay_schedule.py found them): each pair is (the long frame, the short one)
STUTTER_PAIRS = {
    'brave_adventurer_golden_classic_frame_460': (0.03402, 0.00744),
    'paddleslap_rally_frame_286': (0.02863, 0.00151),
}


class ScheduleRun(BaseModel):
    """The viewer's schedule over a run of inner frames (``run_schedule``).

    Attributes:
        frames_by_tick: The frames each tick ran (it presents the last).
        accumulated_by_tick: The accumulator after each tick.
        behind_by_tick: Whether the viewer was behind (``is_behind``) after each tick.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    frames_by_tick: list[list[int]]
    accumulated_by_tick: list[float]
    behind_by_tick: list[bool]

    def replay_lag_seconds(self: Self, *, inner_frame_seconds: list[float], speed: float) -> float:
        """Return how much later than real time the replay ended (negative: earlier).

        The first tick, at time 0, owes nothing but the half-frame phase; the recording's
        frames last ``sum(inner_frame_seconds) / speed`` of real time.

        Returns:
            Seconds.

        """
        replay_seconds = (len(self.frames_by_tick) - 1) * CONTROL_TICK_SECONDS
        return replay_seconds - sum(inner_frame_seconds) / speed


def run_schedule(
    *, inner_frame_seconds: list[float], speed: float = 1.0, stall_before_tick: int | None = None
) -> ScheduleRun:
    """Run the viewer's accumulator over inner frames on an ideal clock, ticked externally.

    Each tick is exactly ``CONTROL_TICK_SECONDS`` after the last and inner frames cost no time,
    as scripts/replay_schedule.py runs it (the replay starts running, no start screen).

    Args:
        inner_frame_seconds: Each inner frame's recorded duration, in order.
        speed: The replay speed.
        stall_before_tick: The tick that opens half a second late (a stall), or None.

    Returns:
        The schedule.

    """
    given = {'seconds': 0.0}
    controls = ReplayControls(total_frames=len(inner_frame_seconds))
    controls.speed = speed
    viewer = ReplayViewer(controls=controls, measured_seconds=lambda: given['seconds'])
    viewer.ticks_externally = True
    frames_by_tick: list[list[int]] = []
    accumulated_by_tick: list[float] = []
    behind_by_tick: list[bool] = []
    frame_index = 0
    while frame_index < len(inner_frame_seconds):
        if stall_before_tick == len(frames_by_tick):
            given['seconds'] += 0.5
        now = viewer.begin_tick(is_inner_running=True)
        assert now is not None
        viewer.accrue(now=now, is_inner_running=True)
        frames_run: list[int] = []
        while frame_index < len(inner_frame_seconds) and viewer.should_run_inner_frame(
            inner_frame_seconds=inner_frame_seconds[frame_index],
            is_inner_over=False,
            is_first_inner_frame=frame_index == 0,
        ):
            frames_run.append(frame_index)
            frame_index += 1
        frames_by_tick.append(frames_run)
        accumulated_by_tick.append(viewer.accumulated_seconds)
        behind_by_tick.append(viewer.is_behind)
        given['seconds'] += CONTROL_TICK_SECONDS
    return ScheduleRun(
        frames_by_tick=frames_by_tick,
        accumulated_by_tick=accumulated_by_tick,
        behind_by_tick=behind_by_tick,
    )


def never_presented(*, frames_by_tick: list[list[int]]) -> list[int]:
    """Return the frames that ran in a tick where a later frame ran too.

    Returns:
        The frames, in order.

    """
    return [frame for frames_run in frames_by_tick for frame in frames_run[:-1]]


def stuttered_recording(*, long_seconds: float, short_seconds: float) -> list[float]:
    """Return steady frames with one long frame and its short catch-up frame in the middle.

    Returns:
        Inner frame durations.

    """
    return [STEADY_FRAME_SECONDS] * 30 + [long_seconds, short_seconds] + [STEADY_FRAME_SECONDS] * 30


# At 2x (measured on the accumulator before rule 2's one-frame limit): the first tick owes the
# half-frame phase, then two frames a tick, a frame shorter than a tick (30) and its short
# catch-up frame (31) sharing one
TWO_TIMES_SCHEDULE = [[]] + [[2 * tick, 2 * tick + 1] for tick in range(31)]


class TestEveryFrameIsShownUpToNormalSpeed:
    """Up to 1x a tick runs one inner frame unless the replay is genuinely behind (rule 2).

    A live run that stuttered (a long frame) and caught up with a short next frame showed both;
    a watched replay at 1x must not run the two in one tick and present only the short one.
    """

    @pytest.mark.parametrize(
        ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
    )
    def test_a_long_frame_followed_by_a_short_one_is_presented(self, long_seconds, short_seconds):
        frames_by_tick = run_schedule(
            inner_frame_seconds=stuttered_recording(
                long_seconds=long_seconds, short_seconds=short_seconds
            )
        ).frames_by_tick
        assert never_presented(frames_by_tick=frames_by_tick) == []

    @pytest.mark.parametrize('speed', [0.25, 0.5])
    @pytest.mark.parametrize(
        ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
    )
    def test_slower_speeds_present_every_frame_too(self, long_seconds, short_seconds, speed):
        frames_by_tick = run_schedule(
            inner_frame_seconds=stuttered_recording(
                long_seconds=long_seconds, short_seconds=short_seconds
            ),
            speed=speed,
        ).frames_by_tick
        assert never_presented(frames_by_tick=frames_by_tick) == []

    def test_a_steady_recording_runs_one_frame_a_tick(self):
        frames_by_tick = run_schedule(
            inner_frame_seconds=[STEADY_FRAME_SECONDS] * 120
        ).frames_by_tick
        # The first tick owes only the half-frame phase; then exactly one frame a tick
        assert frames_by_tick[0] == []
        assert [len(frames_run) for frames_run in frames_by_tick[1:]] == [1] * 120

    @pytest.mark.parametrize(
        ('long_seconds', 'short_seconds'), STUTTER_PAIRS.values(), ids=STUTTER_PAIRS.keys()
    )
    def test_the_replay_falls_at_most_one_tick_behind_after_a_catch_up_frame(
        self, long_seconds, short_seconds
    ):
        """The short frame waits for its own tick: the owed time carries, at most one tick more."""
        inner_frame_seconds = stuttered_recording(
            long_seconds=long_seconds, short_seconds=short_seconds
        )
        schedule = run_schedule(inner_frame_seconds=inner_frame_seconds)
        frames_by_tick = schedule.frames_by_tick
        accumulated_by_tick = schedule.accumulated_by_tick
        frames_run = 0
        for frames_this_tick, accumulated_seconds in zip(
            frames_by_tick, accumulated_by_tick, strict=True
        ):
            frames_run += len(frames_this_tick)
            next_frame_seconds = (
                inner_frame_seconds[frames_run]
                if frames_run < len(inner_frame_seconds)
                else STEADY_FRAME_SECONDS
            )
            # Owed after the tick: less than the next frame plus one tick
            assert accumulated_seconds < next_frame_seconds + CONTROL_TICK_SECONDS
        # The replay ends no more than one tick later than real time would end it
        recording_seconds = sum(inner_frame_seconds)
        replay_seconds = (len(frames_by_tick) - 1) * CONTROL_TICK_SECONDS
        assert replay_seconds - recording_seconds <= CONTROL_TICK_SECONDS + STEADY_FRAME_SECONDS

    def test_a_genuine_stall_still_catches_up_in_one_bounded_burst(self):
        schedule = run_schedule(
            inner_frame_seconds=[STEADY_FRAME_SECONDS] * 200, stall_before_tick=20
        )
        frames_per_tick = [len(frames_run) for frames_run in schedule.frames_by_tick]
        # The stall's tick owes the half second and its own tick plus the 8.3 ms phase (525 ms,
        # under the owed limit's 32.5 frames): it runs frames until less than a frame plus a
        # tick (33.3 ms) is owed, so 30 of them, 25 ms carried
        assert frames_per_tick[20] == 30
        assert schedule.accumulated_by_tick[20] == pytest.approx(0.025)
        # Then one frame a tick again
        assert set(frames_per_tick[21:]) == {1}

    def test_above_normal_speed_frames_shorter_than_a_tick_run_several_a_tick(self):
        """At 2x rally's 28.63 ms frame is shorter than a tick (33.3 ms of inner time).

        It shares a tick with its catch-up frame, as fast-forward always ran them.
        """
        frames_by_tick = run_schedule(
            inner_frame_seconds=stuttered_recording(long_seconds=0.02863, short_seconds=0.00151),
            speed=2.0,
        ).frames_by_tick
        assert frames_by_tick == TWO_TIMES_SCHEDULE


class TestAboveNormalSpeedAFrameLastingATickIsPresented:
    """Rule 2 at every speed for a frame lasting at least a tick of inner time at that speed.

    After such a frame (recorded duration >= speed x the tick period) the next frame in the same
    tick runs only when the replay is behind; frames shorter than that keep fast-forward's
    several a tick.
    """

    def test_golden_classics_long_frame_is_presented_at_twice_the_speed(self):
        """34.02 ms then 7.44 ms (frames 30 and 31): at 2x the long frame lasts 17 ms real."""
        frames_by_tick = run_schedule(
            inner_frame_seconds=stuttered_recording(long_seconds=0.03402, short_seconds=0.00744),
            speed=2.0,
        ).frames_by_tick
        assert 30 not in never_presented(frames_by_tick=frames_by_tick)

    def test_at_four_times_the_same_frame_is_shorter_than_a_tick(self):
        """At 4x a tick is 66.7 ms of inner time: the 34.02 ms frame (8.5 ms real) is shorter.

        Not protected, it runs with the frames after it, the last presented.
        """
        frames_by_tick = run_schedule(
            inner_frame_seconds=stuttered_recording(long_seconds=0.03402, short_seconds=0.00744),
            speed=4.0,
        ).frames_by_tick
        assert 30 in never_presented(frames_by_tick=frames_by_tick)

    @pytest.mark.parametrize('speed', [2.0, 4.0, 8.0])
    def test_steady_60_fps_runs_the_speeds_frames_a_tick(self, speed):
        """Frames shorter than a tick at the speed: unchanged, `speed` frames a tick."""
        frames_by_tick = run_schedule(
            inner_frame_seconds=[STEADY_FRAME_SECONDS] * 800, speed=speed
        ).frames_by_tick
        frames_per_tick = [len(frames_run) for frames_run in frames_by_tick]
        assert set(frames_per_tick[2:-1]) == {int(speed)}


def uniform_frames(
    *, shortest_seconds: float, longest_seconds: float, frame_count: int
) -> list[float]:
    """Return frame times drawn uniformly between two lengths (seeded, the same every run).

    Returns:
        Recorded dts.

    """
    frame_times = random.Random(1)
    return [frame_times.uniform(shortest_seconds, longest_seconds) for _ in range(frame_count)]


class FastRecording(BaseModel):
    """A recording far faster than the viewer's tick, and the speed it is watched at.

    Attributes:
        target_fps: The ``--target-fps`` it was recorded with (its header's ``target_fps``
            option; 0.0 is uncapped).
        frame_seconds: Every frame's recorded dt (frame 0's is 0.0, as a live recording's).
        speed: The replay speed.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    target_fps: float
    frame_seconds: list[float]
    speed: float


# Recordings of games far faster than the viewer's 60 Hz tick (--target-fps N, or uncapped): a
# tick runs several of their frames and presents the last, and the replay must keep their rate
FAST_RECORDINGS = {
    'hit_its_1000_fps_target_at_1x': FastRecording(
        target_fps=1000.0, frame_seconds=[0.0] + [1 / 1000] * 10_000, speed=1.0
    ),
    'hit_its_1500_fps_target_at_1x': FastRecording(
        target_fps=1500.0, frame_seconds=[0.0] + [1 / 1500] * 15_000, speed=1.0
    ),
    'ran_at_1200_fps_under_its_1500_fps_target_at_1x': FastRecording(
        target_fps=1500.0, frame_seconds=[0.0] + [1 / 1200] * 12_000, speed=1.0
    ),
    'uncapped_0.3_to_2_ms_frames_at_1x': FastRecording(
        target_fps=0.0,
        frame_seconds=[
            0.0,
            *uniform_frames(shortest_seconds=0.0003, longest_seconds=0.002, frame_count=10_000),
        ],
        speed=1.0,
    ),
    'hit_its_2000_fps_target_at_half_speed': FastRecording(
        target_fps=2000.0, frame_seconds=[0.0] + [1 / 2000] * 10_000, speed=0.5
    ),
    # More frames a tick (50) than MAX_INNER_FRAMES_PER_TICK: up to 1x only the tick's work
    # budget limits them
    'hit_its_3000_fps_target_at_1x': FastRecording(
        target_fps=3000.0, frame_seconds=[0.0] + [1 / 3000] * 30_000, speed=1.0
    ),
    # An uncapped game's recording (--target-fps 0) at about 3100 FPS, as PaddleSlap achieves
    'uncapped_about_3100_fps_at_1x': FastRecording(
        target_fps=0.0,
        frame_seconds=[
            0.0,
            *uniform_frames(shortest_seconds=0.00025, longest_seconds=0.0004, frame_count=31_000),
        ],
        speed=1.0,
    ),
}


def write_fast_recording(*, recording: FastRecording, path: Path) -> Path:
    """Write the recording with its target FPS in the header's options, as a live one holds it.

    Returns:
        ``path``.

    """
    write_trace(
        trace={
            'game': 'stand_in',
            OPTIONS_HEADER_FIELD: {'target_fps': recording.target_fps},
            FRAMES_FIELD: [
                {'frame': frame_index, DT_FIELD: dt, 'scene': 'StandInScene', 'sprites': []}
                for frame_index, dt in enumerate(recording.frame_seconds)
            ],
        },
        path=path,
    )
    return path


def inner_frame_seconds_of(*, recorded: RecordedFrames) -> list[float]:
    """Return each frame's duration as a watched replay gives it to the viewer.

    The rule of ``ReplaySources._inner_frame_seconds`` (glitchygames/replay/driver.py, rule 4):
    a frame lasts its next frame's dt, the last frame its own.

    Returns:
        Seconds, one per frame.

    """
    last_frame = recorded.frame_count - 1
    return [
        recorded.recorded_dt(frame_index=min(frame_index + 1, last_frame))
        for frame_index in range(recorded.frame_count)
    ]


def required_inner_frames_per_second(*, header: dict[str, Any], recorded: RecordedFrames) -> float:
    """Return the rate a watched replay at 1x must run a recording's frames at.

    The rate the recording achieved (its frames over the sum of their recorded dts), capped by
    its target FPS (the header's ``target_fps`` option; 0 is uncapped).

    Returns:
        Inner frames per recorded second.

    """
    recorded_seconds = sum(
        recorded.recorded_dt(frame_index=frame_index) for frame_index in range(recorded.frame_count)
    )
    achieved_fps = recorded.frame_count / recorded_seconds
    target_fps = float(header[OPTIONS_HEADER_FIELD]['target_fps'])
    return min(target_fps, achieved_fps) if target_fps > 0 else achieved_fps


class RateCheck(BaseModel):
    """Whether a watched replay kept a recording's rate (``check_watched_rate``).

    Attributes:
        required_frames_per_second: Inner frames per real second the replay must run: the
            recording's achieved rate capped by its target FPS, times the speed it is watched at.
        real_seconds: The real time the replay took to run every frame.
        allowed_seconds: The most real time that rate allows, with the tolerance: two ticks and
            one recorded frame over the run (rule 2 lets the replay owe under a frame plus a
            tick when a tick closes, a constant lag of up to a tick, and the run's end is read
            at a tick, so up to one more).

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    required_frames_per_second: float
    real_seconds: float
    allowed_seconds: float

    @property
    def keeps_rate(self: Self) -> bool:
        """True when the replay ran its frames at least at the required rate (tolerance kept)."""
        return self.real_seconds <= self.allowed_seconds


def check_watched_rate(
    *, recording: FastRecording, path: Path, replayed_at_speed: float | None = None
) -> RateCheck:
    """Write a recording, replay it watched (the viewer's schedule) and check its rate.

    Args:
        recording: The recording and the speed it must keep its rate at.
        path: Where to write it.
        replayed_at_speed: The speed the replay actually runs at (a slower one stands for a
            replay that cannot keep up); None is the recording's speed.

    Returns:
        The check.

    """
    write_fast_recording(recording=recording, path=path)
    trace = read_trace_result(path=path).trace
    recorded = RecordedFrames(frames=trace[FRAMES_FIELD], is_truncated=False)
    inner_frame_seconds = inner_frame_seconds_of(recorded=recorded)
    schedule = run_schedule(
        inner_frame_seconds=inner_frame_seconds,
        speed=recording.speed if replayed_at_speed is None else replayed_at_speed,
    )
    required_frames_per_second = (
        required_inner_frames_per_second(header=trace, recorded=recorded) * recording.speed
    )
    tolerance_seconds = 2 * CONTROL_TICK_SECONDS + max(inner_frame_seconds) / recording.speed
    return RateCheck(
        required_frames_per_second=required_frames_per_second,
        real_seconds=(len(schedule.frames_by_tick) - 1) * CONTROL_TICK_SECONDS,
        allowed_seconds=recorded.frame_count / required_frames_per_second + tolerance_seconds,
    )


class TestRecordingsFasterThanTheTickKeepTheirRate:
    """Up to 1x the owed limit never stops a tick short of what rule 2 lets it run.

    With frames shorter than about 1.1 ms, 32.5 frames' worth fell below a frame plus two ticks
    of inner time: every tick was capped, fell behind and the replay ran in slow motion.
    """

    @pytest.mark.parametrize('recording', FAST_RECORDINGS.values(), ids=FAST_RECORDINGS.keys())
    def test_it_runs_at_least_its_recorded_rate_capped_by_its_target(self, recording, tmp_path):
        """Inner frames per real second: at least min(target, achieved) times the speed."""
        check = check_watched_rate(recording=recording, path=tmp_path / 'fast.jsonl.gz')
        assert check.keeps_rate, check

    def test_a_1500_fps_recording_keeps_1500(self, tmp_path):
        """Recorded at --target-fps 1500 and achieving it: watched at 1x, 1500 frames a second."""
        check = check_watched_rate(
            recording=FAST_RECORDINGS['hit_its_1500_fps_target_at_1x'],
            path=tmp_path / 'fast.jsonl.gz',
        )
        assert check.required_frames_per_second == pytest.approx(1500)
        assert check.keeps_rate, check

    def test_a_1500_fps_recording_replayed_at_1200_fails(self, tmp_path):
        """A replay of it managing only 1200 frames a second (0.8x) fails the check."""
        check = check_watched_rate(
            recording=FAST_RECORDINGS['hit_its_1500_fps_target_at_1x'],
            path=tmp_path / 'fast.jsonl.gz',
            replayed_at_speed=0.8,
        )
        assert check.required_frames_per_second == pytest.approx(1500)
        assert not check.keeps_rate, check

    def test_a_1500_fps_target_recording_that_ran_at_1200_keeps_1200(self, tmp_path):
        """Under its target, the rate it achieved is the one to keep: 1200 frames a second."""
        check = check_watched_rate(
            recording=FAST_RECORDINGS['ran_at_1200_fps_under_its_1500_fps_target_at_1x'],
            path=tmp_path / 'fast.jsonl.gz',
        )
        assert check.required_frames_per_second == pytest.approx(1200, rel=0.001)
        assert check.keeps_rate, check

    def test_a_3000_fps_recording_keeps_3000(self, tmp_path):
        """50 frames a tick at 1x, more than MAX_INNER_FRAMES_PER_TICK: only the budget limits."""
        check = check_watched_rate(
            recording=FAST_RECORDINGS['hit_its_3000_fps_target_at_1x'],
            path=tmp_path / 'fast.jsonl.gz',
        )
        assert check.required_frames_per_second == pytest.approx(3000)
        assert check.keeps_rate, check

    def test_a_stall_runs_one_bounded_burst_of_its_short_frames(self):
        """Up to 1x the owed limit, not a frame count, bounds a stall's burst.

        For 1/3000 s frames the owed limit is its floor, the frame plus two ticks (33.67 ms):
        the stall's tick runs until less than the frame plus a tick is owed, so 50 frames (a
        tick's worth, as every tick), and the rest of the half second is dropped (behind).
        """
        schedule = run_schedule(inner_frame_seconds=[1 / 3000] * 3000, stall_before_tick=20)
        frames_per_tick = [len(frames_run) for frames_run in schedule.frames_by_tick]
        assert frames_per_tick[20] == 50
        # Every tick once the phase has settled (from tick 3) runs the same 50
        assert set(frames_per_tick[3:20]) == set(frames_per_tick[21:-1]) == {50}
        assert not schedule.behind_by_tick[19]
        assert schedule.behind_by_tick[20]

    @pytest.mark.parametrize('recording', FAST_RECORDINGS.values(), ids=FAST_RECORDINGS.keys())
    def test_it_never_falls_behind(self, recording):
        inner_frame_seconds = [*recording.frame_seconds[1:], recording.frame_seconds[-1]]
        schedule = run_schedule(inner_frame_seconds=inner_frame_seconds, speed=recording.speed)
        assert not any(schedule.behind_by_tick)


def viewer_owing_for_a_first_frame(*, speed: float, owed_seconds: float) -> ReplayViewer:
    """Return a viewer whose open tick has run no frame yet and owes exactly ``owed_seconds``.

    The half-frame phase is spent first, on a zero-length frame in an earlier tick, so the
    accumulator holds only what is set.

    Returns:
        The viewer.

    """
    controls = ReplayControls(total_frames=10**9)
    controls.speed = speed
    viewer = ReplayViewer(controls=controls, measured_seconds=lambda: 0.0)
    viewer.ticks_externally = True
    for _ in range(2):
        now = viewer.begin_tick(is_inner_running=True)
        assert now is not None
        viewer.accrue(now=now, is_inner_running=True)
        run_open_tick(viewer=viewer, inner_frame_seconds_for=lambda _frame: 0.0)
    now = viewer.begin_tick(is_inner_running=True)
    assert now is not None
    viewer.accrue(now=now, is_inner_running=True)
    viewer.accumulated_seconds = owed_seconds
    return viewer


class TestEachInnerFrameSaysWhetherItRanBehind:
    """``last_inner_frame_ran_behind``: the accumulator owed the frame plus a tick of inner time.

    The viewer's own condition, at every speed: owed >= the frame's recorded duration plus the
    speed times the tick period (``CONTROL_TICK_SECONDS``). The schedule tool and its guard read
    it to tell a frame a tick skipped because the replay was behind from one it hid.
    """

    @pytest.mark.parametrize('speed', [0.5, 1.0, 2.0])
    def test_owing_the_frame_plus_a_tick_of_inner_time_is_behind(self, speed):
        viewer = viewer_owing_for_a_first_frame(
            speed=speed, owed_seconds=STEADY_FRAME_SECONDS + speed * CONTROL_TICK_SECONDS
        )
        assert viewer.should_run_inner_frame(
            inner_frame_seconds=STEADY_FRAME_SECONDS,
            is_inner_over=False,
            is_first_inner_frame=False,
        )
        assert viewer.last_inner_frame_ran_behind

    @pytest.mark.parametrize('speed', [0.5, 1.0, 2.0])
    def test_owing_a_little_less_is_not_behind(self, speed):
        viewer = viewer_owing_for_a_first_frame(
            speed=speed,
            owed_seconds=(STEADY_FRAME_SECONDS + speed * CONTROL_TICK_SECONDS) * 0.999,
        )
        assert viewer.should_run_inner_frame(
            inner_frame_seconds=STEADY_FRAME_SECONDS,
            is_inner_over=False,
            is_first_inner_frame=False,
        )
        assert not viewer.last_inner_frame_ran_behind

    def test_a_frame_run_without_the_accumulator_is_not_behind(self):
        """A paused step runs one frame whatever is owed: never behind, after a frame that was."""
        viewer = viewer_owing_for_a_first_frame(speed=1.0, owed_seconds=0.1)
        assert viewer.should_run_inner_frame(
            inner_frame_seconds=STEADY_FRAME_SECONDS,
            is_inner_over=False,
            is_first_inner_frame=False,
        )
        assert viewer.last_inner_frame_ran_behind
        viewer.controls.paused = True
        viewer.controls.step_requested = True
        assert viewer.should_run_inner_frame(
            inner_frame_seconds=STEADY_FRAME_SECONDS,
            is_inner_over=False,
            is_first_inner_frame=False,
        )
        assert not viewer.last_inner_frame_ran_behind
