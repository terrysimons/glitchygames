"""The golden replays' control tables: every control each game binds, read from its own code.

The controls rule of the golden replays (tests/replay/test_golden_replays.py) needs each game's
bindings: its gameplay scene and ActionMaps (``GAMEPLAY_ACTION_MAPS``, built by the game's own
``_create_action_map(s)``), the controls the engine's scenes and the games' handlers hard-code
(``ENGINE_SCENE_CONTROLS``; Drawing Fire's from its players module, ``DRAWING_FIRE_CONTROLS``),
and the controls a golden replay never exercises, each with its reason
(``UNEXERCISED_CONTROLS``). These are per-game harness data, so this module imports the six
games' scene classes and ``drawing_fire.players``: it is the one root test module allowed to
(the Stage C borrow table's exemption; plans/2026-10-26-workspace-packages-3-demos.md). The
tests that use the tables stay in tests/replay/test_golden_replays.py, which imports no game.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

import pygame
from pydantic import BaseModel, ConfigDict

import paddleslap
from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from clockwork_keep.game import ClockworkKeepScene
from drawing_fire import players as drawing_fire_players
from drawing_fire.game import DrawingFireScene
from glitchygames.scenes.builtin_scenes.gamepad_choice import GamepadChoice, GamepadChoiceButtons
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from mr_muncher.game import MrMuncherScene

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.input import ActionMap


class InputKind(enum.StrEnum):
    """The kind of device a control is on."""

    KEYBOARD = 'keyboard'
    MOUSE = 'mouse'
    GAMEPAD = 'gamepad'


class Control(BaseModel):
    """One way to trigger one of a scene's actions: an input event with one attribute value.

    Attributes:
        scene: The class name of the scene the control belongs to (the scene that receives it).
        action: The action (an ActionMap action, prefixed for a game with several maps).
        kind: Keyboard or gamepad.
        event_name: The pygame event name that triggers it (``KeyDown``, ``KeyUp``, ...; an
            ActionMap axis binding is ``AxisMotion``).
        attribute: The event attribute it is bound to (``scancode``, ``key``, ``button``,
            ``axis``, or None for any event of the type).
        value: That attribute's bound value.

    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    scene: str
    action: str
    kind: InputKind
    event_name: str
    attribute: str | None = None
    value: int | None = None

    def describe(self) -> str:
        """Return the control as a line of a failure message.

        Returns:
            ``scene action: event attribute=value (kind)``.

        """
        binding = '' if self.attribute is None else f' {self.attribute}={self.value}'
        return f'{self.scene} {self.action}: {self.event_name}{binding} ({self.kind})'

    def is_triggered_by(self, *, scene: str, record: dict[str, Any]) -> bool:
        """Return whether a recorded external event exercises this control.

        Only keyboard and mouse controls can be exercised: no golden session has a gamepad
        (UNEXERCISED_CONTROLS says why).

        Args:
            scene: The class name of the scene that received the event.
            record: The recorded event (``name`` and ``attributes``).

        Returns:
            True when the event is this control's, sent to its scene.

        """
        return (
            self.kind in {InputKind.KEYBOARD, InputKind.MOUSE}
            and scene == self.scene
            and record['name'] == self.event_name
            and record['attributes'].get(self.attribute) == self.value
        )


def _key_control(*, scene: type, action: str, event_type: int, key: int) -> Control:
    """Build a keyboard control a scene hard-codes by key code (not through an ActionMap).

    Returns:
        The control.

    """
    return Control(
        scene=scene.__name__,
        action=action,
        kind=InputKind.KEYBOARD,
        event_name=pygame.event.event_name(event_type),
        attribute='key',
        value=key,
    )


def _scancode_control(*, scene: type, action: str, scancode: int) -> Control:
    """Build a keyboard control a scene reads as a held key from the polled input.

    The key's press (its KEYDOWN, at the key's scancode) is what makes the snapshot hold it.

    Returns:
        The control.

    """
    return Control(
        scene=scene.__name__,
        action=action,
        kind=InputKind.KEYBOARD,
        event_name=pygame.event.event_name(pygame.KEYDOWN),
        attribute='scancode',
        value=scancode,
    )


