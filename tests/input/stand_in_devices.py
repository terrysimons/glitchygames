"""Stand-in joysticks and game controllers for tests, through the real devices door.

Devices are hardware, so these doors serve the replay stand-ins (``ReplayJoystick``,
``ReplayController``) from a ``ReplayDeviceRegistry``: the objects a replay hands the engine.
The enumeration answers are the ones SDL gives for the devices: every device is counted as a
joystick and as a possible controller (pygame's controller count is SDL's joystick count), and
``is_controller`` says which are mapped game controllers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from glitchygames.input.devices import (
    CONTROLLER_COUNT_CALL,
    CONTROLLER_KIND,
    IS_CONTROLLER_CALL,
    JOYSTICK_COUNT_CALL,
    JOYSTICK_KIND,
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
)
from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources

if TYPE_CHECKING:
    from collections.abc import Sequence

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


class StandInDeviceSources(LiveSources):
    """Live doors whose devices are a replay registry's stand-ins (no hardware)."""

    def __init__(self: Self, *, registry: ReplayDeviceRegistry) -> None:
        """Create the doors around the registry.

        Args:
            registry: The stand-in devices.

        """
        super().__init__(random_seed=1)
        self.registry = registry

    def devices(self: Self) -> ReplayDeviceRegistry:
        """Return the stand-in devices.

        Returns:
            The registry.

        """
        return self.registry


def stand_in_registry(
    *, descriptors: Sequence[DeviceDescriptor], plugged_in_at_start: bool = True
) -> ReplayDeviceRegistry:
    """Return a registry of stand-in devices, answering enumeration as SDL would for them.

    Args:
        descriptors: The devices; a CONTROLLER_KIND one is a mapped game controller.
        plugged_in_at_start: False counts no devices (they are to be hot-plugged).

    Returns:
        The registry.

    """
    device_count = len(descriptors) if plugged_in_at_start else 0
    answers = [
        EnumerationAnswer(call=JOYSTICK_COUNT_CALL, device_index=None, value=device_count),
        EnumerationAnswer(call=CONTROLLER_COUNT_CALL, device_index=None, value=device_count),
    ]
    answers.extend(
        EnumerationAnswer(
            call=IS_CONTROLLER_CALL,
            device_index=descriptor.device_index,
            value=descriptor.kind == CONTROLLER_KIND,
        )
        for descriptor in descriptors
    )
    return ReplayDeviceRegistry(descriptors=list(descriptors), enumeration_answers=answers)


def install_stand_in_devices(
    *, descriptors: Sequence[DeviceDescriptor], plugged_in_at_start: bool = True
) -> ReplayDeviceRegistry:
    """Install doors whose devices are stand-ins (see ``stand_in_registry``).

    Returns:
        The installed registry.

    """
    registry = stand_in_registry(descriptors=descriptors, plugged_in_at_start=plugged_in_at_start)
    install_sources(sources=StandInDeviceSources(registry=registry))
    return registry
