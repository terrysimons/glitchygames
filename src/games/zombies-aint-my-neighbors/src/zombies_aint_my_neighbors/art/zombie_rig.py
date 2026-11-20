"""The Lawn Zombie's rig: a shambling neighbor in a bathrobe, drawn like the kids (32x48, SNES-era).

Character BOM section 5.1, less ``rise`` (decision 6: zombies come out of TV sets): ``walk`` in
three facings (right is left mirrored by the game), ``grab`` (the lunge and the clamp), and
``crumble`` (down only). He holds a soggy newspaper out in front with both hands, centred, so a
mirrored frame keeps it; his skin is a grey-blue (no green near P1's, BOM section 1). Idle is
walk frame 0 held (BOM: a shuffler stands like it walks), so it has no frames of its own.

It draws with the kids' canvas, shading ramps and outline (``rig``), so the cast shares one look.
"""

from __future__ import annotations

from enum import StrEnum
from types import MappingProxyType
from typing import Final

from pydantic import BaseModel, ConfigDict

from zombies_aint_my_neighbors.art import poses
from zombies_aint_my_neighbors.art.palettes import (
    CLOTHES_DARK,
    CLOTHES_RAMP,
    CLOTHES_SHADE,
    HAIR,
    HEADSET,
    OUTLINE,
    PANTS_RAMP,
    PANTS_SHADE,
    SHOES,
    SKIN,
    SKIN_RAMP,
    SKIN_SHADE,
    WHITE,
    kid_palette,
)
from zombies_aint_my_neighbors.art.poses import AnimationSpec, Facing, Legs
from zombies_aint_my_neighbors.art.rig import (
    ARM_RADIUS,
    LEG_RADIUS,
    Canvas,
    Grid,
    Point,
    outline_figure,
)

# The zombie's palette, on the rig's characters: grey-blue skin, a few dark wisps of hair, a
# faded blue bathrobe, cream striped pyjamas, pink fuzzy slippers
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
ZOMBIE_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((176, 194, 204), (132, 150, 166), (90, 106, 124)),
        hair=(70, 64, 60),
        clothes=((156, 176, 220), (112, 132, 186), (78, 94, 146), (50, 60, 102)),
        pants=((222, 212, 190), (182, 170, 148), (130, 120, 104)),
        shoes=(236, 150, 190),
    )
)

# Character BOM 5.1, less rise
ZOMBIE_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='walk', facings=poses.ALL_FACINGS, frame_interval=0.18, loop=True),
    AnimationSpec(
        state='grab', facings=poses.ALL_FACINGS, frame_interval=0.1, loop=False, then_state='walk'
    ),
    AnimationSpec(state='crumble', facings=(), frame_interval=0.1, loop=False),
)


class ZombieArms(StrEnum):
    """Where the zombie's hands are."""

    HOLD = 'hold'  # the newspaper held out in front
    LUNGE = 'lunge'  # the paper dropped, arms thrown out
    CLAMP = 'clamp'  # arms closing on a victim
    SLUMP = 'slump'  # arms hanging, giving way


class ZombiePose(BaseModel):
    """One frame of the zombie."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    facing: Facing
    legs: Legs = Legs.STAND
    arms: ZombieArms = ZombieArms.HOLD
    bob: int = 0
    lean: int = 0
    # Crumbling, 0 (slumping) to 4 (an empty robe and slippers); None when standing
    crumble_stage: int | None = None


_FRONT_SHOULDERS: Final[tuple[Point, Point]] = ((7.5, 22.0), (24.5, 22.0))
_FRONT_HANDS: Final[dict[ZombieArms, tuple[Point, Point]]] = {
    ZombieArms.HOLD: ((11.0, 28.0), (21.0, 28.0)),
    ZombieArms.LUNGE: ((8.0, 23.0), (24.0, 23.0)),
    ZombieArms.CLAMP: ((13.0, 25.0), (19.0, 25.0)),
    ZombieArms.SLUMP: ((7.5, 34.0), (24.5, 34.0)),
}
_SIDE_SHOULDER: Final[Point] = (16.0, 22.0)
_SIDE_HANDS: Final[dict[ZombieArms, Point]] = {
    ZombieArms.HOLD: (7.0, 27.0),
    ZombieArms.LUNGE: (4.0, 24.0),
    ZombieArms.CLAMP: (6.0, 25.0),
    ZombieArms.SLUMP: (15.0, 34.0),
}
_HAND_RADII: Final[Point] = (2.0, 1.8)
_SLEEVE_RAMP: Final = CLOTHES_SHADE + CLOTHES_SHADE + CLOTHES_DARK
# The hunch: the head sits this much lower on the shoulders than a kid's
_HUNCH: Final = 2
# Crumbling: the head's place and size as it sinks into the heap, by stage (gone at the last)
_SINKING_HEADS: Final[dict[int, tuple[Point, Point]]] = {
    2: ((16, 32.0), (6.5, 6.0)),
    3: ((16, 37.5), (5.0, 4.5)),
}


def _walk(*, facing: Facing) -> tuple[ZombiePose, ...]:
    """Return the shuffle: small steps, a sway, the paper held out.

    Returns:
        Four poses.

    """
    legs = (
        (Legs.STRIDE_NEAR, Legs.PASSING, Legs.STRIDE_FAR, Legs.PASSING)
        if facing is Facing.LEFT
        else (Legs.STAND, Legs.LEFT_UP, Legs.STAND, Legs.RIGHT_UP)
    )
    sway = (0, -1, 0, 1) if facing is not Facing.LEFT else (0, 0, 0, 0)
    return tuple(
        ZombiePose(facing=facing, legs=leg, bob=bob, lean=lean)
        for leg, bob, lean in zip(legs, (0, 1, 0, 1), sway, strict=True)
    )


def zombie_poses() -> dict[str, tuple[ZombiePose, ...]]:
    """Return every zombie namespace with its frames' poses, in BOM order.

    Returns:
        Namespace -> poses.

    """
    walks = {f'walk_{facing}': _walk(facing=facing) for facing in poses.ALL_FACINGS}
    grabs = {
        f'grab_{facing}': (
            ZombiePose(facing=facing, arms=ZombieArms.LUNGE, bob=1),
            ZombiePose(facing=facing, arms=ZombieArms.CLAMP),
        )
        for facing in poses.ALL_FACINGS
    }
    crumble = {
        'crumble': tuple(ZombiePose(facing=Facing.DOWN, crumble_stage=stage) for stage in range(5))
    }
    return walks | grabs | crumble


def _draw_slippers(canvas: Canvas, *, left: int, right: int, top: int) -> None:
    """Draw one fuzzy slipper: pink, a fluffy white trim, a grey sole."""
    for y in (top, top + 1):
        canvas.row(y=y, left=left, right=right, character=SHOES)
    for x in range(left, right + 1, 2):
        canvas.put(x=x, y=top, character=WHITE)
    canvas.row(y=top + 2, left=left, right=right, character=HEADSET)


def _draw_pyjama_leg(canvas: Canvas, *, start: Point, end: Point) -> None:
    """Draw a striped pyjama leg."""
    canvas.capsule(start=start, end=end, radius=LEG_RADIUS, ramp=PANTS_RAMP)
    for stripe_y in (37, 40):
        for x in range(int(min(start[0], end[0])) - 3, int(max(start[0], end[0])) + 4):
            if canvas.at(x=x, y=stripe_y) in PANTS_RAMP:
                canvas.put(x=x, y=stripe_y, character=PANTS_SHADE)


def _draw_legs(canvas: Canvas, *, pose: ZombiePose) -> None:
    """Draw the pyjama legs and slippers (they never sway)."""
    if pose.facing is Facing.LEFT:
        if pose.legs in {Legs.STRIDE_NEAR, Legs.STRIDE_FAR}:
            _draw_pyjama_leg(canvas, start=(17.5, 35), end=(19.5, 42.5))
            _draw_slippers(canvas, left=17, right=23, top=44)
            _draw_pyjama_leg(canvas, start=(15, 35), end=(13, 42.5))
            _draw_slippers(canvas, left=8, right=15, top=44)
        else:
            _draw_pyjama_leg(canvas, start=(16, 35), end=(16, 42.5))
            _draw_slippers(canvas, left=11, right=19, top=44)
        return
    left_lift = 2 if pose.legs is Legs.LEFT_UP else 0
    right_lift = 2 if pose.legs is Legs.RIGHT_UP else 0
    _draw_pyjama_leg(canvas, start=(12.5, 35), end=(12.5, 42.5 - left_lift))
    _draw_pyjama_leg(canvas, start=(19.5, 35), end=(19.5, 42.5 - right_lift))
    _draw_slippers(canvas, left=8, right=14, top=44 - left_lift)
    _draw_slippers(canvas, left=17, right=23, top=44 - right_lift)


def _draw_robe(canvas: Canvas, *, facing: Facing) -> None:
    """Draw the bathrobe: its body, the lapels, the belt and the hem."""
    left, right = (10, 21) if facing is Facing.LEFT else (8, 23)
    canvas.box(left=left, top=20, right=right, bottom=34, ramp=CLOTHES_RAMP)
    canvas.row(y=33, left=left, right=right, character=CLOTHES_SHADE)
    canvas.row(y=34, left=left + 1, right=right - 1, character=CLOTHES_DARK)
    canvas.row(y=28, left=left, right=right, character=CLOTHES_DARK)
    if facing is Facing.DOWN:
        for step in range(5):
            canvas.put(x=12 + step // 2 + 1, y=20 + step, character=CLOTHES_DARK)
            canvas.put(x=19 - step // 2 - 1, y=20 + step, character=CLOTHES_DARK)
        canvas.row(y=29, left=15, right=16, character=CLOTHES_SHADE)
    elif facing is Facing.LEFT:
        canvas.column(x=12, top=20, bottom=27, character=CLOTHES_DARK)


def _draw_front_head(canvas: Canvas) -> None:
    """Draw the zombie's face: grey-blue, wisps of hair, sunken eyes, the mouth hanging open."""
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(16, 13.0), radii=(8.0, 7.4), ramp=SKIN_RAMP)
    canvas.ellipse(centre=(8.2, 14.0), radii=(1.3, 1.9), ramp=SKIN + SKIN_SHADE)
    canvas.ellipse(centre=(23.8, 14.0), radii=(1.3, 1.9), ramp=SKIN + SKIN_SHADE)
    for wisp_x, wisp_y in ((12, 6), (15, 5), (16, 5), (19, 6), (13, 7), (18, 7)):
        canvas.put(x=wisp_x, y=wisp_y, character=HAIR)
    # Sunken eye sockets, a pinprick of light in each; a sagging brow above
    for socket_x in (10, 19):
        canvas.row(y=11, left=socket_x, right=socket_x + 2, character=SKIN_SHADE)
        canvas.row(y=12, left=socket_x, right=socket_x + 2, character=OUTLINE)
        canvas.row(y=13, left=socket_x, right=socket_x + 2, character=OUTLINE)
        canvas.put(x=socket_x + 1, y=12, character=WHITE)
    # A jagged, hanging mouth with a few teeth
    canvas.row(y=16, left=13, right=18, character=OUTLINE)
    canvas.row(y=17, left=13, right=18, character=OUTLINE)
    canvas.row(y=18, left=14, right=17, character=OUTLINE)
    for tooth_x in (14, 16, 17):
        canvas.put(x=tooth_x, y=16, character=WHITE)
    canvas.put(x=15, y=18, character=WHITE)
    # Rot: blotches of the skin's shade
    for spot_x, spot_y in ((21, 9), (22, 10), (9, 15), (17, 7)):
        canvas.put(x=spot_x, y=spot_y, character=SKIN_SHADE)


def _draw_back_head(canvas: Canvas) -> None:
    """Draw the back of the zombie's bald head, with a few wisps."""
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(8.2, 14.0), radii=(1.3, 1.9), ramp=SKIN + SKIN_SHADE)
    canvas.ellipse(centre=(23.8, 14.0), radii=(1.3, 1.9), ramp=SKIN + SKIN_SHADE)
    canvas.ellipse(centre=(16, 13.0), radii=(8.0, 7.4), ramp=SKIN_RAMP)
    for wisp_x, wisp_y in ((11, 9), (14, 11), (18, 10), (21, 12), (16, 14)):
        canvas.put(x=wisp_x, y=wisp_y, character=HAIR)


def _draw_side_head(canvas: Canvas) -> None:
    """Draw the zombie's head in profile, facing left, jaw hanging."""
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(15, 13.0), radii=(7.6, 7.4), ramp=SKIN_RAMP)
    canvas.ellipse(centre=(18.2, 14.0), radii=(1.3, 1.8), ramp=SKIN + SKIN_SHADE)
    canvas.put(x=7, y=14, character=SKIN)
    canvas.put(x=7, y=15, character=SKIN_SHADE)
    for wisp_x, wisp_y in ((14, 6), (17, 6), (19, 8)):
        canvas.put(x=wisp_x, y=wisp_y, character=HAIR)
    canvas.row(y=11, left=8, right=10, character=SKIN_SHADE)
    canvas.row(y=12, left=8, right=10, character=OUTLINE)
    canvas.row(y=13, left=8, right=10, character=OUTLINE)
    canvas.put(x=9, y=12, character=WHITE)
    canvas.put(x=17, y=8, character=SKIN_SHADE)
    canvas.row(y=17, left=8, right=10, character=OUTLINE)
    canvas.row(y=18, left=9, right=10, character=OUTLINE)


def _draw_newspaper(canvas: Canvas, *, facing: Facing) -> None:
    """Draw the soggy newspaper held out in front: a sheet with lines of print."""
    if facing is Facing.LEFT:
        canvas.box(left=2, top=22, right=7, bottom=32, ramp=WHITE + WHITE + HEADSET)
        for print_y in (24, 26, 28, 30):
            canvas.row(y=print_y, left=3, right=6, character=HEADSET)
        return
    canvas.box(left=11, top=25, right=20, bottom=31, ramp=WHITE + WHITE + HEADSET)
    for print_y in (27, 29):
        canvas.row(y=print_y, left=12, right=19, character=HEADSET)


def _draw_arms(canvas: Canvas, *, pose: ZombiePose) -> None:
    """Draw the robe's sleeves and the grey-blue hands."""
    if pose.facing is Facing.LEFT:
        pairs: tuple[tuple[Point, Point], ...] = ((_SIDE_SHOULDER, _SIDE_HANDS[pose.arms]),)
    else:
        pairs = tuple(zip(_FRONT_SHOULDERS, _FRONT_HANDS[pose.arms], strict=True))
    for shoulder, hand in pairs:
        # Sleeves in the robe's shade, so the arms read against its body
        canvas.capsule(start=shoulder, end=hand, radius=ARM_RADIUS, ramp=_SLEEVE_RAMP)
        canvas.ellipse(centre=hand, radii=_HAND_RADII, ramp=SKIN_RAMP)


def _draw_crumbling(canvas: Canvas, *, stage: int) -> None:
    """Draw the zombie crumbling: slumping, buckling, a heap, an empty robe and slippers."""
    if stage <= 1:
        canvas.shift_y = 2 if stage == 0 else 6
        _draw_robe(canvas, facing=Facing.DOWN)
        canvas.shift_y += _HUNCH
        _draw_front_head(canvas)
        canvas.shift_y -= _HUNCH
        _draw_arms(canvas, pose=ZombiePose(facing=Facing.DOWN, arms=ZombieArms.SLUMP))
        canvas.shift_y = 0
        return
    # A heap of robe, the head sinking into it, the slippers left either side
    heap = {
        2: ((16, 40.0), (11.0, 6.0)),
        3: ((16, 42.0), (12.0, 4.0)),
        4: ((16, 44.0), (13.0, 2.5)),
    }
    centre, radii = heap[stage]
    canvas.ellipse(centre=centre, radii=radii, ramp=CLOTHES_RAMP)
    sinking_head = _SINKING_HEADS.get(stage)
    if sinking_head is not None:
        canvas.ellipse(centre=sinking_head[0], radii=sinking_head[1], ramp=SKIN_RAMP)
    _draw_slippers(canvas, left=3, right=8, top=44)
    _draw_slippers(canvas, left=23, right=28, top=44)


def draw_zombie(*, pose: ZombiePose) -> Grid:
    """Return one frame of the zombie, outlined.

    Returns:
        48 rows of 32 palette characters.

    """
    canvas = Canvas()
    if pose.crumble_stage is not None:
        if pose.crumble_stage <= 1:
            _draw_legs(canvas, pose=ZombiePose(facing=Facing.DOWN))
        _draw_crumbling(canvas, stage=pose.crumble_stage)
        outline_figure(canvas)
        return canvas.grid()
    _draw_legs(canvas, pose=pose)
    canvas.shift_x, canvas.shift_y = pose.lean, pose.bob
    arms_behind = pose.facing is Facing.UP
    if arms_behind:
        _draw_arms(canvas, pose=pose)
    _draw_robe(canvas, facing=pose.facing)
    heads = {
        Facing.DOWN: _draw_front_head,
        Facing.UP: _draw_back_head,
        Facing.LEFT: _draw_side_head,
    }
    canvas.shift_y += _HUNCH
    heads[pose.facing](canvas)
    canvas.shift_y -= _HUNCH
    if pose.arms is ZombieArms.HOLD and pose.facing is not Facing.UP:
        _draw_newspaper(canvas, facing=pose.facing)
    if not arms_behind:
        _draw_arms(canvas, pose=pose)
    canvas.shift_x = canvas.shift_y = 0
    outline_figure(canvas)
    return canvas.grid()


def zombie_frames() -> dict[str, tuple[Grid, ...]]:
    """Return every zombie animation's frames, in BOM order.

    Returns:
        Namespace -> frames.

    """
    return {
        namespace: tuple(draw_zombie(pose=pose) for pose in frame_poses)
        for namespace, frame_poses in zombie_poses().items()
    }
