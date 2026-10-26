#!/usr/bin/env python3
"""Test coverage for BallSprite speed_up method."""

import itertools
import math

import pytest

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSchedule,
    SpeedUpSettings,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from glitchygames.movement import Speed

# Constants for magic values
MULTIPLIER_1_15 = 1.15
MULTIPLIER_1_1 = 1.1
TOLERANCE_1E_10 = 1e-10


def _ball_with_speed_up(**settings_fields) -> BallSprite:
    """Create a ball with the given SpeedUpSettings fields (defaults otherwise).

    Returns:
        BallSprite: The ball.

    """
    return BallSprite(speed_up_settings=SpeedUpSettings(**settings_fields))


def _curve_value(curve: SpeedUpCurve, multiplier: float, completed_steps: int) -> float:
    """Return the documented growth factor f(n) relative to the base speed."""
    growth = multiplier - 1.0
    if curve is SpeedUpCurve.LINEAR:
        return 1.0 + completed_steps * growth
    if curve is SpeedUpCurve.EXPONENTIAL:
        return multiplier**completed_steps
    return 1.0 + growth * math.log1p(completed_steps)


class TestBallSpriteSpeedUp:
    """Test BallSprite.speed_up with the EXPONENTIAL curve (constant percentage steps)."""

    def test_speed_up_applies_correct_multiplier(self):
        """Test that speed_up applies the exact multiplier configured."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.EXPONENTIAL, multiplier=MULTIPLIER_1_15)
        initial_speed_x = ball.speed.x
        initial_speed_y = ball.speed.y
        initial_magnitude = math.hypot(initial_speed_x, initial_speed_y)

        ball.speed_up()

        assert abs(ball.speed.x - initial_speed_x * MULTIPLIER_1_15) < TOLERANCE_1E_10
        assert abs(ball.speed.y - initial_speed_y * MULTIPLIER_1_15) < TOLERANCE_1E_10
        final_magnitude = math.hypot(ball.speed.x, ball.speed.y)
        assert abs(final_magnitude - initial_magnitude * MULTIPLIER_1_15) < TOLERANCE_1E_10

    def test_speed_up_preserves_direction(self):
        """Test that speed_up preserves the direction of movement."""
        ball = _ball_with_speed_up(multiplier=MULTIPLIER_1_15)
        ball.speed = Speed(100.0, 50.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        ball.speed_up()

        assert abs(math.atan2(ball.speed.y, ball.speed.x) - initial_direction) < TOLERANCE_1E_10

    def test_multiple_speed_up_calls(self):
        """Test that repeated exponential speed-ups compound: 100 * 1.1**5."""
        ball = _ball_with_speed_up(multiplier=MULTIPLIER_1_1)
        ball.speed = Speed(100.0, 100.0)

        for _ in range(5):
            ball.speed_up()

        expected_speed = 100.0 * (MULTIPLIER_1_1**5)
        assert abs(ball.speed.x - expected_speed) < TOLERANCE_1E_10
        assert abs(ball.speed.y - expected_speed) < TOLERANCE_1E_10

    @pytest.mark.parametrize('multiplier', [1.0, 1.05, 1.1, 1.15, 1.2, 1.5, 2.0])
    def test_speed_up_with_different_multipliers(self, multiplier):
        """Test speed_up with various multiplier values, including 1.0 (no change)."""
        ball = _ball_with_speed_up(multiplier=multiplier)
        ball.speed = Speed(50.0, 75.0)

        ball.speed_up()

        assert abs(ball.speed.x - 50.0 * multiplier) < TOLERANCE_1E_10
        assert abs(ball.speed.y - 75.0 * multiplier) < TOLERANCE_1E_10

    @pytest.mark.parametrize(
        ('speed_x', 'speed_y'), [(-100.0, -50.0), (100.0, -50.0), (-100.0, 50.0)]
    )
    def test_speed_up_keeps_component_signs(self, speed_x, speed_y):
        """Test speed_up scales negative and mixed-sign components correctly."""
        ball = _ball_with_speed_up(multiplier=1.2)
        ball.speed = Speed(speed_x, speed_y)

        ball.speed_up()

        assert abs(ball.speed.x - speed_x * 1.2) < TOLERANCE_1E_10
        assert abs(ball.speed.y - speed_y * 1.2) < TOLERANCE_1E_10

    def test_speed_up_no_precision_loss(self):
        """Test that speed_up doesn't introduce asymmetric precision errors over many calls."""
        ball = _ball_with_speed_up(multiplier=1.01)
        ball.speed = Speed(1.0, 1.0)

        for _ in range(100):
            ball.speed_up()

        assert abs(ball.speed.x - ball.speed.y) < TOLERANCE_1E_10
        assert abs(ball.speed.x - 1.01**100) < 1e-9


