"""The engine positioning step: world sprites placed on screen from the camera each frame.

Uses a real Camera2D and tiny real sprite classes (no pygame mocking), so the positions,
dirty flags and culling asserted here are the ones the frame loop will produce.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from glitchygames.camera import Camera2D
from glitchygames.collision.detection import snapped_world_position
from glitchygames.display_mode import set_display_mode
from glitchygames.effects.shake import ScreenShake
from glitchygames.engine_context import EngineContext
from glitchygames.game_objects.ball import BallSprite
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

# Every term on an exact half, some negative: world (-0.5, -3.5), camera (-10.5, 1.5),
# shake (2.5, -0.5). Expected screen positions are worked by hand per mode, term by term.
HALF_WORLD_POSITION = (-0.5, -3.5)
HALF_CAMERA_POSITION = (-10.5, 1.5)
HALF_SHAKE_OFFSET = (2.5, -0.5)
EXPECTED_HALF_POSITIONS = {
    # Each tuple lists x then y as the world, camera and shake terms, snapped in that order
    PixelSnapMode.NEAREST_HALF_UP: (0 + 10 - 3, -3 - 2 - 0),
    PixelSnapMode.NEAREST_EVEN: (0 + 10 - 2, -4 - 2 - 0),
    PixelSnapMode.FLOOR: (-1 + 11 - 2, -4 - 1 + 1),
    PixelSnapMode.CEIL: (0 + 10 - 3, -3 - 2 - 0),
    PixelSnapMode.TRUNCATE: (0 + 10 - 2, -3 - 1 - 0),
}


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


class FractionalDrawOffsetSprite(WorldSprite):
    """A world sprite whose draw_offset is not whole pixels."""

    draw_offset = (0, 6.5)


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


@pytest.fixture
def camera() -> Camera2D:
    """A real camera at the world origin.

    Returns:
        Camera2D: The camera.

    """
    return Camera2D(SCREEN_WIDTH, SCREEN_HEIGHT)


def patch_world_shake(mocker: MockerFixture, offset: tuple[float, float]) -> None:
    """Make every camera's WORLD shake report a fixed offset."""
    mocker.patch.object(
        ScreenShake, 'offset', new_callable=mocker.PropertyMock, return_value=offset
    )


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
    patch_world_shake(mocker, TEST_SHAKE_OFFSET)

    assert screen_position_for(sprite=sprite, camera=camera) == (
        unshaken_position[0] - 3,
        unshaken_position[1] + 2,
    )


@pytest.mark.parametrize('mode', list(PixelSnapMode))
def test_every_term_snaps_with_the_sprite_mode(
    camera: Camera2D, mocker: MockerFixture, mode: PixelSnapMode
) -> None:
    """World, camera and shake each snap with the sprite's resolved mode, halves included.

    The active default is set to a mode that differs from the sprite's on every half, so a
    term snapped with the default instead would change the result.
    """
    set_active_default_snap_mode(
        PixelSnapMode.CEIL if mode is PixelSnapMode.FLOOR else PixelSnapMode.FLOOR
    )
    camera.world_x, camera.world_y = HALF_CAMERA_POSITION
    patch_world_shake(mocker, HALF_SHAKE_OFFSET)
    sprite = WorldSprite(world_x=HALF_WORLD_POSITION[0], world_y=HALF_WORLD_POSITION[1])
    sprite.pixel_snap_mode = mode

    assert screen_position_for(sprite=sprite, camera=camera) == EXPECTED_HALF_POSITIONS[mode]


@pytest.mark.parametrize('mode', list(PixelSnapMode))
def test_every_term_snaps_with_the_active_default(
    camera: Camera2D, mocker: MockerFixture, mode: PixelSnapMode
) -> None:
    """A sprite without its own mode snaps every term with the active default."""
    set_active_default_snap_mode(mode)
    camera.world_x, camera.world_y = HALF_CAMERA_POSITION
    patch_world_shake(mocker, HALF_SHAKE_OFFSET)
    sprite = WorldSprite(world_x=HALF_WORLD_POSITION[0], world_y=HALF_WORLD_POSITION[1])

    assert screen_position_for(sprite=sprite, camera=camera) == EXPECTED_HALF_POSITIONS[mode]


@pytest.mark.parametrize(
    ('mode', 'shake_x', 'expected_shift_x'),
    [
        # snap(0.5) is 0 under FLOOR but 1 under NEAREST_HALF_UP; snap(-0.5) is -1 and 0
        (PixelSnapMode.FLOOR, 0.5, 0),
        (PixelSnapMode.FLOOR, -0.5, 1),
        (PixelSnapMode.NEAREST_HALF_UP, 0.5, -1),
        (PixelSnapMode.NEAREST_HALF_UP, -0.5, 0),
    ],
)
def test_half_pixel_shake_snaps_asymmetrically(
    camera: Camera2D,
    mocker: MockerFixture,
    mode: PixelSnapMode,
    shake_x: float,
    expected_shift_x: int,
) -> None:
    """A +/-0.5 shake moves the sprite by one pixel in one direction only (per the spec).

    The shake offset is snapped like any other term, so the shift for +0.5 and -0.5 is not
    mirrored: FLOOR moves only for -0.5, NEAREST_HALF_UP only for +0.5.
    """
    set_active_default_snap_mode(mode)
    sprite = WorldSprite(world_x=50.0, world_y=60.0)
    patch_world_shake(mocker, (shake_x, 0.0))

    assert screen_position_for(sprite=sprite, camera=camera) == (50 + expected_shift_x, 60)


def test_draw_offset_is_added(camera: Camera2D) -> None:
    """draw_offset (0, 6) draws the sprite 6 pixels lower."""
    sprite = OffsetWorldSprite(world_x=50.0, world_y=60.0)

    assert screen_position_for(sprite=sprite, camera=camera) == (50, 66)


