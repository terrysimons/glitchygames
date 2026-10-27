"""The engine's camera aim and world-sprite positioning, run inside the real frame.

Runs small real scenes headless through the golden-trace harness
(``glitchygames/replay/tools/golden_traces.py``), which steps frames exactly as
``SceneManager.start()`` does, without pacing. Nothing in pygame is mocked: the rects asserted
are the ones drawn.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

import pygame
import pytest

from glitchygames import live_sources as live_sources_module
from glitchygames.camera import Camera2D, FollowAxes
from glitchygames.collision.detection import snapped_world_position
from glitchygames.collision.layers import collision_rect_offset
from glitchygames.color import BLACK, WHITE
from glitchygames.effects.shake import RumbleSettings, Shake, ShakeStyle, ShakeTarget
from glitchygames.engine import GameEngine
from glitchygames.game_objects import BallSprite
from glitchygames.game_objects.paddle import VerticalPaddle
from glitchygames.input.state import InputSnapshot, current_input
from glitchygames.live_sources import LiveSources
from glitchygames.movement import Speed
from glitchygames.pixel_snap import PixelSnapMode, active_default_snap_mode
from glitchygames.process import OutputCapture, run_command
from glitchygames.randomness import capture_stream_states, random_stream
from glitchygames.replay.ghosts import GhostRecorder, GhostSample, GhostSprite, GhostTrack
from glitchygames.replay.tools.golden_traces import (
    FRAME_SECONDS,
    RANDOM_SEED,
    SCREEN_RESOLUTION,
    GoldenTraceEngine,
    GoldenTraceSceneManager,
    command_line,
    deterministic_environment,
    discard_environment_events,
    press,
    release,
)
from glitchygames.scene_start import SceneStart, rebuild_scene, scene_start_capture_enabled
from glitchygames.scenes import Scene, SceneManager
from glitchygames.scenes.builtin_scenes.pause_scene import PauseScene
from glitchygames.sources import (
    active_sources,
    advance_frame_clock,
    frame_clock_seconds,
    pop_scoped_sources,
    push_scoped_sources,
)
from glitchygames.state import open_saves
from glitchygames.supervision import BREAKPOINT_KIND, ControlEvent
from glitchygames.transitions import FadeTransition
from glitchygames.world import CoordinateSpace, screen_position_for

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from pytest_mock import MockerFixture


SPRITE_SIZE = 16
INPUT_SNAPSHOT_FRAMES = 3
PLAYER_START = (400.5, 300.25)
PLAYER_STEP_X = 3.5
SPAWNED_SPRITE_WORLD_POSITION = (520.75, 330.5)
SPAWN_FRAME = 3
FRAMES_TO_RUN = 6
SCREEN_SPRITE_TOPLEFT = (7, 9)
TEST_FADE_SECONDS = 0.25
PAUSE_FRAMES = 3
# The paddle-hit stand-in starts with one ball, as PaddleSlap does; a paddle hit spawns a second
PADDLESLAP_BALLS_AFTER_ONE_SPAWN = 2
# The stand-in's left paddle and its spawned ball, copied from PaddleSlap's
# (src/games/paddleslap/src/paddleslap/__init__.py:144-151 and 500-512): a 20 x 100 paddle at the
# left edge, centered vertically, moving 400 px/s; a ball spawned at the screen's center moving
# (250, 125) px/s
PADDLE_SIZE = (20, 100)
PADDLE_SPEED = 400
SPAWNED_BALL_SPEED = (250.0, 125.0)

# Transition capture: the player is drawn in a colour nothing else uses, so its pixels can be
# counted in a screenshot; the landmark proves the capture really drew the world sprites
PLAYER_COLOR = (250, 20, 200)
LANDMARK_COLOR = (20, 230, 40)
LANDMARK_OFFSET_X = 80.0
EXACT_COLOR_THRESHOLD = (1, 1, 1, 255)
# A ghost of the player is recorded over this many frames, then played beside a new live run
GHOST_RECORDED_FRAMES = 8


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

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it.

        On a real display the pointer can move over the test's window (x11 sends the motion).
        """


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

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it.

        On a real display the pointer can move over the test's window (x11 sends the motion).
        """


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


# The camera's y before an X-only follow scene is entered (it must stay there)
X_FOLLOW_CAMERA_Y = 0.0


class XFollowScene(CapturedPlayerScene):
    """CapturedPlayerScene whose camera follows the player on X only (a side-scroller)."""

    NAME = 'X Follow'

    @override
    def setup(self: Self) -> None:
        """Follow the player on X only; the camera's y stays where the scene put it."""
        super().setup()
        self.camera.world_y = X_FOLLOW_CAMERA_Y
        self.camera.follow(target=self.player, axes=FollowAxes.X)


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


class ScreenPlayerSprite(pygame.sprite.DirtySprite):
    """A screen-space player with no world position, drawn in PLAYER_COLOR."""

    def __init__(self) -> None:
        """Create the sprite at a fixed screen position."""
        super().__init__()
        self.image = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
        self.image.fill(PLAYER_COLOR)
        self.rect = pygame.Rect(SCREEN_SPRITE_TOPLEFT, (SPRITE_SIZE, SPRITE_SIZE))

    def update_nested_sprites(self) -> None:
        """Scene.update() calls this on every sprite; this sprite has no nested sprites."""

    def on_mouse_motion_event(self, event: pygame.event.Event) -> None:
        """The mouse manager calls this on the sprite under the pointer; it ignores it.

        On a real display the pointer can move over the test's window (x11 sends the motion).
        """


class ScreenPlayerScene(Scene):
    """A scene whose ``player`` is screen space (a HUD-style sprite), beside a world landmark.

    Transitions write a screen-space player's ``visible`` directly (the engine never culls it).
    """

    NAME = 'Screen Player'
    VERSION = '1.0'
    start_visible: ClassVar[int] = 1

    @override
    def setup(self: Self) -> None:
        """Create the screen-space player and a world landmark.

        The player has no world position, so the arriving capture snaps the camera to the
        origin (where it starts) and the landmark is on screen in both captures.
        """
        self.player = ScreenPlayerSprite()
        self.player.visible = self.start_visible
        player_x, player_y = PLAYER_START
        self.landmark = filled_world_sprite(
            world_x=player_x + LANDMARK_OFFSET_X, world_y=player_y, color=LANDMARK_COLOR
        )
        self.all_sprites.add(self.player, self.landmark)


class InvisibleScreenPlayerScene(ScreenPlayerScene):
    """The same scene with the screen-space player made invisible by the game."""

    NAME = 'Invisible Screen Player'
    start_visible: ClassVar[int] = 0


