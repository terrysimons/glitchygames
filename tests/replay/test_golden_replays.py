"""Checks on the golden replays in the workspace members' tests/fixtures/replays.

A fixture is ``<member>/tests/fixtures/replays/<name>.jsonl.gz``, recorded through the
real engine by scripts/record_scripted_session.py. Each fixture is itself a test item: the replay
plugin (glitchygames/testing/replays.py, registered by the engine's pytest11 entry point)
replays it headless through the game's console script entry point (``--replay-trace PATH
--headless``: GameEngine + SceneManager.start, not the golden harness) and fails with the
printed divergence report unless it exits ``ExitCode.SUCCESS``. The tests here check that the
fixtures exist, are in game directories, and that a replay through the engine really compares.

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

from glitchygames.exit_codes import ExitCode
from glitchygames.logical_names import logical_name
from glitchygames.recording import EVENT_BATCHES_FIELD, EXTERNAL_ORIGIN, INTERNAL_ORIGIN
from glitchygames.replay.driver import GAME_HEADER_FIELD, SPRITE_DIVERGENCE
from glitchygames.replay.tools.children import recording_console_script
from glitchygames.replay.tools.scripted_sessions import record_scripted_session
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
from tests.replay.replay_helpers import replay_through_engine, tamper_first_sprite_rect
from tests.stand_in_games import (
    member_recording_path,
    write_header_only_recording,
    write_stand_in_distribution,
)
from tests.stand_in_harness_games import SteeredPaddleScene, steered_paddle_script
from tests.workspace_expectations import (
    EXPECTED_GAME_CONSOLE_SCRIPTS,
    GAMES_LAYER,
    every_games_golden,
)

if TYPE_CHECKING:
    from pathlib import Path


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


def record_stand_in_golden(*, mocker, tmp_path: Path) -> Path:
    """Record a stand-in game's scripted session through the engine, as a golden replay is.

    The stand-in (``SteeredPaddleScene``, tests/stand_in_harness_games.py) draws its paddle on
    every frame, so the recording has a sprite on TAMPERED_FRAME and every frame after it, and
    moves a fixed step per frame, so it replays deterministically.

    Returns:
        The recording's path.

    """
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    path = tmp_path / f'golden{REPLAY_FIXTURE_SUFFIX}'
    record_scripted_session(
        scene_class=SteeredPaddleScene,
        script=steered_paddle_script(),
        frame_count=STAND_IN_GOLDEN_FRAMES,
        path=path,
    )
    frames = read_trace_result(path=path).trace['frames']
    assert all(frame['sprites'] for frame in frames[TAMPERED_FRAME:])
    return path


def test_a_tampered_golden_replay_is_reported_at_its_frame(mocker, capsys, tmp_path):
    """The golden replays really compare: a fixture moved by one pixel diverges there."""
    path = record_stand_in_golden(mocker=mocker, tmp_path=tmp_path)
    tampered_path = tmp_path / f'tampered{REPLAY_FIXTURE_SUFFIX}'
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    capsys.readouterr()

    replay = replay_through_engine(
        mocker=mocker, scene_class=SteeredPaddleScene, path=tampered_path
    )

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
    path = record_stand_in_golden(mocker=mocker, tmp_path=tmp_path)
    tampered_path = tmp_path / f'tampered{REPLAY_FIXTURE_SUFFIX}'
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    rebaselined_path = tmp_path / f'rebaselined{REPLAY_FIXTURE_SUFFIX}'
    capsys.readouterr()

    rebaseline = replay_through_engine(
        mocker=mocker,
        scene_class=SteeredPaddleScene,
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
    replay = replay_through_engine(
        mocker=mocker, scene_class=SteeredPaddleScene, path=rebaselined_path
    )
    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.SUCCESS, report
    assert replay.result.divergence is None


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
