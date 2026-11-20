"""The neighborhood: the joined kids walk a yard larger than the screen under one camera.

Feature plan 4 (plans/2026-11-14-zombies-aint-my-neighbors-4-walking.md), Task 3. Input is the
engine's own ``InputSnapshot`` set as the frame's polled input, as the engine sets it.
"""

from __future__ import annotations

import importlib
import json
import random
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.effects.shake import ShakeTarget
from glitchygames.events.base import HashableEvent
from glitchygames.input.state import InputSnapshot, set_current_input
from glitchygames.randomness import capture_stream_states, reset_streams
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.sprites import AnimatedSprite
from glitchygames.tracing import StableSpriteIds
from tests.input.stand_in_devices import STAND_IN_PAD
from zombies_aint_my_neighbors import groans as groans_module
from zombies_aint_my_neighbors import music
from zombies_aint_my_neighbors.demo_neighborhood import (
    DEMO_PAD_INSTANCE_IDS,
    DemoNeighborhoodScene,
    demo_roster,
)
from zombies_aint_my_neighbors.exit_door import DOOR_SIZE, OPENING_SECONDS
from zombies_aint_my_neighbors.feature_card import CARD_SECONDS, FeatureCardScene
from zombies_aint_my_neighbors.game_over import GameOverScene
from zombies_aint_my_neighbors.groans import GROAN_REST_SECONDS
from zombies_aint_my_neighbors.kid import (
    KID_HEIGHT,
    KID_WIDTH,
    KNOCKOUT_SECONDS,
    Kid,
    KidFacing,
    KidState,
    Weapon,
)
from zombies_aint_my_neighbors.laser import FULL_SECONDS, WARM_UP_SECONDS
from zombies_aint_my_neighbors.neighbor import NEIGHBOR_PLACES, NeighborState
from zombies_aint_my_neighbors.neighborhood import (
    CHEER_SECONDS,
    LASER_FADE_SECONDS,
    LAWN_COLOUR,
    PAN_WIDTH,
    SCREEN_MARGIN,
    STAGE_CLEAR_FADE_SECONDS,
    WALK_SPEED,
    YARD_HEIGHT,
    YARD_WIDTH,
    NeighborhoodScene,
    pan_for,
)
from zombies_aint_my_neighbors.roster import JoinRoster
from zombies_aint_my_neighbors.run_state import NeighborKind, RunState
from zombies_aint_my_neighbors.sounds import (
    GATE,
    GROANS,
    KNOCKOUT,
    LASER_RISE,
    LASER_SHINE,
    LOSS,
    RESCUE,
    TV_BREAK,
    TV_DESTROYED,
    TV_HIT,
    TV_SPAWN,
    ZAP,
)
from zombies_aint_my_neighbors.title import TitleScene
from zombies_aint_my_neighbors.tv import (
    HITS_PER_STAGE,
    SPAWN_MINIMUM_SECONDS,
    TV_SIZE,
    ZOMBIES_IN_ALL,
    ZOMBIES_PER_TV,
    Tv,
)
from zombies_aint_my_neighbors.tv import STAGES as TV_STAGES
from zombies_aint_my_neighbors.zap import Zap
from zombies_aint_my_neighbors.zombie import Zombie

if TYPE_CHECKING:
    from zombies_aint_my_neighbors.sprite_kit import SpriteKit

support = importlib.import_module('src.games.zombies-aint-my-neighbors.tests.screen_support')
regressed_seeds = importlib.import_module(
    'src.games.zombies-aint-my-neighbors.tests.regressed_seeds'
)
seed_cases = regressed_seeds.seed_cases
resolve_seed = regressed_seeds.resolve_seed
failure_note = regressed_seeds.failure_note
KEYBOARD = support.KEYBOARD
gamepad = support.gamepad
OPTIONS = {'input_mode': 'auto', 'no_unhandled_events': True}
FRAME_SECONDS = 1.0 / 60.0
SCREEN_WIDTH, SCREEN_HEIGHT = support.SCREEN_SIZE
FULL = 32767
# Controller-layer button tuples are indexed by CONTROLLER_BUTTON_* id
CONTROLLER_BUTTON_COUNT = 21


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

    A kid gone for the stage (out of lives and faded: hidden) is not in the group (feature
    plan 7); a kid still fading on the ground is.

    Returns:
        (width, height).

    """
    kids = [kid for kid in scene.kids.values() if kid.state is not KidState.OUT]
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


@pytest.mark.parametrize(
    ('players', 'seed_case'),
    [
        (players, case)
        for players in (2, 3, 4)
        for case in seed_cases(
            test='test_the_group_always_fits_on_the_screen', vector=f'players-{players}'
        )
    ],
)
def test_the_group_always_fits_on_the_screen(players, seed_case, request):
    """However the players wander, the group never spans more than the screen less its margins.

    The streams' seed decides when zombies come and whom they knock out of their last life, so
    the test runs a fresh seed and every seed that once failed it (seeds 1, 3 and 5 broke the
    span with four players before feature plan 7's fix: an out kid left the span too early).
    """
    seed = resolve_seed(
        seed_case,
        node=request.node,
        test='test_the_group_always_fits_on_the_screen',
        vector=f'players-{players}',
    )
    reset_streams(seed=seed)
    note = failure_note(
        test='test_the_group_always_fits_on_the_screen', vector=f'players-{players}', seed=seed
    )
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
            assert width <= limit_width + 1e-6, note
            assert height <= limit_height + 1e-6, note


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
        assert not scene.next_scene.opening


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


def test_a_pads_start_on_the_joystick_layer_pauses():
    """On the joystick layer too: a button other than Y goes on to every screen's handling."""
    scene = neighborhood(JoinRoster.empty().join(device=gamepad(5)))

    support.joystick_start(scene, instance_id=5)

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


# The Channel Changer in the yard (feature plan 6)


def hold_fire(*, scancodes=(), pads_firing=()) -> None:
    """Make this frame's polled input hold keys and the A button of some pads (sticks centred).

    Args:
        scancodes: The keys held.
        pads_firing: Instance ids of pads holding A, on the controller layer.

    """
    pressed_a = tuple(
        button == pygame.CONTROLLER_BUTTON_A for button in range(CONTROLLER_BUTTON_COUNT)
    )
    set_current_input(
        snapshot=InputSnapshot(
            pressed_scancodes=frozenset(scancodes),
            modifiers=0,
            mouse_position=(0, 0),
            mouse_buttons=(False, False, False),
            mouse_focused=True,
            controller_axes=dict.fromkeys(pads_firing, (0, 0, 0, 0, 0, 0)),
            controller_buttons=dict.fromkeys(pads_firing, pressed_a),
        )
    )


def face(kid: Kid, facing: KidFacing) -> None:
    """Turn a kid to a facing, standing still."""
    kid.facing = facing
    kid.moving = False


def test_holding_j_fires_zaps_from_the_kids_remote_its_way():
    """Two zaps in half a second (0.25 s apart), flying the kid's aim."""
    scene = neighborhood()
    dex = scene.kids[0]
    face(dex, KidFacing.LEFT)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=0.5)

    assert len(scene.zaps) == 2
    assert all(zap.direction == (-1.0, 0.0) for zap in scene.zaps)


def test_a_pad_fires_for_its_own_kid():
    """A on pad 1 fires Marisol's remote, not Dex's."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(1))
    scene = neighborhood(roster)
    marisol = scene.kids[1]
    face(marisol, KidFacing.DOWN)
    hold_fire(pads_firing=(1,))

    run(scene, seconds=FRAME_SECONDS)

    assert len(scene.zaps) == 1
    assert scene.zap_owners[scene.zaps[0]] == 1


def test_a_zap_kills_a_zombie_in_its_path_and_is_spent():
    """Dex fires left at a zombie beside him: it crumbles and the zap is gone."""
    scene = neighborhood()
    dex = scene.kids[0]
    face(dex, KidFacing.LEFT)
    zombie = scene.add_zombie(world_x=dex.world_x - 70, world_y=dex.world_y)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.25)

    assert zombie.is_dying
    assert scene.zaps == []


def test_a_zapped_zombie_frees_its_tvs_place_at_once():
    """The caps count living zombies: a crumbling one no longer counts."""
    scene = neighborhood()
    dex = scene.kids[0]
    face(dex, KidFacing.LEFT)
    tv = scene.tvs[0]
    tv.zombies = 1
    zombie = scene.add_zombie(world_x=dex.world_x - 70, world_y=dex.world_y, home=tv)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.25)

    assert zombie.is_dying
    assert tv.zombies == 0


def test_a_crumbled_zombie_leaves_the_yard():
    """After its crumble and fade it is out of the scene's zombies, hidden, back in its pool."""
    scene = neighborhood()
    zombie = scene.add_zombie(world_x=100.0, world_y=100.0)
    zombie.zap()

    run(scene, seconds=1.1)

    assert zombie not in scene.zombies
    assert zombie.hidden
    assert scene.zombie_pool.given_back == 1


