#!/usr/bin/env python3
"""Test collision physics edge cases that could cause weird behavior."""

import logging

LOG = logging.getLogger(__name__)


def _test_overlapping_balls():
    """Test case 1: Very small distance (balls overlapping)."""
    LOG.debug('\nTest 1: Overlapping balls (distance = 0.1)')
    dx, dy = 0.1, 0.0
    distance = 0.1

    nx = dx / distance  # 1.0
    ny = dy / distance  # 0.0

    LOG.debug(f'  Normal vector: ({nx}, {ny})')
    LOG.debug(f'  Distance: {distance}')


def _test_zero_distance():
    """Test case 2: Distance exactly zero (balls at same position)."""
    LOG.debug('\nTest 2: Balls at same position (distance = 0)')
    distance = 0.0

    if distance > 0:
        LOG.debug('  Normal vector computed')
    else:
        LOG.debug('  ERROR: Division by zero!')


def _test_same_direction():
    """Test case 3: Balls moving in same direction."""
    LOG.debug('\nTest 3: Balls moving in same direction')
    ball1_speed = (100.0, 0.0)
    ball2_speed = (50.0, 0.0)
    dx, dy = 20.0, 0.0
    distance = 20.0

    nx = dx / distance
    ny = dy / distance

    dvx = ball2_speed[0] - ball1_speed[0]
    dvy = ball2_speed[1] - ball1_speed[1]
    dvn = dvx * nx + dvy * ny

    LOG.debug(f'  Relative velocity: ({dvx}, {dvy})')
    LOG.debug(f'  Relative velocity along normal: {dvn}')
    LOG.debug(f'  Should collide: {dvn < 0}')


def _test_moving_away():
    """Test case 4: Balls moving away from each other."""
    LOG.debug('\nTest 4: Balls moving away from each other')
    ball1_speed = (100.0, 0.0)
    ball2_speed = (-50.0, 0.0)
    dx, dy = 20.0, 0.0
    distance = 20.0

    nx = dx / distance
    ny = dy / distance

    dvx = ball2_speed[0] - ball1_speed[0]
    dvy = ball2_speed[1] - ball1_speed[1]
    dvn = dvx * nx + dvy * ny

    LOG.debug(f'  Relative velocity: ({dvx}, {dvy})')
    LOG.debug(f'  Relative velocity along normal: {dvn}')
    LOG.debug(f'  Should collide: {dvn < 0}')


def _test_small_velocity():
    """Test case 5: One ball with very small velocity."""
    LOG.debug('\nTest 5: One ball with very small velocity')
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.001, 0.0)
    dx, dy = 20.0, 0.0
    distance = 20.0

    nx = dx / distance
    ny = dy / distance

    v1n = ball1_speed[0] * nx + ball1_speed[1] * ny
    v2n = ball2_speed[0] * nx + ball2_speed[1] * ny

    new_ball1_x = ball1_speed[0] - v1n * nx + v2n * nx
    new_ball1_y = ball1_speed[1] - v1n * ny + v2n * ny
    new_ball2_x = ball2_speed[0] - v2n * nx + v1n * nx
    new_ball2_y = ball2_speed[1] - v2n * ny + v1n * ny

    LOG.debug(
        f'  Before: ball1=({ball1_speed[0]}, {ball1_speed[1]}),'
        f' ball2=({ball2_speed[0]}, {ball2_speed[1]})'
    )
    LOG.debug(
        f'  After:  ball1=({new_ball1_x:.3f}, {new_ball1_y:.3f}),'
        f' ball2=({new_ball2_x:.3f}, {new_ball2_y:.3f})'
    )


def test_edge_cases():
    """Test edge cases that could cause balls to get stuck or behave weirdly."""
    LOG.debug('Testing collision physics edge cases...')

    _test_overlapping_balls()
    _test_zero_distance()
    _test_same_direction()
    _test_moving_away()
    _test_small_velocity()


if __name__ == '__main__':
    test_edge_cases()
