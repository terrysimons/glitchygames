"""The cast's and props' sprite files, checked against the character and props BOMs.

The Lawn Zombie, the TV, the Channel Changer, the zap, the two neighbors of the first stage and
the saved and lost effects (character BOM section 6).

The expected names, frames, timings, loops and transitions are copied from the BOMs (character
BOM section 5.1, less ``rise``: decision 6; props BOM, the TV with its damage stages, the
Channel Changer and the zap), not read from the rigs, so a rig that drifts from its BOM fails
here.
"""

from __future__ import annotations

import hashlib
import itertools
import tomllib
from pathlib import Path

import pytest

from glitchygames.sprites import SpriteFactory
from glitchygames.testing import sprite_files
from zombies_aint_my_neighbors.art import (
    build,
    door_rig,
    neighbor_rig,
    rig,
    tv_rig,
    weapon_rig,
    zombie_rig,
)
from zombies_aint_my_neighbors.art.palettes import CLOTHES_RAMP

SPRITES_DIRECTORY = Path(build.__file__).resolve().parents[1] / 'sprites'
FACINGS = ('down', 'up', 'left')
MAGENTA = (255, 0, 255)
SHARED_OUTLINE = (24, 16, 32)
PALETTE_LIMIT = 15

# Character BOM 5.1: namespace -> (frames, interval, loop)
BOM_ZOMBIE = {
    **{f'walk_{facing}': (4, 0.18, True) for facing in FACINGS},
    **{f'grab_{facing}': (2, 0.1, False) for facing in FACINGS},
    'crumble': (5, 0.1, False),
}
BOM_ZOMBIE_TRANSITIONS = frozenset(
    (f'grab_{facing}', f'walk_{facing}', 'animation_complete') for facing in FACINGS
)
BOM_ZOMBIE_HITBOX = {'offset_x': 6, 'offset_y': 12, 'width': 20, 'height': 36}
# Props BOM, the TV and its damage stages
BOM_TV = {
    'static': (3, 0.08, True),
    'spawn': (4, 0.08, False),
    'cracked-static': (3, 0.08, True),
    'cracked-spawn': (4, 0.08, False),
    'smashed-static': (3, 0.08, True),
    'smashed-spawn': (4, 0.08, False),
    'destroyed': (3, 0.1, True),
}
BOM_TV_TRANSITIONS = frozenset({
    ('spawn', 'static', 'animation_complete'),
    ('cracked-spawn', 'cracked-static', 'animation_complete'),
    ('smashed-spawn', 'smashed-static', 'animation_complete'),
})
BOM_TV_HITBOX = {'offset_x': 4, 'offset_y': 12, 'width': 40, 'height': 32}
# The intact TV's frames as feature plan 5 drew them (sha256 of their rows): damage stages are
# added beside them, never drawn over them
INTACT_TV_FINGERPRINT = '2674e988412580cf7231e6aadc92d8f1f73999c6dbab7ec8c9d761e0db7d62e7'
# Props BOM, the Channel Changer: one frame per drawn facing, its whole canvas as its hitbox
BOM_CHANNEL_CHANGER = {f'held_{facing}': (1, 0.08, True) for facing in FACINGS}
BOM_CHANNEL_CHANGER_HITBOX = {'offset_x': 0, 'offset_y': 0, 'width': 12, 'height': 12}
# Props BOM, the zap (fizzle ends in removal: no transition)
BOM_ZAP = {'fly': (3, 0.06, True), 'fizzle': (2, 0.06, False)}
BOM_ZAP_HITBOX = {'offset_x': 2, 'offset_y': 2, 'width': 8, 'height': 8}

# Character BOM section 6: each neighbor's idle and panic, the hitbox they share, and the
# effects (placed by the game: their hitbox is the whole frame, never collided)
BOM_NEIGHBOR = {'idle': (2, 0.5, True), 'panic': (2, 0.12, True)}
BOM_NEIGHBOR_HITBOX = {'offset_x': 4, 'offset_y': 8, 'width': 24, 'height': 40}
BOM_SAVED = {'saved': (5, 0.06, False)}
BOM_LOST = {'lost': (5, 0.08, False)}
WHOLE_KID_FRAME = {'offset_x': 0, 'offset_y': 0, 'width': 32, 'height': 48}
# Props BOM, the laser pointer (its whole canvas as its hitbox: in a hand) and its dot
BOM_LASER_POINTER = {f'held_{facing}': (1, 0.08, True) for facing in FACINGS}
BOM_LASER_POINTER_HITBOX = {'offset_x': 0, 'offset_y': 0, 'width': 12, 'height': 12}
BOM_LASER_DOT = {'glow': (2, 0.06, True)}
BOM_LASER_DOT_HITBOX = {'offset_x': 0, 'offset_y': 0, 'width': 8, 'height': 8}
# Props BOM, the exit door
BOM_DOOR = {'closed': (1, 0.08, True), 'opening': (3, 0.08, False), 'open': (2, 0.2, True)}
BOM_DOOR_TRANSITIONS = frozenset({('opening', 'open', 'animation_complete')})
BOM_DOOR_HITBOX = {'offset_x': 8, 'offset_y': 16, 'width': 32, 'height': 32}

