"""Tests for the Clockwork Keep example game."""

import argparse
import logging
import math
import os
import types
from pathlib import Path

import pygame
import pytest
from scripts.record_golden_traces import (
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    _golden_game,
    command_line,
    press,
    release,
)

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.live import VoiceState
from glitchygames.camera import FollowAxes, ParallaxLayer
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.display_mode import set_display_mode
from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.events.base import HashableEvent
from glitchygames.examples.clockwork_keep import game as clockwork_game
from glitchygames.examples.clockwork_keep import sounds as clockwork_sounds
from glitchygames.examples.clockwork_keep.constants import (
    CLOCK_START_SECONDS,
    COG_SILVER_POINTS,
    ELEVATOR_ASCENT_RUMBLE_LOW,
    GRAVITY,
    HUD_TEXT_COLOR,
    JUMP_VELOCITY,
    JUMP_VELOCITY_RUNNING,
    LAYER_TERRAIN,
    PIT_DEATH_THRESHOLD,
    PLAYER_WIDTH,
    PLAYFIELD_LEFT,
    PLAYFIELD_RIGHT,
)
from glitchygames.examples.clockwork_keep.drawing import clock_hand_angles
from glitchygames.examples.clockwork_keep.game import (
    ELEVATOR_STOP_BOUNCE,
    ELEVATOR_STOP_RATTLE,
    ClockworkKeepScene,
    CogCollectible,
)
from glitchygames.examples.clockwork_keep.levels import (
    ALL_FLOORS,
    FLOOR_BOILER_ROOM,
    FLOOR_CLOCK_FACE,
    FLOOR_GEAR_WORKS,
)
from glitchygames.examples.clockwork_keep.player import Tinker
from glitchygames.examples.clockwork_keep.terrain import Elevator, MovingGear, Platform
from glitchygames.exit_codes import ExitCode
from glitchygames.pixel_snap import PixelSnapMode, snap_to_pixel
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.state import DiskSaveManager
from glitchygames.testing.keys import qwerty_scancode
from glitchygames.world import CoordinateSpace, position_world_sprites

FRAME_TIME = 1.0 / 60.0
SCREEN_SIZE = (800, 480)
WORLD_SPRITE_CLASSES = (Tinker, Platform, Elevator, MovingGear, CogCollectible)


@pytest.fixture
def clockwork_scene(mocker):
    """A floor-0 scene with transition_to recorded instead of performed."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 480))
    scene = ClockworkKeepScene(options={'input_mode': 'joystick'})
    mocker.patch.object(scene, 'transition_to')
    return scene


def _stand_on_first_elevator(scene):
    elevator = scene.elevator_sprites[0]
    scene.player.world_x = elevator.world_x + 5
    scene.player.world_y = elevator.world_y - scene.player.rect.height
    for _ in range(5):
        scene.dt_tick(FRAME_TIME)


def _press_key(scene, key):
    scene.on_key_down_event(
        HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))
    )


class TestElevatorActivation:
    """BUGS.md #24: interact rides the elevator, jump always jumps."""

    def test_interact_rides(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_w)
        clockwork_scene.dt_tick(FRAME_TIME)
        clockwork_scene.transition_to.assert_called_once()

    def test_jump_jumps_and_does_not_ride(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_SPACE)
        clockwork_scene.dt_tick(FRAME_TIME)
        assert clockwork_scene.player.velocity_y < 0
        clockwork_scene.transition_to.assert_not_called()

    def test_jump_while_held_never_rides(self, clockwork_scene):
        """Even if on_ground is restored before the check, jump alone never rides."""
        _stand_on_first_elevator(clockwork_scene)
        clockwork_scene.actions.handle_event(
            HashableEvent(
                pygame.KEYDOWN,
                key=pygame.K_SPACE,
                mod=0,
                unicode='',
                scancode=qwerty_scancode(key=pygame.K_SPACE),
            )
        )
        clockwork_scene._check_elevator()
        clockwork_scene.transition_to.assert_not_called()


@pytest.fixture
def played(clockwork_scene, mocker):
    """Record sound-bank plays without rendering audio."""
    return mocker.patch.object(clockwork_scene.sounds, 'play')


class TestRecipes:
    """Every Clockwork Keep recipe renders."""

    @pytest.mark.parametrize('recipe', clockwork_sounds.ALL_RECIPES, ids=lambda r: r.name)
    def test_every_recipe_renders(self, recipe):
        samples = recipe.render(sample_rate=44100)
        assert len(samples) > 0
        assert abs(samples).max() == pytest.approx(recipe.peak)


