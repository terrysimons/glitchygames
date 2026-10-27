"""Checks on the golden replays in the workspace members' tests/fixtures/replays.

A fixture is ``<member>/tests/fixtures/replays/<name>.jsonl.gz``, recorded through the
real engine by scripts/record_scripted_session.py. Each fixture is itself a test item: the replay
plugin (glitchygames/testing/replays.py, loaded by the root conftest) replays it headless through
the game's console script entry point (``--replay-trace PATH --headless``: GameEngine +
SceneManager.start, not the golden harness) and fails with the printed divergence report unless
it exits ``ExitCode.SUCCESS``. The tests here check that the fixtures exist, are in game
directories, and that a replay through the engine really compares.

The controls rule: every golden replay pauses and resumes, exercises every keyboard control the
game binds, and ends with the game's own quit control (the recorder's controls tail,
scripts/record_scripted_session.py CONTROLS_TAIL_BUILDERS), so a control that stops working
makes its golden replay diverge. ``test_every_golden_replay_exercises_every_control`` enforces it:
it maps each recording's external input events to controls through the game's own bindings (its
ActionMaps, built by the game's ``_create_action_map(s)``) plus the controls the engine's scenes
hard-code (``ENGINE_SCENE_CONTROLS``), and fails on a control no event exercised unless
``UNEXERCISED_CONTROLS`` names it with its reason (an entry that names an exercised control, or
none, fails too). The tables are keyed by game (scripts/record_golden_traces.py's game keys, one
golden each), not by console script: one console script can replay several games' goldens
(Brave Adventurer's launcher replays Classic's and Papyrus's), each checked against its own
game's controls. A game that reads its controls from the frame's polled input instead of an
ActionMap (Drawing Fire) lists them all in ``ENGINE_SCENE_CONTROLS``, each by the event that
changes what is polled (a key's press, the mouse's motion, a button's press). A game with no
pause (``GAMES_WITHOUT_A_PAUSE``) is exempt from pausing, with its reason.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from pydantic import BaseModel, ConfigDict
from scripts.record_golden_traces import PROJECT_ROOT
from scripts.record_scripted_session import (
    GAME_CONSOLE_SCRIPTS,
    REPLAY_FIXTURE_SUFFIX,
    fixture_path,
    record_scripted_session,
)
from scripts.workspace_packages import workspace_members

import paddleslap
from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from clockwork_keep.game import ClockworkKeepScene
from drawing_fire import players as drawing_fire_players
from drawing_fire.game import DrawingFireScene
from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import logical_name
from glitchygames.recording import EVENT_BATCHES_FIELD, EXTERNAL_ORIGIN, INTERNAL_ORIGIN
from glitchygames.replay.driver import SPRITE_DIVERGENCE
from glitchygames.scenes.builtin_scenes.gamepad_choice import GamepadChoice, GamepadChoiceButtons
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.testing.replays import recording_console_script
from glitchygames.tracing import read_trace_result
from mr_muncher.game import MrMuncherScene
from tests.replay.replay_helpers import replay_through_engine, tamper_first_sprite_rect
from tests.stand_in_games import (
    member_recording_path,
    write_header_only_recording,
    write_stand_in_distribution,
)
from tests.stand_in_harness_games import (
    SteeredPaddleScene,
    register_stand_in_game,
    steered_paddle_script,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from glitchygames.input import ActionMap

# The frame a tampered copy of a fixture first differs from the engine at
TAMPERED_FRAME = 10
# The stand-in golden's frames: TAMPERED_FRAME and 20 frames after it
STAND_IN_GOLDEN_FRAMES = 30

# Each workspace member's (directly in <member>/tests/fixtures/replays/): every game is in a
# member, so no golden is in the root's tests/fixtures/replays/<console-script>/ layout
REPLAY_FIXTURES = sorted(
    path
    for member in workspace_members(project_root=PROJECT_ROOT)
    for path in member.replay_fixtures_directory.glob(f'*{REPLAY_FIXTURE_SUFFIX}')
)


def test_the_fixture_directory_holds_golden_replays():
    """A missing fixture set fails here instead of collecting zero replay cases."""
    assert REPLAY_FIXTURES, f"no {REPLAY_FIXTURE_SUFFIX} recordings in the members' fixtures"


def test_every_fixture_directory_is_a_game_console_script():
    """Each fixture's place names a game's console script (so the replay knows the game)."""
    unknown_console_scripts = sorted(
        {recording_console_script(path=path) for path in REPLAY_FIXTURES}
        - set(GAME_CONSOLE_SCRIPTS.values())
    )
    assert not unknown_console_scripts


@pytest.mark.parametrize('game', sorted(GAME_CONSOLE_SCRIPTS))
def test_every_golden_replay_is_replayed_by_its_games_console_script(game):
    """Each game's golden is collected under the console script that starts that game."""
    assert (
        recording_console_script(path=fixture_path(game_key=game)) == (GAME_CONSOLE_SCRIPTS[game])
    )


