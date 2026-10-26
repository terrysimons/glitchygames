#!/usr/bin/env python3
"""Test each ball speed-up trigger end to end, and how the trigger flags combine."""

import dataclasses
import math

import pytest

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSchedule,
    SpeedUpSettings,
    SpeedUpTrigger,
)
from glitchygames.movement import Speed

ALL_TRIGGERS = SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.WALL_BOUNCE

# Positions on the 800x600 test screen well away from every wall
SCREEN_CENTER_X = 400.0
SCREEN_CENTER_Y = 300.0

# A binary-exact frame duration so accumulated game time adds up exactly; a few
# intervals' worth of frames cannot carry the ball from the screen center to a wall
FRAME_SECONDS = 1 / 64

# Binary-exact intervals that are whole numbers of frames
SHORT_INTERVAL = 0.125
LONG_INTERVAL = 0.25


# Copied from tests/game_objects/test_ball_speed_up.py
def _curve_value(curve: SpeedUpCurve, multiplier: float, completed_steps: int) -> float:
    """Return the documented growth factor f(n) relative to the base speed."""
    growth = multiplier - 1.0
    if curve is SpeedUpCurve.LINEAR:
        return 1.0 + completed_steps * growth
    if curve is SpeedUpCurve.EXPONENTIAL:
        return multiplier**completed_steps
    return 1.0 + growth * math.log1p(completed_steps)


def _centered_ball(**ball_arguments) -> BallSprite:
    """Create a ball at the screen center with a fixed speed of (200, 100).

    Returns:
        BallSprite: The ball.

    """
    ball = BallSprite(**ball_arguments)
    ball.world_x = SCREEN_CENTER_X
    ball.world_y = SCREEN_CENTER_Y
    ball.speed = Speed(200.0, 100.0)
    return ball


def _tick_frames(ball: BallSprite, game_seconds: float) -> None:
    """Run dt_tick with FRAME_SECONDS frames until game_seconds of game time has passed."""
    for _ in range(round(game_seconds / FRAME_SECONDS)):
        ball.dt_tick(FRAME_SECONDS)


def _hit_top_wall(ball: BallSprite) -> None:
    """Place the ball on the top wall, moving into it, away from the corners, and bounce."""
    ball.world_x = SCREEN_CENTER_X
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_y = -float(ball._visible_rect().offset_y)
    ball.speed.y = -abs(ball.speed.y)  # a wall only bounces a ball moving into it
    ball._do_bounce()


def _hit_left_wall(ball: BallSprite) -> None:
    """Place the ball on the left wall, moving into it, away from the corners, and bounce."""
    # The ball's visible circle is inset in its image; walls meet the circle (the collision rect)
    ball.world_x = -float(ball._visible_rect().offset_x)
    ball.world_y = SCREEN_CENTER_Y
    ball.speed.x = -abs(ball.speed.x)  # a wall only bounces a ball moving into it
    ball._do_bounce()


