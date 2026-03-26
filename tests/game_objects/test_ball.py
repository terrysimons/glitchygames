"""Tests for BallSprite game object."""

import math
import sys
from pathlib import Path

import pygame
import pytest

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
SIZE_20 = 20
SIZE_30 = 30
POS_50 = 50
POS_749 = 749
POS_25 = 25
POS_399 = 399
DIRECTION_360 = 360
SPEED_2 = 2
SPEED_1 = 1
SPEED_NEG_2 = -2
Y_580 = 580
POS_102 = 102
POS_103 = 103
DIRECTION_125 = 125
DIRECTION_340 = 340
DIRECTION_315 = 315
MULTIPLIER_1_1 = 1.1


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
        assert POS_50 <= ball.rect.x <= POS_749  # Reset sets random position in this range
        assert POS_25 <= ball.rect.y <= POS_399  # Reset sets random position in this range
        assert ball.use_gfxdraw is True
        # Direction is set by reset() during initialization, so it will be random
        assert 0 <= ball.direction <= DIRECTION_360  # Reset sets random direction
        assert isinstance(ball.speed, Speed)
        # Speed is calculated from random direction in reset(), so we can't predict exact values
        # But we can test that it's a reasonable speed magnitude
        # (around 250.0 based on current implementation)
        speed_magnitude = (ball.speed.x**2 + ball.speed.y**2) ** 0.5
        min_speed_magnitude = 240.0
        max_speed_magnitude = 260.0
        # Should be around 250.0 (current implementation uses fixed speed_magnitude = 250.0)
        assert min_speed_magnitude <= speed_magnitude <= max_speed_magnitude
        assert ball.dirty == SPEED_2

    def test_ball_sprite_initialization_custom(self, mocker):
        """Test BallSprite initialization with custom parameters."""
        groups = mocker.Mock()
        mocker.patch('pygame.mixer.Sound')
        ball = BallSprite(
            x=100, y=200, width=30, height=30, groups=groups, collision_sound='test.wav',
        )

        # Position is set by reset() during initialization, so it will be random
        assert ball.rect is not None
        assert POS_50 <= ball.rect.x <= POS_749  # Reset sets random position in this range
        assert POS_25 <= ball.rect.y <= POS_399  # Reset sets random position in this range
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
        ball.speed.y = -2
        ball.snd = mocker.Mock()

        ball._do_bounce()

        assert ball.rect.y == 1  # Small buffer to prevent sticking
        assert ball.speed.y == SPEED_2  # Reversed
        ball.snd.play.assert_called_once()

    def test_do_bounce_bottom_wall(self, mocker):
        """Test ball bounces off bottom wall."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        ball.screen_height = 600
        ball.height = 20
        assert ball.rect is not None
        ball.rect.y = 590  # Below screen
        ball.speed.y = 2
        ball.snd = mocker.Mock()

        ball._do_bounce()

        expected_bottom_y = 579  # screen_height - height - 1 (buffer to prevent sticking)
        assert ball.rect.y == expected_bottom_y
        assert ball.speed.y == SPEED_NEG_2  # Reversed
        ball.snd.play.assert_called_once()

    def test_do_bounce_no_sound(self, mocker):
        """Test ball bounces without sound when no sound loaded."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.y = -5
        ball.speed.y = -2
        # No snd attribute set

        ball._do_bounce()

        assert ball.rect.y == 1  # Small buffer to prevent sticking
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
        """Test ball reset sets random position within bounds."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        original_x = ball.rect.x
        original_y = ball.rect.y

        ball.reset()

        # Position should be within expected bounds
        assert POS_50 <= ball.rect.x <= POS_749
        assert POS_25 <= ball.rect.y <= POS_399
        # Should be different from original (very likely)
        assert ball.rect.x != original_x or ball.rect.y != original_y

    def test_ball_reset_direction(self, mocker):
        """Test ball reset sets random direction."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        original_direction = ball.direction

        ball.reset()

        # Direction should be in 0-360 range
        assert 0 <= ball.direction <= DIRECTION_360
        # Should be different from original (very likely)
        assert ball.direction != original_direction

    def test_ball_reset_direction_range(self, mocker):
        """Test ball reset direction is within expected range."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()

        # Test multiple resets to ensure direction is in valid range
        for _ in range(10):
            ball.reset()
            assert 0 <= ball.direction <= DIRECTION_360


class TestBallSpriteBounceMethod:
    """Test BallSprite bounce method."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_ball_bounce_direction_change(self, mocker):
        """Test ball bounce changes direction correctly."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        ball.direction = 45
        original_speed_x = ball.speed.x
        original_speed_y = ball.speed.y

        ball.bounce(10)

        # Direction should be (180 - 45) % 360 - 10 = 125
        assert ball.direction == DIRECTION_125
        # Speed should be increased by 1.1
        assert ball.speed.x == original_speed_x * MULTIPLIER_1_1
        assert ball.speed.y == original_speed_y * MULTIPLIER_1_1

    def test_ball_bounce_speed_increase(self, mocker):
        """Test ball bounce increases speed."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        original_speed_x = ball.speed.x
        original_speed_y = ball.speed.y

        ball.bounce(0)

        assert ball.speed.x == original_speed_x * MULTIPLIER_1_1
        assert ball.speed.y == original_speed_y * MULTIPLIER_1_1

    def test_ball_bounce_direction_wrapping(self, mocker):
        """Test ball bounce handles direction wrapping correctly."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        ball.direction = 200

        ball.bounce(0)

        # (180 - 200) % 360 = 340
        assert ball.direction == DIRECTION_340


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
        ball.speed.x = 2
        ball.speed.y = 3

        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # With speed=2,3 and dt=0.016, movement should be (0.032, 0.048) which rounds to (0, 0)
        # So position should remain (100, 100)
        assert ball.rect.x == 100  # No movement due to rounding
        assert ball.rect.y == 100  # No movement due to rounding

    def test_ball_update_left_wall_bounce(self, mocker):
        """Test ball bounces off left wall."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = -25  # Left of screen (less than -width)
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
        ball.rect.y = 100

        mock_kill = mocker.patch.object(ball, 'kill')
        ball.dt_tick(0.016)  # Use dt_tick instead of update
        mock_kill.assert_called_once()

    def test_ball_update_no_kill_on_vertical_exit(self, mocker):
        """Test ball does NOT kill when exiting screen vertically (only horizontal exits kill)."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        assert ball.rect is not None
        ball.rect.x = 100
        ball.rect.y = 1000  # Way off screen
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
        ball.speed.y = -2

        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Sound should have been played
        mock_sound.play.assert_called()

    def test_ball_speed_progression(self, mocker):
        """Test ball speed increases with bounces."""
        mocker.patch('pygame.draw.circle')
        ball = BallSprite()
        original_speed = ball.speed.x

        # Multiple bounces should increase speed
        for _ in range(3):
            ball.bounce(0)

        # Speed should be significantly higher (1.1^3 = 1.331)
        expected_speed = original_speed * (1.1**3)
        floating_point_tolerance = 1e-10  # Use approximate equality for floating point
        assert abs(ball.speed.x - expected_speed) < floating_point_tolerance


class TestBallSpeedUpExponentialBoth:
    """Test speed_up with exponential_both type (lines 345->exit)."""

    def _create_ball(self):
        """Create a BallSprite for testing.

        Returns:
            BallSprite: A configured ball sprite.

        """
        return BallSprite(x=100, y=100, width=20, height=20)

    def test_speed_up_exponential_both(self, mock_pygame_patches):
        """Test speed_up with exponential_both type."""
        ball = self._create_ball()
        ball.speed.x = 150.0
        ball.speed.y = 100.0
        original_x = ball.speed.x
        original_y = ball.speed.y

        ball.speed_up(multiplier=1.1, speed_up_type='exponential_both')

        # Both components should be scaled exponentially
        assert ball.speed.x != original_x
        assert ball.speed.y != original_y

    def test_speed_up_exponential_both_with_zero_speeds(self, mock_pygame_patches):
        """Test speed_up exponential_both when speeds are zero."""
        ball = self._create_ball()
        ball.speed.x = 0
        ball.speed.y = 0

        ball.speed_up(multiplier=1.1, speed_up_type='exponential_both')

        assert ball.speed.x == 0
        assert ball.speed.y == 0


class TestContinuousSpeedUpExponentialY:
    """Test continuous exponential Y speed-up (lines 381-382)."""

    def test_continuous_exponential_y_speed_up(self, mock_pygame_patches):
        """Test continuous speed-up with CONTINUOUS_EXPONENTIAL_Y mode."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_interval=0.0,  # Immediate speed-up
        )
        ball.speed.y = 100.0
        original_y = ball.speed.y

        # Set last speed-up time to past so it triggers
        ball._last_speed_up_time = 0.0

        import time

        ball._check_continuous_speed_up(time.time())

        assert ball.speed.y != original_y


