"""A replay under another seed than recorded (rule 19 of glitchygames/replay/driver.py).

The user's decisions (2026-10-26): a replay given ``--random-seed N`` other than its
recording's plays the recording's inputs out under N without comparing ("we can replay the game
but just not record a new version"): headless it prints what differed (the rebaseline's summary)
and exits SUCCESS, writing nothing; watched, its status bar says so and never reports a
divergence; ``--rebaseline NEW --random-seed N`` records them under N in NEW; ``--audit`` under
another seed is refused. These run the departure/arrival session of
tests/world/test_gameplay_recording.py in this process (the stand-in game's child runs are in
tests/replay/tools/test_random_seed.py); this module imports only the engine and engine test
helpers, never ``scripts``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.controls import ReplayControls, Reseeding
from glitchygames.replay.driver import ReplayExitPolicy, ReplayOptions, ReplayResult, ReplaySources
from glitchygames.replay.rebaseline import RebaselineSummary
from glitchygames.tracing import read_trace_result
from tests.world.test_gameplay_recording import (
    RANDOM_SEED,
    Script,
    _key,
    _schedule_quit_in_arrival,
    engine_run_environment,
    run_engine,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# A seed other than the recording's (tests/world/test_gameplay_recording.py RANDOM_SEED)
ANOTHER_SEED = 7
# The frame a scripted action (the game's own exit) runs in
ACTION_FRAME = 2


def record_session(*, tmp_path: Path, mocker) -> Path:
    """Record the departure/arrival session (tests/world/test_gameplay_recording.py) at RANDOM_SEED.

    Returns:
        The recording's path.

    """
    recording_path = tmp_path / 'session.jsonl.gz'
    # engine_run_environment resets Script, so the script is set inside it
    with engine_run_environment(mocker):
        Script.events_by_frame = {
            1: [_key(pygame.KEYDOWN, pygame.K_a, unicode='a')],
            2: [_key(pygame.KEYUP, pygame.K_a)],
        }
        _schedule_quit_in_arrival()
        run_engine('--record-trace', str(recording_path), '--random-seed', str(RANDOM_SEED))
    return recording_path


def replay_session_with_arguments(
    *,
    recording_path: Path,
    mocker,
    arguments: tuple[str, ...],
    action: Callable[[], None] | None = None,
) -> None:
    """Replay the session through the real engine with extra arguments; the exit propagates.

    Args:
        recording_path: The recording.
        mocker: pytest-mock's fixture.
        arguments: More command-line arguments.
        action: Run by the scene on ACTION_FRAME (a game's own exit), or None.

    """
    with engine_run_environment(mocker):
        Script.action, Script.action_frame = action, ACTION_FRAME
        run_engine('--replay-trace', str(recording_path), *arguments)


def test_a_headless_replay_under_another_seed_reports_what_differed_and_exits_success(
    mocker, tmp_path, capsys
):
    """Played out under the given seed, not compared: the summary, nothing recorded, SUCCESS."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    capsys.readouterr()

    with pytest.raises(SystemExit) as exit_information:
        replay_session_with_arguments(
            recording_path=recording_path,
            mocker=mocker,
            arguments=('--headless', '--random-seed', str(ANOTHER_SEED)),
        )

    report = capsys.readouterr().out
    assert exit_information.value.code == ExitCode.SUCCESS, report
    assert f'under random seed {ANOTHER_SEED} (recorded under {RANDOM_SEED}): ' in report
    assert 'Nothing was recorded' in report
    assert sorted(path.name for path in tmp_path.iterdir()) == [recording_path.name]


def test_a_rebaseline_under_another_seed_records_it_in_new(mocker, tmp_path, capsys):
    """``--rebaseline NEW --random-seed N``: NEW's header and options name N; OLD is untouched."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    recording_bytes = recording_path.read_bytes()
    rebaselined_path = tmp_path / 'rebaselined.jsonl.gz'

    with pytest.raises(SystemExit) as exit_information:
        replay_session_with_arguments(
            recording_path=recording_path,
            mocker=mocker,
            arguments=(
                '--headless',
                '--rebaseline',
                str(rebaselined_path),
                '--random-seed',
                str(ANOTHER_SEED),
            ),
        )

    assert exit_information.value.code == ExitCode.SUCCESS, capsys.readouterr().out
    header = read_trace_result(path=rebaselined_path).trace
    assert header['random_seed'] == ANOTHER_SEED
    assert header['options']['random_seed'] == ANOTHER_SEED
    assert recording_path.read_bytes() == recording_bytes


def test_an_audit_under_another_seed_is_refused(mocker, tmp_path, caplog):
    """``--audit`` is a check: under another seed it is refused before anything runs."""
    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    caplog.clear()

    with pytest.raises(SystemExit) as exit_information:
        replay_session_with_arguments(
            recording_path=recording_path,
            mocker=mocker,
            arguments=('--audit', '--random-seed', str(ANOTHER_SEED)),
        )

    assert exit_information.value.code == ExitCode.OPTIONS_REFUSED
    assert f'Cannot audit {recording_path} under --random-seed {ANOTHER_SEED}' in caplog.text
    assert 'Auditing ' not in caplog.text


def test_a_replay_without_comparing_exits_success_whatever_it_found():
    """``ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING``: SUCCESS, even for a run that differed."""
    result = ReplayResult(frames_recorded=3)
    result.end_reason = 'diverged'

    assert result.exit_code(policy=ReplayExitPolicy.SUCCESS_WITHOUT_COMPARING) == ExitCode.SUCCESS


@pytest.mark.parametrize(
    ('undelivered_input_count', 'lost_input_words'),
    [(0, None), (2, '2 recorded input events not delivered (first at frame 1)')],
    ids=['no-input-lost', 'input-lost'],
)
def test_a_reseeded_replays_summary_names_both_seeds_and_any_lost_input(
    undelivered_input_count, lost_input_words
):
    """The summary: frames, both seeds, what differed, any lost input, nothing recorded."""
    summary = RebaselineSummary(
        path=None,
        first_divergence=None,
        frames_differing=0,
        sprites_affected=[],
        frames_replayed=3,
        frames_recorded=3,
        undelivered_input_count=undelivered_input_count,
        first_undelivered_input_frame=1 if undelivered_input_count else None,
    )

    described = summary.describe_reseeded_replay(random_seed=ANOTHER_SEED, recorded_seed=1)

    first_line, second_line = described.splitlines()
    assert first_line.startswith(
        f'Replayed 3 frames under random seed {ANOTHER_SEED} (recorded under 1): no frames differ'
    )
    assert (lost_input_words in first_line) if lost_input_words else first_line.endswith('differ')
    assert second_line.startswith('Nothing was recorded')


def reseeded_header() -> dict[str, object]:
    """Return a header recorded under RANDOM_SEED.

    Returns:
        The header fields ReplaySources reads.

    """
    return {
        'random_seed': RANDOM_SEED,
        'recorded_at': '2026-10-26T00:00:00+00:00',
        'screen_size': [320, 240],
    }


def test_a_reseeded_replay_tells_its_controls_its_seeds():
    """The watched controls know the replay runs under another seed, and which."""
    sources = ReplaySources(
        header=reseeded_header(),
        frames=[],
        format_version=3,
        options=ReplayOptions(random_seed=ANOTHER_SEED),
    )
    compared = ReplaySources(header=reseeded_header(), frames=[], format_version=3)

    assert sources.controls.reseeding == Reseeding(
        random_seed=ANOTHER_SEED, recorded_seed=RANDOM_SEED
    )
    assert compared.controls.reseeding is None


def test_a_reseeded_status_line_names_its_seeds_and_never_a_divergence():
    """Watched under another seed: the status says so, and never "diverged at"."""
    controls = ReplayControls(total_frames=10)
    controls.reseeding = Reseeding(random_seed=ANOTHER_SEED, recorded_seed=RANDOM_SEED)

    line = controls.status_line(frame_number=3, seconds=0.05, divergence_frame=2)

    assert (
        f'replaying under random seed {ANOTHER_SEED} (recorded under {RANDOM_SEED}), not compared'
    ) in line
    assert 'diverged' not in line


def test_d_never_restarts_a_reseeded_replay_at_a_difference():
    """D restarts at a divergence; a reseeded replay has none to restart at."""
    controls = ReplayControls(total_frames=10)
    controls.reseeding = Reseeding(random_seed=ANOTHER_SEED, recorded_seed=RANDOM_SEED)
    controls.divergence_frame = 4

    controls.handle_key(key=pygame.K_d)

    assert controls.take_restart_request() is None


@pytest.mark.parametrize('exit_status', [0, None])
def test_a_reseeded_replay_cut_short_by_the_games_own_exit_still_succeeds(
    mocker, tmp_path, capsys, exit_status
):
    """The game's own sys.exit(0) under another seed is an expected ending, never a failure."""

    def exit_successfully() -> None:
        raise SystemExit(exit_status)

    recording_path = record_session(tmp_path=tmp_path, mocker=mocker)
    capsys.readouterr()

    with pytest.raises(SystemExit) as exit_information:
        replay_session_with_arguments(
            recording_path=recording_path,
            mocker=mocker,
            arguments=('--headless', '--random-seed', str(ANOTHER_SEED)),
            action=exit_successfully,
        )

    report = capsys.readouterr().out
    assert exit_information.value.code == ExitCode.SUCCESS, report
    assert f'under random seed {ANOTHER_SEED} (recorded under {RANDOM_SEED}): ' in report
