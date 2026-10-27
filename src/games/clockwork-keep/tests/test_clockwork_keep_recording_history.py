"""Clockwork Keep's golden moved into its member: its rows from before the move follow it."""

from __future__ import annotations

from glitchygames.recording_metrics import RECORDING_PATH_RENAMES

# Its golden's ledger name, and the one it had before the move
GOLDEN_REPOSITORY_PATH = 'src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/clockwork-keep/golden.jsonl.gz'


def test_clockwork_keeps_golden_keeps_its_history():
    """Clockwork Keep's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_PATH_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH
