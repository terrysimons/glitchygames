"""Checks on the golden replays under tests/fixtures/replays.

A fixture is ``tests/fixtures/replays/<console-script>/<name>.jsonl.gz``, recorded through the
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
none, fails too).
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from pydantic import BaseModel, ConfigDict
from scripts.record_golden_traces import PROJECT_ROOT
from scripts.record_scripted_session import (
    CONSOLE_SCRIPT_GAME_KEYS,
    REPLAY_FIXTURE_DIRECTORY,
    REPLAY_FIXTURE_SUFFIX,
    fixture_path,
)
from scripts.workspace_packages import workspace_members

from glitchygames.examples import paddleslap
from glitchygames.examples.brave_adventurer.game import BraveAdventurerScene
from glitchygames.examples.brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene
from glitchygames.exit_codes import ExitCode
from glitchygames.recording import EVENT_BATCHES_FIELD, EXTERNAL_ORIGIN, INTERNAL_ORIGIN
from glitchygames.replay.driver import SPRITE_DIVERGENCE
from glitchygames.scenes.builtin_scenes.gamepad_choice import GamepadChoice, GamepadChoiceButtons
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.testing.replays import recording_console_script
from glitchygames.tracing import read_trace_result
from mr_muncher.game import MrMuncherScene
from tests.replay.replay_helpers import replay_through_engine, tamper_first_sprite_rect

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.input import ActionMap

# The frame a tampered copy of a fixture first differs from the engine at
TAMPERED_FRAME = 10

# The engine's (tests/fixtures/replays/<console-script>/) and each workspace member's (directly in
# <member>/tests/fixtures/replays/)
REPLAY_FIXTURES = sorted([
    *REPLAY_FIXTURE_DIRECTORY.glob(f'*/*{REPLAY_FIXTURE_SUFFIX}'),
    *(
        path
        for member in workspace_members(project_root=PROJECT_ROOT)
        for path in member.replay_fixtures_directory.glob(f'*{REPLAY_FIXTURE_SUFFIX}')
    ),
])


def test_the_fixture_directory_holds_golden_replays():
    """A missing fixture set fails here instead of collecting zero replay cases."""
    assert REPLAY_FIXTURES, (
        f'no {REPLAY_FIXTURE_SUFFIX} recordings under {REPLAY_FIXTURE_DIRECTORY}'
    )


def test_every_fixture_directory_is_a_game_console_script():
    """Each fixture's place names a game's console script (so the replay knows the game)."""
    unknown_console_scripts = sorted(
        {recording_console_script(path=path) for path in REPLAY_FIXTURES}
        - set(CONSOLE_SCRIPT_GAME_KEYS)
    )
    assert not unknown_console_scripts


def test_a_members_golden_replay_is_replayed_by_the_members_console_script():
    """<member>/tests/fixtures/replays/<name>.jsonl.gz: the member distribution names the game."""
    (member,) = [
        member
        for member in workspace_members(project_root=PROJECT_ROOT)
        if member.distribution == 'mr-muncher'
    ]
    golden = member.replay_fixtures_directory / 'golden.jsonl.gz'

    assert recording_console_script(path=golden) == 'mr-muncher'
    assert (
        recording_console_script(
            path=PROJECT_ROOT / 'tests' / 'fixtures' / 'replays' / 'paddleslap' / 'golden.jsonl.gz'
        )
        == 'paddleslap'
    )


def test_a_recording_of_a_folder_that_is_no_member_is_refused(tmp_path):
    """A distribution that is not installed (or has several console scripts) names no game."""
    misplaced = tmp_path / 'not-a-member' / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz'

    with pytest.raises(KeyError, match='not-a-member'):
        recording_console_script(path=misplaced)


def test_a_tampered_golden_replay_is_reported_at_its_frame(mocker, capsys, tmp_path):
    """The golden replays really compare: a fixture moved by one pixel diverges there."""
    path = REPLAY_FIXTURE_DIRECTORY / 'paddleslap' / f'golden{REPLAY_FIXTURE_SUFFIX}'
    tampered_path = tmp_path / path.name
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)

    replay = replay_through_engine(mocker=mocker, game_key='paddleslap', path=tampered_path)

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
    path = REPLAY_FIXTURE_DIRECTORY / 'paddleslap' / f'golden{REPLAY_FIXTURE_SUFFIX}'
    tampered_path = tmp_path / path.name
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    rebaselined_path = tmp_path / f'rebaselined{REPLAY_FIXTURE_SUFFIX}'

    rebaseline = replay_through_engine(
        mocker=mocker,
        game_key='paddleslap',
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
    replay = replay_through_engine(mocker=mocker, game_key='paddleslap', path=rebaselined_path)
    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.SUCCESS, report
    assert replay.result.divergence is None


class InputKind(enum.StrEnum):
    """The kind of device a control is on."""

    KEYBOARD = 'keyboard'
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

        Only keyboard controls can be exercised: no golden session has a gamepad
        (UNEXERCISED_CONTROLS says why).

        Args:
            scene: The class name of the scene that received the event.
            record: The recorded event (``name`` and ``attributes``).

        Returns:
            True when the event is this control's, sent to its scene.

        """
        return (
            self.kind is InputKind.KEYBOARD
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


# Console script -> (its gameplay scene, its ActionMaps by prefix for an input mode), built by
# the game's own binding code
GAMEPLAY_ACTION_MAPS: dict[str, tuple[type, Callable[[str], dict[str, ActionMap]]]] = {
    'brave-adventurer': (
        BraveAdventurerScene,
        lambda input_mode: {'': BraveAdventurerScene._create_action_map(input_mode=input_mode)},
    ),
    'brave-adventurer-papyrus': (
        PapyrusBraveAdventurerScene,
        lambda input_mode: {
            '': PapyrusBraveAdventurerScene._create_action_map(input_mode=input_mode)
        },
    ),
    'clockwork-keep': (
        ClockworkKeepScene,
        lambda input_mode: {'': ClockworkKeepScene._create_action_map(input_mode=input_mode)},
    ),
    'mr-muncher': (
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

# Console script -> the controls its scenes hard-code in handlers (no ActionMap): the pause
# screen's, PaddleSlap's quit (the base Scene quits on the release of Q or ESC: PaddleSlap binds
# no quit of its own), and Mr. Muncher's joystick hat (on_joy_hat_motion_event)
ENGINE_SCENE_CONTROLS: dict[str, tuple[Control, ...]] = {
    'brave-adventurer': PAUSE_SCENE_CONTROLS,
    'brave-adventurer-papyrus': PAUSE_SCENE_CONTROLS,
    'clockwork-keep': PAUSE_SCENE_CONTROLS,
    'mr-muncher': (
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
QUITS_ONCE = (
    "a session quits once, and it quits from the game's scene with the game's own quit "
    'control; the pause screen quits through the same QUIT event (tests/scenes cover it)'
)

# (console script, scene, action, kind) -> why no golden replay exercises that action's
# controls of that kind
UNEXERCISED_CONTROLS: dict[tuple[str, str, str, InputKind], str] = {
    **{
        (console_script, scene.__name__, action, InputKind.GAMEPAD): NO_GAMEPAD_IN_THE_SESSION
        for console_script, scene, actions in (
            ('brave-adventurer', BraveAdventurerScene, ('move_right', 'move_left', 'jump')),
            ('brave-adventurer', BraveAdventurerScene, ('mic_toggle',)),
            (
                'brave-adventurer-papyrus',
                PapyrusBraveAdventurerScene,
                ('move_right', 'move_left', 'jump'),
            ),
            (
                'clockwork-keep',
                ClockworkKeepScene,
                ('move_right', 'move_left', 'jump', 'interact', 'run'),
            ),
            (
                'mr-muncher',
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
        (console_script, PauseScene.__name__, 'quit', InputKind.KEYBOARD): QUITS_ONCE
        for console_script in GAMEPLAY_ACTION_MAPS
    },
    **{
        (console_script, PauseScene.__name__, choice, InputKind.GAMEPAD): NO_GAMEPAD_IN_THE_SESSION
        for console_script in GAMEPLAY_ACTION_MAPS
        for choice in GamepadChoice
    },
}


def golden_recording(console_script: str) -> dict[str, Any]:
    """Read a game's golden replay.

    Not cached: the five decoded recordings are about 200 MB, which a cache kept for the rest
    of the test run (the Linux CI job has 2 GB); reading them all again takes about 0.5 s.

    Returns:
        The decoded trace: header fields and ``frames``.

    """
    game_key = CONSOLE_SCRIPT_GAME_KEYS[console_script]
    return read_trace_result(path=fixture_path(game_key=game_key)).trace


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


GOLDEN_CONSOLE_SCRIPTS = sorted(GAMEPLAY_ACTION_MAPS)


def test_every_game_with_a_golden_replay_has_its_controls_listed():
    """A new game's golden replay fails here until its bindings are listed above."""
    assert sorted(CONSOLE_SCRIPT_GAME_KEYS) == GOLDEN_CONSOLE_SCRIPTS
    assert sorted(ENGINE_SCENE_CONTROLS) == GOLDEN_CONSOLE_SCRIPTS


@pytest.mark.parametrize('console_script', GOLDEN_CONSOLE_SCRIPTS)
def test_every_golden_replay_exercises_every_control(console_script):
    """Each bound control is pressed in the game's golden replay, or listed with its reason."""
    recording = golden_recording(console_script)
    gameplay_scene, action_maps_for = GAMEPLAY_ACTION_MAPS[console_script]
    action_maps = action_maps_for(recording['options']['input_mode'])
    controls = [
        *_controls_from_action_maps(scene=gameplay_scene, action_maps=action_maps),
        *ENGINE_SCENE_CONTROLS[console_script],
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
        for (script, scene, action, kind), reason in UNEXERCISED_CONTROLS.items()
        if script == console_script
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
    assert not missing, f'{console_script} golden replay never exercises: {missing}'
    assert not exercised_but_allowlisted, (
        f'{console_script}: UNEXERCISED_CONTROLS lists exercised controls: '
        f'{exercised_but_allowlisted}'
    )
    assert not allowlisted_but_unbound, (
        f'{console_script}: UNEXERCISED_CONTROLS lists controls the game does not bind: '
        f'{allowlisted_but_unbound}'
    )


@pytest.mark.parametrize('console_script', GOLDEN_CONSOLE_SCRIPTS)
def test_every_golden_replay_pauses_resumes_and_ends_with_the_games_own_quit(console_script):
    """The game pauses and comes back, and the recording ends on a QUIT the game posted.

    No QUIT comes from outside (the recorder never ends the run itself: the tail's quit control
    does), so a replay whose game no longer quits misses the recorded internal QUIT and diverges.
    """
    recording = golden_recording(console_script)
    frames = recording['frames']
    gameplay_scene, _action_maps_for = GAMEPLAY_ACTION_MAPS[console_script]
    scenes = [frame['scene'] for frame in frames]
    assert PauseScene.__name__ in scenes, f'{console_script} golden replay never pauses'
    first_pause = scenes.index(PauseScene.__name__)
    assert gameplay_scene.__name__ in scenes[first_pause:], f'{console_script} never resumes'
    assert scenes[-1] == gameplay_scene.__name__
    quit_name = pygame.event.event_name(pygame.QUIT)
    quits = [
        (frame_number, record['origin'])
        for frame_number, _scene, record in received_events(recording=recording)
        if record['name'] == quit_name
    ]
    assert quits, f'{console_script} golden replay never quits'
    assert {origin for _frame_number, origin in quits} == {INTERNAL_ORIGIN}
    assert {frame_number for frame_number, _origin in quits} == {frames[-1]['frame']}
