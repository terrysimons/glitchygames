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
    STONE_WALL_WIDTH,
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

    def test_fast_player_past_the_wall_centre_is_pushed_back_the_way_it_came(
        self, adventurer_scene
    ):
        """Moving right, a player whose hitbox centre passed the wall's centre goes back left.

        A dt hitch can carry it that far; it must not be pushed through to the far side.
        """
        scene = adventurer_scene
        self._set_up_wall(scene)
        player = self._place_player_on_ground(scene, hitbox_left=0)
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = _player_hitbox(scene).width
        # Hitbox centre 4 px right of the wall's centre
        wall_center = round(self.WALL_X) + STONE_WALL_WIDTH // 2
        player.world_x = float(wall_center + 4 - hitbox_width // 2 - offset_x)
        player.velocity_x = 900.0
        scene.dt = 0.1  # a hitch: 90 px this frame, from clear of the wall on its left

        scene._resolve_player_wall_collision()

        assert _player_hitbox(scene).right == round(self.WALL_X)

    def test_fast_player_moving_left_is_pushed_out_on_the_right(self, adventurer_scene):
        """Moving left with the hitbox centre left of the wall's centre: pushed out right."""
        scene = adventurer_scene
        self._set_up_wall(scene)
        player = self._place_player_on_ground(scene, hitbox_left=0)
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = _player_hitbox(scene).width
        wall_center = round(self.WALL_X) + STONE_WALL_WIDTH // 2
        player.world_x = float(wall_center - 4 - hitbox_width // 2 - offset_x)
        player.velocity_x = -900.0
        scene.dt = 0.1  # a hitch: 90 px this frame, from clear of the wall on its right

        scene._resolve_player_wall_collision()

        assert _player_hitbox(scene).left == round(self.WALL_X) + STONE_WALL_WIDTH

    def test_wider_frame_while_moving_away_is_not_pushed_through_the_wall(self, adventurer_scene):
        """A hitbox that widens into the wall while moving away is pushed back, not through.

        Flush on the wall's left, jumping away left: the wider frame overlaps the wall, and the
        player must end on the left side again, never on the wall's right side.
        """
        scene = adventurer_scene
        self._set_up_wall(scene)
        player = self._place_player_on_ground(scene, hitbox_left=0)
        offset_x, _ = collision_rect_offset(player)
        player.world_x = self.WALL_X - _player_hitbox(scene).width - offset_x
        _widen_player_hitbox(scene, extra_pixels=6)
        player.velocity_x = -200.0
        scene.dt = 1 / 60

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
        # A few frames walking left, then at rest against the edge. Turning or changing pose
        # moves the hitbox inside the image; the bound is refitted from the hitbox each tick,
        # so the edge is exact once the pose settles (Brave Adventurer draws its pose in
        # update(), after dt_tick, so a pose change can lag the bound by one frame).
        for _ in range(3):
            player.velocity_x = -200.0
            player.dt_tick(1 / 60)
            player.update()
        for _ in range(3):
            player.velocity_x = 0.0
            player.dt_tick(1 / 60)
            player.update()
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


class TestPapyrusFacingLeftHitbox:
    """Papyrus flips its image when facing left; the hitbox must be mirrored with it."""

    @pytest.fixture
    def papyrus_scene(self, mocker):
        """A Papyrus scene with a long flat floor and no walls.

        Returns:
            The scene.

        """
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 480))
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        mocker.patch.object(scene, 'sounds')
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=2000)]
        scene.wall_sprites[:] = []
        return scene

    @staticmethod
    def _face_left(scene):
        player = scene.player
        player.facing_right = False
        player.velocity_x = 0.0
        player.dt_tick(0.0)
        return player

    def test_facing_left_hitbox_matches_the_flipped_figure(self, papyrus_scene):
        """Hitbox == the flipped image's visible pixels (Papyrus hitboxes match its art)."""
        player = self._face_left(papyrus_scene)
        visible = player.image.get_bounding_rect()
        hitbox = get_sprite_collision_rect(player)
        assert hitbox.x - round(player.world_x) == visible.x
        assert hitbox.width == visible.width

    def test_facing_right_is_unchanged(self, papyrus_scene):
        """Facing right the hitbox is the TOML hitbox, unmirrored."""
        player = papyrus_scene.player
        player.dt_tick(0.0)
        assert player.hitbox_flip_x is False
        visible = player.image.get_bounding_rect()
        assert get_sprite_collision_rect(player).x - round(player.world_x) == visible.x

    def test_walking_left_into_a_wall_touches_it(self, papyrus_scene):
        """Hitbox left edge and the flipped figure's visible left edge both meet the wall."""
        scene = papyrus_scene
        wall_x = 300.0
        scene.wall_sprites[:] = [
            types.SimpleNamespace(world_x=wall_x, world_y=GROUND_Y - 64.0, wall_height=64)
        ]
        wall_right = round(wall_x) + STONE_WALL_WIDTH
        player = self._face_left(scene)
        player.world_y = float(GROUND_Y - 50)
        offset_x, _ = collision_rect_offset(player)
        player.world_x = float(wall_right - offset_x - 3)  # 3 px into the wall
        player.velocity_x = -200.0

        scene._resolve_player_wall_collision()

        assert get_sprite_collision_rect(player).left == wall_right
        assert round(player.world_x) + player.image.get_bounding_rect().left == wall_right

    def test_world_left_edge_facing_left(self, papyrus_scene):
        """Facing left, the mirrored hitbox stops at the world's left edge."""
        player = self._face_left(papyrus_scene)
        player.world_x = -50.0
        player.velocity_x = -200.0
        player.dt_tick(0.0)
        assert get_sprite_collision_rect(player).left == 0
