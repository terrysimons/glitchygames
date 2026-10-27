"""Golden traces: every game older than the world-space change plays exactly as it did before it.

The baselines in ``tests/world/golden/`` were recorded by ``scripts/record_golden_traces.py``
before any world-space engine change (plans/2026-10-18-engine-world-space.md), for the games
that existed then (``GOLDEN_TRACE_GAMES``; later games are covered by their golden replays in
their members' ``tests/fixtures/replays/``). Each test
replays the same scripted, deterministic run and compares every sprite's rect and visibility,
frame by frame.

A difference fails the test unless an entry in ``EXPECTED_DIFFERENCES`` explains it: same
field, frame inside the entry's range (or any frame), sprite id matching its pattern, and
either the current value equal to the entry's pinned ``expected`` value, the entry's ``rule``
accepting the (baseline, current) pair, or its ``world_rule`` accepting the difference given
the frame's world sample (world and camera positions the trace does not record, read from the
current run). An entry that explains no difference also fails, so the list cannot go stale.
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
from scripts.record_golden_traces import (
    GAME_SCENES,
    GOLDEN_DIRECTORY,
    GOLDEN_TRACE_GAMES,
    SCRIPT_BUILDERS,
    golden_path,
)

from brave_adventurer import constants as brave_constants
from brave_adventurer.drawing import draw_player, draw_scarab
from brave_adventurer.player import Player as AdventurerPlayer
from brave_adventurer_core import constants as brave_core_constants
from brave_adventurer_papyrus.player import PapyrusPlayer
from brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
)
from clockwork_keep.constants import PLAYER_HEIGHT, PLAYER_WIDTH
from clockwork_keep.drawing import draw_tinker
from clockwork_keep.player import Tinker
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.logical_names import logical_name
from glitchygames.pixel_snap import PixelSnapMode, snap_to_pixel
from glitchygames.replay.tools.golden_traces import record_trace
from glitchygames.tracing import (
    TRACE_FORMAT_VERSION,
    TraceReader,
    decode_frame,
    read_trace,
    write_trace,
)
from glitchygames.world import CULL_MARGIN_PIXELS, is_world_positioned

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from glitchygames.scenes import Scene
    from glitchygames.tracing import StableSpriteIds

# Marks an ExpectedDifference without a pinned value (None is a real value, so it can't be used)
NO_EXPECTED_VALUE: Any = object()
MISSING_EXPECTATION_MESSAGE = 'An ExpectedDifference needs an expected value or a rule'
# A baseline's suffix after its game key (scripts/record_golden_traces.py golden_path)
GOLDEN_TRACE_SUFFIX = '.jsonl.gz'


class AmbiguousExpectedDifferenceError(ValueError):
    """A difference is explained by more than one entry: each must have exactly one cause."""


@dataclass(frozen=True)
class SpriteWorldSample:
    """One world sprite after a frame of the current run.

    Attributes:
        world_x: The sprite's world x.
        world_y: The sprite's world y.
        rect: The sprite's rect as [x, y, width, height] (as the trace records it).
        hidden: Whether the game hid the sprite (``hidden``).
        draw_offset: The sprite's draw_offset (an anchored animation frame's offset, which the
            engine adds to the snapped position, as Papyrus's old apply_camera did; (0, 0) for
            sprites without one).

    """

    world_x: float
    world_y: float
    rect: list[int]
    hidden: bool
    draw_offset: tuple[int, int] = (0, 0)


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
        baseline_rects: The baseline trace's rects for this frame, by sprite id (attached by
            attach_baseline_rects before comparing; empty until then).

    """

    camera_x: float
    camera_y: float
    shake_offset: tuple[float, float]
    snap_mode: PixelSnapMode
    screen_size: tuple[int, int]
    sprites: dict[str, SpriteWorldSample]
    baseline_rects: dict[str, list[int]] = dataclasses.field(default_factory=dict)


def attach_baseline_rects(
    *, world_samples: Mapping[int, FrameWorldSample], baseline: dict[str, Any]
) -> dict[int, FrameWorldSample]:
    """Give each frame's world sample the baseline's rects for that frame.

    Rules that prove a difference from a whole frame (settled_onto_floor) need every sprite's
    baseline rect, not only the differing one's.

    Args:
        world_samples: The current run's world samples by frame.
        baseline: The baseline trace.

    Returns:
        The world samples with baseline_rects filled in.

    """
    baseline_rects_by_frame = {
        frame['frame']: {sprite['id']: sprite['rect'] for sprite in frame['sprites']}
        for frame in baseline['frames']
    }
    return {
        frame_number: dataclasses.replace(
            sample, baseline_rects=baseline_rects_by_frame.get(frame_number, {})
        )
        for frame_number, sample in world_samples.items()
    }


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
                    draw_offset=tuple(getattr(sprite, 'draw_offset', (0, 0))),
                )
                for sprite in scene.all_sprites.sprites()
                if is_world_positioned(sprite)
            },
        )


