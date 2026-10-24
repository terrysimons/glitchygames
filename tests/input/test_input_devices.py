"""Unified input devices (glitchygames/input/input_devices.py).

Devices are hardware, so the devices door serves the replay stand-ins (``ReplayJoystick``,
``ReplayController``) from a ``ReplayDeviceRegistry``: the same objects a replay hands the
engine. Everything else is real: the registry, the devices, the frame's input snapshot.
"""

from __future__ import annotations

from typing import Self

import pygame
import pytest

from glitchygames.input.devices import (
    CONTROLLER_KIND,
    IS_CONTROLLER_CALL,
    JOYSTICK_KIND,
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayController,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.input_devices import (
    CONTROLLER_INPUT_EVENT_TYPES,
    JOYSTICK_INPUT_EVENT_TYPES,
    ConnectedInputDevice,
    ControllerLayer,
    DeviceLayer,
    InputDeviceChanges,
    InputDevices,
    InputMode,
)
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.sources import install_sources

# An unmapped joystick: device index 0, instance id 5
STICK = DeviceDescriptor(
    kind=JOYSTICK_KIND,
    device_index=0,
    instance_id=5,
    name='Flight Stick',
    guid='0300aaaa',
    axis_count=3,
    button_count=2,
    hat_count=1,
    ball_count=1,
)
# A mapped pad: device index 1, instance id 9
PAD = DeviceDescriptor(
    kind=CONTROLLER_KIND,
    device_index=1,
    instance_id=9,
    name='Game Pad',
    guid='0300bbbb',
    axis_count=6,
    button_count=15,
    hat_count=1,
    ball_count=0,
)


class ReplayDeviceSources(LiveSources):
    """Live doors whose devices are a replay registry's stand-ins (no hardware)."""

    def __init__(self: Self, *, registry: ReplayDeviceRegistry) -> None:
        """Create the doors around the registry."""
        super().__init__(random_seed=1)
        self.registry = registry

    def devices(self: Self) -> ReplayDeviceRegistry:
        return self.registry


# What pygame raises for a device unplugged since it was opened
UNPLUGGED_ERROR_MESSAGE = 'Joystick not initialized'


class UnpluggedJoystick(ReplayJoystick):
    """A stand-in joystick unplugged since it was opened: rumbling it raises pygame.error."""

    def rumble(self: Self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        del low_frequency, high_frequency, duration
        raise pygame.error(UNPLUGGED_ERROR_MESSAGE)

    def stop_rumble(self: Self) -> None:
        raise pygame.error(UNPLUGGED_ERROR_MESSAGE)


class RecordingController(ReplayController):
    """A stand-in controller that remembers the rumble requests it was sent."""

    def __init__(self: Self, *, descriptor: DeviceDescriptor) -> None:
        """Create the stand-in with no requests yet."""
        super().__init__(descriptor=descriptor)
        self.rumble_requests: list[tuple[float, float, int]] = []
        self.stopped = False

    def rumble(self: Self, low_frequency: float, high_frequency: float, duration: int) -> bool:
        self.rumble_requests.append((low_frequency, high_frequency, duration))
        return True

    def stop_rumble(self: Self) -> None:
        self.stopped = True


def _install(*, is_controller_answers: dict[int, bool] | None = None) -> ReplayDeviceRegistry:
    """Install doors serving STICK and PAD, answering is_controller by device index.

    Returns:
        The installed registry.

    """
    registry = ReplayDeviceRegistry(
        descriptors=[STICK, PAD],
        enumeration_answers=[
            EnumerationAnswer(call=IS_CONTROLLER_CALL, device_index=device_index, value=value)
            for device_index, value in (is_controller_answers or {}).items()
        ],
    )
    install_sources(sources=ReplayDeviceSources(registry=registry))
    return registry


def _set_snapshot(**device_fields: object) -> None:
    """Make a snapshot holding the given device fields this frame's input."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            **device_fields,
        )
    )


def _opened(registry: ReplayDeviceRegistry) -> tuple[ReplayJoystick, ReplayController]:
    """Open STICK as a joystick and PAD as a controller (and as a joystick), as the managers do.

    Returns:
        The joystick and the controller.

    """
    stick = registry.open_joystick(device_index=STICK.device_index)
    pad = registry.open_controller(device_index=PAD.device_index)
    return stick, pad


class TestLayers:
    """Both layers read the frame's snapshot by instance id, never the device."""

    def test_joystick_layer_reads_the_snapshot_with_the_descriptors_counts(self):
        """Axes, buttons and hats come from the snapshot's joystick layer, padded to the counts."""
        registry = _install(is_controller_answers={0: False})
        stick, _pad = _opened(registry)
        devices = InputDevices()
        devices.synchronize(joysticks={5: stick}, controllers={})
        _set_snapshot(
            device_axes={5: (0.5, -1.0)},
            device_buttons={5: (False, True)},
            device_hats={5: ((1, -1),)},
        )

        device = devices.get(instance_id=5)

        assert device is not None
        layer = device.joystick
        assert layer.kind is DeviceLayer.JOYSTICK
        assert (layer.axis_count, layer.button_count, layer.hat_count, layer.ball_count) == (
            3,
            2,
            1,
            1,
        )
        # The third axis is not in the snapshot: it reads as centred
        assert layer.axes == (0.5, -1.0, 0.0)
        assert layer.buttons == (False, True)
        assert layer.hats == ((1, -1),)
        assert layer.axis(axis=1) == -1.0
        assert layer.button(button=1) is True
        assert layer.hat(hat=0) == (1, -1)

    def test_controller_layer_reads_every_controller_id_from_the_snapshot(self):
        """The controller layer reads every CONTROLLER_AXIS_* / CONTROLLER_BUTTON_* id."""
        _set_snapshot(
            controller_axes={9: (100, -200, 0, 0, 32767, 0)},
            controller_buttons={9: (True, False, True)},
        )
        layer = ControllerLayer(instance_id=9)

        assert layer.kind is DeviceLayer.CONTROLLER
        assert layer.axes == (100, -200, 0, 0, 32767, 0)
        assert len(layer.buttons) == pygame.CONTROLLER_BUTTON_MAX
        assert layer.buttons[:3] == (True, False, True)
        assert layer.hats == ()
        assert layer.axis(axis=pygame.CONTROLLER_AXIS_TRIGGERLEFT) == 32767
        assert layer.button(button=pygame.CONTROLLER_BUTTON_X) is True


class TestSynchronize:
    """The registry follows the devices the joystick and controller managers hold."""

    def test_auto_mode_adds_an_unmapped_joystick_and_a_mapped_pad_with_both_layers(self):
        """An unmapped joystick dispatches its joystick layer, a mapped pad its controller one."""
        registry = _install(is_controller_answers={0: False})
        stick, pad = _opened(registry)
        devices = InputDevices(input_mode=InputMode.AUTO)

        changes = devices.synchronize(
            joysticks={5: stick, 9: pad.as_joystick()}, controllers={9: pad}
        )

        assert [device.instance_id for device in changes.added] == [9, 5]
        assert changes.removed == ()
        assert [device.instance_id for device in devices] == [9, 5]
        assert len(devices) == 2
        stick_device = devices.get(instance_id=5)
        pad_device = devices.get(instance_id=9)
        assert stick_device is not None
        assert pad_device is not None
        assert stick_device.controller is None
        assert stick_device.event_layer is stick_device.joystick
        assert pad_device.controller is not None
        assert pad_device.event_layer is pad_device.controller
        assert pad_device.name == 'Game Pad'
        assert pad_device.descriptor == PAD
        assert devices.input_mode is InputMode.AUTO

    def test_synchronizing_again_changes_nothing(self):
        """A device is added once."""
        registry = _install(is_controller_answers={0: False})
        stick, pad = _opened(registry)
        devices = InputDevices()
        devices.synchronize(joysticks={5: stick}, controllers={9: pad})

        assert devices.synchronize(
            joysticks={5: stick}, controllers={9: pad}
        ) == InputDeviceChanges(added=(), removed=())

    def test_a_mapped_pad_waits_for_its_controller_and_is_added_once(self):
        """JOYDEVICEADDED comes before CONTROLLERDEVICEADDED: the pad is added at the second."""
        registry = _install(is_controller_answers={1: True})
        pad = registry.open_controller(device_index=1)
        devices = InputDevices()

        waiting = devices.synchronize(joysticks={9: pad.as_joystick()}, controllers={})
        arrived = devices.synchronize(joysticks={9: pad.as_joystick()}, controllers={9: pad})

        assert waiting.added == ()
        assert [device.instance_id for device in arrived.added] == [9]
        device = devices.get(instance_id=9)
        assert device is not None
        assert device.controller is not None

    def test_a_device_is_removed_once_neither_manager_holds_it(self):
        """A mapped pad's two removal events: it goes when the second manager lets it go."""
        registry = _install(is_controller_answers={0: False})
        stick, pad = _opened(registry)
        devices = InputDevices()
        devices.synchronize(joysticks={5: stick, 9: pad.as_joystick()}, controllers={9: pad})

        after_joystick_removal = devices.synchronize(joysticks={5: stick}, controllers={9: pad})
        after_controller_removal = devices.synchronize(joysticks={5: stick}, controllers={})

        assert after_joystick_removal.removed == ()
        assert [device.instance_id for device in after_controller_removal.removed] == [9]
        assert devices.get(instance_id=9) is None

    def test_a_device_added_on_the_joystick_layer_gets_its_controller_later(self):
        """A device SDL maps after it was added dispatches its controller layer from then on."""
        registry = _install(is_controller_answers={1: False})
        pad = registry.open_controller(device_index=1)
        devices = InputDevices()
        devices.synchronize(joysticks={9: pad.as_joystick()}, controllers={})
        device = devices.get(instance_id=9)
        assert device is not None
        assert device.controller is None

        changes = devices.synchronize(joysticks={9: pad.as_joystick()}, controllers={9: pad})

        assert changes == InputDeviceChanges()
        assert device.controller is not None
        assert device.event_layer.kind is DeviceLayer.CONTROLLER

    def test_joystick_mode_sees_every_device_on_its_joystick_layer_only(self, caplog):
        """Joystick mode ignores the controllers and never asks the door about mappings."""
        registry = _install()
        stick, pad = _opened(registry)
        devices = InputDevices(input_mode=InputMode.JOYSTICK)

        devices.synchronize(joysticks={5: stick, 9: pad.as_joystick()}, controllers={9: pad})

        assert [device.controller for device in devices] == [None, None]
        assert 'is_controller' not in caplog.text

    def test_controller_mode_hides_unmapped_devices(self):
        """Controller mode sees mapped pads only."""
        registry = _install()
        stick, pad = _opened(registry)
        devices = InputDevices(input_mode=InputMode.CONTROLLER)

        devices.synchronize(joysticks={5: stick, 9: pad.as_joystick()}, controllers={9: pad})

        assert [device.instance_id for device in devices] == [9]

    def test_a_failed_mapping_question_reads_the_device_as_a_joystick(self):
        """When the door cannot say whether a device is mapped, it is added as a joystick."""
        registry = ReplayDeviceRegistry(
            descriptors=[STICK],
            enumeration_answers=[
                EnumerationAnswer(
                    call=IS_CONTROLLER_CALL, device_index=0, value=None, error='SDL is gone'
                )
            ],
        )
        install_sources(sources=ReplayDeviceSources(registry=registry))
        stick = registry.open_joystick(device_index=0)
        devices = InputDevices()

        changes = devices.synchronize(joysticks={5: stick}, controllers={})

        assert [device.instance_id for device in changes.added] == [5]

    def test_a_device_the_door_did_not_open_is_ignored(self, caplog):
        """A device without a door descriptor (opened around the door) is never added."""
        _install()
        outside_the_door = ReplayJoystick(descriptor=STICK)
        devices = InputDevices(input_mode=InputMode.JOYSTICK)

        with caplog.at_level('WARNING', logger='game.input.input_devices'):
            changes = devices.synchronize(joysticks={5: outside_the_door}, controllers={})

        assert changes.added == ()
        assert 'Device 5 was not opened through the devices door' in caplog.text

    def test_a_controller_the_door_did_not_open_is_ignored(self, caplog):
        """A controller without a door descriptor is never added either."""
        _install()
        outside_the_door = ReplayController(descriptor=PAD)
        devices = InputDevices(input_mode=InputMode.CONTROLLER)

        with caplog.at_level('WARNING', logger='game.input.input_devices'):
            changes = devices.synchronize(joysticks={}, controllers={9: outside_the_door})

        assert changes.added == ()
        assert 'Device 9 was not opened through the devices door' in caplog.text

    def test_auto_mode_reads_a_device_without_a_descriptor_as_not_waiting(self, caplog):
        """In auto mode the mapping question needs the descriptor; without one it is skipped."""
        _install()
        outside_the_door = ReplayJoystick(descriptor=STICK)
        devices = InputDevices(input_mode=InputMode.AUTO)

        changes = devices.synchronize(joysticks={5: outside_the_door}, controllers={})

        assert changes.added == ()
        assert 'is_controller' not in caplog.text


class TestDispatch:
    """Each device's input events reach handlers from one layer only."""

    @pytest.fixture
    def devices(self) -> InputDevices:
        """A registry seeing STICK (unmapped) and PAD (mapped), in auto mode.

        Returns:
            The registry.

        """
        registry = _install(is_controller_answers={0: False})
        stick, pad = _opened(registry)
        devices = InputDevices()
        devices.synchronize(joysticks={5: stick, 9: pad.as_joystick()}, controllers={9: pad})
        return devices

    @pytest.mark.parametrize('event_type', sorted(JOYSTICK_INPUT_EVENT_TYPES))
    def test_joystick_events_dispatch_from_unmapped_devices_only(self, devices, event_type):
        """A mapped pad's joystick-layer events are dropped; an unmapped joystick's pass."""
        assert devices.dispatches(event_type=event_type, instance_id=5) is True
        assert devices.dispatches(event_type=event_type, instance_id=9) is False

    @pytest.mark.parametrize('event_type', sorted(CONTROLLER_INPUT_EVENT_TYPES))
    def test_controller_events_dispatch_from_mapped_devices_only(self, devices, event_type):
        """Controller-layer events pass only for a device with a controller layer."""
        assert devices.dispatches(event_type=event_type, instance_id=9) is True
        assert devices.dispatches(event_type=event_type, instance_id=5) is False

    def test_events_of_devices_the_game_does_not_see_are_dropped(self, devices):
        """A device the registry does not hold dispatches nothing."""
        assert devices.dispatches(event_type=pygame.JOYBUTTONDOWN, instance_id=77) is False
        assert devices.dispatches(event_type=pygame.CONTROLLERBUTTONDOWN, instance_id=77) is False

    @pytest.mark.parametrize(
        'event_type',
        [
            pygame.JOYDEVICEADDED,
            pygame.JOYDEVICEREMOVED,
            pygame.CONTROLLERDEVICEADDED,
            pygame.CONTROLLERDEVICEREMOVED,
            pygame.CONTROLLERDEVICEREMAPPED,
        ],
    )
    def test_device_events_always_pass(self, devices, event_type):
        """Device events are not input events (rule 1)."""
        assert devices.dispatches(event_type=event_type, instance_id=77) is True


class TestRumble:
    """Rumble goes to the controller when the device has one, else to the joystick."""

    def test_a_mapped_pad_rumbles_through_its_controller(self):
        """The controller gets the request; stop_rumble stops it."""
        controller = RecordingController(descriptor=PAD)
        device = ConnectedInputDevice(
            descriptor=PAD, joystick=controller.as_joystick(), controller=controller
        )

        assert device.rumble(low_frequency=0.5, high_frequency=0.25, duration_milliseconds=100)
        device.stop_rumble()

        assert controller.rumble_requests == [(0.5, 0.25, 100)]
        assert controller.stopped is True

    def test_a_joystick_rumbles_itself(self):
        """Without a controller layer the joystick is rumbled (a stand-in accepts and drops it)."""
        device = ConnectedInputDevice(
            descriptor=STICK, joystick=ReplayJoystick(descriptor=STICK), controller=None
        )

        assert device.rumble(low_frequency=1.0, high_frequency=1.0, duration_milliseconds=0)
        device.stop_rumble()

    def test_an_unplugged_device_cannot_rumble(self, caplog):
        """A device gone since it was opened answers False and stops quietly."""
        unplugged = UnpluggedJoystick(descriptor=STICK)
        device = ConnectedInputDevice(descriptor=STICK, joystick=unplugged, controller=None)

        with caplog.at_level('DEBUG', logger='game.input.input_devices'):
            assert not device.rumble(
                low_frequency=1.0, high_frequency=1.0, duration_milliseconds=10
            )
            device.stop_rumble()

        assert 'Device 5 could not rumble' in caplog.text
        assert 'Device 5 could not stop rumbling' in caplog.text

    def test_attach_controller_routes_rumble_to_the_new_controller(self):
        """A late mapping rumbles through the controller attached."""
        controller = RecordingController(descriptor=PAD)
        device = ConnectedInputDevice(
            descriptor=PAD, joystick=UnpluggedJoystick(descriptor=PAD), controller=None
        )

        device.attach_controller(controller=controller)

        assert device.rumble(low_frequency=0.1, high_frequency=0.2, duration_milliseconds=3)
        assert controller.rumble_requests == [(0.1, 0.2, 3)]


def test_an_input_event_without_an_instance_id_is_dropped():
    """An input event naming no device reaches no handler."""
    assert InputDevices().dispatches(event_type=pygame.JOYBUTTONDOWN, instance_id=None) is False
