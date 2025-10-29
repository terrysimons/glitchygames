#!/usr/bin/env python3
"""
Test script to verify that single-frame animations now work properly.
This script demonstrates the fix for the issue where single-frame animations
would stop playing after the first frame advance.
"""

import pygame
import sys
import os

# Add the glitchygames package to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'glitchygames'))

from glitchygames.sprites.animated import AnimatedSprite, SpriteFrame
from tests.mocks import MockFactory

def test_single_frame_animation():
    """Test that single-frame animations continue playing."""
    print("Testing single-frame animation fix...")
    
    # Initialize pygame
    pygame.init()
    
    # Create a real surface for the frame using MockFactory
    surface = MockFactory.create_real_pygame_surface(8, 8)
    surface.fill((255, 0, 0))  # Red color
    
    # Create a single frame
    frame = SpriteFrame(surface)
    frame.duration = 0.5  # 0.5 seconds duration
    
    # Create animated sprite with single frame using centralized mocks
    sprite = MockFactory.create_animated_sprite_mock(
        animation_name="idle",
        frame_size=(8, 8),
        pixel_color=(255, 0, 0),
        current_frame=0
    )
    
    # Override the animations to use our single frame
    sprite._animations = {"idle": [frame]}
    sprite.frame_manager.current_animation = "idle"
    sprite.frame_manager.current_frame = 0
    sprite._is_playing = True
    sprite._is_looping = True
    
    print(f"Initial state: current_frame={sprite.current_frame}, is_playing={sprite._is_playing}")
    
    # Simulate multiple update cycles
    dt = 0.016  # ~60 FPS
    for i in range(100):  # Run for ~1.6 seconds
        sprite.update(dt)
        
        # Check every 10 updates
        if i % 10 == 0:
            print(f"Update {i}: current_frame={sprite.current_frame}, is_playing={sprite._is_playing}")
        
        # The animation should still be playing and on frame 0
        assert sprite._is_playing, f"Animation stopped playing at update {i}"
        assert sprite.current_frame == 0, f"Frame changed from 0 to {sprite.current_frame} at update {i}"
    
    print("✅ Single-frame animation test PASSED!")
    print("The animation continued playing and stayed on frame 0 as expected.")
    
    pygame.quit()

if __name__ == "__main__":
    test_single_frame_animation()
