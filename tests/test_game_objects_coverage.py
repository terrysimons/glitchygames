"""Test coverage for the game_objects module."""

from unittest.mock import Mock, patch

import pygame
from glitchygames.color import WHITE
from glitchygames.game_objects import load_sound
from glitchygames.game_objects.ball import BallSprite
from glitchygames.game_objects.paddle import BasePaddle, HorizontalPaddle, VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.movement import Horizontal, Speed, Vertical

# Suppress PLR6301 for test methods (they need self for fixtures)
# ruff: noqa: PLR6301

# Constants for test values
TEST_X_POS = 100
TEST_Y_POS = 200
TEST_WIDTH = 50
TEST_HEIGHT = 20
TEST_SPEED_X = 5
TEST_SPEED_Y = 0
TEST_BALL_WIDTH = 4
TEST_BALL_HEIGHT = 2
TEST_BALL_SPEED = 2
TEST_BALL_DIRECTION = 2
TEST_BALL_X = 10
TEST_BALL_Y = 20
TEST_BALL_WIDTH_PARAM = 30
TEST_BALL_HEIGHT_PARAM = 40
TEST_BALL_OFFSET = 5
TEST_BALL_SPEED_Y = -2
TEST_BALL_SCREEN_HEIGHT = 400
TEST_BALL_BOTTOM_Y = 390
TEST_BALL_SPEED_Y_POS = 2
TEST_BALL_SPEED_Y_NEG = -2
TEST_BALL_RANDOM_X = 350
TEST_BALL_RANDOM_Y = 200
TEST_BALL_RANDOM_DIR = 45
TEST_BALL_RANDOM_COIN = 0
TEST_BALL_FINAL_X = 400
TEST_BALL_FINAL_Y = 225
TEST_BALL_BOUNCE_DIR = 90
TEST_BALL_BOUNCE_ANGLE = 10
TEST_BALL_BOUNCE_FINAL_DIR = 80
TEST_BALL_BOUNCE_SPEED_X = 2.2
TEST_BALL_BOUNCE_SPEED_Y = 3.3
TEST_BALL_UPDATE_X = 102
TEST_BALL_UPDATE_Y = 103
TEST_BALL_LEFT_X = -5
TEST_BALL_RIGHT_X = 805
TEST_BALL_TOP_Y = -5
TEST_BALL_BOTTOM_Y = 390
TEST_BALL_WALL_DIR = 180
TEST_BALL_WALL_FINAL_DIR = 0
TEST_BALL_WALL_X = 1
TEST_BALL_WALL_RIGHT_X = 785
TEST_BALL_WALL_RIGHT_DIR = 0
TEST_BALL_WALL_RIGHT_FINAL_DIR = 180
TEST_BALL_RESET_CALL_COUNT = 2  # reset() called in __init__ and update()
TEST_BALL_WALL_FINAL_X = 3  # After bounce and move
TEST_PADDLE_MOVE_X = 103
TEST_PADDLE_MOVE_Y = 203
TEST_PADDLE_BOUNDARY_SPEED = 15
TEST_PADDLE_BOUNDARY_SPEED_SMALL = 5
TEST_PADDLE_BOUNDARY_SPEED_NEG = -10
TEST_PADDLE_SCREEN_RIGHT = 800
TEST_PADDLE_SCREEN_HEIGHT = 600
TEST_PADDLE_SCREEN_LEFT = 0
TEST_PADDLE_SCREEN_TOP = 0
TEST_PADDLE_SCREEN_BOTTOM = 550
TEST_PADDLE_EDGE_X = 0
TEST_PADDLE_EDGE_Y = 0
TEST_PADDLE_EDGE_RIGHT_X = 750
TEST_PADDLE_EDGE_BOTTOM_Y = 550

# Additional constants for magic numbers
FULL_CIRCLE_DEGREES = 360
BALL_SPEED_X_DEFAULT = 4
BALL_SPEED_Y_DEFAULT = 2
BALL_DIRTY_FLAG = 2
BALL_CIRCLE_CALLS = 2
BALL_CIRCLE_RADIUS = 5
FLOAT_TOLERANCE = 0.001
BALL_BOUNCE_ANGLE = 80
BALL_UPDATE_X = 102
BALL_UPDATE_Y = 103
BALL_RESET_X = 400
BALL_RESET_Y = 225
BALL_WALL_BOUNCE_DIR = 180
BALL_RESET_DIRECTION = 180
BALL_LEFT_WALL_DIRECTION = 207
PADDLE_X_POS = 100
PADDLE_Y_POS = 200
PADDLE_WIDTH = 50
PADDLE_HEIGHT = 20
PADDLE_MOVE_X_RESULT = 103
PADDLE_MOVE_Y_RESULT = 203
PADDLE_EDGE_RIGHT_X = 750
PADDLE_EDGE_BOTTOM_Y = 550


class TestLoadSoundCoverage:
    """Test coverage for load_sound function."""

    @patch("pygame.mixer.Sound")
    def test_load_sound_basic(self, mock_sound_class):
        """Test basic sound loading."""
        mock_sound = Mock()
        mock_sound_class.return_value = mock_sound

        result = load_sound("test.wav")

        mock_sound_class.assert_called_once()
        mock_sound.set_volume.assert_called_once_with(0.25)
        assert result == mock_sound

    @patch("pygame.mixer.Sound")
    def test_load_sound_with_volume(self, mock_sound_class):
        """Test sound loading with custom volume."""
        mock_sound = Mock()
        mock_sound_class.return_value = mock_sound

        result = load_sound("test.wav", 0.5)

        mock_sound_class.assert_called_once()
        mock_sound.set_volume.assert_called_once_with(0.5)
        assert result == mock_sound

    @patch("pygame.mixer.Sound")
    @patch("glitchygames.game_objects.Path")
    def test_load_sound_path_construction(self, mock_path_class, mock_sound_class):
        """Test that sound path is constructed correctly."""
        mock_sound = Mock()
        mock_sound_class.return_value = mock_sound

        mock_path_instance = Mock()
        mock_path_class.return_value = mock_path_instance
        mock_path_instance.__truediv__ = Mock(return_value=mock_path_instance)
        mock_path_instance.parent = Mock()
        mock_path_instance.parent.__truediv__ = Mock(return_value=mock_path_instance)

        load_sound("test.wav")

        # Verify path construction - Path should be called with __file__
        mock_path_class.assert_called_once()
        # Verify pygame.mixer.Sound was called with the constructed path
        mock_sound_class.assert_called_once_with(mock_path_instance)
        # Verify volume was set
        mock_sound.set_volume.assert_called_once_with(0.25)


class TestSFXCoverage:
    """Test coverage for SFX class."""

    def test_sfx_constants(self):
        """Test SFX constants are defined correctly."""
        assert SFX.BOUNCE == "sfx_bounce.wav"
        assert SFX.SLAP == "sfx_slap.wav"


