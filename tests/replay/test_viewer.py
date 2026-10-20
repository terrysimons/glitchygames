"""The replay viewer's outer loop (glitchygames/replay/viewer.py), on a fake measured clock.

These drive ``ReplayViewer`` directly, as ``ReplaySources.hold_frame`` does, with inner frames
that cost a chosen amount of real time; tests/world/test_gameplay_replay.py drives it through a
real replay.
"""

from __future__ import annotations

import collections
import random

import pytest

from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.controls import CONTROL_TICK_SECONDS, ReplayControls
from glitchygames.replay.viewer import (
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
        mocker.patch.object(viewer_module, 'sleep_for', side_effect=self.sleep)

    def read(self) -> float:
        """Return the fake time.

        Returns:
            Seconds.

        """
        return self.now

    def sleep(self, *, seconds: float) -> None:
        """Sleep ``seconds``, waking up a little late at random (sleep_for's signature)."""
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
        now = viewer.begin_tick()
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


def test_keeping_up_is_not_behind(mocker):
    """A viewer that keeps up is not behind, and its effective speed is the speed."""
    time = FakeTime(mocker=mocker)
    viewer = new_viewer(speed=2.0)
    run_ticks(viewer=viewer, time=time, tick_count=120)
    assert not viewer.is_behind
    assert viewer.effective_speed() == pytest.approx(2.0, rel=0.05)