def test_a_zap_that_fizzles_out_leaves_the_yard():
    """A zap at nothing flies its range, fizzles, and is gone: hidden, back in its pool."""
    scene = neighborhood()
    face(scene.kids[0], KidFacing.LEFT)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()
    (zap,) = scene.zaps

    run(scene, seconds=1.0)

    assert scene.zaps == []
    assert zap.hidden
    assert scene.zap_owners == {}
    assert scene.zap_pool.given_back == 1


def test_zaps_pass_through_kids():
    """Dex fires down through Marisol: she stays standing and the zap flies on."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(1))
    scene = neighborhood(roster)
    dex, marisol = scene.kids[0], scene.kids[1]
    marisol.world_x, marisol.world_y = dex.world_x, dex.world_y + 40
    face(dex, KidFacing.DOWN)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.2)

    assert marisol.state is KidState.ACTIVE
    assert len(scene.zaps) == 1
    assert scene.zaps[0].is_live


def kid_under_a_tv(scene: NeighborhoodScene) -> tuple[Kid, Tv]:
    """Put Dex just below the first TV, facing up at it.

    Returns:
        (Dex, the TV).

    """
    dex, tv = scene.kids[0], scene.tvs[0]
    dex.world_x = tv.world_x + (TV_SIZE - KID_WIDTH) / 2
    dex.world_y = tv.world_y + TV_SIZE + 12
    face(dex, KidFacing.UP)
    return dex, tv


def test_nine_zaps_destroy_a_tv():
    """Holding fire at a TV for 2.25 s (9 zaps at 4 a second) destroys it."""
    scene = neighborhood()
    scene.shake = lambda *arguments, **keywords: None
    _dex, tv = kid_under_a_tv(scene)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=2.0)
    assert tv.stage == 'smashed'
    run(scene, seconds=0.5)

    assert tv.is_destroyed


def test_a_destroyed_tv_takes_no_more_zaps():
    """Zaps fly through a destroyed TV."""
    scene = neighborhood()
    scene.shake = lambda *arguments, **keywords: None
    _dex, tv = kid_under_a_tv(scene)
    tv.hits = 9
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.3)

    assert tv.hits == 9
    assert len(scene.zaps) == 1
    assert scene.zaps[0].is_live


def test_destroying_a_tv_shakes_the_world_and_rumbles_the_destroying_pad(mocker):
    """One short world shake, and a rumble on the pad whose kid fired the last zap."""
    roster = JoinRoster.empty().join(device=gamepad(1))
    scene = neighborhood(roster)
    shake = mocker.patch.object(scene, 'shake')
    pad = mocker.Mock()
    devices = mocker.Mock()
    devices.get.return_value = pad
    mocker.patch.object(
        NeighborhoodScene, 'input_devices', new_callable=mocker.PropertyMock, return_value=devices
    )
    # The only player, on pad 1, holds slot 0
    dex = scene.kids[0]
    tv = scene.tvs[0]
    dex.world_x = tv.world_x + (TV_SIZE - KID_WIDTH) / 2
    dex.world_y = tv.world_y + TV_SIZE + 12
    face(dex, KidFacing.UP)
    tv.hits = 8
    hold_fire(pads_firing=(1,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.3)

    assert tv.is_destroyed
    shake.assert_called_once()
    assert shake.call_args.kwargs['targets'] == ShakeTarget.WORLD
    devices.get.assert_called_with(instance_id=1)
    pad.rumble.assert_called_once()


def test_destroying_a_tv_from_a_pad_that_has_gone_rumbles_nothing(mocker):
    """The pad whose zap destroyed the TV was unplugged that frame: the shake alone."""
    scene = neighborhood(JoinRoster.empty().join(device=gamepad(1)))
    shake = mocker.patch.object(scene, 'shake')
    devices = mocker.Mock()
    devices.get.return_value = None
    mocker.patch.object(
        NeighborhoodScene, 'input_devices', new_callable=mocker.PropertyMock, return_value=devices
    )
    dex, tv = kid_under_a_tv(scene)
    tv.hits = 8
    hold_fire(pads_firing=(1,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.3)

    assert tv.is_destroyed
    assert dex.state is KidState.ACTIVE
    shake.assert_called_once()
    devices.get.assert_called_with(instance_id=1)


def test_destroying_a_tv_from_the_keyboard_rumbles_nothing(mocker):
    """The keyboard has no motors: the shake alone."""
    scene = neighborhood()
    shake = mocker.patch.object(scene, 'shake')
    devices = mocker.Mock()
    mocker.patch.object(
        NeighborhoodScene, 'input_devices', new_callable=mocker.PropertyMock, return_value=devices
    )
    _dex, tv = kid_under_a_tv(scene)
    tv.hits = 8
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=FRAME_SECONDS)
    hold_fire()

    run(scene, seconds=0.3)

    shake.assert_called_once()
    devices.get.assert_not_called()


@pytest.mark.parametrize(('facing', 'in_front'), [(KidFacing.DOWN, True), (KidFacing.UP, False)])
def test_the_remote_is_layered_against_its_kid(facing, in_front):
    """Just in front of the kid's layer, except facing up, when it is just behind."""
    scene = neighborhood()
    dex = scene.kids[0]
    face(dex, facing)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=FRAME_SECONDS)

    remote_layer = scene.all_sprites.get_layer_of_sprite(dex.remote)
    kid_layer = scene.all_sprites.get_layer_of_sprite(dex)
    assert remote_layer == kid_layer + (1 if in_front else -1)


def busy_yard() -> NeighborhoodScene:
    """Return four kids facing four ways, their one neighbor already saved.

    With no neighbor left standing the zombies come for the kids, into their fire (feature plan
    7: zombies chase the nearest kid or neighbor).

    Returns:
        The scene.

    """
    run_state = RunState.new_run().model_copy(update={'neighbors': (NeighborKind.PIZZA_TEEN,)})
    scene = NeighborhoodScene(options=dict(OPTIONS), roster=four_players(), run=run_state)
    scene.setup()
    scene.shake = lambda *arguments, **keywords: None
    dex = scene.kids[0]
    home = (dex.world_x, dex.world_y)
    dex.world_x, dex.world_y = scene.neighbors[0].world_x, scene.neighbors[0].world_y
    run(scene, seconds=FRAME_SECONDS)
    dex.world_x, dex.world_y = home
    assert scene.rescued == [NeighborKind.PIZZA_TEEN]
    for kid, facing in zip(scene.kids.values(), KidFacing, strict=False):
        face(kid, facing)
    return scene


def test_everything_the_scene_tracks_is_in_its_sprites_through_a_busy_game():
    """Whatever the scene tracks is drawn, and every zombie or zap shown is one it tracks.

    Twenty seconds of four kids firing every way: zombies spawn, die and fade; zaps fly, strike
    and fizzle; TVs break.
    """
    scene = busy_yard()
    hold_fire(scancodes=(pygame.KSCAN_J,), pads_firing=(1, 2, 3))

    for _ in range(round(20.0 / FRAME_SECONDS)):
        run(scene, seconds=FRAME_SECONDS)
        tracked = {*scene.zombies, *scene.zaps, *scene.kids.values(), *scene.tvs}
        tracked |= {kid.remote for kid in scene.kids.values()}
        assert tracked <= set(scene.all_sprites)
        assert set(scene.zap_owners) == set(scene.zaps)
        assert set(scene.zombie_homes) <= set(scene.zombies)
    # Idle ones wait hidden in the scene's group for their pools (never removed: a removed
    # sprite must not be held, tests/replay/test_removed_sprites_are_freed.py)
    shown = {
        sprite
        for sprite in scene.all_sprites
        if isinstance(sprite, (Zombie, Zap)) and not sprite.hidden
    }
    assert shown <= {*scene.zombies, *scene.zaps}
    assert all(sprite.alive() for sprite in (*scene.zombies, *scene.zaps))