class TestSpeedUpTriggersEndToEnd:
    """Each trigger fires through the ball's real event paths, and only when enabled."""

    def test_no_triggers_still_allows_manual_speed_up(self):
        """With no triggers, events do nothing but an explicit speed_up() still works."""
        ball = _centered_ball(bounce_left_right=True)
        ball.speed = Speed(200.0, -100.0)  # Moving up toward the top wall

        ball.on_paddle_bounce()
        _hit_top_wall(ball)
        ball._advance_continuous_speed_up(1_000.0)
        assert ball.speed_up_count == 0
        assert (ball.speed.x, ball.speed.y) == pytest.approx((200.0, 100.0))  # Only reflected

        ball.speed_up()  # Default settings: EXPONENTIAL x1.1 on BOTH axes

        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((220.0, 110.0))

    def test_continuous_logarithmic_via_dt_tick(self):
        """dt_tick applies one logarithmic step each time an interval elapses."""
        ball = _centered_ball(
            bounce_top_bottom=False,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.CONTINUOUS,
                curve=SpeedUpCurve.LOGARITHMIC,
                multiplier=1.05,
                interval=SHORT_INTERVAL,
            ),
        )

        for completed_steps in range(1, 6):
            # Every frame but the last of the interval leaves the step pending
            _tick_frames(ball, SHORT_INTERVAL - FRAME_SECONDS)
            assert ball.speed_up_count == completed_steps - 1
            ball.dt_tick(FRAME_SECONDS)
            factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.05, completed_steps)
            assert ball.speed_up_count == completed_steps
            assert ball.speed.x == pytest.approx(200.0 * factor)
            assert ball.speed.y == pytest.approx(100.0 * factor)

    def test_wall_bounce_trigger_via_top_and_left_walls(self):
        """WALL_BOUNCE speeds up on real top and left bounces, but not on a paddle hit."""
        ball = _centered_ball(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.LOGARITHMIC,
                multiplier=1.1,
            ),
        )
        ball.speed = Speed(-200.0, -100.0)

        _hit_top_wall(ball)
        first_factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.1, 1)
        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((
            -200.0 * first_factor,
            100.0 * first_factor,
        ))

        _hit_left_wall(ball)
        second_factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.1, 2)
        assert ball.speed_up_count == 2
        assert (ball.speed.x, ball.speed.y) == pytest.approx((
            200.0 * second_factor,
            100.0 * second_factor,
        ))

        ball.on_paddle_bounce()
        assert ball.speed_up_count == 2

    def test_paddle_bounce_trigger_only(self):
        """PADDLE_BOUNCE speeds up on a paddle hit, but not on walls or elapsed time."""
        ball = _centered_ball(
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.PADDLE_BOUNCE,
                curve=SpeedUpCurve.LOGARITHMIC,
                multiplier=1.15,
            ),
        )
        ball.speed = Speed(200.0, -100.0)  # Moving up toward the top wall

        ball.on_paddle_bounce()
        factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.15, 1)
        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((200.0 * factor, -100.0 * factor))

        _hit_top_wall(ball)
        ball._advance_continuous_speed_up(1_000.0)
        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((200.0 * factor, 100.0 * factor))

    def test_continuous_and_wall_bounce_combined(self):
        """A timed step and a wall step share one logarithmic curve: f(2) after both."""
        ball = _centered_ball(
            bounce_top_bottom=True,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.LOGARITHMIC,
                multiplier=1.02,
                interval=LONG_INTERVAL,
            ),
        )

        _tick_frames(ball, LONG_INTERVAL)
        assert ball.speed_up_count == 1
        assert ball.speed.x == pytest.approx(
            200.0 * _curve_value(SpeedUpCurve.LOGARITHMIC, 1.02, 1)
        )

        _hit_top_wall(ball)

        factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.02, 2)
        assert ball.speed_up_count == 2
        assert (ball.speed.x, ball.speed.y) == pytest.approx((200.0 * factor, 100.0 * factor))

    def test_all_triggers_combined(self):
        """Continuous, paddle, and wall steps together reach f(3) on one curve."""
        ball = _centered_ball(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(
                triggers=ALL_TRIGGERS,
                curve=SpeedUpCurve.LOGARITHMIC,
                multiplier=1.01,
                interval=SHORT_INTERVAL,
            ),
        )
        ball.speed = Speed(200.0, -100.0)

        _tick_frames(ball, SHORT_INTERVAL)
        assert ball.speed_up_count == 1
        ball.on_paddle_bounce()
        _hit_top_wall(ball)

        factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.01, 3)
        assert ball.speed_up_count == 3
        assert (ball.speed.x, ball.speed.y) == pytest.approx((200.0 * factor, 100.0 * factor))


class TestSpeedUpTriggerFlags:
    """SpeedUpTrigger flags combine with | and SpeedUpSettings holds one configuration.

    Replaces the old log-only dump of SpeedUpMode flag values and legacy aliases.
    """

    def test_none_contains_no_triggers(self):
        """NONE is empty: no individual trigger is a member of it."""
        for trigger in (
            SpeedUpTrigger.CONTINUOUS,
            SpeedUpTrigger.PADDLE_BOUNCE,
            SpeedUpTrigger.WALL_BOUNCE,
        ):
            assert trigger not in SpeedUpTrigger.NONE
        assert not SpeedUpTrigger.NONE

    def test_triggers_are_distinct_bits(self):
        """Each trigger is its own flag, so combining them never loses one."""
        assert ALL_TRIGGERS.value == (
            SpeedUpTrigger.CONTINUOUS.value
            | SpeedUpTrigger.PADDLE_BOUNCE.value
            | SpeedUpTrigger.WALL_BOUNCE.value
        )
        assert len({trigger.value for trigger in SpeedUpTrigger if trigger.value}) == 3

    def test_combined_membership(self):
        """A combined value contains exactly the triggers that were OR-ed in."""
        bounce_triggers = SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.WALL_BOUNCE
        assert SpeedUpTrigger.PADDLE_BOUNCE in bounce_triggers
        assert SpeedUpTrigger.WALL_BOUNCE in bounce_triggers
        assert SpeedUpTrigger.CONTINUOUS not in bounce_triggers

    def test_removing_a_trigger_with_and_not(self):
        """ALL & ~CONTINUOUS leaves just the bounce triggers."""
        all_except_continuous = ALL_TRIGGERS & ~SpeedUpTrigger.CONTINUOUS
        assert all_except_continuous == SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.WALL_BOUNCE

    def test_default_settings(self):
        """Default settings never speed up automatically and use a 10% exponential step."""
        settings = SpeedUpSettings()
        assert settings.triggers == SpeedUpTrigger.NONE
        assert settings.curve is SpeedUpCurve.EXPONENTIAL
        assert settings.axes is SpeedUpAxes.BOTH
        assert settings.multiplier == pytest.approx(1.1)
        assert settings.interval == pytest.approx(1.0)
        assert settings.schedule is SpeedUpSchedule.FIXED_RATE
        assert settings.max_speed is None

    def test_settings_are_frozen(self):
        """Settings cannot be mutated in place; use dataclasses.replace for a variant."""
        settings = SpeedUpSettings(triggers=SpeedUpTrigger.PADDLE_BOUNCE)
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.multiplier = 2.0  # type: ignore[misc]

        variant = dataclasses.replace(settings, triggers=ALL_TRIGGERS)
        assert variant.triggers == ALL_TRIGGERS
        assert settings.triggers == SpeedUpTrigger.PADDLE_BOUNCE
