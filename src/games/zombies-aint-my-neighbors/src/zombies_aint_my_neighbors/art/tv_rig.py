"""The TV's rig: a boxy wood-cased set on splayed legs, showing static; monsters come out of it.

The props BOM's TV (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md): 48x48, ``static``
(3 frames, looping) and ``spawn`` (4 frames: the screen bulges, bulges further, pops in a flash,
settles), and its damage stages (feature plan 6): ``cracked-`` and ``smashed-`` versions of both,
and ``destroyed`` (3 frames, smoking). The intact frames are drawn exactly as before. It draws
with the kids' canvas, shading and outline (``rig``). The static is noise from a generator
seeded by the frame, so the file never changes between builds.
The antenna is centred, so the TV is the same mirrored.
"""

from __future__ import annotations

import random
from types import MappingProxyType
from typing import Final

from zombies_aint_my_neighbors.art.palettes import (
    CLOTHES,
    CLOTHES_DARK,
    CLOTHES_LIGHT,
    CLOTHES_SHADE,
    HAIR,
    HEADSET,
    PANTS,
    PANTS_RAMP,
    PANTS_SHADE,
    SHOES,
    SKIN_RAMP,
    SKIN_SHADE,
    WHITE,
    kid_palette,
)
from zombies_aint_my_neighbors.art.poses import AnimationSpec
from zombies_aint_my_neighbors.art.rig import Canvas, Grid, outline_figure

# The TV's palette, on the rig's characters: the wood case (the skin ramp's characters), the
# bezel (hair), the static (the clothes ramp: four greys), the grille (the trousers ramp), the
# knobs (shoes), the glow (white) and the antenna's metal (the headset grey)
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
TV_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((176, 122, 74), (138, 90, 52), (96, 60, 34)),
        hair=(46, 44, 50),
        clothes=((214, 218, 222), (160, 166, 174), (104, 110, 120), (58, 62, 70)),
        pants=((120, 86, 56), (88, 62, 40), (60, 42, 28)),
        shoes=(214, 176, 92),
    )
)

WIDTH: Final = 48
HEIGHT: Final = 48

# The props BOM's TV
TV_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='static', facings=(), frame_interval=0.08, loop=True),
    AnimationSpec(state='spawn', facings=(), frame_interval=0.08, loop=False, then_state='static'),
    AnimationSpec(state='cracked-static', facings=(), frame_interval=0.08, loop=True),
    AnimationSpec(
        state='cracked-spawn',
        facings=(),
        frame_interval=0.08,
        loop=False,
        then_state='cracked-static',
    ),
    AnimationSpec(state='smashed-static', facings=(), frame_interval=0.08, loop=True),
    AnimationSpec(
        state='smashed-spawn',
        facings=(),
        frame_interval=0.08,
        loop=False,
        then_state='smashed-static',
    ),
    AnimationSpec(state='destroyed', facings=(), frame_interval=0.1, loop=True),
)
# The damage stages, in order (master plan decision 19); each but the last flickers and spawns
STAGES: Final = ('intact', 'cracked', 'smashed', 'destroyed')

_STATIC_TONES: Final = (CLOTHES_LIGHT, CLOTHES, CLOTHES_SHADE, CLOTHES_DARK)
# The static's seed (each frame adds its index)
_STATIC_SEED: Final = 20261114
# The spawn's frame that pops (before it, the screen bulges; after it, settles)
_POP_FRAME: Final = 2
# The screen's box, inside the bezel
_SCREEN: Final = (10, 19, 33, 36)
# The smashed screen's hole: its centre and radii
_HOLE_CENTRE: Final = (22.0, 27.5)
_HOLE_RADII: Final = (8.5, 6.5)
# Where the smashed screen's spark is, per frame (on the hole's rim)
_SPARKS: Final = ((15, 23), (29, 31), (22, 21))
# The destroyed TV's smoke: a puff's centre per frame, rising
_SMOKE: Final = ((24.0, 11.0), (26.0, 7.0), (23.0, 3.5))


def _draw_case(canvas: Canvas, *, stage: str = 'intact') -> None:
    """Draw the legs, the wood case, the bezel, the grille, the knobs and the antenna.

    A smashed TV's right antenna arm is bent flat; a destroyed TV's case is scorched (its
    darkest wood) and both arms hang down.
    """
    wood = SKIN_SHADE * 3 if stage == 'destroyed' else SKIN_RAMP
    canvas.capsule(start=(12.0, 40.0), end=(9.0, 46.0), radius=1.6, ramp=wood)
    canvas.capsule(start=(36.0, 40.0), end=(39.0, 46.0), radius=1.6, ramp=wood)
    canvas.box(left=4, top=15, right=43, bottom=41, ramp=wood)
    for y in range(_SCREEN[1] - 1, _SCREEN[3] + 2):
        canvas.row(y=y, left=_SCREEN[0] - 1, right=_SCREEN[2] + 1, character=HAIR)
    canvas.box(left=35, top=19, right=41, bottom=37, ramp=PANTS_RAMP)
    for grille_y in range(21, 37, 2):
        canvas.row(y=grille_y, left=36, right=40, character=PANTS_SHADE)
    for knob_y in (22, 28):
        canvas.row(y=knob_y, left=37, right=39, character=SHOES)
        canvas.row(y=knob_y + 1, left=37, right=39, character=SHOES)
    # The rabbit-ear antenna, centred on the case's top
    left_tip = (13.0, 13.0) if stage == 'destroyed' else (15.0, 2.0)
    right_tip = {'smashed': (38.0, 12.0), 'destroyed': (35.0, 13.0)}.get(stage, (33.0, 2.0))
    canvas.capsule(start=(24.0, 14.0), end=left_tip, radius=0.7, ramp=HEADSET)
    canvas.capsule(start=(24.0, 14.0), end=right_tip, radius=0.7, ramp=HEADSET)
    canvas.ellipse(centre=(24.0, 14.0), radii=(3.2, 1.8), ramp=HAIR)
    canvas.row(y=40, left=5, right=42, character=PANTS)


def _draw_static(canvas: Canvas, *, frame: int, grow: int = 0, lighten: bool = False) -> None:
    """Fill the screen with static (``grow``: how far it bulges past the bezel)."""
    left, top, right, bottom = _SCREEN
    # Noise from a generator seeded by the frame, so each build draws the same static (art is
    # built, not played: no gameplay random stream is involved)
    noise = random.Random(_STATIC_SEED + frame)  # ruff: ignore[suspicious-non-cryptographic-random-usage] - pixel noise, not security
    for y in range(top - grow, bottom + grow + 1):
        for x in range(left - grow, right + grow + 1):
            tone = noise.choice(_STATIC_TONES)
            if lighten and tone in {CLOTHES_SHADE, CLOTHES_DARK}:
                tone = CLOTHES
            canvas.put(x=x, y=y, character=tone)
    # A scanline of glow drifting down the screen
    canvas.row(y=top + (frame * 5) % (bottom - top), left=left, right=right, character=WHITE)


def _draw_crack(canvas: Canvas) -> None:
    """Draw a white crack across the screen, corner to corner, with a branch."""
    left, top, right, bottom = _SCREEN
    for step in range(right - left + 1):
        x = left + step
        y = top + round(step * (bottom - top) / (right - left))
        canvas.put(x=x, y=y, character=WHITE)
    for step in range(7):
        canvas.put(x=24 + step, y=26 - step // 2, character=WHITE)


def _draw_hole(canvas: Canvas, *, frame: int, flash: bool = False) -> None:
    """Draw the smashed screen's hole: dark shards round black, a spark on the rim."""
    canvas.ellipse(
        centre=_HOLE_CENTRE,
        radii=(_HOLE_RADII[0] + 1.5, _HOLE_RADII[1] + 1.5),
        ramp=CLOTHES_DARK * 2 + HAIR,
    )
    canvas.ellipse(centre=_HOLE_CENTRE, radii=_HOLE_RADII, ramp=WHITE * 3 if flash else HAIR * 3)
    spark_x, spark_y = _SPARKS[frame % len(_SPARKS)]
    canvas.put(x=spark_x, y=spark_y, character=WHITE)
    for near_x, near_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        canvas.put(x=spark_x + near_x, y=spark_y + near_y, character=SHOES)


def _draw_destroyed(canvas: Canvas, *, frame: int) -> None:
    """Draw the dead screen, black, and a puff of smoke rising from the top."""
    left, top, right, bottom = _SCREEN
    for y in range(top, bottom + 1):
        canvas.row(y=y, left=left, right=right, character=HAIR)
    canvas.put(x=16 + frame * 5, y=24 + frame * 3, character=CLOTHES_DARK)
    for puff, (centre_x, centre_y) in enumerate(_SMOKE[: frame + 1]):
        radius = 2.2 + puff * 0.8
        canvas.ellipse(
            centre=(centre_x, centre_y),
            radii=(radius, radius * 0.8),
            ramp=CLOTHES_LIGHT + CLOTHES + CLOTHES_SHADE,
        )


def draw_tv(*, state: str, frame: int) -> Grid:
    """Return one frame of the TV, outlined.

    Args:
        state: ``static`` or ``spawn``, either with a ``cracked-`` or ``smashed-`` stage in
            front, or ``destroyed``.
        frame: The frame's index in its animation.

    Returns:
        48 rows of 48 palette characters.

    """
    stage, _, action = state.rpartition('-')
    if state == 'destroyed':
        stage, action = 'destroyed', ''
    canvas = Canvas(width=WIDTH, height=HEIGHT)
    _draw_case(canvas, stage=stage or 'intact')
    if stage == 'destroyed':
        _draw_destroyed(canvas, frame=frame)
    else:
        _draw_screen(canvas, action=action, frame=frame)
        if stage == 'cracked':
            _draw_crack(canvas)
        elif stage == 'smashed':
            _draw_hole(canvas, frame=frame, flash=action == 'spawn' and frame == _POP_FRAME)
    outline_figure(canvas)
    return canvas.grid()


def _draw_screen(canvas: Canvas, *, action: str, frame: int) -> None:
    """Draw the screen's static, or a spawn's bulge, pop and settle."""
    state = action
    if state == 'static':
        _draw_static(canvas, frame=frame)
    elif frame < _POP_FRAME:
        # The screen bulges outward, then further, lighter as it swells
        _draw_static(canvas, frame=frame + 3, grow=frame + 1, lighten=True)
    elif frame == _POP_FRAME:
        # The pop: a flash fills and overflows the screen
        _draw_static(canvas, frame=frame + 3, grow=3, lighten=True)
        canvas.ellipse(centre=(22.0, 27.5), radii=(13.0, 11.0), ramp=WHITE * 3 + CLOTHES_LIGHT)
    else:
        _draw_static(canvas, frame=frame + 3)


def tv_frames() -> dict[str, tuple[Grid, ...]]:
    """Return the TV's animations' frames, in the props BOM's order.

    Returns:
        Namespace -> frames.

    """
    frames: dict[str, tuple[Grid, ...]] = {}
    for stage in STAGES[:-1]:
        prefix = '' if stage == 'intact' else f'{stage}-'
        frames[f'{prefix}static'] = tuple(
            draw_tv(state=f'{prefix}static', frame=frame) for frame in range(3)
        )
        frames[f'{prefix}spawn'] = tuple(
            draw_tv(state=f'{prefix}spawn', frame=frame) for frame in range(4)
        )
    frames['destroyed'] = tuple(draw_tv(state='destroyed', frame=frame) for frame in range(3))
    return frames
