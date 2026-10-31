"""Brave Adventurer: Papyrus Edition: what only its TOML sprites do."""

import re
import tomllib
import types
from pathlib import Path

import pygame
import pytest

import brave_adventurer_core as brave_adventurer_core_package
import brave_adventurer_papyrus as papyrus_package
from brave_adventurer_core.constants import (
    GROUND_Y,
    STONE_WALL_WIDTH,
)
from brave_adventurer_papyrus.constants import (
    FALLING_VELOCITY_THRESHOLD as PAPYRUS_FALLING_VELOCITY_THRESHOLD,
)
from brave_adventurer_papyrus.constants import PAPYRUS_PLAYER_HEIGHT, SPRITES_DIR
from brave_adventurer_papyrus.enemies import PapyrusCobra, PapyrusScarab, PapyrusScorpion
from brave_adventurer_papyrus.game import PapyrusBraveAdventurerScene
from brave_adventurer_papyrus.player import PapyrusPlayer
from brave_adventurer_papyrus.sprite_utils import (
    apply_transparency_and_scale,
    prepare_papyrus_sprite,
)
from brave_adventurer_papyrus.terrain import PapyrusGoldScarab
from glitchygames.animation.state_machine import AnimationStateMachine
from glitchygames.collision.layers import collision_rect_offset, get_sprite_collision_rect
from glitchygames.display_mode import set_display_mode
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode, snap_to_pixel
from glitchygames.sprites import AnimatedSprite, FrameAnchor
from glitchygames.world import CoordinateSpace, position_world_sprites, screen_position_for
from tests.display_canvas import show_canvas_on_new_display

PAPYRUS_PACKAGE = Path(papyrus_package.__file__).parent
BRAVE_ADVENTURER_CORE_PACKAGE = Path(brave_adventurer_core_package.__file__).parent
PAPYRUS_WORLD_SPRITE_CLASSES = (
    PapyrusPlayer,
    PapyrusCobra,
    PapyrusScarab,
    PapyrusScorpion,
    PapyrusGoldScarab,
)
SCREEN_SIZE = (800, 480)


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


def _surface_bytes(surface):
    return pygame.image.tobytes(surface, 'RGBA')


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
            set_display_mode(size=(800, 480))
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
            set_display_mode(size=(800, 480))
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
        assert falling_sources == ['idle', 'jumping', 'running']
        for transition in transitions:
            if transition['to'] == 'falling':
                assert transition['when'] == expected_when

    def test_toml_threshold_equals_constant(self, transitions):
        for transition in transitions:
            if transition['to'] == 'falling':
                threshold_text = transition['when'].split()[2]
                assert float(threshold_text) == pytest.approx(PAPYRUS_FALLING_VELOCITY_THRESHOLD)

    def test_falling_comes_after_other_rules_from_same_state(self, transitions):
        for source in ('idle', 'jumping', 'running'):
            targets = [
                transition['to'] for transition in transitions if transition['from'] == source
            ]
            assert targets[-1] == 'falling'

    def test_player_has_no_code_defined_falling_transitions(self):
        if not pygame.get_init():
            pygame.init()
        if pygame.display.get_surface() is None:
            set_display_mode(size=(800, 480))
        scene = PapyrusBraveAdventurerScene(options={'input_mode': 'joystick'})
        state_machine = scene.player.state_machine
        assert state_machine is not None
        falling_conditions = [
            transition.condition
            for transition in state_machine._transitions
            if transition.to_state == 'falling'
        ]
        assert len(falling_conditions) == 3
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
        'source_path',
        sorted([*PAPYRUS_PACKAGE.glob('*.py'), *BRAVE_ADVENTURER_CORE_PACKAGE.glob('*.py')]),
        ids=lambda path: f'{path.parent.name}/{path.name}',
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
            set_display_mode(size=SCREEN_SIZE)
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
            set_display_mode(size=SCREEN_SIZE)
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
            set_display_mode(size=SCREEN_SIZE)
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

    @pytest.mark.parametrize(
        'make_sprite',
        [
            lambda groups: PapyrusPlayer(world_x=100.0, world_y=100.0, groups=groups),
            lambda groups: PapyrusCobra(world_x=100.0, groups=groups),
            lambda groups: PapyrusScarab(world_x=100.0, groups=groups),
            lambda groups: PapyrusScorpion(world_x=100.0, groups=groups),
        ],
        ids=['player', 'cobra', 'scarab', 'scorpion'],
    )
    def test_the_rect_is_the_scaled_images_size(self, make_sprite):
        """A 2x sprite's rect is its drawn image's size, not the native frame's (BUGS.md #59)."""
        _start_display()
        sprite = make_sprite(pygame.sprite.LayeredDirty())
        native_size = sprite.get_current_frame().image.get_size()

        apply_transparency_and_scale(sprite)

        assert sprite.image.get_size() == (native_size[0] * 2, native_size[1] * 2)
        assert sprite.rect.size == sprite.image.get_size()


# A player running right that has just left the ground and started to fall
RUNNING_OFF_A_LEDGE_CONTEXT = {'velocity_x': 200.0, 'velocity_y': 20.0, 'on_ground': False}


class TestRunningOffALedgeFalls:
    """Running off a ledge shows the falling pose in the Papyrus Edition (#209.7)."""

    def test_papyrus_player_goes_from_running_to_falling(self):
        _start_display()
        player = PapyrusPlayer(world_x=100.0, world_y=300.0, groups=pygame.sprite.LayeredDirty())
        assert player.state_machine is not None
        player.state_machine.set_state(PapyrusPlayer.RUNNING)

        player.state_machine.evaluate(RUNNING_OFF_A_LEDGE_CONTEXT)

        assert player.state_machine.current_state == PapyrusPlayer.FALLING
