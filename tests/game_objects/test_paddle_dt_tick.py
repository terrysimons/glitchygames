#!/usr/bin/env python3
"""Test script to verify paddle movement works correctly."""

import logging

import pygame

from glitchygames.game_objects.paddle import VerticalPaddle
from tests.display_canvas import show_canvas_on_new_display

LOG = logging.getLogger(__name__)


def test_paddle_movement():
    """Test paddle movement for consistent behavior."""
    LOG.debug('Testing paddle movement...')

    # Initialize pygame
    pygame.init()
    show_canvas_on_new_display(size=(800, 600))

    # Create a paddle
    paddle = VerticalPaddle(
        'Test Paddle',
        (20, 80),
        (400, 300),
        (255, 255, 255),
        400,  # 400 pixels per second
        collision_sound=None,
    )

    # Test movement in different directions
    directions = ['up', 'down', 'stop']
    dt = 1.0 / 60.0  # 60 FPS

    LOG.debug('Testing with dt=%.4f (60 FPS)', dt)
    LOG.debug('Direction | Initial Pos | Final Pos | Distance | Speed')
    LOG.debug('----------|-------------|-----------|----------|-------')

    for direction in directions:
        # Reset paddle position
        assert paddle.rect is not None
        paddle.rect.y = 300

        # Set movement direction
        if direction == 'up':
            paddle.up()
        elif direction == 'down':
            paddle.down()
        else:  # stop
            paddle.stop()

        initial_y = paddle.rect.y

        # Move paddle for 1 second (60 frames)
        for frame in range(60):
            paddle.dt_tick(dt)

        final_y = paddle.rect.y

        # Calculate distance moved
        distance = abs(final_y - initial_y)
        actual_speed = distance / 1.0  # distance per second

        LOG.debug(
            '%s | %10d | %9d | %6.1f | %6.1f',
            format(direction, '8s'),
            initial_y,
            final_y,
            distance,
            actual_speed,
        )


if __name__ == '__main__':
    test_paddle_movement()
