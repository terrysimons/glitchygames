"""The devices door (glitchygames/input/devices.py)."""

from __future__ import annotations

import pygame
import pygame._sdl2.controller
import pygame.midi
import pytest

from glitchygames.input.devices import (
    MIDI_INPUT_KIND,
    MIDI_MESSAGES_PER_PORT_PER_FRAME,
    MIDI_OUTPUT_KIND,
    MIDI_OVERFLOW_QUIET_READS,
    MIDI_READ_BATCH,
    DeviceDescriptor,
    EnumerationAnswer,
    LiveDeviceRegistry,
    MidiPortDescriptor,
    MidiPortInfo,
    PolledDevices,
    ReadsMidiInput,
    ReplayController,
    ReplayDeviceRegistry,
    ReplayJoystick,
    ReplayMidiInput,
    ReplayMidiOutput,
    _import_sdl_controller_module,
    find_midi_port,
    sdl_controller_module,
)
from glitchygames.input.stand_in_devices import (
    STAND_IN_MIDI_QUEUE_CAPACITY,
    StandInPortMidiError,
)
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.live_sources import LiveSources
from glitchygames.sources import (
    active_sources,
    observe_device_answers,
    stop_observing_device_answers,
)
from tests.input.stand_in_devices import (
    STAND_IN_PAD,
    STAND_IN_STICK,
    install_stand_in_devices,
    stand_in_registry,
)

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
    assert joystick.get_id() == 0  # the recorded device index
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


@pytest.mark.parametrize(
    ('pygame_target', 'call', 'arguments', 'device_index'),
    [
        ('pygame.joystick.get_count', 'joystick_count', {}, None),
        ('pygame._sdl2.controller.get_count', 'controller_count', {}, None),
        ('pygame._sdl2.controller.name_forindex', 'name_for_index', {'device_index': 3}, 3),
        ('pygame._sdl2.controller.Controller', 'open_controller', {'device_index': 3}, 3),
    ],
)
def test_every_failed_live_call_is_recorded_and_fails_the_same_in_replay(
    mocker, pygame_target, call, arguments, device_index
):
    """Each enumeration or open that raises live is remembered, then raises again in replay."""
    mocker.patch(pygame_target, create=True, side_effect=pygame.error('SDL is gone'))
    live = LiveDeviceRegistry()

    with pytest.raises(pygame.error, match='SDL is gone'):
        getattr(live, call)(**arguments)

    answers = live.take_enumeration_answers()
    assert answers == [
        EnumerationAnswer(call=call, device_index=device_index, value=None, error='SDL is gone')
    ]
    replay = ReplayDeviceRegistry(descriptors=[], enumeration_answers=answers)
    with pytest.raises(pygame.error, match='SDL is gone'):
        getattr(replay, call)(**arguments)


def test_live_is_controller_answer_is_remembered(mocker):
    """A live is_controller answer is returned as a bool and remembered for the recorder."""
    mocker.patch('pygame._sdl2.controller.is_controller', return_value=1)
    live = LiveDeviceRegistry()

    assert live.is_controller(device_index=2) is True
    assert live.take_enumeration_answers() == [
        EnumerationAnswer(call='is_controller', device_index=2, value=True)
    ]


def test_replay_stand_ins_drop_hardware_requests():
    """Quit, balls, LEDs and rumble touch no hardware: answers match pygame's for no device."""
    joystick = ReplayJoystick(descriptor=PAD)
    joystick.init()
    joystick.quit()
    assert joystick.get_init() is False
    assert joystick.get_ball(0) == (0, 0)
    assert joystick.set_led((0, 255, 0)) is False

    controller = ReplayController(descriptor=PAD)
    controller.init()
    assert controller.get_init() is True
    controller.quit()
    assert controller.get_init() is False
    assert controller.rumble(0.5, 0.5, 100) is True


def test_replay_stand_ins_are_initialized_on_creation():
    """Opened stand-ins answer get_init() True before any init(), as pygame-ce's devices do.

    pygame-ce opens a Joystick or Controller on creation (its ``Joystick.init`` is deprecated),
    so a live device answers True right away; code that asks before calling init() (Bitmappy's
    controller scan) must see the same answer in a replay.
    """
    registry = ReplayDeviceRegistry(descriptors=[PAD], enumeration_answers=[])

    assert registry.open_joystick(device_index=PAD.device_index).get_init() is True
    controller = registry.open_controller(device_index=PAD.device_index)
    assert controller.get_init() is True
    assert controller.as_joystick().get_init() is True


def test_replay_registry_has_no_enumeration_answers_to_hand_out():
    """A rebaseline copies answers from the source recording, so the replay hands out none."""
    registry = ReplayDeviceRegistry(
        descriptors=[PAD],
        enumeration_answers=[EnumerationAnswer(call='joystick_count', device_index=None, value=1)],
    )
    assert registry.joystick_count() == 1
    assert registry.take_enumeration_answers() == []


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


def test_live_registry_describes_each_opened_device_by_instance_id(mocker):
    """descriptor_for_instance answers with the descriptor the door recorded for the device.

    A game controller is opened on both layers (the controller manager, then the joystick
    manager): its controller descriptor is kept, not replaced by its joystick one.
    """
    fake_controller = make_fake_controller(mocker=mocker, instance_id=12)
    mocker.patch('pygame._sdl2.controller.Controller', return_value=fake_controller)
    mocker.patch('pygame.joystick.Joystick', return_value=fake_controller.as_joystick())
    registry = LiveDeviceRegistry()
    assert registry.descriptor_for_instance(instance_id=12) is None

    registry.open_controller(device_index=0)
    registry.open_joystick(device_index=0)

    descriptor = registry.descriptor_for_instance(instance_id=12)
    assert descriptor is not None
    assert descriptor.kind == 'controller'
    assert descriptor.instance_id == 12
    registry.forget_device(instance_id=12)
    assert registry.descriptor_for_instance(instance_id=12) is None


def test_live_registry_describes_a_plain_joystick_as_a_joystick(mocker):
    """A plain joystick's descriptor is the joystick one (kind 'joystick')."""
    fake_controller = make_fake_controller(mocker=mocker, instance_id=3)
    mocker.patch('pygame.joystick.Joystick', return_value=fake_controller.as_joystick())
    registry = LiveDeviceRegistry()

    registry.open_joystick(device_index=0)

    descriptor = registry.descriptor_for_instance(instance_id=3)
    assert descriptor is not None
    assert descriptor.kind == 'joystick'


def test_replay_registry_describes_each_opened_stand_in_by_instance_id():
    """A replay answers with the recorded descriptor of each stand-in it opened, until removed.

    Only opened devices are described (a recorded device not opened yet is not connected to
    the replayed game), and a controller's descriptor is kept over its joystick one.
    """
    controller_pad = DeviceDescriptor(**{**PAD.to_json(), 'kind': 'controller'})
    registry = ReplayDeviceRegistry(descriptors=[controller_pad], enumeration_answers=[])
    assert registry.descriptor_for_instance(instance_id=7) is None

    registry.open_controller(device_index=0)
    registry.open_joystick(device_index=0)

    assert registry.descriptor_for_instance(instance_id=7) == controller_pad
    registry.forget_device(instance_id=7)
    assert registry.descriptor_for_instance(instance_id=7) is None


def test_live_registry_without_controller_module_reports_no_controllers(mocker):
    """A pygame build without pygame._sdl2.controller answers as SDL with none plugged in.

    Stock Pyodide's pygame-ce compiles the module in but never registers it. Every answer is
    still remembered, so a recording made there replays the same.
    """
    mocker.patch('glitchygames.input.devices._SDL_CONTROLLER_MODULE', None)
    registry = LiveDeviceRegistry()

    assert registry.controller_count() == 0
    assert registry.is_controller(device_index=0) is False
    assert registry.name_for_index(device_index=0) is None
    with pytest.raises(pygame.error, match='game controllers are unavailable'):
        registry.open_controller(device_index=0)

    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='controller_count', device_index=None, value=0),
        EnumerationAnswer(call='is_controller', device_index=0, value=False),
        EnumerationAnswer(call='name_for_index', device_index=0, value=None),
        EnumerationAnswer(
            call='open_controller',
            device_index=0,
            value=None,
            error='game controllers are unavailable in this pygame build',
        ),
    ]


def test_sdl_controller_module_is_pygames_where_it_imports():
    """Desktop pygame-ce has the controller module: the door uses it."""
    assert sdl_controller_module() is pygame._sdl2.controller


def test_import_sdl_controller_module_is_none_when_it_cannot_import(mocker, caplog):
    """A pygame build without the controller module gives None, logged."""
    mocker.patch(
        'glitchygames.input.devices.importlib.import_module',
        side_effect=ModuleNotFoundError("No module named 'pygame._sdl2.controller'"),
    )
    with caplog.at_level('INFO', logger='game.input.devices'):
        assert _import_sdl_controller_module() is None

    assert 'pygame._sdl2.controller is unavailable' in caplog.text


def test_a_stand_in_registry_hands_a_recorder_what_it_opened_and_answered():
    """Stand-ins tell a recorder their answers and opened devices once each, as live play does."""
    registry = stand_in_registry(descriptors=[STAND_IN_STICK, STAND_IN_PAD])

    count = registry.joystick_count()
    controllers = registry.controller_count()
    stick_is_controller = registry.is_controller(device_index=STAND_IN_STICK.device_index)
    pad_name = registry.name_for_index(device_index=STAND_IN_PAD.device_index)
    registry.open_joystick(device_index=STAND_IN_STICK.device_index)
    registry.open_controller(device_index=STAND_IN_PAD.device_index)

    assert (count, controllers, stick_is_controller) == (2, 2, False)
    assert pad_name == STAND_IN_PAD.name
    assert registry.take_opened_descriptors() == [STAND_IN_STICK, STAND_IN_PAD]
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='joystick_count', device_index=None, value=2),
        EnumerationAnswer(call='controller_count', device_index=None, value=2),
        EnumerationAnswer(
            call='is_controller', device_index=STAND_IN_STICK.device_index, value=False
        ),
        EnumerationAnswer(
            call='name_for_index', device_index=STAND_IN_PAD.device_index, value=STAND_IN_PAD.name
        ),
        EnumerationAnswer(
            call='open_joystick',
            device_index=STAND_IN_STICK.device_index,
            value=STAND_IN_STICK.instance_id,
        ),
        EnumerationAnswer(
            call='open_controller',
            device_index=STAND_IN_PAD.device_index,
            value=STAND_IN_PAD.instance_id,
        ),
    ]
    # Taken once each
    assert registry.take_opened_descriptors() == []
    assert registry.take_enumeration_answers() == []


def test_stand_in_frames_without_a_recorder_keep_no_answers():
    """The stand-in doors discard untaken answers and descriptors at the end of every frame."""
    registry = install_stand_in_devices(descriptors=[STAND_IN_STICK])
    sources = active_sources()

    for frame_number in range(3):
        registry.joystick_count()
        registry.open_joystick(device_index=STAND_IN_STICK.device_index)
        sources.end_frame(frame_number=frame_number, dt=0.016, scene=None, control_events=[])

        assert registry.take_enumeration_answers() == []
        assert registry.take_opened_descriptors() == []


KEYS_PORT = MidiPortInfo(interface='CoreMIDI', name='Keys', is_input=True, is_output=False)
SYNTH_PORT = MidiPortInfo(interface='CoreMIDI', name='Synth', is_input=False, is_output=True)
MIDI_ANSWER_CALLS = [
    'midi_port_count',
    'midi_port_info',
    'midi_port_info',
    'default_midi_input_id',
    'default_midi_output_id',
]


def _patch_portmidi(mocker):
    """Stand in for pygame.midi as PortMidi answers (a keyboard, a synth); return it."""
    midi_module = mocker.Mock()
    mocker.patch('glitchygames.input.devices.import_midi_module', return_value=midi_module)
    midi_module.get_count.return_value = 2
    midi_module.get_device_info.side_effect = [
        (b'CoreMIDI', b'Keys', 1, 0, 0),
        (b'CoreMIDI', b'Synth', 0, 1, 0),
    ]
    midi_module.get_default_input_id.return_value = 0
    midi_module.get_default_output_id.return_value = 1
    return midi_module


def _ask_midi(registry):
    return (
        registry.midi_port_count(),
        registry.midi_port_info(port_id=0),
        registry.midi_port_info(port_id=1),
        registry.default_midi_input_id(),
        registry.default_midi_output_id(),
    )


def test_live_midi_enumeration_is_remembered(mocker):
    """Live MIDI answers are the ports' (names decoded) and remembered in call order."""
    _patch_portmidi(mocker)
    registry = LiveDeviceRegistry()

    assert _ask_midi(registry) == (2, KEYS_PORT, SYNTH_PORT, 0, 1)
    answers = registry.take_enumeration_answers()
    assert [answer.call for answer in answers] == MIDI_ANSWER_CALLS
    assert answers[0] == EnumerationAnswer(call='midi_port_count', device_index=None, value=2)
    assert answers[1] == EnumerationAnswer(
        call='midi_port_info', device_index=0, value=['CoreMIDI', 'Keys', True, False]
    )


def test_midi_port_names_with_undecodable_bytes_are_replaced(mocker):
    """A name that is not UTF-8 is decoded with replacement characters, not an error."""
    midi_module = _patch_portmidi(mocker)
    midi_module.get_device_info.side_effect = [(b'ALSA', b'Caf\xe9', 1, 0, 0)]

    info = LiveDeviceRegistry().midi_port_info(port_id=0)

    assert info == MidiPortInfo(interface='ALSA', name='Caf\ufffd', is_input=True, is_output=False)


def test_a_missing_midi_port_is_remembered_as_none(mocker):
    """PortMidi answers None for an id it does not have; a replay gives None too."""
    midi_module = _patch_portmidi(mocker)
    midi_module.get_device_info.side_effect = [None]
    registry = LiveDeviceRegistry()

    assert registry.midi_port_info(port_id=9) is None
    replay = ReplayDeviceRegistry(
        descriptors=[], enumeration_answers=registry.take_enumeration_answers()
    )
    assert replay.midi_port_info(port_id=9) is None


def test_replay_answers_midi_enumeration_as_recorded(mocker):
    """A replay gives the recorded MIDI answers and never touches pygame.midi."""
    midi_module = _patch_portmidi(mocker)
    live = LiveDeviceRegistry()
    live_answers = _ask_midi(live)
    recorded = live.take_enumeration_answers()
    midi_module.reset_mock()
    mocker.patch(
        'glitchygames.input.devices.import_midi_module',
        side_effect=pygame.error('replay must not ask PortMidi'),
    )

    replay = ReplayDeviceRegistry(descriptors=[], enumeration_answers=recorded)

    assert _ask_midi(replay) == live_answers
    assert midi_module.mock_calls == []


def test_replay_without_recorded_midi_answers_has_no_ports(caplog):
    """A recording with no MIDI answers has no ports, and says so once per call."""
    replay = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])

    assert _ask_midi(replay) == (0, None, None, -1, -1)
    assert 'midi_port_count' in caplog.text


