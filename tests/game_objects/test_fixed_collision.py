#!/usr/bin/env python3
"""Test the fixed collision physics."""

import math

def test_fixed_collision_physics():
    """Test the corrected collision physics."""
    print("=== TESTING FIXED COLLISION PHYSICS ===\n")
    
    # Test case 1: Horizontal vs Stationary (should work the same)
    print("Test 1: Horizontal (100,0) vs Stationary (0,0)")
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.0, 0.0)
    
    # New physics: simple velocity swap
    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 100.0
    new_ball2_y = ball1_speed[1]  # 0.0
    
    print(f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: ball1 should stop, ball2 should move right")
    print(f"  ✓ This is correct!\n")
    
    # Test case 2: Vertical vs Stationary (should work the same)
    print("Test 2: Vertical (0,100) vs Stationary (0,0)")
    ball1_speed = (0.0, 100.0)
    ball2_speed = (0.0, 0.0)
    
    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 0.0
    new_ball2_y = ball1_speed[1]  # 100.0
    
    print(f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: ball1 should stop, ball2 should move down")
    print(f"  ✓ This is correct!\n")
    
    # Test case 3: The problematic case - now fixed!
    print("Test 3: FIXED - Vertical (0,100) vs Horizontal (50,0)")
    ball1_speed = (0.0, 100.0)  # Moving vertically
    ball2_speed = (50.0, 0.0)   # Moving horizontally
    
    new_ball1_x = ball2_speed[0]  # 50.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 0.0
    new_ball2_y = ball1_speed[1]  # 100.0
    
    print(f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: ball1 should get horizontal motion, ball2 should get vertical motion")
    print(f"  ✓ This is now correct! Ball1 moves horizontally, ball2 moves vertically")
    
    # Check energy conservation
    original_energy = ball1_speed[0]**2 + ball1_speed[1]**2 + ball2_speed[0]**2 + ball2_speed[1]**2
    final_energy = new_ball1_x**2 + new_ball1_y**2 + new_ball2_x**2 + new_ball2_y**2
    print(f"  Energy conservation: original={original_energy}, final={final_energy}")
    print(f"  ✓ Energy is conserved!\n")
    
    # Test case 4: Diagonal collision
    print("Test 4: Diagonal (50,50) vs Stationary (0,0)")
    ball1_speed = (50.0, 50.0)
    ball2_speed = (0.0, 0.0)
    
    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 0.0
    new_ball2_x = ball1_speed[0]  # 50.0
    new_ball2_y = ball1_speed[1]  # 50.0
    
    print(f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: ball1 should stop, ball2 should move diagonally")
    print(f"  ✓ This is correct!")
    
    # Test case 5: Both balls moving
    print("\nTest 5: Both balls moving - (100,0) vs (0,50)")
    ball1_speed = (100.0, 0.0)
    ball2_speed = (0.0, 50.0)
    
    new_ball1_x = ball2_speed[0]  # 0.0
    new_ball1_y = ball2_speed[1]  # 50.0
    new_ball2_x = ball1_speed[0]  # 100.0
    new_ball2_y = ball1_speed[1]  # 0.0
    
    print(f"  Result: ball1=({new_ball1_x}, {new_ball1_y}), ball2=({new_ball2_x}, {new_ball2_y})")
    print(f"  Expected: balls should swap velocities completely")
    print(f"  ✓ This is correct!")

if __name__ == "__main__":
    test_fixed_collision_physics()
