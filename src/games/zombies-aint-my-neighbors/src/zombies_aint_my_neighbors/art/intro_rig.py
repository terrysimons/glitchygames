"""The intro's rig: the sleepover and the monsters coming out of the TV (feature plan 12).

Character BOM section 7 (plans/2026-11-14-zombies-aint-my-neighbors-2-character-bom.md): nine
sprites, 46 frames. Each kid sits up in a sleeping bag in their player's colour, seen from behind
with the VR headset's strap round the back of the head (``sit``, ``startled``); the TV is a
bigger set than the yard's (64x64), showing the horror host (``show``), then ``static``, then
``bulge`` and ``burst``, and ``switch-off`` (the picture collapsing to a line, then a dot: the
game over too). The monster's hands (``reach``) and the Lawn Zombie (``climb-out``) are drawn on
the TV's 64x64 canvas, lined up with its screen, so the scene places them where the TV is. A lamp
(``still``, ``flicker``) and a bowl of popcorn (``still``) dress the set.

Everything draws with the kids' canvas, shading ramps and outline (``rig``), so the cast shares
one look. Intro sprites are never collided with, and have no transitions: the intro's timeline
(``intro_timeline``) moves each one from animation to animation. The static is noise from a
generator seeded by the frame, so the files never change between builds.
"""

from __future__ import annotations

import math
import random
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from zombies_aint_my_neighbors.art import palettes, tv_rig, zombie_rig
from zombies_aint_my_neighbors.art.palettes import (
    CLOTHES,
    CLOTHES_DARK,
    CLOTHES_LIGHT,
    CLOTHES_RAMP,
    CLOTHES_SHADE,
    HAIR,
    HEADSET,
    OUTLINE,
    PANTS,
    PANTS_RAMP,
    PANTS_SHADE,
    SHOES,
    SKIN,
    SKIN_RAMP,
    WHITE,
    kid_palette,
)
from zombies_aint_my_neighbors.art.poses import AnimationSpec

# Point at run time: ClimbPose (pydantic) resolves its fields' types when it is built
from zombies_aint_my_neighbors.art.rig import Canvas, Grid, Point, outline_figure

if TYPE_CHECKING:
    from collections.abc import Mapping


# A one-frame still has no interval in the BOM: it is held, looping on its one frame
STILL_SECONDS: Final = 1.0
# BOM section 7's sizes
BAG_SIZE: Final = (48, 32)
TV_SIZE: Final = (64, 64)
PROP_SIZE: Final = (32, 32)

_BAG_ANIMATIONS: Final = (
    AnimationSpec(state='sit', facings=(), frame_interval=0.5, loop=True),
    AnimationSpec(state='startled', facings=(), frame_interval=0.12, loop=False),
)
_TV_ANIMATIONS: Final = (
    AnimationSpec(state='show', facings=(), frame_interval=0.25, loop=True),
    AnimationSpec(state='static', facings=(), frame_interval=0.08, loop=True),
    AnimationSpec(state='bulge', facings=(), frame_interval=0.12, loop=False),
    AnimationSpec(state='burst', facings=(), frame_interval=0.08, loop=False),
    AnimationSpec(state='switch-off', facings=(), frame_interval=0.08, loop=False),
)
_STILL: Final = AnimationSpec(state='still', facings=(), frame_interval=STILL_SECONDS, loop=True)
# The snack bowl's one picture. A sprite of one animation with one frame is a still: the engine
# saves it in the static layout (its pixels in [sprite], sprites as text, #220) and names its one
# animation after the sprite, so the bowl's is named so too, and its file is written that way
SNACKS_STILL: Final = AnimationSpec(
    state='intro_snacks', facings=(), frame_interval=STILL_SECONDS, loop=True
)

# Sprite file stem -> its animations, in the BOM's order (read-only: module state shared by every
# engine context, tests/test_process_state_guard.py)
INTRO_ANIMATIONS: Final[Mapping[str, tuple[AnimationSpec, ...]]] = MappingProxyType({
    **{f'intro_bag_{look.name}': _BAG_ANIMATIONS for look in palettes.KIDS},
    'intro_tv': _TV_ANIMATIONS,
    'intro_hands': (AnimationSpec(state='reach', facings=(), frame_interval=0.12, loop=False),),
    'intro_zombie': (
        AnimationSpec(state='climb-out', facings=(), frame_interval=0.12, loop=False),
    ),
    'intro_lamp': (
        _STILL,
        AnimationSpec(state='flicker', facings=(), frame_interval=0.08, loop=True),
    ),
    'intro_snacks': (SNACKS_STILL,),
})
# Frames per animation (BOM section 7)
_FRAME_COUNTS: Final[Mapping[str, int]] = MappingProxyType({
    'sit': 2,
    'startled': 2,
    'show': 4,
    'static': 3,
    'bulge': 4,
    'burst': 4,
    'switch-off': 3,
    'reach': 4,
    'climb-out': 4,
    'still': 1,
    'intro_snacks': 1,
    'flicker': 2,
})

# The lamp: a cream shade lit from inside, a brass stem and foot, the bulb's glow
LAMP_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((150, 104, 66), (112, 76, 46), (78, 52, 32)),
        hair=(52, 36, 28),
        clothes=((255, 238, 186), (246, 206, 122), (212, 158, 74), (148, 100, 46)),
        pants=((232, 198, 112), (186, 148, 72), (122, 92, 42)),
        shoes=(255, 250, 214),
    )
)
# The popcorn bowl: red and white stripes, popcorn, butter
SNACKS_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((255, 248, 222), (244, 224, 168), (204, 176, 112)),
        hair=(96, 30, 30),
        clothes=((244, 112, 104), (214, 58, 58), (160, 34, 40), (104, 22, 30)),
        pants=((236, 236, 228), (196, 196, 190), (150, 150, 146)),
        shoes=(250, 206, 72),
    )
)

# The TV's screen (left, top, right, bottom, inclusive) and its centre, where the monster comes out
_SCREEN: Final = (9, 19, 45, 47)
SCREEN_CENTRE: Final[Point] = (27.0, 33.0)
_STATIC_TONES: Final = (CLOTHES_LIGHT, CLOTHES, CLOTHES_SHADE, CLOTHES_DARK)
# Seeds the static's noise by frame, so builds are identical (art is built, not played)
_STATIC_SEED: Final = 20261119
_SPARKS: Final = ((15, 24), (40, 26), (18, 44), (38, 43))


def _bag_palette(stem: str) -> Mapping[str, tuple[int, int, int]]:
    """Return a bag's palette: its kid's own (the bag is in the player's colour).

    Returns:
        Palette character -> colour.
    """
    look = next(look for look in palettes.KIDS if stem == f'intro_bag_{look.name}')
    return look.palette


def intro_palette(*, sprite: str) -> Mapping[str, tuple[int, int, int]]:
    """Return an intro sprite's palette.

    Args:
        sprite: The sprite file's stem (a key of ``INTRO_ANIMATIONS``).

    Returns:
        Palette character -> colour.

    Raises:
        ValueError: For a stem the BOM does not list.
    """
    if sprite.startswith('intro_bag_') and sprite in INTRO_ANIMATIONS:
        return _bag_palette(sprite)
    palettes_by_stem: dict[str, Mapping[str, tuple[int, int, int]]] = {
        'intro_tv': tv_rig.TV_PALETTE,
        'intro_hands': zombie_rig.ZOMBIE_PALETTE,
        'intro_zombie': zombie_rig.ZOMBIE_PALETTE,
        'intro_lamp': LAMP_PALETTE,
        'intro_snacks': SNACKS_PALETTE,
    }
    if sprite not in palettes_by_stem:
        message = f'no intro sprite {sprite!r}'
        raise ValueError(message)
    return palettes_by_stem[sprite]


def _draw_bag(canvas: Canvas, *, state: str, frame: int) -> None:
    """Draw a kid sitting up in a sleeping bag, seen from behind, the headset strapped on.

    ``sit`` breathes (the head sinks a pixel on frame 1); ``startled`` jerks up, hands rising.
    """
    lift = (2, 4)[frame] if state == 'startled' else -frame
    head_y = 10.0 - lift
    # Pyjama shoulders, tucked into the bag
    canvas.ellipse(centre=(24.0, 19.0 - lift), radii=(10.0, 5.0), ramp=PANTS_RAMP)
    if state == 'startled':
        hand_y = (12.0, 6.0)[frame] - lift
        for side in (-1, 1):
            shoulder = (24.0 + side * 8.0, 18.0 - lift)
            hand = (24.0 + side * (12.0 + frame * 2.0), hand_y)
            canvas.capsule(start=shoulder, end=hand, radius=2.2, ramp=PANTS_RAMP)
            canvas.ellipse(centre=hand, radii=(2.1, 1.9), ramp=SKIN_RAMP)
    # The back of the head, the ears, the headset's strap and goggle sides
    canvas.ellipse(centre=(24.0, head_y), radii=(6.0, 6.5), ramp=HAIR + HAIR + OUTLINE)
    canvas.put(x=17, y=head_y + 1, character=SKIN)
    canvas.put(x=30, y=head_y + 1, character=SKIN)
    # The strap: two rows, the upper one catching the TV's light, so it reads against dark hair
    strap_y = round(head_y)
    canvas.row(y=strap_y - 1, left=18, right=29, character=WHITE)
    canvas.row(y=strap_y, left=18, right=29, character=HEADSET)
    for goggle_x in (15, 30):
        canvas.box(
            left=goggle_x, top=strap_y - 3, right=goggle_x + 2, bottom=strap_y + 1, ramp=HEADSET * 3
        )
        canvas.put(x=goggle_x + 1, y=strap_y - 2, character=WHITE)
    # The bag: quilted, a lighter fold at the top, the zip down one side
    canvas.box(left=5, top=19, right=42, bottom=31, ramp=CLOTHES_RAMP)
    canvas.row(y=19, left=6, right=41, character=CLOTHES_LIGHT)
    canvas.row(y=20, left=5, right=42, character=CLOTHES_LIGHT)
    for quilt_y in (24, 28):
        canvas.row(y=quilt_y, left=7, right=40, character=CLOTHES_SHADE)
    canvas.column(x=37, top=21, bottom=30, character=PANTS_SHADE)


def _draw_tv_case(canvas: Canvas) -> None:
    """Draw the big set: legs, wood case, bezel, grille, knobs and rabbit-ear antenna."""
    canvas.capsule(start=(16.0, 55.0), end=(12.0, 63.0), radius=1.8, ramp=SKIN_RAMP)
    canvas.capsule(start=(48.0, 55.0), end=(52.0, 63.0), radius=1.8, ramp=SKIN_RAMP)
    canvas.box(left=4, top=15, right=59, bottom=56, ramp=SKIN_RAMP)
    left, top, right, bottom = _SCREEN
    for y in range(top - 1, bottom + 2):
        canvas.row(y=y, left=left - 1, right=right + 1, character=HAIR)
    canvas.box(left=49, top=20, right=56, bottom=50, ramp=PANTS_RAMP)
    for grille_y in range(22, 50, 2):
        canvas.row(y=grille_y, left=50, right=55, character=PANTS_SHADE)
    for knob_y in (25, 33):
        canvas.box(left=51, top=knob_y, right=54, bottom=knob_y + 2, ramp=SHOES * 3)
    canvas.capsule(start=(32.0, 15.0), end=(20.0, 2.0), radius=0.7, ramp=HEADSET)
    canvas.capsule(start=(32.0, 15.0), end=(44.0, 2.0), radius=0.7, ramp=HEADSET)
    canvas.ellipse(centre=(32.0, 15.0), radii=(4.0, 2.0), ramp=HAIR)
    canvas.row(y=55, left=5, right=58, character=PANTS)


def _fill_screen(canvas: Canvas, *, character: str) -> None:
    """Fill the screen with one character."""
    left, top, right, bottom = _SCREEN
    for y in range(top, bottom + 1):
        canvas.row(y=y, left=left, right=right, character=character)


def _draw_static(canvas: Canvas, *, frame: int, grow: int = 0, lighten: bool = False) -> None:
    """Fill the screen with static (``grow``: how far it bulges past the bezel)."""
    left, top, right, bottom = _SCREEN
    noise = random.Random(_STATIC_SEED + frame)  # ruff: ignore[suspicious-non-cryptographic-random-usage] - pixel noise, not security
    for y in range(top - grow, bottom + grow + 1):
        for x in range(left - grow, right + grow + 1):
            tone = noise.choice(_STATIC_TONES)
            if lighten and tone in {CLOTHES_SHADE, CLOTHES_DARK}:
                tone = CLOTHES
            canvas.put(x=x, y=y, character=tone)
    canvas.row(y=top + (frame * 5) % (bottom - top), left=left, right=right, character=WHITE)


def _draw_host(canvas: Canvas, *, frame: int) -> None:
    """Draw the horror host on a black set: a pale face talking, a dark robe, a candle."""
    _fill_screen(canvas, character=HAIR)
    canvas.box(left=18, top=36, right=36, bottom=47, ramp=CLOTHES_DARK * 2 + HAIR)
    canvas.ellipse(centre=(27.0, 29.0), radii=(5.0, 6.0), ramp=CLOTHES_LIGHT * 2 + CLOTHES)
    for eye_x in (25, 29):
        canvas.put(x=eye_x, y=28, character=HAIR)
    canvas.row(y=32, left=26, right=28, character=HAIR)
    if frame % 2:
        canvas.row(y=33, left=26, right=28, character=HAIR)
    canvas.column(x=40, top=38, bottom=46, character=WHITE)
    canvas.put(x=40, y=36 + frame % 2, character=SHOES)
    left, top, right, bottom = _SCREEN
    canvas.row(
        y=top + (frame * 7) % (bottom - top), left=left, right=right, character=CLOTHES_SHADE
    )


def _draw_burst(canvas: Canvas, *, frame: int) -> None:
    """Draw the screen bursting: a flash, then a jagged black hole with sparks round its rim."""
    if frame == 0:
        _draw_static(canvas, frame=7, grow=4, lighten=True)
        canvas.ellipse(centre=SCREEN_CENTRE, radii=(20.0, 16.0), ramp=WHITE * 3 + CLOTHES_LIGHT)
        return
    _draw_static(canvas, frame=7 + frame)
    radius_x, radius_y = 13.0 + frame, 10.0 + frame
    canvas.ellipse(
        centre=SCREEN_CENTRE, radii=(radius_x + 2.0, radius_y + 2.0), ramp=CLOTHES_DARK * 2 + HAIR
    )
    canvas.ellipse(centre=SCREEN_CENTRE, radii=(radius_x, radius_y), ramp=HAIR * 3)
    spark_x, spark_y = _SPARKS[frame % len(_SPARKS)]
    canvas.put(x=spark_x, y=spark_y, character=WHITE)
    for near_x, near_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.put(x=spark_x + near_x, y=spark_y + near_y, character=SHOES)


def _draw_switch_off(canvas: Canvas, *, frame: int) -> None:
    """Draw the picture collapsing: a bright line, then a dot, then dark."""
    _fill_screen(canvas, character=HAIR)
    left, _, right, _ = _SCREEN
    centre_x, centre_y = round(SCREEN_CENTRE[0]), round(SCREEN_CENTRE[1])
    if frame == 0:
        canvas.row(y=centre_y, left=left, right=right, character=WHITE)
        canvas.row(y=centre_y - 1, left=left + 4, right=right - 4, character=CLOTHES_LIGHT)
    elif frame == 1:
        canvas.row(y=centre_y, left=centre_x - 1, right=centre_x + 1, character=WHITE)


def _draw_tv(canvas: Canvas, *, state: str, frame: int) -> None:
    """Draw the big set and its screen for one frame."""
    _draw_tv_case(canvas)
    if state == 'show':
        _draw_host(canvas, frame=frame)
    elif state == 'static':
        _draw_static(canvas, frame=frame)
    elif state == 'bulge':
        _draw_static(canvas, frame=frame + 3, grow=frame + 1, lighten=True)
    elif state == 'burst':
        _draw_burst(canvas, frame=frame)
    else:
        _draw_switch_off(canvas, frame=frame)


def _draw_hands(canvas: Canvas, *, frame: int) -> None:
    """Draw the monster's grey-blue hands pushing out of the hole toward the viewer.

    Each frame they come further out, up and apart, and grow (coming closer): frame 0 is
    fingertips through the hole, frame 3 two big hands, fingers spread, reaching up past the
    screen in the robe's sleeves. Four fingers fan up and out from each palm, the thumb inward.
    """
    centre_x, centre_y = SCREEN_CENTRE
    for side in (-1, 1):
        palm_radius = 2.4 + 1.1 * frame
        hand = (centre_x + side * (3.0 + 5.0 * frame), centre_y - 1.0 - 6.0 * frame)
        if frame:
            canvas.capsule(
                start=(centre_x + side * 2.0, centre_y + 3.0),
                end=hand,
                radius=1.8 + 0.7 * frame,
                ramp=CLOTHES_RAMP,
            )
        canvas.ellipse(centre=hand, radii=(palm_radius, palm_radius * 0.9), ramp=SKIN_RAMP)
        finger_length = palm_radius + 1.5 + 0.8 * frame
        for finger in range(4):
            # Fanned from up-and-inward to out-and-up: -105 to -30 degrees from the right,
            # mirrored for the left hand
            angle = math.radians(-105.0 + finger * 25.0)
            tip = (
                hand[0] + side * math.cos(angle) * finger_length,
                hand[1] + math.sin(angle) * finger_length,
            )
            canvas.capsule(start=hand, end=tip, radius=0.7 + 0.15 * frame, ramp=SKIN_RAMP)
        thumb = (hand[0] - side * (palm_radius + 1.0), hand[1] - palm_radius * 0.4)
        canvas.capsule(start=hand, end=thumb, radius=0.7 + 0.15 * frame, ramp=SKIN_RAMP)


type Leg = tuple[Point, Point, Point]


class ClimbPose(BaseModel):
    """One frame of the Lawn Zombie climbing out: where each part of him is.

    Attributes:
        head: The head's centre.
        torso: The robe's box (left, top, right, bottom).
        hands: The two hands' centres, left then right.
        legs: Each leg's (hip, knee, foot); none while only his top half is out.
        paper_held: The newspaper held out in front (standing), not tucked under his arm.
    """

    model_config = ConfigDict(frozen=True, extra='forbid')

    head: Point
    torso: tuple[int, int, int, int]
    hands: tuple[Point, Point]
    legs: tuple[Leg, ...] = ()
    paper_held: bool = False


# Shoulders out, the torso out, a leg over the screen's bottom edge (the thigh forward over the
# bezel, the knee bent, the shin down to the floor), standing in front of the set
_CLIMB_POSES: Final = (
    ClimbPose(head=(27.0, 26.0), torso=(19, 31, 35, 38), hands=((14.0, 46.0), (40.0, 46.0))),
    ClimbPose(head=(27.0, 30.0), torso=(20, 35, 34, 46), hands=((12.0, 52.0), (42.0, 52.0))),
    ClimbPose(
        head=(25.0, 34.0),
        torso=(18, 39, 32, 51),
        hands=((13.0, 55.0), (34.0, 57.0)),
        legs=(((29.0, 48.0), (42.0, 48.0), (43.0, 58.0)),),
    ),
    ClimbPose(
        head=(27.0, 28.0),
        torso=(21, 34, 33, 51),
        hands=((22.0, 44.0), (32.0, 44.0)),
        legs=(
            ((24.0, 48.0), (24.0, 54.0), (23.0, 60.0)),
            ((30.0, 48.0), (30.0, 54.0), (31.0, 60.0)),
        ),
        paper_held=True,
    ),
)


def _draw_zombie(canvas: Canvas, *, frame: int) -> None:
    """Draw the Lawn Zombie in its bathrobe: legs, the robe over them, arms, the head.

    He has his soggy newspaper, as in play (``zombie_rig._draw_newspaper``): tucked under his
    left arm while he climbs, held out in front with both hands once he stands
    (``ClimbPose.paper_held``).

    Each leg is (hip, knee, foot): a thigh and a shin, each from its own hip, so legs read as
    legs (never one shape from the crotch), with a flat slipper on the ground at the foot. The
    robe is drawn after the legs and hangs below the hips, so the tops of the legs are covered.
    """
    pose = _CLIMB_POSES[frame]
    for hip, knee, foot in pose.legs:
        canvas.capsule(start=hip, end=knee, radius=2.4, ramp=PANTS_RAMP)
        canvas.capsule(start=knee, end=foot, radius=2.2, ramp=PANTS_RAMP)
        canvas.ellipse(centre=(foot[0] + 1.0, foot[1] + 1.5), radii=(3.4, 1.4), ramp=SHOES * 3)
    left, top, right, bottom = pose.torso
    canvas.box(left=left, top=top, right=right, bottom=bottom, ramp=CLOTHES_RAMP)
    if not pose.paper_held:
        # Folded under the left arm: drawn before the arm, so the sleeve crosses it
        _draw_paper(canvas, left=left - 3, top=top + 3, right=left + 3, bottom=top + 9)
    for side, hand in zip((left, right), pose.hands, strict=True):
        canvas.capsule(start=(side + 0.5, top + 2.0), end=hand, radius=2.2, ramp=CLOTHES_RAMP)
    if pose.paper_held:
        hands_y = round(min(hand[1] for hand in pose.hands))
        _draw_paper(canvas, left=left + 1, top=hands_y - 4, right=right - 1, bottom=hands_y + 2)
    for hand in pose.hands:
        canvas.ellipse(centre=hand, radii=(2.1, 1.9), ramp=SKIN_RAMP)
    head_x, head_y = pose.head
    canvas.ellipse(centre=pose.head, radii=(5.5, 6.0), ramp=SKIN_RAMP)
    canvas.ellipse(centre=(head_x, head_y - 4.0), radii=(5.0, 2.5), ramp=HAIR * 3)
    for eye_x in (head_x - 2.0, head_x + 2.0):
        canvas.put(x=eye_x, y=head_y, character=CLOTHES_DARK)
    canvas.row(y=round(head_y) + 3, left=round(head_x) - 1, right=round(head_x) + 1, character=HAIR)


def _draw_paper(canvas: Canvas, *, left: int, top: int, right: int, bottom: int) -> None:
    """Draw the newspaper as the play zombie's: a white sheet with grey lines of print."""
    canvas.box(left=left, top=top, right=right, bottom=bottom, ramp=WHITE + WHITE + HEADSET)
    for print_y in range(top + 2, bottom, 2):
        canvas.row(y=print_y, left=left + 1, right=right - 1, character=HEADSET)


def _draw_lamp(canvas: Canvas, *, lit: bool) -> None:
    """Draw a table lamp: a shade lit from inside (or dimmed), a brass stem and foot."""
    shade = CLOTHES_RAMP if lit else CLOTHES_SHADE + CLOTHES_DARK * 3
    for step, y in enumerate(range(5, 16)):
        half = 5 + step // 2
        for x in range(16 - half, 16 + half):
            across = (x + 0.5 - 16) / half
            canvas.put(x=x, y=y, character=shade[min(3, max(0, int((across + 1) * 2)))])
    if lit:
        canvas.row(y=16, left=12, right=19, character=SHOES)
    canvas.box(left=15, top=16, right=16, bottom=26, ramp=PANTS_RAMP)
    canvas.ellipse(centre=(16.0, 28.0), radii=(6.0, 2.5), ramp=PANTS_RAMP)


def _draw_snacks(canvas: Canvas) -> None:
    """Draw a striped bowl heaped with buttered popcorn."""
    for centre in ((10.0, 17.0), (15.0, 14.0), (20.0, 16.0), (13.0, 19.0), (22.0, 19.0)):
        canvas.ellipse(centre=centre, radii=(3.2, 2.8), ramp=SKIN_RAMP)
    for butter_x, butter_y in ((14, 13), (21, 15), (11, 18)):
        canvas.put(x=butter_x, y=butter_y, character=SHOES)
    canvas.ellipse(centre=(16.0, 22.0), radii=(12.0, 3.0), ramp=CLOTHES_RAMP)
    for y in range(22, 30):
        half = round(12 - (y - 22) * 1.1)
        canvas.row(y=y, left=16 - half, right=15 + half, character=CLOTHES)
        for stripe_x in range(16 - half + 2, 16 + half, 4):
            canvas.put(x=stripe_x, y=y, character=WHITE)


def _draw(sprite: str, *, state: str, frame: int) -> Grid:
    """Return one outlined frame of an intro sprite."""
    width, height = (
        BAG_SIZE
        if sprite.startswith('intro_bag_')
        else TV_SIZE
        if sprite in {'intro_tv', 'intro_hands', 'intro_zombie'}
        else PROP_SIZE
    )
    canvas = Canvas(width=width, height=height)
    if sprite.startswith('intro_bag_'):
        _draw_bag(canvas, state=state, frame=frame)
    elif sprite == 'intro_tv':
        _draw_tv(canvas, state=state, frame=frame)
    elif sprite == 'intro_hands':
        _draw_hands(canvas, frame=frame)
    elif sprite == 'intro_zombie':
        _draw_zombie(canvas, frame=frame)
    elif sprite == 'intro_lamp':
        _draw_lamp(canvas, lit=state == 'still' or frame == 0)
    else:
        _draw_snacks(canvas)
    outline_figure(canvas)
    return canvas.grid()


def intro_frames(*, sprite: str) -> dict[str, tuple[Grid, ...]]:
    """Return an intro sprite's animations' frames, in the BOM's order.

    Args:
        sprite: The sprite file's stem (a key of ``INTRO_ANIMATIONS``).

    Returns:
        Namespace -> frames.

    Raises:
        ValueError: For a stem the BOM does not list.
    """
    if sprite not in INTRO_ANIMATIONS:
        message = f'no intro sprite {sprite!r}'
        raise ValueError(message)
    return {
        spec.state: tuple(
            _draw(sprite, state=spec.state, frame=frame)
            for frame in range(_FRAME_COUNTS[spec.state])
        )
        for spec in INTRO_ANIMATIONS[sprite]
    }
