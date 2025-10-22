#!/usr/bin/env python3
"""Test script to debug controller hotplug with and without joystick event blocking."""

import pygame
import pygame._sdl2.controller
import glitchygames.events
import time

def test_controller_hotplug():
    """Test controller hotplug detection with different event blocking configurations."""

    # Initialize pygame
    pygame.init()
    pygame._sdl2.controller.init()

    print("=== Controller Hotplug Debug Test ===")
    print(f"Initial controller count: {pygame._sdl2.controller.get_count()}")

    # Test 1: No event blocking
    print("\n=== TEST 1: No event blocking ===")
    print("Please plug in a controller now...")
    input("Press Enter when ready to start monitoring (no blocking)...")

    start_time = time.time()
    while time.time() - start_time < 10:  # Monitor for 10 seconds
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEADDED:
                print(f"✅ CONTROLLERDEVICEADDED received: {event}")
            elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                print(f"✅ CONTROLLERDEVICEREMOVED received: {event}")
            elif event.type == 1543:
                print(f"❓ Unknown event 1543: {event}")
            elif event.type in glitchygames.events.JOYSTICK_EVENTS:
                print(f"🎮 Joystick event {event.type}: {pygame.event.event_name(event.type)}")
            elif event.type in glitchygames.events.CONTROLLER_EVENTS:
                print(f"🎯 Controller event {event.type}: {pygame.event.event_name(event.type)}")

        current_count = pygame._sdl2.controller.get_count()
        if current_count != getattr(test_controller_hotplug, 'last_count', 0):
            print(f"📊 Controller count changed: {getattr(test_controller_hotplug, 'last_count', 0)} → {current_count}")
            test_controller_hotplug.last_count = current_count

        time.sleep(0.1)

    print("\nNow please unplug the controller...")
    input("Press Enter when ready to monitor unplug (no blocking)...")

    start_time = time.time()
    while time.time() - start_time < 10:  # Monitor for 10 seconds
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEADDED:
                print(f"✅ CONTROLLERDEVICEADDED received: {event}")
            elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                print(f"✅ CONTROLLERDEVICEREMOVED received: {event}")
            elif event.type == 1543:
                print(f"❓ Unknown event 1543: {event}")
            elif event.type in glitchygames.events.JOYSTICK_EVENTS:
                print(f"🎮 Joystick event {event.type}: {pygame.event.event_name(event.type)}")
            elif event.type in glitchygames.events.CONTROLLER_EVENTS:
                print(f"🎯 Controller event {event.type}: {pygame.event.event_name(event.type)}")

        current_count = pygame._sdl2.controller.get_count()
        if current_count != getattr(test_controller_hotplug, 'last_count', 0):
            print(f"📊 Controller count changed: {getattr(test_controller_hotplug, 'last_count', 0)} → {current_count}")
            test_controller_hotplug.last_count = current_count

        time.sleep(0.1)

    # Test 2: With joystick event blocking
    print("\n=== TEST 2: With joystick event blocking ===")
    print("Blocking joystick events...")
    pygame.event.set_blocked(glitchygames.events.JOYSTICK_EVENTS)
    print(f"Blocked events: {glitchygames.events.JOYSTICK_EVENTS}")

    print("Please plug in a controller now...")
    input("Press Enter when ready to start monitoring (with blocking)...")

    start_time = time.time()
    while time.time() - start_time < 10:  # Monitor for 10 seconds
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEADDED:
                print(f"✅ CONTROLLERDEVICEADDED received: {event}")
            elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                print(f"✅ CONTROLLERDEVICEREMOVED received: {event}")
            elif event.type == 1543:
                print(f"❓ Unknown event 1543: {event}")
            elif event.type in glitchygames.events.JOYSTICK_EVENTS:
                print(f"🎮 Joystick event {event.type}: {pygame.event.event_name(event.type)}")
            elif event.type in glitchygames.events.CONTROLLER_EVENTS:
                print(f"🎯 Controller event {event.type}: {pygame.event.event_name(event.type)}")

        current_count = pygame._sdl2.controller.get_count()
        if current_count != getattr(test_controller_hotplug, 'last_count', 0):
            print(f"📊 Controller count changed: {getattr(test_controller_hotplug, 'last_count', 0)} → {current_count}")
            test_controller_hotplug.last_count = current_count

        time.sleep(0.1)

    print("\nNow please unplug the controller...")
    input("Press Enter when ready to monitor unplug (with blocking)...")

    start_time = time.time()
    while time.time() - start_time < 10:  # Monitor for 10 seconds
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEADDED:
                print(f"✅ CONTROLLERDEVICEADDED received: {event}")
            elif event.type == pygame.CONTROLLERDEVICEREMOVED:
                print(f"✅ CONTROLLERDEVICEREMOVED received: {event}")
            elif event.type == 1543:
                print(f"❓ Unknown event 1543: {event}")
            elif event.type in glitchygames.events.JOYSTICK_EVENTS:
                print(f"🎮 Joystick event {event.type}: {pygame.event.event_name(event.type)}")
            elif event.type in glitchygames.events.CONTROLLER_EVENTS:
                print(f"🎯 Controller event {event.type}: {pygame.event.event_name(event.type)}")

        current_count = pygame._sdl2.controller.get_count()
        if current_count != getattr(test_controller_hotplug, 'last_count', 0):
            print(f"📊 Controller count changed: {getattr(test_controller_hotplug, 'last_count', 0)} → {current_count}")
            test_controller_hotplug.last_count = current_count

        time.sleep(0.1)

    print("\n=== Test Complete ===")
    pygame.quit()

if __name__ == "__main__":
    test_controller_hotplug()
