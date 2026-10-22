#!/usr/bin/env python3
"""Test logarithmic speed-up behavior for BallSprite.

SpeedUpCurve.LOGARITHMIC gives big early boosts that taper off:
speed after n steps = s0 * (1 + k * ln(1 + n)), with k = multiplier - 1.
"""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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


def _ball_with_logarithmic_speed_up(**settings_fields) -> BallSprite:
    """Create a ball whose SpeedUpSettings use the LOGARITHMIC curve plus the given fields.

    Returns:
        BallSprite: The ball.

    """
    return BallSprite(
        speed_up_settings=SpeedUpSettings(curve=SpeedUpCurve.LOGARITHMIC, **settings_fields),
    )


def _logarithmic_curve_value(multiplier: float, completed_steps: int) -> float:
    """Return the documented LOGARITHMIC growth factor f(n) = 1 + k * ln(1 + n)."""
    return 1.0 + (multiplier - 1.0) * math.log1p(completed_steps)


def _magnitude(ball: BallSprite) -> float:
    """Return the length of the ball's velocity vector."""
    return math.hypot(ball.speed.x, ball.speed.y)


def _bounce_off_top_wall(ball: BallSprite) -> None:
    """Put the ball just past the top wall and run the real boundary bounce."""
    ball.world_x = WALL_TEST_X
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_y = -float(ball._visible_rect().offset_y) - WALL_OVERSHOOT
    ball._do_bounce()