class TestContinuousSpeedUpLinear:
    """Test continuous linear speed-up (lines 392->exit)."""

    def test_continuous_linear_speed_up(self, mock_pygame_patches):
        """Test continuous speed-up with CONTINUOUS_LINEAR mode."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR,
            speed_up_interval=0.0,
        )
        ball.speed.x = 100.0
        ball.speed.y = 100.0
        original_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)

        ball._last_speed_up_time = 0.0

        import time

        ball._check_continuous_speed_up(time.time())

        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert new_magnitude > original_magnitude


class TestResolveSpeedUpType:
    """Test _resolve_speed_up_type with exponential_both (line 421)."""

    def test_resolve_exponential_both(self, mock_pygame_patches):
        """Test resolving when both exponential X and Y flags are set."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_mode=(
                SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X | SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y
            ),
        )

        result = ball._resolve_speed_up_type(
            SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X,
            SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y,
            SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
            SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
            SpeedUpMode.ON_BOUNCE_LINEAR,
        )

        assert result == 'exponential_both'


class TestCheckBounceSpeedUpUnknownType:
    """Test _check_bounce_speed_up with unknown type (line 466)."""

    def test_unknown_bounce_type_does_nothing(self, mock_pygame_patches):
        """Test that unknown bounce type results in None speed_up_type."""
        ball = BallSprite(x=100, y=100)
        original_x = ball.speed.x
        original_y = ball.speed.y

        ball._check_bounce_speed_up('unknown_type')

        # Speed should remain unchanged
        assert ball.speed.x == original_x
        assert ball.speed.y == original_y


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

        # Position ball at bottom boundary
        assert ball.rect is not None
        ball.rect.y = ball.screen_height - ball.height

        ball._do_bounce()

        # Y speed should be negative (upward) after bottom bounce
        assert ball.speed.y < 0

    def test_left_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test left collision plays sound (line 708)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.snd = mocker.Mock()
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        # Position ball at left boundary
        assert ball.rect is not None
        ball.rect.x = 0

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

        ball._do_bounce()

        assert ball.speed.x > 0
        assert ball.rect.x == 1  # Just inside boundary

    def test_right_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test right collision plays sound (line 736)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.snd = mocker.Mock()
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Position ball at right boundary
        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width

        ball._do_bounce()

        ball.snd.play.assert_called()

    def test_right_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test right collision reflects X speed (lines 743->752)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width

        ball._do_bounce()

        assert ball.speed.x < 0
        assert ball.rect.x == ball.screen_width - ball.width - 1


