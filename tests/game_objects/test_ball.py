"""Tests for BallSprite game object."""

import math
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

import glitchygames.game_objects.ball as ball_module
from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.game_objects.ball import (
    BallSprite,
    PixelSnapMode,
    ServeHorizontalDirection,
    ServeSettings,
    ServeVerticalDirection,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
    snap_to_pixel,
)
from glitchygames.game_objects.paddle import VerticalPaddle
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
SIZE_20 = 20
SIZE_30 = 30
DIRECTION_360 = 360
SPEED_2 = 2
SPEED_1 = 1
SPEED_NEG_2 = -2
Y_580 = 580
POS_102 = 102
POS_103 = 103
DIRECTION_315 = 315
MULTIPLIER_1_1 = 1.1


def _assert_within_spawn_area(ball: BallSprite) -> None:
    """Assert the ball's visible rect lies within ServeSettings.spawn_margin of every edge."""
    margin = ball.serve_settings.spawn_margin
    visible_rect = get_sprite_collision_rect(ball)
    assert margin <= visible_rect.left <= visible_rect.right <= ball.screen_width - margin
    assert margin <= visible_rect.top <= visible_rect.bottom <= ball.screen_height - margin


class TestBallSpriteInitialization:
    """Test BallSprite initialization and basic properties."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_sprite_initialization_defaults(self):
        """Test BallSprite initialization with default parameters."""
        ball = BallSprite()

        assert ball.width == SIZE_20
        assert ball.height == SIZE_20
        # Position is set by reset() during initialization, so it will be random
        assert ball.rect is not None
        _assert_within_spawn_area(ball)
        assert ball.use_gfxdraw is True
        # Direction is set by reset() during initialization, so it will be random
        assert 0 <= ball.direction <= DIRECTION_360  # Reset sets random direction
        assert isinstance(ball.speed, Speed)
        # reset() serves at the default ServeSettings speed in a random direction
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(ServeSettings().speed)
        assert ball.dirty == SPEED_2

    def test_ball_sprite_initialization_custom(self, mocker):
        """Test BallSprite initialization with custom parameters."""
        groups = mocker.Mock()
        mocker.patch('pygame.mixer.Sound')
        ball = BallSprite(
            x=100,
            y=200,
            width=30,
            height=30,
            groups=groups,
            collision_sound='test.wav',
        )

        # Position is set by reset() during initialization, so it will be random
        assert ball.rect is not None
        _assert_within_spawn_area(ball)
        assert ball.width == SIZE_30
        assert ball.height == SIZE_30
        # groups() returns a list, so we need to check the content
        assert groups in ball.groups()

    def test_ball_sprite_initialization_without_groups(self):
        """Test BallSprite initialization creates default groups when None provided."""
        ball = BallSprite()

        # Should create a LayeredDirty group
        assert ball.groups() is not None

    def test_ball_sprite_initialization_with_collision_sound(self, mocker):
        """Test BallSprite initialization with collision sound."""
        mock_sound = mocker.Mock()
        mock_sound_class = mocker.patch(
            'glitchygames.game_objects.sounds.pygame.mixer.Sound',
            return_value=mock_sound,
        )

        ball = BallSprite(collision_sound='bounce.wav')

        mock_sound_class.assert_called_once()
        assert hasattr(ball, 'snd')
        assert ball.snd == mock_sound

    def test_ball_sprite_initialization_without_collision_sound(self):
        """Test BallSprite initialization without collision sound."""
        ball = BallSprite()

        # Should not have snd attribute when no collision sound provided
        assert not hasattr(ball, 'snd')


class TestBallSpriteColor:
    """Test BallSprite color property and setter."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_color_getter(self):
        """Test ball color getter returns correct color."""
        ball = BallSprite()
        ball._color = (255, 0, 0)

        assert ball.color == (255, 0, 0)

    def test_ball_color_setter(self, mocker):
        """Test ball color setter updates color and redraws."""
        mock_draw_circle = mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        ball.width = 20
        ball.height = 20

        ball.color = (0, 255, 0)

        assert ball._color == (0, 255, 0)
        # draw.circle is called twice - once during initialization and once in setter
        assert mock_draw_circle.call_count == SPEED_2
        # Check the last call (the setter call)
        assert ball.image is not None
        mock_draw_circle.assert_any_call(ball.image, (0, 255, 0), (10, 10), 5, 0)


