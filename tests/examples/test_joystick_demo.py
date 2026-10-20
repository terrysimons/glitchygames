"""Tests for the joystick demo's device sites (through the devices door and the snapshot)."""

from __future__ import annotations

from glitchygames.examples.joystick_demo import JoystickScene, TextSprite
from glitchygames.input.devices import (
    IS_CONTROLLER_CALL,
    NAME_FOR_INDEX_CALL,
    DeviceDescriptor,
    EnumerationAnswer,
    ReplayDeviceRegistry,
)
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.sources import active_sources


def _descriptor(*, kind: str) -> DeviceDescriptor:
    """Return a recorded device at device index 0, instance id 4.

    Returns:
        The descriptor.

    """
    return DeviceDescriptor(
        kind=kind,
        device_index=0,
        instance_id=4,
        name='Pad',
        guid=None,
        axis_count=2,
        button_count=1,
        hat_count=1,
        ball_count=0,
    )


def _set_snapshot(**device_fields) -> None:
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


def _printed_lines(*, mocker, render) -> list[str]:
    """Run ``render`` on a text sprite whose text box records what it prints.

    Returns:
        The printed lines, in order.

    """
    text_sprite = TextSprite.__new__(TextSprite)
    text_sprite.image = mocker.Mock()
    text_sprite.text_box = mocker.Mock()
    render(text_sprite)
    return [call.args[1] for call in text_sprite.text_box.print.call_args_list]


def test_joystick_readout_comes_from_the_snapshot(mocker):
    """The joystick panel prints the frame's snapshot, by instance id."""
    _set_snapshot(
        device_axes={4: (0.5, -1.0)}, device_buttons={4: (True,)}, device_hats={4: ((1, 0),)}
    )
    # A device whose own reads disagree with the snapshot: only the snapshot may be read
    joystick = mocker.Mock()
    joystick.get_instance_id.return_value = 4
    joystick.get_numaxes.return_value = 2
    joystick.get_numbuttons.return_value = 1
    joystick.get_numhats.return_value = 1
    joystick.get_axis.return_value = 0.25
    joystick.get_button.return_value = False
    joystick.get_hat.return_value = (0, 0)

    lines = _printed_lines(
        mocker=mocker,
        render=lambda text_sprite: text_sprite._render_joystick_inputs(joystick),
    )

    assert 'Axis 0 value:  0.500' in lines
    assert 'Axis 1 value: -1.000' in lines
    assert 'Button  0 value: True' in lines
    assert 'Hat 0 value: (1, 0)' in lines
    joystick.get_axis.assert_not_called()
    joystick.get_button.assert_not_called()
    joystick.get_hat.assert_not_called()


def test_controller_readout_comes_from_the_snapshot_controller_layer(mocker):
    """The controller panel prints the snapshot's controller layer, by instance id."""
    _set_snapshot(
        controller_axes={4: (100, -200, 0, 0, 32767, 0)},
        controller_buttons={4: (True,) + (False,) * 14},
    )
    # A controller whose own reads disagree with the snapshot: only the snapshot may be read
    controller = mocker.Mock()
    controller.as_joystick.return_value.get_instance_id.return_value = 4
    controller.get_axis.return_value = 7
    controller.get_button.return_value = False
    proxy = mocker.Mock(AXIS=list(range(6)), BUTTONS=list(range(15)))

    lines = _printed_lines(
        mocker=mocker,
        render=lambda text_sprite: text_sprite._render_controller_inputs(proxy, controller),
    )

    assert 'Axis 0 value: 100.000' in lines
    assert 'Axis 4 value: 32767.000' in lines
    assert 'Button  0 value: True' in lines
    assert 'Button  1 value: False' in lines
    controller.get_axis.assert_not_called()
    controller.get_button.assert_not_called()


def test_controller_validation_survives_pygame_without_a_name_lookup(mocker):
    """A controller with no name to look up is still valid (BUGS.md #66)."""
    registry = ReplayDeviceRegistry(
        descriptors=[_descriptor(kind='controller')],
        enumeration_answers=[
            EnumerationAnswer(call=IS_CONTROLLER_CALL, device_index=0, value=True),
            EnumerationAnswer(call=NAME_FOR_INDEX_CALL, device_index=0, value=None),
        ],
    )
    mocker.patch.object(active_sources(), 'devices', return_value=registry)
    real_is_controller = mocker.patch('pygame._sdl2.controller.is_controller')
    scene = JoystickScene.__new__(JoystickScene)

    assert scene._is_controller_still_valid(0) is True
    real_is_controller.assert_not_called()


def test_controller_validation_fails_for_a_recorded_failure(mocker):
    """A recorded enumeration failure makes the controller invalid, as it did live."""
    registry = ReplayDeviceRegistry(
        descriptors=[_descriptor(kind='controller')],
        enumeration_answers=[
            EnumerationAnswer(
                call=IS_CONTROLLER_CALL, device_index=0, value=None, error='device gone'
            ),
        ],
    )
    mocker.patch.object(active_sources(), 'devices', return_value=registry)
    scene = JoystickScene.__new__(JoystickScene)

    assert scene._is_controller_still_valid(0) is False


def test_joystick_device_index_lookup_opens_each_joystick_once_per_frame(mocker):
    """Looking up several joysticks in one frame counts and opens each joystick once."""
    registry = mocker.Mock()
    registry.joystick_count.return_value = 2
    registry.open_joystick.side_effect = lambda device_index: mocker.Mock(**{
        'get_instance_id.return_value': 10 + device_index
    })
    mocker.patch.object(active_sources(), 'devices', return_value=registry)
    text_sprite = TextSprite.__new__(TextSprite)
    text_sprite.forget_joystick_indexes()

    def tracked(instance_id: int):
        return mocker.Mock(**{'get_instance_id.return_value': instance_id})

    assert text_sprite._find_joystick_device_id(tracked(11)) == 1
    assert text_sprite._find_joystick_device_id(tracked(10)) == 0
    assert text_sprite._find_joystick_device_id(tracked(99)) is None
    assert registry.joystick_count.call_count == 1
    assert registry.open_joystick.call_count == 2

    # The next frame looks again
    text_sprite.forget_joystick_indexes()
    assert text_sprite._find_joystick_device_id(tracked(11)) == 1
    assert registry.open_joystick.call_count == 4