def test_a_recorded_midi_failure_raises_again_in_replay(mocker):
    """A PortMidi error is recorded and a replay raises it again."""
    midi_module = _patch_portmidi(mocker)
    midi_module.get_count.side_effect = pygame.error('PortMidi is gone')
    live = LiveDeviceRegistry()
    with pytest.raises(pygame.error, match='PortMidi is gone'):
        live.midi_port_count()
    recorded = live.take_enumeration_answers()
    assert recorded == [
        EnumerationAnswer(
            call='midi_port_count', device_index=None, value=None, error='PortMidi is gone'
        )
    ]

    replay = ReplayDeviceRegistry(descriptors=[], enumeration_answers=recorded)
    with pytest.raises(pygame.error, match='PortMidi is gone'):
        replay.midi_port_count()


def test_malformed_recorded_midi_values_answer_as_no_ports():
    """A recorded value of the wrong shape is no port, no count and no default."""
    replay = ReplayDeviceRegistry(
        descriptors=[],
        enumeration_answers=[
            EnumerationAnswer(call='midi_port_count', device_index=None, value='two'),
            EnumerationAnswer(call='midi_port_info', device_index=0, value=['too', 'short']),
            EnumerationAnswer(call='default_midi_input_id', device_index=None, value='none'),
            EnumerationAnswer(call='default_midi_output_id', device_index=None, value=None),
        ],
    )

    assert _ask_midi(replay) == (0, None, None, -1, -1)


def test_no_portmidi_answers_zero_midi_ports(mocker):
    """Without PortMidi every MIDI call answers as no ports, and the answers are recorded."""
    mocker.patch('glitchygames.input.devices.import_midi_module', return_value=None)
    registry = LiveDeviceRegistry()

    assert (
        registry.midi_port_count(),
        registry.default_midi_input_id(),
        registry.default_midi_output_id(),
        registry.midi_port_info(port_id=0),
    ) == (0, -1, -1, None)
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='midi_port_count', device_index=None, value=0),
        EnumerationAnswer(call='default_midi_input_id', device_index=None, value=-1),
        EnumerationAnswer(call='default_midi_output_id', device_index=None, value=-1),
        EnumerationAnswer(call='midi_port_info', device_index=0, value=None),
    ]


def test_find_midi_port_matches_name_and_direction(mocker):
    """A port is found by name and by the direction the caller wants."""
    midi_module = _patch_portmidi(mocker)
    midi_module.get_device_info.side_effect = lambda port_id: [
        (b'CoreMIDI', b'Keys', 1, 0, 0),
        (b'CoreMIDI', b'Synth', 0, 1, 0),
    ][port_id]
    registry = LiveDeviceRegistry()

    assert find_midi_port(devices=registry, name='Keys', kind=MIDI_INPUT_KIND) == 0
    assert find_midi_port(devices=registry, name='Keys', kind=MIDI_OUTPUT_KIND) is None
    assert find_midi_port(devices=registry, name='Synth', kind=MIDI_OUTPUT_KIND) == 1
    assert find_midi_port(devices=registry, name='Nothing', kind=MIDI_INPUT_KIND) is None


def test_find_midi_port_skips_a_port_that_has_gone(mocker):
    """A port id with no info (unplugged between the count and the ask) is skipped."""
    midi_module = _patch_portmidi(mocker)
    midi_module.get_device_info.side_effect = [None, (b'CoreMIDI', b'Synth', 0, 1, 0)]

    assert find_midi_port(devices=LiveDeviceRegistry(), name='Synth', kind=MIDI_OUTPUT_KIND) == 1


def test_midi_enumeration_never_initializes_portmidi_until_asked(mocker):
    """Building the registry starts nothing; the first MIDI call initializes PortMidi once."""
    midi_module = _patch_portmidi(mocker)

    registry = LiveDeviceRegistry()
    assert midi_module.mock_calls == []

    _ask_midi(registry)
    registry.midi_port_count()
    midi_module.init.assert_called_once_with()


def test_midi_port_info_round_trips_through_an_answer_value():
    """The recorded list is what the port is read back from."""
    assert MidiPortInfo.from_answer_value(KEYS_PORT.to_answer_value()) == KEYS_PORT
    assert MidiPortInfo.from_answer_value(None) is None


def test_a_stand_in_registry_answers_midi_from_its_ports_and_tells_the_recorder():
    """Stand-in MIDI answers come from midi_ports (id = position) and are kept for a recorder."""
    registry = stand_in_registry(descriptors=[], midi_ports=[KEYS_PORT, SYNTH_PORT])

    assert _ask_midi(registry) == (2, KEYS_PORT, SYNTH_PORT, 0, 1)
    assert [answer.call for answer in registry.take_enumeration_answers()] == MIDI_ANSWER_CALLS
    assert registry.midi_port_info(port_id=2) is None
    assert registry.midi_port_info(port_id=-1) is None


def test_a_stand_in_registry_has_no_midi_ports_by_default():
    """Without midi_ports a stand-in registry counts none and has no defaults."""
    assert _ask_midi(install_stand_in_devices(descriptors=[])) == (0, None, None, -1, -1)


KEYS_DESCRIPTOR = MidiPortDescriptor(
    kind=MIDI_INPUT_KIND, port_id=0, name='Keys', interface='CoreMIDI'
)
SYNTH_DESCRIPTOR = MidiPortDescriptor(
    kind=MIDI_OUTPUT_KIND, port_id=1, name='Synth', interface='CoreMIDI'
)


def _patch_portmidi_ports(mocker):
    """Stand in for PortMidi with a keyboard (port 0) and a synth (port 1); return the module.

    Only the hardware is faked: the module's functions and the Input and Output constructors.
    """
    midi_module = mocker.Mock()
    mocker.patch('glitchygames.input.devices.import_midi_module', return_value=midi_module)
    midi_module.MidiException = pygame.midi.MidiException
    ports = [(b'CoreMIDI', b'Keys', 1, 0, 0), (b'CoreMIDI', b'Synth', 0, 1, 0)]
    midi_module.get_device_info.side_effect = lambda port_id: (
        ports[port_id] if 0 <= port_id < len(ports) else None
    )
    return midi_module


def test_a_midi_port_descriptor_round_trips_through_json():
    """A descriptor survives to_json/from_json unchanged."""
    assert MidiPortDescriptor.from_json(KEYS_DESCRIPTOR.to_json()) == KEYS_DESCRIPTOR
    assert KEYS_DESCRIPTOR.to_json() == {
        'kind': 'midi_input',
        'port_id': 0,
        'name': 'Keys',
        'interface': 'CoreMIDI',
    }


def test_a_midi_port_descriptor_refuses_a_kind_that_is_not_midi():
    """A descriptor of a joystick kind is a mistake the model catches."""
    with pytest.raises(ValueError, match='joystick'):
        MidiPortDescriptor(kind='joystick', port_id=0, name='Keys', interface='CoreMIDI')


def test_opening_an_open_midi_port_hands_back_the_same_port(mocker):
    """A port opens once per process: a second open returns the first, and nothing is recorded."""
    midi_module = _patch_portmidi_ports(mocker)
    registry = LiveDeviceRegistry()
    assert registry.midi_input_for_port(port_id=0) is None
    assert registry.midi_output_for_port(port_id=1) is None

    first_input = registry.open_midi_input(port_id=0)
    second_input = registry.open_midi_input(port_id=0)
    first_output = registry.open_midi_output(port_id=1)
    second_output = registry.open_midi_output(port_id=1)

    assert first_input is second_input is midi_module.Input.return_value
    assert first_output is second_output is midi_module.Output.return_value
    midi_module.Input.assert_called_once_with(0)
    midi_module.Output.assert_called_once_with(1)
    midi_module.init.assert_called_once_with()
    assert registry.midi_input_for_port(port_id=0) is first_input
    assert registry.midi_output_for_port(port_id=1) is first_output
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='open_midi_input', device_index=0, value=0),
        EnumerationAnswer(call='open_midi_output', device_index=1, value=1),
    ]


