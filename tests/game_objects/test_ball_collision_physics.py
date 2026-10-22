#!/usr/bin/env python3
"""Test comprehensive ball collision physics scenarios."""

import logging
import math

import pytest

from glitchygames.collision.layers import CollisionManager
from glitchygames.examples.paddleslap import Game
from glitchygames.game_objects.ball import BallSprite
from glitchygames.movement import Speed
from tests.game_objects.ball_helpers import drawn_position, place_ball_center

LOG = logging.getLogger(__name__)


class TestBallCollisionPhysics:
    """Test comprehensive ball collision physics scenarios."""

    def _create_ball(self, x, y, speed_x, speed_y):
        """Create a ball with specified position and speed.

        Returns:
            object: The result.

        """
        ball = BallSprite(
            collision_sound=None,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        assert ball.rect is not None
        ball.rect.x = x
        ball.rect.y = y
        ball.speed = Speed(speed_x, speed_y)
        ball.collision_cooldowns = {}  # type: ignore[unresolved-attribute]
        return ball

    def _simulate_collision(self, ball1, ball2):
        """Simulate collision between two balls using the actual game physics.

        Returns:
            object: The result.

        """
        # Calculate distance between ball centers
        dx = ball2.rect.centerx - ball1.rect.centerx
        dy = ball2.rect.centery - ball1.rect.centery
        distance = math.sqrt(dx * dx + dy * dy)

        # Skip if balls are too far apart or at exact same position
        collision_distance = 20.0  # 10px radius each ball
        if distance > collision_distance or distance < 0.001:
            LOG.debug(
                f'DEBUG: No collision - distance={distance:.2f},'
                f' collision_distance={collision_distance}',
            )
            return None

        # Calculate collision normal
        nx = dx / distance
        ny = dy / distance

        # Calculate relative velocity
        dvx = ball2.speed.x - ball1.speed.x
        dvy = ball2.speed.y - ball1.speed.y

        # Calculate relative velocity along collision normal
        dvn = dvx * nx + dvy * ny

        # For overlapping balls, always allow collision regardless of dvn
        # This ensures that balls that are touching/overlapping will always exchange momentum

        # Calculate velocity components along collision normal
        v1n = ball1.speed.x * nx + ball1.speed.y * ny
        v2n = ball2.speed.x * nx + ball2.speed.y * ny

        # Exchange normal components
        ball1.speed.x = ball1.speed.x - v1n * nx + v2n * nx
        ball1.speed.y = ball1.speed.y - v1n * ny + v2n * ny
        ball2.speed.x = ball2.speed.x - v2n * nx + v1n * nx
        ball2.speed.y = ball2.speed.y - v2n * ny + v1n * ny

        return True  # Collision occurred

    def test_horizontal_vs_stationary(self):
        """Test horizontal ball hitting stationary ball."""
        ball1 = self._create_ball(100, 100, 100.0, 0.0)  # Moving right
        ball2 = self._create_ball(115, 100, 0.0, 0.0)  # Stationary (closer)

        self._simulate_collision(ball1, ball2)

        # Ball1 should stop, ball2 should move right
        assert ball1.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(100.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(0.0, abs=1e-5)

    def test_vertical_vs_stationary(self):
        """Test vertical ball hitting stationary ball."""
        ball1 = self._create_ball(100, 100, 0.0, 100.0)  # Moving down
        ball2 = self._create_ball(100, 115, 0.0, 0.0)  # Stationary (closer)

        self._simulate_collision(ball1, ball2)

        # Ball1 should stop, ball2 should move down
        assert ball1.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(100.0, abs=1e-5)

    def test_diagonal_vs_stationary(self):
        """Test diagonal ball hitting stationary ball."""
        ball1 = self._create_ball(100, 100, 50.0, 50.0)  # Moving diagonally
        ball2 = self._create_ball(110, 110, 0.0, 0.0)  # Stationary (closer)

        self._simulate_collision(ball1, ball2)

        # Ball1 should stop, ball2 should move diagonally
        assert ball1.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(50.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(50.0, abs=1e-5)

    def test_horizontal_vs_horizontal_same_direction(self):
        """Test horizontal ball hitting horizontal ball moving same direction."""
        ball1 = self._create_ball(100, 100, 100.0, 0.0)  # Moving right fast
        ball2 = self._create_ball(115, 100, 50.0, 0.0)  # Moving right slow (closer)

        self._simulate_collision(ball1, ball2)

        # Should exchange horizontal speeds
        assert ball1.speed.x == pytest.approx(50.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(100.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(0.0, abs=1e-5)

    def test_horizontal_vs_horizontal_opposite_direction(self):
        """Test horizontal ball hitting horizontal ball moving opposite direction."""
        ball1 = self._create_ball(100, 100, 100.0, 0.0)  # Moving right
        ball2 = self._create_ball(115, 100, -50.0, 0.0)  # Moving left

        self._simulate_collision(ball1, ball2)

        # Should exchange horizontal speeds
        assert ball1.speed.x == pytest.approx(-50.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(100.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(0.0, abs=1e-5)

    def test_vertical_vs_vertical_same_direction(self):
        """Test vertical ball hitting vertical ball moving same direction."""
        ball1 = self._create_ball(100, 100, 0.0, 100.0)  # Moving down fast
        ball2 = self._create_ball(100, 115, 0.0, 50.0)  # Moving down slow

        self._simulate_collision(ball1, ball2)

        # Should exchange vertical speeds
        assert ball1.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(50.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(100.0, abs=1e-5)

    def test_vertical_vs_vertical_opposite_direction(self):
        """Test vertical ball hitting vertical ball moving opposite direction."""
        ball1 = self._create_ball(100, 100, 0.0, 100.0)  # Moving down
        ball2 = self._create_ball(100, 115, 0.0, -50.0)  # Moving up

        self._simulate_collision(ball1, ball2)

        # Should exchange vertical speeds
        assert ball1.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(-50.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(0.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(100.0, abs=1e-5)

    def test_diagonal_vs_horizontal_from_right(self):
        """Test diagonal ball hitting horizontal ball from the right."""
        ball1 = self._create_ball(100, 100, 50.0, 50.0)  # Moving diagonally right-down
        ball2 = self._create_ball(110, 100, -50.0, 0.0)  # Moving horizontally left (toward ball1)

        self._simulate_collision(ball1, ball2)

        # Ball1 should get horizontal component from ball2, keep vertical
        # Ball2 should get horizontal component from ball1, keep vertical (0)
        assert ball1.speed.x == pytest.approx(-50.0, abs=1e-5)  # Got ball2's horizontal (left)
        assert ball1.speed.y == pytest.approx(50.0, abs=1e-5)  # Kept own vertical
        assert ball2.speed.x == pytest.approx(50.0, abs=1e-5)  # Got ball1's horizontal (right)
        assert ball2.speed.y == pytest.approx(0.0, abs=1e-5)  # Kept own vertical (0)

    def test_diagonal_vs_horizontal_from_left(self):
        """Test diagonal ball hitting horizontal ball from the left."""
        ball1 = self._create_ball(100, 100, -50.0, 50.0)  # Moving diagonally left-down
        ball2 = self._create_ball(90, 100, 50.0, 0.0)  # Moving horizontally right (toward ball1)

        self._simulate_collision(ball1, ball2)

        # Should exchange horizontal components, preserve vertical
        assert ball1.speed.x == pytest.approx(50.0, abs=1e-5)  # Got ball2's horizontal (right)
        assert ball1.speed.y == pytest.approx(50.0, abs=1e-5)  # Kept own vertical
        assert ball2.speed.x == pytest.approx(-50.0, abs=1e-5)  # Got ball1's horizontal (left)
        assert ball2.speed.y == pytest.approx(0.0, abs=1e-5)  # Kept own vertical (0)

    def test_diagonal_vs_vertical_from_above(self):
        """Test diagonal ball hitting vertical ball from above."""
        ball1 = self._create_ball(100, 100, 50.0, 50.0)  # Moving diagonally right-down
        ball2 = self._create_ball(100, 110, 0.0, -50.0)  # Moving vertically up (toward ball1)

        self._simulate_collision(ball1, ball2)

        # Should exchange vertical components, preserve horizontal
        assert ball1.speed.x == pytest.approx(50.0, abs=1e-5)  # Kept own horizontal
        assert ball1.speed.y == pytest.approx(-50.0, abs=1e-5)  # Got ball2's vertical (up)
        assert ball2.speed.x == pytest.approx(0.0, abs=1e-5)  # Kept own horizontal (0)
        assert ball2.speed.y == pytest.approx(50.0, abs=1e-5)  # Got ball1's vertical (down)

    def test_diagonal_vs_vertical_from_below(self):
        """Test diagonal ball hitting vertical ball from below."""
        ball1 = self._create_ball(100, 100, 50.0, -50.0)  # Moving diagonally right-up
        ball2 = self._create_ball(100, 90, 0.0, 50.0)  # Moving vertically down (toward ball1)

        self._simulate_collision(ball1, ball2)

        # Should exchange vertical components, preserve horizontal
        assert ball1.speed.x == pytest.approx(50.0, abs=1e-5)  # Kept own horizontal
        assert ball1.speed.y == pytest.approx(50.0, abs=1e-5)  # Got ball2's vertical (down)
        assert ball2.speed.x == pytest.approx(0.0, abs=1e-5)  # Kept own horizontal (0)
        assert ball2.speed.y == pytest.approx(-50.0, abs=1e-5)  # Got ball1's vertical (up)

    def test_diagonal_vs_diagonal_same_direction(self):
        """Test diagonal ball hitting diagonal ball moving same direction."""
        ball1 = self._create_ball(100, 100, 50.0, 50.0)  # Moving diagonally right-down
        ball2 = self._create_ball(
            110,
            110,
            -25.0,
            -25.0,
        )  # Moving diagonally left-up (toward ball1)

        self._simulate_collision(ball1, ball2)

        # Should exchange velocities completely
        assert ball1.speed.x == pytest.approx(-25.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(-25.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(50.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(50.0, abs=1e-5)

    def test_diagonal_vs_diagonal_opposite_direction(self):
        """Test diagonal ball hitting diagonal ball moving opposite direction."""
        ball1 = self._create_ball(100, 100, 50.0, 50.0)  # Moving diagonally down-right
        ball2 = self._create_ball(
            110,
            110,
            -25.0,
            -25.0,
        )  # Moving diagonally up-left (toward ball1)

        self._simulate_collision(ball1, ball2)

        # Should exchange velocities completely
        assert ball1.speed.x == pytest.approx(-25.0, abs=1e-5)
        assert ball1.speed.y == pytest.approx(-25.0, abs=1e-5)
        assert ball2.speed.x == pytest.approx(50.0, abs=1e-5)
        assert ball2.speed.y == pytest.approx(50.0, abs=1e-5)

    def test_energy_conservation(self):
        """Test that energy is conserved in all collision scenarios."""
        scenarios = [
            # Format: ball1_speed, ball2_speed, description
            ((100.0, 0.0), (0.0, 0.0), 'horizontal vs stationary'),
            ((0.0, 100.0), (0.0, 0.0), 'vertical vs stationary'),
            ((50.0, 50.0), (0.0, 0.0), 'diagonal vs stationary'),
            ((100.0, 0.0), (50.0, 0.0), 'horizontal vs horizontal'),
            ((0.0, 100.0), (0.0, 50.0), 'vertical vs vertical'),
            ((50.0, 50.0), (25.0, 25.0), 'diagonal vs diagonal'),
        ]

        for ball1_speed, ball2_speed, description in scenarios:
            ball1 = self._create_ball(100, 100, ball1_speed[0], ball1_speed[1])
            ball2 = self._create_ball(120, 100, ball2_speed[0], ball2_speed[1])

            # Calculate initial energy
            initial_energy = (
                ball1_speed[0] ** 2
                + ball1_speed[1] ** 2
                + ball2_speed[0] ** 2
                + ball2_speed[1] ** 2
            )

            self._simulate_collision(ball1, ball2)

            # Calculate final energy
            final_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

            assert initial_energy == pytest.approx(final_energy, abs=1e-5), (
                f'Energy not conserved in {description}'
            )

    def test_momentum_conservation(self):
        """Test that momentum is conserved in all collision scenarios."""
        scenarios = [
            # Format: ball1_speed, ball2_speed, description
            ((100.0, 0.0), (0.0, 0.0), 'horizontal vs stationary'),
            ((0.0, 100.0), (0.0, 0.0), 'vertical vs stationary'),
            ((50.0, 50.0), (0.0, 0.0), 'diagonal vs stationary'),
        ]

        for ball1_speed, ball2_speed, description in scenarios:
            ball1 = self._create_ball(100, 100, ball1_speed[0], ball1_speed[1])
            ball2 = self._create_ball(120, 100, ball2_speed[0], ball2_speed[1])

            # Calculate initial momentum
            initial_momentum_x = ball1_speed[0] + ball2_speed[0]
            initial_momentum_y = ball1_speed[1] + ball2_speed[1]

            self._simulate_collision(ball1, ball2)

            # Calculate final momentum
            final_momentum_x = ball1.speed.x + ball2.speed.x
            final_momentum_y = ball1.speed.y + ball2.speed.y

            assert initial_momentum_x == pytest.approx(final_momentum_x, abs=1e-5), (
                f'X momentum not conserved in {description}'
            )
            assert initial_momentum_y == pytest.approx(final_momentum_y, abs=1e-5), (
                f'Y momentum not conserved in {description}'
            )

    def test_same_direction_collision_slower_ball_should_speed_up(self):
        """Test that when two balls move in the same direction, the slower ball speeds up."""
        # Create two balls moving in the same direction (right)
        ball1 = self._create_ball(100, 100, 100.0, 0.0)  # Slower ball moving right
        ball2 = self._create_ball(120, 100, 150.0, 0.0)  # Faster ball moving right (just touching)

        # Record initial speeds
        ball1_initial_speed = ball1.speed.x
        ball2_initial_speed = ball2.speed.x

        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        assert collision_occurred, 'Collision should have occurred'

        # The slower ball (ball1) should have gained speed
        assert ball1.speed.x > ball1_initial_speed, (
            f'Slower ball should have gained speed: {ball1.speed.x} > {ball1_initial_speed}'
        )

        # The faster ball (ball2) should have lost speed
        assert ball2.speed.x < ball2_initial_speed, (
            f'Faster ball should have lost speed: {ball2.speed.x} < {ball2_initial_speed}'
        )

    def test_same_direction_collision_energy_transfer(self):
        """Test that energy is properly transferred in same-direction collisions."""
        # Create two balls moving in the same direction
        ball1 = self._create_ball(100, 100, 50.0, 0.0)  # Slower ball
        ball2 = self._create_ball(120, 100, 200.0, 0.0)  # Faster ball (just touching)

        # Calculate initial total energy
        initial_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        assert collision_occurred, 'Collision should have occurred'

        # Calculate final total energy
        final_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

        # Energy should be conserved (within floating point precision)
        assert final_energy == pytest.approx(initial_energy, abs=1e-5), (
            f'Energy should be conserved: {final_energy} ~= {initial_energy}'
        )

    def test_zero_x_velocity_ball_should_get_horizontal_momentum(self):
        """Test that a ball with zero X velocity gets horizontal momentum when hit diagonally."""
        # Create ball1 moving vertically (x=0), ball2 moving diagonally
        ball1 = self._create_ball(100, 100, 0.0, 100.0)  # Moving up only
        ball2 = self._create_ball(115, 100, 100.0, -50.0)  # Moving right and down (overlapping)

        # Record initial speeds
        ball1_initial_x = ball1.speed.x
        ball1_initial_y = ball1.speed.y

        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        assert collision_occurred, 'Collision should have occurred'

        # Ball1 should have gained horizontal velocity
        assert ball1.speed.x != pytest.approx(0.0, abs=0.1), (
            f'Ball with zero X velocity should gain horizontal momentum: {ball1.speed.x}'
        )

        # Ball1's Y velocity should remain unchanged for horizontal collision
        assert ball1.speed.y == ball1_initial_y, (
            f"Ball's Y velocity should remain unchanged for horizontal"
            f' collision: {ball1.speed.y} = {ball1_initial_y}'
        )

    def test_zero_x_velocity_ball_energy_transfer(self):
        """Test that energy is properly transferred to a ball with zero X velocity."""
        # Create ball1 with zero X velocity, ball2 with horizontal velocity
        ball1 = self._create_ball(100, 100, 0.0, 50.0)  # Moving up only
        ball2 = self._create_ball(120, 100, 150.0, 0.0)  # Moving right only (just touching)

        # Calculate initial total energy
        initial_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        assert collision_occurred, 'Collision should have occurred'

        # Calculate final total energy
        final_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

        # Energy should be conserved
        assert final_energy == pytest.approx(initial_energy, abs=1e-5), (
            f'Energy should be conserved: {final_energy} ~= {initial_energy}'
        )

        # Ball1 should now have horizontal velocity
        assert ball1.speed.x != pytest.approx(0.0, abs=0.1), (
            f'Ball should have gained horizontal velocity: {ball1.speed.x}'
        )

    def test_diagonal_to_horizontal_energy_transfer(self):
        """Test that diagonal energy is properly transferred to horizontal motion."""
        # Create ball1 moving horizontally, ball2 moving diagonally
        ball1 = self._create_ball(100, 100, 100.0, 0.0)  # Moving right only
        ball2 = self._create_ball(120, 100, 50.0, -100.0)  # Moving right and down (just touching)

        # Record initial speeds
        ball1_initial_x = ball1.speed.x
        ball1_initial_y = ball1.speed.y

        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        assert collision_occurred, 'Collision should have occurred'

        # For horizontal collision, Y velocity should remain unchanged
        assert ball1.speed.y == ball1_initial_y, (
            f'Horizontal collision should not change Y velocity:'
            f' {ball1.speed.y} = {ball1_initial_y}'
        )

        # Ball1's X velocity should change due to collision
        assert ball1.speed.x != ball1_initial_x, (
            f"Horizontal ball's X velocity should change: {ball1.speed.x} != {ball1_initial_x}"
        )


class TestBallCollisionEnergyTransfer:
    """Test energy transfer in ball collision scenarios."""

    def _create_ball(self, x, y, speed_x, speed_y):
        """Create a ball with specified position and speed.

        Returns:
            object: The result.

        """
        ball = BallSprite(
            collision_sound=None,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        assert ball.rect is not None
        ball.rect.x = x
        ball.rect.y = y
        ball.speed = Speed(speed_x, speed_y)
        ball.collision_cooldowns = {}  # type: ignore[unresolved-attribute]
        return ball

    def _simulate_collision(self, ball1, ball2):
        """Simulate collision between two balls using the actual game physics.

        Returns:
            object: The result.

        """
        dx = ball2.rect.centerx - ball1.rect.centerx
        dy = ball2.rect.centery - ball1.rect.centery
        distance = math.sqrt(dx * dx + dy * dy)

        collision_distance = 20.0
        if distance > collision_distance or distance < 0.001:
            return None

        nx = dx / distance
        ny = dy / distance

        v1n = ball1.speed.x * nx + ball1.speed.y * ny
        v2n = ball2.speed.x * nx + ball2.speed.y * ny

        ball1.speed.x = ball1.speed.x - v1n * nx + v2n * nx
        ball1.speed.y = ball1.speed.y - v1n * ny + v2n * ny
        ball2.speed.x = ball2.speed.x - v2n * nx + v1n * nx
        ball2.speed.y = ball2.speed.y - v2n * ny + v1n * ny

        return True

    def test_vertical_to_diagonal_energy_transfer(self):
        """Test that vertical energy is properly transferred to diagonal motion."""
        # Create ball1 moving vertically, ball2 moving diagonally
        ball1 = self._create_ball(100, 100, 0.0, 100.0)  # Moving up only
        ball2 = self._create_ball(120, 100, 100.0, -50.0)  # Moving right and down (just touching)

        # Record initial speeds
        ball1_initial_x = ball1.speed.x
        ball1_initial_y = ball1.speed.y

        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        assert collision_occurred, 'Collision should have occurred'

        # Ball1 should have gained X velocity from the diagonal ball
        assert ball1.speed.x != ball1_initial_x, (
            f'Vertical ball should gain X velocity from diagonal:'
            f' {ball1.speed.x} != {ball1_initial_x}'
        )

        # For horizontal collision, Y velocity should remain unchanged
        assert ball1.speed.y == ball1_initial_y, (
            f'Horizontal collision should not change Y velocity:'
            f' {ball1.speed.y} = {ball1_initial_y}'
        )


# ---------------------------------------------------------------------------
# Full-circle collision sweep against the real PaddleSlap collision pipeline.
#
# The tests above re-implement the collision math inside the test, so they
# cannot catch bugs in the game's own code. These tests drive real BallSprites
# through BallSprite.dt_tick() and Game._handle_ball_collisions() (collision
# manager broad phase -> circle check -> elastic exchange -> separation ->
# cooldown) exactly as the game loop does each frame.
#
# Expected behavior: for two equal-mass balls whose centers are aimed at the
# same point at the same time, the contact normal is parallel to their relative
# velocity, so a perfectly elastic collision swaps their velocities exactly.
# A moving ball hitting a stationary ball is the special case where the mover
# stops dead and the target leaves with the mover's original velocity.
# ---------------------------------------------------------------------------

SWEEP_ANGLES_DEGREES = tuple(range(0, 360, 15))
STATIONARY_TARGET_MOVER_SPEEDS = (60.0, 180.0, 400.0)
MOVING_PAIR_SPEEDS = ((100.0, 100.0), (100.0, 300.0), (300.0, 100.0), (300.0, 300.0))
SWEEP_FRAME_DT = 1 / 60
SWEEP_MEETING_POINT = (400.0, 240.0)
SWEEP_MINIMUM_TIME_TO_MEET = 0.3  # seconds
SWEEP_MINIMUM_STARTING_GAP = 40.0  # pixels between centers; collision distance is 10
SWEEP_FRAMES_AFTER_COLLISION = 30
# How far inside the collision distance the centres are on the first frame they could touch
SWEEP_CONTACT_INSET = 2.0  # pixels
SWEEP_BALL_SIZE = 20
# Ball centers live on integer pixels, so the collision normal the game computes can
# be a few degrees off the ideal one. Allow 10% of the relative speed (plus 1 px/s)
# of velocity error for that rounding; real bugs produce errors far larger than this.
# The visible circles are only 10 px across, so this holds because the balls are first
# sampled SWEEP_CONTACT_INSET inside the collision distance (8 px apart): at 3 px or
# less apart, a pixel of rounding turns the normal by 10 degrees or more.
SWEEP_VELOCITY_TOLERANCE_FRACTION = 0.1
SWEEP_CONSERVATION_TOLERANCE = 1e-6


def _velocity_from_angle(angle_degrees: float, speed: float) -> tuple[float, float]:
    """Return the (x, y) velocity for a heading in degrees (0 = right, 90 = down)."""
    angle_radians = math.radians(angle_degrees)
    return (speed * math.cos(angle_radians), speed * math.sin(angle_radians))


class _CollisionSweepHarness:
    """Runs two real BallSprites through the real PaddleSlap per-frame collision path.

    It runs the ball-ball physics step (_handle_ball_collisions) only, not the playability
    rule PaddleSlap's update() applies afterwards (_keep_collided_balls_playable), so the
    sweeps check exact equal-mass elastic physics: swapped velocities, a mover that stops
    dead, and conserved momentum and energy.
    """

    def __init__(
        self,
        first_velocity: tuple[float, float],
        second_velocity: tuple[float, float],
        *,
        meet_on_frame: bool = False,
    ) -> None:
        self.game = Game.__new__(Game)
        self.game.collisions = CollisionManager()
        self.game.collisions.add_layer('balls')
        self.game._ball_collision_cooldowns = {}

        self.first_ball = self._create_ball(first_velocity)
        self.second_ball = self._create_ball(second_velocity)
        # The game's own threshold: the visible circles' radii, not the image size
        _, _, _, self.collision_distance = Game._calculate_ball_distance(
            self.first_ball, self.second_ball
        )

        # The centres reach the meeting point a fraction of a frame after a whole frame,
        # chosen so that on that whole frame they are SWEEP_CONTACT_INSET inside the
        # collision distance, still on the line of their relative velocity. The game
        # computes the contact normal from whole-pixel centres (up to about a pixel off
        # each way), so the normal's error shrinks as the contact distance grows. Without
        # the phase, a pair could first be sampled a few pixels apart (or, meeting exactly
        # on a frame, centred on the same point, where no normal exists and the game skips
        # the pair) and the frames either side are a full step away.
        relative_speed = math.dist(first_velocity, second_velocity)
        minimum_time_to_meet = max(
            SWEEP_MINIMUM_TIME_TO_MEET,
            SWEEP_MINIMUM_STARTING_GAP / relative_speed,
        )
        # meet_on_frame puts the meeting exactly on a frame (the pass-through pin below)
        contact_distance = 0.0 if meet_on_frame else self.collision_distance - SWEEP_CONTACT_INSET
        time_to_meet = (
            math.ceil(minimum_time_to_meet / SWEEP_FRAME_DT) * SWEEP_FRAME_DT
            + contact_distance / relative_speed
        )
        self._aim_at_meeting_point(ball=self.first_ball, time_to_meet=time_to_meet)
        self._aim_at_meeting_point(ball=self.second_ball, time_to_meet=time_to_meet)

        self.maximum_frames_to_collision = round(time_to_meet / SWEEP_FRAME_DT) + 30
        # Balls whose rect the last collision step wrote directly (see step())
        self.rects_written_by_collisions: list[str] = []

    def _create_ball(self, velocity: tuple[float, float]) -> BallSprite:
        """Create a ball with the given velocity, registered in the 'balls' collision layer.

        Returns:
            BallSprite: The ball (placed later by _aim_at_meeting_point).

        """
        ball = BallSprite(
            width=SWEEP_BALL_SIZE,
            height=SWEEP_BALL_SIZE,
            collision_sound=None,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed = Speed(velocity[0], velocity[1])
        self.game.collisions.get_layer('balls').add(ball)
        return ball

    @staticmethod
    def _aim_at_meeting_point(*, ball: BallSprite, time_to_meet: float) -> None:
        """Place a ball so its visible center reaches SWEEP_MEETING_POINT after time_to_meet."""
        place_ball_center(
            ball,
            center_x=SWEEP_MEETING_POINT[0] - ball.speed.x * time_to_meet,
            center_y=SWEEP_MEETING_POINT[1] - ball.speed.y * time_to_meet,
        )

    def center_distance(self) -> float:
        """Return the distance between ball centers, as the game measures it (integer rects)."""
        _, _, distance, _ = Game._calculate_ball_distance(self.first_ball, self.second_ball)
        return distance

    def world_center_distance(self) -> float:
        """Return the distance between ball centers using sub-pixel world positions."""
        return math.dist(
            (self.first_ball.world_x, self.first_ball.world_y),
            (self.second_ball.world_x, self.second_ball.world_y),
        )

    def velocities(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Return both balls' current velocities."""
        return (
            (self.first_ball.speed.x, self.first_ball.speed.y),
            (self.second_ball.speed.x, self.second_ball.speed.y),
        )

    def step(self) -> bool:
        """Advance one frame exactly as the game loop does.

        Returns:
            bool: True if a collision changed either ball's velocity this frame.

        """
        self.first_ball.dt_tick(SWEEP_FRAME_DT)
        self.second_ball.dt_tick(SWEEP_FRAME_DT)
        velocities_before = self.velocities()
        balls = (('first', self.first_ball), ('second', self.second_ball))
        rects_before = {label: ball.rect.topleft for label, ball in balls}
        self.game._handle_ball_collisions()
        # Collision handling must move the world positions only: the engine rebuilds rect
        # from world_x/world_y before each render, so a rect written here would be undone
        self.rects_written_by_collisions = [
            f'{label} ball rect {rects_before[label]} -> {ball.rect.topleft}, '
            f'world=({ball.world_x:.1f}, {ball.world_y:.1f})'
            for label, ball in balls
            if ball.rect.topleft != rects_before[label]
        ]
        # Then the engine positions the world sprites, as the frame loop does after dt_tick
        for _label, ball in balls:
            drawn_position(ball)
        return self.velocities() != velocities_before


def _assert_velocities_swapped(
    harness: _CollisionSweepHarness,
    first_velocity: tuple[float, float],
    second_velocity: tuple[float, float],
    case_description: str,
) -> None:
    """Assert an equal-mass, head-on elastic collision swapped the balls' velocities."""
    (first_after, second_after) = harness.velocities()
    tolerance = SWEEP_VELOCITY_TOLERANCE_FRACTION * math.dist(first_velocity, second_velocity) + 1.0
    first_error = math.dist(first_after, second_velocity)
    second_error = math.dist(second_after, first_velocity)
    assert first_error <= tolerance and second_error <= tolerance, (
        f'Velocities did not swap ({case_description}). '
        f'Expected first=({second_velocity[0]:.1f}, {second_velocity[1]:.1f}) '
        f'second=({first_velocity[0]:.1f}, {first_velocity[1]:.1f}); '
        f'actual first=({first_after[0]:.1f}, {first_after[1]:.1f}) '
        f'second=({second_after[0]:.1f}, {second_after[1]:.1f}); '
        f'errors {first_error:.1f}, {second_error:.1f} (tolerance {tolerance:.1f})'
    )


def _assert_momentum_and_energy_conserved(
    harness: _CollisionSweepHarness,
    first_velocity: tuple[float, float],
    second_velocity: tuple[float, float],
    case_description: str,
) -> None:
    """Assert the collision conserved total momentum and kinetic energy."""
    (first_after, second_after) = harness.velocities()
    momentum_before = (
        first_velocity[0] + second_velocity[0],
        first_velocity[1] + second_velocity[1],
    )
    momentum_after = (first_after[0] + second_after[0], first_after[1] + second_after[1])
    assert math.dist(momentum_before, momentum_after) <= SWEEP_CONSERVATION_TOLERANCE * max(
        1.0, math.hypot(*momentum_before)
    ), f'Momentum not conserved ({case_description}): {momentum_before} -> {momentum_after}'
    energy_before = math.hypot(*first_velocity) ** 2 + math.hypot(*second_velocity) ** 2
    energy_after = math.hypot(*first_after) ** 2 + math.hypot(*second_after) ** 2
    assert energy_after == pytest.approx(energy_before, rel=SWEEP_CONSERVATION_TOLERANCE), (
        f'Kinetic energy not conserved ({case_description}): '
        f'{energy_before:.1f} -> {energy_after:.1f}'
    )


def _assert_rects_in_sync_after_collision(
    harness: _CollisionSweepHarness,
    case_description: str,
) -> None:
    """Assert collision handling moved only world positions, never a ball's rect.

    The engine rebuilds rect from world_x/world_y before each render, so a rect written by
    collision handling would silently undo the overlap separation.
    """
    out_of_sync_balls = harness.rects_written_by_collisions
    assert not out_of_sync_balls, (
        f'Collision handling wrote rect directly ({case_description}): '
        f'{"; ".join(out_of_sync_balls)}. The engine rebuilds rect from world_x/world_y '
        f'before rendering, undoing the separation (distance '
        f'{harness.center_distance():.1f} now, collision distance '
        f'{harness.collision_distance})'
    )


def _assert_balls_separate_and_stay_apart(
    harness: _CollisionSweepHarness,
    case_description: str,
) -> None:
    """Assert no further collisions and a never-shrinking true (sub-pixel) gap."""
    previous_world_distance = harness.world_center_distance()
    for frames_since_collision in range(1, SWEEP_FRAMES_AFTER_COLLISION + 1):
        collided_again = harness.step()
        world_distance = harness.world_center_distance()
        assert not collided_again, (
            f'Balls collided again {frames_since_collision} frame(s) after the first '
            f'collision ({case_description}); distance {harness.center_distance():.1f}'
        )
        assert world_distance >= previous_world_distance, (
            f'Balls moved back toward each other {frames_since_collision} frame(s) after '
            f'colliding ({case_description}): world distance '
            f'{previous_world_distance:.2f} -> {world_distance:.2f}'
        )
        previous_world_distance = world_distance
    final_distance = harness.center_distance()
    assert final_distance > harness.collision_distance, (
        f'Balls still overlapping {SWEEP_FRAMES_AFTER_COLLISION} frames after colliding '
        f'({case_description}): distance {final_distance:.1f}'
    )


def _run_collision_sweep_case(
    first_velocity: tuple[float, float],
    second_velocity: tuple[float, float],
    *,
    meet_on_frame: bool = False,
) -> None:
    """Collide two balls aimed at the same point and verify the result against physics."""
    harness = _CollisionSweepHarness(first_velocity, second_velocity, meet_on_frame=meet_on_frame)
    case_description = (
        f'first ball velocity=({first_velocity[0]:.1f}, {first_velocity[1]:.1f}), '
        f'second ball velocity=({second_velocity[0]:.1f}, {second_velocity[1]:.1f})'
    )

    collided = any(harness.step() for _ in range(harness.maximum_frames_to_collision))
    assert collided, (
        f'Balls aimed at the same point never collided ({case_description}); '
        f'final distance {harness.center_distance():.1f}'
    )

    _assert_velocities_swapped(harness, first_velocity, second_velocity, case_description)
    _assert_momentum_and_energy_conserved(
        harness, first_velocity, second_velocity, case_description
    )
    _assert_rects_in_sync_after_collision(harness, case_description)
    _assert_balls_separate_and_stay_apart(harness, case_description)


class TestBallCollisionSweepStationaryTarget:
    """A moving ball hits a stationary ball from every direction around the circle."""

    @pytest.mark.parametrize('mover_speed', STATIONARY_TARGET_MOVER_SPEEDS, ids='{:.0f}px/s'.format)
    @pytest.mark.parametrize('approach_angle', SWEEP_ANGLES_DEGREES, ids='from{:03d}deg'.format)
    def test_mover_stops_and_target_takes_its_velocity(self, approach_angle, mover_speed):
        """The mover stops dead and the target leaves with the mover's velocity."""
        _run_collision_sweep_case(
            first_velocity=_velocity_from_angle(approach_angle, mover_speed),
            second_velocity=(0.0, 0.0),
        )


def _moving_pair_cases():
    """Every pair of headings for both balls, at several speed combinations.

    Returns:
        list: pytest params of (first_angle, first_speed, second_angle, second_speed).

    """
    cases = []
    for first_speed, second_speed in MOVING_PAIR_SPEEDS:
        for first_angle in SWEEP_ANGLES_DEGREES:
            for second_angle in SWEEP_ANGLES_DEGREES:
                if first_angle == second_angle and first_speed == second_speed:
                    continue  # identical velocities never approach each other
                cases.append(
                    pytest.param(
                        first_angle,
                        first_speed,
                        second_angle,
                        second_speed,
                        id=(
                            f'first{first_angle:03d}deg@{first_speed:.0f}'
                            f'-second{second_angle:03d}deg@{second_speed:.0f}'
                        ),
                    ),
                )
    return cases


class TestBallCollisionSweepMovingPair:
    """Two moving balls collide at every combination of headings."""

    @pytest.mark.parametrize(
        ('first_angle', 'first_speed', 'second_angle', 'second_speed'),
        _moving_pair_cases(),
    )
    def test_balls_swap_velocities(self, first_angle, first_speed, second_angle, second_speed):
        """Two equal-mass balls aimed at the same point swap velocities."""
        _run_collision_sweep_case(
            first_velocity=_velocity_from_angle(first_angle, first_speed),
            second_velocity=_velocity_from_angle(second_angle, second_speed),
        )


# Head-on pairs closing at 10 px a frame (300 px/s each at 60 FPS), the visible circles' whole
# collision distance (10). Aimed to meet exactly on a frame, the frame before has them just
# touching (distance 10, no AABB overlap), the meeting frame has their centres on the same
# pixel (no contact normal, skipped) and the frame after has them touching on the far side:
# they pass through each other untouched.
FRAME_ALIGNED_HEAD_ON_ANGLES_DEGREES = (0, 15, 45, 90)
FRAME_ALIGNED_HEAD_ON_SPEED = 300.0


class TestBallCollisionSweepFrameAlignedMeeting:
    """Balls whose centres would coincide on a frame must still collide (they do not)."""

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'Production bug: PaddleSlap ball-ball collision is sampled once per frame '
            '(Game._handle_ball_collisions, no swept test), so balls closing at the collision '
            'distance (10 px, the visible radius-5 circles) or more per frame can skip from '
            'touching to coincident centres (skipped: no normal) to touching on the far side, '
            'and pass through each other'
        ),
    )
    @pytest.mark.parametrize(
        'first_angle', FRAME_ALIGNED_HEAD_ON_ANGLES_DEGREES, ids='first{:03d}deg'.format
    )
    def test_head_on_balls_meeting_on_a_frame_collide(self, first_angle):
        """Two head-on balls aimed to meet exactly on a frame swap velocities."""
        _run_collision_sweep_case(
            first_velocity=_velocity_from_angle(first_angle, FRAME_ALIGNED_HEAD_ON_SPEED),
            second_velocity=_velocity_from_angle(first_angle + 180, FRAME_ALIGNED_HEAD_ON_SPEED),
            meet_on_frame=True,
        )
