#!/usr/bin/env python3
"""Multi-ball test with wall bouncing enabled (no ball-to-ball collisions)."""

import math
import pygame
import time
import random
from glitchygames.game_objects.ball import BallSprite

def test_multi_ball_wall_bounce():
    """Test multiple balls with wall bouncing enabled."""
    print("=== MULTI-BALL WALL BOUNCE TEST ===")
    print("Testing multiple balls with wall bouncing enabled...")
    
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    
    # Create multiple balls with wall bouncing enabled
    num_balls = 5
    balls = []
    
    for i in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=True,   # Enable wall bouncing
            bounce_left_right=True
        )
        # Randomize starting position and speed
        ball.rect.x = random.randint(50, 750)
        ball.rect.y = random.randint(50, 550)
        ball.speed.x = random.uniform(-200, 200)
        ball.speed.y = random.uniform(-200, 200)
        balls.append(ball)
    
    print(f"Created {num_balls} balls with wall bouncing enabled")
    print(f"Initial ball states:")
    for i, ball in enumerate(balls):
        magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        print(f"  Ball {i+1}: pos=({ball.rect.x},{ball.rect.y}) speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) mag={magnitude:.1f}")
    
    # Track statistics
    start_time = time.time()
    total_bounces = 0
    x_bounces = 0
    y_bounces = 0
    frame_count = 0
    
    # Track trajectory data
    trajectory_data = [[] for _ in range(num_balls)]
    speed_magnitude_samples = [[] for _ in range(num_balls)]
    
    # Simulate movement
    dt = 1.0/60.0  # 60 FPS
    max_frames = 1800  # 30 seconds at 60 FPS
    
    print(f"\nRunning simulation for {max_frames} frames ({max_frames/60:.1f} seconds)...")
    
    while frame_count < max_frames and any(ball.alive() for ball in balls):
        for i, ball in enumerate(balls):
            if ball.alive():
                old_x, old_y = ball.rect.x, ball.rect.y
                old_speed_x, old_speed_y = ball.speed.x, ball.speed.y
                
                ball.dt_tick(dt)
                
                new_x, new_y = ball.rect.x, ball.rect.y
                new_speed_x, new_speed_y = ball.speed.x, ball.speed.y
                
                # Track trajectory
                trajectory_data[i].append((new_x, new_y))
                
                # Check for wall bounces
                if old_x != new_x and (new_x <= 1 or new_x >= 800 - ball.width - 1):
                    x_bounces += 1
                    total_bounces += 1
                    print(f"  Ball {i+1} X wall bounce at x={new_x}")
                
                if old_y != new_y and (new_y <= 1 or new_y >= 600 - ball.height - 1):
                    y_bounces += 1
                    total_bounces += 1
                    print(f"  Ball {i+1} Y wall bounce at y={new_y}")
                
                # Sample speed magnitude every 60 frames (1 second)
                if frame_count % 60 == 0:
                    current_magnitude = math.sqrt(new_speed_x**2 + new_speed_y**2)
                    speed_magnitude_samples[i].append(current_magnitude)
        
        frame_count += 1
        
        # Report progress every 300 frames (5 seconds)
        if frame_count % 300 == 0:
            alive_count = sum(1 for ball in balls if ball.alive())
            elapsed = time.time() - start_time
            print(f"  Frame {frame_count}: {alive_count} balls alive, {total_bounces} total bounces")
    
    total_time = time.time() - start_time
    final_alive = sum(1 for ball in balls if ball.alive())
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Frames processed: {frame_count:,}")
    print(f"Balls still alive: {final_alive}")
    print(f"Total wall bounces: {total_bounces}")
    print(f"X wall bounces: {x_bounces}")
    print(f"Y wall bounces: {y_bounces}")
    
    # Analyze trajectory data
    print(f"\n=== TRAJECTORY ANALYSIS ===")
    for i, ball in enumerate(balls):
        if ball.alive() and trajectory_data[i]:
            positions = trajectory_data[i]
            x_positions = [pos[0] for pos in positions]
            y_positions = [pos[1] for pos in positions]
            
            # Check position bounds
            min_x, max_x = min(x_positions), max(x_positions)
            min_y, max_y = min(y_positions), max(y_positions)
            
            print(f"Ball {i+1} trajectory:")
            print(f"  Position bounds: X[{min_x:.1f}-{max_x:.1f}] Y[{min_y:.1f}-{max_y:.1f}]")
            print(f"  Final position: ({ball.rect.x}, {ball.rect.y})")
            print(f"  Final speed: ({ball.speed.x:.3f}, {ball.speed.y:.3f})")
            print(f"  Final magnitude: {math.sqrt(ball.speed.x**2 + ball.speed.y**2):.3f}")
            
            # Check for trajectory issues
            x_drift = max_x - min_x
            y_drift = max_y - min_y
            
            if x_drift > 50 or y_drift > 50:
                print(f"  ⚠️  Significant position drift detected")
            else:
                print(f"  ✅ Position is stable")
            
            # Check speed magnitude stability
            if speed_magnitude_samples[i]:
                magnitudes = speed_magnitude_samples[i]
                min_mag = min(magnitudes)
                max_mag = max(magnitudes)
                drift = max_mag - min_mag
                
                print(f"  Speed magnitude: min={min_mag:.3f}, max={max_mag:.3f}, drift={drift:.6f}")
                
                if drift < 0.01:
                    print(f"  ✅ Speed magnitude is stable")
                else:
                    print(f"  ⚠️  Speed magnitude drift detected")
    
    # Overall analysis
    print(f"\n=== OVERALL ANALYSIS ===")
    if final_alive == num_balls:
        print(f"  ✅ All balls survived with wall bouncing enabled")
    else:
        print(f"  ⚠️  Only {final_alive}/{num_balls} balls survived")
    
    if total_bounces > 0:
        print(f"  ✅ Wall bouncing is working ({total_bounces} total bounces)")
    else:
        print(f"  ❌ No wall bounces detected - bouncing may be disabled")
    
    pygame.quit()
    
    # Assert that the test completed successfully
    assert final_alive > 0, "At least one ball should survive"
    assert total_bounces > 0, "Wall bouncing should be working"
    
    print(f"\n✅ Test completed successfully")

if __name__ == "__main__":
    test_multi_ball_wall_bounce()
