#!/usr/bin/env python3
"""Multi-ball test with bouncing disabled (Paddle Slap style)."""

import math
import pygame
import time
import random
from glitchygames.game_objects.ball import BallSprite

def test_multi_ball_no_bounce():
    """Test multiple balls with bouncing disabled."""
    print("=== MULTI-BALL NO BOUNCE TEST ===")
    print("Testing multiple balls with bouncing disabled (Paddle Slap style)...")
    
    # Initialize pygame
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    
    # Create multiple balls with bouncing disabled
    num_balls = 10
    balls = []
    
    for i in range(num_balls):
        ball = BallSprite(
            bounce_top_bottom=False,  # No bouncing - balls should die on boundaries
            bounce_left_right=False
        )
        # Randomize starting position and speed
        ball.rect.x = random.randint(100, 700)
        ball.rect.y = random.randint(100, 500)
        ball.speed.x = random.uniform(-300, 300)
        ball.speed.y = random.uniform(-300, 300)
        balls.append(ball)
    
    print(f"Created {num_balls} balls with bouncing disabled")
    print(f"Initial ball states:")
    for i, ball in enumerate(balls):
        print(f"  Ball {i+1}: pos=({ball.rect.x},{ball.rect.y}) speed=({ball.speed.x:.1f},{ball.speed.y:.1f})")
    
    # Track statistics
    start_time = time.time()
    total_bounces = 0
    balls_died = 0
    frame_count = 0
    
    # Simulate movement
    dt = 1.0/60.0  # 60 FPS
    max_frames = 3600  # 60 seconds at 60 FPS
    
    print(f"\nRunning simulation for {max_frames} frames ({max_frames/60:.1f} seconds)...")
    
    while frame_count < max_frames and any(ball.alive() for ball in balls):
        for i, ball in enumerate(balls):
            if ball.alive():
                old_x, old_y = ball.rect.x, ball.rect.y
                ball.dt_tick(dt)
                new_x, new_y = ball.rect.x, ball.rect.y
                
                # Check for boundary bouncing (should not happen)
                if (old_x != new_x and (new_x <= 1 or new_x >= 800 - ball.width - 1)) or \
                   (old_y != new_y and (new_y <= 1 or new_y >= 600 - ball.height - 1)):
                    total_bounces += 1
                    print(f"  WARNING: Ball {i+1} bounced at boundary - bouncing should be disabled!")
                
                # Check if ball died
                if not ball.alive():
                    balls_died += 1
                    print(f"  Ball {i+1} died at position ({new_x}, {new_y})")
        
        frame_count += 1
        
        # Report progress every 600 frames (10 seconds)
        if frame_count % 600 == 0:
            alive_count = sum(1 for ball in balls if ball.alive())
            elapsed = time.time() - start_time
            print(f"  Frame {frame_count}: {alive_count} balls alive, {balls_died} died, {total_bounces} movements")
    
    total_time = time.time() - start_time
    final_alive = sum(1 for ball in balls if ball.alive())
    
    print(f"\n=== FINAL RESULTS ===")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Frames processed: {frame_count:,}")
    print(f"Balls that died: {balls_died}")
    print(f"Balls still alive: {final_alive}")
    print(f"Total movements: {total_bounces}")
    
    # Check for any balls that shouldn't be alive
    for i, ball in enumerate(balls):
        if ball.alive():
            print(f"  Ball {i+1} still alive at position ({ball.rect.x}, {ball.rect.y})")
            print(f"    Speed: ({ball.speed.x:.3f}, {ball.speed.y:.3f})")
            print(f"    Bounce settings: top/bottom={ball.bounce_top_bottom}, left/right={ball.bounce_left_right}")
    
    # Analyze results
    print(f"\nAnalysis:")
    if total_bounces == 0:
        print(f"  ✅ No unexpected movements detected")
    else:
        print(f"  ⚠️  {total_bounces} unexpected movements detected")
    
    if balls_died == num_balls:
        print(f"  ✅ All balls died as expected (no bouncing)")
    elif balls_died > 0:
        print(f"  ⚠️  Only {balls_died}/{num_balls} balls died")
    else:
        print(f"  ❌ No balls died - bouncing may be enabled incorrectly")
    
    pygame.quit()
    
    return balls_died, total_bounces, final_alive

if __name__ == "__main__":
    died, movements, alive = test_multi_ball_no_bounce()
    
    if died == 10 and movements == 0:
        print(f"\n🎉 SUCCESS: All balls died without bouncing as expected!")
    elif died > 0:
        print(f"\n✅ PARTIAL SUCCESS: {died} balls died, {movements} unexpected movements")
    else:
        print(f"\n❌ FAILURE: No balls died, bouncing may be incorrectly enabled")
