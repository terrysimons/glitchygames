"""Tests for Drawing Fire's pencil look: pixel checks on real surfaces (the dummy driver)."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path

import pygame
import pytest

from glitchygames.examples.drawing_fire import drawing as drawing_module
from glitchygames.examples.drawing_fire.battle import (
    ARMY_NAMES,
    MUZZLE_DISTANCE,
    SANDBAG_HEIGHT,
    SANDBAG_WIDTH,
    SOLDIER_CHEST_HEIGHT,
    SOLDIER_HEIGHT,
    Battle,
    Bullet,
    Sandbag,
    Side,
)
from glitchygames.examples.drawing_fire.drawing import (
    ARMY_COLORS,
    ARMY_LIVERIES,
    BANNER_HEIGHT_FRACTION,
    FACING_LEFT_SUFFIX,
    LIVERY_SWATCH_SET,
    PENCIL_COLOR,
    SPRITE_SCALE,
    WOBBLE_PIXELS,
    _banner_surface,
    draw_banner,
    draw_bullet,
    draw_hud,
    draw_sandbag,
    draw_soldier,
    draw_terrain,
    load_soldier_frames,
    text_surface,
    wobble,
)
from glitchygames.examples.drawing_fire.swatches import SwatchError, load_swatch_sets
from glitchygames.examples.drawing_fire.terrain import Terrain
from glitchygames.fonts import FontManager

SOLDIER_PATH = (
    Path(__file__).parents[3]
    / 'glitchygames'
    / 'examples'
    / 'drawing_fire'
    / 'sprites'
    / 'soldier.toml'
)
PAPER = (251, 248, 239)
SCREEN_SIZE = (800, 480)
GROUND_Y = 400.0
SOLDIER_X = 200
# The helmet's middle in the sprite (16 wide, 22 tall): column 8, row 5
HELMET_COLUMN = 8
HELMET_ROW = 5
SPRITE_ROWS = 22
# How far from its exact spot a hand-drawn line may stray (px), with a pixel of line width
WOBBLE_TOLERANCE = math.ceil(WOBBLE_PIXELS) + 1


@pytest.fixture(autouse=True)
def pygame_ready():
    """Real pygame, initialized (the dummy driver)."""
    if not pygame.get_init():
        pygame.init()


@pytest.fixture
def paper():
    """A sheet of paper to draw on."""
    surface = pygame.Surface(SCREEN_SIZE)
    surface.fill(PAPER)
    return surface


@pytest.fixture
def terrain():
    """Flat ground."""
    return Terrain(width=SCREEN_SIZE[0], height=SCREEN_SIZE[1], ground=(GROUND_Y,) * SCREEN_SIZE[0])


@pytest.fixture
def battle(terrain):
    """A one-a-side battle on flat ground."""
    return Battle(terrain=terrain, soldiers_per_side=1, sandbag_xs=())


def without_swatches(text: str) -> str:
    """Drop a sprite file's [swatches] tables, as a save from Bitmappy does.

    Returns:
        The file's text without them.

    """
    kept_lines: list[str] = []
    in_swatches = False
    for line in text.splitlines():
        if line.startswith('['):
            in_swatches = line.startswith('[swatches')
        if not in_swatches:
            kept_lines.append(line)
    return '\n'.join(kept_lines) + '\n'


def test_a_soldier_sprite_without_its_livery_swatches_names_the_file_and_the_set(tmp_path):
    """A sprite with no livery swatch set fails with a SwatchError, not a bare KeyError."""
    path = tmp_path / 'soldier.toml'
    path.write_text(without_swatches(SOLDIER_PATH.read_text(encoding='utf-8')), encoding='utf-8')
    assert load_swatch_sets(path=path) == {}

    with pytest.raises(SwatchError) as raised:
        load_soldier_frames(path=path)

    assert str(path) in str(raised.value)
    assert repr(LIVERY_SWATCH_SET) in str(raised.value)


@pytest.fixture(scope='module')
def frames():
    """The soldier's frames, scaled once and recoloured on demand."""
    pygame.init()
    return load_soldier_frames(path=SOLDIER_PATH)


