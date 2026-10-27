"""scripts/record_scripted_session.py: our games' golden replay tables and its command.

The recorder itself is the engine's (glitchygames/replay/tools/scripted_sessions.py, tested on
stand-ins in tests/replay/tools/test_scripted_sessions.py). These tests check this repository's
policy around it: where each game's golden goes, which console script replays it, that each game
has a controls tail, and that the script gives the engine each game's policy.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts import record_scripted_session
from scripts.record_golden_traces import GAME_MODULES, GAME_SCENES, PROJECT_ROOT, SCRIPT_BUILDERS
from scripts.record_scripted_session import (
    CONTROLS_TAIL_BUILDERS,
    GAME_CONSOLE_SCRIPTS,
    INPUT_ONLY_PLACEMENT_GAMES,
    POLLED_INPUT_GAMES,
    REPLAY_FIXTURE_DIRECTORIES,
    fixture_path,
    record_golden_session,
)
from scripts.workspace_packages import declared_console_scripts, workspace_members

from glitchygames.replay.tools.golden_traces import RANDOM_SEED, GoldenTraceSceneManager
from glitchygames.replay.tools.scripted_sessions import ScriptedInputSupervisor

# The Clockwork Keep script places the player on an elevator before this frame
CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME = 330


def test_every_game_has_a_fixture_location():
    """Every scripted game has a console script and its fixtures in its workspace member."""
    assert sorted(GAME_CONSOLE_SCRIPTS) == sorted(SCRIPT_BUILDERS)
    assert sorted(REPLAY_FIXTURE_DIRECTORIES) == sorted(SCRIPT_BUILDERS)


def test_a_game_no_member_holds_has_no_fixture_location():
    """No game is left in the root layout: a game outside every member is refused, by name."""
    with pytest.raises(KeyError, match='no_such_game'):
        fixture_path(game_key='no_such_game')


def test_each_fixture_directory_is_the_games_console_script_in_pyproject():
    """The mapping follows the members' [project.scripts].

    Each game's console script is its workspace member's, its entry point in one of the
    member's packages (Brave Adventurer's launcher, brave_adventurer_modes, starts both its
    games).
    """
    console_scripts = declared_console_scripts(project_root=PROJECT_ROOT)
    members = workspace_members(project_root=PROJECT_ROOT)
    for game_key, console_script in GAME_CONSOLE_SCRIPTS.items():
        entry_point_module = console_scripts[console_script].split(':')[0]
        game_module = GAME_MODULES[game_key]
        (member,) = [
            member for member in members if game_module.partition('.')[0] in member.import_packages
        ]
        assert entry_point_module.partition('.')[0] in member.import_packages, game_key
        assert REPLAY_FIXTURE_DIRECTORIES[game_key] == member.replay_fixtures_directory


def test_both_brave_adventurer_games_are_replayed_by_the_launcher():
    """One console script for the member's two games (its goldens are named apart)."""
    assert GAME_CONSOLE_SCRIPTS['brave_adventurer'] == 'brave-adventurer'
    assert GAME_CONSOLE_SCRIPTS['brave_adventurer_papyrus'] == 'brave-adventurer'
    assert declared_console_scripts(project_root=PROJECT_ROOT)['brave-adventurer'] == (
        'brave_adventurer_modes:main'
    )


@pytest.mark.parametrize(
    ('game_key', 'member_directory'),
    [
        ('mr_muncher', 'mr-muncher'),
        ('clockwork_keep', 'clockwork-keep'),
        ('paddleslap', 'paddleslap'),
        ('drawing_fire', 'drawing-fire'),
    ],
)
def test_a_member_games_fixture_is_directly_in_the_members_replay_fixtures(
    game_key, member_directory
):
    """A game in a workspace member records into <member>/tests/fixtures/replays/<name>.jsonl.gz."""
    path = fixture_path(game_key=game_key, name='golden')

    assert path.relative_to(PROJECT_ROOT).as_posix() == (
        f'src/games/{member_directory}/tests/fixtures/replays/golden.jsonl.gz'
    )
    assert path.is_file()


@pytest.mark.parametrize(
    ('game_key', 'golden'),
    [('brave_adventurer', 'golden-classic'), ('brave_adventurer_papyrus', 'golden-papyrus')],
)
def test_the_games_of_a_member_with_several_name_their_goldens_apart(game_key, golden):
    """Brave Adventurer's two games share their member's fixtures: golden-<game>.jsonl.gz."""
    path = fixture_path(game_key=game_key)

    assert path.relative_to(PROJECT_ROOT).as_posix() == (
        f'src/games/brave-adventurer/tests/fixtures/replays/{golden}.jsonl.gz'
    )
    assert path.is_file()


def test_every_game_has_a_controls_tail():
    """Every scripted game's golden replay ends with its controls tail (and its quit)."""
    assert sorted(CONTROLS_TAIL_BUILDERS) == sorted(SCRIPT_BUILDERS)


def test_clockwork_keeps_script_places_sprites_and_is_recorded_before_them():
    """Clockwork Keep's first placement is before frame 330: its golden stops there."""
    manager = GoldenTraceSceneManager.install()
    try:
        with pytest.raises(ValueError, match='places sprites directly at frame 330'):
            ScriptedInputSupervisor(
                script=SCRIPT_BUILDERS['clockwork_keep'](),
                frame_count=CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME + 1,
                scene_manager=manager,
            )
        assert (
            ScriptedInputSupervisor(
                script=SCRIPT_BUILDERS['clockwork_keep'](),
                frame_count=CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME,
                scene_manager=manager,
            ).frame_count
            == CLOCKWORK_KEEP_FIRST_PLACEMENT_FRAME
        )
    finally:
        GoldenTraceSceneManager.uninstall()


@pytest.mark.parametrize('game_key', sorted(SCRIPT_BUILDERS))
@pytest.mark.parametrize('exercise_controls', [True, False], ids=['golden', 'script-only'])
def test_a_golden_session_gives_the_engine_the_games_policy(mocker, game_key, exercise_controls):
    """The game's scene, script, tail, flags and our goldens' seed reach the engine's recorder."""
    recorder = mocker.patch.object(record_scripted_session, 'record_scripted_session')
    path = Path('golden.jsonl.gz')

    record_golden_session(
        game_key=game_key, frame_count=5, path=path, exercise_controls=exercise_controls
    )

    (call,) = recorder.call_args_list
    assert call.kwargs['scene_class'] is GAME_SCENES[game_key]
    assert call.kwargs['frame_count'] == 5
    assert call.kwargs['path'] == path
    assert (call.kwargs['controls_tail'] is not None) is exercise_controls
    assert call.kwargs['polled_input'] is (game_key in POLLED_INPUT_GAMES)
    assert call.kwargs['input_only_placements'] is (game_key in INPUT_ONLY_PLACEMENT_GAMES)
    assert call.kwargs['random_seed'] == RANDOM_SEED