class TestSpeedUpStepRatio:
    """speed_up_step_ratio reproduces each documented growth curve exactly."""

    @pytest.mark.parametrize('curve', list(SpeedUpCurve))
    @pytest.mark.parametrize('multiplier', [1.0, 1.01, 1.15, 2.0])
    def test_cumulative_ratios_follow_curve(self, curve, multiplier):
        """Multiplying the step ratios for n steps gives exactly f(n) for n = 0..50."""
        cumulative_factor = 1.0
        for completed_steps in range(51):
            assert cumulative_factor == pytest.approx(
                _curve_value(curve, multiplier, completed_steps), rel=1e-12
            ), f'{curve.name} x{multiplier} after {completed_steps} steps'
            cumulative_factor *= speed_up_step_ratio(curve, multiplier, completed_steps)

    @pytest.mark.parametrize(
        ('curve', 'expected_speeds'),
        [
            # Speed after n speed-ups from 250 px/s with multiplier 1.15, n = 0, 1, 3, 5, 10, 20
            (SpeedUpCurve.LINEAR, (250.0, 287.5, 362.5, 437.5, 625.0, 1000.0)),
            (SpeedUpCurve.EXPONENTIAL, (250.0, 287.5, 380.2, 502.8, 1011.4, 4091.6)),
            (SpeedUpCurve.LOGARITHMIC, (250.0, 276.0, 302.0, 317.2, 339.9, 364.2)),
        ],
    )
    def test_reference_speeds(self, curve, expected_speeds):
        """Spot-check the curves against hand-computed reference values."""
        for completed_steps, expected_speed in zip(
            (0, 1, 3, 5, 10, 20), expected_speeds, strict=True
        ):
            actual_speed = 250.0 * _curve_value(curve, 1.15, completed_steps)
            cumulative_factor = 1.0
            for step in range(completed_steps):
                cumulative_factor *= speed_up_step_ratio(curve, 1.15, step)
            assert 250.0 * cumulative_factor == pytest.approx(actual_speed, rel=1e-12)
            assert 250.0 * cumulative_factor == pytest.approx(expected_speed, abs=0.05)

    def test_logarithmic_steps_shrink(self):
        """Each logarithmic step is smaller than the one before (the curve tapers)."""
        ratios = [speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, 1.15, step) for step in range(20)]
        assert all(later < earlier for earlier, later in itertools.pairwise(ratios))
        assert all(ratio > 1.0 for ratio in ratios)

    def test_linear_steps_add_constant_amount(self):
        """Each linear step adds the same absolute speed: (multiplier - 1) * base."""
        ball_speed = 200.0
        increments = []
        for step in range(10):
            new_speed = ball_speed * speed_up_step_ratio(SpeedUpCurve.LINEAR, 1.25, step)
            increments.append(new_speed - ball_speed)
            ball_speed = new_speed
        assert increments == pytest.approx([50.0] * 10, rel=1e-12)


class TestSpeedUpSettingsValidation:
    """SpeedUpSettings rejects values that would stop, reverse, or break the ball."""

    @pytest.mark.parametrize('multiplier', [0.99, 0.5, 0.0, -1.0, math.nan, math.inf])
    def test_rejects_invalid_multiplier(self, multiplier):
        """A speed-up multiplier must be a finite number >= 1.0."""
        with pytest.raises(ValueError, match='multiplier'):
            SpeedUpSettings(multiplier=multiplier)

    @pytest.mark.parametrize('interval', [0.0, -1.0, math.nan])
    def test_rejects_invalid_interval(self, interval):
        """The continuous interval must be a positive number of seconds."""
        with pytest.raises(ValueError, match='interval'):
            SpeedUpSettings(interval=interval)

    @pytest.mark.parametrize('max_speed', [0.0, -10.0, math.nan])
    def test_rejects_invalid_max_speed(self, max_speed):
        """max_speed must be None (uncapped) or a positive number."""
        with pytest.raises(ValueError, match='max_speed'):
            SpeedUpSettings(max_speed=max_speed)

    def test_accepts_boundaries(self):
        """Boundary values are valid: multiplier 1.0, a tiny interval, and no max_speed."""
        settings = SpeedUpSettings(multiplier=1.0, interval=1e-9, max_speed=None)
        assert settings.multiplier == 1.0