def _drawing_fire_snapshot_control(
    *,
    action: str,
    kind: InputKind,
    event_type: int,
    attribute: str | None = None,
    value: int | None = None,
) -> Control:
    """Build a mouse or gamepad control Drawing Fire's scene reads from the polled input.

    Args:
        action: The action.
        kind: Mouse or gamepad.
        event_type: The event that changes what the snapshot holds (MOUSEMOTION,
            MOUSEBUTTONDOWN, CONTROLLERAXISMOTION, CONTROLLERBUTTONDOWN).
        attribute: The event attribute that names the control (``button``, ``axis``), or None
            for any event of the type.
        value: That attribute's value.

    Returns:
        The control.

    """
    return Control(
        scene=DrawingFireScene.__name__,
        action=action,
        kind=kind,
        event_name=pygame.event.event_name(event_type),
        attribute=attribute,
        value=value,
    )


def _controls_from_action_maps(*, scene: type, action_maps: dict[str, ActionMap]) -> list[Control]:
    """Read a scene's controls from its ActionMaps (``ActionMap.to_dict``: every binding).

    Args:
        scene: The scene class the maps belong to.
        action_maps: Prefix -> action map (the prefix tells several maps' actions apart).

    Returns:
        One control per binding.

    """
    controls: list[Control] = []
    for prefix, action_map in action_maps.items():
        for action, entries in action_map.to_dict().items():
            for entry in entries:
                is_key = entry['type'] == pygame.event.event_name(pygame.KEYDOWN)
                attribute = next(name for name in ('scancode', 'code', 'axis') if name in entry)
                controls.append(
                    Control(
                        scene=scene.__name__,
                        action=f'{prefix}{action}',
                        kind=InputKind.KEYBOARD if is_key else InputKind.GAMEPAD,
                        event_name=entry['type'],
                        # A key code binding matches the event's key; a button's, its button
                        attribute={'code': 'key' if is_key else 'button'}.get(attribute, attribute),
                        value=entry[attribute],
                    )
                )
    return controls


def _paddleslap_action_maps(input_mode: str) -> dict[str, ActionMap]:
    player1_actions, player2_actions, pause_actions = paddleslap.Game._create_action_maps(
        input_mode=input_mode
    )
    return {'player1 ': player1_actions, 'player2 ': player2_actions, '': pause_actions}


# Game (its golden's game key) -> (its gameplay scene, its ActionMaps by prefix for an input
# mode), built by the game's own binding code
GAMEPLAY_ACTION_MAPS: dict[str, tuple[type, Callable[[str], dict[str, ActionMap]]]] = {
    'brave_adventurer': (
        BraveAdventurerScene,
        lambda input_mode: {'': BraveAdventurerScene._create_action_map(input_mode=input_mode)},
    ),
    'brave_adventurer_papyrus': (
        PapyrusBraveAdventurerScene,
        lambda input_mode: {
            '': PapyrusBraveAdventurerScene._create_action_map(input_mode=input_mode)
        },
    ),
    'clockwork_keep': (
        ClockworkKeepScene,
        lambda input_mode: {'': ClockworkKeepScene._create_action_map(input_mode=input_mode)},
    ),
    # Drawing Fire binds no ActionMap: DRAWING_FIRE_CONTROLS lists what it reads from the snapshot
    'drawing_fire': (DrawingFireScene, lambda _input_mode: {}),
    'mr_muncher': (
        MrMuncherScene,
        lambda input_mode: {'': MrMuncherScene._create_action_map(input_mode=input_mode)},
    ),
    'paddleslap': (paddleslap.Game, _paddleslap_action_maps),
}