def test_a_members_golden_replay_is_replayed_by_the_members_console_script(tmp_path, monkeypatch):
    """<member>/tests/fixtures/replays/<name>.jsonl.gz: the member distribution names the game.

    A stand-in member distribution with exactly one console script, so its script is chosen
    without reading the recording's header (a header-only recording that names no game). The
    plugin's other layout, ``fixtures/replays/<console-script>/<name>.jsonl.gz`` (another
    project's, and no game's here since every game is a member), is named by its folder: a
    path under tmp_path whose folder is another installed stand-in's console script, so each
    layout's name visibly comes from its own source.
    """
    installed = tmp_path / 'site-packages'
    for distribution, package in (
        ('stand-in-muncher', 'stand_in_muncher'),
        ('stand-in-fire', 'stand_in_fire'),
    ):
        write_stand_in_distribution(
            directory=installed,
            distribution=distribution,
            console_scripts={distribution: f'{package}:main'},
        )
    monkeypatch.syspath_prepend(installed)
    golden = member_recording_path(tmp_path=tmp_path, distribution='stand-in-muncher')
    write_header_only_recording(path=golden, header={})
    root_layout_golden = (
        tmp_path / 'project' / 'fixtures' / 'replays' / 'stand-in-fire' / 'golden.jsonl.gz'
    )

    assert recording_console_script(path=golden) == 'stand-in-muncher'
    assert recording_console_script(path=root_layout_golden) == 'stand-in-fire'


def test_a_recording_of_a_folder_that_is_no_member_is_refused(tmp_path):
    """A distribution that is not installed (or has several console scripts) names no game."""
    misplaced = tmp_path / 'not-a-member' / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz'

    with pytest.raises(KeyError, match='not-a-member'):
        recording_console_script(path=misplaced)


def record_stand_in_golden(*, mocker, tmp_path: Path) -> tuple[str, Path]:
    """Record a stand-in game's scripted session through the engine, as a golden replay is.

    The stand-in (``SteeredPaddleScene``, tests/stand_in_harness_games.py) draws its paddle on
    every frame, so the recording has a sprite on TAMPERED_FRAME and every frame after it, and
    moves a fixed step per frame, so it replays deterministically.

    Returns:
        The stand-in's game key (registered for this test) and the recording's path.

    """
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    game_key = register_stand_in_game(
        mocker=mocker, scene_class=SteeredPaddleScene, script_builder=steered_paddle_script
    )
    path = tmp_path / f'golden{REPLAY_FIXTURE_SUFFIX}'
    record_scripted_session(
        game_key=game_key,
        frame_count=STAND_IN_GOLDEN_FRAMES,
        path=path,
        exercise_controls=False,
    )
    frames = read_trace_result(path=path).trace['frames']
    assert all(frame['sprites'] for frame in frames[TAMPERED_FRAME:])
    return game_key, path


