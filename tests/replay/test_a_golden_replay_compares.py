"""A golden replay through the engine really compares, and finds the game that replays it.

On stand-ins (tests/stand_in_games.py, tests/stand_in_harness_games.py): a member distribution's
golden is replayed by its console script, a folder that is no member is refused, and a golden
tampered by one pixel diverges at its frame while its rebaseline replays clean. Moved here
unchanged from tests/replay/test_golden_replays.py (Part 3, Stage D, Task D9 fix round 1), which
checks our members' own goldens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from glitchygames.exit_codes import ExitCode
from glitchygames.replay.driver import SPRITE_DIVERGENCE
from glitchygames.replay.tools.children import recording_console_script
from glitchygames.replay.tools.scripted_sessions import record_scripted_session
from glitchygames.tracing import read_trace_result
from tests.replay.replay_helpers import replay_through_engine, tamper_first_sprite_rect
from tests.stand_in_games import (
    member_recording_path,
    write_header_only_recording,
    write_stand_in_distribution,
)
from tests.stand_in_harness_games import SteeredPaddleScene, steered_paddle_script
from tests.workspace_expectations import GOLDEN_SUFFIX

if TYPE_CHECKING:
    from pathlib import Path


# The frame a tampered copy of a fixture first differs from the engine at
TAMPERED_FRAME = 10

# The stand-in golden's frames: TAMPERED_FRAME and 20 frames after it
STAND_IN_GOLDEN_FRAMES = 30


def test_a_members_golden_replay_is_replayed_by_the_members_console_script(tmp_path, monkeypatch):
    """<member>/tests/fixtures/replays/<name>.jsonl.gz: the member distribution names the game.

    A stand-in member distribution with exactly one console script, so its script is chosen
    without reading the recording's header (a header-only recording that names no game). The
    plugin's other layout, ``fixtures/replays/<console-script>/<name>.jsonl.gz`` (another
    project's, and no game's here since every game is a member), is named by its folder: a
    path under tmp_path whose folder is another installed stand-in's console script, so each
    layout's name visibly comes from its own source.
    """
    installed = tmp_path / 'site-packages'
    for distribution, package in (
        ('stand-in-muncher', 'stand_in_muncher'),
        ('stand-in-fire', 'stand_in_fire'),
    ):
        write_stand_in_distribution(
            directory=installed,
            distribution=distribution,
            console_scripts={distribution: f'{package}:main'},
        )
    monkeypatch.syspath_prepend(installed)
    golden = member_recording_path(tmp_path=tmp_path, distribution='stand-in-muncher')
    write_header_only_recording(path=golden, header={})
    root_layout_golden = (
        tmp_path / 'project' / 'fixtures' / 'replays' / 'stand-in-fire' / 'golden.jsonl.gz'
    )

    assert recording_console_script(path=golden) == 'stand-in-muncher'
    assert recording_console_script(path=root_layout_golden) == 'stand-in-fire'


def test_a_recording_of_a_folder_that_is_no_member_is_refused(tmp_path):
    """A distribution that is not installed (or has several console scripts) names no game."""
    misplaced = tmp_path / 'not-a-member' / 'tests' / 'fixtures' / 'replays' / 'golden.jsonl.gz'

    with pytest.raises(KeyError, match='not-a-member'):
        recording_console_script(path=misplaced)


def record_stand_in_golden(*, mocker, tmp_path: Path) -> Path:
    """Record a stand-in game's scripted session through the engine, as a golden replay is.

    The stand-in (``SteeredPaddleScene``, tests/stand_in_harness_games.py) draws its paddle on
    every frame, so the recording has a sprite on TAMPERED_FRAME and every frame after it, and
    moves a fixed step per frame, so it replays deterministically.

    Returns:
        The recording's path.

    """
    # GameEngine._shutdown quits pygame; later tests on this worker still need it
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    path = tmp_path / f'golden{GOLDEN_SUFFIX}'
    record_scripted_session(
        scene_class=SteeredPaddleScene,
        script=steered_paddle_script(),
        frame_count=STAND_IN_GOLDEN_FRAMES,
        path=path,
    )
    frames = read_trace_result(path=path).trace['frames']
    assert all(frame['sprites'] for frame in frames[TAMPERED_FRAME:])
    return path


def test_a_tampered_golden_replay_is_reported_at_its_frame(mocker, capsys, tmp_path):
    """The golden replays really compare: a fixture moved by one pixel diverges there."""
    path = record_stand_in_golden(mocker=mocker, tmp_path=tmp_path)
    tampered_path = tmp_path / f'tampered{GOLDEN_SUFFIX}'
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    capsys.readouterr()

    replay = replay_through_engine(
        mocker=mocker, scene_class=SteeredPaddleScene, path=tampered_path
    )

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
    path = record_stand_in_golden(mocker=mocker, tmp_path=tmp_path)
    tampered_path = tmp_path / f'tampered{GOLDEN_SUFFIX}'
    tampered_path.write_bytes(path.read_bytes())
    tamper_first_sprite_rect(recording_path=tampered_path, frame_number=TAMPERED_FRAME)
    rebaselined_path = tmp_path / f'rebaselined{GOLDEN_SUFFIX}'
    capsys.readouterr()

    rebaseline = replay_through_engine(
        mocker=mocker,
        scene_class=SteeredPaddleScene,
        path=tampered_path,
        extra_arguments=('--rebaseline', str(rebaselined_path)),
    )

    summary = capsys.readouterr().out
    assert rebaseline.exit_status == ExitCode.SUCCESS, summary
    # Every tampered frame differs: those from TAMPERED_FRAME on that have a sprite to move
    frames = read_trace_result(path=tampered_path).trace['frames']
    tampered_frame_count = sum(1 for frame in frames[TAMPERED_FRAME:] if frame['sprites'])
    assert rebaseline.result.differing_frame_count == tampered_frame_count
    assert f'{tampered_frame_count} frames differ (first at {TAMPERED_FRAME}: sprite ' in summary
    assert 'sprites affected: ' in summary
    replay = replay_through_engine(
        mocker=mocker, scene_class=SteeredPaddleScene, path=rebaselined_path
    )
    report = capsys.readouterr().out
    assert replay.exit_status == ExitCode.SUCCESS, report
    assert replay.result.divergence is None
