#!/usr/bin/env python3
"""Test script to verify ball dt_tick method works correctly."""

import logging
import math

import pytest

from glitchygames.game_objects.ball import BallSprite
from tests.mocks.test_mock_factory import MockFactory

LOG = logging.getLogger(__name__)


class TestBallDtTick:
    """Test ball dt_tick method for consistent movement."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_dt_tick(self):
        """Test ball dt_tick method for consistent movement."""
        LOG.debug('Testing ball dt_tick method...')

        # Create a ball
        ball = BallSprite()

        # Test movement in different directions
        directions = [0, 45, 90, 135, 180, 225, 270, 315]  # 8 directions
        dt = 1.0 / 60.0  # 60 FPS

        LOG.debug(f'Testing with dt={dt:.4f} (60 FPS)')
        LOG.debug('Direction | Initial Pos | Final Pos  | Distance | Speed')
        LOG.debug('----------|-------------|------------|----------|-------')

        for direction in directions:
            # Reset ball position to center
            ball.rect.x = 400
            ball.rect.y = 300

            # Set direction and calculate speed
            ball.direction = direction
            radians = math.radians(direction)
            # Use fixed speed magnitude
            speed_magnitude = 250.0
            ball.speed.x = speed_magnitude * math.cos(radians)
            ball.speed.y = speed_magnitude * math.sin(radians)

            initial_x, initial_y = ball.rect.x, ball.rect.y

            # Move ball for 1 second (60 frames) using dt_tick
            for frame in range(60):
                ball.dt_tick(dt)

            final_x, final_y = ball.rect.x, ball.rect.y

            # Calculate distance moved
            distance = math.sqrt((final_x - initial_x) ** 2 + (final_y - initial_y) ** 2)
            actual_speed = distance / 1.0  # distance per second

            LOG.debug(
                f'{direction:8d}° | ({initial_x:3d},{initial_y:3d})'
                f'     | ({final_x:3d},{final_y:3d})'
                f'    | {distance:6.1f} | {actual_speed:6.1f}'
            )
