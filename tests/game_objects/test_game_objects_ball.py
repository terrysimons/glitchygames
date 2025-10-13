"""Tests for BallSprite game object."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


class TestBallSpriteInitialization(unittest.TestCase):
    """Test BallSprite initialization and basic properties."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

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
        assert ball.speed.x == SPEED_2  # Updated default speed
        assert ball.speed.y == SPEED_1  # Updated default speed
        assert ball.dirty == SPEED_2

    def test_ball_sprite_initialization_custom(self):
        """Test BallSprite initialization with custom parameters."""
        groups = Mock()
        with patch("pygame.mixer.Sound"):
            ball = BallSprite(
                x=100,
                y=200,
                width=30,
                height=30,
                groups=groups,
                collision_sound="test.wav"
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

    def test_ball_sprite_initialization_with_collision_sound(self):
        """Test BallSprite initialization with collision sound."""
        with patch("pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound

            ball = BallSprite(collision_sound="bounce.wav")

            mock_sound_class.assert_called_once()
            assert hasattr(ball, "snd")
            assert ball.snd == mock_sound

    def test_ball_sprite_initialization_without_collision_sound(self):
        """Test BallSprite initialization without collision sound."""
        ball = BallSprite()

        # Should not have snd attribute when no collision sound provided
        assert not hasattr(ball, "snd")


class TestBallSpriteColor(unittest.TestCase):
    """Test BallSprite color property and setter."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_ball_color_getter(self):
        """Test ball color getter returns correct color."""
        ball = BallSprite()
        ball._color = (255, 0, 0)

        assert ball.color == (255, 0, 0)

    def test_ball_color_setter(self):
        """Test ball color setter updates color and redraws."""
        with patch("pygame.draw.circle") as mock_draw_circle:
            ball = BallSprite()
            ball.width = 20
            ball.height = 20

            ball.color = (0, 255, 0)

            assert ball._color == (0, 255, 0)
            # draw.circle is called twice - once during initialization and once in setter
            assert mock_draw_circle.call_count == SPEED_2
            # Check the last call (the setter call)
            mock_draw_circle.assert_any_call(
                ball.image,
                (0, 255, 0),
                (10, 10),
                5,
                0
            )


class TestBallSpriteBounce(unittest.TestCase):
    """Test BallSprite bounce functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_do_bounce_top_wall(self):
        """Test ball bounces off top wall."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.y = -5  # Above screen
            ball.speed.y = -2
            ball.snd = Mock()

            ball._do_bounce()

            assert ball.rect.y == 0
            assert ball.speed.y == SPEED_2  # Reversed
            ball.snd.play.assert_called_once()

    def test_do_bounce_bottom_wall(self):
        """Test ball bounces off bottom wall."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.screen_height = 600
            ball.height = 20
            ball.rect.y = 590  # Below screen
            ball.speed.y = 2
            ball.snd = Mock()

            ball._do_bounce()

            assert ball.rect.y == Y_580  # screen_height - height
            assert ball.speed.y == SPEED_NEG_2  # Reversed
            ball.snd.play.assert_called_once()

    def test_do_bounce_no_sound(self):
        """Test ball bounces without sound when no sound loaded."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.y = -5
            ball.speed.y = -2
            # No snd attribute set

            ball._do_bounce()

            assert ball.rect.y == 0
            assert ball.speed.y == SPEED_2

    def test_do_bounce_no_collision(self):
        """Test ball doesn't bounce when not at walls."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.y = 100
            ball.speed.y = 2
            original_speed = ball.speed.y

            ball._do_bounce()

            # Speed should remain unchanged
            assert ball.speed.y == original_speed


class TestBallSpriteReset(unittest.TestCase):
    """Test BallSprite reset functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_ball_reset_position(self):
        """Test ball reset sets random position within bounds."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            original_x = ball.rect.x
            original_y = ball.rect.y

            ball.reset()

            # Position should be within expected bounds
            assert POS_50 <= ball.rect.x <= POS_749
            assert POS_25 <= ball.rect.y <= POS_399
            # Should be different from original (very likely)
            assert ball.rect.x != original_x or ball.rect.y != original_y

    def test_ball_reset_direction(self):
        """Test ball reset sets random direction."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            original_direction = ball.direction

            ball.reset()

            # Direction should be in 0-360 range
            assert 0 <= ball.direction <= DIRECTION_360
            # Should be different from original (very likely)
            assert ball.direction != original_direction

    def test_ball_reset_direction_range(self):
        """Test ball reset direction is within expected range."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()

            # Test multiple resets to ensure direction is in valid range
            for _ in range(10):
                ball.reset()
                assert 0 <= ball.direction <= DIRECTION_360


class TestBallSpriteBounceMethod(unittest.TestCase):
    """Test BallSprite bounce method."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_ball_bounce_direction_change(self):
        """Test ball bounce changes direction correctly."""
        with patch("pygame.draw.circle"):
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

    def test_ball_bounce_speed_increase(self):
        """Test ball bounce increases speed."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            original_speed_x = ball.speed.x
            original_speed_y = ball.speed.y

            ball.bounce(0)

            assert ball.speed.x == original_speed_x * MULTIPLIER_1_1
            assert ball.speed.y == original_speed_y * MULTIPLIER_1_1

    def test_ball_bounce_direction_wrapping(self):
        """Test ball bounce handles direction wrapping correctly."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.direction = 200

            ball.bounce(0)

            # (180 - 200) % 360 = 340
            assert ball.direction == DIRECTION_340


class TestBallSpriteUpdate(unittest.TestCase):
    """Test BallSprite update functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_ball_update_movement(self):
        """Test ball update moves the ball."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.x = 100
            ball.rect.y = 100
            ball.speed.x = 2
            ball.speed.y = 3

            ball.update()

            assert ball.rect.x == POS_102
            assert ball.rect.y == POS_103

    def test_ball_update_left_wall_bounce(self):
        """Test ball bounces off left wall."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.x = -5  # Left of screen
            ball.direction = 45
            ball.speed.x = -2

            with patch.object(ball, "reset") as mock_reset:
                ball.update()

                # Should reverse direction and set x to 1, then move by speed.x
                # Since x becomes negative after movement, reset() should be called
                mock_reset.assert_called_once()
                assert ball.direction == DIRECTION_315  # (360 - 45) % 360

    def test_ball_update_right_wall_bounce(self):
        """Test ball bounces off right wall."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.screen_width = 800
            ball.width = 20
            ball.rect.x = 810  # Right of screen
            ball.direction = 45
            ball.speed.x = 2

            with patch.object(ball, "reset") as mock_reset:
                ball.update()

                # Should reverse direction and then reset() is called due to off-screen
                mock_reset.assert_called_once()
                assert ball.direction == DIRECTION_315  # (360 - 45) % 360

    def test_ball_update_reset_on_exit(self):
        """Test ball resets when exiting screen."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.x = 1000  # Way off screen
            ball.rect.y = 100

            with patch.object(ball, "reset") as mock_reset:
                ball.update()
                mock_reset.assert_called_once()

    def test_ball_update_reset_on_vertical_exit(self):
        """Test ball resets when exiting screen vertically."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            ball.rect.x = 100
            ball.rect.y = 1000  # Way off screen
            ball.screen_height = 600  # Set screen height so ball is off screen
            ball.speed.y = 0  # Don't move vertically to ensure reset is called

            # Mock _do_bounce to not interfere with the test
            with (
                patch.object(ball, "_do_bounce"),
                patch.object(ball, "reset") as mock_reset,
            ):
                ball.update()
                mock_reset.assert_called_once()

    def test_ball_update_calls_do_bounce(self):
        """Test ball update calls _do_bounce."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()

            with patch.object(ball, "_do_bounce") as mock_do_bounce:
                ball.update()
                mock_do_bounce.assert_called_once()


class TestBallSpriteIntegration(unittest.TestCase):
    """Test BallSprite integration scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all patchers
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_ball_full_game_cycle(self):
        """Test complete ball game cycle."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()

            # Initial state
            assert ball.dirty == SPEED_2

            # Update should move ball
            original_x = ball.rect.x
            original_y = ball.rect.y
            ball.update()

            # Ball should have moved
            assert ball.rect.x != original_x or ball.rect.y != original_y

    def test_ball_with_sound_integration(self):
        """Test ball with sound integration."""
        with (
            patch("pygame.draw.circle"),
            patch(
                "glitchygames.game_objects.ball.game_objects.load_sound"
            ) as mock_load_sound,
        ):
            mock_sound = Mock()
            mock_load_sound.return_value = mock_sound

            ball = BallSprite(collision_sound="bounce.wav")
            ball.rect.y = -5  # Trigger top wall bounce
            ball.speed.y = -2

            ball.update()

            # Sound should have been played
            mock_sound.play.assert_called()

    def test_ball_speed_progression(self):
        """Test ball speed increases with bounces."""
        with patch("pygame.draw.circle"):
            ball = BallSprite()
            original_speed = ball.speed.x

            # Multiple bounces should increase speed
            for _ in range(3):
                ball.bounce(0)

            # Speed should be significantly higher (1.1^3 = 1.331)
            expected_speed = original_speed * (1.1 ** 3)
            assert ball.speed.x == expected_speed
