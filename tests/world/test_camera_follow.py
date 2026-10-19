"""Camera follow, the Scene.camera_target() hook and the engine's camera aim.

Uses a real Camera2D, real Scenes and real parallax layers (no pygame mocking), so the camera
positions asserted here are the ones the frame loop will produce once it calls aim_camera().
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import world
from glitchygames.camera import Camera2D, FollowAxes
from glitchygames.effects.shake import Shake, ShakeAxis, ShakeStyle, ShakeTarget
from glitchygames.pixel_snap import PixelSnapMode, set_active_default_snap_mode, snap_to_pixel
from glitchygames.scenes import Scene
from glitchygames.world import CoordinateSpace, aim_camera

if TYPE_CHECKING:
    from pytest_mock import MockerFixture, MockType

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
FRAME_SECONDS = 1.0 / 60.0

CAMERA_START = (0.0, 50.0)
TARGET_POSITION = (200.0, 300.0)
HOOK_POSITION = (-40.0, 75.0)
LEAD_OFFSET = (100.0, 120.0)

# A fractional camera position whose snapped value differs between snap modes
FRACTIONAL_CAMERA_X = 10.5
FRACTIONAL_CAMERA_Y = -3.5
PARALLAX_SCROLL_FACTOR = 0.5

SHAKE_STRENGTH = 10.0
SHAKE_SECONDS = 1.0
SHAKE_FREQUENCY = 2.0

DOUBLE_UPDATE_WARNING_FRAGMENT = 'camera.update() called by the game'


class FollowedSprite(pygame.sprite.DirtySprite):
    """A minimal world sprite for the camera to follow."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self, *, world_x: float, world_y: float) -> None:
        """Create the sprite at a world position.

        Args:
            world_x: World X of the sprite.
            world_y: World Y of the sprite.

        """
        super().__init__()
        self.world_x = world_x
        self.world_y = world_y
        self.rect = pygame.Rect(0, 0, 8, 8)


class PositionlessSprite(pygame.sprite.DirtySprite):
    """A sprite with no world position, which a camera cannot follow."""


class HookScene(Scene):
    """A scene whose camera_target() hook supplies the point, overriding any follow target."""

    def camera_target(self) -> tuple[float, float] | None:
        """Aim at a fixed point.

        Returns:
            tuple[float, float] | None: HOOK_POSITION.

        """
        return HOOK_POSITION


def make_camera(**camera_options: float) -> Camera2D:
    """Build an instantly-following camera at CAMERA_START.

    Args:
        **camera_options: Extra Camera2D keyword options (lead_x, smooth_factor, ...).

    Returns:
        Camera2D: The camera.

    """
    options: dict[str, float] = {'smooth_factor': 1.0, **camera_options}
    camera = Camera2D(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, **options)
    camera.world_x, camera.world_y = CAMERA_START
    return camera


def make_scene(*, scene_class: type[Scene] = Scene, camera: Camera2D) -> Scene:
    """Build a real scene using the given camera.

    Args:
        scene_class: The Scene class to instantiate.
        camera: The camera the scene uses.

    Returns:
        Scene: The scene.

    """
    scene = scene_class(options={})
    scene.camera = camera
    return scene


def make_target() -> FollowedSprite:
    """Build a sprite at TARGET_POSITION.

    Returns:
        FollowedSprite: The target.

    """
    return FollowedSprite(world_x=TARGET_POSITION[0], world_y=TARGET_POSITION[1])


def bounce_shake() -> Shake:
    """Build a deterministic vertical bounce shake.

    Returns:
        Shake: The shake.

    """
    return Shake(
        style=ShakeStyle.BOUNCE,
        strength=SHAKE_STRENGTH,
        duration=SHAKE_SECONDS,
        frequency=SHAKE_FREQUENCY,
        axis=ShakeAxis.VERTICAL,
    )


