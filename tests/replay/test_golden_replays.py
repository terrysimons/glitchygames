"""Every golden replay under tests/fixtures/replays replays through the real engine loop.

A fixture is ``tests/fixtures/replays/<console-script>/<name>.jsonl.gz``, recorded through the
real engine by scripts/record_scripted_session.py. Each is replayed with the normal
``--replay-trace`` startup path (GameEngine + SceneManager.start, not the golden harness) and must
match its recording on every frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest
from scripts.record_golden_traces import (
    GAME_SCENES,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
)
from scripts.record_scripted_session import (
    CONSOLE_SCRIPT_GAME_KEYS,
    REPLAY_FIXTURE_DIRECTORY,
    REPLAY_FIXTURE_SUFFIX,
)

from glitchygames.replay.driver import SPRITE_DIVERGENCE
from glitchygames.scenes import SceneManager
from glitchygames.tracing import read_trace_result
from tests.world.test_gameplay_replay import tamper_first_sprite_rect

if TYPE_CHECKING:
    from pathlib import Path

    from glitchygames.replay import ReplayResult

# The frame a tampered copy of a fixture first differs from the engine at
TAMPERED_FRAME = 10

REPLAY_FIXTURES = sorted(REPLAY_FIXTURE_DIRECTORY.glob(f'*/*{REPLAY_FIXTURE_SUFFIX}'))


def fixture_id(path: Path) -> str:
    """Name a fixture ``<console-script>/<name>`` for its test id.

    Args:
        path: The fixture's path.

    Returns:
        The test id.

    """
    return f'{path.parent.name}/{path.name.removesuffix(REPLAY_FIXTURE_SUFFIX)}'


def replay_through_engine(*, mocker, game_key: str, path: Path) -> ReplayResult:
    """Replay a recording headless through the real engine loop and return its result.

    The replay is started the normal way, with ``--replay-trace`` (GameEngine.__init__ installs
    the ReplaySources, GameEngine.start runs SceneManager.start). Frame pacing is switched off:
    it only sleeps (the replay's frame times come from the recording), so the replay runs as fast
    as it can instead of in real time. pygame is left initialized for later tests on the worker.

    Args:
        mocker: pytest-mock's fixture.
        game_key: The game (a key of GAME_SCENES).
        path: The recording.

    Returns:
        The replay's result, settled by GameEngine._shutdown.

    """
    mocker.patch.object(SceneManager, '_handle_frame_pacing')
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    GoldenTraceSceneManager.install()
    try:
        with command_line(['--log-level', 'warning', '--replay-trace', str(path)]):
            engine = GoldenTraceEngine(game=GAME_SCENES[game_key])
        engine.start()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()
    sources = engine.replay_sources
    assert sources is not None
    return sources.result


def test_the_fixture_directory_holds_golden_replays():
    """A missing fixture set fails here instead of collecting zero replay cases."""
    assert REPLAY_FIXTURES, (
        f'no {REPLAY_FIXTURE_SUFFIX} recordings under {REPLAY_FIXTURE_DIRECTORY}'
    )


def test_every_fixture_directory_is_a_game_console_script():
    """Each fixture directory names a game's console script (so the replay knows the game)."""
    unknown_directories = sorted(
        {path.parent.name for path in REPLAY_FIXTURES} - set(CONSOLE_SCRIPT_GAME_KEYS)
    )
    assert not unknown_directories


@pytest.mark.parametrize('path', REPLAY_FIXTURES, ids=fixture_id)
def test_golden_replay_matches_every_frame(mocker, path):
    """The fixture replays through the real loop to its end with no divergence."""
    recorded_frame_count = len(read_trace_result(path=path).trace['frames'])

    result = replay_through_engine(
        mocker=mocker, game_key=CONSOLE_SCRIPT_GAME_KEYS[path.parent.name], path=path
    )

    assert result.divergence is None, result.divergence
    assert result.end_reason == 'end_of_recording'
    assert result.frames_replayed == recorded_frame_count


def test_a_tampered_golden_replay_is_reported_at_its_frame(mocker, tmp_path):
    """The golden replays really compare: a fixture moved by one pixel diverges there."""
    path = REPLAY_FIXTURE_DIRECTORY / 'paddleslap' / f'golden{REPLAY_FIXTURE_SUFFIX}'
    tampered_path = tmp_path / path.name
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)

    result = replay_through_engine(mocker=mocker, game_key='paddleslap', path=tampered_path)

    assert result.divergence is not None
    assert result.divergence.frame_number == TAMPERED_FRAME
    assert result.divergence.kind == SPRITE_DIVERGENCE
    assert result.end_reason == 'diverged'