# The pause screen every game uses (glitchygames/scenes/builtin_scenes/pause_scene.py): SPACE
# resumes on its release, ESC quits on its press, and Q quits on its release (the base Scene);
# a gamepad's Start or A continues and B or Back quits (gamepad_choice.py)
PAUSE_SCENE_CONTROLS: tuple[Control, ...] = (
    _key_control(scene=PauseScene, action='resume', event_type=pygame.KEYUP, key=pygame.K_SPACE),
    _key_control(scene=PauseScene, action='quit', event_type=pygame.KEYDOWN, key=pygame.K_ESCAPE),
    _key_control(scene=PauseScene, action='quit', event_type=pygame.KEYUP, key=pygame.K_q),
    *_controls_from_action_maps(
        scene=PauseScene, action_maps={'': GamepadChoiceButtons().action_map}
    ),
)

# Drawing Fire's controls (src/games/drawing-fire/src/drawing_fire/players.py), read from the
# frame's snapshot, not an ActionMap: the keyboard's START, BACK, LEFT and RIGHT keys (each key
# of the players module's own scancode lists), the mouse's aim and left button, and the
# controller's sticks, trigger and buttons; and Q, which quits on its release (the base Scene:
# Drawing Fire ignores only Escape's release, its BACK)
DRAWING_FIRE_CONTROLS: tuple[Control, ...] = (
    *(
        _scancode_control(scene=DrawingFireScene, action=action, scancode=scancode)
        for action, scancodes in (
            ('start', drawing_fire_players.START_SCANCODES),
            ('back', drawing_fire_players.BACK_SCANCODES),
            ('left', drawing_fire_players.LEFT_SCANCODES),
            ('right', drawing_fire_players.RIGHT_SCANCODES),
        )
        for scancode in scancodes
    ),
    _drawing_fire_snapshot_control(
        action='aim', kind=InputKind.MOUSE, event_type=pygame.MOUSEMOTION
    ),
    _drawing_fire_snapshot_control(
        action='fire',
        kind=InputKind.MOUSE,
        event_type=pygame.MOUSEBUTTONDOWN,
        attribute='button',
        # pygame numbers the mouse buttons from 1; the snapshot's index from 0
        value=drawing_fire_players.LEFT_MOUSE_BUTTON_INDEX + 1,
    ),
    *(
        _drawing_fire_snapshot_control(
            action=action,
            kind=InputKind.GAMEPAD,
            event_type=pygame.CONTROLLERAXISMOTION,
            attribute='axis',
            value=axis,
        )
        for action, axis in (
            ('move', pygame.CONTROLLER_AXIS_LEFTX),
            ('aim', pygame.CONTROLLER_AXIS_RIGHTX),
            ('aim', pygame.CONTROLLER_AXIS_RIGHTY),
            ('fire', pygame.CONTROLLER_AXIS_TRIGGERRIGHT),
        )
    ),
    *(
        _drawing_fire_snapshot_control(
            action=action,
            kind=InputKind.GAMEPAD,
            event_type=pygame.CONTROLLERBUTTONDOWN,
            attribute='button',
            value=button,
        )
        for action, button in (
            ('fire', pygame.CONTROLLER_BUTTON_RIGHTSHOULDER),
            ('start', pygame.CONTROLLER_BUTTON_START),
            ('back', pygame.CONTROLLER_BUTTON_BACK),
            ('left', pygame.CONTROLLER_BUTTON_DPAD_LEFT),
            ('right', pygame.CONTROLLER_BUTTON_DPAD_RIGHT),
        )
    ),
    _key_control(scene=DrawingFireScene, action='quit', event_type=pygame.KEYUP, key=pygame.K_q),
)

