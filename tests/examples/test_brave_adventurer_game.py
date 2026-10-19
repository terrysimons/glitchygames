"""Tests for the Brave Adventurer games: death and game-over rumble, terrain hitboxes."""

import math
import tomllib
import types
from pathlib import Path

import pygame
import pytest

from glitchygames.animation.state_machine import AnimationStateMachine
from glitchygames.camera import FollowAxes
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.events.base import HashableEvent
from glitchygames.examples import brave_adventurer as brave_adventurer_package
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
from glitchygames.examples.brave_adventurer.drawing import draw_player
from glitchygames.examples.brave_adventurer.enemies import Cobra, Scarab, Scorpion
from glitchygames.examples.brave_adventurer.game import BraveAdventurerScene
from glitchygames.examples.brave_adventurer.player import Player
from glitchygames.examples.brave_adventurer.terrain import GoldScarab, GroundSegment, StoneWall
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    FALLING_VELOCITY_THRESHOLD as PAPYRUS_FALLING_VELOCITY_THRESHOLD,
)
from glitchygames.examples.brave_adventurer_papyrus.constants import (
    PAPYRUS_PLAYER_HEIGHT,
    SPRITES_DIR,
)
from glitchygames.examples.brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from glitchygames.examples.brave_adventurer_papyrus.sprite_utils import apply_transparency_and_scale
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode
from glitchygames.sprites import AnimatedSprite, FrameAnchor
from glitchygames.world import CoordinateSpace, position_world_sprites

FRAME_SECONDS = 1 / 60
BRAVE_ADVENTURER_PACKAGE = Path(brave_adventurer_package.__file__).parent
BRAVE_WORLD_SPRITE_CLASSES = (Player, GroundSegment, StoneWall, GoldScarab, Cobra, Scarab, Scorpion)


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
            player.apply_camera(scene.camera)
            screen_ground = GROUND_Y - round(scene.camera.world_y)
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
    scene.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode='', scancode=0))


class TestEngineWorldSpace:
    """Brave Adventurer's sprites are world sprites; the engine aims the camera and places them."""

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

    def test_setup_follows_the_player_on_the_x_axis(self, brave_scene):
        brave_scene.setup()
        assert brave_scene.camera.follow_target is brave_scene.player
        assert brave_scene.camera.follow_axes is FollowAxes.X

    def test_dt_tick_leaves_the_camera_to_the_engine(self, brave_scene):
        """The game no longer calls camera.update(); the engine aims the camera."""
        brave_scene.camera.begin_frame()
        camera_position = (brave_scene.camera.world_x, brave_scene.camera.world_y)
        brave_scene.dt_tick(FRAME_SECONDS)
        assert not brave_scene.camera.updated_by_game_this_frame
        assert (brave_scene.camera.world_x, brave_scene.camera.world_y) == camera_position

    def test_dt_tick_still_updates_the_distance_score(self, brave_scene):
        brave_scene.player.world_x = 2000.0
        brave_scene.dt_tick(FRAME_SECONDS)
        assert brave_scene.player.max_distance >= 2000.0
        assert brave_scene.player.score > 0

    def test_camera_aims_at_the_player(self, brave_scene):
        brave_scene.setup()
        player = brave_scene.player
        assert brave_scene.camera_target() == (player.world_x, player.world_y)

    def test_camera_stays_still_after_game_over(self, brave_scene):
        """dt_tick stops after game over, and so does the camera (it no longer moves)."""
        brave_scene.setup()
        brave_scene.game_over_triggered = True
        assert brave_scene.camera_target() is None

    def test_terrain_collision_snaps_with_the_scene_mode(self, brave_scene):
        """Terrain edges are snapped as the engine draws them (FLOOR here), not with round()."""
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        segment_right = 300
        # A segment at 0.6 ends at 300 with FLOOR (300.6 floors to 300); round() gave 301
        brave_scene.ground_sprites[:] = [
            types.SimpleNamespace(world_x=0.6, world_y=float(GROUND_Y), segment_width=segment_right)
        ]
        brave_scene.wall_sprites[:] = []
        player = _drawn_player(brave_scene)
        player.world_y = float(GROUND_Y - 20)
        player.velocity_y = 50.0
        player.velocity_x = 200.0
        support_left, _ = brave_scene._player_support_span()
        player.world_x += segment_right - support_left

        brave_scene._resolve_player_ground_collision()

        assert not player.on_ground

    def test_wall_collision_snaps_with_the_scene_mode(self, brave_scene):
        """A wall at 400.6 has its left face at 400 under FLOOR (round() put it at 401)."""
        set_active_default_snap_mode(PixelSnapMode.FLOOR)
        wall_x = 400.6
        brave_scene.wall_sprites[:] = [
            types.SimpleNamespace(world_x=wall_x, world_y=GROUND_Y - 64.0, wall_height=64)
        ]
        brave_scene.ground_sprites[:] = [
            types.SimpleNamespace(world_x=0.0, world_y=float(GROUND_Y), segment_width=2000)
        ]
        player = _drawn_player(brave_scene)
        offset_x, _ = collision_rect_offset(player)
        hitbox_width = _player_hitbox(brave_scene).width
        player.world_x = float(400 - hitbox_width - offset_x + 3)  # 3 px into the wall
        player.world_y = float(GROUND_Y - 47)
        player.velocity_x = 200.0

        brave_scene._resolve_player_wall_collision()

        assert _player_hitbox(brave_scene).right == 400


class TestPoseBeforeCollision:
    """The adventurer's pose (its hitbox) is final before collision runs: no one-frame wall lag.

    Each frame runs as the engine runs it: scene logic (dt_tick), then input events, then
    the render phase (the sprite's update()). The hitbox is checked after logic (what
    collision used) and after the render phase (what is drawn and what the debug overlay
    shows).
    """

    WALL_X = 400.0
    WALL_HEIGHT = 64

    @pytest.fixture
    def walled_scene(self, brave_scene, mocker):
        """The scene with one long ground segment and one real stone wall, and no enemies.

        Returns:
            The scene.

        """
        wall = StoneWall(
            world_x=self.WALL_X, wall_height=self.WALL_HEIGHT, groups=pygame.sprite.LayeredDirty()
        )
        brave_scene.wall_sprites[:] = [wall]
        brave_scene.ground_sprites[:] = [
            GroundSegment(world_x=0.0, segment_width=2000, groups=pygame.sprite.LayeredDirty())
        ]
        mocker.patch.object(brave_scene, '_check_enemy_collisions')
        return brave_scene

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
        self, brave_scene, mocker
    ):
        """Camera at x.5: round(world - camera) and snap(world) - snap(camera) differ by 1 px.

        With the camera at 100.5, round(450 - 100.5) = 350 (half to even) while the engine
        draws the segment edge at 450 - 101 = 349.
        """
        scene = brave_scene
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
