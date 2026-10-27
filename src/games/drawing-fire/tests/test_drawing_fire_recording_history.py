"""Drawing Fire's golden moved into its member: its rows from before the move follow it."""

from __future__ import annotations

from glitchygames.recording_metrics import RECORDING_PATH_RENAMES

GOLDEN_REPOSITORY_PATH = 'src/games/drawing-fire/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/drawing-fire/golden.jsonl.gz'


def test_drawing_fires_golden_keeps_its_history():
    """Drawing Fire's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_PATH_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH
