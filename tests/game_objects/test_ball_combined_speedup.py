#!/usr/bin/env python3
"""Test combining speed-up triggers, curves, and axes for BallSprite.

Every trigger enabled on a ball advances the same step counter on the ball's single
curve, so the speed after N speed-ups is base * f(N) no matter which mix of events
caused them.
"""

import itertools
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

ALL_TRIGGERS = SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.WALL_BOUNCE
BOUNCE_TRIGGERS = SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.WALL_BOUNCE

# Binary-exact interval so accumulated game time never rounds below the interval
CONTINUOUS_INTERVAL = 0.25

# Horizontal center of the 800x600 test screen, far from the side walls
SCREEN_CENTER_X = 400.0
SCREEN_CENTER_Y = 300.0


# Copied from tests/game_objects/test_ball_speed_up.py
def _ball_with_speed_up(**settings_fields) -> BallSprite:
    """Create a ball with the given SpeedUpSettings fields (defaults otherwise).

    Returns:
        BallSprite: The ball.

    """
    return BallSprite(speed_up_settings=SpeedUpSettings(**settings_fields))


# Copied from tests/game_objects/test_ball_speed_up.py
def _curve_value(curve: SpeedUpCurve, multiplier: float, completed_steps: int) -> float:
    """Return the documented growth factor f(n) relative to the base speed."""
    growth = multiplier - 1.0
    if curve is SpeedUpCurve.LINEAR:
        return 1.0 + completed_steps * growth
    if curve is SpeedUpCurve.EXPONENTIAL:
        return multiplier**completed_steps
    return 1.0 + growth * math.log1p(completed_steps)


def _fire_continuous_speed_up(ball: BallSprite) -> None:
    """Advance the continuous timer by exactly one interval of game time."""
    ball._advance_continuous_speed_up(ball.speed_up_settings.interval)


def _hit_top_wall(ball: BallSprite) -> None:
    """Place the ball on the top wall away from the corners and run the bounce check."""
    ball.world_x = SCREEN_CENTER_X
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_y = -float(ball._visible_rect().offset_y)
    ball._do_bounce()


def _hit_left_wall(ball: BallSprite) -> None:
    """Place the ball on the left wall away from the corners and run the bounce check."""
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_x = -float(ball._visible_rect().offset_x)
    ball.world_y = SCREEN_CENTER_Y
    ball._do_bounce()