def place(battle, *, soldier_index=0, x=SOLDIER_X):
    """Stand a soldier at x on the ground.

    Returns:
        The soldier.

    """
    soldier = battle.soldiers[soldier_index]
    soldier.x = x
    soldier.y = GROUND_Y
    return soldier


def pixels_in(surface, rect):
    """Find the colours in a rectangle of the surface.

    Returns:
        The set of RGB colours.

    """
    return {
        tuple(surface.get_at((x, y)))[:3]
        for x in range(max(rect.left, 0), min(rect.right, surface.get_width()))
        for y in range(max(rect.top, 0), min(rect.bottom, surface.get_height()))
    }


def ink_rows(surface, rect):
    """Find the rows inside a rectangle that hold anything but paper.

    Returns:
        The rows' y values, ascending.

    """
    return [
        y
        for y in range(rect.top, rect.bottom)
        if any(surface.get_at((x, y))[:3] != PAPER for x in range(rect.left, rect.right))
    ]


def topmost_ink(surface):
    """Find the highest row (smallest y) that holds anything but paper.

    Returns:
        The row's y.

    """
    return ink_rows(surface, surface.get_rect())[0]


def test_the_armies_wear_pencil_yellow_and_graphite_grey():
    """The colours are the brief's, and the liveries are those colours with a darker secondary."""
    assert ARMY_COLORS == {Side.PLATOON: (242, 194, 48), Side.BRIGADE: (125, 127, 133)}
    assert PENCIL_COLOR == (44, 44, 44)
    assert ARMY_LIVERIES[Side.PLATOON].primary == ARMY_COLORS[Side.PLATOON]
    assert ARMY_LIVERIES[Side.PLATOON].secondary == (214, 168, 40)
    assert ARMY_LIVERIES[Side.BRIGADE].primary == ARMY_COLORS[Side.BRIGADE]
    assert ARMY_LIVERIES[Side.BRIGADE].secondary == (98, 100, 106)


def test_the_sprite_file_wears_the_platoons_own_livery():
    """The raw file is in the Platoon's colours, shades at 2/3, all distinct from one another."""
    livery = load_swatch_sets(path=SOLDIER_PATH)['livery']
    parts = {part.name: part for part in livery.parts}
    helmet, uniform = parts['helmet'].colors, parts['uniform'].colors
    assert helmet[0] == ARMY_COLORS[Side.PLATOON]
    assert uniform[0] == ARMY_LIVERIES[Side.PLATOON].secondary
    for part_colors in (helmet, uniform):
        base, shade = part_colors
        assert shade == tuple(round(channel * 2 / 3) for channel in base)
    swatched = [*helmet, *uniform]
    assert len(set(swatched)) == len(swatched)
    # Replacement is by exact RGB, so no two palette colours may be the same RGB
    with SOLDIER_PATH.open('rb') as sprite_file:
        palette = tomllib.load(sprite_file)['colors'].values()
    palette_colors = [(entry['red'], entry['green'], entry['blue']) for entry in palette]
    assert len(set(palette_colors)) == len(palette_colors)
    assert set(swatched) <= set(palette_colors)


def test_wobble_is_deterministic_and_bounded():
    """The same inputs always wobble the same way, never past WOBBLE_PIXELS, and inputs matter."""
    seen = set()
    for x in range(0, 400, 13):
        for y in range(0, 300, 17):
            for salt in range(3):
                first = wobble(x=x, y=y, salt=salt)
                assert first == wobble(x=x, y=y, salt=salt)
                assert abs(first[0]) <= WOBBLE_PIXELS
                assert abs(first[1]) <= WOBBLE_PIXELS
                seen.add(first)
    # Different inputs wobble differently, both ways, and the wobble is not always zero
    assert len(seen) > 100
    assert min(dx for dx, _ in seen) < 0 < max(dx for dx, _ in seen)
    assert min(dy for _, dy in seen) < 0 < max(dy for _, dy in seen)
    assert wobble(x=1.0, y=2.0, salt=1) != wobble(x=1.0, y=2.0, salt=2)
    # Negative inputs are fine too
    assert abs(wobble(x=-5.5, y=-9.25, salt=-3)[0]) <= WOBBLE_PIXELS


