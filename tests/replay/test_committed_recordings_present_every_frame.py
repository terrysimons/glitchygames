"""A watched 1x replay of every committed recording presents every one of its frames.

A watched replay's viewer (glitchygames/replay/viewer.py) runs recorded frames from an
accumulator on a 60 Hz tick and presents only the last frame a tick ran. Up to 1x a tick runs at
most one frame unless the replay is genuinely behind (rule 2), so a frame the live game ran
long and the short frame its pacing caught up with are each presented. This runs the schedule
tool's simulation (scripts/replay_schedule.py: the viewer's real accumulator on an ideal clock)
over every tracked recording but the golden traces' baselines (tests/world/golden, which no
viewer replays), and fails naming each recording and frame a watched 1x replay hides: never
presented though it lasted at least one tick (``RecordingSchedule.hidden``, the tool's rule;
shorter frames a tick skips by design are not failures).
"""

from __future__ import annotations

from pathlib import Path

from scripts.replay_schedule import milliseconds, recorded_frame_seconds, simulate_schedule

from tests.test_our_stored_paths import tracked_files
from tests.workspace_goldens import every_golden_and_bundled_demo

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RECORDING_SUFFIX = '.jsonl.gz'
# The golden traces' baselines (tests/world/test_golden_traces.py): sprite rects frame by frame,
# never replayed through the viewer
GOLDEN_TRACE_BASELINES = 'tests/world/golden/'
NORMAL_SPEED = 1.0


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


def test_every_committed_recording_presents_every_frame_at_normal_speed():
    """No frame of a golden replay, a bundled demo or a fixture is hidden in a 1x watch."""
    hidden = []
    for recording in committed_recordings():
        schedule = simulate_schedule(
            frame_seconds=recorded_frame_seconds(path=recording), speed=NORMAL_SPEED
        )
        hidden.extend(
            f'{recording.relative_to(PROJECT_ROOT).as_posix()}: frame {frame} '
            # A frame lasts its next frame's dt; a hidden frame always has a next frame
            f'({milliseconds(seconds=schedule.frame_seconds[frame + 1])}) is hidden'
            for frame in schedule.hidden
        )

    assert hidden == []


def test_every_golden_and_bundled_demo_is_checked():
    """The tracked recordings checked hold every golden and every bundled demo of our members."""
    checked = {recording.resolve() for recording in committed_recordings()}

    missing = [
        path
        for _console_script, path in every_golden_and_bundled_demo(project_root=PROJECT_ROOT)
        if path.resolve() not in checked
    ]

    assert missing == []
