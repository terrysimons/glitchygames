"""PaddleSlap's own ball-ball collisions: the fine check, the playability rule and the cooldown.

Moved from the engine's tests (tests/collision/test_ball_paddle_collision.py and
tests/game_objects/test_collision_scenarios.py): their subject is the game's ``Game``
(``_calculate_ball_distance``, ``_handle_ball_collisions``, ``_keep_ball_playable`` and
``_on_ball_ball_collision``), not the engine's ``BallSprite``.
"""

import math

import pygame
import pytest

from glitchygames.collision.layers import CollisionManager
from glitchygames.display_mode import set_display_mode
from glitchygames.game_objects import BallSprite
from glitchygames.movement import Speed
from paddleslap import Game
from tests.game_objects.ball_helpers import VISIBLE_SIZE, drawn_position, make_ball

# The cooldown test's closing speeds, named as in tests/game_objects/test_collision_scenarios.py
SPEED_3_0 = 3.0
SPEED_NEG_3_0 = -3.0


@pytest.fixture(autouse=True)
def real_display():
    """Give BallSprite a real display to convert its image against."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 600))


class TestBallPairDistance:
    """PaddleSlap's ball-ball fine check uses the same visible circles as the broad phase."""

    def test_collision_distance_is_the_sum_of_visible_radii(self):
        """Two real balls collide when their radius-5 circles touch (10 px apart)."""
        first_ball = make_ball(world_x=100, world_y=100)
        second_ball = make_ball(world_x=108, world_y=106)

        delta_x, delta_y, distance, collision_distance = Game._calculate_ball_distance(
            first_ball, second_ball
        )

        assert (delta_x, delta_y) == (8.0, 6.0)
        assert distance == pytest.approx(10.0)
        assert collision_distance == VISIBLE_SIZE


def make_ball_pair_game(*balls):
    """Build a bare PaddleSlap game whose 'balls' layer holds the given balls.

    Returns:
        Game: A game with just enough state for its ball-ball collision methods.

    """
    game = Game.__new__(Game)
    game.collisions = CollisionManager()
    game.collisions.add_layer('balls')
    for ball in balls:
        game.collisions.get_layer('balls').add(ball)
    game._ball_collision_cooldowns = {}
    game._ball_collision_pairs = []
    return game


def angle_from_horizontal_degrees(ball):
    """Return the angle of the ball's velocity from horizontal, 0-90 degrees.

    Returns:
        float: The angle in degrees.

    """
    return math.degrees(math.atan2(abs(ball.speed.y), abs(ball.speed.x)))


class TestBallPairPlayability:
    """After a ball-ball collision, PaddleSlap keeps each ball moving like a serve.

    Equal-mass elastic collisions conserve momentum and energy but can leave a ball almost
    stopped (a head-on hit on a slower ball) or moving almost vertically or horizontally;
    in Pong such a ball never reaches a paddle or slides along a wall.
    """

    def test_head_on_hit_on_a_still_ball_leaves_neither_ball_stalled_or_flat(self):
        """The mover would stop dead and the target leave flat: both get serve-like motion."""
        # Visible centres 9 px apart (< 10): the circles overlap.
        mover = make_ball(world_x=100, world_y=100, speed_x=250.0, speed_y=0.0)
        target = make_ball(world_x=109, world_y=100, speed_x=0.0, speed_y=0.0)
        game = make_ball_pair_game(mover, target)

        game._handle_ball_collisions()
        assert (mover.speed.x, mover.speed.y) == (0.0, 0.0)  # exact elastic physics
        game._keep_collided_balls_playable()

        serve = mover.serve_settings
        for ball in (mover, target):
            assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(serve.speed)
            angle = angle_from_horizontal_degrees(ball)
            assert serve.minimum_angle_degrees - 1e-9 <= angle <= serve.maximum_angle_degrees
        assert mover.speed.x < 0  # away from the target it hit
        assert target.speed.x > 0

    def test_near_vertical_ball_is_turned_to_the_steepest_serve_angle(self):
        """A ball steeper than the serve band keeps its speed and signs at the band's edge."""
        ball = make_ball(world_x=100, world_y=100, speed_x=20.0, speed_y=-400.0)
        partner = make_ball(world_x=91, world_y=100, speed_x=0.0, speed_y=0.0)

        make_ball_pair_game(ball, partner)._keep_ball_playable(ball, partner=partner)

        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(math.hypot(20.0, 400.0))
        assert angle_from_horizontal_degrees(ball) == pytest.approx(
            ball.serve_settings.maximum_angle_degrees
        )
        assert ball.speed.x > 0
        assert ball.speed.y < 0

    def test_flat_ball_is_turned_to_the_shallowest_serve_angle(self):
        """A flat ball (vy == 0) would slide along a wall: it leaves at the band's shallow edge."""
        ball = make_ball(world_x=100, world_y=100, speed_x=-300.0, speed_y=0.0)
        partner = make_ball(world_x=100, world_y=91, speed_x=0.0, speed_y=0.0)

        make_ball_pair_game(ball, partner)._keep_ball_playable(ball, partner=partner)

        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(300.0)
        assert angle_from_horizontal_degrees(ball) == pytest.approx(
            ball.serve_settings.minimum_angle_degrees
        )
        assert ball.speed.x < 0
        assert ball.speed.y > 0  # away from the partner above it

    def test_ball_already_moving_like_a_serve_is_unchanged(self):
        """Inside the serve band and at least serve speed: nothing changes."""
        ball = make_ball(world_x=100, world_y=100, speed_x=-300.0, speed_y=200.0)
        partner = make_ball(world_x=91, world_y=100, speed_x=0.0, speed_y=0.0)

        make_ball_pair_game(ball, partner)._keep_ball_playable(ball, partner=partner)

        assert (ball.speed.x, ball.speed.y) == (-300.0, 200.0)


class TestBallToBallCollisions:
    """A pair of balls that just collided is held apart by PaddleSlap's pair cooldown."""

    def test_ball_to_ball_collision_cooldown(self):
        """A pair that just collided is not collided again during PaddleSlap's pair cooldown.

        The cooldown is the game's (Game._ball_collision_cooldowns, counted in frames), not
        state on the balls.
        """
        game = Game.__new__(Game)
        game._ball_collision_cooldowns = {}
        game._ball_collision_pairs = []
        ball1 = BallSprite(collision_sound=None)
        ball2 = BallSprite(collision_sound=None)
        # Overlapping (centres 10 px apart) and closing on each other
        ball1.world_x, ball1.world_y = 100.0, 100.0
        ball2.world_x, ball2.world_y = 110.0, 100.0
        drawn_position(ball1)
        drawn_position(ball2)
        ball1.speed = Speed(SPEED_3_0, 0.0)
        ball2.speed = Speed(SPEED_NEG_3_0, 0.0)

        game._on_ball_ball_collision(ball1, ball2)
        speeds_after_collision = (ball1.speed.x, ball2.speed.x)
        game._on_ball_ball_collision(ball2, ball1)

        assert game._ball_collision_cooldowns == {(id(ball1), id(ball2)): 10}
        assert speeds_after_collision != (SPEED_3_0, SPEED_NEG_3_0)
        assert (ball1.speed.x, ball2.speed.x) == speeds_after_collision
