"""Checks on the golden replays in the workspace members' tests/fixtures/replays.

A fixture is ``<member>/tests/fixtures/replays/<name>.jsonl.gz``, recorded through the
real engine by scripts/record_scripted_session.py. Each fixture is itself a test item: the replay
plugin (glitchygames/testing/replays.py, registered by the engine's pytest11 entry point)
replays it headless through the game's console script entry point (``--replay-trace PATH
--headless``: GameEngine + SceneManager.start, not the golden harness) and fails with the
printed divergence report unless it exits ``ExitCode.SUCCESS``. The tests here check that the
fixtures exist and are in game directories; that a replay through the engine really compares is
checked on stand-ins in tests/replay/test_a_golden_replay_compares.py.

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

from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts.record_golden_traces import GAME_SCENES, PROJECT_ROOT
from scripts.record_scripted_session import (
    GAME_CONSOLE_SCRIPTS,
    REPLAY_FIXTURE_SUFFIX,
    fixture_path,
)
from scripts.workspace_packages import members_in_layer, workspace_members

from glitchygames.logical_names import logical_name
from glitchygames.recording import EVENT_BATCHES_FIELD, EXTERNAL_ORIGIN, INTERNAL_ORIGIN
from glitchygames.replay.driver import GAME_HEADER_FIELD
from glitchygames.replay.tools.children import recording_console_script
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.tracing import TraceReader, read_trace_result
from tests.replay.golden_replay_controls import (
    ENGINE_SCENE_CONTROLS,
    GAMEPLAY_ACTION_MAPS,
    GAMES_WITHOUT_A_PAUSE,
    UNEXERCISED_CONTROLS,
    Control,
    InputKind,
    _controls_from_action_maps,
)
from tests.workspace_expectations import EXPECTED_GAME_CONSOLE_SCRIPTS, GAMES_LAYER
from tests.workspace_goldens import every_games_golden

if TYPE_CHECKING:
    from pathlib import Path


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


def golden_id(path: Path) -> str:
    """The golden's repository path, as pytest shows it.

    Returns:
        ``src/games/<member>/tests/fixtures/replays/<name>.jsonl.gz``.

    """
    return path.relative_to(PROJECT_ROOT).as_posix()


def test_every_fixture_directory_is_a_game_console_script():
    """Each fixture's place names a game's console script (so the replay knows the game).

    The expected set: the goldens are exactly EXPECTED_GOLDENS (written out by hand: every
    games-layer member holds at least one), and they are replayed by exactly the games-layer
    members' console scripts, which are EXPECTED_GAME_CONSOLE_SCRIPTS (written out by hand: 5).
    """
    every_games_golden(project_root=PROJECT_ROOT)
    games_console_scripts = {
        console_script
        for member in members_in_layer(project_root=PROJECT_ROOT, layer=GAMES_LAYER)
        for console_script in member.console_scripts
    }

    assert games_console_scripts == EXPECTED_GAME_CONSOLE_SCRIPTS
    assert {recording_console_script(path=path) for path in REPLAY_FIXTURES} == (
        games_console_scripts
    )


@pytest.mark.parametrize('golden', REPLAY_FIXTURES, ids=golden_id)
def test_every_golden_replay_is_replayed_by_its_games_console_script(golden):
    """Each golden is collected under a console script of the member holding its game.

    The golden's header names its game by logical name; the golden-trace tool's game keys are
    mapped to logical names explicitly (the logical name of each key's scene class), so the
    golden is the one the tool records for that game, in the member whose packages hold the
    game. (The test above asserts the goldens are there: an empty parametrization would skip.)
    """
    game_keys = {
        logical_name(scene_class=GAME_SCENES[game_key]): game_key for game_key in GAME_SCENES
    }
    with TraceReader(path=golden) as reader:
        recorded_game = reader.header[GAME_HEADER_FIELD]
    game_key = game_keys[recorded_game]
    (member,) = [
        member
        for member in workspace_members(project_root=PROJECT_ROOT)
        if golden.is_relative_to(member.replay_fixtures_directory)
    ]

    assert fixture_path(game_key=game_key) == golden
    assert GAME_SCENES[game_key].__module__.partition('.')[0] in member.import_packages
    assert recording_console_script(path=golden) in member.console_scripts


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
