#!/usr/bin/env python3
"""Test script to verify ball dt_tick method works correctly."""

import logging
import math

import pytest

from glitchygames.game_objects.ball import BallSprite
from tests.game_objects.ball_helpers import drawn_position

LOG = logging.getLogger(__name__)


# The ball moves this many pixels per second in every direction
SPEED_MAGNITUDE = 250.0
FRAMES_PER_SECOND = 60
# The playfield centre: a second at SPEED_MAGNITUDE stays clear of every wall from here
CENTER_X = 400.0
CENTER_Y = 300.0


class TestBallDtTick:
    """Test ball dt_tick method for consistent movement."""

    @pytest.mark.parametrize('direction', [0, 45, 90, 135, 180, 225, 270, 315])
    def test_ball_dt_tick(self, direction):
        """A second of 60 FPS ticks moves the ball SPEED_MAGNITUDE pixels along its heading."""
        ball = BallSprite()
        ball.world_x = CENTER_X
        ball.world_y = CENTER_Y
        ball.direction = direction
        radians = math.radians(direction)
        ball.speed.x = SPEED_MAGNITUDE * math.cos(radians)
        ball.speed.y = SPEED_MAGNITUDE * math.sin(radians)
        frame_seconds = 1.0 / FRAMES_PER_SECOND

        for _ in range(FRAMES_PER_SECOND):
            ball.dt_tick(frame_seconds)

        expected_x = CENTER_X + SPEED_MAGNITUDE * math.cos(radians)
        expected_y = CENTER_Y + SPEED_MAGNITUDE * math.sin(radians)
        LOG.debug(
            '%3d degrees: (%.1f, %.1f), expected (%.1f, %.1f)',
            direction,
            ball.world_x,
            ball.world_y,
            expected_x,
            expected_y,
        )
        assert ball.world_x == pytest.approx(expected_x)
        assert ball.world_y == pytest.approx(expected_y)
        assert math.dist((CENTER_X, CENTER_Y), (ball.world_x, ball.world_y)) == pytest.approx(
            SPEED_MAGNITUDE
        )
        # The engine draws the ball at its snapped world position
        assert drawn_position(ball) == (round(expected_x), round(expected_y))
        assert ball.alive()