def test_opened_midi_ports_are_taken_once_by_the_recorder(mocker):
    """The recorder gets each opened port's descriptor once; a frame nobody recorded drops them."""
    _patch_portmidi_ports(mocker)
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_output(port_id=1)

    assert registry.take_opened_midi_ports() == [KEYS_DESCRIPTOR, SYNTH_DESCRIPTOR]
    assert registry.take_opened_midi_ports() == []

    registry.open_midi_input(port_id=0)  # already open: nothing new
    assert registry.take_opened_midi_ports() == []

    other = LiveDeviceRegistry()
    other.open_midi_input(port_id=0)
    other.discard_untaken()
    assert other.take_opened_midi_ports() == []


def test_replay_midi_output_drops_writes(mocker):
    """A replayed output returns None for every write and calls no pygame.midi function."""
    midi_calls = mocker.patch.multiple(
        'pygame.midi', init=mocker.DEFAULT, Output=mocker.DEFAULT, Input=mocker.DEFAULT
    )
    output = ReplayMidiOutput(descriptor=SYNTH_DESCRIPTOR)

    results = [
        output.note_on(60, 100),
        output.note_on(60, 100, 3),
        output.note_off(60),
        output.note_off(60, 64, 3),
        output.write_short(0x90, 60, 100),
        output.write([[[0x90, 60, 100], 0]]),
        output.write_sys_ex(0, b'\xf0\xf7'),
        output.set_instrument(5),
        output.set_instrument(5, 2),
        output.pitch_bend(100),
        output.pitch_bend(100, 2),
        output.close(),
    ]

    assert results == [None] * len(results)
    assert output.descriptor == SYNTH_DESCRIPTOR
    for midi_call in midi_calls.values():
        midi_call.assert_not_called()


def test_replay_midi_input_has_nothing_to_read():
    """A replayed input never has anything waiting."""
    midi_input = ReplayMidiInput(descriptor=KEYS_DESCRIPTOR)

    assert midi_input.poll() is False
    assert midi_input.read(10) == []
    assert midi_input.close() is None
    assert midi_input.descriptor == KEYS_DESCRIPTOR


def test_a_replay_opens_the_recorded_ports_once_and_never_the_hardware(mocker):
    """The replay hands out stand-ins for the recorded ports, one per port and direction."""
    midi_module = _patch_portmidi_ports(mocker)
    live = LiveDeviceRegistry()
    live.open_midi_input(port_id=0)
    live.open_midi_output(port_id=1)
    recorded_ports = live.take_opened_midi_ports()
    recorded_answers = [
        EnumerationAnswer.from_json(answer.to_json()) for answer in live.take_enumeration_answers()
    ]
    midi_module.reset_mock()

    replay = ReplayDeviceRegistry(
        descriptors=[], enumeration_answers=recorded_answers, midi_ports=recorded_ports
    )
    assert replay.midi_input_for_port(port_id=0) is None
    midi_input = replay.open_midi_input(port_id=0)
    midi_output = replay.open_midi_output(port_id=1)

    assert isinstance(midi_input, ReplayMidiInput)
    assert isinstance(midi_output, ReplayMidiOutput)
    assert (midi_input.descriptor, midi_output.descriptor) == (KEYS_DESCRIPTOR, SYNTH_DESCRIPTOR)
    assert replay.open_midi_input(port_id=0) is midi_input
    assert replay.open_midi_output(port_id=1) is midi_output
    assert replay.midi_input_for_port(port_id=0) is midi_input
    assert replay.midi_output_for_port(port_id=1) is midi_output
    assert midi_module.mock_calls == []


def test_a_replay_learns_ports_opened_in_frames_and_hands_them_to_a_recorder_once():
    """Ports a frame opened open in the replay, and a recording made over it writes them once."""
    replay = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])

    replay.add_midi_ports(descriptors=[KEYS_DESCRIPTOR])

    assert replay.open_midi_input(port_id=0).descriptor == KEYS_DESCRIPTOR
    assert replay.take_opened_midi_ports() == [KEYS_DESCRIPTOR]
    assert replay.take_opened_midi_ports() == []


def test_a_replay_names_a_port_the_recording_never_opened(caplog):
    """An open of an unrecorded port gets a named stand-in and one warning (the game diverged)."""
    replay = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])

    midi_output = replay.open_midi_output(port_id=3)

    assert midi_output.descriptor.name == 'Unrecorded MIDI port 3'
    assert midi_output.descriptor.kind == MIDI_OUTPUT_KIND
    assert 'MIDI port 3 is not in the recording' in caplog.text


def test_a_failed_midi_open_is_recorded_and_fails_the_same_in_replay(mocker):
    """The port vanishes before the open: the failure is recorded and the replay fails the same."""
    midi_module = _patch_portmidi_ports(mocker)
    midi_module.Input.side_effect = pygame.midi.MidiException('Device id invalid')
    midi_module.Output.side_effect = pygame.error('Output refused')
    live = LiveDeviceRegistry()

    with pytest.raises(pygame.error, match='Device id invalid'):
        live.open_midi_input(port_id=0)
    with pytest.raises(pygame.error, match='Output refused'):
        live.open_midi_output(port_id=1)

    answers = live.take_enumeration_answers()
    assert answers == [
        EnumerationAnswer(
            call='open_midi_input', device_index=0, value=None, error='Device id invalid'
        ),
        EnumerationAnswer(
            call='open_midi_output', device_index=1, value=None, error='Output refused'
        ),
    ]
    assert live.take_opened_midi_ports() == []
    assert live.midi_input_for_port(port_id=0) is None

    replay = ReplayDeviceRegistry(
        descriptors=[],
        enumeration_answers=[EnumerationAnswer.from_json(answer.to_json()) for answer in answers],
    )
    with pytest.raises(pygame.error, match='Device id invalid'):
        replay.open_midi_input(port_id=0)
    with pytest.raises(pygame.error, match='Output refused'):
        replay.open_midi_output(port_id=1)


@pytest.mark.parametrize(
    ('open_name', 'port_id', 'message'),
    [
        ('open_midi_input', 9, 'There is no MIDI port 9'),
        ('open_midi_input', 1, r'MIDI port 1 \(Synth\) cannot be opened as a midi_input'),
        ('open_midi_output', 0, r'MIDI port 0 \(Keys\) cannot be opened as a midi_output'),
    ],
)
def test_a_midi_open_of_a_missing_or_wrong_way_port_fails_and_is_recorded(
    mocker, open_name, port_id, message
):
    """A port that is not there, or goes the other way, fails before pygame is asked to open it."""
    midi_module = _patch_portmidi_ports(mocker)
    registry = LiveDeviceRegistry()

    with pytest.raises(pygame.error, match=message):
        getattr(registry, open_name)(port_id=port_id)

    midi_module.Input.assert_not_called()
    midi_module.Output.assert_not_called()
    (answer,) = registry.take_enumeration_answers()
    assert answer.call == open_name
    assert answer.value is None
    assert answer.error is not None
    assert registry.take_opened_midi_ports() == []


def test_a_midi_open_without_portmidi_fails_and_is_recorded(mocker):
    """Without PortMidi an open fails as a pygame.error a replay raises again."""
    mocker.patch('glitchygames.input.devices.import_midi_module', return_value=None)
    registry = LiveDeviceRegistry()

    with pytest.raises(pygame.error, match=r'pygame\.midi is unavailable'):
        registry.open_midi_output(port_id=0)

    (answer,) = registry.take_enumeration_answers()
    assert answer.error == 'pygame.midi is unavailable in this pygame build'


