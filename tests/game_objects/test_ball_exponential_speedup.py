#!/usr/bin/env python3
"""Tests for the exponential speed-up curve in BallSprite.

SpeedUpCurve.EXPONENTIAL grows speed by the same percentage every step:
speed after n steps = s0 * multiplier**n, independent of how fast the ball is going.
"""

import math

import pytest

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from glitchygames.movement import Speed

RELATIVE_TOLERANCE = 1e-12
PROGRESSION_STEPS = 20
# A horizontal position well away from the left/right walls (screen is 800 wide)
WALL_TEST_X = 400.0
# How far past a wall the ball is placed before _do_bounce() reflects it
WALL_OVERSHOOT = 2.0


def _ball_with_exponential_speed_up(**settings_fields) -> BallSprite:
    """Create a ball whose SpeedUpSettings use the EXPONENTIAL curve plus the given fields.

    Returns:
        BallSprite: The ball.

    """
    return BallSprite(
        speed_up_settings=SpeedUpSettings(curve=SpeedUpCurve.EXPONENTIAL, **settings_fields),
    )


def _magnitude(ball: BallSprite) -> float:
    """Return the length of the ball's velocity vector."""
    return math.hypot(ball.speed.x, ball.speed.y)


def _bounce_off_top_wall(ball: BallSprite) -> None:
    """Put the ball just past the top wall and run the real boundary bounce."""
    ball.world_x = WALL_TEST_X
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_y = -float(ball._visible_rect().offset_y) - WALL_OVERSHOOT
    ball._do_bounce()