class TestGameplaySounds:
    """Gameplay events play their sounds exactly when they should."""

    def test_jump_plays_once_when_jump_happens(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_SPACE)
        _press_key(clockwork_scene, pygame.K_SPACE)  # Airborne now: no second jump
        assert [call.args[0] for call in played.call_args_list].count('jump') == 1

    def test_land_plays_once_on_landing(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        played.reset_mock()
        clockwork_scene.player.velocity_y = 0.0
        clockwork_scene.player.world_y -= 40  # Lift into the air
        for _ in range(60):
            clockwork_scene.dt_tick(FRAME_TIME)
        assert [call.args[0] for call in played.call_args_list].count('land') == 1

    def test_first_tick_never_plays_land(self, clockwork_scene, played):
        """_start_transition runs one off-screen dt_tick(0.001) on the new scene."""
        clockwork_scene.dt_tick(0.001)
        assert 'land' not in [call.args[0] for call in played.call_args_list]

    def test_respawn_does_not_play_land(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        clockwork_scene.player.world_y -= 40
        clockwork_scene.dt_tick(FRAME_TIME)
        clockwork_scene._respawn_player()
        played.reset_mock()
        for _ in range(60):
            clockwork_scene.tweens.update(FRAME_TIME)
            clockwork_scene.dt_tick(FRAME_TIME)
        # Landing after the respawn tween can play once; the tween's direct on_ground=True can't
        assert [call.args[0] for call in played.call_args_list].count('land') <= 1

    def test_cog_pickup(self, clockwork_scene, played):
        cog = clockwork_scene.collectible_sprites[0]
        clockwork_scene.player.world_x = cog.world_x
        clockwork_scene.player.world_y = cog.world_y
        clockwork_scene._check_collectibles()
        played.assert_any_call('cog_pickup')

    def test_death_with_lives_left(self, clockwork_scene, played):
        clockwork_scene.player.lives = 2
        clockwork_scene._player_die()
        played.assert_any_call('death')

    def test_game_over_on_last_life(self, clockwork_scene, played, mocker):
        mocker.patch.object(clockwork_scene, '_save_high_score')
        mocker.patch.object(clockwork_scene, '_load_high_scores', return_value=[])
        clockwork_scene.player.lives = 1
        clockwork_scene._player_die()
        played.assert_any_call('game_over')

    def test_game_over_clears_screen_shake(self, clockwork_scene, played, mocker):
        """Spec revision 3: the game-over fade starts with no shake running."""
        mocker.patch.object(clockwork_scene, '_save_high_score')
        mocker.patch.object(clockwork_scene, '_load_high_scores', return_value=[])
        clockwork_scene.shake(
            Shake(style=ShakeStyle.NOISE, strength=5.0, duration=5.0, frequency=5.0),
            targets=ShakeTarget.SCREEN,
        )
        assert clockwork_scene.scene_manager.screen_shake.is_active
        clockwork_scene.player.lives = 1
        clockwork_scene._player_die()
        assert not clockwork_scene.scene_manager.screen_shake.is_active

    def test_setup_keeps_explicit_zero_target_fps_uncapped(self, clockwork_scene):
        clockwork_scene.target_fps = 0
        clockwork_scene.setup()
        assert math.isclose(clockwork_scene.target_fps, 0.0, abs_tol=1e-9)

    def test_setup_prerenders_sounds(self, clockwork_scene, mocker):
        prerender = mocker.patch.object(clockwork_scene.sounds, 'prerender')
        clockwork_scene.setup()
        prerender.assert_called_once()


class TestElevatorRide:
    """The elevator motor, arrival shake and camera hook."""

    def _ride(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        _press_key(clockwork_scene, pygame.K_w)
        clockwork_scene.dt_tick(FRAME_TIME)
        return clockwork_scene.transition_to.call_args.args[1]

    def test_motor_follows_car_speed_then_arrival_shakes_and_stops(
        self, clockwork_scene, played, mocker
    ):
        voice = mocker.Mock(state=VoiceState.PLAYING)
        create_voice = mocker.patch.object(
            clockwork_scene.scene_manager.live_audio, 'create_voice', return_value=voice
        )
        screen_shake = mocker.patch.object(clockwork_scene.scene_manager.screen_shake, 'add')
        transition = self._ride(clockwork_scene)
        assert create_voice.call_args.kwargs['owner'] is transition
        voice.start.assert_called_once()

        old, new = pygame.Surface((800, 480)), pygame.Surface((800, 480))
        transition.start(old, new)
        transition.update(0.5)
        slow_frequency = voice.frequency
        transition.update(3.0)
        assert voice.frequency > slow_frequency  # Accelerating into the stop
        transition.update(1.0)  # Arrives

        voice.stop_now.assert_called_once()
        played.assert_any_call('elevator_clank')
        styles = [call.args[0].style for call in screen_shake.call_args_list]
        assert styles == [ShakeStyle.BOUNCE, ShakeStyle.NOISE]
        assert all(call.args[0].rumble is not None for call in screen_shake.call_args_list)

    def test_ride_without_free_voice_is_silent_not_fatal(self, clockwork_scene, played, mocker):
        """Review focus 2: --live-voice-pool 0 or a full pool still rides."""
        mocker.patch.object(
            clockwork_scene.scene_manager.live_audio,
            'create_voice',
            side_effect=ValueError('All 0 live voice channels are in use'),
        )
        transition = self._ride(clockwork_scene)
        transition.start(pygame.Surface((800, 480)), pygame.Surface((800, 480)))
        assert transition.update(5.0) is True
        played.assert_any_call('elevator_clank')

    def test_ride_with_unavailable_audio_is_silent_not_fatal(self, clockwork_scene, played, mocker):
        voice = mocker.Mock(state=VoiceState.PLAYING)
        voice.start.side_effect = AudioUnavailableError('no mixer')
        mocker.patch.object(
            clockwork_scene.scene_manager.live_audio, 'create_voice', return_value=voice
        )
        transition = self._ride(clockwork_scene)
        transition.start(pygame.Surface((800, 480)), pygame.Surface((800, 480)))
        assert transition.update(5.0) is True
        played.assert_any_call('elevator_clank')

    def test_engine_positions_platforms_from_the_camera(self, clockwork_scene):
        """The engine's positioning step places the floor's world sprites (no game loop)."""
        clockwork_scene.camera.world_y = 37.0
        position_world_sprites(
            sprites=clockwork_scene.all_sprites,
            camera=clockwork_scene.camera,
            screen_size=SCREEN_SIZE,
        )
        platform = clockwork_scene.platform_sprites[0]
        mode = PixelSnapMode.NEAREST_HALF_UP
        assert platform.rect.y == snap_to_pixel(platform.world_y, mode) - 37


class TestElevatorRumble:
    """Sustained ascent rumble and the stronger, absolute stop rumble."""

    _ride = TestElevatorRide._ride

    def test_sustained_low_level_rises_with_speed_and_is_capped(self, clockwork_scene, mocker):
        mocker.patch.object(
            clockwork_scene.scene_manager.live_audio,
            'create_voice',
            return_value=mocker.Mock(state=VoiceState.PLAYING),
        )
        transition = self._ride(clockwork_scene)
        rumble = clockwork_scene.scene_manager.rumble
        transition.start(pygame.Surface((800, 480)), pygame.Surface((800, 480)))
        transition.update(0.5)
        early_level = rumble.sustained_levels[0]
        transition.update(3.0)
        late_level = rumble.sustained_levels[0]
        assert 0.0 < early_level < late_level <= ELEVATOR_ASCENT_RUMBLE_LOW

    def test_arrival_clears_sustained_rumble(self, clockwork_scene, played):
        transition = self._ride(clockwork_scene)
        transition.start(pygame.Surface((800, 480)), pygame.Surface((800, 480)))
        transition.update(3.0)
        assert clockwork_scene.scene_manager.rumble.sustained_levels[0] > 0.0
        transition.update(2.0)  # Arrives
        assert clockwork_scene.scene_manager.rumble.sustained_levels == (0.0, 0.0)

    def test_ride_without_free_voice_still_rumbles(self, clockwork_scene, mocker):
        mocker.patch.object(
            clockwork_scene.scene_manager.live_audio,
            'create_voice',
            side_effect=ValueError('All 0 live voice channels are in use'),
        )
        transition = self._ride(clockwork_scene)
        transition.start(pygame.Surface((800, 480)), pygame.Surface((800, 480)))
        transition.update(3.0)
        assert clockwork_scene.scene_manager.rumble.sustained_levels[0] > 0.0

    def test_stop_shakes_rumble_in_absolute_terms(self):
        for stop_shake in (ELEVATOR_STOP_BOUNCE, ELEVATOR_STOP_RATTLE):
            assert stop_shake.rumble is not None
            assert stop_shake.rumble.scale_with_strength is False
        assert ELEVATOR_STOP_BOUNCE.rumble.low_frequency == 1.0


class TestFloorThreeClock:
    """The floor-3 clock: smooth sweep hands driven by game time."""

    def test_hand_angles_at_start_time(self):
        hour, minute, second = clock_hand_angles(CLOCK_START_SECONDS)
        assert second == pytest.approx(0.0)
        assert minute == pytest.approx(2 * math.pi * 58 / 60)
        assert hour == pytest.approx(2 * math.pi * (11 + 58 / 60) / 12)

    def test_second_hand_sweeps_half_turn_after_thirty_seconds(self):
        _hour, _minute, second = clock_hand_angles(CLOCK_START_SECONDS + 30.0)
        assert second == pytest.approx(math.pi)

    def test_second_hand_wraps_at_exactly_sixty_seconds(self):
        _hour, minute_before, _second = clock_hand_angles(CLOCK_START_SECONDS)
        _hour, minute_after, second = clock_hand_angles(CLOCK_START_SECONDS + 60.0)
        assert second == pytest.approx(0.0)
        assert minute_after - minute_before == pytest.approx(2 * math.pi / 60)

    def test_floor_elapsed_time_advances_and_stops_after_game_over(self, clockwork_scene):
        assert clockwork_scene.floor_elapsed_time == 0.0
        clockwork_scene.dt_tick(0.02)
        assert clockwork_scene.floor_elapsed_time == pytest.approx(0.02)
        clockwork_scene.game_over_triggered = True
        clockwork_scene.dt_tick(0.02)
        assert clockwork_scene.floor_elapsed_time == pytest.approx(0.02)

    def test_floor_caps_its_frame_time_through_the_engine(self):
        """The engine hands dt_tick (and the camera aim) at most 50 ms after a hitch."""
        assert math.isclose(ClockworkKeepScene.MAX_FRAME_SECONDS, 0.05)

    def test_floor_three_scene_renders_a_frame(self, mocker):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 480))
        scene = ClockworkKeepScene(floor_index=2, options={'input_mode': 'joystick'})
        scene.dt_tick(FRAME_TIME)
        surface = pygame.Surface((800, 480))
        scene.all_sprites.draw(surface)
        assert scene.floor_elapsed_time == pytest.approx(FRAME_TIME)

    @pytest.mark.parametrize(('floor_index', 'shows_clock'), [(0, False), (1, False), (2, True)])
    def test_only_the_clock_background_is_animated(self, floor_index, shows_clock):
        """The clock layer draws game time, so it redraws every frame; the walls do not."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 480))
        scene = ClockworkKeepScene(floor_index=floor_index, options={'input_mode': 'joystick'})

        background_layers = [
            sprite for sprite in scene.all_sprites if isinstance(sprite, ParallaxLayer)
        ]

        assert [layer.animated for layer in background_layers] == [shows_clock]

    def test_clock_hands_move_on_a_still_camera(self):
        """The clock redraws with the floor's new elapsed time though the camera stood still."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 480))
        scene = ClockworkKeepScene(floor_index=2, options={'input_mode': 'joystick'})
        (clock_layer,) = [
            sprite for sprite in scene.all_sprites if isinstance(sprite, ParallaxLayer)
        ]
        scene.camera.snap_to(target_x=0.0, target_y=200.0)
        pixels_before = pygame.image.tobytes(clock_layer.image, 'RGBA')

        scene.floor_elapsed_time += 15.0  # the second hand turns a quarter
        scene.camera.snap_to(target_x=0.0, target_y=200.0)

        assert pygame.image.tobytes(clock_layer.image, 'RGBA') != pixels_before

    def test_floor_replay_arguments_rebuild_the_floor(self):
        """replay_arguments() are the floor's constructor arguments as it began."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 480))
        scene = ClockworkKeepScene(
            floor_index=2, player_score=1450, player_lives=2, options={'input_mode': 'joystick'}
        )
        # Scoring on the floor does not change how it began
        scene.player.score += 50
        scene.player.lives -= 1

        assert scene.replay_arguments() == {
            'floor_index': 2,
            'player_score': 1450,
            'player_lives': 2,
        }


class TestStartingFloor:
    """--floor picks the first floor; floors built by the game name theirs (BUGS.md #79)."""

    @pytest.fixture(autouse=True)
    def _display(self):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 480))

    def test_floor_option_picks_the_first_floor(self):
        """The engine builds the first scene from options alone, so --floor must reach it."""
        scene = ClockworkKeepScene(options={'input_mode': 'joystick', 'floor': 1})
        assert scene.floor_index == 1
        assert scene.replay_arguments()['floor_index'] == 1

    def test_no_floor_option_starts_on_the_boiler_room(self):
        scene = ClockworkKeepScene(options={'input_mode': 'joystick'})
        assert scene.floor_index == 0

    def test_explicit_floor_index_wins_over_the_option(self):
        """The elevator and playback rebuilds name the floor; --floor is only the first one."""
        scene = ClockworkKeepScene(floor_index=2, options={'input_mode': 'joystick', 'floor': 1})
        assert scene.floor_index == 2

    @pytest.mark.parametrize('floor_argument', ['-1', '3'])
    def test_floor_option_out_of_range_is_refused(self, floor_argument, capsys):
        parser = argparse.ArgumentParser()
        ClockworkKeepScene.args(parser)
        with pytest.raises(SystemExit):
            parser.parse_args(['--floor', floor_argument])
        assert f"invalid choice: '{floor_argument}'" in capsys.readouterr().err

    def test_floor_option_in_range_parses(self):
        parser = argparse.ArgumentParser()
        ClockworkKeepScene.args(parser)
        assert parser.parse_args(['--floor', '2']).floor == 2


