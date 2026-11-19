"""The kids' rig and Dex's sprite file, checked against the character BOM.

The BOM (plans/2026-11-14-zombies-aint-my-neighbors-2-character-bom.md, section 3) is the spec:
the expected names, frame counts, intervals, loops and transitions below are copied from it, not
read from the rig, so a rig that drifts from the BOM fails here.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from glitchygames.sprites import SpriteFactory
from glitchygames.testing import sprite_files
from zombies_aint_my_neighbors.art import build, contact_sheet, hand_points, palettes, poses, rig

SPRITES_DIRECTORY = Path(build.__file__).resolve().parents[1] / 'sprites'
FACINGS = ('down', 'up', 'left')

# BOM section 3: (state, facings, frames, interval, loop)
# BOM decision 11: standing and walking also face the diagonals
MOVE_FACINGS = (*FACINGS, 'down-left', 'up-left')
BOM_KID_ANIMATIONS: tuple[tuple[str, tuple[str, ...], int, float, bool], ...] = (
    ('idle', MOVE_FACINGS, 2, 0.5, True),
    ('walk', MOVE_FACINGS, 4, 0.12, True),
    ('shoot', FACINGS, 2, 0.08, False),
    ('walk-shoot', FACINGS, 4, 0.12, True),
    ('spray', FACINGS, 2, 0.08, True),
    ('swing', FACINGS, 3, 0.08, True),
    ('launch', FACINGS, 3, 0.08, False),
    ('throw', FACINGS, 3, 0.08, False),
    ('knocked-out', ('',), 5, 0.1, False),
    ('respawn', ('',), 4, 0.1, False),
    ('cheer', ('',), 2, 0.25, True),
    ('rescue', ('',), 2, 0.1, False),
)
# BOM section 3's Then column, where it names a namespace in the same file
BOM_KID_TRANSITIONS: frozenset[tuple[str, str, str]] = frozenset({
    *(
        (f'{state}_{facing}', f'idle_{facing}', 'animation_complete')
        for state in ('shoot', 'launch', 'throw')
        for facing in FACINGS
    ),
    ('knocked-out', 'respawn', 'animation_complete and lives_left > 0'),
    ('respawn', 'idle_down', 'animation_complete'),
    ('rescue', 'idle_down', 'animation_complete'),
})
# BOM decision 10: 32x48 native, every size and hitbox doubled, 15-colour palettes
BOM_KID_HITBOX = {'offset_x': 6, 'offset_y': 12, 'width': 20, 'height': 36}
BOM_KID_SIZE = (32, 48)
BOM_KID_PALETTE_LIMIT = 15
SHARED_OUTLINE = (24, 16, 32)
MAGENTA = (255, 0, 255)
# The kid animations that hold a weapon, so every frame needs a hand point (BOM section 1)
WEAPON_STATES = ('shoot', 'walk-shoot', 'spray', 'swing', 'launch', 'throw')


def namespace(state: str, facing: str) -> str:
    """Return a BOM namespace: ``<state>_<facing>``, or ``<state>`` with no facing.

    Returns:
        The namespace.

    """
    return f'{state}_{facing}' if facing else state


def expected_animations() -> dict[str, tuple[int, float, bool]]:
    """Return every kid namespace the BOM lists, with its frames, interval and loop.

    Returns:
        Namespace -> (frames, interval, loop).

    """
    return {
        namespace(state, facing): (frames, interval, loop)
        for state, facings, frames, interval, loop in BOM_KID_ANIMATIONS
        for facing in facings
    }


def kid_file(look: palettes.KidLook) -> Path:
    """Return a kid's committed sprite file.

    Returns:
        The path, in the package's sprites directory.

    """
    return SPRITES_DIRECTORY / f'{look.name}.toml'


def kid_document(look: palettes.KidLook) -> dict:
    """Return a kid's committed sprite file, parsed.

    Returns:
        The TOML document.

    """
    return tomllib.loads(kid_file(look).read_text())


def test_the_bom_totals_94_frames_a_kid():
    """The spec copied here adds up to the BOM's total, so a copying slip shows."""
    assert sum(frames for frames, _interval, _loop in expected_animations().values()) == 94


def test_the_rigs_poses_match_the_bom_frame_for_frame():
    """The rig makes exactly the BOM's animations, each with the BOM's frame count."""
    frames = rig.kid_frames(look=palettes.DEX)

    assert {name: len(grids) for name, grids in frames.items()} == {
        name: count for name, (count, _interval, _loop) in expected_animations().items()
    }


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_every_frame_is_32_by_48_and_uses_only_its_palette(look):
    """Every frame of every kid is the BOM's size, drawn only in that kid's palette."""
    allowed = set(look.palette)
    for name, grids in rig.kid_frames(look=look).items():
        for index, grid in enumerate(grids):
            assert (len(grid[0]), len(grid)) == BOM_KID_SIZE, f'{name} frame {index}'
            assert {len(row) for row in grid} == {BOM_KID_SIZE[0]}, f'{name} frame {index}'
            assert set(''.join(grid)) <= allowed, f'{name} frame {index}'


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_keeps_to_the_palette_budget_and_shares_the_outline(look):
    """At most 15 colours besides magenta (the SNES budget), the cast's outline among them."""
    colours = {colour for colour in look.palette.values() if colour != MAGENTA}

    assert len(colours) <= BOM_KID_PALETTE_LIMIT
    assert SHARED_OUTLINE in colours
    assert MAGENTA in look.palette.values()


