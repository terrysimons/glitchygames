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


# Feature plan 12: the intro's sprites, checked against the character BOM's section 7. The
# expected sizes, animations, frame counts, intervals and loops are copied from the BOM, not read
# from the rig, so a rig that drifts from the BOM fails here.

# (frames, interval, loop) per animation; a one-frame still has no interval in the BOM (None)
type IntroAnimations = dict[str, tuple[int, float | None, bool | None]]

BOM_INTRO_BAG: IntroAnimations = {'sit': (2, 0.5, True), 'startled': (2, 0.12, False)}
# Stem -> (frame size, animations, the most colours besides magenta)
BOM_INTRO_SPRITES: dict[str, tuple[tuple[int, int], IntroAnimations, int]] = {
    **{f'intro_bag_{look.name}': ((48, 32), BOM_INTRO_BAG, 15) for look in palettes.KIDS},
    'intro_tv': (
        (64, 64),
        {
            'show': (4, 0.25, True),
            'static': (3, 0.08, True),
            'bulge': (4, 0.12, False),
            'burst': (4, 0.08, False),
            'switch-off': (3, 0.08, False),
        },
        15,
    ),
    'intro_hands': ((64, 64), {'reach': (4, 0.12, False)}, 15),
    # The BOM says 14, "as in play": the play zombie's palette holds 15 (feature plan 12, a ruling)
    'intro_zombie': ((64, 64), {'climb-out': (4, 0.12, False)}, 15),
    'intro_lamp': ((32, 32), {'still': (1, None, None), 'flicker': (2, 0.08, True)}, 15),
    # A still (one animation, one frame) is in the static layout: its animation is the sprite's
    'intro_snacks': ((32, 32), {'intro_snacks': (1, None, None)}, 15),
}
BOM_INTRO_FRAMES = 46


def intro_file(stem: str) -> Path:
    """Return an intro sprite's committed file.

    Returns:
        The path, in the package's sprites directory.
    """
    return SPRITES_DIRECTORY / f'{stem}.toml'


def intro_document(stem: str) -> dict:
    """Return an intro sprite's committed file, parsed.

    Returns:
        The TOML document.
    """
    return tomllib.loads(intro_file(stem).read_text(encoding='utf-8'))


def intro_animations(stem: str) -> list[dict]:
    """Return an intro sprite's animations as its file holds them.

    A still in the static layout (its pixels in ``[sprite]``) is one animation named after the
    sprite, with one frame and no timing, as the engine loads it.

    Returns:
        Each animation's table: namespace, frames, and its interval and loop when it has them.
    """
    document = intro_document(stem)
    if 'animation' in document:
        return document['animation']
    sprite = document['sprite']
    return [
        {
            'namespace': sprite['name'],
            'frame': [{'frame_index': 0, 'pixels': sprite['pixels']}],
            'frame_interval': None,
            'loop': None,
        }
    ]


def test_the_intro_bom_totals_46_frames():
    """The rig draws the BOM's 46 intro frames: 4 x (2 + 2) + 18 + 4 + 4 + 3 + 1."""
    from zombies_aint_my_neighbors.art import intro_rig

    frames = sum(
        len(grids)
        for stem in intro_rig.INTRO_ANIMATIONS
        for grids in intro_rig.intro_frames(sprite=stem).values()
    )

    assert set(intro_rig.INTRO_ANIMATIONS) == set(BOM_INTRO_SPRITES)
    assert frames == BOM_INTRO_FRAMES


@pytest.mark.parametrize('stem', BOM_INTRO_SPRITES)
def test_each_intro_file_holds_every_bom_animation_with_its_timing_and_loop(stem):
    """Every animation, frame count, interval and loop as the BOM lists them; nothing else."""
    _, animations, _ = BOM_INTRO_SPRITES[stem]
    found = {
        animation['namespace']: (
            len(animation['frame']),
            animation['frame_interval'],
            animation['loop'],
        )
        for animation in intro_animations(stem)
    }

    assert set(found) == set(animations)
    for name, (frames, interval, loop) in animations.items():
        assert found[name][0] == frames, name
        if interval is not None:
            assert found[name][1:] == (interval, loop), name


@pytest.mark.parametrize('stem', BOM_INTRO_SPRITES)
def test_every_intro_frame_has_its_bom_size_and_keeps_to_its_palette(stem):
    """Each frame is the BOM's size, and the sprite keeps to its colour budget."""
    (width, height), _, limit = BOM_INTRO_SPRITES[stem]
    document = intro_document(stem)

    for animation in intro_animations(stem):
        for frame in animation['frame']:
            rows = frame['pixels'].strip('\n').split('\n')
            assert len(rows) == height, (animation['namespace'], frame['frame_index'])
            assert {len(row) for row in rows} == {width}, animation['namespace']
    colours = {
        (colour['red'], colour['green'], colour['blue']) for colour in document['colors'].values()
    }
    assert len(colours - {MAGENTA}) <= limit


