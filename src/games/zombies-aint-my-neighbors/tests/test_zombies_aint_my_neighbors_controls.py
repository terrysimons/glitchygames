"""Which way each player is pushing: the keyboard, or a pad on either of its layers.

Feature plan 4, Task 2. Inputs are the engine's own ``InputSnapshot`` (its contract), built as
the engine builds one; a pad that has a controller layer appears in ``controller_axes``, and in
joystick mode (scripted sessions) it appears only in ``device_axes``, ``device_buttons`` and
``device_hats``.
"""

from __future__ import annotations

import math

import pygame
import pytest

from glitchygames.input.state import InputSnapshot
from zombies_aint_my_neighbors.controls import (
    DEFAULT_DEADZONE,
    gamepad_direction,
    keyboard_direction,
    player_direction,
)
from zombies_aint_my_neighbors.roster import DeviceIdentity, DeviceKind

PAD = 9
DIAGONAL = math.sqrt(0.5)
FULL = 32767
# Controller-layer button tuples are indexed by CONTROLLER_BUTTON_* id
CONTROLLER_BUTTON_COUNT = 21


def snapshot(**fields) -> InputSnapshot:
    """Return a frame's snapshot with nothing held but ``fields``.

    Returns:
        The snapshot.

    """
    base = {
        'pressed_scancodes': frozenset(),
        'modifiers': 0,
        'mouse_position': (0, 0),
        'mouse_buttons': (False, False, False),
        'mouse_focused': True,
    }
    return InputSnapshot(**(base | fields))


def controller_buttons(*held: int) -> tuple[bool, ...]:
    """Return a controller layer's buttons with ``held`` down.

    Returns:
        One flag per CONTROLLER_BUTTON_* id.

    """
    return tuple(button in held for button in range(CONTROLLER_BUTTON_COUNT))


def approx(direction: tuple[float, float], expected: tuple[float, float]) -> bool:
    """Return whether a direction is the expected one, to rounding.

    Returns:
        True when both parts match.

    """
    return all(
        math.isclose(got, want, abs_tol=1e-6) for got, want in zip(direction, expected, strict=True)
    )


@pytest.mark.parametrize(
    ('scancodes', 'expected'),
    [
        ({pygame.KSCAN_W}, (0.0, -1.0)),
        ({pygame.KSCAN_S}, (0.0, 1.0)),
        ({pygame.KSCAN_A}, (-1.0, 0.0)),
        ({pygame.KSCAN_D}, (1.0, 0.0)),
        ({pygame.KSCAN_UP}, (0.0, -1.0)),
        ({pygame.KSCAN_DOWN}, (0.0, 1.0)),
        ({pygame.KSCAN_LEFT}, (-1.0, 0.0)),
        ({pygame.KSCAN_RIGHT}, (1.0, 0.0)),
        ({pygame.KSCAN_W, pygame.KSCAN_D}, (DIAGONAL, -DIAGONAL)),
        ({pygame.KSCAN_DOWN, pygame.KSCAN_LEFT}, (-DIAGONAL, DIAGONAL)),
        # Opposite keys cancel
        ({pygame.KSCAN_A, pygame.KSCAN_D}, (0.0, 0.0)),
        (set(), (0.0, 0.0)),
    ],
)
def test_the_keyboard_walks_with_wasd_or_the_arrows(scancodes, expected):
    """WASD and the arrows, by position; diagonals are no faster."""
    direction = keyboard_direction(snapshot=snapshot(pressed_scancodes=frozenset(scancodes)))

    assert approx(direction, expected)


@pytest.mark.parametrize(
    ('axes', 'expected'),
    [
        ((FULL, 0), (1.0, 0.0)),
        ((-32768, 0), (-1.0, 0.0)),
        ((0, FULL), (0.0, 1.0)),
        ((FULL, FULL), (DIAGONAL, DIAGONAL)),
        # Inside the deadzone: nothing
        ((int(FULL * (DEFAULT_DEADZONE - 0.01)), 0), (0.0, 0.0)),
    ],
)
def test_a_controller_pads_left_stick_walks(axes, expected):
    """The controller layer's left stick, scaled to -1..1, past the deadzone, capped at 1."""
    frame = snapshot(controller_axes={PAD: (*axes, 0, 0, 0, 0)})

    direction = gamepad_direction(snapshot=frame, instance_id=PAD, deadzone=DEFAULT_DEADZONE)

    assert approx(direction, expected)