def test_no_sprite_file_loads_during_play(mocker):
    """Zombies and zaps come from pools built before play: twenty busy seconds load nothing."""
    scene = busy_yard()
    loads = mocker.spy(AnimatedSprite, '__init__')
    hold_fire(scancodes=(pygame.KSCAN_J,), pads_firing=(1, 2, 3))

    run(scene, seconds=20.0)

    assert loads.call_count == 0
    # The run did reuse: zombies and zaps were taken from their pools and given back
    assert scene.zombie_pool.given_back > 0
    assert scene.zap_pool.given_back > scene.zap_pool.size


# Neighbors, lives and the stage's end (feature plan 7)


def neighbors_stage(*, neighbors=None, roster=None) -> NeighborhoodScene:
    """Return the neighborhood for a run with these neighbors (stage 1's 8 when None).

    Returns:
        The scene, set up.

    """
    run = RunState.new_run()
    if neighbors is not None:
        run = run.model_copy(update={'neighbors': tuple(neighbors)})
    scene = NeighborhoodScene(options=dict(OPTIONS), roster=roster, run=run)
    scene.setup()
    scene.shake = lambda *arguments, **keywords: None
    return scene


def stand_on(sprite, target) -> None:
    """Put a sprite's frame where a target's is."""
    sprite.world_x, sprite.world_y = target.world_x, target.world_y


def test_stage_1_has_its_8_neighbors_at_distinct_places_by_turns():
    """The run's neighbors, each at one of the 12 places, none twice."""
    scene = neighbors_stage()

    assert [neighbor.kind for neighbor in scene.neighbors] == list(RunState.new_run().neighbors)
    places = {(neighbor.world_x, neighbor.world_y) for neighbor in scene.neighbors}
    assert len(places) == 8
    assert places <= {(float(x), float(y)) for x, y in NEIGHBOR_PLACES}


def test_a_later_stage_has_only_its_runs_neighbors():
    """Stage 2 with the two saved: two neighbors."""
    scene = neighbors_stage(neighbors=(NeighborKind.LAWN_CHAIR_READER, NeighborKind.PIZZA_TEEN))

    assert [neighbor.kind for neighbor in scene.neighbors] == [
        NeighborKind.LAWN_CHAIR_READER,
        NeighborKind.PIZZA_TEEN,
    ]


def test_a_kid_touching_a_neighbor_rescues_them():
    """Dex walks into the first neighbor: saved, and counted."""
    scene = neighbors_stage()
    neighbor = scene.neighbors[0]
    stand_on(scene.kids[0], neighbor)

    run(scene, seconds=FRAME_SECONDS)

    assert neighbor.state is NeighborState.SAVED
    assert scene.rescued == [neighbor.kind]


def test_a_zombie_touching_a_neighbor_loses_them_and_grabs():
    """The zombie reaches the neighbor first: lost, and the zombie lunges."""
    scene = neighbors_stage()
    neighbor = scene.neighbors[0]
    zombie = scene.add_zombie(world_x=neighbor.world_x, world_y=neighbor.world_y)

    run(scene, seconds=FRAME_SECONDS)

    assert neighbor.state is NeighborState.LOST
    assert zombie.is_grabbing
    assert scene.rescued == []


def test_a_kid_and_a_zombie_reaching_a_neighbor_together_rescue_them():
    """Kids are checked first: a tie goes to the kid."""
    scene = neighbors_stage()
    neighbor = scene.neighbors[0]
    stand_on(scene.kids[0], neighbor)
    scene.add_zombie(world_x=neighbor.world_x, world_y=neighbor.world_y)

    run(scene, seconds=FRAME_SECONDS)

    assert neighbor.state is NeighborState.SAVED


def test_zombies_chase_a_nearer_neighbor_over_a_kid():
    """A zombie beside a neighbor and far from the kids goes for the neighbor."""
    scene = neighbors_stage()
    neighbor = scene.neighbors[0]
    zombie = scene.add_zombie(world_x=neighbor.world_x + 60, world_y=neighbor.world_y)

    run(scene, seconds=0.5)

    assert zombie.world_x < neighbor.world_x + 60


def test_a_knockout_costs_a_life():
    """Three lives; one zombie touch leaves two."""
    scene = neighbors_stage()
    dex = scene.kids[0]
    scene.add_zombie(world_x=dex.world_x, world_y=dex.world_y)

    run(scene, seconds=FRAME_SECONDS)

    assert scene.run.lives[0] == 2
    assert dex.state is KidState.KNOCKED_OUT


def test_a_knockout_on_the_last_life_puts_the_kid_out():
    """With one life left, the kid falls and stays down."""
    scene = neighbors_stage()
    scene.run = scene.run.lose_life(slot_index=0).lose_life(slot_index=0)
    dex = scene.kids[0]
    scene.add_zombie(world_x=dex.world_x, world_y=dex.world_y)

    run(scene, seconds=FRAME_SECONDS)
    run(scene, seconds=KNOCKOUT_SECONDS + 0.1)

    assert scene.run.lives[0] == 0
    assert dex.is_out


def test_an_out_kid_leaves_the_camera_and_the_group_to_the_others():
    """The camera aims at the kids still in."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(1))
    scene = neighbors_stage(roster=roster)
    dex, marisol = scene.kids[0], scene.kids[1]
    dex.knock_out(last_life=True)
    run(scene, seconds=KNOCKOUT_SECONDS + 1.1)

    centre_x, centre_y = scene.camera_target()

    assert (centre_x, centre_y) == (
        marisol.world_x + KID_WIDTH / 2,
        marisol.world_y + KID_HEIGHT / 2,
    )


def test_everyone_out_is_game_over():
    """The last joined kid out of lives: the game over follows its fade."""
    scene = neighbors_stage()
    scene.run = scene.run.lose_life(slot_index=0).lose_life(slot_index=0)
    dex = scene.kids[0]
    scene.add_zombie(world_x=dex.world_x, world_y=dex.world_y)

    run(scene, seconds=KNOCKOUT_SECONDS + 1.2)

    assert isinstance(scene.next_scene, GameOverScene)


def test_the_door_stays_shut_while_any_neighbor_stands():
    """One saved, the rest still standing: the door is closed."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER))
    stand_on(scene.kids[0], scene.neighbors[0])

    run(scene, seconds=0.5)

    assert not scene.exit_door.is_open


def test_the_door_opens_when_nobody_stands_and_someone_was_rescued():
    """One saved and one lost: the door opens."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER))
    stand_on(scene.kids[0], scene.neighbors[0])
    scene.neighbors[1].lose()

    run(scene, seconds=0.5)

    assert scene.exit_door.is_open


def test_every_neighbor_lost_is_game_over_never_an_exit():
    """Nobody saved: no next stage."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    scene.neighbors[0].lose()

    run(scene, seconds=0.5)

    assert not scene.exit_door.is_open
    assert isinstance(scene.next_scene, GameOverScene)


def clear_the_yard(scene: NeighborhoodScene) -> None:
    """Save every neighbor with Dex, then let the effects finish."""
    for neighbor in scene.neighbors:
        stand_on(scene.kids[0], neighbor)
        run(scene, seconds=FRAME_SECONDS)
    run(scene, seconds=0.5)


def test_a_kid_through_the_open_door_clears_the_stage_and_cheers():
    """Through the door: every kid still in cheers, and the zombies stop."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    clear_the_yard(scene)
    zombie = scene.add_zombie(world_x=100.0, world_y=600.0)
    stand_on(scene.kids[0], scene.exit_door)
    scene.kids[0].world_y += 8

    run(scene, seconds=FRAME_SECONDS * 2)
    where = (zombie.world_x, zombie.world_y)
    run(scene, seconds=0.5)

    assert scene.stage_cleared
    assert scene.kids[0].current_animation == 'cheer'
    assert (zombie.world_x, zombie.world_y) == where


def test_the_kids_cheer_on_the_frame_the_stage_clears():
    """The clear's frame already shows the cheer: the kids are posed again after the gate.

    The kids are posed before the gate is checked, so the kid through it showed its walk for
    the clear's first frame (seen triaging the knocked-out kid's cheer, 2026-11-19).
    """
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    clear_the_yard(scene)
    run(scene, seconds=OPENING_SECONDS + 0.1)
    dex = scene.kids[0]
    stand_on(dex, scene.exit_door)
    dex.world_y += 8

    while not scene.stage_cleared:
        run(scene, seconds=FRAME_SECONDS)

    assert dex.current_animation == 'cheer'
    assert dex.current_frame == 0


def test_after_the_cheer_the_card_brings_the_next_stage_with_the_rescued():
    """1.5 s of cheering, then the card for stage 2 carrying only the neighbors saved."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER))
    stand_on(scene.kids[0], scene.neighbors[1])
    run(scene, seconds=FRAME_SECONDS)
    scene.neighbors[0].lose()
    run(scene, seconds=0.5)
    stand_on(scene.kids[0], scene.exit_door)
    scene.kids[0].world_y += 8

    # The gate swings fully open first (it must be seen to open), then the cheer
    run(scene, seconds=OPENING_SECONDS + CHEER_SECONDS + 0.1)

    card = scene.next_scene
    assert isinstance(card, FeatureCardScene)
    assert card.run.stage == 2
    assert card.run.neighbors == (NeighborKind.LAWN_CHAIR_READER,)
    # The stage's sprite kit goes on to the next card, with whatever it holds (feature plan 9)
    assert card.kit is scene.kit


