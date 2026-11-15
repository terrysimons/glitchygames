"""The kids' rig: draws a 32x48 frame from a pose and a look, in SNES-era detail.

Volumes are shaded with the look's ramps from a light at the top left: the head is an ellipse,
the torso a rounded box, arms and legs capsules shaded across their width. Hand-drawn details go
on top (faces, the VR goggles, each kid's hair and clothes). One pass then outlines the figure
in the cast's shared outline, so every kid is outlined the same way. Head and clothes styles
change colours, and add shapes only above ``SHOULDER_ROW``, so every kid has the same silhouette
from the shoulders down (the shared rig). The approved style sample is feature plan 3's.

Coordinates are columns 0 to 31 and rows 0 to 47. The upper body (head, torso, arms) moves down
by a pose's ``bob`` and right by its ``lean``; the legs stay put.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict

from zombies_aint_my_neighbors.art import poses
from zombies_aint_my_neighbors.art.palettes import (
    CLOTHES,
    CLOTHES_DARK,
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
    SKIN_SHADE,
    TRANSPARENT,
    WHITE,
    ClothesStyle,
    HeadStyle,
)
from zombies_aint_my_neighbors.art.poses import Arms, Facing, Legs, Pose, Special

if TYPE_CHECKING:
    from zombies_aint_my_neighbors.art.palettes import KidLook

type Point = tuple[float, float]
type Grid = tuple[str, ...]

WIDTH: Final = 32
HEIGHT: Final = 48
# The first row below every kid's head details: kids differ only in colour from here down
SHOULDER_ROW: Final = 22

# The light comes from the top left: a surface's tone from its position (-1 lit, 1 shadowed)
_LIGHT_ACROSS: Final = 0.75
_LIGHT_DOWN: Final = 0.45
_LIGHT_BIAS: Final = 0.15
ARM_RADIUS: Final = 2.2
LEG_RADIUS: Final = 2.6
HAND_RADII: Final[Point] = (2.1, 1.9)
# Hair lighter than this (luma, 0 to 255) takes a white sheen, darker hair the cool grey
_LIGHT_HAIR_THRESHOLD: Final = 110
# Only near-black hair shows strands: on brown hair a grey strand reads as a stripe
_STRANDED_HAIR_THRESHOLD: Final = 50
# The sheen: an arc on the top-left of a hair shape, at this fraction of its radii
_SHEEN_RADIUS: Final = 0.62
_SHEEN_START_DEGREES: Final = 200
_SHEEN_END_DEGREES: Final = 265
_SHEEN_STEP_DEGREES: Final = 6

# Front and back views: the shoulders, and the (left, right) hands as the viewer sees them
_FRONT_SHOULDERS: Final[tuple[Point, Point]] = ((7.5, 22.0), (24.5, 22.0))
_FRONT_HANDS: Final[dict[Arms, tuple[Point, Point]]] = {
    Arms.SIDES: ((6.6, 33.2), (25.4, 33.2)),
    Arms.LEFT_FORWARD: ((7.0, 31.5), (25.4, 33.2)),
    Arms.RIGHT_FORWARD: ((6.6, 33.2), (25.0, 31.5)),
    Arms.AIM: ((14.5, 29.0), (17.5, 29.0)),
    Arms.AIM_RECOIL: ((14.5, 27.5), (17.5, 27.5)),
    Arms.BRACE: ((12.5, 31.0), (19.5, 31.0)),
    Arms.BRACE_SHUDDER: ((12.5, 31.0), (19.5, 31.0)),
    Arms.SWING_BACK: ((25.0, 22.0), (27.5, 24.0)),
    Arms.SWING_ACROSS: ((17.0, 29.0), (19.5, 29.0)),
    Arms.SWING_THROUGH: ((4.5, 31.0), (7.0, 29.0)),
    Arms.SHOULDER: ((20.0, 25.0), (25.5, 20.0)),
    Arms.THROW_WINDUP: ((6.6, 33.2), (27.5, 11.0)),
    Arms.THROW_RELEASE: ((6.6, 33.2), (21.0, 18.0)),
    Arms.THROW_FOLLOW: ((6.6, 33.2), (11.0, 31.0)),
    Arms.FISTS_UP: ((4.5, 13.0), (27.5, 13.0)),
    Arms.FISTS_HIGH: ((6.0, 8.5), (26.0, 8.5)),
    Arms.HIGH_FIVE: ((6.6, 33.2), (27.5, 13.0)),
    Arms.HIGH_FIVE_UP: ((6.6, 33.2), (25.5, 8.5)),
}

# Side view (facing left): the near shoulder and hand
_SIDE_SHOULDER: Final[Point] = (16.0, 22.0)
_SIDE_HANDS: Final[dict[Arms, Point]] = {
    Arms.SIDES: (16.0, 33.5),
    Arms.LEFT_FORWARD: (12.0, 32.0),
    Arms.RIGHT_FORWARD: (20.0, 32.0),
    Arms.AIM: (5.0, 25.0),
    Arms.AIM_RECOIL: (7.0, 25.0),
    Arms.BRACE: (7.0, 29.0),
    Arms.BRACE_SHUDDER: (7.0, 29.0),
    Arms.SWING_BACK: (21.5, 20.0),
    Arms.SWING_ACROSS: (8.0, 25.0),
    Arms.SWING_THROUGH: (7.0, 31.0),
    Arms.SHOULDER: (17.0, 20.0),
    Arms.THROW_WINDUP: (23.5, 12.0),
    Arms.THROW_RELEASE: (8.0, 16.0),
    Arms.THROW_FOLLOW: (8.0, 31.0),
    Arms.FISTS_UP: (12.0, 12.0),
    Arms.FISTS_HIGH: (12.0, 8.0),
    Arms.HIGH_FIVE: (12.0, 13.0),
    Arms.HIGH_FIVE_UP: (12.0, 10.0),
}

# Arms reaching forward: seen from behind they are hidden by the body, so drawn first
# The diagonal facings, drawn as the front or back view turned a quarter to the left: the
# upper body shifts this far left, and the face's features further still
_DIAGONALS: Final = frozenset({Facing.DOWN_LEFT, Facing.UP_LEFT})
_DIAGONAL_TURN: Final = -1
_BASE_FACING: Final[dict[Facing, Facing]] = {
    Facing.DOWN: Facing.DOWN,
    Facing.UP: Facing.UP,
    Facing.LEFT: Facing.LEFT,
    Facing.DOWN_LEFT: Facing.DOWN,
    Facing.UP_LEFT: Facing.UP,
}

_FORWARD_ARMS: Final = frozenset({
    Arms.AIM,
    Arms.AIM_RECOIL,
    Arms.BRACE,
    Arms.BRACE_SHUDDER,
    Arms.SWING_ACROSS,
    Arms.SHOULDER,
    Arms.THROW_RELEASE,
})


def tone(*, value: float, ramp: str) -> str:
    """Return the ramp's character for a lighting value (-1 lit to 1 shadowed).

    Returns:
        One character of the ramp.

    """
    index = int((value + 1) / 2 * len(ramp))
    return ramp[min(len(ramp) - 1, max(0, index))]


class Canvas:
    """A grid of palette characters (32x48 by default), transparent to start.

    Drawing is offset by ``shift_x`` and ``shift_y`` (a pose's lean and bob).
    """

    def __init__(self, *, width: int = WIDTH, height: int = HEIGHT) -> None:
        """Make an empty, transparent canvas (a kid's 32x48 unless sized otherwise)."""
        self.width = width
        self.height = height
        self.cells = [[TRANSPARENT] * width for _ in range(height)]
        self.shift_x = 0
        self.shift_y = 0

    def put(self, *, x: float, y: float, character: str) -> None:
        """Paint one cell, shifted (cells outside the canvas are ignored)."""
        column, row = int(x) + self.shift_x, int(y) + self.shift_y
        if 0 <= column < self.width and 0 <= row < self.height:
            self.cells[row][column] = character

    def at(self, *, x: int, y: int) -> str:
        """Return one cell's character, unshifted (transparent outside the canvas).

        Returns:
            The character.

        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return TRANSPARENT

    def row(self, *, y: int, left: int, right: int, character: str) -> None:
        """Paint a run of one row, ``right`` included."""
        for x in range(left, right + 1):
            self.put(x=x, y=y, character=character)

    def column(self, *, x: int, top: int, bottom: int, character: str) -> None:
        """Paint a run of one column, ``bottom`` included."""
        for y in range(top, bottom + 1):
            self.put(x=x, y=y, character=character)

    def ellipse(self, *, centre: Point, radii: Point, ramp: str, bottom: int | None = None) -> None:
        """Paint a shaded ellipse (only rows down to ``bottom``, when given)."""
        centre_x, centre_y = centre
        radius_x, radius_y = radii
        for y in range(self.height):
            if bottom is not None and y > bottom:
                break
            for x in range(self.width):
                across = (x + 0.5 - centre_x) / radius_x
                down = (y + 0.5 - centre_y) / radius_y
                if across * across + down * down <= 1:
                    value = _LIGHT_ACROSS * across + _LIGHT_DOWN * down + _LIGHT_BIAS
                    self.put(x=x, y=y, character=tone(value=value, ramp=ramp))

    def box(self, *, left: int, top: int, right: int, bottom: int, ramp: str) -> None:
        """Paint a shaded box with its corners rounded off."""
        half_width, half_height = (right - left + 1) / 2, (bottom - top + 1) / 2
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if x in {left, right} and y in {top, bottom}:
                    continue
                across = (x + 0.5 - left - half_width) / half_width
                down = (y + 0.5 - top - half_height) / half_height
                value = 0.85 * across + 0.25 * down
                self.put(x=x, y=y, character=tone(value=value, ramp=ramp))

    def capsule(self, *, start: Point, end: Point, radius: float, ramp: str) -> None:
        """Paint a limb: every cell within ``radius`` of the segment, shaded across it."""
        (start_x, start_y), (end_x, end_y) = start, end
        delta_x, delta_y = end_x - start_x, end_y - start_y
        length_squared = delta_x * delta_x + delta_y * delta_y or 1.0
        for y in range(self.height):
            for x in range(self.width):
                point_x, point_y = x + 0.5, y + 0.5
                along = (point_x - start_x) * delta_x + (point_y - start_y) * delta_y
                along = max(0.0, min(1.0, along / length_squared))
                nearest_x, nearest_y = start_x + along * delta_x, start_y + along * delta_y
                if math.hypot(point_x - nearest_x, point_y - nearest_y) <= radius:
                    value = 0.9 * (point_x - nearest_x) / radius + 0.1
                    self.put(x=x, y=y, character=tone(value=value, ramp=ramp))

    def grid(self) -> Grid:
        """Return the canvas as rows of characters.

        Returns:
            The rows, top to bottom.

        """
        return tuple(''.join(cells) for cells in self.cells)


def silhouette(rows: Grid | tuple[str, ...]) -> tuple[str, ...]:
    """Return rows with every drawn cell as ``#`` and every transparent one as ``.``.

    Returns:
        The silhouette rows.

    """
    return tuple(''.join('.' if cell == TRANSPARENT else '#' for cell in row) for row in rows)


def hand_positions(*, pose: Pose) -> tuple[tuple[int, int], ...]:
    """Return where a pose's hands are, in cells after bob and lean (one hand in the side view).

    Returns:
        The hands: (left, right) in the front and back views, (near,) in the side view.

    """
    if pose.facing is Facing.LEFT:
        hands: tuple[Point, ...] = (_SIDE_HANDS[pose.arms],)
    else:
        hands = _FRONT_HANDS[pose.arms]
    turn = _DIAGONAL_TURN if pose.facing in _DIAGONALS else 0
    return tuple((int(x) + pose.lean + turn, int(y) + pose.bob) for x, y in hands)


def _draw_arms(canvas: Canvas, *, pose: Pose) -> None:
    """Draw the arms: sleeves as shaded capsules, a shaded hand at each end."""
    if pose.facing is Facing.LEFT:
        pairs: tuple[tuple[Point, Point], ...] = ((_SIDE_SHOULDER, _SIDE_HANDS[pose.arms]),)
    else:
        pairs = tuple(zip(_FRONT_SHOULDERS, _FRONT_HANDS[pose.arms], strict=True))
    for shoulder, hand in pairs:
        canvas.capsule(start=shoulder, end=hand, radius=ARM_RADIUS, ramp=CLOTHES_RAMP)
        canvas.ellipse(centre=hand, radii=HAND_RADII, ramp=SKIN_RAMP)


def _draw_shoe(canvas: Canvas, *, left: int, right: int, top: int) -> None:
    """Draw one shoe: the upper with laces, a white sole with a grey heel."""
    for y in (top, top + 1):
        canvas.row(y=y, left=left, right=right, character=SHOES)
    canvas.row(y=top + 2, left=left, right=right, character=WHITE)
    canvas.row(y=top + 2, left=right - 1, right=right, character=HEADSET)
    canvas.put(x=left + 1, y=top, character=WHITE)
    canvas.put(x=left + 3, y=top, character=WHITE)


def _draw_legs(canvas: Canvas, *, pose: Pose, look: KidLook) -> None:
    """Draw the legs and shoes (they never bob or lean; a diagonal turns them with the body)."""
    canvas.shift_x = _DIAGONAL_TURN if pose.facing in _DIAGONALS else 0
    if pose.facing is Facing.LEFT:
        _draw_side_legs(canvas, legs=pose.legs)
    else:
        left_lift = 2 if pose.legs in {Legs.LEFT_UP, Legs.TUCKED} else 0
        right_lift = 2 if pose.legs in {Legs.RIGHT_UP, Legs.TUCKED} else 0
        canvas.box(left=10, top=33, right=21, bottom=36, ramp=PANTS_RAMP)
        for leg_x, lift in ((12.5, left_lift), (19.5, right_lift)):
            canvas.capsule(
                start=(leg_x, 35), end=(leg_x, 42.5 - lift), radius=LEG_RADIUS, ramp=PANTS_RAMP
            )
        canvas.row(y=43 - left_lift, left=10, right=15, character=PANTS_SHADE)
        canvas.row(y=43 - right_lift, left=17, right=22, character=PANTS_SHADE)
        _draw_shoe(canvas, left=8, right=14, top=44 - left_lift)
        _draw_shoe(canvas, left=17, right=23, top=44 - right_lift)
    if look.clothes is ClothesStyle.OVERALLS and _BASE_FACING[pose.facing] is not Facing.UP:
        # Matching knee patches on both legs (BOM: symmetric, so mirroring keeps them)
        # Patches recolour denim already drawn, never the gap between the legs
        for knee_x in (14,) if pose.facing is Facing.LEFT else (11, 18):
            for patch_x in range(knee_x, knee_x + 3):
                for patch_y, colour in ((39, CLOTHES), (40, CLOTHES_SHADE)):
                    if canvas.at(x=patch_x, y=patch_y) != TRANSPARENT:
                        canvas.put(x=patch_x, y=patch_y, character=colour)


def _draw_side_legs(canvas: Canvas, *, legs: Legs) -> None:
    """Draw the legs seen from the side (facing left)."""
    shaded = PANTS + PANTS_SHADE + PANTS_SHADE
    if legs in {Legs.STRIDE_NEAR, Legs.STRIDE_FAR}:
        near_ramp, far_ramp = (
            (PANTS_RAMP, shaded) if legs is Legs.STRIDE_NEAR else (shaded, PANTS_RAMP)
        )
        canvas.capsule(start=(17.5, 35), end=(21, 42.5), radius=LEG_RADIUS, ramp=far_ramp)
        _draw_shoe(canvas, left=18, right=24, top=44)
        canvas.box(left=12, top=33, right=20, bottom=36, ramp=PANTS_RAMP)
        canvas.capsule(start=(15, 35), end=(11, 42.5), radius=LEG_RADIUS, ramp=near_ramp)
        _draw_shoe(canvas, left=5, right=12, top=44)
        return
    canvas.box(left=12, top=33, right=20, bottom=36, ramp=PANTS_RAMP)
    canvas.capsule(start=(16, 35), end=(16, 42.5), radius=LEG_RADIUS + 0.4, ramp=PANTS_RAMP)
    canvas.row(y=43, left=13, right=19, character=PANTS_SHADE)
    _draw_shoe(canvas, left=10, right=18, top=44)
    if legs is Legs.PASSING:
        # The trailing foot lifts as it passes
        canvas.row(y=42, left=18, right=20, character=SHOES)


def _draw_torso(canvas: Canvas, *, facing: Facing, clothes: ClothesStyle) -> None:
    """Draw the torso and its clothes details."""
    left, right = (11, 21) if facing is Facing.LEFT else (9, 22)
    canvas.box(left=left, top=20, right=right, bottom=33, ramp=CLOTHES_RAMP)
    canvas.row(y=32, left=left, right=right, character=CLOTHES_SHADE)
    canvas.row(y=33, left=left + 1, right=right - 1, character=CLOTHES_DARK)
    if clothes is ClothesStyle.HOODIE:
        _draw_hoodie(canvas, facing=facing)
    elif clothes is ClothesStyle.OVERALLS:
        _draw_overalls(canvas, facing=facing)
    elif clothes is ClothesStyle.VEST:
        _draw_vest(canvas, facing=facing)
    else:
        _draw_windbreaker(canvas, facing=facing)


def _draw_hoodie(canvas: Canvas, *, facing: Facing) -> None:
    """A hoodie: the hood round the neck, drawstrings and a kangaroo pocket in front."""
    if facing is Facing.DOWN:
        canvas.row(y=20, left=11, right=20, character=CLOTHES_DARK)
        canvas.row(y=21, left=12, right=19, character=CLOTHES_SHADE)
        for string_x, tip_x in ((14, 13), (17, 18)):
            canvas.column(x=string_x, top=22, bottom=24, character=WHITE)
            canvas.put(x=tip_x, y=25, character=WHITE)
        canvas.row(y=28, left=11, right=20, character=CLOTHES_DARK)
        canvas.column(x=11, top=28, bottom=31, character=CLOTHES_DARK)
        canvas.column(x=20, top=28, bottom=31, character=CLOTHES_DARK)
    elif facing is Facing.UP:
        for step, (left, right) in enumerate(((10, 21), (10, 21), (11, 20), (12, 19), (13, 18))):
            canvas.row(y=20 + step, left=left, right=right, character=CLOTHES_SHADE)
        canvas.row(y=25, left=13, right=18, character=CLOTHES_DARK)
    else:
        canvas.ellipse(centre=(19.5, 22.5), radii=(2.5, 3.0), ramp=CLOTHES_SHADE + CLOTHES_DARK)
        canvas.row(y=28, left=12, right=16, character=CLOTHES_DARK)


def _draw_overalls(canvas: Canvas, *, facing: Facing) -> None:
    """Denim overalls over a shirt: the bib, straps and buttons."""
    if facing is Facing.DOWN:
        canvas.box(left=12, top=24, right=19, bottom=33, ramp=PANTS_RAMP)
        canvas.column(x=12, top=20, bottom=24, character=PANTS)
        canvas.column(x=19, top=20, bottom=24, character=PANTS_SHADE)
        canvas.put(x=12, y=24, character=WHITE)
        canvas.put(x=19, y=24, character=WHITE)
        canvas.row(y=28, left=14, right=17, character=PANTS_SHADE)
    elif facing is Facing.UP:
        for step in range(5):
            canvas.put(x=12 + step, y=20 + step, character=PANTS)
            canvas.put(x=19 - step, y=20 + step, character=PANTS)
        canvas.box(left=11, top=27, right=20, bottom=33, ramp=PANTS_RAMP)
    else:
        canvas.box(left=11, top=24, right=16, bottom=33, ramp=PANTS_RAMP)
        canvas.column(x=15, top=20, bottom=24, character=PANTS)
        canvas.put(x=15, y=24, character=WHITE)


def _draw_vest(canvas: Canvas, *, facing: Facing) -> None:
    """A sweater vest: a white V-neck collar and a diamond pattern."""
    if facing is Facing.DOWN:
        for step, (left, right) in enumerate(((13, 18), (14, 17), (15, 16))):
            canvas.row(y=20 + step, left=left, right=right, character=WHITE)
        for diamond_x, diamond_y in ((12, 26), (16, 26), (20, 26), (14, 29), (18, 29)):
            canvas.put(x=diamond_x, y=diamond_y, character=CLOTHES_DARK)
            canvas.put(x=diamond_x - 1, y=diamond_y + 1, character=CLOTHES_SHADE)
            canvas.put(x=diamond_x + 1, y=diamond_y + 1, character=CLOTHES_SHADE)
            canvas.put(x=diamond_x, y=diamond_y + 2, character=CLOTHES_DARK)
    elif facing is Facing.UP:
        canvas.row(y=20, left=12, right=19, character=WHITE)
        canvas.column(x=16, top=21, bottom=31, character=CLOTHES_SHADE)
    else:
        canvas.row(y=20, left=12, right=14, character=WHITE)
        canvas.put(x=13, y=21, character=WHITE)
        for diamond_y in (26, 29):
            canvas.put(x=15, y=diamond_y, character=CLOTHES_DARK)
            canvas.put(x=15, y=diamond_y + 1, character=CLOTHES_SHADE)


def _draw_windbreaker(canvas: Canvas, *, facing: Facing) -> None:
    """A windbreaker: a collar, a zip and a white stripe across the chest."""
    # The stripe spans the torso exactly (its edges differ in the side view)
    left, right = (11, 21) if facing is Facing.LEFT else (9, 22)
    for stripe_y in (25, 26):
        canvas.row(y=stripe_y, left=left, right=right, character=WHITE)
    if facing is Facing.DOWN:
        canvas.row(y=20, left=11, right=20, character=CLOTHES_DARK)
        canvas.column(x=16, top=21, bottom=32, character=CLOTHES_DARK)
    elif facing is Facing.UP:
        canvas.row(y=20, left=11, right=20, character=CLOTHES_SHADE)
    else:
        canvas.row(y=20, left=12, right=17, character=CLOTHES_DARK)


def hair_sheen(*, look: KidLook) -> str:
    """Return the highlight a kid's hair takes: white on light hair, the cool grey on dark hair.

    Returns:
        A palette character.

    """
    red, green, blue = look.palette[HAIR]
    lightness = 0.299 * red + 0.587 * green + 0.114 * blue
    return WHITE if lightness > _LIGHT_HAIR_THRESHOLD else HEADSET


def hair_shows_strands(*, look: KidLook) -> bool:
    """Return whether a kid's hair is dark enough to show strands.

    Returns:
        True for near-black hair.

    """
    red, green, blue = look.palette[HAIR]
    return 0.299 * red + 0.587 * green + 0.114 * blue < _STRANDED_HAIR_THRESHOLD


class HairLook(BaseModel):
    """How a kid's hair catches the light: its sheen's colour, and whether strands show."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    sheen: str
    strands: bool


def hair_look(*, look: KidLook) -> HairLook:
    """Return a kid's hair look, from the hair's lightness.

    Returns:
        The sheen and strands.

    """
    return HairLook(sheen=hair_sheen(look=look), strands=hair_shows_strands(look=look))


def _draw_hair_sheen(canvas: Canvas, *, centre: Point, radii: Point, sheen: str) -> None:
    """Draw hair's sheen: a short arc of highlight on the lit (top left) side of a hair shape."""
    centre_x, centre_y = centre
    radius_x, radius_y = radii
    for degrees in range(_SHEEN_START_DEGREES, _SHEEN_END_DEGREES, _SHEEN_STEP_DEGREES):
        angle = math.radians(degrees)
        canvas.put(
            x=centre_x + _SHEEN_RADIUS * radius_x * math.cos(angle),
            y=centre_y + _SHEEN_RADIUS * radius_y * math.sin(angle),
            character=sheen,
        )


def _draw_cap(
    canvas: Canvas, *, head: HeadStyle, centre_x: float, facing: Facing, sheen: str
) -> None:
    """Draw what tops the head: a beanie and pom-pom, or hair with its ``sheen`` highlight."""
    if head is HeadStyle.BEANIE:
        canvas.ellipse(centre=(centre_x, 8.6), radii=(8.8, 7.2), ramp=CLOTHES_RAMP, bottom=9)
        for x in range(int(centre_x) - 9, int(centre_x) + 9):
            canvas.put(x=x, y=9, character=CLOTHES_SHADE if x % 2 else CLOTHES_DARK)
            canvas.put(x=x, y=10, character=CLOTHES_DARK if x % 2 else CLOTHES_SHADE)
        pom_x = centre_x + (2 if facing is Facing.LEFT else 0)
        # A round, fluffy pom-pom: mostly white, grey only on its shadowed side
        canvas.ellipse(centre=(pom_x, 3.0), radii=(3.2, 2.7), ramp=WHITE * 3 + HEADSET)
        return
    # Plain hair (never shaded into the outline: that read as a black hat), with a sheen
    canvas.ellipse(centre=(centre_x, 9.0), radii=(9.2, 7.6), ramp=HAIR, bottom=11)
    _draw_hair_sheen(canvas, centre=(centre_x, 9.0), radii=(9.2, 7.6), sheen=sheen)
    if head is HeadStyle.BUNS:
        if facing is Facing.LEFT:
            buns: tuple[Point, ...] = ((centre_x + 9.0, 4.5),)
        else:
            buns = ((centre_x - 9.0, 4.5), (centre_x + 9.0, 4.5))
        for bun in buns:
            canvas.ellipse(centre=bun, radii=(3.2, 3.0), ramp=HAIR)
            _draw_hair_sheen(canvas, centre=bun, radii=(3.2, 3.0), sheen=sheen)


def _draw_goggle_front(
    canvas: Canvas,
    *,
    strap: tuple[int, int],
    lenses: tuple[int, int],
    edges: tuple[Point, ...],
    glare: tuple[Point, ...],
) -> None:
    """Draw the goggles seen from in front: the strap, the lenses' box, its edges and glare."""
    canvas.row(y=11, left=strap[0], right=strap[1], character=OUTLINE)
    left, right = lenses
    for y in (10, 11, 12):
        canvas.row(y=y, left=left, right=right, character=HEADSET)
    canvas.row(y=9, left=left, right=right, character=OUTLINE)
    canvas.row(y=13, left=left, right=right, character=OUTLINE)
    for x, y in edges:
        canvas.put(x=x, y=y, character=OUTLINE)
    for x, y in glare:
        canvas.put(x=x, y=y, character=WHITE)


def _goggles_down(canvas: Canvas) -> None:
    """The goggles facing the viewer."""
    _draw_goggle_front(
        canvas,
        strap=(7, 24),
        lenses=(10, 21),
        edges=((9, 11), (9, 12), (22, 11), (22, 12), (15, 11), (16, 11), (15, 12), (16, 12)),
        glare=((11, 11), (12, 11), (17, 11), (12, 10)),
    )


def _goggles_down_left(canvas: Canvas) -> None:
    """The goggles turned with the face: narrower, toward the leading side."""
    _draw_goggle_front(
        canvas,
        strap=(7, 23),
        lenses=(8, 18),
        edges=((7, 11), (7, 12), (19, 11), (19, 12), (13, 11), (13, 12)),
        glare=((9, 11), (10, 11), (15, 11), (10, 10)),
    )


def _goggles_left(canvas: Canvas) -> None:
    """The goggles in profile, jutting from the forehead."""
    canvas.row(y=11, left=8, right=24, character=OUTLINE)
    for y in (10, 11, 12):
        canvas.row(y=y, left=5, right=10, character=HEADSET)
    canvas.row(y=9, left=5, right=10, character=OUTLINE)
    canvas.row(y=13, left=5, right=10, character=OUTLINE)
    canvas.put(x=4, y=11, character=OUTLINE)
    canvas.put(x=6, y=11, character=WHITE)
    canvas.put(x=7, y=10, character=WHITE)


def _goggles_up(canvas: Canvas) -> None:
    """The strap round the back of the head, and its clip."""
    canvas.row(y=11, left=7, right=24, character=OUTLINE)
    canvas.row(y=11, left=14, right=17, character=HEADSET)


def _goggles_up_left(canvas: Canvas) -> None:
    """The strap and its clip, and the goggles' edge peeking past the left cheek."""
    canvas.row(y=11, left=7, right=24, character=OUTLINE)
    canvas.row(y=11, left=15, right=18, character=HEADSET)
    canvas.column(x=6, top=10, bottom=12, character=HEADSET)
    canvas.column(x=5, top=10, bottom=12, character=OUTLINE)


_GOGGLES: Final = {
    Facing.DOWN: _goggles_down,
    Facing.DOWN_LEFT: _goggles_down_left,
    Facing.LEFT: _goggles_left,
    Facing.UP: _goggles_up,
    Facing.UP_LEFT: _goggles_up_left,
}


def _draw_goggles(canvas: Canvas, *, facing: Facing) -> None:
    """The VR headset pushed up on the forehead, as a facing sees it."""
    _GOGGLES[facing](canvas)


def _draw_front_head(canvas: Canvas, *, head: HeadStyle, hair: HairLook) -> None:
    """Draw the head facing the viewer: neck, face, ears, cap or hair, goggles, eyes."""
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(16, 13.5), radii=(8.6, 7.4), ramp=SKIN_RAMP)
    canvas.ellipse(centre=(7.4, 14.5), radii=(1.4, 2.0), ramp=SKIN + SKIN + SKIN_SHADE)
    canvas.ellipse(centre=(24.6, 14.5), radii=(1.4, 2.0), ramp=SKIN + SKIN_SHADE + SKIN_SHADE)
    if head is HeadStyle.HEADPHONES:
        # A bob that frames the face, down to the jaw
        for side_x in (7, 8, 23, 24):
            canvas.column(x=side_x, top=10, bottom=18, character=HAIR)
    elif head is HeadStyle.BEANIE:
        for side_x in (8, 23):
            canvas.column(x=side_x, top=9, bottom=12, character=HAIR)
    else:
        for side_x in (8, 23):
            canvas.column(x=side_x, top=10, bottom=14, character=HAIR)
    _draw_cap(canvas, head=head, centre_x=16, facing=Facing.DOWN, sheen=hair.sheen)
    _draw_goggles(canvas, facing=Facing.DOWN)
    # Eyes: brows, whites, pupils looking at the viewer
    for eye_x in (12, 19):
        canvas.row(y=14, left=eye_x, right=eye_x + 1, character=HAIR)
        canvas.row(y=15, left=eye_x, right=eye_x + 1, character=WHITE)
        canvas.put(x=eye_x, y=16, character=WHITE)
        canvas.put(x=eye_x + 1, y=16, character=OUTLINE)
        canvas.put(x=eye_x + 1, y=17, character=OUTLINE)
    if head is HeadStyle.GLASSES:
        for ring_x in (11, 18):
            canvas.row(y=14, left=ring_x, right=ring_x + 3, character=OUTLINE)
            canvas.row(y=18, left=ring_x, right=ring_x + 3, character=OUTLINE)
            canvas.column(x=ring_x, top=15, bottom=17, character=OUTLINE)
            canvas.column(x=ring_x + 3, top=15, bottom=17, character=OUTLINE)
        canvas.row(y=15, left=15, right=17, character=OUTLINE)
    canvas.put(x=16, y=17, character=SKIN_SHADE)
    canvas.put(x=15, y=19, character=SKIN_SHADE)
    canvas.put(x=16, y=19, character=OUTLINE)
    canvas.put(x=17, y=19, character=SKIN_SHADE)


def _draw_back_head(canvas: Canvas, *, head: HeadStyle, hair: HairLook) -> None:
    """Draw the back of the head (facing up)."""
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(7.4, 14.5), radii=(1.4, 2.0), ramp=SKIN + SKIN + SKIN_SHADE)
    canvas.ellipse(centre=(24.6, 14.5), radii=(1.4, 2.0), ramp=SKIN + SKIN_SHADE + SKIN_SHADE)
    # Plain hair with a sheen and a few strands; the outline pass draws its edge
    canvas.ellipse(centre=(16, 13.5), radii=(8.6, 7.4), ramp=HAIR)
    _draw_hair_sheen(canvas, centre=(16, 13.5), radii=(8.6, 7.4), sheen=hair.sheen)
    if hair.strands:
        # Strands show only on near-black hair (hair_shows_strands)
        for strand_x, top in ((13, 14), (17, 15), (20, 13)):
            canvas.column(x=strand_x, top=top, bottom=top + 3, character=hair.sheen)
    if head is HeadStyle.HEADPHONES:
        for side_x in (7, 8, 23, 24):
            canvas.column(x=side_x, top=10, bottom=18, character=HAIR)
    _draw_cap(canvas, head=head, centre_x=16, facing=Facing.UP, sheen=hair.sheen)
    _draw_goggles(canvas, facing=Facing.UP)


def _draw_three_quarter_front_head(canvas: Canvas, *, head: HeadStyle, hair: HairLook) -> None:
    """Draw the head turned a quarter left of the viewer (facing down-left).

    The face moves toward the leading (left) side and the near ear hides behind it; the back of
    the head shows as hair on the right, with the far ear at its edge.
    """
    canvas.row(y=19, left=12, right=17, character=SKIN_SHADE)
    canvas.ellipse(centre=(15, 13.5), radii=(8.2, 7.4), ramp=SKIN_RAMP)
    # The back of the head, and the far ear at its edge
    canvas.ellipse(centre=(21.0, 12.5), radii=(3.2, 6.0), ramp=HAIR)
    canvas.ellipse(centre=(22.6, 14.8), radii=(1.3, 1.9), ramp=SKIN + SKIN_SHADE)
    if head is HeadStyle.HEADPHONES:
        for side_x in (7, 8, 22, 23):
            canvas.column(x=side_x, top=10, bottom=18, character=HAIR)
    elif head is HeadStyle.BEANIE:
        canvas.column(x=8, top=9, bottom=12, character=HAIR)
    else:
        canvas.column(x=8, top=10, bottom=14, character=HAIR)
    _draw_cap(canvas, head=head, centre_x=15, facing=Facing.DOWN, sheen=hair.sheen)
    _draw_goggles(canvas, facing=Facing.DOWN_LEFT)
    # Eyes closer together and toward the leading side; the nose near the left cheek
    for eye_x in (10, 16):
        canvas.row(y=14, left=eye_x, right=eye_x + 1, character=HAIR)
        canvas.row(y=15, left=eye_x, right=eye_x + 1, character=WHITE)
        canvas.put(x=eye_x, y=16, character=OUTLINE)
        canvas.put(x=eye_x + 1, y=16, character=WHITE)
        canvas.put(x=eye_x, y=17, character=OUTLINE)
    if head is HeadStyle.GLASSES:
        for ring_x in (9, 15):
            canvas.row(y=14, left=ring_x, right=ring_x + 3, character=OUTLINE)
            canvas.row(y=18, left=ring_x, right=ring_x + 3, character=OUTLINE)
            canvas.column(x=ring_x, top=15, bottom=17, character=OUTLINE)
            canvas.column(x=ring_x + 3, top=15, bottom=17, character=OUTLINE)
        canvas.row(y=15, left=13, right=14, character=OUTLINE)
    canvas.put(x=13, y=17, character=SKIN_SHADE)
    canvas.put(x=12, y=19, character=SKIN_SHADE)
    canvas.put(x=13, y=19, character=OUTLINE)
    canvas.put(x=14, y=19, character=SKIN_SHADE)