def add_recording_layer(*, camera: Camera2D, mocker: MockerFixture) -> MockType:
    """Add a real scrolling parallax layer and record its update_scroll calls.

    Args:
        camera: The camera to add the layer to.
        mocker: The pytest-mock fixture.

    Returns:
        The update_scroll spy.

    """
    layer = camera.add_background_layer(
        scroll_factor=PARALLAX_SCROLL_FACTOR,
        draw_function=lambda surface, offset_x, offset_y: None,
        layer_depth=0,
        groups=pygame.sprite.LayeredDirty(),
    )
    return mocker.spy(layer, 'update_scroll')


class TestFollow:
    """Camera2D.follow() and the follow axes."""

    def test_defaults_to_no_target_and_both_axes(self):
        camera = make_camera()
        assert camera.follow_target is None
        assert camera.follow_axes is FollowAxes.BOTH

    def test_both_is_x_and_y(self):
        assert FollowAxes.BOTH == FollowAxes.X | FollowAxes.Y

    def test_follow_records_target_and_axes(self):
        camera = make_camera()
        target = make_target()
        camera.follow(target=target, axes=FollowAxes.X)
        assert camera.follow_target is target
        assert camera.follow_axes is FollowAxes.X

    @pytest.mark.parametrize(
        ('attribute_name', 'new_value'),
        [('follow_target', None), ('follow_axes', FollowAxes.Y)],
    )
    def test_follow_target_and_axes_are_read_only(self, attribute_name: str, new_value: object):
        camera = make_camera()
        with pytest.raises(AttributeError):
            setattr(camera, attribute_name, new_value)

    def test_follow_x_keeps_camera_y(self):
        camera = make_camera()
        camera.follow(target=make_target(), axes=FollowAxes.X)
        aim_camera(scene=make_scene(camera=camera), camera=camera, dt=FRAME_SECONDS)
        assert (camera.world_x, camera.world_y) == (TARGET_POSITION[0], CAMERA_START[1])

    def test_follow_y_keeps_camera_x_with_lead_offsets(self):
        camera = make_camera(lead_x=LEAD_OFFSET[0], lead_y=LEAD_OFFSET[1])
        camera.follow(target=make_target(), axes=FollowAxes.Y)
        aim_camera(scene=make_scene(camera=camera), camera=camera, dt=FRAME_SECONDS)
        assert (camera.world_x, camera.world_y) == (
            CAMERA_START[0],
            TARGET_POSITION[1] - LEAD_OFFSET[1],
        )

    def test_follow_both_follows_both_axes(self):
        camera = make_camera(lead_x=LEAD_OFFSET[0], lead_y=LEAD_OFFSET[1])
        camera.follow(target=make_target())
        aim_camera(scene=make_scene(camera=camera), camera=camera, dt=FRAME_SECONDS)
        assert (camera.world_x, camera.world_y) == (
            TARGET_POSITION[0] - LEAD_OFFSET[0],
            TARGET_POSITION[1] - LEAD_OFFSET[1],
        )

    def test_follow_none_stops_following(self):
        camera = make_camera()
        camera.follow(target=make_target())
        camera.follow(target=None)
        scene = make_scene(camera=camera)
        assert scene.camera_target() is None
        aim_camera(scene=scene, camera=camera, dt=FRAME_SECONDS)
        assert (camera.world_x, camera.world_y) == CAMERA_START

    def test_follow_honours_bounds(self):
        camera = make_camera()
        camera.set_bounds(max_x=TARGET_POSITION[0] / 2)
        camera.follow(target=make_target())
        aim_camera(scene=make_scene(camera=camera), camera=camera, dt=FRAME_SECONDS)
        assert camera.world_x == TARGET_POSITION[0] / 2

    @pytest.mark.parametrize(
        ('axes', 'expected_position'),
        [
            (FollowAxes.X, (TARGET_POSITION[0] - LEAD_OFFSET[0], CAMERA_START[1])),
            (FollowAxes.Y, (CAMERA_START[0], TARGET_POSITION[1] - LEAD_OFFSET[1])),
            (
                FollowAxes.BOTH,
                (TARGET_POSITION[0] - LEAD_OFFSET[0], TARGET_POSITION[1] - LEAD_OFFSET[1]),
            ),
        ],
    )
    def test_snap_followed_axes_to_keeps_unfollowed_axes(
        self, axes: FollowAxes, expected_position: tuple[float, float]
    ):
        camera = make_camera(smooth_factor=0.1, lead_x=LEAD_OFFSET[0], lead_y=LEAD_OFFSET[1])
        camera.follow(target=make_target(), axes=axes)
        camera.snap_followed_axes_to(target_x=TARGET_POSITION[0], target_y=TARGET_POSITION[1])
        assert (camera.world_x, camera.world_y) == expected_position


class TestCameraTargetHook:
    """Scene.camera_target(), Scene.PIXEL_SNAP_MODE and hook precedence."""

    def test_pixel_snap_mode_defaults_to_nearest_half_up(self):
        assert Scene.PIXEL_SNAP_MODE is PixelSnapMode.NEAREST_HALF_UP

    def test_default_hook_returns_follow_target_position_as_floats(self):
        camera = make_camera()
        camera.follow(target=FollowedSprite(world_x=12, world_y=-7))
        target = make_scene(camera=camera).camera_target()
        assert target == (12.0, -7.0)
        assert target is not None
        assert all(type(component) is float for component in target)

    def test_default_hook_without_follow_target_is_none(self):
        assert make_scene(camera=make_camera()).camera_target() is None

    def test_follow_names_a_target_without_world_position(self):
        """The error comes from the follow() call, not a frame later from camera_target()."""
        camera = make_camera()
        with pytest.raises(TypeError, match='PositionlessSprite'):
            camera.follow(target=PositionlessSprite())
        assert camera.follow_target is None

    def test_overridden_hook_wins_over_follow_target(self):
        camera = make_camera()
        camera.follow(target=make_target())
        aim_camera(
            scene=make_scene(scene_class=HookScene, camera=camera),
            camera=camera,
            dt=FRAME_SECONDS,
        )
        assert (camera.world_x, camera.world_y) == HOOK_POSITION

    def test_axes_apply_to_hook_supplied_point(self):
        camera = make_camera()
        camera.follow(target=None, axes=FollowAxes.Y)
        aim_camera(
            scene=make_scene(scene_class=HookScene, camera=camera),
            camera=camera,
            dt=FRAME_SECONDS,
        )
        assert (camera.world_x, camera.world_y) == (CAMERA_START[0], HOOK_POSITION[1])


class TestDoubleUpdateWarning:
    """The warning when game code calls camera.update() while the engine aims the camera."""

    @staticmethod
    def double_update_warnings(warning_spy) -> list[object]:
        return [
            call
            for call in warning_spy.call_args_list
            if DOUBLE_UPDATE_WARNING_FRAGMENT in call.args[0]
        ]

    def test_warns_once_per_scene_and_still_aims(self, mocker: MockerFixture):
        warning_spy = mocker.patch.object(world.log, 'warning')
        camera = make_camera()
        camera.follow(target=make_target())
        scene = make_scene(camera=camera)
        for _frame in range(3):
            camera.begin_frame()
            camera.update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
            aim_camera(scene=scene, camera=camera, dt=FRAME_SECONDS)
            assert (camera.world_x, camera.world_y) == TARGET_POSITION
        assert len(self.double_update_warnings(warning_spy)) == 1

    def test_warns_again_for_another_scene(self, mocker: MockerFixture):
        warning_spy = mocker.patch.object(world.log, 'warning')
        camera = make_camera()
        camera.follow(target=make_target())
        for scene in (make_scene(camera=camera), make_scene(camera=camera)):
            camera.begin_frame()
            camera.update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
            aim_camera(scene=scene, camera=camera, dt=FRAME_SECONDS)
        assert len(self.double_update_warnings(warning_spy)) == 2

    def test_never_warns_in_manual_mode(self, mocker: MockerFixture):
        warning_spy = mocker.patch.object(world.log, 'warning')
        camera = make_camera()
        scene = make_scene(camera=camera)
        camera.begin_frame()
        camera.update(target_x=TARGET_POSITION[0], target_y=TARGET_POSITION[1], dt=FRAME_SECONDS)
        aim_camera(scene=scene, camera=camera, dt=FRAME_SECONDS)
        assert (camera.world_x, camera.world_y) == TARGET_POSITION
        assert self.double_update_warnings(warning_spy) == []

    def test_no_warning_when_the_game_did_not_update_this_frame(self, mocker: MockerFixture):
        warning_spy = mocker.patch.object(world.log, 'warning')
        camera = make_camera()
        camera.follow(target=make_target())
        scene = make_scene(camera=camera)
        camera.update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        camera.begin_frame()
        aim_camera(scene=scene, camera=camera, dt=FRAME_SECONDS)
        assert self.double_update_warnings(warning_spy) == []

    def test_update_flag_is_set_by_update_and_cleared_by_begin_frame(self):
        camera = make_camera()
        assert camera._updated_by_game_this_frame is False
        camera.update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        assert camera._updated_by_game_this_frame is True
        camera.begin_frame()
        assert camera._updated_by_game_this_frame is False
        camera._engine_update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        assert camera._updated_by_game_this_frame is False


class TestEngineUpdate:
    """_engine_update() moves the camera, shake and parallax exactly like update()."""

    def test_engine_update_matches_update(self, mocker: MockerFixture):
        game_camera = make_camera(smooth_factor=0.2, lead_x=LEAD_OFFSET[0])
        engine_camera = make_camera(smooth_factor=0.2, lead_x=LEAD_OFFSET[0])
        game_layer_spy = add_recording_layer(camera=game_camera, mocker=mocker)
        engine_layer_spy = add_recording_layer(camera=engine_camera, mocker=mocker)
        game_camera.shake_effect.add(bounce_shake())
        engine_camera.shake_effect.add(bounce_shake())
        for _frame in range(5):
            game_camera.update(
                target_x=TARGET_POSITION[0], target_y=TARGET_POSITION[1], dt=FRAME_SECONDS
            )
            engine_camera._engine_update(
                target_x=TARGET_POSITION[0], target_y=TARGET_POSITION[1], dt=FRAME_SECONDS
            )
            assert (engine_camera.world_x, engine_camera.world_y) == (
                game_camera.world_x,
                game_camera.world_y,
            )
            assert engine_camera.shake_effect.offset == game_camera.shake_effect.offset
        assert engine_layer_spy.call_args_list == game_layer_spy.call_args_list

    def test_engine_update_advances_shake(self):
        camera = make_camera()
        camera.shake_effect.add(bounce_shake())
        camera._engine_update(target_x=0.0, target_y=0.0, dt=SHAKE_SECONDS)
        assert not camera.shake_effect.is_active


