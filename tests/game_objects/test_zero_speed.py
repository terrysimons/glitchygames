#!/usr/bin/env python3
"""Test what happens when ball speed is zero."""

import logging
import math
import sys
import time
from pathlib import Path

# Add project root so direct imports work
sys.path.insert(0, str(Path(__file__).parent))

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed

from tests.mocks.test_mock_factory import MockFactory

LOG = logging.getLogger(__name__)


def test_zero_speed_scenarios(mocker):
    """Test various scenarios with zero speed components."""
    # Set up centralized mocks
    MockFactory.setup_pygame_mocks_with_mocker(mocker)

    LOG.debug("=== Testing Zero Speed Scenarios ===\n")

    # Create a ball with X-only speedup
    ball = BallSprite(speed_up_mode=SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X, speed_up_multiplier=1.15)

    LOG.debug("1. Both X and Y speeds are 0:")
    ball.speed = Speed(0.0, 0.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    # Try to trigger speed-up
    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")
    LOG.debug("   Result: Ball remains stationary (no movement)\n")

    LOG.debug("2. Only X speed is 0, Y speed is non-zero:")
    ball.speed = Speed(0.0, 100.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")
    LOG.debug("   Result: X remains 0, Y unchanged (X-only speedup doesn't affect Y)\n")

    LOG.debug("3. Only Y speed is 0, X speed is non-zero:")
    ball.speed = Speed(100.0, 0.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")
    LOG.debug("   Result: X speed increases, Y remains 0\n")

    LOG.debug("4. Test with Y-only speedup mode:")
    ball.speed_up_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y
    ball.speed = Speed(100.0, 0.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")
    LOG.debug("   Result: X unchanged, Y remains 0 (Y-only speedup doesn't affect X)\n")

    LOG.debug("5. Test with both X and Y speeds 0 and Y-only speedup:")
    ball.speed = Speed(0.0, 0.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")
    LOG.debug("   Result: Ball remains stationary\n")

    LOG.debug("6. Test movement calculation with zero speed:")
    ball.speed = Speed(0.0, 0.0)
    dt = 0.016  # 60 FPS
    move_x = ball.speed.x * dt
    move_y = ball.speed.y * dt
    LOG.debug(f"   Movement calculation: move_x={move_x}, move_y={move_y}")
    LOG.debug("   Result: No movement occurs (0 * dt = 0)\n")

    LOG.debug("7. Test with very small speeds (near zero):")
    ball.speed = Speed(0.001, 0.001)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    ball.on_paddle_bounce()
    LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")
    LOG.debug("   Result: X speed increases slightly, Y unchanged\n")

    LOG.debug("8. Test continuous speed-up with zero initial speed over many iterations:")
    ball.speed_up_mode = SpeedUpMode.CONTINUOUS_LOGARITHMIC_X
    ball.speed = Speed(0.0, 0.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    # Simulate many game ticks
    current_time = time.time()
    ball._last_speed_up_time = current_time - 1.0  # Force first speed-up

    for i in range(10):
        ball.dt_tick(0.016)  # 60 FPS
        LOG.debug(f"   Iteration {i + 1}: speed=({ball.speed.x:.6f}, {ball.speed.y:.6f})")
        time.sleep(0.1)  # Small delay to see progression

    LOG.debug("   Result: X speed remains 0, Y speed remains 0 (no movement)\n")

    LOG.debug("9. Test with non-zero initial speed and continuous speed-up:")
    ball.speed = Speed(10.0, 5.0)
    LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

    for i in range(10):
        ball.dt_tick(0.016)  # 60 FPS
        LOG.debug(f"   Iteration {i + 1}: speed=({ball.speed.x:.6f}, {ball.speed.y:.6f})")
        time.sleep(0.1)  # Small delay to see progression

    LOG.debug("   Result: X speed increases over time, Y speed unchanged\n")

    LOG.debug("10. Test movement over many iterations with zero speed:")
    ball.speed = Speed(0.0, 0.0)
    ball.rect.x = 100
    ball.rect.y = 100
    LOG.debug(f"   Initial position: ({ball.rect.x}, {ball.rect.y})")

    for i in range(20):
        ball.dt_tick(0.016)  # 60 FPS
        LOG.debug(
            f"   Iteration {i + 1}:"
            f" position=({ball.rect.x}, {ball.rect.y}),"
            f" speed=({ball.speed.x}, {ball.speed.y})"
        )
        time.sleep(0.05)  # Small delay

    LOG.debug("   Result: Position never changes (no movement with zero speed)\n")

    LOG.debug("=== COMPREHENSIVE DIRECTIONAL ZERO SPEED TESTS ===\n")

    # Test all combinations with X-only speedup
    ball.speed_up_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
    test_speeds = [
        (0.0, 0.0, "Both zero"),
        (100.0, 0.0, "X positive, Y zero"),
        (-100.0, 0.0, "X negative, Y zero"),
        (0.0, 100.0, "X zero, Y positive"),
        (0.0, -100.0, "X zero, Y negative"),
        (50.0, 0.0, "X small positive, Y zero"),
        (-50.0, 0.0, "X small negative, Y zero"),
        (0.0, 50.0, "X zero, Y small positive"),
        (0.0, -50.0, "X zero, Y small negative"),
    ]

    for x_speed, y_speed, description in test_speeds:
        LOG.debug(
            f"11.{test_speeds.index((x_speed, y_speed, description)) + 1} Testing {description}:"
        )
        ball.speed = Speed(x_speed, y_speed)
        LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

        ball.on_paddle_bounce()
        LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")

        # Analyze the result
        if math.isclose(x_speed, 0.0, abs_tol=1e-9) and math.isclose(y_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: Both speeds remain 0 (stationary ball)\n")
        elif math.isclose(x_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: X remains 0, Y unchanged (X-only speedup doesn't affect Y)\n")
        elif math.isclose(y_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: X speed increases, Y remains 0 (X-only speedup affects X)\n")
        else:
            LOG.debug("   Result: X speed increases, Y unchanged (X-only speedup affects X only)\n")

    # Test with Y-only speedup
    LOG.debug("=== TESTING Y-ONLY SPEEDUP ===\n")
    ball.speed_up_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y

    for x_speed, y_speed, description in test_speeds:
        index = test_speeds.index((x_speed, y_speed, description)) + 1
        LOG.debug(
            f"12.{index} Testing {description}"
            f" with Y-only speedup:"
        )
        ball.speed = Speed(x_speed, y_speed)
        LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

        ball.on_paddle_bounce()
        LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")

        # Analyze the result
        if math.isclose(x_speed, 0.0, abs_tol=1e-9) and math.isclose(y_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: Both speeds remain 0 (stationary ball)\n")
        elif math.isclose(x_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: X remains 0, Y speed increases (Y-only speedup affects Y)\n")
        elif math.isclose(y_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: X unchanged, Y remains 0 (Y-only speedup doesn't affect X)\n")
        else:
            LOG.debug("   Result: X unchanged, Y speed increases (Y-only speedup affects Y only)\n")

    # Test with both X and Y speedup
    LOG.debug("=== TESTING BOTH X AND Y SPEEDUP ===\n")
    ball.speed_up_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X | SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y

    for x_speed, y_speed, description in test_speeds:
        index = test_speeds.index((x_speed, y_speed, description)) + 1
        LOG.debug(
            f"13.{index} Testing {description}"
            f" with both X and Y speedup:"
        )
        ball.speed = Speed(x_speed, y_speed)
        LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

        ball.on_paddle_bounce()
        LOG.debug(f"   After paddle bounce: ({ball.speed.x}, {ball.speed.y})")

        # Analyze the result
        if math.isclose(x_speed, 0.0, abs_tol=1e-9) and math.isclose(y_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: Both speeds remain 0 (stationary ball)\n")
        elif math.isclose(x_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: X remains 0, Y speed increases (both speedup affects Y)\n")
        elif math.isclose(y_speed, 0.0, abs_tol=1e-9):
            LOG.debug("   Result: X speed increases, Y remains 0 (both speedup affects X)\n")
        else:
            LOG.debug("   Result: Both X and Y speeds increase (both speedup affects both)\n")

    # Test continuous speed-up with various zero combinations
    LOG.debug("=== TESTING CONTINUOUS SPEEDUP WITH ZERO COMBINATIONS ===\n")
    ball.speed_up_mode = SpeedUpMode.CONTINUOUS_LOGARITHMIC_X | SpeedUpMode.CONTINUOUS_LOGARITHMIC_Y

    continuous_test_speeds = [
        (0.0, 0.0, "Both zero"),
        (10.0, 0.0, "X positive, Y zero"),
        (0.0, 10.0, "X zero, Y positive"),
        (5.0, 0.0, "X small positive, Y zero"),
        (0.0, 5.0, "X zero, Y small positive"),
    ]

    for x_speed, y_speed, description in continuous_test_speeds:
        index = continuous_test_speeds.index(
            (x_speed, y_speed, description)
        ) + 1
        LOG.debug(
            f"14.{index} Testing continuous"
            f" speedup with {description}:"
        )
        ball.speed = Speed(x_speed, y_speed)
        LOG.debug(f"   Initial speed: ({ball.speed.x}, {ball.speed.y})")

        # Reset speed-up timer to force immediate speed-up
        current_time = time.time()
        ball._last_speed_up_time = current_time - 1.0

        for i in range(5):
            ball.dt_tick(0.016)  # 60 FPS
            LOG.debug(f"   Iteration {i + 1}: speed=({ball.speed.x:.6f}, {ball.speed.y:.6f})")
            time.sleep(0.1)

        both_nonzero = (
            not math.isclose(x_speed, 0.0, abs_tol=1e-9)
            and not math.isclose(y_speed, 0.0, abs_tol=1e-9)
        )
        result_msg = (
            "X and Y speeds increase"
            if both_nonzero
            else "Only non-zero components increase"
        )
        LOG.debug(f"   Result: {result_msg}\n")


if __name__ == "__main__":
    test_zero_speed_scenarios()
