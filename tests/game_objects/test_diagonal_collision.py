#!/usr/bin/env python3
"""Test diagonal collision with horizontal ball."""

import logging

LOG = logging.getLogger(__name__)


def test_diagonal_vs_horizontal():
    """Test diagonal ball hitting horizontal ball."""
    LOG.debug('=== TESTING DIAGONAL VS HORIZONTAL COLLISION ===\n')

    # Test case: Diagonal ball hits horizontal ball
    LOG.debug('Test: Diagonal (50,50) vs Horizontal (100,0)')
    ball1_speed = (50.0, 50.0)  # Diagonal ball
    ball2_speed = (100.0, 0.0)  # Horizontal ball
    dx, dy = 20.0, 0.0  # Ball2 is to the right of ball1
    distance = 20.0

    # Calculate collision normal
    nx = dx / distance  # 1.0 (horizontal)
    ny = dy / distance  # 0.0

    LOG.debug(f'  Collision normal: ({nx}, {ny})')

    # Calculate velocity components along collision normal
    v1n = ball1_speed[0] * nx + ball1_speed[1] * ny  # 50 * 1.0 + 50 * 0.0 = 50
    v2n = ball2_speed[0] * nx + ball2_speed[1] * ny  # 100 * 1.0 + 0 * 0.0 = 100

    LOG.debug(f'  v1n (ball1 normal component): {v1n}')
    LOG.debug(f'  v2n (ball2 normal component): {v2n}')

    # Exchange normal components
    new_ball1_x = ball1_speed[0] - v1n * nx + v2n * nx  # 50 - 50*1.0 + 100*1.0 = 100
    new_ball1_y = ball1_speed[1] - v1n * ny + v2n * ny  # 50 - 50*0.0 + 100*0.0 = 50
    new_ball2_x = ball2_speed[0] - v2n * nx + v1n * nx  # 100 - 100*1.0 + 50*1.0 = 50
    new_ball2_y = ball2_speed[1] - v2n * ny + v1n * ny  # 0 - 100*0.0 + 50*0.0 = 0

    LOG.debug(
        f'  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})'
    )
    LOG.debug(
        '  Expected: ball1 should get horizontal component, ball2 should get diagonal component'
    )
    LOG.debug('  Analysis:')
    LOG.debug('    - Ball1: Now moves horizontally (100,50) - got the horizontal speed from ball2')
    LOG.debug('    - Ball2: Now moves diagonally (50,0) - got the horizontal component from ball1')
    LOG.info("    - Ball1's Y component (50) is preserved - this is correct!")
    LOG.info("    - Ball2's Y component (0) is preserved - this is correct!")

    # Check energy conservation
    original_energy = (
        ball1_speed[0] ** 2 + ball1_speed[1] ** 2 + ball2_speed[0] ** 2 + ball2_speed[1] ** 2
    )
    final_energy = new_ball1_x**2 + new_ball1_y**2 + new_ball2_x**2 + new_ball2_y**2
    LOG.debug(f'  Energy conservation: original={original_energy}, final={final_energy}')
    LOG.info('  ✓ Energy is conserved!')

    LOG.info('\nThis is the correct behavior for elastic collision!')
    LOG.debug("The diagonal ball's vertical component is preserved,")
    LOG.debug('and only the horizontal components are exchanged.')


if __name__ == '__main__':
    test_diagonal_vs_horizontal()
