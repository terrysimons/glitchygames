"""The recorded-frame pacer and the tick budget (glitchygames/replay/pacer.py).

Written to the rules of the watched replay's contract (glitchygames/replay/viewer.py's module
docstring, rules 1 and 2), which the pacer now carries for the viewer and for any other player
of a recording (an Arcade tile): the owing, the owed limit, rule 2's one frame a tick unless
behind, the behind window and the effective speed. The budget's clock is a fake; the pacer reads
no clock of its own.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

import glitchygames
from glitchygames.replay import viewer as viewer_module
from glitchygames.replay.pacer import (
    BEHIND_SPEED_FRACTION,
    EFFECTIVE_SPEED_WINDOW_TICKS,
    INNER_FRAME_BUDGET_SECONDS,
    MAX_OWED_INNER_FRAMES,
    STALL_TICK_SECONDS,
    RecordedFramePacer,
    TickBudget,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# The viewer's 60 Hz tick and a 60 FPS recording's frame
SIXTY_HERTZ_SECONDS = 1 / 60
# A browser on a 120 Hz display ticks this often
ONE_HUNDRED_TWENTY_HERTZ_SECONDS = 1 / 120
# More frames than any test's tick runs, so a rule that never ends a tick fails instead of hanging
MOST_FRAMES_A_TEST_TICK_RUNS = 10_000


class FakeMeasuredClock:
    """A real-time clock a test moves by hand."""

    def __init__(self, *, now: float = 0.0) -> None:
        """Start at ``now``.

        Args:
            now: Seconds.

        """
        self.now = now

    def read(self) -> float:
        """Return the fake time.

        Returns:
            Seconds.

        """
        return self.now


def budget_never_spent() -> TickBudget:
    """A tick budget on a clock that stands still: frames costing nothing never spend it.

    Returns:
        The budget.

    """
    return TickBudget(length_seconds=INNER_FRAME_BUDGET_SECONDS, measured_seconds=lambda: 0.0)


def budget_already_spent() -> TickBudget:
    """A tick budget whose clock is already past its length.

    Returns:
        The budget.

    """
    return TickBudget(
        length_seconds=INNER_FRAME_BUDGET_SECONDS,
        measured_seconds=lambda: 1.0,
        started_at_seconds=0.0,
    )


def steady_sixty(_frame: int) -> float:
    """A 60 FPS recording's frame duration.

    Returns:
        Seconds.

    """
    return SIXTY_HERTZ_SECONDS


class Player:
    """A test's player of a recording: it runs the next frame each time the pacer allows one.

    Attributes:
        pacer: The pacer.
        frame_seconds_for: The recorded duration of frame N.
        speed: The playback speed (a test may change it between ticks).
        next_frame: The frame the next tick would run first.

    """

    def __init__(
        self,
        *,
        frame_seconds_for: Callable[[int], float] = steady_sixty,
        speed: float = 1.0,
        nominal_tick_seconds: float = SIXTY_HERTZ_SECONDS,
    ) -> None:
        """Start at frame 0.

        Args:
            frame_seconds_for: The recorded duration of frame N.
            speed: The playback speed.
            nominal_tick_seconds: The pacer's tick period.

        """
        self.pacer = RecordedFramePacer(nominal_tick_seconds=nominal_tick_seconds)
        self.frame_seconds_for = frame_seconds_for
        self.speed = speed
        self.next_frame = 0

    def tick(
        self,
        *,
        elapsed_seconds: float,
        budget: TickBudget | None = None,
        after_each_frame: Callable[[], None] | None = None,
    ) -> list[int]:
        """Pay one tick's elapsed time, then run the frames the pacer allows.

        Args:
            elapsed_seconds: The real time the tick pays for.
            budget: The tick's real-time budget; None never spends.
            after_each_frame: Called after each frame runs (a frame costing real time), or None.

        Returns:
            The frames the tick ran, in order.

        """
        tick_budget = budget_never_spent() if budget is None else budget
        self.pacer.pay(elapsed_seconds=elapsed_seconds, speed=self.speed, is_running=True)
        frames_run: list[int] = []
        for _ in range(MOST_FRAMES_A_TEST_TICK_RUNS):
            if not self.pacer.should_run_frame(
                frame_seconds=self.frame_seconds_for(self.next_frame),
                speed=self.speed,
                budget=tick_budget,
            ):
                return frames_run
            frames_run.append(self.next_frame)
            self.next_frame += 1
            if after_each_frame is not None:
                after_each_frame()
        pytest.fail(f'a tick ran more than {MOST_FRAMES_A_TEST_TICK_RUNS} frames')

    def ticks(self, *, tick_count: int, elapsed_seconds: float) -> list[list[int]]:
        """Run ``tick_count`` ticks of the same elapsed time, budgets never spent.

        Returns:
            Each tick's frames run.

        """
        return [self.tick(elapsed_seconds=elapsed_seconds) for _ in range(tick_count)]


def with_a_long_frame_and_its_catch_up(*, long_seconds: float) -> Callable[[int], float]:
    """A 60 FPS recording whose frame 10 ran long and whose frame 11 caught up (1 ms).

    Returns:
        Frame N's recorded duration.

    """

    def frame_seconds_for(frame: int) -> float:
        if frame == 10:
            return long_seconds
        if frame == 11:
            return 0.001
        return SIXTY_HERTZ_SECONDS

    return frame_seconds_for


def shares_a_tick(*, ticks: list[list[int]], first: int, second: int) -> bool:
    """Whether some tick ran both frames.

    Returns:
        True when one tick ran ``first`` and ``second``.

    """
    return any(first in frames and second in frames for frames in ticks)


class TestOwing:
    """Rule 1 and rule 2: owed time from elapsed time times the speed, one frame a tick."""

    def test_at_normal_speed_a_frame_is_owed_each_tick_and_exactly_one_runs(self):
        """At 1x a 60 FPS recording on 60 Hz ticks runs exactly one frame every tick."""
        player = Player()
        ticks = player.ticks(tick_count=600, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert [len(frames) for frames in ticks] == [1] * 600
        assert not player.pacer.is_behind

    @pytest.mark.parametrize('speed', [0.25, 0.5, 1.0])
    def test_up_to_normal_speed_a_long_frame_and_its_catch_up_never_share_a_tick(self, speed):
        """A long frame and the short frame after it are each presented by their own tick."""
        player = Player(
            frame_seconds_for=with_a_long_frame_and_its_catch_up(long_seconds=0.05), speed=speed
        )
        ticks = player.ticks(tick_count=200, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert player.next_frame > 12
        assert not shares_a_tick(ticks=ticks, first=10, second=11)

    def test_above_normal_speed_a_frame_lasting_a_tick_of_inner_time_keeps_its_tick(self):
        """At 2x a 50 ms frame lasts more than a tick of inner time (33 ms): it is presented."""
        player = Player(
            frame_seconds_for=with_a_long_frame_and_its_catch_up(long_seconds=0.05), speed=2.0
        )
        ticks = player.ticks(tick_count=100, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert player.next_frame > 12
        assert not shares_a_tick(ticks=ticks, first=10, second=11)

    def test_above_normal_speed_a_frame_shorter_than_a_tick_of_inner_time_may_share(self):
        """At 4x the same 50 ms frame is shorter than a tick of inner time (67 ms): fast-forward."""
        player = Player(
            frame_seconds_for=with_a_long_frame_and_its_catch_up(long_seconds=0.05), speed=4.0
        )
        ticks = player.ticks(tick_count=100, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert shares_a_tick(ticks=ticks, first=10, second=11)

    def test_a_frame_of_zero_duration_owes_nothing(self):
        """A frame recorded with no duration runs without consuming owed time."""
        pacer = RecordedFramePacer(nominal_tick_seconds=SIXTY_HERTZ_SECONDS)
        pacer.pay(elapsed_seconds=SIXTY_HERTZ_SECONDS, speed=1.0, is_running=True)
        owed_before = pacer.accumulated_seconds
        assert pacer.should_run_frame(frame_seconds=0.0, speed=1.0, budget=budget_never_spent())
        assert pacer.accumulated_seconds == owed_before

    def test_a_frame_of_zero_duration_never_falls_behind(self):
        """Neither the owed limit nor a spent budget makes a zero-length frame fall behind."""
        pacer = RecordedFramePacer(nominal_tick_seconds=SIXTY_HERTZ_SECONDS)
        pacer.pay(elapsed_seconds=0.2, speed=1.0, is_running=True)
        assert not pacer.should_run_frame(
            frame_seconds=0.0, speed=1.0, budget=budget_already_spent()
        )
        assert pacer.accumulated_seconds == pytest.approx(0.2)
        assert not pacer.is_behind

    def test_a_frame_is_not_run_before_it_is_owed(self):
        """The first tick owes half a frame (the phase), so a whole frame waits for the next."""
        player = Player()
        assert player.ticks(tick_count=2, elapsed_seconds=0.0) == [[], []]
        assert player.pacer.accumulated_seconds == pytest.approx(SIXTY_HERTZ_SECONDS / 2)


class TestTheOwedLimit:
    """Owed time past the owed limit is dropped; a stall pays as one nominal tick."""

    def test_owed_time_past_the_limit_is_dropped_and_the_pacer_is_behind_for_a_second(self):
        """A two-second stall keeps 32.5 frames, drops the rest, and is behind for 60 ticks."""
        player = Player()
        stall_frames = player.tick(elapsed_seconds=2.0)
        owed_limit_seconds = (MAX_OWED_INNER_FRAMES + 0.5) * SIXTY_HERTZ_SECONDS
        assert player.pacer.dropped_seconds == pytest.approx(
            2.0 + SIXTY_HERTZ_SECONDS / 2 - owed_limit_seconds
        )
        assert 0 < len(stall_frames) <= MAX_OWED_INNER_FRAMES + 1
        behind_after_each_tick = []
        for _ in range(EFFECTIVE_SPEED_WINDOW_TICKS):
            player.tick(elapsed_seconds=SIXTY_HERTZ_SECONDS)
            behind_after_each_tick.append(player.pacer.is_behind)
        assert behind_after_each_tick == [True] * (EFFECTIVE_SPEED_WINDOW_TICKS - 1) + [False]

    def test_the_accumulator_never_owes_more_than_the_limit(self):
        """However much is paid, what is owed after asking for a frame stays within the limit."""
        pacer = RecordedFramePacer(nominal_tick_seconds=SIXTY_HERTZ_SECONDS)
        pacer.pay(elapsed_seconds=10.0, speed=8.0, is_running=True)
        pacer.should_run_frame(
            frame_seconds=SIXTY_HERTZ_SECONDS, speed=8.0, budget=budget_already_spent()
        )
        assert pacer.accumulated_seconds <= (MAX_OWED_INNER_FRAMES + 0.5) * SIXTY_HERTZ_SECONDS

    def test_a_stall_pays_as_one_nominal_tick(self):
        """Short frames: a stall's burst is bounded as at 60 Hz; a slow tick keeps its rate.

        1 ms frames: the owed limit is its floor, the frame plus a nominal tick plus the tick
        paid for. A 2 s stall counts as one nominal tick (about 34 frames); a 0.2 s tick (below
        ``STALL_TICK_SECONDS``, a slow display) pays its own 0.2 s (about 180 frames).
        """
        frame_seconds = 0.001
        stall_seconds = 2.0
        slow_tick_seconds = 0.2
        assert stall_seconds > STALL_TICK_SECONDS > slow_tick_seconds

        def burst(*, elapsed_seconds: float) -> int:
            player = Player(frame_seconds_for=lambda _frame: frame_seconds)
            player.tick(elapsed_seconds=SIXTY_HERTZ_SECONDS)
            return len(player.tick(elapsed_seconds=elapsed_seconds))

        stall_floor_seconds = frame_seconds + 2 * SIXTY_HERTZ_SECONDS
        assert burst(elapsed_seconds=stall_seconds) <= stall_floor_seconds / frame_seconds + 1
        slow_floor_seconds = slow_tick_seconds - SIXTY_HERTZ_SECONDS - 2 * frame_seconds
        assert burst(elapsed_seconds=slow_tick_seconds) >= slow_floor_seconds / frame_seconds

    def test_a_stall_restarts_the_effective_speed_window(self):
        """A stall is not a slow second: the window forgets what came before it."""
        player = Player()
        player.ticks(tick_count=30, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert player.pacer.effective_speed() > 0
        player.tick(elapsed_seconds=1.0)
        assert player.pacer.effective_speed() == 0.0


class TestNotRunning:
    """Paused, at a start screen or over: nothing is owed and nothing runs."""

    def test_the_accumulator_empties_and_the_next_run_starts_with_half_a_frame(self):
        """A pause forgets the owed time; the restart's first tick owes half the frame."""
        player = Player()
        player.ticks(tick_count=10, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        pacer = player.pacer
        pacer.pay(elapsed_seconds=SIXTY_HERTZ_SECONDS, speed=1.0, is_running=False)
        assert pacer.accumulated_seconds == 0.0
        assert pacer.effective_speed() == 0.0
        pacer.pay(elapsed_seconds=0.0, speed=1.0, is_running=True)
        assert not pacer.should_run_frame(
            frame_seconds=0.04, speed=1.0, budget=budget_never_spent()
        )
        assert pacer.accumulated_seconds == pytest.approx(0.02)

    def test_a_pause_ends_being_behind(self):
        """Behind is forgotten while not running."""
        player = Player()
        player.tick(elapsed_seconds=2.0)
        assert player.pacer.is_behind
        player.pacer.pay(elapsed_seconds=SIXTY_HERTZ_SECONDS, speed=1.0, is_running=False)
        assert not player.pacer.is_behind

    def test_no_frame_runs_on_a_tick_that_is_not_running(self):
        """Even a frame that owes nothing waits while the pacer is told it is not running."""
        pacer = RecordedFramePacer(nominal_tick_seconds=SIXTY_HERTZ_SECONDS)
        pacer.pay(elapsed_seconds=SIXTY_HERTZ_SECONDS, speed=1.0, is_running=False)
        assert not pacer.should_run_frame(frame_seconds=0.0, speed=1.0, budget=budget_never_spent())


class TestTheBudget:
    """A tick runs frames only while its real-time budget lasts."""

    def test_a_spent_budget_carries_the_owed_frame_and_falls_behind(self):
        """Owed but out of time: the frame waits for the next tick and the pacer is behind."""
        player = Player()
        assert player.tick(elapsed_seconds=SIXTY_HERTZ_SECONDS, budget=budget_already_spent()) == []
        assert player.pacer.accumulated_seconds == pytest.approx(1.5 * SIXTY_HERTZ_SECONDS)
        assert player.pacer.is_behind


class TestEffectiveSpeed:
    """The speed the frames really ran at, over the last second of ticks."""

    def test_it_is_zero_before_any_time_passed(self):
        """No running tick measured yet: 0.0."""
        pacer = RecordedFramePacer(nominal_tick_seconds=SIXTY_HERTZ_SECONDS)
        assert pacer.effective_speed() == 0.0

    def test_it_is_inner_seconds_over_real_seconds_over_the_last_second_of_ticks(self):
        """A second at 2x, then a second at 1x: only the last second's ticks count."""
        player = Player(speed=2.0)
        player.ticks(tick_count=EFFECTIVE_SPEED_WINDOW_TICKS, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert player.pacer.effective_speed() == pytest.approx(2.0, abs=0.05)
        player.speed = 1.0
        last_second = player.ticks(
            tick_count=EFFECTIVE_SPEED_WINDOW_TICKS, elapsed_seconds=SIXTY_HERTZ_SECONDS
        )
        inner_seconds = sum(len(frames) for frames in last_second) * SIXTY_HERTZ_SECONDS
        real_seconds = EFFECTIVE_SPEED_WINDOW_TICKS * SIXTY_HERTZ_SECONDS
        assert player.pacer.effective_speed() == pytest.approx(inner_seconds / real_seconds)

    def test_keeping_up_shows_no_real_speed(self):
        """Not behind: None."""
        player = Player()
        player.ticks(tick_count=60, elapsed_seconds=SIXTY_HERTZ_SECONDS)
        assert player.pacer.real_speed_if_behind(speed=1.0) is None

    def test_behind_with_no_running_tick_measured_shows_no_real_speed(self):
        """Behind after a stall, whose window restarted: nothing measured, so None."""
        player = Player()
        player.tick(elapsed_seconds=2.0)
        assert player.pacer.is_behind
        assert player.pacer.real_speed_if_behind(speed=1.0) is None

    def test_behind_but_within_the_fraction_shows_no_real_speed(self):
        """One tick in three out of budget: the others catch up, behind but keeping up."""
        player = Player()
        for tick in range(3 * EFFECTIVE_SPEED_WINDOW_TICKS):
            budget = budget_already_spent() if tick % 3 == 0 else budget_never_spent()
            player.tick(elapsed_seconds=SIXTY_HERTZ_SECONDS, budget=budget)
        assert player.pacer.is_behind
        assert player.pacer.effective_speed() >= BEHIND_SPEED_FRACTION
        assert player.pacer.real_speed_if_behind(speed=1.0) is None

    def test_meaningfully_slower_shows_the_real_speed(self):
        """At 2x, frames costing 12 ms against an 11 ms budget run one a tick: about 1x."""
        player = Player(speed=2.0)
        clock = FakeMeasuredClock()

        def spend_the_frame_cost() -> None:
            clock.now += 0.012

        for _ in range(2 * EFFECTIVE_SPEED_WINDOW_TICKS):
            budget = TickBudget(
                length_seconds=INNER_FRAME_BUDGET_SECONDS, measured_seconds=clock.read
            )
            player.tick(
                elapsed_seconds=SIXTY_HERTZ_SECONDS,
                budget=budget,
                after_each_frame=spend_the_frame_cost,
            )
        assert player.pacer.is_behind
        real_speed = player.pacer.real_speed_if_behind(speed=2.0)
        assert real_speed == player.pacer.effective_speed()
        assert real_speed == pytest.approx(1.0)


class TestNominalTick:
    """The pacer is told its tick period: a 120 Hz display is not mistaken for 60 Hz."""

    def test_a_120_fps_recording_on_120_hz_ticks_runs_one_frame_every_tick(self):
        """One frame a tick, never behind."""
        player = Player(
            frame_seconds_for=lambda _frame: ONE_HUNDRED_TWENTY_HERTZ_SECONDS,
            nominal_tick_seconds=ONE_HUNDRED_TWENTY_HERTZ_SECONDS,
        )
        ticks = player.ticks(tick_count=240, elapsed_seconds=ONE_HUNDRED_TWENTY_HERTZ_SECONDS)
        assert [len(frames) for frames in ticks] == [1] * 240
        assert not player.pacer.is_behind

    def test_a_60_fps_recording_on_120_hz_ticks_keeps_its_rate(self):
        """Two seconds of 120 Hz ticks run two seconds of frames, at most one a tick."""
        player = Player(nominal_tick_seconds=ONE_HUNDRED_TWENTY_HERTZ_SECONDS)
        ticks = player.ticks(tick_count=240, elapsed_seconds=ONE_HUNDRED_TWENTY_HERTZ_SECONDS)
        assert max(len(frames) for frames in ticks) == 1
        assert abs(player.next_frame - 120) <= 1
        assert not player.pacer.is_behind
        assert player.pacer.effective_speed() == pytest.approx(1.0, abs=0.02)


# One generated tick: the real time it pays for, whether the player is running, and the real
# time each frame costs (which spends the tick's budget)
generated_ticks = st.lists(
    st.tuples(
        st.floats(min_value=0.0, max_value=0.6, allow_nan=False),
        st.booleans(),
        st.floats(min_value=0.0005, max_value=0.006, allow_nan=False),
    ),
    min_size=1,
    max_size=80,
)
generated_frame_seconds = st.lists(
    st.one_of(st.just(0.0), st.floats(min_value=0.0001, max_value=0.1, allow_nan=False)),
    min_size=1,
    max_size=40,
)


@given(
    ticks=generated_ticks,
    frame_seconds=generated_frame_seconds,
    speed=st.sampled_from([0.25, 0.5, 1.0, 2.0, 4.0, 8.0]),
    nominal_tick_seconds=st.sampled_from([1 / 30, 1 / 60, 1 / 120]),
)
def test_every_frame_run_is_paid_for_and_none_is_skipped_or_repeated(
    ticks, frame_seconds, speed, nominal_tick_seconds
):
    """Over any elapsed times: time is dropped, never frames, and no frame runs unpaid.

    The player runs the next frame each time the pacer allows one, so frames run in order, each
    once; what makes that true is the pacer's accounting, checked here as a conservation law:
    the inner time paid (elapsed times speed, while running) plus the half-frame phases equals
    the frames run plus what is still owed plus what was dropped past the owed limit plus what
    a pause forfeited (stopping empties the accumulator). Owed time is never negative (no frame
    runs before it is owed), and no frame runs while not running.
    """
    pacer = RecordedFramePacer(nominal_tick_seconds=nominal_tick_seconds)
    clock = FakeMeasuredClock()
    next_frame = 0
    paid_seconds = 0.0
    run_seconds = 0.0
    forfeited_seconds = 0.0
    needs_phase = True
    for elapsed_seconds, is_running, frame_cost_seconds in ticks:
        if not is_running:
            forfeited_seconds += pacer.accumulated_seconds
        pacer.pay(elapsed_seconds=elapsed_seconds, speed=speed, is_running=is_running)
        if is_running:
            paid_seconds += elapsed_seconds * speed
        else:
            needs_phase = True
        budget = TickBudget(length_seconds=INNER_FRAME_BUDGET_SECONDS, measured_seconds=clock.read)
        for _ in range(MOST_FRAMES_A_TEST_TICK_RUNS):
            duration = frame_seconds[next_frame % len(frame_seconds)]
            if is_running and needs_phase:
                needs_phase = False
                paid_seconds += duration / 2
            if not pacer.should_run_frame(frame_seconds=duration, speed=speed, budget=budget):
                break
            assert is_running
            run_seconds += duration
            next_frame += 1
            clock.now += frame_cost_seconds
            assert pacer.accumulated_seconds >= 0
        else:
            pytest.fail('a tick never ended')
        assert pacer.accumulated_seconds >= 0
        clock.now += nominal_tick_seconds
    accounted_seconds = (
        run_seconds + pacer.accumulated_seconds + pacer.dropped_seconds + forfeited_seconds
    )
    assert accounted_seconds == pytest.approx(paid_seconds, abs=1e-9)


class TestTickBudget:
    """One real-time allowance read from an injected clock, shared by every consumer."""

    def test_it_is_spent_once_the_clock_passes_its_length(self):
        """Not spent before its length has passed; spent from then on."""
        clock = FakeMeasuredClock(now=0.0)
        budget = TickBudget(length_seconds=0.01, measured_seconds=clock.read)
        clock.now = 0.005
        assert not budget.is_spent
        clock.now = 0.02
        assert budget.is_spent

    @pytest.mark.parametrize(
        ('now', 'expected_remaining_seconds'), [(0.004, 0.006), (0.01, 0.0), (5.0, 0.0)]
    )
    def test_remaining_seconds_never_goes_below_zero(self, now, expected_remaining_seconds):
        """What is left of the length, and never less than nothing."""
        clock = FakeMeasuredClock(now=0.0)
        budget = TickBudget(length_seconds=0.01, measured_seconds=clock.read)
        clock.now = now
        assert budget.remaining_seconds == pytest.approx(expected_remaining_seconds)
        assert budget.remaining_seconds >= 0.0

    def test_two_consumers_sharing_one_see_each_others_spending(self):
        """What the first spends the second does not get."""
        clock = FakeMeasuredClock(now=100.0)
        budget = TickBudget(length_seconds=0.01, measured_seconds=clock.read)

        def consume(*, work_seconds: float) -> None:
            clock.now += work_seconds

        consume(work_seconds=0.006)
        assert budget.remaining_seconds == pytest.approx(0.004)
        assert not budget.is_spent
        consume(work_seconds=0.004)
        assert budget.is_spent
        assert budget.remaining_seconds == 0.0

    def test_a_given_start_reads_no_clock_when_made(self, mocker):
        """Started at a time already read, it does not read the clock again to start."""
        measured_seconds = mocker.Mock(return_value=3.0)
        budget = TickBudget(
            length_seconds=0.01, measured_seconds=measured_seconds, started_at_seconds=2.995
        )
        measured_seconds.assert_not_called()
        assert budget.remaining_seconds == pytest.approx(0.005)

    def test_with_no_clock_given_it_reads_the_engines_clock_when_read(self, mocker):
        """None is ``glitchygames.clock.measured_seconds``, looked up at each read."""
        engine_clock = mocker.patch('glitchygames.clock.measured_seconds', return_value=50.0)
        budget = TickBudget(length_seconds=0.01)
        engine_clock.return_value = 50.02
        assert budget.is_spent
        assert engine_clock.call_count == 2


def test_the_viewer_re_exports_the_constants_it_moved_to_the_pacer():
    """Imports of the moved constants from the viewer keep working."""
    assert viewer_module.MAX_OWED_INNER_FRAMES == MAX_OWED_INNER_FRAMES
    assert viewer_module.INNER_FRAME_BUDGET_SECONDS == INNER_FRAME_BUDGET_SECONDS
    assert viewer_module.STALL_TICK_SECONDS == STALL_TICK_SECONDS
    assert viewer_module.EFFECTIVE_SPEED_WINDOW_TICKS == EFFECTIVE_SPEED_WINDOW_TICKS
    assert viewer_module.BEHIND_SPEED_FRACTION == BEHIND_SPEED_FRACTION


# Owed frames are computed by subtracting a frame's duration from an accumulator of owed time
OWED_FRAME_SUBTRACTION = re.compile(r'accumulated_seconds\s*-')
# The engine modules allowed to compute owed frames, each with why
OWED_FRAME_COMPUTERS = {
    'replay/pacer.py': "a recording's frames, for every player of one",
    # A live game's frames at a fixed period, under GameHost.run_async in a browser: no recorded
    # durations, no speed (it re-anchors after a stall instead of owing)
    'host.py': "TickPacer: a live inner game's frames",
}


def test_only_the_pacer_computes_owed_frames():
    """No engine module but pacer.py subtracts from an ``accumulated_seconds`` (host.py aside).

    A second accumulator of a recording's frames would be a second pacing rule that drifts from
    the first.
    """
    engine_root = Path(glitchygames.__file__).parent
    computing_modules = sorted(
        path.relative_to(engine_root).as_posix()
        for path in engine_root.rglob('*.py')
        if OWED_FRAME_SUBTRACTION.search(path.read_text(encoding='utf-8'))
    )
    assert computing_modules == sorted(OWED_FRAME_COMPUTERS)
