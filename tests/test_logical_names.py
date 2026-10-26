"""glitchygames/logical_names.py: a recording names a game by where it belongs, not its module."""

from __future__ import annotations

import pytest

from glitchygames import logical_names
from glitchygames.logical_names import (
    logical_module_name,
    logical_name,
    module_for_logical_module,
)
from glitchygames.scenes import Scene


class LocalScene(Scene):
    """A scene in a module that belongs to no layer (this test file)."""


@pytest.mark.parametrize(
    ('module', 'expected'),
    [
        ('mr_muncher.game', 'games.mr_muncher.game'),
        ('paddleslap', 'games.paddleslap'),
        ('drawing_fire.game', 'games.drawing_fire.game'),
        ('joystick_demo', 'demos.joystick_demo'),
        ('text_input_demo', 'demos.text_input_demo'),
        ('glitchygames.scenes.builtin_scenes.pause', 'glitchygames.scenes.builtin_scenes.pause'),
        ('tests.test_logical_names', 'tests.test_logical_names'),
        ('__main__', '__main__'),
    ],
)
def test_a_module_gets_its_layer_or_keeps_its_path(module, expected):
    """A game's or demo's module is named by its layer; any other module by its path."""
    assert logical_module_name(module=module) == expected


def test_a_class_is_its_logical_module_and_qualified_name():
    """The logical module, then a colon and the qualified name."""
    assert logical_name(scene_class=LocalScene) == 'tests.test_logical_names:LocalScene'


def test_a_member_class_keeps_its_logical_name_wherever_it_is_installed(mocker):
    """A member's logical name names its layer and package, not where the package lives."""
    mocker.patch.dict(logical_names.MEMBER_LAYERS, {'space_game': 'games'})

    assert logical_module_name(module='space_game.game') == 'games.space_game.game'
    assert (
        module_for_logical_module(logical_module=logical_module_name(module='space_game.game'))
        == 'space_game.game'
    )


def test_a_logical_module_maps_back_to_the_module_that_holds_it(mocker):
    """A member's package, else the name itself."""
    mocker.patch.dict(logical_names.MEMBER_LAYERS, {'space_game': 'games'})

    assert module_for_logical_module(logical_module='games.paddleslap') == 'paddleslap'
    assert module_for_logical_module(logical_module='games.drawing_fire.game') == (
        'drawing_fire.game'
    )
    assert module_for_logical_module(logical_module='demos.joystick_demo') == 'joystick_demo'
    assert module_for_logical_module(logical_module='games.space_game.game') == 'space_game.game'
    assert module_for_logical_module(logical_module='glitchygames.scenes') == 'glitchygames.scenes'


def test_every_member_has_a_layer():
    """The owner's table (2026-10-25): every game, demo and app is a member of its layer."""
    assert logical_names.MEMBER_LAYERS == {
        'mr_muncher': 'games',
        'brave_adventurer_core': 'games',
        'brave_adventurer': 'games',
        'brave_adventurer_papyrus': 'games',
        'brave_adventurer_modes': 'games',
        'clockwork_keep': 'games',
        'paddleslap': 'games',
        'drawing_fire': 'games',
        'bitmappy': 'apps',
        'dt_demo': 'demos',
        'joystick_demo': 'demos',
        'text_input_demo': 'demos',
    }


def test_a_logical_module_of_an_unknown_package_is_left_as_it_is():
    """A layer's name with a package no layer table lists maps to no module of ours."""
    assert module_for_logical_module(logical_module='games.unknown_game') == 'games.unknown_game'
    assert module_for_logical_module(logical_module='games') == 'games'
