"""Tests for timing functionality and coverage."""

import io
import itertools
import logging
import os
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, override

import pytest

from glitchygames.timing import (
    DEFAULT_SLEEP_GRANULARITY_NS,
    FastTimer,
    PacingTimer,
    PygameTimer,
    SleepModel,
    create_timer,
    describe_pacing_timer,
    measure_sleep_model,
    ms_to_ns,
    pacing_timer_for_options,
    s_to_ns,
    sleep_overshoot_ns,
)

if TYPE_CHECKING:
    from collections.abc import Buffer, Callable


class TestConversionFunctions:
    """Test ms_to_ns and s_to_ns conversion functions."""

    def test_ms_to_ns_basic(self):
        assert ms_to_ns(1.0) == 1_000_000

    def test_ms_to_ns_zero(self):
        assert ms_to_ns(0) == 0

    def test_ms_to_ns_fractional(self):
        assert ms_to_ns(0.5) == 500_000

    def test_ms_to_ns_large(self):
        assert ms_to_ns(1000) == 1_000_000_000

    def test_s_to_ns_basic(self):
        assert s_to_ns(1.0) == 1_000_000_000

    def test_s_to_ns_zero(self):
        assert s_to_ns(0) == 0

    def test_s_to_ns_fractional(self):
        assert s_to_ns(0.001) == 1_000_000


class TestPygameTimer:
    """Test PygameTimer backend."""

    def test_init(self):
        timer = PygameTimer()
        assert timer._pg is not None

    def test_close_does_nothing(self):
        """The legacy backend holds nothing, so closing it (as the teardown does) is harmless."""
        timer = PygameTimer()
        timer.close()
        assert timer._pg is not None

    def test_ns_now_returns_positive(self):
        timer = PygameTimer()
        now = timer.ns_now()
        assert isinstance(now, int)
        assert now >= 0

    def test_start_frame_with_fps(self):
        timer = PygameTimer()
        period = timer.start_frame(60)
        # round(1_000_000_000 / 60) = 16666667
        assert period == 16_666_667

    def test_start_frame_zero_fps(self):
        timer = PygameTimer()
        assert timer.start_frame(0) == 0

    def test_start_frame_negative_fps(self):
        timer = PygameTimer()
        assert timer.start_frame(-1) == 0

    def test_compute_deadline_no_prev(self):
        timer = PygameTimer()
        period_ns = 16_666_666
        deadline = timer.compute_deadline(None, period_ns)
        # Should be roughly now + period
        assert deadline > 0

    def test_compute_deadline_with_prev(self):
        timer = PygameTimer()
        # The previous deadline is now: on time, so the next is exactly one period later.
        prev = timer.ns_now()
        period = 16_666_666
        deadline = timer.compute_deadline(prev, period)
        assert deadline == prev + period

    def test_sleep_until_next_past_deadline(self):
        timer = PygameTimer()
        # Deadline in the past - should return immediately
        past_deadline = timer.ns_now() - 1_000_000_000
        result = timer.sleep_until_next(past_deadline)
        assert result >= 0


class TestFastTimer:
    """Test FastTimer backend."""

    def test_init_default(self):
        timer = FastTimer()
        assert timer.sleep_granularity_ns == 1_000_000
        assert timer._win_period_on is False

    def test_init_custom_granularity(self):
        timer = FastTimer(sleep_granularity_ns=500_000)
        assert timer.sleep_granularity_ns == 500_000

    def test_init_negative_granularity_clamped(self):
        timer = FastTimer(sleep_granularity_ns=-100)
        assert timer.sleep_granularity_ns == 0

    def test_ns_now_returns_positive(self):
        timer = FastTimer()
        now = timer.ns_now()
        assert isinstance(now, int)
        assert now > 0

    def test_ns_now_monotonic(self):
        timer = FastTimer()
        t1 = timer.ns_now()
        t2 = timer.ns_now()
        assert t2 >= t1

    def test_start_frame_with_fps(self):
        timer = FastTimer()
        period = timer.start_frame(60)
        assert period == 16_666_667

    def test_start_frame_zero_fps(self):
        timer = FastTimer()
        assert timer.start_frame(0) == 0

    def test_start_frame_negative_fps(self):
        timer = FastTimer()
        assert timer.start_frame(-5) == 0

    def test_compute_deadline_no_prev(self):
        timer = FastTimer()
        period_ns = 16_666_666
        deadline = timer.compute_deadline(None, period_ns)
        assert deadline > 0

    def test_compute_deadline_with_prev(self):
        timer = FastTimer()
        # The previous deadline is now: on time, so the next is exactly one period later.
        prev = timer.ns_now()
        period = 16_666_666
        deadline = timer.compute_deadline(prev, period)
        assert deadline == prev + period

    def test_sleep_until_next_past_deadline(self):
        timer = FastTimer()
        past_deadline = timer.ns_now() - 1_000_000_000
        result = timer.sleep_until_next(past_deadline)
        assert result > 0

    def test_sleep_until_next_near_future(self):
        timer = FastTimer()
        # Very near future - within spin window
        near_deadline = timer.ns_now() + 100_000  # 100 microseconds
        result = timer.sleep_until_next(near_deadline)
        assert result >= near_deadline

    def test_a_default_timer_reads_and_sleeps_through_glitchygames_clock(self, mocker):
        """A patch on glitchygames.clock reaches a FastTimer built with no counter or sleep.

        Its defaults are looked up on every reading and sleep, not bound when the timer (or
        FastTimer) was defined, so glitchygames.clock is the one place to patch.
        """
        timer = FastTimer()
        fake_clock = FakeClock(start_ns=0)
        mocker.patch('glitchygames.clock.raw_counter_ns', new=fake_clock.perf_counter_ns)
        sleep = mocker.patch('glitchygames.clock.raw_sleep', side_effect=fake_clock.sleep)

        result = timer.sleep_until_next(10_000_000)

        assert result >= 10_000_000
        # The coarse sleep to 1 ms before the deadline, then the spin's yields
        assert sleep.call_args_list[0] == mocker.call(0.009)
        assert all(call == mocker.call(0) for call in sleep.call_args_list[1:])

    def test_final_spin_yields_the_gil_each_iteration(self, mocker):
        """Test the final spin calls sleep(0) so audio callbacks can take the GIL."""
        deadline_ns = 10_000_000
        # Calls: coarse loop reads 9_999_000 (inside the spin window, so no coarse sleep),
        # then the spin reads 9_999_100, 9_999_500 (both short) and 10_000_001 (past).
        mock_sleep = mocker.Mock()
        timer = FastTimer(
            read_counter_ns=mocker.Mock(side_effect=[9_999_000, 9_999_100, 9_999_500, 10_000_001]),
            sleep=mock_sleep,
        )

        result = timer.sleep_until_next(deadline_ns)

        assert result >= deadline_ns
        assert mock_sleep.call_args_list == [mocker.call(0), mocker.call(0)]

    def test_sleep_until_next_with_zero_granularity(self):
        timer = FastTimer(sleep_granularity_ns=0)
        near_deadline = timer.ns_now() + 100_000
        result = timer.sleep_until_next(near_deadline)
        assert result >= near_deadline

    def test_del_non_windows(self):
        """Test __del__ on non-Windows platform doesn't error."""
        timer = FastTimer()
        timer.__del__()


class TestCreateTimer:
    """Test create_timer factory function."""

    def test_create_pygame_timer(self):
        timer = create_timer('pygame')
        assert isinstance(timer, PygameTimer)

    def test_create_fast_timer(self):
        timer = create_timer('fast')
        assert isinstance(timer, FastTimer)

    def test_create_timer_none_defaults_to_fast(self):
        timer = create_timer(None)
        assert isinstance(timer, FastTimer)

    def test_create_timer_empty_options_defaults_to_fast(self):
        timer = create_timer(None, {})
        assert isinstance(timer, FastTimer)

    def test_create_timer_case_insensitive(self):
        timer = create_timer('FAST')
        assert isinstance(timer, FastTimer)

    def test_create_timer_with_options(self):
        timer = create_timer('fast', {'sleep_granularity_ns': 500_000})
        assert isinstance(timer, FastTimer)
        assert timer.sleep_granularity_ns == 500_000

    def test_create_timer_from_options_dict(self):
        timer = create_timer(None, {'timer_backend': 'fast'})
        assert isinstance(timer, FastTimer)

    def test_create_timer_unknown_type_defaults_pygame(self):
        timer = create_timer('unknown')
        assert isinstance(timer, PygameTimer)


ONE_MS_IN_NS = 1_000_000
ONE_S_IN_NS = 1_000_000_000
TARGET_FPS_60 = 60
TARGET_FPS_120 = 120
EXPECTED_PERIOD_60 = 16_666_667  # round(1e9 / 60)
EXPECTED_PERIOD_120 = 8_333_333  # round(1e9 / 120)


class TestMsToNs:
    """Tests for ms_to_ns conversion function."""

    def test_ms_to_ns_one_millisecond(self):
        """Test converting 1 ms to nanoseconds."""
        assert ms_to_ns(1) == ONE_MS_IN_NS

    def test_ms_to_ns_zero(self):
        """Test converting 0 ms to nanoseconds."""
        assert ms_to_ns(0) == 0

    def test_ms_to_ns_fractional(self):
        """Test converting fractional ms to nanoseconds."""
        assert ms_to_ns(0.5) == 500_000

    def test_ms_to_ns_large_value(self):
        """Test converting a large ms value to nanoseconds."""
        assert ms_to_ns(1000) == ONE_S_IN_NS


class TestSToNs:
    """Tests for s_to_ns conversion function."""

    def test_s_to_ns_one_second(self):
        """Test converting 1 second to nanoseconds."""
        assert s_to_ns(1) == ONE_S_IN_NS

    def test_s_to_ns_zero(self):
        """Test converting 0 seconds to nanoseconds."""
        assert s_to_ns(0) == 0

    def test_s_to_ns_fractional(self):
        """Test converting fractional seconds to nanoseconds."""
        assert s_to_ns(0.001) == ONE_MS_IN_NS

    def test_s_to_ns_large_value(self):
        """Test converting a large seconds value to nanoseconds."""
        assert s_to_ns(60) == 60 * ONE_S_IN_NS


class TestFastTimerInit:
    """Tests for FastTimer initialization."""

    def test_default_init(self):
        """Test FastTimer initializes with default sleep granularity."""
        timer = FastTimer()
        assert timer.sleep_granularity_ns == ONE_MS_IN_NS
        assert timer._win_period_on is False

    def test_custom_sleep_granularity(self):
        """Test FastTimer initializes with custom sleep granularity."""
        timer = FastTimer(sleep_granularity_ns=2_000_000)
        assert timer.sleep_granularity_ns == 2_000_000

    def test_negative_sleep_granularity_clamped_to_zero(self):
        """Test FastTimer clamps negative sleep granularity to zero."""
        timer = FastTimer(sleep_granularity_ns=-100)
        assert timer.sleep_granularity_ns == 0

    def test_windows_timer_1ms_on_non_windows(self):
        """Test that windows_timer_1ms flag is ignored on non-Windows platforms."""
        if sys.platform.startswith('win'):
            pytest.skip('This test only applies on non-Windows platforms')
        timer = FastTimer(windows_timer_1ms=True)
        # On non-Windows (macOS/Linux), _win_period_on should remain False
        assert timer._win_period_on is False


class TestFastTimerDel:
    """Tests for FastTimer __del__ cleanup."""

    def test_del_without_win_period(self):
        """Test FastTimer __del__ when _win_period_on is False does nothing."""
        timer = FastTimer()
        assert timer._win_period_on is False
        # Should not raise any errors
        del timer

    def test_del_with_win_period_on_non_windows(self):
        """Test FastTimer __del__ skips cleanup on non-Windows even if flag is set."""
        timer = FastTimer()
        # Force the flag to True to test the platform check in __del__
        timer._win_period_on = True
        # On non-Windows, sys.platform.startswith('win') is False, so cleanup is skipped
        if not sys.platform.startswith('win'):
            del timer  # Should not raise


