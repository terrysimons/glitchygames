#!/usr/bin/env python3
"""Multi-ball test with wall bouncing enabled (no ball-to-ball collisions)."""

import logging
import math
import random
import time

import pygame

from glitchygames.game_objects.ball import BallSprite

LOG = logging.getLogger(__name__)


def _create_wall_bouncing_balls(num_balls, screen_width=800, screen_height=600):
    """Create multiple balls with wall bouncing enabled and randomized positions/speeds.

    Returns:
        List of BallSprite instances with randomized positions and speeds.

    """
    balls = []
    for _index in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        assert ball.rect is not None
        ball.rect.x = random.randint(50, screen_width - 50)
        ball.rect.y = random.randint(50, screen_height - 50)
        ball.speed.x = random.uniform(-200, 200)
        ball.speed.y = random.uniform(-200, 200)
        balls.append(ball)
    return balls


def _run_wall_bounce_simulation(balls, max_frames, dt, screen_width=800, screen_height=600):
    """Run wall bounce simulation and collect trajectory/bounce data.

    Returns:
        A dict with frame_count, total_bounces, x_bounces, y_bounces,
        trajectory_data, speed_magnitude_samples, and start_time.

    """
    start_time = time.time()
    total_bounces = 0
    x_bounces = 0
    y_bounces = 0
    frame_count = 0

    trajectory_data = [[] for _ in range(len(balls))]
    speed_magnitude_samples = [[] for _ in range(len(balls))]

    while frame_count < max_frames and any(ball.alive() for ball in balls):
        for ball_index, ball in enumerate(balls):
            if not ball.alive():
                continue

            ball.dt_tick(dt)

            new_x, new_y = ball.rect.x, ball.rect.y
            trajectory_data[ball_index].append((new_x, new_y))

            # Check for wall bounces
            if new_x <= 1 or new_x >= screen_width - ball.width - 1:
                x_bounces += 1
                total_bounces += 1
                LOG.debug(f'  Ball {ball_index + 1} X wall bounce at x={new_x}')

            if new_y <= 1 or new_y >= screen_height - ball.height - 1:
                y_bounces += 1
                total_bounces += 1
                LOG.debug(f'  Ball {ball_index + 1} Y wall bounce at y={new_y}')

            # Sample speed magnitude every 60 frames (1 second)
            if frame_count % 60 == 0:
                magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
                speed_magnitude_samples[ball_index].append(magnitude)

        frame_count += 1

        if frame_count % 300 == 0:
            alive_count = sum(1 for ball in balls if ball.alive())
            LOG.debug(
                '  Frame %s: %s balls alive, %s total bounces',
                frame_count,
                alive_count,
                total_bounces,
            )

    return {
        'frame_count': frame_count,
        'total_bounces': total_bounces,
        'x_bounces': x_bounces,
        'y_bounces': y_bounces,
        'trajectory_data': trajectory_data,
        'speed_magnitude_samples': speed_magnitude_samples,
        'start_time': start_time,
    }


def _analyze_ball_trajectory(ball, ball_index, trajectory_positions, magnitude_samples):
    """Analyze and log a single ball's trajectory and speed stability."""
    x_positions = [pos[0] for pos in trajectory_positions]
    y_positions = [pos[1] for pos in trajectory_positions]

    min_x, max_x = min(x_positions), max(x_positions)
    min_y, max_y = min(y_positions), max(y_positions)

    LOG.debug(f'Ball {ball_index + 1} trajectory:')
    LOG.debug(f'  Position bounds: X[{min_x:.1f}-{max_x:.1f}] Y[{min_y:.1f}-{max_y:.1f}]')
    LOG.debug(f'  Final position: ({ball.rect.x}, {ball.rect.y})')
    LOG.debug(f'  Final speed: ({ball.speed.x:.3f}, {ball.speed.y:.3f})')
    LOG.debug(f'  Final magnitude: {math.sqrt(ball.speed.x**2 + ball.speed.y**2):.3f}')

    x_drift = max_x - min_x
    y_drift = max_y - min_y

    if x_drift > 50 or y_drift > 50:
        LOG.debug('  Significant position drift detected')
    else:
        LOG.info('  Position is stable')

    if magnitude_samples:
        min_mag = min(magnitude_samples)
        max_mag = max(magnitude_samples)
        drift = max_mag - min_mag

        LOG.debug(f'  Speed magnitude: min={min_mag:.3f}, max={max_mag:.3f}, drift={drift:.6f}')

        if drift < 0.01:
            LOG.info('  Speed magnitude is stable')
        else:
            LOG.debug('  Speed magnitude drift detected')


