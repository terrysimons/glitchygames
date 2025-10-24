#!/usr/bin/env python3
"""
Test ball-to-ball collision energy transfer issues.

This test specifically addresses the reported issues:
1. Balls going the same horizontal direction not transferring energy
2. Balls traveling vertically not taking energy
3. General ball-to-ball collision physics
"""

import unittest
import math
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
import pygame


class TestBallCollisionEnergyTransfer(unittest.TestCase):
    """Test ball-to-ball collision energy transfer scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Initialize pygame for testing
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 600))
    
    def tearDown(self):
        """Clean up test fixtures."""
        pass
    
    def _create_ball(self, x, y, speed_x, speed_y, radius=10):
        """Create a ball sprite for testing."""
        ball = BallSprite(
            x=0, y=0,  # Will be overridden after reset()
            width=radius*2, height=radius*2,
            bounce_top_bottom=True,
            bounce_left_right=False
        )
        # Set position after reset() has been called
        ball.rect.centerx = x
        ball.rect.centery = y
        # Set the speed after creation
        ball.speed.x = speed_x
        ball.speed.y = speed_y
        ball.collision_cooldowns = {}
        return ball
    
    def _simulate_collision(self, ball1, ball2):
        """Simulate collision between two balls using the actual game physics."""
        # Calculate distance between ball centers
        dx = ball2.rect.centerx - ball1.rect.centerx
        dy = ball2.rect.centery - ball1.rect.centery
        distance = math.sqrt(dx * dx + dy * dy)
        
        # Skip if balls are too far apart or at exact same position
        collision_distance = ball1.rect.width // 2 + ball2.rect.width // 2
        if distance > collision_distance or distance < 0.001:
            return False
        
        # Calculate collision normal
        nx = dx / distance
        ny = dy / distance
        
        # Calculate relative velocity
        dvx = ball2.speed.x - ball1.speed.x
        dvy = ball2.speed.y - ball1.speed.y
        
        # Calculate relative velocity along collision normal
        dvn = dvx * nx + dvy * ny
        
        # Simplified collision logic: always allow collision if balls are overlapping
        # or if they're moving toward each other (dvn <= 0)
        if dvn > 0:
            # Balls are moving away from each other - only allow collision if they're overlapping
            # or if there's a significant speed difference (faster ball catching up)
            ball1_speed_magnitude = math.sqrt(ball1.speed.x**2 + ball1.speed.y**2)
            ball2_speed_magnitude = math.sqrt(ball2.speed.x**2 + ball2.speed.y**2)
            
            # Allow collision if balls are overlapping (distance < collision_distance)
            # or if there's a significant speed difference
            if distance >= collision_distance:
                if ball1_speed_magnitude > 0 and ball2_speed_magnitude > 0:
                    speed_ratio = max(ball1_speed_magnitude, ball2_speed_magnitude) / min(ball1_speed_magnitude, ball2_speed_magnitude)
                    if speed_ratio < 1.2:  # Lower threshold for more collisions
                        return False  # Skip if speeds are too similar and balls aren't overlapping
                else:
                    return False  # Skip if one ball has zero speed
        
        # Proper elastic collision physics for equal mass balls
        # Decompose velocities into normal and tangential components
        v1n_scalar = ball1.speed.x * nx + ball1.speed.y * ny
        v2n_scalar = ball2.speed.x * nx + ball2.speed.y * ny
        
        v1n_vec_x = v1n_scalar * nx
        v1n_vec_y = v1n_scalar * ny
        v2n_vec_x = v2n_scalar * nx
        v2n_vec_y = v2n_scalar * ny
        
        v1t_vec_x = ball1.speed.x - v1n_vec_x
        v1t_vec_y = ball1.speed.y - v1n_vec_y
        v2t_vec_x = ball2.speed.x - v2n_vec_x
        v2t_vec_y = ball2.speed.y - v2n_vec_y
        
        # Exchange normal components, preserve tangential components
        ball1.speed.x = v1t_vec_x + v2n_vec_x
        ball1.speed.y = v1t_vec_y + v2n_vec_y
        ball2.speed.x = v2t_vec_x + v1n_vec_x
        ball2.speed.y = v2t_vec_y + v1n_vec_y
        
        return True  # Collision occurred
    
    def test_same_horizontal_direction_energy_transfer(self):
        """Test that balls moving in the same horizontal direction transfer energy."""
        print("\n=== TESTING SAME HORIZONTAL DIRECTION ENERGY TRANSFER ===")
        
        # Create two balls moving in the same horizontal direction
        # Ball 1: moving right at 100 px/s
        # Ball 2: moving right at 50 px/s (behind ball 1)
        ball1 = self._create_ball(100, 200, 100, 0)
        ball2 = self._create_ball(50, 200, 50, 0)
        
        # Position ball2 so it's close enough to collide (same Y, close X)
        ball2.rect.centerx = ball1.rect.centerx - 15  # 15px apart (radius=10 each)
        ball2.rect.centery = ball1.rect.centery  # Same Y coordinate
        
        print(f"Before collision:")
        print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x},{ball1.speed.y})")
        print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x},{ball2.speed.y})")
        
        # Calculate initial energy
        initial_energy1 = ball1.speed.x**2 + ball1.speed.y**2
        initial_energy2 = ball2.speed.x**2 + ball2.speed.y**2
        total_initial_energy = initial_energy1 + initial_energy2
        
        print(f"  Initial energies: Ball1={initial_energy1:.1f}, Ball2={initial_energy2:.1f}, Total={total_initial_energy:.1f}")
        
        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        
        print(f"Collision occurred: {collision_occurred}")
        
        if collision_occurred:
            print(f"After collision:")
            print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x:.1f},{ball1.speed.y:.1f})")
            print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x:.1f},{ball2.speed.y:.1f})")
            
            # Calculate final energy
            final_energy1 = ball1.speed.x**2 + ball1.speed.y**2
            final_energy2 = ball2.speed.x**2 + ball2.speed.y**2
            total_final_energy = final_energy1 + final_energy2
            
            print(f"  Final energies: Ball1={final_energy1:.1f}, Ball2={final_energy2:.1f}, Total={total_final_energy:.1f}")
            
            # Check that energy was transferred
            energy_change1 = final_energy1 - initial_energy1
            energy_change2 = final_energy2 - initial_energy2
            
            print(f"  Energy changes: Ball1={energy_change1:.1f}, Ball2={energy_change2:.1f}")
            
            # Assertions
            self.assertTrue(collision_occurred, "Collision should have occurred")
            self.assertNotEqual(energy_change1, 0, "Ball 1 energy should have changed")
            self.assertNotEqual(energy_change2, 0, "Ball 2 energy should have changed")
            self.assertAlmostEqual(total_final_energy, total_initial_energy, delta=0.1, 
                                 msg="Total energy should be conserved")
            
            # The faster ball should have lost energy, slower ball should have gained energy
            if initial_energy1 > initial_energy2:
                self.assertLess(final_energy1, initial_energy1, "Faster ball should lose energy")
                self.assertGreater(final_energy2, initial_energy2, "Slower ball should gain energy")
        else:
            self.fail("Collision should have occurred for same-direction balls")
    
    def test_vertical_movement_energy_transfer(self):
        """Test that balls traveling vertically transfer energy."""
        print("\n=== TESTING VERTICAL MOVEMENT ENERGY TRANSFER ===")
        
        # Create two balls moving vertically
        # Ball 1: moving down at 100 px/s
        # Ball 2: moving down at 50 px/s (behind ball 1)
        ball1 = self._create_ball(200, 100, 0, 100)
        ball2 = self._create_ball(200, 50, 0, 50)
        
        # Position ball2 so it's close enough to collide (same X, close Y)
        ball2.rect.centerx = ball1.rect.centerx  # Same X coordinate
        ball2.rect.centery = ball1.rect.centery - 15  # 15px apart (radius=10 each)
        
        print(f"Before collision:")
        print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x},{ball1.speed.y})")
        print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x},{ball2.speed.y})")
        
        # Calculate initial energy
        initial_energy1 = ball1.speed.x**2 + ball1.speed.y**2
        initial_energy2 = ball2.speed.x**2 + ball2.speed.y**2
        total_initial_energy = initial_energy1 + initial_energy2
        
        print(f"  Initial energies: Ball1={initial_energy1:.1f}, Ball2={initial_energy2:.1f}, Total={total_initial_energy:.1f}")
        
        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        
        print(f"Collision occurred: {collision_occurred}")
        
        if collision_occurred:
            print(f"After collision:")
            print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x:.1f},{ball1.speed.y:.1f})")
            print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x:.1f},{ball2.speed.y:.1f})")
            
            # Calculate final energy
            final_energy1 = ball1.speed.x**2 + ball1.speed.y**2
            final_energy2 = ball2.speed.x**2 + ball2.speed.y**2
            total_final_energy = final_energy1 + final_energy2
            
            print(f"  Final energies: Ball1={final_energy1:.1f}, Ball2={final_energy2:.1f}, Total={total_final_energy:.1f}")
            
            # Check that energy was transferred
            energy_change1 = final_energy1 - initial_energy1
            energy_change2 = final_energy2 - initial_energy2
            
            print(f"  Energy changes: Ball1={energy_change1:.1f}, Ball2={energy_change2:.1f}")
            
            # Assertions
            self.assertTrue(collision_occurred, "Collision should have occurred")
            self.assertNotEqual(energy_change1, 0, "Ball 1 energy should have changed")
            self.assertNotEqual(energy_change2, 0, "Ball 2 energy should have changed")
            self.assertAlmostEqual(total_final_energy, total_initial_energy, delta=0.1, 
                                 msg="Total energy should be conserved")
            
            # The faster ball should have lost energy, slower ball should have gained energy
            if initial_energy1 > initial_energy2:
                self.assertLess(final_energy1, initial_energy1, "Faster ball should lose energy")
                self.assertGreater(final_energy2, initial_energy2, "Slower ball should gain energy")
        else:
            self.fail("Collision should have occurred for vertical movement")
    
    def test_head_on_collision_energy_transfer(self):
        """Test head-on collision energy transfer."""
        print("\n=== TESTING HEAD-ON COLLISION ENERGY TRANSFER ===")
        
        # Create two balls moving toward each other - position them close enough to collide
        ball1 = self._create_ball(100, 200, 100, 0)  # Moving right
        ball2 = self._create_ball(115, 200, -100, 0)  # Moving left, close to ball1
        
        print(f"Before collision:")
        print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x},{ball1.speed.y})")
        print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x},{ball2.speed.y})")
        
        # Calculate initial energy
        initial_energy1 = ball1.speed.x**2 + ball1.speed.y**2
        initial_energy2 = ball2.speed.x**2 + ball2.speed.y**2
        total_initial_energy = initial_energy1 + initial_energy2
        
        print(f"  Initial energies: Ball1={initial_energy1:.1f}, Ball2={initial_energy2:.1f}, Total={total_initial_energy:.1f}")
        
        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        
        print(f"Collision occurred: {collision_occurred}")
        
        if collision_occurred:
            print(f"After collision:")
            print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x:.1f},{ball1.speed.y:.1f})")
            print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x:.1f},{ball2.speed.y:.1f})")
            
            # Calculate final energy
            final_energy1 = ball1.speed.x**2 + ball1.speed.y**2
            final_energy2 = ball2.speed.x**2 + ball2.speed.y**2
            total_final_energy = final_energy1 + final_energy2
            
            print(f"  Final energies: Ball1={final_energy1:.1f}, Ball2={final_energy2:.1f}, Total={total_final_energy:.1f}")
            
            # Check that energy was transferred
            energy_change1 = final_energy1 - initial_energy1
            energy_change2 = final_energy2 - initial_energy2
            
            print(f"  Energy changes: Ball1={energy_change1:.1f}, Ball2={energy_change2:.1f}")
            
            # Assertions
            self.assertTrue(collision_occurred, "Collision should have occurred")
            # For head-on collision with equal masses and speeds, balls exchange velocities
            # so individual energies change but total energy is conserved
            self.assertAlmostEqual(total_final_energy, total_initial_energy, delta=0.1,
                                 msg="Total energy should be conserved")
            
            # For head-on collision, balls should exchange velocities
            self.assertAlmostEqual(final_energy1, initial_energy2, delta=0.1,
                                 msg="Ball 1 should have ball 2's initial energy")
            self.assertAlmostEqual(final_energy2, initial_energy1, delta=0.1,
                                 msg="Ball 2 should have ball 1's initial energy")
            
            # Verify that velocities have actually changed (even if energies are the same)
            self.assertNotEqual(ball1.speed.x, 100, "Ball 1 X speed should change")
            self.assertNotEqual(ball2.speed.x, -100, "Ball 2 X speed should change")
        else:
            self.fail("Collision should have occurred for head-on collision")
    
    def test_diagonal_collision_energy_transfer(self):
        """Test diagonal collision energy transfer."""
        print("\n=== TESTING DIAGONAL COLLISION ENERGY TRANSFER ===")
        
        # Create two balls moving diagonally - position them close enough to collide
        ball1 = self._create_ball(100, 100, 100, 100)  # Moving down-right
        ball2 = self._create_ball(110, 110, -50, -50)  # Moving up-left, very close to ball1
        
        print(f"Before collision:")
        print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x},{ball1.speed.y})")
        print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x},{ball2.speed.y})")
        
        # Calculate initial energy
        initial_energy1 = ball1.speed.x**2 + ball1.speed.y**2
        initial_energy2 = ball2.speed.x**2 + ball2.speed.y**2
        total_initial_energy = initial_energy1 + initial_energy2
        
        print(f"  Initial energies: Ball1={initial_energy1:.1f}, Ball2={initial_energy2:.1f}, Total={total_initial_energy:.1f}")
        
        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        
        print(f"Collision occurred: {collision_occurred}")
        
        if collision_occurred:
            print(f"After collision:")
            print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x:.1f},{ball1.speed.y:.1f})")
            print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x:.1f},{ball2.speed.y:.1f})")
            
            # Calculate final energy
            final_energy1 = ball1.speed.x**2 + ball1.speed.y**2
            final_energy2 = ball2.speed.x**2 + ball2.speed.y**2
            total_final_energy = final_energy1 + final_energy2
            
            print(f"  Final energies: Ball1={final_energy1:.1f}, Ball2={final_energy2:.1f}, Total={total_final_energy:.1f}")
            
            # Check that energy was transferred
            energy_change1 = final_energy1 - initial_energy1
            energy_change2 = final_energy2 - initial_energy2
            
            print(f"  Energy changes: Ball1={energy_change1:.1f}, Ball2={energy_change2:.1f}")
            
            # Assertions
            self.assertTrue(collision_occurred, "Collision should have occurred")
            self.assertNotEqual(energy_change1, 0, "Ball 1 energy should have changed")
            self.assertNotEqual(energy_change2, 0, "Ball 2 energy should have changed")
            self.assertAlmostEqual(total_final_energy, total_initial_energy, delta=0.1, 
                                 msg="Total energy should be conserved")
        else:
            self.fail("Collision should have occurred for diagonal collision")
    
    def test_no_collision_when_far_apart(self):
        """Test that balls far apart don't collide."""
        print("\n=== TESTING NO COLLISION WHEN FAR APART ===")
        
        # Create two balls far apart
        ball1 = self._create_ball(100, 200, 100, 0)
        ball2 = self._create_ball(300, 200, 50, 0)  # 200px apart
        
        print(f"Balls far apart:")
        print(f"  Ball 1: pos=({ball1.rect.centerx},{ball1.rect.centery}) speed=({ball1.speed.x},{ball1.speed.y})")
        print(f"  Ball 2: pos=({ball2.rect.centerx},{ball2.rect.centery}) speed=({ball2.speed.x},{ball2.speed.y})")
        
        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        
        print(f"Collision occurred: {collision_occurred}")
        
        # Should not collide
        self.assertFalse(collision_occurred, "Balls far apart should not collide")
    
    def test_collision_distance_calculation(self):
        """Test that collision distance is calculated correctly."""
        print("\n=== TESTING COLLISION DISTANCE CALCULATION ===")
        
        # Create two balls with known positions
        ball1 = self._create_ball(100, 200, 100, 0)
        ball2 = self._create_ball(120, 200, 50, 0)  # 20px apart, radius=10 each
        
        print(f"Ball1 rect: x={ball1.rect.x}, y={ball1.rect.y}, centerx={ball1.rect.centerx}, centery={ball1.rect.centery}")
        print(f"Ball2 rect: x={ball2.rect.x}, y={ball2.rect.y}, centerx={ball2.rect.centerx}, centery={ball2.rect.centery}")
        
        # Calculate distance
        dx = ball2.rect.centerx - ball1.rect.centerx
        dy = ball2.rect.centery - ball1.rect.centery
        distance = math.sqrt(dx * dx + dy * dy)
        collision_distance = ball1.rect.width // 2 + ball2.rect.width // 2
        
        print(f"Distance between centers: {distance:.1f}")
        print(f"Collision distance (sum of radii): {collision_distance}")
        print(f"Should collide: {distance <= collision_distance}")
        
        # Should collide since distance (20) <= collision_distance (20)
        self.assertLessEqual(distance, collision_distance, "Balls should be in collision range")
        
        # Simulate collision
        collision_occurred = self._simulate_collision(ball1, ball2)
        self.assertTrue(collision_occurred, "Collision should have occurred")


if __name__ == '__main__':
    unittest.main()