# (file, its BOM animations, transitions, hitbox, size, palette)
SPRITES = {
    'lawn_zombie': (
        BOM_ZOMBIE,
        BOM_ZOMBIE_TRANSITIONS,
        BOM_ZOMBIE_HITBOX,
        (32, 48),
        zombie_rig.ZOMBIE_PALETTE,
    ),
    'tv': (BOM_TV, BOM_TV_TRANSITIONS, BOM_TV_HITBOX, (48, 48), tv_rig.TV_PALETTE),
    'channel_changer': (
        BOM_CHANNEL_CHANGER,
        frozenset(),
        BOM_CHANNEL_CHANGER_HITBOX,
        (12, 12),
        weapon_rig.WEAPON_PALETTE,
    ),
    'zap': (BOM_ZAP, frozenset(), BOM_ZAP_HITBOX, (12, 12), weapon_rig.WEAPON_PALETTE),
    'pizza_teen': (
        BOM_NEIGHBOR,
        frozenset(),
        BOM_NEIGHBOR_HITBOX,
        (32, 48),
        neighbor_rig.PIZZA_TEEN_PALETTE,
    ),
    'lawn_chair_reader': (
        BOM_NEIGHBOR,
        frozenset(),
        BOM_NEIGHBOR_HITBOX,
        (32, 48),
        neighbor_rig.LAWN_CHAIR_READER_PALETTE,
    ),
    'saved': (BOM_SAVED, frozenset(), WHOLE_KID_FRAME, (32, 48), neighbor_rig.EFFECT_PALETTE),
    'lost': (BOM_LOST, frozenset(), WHOLE_KID_FRAME, (32, 48), neighbor_rig.EFFECT_PALETTE),
    'exit_door': (BOM_DOOR, BOM_DOOR_TRANSITIONS, BOM_DOOR_HITBOX, (48, 48), door_rig.DOOR_PALETTE),
    'laser_pointer': (
        BOM_LASER_POINTER,
        frozenset(),
        BOM_LASER_POINTER_HITBOX,
        (12, 12),
        weapon_rig.LASER_PALETTE,
    ),
    'laser_dot': (
        BOM_LASER_DOT,
        frozenset(),
        BOM_LASER_DOT_HITBOX,
        (8, 8),
        weapon_rig.LASER_PALETTE,
    ),
}
FRAMES = {
    'lawn_zombie': zombie_rig.zombie_frames,
    'tv': tv_rig.tv_frames,
    'channel_changer': weapon_rig.channel_changer_frames,
    'zap': weapon_rig.zap_frames,
    'pizza_teen': lambda: neighbor_rig.neighbor_frames(name='pizza_teen'),
    'lawn_chair_reader': lambda: neighbor_rig.neighbor_frames(name='lawn_chair_reader'),
    'saved': neighbor_rig.saved_frames,
    'lost': neighbor_rig.lost_frames,
    'exit_door': door_rig.door_frames,
    'laser_pointer': weapon_rig.laser_pointer_frames,
    'laser_dot': weapon_rig.laser_dot_frames,
}
TEXTS = {
    'lawn_zombie': build.zombie_sprite_text,
    'tv': build.tv_sprite_text,
    'channel_changer': build.channel_changer_sprite_text,
    'zap': build.zap_sprite_text,
    'pizza_teen': lambda: build.neighbor_sprite_text(name='pizza_teen'),
    'lawn_chair_reader': lambda: build.neighbor_sprite_text(name='lawn_chair_reader'),
    'saved': build.saved_sprite_text,
    'lost': build.lost_sprite_text,
    'exit_door': build.door_sprite_text,
    'laser_pointer': build.laser_pointer_sprite_text,
    'laser_dot': build.laser_dot_sprite_text,
}


def sprite_file(name: str) -> Path:
    """Return a sprite's committed file.

    Returns:
        The path.

    """
    return SPRITES_DIRECTORY / f'{name}.toml'


def document(name: str) -> dict:
    """Return a sprite's committed file, parsed.

    Returns:
        The TOML document.

    """
    return tomllib.loads(sprite_file(name).read_text())


def test_the_zombie_bom_totals_23_frames():
    """BOM 5.1 less rise: 12 + 6 + 5."""
    assert sum(frames for frames, _interval, _loop in BOM_ZOMBIE.values()) == 23


