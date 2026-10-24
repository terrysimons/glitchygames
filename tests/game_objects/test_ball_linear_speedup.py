#!/usr/bin/env python3
"""Test linear speed-up behavior for BallSprite.

SpeedUpCurve.LINEAR grows speed by the same absolute amount every step:
speed after n steps = s0 * (1 + n * k), with k = multiplier - 1.
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


def _ball_with_linear_speed_up(**settings_fields) -> BallSprite:
    """Create a ball whose SpeedUpSettings use the LINEAR curve plus the given fields.

    Returns:
        BallSprite: The ball.

    """
    return BallSprite(
        speed_up_settings=SpeedUpSettings(curve=SpeedUpCurve.LINEAR, **settings_fields),
    )


def _linear_curve_value(multiplier: float, completed_steps: int) -> float:
    """Return the documented LINEAR growth factor f(n) = 1 + n * (multiplier - 1)."""
    return 1.0 + completed_steps * (multiplier - 1.0)


def _magnitude(ball: BallSprite) -> float:
    """Return the length of the ball's velocity vector."""
    return math.hypot(ball.speed.x, ball.speed.y)


def _bounce_off_top_wall(ball: BallSprite) -> None:
    """Put the ball just past the top wall and run the real boundary bounce."""
    ball.world_x = WALL_TEST_X
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_y = -float(ball._visible_rect().offset_y) - WALL_OVERSHOOT
    ball._do_bounce()


def _bounce_off_bottom_wall(ball: BallSprite) -> None:
    """Put the ball just past the bottom wall and run the real boundary bounce."""
    ball.world_x = WALL_TEST_X
    visible_rect = ball._visible_rect()
    ball.world_y = (
        float(ball.screen_height - visible_rect.height - visible_rect.offset_y) + WALL_OVERSHOOT
    )
    ball._do_bounce()