class TestBallCombinedSpeedUp:
    """Test BallSprite with several speed-up triggers enabled at once."""

    def test_continuous_and_paddle_triggers_share_one_curve(self):
        """A continuous step then a paddle step land on f(2) with the angle preserved."""
        ball = _ball_with_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.PADDLE_BOUNCE,
            curve=SpeedUpCurve.LOGARITHMIC,
            multiplier=1.2,
            interval=CONTINUOUS_INTERVAL,
        )
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        _fire_continuous_speed_up(ball)
        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(100.0 * _curve_value(SpeedUpCurve.LOGARITHMIC, 1.2, 1))

        ball.on_paddle_bounce()

        expected_factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.2, 2)
        assert ball.speed_up_count == 2
        assert ball.speed.x == pytest.approx(100.0 * expected_factor)
        assert ball.speed.y == pytest.approx(200.0 * expected_factor)
        assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction)

    def test_continuous_and_paddle_triggers_y_only(self):
        """With Y_ONLY, mixed continuous and paddle steps scale only vertical speed."""
        ball = _ball_with_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.PADDLE_BOUNCE,
            curve=SpeedUpCurve.LINEAR,
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.15,
            interval=CONTINUOUS_INTERVAL,
        )
        ball.speed = Speed(150.0, 100.0)

        _fire_continuous_speed_up(ball)
        ball.on_paddle_bounce()

        assert ball.speed.x == pytest.approx(150.0)
        assert ball.speed.y == pytest.approx(100.0 * _curve_value(SpeedUpCurve.LINEAR, 1.15, 2))

    def test_paddle_and_wall_triggers_share_one_curve(self):
        """A paddle step then a real top-wall bounce land on f(2); the wall flips Y."""
        ball = _ball_with_speed_up(
            triggers=BOUNCE_TRIGGERS,
            curve=SpeedUpCurve.LOGARITHMIC,
            multiplier=1.25,
        )
        ball.speed = Speed(200.0, -150.0)

        ball.on_paddle_bounce()
        first_factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.25, 1)
        assert ball.speed.x == pytest.approx(200.0 * first_factor)
        assert ball.speed.y == pytest.approx(-150.0 * first_factor)

        _hit_top_wall(ball)

        second_factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.25, 2)
        assert ball.speed_up_count == 2
        assert ball.speed.x == pytest.approx(200.0 * second_factor)
        assert ball.speed.y == pytest.approx(150.0 * second_factor)  # Reflected downward

    def test_all_triggers_linear(self):
        """All three triggers with LINEAR add the same absolute amount each time."""
        ball = _ball_with_speed_up(
            triggers=ALL_TRIGGERS,
            curve=SpeedUpCurve.LINEAR,
            multiplier=1.1,
            interval=CONTINUOUS_INTERVAL,
        )
        ball.speed = Speed(100.0, -200.0)
        initial_magnitude = math.hypot(ball.speed.x, ball.speed.y)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        magnitudes = [initial_magnitude]
        _fire_continuous_speed_up(ball)
        magnitudes.append(math.hypot(ball.speed.x, ball.speed.y))
        ball.on_paddle_bounce()
        magnitudes.append(math.hypot(ball.speed.x, ball.speed.y))
        _hit_top_wall(ball)
        magnitudes.append(math.hypot(ball.speed.x, ball.speed.y))

        assert ball.speed_up_count == 3
        increments = [later - earlier for earlier, later in itertools.pairwise(magnitudes)]
        assert increments == pytest.approx([initial_magnitude * 0.1] * 3)
        assert magnitudes[-1] == pytest.approx(initial_magnitude * 1.3)
        # The top wall reflected Y, so the heading is mirrored but otherwise unchanged
        assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(-initial_direction)

    def test_all_triggers_x_only(self):
        """All triggers with X_ONLY grow horizontal speed on the curve; Y never changes."""
        ball = _ball_with_speed_up(
            triggers=ALL_TRIGGERS,
            curve=SpeedUpCurve.LOGARITHMIC,
            axes=SpeedUpAxes.X_ONLY,
            multiplier=1.2,
            interval=CONTINUOUS_INTERVAL,
        )
        ball.speed = Speed(100.0, 200.0)

        _fire_continuous_speed_up(ball)
        assert ball.speed.x == pytest.approx(100.0 * _curve_value(SpeedUpCurve.LOGARITHMIC, 1.2, 1))
        assert ball.speed.y == pytest.approx(200.0)

        ball.on_paddle_bounce()
        assert ball.speed.x == pytest.approx(100.0 * _curve_value(SpeedUpCurve.LOGARITHMIC, 1.2, 2))
        assert ball.speed.y == pytest.approx(200.0)

    def test_all_triggers_y_only(self):
        """All triggers with Y_ONLY grow vertical speed on the curve; X never changes."""
        ball = _ball_with_speed_up(
            triggers=ALL_TRIGGERS,
            curve=SpeedUpCurve.LOGARITHMIC,
            axes=SpeedUpAxes.Y_ONLY,
            multiplier=1.3,
            interval=CONTINUOUS_INTERVAL,
        )
        ball.speed = Speed(100.0, -200.0)

        _fire_continuous_speed_up(ball)
        assert ball.speed.x == pytest.approx(100.0)
        assert ball.speed.y == pytest.approx(
            -200.0 * _curve_value(SpeedUpCurve.LOGARITHMIC, 1.3, 1)
        )

        _hit_top_wall(ball)
        assert ball.speed.x == pytest.approx(100.0)
        assert ball.speed.y == pytest.approx(200.0 * _curve_value(SpeedUpCurve.LOGARITHMIC, 1.3, 2))

    def test_trigger_order_does_not_change_the_curve(self):
        """Paddle-then-wall and wall-then-paddle reach the same speed (one shared curve).

        Replaces the old per-trigger curve test (linear paddle + logarithmic wall): a
        ball now has one curve, so the second step uses step 1 of it whichever event
        came first.
        """
        speeds_by_order = []
        for paddle_first in (True, False):
            ball = _ball_with_speed_up(
                triggers=BOUNCE_TRIGGERS,
                curve=SpeedUpCurve.LOGARITHMIC,
                multiplier=1.15,
            )
            ball.speed = Speed(150.0, 100.0)
            if paddle_first:
                ball.on_paddle_bounce()
                ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
            else:
                ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
                ball.on_paddle_bounce()
            speeds_by_order.append((ball.speed.x, ball.speed.y))

        expected_factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.15, 2)
        assert speeds_by_order[0] == pytest.approx(speeds_by_order[1])
        assert speeds_by_order[0] == pytest.approx((
            150.0 * expected_factor,
            100.0 * expected_factor,
        ))

    def test_second_trigger_uses_next_step_not_first_step(self):
        """A wall bounce after a paddle bounce applies the step-1 ratio, not step 0 again."""
        ball = _ball_with_speed_up(
            triggers=BOUNCE_TRIGGERS,
            curve=SpeedUpCurve.LOGARITHMIC,
            multiplier=1.15,
        )
        ball.speed = Speed(150.0, 100.0)
        ball.on_paddle_bounce()
        speed_after_paddle = ball.speed.x

        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)

        step_one_ratio = speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, 1.15, 1)
        step_zero_ratio = speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, 1.15, 0)
        assert ball.speed.x == pytest.approx(speed_after_paddle * step_one_ratio)
        assert step_one_ratio < step_zero_ratio

    def test_each_event_applies_exactly_one_step(self):
        """With every trigger enabled, one event still applies one step, never several.

        Replaces the old priority test (two continuous flags competing): each event
        now advances the shared curve by exactly one step.
        """
        ball = _ball_with_speed_up(
            triggers=ALL_TRIGGERS,
            curve=SpeedUpCurve.EXPONENTIAL,
            multiplier=1.1,
            interval=CONTINUOUS_INTERVAL,
        )
        ball.speed = Speed(100.0, 200.0)

        _fire_continuous_speed_up(ball)
        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((110.0, 220.0))

        ball.on_paddle_bounce()
        assert ball.speed_up_count == 2
        assert (ball.speed.x, ball.speed.y) == pytest.approx((121.0, 242.0))

    def test_combined_triggers_with_real_wall_bouncing(self):
        """A paddle hit and a real left-wall bounce both speed up; the wall flips X."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(
                triggers=BOUNCE_TRIGGERS,
                curve=SpeedUpCurve.EXPONENTIAL,
                multiplier=1.2,
            ),
        )
        ball.speed = Speed(-100.0, 150.0)

        ball.on_paddle_bounce()
        assert (ball.speed.x, ball.speed.y) == pytest.approx((-120.0, 180.0))

        _hit_left_wall(ball)

        assert ball.speed_up_count == 2
        assert (ball.speed.x, ball.speed.y) == pytest.approx((144.0, 216.0))  # X reflected

    def test_wall_trigger_ignored_when_wall_bounce_disabled(self):
        """A real wall bounce reflects but does not speed up if only PADDLE_BOUNCE is on."""
        ball = _ball_with_speed_up(triggers=SpeedUpTrigger.PADDLE_BOUNCE, multiplier=1.2)
        ball.speed = Speed(100.0, -150.0)

        _hit_top_wall(ball)

        assert ball.speed_up_count == 0
        assert (ball.speed.x, ball.speed.y) == pytest.approx((100.0, 150.0))

    def test_zero_speed_components_stay_zero(self):
        """Combined triggers scale zero components to zero (no invented motion)."""
        ball = _ball_with_speed_up(
            triggers=BOUNCE_TRIGGERS,
            curve=SpeedUpCurve.EXPONENTIAL,
            multiplier=1.5,
        )

        ball.speed = Speed(0.0, 100.0)
        ball.on_paddle_bounce()
        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)
        assert ball.speed.y == pytest.approx(150.0)

        ball.speed = Speed(100.0, 0.0)
        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
        assert ball.speed.x == pytest.approx(150.0)
        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)

    def test_reset_after_mixed_triggers_restarts_the_curve(self):
        """After reset() the next speed-up uses the step-0 ratio again, whatever came before."""
        ball = _ball_with_speed_up(
            triggers=ALL_TRIGGERS,
            curve=SpeedUpCurve.LOGARITHMIC,
            multiplier=1.15,
            interval=CONTINUOUS_INTERVAL,
        )
        _fire_continuous_speed_up(ball)
        ball.on_paddle_bounce()
        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
        assert ball.speed_up_count == 3

        ball.reset()
        assert ball.speed_up_count == 0
        speed_after_reset = (ball.speed.x, ball.speed.y)

        ball.on_paddle_bounce()

        step_zero_ratio = speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, 1.15, 0)
        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((
            speed_after_reset[0] * step_zero_ratio,
            speed_after_reset[1] * step_zero_ratio,
        ))
