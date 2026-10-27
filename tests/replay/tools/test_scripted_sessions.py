"""The scripted-session recorder (glitchygames/replay/tools/scripted_sessions.py) and its tool.

The recorder runs a game by its scene class, an input script and flags, so every test here runs
a stand-in game (tests/stand_in_harness_games.py in this process; the installed stand-in game of
tests/stand_in_games.py in child processes). The ``record-session`` tool is run end to end
through both front ends: as the game's own flag and as the ``glitchygames`` command, with the
input script and controls tail in the stand-in's own project, and each recording replays
``SUCCESS`` through ``--replay-trace --headless``.

Moved here with the recorder (Part 3, Stage D, Task D4b) from
tests/replay/test_record_scripted_session.py, whose tests of our games' tables stay there.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import live_sources
from glitchygames.events import GAMEEVENT
from glitchygames.exit_codes import ExitCode
from glitchygames.input.state import IDLE_INPUT
from glitchygames.process import run_command
from glitchygames.recording import EVENT_BATCHES_FIELD, EXTERNAL_ORIGIN, post_event
from glitchygames.replay.tools import command, scripted_sessions
from glitchygames.replay.tools.golden_traces import (
    RANDOM_SEED,
    GoldenTraceSceneManager,
    InputScript,
    press,
    release,
)
from glitchygames.replay.tools.registry import run_game_flag_tool
from glitchygames.replay.tools.scripted_sessions import (
    QUIT_WAIT_FRAMES,
    GameDidNotQuitError,
    PostedPolledInput,
    ScriptedInputSupervisor,
    clear_events_left_queued,
    polled_input_follows,
    record_scripted_session,
)
from glitchygames.tracing import read_trace_result
from tests.replay.replay_helpers import replay_through_engine
from tests.stand_in_games import (
    RECORD_TIMEOUT_SECONDS,
    STAND_IN_GAME_RESOLUTION,
    StandInGame,
    use_stand_in_game,
    write_stand_in_game,
)
from tests.stand_in_harness_games import SteeredPaddleScene, steered_paddle_script

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

# Long enough for the steered paddle's whole script (its last key is released before frame 60);
# PaddleSlap's session was this long too, for both its paddles to start tracking a served ball
RECORDED_FRAME_COUNT = 120
# A script whose first placement runs before this frame
FIRST_PLACEMENT_FRAME = 30
# A subtype no game posts: the stale event a previous test left in the queue
STALE_EVENT_SUBTYPE = 9999

# The stand-in project's input scripts: a module in the project's root, run from there. The
# session's script presses and releases the right arrow (which the stand-in game ignores: it
# still records them as a player's keys); its controls tail presses and releases Q, which ends
# the stand-in game (the base scene quits on Q's release)
STAND_IN_INPUTS_MODULE = 'stand_in_session_inputs'
STAND_IN_SESSION_SCRIPT = f'{STAND_IN_INPUTS_MODULE}:session_script'
STAND_IN_CONTROLS_TAIL = f'{STAND_IN_INPUTS_MODULE}:quit_tail'
STAND_IN_INPUTS_SOURCE = '''\
"""The stand-in project's session input (tests/replay/tools/test_scripted_sessions.py)."""

import pygame

from glitchygames.replay.tools.golden_traces import InputScript, press, release


def session_script():
    """Return the stand-in game's session script: the right arrow, pressed then released."""
    script = InputScript()
    script.at(2, press(pygame.K_RIGHT))
    script.at(5, release(pygame.K_RIGHT))
    return script


def quit_tail():
    """Return the stand-in game's controls tail: Q, which quits it."""
    tail = InputScript()
    tail.at(2, press(pygame.K_q))
    tail.at(4, release(pygame.K_q))
    return tail


def placing_script():
    """Return a script that places the mover inside the session."""
    script = InputScript()
    script.place(3, lambda scene: None)
    return script
