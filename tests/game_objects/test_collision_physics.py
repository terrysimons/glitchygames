#!/usr/bin/env python3
"""Test collision physics with zero velocity components."""

import math

def test_collision_physics():
    """Test collision physics with various velocity combinations."""
    print("Testing collision physics with zero velocity components...")
    
    # Test case 1: One ball moving horizontally, one stationary
    print("\nTest 1: Horizontal vs Stationary")
    ball1_speed = (100.0, 0.0)  # Moving right
    ball2_speed = (0.0, 0.0)    # Stationary
    dx, dy = 20.0, 0.0  # Ball2 is to the right of ball1
    distance = 20.0
    
    # Current physics calculation
    nx = dx / distance  # 1.0
    ny = dy / distance  # 0.0
    
    v1n = ball1_speed[0] * nx + ball1_speed[1] * ny  # 100.0
    v2n = ball2_speed[0] * nx + ball2_speed[1] * ny  # 0.0
    
    # Exchange velocities
    new_ball1_x = ball1_speed[0] - v1n * nx + v2n * nx  # 100 - 100 + 0 = 0
    new_ball1_y = ball1_speed[1] - v1n * ny + v2n * ny  # 0 - 0 + 0 = 0
    new_ball2_x = ball2_speed[0] - v2n * nx + v1n * nx  # 0 - 0 + 100 = 100
    new_ball2_y = ball2_speed[1] - v2n * ny + v1n * ny  # 0 - 0 + 0 = 0
    
    print(f"  Before: ball1=({ball1_speed[0]}, {ball1_speed[1]}), ball2=({ball2_speed[0]}, {ball2_speed[1]})")
    print(f"  After:  ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: ball1 should stop, ball2 should move right")
    
    # Test case 2: One ball moving vertically, one stationary
    print("\nTest 2: Vertical vs Stationary")
    ball1_speed = (0.0, 100.0)  # Moving down
    ball2_speed = (0.0, 0.0)    # Stationary
    dx, dy = 0.0, 20.0  # Ball2 is below ball1
    distance = 20.0
    
    nx = dx / distance  # 0.0
    ny = dy / distance  # 1.0
    
    v1n = ball1_speed[0] * nx + ball1_speed[1] * ny  # 100.0
    v2n = ball2_speed[0] * nx + ball2_speed[1] * ny  # 0.0
    
    new_ball1_x = ball1_speed[0] - v1n * nx + v2n * nx  # 0 - 0 + 0 = 0
    new_ball1_y = ball1_speed[1] - v1n * ny + v2n * ny  # 100 - 100 + 0 = 0
    new_ball2_x = ball2_speed[0] - v2n * nx + v1n * nx  # 0 - 0 + 0 = 0
    new_ball2_y = ball2_speed[1] - v2n * ny + v1n * ny  # 0 - 0 + 100 = 100
    
    print(f"  Before: ball1=({ball1_speed[0]}, {ball1_speed[1]}), ball2=({ball2_speed[0]}, {ball2_speed[1]})")
    print(f"  After:  ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: ball1 should stop, ball2 should move down")
    
    # Test case 3: Diagonal collision with zero components
    print("\nTest 3: Diagonal vs Stationary")
    ball1_speed = (50.0, 50.0)  # Moving diagonally
    ball2_speed = (0.0, 0.0)    # Stationary
    dx, dy = 14.14, 14.14  # 45-degree angle
    distance = math.sqrt(dx*dx + dy*dy)  # ~20.0
    
    nx = dx / distance  # ~0.707
    ny = dy / distance  # ~0.707
    
    v1n = ball1_speed[0] * nx + ball1_speed[1] * ny  # ~70.7
    v2n = ball2_speed[0] * nx + ball2_speed[1] * ny  # 0.0
    
    new_ball1_x = ball1_speed[0] - v1n * nx + v2n * nx
    new_ball1_y = ball1_speed[1] - v1n * ny + v2n * ny
    new_ball2_x = ball2_speed[0] - v2n * nx + v1n * nx
    new_ball2_y = ball2_speed[1] - v2n * ny + v1n * ny
    
    print(f"  Before: ball1=({ball1_speed[0]}, {ball1_speed[1]}), ball2=({ball2_speed[0]}, {ball2_speed[1]})")
    print(f"  After:  ball1=({new_ball1_x:.1f}, {new_ball1_y:.1f}), ball2=({new_ball2_x:.1f}, {new_ball2_y:.1f})")
    print(f"  Expected: ball1 should stop, ball2 should move diagonally")

if __name__ == "__main__":
    test_collision_physics()