def test_the_tv_bom_totals_24_frames():
    """Props BOM: the intact 3 + 4, and the damage stages' 17."""
    assert sum(frames for frames, _interval, _loop in BOM_TV.values()) == 24


def test_the_weapon_boms_total_8_frames():
    """Props BOM: the Channel Changer's 3 and the zap's 5."""
    assert sum(frames for frames, _i, _l in (*BOM_CHANNEL_CHANGER.values(), *BOM_ZAP.values())) == 8


def test_the_neighbor_boms_total_18_frames():
    """Character BOM section 6, first stage: 4 a neighbor, 5 for each effect."""
    total = sum(
        frames
        for animations in (BOM_NEIGHBOR, BOM_NEIGHBOR, BOM_SAVED, BOM_LOST)
        for frames, _interval, _loop in animations.values()
    )

    assert total == 18


@pytest.mark.parametrize('name', ['pizza_teen', 'lawn_chair_reader'])
def test_a_neighbors_panic_looks_different_from_its_idle(name):
    """Players must see at a glance who is in danger."""
    frames = neighbor_rig.neighbor_frames(name=name)

    assert frames['idle'][0] != frames['panic'][0]


@pytest.mark.parametrize('name', ['pizza_teen', 'lawn_chair_reader'])
def test_a_neighbor_has_one_facing(name):
    """Neighbors never move, so they face the viewer only (character BOM section 6)."""
    assert set(neighbor_rig.neighbor_frames(name=name)) == {'idle', 'panic'}


def test_the_saved_figure_leaves_from_the_feet_up():
    """Each frame of saved draws fewer cells in the bottom half than the one before."""
    frames = neighbor_rig.saved_frames()['saved']
    lower = [sum(row.count('.') for row in grid[24:]) for grid in frames]

    assert all(later >= earlier for earlier, later in itertools.pairwise(lower))


def test_the_laser_boms_total_5_frames():
    """Props BOM: the pointer's 3 and the dot's 2."""
    animations = (*BOM_LASER_POINTER.values(), *BOM_LASER_DOT.values())

    assert sum(frames for frames, _interval, _loop in animations) == 5


@pytest.mark.parametrize('facing', [*FACINGS, 'right'])
def test_the_laser_pointers_tip_is_its_red_cell(facing):
    """The light leaves from the red tip, on every facing (right mirrors left: x' = 11 - x)."""
    drawn = 'left' if facing == 'right' else facing
    grid = weapon_rig.laser_pointer_frames()[f'held_{drawn}'][0]
    tip_x, tip_y = weapon_rig.laser_tip(facing=facing)
    column = 11 - tip_x if facing == 'right' else tip_x

    assert grid[tip_y][column] == weapon_rig.LASER_TIP


def test_the_laser_pointer_is_centred_on_the_hand():
    """The grip is the canvas's centre on every facing: drawn there."""
    for name, (grid,) in weapon_rig.laser_pointer_frames().items():
        assert grid[6][6] != '.', name


def test_the_dot_has_no_outline_and_flickers():
    """A dot of light has no edge; its two frames differ."""
    first, second = weapon_rig.laser_dot_frames()['glow']

    assert 'O' not in ''.join(first) + ''.join(second)
    assert first != second


def test_the_door_bom_totals_6_frames():
    """Props BOM: 1 + 3 + 2."""
    assert sum(frames for frames, _interval, _loop in BOM_DOOR.values()) == 6


def test_the_open_door_glows_where_the_closed_one_is_shut():
    """Open, the gateway shows the glow's blues; closed, none."""
    frames = door_rig.door_frames()
    # The glow is drawn in the clothes ramp's characters
    blues = set(CLOTHES_RAMP)

    assert not blues & set(''.join(frames['closed'][0]))
    assert blues & set(''.join(frames['open'][0]))


def test_the_intact_tv_is_drawn_as_before():
    """Adding damage stages leaves the intact TV's frames as feature plan 5 drew them."""
    frames = tv_rig.tv_frames()
    rows = '\n'.join(row for name in ('static', 'spawn') for grid in frames[name] for row in grid)

    assert hashlib.sha256(rows.encode()).hexdigest() == INTACT_TV_FINGERPRINT


def test_each_damage_stage_looks_different_from_the_one_before():
    """Cracked, smashed and destroyed are each told apart from the stage before at a glance."""
    frames = tv_rig.tv_frames()
    stages = ('static', 'cracked-static', 'smashed-static', 'destroyed')

    for before, after in itertools.pairwise(stages):
        assert frames[before][0] != frames[after][0], (before, after)


@pytest.mark.parametrize('facing', [*FACINGS, 'right'])
def test_the_remote_tip_is_its_led(facing):
    """A zap leaves from the LED, on every facing (right mirrors left: x' = 11 - x)."""
    drawn = 'left' if facing == 'right' else facing
    grid = weapon_rig.channel_changer_frames()[f'held_{drawn}'][0]
    tip_x, tip_y = weapon_rig.remote_tip(facing=facing)
    column = 11 - tip_x if facing == 'right' else tip_x

    assert grid[tip_y][column] == weapon_rig.LED


