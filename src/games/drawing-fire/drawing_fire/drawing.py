"""Drawing Fire's pencil look: the battle drawn as a child's war drawing, in pencil on paper.

Everything here draws onto a surface it is given, from the battle model. Nothing here draws from
a random stream: a hand-drawn line wanders by ``wobble``, a deterministic hash of where it is, so
the same picture is drawn every time.
"""

from __future__ import annotations

import functools
import math
from typing import TYPE_CHECKING, cast

import pygame

from drawing_fire.battle import (
    ARMY_NAMES,
    MUZZLE_DISTANCE,
    Side,
)
from drawing_fire.swatches import (
    RecoloredFrames,
    Scheme,
    SwatchError,
    load_frames,
    load_swatch_sets,
)
from glitchygames.fonts import FontManager
from glitchygames.fonts.font_manager import DEFAULT_FONT_NAME

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from drawing_fire.battle import Battle, Bullet, Sandbag, Soldier
    from drawing_fire.terrain import Terrain

type Color = tuple[int, int, int]

ARMY_COLORS: dict[Side, Color] = {Side.PLATOON: (242, 194, 48), Side.BRIGADE: (125, 127, 133)}
# Each army's livery for the soldier sprite: its colour on the helmet, a darker one on the uniform
ARMY_LIVERIES = {
    Side.PLATOON: Scheme(primary=(242, 194, 48), secondary=(214, 168, 40)),
    Side.BRIGADE: Scheme(primary=(125, 127, 133), secondary=(98, 100, 106)),
}
PENCIL_COLOR: Color = (44, 44, 44)
# Light hatching under the ground, and the grey wash of a sandbag
HATCH_COLOR: Color = (196, 192, 182)
SANDBAG_WASH_COLOR: Color = (226, 224, 216)

# A hand-drawn line strays at most this far from where it should be, each way (px)
WOBBLE_PIXELS = 1.5
# The wobble's inputs are rounded to this many steps per pixel, so a point always wobbles the same
WOBBLE_STEPS_PER_PIXEL = 4
# Salts keep the wobble of different things from lining up
SALT_GROUND = 1
SALT_HATCH = 2
SALT_SANDBAG = 3
SALT_SOLDIER = 4
SALT_LETTER = 5
SALT_CHIP = 6
SALT_SMUDGE = 7
# The parts of a soldier's arm that wobble each their own way
WOBBLE_PART_HAND = 0
WOBBLE_PART_MUZZLE = 1

GROUND_LINE_WIDTH = 2
# The ground is sampled this often along x (px) so it can wobble between samples
GROUND_SAMPLE_PIXELS = 8
HATCH_SPACING_PIXELS = 10
HATCH_LENGTH_PIXELS = 12
HATCH_SLANT_PIXELS = 7

# The sprite (16x22) is drawn this many times larger: 44 px tall, with its chest 20 px above the
# feet, which is where the battle puts a soldier's chest
SPRITE_SCALE = 2
# The soldier sprite's swatch set that is recoloured into each army's livery
LIVERY_SWATCH_SET = 'livery'
# A soldier facing left uses the animation named with this added (the frames, mirrored)
FACING_LEFT_SUFFIX = '_left'
# The sprite's top rows are empty, above the helmet
SPRITE_EMPTY_ROWS_ABOVE_HELMET = 4
# How long a walk frame shows (s), as the sprite file says
WALK_FRAME_SECONDS = 0.15
ARM_WIDTH = 2
# The arm runs from the chest to here (px), then the pistol to the muzzle
ARM_LENGTH_PIXELS = 7.0
PISTOL_WIDTH = 4
PENNANT_POLE_HEIGHT = 28
PENNANT_FONT_SIZE = 12
PENNANT_PADDING_PIXELS = 3
PENNANT_POLE_WIDTH = 2
PENNANT_NOTCH_PIXELS = 4

# A sandbag's top sags at its ends by up to this fraction of its height when it has no sand
SANDBAG_SAG_FRACTION = 0.45
SANDBAG_TOP_POINTS = 9
SANDBAG_SEAM_COUNT = 2
SANDBAG_LINE_WIDTH = 2
# A flattened bag's heap: (across the bag from -1 to 1, rise in px)
SMUDGE_HEAP_PROFILE = ((-0.6, 2.0), (-0.1, 3.0), (0.4, 2.5))
TRICKLE_DOT_RADIUS = 1
# Where the trickle's dots are, as fractions of the bag's height, just outside its right edge
TRICKLE_HEIGHT_FRACTIONS = (0.7, 0.4, 0.1)
TRICKLE_OFFSET_PIXELS = 6