class TestFastTimerNsNow:
    """Tests for FastTimer.ns_now method."""

    def test_ns_now_returns_positive_integer(self):
        """Test that ns_now returns a positive integer."""
        timer = FastTimer()
        now = timer.ns_now()
        assert isinstance(now, int)
        assert now > 0

    def test_ns_now_monotonically_increases(self):
        """Test that ns_now values increase over time."""
        timer = FastTimer()
        first = timer.ns_now()
        second = timer.ns_now()
        assert second >= first


class TestFastTimerStartFrame:
    """Tests for FastTimer.start_frame method."""

    def test_start_frame_60_fps(self):
        """Test start_frame returns correct period for 60 FPS."""
        timer = FastTimer()
        period = timer.start_frame(TARGET_FPS_60)
        assert period == EXPECTED_PERIOD_60

    def test_start_frame_120_fps(self):
        """Test start_frame returns correct period for 120 FPS."""
        timer = FastTimer()
        period = timer.start_frame(TARGET_FPS_120)
        assert period == EXPECTED_PERIOD_120

    def test_start_frame_zero_fps_returns_zero(self):
        """Test start_frame returns 0 when target_fps is 0 (unlimited)."""
        timer = FastTimer()
        period = timer.start_frame(0)
        assert period == 0


class TestFastTimerComputeDeadline:
    """Tests for FastTimer.compute_deadline method."""

    def test_compute_deadline_with_no_previous(self):
        """Test compute_deadline with prev_deadline_ns=None uses current time."""
        timer = FastTimer()
        period_ns = EXPECTED_PERIOD_60
        before = timer.ns_now()
        deadline = timer.compute_deadline(None, period_ns)
        after = timer.ns_now()
        # Deadline should be approximately now + period
        assert deadline >= before + period_ns
        assert deadline <= after + period_ns

    def test_compute_deadline_with_previous(self):
        """Test compute_deadline with a previous deadline adds period."""
        timer = FastTimer()
        # The previous deadline is now: on time, so the next is exactly one period later.
        prev_deadline = timer.ns_now()
        period_ns = EXPECTED_PERIOD_60
        deadline = timer.compute_deadline(prev_deadline, period_ns)
        assert deadline == prev_deadline + period_ns


class TestFastTimerSleepUntilNext:
    """Tests for FastTimer.sleep_until_next method."""

    def test_sleep_until_next_deadline_in_past(self):
        """Test sleep_until_next returns immediately when deadline is in the past."""
        timer = FastTimer()
        past_deadline = timer.ns_now() - ONE_S_IN_NS
        result = timer.sleep_until_next(past_deadline)
        assert result >= past_deadline

    def test_sleep_until_next_deadline_now(self):
        """Test sleep_until_next returns immediately when deadline is approximately now."""
        timer = FastTimer()
        deadline = timer.ns_now()
        result = timer.sleep_until_next(deadline)
        assert result >= deadline

    def test_sleep_until_next_short_deadline(self):
        """Test sleep_until_next waits until a short future deadline."""
        timer = FastTimer(sleep_granularity_ns=0)
        # Set deadline 1ms in the future (short enough to spin-wait)
        deadline = timer.ns_now() + ONE_MS_IN_NS
        result = timer.sleep_until_next(deadline)
        assert result >= deadline


class TestPygameTimerExtended:
    """Tests for PygameTimer that require pygame mocking."""

    def test_pygame_timer_start_frame_zero_fps(self, mocker):
        """Test PygameTimer.start_frame returns 0 when target_fps is 0."""
        # Mock pygame import inside PygameTimer.__init__
        mock_pygame = mocker.MagicMock()
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = PygameTimer()
        period = timer.start_frame(0)
        assert period == 0

    def test_pygame_timer_start_frame_60_fps(self, mocker):
        """Test PygameTimer.start_frame returns correct period for 60 FPS."""
        mock_pygame = mocker.MagicMock()
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = PygameTimer()
        period = timer.start_frame(TARGET_FPS_60)
        assert period == EXPECTED_PERIOD_60

    def test_pygame_timer_compute_deadline_no_previous(self, mocker):
        """Test PygameTimer.compute_deadline with prev_deadline_ns=None."""
        mock_pygame = mocker.MagicMock()
        mock_ticks_value = 1000
        mock_pygame.time.get_ticks.return_value = mock_ticks_value
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = PygameTimer()
        period_ns = EXPECTED_PERIOD_60
        deadline = timer.compute_deadline(None, period_ns)
        expected_now_ns = mock_ticks_value * ONE_MS_IN_NS
        assert deadline == expected_now_ns + period_ns

    def test_pygame_timer_compute_deadline_with_previous(self, mocker):
        """Test PygameTimer.compute_deadline with a previous deadline."""
        mock_pygame = mocker.MagicMock()
        # The clock reads 500 ms, the previous deadline: on time, so no re-anchoring.
        mock_pygame.time.get_ticks.return_value = 500
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = PygameTimer()
        prev_deadline = 500_000_000
        period_ns = EXPECTED_PERIOD_60
        deadline = timer.compute_deadline(prev_deadline, period_ns)
        assert deadline == prev_deadline + period_ns

    def test_pygame_timer_sleep_until_next(self, mocker):
        """Test PygameTimer.sleep_until_next calls pygame.time.delay."""
        mock_pygame = mocker.MagicMock()
        # First call for remaining_ns calculation, second call for return value
        mock_pygame.time.get_ticks.side_effect = [1000, 1017]
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = PygameTimer()
        # Deadline is 17ms ahead of the first get_ticks call (1000ms)
        deadline_ns = (1000 + 17) * ONE_MS_IN_NS
        result = timer.sleep_until_next(deadline_ns)
        # Should have called delay
        mock_pygame.time.delay.assert_called_once()
        # Result should be the second get_ticks value in ns
        assert result == 1017 * ONE_MS_IN_NS


