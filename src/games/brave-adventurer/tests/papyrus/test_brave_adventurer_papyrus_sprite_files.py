"""The Papyrus Edition's TOML sprites pass the engine's checks of a bundled sprite file.

The engine's tests check its own sprite files (tests/sprites/test_engine_sprite_files.py, with
glitchygames.testing.sprite_files); these run the same checks on Papyrus's, which moved out of
the engine with the game. The state machines' transitions are only Papyrus's (no engine sprite
has any).
"""

import pygame
import pytest

from brave_adventurer_papyrus.constants import SPRITES_DIR
from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import AnimatedSprite
from glitchygames.testing import sprite_files

PAPYRUS_SPRITE_FILES = sorted(SPRITES_DIR.glob('*.toml'))
PAPYRUS_ANIMATED_SPRITE_FILES = [
    sprite_file
    for sprite_file in PAPYRUS_SPRITE_FILES
    if '[[animation]]' in sprite_file.read_text(encoding='utf-8')
]


def sprite_file_id(sprite_file):
    """Name a sprite file by its file name (``cobra.toml``).

    Returns:
        The file's name.

    """
    return sprite_file.name


@pytest.fixture
def display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


def test_every_papyrus_sprite_is_checked():
    """The five sprites (player, cobra, scarab, scorpion, gold scarab), all animated."""
    assert [sprite_file.name for sprite_file in PAPYRUS_SPRITE_FILES] == [
        'cobra.toml',
        'gold_scarab.toml',
        'player.toml',
        'scarab.toml',
        'scorpion.toml',
    ]
    assert PAPYRUS_ANIMATED_SPRITE_FILES == PAPYRUS_SPRITE_FILES


@pytest.mark.parametrize('sprite_file', PAPYRUS_SPRITE_FILES, ids=sprite_file_id)
def test_rows_have_equal_lengths(sprite_file):
    """Every pixel row of a Papyrus sprite is the same width."""
    sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', PAPYRUS_ANIMATED_SPRITE_FILES, ids=sprite_file_id)
def test_animation_timings_survive_a_save_round_trip(sprite_file, tmp_path):
    """Save writes each animation's timing back."""
    sprite_files.check_animation_timings_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', PAPYRUS_SPRITE_FILES, ids=sprite_file_id)
def test_hitboxes_survive_a_save_round_trip_unchanged(sprite_file, tmp_path):
    """Save writes exactly the hitboxes the file defined."""
    sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', PAPYRUS_SPRITE_FILES, ids=sprite_file_id)
def test_pixels_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load, save and reload give every frame the same pixels."""
    sprite_files.check_pixels_survive_a_save_round_trip(sprite_file=sprite_file, directory=tmp_path)


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', PAPYRUS_SPRITE_FILES, ids=sprite_file_id)
def test_metadata_survives_a_save_round_trip(sprite_file, tmp_path):
    """Name, description, frame_anchor and hitbox survive a save."""
    sprite_files.check_metadata_survives_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', PAPYRUS_SPRITE_FILES, ids=sprite_file_id)
def test_transitions_survive_a_save_round_trip(sprite_file, tmp_path):
    """Every [[transition]] is written back in order."""
    sprite_files.check_transitions_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize(
    ('sprite_file', 'expected_pairs'),
    [
        (
            SPRITES_DIR / 'player.toml',
            [
                ('idle', 'running'),
                ('running', 'idle'),
                ('idle', 'jumping'),
                ('running', 'jumping'),
                ('falling', 'idle'),
                ('jumping', 'idle'),
                # Expressions phase 2 moved the falling transitions into the TOML, appended last
                ('idle', 'falling'),
                ('jumping', 'falling'),
                ('running', 'falling'),
            ],
        ),
        (
            SPRITES_DIR / 'cobra.toml',
            [('idle', 'strike'), ('strike', 'idle')],
        ),
    ],
    ids=['papyrus-player', 'cobra'],
)
def test_state_machine_transitions_reload_in_order(sprite_file, expected_pairs, tmp_path):
    """The reloaded sprite's state machine has the same transitions in the same order."""
    saved_file = tmp_path / sprite_file.name
    AnimatedSprite(str(sprite_file)).save(str(saved_file), 'toml')
    reloaded_sprite = AnimatedSprite(str(saved_file))

    assert reloaded_sprite.state_machine is not None
    assert [
        (transition.from_state, transition.to_state)
        for transition in reloaded_sprite.state_machine._transitions
    ] == expected_pairs


def test_cobra_eye_has_a_color():
    """The cobra's second eye, glyph 'e', has a palette color: a darker shade of 'E'.

    It had none, so the eye drew transparent (the strict pixel-row check found it).
    """
    cobra = AnimatedSprite(str(SPRITES_DIR / 'cobra.toml'))

    assert cobra._color_map['e'] == (180, 30, 30)
    assert cobra.pixel_row_repairs == []
