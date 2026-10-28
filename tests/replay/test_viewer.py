"""The replay viewer's outer loop (glitchygames/replay/viewer.py), on a fake measured clock.

These drive ``ReplayViewer`` directly, as ``ReplaySources.hold_frame`` does, with inner frames
that cost a chosen amount of real time; tests/world/test_gameplay_replay.py drives it through a
real replay.
"""

from __future__ import annotations

import collections
import random
from time import perf_counter_ns

import pytest

from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, ReplayControls
from glitchygames.replay.viewer import (
    BEHIND_SPEED_FRACTION,
    EFFECTIVE_SPEED_WINDOW_TICKS,
    INNER_FRAME_BUDGET_SECONDS,
    MAX_INNER_FRAMES_PER_TICK,
    ReplayViewer,
)

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
        mocker.patch.object(viewer_module, 'measured_seconds', side_effect=self.read)
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
        frames = 0
        while viewer.should_run_inner_frame(
            inner_frame_seconds=inner_frame_seconds, is_inner_over=False, is_first_inner_frame=False
        ):
            frames += 1
            time.now += inner_frame_cost_seconds
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
    """A two-second stall runs one tick of MAX_INNER_FRAMES_PER_TICK, then the normal pace."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer()
    run_ticks(viewer=viewer, time=time, tick_count=10)
    time.now += 2.0  # a two-second stall: 120 frames owed, at most one tick's worth are kept
    frames_per_tick = run_ticks(viewer=viewer, time=time, tick_count=30)
    assert frames_per_tick[MAX_INNER_FRAMES_PER_TICK] == 1
    assert max(frames_per_tick) == MAX_INNER_FRAMES_PER_TICK
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
            while viewer.should_run_inner_frame(
                inner_frame_seconds=RECORDED_FRAME_SECONDS,
                is_inner_over=False,
                is_first_inner_frame=False,
            ):
                frames_run += 1
            time.now += 1 / display_hertz

        real_seconds = (tick_count - 1) / display_hertz
        assert abs(frames_run - real_seconds / RECORDED_FRAME_SECONDS) <= 1
        assert not time.sleeps