class TestCreateTimerExtended:
    """Tests for create_timer factory function."""

    def test_create_timer_fast(self):
        """Test create_timer with 'fast' type returns FastTimer."""
        timer = create_timer('fast')
        assert isinstance(timer, FastTimer)

    def test_create_timer_fast_with_options(self):
        """Test create_timer with 'fast' type and custom options."""
        options = {'sleep_granularity_ns': 2_000_000, 'windows_timer_1ms': False}
        timer = create_timer('fast', options=options)
        assert isinstance(timer, FastTimer)
        assert timer.sleep_granularity_ns == 2_000_000

    def test_create_timer_pygame(self, mocker):
        """Test create_timer with 'pygame' type returns PygameTimer."""
        mock_pygame = mocker.MagicMock()
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = create_timer('pygame')
        assert isinstance(timer, PygameTimer)

    def test_create_timer_none_defaults_to_fast(self):
        """Test create_timer with None type defaults to FastTimer."""
        timer = create_timer(None)
        assert isinstance(timer, FastTimer)

    def test_create_timer_from_options_dict(self):
        """Test create_timer reads timer_backend from options dict."""
        options = {'timer_backend': 'fast'}
        timer = create_timer(None, options=options)
        assert isinstance(timer, FastTimer)


class TestFractionalTargetFps:
    """Fractional target FPS is rounded to a nanosecond period, not truncated."""

    def test_fast_timer_fractional_target(self):
        assert FastTimer().start_frame(60.5) == 16_528_926

    def test_fast_timer_integer_target_rounds_up(self):
        assert FastTimer().start_frame(60) == 16_666_667

    def test_fast_timer_zero_target(self):
        assert FastTimer().start_frame(0) == 0

    def test_pygame_timer_fractional_target(self):
        assert PygameTimer().start_frame(60.5) == 16_528_926

    def test_pygame_timer_integer_target_rounds_up(self):
        assert PygameTimer().start_frame(60) == 16_666_667

    def test_pygame_timer_zero_target(self):
        assert PygameTimer().start_frame(0) == 0


# --- Re-anchoring after a hitch (BUGS.md #58) -------------------------------------------------

PERIOD_60_01_NS = 16_663_889  # round(1e9 / 60.01), the engine's default target
HITCH_NS = 2 * ONE_S_IN_NS
LIGHT_WORK_NS = 4 * ONE_MS_IN_NS
TWO_MS_LATE_NS = 2 * ONE_MS_IN_NS


class FakeClock:
    """A nanosecond clock that only moves when the code under test sleeps or a test advances it.

    Stands in for the raw counter and sleep a FastTimer is given (``read_counter_ns``, ``sleep``)
    and for
    ``pygame.time.get_ticks`` / ``pygame.time.delay`` (PygameTimer), so pacing runs with no real
    sleeping. ``sleep_count`` counts calls that moved the clock forward.
    """

    # FastTimer spins with sleep(0); each spin step costs one microsecond of fake time so
    # the spin loop terminates.
    SPIN_STEP_NS = 1_000

    def __init__(self, start_ns: int) -> None:
        """Start the clock at ``start_ns``."""
        self.now_ns = start_ns
        self.sleep_count = 0

    def advance(self, duration_ns: int) -> None:
        """Move the clock forward without counting a sleep (simulated frame work)."""
        self.now_ns += duration_ns

    def perf_counter_ns(self) -> int:
        """Return the current fake time in nanoseconds.

        Returns:
            The current fake time in nanoseconds.

        """
        return self.now_ns

    def sleep(self, seconds: float) -> None:
        """Sleep on the fake clock (the raw sleep's replacement)."""
        self.now_ns += max(round(seconds * 1_000_000_000), self.SPIN_STEP_NS)
        self.sleep_count += 1

    def get_ticks(self) -> int:
        """Return whole milliseconds, as pygame.time.get_ticks does.

        Returns:
            The current fake time in whole milliseconds.

        """
        return self.now_ns // ONE_MS_IN_NS

    def delay(self, milliseconds: int) -> None:
        """Sleep whole milliseconds on the fake clock (pygame.time.delay replacement)."""
        if milliseconds > 0:
            self.now_ns += milliseconds * ONE_MS_IN_NS
            self.sleep_count += 1


def make_timer_on_fake_clock(*, backend: str, clock: FakeClock) -> FastTimer | PygameTimer:
    """Build a timer backend whose clock and sleeps are the fake clock.

    Returns:
        The timer backend, reading and sleeping on ``clock``.

    """
    # The clock's own functions, not recording mocks: a paced run calls them millions of times
    # (the final spin reads the clock every fake microsecond), and a mock keeping each call held
    # about 2 GB in the 1,000-frame test (BUGS.md #85)
    if backend == 'fast':
        return FastTimer(read_counter_ns=clock.perf_counter_ns, sleep=clock.sleep)
    timer = PygameTimer()
    timer._pg = SimpleNamespace(time=SimpleNamespace(get_ticks=clock.get_ticks, delay=clock.delay))
    return timer


def run_paced_frames(
    *,
    timer: FastTimer | PygameTimer,
    clock: FakeClock,
    period_ns: int,
    work_ns_per_frame: list[int],
    first_deadline_ns: int | None = None,
) -> tuple[list[int], list[bool]]:
    """Run the SceneManager pacing sequence (work, compute_deadline, sleep_until_next).

    Returns:
        The deadline of each frame and, per frame, whether sleep_until_next slept at all.

    """
    deadlines: list[int] = []
    slept_per_frame: list[bool] = []
    previous_deadline_ns = first_deadline_ns
    for work_ns in work_ns_per_frame:
        clock.advance(work_ns)
        deadline_ns = timer.compute_deadline(previous_deadline_ns, period_ns)
        sleeps_before = clock.sleep_count
        timer.sleep_until_next(deadline_ns)
        deadlines.append(deadline_ns)
        slept_per_frame.append(clock.sleep_count > sleeps_before)
        previous_deadline_ns = deadline_ns
    return deadlines, slept_per_frame


BACKENDS = ['fast', 'pygame']


