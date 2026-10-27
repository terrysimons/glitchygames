"""Clockwork Keep's golden moved into its member: its rows from before the move follow it."""

from __future__ import annotations

from pathlib import Path

from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parents[4]
# Recordings that moved, old repository path -> new (our [tool.glitchygames])
RECORDING_RENAMES = load_project_settings(project_root=PROJECT_ROOT).recording_renames
# Its golden's ledger name, and the one it had before the move
GOLDEN_REPOSITORY_PATH = 'src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/clockwork-keep/golden.jsonl.gz'


def test_clockwork_keeps_golden_keeps_its_history():
    """Clockwork Keep's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH
