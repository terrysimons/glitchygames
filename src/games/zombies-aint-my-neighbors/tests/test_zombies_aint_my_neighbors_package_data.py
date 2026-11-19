"""The game's sprite files ship inside its package (package data), read through the package path."""

from __future__ import annotations

from importlib import resources

import pytest

import zombies_aint_my_neighbors


@pytest.mark.parametrize('name', ['dex', 'marisol', 'theo', 'june'])
def test_each_kid_ships_inside_the_package(name):
    """Each kid's sprite file is package data beside the code, not a repository file only."""
    sprite = resources.files(zombies_aint_my_neighbors) / 'sprites' / f'{name}.toml'

    assert sprite.is_file()
    assert sprite.read_text().startswith('# Written by zombies_aint_my_neighbors.art.build')