class CameraFreeScene(Scene):
    """A plain scene holding one world sprite; it never sets its camera up."""

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


# A WORLD shake on a camera that nothing moves: one world sprite at a whole-pixel position
STILL_SPRITE_POSITION = (50, 50)
STILL_CAMERA_SHAKE = Shake(
    style=ShakeStyle.JITTER,
    strength=8.0,
    duration=0.2,
    frequency=30.0,
    rumble=RumbleSettings(low_frequency=0.5, high_frequency=0.5),
)
# Every frame of the shake, plus two to see it finished
STILL_CAMERA_SHAKE_FRAMES = math.ceil(STILL_CAMERA_SHAKE.duration / FRAME_SECONDS) + 2
SHAKE_ADVANCE_FRAMES = 4


class StillCameraScene(Scene):
    """A scene with one world sprite and the identity camera, which nothing ever moves.

    PaddleSlap is such a scene: its world-space balls are drawn from a camera that stays at
    the origin.
    """

    NAME = 'Still Camera'
    VERSION = '1.0'

    @override
    def setup(self: Self) -> None:
        """Add one world sprite at STILL_SPRITE_POSITION."""
        sprite_x, sprite_y = STILL_SPRITE_POSITION
        self.world_sprite = WorldSprite(world_x=float(sprite_x), world_y=float(sprite_y))
        self.all_sprites.add(self.world_sprite)


class StoppedFollowScene(StillCameraScene):
    """Follows its sprite, but camera_target() returns None, as a game does after game over."""

    NAME = 'Stopped Follow'

    @override
    def setup(self: Self) -> None:
        """Add the sprite and follow it."""
        super().setup()
        self.camera.follow(target=self.world_sprite)

    @override
    def camera_target(self: Self) -> tuple[float, float] | None:
        """Aim nowhere: the camera stands still.

        Returns:
            None, always.

        """
        return None


class AimedCameraScene(StillCameraScene):
    """The engine aims the camera at the sprite every frame."""

    NAME = 'Aimed Camera'

    @override
    def setup(self: Self) -> None:
        """Add the sprite and follow it."""
        super().setup()
        self.camera.follow(target=self.world_sprite)


class GameMovedCameraScene(StillCameraScene):
    """A manual camera: the game moves it in dt_tick, with no follow target."""

    NAME = 'Game Moved Camera'

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move the camera towards the sprite.

        Args:
            dt: The frame's delta time in seconds.

        """
        super().dt_tick(dt)
        self.camera.update(self.world_sprite.world_x, self.world_sprite.world_y, dt)


class DoubleMovedCameraScene(GameMovedCameraScene):
    """Misuse: the game moves the camera in dt_tick and the engine also aims it."""

    NAME = 'Double Moved Camera'

    @override
    def setup(self: Self) -> None:
        """Add the sprite and follow it."""
        super().setup()
        self.camera.follow(target=self.world_sprite)


class PaddleHitScene(Scene):
    """A stand-in for PaddleSlap: a world-space ball, a paddle, and a ball spawned on each hit.

    Its dt_tick moves every sprite, then pairs balls with the paddle through the collision
    manager; ``BallSprite.handle_paddle_collision`` reverses the ball's speed and calls
    ``on_paddle_collision``, which spawns a second world-space ball, all inside dt_tick, as
    PaddleSlap's ``_resolve_collisions`` does (src/games/paddleslap/src/paddleslap/__init__.py).
    """

    NAME = 'Paddle Hit'
    VERSION = '1.0'

    @override
    def setup(self: Self) -> None:
        """Add the left paddle and one ball, each in its collision layer."""
        self.background_color = BLACK
        self.player1 = VerticalPaddle(
            'Player 1',
            PADDLE_SIZE,
            (0, self.screen_height // 2 - PADDLE_SIZE[1] // 2),
            WHITE,
            PADDLE_SPEED,
        )
        self.collisions.add_layer('balls')
        self.collisions.add_layer('paddles')
        self.collisions.get_layer('paddles').add(self.player1)
        self.balls: list[BallSprite] = []
        self.all_sprites.add(self.player1)
        self._add_ball(ball=BallSprite(bounce_left_right=False))

    def _add_ball(self: Self, *, ball: BallSprite) -> None:
        """Add a ball to the balls, the sprites and the balls layer; a paddle hit spawns one."""
        ball.on_paddle_collision = self._spawn_ball
        self.balls.append(ball)
        self.all_sprites.add(ball)
        self.collisions.get_layer('balls').add(ball)

    def _spawn_ball(self: Self, _ball: BallSprite) -> None:
        """Spawn a ball at the screen's center, as PaddleSlap's default spawn mode does."""
        new_ball = BallSprite(bounce_left_right=False)
        new_ball.world_x = float(self.screen_width // 2)
        new_ball.world_y = float(self.screen_height // 2)
        new_ball.speed = Speed(*SPAWNED_BALL_SPEED)
        self._add_ball(ball=new_ball)

    @staticmethod
    def _on_ball_paddle_collision(ball: BallSprite, paddle: VerticalPaddle) -> None:
        """Bounce a ball the collision manager paired with the paddle, if it touches it."""
        ball.handle_paddle_collision(paddle)

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Move every sprite, then resolve this frame's paddle hits (spawning on a hit).

        Args:
            dt: The frame's delta time in seconds.

        """
        for sprite in self.all_sprites:
            sprite.dt_tick(dt)
        self.collisions.check_overlap('balls', 'paddles', callback=self._on_ball_paddle_collision)


@contextlib.contextmanager
def running_scene(
    scene_class: type[Scene], *, extra_arguments: Sequence[str] = ()
) -> Generator[GoldenTraceSceneManager]:
    """Start a scene headless in the harness's deterministic environment.

    Args:
        scene_class: The scene class to make active.
        extra_arguments: More command-line arguments (``--replay-trace PATH``).

    Yields:
        The scene manager with the scene active.

    """
    with (
        tempfile.TemporaryDirectory(prefix='frame-integration-saves-') as save_directory,
        deterministic_environment(save_root=Path(save_directory)),
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
                *extra_arguments,
            ]):
                engine = GoldenTraceEngine(game=scene_class)
            engine.install_game(scene_class=scene_class)
            yield manager
        finally:
            pygame.event.clear()
            GoldenTraceSceneManager.uninstall()