class TestBallSpeedUpBehavior:
    """Axes, caps, triggers, and the step counter on a real ball."""

    def test_default_settings_never_trigger(self):
        """With default settings no bounce or timer speeds the ball up."""
        ball = BallSprite()
        ball.speed = Speed(100.0, 50.0)
        ball.on_paddle_bounce()
        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
        ball._advance_continuous_speed_up(1_000.0)
        assert (ball.speed.x, ball.speed.y) == (100.0, 50.0)
        assert ball.speed_up_count == 0

    @pytest.mark.parametrize(
        ('axes', 'expected_speed'),
        [
            (SpeedUpAxes.BOTH, (120.0, -60.0)),
            (SpeedUpAxes.X_ONLY, (120.0, -50.0)),
            (SpeedUpAxes.Y_ONLY, (100.0, -60.0)),
        ],
    )
    def test_axes(self, axes, expected_speed):
        """Only the configured components change, keeping their signs."""
        ball = _ball_with_speed_up(axes=axes, multiplier=1.2)
        ball.speed = Speed(100.0, -50.0)
        ball.speed_up()
        assert (ball.speed.x, ball.speed.y) == pytest.approx(expected_speed)

    def test_single_axis_with_zero_component_stays_zero(self):
        """X_ONLY on a purely vertical ball cannot invent horizontal motion."""
        ball = _ball_with_speed_up(axes=SpeedUpAxes.X_ONLY, multiplier=1.5)
        ball.speed = Speed(0.0, 80.0)
        ball.speed_up()
        assert (ball.speed.x, ball.speed.y) == (0.0, 80.0)

    @pytest.mark.parametrize(
        ('axes', 'initial_speed', 'expected_speed'),
        [
            (SpeedUpAxes.BOTH, (300.0, 400.0), (240.0, 320.0)),  # magnitude 500 -> 400
            (SpeedUpAxes.X_ONLY, (-500.0, 30.0), (-400.0, 30.0)),
            (SpeedUpAxes.Y_ONLY, (30.0, -500.0), (30.0, -400.0)),
        ],
    )
    def test_max_speed_caps_configured_axes(self, axes, initial_speed, expected_speed):
        """A speed-up never leaves the configured speed above max_speed."""
        ball = _ball_with_speed_up(axes=axes, multiplier=1.5, max_speed=400.0)
        ball.speed = Speed(*initial_speed)
        ball.speed_up()
        assert (ball.speed.x, ball.speed.y) == pytest.approx(expected_speed)

    def test_speed_exactly_at_cap_is_unchanged(self):
        """A ball already exactly at max_speed stays there."""
        ball = _ball_with_speed_up(multiplier=1.5, max_speed=500.0)
        ball.speed = Speed(300.0, 400.0)
        ball.speed_up()
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(500.0)

    def test_speed_up_scales_current_speed_after_external_change(self):
        """Collisions that change speed between steps are kept, not snapped back to a curve."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.15)
        ball.speed = Speed(200.0, 0.0)
        ball.speed_up()
        ball.speed = Speed(-50.0, 30.0)  # e.g. an elastic collision with another ball
        ball.speed_up()
        second_step_ratio = speed_up_step_ratio(SpeedUpCurve.LOGARITHMIC, 1.15, 1)
        assert (ball.speed.x, ball.speed.y) == pytest.approx((
            -50.0 * second_step_ratio,
            30.0 * second_step_ratio,
        ))

    def test_reset_restarts_the_curve(self):
        """reset() (a new serve) starts the speed-up curve again from step 0."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.15)
        for _ in range(4):
            ball.speed_up()
        assert ball.speed_up_count == 4
        ball.reset()
        assert ball.speed_up_count == 0

    def test_triggers_share_one_curve(self):
        """Paddle and wall speed-ups advance the same step counter."""
        ball = _ball_with_speed_up(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE | SpeedUpTrigger.WALL_BOUNCE,
            curve=SpeedUpCurve.LOGARITHMIC,
        )
        ball.on_paddle_bounce()
        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
        ball._apply_triggered_speed_up(SpeedUpTrigger.CONTINUOUS)  # not enabled
        assert ball.speed_up_count == 2

    def test_continuous_trigger_respects_interval(self):
        """Continuous speed-up fires once per elapsed interval of game time."""
        ball = _ball_with_speed_up(triggers=SpeedUpTrigger.CONTINUOUS, interval=2.0)
        ball._advance_continuous_speed_up(1.75)
        assert ball.speed_up_count == 0
        ball._advance_continuous_speed_up(0.25)
        assert ball.speed_up_count == 1
        ball._advance_continuous_speed_up(1.0)
        assert ball.speed_up_count == 1
        ball._advance_continuous_speed_up(1.0)
        assert ball.speed_up_count == 2

    def test_continuous_timer_uses_game_time_not_wall_clock(self, mocker):
        """Wall-clock time passing (e.g. while paused) does not advance the timer."""
        mock_time = mocker.patch('time.time', return_value=0.0)
        ball = _ball_with_speed_up(triggers=SpeedUpTrigger.CONTINUOUS, interval=1.0)
        mock_time.return_value = 1_000.0  # a long pause: dt_tick is not called
        ball.dt_tick(1 / 64)
        assert ball.speed_up_count == 0

    def test_dt_tick_drives_the_continuous_timer(self):
        """dt_tick passes its dt to the continuous timer."""
        ball = _ball_with_speed_up(triggers=SpeedUpTrigger.CONTINUOUS, interval=0.25)
        for _ in range(16):  # 16 frames of 1/64 s = 0.25 s
            ball.dt_tick(1 / 64)
        assert ball.speed_up_count == 1

    def test_reset_restarts_the_continuous_timer(self):
        """A new serve starts a fresh interval."""
        ball = _ball_with_speed_up(triggers=SpeedUpTrigger.CONTINUOUS, interval=1.0)
        ball._advance_continuous_speed_up(0.9)
        ball.reset()
        ball._advance_continuous_speed_up(0.9)
        assert ball.speed_up_count == 0

    def test_float_accumulation_does_not_delay_a_speed_up(self):
        """Ten 0.1 s frames reach a 1.0 s interval though they sum to 0.9999999999999999."""
        ball = _ball_with_speed_up(triggers=SpeedUpTrigger.CONTINUOUS, interval=1.0)
        for _ in range(10):
            ball._advance_continuous_speed_up(0.1)
        assert ball.speed_up_count == 1