def _draw_three_quarter_back_head(canvas: Canvas, *, head: HeadStyle, hair: HairLook) -> None:
    """Draw the back of the head turned a quarter left (facing up-left).

    The near ear and the edge of the cheek show on the left; the rest is hair.
    """
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(7.6, 14.5), radii=(1.4, 2.0), ramp=SKIN + SKIN + SKIN_SHADE)
    canvas.ellipse(centre=(16.4, 13.5), radii=(8.4, 7.4), ramp=HAIR)
    # The edge of the cheek and jaw, turning away
    canvas.column(x=8, top=13, bottom=17, character=SKIN)
    canvas.column(x=9, top=15, bottom=17, character=SKIN_SHADE)
    _draw_hair_sheen(canvas, centre=(16.4, 13.5), radii=(8.4, 7.4), sheen=hair.sheen)
    if hair.strands:
        for strand_x, top in ((14, 14), (18, 15), (21, 13)):
            canvas.column(x=strand_x, top=top, bottom=top + 3, character=hair.sheen)
    if head is HeadStyle.HEADPHONES:
        for side_x in (8, 23, 24):
            canvas.column(x=side_x, top=10, bottom=18, character=HAIR)
    _draw_cap(canvas, head=head, centre_x=16, facing=Facing.UP, sheen=hair.sheen)
    _draw_goggles(canvas, facing=Facing.UP_LEFT)


