"""The devices door (glitchygames/input/devices.py)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.input.devices import (
    DeviceDescriptor,
    EnumerationAnswer,
    LiveDeviceRegistry,
    PolledDevices,
    ReplayController,
    ReplayDeviceRegistry,
    ReplayJoystick,
)
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.live_sources import LiveSources

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
    # The same kind of object live returns: a controller's joystick view
    assert registry.joystick_for_instance(instance_id=7) is controller.as_joystick()
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
    assert registry.poll() == PolledDevices(
        axes={}, buttons={}, hats={}, controller_axes={}, controller_buttons={}
    )


def test_live_poll_drops_a_controller_whose_controller_layer_fails(mocker):
    """A controller that errors on the controller layer is absent from both layers."""
    fake_controller = make_fake_controller(mocker=mocker, instance_id=12)
    fake_controller.get_axis.side_effect = pygame.error('Controller not attached')
    mocker.patch('pygame._sdl2.controller.Controller', return_value=fake_controller)
    registry = LiveDeviceRegistry()
    registry.open_controller(device_index=0)
    assert registry.poll() == PolledDevices(
        axes={}, buttons={}, hats={}, controller_axes={}, controller_buttons={}
    )


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


def fake_controller_axis(axis: int) -> int:
    """Return a distinct pygame-scale value per controller axis id (the live fake's axes).

    Returns:
        The axis value.

    """
    return {pygame.CONTROLLER_AXIS_TRIGGERLEFT: 32767, pygame.CONTROLLER_AXIS_LEFTX: -32768}.get(
        axis, axis
    )


def fake_controller_button(button: int) -> bool:
    """Return True for CONTROLLER_BUTTON_A only (the live fake's buttons).

    Returns:
        Whether the button is held.

    """
    return button == pygame.CONTROLLER_BUTTON_A


def make_fake_controller(*, mocker, instance_id: int):
    """Return a mocked pygame Controller whose joystick view and controller layer differ.

    Returns:
        The fake controller.

    """
    joystick_view = mocker.Mock(**{
        'get_instance_id.return_value': instance_id,
        'get_name.return_value': 'Fake Controller',
        'get_guid.return_value': 'guid',
        'get_numaxes.return_value': 2,
        'get_numbuttons.return_value': 2,
        'get_numhats.return_value': 1,
        'get_numballs.return_value': 0,
        'get_axis.side_effect': lambda index: [0.25, -0.75][index],
        'get_button.side_effect': lambda index: [False, True][index],
        'get_hat.return_value': (0, -1),
    })
    return mocker.Mock(**{
        'as_joystick.return_value': joystick_view,
        'get_axis.side_effect': fake_controller_axis,
        'get_button.side_effect': fake_controller_button,
    })


def test_live_and_replay_controllers_answer_the_same_on_both_layers(mocker):
    """A controller read live and its replay stand-in agree for the same snapshot."""
    fake_controller = make_fake_controller(mocker=mocker, instance_id=12)
    mocker.patch('pygame._sdl2.controller.Controller', return_value=fake_controller)
    sources = LiveSources(random_seed=1)
    live_controller = sources.devices().open_controller(device_index=0)
    snapshot = sources.input_snapshot()
    live_joystick_view = sources.devices().joystick_for_instance(instance_id=12)

    replay = ReplayDeviceRegistry(
        descriptors=sources.devices().take_opened_descriptors(), enumeration_answers=[]
    )
    set_current_input(snapshot=snapshot)
    replay_controller = replay.open_controller(device_index=0)
    replay_joystick_view = replay.joystick_for_instance(instance_id=12)
    assert replay_joystick_view is not None

    for axis in range(pygame.CONTROLLER_AXIS_MAX):
        assert replay_controller.get_axis(axis) == live_controller.get_axis(axis)
    for button in range(pygame.CONTROLLER_BUTTON_MAX):
        assert replay_controller.get_button(button) == live_controller.get_button(button)
    assert replay_controller.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT) == 32767
    for index in range(2):
        assert replay_joystick_view.get_axis(index) == live_joystick_view.get_axis(index)
        assert replay_joystick_view.get_button(index) == live_joystick_view.get_button(index)
    assert replay_joystick_view.get_hat(0) == live_joystick_view.get_hat(0) == (0, -1)
    assert replay_controller.as_joystick() is replay_joystick_view


def test_a_failed_live_open_is_recorded_and_fails_the_same_in_replay(mocker):
    """Hotplug race: the device vanishes before the open; the replay's open fails the same way."""
    mocker.patch('pygame.joystick.Joystick', side_effect=pygame.error('Invalid joystick device'))
    live = LiveDeviceRegistry()
    with pytest.raises(pygame.error, match='Invalid joystick device'):
        live.open_joystick(device_index=2)
    answers = live.take_enumeration_answers()
    assert answers == [
        EnumerationAnswer(
            call='open_joystick', device_index=2, value=None, error='Invalid joystick device'
        )
    ]
    assert live.take_opened_descriptors() == []

    recorded = [EnumerationAnswer.from_json(answer.to_json()) for answer in answers]
    replay = ReplayDeviceRegistry(descriptors=[PAD], enumeration_answers=recorded)
    with pytest.raises(pygame.error, match='Invalid joystick device'):
        replay.open_joystick(device_index=2)


def test_a_retry_after_a_failed_open_opens_in_replay_too(mocker):
    """Opens answer in recorded order: the failure, then the later successful open."""
    fake_device = mocker.Mock(**{
        'get_instance_id.return_value': 7,
        'get_name.return_value': 'Test Pad',
        'get_guid.return_value': 'abc',
        'get_numaxes.return_value': 2,
        'get_numbuttons.return_value': 3,
        'get_numhats.return_value': 1,
        'get_numballs.return_value': 0,
    })
    mocker.patch(
        'pygame.joystick.Joystick',
        side_effect=[pygame.error('Invalid joystick device'), fake_device],
    )
    live = LiveDeviceRegistry()
    with pytest.raises(pygame.error):
        live.open_joystick(device_index=0)
    live.open_joystick(device_index=0)

    replay = ReplayDeviceRegistry(
        descriptors=live.take_opened_descriptors(),
        enumeration_answers=live.take_enumeration_answers(),
    )
    with pytest.raises(pygame.error, match='Invalid joystick device'):
        replay.open_joystick(device_index=0)
    assert replay.open_joystick(device_index=0).get_name() == 'Test Pad'


def test_a_failed_live_enumeration_is_recorded_and_fails_the_same_in_replay(mocker):
    """An enumeration call that raises live is recorded and raises again in replay."""
    mocker.patch(
        'pygame._sdl2.controller.is_controller', side_effect=pygame.error('Index out of range')
    )
    live = LiveDeviceRegistry()
    with pytest.raises(pygame.error, match='Index out of range'):
        live.is_controller(device_index=4)
    replay = ReplayDeviceRegistry(
        descriptors=[], enumeration_answers=live.take_enumeration_answers()
    )
    with pytest.raises(pygame.error, match='Index out of range'):
        replay.is_controller(device_index=4)


def test_descriptors_sharing_a_device_index_are_all_kept_in_order(caplog):
    """A reused device index (unplug, replug) keeps both devices, warns, and counts both."""
    replugged = DeviceDescriptor(
        kind='joystick',
        device_index=0,
        instance_id=8,
        name='Replugged Pad',
        guid='def',
        axis_count=2,
        button_count=3,
        hat_count=1,
        ball_count=0,
    )
    registry = ReplayDeviceRegistry(descriptors=[PAD, replugged], enumeration_answers=[])
    assert 'device index 0 again' in caplog.text
    assert registry.joystick_count() == 2
    assert registry.open_joystick(device_index=0).get_instance_id() == 7
    assert registry.open_joystick(device_index=0).get_instance_id() == 8


def test_a_controller_whose_joystick_view_fails_is_closed_again(mocker):
    """A controller that opens but cannot be described is quit before the failure is raised."""
    fake_controller = mocker.Mock(**{
        'as_joystick.side_effect': pygame.error('Controller not attached'),
    })
    mocker.patch('pygame._sdl2.controller.Controller', return_value=fake_controller)
    registry = LiveDeviceRegistry()
    with pytest.raises(pygame.error, match='Controller not attached'):
        registry.open_controller(device_index=0)
    fake_controller.quit.assert_called_once_with()
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(
            call='open_controller', device_index=0, value=None, error='Controller not attached'
        )
    ]


def test_live_poll_forgets_a_device_that_raises(mocker):
    """A device that errors while polled is forgotten: it is not polled (or logged) again."""
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

    registry.poll()
    registry.poll()

    assert fake_device.get_axis.call_count == 1
    assert registry.joystick_for_instance(instance_id=4) is None


def test_live_poll_forgets_a_detached_controller(mocker):
    """A controller that reports itself detached is forgotten without reading it."""
    fake_controller = make_fake_controller(mocker=mocker, instance_id=12)
    fake_controller.attached.return_value = False
    mocker.patch('pygame._sdl2.controller.Controller', return_value=fake_controller)
    registry = LiveDeviceRegistry()
    registry.open_controller(device_index=0)

    assert registry.poll() == PolledDevices(
        axes={}, buttons={}, hats={}, controller_axes={}, controller_buttons={}
    )
    assert registry.joystick_for_instance(instance_id=12) is None
    fake_controller.get_axis.assert_not_called()
    fake_controller.as_joystick.return_value.get_axis.assert_not_called()


def test_live_registry_forgets_a_removed_device(mocker):
    """forget_device (the device-removed path) stops polling and looking up the device."""
    fake_controller = make_fake_controller(mocker=mocker, instance_id=12)
    mocker.patch('pygame._sdl2.controller.Controller', return_value=fake_controller)
    registry = LiveDeviceRegistry()
    registry.open_controller(device_index=0)

    registry.forget_device(instance_id=12)
    registry.forget_device(instance_id=12)  # a second removal event is harmless

    assert registry.joystick_for_instance(instance_id=12) is None
    assert registry.poll().controller_axes == {}


def test_replay_registry_forgets_a_removed_device():
    """The replay registry forgets a removed stand-in as live play does."""
    registry = ReplayDeviceRegistry(descriptors=[PAD], enumeration_answers=[])
    registry.open_joystick(device_index=0)

    registry.forget_device(instance_id=7)

    assert registry.joystick_for_instance(instance_id=7) is None


def test_live_frames_without_a_recorder_keep_no_enumeration_answers(mocker):
    """Untaken answers and descriptors are discarded at the end of every live frame."""
    mocker.patch('pygame.joystick.get_count', return_value=1)
    fake_device = mocker.Mock(**{
        'get_instance_id.return_value': 4,
        'get_name.return_value': 'Pad',
        'get_guid.return_value': 'g',
        'get_numaxes.return_value': 0,
        'get_numbuttons.return_value': 0,
        'get_numhats.return_value': 0,
        'get_numballs.return_value': 0,
    })
    mocker.patch('pygame.joystick.Joystick', return_value=fake_device)
    sources = LiveSources(random_seed=1)
    registry = sources.devices()

    for frame_number in range(5):
        registry.joystick_count()
        registry.open_joystick(device_index=0)
        sources.end_frame(frame_number=frame_number, dt=0.016, scene=None, control_events=[])

        assert registry.take_enumeration_answers() == []
        assert registry.take_opened_descriptors() == []


def test_answers_taken_before_the_end_of_a_live_frame_are_intact(mocker):
    """A recorder takes the frame's answers before end_frame discards what is left."""
    mocker.patch('pygame.joystick.get_count', return_value=2)
    sources = LiveSources(random_seed=1)
    registry = sources.devices()

    registry.joystick_count()
    taken = registry.take_enumeration_answers()
    sources.end_frame(frame_number=0, dt=0.016, scene=None, control_events=[])

    assert taken == [EnumerationAnswer(call='joystick_count', device_index=None, value=2)]
