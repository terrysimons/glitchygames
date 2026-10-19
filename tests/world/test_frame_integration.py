"""The engine's camera aim and world-sprite positioning, run inside the real frame.

Runs small real scenes headless through the golden-trace harness
(``scripts/record_golden_traces.py``), which steps frames exactly as ``SceneManager.start()``
does, without pacing. Nothing in pygame is mocked: the rects asserted are the ones drawn.
"""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
import pytest
from scripts.record_golden_traces import (
    FAKE_CLOCK_START_SECONDS,
    FRAME_SECONDS,
    RANDOM_SEED,
    SCREEN_RESOLUTION,
    FakeClock,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
    deterministic_environment,
    discard_environment_events,
    press,
    release,
)

from glitchygames.camera import Camera2D
from glitchygames.collision.detection import snapped_world_position
from glitchygames.pixel_snap import PixelSnapMode, active_default_snap_mode
from glitchygames.scenes import Scene
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.transitions import FadeTransition
from glitchygames.world import CoordinateSpace, screen_position_for

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

SPRITE_SIZE = 16
PLAYER_START = (400.5, 300.25)
PLAYER_STEP_X = 3.5
SPAWNED_SPRITE_WORLD_POSITION = (520.75, 330.5)
SPAWN_FRAME = 3
FRAMES_TO_RUN = 6
SCREEN_SPRITE_TOPLEFT = (7, 9)
TEST_FADE_SECONDS = 0.25
PAUSE_FRAMES = 3

# Transition capture: the player is drawn in a colour nothing else uses, so its pixels can be
# counted in a screenshot; the landmark proves the capture really drew the world sprites
PLAYER_COLOR = (250, 20, 200)
LANDMARK_COLOR = (20, 230, 40)
LANDMARK_OFFSET_X = 80.0
EXACT_COLOR_THRESHOLD = (1, 1, 1, 255)


class WorldSprite(pygame.sprite.DirtySprite):
    """A minimal sprite living in world coordinates."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, world_x: float, world_y: float) -> None:
        """Create the sprite at a world position with a small real surface.

        Args:
            world_x: World X of the sprite's top-left.
            world_y: World Y of the sprite's top-left.

        """
        super().__init__()
        self.world_x = world_x
        self.world_y = world_y
        self.image = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
        self.rect = self.image.get_rect()

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""


class ScreenSprite(pygame.sprite.DirtySprite):
    """A HUD-style sprite: no coordinate space declared, so the engine never moves it."""

    def __init__(self) -> None:
        """Create the sprite at a fixed screen position."""
        super().__init__()
        self.world_x = 900.0
        self.world_y = 900.0
        self.image = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
        self.rect = pygame.Rect(SCREEN_SPRITE_TOPLEFT, (SPRITE_SIZE, SPRITE_SIZE))

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""


class FollowingScene(Scene):
    """A scrolling scene: the camera follows a moving player; one sprite spawns mid-run.

    Records, at render time, each world sprite's rect next to where screen_position_for says
    it belongs, so the tests can check what was actually drawn.
    """

    NAME = 'Following'
    VERSION = '1.0'

    @override
    def setup(self: Self) -> None:
        """Create the player, the HUD sprite and a following camera (once).

        Resuming from a pause runs setup() again; the scene keeps what it already has, as a
        game keeps its state across a pause.
        """
        if getattr(self, 'player', None) is not None:
            return
        self.camera = Camera2D(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            lead_x=self.screen_width / 2,
            lead_y=self.screen_height / 2,
        )
        player_x, player_y = PLAYER_START
        self.player = WorldSprite(world_x=player_x, world_y=player_y)
        self.hud = ScreenSprite()
        self.all_sprites.add(self.player, self.hud)
        self.camera.follow(target=self.player)
        self.frame_number = 0
        self.spawned: WorldSprite | None = None
        self.render_samples: list[dict[str, Any]] = []
        self.game_updated_camera_at_tick_start: list[bool] = []

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the player; spawn a sprite on SPAWN_FRAME, as a game spawns a ball."""
        self.game_updated_camera_at_tick_start.append(self.camera.updated_by_game_this_frame)
        super().dt_tick(dt)
        self.frame_number += 1
        self.player.world_x += PLAYER_STEP_X
        if self.frame_number == SPAWN_FRAME:
            spawned_x, spawned_y = SPAWNED_SPRITE_WORLD_POSITION
            self.spawned = WorldSprite(world_x=spawned_x, world_y=spawned_y)
            self.all_sprites.add(self.spawned)

    @override
    def render(self: Self, screen: pygame.Surface) -> None:
        """Record every sprite's rect and expected position, then draw."""
        world_sprites = [self.player] + ([self.spawned] if self.spawned is not None else [])
        self.render_samples.append({
            'frame': self.frame_number,
            'camera': (self.camera.world_x, self.camera.world_y),
            'drawn': [sprite.rect.topleft for sprite in world_sprites],
            'expected': [
                screen_position_for(sprite=sprite, camera=self.camera) for sprite in world_sprites
            ],
            'hud': self.hud.rect.topleft,
            'snap_mode': active_default_snap_mode(),
        })
        super().render(screen)


class ManualCameraScene(FollowingScene):
    """A game that still moves its camera itself, in update() (the render phase)."""

    NAME = 'Manual Camera'

    @override
    def update(self: Self) -> None:
        """Move the camera by hand every frame, after the engine's aim."""
        self.camera.update(self.player.world_x, self.player.world_y, FRAME_SECONDS)
        super().update()


class FloorFollowingScene(FollowingScene):
    """A FLOOR-snapping scrolling scene, to check its mode comes back after a pause."""

    NAME = 'Floor Following'
    PIXEL_SNAP_MODE: ClassVar[PixelSnapMode] = PixelSnapMode.FLOOR


def filled_world_sprite(*, world_x: float, world_y: float, color: tuple[int, int, int]) -> Any:
    """Build a world sprite whose whole image is one colour.

    Args:
        world_x: World X of the sprite's top-left.
        world_y: World Y of the sprite's top-left.
        color: The fill colour.

    Returns:
        The WorldSprite.

    """
    sprite = WorldSprite(world_x=world_x, world_y=world_y)
    sprite.image.fill(color)
    return sprite


class CapturedPlayerScene(Scene):
    """A scene with a WORLD-space ``player`` (which transitions hide) and a landmark."""

    NAME = 'Captured Player'
    VERSION = '1.0'

    @override
    def setup(self: Self) -> None:
        """Create the player and landmark and follow the player."""
        self.camera = Camera2D(
            screen_width=self.screen_width,
            screen_height=self.screen_height,
            lead_x=self.screen_width / 2,
            lead_y=self.screen_height / 2,
        )
        player_x, player_y = PLAYER_START
        self.player = filled_world_sprite(world_x=player_x, world_y=player_y, color=PLAYER_COLOR)
        self.landmark = filled_world_sprite(
            world_x=player_x + LANDMARK_OFFSET_X, world_y=player_y, color=LANDMARK_COLOR
        )
        self.all_sprites.add(self.player, self.landmark)
        self.camera.follow(target=self.player)


OFF_SCREEN_PLAYER_POSITION = (5000.0, 5000.0)


class OffScreenPlayerScene(Scene):
    """A scene whose WORLD-space ``player`` is far off screen; the camera is pinned at 0, 0."""

    NAME = 'Off Screen Player'
    VERSION = '1.0'
    start_hidden: ClassVar[bool] = False

    @override
    def setup(self: Self) -> None:
        """Create the off-screen player; bounds keep the camera from ever reaching it."""
        self.camera.set_bounds(min_x=0.0, max_x=0.0, min_y=0.0, max_y=0.0)
        player_x, player_y = OFF_SCREEN_PLAYER_POSITION
        self.player = filled_world_sprite(world_x=player_x, world_y=player_y, color=PLAYER_COLOR)
        self.player.hidden = self.start_hidden
        self.all_sprites.add(self.player)


class HiddenOffScreenPlayerScene(OffScreenPlayerScene):
    """The same scene with the player hidden by the game."""

    NAME = 'Hidden Off Screen Player'
    start_hidden: ClassVar[bool] = True


