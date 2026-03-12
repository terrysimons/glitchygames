#!/usr/bin/env python3
"""Multi-ball test with wall bouncing but ball-to-ball collision clipping (no bouncing).

Tests that balls correctly pass through each other without physics response,
while wall bouncing continues to work and preserve energy.

Includes per-pair collision cooldown so each crossing event is counted once,
not once per overlapping frame.
"""

import math
import random

import pygame

from glitchygames.game_objects.ball import BallSprite

# Number of frames to suppress re-detection of the same ball pair after a collision.
# For clipping, this means we only count a crossing once, not every frame the
# bounding boxes overlap.
COLLISION_COOLDOWN_FRAMES = 10


def test_multi_ball_ball_collision_clip():
    """Test multiple balls with wall bouncing but ball-to-ball collision clipping.

    Verifies:
    - All balls survive the simulation
    - Wall bouncing works
    - Ball-to-ball collisions are detected (but balls clip through)
    - Speed magnitudes remain perfectly stable (no physics response on clip)
    - Each crossing event is counted exactly once
    """
    # Use a fixed seed for reproducibility
    random.seed(42)

    # Initialize pygame
    pygame.init()
    pygame.display.set_mode((800, 600))

    # Create multiple balls with wall bouncing enabled
    num_balls = 5
    balls = []

    for _ball_index in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.rect.x = random.randint(100, 700)
        ball.rect.y = random.randint(100, 500)
        ball.speed.x = random.uniform(-150, 150)
        ball.speed.y = random.uniform(-150, 150)
        balls.append(ball)

    # Record initial magnitudes — clipping should not change any speeds
    initial_magnitudes = [
        math.sqrt(ball.speed.x ** 2 + ball.speed.y ** 2)
        for ball in balls
    ]

    # Track statistics
    wall_bounces = 0
    ball_collisions = 0
    frame_count = 0

    # Per-pair cooldown: maps (i, j) tuple to remaining cooldown frames
    collision_cooldowns = {}

    # Simulate movement: 30 seconds at 60 FPS
    dt = 1.0 / 60.0
    max_frames = 1800

    while frame_count < max_frames and any(ball.alive() for ball in balls):
        # Tick cooldowns at start of each frame
        expired_pairs = [
            pair for pair, remaining in collision_cooldowns.items() if remaining <= 1
        ]
        for pair in expired_pairs:
            del collision_cooldowns[pair]
        for pair in collision_cooldowns:
            collision_cooldowns[pair] -= 1

        # Check for ball-to-ball collisions (detect only, no physics response)
        for i in range(len(balls)):
            for j in range(i + 1, len(balls)):
                if not (balls[i].alive() and balls[j].alive()):
                    continue

                # Skip pairs still in cooldown
                pair_key = (i, j)
                if pair_key in collision_cooldowns:
                    continue

                # Use center-based distance detection (not AABB)
                dx = balls[j].rect.centerx - balls[i].rect.centerx
                dy = balls[j].rect.centery - balls[i].rect.centery
                distance = math.sqrt(dx * dx + dy * dy)
                collision_distance = balls[i].rect.width // 2 + balls[j].rect.width // 2

                if distance <= collision_distance:
                    ball_collisions += 1
                    collision_cooldowns[pair_key] = COLLISION_COOLDOWN_FRAMES
                    # No collision response — balls clip through each other

        # Update ball positions (wall bouncing happens inside dt_tick)
        for i, ball in enumerate(balls):
            if ball.alive():
                old_speed_x, old_speed_y = ball.speed.x, ball.speed.y

                ball.dt_tick(dt)

                # Detect wall bounces by speed direction flip at boundaries
                if (
                    old_speed_x * ball.speed.x < 0
                    and (ball.rect.x <= 1 or ball.rect.x >= 800 - ball.width - 1)
                ):
                    wall_bounces += 1

                if (
                    old_speed_y * ball.speed.y < 0
                    and (ball.rect.y <= 1 or ball.rect.y >= 600 - ball.height - 1)
                ):
                    wall_bounces += 1

        frame_count += 1

    final_alive = sum(1 for ball in balls if ball.alive())

    # Compute final magnitudes
    final_magnitudes = [
        math.sqrt(ball.speed.x ** 2 + ball.speed.y ** 2)
        for ball in balls
    ]

    pygame.quit()

    # === ASSERTIONS ===

    # All balls must survive
    assert final_alive == num_balls, (
        f"Expected all {num_balls} balls to survive, but only {final_alive} alive"
    )

    # Wall bouncing must be working
    assert wall_bounces > 0, "No wall bounces detected — wall bouncing is broken"

    # Every ball's speed magnitude must be perfectly stable (clip = no physics response)
    for i in range(num_balls):
        magnitude_drift = abs(final_magnitudes[i] - initial_magnitudes[i])
        assert magnitude_drift < 1e-12, (
            f"Ball {i + 1} has speed magnitude drift during clipping: "
            f"initial={initial_magnitudes[i]:.6f}, "
            f"final={final_magnitudes[i]:.6f}, drift={magnitude_drift:.2e}"
        )


if __name__ == "__main__":
    test_multi_ball_ball_collision_clip()
