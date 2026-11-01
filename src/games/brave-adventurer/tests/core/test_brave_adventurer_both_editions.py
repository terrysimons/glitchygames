"""Brave Adventurer, both editions: their scenes play by the same rules.

Each test runs on the classic edition (BraveAdventurerScene) and the Papyrus Edition
(PapyrusBraveAdventurerScene) unless it says otherwise: death and game-over rumble, terrain
hitboxes, world space, input, saves, the HUD, each game's main() and its level manager.
"""

import math
import os
import types
from pathlib import Path

import pygame
import pytest

from brave_adventurer import game as brave_adventurer_game
from brave_adventurer.drawing import draw_player
from brave_adventurer.enemies import Scarab
from brave_adventurer.game import BraveAdventurerScene
from brave_adventurer.levels import ClassicLevelManager
from brave_adventurer_core.constants import (
    COLLECTIBLE_SCORE_BONUS,
    DEATH_RUMBLE_DURATION,
    DEATH_RUMBLE_HIGH,
    DEATH_RUMBLE_LOW,
    DISTANCE_SCORE_DIVISOR,
    GAME_OVER_RUMBLE_DURATION,
    GAME_OVER_RUMBLE_HIGH,
    GAME_OVER_RUMBLE_LOW,
    GROUND_Y,
    PIT_EDGE_COLOR,
    PIT_FLOOR_COLOR,
    PIT_WALL_COLOR,
    PIT_WALL_SHADOW,
    SCREEN_WIDTH,
    STONE_WALL_WIDTH,
)
from brave_adventurer_core.levels import LEVEL_1, ScreenData
from brave_adventurer_core.terrain import GroundSegment, StoneWall
from brave_adventurer_papyrus import game as papyrus_game
from brave_adventurer_papyrus.constants import PAPYRUS_PLAYER_HEIGHT
from brave_adventurer_papyrus.enemies import PapyrusScarab
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from brave_adventurer_papyrus.levels import PapyrusLevelManager
from glitchygames.camera import FollowAxes
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.display_mode import set_display_mode
from glitchygames.events.base import HashableEvent
from glitchygames.exit_codes import ExitCode
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode
from glitchygames.replay.tools.golden_traces import (
    GoldenTraceEngine,
    command_line,
    golden_game,
    press,
    release,
)
from glitchygames.scenes import SceneManager
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.sprites import AnimatedSprite
from glitchygames.state import DiskSaveManager
from glitchygames.testing.keys import qwerty_scancode
from glitchygames.world import position_world_sprites
from tests.display_canvas import show_canvas_on_new_display

FRAME_SECONDS = 1 / 60
# The member's golden replays: golden-classic.jsonl.gz, golden-papyrus.jsonl.gz
REPLAY_FIXTURES_DIRECTORY = Path(__file__).parents[1] / 'fixtures' / 'replays'
SCREEN_SIZE = (800, 480)


@pytest.fixture(params=[BraveAdventurerScene, PapyrusBraveAdventurerScene])
def adventurer_scene(request, mocker):
    """Each game's scene with rumble, sounds, respawn and saving replaced by mocks."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=(800, 480))
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

    dt_tick draws Brave Adventurer's pose and sets Papyrus's scale; update() is the
    render phase (Brave Adventurer's respawn fade, Papyrus's animation).
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
            native_hitbox.width + extra_pixels // player.scale,
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
        from brave_adventurer_papyrus.enemies import PapyrusScarab

        scarab = PapyrusScarab(500.0, pygame.sprite.LayeredDirty())
        scarab.dt_tick(0.0)
    else:
        from brave_adventurer.enemies import Scarab

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
        # so the edge is exact once the pose settles (Brave Adventurer refits it after drawing
        # its pose in dt_tick, so its edge is exact on every frame: see the test below).
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
    def test_brave_adventurer_hitbox_never_passes_the_world_left_edge(self, adventurer_scene):
        """Walking left into the edge, turning right and back: the hitbox stays at x >= 0.

        The pose is drawn in dt_tick and the edge refitted to it, so a turn (which moves the
        hitbox inside the image) cannot leave the hitbox past the edge for a frame.
        """
        player = _drawn_player(adventurer_scene)
        player.world_x = 10.0
        hitbox_lefts = []
        for move in [player.move_left] * 20 + [player.move_right] * 2 + [player.move_left] * 5:
            move()
            player.dt_tick(1 / 60)
            hitbox_lefts.append(_player_hitbox(adventurer_scene).left)  # what collision used
            player.update()
            hitbox_lefts.append(_player_hitbox(adventurer_scene).left)  # what is drawn
        assert min(hitbox_lefts) == 0

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


def _tick_like_the_game(scene):
    """One frame: player tick (Brave Adventurer draws its pose here), terrain, render phase.

    Returns:
        True if the player landed this frame (in the air before, on the ground after).

    """
    player = scene.player
    player.velocity_x = 0.0
    player.dt_tick(1 / 60)
    was_in_the_air = not player.on_ground
    scene._resolve_player_ground_collision()
    scene._resolve_player_wall_collision()
    player.update()
    return was_in_the_air and player.on_ground


class TestStableSupportAtEdges:
    """Standing at a ledge or wall-top edge never oscillates between idle and falling.

    Falling poses/frames are wider than idle ones, so support measured with the current
    hitbox would drop an idle player, catch it on the wider falling hitbox, and repeat.
    """

    SEGMENT_LEFT = 300
    SEGMENT_WIDTH = 200

    def _count_landings_at(self, scene, *, start_x, start_y, facing_right):
        player = scene.player
        player.facing_right = facing_right
        player.world_x = float(start_x)
        player.world_y = float(start_y)
        player.velocity_y = 0.0
        for _ in range(20):
            _tick_like_the_game(scene)
        return sum(_tick_like_the_game(scene) for _ in range(40))

    @pytest.mark.parametrize('facing_right', [True, False], ids=['facing_right', 'facing_left'])
    def test_ledge_edges(self, adventurer_scene, facing_right):
        """At every start position around both ends of a ledge: at most one landing."""
        scene = adventurer_scene
        scene.ground_sprites[:] = [
            types.SimpleNamespace(
                world_x=float(self.SEGMENT_LEFT), segment_width=self.SEGMENT_WIDTH
            )
        ]
        scene.wall_sprites[:] = []
        segment_right = self.SEGMENT_LEFT + self.SEGMENT_WIDTH
        starts = [
            *range(self.SEGMENT_LEFT - 50, self.SEGMENT_LEFT + 10),
            *range(segment_right - 40, segment_right + 10),
        ]
        oscillating = []
        for start_x in starts:
            landings = self._count_landings_at(
                scene, start_x=start_x, start_y=GROUND_Y - 49, facing_right=facing_right
            )
            if landings > 1:
                oscillating.append((start_x, landings))
        assert oscillating == []

    @pytest.mark.parametrize('facing_right', [True, False], ids=['facing_right', 'facing_left'])
    def test_wall_top_edges(self, adventurer_scene, facing_right):
        """Standing on a wall top near either edge: at most one landing."""
        scene = adventurer_scene
        wall_x = 400.0
        wall_height = 64
        scene.wall_sprites[:] = [
            types.SimpleNamespace(
                world_x=wall_x, world_y=float(GROUND_Y - wall_height), wall_height=wall_height
            )
        ]
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=2000)]
        wall_left = round(wall_x)
        wall_right = wall_left + STONE_WALL_WIDTH
        oscillating = []
        for start_x in [
            *range(wall_left - 40, wall_left + 8),
            *range(wall_right - 30, wall_right + 10),
        ]:
            landings = self._count_landings_at(
                scene,
                start_x=start_x,
                start_y=GROUND_Y - wall_height - 49,
                facing_right=facing_right,
            )
            if landings > 1:
                oscillating.append((start_x, landings))
        assert oscillating == []


class TestOneDeathPerHit:
    """Touching two enemies in the same collision pass costs one life, not two."""

    def test_two_overlapping_enemies_cost_one_life_and_one_respawn(self, adventurer_scene):
        """Both enemies overlap the player; only the first contact kills."""
        scene = adventurer_scene
        player = _drawn_player(scene)
        player.lives = 3
        hitbox = _player_hitbox(scene)
        enemy_layer = scene.collisions.get_layer('enemies')
        enemy_layer.clear()
        for offset in (0, 4):
            enemy_layer.add(
                types.SimpleNamespace(
                    world_x=float(hitbox.x + offset),
                    world_y=float(hitbox.y),
                    rect=pygame.Rect(0, 0, 10, 10),
                )
            )

        scene._check_enemy_collisions()

        assert player.lives == 2
        scene._respawn_player.assert_called_once()


def _press_key(scene, key):
    scene.on_key_down_event(
        HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))
    )


class TestEngineWorldSpace:
    """The engine aims the camera and places the sprites; the games snap as it draws.

    The scene-level tests run for both editions (Papyrus shares the scene logic's shape); each
    edition's sprite and module scans are in its own tests (classic/, papyrus/), the shared
    primitives' in core/.
    """

    def test_setup_follows_the_player_on_the_x_axis(self, adventurer_scene):
        adventurer_scene.setup()
        assert adventurer_scene.camera.follow_target is adventurer_scene.player
        assert adventurer_scene.camera.follow_axes is FollowAxes.X

    def test_dt_tick_leaves_the_camera_to_the_engine(self, adventurer_scene):
        """The game no longer calls camera.update(); the engine aims the camera."""
        adventurer_scene.camera.begin_frame()
        camera_position = (adventurer_scene.camera.world_x, adventurer_scene.camera.world_y)
        adventurer_scene.dt_tick(FRAME_SECONDS)
        assert not adventurer_scene.camera.updated_by_game_this_frame
        assert (adventurer_scene.camera.world_x, adventurer_scene.camera.world_y) == camera_position

    def test_dt_tick_still_updates_the_distance_score(self, adventurer_scene):
        adventurer_scene.player.world_x = 2000.0
        adventurer_scene.dt_tick(FRAME_SECONDS)
        assert adventurer_scene.player.max_distance >= 2000.0
        assert adventurer_scene.player.score > 0

    def test_camera_aims_at_the_player(self, adventurer_scene):
        adventurer_scene.setup()
        player = adventurer_scene.player
        assert adventurer_scene.camera_target() == (player.world_x, player.world_y)

    def test_camera_stops_following_at_game_over(self, adventurer_scene):
        """dt_tick stops after game over, and so does the camera: it follows nothing."""
        adventurer_scene.setup()
        adventurer_scene.player.lives = 1
        adventurer_scene._player_die()
        assert adventurer_scene.game_over_triggered
        assert adventurer_scene.camera.follow_target is None
        assert adventurer_scene.camera_target() is None

    def test_terrain_collision_snaps_with_the_scene_mode(self, adventurer_scene):
        """Terrain edges are snapped as the engine draws them (FLOOR here), not with round()."""
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        segment_right = 300
        # A segment at 0.6 ends at 300 with FLOOR (300.6 floors to 300); round() gave 301
        adventurer_scene.ground_sprites[:] = [
            types.SimpleNamespace(world_x=0.6, world_y=float(GROUND_Y), segment_width=segment_right)
        ]
        adventurer_scene.wall_sprites[:] = []
        player = _drawn_player(adventurer_scene)
        player.world_y = float(GROUND_Y - 20)
        player.velocity_y = 50.0
        player.velocity_x = 200.0
        support_left, _ = adventurer_scene._player_support_span()
        player.world_x += segment_right - support_left

        adventurer_scene._resolve_player_ground_collision()

        assert not player.on_ground

    def test_wall_collision_snaps_with_the_scene_mode(self, adventurer_scene):
        """A wall at 400.6 has its left face at 400 under FLOOR (round() put it at 401)."""
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        wall_x = 400.6
        adventurer_scene.wall_sprites[:] = [
            types.SimpleNamespace(world_x=wall_x, world_y=GROUND_Y - 64.0, wall_height=64)
        ]
        adventurer_scene.ground_sprites[:] = [
            types.SimpleNamespace(world_x=0.0, world_y=float(GROUND_Y), segment_width=2000)
        ]
        player = _drawn_player(adventurer_scene)
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = _player_hitbox(adventurer_scene).width
        player.world_x = float(400 - hitbox_width - offset_x + 3)  # 3 px into the wall
        player.world_y = float(GROUND_Y - 47)
        player.velocity_x = 200.0

        adventurer_scene._resolve_player_wall_collision()

        assert _player_hitbox(adventurer_scene).right == 400


class TestPoseBeforeCollision:
    """The adventurer's pose (its hitbox) is final before collision runs: no one-frame wall lag.

    Both editions: Brave Adventurer draws its pose in dt_tick, Papyrus advances its animation
    frame there.

    Each frame runs as the engine runs it: scene logic (dt_tick), then input events, then
    the render phase (the sprite's update()). The hitbox is checked after logic (what
    collision used) and after the render phase (what is drawn and what the debug overlay
    shows).
    """

    WALL_X = 400.0
    WALL_HEIGHT = 64

    @pytest.fixture
    def walled_scene(self, adventurer_scene, mocker):
        """Each edition's scene with one long ground segment, one real stone wall, no enemies.

        Returns:
            The scene.

        """
        wall = StoneWall(
            world_x=self.WALL_X, wall_height=self.WALL_HEIGHT, groups=pygame.sprite.LayeredDirty()
        )
        adventurer_scene.wall_sprites[:] = [wall]
        adventurer_scene.ground_sprites[:] = [
            GroundSegment(world_x=0.0, segment_width=2000, groups=pygame.sprite.LayeredDirty())
        ]
        mocker.patch.object(adventurer_scene, '_check_enemy_collisions')
        return adventurer_scene

    def _stand_flush_against_wall(self, scene, *, side, facing_right):
        """Stand the player on the ground with its hitbox flush against a side of the wall.

        Returns:
            The player.

        """
        player = scene.player
        player.world_x = self.WALL_X - 200.0
        for _ in range(30):  # settle onto the ground
            scene.dt_tick(FRAME_SECONDS)
            player.update()
        player.facing_right = facing_right
        player.dt_tick(0.0)
        player.update()
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = get_sprite_collision_rect(player).width
        wall_left = round(self.WALL_X)
        wall_right = wall_left + STONE_WALL_WIDTH
        if side == 'left':
            player.world_x = float(wall_left - (offset_x + hitbox_width))
        else:
            player.world_x = float(wall_right - offset_x)
        scene.dt_tick(FRAME_SECONDS)
        player.update()
        hitbox = get_sprite_collision_rect(player)
        if side == 'left':
            assert hitbox.right == wall_left
        else:
            assert hitbox.left == wall_right
        assert player.on_ground
        return player

    def _hitbox_overlaps_the_wall(self, player):
        hitbox = get_sprite_collision_rect(player)
        wall_rect = pygame.Rect(
            round(self.WALL_X),
            GROUND_Y - self.WALL_HEIGHT,
            STONE_WALL_WIDTH,
            self.WALL_HEIGHT,
        )
        return hitbox.colliderect(wall_rect)

    @pytest.mark.parametrize('side', ['left', 'right'])
    @pytest.mark.parametrize('facing_right', [True, False], ids=['facing_right', 'facing_left'])
    @pytest.mark.parametrize('move_key', [pygame.K_LEFT, pygame.K_RIGHT], ids=['left', 'right'])
    def test_turning_and_jumping_at_a_wall_never_puts_the_hitbox_in_it(
        self, walled_scene, side, facing_right, move_key
    ):
        scene = walled_scene
        player = self._stand_flush_against_wall(scene, side=side, facing_right=facing_right)
        _press_key(scene, move_key)
        overlapping_frames = []
        on_ground_by_frame = []
        for frame_number in range(20):
            scene.dt_tick(FRAME_SECONDS)
            on_ground_by_frame.append(player.on_ground)
            if self._hitbox_overlaps_the_wall(player):
                overlapping_frames.append((frame_number, 'collision'))
            if frame_number == 0:
                _press_key(scene, pygame.K_SPACE)
            player.update()
            if self._hitbox_overlaps_the_wall(player):
                overlapping_frames.append((frame_number, 'drawn'))
        # Jump pressed during frame 0's events: airborne from frame 1's logic on
        assert on_ground_by_frame[0]
        assert not on_ground_by_frame[1]
        assert overlapping_frames == []

    @pytest.mark.parametrize('adventurer_scene', [BraveAdventurerScene], indirect=True)
    def test_dt_tick_draws_the_pose_collision_uses(self, walled_scene):
        """The image after dt_tick already shows this frame's facing; update() keeps it."""
        scene = walled_scene
        player = self._stand_flush_against_wall(scene, side='left', facing_right=True)
        _press_key(scene, pygame.K_LEFT)
        scene.dt_tick(FRAME_SECONDS)
        bounds_after_logic = player.image.get_bounding_rect()
        player.update()
        assert not player.facing_right
        assert player.image.get_bounding_rect() == bounds_after_logic
        facing_left = player.image.copy()
        facing_left.fill((0, 0, 0, 0))
        draw_player(
            facing_left, player.state, facing_right=False, animation_timer=player.animation_timer
        )
        assert bounds_after_logic == facing_left.get_bounding_rect()


class TestPitGapsMatchTheGround:
    """Pit gaps are drawn between the ground segments' drawn rects, so no seam can open."""

    def test_pit_edges_coincide_with_the_drawn_segments_at_a_half_pixel_camera(
        self, adventurer_scene, mocker
    ):
        """Camera at x.5: round(world - camera) and snap(world) - snap(camera) differ by 1 px.

        With the camera at 100.5, round(450 - 100.5) = 350 (half to even) while the engine
        draws the segment edge at 450 - 101 = 349.
        """
        scene = adventurer_scene
        sprite_group = pygame.sprite.LayeredDirty()
        left_segment = GroundSegment(world_x=0.0, segment_width=450, groups=sprite_group)
        right_segment = GroundSegment(world_x=550.0, segment_width=400, groups=sprite_group)
        scene.ground_sprites[:] = [left_segment, right_segment]
        scene.camera.world_x = 100.5
        position_world_sprites(sprites=sprite_group, camera=scene.camera, screen_size=(800, 480))
        draw_rect_spy = mocker.spy(pygame.draw, 'rect')

        scene._draw_pits(pygame.Surface((800, 480)))

        pit_fill_rect = draw_rect_spy.call_args_list[0].args[2]
        assert left_segment.rect.right == 349
        assert pit_fill_rect[0] == left_segment.rect.right
        assert pit_fill_rect[0] + pit_fill_rect[2] == right_segment.rect.left


def key_at(*, key: int, scancode: int) -> HashableEvent:
    """Return a key press reporting ``key`` at physical position ``scancode`` (another layout).

    Returns:
        The KEYDOWN event.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, scancode=scancode, mod=0, unicode='')


class TestPositionalKeys:
    """Every control is a physical position, pause and quit included (both editions)."""

    @pytest.mark.parametrize(
        ('action', 'scancode', 'qwerty_key'),
        [
            ('move_right', pygame.KSCAN_RIGHT, pygame.K_RIGHT),
            ('move_left', pygame.KSCAN_LEFT, pygame.K_LEFT),
            ('jump', pygame.KSCAN_SPACE, pygame.K_SPACE),
            ('jump', pygame.KSCAN_UP, pygame.K_UP),
        ],
    )
    def test_a_positional_control_is_its_position(
        self, adventurer_scene, action, scancode, qwerty_key
    ):
        actions = adventurer_scene.actions
        assert actions.get_action(key_at(key=pygame.K_F13, scancode=scancode)) == action
        assert actions.get_action(key_at(key=qwerty_key, scancode=pygame.KSCAN_F13)) is None

    @pytest.mark.parametrize(
        ('action', 'scancode', 'qwerty_key'),
        [('pause', pygame.KSCAN_ESCAPE, pygame.K_ESCAPE), ('quit', pygame.KSCAN_Q, pygame.K_q)],
    )
    def test_pause_and_quit_are_positions_too(self, adventurer_scene, action, scancode, qwerty_key):
        actions = adventurer_scene.actions
        assert actions.get_action(key_at(key=pygame.K_F13, scancode=scancode)) == action
        assert actions.get_action(key_at(key=qwerty_key, scancode=pygame.KSCAN_F13)) is None


# --- Scene behaviour the golden replays never reach (both editions unless noted) ---

GAME_SCENE_CLASSES = [BraveAdventurerScene, PapyrusBraveAdventurerScene]
BACKGROUND_COLOR = (1, 2, 3)


def _start_display():
    if not pygame.get_init():
        pygame.init()
    # Reopen a display of another size too: the scenes size the pit floor from it, and under
    # pytest another test may have left any size (BUGS.md #211 item 7)
    display_surface = pygame.display.get_surface()
    if display_surface is None or display_surface.get_size() != SCREEN_SIZE:
        # The harness's canvas pattern on it: a new display is black, which its black-frame
        # guard fails
        show_canvas_on_new_display(size=SCREEN_SIZE)


@pytest.fixture(params=GAME_SCENE_CLASSES)
def real_scene(request):
    """Each game's scene with nothing replaced: real sounds, saves, rumble and respawn.

    Returns:
        The scene.

    """
    _start_display()
    return request.param(options={'input_mode': 'joystick'})


def _surface_bytes(surface):
    return pygame.image.tobytes(surface, 'RGBA')


def _filled_surface():
    surface = pygame.Surface(SCREEN_SIZE)
    surface.fill(BACKGROUND_COLOR)
    return surface


def _joystick_button_event(event_type, button):
    return HashableEvent(event_type, joy=0, instance_id=0, button=button)


def _controller_button_event(event_type, button):
    return HashableEvent(event_type, instance_id=0, button=button)


def _player_in_the_air(scene):
    player = _drawn_player(scene)
    player.on_ground = False
    player.velocity_y = 120.0
    return player


class TestSceneConstruction:
    """The scene uses a sprite group it is given, or makes its own."""

    @pytest.mark.parametrize('scene_class', GAME_SCENE_CLASSES, ids=lambda cls: cls.__name__)
    def test_a_given_group_holds_every_sprite(self, scene_class):
        _start_display()
        group = pygame.sprite.LayeredDirty()

        scene = scene_class(options={'input_mode': 'joystick'}, groups=group)

        assert scene.all_sprites is group
        assert scene.player in group
        assert all(enemy in group for enemy in scene.enemy_sprites)


class TestGameOverFreezesTheWorld:
    """After the last life, dt_tick moves nothing and a second death costs nothing."""

    def test_dt_tick_after_game_over_moves_nothing(self, real_scene):
        player = real_scene.player
        real_scene.game_over_triggered = True
        player.velocity_x = 200.0
        player.velocity_y = 300.0
        position = (player.world_x, player.world_y)

        real_scene.dt_tick(FRAME_SECONDS)

        assert (player.world_x, player.world_y) == position

    def test_dying_again_after_game_over_costs_no_life(self, real_scene):
        real_scene.game_over_triggered = True
        real_scene.player.lives = 0

        real_scene._player_die()

        assert real_scene.player.lives == 0


class TestFlatGroundWithoutSegments:
    """A level without ground segments stands the player on an endless flat floor."""

    def test_falling_player_lands_on_the_ground_line(self, real_scene):
        scene = real_scene
        scene.ground_sprites[:] = []
        player = _drawn_player(scene)
        player.world_y = float(GROUND_Y - 20)  # sunk into the floor, falling
        player.velocity_y = 50.0

        scene._resolve_player_ground_collision()

        assert player.on_ground
        assert player.velocity_y == 0.0
        if isinstance(scene, PapyrusBraveAdventurerScene):
            assert player.world_y == GROUND_Y - PAPYRUS_PLAYER_HEIGHT
        else:
            assert _player_hitbox(scene).bottom == GROUND_Y

    def test_rising_player_is_not_caught_by_the_ground_line(self, real_scene):
        scene = real_scene
        scene.ground_sprites[:] = []
        player = _drawn_player(scene)
        player.world_y = float(GROUND_Y - 20)
        player.velocity_y = -50.0

        scene._resolve_player_ground_collision()

        assert not player.on_ground

    def test_no_pits_are_drawn(self, real_scene):
        real_scene.ground_sprites[:] = []
        surface = _filled_surface()
        before = _surface_bytes(surface)

        real_scene._draw_pits(surface)

        assert _surface_bytes(surface) == before

    def test_a_scarab_with_no_ground_rolls_on_the_pit_floor(self, real_scene):
        scene = real_scene
        scene.ground_sprites[:] = []
        scene.wall_sprites[:] = []
        scarab = _make_scarab(scene)
        scarab.world_y = float(scene.screen_height)  # fallen past the pit floor
        scarab.velocity_y = 100.0
        scene.enemy_sprites[:] = [scarab]

        scene._resolve_enemy_terrain_collisions()

        assert scarab.on_ground
        assert scarab.velocity_y == 0.0
        assert get_sprite_collision_rect(scarab).bottom == scene.screen_height


class TestPitWalls:
    """In a pit, the next segment's edge is a wall the player cannot walk through."""

    PIT_RIGHT = 400

    def test_walking_right_in_a_pit_stops_flush_with_the_far_edge(self, real_scene):
        scene = real_scene
        scene.ground_sprites[:] = [
            types.SimpleNamespace(world_x=0.0, segment_width=300),
            types.SimpleNamespace(world_x=float(self.PIT_RIGHT), segment_width=400),
        ]
        scene.wall_sprites[:] = []
        player = _drawn_player(scene)
        player.world_y = float(GROUND_Y + 10)  # down in the pit
        player.velocity_y = 0.0
        player.velocity_x = 200.0
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = _player_hitbox(scene).width
        player.world_x = float(self.PIT_RIGHT - hitbox_width - offset_x + 3)  # 3 px into it

        scene._resolve_player_ground_collision()

        assert not player.on_ground
        assert _player_hitbox(scene).right == self.PIT_RIGHT


class TestHighScores:
    """The last death saves the score to the game's real save files and shows the table."""

    @pytest.fixture
    def saving_scene(self, real_scene, tmp_path):
        """The scene saving to a DiskSaveManager in tmp_path.

        Returns:
            The scene.

        """
        real_scene.saves = DiskSaveManager('brave-adventurer-test', save_dir=tmp_path)
        return real_scene

    def test_first_score_starts_the_table(self, saving_scene, tmp_path):
        saving_scene.player.score = 120
        saving_scene.player.lives = 1

        saving_scene._player_die()

        game_over_scene = saving_scene.next_scene
        assert isinstance(game_over_scene, GameOverScene)
        assert game_over_scene.final_score == 120
        assert game_over_scene.high_scores == [{'score': 120}]
        reread = DiskSaveManager('brave-adventurer-test', save_dir=tmp_path)
        assert reread.load('high_scores') == {'scores': [{'score': 120}]}

    def test_table_keeps_the_ten_best_in_descending_order(self, saving_scene, tmp_path):
        saving_scene.saves.save(
            'high_scores', {'scores': [{'score': score} for score in range(100, 1100, 100)]}
        )
        saving_scene.player.score = 550

        high_scores = saving_scene._save_high_score()

        expected = [{'score': score} for score in (1000, 900, 800, 700, 600, 550, 500, 400)]
        expected += [{'score': 300}, {'score': 200}]
        assert high_scores == expected
        reread = DiskSaveManager('brave-adventurer-test', save_dir=tmp_path)
        assert reread.load('high_scores') == {'scores': expected}


class TestJumpInput:
    """Jump from the keyboard, a controller or a joystick: only from the ground, with a sound."""

    @staticmethod
    def _press_jump(scene, source):
        if source == 'keyboard':
            _press_key(scene, pygame.K_SPACE)
        elif source == 'controller':
            scene.on_controller_button_down_event(
                _controller_button_event(pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLER_BUTTON_A)
            )
        else:
            scene.on_joy_button_down_event(
                _joystick_button_event(pygame.JOYBUTTONDOWN, pygame.CONTROLLER_BUTTON_A)
            )

    @pytest.fixture(params=['keyboard', 'controller', 'joystick'])
    def jump_source(self, request):
        return request.param

    @pytest.fixture
    def jump_scene(self, adventurer_scene, jump_source):
        """The scene bound for the jump source (the controller binds CONTROLLERBUTTON events).

        Returns:
            The scene.

        """
        if jump_source != 'controller':
            return adventurer_scene
        scene = type(adventurer_scene)(options={'input_mode': 'controller'})
        scene.sounds = adventurer_scene.sounds  # the fixture's stand-in for the speakers
        return scene

    def test_jump_from_the_ground_plays_the_jump_sound(self, jump_scene, jump_source):
        player = _drawn_player(jump_scene)
        player.on_ground = True
        player.velocity_y = 0.0

        self._press_jump(jump_scene, jump_source)

        assert player.velocity_y < 0
        assert not player.on_ground
        jump_scene.sounds.play_jump.assert_called_once_with()

    def test_jump_in_the_air_does_nothing(self, jump_scene, jump_source):
        player = _player_in_the_air(jump_scene)

        self._press_jump(jump_scene, jump_source)

        assert player.velocity_y == 120.0
        jump_scene.sounds.play_jump.assert_not_called()

    def test_an_unbound_button_does_nothing(self, jump_scene, jump_source):
        player = _drawn_player(jump_scene)
        player.on_ground = True
        player.velocity_y = 0.0
        unbound_button = pygame.CONTROLLER_BUTTON_X
        if jump_source == 'keyboard':
            jump_scene.on_key_down_event(key_at(key=pygame.K_F13, scancode=pygame.KSCAN_F13))
        elif jump_source == 'controller':
            jump_scene.on_controller_button_down_event(
                _controller_button_event(pygame.CONTROLLERBUTTONDOWN, unbound_button)
            )
        else:
            jump_scene.on_joy_button_down_event(
                _joystick_button_event(pygame.JOYBUTTONDOWN, unbound_button)
            )

        assert player.on_ground
        assert player.velocity_y == 0.0
        assert jump_scene.next_scene is None
        # No quit either (the scene manager's flag: Scene has none, BUGS.md #203)
        assert not jump_scene.scene_manager.quit_requested


class TestQuitKey:
    """Q (by position) ends the run."""

    @pytest.mark.parametrize(
        'scene_class',
        [BraveAdventurerScene, PapyrusBraveAdventurerScene],
        ids=['brave_adventurer', 'brave_adventurer_papyrus'],
    )
    def test_quit_position_ends_the_run(self, scene_class):
        """Through the engine's frame loop (next_scene = None never ended it)."""
        with golden_game(scene_class=scene_class, random_seed=1) as manager:
            pygame.event.post(press(pygame.K_q))
            pygame.event.post(release(pygame.K_q))
            for _ in range(3):
                manager.dt = FRAME_SECONDS
                manager.run_frame()
            assert manager.quit_requested


class TestButtonsAndAxesHoldMovement:
    """A D-pad button held moves the player until released; joystick axes move nothing."""

    def test_holding_the_dpad_walks_right_until_released(self, real_scene):
        scene = real_scene
        player = scene.player
        start_x = player.world_x
        scene.on_joy_button_down_event(
            _joystick_button_event(pygame.JOYBUTTONDOWN, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
        )
        for _ in range(10):
            scene.dt_tick(FRAME_SECONDS)
        assert scene.actions.is_held('move_right')
        assert player.world_x > start_x

        scene.on_joy_button_up_event(
            _joystick_button_event(pygame.JOYBUTTONUP, pygame.CONTROLLER_BUTTON_DPAD_RIGHT)
        )

        assert not scene.actions.is_held('move_right')

    @pytest.mark.parametrize('scene_class', GAME_SCENE_CLASSES, ids=lambda cls: cls.__name__)
    def test_releasing_a_controller_dpad_button_stops_holding(self, scene_class):
        _start_display()
        scene = scene_class(options={'input_mode': 'controller'})
        dpad_right = pygame.CONTROLLER_BUTTON_DPAD_RIGHT
        scene.on_controller_button_down_event(
            _controller_button_event(pygame.CONTROLLERBUTTONDOWN, dpad_right)
        )
        assert scene.actions.is_held('move_right')

        scene.on_controller_button_up_event(
            _controller_button_event(pygame.CONTROLLERBUTTONUP, dpad_right)
        )

        assert not scene.actions.is_held('move_right')

    def test_a_joystick_axis_moves_nothing(self, real_scene):
        """No action is bound to an axis: tilting the stick holds no action."""
        real_scene.on_joy_axis_motion_event(
            HashableEvent(pygame.JOYAXISMOTION, joy=0, instance_id=0, axis=0, value=1.0)
        )

        for action in ('move_right', 'move_left', 'jump'):
            assert not real_scene.actions.is_held(action)


class TestHud:
    """The HUD draws only once setup() has loaded its font."""

    def test_before_setup_nothing_is_drawn(self, real_scene):
        surface = _filled_surface()
        before = _surface_bytes(surface)

        real_scene._draw_hud(surface)

        assert _surface_bytes(surface) == before

    def test_after_setup_score_and_lives_are_drawn(self, real_scene):
        real_scene.setup()
        surface = _filled_surface()
        before = _surface_bytes(surface)

        real_scene._draw_hud(surface)

        assert _surface_bytes(surface) != before


class TestMain:
    """Each game's console script entry point runs the real engine (here a headless replay).

    main() runs with its module's GameEngine replaced by GoldenTraceEngine: the real engine
    opening a plain window, since SDL's dummy video driver warns "no fast renderer available"
    for GameEngine's SCALED window, an error under pytest's filterwarnings.
    """

    @pytest.mark.parametrize(
        ('golden_name', 'game_module'),
        [('golden-classic', brave_adventurer_game), ('golden-papyrus', papyrus_game)],
    )
    def test_main_replays_the_golden_recording(self, mocker, golden_name, game_module):
        mocker.patch.object(game_module, 'GameEngine', GoldenTraceEngine)
        # GameEngine._shutdown quits pygame; later tests on this worker still need it
        mocker.patch('pygame.quit')
        mocker.patch('pygame.display.quit')
        # --headless sets the SDL driver variables; the test's own values come back afterwards
        mocker.patch.dict(os.environ)
        recording = REPLAY_FIXTURES_DIRECTORY / f'{golden_name}.jsonl.gz'
        SceneManager._reset()  # the engine starts from a fresh scene manager, as a process does
        try:
            with (
                command_line([
                    '--log-level',
                    'warning',
                    '--replay-trace',
                    str(recording),
                    '--headless',
                ]),
                pytest.raises(SystemExit) as exit_info,
            ):
                game_module.main()
        finally:
            pygame.event.clear()
            SceneManager._reset()

        assert exit_info.value.code == ExitCode.SUCCESS


class TestLevelManagers:
    """Both editions build the same level data; an enemy type neither knows is left out."""

    @pytest.mark.parametrize(
        ('manager_class', 'scarab_class'),
        [(ClassicLevelManager, Scarab), (PapyrusLevelManager, PapyrusScarab)],
        ids=['ClassicLevelManager', 'PapyrusLevelManager'],
    )
    def test_unknown_enemy_type_is_skipped(self, manager_class, scarab_class):
        _start_display()
        screen = ScreenData(
            ground_segments=[(0, 800)],
            enemies=[('sphinx', 100, {}), ('scarab', 300, {})],
        )

        manager = manager_class(level_data=[screen], groups=pygame.sprite.LayeredDirty())

        assert [type(enemy) for enemy in manager.enemy_sprites] == [scarab_class]

    def test_level_width_spans_every_screen(self):
        _start_display()
        manager = ClassicLevelManager(level_data=LEVEL_1, groups=pygame.sprite.LayeredDirty())

        last_segment = max(manager.ground_sprites, key=lambda segment: segment.world_x)

        assert manager.level_width == len(LEVEL_1) * SCREEN_WIDTH
        assert last_segment.world_x + last_segment.segment_width == manager.level_width


class TestPlayerJump:
    """A player in the air cannot jump again (both editions)."""

    def test_jump_in_the_air_keeps_the_fall(self, real_scene):
        player = _player_in_the_air(real_scene)

        player.jump()

        assert player.velocity_y == 120.0
        assert not player.on_ground


class TestCollectibleBonusIsKept:
    """A gold scarab's bonus stays in the score: score = distance score + bonus points (#204)."""

    def test_collecting_a_gold_scarab_adds_its_bonus_to_the_distance_score(self, real_scene):
        player = real_scene.player
        collectible = next(iter(real_scene.collectible_sprites))
        collectible.world_x = player.world_x
        collectible.base_world_y = player.world_y + 10.0

        real_scene.dt_tick(FRAME_SECONDS)

        assert collectible not in real_scene.collectible_sprites
        assert player.bonus_points == COLLECTIBLE_SCORE_BONUS
        distance_score = round(player.max_distance / DISTANCE_SCORE_DIVISOR)
        assert player.score == distance_score + COLLECTIBLE_SCORE_BONUS

    def test_the_bonus_survives_later_frames(self, real_scene):
        real_scene._on_player_collect(real_scene.player, next(iter(real_scene.collectible_sprites)))

        for _ in range(3):
            real_scene.dt_tick(FRAME_SECONDS)

        distance_score = round(real_scene.player.max_distance / DISTANCE_SCORE_DIVISOR)
        assert real_scene.player.score == distance_score + COLLECTIBLE_SCORE_BONUS


class TestRespawnStopsWalking:
    """Respawning clears the walk target, so the fading player stands still (#206)."""

    def test_a_player_walking_when_it_dies_does_not_walk_on_while_it_fades(self, real_scene):
        player = real_scene.player
        # Walking right as it dies: movement input is skipped while respawning, so the walk
        # target stays whatever it was
        player.move_right()

        real_scene._respawn_player()
        position_at_death = player.world_x
        # The fade out lasts 0.2 s: stay inside it (before the player is repositioned)
        for _ in range(6):
            real_scene.dt_tick(FRAME_SECONDS)

        assert player.is_respawning
        assert player.world_x == pytest.approx(position_at_death)


class TestRespawnNearTheStart:
    """A death within RESPAWN_OFFSET of the start respawns at x 0.0, a float like every x (#230)."""

    def test_the_clamped_respawn_position_is_a_float(self, real_scene):
        player = real_scene.player
        player.world_x = 50.0

        real_scene._respawn_player()
        # Past the 0.2 s fade out, where the player is repositioned
        for _ in range(30):
            real_scene.dt_tick(FRAME_SECONDS)

        assert not player.is_respawning
        assert player.world_x == 0.0
        assert type(player.world_x) is float


class TestScarabInAPitIsDrawn:
    """A scarab that rolled into a pit is drawn over the pit fill, as the player is (#209.5)."""

    @pytest.mark.parametrize(
        ('scene_class', 'scarab_class'),
        [(BraveAdventurerScene, Scarab), (PapyrusBraveAdventurerScene, PapyrusScarab)],
    )
    def test_a_scarab_on_the_pit_floor_is_visible(self, scene_class, scarab_class):
        _start_display()
        # The pit floor is the display's bottom: the game's own 800x480 display, which the
        # scene is rendered to (and presented, as a frame)
        screen = set_display_mode(size=SCREEN_SIZE)
        scene = scene_class(options={'input_mode': 'joystick'})
        scarab = next(enemy for enemy in scene.enemy_sprites if isinstance(enemy, scarab_class))
        # Screen 4's pit runs from world x 3550 to 3650
        scarab.world_x = 3590.0
        scarab.roll_speed = 0.0
        for _ in range(60):
            scarab.dt_tick(FRAME_SECONDS)
            scene._resolve_enemy_terrain_collisions()
        scene.camera.world_x = 3300.0
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=(800, 480)
        )
        scene.all_sprites.update()

        scene.render(screen)

        assert scarab.visible
        assert scarab.rect.top > GROUND_Y  # in the pit, below the ground line
        pit_colors = {PIT_WALL_COLOR, PIT_FLOOR_COLOR, PIT_EDGE_COLOR, PIT_WALL_SHADOW}
        scarab_pixels = {
            tuple(screen.get_at((x, y)))[:3]
            for x in range(scarab.rect.left, scarab.rect.right)
            for y in range(scarab.rect.top, min(scarab.rect.bottom, SCREEN_SIZE[1]))
        }
        assert scarab_pixels - pit_colors


class TestRunningOffALedgeFalls:
    """Running off a ledge shows the falling pose in both editions (#209.7)."""

    @pytest.mark.parametrize('scene_class', GAME_SCENE_CLASSES, ids=lambda cls: cls.__name__)
    def test_running_on_the_ground_stays_running(self, scene_class):
        _start_display()
        scene = scene_class(options={'input_mode': 'joystick'})
        _press_key(scene, pygame.K_RIGHT)

        for _ in range(30):
            scene.dt_tick(FRAME_SECONDS)

        assert scene.player.state_machine.current_state == 'running'


class TestBraveVersionFlag:
    """-v/--version prints the edition's name and version and exits (BUGS.md #178 item 25)."""

    @pytest.mark.parametrize(
        ('game_module', 'expected_output'),
        [
            (brave_adventurer_game, 'Brave Adventurer 1.0\n'),
            (papyrus_game, 'Brave Adventurer: Papyrus Edition 1.0\n'),
        ],
    )
    @pytest.mark.parametrize('version_flag', ['-v', '--version'])
    def test_version_flag_prints_the_version_and_exits(
        self, mocker, capsys, game_module, expected_output, version_flag
    ):
        mocker.patch.object(game_module, 'GameEngine', GoldenTraceEngine)
        # A game that ignored the flag would run its loop here; the flag must exit before start()
        start = mocker.patch.object(GoldenTraceEngine, 'start')
        with command_line([version_flag]), pytest.raises(SystemExit) as exit_info:
            game_module.main()

        assert exit_info.value.code == ExitCode.SUCCESS
        assert capsys.readouterr().out == expected_output
        start.assert_not_called()
