"""``--random-seed``: one option, one rule, for every run, recording, replay and tool.

The rule (the user's decisions, 2026-10-26): the option defaults to None. A run or a recording
(a plain game, ``record-trace``, ``record-golden-trace``, ``record-session``) rolls a random
seed when it is None, logged in the recording, and uses a given one as is. A replay uses the
recording's seed when it is None or given that one, and compares as always. Given another seed,
a replay plays the recording's inputs out under it without comparing ("we can replay the game
but just not record a new version"): headless it prints what differed and exits SUCCESS, and it
writes nothing; ``--rebaseline NEW`` records it in NEW; ``--audit``, a check, is refused.

The grid (record or replay, given or None) runs on the stand-in game of tests/stand_in_games.py,
whose mover steps by a seeded random amount each frame, in child processes, as a player's runs
are. The harness's own default (``record_trace``) and the replay doors' override are checked in
this process.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.process import run_command
from glitchygames.replay.driver import ReplayOptions, ReplaySources
from glitchygames.replay.tools.golden_traces import InputScript, record_trace
from glitchygames.replay.tools.registry import RANDOM_SEED_OPTION, TOOLS
from glitchygames.tracing import read_trace_result
from tests.replay.replay_helpers import tamper_first_sprite_rect
from tests.replay.tools.test_golden_trace_harness import SeededWanderScene
from tests.stand_in_games import (
    RECORD_TIMEOUT_SECONDS,
    StandInGame,
    record_stand_in_game,
    use_stand_in_game,
    write_stand_in_game,
)

if TYPE_CHECKING:
    from pathlib import Path

# A seed given to a recording, and another given to its replay in place of the recorded one
GIVEN_RECORDING_SEED = 41
GIVEN_REPLAY_SEED = 7
# Frames the harness runs for the default-seed check: enough random steps that two random
# seeds giving the same trace is out of the question
HARNESS_FRAME_COUNT = 30
# The frame a tampered copy of a recording diverges at (the stand-in's mover is on every frame)
TAMPERED_FRAME = 10
# What the help says, for every tool that lists the option
RANDOM_SEED_RULE_WORDS = (
    'a run or recording rolls a random',
    "a replay uses the recording's",
    'without comparing or writing anything',
    '--replay-trace OLD --rebaseline NEW --random-seed N',
    '--audit under another seed is refused',
)


@pytest.fixture
def stand_in_game(tmp_path_factory, monkeypatch) -> StandInGame:
    """Install the stand-in game (tests/stand_in_games.py) for this test and its children.

    Returns:
        The stand-in game.

    """
    install_directory = tmp_path_factory.mktemp('site-packages')
    game = write_stand_in_game(directory=install_directory)
    use_stand_in_game(install_directory=install_directory, monkeypatch=monkeypatch)
    return game


def recorded_seed(*, path: Path) -> int:
    """Return a recording's header seed.

    Returns:
        Its ``random_seed``.

    """
    return read_trace_result(path=path).trace['random_seed']


def replay_stand_in_game(
    *,
    game: StandInGame,
    path: Path,
    extra_arguments: tuple[str, ...] = (),
    working_directory: Path | None = None,
) -> tuple[int, str]:
    """Replay a stand-in game's recording headless in a child, logging at info level.

    Args:
        game: The stand-in game.
        path: The recording.
        extra_arguments: More command-line arguments for the child.
        working_directory: Where the child runs (this process's directory by default).

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
            '--replay-trace',
            str(path),
            '--headless',
            *extra_arguments,
        ],
        environment=os.environ,
        timeout_seconds=RECORD_TIMEOUT_SECONDS,
        capture_output=True,
        working_directory=working_directory,
    )
    return completed.returncode, completed.stdout or ''


def assert_the_replay_compares(
    *, game: StandInGame, path: Path, extra_arguments: tuple[str, ...]
) -> None:
    """Check a replay with these arguments really compares: a tampered copy diverges.

    A replay that compared nothing (a reseeded one) would exit SUCCESS for the copy too.

    Args:
        game: The stand-in game.
        path: The recording.
        extra_arguments: The replay's arguments (no seed, or the recorded one).

    """
    tampered = path.with_name(f'tampered-{path.name}')
    tampered.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered, frame_number=TAMPERED_FRAME)

    status, output = replay_stand_in_game(game=game, path=tampered, extra_arguments=extra_arguments)

    assert status == ExitCode.REPLAY_DIVERGED, output
    assert f'Replay diverged at frame {TAMPERED_FRAME}' in output
    assert 'Nothing was recorded' not in output


def test_a_recording_without_a_seed_rolls_one_each_time(stand_in_game, tmp_path):
    """Record, None: each recording rolls its own seed, logged in its header."""
    first = record_stand_in_game(game=stand_in_game, path=tmp_path / 'first.jsonl.gz')
    second = record_stand_in_game(game=stand_in_game, path=tmp_path / 'second.jsonl.gz')

    assert recorded_seed(path=first) != recorded_seed(path=second)


def test_a_recording_given_a_seed_records_it(stand_in_game, tmp_path):
    """Record, given: the seed is used as is, and the header names it."""
    path = record_stand_in_game(
        game=stand_in_game,
        path=tmp_path / 'given.jsonl.gz',
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )

    assert recorded_seed(path=path) == GIVEN_RECORDING_SEED


def test_a_replay_without_a_seed_uses_the_recordings_and_matches(stand_in_game, tmp_path):
    """Replay, None: the recording's seed, so the seeded mover replays exactly."""
    path = record_stand_in_game(game=stand_in_game, path=tmp_path / 'recorded.jsonl.gz')

    status, output = replay_stand_in_game(game=stand_in_game, path=path)

    assert status == ExitCode.SUCCESS, output
    assert f'random seed {recorded_seed(path=path)})' in output
    assert_the_replay_compares(game=stand_in_game, path=path, extra_arguments=())


def test_a_replay_given_the_recordings_own_seed_matches(stand_in_game, tmp_path):
    """Replay, given the recorded seed: allowed, and it replays exactly."""
    path = record_stand_in_game(
        game=stand_in_game,
        path=tmp_path / 'recorded.jsonl.gz',
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )

    status, output = replay_stand_in_game(
        game=stand_in_game,
        path=path,
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )

    assert status == ExitCode.SUCCESS, output
    assert_the_replay_compares(
        game=stand_in_game,
        path=path,
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )


def test_a_replay_given_another_seed_plays_out_under_it_and_writes_nothing(stand_in_game, tmp_path):
    """Replay, given another seed: played out under it, not compared, nothing written.

    Headless it prints what differed from the recording (as a rebaseline does), says nothing was
    recorded, and exits SUCCESS. The engine ran under the given seed: it announces it, and the
    stand-in's seeded mover moved otherwise than recorded.
    """
    recording_directory = tmp_path / 'recording'
    recording_directory.mkdir()
    path = record_stand_in_game(
        game=stand_in_game,
        path=recording_directory / 'recorded.jsonl.gz',
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )
    recording_bytes = path.read_bytes()
    working_directory = tmp_path / 'working'
    working_directory.mkdir()

    status, output = replay_stand_in_game(
        game=stand_in_game,
        path=path,
        extra_arguments=('--random-seed', str(GIVEN_REPLAY_SEED)),
        working_directory=working_directory,
    )

    assert status == ExitCode.SUCCESS, output
    assert f'random seed {GIVEN_REPLAY_SEED})' in output
    assert (
        f'under random seed {GIVEN_REPLAY_SEED} (recorded under {GIVEN_RECORDING_SEED}): '
    ) in output
    # The seeded mover moved otherwise than recorded: the frames differ
    assert 'no frames differ' not in output
    assert 'Nothing was recorded' in output
    assert 'Replay diverged' not in output
    assert sorted(recording_directory.iterdir()) == [path]
    assert path.read_bytes() == recording_bytes
    assert list(working_directory.iterdir()) == []


def test_an_audit_given_another_seed_is_refused_before_it_runs(stand_in_game, tmp_path):
    """``--audit`` under another seed: refused, naming both seeds, the replay and rebaseline."""
    path = record_stand_in_game(
        game=stand_in_game,
        path=tmp_path / 'recorded.jsonl.gz',
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )

    status, output = replay_stand_in_game(
        game=stand_in_game,
        path=path,
        extra_arguments=('--random-seed', str(GIVEN_REPLAY_SEED), '--audit'),
    )

    assert status == ExitCode.OPTIONS_REFUSED, output
    assert f'Cannot audit {path} under --random-seed {GIVEN_REPLAY_SEED}' in output
    assert f'recorded under seed {GIVEN_RECORDING_SEED}' in output
    assert '--replay-trace OLD --rebaseline NEW --random-seed N' in output
    assert 'Auditing ' not in output