@pytest.mark.parametrize('backend', BACKENDS)
class TestDeadlineReanchorsAfterHitch:
    """After falling more than one period behind, pacing re-anchors instead of bursting."""

    def test_two_second_hitch_reanchors_to_now_plus_period(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)
        previous_deadline_ns = clock.now_ns
        clock.advance(HITCH_NS)

        deadline_ns = timer.compute_deadline(previous_deadline_ns, PERIOD_60_01_NS)

        assert deadline_ns == clock.now_ns + PERIOD_60_01_NS

    def test_frames_after_a_hitch_are_all_paced(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)
        frame_count = 200
        hitch_frame = 20
        work_ns_per_frame = [LIGHT_WORK_NS] * frame_count
        work_ns_per_frame[hitch_frame] = HITCH_NS

        _deadlines, slept_per_frame = run_paced_frames(
            timer=timer,
            clock=clock,
            period_ns=PERIOD_60_01_NS,
            work_ns_per_frame=work_ns_per_frame,
        )

        # Without re-anchoring the ~120 frames after the hitch ran back to back unslept.
        assert slept_per_frame.count(False) == 0

    def test_hitch_frame_is_followed_by_steady_period_deadlines(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)
        work_ns_per_frame = [LIGHT_WORK_NS] * 10
        work_ns_per_frame[3] = HITCH_NS

        deadlines, _slept_per_frame = run_paced_frames(
            timer=timer,
            clock=clock,
            period_ns=PERIOD_60_01_NS,
            work_ns_per_frame=work_ns_per_frame,
        )

        gaps = [later - earlier for earlier, later in itertools.pairwise(deadlines)]
        assert gaps[2] > HITCH_NS  # the re-anchor jump (the dropped backlog)
        assert all(gap == PERIOD_60_01_NS for gap in gaps[3:])

    def test_slightly_late_frame_still_catches_up(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)
        previous_deadline_ns = clock.now_ns
        # 2 ms past this frame's deadline (previous + period): normal jitter.
        clock.advance(PERIOD_60_01_NS + TWO_MS_LATE_NS)

        deadline_ns = timer.compute_deadline(previous_deadline_ns, PERIOD_60_01_NS)

        assert deadline_ns == previous_deadline_ns + PERIOD_60_01_NS

    def test_average_rate_over_jittery_frames_equals_target_exactly(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)
        frame_count = 1_000
        # Deterministic jitter: 0 to 0.95 periods of work per frame, with a 1.8-period spike
        # every 50th frame. A spike leaves the loop less than one period behind, so it is caught
        # up and no frame is dropped.
        work_ns_per_frame = [
            (frame_index * 7 % 20) * PERIOD_60_01_NS // 20 for frame_index in range(frame_count)
        ]
        for spike_frame in range(25, frame_count, 50):
            work_ns_per_frame[spike_frame] = PERIOD_60_01_NS * 18 // 10

        deadlines, _slept_per_frame = run_paced_frames(
            timer=timer,
            clock=clock,
            period_ns=PERIOD_60_01_NS,
            work_ns_per_frame=work_ns_per_frame,
        )

        assert deadlines[-1] - deadlines[0] == (frame_count - 1) * PERIOD_60_01_NS
        elapsed_seconds = (deadlines[-1] - deadlines[0]) / ONE_S_IN_NS
        measured_fps = (frame_count - 1) / elapsed_seconds
        assert measured_fps == pytest.approx(ONE_S_IN_NS / PERIOD_60_01_NS, rel=1e-12)
        # The period is rounded to a whole nanosecond, 60.0100013 FPS.
        assert measured_fps == pytest.approx(60.01, abs=1e-5)

    def test_uncapped_period_zero_is_unchanged(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)
        previous_deadline_ns = clock.now_ns
        clock.advance(HITCH_NS)

        assert timer.compute_deadline(previous_deadline_ns, 0) == previous_deadline_ns

    def test_first_frame_is_now_plus_period(self, backend):
        clock = FakeClock(start_ns=10 * ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)

        assert timer.compute_deadline(None, PERIOD_60_01_NS) == clock.now_ns + PERIOD_60_01_NS


# A previous deadline chosen so that previous + 2 periods is exactly 1000 ms, a whole-millisecond
# instant both backends can read (PygameTimer's clock is whole milliseconds).
BOUNDARY_PREVIOUS_DEADLINE_NS = ONE_S_IN_NS - 2 * PERIOD_60_01_NS


@pytest.mark.parametrize('backend', BACKENDS)
class TestDeadlineReanchorBoundary:
    """Exactly one period behind still catches up; any later than that re-anchors."""

    def test_one_millisecond_inside_the_boundary_catches_up(self, backend):
        clock = FakeClock(start_ns=ONE_S_IN_NS - ONE_MS_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)

        deadline_ns = timer.compute_deadline(BOUNDARY_PREVIOUS_DEADLINE_NS, PERIOD_60_01_NS)

        assert deadline_ns == BOUNDARY_PREVIOUS_DEADLINE_NS + PERIOD_60_01_NS

    def test_exactly_one_period_behind_catches_up(self, backend):
        clock = FakeClock(start_ns=ONE_S_IN_NS)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)

        deadline_ns = timer.compute_deadline(BOUNDARY_PREVIOUS_DEADLINE_NS, PERIOD_60_01_NS)

        assert deadline_ns == BOUNDARY_PREVIOUS_DEADLINE_NS + PERIOD_60_01_NS

    def test_past_one_period_behind_reanchors(self, backend):
        # The smallest step each clock can show past the boundary: 1 ns, or 1 ms for pygame.
        step_past_boundary_ns = 1 if backend == 'fast' else ONE_MS_IN_NS
        clock = FakeClock(start_ns=ONE_S_IN_NS + step_past_boundary_ns)
        timer = make_timer_on_fake_clock(backend=backend, clock=clock)

        deadline_ns = timer.compute_deadline(BOUNDARY_PREVIOUS_DEADLINE_NS, PERIOD_60_01_NS)

        assert deadline_ns == ONE_S_IN_NS + step_past_boundary_ns + PERIOD_60_01_NS


