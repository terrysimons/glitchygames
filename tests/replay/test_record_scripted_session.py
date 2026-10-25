"""scripts/record_scripted_session.py records a golden input script through the real engine."""

from __future__ import annotations

import pygame
import pytest
from scripts.record_golden_traces import (
    GAME_MODULES,
    PROJECT_ROOT,
    SCRIPT_BUILDERS,
    GoldenTraceSceneManager,
    InputScript,
    press,
    release,
)
from scripts.record_scripted_session import (
    CONSOLE_SCRIPT_GAME_KEYS,
    CONTROLS_TAIL_BUILDERS,
    QUIT_WAIT_FRAMES,
    GameDidNotQuitError,
    ScriptedInputSupervisor,
    fixture_path,
    record_scripted_session,
)
from scripts.workspace_packages import declared_console_scripts

from glitchygames.exit_codes import ExitCode
from glitchygames.recording import EVENT_BATCHES_FIELD, EXTERNAL_ORIGIN
from glitchygames.tracing import read_trace_result
from tests.replay.replay_helpers import replay_through_engine

# Long enough for both PaddleSlap paddles to start tracking a served ball
RECORDED_FRAME_COUNT = 120
# The Clockwork Keep script places the player on an elevator before this frame
CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME = 330


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


@pytest.mark.frames_vary(
    reason='the session runs the real frame loop: each frame moves by its measured frame time'
)
def test_scripted_session_records_and_replays(mocker, tmp_path):
    """A PaddleSlap session records its frames and external key events, then replays exactly."""
    path = tmp_path / 'rally.jsonl.gz'
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')

    record_scripted_session(
        game_key='paddleslap',
        frame_count=RECORDED_FRAME_COUNT,
        path=path,
        exercise_controls=False,
    )

    frames = read_trace_result(path=path).trace['frames']
    assert [frame['frame'] for frame in frames] == list(range(RECORDED_FRAME_COUNT))
    # The paddles were steered by key events the pump returned as external (a player's keys)
    key_events = [event for frame in frames for event in recorded_key_events(frame=frame)]
    assert key_events
    assert {origin for _type, _key, origin in key_events} == {EXTERNAL_ORIGIN}

    replay = replay_through_engine(mocker=mocker, game_key='paddleslap', path=path)

    assert replay.exit_status == ExitCode.SUCCESS, replay.result.divergence
    assert replay.result.end_reason == 'end_of_recording'
    assert replay.result.frames_replayed == RECORDED_FRAME_COUNT


def test_games_with_sprite_placements_are_refused(scene_manager):
    """A session that would run a frame a sprite placement precedes is refused."""
    with pytest.raises(ValueError, match='places sprites directly'):
        ScriptedInputSupervisor(
            script=SCRIPT_BUILDERS['clockwork_keep'](),
            game_key='clockwork_keep',
            frame_count=CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME + 1,
            scene_manager=scene_manager,
        )


def test_placements_after_the_last_recorded_frame_are_allowed(scene_manager):
    """A session that ends before the first placement records only input."""
    supervisor = ScriptedInputSupervisor(
        script=SCRIPT_BUILDERS['clockwork_keep'](),
        game_key='clockwork_keep',
        frame_count=CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME,
        scene_manager=scene_manager,
    )

    assert supervisor.frame_count == CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME


def test_input_before_the_first_frame_is_refused(scene_manager):
    """No supervisor slot precedes frame 0, so input scheduled for it is refused."""
    script = InputScript()
    script.at(0, press(pygame.K_RIGHT))

    with pytest.raises(ValueError, match='before frame 0'):
        ScriptedInputSupervisor(
            script=script, game_key='paddleslap', frame_count=10, scene_manager=scene_manager
        )


def test_the_supervisor_posts_the_next_frames_input_and_stops_the_last_frame(scene_manager):
    """Each slot posts the next frame's key events; the last frame's slot ends the run."""
    script = InputScript()
    script.tap(5, pygame.K_RIGHT, held_frames=2)
    supervisor = ScriptedInputSupervisor(
        script=script, game_key='paddleslap', frame_count=8, scene_manager=scene_manager
    )
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


def test_every_game_has_a_fixture_location():
    """Every scripted game maps to tests/fixtures/replays/<console-script>/."""
    assert sorted(CONSOLE_SCRIPT_GAME_KEYS.values()) == sorted(SCRIPT_BUILDERS)

    path = fixture_path(game_key='brave_adventurer_papyrus', name='golden')

    assert path.relative_to(PROJECT_ROOT).as_posix() == (
        'tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz'
    )


def test_each_fixture_directory_is_the_games_console_script_in_pyproject():
    """The mapping follows [project.scripts] (the root's and the members'): each in its module."""
    console_scripts = declared_console_scripts(project_root=PROJECT_ROOT)
    for console_script, game_key in CONSOLE_SCRIPT_GAME_KEYS.items():
        entry_point_module = console_scripts[console_script].split(':')[0]
        assert entry_point_module == GAME_MODULES[game_key]


def test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures():
    """A game in a workspace member records into <member>/tests/fixtures/replays/<name>.jsonl.gz."""
    path = fixture_path(game_key='mr_muncher', name='golden')

    assert path.relative_to(PROJECT_ROOT).as_posix() == (
        'src/games/mr-muncher/tests/fixtures/replays/golden.jsonl.gz'
    )


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


def test_every_game_has_a_controls_tail():
    """Every scripted game's golden replay ends with its controls tail (and its quit)."""
    assert sorted(CONTROLS_TAIL_BUILDERS) == sorted(SCRIPT_BUILDERS)


def test_the_controls_tail_releases_held_keys_then_plays_and_never_ends_the_run(scene_manager):
    """After the script's frames: held keys are released, then the tail's input is posted."""
    script = InputScript()
    script.at(1, press(pygame.K_RIGHT), press(pygame.K_LEFT))
    script.at(2, release(pygame.K_LEFT))
    tail = InputScript()
    tail.at(1, press(pygame.K_q))
    supervisor = ScriptedInputSupervisor(
        script=script,
        game_key='paddleslap',
        frame_count=3,
        scene_manager=scene_manager,
        controls_tail=tail,
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
        script=InputScript(),
        game_key='paddleslap',
        frame_count=1,
        scene_manager=scene_manager,
        controls_tail=tail,
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
            game_key='paddleslap',
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
    # X is no PaddleSlap control: nothing quits
    tail.at(2, press(pygame.K_x))
    mocker.patch.dict(CONTROLS_TAIL_BUILDERS, {'paddleslap': lambda: tail})
    path = tmp_path / 'never-quits.jsonl.gz'

    with pytest.raises(GameDidNotQuitError, match='still running'):
        record_scripted_session(
            game_key='paddleslap', frame_count=5, path=path, exercise_controls=True
        )

    frames = read_trace_result(path=path).trace['frames']
    # The script's 5 frames, the tail's frames 0 to 2 (its last input), QUIT_WAIT_FRAMES more,
    # and the frame whose slot ends the run
    assert len(frames) == 5 + 3 + QUIT_WAIT_FRAMES
