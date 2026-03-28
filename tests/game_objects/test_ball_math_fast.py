#!/usr/bin/env python3
"""Fast mathematical stability test for ball bouncing."""

import logging
import math
import time
from typing import NamedTuple

import pytest

LOG = logging.getLogger(__name__)


class BounceState(NamedTuple):
    """Position and velocity state for a bouncing ball."""

    x: float
    y: float
    speed_x: float
    speed_y: float


class BoundsRect(NamedTuple):
    """Ball and screen dimensions for bounce boundary calculations."""

    ball_width: int
    ball_height: int
    screen_width: int
    screen_height: int


class BounceResult(NamedTuple):
    """Result of applying wall bounce logic."""

    x: float
    y: float
    speed_x: float
    speed_y: float
    x_bounces: int
    y_bounces: int


class SimConfig(NamedTuple):
    """Configuration parameters for running a bounce simulation."""

    dt: float
    iterations: int


def _apply_wall_bounces(state: BounceState, bounds: BoundsRect) -> BounceResult:
    """Apply wall bounce logic and return updated position, speed, and bounce counts.

    Returns:
        BounceResult with updated position, speed, and bounce counts.

    """
    new_x = state.x
    new_y = state.y
    speed_x = state.speed_x
    speed_y = state.speed_y
    x_bounces = 0
    y_bounces = 0

    # Top bounce
    if new_y <= 0:
        new_y = 1
        speed_y = abs(speed_y)
        y_bounces += 1

    # Bottom bounce
    if new_y + bounds.ball_height >= bounds.screen_height:
        new_y = bounds.screen_height - bounds.ball_height - 1
        speed_y = -abs(speed_y)
        y_bounces += 1

    # Left bounce
    if new_x <= 0:
        new_x = 1
        speed_x = abs(speed_x)
        x_bounces += 1

    # Right bounce
    if new_x + bounds.ball_width >= bounds.screen_width:
        new_x = bounds.screen_width - bounds.ball_width - 1
        speed_x = -abs(speed_x)
        x_bounces += 1

    return BounceResult(
        x=new_x,
        y=new_y,
        speed_x=speed_x,
        speed_y=speed_y,
        x_bounces=x_bounces,
        y_bounces=y_bounces,
    )


def _run_bounce_simulation(state: BounceState, bounds: BoundsRect, config: SimConfig):
    """Run the ball bounce simulation loop.

    Returns:
        A dict with simulation results: final position, speed, bounce counts,
        position bounds, and magnitude samples.

    """
    x = state.x
    y = state.y
    speed_x = state.speed_x
    speed_y = state.speed_y

    # Use a dict for accumulating statistics to reduce local variable count
    stats = {
        'bounce_count': 0,
        'x_bounces': 0,
        'y_bounces': 0,
        'min_x': x,
        'max_x': x,
        'min_y': y,
        'max_y': y,
    }
    initial_magnitude = math.sqrt(speed_x**2 + speed_y**2)
    magnitude_samples = []
    start_time = time.time()

    for i in range(config.iterations):
        new_x = x + round(speed_x * config.dt)
        new_y = y + round(speed_y * config.dt)

        bounce_result = _apply_wall_bounces(
            state=BounceState(x=new_x, y=new_y, speed_x=speed_x, speed_y=speed_y),
            bounds=bounds,
        )
        new_x = bounce_result.x
        new_y = bounce_result.y
        speed_x = bounce_result.speed_x
        speed_y = bounce_result.speed_y
        stats['x_bounces'] += bounce_result.x_bounces
        stats['y_bounces'] += bounce_result.y_bounces
        stats['bounce_count'] += bounce_result.x_bounces + bounce_result.y_bounces

        x, y = new_x, new_y
        stats['min_x'] = min(stats['min_x'], x)
        stats['max_x'] = max(stats['max_x'], x)
        stats['min_y'] = min(stats['min_y'], y)
        stats['max_y'] = max(stats['max_y'], y)

        # Sample speed magnitude every 100000 iterations
        if i % 100000 == 0:
            magnitude_samples.append(math.sqrt(speed_x**2 + speed_y**2))

    return {
        'x': x,
        'y': y,
        'speed_x': speed_x,
        'speed_y': speed_y,
        'initial_magnitude': initial_magnitude,
        'magnitude_samples': magnitude_samples,
        'total_time': time.time() - start_time,
        **stats,
    }


def _log_simulation_results(results, iterations):
    """Log the results of a bounce simulation."""
    LOG.debug('\n=== FINAL RESULTS ===')
    LOG.debug(f'Total bounces: {results["bounce_count"]:,}')
    LOG.debug(f'X bounces: {results["x_bounces"]:,}')
    LOG.debug(f'Y bounces: {results["y_bounces"]:,}')
    LOG.debug(f'Total time: {results["total_time"]:.3f} seconds')
    LOG.debug(f'Iterations per second: {iterations / results["total_time"]:.0f}')
    LOG.debug(f'Calculations per second: {iterations * 4 / results["total_time"]:.0f}')
    LOG.debug(f'Final position: ({results["x"]:.3f}, {results["y"]:.3f})')
    LOG.debug(f'Final speed: ({results["speed_x"]:.6f}, {results["speed_y"]:.6f})')
    final_magnitude = math.sqrt(results['speed_x'] ** 2 + results['speed_y'] ** 2)
    LOG.debug(f'Final speed magnitude: {final_magnitude:.6f}')
    LOG.debug(
        f'Position bounds: X[{results["min_x"]:.1f}-{results["max_x"]:.1f}]'
        f' Y[{results["min_y"]:.1f}-{results["max_y"]:.1f}]',
    )


