"""Tests for the Clockwork Keep example game."""

import math

import pygame
import pytest

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.live import VoiceState
from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.events.base import HashableEvent
from glitchygames.examples.clockwork_keep import sounds as clockwork_sounds
from glitchygames.examples.clockwork_keep.constants import (
    CLOCK_START_SECONDS,
    ELEVATOR_ASCENT_RUMBLE_LOW,
)
from glitchygames.examples.clockwork_keep.drawing import clock_hand_angles
from glitchygames.examples.clockwork_keep.game import (
    ELEVATOR_STOP_BOUNCE,
    ELEVATOR_STOP_RATTLE,
    ClockworkKeepScene,
)

FRAME_TIME = 1.0 / 60.0


@pytest.fixture
def clockwork_scene(mocker):
    """A floor-0 scene with transition_to recorded instead of performed."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 480))
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
    scene.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0))


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
            HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode='', scancode=0)
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

    def test_apply_camera_to_sprites_repositions(self, clockwork_scene):
        clockwork_scene.camera.world_y = 37.0
        clockwork_scene.apply_camera_to_sprites()
        platform = clockwork_scene.platform_sprites[0]
        assert platform.rect.y == round(platform.world_y - 37.0)


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

    def test_floor_elapsed_time_uses_capped_dt(self, clockwork_scene):
        clockwork_scene.dt_tick(5.0)
        assert clockwork_scene.floor_elapsed_time == pytest.approx(0.05)

    def test_floor_three_scene_renders_a_frame(self, mocker):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 480))
        scene = ClockworkKeepScene(floor_index=2, options={'input_mode': 'joystick'})
        scene.dt_tick(FRAME_TIME)
        surface = pygame.Surface((800, 480))
        scene.all_sprites.draw(surface)
        assert scene.floor_elapsed_time == pytest.approx(FRAME_TIME)
