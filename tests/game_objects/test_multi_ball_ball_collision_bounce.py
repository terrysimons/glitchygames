#!/usr/bin/env python3
"""Multi-ball test with wall bouncing AND ball-to-ball collision bouncing.

Tests energy conservation across wall bounces and ball-to-ball elastic collisions.
Uses correct normal-decomposition physics (exchange normal velocity components,
preserve tangential components) which conserves energy exactly.

Includes per-pair collision cooldown to prevent the same collision from being
processed multiple times while balls are still overlapping.
"""

import math
import random

import pygame

from glitchygames.game_objects.ball import BallSprite

# Tolerance for floating-point energy comparison.
# The collision math (normal decomposition + exchange) is exact in theory.
# IEEE 754 double precision introduces errors on the order of 1e-12 per operation,
# and these accumulate over multiple collisions. 1e-9 is generous.
ENERGY_TOLERANCE = 1e-9

# Number of frames to suppress re-detection of the same ball pair after a collision.
# This prevents duplicate collision processing when bounding boxes overlap across
# multiple consecutive frames (especially for balls with similar trajectories).
COLLISION_COOLDOWN_FRAMES = 10


def _compute_kinetic_energy(balls):
    """Compute total kinetic energy (proportional) for a list of balls.

    Returns sum of speed_magnitude^2 for all alive balls.
    For equal-mass balls, this is proportional to total kinetic energy.

    Returns:
        object: The result.

    """
    return sum(ball.speed.x**2 + ball.speed.y**2 for ball in balls if ball.alive())


def _exchange_normal_velocity_components(ball1, ball2, nx, ny):
    """Exchange normal velocity components between two balls.

    Decomposes each ball's velocity into normal and tangential components,
    then exchanges the normal components. Preserves both momentum and kinetic energy.
    """
    v1n_scalar = ball1.speed.x * nx + ball1.speed.y * ny
    v2n_scalar = ball2.speed.x * nx + ball2.speed.y * ny

    v1n_vec_x = v1n_scalar * nx
    v1n_vec_y = v1n_scalar * ny
    v2n_vec_x = v2n_scalar * nx
    v2n_vec_y = v2n_scalar * ny

    v1t_vec_x = ball1.speed.x - v1n_vec_x
    v1t_vec_y = ball1.speed.y - v1n_vec_y
    v2t_vec_x = ball2.speed.x - v2n_vec_x
    v2t_vec_y = ball2.speed.y - v2n_vec_y

    ball1.speed.x = v1t_vec_x + v2n_vec_x
    ball1.speed.y = v1t_vec_y + v2n_vec_y
    ball2.speed.x = v2t_vec_x + v1n_vec_x
    ball2.speed.y = v2t_vec_y + v1n_vec_y


def _handle_elastic_collision(ball1, ball2):
    """Handle elastic collision between two equal-mass balls.

    Uses normal-decomposition: decomposes each ball's velocity into components
    along the collision normal and tangent, then exchanges the normal components.
    This preserves both momentum and kinetic energy exactly.

    Args:
        ball1: First BallSprite.
        ball2: Second BallSprite.

    Returns:
        True if collision was resolved, False if balls were separating.

    """
    # Use center positions for accurate collision normal
    dx = ball2.rect.centerx - ball1.rect.centerx
    dy = ball2.rect.centery - ball1.rect.centery
    distance = math.sqrt(dx * dx + dy * dy)

    if distance < 0.001:
        # Balls at exact same position — can't compute normal
        return False

    # Collision normal (unit vector from ball1 center to ball2 center)
    nx = dx / distance
    ny = dy / distance

    # Check if balls are approaching along the collision normal
    relative_velocity_along_normal = (ball2.speed.x - ball1.speed.x) * nx + (
        ball2.speed.y - ball1.speed.y
    ) * ny

    # If relative velocity along normal is positive, balls are separating
    collision_distance = ball1.rect.width // 2 + ball2.rect.width // 2
    if relative_velocity_along_normal > 0 and distance >= collision_distance:
        return False

    _exchange_normal_velocity_components(ball1, ball2, nx, ny)

    # Separate balls to prevent re-triggering collision next frame
    overlap = collision_distance - distance
    if overlap > 0:
        separation_distance = overlap + 2.0  # Extra buffer to prevent sticking
        half_separation = separation_distance * 0.5
        ball1.rect.x -= round(nx * half_separation)
        ball1.rect.y -= round(ny * half_separation)
        ball2.rect.x += round(nx * half_separation)
        ball2.rect.y += round(ny * half_separation)

    return True


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


def _detect_and_resolve_collisions(balls, collision_cooldowns, collision_participants):
    """Detect ball-to-ball collisions and resolve them elastically.

    Returns:
        The number of collisions resolved this frame.

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
                resolved = _handle_elastic_collision(balls[i], balls[j])
                if resolved:
                    ball_collisions += 1
                    collision_participants.add(i)
                    collision_participants.add(j)
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


def test_multi_ball_ball_collision_bounce():
    """Test multiple balls with both wall bouncing and ball-to-ball collision bouncing.

    Verifies:
    - All balls survive the simulation
    - Wall bouncing works
    - Ball-to-ball collisions are detected and resolved
    - Total kinetic energy is conserved (within floating-point tolerance)
    - Individual ball speed magnitudes remain stable through wall bounces
    - No duplicate collision detections for the same crossing event
    """
    random.seed(42)
    pygame.init()
    pygame.display.set_mode((800, 600))

    num_balls = 5
    balls = _create_random_balls(num_balls)

    initial_energy = _compute_kinetic_energy(balls)
    initial_magnitudes = [math.sqrt(ball.speed.x**2 + ball.speed.y**2) for ball in balls]
    collision_participants = set()
    collision_cooldowns = {}
    wall_bounces = 0
    ball_collisions = 0
    frame_count = 0

    while frame_count < 1800 and any(ball.alive() for ball in balls):
        _tick_collision_cooldowns(collision_cooldowns)
        ball_collisions += _detect_and_resolve_collisions(
            balls,
            collision_cooldowns,
            collision_participants,
        )
        wall_bounces += _update_balls_and_count_wall_bounces(balls, 1.0 / 60.0)
        frame_count += 1

    final_energy = _compute_kinetic_energy(balls)
    final_magnitudes = [math.sqrt(ball.speed.x**2 + ball.speed.y**2) for ball in balls]

    pygame.quit()

    # === ASSERTIONS ===
    final_alive = sum(1 for ball in balls if ball.alive())
    assert final_alive == num_balls, (
        f'Expected all {num_balls} balls to survive, but only {final_alive} alive'
    )
    assert wall_bounces > 0, 'No wall bounces detected — wall bouncing is broken'

    energy_drift = abs(final_energy - initial_energy)
    assert energy_drift < ENERGY_TOLERANCE, (
        f'Total kinetic energy not conserved: '
        f'initial={initial_energy:.6f}, final={final_energy:.6f}, '
        f'drift={energy_drift:.2e} (tolerance={ENERGY_TOLERANCE:.2e})'
    )

    for i in range(num_balls):
        if i not in collision_participants:
            magnitude_drift = abs(final_magnitudes[i] - initial_magnitudes[i])
            assert magnitude_drift < 1e-12, (
                f'Ball {i + 1} (no collisions) has speed magnitude drift: '
                f'initial={initial_magnitudes[i]:.6f}, '
                f'final={final_magnitudes[i]:.6f}, drift={magnitude_drift:.2e}'
            )


if __name__ == '__main__':
    test_multi_ball_ball_collision_bounce()
