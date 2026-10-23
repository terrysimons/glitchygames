"""Tests for the Brave Adventurer games: death and game-over rumble, terrain hitboxes."""

import hashlib
import math
import os
import re
import tomllib
import types
from pathlib import Path

import pygame
import pytest
from scripts.record_golden_traces import GoldenTraceEngine, command_line
from scripts.record_scripted_session import REPLAY_FIXTURE_DIRECTORY

from glitchygames.animation.state_machine import AnimationStateMachine
from glitchygames.audio import VoiceAssistant
from glitchygames.camera import FollowAxes
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.events.base import HashableEvent
from glitchygames.examples import brave_adventurer as brave_adventurer_package
from glitchygames.examples import brave_adventurer_papyrus as papyrus_package
from glitchygames.examples.brave_adventurer import game as brave_adventurer_game
from glitchygames.examples.brave_adventurer.constants import (
    DEATH_RUMBLE_DURATION,
    DEATH_RUMBLE_HIGH,
    DEATH_RUMBLE_LOW,
    GAME_OVER_RUMBLE_DURATION,
    GAME_OVER_RUMBLE_HIGH,
    GAME_OVER_RUMBLE_LOW,
    GROUND_Y,
    SCREEN_WIDTH,
    STONE_WALL_WIDTH,
)
from glitchygames.examples.brave_adventurer.drawing import (
    draw_dunes_and_oasis,
    draw_near_ground_details,
    draw_player,
    draw_pyramids,
    draw_sky,
)
from glitchygames.examples.brave_adventurer.enemies import Cobra, Scarab, Scorpion
from glitchygames.examples.brave_adventurer.game import (
    MIC_BUTTON_CONTROLLER,
    MIC_BUTTON_JOYSTICK,
    BraveAdventurerScene,
)
from glitchygames.examples.brave_adventurer.levels import LEVEL_1, LevelManager, ScreenData
from glitchygames.examples.brave_adventurer.player import Player
from glitchygames.examples.brave_adventurer.terrain import GoldScarab, GroundSegment, StoneWall
from glitchygames.examples.brave_adventurer_papyrus import game as papyrus_game
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    FALLING_VELOCITY_THRESHOLD as PAPYRUS_FALLING_VELOCITY_THRESHOLD,
)
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    PAPYRUS_PLAYER_HEIGHT,
    SPRITES_DIR,
)
from glitchygames.examples.brave_adventurer_papyrus.enemies import (
    PapyrusCobra,
    PapyrusScarab,
    PapyrusScorpion,
)
from glitchygames.examples.brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.examples.brave_adventurer_papyrus.levels import PapyrusLevelManager
from glitchygames.examples.brave_adventurer_papyrus.player import PapyrusPlayer
from glitchygames.examples.brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
    prepare_papyrus_sprite,
)
from glitchygames.examples.brave_adventurer_papyrus.terrain import PapyrusGoldScarab
from glitchygames.exit_codes import ExitCode
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode, snap_to_pixel
from glitchygames.scenes import SceneManager
from glitchygames.scenes.builtin_scenes.game_over_scene import GameOverScene
from glitchygames.sprites import AnimatedSprite, FrameAnchor
from glitchygames.state import DiskSaveManager
from glitchygames.testing.keys import qwerty_scancode
from glitchygames.world import CoordinateSpace, position_world_sprites, screen_position_for

FRAME_SECONDS = 1 / 60
BRAVE_ADVENTURER_PACKAGE = Path(brave_adventurer_package.__file__).parent
BRAVE_WORLD_SPRITE_CLASSES = (Player, GroundSegment, StoneWall, GoldScarab, Cobra, Scarab, Scorpion)
PAPYRUS_PACKAGE = Path(papyrus_package.__file__).parent
PAPYRUS_WORLD_SPRITE_CLASSES = (
    PapyrusPlayer,
    PapyrusCobra,
    PapyrusScarab,
    PapyrusScorpion,
    PapyrusGoldScarab,
)
SCREEN_SIZE = (800, 480)


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

    dt_tick draws Brave Adventurer's pose and sets Papyrus's hitbox_scale; update() is the
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
        # The image is drawn at rect = position + draw_offset (BOTTOM frame anchoring)
        assert hitbox.x - round(player.world_x) == visible.x + player.draw_offset[0]
        assert hitbox.width == visible.width

    def test_facing_right_is_unchanged(self, papyrus_scene):
        """Facing right the hitbox is the TOML hitbox, unmirrored."""
        player = papyrus_scene.player
        player.dt_tick(0.0)
        assert player.hitbox_flip_x is False
        visible = player.image.get_bounding_rect()
        drawn_left = visible.x + player.draw_offset[0]
        assert get_sprite_collision_rect(player).x - round(player.world_x) == drawn_left

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
        drawn_left = round(player.world_x) + player.draw_offset[0]
        assert drawn_left + player.image.get_bounding_rect().left == wall_right

    def test_world_left_edge_facing_left(self, papyrus_scene):
        """Facing left, the mirrored hitbox stops at the world's left edge."""
        player = self._face_left(papyrus_scene)
        player.world_x = -50.0
        player.velocity_x = -200.0
        player.dt_tick(0.0)
        assert get_sprite_collision_rect(player).left == 0


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


class TestPapyrusFeetAnchoring:
    """Papyrus frames stand their visible feet on one fixed foot line.

    The frames are top-aligned with different visible bottoms; each is drawn lower by its
    anchor offset, and its hitbox moves with it.
    """

    @pytest.fixture
    def standing_player(self, mocker):
        """A Papyrus player standing on a long flat floor, facing right.

        Returns:
            The (scene, player) pair.

        """
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 480))
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        mocker.patch.object(scene, 'sounds')
        scene.ground_sprites[:] = [types.SimpleNamespace(world_x=0.0, segment_width=4000)]
        scene.wall_sprites[:] = []
        player = scene.player
        player.world_x = 200.0
        player.world_y = float(GROUND_Y - PAPYRUS_PLAYER_HEIGHT)
        return scene, player

    @staticmethod
    def _all_frames(player):
        return [
            (animation_name, frame_index)
            for animation_name, frames in player.animation_data.items()
            for frame_index in range(len(frames))
        ]

    def test_foot_row_is_the_sprite_hitbox_bottom_and_the_tallest_frame(self, standing_player):
        """The [sprite.hitbox] bottom and the tallest frame's hitbox bottom agree: 27 rows."""
        _, player = standing_player
        tallest_bottom = max(
            frame.hitbox.bottom
            for frames in player.animation_data.values()
            for frame in frames
            if frame.has_explicit_hitbox
        )
        assert player.default_hitbox is not None
        assert player.default_hitbox.bottom == tallest_bottom == 27
        assert player.frame_anchor is FrameAnchor.BOTTOM
        assert player.hitbox_scale * 27 == PAPYRUS_PLAYER_HEIGHT

    def test_every_frame_stands_its_visible_feet_on_the_ground(self, standing_player):
        """Lowest visible row on screen == ground line - 1 and hitbox bottom == ground line."""
        scene, player = standing_player
        misplaced = []
        for animation_name, frame_index in self._all_frames(player):
            player.set_animation(animation_name)
            player.set_frame(frame_index)
            apply_transparency_and_scale(player)
            # The engine places the player: snap(world) - snap(camera) plus the frame's offset
            position_world_sprites(sprites=[player], camera=scene.camera, screen_size=SCREEN_SIZE)
            screen_ground = GROUND_Y - snap_to_pixel(
                scene.camera.world_y, PixelSnapMode.NEAREST_HALF_UP
            )
            lowest_visible_row = (
                player.rect.y
                + player.image.get_bounding_rect().bottom
                - 1
                + GROUND_Y
                - screen_ground
            )
            hitbox_bottom = get_sprite_collision_rect(player).bottom
            if (lowest_visible_row, hitbox_bottom) != (GROUND_Y - 1, GROUND_Y):
                misplaced.append((animation_name, frame_index, lowest_visible_row, hitbox_bottom))
        assert misplaced == []

    def test_head_bob_is_the_frame_anchor_offset(self, standing_player):
        """Each frame is drawn (27 - its hitbox bottom) * 2 px lower: idle 0, running 4-6."""
        _, player = standing_player
        offsets = {}
        for animation_name, frame_index in self._all_frames(player):
            player.set_animation(animation_name)
            player.set_frame(frame_index)
            frame = player.get_current_frame()
            offsets[animation_name, frame_index] = player.draw_offset
            # BOTTOM moves frames only vertically: no horizontal shift per frame
            assert player.draw_offset == (0, (27 - frame.hitbox.bottom) * 2)
        assert offsets['idle', 0] == (0, 0)

    def test_running_cycle_never_leaves_the_ground(self, standing_player):
        """Running across flat ground through every run frame: on_ground stays True."""
        scene, player = standing_player
        scene._resolve_player_ground_collision()
        grounded_frames = []
        for _ in range(120):
            player.velocity_x = 220.0
            player.dt_tick(1 / 60)
            scene._resolve_player_ground_collision()
            scene._resolve_player_wall_collision()
            grounded_frames.append(player.on_ground)
        assert all(grounded_frames)


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


class _RecordingSprite:
    """Minimal sprite that records which animation the state machine plays."""

    def __init__(self) -> None:
        self.played_animations: list[str] = []

    def play(self, animation_name: str) -> None:
        self.played_animations.append(animation_name)


class TestPapyrusFallingTransitions:
    """Papyrus declares its falling transitions in player.toml, not in code."""

    @pytest.fixture
    def transitions(self):
        with (SPRITES_DIR / 'player.toml').open('rb') as toml_file:
            return tomllib.load(toml_file)['transition']

    def test_falling_transitions_are_declared_in_toml(self, transitions):
        expected_when = f'velocity_y > {PAPYRUS_FALLING_VELOCITY_THRESHOLD} and not on_ground'
        falling_sources = [
            transition['from'] for transition in transitions if transition['to'] == 'falling'
        ]
        assert falling_sources == ['idle', 'jumping']
        for transition in transitions:
            if transition['to'] == 'falling':
                assert transition['when'] == expected_when

    def test_toml_threshold_equals_constant(self, transitions):
        for transition in transitions:
            if transition['to'] == 'falling':
                threshold_text = transition['when'].split()[2]
                assert float(threshold_text) == pytest.approx(PAPYRUS_FALLING_VELOCITY_THRESHOLD)

    def test_falling_comes_after_other_rules_from_same_state(self, transitions):
        for source in ('idle', 'jumping'):
            targets = [
                transition['to'] for transition in transitions if transition['from'] == source
            ]
            assert targets[-1] == 'falling'

    def test_player_has_no_code_defined_falling_transitions(self):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode((800, 480))
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        state_machine = scene.player.state_machine
        assert state_machine is not None
        falling_conditions = [
            transition.condition
            for transition in state_machine._transitions
            if transition.to_state == 'falling'
        ]
        assert len(falling_conditions) == 2
        for condition in falling_conditions:
            assert type(condition).__module__ == 'glitchygames.animation.expressions'

    def test_state_machine_idle_to_falling(self, transitions):
        sprite = _RecordingSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml(transitions)
        state_machine.set_state('idle')
        state_machine.evaluate({'velocity_x': 0.0, 'velocity_y': 20.0, 'on_ground': False})
        assert state_machine.current_state == 'falling'

    def test_state_machine_jumping_to_falling(self, transitions):
        sprite = _RecordingSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml(transitions)
        state_machine.set_state('jumping')
        state_machine.evaluate({'velocity_x': 0.0, 'velocity_y': 20.0, 'on_ground': False})
        assert state_machine.current_state == 'falling'

    def test_standing_still_on_ground_stays_idle(self, transitions):
        sprite = _RecordingSprite()
        state_machine = AnimationStateMachine(sprite)
        state_machine.load_from_toml(transitions)
        state_machine.set_state('idle')
        state_machine.evaluate({'velocity_x': 0.0, 'velocity_y': 20.0, 'on_ground': True})
        assert state_machine.current_state == 'idle'


@pytest.fixture
def brave_scene(mocker):
    """A Brave Adventurer scene with sounds, rumble and saving mocked."""
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((800, 480))
    scene = BraveAdventurerScene(options={'input_mode': 'joystick'})
    mocker.patch.object(scene.scene_manager.rumble, 'pulse')
    mocker.patch.object(scene, 'sounds')
    mocker.patch.object(scene, '_save_high_score', return_value=[])
    return scene


def _press_key(scene, key):
    scene.on_key_down_event(
        HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=qwerty_scancode(key=key))
    )