def _draw_side_head(canvas: Canvas, *, head: HeadStyle, hair: HairLook) -> None:
    """Draw the head in profile, facing left."""
    canvas.row(y=19, left=13, right=18, character=SKIN_SHADE)
    canvas.ellipse(centre=(15, 13.5), radii=(8.0, 7.4), ramp=SKIN_RAMP)
    # The back of the head is hair; the ear sits at its edge
    canvas.ellipse(centre=(19.5, 13.0), radii=(4.6, 6.6), ramp=HAIR)
    _draw_hair_sheen(canvas, centre=(19.5, 13.0), radii=(4.6, 6.6), sheen=hair.sheen)
    canvas.ellipse(centre=(17.6, 15.0), radii=(1.3, 1.8), ramp=SKIN + SKIN_SHADE)
    if head is HeadStyle.HEADPHONES:
        canvas.column(x=22, top=12, bottom=18, character=HAIR)
        canvas.column(x=21, top=14, bottom=18, character=HAIR)
    canvas.put(x=6, y=16, character=SKIN)
    canvas.put(x=6, y=17, character=SKIN_SHADE)
    _draw_cap(canvas, head=head, centre_x=15, facing=Facing.LEFT, sheen=hair.sheen)
    _draw_goggles(canvas, facing=Facing.LEFT)
    canvas.row(y=14, left=9, right=10, character=HAIR)
    canvas.row(y=15, left=9, right=10, character=WHITE)
    canvas.put(x=9, y=16, character=OUTLINE)
    canvas.put(x=10, y=16, character=WHITE)
    if head is HeadStyle.GLASSES:
        canvas.row(y=14, left=8, right=11, character=OUTLINE)
        canvas.row(y=18, left=8, right=11, character=OUTLINE)
        canvas.column(x=8, top=15, bottom=17, character=OUTLINE)
        canvas.column(x=11, top=15, bottom=17, character=OUTLINE)
        canvas.row(y=15, left=12, right=16, character=OUTLINE)
    canvas.put(x=8, y=19, character=OUTLINE)
    canvas.put(x=9, y=19, character=SKIN_SHADE)


