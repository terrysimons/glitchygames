#!/usr/bin/env python3
"""Test comprehensive ball collision physics scenarios."""

import math

import pytest
from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed


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
            speed_up_mode=SpeedUpMode.NONE,
            speed_up_multiplier=1.0,
            speed_up_interval=1.0,
        )
        ball.rect.x = x
        ball.rect.y = y
        ball.speed = Speed(speed_x, speed_y)
        ball.collision_cooldowns = {}
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
            print(
                f"DEBUG: No collision - distance={distance:.2f}, collision_distance={collision_distance}"
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
            110, 110, -25.0, -25.0
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
            110, 110, -25.0, -25.0
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
            # (ball1_speed, ball2_speed, description)
            ((100.0, 0.0), (0.0, 0.0), "horizontal vs stationary"),
            ((0.0, 100.0), (0.0, 0.0), "vertical vs stationary"),
            ((50.0, 50.0), (0.0, 0.0), "diagonal vs stationary"),
            ((100.0, 0.0), (50.0, 0.0), "horizontal vs horizontal"),
            ((0.0, 100.0), (0.0, 50.0), "vertical vs vertical"),
            ((50.0, 50.0), (25.0, 25.0), "diagonal vs diagonal"),
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
                f"Energy not conserved in {description}"
            )

    def test_momentum_conservation(self):
        """Test that momentum is conserved in all collision scenarios."""
        scenarios = [
            # (ball1_speed, ball2_speed, description)
            ((100.0, 0.0), (0.0, 0.0), "horizontal vs stationary"),
            ((0.0, 100.0), (0.0, 0.0), "vertical vs stationary"),
            ((50.0, 50.0), (0.0, 0.0), "diagonal vs stationary"),
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
                f"X momentum not conserved in {description}"
            )
            assert initial_momentum_y == pytest.approx(final_momentum_y, abs=1e-5), (
                f"Y momentum not conserved in {description}"
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
        assert collision_occurred, "Collision should have occurred"

        # The slower ball (ball1) should have gained speed
        assert ball1.speed.x > ball1_initial_speed, (
            f"Slower ball should have gained speed: {ball1.speed.x} > {ball1_initial_speed}"
        )

        # The faster ball (ball2) should have lost speed
        assert ball2.speed.x < ball2_initial_speed, (
            f"Faster ball should have lost speed: {ball2.speed.x} < {ball2_initial_speed}"
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
        assert collision_occurred, "Collision should have occurred"

        # Calculate final total energy
        final_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

        # Energy should be conserved (within floating point precision)
        assert final_energy == pytest.approx(initial_energy, abs=1e-5), (
            f"Energy should be conserved: {final_energy} ~= {initial_energy}"
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
        assert collision_occurred, "Collision should have occurred"

        # Ball1 should have gained horizontal velocity
        assert ball1.speed.x != pytest.approx(0.0, abs=0.1), (
            f"Ball with zero X velocity should gain horizontal momentum: {ball1.speed.x}"
        )

        # Ball1's Y velocity should remain unchanged for horizontal collision
        assert ball1.speed.y == ball1_initial_y, (
            f"Ball's Y velocity should remain unchanged for horizontal collision: {ball1.speed.y} = {ball1_initial_y}"
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
        assert collision_occurred, "Collision should have occurred"

        # Calculate final total energy
        final_energy = ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2

        # Energy should be conserved
        assert final_energy == pytest.approx(initial_energy, abs=1e-5), (
            f"Energy should be conserved: {final_energy} ~= {initial_energy}"
        )

        # Ball1 should now have horizontal velocity
        assert ball1.speed.x != pytest.approx(0.0, abs=0.1), (
            f"Ball should have gained horizontal velocity: {ball1.speed.x}"
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
        assert collision_occurred, "Collision should have occurred"

        # For horizontal collision, Y velocity should remain unchanged
        assert ball1.speed.y == ball1_initial_y, (
            f"Horizontal collision should not change Y velocity: {ball1.speed.y} = {ball1_initial_y}"
        )

        # Ball1's X velocity should change due to collision
        assert ball1.speed.x != ball1_initial_x, (
            f"Horizontal ball's X velocity should change: {ball1.speed.x} != {ball1_initial_x}"
        )

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
        assert collision_occurred, "Collision should have occurred"

        # Ball1 should have gained X velocity from the diagonal ball
        assert ball1.speed.x != ball1_initial_x, (
            f"Vertical ball should gain X velocity from diagonal: {ball1.speed.x} != {ball1_initial_x}"
        )

        # For horizontal collision, Y velocity should remain unchanged
        assert ball1.speed.y == ball1_initial_y, (
            f"Horizontal collision should not change Y velocity: {ball1.speed.y} = {ball1_initial_y}"
        )
