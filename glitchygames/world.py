"""World space: sprites that live in world coordinates and are positioned by the engine."""

from __future__ import annotations

import enum
import logging
import weakref
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

import pygame

from glitchygames.pixel_snap import resolve_snap_mode, snap_to_pixel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from glitchygames.camera import Camera2D

log: logging.Logger = logging.getLogger('game.world')

# Scenes already warned that the game and the engine both moved the camera (warn once each)
_scenes_warned_about_double_update: weakref.WeakSet[object] = weakref.WeakSet()

# Sprites this far outside the screen still count as visible, so they never pop in at the edge
CULL_MARGIN_PIXELS = 32

# pygame DirtySprite.dirty values: redraw once, and redraw every frame
DIRTY_REDRAW_ONCE = 1
DIRTY_ALWAYS_REDRAW = 2


class CoordinateSpace(enum.Enum):
    """Where a sprite's position lives.

    SCREEN: fixed on the screen (HUD, UI). WORLD: moves with the camera.
    """

    SCREEN = 'screen'
    WORLD = 'world'


@runtime_checkable
class WorldPositioned(Protocol):
    """A sprite the engine positions from the camera each frame."""

    COORDINATE_SPACE: CoordinateSpace
    world_x: float
    world_y: float
    rect: pygame.Rect


class _CameraTargetScene(Protocol):
    """The scene attribute the camera aim reads (it writes nothing on the scene)."""

    def camera_target(self) -> tuple[float, float] | None:
        """Return the world point to aim the camera at, or None for a manual camera."""
        ...


class _PositionedSprite(Protocol):
    """The sprite attributes the positioning step writes."""

    rect: pygame.Rect
    dirty: int
    visible: int


def is_world_positioned(sprite: object) -> bool:
    """Report whether the engine positions this sprite (it declared CoordinateSpace.WORLD).

    Args:
        sprite: Any object; sprites without COORDINATE_SPACE are screen space.

    Returns:
        bool: True only when COORDINATE_SPACE is CoordinateSpace.WORLD.

    """
    return getattr(sprite, 'COORDINATE_SPACE', CoordinateSpace.SCREEN) is CoordinateSpace.WORLD


def screen_position_for(*, sprite: object, camera: Camera2D) -> tuple[int, int]:
    """Screen top-left for a world sprite: snap(world) - snap(camera) - shake, plus draw_offset.

    Sprite and camera are snapped separately with the sprite's snap mode, so sprites that move
    with the camera keep a constant on-screen spacing instead of shimmering by a pixel.
    The shake offset is snapped with the same mode, so a +/-0.5 shake is not mirrored (FLOOR
    moves only for -0.5, NEAREST_HALF_UP only for +0.5), as the spec specifies.

    Args:
        sprite: A sprite declaring CoordinateSpace.WORLD.
        camera: The camera whose position and WORLD shake place the sprite.

    Returns:
        tuple[int, int]: The whole-pixel screen top-left.

    Raises:
        TypeError: If the sprite declares world space but lacks world_x or world_y, or its
            draw_offset is not whole pixels.

    """
    world_x = getattr(sprite, 'world_x', None)
    world_y = getattr(sprite, 'world_y', None)
    if world_x is None or world_y is None:
        message = (
            f'{type(sprite).__name__} declares CoordinateSpace.WORLD but has no world_x/world_y'
        )
        raise TypeError(message)

    mode = resolve_snap_mode(sprite)
    # The WORLD shake offset is read, never advanced: Camera2D.update() advances it
    shake_x, shake_y = camera.shake_effect.offset
    draw_offset_x, draw_offset_y = getattr(sprite, 'draw_offset', (0, 0))
    if not all(
        isinstance(component, int) and not isinstance(component, bool)
        for component in (draw_offset_x, draw_offset_y)
    ):
        message = (
            f'{type(sprite).__name__} draw_offset must be whole pixels (ints), '
            f'got {(draw_offset_x, draw_offset_y)!r}'
        )
        raise TypeError(message)
    screen_x = (
        snap_to_pixel(world_x, mode)
        - snap_to_pixel(camera.world_x, mode)
        - snap_to_pixel(shake_x, mode)
        + draw_offset_x
    )
    screen_y = (
        snap_to_pixel(world_y, mode)
        - snap_to_pixel(camera.world_y, mode)
        - snap_to_pixel(shake_y, mode)
        + draw_offset_y
    )
    return (screen_x, screen_y)


def position_world_sprites(
    *, sprites: Iterable[object], camera: Camera2D, screen_size: tuple[int, int]
) -> None:
    """Place every world sprite on screen from the camera and cull it.

    Writes only rect.topleft, dirty (set to 1 when the sprite moved, unless it is 2) and
    visible (on screen within CULL_MARGIN_PIXELS and not hidden). visible is written only when
    it changes, because DirtySprite's visible setter also marks the sprite dirty. Screen-space
    sprites are skipped entirely.

    Args:
        sprites: The sprites to consider (normally the scene's all_sprites).
        camera: The camera to position world sprites from.
        screen_size: The screen (width, height) used for culling.

    """
    cull_rect = pygame.Rect((0, 0), screen_size).inflate(
        2 * CULL_MARGIN_PIXELS, 2 * CULL_MARGIN_PIXELS
    )
    for sprite in sprites:
        if not is_world_positioned(sprite):
            continue
        new_topleft = screen_position_for(sprite=sprite, camera=camera)
        positioned_sprite = cast('_PositionedSprite', sprite)
        if positioned_sprite.rect.topleft != new_topleft:
            positioned_sprite.rect.topleft = new_topleft
            # dirty == 2 sprites already redraw every frame; keep their mode
            if positioned_sprite.dirty != DIRTY_ALWAYS_REDRAW:
                positioned_sprite.dirty = DIRTY_REDRAW_ONCE
        is_visible = positioned_sprite.rect.colliderect(cull_rect) and not getattr(
            sprite, 'hidden', False
        )
        # DirtySprite's visible setter marks the sprite dirty, so write only on a change
        if bool(positioned_sprite.visible) != is_visible:
            positioned_sprite.visible = int(is_visible)


def aim_camera(*, scene: object, camera: Camera2D, dt: float) -> None:
    """Move the camera toward the scene's camera target (the engine's camera aim step).

    The target comes from scene.camera_target() (an override, else the camera's follow target).
    None means a manual camera: it is left alone. An axis the camera does not follow keeps the
    camera's current goal on that axis (Camera2D.aim_at). If game code also called
    camera.update() this frame, a warning is logged once per scene and the camera is still
    aimed.

    The double-update warning is tracked per scene, but the manual-update flag it reads
    (Camera2D.updated_by_game_this_frame) is per camera: the scene manager must call
    camera.begin_frame() exactly once per frame, before scene logic, or the flag carries over
    from an earlier frame.

    Args:
        scene: The active scene (a glitchygames Scene).
        camera: The scene's camera.
        dt: Delta time in seconds since the last frame.

    """
    target = cast('_CameraTargetScene', scene).camera_target()
    if target is None:
        return
    if camera.updated_by_game_this_frame and scene not in _scenes_warned_about_double_update:
        log.warning(
            'camera.update() called by the game while the engine is also aiming the camera; '
            'remove the manual call or stop following (scene %s)',
            getattr(scene, 'NAME', type(scene).__name__),
        )
        _scenes_warned_about_double_update.add(scene)
    target_x, target_y = target
    camera.aim_at(target_x=target_x, target_y=target_y, dt=dt)
