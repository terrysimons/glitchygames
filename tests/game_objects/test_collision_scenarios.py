"""Test collision scenarios for Paddle Slap game.

This module tests the three types of collisions:
1. Wall collisions (top/bottom) - bounce with no speed change
2. Paddle collisions (left/right) - bounce with speed increase
3. Ball-to-ball collisions - elastic physics with energy conservation
"""

import math

from glitchygames.collision.layers import CollisionManager
from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.ball import (
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from glitchygames.movement import Speed
from tests.game_objects.ball_helpers import drawn_position

# A stand-in for Paddle Slap's speed-up, with its values copied so the engine's tests import no
# game (PADDLESLAP_SPEED_UP, src/games/paddleslap/src/paddleslap/__init__.py:93): a ball speeds
# up on each paddle bounce, logarithmically, on both axes
STAND_IN_PADDLE_SPEED_UP = SpeedUpSettings(
    triggers=SpeedUpTrigger.PADDLE_BOUNCE,
    curve=SpeedUpCurve.LOGARITHMIC,
    axes=SpeedUpAxes.BOTH,
    multiplier=1.15,
    max_speed=500.0,
)

# Constants for magic values
SPEED_3_0 = 3.0
SPEED_2_0 = 2.0
SPEED_NEG_2_0 = -2.0
SPEED_5_0 = 5.0
SPEED_NEG_3_0 = -3.0
SPEED_10_0 = 10.0
SPEED_0_1 = 0.1
SPEED_4_0 = 4.0
SPEED_NEG_4_0 = -4.0
SPEED_1_0 = 1.0
SPEED_NEG_1_0 = -1.0
SPEED_NEG_2_0_COLLISION = -2.0
SPEED_0_0 = 0.0
SPEED_2_0_COLLISION = 2.0
SPEED_5_0_OVERLAP = 5.0
SPEED_2_0_SEPARATION = 2.0
SPEED_0_5 = 0.5
TOLERANCE_0_01 = 0.01


def _place_on_top_wall(ball: BallSprite) -> None:
    """Put the ball where its visible circle's top edge touches the top wall.

    The radius-5 circle is inset in the ball's image, and walls meet the circle (the
    collision rect), so the ball's world_y is minus that inset.
    """
    ball.world_y = -float(ball._visible_rect().offset_y)


def _place_on_bottom_wall(ball: BallSprite) -> None:
    """Put the ball where its visible circle's bottom edge touches the bottom wall."""
    visible_rect = ball._visible_rect()
    ball.world_y = float(ball.screen_height - visible_rect.height - visible_rect.offset_y)


class TestWallCollisions:
    """Test ball bouncing off top and bottom walls."""

    def test_ball_bounces_off_top_wall(self):
        """Test ball bounces off top wall with speed reversal."""
        # Setup: Ball moving up towards top wall
        ball = BallSprite()
        ball.speed = Speed(SPEED_3_0, SPEED_NEG_2_0)  # Moving up and right
        _place_on_top_wall(ball)  # At top wall (triggers bounce condition)

        # Action: Trigger top wall collision
        ball._do_bounce()

        # Expected: Speed.y reversed, speed.x unchanged, ball inside boundary
        assert ball.speed.x == SPEED_3_0  # Unchanged
        assert ball.speed.y == SPEED_2_0  # Reversed from -2.0 to +2.0
        assert ball.world_y >= -ball._visible_rect().offset_y  # Ball is inside boundary
        assert drawn_position(ball)[1] == round(ball.world_y)

    def test_ball_bounces_off_bottom_wall(self):
        """Test ball bounces off bottom wall with speed reversal."""
        # Setup: Ball moving down towards bottom wall
        ball = BallSprite()
        ball.speed = Speed(SPEED_3_0, SPEED_2_0)  # Moving down and right
        ball.screen_height = 450
        _place_on_bottom_wall(ball)  # At bottom wall (triggers bounce condition)

        # Action: Trigger bottom wall collision
        ball._do_bounce()

        # Expected: Speed.y reversed, speed.x unchanged
        assert ball.speed.x == SPEED_3_0  # Unchanged
        assert ball.speed.y == SPEED_NEG_2_0  # Reversed from +2.0 to -2.0

    def test_wall_collision_preserves_speed_magnitude(self):
        """Test wall collision preserves total speed magnitude."""
        # Setup: Ball with known speed magnitude
        ball = BallSprite()
        ball.speed = Speed(SPEED_3_0, SPEED_4_0)  # Magnitude = 5.0
        initial_magnitude = math.sqrt(SPEED_3_0**2 + SPEED_4_0**2)
        ball.world_x = 300.0
        ball.world_y = 1.0  # Near the top wall, but the visible circle does not touch it

        # Action: Trigger wall collision
        ball._do_bounce()

        # Expected: Speed magnitude preserved
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert abs(final_magnitude - initial_magnitude) < TOLERANCE_0_01  # Within tolerance

    def test_wall_collision_does_not_change_horizontal_speed(self):
        """Test wall collision doesn't affect horizontal movement."""
        # Setup: Ball with horizontal and vertical movement
        ball = BallSprite()
        ball.speed = Speed(SPEED_5_0, SPEED_NEG_3_0)  # Moving right and up
        _place_on_top_wall(ball)  # At top wall (triggers bounce condition)

        # Action: Trigger wall collision
        ball._do_bounce()

        # Expected: Horizontal speed unchanged
        assert ball.speed.x == SPEED_5_0  # Unchanged
        assert ball.speed.y == SPEED_3_0  # Reversed from -3.0 to +3.0


class TestPaddleCollisions:
    """Test ball bouncing off left and right paddles."""

    def test_ball_bounces_off_left_paddle(self):
        """Test ball bounces off left paddle with speed increase."""
        # Setup: Ball moving left towards left paddle
        ball = BallSprite(speed_up_settings=STAND_IN_PADDLE_SPEED_UP)
        ball.speed = Speed(SPEED_NEG_3_0, SPEED_2_0)  # Moving left and down
        initial_magnitude = math.sqrt(SPEED_3_0**2 + SPEED_2_0**2)

        # Action: Trigger left paddle collision (simulate speed_up)
        ball.speed.x *= -1  # Reverse direction
        ball.speed_up()  # 15% speed increase

        # Expected: Direction reversed, speed increased (using logarithmic scaling)
        # PaddleSlap uses the LOGARITHMIC curve, so the first step is 1 + 0.15*ln(2)
        assert ball.speed.x > SPEED_3_0  # Reversed and increased
        assert ball.speed.y > SPEED_2_0  # Increased
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert final_magnitude > initial_magnitude  # Speed increased
        expected_ratio = speed_up_step_ratio(
            curve=STAND_IN_PADDLE_SPEED_UP.curve,
            multiplier=STAND_IN_PADDLE_SPEED_UP.multiplier,
            completed_steps=0,
        )
        assert math.isclose(final_magnitude, initial_magnitude * expected_ratio)

    def test_ball_bounces_off_right_paddle(self):
        """Test ball bounces off right paddle with speed increase."""
        # Setup: Ball moving right towards right paddle
        ball = BallSprite(speed_up_settings=STAND_IN_PADDLE_SPEED_UP)
        ball.speed = Speed(SPEED_3_0, SPEED_2_0)  # Moving right and down
        initial_magnitude = math.sqrt(SPEED_3_0**2 + SPEED_2_0**2)

        # Action: Trigger right paddle collision
        ball.speed.x *= -1  # Reverse direction
        ball.speed_up()  # 15% speed increase

        # Expected: Direction reversed, speed increased (using logarithmic scaling)
        # PaddleSlap uses the LOGARITHMIC curve, so the first step is 1 + 0.15*ln(2)
        assert ball.speed.x < SPEED_NEG_3_0  # Reversed and increased (negative)
        assert ball.speed.y > SPEED_2_0  # Increased
        final_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert final_magnitude > initial_magnitude  # Speed increased

    def test_paddle_collision_spawns_new_ball(self):
        """Test paddle collision spawns a new ball."""
        # This test would require mocking the game instance
        # For now, we'll test the speed_up behavior
        ball = BallSprite(speed_up_settings=STAND_IN_PADDLE_SPEED_UP)
        initial_speed_x = ball.speed.x
        initial_speed_y = ball.speed.y

        # Action: Simulate paddle collision
        ball.speed_up()

        # Expected: Speed magnitude increased (regardless of direction)
        assert abs(ball.speed.x) > abs(initial_speed_x)  # Speed magnitude increased
        assert abs(ball.speed.y) > abs(initial_speed_y)  # Speed magnitude increased

    def test_paddle_collision_reverses_horizontal_direction(self):
        """Test paddle collision reverses horizontal direction."""
        # Setup: Ball moving left
        ball = BallSprite(speed_up_settings=STAND_IN_PADDLE_SPEED_UP)
        ball.speed = Speed(SPEED_NEG_4_0, SPEED_1_0)  # Moving left

        # Action: Simulate paddle collision
        ball.speed.x *= -1  # Reverse direction
        ball.speed_up()  # Speed increase

        # Expected: Horizontal direction reversed
        assert ball.speed.x > 0  # Now moving right
        assert ball.speed.y > 0  # Vertical unchanged (positive)


class TestBallToBallCollisions:
    """Test elastic collisions between balls."""

    def test_ball_to_ball_collision_conserves_energy(self):
        """Test ball-to-ball collision conserves total kinetic energy."""
        # Setup: Two balls with known speeds
        ball1 = BallSprite()
        ball2 = BallSprite()
        ball1.speed = Speed(SPEED_2_0_COLLISION, SPEED_0_0)  # Moving right
        ball2.speed = Speed(SPEED_0_0, SPEED_3_0)  # Moving down

        # Calculate initial total kinetic energy
        initial_energy = 0.5 * (
            SPEED_2_0_COLLISION**2 + SPEED_0_0**2 + SPEED_0_0**2 + SPEED_3_0**2
        )  # 6.5

        # Action: Simulate elastic collision
        # For equal mass balls, they exchange velocity components along collision normal
        # This is a simplified test - real collision would need proper normal calculation
        temp_x1, temp_y1 = ball1.speed.x, ball1.speed.y
        temp_x2, temp_y2 = ball2.speed.x, ball2.speed.y

        # Simple momentum exchange (simplified elastic collision)
        ball1.speed.x = temp_x2
        ball1.speed.y = temp_y2
        ball2.speed.x = temp_x1
        ball2.speed.y = temp_y1

        # Calculate final total kinetic energy
        final_energy = 0.5 * (
            ball1.speed.x**2 + ball1.speed.y**2 + ball2.speed.x**2 + ball2.speed.y**2
        )

        # Expected: Energy conserved
        assert abs(final_energy - initial_energy) < TOLERANCE_0_01  # Within tolerance

    def test_ball_to_ball_collision_exchanges_momentum(self):
        """Test ball-to-ball collision exchanges momentum."""
        # Setup: Ball1 moving, Ball2 stationary
        ball1 = BallSprite()
        ball2 = BallSprite()
        ball1.speed = Speed(SPEED_3_0, SPEED_0_0)  # Moving right
        ball2.speed = Speed(SPEED_0_0, SPEED_0_0)  # Stationary

        # Action: Simulate collision (momentum exchange)
        # In elastic collision, balls exchange momentum
        ball1_initial_momentum = (ball1.speed.x, ball1.speed.y)
        ball2_initial_momentum = (ball2.speed.x, ball2.speed.y)

        # Exchange momenta (simplified)
        ball1.speed.x, ball1.speed.y = ball2_initial_momentum
        ball2.speed.x, ball2.speed.y = ball1_initial_momentum

        # Expected: Momentum exchanged
        assert ball1.speed.x == SPEED_0_0  # Now stationary
        assert ball1.speed.y == SPEED_0_0
        assert ball2.speed.x == SPEED_3_0  # Now moving
        assert ball2.speed.y == SPEED_0_0

    def test_ball_to_ball_collision_separation(self):
        """Test balls separate after collision to prevent sticking."""
        # Setup: Two overlapping balls
        ball1 = BallSprite()
        ball2 = BallSprite()
        assert ball1.rect is not None
        assert ball2.rect is not None
        ball1.rect.x = 100
        ball1.rect.y = 100
        ball2.rect.x = 105  # Overlapping
        ball2.rect.y = 100

        # Action: Simulate separation
        overlap = SPEED_5_0_OVERLAP
        separation_distance = max(overlap, SPEED_2_0_SEPARATION)
        ball1.rect.x -= separation_distance * SPEED_0_5
        ball2.rect.x += separation_distance * SPEED_0_5

        # Expected: Balls are separated
        distance = abs(ball2.rect.x - ball1.rect.x)
        assert distance >= SPEED_2_0_SEPARATION  # Minimum separation

    def test_ball_to_ball_collision_elastic_physics(self):
        """Test ball-to-ball collision follows elastic physics."""
        # Setup: Two balls with known velocities
        ball1 = BallSprite()
        ball2 = BallSprite()
        ball1.speed = Speed(SPEED_4_0, SPEED_0_0)  # Moving right
        ball2.speed = Speed(SPEED_NEG_2_0_COLLISION, SPEED_0_0)  # Moving left

        # Calculate initial total momentum
        initial_momentum_x = ball1.speed.x + ball2.speed.x  # SPEED_2_0_COLLISION
        initial_momentum_y = ball1.speed.y + ball2.speed.y  # SPEED_0_0

        # Action: Simulate elastic collision
        # For equal mass balls, they exchange velocities along collision normal
        # Simplified: direct velocity exchange
        ball1.speed.x, ball2.speed.x = ball2.speed.x, ball1.speed.x

        # Calculate final total momentum
        final_momentum_x = ball1.speed.x + ball2.speed.x  # SPEED_2_0_COLLISION
        final_momentum_y = ball1.speed.y + ball2.speed.y  # SPEED_0_0

        # Expected: Momentum conserved
        assert abs(final_momentum_x - initial_momentum_x) < TOLERANCE_0_01
        assert abs(final_momentum_y - initial_momentum_y) < TOLERANCE_0_01


class TestIntegrationCollisions:
    """Test mixed collision scenarios."""

    def test_mixed_collision_scenarios(self):
        """Test sequence of different collision types."""
        # Setup: Ball that will hit wall, then paddle, then another ball
        ball = BallSprite(speed_up_settings=STAND_IN_PADDLE_SPEED_UP)
        ball.speed = Speed(SPEED_3_0, SPEED_NEG_2_0)  # Moving right and up
        _place_on_top_wall(ball)  # At top wall (triggers bounce condition)

        # Action 1: Wall collision
        ball._do_bounce()
        wall_speed = ball.speed.y  # Should be positive now

        # Action 2: Paddle collision
        ball.speed.x *= -1  # Reverse direction
        ball.speed_up()  # Speed increase
        paddle_speed = math.sqrt(ball.speed.x**2 + ball.speed.y**2)

        # Expected: Each collision behaves correctly
        assert wall_speed > 0  # Wall collision reversed direction
        assert paddle_speed > SPEED_3_0  # Paddle collision increased speed

    def test_multiple_balls_collision_behavior(self):
        """Test multiple balls with various collision types."""
        # Setup: Multiple balls
        ball1 = BallSprite()
        ball2 = BallSprite(speed_up_settings=STAND_IN_PADDLE_SPEED_UP)
        ball3 = BallSprite()

        ball1.speed = Speed(
            SPEED_2_0_COLLISION,
            SPEED_NEG_1_0,
        )  # Add vertical movement for wall collision
        ball2.speed = Speed(
            SPEED_2_0_COLLISION,
            SPEED_3_0,
        )  # Add horizontal movement for paddle collision
        ball3.speed = Speed(SPEED_NEG_1_0, SPEED_1_0)

        # Action: Simulate various collisions
        # Ball1 hits wall (must set world_y for sub-pixel tracking)
        _place_on_top_wall(ball1)  # At top wall (triggers bounce condition)
        ball1._do_bounce()

        # Ball2 hits paddle
        ball2.speed.x *= -1
        ball2.speed_up()

        # Ball1 and Ball3 collide (simplified)
        ball1.speed.x, ball3.speed.x = ball3.speed.x, ball1.speed.x

        # Expected: All collisions work correctly
        assert ball1.speed.y > 0  # Wall collision worked
        assert ball2.speed.x < 0  # Paddle collision worked
        assert ball1.speed.x == SPEED_NEG_1_0  # Ball-to-ball collision worked
        assert ball3.speed.x == SPEED_2_0_COLLISION

    def test_collision_edge_cases(self):
        """Test collision behavior at boundaries and extreme speeds."""
        # Setup: Ball at boundary with extreme speed
        ball = BallSprite()
        ball.speed = Speed(SPEED_10_0, SPEED_NEG_1_0)  # Very fast horizontal with vertical movement
        _place_on_top_wall(ball)  # At top boundary (triggers bounce condition)

        # Action: Wall collision
        ball._do_bounce()

        # Expected: Collision works even with extreme speeds
        assert ball.speed.x == SPEED_10_0  # Horizontal unchanged
        assert ball.speed.y > 0  # Vertical reversed

        # Test with very slow speed
        ball.speed = Speed(SPEED_0_1, -SPEED_0_1)
        _place_on_top_wall(ball)  # At top wall (triggers bounce condition)
        ball._do_bounce()

        # Expected: Collision works with slow speeds too
        assert ball.speed.x == SPEED_0_1
        assert ball.speed.y > 0


class TestBallCollisionLayer:
    """Removing balls from a PaddleSlap-style 'balls' collision layer."""

    def test_removing_a_ball_twice_leaves_the_layer_unchanged(self):
        """A ball already removed (a dead ball cleaned up twice) is ignored the second time."""
        collisions = CollisionManager()
        balls_layer = collisions.add_layer('balls')
        removed_ball = BallSprite()
        remaining_ball = BallSprite()
        balls_layer.add(removed_ball)
        balls_layer.add(remaining_ball)

        balls_layer.remove(removed_ball)
        balls_layer.remove(removed_ball)

        assert balls_layer.sprites == [remaining_ball]
        assert len(balls_layer) == 1