# ---------------------------------------------------------------------------
# Continuous schedule sweep: each schedule against a reference model, across frame
# rates, irregular frame times, and long hitches.
# ---------------------------------------------------------------------------

SCHEDULE_SWEEP_DURATION_SECONDS = 6.0
SCHEDULE_SWEEP_INTERVALS = (0.1, 0.25, 1.0)
SCHEDULE_TIMER_TOLERANCE = 1e-9


def _frame_durations(pattern: str) -> list[float]:
    """Return frame durations (seconds) covering SCHEDULE_SWEEP_DURATION_SECONDS."""
    if pattern.startswith('steady'):
        frames_per_second = int(pattern.removeprefix('steady'))
        frame_count = round(SCHEDULE_SWEEP_DURATION_SECONDS * frames_per_second)
        return [1.0 / frames_per_second] * frame_count
    if pattern == 'jittery':
        # Deterministic irregular frames between ~4 ms and ~45 ms
        durations = []
        elapsed = 0.0
        step = 0
        while elapsed < SCHEDULE_SWEEP_DURATION_SECONDS:
            duration = 0.004 + (step * 7919 % 41) / 1000.0
            durations.append(duration)
            elapsed += duration
            step += 1
        return durations
    # 'hitch': steady 60 fps with two long frames (2.6 s and 0.55 s) in the middle
    durations = [1.0 / 60] * 120 + [2.6] + [1.0 / 60] * 60 + [0.55] + [1.0 / 60] * 60
    return durations


def _reference_speed_up_count(
    schedule: SpeedUpSchedule, interval: float, durations: list[float]
) -> int:
    """Count speed-ups the documented rule for each schedule produces."""
    count = 0
    elapsed = 0.0
    for duration in durations:
        elapsed += duration
        due = math.floor((elapsed + SCHEDULE_TIMER_TOLERANCE) / interval)
        if due < 1:
            continue
        if schedule is SpeedUpSchedule.CATCH_UP:
            count += due
            elapsed -= due * interval
        elif schedule is SpeedUpSchedule.FIXED_RATE:
            count += 1
            elapsed -= due * interval
        else:  # MINIMUM_GAP
            count += 1
            elapsed = 0.0
        elapsed = max(elapsed, 0.0)
    return count