class TestPlatformSupportUsesHitbox:
    """Platforms support the player by its collision rect (hitbox), not its drawn width.

    The tinker figure leaves a 4 px transparent margin on the left of its 28 px image, so
    the difference shows at a platform's right edge.
    """

    PLATFORM_LEFT = 300.0
    PLATFORM_WIDTH = 200
    PLATFORM_TOP = 300.0

    def _stand_past_platform_right_edge(self, scene, *, hitbox_left):
        """Put the drawn player level with a platform, hitbox left edge at hitbox_left."""
        scene.platform_sprites[:] = [
            types.SimpleNamespace(
                world_x=self.PLATFORM_LEFT,
                world_y=self.PLATFORM_TOP,
                rect=pygame.Rect(0, 0, self.PLATFORM_WIDTH, 12),
            )
        ]
        scene.elevator_sprites[:] = []
        player = scene.player
        player.dt_tick(0.0)  # draws the pose; collision rects trim to its visible pixels
        offset_x, offset_y = collision_rect_offset(player)
        player.world_x = float(hitbox_left - offset_x)
        # Hitbox bottom (the visible feet) level with the platform top
        player.world_y = self.PLATFORM_TOP - (offset_y + get_sprite_collision_rect(player).height)
        player.velocity_y = 0.0
        scene._resolve_ground_collision()
        return player

    def test_only_the_transparent_margin_over_the_platform_does_not_support(self, clockwork_scene):
        """Hitbox left edge exactly at the platform's right edge: standing on nothing."""
        platform_right = round(self.PLATFORM_LEFT) + self.PLATFORM_WIDTH
        player = self._stand_past_platform_right_edge(clockwork_scene, hitbox_left=platform_right)
        assert get_sprite_collision_rect(player).left == platform_right
        assert player.world_x < platform_right  # the image's transparent margin still overlaps
        assert not player.on_ground

    def test_one_hitbox_pixel_over_the_platform_supports(self, clockwork_scene):
        """Hitbox one pixel over the platform: on the ground."""
        platform_right = round(self.PLATFORM_LEFT) + self.PLATFORM_WIDTH
        player = self._stand_past_platform_right_edge(
            clockwork_scene, hitbox_left=platform_right - 1
        )
        assert player.on_ground