# A bullet is a dash this long (px), trailing behind it
BULLET_DASH_PIXELS = 9.0
BULLET_WIDTH = 2
# A bullet slower than this (px/s) has no direction to trail behind
MINIMUM_BULLET_SPEED = 1e-6

HUD_MARGIN_PIXELS = 16
HUD_NAME_FONT_SIZE = 22
HUD_COUNT_FONT_SIZE = 16
HUD_CHIP_SIZE_PIXELS = 14
HUD_LINE_GAP_PIXELS = 2
BANNER_FONT_SIZE = 56
# The banner is lettered this far down the screen (a fraction of its height)
BANNER_HEIGHT_FRACTION = 1 / 4
# Letters wander more than lines do
BANNER_WOBBLE_SCALE = 2.0
BANNER_UNDERLINE_WIDTH = 3
# A banner's further lines are lettered under its first, this far apart (px)
BANNER_LINE_GAP_PIXELS = 4

# A 32-bit hash: the primes mix x, y and the salt (Teschner et al., "Optimized Spatial Hashing
# for Collision Detection of Deformable Objects", 2003) and the finalizer spreads the bits
# (MurmurHash3's fmix32, by Austin Appleby, public domain)
HASH_PRIME_X = 73856093
HASH_PRIME_Y = 19349663
HASH_PRIME_SALT = 83492791
HASH_MASK = 0xFFFFFFFF
HASH_MIX_SHIFT_FIRST = 16
HASH_MIX_SHIFT_SECOND = 13
HASH_MIX_MULTIPLIER_FIRST = 0x85EBCA6B
HASH_MIX_MULTIPLIER_SECOND = 0xC2B2AE35
HASH_HALF_BITS = 16
HASH_HALF_MASK = 0xFFFF
HASH_HALF_MIDDLE = HASH_HALF_MASK / 2


def wobble(*, x: float, y: float, salt: int) -> tuple[float, float]:
    """Find how far a hand-drawn point strays from where it should be.

    It is a hash of its inputs, not a random draw, so the same point always strays the same way.

    Args:
        x: Where the point is.
        y: Where the point is.
        salt: A number that tells one kind of line from another.

    Returns:
        The (x, y) offset, each between -WOBBLE_PIXELS and WOBBLE_PIXELS.

    """
    mixed = (
        (round(x * WOBBLE_STEPS_PER_PIXEL) * HASH_PRIME_X)
        ^ (round(y * WOBBLE_STEPS_PER_PIXEL) * HASH_PRIME_Y)
        ^ (salt * HASH_PRIME_SALT)
    ) & HASH_MASK
    mixed ^= mixed >> HASH_MIX_SHIFT_FIRST
    mixed = (mixed * HASH_MIX_MULTIPLIER_FIRST) & HASH_MASK
    mixed ^= mixed >> HASH_MIX_SHIFT_SECOND
    mixed = (mixed * HASH_MIX_MULTIPLIER_SECOND) & HASH_MASK
    mixed ^= mixed >> HASH_MIX_SHIFT_FIRST
    low = mixed & HASH_HALF_MASK
    high = mixed >> HASH_HALF_BITS
    return (
        (low / HASH_HALF_MIDDLE - 1.0) * WOBBLE_PIXELS,
        (high / HASH_HALF_MIDDLE - 1.0) * WOBBLE_PIXELS,
    )


def _wobbled(*, x: float, y: float, salt: int) -> tuple[float, float]:
    """Move a point by its wobble.

    Returns:
        The point, strayed.

    """
    offset_x, offset_y = wobble(x=x, y=y, salt=salt)
    return (x + offset_x, y + offset_y)


def _font(*, size: int) -> pygame.font.Font:
    """Get the bundled font at a size: FontManager builds each size once and keeps it.

    Returns:
        The font.

    """
    return cast(
        'pygame.font.Font',
        FontManager.pygame_font(font_config={'font_name': DEFAULT_FONT_NAME, 'font_size': size}),
    )


