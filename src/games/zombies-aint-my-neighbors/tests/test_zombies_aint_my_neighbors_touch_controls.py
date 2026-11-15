"""The game's touch buttons press keys its screens read (browser/touch_controls.js).

A button whose key nothing reads would do nothing, and the keys drift with the game. Start and
Pause work on every screen; the D-pad and Fire are the neighborhood's, read as polled keys
(``controls.POLLED_SCANCODES``), so without them a phone could join but never walk or fire.
"""

from __future__ import annotations

from scripts.build_browser_bundle import TOUCH_LAYOUTS, TouchLayout

from tests.touch_controls import (
    SCANCODE_BY_CODE,
    assert_every_button_presses_a_key_its_scenes_read,
    bound_scancodes,
    layout_buttons,
)
from zombies_aint_my_neighbors.controls import FIRE_SCANCODES, POLLED_SCANCODES
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene
from zombies_aint_my_neighbors.roster_scene import RosterScene

LAYOUT = TOUCH_LAYOUTS['zombies-aint-my-neighbors']


def test_start_and_pause_press_keys_every_screen_reads():
    """Start (Enter) and Pause (P) are what the title, the card and the neighborhood bind."""
    assert_every_button_presses_a_key_its_scenes_read(
        layout=TouchLayout(center=LAYOUT.center, right=LAYOUT.right[:1]),
        scene_scancodes=[bound_scancodes(RosterScene._create_action_map(options={}))],
    )


def test_the_d_pad_and_fire_press_keys_the_neighborhood_polls():
    """The left thumb walks and the right fires: keys the neighborhood reads each frame."""
    walk_and_fire = TouchLayout(left=LAYOUT.left, right=LAYOUT.right[1:2])

    assert layout_buttons(walk_and_fire)
    for button in layout_buttons(walk_and_fire):
        assert SCANCODE_BY_CODE[button.code] in POLLED_SCANCODES, button


def test_the_d_pad_walks_all_four_ways_and_a_button_fires():
    """Up, down, left and right on the left; Fire on the right."""
    left = {SCANCODE_BY_CODE[button.code] for row in LAYOUT.left for button in row if button}
    right = [button for row in LAYOUT.right for button in row if button]

    assert len(left) == 4
    assert any(
        SCANCODE_BY_CODE[button.code] in FIRE_SCANCODES and button.label == 'Fire'
        for button in right
    )


def test_a_switch_button_presses_the_key_the_neighborhood_binds_to_switch():
    """Feature plan 8: Switch (K) swaps the weapon; the neighborhood's action map binds it."""
    switch = [
        button for row in LAYOUT.right for button in row if button and button.label == 'Switch'
    ]
    bound = bound_scancodes(NeighborhoodScene._create_action_map(options={}))

    assert len(switch) == 1
    assert SCANCODE_BY_CODE[switch[0].code] in bound