@pytest.mark.parametrize(
    ('knocked_out_before_the_clear', 'cheers'),
    [(0.0, False), (0.5, True), (1.0, True), (1.5, True)],
)
def test_a_kid_knocked_out_at_the_clear_cheers_when_it_gets_up(
    knocked_out_before_the_clear, cheers
):
    """P2 is down as Dex clears the stage: it gets up into the cheer, never standing idle.

    The knockout (1.9 s) outlasts the cheer (1.5 s), so a kid knocked out as the stage clears is
    still down when the card comes; one knocked out earlier gets up during the cheer and cheers.
    Before the fix it stood idle (feature plan 7's deferred Minor).
    """
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(1))
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,), roster=roster)
    clear_the_yard(scene)
    run(scene, seconds=OPENING_SECONDS + 0.1)
    dex, other = scene.kids[0], scene.kids[1]
    # Beside the gate, so keeping the group together leaves Dex at it
    other.world_x = scene.exit_door.world_x + 96
    other.world_y = scene.exit_door.world_y + 40
    other.knock_out(last_life=False)
    run(scene, seconds=knocked_out_before_the_clear)
    stand_on(dex, scene.exit_door)
    dex.world_y += 8

    animations_while_cheering = []
    while scene.next_scene is None:
        run(scene, seconds=FRAME_SECONDS)
        if scene.stage_cleared:
            animations_while_cheering.append(other.current_animation)

    assert isinstance(scene.next_scene, FeatureCardScene)
    assert not any(name.startswith('idle') for name in animations_while_cheering)
    assert (animations_while_cheering[-1] == 'cheer') is cheers


def test_a_closed_door_lets_nobody_through():
    """Touching the shut gate does nothing."""
    scene = neighbors_stage()
    stand_on(scene.kids[0], scene.exit_door)
    scene.kids[0].world_y += 8

    run(scene, seconds=0.2)

    assert not scene.stage_cleared


def test_the_neighborhood_rebuilds_its_stage_from_its_replay_arguments():
    """A replay starting on stage 2 gets the same run back through JSON."""
    run_state = RunState.new_run().next_stage(rescued=(NeighborKind.PIZZA_TEEN,))
    scene = NeighborhoodScene(options=dict(OPTIONS), run=run_state)

    arguments = json.loads(json.dumps(scene.replay_arguments()))
    rebuilt = NeighborhoodScene(options=dict(OPTIONS), **arguments)

    assert rebuilt.run == run_state


# The heads-up display (feature plan 7)


def test_the_hud_shows_each_joined_players_lives_and_hides_free_slots():
    """P1 and three lives for the keyboard player; the three free slots show nothing."""
    scene = neighbors_stage()

    assert scene.hud.lives_text(slot_index=0) == 'P1 \N{MULTIPLICATION SIGN}3'
    assert scene.hud.lives_picture(slot_index=0).visible
    for slot_index in (1, 2, 3):
        assert not scene.hud.lives_picture(slot_index=slot_index).visible


def test_the_hud_counts_down_lives_and_shows_a_player_out():
    """A knockout leaves two lives; the last life lost reads OUT."""
    scene = neighbors_stage()
    dex = scene.kids[0]
    scene.add_zombie(world_x=dex.world_x, world_y=dex.world_y)
    run(scene, seconds=FRAME_SECONDS)

    assert scene.hud.lives_text(slot_index=0) == 'P1 \N{MULTIPLICATION SIGN}2'
    scene.run = scene.run.lose_life(slot_index=0).lose_life(slot_index=0)
    run(scene, seconds=FRAME_SECONDS)
    assert scene.hud.lives_text(slot_index=0) == 'P1 OUT'


def test_the_hud_shows_the_stage_and_the_neighbors_rescued():
    """STAGE 1 and NEIGHBORS 0/8; a rescue makes it 1/8."""
    scene = neighbors_stage()
    assert scene.hud.status_text == 'STAGE 1   NEIGHBORS 0/8'

    stand_on(scene.kids[0], scene.neighbors[0])
    run(scene, seconds=FRAME_SECONDS)

    assert scene.hud.status_text == 'STAGE 1   NEIGHBORS 1/8'


def test_the_hud_is_drawn_over_the_yard_and_stays_put():
    """Above every world sprite, in screen space: the camera moving leaves it where it is."""
    scene = neighbors_stage()
    picture = scene.hud.lives_picture(slot_index=0)
    where = picture.rect.copy()
    world_layers = [
        scene.all_sprites.get_layer_of_sprite(sprite)
        for sprite in scene.all_sprites
        if getattr(sprite, 'COORDINATE_SPACE', None) is not None
        and sprite.COORDINATE_SPACE.name == 'WORLD'
    ]

    scene.kids[0].world_x += 400
    run(scene, seconds=0.5)

    assert scene.all_sprites.get_layer_of_sprite(picture) > max(world_layers)
    assert picture.rect == where


def test_a_rescue_or_loss_plays_in_front_of_whoever_caused_it():
    """The effect is drawn over the kid or zombie standing on the neighbor, not hidden behind."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER))
    rescued, lost = scene.neighbors
    dex = scene.kids[0]
    stand_on(dex, rescued)
    zombie = scene.add_zombie(world_x=lost.world_x, world_y=lost.world_y)

    run(scene, seconds=FRAME_SECONDS)

    layer = scene.all_sprites.get_layer_of_sprite
    assert rescued.effect is not None
    assert lost.effect is not None
    assert layer(rescued.effect) > layer(dex)
    assert layer(lost.effect) > layer(zombie)


def test_a_kid_waiting_at_the_gate_leaves_only_once_it_has_swung_open():
    """The door must be seen to open: no clearing on a gate still drawn shut or swinging."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER))
    dex = scene.kids[0]
    stand_on(dex, scene.neighbors[0])
    run(scene, seconds=FRAME_SECONDS)
    stand_on(dex, scene.exit_door)
    dex.world_y += 8
    scene.neighbors[1].lose()
    door_when_cleared = None

    for _ in range(90):
        run(scene, seconds=FRAME_SECONDS)
        if scene.stage_cleared:
            door_when_cleared = scene.exit_door.current_animation
            break

    assert door_when_cleared == 'open'


# Switching weapons (feature plan 8): K on the keyboard, Y on a pad (both layers, Y's number)


def pad_button(scene: NeighborhoodScene, *, instance_id: int, button: int, joystick: bool) -> None:
    """Press a pad button on the controller layer, or the joystick layer."""
    if joystick:
        scene.on_joy_button_down_event(
            HashableEvent(
                pygame.JOYBUTTONDOWN, instance_id=instance_id, joy=instance_id, button=button
            )
        )
    else:
        scene.on_controller_button_down_event(
            HashableEvent(pygame.CONTROLLERBUTTONDOWN, instance_id=instance_id, button=button)
        )


def test_k_switches_the_keyboard_players_weapon_and_back():
    """The Channel Changer to the laser pointer, and back."""
    scene = neighborhood()
    dex = scene.kids[0]
    assert dex.weapon is Weapon.CHANNEL_CHANGER

    support.press_key(scene, pygame.K_k)
    assert dex.weapon is Weapon.LASER_POINTER
    support.press_key(scene, pygame.K_k)
    assert dex.weapon is Weapon.CHANNEL_CHANGER


@pytest.mark.parametrize('joystick', [False, True])
def test_a_pads_y_switches_its_own_kids_weapon_only(joystick):
    """Y on pad 1 switches Marisol's weapon; Dex keeps his."""
    roster = JoinRoster.empty().join(device=KEYBOARD).join(device=gamepad(1))
    scene = neighborhood(roster)

    pad_button(scene, instance_id=1, button=pygame.CONTROLLER_BUTTON_Y, joystick=joystick)

    assert scene.kids[1].weapon is Weapon.LASER_POINTER
    assert scene.kids[0].weapon is Weapon.CHANNEL_CHANGER


