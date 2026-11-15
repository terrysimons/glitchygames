"""The game's touch buttons press keys its screens read (browser/touch_controls.js).

A button whose key nothing reads would do nothing, and the keys drift with the game.
"""

from __future__ import annotations

from scripts.build_browser_bundle import TOUCH_LAYOUTS

from tests.touch_controls import (
    assert_every_button_presses_a_key_its_scenes_read,
    bound_scancodes,
)
from zombies_aint_my_neighbors.roster_scene import RosterScene


def test_every_button_presses_a_key_its_game_reads():
    """Start (Enter) and Pause (P) are what the title and the feature card bind."""
    assert_every_button_presses_a_key_its_scenes_read(
        layout=TOUCH_LAYOUTS['zombies-aint-my-neighbors'],
        scene_scancodes=[bound_scancodes(RosterScene._create_action_map(options={}))],
    )