def draw_terrain(surface: pygame.Surface, terrain: Terrain) -> None:
    """Pencil the ground: a wavering line along it, with light hatching below.

    Args:
        surface: Where to draw.
        terrain: The ground.

    """
    last_x = len(terrain.ground) - 1
    sample_xs = [*range(0, last_x, GROUND_SAMPLE_PIXELS), last_x]
    pygame.draw.lines(
        surface=surface,
        color=PENCIL_COLOR,
        closed=False,
        points=[_wobbled(x=x, y=terrain.ground[x], salt=SALT_GROUND) for x in sample_xs],
        width=GROUND_LINE_WIDTH,
    )
    for x in range(0, last_x + 1, HATCH_SPACING_PIXELS):
        start = _wobbled(x=x, y=terrain.ground[x] + GROUND_LINE_WIDTH + 2, salt=SALT_HATCH)
        end = _wobbled(
            x=x - HATCH_SLANT_PIXELS,
            y=terrain.ground[x] + GROUND_LINE_WIDTH + 2 + HATCH_LENGTH_PIXELS,
            salt=SALT_HATCH,
        )
        pygame.draw.line(surface=surface, color=HATCH_COLOR, start_pos=start, end_pos=end, width=1)


def draw_sandbag(surface: pygame.Surface, sandbag: Sandbag, terrain: Terrain) -> None:
    """Draw a sandbag wall: it sags as it loses sand, and trickles sand once hit, until flat.

    Args:
        surface: Where to draw.
        sandbag: The sandbag.
        terrain: The ground it stands on.

    """
    half_width = sandbag.width / 2
    if sandbag.flattened:
        # All that is left is a low heap of sand on the ground
        heap = [
            (sandbag.x - half_width, terrain.ground_y(sandbag.x - half_width)),
            *(
                _wobbled(
                    x=sandbag.x + across * half_width,
                    y=terrain.ground_y(sandbag.x + across * half_width) - rise,
                    salt=SALT_SMUDGE,
                )
                for across, rise in SMUDGE_HEAP_PROFILE
            ),
            (sandbag.x + half_width, terrain.ground_y(sandbag.x + half_width)),
        ]
        pygame.draw.polygon(surface=surface, color=SANDBAG_WASH_COLOR, points=heap)
        pygame.draw.lines(
            surface=surface,
            color=PENCIL_COLOR,
            closed=False,
            points=heap,
            width=SANDBAG_LINE_WIDTH,
        )
        return

    height = sandbag.height
    # The ends of the top sink as the sand goes
    end_height = height * (1.0 - SANDBAG_SAG_FRACTION * (1.0 - sandbag.sand))
    # On a slope the bag follows the ground under it, so it never floats or sinks
    left_x, right_x = sandbag.x - half_width, sandbag.x + half_width
    outline: list[tuple[float, float]] = [(left_x, terrain.ground_y(left_x))]
    for index in range(SANDBAG_TOP_POINTS):
        across = -1.0 + 2.0 * index / (SANDBAG_TOP_POINTS - 1)
        x = sandbag.x + across * half_width
        top_height = end_height + (height - end_height) * (1.0 - across * across)
        outline.append(_wobbled(x=x, y=terrain.ground_y(x) - top_height, salt=SALT_SANDBAG))
    outline.append((right_x, terrain.ground_y(right_x)))
    pygame.draw.polygon(surface=surface, color=SANDBAG_WASH_COLOR, points=outline)
    pygame.draw.polygon(
        surface=surface, color=PENCIL_COLOR, points=outline, width=SANDBAG_LINE_WIDTH
    )
    # The seams between the courses of bags, kept below the sagging top
    for seam in range(1, SANDBAG_SEAM_COUNT + 1):
        seam_height = end_height * seam / (SANDBAG_SEAM_COUNT + 1)
        pygame.draw.line(
            surface=surface,
            color=PENCIL_COLOR,
            start_pos=_wobbled(
                x=left_x, y=terrain.ground_y(left_x) - seam_height, salt=SALT_SANDBAG
            ),
            end_pos=_wobbled(
                x=right_x, y=terrain.ground_y(right_x) - seam_height, salt=SALT_SANDBAG
            ),
            width=1,
        )
    if sandbag.sand >= 1.0:
        return
    # A bag that has been hit trickles sand beside it, in dots down to the ground
    trickle_x = right_x + TRICKLE_OFFSET_PIXELS
    for fraction in TRICKLE_HEIGHT_FRACTIONS:
        pygame.draw.circle(
            surface=surface,
            color=PENCIL_COLOR,
            center=_wobbled(
                x=trickle_x, y=terrain.ground_y(trickle_x) - height * fraction, salt=SALT_SANDBAG
            ),
            radius=TRICKLE_DOT_RADIUS,
        )