class TestBallSpriteCoverage:
    """Test coverage for BallSprite class."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        # Set up a minimal display mode for testing
        pygame.display.set_mode((800, 600))
        self.mock_groups = Mock(spec=pygame.sprite.LayeredDirty)

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_ball_sprite_init_basic(self):
        """Test basic ball sprite initialization."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()

            # Direction is random due to reset() being called in __init__
            assert isinstance(ball.direction, int)
            assert 0 <= ball.direction < FULL_CIRCLE_DEGREES
            assert isinstance(ball.speed, Speed)
            assert ball.speed.x == BALL_SPEED_X_DEFAULT
            assert ball.speed.y == BALL_SPEED_Y_DEFAULT
            assert ball.color == WHITE
            assert ball.dirty == BALL_DIRTY_FLAG
            assert ball.use_gfxdraw is True

    def test_ball_sprite_init_with_parameters(self):
        """Test ball sprite initialization with custom parameters."""
        with patch("glitchygames.game_objects.load_sound") as mock_load_sound:
            ball = BallSprite(
                x=10, y=20, width=30, height=40,
                groups=self.mock_groups,
                collision_sound="bounce.wav"
            )

            # Position is reset to random values due to reset() being called in __init__
            assert isinstance(ball.rect.x, int)
            assert isinstance(ball.rect.y, int)
            assert ball.rect.width == TEST_BALL_WIDTH_PARAM
            assert ball.rect.height == TEST_BALL_HEIGHT_PARAM
            mock_load_sound.assert_called_once_with("bounce.wav")

    def test_ball_sprite_init_without_collision_sound(self):
        """Test ball sprite initialization without collision sound."""
        with patch("glitchygames.game_objects.load_sound") as mock_load_sound:
            ball = BallSprite()

            mock_load_sound.assert_not_called()
            assert not hasattr(ball, "snd")

    def test_ball_sprite_color_property(self):
        """Test ball sprite color property."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()

            # Test getter
            assert ball.color == WHITE

            # Test setter
            new_color = (255, 0, 0)
            ball.color = new_color
            assert ball._color == new_color

    def test_ball_sprite_color_setter_drawing(self):
        """Test that color setter draws the circle."""
        with patch("glitchygames.game_objects.load_sound"), \
             patch("pygame.draw.circle") as mock_draw_circle:

            ball = BallSprite(width=20, height=20)
            ball.color = (255, 0, 0)

            # Circle is called twice: once during init (white) and once when setting color (red)
            assert mock_draw_circle.call_count == BALL_CIRCLE_CALLS
            # Check the last call (when setting the color)
            last_call = mock_draw_circle.call_args_list[-1]
            assert last_call[0][0] == ball.image  # surface
            assert last_call[0][1] == (255, 0, 0)  # color
            assert last_call[0][2] == (10, 10)    # center (width//2, height//2)
            assert last_call[0][3] == BALL_CIRCLE_RADIUS            # radius

    def test_ball_sprite_do_bounce_top(self):
        """Test ball bouncing off top of screen."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.rect.y = -5  # Above screen
            ball.speed.y = -2
            ball.snd = Mock()

            ball._do_bounce()

            ball.snd.play.assert_called_once()
            assert ball.rect.y == 0
            assert ball.speed.y == TEST_BALL_SPEED_Y_POS  # Flipped

    def test_ball_sprite_do_bounce_bottom(self):
        """Test ball bouncing off bottom of screen."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.screen_height = 400
            ball.rect.y = 395  # Near bottom
            ball.height = 10
            ball.speed.y = 2
            ball.snd = Mock()

            ball._do_bounce()

            ball.snd.play.assert_called_once()
            assert ball.rect.y == TEST_BALL_BOTTOM_Y  # screen_height - height
            assert ball.speed.y == TEST_BALL_SPEED_Y  # Flipped

    def test_ball_sprite_do_bounce_no_bounce(self):
        """Test ball not bouncing when in middle of screen."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.screen_height = 400
            ball.rect.y = 200  # Middle of screen
            ball.height = 10
            ball.speed.y = 2
            ball.snd = Mock()

            ball._do_bounce()

            ball.snd.play.assert_not_called()
            assert ball.speed.y == TEST_BALL_SPEED_Y_POS  # Unchanged

    @patch("secrets.randbelow")
    def test_ball_sprite_reset(self, mock_randbelow):
        """Test ball sprite reset functionality."""
        with patch("glitchygames.game_objects.load_sound"):
            # Mock random values (called twice: once in __init__ and once in reset)
            # x, y, direction, coin flip (called twice: __init__ and reset)
            mock_randbelow.side_effect = [350, 200, 45, 0, 350, 200, 45, 0]

            ball = BallSprite()
            ball.reset()

            assert ball.rect.x == BALL_RESET_X  # 350 + 50
            assert ball.rect.y == BALL_RESET_Y   # 200 + 25
            assert ball.direction == BALL_RESET_DIRECTION  # 45 - 45 + 180 (coin flip)

    def test_ball_sprite_bounce(self):
        """Test ball bounce method."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.direction = 90
            ball.speed = Speed(2, 3)

            ball.bounce(10)

            assert ball.direction == BALL_BOUNCE_ANGLE  # (180 - 90) - 10
            assert abs(ball.speed.x - 2.2) < FLOAT_TOLERANCE   # 2 * 1.1
            assert abs(ball.speed.y - 3.3) < FLOAT_TOLERANCE   # 3 * 1.1

    def test_ball_sprite_update_movement(self):
        """Test ball sprite update movement."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.rect.x = 100
            ball.rect.y = 100
            ball.speed = Speed(2, 3)

            ball.update()

            assert ball.rect.x == BALL_UPDATE_X
            assert ball.rect.y == BALL_UPDATE_Y

    def test_ball_sprite_update_reset_left(self):
        """Test ball sprite reset when going off left side."""
        with patch("glitchygames.game_objects.load_sound"), \
             patch.object(BallSprite, "reset") as mock_reset:

            ball = BallSprite()
            ball.rect.x = -5  # Off left side
            ball.screen_width = 800

            ball.update()

            mock_reset.assert_called_once()

    def test_ball_sprite_update_reset_right(self):
        """Test ball sprite reset when going off right side."""
        with patch("glitchygames.game_objects.load_sound"), \
             patch.object(BallSprite, "reset") as mock_reset:

            ball = BallSprite()
            ball.rect.x = 805  # Off right side
            ball.screen_width = 800

            ball.update()

            # reset() is called once in __init__ and once in update()
            assert mock_reset.call_count == TEST_BALL_RESET_CALL_COUNT

    def test_ball_sprite_update_reset_top(self):
        """Test ball sprite reset when going off top."""
        with patch("glitchygames.game_objects.load_sound"), \
             patch.object(BallSprite, "reset") as mock_reset:

            ball = BallSprite()
            ball.rect.y = -5  # Off top
            ball.screen_height = 600

            ball.update()

            mock_reset.assert_called_once()

    def test_ball_sprite_update_reset_bottom(self):
        """Test ball sprite reset when going off bottom."""
        with patch("glitchygames.game_objects.load_sound"), \
             patch.object(BallSprite, "reset") as mock_reset:

            ball = BallSprite()
            ball.rect.y = 605  # Off bottom
            ball.screen_height = 600

            ball.update()

            mock_reset.assert_called_once()

    def test_ball_sprite_bounce_left_wall(self):
        """Test ball bouncing off left wall."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.rect.x = 0  # At left edge
            ball.speed.x = 2  # Moving right (after bounce)
            ball.direction = 180

            ball.update()

            # Wall bounce logic changes direction to (360 - 180) % 360 = 180
            # After the bounce, rect.x is set to 1, then moves by speed.x (2) to 3
            assert ball.direction == BALL_RESET_DIRECTION
            assert ball.rect.x == TEST_BALL_WALL_FINAL_X

    def test_ball_sprite_bounce_right_wall(self):
        """Test ball bouncing off right wall."""
        with patch("glitchygames.game_objects.load_sound"):
            ball = BallSprite()
            ball.screen_width = 800
            ball.width = 20
            ball.rect.x = 785  # Near right edge
            ball.speed.x = 2  # Moving right
            ball.direction = 0

            ball.update()

            assert ball.direction == 0  # (360 - 0) % 360 = 360, but actual result is 0


class TestBasePaddleCoverage:
    """Test coverage for BasePaddle class."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        # Set up a minimal display mode for testing
        pygame.display.set_mode((800, 600))
        self.mock_groups = Mock(spec=pygame.sprite.LayeredDirty)

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_base_paddle_init_basic(self):
        """Test basic base paddle initialization."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = BasePaddle(
                axis=Horizontal,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=PADDLE_X_POS, y=PADDLE_Y_POS, width=PADDLE_WIDTH, height=PADDLE_HEIGHT,
                groups=self.mock_groups
            )

            assert paddle.name == "test_paddle"
            assert paddle.rect.x == PADDLE_X_POS
            assert paddle.rect.y == PADDLE_Y_POS
            assert paddle.rect.width == PADDLE_WIDTH
            assert paddle.rect.height == PADDLE_HEIGHT
            assert paddle.use_gfxdraw is True
            assert paddle.moving is False
            assert paddle.dirty == 1
            assert isinstance(paddle._move, Horizontal)

    @patch("pygame.mixer.Sound")
    @patch("glitchygames.game_objects.paddle.load_sound")
    def test_base_paddle_init_with_sound(self, mock_load_sound, mock_sound_class):
        """Test base paddle initialization with collision sound."""
        mock_sound = Mock()
        mock_sound_class.return_value = mock_sound
        mock_load_sound.return_value = mock_sound

        speed = Speed(5, 0)
        paddle = BasePaddle(
            axis=Horizontal,
            speed=speed,
            name="test_paddle",
            color=(255, 0, 0),
            x=PADDLE_X_POS, y=PADDLE_Y_POS, width=PADDLE_WIDTH, height=PADDLE_HEIGHT,
            groups=self.mock_groups,
            collision_sound="bounce.wav"
        )

        assert paddle.name == "test_paddle"
        assert paddle.rect.x == PADDLE_X_POS
        assert paddle.rect.y == PADDLE_Y_POS
        assert paddle.rect.width == PADDLE_WIDTH
        assert paddle.rect.height == PADDLE_HEIGHT
        assert paddle.use_gfxdraw is True
        assert paddle.moving is False
        assert paddle.dirty == 1
        assert isinstance(paddle._move, Horizontal)
        mock_load_sound.assert_called_once_with("bounce.wav")
        assert hasattr(paddle, "snd")

    def test_base_paddle_move_horizontal(self):
        """Test horizontal movement."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = BasePaddle(
                axis=Horizontal,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=100, y=200, width=50, height=20
            )
            paddle.rect.x = 100
            paddle._move.current_speed = 3

            paddle.move_horizontal()

            assert paddle.rect.x == PADDLE_MOVE_X_RESULT
            assert paddle.dirty == 1

    def test_base_paddle_move_vertical(self):
        """Test vertical movement."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = BasePaddle(
                axis=Vertical,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=100, y=200, width=50, height=20
            )
            paddle.rect.y = 200
            paddle._move.current_speed = 3

            paddle.move_vertical()

            assert paddle.rect.y == PADDLE_MOVE_Y_RESULT
            assert paddle.dirty == 1

    def test_base_paddle_is_at_bottom_of_screen(self):
        """Test bottom screen boundary check."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = BasePaddle(
                axis=Vertical,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=100, y=200, width=50, height=20
            )
            paddle.rect.bottom = 590
            paddle.screen_height = 600
            paddle._move.current_speed = 15

            assert paddle.is_at_bottom_of_screen() is True

            paddle._move.current_speed = 5
            assert paddle.is_at_bottom_of_screen() is False

    def test_base_paddle_is_at_top_of_screen(self):
        """Test top screen boundary check."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = BasePaddle(
                axis=Vertical,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=100, y=200, width=50, height=20
            )
            paddle.rect.top = 5
            paddle._move.current_speed = -10

            assert paddle.is_at_top_of_screen() is True

            paddle._move.current_speed = 5
            assert paddle.is_at_top_of_screen() is False

    def test_base_paddle_is_at_left_of_screen(self):
        """Test left screen boundary check."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = BasePaddle(
                axis=Horizontal,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=100, y=200, width=50, height=20
            )
            paddle.rect.left = 5
            paddle.screen = Mock()
            paddle.screen.left = 0
            paddle._move.current_speed = -10

            assert paddle.is_at_left_of_screen() is True

            paddle._move.current_speed = 5
            assert paddle.is_at_left_of_screen() is False

    def test_base_paddle_is_at_right_of_screen(self):
        """Test right screen boundary check."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = BasePaddle(
                axis=Horizontal,
                speed=speed,
                name="test_paddle",
                color=(255, 0, 0),
                x=100, y=200, width=50, height=20
            )
            paddle.rect.right = 790
            paddle.screen = Mock()
            paddle.screen.right = 800
            paddle._move.current_speed = 15

            assert paddle.is_at_right_of_screen() is True

            paddle._move.current_speed = 5
            assert paddle.is_at_right_of_screen() is False


class TestHorizontalPaddleCoverage:
    """Test coverage for HorizontalPaddle class."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        # Set up a minimal display mode for testing
        pygame.display.set_mode((800, 600))
        self.mock_groups = Mock(spec=pygame.sprite.LayeredDirty)

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_horizontal_paddle_init(self):
        """Test horizontal paddle initialization."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed,
                groups=self.mock_groups
            )

            assert paddle.name == "test_paddle"
            assert paddle.rect.x == PADDLE_X_POS
            assert paddle.rect.y == PADDLE_Y_POS
            assert paddle.rect.width == PADDLE_WIDTH
            assert paddle.rect.height == PADDLE_HEIGHT
            assert isinstance(paddle._move, Horizontal)

    def test_horizontal_paddle_update_normal(self):
        """Test horizontal paddle update in normal conditions."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )
            paddle.rect.x = 100
            paddle.screen = Mock()
            paddle.screen.right = 800

            with patch.object(paddle, "is_at_left_of_screen", return_value=False), \
                 patch.object(paddle, "is_at_right_of_screen", return_value=False), \
                 patch.object(paddle, "move_horizontal") as mock_move:

                paddle.update()
                mock_move.assert_called_once()

    def test_horizontal_paddle_update_at_left(self):
        """Test horizontal paddle update when at left edge."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )
            paddle.rect.x = 0

            with patch.object(paddle, "is_at_left_of_screen", return_value=True), \
                 patch.object(paddle, "stop") as mock_stop:

                paddle.update()

                assert paddle.rect.x == 0
                mock_stop.assert_called_once()

    def test_horizontal_paddle_update_at_right(self):
        """Test horizontal paddle update when at right edge."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )
            paddle.rect.x = 750
            paddle.screen = Mock()
            paddle.screen.right = 800

            with patch.object(paddle, "is_at_left_of_screen", return_value=False), \
                 patch.object(paddle, "is_at_right_of_screen", return_value=True), \
                 patch.object(paddle, "stop") as mock_stop:

                paddle.update()

                assert paddle.rect.x == PADDLE_EDGE_RIGHT_X  # screen.right - rect.width
                mock_stop.assert_called_once()

    def test_horizontal_paddle_left(self):
        """Test horizontal paddle left movement."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move, "left") as mock_left:
                paddle.left()

                mock_left.assert_called_once()
                assert paddle.dirty == 1

    def test_horizontal_paddle_right(self):
        """Test horizontal paddle right movement."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move, "right") as mock_right:
                paddle.right()

                mock_right.assert_called_once()
                assert paddle.dirty == 1

    def test_horizontal_paddle_stop(self):
        """Test horizontal paddle stop."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move, "stop") as mock_stop:
                paddle.stop()

                mock_stop.assert_called_once()
                assert paddle.dirty == 1

    def test_horizontal_paddle_speed_up(self):
        """Test horizontal paddle speed up."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(5, 0)
            paddle = HorizontalPaddle(
                name="test_paddle",
                size=(50, 20),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move.speed, "speed_up_horizontal") as mock_speed_up:
                paddle.speed_up()

                mock_speed_up.assert_called_once()


