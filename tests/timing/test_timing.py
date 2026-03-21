"""Tests for timing functionality and coverage."""

import sys

import pytest

from glitchygames.timing import (
    FastTimer,
    PygameTimer,
    create_timer,
    ms_to_ns,
    s_to_ns,
)


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

    def test_ns_now_returns_positive(self):
        timer = PygameTimer()
        now = timer.ns_now()
        assert isinstance(now, int)
        assert now >= 0

    def test_start_frame_with_fps(self):
        timer = PygameTimer()
        period = timer.start_frame(60)
        # 1_000_000_000 // 60 = 16666666
        assert period == 1_000_000_000 // 60

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
        prev = 1_000_000_000
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
        assert period == 1_000_000_000 // 60

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
        prev = 1_000_000_000
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

    def test_create_timer_none_defaults_to_pygame(self):
        timer = create_timer(None)
        assert isinstance(timer, PygameTimer)

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
EXPECTED_PERIOD_60 = ONE_S_IN_NS // TARGET_FPS_60
EXPECTED_PERIOD_120 = ONE_S_IN_NS // TARGET_FPS_120


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
        prev_deadline = 1_000_000_000
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

    def test_create_timer_none_defaults_to_pygame(self, mocker):
        """Test create_timer with None type defaults to PygameTimer."""
        mock_pygame = mocker.MagicMock()
        mocker.patch.dict('sys.modules', {'pygame': mock_pygame})

        from glitchygames.timing import PygameTimer

        timer = create_timer(None)
        assert isinstance(timer, PygameTimer)

    def test_create_timer_from_options_dict(self):
        """Test create_timer reads timer_backend from options dict."""
        options = {'timer_backend': 'fast'}
        timer = create_timer(None, options=options)
        assert isinstance(timer, FastTimer)
