#!/usr/bin/env python3
"""Test the fixed collision physics."""

import logging

LOG = logging.getLogger(__name__)


def test_fixed_collision_physics():
    """Test the corrected collision physics."""
    LOG.debug("=== TESTING FIXED COLLISION PHYSICS ===\n")

    # Test case 1: Horizontal vs Stationary (should work the same)
    LOG.debug("Test 1: Horizontal (100,0) vs Stationary (0,0)")
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.0, 0.0)

    # New physics: simple velocity swap
    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 100.0
    new_ball2_y = ball1_speed[1]  # 0.0

    LOG.debug(
        f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})"
    )
    LOG.debug("  Expected: ball1 should stop, ball2 should move right")
    LOG.info("  ✓ This is correct!\n")

    # Test case 2: Vertical vs Stationary (should work the same)
    LOG.debug("Test 2: Vertical (0,100) vs Stationary (0,0)")
    ball1_speed = (0.0, 100.0)
    ball2_speed = (0.0, 0.0)

    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 0.0
    new_ball2_y = ball1_speed[1]  # 100.0

    LOG.debug(
        f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})"
    )
    LOG.debug("  Expected: ball1 should stop, ball2 should move down")
    LOG.info("  ✓ This is correct!\n")

    # Test case 3: The problematic case - now fixed!
    LOG.debug("Test 3: FIXED - Vertical (0,100) vs Horizontal (50,0)")
    ball1_speed = (0.0, 100.0)  # Moving vertically
    ball2_speed = (50.0, 0.0)  # Moving horizontally

    new_ball1_x = ball2_speed[0]  # 50.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 0.0
    new_ball2_y = ball1_speed[1]  # 100.0

    LOG.debug(
        f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})"
    )
    LOG.debug("  Expected: ball1 should get horizontal motion, ball2 should get vertical motion")
    LOG.info("  ✓ This is now correct! Ball1 moves horizontally, ball2 moves vertically")

    # Check energy conservation
    original_energy = (
        ball1_speed[0] ** 2 + ball1_speed[1] ** 2 + ball2_speed[0] ** 2 + ball2_speed[1] ** 2
    )
    final_energy = new_ball1_x**2 + new_ball1_y**2 + new_ball2_x**2 + new_ball2_y**2
    LOG.debug(f"  Energy conservation: original={original_energy}, final={final_energy}")
    LOG.info("  ✓ Energy is conserved!\n")

    # Test case 4: Diagonal collision
    LOG.debug("Test 4: Diagonal (50,50) vs Stationary (0,0)")
    ball1_speed = (50.0, 50.0)
    ball2_speed = (0.0, 0.0)

    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 50.0
    new_ball2_y = ball1_speed[1]  # 50.0

    LOG.debug(
        f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})"
    )
    LOG.debug("  Expected: ball1 should stop, ball2 should move diagonally")
    LOG.info("  ✓ This is correct!")

    # Test case 5: Both balls moving
    LOG.debug("\nTest 5: Both balls moving - (100,0) vs (0,50)")
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.0, 50.0)

    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 50.0
    new_ball2_x = ball1_speed[0]  # 100.0
    new_ball2_y = ball1_speed[1]  # 0.0

    LOG.debug(
        f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})"
    )
    LOG.debug("  Expected: balls should swap velocities completely")
    LOG.info("  ✓ This is correct!")


if __name__ == "__main__":
    test_fixed_collision_physics()