class TestHitboxLooseEnds:
    """Side walls, standing height and cog pickups use collision rects (hitboxes)."""

    @staticmethod
    def _drawn_player(scene, *, facing_right=True):
        """Draw the tinker so its collision rect trims to its visible pixels.

        Returns:
            The player.

        """
        player = scene.player
        player.facing_right = facing_right
        player.dt_tick(0.0)  # dt_tick draws the pose
        return player

    def test_left_wall_stops_the_hitbox_not_the_image(self, clockwork_scene):
        """Facing right the figure has a 4 px transparent left margin; no gap at the wall."""
        player = self._drawn_player(clockwork_scene, facing_right=True)
        player.world_x = float(PLAYFIELD_LEFT - 20)
        player.dt_tick(0.0)
        assert get_sprite_collision_rect(player).left == PLAYFIELD_LEFT

    def test_right_wall_stops_the_hitbox_not_the_image(self, clockwork_scene):
        """Facing left the 4 px margin is on the right; no gap at the right wall."""
        player = self._drawn_player(clockwork_scene, facing_right=False)
        player.world_x = float(PLAYFIELD_RIGHT)
        player.dt_tick(0.0)
        assert get_sprite_collision_rect(player).right == PLAYFIELD_RIGHT

    def test_landing_puts_the_visible_feet_on_the_platform(self, clockwork_scene):
        """The hitbox bottom (the visible feet) rests on the platform top, no 2 px float."""
        scene = clockwork_scene
        platform_top = 300.0
        scene.platform_sprites[:] = [
            types.SimpleNamespace(
                world_x=300.0, world_y=platform_top, rect=pygame.Rect(0, 0, 200, 12)
            )
        ]
        scene.elevator_sprites[:] = []
        player = self._drawn_player(scene)
        _, offset_y = collision_rect_offset(player)
        hitbox_height = get_sprite_collision_rect(player).height
        player.world_x = 350.0
        player.world_y = platform_top - (offset_y + hitbox_height) + 3  # 3 px into the top
        player.velocity_y = 50.0

        scene._resolve_ground_collision()

        assert player.on_ground
        assert get_sprite_collision_rect(player).bottom == round(platform_top)
        visible = player.image.get_bounding_rect()
        assert round(player.world_y) + visible.bottom == round(platform_top)

    def test_cog_touching_only_the_transparent_margin_is_not_picked_up(
        self, clockwork_scene, played
    ):
        """The cog overlaps the image's transparent left margin, not the hitbox."""
        scene = clockwork_scene
        player = self._drawn_player(scene, facing_right=True)
        player.world_x = 400.0
        player.world_y = 200.0
        cog = scene.collectible_sprites[0]
        cog.dt_tick(0.0)
        hitbox = get_sprite_collision_rect(player)
        cog.world_x = float(hitbox.left - cog.rect.width)  # right edge on the hitbox edge
        cog.world_y = float(hitbox.top + 10)
        cog._base_world_y = cog.world_y
        assert round(player.world_x) < round(cog.world_x) + cog.rect.width  # image overlaps

        scene._check_collectibles()

        assert cog in scene.collectible_sprites
        assert all(call.args[0] != 'cog_pickup' for call in played.call_args_list)

    def test_cog_overlapping_the_hitbox_is_picked_up(self, clockwork_scene, played):
        """One pixel of hitbox overlap collects the cog, through the collision layers."""
        scene = clockwork_scene
        player = self._drawn_player(scene, facing_right=True)
        player.world_x = 400.0
        player.world_y = 200.0
        cog = scene.collectible_sprites[0]
        cog.dt_tick(0.0)
        hitbox = get_sprite_collision_rect(player)
        cog.world_x = float(hitbox.left - cog.rect.width + 1)
        cog.world_y = float(hitbox.top + 10)
        cog._base_world_y = cog.world_y

        scene._check_collectibles()

        assert cog not in scene.collectible_sprites
        assert cog not in scene.collisions.get_layer('cogs').sprites
        played.assert_any_call('cog_pickup')

    def test_player_and_cogs_are_collision_layers(self, clockwork_scene):
        """The overlay shows the same rects the pickups use."""
        assert clockwork_scene.collisions.get_layer('player').sprites == [clockwork_scene.player]
        assert clockwork_scene.collisions.get_layer('cogs').sprites == (
            clockwork_scene.collectible_sprites
        )


def test_two_overlapped_cogs_are_both_collected_in_one_frame(clockwork_scene, played):
    """Collecting one cog (removing it from the layer) must not skip the next one."""
    scene = clockwork_scene
    player = scene.player
    player.dt_tick(0.0)  # dt_tick draws the pose
    player.world_x = 400.0
    player.world_y = 200.0
    hitbox = get_sprite_collision_rect(player)
    first_cog, second_cog = scene.collectible_sprites[:2]
    for cog in (first_cog, second_cog):
        cog.dt_tick(0.0)
        cog.world_x = float(hitbox.left + 2)
        cog.world_y = float(hitbox.top + 10)
        cog._base_world_y = cog.world_y

    scene._check_collectibles()

    assert first_cog not in scene.collectible_sprites
    assert second_cog not in scene.collectible_sprites


class TestEngineWorldSpace:
    """Clockwork Keep's sprites live in world space; the engine aims the camera and places them."""

    @pytest.mark.parametrize('sprite_class', WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__)
    def test_world_sprite_classes_declare_world_space(self, sprite_class):
        assert sprite_class.COORDINATE_SPACE is CoordinateSpace.WORLD

    @pytest.mark.parametrize('sprite_class', WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__)
    def test_no_sprite_class_positions_itself_from_the_camera(self, sprite_class):
        assert not hasattr(sprite_class, 'apply_camera')

    def test_scene_has_no_camera_loop(self):
        assert 'apply_camera_to_sprites' not in vars(ClockworkKeepScene)

    def test_setup_follows_the_player_on_both_axes(self, clockwork_scene):
        clockwork_scene.setup()
        assert clockwork_scene.camera.follow_target is clockwork_scene.player
        assert clockwork_scene.camera.follow_axes is FollowAxes.BOTH

    def test_dt_tick_leaves_the_camera_to_the_engine(self, clockwork_scene):
        """The game no longer calls camera.update(); the engine aims the camera."""
        clockwork_scene.camera.begin_frame()
        camera_position = (clockwork_scene.camera.world_x, clockwork_scene.camera.world_y)
        clockwork_scene.dt_tick(FRAME_TIME)
        assert not clockwork_scene.camera.updated_by_game_this_frame
        assert (clockwork_scene.camera.world_x, clockwork_scene.camera.world_y) == camera_position

    def test_camera_aims_at_the_player(self, clockwork_scene):
        clockwork_scene.setup()
        player = clockwork_scene.player
        assert clockwork_scene.camera_target() == (player.world_x, player.world_y)

    def test_camera_stops_following_at_game_over(self, clockwork_scene, mocker):
        """dt_tick stops after game over, and so does the camera: it follows nothing."""
        mocker.patch.object(clockwork_scene, 'sounds')
        mocker.patch.object(clockwork_scene, '_save_high_score')
        mocker.patch.object(clockwork_scene, '_load_high_scores', return_value=[])
        clockwork_scene.setup()
        clockwork_scene.player.lives = 1
        clockwork_scene._player_die()
        assert clockwork_scene.game_over_triggered
        assert clockwork_scene.camera.follow_target is None
        assert clockwork_scene.camera_target() is None


class TestPoseBeforeCollision:
    """The tinker's pose (its hitbox) is final before collision runs: no one-frame wall lag.

    Each frame runs as the engine runs it: scene logic (dt_tick), then input events, then
    the render phase (the sprite's update()). The hitbox is checked after logic (what
    collision used) and after the render phase (what is drawn and what the debug overlay
    shows).
    """

    @staticmethod
    def _stand_flush_against_wall(scene, *, wall, facing_right):
        """Stand the player on the floor with its hitbox flush against a side wall.

        Returns:
            The player.

        """
        player = scene.player
        for _ in range(30):  # settle onto the floor
            scene.dt_tick(FRAME_TIME)
            player.update()
        player.facing_right = facing_right
        player.dt_tick(0.0)
        player.update()
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = get_sprite_collision_rect(player).width
        if wall == 'left':
            player.world_x = float(PLAYFIELD_LEFT - offset_x)
        else:
            player.world_x = float(PLAYFIELD_RIGHT - (offset_x + hitbox_width))
        scene.dt_tick(FRAME_TIME)
        player.update()
        hitbox = get_sprite_collision_rect(player)
        if wall == 'left':
            assert hitbox.left == PLAYFIELD_LEFT
        else:
            assert hitbox.right == PLAYFIELD_RIGHT
        assert player.on_ground
        return player

    @staticmethod
    def _hitbox_overlaps_a_wall(player):
        hitbox = get_sprite_collision_rect(player)
        return hitbox.left < PLAYFIELD_LEFT or hitbox.right > PLAYFIELD_RIGHT

    @pytest.mark.parametrize('wall', ['left', 'right'])
    @pytest.mark.parametrize('facing_right', [True, False], ids=['facing_right', 'facing_left'])
    @pytest.mark.parametrize('move_key', [pygame.K_LEFT, pygame.K_RIGHT], ids=['left', 'right'])
    def test_turning_and_jumping_at_a_wall_never_puts_the_hitbox_in_it(
        self, clockwork_scene, wall, facing_right, move_key
    ):
        scene = clockwork_scene
        player = self._stand_flush_against_wall(scene, wall=wall, facing_right=facing_right)
        _press_key(scene, move_key)
        overlapping_frames = []
        on_ground_by_frame = []
        for frame_number in range(20):
            scene.dt_tick(FRAME_TIME)
            on_ground_by_frame.append(player.on_ground)
            if self._hitbox_overlaps_a_wall(player):
                overlapping_frames.append((frame_number, 'collision'))
            if frame_number == 0:
                _press_key(scene, pygame.K_SPACE)
            player.update()
            if self._hitbox_overlaps_a_wall(player):
                overlapping_frames.append((frame_number, 'drawn'))
        # Jump pressed during frame 0's events: airborne from frame 1's logic on
        assert on_ground_by_frame[0]
        assert not on_ground_by_frame[1]
        assert overlapping_frames == []

    def test_dt_tick_draws_the_pose_collision_uses(self, clockwork_scene):
        """The image after dt_tick already shows this frame's facing; update() keeps it."""
        scene = clockwork_scene
        player = self._stand_flush_against_wall(scene, wall='left', facing_right=True)
        _press_key(scene, pygame.K_LEFT)
        scene.dt_tick(FRAME_TIME)
        bounds_after_logic = player.image.get_bounding_rect()
        player.update()
        assert not player.facing_right
        assert player.image.get_bounding_rect() == bounds_after_logic
        assert bounds_after_logic.left == 0  # facing left: the transparent margin is on the right


def test_world_shake_on_a_set_up_floor_does_not_warn(clockwork_scene, mocker, caplog):
    """The floor's sprites are world sprites: a WORLD shake moves them, so no misuse warning."""
    clockwork_scene.setup()
    mocker.patch.object(clockwork_scene.scene_manager, 'active_scene', clockwork_scene)
    with caplog.at_level(logging.WARNING):
        clockwork_scene.shake(ELEVATOR_STOP_BOUNCE, targets=ShakeTarget.WORLD)
    assert all('WORLD shake on' not in record.getMessage() for record in caplog.records)


