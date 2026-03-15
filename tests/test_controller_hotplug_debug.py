#!/usr/bin/env python3
"""Test script to debug controller hotplug with and without joystick event blocking.

This is a manual/interactive test that requires a physical controller and user input.
It is automatically skipped when run non-interactively (e.g., under pytest in CI).
Run directly with: python tests/test_controller_hotplug_debug.py
"""

import logging
import sys
import time

import glitchygames.events
import pygame
import pygame._sdl2.controller
import pytest

LOG = logging.getLogger(__name__)

# Skip this entire module when stdin is not a TTY (non-interactive pytest runs)
pytestmark = pytest.mark.skipif(
    not sys.stdin.isatty(),
    reason="Interactive test requires a TTY (run directly with python, not via pytest)",
)


def _prompt_or_skip(message: str) -> None:
    """Prompt the user for input, or skip the test if stdin is not interactive."""
    try:
        input(message)
    except EOFError:
        pytest.skip("No interactive terminal available for controller hotplug test")


def _monitor_controller_events(duration: float) -> None:
    """Monitor and log controller/joystick events for the given duration in seconds."""
    start_time = time.time()
    while time.time() - start_time < duration:
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEADDED:
                LOG.debug(f"CONTROLLERDEVICEADDED received: {event}")
            elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                LOG.debug(f"CONTROLLERDEVICEREMOVED received: {event}")
            elif event.type == 1543:
                LOG.debug(f"Unknown event 1543: {event}")
            elif event.type in glitchygames.events.JOYSTICK_EVENTS:
                LOG.debug(f"Joystick event {event.type}: {pygame.event.event_name(event.type)}")
            elif event.type in glitchygames.events.CONTROLLER_EVENTS:
                LOG.debug(f"Controller event {event.type}: {pygame.event.event_name(event.type)}")

        current_count = pygame._sdl2.controller.get_count()
        if current_count != getattr(test_controller_hotplug, "last_count", 0):
            last_count = getattr(test_controller_hotplug, "last_count", 0)
            LOG.debug(f"Controller count changed: {last_count} -> {current_count}")
            test_controller_hotplug.last_count = current_count

        time.sleep(0.1)


def test_controller_hotplug():
    """Test controller hotplug detection with different event blocking configurations."""
    # Initialize pygame
    pygame.init()
    pygame._sdl2.controller.init()

    LOG.debug("=== Controller Hotplug Debug Test ===")
    LOG.debug(f"Initial controller count: {pygame._sdl2.controller.get_count()}")

    # Test 1: No event blocking
    LOG.debug("\n=== TEST 1: No event blocking ===")
    LOG.debug("Please plug in a controller now...")
    _prompt_or_skip("Press Enter when ready to start monitoring (no blocking)...")
    _monitor_controller_events(duration=10)

    LOG.debug("\nNow please unplug the controller...")
    _prompt_or_skip("Press Enter when ready to monitor unplug (no blocking)...")
    _monitor_controller_events(duration=10)

    # Test 2: With joystick event blocking
    LOG.debug("\n=== TEST 2: With joystick event blocking ===")
    LOG.debug("Blocking joystick events...")
    pygame.event.set_blocked(glitchygames.events.JOYSTICK_EVENTS)
    LOG.debug(f"Blocked events: {glitchygames.events.JOYSTICK_EVENTS}")

    LOG.debug("Please plug in a controller now...")
    _prompt_or_skip("Press Enter when ready to start monitoring (with blocking)...")
    _monitor_controller_events(duration=10)

    LOG.debug("\nNow please unplug the controller...")
    _prompt_or_skip("Press Enter when ready to monitor unplug (with blocking)...")
    _monitor_controller_events(duration=10)

    LOG.debug("\n=== Test Complete ===")
    pygame.quit()


if __name__ == "__main__":
    test_controller_hotplug()