'''
# The session's script frames: fewer than the stand-in runs before it quits itself
SESSION_FRAME_COUNT = 8
# The stand-in game for the tool runs quits itself only after this many frames, so the
# controls tail's Q is what ends it
STAND_IN_SESSION_GAME_FRAMES = 200
# What the engine logs when it is built after pygame was started: a second engine would
WARNING_OF_A_SECOND_ENGINE = 'pygame was initialized before the engine'
# What the engine logs once per engine it builds (print_game_info)
ONE_LINE_PER_ENGINE = 'Game Title: '


@pytest.fixture
def scene_manager():
    """A fresh SceneManager singleton, cleared afterwards with the event queue.

    Yields:
        The scene manager.

    """
    manager = GoldenTraceSceneManager.install()
    try:
        yield manager
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Its facts: one console script (``stand-in-rally``) in package ``stand_in_rally``, one scene
    whose mover is a sprite on every frame, seeded and deterministic, no input of its own (the
    base scene's quit keys end it); here it quits itself only after
    ``STAND_IN_SESSION_GAME_FRAMES`` frames.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(
        directory=install_directory, frames_before_quit=STAND_IN_SESSION_GAME_FRAMES
    )
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


@pytest.fixture
def stand_in_project(tmp_path, monkeypatch) -> Generator[Path]:
    """Write the stand-in project's input script module; forget it again afterwards.

    Yields:
        The project's directory (the module is in its root).

    """
    project = tmp_path / 'project'
    project.mkdir()
    (project / f'{STAND_IN_INPUTS_MODULE}.py').write_text(STAND_IN_INPUTS_SOURCE, encoding='utf-8')
    monkeypatch.delitem(sys.modules, STAND_IN_INPUTS_MODULE, raising=False)
    yield project
    sys.modules.pop(STAND_IN_INPUTS_MODULE, None)


def recorded_key_events(*, frame: dict) -> list[tuple[int, int, str]]:
    """Return a recorded frame's key events as (type, key, origin).

    Returns:
        The key events of every batch the frame pumped, in order.

    """
    return [
        (record['type'], record['attributes']['key'], record['origin'])
        for batch in frame.get(EVENT_BATCHES_FIELD, [])
        for record in batch
        if record['type'] in {pygame.KEYDOWN, pygame.KEYUP}
    ]


def run_stand_in_game(
    *, game: StandInGame, arguments: list[str], working_directory: Path
) -> tuple[int, str]:
    """Run the stand-in game in a child, its log at info level, headless.

    Returns:
        The child's exit status and its output (standard output and error together).

    """
    completed = run_command(
        command=[
            sys.executable,
            '-c',
            f'import {game.package}; {game.package}.main()',
            '--log-level',
            'info',
            '--resolution',
            STAND_IN_GAME_RESOLUTION,
            '--headless',
            *arguments,
        ],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=working_directory,
    )
    return completed.returncode, completed.stdout or ''


@pytest.mark.frames_vary(
    reason='the session runs the real frame loop: each frame moves by its measured frame time'
)
def test_scripted_session_records_and_replays(mocker, tmp_path):
    """A stand-in session records its frames and external key events, then replays exactly.

    The stand-in (``SteeredPaddleScene``) reads key events, polls no input, places no sprite and
    moves a fixed step per frame, so its replay is deterministic.
    """
    path = tmp_path / 'rally.jsonl.gz'
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')

    record_scripted_session(
        scene_class=SteeredPaddleScene,
        script=steered_paddle_script(),
        frame_count=RECORDED_FRAME_COUNT,
        path=path,
    )

    frames = read_trace_result(path=path).trace['frames']
    assert [frame['frame'] for frame in frames] == list(range(RECORDED_FRAME_COUNT))
    # The paddle was steered by key events the pump returned as external (a player's keys)
    key_events = [event for frame in frames for event in recorded_key_events(frame=frame)]
    assert key_events
    assert {origin for _type, _key, origin in key_events} == {EXTERNAL_ORIGIN}
    # Without polled_input the snapshots never show the posted keys held
    assert not any('pressed_scancodes' in frame.get('input_changes', {}) for frame in frames)

    replay = replay_through_engine(mocker=mocker, scene_class=SteeredPaddleScene, path=path)

    assert replay.exit_status == ExitCode.SUCCESS, replay.result.divergence
    assert replay.result.end_reason == 'end_of_recording'
    assert replay.result.frames_replayed == RECORDED_FRAME_COUNT


@pytest.mark.frames_vary(
    reason='the session runs the real frame loop: each frame moves by its measured frame time'
)
def test_a_polled_input_session_shows_the_posted_keys_held(mocker, tmp_path):
    """With polled_input the session's snapshots show the script's keys held, as a player's."""
    path = tmp_path / 'polled.jsonl.gz'
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')

    record_scripted_session(
        scene_class=SteeredPaddleScene,
        script=steered_paddle_script(),
        frame_count=RECORDED_FRAME_COUNT,
        path=path,
        polled_input=True,
        random_seed=RANDOM_SEED,
    )

    frames = read_trace_result(path=path).trace['frames']
    assert any('pressed_scancodes' in frame.get('input_changes', {}) for frame in frames)
    assert read_trace_result(path=path).trace['random_seed'] == RANDOM_SEED
    # The live doors' capture is put back afterwards
    assert live_sources.capture_live_snapshot.__name__ == 'capture_live_snapshot'


@pytest.mark.frames_vary(
    reason='the session runs the real frame loop: each frame moves by its measured frame time'
)
def test_a_session_drops_events_left_queued_before_it(mocker, tmp_path):
    """An internal event a caller left queued is never recorded as the session's own.

    The stand-in (``SteeredPaddleScene``) posts no event of its own, so none of subtype
    STALE_EVENT_SUBTYPE can come from it.
    """
    path = tmp_path / 'stale.jsonl.gz'
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    # What an earlier test's scene left behind: a game event it posted and never pumped
    post_event(pygame.event.Event(GAMEEVENT, {'subtype': STALE_EVENT_SUBTYPE}))

    record_scripted_session(
        scene_class=SteeredPaddleScene, script=steered_paddle_script(), frame_count=5, path=path
    )

    frames = read_trace_result(path=path).trace['frames']
    recorded_subtypes = [
        record['attributes'].get('subtype')
        for frame in frames
        for batch in frame.get(EVENT_BATCHES_FIELD, [])
        for record in batch
        if record['type'] == GAMEEVENT
    ]
    assert STALE_EVENT_SUBTYPE not in recorded_subtypes


def placing_script() -> InputScript:
    """Return a script with one placement, before FIRST_PLACEMENT_FRAME.

    Returns:
        The input script.

    """
    script = InputScript()
    script.place(FIRST_PLACEMENT_FRAME, lambda _scene: None)
    return script


def test_a_script_that_places_sprites_inside_the_session_is_refused(scene_manager):
    """A session that would run a frame a sprite placement precedes is refused."""
    with pytest.raises(ValueError, match='places sprites directly at frame 30'):
        ScriptedInputSupervisor(
            script=placing_script(),
            frame_count=FIRST_PLACEMENT_FRAME + 1,
            scene_manager=scene_manager,
        )


def test_placements_after_the_last_recorded_frame_are_allowed(scene_manager):
    """A session that ends before the first placement records only input."""
    supervisor = ScriptedInputSupervisor(
        script=placing_script(), frame_count=FIRST_PLACEMENT_FRAME, scene_manager=scene_manager
    )

    assert supervisor.frame_count == FIRST_PLACEMENT_FRAME


def test_input_only_placements_may_run_inside_the_session(scene_manager):
    """Placements that only steer the script's own input are allowed inside the session."""
    supervisor = ScriptedInputSupervisor(
        script=placing_script(),
        frame_count=FIRST_PLACEMENT_FRAME + 1,
        scene_manager=scene_manager,
        input_only_placements=True,
    )

    assert supervisor.frame_count == FIRST_PLACEMENT_FRAME + 1


def test_input_before_the_first_frame_is_refused(scene_manager):
    """No supervisor slot precedes frame 0, so input scheduled for it is refused."""
    script = InputScript()
    script.at(0, press(pygame.K_RIGHT))

    with pytest.raises(ValueError, match='before frame 0'):
        ScriptedInputSupervisor(script=script, frame_count=10, scene_manager=scene_manager)


def test_the_supervisor_posts_the_next_frames_input_and_stops_the_last_frame(scene_manager):
    """Each slot posts the next frame's key events; the last frame's slot ends the run."""
    script = InputScript()
    script.tap(5, pygame.K_RIGHT, held_frames=2)
    supervisor = ScriptedInputSupervisor(script=script, frame_count=8, scene_manager=scene_manager)
    pygame.event.clear()

    posted_by_frame = {}
    for frame_number in range(8):
        supervisor.on_frame(frame_number=frame_number, scene=None)
        posted_by_frame[frame_number + 1] = [
            (event.type, event.key)
            for event in pygame.event.get()
            if event.type in {pygame.KEYDOWN, pygame.KEYUP}
        ]
        assert scene_manager.quit_requested is (frame_number == 7)

    assert posted_by_frame[5] == [(pygame.KEYDOWN, pygame.K_RIGHT)]
    assert posted_by_frame[7] == [(pygame.KEYUP, pygame.K_RIGHT)]
    assert all(not posted_by_frame[frame] for frame in posted_by_frame if frame not in {5, 7})


def posted_key_events() -> list[tuple[int, int]]:
    """Drain the queue and return the key events in it as (type, key).

    Returns:
        The key events, in order.

    """
    return [
        (event.type, event.key)
        for event in pygame.event.get()
        if event.type in {pygame.KEYDOWN, pygame.KEYUP}
    ]


def test_the_controls_tail_releases_held_keys_then_plays_and_never_ends_the_run(scene_manager):
    """After the script's frames: held keys are released, then the tail's input is posted."""
    script = InputScript()
    script.at(1, press(pygame.K_RIGHT), press(pygame.K_LEFT))
    script.at(2, release(pygame.K_LEFT))
    tail = InputScript()
    tail.at(1, press(pygame.K_q))
    supervisor = ScriptedInputSupervisor(
        script=script, frame_count=3, scene_manager=scene_manager, controls_tail=tail
    )
    pygame.event.clear()

    posted_by_frame = {}
    for frame_number in range(6):
        supervisor.on_frame(frame_number=frame_number, scene=None)
        posted_by_frame[frame_number + 1] = posted_key_events()

    # The game, not the supervisor, ends the run
    assert scene_manager.quit_requested is False
    assert supervisor.game_did_not_quit is False
    assert posted_by_frame[2] == [(pygame.KEYUP, pygame.K_LEFT)]
    # Tail frame 0 is frame 3: RIGHT was still held
    assert posted_by_frame[3] == [(pygame.KEYUP, pygame.K_RIGHT)]
    assert posted_by_frame[4] == [(pygame.KEYDOWN, pygame.K_q)]
    assert not posted_by_frame[5]
    assert not posted_by_frame[6]


def test_a_game_still_running_after_its_tail_is_stopped_and_flagged(scene_manager):
    """QUIT_WAIT_FRAMES after the tail's last input, the supervisor ends the run itself."""
    tail = InputScript()
    tail.at(1, press(pygame.K_q))
    supervisor = ScriptedInputSupervisor(
        script=InputScript(), frame_count=1, scene_manager=scene_manager, controls_tail=tail
    )

    # Tail frame N is posted at the slot of frame N (frame_count 1); the last input is at tail
    # frame 1, so the slot posting tail frame 1 + QUIT_WAIT_FRAMES + 1 ends the run
    last_waiting_frame = 1 + QUIT_WAIT_FRAMES
    for frame_number in range(last_waiting_frame + 1):
        supervisor.on_frame(frame_number=frame_number, scene=None)
    assert scene_manager.quit_requested is False
    supervisor.on_frame(frame_number=last_waiting_frame + 1, scene=None)

    assert scene_manager.quit_requested is True
    assert supervisor.game_did_not_quit is True
    pygame.event.clear()


def test_a_controls_tail_without_key_events_is_refused(scene_manager):
    """A tail is key events only (it is input), and it must hold some (its quit)."""
    with pytest.raises(ValueError, match='controls tail'):
        ScriptedInputSupervisor(
            script=InputScript(),
            frame_count=10,
            scene_manager=scene_manager,
            controls_tail=InputScript(),
        )


@pytest.mark.frames_vary(
    reason='the session runs the real frame loop: each frame moves by its measured frame time'
)
def test_a_tail_whose_quit_does_not_quit_fails_the_recording(mocker, tmp_path):
    """A controls tail that never ends the game raises GameDidNotQuitError after recording."""
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    tail = InputScript()
    # X is no control of the stand-in (its controls are the arrows, its quit keys Q and ESC):
    # nothing quits
    tail.at(2, press(pygame.K_x))
    path = tmp_path / 'never-quits.jsonl.gz'

    with pytest.raises(GameDidNotQuitError, match='still running'):
        record_scripted_session(
            scene_class=SteeredPaddleScene,
            script=steered_paddle_script(),
            frame_count=5,
            path=path,
            controls_tail=tail,
        )

    frames = read_trace_result(path=path).trace['frames']
    # The script's 5 frames, the tail's frames 0 to 2 (its last input), QUIT_WAIT_FRAMES more,
    # and the frame whose slot ends the run
    assert len(frames) == 5 + 3 + QUIT_WAIT_FRAMES


def mouse_button_event(event_type: int, *, button: int) -> pygame.event.Event:
    """Build a mouse button press or release at the window's corner.

    Returns:
        The MOUSEBUTTONDOWN or MOUSEBUTTONUP event.

    """
    return pygame.event.Event(event_type, pos=(0, 0), button=button, touch=False)


def test_posted_input_holds_keys_and_the_mouse_until_released():
    """The posted press holds its scancode and button; the release lets go; the mouse stays."""
    posted_input = PostedPolledInput()
    posted_input.follow(press(pygame.K_a))
    posted_input.follow(
        pygame.event.Event(
            pygame.MOUSEMOTION, pos=(40, 50), rel=(40, 50), buttons=(0, 0, 0), touch=False
        )
    )
    posted_input.follow(mouse_button_event(pygame.MOUSEBUTTONDOWN, button=1))

    held = posted_input.overlay(IDLE_INPUT)

    assert held.pressed_scancodes == frozenset({pygame.KSCAN_A})
    assert held.mouse_position == (40, 50)
    assert held.mouse_buttons == (True, False, False)

    posted_input.follow(release(pygame.K_a))
    posted_input.follow(mouse_button_event(pygame.MOUSEBUTTONUP, button=1))
    released = posted_input.overlay(IDLE_INPUT)

    assert released.pressed_scancodes == frozenset()
    assert released.mouse_position == (40, 50)
    assert released.mouse_buttons == (False, False, False)


def test_posted_input_leaves_the_live_snapshot_alone_where_nothing_was_posted():
    """Unposted input is the live snapshot's: its keys, its mouse; wheel buttons change nothing."""
    posted_input = PostedPolledInput()
    # pygame's buttons 4 and 5 are the wheel, which the snapshot does not hold
    posted_input.follow(mouse_button_event(pygame.MOUSEBUTTONDOWN, button=4))
    live = dataclasses.replace(
        IDLE_INPUT,
        pressed_scancodes=frozenset({pygame.KSCAN_D}),
        mouse_position=(7, 9),
        mouse_buttons=(False, False, True),
    )

    assert posted_input.overlay(live) == live


def test_live_snapshots_show_the_posted_input_only_inside_the_scope():
    """polled_input_follows replaces the live doors' capture, then puts it back."""
    original_capture = live_sources.capture_live_snapshot
    posted_input = PostedPolledInput()
    posted_input.follow(press(pygame.K_RETURN))

    with polled_input_follows(posted_input):
        snapshot = live_sources.capture_live_snapshot()

    assert pygame.KSCAN_RETURN in snapshot.pressed_scancodes
    assert live_sources.capture_live_snapshot is original_capture


def test_the_supervisor_places_and_posts_per_frame_input_on_the_active_scene(scene_manager):
    """With a scene, the slot runs the next frame's placements and posts its per-frame input."""
    scene = SteeredPaddleScene(options={})
    placed_on: list[object] = []
    motion = pygame.event.Event(
        pygame.MOUSEMOTION, pos=(12, 34), rel=(0, 0), buttons=(0, 0, 0), touch=False
    )
    script = InputScript(per_frame=lambda _scene: [motion])
    script.place(2, placed_on.append)
    supervisor = ScriptedInputSupervisor(
        script=script, frame_count=5, scene_manager=scene_manager, input_only_placements=True
    )
    pygame.event.clear()

    supervisor.on_frame(frame_number=1, scene=scene)

    assert placed_on == [scene]
    assert [event.type for event in pygame.event.get()] == [pygame.MOUSEMOTION]
    assert supervisor.posted_input.mouse_position == (12, 34)
    # A mouse motion holds no key
    assert supervisor.held_keys == set()


def test_posted_input_ignores_events_that_change_no_polled_input():
    """An event that is no key, mouse motion or mouse button changes nothing polled."""
    posted_input = PostedPolledInput()

    posted_input.follow(pygame.event.Event(pygame.JOYBUTTONDOWN, instance_id=0, button=1))

    assert posted_input.overlay(IDLE_INPUT) == IDLE_INPUT


def test_queued_events_are_cleared_only_while_the_display_runs(mocker):
    """A queue is cleared while pygame's display runs; without one there is no queue to clear."""
    cleared = mocker.patch.object(pygame.event, 'clear')
    mocker.patch.object(pygame.display, 'get_init', return_value=False)

    clear_events_left_queued()

    cleared.assert_not_called()


def test_the_supervisor_follows_what_it_posts(scene_manager):
    """Every event the supervisor posts is noted in its polled input."""
    script = InputScript()
    script.at(1, press(pygame.K_LEFT))
    supervisor = ScriptedInputSupervisor(script=script, frame_count=3, scene_manager=scene_manager)

    supervisor.on_frame(frame_number=0, scene=None)

    assert supervisor.posted_input.held_scancodes == {pygame.KSCAN_LEFT}


def session_tool_arguments(*, controls_tail: bool = True) -> list[str]:
    """Return ``record-session``'s options for the stand-in project's session.

    Returns:
        The input script, frame count, controls tail (when asked for) and seed options.

    """
    return [
        '--input-script',
        STAND_IN_SESSION_SCRIPT,
        '--frame-count',
        str(SESSION_FRAME_COUNT),
        *(['--controls-tail', STAND_IN_CONTROLS_TAIL] if controls_tail else []),
        '--random-seed',
        str(RANDOM_SEED),
    ]


def test_record_session_on_a_stand_in_game_as_a_flag_and_a_command(
    stand_in_game, stand_in_project, tmp_path, capfd
):
    """``--record-session`` on the game and ``glitchygames record-session``: each replays clean.

    Each runs the stand-in game in a child in the stand-in's project, with the project's input
    script and controls tail: the recording holds the script's keys as a player's, ends with the
    QUIT the game posted on the tail's Q, names the seed given, and replays ``SUCCESS`` through
    ``--replay-trace --headless``. The flag builds one engine only: the harness's, with no
    warning that pygame was started before it.
    """
    flag_recording = tmp_path / 'flag.jsonl.gz'
    command_recording = tmp_path / 'command.jsonl.gz'

    flag_status, flag_output = run_stand_in_game(
        game=stand_in_game,
        arguments=['--record-session', str(flag_recording), *session_tool_arguments()],
        working_directory=stand_in_project,
    )
    command_status = command.main([
        'record-session',
        stand_in_game.console_script,
        str(command_recording),
        *session_tool_arguments(),
        '--headless',
        '--project-root',
        str(stand_in_project),
        '--',
        '--log-level',
        'error',
    ])

    errors = capfd.readouterr().err
    assert flag_status == ExitCode.SUCCESS, flag_output
    assert command_status == ExitCode.SUCCESS, errors
    assert (
        f'glitchygames record-session: running {stand_in_game.console_script} '
        '(an installed console script)'
    ) in errors
    assert WARNING_OF_A_SECOND_ENGINE not in flag_output
    assert flag_output.count(ONE_LINE_PER_ENGINE) == 1, flag_output
    for recording in (flag_recording, command_recording):
        trace = read_trace_result(path=recording).trace
        assert trace['random_seed'] == RANDOM_SEED
        key_events = [
            event for frame in trace['frames'] for event in recorded_key_events(frame=frame)
        ]
        assert (pygame.KEYDOWN, pygame.K_RIGHT, EXTERNAL_ORIGIN) in key_events
        assert (pygame.KEYUP, pygame.K_q, EXTERNAL_ORIGIN) in key_events
        # Ended by the game's own QUIT, long before the stand-in would quit itself
        assert len(trace['frames']) < STAND_IN_SESSION_GAME_FRAMES
        replay_status, replay_output = run_stand_in_game(
            game=stand_in_game,
            arguments=['--replay-trace', str(recording)],
            working_directory=stand_in_project,
        )
        assert replay_status == ExitCode.SUCCESS, replay_output


def test_record_session_without_a_tail_ends_after_the_scripts_frames(
    stand_in_game, stand_in_project, tmp_path
):
    """Without ``--controls-tail`` the session holds the script's frames and no quit."""
    recording = tmp_path / 'script-only.jsonl.gz'

    status, output = run_stand_in_game(
        game=stand_in_game,
        arguments=[
            '--record-session',
            str(recording),
            *session_tool_arguments(controls_tail=False),
            '--polled-input',
        ],
        working_directory=stand_in_project,
    )

    assert status == ExitCode.SUCCESS, output
    assert len(read_trace_result(path=recording).trace['frames']) == SESSION_FRAME_COUNT


def session_options(*, path: Path, **given: object) -> dict[str, object]:
    """Return a game's parsed options with ``--record-session`` given.

    Returns:
        The options ``run_game_flag_tool`` reads.

    """
    return {
        'record_session': str(path),
        'input_script': STAND_IN_SESSION_SCRIPT,
        'frame_count': SESSION_FRAME_COUNT,
        'controls_tail': None,
        'polled_input': False,
        'input_only_placements': False,
        'random_seed': None,
        **given,
    }


@pytest.fixture
def in_stand_in_project(stand_in_project, monkeypatch) -> Path:
    """Run the test in the stand-in project's directory, where its input scripts are found.

    Returns:
        The project's directory.

    """
    monkeypatch.chdir(stand_in_project)
    return stand_in_project


@pytest.mark.parametrize(
    ('given', 'logged'),
    [
        ({'input_script': f'{STAND_IN_INPUTS_MODULE}:nothing'}, 'nothing'),
        ({'controls_tail': f'{STAND_IN_INPUTS_MODULE}:nothing'}, 'nothing'),
        (
            {'input_script': f'{STAND_IN_INPUTS_MODULE}:placing_script'},
            'places sprites directly',
        ),
    ],
    ids=['no-input-script', 'no-controls-tail', 'a-placement-inside'],
)
@pytest.mark.usefixtures('in_stand_in_project')
def test_a_session_that_cannot_be_recorded_is_refused_and_nothing_runs(
    tmp_path, mocker, caplog, given, logged
):
    """An input script or tail that names none, or a placement inside the session: refused."""
    path = tmp_path / 'session.jsonl.gz'
    # Refused before any engine is built (no window opens for a session that can't be recorded)
    built = mocker.patch.object(scripted_sessions, 'GoldenTraceEngine')

    result = run_game_flag_tool(
        options=session_options(path=path, **given), game=SteeredPaddleScene
    )

    assert result == ExitCode.OPTIONS_REFUSED
    assert logged in caplog.text
    built.assert_not_called()
    assert not path.exists()


class SceneWithAnUnusableTargetFps(SteeredPaddleScene):
    """A game whose own code is wrong: its TARGET_FPS is negative (a ValueError)."""

    TARGET_FPS = -1


@pytest.mark.usefixtures('in_stand_in_project')
def test_the_games_own_errors_keep_their_own_exit(tmp_path):
    """A ValueError from the game itself is not an option refusal: it reaches the crash boundary.

    Only the session's own checks (the input scripts, the placements, the recording's
    directory) are refused or reported as unwritable; the game's errors propagate, so the engine
    ends the run INTERNAL_ERROR as for any game.
    """
    with pytest.raises(ValueError, match='TARGET_FPS'):
        run_game_flag_tool(
            options=session_options(path=tmp_path / 'session.jsonl.gz'),
            game=SceneWithAnUnusableTargetFps,
        )


@pytest.mark.usefixtures('in_stand_in_project')
def test_the_game_flag_gives_the_recorder_the_session_it_was_asked_for(tmp_path, mocker):
    """The tool's options reach the recorder: the scene class, scripts, flags and seed."""
    recorder = mocker.patch.object(scripted_sessions, 'record_scripted_session')
    path = tmp_path / 'session.jsonl.gz'

    result = run_game_flag_tool(
        options=session_options(
            path=path,
            controls_tail=STAND_IN_CONTROLS_TAIL,
            polled_input=True,
            input_only_placements=True,
            random_seed=RANDOM_SEED,
        ),
        game=SteeredPaddleScene(options={}),
    )

    assert result == ExitCode.SUCCESS
    (call,) = recorder.call_args_list
    assert call.kwargs['scene_class'] is SteeredPaddleScene
    assert call.kwargs['frame_count'] == SESSION_FRAME_COUNT
    assert call.kwargs['path'] == path
    assert call.kwargs['controls_tail'].key_events
    assert call.kwargs['polled_input'] is True
    assert call.kwargs['input_only_placements'] is True
    assert call.kwargs['random_seed'] == RANDOM_SEED


@pytest.mark.usefixtures('in_stand_in_project')
def test_a_tail_that_does_not_quit_the_game_is_unusable_input(tmp_path, mocker, caplog):
    """The tool's controls tail never quit the game: the recording does not end as it must."""
    mocker.patch(
        'glitchygames.replay.tools.scripted_sessions.record_scripted_session',
        side_effect=GameDidNotQuitError('still running'),
    )

    result = run_game_flag_tool(
        options=session_options(path=tmp_path / 'session.jsonl.gz'), game=SteeredPaddleScene
    )

    assert result == ExitCode.UNUSABLE_INPUT
    assert 'still running' in caplog.text


@pytest.mark.usefixtures('in_stand_in_project')
def test_a_session_that_cannot_be_written_is_cannot_write_output(tmp_path, caplog):
    """A recording whose directory can't be made exits CANNOT_WRITE_OUTPUT, naming the path."""
    blocker = tmp_path / 'a-file'
    blocker.write_text('not a directory', encoding='utf-8')
    path = blocker / 'session.jsonl.gz'

    result = run_game_flag_tool(
        options=session_options(path=path), game=SteeredPaddleScene(options={})
    )

    assert result == ExitCode.CANNOT_WRITE_OUTPUT
    assert str(path) in caplog.text
