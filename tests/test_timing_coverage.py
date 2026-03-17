"""Tests for glitchygames.timing module - timer backends and factory."""

from glitchygames.timing import FastTimer, PygameTimer, create_timer, ms_to_ns, s_to_ns


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