@dataclass(frozen=True)
class ExpectedDifference:
    """Justified differences between a baseline trace and the current run.

    An entry explains a difference when the field is the same, the frame is in ``frames`` (any
    frame when ``frames`` is None), the sprite id matches ``sprite_pattern`` (fnmatch, e.g.
    ``'GroundSegment#*'``; ``''`` matches frame-level fields), and either the current value
    equals ``expected``, ``rule`` returns True for (baseline value, current value), or
    ``world_rule`` returns True for the difference and the frame's world sample.

    Attributes:
        frames: The frames the entry covers (``range(n, n + 1)`` for one frame), or None for
            every frame (an entry whose rule proves each difference wherever it occurs).
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

    frames: range | None
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
            or (self.frames is not None and difference.frame not in self.frames)
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


# The snap mode the spec sets for every game (Scene.PIXEL_SNAP_MODE's default). The rules
# compute expected rects with it, never with the mode the run reports, so a game that snaps
# differently is caught rather than explained.
SPEC_SNAP_MODE = PixelSnapMode.NEAREST_HALF_UP

# A position's fractional part that NEAREST_HALF_UP rounds up and round() rounds to even
EXACT_HALF_FRACTION = 0.5


def engine_rect(
    sprite: SpriteWorldSample, frame: FrameWorldSample, *, mode: PixelSnapMode
) -> list[int]:
    """The rect the engine places a world sprite at: snap(world) - snap(camera) - snap(shake).

    Plus the sprite's draw_offset, which the engine adds (world.screen_position_for).

    Args:
        sprite: The sprite's world sample.
        frame: The frame's world sample.
        mode: The snap mode the expectation pins (not the run's).

    Returns:
        [x, y, width, height].

    """
    shake_x, shake_y = frame.shake_offset
    draw_offset_x, draw_offset_y = sprite.draw_offset
    return [
        snap_to_pixel(sprite.world_x, mode)
        - snap_to_pixel(frame.camera_x, mode)
        - snap_to_pixel(shake_x, mode)
        + draw_offset_x,
        snap_to_pixel(sprite.world_y, mode)
        - snap_to_pixel(frame.camera_y, mode)
        - snap_to_pixel(shake_y, mode)
        + draw_offset_y,
        *sprite.rect[2:],
    ]


def camera_apply_rect(
    sprite: SpriteWorldSample, frame: FrameWorldSample, *, world_y_offset: float = 0.0
) -> list[int]:
    """The rect the games' old apply_camera gave: Camera2D.apply, round(world - camera - shake).

    Plus the sprite's draw_offset: Papyrus's old player apply_camera added it to the rounded
    position. Every other old apply_camera ignored it, and those sprites' offset is (0, 0).

    Args:
        sprite: The sprite's world sample.
        frame: The frame's world sample.
        world_y_offset: Added to the sprite's world y (where the old run had the sprite).

    Returns:
        [x, y, width, height].

    """
    shake_x, shake_y = frame.shake_offset
    draw_offset_x, draw_offset_y = sprite.draw_offset
    return [
        round(sprite.world_x - frame.camera_x - shake_x) + draw_offset_x,
        round(sprite.world_y + world_y_offset - frame.camera_y - shake_y) + draw_offset_y,
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


@functools.cache
def adventurer_feet_margin_pixels() -> int:
    """Transparent rows below the Brave Adventurer figure's feet in its 48 px image.

    Before the pose fix, the first ground check ran before any pose was drawn, on the blank
    image, whose hitbox is the whole image: the adventurer stood this many pixels too high.

    Returns:
        The image height minus the bottom of the drawn idle pose.

    """
    image = pygame.Surface(
        (brave_constants.PLAYER_WIDTH, brave_constants.PLAYER_HEIGHT), pygame.SRCALPHA
    )
    draw_player(image, AdventurerPlayer.IDLE, facing_right=True, animation_timer=0.0)
    return brave_constants.PLAYER_HEIGHT - image.get_bounding_rect().bottom


@functools.cache
def scarab_feet_margin_pixels() -> int:
    """Transparent rows below a Brave Adventurer scarab's drawn underside.

    The old per-sprite culling set dirty = 0 on a culled sprite, and Scene.update() calls
    update() only on dirty sprites, so a scarab that was never on screen was never drawn: it
    collided on its blank image (hitbox = the whole image) and rolled this many pixels high.
    The underside does not change with the roll angle.

    Evidence (Task 7, scratch emulation of the old game on this branch): with the old culling
    (dirty = 0), the old pose order and the old manual camera restored, the run matches the
    baseline with 0 differences in 900 frames; restoring only the old culling's dirty = 0
    accounts for exactly the 3384 scarab rect differences.

    Returns:
        The image height minus the bottom of the drawn scarab.

    """
    image = pygame.Surface(
        (brave_constants.SCARAB_WIDTH, brave_constants.SCARAB_HEIGHT), pygame.SRCALPHA
    )
    draw_scarab(image, 0.0)
    return brave_constants.SCARAB_HEIGHT - image.get_bounding_rect().bottom


def _sprite_sample(
    difference: TraceDifference, frame: FrameWorldSample
) -> SpriteWorldSample | None:
    """The difference's sprite sample, or None if absent or the run is not in the spec mode.

    Returns:
        The sprite's world sample, or None.

    """
    if frame.snap_mode is not SPEC_SNAP_MODE:
        return None
    return frame.sprites.get(difference.sprite_id)


def within_one_pixel_per_axis(*, baseline: list[int], current: list[int]) -> bool:
    """Whether two rects have the same size and positions at most 1 px apart on each axis.

    Returns:
        True if the rects differ by at most one pixel in x and in y, and not in size.

    """
    return (
        abs(current[0] - baseline[0]) <= 1
        and abs(current[1] - baseline[1]) <= 1
        and current[2:] == baseline[2:]
    )


def _old_and_engine_formulas_give(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Whether this frame's positions give the baseline by the old formula, current by the engine.

    The current rect is snap(world) - snap(camera) (plus draw_offset); the baseline is
    round(world - camera) of the very same positions, at most 1 px apart per axis.

    Returns:
        True if both rects follow from this frame's positions.

    """
    sprite = _sprite_sample(difference, frame)
    return (
        sprite is not None
        and within_one_pixel_per_axis(baseline=difference.baseline, current=difference.current)
        and difference.current == engine_rect(sprite, frame, mode=SPEC_SNAP_MODE)
        and difference.baseline == camera_apply_rect(sprite, frame)
    )


def _differs_only_by_rounding_an_exact_half(
    difference: TraceDifference, frame: FrameWorldSample
) -> bool:
    """Whether every differing axis has a whole camera and shake and a world position at .5.

    Then snap(world) - snap(camera) and round(world - camera) can differ only in how the exact
    half is rounded: half up (the engine) or half to even (Python's round()).

    Returns:
        True if each axis whose position differs is such an exact half.

    """
    sprite = _sprite_sample(difference, frame)
    if sprite is None:
        return False
    shake_x, shake_y = frame.shake_offset
    axes = (
        (sprite.world_x, frame.camera_x, shake_x),
        (sprite.world_y, frame.camera_y, shake_y),
    )
    differing_axes = [
        axis
        for axis_index, axis in enumerate(axes)
        if difference.baseline[axis_index] != difference.current[axis_index]
    ]
    return bool(differing_axes) and all(
        camera % 1 == 0 and shake % 1 == 0 and world % 1 == EXACT_HALF_FRACTION
        for world, camera, shake in differing_axes
    )


def rounded_half_up_at_exact_half(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Spec 2.2's half-up rounding: a world position at exactly .5 under a whole camera.

    Python's round() rounds an exact half to even (round(10292.5) = 10292); the engine's
    NEAREST_HALF_UP rounds it up (10293). With a whole camera and shake that is the only
    possible cause of the 1 px difference.

    Returns:
        True if both rects follow from this frame's positions and each differing axis is
        such an exact half.

    """
    return _old_and_engine_formulas_give(
        difference, frame
    ) and _differs_only_by_rounding_an_exact_half(difference, frame)


def separately_snapped(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Spec 2.2: the same world and camera positions give the baseline by the old formula.

    The current rect is snap(world) - snap(camera); the baseline is round(world - camera) of
    the very same positions. They differ by a pixel when the fractions of world and camera
    positions straddle a half. A difference that is only an exact half rounded under a whole
    camera is rounded_half_up_at_exact_half's, not this rule's.

    Returns:
        True if both rects follow from this frame's positions, at most 1 px apart per axis.

    """
    return _old_and_engine_formulas_give(
        difference, frame
    ) and not _differs_only_by_rounding_an_exact_half(difference, frame)


def _old_sprite_stood_higher_by(
    difference: TraceDifference, frame: FrameWorldSample, *, margin_pixels: float
) -> bool:
    """Whether the old run had the sprite margin_pixels higher than today, same x and camera.

    Exact: the current rect is the engine's for this frame's positions, and the baseline is
    the old formula, round(world - camera - shake), with the sprite raised by the margin.

    Returns:
        True if both rects follow from this frame's positions and the margin.

    """
    sprite = _sprite_sample(difference, frame)
    return (
        sprite is not None
        and difference.current == engine_rect(sprite, frame, mode=SPEC_SNAP_MODE)
        and difference.baseline == camera_apply_rect(sprite, frame, world_y_offset=-margin_pixels)
    )


def stood_on_blank_image_hitbox(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Pose fix: the old run stood the tinker tinker_feet_margin_pixels() higher, same camera.

    Returns:
        True if the baseline is the old formula with the tinker raised by the margin.

    """
    return _old_sprite_stood_higher_by(difference, frame, margin_pixels=tinker_feet_margin_pixels())


def adventurer_stood_on_blank_image_hitbox(
    difference: TraceDifference, frame: FrameWorldSample
) -> bool:
    """Pose fix: the old run stood the adventurer adventurer_feet_margin_pixels() higher.

    Returns:
        True if the baseline is the old formula with the adventurer raised by the margin.

    """
    return _old_sprite_stood_higher_by(
        difference, frame, margin_pixels=adventurer_feet_margin_pixels()
    )


def _scarab_is_dropping_from_its_spawn_height(sprite: SpriteWorldSample) -> bool:
    """Whether a scarab is between its spawn height and its resting height (its first drop).

    A scarab spawns with its image bottom on the ground and today drops the margin until its
    drawn underside lands; it never comes back up into this band (it only falls, into pits).

    Returns:
        True while the scarab is strictly between the two heights.

    """
    spawn_world_y = brave_core_constants.GROUND_Y - brave_constants.SCARAB_HEIGHT
    return spawn_world_y < sprite.world_y < spawn_world_y + scarab_feet_margin_pixels()


def scarab_stood_on_blank_image_hitbox(
    difference: TraceDifference, frame: FrameWorldSample
) -> bool:
    """Old culling: an undrawn scarab rolled scarab_feet_margin_pixels() higher, same x.

    Exact for every frame after the scarab's first drop (old world y = today's - margin; the
    blank and drawn hitboxes share x and width, so x is unchanged). The drop itself is
    scarab_dropping_from_its_spawn_height.

    Returns:
        True if the baseline is the old formula with the scarab raised by the margin.

    """
    sprite = _sprite_sample(difference, frame)
    return (
        sprite is not None
        and not _scarab_is_dropping_from_its_spawn_height(sprite)
        and _old_sprite_stood_higher_by(
            difference, frame, margin_pixels=scarab_feet_margin_pixels()
        )
    )


def scarab_dropping_from_its_spawn_height(
    difference: TraceDifference, frame: FrameWorldSample
) -> bool:
    """Old culling, the first frames: today's scarab drops onto its drawn underside.

    The old, undrawn scarab already stood on its blank image at its spawn height, so the
    baseline is the old formula with the scarab exactly at GROUND_Y - SCARAB_HEIGHT.

    Returns:
        True if the scarab is dropping and the baseline puts the old one at its spawn height.

    """
    sprite = _sprite_sample(difference, frame)
    if sprite is None or not _scarab_is_dropping_from_its_spawn_height(sprite):
        return False
    spawn_world_y = brave_core_constants.GROUND_Y - brave_constants.SCARAB_HEIGHT
    return _old_sprite_stood_higher_by(
        difference, frame, margin_pixels=sprite.world_y - spawn_world_y
    )


def _old_camera_y_interval(frame: FrameWorldSample) -> tuple[float, float] | None:
    """The old camera y (plus WORLD shake) that gives every non-tinker baseline rect's y.

    Each non-tinker world sprite stood where it stands now (platforms and elevators do not
    move; cogs bob on game time, which the pose fix does not change), so its baseline y,
    round(world_y - camera_y - shake_y), bounds the old camera to a 1 px window. The old
    camera is also within half a pixel of the sampled one. Closed intervals accept an exact
    rounding tie either way.

    Returns:
        (lowest, highest) old camera y, or None when no single camera explains the frame.

    """
    _, shake_y = frame.shake_offset
    lowest = frame.camera_y - 0.5
    highest = frame.camera_y + 0.5
    for sprite_id, sprite in frame.sprites.items():
        baseline_rect = frame.baseline_rects.get(sprite_id)
        if baseline_rect is None or sprite_id.startswith(f'{Tinker.__name__}#'):
            continue
        lowest = max(lowest, sprite.world_y - shake_y - baseline_rect[1] - 0.5)
        highest = min(highest, sprite.world_y - shake_y - baseline_rect[1] + 0.5)
    if lowest > highest:
        return None
    return (lowest, highest)


def settled_onto_floor(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Pose fix, the frames after it: the old tinker was still dropping onto its floor.

    Standing too high (stood_on_blank_image_hitbox), the old tinker fell its last pixels over
    the next frames, and the old camera, aimed at it, trailed the sampled one by a fraction of
    a pixel. The proof: the current rect is exactly the engine's; one old camera y, within
    half a pixel of the sampled one, gives every non-tinker sprite's baseline y in this frame
    (_old_camera_y_interval); and under that same camera the baseline tinker is drawn from an
    old world y at most tinker_feet_margin_pixels() above today's. x and size are unchanged.

    Returns:
        True if one old camera and an old tinker within the margin give the baseline frame.

    """
    sprite = _sprite_sample(difference, frame)
    if sprite is None or difference.current != engine_rect(sprite, frame, mode=SPEC_SNAP_MODE):
        return False
    shake_x, shake_y = frame.shake_offset
    baseline_x, baseline_y, *baseline_size = difference.baseline
    if baseline_x != round(sprite.world_x - frame.camera_x - shake_x) or (
        baseline_size != sprite.rect[2:]
    ):
        return False
    camera_interval = _old_camera_y_interval(frame)
    if camera_interval is None:
        return False
    if not difference.sprite_id.startswith(f'{Tinker.__name__}#'):
        # Its own baseline y bounded the interval, so a non-empty interval explains it
        return difference.sprite_id in frame.baseline_rects
    lowest_camera_y, highest_camera_y = camera_interval
    # Old world_y - camera_y - shake_y over old world_y in [world_y - margin, world_y] and
    # camera_y in the interval; round() of it must reach the baseline y
    lowest_offset = sprite.world_y - tinker_feet_margin_pixels() - highest_camera_y - shake_y
    highest_offset = sprite.world_y - lowest_camera_y - shake_y
    return lowest_offset <= baseline_y + 0.5 and highest_offset >= baseline_y - 0.5


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


# Animation times sampled when measuring the primitives adventurer's poses (two seconds at
# 50 ms covers every cycle, as the player's own common_hitbox_x_range measurement does)
ADVENTURER_POSE_SAMPLE_TIMES = tuple(sample_index * 0.05 for sample_index in range(40))
# The poses the old player fell into a pit in: running off the ledge, idle once a pit wall
# stopped it (running to idle on zero speed), before idle to falling took over
ADVENTURER_OLD_FALL_POSES = (AdventurerPlayer.RUNNING, AdventurerPlayer.IDLE)
PAPYRUS_OLD_FALL_POSES = (PapyrusPlayer.RUNNING, PapyrusPlayer.IDLE)


def _edge_spread(*, old_edges: set[int], falling_edges: set[int]) -> int:
    """The largest distance between an old pose's hitbox edge and a falling pose's.

    Returns:
        The largest absolute difference between one old edge and one falling edge.

    """
    return max(
        abs(old_edge - falling_edge) for old_edge in old_edges for falling_edge in falling_edges
    )


@functools.cache
def adventurer_falling_pose_shift_pixels() -> int:
    """How far the primitives adventurer's hitbox edges move from an old pose to falling.

    Before the running to falling transition (BUGS.md #209 item 7), a player that ran off a
    ledge fell in its running pose, went idle when a pit wall stopped it (running to idle on
    zero speed) and only then falling (idle to falling). The pit walls stop the hitbox, so
    falling in its falling pose the player stops up to this many pixels from the old one.

    Returns:
        The largest change of the hitbox's left or right edge from a running or idle pose to
        a falling pose, over both facings.

    """
    image = pygame.Surface(
        (brave_constants.PLAYER_WIDTH, brave_constants.PLAYER_HEIGHT), pygame.SRCALPHA
    )
    shift = 0
    for facing_right in (True, False):
        edges: dict[str, dict[str, set[int]]] = {}
        for state in (*ADVENTURER_OLD_FALL_POSES, AdventurerPlayer.FALLING):
            edges[state] = {'left': set(), 'right': set()}
            for animation_time in ADVENTURER_POSE_SAMPLE_TIMES:
                image.fill((0, 0, 0, 0))
                draw_player(image, state, facing_right=facing_right, animation_timer=animation_time)
                visible = image.get_bounding_rect()
                edges[state]['left'].add(visible.left)
                edges[state]['right'].add(visible.right)
        for edge in ('left', 'right'):
            shift = max(
                shift,
                _edge_spread(
                    old_edges=set().union(
                        *(edges[state][edge] for state in ADVENTURER_OLD_FALL_POSES)
                    ),
                    falling_edges=edges[AdventurerPlayer.FALLING][edge],
                ),
            )
    return shift


@functools.cache
def papyrus_running_and_falling_poses() -> tuple[int, frozenset[int]]:
    """The Papyrus adventurer's old fall frames and its falling frame, from player.toml.

    The old player fell running, went idle when a pit wall stopped it, then falling (see
    adventurer_falling_pose_shift_pixels).

    Returns:
        (the largest change of the hitbox's left or right edge from a running or idle frame
        to a falling frame, over both facings; the running and idle frames' draw_offset y
        values, where the old run drew the falling player).

    """
    player = PapyrusPlayer(world_x=0.0, world_y=0.0, groups=pygame.sprite.LayeredDirty())
    shift = 0
    old_draw_offsets_y: set[int] = set()
    for facing_right in (True, False):
        player.facing_right = facing_right
        player.hitbox_flip_x = not facing_right
        edges: dict[str, dict[str, set[int]]] = {}
        for state in (*PAPYRUS_OLD_FALL_POSES, PapyrusPlayer.FALLING):
            edges[state] = {'left': set(), 'right': set()}
            player.set_animation(state)
            for frame_index in range(player.current_animation_frame_count):
                player.set_frame(frame_index)
                apply_transparency_and_scale(player)
                offset_x, _ = collision_rect_offset(player)
                hitbox_width = get_sprite_collision_rect(player).width
                edges[state]['left'].add(offset_x)
                edges[state]['right'].add(offset_x + hitbox_width)
                if state in PAPYRUS_OLD_FALL_POSES:
                    old_draw_offsets_y.add(player.draw_offset[1])
        for edge in ('left', 'right'):
            shift = max(
                shift,
                _edge_spread(
                    old_edges=set().union(
                        *(edges[state][edge] for state in PAPYRUS_OLD_FALL_POSES)
                    ),
                    falling_edges=edges[PapyrusPlayer.FALLING][edge],
                ),
            )
    player.kill()
    return shift, frozenset(old_draw_offsets_y)


def _old_camera_x_interval(
    frame: FrameWorldSample, *, player_prefix: str, shift_pixels: int
) -> tuple[float, float] | None:
    """The old camera x (plus WORLD shake) that gives every non-player baseline rect's x.

    Every sprite but the player stands where it stood in the old run (terrain does not move;
    enemies and collectibles move on game time, which the pose change does not touch), so its
    baseline x, round(world_x - camera_x - shake_x) plus its draw_offset, bounds the old camera
    x to a 1 px window. The old camera, aimed at an old player at most shift_pixels away, is
    within that of the sampled one. Closed intervals accept an exact rounding tie either way.

    Returns:
        (lowest, highest) old camera x, or None when no single camera explains the frame.

    """
    shake_x, _ = frame.shake_offset
    lowest = frame.camera_x - shift_pixels - 0.5
    highest = frame.camera_x + shift_pixels + 0.5
    for sprite_id, sprite in frame.sprites.items():
        baseline_rect = frame.baseline_rects.get(sprite_id)
        if baseline_rect is None or sprite_id.startswith(player_prefix):
            continue
        old_offset = sprite.world_x - shake_x + sprite.draw_offset[0] - baseline_rect[0]
        lowest = max(lowest, old_offset - 0.5)
        highest = min(highest, old_offset + 0.5)
    if lowest > highest:
        return None
    return (lowest, highest)


@dataclass(frozen=True)
class FallingPoseChange:
    """What the running to falling rule needs to know about one edition.

    Attributes:
        player_prefix: The player's sprite id prefix (``'<ClassName>#'``).
        shift_pixels: How far the player's hitbox edges move from a running to a falling pose.
        old_draw_offsets_y: The draw_offset y values of the frames the old player fell in.
        old_world_y_offsets: Where else (world y offsets) the old run had a sprite, by sprite
            id prefix (the scarabs' old-culling margin), besides where it stands now.
        other_rules: The edition's other world rules: a difference one of them explains is
            theirs, never this rule's (each difference has exactly one cause).

    """

    player_prefix: str
    shift_pixels: int
    old_draw_offsets_y: frozenset[int]
    old_world_y_offsets: Mapping[str, frozenset[float]]
    other_rules: tuple[Callable[[TraceDifference, FrameWorldSample], bool], ...]


def _fell_in_its_falling_pose(
    difference: TraceDifference, frame: FrameWorldSample, *, change: FallingPoseChange
) -> bool:
    """Running to falling (BUGS.md #209 item 7): the old player fell into a pit running.

    The proof: the current rect is exactly the engine's; the sprite did not change size; none
    of the edition's other rules explains the difference; one old camera x, within
    change.shift_pixels of the sampled one, gives every non-player sprite's baseline x
    (_old_camera_x_interval); a non-player sprite's baseline y is the old formula's under the
    unchanged camera y (the camera follows on x only), at today's world y or one of its
    old_world_y_offsets; and under that camera the baseline player is drawn from an old world x
    at most change.shift_pixels from today's, at today's world y with today's draw_offset or
    one of an old fall frame's.

    Returns:
        True if one old camera and an old player within the shift give the baseline frame.

    """
    sprite = _sprite_sample(difference, frame)
    if (
        sprite is None
        or difference.current != engine_rect(sprite, frame, mode=SPEC_SNAP_MODE)
        or difference.baseline[2:] != difference.current[2:]
        or _old_and_engine_formulas_give(difference, frame)
        or any(rule(difference, frame) for rule in change.other_rules)
    ):
        return False
    camera_interval = _old_camera_x_interval(
        frame, player_prefix=change.player_prefix, shift_pixels=change.shift_pixels
    )
    if camera_interval is None:
        return False
    shake_x, shake_y = frame.shake_offset
    draw_offset_x, draw_offset_y = sprite.draw_offset
    baseline_x, baseline_y = difference.baseline[:2]
    if not difference.sprite_id.startswith(change.player_prefix):
        # Its own baseline x bounded the interval, so a non-empty interval explains its x
        world_y_offsets = {0.0}.union(
            *(
                offsets
                for prefix, offsets in change.old_world_y_offsets.items()
                if difference.sprite_id.startswith(prefix)
            )
        )
        return any(
            baseline_y
            == round(sprite.world_y + world_y_offset - frame.camera_y - shake_y) + draw_offset_y
            for world_y_offset in world_y_offsets
        )
    old_draw_offset_y = baseline_y - round(sprite.world_y - frame.camera_y - shake_y)
    if old_draw_offset_y not in change.old_draw_offsets_y | {draw_offset_y}:
        return False
    lowest_camera_x, highest_camera_x = camera_interval
    # Old world_x - camera_x - shake_x over old world_x within shift_pixels of today's and
    # camera_x in the interval; round() of it must reach the baseline x
    lowest_offset = (
        sprite.world_x - change.shift_pixels - highest_camera_x - shake_x + draw_offset_x
    )
    highest_offset = (
        sprite.world_x + change.shift_pixels - lowest_camera_x - shake_x + draw_offset_x
    )
    return lowest_offset <= baseline_x + 0.5 and highest_offset >= baseline_x - 0.5


def adventurer_fell_in_its_falling_pose(
    difference: TraceDifference, frame: FrameWorldSample
) -> bool:
    """Running to falling, primitives edition (see _fell_in_its_falling_pose).

    Its scarabs rolled scarab_feet_margin_pixels() high in the old run (old culling, see
    scarab_stood_on_blank_image_hitbox), which that rule explains only under today's camera.

    Returns:
        True if the old running-pose fall explains the difference.

    """
    return _fell_in_its_falling_pose(
        difference,
        frame,
        change=FallingPoseChange(
            player_prefix=f'{AdventurerPlayer.__name__}#',
            shift_pixels=adventurer_falling_pose_shift_pixels(),
            old_draw_offsets_y=frozenset({0}),
            old_world_y_offsets={'Scarab#': frozenset({float(-scarab_feet_margin_pixels())})},
            other_rules=(scarab_stood_on_blank_image_hitbox,),
        ),
    )


def papyrus_fell_in_its_falling_pose(difference: TraceDifference, frame: FrameWorldSample) -> bool:
    """Running to falling, Papyrus edition (see _fell_in_its_falling_pose).

    Returns:
        True if the old running-pose fall explains the difference.

    """
    shift_pixels, old_draw_offsets_y = papyrus_running_and_falling_poses()
    return _fell_in_its_falling_pose(
        difference,
        frame,
        change=FallingPoseChange(
            player_prefix=f'{PapyrusPlayer.__name__}#',
            shift_pixels=shift_pixels,
            old_draw_offsets_y=old_draw_offsets_y,
            old_world_y_offsets={},
            other_rules=(),
        ),
    )


# Filled in by later tasks of the world-space plan; every entry must say why it is expected.
EXPECTED_DIFFERENCES: dict[str, list[ExpectedDifference]] = {
    'clockwork_keep': [
        ExpectedDifference(
            frames=None,
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
            frames=None,
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
            world_rule=settled_onto_floor,
            reason=(
                'Pose fix (spec 1): after standing 2 px high on frame 0 the old tinker fell '
                'onto the floor and the old camera trailed it by a fraction of a pixel'
            ),
        ),
        ExpectedDifference(
            frames=range(595, 596),
            sprite_pattern='Tinker#1',
            field='rect',
            world_rule=settled_onto_floor,
            reason=(
                'Pose fix (spec 1): on the first frame after the ride the old tinker dropped '
                'its 2 px and the old camera followed it'
            ),
        ),
    ],
    'brave_adventurer': [
        ExpectedDifference(
            frames=None,
            sprite_pattern='*',
            field='visible',
            world_rule=culled_outside_margin,
            reason=(
                'Engine culling (spec 2.4): the old per-sprite culling (Camera2D.is_visible) '
                'kept sprites up to 64 px beyond the screen sides and never culled the '
                'adventurer (below the screen after falling into a pit); the engine hides '
                'every world sprite beyond CULL_MARGIN_PIXELS'
            ),
        ),
        ExpectedDifference(
            frames=None,
            sprite_pattern='*',
            field='rect',
            world_rule=separately_snapped,
            reason=(
                'Spec 2.2: sprite and camera are snapped separately, snap(world) - '
                'snap(camera), instead of round(world - camera); the running adventurer, the '
                'rolling scarabs and the gliding camera all have fractions'
            ),
        ),
        ExpectedDifference(
            frames=range(1, 2),
            sprite_pattern='Player#0',
            field='rect',
            world_rule=adventurer_stood_on_blank_image_hitbox,
            reason=(
                'Pose fix (spec 1): the first ground check used to run before any pose was '
                'drawn, on the blank image, standing the adventurer 1 px too high'
            ),
        ),
        ExpectedDifference(
            frames=None,
            sprite_pattern='Scarab#*',
            field='rect',
            world_rule=scarab_stood_on_blank_image_hitbox,
            reason=(
                'Old culling side effect: culled sprites got dirty = 0, so Scene.update() never '
                'drew them and an off-screen scarab collided on its blank image (whole-image '
                'hitbox), rolling 2 px high; engine culling keeps dirty = 2, so scarabs are '
                'drawn and rest their visible underside on the ground'
            ),
        ),
        ExpectedDifference(
            frames=range(1, 4),
            sprite_pattern='Scarab#*',
            field='rect',
            world_rule=scarab_dropping_from_its_spawn_height,
            reason=(
                'Old culling side effect, first frames: today a scarab drops its 2 px from its '
                'spawn height onto its drawn underside; the undrawn old one stood at its spawn '
                'height'
            ),
        ),
        ExpectedDifference(
            frames=range(860, 900),
            sprite_pattern='*',
            field='rect',
            world_rule=adventurer_fell_in_its_falling_pose,
            reason=(
                'Running to falling (BUGS.md #209 item 7): the script runs off a ledge into the '
                'screen-4 pit; from frame 860 the player falls in its falling pose, whose '
                'hitbox the pit wall stops at another x than the running (then idle) pose the '
                'old player fell in, and the camera, following it, trails the old one by that '
                'much'
            ),
        ),
    ],
    'brave_adventurer_papyrus': [
        ExpectedDifference(
            frames=None,
            sprite_pattern='*',
            field='visible',
            world_rule=culled_outside_margin,
            reason=(
                'Engine culling (spec 2.4): the old per-sprite culling (Camera2D.is_visible) '
                "kept Papyrus's sprites and Brave Adventurer's shared ground segments and walls "
                'up to 64 px beyond the screen sides and never culled the adventurer (below the '
                'screen after falling into a pit); the engine hides every world sprite beyond '
                'CULL_MARGIN_PIXELS'
            ),
        ),
        ExpectedDifference(
            frames=None,
            sprite_pattern='*',
            field='rect',
            world_rule=separately_snapped,
            reason=(
                'Spec 2.2: sprite and camera are snapped separately, snap(world) - '
                'snap(camera), instead of round(world - camera); the running adventurer (plus '
                "its anchored frame's draw_offset, before and after), the rolling scarabs and "
                'the gliding camera all have fractions'
            ),
        ),
        ExpectedDifference(
            frames=None,
            sprite_pattern='*',
            field='rect',
            world_rule=rounded_half_up_at_exact_half,
            reason=(
                'Spec 2.2 half-up rounding: a rolling scarab at exactly x.5 under the still '
                'camera (x = 0 before it moves) was drawn by round(), half to even; the engine '
                'snaps an exact half up'
            ),
        ),
        ExpectedDifference(
            frames=range(841, 900),
            sprite_pattern='*',
            field='rect',
            world_rule=papyrus_fell_in_its_falling_pose,
            reason=(
                'Running to falling (BUGS.md #209 item 7): the script runs off a ledge on frame '
                '841; the player now falls in its falling frame, anchored 2 px higher than the '
                'running frames the old player fell in and 4 px lower than the idle frame it '
                'showed once the pit wall stopped it; in the screen-4 pit its wider hitbox '
                'stops at another x, which the camera, following it, trails'
            ),
        ),
    ],
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

    Raises:
        AmbiguousExpectedDifferenceError: If more than one entry explains a difference.

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
        if len(explaining_entries) > 1:
            entry_reasons = '; '.join(
                f'entry {entry_index}: {expected[entry_index].reason}'
                for entry_index in explaining_entries
            )
            message = (
                f'{_describe(difference)} is explained by {len(explaining_entries)} entries '
                f'(each difference needs exactly one cause): {entry_reasons}'
            )
            raise AmbiguousExpectedDifferenceError(message)
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
    """Every game with a golden trace has an entry, so a new trace cannot slip past the list.

    The expected set is the baselines themselves, one file per game in ``tests/world/golden/``
    (frozen since the world-space change), so the golden-trace tests cannot pass on zero.
    """
    baselines = {
        path.name.removesuffix(GOLDEN_TRACE_SUFFIX)
        for path in GOLDEN_DIRECTORY.glob(f'*{GOLDEN_TRACE_SUFFIX}')
    }

    assert baselines
    assert set(GOLDEN_TRACE_GAMES) == baselines
    assert set(EXPECTED_DIFFERENCES) == baselines


@pytest.mark.parametrize('game_key', sorted(GOLDEN_TRACE_GAMES))
def test_game_matches_golden_trace(game_key):
    """Replaying the game's script reproduces its golden trace, up to listed differences."""
    baseline = read_trace(path=golden_path(game_key))
    world_sampler = WorldSampler()
    scene_class = GAME_SCENES[game_key]
    current = record_trace(
        scene_class=scene_class,
        script=SCRIPT_BUILDERS[game_key](),
        frame_count=len(baseline['frames']),
        frame_observer=world_sampler,
    )

    # The baselines name their game by key (scripts/record_golden_traces.py main); the harness
    # names it by its scene's logical name
    assert baseline['game'] == game_key
    assert current['game'] == logical_name(scene_class=scene_class)
    assert current['frame_seconds'] == baseline['frame_seconds']
    unexplained, stale = unexplained_and_stale(
        differences=trace_differences(baseline=baseline, current=current),
        expected=EXPECTED_DIFFERENCES[game_key],
        world_samples=attach_baseline_rects(world_samples=world_sampler.frames, baseline=baseline),
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


@pytest.mark.parametrize('game_key', sorted(GOLDEN_TRACE_GAMES))
def test_committed_trace_reencodes_to_identical_bytes(game_key, tmp_path):
    """Decoding then encoding a committed trace gives back every frame and the same lines.

    The committed files are format version 2 and the writer writes version 3, so the header
    line differs in its ``format_version`` alone; every frame line is identical.
    """
    path = golden_path(game_key)
    baseline = read_trace(path=path)
    reencoded_path = tmp_path / path.name
    write_trace(trace=baseline, path=reencoded_path)

    assert read_trace(path=reencoded_path) == baseline
    with gzip.open(path, 'rt', encoding='utf-8') as committed_file:
        committed_lines = committed_file.read().splitlines()
    with gzip.open(reencoded_path, 'rt', encoding='utf-8') as reencoded_file:
        reencoded_lines = reencoded_file.read().splitlines()
    committed_header = json.loads(committed_lines[0])
    reencoded_header = json.loads(reencoded_lines[0])
    assert committed_header.pop('format_version') == 2
    assert reencoded_header.pop('format_version') == TRACE_FORMAT_VERSION
    assert reencoded_header == committed_header
    assert reencoded_lines[1:] == committed_lines[1:]


@pytest.mark.parametrize('game_key', sorted(GOLDEN_TRACE_GAMES))
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


@pytest.mark.parametrize('game_key', sorted(GOLDEN_TRACE_GAMES))
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
    write_trace(trace=altered, path=altered_path)

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

    def test_entry_without_frames_covers_every_frame(self):
        expected = [
            ExpectedDifference(
                frames=None,
                sprite_pattern='Ball#0',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='test',
            )
        ]
        unexplained, stale = unexplained_and_stale(
            differences=self._one_rect_change(frame_count=4), expected=expected
        )
        assert unexplained == []
        assert stale == []

    def test_difference_explained_by_two_entries_fails_naming_both(self):
        """Each difference must have exactly one cause: overlapping entries are an error."""
        expected = [
            ExpectedDifference(
                frames=None,
                sprite_pattern='Ball#0',
                field='rect',
                expected=[2, 2, 3, 4],
                reason='first cause',
            ),
            ExpectedDifference(
                frames=range(1),
                sprite_pattern='*',
                field='rect',
                rule=lambda baseline_value, current_value: True,
                reason='second cause',
            ),
        ]
        with pytest.raises(AmbiguousExpectedDifferenceError) as error_info:
            unexplained_and_stale(differences=self._one_rect_change(), expected=expected)
        message = str(error_info.value)
        assert 'frame 0, sprite Ball#0, rect' in message
        assert 'first cause' in message
        assert 'second cause' in message

    def test_entry_needs_an_expected_value_or_a_rule(self):
        with pytest.raises(ValueError, match='expected value or a rule'):
            ExpectedDifference(frames=range(1), sprite_pattern='*', field='rect', reason='test')


class TestWorldRules:
    """World rules: differences proven from the current run's world and camera positions."""

    @staticmethod
    def _world_frame(
        *,
        camera_y: float,
        sprite: SpriteWorldSample,
        snap_mode: PixelSnapMode = PixelSnapMode.NEAREST_HALF_UP,
    ) -> FrameWorldSample:
        return FrameWorldSample(
            camera_x=0.0,
            camera_y=camera_y,
            shake_offset=(0.0, 0.0),
            snap_mode=snap_mode,
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

    def test_separately_snapped_rejects_a_floor_snapped_run(self):
        """The rules pin the spec's NEAREST_HALF_UP: a run snapping with FLOOR is not explained."""
        # Camera 0.2, cog 10.9: FLOOR gives 10 - 0 = 10; round(10.9 - 0.2) = 11 before
        sprite = SpriteWorldSample(world_x=0.0, world_y=10.9, rect=[0, 10, 16, 16], hidden=False)
        frame = self._world_frame(camera_y=0.2, sprite=sprite, snap_mode=PixelSnapMode.FLOOR)
        difference = TraceDifference(
            frame=0,
            sprite_id='Cog#0',
            field='rect',
            baseline=[0, 11, 16, 16],
            current=[0, 10, 16, 16],
        )
        assert not separately_snapped(difference, frame)

    @pytest.mark.parametrize(
        ('current', 'within'),
        [([1, 11, 16, 16], True), ([0, 12, 16, 16], False), ([2, 10, 16, 16], False)],
        ids=['one_pixel_each_axis', 'two_pixels_in_y', 'two_pixels_in_x'],
    )
    def test_within_one_pixel_per_axis(self, current, within):
        assert within_one_pixel_per_axis(baseline=[0, 10, 16, 16], current=current) is within

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

    @staticmethod
    def _rolling_scarab_difference(*, camera_x: float) -> tuple[TraceDifference, FrameWorldSample]:
        """A Papyrus scarab at x = 10292.5 (as in the real run) under a camera at camera_x.

        Returns:
            The difference (baseline by round(), current by the engine) and its frame.

        """
        sprite = SpriteWorldSample(
            world_x=10292.5, world_y=386.0, rect=[0, 386, 10, 8], hidden=False
        )
        frame = FrameWorldSample(
            camera_x=camera_x,
            camera_y=0.0,
            shake_offset=(0.0, 0.0),
            snap_mode=PixelSnapMode.NEAREST_HALF_UP,
            screen_size=(800, 480),
            sprites={'PapyrusScarab#1': sprite},
        )
        difference = TraceDifference(
            frame=2,
            sprite_id='PapyrusScarab#1',
            field='rect',
            baseline=camera_apply_rect(sprite, frame),
            current=engine_rect(sprite, frame, mode=PixelSnapMode.NEAREST_HALF_UP),
        )
        return difference, frame

    def test_exact_half_with_a_whole_camera_is_the_half_up_rule_only(self):
        """round(10292.5 - 0) = 10292 (half to even); the engine's half-up snap gives 10293."""
        difference, frame = self._rolling_scarab_difference(camera_x=0.0)
        assert difference.baseline[0] == 10292
        assert difference.current[0] == 10293
        assert rounded_half_up_at_exact_half(difference, frame)
        assert not separately_snapped(difference, frame)

    def test_exact_half_with_a_fractional_camera_is_separate_snapping(self):
        """Camera 0.3: snap(10292.5) - snap(0.3) = 10293, round(10292.2) = 10292."""
        difference, frame = self._rolling_scarab_difference(camera_x=0.3)
        assert difference.baseline[0] != difference.current[0]
        assert not rounded_half_up_at_exact_half(difference, frame)
        assert separately_snapped(difference, frame)

    def test_half_up_rule_needs_the_old_formula_for_the_baseline(self):
        difference, frame = self._rolling_scarab_difference(camera_x=0.0)
        wrong_baseline = dataclasses.replace(difference, baseline=[10291, 386, 10, 8])
        assert not rounded_half_up_at_exact_half(wrong_baseline, frame)

    def test_world_rules_add_the_anchored_frames_draw_offset(self):
        """Papyrus's player is drawn at its frame's draw_offset, by the engine and the old code."""
        sprite = SpriteWorldSample(
            world_x=262.444, world_y=247.0, rect=[0, 0, 20, 28], hidden=False, draw_offset=(0, 6)
        )
        frame = self._world_frame(camera_y=0.0, sprite=sprite)
        frame = dataclasses.replace(frame, camera_x=2.7106)
        assert engine_rect(sprite, frame, mode=PixelSnapMode.NEAREST_HALF_UP)[:2] == [259, 253]
        assert camera_apply_rect(sprite, frame)[:2] == [260, 253]

    @staticmethod
    def _settling_frame(*, tinker_baseline_y: int) -> FrameWorldSample:
        """Frame 1 of the real run: camera 131.86, cogs bobbing, the tinker standing at 894.

        Returns:
            The world sample with its baseline rects attached.

        """
        cog = SpriteWorldSample(
            world_x=400.0, world_y=860.2995, rect=[400, 728, 16, 16], hidden=False
        )
        platform = SpriteWorldSample(
            world_x=100.0, world_y=936.0, rect=[100, 804, 600, 12], hidden=False
        )
        tinker = SpriteWorldSample(
            world_x=400.0, world_y=894.0, rect=[400, 762, 28, 44], hidden=False
        )
        return FrameWorldSample(
            camera_x=0.0,
            camera_y=131.86,
            shake_offset=(0.0, 0.0),
            snap_mode=PixelSnapMode.NEAREST_HALF_UP,
            screen_size=(800, 480),
            sprites={'CogCollectible#0': cog, 'Platform#0': platform, 'Tinker#0': tinker},
            baseline_rects={
                'CogCollectible#0': [400, 729, 16, 16],
                'Platform#0': [100, 804, 600, 12],
                'Tinker#0': [400, tinker_baseline_y, 28, 44],
            },
        )

    def test_settling_finds_one_old_camera_for_the_whole_frame(self):
        # Cog 860.2995 -> 729 and platform 936 -> 804 put the old camera in [131.5, 131.7995];
        # the old tinker, up to 2 px higher than 894, then drew at 761 or 762
        frame = self._settling_frame(tinker_baseline_y=761)
        cog_difference = TraceDifference(
            frame=1,
            sprite_id='CogCollectible#0',
            field='rect',
            baseline=[400, 729, 16, 16],
            current=[400, 728, 16, 16],
        )
        tinker_difference = TraceDifference(
            frame=1,
            sprite_id='Tinker#0',
            field='rect',
            baseline=[400, 761, 28, 44],
            current=[400, 762, 28, 44],
        )
        assert settled_onto_floor(cog_difference, frame)
        assert settled_onto_floor(tinker_difference, frame)

    def test_settling_rejects_a_tinker_no_old_position_explains(self):
        """759 needs the tinker 2.7 px or more above 894 under that camera: more than the margin."""
        frame = self._settling_frame(tinker_baseline_y=759)
        tinker_difference = TraceDifference(
            frame=1,
            sprite_id='Tinker#0',
            field='rect',
            baseline=[400, 759, 28, 44],
            current=[400, 762, 28, 44],
        )
        assert not settled_onto_floor(tinker_difference, frame)

    def test_settling_rejects_sprites_no_single_old_camera_explains(self):
        frame = dataclasses.replace(
            self._settling_frame(tinker_baseline_y=761),
            baseline_rects={
                'CogCollectible#0': [400, 729, 16, 16],
                'Platform#0': [100, 803, 600, 12],  # needs a camera of 132.5 or more
                'Tinker#0': [400, 761, 28, 44],
            },
        )
        cog_difference = TraceDifference(
            frame=1,
            sprite_id='CogCollectible#0',
            field='rect',
            baseline=[400, 729, 16, 16],
            current=[400, 728, 16, 16],
        )
        assert not settled_onto_floor(cog_difference, frame)

    @staticmethod
    def _scarab_frame(*, world_y: float) -> FrameWorldSample:
        """A frame with one Brave Adventurer scarab at world_y; the camera has a fraction.

        Returns:
            The world sample.

        """
        scarab = SpriteWorldSample(
            world_x=6294.0, world_y=world_y, rect=[0, 0, 20, 16], hidden=False
        )
        return FrameWorldSample(
            camera_x=0.6,
            camera_y=0.0,
            shake_offset=(0.0, 0.0),
            snap_mode=PixelSnapMode.NEAREST_HALF_UP,
            screen_size=(800, 480),
            sprites={'Scarab#0': scarab},
        )

    def test_blank_image_margins_are_measured_from_the_drawings(self):
        """The scarab's underside is 2 px above its image bottom; the adventurer's feet 1 px."""
        assert scarab_feet_margin_pixels() == 2
        assert adventurer_feet_margin_pixels() == 1

    @pytest.mark.parametrize(('baseline_y', 'explained'), [(384, True), (385, False), (386, False)])
    def test_scarab_on_its_blank_image_stood_the_margin_higher(self, baseline_y, explained):
        # Today's scarab rests at 386 (drawn underside on the ground); the blank one at 384
        frame = self._scarab_frame(world_y=386.0)
        difference = TraceDifference(
            frame=40,
            sprite_id='Scarab#0',
            field='rect',
            baseline=[6294 - 1, baseline_y, 20, 16],
            current=[6294 - 1, 386, 20, 16],
        )
        assert scarab_stood_on_blank_image_hitbox(difference, frame) is explained

    def test_scarab_raised_rule_rejects_a_scarab_still_dropping_from_its_spawn(self):
        """While dropping its first 2 px, the old scarab was at its spawn height, not 2 px up."""
        frame = self._scarab_frame(world_y=385.6)
        difference = TraceDifference(
            frame=3,
            sprite_id='Scarab#0',
            field='rect',
            baseline=[6293, 384, 20, 16],
            current=[6293, 386, 20, 16],
        )
        assert not scarab_stood_on_blank_image_hitbox(difference, frame)
        assert scarab_dropping_from_its_spawn_height(difference, frame)

    def test_scarab_drop_rule_needs_the_old_scarab_at_its_spawn_height(self):
        frame = self._scarab_frame(world_y=385.6)
        difference = TraceDifference(
            frame=3,
            sprite_id='Scarab#0',
            field='rect',
            baseline=[6293, 385, 20, 16],
            current=[6293, 386, 20, 16],
        )
        assert not scarab_dropping_from_its_spawn_height(difference, frame)

    def test_scarab_drop_rule_rejects_a_scarab_that_has_landed(self):
        frame = self._scarab_frame(world_y=386.0)
        difference = TraceDifference(
            frame=40,
            sprite_id='Scarab#0',
            field='rect',
            baseline=[6293, 384, 20, 16],
            current=[6293, 386, 20, 16],
        )
        assert not scarab_dropping_from_its_spawn_height(difference, frame)
