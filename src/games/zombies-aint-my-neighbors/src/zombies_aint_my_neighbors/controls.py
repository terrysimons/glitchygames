"""Which way each player is pushing, and whether they are firing, from the frame's polled input.

Every player reads only their own device (master plan, decision 5):

* the keyboard: WASD or the arrows, by scancode (the same place on every keyboard layout);
* a pad: its d-pad, else its left stick past the deadzone. A pad with a controller layer is read
  there (it appears in the snapshot's ``controller_axes``); otherwise, as in joystick mode, which
  scripted sessions force, it is read on the joystick layer: axes 0 and 1, hat 0, and the d-pad
  buttons by the controller layer's numbers (the engine's convention, gamepad_choice.py).

Firing (feature plan 6) is held, not pressed: J (under a WASD hand) or Right Shift (under an
arrows hand) on the keyboard, by scancode; A on a pad's controller layer, or button 0, A's
number, on its joystick layer. None of the keys the shared screens, the title, the AI console
or the overlay use (Space, Esc, Enter, P, Q, backtick, F3, F4: ``roster_scene.py``).

A direction is ``(x, y)`` with ``y`` positive downwards, never longer than 1, so diagonals are no
faster. The engine has no polled deadzone helper; the default is ``ActionMap``'s.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

import pygame

from glitchygames.input.action_map import DEFAULT_DEADZONE as ENGINE_DEFAULT_DEADZONE
from zombies_aint_my_neighbors.roster import DeviceKind

if TYPE_CHECKING:
    from glitchygames.input.state import InputSnapshot
    from zombies_aint_my_neighbors.roster import DeviceIdentity

type Direction = tuple[float, float]

DEFAULT_DEADZONE: Final = ENGINE_DEFAULT_DEADZONE
STANDING: Final[Direction] = (0.0, 0.0)
# The controller layer's axis range (pygame's Controller.get_axis)
CONTROLLER_AXIS_MAXIMUM: Final = 32767
# The joystick layer's stick axes and d-pad hat
JOYSTICK_STICK_X_AXIS: Final = 0
JOYSTICK_STICK_Y_AXIS: Final = 1
JOYSTICK_DPAD_HAT: Final = 0

# The keys for each way, by scancode: WASD and the arrows
_KEYS_UP: Final = frozenset({pygame.KSCAN_W, pygame.KSCAN_UP})
_KEYS_DOWN: Final = frozenset({pygame.KSCAN_S, pygame.KSCAN_DOWN})
_KEYS_LEFT: Final = frozenset({pygame.KSCAN_A, pygame.KSCAN_LEFT})
_KEYS_RIGHT: Final = frozenset({pygame.KSCAN_D, pygame.KSCAN_RIGHT})
# The keys that fire, by scancode
FIRE_SCANCODES: Final = frozenset({pygame.KSCAN_J, pygame.KSCAN_RSHIFT})
# A pad's fire button: A on the controller layer, the same number on the joystick layer
FIRE_BUTTON: Final = pygame.CONTROLLER_BUTTON_A


def limited(*, x: float, y: float) -> Direction:
    """Return a direction no longer than 1 (a longer one keeps its angle).

    Returns:
        The direction.

    """
    length = math.hypot(x, y)
    if length > 1:
        return (x / length, y / length)
    return (float(x), float(y))


def _held_axis(*, negative: bool, positive: bool) -> float:
    """Return -1, 0 or 1 from two opposite held controls (both held cancel).

    Returns:
        The axis value.

    """
    return float(positive) - float(negative)


def keyboard_direction(*, snapshot: InputSnapshot) -> Direction:
    """Return the keyboard player's direction: WASD or the arrows.

    Returns:
        The direction.

    """
    held = snapshot.pressed_scancodes
    return limited(
        x=_held_axis(negative=bool(held & _KEYS_LEFT), positive=bool(held & _KEYS_RIGHT)),
        y=_held_axis(negative=bool(held & _KEYS_UP), positive=bool(held & _KEYS_DOWN)),
    )


def _past_deadzone(*, x: float, y: float, deadzone: float) -> Direction:
    """Return a stick's direction, or standing when it is inside the deadzone.

    Returns:
        The direction.

    """
    if math.hypot(x, y) < deadzone:
        return STANDING
    return limited(x=x, y=y)


def _controller_direction(
    *, snapshot: InputSnapshot, instance_id: int, deadzone: float
) -> Direction:
    """Return a pad's direction on its controller layer: the d-pad, else the left stick.

    Returns:
        The direction.

    """

    def pressed(button: int) -> bool:
        return snapshot.controller_button(device_id=instance_id, button=button)

    dpad = (
        _held_axis(
            negative=pressed(pygame.CONTROLLER_BUTTON_DPAD_LEFT),
            positive=pressed(pygame.CONTROLLER_BUTTON_DPAD_RIGHT),
        ),
        _held_axis(
            negative=pressed(pygame.CONTROLLER_BUTTON_DPAD_UP),
            positive=pressed(pygame.CONTROLLER_BUTTON_DPAD_DOWN),
        ),
    )
    if dpad != STANDING:
        return limited(x=dpad[0], y=dpad[1])
    stick_x, stick_y = (
        max(
            -1.0,
            snapshot.controller_axis(device_id=instance_id, axis=axis) / CONTROLLER_AXIS_MAXIMUM,
        )
        for axis in (pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY)
    )
    return _past_deadzone(x=stick_x, y=stick_y, deadzone=deadzone)


def _joystick_direction(*, snapshot: InputSnapshot, instance_id: int, deadzone: float) -> Direction:
    """Return a pad's direction on its joystick layer: the hat or d-pad buttons, else the stick.

    Returns:
        The direction.

    """
    hat_x, hat_y = snapshot.hat(device_id=instance_id, hat=JOYSTICK_DPAD_HAT)
    if (hat_x, hat_y) != (0, 0):
        # A hat's up is +1; the screen's up is -1
        return limited(x=hat_x, y=-hat_y)

    def pressed(button: int) -> bool:
        return snapshot.button(device_id=instance_id, button=button)

    buttons = (
        _held_axis(
            negative=pressed(pygame.CONTROLLER_BUTTON_DPAD_LEFT),
            positive=pressed(pygame.CONTROLLER_BUTTON_DPAD_RIGHT),
        ),
        _held_axis(
            negative=pressed(pygame.CONTROLLER_BUTTON_DPAD_UP),
            positive=pressed(pygame.CONTROLLER_BUTTON_DPAD_DOWN),
        ),
    )
    if buttons != STANDING:
        return limited(x=buttons[0], y=buttons[1])
    return _past_deadzone(
        x=snapshot.axis(device_id=instance_id, axis=JOYSTICK_STICK_X_AXIS),
        y=snapshot.axis(device_id=instance_id, axis=JOYSTICK_STICK_Y_AXIS),
        deadzone=deadzone,
    )


def gamepad_direction(*, snapshot: InputSnapshot, instance_id: int, deadzone: float) -> Direction:
    """Return a pad's direction, from its controller layer when it has one, else its joystick layer.

    Returns:
        The direction (standing for a pad the snapshot does not hold).

    """
    if instance_id in snapshot.controller_axes:
        return _controller_direction(snapshot=snapshot, instance_id=instance_id, deadzone=deadzone)
    return _joystick_direction(snapshot=snapshot, instance_id=instance_id, deadzone=deadzone)


def player_direction(
    *, snapshot: InputSnapshot, device: DeviceIdentity, deadzone: float
) -> Direction:
    """Return the direction of the player on a device: the keyboard, or a pad by instance id.

    Returns:
        The direction.

    """
    if device.kind is DeviceKind.KEYBOARD or device.instance_id is None:
        return keyboard_direction(snapshot=snapshot)
    return gamepad_direction(snapshot=snapshot, instance_id=device.instance_id, deadzone=deadzone)


def keyboard_firing(*, snapshot: InputSnapshot) -> bool:
    """Return whether the keyboard player holds a fire key (J or Right Shift).

    Returns:
        True while one is held.

    """
    return bool(snapshot.pressed_scancodes & FIRE_SCANCODES)


def gamepad_firing(*, snapshot: InputSnapshot, instance_id: int) -> bool:
    """Return whether a pad holds its fire button, on its controller layer when it has one.

    Returns:
        True while it is held (never for a pad the snapshot does not hold).

    """
    if instance_id in snapshot.controller_axes:
        return snapshot.controller_button(device_id=instance_id, button=FIRE_BUTTON)
    return snapshot.button(device_id=instance_id, button=FIRE_BUTTON)


def player_firing(*, snapshot: InputSnapshot, device: DeviceIdentity) -> bool:
    """Return whether the player on a device holds fire: the keyboard, or a pad by instance id.

    Returns:
        True while fire is held.

    """
    if device.kind is DeviceKind.KEYBOARD or device.instance_id is None:
        return keyboard_firing(snapshot=snapshot)
    return gamepad_firing(snapshot=snapshot, instance_id=device.instance_id)
