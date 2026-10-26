"""Brave Adventurer's touch buttons press keys its scenes read (browser/touch_controls.js).

Moved from the engine's tests (tests/test_browser_touch_controls.py). The page runs the title
screen, then either game, so a button must work on every one of them: the title screen
(``brave_adventurer_modes``), Classic (``brave_adventurer``) and Papyrus
(``brave_adventurer_papyrus``). The engine's ``GAMES`` names only the title scene, so these
per-scene checks live here.
"""

from __future__ import annotations

from scripts.build_browser_bundle import TOUCH_LAYOUTS

from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer_modes.title import TitleScene
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from tests.touch_controls import (
    SCANCODE_BY_CODE,
    assert_every_button_presses_a_key_its_scenes_read,
    bound_scancodes,
    layout_buttons,
)

# The touch codes the Brave Adventurer title screen deliberately ignores, each with why
TITLE_SCREEN_IGNORED_TOUCH_CODES = {
    'Escape': 'the Pause button: Escape does nothing on the title screen (the user, 2026-10-25)'
}


def test_every_button_presses_a_key_its_game_reads():
    """A button whose key nothing reads would do nothing (the keys drift with the games)."""
    assert_every_button_presses_a_key_its_scenes_read(
        layout=TOUCH_LAYOUTS['brave-adventurer'],
        scene_scancodes=[
            bound_scancodes(TitleScene._create_action_map(input_mode='auto')),
            bound_scancodes(BraveAdventurerScene._create_action_map(input_mode='auto')),
            bound_scancodes(PapyrusBraveAdventurerScene._create_action_map(input_mode='auto')),
        ],
    )


def test_the_brave_adventurer_title_screen_takes_the_games_buttons():
    """On a phone the title screen is driven by the games' buttons, bar the ones it ignores.

    Every button but those in TITLE_SCREEN_IGNORED_TOUCH_CODES is bound on the title screen, and
    every ignored code really is unbound there (a stale exemption fails too).
    """
    title_scancodes = bound_scancodes(TitleScene._create_action_map(input_mode='auto'))

    for button in layout_buttons(TOUCH_LAYOUTS['brave-adventurer']):
        if button.code not in TITLE_SCREEN_IGNORED_TOUCH_CODES:
            assert SCANCODE_BY_CODE[button.code] in title_scancodes, button

    for code in TITLE_SCREEN_IGNORED_TOUCH_CODES:
        assert SCANCODE_BY_CODE[code] not in title_scancodes, code
