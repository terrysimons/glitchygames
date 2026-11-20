"""Drawing Fire's benchmarks (the line-of-sight walk is a third of the game's frame).

Run benchmarks:
    pytest src/games/drawing-fire/tests/test_drawing_fire_benchmarks.py --benchmark-only
"""

from __future__ import annotations

import random

from drawing_fire.drivers import _can_see
from drawing_fire.terrain import build_terrain

FIELD_WIDTH = 800
FIELD_HEIGHT = 480
# Two soldiers across most of the field, chests above the ground, as the computer players test
SIGHT_START = (60.0, 330.0)
SIGHT_END = (740.0, 330.0)


def test_benchmark_line_of_sight_across_the_field(benchmark):
    """Benchmark one long line-of-sight test (about 110 ground_y calls)."""
    terrain = build_terrain(width=FIELD_WIDTH, height=FIELD_HEIGHT, random=random.Random(5))
    benchmark(_can_see, terrain=terrain, start=SIGHT_START, end=SIGHT_END)