def test_each_army_wears_its_own_colour(paper, battle, frames):
    """The same sprite, two liveries: a helmet pixel is pencil yellow or graphite grey."""
    helmet_offset = (
        (HELMET_COLUMN - 8) * SPRITE_SCALE,
        (HELMET_ROW - SPRITE_ROWS) * SPRITE_SCALE,
    )
    platoon = place(battle, soldier_index=0, x=SOLDIER_X)
    brigade = place(battle, soldier_index=1, x=SOLDIER_X + 300)
    draw_soldier(paper, platoon, frames=frames, marked=None)
    draw_soldier(paper, brigade, frames=frames, marked=None)
    assert (
        tuple(paper.get_at((SOLDIER_X + helmet_offset[0], round(GROUND_Y) + helmet_offset[1])))[:3]
        == ARMY_COLORS[Side.PLATOON]
    )
    assert (
        tuple(
            paper.get_at((SOLDIER_X + 300 + helmet_offset[0], round(GROUND_Y) + helmet_offset[1]))
        )[:3]
        == ARMY_COLORS[Side.BRIGADE]
    )
    platoon_box = pygame.Rect(SOLDIER_X - 20, GROUND_Y - 60, 40, 60)
    assert ARMY_COLORS[Side.BRIGADE] not in pixels_in(paper, platoon_box)


def test_the_sprite_stands_soldier_height_tall_with_its_feet_on_the_ground(paper, battle, frames):
    """Scaled up to about SOLDIER_HEIGHT, the feet on (x, y)."""
    soldier = place(battle)
    soldier.aim_angle = 0.0
    draw_soldier(paper, soldier, frames=frames, marked=None)
    column = pygame.Rect(SOLDIER_X - 16, 0, 32, int(GROUND_Y) + 10)
    rows = ink_rows(paper, column)
    assert abs(rows[-1] - GROUND_Y) <= 1
    assert abs((rows[-1] - rows[0]) - SOLDIER_HEIGHT) <= 6


def test_the_scaled_frames_are_built_once(frames):
    """The same scheme gives the same surfaces, already at the drawing size."""
    scheme = ARMY_LIVERIES[Side.PLATOON]
    first = frames.frames_for(scheme)
    assert frames.frames_for(scheme) is first
    assert first['stand'][0].get_size() == (16 * SPRITE_SCALE, 22 * SPRITE_SCALE)
    assert len(first['walk']) == 2


def test_the_arm_and_pistol_are_pencilled_along_the_aim(paper, battle, frames):
    """Pencil lines run from the chest along the aim, and follow it when it turns."""
    soldier = place(battle)
    chest_x, chest_y = soldier.chest
    for angle in (0.0, math.pi / 2, -math.pi / 4):
        paper.fill(PAPER)
        soldier.aim_angle = angle
        draw_soldier(paper, soldier, frames=frames, marked=None)
        tip_x = chest_x + MUZZLE_DISTANCE * 0.75 * math.cos(angle)
        tip_y = chest_y - MUZZLE_DISTANCE * 0.75 * math.sin(angle)
        near_tip = pygame.Rect(round(tip_x) - 2, round(tip_y) - 2, 5, 5)
        assert PENCIL_COLOR in pixels_in(paper, near_tip)
    # Aiming straight up leaves no pencil on the aim-right side, at the same distance
    paper.fill(PAPER)
    soldier.aim_angle = math.pi / 2
    draw_soldier(paper, soldier, frames=frames, marked=None)
    right_of_chest = pygame.Rect(round(chest_x) + 8, round(chest_y) - 2, 5, 5)
    assert PENCIL_COLOR not in pixels_in(paper, right_of_chest)
    assert GROUND_Y - chest_y == SOLDIER_CHEST_HEIGHT


