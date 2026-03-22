#!/usr/bin/env python3
"""Test script to verify the logging is working."""

import logging
import sys
from pathlib import Path

import pygame

# Add the glitchygames directory to the path
sys.path.insert(0, str(Path(__file__).parent / 'glitchygames'))

from glitchygames.game_objects.ball import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle

LOG = logging.getLogger(__name__)


def test_logging():
    """Test the logging functionality."""
    # Initialize pygame and set a display mode so Surface.convert() works
    pygame.init()
    pygame.display.set_mode((800, 600))

    try:
        LOG.debug('Testing ball and paddle logging...')

        # Create a ball
        ball = BallSprite()
        ball.speed.x = 100.0
        ball.speed.y = 50.0
        assert ball.rect is not None
        ball.rect.x = 100
        ball.rect.y = 100

        LOG.debug('\n=== Testing Ball Movement ===')
        ball.dt_tick(0.016)  # 60 FPS

        LOG.debug('\n=== Testing Ball Bounce ===')
        ball.rect.y = -5  # Above screen
        ball._do_bounce()

        # Create a paddle
        paddle = VerticalPaddle('Test Paddle', (20, 80), (0, 100), (255, 255, 255), 300)

        LOG.debug('\n=== Testing Paddle Movement ===')
        paddle.dt_tick(0.016)  # 60 FPS

        LOG.debug('\nLogging test completed!')
    finally:
        pygame.quit()


if __name__ == '__main__':
    test_logging()
