"""The feature card: the placeholder screen a joined player's second start opens.

It shows FEATURE PRESENTATION and each joined player in their colour; a joined player's start
goes back to the title with everyone still joined; unplugging the last player goes back too.
"""

from __future__ import annotations

import importlib
import json

import pygame
import pytest

from glitchygames.events.base import HashableEvent
from glitchygames.sprites import AnimatedSprite
from tests.input.stand_in_devices import STAND_IN_PAD
from zombies_aint_my_neighbors.feature_card import CARD_SECONDS, FeatureCardScene
from zombies_aint_my_neighbors.neighborhood import NeighborhoodScene, stage_needs
from zombies_aint_my_neighbors.roster import PLAYER_COLOURS, JoinRoster
from zombies_aint_my_neighbors.run_state import NeighborKind, RunState
from zombies_aint_my_neighbors.sprite_kit import Part, PartKind
from zombies_aint_my_neighbors.title import TitleScene

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
KEYBOARD = support.KEYBOARD
gamepad = support.gamepad
OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True}


def card_for(roster: JoinRoster) -> FeatureCardScene:
    """Return a feature card for a roster, set up as the scene manager sets it up.

    Returns:
        The card.

    """
    card = FeatureCardScene(options=dict(OPTIONS), roster=roster)
    card.setup()
    return card


def test_a_joined_players_second_start_begins_the_feature():
    """On the title, a start from a device that has joined opens the feature card."""
    title = TitleScene(options=dict(OPTIONS))
    title.setup()
    support.press_key(title, pygame.K_RETURN)

    support.press_key(title, pygame.K_RETURN)

    assert isinstance(title.next_scene, FeatureCardScene)
    assert title.next_scene.roster == title.roster


def test_an_unjoined_devices_first_start_only_joins():
    """A new device's first start joins it and never also begins the feature."""
    title = TitleScene(options=dict(OPTIONS))
    title.setup()
    support.press_key(title, pygame.K_RETURN)

    support.controller_start(title, instance_id=4)

    assert title.next_scene is None
    assert support.joined_devices(title) == [KEYBOARD, gamepad(4), None, None]


def test_a_pads_second_start_on_the_joystick_layer_begins_the_feature_too():
    """Beginning works from a pad in joystick mode as from the keyboard."""
    title = TitleScene(options=dict(OPTIONS))
    title.setup()
    support.joystick_start(title, instance_id=2)

    support.joystick_start(title, instance_id=2)

    assert isinstance(title.next_scene, FeatureCardScene)


def test_the_card_shows_each_joined_player_in_their_colour():
    """Joined players' colours are on the card; the free slots' colours are not."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(3))
    roster = roster.leave(device=KEYBOARD).join(device=gamepad(5)).join(device=KEYBOARD)
    # P1: pad 5, P2: pad 3, P3: keyboard; P4 free
    card = card_for(roster)

    screen = support.rendered(card)

    whole = screen.get_rect()
    for slot_index in (0, 1, 2):
        assert support.exact_colour_count(screen, whole, PLAYER_COLOURS[slot_index]) > 0
    assert support.exact_colour_count(screen, whole, PLAYER_COLOURS[3]) == 0


def test_a_joined_players_start_on_the_card_skips_to_the_neighborhood():
    """Start skips the card: straight to the neighborhood, everyone still joined."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(7))
    card = card_for(roster)

    support.controller_start(card, instance_id=7)

    assert isinstance(card.next_scene, NeighborhoodScene)
    assert card.next_scene.roster == roster


def test_the_card_shows_for_two_seconds_then_the_neighborhood_begins():
    """A TV title card: FEATURE PRESENTATION for 2 s, then the show."""
    roster = JoinRoster.empty().join(device=KEYBOARD)
    card = card_for(roster)

    support.tick_to(card, seconds=CARD_SECONDS - 0.1)
    assert card.next_scene is None
    support.tick_to(card, seconds=CARD_SECONDS + 0.05)

    assert isinstance(card.next_scene, NeighborhoodScene)
    assert card.next_scene.roster == roster


