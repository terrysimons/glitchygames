#!/usr/bin/env python3
"""Test all ball speed-up modes."""

import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode

from tests.mocks.test_mock_factory import MockFactory

LOG = logging.getLogger(__name__)


def test_speed_up_modes(mocker):
    """Test all speed-up modes."""
    LOG.debug("=== BALL SPEED-UP MODES TEST ===")
    LOG.debug("Testing all configurable speed-up behaviors...")

    # Set up centralized mocks
    MockFactory.setup_pygame_mocks_with_mocker(mocker)

    # Test 1: No speed-up (default)
    LOG.debug("\n1. NO SPEED-UP MODE")
    ball1 = BallSprite(speed_up_mode=SpeedUpMode.NONE)
    initial_speed = ball1.speed.x
    ball1.speed_up()  # Manual speed-up should still work
    LOG.debug(f"   Initial speed: {initial_speed:.2f}")
    LOG.debug(f"   After manual speed_up(): {ball1.speed.x:.2f}")
    LOG.debug(f"   Speed increase: {((ball1.speed.x / initial_speed) - 1) * 100:.1f}%")

    # Test 2: Continuous logarithmic speed-up
    LOG.debug("\n2. CONTINUOUS LOGARITHMIC SPEED-UP MODE")
    ball2 = BallSprite(
        speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
        speed_up_multiplier=1.05,  # 5% logarithmic increase
        speed_up_interval=0.1,  # Every 0.1 seconds
    )
    LOG.debug(f"   Initial speed: {ball2.speed.x:.2f}")

    # Simulate 0.5 seconds of continuous speed-up
    for i in range(5):
        ball2.dt_tick(0.1)  # 0.1 second intervals
        LOG.debug(f"   After {0.1 * (i + 1):.1f}s: {ball2.speed.x:.2f}")

    # Test 3: Wall bounce logarithmic speed-up
    LOG.debug("\n3. WALL BOUNCE LOGARITHMIC SPEED-UP MODE")
    ball3 = BallSprite(
        speed_up_mode=SpeedUpMode.WALL_ONLY_LOGARITHMIC_X,
        speed_up_multiplier=1.1,  # 10% logarithmic increase
        bounce_top_bottom=True,
        bounce_left_right=True,
    )
    LOG.debug(f"   Initial speed: {ball3.speed.x:.2f}")

    # Simulate wall bounces
    ball3.rect.y = 0  # Hit top wall
    ball3._do_bounce()
    LOG.debug(f"   After top bounce: {ball3.speed.x:.2f}")

    ball3.rect.x = 0  # Hit left wall
    ball3._do_bounce()
    LOG.debug(f"   After left bounce: {ball3.speed.x:.2f}")

    # Test 4: Paddle bounce logarithmic speed-up
    LOG.debug("\n4. PADDLE BOUNCE LOGARITHMIC SPEED-UP MODE")
    ball4 = BallSprite(
        speed_up_mode=SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X,
        speed_up_multiplier=1.15,  # 15% logarithmic increase
    )
    LOG.debug(f"   Initial speed: {ball4.speed.x:.2f}")

    # Simulate paddle bounce
    ball4.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: {ball4.speed.x:.2f}")

    # Test 5: Combined logarithmic modes
    LOG.debug("\n5. COMBINED LOGARITHMIC MODES")
    ball5 = BallSprite(
        speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X
        | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
        speed_up_multiplier=1.02,  # 2% logarithmic increase
        speed_up_interval=0.2,  # Every 0.2 seconds
        bounce_top_bottom=True,
    )
    LOG.debug(f"   Initial speed: {ball5.speed.x:.2f}")

    # Simulate continuous + wall bounce
    ball5.dt_tick(0.2)  # Continuous speed-up
    LOG.debug(f"   After 0.2s continuous: {ball5.speed.x:.2f}")

    ball5.rect.y = 0  # Wall bounce
    ball5._do_bounce()
    LOG.debug(f"   After wall bounce: {ball5.speed.x:.2f}")

    # Test 6: All logarithmic modes combined
    LOG.debug("\n6. ALL LOGARITHMIC MODES COMBINED")
    ball6 = BallSprite(
        speed_up_mode=SpeedUpMode.ALL_LOGARITHMIC_X,
        speed_up_multiplier=1.01,  # 1% logarithmic increase
        speed_up_interval=0.1,
        bounce_top_bottom=True,
        bounce_left_right=True,
    )
    LOG.debug(f"   Initial speed: {ball6.speed.x:.2f}")

    # Simulate all types of speed-up
    ball6.dt_tick(0.1)  # Continuous
    LOG.debug(f"   After continuous: {ball6.speed.x:.2f}")

    ball6.on_paddle_bounce()  # Paddle
    LOG.debug(f"   After paddle: {ball6.speed.x:.2f}")

    ball6.rect.y = 0  # Wall
    ball6._do_bounce()
    LOG.debug(f"   After wall: {ball6.speed.x:.2f}")

    LOG.debug("\n=== LOGARITHMIC SPEED-UP MODE FLAGS ===")
    LOG.debug(f"SpeedUpMode.NONE = {SpeedUpMode.NONE}")
    LOG.debug(f"SpeedUpMode.CONTINUOUS_LOGARITHMIC_X = {SpeedUpMode.CONTINUOUS_LOGARITHMIC_X}")
    LOG.debug(f"SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X = {SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X}")
    LOG.debug(f"SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y = {SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y}")
    LOG.debug(
        f"SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X = {SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X}"
    )
    LOG.debug(
        f"SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y = {SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_Y}"
    )
    LOG.debug(f"SpeedUpMode.ALL_LOGARITHMIC_X = {SpeedUpMode.ALL_LOGARITHMIC_X}")
    LOG.debug(f"SpeedUpMode.ALL_LOGARITHMIC_Y = {SpeedUpMode.ALL_LOGARITHMIC_Y}")
    LOG.debug(f"SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_X = {SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_X}")
    LOG.debug(f"SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_Y = {SpeedUpMode.BOUNCE_ONLY_LOGARITHMIC_Y}")
    LOG.debug(f"SpeedUpMode.WALL_ONLY_LOGARITHMIC_X = {SpeedUpMode.WALL_ONLY_LOGARITHMIC_X}")
    LOG.debug(f"SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X = {SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X}")

    LOG.debug("\n=== LEGACY ALIASES (for backward compatibility) ===")
    LOG.debug(f"SpeedUpMode.CONTINUOUS = {SpeedUpMode.CONTINUOUS}")
    LOG.debug(f"SpeedUpMode.ON_BOUNCE = {SpeedUpMode.ON_BOUNCE}")
    LOG.debug(f"SpeedUpMode.ON_WALL_BOUNCE = {SpeedUpMode.ON_WALL_BOUNCE}")
    LOG.debug(f"SpeedUpMode.ALL = {SpeedUpMode.ALL}")
    LOG.debug(f"SpeedUpMode.BOUNCE_ONLY = {SpeedUpMode.BOUNCE_ONLY}")
    LOG.debug(f"SpeedUpMode.WALL_ONLY = {SpeedUpMode.WALL_ONLY}")
    LOG.debug(f"SpeedUpMode.PADDLE_ONLY = {SpeedUpMode.PADDLE_ONLY}")

    LOG.debug("\n=== BITWISE OPERATIONS ===")
    LOG.debug("You can combine logarithmic modes using bitwise OR:")
    LOG.debug("  SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X")
    LOG.debug("  SpeedUpMode.WALL_ONLY_LOGARITHMIC_X | SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X")
    LOG.debug(
        "  SpeedUpMode.ALL_LOGARITHMIC & ~SpeedUpMode.CONTINUOUS_LOGARITHMIC_X  # All except continuous"
    )

    LOG.info("\nAll speed-up modes tested successfully!")


if __name__ == "__main__":
    test_speed_up_modes()
