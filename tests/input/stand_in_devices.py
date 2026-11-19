"""Stand-in joysticks and game controllers for tests, through the real devices door.

Devices are hardware, so tests use stand-ins: the doors, registry and installer are the
engine's (glitchygames/input/stand_in_devices.py, which says how they answer), imported here so
every test keeps importing them from this module. The descriptors are the tests' own.
"""

from __future__ import annotations

from glitchygames.input.devices import CONTROLLER_KIND, JOYSTICK_KIND, DeviceDescriptor
from glitchygames.input.stand_in_devices import (
    StandInDeviceSources,
    install_stand_in_devices,
    stand_in_registry,
)

__all__ = [
    'STAND_IN_PAD',
    'STAND_IN_STICK',
    'StandInDeviceSources',
    'install_stand_in_devices',
    'stand_in_registry',
]

# An unmapped joystick: device index 0, instance id 5 (an instance id other than its index)
STAND_IN_STICK = DeviceDescriptor(
    kind=JOYSTICK_KIND,
    device_index=0,
    instance_id=5,
    name='Stand-in Flight Stick',
    guid='03000000aaaa0000bbbb000000000000',
    axis_count=3,
    button_count=4,
    hat_count=1,
    ball_count=1,
)
# A mapped game pad: device index 1, instance id 9
STAND_IN_PAD = DeviceDescriptor(
    kind=CONTROLLER_KIND,
    device_index=1,
    instance_id=9,
    name='Stand-in Game Pad',
    guid='03000000cccc0000dddd000000000000',
    axis_count=6,
    button_count=15,
    hat_count=1,
    ball_count=0,
)