def step(manager: GoldenTraceSceneManager, *events: pygame.event.Event, frames: int = 1) -> None:
    """Run frames at the harness's fixed dt, posting events before the first one.

    It sets ``manager.dt`` itself and never calls ``SceneManager._finish_frame``, so a playback
    scope's frames get the harness's dt, not the recording's: playback tests stepped with it
    only work for recordings made by the harness (at FRAME_SECONDS). A recording made by the
    real frame loop (``--record-trace``, scripts/record_scripted_session.py) is played with
    ``step_finishing`` (tests/replay/playback_fixtures.py) instead.

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

    def test_a_scene_manager_made_before_any_display_has_no_screen(self, mocker: MockerFixture):
        """No display surface yet: the manager starts without a screen and finds it later."""
        display_surface = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
        get_surface = mocker.patch.object(pygame.display, 'get_surface', return_value=None)
        SceneManager._reset()
        try:
            manager = SceneManager()
            assert manager.screen is None
            get_surface.return_value = display_surface
            manager.update_screen()
            assert manager.screen is display_surface
        finally:
            SceneManager._reset()

    def test_a_scene_switched_to_without_a_display_is_set_up_and_active(
        self, mocker: MockerFixture
    ):
        """Switching scenes with no surface skips only the background redraw."""
        with running_scene(CameraFreeScene) as manager:
            departing_scene = manager.active_scene
            assert isinstance(departing_scene, CameraFreeScene)
            # A Scene needs the display to be built; the display goes away after that
            arriving_scene = CameraFreeScene(options=departing_scene.options)
            mocker.patch.object(pygame.display, 'get_surface', return_value=None)
            manager.screen = None

            manager.switch_to_scene(arriving_scene)

            assert manager.active_scene is arriving_scene
            assert manager.screen is None
            # setup() ran: its world sprite exists
            assert arriving_scene.world_sprite.world_x == PLAYER_START[0]


class NamelessScene(CameraFreeScene):
    """A scene with neither a name nor a version for the window caption."""

    NAME = ''
    VERSION = ''


class TestWindowCaption:
    """The window caption is the scene's name and version, each only when it has one."""

    @pytest.mark.parametrize(
        ('scene_class', 'expected_caption'),
        [(FollowingScene, 'Following v1.0'), (NamelessScene, '')],
        ids=['name-and-version', 'neither'],
    )
    def test_caption_names_the_active_scene(self, scene_class: type[Scene], expected_caption: str):
        with running_scene(scene_class) as manager:
            assert isinstance(manager.active_scene, scene_class)
            # pygame gives an empty tuple for an empty caption
            assert (pygame.display.get_caption() or ('',))[0] == expected_caption


class TestSceneRedraw:
    """Scene.update() forces its sprites to redraw only while the scene itself is dirty."""

    def test_a_clean_scene_leaves_clean_sprites_clean(self):
        with running_scene(CameraFreeScene) as manager:
            step(manager)
            scene = manager.active_scene
            assert isinstance(scene, CameraFreeScene)
            scene.dirty = 0
            scene.world_sprite.dirty = 0

            scene.update()

            assert scene.world_sprite.dirty == 0

    def test_a_dirty_scene_marks_clean_sprites_dirty(self):
        with running_scene(CameraFreeScene) as manager:
            step(manager)
            scene = manager.active_scene
            assert isinstance(scene, CameraFreeScene)
            scene.dirty = 1
            scene.world_sprite.dirty = 0

            scene.update()

            assert scene.world_sprite.dirty == 1


class TestSceneWithAnIdentityCamera:
    """A scene that never sets its camera up runs its frames on Scene's identity camera.

    Every Scene has a camera (the scene manager no longer accepts stand-ins without one); a
    scene that never follows or moves it keeps the identity camera, so the camera steps run
    but move nothing.
    """

    def test_frame_runs_on_the_identity_camera(self):
        """begin_frame, aim and positioning run, and the world sprite stays where it is drawn."""
        with running_scene(CameraFreeScene) as manager:
            scene = manager.active_scene
            assert isinstance(scene, CameraFreeScene)
            step(manager)
            sprite_rect_before = scene.world_sprite.rect.copy()

            step(manager, frames=2)

            assert scene.camera.follow_target is None
            # The identity camera: world positions are screen positions
            assert scene.camera.world_to_screen(0.0, 0.0) == (0, 0)
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

    def test_camera_waits_for_the_resumed_scene_logic(self):
        """A scene switched to during a frame's events is not aimed until its first dt_tick.

        Resuming from the pause screen switches scenes while events are processed, after the
        pause scene's logic ran. The resumed scene ran no logic that frame, so its camera must
        not take a smoothing step either: camera time stays in step with the scene's game time
        (the camera moved only in dt_tick before the engine aimed it).
        """
        with running_scene(FollowingScene) as manager:
            step(manager, frames=2)
            game_scene = active_following_scene(manager)
            game_scene.pause()
            step(manager)
            game_scene.player.world_x += PLAYER_STEP_X  # the camera now has somewhere to go
            step(manager, press(pygame.K_SPACE))
            camera_before_resume = (game_scene.camera.world_x, game_scene.camera.world_y)
            ticks_before_resume = game_scene.frame_number

            step(manager, release(pygame.K_SPACE))

            assert manager.active_scene is game_scene
            assert game_scene.frame_number == ticks_before_resume
            assert (game_scene.camera.world_x, game_scene.camera.world_y) == camera_before_resume
            step(manager)
            assert game_scene.frame_number == ticks_before_resume + 1
            assert (game_scene.camera.world_x, game_scene.camera.world_y) != camera_before_resume


class GameTimeScene(CameraFreeScene):
    """Overrides dt_tick without calling super: game time is the engine's, not the scene's."""

    NAME = 'Game Time'
    MAX_FRAME_SECONDS: ClassVar[float | None] = 0.05

    @override
    def dt_tick(self: Self, dt: float) -> None:
        """Remember the dt, skipping Scene.dt_tick.

        Args:
            dt: The frame's (capped) delta time in seconds.

        """
        self.last_dt = dt


class TestGameTime:
    """Scene.game_time sums the scene's (capped) dt and stops while the scene is not running."""

    def test_game_time_sums_the_scene_dt_even_without_super(self):
        """A dt_tick override that skips super() still advances game time."""
        with running_scene(GameTimeScene) as manager:
            step(manager, frames=4)
            assert manager.active_scene is not None
            assert manager.active_scene.game_time == pytest.approx(4 * FRAME_SECONDS)

    def test_game_time_uses_the_capped_dt(self):
        """A long frame advances game time by MAX_FRAME_SECONDS only."""
        with running_scene(GameTimeScene) as manager:
            manager.dt = 2.0
            manager.run_frame()
            assert manager.active_scene is not None
            assert manager.active_scene.game_time == pytest.approx(GameTimeScene.MAX_FRAME_SECONDS)

    def test_game_time_stops_while_paused(self):
        """While the pause scene runs, the paused game's time stands still."""
        with running_scene(StillCameraScene) as manager:
            step(manager, frames=2)
            game_scene = manager.active_scene
            assert game_scene is not None
            # pause() switches at the end of the next frame, after the game's dt_tick
            game_scene.pause()
            step(manager)
            assert isinstance(manager.active_scene, PauseScene)
            paused_at = game_scene.game_time
            assert paused_at > 0
            step(manager, frames=PAUSE_FRAMES)
            assert isinstance(manager.active_scene, PauseScene)
            assert game_scene.game_time == paused_at


START_CAPTURE_SAVE_NAMESPACE = 'start-capture-test'
SHARED_STREAM_NAME = 'test.shared'
# Prints the replay package's modules loaded by importing glitchygames.scenes
REPLAY_MODULES_AFTER_IMPORTING_SCENES = (
    'import sys, glitchygames.scenes\n'
    "print(sorted(name for name in sys.modules if name.startswith('glitchygames.replay')))"
)
# Frame time that passes between building a scene and setting it up (a floor built a frame early)
FRAME_SECONDS_BEFORE_SETUP = 0.5


class StartCapturedScene(CameraFreeScene):
    """Draws as it is built and as it is set up, carries a level and saves while it is built."""

    NAME = 'Start Captured'

    def __init__(
        self: Self,
        options: dict[str, Any] | None = None,
        groups: pygame.sprite.LayeredDirty[Any] | None = None,
        level: int = 1,
    ) -> None:
        """Draw the spawn position, then write a save slot (before setup()).

        Args:
            options: The game's options.
            groups: The sprite group.
            level: The level this scene plays (its replay argument).

        """
        super().__init__(options=options, groups=groups)
        self.level = level
        self.spawn_x = random_stream('test.spawn').randrange(0, 100)
        self.saves = open_saves(app_name=START_CAPTURE_SAVE_NAMESPACE)
        self.saves_seen_while_built = self.saves.slot_names()
        self.saves.save('progress', {'level': level})
        self.setup_draw: float | None = None
        self.setup_frame_clock: float | None = None

    @override
    def setup(self: Self) -> None:
        """Draw from a stream other code shares and read the frame clock."""
        super().setup()
        self.setup_draw = random_stream(SHARED_STREAM_NAME).random()
        self.setup_frame_clock = frame_clock_seconds()

    @override
    def replay_arguments(self: Self) -> dict[str, Any]:
        """Rebuild with the same level.

        Returns:
            The level.

        """
        return {'level': self.level}


class UncapturedScene(StartCapturedScene):
    """A scene that cannot be rebuilt on its own opts out of start capture."""

    CAPTURES_SCENE_START: ClassVar[bool] = False


def _built_early(*, options: dict[str, Any]) -> StartCapturedScene:
    """Build a scene, then let other code draw and frame time pass before it is set up.

    Args:
        options: The scene's options.

    Returns:
        The scene, not set up.

    """
    scene = StartCapturedScene(options=options, level=2)
    random_stream(SHARED_STREAM_NAME).random()
    advance_frame_clock(seconds=FRAME_SECONDS_BEFORE_SETUP)
    return scene


class TestSceneStart:
    """A scene's start capture holds what rebuilding it as it began needs."""

    def test_start_capture_holds_arguments_streams_clock_and_saves(self, mocker):
        """The start names the class, its arguments, both moments and the saves before __init__."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(StartCapturedScene) as manager:
            start = manager.active_scene_start
            assert start is not None
            assert start.scene_class == 'StartCapturedScene'
            assert start.arguments == {'level': 1}
            assert start.construction_frame_clock_seconds == 0.0
            assert start.setup_frame_clock_seconds == 0.0
            assert start.construction_random_states['seed'] == RANDOM_SEED
            # First opened inside __init__: snapshotted when opened, before __init__ wrote to it
            assert start.saves == {START_CAPTURE_SAVE_NAMESPACE: {}}
            assert SceneStart.from_json(json.loads(json.dumps(start.to_json()))) == start

    def test_stores_open_before_construction_are_seen_as_they_were(self, mocker):
        """A store already open when the scene is built is snapshotted before __init__ writes."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(CameraFreeScene) as manager:
            assert manager.active_scene is not None
            open_saves(app_name=START_CAPTURE_SAVE_NAMESPACE).save('progress', {'level': 7})
            scene = StartCapturedScene(options=manager.active_scene.options, level=3)
            manager.switch_to_scene(scene)
            start = manager.active_scene_start
            assert start is not None
            progress = start.saves[START_CAPTURE_SAVE_NAMESPACE]['progress']
            assert progress['data'] == {'level': 7}

    def test_the_first_logic_frame_is_captured_at_its_top(self, mocker):
        """The start is completed as the first frame running the scene's logic begins."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(StartCapturedScene) as manager:
            start = manager.active_scene_start
            assert start is not None
            assert start.first_logic_frame is None
            states_before_the_frame = capture_stream_states()
            step(manager)
            completed = manager.active_scene_start
            assert completed is not None
            first_logic_frame = completed.first_logic_frame
            assert first_logic_frame is not None
            assert first_logic_frame.random_states == states_before_the_frame
            assert first_logic_frame.frame_clock_seconds == frame_clock_seconds()
            assert first_logic_frame.earlier_internal_event_count == 0
            assert first_logic_frame.arrived_by_transition is False
            # Later frames keep it
            step(manager)
            assert manager.active_scene_start is completed

    def test_rebuilt_scene_draws_the_same_randomness(self, mocker):
        """A rebuild restores the streams and frame clock the original began with."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(StartCapturedScene) as manager:
            original = manager.active_scene
            start = manager.active_scene_start
            assert isinstance(original, StartCapturedScene)
            assert start is not None
            step(manager, frames=2)
            # Advance the stream after the start, so only a restore draws the same value
            random_stream('test.spawn').random()
            rebuilt = rebuild_scene(
                start=start, scene_class=StartCapturedScene, options=original.options
            )
            assert isinstance(rebuilt, StartCapturedScene)
            assert rebuilt.spawn_x == original.spawn_x
            assert rebuilt.level == 1
            assert frame_clock_seconds() == start.setup_frame_clock_seconds

    def test_a_scene_built_early_rebuilds_exactly(self, mocker):
        """Draws and frame time between building and setting up a scene are restored too."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(CameraFreeScene) as manager:
            assert manager.active_scene is not None
            original = _built_early(options=manager.active_scene.options)
            manager.switch_to_scene(original)
            start = manager.active_scene_start
            assert start is not None
            assert start.setup_frame_clock_seconds == pytest.approx(
                start.construction_frame_clock_seconds + FRAME_SECONDS_BEFORE_SETUP
            )
            original_next_draw = random_stream(SHARED_STREAM_NAME).random()
            rebuilt = rebuild_scene(
                start=start, scene_class=StartCapturedScene, options=original.options
            )
            assert isinstance(rebuilt, StartCapturedScene)
            manager.switch_to_scene(rebuilt)
            assert rebuilt.spawn_x == original.spawn_x
            assert rebuilt.setup_draw == original.setup_draw
            assert rebuilt.setup_frame_clock == original.setup_frame_clock
            # The save view is the one the original's __init__ saw, before its own write (the
            # playback scope sandboxes it for the rebuilt scene; here the real store has the write)
            assert original.saves_seen_while_built == []
            assert start.saves == {START_CAPTURE_SAVE_NAMESPACE: {}}
            assert random_stream(SHARED_STREAM_NAME).random() == original_next_draw

    def test_the_start_shares_no_mutable_state(self, mocker):
        """Changing what to_json returned, or the record read, never changes the start."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(StartCapturedScene) as manager:
            start = manager.active_scene_start
            assert start is not None
            record = start.to_json()
            record['arguments']['level'] = 99
            record['construction_random_states']['seed'] = 0
            assert start.arguments == {'level': 1}
            assert start.construction_random_states['seed'] == RANDOM_SEED
            read_back = SceneStart.from_json(record)
            record['arguments']['level'] = 5
            assert read_back.arguments == {'level': 99}

    def test_non_json_arguments_are_refused(self, mocker):
        """replay_arguments() that would not read back from JSON is a TypeError naming the scene."""

        class BadArguments(StartCapturedScene):
            @override
            def replay_arguments(self: Self) -> dict[str, Any]:
                return {'surface': object()}

        mocker.patch.object(BadArguments, 'INSTANT_REPLAY_SECONDS', 10.0)
        with pytest.raises(TypeError, match='BadArguments'), running_scene(BadArguments):
            pass

    def test_tuple_arguments_are_refused(self, mocker):
        """A tuple reads back from JSON as a list, so the rebuild would differ: refused."""

        class TupleArguments(StartCapturedScene):
            @override
            def replay_arguments(self: Self) -> dict[str, Any]:
                return {'position': (1, 2)}

        mocker.patch.object(TupleArguments, 'INSTANT_REPLAY_SECONDS', 10.0)
        with pytest.raises(TypeError, match='TupleArguments'), running_scene(TupleArguments):
            pass


class TestSceneStartCaptureScope:
    """Starts are captured only while they can be used, and a scene keeps its first one."""

    def test_live_play_captures_nothing(self):
        """Without recording, playback or instant replay, no scene start is captured."""
        with running_scene(StartCapturedScene) as manager:
            assert manager.active_scene_start is None

    def test_a_scene_that_opts_out_captures_nothing(self, mocker):
        """CAPTURES_SCENE_START = False wins over instant replay and capturing doors."""
        mocker.patch.object(UncapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(UncapturedScene) as manager:
            assert manager.active_scene_start is None

    def test_the_pause_screen_opts_out(self):
        """PauseScene presents another scene, so it cannot be rebuilt on its own."""
        assert PauseScene.CAPTURES_SCENE_START is False
        assert scene_start_capture_enabled(scene_class=PauseScene) is False

    def test_resume_from_pause_keeps_the_first_capture(self, mocker):
        """Resuming runs the scene's setup again but keeps the start of its first setup."""
        mocker.patch.object(StartCapturedScene, 'INSTANT_REPLAY_SECONDS', 10.0)
        with running_scene(StartCapturedScene) as manager:
            game_scene = manager.active_scene
            assert game_scene is not None
            step(manager, frames=2)
            # Complete once its first logic frame began (glitchygames/scene_start.py, rule 7)
            first = manager.active_scene_start
            assert first is not None
            assert first.first_logic_frame is not None
            game_scene.pause()
            step(manager)
            assert isinstance(manager.active_scene, PauseScene)
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE))
            assert manager.active_scene is game_scene
            assert manager.active_scene_start is first

    def test_scenes_do_not_import_the_replay_driver(self):
        """glitchygames.scenes stays light: start capture lives in a leaf module."""
        completed = run_command(
            command=[
                sys.executable,
                '-c',
                REPLAY_MODULES_AFTER_IMPORTING_SCENES,
            ],
            environment=dict(os.environ),
            timeout_seconds=60.0,
            capture_output=OutputCapture.TOGETHER,
        )
        assert completed.returncode == 0, completed.stdout
        assert completed.stdout.strip().splitlines()[-1] == '[]'


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

    def test_arriving_capture_snaps_only_the_followed_axes(self):
        """An X-only follow scene entered through a transition keeps its camera's y.

        The capture snaps the camera to its target so the screenshot shows the right view;
        snapping y too would leave an X-only camera at the player's y for good (the aim never
        moves an unfollowed axis).
        """
        with running_scene(CapturedPlayerScene) as manager:
            step(manager)
            departing_scene = manager.active_scene
            assert isinstance(departing_scene, CapturedPlayerScene)

            departing_scene.transition_to(
                XFollowScene(options=departing_scene.options),
                FadeTransition(duration=TEST_FADE_SECONDS),
            )
            step(manager)

            arriving_scene = manager.active_scene
            assert isinstance(arriving_scene, XFollowScene)
            camera = arriving_scene.camera
            assert camera.world_x == arriving_scene.player.world_x - camera.lead_x
            assert camera.world_y == X_FOLLOW_CAMERA_Y

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

    @pytest.mark.parametrize('capture_index', [0, 1], ids=['outgoing', 'arriving'])
    def test_screen_space_player_is_hidden_in_both_captures(
        self, mocker: MockerFixture, capture_index: int
    ):
        """A screen-space player is left out of both screenshots and shown again afterwards."""
        with running_scene(ScreenPlayerScene) as manager:
            step(manager, frames=2)
            departing_scene = manager.active_scene
            assert isinstance(departing_scene, ScreenPlayerScene)
            assert manager.screen is not None
            assert color_pixel_count(manager.screen, PLAYER_COLOR) > 0

            transition = FadeTransition(duration=TEST_FADE_SECONDS)
            start_spy = mocker.spy(transition, 'start')
            departing_scene.transition_to(
                ScreenPlayerScene(options=departing_scene.options), transition
            )
            step(manager)

            assert start_spy.call_count == 1
            capture = start_spy.call_args.args[capture_index]
            assert color_pixel_count(capture, PLAYER_COLOR) == 0
            assert color_pixel_count(capture, LANDMARK_COLOR) > 0
            arriving_scene = manager.active_scene
            assert isinstance(arriving_scene, ScreenPlayerScene)
            assert departing_scene.player.visible
            assert arriving_scene.player.visible
            # The engine never moves a screen-space player
            assert arriving_scene.player.rect.topleft == SCREEN_SPRITE_TOPLEFT

    def test_an_invisible_screen_space_player_stays_invisible_after_the_capture(self):
        """The arriving capture gives a screen-space player back the visible it had."""
        with running_scene(ScreenPlayerScene) as manager:
            step(manager)
            departing_scene = manager.active_scene
            assert isinstance(departing_scene, ScreenPlayerScene)

            departing_scene.transition_to(
                InvisibleScreenPlayerScene(options=departing_scene.options),
                FadeTransition(duration=TEST_FADE_SECONDS),
            )
            step(manager)

            arriving_scene = manager.active_scene
            assert isinstance(arriving_scene, InvisibleScreenPlayerScene)
            assert not arriving_scene.player.visible


class TestWorldBallsInTheFrame:
    """A PaddleSlap-like scene's world-space balls are drawn where its logic left them."""

    def test_paddle_hit_and_spawned_ball_are_drawn_at_their_world_positions(self):
        """A paddle bounce and the ball it spawns are both placed before that frame's render.

        Both happen in the game's dt_tick; the engine then positions world sprites, so neither
        ball is drawn a frame late, and the new ball is never drawn at (0, 0).
        """
        with running_scene(PaddleHitScene) as manager:
            step(manager)
            game = manager.active_scene
            assert isinstance(game, PaddleHitScene)
            ball = game.balls[0]
            paddle = game.player1
            # Visible circle 1 px right of the left paddle, moving left 5 px: inside it after
            # one frame
            visible_offset_x, _visible_offset_y = collision_rect_offset(ball)
            ball.world_x = float(paddle.rect.right + 1 - visible_offset_x)
            ball.world_y = float(paddle.rect.centery - ball.rect.height // 2)
            ball.speed.x = -300.0
            ball.speed.y = 0.0

            step(manager)

            assert len(game.balls) == PADDLESLAP_BALLS_AFTER_ONE_SPAWN
            assert ball.speed.x > 0  # bounced this frame
            spawned_ball = game.balls[-1]
            for drawn_ball in (ball, spawned_ball):
                assert drawn_ball.rect.topleft == snapped_world_position(
                    drawn_ball, drawn_ball.world_x, drawn_ball.world_y
                )
            assert spawned_ball.rect.topleft != (0, 0)


class TestWorldShakeOnAStillCamera:
    """A WORLD shake decays even when nothing moves the camera (final review, Important 1).

    Before the fix the shake advanced only when the camera moved (camera.update() or the
    engine aim), so on a still camera it stayed at full strength forever: world sprites stayed
    displaced and the rumble stayed on.
    """

    @pytest.mark.parametrize(
        'scene_class', [StillCameraScene, StoppedFollowScene], ids=['no-target', 'target-none']
    )
    def test_world_shake_decays_and_the_sprite_returns(self, scene_class: type[Scene]):
        """The sprite shakes, then is drawn at rest again, and the rumble stops."""
        with running_scene(scene_class) as manager:
            step(manager)
            scene = manager.active_scene
            assert isinstance(scene, StillCameraScene)
            assert scene.world_sprite.rect.topleft == STILL_SPRITE_POSITION

            scene.shake(STILL_CAMERA_SHAKE, targets=ShakeTarget.WORLD)
            assert scene.camera.shake_effect.rumble_levels != (0.0, 0.0)
            drawn_positions: list[tuple[int, int]] = []
            for _frame in range(STILL_CAMERA_SHAKE_FRAMES):
                step(manager)
                drawn_positions.append(scene.world_sprite.rect.topleft)

            assert any(position != STILL_SPRITE_POSITION for position in drawn_positions)
            assert scene.camera.shake_effect.is_active is False
            assert scene.camera.shake_effect.offset == (0.0, 0.0)
            assert scene.world_sprite.rect.topleft == STILL_SPRITE_POSITION
            assert scene.camera.shake_effect.rumble_levels == (0.0, 0.0)
            assert scene.camera.shake_effect.rumble_remaining == 0.0
            # Nothing moved the camera itself
            assert (scene.camera.world_x, scene.camera.world_y) == (0.0, 0.0)

    @pytest.mark.parametrize(
        'scene_class',
        [
            StillCameraScene,
            StoppedFollowScene,
            AimedCameraScene,
            GameMovedCameraScene,
            DoubleMovedCameraScene,
        ],
        ids=['neither', 'target-none', 'aimed', 'game-moved', 'game-moved-and-aimed'],
    )
    def test_shake_advances_exactly_once_per_frame(
        self, mocker: MockerFixture, scene_class: type[Scene]
    ):
        """Whoever moves the camera (nobody, the engine, the game, both), one advance a frame.

        Each advance gets the scene's dt, the dt the engine aim would have used.
        """
        with running_scene(scene_class) as manager:
            step(manager)
            scene = manager.active_scene
            assert isinstance(scene, StillCameraScene)
            shake_update_spy = mocker.spy(scene.camera.shake_effect, 'update')

            step(manager, frames=SHAKE_ADVANCE_FRAMES)

            assert [call.args for call in shake_update_spy.call_args_list] == [
                (FRAME_SECONDS,)
            ] * SHAKE_ADVANCE_FRAMES


class TestInputSnapshotInTheFrame:
    """The snapshot is taken once per frame, right after the pump, and stays fixed."""

    def test_snapshot_taken_after_the_pump_is_the_frames_input(self, mocker: MockerFixture):
        """Each frame pumps, then captures one snapshot, which becomes the engine's input."""
        order: list[str] = []
        captured: list[InputSnapshot] = []
        original_pump = GameEngine._pump_events

        def recording_pump(engine: GameEngine) -> list[pygame.event.Event]:
            order.append('pump')
            return original_pump(engine)

        def distinct_capture(**keywords: Any) -> InputSnapshot:
            # A different snapshot every frame, so each frame's input is identifiable
            order.append('capture')
            snapshot = InputSnapshot(
                pressed_scancodes=frozenset(),
                modifiers=0,
                mouse_position=(len(captured), 0),
                mouse_buttons=(False, False, False),
                mouse_focused=True,
                **keywords,
            )
            captured.append(snapshot)
            return snapshot

        mocker.patch.object(GameEngine, '_pump_events', autospec=True, side_effect=recording_pump)
        # LiveSources calls the name it imported into glitchygames/live_sources.py
        mocker.patch.object(live_sources_module, 'capture_live_snapshot', distinct_capture)
        with running_scene(CameraFreeScene) as manager:
            assert manager.game_engine is not None
            for frame_index in range(INPUT_SNAPSHOT_FRAMES):
                step(manager)
                assert len(captured) == frame_index + 1
                assert manager.game_engine.input is captured[-1]
                assert current_input() is captured[-1]
        assert order == ['pump', 'capture'] * INPUT_SNAPSHOT_FRAMES


class OrderRecordingSupervisor:
    """A supervisor that records each call's frame number and scene class name."""

    def __init__(self: Self) -> None:
        """Create the supervisor with no calls recorded yet."""
        self.calls: list[tuple[int, str]] = []

    def on_frame(self: Self, *, frame_number: int, scene: Scene | None) -> None:
        """Record the frame number and the scene's class name."""
        self.calls.append((frame_number, type(scene).__name__))


class TestSupervisorHook:
    """Supervisors run once per frame at their slot, after events and before frame services."""

    def test_supervisors_run_once_per_frame_after_events(self, mocker: MockerFixture) -> None:
        with running_scene(CameraFreeScene) as manager:
            supervisor = OrderRecordingSupervisor()
            manager.add_supervisor(supervisor=supervisor)
            order: list[str] = []
            mocker.patch.object(
                manager, '_process_events', side_effect=lambda: order.append('events')
            )
            mocker.patch.object(
                manager, '_update_frame_services', side_effect=lambda: order.append('services')
            )
            original_on_frame = supervisor.on_frame

            def ordered_on_frame(**keywords: Any) -> None:
                order.append('supervisor')
                original_on_frame(**keywords)

            mocker.patch.object(supervisor, 'on_frame', side_effect=ordered_on_frame)
            step(manager, frames=2)
        assert order == ['events', 'supervisor', 'services'] * 2
        assert supervisor.calls == [(0, 'CameraFreeScene'), (1, 'CameraFreeScene')]

    def test_supervisors_run_in_transition_frames(self, mocker: MockerFixture) -> None:
        with running_scene(CameraFreeScene) as manager:
            supervisor = OrderRecordingSupervisor()
            manager.add_supervisor(supervisor=supervisor)
            order: list[str] = []
            mocker.patch.object(
                manager,
                '_process_transition_events',
                side_effect=lambda: order.append('transition events'),
            )
            mocker.patch.object(
                manager, '_update_frame_services', side_effect=lambda: order.append('services')
            )
            original_on_frame = supervisor.on_frame

            def ordered_on_frame(**keywords: Any) -> None:
                order.append('supervisor')
                original_on_frame(**keywords)

            mocker.patch.object(supervisor, 'on_frame', side_effect=ordered_on_frame)
            manager._active_transition = mocker.Mock(**{'update.return_value': False})
            step(manager, frames=1)
            manager._active_transition = None
        assert order == ['transition events', 'supervisor', 'services']
        assert supervisor.calls == [(0, 'CameraFreeScene')]

    def test_removed_supervisor_is_not_called(self) -> None:
        with running_scene(CameraFreeScene) as manager:
            supervisor = OrderRecordingSupervisor()
            manager.add_supervisor(supervisor=supervisor)
            manager.remove_supervisor(supervisor=supervisor)
            step(manager, frames=1)
        assert supervisor.calls == []

    def test_a_supervisor_the_scope_removed_and_the_live_game_re_added_outlives_the_scope(
        self,
    ) -> None:
        """Removing a scope's supervisor forgets it was the scope's (playback.py rule 4).

        The scope's code adds a supervisor and removes it again; a live supervisor then adds
        the same one while the scope plays, which makes it the live game's. The scope's end
        removes only what still belongs to the scope, so the supervisor keeps running after.
        """
        with running_scene(CameraFreeScene) as manager:
            supervisor = OrderRecordingSupervisor()
            push_scoped_sources(sources=LiveSources(random_seed=RANDOM_SEED))
            try:
                assert manager.in_playback_scope
                # The scope's code (its scene's setup(), say) adds it and removes it again
                manager.add_supervisor(supervisor=supervisor)
                manager.remove_supervisor(supervisor=supervisor)
                # A live supervisor adds it while the scope plays: it is the live game's
                manager._run_live_or_scope_code(
                    is_scope_code=False,
                    call=lambda: manager.add_supervisor(supervisor=supervisor),
                )
                # What the scope's end does before its doors are popped
                manager._remove_scope_supervision()
            finally:
                pop_scoped_sources()
            step(manager, frames=1)
        assert supervisor.calls == [(0, 'CameraFreeScene')]


class TestControlEvents:
    """Control events reach their handlers and the doors' end_frame, live or scheduled."""

    def test_recorded_control_events_reach_handlers_and_end_frame(
        self, mocker: MockerFixture
    ) -> None:
        handled: list[ControlEvent] = []
        with running_scene(CameraFreeScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            end_frame = mocker.spy(active_sources(), 'end_frame')
            manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'here'})
            step(manager, frames=2)
        assert handled == [ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'here'})]
        first_frame_call, second_frame_call = end_frame.call_args_list
        assert first_frame_call.kwargs['control_events'] == handled
        # Each frame's list holds that frame's control events only
        assert second_frame_call.kwargs['control_events'] == []

    def test_scheduled_control_events_are_applied_at_the_slot(self, mocker: MockerFixture) -> None:
        scheduled = ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'from recording'})
        handled: list[ControlEvent] = []
        with running_scene(CameraFreeScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            mocker.patch.object(
                active_sources(),
                'control_events_for_frame',
                side_effect=lambda frame_number: [scheduled] if frame_number == 1 else [],
            )
            step(manager, frames=3)
        assert handled == [scheduled]

    def test_a_failing_handler_still_lets_the_others_run_then_fails_loudly(
        self, mocker: MockerFixture
    ) -> None:
        handled: list[ControlEvent] = []

        def broken_handler(control_event: ControlEvent) -> None:
            message = f'broken handler got {control_event.kind}'
            raise ValueError(message)

        def also_broken_handler(control_event: ControlEvent) -> None:
            message = f'second broken handler got {control_event.kind}'
            raise KeyError(message)

        with running_scene(CameraFreeScene) as manager:
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=broken_handler)
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=also_broken_handler)
            manager.add_control_event_handler(kind=BREAKPOINT_KIND, handler=handled.append)
            end_frame = mocker.spy(active_sources(), 'end_frame')
            with pytest.raises(ValueError, match='broken handler got breakpoint'):
                manager.record_control_event(kind=BREAKPOINT_KIND, data={'label': 'here'})
            step(manager, frames=1)
        recorded = ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'here'})
        assert handled == [recorded]
        assert end_frame.call_args.kwargs['control_events'] == [recorded]

    def test_recorded_data_is_a_read_only_copy(self, mocker: MockerFixture) -> None:
        data: dict[str, Any] = {'label': 'here', 'path': {'steps': [1, 2]}}
        with running_scene(CameraFreeScene) as manager:
            end_frame = mocker.spy(active_sources(), 'end_frame')
            manager.record_control_event(kind=BREAKPOINT_KIND, data=data)
            data['label'] = 'changed'
            data['path']['steps'].append(3)
            step(manager, frames=1)
        (recorded,) = end_frame.call_args.kwargs['control_events']
        assert recorded.to_json() == {
            'kind': 'breakpoint',
            'label': 'here',
            'path': {'steps': [1, 2]},
        }
        recorded_data = recorded.data
        with pytest.raises(TypeError):
            recorded_data['label'] = 'changed'
        with pytest.raises(TypeError):
            recorded_data['path']['steps'] = []
        with pytest.raises(AttributeError):
            recorded_data['path']['steps'].append(3)

    def test_to_json_returns_plain_json_types(self) -> None:
        event = ControlEvent(kind=BREAKPOINT_KIND, data={'path': {'steps': [1, 2]}})
        record = event.to_json()
        assert type(record) is dict
        assert type(record['path']) is dict
        assert type(record['path']['steps']) is list
        assert json.loads(json.dumps(record)) == record

    def test_control_event_json_round_trip(self) -> None:
        event = ControlEvent(kind=BREAKPOINT_KIND, data={'label': 'x'})
        assert event.to_json() == {'kind': 'breakpoint', 'label': 'x'}
        assert ControlEvent.from_json(event.to_json()) == event


