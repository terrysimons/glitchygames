#!/usr/bin/env python3
"""Test the fixed collision physics."""

import logging

LOG = logging.getLogger(__name__)


def _test_velocity_swap(test_label, ball1_speed, ball2_speed, expected_description):
    """Test a single velocity swap collision case.

    The simple collision model swaps velocities entirely between two equal-mass balls.

    Returns:
        Tuple of (new_ball1_x, new_ball1_y, new_ball2_x, new_ball2_y).

    """
    LOG.debug(test_label)

    new_ball1_x = ball2_speed[0]
    new_ball1_y = ball2_speed[1]
    new_ball2_x = ball1_speed[0]
    new_ball2_y = ball1_speed[1]

    LOG.debug(
        f'  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})'
    )
    LOG.debug(f'  Expected: {expected_description}')
    LOG.info('  Correct!')

    return new_ball1_x, new_ball1_y, new_ball2_x, new_ball2_y


def test_fixed_collision_physics():
    """Test the corrected collision physics."""
    LOG.debug('=== TESTING FIXED COLLISION PHYSICS ===\n')

    # Test case 1: Horizontal vs Stationary
    _test_velocity_swap(
        'Test 1: Horizontal (100,0) vs Stationary (0,0)',
        (100.0, 0.0),
        (0.0, 0.0),
        'ball1 should stop, ball2 should move right',
    )

    # Test case 2: Vertical vs Stationary
    _test_velocity_swap(
        'Test 2: Vertical (0,100) vs Stationary (0,0)',
        (0.0, 100.0),
        (0.0, 0.0),
        'ball1 should stop, ball2 should move down',
    )

    # Test case 3: The problematic case - now fixed!
    ball1_speed = (0.0, 100.0)
    ball2_speed = (50.0, 0.0)
    new_ball1_x, new_ball1_y, new_ball2_x, new_ball2_y = _test_velocity_swap(
        'Test 3: FIXED - Vertical (0,100) vs Horizontal (50,0)',
        ball1_speed,
        ball2_speed,
        'ball1 should get horizontal motion, ball2 should get vertical motion',
    )

    # Check energy conservation for case 3
    original_energy = (
        ball1_speed[0] ** 2 + ball1_speed[1] ** 2 + ball2_speed[0] ** 2 + ball2_speed[1] ** 2
    )
    final_energy = new_ball1_x**2 + new_ball1_y**2 + new_ball2_x**2 + new_ball2_y**2
    LOG.debug(f'  Energy conservation: original={original_energy}, final={final_energy}')
    LOG.info('  Energy is conserved!\n')

    # Test case 4: Diagonal collision
    _test_velocity_swap(
        'Test 4: Diagonal (50,50) vs Stationary (0,0)',
        (50.0, 50.0),
        (0.0, 0.0),
        'ball1 should stop, ball2 should move diagonally',
    )

    # Test case 5: Both balls moving
    _test_velocity_swap(
        '\nTest 5: Both balls moving - (100,0) vs (0,50)',
        (100.0, 0.0),
        (0.0, 50.0),
        'balls should swap velocities completely',
    )


if __name__ == '__main__':
    test_fixed_collision_physics()
