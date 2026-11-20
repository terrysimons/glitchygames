"""The game's sprites and demo ship inside its package (package data), read through the package."""

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


def test_the_attract_demo_ships_inside_the_package():
    """The attract demo (feature plan 13) is a bundled demo: package data beside the code."""
    demo = resources.files(zombies_aint_my_neighbors) / 'demos' / 'neighborhood_four_kids.jsonl.gz'

    assert demo.is_file()
