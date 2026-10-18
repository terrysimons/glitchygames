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