class TestSleepGranularityEndsTheSleep:
    """The sleep ends sleep_granularity_ns before the deadline; the rest is spun."""

    def test_the_sleep_ends_the_granularity_before_the_deadline(self, mocker):
        """A 16 ms granularity sleeps 4 ms of a 20 ms wait, then spins the last 16 ms."""
        # Reads: 0 (sleep 4 ms), 4 ms (inside the granularity: spin), then past the deadline
        mock_sleep = mocker.Mock()
        timer = FastTimer(
            sleep_granularity_ns=16_000_000,
            read_counter_ns=mocker.Mock(side_effect=[0, 4_000_000, 20_000_001]),
            sleep=mock_sleep,
        )

        result = timer.sleep_until_next(20_000_000)

        assert result >= 20_000_000
        assert mock_sleep.call_args_list == [mocker.call(0.004)]

    def test_the_default_still_spins_only_the_last_millisecond(self, mocker):
        """The 1 ms default sleeps to 1 ms before the deadline, as the fixed spin window did."""
        mock_sleep = mocker.Mock()
        timer = FastTimer(
            read_counter_ns=mocker.Mock(side_effect=[0, 9_000_000, 10_000_001]), sleep=mock_sleep
        )

        timer.sleep_until_next(10_000_000)

        assert mock_sleep.call_args_list == [mocker.call(0.009)]


class TestSleepModel:
    """--timer-backend auto: each sleep is sized so its predicted wake lands before the deadline.

    A sleep's delay past its length is modelled as a constant plus a fraction of the length:
    macOS lets a normal-priority sleep run late by 25% of its length (4 ms wakes 1.01 ms late,
    16 ms 4.01 ms), and at background priority by a flat 85-100 ms.
    """

    def test_the_model_is_fitted_from_a_short_and_a_long_probe(self, mocker):
        """Delays of 0.25 ms after 1 ms and 2 ms after 8 ms: 0 ms constant, 25% of the length."""
        mocker.patch(
            'glitchygames.timing.sleep_overshoot_ns',
            side_effect=lambda *, probe_ns, samples, **_clock: probe_ns // 4,
        )

        model = measure_sleep_model()

        assert model == SleepModel(constant_ns=0, fraction=0.25)

    def test_a_flat_delay_is_all_constant(self, mocker):
        """90 ms late whatever the length (background priority): no fraction."""
        mocker.patch(
            'glitchygames.timing.sleep_overshoot_ns',
            side_effect=lambda *, probe_ns, samples, **_clock: 90_000_000,
        )

        assert measure_sleep_model() == SleepModel(constant_ns=90_000_000, fraction=0.0)

    def test_the_probe_overshoot_is_the_90th_percentile(self, mocker):
        """One very late wake does not decide it: the 90th percentile of the samples does."""
        samples = 10
        overshoots = [index * 100_000 for index in range(samples)]
        overshoots[0] = 500_000_000  # one 500 ms outlier
        clock_reads = []
        for overshoot in overshoots:
            clock_reads.extend([0, 1_000_000 + overshoot])
        measured = sleep_overshoot_ns(
            probe_ns=1_000_000,
            samples=samples,
            read_counter_ns=mocker.Mock(side_effect=clock_reads),
            sleep=mocker.Mock(),
        )

        assert measured == sorted(overshoots)[int(0.9 * (samples - 1))]
        assert measured < 500_000_000

    def test_a_sleep_is_sized_to_wake_the_granularity_before_the_deadline(self, mocker):
        """25% delay, 12.7 ms to wait: sleep 9.36 ms (wakes 11.7 ms in), spin the rest."""
        mock_sleep = mocker.Mock()
        timer = FastTimer(
            sleep_model=SleepModel(constant_ns=0, fraction=0.25),
            read_counter_ns=mocker.Mock(side_effect=[0, 11_700_000, 12_700_001]),
            sleep=mock_sleep,
        )

        timer.sleep_until_next(12_700_000)

        (sleep_seconds,) = mock_sleep.call_args_list[0].args
        assert sleep_seconds == pytest.approx((12_700_000 - 1_000_000) / 1.25 / 1e9)
        assert all(call.args == (0,) for call in mock_sleep.call_args_list[1:])

    def test_a_delay_longer_than_the_wait_spins_the_whole_wait(self, mocker):
        """A 90 ms constant delay and a 16.7 ms frame: sleeping can only be late, so spin."""
        mock_sleep = mocker.Mock()
        timer = FastTimer(
            sleep_model=SleepModel(constant_ns=90_000_000, fraction=0.0),
            read_counter_ns=mocker.Mock(side_effect=[0, 8_000_000, 16_700_001]),
            sleep=mock_sleep,
        )

        timer.sleep_until_next(16_700_000)

        assert all(call.args == (0,) for call in mock_sleep.call_args_list)

    def test_auto_measures_the_model_when_first_needed(self, mocker):
        """A run that never paces (uncapped, a headless replay) never spends the measurement."""
        model = SleepModel(constant_ns=0, fraction=0.25)
        measure = mocker.patch('glitchygames.timing.measure_sleep_model', return_value=model)

        timer = create_timer('auto', {'sleep_granularity_ns': None})
        # Describing it (a recording naming its run's timer) does not measure
        assert timer.pacing_timer().sleep_model is None
        measure.assert_not_called()
        # The first paced sleep (or calibrate()) measures, once (a deadline already past: no
        # sleep), with the timer's own counter and sleep: its defaults (None), which resolve to
        # glitchygames/clock.py's raw ones when called
        timer.sleep_until_next(timer.ns_now() - 1)
        timer.calibrate()
        assert timer.pacing_timer() == PacingTimer(
            backend='fast', sleep_granularity_ns=DEFAULT_SLEEP_GRANULARITY_NS, sleep_model=model
        )

        measure.assert_called_once_with(read_counter_ns=None, sleep=None)

    def test_auto_with_an_explicit_granularity_calibrates_with_that_margin(self, mocker):
        """--sleep-granularity-ns sets the final spin; auto still measures the sleep model."""
        model = SleepModel(constant_ns=0, fraction=0.25)
        mocker.patch('glitchygames.timing.measure_sleep_model', return_value=model)

        timer = create_timer('auto', {'sleep_granularity_ns': 2_000_000})
        timer.calibrate()

        assert timer.pacing_timer() == PacingTimer(
            backend='fast', sleep_granularity_ns=2_000_000, sleep_model=model
        )

    def test_fast_without_a_granularity_uses_the_default(self):
        """--timer-backend fast keeps the 1 ms default, with no model."""
        timer = create_timer('fast', {'sleep_granularity_ns': None})

        assert isinstance(timer, FastTimer)
        assert timer.pacing_timer() == PacingTimer(
            backend='fast', sleep_granularity_ns=DEFAULT_SLEEP_GRANULARITY_NS, sleep_model=None
        )

    @pytest.mark.parametrize(
        ('options', 'expected'),
        [
            (
                {'timer_backend': 'auto', 'sleep_granularity_ns': 1_000_000},
                PacingTimer(backend='fast', sleep_granularity_ns=1_000_000, sleep_model=None),
            ),
            (
                {'timer_backend': 'fast', 'sleep_granularity_ns': 2_000_000},
                PacingTimer(backend='fast', sleep_granularity_ns=2_000_000, sleep_model=None),
            ),
            (
                {'timer_backend': 'fast', 'sleep_granularity_ns': None},
                PacingTimer(
                    backend='fast',
                    sleep_granularity_ns=DEFAULT_SLEEP_GRANULARITY_NS,
                    sleep_model=None,
                ),
            ),
            (
                {'timer_backend': 'pygame'},
                PacingTimer(backend='pygame', sleep_granularity_ns=None, sleep_model=None),
            ),
        ],
        ids=['auto', 'fast', 'fast-default-granularity', 'pygame'],
    )
    def test_options_describe_the_timer_they_would_create(self, options, expected):
        """Before (or without) a timer, the options say which it is, uncalibrated."""
        assert pacing_timer_for_options(options=options) == expected

    def test_the_pygame_timer_describes_itself(self):
        """The legacy backend sleeps in whole milliseconds and has no granularity."""
        timer = PygameTimer()
        timer.calibrate()  # nothing to calibrate
        assert timer.pacing_timer() == PacingTimer(
            backend='pygame', sleep_granularity_ns=None, sleep_model=None
        )