def test_the_remote_is_centred_on_the_hand():
    """The hand point is the canvas's centre on every facing: the grip's cells are drawn there."""
    for name, (grid,) in weapon_rig.channel_changer_frames().items():
        assert grid[6][6] != '.', name


@pytest.mark.parametrize('name', SPRITES)
def test_every_frame_has_its_size_and_uses_only_its_palette(name):
    """Every frame is the BOM's size, drawn only in the sprite's palette characters."""
    _animations, _transitions, _hitbox, (width, height), palette = SPRITES[name]
    for namespace, grids in FRAMES[name]().items():
        for index, grid in enumerate(grids):
            assert (len(grid[0]), len(grid)) == (width, height), f'{namespace} {index}'
            assert {len(row) for row in grid} == {width}, f'{namespace} {index}'
            assert set(''.join(grid)) <= set(palette), f'{namespace} {index}'


@pytest.mark.parametrize('name', SPRITES)
def test_each_palette_keeps_the_budget_and_the_shared_outline(name):
    """At most 15 colours besides magenta, the cast's outline among them."""
    palette = SPRITES[name][4]
    colours = {colour for colour in palette.values() if colour != MAGENTA}

    assert len(colours) <= PALETTE_LIMIT
    assert SHARED_OUTLINE in colours
    assert MAGENTA in palette.values()


@pytest.mark.parametrize('name', SPRITES)
def test_each_file_holds_its_bom_animations(name):
    """Every namespace, frame count, interval and loop as the BOM lists them; nothing else."""
    found = {
        animation['namespace']: (
            len(animation['frame']),
            animation['frame_interval'],
            animation['loop'],
        )
        for animation in document(name)['animation']
    }

    assert found == SPRITES[name][0]


@pytest.mark.parametrize('name', SPRITES)
def test_each_file_has_its_bom_transitions(name):
    """Each Then naming a namespace in the same file is a transition (a file may have none)."""
    found = {
        (transition['from'], transition['to'], transition['when'])
        for transition in document(name).get('transition', [])
    }

    assert found == SPRITES[name][1]


@pytest.mark.parametrize('name', SPRITES)
def test_each_file_has_its_bom_hitbox_and_bottom_anchor(name):
    """The hitbox and anchor the BOM gives, the hitbox inside the frame."""
    sprite = document(name)['sprite']
    width, height = SPRITES[name][3]

    assert sprite['hitbox'] == SPRITES[name][2]
    assert sprite['frame_anchor'] == 'bottom'
    assert sprite['hitbox']['offset_x'] + sprite['hitbox']['width'] <= width
    assert sprite['hitbox']['offset_y'] + sprite['hitbox']['height'] <= height


@pytest.mark.parametrize('name', SPRITES)
def test_each_committed_file_is_what_its_rig_writes(name):
    """The TOML in the repository always matches its rig (regenerate with art.build)."""
    assert sprite_file(name).read_text() == TEXTS[name]()


@pytest.mark.parametrize('name', SPRITES)
def test_each_loads_through_the_sprite_factory(name):
    """The engine loads every animation."""
    sprite = SpriteFactory.load_sprite(filename=str(sprite_file(name)))

    assert set(sprite.frames) == set(SPRITES[name][0])


@pytest.mark.parametrize('name', SPRITES)
def test_rows_have_equal_lengths(name):
    """The engine's row check."""
    sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file(name))


@pytest.mark.parametrize('name', SPRITES)
def test_tags_are_well_formed(name):
    """The engine's tag check."""
    sprite_files.check_sprite_tags_are_well_formed(sprite_file=sprite_file(name))


@pytest.mark.parametrize(
    'check',
    [
        sprite_files.check_animation_timings_survive_a_save_round_trip,
        sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged,
        sprite_files.check_pixels_survive_a_save_round_trip,
        sprite_files.check_metadata_survives_a_save_round_trip,
        sprite_files.check_transitions_survive_a_save_round_trip,
    ],
    ids=lambda check: check.__name__,
)
@pytest.mark.parametrize('name', SPRITES)
def test_each_survives_a_save_round_trip(name, check, tmp_path):
    """The engine's round-trip checks."""
    check(sprite_file=sprite_file(name), directory=tmp_path)


def test_the_zombie_is_symmetric_where_it_must_be():
    """The newspaper is held in front, centred: the front view's silhouette is left-right even."""
    frame = zombie_rig.zombie_frames()['walk_down'][0]

    assert rig.silhouette(frame) == tuple(row[::-1] for row in rig.silhouette(frame))