def test_a_tampered_golden_replay_is_reported_at_its_frame(mocker, capsys, tmp_path):
    """The golden replays really compare: a fixture moved by one pixel diverges there."""
    game_key, path = record_stand_in_golden(mocker=mocker, tmp_path=tmp_path)
    tampered_path = tmp_path / f'tampered{REPLAY_FIXTURE_SUFFIX}'
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    capsys.readouterr()

    replay = replay_through_engine(mocker=mocker, game_key=game_key, path=tampered_path)

    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.REPLAY_DIVERGED, report
    assert report.startswith(f'Replay diverged at frame {TAMPERED_FRAME}: sprite ')
    divergence = replay.result.divergence
    assert divergence is not None
    assert divergence.frame_number == TAMPERED_FRAME
    assert divergence.kind == SPRITE_DIVERGENCE


def test_a_rebaselined_golden_replay_names_the_tampered_frames_and_replays_clean(
    mocker, capsys, tmp_path
):
    """--rebaseline of a tampered fixture reports the change, and its output replays exactly."""
    game_key, path = record_stand_in_golden(mocker=mocker, tmp_path=tmp_path)
    tampered_path = tmp_path / f'tampered{REPLAY_FIXTURE_SUFFIX}'
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    rebaselined_path = tmp_path / f'rebaselined{REPLAY_FIXTURE_SUFFIX}'
    capsys.readouterr()

    rebaseline = replay_through_engine(
        mocker=mocker,
        game_key=game_key,
        path=tampered_path,
        extra_arguments=('--rebaseline', str(rebaselined_path)),
    )

    summary = capsys.readouterr().out
    assert rebaseline.exit_status == ExitCode.SUCCESS, summary
    # Every tampered frame differs: those from TAMPERED_FRAME on that have a sprite to move
    frames = read_trace_result(path=tampered_path).trace['frames']
    tampered_frame_count = sum(1 for frame in frames[TAMPERED_FRAME:] if frame['sprites'])
    assert rebaseline.result.differing_frame_count == tampered_frame_count
    assert f'{tampered_frame_count} frames differ (first at {TAMPERED_FRAME}: sprite ' in summary
    assert 'sprites affected: ' in summary
    replay = replay_through_engine(mocker=mocker, game_key=game_key, path=rebaselined_path)
    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.SUCCESS, report
    assert replay.result.divergence is None


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


def golden_recording(game: str) -> dict[str, Any]:
    """Read a game's golden replay.

    Not cached: the six decoded recordings are about 200 MB, which a cache kept for the rest
    of the test run (the Linux CI job has 2 GB); reading them all again takes about 0.5 s.

    Args:
        game: The game's key (scripts/record_golden_traces.py), which names its golden.

    Returns:
        The decoded trace: header fields and ``frames``.

    """
    return read_trace_result(path=fixture_path(game_key=game)).trace


def received_events(*, recording: dict[str, Any]) -> list[tuple[int, str, dict[str, Any]]]:
    """Return every recorded event with its frame and the scene that received it.

    A frame's events reach the scene active when the frame starts: the scene the frame before
    ended on (a switch an event asks for happens after the frame's events).

    Args:
        recording: A decoded trace.

    Returns:
        (frame number, receiving scene's class name, event record), in order.

    """
    events: list[tuple[int, str, dict[str, Any]]] = []
    frames = recording['frames']
    for index, frame in enumerate(frames):
        receiving_scene = frames[max(index - 1, 0)]['scene']
        events.extend(
            (frame['frame'], receiving_scene, record)
            for batch in frame.get(EVENT_BATCHES_FIELD, [])
            for record in batch
        )
    return events


GOLDEN_GAMES = sorted(GAMEPLAY_ACTION_MAPS)


def test_every_game_with_a_golden_replay_has_its_controls_listed():
    """A new game's golden replay fails here until its bindings are listed above."""
    assert sorted(GAME_CONSOLE_SCRIPTS) == GOLDEN_GAMES
    assert sorted(ENGINE_SCENE_CONTROLS) == GOLDEN_GAMES
    assert {game for game, _scene, _action, _kind in UNEXERCISED_CONTROLS} <= set(GOLDEN_GAMES)