def key_at(*, key: int, scancode: int) -> HashableEvent:
    """Return a key press reporting ``key`` at physical position ``scancode`` (another layout).

    Returns:
        The KEYDOWN event.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, scancode=scancode, mod=0, unicode='')


class TestPositionalKeys:
    """Every control is a physical position (scancode bindings), pause and quit included."""

    @pytest.mark.parametrize(
        ('action', 'scancode', 'qwerty_key'),
        [
            ('move_right', pygame.KSCAN_RIGHT, pygame.K_RIGHT),
            ('move_left', pygame.KSCAN_LEFT, pygame.K_LEFT),
            ('jump', pygame.KSCAN_SPACE, pygame.K_SPACE),
            ('jump', pygame.KSCAN_UP, pygame.K_UP),
            ('interact', pygame.KSCAN_W, pygame.K_w),
            ('run', pygame.KSCAN_LSHIFT, pygame.K_LSHIFT),
        ],
    )
    def test_a_positional_control_is_its_position(
        self, clockwork_scene, action, scancode, qwerty_key
    ):
        actions = clockwork_scene.actions
        assert actions.get_action(key_at(key=pygame.K_F13, scancode=scancode)) == action
        assert actions.get_action(key_at(key=qwerty_key, scancode=pygame.KSCAN_F13)) is None

    @pytest.mark.parametrize(
        ('action', 'scancode', 'qwerty_key'),
        [('pause', pygame.KSCAN_ESCAPE, pygame.K_ESCAPE), ('quit', pygame.KSCAN_Q, pygame.K_q)],
    )
    def test_pause_and_quit_are_positions_too(self, clockwork_scene, action, scancode, qwerty_key):
        actions = clockwork_scene.actions
        assert actions.get_action(key_at(key=pygame.K_F13, scancode=scancode)) == action
        assert actions.get_action(key_at(key=qwerty_key, scancode=pygame.KSCAN_F13)) is None


class TestMovingGear:
    """The moving gear platform: drawn with teeth, moving on a sine path about its centre."""

    @pytest.fixture(autouse=True)
    def _display(self):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=SCREEN_SIZE)

    def test_gear_is_drawn_with_teeth_along_its_top_edge(self):
        gear = MovingGear(world_x=100.0, world_y=200.0, groups=pygame.sprite.LayeredDirty())

        assert gear.image.get_size() == (40, 10)
        tooth_color = (120, 110, 90, 255)
        body_color = (140, 130, 110, 255)
        # A tooth every 8 px (4 px wide, 2 px tall), body color between and below them
        assert tuple(gear.image.get_at((0, 0))) == tooth_color
        assert tuple(gear.image.get_at((3, 1))) == tooth_color
        assert tuple(gear.image.get_at((32, 0))) == tooth_color
        assert tuple(gear.image.get_at((5, 0))) == body_color
        assert tuple(gear.image.get_at((0, 2))) == body_color
        assert (gear.world_x, gear.world_y) == (100.0, 200.0)

    def test_gear_moves_on_a_sine_path_about_its_centre(self):
        gear = MovingGear(
            world_x=100.0,
            world_y=200.0,
            groups=pygame.sprite.LayeredDirty(),
            move_range_x=30.0,
            move_range_y=10.0,
            speed=2.0,
            size=24,
        )
        assert gear.image.get_size() == (24, 6)

        assert (gear.moved_x, gear.moved_y) == (0.0, 0.0)

        gear.dt_tick(0.25)
        assert gear.world_x == pytest.approx(100.0 + 30.0 * math.sin(0.5))
        assert gear.world_y == pytest.approx(200.0 + 10.0 * math.sin(0.5))
        # How far this tick moved it (from its centre, where it starts)
        assert gear.moved_x == pytest.approx(30.0 * math.sin(0.5))
        assert gear.moved_y == pytest.approx(10.0 * math.sin(0.5))

        # A quarter period after the start (timer * speed = pi / 2): the far end of the range
        gear.dt_tick(math.pi / 4 - 0.25)
        assert gear.world_x == pytest.approx(130.0)
        assert gear.world_y == pytest.approx(210.0)
        assert gear.moved_x == pytest.approx(30.0 - 30.0 * math.sin(0.5))


def _jump_height(*, jump_velocity):
    """Return how high a jump lifts the feet (pixels): v squared over 2g."""
    return jump_velocity**2 / (2.0 * GRAVITY)


def _release_key(scene, key):
    scene.on_key_up_event(
        HashableEvent(pygame.KEYUP, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))
    )


class TestClockFaceMovingGear:
    """The Clock Face's final approach rides a moving gear platform from the centre step."""

    # Section 5 of FLOOR_CLOCK_FACE (levels.py): the centre step and the last step
    CENTRE_STEP = (320, 470)
    LAST_STEP = (520, 290)

    @pytest.fixture
    def clock_face_scene(self, mocker):
        """A Clock Face scene with transition_to recorded instead of performed."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=SCREEN_SIZE)
        scene = ClockworkKeepScene(floor_index=2, options={'input_mode': 'joystick'})
        mocker.patch.object(scene, 'transition_to')
        return scene

    @pytest.fixture
    def clock_face_played(self, clock_face_scene, mocker):
        """Record the Clock Face's sound-bank plays without rendering audio."""
        return mocker.patch.object(clock_face_scene.sounds, 'play')

    @staticmethod
    def _platform_at(scene, position):
        (platform,) = [
            platform
            for platform in scene.platform_sprites
            if (platform.world_x, platform.world_y) == position
        ]
        return platform

    @staticmethod
    def _stand_player(scene, *, hitbox_left, surface_top):
        """Stand the drawn player at rest, hitbox left at hitbox_left, feet on surface_top."""
        player = scene.player
        player.dt_tick(0.0)  # draws the pose; collision rects trim to its visible pixels
        offset_x, offset_y = collision_rect_offset(player)
        player.world_x = float(hitbox_left - offset_x)
        player.world_y = surface_top - (offset_y + get_sprite_collision_rect(player).height)
        player.velocity_x = 0.0
        player.velocity_y = 0.0
        player.on_ground = True
        return player

    @staticmethod
    def _feet(player):
        return get_sprite_collision_rect(player).bottom

    def test_only_the_clock_face_has_moving_gears(self):
        """The golden recordings reach floors 0 and 1 only, so their sprites stay unchanged."""
        assert FLOOR_BOILER_ROOM.moving_gears == []
        assert FLOOR_GEAR_WORKS.moving_gears == []
        assert len(FLOOR_CLOCK_FACE.moving_gears) == 1
        assert ALL_FLOORS[2] is FLOOR_CLOCK_FACE

    def test_floor_builds_its_gears_from_the_level_data(self, clock_face_scene):
        (gear_data,) = FLOOR_CLOCK_FACE.moving_gears
        (gear,) = clock_face_scene.moving_gear_sprites

        assert isinstance(gear, MovingGear)
        assert gear in clock_face_scene.all_sprites
        assert clock_face_scene.all_sprites.get_layer_of_sprite(gear) == LAYER_TERRAIN
        assert (gear.world_x, gear.world_y) == (gear_data.world_x, gear_data.world_y)
        assert gear.image.get_size() == (gear_data.size, gear_data.size // 4)

        # A quarter period in, the gear is at the right end of its sweep
        clock_face_scene.dt_tick(math.pi / (2.0 * gear_data.speed))
        assert gear.world_x == pytest.approx(gear_data.world_x + gear_data.move_range_x)
        assert gear.world_y == pytest.approx(gear_data.world_y)

    def test_floors_without_gears_build_none(self, clockwork_scene):
        assert clockwork_scene.moving_gear_sprites == []
        assert not any(isinstance(sprite, MovingGear) for sprite in clockwork_scene.all_sprites)

    def test_the_route_is_within_a_walking_jump(self):
        """Centre step to gear and gear to last step are each within a walking jump's height.

        The centre step to the last step directly is beyond even a running jump, so the gear
        is the way up; at the right end of its sweep the gear stops just short of the last step.
        """
        (gear_data,) = FLOOR_CLOCK_FACE.moving_gears
        walking_jump = _jump_height(jump_velocity=JUMP_VELOCITY)
        running_jump = _jump_height(jump_velocity=JUMP_VELOCITY_RUNNING)
        centre_step_top = self.CENTRE_STEP[1]
        last_step_left, last_step_top = self.LAST_STEP

        assert centre_step_top - gear_data.world_y < walking_jump
        assert gear_data.world_y - last_step_top < walking_jump
        assert centre_step_top - last_step_top > running_jump
        gear_right_at_its_right_end = gear_data.world_x + gear_data.move_range_x + gear_data.size
        assert 0 < last_step_left - gear_right_at_its_right_end <= gear_data.size // 4
        # The left end of the sweep stays clear of the wall: a rider is never carried into it
        assert gear_data.world_x - gear_data.move_range_x - PLAYFIELD_LEFT >= PLAYER_WIDTH

    def test_a_rider_is_carried_and_stays_on_the_gear(self, clock_face_scene, clock_face_played):
        scene = clock_face_scene
        (gear,) = scene.moving_gear_sprites
        player = self._stand_player(
            scene, hitbox_left=round(gear.world_x) + 20, surface_top=gear.world_y
        )
        scene._resolve_ground_collision()
        assert scene.riding_gear is gear
        player_x_from_gear = player.world_x - gear.world_x

        for _ in range(60):
            scene.dt_tick(FRAME_TIME)
            assert player.on_ground
            assert scene.riding_gear is gear
            assert self._feet(player) == get_sprite_collision_rect(gear).top

        # A second's ride moved the gear (and its rider with it) well to the right
        assert gear.world_x > FLOOR_CLOCK_FACE.moving_gears[0].world_x + 100
        assert player.world_x - gear.world_x == pytest.approx(player_x_from_gear)
        # Never left it, so never landed again
        assert [call.args for call in clock_face_played.call_args_list] == []

    def test_jumping_off_leaves_the_gear_behind(self, clock_face_scene):
        scene = clock_face_scene
        (gear,) = scene.moving_gear_sprites
        player = self._stand_player(
            scene, hitbox_left=round(gear.world_x) + 20, surface_top=gear.world_y
        )
        scene._resolve_ground_collision()
        scene.dt_tick(FRAME_TIME)
        player_x_at_takeoff = player.world_x

        _press_key(scene, pygame.K_UP)
        scene.dt_tick(FRAME_TIME)

        assert not player.on_ground
        assert scene.riding_gear is None
        # Standing still in the air: no horizontal input, and the gear no longer carries it
        assert player.world_x == pytest.approx(player_x_at_takeoff)
        assert gear.moved_x != 0.0

    def test_respawning_from_the_gear_rides_nothing(self, clock_face_scene, clock_face_played):
        scene = clock_face_scene
        (gear,) = scene.moving_gear_sprites
        self._stand_player(scene, hitbox_left=round(gear.world_x) + 20, surface_top=gear.world_y)
        scene._resolve_ground_collision()
        scene._respawn_player()

        for _ in range(30):  # the 0.2 s fade out, then the move to the spawn point
            scene.dt_tick(FRAME_TIME)

        assert scene.riding_gear is None
        assert not scene.player.is_respawning

    def test_climbing_the_final_approach_on_the_gear(self, clock_face_scene, clock_face_played):
        """Centre step, hop onto the gear, ride its sweep (the silver cog), hop to the last step."""
        scene = clock_face_scene
        (gear,) = scene.moving_gear_sprites
        centre_step = self._platform_at(scene, self.CENTRE_STEP)
        last_step = self._platform_at(scene, self.LAST_STEP)
        player = self._stand_player(
            scene, hitbox_left=round(centre_step.world_x) + 110, surface_top=centre_step.world_y
        )
        score_before = player.score

        def run_until(condition, *, most_frames):
            for _ in range(most_frames):
                scene.dt_tick(FRAME_TIME)
                if condition():
                    return
            pytest.fail('the condition never held')

        # Wait for the gear to turn back at the right end of its sweep, then hop up onto it
        run_until(lambda: gear.moved_x < 0.0, most_frames=120)
        assert self._feet(player) == round(centre_step.world_y)
        _press_key(scene, pygame.K_UP)
        _release_key(scene, pygame.K_UP)
        run_until(lambda: scene.riding_gear is gear, most_frames=60)

        # Ride it to the left end and back to the right end: the silver cog is on the way
        run_until(lambda: gear.moved_x > 0.0, most_frames=240)
        run_until(lambda: gear.moved_x < 0.0, most_frames=240)
        assert scene.riding_gear is gear
        assert player.score == score_before + COG_SILVER_POINTS

        # Hop right onto the last step as the gear pauses
        _press_key(scene, pygame.K_RIGHT)
        _press_key(scene, pygame.K_UP)
        _release_key(scene, pygame.K_UP)
        run_until(lambda: not player.on_ground, most_frames=5)
        run_until(lambda: player.on_ground, most_frames=60)
        _release_key(scene, pygame.K_RIGHT)

        assert scene.riding_gear is None
        assert self._feet(player) == round(last_step.world_y)
        hitbox = get_sprite_collision_rect(player)
        assert hitbox.right > last_step.world_x
        assert hitbox.left < last_step.world_x + last_step.rect.width

    def test_the_gear_is_drawn_where_the_camera_puts_it(self, clock_face_scene):
        scene = clock_face_scene
        (gear,) = scene.moving_gear_sprites
        scene.dt_tick(0.5)  # off its starting point, at a sub-pixel position
        scene.camera.snap_to(target_x=0.0, target_y=gear.world_y - 200.0)
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=SCREEN_SIZE
        )
        screen = pygame.Surface(SCREEN_SIZE, depth=32)
        scene.render(screen)

        gear_left = snap_to_pixel(gear.world_x, PixelSnapMode.NEAREST_HALF_UP) - snap_to_pixel(
            scene.camera.world_x, PixelSnapMode.NEAREST_HALF_UP
        )
        gear_top = snap_to_pixel(gear.world_y, PixelSnapMode.NEAREST_HALF_UP) - snap_to_pixel(
            scene.camera.world_y, PixelSnapMode.NEAREST_HALF_UP
        )
        assert gear.visible
        assert gear.rect.topleft == (gear_left, gear_top)
        body_color = (140, 130, 110)
        tooth_color = (120, 110, 90)
        gear_width, gear_height = gear.image.get_size()
        # Teeth on its top edge, the body below them and between them, nothing just outside it
        assert tuple(screen.get_at((gear_left, gear_top)))[:3] == tooth_color
        assert tuple(screen.get_at((gear_left + 5, gear_top)))[:3] == body_color
        assert (
            tuple(screen.get_at((gear_left + gear_width - 1, gear_top + gear_height - 1)))[:3]
            == body_color
        )
        assert tuple(screen.get_at((gear_left - 1, gear_top + 5)))[:3] != body_color
        assert tuple(screen.get_at((gear_left, gear_top + gear_height)))[:3] != body_color


class TestTinkerControls:
    """Tinker's own jump and velocity controls."""

    def test_an_airborne_tinker_does_not_jump_again(self, clockwork_scene):
        player = clockwork_scene.player
        player.on_ground = False
        player.velocity_y = 50.0

        player.jump()

        assert player.velocity_y == pytest.approx(50.0)

    def test_velocity_x_is_the_physics_body_velocity(self, clockwork_scene):
        player = clockwork_scene.player
        player.velocity_x = 123.0
        assert player.physics.velocity_x == pytest.approx(123.0)

    @pytest.mark.parametrize(('move', 'expected_sign'), [('move_right', 1.0), ('move_left', -1.0)])
    def test_moving_accelerates_the_tinker(self, clockwork_scene, move, expected_sign):
        player = clockwork_scene.player
        getattr(player, move)(running=True)
        player.physics.tick(0.1)
        assert math.copysign(1.0, player.velocity_x) == expected_sign
        assert player.facing_right is (expected_sign > 0)

        player.stop_horizontal()
        for _ in range(60):
            player.physics.tick(0.1)
        assert player.velocity_x == pytest.approx(0.0)


def test_floor_uses_the_sprite_group_it_is_given(clockwork_scene):
    """A floor built with a sprite group draws its sprites in that group."""
    groups = pygame.sprite.LayeredDirty()
    scene = ClockworkKeepScene(options={'input_mode': 'joystick'}, groups=groups)
    assert scene.all_sprites is groups
    assert scene.player in groups


class TestDeathAndHighScores:
    """Falling into the pit, game over, and the saved high scores (real files in tmp_path)."""

    @pytest.fixture
    def saving_scene(self, clockwork_scene, tmp_path):
        clockwork_scene.saves = DiskSaveManager('clockwork-keep', save_dir=tmp_path)
        return clockwork_scene

    def test_falling_below_the_floor_costs_a_life(self, clockwork_scene, played):
        lives_before = clockwork_scene.player.lives
        clockwork_scene.player.world_y = float(
            clockwork_scene.floor_data.height + PIT_DEATH_THRESHOLD + 100
        )

        clockwork_scene.dt_tick(FRAME_TIME)

        assert clockwork_scene.player.lives == lives_before - 1
        assert clockwork_scene.player.is_respawning
        played.assert_any_call('death')

    def test_dying_after_game_over_changes_nothing(self, clockwork_scene, played):
        clockwork_scene.game_over_triggered = True
        lives_before = clockwork_scene.player.lives

        clockwork_scene._player_die()

        assert clockwork_scene.player.lives == lives_before
        played.assert_not_called()

    def test_first_game_over_saves_its_score_and_shows_it(self, saving_scene, played):
        saving_scene.player.score = 250
        saving_scene.player.lives = 1

        saving_scene._player_die()

        expected_scores = [{'score': 250, 'floor': 0}]
        assert saving_scene.saves.load('high_scores') == {'scores': expected_scores}
        (game_over, _transition), _keywords = saving_scene.transition_to.call_args
        assert isinstance(game_over, GameOverScene)
        assert game_over.final_score == 250
        assert game_over.high_scores == expected_scores

    def test_game_over_keeps_the_ten_best_scores_best_first(self, saving_scene, played):
        earlier_scores = [{'score': score, 'floor': 1} for score in range(100, 1100, 100)]
        saving_scene.saves.save('high_scores', {'scores': earlier_scores})
        saving_scene.player.score = 550
        saving_scene.player.lives = 1

        saving_scene._player_die()

        saved_scores = saving_scene.saves.load('high_scores')['scores']
        assert [entry['score'] for entry in saved_scores] == [
            1000,
            900,
            800,
            700,
            600,
            550,
            500,
            400,
            300,
            200,
        ]
        assert {'score': 550, 'floor': 0} in saved_scores

    def test_no_saved_scores_load_as_none(self, saving_scene):
        assert saving_scene._load_high_scores() == []