def ghost_square(_sample: GhostSample) -> pygame.Surface:
    """Draw any ghost sample as a square the player's size.

    Returns:
        A new surface.

    """
    return pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))


class TestGhostsInTheFrame:
    """Ghosts are recorded at the supervisor slot and positioned by the engine like any sprite."""

    def test_recorder_samples_once_per_frame_and_stops_on_finish(self):
        with running_scene(FollowingScene) as manager:
            scene = active_following_scene(manager)
            recorder = GhostRecorder(sprite=scene.player, scene=scene)
            step(manager, frames=4)
            track = recorder.finish()
            step(manager, frames=2)
        assert len(track.samples) == 4
        assert [recorded.game_seconds for recorded in track.samples] == pytest.approx([
            FRAME_SECONDS * index for index in range(1, 5)
        ])
        # Sampled after the frame's logic: the player had moved PLAYER_STEP_X each frame
        assert [recorded.world_x for recorded in track.samples] == pytest.approx([
            PLAYER_START[0] + PLAYER_STEP_X * index for index in range(1, 5)
        ])

    def test_recorder_skips_the_frames_its_scene_is_paused(self):
        """Behind the pause screen the scene's game time stands still: nothing is sampled."""
        with running_scene(FollowingScene) as manager:
            game_scene = active_following_scene(manager)
            recorder = GhostRecorder(sprite=game_scene.player, scene=game_scene)
            step(manager, frames=2)
            game_scene.pause()
            step(manager)
            assert isinstance(manager.active_scene, PauseScene)
            step(manager, frames=PAUSE_FRAMES)
            step(manager, press(pygame.K_SPACE))
            step(manager, release(pygame.K_SPACE))
            assert manager.active_scene is game_scene
            step(manager, frames=2)
            track = recorder.finish()
        game_seconds = [recorded.game_seconds for recorded in track.samples]
        assert game_seconds == sorted(set(game_seconds))
        assert game_seconds[-1] == pytest.approx(game_scene.game_time)
        # Frames 1-3 ran the scene's logic (pause() switches at the end of the third),
        # the resume frame ran none, the two after it did
        assert len(track.samples) == 5

    def test_a_ghost_lines_up_with_a_live_run_of_the_same_scene(self):
        """Drawn where the player is, each frame: the ghost lags no frame behind."""
        with running_scene(FollowingScene) as manager:
            recorded_scene = active_following_scene(manager)
            recorder = GhostRecorder(sprite=recorded_scene.player, scene=recorded_scene)
            step(manager, frames=GHOST_RECORDED_FRAMES)
            track = recorder.finish()
        with running_scene(FollowingScene) as manager:
            scene = active_following_scene(manager)
            ghost = GhostSprite(track=track, image_for=ghost_square)
            ghost.scene = scene
            scene.all_sprites.add(ghost)
            drawn: list[tuple[tuple[int, int], tuple[int, int]]] = []
            for _frame in range(GHOST_RECORDED_FRAMES):
                step(manager)
                drawn.append((ghost.rect.topleft, scene.player.rect.topleft))
        assert all(ghost_topleft == player_topleft for ghost_topleft, player_topleft in drawn)
        assert ghost.visible
        assert ghost.hidden is False

    def test_ghost_is_culled_like_any_world_sprite(self):
        far_away = GhostTrack(
            samples=(
                GhostSample(
                    game_seconds=0.0, world_x=100_000.0, world_y=0.0, appearance={}, visible=True
                ),
            )
        )
        with running_scene(CameraFreeScene) as manager:
            scene = manager.active_scene
            assert scene is not None
            ghost = GhostSprite(track=far_away, image_for=ghost_square)
            ghost.scene = scene
            scene.all_sprites.add(ghost)
            step(manager, frames=1)
        assert ghost.visible == 0  # outside the screen plus CULL_MARGIN_PIXELS
        assert ghost.hidden is False  # culled by the engine, not hidden by the track

    def test_a_ghost_with_nothing_to_show_is_culled_by_the_engine(self):
        """Before its first sample its image is empty, which the engine's culling hides."""
        later = GhostTrack(
            samples=(
                GhostSample(
                    game_seconds=1.0,
                    world_x=PLAYER_START[0],
                    world_y=PLAYER_START[1],
                    appearance={},
                    visible=True,
                ),
            )
        )
        with running_scene(CameraFreeScene) as manager:
            scene = manager.active_scene
            assert scene is not None
            ghost = GhostSprite(track=later, image_for=ghost_square)
            ghost.scene = scene
            scene.all_sprites.add(ghost)
            step(manager, frames=1)
            assert ghost.visible == 0
            assert ghost.hidden is False
            step(manager, frames=round(1.0 / FRAME_SECONDS) + 1)
            assert ghost.visible == 1
