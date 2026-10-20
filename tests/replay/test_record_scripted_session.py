"""scripts/record_scripted_session.py records a golden input script through the real engine."""

from __future__ import annotations

import tomllib

import pygame
import pytest
from scripts.record_golden_traces import (
    PROJECT_ROOT,
    SCRIPT_BUILDERS,
    GoldenTraceSceneManager,
    InputScript,
    press,
)
from scripts.record_scripted_session import (
    CONSOLE_SCRIPT_GAME_KEYS,
    ScriptedInputSupervisor,
    fixture_path,
    record_scripted_session,
)

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


def test_scripted_session_records_and_replays(mocker, tmp_path):
    """A PaddleSlap session records its frames and external key events, then replays exactly."""
    path = tmp_path / 'rally.jsonl.gz'
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')

    record_scripted_session(game_key='paddleslap', frame_count=RECORDED_FRAME_COUNT, path=path)

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
    """The mapping follows [project.scripts]: each game's entry point is in its module."""
    with (PROJECT_ROOT / 'pyproject.toml').open('rb') as pyproject_file:
        console_scripts = tomllib.load(pyproject_file)['project']['scripts']
    for console_script, game_key in CONSOLE_SCRIPT_GAME_KEYS.items():
        entry_point_module = console_scripts[console_script].split(':')[0]
        assert entry_point_module == f'glitchygames.examples.{game_key}'
