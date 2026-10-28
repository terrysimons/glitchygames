"""The browser games' touch controls (scripts/build_browser_bundle.py ``TOUCH_LAYOUTS``).

The page (browser/touch_controls.js) turns each button into the key events of the key it names,
so every button must press a key its game reads: one its action maps bind, or one of the shared
pause and game-over screens' (Space resumes or restarts, Esc quits). Each game checks that of its
own buttons (``test_<distribution>_touch_controls.py`` in its tests, through the shared
tests/touch_controls.py); this file checks the layouts and the boot config.
"""

from __future__ import annotations

import json

from scripts.build_browser_bundle import (
    GAMES,
    TOUCH_KEYS,
    TOUCH_LAYOUTS,
    boot_config,
    touch_controls_config,
)

from tests.touch_controls import SCANCODE_BY_CODE

# The games with no touch layout, each with its reason
GAMES_WITHOUT_TOUCH_CONTROLS = {
    'bitmappy': 'the editor needs a pointer and a keyboard; the games need only the buttons',
    'drawing-fire': 'dual stick: touch controls once its controls settle',
}


def test_every_game_has_touch_controls_or_a_reason_not():
    """Each game has a layout, or is listed with why not (a new game must do one or the other)."""
    assert set(TOUCH_LAYOUTS) == set(GAMES) - set(GAMES_WITHOUT_TOUCH_CONTROLS)


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