class TestDescribePacingTimer:
    """describe_pacing_timer names the backend, its final spin and its calibration."""

    def test_pygame_timer_is_named_by_its_backend_alone(self):
        """A timer without a sleep granularity (the pygame backend) is just its backend's name."""
        pacing = PacingTimer(backend='pygame', sleep_granularity_ns=None, sleep_model=None)

        assert describe_pacing_timer(pacing=pacing) == 'pygame'

    def test_uncalibrated_fast_timer_gives_its_final_spin(self):
        """An uncalibrated fast timer is described by its final spin, in milliseconds."""
        pacing = PacingTimer(backend='fast', sleep_granularity_ns=1_500_000, sleep_model=None)

        assert describe_pacing_timer(pacing=pacing) == 'fast, final spin 1.5 ms'

    def test_calibrated_fast_timer_gives_its_sleep_model(self):
        """A calibrated fast timer adds how late its sleeps wake."""
        pacing = PacingTimer(
            backend='fast',
            sleep_granularity_ns=1_000_000,
            sleep_model=SleepModel(constant_ns=120_000, fraction=0.25),
        )

        assert describe_pacing_timer(pacing=pacing) == (
            'fast, final spin 1.0 ms (calibrated: sleeps wake 0.12 ms + 25% of their length late)'
        )


class FakeWinmm:
    """Stands in for ctypes.windll.winmm: records the timer period calls it gets."""

    def __init__(self, *, failure: Exception | None = None) -> None:
        """Start with no calls; raise failure from timeEndPeriod when given."""
        self.calls: list[tuple[str, int]] = []
        self.failure = failure

    def timeBeginPeriod(self, period: int) -> int:  # ruff: ignore[invalid-function-name]  # the Windows API's name
        """Record a timer resolution request.

        Returns:
            int: 0, TIMERR_NOERROR.

        """
        self.calls.append(('timeBeginPeriod', period))
        return 0

    def timeEndPeriod(self, period: int) -> int:  # ruff: ignore[invalid-function-name]  # the Windows API's name
        """Record a timer resolution release, or raise the failure this stand-in was made with.

        Returns:
            int: 0, TIMERR_NOERROR.

        """
        if self.failure is not None:
            raise self.failure
        self.calls.append(('timeEndPeriod', period))
        return 0


