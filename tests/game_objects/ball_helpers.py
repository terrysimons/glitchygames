"""Shared helpers for tests of world-space balls (BallSprite)."""

from __future__ import annotations

import pygame

from glitchygames.camera import Camera2D
from glitchygames.collision.bounds import opaque_bounds
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.game_objects.ball import BallSprite
from glitchygames.world import position_world_sprites

# The ball's visible circle box size (its drawn circle sits VISIBLE_OFFSET inside its rect)
VISIBLE_SIZE = 10


def drawn_position(ball: BallSprite) -> tuple[int, int]:
    """Position the ball as the engine does before a render, under an identity camera.

    The ball is a world sprite: its rect is written only by the engine's positioning step
    (glitchygames/world.py), so tests that check where the ball is drawn run that step first.
    PaddleSlap's camera never moves, so screen and world coordinates are the same.

    Returns:
        tuple[int, int]: The ball's rect top-left after positioning.

    """
    screen_size = (int(ball.screen_width), int(ball.screen_height))
    position_world_sprites(sprites=[ball], camera=Camera2D(*screen_size), screen_size=screen_size)
    return ball.rect.topleft


def visible_center_offset(ball: BallSprite) -> tuple[float, float]:
    """Return the offset of the ball's visible circle centre from its world position.

    The ball collides as its visible pixels (its collision rect, glitchygames/collision/
    bounds.py): the radius-5 circle drawn centred in its image, not the whole image. Tests
    that aim or place a ball by its centre use this offset instead of assuming the image size.

    Returns:
        tuple[float, float]: (offset_x, offset_y) of the visible circle's centre.

    """
    visible_rect = get_sprite_collision_rect(ball)
    offset_x, offset_y = collision_rect_offset(ball)
    return (offset_x + visible_rect.width / 2, offset_y + visible_rect.height / 2)


def place_ball_center(ball: BallSprite, *, center_x: float, center_y: float) -> None:
    """Set the ball's world position so its visible circle is centred on (center_x, center_y)."""
    offset_x, offset_y = visible_center_offset(ball)
    ball.world_x = center_x - offset_x
    ball.world_y = center_y - offset_y


def place_visible_edge_past_wall(ball: BallSprite, *, wall: str, overshoot: float) -> None:
    """Move the ball so its visible circle's edge is `overshoot` pixels past a screen wall.

    Walls are the screen edges ('top', 'bottom', 'left' or 'right'); the ball meets them with
    its visible circle (its collision rect), which is inset from its image's edges. Only the
    axis that wall is on changes.

    Raises:
        ValueError: For an unknown wall name.

    """
    visible_rect = get_sprite_collision_rect(ball)
    offset_x, offset_y = collision_rect_offset(ball)
    if wall == 'top':
        ball.world_y = -offset_y - overshoot
    elif wall == 'bottom':
        ball.world_y = ball.screen_height - visible_rect.height - offset_y + overshoot
    elif wall == 'left':
        ball.world_x = -offset_x - overshoot
    elif wall == 'right':
        ball.world_x = ball.screen_width - visible_rect.width - offset_x + overshoot
    else:
        message = f'Unknown wall {wall!r}: expected top, bottom, left or right'
        raise ValueError(message)


def drawn_visible_rect(ball: BallSprite) -> pygame.Rect:
    """Position the ball as the engine does (see drawn_position) and return its drawn circle.

    Returns:
        pygame.Rect: The screen rect of the ball's visible pixels where it is drawn.

    """
    left, top = drawn_position(ball)
    visible_bounds = opaque_bounds(ball.image)
    return pygame.Rect(
        left + visible_bounds.x, top + visible_bounds.y, visible_bounds.width, visible_bounds.height
    )


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
