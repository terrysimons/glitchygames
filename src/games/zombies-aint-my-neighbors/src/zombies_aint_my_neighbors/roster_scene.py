"""A screen that keeps the join roster and turns start presses and unplugged pads into changes.

The title and the feature card read the same controls the same way: Enter on the keyboard,
START on a pad (either layer), P to pause, and an unplugged pad giving up its slot. Each screen
decides what a start press means (``_press_start``) and what an unplugged pad means
(``_device_left``); this base turns the engine's events into those two calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final, override

import pygame

from glitchygames.color import BLACK
from glitchygames.input.action_map import ActionMap
from zombies_aint_my_neighbors.music import SCORE
from zombies_aint_my_neighbors.pad_tolerant import PadTolerantScene
from zombies_aint_my_neighbors.roster import DeviceIdentity, DeviceKind, JoinRoster
from zombies_aint_my_neighbors.sounds import SOUND_REFERENCES

if TYPE_CHECKING:
    from collections.abc import Mapping

    from glitchygames.events.base import ControllerButtonEvent, JoyButtonEvent, KeyEvent
    from glitchygames.input.input_devices import InputDevice

# The keyboard's start is Enter, on the main keys or the keypad: never Space or Esc, which the
# engine's pause and game-over screens use, nor Q, P, backtick, F3 or F4 (_create_action_map)
# A pad's start. In joystick mode an unmapped pad's START is the same number: the engine's
# gamepad_choice.py reads both layers by the same numbers
GAMEPAD_START_BUTTON: Final = pygame.CONTROLLER_BUTTON_START
# P pauses, by its position (the shared pause screen resumes with Space)
PAUSE_SCANCODE: Final = pygame.KSCAN_P
# The actions the screens bind
START_ACTION: Final = 'start'
PAUSE_ACTION: Final = 'pause'
KEYBOARD_IDENTITY: Final = DeviceIdentity(kind=DeviceKind.KEYBOARD, instance_id=None)


def gamepad_identity(*, instance_id: int) -> DeviceIdentity:
    """Return a pad's identity from its SDL instance id.

    Returns:
        The identity.

    """
    return DeviceIdentity(kind=DeviceKind.GAMEPAD, instance_id=instance_id)


def as_roster(roster: JoinRoster | dict[str, Any] | None) -> JoinRoster:
    """Return a roster from a roster, its JSON form (as a replay passes it back) or None.

    Returns:
        The roster (empty for None).

    """
    if roster is None:
        return JoinRoster.empty()
    if isinstance(roster, JoinRoster):
        return roster
    return JoinRoster.model_validate(roster)


class RosterScene(PadTolerantScene):
    """A black screen that keeps the roster and reads start presses and unplugged pads."""

    # Every sound the game plays, compiled while the game starts (feature plans 10 and 11;
    # decision 11): the effects and the score's mixes. The title and the neighborhood, the scenes
    # the launcher hands the engine, inherit it
    SOUNDS = (*SOUND_REFERENCES, *SCORE)

    @override
    def __init__(
        self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        roster: JoinRoster | dict[str, Any] | None = None,
    ) -> None:
        """Make the screen.

        Args:
            options: The engine's options.
            groups: The sprite groups to draw into (a new LayeredDirty when None).
            roster: The players joined: a roster, its JSON form (as a replay passes it back),
                or None for nobody.

        """
        if groups is None:
            groups = pygame.sprite.LayeredDirty()
        super().__init__(options=options, groups=groups)
        self.background_color = BLACK
        self.roster = as_roster(roster)
        self.actions = self._create_action_map(options=self.options or {})
        # Set up once already: a later setup is a resume (from the pause screen)
        self._has_been_set_up = False

    @staticmethod
    def _create_action_map(*, options: Mapping[str, Any]) -> ActionMap:
        """Bind the screens' controls, every key by its position (ActionMap's docstring).

        Enter (main or keypad) or a pad's START is start; P pauses.

        Args:
            options: The engine's options: the map follows its input mode
                (``ActionMap.from_engine_options``), so a pad's START binds the controller
                layer, the joystick layer or both, as the engine delivers it.

        Returns:
            The action map.

        """
        actions = ActionMap.from_engine_options(options)
        actions.bind(
            START_ACTION, scancode=pygame.KSCAN_RETURN, controller_button=GAMEPAD_START_BUTTON
        )
        actions.bind(START_ACTION, scancode=pygame.KSCAN_KP_ENTER)
        actions.bind(PAUSE_ACTION, scancode=PAUSE_SCANCODE)
        return actions

    @override
    def setup(self) -> None:
        """Set the screen up; on a resume, first drop the pads unplugged while it was away.

        The engine tells only the active scene that a device left
        (``SceneManager.on_input_device_removed``), so a pad unplugged on the pause screen never
        reached this one. Every pad in the roster must still be a connected device.
        """
        super().setup()
        if self._has_been_set_up:
            self._drop_pads_no_longer_connected()
        self._has_been_set_up = True

    def _drop_pads_no_longer_connected(self) -> None:
        """Free the slot of every joined pad the engine no longer sees."""
        for player in self.roster.joined_players:
            device = player.device
            if device.instance_id is None:
                # The keyboard is never unplugged
                continue
            if self.input_devices.get(instance_id=device.instance_id) is None:
                self._device_left(device=device)

    @override
    def replay_arguments(self) -> dict[str, Any]:
        """Rebuild this screen as it began.

        Returns:
            The roster, as JSON reads it back.

        """
        return {'roster': self.roster.model_dump(mode='json')}

    @override
    def on_key_down_event(self, event: KeyEvent) -> None:
        """Enter presses start for the keyboard and P pauses; other keys go to the base scene.

        Args:
            event: The key press.

        """
        action = self.actions.get_action(event)
        if action == START_ACTION:
            self._press_start(device=KEYBOARD_IDENTITY)
        elif action == PAUSE_ACTION:
            self.pause()
        else:
            super().on_key_down_event(event)

    @override
    def on_controller_button_down_event(self, event: ControllerButtonEvent) -> None:
        """START on a mapped pad presses start for that pad.

        Args:
            event: The button press.

        """
        if self.actions.get_action(event) == START_ACTION:
            self._press_start(device=gamepad_identity(instance_id=event.instance_id))
        else:
            super().on_controller_button_down_event(event)

    @override
    def on_joy_button_down_event(self, event: JoyButtonEvent) -> None:
        """START on the joystick layer (unmapped pads, and joystick mode) presses start.

        Args:
            event: The button press.

        """
        if self.actions.get_action(event) == START_ACTION:
            self._press_start(device=gamepad_identity(instance_id=event.instance_id))
        else:
            super().on_joy_button_down_event(event)

    @override
    def on_input_device_removed(self, *, device: InputDevice) -> None:
        """An unplugged pad gives up its slot.

        Args:
            device: The device the game no longer sees.

        """
        self._device_left(device=gamepad_identity(instance_id=device.instance_id))

    def _press_start(self, *, device: DeviceIdentity) -> None:
        """React to a device's start press: each screen says what it means.

        Args:
            device: The device whose start was pressed.

        Raises:
            NotImplementedError: Always, here: a screen that reads start must say what it does.

        """
        message = f'{type(self).__name__} does not say what a start press does'
        raise NotImplementedError(message)

    def _device_left(self, *, device: DeviceIdentity) -> None:
        """Free an unplugged device's slot.

        Args:
            device: The device that was unplugged.

        """
        self.roster = self.roster.leave(device=device)
