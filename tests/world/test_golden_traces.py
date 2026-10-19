"""Golden traces: every game plays exactly as it did before the engine world-space change.

The baselines in ``tests/world/golden/`` were recorded by ``scripts/record_golden_traces.py``
before any world-space engine change (plans/2026-10-18-engine-world-space.md). Each test
replays the same scripted, deterministic run and compares every sprite's rect and visibility,
frame by frame.

A difference fails the test unless an entry in ``EXPECTED_DIFFERENCES`` explains it: same
field, frame inside the entry's range, sprite id matching its pattern, and either the current
value equal to the entry's pinned ``expected`` value, the entry's ``rule`` accepting the
(baseline, current) pair, or its ``world_rule`` accepting the difference given the frame's
world sample (world and camera positions the trace does not record, read from the current
run). An entry that explains no difference also fails, so the list cannot go stale.
"""

from __future__ import annotations

import copy
import dataclasses
import fnmatch
import functools
import gzip
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pygame
import pytest
from scripts.record_golden_traces import GAME_SCENES, golden_path, record_trace

from glitchygames.examples.clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH
from glitchygames.examples.clockwork_keep.drawing import draw_tinker
from glitchygames.examples.clockwork_keep.player import Tinker
from glitchygames.pixel_snap import PixelSnapMode, snap_to_pixel
from glitchygames.tracing import TraceReader, decode_frame, read_trace, write_trace
from glitchygames.world import CULL_MARGIN_PIXELS, is_world_positioned

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from glitchygames.scenes import Scene
    from glitchygames.tracing import StableSpriteIds

# Marks an ExpectedDifference without a pinned value (None is a real value, so it can't be used)
NO_EXPECTED_VALUE: Any = object()
MISSING_EXPECTATION_MESSAGE = 'An ExpectedDifference needs an expected value or a rule'
# The seeded-reproducibility test: --random-seed value and frames per run
SEEDED_TRACE_SEED = 123
SEEDED_TRACE_FRAME_COUNT = 120


@dataclass(frozen=True)
class SpriteWorldSample:
    """One world sprite after a frame of the current run.

    Attributes:
        world_x: The sprite's world x.
        world_y: The sprite's world y.
        rect: The sprite's rect as [x, y, width, height] (as the trace records it).
        hidden: Whether the game hid the sprite (``hidden``).

    """

    world_x: float
    world_y: float
    rect: list[int]
    hidden: bool


@dataclass(frozen=True)
class FrameWorldSample:
    """World data of the current run after one frame, which the trace does not record.

    Attributes:
        camera_x: The camera's world x.
        camera_y: The camera's world y.
        shake_offset: The camera's WORLD shake offset.
        snap_mode: The scene's PIXEL_SNAP_MODE.
        screen_size: The display surface size (what the engine culls against).
        sprites: Each world sprite's sample, by trace id.

    """

    camera_x: float
    camera_y: float
    shake_offset: tuple[float, float]
    snap_mode: PixelSnapMode
    screen_size: tuple[int, int]
    sprites: dict[str, SpriteWorldSample]


class WorldSampler:
    """A record_trace frame observer that keeps each frame's world sample."""

    def __init__(self) -> None:
        """Start with no frames sampled."""
        self.frames: dict[int, FrameWorldSample] = {}

    def __call__(self, *, frame_number: int, scene: Scene, sprite_ids: StableSpriteIds) -> None:
        """Sample the camera and every world sprite of the active scene.

        Args:
            frame_number: The frame just run.
            scene: The active scene after the frame.
            sprite_ids: The run's sprite ids (the trace's ids).

        """
        camera = scene.camera
        display_surface = pygame.display.get_surface()
        assert display_surface is not None
        self.frames[frame_number] = FrameWorldSample(
            camera_x=camera.world_x,
            camera_y=camera.world_y,
            shake_offset=camera.shake_effect.offset,
            snap_mode=scene.PIXEL_SNAP_MODE,
            screen_size=display_surface.get_size(),
            sprites={
                sprite_ids.id_for(sprite): SpriteWorldSample(
                    world_x=sprite.world_x,
                    world_y=sprite.world_y,
                    rect=[sprite.rect.x, sprite.rect.y, sprite.rect.width, sprite.rect.height],
                    hidden=bool(getattr(sprite, 'hidden', False)),
                )
                for sprite in scene.all_sprites.sprites()
                if is_world_positioned(sprite)
            },
        )


