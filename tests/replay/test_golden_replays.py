"""Checks on the golden replays under tests/fixtures/replays.

A fixture is ``tests/fixtures/replays/<console-script>/<name>.jsonl.gz``, recorded through the
real engine by scripts/record_scripted_session.py. Each fixture is itself a test item: the replay
plugin (glitchygames/testing/replays.py, loaded by the root conftest) replays it headless through
the game's console script entry point (``--replay-trace PATH --headless``: GameEngine +
SceneManager.start, not the golden harness) and fails with the printed divergence report unless
it exits ``ExitCode.SUCCESS``. The tests here check that the fixtures exist, are in game
directories, and that a replay through the engine really compares.
"""

from __future__ import annotations

from scripts.record_scripted_session import (
    CONSOLE_SCRIPT_GAME_KEYS,
    REPLAY_FIXTURE_DIRECTORY,
    REPLAY_FIXTURE_SUFFIX,
)

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import SPRITE_DIVERGENCE
from tests.replay.replay_helpers import replay_through_engine, tamper_first_sprite_rect

# The frame a tampered copy of a fixture first differs from the engine at
TAMPERED_FRAME = 10

REPLAY_FIXTURES = sorted(REPLAY_FIXTURE_DIRECTORY.glob(f'*/*{REPLAY_FIXTURE_SUFFIX}'))


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
    assert f'frames differ (first at {TAMPERED_FRAME}: sprite ' in summary
    assert 'sprites affected: ' in summary
    replay = replay_through_engine(mocker=mocker, game_key='paddleslap', path=rebaselined_path)
    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.SUCCESS, report
    assert replay.result.divergence is None
