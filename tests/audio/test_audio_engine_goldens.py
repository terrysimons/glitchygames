"""PaddleSlap's golden replay still matches under each sound cache mode.

A repository test (tests/test_suite_collection.py ``REPOSITORY_TEST_FILES``): it replays our
member's golden, found through the workspace (tests/workspace_goldens.py), headless in a child
(``replay_recording_headless``). ``--sound-cache`` is replay-local, so the recording replays under
whichever mode is given.
"""

from pathlib import Path

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.tools.children import recording_console_script, replay_recording_headless
from tests.workspace_goldens import every_games_golden

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GOLDEN_GAME = 'paddleslap'


def paddleslap_golden() -> Path:
    """PaddleSlap's golden replay, from the workspace.

    Returns:
        Its path.
    """
    (golden,) = [
        path
        for path in every_games_golden(project_root=PROJECT_ROOT)
        if recording_console_script(path=path) == GOLDEN_GAME
    ]
    return golden


@pytest.mark.parametrize('cache_mode', ['none', 'ram'])
def test_golden_replay_still_matches_under_each_cache_mode(cache_mode):
    """Both M1 cache modes replay the golden exactly."""
    replayed = replay_recording_headless(
        console_script=GOLDEN_GAME,
        path=paddleslap_golden(),
        game_arguments=('--sound-cache', cache_mode),
    )

    assert replayed.returncode == ExitCode.SUCCESS, replayed.stdout


def test_the_cache_mode_reaches_the_replayed_game():
    """The disk mode, refused until M3, is refused in the replay: the option reached the game."""
    replayed = replay_recording_headless(
        console_script=GOLDEN_GAME,
        path=paddleslap_golden(),
        game_arguments=('--sound-cache', 'disk'),
    )

    assert replayed.returncode == ExitCode.OPTIONS_REFUSED, replayed.stdout
    assert 'arrives in M3' in replayed.stdout