def _draw_headphones(canvas: Canvas, *, facing: Facing) -> None:
    """Headphones round the neck, inside the torso's outline (the silhouette is unchanged)."""
    if facing is Facing.LEFT:
        canvas.row(y=20, left=13, right=18, character=HEADSET)
        canvas.ellipse(centre=(14.5, 21.5), radii=(1.6, 1.6), ramp=HEADSET + OUTLINE)
        return
    canvas.row(y=20, left=11, right=20, character=HEADSET)
    for cup_x in (11.5, 20.5):
        canvas.ellipse(centre=(cup_x, 21.6), radii=(1.6, 1.6), ramp=HEADSET + OUTLINE)


def outline_figure(canvas: Canvas) -> None:
    """Outline the figure: every transparent cell beside a drawn one becomes the outline."""
    drawn = [[cell != TRANSPARENT for cell in cells] for cells in canvas.cells]
    for y in range(canvas.height):
        for x in range(canvas.width):
            if drawn[y][x]:
                continue
            neighbours = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            if any(
                0 <= near_x < canvas.width and 0 <= near_y < canvas.height and drawn[near_y][near_x]
                for near_x, near_y in neighbours
            ):
                canvas.cells[y][x] = OUTLINE


def _draw_lying(canvas: Canvas, *, stars: bool) -> None:
    """Draw a kid flat on the ground, face up (knocked out): the same shape for every kid."""
    for leg_y in (35.5, 40.5):
        canvas.capsule(start=(24, leg_y), end=(29, leg_y), radius=LEG_RADIUS, ramp=PANTS_RAMP)
    canvas.box(left=29, top=33, right=31, bottom=37, ramp=SHOES + SHOES + WHITE)
    canvas.box(left=29, top=38, right=31, bottom=42, ramp=SHOES + SHOES + WHITE)
    canvas.box(left=12, top=32, right=24, bottom=43, ramp=CLOTHES_RAMP)
    canvas.capsule(start=(13, 33), end=(19, 30.5), radius=ARM_RADIUS, ramp=CLOTHES_RAMP)
    canvas.capsule(start=(13, 42), end=(19, 44.5), radius=ARM_RADIUS, ramp=CLOTHES_RAMP)
    canvas.ellipse(centre=(7, 37.5), radii=(6.2, 6.6), ramp=SKIN_RAMP)
    canvas.ellipse(centre=(3.0, 37.5), radii=(3.0, 6.0), ramp=HAIR + HAIR + OUTLINE)
    canvas.column(x=5, top=32, bottom=43, character=OUTLINE)
    canvas.column(x=4, top=33, bottom=42, character=HEADSET)
    for eye_y in (35, 40):
        # Dazed eyes: little crosses
        canvas.put(x=8, y=eye_y, character=OUTLINE)
        canvas.put(x=9, y=eye_y + 1, character=OUTLINE)
        canvas.put(x=8, y=eye_y + 1, character=SKIN_SHADE)
        canvas.put(x=9, y=eye_y, character=OUTLINE)
    outline_figure(canvas)
    if stars:
        for star_x, star_y in ((5, 26), (11, 23), (17, 26)):
            canvas.put(x=star_x, y=star_y, character=WHITE)
            canvas.put(x=star_x - 1, y=star_y, character=HEADSET)
            canvas.put(x=star_x + 1, y=star_y, character=HEADSET)
            canvas.put(x=star_x, y=star_y - 1, character=HEADSET)
            canvas.put(x=star_x, y=star_y + 1, character=HEADSET)


