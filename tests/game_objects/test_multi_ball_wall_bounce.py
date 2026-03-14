#!/usr/bin/env python3
"""Multi-ball test with wall bouncing enabled (no ball-to-ball collisions)."""

import logging
import math
import random
import time

import pygame
from glitchygames.game_objects.ball import BallSprite

LOG = logging.getLogger(__name__)


def test_multi_ball_wall_bounce():
    """Test multiple balls with wall bouncing enabled."""
    LOG.debug("=== MULTI-BALL WALL BOUNCE TEST ===")
    LOG.debug("Testing multiple balls with wall bouncing enabled...")

    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((800, 600))

    # Create multiple balls with wall bouncing enabled
    num_balls = 5
    balls = []

    for i in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=True,  # Enable wall bouncing
            bounce_left_right=True,
        )
        # Randomize starting position and speed
        ball.rect.x = random.randint(50, 750)
        ball.rect.y = random.randint(50, 550)
        ball.speed.x = random.uniform(-200, 200)
        ball.speed.y = random.uniform(-200, 200)
        balls.append(ball)

    LOG.debug(f"Created {num_balls} balls with wall bouncing enabled")
    LOG.debug("Initial ball states:")
    for i, ball in enumerate(balls):
        magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        LOG.debug(
            f"  Ball {i + 1}: pos=({ball.rect.x},{ball.rect.y}) speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) mag={magnitude:.1f}"
        )

    # Track statistics
    start_time = time.time()
    total_bounces = 0
    x_bounces = 0
    y_bounces = 0
    frame_count = 0

    # Track trajectory data
    trajectory_data = [[] for _ in range(num_balls)]
    speed_magnitude_samples = [[] for _ in range(num_balls)]

    # Simulate movement
    dt = 1.0 / 60.0  # 60 FPS
    max_frames = 1800  # 30 seconds at 60 FPS

    LOG.debug(f"\nRunning simulation for {max_frames} frames ({max_frames / 60:.1f} seconds)...")

    while frame_count < max_frames and any(ball.alive() for ball in balls):
        for i, ball in enumerate(balls):
            if ball.alive():
                old_x, old_y = ball.rect.x, ball.rect.y
                old_speed_x, old_speed_y = ball.speed.x, ball.speed.y

                ball.dt_tick(dt)

                new_x, new_y = ball.rect.x, ball.rect.y
                new_speed_x, new_speed_y = ball.speed.x, ball.speed.y

                # Track trajectory
                trajectory_data[i].append((new_x, new_y))

                # Check for wall bounces
                if old_x != new_x and (new_x <= 1 or new_x >= 800 - ball.width - 1):
                    x_bounces += 1
                    total_bounces += 1
                    LOG.debug(f"  Ball {i + 1} X wall bounce at x={new_x}")

                if old_y != new_y and (new_y <= 1 or new_y >= 600 - ball.height - 1):
                    y_bounces += 1
                    total_bounces += 1
                    LOG.debug(f"  Ball {i + 1} Y wall bounce at y={new_y}")

                # Sample speed magnitude every 60 frames (1 second)
                if frame_count % 60 == 0:
                    current_magnitude = math.sqrt(new_speed_x**2 + new_speed_y**2)
                    speed_magnitude_samples[i].append(current_magnitude)

        frame_count += 1

        # Report progress every 300 frames (5 seconds)
        if frame_count % 300 == 0:
            alive_count = sum(1 for ball in balls if ball.alive())
            elapsed = time.time() - start_time
            LOG.debug(
                f"  Frame {frame_count}: {alive_count} balls alive, {total_bounces} total bounces"
            )

    total_time = time.time() - start_time
    final_alive = sum(1 for ball in balls if ball.alive())

    LOG.debug("\n=== FINAL RESULTS ===")
    LOG.debug(f"Total time: {total_time:.2f} seconds")
    LOG.debug(f"Frames processed: {frame_count:,}")
    LOG.debug(f"Balls still alive: {final_alive}")
    LOG.debug(f"Total wall bounces: {total_bounces}")
    LOG.debug(f"X wall bounces: {x_bounces}")
    LOG.debug(f"Y wall bounces: {y_bounces}")

    # Analyze trajectory data
    LOG.debug("\n=== TRAJECTORY ANALYSIS ===")
    for i, ball in enumerate(balls):
        if ball.alive() and trajectory_data[i]:
            positions = trajectory_data[i]
            x_positions = [pos[0] for pos in positions]
            y_positions = [pos[1] for pos in positions]

            # Check position bounds
            min_x, max_x = min(x_positions), max(x_positions)
            min_y, max_y = min(y_positions), max(y_positions)

            LOG.debug(f"Ball {i + 1} trajectory:")
            LOG.debug(f"  Position bounds: X[{min_x:.1f}-{max_x:.1f}] Y[{min_y:.1f}-{max_y:.1f}]")
            LOG.debug(f"  Final position: ({ball.rect.x}, {ball.rect.y})")
            LOG.debug(f"  Final speed: ({ball.speed.x:.3f}, {ball.speed.y:.3f})")
            LOG.debug(f"  Final magnitude: {math.sqrt(ball.speed.x**2 + ball.speed.y**2):.3f}")

            # Check for trajectory issues
            x_drift = max_x - min_x
            y_drift = max_y - min_y

            if x_drift > 50 or y_drift > 50:
                LOG.debug("  ⚠️  Significant position drift detected")
            else:
                LOG.info("  ✅ Position is stable")

            # Check speed magnitude stability
            if speed_magnitude_samples[i]:
                magnitudes = speed_magnitude_samples[i]
                min_mag = min(magnitudes)
                max_mag = max(magnitudes)
                drift = max_mag - min_mag

                LOG.debug(
                    f"  Speed magnitude: min={min_mag:.3f}, max={max_mag:.3f}, drift={drift:.6f}"
                )

                if drift < 0.01:
                    LOG.info("  ✅ Speed magnitude is stable")
                else:
                    LOG.debug("  ⚠️  Speed magnitude drift detected")

    # Overall analysis
    LOG.debug("\n=== OVERALL ANALYSIS ===")
    if final_alive == num_balls:
        LOG.info("  ✅ All balls survived with wall bouncing enabled")
    else:
        LOG.debug(f"  ⚠️  Only {final_alive}/{num_balls} balls survived")

    if total_bounces > 0:
        LOG.info(f"  ✅ Wall bouncing is working ({total_bounces} total bounces)")
    else:
        LOG.debug("  ❌ No wall bounces detected - bouncing may be disabled")

    pygame.quit()

    # Assert that the test completed successfully
    assert final_alive > 0, "At least one ball should survive"
    assert total_bounces > 0, "Wall bouncing should be working"

    LOG.info("\n✅ Test completed successfully")


if __name__ == "__main__":
    test_multi_ball_wall_bounce()