class TestEngineWorldSpace:
    """Brave Adventurer's sprites are world sprites; the engine aims the camera and places them.

    The scene-level tests run for both editions (Papyrus shares the scene logic's shape).
    """

    @pytest.mark.parametrize(
        'sprite_class', BRAVE_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_world_sprite_classes_declare_world_space(self, sprite_class):
        assert sprite_class.COORDINATE_SPACE is CoordinateSpace.WORLD

    @pytest.mark.parametrize(
        'sprite_class', BRAVE_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_no_sprite_class_positions_itself_from_the_camera(self, sprite_class):
        assert not hasattr(sprite_class, 'apply_camera')

    @pytest.mark.parametrize(
        'source_path', sorted(BRAVE_ADVENTURER_PACKAGE.glob('*.py')), ids=lambda path: path.name
    )
    def test_no_module_culls_or_positions_sprites_itself(self, source_path):
        """Culling and positioning are the engine's; only the pit gaps still use camera.apply."""
        source = source_path.read_text(encoding='utf-8')
        assert 'is_visible' not in source
        assert 'apply_camera' not in source

    def test_scene_has_no_camera_loop(self):
        assert '_follow_player_with_camera' not in vars(BraveAdventurerScene)

    def test_ground_segment_has_its_world_y(self):
        segment = GroundSegment(
            world_x=40.0, segment_width=100, groups=pygame.sprite.LayeredDirty()
        )
        assert segment.world_y == GROUND_Y

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


class TestPapyrusEngineWorldSpace:
    """Papyrus's own sprites are world sprites too: no Papyrus sprite positions itself."""

    @pytest.mark.parametrize(
        'sprite_class', PAPYRUS_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_world_sprite_classes_declare_world_space(self, sprite_class):
        assert sprite_class.COORDINATE_SPACE is CoordinateSpace.WORLD

    @pytest.mark.parametrize(
        'sprite_class', PAPYRUS_WORLD_SPRITE_CLASSES, ids=lambda cls: cls.__name__
    )
    def test_no_sprite_class_positions_itself_from_the_camera(self, sprite_class):
        assert not hasattr(sprite_class, 'apply_camera')

    @pytest.mark.parametrize(
        'source_path', sorted(PAPYRUS_PACKAGE.glob('*.py')), ids=lambda path: path.name
    )
    def test_no_module_culls_positions_or_rounds_world_positions(self, source_path):
        """Culling, positioning and snapping are the engine's (pit gaps use the drawn rects)."""
        source = source_path.read_text(encoding='utf-8')
        assert 'is_visible' not in source
        assert 'apply_camera' not in source
        assert 'camera.apply(' not in source
        assert re.search(r'rect\.(x|y|topleft)\s*=', source) is None
        assert re.search(r'round\([^()]*world_[xy]', source) is None

    def test_scene_has_no_camera_loop(self):
        assert '_follow_player_with_camera' not in vars(PapyrusBraveAdventurerScene)

    def test_foot_line_snaps_with_the_scene_mode(self, mocker):
        """The foot line is the snapped world y + PAPYRUS_PLAYER_HEIGHT, snapped as drawn.

        At y = GROUND_Y - PAPYRUS_PLAYER_HEIGHT - 0.4, FLOOR puts the feet 1 px above the
        ground (not landed yet); round() put them on it.
        """
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode(SCREEN_SIZE)
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        mocker.patch.object(scene, 'sounds')
        scene.ground_sprites[:] = [
            types.SimpleNamespace(world_x=0.0, world_y=float(GROUND_Y), segment_width=2000)
        ]
        scene.wall_sprites[:] = []
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        player = scene.player
        player.world_x = 200.0
        player.world_y = GROUND_Y - PAPYRUS_PLAYER_HEIGHT - 0.4
        player.velocity_y = 10.0

        scene._resolve_player_ground_collision()

        assert not player.on_ground

    def test_player_rect_is_the_engine_position_with_the_frame_draw_offset(self):
        """The engine adds the anchored frame's draw_offset once; Papyrus adds nothing itself."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode(SCREEN_SIZE)
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        player = scene.player
        player.set_animation('running')
        player.set_frame(1)
        apply_transparency_and_scale(player)
        draw_offset_x, draw_offset_y = player.draw_offset
        assert draw_offset_y != 0  # a running frame is drawn lower than the idle one
        player.world_x = 200.4
        player.world_y = 312.5
        scene.camera.world_x = 50.6

        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=SCREEN_SIZE
        )

        mode = PixelSnapMode.NEAREST_HALF_UP
        assert player.rect.topleft == screen_position_for(sprite=player, camera=scene.camera)
        assert player.rect.topleft == (
            snap_to_pixel(200.4, mode) - snap_to_pixel(50.6, mode) + draw_offset_x,
            snap_to_pixel(312.5, mode) - snap_to_pixel(scene.camera.world_y, mode) + draw_offset_y,
        )

    def test_off_screen_enemy_is_culled_by_the_engine_and_keeps_redrawing(self):
        """Engine culling hides an enemy beyond the margin and never sets dirty = 0."""
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            pygame.display.set_mode(SCREEN_SIZE)
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        scarab = PapyrusScarab(world_x=1000.0, groups=scene.all_sprites)

        scene.camera.world_x = scarab.world_x + 5000.0  # far off screen
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=SCREEN_SIZE
        )
        assert not scarab.visible
        assert scarab.dirty == 2

        scene.camera.world_x = scarab.world_x - 100.0  # back on screen
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=SCREEN_SIZE
        )
        assert scarab.visible
        assert scarab.dirty == 2


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


class TestEngineCullingKeepsEnemiesAnimated:
    """Off-screen enemies keep animating: engine culling never sets dirty = 0.

    The old per-sprite culling set dirty = 0 on a culled sprite, and Scene.update() calls
    update() only on dirty sprites, so an enemy that had been off screen drew once on coming
    back and then froze.
    """

    SCREEN_SIZE = (800, 480)

    def _position(self, scene, *, camera_x):
        scene.camera.world_x = camera_x
        position_world_sprites(
            sprites=scene.all_sprites, camera=scene.camera, screen_size=self.SCREEN_SIZE
        )

    def test_scarab_redraws_after_being_off_screen(self, brave_scene):
        scene = brave_scene
        scarab = Scarab(world_x=1000.0, groups=scene.all_sprites)
        scarab.roll_angle = 0.0

        self._position(scene, camera_x=scarab.world_x + 5000.0)  # far off screen
        assert not scarab.visible
        assert scarab.dirty == 2

        self._position(scene, camera_x=scarab.world_x - 100.0)  # back on screen
        assert scarab.visible
        assert scarab.dirty == 2
        scene.update()
        first_image = pygame.image.tobytes(scarab.image, 'RGBA')

        scarab.roll_angle = 1.2  # the wing line leans 3 px: a different picture
        self._position(scene, camera_x=scarab.world_x - 100.0)
        scene.update()

        assert scarab.dirty == 2
        assert pygame.image.tobytes(scarab.image, 'RGBA') != first_image


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


# Pixel digests of the parallax layers as drawn by the per-column / per-row drawing code these
# functions replaced (recorded 2026-10-22 from that code, before the cached-gradient and
# filled-run rewrite). Key: (function name, surface size, camera offset); the layer is drawn
# onto a cleared SRCALPHA surface with camera_y = camera offset / 2 (unused by these layers).
# Sizes: the game's screen, an odd size, and one shorter than the horizon and the dunes.
# Offsets are what ParallaxLayer.update_scroll passes: a snapped camera position times the
# layer's scroll factor, so fractional, negative (a shaken camera at the left bound) and large.
PARALLAX_DRAWING_GOLDEN_DIGESTS = {
    ('draw_sky', (800, 480), 0.0): '54327c311f76800e3d64d596d6558789',
    ('draw_sky', (513, 397), 0.0): '1db6d9aa7ffd1d031ced02714130a8cb',
    ('draw_sky', (300, 240), 0.0): '6483e81a0edf0e5465a7df352feeb06f',
    ('draw_pyramids', (800, 480), 0.0): 'f01ddcac601adb6f6df019738c08eb3e',
    ('draw_pyramids', (800, 480), 0.3): 'f01ddcac601adb6f6df019738c08eb3e',
    ('draw_pyramids', (800, 480), 12.3): '22093d59ffc45e1ff61a64a67b4e8b87',
    ('draw_pyramids', (800, 480), 700.7): 'c696cd257491f13dc93896c1201bd087',
    ('draw_pyramids', (800, 480), 2399.9): 'f01ddcac601adb6f6df019738c08eb3e',
    ('draw_pyramids', (800, 480), 3001.5): '977c85de6310bba303411cdada9f8ee7',
    ('draw_pyramids', (800, 480), 100000.3): 'ad12fbfea75a7ce6613ed134f651600f',
    ('draw_pyramids', (800, 480), -0.7): 'e082d29596c5c1efaa93295397a933ab',
    ('draw_pyramids', (800, 480), -250.0): 'b28fcb98dc50c224aa3084f764ba339f',
    ('draw_pyramids', (513, 397), 0.0): '95e48bb56432931707c5483b2123d9c6',
    ('draw_pyramids', (513, 397), 0.3): '95e48bb56432931707c5483b2123d9c6',
    ('draw_pyramids', (513, 397), 12.3): 'd4deaeb8276d905cdcfda4922d16b64d',
    ('draw_pyramids', (513, 397), 700.7): 'd0280ca820ec14ca7038f64a26f62c6c',
    ('draw_pyramids', (513, 397), 2399.9): '95e48bb56432931707c5483b2123d9c6',
    ('draw_pyramids', (513, 397), 3001.5): '65db89d687314e31ded4fc35e3124465',
    ('draw_pyramids', (513, 397), 100000.3): '50da6f41b04b448e09a742ed1ebf2231',
    ('draw_pyramids', (513, 397), -0.7): 'f8a0f3978c2b9dab42972b27ff883e84',
    ('draw_pyramids', (513, 397), -250.0): '13cfc490cfb9f97a89a73d9c1ca417bb',
    ('draw_pyramids', (300, 240), 0.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 0.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 12.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 700.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 2399.9): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 3001.5): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), 100000.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), -0.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_pyramids', (300, 240), -250.0): '0c88d932bf1a2aa2833e27e1a7d33e1e',
    ('draw_dunes_and_oasis', (800, 480), 0.0): 'ba2d90f47217e92dffdb74963ca19d21',
    ('draw_dunes_and_oasis', (800, 480), 0.3): '9cbc314220d61efeb75820ad9fb654d0',
    ('draw_dunes_and_oasis', (800, 480), 12.3): '536afc3aa0f11a126d5ba9f40254ce3f',
    ('draw_dunes_and_oasis', (800, 480), 700.7): '2cce7ebe65bee81d957e372859cbdd9e',
    ('draw_dunes_and_oasis', (800, 480), 2399.9): 'ba7cca61a028ec3b19117107a323f067',
    ('draw_dunes_and_oasis', (800, 480), 3001.5): '7f81ff8548aadd0b0f717d2cdd1c926d',
    ('draw_dunes_and_oasis', (800, 480), 100000.3): 'd5c4ffe894119641306e3d7e8e53e3dc',
    ('draw_dunes_and_oasis', (800, 480), -0.7): 'ced9122d3378c5aa51a1216d55164c9a',
    ('draw_dunes_and_oasis', (800, 480), -250.0): 'f5f54af860bdead369693e113fc40ec0',
    ('draw_dunes_and_oasis', (513, 397), 0.0): '9bba35f5dd2835f263358c7c4d1bf601',
    ('draw_dunes_and_oasis', (513, 397), 0.3): '02ef565d313a0a8eab6ee59529c604b0',
    ('draw_dunes_and_oasis', (513, 397), 12.3): '6708d317b09c5f79f5cf424b6c143941',
    ('draw_dunes_and_oasis', (513, 397), 700.7): 'e72c82105b12b52f44b76300025ab343',
    ('draw_dunes_and_oasis', (513, 397), 2399.9): '15a55a6cb9d189979fcf17c8387565c1',
    ('draw_dunes_and_oasis', (513, 397), 3001.5): '5a2026dedcfa2ff28cb44409c68c8a87',
    ('draw_dunes_and_oasis', (513, 397), 100000.3): '05f3a94682d72fc12f56ba4dc61e71e2',
    ('draw_dunes_and_oasis', (513, 397), -0.7): '831aee8fc61b64070c911dda138bfe89',
    ('draw_dunes_and_oasis', (513, 397), -250.0): 'c6bb577e97846a6663c472ecbbc90e9c',
    ('draw_dunes_and_oasis', (300, 240), 0.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 0.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 12.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 700.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 2399.9): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 3001.5): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), 100000.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), -0.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_dunes_and_oasis', (300, 240), -250.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (800, 480), 0.0): '826d1ca7bddc505ce313524e982d1867',
    ('draw_near_ground_details', (800, 480), 0.3): '826d1ca7bddc505ce313524e982d1867',
    ('draw_near_ground_details', (800, 480), 12.3): 'fe2ff33a2f432eca1474d0d5057a3d73',
    ('draw_near_ground_details', (800, 480), 700.7): '5909be69351a440e95845c7e517f3b24',
    ('draw_near_ground_details', (800, 480), 2399.9): 'aab3e9cc76b85e71829a31db19c06eec',
    ('draw_near_ground_details', (800, 480), 3001.5): '79ce5c6f1c25040cd665380befedb183',
    ('draw_near_ground_details', (800, 480), 100000.3): 'e10413fe998e9d68f18f41751859bc39',
    ('draw_near_ground_details', (800, 480), -0.7): 'af67ccad971663558a090fb7efa6c5bc',
    ('draw_near_ground_details', (800, 480), -250.0): '99b3a0bee2b2f9301b2407696f542115',
    ('draw_near_ground_details', (513, 397), 0.0): 'd89f1938327c889140760efe1b4ad3d3',
    ('draw_near_ground_details', (513, 397), 0.3): 'd89f1938327c889140760efe1b4ad3d3',
    ('draw_near_ground_details', (513, 397), 12.3): '2b3e4e4975e65fa05cb16e26fc3187aa',
    ('draw_near_ground_details', (513, 397), 700.7): '1d99fce2cf61d26ebed40f48d9003797',
    ('draw_near_ground_details', (513, 397), 2399.9): '160b66e2dd48675d395150879a9f3443',
    ('draw_near_ground_details', (513, 397), 3001.5): '6e06f8a8e831e50d0e4af1c2db872cae',
    ('draw_near_ground_details', (513, 397), 100000.3): '4541d2196ecb48dad1f2abb5d6be596d',
    ('draw_near_ground_details', (513, 397), -0.7): '74a7d2c6792fa1ac2994c06d601f1cb1',
    ('draw_near_ground_details', (513, 397), -250.0): '15a10c74496602b5b971c5ea480c8a25',
    ('draw_near_ground_details', (300, 240), 0.0): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 0.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 12.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 700.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 2399.9): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 3001.5): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), 100000.3): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), -0.7): 'f656f8a7837fb9588293572f43d0bfc5',
    ('draw_near_ground_details', (300, 240), -250.0): 'f656f8a7837fb9588293572f43d0bfc5',
}
PARALLAX_DRAW_FUNCTIONS = {
    'draw_sky': draw_sky,
    'draw_pyramids': draw_pyramids,
    'draw_dunes_and_oasis': draw_dunes_and_oasis,
    'draw_near_ground_details': draw_near_ground_details,
}


def parallax_layer_digest(
    *, function_name: str, surface_size: tuple[int, int], camera_offset: float
) -> str:
    """Draw one parallax layer onto a cleared SRCALPHA surface and digest its RGBA pixels.

    Returns:
        The hex digest of the drawn pixels (independent of the surface's pixel format).

    """
    surface = pygame.Surface(surface_size, pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))
    PARALLAX_DRAW_FUNCTIONS[function_name](surface, camera_offset, camera_offset * 0.5)
    return hashlib.blake2b(pygame.image.tobytes(surface, 'RGBA'), digest_size=16).hexdigest()


class TestParallaxDrawingGoldens:
    """The parallax layers draw exactly the pixels the per-column drawing code drew."""

    @pytest.mark.parametrize(
        ('function_name', 'surface_size', 'camera_offset'),
        list(PARALLAX_DRAWING_GOLDEN_DIGESTS),
    )
    def test_layer_matches_golden(self, function_name, surface_size, camera_offset):
        digest = parallax_layer_digest(
            function_name=function_name, surface_size=surface_size, camera_offset=camera_offset
        )

        golden_digest = PARALLAX_DRAWING_GOLDEN_DIGESTS[function_name, surface_size, camera_offset]
        assert digest == golden_digest

    @pytest.mark.parametrize('function_name', list(PARALLAX_DRAW_FUNCTIONS))
    def test_redrawing_at_another_size_and_back_is_unchanged(self, function_name):
        """A cache keyed by surface size never hands one size's drawing to another."""
        first_digest = parallax_layer_digest(
            function_name=function_name, surface_size=SCREEN_SIZE, camera_offset=12.3
        )
        parallax_layer_digest(
            function_name=function_name, surface_size=(513, 397), camera_offset=12.3
        )

        assert (
            parallax_layer_digest(
                function_name=function_name, surface_size=SCREEN_SIZE, camera_offset=12.3
            )
            == first_digest
        )

    def test_sky_draws_its_gradient_once_per_size(self, mocker):
        """The sky gradient is built once per surface size and blitted afterwards."""
        draw_sky(pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA), 0.0, 0.0)
        draw_line_spy = mocker.spy(pygame.draw, 'line')

        draw_sky(pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA), 0.0, 0.0)

        assert draw_line_spy.call_count == 0

    def test_pyramids_draw_the_ground_gradient_once_per_size(self, mocker):
        """The horizon-to-sand gradient is built once and blitted, not drawn row by row."""
        surface = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        draw_pyramids(surface, 0.0, 0.0)
        draw_line_spy = mocker.spy(pygame.draw, 'line')

        draw_pyramids(surface, 40.0, 0.0)

        assert draw_line_spy.call_count == 0

    def test_dunes_draw_no_line_per_column(self, mocker):
        """The dune sand is filled in runs of equal height, not one line per screen column.

        At camera offset 1700 both oases are off screen, so no line is drawn at all.
        """
        surface = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        draw_line_spy = mocker.spy(pygame.draw, 'line')

        draw_dunes_and_oasis(surface, 1700.0, 0.0)

        assert draw_line_spy.call_count == 0


# --- Scene behaviour the golden replays never reach (both editions unless noted) ---

GAME_SCENE_CLASSES = [BraveAdventurerScene, PapyrusBraveAdventurerScene]
BACKGROUND_COLOR = (1, 2, 3)


def _start_display():
    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode(SCREEN_SIZE)


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
        assert jump_scene.next_scene is jump_scene
        assert not jump_scene.quit_requested


class TestQuitKey:
    """Q (by position) ends the game: no next scene."""

    def test_quit_position_ends_the_game(self, real_scene):
        real_scene.on_key_down_event(key_at(key=pygame.K_q, scancode=pygame.KSCAN_Q))

        assert real_scene.next_scene is None


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


@pytest.mark.parametrize('adventurer_scene', [BraveAdventurerScene], indirect=True)
class TestVoiceAssistantMicButton:
    """Brave Adventurer: holding the mic button records a question, releasing it answers.

    The voice assistant drives a controller's microphone and speaker (hardware), so it is a
    stand-in here.
    """

    @pytest.fixture
    def voice_assistant(self, mocker):
        return mocker.create_autospec(VoiceAssistant, instance=True)

    @staticmethod
    def _controller_scene():
        _start_display()
        return BraveAdventurerScene(options={'input_mode': 'controller'})

    def test_each_frame_collects_finished_responses(self, adventurer_scene, voice_assistant):
        adventurer_scene.voice_assistant = voice_assistant

        adventurer_scene.dt_tick(FRAME_SECONDS)

        voice_assistant.update.assert_called_once_with()

    def test_controller_mic_button_listens_and_answers(self, adventurer_scene, voice_assistant):
        scene = self._controller_scene()
        scene.voice_assistant = voice_assistant

        scene.on_controller_button_down_event(
            _controller_button_event(pygame.CONTROLLERBUTTONDOWN, MIC_BUTTON_CONTROLLER)
        )
        voice_assistant.start_listening.assert_called_once_with()
        scene.on_controller_button_up_event(
            _controller_button_event(pygame.CONTROLLERBUTTONUP, MIC_BUTTON_CONTROLLER)
        )

        voice_assistant.stop_listening_and_respond.assert_called_once_with()

    def test_joystick_mic_button_listens_and_answers(self, adventurer_scene, voice_assistant):
        adventurer_scene.voice_assistant = voice_assistant

        adventurer_scene.on_joy_button_down_event(
            _joystick_button_event(pygame.JOYBUTTONDOWN, MIC_BUTTON_JOYSTICK)
        )
        voice_assistant.start_listening.assert_called_once_with()
        adventurer_scene.on_joy_button_up_event(
            _joystick_button_event(pygame.JOYBUTTONUP, MIC_BUTTON_JOYSTICK)
        )

        voice_assistant.stop_listening_and_respond.assert_called_once_with()

    def test_mic_button_without_an_assistant_does_nothing(self, adventurer_scene):
        """No controller with a microphone was found: the mic button is ignored."""
        controller_scene = self._controller_scene()
        for scene in (adventurer_scene, controller_scene):
            scene.voice_assistant = None
            scene.dt_tick(FRAME_SECONDS)
        controller_scene.on_controller_button_down_event(
            _controller_button_event(pygame.CONTROLLERBUTTONDOWN, MIC_BUTTON_CONTROLLER)
        )
        controller_scene.on_controller_button_up_event(
            _controller_button_event(pygame.CONTROLLERBUTTONUP, MIC_BUTTON_CONTROLLER)
        )
        adventurer_scene.on_joy_button_down_event(
            _joystick_button_event(pygame.JOYBUTTONDOWN, MIC_BUTTON_JOYSTICK)
        )
        adventurer_scene.on_joy_button_up_event(
            _joystick_button_event(pygame.JOYBUTTONUP, MIC_BUTTON_JOYSTICK)
        )

        assert adventurer_scene.voice_assistant is None
        assert controller_scene.voice_assistant is None


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
        ('console_script', 'game_module'),
        [('brave-adventurer', brave_adventurer_game), ('brave-adventurer-papyrus', papyrus_game)],
    )
    def test_main_replays_the_golden_recording(self, mocker, console_script, game_module):
        mocker.patch.object(game_module, 'GameEngine', GoldenTraceEngine)
        # GameEngine._shutdown quits pygame; later tests on this worker still need it
        mocker.patch('pygame.quit')
        mocker.patch('pygame.display.quit')
        # --headless sets the SDL driver variables; the test's own values come back afterwards
        mocker.patch.dict(os.environ)
        recording = REPLAY_FIXTURE_DIRECTORY / console_script / 'golden.jsonl.gz'
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
        [(LevelManager, Scarab), (PapyrusLevelManager, PapyrusScarab)],
        ids=['LevelManager', 'PapyrusLevelManager'],
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
        manager = LevelManager(level_data=LEVEL_1, groups=pygame.sprite.LayeredDirty())

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


class TestPapyrusSpriteUtilities:
    """The Papyrus conversions handle a sprite with no frames and a scale of 1."""

    def test_a_sprite_without_frames_keeps_its_image(self):
        _start_display()
        sprite = AnimatedSprite(groups=pygame.sprite.LayeredDirty())
        image = sprite.image

        prepare_papyrus_sprite(sprite)
        apply_transparency_and_scale(sprite)

        assert sprite.image is image
        assert sprite.hitbox_scale == 2

    def test_scale_one_draws_a_copy_of_the_frame(self):
        _start_display()
        sprite = AnimatedSprite(
            filename=str(SPRITES_DIR / 'cobra.toml'), groups=pygame.sprite.LayeredDirty()
        )
        prepare_papyrus_sprite(sprite, scale_factor=1)

        apply_transparency_and_scale(sprite, scale_factor=1)

        frame_image = sprite.get_current_frame().image
        assert sprite.image is not frame_image
        assert sprite.image.get_size() == frame_image.get_size()
        assert _surface_bytes(sprite.image) == _surface_bytes(frame_image)
        assert sprite.hitbox_scale == 1
