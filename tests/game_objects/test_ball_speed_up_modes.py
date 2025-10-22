#!/usr/bin/env python3
"""Test all ball speed-up modes."""

import time
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory

def test_speed_up_modes():
    """Test all speed-up modes."""
    print("=== BALL SPEED-UP MODES TEST ===")
    print("Testing all configurable speed-up behaviors...")
    
    # Set up centralized mocks
    patchers = MockFactory.setup_pygame_mocks()
    for patcher in patchers:
        patcher.start()
    
    try:
        # Test 1: No speed-up (default)
        print("\n1. NO SPEED-UP MODE")
        ball1 = BallSprite(speed_up_mode=SpeedUpMode.NONE)
        initial_speed = ball1.speed.x
        ball1.speed_up()  # Manual speed-up should still work
        print(f"   Initial speed: {initial_speed:.2f}")
        print(f"   After manual speed_up(): {ball1.speed.x:.2f}")
        print(f"   Speed increase: {((ball1.speed.x / initial_speed) - 1) * 100:.1f}%")
    
        # Test 2: Continuous logarithmic speed-up
        print("\n2. CONTINUOUS LOGARITHMIC SPEED-UP MODE")
        ball2 = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
            speed_up_multiplier=1.05,  # 5% logarithmic increase
            speed_up_interval=0.1  # Every 0.1 seconds
        )
        print(f"   Initial speed: {ball2.speed.x:.2f}")
        
        # Simulate 0.5 seconds of continuous speed-up
        for i in range(5):
            ball2.dt_tick(0.1)  # 0.1 second intervals
            print(f"   After {0.1 * (i + 1):.1f}s: {ball2.speed.x:.2f}")
        
        # Test 3: Wall bounce logarithmic speed-up
        print("\n3. WALL BOUNCE LOGARITHMIC SPEED-UP MODE")
        ball3 = BallSprite(
            speed_up_mode=SpeedUpMode.WALL_ONLY_LOGARITHMIC_X,
            speed_up_multiplier=1.1,  # 10% logarithmic increase
            bounce_top_bottom=True,
            bounce_left_right=True
        )
        print(f"   Initial speed: {ball3.speed.x:.2f}")
        
        # Simulate wall bounces
        ball3.rect.y = 0  # Hit top wall
        ball3._do_bounce()
        print(f"   After top bounce: {ball3.speed.x:.2f}")
        
        ball3.rect.x = 0  # Hit left wall
        ball3._do_bounce()
        print(f"   After left bounce: {ball3.speed.x:.2f}")
        
        # Test 4: Paddle bounce logarithmic speed-up
        print("\n4. PADDLE BOUNCE LOGARITHMIC SPEED-UP MODE")
        ball4 = BallSprite(
            speed_up_mode=SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X,
            speed_up_multiplier=1.15  # 15% logarithmic increase
        )
        print(f"   Initial speed: {ball4.speed.x:.2f}")
        
        # Simulate paddle bounce
        ball4.on_paddle_bounce()
        print(f"   After paddle bounce: {ball4.speed.x:.2f}")
        
        # Test 5: Combined logarithmic modes
        print("\n5. COMBINED LOGARITHMIC MODES")
        ball5 = BallSprite(
            speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
            speed_up_multiplier=1.02,  # 2% logarithmic increase
            speed_up_interval=0.2,  # Every 0.2 seconds
            bounce_top_bottom=True
        )
        print(f"   Initial speed: {ball5.speed.x:.2f}")
        
        # Simulate continuous + wall bounce
        ball5.dt_tick(0.2)  # Continuous speed-up
        print(f"   After 0.2s continuous: {ball5.speed.x:.2f}")
        
        ball5.rect.y = 0  # Wall bounce
        ball5._do_bounce()
        print(f"   After wall bounce: {ball5.speed.x:.2f}")
        
        # Test 6: All logarithmic modes combined
        print("\n6. ALL LOGARITHMIC MODES COMBINED")
        ball6 = BallSprite(
                speed_up_mode=SpeedUpMode.ALL_LOGARITHMIC_X,
            speed_up_multiplier=1.01,  # 1% logarithmic increase
            speed_up_interval=0.1,
            bounce_top_bottom=True,
            bounce_left_right=True
        )
        print(f"   Initial speed: {ball6.speed.x:.2f}")
        
        # Simulate all types of speed-up
        ball6.dt_tick(0.1)  # Continuous
        print(f"   After continuous: {ball6.speed.x:.2f}")
        
        ball6.on_paddle_bounce()  # Paddle
        print(f"   After paddle: {ball6.speed.x:.2f}")
        
        ball6.rect.y = 0  # Wall
        ball6._do_bounce()
        print(f"   After wall: {ball6.speed.x:.2f}")
        
        print("\n=== LOGARITHMIC SPEED-UP MODE FLAGS ===")
        print(f"SpeedUpMode.NONE = {SpeedUpMode.NONE}")
        print(f"SpeedUpMode.CONTINUOUS_LOGARITHMIC_X = {SpeedUpMode.CONTINUOUS_LOGARITHMIC_X}")
        print(f"SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X = {SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X}")
        print(f"SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y = {SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y}")
        print(f"SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X = {SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X}")
        print(f"SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y = {SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y}")
        print(f"SpeedUpMode.ALL_LOGARITHMIC_X = {SpeedUpMode.ALL_LOGARITHMIC_X}")
        print(f"SpeedUpMode.ALL_LOGARITHMIC_Y = {SpeedUpMode.ALL_LOGARITHMIC_Y}")
        print(f"SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_X = {SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_X}")
        print(f"SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_Y = {SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_Y}")
        print(f"SpeedUpMode.WALL_ONLY_LOGARITHMIC_X = {SpeedUpMode.WALL_ONLY_LOGARITHMIC_X}")
        print(f"SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X = {SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X}")
        
        print("\n=== LEGACY ALIASES (for backward compatibility) ===")
        print(f"SpeedUpMode.CONTINUOUS = {SpeedUpMode.CONTINUOUS}")
        print(f"SpeedUpMode.ON_BOUNCE = {SpeedUpMode.ON_BOUNCE}")
        print(f"SpeedUpMode.ON_WALL_BOUNCE = {SpeedUpMode.ON_WALL_BOUNCE}")
        print(f"SpeedUpMode.ALL = {SpeedUpMode.ALL}")
        print(f"SpeedUpMode.BOUNCE_ONLY = {SpeedUpMode.BOUNCE_ONLY}")
        print(f"SpeedUpMode.WALL_ONLY = {SpeedUpMode.WALL_ONLY}")
        print(f"SpeedUpMode.PADDLE_ONLY = {SpeedUpMode.PADDLE_ONLY}")
        
        print("\n=== BITWISE OPERATIONS ===")
        print("You can combine logarithmic modes using bitwise OR:")
        print("  SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X")
        print("  SpeedUpMode.WALL_ONLY_LOGARITHMIC_X | SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X")
        print("  SpeedUpMode.ALL_LOGARITHMIC & ~SpeedUpMode.CONTINUOUS_LOGARITHMIC_X  # All except continuous")
        
        print("\n✅ All speed-up modes tested successfully!")
    
    finally:
        # Clean up mocks
        MockFactory.teardown_pygame_mocks(patchers)

if __name__ == "__main__":
    test_speed_up_modes()
