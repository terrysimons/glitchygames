"""The browser games' touch controls (scripts/build_browser_bundle.py ``TOUCH_LAYOUTS``).

The page (browser/touch_controls.js) turns each button into the key events of the key it names,
so every button must press a key its game reads: one its action maps bind, or one of the shared
pause and game-over screens' (Space resumes or restarts, Esc quits).
"""

from __future__ import annotations

import json

import pygame
import pytest
from scripts.build_browser_bundle import (
    GAMES,
    TOUCH_KEYS,
    TOUCH_LAYOUTS,
    boot_config,
    touch_controls_config,
)

from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_modes.title import TitleScene
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene
from glitchygames.examples.paddleslap import Game as PaddleSlapScene
from mr_muncher.game import MrMuncherScene

# The pygame scancode of each key a touch button can press (its DOM KeyboardEvent.code)
SCANCODE_BY_CODE = {
    'ArrowUp': pygame.KSCAN_UP,
    'ArrowDown': pygame.KSCAN_DOWN,
    'ArrowLeft': pygame.KSCAN_LEFT,
    'ArrowRight': pygame.KSCAN_RIGHT,
    'Space': pygame.KSCAN_SPACE,
    'Escape': pygame.KSCAN_ESCAPE,
    'KeyW': pygame.KSCAN_W,
    'KeyS': pygame.KSCAN_S,
    'KeyP': pygame.KSCAN_P,
    'ShiftLeft': pygame.KSCAN_LSHIFT,
}

# The shared pause and game-over screens' keys (scenes/builtin_scenes: Space, Esc)
SHARED_SCREEN_CODES = frozenset({'Space', 'Escape'})


def bound_scancodes(*action_maps) -> set[int]:
    """Return every scancode the action maps bind.

    Returns:
        The scancodes.

    """
    return {
        binding['scancode']
        for action_map in action_maps
        for bindings in action_map.to_dict().values()
        for binding in bindings
        if 'scancode' in binding
    }


# Each page's scenes that take its buttons, by the scancodes each reads: a button must work on
# every one of them (Brave Adventurer's page runs its title screen, then either game)
GAME_SCANCODES = {
    'paddleslap': lambda: [bound_scancodes(*PaddleSlapScene._create_action_maps())],
    'brave-adventurer': lambda: [
        bound_scancodes(TitleScene._create_action_map(input_mode='auto')),
        bound_scancodes(BraveAdventurerScene._create_action_map(input_mode='auto')),
        bound_scancodes(PapyrusBraveAdventurerScene._create_action_map(input_mode='auto')),
    ],
    'clockwork-keep': lambda: [
        bound_scancodes(ClockworkKeepScene._create_action_map(input_mode='auto'))
    ],
    'mr-muncher': lambda: [bound_scancodes(MrMuncherScene._create_action_map(input_mode='auto'))],
}


# The games with no touch layout, each with its reason
GAMES_WITHOUT_TOUCH_CONTROLS = {
    'bitmappy': 'the editor needs a pointer and a keyboard; the games need only the buttons',
    'drawing-fire': 'dual stick: touch controls once its controls settle',
}


def layout_buttons(layout) -> list:
    """Return every button of a layout (gaps left out).

    Returns:
        The buttons, cluster by cluster.

    """
    return [
        button
        for rows in (layout.left, layout.center, layout.right)
        for row in rows
        for button in row
        if button is not None
    ]


def test_every_game_has_touch_controls_or_a_reason_not():
    """Each game has a layout, or is listed with why not (a new game must do one or the other)."""
    assert set(TOUCH_LAYOUTS) == set(GAMES) - set(GAMES_WITHOUT_TOUCH_CONTROLS)


@pytest.mark.parametrize('game', sorted(GAME_SCANCODES))
def test_every_button_presses_a_key_its_game_reads(game):
    """A button whose key nothing reads would do nothing (the keys drift with the games)."""
    shared = {SCANCODE_BY_CODE[code] for code in SHARED_SCREEN_CODES}
    for scene_scancodes in GAME_SCANCODES[game]():
        readable = scene_scancodes | shared

        for button in layout_buttons(TOUCH_LAYOUTS[game]):
            assert SCANCODE_BY_CODE[button.code] in readable, (game, button)


def test_the_brave_adventurer_title_screen_takes_the_games_buttons():
    """On a phone the title screen is driven by the games' buttons: the arrows and Jump."""
    title_scancodes = bound_scancodes(TitleScene._create_action_map(input_mode='auto'))

    for button in layout_buttons(TOUCH_LAYOUTS['brave-adventurer']):
        assert SCANCODE_BY_CODE[button.code] in title_scancodes, button


def test_every_touch_key_has_its_scancode_here():
    """The test's table covers every key a button can press (a new one must be added to both)."""
    assert set(TOUCH_KEYS) == set(SCANCODE_BY_CODE)


def test_boot_config_carries_the_layout_with_each_keys_event_fields():
    """The page builds the buttons from boot_config.json, which names each key fully."""
    config = boot_config(game='mr-muncher', arguments=[])
    controls = touch_controls_config(layout=TOUCH_LAYOUTS['mr-muncher'])

    assert config['touch_controls'] == controls
    up_row, middle_row, down_row = controls['left']
    assert up_row[0] is None
    assert up_row[1] == {
        'label': '▲',
        'key_name': '',
        'code': 'ArrowUp',
        'key': 'ArrowUp',
        'key_code': 38,
    }
    assert middle_row[1] is None
    assert [button['code'] for button in middle_row if button] == ['ArrowLeft', 'ArrowRight']
    down_button = down_row[1]
    assert down_button is not None
    assert down_button['code'] == 'ArrowDown'
    assert controls['center'] == [
        [{'label': 'Pause', 'key_name': 'P', 'code': 'KeyP', 'key': 'p', 'key_code': 80}]
    ]
    json.dumps(config)


def test_bitmappy_has_no_touch_controls_in_its_config():
    """Without a layout the config says None, and the page shows no buttons."""
    assert boot_config(game='bitmappy', arguments=[])['touch_controls'] is None