def test_a_pad_nobody_holds_switches_nothing():
    """A pad not joined has no kid to switch."""
    scene = neighborhood()

    pad_button(scene, instance_id=7, button=pygame.CONTROLLER_BUTTON_Y, joystick=False)

    assert scene.kids[0].weapon is Weapon.CHANNEL_CHANGER


# The lure in the yard (feature plan 8)


def laser_ready(scene: NeighborhoodScene, kid: Kid, facing: KidFacing) -> None:
    """Give a kid the laser pointer, facing a way, standing."""
    kid.switch_weapon()
    face(kid, facing)


@pytest.mark.parametrize('seed_case', seed_cases(test='test_a_laser_pulls_a_zombie_off_a_neighbor'))
def test_a_laser_pulls_a_zombie_off_a_neighbor(seed_case, request):
    """A laser pulls a zombie off a neighbor it would otherwise reach.

    Wherever the neighbor is drawn (the seed decides), Dex stands 260 px to whichever side has
    room, a zombie 60 px from the neighbor between them: unlured it would reach the neighbor in
    about a second. Dex shines his dot just past the zombie; it goes to the dot instead. (It once
    failed on seeds that put Dex outside the yard; that seed was never captured.)
    """
    seed = resolve_seed(
        seed_case, node=request.node, test='test_a_laser_pulls_a_zombie_off_a_neighbor'
    )
    reset_streams(seed=seed)
    note = failure_note(
        test='test_a_laser_pulls_a_zombie_off_a_neighbor', vector='default', seed=seed
    )
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    neighbor = scene.neighbors[0]
    room_on_the_right = neighbor.world_x + 260 + KID_WIDTH <= YARD_WIDTH
    side = 1 if room_on_the_right else -1
    dex = scene.kids[0]
    dex.world_x, dex.world_y = neighbor.world_x + side * 260, neighbor.world_y
    laser_ready(scene, dex, KidFacing.LEFT if room_on_the_right else KidFacing.RIGHT)
    zombie = scene.add_zombie(world_x=neighbor.world_x + side * 60, world_y=neighbor.world_y)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=2.5)

    assert neighbor.is_standing, note
    assert abs(zombie.world_x - neighbor.world_x) >= 60, note


def test_a_lured_zombie_still_knocks_out_a_kid_in_its_way():
    """A lured zombie still knocks out a kid it walks into.

    Unlured, the zombie would turn for the neighbor just behind it; lured by the dot past Dex,
    it walks through him, and the touch knocks him out.
    """
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    dex = scene.kids[0]
    neighbor = scene.neighbors[0]
    neighbor.world_x, neighbor.world_y = dex.world_x - 100, dex.world_y
    laser_ready(scene, dex, KidFacing.RIGHT)
    scene.add_zombie(world_x=dex.world_x - 60, world_y=dex.world_y)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=2.0)

    assert dex.state is not KidState.ACTIVE
    assert neighbor.is_standing


# The laser on the heads-up display (feature plan 8)


def test_the_hud_shows_each_players_weapon():
    """ZAP to begin; LASER after a switch; free slots show nothing."""
    scene = neighbors_stage()
    assert scene.hud.weapon_text(slot_index=0) == 'ZAP'
    assert scene.hud.weapon_picture(slot_index=0).visible
    assert not scene.hud.weapon_picture(slot_index=1).visible

    support.press_key(scene, pygame.K_k)
    run(scene, seconds=FRAME_SECONDS)

    assert scene.hud.weapon_text(slot_index=0) == 'LASER'


def test_the_hud_battery_bar_follows_the_charge_and_greys_when_dead():
    """Full; half after 1.5 s of drawing; dead after 3 s, shown grey."""
    scene = neighbors_stage()
    dex = scene.kids[0]
    dex.switch_weapon()
    assert scene.hud.battery_shown(slot_index=0) == (1.0, False)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=1.5)
    fill, dead = scene.hud.battery_shown(slot_index=0)
    assert fill == pytest.approx(0.5, abs=0.04)
    assert not dead
    run(scene, seconds=1.6)

    assert scene.hud.battery_shown(slot_index=0) == (0.0, True)
    assert not scene.hud.battery_picture(slot_index=1).visible


def test_a_zombie_lured_toward_the_yards_edge_stays_in_the_yard():
    """Dex near the top, shining up: the zombie he lures stands on the dot, wholly in the yard."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    neighbor = scene.neighbors[0]
    neighbor.world_x, neighbor.world_y = 1400.0, 800.0
    dex = scene.kids[0]
    dex.world_x, dex.world_y = 800.0, 100.0
    laser_ready(scene, dex, KidFacing.UP)
    zombie = scene.add_zombie(world_x=1000.0, world_y=40.0)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=2.9)

    assert zombie.world_y >= 0.0
    assert 0.0 <= zombie.world_x <= YARD_WIDTH - KID_WIDTH


def test_a_kid_keeps_its_weapon_into_the_next_stage_with_a_full_battery():
    """Dex clears the stage holding the laser, half its charge spent: stage 2 gives it back full."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    dex = scene.kids[0]
    stand_on(dex, scene.neighbors[0])
    run(scene, seconds=FRAME_SECONDS)
    run(scene, seconds=0.5)
    dex.switch_weapon()
    dex.battery.charge_seconds = 1.5
    stand_on(dex, scene.exit_door)
    dex.world_y += 8

    run(scene, seconds=OPENING_SECONDS + CHEER_SECONDS + 0.1)
    card = scene.next_scene
    assert isinstance(card, FeatureCardScene)
    stage_2 = NeighborhoodScene(options=dict(OPTIONS), roster=card.roster, run=card.run)

    assert stage_2.kids[0].weapon is Weapon.LASER_POINTER
    assert stage_2.kids[0].battery.charge_seconds == FULL_SECONDS


def test_a_shining_kid_knocked_out_lures_no_zombie_that_frame():
    """Two zombies: the first knocks Dex out; the second, also in the dot's reach, is not lured.

    The final review found the dot still lit for the rest of that frame.
    """
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    neighbor = scene.neighbors[0]
    neighbor.world_x, neighbor.world_y = 1400.0, 800.0
    dex = scene.kids[0]
    laser_ready(scene, dex, KidFacing.RIGHT)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=0.5)
    assert dex.laser_lit
    scene.add_zombie(world_x=dex.world_x, world_y=dex.world_y)
    dot_x, dot_y = dex.dot.centre()
    second = scene.add_zombie(world_x=dot_x - 16 + 100, world_y=dot_y - 48)
    where = second.world_x

    run(scene, seconds=FRAME_SECONDS)

    assert dex.dot.hidden
    assert second.world_x >= where


# The sprite kit (feature plan 9): a stage built ahead is the stage built at once

KIT_EQUIVALENCE_TEST = 'test_a_stage_built_from_any_kit_is_the_stage_built_without_one'
# Stage 2 with a mix of neighbors, so both kinds and their order are exercised
MIXED_STAGE_2 = RunState.new_run().next_stage(
    rescued=(NeighborKind.PIZZA_TEEN, NeighborKind.LAWN_CHAIR_READER, NeighborKind.PIZZA_TEEN)
)
# How far the card got before its stage began: at once, partway, all but its last frame
CARD_PROGRESS_SECONDS = (0.0, 0.3, 1.0, CARD_SECONDS - 0.05)


def roster_of(players: int) -> JoinRoster:
    """Return a roster of the keyboard and then pads 1 to 3, ``players`` long.

    Returns:
        The roster.

    """
    roster = JoinRoster.empty().join(device=KEYBOARD)
    for instance_id in (1, 2, 3)[: players - 1]:
        roster = roster.join(device=gamepad(instance_id))
    return roster


def built_stage(*, roster: JoinRoster, kit: SpriteKit | None, seed: int):
    """Build stage 2 from a seed and describe it as a recording and a replay would see it.

    Returns:
        Each sprite in draw order (its replay id, layer, place, hidden and, for a TV, its first
        wait), and every random stream's state after the build.

    """
    reset_streams(seed=seed)
    scene = NeighborhoodScene(options=dict(OPTIONS), roster=roster, run=MIXED_STAGE_2, kit=kit)
    sprite_ids = StableSpriteIds()
    sprites = [
        (
            sprite_ids.id_for(sprite),
            scene.all_sprites.get_layer_of_sprite(sprite),
            getattr(sprite, 'world_x', None),
            getattr(sprite, 'world_y', None),
            getattr(sprite, 'hidden', None),
            getattr(sprite, 'seconds_until_spawn', None),
        )
        for sprite in scene.all_sprites.sprites()
    ]
    return sprites, capture_stream_states()