class TestBallExponentialSpeedUp:
    """Test exponential speed-up functionality."""

    def test_exponential_x_speed_up(self):
        """Test X_ONLY exponential speed-up scales only the horizontal component."""
        ball = _ball_with_exponential_speed_up(axes=SpeedUpAxes.X_ONLY, multiplier=1.2)
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        ball.speed_up()

        assert ball.speed.x == pytest.approx(100.0 * 1.2, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(50.0, rel=RELATIVE_TOLERANCE)

    def test_exponential_y_speed_up(self):
        """Test Y_ONLY exponential speed-up scales only the vertical component."""
        ball = _ball_with_exponential_speed_up(axes=SpeedUpAxes.Y_ONLY, multiplier=1.5)
        ball.speed.x = 200.0
        ball.speed.y = 150.0

        ball.speed_up()

        assert ball.speed.x == pytest.approx(200.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(150.0 * 1.5, rel=RELATIVE_TOLERANCE)

    def test_exponential_both_speed_up(self):
        """Test BOTH exponential speed-up scales both components by the multiplier."""
        ball = _ball_with_exponential_speed_up(axes=SpeedUpAxes.BOTH, multiplier=1.3)
        ball.speed.x = 80.0
        ball.speed.y = 120.0
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        ball.speed_up()

        assert ball.speed.x == pytest.approx(80.0 * 1.3, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(120.0 * 1.3, rel=RELATIVE_TOLERANCE)
        assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)

    def test_exponential_speed_up_with_zero_speed(self):
        """Test X_ONLY speed-up on a zero X component leaves both components unchanged."""
        ball = _ball_with_exponential_speed_up(axes=SpeedUpAxes.X_ONLY, multiplier=1.2)
        ball.speed.x = 0.0
        ball.speed.y = 100.0

        for _ in range(5):
            ball.speed_up()

        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)
        assert math.isclose(ball.speed.y, 100.0)
        assert ball.speed_up_count == 5

    def test_continuous_exponential_speed_up(self):
        """Test continuous exponential speed-up fires once per interval of game time."""
        ball = _ball_with_exponential_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS,
            multiplier=1.1,
            interval=0.25,  # Exactly representable, so elapsed-time math is exact
        )
        ball.speed.x = 50.0
        ball.speed.y = 75.0

        # Two intervals elapse in one advance, but the default FIXED_RATE schedule applies
        # only one step (no catch-up) and drops the extra whole interval
        ball._advance_continuous_speed_up(0.5)

        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(50.0 * 1.1, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(75.0 * 1.1, rel=RELATIVE_TOLERANCE)
        assert ball._continuous_elapsed_time == pytest.approx(0.0)

        ball._advance_continuous_speed_up(0.125)  # Half an interval later: nothing
        assert ball.speed_up_count == 1

        ball._advance_continuous_speed_up(0.125)  # Completes the interval
        for _ in range(4):
            ball._advance_continuous_speed_up(0.25)

        assert ball.speed_up_count == 6
        assert ball.speed.x == pytest.approx(50.0 * 1.1**6, rel=1e-9)
        assert ball.speed.y == pytest.approx(75.0 * 1.1**6, rel=1e-9)

    def test_continuous_exponential_ignored_when_trigger_not_enabled(self):
        """Test elapsed time does nothing when CONTINUOUS is not a configured trigger."""
        ball = _ball_with_exponential_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE,
            multiplier=1.1,
            interval=0.1,
        )
        ball.speed = Speed(50.0, 75.0)

        ball._advance_continuous_speed_up(10.0)

        assert ball.speed_up_count == 0
        assert ball.speed.x == pytest.approx(50.0)
        assert ball.speed.y == pytest.approx(75.0)

    def test_paddle_bounce_exponential_speed_up(self):
        """Test each paddle bounce multiplies speed by the same factor, whatever the speed."""
        ball = _ball_with_exponential_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE,
            multiplier=1.4,
        )
        ball.speed.x = 200.0
        ball.speed.y = 100.0

        for completed_steps in range(1, 6):
            ball.on_paddle_bounce()
            assert ball.speed.x == pytest.approx(200.0 * 1.4**completed_steps, rel=1e-9)
            assert ball.speed.y == pytest.approx(100.0 * 1.4**completed_steps, rel=1e-9)

    def test_paddle_bounce_exponential_ignored_when_trigger_not_enabled(self):
        """Test on_paddle_bounce does nothing when PADDLE_BOUNCE is not configured."""
        ball = _ball_with_exponential_speed_up(
            triggers=SpeedUpTrigger.WALL_BOUNCE,
            multiplier=1.4,
        )
        ball.speed = Speed(200.0, 100.0)

        ball.on_paddle_bounce()

        assert ball.speed_up_count == 0
        assert ball.speed.x == pytest.approx(200.0)
        assert ball.speed.y == pytest.approx(100.0)

    def test_wall_bounce_exponential_speed_up(self):
        """Test a real top-wall bounce with Y_ONLY scales only the reflected Y component."""
        ball = _ball_with_exponential_speed_up(
            triggers=SpeedUpTrigger.WALL_BOUNCE,
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.3,
        )
        ball.speed.x = 150.0
        ball.speed.y = -80.0

        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(150.0, rel=RELATIVE_TOLERANCE)
        # Reflected downward by the bounce, then scaled
        assert ball.speed.y == pytest.approx(80.0 * 1.3, rel=RELATIVE_TOLERANCE)

    def test_combined_exponential_triggers(self):
        """Test all triggers combined share one step counter on the same constant ratio."""
        ball = _ball_with_exponential_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS
            | SpeedUpTrigger.PADDLE_BOUNCE
            | SpeedUpTrigger.WALL_BOUNCE,
            multiplier=1.2,
            interval=0.1,
        )
        ball.speed.x = 100.0
        ball.speed.y = -200.0

        ball._advance_continuous_speed_up(0.2)
        ball.on_paddle_bounce()
        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 3
        assert ball.speed.x == pytest.approx(100.0 * 1.2**3, rel=1e-9)
        # The top-wall bounce reflected Y downward
        assert ball.speed.y == pytest.approx(200.0 * 1.2**3, rel=1e-9)

    def test_exponential_curve_differs_from_linear_and_logarithmic(self):
        """Test the curve setting alone picks the growth: same multiplier, different speeds.

        Replaces the old "exponential has priority over logarithmic" flag test; a ball now
        has exactly one curve, so the meaningful check is that EXPONENTIAL outgrows the
        other curves from the same start.
        """
        multiplier = 1.2
        steps = 10
        final_magnitudes = {}
        for curve in SpeedUpCurve:
            ball = BallSprite(speed_up_settings=SpeedUpSettings(curve=curve, multiplier=multiplier))
            ball.speed = Speed(100.0, 50.0)
            for _ in range(steps):
                ball.speed_up()
            final_magnitudes[curve] = _magnitude(ball)

        initial_magnitude = math.hypot(100.0, 50.0)
        assert final_magnitudes[SpeedUpCurve.EXPONENTIAL] == pytest.approx(
            initial_magnitude * multiplier**steps, rel=1e-9
        )
        assert (
            final_magnitudes[SpeedUpCurve.EXPONENTIAL]
            > final_magnitudes[SpeedUpCurve.LINEAR]
            > final_magnitudes[SpeedUpCurve.LOGARITHMIC]
        )

    def test_exponential_speed_up_extreme_values(self):
        """Test the ratio does not depend on the current speed (no speed-based exponent)."""
        ball = _ball_with_exponential_speed_up(multiplier=1.1)
        ball.speed.x = 1000.0
        ball.speed.y = 500.0

        ball.speed_up()

        assert ball.speed.x == pytest.approx(1000.0 * 1.1, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(500.0 * 1.1, rel=RELATIVE_TOLERANCE)

        slow_ball = _ball_with_exponential_speed_up(multiplier=1.1)
        slow_ball.speed = Speed(0.5, 0.25)
        slow_ball.speed_up()

        assert slow_ball.speed.x == pytest.approx(0.5 * 1.1, rel=RELATIVE_TOLERANCE)
        assert slow_ball.speed.y == pytest.approx(0.25 * 1.1, rel=RELATIVE_TOLERANCE)

    def test_exponential_speed_up_negative_speed(self):
        """Test exponential speed-up keeps the sign of negative components."""
        ball = _ball_with_exponential_speed_up(multiplier=1.2)
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        ball.speed_up()

        assert ball.speed.x == pytest.approx(-100.0 * 1.2, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(50.0 * 1.2, rel=RELATIVE_TOLERANCE)


class TestBallExponentialCurveProperties:
    """Test the EXPONENTIAL curve over many steps: closed form, constant ratio, caps, reset."""

    @pytest.mark.parametrize('multiplier', [1.01, 1.1, 1.25, 1.5, 2.0])
    @pytest.mark.parametrize(
        ('base_speed_x', 'base_speed_y'), [(250.0, 125.0), (-80.0, 60.0), (3.0, -400.0)]
    )
    def test_exponential_progression_matches_closed_form(
        self, multiplier, base_speed_x, base_speed_y
    ):
        """Test speed after n = 0..20 steps is s0 * multiplier**n for each component."""
        ball = _ball_with_exponential_speed_up(multiplier=multiplier)
        ball.speed = Speed(base_speed_x, base_speed_y)

        for completed_steps in range(PROGRESSION_STEPS + 1):
            expected_factor = multiplier**completed_steps
            assert ball.speed_up_count == completed_steps
            assert ball.speed.x == pytest.approx(base_speed_x * expected_factor, rel=1e-10)
            assert ball.speed.y == pytest.approx(base_speed_y * expected_factor, rel=1e-10)
            ball.speed_up()

    @pytest.mark.parametrize('multiplier', [1.05, 1.2, 2.0])
    def test_exponential_ratio_is_constant_per_step(self, multiplier):
        """Test every step multiplies speed by the same ratio (the defining property)."""
        ball = _ball_with_exponential_speed_up(multiplier=multiplier)
        ball.speed = Speed(120.0, -160.0)

        previous_magnitude = _magnitude(ball)
        previous_increment = 0.0
        for completed_steps in range(PROGRESSION_STEPS):
            assert speed_up_step_ratio(
                SpeedUpCurve.EXPONENTIAL, multiplier, completed_steps
            ) == pytest.approx(multiplier, rel=RELATIVE_TOLERANCE)
            ball.speed_up()
            current_magnitude = _magnitude(ball)
            assert current_magnitude / previous_magnitude == pytest.approx(
                multiplier, rel=RELATIVE_TOLERANCE
            )
            # Absolute increments grow every step, unlike LINEAR
            current_increment = current_magnitude - previous_magnitude
            assert current_increment > previous_increment
            previous_increment = current_increment
            previous_magnitude = current_magnitude

    def test_exponential_multiplier_of_one_never_changes_speed(self):
        """Test multiplier=1.0 leaves speed untouched while still counting steps."""
        ball = _ball_with_exponential_speed_up(multiplier=1.0)
        ball.speed = Speed(-130.0, 70.0)

        for _ in range(PROGRESSION_STEPS):
            ball.speed_up()

        assert ball.speed.x == pytest.approx(-130.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(70.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed_up_count == PROGRESSION_STEPS

    def test_exponential_reset_restarts_count(self):
        """Test reset() returns the step counter to 0 and the next step is again x multiplier."""
        ball = _ball_with_exponential_speed_up(multiplier=1.3)
        for _ in range(4):
            ball.speed_up()
        assert ball.speed_up_count == 4

        ball.reset()
        assert ball.speed_up_count == 0
        speed_after_reset_x = ball.speed.x
        speed_after_reset_y = ball.speed.y

        ball.speed_up()

        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(speed_after_reset_x * 1.3, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(speed_after_reset_y * 1.3, rel=RELATIVE_TOLERANCE)

    def test_exponential_speed_up_clamped_to_max_speed(self):
        """Test max_speed caps the magnitude and keeps the trajectory angle."""
        ball = _ball_with_exponential_speed_up(multiplier=2.0, max_speed=500.0)
        ball.speed = Speed(-60.0, 80.0)  # Magnitude 100
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        expected_magnitudes = [200.0, 400.0, 500.0, 500.0, 500.0]
        for expected_magnitude in expected_magnitudes:
            ball.speed_up()
            assert _magnitude(ball) == pytest.approx(expected_magnitude)
            assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)

        assert ball.speed_up_count == len(expected_magnitudes)

    def test_exponential_y_only_clamped_to_max_speed(self):
        """Test Y_ONLY max_speed caps only |speed.y|, keeping its sign."""
        ball = _ball_with_exponential_speed_up(
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.5,
            max_speed=300.0,
        )
        ball.speed = Speed(900.0, -200.0)

        ball.speed_up()  # Would be -300, exactly the cap
        assert ball.speed.y == pytest.approx(-300.0)
        ball.speed_up()  # Would be -450
        assert ball.speed.y == pytest.approx(-300.0)
        # X is above max_speed but is not a configured axis, so it is not clamped
        assert ball.speed.x == pytest.approx(900.0)

    def test_exponential_x_only_progression(self):
        """Test X_ONLY follows multiplier**n on speed.x for 20 steps; speed.y never changes."""
        ball = _ball_with_exponential_speed_up(axes=SpeedUpAxes.X_ONLY, multiplier=1.1)
        ball.speed = Speed(-40.0, 90.0)

        for completed_steps in range(1, PROGRESSION_STEPS + 1):
            ball.speed_up()
            assert ball.speed.x == pytest.approx(-40.0 * 1.1**completed_steps, rel=1e-10)
            assert ball.speed.y == pytest.approx(90.0, rel=RELATIVE_TOLERANCE)
