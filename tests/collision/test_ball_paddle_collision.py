"""Test BallSprite.handle_paddle_collision: exact circle-vs-rect hits and the bounce response.

These use real pygame surfaces so the ball's visible circle (radius 5, drawn in the middle of
its 20x20 colorkey image) gives its real collision rect: a 10x10 box offset (5, 5) from the
drawn position. They live under tests/collision because tests/conftest.py mocks pygame (and
pygame.draw) for every test path containing "game_objects" or "scene".
"""

import math

import pygame
import pytest

from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.game_objects.ball import BallSprite, SpeedUpSettings, SpeedUpTrigger
from glitchygames.game_objects.paddle import VerticalPaddle

# Paddle occupies x 50..70 and y 50..150 (centre x 60).
PADDLE_POSITION = (50, 50)
PADDLE_SIZE = (20, 100)
# The ball's visible circle box relative to its drawn position.
VISIBLE_OFFSET = 5
VISIBLE_SIZE = 10


@pytest.fixture(autouse=True)
def real_display():
    """Give BallSprite and VerticalPaddle a real display to convert their images against."""
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 600))


@pytest.fixture
def paddle(mocker):
    """A real vertical paddle with a mock collision sound.

    Returns:
        VerticalPaddle: The paddle.

    """
    real_paddle = VerticalPaddle('Test Paddle', PADDLE_SIZE, PADDLE_POSITION, (255, 255, 255), 400)
    real_paddle.snd = mocker.Mock()
    return real_paddle


def make_ball(*, world_x, world_y, speed_x=100.0, speed_y=50.0, speed_up_settings=None):
    """Build a real ball at a world position with a known velocity.

    Returns:
        BallSprite: The ball.

    """
    ball = BallSprite(speed_up_settings=speed_up_settings)
    ball.world_x = float(world_x)
    ball.world_y = float(world_y)
    ball.speed.x = speed_x
    ball.speed.y = speed_y
    return ball


class TestCollisionGeometry:
    """The fine check is the ball's visible circle against the paddle's collision rect."""

    def test_ball_collision_rect_is_its_visible_circle(self):
        """The ball collides as the 10x10 box around its drawn circle."""
        ball = make_ball(world_x=40, world_y=90)
        assert get_sprite_collision_rect(ball) == pygame.Rect(45, 95, 10, 10)

    def test_paddle_collision_rect_is_its_full_rect(self, paddle):
        """Paddles are filled rects, so trimming leaves their collision rect unchanged."""
        assert get_sprite_collision_rect(paddle) == paddle.rect

    def test_far_ball_misses_without_side_effects(self, paddle, mocker):
        """A miss returns False and changes nothing."""
        ball = make_ball(world_x=200, world_y=90)
        ball.on_paddle_collision = mocker.Mock()
        ball.dirty = 1

        assert ball.handle_paddle_collision(paddle) is False

        assert (ball.world_x, ball.world_y) == (200.0, 90.0)
        assert (ball.speed.x, ball.speed.y) == (100.0, 50.0)
        assert ball.dirty == 1
        paddle.snd.play.assert_not_called()
        ball.on_paddle_collision.assert_not_called()

    def test_corner_box_overlap_without_circle_overlap_misses(self, paddle):
        """The ball's box overlaps the paddle's corner but the circle does not: no bounce."""
        # Visible box (69, 149)-(79, 159): centre (74, 154), 4 px right and below the corner
        # (70, 150), so the distance is sqrt(32) > radius 5.
        ball = make_ball(world_x=64, world_y=144, speed_x=-100.0, speed_y=-50.0)
        assert get_sprite_collision_rect(ball).colliderect(get_sprite_collision_rect(paddle))

        assert ball.handle_paddle_collision(paddle) is False
        assert ball.speed.x == -100.0

    def test_circle_overlapping_the_corner_hits(self, paddle):
        """A circle reaching past the corner bounces."""
        # Centre (73, 153): distance sqrt(18) < 5.
        ball = make_ball(world_x=63, world_y=143, speed_x=-100.0)
        assert ball.handle_paddle_collision(paddle) is True

    def test_touching_the_face_counts(self, paddle):
        """A circle whose edge exactly touches the paddle face is a hit."""
        # Visible box (40, 95)-(50, 105): centre (45, 100), 5 px from the left face at x=50.
        ball = make_ball(world_x=35, world_y=90, speed_x=100.0)
        assert ball.handle_paddle_collision(paddle) is True

    def test_touching_the_corner_counts(self, paddle):
        """A circle exactly radius away from the corner is a hit."""
        # Centre (73, 154): 3 px right and 4 px below the corner (70, 150), distance 5.
        ball = make_ball(world_x=63, world_y=144, speed_x=-100.0)
        assert ball.handle_paddle_collision(paddle) is True


