"""The neighborhood golden clears its stage and reaches stage 2, on the route its planner makes.

Feature plan 7. The golden's stage-clear route is a fixed list of held keys
(``scripts.golden_inputs.NEIGHBORHOOD_STAGE_CLEAR_ROUTE``), planned by simulating the stage
(``scripts.plan_neighborhood_route``). A gameplay change (zombie speed, neighbor places, spawn
timing, a new weapon) can move things so the same keys miss neighbors or never reach the gate,
and a re-recording would still replay. These tests catch it: the golden must reach stage 2, and
the committed route must still be the plan.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from scripts.golden_inputs import NEIGHBORHOOD_STAGE_CLEAR_ROUTE
from scripts.plan_neighborhood_route import plan_route

GOLDEN = Path(__file__).resolve().parent / 'fixtures' / 'replays' / 'golden-neighborhood.jsonl.gz'


def scene_starts(path: Path) -> list[tuple[str, dict]]:
    """Return each scene a recording starts: its class name and its arguments.

    Returns:
        (scene class name, arguments), in order.

    """
    starts = []
    with gzip.open(path, 'rt', encoding='utf-8') as recording:
        for line in recording:
            scene_start = json.loads(line).get('scene_start')
            if scene_start:
                starts.append((scene_start['scene_class'], scene_start.get('arguments', {})))
    return starts


def test_the_neighborhood_golden_clears_its_stage_into_stage_2():
    """Stage 1, then the STAGE 2 card, then stage 2's neighborhood with the neighbors rescued."""
    starts = scene_starts(GOLDEN)
    stages = [(name, arguments.get('run', {}).get('stage')) for name, arguments in starts]

    assert stages[0] == ('NeighborhoodScene', 1)
    assert ('FeatureCardScene', 2) in stages
    assert stages.index(('FeatureCardScene', 2)) < stages.index(('NeighborhoodScene', 2))
    stage_2 = next(
        arguments for name, arguments in starts if arguments.get('run', {}).get('stage') == 2
    )
    assert stage_2['run']['neighbors']


def test_the_committed_route_is_still_the_plan():
    """Planning the stage again gives the route the golden holds, and it clears the stage."""
    plan = plan_route()

    assert plan.route == NEIGHBORHOOD_STAGE_CLEAR_ROUTE
    assert plan.rescued > 0
    assert plan.cleared_at < plan.card_at


def test_the_golden_lures_a_zombie_with_the_laser():
    """The opening's laser burst pulls a zombie (feature plan 8): the lure has a replay too.

    The final review found the first burst shone where no zombie could reach it.
    """
    plan = plan_route()

    assert plan.lured_frames > 0