@pytest.mark.parametrize('stem', BOM_INTRO_SPRITES)
def test_every_shipped_intro_sprite_passes_the_engines_checks(stem, tmp_path):
    """The schema, equal rows, tags, and a save keeping the document, pixels and timings.

    The timing check skips a one-frame sprite (a save writes it without timing), and a skip
    ends the test: it runs last, so every other check still runs for the snack bowl.
    """
    sprite_file = intro_file(stem)

    sprite_files.check_values_match_the_schema(sprite_file=sprite_file)
    sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)
    sprite_files.check_sprite_tags_are_well_formed(sprite_file=sprite_file)
    sprite_files.check_pixels_survive_a_save_round_trip(sprite_file=sprite_file, directory=tmp_path)
    sprite_files.check_save_keeps_the_parsed_document(sprite_file=sprite_file)
    sprite_files.check_animation_timings_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


def test_every_file_the_build_writes_survives_a_save(tmp_path):
    """A save of each built file gives back the document it parses to (the engine's save format).

    The test gap behind main going red after #227: #220 made a save write a one-animation,
    one-frame sprite in the static layout, while the build still wrote the snack bowl with an
    ``[[animation]]`` table. Checked here on the build's own output, not only the committed files.
    """
    for sprite_file in build.build(directory=tmp_path):
        sprite_files.check_save_keeps_the_parsed_document(sprite_file=sprite_file)


def test_a_still_must_name_its_animation_after_its_sprite():
    """The engine names a still's one animation after its sprite: the build refuses another name."""
    with pytest.raises(ValueError, match="the still 'bowl' must name its one animation 'bowl'"):
        build.character_sprite_text(
            header=(),
            name='bowl',
            description='A still',
            tags=('prop',),
            hitbox={'offset_x': 0, 'offset_y': 0, 'width': 1, 'height': 1},
            palette={'.': (255, 0, 255)},
            frames={'still': (('.',),)},
            specs=(),
        )


@pytest.mark.parametrize('stem', BOM_INTRO_SPRITES)
def test_each_committed_intro_file_is_what_the_rig_writes(stem):
    """Each shipped intro sprite is the build's output exactly: rebuilt, never hand-edited."""
    assert intro_file(stem).read_text(encoding='utf-8') == build.intro_sprite_text(sprite=stem)


@pytest.mark.parametrize('stem', BOM_INTRO_SPRITES)
def test_each_intro_sprite_is_an_intro_prop_anchored_at_the_bottom(stem):
    """Tagged as the intro's, anchored at the bottom, and with no transitions.

    The intro's timeline (feature plan 12) is the only thing that moves one animation to the next.
    """
    document = intro_document(stem)

    assert 'intro' in document['sprite']['tags']
    assert document['sprite']['frame_anchor'] == 'bottom'
    assert 'transition' not in document


def test_building_the_intro_twice_writes_the_same_files(tmp_path):
    """The rig is deterministic: two builds write the same bytes, the static included."""
    first = {path.name: path.read_bytes() for path in build.build(directory=tmp_path / 'one')}
    second = {path.name: path.read_bytes() for path in build.build(directory=tmp_path / 'two')}

    assert {name for name in first if name.startswith('intro_')} == {
        f'{stem}.toml' for stem in BOM_INTRO_SPRITES
    }
    assert first == second


def test_the_intro_contact_sheet_has_a_row_per_intro_animation():
    """One row per sprite and animation (18), each as tall as the tallest intro frame."""
    rows = sum(len(animations) for _, animations, _ in BOM_INTRO_SPRITES.values())

    sheet = contact_sheet.intro_contact_sheet()

    assert rows == 18
    assert sheet.get_height() == rows * (64 * contact_sheet.SCALE + contact_sheet.GAP)


def test_the_contact_sheet_command_writes_the_intro_sheet(tmp_path):
    """``... contact_sheet --intro --output PATH`` writes the intro's sheet as a PNG."""
    output = tmp_path / 'intro.png'

    contact_sheet.main(['--intro', '--output', str(output)])

    assert output.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'


@pytest.mark.parametrize('function', ['intro_frames', 'intro_palette'])
def test_the_intro_rig_refuses_a_sprite_the_bom_does_not_list(function):
    """Asking for an intro sprite the BOM never lists raises, naming it."""
    from zombies_aint_my_neighbors.art import intro_rig

    with pytest.raises(ValueError, match="no intro sprite 'intro_moon'"):
        getattr(intro_rig, function)(sprite='intro_moon')
