"""The devices door (glitchygames/input/devices.py)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.input.devices import (
    DeviceDescriptor,
    EnumerationAnswer,
    LiveDeviceRegistry,
    ReplayController,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.state import InputSnapshot, set_current_input

PAD = DeviceDescriptor(
    kind='joystick',
    device_index=0,
    instance_id=7,
    name='Test Pad',
    guid='abc',
    axis_count=2,
    button_count=3,
    hat_count=1,
    ball_count=0,
)


@pytest.fixture(autouse=True)
def initialized_pygame():
    """Key and device lookups need SDL initialized (always true in a running engine)."""
    if not pygame.get_init():
        pygame.init()


def test_descriptor_round_trips_through_json():
    """A descriptor survives to_json/from_json unchanged."""
    assert DeviceDescriptor.from_json(PAD.to_json()) == PAD


def test_enumeration_answer_round_trips_through_json():
    """An enumeration answer survives to_json/from_json unchanged."""
    answer = EnumerationAnswer(call='name_for_index', device_index=2, value='Pad')
    assert EnumerationAnswer.from_json(answer.to_json()) == answer


def test_replay_joystick_answers_from_the_descriptor_and_the_snapshot():
    """The stand-in reads counts from its descriptor and positions from current_input()."""
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            device_axes={7: (0.5, -0.25)},
            device_buttons={7: (False, True, False)},
            device_hats={7: ((0, 1),)},
        )
    )
    joystick = ReplayJoystick(descriptor=PAD)
    joystick.init()
    assert joystick.get_name() == 'Test Pad'
    assert joystick.get_instance_id() == 7
    assert joystick.get_numaxes() == 2
    assert joystick.get_axis(1) == -0.25
    assert joystick.get_button(1) is True
    assert joystick.get_hat(0) == (0, 1)
    assert joystick.rumble(0.5, 0.5, 100) is True  # accepted and dropped


def test_replay_controller_offers_the_controller_surface():
    """The controller stand-in offers every Controller member the proxies use."""
    controller = ReplayController(descriptor=PAD)
    assert controller.name == 'Test Pad'
    assert controller.id == 0
    assert controller.attached() is True
    assert controller.get_mapping() == {}
    assert controller.set_led((255, 0, 0)) is False  # stand-ins have no LED
    assert controller.as_joystick().get_instance_id() == 7


def test_replay_registry_never_opens_real_hardware(mocker):
    """A replay registry answers with stand-ins and never touches pygame devices."""
    real_joystick = mocker.patch('pygame.joystick.Joystick')
    real_controller = mocker.patch('pygame._sdl2.controller.Controller')
    real_count = mocker.patch('pygame.joystick.get_count', return_value=5)
    registry = ReplayDeviceRegistry(descriptors=[PAD], enumeration_answers=[])
    joystick = registry.open_joystick(device_index=0)
    controller = registry.open_controller(device_index=0)
    assert isinstance(joystick, ReplayJoystick)
    assert isinstance(controller, ReplayController)
    assert registry.joystick_count() == 1  # the recording's device, not the 5 plugged in
    assert registry.joystick_for_instance(instance_id=7) is controller
    real_joystick.assert_not_called()
    real_controller.assert_not_called()
    real_count.assert_not_called()


def test_replay_enumeration_answers_in_recorded_order_then_repeats_the_last():
    """Recorded answers come back in order, then the last one repeats."""
    registry = ReplayDeviceRegistry(
        descriptors=[],
        enumeration_answers=[
            EnumerationAnswer(call='controller_count', device_index=None, value=1),
            EnumerationAnswer(call='controller_count', device_index=None, value=2),
            EnumerationAnswer(call='is_controller', device_index=1, value=True),
        ],
    )
    assert [registry.controller_count() for _ in range(3)] == [1, 2, 2]
    assert registry.is_controller(device_index=1) is True


def test_replay_enumeration_never_recorded_warns_once_per_key(caplog):
    """An unrecorded call answers from the descriptors and warns once per call and index."""
    registry = ReplayDeviceRegistry(descriptors=[PAD], enumeration_answers=[])
    assert registry.name_for_index(device_index=0) == 'Test Pad'
    assert registry.name_for_index(device_index=0) == 'Test Pad'
    assert registry.is_controller(device_index=0) is False
    assert caplog.text.count('name_for_index(0) is not in the recording') == 1
    assert caplog.text.count('is_controller(0) is not in the recording') == 1


def test_replay_registry_unknown_device_gets_a_named_stand_in(caplog):
    """Opening a device the recording never saw gives a named stand-in and a warning."""
    registry = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])
    joystick = registry.open_joystick(device_index=3)
    assert joystick.get_name() == 'Unrecorded device 3'
    assert 'not in the recording' in caplog.text


def test_replay_registry_hands_learned_descriptors_out_once():
    """Descriptors learned from frame fields are opened by index and taken once."""
    registry = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])
    registry.add_descriptors(descriptors=[PAD])
    assert registry.open_joystick(device_index=0).get_name() == 'Test Pad'
    assert registry.take_opened_descriptors() == [PAD]
    assert registry.take_opened_descriptors() == []


def test_live_registry_remembers_enumeration_answers(mocker):
    """Live enumeration answers are remembered for the recorder and taken once."""
    mocker.patch('pygame.joystick.get_count', return_value=2)
    registry = LiveDeviceRegistry()
    assert registry.joystick_count() == 2
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='joystick_count', device_index=None, value=2)
    ]
    assert registry.take_enumeration_answers() == []


def test_live_snapshot_holds_opened_device_positions(mocker):
    """LiveSources polls opened devices into the snapshot and remembers their descriptors."""
    from glitchygames.live_sources import LiveSources

    fake_device = mocker.Mock(**{
        'get_instance_id.return_value': 4,
        'get_name.return_value': 'Pad',
        'get_guid.return_value': 'g',
        'get_numaxes.return_value': 1,
        'get_numbuttons.return_value': 1,
        'get_numhats.return_value': 1,
        'get_numballs.return_value': 0,
        'get_axis.return_value': 0.5,
        'get_button.return_value': True,
        'get_hat.return_value': (1, 0),
    })
    mocker.patch('pygame.joystick.Joystick', return_value=fake_device)
    sources = LiveSources(random_seed=1)
    sources.devices().open_joystick(device_index=0)
    snapshot = sources.input_snapshot()
    assert snapshot.axis(device_id=4, axis=0) == 0.5
    assert snapshot.button(device_id=4, button=0) is True
    assert snapshot.hat(device_id=4, hat=0) == (1, 0)
    assert sources.devices().take_opened_descriptors() == [
        DeviceDescriptor(
            kind='joystick',
            device_index=0,
            instance_id=4,
            name='Pad',
            guid='g',
            axis_count=1,
            button_count=1,
            hat_count=1,
            ball_count=0,
        )
    ]


def test_live_poll_skips_a_device_unplugged_since_it_was_opened(mocker):
    """A device that errors while polled is absent from all three mappings."""
    fake_device = mocker.Mock(**{
        'get_instance_id.return_value': 4,
        'get_name.return_value': 'Pad',
        'get_guid.return_value': 'g',
        'get_numaxes.return_value': 1,
        'get_numbuttons.return_value': 0,
        'get_numhats.return_value': 0,
        'get_numballs.return_value': 0,
        'get_axis.side_effect': pygame.error('Joystick not initialized'),
    })
    mocker.patch('pygame.joystick.Joystick', return_value=fake_device)
    registry = LiveDeviceRegistry()
    registry.open_joystick(device_index=0)
    assert registry.poll() == ({}, {}, {})


def test_live_name_for_index_asks_sdl_when_pygame_has_the_lookup(mocker):
    """With pygame's name_forindex the live name is SDL's, remembered for the recorder."""
    mocker.patch('pygame._sdl2.controller.name_forindex', create=True, return_value='Pad')
    registry = LiveDeviceRegistry()
    assert registry.name_for_index(device_index=1) == 'Pad'
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='name_for_index', device_index=1, value='Pad')
    ]


def test_live_name_for_index_is_none_without_the_lookup(mocker):
    """pygame-ce has no name_forindex: the answer is None, still remembered."""
    mocker.patch('pygame._sdl2.controller.name_forindex', create=True, new=None)
    registry = LiveDeviceRegistry()
    assert registry.name_for_index(device_index=1) is None
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='name_for_index', device_index=1, value=None)
    ]
