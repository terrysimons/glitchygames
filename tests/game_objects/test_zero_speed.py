#!/usr/bin/env python3
"""Test what happens when ball speed is zero."""

import logging
import math
import sys
from pathlib import Path

# Add project root so direct imports work
sys.path.insert(0, str(Path(__file__).parent))

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
)
from glitchygames.movement import Speed
from tests.game_objects.test_ball import _drawn_position
from tests.mocks.test_mock_factory import MockFactory

LOG = logging.getLogger(__name__)
SPEED_UP_MULTIPLIER = 1.15


def _logarithmic_settings(triggers: SpeedUpTrigger, axes: SpeedUpAxes) -> SpeedUpSettings:
    """Build logarithmic speed-up settings for the given triggers and axes.

    Returns:
        SpeedUpSettings: The settings.

    """
    return SpeedUpSettings(
        triggers=triggers,
        curve=SpeedUpCurve.LOGARITHMIC,
        axes=axes,
        multiplier=SPEED_UP_MULTIPLIER,
    )


def _run_basic_bounce_scenarios(ball):
    """Run basic paddle bounce scenarios (tests 1-7)."""
    LOG.debug('1. Both X and Y speeds are 0:')
    ball.speed = Speed(0.0, 0.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')
    ball.on_paddle_bounce()
    LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')
    LOG.debug('   Result: Ball remains stationary (no movement)\n')

    LOG.debug('2. Only X speed is 0, Y speed is non-zero:')
    ball.speed = Speed(0.0, 100.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')
    ball.on_paddle_bounce()
    LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')
    LOG.debug("   Result: X remains 0, Y unchanged (X-only speedup doesn't affect Y)\n")

    LOG.debug('3. Only Y speed is 0, X speed is non-zero:')
    ball.speed = Speed(100.0, 0.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')
    ball.on_paddle_bounce()
    LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')
    LOG.debug('   Result: X speed increases, Y remains 0\n')

    LOG.debug('4. Test with Y-only speedup mode:')
    ball.speed_up_settings = _logarithmic_settings(
        triggers=SpeedUpTrigger.PADDLE_BOUNCE, axes=SpeedUpAxes.Y_ONLY
    )
    ball.speed = Speed(100.0, 0.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')
    ball.on_paddle_bounce()
    LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')
    LOG.debug("   Result: X unchanged, Y remains 0 (Y-only speedup doesn't affect X)\n")

    LOG.debug('5. Test with both X and Y speeds 0 and Y-only speedup:')
    ball.speed = Speed(0.0, 0.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')
    ball.on_paddle_bounce()
    LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')
    LOG.debug('   Result: Ball remains stationary\n')

    LOG.debug('6. Test movement calculation with zero speed:')
    ball.speed = Speed(0.0, 0.0)
    dt = 0.016  # 60 FPS
    move_x = ball.speed.x * dt
    move_y = ball.speed.y * dt
    LOG.debug(f'   Movement calculation: move_x={move_x}, move_y={move_y}')
    LOG.debug('   Result: No movement occurs (0 * dt = 0)\n')

    LOG.debug('7. Test with very small speeds (near zero):')
    ball.speed = Speed(0.001, 0.001)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')
    ball.on_paddle_bounce()
    LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')
    LOG.debug('   Result: X speed increases slightly, Y unchanged\n')


def _run_continuous_speedup_scenarios(ball):
    """Run continuous speed-up scenarios (tests 8-10)."""
    LOG.debug('8. Test continuous speed-up with zero initial speed over many iterations:')
    ball.speed_up_settings = _logarithmic_settings(
        triggers=SpeedUpTrigger.CONTINUOUS, axes=SpeedUpAxes.X_ONLY
    )
    ball.speed = Speed(0.0, 0.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')

    # Simulate many game ticks, each one speed-up interval of game time long, so every
    # tick is due a speed-up (the timer counts game time, so no real waiting is needed)
    interval = ball.speed_up_settings.interval
    speed_up_count_before = ball.speed_up_count

    for iteration in range(10):
        ball.dt_tick(interval)
        LOG.debug(f'   Iteration {iteration + 1}: speed=({ball.speed.x:.6f}, {ball.speed.y:.6f})')

    assert ball.speed_up_count == speed_up_count_before + 10
    assert (ball.speed.x, ball.speed.y) == (0.0, 0.0)
    LOG.debug('   Result: X speed remains 0, Y speed remains 0 (no movement)\n')

    LOG.debug('9. Test with non-zero initial speed and continuous speed-up:')
    # Start mid-screen: the ball travels ~50 px in this scenario, and a wall bounce from
    # a spawn near an edge would flip Y and break the "Y unchanged" check
    ball.world_x = float(ball.screen_width - ball.width) / 2
    ball.world_y = float(ball.screen_height - ball.height) / 2
    ball.speed = Speed(10.0, 5.0)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')

    for iteration in range(10):
        ball.dt_tick(interval)
        LOG.debug(f'   Iteration {iteration + 1}: speed=({ball.speed.x:.6f}, {ball.speed.y:.6f})')

    assert ball.speed.x > 10.0
    assert ball.speed.y == 5.0
    LOG.debug('   Result: X speed increases over time, Y speed unchanged\n')

    LOG.debug('10. Test movement over many iterations with zero speed:')
    ball.speed = Speed(0.0, 0.0)
    # Move via world_x/world_y; the engine places rect from them before each render, so
    # setting rect alone would be overwritten
    ball.world_x = 100.0
    ball.world_y = 100.0
    LOG.debug(f'   Initial position: ({ball.world_x}, {ball.world_y})')

    for iteration in range(20):
        ball.dt_tick(interval)
        LOG.debug(
            f'   Iteration {iteration + 1}:'
            f' position=({ball.world_x}, {ball.world_y}),'
            f' speed=({ball.speed.x}, {ball.speed.y})',
        )

    assert _drawn_position(ball) == (100, 100)
    assert (ball.speed.x, ball.speed.y) == (0.0, 0.0)
    LOG.debug('   Result: Position never changes (no movement with zero speed)\n')


def _run_bounce_tests_for_mode(ball, speed_up_settings, test_speeds, label):
    """Run paddle bounce tests for the given speed-up settings across all test speed combos."""
    ball.speed_up_settings = speed_up_settings

    for index, (x_speed, y_speed, description) in enumerate(test_speeds, start=1):
        LOG.debug(f'{label}.{index} Testing {description}:')
        ball.speed = Speed(x_speed, y_speed)
        LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')

        ball.on_paddle_bounce()
        LOG.debug(f'   After paddle bounce: ({ball.speed.x}, {ball.speed.y})')

        x_is_zero = math.isclose(x_speed, 0.0, abs_tol=1e-9)
        y_is_zero = math.isclose(y_speed, 0.0, abs_tol=1e-9)

        # A speed-up only scales components, so a zero component must stay zero
        if x_is_zero:
            assert ball.speed.x == 0.0
        if y_is_zero:
            assert ball.speed.y == 0.0

        if x_is_zero and y_is_zero:
            LOG.debug('   Result: Both speeds remain 0 (stationary ball)\n')
        elif x_is_zero:
            LOG.debug('   Result: X remains 0, Y component affected by mode\n')
        elif y_is_zero:
            LOG.debug('   Result: Y remains 0, X component affected by mode\n')
        else:
            LOG.debug('   Result: Non-zero components affected by mode\n')


def _run_continuous_speedup_test(ball, x_speed, y_speed, description, label_index):
    """Run a continuous speed-up test for a single speed combination."""
    LOG.debug(f'14.{label_index} Testing continuous speedup with {description}:')
    ball.speed = Speed(x_speed, y_speed)
    LOG.debug(f'   Initial speed: ({ball.speed.x}, {ball.speed.y})')

    # Each tick is one speed-up interval of game time, so every tick is due a speed-up
    for iteration in range(5):
        ball.dt_tick(ball.speed_up_settings.interval)
        LOG.debug(f'   Iteration {iteration + 1}: speed=({ball.speed.x:.6f}, {ball.speed.y:.6f})')

    # A speed-up only scales components: zero stays zero, non-zero grows in magnitude
    for initial_component, final_component in ((x_speed, ball.speed.x), (y_speed, ball.speed.y)):
        if math.isclose(initial_component, 0.0, abs_tol=1e-9):
            assert final_component == 0.0
        else:
            assert abs(final_component) > abs(initial_component)

    both_nonzero = not math.isclose(x_speed, 0.0, abs_tol=1e-9) and not math.isclose(
        y_speed,
        0.0,
        abs_tol=1e-9,
    )
    result_msg = 'X and Y speeds increase' if both_nonzero else 'Only non-zero components increase'
    LOG.debug(f'   Result: {result_msg}\n')


def test_zero_speed_scenarios(mocker):
    """Test various scenarios with zero speed components."""
    # Set up centralized mocks
    MockFactory.setup_pygame_mocks_with_mocker(mocker)

    LOG.debug('=== Testing Zero Speed Scenarios ===\n')

    # Create a ball with X-only speedup
    ball = BallSprite(
        speed_up_settings=_logarithmic_settings(
            triggers=SpeedUpTrigger.PADDLE_BOUNCE, axes=SpeedUpAxes.X_ONLY
        ),
    )

    _run_basic_bounce_scenarios(ball)
    _run_continuous_speedup_scenarios(ball)

    # Directional zero speed tests using extracted helper
    test_speeds = [
        (0.0, 0.0, 'Both zero'),
        (100.0, 0.0, 'X positive, Y zero'),
        (-100.0, 0.0, 'X negative, Y zero'),
        (0.0, 100.0, 'X zero, Y positive'),
        (0.0, -100.0, 'X zero, Y negative'),
        (50.0, 0.0, 'X small positive, Y zero'),
        (-50.0, 0.0, 'X small negative, Y zero'),
        (0.0, 50.0, 'X zero, Y small positive'),
        (0.0, -50.0, 'X zero, Y small negative'),
    ]

    LOG.debug('=== COMPREHENSIVE DIRECTIONAL ZERO SPEED TESTS ===\n')
    _run_bounce_tests_for_mode(
        ball,
        _logarithmic_settings(triggers=SpeedUpTrigger.PADDLE_BOUNCE, axes=SpeedUpAxes.X_ONLY),
        test_speeds,
        label='11',
    )

    LOG.debug('=== TESTING Y-ONLY SPEEDUP ===\n')
    _run_bounce_tests_for_mode(
        ball,
        _logarithmic_settings(triggers=SpeedUpTrigger.PADDLE_BOUNCE, axes=SpeedUpAxes.Y_ONLY),
        test_speeds,
        label='12',
    )

    LOG.debug('=== TESTING BOTH X AND Y SPEEDUP ===\n')
    _run_bounce_tests_for_mode(
        ball,
        _logarithmic_settings(triggers=SpeedUpTrigger.PADDLE_BOUNCE, axes=SpeedUpAxes.BOTH),
        test_speeds,
        label='13',
    )

    # Test continuous speed-up with various zero combinations
    LOG.debug('=== TESTING CONTINUOUS SPEEDUP WITH ZERO COMBINATIONS ===\n')
    ball.speed_up_settings = _logarithmic_settings(
        triggers=SpeedUpTrigger.CONTINUOUS, axes=SpeedUpAxes.BOTH
    )

    continuous_test_speeds = [
        (0.0, 0.0, 'Both zero'),
        (10.0, 0.0, 'X positive, Y zero'),
        (0.0, 10.0, 'X zero, Y positive'),
        (5.0, 0.0, 'X small positive, Y zero'),
        (0.0, 5.0, 'X zero, Y small positive'),
    ]

    for index, (x_speed, y_speed, description) in enumerate(continuous_test_speeds, start=1):
        _run_continuous_speedup_test(ball, x_speed, y_speed, description, index)


if __name__ == '__main__':
    test_zero_speed_scenarios()  # type: ignore[missing-argument]