def load_soldier_frames(*, path: Path) -> RecoloredFrames:
    """Load the soldier sprite, scaled up once, ready to be recoloured for each army.

    The frames are scaled before they are recoloured, by whole pixels, so a recolour (which
    replaces exact colours) still finds every pixel. Each animation also has a mirrored copy
    under its name plus ``FACING_LEFT_SUFFIX``, for a soldier facing left.

    Args:
        path: The soldier's TOML file.

    Returns:
        The frames, drawn SPRITE_SCALE times larger, in any scheme's colours on demand.

    Raises:
        SwatchError: The file has no ``LIVERY_SWATCH_SET`` swatch set (Bitmappy's save drops
            [swatches], so a sprite saved there loses it).

    """
    swatch_sets = load_swatch_sets(path=path)
    if LIVERY_SWATCH_SET not in swatch_sets:
        message = (
            f'{path}: no {LIVERY_SWATCH_SET!r} swatch set (the soldier is recoloured into each '
            "army's livery by it; a save from Bitmappy drops [swatches])"
        )
        raise SwatchError(message)
    scaled: dict[str, tuple[pygame.Surface, ...]] = {}
    for namespace, animation_frames in load_frames(path=path).items():
        scaled[namespace] = tuple(
            pygame.transform.scale(
                frame, (frame.get_width() * SPRITE_SCALE, frame.get_height() * SPRITE_SCALE)
            )
            for frame in animation_frames
        )
        # The soldier faces right as drawn; a mirrored copy, made once, faces left
        scaled[namespace + FACING_LEFT_SUFFIX] = tuple(
            pygame.transform.flip(frame, flip_x=True, flip_y=False) for frame in scaled[namespace]
        )
    return RecoloredFrames(frames=scaled, swatch_set=swatch_sets[LIVERY_SWATCH_SET])


def draw_soldier(  # ruff: ignore[too-many-arguments] - the walk and the clock go with the soldier
    surface: pygame.Surface,
    soldier: Soldier,
    *,
    frames: RecoloredFrames,
    marked: str | None,
    walking: bool = False,
    seconds: float = 0.0,
) -> None:
    """Draw a soldier in his army's livery, with his arm and pistol pencilled along his aim.

    Args:
        surface: Where to draw.
        soldier: The soldier.
        frames: The soldier sprite's frames, in any livery.
        marked: A player's name, drawn as a pennant over him (None for a computer's soldier).
        walking: Whether he is walking (his walk frames show, one after another).
        seconds: The battle's clock, for the walk frames.

    """
    sprite_frames = frames.frames_for(ARMY_LIVERIES[soldier.side])
    # He faces the way he aims (the Brigade, aiming left, faces left)
    suffix = FACING_LEFT_SUFFIX if math.cos(soldier.aim_angle) < 0.0 else ''
    if not soldier.alive:
        frame = sprite_frames['down' + suffix][0]
    elif walking:
        walk_frames = sprite_frames['walk' + suffix]
        frame = walk_frames[int(seconds / WALK_FRAME_SECONDS) % len(walk_frames)]
    else:
        frame = sprite_frames['stand' + suffix][0]
    surface.blit(frame, frame.get_rect(midbottom=(round(soldier.x), round(soldier.y))))
    if not soldier.alive:
        return

    chest_x, chest_y = soldier.chest
    direction_x = math.cos(soldier.aim_angle)
    # Screen y grows downward, so aiming up lifts the arm
    direction_y = -math.sin(soldier.aim_angle)
    # The wobble of his arm is keyed on him and the part, never on where it is: the arm would
    # shake as he walks or turns (the aim is held steady between shots on purpose)
    hand_wobble = wobble(x=soldier.soldier_id, y=WOBBLE_PART_HAND, salt=SALT_SOLDIER)
    muzzle_wobble = wobble(x=soldier.soldier_id, y=WOBBLE_PART_MUZZLE, salt=SALT_SOLDIER)
    hand = (
        chest_x + direction_x * ARM_LENGTH_PIXELS + hand_wobble[0],
        chest_y + direction_y * ARM_LENGTH_PIXELS + hand_wobble[1],
    )
    muzzle = (
        chest_x + direction_x * MUZZLE_DISTANCE + muzzle_wobble[0],
        chest_y + direction_y * MUZZLE_DISTANCE + muzzle_wobble[1],
    )
    pygame.draw.line(
        surface=surface,
        color=PENCIL_COLOR,
        start_pos=(chest_x, chest_y),
        end_pos=hand,
        width=ARM_WIDTH,
    )
    pygame.draw.line(
        surface=surface, color=PENCIL_COLOR, start_pos=hand, end_pos=muzzle, width=PISTOL_WIDTH
    )
    if marked is not None:
        _draw_pennant(surface, soldier=soldier, name=marked, frame_height=frame.get_height())


