#!/usr/bin/env python3
"""Base class for multi-ball tests with configurable frame rates."""

import math
import pygame
import time
import random
from glitchygames.game_objects.ball import BallSprite

class MultiBallTestBase:
    """Base class for multi-ball collision tests."""
    
    def __init__(self, test_name, num_balls=5, enable_ball_collisions=False, enable_ball_bouncing=False):
        self.test_name = test_name
        self.num_balls = num_balls
        self.enable_ball_collisions = enable_ball_collisions
        self.enable_ball_bouncing = enable_ball_bouncing
        self.balls = []
        self.trajectory_data = []
        self.speed_magnitude_samples = []
        
    def setup_balls(self):
        """Set up balls for the test."""
        self.balls = []
        self.trajectory_data = [[] for _ in range(self.num_balls)]
        self.speed_magnitude_samples = [[] for _ in range(self.num_balls)]
        
        for i in range(self.num_balls):
            ball = BallSprite(
                bounce_top_bottom=True,   # Enable wall bouncing
                bounce_left_right=True
            )
            # Randomize starting position and speed
            ball.rect.x = random.randint(50, 750)
            ball.rect.y = random.randint(50, 550)
            ball.speed.x = random.uniform(-150, 150)
            ball.speed.y = random.uniform(-150, 150)
            self.balls.append(ball)
    
    def print_initial_state(self):
        """Print initial ball states."""
        print(f"Created {self.num_balls} balls")
        print(f"Initial ball states:")
        for i, ball in enumerate(self.balls):
            magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
            print(f"  Ball {i+1}: pos=({ball.rect.x},{ball.rect.y}) speed=({ball.speed.x:.1f},{ball.speed.y:.1f}) mag={magnitude:.1f}")
    
    def handle_ball_collisions(self):
        """Handle ball-to-ball collisions."""
        ball_collisions = 0
        
        for i in range(len(self.balls)):
            for j in range(i+1, len(self.balls)):
                if self.balls[i].alive() and self.balls[j].alive():
                    # Check if balls are colliding
                    if pygame.sprite.collide_rect(self.balls[i], self.balls[j]):
                        ball_collisions += 1
                        print(f"  Ball {i+1} and Ball {j+1} collision detected!")
                        
                        if self.enable_ball_bouncing:
                            # Elastic collision response
                            self._handle_elastic_collision(self.balls[i], self.balls[j])
                        # If not bouncing, balls just clip through each other
        
        return ball_collisions
    
    def _handle_elastic_collision(self, ball1, ball2):
        """Handle elastic collision between two balls."""
        # Calculate relative velocity
        rel_vel_x = ball1.speed.x - ball2.speed.x
        rel_vel_y = ball1.speed.y - ball2.speed.y
        
        # Calculate relative position
        rel_pos_x = ball1.rect.x - ball2.rect.x
        rel_pos_y = ball1.rect.y - ball2.rect.y
        
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
                return
            
            # Calculate restitution (elastic collision)
            restitution = 1.0
            impulse = -(1 + restitution) * vel_along_normal
            
            # Apply impulse
            impulse_x = impulse * norm_x
            impulse_y = impulse * norm_y
            
            ball1.speed.x += impulse_x
            ball1.speed.y += impulse_y
            ball2.speed.x -= impulse_x
            ball2.speed.y -= impulse_y
            
            # Separate balls to prevent sticking
            overlap = (ball1.width + ball2.width) / 2 - distance
            if overlap > 0:
                separation_x = norm_x * overlap / 2
                separation_y = norm_y * overlap / 2
                
                ball1.rect.x += separation_x
                ball1.rect.y += separation_y
                ball2.rect.x -= separation_x
                ball2.rect.y -= separation_y
    
    def update_balls(self, dt, frame_count):
        """Update ball positions and track data."""
        wall_bounces = 0
        
        for i, ball in enumerate(self.balls):
            if ball.alive():
                old_x, old_y = ball.rect.x, ball.rect.y
                old_speed_x, old_speed_y = ball.speed.x, ball.speed.y
                
                ball.dt_tick(dt)
                
                new_x, new_y = ball.rect.x, ball.rect.y
                new_speed_x, new_speed_y = ball.speed.x, ball.speed.y
                
                # Track trajectory
                self.trajectory_data[i].append((new_x, new_y))
                
                # Check for wall bounces
                if old_x != new_x and (new_x <= 1 or new_x >= 800 - ball.width - 1):
                    wall_bounces += 1
                    print(f"  Ball {i+1} X wall bounce at x={new_x}")
                
                if old_y != new_y and (new_y <= 1 or new_y >= 600 - ball.height - 1):
                    wall_bounces += 1
                    print(f"  Ball {i+1} Y wall bounce at y={new_y}")
                
                # Sample speed magnitude every 60 frames (1 second at 60 FPS)
                if frame_count % 60 == 0:
                    current_magnitude = math.sqrt(new_speed_x**2 + new_speed_y**2)
                    self.speed_magnitude_samples[i].append(current_magnitude)
        
        return wall_bounces
    
    def run_test(self, fps, duration_seconds):
        """Run the test with specified FPS and duration."""
        print(f"=== {self.test_name} ===")
        print(f"Testing at {fps} FPS for {duration_seconds} seconds...")
        
        # Initialize pygame
        pygame.init()
        screen = pygame.display.set_mode((800, 600))
        
        # Set up balls
        self.setup_balls()
        self.print_initial_state()
        
        # Calculate test parameters
        if fps == float('inf'):
            dt = 0.0  # No time step for infinite FPS
            max_frames = int(60 * duration_seconds)  # Use 60 FPS as base for infinite
        else:
            dt = 1.0 / fps
            max_frames = int(fps * duration_seconds)
        
        print(f"\nRunning simulation for {max_frames} frames ({duration_seconds} seconds)...")
        
        # Track statistics
        start_time = time.time()
        total_wall_bounces = 0
        total_ball_collisions = 0
        frame_count = 0
        
        # Run simulation
        while frame_count < max_frames and any(ball.alive() for ball in self.balls):
            # Handle ball-to-ball collisions
            if self.enable_ball_collisions:
                ball_collisions = self.handle_ball_collisions()
                total_ball_collisions += ball_collisions
            
            # Update ball positions
            if fps == float('inf'):
                # For infinite FPS, use a very small dt to simulate continuous movement
                wall_bounces = self.update_balls(0.001, frame_count)
            else:
                wall_bounces = self.update_balls(dt, frame_count)
            total_wall_bounces += wall_bounces
            
            frame_count += 1
            
            # Report progress every 300 frames (5 seconds at 60 FPS)
            if frame_count % 300 == 0:
                alive_count = sum(1 for ball in self.balls if ball.alive())
                elapsed = time.time() - start_time
                print(f"  Frame {frame_count}: {alive_count} balls alive, {total_wall_bounces} wall bounces, {total_ball_collisions} ball collisions")
        
        total_time = time.time() - start_time
        final_alive = sum(1 for ball in self.balls if ball.alive())
        
        # Print results
        self.print_results(total_time, frame_count, final_alive, total_wall_bounces, total_ball_collisions)
        
        pygame.quit()
        
        return final_alive, total_wall_bounces, total_ball_collisions
    
    def print_results(self, total_time, frame_count, final_alive, wall_bounces, ball_collisions):
        """Print test results."""
        print(f"\n=== FINAL RESULTS ===")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Frames processed: {frame_count:,}")
        print(f"Balls still alive: {final_alive}")
        print(f"Wall bounces: {wall_bounces}")
        print(f"Ball-to-ball collisions: {ball_collisions}")
        
        # Analyze trajectory data
        print(f"\n=== TRAJECTORY ANALYSIS ===")
        for i, ball in enumerate(self.balls):
            if ball.alive() and self.trajectory_data[i]:
                positions = self.trajectory_data[i]
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
                if self.speed_magnitude_samples[i]:
                    magnitudes = self.speed_magnitude_samples[i]
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
        if final_alive == self.num_balls:
            print(f"  ✅ All balls survived")
        else:
            print(f"  ⚠️  Only {final_alive}/{self.num_balls} balls survived")
        
        if wall_bounces > 0:
            print(f"  ✅ Wall bouncing is working ({wall_bounces} wall bounces)")
        else:
            print(f"  ❌ No wall bounces detected")
        
        if self.enable_ball_collisions:
            if ball_collisions > 0:
                if self.enable_ball_bouncing:
                    print(f"  ✅ Ball-to-ball collision bouncing is working ({ball_collisions} collisions)")
                else:
                    print(f"  ✅ Ball-to-ball collision clipping is working ({ball_collisions} collisions clipped)")
            else:
                print(f"  ⚠️  No ball-to-ball collisions detected")