@dataclass(frozen=True)
class ExpectedDifference:
    """Justified differences between a baseline trace and the current run.

    An entry explains a difference when the field is the same, the frame is in ``frames``, the
    sprite id matches ``sprite_pattern`` (fnmatch, e.g. ``'GroundSegment#*'``; ``''`` matches
    frame-level fields), and either the current value equals ``expected``, ``rule`` returns
    True for (baseline value, current value), or ``world_rule`` returns True for the
    difference and the frame's world sample.

    Attributes:
        frames: The frames the entry covers (``range(n, n + 1)`` for one frame).
        sprite_pattern: fnmatch pattern for sprite ids (``<ClassName>#<n>``).
        field: ``'rect'`` (list), ``'visible'`` (bool) or ``'present'`` (bool: is the sprite
            in the current run) for a sprite; ``'scene'`` or ``'frame_count'`` for the frame
            or the whole trace.
        reason: Why the difference is expected.
        expected: The value the current run must now produce.
        rule: Accepts (baseline value, current value) for a systematic difference.
        world_rule: Accepts (difference, the frame's world sample) for a difference whose
            cause is proven from world and camera positions; never called without a sample.

    """

    frames: range
    sprite_pattern: str
    field: str
    reason: str
    expected: Any = NO_EXPECTED_VALUE
    rule: Callable[[Any, Any], bool] | None = dataclasses.field(default=None, compare=False)
    world_rule: Callable[[TraceDifference, FrameWorldSample], bool] | None = dataclasses.field(
        default=None, compare=False
    )

    def __post_init__(self) -> None:
        """Reject an entry that would explain any value.

        Raises:
            ValueError: If neither an expected value nor a rule is given.

        """
        if self.expected is NO_EXPECTED_VALUE and self.rule is None and self.world_rule is None:
            raise ValueError(MISSING_EXPECTATION_MESSAGE)

    def explains(
        self, difference: TraceDifference, *, world_sample: FrameWorldSample | None = None
    ) -> bool:
        """Report whether this entry explains a difference.

        Args:
            difference: A difference found between the traces.
            world_sample: The current run's world sample for the difference's frame, if
                sampled.

        Returns:
            True if the difference matches this entry.

        """
        if (
            difference.field != self.field
            or difference.frame not in self.frames
            or not fnmatch.fnmatchcase(difference.sprite_id, self.sprite_pattern)
        ):
            return False
        if self.expected is not NO_EXPECTED_VALUE and difference.current == self.expected:
            return True
        if self.rule is not None and self.rule(difference.baseline, difference.current):
            return True
        return (
            self.world_rule is not None
            and world_sample is not None
            and self.world_rule(difference, world_sample)
        )


@dataclass(frozen=True)
class TraceDifference:
    """A difference found between the baseline and the current run.

    Attributes:
        frame: The frame number.
        sprite_id: The sprite id, or ``''`` for a frame-level field.
        field: Which field differs.
        baseline: The baseline value.
        current: The current value.

    """

    frame: int
    sprite_id: str
    field: str
    baseline: Any
    current: Any

    @property
    def key(self) -> tuple[int, str, str]:
        """The (frame, sprite id, field) that identifies this difference."""
        return (self.frame, self.sprite_id, self.field)


def engine_rect(sprite: SpriteWorldSample, frame: FrameWorldSample) -> list[int]:
    """The rect the engine places a world sprite at: snap(world) - snap(camera) - snap(shake).

    Returns:
        [x, y, width, height].

    """
    shake_x, shake_y = frame.shake_offset
    mode = frame.snap_mode
    return [
        snap_to_pixel(sprite.world_x, mode)
        - snap_to_pixel(frame.camera_x, mode)
        - snap_to_pixel(shake_x, mode),
        snap_to_pixel(sprite.world_y, mode)
        - snap_to_pixel(frame.camera_y, mode)
        - snap_to_pixel(shake_y, mode),
        *sprite.rect[2:],
    ]


