#!/usr/bin/env python3
"""
Test script to verify Game Over functionality.
"""

import sys
import os
import pygame

# Add the glitchygames package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../glitchygames'))

from glitchygames.examples.paddleslap import Game

def test_game_over_condition():
    """Test that Game Over is triggered when all balls are dead."""
    
    # Initialize pygame (minimal setup)
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    
    # Create a game instance
    game = Game(options={})
    game.setup()
    
    # Check initial state
    initial_ball_count = len(game.balls)
    print(f"Initial ball count: {initial_ball_count}")
    
    # Simulate all balls being killed
    for ball in game.balls:
        ball.kill()
    
    # Check that balls are marked as dead
    dead_balls = [ball for ball in game.balls if not ball.alive()]
    print(f"Dead balls: {len(dead_balls)}")
    
    # Simulate the update cycle that should trigger Game Over
    game.update()
    
    # Check if Game Over was triggered (balls list should be empty after cleanup)
    final_ball_count = len(game.balls)
    print(f"Final ball count after update: {final_ball_count}")
    
    # Verify that all balls were removed
    assert final_ball_count == 0, f"Expected 0 balls, got {final_ball_count}"
    print("✅ Game Over condition properly detected!")
    
    pygame.quit()

if __name__ == "__main__":
    test_game_over_condition()