class TestFastTimerWindowsTimerResolution:
    """On Windows, --windows-timer-1ms asks WinMM for 1 ms timer resolution and gives it back.

    The platform is faked: timing's ``sys`` is replaced with one reporting ``win32``, and
    ``ctypes.windll`` (absent off Windows) with a recording stand-in.
    """

    @pytest.fixture
    def on_windows(self, mocker):
        """Make glitchygames.timing see a Windows platform."""
        from glitchygames import timing

        mocker.patch.object(timing, 'sys', mocker.Mock(platform='win32'))

    def test_requests_and_releases_1ms_resolution(self, on_windows, monkeypatch):
        """The timer begins a 1 ms period at construction and ends it when closed, once."""
        import ctypes

        winmm = FakeWinmm()
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)

        timer = FastTimer(windows_timer_1ms=True)
        assert timer._win_period_on is True
        assert winmm.calls == [('timeBeginPeriod', 1)]

        timer.close()
        assert winmm.calls == [('timeBeginPeriod', 1), ('timeEndPeriod', 1)]

        # Closed: neither a second close nor the finaliser ends the period again
        timer.close()
        timer.__del__()
        assert winmm.calls == [('timeBeginPeriod', 1), ('timeEndPeriod', 1)]

    def test_the_finaliser_releases_a_timer_never_closed(self, on_windows, monkeypatch):
        """A timer dropped without close still gives the resolution back."""
        import ctypes

        winmm = FakeWinmm()
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)
        timer = FastTimer(windows_timer_1ms=True)

        del timer

        assert winmm.calls == [('timeBeginPeriod', 1), ('timeEndPeriod', 1)]

    def test_closing_off_windows_ends_the_period_without_winmm(self, mocker, monkeypatch):
        """A timer whose period is on, closed on another platform, just marks it ended."""
        import ctypes

        from glitchygames import timing

        winmm = FakeWinmm()
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)
        timer = FastTimer(windows_timer_1ms=False)
        timer._win_period_on = True
        mocker.patch.object(timing, 'sys', mocker.Mock(platform='darwin'))

        timer.close()

        assert timer._win_period_on is False
        assert winmm.calls == []

    def test_without_the_flag_winmm_is_not_touched(self, on_windows, monkeypatch):
        """Without windows_timer_1ms, a Windows timer leaves the system timer alone."""
        import ctypes

        winmm = FakeWinmm()
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)

        timer = FastTimer()

        assert timer._win_period_on is False
        assert winmm.calls == []

    def test_unavailable_winmm_leaves_the_resolution_alone(self, on_windows, monkeypatch, caplog):
        """Without ctypes.windll the request fails quietly (debug log) and nothing is released."""
        import ctypes

        monkeypatch.delattr(ctypes, 'windll', raising=False)

        with caplog.at_level('DEBUG', logger='glitchygames.timing'):
            timer = FastTimer(windows_timer_1ms=True)

        assert timer._win_period_on is False
        assert 'Windows timer resolution setup failed' in caplog.text

    def test_a_failed_release_is_logged_not_raised(self, on_windows, monkeypatch, caplog):
        """An error ending the period in close is logged at debug level, never raised."""
        import ctypes

        winmm = FakeWinmm(failure=OSError('winmm went away'))
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)
        timer = FastTimer(windows_timer_1ms=True)

        with caplog.at_level('DEBUG', logger='glitchygames.timing'):
            timer.close()

        assert 'Windows timer resolution cleanup failed: winmm went away' in caplog.text

    def test_the_finaliser_logs_nothing(self, on_windows, monkeypatch, caplog):
        """A failed release in __del__ is neither logged nor raised: a finaliser does no I/O."""
        import ctypes

        winmm = FakeWinmm(failure=OSError('winmm went away'))
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)
        timer = FastTimer(windows_timer_1ms=True)

        with caplog.at_level('DEBUG'):
            timer.__del__()

        assert caplog.records == []
        assert timer._win_period_on is False

    def test_a_finaliser_run_mid_write_does_not_write(self, on_windows, monkeypatch, caplog):
        """BUGS.md #188: a timer finalised while a log record is being written stays silent.

        The garbage collector can run a finaliser at any allocation, including inside a write to
        the stream a log handler writes to (pytest's live logging writes to stdout). A finaliser
        that logged there would write to that stream again from inside its own write, and the
        stream's buffer refuses that (``RuntimeError: reentrant call inside
        <_io.BufferedWriter>``), reported as an unraisable exception. Here the last reference to
        a timer whose release fails (the logging path the finaliser used to take) is dropped
        from inside the raw write, deterministically, as the collector would.
        """
        import ctypes

        winmm = FakeWinmm(failure=OSError('winmm went away'))
        monkeypatch.setattr(ctypes, 'windll', fake_windll(winmm=winmm), raising=False)
        unraisable_errors: list[BaseException | None] = []
        monkeypatch.setattr(
            sys, 'unraisablehook', lambda unraisable: unraisable_errors.append(unraisable.exc_value)
        )
        timer_holder = [FastTimer(windows_timer_1ms=True)]
        raw_stream = RawStreamRunningDuringWrite(during_write=timer_holder.clear)
        log_stream = io.TextIOWrapper(
            io.BufferedWriter(raw_stream), encoding='utf-8', write_through=True
        )
        handler = RaisingStreamHandler(log_stream)
        timing_logger = logging.getLogger('glitchygames.timing')
        caplog.set_level('DEBUG', logger='glitchygames.timing')
        timing_logger.addHandler(handler)
        try:
            timing_logger.debug('a record being written when the timer is finalised')
        finally:
            timing_logger.removeHandler(handler)

        assert timer_holder == []
        assert unraisable_errors == []
        # The text stream writes the platform's line ending (\r\n on Windows)
        expected = f'a record being written when the timer is finalised{os.linesep}'.encode()
        assert raw_stream.written == expected


def fake_windll(*, winmm: FakeWinmm) -> SimpleNamespace:
    """Return a ctypes.windll stand-in whose winmm is the given recorder.

    Returns:
        SimpleNamespace: An object with only a ``winmm`` attribute.

    """
    return SimpleNamespace(winmm=winmm)


class RawStreamRunningDuringWrite(io.RawIOBase):
    """A raw stream that runs a callback inside its first write, as a garbage collection would.

    A BufferedWriter holds its lock while it writes to its raw stream, so anything the callback
    writes to the same buffer is a reentrant call.
    """

    def __init__(self, *, during_write: Callable[[], None]) -> None:
        """Keep the callback to run inside the first write."""
        super().__init__()
        self.during_write: Callable[[], None] | None = during_write
        self.written = bytearray()

    @override
    def writable(self) -> bool:
        """Accept writes.

        Returns:
            bool: True.

        """
        return True

    @override
    def write(self, data: Buffer) -> int:
        """Keep the bytes, running the callback the first time.

        Returns:
            int: How many bytes were written (all of them).

        """
        callback, self.during_write = self.during_write, None
        if callback is not None:
            callback()
        written_bytes = bytes(data)
        self.written.extend(written_bytes)
        return len(written_bytes)


class RaisingStreamHandler(logging.StreamHandler):
    """A stream handler that raises a write's error, as pytest's logging handlers do."""

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        """Raise the error being handled (the emit's) instead of printing it."""
        handled_error = sys.exception()
        if handled_error is not None:
            raise handled_error