class TestBallSpriteBounce:
    """Test BallSprite bounce functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_do_bounce_top_wall(self, mocker):
        """Test ball bounces off top wall."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.y = -5  # Above screen
        ball.world_y = -5.0  # Sub-pixel position must also be set
        ball.speed.y = -2
        ball.snd = mocker.Mock()

        ball._do_bounce()

        # Ball reflects off top boundary preserving overshoot: world_y = -(-5) = 5
        assert ball.world_y >= 0  # Ball is inside boundary
        assert ball.rect.y == round(ball.world_y)
        assert ball.speed.y == SPEED_2  # Reversed
        ball.snd.play.assert_called_once()

    def test_do_bounce_bottom_wall(self, mocker):
        """Test ball bounces off bottom wall."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        ball.screen_height = 600
        ball.height = 20
        assert ball.rect is not None
        ball.rect.y = 590  # Below screen (590 + 20 = 610 >= 600)
        ball.world_y = 590.0  # Sub-pixel position must also be set
        ball.speed.y = 2
        ball.snd = mocker.Mock()

        ball._do_bounce()

        # Ball reflects off bottom boundary preserving overshoot
        boundary = float(ball.screen_height - ball.height)  # 580.0
        assert ball.world_y <= boundary  # Ball is inside boundary
        assert ball.rect.y == round(ball.world_y)
        assert ball.speed.y == SPEED_NEG_2  # Reversed
        ball.snd.play.assert_called_once()

    def test_do_bounce_no_sound(self, mocker):
        """Test ball bounces without sound when no sound loaded."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.y = -5
        ball.world_y = -5.0  # Sub-pixel position must also be set
        ball.speed.y = -2
        # No snd attribute set

        ball._do_bounce()

        # Ball reflects off top boundary preserving overshoot
        assert ball.world_y >= 0  # Ball is inside boundary
        assert ball.rect.y == round(ball.world_y)
        assert ball.speed.y == SPEED_2

    def test_do_bounce_no_collision(self, mocker):
        """Test ball doesn't bounce when not at walls."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.y = 100
        ball.speed.y = 2
        original_speed = ball.speed.y

        ball._do_bounce()

        # Speed should remain unchanged
        assert ball.speed.y == original_speed


class TestBallSpriteReset:
    """Test BallSprite reset functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_reset_position(self, mocker):
        """Test ball reset places the ball at the random position it draws, inside the margin."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        randint = mocker.patch.object(ball_module._SERVE_RANDOM, 'randint', side_effect=[173, 70])

        ball.reset()

        assert ball.rect is not None
        assert (ball.rect.x, ball.rect.y) == (173, 70)
        margin = ball.serve_settings.spawn_margin
        assert randint.call_args_list == [
            mocker.call(margin, ball.screen_width - ball.width - margin),
            mocker.call(margin, ball.screen_height - ball.height - margin),
        ]

    def test_ball_reset_direction(self, mocker):
        """Test ball.direction reports the served heading (0 = right, 90 = down)."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite(
            serve_settings=ServeSettings(
                horizontal=ServeHorizontalDirection.LEFT,
                vertical=ServeVerticalDirection.UP,
            ),
        )
        mocker.patch.object(ball_module._SERVE_RANDOM, 'uniform', return_value=30.0)

        ball.reset()

        assert ball.direction == pytest.approx(210.0)  # left and 30 degrees up

    def test_ball_reset_direction_range(self, mocker):
        """Test ball reset direction is within expected range."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()

        # Test multiple resets to ensure direction is in valid range
        for _ in range(10):
            ball.reset()
            assert 0 <= ball.direction <= DIRECTION_360

    def test_reset_restores_serve_after_speed_changes(self):
        """reset() always serves at the configured speed, whatever the ball was doing."""
        ball = BallSprite(serve_settings=ServeSettings(speed=180.0))
        ball.speed = Speed(999.0, -5.0)
        ball.reset()
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(180.0)


# ---------------------------------------------------------------------------
# Serve settings: every combination of settings and random outcomes.
# ---------------------------------------------------------------------------

SERVE_ANGLE_BAND = (15.0, 60.0)
SERVE_SPEED = 250.0
HORIZONTAL_COIN_OUTCOMES = (ServeHorizontalDirection.LEFT, ServeHorizontalDirection.RIGHT)
VERTICAL_COIN_OUTCOMES = (ServeVerticalDirection.UP, ServeVerticalDirection.DOWN)


class ServeCase(NamedTuple):
    """One combination of serve settings and pinned random outcomes."""

    horizontal: ServeHorizontalDirection
    vertical: ServeVerticalDirection
    angle: float
    horizontal_coin: ServeHorizontalDirection
    vertical_coin: ServeVerticalDirection
    serve_toward: ServeHorizontalDirection | None


def _serve_outcome_cases():
    """Every direction setting x band-edge/middle angle x coin outcome x override.

    Returns:
        list: pytest params of ServeCase.

    """
    angles = (SERVE_ANGLE_BAND[0], sum(SERVE_ANGLE_BAND) / 2, SERVE_ANGLE_BAND[1])
    return [
        pytest.param(
            ServeCase(horizontal, vertical, angle, horizontal_coin, vertical_coin, serve_toward),
            id=(
                f'{horizontal.name}-{vertical.name}-{angle}deg-coins'
                f'{horizontal_coin.name}{vertical_coin.name}-toward'
                f'{serve_toward.name if serve_toward else "None"}'
            ),
        )
        for horizontal in ServeHorizontalDirection
        for vertical in ServeVerticalDirection
        for angle in angles
        for horizontal_coin in HORIZONTAL_COIN_OUTCOMES
        for vertical_coin in VERTICAL_COIN_OUTCOMES
        for serve_toward in (None, ServeHorizontalDirection.LEFT, ServeHorizontalDirection.RIGHT)
    ]


@pytest.mark.usefixtures('pygame_mocks')
class TestServeSettings:
    """ServeSettings controls serve speed, angle band, directions, and spawn area."""

    @pytest.fixture
    def pygame_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_defaults_are_pong_style(self):
        """Default serves: 15-60 degrees from horizontal, any diagonal, 250 px/s."""
        settings = ServeSettings()
        assert (settings.minimum_angle_degrees, settings.maximum_angle_degrees) == (15.0, 60.0)
        assert settings.horizontal is ServeHorizontalDirection.EITHER
        assert settings.vertical is ServeVerticalDirection.EITHER
        assert settings.speed == SERVE_SPEED
        assert settings.spawn_margin == 50

    @pytest.mark.parametrize('serve_case', _serve_outcome_cases())
    def test_every_serve_outcome(self, mocker, serve_case):
        """The serve has the configured speed and drawn angle, toward the right sides.

        serve_toward overrides the horizontal setting; EITHER uses the coin flip.
        """
        (horizontal, vertical, angle, horizontal_coin, vertical_coin, serve_toward) = serve_case
        ball = BallSprite(
            serve_settings=ServeSettings(
                minimum_angle_degrees=SERVE_ANGLE_BAND[0],
                maximum_angle_degrees=SERVE_ANGLE_BAND[1],
                horizontal=horizontal,
                vertical=vertical,
                speed=SERVE_SPEED,
            ),
        )
        mocker.patch.object(ball_module._SERVE_RANDOM, 'uniform', return_value=angle)
        mocker.patch.object(
            ball_module._SERVE_RANDOM,
            'choice',
            side_effect=lambda options: (
                horizontal_coin if options[0] in HORIZONTAL_COIN_OUTCOMES else vertical_coin
            ),
        )

        ball.serve(serve_toward=serve_toward)

        expected_horizontal = serve_toward or (
            horizontal_coin if horizontal is ServeHorizontalDirection.EITHER else horizontal
        )
        expected_vertical = vertical_coin if vertical is ServeVerticalDirection.EITHER else vertical
        description = f'{horizontal.name}/{vertical.name} {angle} toward {serve_toward}'
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(SERVE_SPEED), description
        assert math.degrees(math.atan2(abs(ball.speed.y), abs(ball.speed.x))) == pytest.approx(
            angle
        ), description
        if expected_horizontal is ServeHorizontalDirection.RIGHT:
            assert ball.speed.x > 0, description
        else:
            assert ball.speed.x < 0, description
        if expected_vertical is ServeVerticalDirection.DOWN:
            assert ball.speed.y > 0, description
        else:
            assert ball.speed.y < 0, description
        assert ball.direction == pytest.approx(
            math.degrees(math.atan2(ball.speed.y, ball.speed.x)) % 360
        ), description

    def test_default_serves_reach_all_four_diagonals_within_the_band(self):
        """With real randomness, serves stay in the band and cover every diagonal."""
        ball = BallSprite()
        quadrants = set()
        for _ in range(400):
            ball.serve()
            angle = math.degrees(math.atan2(abs(ball.speed.y), abs(ball.speed.x)))
            assert SERVE_ANGLE_BAND[0] - 1e-9 <= angle <= SERVE_ANGLE_BAND[1] + 1e-9
            quadrants.add((ball.speed.x > 0, ball.speed.y > 0))
        assert len(quadrants) == 4

    @pytest.mark.parametrize('angle', [0.0, 90.0])
    def test_horizontal_and_vertical_extremes(self, mocker, angle):
        """A 0-degree serve is purely horizontal; a 90-degree serve purely vertical."""
        ball = BallSprite(
            serve_settings=ServeSettings(
                minimum_angle_degrees=angle,
                maximum_angle_degrees=angle,
                horizontal=ServeHorizontalDirection.RIGHT,
                vertical=ServeVerticalDirection.DOWN,
            ),
        )
        mocker.patch.object(ball_module._SERVE_RANDOM, 'uniform', return_value=angle)
        ball.serve()
        expected = (250.0, 0.0) if angle == 0.0 else (0.0, 250.0)
        assert (ball.speed.x, ball.speed.y) == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize(
        ('screen_width', 'screen_height'), [(320, 240), (800, 600), (1920, 1080), (121, 121)]
    )
    @pytest.mark.parametrize('pick', ['lowest', 'highest'])
    def test_spawn_position_fits_any_screen(self, mocker, screen_width, screen_height, pick):
        """The serve position is within the margin of the actual screen at any size."""
        ball = BallSprite()
        ball.screen_width = screen_width
        ball.screen_height = screen_height
        mocker.patch.object(
            ball_module._SERVE_RANDOM,
            'randint',
            side_effect=lambda low, high: low if pick == 'lowest' else high,
        )
        ball.reset()
        _assert_within_spawn_area(ball)

    @pytest.mark.parametrize(('screen_width', 'screen_height'), [(100, 100), (20, 20), (10, 10)])
    def test_spawn_position_on_screens_too_small_for_the_margin(self, screen_width, screen_height):
        """Without room for the margin, the visible ball is centered (clamped to the screen)."""
        ball = BallSprite()
        ball.screen_width = screen_width
        ball.screen_height = screen_height
        ball.reset()
        visible_rect = get_sprite_collision_rect(ball)
        expected_left = max((screen_width - visible_rect.width) // 2, 0)
        expected_top = max((screen_height - visible_rect.height) // 2, 0)
        assert visible_rect.topleft == (expected_left, expected_top)

    @pytest.mark.parametrize(
        ('field', 'value'),
        [
            ('minimum_angle_degrees', -1.0),
            ('maximum_angle_degrees', 90.5),
            ('minimum_angle_degrees', math.nan),
            ('speed', 0.0),
            ('speed', -10.0),
            ('speed', math.inf),
            ('spawn_margin', -1),
        ],
    )
    def test_rejects_invalid_settings(self, field, value):
        """Out-of-range serve settings raise ValueError naming the field."""
        with pytest.raises(ValueError, match=field.split('_')[0]):
            ServeSettings(**{field: value})

    def test_rejects_minimum_angle_above_maximum(self):
        """The angle band must not be inverted."""
        with pytest.raises(ValueError, match='angle'):
            ServeSettings(minimum_angle_degrees=60.0, maximum_angle_degrees=15.0)


WALL_BOUNCE_SWEEP_ANGLES_DEGREES = tuple(range(0, 360, 15))
WALL_BOUNCE_SWEEP_SPEEDS = (60.0, 250.0, 450.0)
# How far past a wall the ball starts (negative: just inside, but its rounded rect
# already touches the wall)
WALL_OVERSHOOTS = (2.0, 0.0, -0.3)
WALL_BOUNCE_TOLERANCE = 1e-9
WALL_BOUNCE_SPEED_UP_MULTIPLIER = 1.1
FRAMES_AFTER_BOUNCE = 10
CORNERS = (('top', 'left'), ('top', 'right'), ('bottom', 'left'), ('bottom', 'right'))
# Unit direction pointing INTO each wall
INTO_WALL_DIRECTIONS = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


class PlayfieldLimits(NamedTuple):
    """World positions at which the ball's visible edges touch each wall."""

    minimum_x: float  # visible left edge on the left wall
    maximum_x: float  # visible right edge on the right wall
    minimum_y: float  # visible top edge on the top wall
    maximum_y: float  # visible bottom edge on the bottom wall


