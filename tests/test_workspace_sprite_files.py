"""Every workspace member's sprite files pass the engine's checks of a bundled sprite file.

The sprite files are discovered, not listed (tests/workspace_sprite_files.py): every TOML sprite
(a file with a ``sprite`` table) in any member's import packages. So a sprite that moves with its
game into a member, or a new member's sprites, are checked without anyone adding them (Drawing
Fire's soldier dropped out of the checks once when it left examples/: the Part 2 draft audit's
M5). The checks are
glitchygames.testing.sprite_files, which the engine runs on its own sprites
(tests/sprites/test_engine_sprite_files.py); a member may also run them from its own tests
(Papyrus's, and Bitmappy's sprite library), with checks of its own beside them.

The files are read from the source tree by path: nothing here imports a member.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.sprites import sprite_toml
from glitchygames.sprites.sprite_toml import (
    parse_sprite_toml,
    split_sprite_text,
    write_sprite_toml,
)
from glitchygames.testing import sprite_files
from tests.workspace_sprite_files import (
    MEMBER_ANIMATED_SPRITE_FILES,
    MEMBER_SPRITE_FILES,
    member_sprite_files,
    sprite_file_id,
)

# The engine's own sprites (src/glitchygames/assets) join the members' for the text round trips
SHIPPED_SPRITE_FILES = [
    *sorted((Path(sprite_toml.__file__).parent.parent / 'assets').glob('*.toml')),
    *MEMBER_SPRITE_FILES,
]
BITMAPPY_LIBRARY_PREFIX = 'apps/bitmappy/src/bitmappy/resources/sprites/'


@pytest.fixture
def display():
    """Give AnimatedSprite a real display for loading and saving."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(96, 64))


def test_the_members_sprites_are_found():
    """Every member that ships sprites is found: Drawing Fire's, Papyrus's and Bitmappy's."""
    found = {sprite_file_id(sprite_file) for sprite_file in MEMBER_SPRITE_FILES}

    assert 'games/drawing-fire/src/drawing_fire/sprites/soldier.toml' in found
    assert 'games/brave-adventurer/src/brave_adventurer_papyrus/sprites/cobra.toml' in found
    assert any(name.startswith('apps/bitmappy/src/bitmappy/resources/sprites/') for name in found)
    assert MEMBER_ANIMATED_SPRITE_FILES


def test_an_installed_engine_sprite_is_named_without_the_repository(mocker, tmp_path):
    """Under a non-editable install the engine's sprites are not below the repository's src/.

    nox -s test installs the engine into site-packages, so SHIPPED_SPRITE_FILES points there:
    the id is then the path below the engine's parent folder, the same under either install.
    """
    mocker.patch('tests.workspace_sprite_files.PROJECT_ROOT', tmp_path)
    engine_sprite = next((Path(sprite_toml.__file__).parent.parent / 'assets').glob('*.toml'))

    assert sprite_file_id(engine_sprite) == f'glitchygames/assets/{engine_sprite.name}'


def test_the_bitmappy_library_is_among_the_files_checked():
    """The checks below cover Bitmappy's sprite library (toadstool.toml among it) as well."""
    found = {sprite_file_id(sprite_file) for sprite_file in MEMBER_SPRITE_FILES}

    assert any(name.startswith(BITMAPPY_LIBRARY_PREFIX) for name in found)
    assert 'toadstool.toml' in {sprite_file.name for sprite_file in MEMBER_SPRITE_FILES}


def test_a_new_members_sprite_is_found_and_a_toml_without_a_sprite_is_not(tmp_path):
    """Discovery reads the workspace: a member's sprite is found wherever it is in its package."""
    (tmp_path / 'pyproject.toml').write_text(
        '[project]\nname = "glitchygames"\n\n'
        '[tool.uv.workspace]\nmembers = ["src/games/space-game"]\n',
        encoding='utf-8',
    )
    member = tmp_path / 'src' / 'games' / 'space-game'
    art = member / 'src' / 'space_game' / 'art' / 'ships'
    art.mkdir(parents=True)
    (member / 'pyproject.toml').write_text(
        '[project]\nname = "space-game"\n\n'
        '[tool.hatch.build.targets.wheel]\npackages = ["src/space_game"]\n',
        encoding='utf-8',
    )
    (art / 'ship.toml').write_text('[sprite]\nname = "ship"\n', encoding='utf-8')
    # A table header written another way is still a sprite's
    (art / 'tug.toml').write_text('[ sprite ]  # the tug\nname = "tug"\n', encoding='utf-8')
    (art / 'settings.toml').write_text('[speed]\nmaximum = 3\n', encoding='utf-8')

    assert member_sprite_files(project_root=tmp_path) == [art / 'ship.toml', art / 'tug.toml']


@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_rows_have_equal_lengths(sprite_file):
    """Every pixel row of a member's sprite is the same width."""
    sprite_files.check_rows_have_equal_lengths(sprite_file=sprite_file)


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_ANIMATED_SPRITE_FILES, ids=sprite_file_id)
def test_animation_timings_survive_a_save_round_trip(sprite_file, tmp_path):
    """Save writes each animation's timing back."""
    sprite_files.check_animation_timings_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_hitboxes_survive_a_save_round_trip_unchanged(sprite_file, tmp_path):
    """Save writes exactly the hitboxes the file defined."""
    sprite_files.check_hitboxes_survive_a_save_round_trip_unchanged(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_pixels_survive_a_save_round_trip(sprite_file, tmp_path):
    """Load, save and reload give every frame the same pixels."""
    sprite_files.check_pixels_survive_a_save_round_trip(sprite_file=sprite_file, directory=tmp_path)


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_metadata_survives_a_save_round_trip(sprite_file, tmp_path):
    """Name, description, frame_anchor and hitbox survive a save."""
    sprite_files.check_metadata_survives_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_transitions_survive_a_save_round_trip(sprite_file, tmp_path):
    """Every [[transition]] is written back in order."""
    sprite_files.check_transitions_survive_a_save_round_trip(
        sprite_file=sprite_file, directory=tmp_path
    )


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_text_and_file_loads_agree(sprite_file):
    """The text of a sprite file loads to the sprite the file does (RGBA frames, metadata, ...)."""
    sprite_files.check_text_and_file_loads_agree(sprite_file=sprite_file)


@pytest.mark.parametrize('sprite_file', SHIPPED_SPRITE_FILES, ids=sprite_file_id)
def test_every_shipped_sprite_file_round_trips(sprite_file):
    """Parsing a shipped sprite, writing it and parsing the text gives an equal document."""
    text = sprite_file.read_text(encoding='utf-8')
    document = parse_sprite_toml(text=text, source_name=str(sprite_file))
    written = write_sprite_toml(data=document)
    assert parse_sprite_toml(text=written, source_name=str(sprite_file)) == document


def test_a_shipped_multi_animation_sprite_splits_into_loadable_frames_with_equal_pixels():
    """Every frame of a real sprite is written, loads, and keeps its source pixels."""
    (sprite_file,) = [
        path
        for path in MEMBER_SPRITE_FILES
        if path.as_posix().endswith('brave_adventurer_papyrus/sprites/player.toml')
    ]
    text = sprite_file.read_text(encoding='utf-8')
    source = parse_sprite_toml(text=text, source_name='source')
    source_pixels = [
        frame['pixels'] for animation in source['animation'] for frame in animation['frame']
    ]
    assert len(source['animation']) > 1
    written = [
        parse_sprite_toml(text=each, source_name='split') for each in split_sprite_text(text=text)
    ]
    assert [document['sprite']['pixels'] for document in written] == source_pixels
    for document in written:
        assert set(document['colors']) <= set(source['colors'])


@pytest.mark.usefixtures('display')
@pytest.mark.parametrize('sprite_file', MEMBER_SPRITE_FILES, ids=sprite_file_id)
def test_save_writes_the_sprites_text(sprite_file, tmp_path):
    """Saving a loaded sprite writes exactly the text sprite_to_text gives for it."""
    sprite_files.check_save_writes_the_sprites_text(sprite_file=sprite_file, directory=tmp_path)
