#!/usr/bin/env python3
"""Test ball speed behavior over many speed-ups driven through dt_tick."""

import itertools
import math

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
)
from glitchygames.movement import Speed
from tests.game_objects.ball_helpers import place_visible_edge_past_wall

# Positions on the 800x600 test screen well away from every wall
SCREEN_CENTER_X = 400.0
SCREEN_CENTER_Y = 300.0

# A binary-exact frame duration so accumulated game time adds up exactly
FRAME_SECONDS = 1 / 64

# Binary-exact interval that is a whole number of frames (4)
SPEED_UP_INTERVAL = 0.0625

# Relative slack for float error when comparing against max_speed
MAX_SPEED_TOLERANCE = 1e-9


# Copied from tests/game_objects/test_ball_speed_up.py
def _curve_value(curve: SpeedUpCurve, multiplier: float, completed_steps: int) -> float:
    """Return the documented growth factor f(n) relative to the base speed."""
    growth = multiplier - 1.0
    if curve is SpeedUpCurve.LINEAR:
        return 1.0 + completed_steps * growth
    if curve is SpeedUpCurve.EXPONENTIAL:
        return multiplier**completed_steps
    return 1.0 + growth * math.log1p(completed_steps)


def _continuous_ball(**settings_fields) -> BallSprite:
    """Create a non-bouncing ball at the screen center that speeds up on a timer.

    Bouncing is disabled, so the ball drifting off screen (and being killed) never
    changes its speed; only the timer does.

    Returns:
        BallSprite: The ball.

    """
    ball = BallSprite(
        bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
        bounce_left_right=False,
        speed_up_settings=SpeedUpSettings(
            triggers=SpeedUpTrigger.CONTINUOUS,
            interval=SPEED_UP_INTERVAL,
            **settings_fields,
        ),
    )
    ball.world_x = SCREEN_CENTER_X
    ball.world_y = SCREEN_CENTER_Y
    return ball


def _tick_through_intervals(ball: BallSprite, interval_count: int) -> None:
    """Run dt_tick with FRAME_SECONDS frames for interval_count intervals of game time."""
    frames_per_interval = round(SPEED_UP_INTERVAL / FRAME_SECONDS)
    for _ in range(interval_count * frames_per_interval):
        ball.dt_tick(FRAME_SECONDS)


