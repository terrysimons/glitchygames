#!/usr/bin/env python3
"""Multi-ball test with wall bouncing AND ball-to-ball collision bouncing."""

import math
import pygame
import time
import random
from glitchygames.game_objects.ball import BallSprite

def test_multi_ball_ball_collision_bounce():
    """Test multiple balls with both wall bouncing and ball-to-ball collision bouncing."""
    print("=== MULTI-BALL COLLISION BOUNCE TEST ===")
    print("Testing multiple balls with wall bouncing AND ball-to-ball collision bouncing...")
    
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
        ball.rect.x = random.randint(100, 700)
        ball.rect.y = random.randint(100, 500)
        ball.speed.x = random.uniform(-150, 150)
        ball.speed.y = random.uniform(-150, 150)
        balls.append(ball)
    
    print(f"Created {num_balls} balls with wall bouncing enabled")
    print(f"Initial ball states:")
    for i, ball in enumerate(balls):
        magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        print(f"  Ball {i+1}: pos=({ball.rect.x},{ball.rect.y}) speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) mag={magnitude:.1f}")
    
    # Track statistics
    start_time = time.time()
    wall_bounces = 0
    ball_collisions = 0
    frame_count = 0
    
    # Track trajectory data
    trajectory_data = [[] for _ in range(num_balls)]
    speed_magnitude_samples = [[] for _ in range(num_balls)]
    
    # Simulate movement
    dt = 1.0/60.0  # 60 FPS
    max_frames = 1800  # 30 seconds at 60 FPS
    
    print(f"\nRunning simulation for {max_frames} frames ({max_frames/60:.1f} seconds)...")
    
    while frame_count < max_frames and any(ball.alive() for ball in balls):
        # Check for ball-to-ball collisions
        for i in range(len(balls)):
            for j in range(i+1, len(balls)):
                if balls[i].alive() and balls[j].alive():
                    # Check if balls are colliding
                    if pygame.sprite.collide_rect(balls[i], balls[j]):
                        ball_collisions += 1
                        print(f"  Ball {i+1} and Ball {j+1} collision detected!")
                        
                        # Simple elastic collision response
                        # Calculate relative velocity
                        rel_vel_x = balls[i].speed.x - balls[j].speed.x
                        rel_vel_y = balls[i].speed.y - balls[j].speed.y
                        
                        # Calculate relative position
                        rel_pos_x = balls[i].rect.x - balls[j].rect.x
                        rel_pos_y = balls[i].rect.y - balls[j].rect.y
                        
                        # Calculate distance
                        distance = math.sqrt(rel_pos_x**2 + rel_pos_y**2)
                        
                        if distance > 0:
                            # Normalize relative position
                            norm_x = rel_pos_x / distance
                            norm_y = rel_pos_y / distance
                            
                            # Calculate relative velocity in collision normal direction
                            vel_along_normal = rel_vel_x * norm_x + rel_vel_y * norm_y
                            
                            # Do not resolve if velocities are separating
                            if vel_along_normal > 0:
                                continue
                            
                            # Calculate restitution (elastic collision)
                            restitution = 1.0
                            impulse = -(1 + restitution) * vel_along_normal
                            
                            # Apply impulse
                            impulse_x = impulse * norm_x
                            impulse_y = impulse * norm_y
                            
                            balls[i].speed.x += impulse_x
                            balls[i].speed.y += impulse_y
                            balls[j].speed.x -= impulse_x
                            balls[j].speed.y -= impulse_y
                            
                            # Separate balls to prevent sticking
                            overlap = (balls[i].width + balls[j].width) / 2 - distance
                            if overlap > 0:
                                separation_x = norm_x * overlap / 2
                                separation_y = norm_y * overlap / 2
                                
                                balls[i].rect.x += separation_x
                                balls[i].rect.y += separation_y
                                balls[j].rect.x -= separation_x
                                balls[j].rect.y -= separation_y
        
        # Update ball positions and check for wall bounces
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
                    wall_bounces += 1
                    print(f"  Ball {i+1} X wall bounce at x={new_x}")
                
                if old_y != new_y and (new_y <= 1 or new_y >= 600 - ball.height - 1):
                    wall_bounces += 1
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
            print(f"  Frame {frame_count}: {alive_count} balls alive, {wall_bounces} wall bounces, {ball_collisions} ball collisions")
    
    total_time = time.time() - start_time
    final_alive = sum(1 for ball in balls if ball.alive())
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Frames processed: {frame_count:,}")
    print(f"Balls still alive: {final_alive}")
    print(f"Wall bounces: {wall_bounces}")
    print(f"Ball-to-ball collisions: {ball_collisions}")
    
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
        print(f"  ✅ All balls survived with collision bouncing enabled")
    else:
        print(f"  ⚠️  Only {final_alive}/{num_balls} balls survived")
    
    if wall_bounces > 0:
        print(f"  ✅ Wall bouncing is working ({wall_bounces} wall bounces)")
    else:
        print(f"  ❌ No wall bounces detected")
    
    if ball_collisions > 0:
        print(f"  ✅ Ball-to-ball collision bouncing is working ({ball_collisions} collisions)")
    else:
        print(f"  ⚠️  No ball-to-ball collisions detected")
    
    pygame.quit()
    
    return final_alive, wall_bounces, ball_collisions

if __name__ == "__main__":
    alive, wall_bounces, ball_collisions = test_multi_ball_ball_collision_bounce()
    
    if alive == 5 and wall_bounces > 0:
        print(f"\n🎉 SUCCESS: All balls survived with collision bouncing!")
    elif alive > 0 and wall_bounces > 0:
        print(f"\n✅ PARTIAL SUCCESS: {alive} balls survived with {wall_bounces} wall bounces and {ball_collisions} ball collisions")
    else:
        print(f"\n❌ FAILURE: Collision bouncing system not working correctly")