def test_a_stand_in_registry_opens_its_midi_ports_and_tells_the_recorder():
    """Stand-in ports open as stand-ins, once, and a recorder takes the descriptors and answers."""
    registry = stand_in_registry(descriptors=[], midi_ports=[KEYS_PORT, SYNTH_PORT])

    midi_input = registry.open_midi_input(port_id=0)
    midi_output = registry.open_midi_output(port_id=1)

    assert registry.open_midi_input(port_id=0) is midi_input
    assert midi_output.descriptor == SYNTH_DESCRIPTOR
    assert registry.take_opened_midi_ports() == [KEYS_DESCRIPTOR, SYNTH_DESCRIPTOR]
    assert registry.take_opened_midi_ports() == []
    assert registry.take_enumeration_answers() == [
        EnumerationAnswer(call='open_midi_input', device_index=0, value=0),
        EnumerationAnswer(call='open_midi_output', device_index=1, value=1),
    ]


def test_stand_in_frames_without_a_recorder_keep_no_midi_ports():
    """The stand-in doors discard untaken MIDI ports at the end of every frame."""
    registry = install_stand_in_devices(descriptors=[], midi_ports=[KEYS_PORT])
    registry.open_midi_input(port_id=0)

    active_sources().end_frame(frame_number=0, dt=0.016, scene=None, control_events=[])

    assert registry.take_opened_midi_ports() == []


def test_find_midi_port_refuses_a_kind_that_is_not_midi():
    """An unknown kind is a mistake, not a search for outputs."""
    registry = stand_in_registry(descriptors=[], midi_ports=[KEYS_PORT, SYNTH_PORT])

    with pytest.raises(ValueError, match=r"'joystick'"):
        find_midi_port(devices=registry, name='Keys', kind='joystick')


def test_without_portmidi_the_unavailable_message_is_logged_once_per_registry(mocker, caplog):
    """A game asking about MIDI every frame does not log the missing module every frame."""
    mocker.patch(
        'glitchygames.input.devices.importlib.import_module',
        side_effect=ModuleNotFoundError("No module named 'pygame.pypm'"),
    )
    registry = LiveDeviceRegistry()

    with caplog.at_level('INFO', logger='game.input.devices'):
        for _ in range(3):
            registry.midi_port_count()
            registry.default_midi_input_id()

    assert caplog.text.count('pygame.midi is unavailable') == 1


def test_a_portmidi_start_failure_during_an_open_is_recorded_once_and_fails_the_same_in_replay(
    mocker,
):
    """PortMidi cannot start: the open raises, one failure is recorded, the replay raises it too."""
    midi_module = _patch_portmidi_ports(mocker)
    midi_module.init.side_effect = pygame.error('PortMidi cannot start')
    live = LiveDeviceRegistry()

    with pytest.raises(pygame.error, match='PortMidi cannot start'):
        live.open_midi_input(port_id=0)

    answers = live.take_enumeration_answers()
    assert answers == [
        EnumerationAnswer(
            call='open_midi_input', device_index=0, value=None, error='PortMidi cannot start'
        )
    ]
    assert live.take_opened_midi_ports() == []
    midi_module.Input.assert_not_called()

    replay = ReplayDeviceRegistry(
        descriptors=[],
        enumeration_answers=[EnumerationAnswer.from_json(answer.to_json()) for answer in answers],
    )
    with pytest.raises(pygame.error, match='PortMidi cannot start'):
        replay.open_midi_input(port_id=0)


TWO_INPUT_PORTS = [(b'CoreMIDI', b'Keys', 1, 0, 0), (b'CoreMIDI', b'Pads', 1, 0, 0)]


class FakePortMidiInput:
    """A PortMidi input as the hardware gives it (seen on a virtual port; pygame-ce 2.5.8).

    It queues up to ``capacity`` messages. One more overflows it: that and all later input is
    refused, ``poll`` is False once the queue is read, and the next ``read`` raises once (losing
    what that read had taken); then the port works again.
    """

    def __init__(
        self,
        *,
        messages=(),
        fails=False,
        fails_after_reads=None,
        capacity=4096,
        overflow_message=b'PortMidi: Buffer overflow',
    ):
        """Queue the messages; every call raises a plain Exception once ``fails``.

        ``fails_after_reads`` makes it fail from the call after that many reads.
        """
        self.messages = []
        self.fails = fails
        self.fails_after_reads = fails_after_reads
        self.capacity = capacity
        self.overflow_message = overflow_message
        self.overflowed = False
        self.read_sizes = []
        self.send(messages)

    def send(self, messages):
        for message in messages:
            if self.overflowed or len(self.messages) >= self.capacity:
                self.overflowed = True
            else:
                self.messages.append(message)

    def _raise_when_failing(self):
        after_reads = self.fails_after_reads
        if self.fails or (after_reads is not None and len(self.read_sizes) >= after_reads):
            # PortMidi's Poll and Read raise a plain Exception (pypm.pyx)
            message = 'Host error'
            raise StandInPortMidiError(message)

    def poll(self):
        self._raise_when_failing()
        return bool(self.messages)

    def read(self, num_events):
        self._raise_when_failing()
        self.read_sizes.append(num_events)
        batch, self.messages = self.messages[:num_events], self.messages[num_events:]
        if self.overflowed and len(batch) < num_events:
            self.overflowed = False
            raise StandInPortMidiError(self.overflow_message)
        return batch


def _patch_portmidi_inputs(mocker, *, inputs_by_port):
    """Stand in for PortMidi with two input ports whose Input objects are the given fakes."""
    midi_module = mocker.Mock()
    mocker.patch('glitchygames.input.devices.import_midi_module', return_value=midi_module)
    midi_module.MidiException = pygame.midi.MidiException
    midi_module.midis2events = pygame.midi.midis2events
    midi_module.get_device_info.side_effect = lambda port_id: (
        TWO_INPUT_PORTS[port_id] if 0 <= port_id < len(TWO_INPUT_PORTS) else None
    )
    midi_module.Input.side_effect = lambda port_id: inputs_by_port[port_id]
    return midi_module


def _timestamps(events):
    return [event.timestamp for event in events]


def test_a_live_burst_larger_than_one_read_is_read_whole_in_port_order(mocker):
    """Every opened input is read until empty, a read asking for MIDI_READ_BATCH at a time."""
    burst = [([0x90, 60, 100, 0], timestamp) for timestamp in range(MIDI_READ_BATCH * 2 + 5)]
    keys = FakePortMidiInput(messages=burst)
    pads = FakePortMidiInput(messages=[([0x99, 36, 90, 0], 7)])
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys, 1: pads})
    registry = LiveDeviceRegistry()
    # Opened out of order: the read is still in port-id order
    registry.open_midi_input(port_id=1)
    registry.open_midi_input(port_id=0)

    events = registry.read_midi_input()

    assert [event.vice_id for event in events] == [0] * len(burst) + [1]
    assert _timestamps(events[: len(burst)]) == list(range(len(burst)))
    # The last read, past the short batch, finds nothing
    assert keys.read_sizes == [MIDI_READ_BATCH] * 4
    assert all(event.type == pygame.MIDIIN for event in events)
    assert registry.read_midi_input() == []


def test_a_live_read_with_no_opened_input_touches_nothing(mocker):
    """A game that opened no input never reads PortMidi."""
    midi_module = _patch_portmidi_inputs(mocker, inputs_by_port={})
    registry = LiveDeviceRegistry()

    assert registry.read_midi_input() == []
    midi_module.Input.assert_not_called()


def test_a_live_port_that_raises_is_dropped_once_and_the_others_still_read(mocker, caplog):
    """A port raising a plain Exception is dropped (logged once, with id and name)."""
    keys = FakePortMidiInput(messages=[([0x90, 60, 100, 0], 1)], fails=True)
    pads = FakePortMidiInput(messages=[([0x99, 36, 90, 0], 2)])
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys, 1: pads})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_input(port_id=1)

    with caplog.at_level('ERROR', logger='game.input.devices'):
        first = registry.read_midi_input()
        pads.messages.append(([0x89, 36, 0, 0], 3))
        second = registry.read_midi_input()

    assert _timestamps(first) == [2]
    assert _timestamps(second) == [3]
    failures = [record for record in caplog.records if 'failed' in record.getMessage()]
    assert len(failures) == 1
    assert 'port 0 (Keys)' in failures[0].getMessage()
    # Dropped, not closed: the port stays the one the registry opened
    assert registry.midi_input_for_port(port_id=0) is keys


def test_only_the_live_and_stand_in_registries_read_midi_input():
    """ReadsMidiInput is what the pump asks for: a replay registry does not have it."""
    assert isinstance(LiveDeviceRegistry(), ReadsMidiInput)
    assert isinstance(stand_in_registry(descriptors=[]), ReadsMidiInput)
    assert not isinstance(
        ReplayDeviceRegistry(descriptors=[], enumeration_answers=[]), ReadsMidiInput
    )


def test_stand_in_midi_input_is_read_only_from_opened_ports_and_only_once():
    """Queued messages of a port nobody opened stay queued; a read takes them once, in order."""
    registry = stand_in_registry(descriptors=[], midi_ports=[KEYS_PORT, KEYS_PORT])
    registry.queue_midi_input(port_id=0, messages=[([0x90, 60, 100, 0], 5), ([0x80, 60, 0, 0], 9)])
    registry.queue_midi_input(port_id=1, messages=[([0x90, 61, 100, 0], 6)])
    registry.open_midi_input(port_id=0)

    events = registry.read_midi_input()

    assert [(event.vice_id, event.status, event.data1, event.timestamp) for event in events] == [
        (0, 0x90, 60, 5),
        (0, 0x80, 60, 9),
    ]
    assert registry.read_midi_input() == []
    # Opened later, the other port's queue is still there
    registry.open_midi_input(port_id=1)
    assert _timestamps(registry.read_midi_input()) == [6]


def test_a_live_port_that_says_waiting_but_reads_nothing_does_not_loop_forever(mocker):
    """A port whose read returns nothing ends the frame's read, whatever its poll says."""
    keys = mocker.Mock(**{'poll.return_value': True, 'read.return_value': []})
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)

    assert registry.read_midi_input() == []
    keys.read.assert_called_once_with(MIDI_READ_BATCH)


def test_a_failing_live_port_is_dropped_even_when_portmidi_cannot_name_it_any_more(mocker, caplog):
    """The port's name is kept from its open: a vanished device's info lookup is never needed."""
    keys = FakePortMidiInput(messages=[([0x90, 60, 100, 0], 1)], fails=True)
    pads = FakePortMidiInput(messages=[([0x99, 36, 90, 0], 2)])
    midi_module = _patch_portmidi_inputs(mocker, inputs_by_port={0: keys, 1: pads})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_input(port_id=1)
    # The device is gone: PortMidi cannot describe it any more
    midi_module.get_device_info.side_effect = pygame.midi.MidiException('Host error')

    with caplog.at_level('ERROR', logger='game.input.devices'):
        events = registry.read_midi_input()

    assert _timestamps(events) == [2]
    failures = [record.getMessage() for record in caplog.records if 'failed' in record.getMessage()]
    assert len(failures) == 1
    assert 'port 0 (Keys)' in failures[0]


def test_what_a_port_gave_before_it_failed_is_delivered_in_that_frame(mocker):
    """A port returning one full batch and then raising: the batch arrives, then it is dropped."""
    burst = [([0x90, 60, 100, 0], timestamp) for timestamp in range(MIDI_READ_BATCH + 10)]
    keys = FakePortMidiInput(messages=burst, fails_after_reads=1)
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)

    first = registry.read_midi_input()
    second = registry.read_midi_input()

    assert _timestamps(first) == list(range(MIDI_READ_BATCH))
    assert second == []
    assert keys.read_sizes == [MIDI_READ_BATCH]


def test_closing_the_midi_ports_closes_each_and_shuts_portmidi_down_once(mocker):
    """Every opened port closes, PortMidi quits, a second close does nothing more."""
    midi_module = _patch_portmidi_ports(mocker)
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_output(port_id=1)

    registry.close_midi_ports()
    registry.close_midi_ports()

    midi_module.Input.return_value.close.assert_called_once_with()
    midi_module.Output.return_value.close.assert_called_once_with()
    midi_module.quit.assert_called_once_with()
    assert registry.midi_input_for_port(port_id=0) is None
    assert registry.midi_output_for_port(port_id=1) is None


def test_closing_the_midi_ports_touches_nothing_when_portmidi_never_started(mocker):
    """No MIDI was asked: closing asks PortMidi nothing and does not start it."""
    midi_module = _patch_portmidi_ports(mocker)
    registry = LiveDeviceRegistry()

    registry.close_midi_ports()

    assert midi_module.mock_calls == []


def test_ports_that_fail_to_close_are_logged_the_rest_close_and_portmidi_quits(mocker, caplog):
    """PortMidi's Close raises a plain Exception: every failure is logged, all ports are tried."""
    midi_module = _patch_portmidi_ports(mocker)
    midi_module.Input.return_value.close.side_effect = StandInPortMidiError('input close failed')
    midi_module.Output.return_value.close.side_effect = StandInPortMidiError('output close failed')
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_output(port_id=1)

    with caplog.at_level('WARNING', logger='game.input.devices'):
        registry.close_midi_ports()

    midi_module.Input.return_value.close.assert_called_once_with()
    midi_module.Output.return_value.close.assert_called_once_with()
    midi_module.quit.assert_called_once_with()
    assert 'input port 0 (Keys)' in caplog.text
    assert 'output port 1' in caplog.text


def test_a_midi_constructor_failure_is_a_remembered_pygame_error_and_replays_the_same(mocker):
    """PortMidi's Input raises a plain Exception with a bytes message: pygame.error, recorded."""
    midi_module = _patch_portmidi_ports(mocker)
    midi_module.Input.side_effect = Exception(b'PortMidi: Device already open')
    midi_module.Output.side_effect = ValueError('no such output')
    live = LiveDeviceRegistry()

    with pytest.raises(pygame.error, match='PortMidi: Device already open'):
        live.open_midi_input(port_id=0)
    with pytest.raises(pygame.error, match='no such output'):
        live.open_midi_output(port_id=1)

    answers = live.take_enumeration_answers()
    failures = [(answer.call, answer.error) for answer in answers if answer.error is not None]
    assert failures == [
        ('open_midi_input', 'PortMidi: Device already open'),
        ('open_midi_output', 'no such output'),
    ]
    assert live.midi_input_for_port(port_id=0) is None
    replay = ReplayDeviceRegistry(
        descriptors=[],
        enumeration_answers=[EnumerationAnswer.from_json(answer.to_json()) for answer in answers],
    )
    with pytest.raises(pygame.error, match='PortMidi: Device already open'):
        replay.open_midi_input(port_id=0)


@pytest.mark.parametrize(
    ('raised', 'message'),
    [
        (pygame.midi.MidiException('Device id invalid'), 'Device id invalid'),
        (Exception(b'bytes \xff message'), 'bytes � message'),
        (Exception(), ''),
        (Exception('text'), 'text'),
    ],
)
def test_a_midi_constructor_failure_message_is_text_whatever_was_raised(mocker, raised, message):
    """MidiException's parameter, bytes, nothing at all and text all become the error's text."""
    midi_module = _patch_portmidi_ports(mocker)
    midi_module.Input.side_effect = raised

    with pytest.raises(pygame.error) as caught:
        LiveDeviceRegistry().open_midi_input(port_id=0)

    assert str(caught.value) == message