class TestBallSpeedBehavior:
    """Test ball speed behavior and speed-up settings."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        self.screen = set_display_mode(size=(800, 600))

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_exponential_speedup_no_runaway_growth(self):
        """max_speed stops exponential growth; uncapped it follows multiplier**n exactly."""
        uncapped_ball = _continuous_ball(curve=SpeedUpCurve.EXPONENTIAL, multiplier=1.1)
        capped_ball = _continuous_ball(
            curve=SpeedUpCurve.EXPONENTIAL, multiplier=1.1, max_speed=1000.0
        )
        initial_magnitude = math.hypot(uncapped_ball.speed.x, uncapped_ball.speed.y)
        capped_ball.speed = Speed(uncapped_ball.speed.x, uncapped_ball.speed.y)
        initial_direction = math.atan2(capped_ball.speed.y, capped_ball.speed.x)

        for step in range(1, 21):
            _tick_through_intervals(uncapped_ball, interval_count=1)
            _tick_through_intervals(capped_ball, interval_count=1)
            capped_magnitude = math.hypot(capped_ball.speed.x, capped_ball.speed.y)
            assert capped_magnitude <= 1000.0 * (1.0 + MAX_SPEED_TOLERANCE), f'step {step}'

        uncapped_magnitude = math.hypot(uncapped_ball.speed.x, uncapped_ball.speed.y)
        assert uncapped_ball.speed_up_count == 20
        assert uncapped_magnitude == pytest.approx(initial_magnitude * 1.1**20)
        assert uncapped_magnitude > 1000.0  # So the cap really was needed
        assert math.hypot(capped_ball.speed.x, capped_ball.speed.y) == pytest.approx(1000.0)
        assert math.atan2(capped_ball.speed.y, capped_ball.speed.x) == pytest.approx(
            initial_direction
        )

    def test_logarithmic_speedup_behavior(self):
        """Logarithmic growth reaches 1 + k*ln(1 + n) with ever smaller steps."""
        ball = _continuous_ball(curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.1)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        initial_magnitude = math.hypot(initial_x, initial_y)

        magnitudes = [initial_magnitude]
        for _ in range(20):
            _tick_through_intervals(ball, interval_count=1)
            magnitudes.append(math.hypot(ball.speed.x, ball.speed.y))

        assert ball.speed_up_count == 20
        assert magnitudes[-1] == pytest.approx(initial_magnitude * (1.0 + 0.1 * math.log(21.0)))
        increments = [later - earlier for earlier, later in itertools.pairwise(magnitudes)]
        assert all(increment > 0.0 for increment in increments)
        assert all(later < earlier for earlier, later in itertools.pairwise(increments))
        # Signs are preserved
        assert (ball.speed.x > 0) == (initial_x > 0)
        assert (ball.speed.y > 0) == (initial_y > 0)

    def test_linear_speedup_behavior(self):
        """Linear growth adds the same amount each step and preserves direction."""
        ball = _continuous_ball(curve=SpeedUpCurve.LINEAR, multiplier=1.1)
        initial_magnitude = math.hypot(ball.speed.x, ball.speed.y)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        magnitudes = [initial_magnitude]
        for _ in range(5):
            _tick_through_intervals(ball, interval_count=1)
            magnitudes.append(math.hypot(ball.speed.x, ball.speed.y))

        increments = [later - earlier for earlier, later in itertools.pairwise(magnitudes)]
        assert increments == pytest.approx([initial_magnitude * 0.1] * 5)
        assert magnitudes[-1] == pytest.approx(initial_magnitude * 1.5)
        assert math.atan2(ball.speed.y, ball.speed.x) == pytest.approx(initial_direction, abs=1e-9)

    def test_continuous_speedup_respects_interval(self):
        """dt_tick speeds up once per elapsed interval, not on every frame."""
        ball = _continuous_ball(curve=SpeedUpCurve.EXPONENTIAL, multiplier=1.1)
        initial_x = ball.speed.x
        half_interval = SPEED_UP_INTERVAL / 2

        expected_counts = [0, 1, 1, 2, 2, 3]  # After each half-interval frame
        for frame, expected_count in enumerate(expected_counts, start=1):
            ball.dt_tick(half_interval)
            assert ball.speed_up_count == expected_count, f'frame {frame}'
            assert ball.speed.x == pytest.approx(initial_x * 1.1**expected_count)

    def test_bounce_speedup_triggers(self):
        """A real top-wall bounce in dt_tick reflects Y and applies one speed-up."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=False,  # Disable left/right to avoid double-bounce
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.EXPONENTIAL,
                multiplier=1.1,
            ),
        )

        # Set controlled initial speed and position to avoid random interactions
        ball.speed = Speed(100.0, -50.0)
        ball.world_x = SCREEN_CENTER_X
        # The visible circle (its collision rect) touches the top wall
        place_visible_edge_past_wall(ball, wall='top', overshoot=0.0)
        # Game time passing must not matter for walls (CONTINUOUS is not a trigger)
        ball._advance_continuous_speed_up(1_000.0)
        assert ball.speed_up_count == 0

        # This should trigger a bounce and speed-up (small dt to avoid large movement)
        ball.dt_tick(0.016)

        assert ball.speed_up_count == 1
        assert (ball.speed.x, ball.speed.y) == pytest.approx((110.0, 55.0))

    def test_speedup_mode_none_no_speedup(self):
        """SpeedUpTrigger.NONE prevents any automatic speed-up, however long it runs."""
        ball = BallSprite(
            bounce_top_bottom=False,  # Disable bouncing to avoid speed changes
            bounce_left_right=False,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.NONE,
                multiplier=1.1,
                interval=SPEED_UP_INTERVAL,
            ),
        )
        ball.world_x = SCREEN_CENTER_X
        ball.world_y = SCREEN_CENTER_Y
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        for _ in range(50):
            ball.dt_tick(1.0)  # 50 seconds of game time, 800 intervals

        assert ball.speed_up_count == 0
        assert ball.speed.x == initial_x
        assert ball.speed.y == initial_y

    def test_speedup_magnitude_bounds(self):
        """With bouncing and frequent speed-ups, speed never exceeds max_speed."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.EXPONENTIAL,
                multiplier=1.1,
                interval=SPEED_UP_INTERVAL,
                max_speed=600.0,
            ),
        )
        ball.world_x = SCREEN_CENTER_X
        ball.world_y = SCREEN_CENTER_Y

        # 100 frames, each one interval long, so every frame is due a speed-up
        for frame in range(1, 101):
            ball.dt_tick(SPEED_UP_INTERVAL)
            magnitude = math.hypot(ball.speed.x, ball.speed.y)
            assert magnitude <= 600.0 * (1.0 + MAX_SPEED_TOLERANCE), f'frame {frame}'

        assert ball.speed_up_count >= 100
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(600.0)

    def test_exponential_vs_logarithmic_comparison(self):
        """After 10 steps each curve gives its documented speed: exp > linear > log.

        Guards against the old behavior where LOGARITHMIC matched LINEAR and LINEAR
        compounded like EXPONENTIAL.
        """
        balls_by_curve = {
            curve: _continuous_ball(curve=curve, multiplier=1.1) for curve in SpeedUpCurve
        }
        for ball in balls_by_curve.values():
            ball.speed = Speed(100.0, 0.0)

        for ball in balls_by_curve.values():
            _tick_through_intervals(ball, interval_count=10)

        final_speeds = {curve: ball.speed.x for curve, ball in balls_by_curve.items()}
        assert final_speeds[SpeedUpCurve.EXPONENTIAL] == pytest.approx(100.0 * 1.1**10)
        assert final_speeds[SpeedUpCurve.LINEAR] == pytest.approx(200.0)
        assert final_speeds[SpeedUpCurve.LOGARITHMIC] == pytest.approx(
            100.0 * (1.0 + 0.1 * math.log(11.0))
        )
        assert (
            final_speeds[SpeedUpCurve.EXPONENTIAL]
            > final_speeds[SpeedUpCurve.LINEAR]
            > final_speeds[SpeedUpCurve.LOGARITHMIC]
        )

    @pytest.mark.parametrize(
        ('axes', 'angle_trend'),
        [
            (SpeedUpAxes.BOTH, 'constant'),
            (SpeedUpAxes.X_ONLY, 'flatter'),
            (SpeedUpAxes.Y_ONLY, 'steeper'),
        ],
    )
    def test_speedup_preserves_direction_components(self, axes, angle_trend):
        """Over many steps BOTH keeps the angle, X_ONLY flattens it, Y_ONLY steepens it."""
        ball = _continuous_ball(curve=SpeedUpCurve.LINEAR, axes=axes, multiplier=1.1)
        ball.speed = Speed(150.0, 100.0)

        angles = [math.atan2(ball.speed.y, ball.speed.x)]
        for _ in range(10):
            _tick_through_intervals(ball, interval_count=1)
            angles.append(math.atan2(ball.speed.y, ball.speed.x))

        consecutive_angles = list(itertools.pairwise(angles))
        if angle_trend == 'constant':
            assert angles == pytest.approx([angles[0]] * len(angles))
        elif angle_trend == 'flatter':
            assert all(later < earlier for earlier, later in consecutive_angles)
            assert math.tan(angles[-1]) == pytest.approx((100.0 / 150.0) / 2.0)
        else:
            assert all(later > earlier for earlier, later in consecutive_angles)
            assert math.tan(angles[-1]) == pytest.approx((100.0 / 150.0) * 2.0)

    @pytest.mark.parametrize('axes', list(SpeedUpAxes))
    def test_speedup_with_negative_speeds(self, axes):
        """Negative components grow in magnitude on the configured axes and keep their sign."""
        ball = _continuous_ball(curve=SpeedUpCurve.LOGARITHMIC, axes=axes, multiplier=1.1)
        ball.speed = Speed(-100.0, -50.0)

        _tick_through_intervals(ball, interval_count=5)

        factor = _curve_value(SpeedUpCurve.LOGARITHMIC, 1.1, 5)
        expected_x = -100.0 * factor if axes is not SpeedUpAxes.Y_ONLY else -100.0
        expected_y = -50.0 * factor if axes is not SpeedUpAxes.X_ONLY else -50.0
        assert (ball.speed.x, ball.speed.y) == pytest.approx((expected_x, expected_y))
        assert ball.speed.x < 0, 'X speed should remain negative'
        assert ball.speed.y < 0, 'Y speed should remain negative'