@pytest.mark.parametrize(
    ('card_seconds', 'card_players', 'stage_players', 'seed_case'),
    [
        (card_seconds, card_players, stage_players, case)
        for card_seconds in CARD_PROGRESS_SECONDS
        for card_players, stage_players in ((1, 1), (4, 4), (4, 2))
        for case in seed_cases(
            test=KIT_EQUIVALENCE_TEST,
            vector=f'card-{card_seconds:.2f}s-players-{card_players}-to-{stage_players}',
        )
    ],
)
def test_a_stage_built_from_any_kit_is_the_stage_built_without_one(
    card_seconds, card_players, stage_players, seed_case, request
):
    """A stage built from the card's kit is the stage a replay's rebuild makes with none.

    However far the card got, and with leftovers (4 players on the card, 2 left), it has the same
    sprites in the same order, places and waits, and leaves the random streams the same
    (sprite_kit.py rules 2-4).
    """
    vector = f'card-{card_seconds:.2f}s-players-{card_players}-to-{stage_players}'
    seed = resolve_seed(seed_case, node=request.node, test=KIT_EQUIVALENCE_TEST, vector=vector)
    card = FeatureCardScene(
        options=dict(OPTIONS), roster=roster_of(card_players), run=MIXED_STAGE_2
    )
    card.setup()
    support.tick_to(card, seconds=card_seconds)

    ahead = built_stage(roster=roster_of(stage_players), kit=card.kit, seed=seed)
    at_once = built_stage(roster=roster_of(stage_players), kit=None, seed=seed)

    assert ahead == at_once, failure_note(test=KIT_EQUIVALENCE_TEST, vector=vector, seed=seed)


# The first sounds (feature plan 10)


def test_a_shot_plays_the_zap_panned_toward_the_kid(mocker):
    """Each shot plays the remote's warbly zap, panned to where the kid stands on the screen."""
    scene = neighborhood()
    dex = scene.kids[0]
    zap = mocker.spy(scene.sounds[ZAP], 'play')
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=FRAME_SECONDS)

    assert zap.call_count == 1
    assert zap.call_args.kwargs['pan'] == pytest.approx(
        pan_for(world_x=dex.world_x + KID_WIDTH / 2, camera=scene.camera, screen_width=SCREEN_WIDTH)
    )


def test_held_fire_plays_one_zap_for_every_shot(mocker):
    """A second of held fire: as many zaps heard as fired, never more."""
    scene = neighborhood()
    zap = mocker.spy(scene.sounds[ZAP], 'play')
    shots = mocker.spy(scene, 'add_zap')
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=1.0)

    assert shots.call_count > 1
    assert zap.call_count == shots.call_count


def test_the_laser_pointer_plays_no_zap(mocker):
    """Fire held with the laser pointer shines it: no zap is fired or heard."""
    scene = neighborhood()
    scene.kids[0].switch_weapon()
    zap = mocker.spy(scene.sounds[ZAP], 'play')
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=0.5)

    assert zap.call_count == 0


def screen_left(scene: NeighborhoodScene) -> float:
    """Return the world x the screen's left edge shows (the camera only shifts the world).

    Returns:
        The world x.

    """
    screen_x, _screen_y = scene.camera.world_to_screen(0.0, 0.0)
    return float(-screen_x)


@pytest.mark.parametrize(
    ('screen_fraction', 'pan'), [(0.0, -PAN_WIDTH), (0.5, 0.0), (1.0, PAN_WIDTH)]
)
def test_a_sound_pans_with_its_place_on_the_screen(screen_fraction, pan):
    """Left edge pans left, middle centres, right edge pans right, wherever the camera is."""
    scene = neighborhood()
    # Partway across the yard, so the screen's left edge is not the world's
    scene.camera.world_x = 320.0
    left = screen_left(scene)

    assert pan_for(
        world_x=left + screen_fraction * SCREEN_WIDTH,
        camera=scene.camera,
        screen_width=SCREEN_WIDTH,
    ) == pytest.approx(pan, abs=0.01)


def test_a_sound_off_the_screen_pans_no_further_than_its_edge():
    """A zombie groaning beyond the screen's edge sounds from the edge."""
    scene = neighborhood()
    scene.camera.world_x = 320.0
    left = screen_left(scene)

    assert pan_for(world_x=left - 500.0, camera=scene.camera, screen_width=SCREEN_WIDTH) == (
        pytest.approx(-PAN_WIDTH)
    )


def laser_scene(mocker):
    """Return the neighborhood with Dex holding the laser pointer, and spies on its two sounds.

    Returns:
        The scene, the rise's spy and the shine's spy.

    """
    scene = neighborhood()
    scene.kids[0].switch_weapon()
    rise = mocker.spy(scene.sounds[LASER_RISE], 'play')
    shine = mocker.spy(scene.sounds[LASER_SHINE], 'play')
    return scene, rise, shine


def test_aiming_the_laser_plays_its_rise_then_loops_its_shine(mocker):
    """The wheee rises through the warm-up; once the dot shines, its wobble loops."""
    scene, rise, shine = laser_scene(mocker)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=FRAME_SECONDS)
    assert rise.call_count == 1
    assert shine.call_count == 0
    run(scene, seconds=WARM_UP_SECONDS + 0.1)

    assert scene.kids[0].laser_lit
    assert rise.call_count == 1
    assert shine.call_count == 1
    assert shine.call_args.kwargs['loop'] is True


def stops_of(spy, sound) -> list:
    """Return the fades a handle class's ``stop`` spy saw for one playing sound.

    The engine's handles are frozen, so the spy watches their class.

    Returns:
        Each call's ``fade``.

    """
    return [call.kwargs.get('fade') for call in spy.call_args_list if call.args[0] is sound]


def shining(mocker):
    """Return the scene with Dex's dot lit, its looping shine, and a spy on handles' stop.

    Returns:
        The scene, the shine and the spy.

    """
    scene, _rise, shine = laser_scene(mocker)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=WARM_UP_SECONDS + 0.1)
    assert scene.kids[0].laser_lit
    return scene, shine.spy_return, mocker.spy(type(shine.spy_return), 'stop')


def test_letting_go_fades_the_shine_out(mocker):
    """The dot goes out with fire let go: its wobble fades."""
    scene, sound, stop = shining(mocker)
    hold_fire()

    run(scene, seconds=FRAME_SECONDS)

    assert stops_of(stop, sound) == [LASER_FADE_SECONDS]


def test_switching_weapons_fades_the_shine_out(mocker):
    """Switched to the remote mid-shine, the laser falls silent."""
    scene, sound, stop = shining(mocker)

    scene.kids[0].switch_weapon()
    run(scene, seconds=FRAME_SECONDS)

    assert stops_of(stop, sound) == [LASER_FADE_SECONDS]


def test_a_knockout_fades_the_shine_out(mocker):
    """Knocked out mid-shine, the kid's laser falls silent."""
    scene, sound, stop = shining(mocker)

    scene.kids[0].knock_out(last_life=False)
    run(scene, seconds=FRAME_SECONDS)

    assert stops_of(stop, sound) == [LASER_FADE_SECONDS]


def test_a_dead_battery_fades_the_shine_out(mocker):
    """Held until its battery dies, the laser falls silent with its dot."""
    scene, sound, stop = shining(mocker)

    run(scene, seconds=FULL_SECONDS)

    assert not scene.kids[0].laser_lit
    assert stops_of(stop, sound) == [LASER_FADE_SECONDS]


def test_a_tap_too_short_to_light_stops_its_rise(mocker):
    """Let go before the dot lights: the wheee fades and no shine starts."""
    scene, rise, shine = laser_scene(mocker)
    hold_fire(scancodes=(pygame.KSCAN_J,))
    run(scene, seconds=0.1)
    sound = rise.spy_return
    stop = mocker.spy(type(sound), 'stop')
    hold_fire()

    run(scene, seconds=FRAME_SECONDS)

    assert stops_of(stop, sound) == [LASER_FADE_SECONDS]
    assert shine.call_count == 0


