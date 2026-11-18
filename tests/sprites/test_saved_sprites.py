"""Saving a generated sprite (sprites/saved_sprites.py): a safe name, never overwriting.

The AI console's ``/sprite`` saves under the running game's package; the sprite's name comes
from the model, so it is never trusted as a path (plans/2026-11-17-sprite-command.md, Task 3).
"""

import re

import pytest

from glitchygames.sprites.saved_sprites import game_sprites_folder, save_sprite, sprite_file_name

SAFE_STEM = re.compile(r'[a-z0-9_-]+')
TEXT = '[sprite]\nname = "x"\npixels = "#"\n'


@pytest.mark.parametrize(
    ('sprite_name', 'description'),
    [
        ('../../evil', 'a dragon'),
        ('/etc/passwd', 'a dragon'),
        ('a/b', 'a dragon'),
        ('   ', 'a dragon'),
        ('CON', 'a dragon'),
        ('..', 'a dragon'),
        ('dragon!!', 'a dragon'),
        (None, ''),
        (None, '../..'),
        ('x' * 300, 'a dragon'),
    ],
)
def test_a_file_name_is_never_a_path(tmp_path, sprite_name, description):
    """Whatever the model names it, the file lands directly in the sprites folder."""
    stem = sprite_file_name(sprite_name=sprite_name, description=description)

    assert SAFE_STEM.fullmatch(stem), stem
    assert stem.casefold() not in {'con', 'prn', 'aux', 'nul'}
    saved = save_sprite(toml_text=TEXT, file_stem=stem, sprites_folder=tmp_path / 'sprites')
    assert saved.parent == tmp_path / 'sprites'
    assert saved.read_text(encoding='utf-8') == TEXT


@pytest.mark.parametrize(
    ('sprite_name', 'description', 'stem'),
    [
        ('Blue Dragon', 'ignored', 'blue_dragon'),
        (None, 'a red  heart!', 'a_red_heart'),
        ('', 'glint', 'glint'),
        (None, '', 'sprite'),
    ],
)
def test_a_file_name_comes_from_the_name_else_the_description(sprite_name, description, stem):
    """The sprite's own name first, then the description, then ``sprite``."""
    assert sprite_file_name(sprite_name=sprite_name, description=description) == stem


def test_a_second_sprite_of_the_same_name_gets_a_new_file(tmp_path):
    """The first file is never overwritten."""
    folder = tmp_path / 'sprites'
    first = save_sprite(toml_text=TEXT, file_stem='dragon', sprites_folder=folder)
    second = save_sprite(toml_text=TEXT + '# 2\n', file_stem='dragon', sprites_folder=folder)

    assert (first.name, second.name) == ('dragon.toml', 'dragon_001.toml')
    assert first.read_text(encoding='utf-8') == TEXT


def test_a_folder_that_cannot_be_written_raises(tmp_path):
    """The caller says why it was not saved (a folder under a file, unwritable everywhere)."""
    blocker = tmp_path / 'blocker'
    blocker.write_text('a file, not a folder', encoding='utf-8')

    with pytest.raises(OSError, match='blocker'):
        save_sprite(toml_text=TEXT, file_stem='dragon', sprites_folder=blocker / 'sprites')


def test_a_games_sprites_folder_is_in_its_package():
    """``<package directory>/sprites``; an unknown package has none."""
    folder = game_sprites_folder(package='glitchygames')

    assert folder is not None
    assert folder.name == 'sprites'
    assert (folder.parent / '__init__.py').is_file()
    assert game_sprites_folder(package='no_such_package_anywhere') is None