class TestBallLogarithmicSpeedUp:
    """Test BallSprite logarithmic speed-up behavior."""

    def test_logarithmic_x_speed_up(self):
        """Test X_ONLY logarithmic speed-up scales only speed.x by f(1) = 1 + k * ln 2."""
        ball = _ball_with_logarithmic_speed_up(axes=SpeedUpAxes.X_ONLY, multiplier=1.2)
        ball.speed = Speed(100.0, 200.0)

        ball.speed_up()

        assert ball.speed.x == pytest.approx(
            100.0 * _logarithmic_curve_value(1.2, 1), rel=RELATIVE_TOLERANCE
        )
        assert ball.speed.y == pytest.approx(200.0, rel=RELATIVE_TOLERANCE)

    def test_logarithmic_y_speed_up(self):
        """Test Y_ONLY logarithmic speed-up scales only speed.y."""
        ball = _ball_with_logarithmic_speed_up(axes=SpeedUpAxes.Y_ONLY, multiplier=1.3)
        ball.speed = Speed(100.0, 200.0)

        ball.speed_up()

        assert ball.speed.x == pytest.approx(100.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(
            200.0 * _logarithmic_curve_value(1.3, 1), rel=RELATIVE_TOLERANCE
        )

    def test_logarithmic_both_speed_up(self):
        """Test BOTH logarithmic speed-up scales both components by the same factor."""
        ball = _ball_with_logarithmic_speed_up(axes=SpeedUpAxes.BOTH, multiplier=1.15)
        ball.speed = Speed(100.0, 200.0)

        ball.speed_up()

        expected_factor = _logarithmic_curve_value(1.15, 1)
        assert ball.speed.x == pytest.approx(100.0 * expected_factor, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(200.0 * expected_factor, rel=RELATIVE_TOLERANCE)

    def test_logarithmic_x_speed_up_with_wall_bounce(self):
        """Test a real top-wall bounce with X_ONLY scales speed.x; speed.y is only reflected."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.WALL_BOUNCE,
            axes=SpeedUpAxes.X_ONLY,
            multiplier=1.25,
        )
        ball.bounce_left_right = True
        ball.speed = Speed(150.0, -100.0)

        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(
            150.0 * _logarithmic_curve_value(1.25, 1), rel=RELATIVE_TOLERANCE
        )
        assert ball.speed.y == pytest.approx(100.0, rel=RELATIVE_TOLERANCE)

    def test_logarithmic_y_speed_up_with_wall_bounce(self):
        """Test a real top-wall bounce with Y_ONLY scales the reflected speed.y only."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.WALL_BOUNCE,
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.3,
        )
        ball.bounce_left_right = True
        ball.speed = Speed(150.0, -100.0)

        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(150.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(
            100.0 * _logarithmic_curve_value(1.3, 1), rel=RELATIVE_TOLERANCE
        )

    def test_logarithmic_both_speed_up_with_wall_bounce(self):
        """Test a real top-wall bounce with BOTH scales both components."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.WALL_BOUNCE,
            axes=SpeedUpAxes.BOTH,
            multiplier=1.2,
        )
        ball.bounce_left_right = True
        ball.speed = Speed(150.0, -100.0)

        _bounce_off_top_wall(ball)

        expected_factor = _logarithmic_curve_value(1.2, 1)
        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(150.0 * expected_factor, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(100.0 * expected_factor, rel=RELATIVE_TOLERANCE)

    def test_logarithmic_wall_bounce_ignored_when_trigger_not_enabled(self):
        """Test a real wall bounce only reflects the ball when WALL_BOUNCE is not configured."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.CONTINUOUS,
            multiplier=1.2,
        )
        ball.speed = Speed(150.0, -100.0)

        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 0
        assert ball.speed.x == pytest.approx(150.0)
        assert ball.speed.y == pytest.approx(100.0)

    def test_logarithmic_x_speed_up_with_paddle_bounce(self):
        """Test paddle bounces with X_ONLY follow the curve on speed.x only."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE,
            axes=SpeedUpAxes.X_ONLY,
            multiplier=1.4,
        )
        ball.speed = Speed(200.0, 150.0)

        for completed_steps in range(1, 6):
            ball.on_paddle_bounce()
            assert ball.speed.x == pytest.approx(
                200.0 * _logarithmic_curve_value(1.4, completed_steps), rel=RELATIVE_TOLERANCE
            )
            assert ball.speed.y == pytest.approx(150.0, rel=RELATIVE_TOLERANCE)

    def test_logarithmic_y_speed_up_with_paddle_bounce(self):
        """Test paddle bounces with Y_ONLY follow the curve on speed.y only."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE,
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.35,
        )
        ball.speed = Speed(200.0, 150.0)

        for completed_steps in range(1, 6):
            ball.on_paddle_bounce()
            assert ball.speed.x == pytest.approx(200.0, rel=RELATIVE_TOLERANCE)
            assert ball.speed.y == pytest.approx(
                150.0 * _logarithmic_curve_value(1.35, completed_steps), rel=RELATIVE_TOLERANCE
            )

    def test_logarithmic_paddle_bounce_ignored_when_trigger_not_enabled(self):
        """Test on_paddle_bounce does nothing with the default (NONE) triggers."""
        ball = _ball_with_logarithmic_speed_up(multiplier=1.4)
        ball.speed = Speed(200.0, 150.0)

        ball.on_paddle_bounce()

        assert ball.speed_up_count == 0
        assert ball.speed.x == pytest.approx(200.0)
        assert ball.speed.y == pytest.approx(150.0)

    def test_logarithmic_continuous_speed_up(self):
        """Test continuous logarithmic speed-up for X_ONLY and Y_ONLY balls."""
        ball_x_only = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS,
            axes=SpeedUpAxes.X_ONLY,
            multiplier=1.1,
            interval=0.1,
        )
        ball_x_only.speed = Speed(100.0, 200.0)
        ball_x_only._advance_continuous_speed_up(0.1)

        assert ball_x_only.speed.x == pytest.approx(100.0 * _logarithmic_curve_value(1.1, 1))
        assert ball_x_only.speed.y == pytest.approx(200.0)

        ball_y_only = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS,
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.15,
            interval=0.1,
        )
        ball_y_only.speed = Speed(100.0, 200.0)
        ball_y_only._advance_continuous_speed_up(0.1)

        assert ball_y_only.speed.x == pytest.approx(100.0)
        assert ball_y_only.speed.y == pytest.approx(200.0 * _logarithmic_curve_value(1.15, 1))

    def test_logarithmic_continuous_speed_up_over_many_intervals(self):
        """Test one step per elapsed interval follows the curve; half intervals do nothing."""
        ball = _ball_with_logarithmic_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS,
            multiplier=1.5,
            interval=0.5,
        )
        ball.speed = Speed(30.0, 40.0)  # Magnitude 50

        for interval_number in range(1, PROGRESSION_STEPS + 1):
            ball._advance_continuous_speed_up(0.25)  # Mid-interval
            assert ball.speed_up_count == interval_number - 1
            ball._advance_continuous_speed_up(0.25)  # Completes the interval
            assert ball.speed_up_count == interval_number
            assert _magnitude(ball) == pytest.approx(
                50.0 * _logarithmic_curve_value(1.5, interval_number), rel=1e-10
            )

    def test_logarithmic_speed_up_preserves_direction(self):
        """Test that BOTH logarithmic speed-up preserves direction over many steps."""
        ball = _ball_with_logarithmic_speed_up(multiplier=1.5)
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        for _ in range(PROGRESSION_STEPS):
            ball.speed_up()
            new_direction = math.atan2(ball.speed.y, ball.speed.x)
            assert initial_direction == pytest.approx(new_direction, abs=1e-12)

    def test_logarithmic_speed_up_multiple_applications(self):
        """Test three logarithmic speed-ups give 1 + k * ln 4, not compounding 1.2**3."""
        ball = _ball_with_logarithmic_speed_up(multiplier=1.2)
        ball.speed = Speed(50.0, 50.0)

        for _ in range(3):
            ball.speed_up()

        expected_factor = 1.0 + 0.2 * math.log(4.0)
        assert ball.speed.x == pytest.approx(50.0 * expected_factor)
        assert ball.speed.y == pytest.approx(50.0 * expected_factor)
        # The old (wrong) LOGARITHMIC behavior compounded to 1.2**3
        assert ball.speed.x < 50.0 * 1.2**3

    def test_logarithmic_speed_up_with_negative_speeds(self):
        """Test logarithmic speed-up makes negative components more negative."""
        ball = _ball_with_logarithmic_speed_up(multiplier=1.3)
        ball.speed = Speed(-100.0, -200.0)

        ball.speed_up()

        expected_factor = _logarithmic_curve_value(1.3, 1)
        assert ball.speed.x == pytest.approx(-100.0 * expected_factor)
        assert ball.speed.y == pytest.approx(-200.0 * expected_factor)

    def test_logarithmic_speed_up_with_zero_component(self):
        """Test Y_ONLY on a zero Y component changes nothing: zero stays zero, X untouched."""
        ball = _ball_with_logarithmic_speed_up(axes=SpeedUpAxes.Y_ONLY, multiplier=1.5)
        ball.speed = Speed(100.0, 0.0)

        for _ in range(5):
            ball.speed_up()

        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)
        assert ball.speed.x == pytest.approx(100.0)
        assert ball.speed_up_count == 5

    @pytest.mark.parametrize('multiplier', [1.01, 1.05, 1.1, 1.15, 1.2, 1.5, 2.0])
    def test_logarithmic_speed_up_precision(self, multiplier):
        """Test the first step is exactly 1 + k * ln 2 for various multipliers."""
        ball = _ball_with_logarithmic_speed_up(multiplier=multiplier)
        ball.speed = Speed(100.0, 200.0)

        ball.speed_up()

        expected_factor = 1.0 + (multiplier - 1.0) * math.log(2.0)
        assert ball.speed.x == pytest.approx(100.0 * expected_factor, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(200.0 * expected_factor, rel=RELATIVE_TOLERANCE)


class TestBallLogarithmicCurveProperties:
    """Test the LOGARITHMIC curve over many steps: closed form, tapering growth, caps, reset."""

    @pytest.mark.parametrize('multiplier', [1.01, 1.1, 1.25, 1.5, 2.0, 3.0])
    @pytest.mark.parametrize(
        ('base_speed_x', 'base_speed_y'), [(250.0, 125.0), (-80.0, 60.0), (3.0, -400.0)]
    )
    def test_logarithmic_progression_matches_closed_form(
        self, multiplier, base_speed_x, base_speed_y
    ):
        """Test speed after n = 0..20 steps is exactly s0 * (1 + k * ln(1 + n))."""
        ball = _ball_with_logarithmic_speed_up(multiplier=multiplier)
        ball.speed = Speed(base_speed_x, base_speed_y)

        for completed_steps in range(PROGRESSION_STEPS + 1):
            expected_factor = _logarithmic_curve_value(multiplier, completed_steps)
            assert ball.speed_up_count == completed_steps
            assert ball.speed.x == pytest.approx(
                base_speed_x * expected_factor, rel=RELATIVE_TOLERANCE
            )
            assert ball.speed.y == pytest.approx(
                base_speed_y * expected_factor, rel=RELATIVE_TOLERANCE
            )
            ball.speed_up()

    @pytest.mark.parametrize('multiplier', [1.05, 1.2, 2.0])
    def test_logarithmic_increments_shrink_but_stay_positive(self, multiplier):
        """Test each step adds less speed than the previous one, but always some."""
        ball = _ball_with_logarithmic_speed_up(multiplier=multiplier)
        ball.speed = Speed(120.0, -160.0)

        previous_magnitude = _magnitude(ball)
        previous_increment = math.inf
        for completed_steps in range(PROGRESSION_STEPS * 5):
            ratio = speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, multiplier, completed_steps)
            assert ratio > 1.0
            ball.speed_up()
            current_magnitude = _magnitude(ball)
            current_increment = current_magnitude - previous_magnitude
            assert 0.0 < current_increment < previous_increment, (
                f'increment did not shrink at step {completed_steps + 1}'
            )
            previous_increment = current_increment
            previous_magnitude = current_magnitude

    def test_logarithmic_stays_far_below_exponential(self):
        """Test after many steps LOGARITHMIC is far slower than EXPONENTIAL and LINEAR."""
        multiplier = 1.1
        steps = 50
        base_speed = Speed(150.0, 200.0)  # Magnitude 250
        final_magnitudes = {}
        for curve in SpeedUpCurve:
            ball = BallSprite(speed_up_settings=SpeedUpSettings(curve=curve, multiplier=multiplier))
            ball.speed = Speed(base_speed.x, base_speed.y)
            for _ in range(steps):
                ball.speed_up()
            final_magnitudes[curve] = _magnitude(ball)

        logarithmic_magnitude = final_magnitudes[SpeedUpCurve.LOGARITHMIC]
        assert logarithmic_magnitude == pytest.approx(
            250.0 * _logarithmic_curve_value(multiplier, steps), rel=1e-10
        )
        # 1 + 0.1 * ln 51 is about 1.39x, versus 1.1**50 (about 117x) and 1 + 50 * 0.1 = 6x
        assert logarithmic_magnitude < 1.5 * 250.0
        assert final_magnitudes[SpeedUpCurve.EXPONENTIAL] > 50.0 * logarithmic_magnitude
        assert final_magnitudes[SpeedUpCurve.LINEAR] > 4.0 * logarithmic_magnitude

    def test_logarithmic_multiplier_of_one_never_changes_speed(self):
        """Test multiplier=1.0 (k = 0) leaves speed untouched while still counting steps."""
        ball = _ball_with_logarithmic_speed_up(multiplier=1.0)
        ball.speed = Speed(-130.0, 70.0)

        for _ in range(PROGRESSION_STEPS):
            ball.speed_up()

        assert ball.speed.x == pytest.approx(-130.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(70.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed_up_count == PROGRESSION_STEPS

    def test_logarithmic_reset_restarts_curve(self):
        """Test reset() returns to step 0, so the next step is the large first boost again."""
        multiplier = 2.0
        ball = _ball_with_logarithmic_speed_up(multiplier=multiplier)
        for _ in range(10):
            ball.speed_up()
        assert ball.speed_up_count == 10

        ball.reset()
        assert ball.speed_up_count == 0
        speed_after_reset_x = ball.speed.x
        speed_after_reset_y = ball.speed.y

        ball.speed_up()

        first_step_factor = _logarithmic_curve_value(multiplier, 1)
        assert ball.speed.x == pytest.approx(speed_after_reset_x * first_step_factor)
        assert ball.speed.y == pytest.approx(speed_after_reset_y * first_step_factor)
        # Without the reset the step would have been the much smaller f(11) / f(10)
        assert first_step_factor > speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, multiplier, 10)

    def test_logarithmic_speed_up_clamped_to_max_speed(self):
        """Test max_speed caps the magnitude (keeping direction) once the curve reaches it."""
        multiplier = 2.0
        ball = _ball_with_logarithmic_speed_up(multiplier=multiplier, max_speed=300.0)
        ball.speed = Speed(120.0, 160.0)  # Magnitude 200
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # f(n) = 1 + ln(1 + n) passes 1.5 (300 px/s) at n = 1 (1.69)
        ball.speed_up()
        assert _magnitude(ball) == pytest.approx(300.0)

        for _ in range(10):
            ball.speed_up()
            assert _magnitude(ball) == pytest.approx(300.0)
            assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)

    def test_logarithmic_curve_below_max_speed_is_not_clamped(self):
        """Test a max_speed above the reachable curve never alters the progression."""
        multiplier = 1.1
        ball = _ball_with_logarithmic_speed_up(multiplier=multiplier, max_speed=10_000.0)
        ball.speed = Speed(150.0, 200.0)  # Magnitude 250

        for completed_steps in range(1, PROGRESSION_STEPS + 1):
            ball.speed_up()
            assert _magnitude(ball) == pytest.approx(
                250.0 * _logarithmic_curve_value(multiplier, completed_steps),
                rel=RELATIVE_TOLERANCE,
            )
