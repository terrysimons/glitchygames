"""Every workspace member's sprite files pass the engine's checks of a bundled sprite file.

The sprite files are discovered, not listed: every TOML sprite (a file with a ``[sprite]`` table)
in any member's import packages. So a sprite that moves with its game into a member, or a new
member's sprites, are checked without anyone adding them (Drawing Fire's soldier dropped out of
the checks once when it left examples/: the Part 2 draft audit's M5). The checks are
glitchygames.testing.sprite_files, which the engine runs on its own sprites
(tests/sprites/test_engine_sprite_files.py); a member may also run them from its own tests
(Papyrus's, and Bitmappy's sprite library), with checks of its own beside them.

The files are read from the source tree by path: nothing here imports a member.
"""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest
from scripts.workspace_packages import workspace_members

from glitchygames.display_mode import set_display_mode
from glitchygames.testing import sprite_files

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# What makes a TOML file a sprite file
SPRITE_TABLE = '[sprite]'


def member_sprite_files(*, project_root: Path) -> list[Path]:
    """Return every sprite file in the workspace members' import packages, in path order.

    Args:
        project_root: The repository.

    Returns:
        The sprite files.

    """
    return sorted(
        toml_file
        for member in workspace_members(project_root=project_root)
        for package_directory in member.package_directories
        for toml_file in package_directory.rglob(sprite_files.SPRITE_FILE_PATTERN)
        if SPRITE_TABLE in toml_file.read_text(encoding='utf-8').splitlines()
    )


MEMBER_SPRITE_FILES = member_sprite_files(project_root=PROJECT_ROOT)
MEMBER_ANIMATED_SPRITE_FILES = [
    sprite_file
    for sprite_file in MEMBER_SPRITE_FILES
    if sprite_files.ANIMATION_MARKER in sprite_file.read_text(encoding='utf-8')
]


def sprite_file_id(sprite_file: Path) -> str:
    """Name a sprite file by its path below src/ (``games/drawing-fire/src/.../soldier.toml``).

    Returns:
        The path.

    """
    return sprite_file.relative_to(PROJECT_ROOT / 'src').as_posix()


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
    (art / 'settings.toml').write_text('[speed]\nmaximum = 3\n', encoding='utf-8')

    assert member_sprite_files(project_root=tmp_path) == [art / 'ship.toml']


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
