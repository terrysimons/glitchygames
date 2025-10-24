#!/usr/bin/env python3
"""Test collision physics edge cases that could cause weird behavior."""

import math

def test_edge_cases():
    """Test edge cases that could cause balls to get stuck or behave weirdly."""
    print("Testing collision physics edge cases...")
    
    # Test case 1: Very small distance (balls overlapping)
    print("\nTest 1: Overlapping balls (distance = 0.1)")
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.0, 0.0)
    dx, dy = 0.1, 0.0  # Very small distance
    distance = 0.1
    
    nx = dx / distance  # 1.0
    ny = dy / distance  # 0.0
    
    print(f"  Normal vector: ({nx}, {ny})")
    print(f"  Distance: {distance}")
    
    # Test case 2: Distance exactly zero (balls at same position)
    print("\nTest 2: Balls at same position (distance = 0)")
    dx, dy = 0.0, 0.0
    distance = 0.0
    
    if distance > 0:
        nx = dx / distance
        ny = dy / distance
        print(f"  Normal vector: ({nx}, {ny})")
    else:
        print("  ERROR: Division by zero!")
    
    # Test case 3: Balls moving in same direction
    print("\nTest 3: Balls moving in same direction")
    ball1_speed = (100.0, 0.0)  # Moving right
    ball2_speed = (50.0, 0.0)   # Also moving right, but slower
    dx, dy = 20.0, 0.0
    distance = 20.0
    
    nx = dx / distance  # 1.0
    ny = dy / distance  # 0.0
    
    # Calculate relative velocity
    dvx = ball2_speed[0] - ball1_speed[0]  # 50 - 100 = -50
    dvy = ball2_speed[1] - ball1_speed[1]  # 0 - 0 = 0
    dvn = dvx * nx + dvy * ny  # -50 * 1.0 + 0 * 0.0 = -50
    
    print(f"  Relative velocity: ({dvx}, {dvy})")
    print(f"  Relative velocity along normal: {dvn}")
    print(f"  Should collide: {dvn < 0}")
    
    # Test case 4: Balls moving away from each other
    print("\nTest 4: Balls moving away from each other")
    ball1_speed = (100.0, 0.0)  # Moving right
    ball2_speed = (-50.0, 0.0)  # Moving left
    dx, dy = 20.0, 0.0
    distance = 20.0
    
    nx = dx / distance  # 1.0
    ny = dy / distance  # 0.0
    
    dvx = ball2_speed[0] - ball1_speed[0]  # -50 - 100 = -150
    dvy = ball2_speed[1] - ball1_speed[1]  # 0 - 0 = 0
    dvn = dvx * nx + dvy * ny  # -150 * 1.0 + 0 * 0.0 = -150
    
    print(f"  Relative velocity: ({dvx}, {dvy})")
    print(f"  Relative velocity along normal: {dvn}")
    print(f"  Should collide: {dvn < 0}")
    
    # Test case 5: One ball with very small velocity
    print("\nTest 5: One ball with very small velocity")
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.001, 0.0)  # Very small velocity
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
    
    print(f"  Before: ball1=({ball1_speed[0]}, {ball1_speed[1]}), ball2=({ball2_speed[0]}, {ball2_speed[1]})")
    print(f"  After:  ball1=({new_ball1_x:.3f}, {new_ball1_y:.3f}), ball2=({new_ball2_x:.3f}, {new_ball2_y:.3f})")

if __name__ == "__main__":
    test_edge_cases()
