"""The game over: the TV switches off, GAME OVER shows, and the title returns.

Feature plan 7, Task 8; character BOM decision 5 (less the villain's laugh until he is drawn).
The picture collapses to a bright line, then a dot, then dark (0.6 s); GAME OVER follows; after
4 s, or a joined player's start, the title returns with everyone still joined.
"""

from __future__ import annotations

import importlib

import pygame

from zombies_aint_my_neighbors.game_over import (
    GAME_OVER_SECONDS,
    SWITCH_OFF_SECONDS,
    GameOverScene,
)
from zombies_aint_my_neighbors.roster import JoinRoster
from zombies_aint_my_neighbors.title import TitleScene

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
KEYBOARD = support.KEYBOARD
OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True}


def game_over() -> GameOverScene:
    """Return the game over for the keyboard player, set up.

    Returns:
        The scene.

    """
    scene = GameOverScene(options=dict(OPTIONS), roster=JoinRoster.empty().join(device=KEYBOARD))
    scene.setup()
    return scene


def lit_pixels(surface: pygame.Surface) -> int:
    """Count the pixels brighter than mid-grey.

    Returns:
        The count.

    """
    width, height = surface.get_size()
    return sum(
        1
        for y in range(0, height, 4)
        for x in range(0, width, 4)
        if sum(surface.get_at((x, y))[:3]) > 3 * 128
    )


def test_the_plan_values():
    """0.6 s of switching off; the title after 4 s."""
    assert (SWITCH_OFF_SECONDS, GAME_OVER_SECONDS) == (0.6, 4.0)


def test_the_picture_collapses_to_a_line_then_a_dot():
    """Fewer lit pixels as the switch-off goes on, and GAME OVER not yet shown."""
    scene = game_over()
    counts = []
    for seconds in (0.05, 0.25, 0.45):
        support.tick_to(scene, seconds=seconds)
        counts.append(lit_pixels(support.rendered(scene)))
        assert not scene.game_over_text.visible

    assert counts[0] > counts[1] > counts[2]


def test_game_over_shows_after_the_switch_off():
    """The words appear once the screen is dark."""
    scene = game_over()

    support.tick_to(scene, seconds=SWITCH_OFF_SECONDS + 0.1)

    assert scene.game_over_text.visible
    assert lit_pixels(support.rendered(scene)) > 0


def test_after_four_seconds_the_title_returns_with_everyone_joined():
    """The roster carries back."""
    scene = game_over()

    support.tick_to(scene, seconds=GAME_OVER_SECONDS + 0.05)

    assert isinstance(scene.next_scene, TitleScene)
    assert scene.next_scene.roster == scene.roster


def test_a_joined_players_start_returns_to_the_title_at_once():
    """Enter, after the words show."""
    scene = game_over()
    support.tick_to(scene, seconds=SWITCH_OFF_SECONDS + 0.1)

    support.press_key(scene, pygame.K_RETURN)

    assert isinstance(scene.next_scene, TitleScene)