def test_the_kids_differ_only_in_colour_and_head_never_in_pose():
    """The shared rig: every kid's frames have the same silhouette below the shoulders."""
    reference = rig.kid_frames(look=palettes.DEX)
    for look in palettes.KIDS:
        frames = rig.kid_frames(look=look)
        for name, grids in reference.items():
            for index, grid in enumerate(grids):
                body_rows = slice(rig.SHOULDER_ROW, BOM_KID_SIZE[1])
                assert rig.silhouette(grid[body_rows]) == rig.silhouette(
                    frames[name][index][body_rows]
                ), f'{look.name} {name} frame {index}'


def test_every_weapon_frame_has_a_hand_point_inside_the_frame():
    """Weapons sit in the hand: each weapon frame has one, within 32x48 (BOM section 1)."""
    for state in WEAPON_STATES:
        for facing in FACINGS:
            name = namespace(state, facing)
            frames = expected_animations()[name][0]
            points = hand_points.KID_HAND_POINTS[name]
            assert len(points) == frames, name
            for x, y in points:
                assert 0 <= x < BOM_KID_SIZE[0], name
                assert 0 <= y < BOM_KID_SIZE[1], name


def test_idle_and_walk_frames_have_no_hand_points():
    """Weapons show only while attacking (BOM decision 9), so these carry none."""
    assert not any(
        name.startswith(('idle_', 'walk_', 'knocked-out', 'respawn', 'cheer', 'rescue'))
        for name in hand_points.KID_HAND_POINTS
    )


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_file_holds_every_bom_animation_with_its_timing_and_loop(look):
    """Every namespace, frame count, interval and loop as the BOM lists them; nothing else."""
    found = {
        animation['namespace']: (
            len(animation['frame']),
            animation['frame_interval'],
            animation['loop'],
        )
        for animation in kid_document(look)['animation']
    }

    assert found == expected_animations()


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_file_has_no_right_facing_animations(look):
    """Right is left mirrored by the game (BOM section 1), so the file never holds it."""
    assert not any(
        animation['namespace'].endswith('_right') for animation in kid_document(look)['animation']
    )


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_file_has_the_bom_transitions(look):
    """Each Then that names a namespace in the same file is a transition (BOM section 1)."""
    found = {
        (transition['from'], transition['to'], transition['when'])
        for transition in kid_document(look)['transition']
    }

    assert found == BOM_KID_TRANSITIONS


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_file_has_the_bom_hitbox_and_bottom_anchor(look):
    """The body hitbox and the bottom anchor, as the BOM gives them."""
    document = kid_document(look)

    assert document['sprite']['hitbox'] == BOM_KID_HITBOX
    assert document['sprite']['frame_anchor'] == 'bottom'


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_committed_kid_file_is_what_the_rig_writes(look):
    """The TOML in the repository always matches the rig (regenerate with art.build)."""
    assert kid_file(look).read_text() == build.sprite_file_text(look=look)


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_loads_through_the_sprite_factory(look):
    """The engine loads the file as an animated sprite with every animation."""
    sprite = SpriteFactory.load_sprite(filename=str(kid_file(look)))

    assert set(sprite.frames) == set(expected_animations())


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_rows_have_equal_lengths(look):
    """The engine's row check."""
    sprite_files.check_rows_have_equal_lengths(sprite_file=kid_file(look))


@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_tags_are_well_formed(look):
    """The engine's tag check."""
    sprite_files.check_sprite_tags_are_well_formed(sprite_file=kid_file(look))


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
@pytest.mark.parametrize('look', palettes.KIDS, ids=lambda look: look.name)
def test_each_kid_survives_a_save_round_trip(look, check, tmp_path):
    """The engine's round-trip checks: a save keeps timings, hitboxes, pixels, metadata."""
    check(sprite_file=kid_file(look), directory=tmp_path)


def test_the_build_command_writes_every_kid_where_it_is_told(tmp_path):
    """``python -m zombies_aint_my_neighbors.art.build --output DIR`` writes each kid there."""
    build.main(['--output', str(tmp_path)])

    for look in palettes.KIDS:
        assert (tmp_path / f'{look.name}.toml').read_text() == build.sprite_file_text(look=look)


def test_the_contact_sheet_command_writes_a_png_with_a_row_per_animation(tmp_path):
    """The contact sheet has one row per BOM animation and room for the longest one."""
    import pygame

    sheet_path = tmp_path / 'dex.png'

    contact_sheet.main(['--kid', 'dex', '--output', str(sheet_path)])

    sheet = pygame.image.load(str(sheet_path))
    cell_height = BOM_KID_SIZE[1] * contact_sheet.SCALE + contact_sheet.GAP
    assert sheet.get_height() == len(expected_animations()) * cell_height


def test_an_animation_the_bom_does_not_list_is_refused():
    """Asking the poses for a state the BOM never lists raises, naming it."""
    with pytest.raises(ValueError, match="no kid animation 'moonwalk'"):
        poses.kid_poses(state='moonwalk', facing=None)


def test_painting_off_the_canvas_does_nothing_and_reading_it_is_transparent():
    """A pose that reaches past the edge is clipped, never wrapped or raised."""
    canvas = rig.Canvas()

    for x, y in ((-1, 5), (rig.WIDTH, 5), (5, -1), (5, rig.HEIGHT)):
        canvas.put(x=x, y=y, character=palettes.WHITE)

    assert canvas.grid() == rig.Canvas().grid()
    assert canvas.at(x=-1, y=0) == palettes.TRANSPARENT
    assert canvas.at(x=0, y=rig.HEIGHT) == palettes.TRANSPARENT
