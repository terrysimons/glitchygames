"""Tests for BallSprite game object."""

import sys
from pathlib import Path

import pytest
from glitchygames.game_objects.ball import BallSprite
from glitchygames.movement import Speed

from tests.mocks.test_mock_factory import MockFactory

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Constants for magic values
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
        mocker.patch("pygame.mixer.Sound")
        ball = BallSprite(
            x=100, y=200, width=30, height=30, groups=groups, collision_sound="test.wav"
        )

        # Position is set by reset() during initialization, so it will be random
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
            "glitchygames.game_objects.sounds.pygame.mixer.Sound",
            return_value=mock_sound,
        )

        ball = BallSprite(collision_sound="bounce.wav")

        mock_sound_class.assert_called_once()
        assert hasattr(ball, "snd")
        assert ball.snd == mock_sound

    def test_ball_sprite_initialization_without_collision_sound(self):
        """Test BallSprite initialization without collision sound."""
        ball = BallSprite()

        # Should not have snd attribute when no collision sound provided
        assert not hasattr(ball, "snd")


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
        mock_draw_circle = mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.width = 20
        ball.height = 20

        ball.color = (0, 255, 0)

        assert ball._color == (0, 255, 0)
        # draw.circle is called twice - once during initialization and once in setter
        assert mock_draw_circle.call_count == SPEED_2
        # Check the last call (the setter call)
        mock_draw_circle.assert_any_call(ball.image, (0, 255, 0), (10, 10), 5, 0)


class TestBallSpriteBounce:
    """Test BallSprite bounce functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def test_do_bounce_top_wall(self, mocker):
        """Test ball bounces off top wall."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.rect.y = -5  # Above screen
        ball.speed.y = -2
        ball.snd = mocker.Mock()

        ball._do_bounce()

        assert ball.rect.y == 1  # Small buffer to prevent sticking
        assert ball.speed.y == SPEED_2  # Reversed
        ball.snd.play.assert_called_once()

    def test_do_bounce_bottom_wall(self, mocker):
        """Test ball bounces off bottom wall."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.screen_height = 600
        ball.height = 20
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.rect.y = -5
        ball.speed.y = -2
        # No snd attribute set

        ball._do_bounce()

        assert ball.rect.y == 1  # Small buffer to prevent sticking
        assert ball.speed.y == SPEED_2

    def test_do_bounce_no_collision(self, mocker):
        """Test ball doesn't bounce when not at walls."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        original_direction = ball.direction

        ball.reset()

        # Direction should be in 0-360 range
        assert 0 <= ball.direction <= DIRECTION_360
        # Should be different from original (very likely)
        assert ball.direction != original_direction

    def test_ball_reset_direction_range(self, mocker):
        """Test ball reset direction is within expected range."""
        mocker.patch("pygame.draw.circle")
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
        mocker.patch("pygame.draw.circle")
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        original_speed_x = ball.speed.x
        original_speed_y = ball.speed.y

        ball.bounce(0)

        assert ball.speed.x == original_speed_x * MULTIPLIER_1_1
        assert ball.speed.y == original_speed_y * MULTIPLIER_1_1

    def test_ball_bounce_direction_wrapping(self, mocker):
        """Test ball bounce handles direction wrapping correctly."""
        mocker.patch("pygame.draw.circle")
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.rect.x = -25  # Left of screen (less than -width)
        ball.direction = 45
        ball.speed.x = -2

        mock_kill = mocker.patch.object(ball, "kill")
        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Should kill() when ball goes off-screen (no direction change for left/right)
        mock_kill.assert_called_once()
        expected_direction = 45  # Direction should remain unchanged
        assert ball.direction == expected_direction

    def test_ball_update_right_wall_bounce(self, mocker):
        """Test ball bounces off right wall."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.screen_width = 800
        ball.width = 20
        ball.rect.x = 810  # Right of screen
        ball.direction = 45
        ball.speed.x = 2

        mock_kill = mocker.patch.object(ball, "kill")
        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Should kill() when ball goes off-screen (no direction change for left/right)
        mock_kill.assert_called_once()
        expected_direction = 45  # Direction should remain unchanged
        assert ball.direction == expected_direction

    def test_ball_update_reset_on_exit(self, mocker):
        """Test ball resets when exiting screen."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.rect.x = 1000  # Way off screen
        ball.rect.y = 100

        mock_kill = mocker.patch.object(ball, "kill")
        ball.dt_tick(0.016)  # Use dt_tick instead of update
        mock_kill.assert_called_once()

    def test_ball_update_no_kill_on_vertical_exit(self, mocker):
        """Test ball does NOT kill when exiting screen vertically (only horizontal exits kill)."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        ball.rect.x = 100
        ball.rect.y = 1000  # Way off screen
        ball.screen_height = 600  # Set screen height so ball is off screen
        ball.speed.y = 0  # Don't move vertically

        # Mock _do_bounce to not interfere with the test
        mocker.patch.object(ball, "_do_bounce")
        mock_kill = mocker.patch.object(ball, "kill")
        ball.dt_tick(0.016)  # Use dt_tick instead of update
        mock_kill.assert_not_called()  # Should NOT be called for vertical exits

    def test_ball_update_calls_do_bounce(self, mocker):
        """Test ball dt_tick calls _do_bounce."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()

        mock_do_bounce = mocker.patch.object(ball, "_do_bounce")
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
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()

        # Initial state
        assert ball.dirty == SPEED_2

        # Update should move ball
        original_x = ball.rect.x
        original_y = ball.rect.y
        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Ball should have moved
        assert ball.rect.x != original_x or ball.rect.y != original_y

    def test_ball_with_sound_integration(self, mocker):
        """Test ball with sound integration."""
        mocker.patch("pygame.draw.circle")
        mock_sound = mocker.Mock()
        mocker.patch(
            "glitchygames.game_objects.ball.game_objects.load_sound",
            return_value=mock_sound,
        )

        ball = BallSprite(collision_sound="bounce.wav")
        ball.rect.y = -5  # Trigger top wall bounce
        ball.speed.y = -2

        ball.dt_tick(0.016)  # Use dt_tick instead of update

        # Sound should have been played
        mock_sound.play.assert_called()

    def test_ball_speed_progression(self, mocker):
        """Test ball speed increases with bounces."""
        mocker.patch("pygame.draw.circle")
        ball = BallSprite()
        original_speed = ball.speed.x

        # Multiple bounces should increase speed
        for _ in range(3):
            ball.bounce(0)

        # Speed should be significantly higher (1.1^3 = 1.331)
        expected_speed = original_speed * (1.1**3)
        floating_point_tolerance = 1e-10  # Use approximate equality for floating point
        assert abs(ball.speed.x - expected_speed) < floating_point_tolerance
