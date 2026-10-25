"""Tests for Drawing Fire's player input."""

from __future__ import annotations

import math

import pygame

from glitchygames.examples.drawing_fire.battle import Intent
from glitchygames.examples.drawing_fire.players import (
    KEYBOARD,
    Button,
    ButtonEdges,
    Device,
    connected_devices,
    device_intent,
)
from glitchygames.input.state import InputSnapshot

CONTROLLER_ID = 7
AXIS_COUNT = 6
BUTTON_COUNT = 21
FULL_DEFLECTION = 32767
MOST_NEGATIVE = -32768
SOLDIER_POSITION = (400.0, 300.0)
CONTROLLER = Device(controller_id=CONTROLLER_ID)


def controller_snapshot(*, axes: dict[int, int] | None = None, buttons: set[int] | None = None):
    """Build a snapshot with one controller (id 7) holding the given axes and buttons.

    Returns:
        The snapshot.

    """
    axis_values = [0] * AXIS_COUNT
    for axis, value in (axes or {}).items():
        axis_values[axis] = value
    button_values = [index in (buttons or set()) for index in range(BUTTON_COUNT)]
    return InputSnapshot(
        pressed_scancodes=frozenset(),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
        controller_axes={CONTROLLER_ID: tuple(axis_values)},
        controller_buttons={CONTROLLER_ID: tuple(button_values)},
    )


def keyboard_snapshot(
    *,
    scancodes: set[int] | None = None,
    mouse_position: tuple[int, int] = (0, 0),
    mouse_buttons: tuple[bool, bool, bool] = (False, False, False),
):
    """Build a snapshot with the keyboard and mouse only.

    Returns:
        The snapshot.

    """
    return InputSnapshot(
        pressed_scancodes=frozenset(scancodes or ()),
        modifiers=0,
        mouse_position=mouse_position,
        mouse_buttons=mouse_buttons,
        mouse_focused=True,
    )


def controller_intent(snapshot, last_aim=0.0):
    """Return the intent of controller 7.

    Returns:
        The intent.

    """
    return device_intent(
        device=CONTROLLER, snapshot=snapshot, soldier_position=SOLDIER_POSITION, last_aim=last_aim
    )


def keyboard_intent(snapshot):
    """Return the keyboard's intent.

    Returns:
        The intent.

    """
    return device_intent(
        device=KEYBOARD, snapshot=snapshot, soldier_position=SOLDIER_POSITION, last_aim=0.0
    )


def test_dual_stick_moves_and_aims():
    """Dual stick moves and aims."""
    snapshot = controller_snapshot(
        axes={
            pygame.CONTROLLER_AXIS_LEFTX: FULL_DEFLECTION,
            pygame.CONTROLLER_AXIS_RIGHTX: 0,
            pygame.CONTROLLER_AXIS_RIGHTY: -FULL_DEFLECTION,
        }
    )

    intent = controller_intent(snapshot)

    assert intent.move == 1.0
    assert math.isclose(intent.aim_angle, math.pi / 2)
    assert not intent.fire


def test_the_most_negative_axis_value_clamps_to_minus_one():
    """The most negative axis value clamps to minus one."""
    snapshot = controller_snapshot(axes={pygame.CONTROLLER_AXIS_LEFTX: MOST_NEGATIVE})

    assert controller_intent(snapshot).move == -1.0


def test_a_resting_move_stick_does_not_move():
    """A resting move stick does not move."""
    snapshot = controller_snapshot(axes={pygame.CONTROLLER_AXIS_LEFTX: 3000})

    assert controller_intent(snapshot).move == 0.0


def test_a_resting_aim_stick_keeps_the_last_aim():
    """A resting aim stick keeps the last aim."""
    snapshot = controller_snapshot(
        axes={pygame.CONTROLLER_AXIS_RIGHTX: 3000, pygame.CONTROLLER_AXIS_RIGHTY: 3000}
    )

    assert controller_intent(snapshot, last_aim=1.25).aim_angle == 1.25


def test_the_trigger_fires():
    """The trigger fires."""
    snapshot = controller_snapshot(axes={pygame.CONTROLLER_AXIS_TRIGGERRIGHT: FULL_DEFLECTION})

    assert controller_intent(snapshot).fire


def test_a_light_trigger_pull_does_not_fire():
    """A light trigger pull does not fire."""
    snapshot = controller_snapshot(axes={pygame.CONTROLLER_AXIS_TRIGGERRIGHT: 10000})

    assert not controller_intent(snapshot).fire


def test_the_right_shoulder_fires():
    """The right shoulder fires."""
    snapshot = controller_snapshot(buttons={pygame.CONTROLLER_BUTTON_RIGHTSHOULDER})

    assert controller_intent(snapshot).fire


def test_an_unknown_controller_is_idle():
    """An unknown controller is idle."""
    snapshot = keyboard_snapshot()

    assert controller_intent(snapshot, last_aim=0.5) == Intent(move=0.0, aim_angle=0.5, fire=False)


def test_the_keyboard_aims_at_the_mouse():
    """The keyboard aims at the mouse."""
    snapshot = keyboard_snapshot(mouse_position=(300, 200))

    assert math.pi / 2 < keyboard_intent(snapshot).aim_angle < math.pi


def test_the_keyboard_aims_right_at_a_mouse_on_the_soldier_row():
    """The keyboard aims right at a mouse on the soldier row."""
    snapshot = keyboard_snapshot(mouse_position=(500, 300))

    assert math.isclose(keyboard_intent(snapshot).aim_angle, 0.0)