def test_the_shine_follows_the_kid_across_the_screen(mocker):
    """Walking while shining, the wobble pans with the kid."""
    scene, sound, _stop = shining(mocker)
    pan = mocker.spy(type(sound), 'set_pan')
    hold_fire(scancodes=(pygame.KSCAN_J, pygame.KSCAN_D))

    run(scene, seconds=0.2)

    pans = [call.args[1] for call in pan.call_args_list if call.args[0] is sound]
    assert pans
    assert pans[-1] == pytest.approx(scene._pan_at(scene.kids[0]))
    assert pans[-1] > pans[0]


def test_an_unplugged_players_shine_stops(mocker):
    """A pad unplugged mid-shine takes its kid, and the kid's laser falls silent."""
    with support.running_game(scene_class=NeighborhoodScene, plugged_in_at_start=False) as (
        engine,
        scene,
    ):
        assert isinstance(scene, NeighborhoodScene)
        support.plug_in_the_pad(engine)
        pad = gamepad(STAND_IN_PAD.instance_id)
        scene.roster = scene.roster.join(device=pad)
        scene.add_missing_kids()
        scene.kids[1].switch_weapon()
        shine = mocker.spy(scene.sounds[LASER_SHINE], 'play')
        hold_fire(pads_firing=(STAND_IN_PAD.instance_id,))
        run(scene, seconds=WARM_UP_SECONDS + 0.1)
        assert shine.call_count == 1
        sound = shine.spy_return
        stop = mocker.spy(type(sound), 'stop')

        support.unplug_the_pad(engine)
        run(scene, seconds=FRAME_SECONDS)

        assert stops_of(stop, sound) == [LASER_FADE_SECONDS]


def groans_heard(mocker, scene: NeighborhoodScene) -> list[str]:
    """Spy on every groan the scene plays, recording each one's name in the order played.

    Returns:
        The list, filled as the scene runs.

    """
    heard: list[str] = []
    for name in GROANS:
        sound = scene.sounds[name]
        original = sound.play

        def play(*arguments, _name=name, _original=original, **keywords):
            heard.append(_name)
            return _original(*arguments, **keywords)

        mocker.patch.object(sound, 'play', side_effect=play)
    return heard


def test_a_zombie_seeing_a_kid_groans_from_where_it_stands(mocker):
    """Every chance taken (forced): a zombie that sees Dex groans once, panned to it.

    Once: it groans at the new target, not again while it keeps chasing Dex, even past its 3 s
    rest (it is 400 px off, at 40 px/s, so it never reaches him and turns to anything else).
    """
    mocker.patch.object(groans_module, 'GROAN_CHANCE', 1.0)
    scene = neighborhood()
    heard = groans_heard(mocker, scene)
    dex = scene.kids[0]
    zombie = scene.add_zombie(world_x=dex.world_x + 400.0, world_y=dex.world_y)

    run(scene, seconds=FRAME_SECONDS)
    run(scene, seconds=GROAN_REST_SECONDS + 1.0)

    assert len(heard) == 1
    played = scene.sounds[heard[0]].play
    assert played.call_args.kwargs['pan'] == pytest.approx(scene._pan_at(zombie), abs=0.05)


def test_no_zombie_groans_when_no_chance_is_taken(mocker):
    """The chance at 0: zombies come and chase, in silence."""
    mocker.patch.object(groans_module, 'GROAN_CHANCE', 0.0)
    scene = busy_yard()
    heard = groans_heard(mocker, scene)

    run(scene, seconds=12.0)

    assert scene.zombies or scene.zombie_pool.given_back
    assert heard == []


GROAN_REPLAY_TEST = 'test_the_same_seed_groans_the_same_groans'


def groan_decisions(mocker, scene: NeighborhoodScene) -> list[tuple[float, bool]]:
    """Spy on every groan chance the scene takes, recording when it came and whether it groaned.

    Every chance, groaned or silent, so a run proves its rolls repeat even when luck groans none:
    a busy yard's 20 s gives some seeds only 9 chances at 1 in 3, all silent 1 seed in 38 (seed
    1270429352, 2026-11-17).

    Returns:
        The list of (game time, groaned), filled as the scene runs.

    """
    decisions: list[tuple[float, bool]] = []
    original = scene.groan_timer.should_groan

    def should_groan(**keywords):
        groaned = original(**keywords)
        decisions.append((keywords['now'], groaned))
        return groaned

    mocker.patch.object(scene.groan_timer, 'should_groan', side_effect=should_groan)
    return decisions


@pytest.mark.parametrize('seed_case', seed_cases(test=GROAN_REPLAY_TEST))
def test_the_same_seed_groans_the_same_groans(mocker, seed_case, request):
    """Groans come from a named stream: a busy yard run twice from one seed groans alike.

    Alike chance for chance, silent ones included, so the proof doesn't hang on luck: some seeds
    groan none in 20 s (groan_decisions).
    """
    seed = resolve_seed(seed_case, node=request.node, test=GROAN_REPLAY_TEST)
    runs = []
    for _ in range(2):
        reset_streams(seed=seed)
        scene = busy_yard()
        decisions = groan_decisions(mocker, scene)
        heard = groans_heard(mocker, scene)
        hold_fire(scancodes=(pygame.KSCAN_J,), pads_firing=(1, 2, 3))
        run(scene, seconds=20.0)
        hold_fire()
        runs.append((list(decisions), list(heard)))

    note = failure_note(test=GROAN_REPLAY_TEST, vector='default', seed=seed)
    (first_decisions, _first_heard), _second = runs
    assert first_decisions, note
    assert runs[0] == runs[1], note


def test_an_unplugged_player_who_never_aimed_the_laser_fades_nothing(mocker):
    """A pad unplugged before its kid ever shone: there is no laser sound to fade."""
    with support.running_game(scene_class=NeighborhoodScene, plugged_in_at_start=False) as (
        engine,
        scene,
    ):
        assert isinstance(scene, NeighborhoodScene)
        support.plug_in_the_pad(engine)
        scene.roster = scene.roster.join(device=gamepad(STAND_IN_PAD.instance_id))
        scene.add_missing_kids()
        run(scene, seconds=FRAME_SECONDS)
        played = mocker.spy(type(scene.sounds[LASER_SHINE]), 'play')

        support.unplug_the_pad(engine)
        run(scene, seconds=FRAME_SECONDS)

        assert 1 not in scene.kids
        assert played.call_count == 0


# The rest of the sounds (feature plan 11)


def spies(mocker, scene: NeighborhoodScene, *names: str) -> dict:
    """Spy on the plays of some of the scene's sounds.

    Returns:
        Each name's spy.

    """
    return {name: mocker.spy(scene.sounds[name], 'play') for name in names}


def pan_of(scene: NeighborhoodScene, *, world_x: float, width: float) -> float:
    """Return the pan a sound made by something this wide, standing here, should have.

    Returns:
        The pan.

    """
    return pan_for(world_x=world_x + width / 2, camera=scene.camera, screen_width=SCREEN_WIDTH)


def test_every_zombie_climbing_out_plays_the_spawn_from_its_tv(mocker):
    """Ten seconds: each TV's first zombie, and a spawn heard from where each TV stands."""
    scene = neighborhood()
    spawn = spies(mocker, scene, TV_SPAWN)[TV_SPAWN]
    pans = {pan_of(scene, world_x=tv.world_x, width=TV_SIZE) for tv in scene.tvs}

    run(scene, seconds=10.0)

    assert spawn.call_count == len(scene.zombies) == len(scene.tvs)
    assert {call.kwargs['pan'] for call in spawn.call_args_list} == pans


def test_a_zap_on_a_tv_plays_only_the_strongest_of_what_it_did(mocker):
    """Nine zaps: six hits, a break into cracked and one into smashed, then the destruction."""
    scene = neighborhood()
    scene.shake = lambda *arguments, **keywords: None
    _dex, tv = kid_under_a_tv(scene)
    heard = spies(mocker, scene, TV_HIT, TV_BREAK, TV_DESTROYED)
    hold_fire(scancodes=(pygame.KSCAN_J,))

    run(scene, seconds=2.5)

    assert tv.is_destroyed
    assert {name: spy.call_count for name, spy in heard.items()} == {
        TV_HIT: 6,
        TV_BREAK: 2,
        TV_DESTROYED: 1,
    }
    pan = pan_of(scene, world_x=tv.world_x, width=TV_SIZE)
    for spy in heard.values():
        assert all(call.kwargs['pan'] == pytest.approx(pan) for call in spy.call_args_list)