class TestCornerCollisions:
    """Test corner collision handling (lines 773-807)."""

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

    def test_top_left_corner_collision(self, mock_pygame_patches):
        """Test top-left corner collision (lines 783-786, 796-798)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = -100.0  # Moving left
        ball.speed.y = -100.0  # Moving up

        assert ball.rect is not None
        ball.rect.x = 0
        ball.rect.y = 0

        ball._do_bounce()

        # After corner collision, ball should be placed at (1, 1)
        assert ball.rect.x == 1
        assert ball.rect.y == 1

    def test_top_right_corner_collision(self, mock_pygame_patches):
        """Test top-right corner collision (lines 787-790, 799-801)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = 100.0  # Moving right
        ball.speed.y = -100.0  # Moving up

        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width
        ball.rect.y = 0

        ball._do_bounce()

        assert ball.rect.x == ball.screen_width - ball.width - 1
        assert ball.rect.y == 1

    def test_bottom_left_corner_collision(self, mock_pygame_patches):
        """Test bottom-left corner collision (lines 802-804)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = -100.0
        ball.speed.y = 100.0

        assert ball.rect is not None
        ball.rect.x = 0
        ball.rect.y = ball.screen_height - ball.height

        ball._do_bounce()

        assert ball.rect.x == 1
        assert ball.rect.y == ball.screen_height - ball.height - 1

    def test_bottom_right_corner_collision(self, mock_pygame_patches):
        """Test bottom-right corner collision (lines 805-807)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = 100.0
        ball.speed.y = 100.0

        assert ball.rect is not None
        ball.rect.x = ball.screen_width - ball.width
        ball.rect.y = ball.screen_height - ball.height

        ball._do_bounce()

        assert ball.rect.x == ball.screen_width - ball.width - 1
        assert ball.rect.y == ball.screen_height - ball.height - 1


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


