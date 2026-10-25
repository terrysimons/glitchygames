"""Tests for the Drawing Fire scene, on real pygame (the dummy driver)."""

from __future__ import annotations

import pygame
import pytest

from glitchygames.display_mode import set_display_mode
from glitchygames.examples import drawing_fire
from glitchygames.examples.drawing_fire import game as drawing_fire_game
from glitchygames.examples.drawing_fire.battle import (
    ARMY_NAMES,
    SOLDIERS_PER_SIDE,
    Bullet,
    Side,
)
from glitchygames.examples.drawing_fire.drawing import ARMY_COLORS, ARMY_LIVERIES, PENCIL_COLOR
from glitchygames.examples.drawing_fire.game import (
    PAPER_COLOR,
    VICTORY_SECONDS,
    DrawingFireScene,
    Phase,
)
from glitchygames.randomness import reset_streams

SCREEN_SIZE = (800, 480)
TEST_SEED = 20261025


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)


@pytest.fixture
def scene():
    """A new battlefield, its random streams seeded."""
    reset_streams(seed=TEST_SEED)
    return DrawingFireScene(options={'input_mode': 'joystick'})


def test_the_scene_draws_paper_and_ground(scene):
    """The paper fills the screen and the ground line is pencilled on it."""
    scene.render(scene.screen)
    assert scene.screen.get_at((5, 5))[:3] == PAPER_COLOR
    ground_x = 400
    ground_y = round(scene.terrain.ground_y(ground_x))
    column = [scene.screen.get_at((ground_x, y))[:3] for y in range(ground_y - 2, ground_y + 3)]
    assert PENCIL_COLOR in column


def test_the_terrain_fits_the_screen_and_is_seeded(scene):
    """The terrain has a ground y per screen pixel, from the seeded stream."""
    assert len(scene.terrain.ground) == SCREEN_SIZE[0]
    reset_streams(seed=TEST_SEED)
    assert DrawingFireScene(options={'input_mode': 'joystick'}).terrain == scene.terrain


def test_main_runs_the_scene(mocker):
    """main() starts the engine with the Drawing Fire scene."""
    engine = mocker.patch.object(drawing_fire_game, 'GameEngine')
    drawing_fire.main()
    engine.assert_called_once_with(game=DrawingFireScene)
    engine.return_value.start.assert_called_once_with()


def test_the_scene_uses_the_sprite_group_it_is_given():
    """A given sprite group is the scene's group."""
    reset_streams(seed=TEST_SEED)
    groups = pygame.sprite.LayeredDirty()
    assert DrawingFireScene(options={'input_mode': 'joystick'}, groups=groups).all_sprites is groups


def kill_army(scene, side):
    """Take every soldier of an army out of the fight."""
    for soldier in scene.battle.soldiers:
        if soldier.side is side:
            soldier.health = 0


def test_the_scene_starts_in_battle_one_with_both_armies(scene):
    """A new scene is battle 1, in the battle phase, with every soldier standing."""
    assert scene.battle_number == 1
    assert scene.phase is Phase.BATTLE
    assert len(scene.battle.living(Side.PLATOON)) == SOLDIERS_PER_SIDE
    assert len(scene.battle.living(Side.BRIGADE)) == SOLDIERS_PER_SIDE


def test_the_battle_plays_itself_in_dt_tick(scene):
    """Stepping the scene moves the battle's clock and its soldiers."""
    starting_xs = [soldier.x for soldier in scene.battle.soldiers]
    for _ in range(60):
        scene.dt_tick(1 / 60)
    assert scene.battle.seconds == pytest.approx(1.0)
    assert [soldier.x for soldier in scene.battle.soldiers] != starting_xs


def test_a_win_announces_the_army_then_the_next_battle_starts(scene):
    """The victory message names the winner; after VICTORY_SECONDS battle 2 begins."""
    first_terrain = scene.terrain
    kill_army(scene, Side.BRIGADE)
    scene.dt_tick(1 / 60)
    assert scene.phase is Phase.VICTORY
    assert scene.victory_message == f'{ARMY_NAMES[Side.PLATOON]} wins!'
    scene.dt_tick(VICTORY_SECONDS / 2)
    assert scene.battle_number == 1
    assert scene.phase is Phase.VICTORY
    scene.dt_tick(VICTORY_SECONDS)
    assert scene.battle_number == 2
    assert scene.phase is Phase.BATTLE
    assert not scene.victory_message
    assert len(scene.battle.living(Side.BRIGADE)) == SOLDIERS_PER_SIDE
    assert scene.terrain != first_terrain


