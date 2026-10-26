"""Clockwork Keep moved out of glitchygames/examples: its logical names and history stayed."""

from __future__ import annotations

import gzip
import importlib.util
import inspect
import json
from pathlib import Path

import clockwork_keep.game
from clockwork_keep.game import ClockworkKeepScene
from glitchygames.logical_names import logical_name
from glitchygames.recording_metrics import RECORDING_PATH_RENAMES
from glitchygames.scenes import Scene

# The member's golden replay, directly in its tests/fixtures/replays/
GOLDEN_REPLAY_PATH = Path(__file__).parent / 'fixtures' / 'replays' / 'golden.jsonl.gz'
# Its golden's ledger name, and the one it had before the move
GOLDEN_REPOSITORY_PATH = 'src/games/clockwork-keep/tests/fixtures/replays/golden.jsonl.gz'
GOLDEN_FORMER_PATH = 'tests/fixtures/replays/clockwork-keep/golden.jsonl.gz'


def scenes_the_golden_starts() -> set[str]:
    """Return the logical name of every scene the golden replay starts.

    Returns:
        The scenes' logical names.

    """
    with gzip.open(GOLDEN_REPLAY_PATH, 'rt', encoding='utf-8') as golden:
        frames = [json.loads(line) for line in golden.read().splitlines()[1:]]
    return {
        frame['scene_start']['scene'] for frame in frames if frame.get('scene_start') is not None
    }


def test_clockwork_keep_keeps_its_logical_names():
    """Recordings made before the move name games.clockwork_keep.game:<scene>, as the moved code."""
    assert logical_name(scene_class=ClockworkKeepScene) == (
        'games.clockwork_keep.game:ClockworkKeepScene'
    )
    scenes = {
        logical_name(scene_class=scene_class): scene_class
        for _name, scene_class in inspect.getmembers(clockwork_keep.game, inspect.isclass)
        if issubclass(scene_class, Scene) and scene_class.__module__ == clockwork_keep.game.__name__
    }
    started = {name for name in scenes_the_golden_starts() if name.startswith('games.')}

    assert started, 'the golden replay starts the game'
    # Every scene the golden starts is a scene the moved game defines, under the same name
    assert started <= scenes.keys()
    for name, scene_class in scenes.items():
        assert name == f'games.clockwork_keep.game:{scene_class.__qualname__}'


def test_the_old_example_package_is_gone():
    """Nothing is left in glitchygames/examples to import (a stale __pycache__ would be)."""
    assert importlib.util.find_spec('glitchygames.examples.clockwork_keep') is None


def test_clockwork_keeps_golden_keeps_its_history():
    """Clockwork Keep's golden moved into its member: its rows from before the move follow."""
    assert RECORDING_PATH_RENAMES[GOLDEN_FORMER_PATH] == GOLDEN_REPOSITORY_PATH
