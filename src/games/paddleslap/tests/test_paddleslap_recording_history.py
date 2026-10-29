"""PaddleSlap's own recording history: every path its recordings had leads to the committed file.

Split from the engine's tests (tests/replay/tools/test_report.py, whose end-to-end test of the
report stays there). Every path the rally demo and the golden had before the move leads to the
committed file (the root pyproject.toml's ``[tool.glitchygames]`` ``recording-renames``).
"""

from __future__ import annotations

from pathlib import Path

from glitchygames.replay.tools.settings import load_project_settings

PROJECT_ROOT = Path(__file__).resolve().parents[4]
# Recordings that moved, old repository path -> new (our [tool.glitchygames])
RECORDING_RENAMES = load_project_settings(project_root=PROJECT_ROOT).recording_renames

# Where the rally demo is now, and every path it had before, relative to the repository
RALLY_DEMO_REPOSITORY_PATH = 'src/games/paddleslap/src/paddleslap/demos/rally.jsonl.gz'
RALLY_DEMO_FORMER_PATHS = (
    'glitchygames/examples/paddleslap_demos/rally.jsonl.gz',
    'src/glitchygames/examples/paddleslap_demos/rally.jsonl.gz',
    'src/games/paddleslap/paddleslap/demos/rally.jsonl.gz',
)
GOLDEN_REPOSITORY_PATH = 'src/games/paddleslap/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/paddleslap/golden.jsonl.gz'


def test_the_rally_demo_keeps_its_whole_history():
    """Each of the demo's former paths maps straight to its new one: a lookup is one step."""
    for former_path in RALLY_DEMO_FORMER_PATHS:
        assert RECORDING_RENAMES[former_path] == RALLY_DEMO_REPOSITORY_PATH


def test_paddleslaps_golden_keeps_its_history():
    """PaddleSlap's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH
