"""The TV's rig: a boxy wood-cased set on splayed legs, showing static; monsters come out of it.

The props BOM's TV (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md): 48x48, ``static``
(3 frames, looping) and ``spawn`` (4 frames: the screen bulges, bulges further, pops in a flash,
settles). It draws with the kids' canvas, shading and outline (``rig``). The static is noise
from a generator seeded by the frame, so the file never changes between builds.
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
)

_STATIC_TONES: Final = (CLOTHES_LIGHT, CLOTHES, CLOTHES_SHADE, CLOTHES_DARK)
# The static's seed (each frame adds its index)
_STATIC_SEED: Final = 20261114
# The spawn's frame that pops (before it, the screen bulges; after it, settles)
_POP_FRAME: Final = 2
# The screen's box, inside the bezel
_SCREEN: Final = (10, 19, 33, 36)


def _draw_case(canvas: Canvas) -> None:
    """Draw the legs, the wood case, the bezel, the grille, the knobs and the antenna."""
    canvas.capsule(start=(12.0, 40.0), end=(9.0, 46.0), radius=1.6, ramp=SKIN_RAMP)
    canvas.capsule(start=(36.0, 40.0), end=(39.0, 46.0), radius=1.6, ramp=SKIN_RAMP)
    canvas.box(left=4, top=15, right=43, bottom=41, ramp=SKIN_RAMP)
    for y in range(_SCREEN[1] - 1, _SCREEN[3] + 2):
        canvas.row(y=y, left=_SCREEN[0] - 1, right=_SCREEN[2] + 1, character=HAIR)
    canvas.box(left=35, top=19, right=41, bottom=37, ramp=PANTS_RAMP)
    for grille_y in range(21, 37, 2):
        canvas.row(y=grille_y, left=36, right=40, character=PANTS_SHADE)
    for knob_y in (22, 28):
        canvas.row(y=knob_y, left=37, right=39, character=SHOES)
        canvas.row(y=knob_y + 1, left=37, right=39, character=SHOES)
    # The rabbit-ear antenna, centred on the case's top
    canvas.capsule(start=(24.0, 14.0), end=(15.0, 2.0), radius=0.7, ramp=HEADSET)
    canvas.capsule(start=(24.0, 14.0), end=(33.0, 2.0), radius=0.7, ramp=HEADSET)
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


def draw_tv(*, state: str, frame: int) -> Grid:
    """Return one frame of the TV, outlined.

    Args:
        state: ``static`` or ``spawn``.
        frame: The frame's index in its animation.

    Returns:
        48 rows of 48 palette characters.

    """
    canvas = Canvas(width=WIDTH, height=HEIGHT)
    _draw_case(canvas)
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
    outline_figure(canvas)
    return canvas.grid()


def tv_frames() -> dict[str, tuple[Grid, ...]]:
    """Return the TV's animations' frames, in the props BOM's order.

    Returns:
        Namespace -> frames.

    """
    return {
        'static': tuple(draw_tv(state='static', frame=frame) for frame in range(3)),
        'spawn': tuple(draw_tv(state='spawn', frame=frame) for frame in range(4)),
    }
