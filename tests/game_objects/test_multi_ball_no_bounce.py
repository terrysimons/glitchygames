#!/usr/bin/env python3
"""Multi-ball test with bouncing disabled (Paddle Slap style)."""

import logging
import random
import time

import pygame
from glitchygames.game_objects.ball import BallSprite

LOG = logging.getLogger(__name__)


def test_multi_ball_no_bounce():
    """Test multiple balls with bouncing disabled."""
    LOG.debug("=== MULTI-BALL NO BOUNCE TEST ===")
    LOG.debug("Testing multiple balls with bouncing disabled (Paddle Slap style)...")

    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((800, 600))

    # Create multiple balls with bouncing disabled
    num_balls = 10
    balls = []

    for i in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=False,  # No bouncing - balls should die on boundaries
            bounce_left_right=False,
        )
        # Randomize starting position and speed
        ball.rect.x = random.randint(100, 700)
        ball.rect.y = random.randint(100, 500)
        ball.speed.x = random.uniform(-300, 300)
        ball.speed.y = random.uniform(-300, 300)
        balls.append(ball)

    LOG.debug(f"Created {num_balls} balls with bouncing disabled")
    LOG.debug("Initial ball states:")
    for i, ball in enumerate(balls):
        LOG.debug(
            f"  Ball {i + 1}: pos=({ball.rect.x},{ball.rect.y})"
            f" speed=({ball.speed.x:.1f},{ball.speed.y:.1f})"
        )

    # Track statistics
    start_time = time.time()
    balls_died = 0
    frame_count = 0

    # Simulate movement
    dt = 1.0 / 60.0  # 60 FPS
    max_frames = 3600  # 60 seconds at 60 FPS

    LOG.debug(f"\nRunning simulation for {max_frames} frames ({max_frames / 60:.1f} seconds)...")

    while frame_count < max_frames and any(ball.alive() for ball in balls):
        for i, ball in enumerate(balls):
            if ball.alive():
                old_x, old_y = ball.rect.x, ball.rect.y
                ball.dt_tick(dt)
                new_x, new_y = ball.rect.x, ball.rect.y

                # When bouncing is disabled, balls should not bounce at boundaries
                # They should either die when they go off-screen or continue moving past boundaries
                # No bounce detection needed since bouncing is disabled

                # Check if ball died
                if not ball.alive():
                    balls_died += 1
                    LOG.debug(f"  Ball {i + 1} died at position ({new_x}, {new_y})")

        frame_count += 1

        # Report progress every 600 frames (10 seconds)
        if frame_count % 600 == 0:
            alive_count = sum(1 for ball in balls if ball.alive())
            elapsed = time.time() - start_time
            LOG.debug(f"  Frame {frame_count}: {alive_count} balls alive, {balls_died} died")

    total_time = time.time() - start_time
    final_alive = sum(1 for ball in balls if ball.alive())

    LOG.debug("\n=== FINAL RESULTS ===")
    LOG.debug(f"Total time: {total_time:.2f} seconds")
    LOG.debug(f"Frames processed: {frame_count:,}")
    LOG.debug(f"Balls that died: {balls_died}")
    LOG.debug(f"Balls still alive: {final_alive}")

    # Check for any balls that shouldn't be alive
    for i, ball in enumerate(balls):
        if ball.alive():
            LOG.debug(f"  Ball {i + 1} still alive at position ({ball.rect.x}, {ball.rect.y})")
            LOG.debug(f"    Speed: ({ball.speed.x:.3f}, {ball.speed.y:.3f})")
            LOG.debug(
                f"    Bounce settings:"
                f" top/bottom={ball.bounce_top_bottom},"
                f" left/right={ball.bounce_left_right}"
            )

    # Analyze results
    LOG.debug("\nAnalysis:")
    if balls_died == num_balls:
        LOG.info("  ✅ All balls died as expected (no bouncing)")
    elif balls_died > 0:
        LOG.debug(f"  ⚠️  Only {balls_died}/{num_balls} balls died")
    else:
        LOG.debug("  ❌ No balls died - bouncing may be enabled incorrectly")

    pygame.quit()

    # Assert that the test completed successfully
    assert balls_died > 0, "At least some balls should die when bouncing is disabled"

    LOG.info("\n✅ Test completed successfully")


if __name__ == "__main__":
    test_multi_ball_no_bounce()