def test_fractional_draw_offset_raises_type_error_naming_the_class(camera: Camera2D) -> None:
    """draw_offset must be whole pixels; a float component fails clearly."""
    with pytest.raises(TypeError, match=r'FractionalDrawOffsetSprite draw_offset must be whole'):
        screen_position_for(
            sprite=FractionalDrawOffsetSprite(world_x=0.0, world_y=0.0), camera=camera
        )


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


@pytest.mark.parametrize(
    ('edge', 'world_position'),
    [
        ('left', (-CULL_MARGIN_PIXELS - SPRITE_SIZE, 100)),
        ('right', (SCREEN_WIDTH + CULL_MARGIN_PIXELS, 100)),
        ('top', (100, -CULL_MARGIN_PIXELS - SPRITE_SIZE)),
        ('bottom', (100, SCREEN_HEIGHT + CULL_MARGIN_PIXELS)),
    ],
)
def test_cull_boundary_on_every_edge(
    camera: Camera2D, edge: str, world_position: tuple[int, int]
) -> None:
    """Exactly CULL_MARGIN_PIXELS outside an edge is culled; one pixel nearer is visible."""
    toward_screen = {'left': (1, 0), 'right': (-1, 0), 'top': (0, 1), 'bottom': (0, -1)}[edge]
    sprite = WorldSprite(world_x=world_position[0], world_y=world_position[1])

    position(sprite, camera)

    assert not sprite.visible

    sprite.world_x += toward_screen[0]
    sprite.world_y += toward_screen[1]
    position(sprite, camera)

    assert sprite.visible


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


# --- PaddleSlap's ball: a world sprite under an identity camera ---

BALL_DISPLAY_SIZE = (800, 600)
BALL_HALF_POSITION = (100.5, 60.5)


@pytest.fixture
def ball_display() -> None:
    """Give BallSprite a real display to create its image against."""
    pygame.init()
    if pygame.display.get_surface() is None:
        set_display_mode(size=BALL_DISPLAY_SIZE)


@pytest.mark.usefixtures('ball_display')
class TestBallWorldSpace:
    """The ball lives in world space; the engine, not its setters, writes its rect."""

    def test_ball_declares_world_space(self) -> None:
        """BallSprite is positioned by the engine."""
        assert BallSprite.COORDINATE_SPACE is CoordinateSpace.WORLD
        assert is_world_positioned(BallSprite())

    def test_setting_the_world_position_leaves_rect_alone(self) -> None:
        """world_x/world_y and pixel_snap_mode no longer write rect."""
        ball = BallSprite()
        rect_before = ball.rect.topleft

        ball.world_x = 123.75
        ball.world_y = 45.25
        ball.pixel_snap_mode = PixelSnapMode.FLOOR

        assert ball.rect.topleft == rect_before
        assert (ball.world_x, ball.world_y) == (123.75, 45.25)

    @pytest.mark.parametrize(
        ('ball_mode', 'expected_topleft'),
        [(PixelSnapMode.NEAREST_HALF_UP, (101, 61)), (PixelSnapMode.FLOOR, (100, 60))],
        ids=['nearest-half-up', 'floor'],
    )
    def test_identity_camera_places_the_ball_at_its_snapped_world_position(
        self, ball_mode: PixelSnapMode, expected_topleft: tuple[int, int]
    ) -> None:
        """Under the identity camera, rect is the world position snapped with the ball's mode.

        The scene default is set to a third mode, so only the ball's own mode can give the
        expected positions.
        """
        set_active_default_snap_mode(PixelSnapMode.CEIL)
        identity_camera = Camera2D(*BALL_DISPLAY_SIZE)
        ball = BallSprite(pixel_snap_mode=ball_mode)
        ball.world_x, ball.world_y = BALL_HALF_POSITION

        position_world_sprites(
            sprites=[ball], camera=identity_camera, screen_size=BALL_DISPLAY_SIZE
        )

        assert ball.rect.topleft == expected_topleft
        assert ball.rect.topleft == snapped_world_position(ball, ball.world_x, ball.world_y)
        assert ball.visible

    @pytest.mark.parametrize(
        'ball_mode', [PixelSnapMode.NEAREST_HALF_UP, PixelSnapMode.FLOOR], ids=['half-up', 'floor']
    )
    def test_drawn_center_is_where_positioning_will_draw_the_ball(
        self, ball_mode: PixelSnapMode
    ) -> None:
        """drawn_center() reads the world position, so it is current while rect is stale."""
        identity_camera = Camera2D(*BALL_DISPLAY_SIZE)
        ball = BallSprite(pixel_snap_mode=ball_mode)
        ball.world_x, ball.world_y = BALL_HALF_POSITION
        ball.rect.topleft = (-1000, -1000)  # last frame's place, not yet repositioned

        drawn_center = ball.drawn_center()

        position_world_sprites(
            sprites=[ball], camera=identity_camera, screen_size=BALL_DISPLAY_SIZE
        )
        assert drawn_center == ball.rect.center


def test_each_engine_context_has_its_own_default_snap_mode():
    """The running scene's snap mode in one context never changes another's (audit C1)."""
    second = EngineContext(name='second')
    set_active_default_snap_mode(mode=PixelSnapMode.FLOOR)

    with second.active():
        assert active_default_snap_mode() is PixelSnapMode.NEAREST_HALF_UP
        set_active_default_snap_mode(mode=PixelSnapMode.CEIL)
        assert resolve_snap_mode(sprite=object()) is PixelSnapMode.CEIL

    assert active_default_snap_mode() is PixelSnapMode.FLOOR
    assert resolve_snap_mode(sprite=object()) is PixelSnapMode.FLOOR
