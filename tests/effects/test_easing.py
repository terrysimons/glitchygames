"""Tests for easing functions."""

import pytest

from glitchygames.effects.easing import EASING_FUNCTIONS, get_easing


class TestEasingBoundaries:
    """All easing functions must satisfy f(0)=0 and f(1)=1."""

    @pytest.mark.parametrize('name', sorted(EASING_FUNCTIONS.keys()))
    def test_start_at_zero(self, name: str):
        """Every easing function returns 0.0 at t=0.0."""
        easing_function = EASING_FUNCTIONS[name]
        assert easing_function(0.0) == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.parametrize('name', sorted(EASING_FUNCTIONS.keys()))
    def test_end_at_one(self, name: str):
        """Every easing function returns 1.0 at t=1.0."""
        easing_function = EASING_FUNCTIONS[name]
        assert easing_function(1.0) == pytest.approx(1.0, abs=1e-10)


class TestEasingMidpoint:
    """Sanity checks for easing values at t=0.5."""

    def test_linear_midpoint(self):
        """Linear easing returns 0.5 at t=0.5."""
        assert EASING_FUNCTIONS['linear'](0.5) == pytest.approx(0.5)

    def test_ease_in_quad_midpoint(self):
        """Ease-in quad at midpoint is less than 0.5 (still accelerating)."""
        assert EASING_FUNCTIONS['ease_in_quad'](0.5) < 0.5

    def test_ease_out_quad_midpoint(self):
        """Ease-out quad at midpoint is greater than 0.5 (decelerating)."""
        assert EASING_FUNCTIONS['ease_out_quad'](0.5) > 0.5

    def test_ease_in_out_quad_midpoint(self):
        """Ease-in-out quad passes through 0.5 at t=0.5."""
        assert EASING_FUNCTIONS['ease_in_out_quad'](0.5) == pytest.approx(0.5)


class TestEasingOvershoot:
    """Elastic and back curves can overshoot 0.0-1.0 range."""

    def test_ease_out_elastic_overshoots(self):
        """Elastic out overshoots 1.0 during the spring effect."""
        values = [EASING_FUNCTIONS['ease_out_elastic'](t / 20.0) for t in range(21)]
        assert any(value > 1.0 for value in values)

    def test_ease_out_back_overshoots(self):
        """Back out overshoots 1.0 before settling."""
        values = [EASING_FUNCTIONS['ease_out_back'](t / 20.0) for t in range(21)]
        assert any(value > 1.0 for value in values)

    def test_ease_in_back_undershoots(self):
        """Back in goes below 0.0 before accelerating."""
        values = [EASING_FUNCTIONS['ease_in_back'](t / 20.0) for t in range(21)]
        assert any(value < 0.0 for value in values)


IN_OUT_EASING_NAMES = sorted(name for name in EASING_FUNCTIONS if '_in_out_' in name)
# t from 0.0 to 1.0 in steps of 0.05
SAMPLE_TIMES = [step / 20.0 for step in range(21)]


class TestInOutSymmetry:
    """Every in-out curve is point-symmetric about (0.5, 0.5): its two halves mirror each other."""

    @pytest.mark.parametrize('name', IN_OUT_EASING_NAMES)
    def test_second_half_mirrors_the_first(self, name: str):
        """f(t) + f(1 - t) == 1 at every sample, so both halves of the curve are exercised."""
        easing = EASING_FUNCTIONS[name]

        for t in SAMPLE_TIMES:
            assert easing(t) + easing(1.0 - t) == pytest.approx(1.0), t

    @pytest.mark.parametrize('name', IN_OUT_EASING_NAMES)
    def test_halfway_is_half(self, name: str):
        """At t = 0.5 every in-out curve is at 0.5, where its two halves meet."""
        assert EASING_FUNCTIONS[name](0.5) == pytest.approx(0.5)

    def test_in_out_expo_is_slow_at_the_ends(self):
        """Expo in-out barely moves in its first and last tenth (its exponential halves)."""
        easing = EASING_FUNCTIONS['ease_in_out_expo']

        assert easing(0.1) == pytest.approx(0.5 * 2.0**-8)
        assert easing(0.9) == pytest.approx(1.0 - 0.5 * 2.0**-8)

    def test_in_out_elastic_overshoots_both_ways(self):
        """Elastic in-out dips below 0 in its first half and rises above 1 in its second."""
        easing = EASING_FUNCTIONS['ease_in_out_elastic']
        first_half = [easing(t) for t in SAMPLE_TIMES if t < 0.5]
        second_half = [easing(t) for t in SAMPLE_TIMES if t > 0.5]

        assert min(first_half) < 0.0
        assert max(second_half) > 1.0


class TestEaseOutBounce:
    """Penner's bounce: it reaches 1.0 at each bounce and dips less after each one."""

    @pytest.mark.parametrize('boundary', [1.0 / 2.75, 2.0 / 2.75, 2.5 / 2.75])
    def test_touches_one_at_each_bounce(self, boundary: float):
        """At the end of each bounce segment the curve is back at 1.0."""
        assert EASING_FUNCTIONS['ease_out_bounce'](boundary) == pytest.approx(1.0)

    @pytest.mark.parametrize(
        ('bounce_peak_time', 'expected'),
        [(1.5 / 2.75, 0.75), (2.25 / 2.75, 0.9375), (2.625 / 2.75, 0.984375)],
    )
    def test_each_bounce_dips_less(self, bounce_peak_time: float, expected: float):
        """The dips of the three bounces are 0.75, 0.9375 and 0.984375."""
        assert EASING_FUNCTIONS['ease_out_bounce'](bounce_peak_time) == pytest.approx(expected)


class TestEasingCount:
    """Verify we have all 31 easing functions."""

    def test_function_count(self):
        """31 easing functions: linear + 10 families x 3 variants."""
        expected_count = 31
        assert len(EASING_FUNCTIONS) == expected_count


class TestGetEasing:
    """Test the get_easing lookup function."""

    def test_valid_name(self):
        """Returns the correct function for a valid name."""
        easing_function = get_easing('linear')
        assert easing_function(0.5) == pytest.approx(0.5)

    def test_invalid_name_raises(self):
        """Raises KeyError for unknown easing names."""
        with pytest.raises(KeyError, match="Unknown easing function 'nonexistent'"):
            get_easing('nonexistent')