class TestFloorInput:
    """Pause, quit, focus loss and gamepad input on a floor."""

    def test_losing_window_focus_pauses(self, clockwork_scene):
        clockwork_scene.on_window_focus_lost_event(HashableEvent(pygame.WINDOWFOCUSLOST))
        assert isinstance(clockwork_scene.next_scene, PauseScene)

    def test_losing_window_focus_after_game_over_does_not_pause(self, clockwork_scene):
        clockwork_scene.game_over_triggered = True
        clockwork_scene.on_window_focus_lost_event(HashableEvent(pygame.WINDOWFOCUSLOST))
        assert clockwork_scene.next_scene is clockwork_scene

    def test_the_pause_key_pauses(self, clockwork_scene):
        _press_key(clockwork_scene, pygame.K_ESCAPE)
        assert isinstance(clockwork_scene.next_scene, PauseScene)

    def test_the_quit_key_ends_the_run(self):
        """Through the engine's frame loop (next_scene = None never ended it)."""
        with _golden_game('clockwork_keep', random_seed=1) as manager:
            pygame.event.post(press(pygame.K_q))
            pygame.event.post(release(pygame.K_q))
            for _ in range(3):
                manager.dt = 1 / 60
                manager.run_frame()
            assert manager.quit_requested

    def test_an_unbound_key_goes_to_the_scene_and_changes_nothing(self, clockwork_scene):
        _press_key(clockwork_scene, pygame.K_F13)
        assert clockwork_scene.next_scene is clockwork_scene
        assert clockwork_scene.player.velocity_y == pytest.approx(0.0)

    def test_joystick_interact_button_is_held_and_does_not_jump(self, clockwork_scene):
        _stand_on_first_elevator(clockwork_scene)
        clockwork_scene.on_joy_button_down_event(
            HashableEvent(
                pygame.JOYBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_Y, joy=0, instance_id=0
            )
        )
        assert clockwork_scene.actions.is_held('interact')
        assert clockwork_scene.player.velocity_y >= 0

    def test_controller_interact_button_is_held_and_does_not_jump(self):
        scene = ClockworkKeepScene(options={'input_mode': 'controller'})
        _stand_on_first_elevator(scene)
        scene.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_Y, instance_id=0
            )
        )
        assert scene.actions.is_held('interact')
        assert scene.player.velocity_y >= 0

    def test_interact_away_from_the_elevators_does_not_ride(self, clockwork_scene):
        for _ in range(5):
            clockwork_scene.dt_tick(FRAME_TIME)  # Standing at the spawn, far from any elevator
        assert clockwork_scene.player.on_ground
        _press_key(clockwork_scene, pygame.K_w)
        clockwork_scene.dt_tick(FRAME_TIME)
        clockwork_scene.transition_to.assert_not_called()

    def test_joystick_button_a_jumps_and_its_release_lets_go(self, clockwork_scene, played):
        _stand_on_first_elevator(clockwork_scene)
        button = pygame.CONTROLLER_BUTTON_A

        clockwork_scene.on_joy_button_down_event(
            HashableEvent(pygame.JOYBUTTONDOWN, button=button, joy=0, instance_id=0)
        )
        assert clockwork_scene.player.velocity_y < 0
        assert clockwork_scene.actions.is_held('jump')
        played.assert_any_call('jump')

        clockwork_scene.on_joy_button_up_event(
            HashableEvent(pygame.JOYBUTTONUP, button=button, joy=0, instance_id=0)
        )
        assert not clockwork_scene.actions.is_held('jump')

    def test_joystick_axis_motion_moves_nothing(self, clockwork_scene):
        """The floor binds no stick axis: the D-pad and keys move the Tinker."""
        clockwork_scene.on_joy_axis_motion_event(
            HashableEvent(pygame.JOYAXISMOTION, axis=0, value=1.0, joy=0, instance_id=0)
        )
        clockwork_scene.dt_tick(FRAME_TIME)
        assert not clockwork_scene.actions.is_held('move_right')
        assert clockwork_scene.player.velocity_x == pytest.approx(0.0)

    def test_controller_button_a_jumps_and_its_release_lets_go(self, mocker):
        scene = ClockworkKeepScene(options={'input_mode': 'controller'})
        played = mocker.patch.object(scene.sounds, 'play')
        _stand_on_first_elevator(scene)
        button = pygame.CONTROLLER_BUTTON_A

        scene.on_controller_button_down_event(
            HashableEvent(pygame.CONTROLLERBUTTONDOWN, button=button, instance_id=0)
        )
        assert scene.player.velocity_y < 0
        assert scene.actions.is_held('jump')
        played.assert_any_call('jump')

        scene.on_controller_button_up_event(
            HashableEvent(pygame.CONTROLLERBUTTONUP, button=button, instance_id=0)
        )
        assert not scene.actions.is_held('jump')


class TestFloorRendering:
    """The floor's frame: the world, then the HUD once setup() has loaded its font."""

    # The score text's place: top left, (10, 10), one line of the 28 px font
    SCORE_AREA = pygame.Rect(10, 10, 100, 20)

    @staticmethod
    def _hud_text_pixel_count(surface, area):
        return sum(
            1
            for x in range(area.left, area.right)
            for y in range(area.top, area.bottom)
            if tuple(surface.get_at((x, y)))[:3] == HUD_TEXT_COLOR
        )

    def _rendered_frame(self, scene):
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=SCREEN_SIZE
        )
        screen = pygame.Surface(SCREEN_SIZE, depth=32)
        scene.render(screen)
        return screen

    def test_floor_draws_the_hud_after_setup(self, clockwork_scene):
        clockwork_scene.setup()
        screen = self._rendered_frame(clockwork_scene)
        assert self._hud_text_pixel_count(screen, self.SCORE_AREA) > 0
        assert clockwork_scene.rects is None  # The whole screen is presented

    def test_floor_rendered_before_setup_draws_no_hud(self, clockwork_scene):
        screen = self._rendered_frame(clockwork_scene)
        assert self._hud_text_pixel_count(screen, self.SCORE_AREA) == 0


GOLDEN_REPLAY_PATH = (
    Path(__file__).parent.parent / 'fixtures' / 'replays' / 'clockwork-keep' / 'golden.jsonl.gz'
)


def test_main_runs_the_game_through_the_engine(mocker, capsys):
    """main() starts Clockwork Keep in the engine: here a headless replay of the golden run.

    GoldenTraceEngine is the GameEngine without the SCALED display flag, which SDL's dummy
    video driver cannot honour; pygame.quit is patched because later tests on this worker
    need pygame (as tests/replay/replay_helpers.replay_through_engine does).
    """
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    mocker.patch.dict(os.environ)  # --headless sets the SDL driver variables
    mocker.patch.object(clockwork_game, 'GameEngine', GoldenTraceEngine)
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
            clockwork_game.main()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()

    assert exit_info.value.code == ExitCode.SUCCESS
    assert 'Replay matched' in capsys.readouterr().out