def _analyze_wall_bounce_results(balls, results):
    """Analyze and log trajectory and speed stability results.

    Returns:
        The number of balls still alive.

    """
    total_time = time.time() - results['start_time']
    final_alive = sum(1 for ball in balls if ball.alive())

    LOG.debug('\n=== FINAL RESULTS ===')
    LOG.debug(f'Total time: {total_time:.2f} seconds')
    LOG.debug(f'Frames processed: {results["frame_count"]:,}')
    LOG.debug('Balls still alive: %s', final_alive)
    LOG.debug(f'Total wall bounces: {results["total_bounces"]}')
    LOG.debug(f'X wall bounces: {results["x_bounces"]}')
    LOG.debug(f'Y wall bounces: {results["y_bounces"]}')

    # Analyze individual ball trajectories
    LOG.debug('\n=== TRAJECTORY ANALYSIS ===')
    for ball_index, ball in enumerate(balls):
        if ball.alive() and results['trajectory_data'][ball_index]:
            _analyze_ball_trajectory(
                ball,
                ball_index,
                results['trajectory_data'][ball_index],
                results['speed_magnitude_samples'][ball_index],
            )

    return final_alive


def test_multi_ball_wall_bounce():
    """Test multiple balls with wall bouncing enabled."""
    LOG.debug('=== MULTI-BALL WALL BOUNCE TEST ===')
    LOG.debug('Testing multiple balls with wall bouncing enabled...')

    # Initialize pygame
    pygame.init()
    pygame.display.set_mode((800, 600))

    num_balls = 5
    balls = _create_wall_bouncing_balls(num_balls)

    LOG.debug('Created %s balls with wall bouncing enabled', num_balls)
    LOG.debug('Initial ball states:')
    for ball_index, ball in enumerate(balls):
        magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        LOG.debug(
            f'  Ball {ball_index + 1}: pos=({ball.rect.x},{ball.rect.y})'
            f' speed=({ball.speed.x:.1f},{ball.speed.y:.1f})'
            f' mag={magnitude:.1f}',
        )

    dt = 1.0 / 60.0  # 60 FPS
    max_frames = 1800  # 30 seconds at 60 FPS

    LOG.debug(f'\nRunning simulation for {max_frames} frames ({max_frames / 60:.1f} seconds)...')

    results = _run_wall_bounce_simulation(balls, max_frames, dt)
    final_alive = _analyze_wall_bounce_results(balls, results)

    # Overall analysis
    LOG.debug('\n=== OVERALL ANALYSIS ===')
    if final_alive == num_balls:
        LOG.info('  All balls survived with wall bouncing enabled')
    else:
        LOG.debug('  Only %s/%s balls survived', final_alive, num_balls)

    total_bounces = int(results['total_bounces'])
    if total_bounces > 0:
        LOG.info('  Wall bouncing is working (%s total bounces)', total_bounces)
    else:
        LOG.debug('  No wall bounces detected - bouncing may be disabled')

    pygame.quit()

    # Assert that the test completed successfully
    assert final_alive > 0, 'At least one ball should survive'
    assert total_bounces > 0, 'Wall bouncing should be working'

    LOG.info('\nTest completed successfully')


if __name__ == '__main__':
    test_multi_ball_wall_bounce()
