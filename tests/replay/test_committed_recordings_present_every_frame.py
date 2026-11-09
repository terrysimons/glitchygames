"""A watched 1x replay of every committed recording presents every one of its frames.

A watched replay's viewer (glitchygames/replay/viewer.py) runs recorded frames from an
accumulator on a 60 Hz tick and presents only the last frame a tick ran. Up to 1x a tick runs at
most one frame unless the replay is genuinely behind (rule 2), so a frame the live game ran
long and the short frame its pacing caught up with are each presented. This runs the schedule
tool's simulation (scripts/replay_schedule.py: the viewer's real accumulator on an ideal clock)
over every tracked recording but the golden traces' baselines (tests/world/golden, which no
viewer replays), and fails naming each recording and frame a watched 1x replay hides: never
presented because a later frame ran in its tick while the replay was not behind
(``RecordingSchedule.hidden``, the tool's rule, on the viewer's own behind condition; frames a
tick skipped while the replay was behind are not failures).
"""

from __future__ import annotations

from pathlib import Path

from scripts.replay_schedule import (
    main,
    milliseconds,
    recorded_frame_seconds,
    simulate_schedule,
)

from glitchygames.bundled_demos import bundled_demos
from glitchygames.exit_codes import ExitCode
from glitchygames.replay.viewer import ReplayViewer
from tests.test_our_stored_paths import tracked_files
from tests.workspace_expectations import MEMBER_PACKAGES
from tests.workspace_goldens import every_games_golden

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RECORDING_SUFFIX = '.jsonl.gz'
# The golden traces' baselines (tests/world/test_golden_traces.py): sprite rects frame by frame,
# never replayed through the viewer
GOLDEN_TRACE_BASELINES = 'tests/world/golden/'
NORMAL_SPEED = 1.0
TWICE_THE_SPEED = 2.0
# PaddleSlap's bundled demo, whose frame 286 (28.63 ms) a broken rule 2 hides
RALLY_DEMO = PROJECT_ROOT / 'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'


def committed_recordings() -> list[Path]:
    """Return every tracked recording but the golden traces' baselines.

    Returns:
        Their paths, sorted.

    """
    return sorted(
        PROJECT_ROOT / name
        for name in tracked_files()
        if name.endswith(RECORDING_SUFFIX) and not name.startswith(GOLDEN_TRACE_BASELINES)
    )


def schedule_problems(*, speed: float) -> list[str]:
    """Return every hidden frame, and every frame the viewer's behind flag disagrees on.

    Args:
        speed: The replay speed simulated.

    Returns:
        ``<recording>: frame N (X ms) is hidden`` and ``<recording>: the viewer disagrees on
        whether frame N ran behind`` lines, by recording.

    """
    problems = []
    for recording in committed_recordings():
        name = recording.relative_to(PROJECT_ROOT).as_posix()
        schedule = simulate_schedule(
            frame_seconds=recorded_frame_seconds(path=recording), speed=speed
        )
        problems.extend(
            f'{name}: frame {frame} '
            # A frame lasts its next frame's dt; a hidden frame always has a next frame
            f'({milliseconds(seconds=schedule.frame_seconds[frame + 1])}) is hidden'
            for frame in schedule.hidden
        )
        problems.extend(
            f'{name}: the viewer disagrees on whether frame {frame} ran behind'
            for frame in schedule.behind_disagreements
        )
    return problems


def test_every_committed_recording_presents_every_frame_at_normal_speed():
    """No frame of a golden replay, a bundled demo or a fixture is hidden in a 1x watch."""
    assert schedule_problems(speed=NORMAL_SPEED) == []


def test_every_committed_recording_presents_its_long_frames_at_twice_the_speed():
    """At 2x every frame lasting at least a tick of inner time (33.3 ms) is shown (rule 2)."""
    assert schedule_problems(speed=TWICE_THE_SPEED) == []


def weakened_owes_beyond_a_tick(viewer: ReplayViewer, *, inner_frame_seconds: float) -> bool:
    """A broken behind condition: owing the frame alone (rule 2's deferral then never applies).

    Returns:
        True when the accumulator holds the frame's duration.

    """
    return viewer.accumulated_seconds >= inner_frame_seconds


def test_a_weakened_behind_condition_is_caught_by_the_guard(mocker):
    """A broken viewer behind condition hides golden-classic frame 460; the guard names it.

    The guard derives behind itself, so the viewer's own condition (and rule 2 built on it)
    breaking cannot hide the frame from it.
    """
    mocker.patch.object(
        ReplayViewer,
        '_owes_beyond_a_tick',
        autospec=True,
        side_effect=weakened_owes_beyond_a_tick,
    )

    problems = schedule_problems(speed=NORMAL_SPEED)

    assert (
        'src/games/brave-adventurer/tests/fixtures/replays/golden-classic.jsonl.gz: '
        'frame 460 (34.02 ms) is hidden'
    ) in problems


def test_a_weakened_behind_condition_is_caught_by_the_tool(mocker, capsys):
    """The schedule tool, on the same broken viewer, names rally frame 286 and fails."""
    mocker.patch.object(
        ReplayViewer,
        '_owes_beyond_a_tick',
        autospec=True,
        side_effect=weakened_owes_beyond_a_tick,
    )

    exit_code = main(arguments=[str(RALLY_DEMO), '--summary'])

    output = capsys.readouterr().out
    assert exit_code == ExitCode.REPLAY_DIVERGED
    assert 'hidden: 286' in output


def test_every_golden_and_bundled_demo_is_checked():
    """The tracked recordings checked hold every golden and every bundled demo of our members.

    A golden is found in the repository, so it is matched by its path. A bundled demo is found
    where its package is installed: in the repository under ``uv sync`` (editable), in
    site-packages under nox (not editable). So it is matched by its install name
    (``paddleslap/demos/rally.jsonl.gz``), which is the same under any install.
    """
    checked = committed_recordings()
    checked_paths = {recording.resolve() for recording in checked}
    checked_names = [recording.as_posix() for recording in checked]

    missing_goldens = [
        golden
        for golden in every_games_golden(project_root=PROJECT_ROOT)
        if golden.resolve() not in checked_paths
    ]
    demos = bundled_demos(packages=MEMBER_PACKAGES)
    missing_demos = [
        demo.install_name
        for demo in demos
        if not any(name.endswith(f'/{demo.install_name}') for name in checked_names)
    ]

    # Found at all: with the members not installed, nothing would be missing either
    assert demos
    assert missing_goldens == []
    assert missing_demos == []
