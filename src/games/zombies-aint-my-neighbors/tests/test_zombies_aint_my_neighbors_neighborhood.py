"""The neighborhood: the joined kids walk a yard larger than the screen under one camera.

Feature plan 4 (plans/2026-11-14-zombies-aint-my-neighbors-4-walking.md), Task 3. Input is the
engine's own ``InputSnapshot`` set as the frame's polled input, as the engine sets it.
"""

from __future__ import annotations

import importlib
import json
import random

import pygame
import pytest

from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.randomness import reset_streams
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from tests.input.stand_in_devices import STAND_IN_PAD
from zombies_aint_my_neighbors.kid import KID_HEIGHT, KID_WIDTH, KNOCKOUT_SECONDS, KidState
from zombies_aint_my_neighbors.neighborhood import (
    LAWN_COLOUR,
    SCREEN_MARGIN,
    WALK_SPEED,
    YARD_HEIGHT,
    YARD_WIDTH,
    NeighborhoodScene,
)
from zombies_aint_my_neighbors.roster import JoinRoster
from zombies_aint_my_neighbors.title import TitleScene
from zombies_aint_my_neighbors.tv import (
    SPAWN_MINIMUM_SECONDS,
    TV_SIZE,
    ZOMBIES_IN_ALL,
    ZOMBIES_PER_TV,
)

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
KEYBOARD = support.KEYBOARD
gamepad = support.gamepad
OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True}
FRAME_SECONDS = 1.0 / 60.0
SCREEN_WIDTH, SCREEN_HEIGHT = support.SCREEN_SIZE
FULL = 32767


@pytest.fixture(autouse=True)
def nothing_held():
    """Each test starts with no input held, and leaves none held."""
    hold()
    yield
    hold()


def hold(*, scancodes=(), pads=None) -> None:
    """Make this frame's polled input hold keys (by scancode) and pad sticks.

    Args:
        scancodes: The keys held.
        pads: Instance id -> (stick x, stick y) on the controller layer, -32768..32767.

    """
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(scancodes),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            controller_axes={
                instance_id: (x, y, 0, 0, 0, 0) for instance_id, (x, y) in (pads or {}).items()
            },
        )
    )


def neighborhood(roster: JoinRoster | None = None) -> NeighborhoodScene:
    """Return the neighborhood for a roster, set up as the scene manager sets it up.

    Returns:
        The scene.

    """
    scene = NeighborhoodScene(options=dict(OPTIONS), roster=roster)
    scene.setup()
    return scene


def run(scene: NeighborhoodScene, *, seconds: float) -> None:
    """Run the scene's logic for some seconds, frame by frame."""
    support.tick_to(scene, seconds=scene.game_time + seconds)


def four_players() -> JoinRoster:
    """Return a roster of the keyboard and three pads.

    Returns:
        The roster.

    """
    roster = JoinRoster.empty().join(device=KEYBOARD)
    for instance_id in (1, 2, 3):
        roster = roster.join(device=gamepad(instance_id))
    return roster


def group_span(scene: NeighborhoodScene) -> tuple[float, float]:
    """Return the width and height the joined kids' frames span together.

    Returns:
        (width, height).

    """
    kids = list(scene.kids.values())
    left = min(kid.world_x for kid in kids)
    right = max(kid.world_x + KID_WIDTH for kid in kids)
    top = min(kid.world_y for kid in kids)
    bottom = max(kid.world_y + KID_HEIGHT for kid in kids)
    return right - left, bottom - top


def test_built_from_options_alone_the_keyboard_plays_dex():
    """A recording's first scene is built from options only: the keyboard is P1 (Dex)."""
    scene = neighborhood()

    assert support.joined_devices(scene) == [KEYBOARD, None, None, None]
    assert [kid.look_name for kid in scene.kids.values()] == ['dex']


def test_each_joined_slot_plays_its_kid():
    """P1 is Dex, P2 Marisol, P3 Theo, P4 June, whoever joined there."""
    scene = neighborhood(four_players().leave(device=gamepad(2)))

    assert {slot: kid.look_name for slot, kid in scene.kids.items()} == {
        0: 'dex',
        1: 'marisol',
        3: 'june',
    }


def test_the_keyboard_player_walks_at_walk_speed():
    """Holding D for a second moves the keyboard's kid right by the walk speed."""
    scene = neighborhood()
    dex = scene.kids[0]
    start_x, start_y = dex.world_x, dex.world_y

    hold(scancodes={pygame.KSCAN_D})
    run(scene, seconds=1.0)

    assert dex.world_x == pytest.approx(start_x + WALK_SPEED, abs=WALK_SPEED * FRAME_SECONDS)
    assert dex.world_y == start_y


def test_a_pad_player_walks_with_their_own_pad_only():
    """A pad's stick moves its kid; the keyboard's kid stays put."""
    scene = neighborhood(JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(5)))
    dex, marisol = scene.kids[0], scene.kids[1]
    dex_start, marisol_start_y = (dex.world_x, dex.world_y), marisol.world_y

    hold(pads={5: (0, FULL)})
    run(scene, seconds=0.5)

    assert (dex.world_x, dex.world_y) == dex_start
    assert marisol.world_y > marisol_start_y


def test_kids_never_leave_the_yard():
    """Walking into an edge for a long time stops at the edge."""
    scene = neighborhood()
    dex = scene.kids[0]

    hold(scancodes={pygame.KSCAN_A, pygame.KSCAN_W})
    run(scene, seconds=20.0)

    assert (dex.world_x, dex.world_y) == (0.0, 0.0)
    hold(scancodes={pygame.KSCAN_D, pygame.KSCAN_S})
    run(scene, seconds=30.0)
    assert (dex.world_x, dex.world_y) == (YARD_WIDTH - KID_WIDTH, YARD_HEIGHT - KID_HEIGHT)


@pytest.mark.parametrize('players', [2, 3, 4])
def test_the_group_always_fits_on_the_screen(players):
    """However the players wander, the group never spans more than the screen less its margins."""
    pads = (1, 2, 3)[: players - 1]
    roster = JoinRoster.empty().join(device=KEYBOARD)
    for instance_id in pads:
        roster = roster.join(device=gamepad(instance_id))
    scene = neighborhood(roster)
    generator = random.Random(20261114 + players)
    limit_width = SCREEN_WIDTH - 2 * SCREEN_MARGIN
    limit_height = SCREEN_HEIGHT - 2 * SCREEN_MARGIN
    for _ in range(40):
        keys = generator.choice([
            (),
            (pygame.KSCAN_A,),
            (pygame.KSCAN_D,),
            (pygame.KSCAN_W, pygame.KSCAN_D),
        ])
        sticks = {
            pad: (generator.randint(-FULL, FULL), generator.randint(-FULL, FULL)) for pad in pads
        }
        hold(scancodes=keys, pads=sticks)
        for _ in range(generator.randint(1, 60)):
            scene.advance_game_time(seconds=FRAME_SECONDS)
            scene.dt_tick(FRAME_SECONDS)
            width, height = group_span(scene)
            assert width <= limit_width + 1e-6
            assert height <= limit_height + 1e-6


def test_the_camera_aims_at_the_middle_of_the_group():
    """The camera's target is the middle of the kids' bounding box, not their average."""
    scene = neighborhood(four_players())
    kids = list(scene.kids.values())
    left = min(kid.world_x for kid in kids)
    right = max(kid.world_x + KID_WIDTH for kid in kids)
    top = min(kid.world_y for kid in kids)
    bottom = max(kid.world_y + KID_HEIGHT for kid in kids)

    assert scene.camera_target() == ((left + right) / 2, (top + bottom) / 2)


def test_the_camera_stays_inside_the_yard():
    """The camera never shows past the yard's edges."""
    scene = neighborhood()

    assert scene.camera.bounds == (0, 0, YARD_WIDTH - SCREEN_WIDTH, YARD_HEIGHT - SCREEN_HEIGHT)


