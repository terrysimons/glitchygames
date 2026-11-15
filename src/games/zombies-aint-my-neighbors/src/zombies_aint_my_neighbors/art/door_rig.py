"""The exit door's rig: a garden gate in the top hedge, glowing VR blue once open.

The props BOM's exit door (plans/2026-11-14-zombies-aint-my-neighbors-props-bom.md), feature
plan 7: 48x48, ``closed`` (1 frame), ``opening`` (3 frames, 0.08 s: the gate swings in, the glow
grows) and ``open`` (2 frames, 0.2 s, looping: the glow pulses). It draws with the kids' canvas
and outline (``rig``). It is symmetric, and never mirrored.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Final

from zombies_aint_my_neighbors.art.palettes import (
    CLOTHES,
    CLOTHES_DARK,
    CLOTHES_LIGHT,
    CLOTHES_SHADE,
    HAIR,
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

# The gate's white wood (the skin ramp's characters), the posts' dark wood (hair, shoes), the
# hedge's greens (the trousers ramp), the glow's blues (the clothes ramp: saved's blues) and white
# Read-only: module state shared by every engine context (tests/test_process_state_guard.py)
DOOR_PALETTE: Final = MappingProxyType(
    kid_palette(
        skin=((250, 248, 240), (222, 218, 206), (172, 168, 158)),
        hair=(70, 50, 36),
        clothes=((200, 240, 255), (96, 200, 255), (40, 140, 230), (24, 84, 170)),
        pants=((76, 120, 70), (52, 92, 52), (36, 66, 40)),
        shoes=(116, 84, 56),
    )
)

WIDTH: Final = 48
HEIGHT: Final = 48

# The props BOM's exit door
DOOR_ANIMATIONS: Final[tuple[AnimationSpec, ...]] = (
    AnimationSpec(state='closed', facings=(), frame_interval=0.08, loop=True),
    AnimationSpec(state='opening', facings=(), frame_interval=0.08, loop=False, then_state='open'),
    AnimationSpec(state='open', facings=(), frame_interval=0.2, loop=True),
)

# The gateway between the posts
_GAP_LEFT: Final = 12
_GAP_RIGHT: Final = 35
_GAP_TOP: Final = 14
_GAP_BOTTOM: Final = 46
# The glow's full strength: from here on a bright core shows in the gateway
_FULL_GLOW: Final = 2


def _draw_hedge_and_posts(canvas: Canvas) -> None:
    """Draw the hedge either side and the two gate posts with their caps."""
    for left, right in ((0, 9), (38, 47)):
        canvas.box(left=left, top=10, right=right, bottom=47, ramp=PANTS_RAMP)
        for leaf_y in range(13, 46, 4):
            canvas.put(x=left + 3 + leaf_y % 3, y=leaf_y, character=PANTS_SHADE)
            canvas.put(x=left + 6 - leaf_y % 2, y=leaf_y + 2, character=PANTS)
    for post_left in (_GAP_LEFT - 3, _GAP_RIGHT + 1):
        canvas.box(
            left=post_left, top=10, right=post_left + 2, bottom=47, ramp=SHOES + SHOES + HAIR
        )
        canvas.row(y=9, left=post_left - 1, right=post_left + 3, character=SKIN_SHADE)


def _draw_glow(canvas: Canvas, *, strength: int) -> None:
    """Fill the gateway with the safe room's glow: 0 none, 1 faint, 2 full, 3 bright."""
    if strength == 0:
        return
    ramps = {
        1: CLOTHES_DARK * 3,
        2: CLOTHES_SHADE + CLOTHES + CLOTHES_SHADE,
        3: CLOTHES + CLOTHES_LIGHT + CLOTHES,
    }
    canvas.box(
        left=_GAP_LEFT, top=_GAP_TOP, right=_GAP_RIGHT, bottom=_GAP_BOTTOM, ramp=ramps[strength]
    )
    if strength >= _FULL_GLOW:
        centre_x = (_GAP_LEFT + _GAP_RIGHT) / 2
        canvas.ellipse(
            centre=(centre_x, 30.0),
            radii=(6.0 + strength, 9.0 + strength),
            ramp=CLOTHES_LIGHT + WHITE + CLOTHES_LIGHT,
        )


def _draw_gate(canvas: Canvas, *, swing: int) -> None:
    """Draw the two picket leaves, each swung in by ``swing`` thirds (narrower toward its post)."""
    half = (_GAP_RIGHT - _GAP_LEFT + 1) // 2
    leaf_width = half - (half * swing) // 3
    if leaf_width <= 0:
        return
    for leaf_left in (_GAP_LEFT, _GAP_RIGHT - leaf_width + 1):
        leaf_right = leaf_left + leaf_width - 1
        for rail_y in (24, 38):
            canvas.row(y=rail_y, left=leaf_left, right=leaf_right, character=SKIN_SHADE)
        for picket_x in range(leaf_left, leaf_right + 1, 3):
            canvas.box(
                left=picket_x,
                top=18,
                right=min(picket_x + 1, leaf_right),
                bottom=44,
                ramp=SKIN_RAMP,
            )
            canvas.put(x=picket_x, y=17, character=SKIN_RAMP[0])


def draw_door(*, state: str, frame: int) -> Grid:
    """Return one frame of the exit door, outlined.

    Args:
        state: ``closed``, ``opening`` or ``open``.
        frame: The frame's index in its animation.

    Returns:
        48 rows of 48 palette characters.

    """
    canvas = Canvas(width=WIDTH, height=HEIGHT)
    _draw_hedge_and_posts(canvas)
    if state == 'closed':
        _draw_gate(canvas, swing=0)
    elif state == 'opening':
        _draw_glow(canvas, strength=frame + 1)
        _draw_gate(canvas, swing=frame + 1)
    else:
        _draw_glow(canvas, strength=3 if frame == 0 else 2)
    outline_figure(canvas)
    return canvas.grid()


def door_frames() -> dict[str, tuple[Grid, ...]]:
    """Return the door's animations' frames, in the props BOM's order.

    Returns:
        Namespace -> frames.

    """
    return {
        'closed': (draw_door(state='closed', frame=0),),
        'opening': tuple(draw_door(state='opening', frame=frame) for frame in range(3)),
        'open': tuple(draw_door(state='open', frame=frame) for frame in range(2)),
    }
