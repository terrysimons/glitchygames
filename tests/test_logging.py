#!/usr/bin/env python3
"""Test script to verify the logging is working."""

import sys
import os

# Add the glitchygames directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'glitchygames'))

from glitchygames.game_objects.ball import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle

def test_logging():
    """Test the logging functionality."""
    print("Testing ball and paddle logging...")
    
    # Create a ball
    ball = BallSprite()
    ball.speed.x = 100.0
    ball.speed.y = 50.0
    ball.rect.x = 100
    ball.rect.y = 100
    
    print("\n=== Testing Ball Movement ===")
    ball.dt_tick(0.016)  # 60 FPS
    
    print("\n=== Testing Ball Bounce ===")
    ball.rect.y = -5  # Above screen
    ball._do_bounce()
    
    # Create a paddle
    paddle = VerticalPaddle("Test Paddle", (20, 80), (0, 100), (255, 255, 255), 300)
    
    print("\n=== Testing Paddle Movement ===")
    paddle.dt_tick(0.016)  # 60 FPS
    
    print("\nLogging test completed!")

if __name__ == "__main__":
    test_logging()