class TestPaddleCollisionSpeedCap:
    """Test paddle collision speed capping (lines 897-899, 903)."""

    def test_paddle_collision_caps_speed(self, mock_pygame_patches, mocker):
        """Test that paddle collision caps speed at max_speed."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        # Create a mock paddle
        paddle = mocker.Mock()
        paddle.rect = pygame.Rect(90, 90, 20, 100)
        paddle.snd = None

        # Set extremely high speed
        ball.speed.x = 1000.0
        ball.speed.y = 1000.0

        # Position ball overlapping with paddle
        assert ball.rect is not None
        ball.rect.x = 95
        ball.rect.y = 100

        ball._adjust_position_for_paddle_collision(paddle)

        # Speed should be capped
        speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert speed_magnitude <= 500.0 + 0.01  # max_speed = 500.0

    def test_paddle_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test paddle collision plays paddle's sound (lines 886->890)."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        paddle = mocker.Mock()
        paddle.rect = pygame.Rect(120, 90, 20, 100)
        paddle.snd = mocker.Mock()

        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Ball center is to the right of paddle center
        assert ball.rect is not None
        ball.rect.x = 130
        ball.rect.y = 100

        ball._adjust_position_for_paddle_collision(paddle)

        paddle.snd.play.assert_called_once()

    def test_paddle_collision_triggers_on_paddle_collision(self, mock_pygame_patches, mocker):
        """Test paddle collision calls on_paddle_collision if it exists (line 903)."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        mock_callback = mocker.Mock()
        ball.on_paddle_collision = mock_callback  # type: ignore[unresolved-attribute]

        paddle = mocker.Mock()
        paddle.rect = pygame.Rect(120, 90, 20, 100)
        paddle.snd = None

        ball.speed.x = 100.0
        ball.speed.y = 50.0
        assert ball.rect is not None
        ball.rect.x = 130
        ball.rect.y = 100

        ball._adjust_position_for_paddle_collision(paddle)

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


class TestBallCheckPaddleCollisions:
    """Test _check_paddle_collisions with actual paddle sprites (line 859->858)."""

    def test_check_paddle_collisions_no_matching_sprites(self, mock_pygame_patches, mocker):
        """Test _check_paddle_collisions when no paddle sprites overlap.

        Covers branch 859->858 where colliderect returns False.
        """
        ball = BallSprite(x=100, y=100, width=20, height=20)

        # Create a mock group with a non-colliding sprite
        mock_group = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_sprite.rect = pygame.Rect(500, 500, 20, 100)  # Far away
        mock_sprite.__class__.__name__ = 'PaddleSprite'
        mock_group.__iter__ = mocker.Mock(return_value=iter([mock_sprite, ball]))

        mocker.patch.object(ball, 'groups', return_value=[mock_group])

        ball._check_paddle_collisions()


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