class DeviceAnswerListener:
    """Keeps every answer the devices door gives, with what it opened (DeviceAnswerObserver)."""

    def __init__(self):
        """Start with nothing heard."""
        self.heard = []

    def on_device_answer(self, *, answer, opened) -> None:
        """Keep the answer and the opened descriptor."""
        self.heard.append((answer.call, answer.device_index, answer.error, opened))


@pytest.fixture
def device_answers():
    """Listen to the devices door for the test.

    Yields:
        What was heard: (call, port, error, opened), in order.

    """
    listener = DeviceAnswerListener()
    observe_device_answers(observer=listener)
    yield listener.heard
    stop_observing_device_answers(observer=listener)


def _midi_registry(*, kind, mocker):
    """Return a live, stand-in or replay registry with Keys (port 0) and Synth (port 1)."""
    if kind == 'live':
        _patch_portmidi_ports(mocker)
        return LiveDeviceRegistry()
    if kind == 'stand-in':
        return stand_in_registry(descriptors=[], midi_ports=[KEYS_PORT, SYNTH_PORT])
    return ReplayDeviceRegistry(
        descriptors=[],
        enumeration_answers=[],
        midi_ports=[KEYS_DESCRIPTOR, SYNTH_DESCRIPTOR],
    )


@pytest.mark.parametrize('kind', ['live', 'stand-in', 'replay'])
def test_observers_are_told_which_port_an_open_opened_or_handed_back(mocker, device_answers, kind):
    """Every open names its port, a second open of it too: a journal holds each port asked for.

    A port is opened once per registry, so a scene opening one an earlier scene opened is handed
    it back: without the descriptor its journal would not know the port.
    """
    registry = _midi_registry(kind=kind, mocker=mocker)
    midi_input = registry.open_midi_input(port_id=0)
    midi_output = registry.open_midi_output(port_id=1)

    assert registry.open_midi_input(port_id=0) is midi_input
    assert registry.open_midi_output(port_id=1) is midi_output

    opens = [
        ('open_midi_input', 0, None, KEYS_DESCRIPTOR),
        ('open_midi_output', 1, None, SYNTH_DESCRIPTOR),
    ]
    assert device_answers == [*opens, *opens]


@pytest.mark.parametrize('kind', ['live', 'stand-in'])
def test_a_port_handed_back_is_recorded_once(mocker, kind):
    """Only observers hear of the second open: the recorder takes one answer and one port."""
    registry = _midi_registry(kind=kind, mocker=mocker)
    registry.open_midi_input(port_id=0)
    registry.open_midi_input(port_id=0)

    assert [answer.call for answer in registry.take_enumeration_answers()] == ['open_midi_input']
    assert registry.take_opened_midi_ports() == [KEYS_DESCRIPTOR]


def test_an_adopted_midi_port_is_the_one_an_open_hands_back(device_answers):
    """An instant replay's ports: adopting asks no answer; opening one gets the same stand-in."""
    registry = ReplayDeviceRegistry(descriptors=[], enumeration_answers=[])

    midi_input = registry.adopt_midi_port(descriptor=KEYS_DESCRIPTOR)
    midi_output = registry.adopt_midi_port(descriptor=SYNTH_DESCRIPTOR)

    assert isinstance(midi_input, ReplayMidiInput)
    assert isinstance(midi_output, ReplayMidiOutput)
    assert device_answers == []
    assert registry.take_opened_midi_ports() == []
    assert registry.midi_input_for_port(port_id=0) is midi_input
    assert registry.midi_output_for_port(port_id=1) is midi_output
    assert registry.open_midi_input(port_id=0) is midi_input
    assert registry.open_midi_output(port_id=1) is midi_output
    # Kept apart by direction: port 0 was adopted as an input only
    assert registry.midi_output_for_port(port_id=0) is None


def test_a_defect_in_our_conversion_surfaces_and_drops_no_port(mocker):
    """Only the port's own read is contained: a bug of ours is not a failing port."""
    keys = FakePortMidiInput(messages=[([0x90, 60, 100, 0], 1)])
    midi_module = _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    midi_module.midis2events = mocker.Mock(side_effect=TypeError('our defect'))

    with pytest.raises(TypeError, match='our defect'):
        registry.read_midi_input()

    midi_module.midis2events = pygame.midi.midis2events
    keys.messages.append(([0x80, 60, 0, 0], 2))
    assert _timestamps(registry.read_midi_input()) == [2]


# What PortMidi's read raises when its buffer overflowed (pygame-ce 2.5.8, seen on a virtual port):
# bytes today, and pygame-ce plans text
OVERFLOW_MESSAGES = [b'PortMidi: Buffer overflow', 'PortMidi: Buffer overflow']


def _overflow_warnings(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == 'game.input.devices' and 'lost' in record.getMessage()
    ]


def _numbered(*, count, first=0):
    """Return that many messages, each with its number as its timestamp."""
    return [([0x90, 60, 100, 0], number) for number in range(first, first + count)]


@pytest.mark.parametrize('message', OVERFLOW_MESSAGES, ids=['bytes', 'text'])
def test_an_overflowed_port_is_told_from_the_read_and_read_on(mocker, caplog, message):
    """Full, then refused: everything queued arrives, the loss is logged, later input arrives.

    Once the queue is read, poll is False for good: only a read raises the overflow and frees it.
    """
    keys = FakePortMidiInput(
        messages=_numbered(count=MIDI_READ_BATCH + 1),
        capacity=MIDI_READ_BATCH,
        overflow_message=message,
    )
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    assert keys.poll() is True

    with caplog.at_level('WARNING', logger='game.input.devices'):
        assert _timestamps(registry.read_midi_input()) == list(range(MIDI_READ_BATCH))
        keys.send(_numbered(count=1, first=500))
        assert _timestamps(registry.read_midi_input()) == [500]

    (warning,) = _overflow_warnings(caplog)
    assert 'port 0 (Keys)' in warning
    assert [record.levelname for record in caplog.records] == ['WARNING']


def test_what_arrives_after_the_overflow_is_read_in_the_same_frame(mocker):
    """Reading goes on after the overflow is met."""
    keys = FakePortMidiInput(messages=_numbered(count=MIDI_READ_BATCH), capacity=MIDI_READ_BATCH)
    real_read = keys.read

    def read(num_events):
        if not keys.messages and not keys.overflowed and len(keys.read_sizes) == 1:
            # More arrives as the queue is read: full again, and refused
            keys.send(_numbered(count=MIDI_READ_BATCH + 1, first=100))
        try:
            return real_read(num_events)
        except StandInPortMidiError:
            keys.send(_numbered(count=2, first=500))
            raise

    keys.read = read
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)

    assert _timestamps(registry.read_midi_input()) == [
        *range(MIDI_READ_BATCH),
        *range(100, 100 + MIDI_READ_BATCH),
        500,
        501,
    ]


class FloodingPort(FakePortMidiInput):
    """A port that fills again at every read: it never has nothing to give."""

    def __init__(self, *, overflows):
        """Flood with messages, or, when ``overflows``, with nothing but overflows."""
        super().__init__()
        self.overflows = overflows
        self.sent = 0

    def read(self, num_events):
        self.read_sizes.append(num_events)
        if self.overflows:
            raise StandInPortMidiError(OVERFLOW_MESSAGES[0])
        self.sent += num_events
        return _numbered(count=num_events, first=self.sent - num_events)