def _playfield_limits(ball: BallSprite) -> PlayfieldLimits:
    """Return where the ball's visible collision rect touches each wall.

    The ball's walls are its visible pixels (its collision rect), offset from its drawn
    position. With pygame mocked the circle is not drawn, so the visible rect is the whole
    image (offset 0) and the limits are 0 and screen size minus image size.

    Returns:
        PlayfieldLimits: The world positions of wall contact.

    """
    visible_rect = get_sprite_collision_rect(ball)
    offset_x = visible_rect.x - snap_to_pixel(ball.world_x, ball.pixel_snap_mode)
    offset_y = visible_rect.y - snap_to_pixel(ball.world_y, ball.pixel_snap_mode)
    return PlayfieldLimits(
        minimum_x=float(-offset_x),
        maximum_x=float(ball.screen_width - visible_rect.width - offset_x),
        minimum_y=float(-offset_y),
        maximum_y=float(ball.screen_height - visible_rect.height - offset_y),
    )


def _place_ball_past_walls(ball: BallSprite, walls: tuple[str, ...], overshoot: float) -> None:
    """Put the ball's visible edge `overshoot` past each given wall, centered otherwise."""
    limits = _playfield_limits(ball)
    world_x = (limits.minimum_x + limits.maximum_x) / 2
    world_y = (limits.minimum_y + limits.maximum_y) / 2
    if 'left' in walls:
        world_x = limits.minimum_x - overshoot
    if 'right' in walls:
        world_x = limits.maximum_x + overshoot
    if 'top' in walls:
        world_y = limits.minimum_y - overshoot
    if 'bottom' in walls:
        world_y = limits.maximum_y + overshoot
    ball.world_x = world_x
    ball.world_y = world_y


def _expected_position_after_bounce(
    ball: BallSprite, walls: tuple[str, ...], overshoot: float
) -> tuple[float, float]:
    """Mirror the visible overshoot back inside each wall; a ball already inside stays put."""
    limits = _playfield_limits(ball)
    expected_x = (limits.minimum_x + limits.maximum_x) / 2
    expected_y = (limits.minimum_y + limits.maximum_y) / 2
    inside_distance = abs(overshoot)
    if 'left' in walls:
        expected_x = limits.minimum_x + inside_distance
    if 'right' in walls:
        expected_x = limits.maximum_x - inside_distance
    if 'top' in walls:
        expected_y = limits.minimum_y + inside_distance
    if 'bottom' in walls:
        expected_y = limits.maximum_y - inside_distance
    return expected_x, expected_y


def _is_moving_into_walls(unit_x: float, unit_y: float, walls: tuple[str, ...]) -> bool:
    """Return True if the direction has a non-zero component into every given wall."""
    return all(
        unit_x * INTO_WALL_DIRECTIONS[wall][0] + unit_y * INTO_WALL_DIRECTIONS[wall][1]
        > WALL_BOUNCE_TOLERANCE
        for wall in walls
    )


def _wall_bounce_sweep_cases():
    """Every wall and corner x every 15-degree heading into it x overshoots x speeds.

    Returns:
        list: pytest params of (walls, angle, overshoot, speed).

    """
    cases = []
    for walls in [(wall,) for wall in INTO_WALL_DIRECTIONS] + list(CORNERS):
        for angle in WALL_BOUNCE_SWEEP_ANGLES_DEGREES:
            unit_x = math.cos(math.radians(angle))
            unit_y = math.sin(math.radians(angle))
            if not _is_moving_into_walls(unit_x, unit_y, walls):
                continue
            cases.extend(
                pytest.param(
                    walls,
                    angle,
                    overshoot,
                    speed,
                    id=f'{"+".join(walls)}-{angle:03d}deg-overshoot{overshoot}@{speed:.0f}',
                )
                for overshoot in WALL_OVERSHOOTS
                for speed in WALL_BOUNCE_SWEEP_SPEEDS
            )
    return cases