def _schedule_sweep_cases():
    """Every schedule x interval x frame pattern.

    Returns:
        list: pytest params of (schedule, interval, pattern).

    """
    return [
        pytest.param(schedule, interval, pattern, id=f'{schedule.name}-{interval}s-{pattern}')
        for schedule in SpeedUpSchedule
        for interval in SCHEDULE_SWEEP_INTERVALS
        for pattern in ('steady30', 'steady60', 'steady144', 'jittery', 'hitch')
    ]


class TestContinuousSpeedUpSchedule:
    """Each SpeedUpSchedule matches its rule and the properties that make it useful."""

    @staticmethod
    def _run(schedule: SpeedUpSchedule, interval: float, durations: list[float]) -> int:
        ball = _ball_with_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS,
            schedule=schedule,
            interval=interval,
            multiplier=1.0,  # count steps without changing speed
        )
        for duration in durations:
            ball._advance_continuous_speed_up(duration)
        return ball.speed_up_count

    def test_default_schedule_is_fixed_rate(self):
        """FIXED_RATE is the default: frame-rate independent with no bursts."""
        assert SpeedUpSettings().schedule is SpeedUpSchedule.FIXED_RATE

    @pytest.mark.parametrize(('schedule', 'interval', 'pattern'), _schedule_sweep_cases())
    def test_matches_reference_model(self, schedule, interval, pattern):
        """The ball's count matches the documented rule for every frame pattern."""
        durations = _frame_durations(pattern)
        assert self._run(schedule, interval, durations) == _reference_speed_up_count(
            schedule, interval, durations
        )

    @pytest.mark.parametrize('schedule', [SpeedUpSchedule.FIXED_RATE, SpeedUpSchedule.CATCH_UP])
    @pytest.mark.parametrize('interval', SCHEDULE_SWEEP_INTERVALS)
    def test_rate_is_independent_of_frame_rate(self, schedule, interval):
        """At any steady frame rate, 6 s of play gives exactly 6 / interval speed-ups."""
        expected_count = round(SCHEDULE_SWEEP_DURATION_SECONDS / interval)
        for pattern in ('steady30', 'steady60', 'steady144'):
            assert self._run(schedule, interval, _frame_durations(pattern)) == expected_count, (
                f'{schedule.name} at {pattern}'
            )

    def test_catch_up_counts_every_interval_even_across_hitches(self):
        """CATCH_UP always totals floor(elapsed / interval)."""
        durations = _frame_durations('hitch')
        expected_count = math.floor(sum(durations) / 0.25 + SCHEDULE_TIMER_TOLERANCE)
        assert self._run(SpeedUpSchedule.CATCH_UP, 0.25, durations) == expected_count

    def test_catch_up_bursts_after_a_long_frame(self):
        """CATCH_UP applies every missed speed-up in the frame that ends a hitch."""
        assert self._run(SpeedUpSchedule.CATCH_UP, 0.25, [1.0]) == 4

    def test_fixed_rate_applies_one_speed_up_after_a_long_frame(self):
        """FIXED_RATE never bursts: a hitch yields one speed-up, then the schedule resumes."""
        assert self._run(SpeedUpSchedule.FIXED_RATE, 0.25, [1.0]) == 1
        # Remainder is kept: 1.1 s -> one speed-up now, next due 0.15 s later
        assert self._run(SpeedUpSchedule.FIXED_RATE, 0.25, [1.1, 0.15]) == 2
        assert self._run(SpeedUpSchedule.FIXED_RATE, 0.25, [1.1, 0.14]) == 1

    def test_minimum_gap_discards_leftover_time(self):
        """MINIMUM_GAP restarts the interval when it fires, so frame overshoot is lost."""
        # At 60 fps a 0.025 s interval needs 2 frames (0.0333 s) to cross; MINIMUM_GAP
        # throws the 0.0083 s overshoot away each time, FIXED_RATE carries it forward.
        steady_60_frames = _frame_durations('steady60')
        assert self._run(SpeedUpSchedule.MINIMUM_GAP, 0.025, steady_60_frames) == 180
        assert self._run(SpeedUpSchedule.FIXED_RATE, 0.025, steady_60_frames) == 240

    @pytest.mark.parametrize('schedule', list(SpeedUpSchedule))
    def test_no_time_no_speed_up(self, schedule):
        """Zero-length frames never trigger a speed-up."""
        assert self._run(schedule, 0.25, [0.0] * 1000) == 0