def test_backspace_on_the_card_goes_back_to_the_title_with_everyone_joined():
    """Back (Backspace) returns to the title, so more players can join."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(7))
    card = card_for(roster)

    support.press_key(card, pygame.K_BACKSPACE)

    assert isinstance(card.next_scene, TitleScene)
    assert not card.next_scene.opening
    assert card.next_scene.roster == roster


@pytest.mark.parametrize('layer', ['controller', 'joystick'])
def test_a_pads_back_button_on_the_card_goes_back_to_the_title(layer):
    """A pad's BACK does the same, on either layer."""
    roster = JoinRoster.empty().join(device=gamepad(7))
    card = card_for(roster)
    if layer == 'controller':
        card.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN, instance_id=7, button=pygame.CONTROLLER_BUTTON_BACK
            )
        )
    else:
        card.on_joy_button_down_event(
            HashableEvent(
                pygame.JOYBUTTONDOWN, instance_id=7, joy=7, button=pygame.CONTROLLER_BUTTON_BACK
            )
        )

    assert isinstance(card.next_scene, TitleScene)
    assert not card.next_scene.opening


def test_other_keys_on_the_card_do_nothing():
    """Only start and back steer the card."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))

    support.press_key(card, pygame.K_a)

    assert card.next_scene is None


def test_an_unjoined_devices_start_on_the_card_does_nothing():
    """Only joined players control the card."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))

    support.controller_start(card, instance_id=8)
    support.joystick_start(card, instance_id=8)

    assert card.next_scene is None


def test_unplugging_a_player_on_the_card_drops_them():
    """A joined pad unplugged on the card leaves the roster (Review Focus 3)."""
    with support.running_game(scene_class=FeatureCardScene, plugged_in_at_start=False) as (
        engine,
        card,
    ):
        assert isinstance(card, FeatureCardScene)
        support.plug_in_the_pad(engine)
        pad = gamepad(STAND_IN_PAD.instance_id)
        card.roster = JoinRoster.empty().join(device=KEYBOARD).join(device=pad)

        support.unplug_the_pad(engine)

        assert support.joined_devices(card) == [KEYBOARD, None, None, None]
        assert card.next_scene is None


def test_unplugging_the_last_player_on_the_card_returns_to_the_title():
    """With nobody left, the card goes back to the title (Review Focus 3)."""
    with support.running_game(scene_class=FeatureCardScene, plugged_in_at_start=False) as (
        engine,
        card,
    ):
        assert isinstance(card, FeatureCardScene)
        support.plug_in_the_pad(engine)
        card.roster = JoinRoster.empty().join(device=gamepad(STAND_IN_PAD.instance_id))

        support.unplug_the_pad(engine)

        assert isinstance(card.next_scene, TitleScene)
        assert not card.next_scene.opening
        assert card.next_scene.roster == JoinRoster.empty()


@pytest.mark.parametrize('input_mode', ['auto', 'joystick'])
def test_the_card_handles_raw_device_events(input_mode):
    """Plugging, remapping and unplugging a pad on the card raises nothing."""
    with support.running_game(
        scene_class=FeatureCardScene, input_mode=input_mode, plugged_in_at_start=False
    ) as (engine, _card):
        support.plug_in_the_pad(engine)
        engine.process_controller_event(
            HashableEvent(pygame.CONTROLLERDEVICEREMAPPED, instance_id=STAND_IN_PAD.instance_id)
        )
        support.unplug_the_pad(engine)


def test_replay_arguments_rebuild_the_card_with_the_same_roster_through_json():
    """A replay rebuilds the card from its arguments as JSON gives them back."""
    roster = JoinRoster.empty().join(device=gamepad(1)).join(device=KEYBOARD)
    card = FeatureCardScene(options=dict(OPTIONS), roster=roster)

    arguments = json.loads(json.dumps(card.replay_arguments()))
    rebuilt = FeatureCardScene(options=dict(OPTIONS), **arguments)

    assert rebuilt.roster == roster


def test_the_card_renders_no_text_after_setup(mocker):
    """Every text image is made in setup() (decision 11)."""
    text = importlib.import_module('zombies_aint_my_neighbors.text')
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))
    spy = mocker.spy(text, 'render_text')

    support.tick_to(card, seconds=1.0)
    support.rendered(card)

    assert spy.call_count == 0


def test_a_screen_that_does_not_say_what_start_does_fails_loudly():
    """RosterScene's own start press raises: each screen must say what start means."""
    roster_scene = importlib.import_module('zombies_aint_my_neighbors.roster_scene')
    screen = roster_scene.RosterScene(options=dict(OPTIONS))

    with pytest.raises(NotImplementedError, match='RosterScene does not say what a start press'):
        support.press_key(screen, pygame.K_RETURN)


