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
from collections import Counter
from pathlib import Path

from scripts.golden_inputs import NEIGHBORHOOD_STAGE_CLEAR_ROUTE
from scripts.plan_neighborhood_route import plan_route

from glitchygames.recording import SCENE_START_FIELD
from glitchygames.replay.playback import PlaybackOptions, start_playback
from glitchygames.tracing import FRAMES_FIELD, read_trace_result
from tests.replay.playback_fixtures import step_finishing
from tests.world.test_frame_integration import running_scene
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene
from zombies_aint_my_neighbors.sprite_kit import Part, PartKind

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


def stage_2_start_frame(frames: list[dict]) -> int:
    """Return the index of the frame where the golden's stage-2 neighborhood begins.

    Returns:
        The frame index.

    Raises:
        AssertionError: If no frame starts a stage-2 neighborhood.

    """
    for index, frame in enumerate(frames):
        scene_start = frame.get(SCENE_START_FIELD)
        if (
            scene_start
            and scene_start['scene_class'] == 'NeighborhoodScene'
            and scene_start.get('arguments', {}).get('run', {}).get('stage') == 2
        ):
            return index
    message = 'the golden holds no stage-2 neighborhood'
    raise AssertionError(message)


def test_the_golden_plays_back_from_stage_2s_start():
    """An in-game playback starting on stage 2 matches the recording to its end.

    A playback rebuilds the scene from its start and gives sprites the ids the recording gave
    (tracing.StableSpriteIds; replay/driver.py rule 18): stage 2's sprites must come back with
    the same ids, however the game builds or reuses them (feature plan 9). The playback's rebuilt
    stage is given no kit, so it builds its own: the live stage's kit is untouched.
    """
    trace = read_trace_result(path=GOLDEN).trace
    frames = trace[FRAMES_FIELD]
    header = {name: value for name, value in trace.items() if name != FRAMES_FIELD}
    start = stage_2_start_frame(frames)

    with running_scene(NeighborhoodScene, extra_arguments=('--resolution', '800x480')) as manager:
        live_kit = manager.active_scene.kit
        live_kit.build_one_toward(needs=Counter({Part(kind=PartKind.TV): 2}))
        waiting = live_kit.storage.sprites()
        assert start_playback(
            manager=manager,
            header=header,
            frames=frames,
            then=manager.active_scene,
            options=PlaybackOptions(start_frame=start),
        )
        step_finishing(manager, frames=len(frames) - start + 5)
        played = manager.last_playback_result
        assert live_kit.storage.sprites() == waiting

    assert played is not None
    assert played.divergence is None, played.divergence
    assert played.end_reason in {'end_of_recording', 'quit'}

