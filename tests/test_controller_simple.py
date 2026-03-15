#!/usr/bin/env python3
"""Simple test script to debug controller hotplug with and without joystick event blocking."""

import logging
import time

import pygame
import pygame._sdl2.controller

LOG = logging.getLogger(__name__)

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
    details = f'type={event.type} name={name}'
    if hasattr(event, 'which'):
        details += f' which={event.which}'
    if hasattr(event, 'instance_id'):
        details += f' instance_id={event.instance_id}'
    LOG.debug(f'🔔 Device Event: {details} {event}')


def dump_event(event):
    """Dump event details to console."""
    try:
        LOG.debug(f'Event {event.type}: {pygame.event.event_name(event.type)} - {event}')
        LOG.debug(f'   Raw event: {event}')

        # Get event attributes safely
        attrs = [attr for attr in dir(event) if not attr.startswith('_')]
        LOG.debug(f'   Event attributes: {attrs}')

        # Print specific attributes if they exist
        if hasattr(event, 'which'):
            LOG.debug(f'   Event which: {event.which}')
        if hasattr(event, 'button'):
            LOG.debug(f'   Event button: {event.button}')
        if hasattr(event, 'axis'):
            LOG.debug(f'   Event axis: {event.axis}')
        if hasattr(event, 'value'):
            LOG.debug(f'   Event value: {event.value}')
        if hasattr(event, 'instance_id'):
            LOG.debug(f'   Event instance_id: {event.instance_id}')
        if hasattr(event, 'device_index'):
            LOG.debug(f'   Event device_index: {event.device_index}')
        if hasattr(event, 'guid'):
            LOG.debug(f'   Event guid: {event.guid}')

    except (AttributeError, pygame.error) as e:
        LOG.debug(f'⚠️  Error dumping event: {e}')
        LOG.debug(f'   Raw event: {event}')


def process_events():
    """Process all pending pygame events including controller input."""
    try:
        events = pygame.event.get()
        for event in events:
            # Handle controller device addition - open the controller to enable events
            if event.type == pygame.CONTROLLERDEVICEADDED:
                LOG.debug(f'🔌 NEW CONTROLLER DETECTED! Opening controller {event.device_index}...')
                try:
                    controller = pygame._sdl2.controller.Controller(event.device_index)
                    LOG.info(
                        f'✅ Successfully opened controller {event.device_index}: {controller}'
                    )
                except pygame.error as e:
                    LOG.debug(f'❌ Failed to open controller {event.device_index}: {e}')

            dump_event(event)
    except pygame.error as e:
        LOG.debug(f'⚠️  Error getting events: {e}')

    current_count = pygame._sdl2.controller.get_count()
    if current_count != getattr(process_events, 'last_count', 0):
        LOG.debug(
            f"📊 Controller count changed: {getattr(process_events, 'last_count', 0)}"
            f" → {current_count}"
        )
        process_events.last_count = current_count

    time.sleep(0.1)


def test_controller_hotplug():
    """Test controller hotplug detection with different event blocking configurations."""
    # Initialize pygame
    pygame.init()
    pygame._sdl2.controller.init()

    LOG.debug('=== Controller Hotplug Debug Test ===')
    LOG.debug(f'Initial controller count: {pygame._sdl2.controller.get_count()}')
    LOG.debug(f'Controller event state: {pygame._sdl2.controller.get_eventstate()}')
    LOG.debug(f'Joystick count: {pygame.joystick.get_count()}')

    # Enable controller events
    pygame._sdl2.controller.set_eventstate(True)
    LOG.debug(f'Controller event state after enabling: {pygame._sdl2.controller.get_eventstate()}')

    # Try to open controllers to see if that helps with button events
    for i in range(pygame._sdl2.controller.get_count()):
        try:
            controller = pygame._sdl2.controller.Controller(i)
            LOG.debug(f'Opened controller {i}: {controller}')
        except pygame.error as e:
            LOG.debug(f'Could not open controller {i}: {e}')

    # Test 1: No event blocking
    LOG.debug('\n=== TEST 1: No event blocking ===')
    LOG.debug(f'Monitoring for {TEST_DURATION} seconds... Please plug/unplug controllers...')

    start_time = time.time()
    while time.time() - start_time < TEST_DURATION:
        process_events()

    # Test 2: With joystick event blocking
    LOG.debug('\n=== TEST 2: With joystick event blocking ===')
    LOG.debug('Blocking joystick events...')
    pygame.event.set_blocked(JOYSTICK_EVENTS)
    LOG.debug(f'Blocked events: {JOYSTICK_EVENTS}')
    LOG.debug(f'Controller Event state: {pygame._sdl2.controller.get_eventstate()}')
    pygame._sdl2.controller.set_eventstate(True)

    LOG.debug(f'Monitoring for {TEST_DURATION} seconds... Please plug/unplug controllers...')

    start_time = time.time()
    while time.time() - start_time < TEST_DURATION:
        process_events()

    LOG.debug('\n=== Test Complete ===')
    pygame.quit()


if __name__ == '__main__':
    test_controller_hotplug()