def test_setting_the_card_up_again_after_a_pause_keeps_one_set_of_sprites():
    """Resuming from the pause screen sets the card up again; it makes no second set."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))
    sprites_before = set(card.all_sprites.sprites())

    card.setup()

    assert set(card.all_sprites.sprites()) == sprites_before


def test_a_given_sprite_group_is_used():
    """A screen draws into the group it is given (the engine's, or a test's)."""
    group = pygame.sprite.LayeredDirty()

    card = FeatureCardScene(options=dict(OPTIONS), groups=group, roster=JoinRoster.empty())

    assert card.all_sprites is group


def test_the_card_returns_to_the_title_when_its_last_pad_left_during_a_pause():
    """Resuming the card after its only player's pad was unplugged on the pause screen."""
    # The engine's PauseScene leaves the unplug unhandled (Engine wishlist #10)
    with support.running_game(
        scene_class=FeatureCardScene, plugged_in_at_start=False, unhandled_events_raise=False
    ) as (
        engine,
        card,
    ):
        assert isinstance(card, FeatureCardScene)
        support.plug_in_the_pad(engine)
        card.roster = JoinRoster.empty().join(device=gamepad(STAND_IN_PAD.instance_id))
        support.press_key(card, pygame.K_p)
        pause_screen = card.next_scene
        engine.scene_manager.switch_to_scene(pause_screen)

        support.unplug_the_pad(engine)
        engine.scene_manager.switch_to_scene(card)
        # The resumed card's first frame
        support.rendered(card)

        assert support.joined_devices(card) == [None, None, None, None]
        assert isinstance(card.next_scene, TitleScene)
        assert not card.next_scene.opening


# The card between stages (feature plan 7)


def test_the_first_card_is_the_feature_presentation_and_starts_a_new_run():
    """From the title, no run yet: FEATURE PRESENTATION, then stage 1."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))
    support.tick_to(card, seconds=CARD_SECONDS + 0.05)

    assert card.card_text == 'FEATURE PRESENTATION'
    assert isinstance(card.next_scene, NeighborhoodScene)
    assert card.next_scene.run == RunState.new_run()


def test_a_later_stages_card_names_the_stage_and_carries_the_run():
    """After a stage clear: STAGE 2, then the neighborhood with that run."""
    run = RunState.new_run().next_stage(rescued=(NeighborKind.PIZZA_TEEN,))
    card = FeatureCardScene(
        options=dict(OPTIONS), roster=JoinRoster.empty().join(device=KEYBOARD), run=run
    )
    card.setup()
    support.tick_to(card, seconds=CARD_SECONDS + 0.05)

    assert card.card_text == 'STAGE 2'
    assert isinstance(card.next_scene, NeighborhoodScene)
    assert card.next_scene.run == run


def test_replay_arguments_carry_the_run_through_json():
    """A replay starting on a stage's card gets its run back."""
    run = RunState.new_run().next_stage(rescued=(NeighborKind.LAWN_CHAIR_READER,))
    card = FeatureCardScene(options=dict(OPTIONS), roster=JoinRoster.empty(), run=run)

    arguments = json.loads(json.dumps(card.replay_arguments()))

    assert FeatureCardScene(options=dict(OPTIONS), **arguments).run == run


def test_back_on_a_later_stages_card_keeps_the_run():
    """Back between stages keeps the run; the title's next start brings back the same card.

    The owner, 2026-11-15: a new run there would dodge the shrinking pool.
    """
    roster = JoinRoster.empty().join(device=KEYBOARD)
    run = RunState.new_run().lose_life(slot_index=0).next_stage(rescued=(NeighborKind.PIZZA_TEEN,))
    card = FeatureCardScene(options=dict(OPTIONS), roster=roster, run=run)
    card.setup()

    support.press_key(card, pygame.K_BACKSPACE)

    title = card.next_scene
    assert isinstance(title, TitleScene)
    assert title.run == run
    title.setup()
    support.press_key(title, pygame.K_RETURN)
    assert isinstance(title.next_scene, FeatureCardScene)
    assert title.next_scene.run == run