# ---------------------------------------------------------------------------
# Sweep: every trigger x curve x axes x heading x speed, over several speed-ups.
# ---------------------------------------------------------------------------

SPEED_UP_SWEEP_ANGLES_DEGREES = tuple(range(0, 360, 15))
SPEED_UP_SWEEP_SPEEDS = (60.0, 250.0, 450.0)
SPEED_UP_SWEEP_MULTIPLIER = 1.15
SPEED_UP_SWEEP_STEPS = 5
SPEED_UP_DIRECTION_TOLERANCE = 1e-9


def _speed_up_sweep_cases():
    """Every trigger x curve x axes x heading x speed.

    Returns:
        list: pytest params of (trigger, curve, axes, angle, speed).

    """
    return [
        pytest.param(
            trigger,
            curve,
            axes,
            angle,
            speed,
            id=f'{trigger.name}-{curve.name}-{axes.name}-{angle:03d}deg@{speed:.0f}',
        )
        for trigger in (
            SpeedUpTrigger.PADDLE_BOUNCE,
            SpeedUpTrigger.WALL_BOUNCE,
            SpeedUpTrigger.CONTINUOUS,
        )
        for curve in SpeedUpCurve
        for axes in SpeedUpAxes
        for angle in SPEED_UP_SWEEP_ANGLES_DEGREES
        for speed in SPEED_UP_SWEEP_SPEEDS
    ]


def _fire_trigger(ball: BallSprite, trigger: SpeedUpTrigger) -> None:
    """Fire one speed-up event of the given kind through the ball's trigger path."""
    if trigger is SpeedUpTrigger.PADDLE_BOUNCE:
        ball.on_paddle_bounce()
    elif trigger is SpeedUpTrigger.WALL_BOUNCE:
        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)
    else:
        ball._advance_continuous_speed_up(ball.speed_up_settings.interval)


class TestBallSpeedUpSweep:
    """Each configuration follows its curve on the configured axes from every heading."""

    @pytest.mark.parametrize(
        ('trigger', 'curve', 'axes', 'angle', 'speed'), _speed_up_sweep_cases()
    )
    def test_speed_up_follows_curve_on_configured_axes(self, trigger, curve, axes, angle, speed):
        """After N speed-ups, the configured speed equals base * f(N); the rest is untouched."""
        ball = _ball_with_speed_up(
            triggers=trigger,
            curve=curve,
            axes=axes,
            multiplier=SPEED_UP_SWEEP_MULTIPLIER,
        )
        initial_x = speed * math.cos(math.radians(angle))
        initial_y = speed * math.sin(math.radians(angle))
        ball.speed = Speed(initial_x, initial_y)

        for _ in range(SPEED_UP_SWEEP_STEPS):
            _fire_trigger(ball, trigger)

        factor = _curve_value(curve, SPEED_UP_SWEEP_MULTIPLIER, SPEED_UP_SWEEP_STEPS)
        expected_x = initial_x * factor if axes is not SpeedUpAxes.Y_ONLY else initial_x
        expected_y = initial_y * factor if axes is not SpeedUpAxes.X_ONLY else initial_y
        description = (
            f'{trigger.name} {curve.name} {axes.name} from ({initial_x:.2f}, {initial_y:.2f})'
        )
        assert ball.speed_up_count == SPEED_UP_SWEEP_STEPS, description
        assert ball.speed.x == pytest.approx(expected_x, rel=1e-12, abs=1e-9), description
        assert ball.speed.y == pytest.approx(expected_y, rel=1e-12, abs=1e-9), description
        if axes is SpeedUpAxes.BOTH:
            final_speed = math.hypot(ball.speed.x, ball.speed.y)
            assert (
                math.dist(
                    (ball.speed.x / final_speed, ball.speed.y / final_speed),
                    (initial_x / speed, initial_y / speed),
                )
                <= SPEED_UP_DIRECTION_TOLERANCE
            ), f'{description}: heading changed'
