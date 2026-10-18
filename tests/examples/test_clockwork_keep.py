"""Tests for the Clockwork Keep example game."""

import pygame
import pytest

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.live import VoiceState
from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.events.base import HashableEvent
from glitchygames.examples.clockwork_keep import sounds as clockwork_sounds
from glitchygames.examples.clockwork_keep.game import ClockworkKeepScene

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
