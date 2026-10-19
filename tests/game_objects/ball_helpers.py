"""Shared helpers for tests of world-space balls (BallSprite)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from glitchygames.camera import Camera2D
from glitchygames.world import position_world_sprites

if TYPE_CHECKING:
    from glitchygames.game_objects.ball import BallSprite


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