@pytest.mark.usefixtures('pygame_mocks')
class TestBallSpriteWallBounceSpeed:
    """Wall bounces only change speed through the configured WALL_BOUNCE speed-up.

    Replaces tests of the removed legacy BallSprite.bounce(), which applied a hidden,
    hardcoded 1.1x speed-up that bypassed speed_up_settings.
    """

    @pytest.fixture
    def pygame_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    @pytest.mark.parametrize(
        'speed_ups_enabled', [False, True], ids=['no_speed_up', 'wall_speed_up']
    )
    @pytest.mark.parametrize(('walls', 'angle', 'overshoot', 'speed'), _wall_bounce_sweep_cases())
    def test_bounce_reflects_once_and_leaves(
        self, walls, angle, overshoot, speed, speed_ups_enabled
    ):
        """A wall or corner hit is one bounce: mirrored, inside the field, then gone.

        Checks the hit-walls' velocity components flip and the others don't, speed is
        unchanged (or one WALL_BOUNCE step if enabled, even for a corner touching two
        walls), the ball ends up inside the playfield at the mirrored position, and in
        the following frames it moves away without bouncing again.
        """
        speed_up_settings = (
            SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.EXPONENTIAL,
                multiplier=WALL_BOUNCE_SPEED_UP_MULTIPLIER,
            )
            if speed_ups_enabled
            else None
        )
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=speed_up_settings,
        )
        initial_x = speed * math.cos(math.radians(angle))
        initial_y = speed * math.sin(math.radians(angle))
        ball.speed = Speed(initial_x, initial_y)
        _place_ball_past_walls(ball, walls, overshoot)
        description = (
            f'{"+".join(walls)} hit from ({initial_x:.2f}, {initial_y:.2f}), overshoot {overshoot}'
        )

        ball._do_bounce()

        expected_factor = WALL_BOUNCE_SPEED_UP_MULTIPLIER if speed_ups_enabled else 1.0
        flips_x = 'left' in walls or 'right' in walls
        flips_y = 'top' in walls or 'bottom' in walls
        expected_speed = (
            (-initial_x if flips_x else initial_x) * expected_factor,
            (-initial_y if flips_y else initial_y) * expected_factor,
        )
        assert (ball.speed.x, ball.speed.y) == pytest.approx(
            expected_speed, abs=WALL_BOUNCE_TOLERANCE
        ), description
        assert ball.speed_up_count == (1 if speed_ups_enabled else 0), description
        assert (ball.world_x, ball.world_y) == pytest.approx(
            _expected_position_after_bounce(ball, walls, overshoot), abs=WALL_BOUNCE_TOLERANCE
        ), description
        limits = _playfield_limits(ball)
        assert limits.minimum_x <= ball.world_x <= limits.maximum_x, description
        assert limits.minimum_y <= ball.world_y <= limits.maximum_y, description

        speed_after_bounce = (ball.speed.x, ball.speed.y)
        for frame in range(1, FRAMES_AFTER_BOUNCE + 1):
            ball.dt_tick(1 / 60)
            assert (ball.speed.x, ball.speed.y) == speed_after_bounce, (
                f'{description}: bounced again {frame} frame(s) later'
            )
        assert ball.speed_up_count == (1 if speed_ups_enabled else 0), description

    @pytest.mark.parametrize('motion', ['away', 'stationary'])
    @pytest.mark.parametrize('overshoot', [2.0, 7.5])
    @pytest.mark.parametrize(
        'walls', [(wall,) for wall in INTO_WALL_DIRECTIONS] + list(CORNERS), ids='+'.join
    )
    def test_ball_past_wall_is_put_back_inside_without_bouncing(
        self, mocker, walls, overshoot, motion
    ):
        """A ball found past a wall but not moving into it is moved inside, not bounced.

        No velocity change, no sound, and no WALL_BOUNCE speed-up; only the position is
        mirrored back inside the playfield.
        """
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(triggers=SpeedUpTrigger.WALL_BOUNCE),
        )
        ball.snd = mocker.Mock()
        away_x = -sum(INTO_WALL_DIRECTIONS[wall][0] for wall in walls)
        away_y = -sum(INTO_WALL_DIRECTIONS[wall][1] for wall in walls)
        velocity = (away_x * 200.0, away_y * 200.0) if motion == 'away' else (0.0, 0.0)
        ball.speed = Speed(*velocity)
        _place_ball_past_walls(ball, walls, overshoot)

        ball._do_bounce()

        assert (ball.speed.x, ball.speed.y) == velocity
        assert ball.speed_up_count == 0
        ball.snd.play.assert_not_called()
        assert (ball.world_x, ball.world_y) == pytest.approx(
            _expected_position_after_bounce(ball, walls, overshoot)
        )

    def test_wall_bounce_trigger_applies_one_curve_step_per_bounce(self):
        """Three real wall bounces with WALL_BOUNCE give exactly three curve steps."""
        ball = BallSprite(
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.EXPONENTIAL,
                multiplier=MULTIPLIER_1_1,
            ),
        )
        ball.speed = Speed(200.0, -100.0)

        for wall in ('top', 'bottom', 'top'):
            _place_ball_past_walls(ball, (wall,), overshoot=2.0)
            ball._do_bounce()

        assert ball.speed_up_count == 3
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(
            math.hypot(200.0, 100.0) * MULTIPLIER_1_1**3
        )
        # Three vertical reflections leave the ball moving up and to the right
        assert ball.speed.x > 0
        assert ball.speed.y > 0