def test_each_golden_is_its_own_games_recording():
    """A game's golden names that game's scene, so its controls are checked against its own."""
    for game, (gameplay_scene, _action_maps_for) in GAMEPLAY_ACTION_MAPS.items():
        recording = golden_recording(game)
        assert recording['game'] == logical_name(scene_class=gameplay_scene), game


@pytest.mark.parametrize('game', GOLDEN_GAMES)
def test_every_golden_replay_exercises_every_control(game):
    """Each bound control is pressed in the game's golden replay, or listed with its reason."""
    recording = golden_recording(game)
    gameplay_scene, action_maps_for = GAMEPLAY_ACTION_MAPS[game]
    action_maps = action_maps_for(recording['options']['input_mode'])
    controls = [
        *_controls_from_action_maps(scene=gameplay_scene, action_maps=action_maps),
        *ENGINE_SCENE_CONTROLS[game],
    ]
    external_events = [
        (scene, record)
        for _frame_number, scene, record in received_events(recording=recording)
        if record['origin'] == EXTERNAL_ORIGIN
    ]
    exercised = [
        control
        for control in controls
        if any(
            control.is_triggered_by(scene=scene, record=record) for scene, record in external_events
        )
    ]
    allowlist = {
        (scene, action, kind): reason
        for (listed_game, scene, action, kind), reason in UNEXERCISED_CONTROLS.items()
        if listed_game == game
    }

    def allowlist_key(control: Control) -> tuple[str, str, InputKind]:
        return (control.scene, control.action, control.kind)

    missing = [
        control.describe()
        for control in controls
        if control not in exercised and allowlist_key(control) not in allowlist
    ]
    exercised_but_allowlisted = [
        control.describe() for control in exercised if allowlist_key(control) in allowlist
    ]
    allowlisted_but_unbound = sorted(
        str(key)
        for key in allowlist
        if not any(allowlist_key(control) == key for control in controls)
    )
    assert not missing, f'{game} golden replay never exercises: {missing}'
    assert not exercised_but_allowlisted, (
        f'{game}: UNEXERCISED_CONTROLS lists exercised controls: {exercised_but_allowlisted}'
    )
    assert not allowlisted_but_unbound, (
        f'{game}: UNEXERCISED_CONTROLS lists controls the game does not bind: '
        f'{allowlisted_but_unbound}'
    )


@pytest.mark.parametrize('game', GOLDEN_GAMES)
def test_every_golden_replay_pauses_resumes_and_ends_with_the_games_own_quit(game):
    """The game pauses and comes back, and the recording ends on a QUIT the game posted.

    No QUIT comes from outside (the recorder never ends the run itself: the tail's quit control
    does), so a replay whose game no longer quits misses the recorded internal QUIT and diverges.
    A game in GAMES_WITHOUT_A_PAUSE must never reach the pause screen instead.
    """
    recording = golden_recording(game)
    frames = recording['frames']
    gameplay_scene, _action_maps_for = GAMEPLAY_ACTION_MAPS[game]
    scenes = [frame['scene'] for frame in frames]
    if game in GAMES_WITHOUT_A_PAUSE:
        assert PauseScene.__name__ not in scenes, f'{game} has no pause, yet paused'
    else:
        assert PauseScene.__name__ in scenes, f'{game} golden replay never pauses'
        first_pause = scenes.index(PauseScene.__name__)
        assert gameplay_scene.__name__ in scenes[first_pause:], f'{game} never resumes'
    assert scenes[-1] == gameplay_scene.__name__
    quit_name = pygame.event.event_name(pygame.QUIT)
    quits = [
        (frame_number, record['origin'])
        for frame_number, _scene, record in received_events(recording=recording)
        if record['name'] == quit_name
    ]
    assert quits, f'{game} golden replay never quits'
    assert {origin for _frame_number, origin in quits} == {INTERNAL_ORIGIN}
    assert {frame_number for frame_number, _origin in quits} == {frames[-1]['frame']}