def camera_apply_rect(
    sprite: SpriteWorldSample, frame: FrameWorldSample, *, world_y_offset: float = 0.0
) -> list[int]:
    """The rect the games' old apply_camera gave: Camera2D.apply, round(world - camera - shake).

    Args:
        sprite: The sprite's world sample.
        frame: The frame's world sample.
        world_y_offset: Added to the sprite's world y (where the old run had the sprite).

    Returns:
        [x, y, width, height].

    """
    shake_x, shake_y = frame.shake_offset
    return [
        round(sprite.world_x - frame.camera_x - shake_x),
        round(sprite.world_y + world_y_offset - frame.camera_y - shake_y),
        *sprite.rect[2:],
    ]


@functools.cache
def tinker_feet_margin_pixels() -> int:
    """Transparent rows below the tinker's feet (its image is taller than the drawn figure).

    Before the pose fix, the first ground check of a new floor ran before any pose was drawn:
    a blank image's hitbox is the whole image, so the tinker stood this many pixels too high
    until the next tick.

    Returns:
        The image height minus the bottom of the drawn idle pose.

    """
    image = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT), pygame.SRCALPHA)
    draw_tinker(image, Tinker.IDLE, facing_right=True, animation_timer=0.0)
    return PLAYER_HEIGHT - image.get_bounding_rect().bottom


def _sprite_sample(
    difference: TraceDifference, frame: FrameWorldSample
) -> SpriteWorldSample | None:
    return frame.sprites.get(difference.sprite_id)


