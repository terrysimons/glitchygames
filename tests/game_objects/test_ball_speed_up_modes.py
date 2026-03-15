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


def _test_no_speed_up():
    """Test 1: No speed-up (default)."""
    LOG.debug("\n1. NO SPEED-UP MODE")
    ball = BallSprite(speed_up_mode=SpeedUpMode.NONE)
    initial_speed = ball.speed.x
    ball.speed_up()  # Manual speed-up should still work
    LOG.debug(f"   Initial speed: {initial_speed:.2f}")
    LOG.debug(f"   After manual speed_up(): {ball.speed.x:.2f}")
    LOG.debug(f"   Speed increase: {((ball.speed.x / initial_speed) - 1) * 100:.1f}%")


def _test_continuous_logarithmic():
    """Test 2: Continuous logarithmic speed-up."""
    LOG.debug("\n2. CONTINUOUS LOGARITHMIC SPEED-UP MODE")
    ball = BallSprite(
        speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X,
        speed_up_multiplier=1.05,
        speed_up_interval=0.1,
    )
    LOG.debug(f"   Initial speed: {ball.speed.x:.2f}")

    for i in range(5):
        ball.dt_tick(0.1)
        LOG.debug(f"   After {0.1 * (i + 1):.1f}s: {ball.speed.x:.2f}")


def _test_wall_bounce_logarithmic():
    """Test 3: Wall bounce logarithmic speed-up."""
    LOG.debug("\n3. WALL BOUNCE LOGARITHMIC SPEED-UP MODE")
    ball = BallSprite(
        speed_up_mode=SpeedUpMode.WALL_ONLY_LOGARITHMIC_X,
        speed_up_multiplier=1.1,
        bounce_top_bottom=True,
        bounce_left_right=True,
    )
    LOG.debug(f"   Initial speed: {ball.speed.x:.2f}")

    ball.rect.y = 0
    ball._do_bounce()
    LOG.debug(f"   After top bounce: {ball.speed.x:.2f}")

    ball.rect.x = 0
    ball._do_bounce()
    LOG.debug(f"   After left bounce: {ball.speed.x:.2f}")


def _test_paddle_bounce_logarithmic():
    """Test 4: Paddle bounce logarithmic speed-up."""
    LOG.debug("\n4. PADDLE BOUNCE LOGARITHMIC SPEED-UP MODE")
    ball = BallSprite(
        speed_up_mode=SpeedUpMode.PADDLE_ONLY_LOGARITHMIC_X,
        speed_up_multiplier=1.15,
    )
    LOG.debug(f"   Initial speed: {ball.speed.x:.2f}")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: {ball.speed.x:.2f}")


def _test_combined_logarithmic():
    """Test 5: Combined logarithmic modes."""
    LOG.debug("\n5. COMBINED LOGARITHMIC MODES")
    ball = BallSprite(
        speed_up_mode=SpeedUpMode.CONTINUOUS_LOGARITHMIC_X
        | SpeedUpMode.ON_WALL_BOUNCE_LOGARITHMIC_X,
        speed_up_multiplier=1.02,
        speed_up_interval=0.2,
        bounce_top_bottom=True,
    )
    LOG.debug(f"   Initial speed: {ball.speed.x:.2f}")

    ball.dt_tick(0.2)
    LOG.debug(f"   After 0.2s continuous: {ball.speed.x:.2f}")

    ball.rect.y = 0
    ball._do_bounce()
    LOG.debug(f"   After wall bounce: {ball.speed.x:.2f}")


def _test_all_logarithmic_combined():
    """Test 6: All logarithmic modes combined."""
    LOG.debug("\n6. ALL LOGARITHMIC MODES COMBINED")
    ball = BallSprite(
        speed_up_mode=SpeedUpMode.ALL_LOGARITHMIC_X,
        speed_up_multiplier=1.01,
        speed_up_interval=0.1,
        bounce_top_bottom=True,
        bounce_left_right=True,
    )
    LOG.debug(f"   Initial speed: {ball.speed.x:.2f}")

    ball.dt_tick(0.1)
    LOG.debug(f"   After continuous: {ball.speed.x:.2f}")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle: {ball.speed.x:.2f}")

    ball.rect.y = 0
    ball._do_bounce()
    LOG.debug(f"   After wall: {ball.speed.x:.2f}")


def _log_speed_up_mode_flags():
    """Log all speed-up mode flag values."""
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
        "  SpeedUpMode.ALL_LOGARITHMIC"
        " & ~SpeedUpMode.CONTINUOUS_LOGARITHMIC_X"
        "  # All except continuous"
    )


def test_speed_up_modes(mocker):
    """Test all speed-up modes."""
    LOG.debug("=== BALL SPEED-UP MODES TEST ===")
    LOG.debug("Testing all configurable speed-up behaviors...")

    MockFactory.setup_pygame_mocks_with_mocker(mocker)

    _test_no_speed_up()
    _test_continuous_logarithmic()
    _test_wall_bounce_logarithmic()
    _test_paddle_bounce_logarithmic()
    _test_combined_logarithmic()
    _test_all_logarithmic_combined()
    _log_speed_up_mode_flags()

    LOG.info("\nAll speed-up modes tested successfully!")


if __name__ == "__main__":
    test_speed_up_modes()
