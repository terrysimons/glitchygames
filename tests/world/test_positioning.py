"""The engine positioning step: world sprites placed on screen from the camera each frame.

Uses a real Camera2D and tiny real sprite classes (no pygame mocking), so the positions,
dirty flags and culling asserted here are the ones the frame loop will produce.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames import pixel_snap
from glitchygames.camera import Camera2D
from glitchygames.effects.shake import ScreenShake
from glitchygames.pixel_snap import (
    PixelSnapMode,
    active_default_snap_mode,
    resolve_snap_mode,
    set_active_default_snap_mode,
)
from glitchygames.world import (
    CULL_MARGIN_PIXELS,
    CoordinateSpace,
    WorldPositioned,
    is_world_positioned,
    position_world_sprites,
    screen_position_for,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytest_mock import MockerFixture

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
SPRITE_SIZE = 16

# Snapping scenario: camera and sprite at fractional positions moving together
CAMERA_START_X = 10.5
SPRITE_START_X = 100.5
SECOND_SPRITE_START_X = 140.5
SCROLL_STEP_PIXELS = 0.25
SCROLL_STEPS = 8

TEST_SHAKE_OFFSET = (3.0, -2.0)
TEST_DRAW_OFFSET = (0, 6)


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
        self.dirty = 0


class FloorSnappedWorldSprite(WorldSprite):
    """A world sprite overriding the scene snap mode with FLOOR."""

    pixel_snap_mode = PixelSnapMode.FLOOR


class OffsetWorldSprite(WorldSprite):
    """A world sprite drawn a few pixels below its world position."""

    draw_offset = TEST_DRAW_OFFSET


class MissingWorldYSprite(pygame.sprite.DirtySprite):
    """Declares world space but forgot world_y."""

    COORDINATE_SPACE = CoordinateSpace.WORLD

    def __init__(self) -> None:
        """Create the sprite with only world_x."""
        super().__init__()
        self.world_x = 0.0
        self.image = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
        self.rect = self.image.get_rect()


class UndeclaredSprite(pygame.sprite.DirtySprite):
    """A HUD-style sprite with no coordinate space declared (defaults to screen)."""

    def __init__(self) -> None:
        """Create the sprite at a fixed screen position."""
        super().__init__()
        self.world_x = 500.0
        self.world_y = 500.0
        self.image = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
        self.rect = pygame.Rect(7, 9, SPRITE_SIZE, SPRITE_SIZE)
        # visible first: DirtySprite's visible setter sets dirty = 1
        self.visible = 1
        self.dirty = 0


class ScreenSprite(UndeclaredSprite):
    """A sprite that explicitly declares screen space."""

    COORDINATE_SPACE = CoordinateSpace.SCREEN


@pytest.fixture(autouse=True)
def restore_default_snap_mode() -> Generator[None]:
    """Put the module-level default snap mode back after each test.

    Yields:
        None: Control to the test.

    """
    original_mode = pixel_snap.active_default_snap_mode()
    yield
    pixel_snap.set_active_default_snap_mode(original_mode)


@pytest.fixture
def camera() -> Camera2D:
    """A real camera at the world origin.

    Returns:
        Camera2D: The camera.

    """
    return Camera2D(SCREEN_WIDTH, SCREEN_HEIGHT)


def position(sprite: object, camera: Camera2D) -> None:
    """Run the positioning step over one sprite."""
    position_world_sprites(sprites=[sprite], camera=camera, screen_size=SCREEN_SIZE)


# --- Snap mode resolution ---


def test_active_default_snap_mode_starts_as_nearest_half_up() -> None:
    """The engine default matches Scene.PIXEL_SNAP_MODE's default."""
    assert active_default_snap_mode() is PixelSnapMode.NEAREST_HALF_UP


def test_resolve_snap_mode_prefers_the_sprite_mode() -> None:
    """A sprite's own PixelSnapMode wins; anything else falls back to the active default."""
    floor_sprite = FloorSnappedWorldSprite(world_x=0.0, world_y=0.0)
    plain_sprite = WorldSprite(world_x=0.0, world_y=0.0)
    plain_sprite.pixel_snap_mode = 'floor'  # Not a PixelSnapMode: ignored

    assert resolve_snap_mode(floor_sprite) is PixelSnapMode.FLOOR
    assert resolve_snap_mode(plain_sprite) is PixelSnapMode.NEAREST_HALF_UP

    set_active_default_snap_mode(PixelSnapMode.CEIL)

    assert resolve_snap_mode(plain_sprite) is PixelSnapMode.CEIL
    assert resolve_snap_mode(floor_sprite) is PixelSnapMode.FLOOR


# --- Declaration ---


def test_is_world_positioned_only_for_world_declarations() -> None:
    """Only CoordinateSpace.WORLD opts a sprite in; undeclared and SCREEN stay out."""
    assert is_world_positioned(WorldSprite(world_x=0.0, world_y=0.0))
    assert not is_world_positioned(UndeclaredSprite())
    assert not is_world_positioned(ScreenSprite())


def test_world_sprite_satisfies_the_world_positioned_protocol() -> None:
    """The runtime-checkable protocol recognizes a complete world sprite."""
    assert isinstance(WorldSprite(world_x=0.0, world_y=0.0), WorldPositioned)
    assert not isinstance(MissingWorldYSprite(), WorldPositioned)


# --- Snapping ---


def test_sprite_and_camera_snap_separately(camera: Camera2D) -> None:
    """Screen x = snap(world) - snap(camera): 101 - 11 = 90 with NEAREST_HALF_UP."""
    camera.world_x = CAMERA_START_X
    sprite = WorldSprite(world_x=SPRITE_START_X, world_y=0.0)

    assert screen_position_for(sprite=sprite, camera=camera) == (90, 0)


def test_moving_camera_and_sprites_together_does_not_shimmer(camera: Camera2D) -> None:
    """Sprites scrolling with the camera keep a constant on-screen spacing at every step."""
    camera.world_x = CAMERA_START_X
    first_sprite = WorldSprite(world_x=SPRITE_START_X, world_y=0.0)
    second_sprite = WorldSprite(world_x=SECOND_SPRITE_START_X, world_y=0.0)
    position_world_sprites(
        sprites=[first_sprite, second_sprite], camera=camera, screen_size=SCREEN_SIZE
    )
    initial_spacing = second_sprite.rect.x - first_sprite.rect.x

    for _ in range(SCROLL_STEPS):
        camera.world_x += SCROLL_STEP_PIXELS
        first_sprite.world_x += SCROLL_STEP_PIXELS
        second_sprite.world_x += SCROLL_STEP_PIXELS
        position_world_sprites(
            sprites=[first_sprite, second_sprite], camera=camera, screen_size=SCREEN_SIZE
        )
        assert first_sprite.rect.x == 90
        assert second_sprite.rect.x - first_sprite.rect.x == initial_spacing


def test_sprite_pixel_snap_mode_overrides_the_default(camera: Camera2D) -> None:
    """A FLOOR sprite floors; a plain sprite uses the active default, which can change."""
    camera.world_x = CAMERA_START_X
    floor_sprite = FloorSnappedWorldSprite(world_x=SPRITE_START_X, world_y=0.0)
    plain_sprite = WorldSprite(world_x=SPRITE_START_X, world_y=0.0)

    assert screen_position_for(sprite=floor_sprite, camera=camera) == (100 - 10, 0)
    assert screen_position_for(sprite=plain_sprite, camera=camera) == (101 - 11, 0)

    set_active_default_snap_mode(PixelSnapMode.FLOOR)

    assert screen_position_for(sprite=plain_sprite, camera=camera) == (100 - 10, 0)


def test_world_shake_offset_shifts_the_screen_position(
    camera: Camera2D, mocker: MockerFixture
) -> None:
    """A WORLD shake offset of (3, -2) moves the sprite by (-3, +2)."""
    sprite = WorldSprite(world_x=50.0, world_y=60.0)
    unshaken_position = screen_position_for(sprite=sprite, camera=camera)
    mocker.patch.object(
        ScreenShake,
        'offset',
        new_callable=mocker.PropertyMock,
        return_value=TEST_SHAKE_OFFSET,
    )

    assert screen_position_for(sprite=sprite, camera=camera) == (
        unshaken_position[0] - 3,
        unshaken_position[1] + 2,
    )


def test_draw_offset_is_added(camera: Camera2D) -> None:
    """draw_offset (0, 6) draws the sprite 6 pixels lower."""
    sprite = OffsetWorldSprite(world_x=50.0, world_y=60.0)

    assert screen_position_for(sprite=sprite, camera=camera) == (50, 66)


def test_integer_world_positions_work(camera: Camera2D) -> None:
    """Integer world_x/world_y are snapped like floats."""
    camera.world_x = 5
    sprite = WorldSprite(world_x=40, world_y=30)

    position(sprite, camera)

    assert sprite.rect.topleft == (35, 30)


