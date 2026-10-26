"""Player input: a device (the keyboard and mouse, or a game controller) becomes an ``Intent``.

A player's input is turned into an ``Intent`` like any other driver's, so the battle's rules
never depend on who drives a soldier. Everything is read from an ``InputSnapshot`` (the
engine's ``current_input()``), never from pygame directly, and nothing here uses a clock or
randomness.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from drawing_fire.battle import Intent

if TYPE_CHECKING:
    from glitchygames.input.state import InputSnapshot

# pygame's Controller.get_axis scale: -32768..32767, normalised by the positive limit
AXIS_FULL_SCALE = 32767
# A stick closer to the centre than this (fraction of full deflection) is at rest
STICK_DEAD_ZONE = 0.2
# The right trigger fires once pulled past this fraction of its travel
TRIGGER_THRESHOLD = 0.5
LEFT_MOUSE_BUTTON_INDEX = 0

# Keyboard scancodes (the snapshot holds scancodes, not key codes). W and S do nothing in the
# MVP: there is no jump or crouch.
LEFT_SCANCODES = (pygame.KSCAN_A, pygame.KSCAN_LEFT)
RIGHT_SCANCODES = (pygame.KSCAN_D, pygame.KSCAN_RIGHT)
# Enter means both the main and the keypad key
START_SCANCODES = (pygame.KSCAN_RETURN, pygame.KSCAN_KP_ENTER)
BACK_SCANCODES = (pygame.KSCAN_ESCAPE,)


@dataclass(frozen=True)
class Device:
    """A source of player input: a game controller, or the keyboard and mouse."""

    # The game controller's instance id; None is the keyboard and mouse
    controller_id: int | None


KEYBOARD = Device(controller_id=None)


class Button(enum.Enum):
    """The buttons the game menus and seats read from a device."""

    START = enum.auto()
    BACK = enum.auto()
    LEFT = enum.auto()
    RIGHT = enum.auto()


def connected_devices(snapshot: InputSnapshot) -> tuple[Device, ...]:
    """Return the devices in a snapshot: the keyboard, then each controller, by id.

    Returns:
        The keyboard first, then one device per controller id in ``snapshot.controller_axes``.

    """
    return (
        KEYBOARD,
        *(
            Device(controller_id=controller_id)
            for controller_id in sorted(snapshot.controller_axes)
        ),
    )


def _normalised_axis(*, snapshot: InputSnapshot, controller_id: int, axis: int) -> float:
    """Return a controller axis scaled to -1..1 (-32768 would be just under -1, so clamp)."""
    raw_value = snapshot.controller_axis(device_id=controller_id, axis=axis)
    return max(-1.0, min(1.0, raw_value / AXIS_FULL_SCALE))


def _controller_move(*, snapshot: InputSnapshot, controller_id: int) -> float:
    move = _normalised_axis(
        snapshot=snapshot, controller_id=controller_id, axis=pygame.CONTROLLER_AXIS_LEFTX
    )
    return move if abs(move) > STICK_DEAD_ZONE else 0.0


def _controller_intent(*, controller_id: int, snapshot: InputSnapshot, last_aim: float) -> Intent:
    aim_x = _normalised_axis(
        snapshot=snapshot, controller_id=controller_id, axis=pygame.CONTROLLER_AXIS_RIGHTX
    )
    aim_y = _normalised_axis(
        snapshot=snapshot, controller_id=controller_id, axis=pygame.CONTROLLER_AXIS_RIGHTY
    )
    # The dead zone is on the stick's magnitude, so a diagonal push is not cut short
    aim_angle = (
        math.atan2(-aim_y, aim_x) if math.hypot(aim_x, aim_y) > STICK_DEAD_ZONE else last_aim
    )
    trigger = _normalised_axis(
        snapshot=snapshot, controller_id=controller_id, axis=pygame.CONTROLLER_AXIS_TRIGGERRIGHT
    )
    fire = trigger > TRIGGER_THRESHOLD or snapshot.controller_button(
        device_id=controller_id, button=pygame.CONTROLLER_BUTTON_RIGHTSHOULDER
    )
    return Intent(
        move=_controller_move(snapshot=snapshot, controller_id=controller_id),
        aim_angle=aim_angle,
        fire=fire,
    )


def _any_scancode_held(*, snapshot: InputSnapshot, scancodes: tuple[int, ...]) -> bool:
    return any(snapshot.scancode_pressed(scancode=scancode) for scancode in scancodes)


def _keyboard_move(*, snapshot: InputSnapshot) -> float:
    move = 0.0
    if _any_scancode_held(snapshot=snapshot, scancodes=LEFT_SCANCODES):
        move -= 1.0
    if _any_scancode_held(snapshot=snapshot, scancodes=RIGHT_SCANCODES):
        move += 1.0
    return move


def device_intent(
    *,
    device: Device,
    snapshot: InputSnapshot,
    soldier_position: tuple[float, float],
    last_aim: float,
) -> Intent:
    """Turn one device's input this frame into an ``Intent``.

    Args:
        device: The device driving the soldier.
        snapshot: This frame's input.
        soldier_position: The soldier's screen position (the keyboard aims from it at the mouse).
        last_aim: The previous aim angle, kept while a controller's aim stick rests or the mouse
            is exactly on the soldier's chest.

    Returns:
        The intent. Move is -1..1, aim is radians (0 right, pi / 2 up), fire is a bool.

    """
    if device.controller_id is not None:
        return _controller_intent(
            controller_id=device.controller_id, snapshot=snapshot, last_aim=last_aim
        )
    soldier_x, soldier_y = soldier_position
    mouse_x, mouse_y = snapshot.mouse_position
    # A mouse exactly on the chest points nowhere (atan2(0, 0) would snap the aim right), so
    # the aim stays where it was
    if (mouse_x, mouse_y) == (soldier_x, soldier_y):
        aim_angle = last_aim
    else:
        # Screen y grows downward, so up is soldier_y - mouse_y
        aim_angle = math.atan2(soldier_y - mouse_y, mouse_x - soldier_x)
    return Intent(
        move=_keyboard_move(snapshot=snapshot),
        aim_angle=aim_angle,
        fire=snapshot.mouse_buttons[LEFT_MOUSE_BUTTON_INDEX],
    )


def _controller_buttons_down(*, snapshot: InputSnapshot, controller_id: int) -> frozenset[Button]:
    move = _controller_move(snapshot=snapshot, controller_id=controller_id)
    candidates = {
        Button.START: snapshot.controller_button(
            device_id=controller_id, button=pygame.CONTROLLER_BUTTON_START
        ),
        Button.BACK: snapshot.controller_button(
            device_id=controller_id, button=pygame.CONTROLLER_BUTTON_BACK
        ),
        Button.LEFT: move < 0.0
        or snapshot.controller_button(
            device_id=controller_id, button=pygame.CONTROLLER_BUTTON_DPAD_LEFT
        ),
        Button.RIGHT: move > 0.0
        or snapshot.controller_button(
            device_id=controller_id, button=pygame.CONTROLLER_BUTTON_DPAD_RIGHT
        ),
    }
    return frozenset(button for button, is_down in candidates.items() if is_down)


def _keyboard_buttons_down(*, snapshot: InputSnapshot) -> frozenset[Button]:
    candidates = {
        Button.START: _any_scancode_held(snapshot=snapshot, scancodes=START_SCANCODES),
        Button.BACK: _any_scancode_held(snapshot=snapshot, scancodes=BACK_SCANCODES),
        Button.LEFT: _any_scancode_held(snapshot=snapshot, scancodes=LEFT_SCANCODES),
        Button.RIGHT: _any_scancode_held(snapshot=snapshot, scancodes=RIGHT_SCANCODES),
    }
    return frozenset(button for button, is_down in candidates.items() if is_down)


class ButtonEdges:
    """Tracks, per device and button, how many frames and seconds each has been held.

    ``update`` is called once per frame with that frame's snapshot and the seconds the frame
    advances. A device missing from a snapshot (a controller unplugged) reads as all buttons up.
    """

    def __init__(self) -> None:
        """Start with nothing held."""
        self._held_frame_counts: dict[tuple[Device, Button], int] = {}
        self._held_seconds: dict[tuple[Device, Button], float] = {}

    def update(self, snapshot: InputSnapshot, *, dt: float) -> None:
        """Count this frame's held buttons on every connected device.

        Args:
            snapshot: This frame's input.
            dt: The seconds this frame advances: a button down this frame has been held for
                them too (so a hold is timed the same at 30 and at 60 frames a second).

        """
        held_frame_counts: dict[tuple[Device, Button], int] = {}
        held_seconds: dict[tuple[Device, Button], float] = {}
        for device in connected_devices(snapshot):
            if device.controller_id is None:
                buttons_down = _keyboard_buttons_down(snapshot=snapshot)
            else:
                buttons_down = _controller_buttons_down(
                    snapshot=snapshot, controller_id=device.controller_id
                )
            for button in buttons_down:
                held_frame_counts[device, button] = (
                    self._held_frame_counts.get((device, button), 0) + 1
                )
                held_seconds[device, button] = self._held_seconds.get((device, button), 0.0) + dt
        self._held_frame_counts = held_frame_counts
        self._held_seconds = held_seconds

    def pressed(self, device: Device, button: Button) -> bool:
        """Return whether the button went down this frame (up the frame before).

        Returns:
            True on the first frame of a press only.

        """
        return self.held_frames(device, button) == 1

    def held_frames(self, device: Device, button: Button) -> int:
        """Return how many frames the button has been held so far.

        Returns:
            The frame count; 0 when the button is up.

        """
        return self._held_frame_counts.get((device, button), 0)

    def held_seconds(self, device: Device, button: Button) -> float:
        """Return how long the button has been held so far, in the seconds the frames advanced.

        Returns:
            The seconds; 0.0 when the button is up.

        """
        return self._held_seconds.get((device, button), 0.0)