def test_a_walking_soldier_alternates_his_walk_frames(paper, battle, frames):
    """Walking draws the walk frames (by the battle clock); standing draws the stand frame."""
    soldier = place(battle)
    surfaces = []
    for seconds, walking in ((0.0, False), (0.0, True), (0.2, True), (0.4, True)):
        paper.fill(PAPER)
        draw_soldier(paper, soldier, frames=frames, marked=None, walking=walking, seconds=seconds)
        surfaces.append(pygame.image.tobytes(paper, 'RGB'))
    stand, first_step, second_step, first_step_again = surfaces
    assert len({stand, first_step, second_step}) == 3
    assert first_step == first_step_again


def test_a_dead_soldier_lies_down_without_an_arm(paper, battle, frames):
    """The down frame is low: nothing is drawn above half a soldier, and no pencil arm."""
    soldier = place(battle)
    soldier.health = 0
    draw_soldier(paper, soldier, frames=frames, marked=None)
    column = pygame.Rect(SOLDIER_X - 24, 0, 48, int(GROUND_Y) + 10)
    assert GROUND_Y - topmost_ink(paper) <= SOLDIER_HEIGHT / 2
    assert PENCIL_COLOR not in pixels_in(paper, column)


def test_a_marked_soldier_flies_a_pennant_with_the_players_name(paper, battle, frames):
    """The pennant is drawn above his head, in his army's colour, and only when marked."""
    soldier = place(battle)
    draw_soldier(paper, soldier, frames=frames, marked=None)
    plain_top = topmost_ink(paper)
    plain = pygame.image.tobytes(paper, 'RGB')
    paper.fill(PAPER)
    draw_soldier(paper, soldier, frames=frames, marked='Terry')
    assert pygame.image.tobytes(paper, 'RGB') != plain
    assert topmost_ink(paper) < plain_top
    above_head = pygame.Rect(SOLDIER_X - 40, 0, 120, plain_top)
    assert ARMY_COLORS[Side.PLATOON] in pixels_in(paper, above_head)


def test_a_bullet_is_a_short_dash_along_its_flight(paper):
    """The dash trails behind the bullet and is pencil."""
    bullet = Bullet(
        x=300.0, y=200.0, velocity_x=600.0, velocity_y=0.0, side=Side.PLATOON, distance_left=100.0
    )
    draw_bullet(paper, bullet)
    behind = pygame.Rect(292, 198, 8, 5)
    ahead = pygame.Rect(306, 198, 20, 5)
    assert PENCIL_COLOR in pixels_in(paper, behind)
    assert pixels_in(paper, ahead) == {PAPER}


def test_a_bullet_with_no_velocity_is_a_dot(paper):
    """A stopped bullet still draws, and nothing divides by zero."""
    bullet = Bullet(
        x=300.0, y=200.0, velocity_x=0.0, velocity_y=0.0, side=Side.BRIGADE, distance_left=100.0
    )
    draw_bullet(paper, bullet)
    assert PENCIL_COLOR in pixels_in(paper, pygame.Rect(296, 196, 9, 9))


def test_the_ground_is_a_pencil_line_with_hatching_under_it(paper, terrain):
    """A pencil line runs along the ground, and light hatching fills below it."""
    draw_terrain(paper, terrain)
    for x in (100, 400, 700):
        column = pygame.Rect(x, round(GROUND_Y) - WOBBLE_TOLERANCE, 1, 2 * WOBBLE_TOLERANCE)
        assert PENCIL_COLOR in pixels_in(paper, column)
    below = pygame.Rect(0, round(GROUND_Y) + 6, SCREEN_SIZE[0], 12)
    assert len(pixels_in(paper, below)) > 1
    above = pygame.Rect(0, 0, SCREEN_SIZE[0], round(GROUND_Y) - WOBBLE_TOLERANCE)
    assert pixels_in(paper, above) == {PAPER}


