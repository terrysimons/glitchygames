"""Every committed recording names its game and scenes by logical names that resolve."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from scripts.workspace_packages import workspace_members

from glitchygames.logical_names import module_for_logical_module
from glitchygames.recording import SCENE_START_FIELD
from glitchygames.testing.replays import bundled_demo_paths
from glitchygames.tracing import read_trace

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COMMITTED_RECORDINGS = sorted([
    *PROJECT_ROOT.glob('tests/fixtures/replays/*/*.jsonl.gz'),
    *(
        recording
        for member in workspace_members(project_root=PROJECT_ROOT)
        for recording in member.replay_fixtures_directory.glob('*.jsonl.gz')
    ),
    *(path for _console_script, path in bundled_demo_paths()),
])


def resolves(logical: str) -> bool:
    """Whether ``layer.module:qualname`` names a class of a real module in the workspace.

    Returns:
        True when the module imports and the qualified name inside it is a class.

    """
    logical_module, _, qualified_name = logical.partition(':')
    try:
        target: object = importlib.import_module(
            module_for_logical_module(logical_module=logical_module)
        )
    except ImportError:
        return False
    for attribute in qualified_name.split('.'):
        target = getattr(target, attribute, None)
    return isinstance(target, type)


def recording_id(path: Path) -> str:
    """The recording's repository path (the bundled demo, in the installed engine: its name).

    Returns:
        The id pytest shows for the recording.

    """
    return (
        path.relative_to(PROJECT_ROOT).as_posix()
        if path.is_relative_to(PROJECT_ROOT)
        else path.name
    )


@pytest.mark.parametrize('recording', COMMITTED_RECORDINGS, ids=recording_id)
def test_every_logical_name_in_the_recording_resolves(recording):
    """The header's ``game`` and every scene start's ``scene`` name a class that exists."""
    trace = read_trace(path=recording)
    names = [trace.get('game')] + [
        frame[SCENE_START_FIELD].get('scene')
        for frame in trace['frames']
        if SCENE_START_FIELD in frame
    ]

    unresolved = [name for name in names if name is None or not resolves(name)]
    assert not unresolved, f'{recording}: logical names missing or unresolved: {unresolved}'


def test_the_committed_recordings_are_all_checked():
    """Five golden replays and PaddleSlap's demo (more as games, demos and apps gain them)."""
    assert len(COMMITTED_RECORDINGS) >= 6