def test_back_on_the_first_card_leaves_the_title_to_start_afresh():
    """Before stage 1 nothing is lost: the title holds no run, and its card starts a new one."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))

    support.press_key(card, pygame.K_BACKSPACE)

    title = card.next_scene
    assert isinstance(title, TitleScene)
    assert title.run is None
    assert 'run' not in title.replay_arguments()


def test_a_titles_kept_run_survives_its_replay_arguments():
    """A replay starting on that title gets the run back through JSON."""
    run = RunState.new_run().next_stage(rescued=(NeighborKind.LAWN_CHAIR_READER,))
    title = TitleScene(options=dict(OPTIONS), roster=JoinRoster.empty(), run=run)

    arguments = json.loads(json.dumps(title.replay_arguments()))

    assert TitleScene(options=dict(OPTIONS), **arguments).run == run


# Building the coming stage ahead (feature plan 9)


def coming_needs(card: FeatureCardScene):
    """Return the parts the card's coming stage takes.

    Returns:
        The needs.

    """
    return stage_needs(
        run=card.run, joined_slots={player.slot_index for player in card.roster.joined_players}
    )


def test_the_card_builds_the_coming_stage_before_it_ends():
    """By the card's last frame every sprite the stage takes is built, four players' kids too."""
    roster = JoinRoster.empty().join(device=KEYBOARD)
    for instance_id in (1, 2, 3):
        roster = roster.join(device=gamepad(instance_id))
    card = card_for(roster)

    support.tick_to(card, seconds=CARD_SECONDS - 0.1)

    assert card.next_scene is None
    assert card.kit.is_ready_for(needs=coming_needs(card))


def test_a_stage_begun_after_the_whole_card_loads_no_sprite_file(mocker):
    """The pause the stage's build was (0.34 s) is gone: the card built it all."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))
    support.tick_to(card, seconds=CARD_SECONDS - 0.05)
    loads = mocker.spy(AnimatedSprite, '__init__')

    support.tick_to(card, seconds=CARD_SECONDS + 0.05)

    assert isinstance(card.next_scene, NeighborhoodScene)
    assert loads.call_count == 0


def test_a_later_stages_card_builds_its_own_neighbors():
    """Stage 2 with three Pizza Teens saved: the card builds three Pizza Teens, no Readers."""
    run = RunState.new_run().next_stage(rescued=(NeighborKind.PIZZA_TEEN,) * 3)
    card = FeatureCardScene(
        options=dict(OPTIONS), roster=JoinRoster.empty().join(device=KEYBOARD), run=run
    )
    card.setup()

    support.tick_to(card, seconds=CARD_SECONDS - 0.1)

    assert card.kit.ready(Part(kind=PartKind.NEIGHBOR, variant=NeighborKind.PIZZA_TEEN)) == 3
    assert card.kit.ready(Part(kind=PartKind.NEIGHBOR, variant=NeighborKind.LAWN_CHAIR_READER)) == 0


def test_the_card_gives_its_stage_the_kit_it_built():
    """The stage takes the sprites the card built: the same kit, handed over."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))

    support.tick_to(card, seconds=CARD_SECONDS + 0.05)

    assert isinstance(card.next_scene, NeighborhoodScene)
    assert card.next_scene.kit is card.kit


def test_a_card_given_no_kit_makes_its_own():
    """From the title (or a replay's rebuild) a card starts an empty kit of its own."""
    first = card_for(JoinRoster.empty().join(device=KEYBOARD))
    second = card_for(JoinRoster.empty().join(device=KEYBOARD))

    assert first.kit is not second.kit
    assert first.kit.storage.sprites() == []


def test_the_card_builds_nothing_once_the_stage_has_begun():
    """A start pressed early begins the stage; the card builds no leftovers after it."""
    card = card_for(JoinRoster.empty().join(device=KEYBOARD))
    support.tick_to(card, seconds=0.1)
    support.press_key(card, pygame.K_RETURN)
    assert isinstance(card.next_scene, NeighborhoodScene)
    left = len(card.kit.storage.sprites())

    support.tick_to(card, seconds=0.5)

    assert len(card.kit.storage.sprites()) == left


# The score is built while the game starts, never on the card (feature plan 11)


def compiles(card: FeatureCardScene) -> int:
    """Return how many sounds the card's audio engine has compiled so far.

    Returns:
        The count.

    """
    return card.scene_manager.audio.accountant.compile_count


def test_the_card_compiles_no_sound_from_start_to_end():
    """Four players' card shown to its end: the score was built while the game started."""
    roster = JoinRoster.empty().join(device=KEYBOARD)
    for instance_id in (1, 2, 3):
        roster = roster.join(device=gamepad(instance_id))
    card = card_for(roster)

    support.tick_to(card, seconds=CARD_SECONDS - 0.1)

    assert card.next_scene is None
    assert compiles(card) == 0
