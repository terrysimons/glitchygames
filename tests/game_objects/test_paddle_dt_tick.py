#!/usr/bin/env python3
"""Test script to verify paddle movement works correctly."""

import logging

import pygame
from glitchygames.game_objects.paddle import VerticalPaddle

LOG = logging.getLogger(__name__)


def test_paddle_movement():
    """Test paddle movement for consistent behavior."""
    LOG.debug("Testing paddle movement...")

    # Initialize pygame
    pygame.init()
    pygame.display.set_mode((800, 600))

    # Create a paddle
    paddle = VerticalPaddle(
        "Test Paddle",
        (20, 80),
        (400, 300),
        (255, 255, 255),
        400,  # 400 pixels per second
        collision_sound=None,
    )

    # Test movement in different directions
    directions = ["up", "down", "stop"]
    dt = 1.0 / 60.0  # 60 FPS

    LOG.debug(f"Testing with dt={dt:.4f} (60 FPS)")
    LOG.debug("Direction | Initial Pos | Final Pos | Distance | Speed")
    LOG.debug("----------|-------------|-----------|----------|-------")

    for direction in directions:
        # Reset paddle position
        paddle.rect.y = 300

        # Set movement direction
        if direction == "up":
            paddle.up()
        elif direction == "down":
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
            f"{direction:8s} | {initial_y:10d} | {final_y:9d} | {distance:6.1f} | {actual_speed:6.1f}"
        )


if __name__ == "__main__":
    test_paddle_movement()