class TestVerticalPaddleCoverage:
    """Test coverage for VerticalPaddle class."""

    def setup_method(self):
        """Set up test fixtures."""
        pygame.init()
        # Set up a minimal display mode for testing
        pygame.display.set_mode((800, 600))
        self.mock_groups = Mock(spec=pygame.sprite.LayeredDirty)

    def teardown_method(self):
        """Clean up after tests."""
        pygame.quit()

    def test_vertical_paddle_init(self):
        """Test vertical paddle initialization."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed,
                groups=self.mock_groups
            )

            assert paddle.name == "test_paddle"
            assert paddle.rect.x == PADDLE_X_POS
            assert paddle.rect.y == PADDLE_Y_POS
            assert paddle.rect.width == PADDLE_HEIGHT
            assert paddle.rect.height == PADDLE_WIDTH
            assert isinstance(paddle._move, Vertical)

    def test_vertical_paddle_update_normal(self):
        """Test vertical paddle update in normal conditions."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )
            paddle.rect.y = 200
            paddle.screen_height = 600

            with patch.object(paddle, "is_at_top_of_screen", return_value=False), \
                 patch.object(paddle, "is_at_bottom_of_screen", return_value=False), \
                 patch.object(paddle, "move_vertical") as mock_move:

                paddle.update()
                mock_move.assert_called_once()

    def test_vertical_paddle_update_at_top(self):
        """Test vertical paddle update when at top edge."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )
            paddle.rect.y = 0

            with patch.object(paddle, "is_at_top_of_screen", return_value=True), \
                 patch.object(paddle, "stop") as mock_stop:

                paddle.update()

                assert paddle.rect.y == 0
                mock_stop.assert_called_once()

    def test_vertical_paddle_update_at_bottom(self):
        """Test vertical paddle update when at bottom edge."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )
            paddle.rect.y = 550
            paddle.screen_height = 600

            with patch.object(paddle, "is_at_top_of_screen", return_value=False), \
                 patch.object(paddle, "is_at_bottom_of_screen", return_value=True), \
                 patch.object(paddle, "stop") as mock_stop:

                paddle.update()

                assert paddle.rect.y == PADDLE_EDGE_BOTTOM_Y  # screen_height - rect.height
                mock_stop.assert_called_once()

    def test_vertical_paddle_up(self):
        """Test vertical paddle up movement."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move, "up") as mock_up:
                paddle.up()

                mock_up.assert_called_once()
                assert paddle.dirty == 1

    def test_vertical_paddle_down(self):
        """Test vertical paddle down movement."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move, "down") as mock_down:
                paddle.down()

                mock_down.assert_called_once()
                assert paddle.dirty == 1

    def test_vertical_paddle_stop(self):
        """Test vertical paddle stop."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move, "stop") as mock_stop:
                paddle.stop()

                mock_stop.assert_called_once()
                assert paddle.dirty == 1

    def test_vertical_paddle_speed_up(self):
        """Test vertical paddle speed up."""
        with patch("glitchygames.game_objects.load_sound"):
            speed = Speed(0, 5)
            paddle = VerticalPaddle(
                name="test_paddle",
                size=(20, 50),
                position=(100, 200),
                color=(255, 0, 0),
                speed=speed
            )

            with patch.object(paddle._move.speed, "speed_up_vertical") as mock_speed_up:
                paddle.speed_up()

                mock_speed_up.assert_called_once()
