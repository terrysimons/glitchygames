"""Ball walls, off-screen kill and serve margins use the ball's visible circle (real surfaces).

The ball's image is 20x20 with a radius-5 circle in the middle, so its visible collision rect is
a 10x10 box offset (5, 5) from where it is drawn. These tests live under tests/collision because
tests/conftest.py mocks pygame drawing for every path containing "game_objects"; there the circle
is never drawn and the visible rect is the whole image. The wall sweep helpers are shared with
tests/game_objects/test_ball.py, which runs the same sweep with the mocked (offset 0) ball.
"""

import math

import pygame
import pytest

import glitchygames.game_objects.ball as ball_module
from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.game_objects.ball import BallSprite, ServeSettings
from glitchygames.movement import Speed
from tests.game_objects.test_ball import (
    CORNERS,
    FRAMES_AFTER_BOUNCE,
    WALL_BOUNCE_TOLERANCE,
    _expected_position_after_bounce,
    _place_ball_past_walls,
    _playfield_limits,
    _wall_bounce_sweep_cases,
)

SCREEN_SIZE = (800, 600)
VISIBLE_OFFSET = 5
VISIBLE_SIZE = 10


@pytest.fixture(autouse=True)
def real_display():
    """Give BallSprite a real display to convert its image against."""
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode(SCREEN_SIZE)


def make_bouncing_ball(*, bounce_left_right=True):
    """Build a real ball that bounces off the top and bottom (and optionally side) walls.

    Returns:
        BallSprite: The ball.

    """
    ball = BallSprite(bounce_top_bottom=True, bounce_left_right=bounce_left_right)
    ball.screen_width, ball.screen_height = SCREEN_SIZE
    return ball


class TestVisiblePlayfieldLimits:
    """Wall contact happens where the visible circle meets the wall."""

    def test_limits_are_offset_by_the_transparent_margin(self):
        """The visible box touches the walls 5 px past the image's own edges."""
        ball = make_bouncing_ball()
        limits = _playfield_limits(ball)
        assert limits.minimum_x == -VISIBLE_OFFSET
        assert limits.minimum_y == -VISIBLE_OFFSET
        assert limits.maximum_x == SCREEN_SIZE[0] - VISIBLE_SIZE - VISIBLE_OFFSET
        assert limits.maximum_y == SCREEN_SIZE[1] - VISIBLE_SIZE - VISIBLE_OFFSET

    def test_circle_short_of_the_top_wall_does_not_bounce(self):
        """Visible top at y=3, moving up: not touching yet (the image top is already at -2)."""
        ball = make_bouncing_ball()
        ball.speed = Speed(0.0, -100.0)
        ball.world_x = 400.0
        ball.world_y = -2.0

        ball._do_bounce()

        assert ball.speed.y == -100.0
        assert ball.world_y == -2.0

    def test_circle_touching_the_top_wall_bounces(self):
        """Visible top at y=0, moving up: one bounce, position kept."""
        ball = make_bouncing_ball()
        ball.speed = Speed(0.0, -100.0)
        ball.world_x = 400.0
        ball.world_y = -5.0

        ball._do_bounce()

        assert ball.speed.y == 100.0
        assert ball.world_y == -5.0
        assert get_sprite_collision_rect(ball).top == 0

    def test_circle_touching_the_bottom_wall_bounces(self):
        """Visible bottom on the bottom wall, moving down: bounces."""
        ball = make_bouncing_ball()
        ball.speed = Speed(0.0, 100.0)
        ball.world_x = 400.0
        ball.world_y = float(SCREEN_SIZE[1] - VISIBLE_SIZE - VISIBLE_OFFSET)

        ball._do_bounce()

        assert ball.speed.y == -100.0
        assert get_sprite_collision_rect(ball).bottom == SCREEN_SIZE[1]

    def test_top_overshoot_is_mirrored_on_the_visible_edge(self):
        """A visible top 3 px above the wall is mirrored to 3 px below it."""
        ball = make_bouncing_ball()
        ball.speed = Speed(0.0, -100.0)
        ball.world_x = 400.0
        ball.world_y = -8.0

        ball._do_bounce()

        assert ball.world_y == -2.0
        assert get_sprite_collision_rect(ball).top == 3