class TestBounceResponse:
    """Side choice, visible-edge flush placement, speed flip, sound, speed-up, clamp, callback."""

    def test_hit_from_the_left_is_flush_with_the_left_face(self, paddle):
        """The ball's visible right edge ends on the paddle's left face, moving left."""
        ball = make_ball(world_x=40, world_y=90, speed_x=100.0, speed_y=50.0)

        assert ball.handle_paddle_collision(paddle) is True

        assert ball.world_x == paddle.rect.left - (VISIBLE_OFFSET + VISIBLE_SIZE)
        assert get_sprite_collision_rect(ball).right == paddle.rect.left
        assert ball.speed.x == -100.0
        assert math.isclose(ball.speed.y, 50.0)
        assert ball.world_y == 90.0
        assert ball.dirty == 2

    def test_hit_from_the_right_is_flush_with_the_right_face(self, paddle):
        """The ball's visible left edge starts on the paddle's right face, moving right."""
        ball = make_ball(world_x=60, world_y=90, speed_x=-100.0, speed_y=50.0)

        assert ball.handle_paddle_collision(paddle) is True

        assert ball.world_x == paddle.rect.right - VISIBLE_OFFSET
        assert get_sprite_collision_rect(ball).left == paddle.rect.right
        assert ball.speed.x == 100.0
        assert math.isclose(ball.speed.y, 50.0)

    def test_fast_ball_past_the_paddle_centre_moving_right_hits_the_left_face(self, paddle):
        """A ball moving right always hits the left face, even if one long frame (30 fps, a
        hitch) carried its centre past the paddle's centre; it must not be ejected out the back.
        """
        # Visible box (61, 95)-(71, 105): centre 66 > paddle centre 60, moving right.
        ball = make_ball(world_x=56, world_y=90, speed_x=600.0)
        assert ball.handle_paddle_collision(paddle) is True
        assert ball.speed.x == -600.0
        assert get_sprite_collision_rect(ball).right == paddle.rect.left

    def test_ball_moving_left_hits_the_right_face(self, paddle):
        """A ball moving left hits the right face even with its centre left of the paddle's."""
        # Visible box (54, 95)-(64, 105): centre 59 < paddle centre 60, moving left.
        ball = make_ball(world_x=49, world_y=90, speed_x=-100.0)
        assert ball.handle_paddle_collision(paddle) is True
        assert ball.speed.x == 100.0
        assert get_sprite_collision_rect(ball).left == paddle.rect.right

    def test_horizontally_still_ball_uses_collision_rect_centres(self, paddle):
        """With speed.x == 0 the face falls back to ball centre vs paddle centre."""
        # Visible box (54, 95)-(64, 105): centre 59 < paddle centre 60.
        ball = make_ball(world_x=49, world_y=90, speed_x=0.0)
        assert ball.handle_paddle_collision(paddle) is True
        assert get_sprite_collision_rect(ball).right == paddle.rect.left

    def test_still_ball_centred_on_the_paddle_goes_right(self, paddle):
        """Exactly centred and not moving horizontally counts as the right side, as before."""
        # Visible box (55, 95)-(65, 105): centre 60 == paddle centre 60.
        ball = make_ball(world_x=50, world_y=90, speed_x=0.0)
        assert ball.handle_paddle_collision(paddle) is True
        assert get_sprite_collision_rect(ball).left == paddle.rect.right

    def test_hit_plays_the_paddle_sound(self, paddle):
        """The paddle's collision sound plays once."""
        ball = make_ball(world_x=40, world_y=90)
        ball.handle_paddle_collision(paddle)
        paddle.snd.play.assert_called_once()

    def test_paddle_without_sound_is_fine(self, paddle):
        """A paddle with no sound still bounces the ball."""
        paddle.snd = None
        ball = make_ball(world_x=40, world_y=90)
        assert ball.handle_paddle_collision(paddle) is True

    def test_hit_applies_paddle_bounce_speed_up(self, paddle):
        """PADDLE_BOUNCE speeds the ball up once per hit."""
        settings = SpeedUpSettings(triggers=SpeedUpTrigger.PADDLE_BOUNCE, multiplier=1.5)
        ball = make_ball(world_x=40, world_y=90, speed_up_settings=settings)

        ball.handle_paddle_collision(paddle)

        assert ball.speed_up_count == 1
        assert math.isclose(ball.speed.x, -150.0)
        assert math.isclose(ball.speed.y, 75.0)

    def test_hit_caps_speed_at_max_speed(self, paddle):
        """A ball arriving above max_speed is clamped on the hit."""
        ball = make_ball(
            world_x=40,
            world_y=90,
            speed_x=1000.0,
            speed_y=1000.0,
            speed_up_settings=SpeedUpSettings(max_speed=500.0),
        )
        ball.handle_paddle_collision(paddle)
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(500.0)

    def test_hit_without_max_speed_does_not_cap(self, paddle):
        """Default settings (max_speed=None, no triggers) leave a fast ball's magnitude alone."""
        ball = make_ball(world_x=40, world_y=90, speed_x=1000.0, speed_y=1000.0)
        ball.handle_paddle_collision(paddle)
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(math.sqrt(2) * 1000.0)

    def test_hit_calls_on_paddle_collision(self, paddle, mocker):
        """The game's on_paddle_collision callback is called with the ball."""
        ball = make_ball(world_x=40, world_y=90)
        ball.on_paddle_collision = mocker.Mock()
        ball.handle_paddle_collision(paddle)
        ball.on_paddle_collision.assert_called_once_with(ball)

    def test_dt_tick_no_longer_checks_paddles(self, paddle):
        """Paddle detection moved to the collision manager: dt_tick alone never bounces."""
        group = pygame.sprite.LayeredDirty()
        ball = BallSprite(groups=group)
        group.add(paddle)
        ball.world_x = 40.0
        ball.world_y = 90.0
        ball.speed.x = 100.0
        ball.speed.y = 0.0

        ball.dt_tick(0.01)

        assert ball.speed.x == 100.0
        paddle.snd.play.assert_not_called()


class TestBallPairDistance:
    """PaddleSlap's ball-ball fine check uses the same visible circles as the broad phase."""

    def test_collision_distance_is_the_sum_of_visible_radii(self):
        """Two real balls collide when their radius-5 circles touch (10 px apart)."""
        from glitchygames.examples.paddleslap import Game

        first_ball = make_ball(world_x=100, world_y=100)
        second_ball = make_ball(world_x=108, world_y=106)

        delta_x, delta_y, distance, collision_distance = Game._calculate_ball_distance(
            first_ball, second_ball
        )

        assert (delta_x, delta_y) == (8.0, 6.0)
        assert distance == pytest.approx(10.0)
        assert collision_distance == VISIBLE_SIZE
