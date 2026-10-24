"""A gamepad's buttons on a screen with one way on and one way out (pause, game over).

The pause and game-over screens answered only the keyboard, so a player on a gamepad could not
unpause or restart (BUGS.md #209 item 10). ``GamepadChoiceButtons`` gives both screens the same
buttons, mirroring their keys:

- Start or A goes on (resume, restart) on its release, as SPACE does, and only when its press
  reached this screen: the release of the Start press that paused the game, or of an A held
  when the game ended, must not go on at once.
- B or Back quits on its press, as ESC does.

Both event layers are answered (glitchygames/input/input_devices.py, rule 1): a mapped pad's
buttons arrive as controller events (``CONTROLLER_BUTTON_*`` ids), any other device's as
joystick events, read by the same numbers (as ``ActionMap`` binds a ``controller_button`` in
joystick mode). The engine dispatches each device's events from one layer only and applies
``--input-mode``, so each press arrives once whatever the mode.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Self

import pygame

from glitchygames.input.action_map import ActionMap

if TYPE_CHECKING:
    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent

# The buttons that go on (resume, restart) and the buttons that quit
CONTINUE_BUTTONS: tuple[int, ...] = (pygame.CONTROLLER_BUTTON_START, pygame.CONTROLLER_BUTTON_A)
QUIT_BUTTONS: tuple[int, ...] = (pygame.CONTROLLER_BUTTON_B, pygame.CONTROLLER_BUTTON_BACK)


class GamepadChoice(enum.StrEnum):
    """What a gamepad button chose."""

    CONTINUE = 'continue'
    QUIT = 'quit'


class GamepadChoiceButtons:
    """Read a screen's gamepad buttons: continue on a release after a press, quit on a press."""

    def __init__(self: Self) -> None:
        """Bind the buttons on both event layers, with no press seen yet."""
        # 'auto' (ActionMap's default) binds controller and joystick button events: the engine
        # has already chosen which layer each device's events come from
        self._actions = ActionMap()
        for button in CONTINUE_BUTTONS:
            self._actions.bind(GamepadChoice.CONTINUE, controller_button=button)
        for button in QUIT_BUTTONS:
            self._actions.bind(GamepadChoice.QUIT, controller_button=button)
        # A continue button's press reached this screen, so its release goes on
        self._continue_pressed = False

    @property
    def action_map(self: Self) -> ActionMap:
        """The bindings: GamepadChoice actions on CONTINUE_BUTTONS and QUIT_BUTTONS."""
        return self._actions

    def button_pressed(
        self: Self, event: ControllerButtonEvent | JoyButtonEvent
    ) -> GamepadChoice | None:
        """Read a button press.

        Args:
            event: A CONTROLLERBUTTONDOWN or JOYBUTTONDOWN event.

        Returns:
            GamepadChoice.QUIT for a quit button (act now); None otherwise (a continue button's
            press only arms its release).

        """
        action = self._actions.get_action(event)
        if action == GamepadChoice.CONTINUE:
            self._continue_pressed = True
            return None
        if action == GamepadChoice.QUIT:
            return GamepadChoice.QUIT
        return None

    def button_released(
        self: Self, event: ControllerButtonEvent | JoyButtonEvent
    ) -> GamepadChoice | None:
        """Read a button release.

        Args:
            event: A CONTROLLERBUTTONUP or JOYBUTTONUP event.

        Returns:
            GamepadChoice.CONTINUE for a continue button whose press reached this screen (act
            now); None otherwise.

        """
        if self._actions.get_action(event) == GamepadChoice.CONTINUE and self._continue_pressed:
            self._continue_pressed = False
            return GamepadChoice.CONTINUE
        return None