def test_missing_world_y_raises_type_error_naming_the_class(camera: Camera2D) -> None:
    """A WORLD sprite without world_y fails clearly at positioning time."""
    with pytest.raises(TypeError, match=r'MissingWorldYSprite declares CoordinateSpace\.WORLD'):
        position(MissingWorldYSprite(), camera)


# --- Dirty handling ---


def test_dirty_set_only_when_the_position_changes(camera: Camera2D) -> None:
    """Moving marks the sprite dirty; an unchanged position leaves dirty alone."""
    sprite = WorldSprite(world_x=20.0, world_y=30.0)

    position(sprite, camera)

    assert sprite.rect.topleft == (20, 30)
    assert sprite.dirty == 1

    sprite.dirty = 0
    position(sprite, camera)

    assert sprite.dirty == 0
    assert sprite.visible


def test_dirty_two_sprite_stays_two(camera: Camera2D) -> None:
    """A sprite in always-redraw mode keeps dirty == 2 whether or not it moves."""
    sprite = WorldSprite(world_x=20.0, world_y=30.0)
    sprite.rect.topleft = (20, 30)
    sprite.dirty = 2

    position(sprite, camera)

    assert sprite.dirty == 2

    sprite.world_x = 25.0
    position(sprite, camera)

    assert sprite.rect.topleft == (25, 30)
    assert sprite.dirty == 2


# --- Culling ---


def test_on_screen_sprite_is_visible(camera: Camera2D) -> None:
    """A sprite inside the screen is visible."""
    sprite = WorldSprite(world_x=100.0, world_y=100.0)
    sprite.visible = 0

    position(sprite, camera)

    assert sprite.visible


def test_sprite_within_the_cull_margin_is_visible(camera: Camera2D) -> None:
    """31 px past the right edge is inside the 32 px margin."""
    sprite = WorldSprite(world_x=SCREEN_WIDTH + CULL_MARGIN_PIXELS - 1, world_y=100.0)

    position(sprite, camera)

    assert sprite.visible


def test_sprite_beyond_the_cull_margin_is_not_visible(camera: Camera2D) -> None:
    """40 px past the right edge is culled."""
    sprite = WorldSprite(world_x=SCREEN_WIDTH + 40, world_y=100.0)

    position(sprite, camera)

    assert not sprite.visible


def test_hidden_sprite_is_invisible_and_returns_when_unhidden(camera: Camera2D) -> None:
    """Setting hidden hides an on-screen sprite; clearing it shows the sprite again."""
    sprite = WorldSprite(world_x=100.0, world_y=100.0)
    sprite.hidden = True

    position(sprite, camera)

    assert not sprite.visible

    sprite.hidden = False
    position(sprite, camera)

    assert sprite.visible


def test_hidden_sprite_scrolling_on_screen_stays_invisible(camera: Camera2D) -> None:
    """A hidden sprite that comes into view through scrolling is still not shown."""
    sprite = WorldSprite(world_x=SCREEN_WIDTH + 200.0, world_y=100.0)
    sprite.hidden = True

    position(sprite, camera)

    assert not sprite.visible

    camera.world_x = 200.0
    position(sprite, camera)

    assert sprite.rect.x == SCREEN_WIDTH
    assert not sprite.visible


# --- Untouched state ---


@pytest.mark.parametrize('sprite_class', [UndeclaredSprite, ScreenSprite])
def test_screen_space_sprites_are_untouched(
    camera: Camera2D, sprite_class: type[UndeclaredSprite]
) -> None:
    """Undeclared and SCREEN sprites keep their rect, visible and dirty."""
    sprite = sprite_class()
    camera.world_x = 123.0

    position(sprite, camera)

    assert sprite.rect.topleft == (7, 9)
    assert sprite.visible == 1
    assert sprite.dirty == 0


def test_step_never_changes_world_position_camera_or_image(camera: Camera2D) -> None:
    """The step writes only rect, dirty and visible."""
    camera.world_x = CAMERA_START_X
    camera.world_y = 4.25
    sprite = WorldSprite(world_x=SPRITE_START_X, world_y=60.75)
    original_image = sprite.image

    position(sprite, camera)

    assert sprite.world_x == SPRITE_START_X
    assert sprite.world_y == 60.75
    assert (camera.world_x, camera.world_y) == (CAMERA_START_X, 4.25)
    assert sprite.image is original_image