class TestVisibleWallSweep:
    """The full wall and corner sweep from test_ball.py, with the real visible circle."""

    @pytest.mark.parametrize(('walls', 'angle', 'overshoot', 'speed'), _wall_bounce_sweep_cases())
    def test_bounce_reflects_once_and_leaves(self, walls, angle, overshoot, speed):
        """One reflection off the visible edge, mirrored inside, then no re-bounce."""
        ball = make_bouncing_ball()
        initial_x = speed * math.cos(math.radians(angle))
        initial_y = speed * math.sin(math.radians(angle))
        ball.speed = Speed(initial_x, initial_y)
        _place_ball_past_walls(ball, walls, overshoot)
        expected_position = _expected_position_after_bounce(ball, walls, overshoot)
        description = f'{"+".join(walls)} at {angle} deg, overshoot {overshoot}'

        ball._do_bounce()

        flips_x = 'left' in walls or 'right' in walls
        flips_y = 'top' in walls or 'bottom' in walls
        expected_speed = (
            -initial_x if flips_x else initial_x,
            -initial_y if flips_y else initial_y,
        )
        assert (ball.speed.x, ball.speed.y) == pytest.approx(
            expected_speed, abs=WALL_BOUNCE_TOLERANCE
        ), description
        assert (ball.world_x, ball.world_y) == pytest.approx(
            expected_position, abs=WALL_BOUNCE_TOLERANCE
        ), description
        visible_rect = get_sprite_collision_rect(ball)
        assert 0 <= visible_rect.left <= visible_rect.right <= SCREEN_SIZE[0], description
        assert 0 <= visible_rect.top <= visible_rect.bottom <= SCREEN_SIZE[1], description

        speed_after_bounce = (ball.speed.x, ball.speed.y)
        for frame in range(1, FRAMES_AFTER_BOUNCE + 1):
            ball.dt_tick(1 / 60)
            assert (ball.speed.x, ball.speed.y) == speed_after_bounce, (
                f'{description}: bounced again {frame} frame(s) later'
            )

    @pytest.mark.parametrize('corner', CORNERS, ids='+'.join)
    def test_ball_exactly_in_a_corner_reflects_both_and_leaves(self, corner):
        """Visible edges on both walls of a corner: both components flip, position kept."""
        ball = make_bouncing_ball()
        limits = _playfield_limits(ball)
        speed_x = -100.0 if 'left' in corner else 100.0
        speed_y = -100.0 if 'top' in corner else 100.0
        ball.speed = Speed(speed_x, speed_y)
        ball.world_x = limits.minimum_x if 'left' in corner else limits.maximum_x
        ball.world_y = limits.minimum_y if 'top' in corner else limits.maximum_y
        corner_position = (ball.world_x, ball.world_y)

        ball._do_bounce()

        assert (ball.speed.x, ball.speed.y) == (-speed_x, -speed_y)
        assert (ball.world_x, ball.world_y) == corner_position
        ball.dt_tick(1 / 60)
        assert (ball.speed.x, ball.speed.y) == (-speed_x, -speed_y)


class TestVisibleOffScreenKill:
    """A scoring ball is killed only once its visible circle has fully left the screen."""

    @staticmethod
    def _ball_at(world_x):
        """A stationary non-side-bouncing ball in a group, at world_x.

        Returns:
            BallSprite: The ball.

        """
        group = pygame.sprite.LayeredDirty()
        ball = BallSprite(groups=group, bounce_top_bottom=True, bounce_left_right=False)
        ball.screen_width, ball.screen_height = SCREEN_SIZE
        ball.speed = Speed(0.0, 0.0)
        ball.world_x = float(world_x)
        ball.world_y = 300.0
        return ball

    def test_visible_right_edge_on_the_left_border_is_alive(self):
        """Visible right edge at x=0 (world -15): still touching the screen."""
        ball = self._ball_at(-VISIBLE_OFFSET - VISIBLE_SIZE)
        ball.dt_tick(0.0)
        assert ball.alive()

    def test_visible_circle_past_the_left_border_is_killed(self):
        """Visible right edge at x=-1 (world -16) is off screen, though the image is not."""
        ball = self._ball_at(-VISIBLE_OFFSET - VISIBLE_SIZE - 1)
        ball.dt_tick(0.0)
        assert not ball.alive()

    def test_visible_left_edge_on_the_right_border_is_alive(self):
        """Visible left edge at x=800 (world 795): not yet past the border."""
        ball = self._ball_at(SCREEN_SIZE[0] - VISIBLE_OFFSET)
        ball.dt_tick(0.0)
        assert ball.alive()

    def test_visible_circle_past_the_right_border_is_killed(self):
        """Visible left edge at x=801 (world 796) is past the border."""
        ball = self._ball_at(SCREEN_SIZE[0] - VISIBLE_OFFSET + 1)
        ball.dt_tick(0.0)
        assert not ball.alive()


class TestVisibleServeMargin:
    """spawn_margin is measured from the visible circle to each screen edge."""

    @pytest.mark.parametrize('pick', ['lowest', 'highest'])
    def test_visible_circle_is_exactly_margin_from_the_edges(self, mocker, pick):
        """The extreme serve positions put the visible box exactly spawn_margin from the edge."""
        ball = make_bouncing_ball()
        mocker.patch.object(
            ball_module._SERVE_RANDOM,
            'randint',
            side_effect=lambda low, high: low if pick == 'lowest' else high,
        )
        margin = ServeSettings().spawn_margin

        ball.reset()

        visible_rect = get_sprite_collision_rect(ball)
        if pick == 'lowest':
            assert visible_rect.topleft == (margin, margin)
        else:
            assert visible_rect.bottomright == (SCREEN_SIZE[0] - margin, SCREEN_SIZE[1] - margin)

    def test_screen_too_small_centres_the_visible_circle(self):
        """On a 10x10 screen the 10x10 visible box fills it exactly."""
        ball = make_bouncing_ball()
        ball.screen_width = ball.screen_height = VISIBLE_SIZE
        ball.reset()
        assert get_sprite_collision_rect(ball).topleft == (0, 0)
