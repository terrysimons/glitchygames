"""Mr. Muncher's touch buttons press keys its game reads (browser/touch_controls.js).

Moved from the engine's tests (tests/test_browser_touch_controls.py, one case per game): a
button whose key nothing reads would do nothing, and the keys drift with the game.
"""

from __future__ import annotations

from scripts.build_browser_bundle import TOUCH_LAYOUTS

from mr_muncher.game import MrMuncherScene
from tests.touch_controls import (
    assert_every_button_presses_a_key_its_scenes_read,
    bound_scancodes,
)


def test_every_button_presses_a_key_its_game_reads():
    """A button whose key nothing reads would do nothing (the keys drift with the games)."""
    assert_every_button_presses_a_key_its_scenes_read(
        layout=TOUCH_LAYOUTS['mr-muncher'],
        scene_scancodes=[bound_scancodes(MrMuncherScene._create_action_map(input_mode='auto'))],
    )
