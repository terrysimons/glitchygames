"""Every golden replay under tests/fixtures/replays replays through the real engine loop.

A fixture is ``tests/fixtures/replays/<console-script>/<name>.jsonl.gz``, recorded through the
real engine by scripts/record_scripted_session.py. Each is replayed with the normal
``--replay-trace PATH --headless`` startup path (GameEngine + SceneManager.start, not the golden
harness), must match its recording on every frame and exit ``ExitCode.SUCCESS``; a failure shows
the printed divergence report.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from scripts.record_scripted_session import (
    CONSOLE_SCRIPT_GAME_KEYS,
    REPLAY_FIXTURE_DIRECTORY,
    REPLAY_FIXTURE_SUFFIX,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import SPRITE_DIVERGENCE
from glitchygames.tracing import read_trace_result
from tests.replay.replay_helpers import replay_through_engine, tamper_first_sprite_rect

if TYPE_CHECKING:
    from pathlib import Path

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
def test_golden_replay_matches_every_frame(mocker, capsys, path):
    """The fixture replays headless through the real loop to its end and exits SUCCESS."""
    recorded_frame_count = len(read_trace_result(path=path).trace['frames'])

    replay = replay_through_engine(
        mocker=mocker, game_key=CONSOLE_SCRIPT_GAME_KEYS[path.parent.name], path=path
    )

    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.SUCCESS, report
    assert report == f'Replay matched {recorded_frame_count} frames (end of recording)\n'
    assert replay.result.frames_replayed == recorded_frame_count


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
