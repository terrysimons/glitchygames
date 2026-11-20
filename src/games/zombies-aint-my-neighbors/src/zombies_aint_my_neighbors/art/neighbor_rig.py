"""The neighbors' rig: the Pizza Delivery Teen, the Lawn-Chair Reader, and being saved or lost.

Character BOM section 6 (feature plan 7). Neighbors never move, so each is drawn facing the
viewer only: ``idle`` (2 frames, 0.5 s) and ``panic`` (2 frames, 0.12 s). The two shared effects
are drawn over where a neighbor stood: ``saved`` (5 frames, 0.06 s: the figure streams up into a
VR safe room's blue portal) and ``lost`` (5 frames, 0.08 s: it flickers to a silhouette of TV
static and fades). They draw with the kids' canvas, shading ramps and outline (``rig``), so the
cast shares one look; the effects' noise comes from a generator seeded by the frame, so a build
never changes.

The Lawn-Chair Reader is an older woman in a wide sun hat and a lavender cardigan in a striped
lawn chair, far from the original game's victims (character BOM, A7).
"""

from __future__ import annotations

import random
from types import MappingProxyType
from typing import Final

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
    PANTS_LIGHT,
    PANTS_RAMP,
    PANTS_SHADE,
    SHOES,
    SKIN,
    SKIN_LIGHT,
    SKIN_RAMP,
    SKIN_SHADE,
    WHITE,
    kid_palette,
)
from zombies_aint_my_neighbors.art.poses import AnimationSpec
from zombies_aint_my_neighbors.art.rig import ARM_RADIUS, LEG_RADIUS, Canvas, Grid, outline_figure

# The Pizza Delivery Teen: a red uniform polo and cap, dark jeans (the hair's colour), the pizza
# box's cardboard (the trousers ramp), dark sneakers
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
PIZZA_TEEN_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((240, 196, 160), (210, 160, 122), (160, 112, 82)),
        hair=(52, 48, 66),
        clothes=((250, 122, 112), (214, 52, 48), (156, 30, 36), (98, 18, 28)),
        pants=((232, 196, 140), (196, 156, 100), (146, 110, 66)),
        shoes=(70, 70, 80),
    )
)
# The Lawn-Chair Reader: a lavender cardigan, a straw sun hat (the trousers ramp), the chair's
# webbing stripes (the shoes' teal and white), its aluminium frame (the headset grey)
LAWN_CHAIR_READER_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((236, 200, 176), (206, 160, 132), (156, 112, 92)),
        hair=(226, 226, 232),
        clothes=((222, 200, 244), (180, 152, 220), (128, 102, 172), (86, 64, 124)),
        pants=((246, 226, 160), (216, 186, 112), (164, 132, 70)),
        shoes=(64, 176, 168),
    )
)
# Being saved (the VR safe room's blues, the clothes ramp) and lost (TV static: the trousers'
# greys and the skin ramp's darker greys)
EFFECT_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((150, 152, 160), (110, 112, 122), (72, 74, 84)),
        hair=(40, 40, 48),
        clothes=((200, 240, 255), (96, 200, 255), (40, 140, 230), (24, 84, 170)),
        pants=((236, 236, 240), (200, 202, 208), (176, 178, 186)),
        shoes=(255, 240, 160),
    )
)

WIDTH: Final = 32
HEIGHT: Final = 48

# Character BOM section 6
NEIGHBOR_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='idle', facings=(), frame_interval=0.5, loop=True),
    AnimationSpec(state='panic', facings=(), frame_interval=0.12, loop=True),
)
SAVED_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='saved', facings=(), frame_interval=0.06, loop=False),
)
LOST_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='lost', facings=(), frame_interval=0.08, loop=False),
)

_EFFECT_SEED: Final = 20261116
_FRAMES: Final = 2
_EFFECT_FRAMES: Final = 5
# The figure's middle column (an arm left of it reaches right, and the other way)
_MIDDLE_X: Final = WIDTH / 2
# The silhouette the effects dissolve: a head (centre, radius), a body and two legs (boxes)
_HEAD_CENTRE: Final = (16.0, 12.0)
_HEAD_RADIUS: Final = 6.5
_BODY: Final = (8, 19, 23, 34)
_LEGS: Final = ((10, 35, 14, 45), (17, 35, 21, 45))
# The share of the gone part of the figure left as rising specks while being saved
_SPECK_CHANCE: Final = 0.18
# From this frame of being lost, every other scan line breaks away
_BREAKUP_FROM_FRAME: Final = 2


def _draw_eyes(canvas: Canvas, *, row: int, wide: bool) -> None:
    """Draw two eyes: dots, or wide whites with pupils (panic)."""
    for eye_x in (12, 19):
        if wide:
            canvas.row(y=row - 1, left=eye_x - 1, right=eye_x + 1, character=WHITE)
            canvas.row(y=row, left=eye_x - 1, right=eye_x + 1, character=WHITE)
            canvas.put(x=eye_x, y=row, character=OUTLINE)
        else:
            canvas.put(x=eye_x, y=row, character=OUTLINE)


def _draw_pizza_teen(canvas: Canvas, *, state: str, frame: int) -> None:
    """Draw the Pizza Delivery Teen, standing: the order slip, or the box held up as a shield."""
    shake = frame if state == 'panic' else 0
    # Jeans and sneakers
    for leg_x in (12.5, 19.5):
        canvas.capsule(start=(leg_x, 33), end=(leg_x, 42.5), radius=LEG_RADIUS, ramp=HAIR * 3)
    for left in (9, 17):
        canvas.row(y=44, left=left, right=left + 5, character=SHOES)
        canvas.row(y=45, left=left, right=left + 5, character=SHOES)
        canvas.row(y=46, left=left, right=left + 5, character=WHITE)
    canvas.shift_x = shake
    # The red uniform polo, its collar and a name badge
    canvas.box(left=8, top=20, right=23, bottom=34, ramp=CLOTHES_RAMP)
    canvas.row(y=20, left=13, right=18, character=WHITE)
    canvas.row(y=24, left=18, right=20, character=WHITE)
    # The head, the red cap with its peak
    canvas.ellipse(centre=(16, 13.0), radii=(7.4, 7.2), ramp=SKIN_RAMP)
    canvas.ellipse(centre=(16, 8.0), radii=(7.8, 3.6), ramp=CLOTHES_RAMP, bottom=9)
    canvas.row(y=10, left=8, right=24, character=CLOTHES_SHADE)
    canvas.row(y=11, left=10, right=22, character=CLOTHES_DARK)
    canvas.put(x=16, y=6, character=WHITE)
    if state == 'idle':
        # Reading the slip: eyes down on frame 0, up on frame 1
        _draw_eyes(canvas, row=14 if frame == 0 else 13, wide=False)
        canvas.row(y=17, left=14, right=17, character=SKIN_SHADE)
        # The box under the left arm; the slip held up in the right hand
        canvas.box(left=2, top=26, right=11, bottom=31, ramp=PANTS_RAMP)
        canvas.row(y=28, left=4, right=9, character=CLOTHES)
        canvas.capsule(start=(23, 22), end=(22, 28 - frame), radius=ARM_RADIUS, ramp=CLOTHES_RAMP)
        canvas.ellipse(centre=(21.5, 28.5 - frame), radii=(2.0, 1.8), ramp=SKIN_RAMP)
        for y in range(23 - frame, 28 - frame):
            canvas.row(y=y, left=18, right=21, character=WHITE)
        canvas.row(y=24 - frame, left=19, right=20, character=HEADSET)
        canvas.row(y=26 - frame, left=19, right=20, character=HEADSET)
    else:
        # The box held up in both hands as a shield, eyes wide over it
        _draw_eyes(canvas, row=13, wide=True)
        for hand_x in (6.0, 26.0):
            canvas.capsule(
                start=(hand_x + (2 if hand_x < _MIDDLE_X else -2), 22),
                end=(hand_x, 18),
                radius=ARM_RADIUS,
                ramp=CLOTHES_RAMP,
            )
        canvas.box(left=5, top=15, right=27, bottom=26, ramp=PANTS_RAMP)
        canvas.row(y=15, left=6, right=26, character=PANTS_LIGHT)
        canvas.ellipse(centre=(16, 20.5), radii=(3.5, 2.5), ramp=CLOTHES + CLOTHES_SHADE)
        canvas.row(y=26, left=6, right=26, character=PANTS_SHADE)
    canvas.shift_x = 0


def _draw_lawn_chair(canvas: Canvas) -> None:
    """Draw the striped lawn chair: its aluminium frame and teal-and-white webbing."""
    for post_x in (5, 26):
        canvas.column(x=post_x, top=18, bottom=46, character=HEADSET)
    canvas.row(y=46, left=4, right=27, character=HEADSET)
    canvas.row(y=36, left=5, right=26, character=HEADSET)
    for y in range(18, 36):
        canvas.row(y=y, left=6, right=25, character=SHOES if (y // 2) % 2 == 0 else WHITE)


def _draw_reader(canvas: Canvas, *, state: str, frame: int) -> None:
    """Draw the Lawn-Chair Reader, seated: turning a page, or the paper over her head."""
    _draw_lawn_chair(canvas)
    shake = frame if state == 'panic' else 0
    # Shins and sandals, the knees toward the viewer
    for leg_x in (12.5, 19.5):
        canvas.capsule(start=(leg_x, 36), end=(leg_x, 43.5), radius=LEG_RADIUS, ramp=SKIN_RAMP)
    for left in (9, 17):
        canvas.row(y=44, left=left, right=left + 5, character=PANTS_SHADE)
    canvas.shift_x = shake
    # The lavender cardigan, seated; a lap of skirt over the knees
    canvas.box(left=9, top=22, right=22, bottom=35, ramp=CLOTHES_RAMP)
    canvas.box(left=8, top=33, right=23, bottom=37, ramp=CLOTHES_SHADE * 2 + CLOTHES_DARK)
    # The head: white hair, the straw sun hat's wide brim
    canvas.ellipse(centre=(16, 17.0), radii=(6.6, 6.4), ramp=SKIN_RAMP)
    canvas.row(y=11, left=10, right=21, character=HAIR)
    canvas.row(y=12, left=10, right=21, character=HAIR)
    canvas.ellipse(centre=(16, 8.5), radii=(5.5, 3.5), ramp=PANTS_RAMP)
    canvas.row(y=11, left=3, right=28, character=PANTS)
    canvas.row(y=12, left=4, right=27, character=PANTS_SHADE)
    canvas.row(y=9, left=11, right=20, character=CLOTHES)
    if state == 'idle':
        _draw_reading(canvas, frame=frame)
    else:
        _draw_paper_over_head(canvas)
    canvas.shift_x = 0


def _draw_reading(canvas: Canvas, *, frame: int) -> None:
    """Draw the reader's face and the newspaper held open (frame 1: a page turning over)."""
    _draw_eyes(canvas, row=17, wide=False)
    canvas.row(y=20, left=15, right=17, character=SKIN_SHADE)
    right = 25 if frame == 0 else 17
    for y in range(23, 33):
        canvas.row(y=y, left=6, right=right, character=WHITE)
    for line_y in (25, 27, 29, 31):
        canvas.row(y=line_y, left=7, right=right - 1, character=HEADSET)
    canvas.column(x=16, top=23, bottom=32, character=HEADSET)
    if frame == 1:
        # The turning page, mid-air
        for step in range(9):
            canvas.row(y=24 + step, left=18 + step // 3, right=21 + step // 3, character=WHITE)
    for hand_x in (6.0, float(right)):
        canvas.ellipse(centre=(hand_x, 28.0), radii=(2.0, 1.8), ramp=SKIN_RAMP)


def _draw_paper_over_head(canvas: Canvas) -> None:
    """Draw the reader panicking: eyes wide, mouth open, the paper held over her head."""
    _draw_eyes(canvas, row=17, wide=True)
    canvas.row(y=20, left=15, right=16, character=OUTLINE)
    canvas.row(y=21, left=15, right=16, character=OUTLINE)
    for shoulder_x, hand_x in ((10.0, 6.0), (21.0, 25.0)):
        canvas.capsule(
            start=(shoulder_x, 24), end=(hand_x, 6), radius=ARM_RADIUS, ramp=CLOTHES_RAMP
        )
    for y in range(1, 7):
        canvas.row(y=y, left=4, right=27, character=WHITE)
    for line_y in (2, 4):
        canvas.row(y=line_y, left=6, right=25, character=HEADSET)


def draw_neighbor(*, name: str, state: str, frame: int) -> Grid:
    """Return one frame of a neighbor, outlined.

    Args:
        name: ``pizza_teen`` or ``lawn_chair_reader``.
        state: ``idle`` or ``panic``.
        frame: The frame's index in its animation.

    Returns:
        48 rows of 32 palette characters.

    """
    canvas = Canvas(width=WIDTH, height=HEIGHT)
    if name == 'pizza_teen':
        _draw_pizza_teen(canvas, state=state, frame=frame)
    else:
        _draw_reader(canvas, state=state, frame=frame)
    outline_figure(canvas)
    return canvas.grid()


def neighbor_frames(*, name: str) -> dict[str, tuple[Grid, ...]]:
    """Return a neighbor's animations' frames, in the BOM's order.

    Returns:
        Namespace -> frames.

    """
    return {
        state: tuple(draw_neighbor(name=name, state=state, frame=frame) for frame in range(_FRAMES))
        for state in ('idle', 'panic')
    }


def _figure_cells() -> list[tuple[int, int]]:
    """Return the cells of a standing person's silhouette (what the effects dissolve).

    Returns:
        (x, y) cells, top to bottom.

    """

    def inside(box: tuple[int, int, int, int], x: int, y: int) -> bool:
        left, top, right, bottom = box
        return left <= x <= right and top <= y <= bottom

    centre_x, centre_y = _HEAD_CENTRE
    cells: list[tuple[int, int]] = []
    for y in range(4, 46):
        for x in range(WIDTH):
            head = ((x + 0.5 - centre_x) ** 2 + (y + 0.5 - centre_y) ** 2) <= _HEAD_RADIUS**2
            if head or inside(_BODY, x, y) or any(inside(leg, x, y) for leg in _LEGS):
                cells.append((x, y))
    return cells


def _noise(frame: int) -> random.Random:
    """Return the effects' noise for a frame (art is built, not played: no gameplay stream).

    Returns:
        A generator seeded by the frame.

    """
    return random.Random(_EFFECT_SEED + frame)  # ruff: ignore[suspicious-non-cryptographic-random-usage] - pixel noise, not security


def draw_saved(*, frame: int) -> Grid:
    """Return a frame of ``saved``: the figure streams up into a blue portal, which closes.

    Returns:
        48 rows of 32 palette characters.

    """
    canvas = Canvas(width=WIDTH, height=HEIGHT)
    noise = _noise(frame)
    # The portal: a blue ring over the head, closing on the last frame
    radius_x = (9.0, 10.0, 10.0, 8.0, 4.0)[frame]
    canvas.ellipse(
        centre=(16, 3.0), radii=(radius_x, 2.6), ramp=CLOTHES_LIGHT + CLOTHES + CLOTHES_SHADE
    )
    canvas.ellipse(centre=(16, 3.0), radii=(radius_x * 0.6, 1.4), ramp=CLOTHES_DARK * 3)
    # The figure, gone from the feet up a fifth a frame; the rest streams up as specks
    cutoff = 46 - frame * 10
    for x, y in _figure_cells():
        if y < cutoff:
            canvas.put(x=x, y=y, character=CLOTHES_LIGHT if (x + y + frame) % 3 else WHITE)
        elif noise.random() < _SPECK_CHANCE:
            canvas.put(x=x, y=y - 8 - frame * 4, character=noise.choice((WHITE, CLOTHES)))
    outline_figure(canvas)
    return canvas.grid()


def draw_lost(*, frame: int) -> Grid:
    """Return a frame of ``lost``: a silhouette of TV static that flickers, breaks up and fades.

    Returns:
        48 rows of 32 palette characters.

    """
    canvas = Canvas(width=WIDTH, height=HEIGHT)
    noise = _noise(frame + _EFFECT_FRAMES)
    kept = (1.0, 0.8, 0.55, 0.3, 0.1)[frame]
    tones = (PANTS_LIGHT, PANTS, PANTS_SHADE, SKIN_LIGHT, SKIN, SKIN_SHADE)
    for x, y in _figure_cells():
        # Every other scan line breaks away from frame 2 on
        if frame >= _BREAKUP_FROM_FRAME and y % 2 == frame % 2:
            continue
        if noise.random() < kept:
            canvas.put(x=x, y=y, character=noise.choice(tones))
    outline_figure(canvas)
    return canvas.grid()


def saved_frames() -> dict[str, tuple[Grid, ...]]:
    """Return ``saved``'s frames.

    Returns:
        Namespace -> frames.

    """
    return {'saved': tuple(draw_saved(frame=frame) for frame in range(_EFFECT_FRAMES))}


def lost_frames() -> dict[str, tuple[Grid, ...]]:
    """Return ``lost``'s frames.

    Returns:
        Namespace -> frames.

    """
    return {'lost': tuple(draw_lost(frame=frame) for frame in range(_EFFECT_FRAMES))}


# Each neighbor's sprite name and palette, for the builder and the game
NEIGHBOR_LOOKS: Final = MappingProxyType({
    'pizza_teen': PIZZA_TEEN_PALETTE,
    'lawn_chair_reader': LAWN_CHAIR_READER_PALETTE,
})