def test_a_flood_is_capped_per_port_per_frame_and_goes_on_in_order(mocker):
    """A port that never runs dry cannot hold the frame, nor keep the other ports waiting."""
    keys = FloodingPort(overflows=False)
    pads = FakePortMidiInput(messages=[([0x99, 36, 90, 0], 2)])
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys, 1: pads})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_input(port_id=1)

    cap = MIDI_MESSAGES_PER_PORT_PER_FRAME
    assert _timestamps(registry.read_midi_input()) == [*range(cap), 2]
    assert _timestamps(registry.read_midi_input()) == list(range(cap, 2 * cap))


def test_a_queue_longer_than_the_cap_arrives_whole_over_frames(mocker):
    """What the cap leaves waits for the next frame, in order."""
    cap = MIDI_MESSAGES_PER_PORT_PER_FRAME
    keys = FakePortMidiInput(messages=_numbered(count=cap + 3), capacity=2 * cap)
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)

    assert len(registry.read_midi_input()) == cap
    assert _timestamps(registry.read_midi_input()) == [cap, cap + 1, cap + 2]


def test_the_cap_takes_a_whole_portmidi_buffer_and_its_overflow_in_one_frame():
    """PortMidi queues 4096 (pygame's default): the overflow is met as the queue is read."""
    assert MIDI_MESSAGES_PER_PORT_PER_FRAME > 4096
    # A read cut short by the overflow loses what it had taken: a full queue divides into batches
    assert 4096 % MIDI_READ_BATCH == 0
    assert MIDI_MESSAGES_PER_PORT_PER_FRAME % MIDI_READ_BATCH == 0


def test_a_port_that_only_overflows_does_not_hold_the_frame(mocker, caplog):
    """Two overflows end the port's read for this frame: it is not dropped, and is read again."""
    keys = FloodingPort(overflows=True)
    pads = FakePortMidiInput(messages=[([0x99, 36, 90, 0], 2)])
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys, 1: pads})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_input(port_id=1)

    with caplog.at_level('WARNING', logger='game.input.devices'):
        assert _timestamps(registry.read_midi_input()) == [2]
        keys.overflows = False
        assert len(registry.read_midi_input()) == MIDI_MESSAGES_PER_PORT_PER_FRAME

    assert len(_overflow_warnings(caplog)) == 1


def test_a_burst_of_overflows_is_logged_once_and_the_next_burst_again(mocker, caplog):
    """Per port; a burst ends after MIDI_OVERFLOW_QUIET_READS reads without an overflow."""
    keys = FakePortMidiInput(capacity=MIDI_READ_BATCH)
    pads = FakePortMidiInput(capacity=MIDI_READ_BATCH)
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys, 1: pads})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)
    registry.open_midi_input(port_id=1)

    def read_frames(*, frames, overflowing):
        for _ in range(frames):
            for port in overflowing:
                port.send(_numbered(count=MIDI_READ_BATCH + 1))
            registry.read_midi_input()

    with caplog.at_level('WARNING', logger='game.input.devices'):
        read_frames(frames=3, overflowing=[keys])
        # Quiet for one read less than it takes: the same burst
        read_frames(frames=MIDI_OVERFLOW_QUIET_READS - 1, overflowing=[])
        read_frames(frames=1, overflowing=[keys])
        assert len(_overflow_warnings(caplog)) == 1
        # Another port's burst is its own
        read_frames(frames=1, overflowing=[pads])
        assert len(_overflow_warnings(caplog)) == 2
        read_frames(frames=MIDI_OVERFLOW_QUIET_READS, overflowing=[])
        read_frames(frames=2, overflowing=[keys])
        assert len(_overflow_warnings(caplog)) == 3


@pytest.mark.parametrize('message', [b'PortMidi: Host error', 'PortMidi: Host error'])
def test_any_other_failure_still_drops_the_port(mocker, caplog, message):
    """A port failing otherwise is a device that went away: dropped, as before."""
    keys = FakePortMidiInput(
        messages=_numbered(count=MIDI_READ_BATCH + 1),
        capacity=MIDI_READ_BATCH,
        overflow_message=message,
    )
    _patch_portmidi_inputs(mocker, inputs_by_port={0: keys})
    registry = LiveDeviceRegistry()
    registry.open_midi_input(port_id=0)

    with caplog.at_level('WARNING', logger='game.input.devices'):
        assert len(registry.read_midi_input()) == MIDI_READ_BATCH
        keys.send(_numbered(count=1))
        assert registry.read_midi_input() == []

    assert [record.levelname for record in caplog.records] == ['ERROR']


def test_the_stand_in_port_overflows_as_portmidi_does(caplog):
    """Full at 4096: more is refused, what was queued arrives, a read raises once, then it works."""
    registry = stand_in_registry(descriptors=[], midi_ports=[KEYS_PORT])
    midi_input = registry.open_midi_input(port_id=0)
    registry.queue_midi_input(port_id=0, messages=_numbered(count=STAND_IN_MIDI_QUEUE_CAPACITY + 1))
    registry.queue_midi_input(port_id=0, messages=_numbered(count=1, first=9000))
    with caplog.at_level('WARNING', logger='game.input.devices'):
        assert _timestamps(registry.read_midi_input()) == list(range(STAND_IN_MIDI_QUEUE_CAPACITY))
        registry.queue_midi_input(port_id=0, messages=_numbered(count=1, first=9001))
        assert _timestamps(registry.read_midi_input()) == [9001]
    assert len(_overflow_warnings(caplog)) == 1

    # Read part way, the overflow not met: still refused
    registry.queue_midi_input(port_id=0, messages=_numbered(count=STAND_IN_MIDI_QUEUE_CAPACITY + 1))
    assert len(midi_input.read(10)) == 10
    registry.queue_midi_input(port_id=0, messages=_numbered(count=1, first=9002))
    rest = STAND_IN_MIDI_QUEUE_CAPACITY - 10
    assert len(midi_input.read(rest)) == rest
    assert midi_input.poll() is False
    with pytest.raises(StandInPortMidiError):
        midi_input.read(1)

    # Read by hand: poll says nothing waits, the read raises once and loses what it had taken
    registry.queue_midi_input(port_id=0, messages=_numbered(count=STAND_IN_MIDI_QUEUE_CAPACITY + 1))
    assert len(midi_input.read(STAND_IN_MIDI_QUEUE_CAPACITY)) == STAND_IN_MIDI_QUEUE_CAPACITY
    assert midi_input.poll() is False
    with pytest.raises(StandInPortMidiError) as overflow:
        midi_input.read(1)
    assert overflow.value.args == (OVERFLOW_MESSAGES[0],)
    assert midi_input.read(1) == []
    registry.queue_midi_input(port_id=0, messages=_numbered(count=STAND_IN_MIDI_QUEUE_CAPACITY + 1))
    with pytest.raises(StandInPortMidiError):
        midi_input.read(STAND_IN_MIDI_QUEUE_CAPACITY + 1)
    assert midi_input.read(1) == []


@pytest.mark.parametrize(
    ('interface', 'name'),
    [(b'CoreMIDI', b'Keys'), ('CoreMIDI', 'Keys'), (b'CoreMIDI', 'Keys')],
    ids=['bytes', 'text', 'mixed'],
)
def test_port_names_are_read_as_bytes_or_text(mocker, interface, name):
    """pygame-ce gives bytes (2.5.8) and plans text: the door answers text either way."""
    midi_module = _patch_portmidi_ports(mocker)
    midi_module.get_device_info.side_effect = lambda port_id: (interface, name, 1, 0, 0)
    registry = LiveDeviceRegistry()

    assert registry.midi_port_info(port_id=0) == KEYS_PORT
    registry.open_midi_input(port_id=0)
    assert registry.take_opened_midi_ports() == [KEYS_DESCRIPTOR]
