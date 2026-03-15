#!/usr/bin/env python3
"""Base class for multi-ball tests with configurable frame rates.

Provides reusable simulation infrastructure with correct elastic collision physics
using normal-decomposition (exchange normal velocity components, preserve tangential).

Includes per-pair collision cooldown to prevent the same collision from being
processed multiple times while balls are still overlapping.
"""

import logging
import math
import random
import time

import pygame
from glitchygames.game_objects.ball import BallSprite

LOG = logging.getLogger(__name__)

# Number of frames to suppress re-detection of the same ball pair after a collision.
# This prevents duplicate collision processing when bounding boxes overlap across
# multiple consecutive frames (especially for balls with similar trajectories).
COLLISION_COOLDOWN_FRAMES = 10


class MultiBallTestBase:
    """Base class for multi-ball collision tests."""

    def __init__(
        self, test_name, num_balls=5, *, enable_ball_collisions=False, enable_ball_bouncing=False
    ):
        """Initialize multi-ball test base with configuration parameters."""
        self.test_name = test_name
        self.num_balls = num_balls
        self.enable_ball_collisions = enable_ball_collisions
        self.enable_ball_bouncing = enable_ball_bouncing
        self.balls = []
        self.trajectory_data = []
        self.speed_magnitude_samples = []
        self.initial_energy = 0.0
        # Per-pair cooldown: maps (i, j) tuple to remaining cooldown frames
        self.collision_cooldowns = {}

    def setup_balls(self):
        """Set up balls for the test."""
        self.balls = []
        self.trajectory_data = [[] for _ in range(self.num_balls)]
        self.speed_magnitude_samples = [[] for _ in range(self.num_balls)]
        self.collision_cooldowns = {}

        for _ball_index in range(self.num_balls):
            ball = BallSprite(
                bounce_top_bottom=True,
                bounce_left_right=True,
            )
            ball.rect.x = random.randint(50, 750)
            ball.rect.y = random.randint(50, 550)
            ball.speed.x = random.uniform(-150, 150)
            ball.speed.y = random.uniform(-150, 150)
            self.balls.append(ball)

        self.initial_energy = self._compute_total_energy()

    def _compute_total_energy(self):
        """Compute total kinetic energy (proportional) for all alive balls.

        Returns sum of speed_magnitude^2. For equal-mass balls, this is
        proportional to total kinetic energy.

        Returns:
            object: The result.

        """
        return sum(ball.speed.x**2 + ball.speed.y**2 for ball in self.balls if ball.alive())

    def print_initial_state(self):
        """Print initial ball states."""
        LOG.debug(f"Created {self.num_balls} balls")
        LOG.debug("Initial ball states:")
        for i, ball in enumerate(self.balls):
            magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
            LOG.debug(
                f"  Ball {i + 1}: pos=({ball.rect.x},{ball.rect.y}) "
                f"speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) mag={magnitude:.1f}"
            )

    def _tick_cooldowns(self):
        """Decrement all active cooldowns and remove expired ones."""
        expired_pairs = []
        for pair, remaining in self.collision_cooldowns.items():
            if remaining <= 1:
                expired_pairs.append(pair)
            else:
                self.collision_cooldowns[pair] = remaining - 1
        for pair in expired_pairs:
            del self.collision_cooldowns[pair]

    def handle_ball_collisions(self):
        """Handle ball-to-ball collisions using center-distance detection.

        Uses per-pair cooldown to prevent the same collision from being
        processed on consecutive frames while bounding boxes still overlap.

        Returns:
            object: The result.

        """
        ball_collisions = 0

        for i in range(len(self.balls)):
            for j in range(i + 1, len(self.balls)):
                if not (self.balls[i].alive() and self.balls[j].alive()):
                    continue

                # Skip pairs still in cooldown
                pair_key = (i, j)
                if pair_key in self.collision_cooldowns:
                    continue

                # Use center-based distance detection (not AABB)
                dx = self.balls[j].rect.centerx - self.balls[i].rect.centerx
                dy = self.balls[j].rect.centery - self.balls[i].rect.centery
                distance = math.sqrt(dx * dx + dy * dy)
                collision_distance = self.balls[i].rect.width // 2 + self.balls[j].rect.width // 2

                if distance <= collision_distance:
                    if self.enable_ball_bouncing:
                        resolved = self._handle_elastic_collision(
                            self.balls[i], self.balls[j], distance, dx, dy
                        )
                        if resolved:
                            ball_collisions += 1
                            self.collision_cooldowns[pair_key] = COLLISION_COOLDOWN_FRAMES
                    else:
                        # Collision detected but no bounce — balls clip through
                        ball_collisions += 1
                        self.collision_cooldowns[pair_key] = COLLISION_COOLDOWN_FRAMES

        return ball_collisions

    def _handle_elastic_collision(self, ball1, ball2, distance, dx, dy):
        """Handle elastic collision between two equal-mass balls.

        Uses normal-decomposition: decomposes each ball's velocity into
        components along the collision normal and tangent, then exchanges
        the normal components. This preserves both momentum and kinetic
        energy exactly.

        Args:
            ball1: First BallSprite.
            ball2: Second BallSprite.
            distance: Pre-computed distance between centers.
            dx: X difference (ball2.centerx - ball1.centerx).
            dy: Y difference (ball2.centery - ball1.centery).

        Returns:
            True if collision was resolved, False if balls were separating.

        """
        if distance < 0.001:
            return False

        # Collision normal (unit vector from ball1 center to ball2 center)
        nx = dx / distance
        ny = dy / distance

        # Check if balls are approaching along the collision normal
        relative_velocity_along_normal = (ball2.speed.x - ball1.speed.x) * nx + (
            ball2.speed.y - ball1.speed.y
        ) * ny

        collision_distance = ball1.rect.width // 2 + ball2.rect.width // 2
        if relative_velocity_along_normal > 0 and distance >= collision_distance:
            return False

        # Decompose velocities into normal and tangential components
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

        # Exchange normal components, preserve tangential components
        ball1.speed.x = v1t_vec_x + v2n_vec_x
        ball1.speed.y = v1t_vec_y + v2n_vec_y
        ball2.speed.x = v2t_vec_x + v1n_vec_x
        ball2.speed.y = v2t_vec_y + v1n_vec_y

        # Separate balls to prevent re-triggering collision next frame
        overlap = collision_distance - distance
        if overlap > 0:
            separation_distance = overlap + 2.0
            half_separation = separation_distance * 0.5
            ball1.rect.x -= round(nx * half_separation)
            ball1.rect.y -= round(ny * half_separation)
            ball2.rect.x += round(nx * half_separation)
            ball2.rect.y += round(ny * half_separation)

        return True

    def update_balls(self, dt, frame_count):
        """Update ball positions and track data.

        Returns:
            object: The result.

        """
        wall_bounces = 0

        for i, ball in enumerate(self.balls):
            if ball.alive():
                old_speed_x, old_speed_y = ball.speed.x, ball.speed.y

                ball.dt_tick(dt)

                # Detect wall bounces by speed direction flip at boundaries
                if old_speed_x * ball.speed.x < 0 and (
                    ball.rect.x <= 1 or ball.rect.x >= 800 - ball.width - 1
                ):
                    wall_bounces += 1

                if old_speed_y * ball.speed.y < 0 and (
                    ball.rect.y <= 1 or ball.rect.y >= 600 - ball.height - 1
                ):
                    wall_bounces += 1

                # Track trajectory
                self.trajectory_data[i].append((ball.rect.x, ball.rect.y))

                # Sample speed magnitude every 60 frames (1 second at 60 FPS)
                if frame_count % 60 == 0:
                    current_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
                    self.speed_magnitude_samples[i].append(current_magnitude)

        return wall_bounces

    def run_test(self, fps, duration_seconds):
        """Run the test with specified FPS and duration.

        Returns:
            object: The result.

        """
        LOG.debug(f"=== {self.test_name} ===")
        LOG.debug(f"Testing at {fps} FPS for {duration_seconds} seconds...")

        # Initialize pygame
        pygame.init()
        pygame.display.set_mode((800, 600))

        # Set up balls
        self.setup_balls()
        self.print_initial_state()

        # Calculate test parameters
        if fps == float("inf"):
            dt = 0.0
            max_frames = int(60 * duration_seconds)
        else:
            dt = 1.0 / fps
            max_frames = int(fps * duration_seconds)

        LOG.debug(f"\nRunning simulation for {max_frames} frames ({duration_seconds} seconds)...")

        # Track statistics
        start_time = time.time()
        total_wall_bounces = 0
        total_ball_collisions = 0
        frame_count = 0

        # Run simulation
        while frame_count < max_frames and any(ball.alive() for ball in self.balls):
            # Tick cooldowns at start of each frame
            self._tick_cooldowns()

            if self.enable_ball_collisions:
                ball_collisions = self.handle_ball_collisions()
                total_ball_collisions += ball_collisions

            if fps == float("inf"):
                wall_bounces = self.update_balls(0.001, frame_count)
            else:
                wall_bounces = self.update_balls(dt, frame_count)
            total_wall_bounces += wall_bounces

            frame_count += 1

            if frame_count % 300 == 0:
                alive_count = sum(1 for ball in self.balls if ball.alive())
                LOG.debug(
                    f"  Frame {frame_count}: {alive_count} balls alive, "
                    f"{total_wall_bounces} wall bounces, "
                    f"{total_ball_collisions} ball collisions"
                )

        total_time = time.time() - start_time
        final_alive = sum(1 for ball in self.balls if ball.alive())

        self.print_results(
            total_time,
            frame_count,
            final_alive,
            total_wall_bounces,
            total_ball_collisions,
        )

        pygame.quit()

        return final_alive, total_wall_bounces, total_ball_collisions

    def print_results(self, total_time, frame_count, final_alive, wall_bounces, ball_collisions):
        """Print test results."""
        LOG.debug("\n=== FINAL RESULTS ===")
        LOG.debug(f"Total time: {total_time:.2f} seconds")
        LOG.debug(f"Frames processed: {frame_count:,}")
        LOG.debug(f"Balls still alive: {final_alive}")
        LOG.debug(f"Wall bounces: {wall_bounces}")
        LOG.debug(f"Ball-to-ball collisions: {ball_collisions}")

        # Energy conservation check
        final_energy = self._compute_total_energy()
        energy_drift = abs(final_energy - self.initial_energy)
        LOG.debug("\n=== ENERGY ANALYSIS ===")
        LOG.debug(f"  Initial energy: {self.initial_energy:.6f}")
        LOG.debug(f"  Final energy:   {final_energy:.6f}")
        LOG.debug(f"  Drift:          {energy_drift:.2e}")

        # Per-ball speed magnitude analysis
        LOG.debug("\n=== SPEED MAGNITUDE ANALYSIS ===")
        for i, ball in enumerate(self.balls):
            if ball.alive() and self.speed_magnitude_samples[i]:
                magnitudes = self.speed_magnitude_samples[i]
                min_mag = min(magnitudes)
                max_mag = max(magnitudes)
                drift = max_mag - min_mag

                LOG.debug(
                    f"Ball {i + 1}: magnitude range [{min_mag:.3f}, {max_mag:.3f}], "
                    f"drift={drift:.6f}"
                )

        # Overall analysis
        LOG.info("\n=== OVERALL ANALYSIS ===")
        if final_alive == self.num_balls:
            LOG.info(f"  All {self.num_balls} balls survived")
        else:
            LOG.info(f"  Only {final_alive}/{self.num_balls} balls survived")

        if wall_bounces > 0:
            LOG.info(f"  Wall bouncing working ({wall_bounces} bounces)")

        if self.enable_ball_collisions and ball_collisions > 0:
            if self.enable_ball_bouncing:
                LOG.info(
                    f"  Ball-to-ball collision bouncing working ({ball_collisions} collisions)"
                )
            else:
                LOG.info(
                    f"  Ball-to-ball collision clipping working ({ball_collisions} collisions)"
                )
