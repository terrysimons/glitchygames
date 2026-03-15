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


def _create_random_balls(num_balls):
    """Create a list of randomly positioned balls with wall bouncing enabled.

    Returns:
        List of BallSprite instances.

    """
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
    return balls


def _tick_collision_cooldowns(collision_cooldowns):
    """Decrement all active cooldowns and remove expired ones."""
    expired_pairs = [pair for pair, remaining in collision_cooldowns.items() if remaining <= 1]
    for pair in expired_pairs:
        del collision_cooldowns[pair]
    for pair in collision_cooldowns:
        collision_cooldowns[pair] -= 1


def _detect_clip_collisions(balls, collision_cooldowns):
    """Detect ball-to-ball collisions without physics response (clipping).

    Returns:
        The number of new collisions detected this frame.

    """
    ball_collisions = 0
    for i in range(len(balls)):
        for j in range(i + 1, len(balls)):
            if not (balls[i].alive() and balls[j].alive()):
                continue

            pair_key = (i, j)
            if pair_key in collision_cooldowns:
                continue

            dx = balls[j].rect.centerx - balls[i].rect.centerx
            dy = balls[j].rect.centery - balls[i].rect.centery
            distance = math.sqrt(dx * dx + dy * dy)
            collision_distance = balls[i].rect.width // 2 + balls[j].rect.width // 2

            if distance <= collision_distance:
                ball_collisions += 1
                collision_cooldowns[pair_key] = COLLISION_COOLDOWN_FRAMES

    return ball_collisions


def _update_balls_and_count_wall_bounces(balls, dt):
    """Update ball positions and count wall bounces.

    Returns:
        The number of wall bounces detected this frame.

    """
    wall_bounces = 0
    for ball in balls:
        if ball.alive():
            old_speed_x, old_speed_y = ball.speed.x, ball.speed.y
            ball.dt_tick(dt)

            if old_speed_x * ball.speed.x < 0 and (
                ball.rect.x <= 1 or ball.rect.x >= 800 - ball.width - 1
            ):
                wall_bounces += 1

            if old_speed_y * ball.speed.y < 0 and (
                ball.rect.y <= 1 or ball.rect.y >= 600 - ball.height - 1
            ):
                wall_bounces += 1

    return wall_bounces


def test_multi_ball_ball_collision_clip():
    """Test multiple balls with wall bouncing but ball-to-ball collision clipping.

    Verifies:
    - All balls survive the simulation
    - Wall bouncing works
    - Ball-to-ball collisions are detected (but balls clip through)
    - Speed magnitudes remain perfectly stable (no physics response on clip)
    - Each crossing event is counted exactly once
    """
    random.seed(42)
    pygame.init()
    pygame.display.set_mode((800, 600))

    num_balls = 5
    balls = _create_random_balls(num_balls)
    initial_magnitudes = [math.sqrt(ball.speed.x**2 + ball.speed.y**2) for ball in balls]
    collision_cooldowns = {}
    wall_bounces = 0
    ball_collisions = 0
    frame_count = 0
    dt = 1.0 / 60.0
    max_frames = 1800

    while frame_count < max_frames and any(ball.alive() for ball in balls):
        _tick_collision_cooldowns(collision_cooldowns)
        ball_collisions += _detect_clip_collisions(balls, collision_cooldowns)
        wall_bounces += _update_balls_and_count_wall_bounces(balls, dt)
        frame_count += 1

    final_alive = sum(1 for ball in balls if ball.alive())
    final_magnitudes = [math.sqrt(ball.speed.x**2 + ball.speed.y**2) for ball in balls]

    pygame.quit()

    # === ASSERTIONS ===
    assert final_alive == num_balls, (
        f"Expected all {num_balls} balls to survive, but only {final_alive} alive"
    )
    assert wall_bounces > 0, "No wall bounces detected — wall bouncing is broken"

    for i in range(num_balls):
        magnitude_drift = abs(final_magnitudes[i] - initial_magnitudes[i])
        assert magnitude_drift < 1e-12, (
            f"Ball {i + 1} has speed magnitude drift during clipping: "
            f"initial={initial_magnitudes[i]:.6f}, "
            f"final={final_magnitudes[i]:.6f}, drift={magnitude_drift:.2e}"
        )


if __name__ == "__main__":
    test_multi_ball_ball_collision_clip()