class TestBallSpriteUpdate:
    """Test BallSprite update functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_update_movement(self, mocker):
        """Test ball update moves the ball."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = 100
        ball.rect.y = 100
        ball.world_x = 100.0  # Sub-pixel position must also be set
        ball.world_y = 100.0
        ball.speed.x = 2
        ball.speed.y = 3

        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # With speed=2,3 and dt=0.016, movement should be (0.032, 0.048)
        # world_x = 100.032, world_y = 100.048, both round to 100
        assert ball.rect.x == 100  # No visible movement due to rounding
        assert ball.rect.y == 100  # No visible movement due to rounding

    def test_ball_update_left_wall_bounce(self, mocker):
        """Test ball bounces off left wall."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = -25  # Left of screen (less than -width)
        ball.world_x = -25.0  # Sub-pixel position must also be set
        ball.direction = 45
        ball.speed.x = -2

        mock_kill = mocker.patch.object(ball, 'kill')
        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Should kill() when ball goes off-screen (no direction change for left/right)
        mock_kill.assert_called_once()
        expected_direction = 45  # Direction should remain unchanged
        assert ball.direction == expected_direction

    def test_ball_update_right_wall_bounce(self, mocker):
        """Test ball bounces off right wall."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        ball.screen_width = 800
        ball.width = 20
        assert ball.rect is not None
        ball.rect.x = 810  # Right of screen
        ball.world_x = 810.0  # Sub-pixel position must also be set
        ball.direction = 45
        ball.speed.x = 2

        mock_kill = mocker.patch.object(ball, 'kill')
        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Should kill() when ball goes off-screen (no direction change for left/right)
        mock_kill.assert_called_once()
        expected_direction = 45  # Direction should remain unchanged
        assert ball.direction == expected_direction

    def test_ball_update_reset_on_exit(self, mocker):
        """Test ball resets when exiting screen."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = 1000  # Way off screen
        ball.world_x = 1000.0  # Sub-pixel position must also be set
        ball.rect.y = 100
        ball.world_y = 100.0

        mock_kill = mocker.patch.object(ball, 'kill')
        ball.dt_tick(0.016)  # Use dt_tick instead of update
        mock_kill.assert_called_once()

    def test_ball_update_no_kill_on_vertical_exit(self, mocker):
        """Test ball does NOT kill when exiting screen vertically (only horizontal exits kill)."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = 100
        ball.world_x = 100.0  # Sub-pixel position must also be set
        ball.rect.y = 1000  # Way off screen
        ball.world_y = 1000.0
        ball.screen_height = 600  # Set screen height so ball is off screen
        ball.speed.y = 0  # Don't move vertically

        # Mock _do_bounce to not interfere with the test
        mocker.patch.object(ball, '_do_bounce')
        mock_kill = mocker.patch.object(ball, 'kill')
        ball.dt_tick(0.016)  # Use dt_tick instead of update
        mock_kill.assert_not_called()  # Should NOT be called for vertical exits

    def test_ball_update_calls_do_bounce(self, mocker):
        """Test ball dt_tick calls _do_bounce."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()

        mock_do_bounce = mocker.patch.object(ball, '_do_bounce')
        ball.dt_tick(0.016)  # Use dt_tick instead of update
        mock_do_bounce.assert_called_once()


class TestBallSpriteIntegration:
    """Test BallSprite integration scenarios."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_full_game_cycle(self, mocker):
        """Test complete ball game cycle."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()

        # Initial state
        assert ball.dirty == SPEED_2

        # Update should move ball
        assert ball.rect is not None
        original_x = ball.rect.x
        original_y = ball.rect.y
        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Ball should have moved
        assert ball.rect.x != original_x or ball.rect.y != original_y

    def test_ball_with_sound_integration(self, mocker):
        """Test ball with sound integration."""
        mocker.patch('pygame.draw.circle')
        mock_sound = mocker.Mock()
        mocker.patch(
            'glitchygames.game_objects.ball.game_objects.load_sound',
            return_value=mock_sound,
        )

        ball = BallSprite(collision_sound='bounce.wav')
        assert ball.rect is not None
        ball.rect.y = -5  # Trigger top wall bounce
        ball.world_y = -5.0  # Sub-pixel position must also be set
        ball.speed.y = -2

        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Sound should have been played
        mock_sound.play.assert_called()

    def test_ball_speed_progression(self, mocker):
        """Test ball speed increases with each speed-up (replaces the legacy bounce() test)."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite(speed_up_settings=SpeedUpSettings(multiplier=MULTIPLIER_1_1))
        original_speed = ball.speed.x

        for _ in range(3):
            ball.speed_up()

        # Exponential curve: 1.1^3 = 1.331
        expected_speed = original_speed * (MULTIPLIER_1_1**3)
        floating_point_tolerance = 1e-10  # Use approximate equality for floating point
        assert abs(ball.speed.x - expected_speed) < floating_point_tolerance


class TestBallSpeedUpExponentialBoth:
    """Test speed_up with the EXPONENTIAL curve on BOTH axes."""

    def _create_ball(self):
        """Create a BallSprite configured for exponential speed-ups on both axes.

        Returns:
            BallSprite: A configured ball sprite.

        """
        return BallSprite(
            x=100,
            y=100,
            width=20,
            height=20,
            speed_up_settings=SpeedUpSettings(
                curve=SpeedUpCurve.EXPONENTIAL,
                axes=SpeedUpAxes.BOTH,
                multiplier=MULTIPLIER_1_1,
            ),
        )

    def test_speed_up_exponential_both(self, mock_pygame_patches):
        """Test speed_up scales both components by the exponential multiplier."""
        ball = self._create_ball()
        ball.speed.x = 150.0
        ball.speed.y = 100.0
        original_x = ball.speed.x
        original_y = ball.speed.y

        ball.speed_up()

        # Both components should be scaled by exactly the multiplier
        assert ball.speed.x == pytest.approx(original_x * MULTIPLIER_1_1)
        assert ball.speed.y == pytest.approx(original_y * MULTIPLIER_1_1)
        assert ball.speed_up_count == 1

    def test_speed_up_exponential_both_with_zero_speeds(self, mock_pygame_patches):
        """Test speed_up exponential on both axes when speeds are zero."""
        ball = self._create_ball()
        ball.speed.x = 0
        ball.speed.y = 0

        ball.speed_up()

        assert ball.speed.x == 0
        assert ball.speed.y == 0


class TestContinuousSpeedUpExponentialY:
    """Test continuous exponential speed-up on the Y axis only."""

    def test_continuous_exponential_y_speed_up(self, mock_pygame_patches):
        """Test the CONTINUOUS trigger with an EXPONENTIAL curve on Y_ONLY."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.CONTINUOUS,
                curve=SpeedUpCurve.EXPONENTIAL,
                axes=SpeedUpAxes.Y_ONLY,
                multiplier=MULTIPLIER_1_1,
                interval=1.0,
            ),
        )
        ball.speed.x = 50.0
        ball.speed.y = 100.0
        original_x = ball.speed.x
        original_y = ball.speed.y

        # One full interval of game time elapses
        ball._advance_continuous_speed_up(1.0)

        assert ball.speed_up_count == 1
        assert ball.speed.y == pytest.approx(original_y * MULTIPLIER_1_1)
        assert ball.speed.x == original_x
        # The timer starts counting toward the next step from zero
        assert ball._continuous_elapsed_time == pytest.approx(0.0)


class TestContinuousSpeedUpLinear:
    """Test continuous linear speed-up on both axes."""

    def test_continuous_linear_speed_up(self, mock_pygame_patches):
        """Test the CONTINUOUS trigger with a LINEAR curve on BOTH axes."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.CONTINUOUS,
                curve=SpeedUpCurve.LINEAR,
                axes=SpeedUpAxes.BOTH,
                multiplier=MULTIPLIER_1_1,
                interval=1.0,
            ),
        )
        ball.speed.x = 100.0
        ball.speed.y = 100.0
        original_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)

        # One full interval of game time elapses
        ball._advance_continuous_speed_up(1.0)

        assert ball.speed_up_count == 1
        # First linear step from n=0 is (1 + k) / 1 = multiplier
        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert new_magnitude == pytest.approx(original_magnitude * MULTIPLIER_1_1)


class TestPaddleBounceTriggerExponentialBoth:
    """Test the PADDLE_BOUNCE trigger scaling both axes exponentially."""

    def test_paddle_bounce_scales_both_axes(self, mock_pygame_patches):
        """Test on_paddle_bounce speeds up both components when PADDLE_BOUNCE is set."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.PADDLE_BOUNCE,
                curve=SpeedUpCurve.EXPONENTIAL,
                axes=SpeedUpAxes.BOTH,
                multiplier=MULTIPLIER_1_1,
            ),
        )
        ball.speed.x = 150.0
        ball.speed.y = 100.0

        ball.on_paddle_bounce()

        assert ball.speed.x == pytest.approx(150.0 * MULTIPLIER_1_1)
        assert ball.speed.y == pytest.approx(100.0 * MULTIPLIER_1_1)
        assert ball.speed_up_count == 1


class TestTriggeredSpeedUpNotConfigured:
    """Test _apply_triggered_speed_up with a trigger that is not configured."""

    def test_unconfigured_trigger_does_nothing(self, mock_pygame_patches):
        """Test that a trigger missing from settings.triggers leaves speed unchanged."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_settings=SpeedUpSettings(triggers=SpeedUpTrigger.PADDLE_BOUNCE),
        )
        original_x = ball.speed.x
        original_y = ball.speed.y

        ball._apply_triggered_speed_up(SpeedUpTrigger.WALL_BOUNCE)

        # Speed should remain unchanged and no curve step consumed
        assert ball.speed.x == original_x
        assert ball.speed.y == original_y
        assert ball.speed_up_count == 0


class TestBallBoundaryCollisions:
    """Test boundary collision handlers (lines 685->694, 708, 715->724, 736, 743->752)."""

    def _create_ball_with_left_right_bounce(self):
        """Create a ball with left/right bouncing enabled.

        Returns:
            BallSprite: A ball with all bouncing enabled.

        """
        return BallSprite(
            x=100,
            y=100,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )

    def test_bottom_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test bottom collision reflects Y speed (lines 685->694)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = 100.0
        ball.speed.y = 100.0  # Moving downward

        # Position ball at bottom boundary (must set world_y for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.y = ball.screen_height - ball.height
        ball.world_y = float(ball.screen_height - ball.height)

        ball._do_bounce()

        # Y speed should be negative (upward) after bottom bounce
        assert ball.speed.y < 0

    def test_left_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test left collision plays sound (line 708)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.snd = mocker.Mock()
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        # Position ball at left boundary (must set world_x for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.x = 0
        ball.world_x = 0.0

        ball._do_bounce()

        ball.snd.play.assert_called()
        # X speed should be positive (rightward)
        assert ball.speed.x > 0

    def test_left_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test left collision reflects X speed (lines 715->724)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        assert ball.rect is not None
        ball.rect.x = 0
        ball.world_x = 0.0  # Sub-pixel position must also be set

        ball._do_bounce()

        assert ball.speed.x > 0
        assert ball.world_x >= 0  # Ball is inside boundary
        assert ball.rect.x == round(ball.world_x)

    def test_right_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test right collision plays sound (line 736)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.snd = mocker.Mock()
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Position ball at right boundary (must set world_x for sub-pixel tracking)
        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width
        ball.world_x = float(ball.screen_width - ball.width)

        ball._do_bounce()

        ball.snd.play.assert_called()

    def test_right_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test right collision reflects X speed (lines 743->752)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width
        ball.world_x = float(ball.screen_width - ball.width)  # Sub-pixel position

        ball._do_bounce()

        assert ball.speed.x < 0
        boundary = float(ball.screen_width - ball.width)
        assert ball.world_x <= boundary  # Ball is inside boundary
        assert ball.rect.x == round(ball.world_x)


class TestCornerCollisions:
    """A ball touching two walls at a corner bounces off both, once, and leaves.

    These used to expect the ball to be teleported to 1 px inside the corner; that
    placement came with a double reflection that sent the ball back into the corner
    (bug #14). The full corner sweep lives in TestBallSpriteWallBounceSpeed.
    """

    def _create_bouncing_ball(self):
        """Create a ball with all bouncing enabled.

        Returns:
            BallSprite: A ball with all bouncing enabled.

        """
        return BallSprite(
            x=100,
            y=100,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )

    def _assert_corner_bounce(self, ball, *, corner, speed_x, speed_y):
        """Bounce a ball whose visible edges sit exactly in a corner; it reflects and leaves.

        Args:
            ball: The ball.
            corner: ('top' or 'bottom', 'left' or 'right').
            speed_x: Horizontal speed into the corner.
            speed_y: Vertical speed into the corner.

        """
        limits = _playfield_limits(ball)
        corner_x = limits.minimum_x if 'left' in corner else limits.maximum_x
        corner_y = limits.minimum_y if 'top' in corner else limits.maximum_y
        ball.speed.x = speed_x
        ball.speed.y = speed_y
        ball.world_x = corner_x
        ball.world_y = corner_y

        ball._do_bounce()

        # Both components reflected away from the walls; the ball stays where it touched
        assert (ball.speed.x, ball.speed.y) == (-speed_x, -speed_y)
        assert (ball.world_x, ball.world_y) == (corner_x, corner_y)

        # Next frame it moves out of the corner instead of bouncing again
        ball.dt_tick(1 / 60)
        assert (ball.speed.x, ball.speed.y) == (-speed_x, -speed_y)
        assert abs(ball.world_x - corner_x) > 0
        assert abs(ball.world_y - corner_y) > 0

    def test_top_left_corner_collision(self, mock_pygame_patches):
        """Test top-left corner collision."""
        ball = self._create_bouncing_ball()
        self._assert_corner_bounce(ball, corner=('top', 'left'), speed_x=-100.0, speed_y=-100.0)

    def test_top_right_corner_collision(self, mock_pygame_patches):
        """Test top-right corner collision."""
        ball = self._create_bouncing_ball()
        self._assert_corner_bounce(ball, corner=('top', 'right'), speed_x=100.0, speed_y=-100.0)

    def test_bottom_left_corner_collision(self, mock_pygame_patches):
        """Test bottom-left corner collision."""
        ball = self._create_bouncing_ball()
        self._assert_corner_bounce(ball, corner=('bottom', 'left'), speed_x=-100.0, speed_y=100.0)

    def test_bottom_right_corner_collision(self, mock_pygame_patches):
        """Test bottom-right corner collision."""
        ball = self._create_bouncing_ball()
        self._assert_corner_bounce(ball, corner=('bottom', 'right'), speed_x=100.0, speed_y=100.0)


class TestDtTickMovementMismatch:
    """Test dt_tick movement mismatch logging (line 553)."""

    def test_dt_tick_basic_movement(self, mock_pygame_patches):
        """Test dt_tick applies movement correctly."""
        ball = BallSprite(x=100, y=100)
        ball.speed.x = 200.0
        ball.speed.y = 100.0

        assert ball.rect is not None
        original_x = ball.rect.x
        original_y = ball.rect.y

        ball.dt_tick(0.016)

        # Position should change based on speed * dt
        assert ball.rect.x != original_x or ball.rect.y != original_y


def _speed_cap_paddle(*, x):
    """A real VerticalPaddle at (x, 90), 20x100, with no collision sound."""
    paddle = VerticalPaddle('Test Paddle', (20, 100), (x, 90), (255, 255, 255), 400)
    paddle.snd = None
    return paddle


