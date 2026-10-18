"""Tests for the Brave Adventurer games: death and game-over rumble, terrain hitboxes."""

import math
import types

import pygame
import pytest

from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.examples.brave_adventurer.constants import (
    DEATH_RUMBLE_DURATION,
    DEATH_RUMBLE_HIGH,
    DEATH_RUMBLE_LOW,
    GAME_OVER_RUMBLE_DURATION,
    GAME_OVER_RUMBLE_HIGH,
    GAME_OVER_RUMBLE_LOW,
    GROUND_Y,
)
from glitchygames.examples.brave_adventurer.game import BraveAdventurerScene
from glitchygames.examples.brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.sprites import AnimatedSprite


@pytest.fixture(params=[BraveAdventurerScene, PapyrusBraveAdventurerScene])
def adventurer_scene(request, mocker):
    """Each game's scene with rumble, sounds, respawn and saving replaced by mocks."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 480))
    scene = request.param(options={'input_mode': 'joystick'})
    mocker.patch.object(scene.scene_manager.rumble, 'pulse')
    mocker.patch.object(scene, 'sounds')
    mocker.patch.object(scene, '_respawn_player')
    mocker.patch.object(scene, '_save_high_score', return_value=[])
    return scene


class TestDefaultTargetFps:
    """An explicit --target-fps 0 stays uncapped; the engine default supplies 60.01."""

    def test_setup_keeps_explicit_zero_target_fps_uncapped(self, adventurer_scene):
        adventurer_scene.target_fps = 0
        adventurer_scene.setup()
        assert math.isclose(adventurer_scene.target_fps, 0.0, abs_tol=1e-9)


class TestDeathRumble:
    """Losing a life rumbles; the last life rumbles harder."""

    def test_losing_a_life_pulses_the_death_rumble(self, adventurer_scene):
        adventurer_scene.player.lives = 2
        adventurer_scene._player_die()
        adventurer_scene.scene_manager.rumble.pulse.assert_called_once_with(
            low_frequency=DEATH_RUMBLE_LOW,
            high_frequency=DEATH_RUMBLE_HIGH,
            duration=DEATH_RUMBLE_DURATION,
        )

    def test_last_life_pulses_the_game_over_rumble(self, adventurer_scene):
        adventurer_scene.player.lives = 1
        adventurer_scene._player_die()
        adventurer_scene.scene_manager.rumble.pulse.assert_called_once_with(
            low_frequency=GAME_OVER_RUMBLE_LOW,
            high_frequency=GAME_OVER_RUMBLE_HIGH,
            duration=GAME_OVER_RUMBLE_DURATION,
        )


# --- Terrain resolution uses the player's collision rect (hitbox), not the drawn width ---


def _drawn_player(scene):
    """Tick and draw the player once, as a game frame does, and return it.

    dt_tick sets Papyrus's hitbox_scale; update() draws Brave Adventurer's figure.
    """
    scene.player.dt_tick(0.0)
    scene.player.update()
    return scene.player


def _player_hitbox(scene):
    return get_sprite_collision_rect(scene.player)


def _widen_player_hitbox(scene, extra_pixels):
    """Simulate an animation frame or pose whose hitbox is wider on the right."""
    player = scene.player
    if isinstance(player, AnimatedSprite):
        frame = player.get_current_frame()
        native_hitbox = frame.hitbox if frame.has_explicit_hitbox else player.default_hitbox
        frame.hitbox = pygame.Rect(
            native_hitbox.x,
            native_hitbox.y,
            native_hitbox.width + extra_pixels // player.hitbox_scale,
            native_hitbox.height,
        )
    else:
        visible = player.image.get_bounding_rect()
        player.image.fill(
            (200, 200, 200, 255),
            pygame.Rect(visible.right, visible.centery, extra_pixels, 2),
        )


class TestTerrainUsesHitbox:
    """Walls, ledges and pits are resolved against the collision rect, so no visible gap."""

    WALL_X = 400.0

    def _set_up_wall(self, scene):
        scene.wall_sprites[:] = [
            types.SimpleNamespace(world_x=self.WALL_X, world_y=GROUND_Y - 64.0, wall_height=64)
        ]
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=2000)]

    def _place_player_on_ground(self, scene, *, hitbox_left):
        """Put the player on the ground with its hitbox's left edge at hitbox_left."""
        player = _drawn_player(scene)
        offset_x, _ = collision_rect_offset(player)
        player.world_x = float(hitbox_left - offset_x)
        # Sunk into the ground and falling, so each game snaps it up onto its own foot line
        player.world_y = float(GROUND_Y - 20)
        player.velocity_y = 50.0
        scene._resolve_player_ground_collision()
        return player

    def test_walking_into_a_wall_stops_with_the_hitbox_flush(self, adventurer_scene):
        """Hitbox right edge ends exactly on the wall's left face (no transparent-margin gap)."""
        scene = adventurer_scene
        self._set_up_wall(scene)
        player = self._place_player_on_ground(scene, hitbox_left=0)
        hitbox_width = _player_hitbox(scene).width
        offset_x, _ = collision_rect_offset(player)
        player.world_x = self.WALL_X - hitbox_width - offset_x + 3  # 3 px into the wall
        player.velocity_x = 200.0

        scene._resolve_player_wall_collision()

        assert _player_hitbox(scene).right == round(self.WALL_X)

    def test_wider_frame_while_flush_is_pushed_back_out(self, adventurer_scene):
        """Standing flush, a frame with a wider hitbox must not leave the player in the wall."""
        scene = adventurer_scene
        self._set_up_wall(scene)
        player = self._place_player_on_ground(scene, hitbox_left=0)
        offset_x, _ = collision_rect_offset(player)
        player.world_x = self.WALL_X - _player_hitbox(scene).width - offset_x
        player.velocity_x = 0.0
        scene._resolve_player_wall_collision()
        assert _player_hitbox(scene).right == round(self.WALL_X)

        _widen_player_hitbox(scene, extra_pixels=6)
        assert _player_hitbox(scene).right > round(self.WALL_X)

        scene._resolve_player_wall_collision()

        assert _player_hitbox(scene).right == round(self.WALL_X)

    def test_ledge_falls_only_when_the_hitbox_leaves_the_segment(self, adventurer_scene):
        """Walking right off a ledge: still supported until the hitbox's back edge passes it."""
        scene = adventurer_scene
        self._set_up_wall(scene)
        segment_right = 300
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=segment_right)]
        scene.wall_sprites[:] = []
        player = self._place_player_on_ground(scene, hitbox_left=100)
        assert player.on_ground
        player.velocity_x = 200.0
        offset_x, _ = collision_rect_offset(player)

        player.world_x = float(segment_right - 1 - offset_x)
        scene._resolve_player_ground_collision()
        assert player.on_ground

        player.world_x = float(segment_right - offset_x)
        scene._resolve_player_ground_collision()
        assert not player.on_ground


def _make_scarab(scene):
    """Build each game's scarab, drawn once so its collision rect trims to its pixels.

    Returns:
        The scarab.

    """
    if isinstance(scene, PapyrusBraveAdventurerScene):
        from glitchygames.examples.brave_adventurer_papyrus.enemies import PapyrusScarab

        scarab = PapyrusScarab(500.0, pygame.sprite.LayeredDirty())
        scarab.dt_tick(0.0)
    else:
        from glitchygames.examples.brave_adventurer.enemies import Scarab

        scarab = Scarab(500.0, pygame.sprite.LayeredDirty())
        scarab.update()
    return scarab


class TestHitboxLooseEnds:
    """World edge, standing height and scarab ground contact use collision rects."""

    def test_world_left_edge_stops_the_hitbox(self, adventurer_scene):
        """The player's hitbox, not its transparent margin, meets the world's left edge."""
        player = _drawn_player(adventurer_scene)
        player.world_x = -50.0
        player.velocity_x = -200.0
        player.dt_tick(0.0)
        assert _player_hitbox(adventurer_scene).left == 0

    @pytest.mark.parametrize('adventurer_scene', [BraveAdventurerScene], indirect=True)
    def test_brave_adventurer_feet_stand_on_the_ground(self, adventurer_scene):
        """Brave Adventurer's figure ends 1 px above its 48 px image; the feet touch the ground.

        Papyrus keeps PAPYRUS_PLAYER_HEIGHT as its foot line: its per-frame hitboxes are 24-27
        native rows tall, so standing on the hitbox bottom would bounce between frames.
        """
        scene = adventurer_scene
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=2000)]
        scene.wall_sprites[:] = []
        player = _drawn_player(scene)
        player.world_x = 100.0
        player.world_y = float(GROUND_Y - 40)
        player.velocity_y = 100.0

        scene._resolve_player_ground_collision()

        assert player.on_ground
        assert _player_hitbox(scene).bottom == GROUND_Y
        assert round(player.world_y) + player.image.get_bounding_rect().bottom == GROUND_Y

    def test_scarab_rolls_with_its_visible_bottom_on_the_ground(self, adventurer_scene):
        """The scarab's hitbox bottom (2 px above its image bottom) rests on the ground."""
        scene = adventurer_scene
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=2000)]
        scene.wall_sprites[:] = []
        scarab = _make_scarab(scene)
        scarab.world_y = float(GROUND_Y - 10)
        scarab.velocity_y = 100.0
        scene.enemy_sprites[:] = [scarab]

        scene._resolve_enemy_terrain_collisions()

        assert scarab.on_ground
        assert get_sprite_collision_rect(scarab).bottom == GROUND_Y
