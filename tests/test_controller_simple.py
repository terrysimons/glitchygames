#!/usr/bin/env python3
"""Simple test script to debug controller hotplug with and without joystick event blocking."""

import pygame
import pygame._sdl2.controller
import time


# These are typical joystick events for pygame 2.x:
# You may update these according to your pygame version if necessary
JOYSTICK_EVENTS = [
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
    pygame.JOYHATMOTION,
    pygame.JOYDEVICEADDED,
    pygame.JOYDEVICEREMOVED,
]

CONTROLLER_EVENTS = [
    pygame.CONTROLLERAXISMOTION,
    pygame.CONTROLLERBUTTONDOWN,
    pygame.CONTROLLERBUTTONUP,
    pygame.CONTROLLERDEVICEADDED,
    pygame.CONTROLLERDEVICEREMAPPED,
    pygame.CONTROLLERDEVICEREMOVED,
    pygame.CONTROLLERTOUCHPADDOWN,
    pygame.CONTROLLERTOUCHPADMOTION,
    pygame.CONTROLLERTOUCHPADUP,
    pygame.CONTROLLERSENSORUPDATE,
]

TEST_DURATION = 15

def print_device_event(event):
    """Print details of a joystick or controller device event."""
    # Map of name for known device events for both joysticks and controllers
    # No need for event_type_names mapping; use pygame's event_name
    # Try to pretty-print known events, fallback to generic info
    name = pygame.event.event_name(event.type)
    details = f"type={event.type} name={name}"
    if hasattr(event, "which"):
        details += f" which={event.which}"
    if hasattr(event, "instance_id"):
        details += f" instance_id={event.instance_id}"
    print(f"🔔 Device Event: {details} {event}")


def dump_event(event):
    """Dump event details to console."""
    try:
        print(f"Event {event.type}: {pygame.event.event_name(event.type)} - {event}")
        print(f"   Raw event: {event}")

        # Get event attributes safely
        attrs = [attr for attr in dir(event) if not attr.startswith('_')]
        print(f"   Event attributes: {attrs}")

        # Print specific attributes if they exist
        if hasattr(event, 'which'):
            print(f"   Event which: {event.which}")
        if hasattr(event, 'button'):
            print(f"   Event button: {event.button}")
        if hasattr(event, 'axis'):
            print(f"   Event axis: {event.axis}")
        if hasattr(event, 'value'):
            print(f"   Event value: {event.value}")
        if hasattr(event, 'instance_id'):
            print(f"   Event instance_id: {event.instance_id}")
        if hasattr(event, 'device_index'):
            print(f"   Event device_index: {event.device_index}")
        if hasattr(event, 'guid'):
            print(f"   Event guid: {event.guid}")


    except Exception as e:
        print(f"⚠️  Error dumping event: {e}")
        print(f"   Raw event: {event}")


def process_events():
    try:
        events = pygame.event.get()
        for event in events:
            # Handle controller device addition - open the controller to enable events
            if event.type == pygame.CONTROLLERDEVICEADDED:
                print(f"🔌 NEW CONTROLLER DETECTED! Opening controller {event.device_index}...")
                try:
                    controller = pygame._sdl2.controller.Controller(event.device_index)
                    print(f"✅ Successfully opened controller {event.device_index}: {controller}")
                except Exception as e:
                    print(f"❌ Failed to open controller {event.device_index}: {e}")

            dump_event(event)
    except Exception as e:
        print(f"⚠️  Error getting events: {e}")

    current_count = pygame._sdl2.controller.get_count()
    if current_count != getattr(process_events, 'last_count', 0):
        print(f"📊 Controller count changed: {getattr(process_events, 'last_count', 0)} → {current_count}")
        process_events.last_count = current_count

    time.sleep(0.1)



def test_controller_hotplug():
    """Test controller hotplug detection with different event blocking configurations using simplified event printing."""
    # Initialize pygame
    pygame.init()
    pygame._sdl2.controller.init()

    print("=== Controller Hotplug Debug Test ===")
    print(f"Initial controller count: {pygame._sdl2.controller.get_count()}")
    print(f"Controller event state: {pygame._sdl2.controller.get_eventstate()}")
    print(f"Joystick count: {pygame.joystick.get_count()}")

    # Enable controller events
    pygame._sdl2.controller.set_eventstate(True)
    print(f"Controller event state after enabling: {pygame._sdl2.controller.get_eventstate()}")

    # Try to open controllers to see if that helps with button events
    for i in range(pygame._sdl2.controller.get_count()):
        try:
            controller = pygame._sdl2.controller.Controller(i)
            print(f"Opened controller {i}: {controller}")
        except Exception as e:
            print(f"Could not open controller {i}: {e}")

    # Test 1: No event blocking
    print("\n=== TEST 1: No event blocking ===")
    print(f"Monitoring for {TEST_DURATION} seconds... Please plug/unplug controllers...")

    start_time = time.time()
    while time.time() - start_time < TEST_DURATION:
        process_events()


    # Test 2: With joystick event blocking
    print("\n=== TEST 2: With joystick event blocking ===")
    print("Blocking joystick events...")
    pygame.event.set_blocked(JOYSTICK_EVENTS)
    print(f"Blocked events: {JOYSTICK_EVENTS}")
    print(f"Controller Event state: {pygame._sdl2.controller.get_eventstate()}")
    pygame._sdl2.controller.set_eventstate(True)

    print(f"Monitoring for {TEST_DURATION} seconds... Please plug/unplug controllers...")

    start_time = time.time()
    while time.time() - start_time < TEST_DURATION:
        process_events()

    print("\n=== Test Complete ===")
    pygame.quit()


if __name__ == "__main__":
    test_controller_hotplug()