def test_a_lower_kid_is_drawn_in_front():
    """Kids are drawn in order of their feet: lower on the screen is in front."""
    scene = neighborhood(JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(5)))
    dex, marisol = scene.kids[0], scene.kids[1]

    hold(pads={5: (0, FULL)})
    run(scene, seconds=0.5)

    assert marisol.world_y > dex.world_y
    assert scene.all_sprites.get_layer_of_sprite(marisol) > scene.all_sprites.get_layer_of_sprite(
        dex
    )


def test_unplugging_a_pad_removes_its_kid():
    """A pad unplugged in the neighborhood takes its kid with it and frees its slot."""
    with support.running_game(scene_class=NeighborhoodScene, plugged_in_at_start=False) as (
        engine,
        scene,
    ):
        assert isinstance(scene, NeighborhoodScene)
        support.plug_in_the_pad(engine)
        pad = gamepad(STAND_IN_PAD.instance_id)
        scene.roster = scene.roster.join(device=pad)
        scene.add_missing_kids()
        marisol = scene.kids[1]

        support.unplug_the_pad(engine)

        assert support.joined_devices(scene) == [KEYBOARD, None, None, None]
        assert 1 not in scene.kids
        assert not marisol.alive()


def test_unplugging_the_last_player_returns_to_the_title():
    """With nobody left, the neighborhood goes back to the title."""
    with support.running_game(scene_class=NeighborhoodScene, plugged_in_at_start=False) as (
        engine,
        scene,
    ):
        assert isinstance(scene, NeighborhoodScene)
        support.plug_in_the_pad(engine)
        scene.roster = JoinRoster.empty().join(device=gamepad(STAND_IN_PAD.instance_id))

        support.unplug_the_pad(engine)

        assert isinstance(scene.next_scene, TitleScene)


@pytest.mark.parametrize('key', [pygame.K_p, pygame.K_RETURN])
def test_p_or_start_pauses(key):
    """P pauses, and so does start (Enter, or a pad's START)."""
    scene = neighborhood()

    support.press_key(scene, key)

    assert isinstance(scene.next_scene, PauseScene)


def test_a_pads_start_pauses():
    """A joined pad's START pauses the game too."""
    scene = neighborhood(JoinRoster.empty().join(device=gamepad(5)))

    support.controller_start(scene, instance_id=5)

    assert isinstance(scene.next_scene, PauseScene)


def test_the_yard_is_lawn_not_black():
    """The yard shows its lawn (never the black of nothing drawn)."""
    scene = neighborhood()

    screen = support.rendered(scene)

    lawn_pixels = support.exact_colour_count(screen, screen.get_rect(), LAWN_COLOUR)
    assert lawn_pixels > SCREEN_WIDTH * SCREEN_HEIGHT // 4


def test_replay_arguments_rebuild_the_neighborhood_through_json():
    """A replay rebuilds the scene with the same players."""
    roster = four_players()
    scene = NeighborhoodScene(options=dict(OPTIONS), roster=roster)

    rebuilt = NeighborhoodScene(
        options=dict(OPTIONS), **json.loads(json.dumps(scene.replay_arguments()))
    )

    assert rebuilt.roster == roster


def test_unused_pad_events_are_handled():
    """Sticks and hats on the neighborhood raise nothing, even with unhandled events on."""
    from glitchygames.events.base import HashableEvent

    scene = neighborhood()

    scene.on_controller_axis_motion_event(
        HashableEvent(pygame.CONTROLLERAXISMOTION, instance_id=2, axis=0, value=1000)
    )
    scene.on_joy_hat_motion_event(
        HashableEvent(pygame.JOYHATMOTION, instance_id=1, joy=1, hat=0, value=(1, 0))
    )


def test_the_yard_is_a_checkerboard_with_a_hedge_round_its_edge():
    """The yard's layer: a two-tone checkerboard, and the hedge where the yard ends.

    The checkerboard changes both across and down, so walking either way shows.
    """
    from zombies_aint_my_neighbors.neighborhood import (
        HEDGE_COLOUR,
        HEDGE_THICKNESS,
        LAWN_CHECKER_COLOUR,
        LAWN_CHECKER_SIZE,
        draw_yard,
    )

    def colour(surface: pygame.Surface, x: int, y: int) -> tuple[int, ...]:
        return tuple(surface.get_at((x, y)))[:3]

    at_the_corner = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    draw_yard(at_the_corner, 0.0, 0.0)
    middle_of = LAWN_CHECKER_SIZE // 2

    assert colour(at_the_corner, HEDGE_THICKNESS // 2, 200) == HEDGE_COLOUR
    assert colour(at_the_corner, 200, HEDGE_THICKNESS // 2) == HEDGE_COLOUR
    square = LAWN_CHECKER_SIZE
    assert colour(at_the_corner, square + middle_of, square + middle_of) == LAWN_COLOUR
    assert colour(at_the_corner, 2 * square + middle_of, square + middle_of) == LAWN_CHECKER_COLOUR
    assert colour(at_the_corner, square + middle_of, 2 * square + middle_of) == LAWN_CHECKER_COLOUR

    in_the_middle = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    draw_yard(in_the_middle, 400.0, 240.0)
    across = {colour(in_the_middle, x, 200) for x in range(0, SCREEN_WIDTH, 8)}
    down = {colour(in_the_middle, 200, y) for y in range(0, SCREEN_HEIGHT, 8)}
    assert across == {LAWN_COLOUR, LAWN_CHECKER_COLOUR}
    assert down == {LAWN_COLOUR, LAWN_CHECKER_COLOUR}


def test_moving_the_camera_down_moves_the_checkerboard():
    """The pattern follows the camera vertically too: a camera a square lower shows it shifted."""
    from zombies_aint_my_neighbors.neighborhood import LAWN_CHECKER_SIZE, draw_yard

    here = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    lower = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    draw_yard(here, 400.0, 240.0)
    draw_yard(lower, 400.0, 240.0 + LAWN_CHECKER_SIZE)

    assert tuple(here.get_at((200, 200))) != tuple(lower.get_at((200, 200)))


def test_resuming_after_a_pause_lays_no_second_yard():
    """Setting the scene up again (a resume) keeps its one yard layer."""
    scene = neighborhood()
    sprites_before = set(scene.all_sprites.sprites())

    scene.setup()

    assert set(scene.all_sprites.sprites()) == sprites_before


def test_with_nobody_left_the_camera_aims_at_the_middle_of_the_yard():
    """Between the last unplug and the title, the camera has no kids to follow."""
    scene = neighborhood()
    scene.kids.pop(0).kill()

    assert scene.camera_target() == (YARD_WIDTH / 2, YARD_HEIGHT / 2)


# --- Zombies and TVs (feature plan 5, Task 7) -------------------------------------------------


def test_four_tvs_stand_one_in_each_quarter_of_the_yard():
    """Each quarter of the yard holds one TV's frame."""
    scene = neighborhood()
    quarters = {
        (tv.world_x + TV_SIZE / 2 >= YARD_WIDTH / 2, tv.world_y + TV_SIZE / 2 >= YARD_HEIGHT / 2)
        for tv in scene.tvs
    }

    assert len(scene.tvs) == 4
    assert len(quarters) == 4
    for tv in scene.tvs:
        assert 0 <= tv.world_x <= YARD_WIDTH - TV_SIZE
        assert 0 <= tv.world_y <= YARD_HEIGHT - TV_SIZE


def test_no_zombie_comes_before_six_seconds_and_every_tv_has_spawned_by_ten():
    """The first waits are 6 to 9 s; each TV's zombie then pops out in front of it."""
    scene = neighborhood()

    run(scene, seconds=SPAWN_MINIMUM_SECONDS - 0.1)
    assert scene.zombies == []
    run(scene, seconds=10.0 - SPAWN_MINIMUM_SECONDS)

    assert [tv.zombies for tv in scene.tvs] == [1, 1, 1, 1]
    assert len(scene.zombies) == 4


def test_a_new_zombie_stands_at_its_tvs_spawn_point():
    """On the frame it appears, a zombie is where its TV puts it."""
    scene = neighborhood()
    spawn_points = {tv.spawn_point() for tv in scene.tvs}
    for _ in range(round(10.0 * 60)):
        before = len(scene.zombies)
        support.tick_to(scene, seconds=scene.game_time + FRAME_SECONDS)
        if len(scene.zombies) > before:
            newest = scene.zombies[-1]
            # It has had its first frame of shambling (a third of a pixel at most)
            assert any(
                abs(newest.world_x - x) <= 1 and abs(newest.world_y - y) <= 1
                for x, y in spawn_points
            )
            return
    pytest.fail('no zombie appeared in 10 s')


def test_the_caps_hold_over_a_long_game():
    """In two minutes, never more than 3 zombies from a TV, nor 10 in all."""
    scene = neighborhood(four_players())
    for _ in range(120):
        run(scene, seconds=1.0)
        assert all(tv.zombies <= ZOMBIES_PER_TV for tv in scene.tvs)
        assert len(scene.zombies) <= ZOMBIES_IN_ALL
        assert len(scene.zombies) == sum(tv.zombies for tv in scene.tvs) - sum(
            tv.is_spawning and not tv.zombie_out for tv in scene.tvs
        )

    assert len(scene.zombies) == ZOMBIES_IN_ALL


def test_a_zombie_touching_a_kid_knocks_it_out_and_grabs():
    """The core threat: one touch, a knockout and a grab."""
    scene = neighborhood()
    kid = scene.kids[0]
    zombie = scene.add_zombie(world_x=kid.world_x + 4, world_y=kid.world_y)

    support.tick_to(scene, seconds=scene.game_time + FRAME_SECONDS)

    assert kid.state is KidState.KNOCKED_OUT
    assert zombie.is_grabbing


def test_a_zombie_out_of_reach_knocks_nobody_out():
    """Not touching, nothing happens."""
    scene = neighborhood()
    kid = scene.kids[0]
    zombie = scene.add_zombie(world_x=kid.world_x + 200, world_y=kid.world_y)

    support.tick_to(scene, seconds=scene.game_time + FRAME_SECONDS)

    assert kid.state is KidState.ACTIVE
    assert not zombie.is_grabbing


def test_a_knocked_out_kid_ignores_its_player():
    """Holding right while knocked out moves the kid nowhere."""
    scene = neighborhood()
    kid = scene.kids[0]
    kid.knock_out()
    before = (kid.world_x, kid.world_y)
    hold(scancodes=(pygame.KSCAN_D,))

    run(scene, seconds=KNOCKOUT_SECONDS)

    assert (kid.world_x, kid.world_y) == before


def test_zombies_and_tvs_are_drawn_by_their_feet_with_the_kids():
    """One depth rule: each sprite's layer is the row of its feet."""
    scene = neighborhood()
    kid = scene.kids[0]
    scene.add_zombie(world_x=kid.world_x + 300, world_y=kid.world_y + 100)
    support.tick_to(scene, seconds=scene.game_time + FRAME_SECONDS)

    for sprite, height in [(tv, TV_SIZE) for tv in scene.tvs] + [
        (zombie, KID_HEIGHT) for zombie in scene.zombies
    ]:
        assert scene.all_sprites.get_layer_of_sprite(sprite) == round(sprite.world_y + height)


def test_the_same_seed_brings_the_same_zombies():
    """The spawns come from the named stream: the same engine seed, the same zombies."""
    places = []
    for _ in range(2):
        reset_streams(seed=20261114)
        scene = neighborhood()
        run(scene, seconds=10.0)
        places.append([(round(z.world_x, 3), round(z.world_y, 3)) for z in scene.zombies])

    assert places[0] == places[1]
    assert places[0]