def _draw_pennant(
    surface: pygame.Surface, *, soldier: Soldier, name: str, frame_height: int
) -> None:
    """Fly a player's name over a soldier on a pole, on a pennant in his army's colour.

    Args:
        surface: Where to draw.
        soldier: The marked soldier.
        name: The player's name.
        frame_height: How tall the soldier is drawn (px).

    """
    # The pole stands on his helmet, below the sprite's empty top rows
    pole_bottom = (
        round(soldier.x),
        round(soldier.y) - frame_height + SPRITE_EMPTY_ROWS_ABOVE_HELMET * SPRITE_SCALE,
    )
    pole_top = (pole_bottom[0], pole_bottom[1] - PENNANT_POLE_HEIGHT)
    label = text_surface(name, size=PENNANT_FONT_SIZE)
    flag = pygame.Rect(
        pole_top[0] + PENNANT_POLE_WIDTH,
        pole_top[1],
        label.get_width() + 2 * PENNANT_PADDING_PIXELS + PENNANT_NOTCH_PIXELS,
        label.get_height() + PENNANT_PADDING_PIXELS,
    )
    # A swallow-tailed flag, notched at the end
    outline = [
        flag.topleft,
        flag.topright,
        (flag.right - PENNANT_NOTCH_PIXELS, flag.centery),
        flag.bottomright,
        flag.bottomleft,
    ]
    pygame.draw.polygon(surface=surface, color=ARMY_COLORS[soldier.side], points=outline)
    pygame.draw.polygon(surface=surface, color=PENCIL_COLOR, points=outline, width=1)
    pygame.draw.line(
        surface=surface,
        color=PENCIL_COLOR,
        start_pos=pole_bottom,
        end_pos=pole_top,
        width=PENNANT_POLE_WIDTH,
    )
    surface.blit(
        label, (flag.left + PENNANT_PADDING_PIXELS, flag.top + PENNANT_PADDING_PIXELS // 2)
    )


def draw_bullet(surface: pygame.Surface, bullet: Bullet) -> None:
    """Draw a bullet as a short pencil dash trailing behind it.

    Args:
        surface: Where to draw.
        bullet: The bullet.

    """
    speed = math.hypot(bullet.velocity_x, bullet.velocity_y)
    if speed < MINIMUM_BULLET_SPEED:
        pygame.draw.circle(
            surface=surface, color=PENCIL_COLOR, center=(bullet.x, bullet.y), radius=BULLET_WIDTH
        )
        return
    tail = (
        bullet.x - bullet.velocity_x / speed * BULLET_DASH_PIXELS,
        bullet.y - bullet.velocity_y / speed * BULLET_DASH_PIXELS,
    )
    pygame.draw.line(
        surface=surface,
        color=PENCIL_COLOR,
        start_pos=tail,
        end_pos=(bullet.x, bullet.y),
        width=BULLET_WIDTH,
    )


@functools.cache
def text_surface(text: str, *, size: int) -> pygame.Surface:
    """Render a line of pencilled text once: the same text at the same size is the same surface.

    Args:
        text: The text.
        size: The font size.

    Returns:
        The rendered text (kept, so no frame renders text again).

    """
    return _font(size=size).render(text, antialias=True, color=PENCIL_COLOR)


def draw_hud(surface: pygame.Surface, battle: Battle) -> None:
    """Write each army's name and living count in its own top corner.

    Args:
        surface: Where to draw.
        battle: The battle.

    """
    for side in Side:
        on_left = side is Side.PLATOON
        name = text_surface(ARMY_NAMES[side], size=HUD_NAME_FONT_SIZE)
        count = text_surface(f'soldiers {len(battle.living(side))}', size=HUD_COUNT_FONT_SIZE)
        chip = pygame.Rect(0, 0, HUD_CHIP_SIZE_PIXELS, HUD_CHIP_SIZE_PIXELS)
        top = HUD_MARGIN_PIXELS
        if on_left:
            chip.topleft = (HUD_MARGIN_PIXELS, top + (name.get_height() - chip.height) // 2)
            name_left = chip.right + HUD_LINE_GAP_PIXELS * 3
        else:
            chip.topright = (
                surface.get_width() - HUD_MARGIN_PIXELS,
                top + (name.get_height() - chip.height) // 2,
            )
            name_left = chip.left - HUD_LINE_GAP_PIXELS * 3 - name.get_width()
        pygame.draw.rect(surface=surface, color=ARMY_COLORS[side], rect=chip)
        pygame.draw.rect(surface=surface, color=PENCIL_COLOR, rect=chip, width=1)
        surface.blit(name, (name_left, top))
        surface.blit(count, (name_left, top + name.get_height() + HUD_LINE_GAP_PIXELS))


@functools.cache
def _banner_surface(text: str) -> pygame.Surface:
    """Letter a message by hand onto a see-through surface, each letter a little off, underlined.

    Args:
        text: The message.

    Returns:
        The lettered message (kept, so no frame letters it again).

    """
    font = _font(size=BANNER_FONT_SIZE)
    advances = [font.size(letter)[0] for letter in text]
    padding = math.ceil(WOBBLE_PIXELS * BANNER_WOBBLE_SCALE) + BANNER_UNDERLINE_WIDTH
    width = sum(advances) + 2 * padding
    banner = pygame.Surface((width, font.get_height() + 2 * padding), pygame.SRCALPHA)
    left = float(padding)
    for index, (letter, advance) in enumerate(zip(text, advances, strict=True)):
        offset_x, offset_y = wobble(x=index, y=len(text), salt=SALT_LETTER)
        glyph = font.render(letter, antialias=True, color=PENCIL_COLOR)
        banner.blit(
            glyph,
            (
                round(left + offset_x * BANNER_WOBBLE_SCALE),
                round(padding + offset_y * BANNER_WOBBLE_SCALE),
            ),
        )
        left += advance
    underline_y = padding + font.get_height()
    pygame.draw.line(
        surface=banner,
        color=PENCIL_COLOR,
        start_pos=_wobbled(x=padding, y=underline_y, salt=SALT_CHIP),
        end_pos=_wobbled(x=width - padding, y=underline_y, salt=SALT_CHIP),
        width=BANNER_UNDERLINE_WIDTH,
    )
    return banner


def draw_banner(surface: pygame.Surface, lines: Sequence[str]) -> None:
    """Show a hand-lettered message across the middle of the sky, a line at a time.

    The first line is centred BANNER_HEIGHT_FRACTION down the screen (where a one-line banner
    always is); each further line is centred under the one before it. Every line is lettered
    and kept on its own (``_banner_surface``, cached by its text).

    Args:
        surface: Where to draw.
        lines: The message's lines: the winner's one line, or a draw's two.

    """
    centre_x = surface.get_width() // 2
    previous: pygame.Rect | None = None
    for text in lines:
        banner = _banner_surface(text)
        if previous is None:
            rect = banner.get_rect(
                center=(centre_x, round(surface.get_height() * BANNER_HEIGHT_FRACTION))
            )
        else:
            rect = banner.get_rect(midtop=(centre_x, previous.bottom + BANNER_LINE_GAP_PIXELS))
        surface.blit(banner, rect)
        previous = rect