class CameraFreeScene(Scene):
    """A plain scene holding one world sprite; the test removes its camera."""

    NAME = 'Camera Free'
    VERSION = '1.0'

    @override
    def setup(self: Self) -> None:
        """Add a world sprite away from the origin."""
        player_x, player_y = PLAYER_START
        self.world_sprite = WorldSprite(world_x=player_x, world_y=player_y)
        self.all_sprites.add(self.world_sprite)


class FloorSnappingScene(Scene):
    """A retro scene that snaps with FLOOR; records the active mode seen during setup()."""

    NAME = 'Floor Snapping'
    VERSION = '1.0'
    PIXEL_SNAP_MODE: ClassVar[PixelSnapMode] = PixelSnapMode.FLOOR

    mode_during_setup: ClassVar[PixelSnapMode | None] = None

    @override
    def setup(self: Self) -> None:
        """Remember the active snap mode while the scene sets itself up."""
        FloorSnappingScene.mode_during_setup = active_default_snap_mode()

    def leave(self: Self) -> None:
        """Fade to a FollowingScene (default NEAREST_HALF_UP)."""
        self.transition_to(
            FollowingScene(options=self.options), FadeTransition(duration=TEST_FADE_SECONDS)
        )


@contextlib.contextmanager
def running_scene(scene_class: type[Scene]) -> Generator[GoldenTraceSceneManager]:
    """Start a scene headless in the harness's deterministic environment.

    Args:
        scene_class: The scene class to make active.

    Yields:
        The scene manager with the scene active.

    """
    clock = FakeClock(start_seconds=FAKE_CLOCK_START_SECONDS)
    with (
        tempfile.TemporaryDirectory(prefix='frame-integration-saves-') as save_directory,
        deterministic_environment(clock=clock, save_root=Path(save_directory)),
    ):
        manager = GoldenTraceSceneManager.install()
        try:
            with command_line([
                '--windowed',
                '--resolution',
                SCREEN_RESOLUTION,
                '--log-level',
                'warning',
                '--random-seed',
                str(RANDOM_SEED),
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            engine.install_game(scene_class=scene_class)
            yield manager
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def step(manager: GoldenTraceSceneManager, *events: pygame.event.Event, frames: int = 1) -> None:
    """Run frames at the harness's fixed dt, posting events before the first one.

    Args:
        manager: The running scene manager.
        *events: Events posted before the first frame.
        frames: How many frames to run.

    """
    for frame_index in range(frames):
        manager.dt = FRAME_SECONDS
        discard_environment_events()
        if frame_index == 0:
            for event in events:
                pygame.event.post(event)
        manager.run_frame()


def active_following_scene(manager: GoldenTraceSceneManager) -> FollowingScene:
    """Return the active scene, checked to be a FollowingScene.

    Args:
        manager: The running scene manager.

    Returns:
        The active FollowingScene.

    """
    scene = manager.active_scene
    assert isinstance(scene, FollowingScene)
    return scene


class TestPositioningInTheFrame:
    """World sprites are aimed at and placed by the engine before every render."""

    def test_world_sprite_is_positioned_before_render(self):
        """At render time the player's rect is where screen_position_for puts it."""
        with running_scene(FollowingScene) as manager:
            step(manager, frames=FRAMES_TO_RUN)
            scene = active_following_scene(manager)

            assert len(scene.render_samples) == FRAMES_TO_RUN
            for sample in scene.render_samples:
                assert sample['drawn'][0] == sample['expected'][0]
            # The camera really moved (the engine aimed it at the moving player)
            first_camera = scene.render_samples[0]['camera']
            last_camera = scene.render_samples[-1]['camera']
            assert last_camera[0] > first_camera[0]

    def test_sprite_spawned_during_dt_tick_is_positioned_on_its_first_frame(self):
        """A sprite added in dt_tick is drawn at its place on its very first frame."""
        with running_scene(FollowingScene) as manager:
            step(manager, frames=FRAMES_TO_RUN)
            scene = active_following_scene(manager)

            first_spawned_sample = next(
                sample for sample in scene.render_samples if len(sample['drawn']) > 1
            )
            assert first_spawned_sample['frame'] == SPAWN_FRAME
            assert first_spawned_sample['drawn'][1] == first_spawned_sample['expected'][1]
            assert first_spawned_sample['drawn'][1] != (0, 0)

    def test_screen_space_sprite_is_never_moved(self):
        """The HUD sprite stays at its screen position while the camera scrolls."""
        with running_scene(FollowingScene) as manager:
            step(manager, frames=FRAMES_TO_RUN)
            scene = active_following_scene(manager)

            assert {sample['hud'] for sample in scene.render_samples} == {SCREEN_SPRITE_TOPLEFT}

    def test_manual_update_flag_is_cleared_at_the_start_of_each_frame(self):
        """begin_frame() runs before dt_tick: last frame's manual update() does not carry over."""
        with running_scene(ManualCameraScene) as manager:
            step(manager, frames=FRAMES_TO_RUN)
            scene = active_following_scene(manager)

            assert scene.game_updated_camera_at_tick_start == [False] * FRAMES_TO_RUN
            assert scene.camera.updated_by_game_this_frame is True


class TestSnapModeActivation:
    """Activating a scene makes its PIXEL_SNAP_MODE the active default snap mode."""

    def test_activation_sets_the_scene_snap_mode_before_setup(self):
        """The FLOOR scene's setup() and frames already run with FLOOR."""
        FloorSnappingScene.mode_during_setup = None
        with running_scene(FloorSnappingScene) as manager:
            assert FloorSnappingScene.mode_during_setup is PixelSnapMode.FLOOR
            step(manager)
            assert active_default_snap_mode() is PixelSnapMode.FLOOR

    def test_transition_to_a_default_scene_restores_nearest_half_up(self):
        """Leaving the FLOOR scene for a default scene switches the active mode back."""
        with running_scene(FloorSnappingScene) as manager:
            scene = manager.active_scene
            assert isinstance(scene, FloorSnappingScene)
            scene.leave()
            step(manager)

            assert isinstance(manager.active_scene, FollowingScene)
            assert active_default_snap_mode() is PixelSnapMode.NEAREST_HALF_UP

    def test_collision_snapping_follows_the_active_scene_mode(self):
        """snapped_world_position for a sprite without its own mode uses the scene's mode."""
        sprite = WorldSprite(world_x=10.5, world_y=-0.5)
        with running_scene(FloorSnappingScene):
            assert snapped_world_position(sprite, world_x=10.5, world_y=-0.5) == (10, -1)


def color_pixel_count(surface: pygame.Surface, color: tuple[int, int, int]) -> int:
    """Count the pixels of exactly one colour in a surface.

    Args:
        surface: The captured surface.
        color: The colour to count.

    Returns:
        The number of pixels of that colour.

    """
    return pygame.mask.from_threshold(surface, color, EXACT_COLOR_THRESHOLD).count()


class TestFrameWithoutDisplay:
    """Without a display surface the camera is still aimed; positioning is skipped."""

    def test_no_screen_aims_the_camera_but_skips_positioning(self, mocker: MockerFixture):
        """With no surface to place sprites on, rects stay put while the camera moves."""
        with running_scene(FollowingScene) as manager:
            scene = active_following_scene(manager)
            mocker.patch.object(pygame.display, 'get_surface', return_value=None)
            manager.screen = None
            player_rect_before = scene.player.rect.copy()
            camera_before = (scene.camera.world_x, scene.camera.world_y)

            step(manager, frames=2)

            assert (scene.camera.world_x, scene.camera.world_y) != camera_before
            assert scene.player.rect == player_rect_before


class TestSceneWithoutCamera:
    """A scene stand-in without a camera runs its frames; the camera steps are skipped."""

    def test_frame_runs_without_a_camera(self):
        """No begin_frame, aim or positioning without a camera, and no crash."""
        with running_scene(CameraFreeScene) as manager:
            scene = manager.active_scene
            assert isinstance(scene, CameraFreeScene)
            del scene.camera
            sprite_rect_before = scene.world_sprite.rect.copy()

            step(manager, frames=2)

            assert scene.world_sprite.rect == sprite_rect_before


class TestResumeAfterPause:
    """Resuming a game from PauseScene restores its snap mode and positions its sprites."""

    def test_resume_restores_snap_mode_and_positions_world_sprites(self):
        """The first frame after resume snaps with FLOOR and draws sprites in place."""
        with running_scene(FloorFollowingScene) as manager:
            step(manager, frames=2)
            game_scene = active_following_scene(manager)
            game_scene.pause()
            step(manager)
            assert isinstance(manager.active_scene, PauseScene)
            assert active_default_snap_mode() is PixelSnapMode.NEAREST_HALF_UP

            # The game moves on while paused, so its sprites' rects are stale on resume
            game_scene.player.world_x += PLAYER_STEP_X
            step(manager, frames=PAUSE_FRAMES)
            step(manager, press(pygame.K_SPACE))
            samples_before_resume = len(game_scene.render_samples)
            step(manager, release(pygame.K_SPACE))
            assert manager.active_scene is game_scene
            assert active_default_snap_mode() is PixelSnapMode.FLOOR
            step(manager)

            first_resumed_sample = game_scene.render_samples[samples_before_resume]
            assert first_resumed_sample['snap_mode'] is PixelSnapMode.FLOOR
            assert first_resumed_sample['drawn'][0] == first_resumed_sample['expected'][0]


class TestTransitionCapture:
    """The arriving scene's transition screenshot shows its world sprites in place."""

    def test_arriving_scene_world_sprites_are_positioned_for_the_capture(self):
        """After a transition starts, the new scene's player sits where the camera puts it."""
        with running_scene(FloorSnappingScene) as manager:
            scene = manager.active_scene
            assert isinstance(scene, FloorSnappingScene)
            scene.leave()
            step(manager)

            assert manager._active_transition is not None
            arriving_scene = active_following_scene(manager)
            assert arriving_scene.player.rect.topleft == screen_position_for(
                sprite=arriving_scene.player, camera=arriving_scene.camera
            )
            assert arriving_scene.player.rect.topleft != (0, 0)

    @pytest.mark.parametrize('capture_index', [0, 1], ids=['outgoing', 'arriving'])
    def test_world_space_player_is_hidden_in_both_captures(
        self, mocker: MockerFixture, capture_index: int
    ):
        """The transition draws its own player overlay, so neither screenshot has the player."""
        with running_scene(CapturedPlayerScene) as manager:
            step(manager, frames=2)
            departing_scene = manager.active_scene
            assert isinstance(departing_scene, CapturedPlayerScene)
            assert manager.screen is not None
            # The player really is on screen before the transition
            assert color_pixel_count(manager.screen, PLAYER_COLOR) > 0

            transition = FadeTransition(duration=TEST_FADE_SECONDS)
            start_spy = mocker.spy(transition, 'start')
            departing_scene.transition_to(
                CapturedPlayerScene(options=departing_scene.options), transition
            )
            step(manager)

            assert start_spy.call_count == 1
            capture = start_spy.call_args.args[capture_index]
            assert color_pixel_count(capture, PLAYER_COLOR) == 0
            assert color_pixel_count(capture, LANDMARK_COLOR) > 0
            arriving_scene = manager.active_scene
            assert isinstance(arriving_scene, CapturedPlayerScene)
            # Visibility is restored afterwards, as before
            assert departing_scene.player.visible
            assert arriving_scene.player.visible

    @pytest.mark.parametrize(
        'scene_class', [OffScreenPlayerScene, HiddenOffScreenPlayerScene], ids=['shown', 'hidden']
    )
    def test_captures_never_uncull_an_off_screen_world_player(self, scene_class: type[Scene]):
        """The captures hide a world player with hidden, restored afterwards, never visible."""
        with running_scene(scene_class) as manager:
            step(manager, frames=2)
            departing_scene = manager.active_scene
            assert isinstance(departing_scene, OffScreenPlayerScene)
            assert not departing_scene.player.visible  # culled: far off screen

            departing_scene.transition_to(
                scene_class(options=departing_scene.options),
                FadeTransition(duration=TEST_FADE_SECONDS),
            )
            step(manager)

            arriving_scene = manager.active_scene
            assert isinstance(arriving_scene, OffScreenPlayerScene)
            assert arriving_scene is not departing_scene
            for scene in (departing_scene, arriving_scene):
                assert not scene.player.visible
                assert scene.player.hidden is scene_class.start_hidden
