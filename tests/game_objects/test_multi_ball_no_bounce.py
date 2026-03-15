#!/usr/bin/env python3
"""Multi-ball test with bouncing disabled (Paddle Slap style)."""

import logging
import random
import time

import pygame

from glitchygames.game_objects.ball import BallSprite

LOG = logging.getLogger(__name__)


def _create_no_bounce_balls(num_balls, screen_width=800, screen_height=600):
    """Create multiple balls with bouncing disabled and randomized positions/speeds.

    Returns:
        List of BallSprite instances with bouncing disabled.

    """
    balls = []
    for _index in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=False,
            bounce_left_right=False,
        )
        ball.rect.x = random.randint(100, screen_width - 100)
        ball.rect.y = random.randint(100, screen_height - 100)
        ball.speed.x = random.uniform(-300, 300)
        ball.speed.y = random.uniform(-300, 300)
        balls.append(ball)
    return balls


def _run_no_bounce_simulation(balls, max_frames, dt):
    """Run simulation with bouncing disabled and track ball deaths.

    Returns:
        A dict with frame_count, balls_died, and start_time.

    """
    start_time = time.time()
    balls_died = 0
    frame_count = 0

    while frame_count < max_frames and any(ball.alive() for ball in balls):
        for ball_index, ball in enumerate(balls):
            if ball.alive():
                ball.dt_tick(dt)
                new_x, new_y = ball.rect.x, ball.rect.y

                # Check if ball died
                if not ball.alive():
                    balls_died += 1
                    LOG.debug(f'  Ball {ball_index + 1} died at position ({new_x}, {new_y})')

        frame_count += 1

        if frame_count % 600 == 0:
            alive_count = sum(1 for ball in balls if ball.alive())
            LOG.debug(f'  Frame {frame_count}: {alive_count} balls alive, {balls_died} died')

    return {
        'frame_count': frame_count,
        'balls_died': balls_died,
        'start_time': start_time,
    }


def test_multi_ball_no_bounce():
    """Test multiple balls with bouncing disabled."""
    LOG.debug('=== MULTI-BALL NO BOUNCE TEST ===')
    LOG.debug('Testing multiple balls with bouncing disabled (Paddle Slap style)...')

    # Initialize pygame
    pygame.init()
    pygame.display.set_mode((800, 600))

    num_balls = 10
    balls = _create_no_bounce_balls(num_balls)

    LOG.debug(f'Created {num_balls} balls with bouncing disabled')
    LOG.debug('Initial ball states:')
    for ball_index, ball in enumerate(balls):
        LOG.debug(
            f'  Ball {ball_index + 1}: pos=({ball.rect.x},{ball.rect.y})'
            f' speed=({ball.speed.x:.1f},{ball.speed.y:.1f})'
        )

    dt = 1.0 / 60.0  # 60 FPS
    max_frames = 3600  # 60 seconds at 60 FPS

    LOG.debug(f'\nRunning simulation for {max_frames} frames ({max_frames / 60:.1f} seconds)...')

    results = _run_no_bounce_simulation(balls, max_frames, dt)

    total_time = time.time() - results['start_time']
    final_alive = sum(1 for ball in balls if ball.alive())
    balls_died = results['balls_died']

    LOG.debug('\n=== FINAL RESULTS ===')
    LOG.debug(f'Total time: {total_time:.2f} seconds')
    LOG.debug(f"Frames processed: {results['frame_count']:,}")
    LOG.debug(f'Balls that died: {balls_died}')
    LOG.debug(f'Balls still alive: {final_alive}')

    # Check for any balls that shouldn't be alive
    for ball_index, ball in enumerate(balls):
        if ball.alive():
            LOG.debug(
                f'  Ball {ball_index + 1} still alive at'
                f' position ({ball.rect.x}, {ball.rect.y})'
            )
            LOG.debug(f'    Speed: ({ball.speed.x:.3f}, {ball.speed.y:.3f})')
            LOG.debug(
                f'    Bounce settings:'
                f' top/bottom={ball.bounce_top_bottom},'
                f' left/right={ball.bounce_left_right}'
            )

    # Analyze results
    LOG.debug('\nAnalysis:')
    if balls_died == num_balls:
        LOG.info('  All balls died as expected (no bouncing)')
    elif balls_died > 0:
        LOG.debug(f'  Only {balls_died}/{num_balls} balls died')
    else:
        LOG.debug('  No balls died - bouncing may be enabled incorrectly')

    pygame.quit()

    # Assert that the test completed successfully
    assert balls_died > 0, 'At least some balls should die when bouncing is disabled'

    LOG.info('\nTest completed successfully')


if __name__ == '__main__':
    test_multi_ball_no_bounce()
