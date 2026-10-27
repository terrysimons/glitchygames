"""Brave Adventurer's and Papyrus's goldens moved into the member: their history follows them."""

from __future__ import annotations

from pathlib import Path

import pytest

from glitchygames.recording_metrics import RECORDING_PATH_RENAMES
from glitchygames.testing.replays import recording_console_script

PROJECT_ROOT = Path(__file__).resolve().parents[4]
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
    assert RECORDING_PATH_RENAMES[old_path] == new_path.relative_to(PROJECT_ROOT).as_posix()
    assert recording_console_script(path=new_path) == console_script