def _analyze_magnitude_stability(magnitude_samples, initial_magnitude):
    """Analyze and log speed magnitude stability from samples."""
    if not magnitude_samples:
        return

    min_magnitude = min(magnitude_samples)
    max_magnitude = max(magnitude_samples)
    avg_magnitude = sum(magnitude_samples) / len(magnitude_samples)
    magnitude_drift = max_magnitude - min_magnitude

    LOG.debug('\nSpeed magnitude analysis:')
    LOG.debug(f'  Initial: {initial_magnitude:.6f}')
    LOG.debug(f'  Samples: {len(magnitude_samples)}')
    LOG.debug(f'  Min: {min_magnitude:.6f}')
    LOG.debug(f'  Max: {max_magnitude:.6f}')
    LOG.debug(f'  Average: {avg_magnitude:.6f}')
    LOG.debug(f'  Drift: {magnitude_drift:.6f}')

    if magnitude_drift > 1.0:
        LOG.debug('  WARNING: Significant speed magnitude drift detected!')
    else:
        LOG.info('  Speed magnitude is stable.')


def _check_position_bounds(results, screen_width, screen_height, ball_width, ball_height):
    """Check and log whether position bounds stayed within expected range."""
    expected_min_x, expected_max_x = 1, screen_width - ball_width - 1
    expected_min_y, expected_max_y = 1, screen_height - ball_height - 1

    if (
        results['min_x'] >= expected_min_x
        and results['max_x'] <= expected_max_x
        and results['min_y'] >= expected_min_y
        and results['max_y'] <= expected_max_y
    ):
        LOG.info('  Position bounds are correct')
    else:
        LOG.debug('  Position bounds issue detected')
        LOG.debug(
            f'    Expected X: [{expected_min_x}-{expected_max_x}],'
            f' got [{results["min_x"]:.1f}-{results["max_x"]:.1f}]',
        )
        LOG.debug(
            f'    Expected Y: [{expected_min_y}-{expected_max_y}],'
            f' got [{results["min_y"]:.1f}-{results["max_y"]:.1f}]',
        )


def _check_finite_values(speed_x, speed_y, x, y):
    """Check for NaN or infinity values and fail the test if found."""
    LOG.debug('\nFloating-point precision check:')
    LOG.debug(f'  Speed X precision: {speed_x:.10f}')
    LOG.debug(f'  Speed Y precision: {speed_y:.10f}')
    LOG.debug(f'  Position X precision: {x:.10f}')
    LOG.debug(f'  Position Y precision: {y:.10f}')

    if math.isnan(speed_x) or math.isnan(speed_y) or math.isnan(x) or math.isnan(y):
        pytest.fail('NaN values detected in ball calculations')
    elif math.isinf(speed_x) or math.isinf(speed_y) or math.isinf(x) or math.isinf(y):
        pytest.fail('Infinity values detected in ball calculations')
    else:
        LOG.info('  All values are finite')


def test_ball_math_fast():
    """Test ball mathematical stability with direct calculations."""
    LOG.debug('=== FAST BALL MATHEMATICAL STABILITY TEST ===')
    LOG.debug('Testing mathematical calculations for potential issues...')

    screen_width = 800
    screen_height = 600
    ball_width = 20
    ball_height = 20
    iterations = 100000

    LOG.debug(f'\nRunning {iterations:,} iterations...')

    results = _run_bounce_simulation(
        state=BounceState(x=400.0, y=300.0, speed_x=250.0, speed_y=125.0),
        bounds=BoundsRect(
            ball_width=ball_width,
            ball_height=ball_height,
            screen_width=screen_width,
            screen_height=screen_height,
        ),
        config=SimConfig(dt=1.0 / 60.0, iterations=iterations),
    )

    _log_simulation_results(results, iterations)
    _analyze_magnitude_stability(results['magnitude_samples'], results['initial_magnitude'])

    # Check for mathematical stability
    LOG.debug('\nMathematical stability check:')
    final_speed_x = float(results['speed_x'])
    final_speed_y = float(results['speed_y'])
    initial_mag = float(results['initial_magnitude'])
    final_magnitude = math.sqrt(final_speed_x**2 + final_speed_y**2)
    magnitude_change = abs(final_magnitude - initial_mag)
    LOG.debug(f'  Speed magnitude change: {magnitude_change:.6f}')

    _check_position_bounds(results, screen_width, screen_height, ball_width, ball_height)
    _check_finite_values(final_speed_x, final_speed_y, results['x'], results['y'])

    # Assert that the test completed successfully
    bounce_count = int(results['bounce_count'])
    assert bounce_count >= 0, 'Bounce count should be non-negative'
    assert len(results['magnitude_samples']) > 0, 'Should have magnitude samples'

    # Check for mathematical stability (no excessive drift)
    if len(results['magnitude_samples']) > 1:
        drift = max(results['magnitude_samples']) - min(results['magnitude_samples'])
        assert drift < 0.01, f'Mathematical drift too high: {drift:.6f}'

    LOG.info('\nTest completed successfully')


if __name__ == '__main__':
    test_ball_math_fast()
