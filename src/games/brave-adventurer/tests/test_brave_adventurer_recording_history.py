"""Brave Adventurer's and Papyrus's goldens moved into the member: their history follows them."""

from __future__ import annotations

from pathlib import Path

import pytest

from glitchygames.replay.tools.children import recording_console_script
from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parents[4]
# Recordings that moved, old repository path -> new (our [tool.glitchygames])
RECORDING_RENAMES = load_project_settings(project_root=PROJECT_ROOT).recording_renames
MEMBER_DIRECTORY = Path(__file__).resolve().parents[1]
REPLAY_FIXTURES_DIRECTORY = MEMBER_DIRECTORY / 'tests' / 'fixtures' / 'replays'
# Each game's golden replay: where it was in the engine's tests (named after the console script
# that replayed it then), where it is now, and the console script that replays it now: the
# launcher, for both
GOLDENS = [
    (
        'tests/fixtures/replays/brave-adventurer/golden.jsonl.gz',
        'golden-classic.jsonl.gz',
        'brave-adventurer',
    ),
    (
        'tests/fixtures/replays/brave-adventurer-papyrus/golden.jsonl.gz',
        'golden-papyrus.jsonl.gz',
        'brave-adventurer',
    ),
]


@pytest.mark.parametrize(('old_path', 'new_name', 'console_script'), GOLDENS)
def test_both_goldens_keep_their_history(old_path, new_name, console_script):
    """Each golden moved (its ledger rows follow it) and still replays through its own game."""
    new_path = REPLAY_FIXTURES_DIRECTORY / new_name

    assert new_path.is_file()
    assert not (PROJECT_ROOT / old_path).exists()
    assert RECORDING_RENAMES[old_path] == new_path.relative_to(PROJECT_ROOT).as_posix()
    assert recording_console_script(path=new_path) == console_script