class TestAdvanceShake:
    """advance_shake() decays a still camera's WORLD shake; the shake advances once a frame."""

    def test_advance_shake_decays_the_shake_without_moving_the_camera(self):
        camera = make_camera()
        camera.shake_effect.add(bounce_shake())
        camera.advance_shake(dt=SHAKE_SECONDS)
        assert not camera.shake_effect.is_active
        assert (camera.world_x, camera.world_y) == CAMERA_START

    def test_advance_shake_redraws_parallax_only_while_shaking(self, mocker: MockerFixture):
        """The layer follows the shake back to rest, then is left alone (no camera move)."""
        camera = make_camera()
        layer_spy = add_recording_layer(camera=camera, mocker=mocker)
        camera.shake_effect.add(bounce_shake())

        camera.advance_shake(dt=FRAME_SECONDS)
        shake_x, shake_y = camera.shake_effect.offset
        assert (shake_x, shake_y) != (0.0, 0.0)
        layer_spy.assert_called_once_with(
            snap_to_pixel(CAMERA_START[0] + shake_x, PixelSnapMode.NEAREST_HALF_UP),
            snap_to_pixel(CAMERA_START[1] + shake_y, PixelSnapMode.NEAREST_HALF_UP),
        )

        camera.advance_shake(dt=SHAKE_SECONDS)  # the shake ends: the layer returns to rest
        assert layer_spy.call_args == mocker.call(
            snap_to_pixel(CAMERA_START[0], PixelSnapMode.NEAREST_HALF_UP),
            snap_to_pixel(CAMERA_START[1], PixelSnapMode.NEAREST_HALF_UP),
        )
        camera.advance_shake(dt=FRAME_SECONDS)  # no shake: nothing to redraw
        assert layer_spy.call_count == 2

    def test_shake_advanced_flag_is_set_by_every_advance_and_cleared_by_begin_frame(self):
        camera = make_camera()
        assert camera.shake_advanced_this_frame is False
        camera.advance_shake(dt=FRAME_SECONDS)
        assert camera.shake_advanced_this_frame is True
        camera.begin_frame()
        assert camera.shake_advanced_this_frame is False
        camera.update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        assert camera.shake_advanced_this_frame is True
        camera.begin_frame()
        camera.aim_at(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        assert camera.shake_advanced_this_frame is True

    def test_aim_does_not_advance_a_shake_the_game_already_advanced(self, mocker: MockerFixture):
        """A camera.update() in dt_tick and the engine aim in one frame: one shake advance."""
        camera = make_camera()
        camera.shake_effect.add(bounce_shake())
        shake_update_spy = mocker.spy(camera.shake_effect, 'update')
        camera.begin_frame()
        camera.update(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        camera.aim_at(target_x=0.0, target_y=0.0, dt=FRAME_SECONDS)
        assert shake_update_spy.call_count == 1


class TestSnappedParallax:
    """Parallax layers scroll from the snapped camera position (the active snap mode)."""

    @pytest.mark.parametrize(
        ('mode', 'expected_camera_position'),
        [
            (PixelSnapMode.NEAREST_HALF_UP, (11, -3)),
            (PixelSnapMode.FLOOR, (10, -4)),
            (PixelSnapMode.TRUNCATE, (10, -3)),
        ],
    )
    def test_update_scrolls_layers_from_whole_pixels(
        self, mocker: MockerFixture, mode: PixelSnapMode, expected_camera_position
    ):
        set_active_default_snap_mode(mode)
        camera = make_camera()
        layer_spy = add_recording_layer(camera=camera, mocker=mocker)
        camera.update(target_x=FRACTIONAL_CAMERA_X, target_y=FRACTIONAL_CAMERA_Y, dt=FRAME_SECONDS)
        layer_spy.assert_called_once_with(*expected_camera_position)
        assert all(type(value) is int for value in layer_spy.call_args.args)
        # The camera itself keeps its fractional position for logic
        assert (camera.world_x, camera.world_y) == (FRACTIONAL_CAMERA_X, FRACTIONAL_CAMERA_Y)

    def test_snapped_shaken_position_is_snapped_as_a_sum(self, mocker: MockerFixture):
        camera = make_camera()
        layer_spy = add_recording_layer(camera=camera, mocker=mocker)
        camera.shake_effect.add(bounce_shake())
        camera.update(target_x=FRACTIONAL_CAMERA_X, target_y=FRACTIONAL_CAMERA_Y, dt=FRAME_SECONDS)
        shake_x, shake_y = camera.shake_effect.offset
        assert (shake_x, shake_y) != (0.0, 0.0)
        layer_spy.assert_called_once_with(
            snap_to_pixel(FRACTIONAL_CAMERA_X + shake_x, PixelSnapMode.NEAREST_HALF_UP),
            snap_to_pixel(FRACTIONAL_CAMERA_Y + shake_y, PixelSnapMode.NEAREST_HALF_UP),
        )

    def test_snap_to_scrolls_layers_from_whole_pixels(self, mocker: MockerFixture):
        camera = make_camera()
        layer_spy = add_recording_layer(camera=camera, mocker=mocker)
        camera.snap_to(target_x=FRACTIONAL_CAMERA_X, target_y=FRACTIONAL_CAMERA_Y)
        layer_spy.assert_called_once_with(11, -3)
        assert (camera.world_x, camera.world_y) == (FRACTIONAL_CAMERA_X, FRACTIONAL_CAMERA_Y)


class TestSnapToThenAim:
    """Review focus 3: a camera snapped to its target in setup does not move on the first frame."""

    def test_snapped_camera_stays_on_unmoved_target(self):
        camera = make_camera(smooth_factor=0.1, lead_x=LEAD_OFFSET[0], lead_y=LEAD_OFFSET[1])
        target = make_target()
        camera.follow(target=target)
        camera.snap_to(target_x=target.world_x, target_y=target.world_y)
        snapped_position = (camera.world_x, camera.world_y)
        camera.begin_frame()
        aim_camera(scene=make_scene(camera=camera), camera=camera, dt=FRAME_SECONDS)
        assert (camera.world_x, camera.world_y) == snapped_position


WORLD_SHAKE_WARNING_FRAGMENT = 'WORLD shake on'


class TestWorldShakeWarning:
    """Scene.shake warns that a WORLD shake moves nothing only when nothing uses the camera."""

    @staticmethod
    def _shake_world(*, scene: Scene, mocker: MockerFixture) -> None:
        mocker.patch.object(scene.scene_manager, 'active_scene', scene)
        scene.shake(bounce_shake(), targets=ShakeTarget.WORLD)

    @staticmethod
    def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
        return [
            record.getMessage()
            for record in caplog.records
            if WORLD_SHAKE_WARNING_FRAGMENT in record.getMessage()
        ]

    def test_scene_with_world_sprites_does_not_warn(self, mocker, caplog):
        """World sprites are placed from the camera by the engine, never through apply()."""
        scene = make_scene(camera=Camera2D(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT))
        scene.all_sprites.add(make_target())
        with caplog.at_level(logging.WARNING):
            self._shake_world(scene=scene, mocker=mocker)
        assert self._warnings(caplog) == []

    def test_scene_with_parallax_layers_does_not_warn(self, mocker, caplog):
        camera = Camera2D(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        add_recording_layer(camera=camera, mocker=mocker)
        scene = make_scene(camera=camera)
        with caplog.at_level(logging.WARNING):
            self._shake_world(scene=scene, mocker=mocker)
        assert self._warnings(caplog) == []

    def test_scene_whose_camera_was_applied_does_not_warn(self, mocker, caplog):
        camera = Camera2D(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        camera.apply(0.0, 0.0)
        scene = make_scene(camera=camera)
        with caplog.at_level(logging.WARNING):
            self._shake_world(scene=scene, mocker=mocker)
        assert self._warnings(caplog) == []

    def test_scene_where_nothing_uses_the_camera_still_warns_once(self, mocker, caplog):
        scene = make_scene(camera=Camera2D(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT))
        scene.all_sprites.add(PositionlessSprite())
        with caplog.at_level(logging.WARNING):
            self._shake_world(scene=scene, mocker=mocker)
            self._shake_world(scene=scene, mocker=mocker)
        assert len(self._warnings(caplog)) == 1

    def test_camera_reports_its_parallax_layers(self, mocker):
        camera = Camera2D(screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)
        assert camera.has_parallax_layers is False
        add_recording_layer(camera=camera, mocker=mocker)
        assert camera.has_parallax_layers is True
