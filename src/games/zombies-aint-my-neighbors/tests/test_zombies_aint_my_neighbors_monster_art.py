"""The Lawn Zombie's and the TV's sprite files, checked against the character and props BOMs.

The expected names, frames, timings, loops and transitions are copied from the BOMs (character
BOM section 5.1, less ``rise``: decision 6; props BOM, the TV), not read from the rigs, so a rig
that drifts from its BOM fails here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from glitchygames.sprites import SpriteFactory
from glitchygames.testing import sprite_files
from zombies_aint_my_neighbors.art import build, rig, tv_rig, zombie_rig

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
# Props BOM, the TV
BOM_TV = {'static': (3, 0.08, True), 'spawn': (4, 0.08, False)}
BOM_TV_TRANSITIONS = frozenset({('spawn', 'static', 'animation_complete')})
BOM_TV_HITBOX = {'offset_x': 4, 'offset_y': 12, 'width': 40, 'height': 32}

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
}
FRAMES = {'lawn_zombie': zombie_rig.zombie_frames, 'tv': tv_rig.tv_frames}
TEXTS = {'lawn_zombie': build.zombie_sprite_text, 'tv': build.tv_sprite_text}


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


def test_the_tv_bom_totals_7_frames():
    """Props BOM: 3 + 4."""
    assert sum(frames for frames, _interval, _loop in BOM_TV.values()) == 7


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
    """Each Then naming a namespace in the same file is a transition."""
    found = {
        (transition['from'], transition['to'], transition['when'])
        for transition in document(name)['transition']
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