def draw_kid(*, pose: Pose, look: KidLook) -> Grid:
    """Return one frame of a kid: the pose drawn in the kid's look, outlined.

    Returns:
        48 rows of 32 palette characters.

    """
    canvas = Canvas()
    if pose.special in {Special.LYING, Special.LYING_STARS}:
        _draw_lying(canvas, stars=pose.special is Special.LYING_STARS)
        return canvas.grid()
    _draw_legs(canvas, pose=pose, look=look)
    turn = _DIAGONAL_TURN if pose.facing in _DIAGONALS else 0
    base = _BASE_FACING[pose.facing]
    canvas.shift_x, canvas.shift_y = pose.lean + turn, pose.bob
    arms_behind = base is Facing.UP and pose.arms in _FORWARD_ARMS
    if arms_behind:
        _draw_arms(canvas, pose=pose)
    _draw_torso(canvas, facing=base, clothes=look.clothes)
    if pose.facing is Facing.DOWN_LEFT:
        # Turned away on the right: that side of the torso falls into shadow
        canvas.column(x=22, top=21, bottom=32, character=CLOTHES_DARK)
    head_drawers = {
        Facing.DOWN: _draw_front_head,
        Facing.UP: _draw_back_head,
        Facing.LEFT: _draw_side_head,
        Facing.DOWN_LEFT: _draw_three_quarter_front_head,
        Facing.UP_LEFT: _draw_three_quarter_back_head,
    }
    head_drawers[pose.facing](canvas, head=look.head, hair=hair_look(look=look))
    if look.head is HeadStyle.HEADPHONES:
        _draw_headphones(canvas, facing=base)
    if not arms_behind:
        _draw_arms(canvas, pose=pose)
    canvas.shift_x = canvas.shift_y = 0
    outline_figure(canvas)
    if pose.sparkle:
        for spark_x, spark_y in ((29, 5), (30, 9), (26, 3)):
            canvas.put(x=spark_x, y=spark_y, character=WHITE)
            canvas.put(x=spark_x - 1, y=spark_y, character=HEADSET)
            canvas.put(x=spark_x, y=spark_y + 1, character=HEADSET)
    if pose.special is Special.LOADING and pose.loaded_rows is not None:
        _load_in(canvas, loaded_rows=pose.loaded_rows)
    return canvas.grid()


def _load_in(canvas: Canvas, *, loaded_rows: int) -> None:
    """Hide the rows not loaded yet, and light the loading line where the figure is."""
    for y in range(loaded_rows, HEIGHT):
        for x in range(WIDTH):
            if y == loaded_rows and canvas.at(x=x, y=y) != TRANSPARENT:
                canvas.cells[y][x] = WHITE
            elif y > loaded_rows:
                canvas.cells[y][x] = TRANSPARENT


def kid_frames(*, look: KidLook) -> dict[str, tuple[Grid, ...]]:
    """Return every kid animation's frames for one kid, in BOM order.

    Returns:
        Namespace -> frames.

    """
    return {
        name: tuple(draw_kid(pose=pose, look=look) for pose in frame_poses)
        for name, frame_poses in poses.kid_namespaces().items()
    }
