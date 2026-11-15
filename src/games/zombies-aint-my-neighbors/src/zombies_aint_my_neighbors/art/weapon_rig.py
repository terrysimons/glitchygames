"""The weapons' rig: the Channel Changer (a TV remote) and the zap it fires.

The props BOM (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md), feature plan 6. Both are
12x12 and share one palette. The remote is drawn centred on a kid's hand point, one frame per
drawn facing (down, up, left; right is left mirrored), with its LED where a zap leaves
(``remote_tip``). The zap is a ring of static round a flickering core; its static, like the
TV's, is noise from a generator seeded by the frame, so the file never changes between builds.
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
    HEADSET,
    PANTS,
    PANTS_LIGHT,
    SHOES,
    SKIN_RAMP,
    WHITE,
    kid_palette,
)
from zombies_aint_my_neighbors.art.poses import AnimationSpec
from zombies_aint_my_neighbors.art.rig import Canvas, Grid, Point, outline_figure

# The palette, on the rig's characters: the remote's black case (the skin ramp's characters), the
# zap's static (the clothes ramp: the TV's four greys), the LED's greens (the trousers ramp), the
# power button's red (shoes), the glow (white) and the buttons' grey (the headset's). The hair
# character is unused
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
WEAPON_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((92, 92, 106), (56, 56, 68), (32, 32, 40)),
        hair=(44, 44, 52),
        clothes=((214, 218, 222), (160, 166, 174), (104, 110, 120), (58, 62, 70)),
        pants=((196, 255, 186), (86, 236, 96), (34, 150, 64)),
        shoes=(224, 44, 52),
    )
)

SIZE: Final = 12
# The LED's character (a zap leaves from it)
LED: Final = PANTS
# The canvas's centre, placed on a kid's hand point
GRIP: Final[Point] = (6, 6)

# The remote's drawn facings (right is left mirrored)
REMOTE_FACINGS: Final = ('down', 'up', 'left')
# Where a zap leaves, per facing: the LED's cell. Right mirrors left (x' = 11 - x)
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
REMOTE_TIPS: Final = MappingProxyType({
    'down': (6, 10),
    'up': (6, 1),
    'left': (1, 6),
    'right': (SIZE - 1 - 1, 6),
})

# The props BOM's Channel Changer and zap
CHANNEL_CHANGER_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='held', facings=(), frame_interval=0.08, loop=True),
)
ZAP_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='fly', facings=(), frame_interval=0.06, loop=True),
    AnimationSpec(state='fizzle', facings=(), frame_interval=0.06, loop=False),
)

_STATIC_TONES: Final = (CLOTHES_LIGHT, CLOTHES, CLOTHES_SHADE, CLOTHES_DARK)
# The zap's static seed (each frame adds its index)
_STATIC_SEED: Final = 20261115
# The zap's ring: cells this far from the centre, in pixels
_RING_INNER: Final = 2.2
_RING_OUTER: Final = 4.6
# Specks left in each fizzle frame
_FIZZLE_SPECKS: Final = (7, 3)


def remote_tip(*, facing: str) -> tuple[int, int]:
    """Return where a zap leaves the remote, on its 12x12 canvas.

    Args:
        facing: ``down``, ``up``, ``left`` or ``right``.

    Returns:
        The LED's (x, y).

    """
    return REMOTE_TIPS[facing]


def _draw_remote_long(canvas: Canvas, *, led_y: int, button: bool) -> None:
    """Draw the remote seen end-on (pointing down or up): 6 wide, 10 tall, the LED at ``led_y``."""
    canvas.box(left=3, top=1, right=8, bottom=10, ramp=SKIN_RAMP)
    for button_y in (4, 6, 8):
        canvas.put(x=4, y=button_y, character=HEADSET)
        canvas.put(x=7, y=button_y, character=HEADSET)
    if button:
        canvas.row(y=2 if led_y > GRIP[1] else 9, left=5, right=6, character=SHOES)
    canvas.row(y=led_y, left=5, right=6, character=LED)


def draw_channel_changer(*, facing: str) -> Grid:
    """Return the remote in one drawn facing, outlined.

    Args:
        facing: ``down`` (end-on, the LED toward the viewer, below the hand), ``up`` (its back,
            the LED away, above the hand) or ``left`` (side-on, the LED at the left end).

    Returns:
        12 rows of 12 palette characters.

    """
    canvas = Canvas(width=SIZE, height=SIZE)
    if facing == 'down':
        _draw_remote_long(canvas, led_y=REMOTE_TIPS['down'][1], button=True)
    elif facing == 'up':
        _draw_remote_long(canvas, led_y=REMOTE_TIPS['up'][1], button=False)
    else:
        canvas.box(left=2, top=4, right=10, bottom=8, ramp=SKIN_RAMP)
        canvas.row(y=4, left=7, right=8, character=SHOES)
        for button_x in (4, 6, 8):
            canvas.put(x=button_x, y=6, character=HEADSET)
        canvas.put(x=1, y=6, character=LED)
        canvas.put(x=1, y=5, character=PANTS_LIGHT)
    outline_figure(canvas)
    return canvas.grid()


def channel_changer_frames() -> dict[str, tuple[Grid, ...]]:
    """Return the remote's animations' frames, in the props BOM's order.

    Returns:
        Namespace -> frames (one each).

    """
    return {f'held_{facing}': (draw_channel_changer(facing=facing),) for facing in REMOTE_FACINGS}


def _noise(frame: int) -> random.Random:
    """Return the zap's noise for a frame (art is built, not played: no gameplay stream).

    Returns:
        A generator seeded by the frame.

    """
    return random.Random(_STATIC_SEED + frame)  # ruff: ignore[suspicious-non-cryptographic-random-usage] - pixel noise, not security


def draw_zap(*, state: str, frame: int) -> Grid:
    """Return one frame of the zap, outlined.

    Args:
        state: ``fly`` (the ring and its core) or ``fizzle`` (specks, fewer each frame).
        frame: The frame's index in its animation.

    Returns:
        12 rows of 12 palette characters.

    """
    canvas = Canvas(width=SIZE, height=SIZE)
    noise = _noise(frame if state == 'fly' else frame + 3)
    centre = (SIZE - 1) / 2
    ring = [
        (x, y)
        for y in range(SIZE)
        for x in range(SIZE)
        if _RING_INNER <= ((x - centre) ** 2 + (y - centre) ** 2) ** 0.5 <= _RING_OUTER
    ]
    if state == 'fly':
        for x, y in ring:
            canvas.put(x=x, y=y, character=noise.choice(_STATIC_TONES))
        core = (LED, WHITE, PANTS_LIGHT)[frame % 3]
        canvas.row(y=5, left=5, right=6, character=core)
        canvas.row(y=6, left=5, right=6, character=core)
    else:
        for x, y in noise.sample(ring, _FIZZLE_SPECKS[frame]):
            canvas.put(x=x, y=y, character=noise.choice((CLOTHES_LIGHT, LED, WHITE)))
    outline_figure(canvas)
    return canvas.grid()


def zap_frames() -> dict[str, tuple[Grid, ...]]:
    """Return the zap's animations' frames, in the props BOM's order.

    Returns:
        Namespace -> frames.

    """
    return {
        'fly': tuple(draw_zap(state='fly', frame=frame) for frame in range(3)),
        'fizzle': tuple(draw_zap(state='fizzle', frame=frame) for frame in range(2)),
    }
