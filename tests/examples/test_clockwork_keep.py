"""Tests for the Clockwork Keep example game."""

import math
import types

import pygame
import pytest

from glitchygames.audio.exceptions import AudioUnavailableError
from glitchygames.audio.live import VoiceState
from glitchygames.camera import FollowAxes
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.effects.shake import Shake, ShakeStyle, ShakeTarget
from glitchygames.events.base import HashableEvent
from glitchygames.examples.clockwork_keep import sounds as clockwork_sounds
from glitchygames.examples.clockwork_keep.constants import (
    CLOCK_START_SECONDS,
    ELEVATOR_ASCENT_RUMBLE_LOW,
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
from glitchygames.examples.clockwork_keep.player import Tinker
from glitchygames.examples.clockwork_keep.terrain import Elevator, MovingGear, Platform
from glitchygames.pixel_snap import PixelSnapMode, snap_to_pixel
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
        assert (clockwork_scene.camera.world_x, clockwork_scene.camera.world_y) == (camera_position)

    def test_camera_aims_at_the_player(self, clockwork_scene):
        clockwork_scene.setup()
        player = clockwork_scene.player
        assert clockwork_scene.camera_target() == (player.world_x, player.world_y)

    def test_camera_stays_still_after_game_over(self, clockwork_scene):
        """dt_tick stops after game over, and so does the camera (it no longer moves)."""
        clockwork_scene.setup()
        clockwork_scene.game_over_triggered = True
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
        assert hitbox.left == PLAYFIELD_LEFT if wall == 'left' else hitbox.right == PLAYFIELD_RIGHT
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
        for frame_number in range(20):
            scene.dt_tick(FRAME_TIME)
            if self._hitbox_overlaps_a_wall(player):
                overlapping_frames.append((frame_number, 'collision'))
            if frame_number == 0:
                _press_key(scene, pygame.K_SPACE)
            player.update()
            if self._hitbox_overlaps_a_wall(player):
                overlapping_frames.append((frame_number, 'drawn'))
        assert player.velocity_y < 0 or not player.on_ground  # it jumped
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