def test_the_ground_follows_the_hills(paper):
    """The line goes through the terrain's own ground y."""
    ground = tuple(GROUND_Y - (60.0 if 300 <= x < 400 else 0.0) for x in range(SCREEN_SIZE[0]))
    hilly = Terrain(width=SCREEN_SIZE[0], height=SCREEN_SIZE[1], ground=ground)
    draw_terrain(paper, hilly)
    column = pygame.Rect(350, round(GROUND_Y) - 60 - WOBBLE_TOLERANCE, 1, 2 * WOBBLE_TOLERANCE)
    assert PENCIL_COLOR in pixels_in(paper, column)


def test_a_full_sandbag_is_taller_than_a_half_empty_one(paper, terrain):
    """Sand shows in the height: the topmost ink of the bag."""
    full = Sandbag(x=300.0, width=SANDBAG_WIDTH, sand=1.0)
    half = Sandbag(x=300.0, width=SANDBAG_WIDTH, sand=0.5)
    draw_sandbag(paper, full, terrain)
    full_top = topmost_ink(paper)
    paper.fill(PAPER)
    draw_sandbag(paper, half, terrain)
    half_top = topmost_ink(paper)
    assert full_top < half_top
    assert abs((GROUND_Y - full_top) - SANDBAG_HEIGHT) <= WOBBLE_TOLERANCE
    assert abs((GROUND_Y - half_top) - SANDBAG_HEIGHT / 2) <= WOBBLE_TOLERANCE + 2


def test_a_half_empty_sandbag_sags(paper, terrain):
    """With less sand the bag's top sags at its ends below its middle."""
    half = Sandbag(x=300.0, width=SANDBAG_WIDTH, sand=0.5)
    draw_sandbag(paper, half, terrain)
    middle_top = ink_rows(paper, pygame.Rect(296, 0, 8, 480))[0]
    end_top = ink_rows(paper, pygame.Rect(300 - 24, 0, 4, 480))[0]
    assert end_top > middle_top + 1


