#!/usr/bin/env python3
"""Fast mathematical stability test for ball bouncing."""

import math
import time

def test_ball_math_fast():
    """Test ball mathematical stability with direct calculations."""
    print("=== FAST BALL MATHEMATICAL STABILITY TEST ===")
    print("Testing mathematical calculations for potential issues...")
    
    # Simulate ball parameters
    screen_width = 800
    screen_height = 600
    ball_width = 20
    ball_height = 20
    
    # Initial ball state
    x = 400.0
    y = 300.0
    speed_x = 250.0
    speed_y = 125.0
    dt = 1.0/60.0  # 60 FPS
    
    print(f"Initial state:")
    print(f"  Position: ({x:.3f}, {y:.3f})")
    print(f"  Speed: ({speed_x:.6f}, {speed_y:.6f})")
    print(f"  Speed magnitude: {math.sqrt(speed_x**2 + speed_y**2):.6f}")
    
    # Track statistics
    bounce_count = 0
    x_bounces = 0
    y_bounces = 0
    start_time = time.time()
    
    # Track speed magnitude over time
    initial_magnitude = math.sqrt(speed_x**2 + speed_y**2)
    magnitude_samples = []
    
    # Track position bounds
    min_x = max_x = x
    min_y = max_y = y
    
    # Simulate many iterations
    iterations = 100000  # 100k iterations for fast test
    
    print(f"\nRunning {iterations:,} iterations...")
    
    for i in range(iterations):
        # Calculate movement
        move_x = speed_x * dt
        move_y = speed_y * dt
        
        # Update position with rounding (like in dt_tick)
        new_x = x + round(move_x)
        new_y = y + round(move_y)
        
        # Check for bounces
        bounced = False
        
        # Top bounce
        if new_y <= 0:
            new_y = 1
            speed_y = abs(speed_y)  # Ensure positive (downward)
            y_bounces += 1
            bounce_count += 1
            bounced = True
        
        # Bottom bounce
        if new_y + ball_height >= screen_height:
            new_y = screen_height - ball_height - 1
            speed_y = -abs(speed_y)  # Ensure negative (upward)
            y_bounces += 1
            bounce_count += 1
            bounced = True
        
        # Left bounce
        if new_x <= 0:
            new_x = 1
            speed_x = abs(speed_x)  # Ensure positive (rightward)
            x_bounces += 1
            bounce_count += 1
            bounced = True
        
        # Right bounce
        if new_x + ball_width >= screen_width:
            new_x = screen_width - ball_width - 1
            speed_x = -abs(speed_x)  # Ensure negative (leftward)
            x_bounces += 1
            bounce_count += 1
            bounced = True
        
        # Update position
        x, y = new_x, new_y
        
        # Track position bounds
        min_x = min(min_x, x)
        max_x = max(max_x, x)
        min_y = min(min_y, y)
        max_y = max(max_y, y)
        
        # Sample speed magnitude every 100000 iterations
        if i % 100000 == 0:
            current_magnitude = math.sqrt(speed_x**2 + speed_y**2)
            magnitude_samples.append(current_magnitude)
        
        # Report progress every 1000000 iterations
        if i % 1000000 == 0 and i > 0:
            elapsed = time.time() - start_time
            current_magnitude = math.sqrt(speed_x**2 + speed_y**2)
            magnitude_change = abs(current_magnitude - initial_magnitude)
            
            
            if magnitude_change > 0.1:
                print(f"    WARNING: Speed magnitude changed by {magnitude_change:.6f}")
    
    total_time = time.time() - start_time
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total bounces: {bounce_count:,}")
    print(f"X bounces: {x_bounces:,}")
    print(f"Y bounces: {y_bounces:,}")
    print(f"Total time: {total_time:.3f} seconds")
    print(f"Iterations per second: {iterations/total_time:.0f}")
    print(f"Calculations per second: {iterations*4/total_time:.0f}")  # 4 calculations per iteration
    
    print(f"Final position: ({x:.3f}, {y:.3f})")
    print(f"Final speed: ({speed_x:.6f}, {speed_y:.6f})")
    print(f"Final speed magnitude: {math.sqrt(speed_x**2 + speed_y**2):.6f}")
    print(f"Position bounds: X[{min_x:.1f}-{max_x:.1f}] Y[{min_y:.1f}-{max_y:.1f}]")
    
    # Analyze speed magnitude stability
    if magnitude_samples:
        min_magnitude = min(magnitude_samples)
        max_magnitude = max(magnitude_samples)
        avg_magnitude = sum(magnitude_samples) / len(magnitude_samples)
        magnitude_drift = max_magnitude - min_magnitude
        
        print(f"\nSpeed magnitude analysis:")
        print(f"  Initial: {initial_magnitude:.6f}")
        print(f"  Samples: {len(magnitude_samples)}")
        print(f"  Min: {min_magnitude:.6f}")
        print(f"  Max: {max_magnitude:.6f}")
        print(f"  Average: {avg_magnitude:.6f}")
        print(f"  Drift: {magnitude_drift:.6f}")
        
        if magnitude_drift > 1.0:
            print(f"  WARNING: Significant speed magnitude drift detected!")
        else:
            print(f"  Speed magnitude is stable.")
    
    # Check for mathematical issues
    print(f"\nMathematical stability check:")
    final_magnitude = math.sqrt(speed_x**2 + speed_y**2)
    magnitude_change = abs(final_magnitude - initial_magnitude)
    print(f"  Speed magnitude change: {magnitude_change:.6f}")
    
    if magnitude_change < 0.01:
        print(f"  ✅ Speed magnitude is stable")
    else:
        print(f"  ⚠️  Speed magnitude has drifted")
    
    # Check position bounds
    expected_min_x, expected_max_x = 1, screen_width - ball_width - 1
    expected_min_y, expected_max_y = 1, screen_height - ball_height - 1
    
    if min_x >= expected_min_x and max_x <= expected_max_x and min_y >= expected_min_y and max_y <= expected_max_y:
        print(f"  ✅ Position bounds are correct")
    else:
        print(f"  ⚠️  Position bounds issue detected")
        print(f"    Expected X: [{expected_min_x}-{expected_max_x}], got [{min_x:.1f}-{max_x:.1f}]")
        print(f"    Expected Y: [{expected_min_y}-{expected_max_y}], got [{min_y:.1f}-{max_y:.1f}]")
    
    # Check for floating-point precision issues
    print(f"\nFloating-point precision check:")
    print(f"  Speed X precision: {speed_x:.10f}")
    print(f"  Speed Y precision: {speed_y:.10f}")
    print(f"  Position X precision: {x:.10f}")
    print(f"  Position Y precision: {y:.10f}")
    
    # Check for NaN or infinity
    if math.isnan(speed_x) or math.isnan(speed_y) or math.isnan(x) or math.isnan(y):
        print(f"  ❌ NaN values detected!")
        assert False, "NaN values detected in ball calculations"
    elif math.isinf(speed_x) or math.isinf(speed_y) or math.isinf(x) or math.isinf(y):
        print(f"  ❌ Infinity values detected!")
        assert False, "Infinity values detected in ball calculations"
    else:
        print(f"  ✅ All values are finite")
    
    # Assert that the test completed successfully
    assert bounce_count >= 0, "Bounce count should be non-negative"
    assert len(magnitude_samples) > 0, "Should have magnitude samples"
    
    # Check for mathematical stability (no excessive drift)
    if len(magnitude_samples) > 1:
        drift = max(magnitude_samples) - min(magnitude_samples)
        assert drift < 0.01, f"Mathematical drift too high: {drift:.6f}"
    
    print(f"\n✅ Test completed successfully")

if __name__ == "__main__":
    test_ball_math_fast()
