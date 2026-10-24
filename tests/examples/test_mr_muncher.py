"""Tests for the Mr. Muncher scene: the flow of a game, scoring, input, saves and the screens.

Real pygame and the real display (800x480, as the game runs by default); what is drawn is
checked by its pixels. Saves go to a temporary directory. Sound plays are recorded (the bank's
``play`` patched) only where a test is about which sound plays. The parts (maze, levels,
actors, pictures, autopilot) are tested in test_mr_muncher_maze_and_actors.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pygame
import pytest
from scripts.record_golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    _golden_game,
    command_line,
    discard_environment_events,
    press,
    release,
)

from glitchygames.audio.live import LiveAudio
from glitchygames.camera import Camera2D
from glitchygames.display_mode import set_display_mode
from glitchygames.events.base import HashableEvent
from glitchygames.examples import mr_muncher
from glitchygames.examples.mr_muncher import drawing
from glitchygames.examples.mr_muncher import game as mr_muncher_game
from glitchygames.examples.mr_muncher.actors import MuncherState
from glitchygames.examples.mr_muncher.autopilot import Autopilot
from glitchygames.examples.mr_muncher.game import (
    BONUS_POINTS_SHOW_SECONDS,
    BONUS_SECONDS,
    CAUGHT_SHAKE,
    DEATH_AFTER_SECONDS,
    DEATH_ANIMATION_SECONDS,
    DEATH_FREEZE_SECONDS,
    EAT_PAUSE_SECONDS,
    EXTRA_LIFE_SCORE,
    GAME_OVER_SECONDS,
    INTRO_READY_SECONDS,
    LEVEL_CLEAR_FLASH_SECONDS,
    LEVEL_CLEAR_PAUSE_SECONDS,
    MESSAGE_COLOR,
    MINIMUM_TILE_SIZE,
    READY_SECONDS,
    STARTING_LIVES,
    THE_END_COLOR,
    TITLE_COLOR,
    GameProgress,
    MrMuncherGameOverScene,
    MrMuncherScene,
    Phase,
    maze_geometry,
    shared_sound_bank,
)
from glitchygames.examples.mr_muncher.maze import Direction, build_maze
from glitchygames.exit_codes import ExitCode
from glitchygames.randomness import reset_streams
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.testing.keys import qwerty_scancode
from glitchygames.transitions import FadeTransition
from glitchygames.world import position_world_sprites

SCREEN_SIZE = (800, 480)
FRAME_SECONDS = 1.0 / 60.0
TEST_SEED = 20261023
# Screen pixels of the default layout: tiles of 20 pixels, the maze from x = 130
TILE_SIZE = 20
MAZE_LEFT = 130

GOLDEN_REPLAY_PATH = (
    Path(__file__).parent.parent / 'fixtures' / 'replays' / 'mr-muncher' / 'golden.jsonl.gz'
)


@pytest.fixture(autouse=True)
def display():
    """The game's display: 800x480."""
    if not pygame.get_init():
        pygame.init()
    surface = pygame.display.get_surface()
    if surface is None or surface.get_size() != SCREEN_SIZE:
        set_display_mode(size=SCREEN_SIZE)


@pytest.fixture
def save_directory(tmp_path, mocker):
    """Keep the game's saves in a temporary directory.

    Returns:
        The directory saves go to.

    """
    mocker.patch(
        'glitchygames.state.manager.get_save_directory',
        side_effect=lambda app_name: tmp_path / app_name,
    )
    return tmp_path


@pytest.fixture
def scene(save_directory):
    """A new game's first level, its random streams seeded."""
    reset_streams(seed=TEST_SEED)
    return MrMuncherScene(options={'input_mode': 'joystick'})


@pytest.fixture
def played(scene, mocker):
    """Record the sounds the scene plays."""
    return mocker.patch.object(scene.sounds, 'play')


@pytest.fixture
def playing(scene):
    """The scene, its countdown over: in play."""
    _tick(scene, seconds=scene.ready_seconds + FRAME_SECONDS)
    assert scene.phase is Phase.PLAYING
    return scene


def _tick(scene: MrMuncherScene, *, seconds: float) -> None:
    """Run the scene's logic for some seconds, frame by frame, as the scene manager does."""
    for _ in range(round(seconds / FRAME_SECONDS)):
        scene.advance_game_time(seconds=FRAME_SECONDS)
        scene.dt_tick(FRAME_SECONDS)


def _key_event(event_type: int, key: int) -> HashableEvent:
    return HashableEvent(event_type, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))


def _press(scene: MrMuncherScene, key: int) -> None:
    scene.on_key_down_event(_key_event(pygame.KEYDOWN, key))


def _release(scene: MrMuncherScene, key: int) -> None:
    scene.on_key_up_event(_key_event(pygame.KEYUP, key))


def _rendered(scene: MrMuncherScene) -> pygame.Surface:
    """Place the world sprites (as the engine does each frame), then draw the scene."""
    assert scene.screen is not None
    position_world_sprites(sprites=scene.all_sprites, camera=scene.camera, screen_size=SCREEN_SIZE)
    scene.render(scene.screen)
    return scene.screen


def _rgb(surface: pygame.Surface, position: tuple[int, int]) -> tuple[int, int, int]:
    color = surface.get_at(position)
    return (color.r, color.g, color.b)


def _area_colors(surface: pygame.Surface, area: pygame.Rect) -> set[tuple[int, int, int]]:
    return {
        _rgb(surface, (x, y))
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
    }


def _tile_area(column: int, row: int) -> pygame.Rect:
    return pygame.Rect(MAZE_LEFT + column * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE)


def _eat_all_but(scene: MrMuncherScene, *cells: tuple[int, int]) -> None:
    """Eat every sprocket except those on the given tiles (as if the player had)."""
    for cell, sprocket in scene.sprockets.items():
        if cell not in cells:
            sprocket.eat()
            scene.sprockets_eaten += 1


def _clear_the_way(scene: MrMuncherScene) -> None:
    """Send every muncher far away into the house, where it waits harmlessly."""
    for muncher in scene.munchers:
        muncher.place_at(position=scene.maze.house_centre)
        muncher.state = MuncherState.WAITING
    scene.life_seconds = -1000.0  # Nobody is released


class TestLayout:
    """The maze fills the screen's height between two side panels."""

    def test_the_default_screen(self):
        geometry = maze_geometry(maze=build_maze(), screen_size=SCREEN_SIZE)
        assert (geometry.tile_size, geometry.left, geometry.top) == (TILE_SIZE, MAZE_LEFT, 0)

    def test_a_narrow_screen_keeps_room_for_the_panels(self):
        geometry = maze_geometry(maze=build_maze(), screen_size=(600, 480))
        assert geometry.tile_size == 14
        assert geometry.left >= 100

    def test_tiles_never_get_tiny(self):
        assert (
            maze_geometry(maze=build_maze(), screen_size=(100, 50)).tile_size == MINIMUM_TILE_SIZE
        )

    def test_the_first_frame(self, scene, played):
        scene.setup()
        screen = _rendered(scene)
        assert _rgb(screen, (MAZE_LEFT + 4 * TILE_SIZE, 3 * TILE_SIZE)) == drawing.WALL_FILL_COLOR
        assert _rgb(screen, _tile_area(12, 16).center) == drawing.SPROCKET_COLOR
        # The player, a muncher, the countdown under the house, and the title in the left panel
        assert drawing.BUCKET_RED in _area_colors(screen, _tile_area(13, 18))
        assert scene.munchers[0].profile.color in _area_colors(screen, _tile_area(13, 8))
        assert MESSAGE_COLOR in _area_colors(screen, scene.message.rect)
        assert scene.message_shown == ('3', MESSAGE_COLOR)
        assert TITLE_COLOR in _area_colors(screen, pygame.Rect(0, 0, MAZE_LEFT, 80))

    def test_a_given_sprite_group_is_used(self, save_directory):
        group = pygame.sprite.LayeredDirty()
        scene = MrMuncherScene(options={}, groups=group)
        assert scene.all_sprites is group
        assert scene.player in group

    def test_the_sound_bank_is_shared_by_every_level(self, scene):
        assert scene.sounds is shared_sound_bank()


class TestStartingALevel:
    """A new game counts down like a film leader; later reels and lives show their number."""

    def test_a_new_game_counts_down_then_calls_action(self, scene, played):
        scene.setup()
        _tick(scene, seconds=INTRO_READY_SECONDS - 0.1)
        assert scene.phase is Phase.READY
        assert scene.message_shown[0] == 'ACTION!'
        assert scene.player.position == (13.0, 18.0)
        assert [call.args[0] for call in played.call_args_list] == [
            'countdown_beep',
            'countdown_beep',
            'countdown_beep',
            'action',
        ]
        _tick(scene, seconds=0.2)
        assert scene.phase is Phase.PLAYING
        assert not scene.message.visible

    def test_a_later_reel_shows_its_number(self, save_directory, mocker):
        later = MrMuncherScene(options={}, progress=GameProgress(level=2, score=4000, lives=2))
        played = mocker.patch.object(later.sounds, 'play')
        later.setup()
        assert later.message_shown[0] == 'REEL 2'
        played.assert_not_called()
        assert later.ready_seconds == READY_SECONDS
        assert (later.score, later.lives) == (4000, 2)
        _tick(later, seconds=READY_SECONDS - 0.1)
        played.assert_called_once_with('action')

    def test_setting_up_again_after_a_pause_shows_no_message_in_play(self, playing):
        playing.setup()
        assert not playing.message.visible

    def test_replay_arguments_rebuild_the_reel_as_it_began(self, save_directory):
        progress = GameProgress(level=3, score=12000, lives=4, extra_life_awarded=True)
        reel = MrMuncherScene(options={}, progress=progress)
        reel.score += 500
        arguments = reel.replay_arguments()
        assert arguments == {'progress': progress.model_dump()}
        rebuilt = MrMuncherScene(options={}, **arguments)
        assert rebuilt.starting_progress == progress

    def test_the_best_saved_score_is_the_high_score(self, scene, save_directory):
        scene.saves.save('high_scores', {'scores': [{'score': 7777, 'level': 2}]})
        again = MrMuncherScene(options={})
        assert again.high_score == 7777
        assert again._saved_high_scores() == [{'score': 7777, 'level': 2}]

    def test_play_starts_the_projector(self, scene):
        scene.scene_manager._live_audio = LiveAudio(channel_indices=(0,))
        _tick(scene, seconds=scene.ready_seconds + FRAME_SECONDS)
        assert scene.projector is not None
        assert scene.projector.is_playing
        scene.cleanup()
        assert scene.projector is None

    def test_without_a_free_voice_it_plays_without_its_projector(self, scene, caplog):
        scene.scene_manager._live_audio = LiveAudio(channel_indices=())
        _tick(scene, seconds=scene.ready_seconds + FRAME_SECONDS)
        assert scene.projector is None
        assert 'without its projector' in caplog.text


class TestInput:
    """Arrows, WASD, the D-pad, a hat and the stick steer; ESC or P pause; Q quits."""

    @pytest.mark.parametrize(
        ('key', 'direction'),
        [
            (pygame.K_UP, Direction.UP),
            (pygame.K_DOWN, Direction.DOWN),
            (pygame.K_LEFT, Direction.LEFT),
            (pygame.K_RIGHT, Direction.RIGHT),
            (pygame.K_w, Direction.UP),
            (pygame.K_a, Direction.LEFT),
            (pygame.K_s, Direction.DOWN),
            (pygame.K_d, Direction.RIGHT),
        ],
    )
    def test_a_pressed_direction_is_wanted_from_the_next_frame(self, scene, key, direction):
        scene.player.wanted_direction = None
        _press(scene, key)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is direction

    def test_letting_go_of_the_wanted_way_returns_to_one_still_held(self, scene):
        _press(scene, pygame.K_RIGHT)
        _press(scene, pygame.K_UP)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.UP
        _release(scene, pygame.K_UP)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.RIGHT

    def test_letting_go_of_the_last_key_keeps_the_wanted_way(self, scene):
        _press(scene, pygame.K_UP)
        _tick(scene, seconds=FRAME_SECONDS)
        _release(scene, pygame.K_UP)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.UP

    def test_letting_go_of_another_key_changes_nothing(self, scene):
        _press(scene, pygame.K_UP)
        _press(scene, pygame.K_RIGHT)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.UP
        _release(scene, pygame.K_RIGHT)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.UP

    @pytest.mark.parametrize('key', [pygame.K_ESCAPE, pygame.K_p])
    def test_escape_or_p_pauses(self, scene, key):
        _press(scene, key)
        assert isinstance(scene.next_scene, PauseScene)

    def test_q_quits(self):
        """Q (by its position) ends the run through the engine's frame loop."""
        with _golden_game('mr_muncher', random_seed=TEST_SEED) as manager:
            pygame.event.post(press(pygame.K_q))
            pygame.event.post(release(pygame.K_q))
            for _ in range(3):
                manager.dt = FRAME_SECONDS
                manager.run_frame()
            assert manager.quit_requested

    def test_other_keys_go_to_the_base_scene(self, scene):
        _press(scene, pygame.K_x)
        _release(scene, pygame.K_x)
        assert scene.next_scene is None

    def test_losing_focus_pauses_but_not_once_the_game_is_over(self, scene):
        focus_lost = HashableEvent(pygame.WINDOWFOCUSLOST, window=None)
        scene.on_window_focus_lost_event(focus_lost)
        assert isinstance(scene.next_scene, PauseScene)
        scene.next_scene = None
        scene.phase = Phase.GAME_OVER
        scene.on_window_focus_lost_event(focus_lost)
        assert scene.next_scene is None

    def test_joystick_buttons_steer_and_start_pauses(self, scene):
        dpad_up = HashableEvent(
            pygame.JOYBUTTONDOWN, instance_id=0, joy=0, button=pygame.CONTROLLER_BUTTON_DPAD_UP
        )
        scene.player.wanted_direction = None
        scene.on_joy_button_down_event(dpad_up)
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.UP
        scene.on_joy_button_up_event(
            HashableEvent(
                pygame.JOYBUTTONUP, instance_id=0, joy=0, button=pygame.CONTROLLER_BUTTON_DPAD_UP
            )
        )
        assert scene.next_scene is None
        scene.on_joy_button_down_event(
            HashableEvent(
                pygame.JOYBUTTONDOWN, instance_id=0, joy=0, button=pygame.CONTROLLER_BUTTON_START
            )
        )
        assert isinstance(scene.next_scene, PauseScene)

    def test_a_joystick_stick_steers(self, scene):
        scene.on_joy_axis_motion_event(
            HashableEvent(
                pygame.JOYAXISMOTION,
                instance_id=0,
                joy=0,
                axis=pygame.CONTROLLER_AXIS_LEFTX,
                value=0.9,
            )
        )
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.RIGHT

    @pytest.mark.parametrize(
        ('value', 'direction'),
        [
            ((1, 0), Direction.RIGHT),
            ((-1, 0), Direction.LEFT),
            ((0, 1), Direction.UP),
            ((0, -1), Direction.DOWN),
            ((0, 0), Direction.LEFT),
        ],
    )
    def test_a_joystick_hat_steers(self, scene, value, direction):
        scene.on_joy_hat_motion_event(
            HashableEvent(pygame.JOYHATMOTION, instance_id=0, joy=0, hat=0, value=value)
        )
        assert scene.player.wanted_direction is direction

    def test_controller_mode_steers_with_the_dpad_and_stick(self, save_directory):
        scene = MrMuncherScene(options={'input_mode': 'controller'})
        scene.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN,
                instance_id=0,
                button=pygame.CONTROLLER_BUTTON_DPAD_DOWN,
            )
        )
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.DOWN
        scene.on_controller_button_up_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONUP, instance_id=0, button=pygame.CONTROLLER_BUTTON_DPAD_DOWN
            )
        )
        scene.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                instance_id=0,
                axis=pygame.CONTROLLER_AXIS_LEFTY,
                value=-30000,
            )
        )
        _tick(scene, seconds=FRAME_SECONDS)
        assert scene.player.wanted_direction is Direction.UP
        scene.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN, instance_id=0, button=pygame.CONTROLLER_BUTTON_START
            )
        )
        assert isinstance(scene.next_scene, PauseScene)


class TestEating:
    """Sprockets, snacks, the bonus, extra lives and clearing the level."""

    def test_the_player_eats_the_sprockets_it_passes(self, playing, played):
        _clear_the_way(playing)
        _tick(playing, seconds=0.38)
        assert 10.0 < playing.player.tile_x < 10.5
        eaten = [cell for cell in [(12, 18), (11, 18), (10, 18)] if playing.sprockets[cell].eaten]
        assert len(eaten) == 3
        assert playing.score == 30
        assert [call.args[0] for call in played.call_args_list] == [
            'crunch_one',
            'crunch_two',
            'crunch_one',
        ]
        assert drawing.SPROCKET_COLOR not in _area_colors(_rendered(playing), _tile_area(11, 18))

    def test_a_snack_frightens_the_munchers(self, playing, played):
        playing.mode_seconds = 3.0
        playing.player.place_at(position=(2, 18))
        playing.player.direction = Direction.LEFT
        playing.munchers[1].state = MuncherState.EATEN
        _tick(playing, seconds=0.25)
        assert playing.sprockets[1, 18].eaten
        assert playing.score == 10 + 50  # The sprocket it stood on, then the snack
        played.assert_any_call('sugar_rush')
        assert playing.frightened_seconds_left > 6.0
        assert playing.munchers[0].frightened
        assert not playing.munchers[1].frightened  # Already eaten: only eyes
        # The scatter/chase clock stops while they are frightened
        assert playing.mode_seconds == pytest.approx(3.0, abs=0.1)
        _tick(playing, seconds=playing.settings.frightened_seconds)
        assert playing.frightened_seconds_left == 0.0
        assert not playing.munchers[0].frightened

    def test_a_fright_turns_the_roaming_munchers_round(self, playing):
        playing._start_fright()
        assert playing.munchers[0].reverse_soon
        assert not playing.munchers[1].reverse_soon  # Still waiting in the house

    def test_frightened_munchers_flash_before_they_recover(self, playing):
        playing._start_fright()
        playing.frightened_seconds_left = 1.9
        playing._pose_sprites()
        chomper_image = playing.munchers[0].image
        assert drawing.FLASHING_COLOR in _area_colors(chomper_image, chomper_image.get_rect())

    def test_the_bonus_appears_after_seventy_sprockets_and_is_worth_eating(self, playing, played):
        _clear_the_way(playing)
        playing.sprockets_eaten = 69
        playing.player.place_at(position=(12, 16))
        playing._eat_at_player()
        assert playing.bonus.visible
        playing.player.place_at(position=playing.message_cell)
        playing._eat_at_player()
        assert not playing.bonus.visible
        assert playing.bonus_points.visible
        played.assert_any_call('eat_bonus')
        assert playing.score == 10 + playing.settings.bonus_points
        _tick(playing, seconds=BONUS_POINTS_SHOW_SECONDS + 0.1)
        assert not playing.bonus_points.visible

    def test_an_uneaten_bonus_goes_away(self, playing):
        _clear_the_way(playing)
        playing.bonus.visible = 1
        playing.bonus_seconds_left = BONUS_SECONDS
        playing.player.place_at(position=(1, 1))
        playing.player.direction = None
        playing.player.wanted_direction = None
        _tick(playing, seconds=BONUS_SECONDS + 0.1)
        assert not playing.bonus.visible

    def test_ten_thousand_points_give_one_extra_life(self, playing, played):
        playing.score = EXTRA_LIFE_SCORE - 10
        playing._add_points(10)
        assert playing.lives == STARTING_LIVES + 1
        assert playing.extra_life_awarded
        played.assert_any_call('extra_life')
        playing._add_points(EXTRA_LIFE_SCORE)
        assert playing.lives == STARTING_LIVES + 1
        assert playing.high_score == playing.score
        # The spare lives show in the right panel
        right_panel_top = pygame.Rect(670, 30, 130, 30)
        assert drawing.BUCKET_RED in _area_colors(_rendered(playing), right_panel_top)

    def test_the_last_sprocket_clears_the_reel(self, playing, played):
        _eat_all_but(playing, (12, 18))
        _tick(playing, seconds=0.2)
        assert playing.phase is Phase.LEVEL_CLEAR
        assert all(muncher.hidden for muncher in playing.munchers)
        assert playing.message_shown == ('CUT!', MESSAGE_COLOR)
        played.assert_any_call('level_clear')
        _tick(playing, seconds=LEVEL_CLEAR_PAUSE_SECONDS + LEVEL_CLEAR_FLASH_SECONDS)
        next_level = playing.next_scene
        assert isinstance(next_level, MrMuncherScene)
        assert next_level is not playing
        assert next_level.starting_progress == GameProgress(
            level=2, score=playing.score, lives=STARTING_LIVES
        )
        _tick(playing, seconds=FRAME_SECONDS)
        assert playing.next_scene is next_level  # Asked for once

    def test_the_cleared_maze_flashes(self, playing):
        _eat_all_but(playing, (12, 18))
        _tick(playing, seconds=0.2)
        playing.phase_seconds = LEVEL_CLEAR_PAUSE_SECONDS + 0.1
        flashing = _area_colors(_rendered(playing), pygame.Rect(MAZE_LEFT, 0, 540, 40))
        assert drawing.WALL_FLASH_EDGE_COLOR in flashing
        playing.phase_seconds = LEVEL_CLEAR_PAUSE_SECONDS + 0.3
        plain = _area_colors(_rendered(playing), pygame.Rect(MAZE_LEFT, 0, 540, 40))
        assert drawing.WALL_FLASH_EDGE_COLOR not in plain


class TestMunchers:
    """Munchers leave the house on time, change mode, are eaten when blue, and catch the player."""

    def test_munchers_leave_the_house_one_by_one(self, playing):
        release_seconds = playing.settings.release_seconds
        _tick(playing, seconds=release_seconds[0] + 0.05)
        states = [muncher.state for muncher in playing.munchers[1:]]
        assert states[0] is not MuncherState.WAITING
        assert states[1:] == [MuncherState.WAITING, MuncherState.WAITING]

    def test_a_change_of_mode_turns_roaming_munchers_round(self, playing):
        playing.mode_seconds = playing.settings.mode_schedule[0] - 0.001
        playing._advance_timers(seconds=0.01)
        assert playing.munchers[0].reverse_soon

    def test_eating_frightened_munchers_doubles_their_points(self, playing, played):
        _clear_the_way(playing)
        playing._start_fright()
        for points, muncher in zip((200, 400, 800, 1600), playing.munchers, strict=True):
            muncher.state = MuncherState.ROAMING
            muncher.frightened = True
            muncher.place_at(position=playing.player.position)
            score = playing.score
            assert playing._check_contacts()
            assert playing.score - score == points
            assert playing.phase is Phase.MUNCHER_EATEN
            assert muncher.state is MuncherState.EATEN
            assert muncher.hidden and playing.player.hidden
            assert playing.muncher_points.visible
            _tick(playing, seconds=EAT_PAUSE_SECONDS + FRAME_SECONDS)
            assert playing.phase is Phase.PLAYING
            assert not muncher.hidden and not playing.player.hidden
            assert not playing.muncher_points.visible
            muncher.place_at(position=playing.maze.house_centre)
            muncher.state = MuncherState.WAITING
        played.assert_any_call('camera_flash')

    def test_a_muncher_can_walk_into_a_player_standing_still(self, playing):
        _clear_the_way(playing)
        playing.mode_seconds = playing.settings.mode_schedule[0] + 1.0  # Chasing
        playing.player.place_at(position=(3, 1))  # Standing still
        playing.player.wanted_direction = None
        chomper = playing.munchers[0]
        chomper.state = MuncherState.ROAMING
        chomper.place_at(position=(4.7, 1))
        chomper.direction = Direction.LEFT
        _tick(playing, seconds=0.2)
        assert playing.phase is Phase.DYING
        assert playing.player.position == (3.0, 1.0)

    def test_a_waiting_muncher_cannot_touch_the_player(self, playing):
        snapper = playing.munchers[1]
        snapper.place_at(position=playing.player.position)
        assert not playing._check_contacts()

    def test_a_catch_shakes_the_screen_and_the_player_dies(self, playing, played, mocker):
        shake = mocker.spy(playing, 'shake')
        playing.mode_seconds = playing.settings.mode_schedule[0] + 1.0  # Chasing
        chomper = playing.munchers[0]
        chomper.place_at(position=(12, 18))
        chomper.direction = Direction.RIGHT
        for _ in range(12):
            if playing.phase is Phase.DYING:
                break
            _tick(playing, seconds=FRAME_SECONDS)
        assert playing.phase is Phase.DYING
        shake.assert_called_once_with(CAUGHT_SHAKE, targets=mr_muncher_game.ShakeTarget.SCREEN)
        _tick(playing, seconds=DEATH_FREEZE_SECONDS - 0.1)
        assert not chomper.hidden
        assert playing.player.dying_progress is None
        _tick(playing, seconds=DEATH_ANIMATION_SECONDS / 2)
        assert chomper.hidden
        assert playing.player.dying_progress == pytest.approx(0.5, abs=0.1)
        played.assert_any_call('film_snap')
        # The rest of the freeze (0.1 s), the animation's second half and the empty moment
        _tick(playing, seconds=0.1 + DEATH_ANIMATION_SECONDS / 2 + DEATH_AFTER_SECONDS + 0.02)
        assert playing.phase is Phase.READY
        assert playing.lives == STARTING_LIVES - 1
        assert playing.player.position == (13.0, 18.0)
        assert chomper.position == (13.0, 8.0)
        assert playing.message_shown[0] == 'TAKE 2'
        assert playing.ready_seconds == READY_SECONDS

    def test_losing_the_last_life_ends_the_game(self, playing, played, save_directory, mocker):
        transition_to = mocker.patch.object(playing, 'transition_to')
        playing.lives = 1
        playing.score = 1230
        playing._catch_player()
        _tick(
            playing,
            seconds=DEATH_FREEZE_SECONDS + DEATH_ANIMATION_SECONDS + DEATH_AFTER_SECONDS + 0.02,
        )
        assert playing.phase is Phase.GAME_OVER
        assert playing.player.hidden
        assert playing.message_shown == ('THE END', THE_END_COLOR)
        played.assert_any_call('the_end')
        assert playing._saved_high_scores() == [{'score': 1230, 'level': 1}]
        _tick(playing, seconds=GAME_OVER_SECONDS + FRAME_SECONDS)
        game_over, fade = transition_to.call_args.args
        assert isinstance(game_over, MrMuncherGameOverScene)
        assert isinstance(fade, FadeTransition)
        assert game_over.final_score == 1230
        _tick(playing, seconds=FRAME_SECONDS)
        transition_to.assert_called_once()

    def test_pausing_after_game_over_is_not_possible(self, playing):
        playing.phase = Phase.GAME_OVER
        _press(playing, pygame.K_ESCAPE)
        assert playing.next_scene is None

    def test_the_high_score_table_keeps_the_best_ten(self, playing):
        playing.saves.save(
            'high_scores',
            {'scores': [{'score': 100 * rank, 'level': 1} for rank in range(10, 0, -1)]},
        )
        playing.score = 550
        playing._save_high_score()
        scores = [entry['score'] for entry in playing._saved_high_scores()]
        assert scores == [1000, 900, 800, 700, 600, 550, 500, 400, 300, 200]


class TestProjector:
    """The projector flutters faster as sprockets go and changes for frights and eyes."""

    @pytest.fixture
    def projector_scene(self, playing):
        playing.scene_manager._live_audio = LiveAudio(channel_indices=(0,))
        playing._start_projector()
        assert playing.projector is not None
        return playing

    def test_it_speeds_up_as_sprockets_go(self, projector_scene):
        projector_scene._update_projector()
        cutoff, flutter = projector_scene.projector_settings
        assert projector_scene.projector.low_pass_cutoff == cutoff
        _eat_all_but(projector_scene, (1, 1))
        projector_scene._update_projector()
        later_cutoff, later_flutter = projector_scene.projector_settings
        assert later_cutoff > cutoff
        assert later_flutter > flutter
        assert projector_scene.projector.tremolo.rate_hz == later_flutter

    def test_it_wobbles_while_munchers_are_frightened_and_races_for_eyes(self, projector_scene):
        projector_scene._start_fright()
        projector_scene._update_projector()
        assert projector_scene.projector_settings == (
            mr_muncher_game.FRIGHTENED_PROJECTOR_CUTOFF_HZ,
            mr_muncher_game.FRIGHTENED_PROJECTOR_FLUTTER_HZ,
        )
        projector_scene.munchers[0].state = MuncherState.EATEN
        projector_scene._update_projector()
        assert projector_scene.projector_settings == (
            mr_muncher_game.EYES_PROJECTOR_CUTOFF_HZ,
            mr_muncher_game.EYES_PROJECTOR_FLUTTER_HZ,
        )

    def test_a_catch_stops_the_projector(self, projector_scene):
        projector_scene._catch_player()
        assert projector_scene.projector is None
        projector_scene._update_projector()  # Without a projector nothing happens
        projector_scene._stop_projector()


class TestDebugOverlay:
    """The debug overlay marks each roaming muncher's target tile in its colour."""

    def test_targets_are_marked(self, playing):
        surface = pygame.Surface(SCREEN_SIZE)
        chomper = playing.munchers[0]
        chomper.target = (1, 1)
        playing.debug_draw(surface, Camera2D(screen_width=800, screen_height=480))
        assert chomper.profile.color in _area_colors(surface, _tile_area(1, 1))
        # A waiting muncher's target is not drawn
        playing.munchers[1].target = (25, 22)
        playing.debug_draw(surface, Camera2D(screen_width=800, screen_height=480))
        assert _area_colors(surface, _tile_area(25, 22)) == {(0, 0, 0)}


class TestGameOverScreen:
    """The game-over screen shows the level reached and starts a new game."""

    def _screen(self, *, final_score: int, best: int) -> MrMuncherGameOverScene:
        screen = MrMuncherGameOverScene(
            final_score=final_score,
            high_scores=[{'score': best, 'level': 2}],
            level_reached=2,
            options={},
        )
        screen.setup()
        return screen

    def test_replay_arguments(self, save_directory):
        screen = self._screen(final_score=500, best=900)
        assert screen.replay_arguments() == {
            'final_score': 500,
            'high_scores': [{'score': 900, 'level': 2}],
            'level_reached': 2,
        }

    def test_a_new_best_is_announced(self, save_directory):
        headlines = {}
        for final_score in (900, 500):
            screen = self._screen(final_score=final_score, best=900)
            headline = screen.all_sprites.sprites()[-1]
            assert TITLE_COLOR in _area_colors(headline.image, headline.image.get_rect())
            headlines[final_score] = headline.rect.width
        assert headlines[900] > headlines[500]  # NEW HIGH SCORE! is the longer line

    @pytest.mark.parametrize(
        ('handler', 'event_type'),
        [
            ('on_joy_button_down_event', pygame.JOYBUTTONDOWN),
            ('on_controller_button_down_event', pygame.CONTROLLERBUTTONDOWN),
        ],
    )
    @pytest.mark.parametrize(
        ('button', 'restarts'),
        [
            (pygame.CONTROLLER_BUTTON_A, True),
            (pygame.CONTROLLER_BUTTON_START, True),
            (pygame.CONTROLLER_BUTTON_B, False),
        ],
    )
    def test_a_gamepad_starts_a_new_game(
        self, save_directory, handler, event_type, button, restarts
    ):
        screen = self._screen(final_score=500, best=900)
        screen.scene_manager.switch_to_scene(screen)
        getattr(screen, handler)(HashableEvent(event_type, instance_id=0, joy=0, button=button))
        active = screen.scene_manager.active_scene
        assert isinstance(active, MrMuncherScene) is restarts
        active.render(active.screen)


class TestWholeGames:
    """Whole games through the engine's frame loop (the golden harness, fixed 1/60 frames)."""

    def _run(self, manager, *, frames: int, steering=None) -> None:
        for _ in range(frames):
            manager.dt = FRAME_SECONDS
            discard_environment_events()
            if steering is not None:
                for event in steering(manager.active_scene):
                    pygame.event.post(event)
            manager.run_frame()

    def test_a_cleared_level_leads_to_the_next(self):
        with _golden_game('mr_muncher', random_seed=TEST_SEED) as manager:
            first = manager.active_scene
            assert isinstance(first, MrMuncherScene)
            _eat_all_but(first, (12, 18))
            self._run(manager, frames=round((INTRO_READY_SECONDS + 3.4) * 60))
            second = manager.active_scene
            assert isinstance(second, MrMuncherScene)
            assert second.settings.level == 2
            assert second.phase is Phase.READY
            assert second.score == first.score
            assert second.message_shown[0] == 'REEL 2'

    def test_a_game_over_leads_to_a_new_game(self):
        with _golden_game('mr_muncher', random_seed=TEST_SEED) as manager:
            last_life = MrMuncherScene(options=manager.OPTIONS, progress=GameProgress(lives=1))
            manager.switch_to_scene(last_life)
            autopilot = Autopilot(seek_capture_after_seconds=0.0)

            def steering(scene):
                """Steer by setting the wanted way directly (no keys).

                Returns:
                    No events.

                """
                if not isinstance(scene, MrMuncherScene):
                    return []
                direction = autopilot.choose_direction(scene=scene)
                scene.player.wanted_direction = direction
                return []

            self._run(manager, frames=60 * 25, steering=steering)
            game_over = manager.active_scene
            assert isinstance(game_over, MrMuncherGameOverScene)
            pygame.event.post(press(pygame.K_SPACE))
            pygame.event.post(release(pygame.K_SPACE))
            self._run(manager, frames=2)
            assert isinstance(manager.active_scene, MrMuncherScene)
            assert manager.active_scene.lives == STARTING_LIVES


def test_the_package_runs_the_games_main():
    """``uv run mr-muncher`` (the package's main) is the game module's main."""
    assert mr_muncher.main is mr_muncher_game.main


def test_main_runs_the_game_through_the_engine(mocker, capsys):
    """main() starts Mr. Muncher in the engine: here a headless replay of the golden run.

    GoldenTraceEngine is the GameEngine without the SCALED display flag, which SDL's dummy
    video driver cannot honour; pygame.quit is patched because later tests on this worker
    need pygame (as tests/replay/replay_helpers.replay_through_engine does).
    """
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    mocker.patch.dict(os.environ)  # --headless sets the SDL driver variables
    mocker.patch.object(mr_muncher_game, 'GameEngine', GoldenTraceEngine)
    GoldenTraceSceneManager.install()
    try:
        with (
            command_line([
                '--log-level',
                'warning',
                '--replay-trace',
                str(GOLDEN_REPLAY_PATH),
                '--headless',
            ]),
            pytest.raises(SystemExit) as exit_info,
        ):
            mr_muncher_game.main()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()

    assert exit_info.value.code == ExitCode.SUCCESS
    assert 'Replay matched' in capsys.readouterr().out