class TestPaddleCollisionSpeedCap:
    """Test handle_paddle_collision's speed cap, sound and callback (mocked pygame).

    With pygame mocked the ball's circle is not drawn, so its collision rect is its full
    20x20 image; the visible-pixel geometry is covered in test_ball_paddle_collision.py.
    """

    def test_paddle_collision_caps_speed(self, mock_pygame_patches):
        """Test that paddle collision caps speed at the configured max_speed."""
        ball = BallSprite(
            x=100,
            y=100,
            width=20,
            height=20,
            speed_up_settings=SpeedUpSettings(max_speed=500.0),
        )
        paddle = _speed_cap_paddle(x=90)

        # Set extremely high speed
        ball.speed.x = 1000.0
        ball.speed.y = 1000.0

        # Position ball overlapping with paddle
        ball.world_x = 95.0
        ball.world_y = 100.0

        assert ball.handle_paddle_collision(paddle) is True

        # Speed should be capped
        speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert speed_magnitude <= 500.0 + 0.01  # max_speed = 500.0

    def test_paddle_collision_without_max_speed_does_not_cap(self, mock_pygame_patches):
        """Test that default settings (max_speed=None) leave a fast ball uncapped."""
        ball = BallSprite(x=100, y=100, width=20, height=20)
        paddle = _speed_cap_paddle(x=90)

        ball.speed.x = 1000.0
        ball.speed.y = 1000.0
        ball.world_x = 95.0
        ball.world_y = 100.0

        assert ball.handle_paddle_collision(paddle) is True

        # No cap and no PADDLE_BOUNCE trigger: magnitude is unchanged by the collision
        speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert speed_magnitude == pytest.approx(math.sqrt(2) * 1000.0)

    def test_paddle_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test paddle collision plays paddle's sound."""
        ball = BallSprite(x=100, y=100, width=20, height=20)
        paddle = _speed_cap_paddle(x=120)
        paddle.snd = mocker.Mock()

        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Ball center is to the right of paddle center
        ball.world_x = 130.0
        ball.world_y = 100.0

        assert ball.handle_paddle_collision(paddle) is True

        paddle.snd.play.assert_called_once()

    def test_paddle_collision_triggers_on_paddle_collision(self, mock_pygame_patches, mocker):
        """Test paddle collision calls on_paddle_collision if it exists."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        mock_callback = mocker.Mock()
        ball.on_paddle_collision = mock_callback  # type: ignore[unresolved-attribute]

        paddle = _speed_cap_paddle(x=120)

        ball.speed.x = 100.0
        ball.speed.y = 50.0
        ball.world_x = 130.0
        ball.world_y = 100.0

        assert ball.handle_paddle_collision(paddle) is True

        mock_callback.assert_called_once_with(ball)


class TestBallMovementMismatchWarning:
    """Test dt_tick movement mismatch logging (line 553)."""

    def test_dt_tick_movement_mismatch_detection(self, mock_pygame_patches, mocker):
        """Test that movement mismatch is detected when rect changes unexpectedly.

        Covers line 553 where delta doesn't match expected movement.
        The mismatch occurs when rect.x or rect.y is modified externally
        between the move and the delta check (e.g., by boundary clamping
        in _do_bounce). The dt_tick method logs a warning in that case.
        """
        ball = BallSprite(
            x=400,
            y=0,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        ball.speed.x = 0.0
        ball.speed.y = -200.0  # Moving up fast

        # Position ball so bounce will modify rect.y
        assert ball.rect is not None
        ball.rect.y = -5

        # dt_tick will: add move_y to rect.y (making it more negative),
        # then _do_bounce will set it to 1.
        # This means delta_y != round(move_y), triggering line 553.
        ball.dt_tick(0.016)

        # After bounce, rect.y should be positive
        assert ball.rect.y >= 0


class TestBallHandlePaddleCollisionMiss:
    """Test handle_paddle_collision with a paddle the ball does not touch."""

    def test_far_paddle_is_not_a_collision(self, mock_pygame_patches):
        """A paddle far from the ball returns False and leaves the ball's velocity alone."""
        ball = BallSprite(x=100, y=100, width=20, height=20)
        ball.world_x = 100.0
        ball.world_y = 100.0
        ball.speed.x = 100.0
        paddle = _speed_cap_paddle(x=500)

        assert ball.handle_paddle_collision(paddle) is False
        assert ball.speed.x == 100.0
        assert ball.world_x == 100.0