def separately_snapped(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Spec 2.2: the same world and camera positions give the baseline by the old formula.

    The current rect is snap(world) - snap(camera); the baseline is round(world - camera) of
    the very same positions. They differ by a pixel when the fractions of world and camera
    positions straddle a half.

    Returns:
        True if both rects follow from this frame's positions.

    """
    sprite = _sprite_sample(difference, frame)
    return (
        sprite is not None
        and difference.current == engine_rect(sprite, frame)
        and difference.baseline == camera_apply_rect(sprite, frame)
    )


def stood_on_blank_image_hitbox(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Pose fix: the old run stood the tinker tinker_feet_margin_pixels() higher, same camera.

    Returns:
        True if the baseline is the old formula with the tinker raised by the margin.

    """
    sprite = _sprite_sample(difference, frame)
    return (
        sprite is not None
        and difference.current == engine_rect(sprite, frame)
        and difference.baseline
        == camera_apply_rect(sprite, frame, world_y_offset=-tinker_feet_margin_pixels())
    )


def settling_after_blank_image_hitbox(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Pose fix, the frames after it: the old tinker was still dropping onto its floor.

    Standing too high (stood_on_blank_image_hitbox), the old tinker fell its last pixels over
    the next frames, and the old camera, aimed at it, trailed by a fraction of a pixel. The
    current rect is exactly the engine's; the baseline is one pixel off the old formula on
    this run's positions, in y only. Not an exact proof: the old positions are not sampled.
    Replaying the old pose order and round(world - camera) reproduces every baseline rect of
    the trace exactly (see the Task 6 report).

    Returns:
        True if the current rect is the engine's and the baseline is 1 px off in y only.

    """
    sprite = _sprite_sample(difference, frame)
    if sprite is None or difference.current != engine_rect(sprite, frame):
        return False
    old_rect = camera_apply_rect(sprite, frame)
    return (
        difference.baseline[0] == old_rect[0]
        and abs(difference.baseline[1] - old_rect[1]) == 1
        and difference.baseline[2:] == old_rect[2:]
    )


def culled_outside_margin(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Engine culling: the sprite is entirely outside the screen grown by CULL_MARGIN_PIXELS.

    Returns:
        True if the sprite became invisible and is off screen beyond the margin, not hidden.

    """
    sprite = _sprite_sample(difference, frame)
    cull_rect = pygame.Rect((0, 0), frame.screen_size).inflate(
        2 * CULL_MARGIN_PIXELS, 2 * CULL_MARGIN_PIXELS
    )
    return (
        sprite is not None
        and difference.baseline is True
        and difference.current is False
        and not sprite.hidden
        and not cull_rect.colliderect(pygame.Rect(sprite.rect))
    )


# Every frame of a run, for entries that hold wherever their rule proves them
ALL_FRAMES = range(1_000_000)

# Filled in by later tasks of the world-space plan; every entry must say why it is expected.
EXPECTED_DIFFERENCES: dict[str, list[ExpectedDifference]] = {
    'clockwork_keep': [
        ExpectedDifference(
            frames=ALL_FRAMES,
            sprite_pattern='*',
            field='visible',
            world_rule=culled_outside_margin,
            reason=(
                'Engine culling (spec 2.4): Clockwork Keep never culled, so sprites far off '
                'screen (and the tinker before the camera swoops down to it, or after it is '
                'placed on the elevator) were visible; the engine hides them beyond '
                'CULL_MARGIN_PIXELS'
            ),
        ),
        ExpectedDifference(
            frames=ALL_FRAMES,
            sprite_pattern='*',
            field='rect',
            world_rule=separately_snapped,
            reason=(
                'Spec 2.2: sprite and camera are snapped separately, snap(world) - '
                'snap(camera), instead of round(world - camera); the bobbing cogs and the '
                'gliding camera both have fractions'
            ),
        ),
        ExpectedDifference(
            frames=range(1),
            sprite_pattern='Tinker#0',
            field='rect',
            world_rule=stood_on_blank_image_hitbox,
            reason=(
                'Pose fix (spec 1): the first ground check used to run before any pose was '
                'drawn, on the blank image, standing the tinker 2 px too high'
            ),
        ),
        ExpectedDifference(
            frames=range(351, 595),
            sprite_pattern='Tinker#1',
            field='rect',
            world_rule=stood_on_blank_image_hitbox,
            reason=(
                'Pose fix (spec 1): during the elevator ride the arriving floor shows its '
                'capture tick, whose ground check used to run on the blank image (2 px high)'
            ),
        ),
        ExpectedDifference(
            frames=range(1, 10),
            sprite_pattern='*',
            field='rect',
            world_rule=settling_after_blank_image_hitbox,
            reason=(
                'Pose fix (spec 1): after standing 2 px high on frame 0 the old tinker fell '
                'onto the floor and the old camera trailed it by a fraction of a pixel'
            ),
        ),
        ExpectedDifference(
            frames=range(595, 596),
            sprite_pattern='Tinker#1',
            field='rect',
            world_rule=settling_after_blank_image_hitbox,
            reason=(
                'Pose fix (spec 1): on the first frame after the ride the old tinker dropped '
                'its 2 px and the old camera followed it'
            ),
        ),
    ],
    'brave_adventurer': [],
    'brave_adventurer_papyrus': [],
    'paddleslap': [],
}


def _sprite_fields(frame: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        sprite['id']: {'rect': sprite['rect'], 'visible': sprite['visible']}
        for sprite in frame['sprites']
    }


def _frame_differences(
    *, baseline_frame: dict[str, Any], current_frame: dict[str, Any]
) -> list[TraceDifference]:
    frame_number = baseline_frame['frame']
    differences: list[TraceDifference] = []
    if baseline_frame['scene'] != current_frame['scene']:
        differences.append(
            TraceDifference(
                frame=frame_number,
                sprite_id='',
                field='scene',
                baseline=baseline_frame['scene'],
                current=current_frame['scene'],
            )
        )
    baseline_sprites = _sprite_fields(baseline_frame)
    current_sprites = _sprite_fields(current_frame)
    # Baseline order first, then sprites only the current run has
    sprite_ids = list(baseline_sprites) + [
        sprite_id for sprite_id in current_sprites if sprite_id not in baseline_sprites
    ]
    for sprite_id in sprite_ids:
        baseline_sprite = baseline_sprites.get(sprite_id)
        current_sprite = current_sprites.get(sprite_id)
        if baseline_sprite is None or current_sprite is None:
            differences.append(
                TraceDifference(
                    frame=frame_number,
                    sprite_id=sprite_id,
                    field='present',
                    baseline=baseline_sprite is not None,
                    current=current_sprite is not None,
                )
            )
            continue
        differences.extend(
            TraceDifference(
                frame=frame_number,
                sprite_id=sprite_id,
                field=field_name,
                baseline=baseline_sprite[field_name],
                current=current_sprite[field_name],
            )
            for field_name in ('rect', 'visible')
            if baseline_sprite[field_name] != current_sprite[field_name]
        )
    return differences


def trace_differences(
    *, baseline: dict[str, Any], current: dict[str, Any]
) -> list[TraceDifference]:
    """Compare two traces frame by frame.

    Args:
        baseline: The recorded golden trace.
        current: The trace of the current run.

    Returns:
        Every difference, in frame order.

    """
    differences: list[TraceDifference] = []
    baseline_frames = baseline['frames']
    current_frames = current['frames']
    if len(baseline_frames) != len(current_frames):
        differences.append(
            TraceDifference(
                frame=min(len(baseline_frames), len(current_frames)),
                sprite_id='',
                field='frame_count',
                baseline=len(baseline_frames),
                current=len(current_frames),
            )
        )
    for baseline_frame, current_frame in zip(baseline_frames, current_frames, strict=False):
        differences.extend(
            _frame_differences(baseline_frame=baseline_frame, current_frame=current_frame)
        )
    return differences


def unexplained_and_stale(
    *,
    differences: list[TraceDifference],
    expected: list[ExpectedDifference],
    world_samples: Mapping[int, FrameWorldSample] | None = None,
) -> tuple[list[TraceDifference], list[ExpectedDifference]]:
    """Split differences into unexplained ones and expected ones that did not occur.

    Args:
        differences: The differences found.
        expected: The listed, justified differences.
        world_samples: The current run's world samples by frame (for world rules).

    Returns:
        (differences not listed, listed differences that no longer occur).

    """
    world_samples = world_samples or {}
    used_entries: set[int] = set()
    unexplained: list[TraceDifference] = []
    for difference in differences:
        world_sample = world_samples.get(difference.frame)
        explaining_entries = [
            entry_index
            for entry_index, entry in enumerate(expected)
            if entry.explains(difference, world_sample=world_sample)
        ]
        if explaining_entries:
            used_entries.update(explaining_entries)
        else:
            unexplained.append(difference)
    stale = [entry for entry_index, entry in enumerate(expected) if entry_index not in used_entries]
    return unexplained, stale


def _describe(difference: TraceDifference) -> str:
    return (
        f'frame {difference.frame}, sprite {difference.sprite_id or "(frame)"}, '
        f'{difference.field}: baseline {difference.baseline!r}, current {difference.current!r}'
    )


def test_expected_differences_cover_every_game():
    """Every recorded game has an entry, so a new game cannot slip past the list."""
    assert set(EXPECTED_DIFFERENCES) == set(GAME_SCENES)


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_game_matches_golden_trace(game_key):
    """Replaying the game's script reproduces its golden trace, up to listed differences."""
    baseline = read_trace(path=golden_path(game_key))
    world_sampler = WorldSampler()
    current = record_trace(
        game_key, frame_count=len(baseline['frames']), frame_observer=world_sampler
    )

    assert current['game'] == baseline['game']
    assert current['frame_seconds'] == baseline['frame_seconds']
    unexplained, stale = unexplained_and_stale(
        differences=trace_differences(baseline=baseline, current=current),
        expected=EXPECTED_DIFFERENCES[game_key],
        world_samples=world_sampler.frames,
    )
    if unexplained:
        pytest.fail(
            f'{game_key}: {len(unexplained)} unexpected difference(s); first at '
            f'{_describe(unexplained[0])}',
            pytrace=False,
        )
    if stale:
        pytest.fail(
            f'{game_key}: {len(stale)} expected difference(s) no longer occur; first: {stale[0]}',
            pytrace=False,
        )


def test_same_random_seed_gives_identical_paddleslap_traces():
    """--random-seed 123 twice plays PaddleSlap identically; seed 124 plays differently.

    Every random draw (serves, spawn positions, colours, shakes) comes from the run's seeded
    streams, so the harness needs no patching of the games' randomness.
    """
    first_run = record_trace(
        'paddleslap', frame_count=SEEDED_TRACE_FRAME_COUNT, random_seed=SEEDED_TRACE_SEED
    )
    second_run = record_trace(
        'paddleslap', frame_count=SEEDED_TRACE_FRAME_COUNT, random_seed=SEEDED_TRACE_SEED
    )
    other_seed_run = record_trace(
        'paddleslap', frame_count=SEEDED_TRACE_FRAME_COUNT, random_seed=SEEDED_TRACE_SEED + 1
    )

    assert second_run == first_run
    assert trace_differences(baseline=first_run, current=other_seed_run) != []


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_committed_trace_reencodes_to_identical_bytes(game_key, tmp_path):
    """Decoding then encoding a committed trace gives back every frame and the same bytes."""
    path = golden_path(game_key)
    baseline = read_trace(path=path)
    reencoded_path = tmp_path / path.name
    write_trace(baseline, path=reencoded_path)

    assert read_trace(path=reencoded_path) == baseline
    assert reencoded_path.read_bytes() == path.read_bytes()


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_streaming_reader_matches_read_trace_and_frame_by_frame_decoding(game_key):
    """TraceReader, read_trace and decode_frame chained by hand give the same frames."""
    path = golden_path(game_key)
    trace = read_trace(path=path)
    with TraceReader(path=path) as reader:
        streamed_frames = list(reader)
        streamed_header = reader.header

    assert streamed_frames == trace['frames']
    assert {**streamed_header, 'frames': streamed_frames} == trace
    previous_frame = None
    for line_record, streamed_frame in zip(_line_records(path), streamed_frames, strict=True):
        previous_frame = decode_frame(line_record=line_record, previous_frame_record=previous_frame)
        assert previous_frame == streamed_frame


def _line_records(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, 'rt', encoding='utf-8') as trace_file:
        return [json.loads(line) for line in trace_file][1:]


@pytest.mark.parametrize('game_key', sorted(GAME_SCENES))
def test_altered_middle_frame_is_found_at_its_frame_and_sprite(game_key, tmp_path):
    """Delta encoding hides nothing: one value changed in one middle frame is one difference."""
    baseline = read_trace(path=golden_path(game_key))
    altered = copy.deepcopy(baseline)
    middle_frame = next(
        frame for frame in altered['frames'][len(altered['frames']) // 2 :] if frame['sprites']
    )
    altered_sprite = middle_frame['sprites'][len(middle_frame['sprites']) // 2]
    altered_sprite['rect'][0] += 1
    altered_path = tmp_path / 'altered.jsonl.gz'
    write_trace(altered, path=altered_path)

    differences = trace_differences(baseline=baseline, current=read_trace(path=altered_path))

    assert [difference.key for difference in differences] == [
        (middle_frame['frame'], altered_sprite['id'], 'rect')
    ]
    unexplained, _ = unexplained_and_stale(differences=differences, expected=[])
    assert unexplained == differences


class TestTraceComparison:
    """The comparison itself: it finds, explains and goes stale exactly as documented."""

    @staticmethod
    def _trace(*frames: dict[str, Any]) -> dict[str, Any]:
        return {'game': 'example', 'frame_seconds': 1.0 / 60.0, 'frames': list(frames)}

    @staticmethod
    def _frame(frame_number: int, *sprites: dict[str, Any], scene: str = 'Example'):
        return {'frame': frame_number, 'scene': scene, 'sprites': list(sprites)}

    @staticmethod
    def _sprite(sprite_id: str, rect: list[int], *, visible: bool = True) -> dict[str, Any]:
        return {'id': sprite_id, 'rect': rect, 'visible': visible}

    def test_identical_traces_have_no_differences(self):
        trace = self._trace(self._frame(0, self._sprite('Ball#0', [1, 2, 3, 4])))
        assert trace_differences(baseline=trace, current=trace) == []

    def test_rect_visible_scene_and_presence_differences_are_found(self):
        baseline = self._trace(
            self._frame(0, self._sprite('Ball#0', [1, 2, 3, 4]), self._sprite('Wall#0', [0] * 4)),
        )
        current = self._trace(
            self._frame(
                0,
                self._sprite('Ball#0', [1, 3, 3, 4], visible=False),
                self._sprite('Coin#0', [5, 5, 5, 5]),
                scene='Other',
            ),
        )
        keys = [
            difference.key for difference in trace_differences(baseline=baseline, current=current)
        ]
        assert keys == [
            (0, '', 'scene'),
            (0, 'Ball#0', 'rect'),
            (0, 'Ball#0', 'visible'),
            (0, 'Wall#0', 'present'),
            (0, 'Coin#0', 'present'),
        ]

    def test_frame_count_difference_is_found(self):
        baseline = self._trace(self._frame(0), self._frame(1))
        current = self._trace(self._frame(0))
        differences = trace_differences(baseline=baseline, current=current)
        assert [difference.key for difference in differences] == [(1, '', 'frame_count')]

    @classmethod
    def _one_rect_change(cls, *, frame_count: int = 1, sprite_id: str = 'Ball#0'):
        """Traces where one sprite's x moves from 1 to 2 on every frame."""
        baseline = cls._trace(*[
            cls._frame(frame_number, cls._sprite(sprite_id, [1, 2, 3, 4]))
            for frame_number in range(frame_count)
        ])
        current = cls._trace(*[
            cls._frame(frame_number, cls._sprite(sprite_id, [2, 2, 3, 4]))
            for frame_number in range(frame_count)
        ])
        return trace_differences(baseline=baseline, current=current)

    def test_listed_difference_with_its_value_is_explained(self):
        expected = [
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='Ball#0',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(), expected=expected
        )
        assert unexplained == []
        assert stale == []

    def test_listed_difference_with_another_value_is_unexplained(self):
        expected = [
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='Ball#0',
                field='rect',
                expected=[3, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(), expected=expected
        )
        assert [difference.key for difference in unexplained] == [(0, 'Ball#0', 'rect')]
        assert stale == expected

    def test_absent_sprite_is_explained_by_expected_false(self):
        baseline = self._trace(self._frame(0, self._sprite('Coin#0', [0, 0, 1, 1])))
        current = self._trace(self._frame(0))
        expected = [
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='Coin#0',
                field='present',
                expected=False,
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=trace_differences(baseline=baseline, current=current),
            expected=expected,
        )
        assert unexplained == []
        assert stale == []

    def test_unlisted_difference_is_unexplained(self):
        unexplained, stale = unexplained_and_stale(differences=self._one_rect_change(), expected=[])
        assert [difference.key for difference in unexplained] == [(0, 'Ball#0', 'rect')]
        assert stale == []

    def test_frame_range_explains_every_frame_inside_it_only(self):
        expected = [
            ExpectedDifference(
                frames=range(1, 3),
                sprite_pattern='Ball#0',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=4), expected=expected
        )
        assert [difference.frame for difference in unexplained] == [0, 3]
        assert stale == []

    def test_sprite_pattern_matches_with_fnmatch(self):
        expected = [
            ExpectedDifference(
                frames=range(2),
                sprite_pattern='GroundSegment#*',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        ground_unexplained, _ = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=2, sprite_id='GroundSegment#7'),
            expected=expected,
        )
        wall_unexplained, wall_stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=2, sprite_id='StoneWall#0'),
            expected=expected,
        )
        assert ground_unexplained == []
        assert len(wall_unexplained) == 2
        assert wall_stale == expected

    def test_rule_explains_the_differences_it_accepts(self):
        def shifted_right_by_one(baseline_value, current_value):
            return current_value == [baseline_value[0] + 1, *baseline_value[1:]]

        def shifted_left_by_one(baseline_value, current_value):
            return current_value == [baseline_value[0] - 1, *baseline_value[1:]]

        accepted_unexplained, accepted_stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=3),
            expected=[
                ExpectedDifference(
                    frames=range(3),
                    sprite_pattern='*',
                    field='rect',
                    rule=shifted_right_by_one,
                    reason='test',
                )
            ],
        )
        rejected_unexplained, _ = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=3),
            expected=[
                ExpectedDifference(
                    frames=range(3),
                    sprite_pattern='*',
                    field='rect',
                    rule=shifted_left_by_one,
                    reason='test',
                )
            ],
        )
        assert accepted_unexplained == []
        assert accepted_stale == []
        assert len(rejected_unexplained) == 3

    def test_range_entry_that_explains_nothing_is_stale(self):
        trace = self._trace(self._frame(0, self._sprite('Ball#0', [1, 2, 3, 4])))
        expected = [
            ExpectedDifference(
                frames=range(100),
                sprite_pattern='*',
                field='rect',
                rule=lambda baseline_value, current_value: True,
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=trace_differences(baseline=trace, current=trace), expected=expected
        )
        assert unexplained == []
        assert stale == expected

    def test_entry_needs_an_expected_value_or_a_rule(self):
        with pytest.raises(ValueError, match='expected value or a rule'):
            ExpectedDifference(frames=range(1), sprite_pattern='*', field='rect', reason='test')

    @staticmethod
    def _world_frame(*, camera_y: float, sprite: SpriteWorldSample) -> FrameWorldSample:
        return FrameWorldSample(
            camera_x=0.0,
            camera_y=camera_y,
            shake_offset=(0.0, 0.0),
            snap_mode=PixelSnapMode.NEAREST_HALF_UP,
            screen_size=(800, 480),
            sprites={'Cog#0': sprite},
        )

    def test_world_rule_explains_with_the_frames_world_sample_only(self):
        # Camera 0.4, cog 10.7: round(10.7 - 0.4) = 10 before, snap(10.7) - snap(0.4) = 11 now
        sprite = SpriteWorldSample(world_x=0.0, world_y=10.7, rect=[0, 11, 16, 16], hidden=False)
        frame = self._world_frame(camera_y=0.4, sprite=sprite)
        difference = TraceDifference(
            frame=0,
            sprite_id='Cog#0',
            field='rect',
            baseline=[0, 10, 16, 16],
            current=[0, 11, 16, 16],
        )
        entry = ExpectedDifference(
            frames=range(1),
            sprite_pattern='*',
            field='rect',
            world_rule=separately_snapped,
            reason='test',
        )
        unexplained, stale = unexplained_and_stale(
            differences=[difference], expected=[entry], world_samples={0: frame}
        )
        unsampled_unexplained, _ = unexplained_and_stale(differences=[difference], expected=[entry])
        assert unexplained == []
        assert stale == []
        assert unsampled_unexplained == [difference]

    def test_separately_snapped_rejects_a_baseline_the_old_formula_does_not_give(self):
        sprite = SpriteWorldSample(world_x=0.0, world_y=10.7, rect=[0, 11, 16, 16], hidden=False)
        frame = self._world_frame(camera_y=0.4, sprite=sprite)
        difference = TraceDifference(
            frame=0,
            sprite_id='Cog#0',
            field='rect',
            baseline=[0, 9, 16, 16],
            current=[0, 11, 16, 16],
        )
        assert not separately_snapped(difference, frame)

    @pytest.mark.parametrize(
        ('rect', 'hidden', 'explained'),
        [
            ([0, 480 + CULL_MARGIN_PIXELS, 16, 16], False, True),
            ([0, 480 + CULL_MARGIN_PIXELS - 1, 16, 16], False, False),
            ([0, 100, 16, 16], False, False),
            ([0, 900, 16, 16], True, False),
        ],
        ids=['beyond_margin', 'inside_margin', 'on_screen', 'hidden_by_the_game'],
    )
    def test_culled_outside_margin_needs_the_sprite_beyond_the_margin(
        self, rect, hidden, explained
    ):
        sprite = SpriteWorldSample(world_x=0.0, world_y=0.0, rect=rect, hidden=hidden)
        frame = self._world_frame(camera_y=0.0, sprite=sprite)
        difference = TraceDifference(
            frame=0, sprite_id='Cog#0', field='visible', baseline=True, current=False
        )
        assert culled_outside_margin(difference, frame) is explained

    def test_entry_with_only_a_world_rule_is_accepted(self):
        entry = ExpectedDifference(
            frames=range(1),
            sprite_pattern='*',
            field='rect',
            world_rule=separately_snapped,
            reason='test',
        )
        assert entry.world_rule is separately_snapped