class TestBallLinearSpeedUp:
    """Test BallSprite linear speed-up behavior."""

    def test_linear_speed_up_preserves_direction(self):
        """Test that linear speed-up preserves ball direction while adding s0 * k."""
        ball = _ball_with_linear_speed_up(multiplier=1.5)
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)
        initial_magnitude = _magnitude(ball)

        ball.speed_up()

        assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)
        assert _magnitude(ball) == pytest.approx(initial_magnitude * 1.5)

        # Second step adds the same 0.5 * s0 again: 2.0x, not 1.5**2 = 2.25x
        ball.speed_up()

        assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)
        assert _magnitude(ball) == pytest.approx(initial_magnitude * 2.0)

    def test_linear_speed_up_with_bounce(self):
        """Test linear speed-up triggered by real wall bounces."""
        ball = _ball_with_linear_speed_up(
            triggers=SpeedUpTrigger.WALL_BOUNCE,
            multiplier=1.2,
        )
        ball.bounce_left_right = True
        ball.speed = Speed(150.0, -100.0)
        initial_magnitude = _magnitude(ball)

        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 1
        assert _magnitude(ball) == pytest.approx(initial_magnitude * 1.2)
        # Y speed should be positive (downward) after top bounce
        assert ball.speed.y > 0
        assert ball.speed.x == pytest.approx(150.0 * 1.2)
        assert ball.speed.y == pytest.approx(100.0 * 1.2)

        _bounce_off_bottom_wall(ball)

        # Second wall bounce adds another 0.2 * s0: 1.4x total
        assert ball.speed_up_count == 2
        assert _magnitude(ball) == pytest.approx(initial_magnitude * 1.4)
        # Y speed should be negative (upward) after bottom bounce
        assert ball.speed.y < 0

    def test_linear_speed_up_with_paddle_bounce(self):
        """Test linear speed-up behavior with paddle bouncing."""
        ball = _ball_with_linear_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE,
            multiplier=1.3,
        )
        ball.speed = Speed(200.0, 150.0)
        initial_magnitude = _magnitude(ball)

        for expected_factor in (1.3, 1.6, 1.9, 2.2):
            ball.on_paddle_bounce()
            assert _magnitude(ball) == pytest.approx(initial_magnitude * expected_factor)

    def test_linear_speed_up_paddle_bounce_ignored_when_trigger_not_enabled(self):
        """Test paddle bounces, wall bounces, and time do nothing without matching triggers."""
        ball = _ball_with_linear_speed_up(multiplier=1.3)
        ball.speed = Speed(200.0, 150.0)

        ball.on_paddle_bounce()
        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
        ball._advance_continuous_speed_up(100.0)

        assert ball.speed_up_count == 0
        assert ball.speed.x == pytest.approx(200.0)
        assert ball.speed.y == pytest.approx(150.0)

    def test_linear_wall_bounce_does_not_fire_paddle_only_trigger(self):
        """Test a PADDLE_BOUNCE-only ball keeps its speed through a real wall bounce."""
        ball = _ball_with_linear_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE,
            multiplier=1.3,
        )
        ball.speed = Speed(150.0, -100.0)

        _bounce_off_top_wall(ball)

        assert ball.speed_up_count == 0
        assert ball.speed.x == pytest.approx(150.0)
        assert ball.speed.y == pytest.approx(100.0)

    def test_linear_continuous_speed_up(self):
        """Test continuous linear speed-up fires once per interval and keeps direction."""
        ball = _ball_with_linear_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS,
            multiplier=1.1,
            interval=0.1,
        )
        ball.speed = Speed(100.0, 100.0)
        initial_magnitude = _magnitude(ball)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        ball._advance_continuous_speed_up(0.05)  # Too early
        assert ball.speed_up_count == 0
        assert _magnitude(ball) == pytest.approx(initial_magnitude)

        ball._advance_continuous_speed_up(0.05)  # Completes the interval: speed-up
        assert ball.speed_up_count == 1
        assert _magnitude(ball) == pytest.approx(initial_magnitude * 1.1)

        ball._advance_continuous_speed_up(0.05)  # Only half an interval since last speed-up
        assert ball.speed_up_count == 1

        ball._advance_continuous_speed_up(0.05)
        assert ball.speed_up_count == 2
        assert _magnitude(ball) == pytest.approx(initial_magnitude * 1.2)

        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction)

    def test_linear_speed_up_multiple_applications(self):
        """Test that multiple linear speed-ups add up instead of compounding."""
        ball = _ball_with_linear_speed_up(multiplier=1.2)
        ball.speed = Speed(50.0, 50.0)
        initial_magnitude = _magnitude(ball)

        for _ in range(3):
            ball.speed_up()

        final_magnitude = _magnitude(ball)
        assert ball.speed_up_count == 3
        assert final_magnitude == pytest.approx(initial_magnitude * (1.0 + 3 * 0.2))
        # The old (wrong) LINEAR behavior compounded to 1.2**3 = 1.728x
        assert final_magnitude < initial_magnitude * (1.2**3)

    def test_linear_speed_up_with_zero_speed(self):
        """Test linear speed-up behavior with zero initial speed."""
        ball = _ball_with_linear_speed_up(multiplier=1.5)
        ball.speed = Speed(0.0, 0.0)

        for _ in range(5):
            ball.speed_up()

        # Should remain zero
        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)
        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)
        assert ball.speed_up_count == 5

    @pytest.mark.parametrize(
        'angle_degrees', [0, 30, 45, 60, 90, 120, 135, 150, 180, 210, 225, 240, 270, 300, 315, 330]
    )
    def test_linear_speed_up_direction_preservation_accuracy(self, angle_degrees):
        """Test that linear speed-up preserves direction with high precision over many steps."""
        ball = _ball_with_linear_speed_up(multiplier=1.5)
        angle_radians = math.radians(angle_degrees)
        speed_magnitude = 100.0
        ball.speed.x = speed_magnitude * math.cos(angle_radians)
        ball.speed.y = speed_magnitude * math.sin(angle_radians)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        for completed_steps in range(1, PROGRESSION_STEPS + 1):
            ball.speed_up()
            new_direction = math.atan2(ball.speed.y, ball.speed.x)
            assert initial_direction == pytest.approx(new_direction, abs=1e-12), (
                f'Direction not preserved for angle {angle_degrees} degrees'
            )
            assert _magnitude(ball) == pytest.approx(
                speed_magnitude * _linear_curve_value(1.5, completed_steps),
                rel=RELATIVE_TOLERANCE,
            )

    @pytest.mark.parametrize('multiplier', [1.01, 1.1, 1.25, 1.5, 2.0, 3.0])
    @pytest.mark.parametrize(
        ('base_speed_x', 'base_speed_y'), [(250.0, 125.0), (-80.0, 60.0), (3.0, -400.0)]
    )
    def test_linear_progression_matches_closed_form(self, multiplier, base_speed_x, base_speed_y):
        """Test speed after n = 0..20 steps is exactly s0 * (1 + n * k) for each component."""
        ball = _ball_with_linear_speed_up(multiplier=multiplier)
        ball.speed = Speed(base_speed_x, base_speed_y)

        for completed_steps in range(PROGRESSION_STEPS + 1):
            expected_factor = _linear_curve_value(multiplier, completed_steps)
            assert ball.speed_up_count == completed_steps
            assert ball.speed.x == pytest.approx(
                base_speed_x * expected_factor, rel=RELATIVE_TOLERANCE
            )
            assert ball.speed.y == pytest.approx(
                base_speed_y * expected_factor, rel=RELATIVE_TOLERANCE
            )
            ball.speed_up()

    @pytest.mark.parametrize('multiplier', [1.05, 1.2, 2.0])
    def test_linear_increment_is_constant_per_step(self, multiplier):
        """Test every step adds the same absolute speed s0 * k (the defining LINEAR property)."""
        ball = _ball_with_linear_speed_up(multiplier=multiplier)
        ball.speed = Speed(120.0, -160.0)  # Magnitude 200
        base_magnitude = _magnitude(ball)
        expected_increment = base_magnitude * (multiplier - 1.0)

        previous_magnitude = base_magnitude
        for _ in range(PROGRESSION_STEPS):
            ball.speed_up()
            current_magnitude = _magnitude(ball)
            assert current_magnitude - previous_magnitude == pytest.approx(
                expected_increment, rel=1e-9
            )
            previous_magnitude = current_magnitude

    def test_linear_step_ratio_shrinks_toward_one(self):
        """Test the per-step ratio (1 + (n+1)k) / (1 + nk) falls every step but stays > 1."""
        multiplier = 1.5
        growth = multiplier - 1.0
        previous_ratio = math.inf
        for completed_steps in range(PROGRESSION_STEPS + 1):
            ratio = speed_up_step_ratio(SpeedUpCurve.LINEAR, multiplier, completed_steps)
            assert ratio == pytest.approx(
                (1.0 + (completed_steps + 1) * growth) / (1.0 + completed_steps * growth),
                rel=RELATIVE_TOLERANCE,
            )
            assert 1.0 < ratio < previous_ratio
            previous_ratio = ratio

    def test_linear_multiplier_of_one_never_changes_speed(self):
        """Test multiplier=1.0 (k = 0) leaves speed untouched while still counting steps."""
        ball = _ball_with_linear_speed_up(multiplier=1.0)
        ball.speed = Speed(-130.0, 70.0)

        for _ in range(PROGRESSION_STEPS):
            ball.speed_up()

        assert ball.speed.x == pytest.approx(-130.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(70.0, rel=RELATIVE_TOLERANCE)
        assert ball.speed_up_count == PROGRESSION_STEPS

    def test_linear_speed_up_keeps_changes_made_between_steps(self):
        """Test a speed change between steps (e.g. a collision) is scaled, not overwritten."""
        multiplier = 1.25
        ball = _ball_with_linear_speed_up(multiplier=multiplier)
        ball.speed = Speed(100.0, 100.0)
        ball.speed_up()
        ball.speed_up()

        # Something else (a collision) changes the speed between speed-ups
        ball.speed = Speed(-90.0, 40.0)
        ball.speed_up()

        expected_ratio = _linear_curve_value(multiplier, 3) / _linear_curve_value(multiplier, 2)
        assert ball.speed.x == pytest.approx(-90.0 * expected_ratio, rel=RELATIVE_TOLERANCE)
        assert ball.speed.y == pytest.approx(40.0 * expected_ratio, rel=RELATIVE_TOLERANCE)

    def test_linear_reset_restarts_curve(self):
        """Test reset() returns to step 0, so the next step is again the full 1 + k."""
        multiplier = 1.5
        ball = _ball_with_linear_speed_up(multiplier=multiplier)
        for _ in range(4):
            ball.speed_up()
        assert ball.speed_up_count == 4

        ball.reset()
        assert ball.speed_up_count == 0
        speed_after_reset_x = ball.speed.x
        speed_after_reset_y = ball.speed.y

        ball.speed_up()

        # Without the reset this step would have been only 3.5 / 3.0
        assert ball.speed.x == pytest.approx(speed_after_reset_x * multiplier)
        assert ball.speed.y == pytest.approx(speed_after_reset_y * multiplier)

    def test_linear_speed_up_clamped_to_max_speed(self):
        """Test max_speed caps the magnitude (keeping direction) once the line passes it."""
        ball = _ball_with_linear_speed_up(multiplier=1.5, max_speed=400.0)
        ball.speed = Speed(120.0, 160.0)  # Magnitude 200
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        ball.speed_up()  # 300, under the cap
        assert _magnitude(ball) == pytest.approx(300.0)

        ball.speed_up()  # 400, exactly the cap
        assert _magnitude(ball) == pytest.approx(400.0)

        for _ in range(5):
            ball.speed_up()  # Would be 500, 600, ... without the cap
            assert _magnitude(ball) == pytest.approx(400.0)
            assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)

        assert ball.speed_up_count == 7

    def test_linear_x_only_scales_horizontal_component(self):
        """Test X_ONLY grows only speed.x linearly and leaves speed.y alone."""
        ball = _ball_with_linear_speed_up(axes=SpeedUpAxes.X_ONLY, multiplier=1.25)
        ball.speed = Speed(-200.0, 80.0)

        for completed_steps in range(1, PROGRESSION_STEPS + 1):
            ball.speed_up()
            assert ball.speed.x == pytest.approx(
                -200.0 * _linear_curve_value(1.25, completed_steps), rel=RELATIVE_TOLERANCE
            )
            assert ball.speed.y == pytest.approx(80.0, rel=RELATIVE_TOLERANCE)

    def test_linear_y_only_scales_vertical_component(self):
        """Test Y_ONLY grows only speed.y linearly and leaves speed.x alone."""
        ball = _ball_with_linear_speed_up(axes=SpeedUpAxes.Y_ONLY, multiplier=1.25)
        ball.speed = Speed(200.0, -80.0)

        for completed_steps in range(1, PROGRESSION_STEPS + 1):
            ball.speed_up()
            assert ball.speed.x == pytest.approx(200.0, rel=RELATIVE_TOLERANCE)
            assert ball.speed.y == pytest.approx(
                -80.0 * _linear_curve_value(1.25, completed_steps), rel=RELATIVE_TOLERANCE
            )

    def test_linear_x_only_clamped_to_max_speed(self):
        """Test X_ONLY max_speed caps only |speed.x|, keeping its sign."""
        ball = _ball_with_linear_speed_up(
            axes=SpeedUpAxes.X_ONLY,
            multiplier=2.0,
            max_speed=250.0,
        )
        ball.speed = Speed(-100.0, 300.0)

        ball.speed_up()  # -200
        assert ball.speed.x == pytest.approx(-200.0)
        ball.speed_up()  # Would be -300
        assert ball.speed.x == pytest.approx(-250.0)
        # Y is above max_speed but is not a configured axis, so it is not clamped
        assert ball.speed.y == pytest.approx(300.0)