def test_a_rebaseline_given_a_seed_replays_under_it_and_records_it(stand_in_game, tmp_path):
    """``--rebaseline NEW --random-seed N``: the engine uses N, NEW names it, OLD is untouched."""
    path = record_stand_in_game(
        game=stand_in_game,
        path=tmp_path / 'recorded.jsonl.gz',
        extra_arguments=('--random-seed', str(GIVEN_RECORDING_SEED)),
    )
    recording_bytes = path.read_bytes()
    rebaselined = tmp_path / 'rebaselined.jsonl.gz'

    status, output = replay_stand_in_game(
        game=stand_in_game,
        path=path,
        extra_arguments=('--random-seed', str(GIVEN_REPLAY_SEED), '--rebaseline', str(rebaselined)),
    )

    assert status == ExitCode.SUCCESS, output
    assert f'random seed {GIVEN_REPLAY_SEED})' in output
    assert recorded_seed(path=rebaselined) == GIVEN_REPLAY_SEED
    assert read_trace_result(path=rebaselined).trace['options']['random_seed'] == (
        GIVEN_REPLAY_SEED
    )
    assert path.read_bytes() == recording_bytes


def test_a_rebaseline_without_a_seed_keeps_the_recordings(stand_in_game, tmp_path):
    """``--rebaseline NEW`` alone replays under OLD's seed, and NEW names it."""
    path = record_stand_in_game(game=stand_in_game, path=tmp_path / 'recorded.jsonl.gz')
    rebaselined = tmp_path / 'rebaselined.jsonl.gz'

    status, output = replay_stand_in_game(
        game=stand_in_game, path=path, extra_arguments=('--rebaseline', str(rebaselined))
    )

    assert status == ExitCode.SUCCESS, output
    assert recorded_seed(path=rebaselined) == recorded_seed(path=path)


def test_the_replay_doors_use_a_given_seed_in_place_of_the_recorded_one():
    """``ReplayOptions.random_seed`` (a rebaseline's) replaces the header's seed; None keeps it."""
    header = {
        'random_seed': GIVEN_RECORDING_SEED,
        'recorded_at': '2026-10-26T00:00:00+00:00',
        'screen_size': [320, 240],
    }

    recorded = ReplaySources(header=header, frames=[], format_version=3)
    overridden = ReplaySources(
        header=header,
        frames=[],
        format_version=3,
        options=ReplayOptions(random_seed=GIVEN_REPLAY_SEED),
    )

    assert recorded.random_seed == GIVEN_RECORDING_SEED
    assert overridden.random_seed == GIVEN_REPLAY_SEED


def test_the_golden_harness_rolls_a_seed_when_none_is_given():
    """``record_trace`` without a seed rolls one, as any run does: two runs differ."""
    first = record_trace(
        scene_class=SeededWanderScene, script=InputScript(), frame_count=HARNESS_FRAME_COUNT
    )
    second = record_trace(
        scene_class=SeededWanderScene, script=InputScript(), frame_count=HARNESS_FRAME_COUNT
    )

    assert first['frames'] != second['frames']


def test_every_tool_that_takes_a_seed_shares_one_option_stating_the_rule():
    """One ``--random-seed`` (default None) for every tool that runs the game.

    verify and measure list it only to refuse it (they always replay each recording under its
    recorded seed: test_verify.py, test_measure.py).
    """
    listing = sorted(tool.name for tool in TOOLS if RANDOM_SEED_OPTION in tool.options)

    assert listing == sorted([
        'record-trace',
        'replay-trace',
        'record-golden-trace',
        'record-session',
        'verify',
        'measure',
    ])
    assert RANDOM_SEED_OPTION.default is None
    for words in RANDOM_SEED_RULE_WORDS:
        assert words in RANDOM_SEED_OPTION.help