# Game -> the controls its scenes hard-code in handlers (no ActionMap): the pause
# screen's, PaddleSlap's quit (the base Scene quits on the release of Q or ESC: PaddleSlap binds
# no quit of its own), Mr. Muncher's joystick hat (on_joy_hat_motion_event) and every one of
# Drawing Fire's (it has no pause screen)
ENGINE_SCENE_CONTROLS: dict[str, tuple[Control, ...]] = {
    'brave_adventurer': PAUSE_SCENE_CONTROLS,
    'brave_adventurer_papyrus': PAUSE_SCENE_CONTROLS,
    'clockwork_keep': PAUSE_SCENE_CONTROLS,
    'drawing_fire': DRAWING_FIRE_CONTROLS,
    'mr_muncher': (
        *PAUSE_SCENE_CONTROLS,
        Control(
            scene=MrMuncherScene.__name__,
            action='steer',
            kind=InputKind.GAMEPAD,
            event_name=pygame.event.event_name(pygame.JOYHATMOTION),
        ),
    ),
    'paddleslap': (
        *PAUSE_SCENE_CONTROLS,
        _key_control(scene=paddleslap.Game, action='quit', event_type=pygame.KEYUP, key=pygame.K_q),
        _key_control(
            scene=paddleslap.Game, action='quit', event_type=pygame.KEYUP, key=pygame.K_ESCAPE
        ),
    ),
}

NO_GAMEPAD_IN_THE_SESSION = (
    'no golden session has a gamepad: the scripted session runs on the dummy driver, which has '
    'no joystick, and the engine drops the input events of devices it has not opened '
    '(InputDevices.dispatches), so a supervisor cannot post them (a stand-in device recorded '
    'through the devices door would be needed: plans/future-features.md #44)'
)
# Game -> why it never pauses (so its golden replay cannot pause and resume)
GAMES_WITHOUT_A_PAUSE: dict[str, str] = {
    'drawing_fire': (
        'Drawing Fire has no pause in its MVP: players drop into and out of a battle that runs '
        'on (the next one starts on its own), and Escape is Back on the keyboard, held to '
        'leave a seat (plans/2026-10-25-drawing-fire-design.md, sections 4.1 and 4.4)'
    ),
}
# The games whose golden replays go through the engine's pause screen
PAUSING_GAMES = sorted(set(GAMEPLAY_ACTION_MAPS) - set(GAMES_WITHOUT_A_PAUSE))
QUITS_ONCE = (
    "a session quits once, and it quits from the game's scene with the game's own quit "
    'control; the pause screen quits through the same QUIT event (tests/scenes cover it)'
)

# (game, scene, action, kind) -> why its golden replay never exercises that action's controls
# of that kind
UNEXERCISED_CONTROLS: dict[tuple[str, str, str, InputKind], str] = {
    **{
        (game, scene.__name__, action, InputKind.GAMEPAD): NO_GAMEPAD_IN_THE_SESSION
        for game, scene, actions in (
            ('brave_adventurer', BraveAdventurerScene, ('move_right', 'move_left', 'jump')),
            ('brave_adventurer', BraveAdventurerScene, ('mic_toggle',)),
            (
                'brave_adventurer_papyrus',
                PapyrusBraveAdventurerScene,
                ('move_right', 'move_left', 'jump'),
            ),
            (
                'clockwork_keep',
                ClockworkKeepScene,
                ('move_right', 'move_left', 'jump', 'interact', 'run'),
            ),
            (
                'drawing_fire',
                DrawingFireScene,
                ('move', 'aim', 'fire', 'start', 'back', 'left', 'right'),
            ),
            (
                'mr_muncher',
                MrMuncherScene,
                ('move_up', 'move_left', 'move_down', 'move_right', 'pause', 'steer'),
            ),
            (
                'paddleslap',
                paddleslap.Game,
                ('player1 up', 'player1 down', 'player2 up', 'player2 down'),
            ),
        )
        for action in actions
    },
    **{
        (game, PauseScene.__name__, 'quit', InputKind.KEYBOARD): QUITS_ONCE
        for game in PAUSING_GAMES
    },
    **{
        (game, PauseScene.__name__, choice, InputKind.GAMEPAD): NO_GAMEPAD_IN_THE_SESSION
        for game in PAUSING_GAMES
        for choice in GamepadChoice
    },
}