def test_a_rescue_plays_once_from_the_neighbor(mocker):
    """Dex reaches a neighbor: one rescue heard, from where the neighbor stood."""
    scene = neighbors_stage()
    neighbor = scene.neighbors[0]
    heard = spies(mocker, scene, RESCUE, LOSS)
    stand_on(scene.kids[0], neighbor)

    run(scene, seconds=0.5)

    assert heard[RESCUE].call_count == 1
    assert heard[LOSS].call_count == 0
    assert heard[RESCUE].call_args.kwargs['pan'] == pytest.approx(
        pan_of(scene, world_x=neighbor.world_x, width=KID_WIDTH)
    )


def test_a_loss_plays_once_from_the_neighbor(mocker):
    """A zombie reaches a neighbor first: one loss heard, from where the neighbor stood."""
    scene = neighbors_stage()
    neighbor = scene.neighbors[0]
    heard = spies(mocker, scene, RESCUE, LOSS)
    scene.add_zombie(world_x=neighbor.world_x, world_y=neighbor.world_y)

    run(scene, seconds=0.5)

    assert heard[LOSS].call_count == 1
    assert heard[RESCUE].call_count == 0
    assert heard[LOSS].call_args.kwargs['pan'] == pytest.approx(
        pan_of(scene, world_x=neighbor.world_x, width=KID_WIDTH)
    )


def test_a_knockout_bonks_once_however_long_the_zombie_stays(mocker):
    """One knockout, one bonk: a zombie still on the kid while it is down bonks no more."""
    scene = neighborhood()
    dex = scene.kids[0]
    knockout = spies(mocker, scene, KNOCKOUT)[KNOCKOUT]
    zombie = scene.add_zombie(world_x=dex.world_x, world_y=dex.world_y)
    pan = pan_of(scene, world_x=dex.world_x, width=KID_WIDTH)

    for _ in range(round(KNOCKOUT_SECONDS * 60)):
        zombie.world_x, zombie.world_y = dex.world_x, dex.world_y
        run(scene, seconds=FRAME_SECONDS)

    assert knockout.call_count == 1
    assert knockout.call_args.kwargs['pan'] == pytest.approx(pan)


def test_the_gate_creaks_once_as_it_begins_to_open(mocker):
    """The yard empty and one rescued: one creak, on the frame the gate starts to swing."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    gate = spies(mocker, scene, GATE)[GATE]
    stand_on(scene.kids[0], scene.neighbors[0])

    opened_at = None
    for _ in range(60):
        run(scene, seconds=FRAME_SECONDS)
        if opened_at is None and scene.exit_door.is_open:
            opened_at = gate.call_count

    assert opened_at == 1
    assert gate.call_count == 1
    assert gate.call_args.kwargs['pan'] == pytest.approx(
        pan_of(scene, world_x=scene.exit_door.world_x, width=DOOR_SIZE)
    )


def test_the_stage_loop_starts_on_the_stages_first_frame_looping_on_the_music_bus(mocker):
    """One sound, every layer mixed in, looping by itself, on the music bus above the effects."""
    scene = neighborhood()
    loop = mocker.spy(scene.music.loop_sound, 'play')

    run(scene, seconds=FRAME_SECONDS)

    assert loop.call_count == 1
    assert loop.call_args.kwargs == {
        'volume': music.MUSIC_VOLUME,
        'bus': music.MUSIC_BUS,
        'priority': music.MUSIC_PRIORITY,
        'loop': True,
    }


def test_the_stage_loop_is_exactly_its_bars_long():
    """16.000 s, every tail folded onto its start, so each repeat lands on the beat."""
    scene = neighborhood()

    assert scene.music.loop_sound.length == music.LOOP_SECONDS


def test_no_cue_of_the_score_clips():
    """The layers' volumes add up to no more than full scale at any sample."""
    scene = neighborhood()
    audio = scene.scene_manager.audio

    peaks = {cue.name: music.cue_sound(audio, cue).peak for cue in music.CUES}

    assert all(peak <= 1.0 for peak in peaks.values()), peaks


def without_zombies(scene: NeighborhoodScene) -> None:
    """Destroy every TV, so no zombie comes: a long run can't end in a game over by chance.

    The tests' random streams are unseeded, so whether zombies reach a kid in 16 s is luck.
    """
    for tv in scene.tvs:
        tv.hits = HITS_PER_STAGE * (len(TV_STAGES) - 1)
    assert all(tv.is_destroyed for tv in scene.tvs)


def test_the_stage_loop_is_started_once_and_repeats_by_itself(mocker):
    """Past its first boundary, still the one play: the mixer repeats it, not the stage."""
    scene = neighborhood()
    without_zombies(scene)
    loop = mocker.spy(scene.music.loop_sound, 'play')

    run(scene, seconds=music.LOOP_SECONDS + 1.0)

    assert loop.call_count == 1


def test_the_stage_asks_for_no_sound_during_play(mocker):
    """Every sound it plays was got in setup: nothing can compile mid-stage (decision 11)."""
    scene = busy_yard()
    asked = mocker.spy(scene.scene_manager.audio, 'sound')
    hold_fire(scancodes=(pygame.KSCAN_J,), pads_firing=(1, 2, 3))

    run(scene, seconds=20.0)

    assert asked.call_count == 0


def through_the_gate(scene: NeighborhoodScene) -> None:
    """Walk Dex into the open gate (the yard already cleared)."""
    stand_on(scene.kids[0], scene.exit_door)
    scene.kids[0].world_y += 8


def test_clearing_the_stage_fades_the_loop_and_plays_the_clear(mocker):
    """Through the gate: the loop fades out, the D major sting plays once, the loop never again."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    loop = mocker.spy(scene.music.loop_sound, 'play')
    clear = mocker.spy(scene.music.clear_sound, 'play')
    clear_the_yard(scene)
    playing = loop.spy_return
    stop = mocker.spy(type(playing), 'stop')
    through_the_gate(scene)

    run(scene, seconds=CHEER_SECONDS)

    assert scene.stage_cleared
    assert clear.call_count == 1
    assert clear.call_args.kwargs['loop'] is False
    assert stops_of(stop, playing) == [STAGE_CLEAR_FADE_SECONDS]
    assert loop.call_count == 1


def test_a_clear_before_the_loop_started_plays_the_clear_alone_and_the_loop_never(mocker):
    """Cleared before the loop's first frame: the sting plays, nothing fades, no loop follows."""
    scene = neighbors_stage(neighbors=(NeighborKind.PIZZA_TEEN,))
    stage_music = music.StageMusic()
    stage_music.prepare(scene.scene_manager.audio)
    loop = mocker.spy(stage_music.loop_sound, 'play')
    clear = mocker.spy(stage_music.clear_sound, 'play')

    stage_music.play_the_clear(fade=STAGE_CLEAR_FADE_SECONDS)
    stage_music.start()

    assert clear.call_count == 1
    assert clear.call_args.kwargs['loop'] is False
    assert loop.call_count == 0


@pytest.mark.parametrize('sound', ['loop_sound', 'clear_sound'])
def test_the_stage_music_has_no_sound_before_it_is_prepared(sound):
    """Asked for before the stage's setup got them: said so, not a None played."""
    stage_music = music.StageMusic()

    with pytest.raises(RuntimeError, match='not prepared'):
        getattr(stage_music, sound)


def test_the_demo_roster_joins_the_keyboard_then_three_pads_as_slots_one_to_four():
    """The attract demo's players (feature plan 13): the keyboard is P1, stand-in pads P2 to P4."""
    assert DEMO_PAD_INSTANCE_IDS == (0, 1, 2)
    assert [player.device for player in demo_roster().joined_players] == [
        KEYBOARD,
        gamepad(0),
        gamepad(1),
        gamepad(2),
    ]
    assert [player.slot_index for player in demo_roster().joined_players] == [0, 1, 2, 3]


def test_the_demo_neighborhood_starts_with_four_kids():
    """Built from options alone, as a recording's first scene is, it has all four kids."""
    scene = DemoNeighborhoodScene(options=dict(OPTIONS))
    scene.setup()

    assert {slot: kid.look_name for slot, kid in scene.kids.items()} == {
        0: 'dex',
        1: 'marisol',
        2: 'theo',
        3: 'june',
    }


def test_the_demo_neighborhood_rebuilds_from_its_replay_arguments():
    """A replay rebuilds it from its recorded scene start, the four players included."""
    scene = DemoNeighborhoodScene(options=dict(OPTIONS))

    rebuilt = DemoNeighborhoodScene(
        options=dict(OPTIONS), **json.loads(json.dumps(scene.replay_arguments()))
    )

    assert rebuilt.roster == demo_roster()
    assert rebuilt.replay_arguments() == scene.replay_arguments()