def test_the_victory_message_is_drawn_on_the_paper(scene, mocker):
    """The announcement is pencilled in the sky, which was blank before."""
    sky = pygame.Rect(SCREEN_SIZE[0] // 4, 60, SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] // 4)

    def sky_colors():
        return {
            tuple(scene.screen.get_at((x, y)))[:3]
            for x in range(sky.left, sky.right)
            for y in range(sky.top, sky.bottom)
        }

    scene.render(scene.screen)
    assert PENCIL_COLOR not in sky_colors()
    kill_army(scene, Side.PLATOON)
    scene.dt_tick(1 / 60)
    scene.render(scene.screen)
    assert PENCIL_COLOR in sky_colors()
    # The font is built once and kept
    font_constructor = mocker.spy(pygame.font, 'Font')
    scene.render(scene.screen)
    assert font_constructor.call_count == 0


def test_the_battle_is_drawn_in_each_armys_colour(scene):
    """Every living soldier's helmet is pencil yellow or graphite grey, where he stands."""
    scene.render(scene.screen)
    for soldier in scene.battle.soldiers:
        helmet = (round(soldier.x), round(soldier.y) - 34)
        assert tuple(scene.screen.get_at(helmet))[:3] == ARMY_COLORS[soldier.side]


def test_walking_soldiers_are_found_by_their_step(scene):
    """A soldier who walked this step is walking; one who stood still is not."""
    assert not scene.walking_soldier_ids
    for _ in range(30):
        scene.dt_tick(1 / 60)
    assert scene.walking_soldier_ids
    assert scene.walking_soldier_ids <= {soldier.soldier_id for soldier in scene.battle.soldiers}
    scene.start_battle()
    assert not scene.walking_soldier_ids


def test_bullets_and_sandbags_are_drawn(scene):
    """A bullet in flight is a pencil dash, and every sandbag is on the paper."""
    scene.render(scene.screen)
    blank = pygame.image.tobytes(scene.screen, 'RGB')
    bullet = Bullet(
        x=400.0, y=60.0, velocity_x=600.0, velocity_y=0.0, side=Side.PLATOON, distance_left=100.0
    )
    scene.battle.bullets.append(bullet)
    scene.render(scene.screen)
    assert tuple(scene.screen.get_at((396, 60)))[:3] == PENCIL_COLOR
    assert pygame.image.tobytes(scene.screen, 'RGB') != blank
    sandbag = scene.battle.sandbags[0]
    top = round(scene.terrain.ground_y(sandbag.x) - sandbag.height) + 4
    assert tuple(scene.screen.get_at((round(sandbag.x), top)))[:3] != PAPER_COLOR


def test_drawing_the_same_battle_twice_gives_the_same_picture(scene):
    """Nothing in the drawing is random."""
    for _ in range(90):
        scene.dt_tick(1 / 60)
    scene.render(scene.screen)
    first = pygame.image.tobytes(scene.screen, 'RGB')
    scene.render(scene.screen)
    assert pygame.image.tobytes(scene.screen, 'RGB') == first


def test_the_soldier_frames_are_scaled_once_for_the_scene(scene):
    """The scene keeps one set of frames, and each army's livery is built once."""
    frames = scene.soldier_frames
    scene.render(scene.screen)
    scheme_frames = frames.frames_for(ARMY_LIVERIES[Side.PLATOON])
    scene.render(scene.screen)
    assert scene.soldier_frames is frames
    assert frames.frames_for(ARMY_LIVERIES[Side.PLATOON]) is scheme_frames


def test_a_new_battle_redraws_the_ground(scene):
    """The ground line follows the new battle's terrain."""
    scene.start_battle()
    scene.render(scene.screen)
    ground_x = 400
    ground_y = round(scene.terrain.ground_y(ground_x))
    column = [scene.screen.get_at((ground_x, y))[:3] for y in range(ground_y - 2, ground_y + 3)]
    assert PENCIL_COLOR in column


def test_battles_replay_from_the_same_seed():
    """The same seed gives the same battle after the same ticks."""
    snapshots = []
    for _ in range(2):
        reset_streams(seed=TEST_SEED)
        scene = DrawingFireScene(options={'input_mode': 'joystick'})
        for _ in range(120):
            scene.dt_tick(1 / 60)
        snapshots.append([(soldier.x, soldier.health) for soldier in scene.battle.soldiers])
    assert snapshots[0] == snapshots[1]