@pytest.mark.parametrize(
    ('buttons', 'expected'),
    [
        ((pygame.CONTROLLER_BUTTON_DPAD_UP,), (0.0, -1.0)),
        ((pygame.CONTROLLER_BUTTON_DPAD_DOWN,), (0.0, 1.0)),
        ((pygame.CONTROLLER_BUTTON_DPAD_LEFT,), (-1.0, 0.0)),
        (
            (pygame.CONTROLLER_BUTTON_DPAD_RIGHT, pygame.CONTROLLER_BUTTON_DPAD_UP),
            (DIAGONAL, -DIAGONAL),
        ),
    ],
)
def test_a_controller_pads_d_pad_walks_and_wins_over_the_stick(buttons, expected):
    """A d-pad press beats the stick (a player pressing it means it)."""
    frame = snapshot(
        controller_axes={PAD: (-FULL, -FULL, 0, 0, 0, 0)},
        controller_buttons={PAD: controller_buttons(*buttons)},
    )

    direction = gamepad_direction(snapshot=frame, instance_id=PAD, deadzone=DEFAULT_DEADZONE)

    assert approx(direction, expected)


def test_a_pad_in_joystick_mode_walks_with_its_first_two_axes():
    """With no controller layer, the joystick layer's axes 0 and 1 are the stick."""
    frame = snapshot(device_axes={PAD: (0.0, -1.0, 0.0)})

    direction = gamepad_direction(snapshot=frame, instance_id=PAD, deadzone=DEFAULT_DEADZONE)

    assert approx(direction, (0.0, -1.0))


@pytest.mark.parametrize(
    ('hat', 'expected'),
    [((1, 0), (1.0, 0.0)), ((0, 1), (0.0, -1.0)), ((-1, -1), (-DIAGONAL, DIAGONAL))],
)
def test_a_pad_in_joystick_mode_walks_with_its_hat(hat, expected):
    """The hat is the d-pad on the joystick layer; its up is +1, the screen's up is -1."""
    frame = snapshot(device_axes={PAD: (0.0, 0.0)}, device_hats={PAD: (hat,)})

    direction = gamepad_direction(snapshot=frame, instance_id=PAD, deadzone=DEFAULT_DEADZONE)

    assert approx(direction, expected)


def test_a_pad_in_joystick_mode_walks_with_d_pad_buttons_by_their_controller_numbers():
    """The engine reads the joystick layer's buttons by the controller layer's numbers."""
    held = tuple(
        button == pygame.CONTROLLER_BUTTON_DPAD_LEFT for button in range(CONTROLLER_BUTTON_COUNT)
    )
    frame = snapshot(device_axes={PAD: (0.0, 0.0)}, device_buttons={PAD: held})

    direction = gamepad_direction(snapshot=frame, instance_id=PAD, deadzone=DEFAULT_DEADZONE)

    assert approx(direction, (-1.0, 0.0))


def test_an_unknown_pad_does_not_walk():
    """A pad the snapshot does not hold reads as standing still."""
    direction = gamepad_direction(snapshot=snapshot(), instance_id=PAD, deadzone=DEFAULT_DEADZONE)

    assert direction == (0.0, 0.0)


def test_each_player_reads_only_their_own_device():
    """The keyboard player ignores pads, and a pad player ignores the keyboard and other pads."""
    frame = snapshot(
        pressed_scancodes=frozenset({pygame.KSCAN_D}),
        controller_axes={PAD: (0, FULL, 0, 0, 0, 0), 4: (-FULL, 0, 0, 0, 0, 0)},
    )
    keyboard = DeviceIdentity(kind=DeviceKind.KEYBOARD, instance_id=None)
    pad = DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=PAD)

    assert approx(player_direction(snapshot=frame, device=keyboard, deadzone=0.15), (1.0, 0.0))
    assert approx(player_direction(snapshot=frame, device=pad, deadzone=0.15), (0.0, 1.0))