def test_the_keyboard_moves_with_a_d_and_the_arrows():
    """The keyboard moves with a d and the arrows."""
    left = keyboard_intent(keyboard_snapshot(scancodes={pygame.KSCAN_A}))
    left_arrow = keyboard_intent(keyboard_snapshot(scancodes={pygame.KSCAN_LEFT}))
    right = keyboard_intent(keyboard_snapshot(scancodes={pygame.KSCAN_D}))
    right_arrow = keyboard_intent(keyboard_snapshot(scancodes={pygame.KSCAN_RIGHT}))

    assert (left.move, left_arrow.move) == (-1.0, -1.0)
    assert (right.move, right_arrow.move) == (1.0, 1.0)


def test_holding_both_keyboard_directions_does_not_move():
    """Holding both keyboard directions does not move."""
    snapshot = keyboard_snapshot(scancodes={pygame.KSCAN_A, pygame.KSCAN_D})

    assert keyboard_intent(snapshot).move == 0.0


def test_the_left_mouse_button_fires():
    """The left mouse button fires."""
    snapshot = keyboard_snapshot(mouse_buttons=(True, False, False))

    assert keyboard_intent(snapshot).fire


def test_start_is_pressed_once_per_press():
    """Start is pressed once per press."""
    edges = ButtonEdges()
    held = controller_snapshot(buttons={pygame.CONTROLLER_BUTTON_START})

    edges.update(held)
    first_frame = edges.pressed(CONTROLLER, Button.START)
    edges.update(held)
    second_frame = edges.pressed(CONTROLLER, Button.START)

    assert first_frame
    assert not second_frame


def test_held_frames_count_up_and_reset_on_release():
    """Held frames count up and reset on release."""
    edges = ButtonEdges()
    held = controller_snapshot(buttons={pygame.CONTROLLER_BUTTON_BACK})
    released = controller_snapshot()

    edges.update(held)
    edges.update(held)
    edges.update(held)
    counted = edges.held_frames(CONTROLLER, Button.BACK)
    edges.update(released)

    assert counted == 3
    assert edges.held_frames(CONTROLLER, Button.BACK) == 0
    assert not edges.pressed(CONTROLLER, Button.BACK)


def test_a_vanished_device_reads_as_all_buttons_up():
    """A vanished device reads as all buttons up."""
    edges = ButtonEdges()
    edges.update(controller_snapshot(buttons={pygame.CONTROLLER_BUTTON_START}))

    edges.update(keyboard_snapshot())

    assert edges.held_frames(CONTROLLER, Button.START) == 0
    assert not edges.pressed(CONTROLLER, Button.START)


def test_a_device_never_seen_has_no_buttons_down():
    """A device never seen has no buttons down."""
    edges = ButtonEdges()

    assert edges.held_frames(CONTROLLER, Button.LEFT) == 0
    assert not edges.pressed(CONTROLLER, Button.LEFT)


def test_the_dpad_and_the_left_stick_press_left_and_right():
    """The dpad and the left stick press left and right."""
    edges = ButtonEdges()

    edges.update(controller_snapshot(buttons={pygame.CONTROLLER_BUTTON_DPAD_LEFT}))
    dpad_left = edges.pressed(CONTROLLER, Button.LEFT)
    edges.update(controller_snapshot(buttons={pygame.CONTROLLER_BUTTON_DPAD_RIGHT}))
    dpad_right = edges.pressed(CONTROLLER, Button.RIGHT)
    edges.update(controller_snapshot())
    edges.update(controller_snapshot(axes={pygame.CONTROLLER_AXIS_LEFTX: MOST_NEGATIVE}))
    stick_left = edges.pressed(CONTROLLER, Button.LEFT)
    edges.update(controller_snapshot(axes={pygame.CONTROLLER_AXIS_LEFTX: FULL_DEFLECTION}))
    stick_right = edges.pressed(CONTROLLER, Button.RIGHT)

    assert (dpad_left, dpad_right, stick_left, stick_right) == (True, True, True, True)


def test_the_keyboard_buttons():
    """The keyboard buttons."""
    edges = ButtonEdges()

    edges.update(keyboard_snapshot(scancodes={pygame.KSCAN_RETURN, pygame.KSCAN_ESCAPE}))
    return_start = edges.pressed(KEYBOARD, Button.START)
    escape_back = edges.pressed(KEYBOARD, Button.BACK)
    edges.update(keyboard_snapshot(scancodes={pygame.KSCAN_A}))
    a_left = edges.pressed(KEYBOARD, Button.LEFT)
    edges.update(keyboard_snapshot(scancodes={pygame.KSCAN_RIGHT}))
    arrow_right = edges.pressed(KEYBOARD, Button.RIGHT)

    assert return_start
    assert escape_back
    assert a_left
    assert arrow_right


def test_keypad_enter_alone_presses_start():
    """Keypad enter alone presses start."""
    edges = ButtonEdges()

    edges.update(keyboard_snapshot(scancodes={pygame.KSCAN_KP_ENTER}))

    assert edges.pressed(KEYBOARD, Button.START)


def test_connected_devices_list_the_keyboard_and_each_controller():
    """Connected devices list the keyboard and each controller."""
    snapshot = InputSnapshot(
        pressed_scancodes=frozenset(),
        modifiers=0,
        mouse_position=(0, 0),
        mouse_buttons=(False, False, False),
        mouse_focused=True,
        controller_axes={9: (0,) * AXIS_COUNT, 3: (0,) * AXIS_COUNT},
    )

    assert connected_devices(snapshot) == (
        KEYBOARD,
        Device(controller_id=3),
        Device(controller_id=9),
    )