class TestBallBottomBounceZeroSpeed:
    """Test bottom collision when speed magnitude is zero (line 685->694)."""

    def test_bottom_collision_zero_magnitude_no_reflection(self, mock_pygame_patches):
        """Test that bottom collision with zero speed skips reflection.

        Covers the branch at 685->694 where speed_magnitude == 0 and the
        reflection logic is skipped.
        """
        ball = BallSprite(
            x=400,
            y=580,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed.x = 0.0
        ball.speed.y = 0.0

        import logging

        log = logging.getLogger('game')

        # Position ball at bottom
        assert ball.rect is not None
        ball.rect.y = ball.screen_height - ball.height

        ball._handle_bottom_collision(log)

        # Speed should remain zero
        assert ball.speed.x == pytest.approx(0.0)
        assert ball.speed.y == pytest.approx(0.0)

    def test_left_collision_zero_magnitude_no_reflection(self, mock_pygame_patches):
        """Test that left collision with zero speed skips reflection.

        Covers branch 715->724 where speed_magnitude == 0.
        """
        ball = BallSprite(
            x=0,
            y=300,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed.x = 0.0
        ball.speed.y = 0.0

        import logging

        log = logging.getLogger('game')

        assert ball.rect is not None
        ball.rect.x = 0

        ball._handle_left_collision(log)

        assert ball.speed.x == pytest.approx(0.0)

    def test_right_collision_zero_magnitude_no_reflection(self, mock_pygame_patches):
        """Test that right collision with zero speed skips reflection.

        Covers branch 743->752 where speed_magnitude == 0.
        """
        ball = BallSprite(
            x=780,
            y=300,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed.x = 0.0
        ball.speed.y = 0.0

        import logging

        log = logging.getLogger('game')

        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width

        ball._handle_right_collision(log)

        assert ball.speed.x == pytest.approx(0.0)


# Expected whole pixel for each input under every PixelSnapMode, in column order:
# (NEAREST_HALF_UP, NEAREST_EVEN, FLOOR, CEIL, TRUNCATE).
SNAP_EXPECTATION_MODES = (
    PixelSnapMode.NEAREST_HALF_UP,
    PixelSnapMode.NEAREST_EVEN,
    PixelSnapMode.FLOOR,
    PixelSnapMode.CEIL,
    PixelSnapMode.TRUNCATE,
)
LARGEST_FLOAT_BELOW_HALF = math.nextafter(0.5, 0.0)  # 0.49999999999999994
SMALLEST_FLOAT_ABOVE_HALF = math.nextafter(0.5, 1.0)
LARGEST_FLOAT_BELOW_TWO = math.nextafter(2.0, 0.0)
SMALLEST_FLOAT_ABOVE_TWO = math.nextafter(2.0, 3.0)
# Above 2**52 adjacent floats are 1 apart, so value + 0.5 rounds to an even neighbor.
LARGE_ODD_WHOLE_NUMBER = float(2**52 + 1)
SNAP_EXPECTATIONS = {
    # Whole numbers: no rounding required, every mode must return the value unchanged
    'zero': (0.0, (0, 0, 0, 0, 0)),
    'negative zero': (-0.0, (0, 0, 0, 0, 0)),
    'positive whole': (3.0, (3, 3, 3, 3, 3)),
    'negative whole': (-3.0, (-3, -3, -3, -3, -3)),
    'large positive whole': (1_000_000.0, (1_000_000,) * 5),
    'large negative whole': (-1_000_000.0, (-1_000_000,) * 5),
    'whole above 2**52': (LARGE_ODD_WHOLE_NUMBER, (2**52 + 1,) * 5),
    'negative whole above 2**52': (-LARGE_ODD_WHOLE_NUMBER, (-(2**52 + 1),) * 5),
    # Fractions: rounding required
    'quarter': (0.25, (0, 0, 0, 1, 0)),
    'three quarters': (0.75, (1, 1, 0, 1, 0)),
    'negative quarter': (-0.25, (0, 0, -1, 0, 0)),
    'negative three quarters': (-0.75, (-1, -1, -1, 0, 0)),
    # Exact halves: where the nearest modes differ from each other
    'half': (0.5, (1, 0, 0, 1, 0)),
    'one and a half': (1.5, (2, 2, 1, 2, 1)),
    'two and a half': (2.5, (3, 2, 2, 3, 2)),
    'negative half': (-0.5, (0, 0, -1, 0, 0)),
    'negative one and a half': (-1.5, (-1, -2, -2, -1, -1)),
    'negative two and a half': (-2.5, (-2, -2, -3, -2, -2)),
    'large half': (1_000_000.5, (1_000_001, 1_000_000, 1_000_000, 1_000_001, 1_000_000)),
    'large negative half': (
        -1_000_000.5,
        (-1_000_000, -1_000_000, -1_000_001, -1_000_000, -1_000_000),
    ),
    # One float step either side of a half
    'just below half': (LARGEST_FLOAT_BELOW_HALF, (0, 0, 0, 1, 0)),
    'just above half': (SMALLEST_FLOAT_ABOVE_HALF, (1, 1, 0, 1, 0)),
    'just above negative half': (-LARGEST_FLOAT_BELOW_HALF, (0, 0, -1, 0, 0)),
    'just below negative half': (-SMALLEST_FLOAT_ABOVE_HALF, (-1, -1, -1, 0, 0)),
    # One float step either side of a whole number
    'just below two': (LARGEST_FLOAT_BELOW_TWO, (2, 2, 1, 2, 1)),
    'just above two': (SMALLEST_FLOAT_ABOVE_TWO, (2, 2, 2, 3, 2)),
    'just above negative two': (-LARGEST_FLOAT_BELOW_TWO, (-2, -2, -2, -1, -1)),
    'just below negative two': (-SMALLEST_FLOAT_ABOVE_TWO, (-2, -2, -3, -2, -2)),
}


def _snap_expectation_cases():
    """Flatten SNAP_EXPECTATIONS into one pytest param per (input, mode).

    Returns:
        list: pytest params of (value, mode, expected_pixel).

    """
    return [
        pytest.param(value, mode, expected_pixel, id=f'{label}-{mode.name}')
        for label, (value, expected_pixels) in SNAP_EXPECTATIONS.items()
        for mode, expected_pixel in zip(SNAP_EXPECTATION_MODES, expected_pixels, strict=True)
    ]


class TestSnapToPixel:
    """Test snap_to_pixel for every PixelSnapMode at every rounding boundary."""

    def test_expectation_table_covers_every_mode(self):
        """A new PixelSnapMode must be added to the expectation table to be tested."""
        assert set(SNAP_EXPECTATION_MODES) == set(PixelSnapMode)

    @pytest.mark.parametrize(('value', 'mode', 'expected_pixel'), _snap_expectation_cases())
    def test_snap_modes(self, value, mode, expected_pixel):
        """Each mode maps the value to the documented whole pixel, as an int."""
        snapped = snap_to_pixel(value, mode)
        assert snapped == expected_pixel
        assert type(snapped) is int

    def test_snapping_lives_in_neutral_module_and_is_re_exported(self):
        """glitchygames.pixel_snap owns snapping; ball and game_objects re-export it."""
        import glitchygames.game_objects as game_objects_package
        import glitchygames.pixel_snap as pixel_snap_module

        assert ball_module.PixelSnapMode is pixel_snap_module.PixelSnapMode
        assert ball_module.snap_to_pixel is pixel_snap_module.snap_to_pixel
        assert game_objects_package.PixelSnapMode is pixel_snap_module.PixelSnapMode
        assert game_objects_package.snap_to_pixel is pixel_snap_module.snap_to_pixel


@pytest.mark.usefixtures('pygame_mocks')
class TestBallSpritePixelSnapping:
    """Test that world_x/world_y keep rect in sync using the ball's pixel snap mode."""

    @pytest.fixture
    def pygame_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_default_mode_is_nearest_half_up(self):
        """Balls default to NEAREST_HALF_UP for smooth, unbiased motion."""
        ball = BallSprite()
        assert ball.pixel_snap_mode is PixelSnapMode.NEAREST_HALF_UP

    def test_setting_world_position_updates_rect(self):
        """Assigning world_x/world_y moves rect without any manual sync."""
        ball = BallSprite()
        ball.world_x = 123.6
        ball.world_y = 45.5
        assert (ball.rect.x, ball.rect.y) == (124, 46)

    def test_in_place_adjustment_updates_rect(self):
        """Augmented assignment (e.g. collision separation) also moves rect."""
        ball = BallSprite()
        ball.world_x = 100.0
        ball.world_y = 100.0
        ball.world_x -= 2.5
        ball.world_y += 1.5
        assert (ball.rect.x, ball.rect.y) == (98, 102)
        assert (ball.world_x, ball.world_y) == (97.5, 101.5)

    def test_custom_mode_is_used_for_rect(self):
        """A ball created with FLOOR snapping draws at the floored position."""
        ball = BallSprite(pixel_snap_mode=PixelSnapMode.FLOOR)
        ball.world_x = 10.9
        ball.world_y = -0.5
        assert (ball.rect.x, ball.rect.y) == (10, -1)

    def test_changing_mode_resnaps_rect(self):
        """Switching modes immediately re-derives rect from the world position."""
        ball = BallSprite()
        ball.world_x = 10.5
        assert ball.rect.x == 11
        ball.pixel_snap_mode = PixelSnapMode.FLOOR
        assert ball.rect.x == 10

    def test_half_pixel_per_frame_motion_steps_evenly(self):
        """At 0.5 px/frame, NEAREST_HALF_UP advances exactly 1 px every 2 frames.

        Python's round() (NEAREST_EVEN) instead holds some pixels for 3 frames and others
        for 1, which shows up as visible stutter in slow-moving sprites.
        """
        ball = BallSprite(bounce_top_bottom=False)
        ball.world_x = 100.0
        ball.world_y = 100.0
        # 32 px/s at 1/64 s per frame is exactly 0.5 px/frame in binary floating point,
        # so accumulated error cannot nudge a position off the .5 boundary.
        ball.speed = Speed(32.0, 0.0)
        rendered_x_positions = [ball.rect.x]
        for _ in range(8):
            ball.dt_tick(1 / 64)
            rendered_x_positions.append(ball.rect.x)
        assert rendered_x_positions == [100, 101, 101, 102, 102, 103, 103, 104, 104]