def test_a_flattened_sandbag_is_a_smudge_on_the_ground(paper, terrain):
    """No sand left: a low smear, not a bag, and no trickle."""
    flat = Sandbag(x=300.0, width=SANDBAG_WIDTH, sand=0.0)
    draw_sandbag(paper, flat, terrain)
    assert GROUND_Y - topmost_ink(paper) <= WOBBLE_TOLERANCE + 3
    beside = pygame.Rect(300 + SANDBAG_WIDTH // 2 + 4, 300, 8, 110)
    assert pixels_in(paper, beside) == {PAPER}


def test_sand_trickles_only_from_a_bag_that_has_been_hit(paper, terrain):
    """Sand dribbles down beside a hit, standing bag, and not from a full one."""
    beside = pygame.Rect(300 + SANDBAG_WIDTH // 2 + 4, 300, 8, 110)
    draw_sandbag(paper, Sandbag(x=300.0, width=SANDBAG_WIDTH, sand=1.0), terrain)
    assert pixels_in(paper, beside) == {PAPER}
    draw_sandbag(paper, Sandbag(x=300.0, width=SANDBAG_WIDTH, sand=0.5), terrain)
    assert len(pixels_in(paper, beside)) > 1


def test_the_hud_writes_each_armys_name_in_its_own_corner(paper, battle):
    """Both corners change, and the left and right are not mirror images."""
    blank = pygame.image.tobytes(paper, 'RGB')
    draw_hud(paper, battle)
    assert pygame.image.tobytes(paper, 'RGB') != blank
    left_corner = pygame.Rect(0, 0, 200, 60)
    right_corner = pygame.Rect(SCREEN_SIZE[0] - 200, 0, 200, 60)
    assert pixels_in(paper, left_corner) != {PAPER}
    assert pixels_in(paper, right_corner) != {PAPER}
    # The middle of the sky is left alone
    assert pixels_in(paper, pygame.Rect(260, 0, 280, 60)) == {PAPER}
    assert ARMY_NAMES[Side.PLATOON]
    assert ARMY_COLORS[Side.PLATOON] in pixels_in(paper, left_corner)
    assert ARMY_COLORS[Side.BRIGADE] in pixels_in(paper, right_corner)


def test_the_hud_counts_the_living(paper, battle):
    """When a soldier falls the count changes, so the corner does."""
    draw_hud(paper, battle)
    before = pygame.image.tobytes(paper, 'RGB')
    battle.soldiers[0].health = 0
    paper.fill(PAPER)
    draw_hud(paper, battle)
    assert pygame.image.tobytes(paper, 'RGB') != before


def test_the_hud_font_and_text_are_made_once(paper, battle, mocker):
    """The HUD builds its two fonts once (through pygame.font.Font) and renders each text once."""
    mocker.patch.dict(FontManager._font_cache, clear=True)
    text_surface.cache_clear()
    font_constructor = mocker.spy(pygame.font, 'Font')
    draw_hud(paper, battle)
    # The name font and the count font: this spy does see FontManager build them
    assert font_constructor.call_count == 2
    rendered = mocker.spy(drawing_module, '_font')
    for _ in range(3):
        draw_hud(paper, battle)
    assert font_constructor.call_count == 2
    assert rendered.call_count == 0
    # A new count is new text, rendered once
    battle.soldiers[0].health = 0
    draw_hud(paper, battle)
    draw_hud(paper, battle)
    assert rendered.call_count == 1


def test_the_banner_is_hand_lettered_in_the_sky(paper):
    """The message is pencilled in the middle of the sky, the same each time."""
    draw_banner(paper, ('Pencil Platoon wins!',))
    first = pygame.image.tobytes(paper, 'RGB')
    sky = pygame.Rect(SCREEN_SIZE[0] // 4, 40, SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] // 3)
    assert PENCIL_COLOR in pixels_in(paper, sky)
    paper.fill(PAPER)
    draw_banner(paper, ('Pencil Platoon wins!',))
    assert pygame.image.tobytes(paper, 'RGB') == first
    paper.fill(PAPER)
    draw_banner(paper, ('Graphite Brigade wins!',))
    assert pygame.image.tobytes(paper, 'RGB') != first


def test_a_two_line_banner_letters_its_second_line_under_the_first(paper):
    """The first line is where a one-line banner is; the second is pencilled under it."""
    draw_banner(paper, ('Nobody wins!',))
    one_line = paper.copy()
    first_line_bottom = (
        _banner_surface('Nobody wins!')
        .get_rect(center=(SCREEN_SIZE[0] // 2, round(SCREEN_SIZE[1] * BANNER_HEIGHT_FRACTION)))
        .bottom
    )
    under = pygame.Rect(0, first_line_bottom, SCREEN_SIZE[0], SCREEN_SIZE[1] // 2)
    assert PENCIL_COLOR not in pixels_in(one_line, under)
    paper.fill(PAPER)

    draw_banner(paper, ('Nobody wins!', 'Everybody loses!'))

    above = pygame.Rect(0, 0, SCREEN_SIZE[0], first_line_bottom)
    assert pygame.image.tobytes(paper.subsurface(above), 'RGB') == pygame.image.tobytes(
        one_line.subsurface(above), 'RGB'
    )
    assert PENCIL_COLOR in pixels_in(paper, under)


def test_the_banner_font_and_lettering_are_made_once(paper, mocker):
    """The banner builds its font once (through pygame.font.Font) and letters each message once."""
    mocker.patch.dict(FontManager._font_cache, clear=True)
    _banner_surface.cache_clear()
    font_constructor = mocker.spy(pygame.font, 'Font')
    draw_banner(paper, ('Pencil Platoon wins!',))
    assert font_constructor.call_count == 1
    rendered = mocker.spy(drawing_module, '_font')
    draw_banner(paper, ('Pencil Platoon wins!',))
    draw_banner(paper, ('Pencil Platoon wins!',))
    assert font_constructor.call_count == 1
    assert rendered.call_count == 0


def pencil_pixels(surface):
    """Find the arm-and-pistol pixels (the pencil colour is used for nothing else on the soldier).

    Returns:
        The set of (x, y) of every pencil pixel.

    """
    return {
        (x, y)
        for x in range(surface.get_width())
        for y in range(surface.get_height())
        if tuple(surface.get_at((x, y)))[:3] == PENCIL_COLOR
    }


@pytest.mark.parametrize('shift', [1, 3, 30])
def test_the_arm_does_not_shake_as_the_soldier_moves(paper, battle, frames, shift):
    """The arm's wobble is keyed on the soldier, not where he stands, so walking never shakes it."""
    soldier = place(battle, x=SOLDIER_X)
    soldier.aim_angle = 0.7
    draw_soldier(paper, soldier, frames=frames, marked=None)
    first = pencil_pixels(paper)
    paper.fill(PAPER)
    soldier.x = SOLDIER_X + shift
    draw_soldier(paper, soldier, frames=frames, marked=None)
    assert first
    assert {(x + shift, y) for x, y in first} == pencil_pixels(paper)


def test_each_soldiers_arm_wobbles_in_its_own_way(paper, battle, frames):
    """Two soldiers at the same spot with the same aim have arms that differ by their wobble."""
    first = place(battle, soldier_index=0)
    second = place(battle, soldier_index=1)
    first.aim_angle = second.aim_angle = 0.7
    second.side = first.side
    draw_soldier(paper, first, frames=frames, marked=None)
    first_pixels = pencil_pixels(paper)
    paper.fill(PAPER)
    draw_soldier(paper, second, frames=frames, marked=None)
    assert first_pixels != pencil_pixels(paper)


def test_a_soldier_faces_the_way_he_aims(paper, battle, frames):
    """Aiming left draws the mirrored frames: his legs are the right-facing ones, flipped."""
    soldier = place(battle)
    legs = pygame.Rect(SOLDIER_X - 16, round(GROUND_Y) - 14, 32, 14)

    def legs_drawn(angle):
        paper.fill(PAPER)
        soldier.aim_angle = angle
        draw_soldier(paper, soldier, frames=frames, marked=None, walking=True, seconds=0.2)
        return paper.subsurface(legs).copy()

    right = legs_drawn(0.0)
    left = legs_drawn(math.pi)
    assert pygame.image.tobytes(right, 'RGB') != pygame.image.tobytes(left, 'RGB')
    mirrored = pygame.transform.flip(right, flip_x=True, flip_y=False)
    assert pygame.image.tobytes(mirrored, 'RGB') == pygame.image.tobytes(left, 'RGB')
    assert FACING_LEFT_SUFFIX == '_left'


def test_the_brigade_faces_left_from_the_start(paper, battle, frames):
    """The Brigade's soldiers start aimed left, so they are drawn facing left."""
    brigade = place(battle, soldier_index=1)
    assert math.cos(brigade.aim_angle) < 0
    draw_soldier(paper, brigade, frames=frames, marked=None)
    left_facing = frames.frames_for(ARMY_LIVERIES[Side.BRIGADE])['stand' + FACING_LEFT_SUFFIX][0]
    assert left_facing.get_size() == (16 * SPRITE_SCALE, 22 * SPRITE_SCALE)
