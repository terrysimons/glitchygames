"""The game over: the TV switches off, GAME OVER shows, and the title returns.

Feature plan 7, Task 8; character BOM decision 5 (less the villain's laugh until he is drawn).
The picture collapses to a bright line, then a dot, then dark (0.6 s); GAME OVER follows; after
4 s, or a joined player's start, the title returns with everyone still joined.
"""

from __future__ import annotations

import importlib

import pygame
import pytest

from zombies_aint_my_neighbors import music
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


@pytest.mark.draws_frames
def test_the_picture_collapses_to_a_line_then_a_dot():
    """Fewer lit pixels as the switch-off goes on, and GAME OVER not yet shown."""
    scene = game_over()
    counts = []
    for seconds in (0.05, 0.25, 0.45):
        support.tick_to(scene, seconds=seconds)
        counts.append(lit_pixels(support.rendered(scene)))
        assert not scene.game_over_text.visible

    assert counts[0] > counts[1] > counts[2]


@pytest.mark.draws_frames
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
    assert not scene.next_scene.opening
    assert scene.next_scene.roster == scene.roster


def test_a_joined_players_start_returns_to_the_title_at_once():
    """Enter, after the words show."""
    scene = game_over()
    support.tick_to(scene, seconds=SWITCH_OFF_SECONDS + 0.1)

    support.press_key(scene, pygame.K_RETURN)

    assert isinstance(scene.next_scene, TitleScene)
    assert not scene.next_scene.opening


@pytest.mark.parametrize(
    'picture', ['game_over_text', 'screen_picture', 'switch_off_sound', 'game_over_music']
)
def test_the_pictures_cannot_be_read_before_setup(picture):
    """The words, the switch-off and its sound exist once the scene is set up: sooner is a bug."""
    scene = GameOverScene(options=dict(OPTIONS), roster=JoinRoster.empty().join(device=KEYBOARD))

    with pytest.raises(RuntimeError, match='not set up'):
        getattr(scene, picture)


def test_setting_up_again_after_a_pause_keeps_one_set_of_pictures():
    """Resuming from the pause screen sets the scene up again: nothing is drawn twice."""
    scene = game_over()
    pictures = scene.all_sprites.sprites()
    words = scene.game_over_text

    scene.setup()

    assert scene.all_sprites.sprites() == pictures
    assert scene.game_over_text is words


def test_an_unjoined_pads_start_does_nothing():
    """Only a joined player's start leaves early."""
    scene = game_over()

    support.controller_start(scene, instance_id=9)

    assert scene.next_scene is None


# Its sounds (feature plan 11)


def test_the_switch_off_sounds_once_as_the_picture_collapses(mocker):
    """The tube's falling whine on the first frame, centred, and never again."""
    scene = game_over()
    switch_off = mocker.spy(scene.switch_off_sound, 'play')

    support.tick_to(scene, seconds=1.0 / 60.0)
    assert switch_off.call_count == 1
    support.tick_to(scene, seconds=GAME_OVER_SECONDS - 0.05)

    assert switch_off.call_count == 1
    assert switch_off.call_args.kwargs == {}


def test_the_sting_plays_once_as_game_over_shows(mocker):
    """Dun, dun, DUNNN: one sound, every layer mixed in, on the frame the words appear, once."""
    scene = game_over()
    sting = mocker.spy(scene.game_over_music, 'play')

    support.tick_to(scene, seconds=SWITCH_OFF_SECONDS - 0.05)
    assert sting.call_count == 0
    support.tick_to(scene, seconds=SWITCH_OFF_SECONDS + 0.02)
    assert scene.game_over_text.visible
    support.tick_to(scene, seconds=GAME_OVER_SECONDS - 0.05)

    assert sting.call_count == 1
    assert sting.call_args.kwargs == {
        'volume': music.MUSIC_VOLUME,
        'bus': music.MUSIC_BUS,
        'priority': music.MUSIC_PRIORITY,
        'loop': False,
    }


def test_setting_up_again_after_a_pause_keeps_its_sounds():
    """A pause's return sets the scene up again: the same sounds, nothing asked for twice."""
    scene = game_over()
    switch_off, sting = scene.switch_off_sound, scene.game_over_music

    scene.setup()

    assert scene.switch_off_sound is switch_off
    assert scene.game_over_music is sting
