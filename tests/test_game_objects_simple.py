"""Simple test coverage for the game_objects module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.ball import BallSprite
from glitchygames.game_objects.paddle import HorizontalPaddle, VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.speed import Speed
from glitchygames.movement.vertical import Vertical

from test_mock_factory import MockFactory

# Constants for test values
DEFAULT_INCREMENT = 0.2
CUSTOM_INCREMENT = 0.5
SPEED_X_5 = 5
SPEED_Y_10 = 10
SPEED_X_2 = 2
SPEED_Y_3 = 3
SPEED_X_2_5 = 2.5
SPEED_Y_3_5 = 3.5
SPEED_X_NEGATIVE_2_5 = -2.5
SPEED_Y_NEGATIVE_3_5 = -3.5
SPEED_X_NEGATIVE_5 = -5
SPEED_Y_5 = 5
SPEED_X_10 = 10
SPEED_Y_10 = 10


class TestLoadSound(unittest.TestCase):
    """Test load_sound function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_sound_file = "test_sound.wav"
        self.test_volume = 0.5

    @patch("pygame.mixer.Sound")
    @patch("pathlib.Path.__truediv__")
    def test_load_sound_with_volume(self, mock_path_div, mock_sound):
        """Test load_sound with custom volume."""
        mock_sound_instance = Mock()
        mock_sound.return_value = mock_sound_instance
        mock_path_div.return_value = Path("test_path")

        result = load_sound(self.test_sound_file, self.test_volume)

        mock_sound.assert_called_once()
        mock_sound_instance.set_volume.assert_called_once_with(self.test_volume)
        assert result == mock_sound_instance

    @patch("pygame.mixer.Sound")
    @patch("pathlib.Path.__truediv__")
    def test_load_sound_default_volume(self, mock_path_div, mock_sound):
        """Test load_sound with default volume."""
        mock_sound_instance = Mock()
        mock_sound.return_value = mock_sound_instance
        mock_path_div.return_value = Path("test_path")

        result = load_sound(self.test_sound_file)

        mock_sound.assert_called_once()
        mock_sound_instance.set_volume.assert_called_once_with(0.25)
        assert result == mock_sound_instance

    @patch("pygame.mixer.Sound")
    @patch("pathlib.Path.__truediv__")
    def test_load_sound_path_construction(self, mock_path_div, mock_sound):
        """Test load_sound constructs correct path."""
        mock_sound_instance = Mock()
        mock_sound.return_value = mock_sound_instance
        mock_path_div.return_value = Path("test_path")

        load_sound(self.test_sound_file)

        # Verify path construction - the actual call should be with the filename
        mock_path_div.assert_called_with(self.test_sound_file)


class TestSFX(unittest.TestCase):
    """Test SFX class."""

    def test_sfx_constants(self):  # noqa: PLR6301
        """Test SFX constants are defined correctly."""
        assert SFX.BOUNCE == "sfx_bounce.wav"
        assert SFX.SLAP == "sfx_slap.wav"


class TestSpeed(unittest.TestCase):
    """Test Speed class."""

    def test_speed_initialization_default(self):  # noqa: PLR6301
        """Test Speed initialization with default values."""
        speed = Speed()
        assert speed.x == 0
        assert speed.y == 0
        assert speed.increment == DEFAULT_INCREMENT

    def test_speed_initialization_custom(self):  # noqa: PLR6301
        """Test Speed initialization with custom values."""
        speed = Speed(SPEED_X_5, SPEED_Y_10, CUSTOM_INCREMENT)
        assert speed.x == SPEED_X_5
        assert speed.y == SPEED_Y_10
        assert speed.increment == CUSTOM_INCREMENT

    def test_speed_up(self):  # noqa: PLR6301
        """Test Speed speed_up method."""
        speed = Speed(SPEED_X_2, SPEED_Y_3, CUSTOM_INCREMENT)
        speed.speed_up()
        assert speed.x == SPEED_X_2_5
        assert speed.y == SPEED_Y_3_5

    def test_speed_up_horizontal(self):  # noqa: PLR6301
        """Test Speed speed_up_horizontal method."""
        speed = Speed(SPEED_X_2, SPEED_Y_3, CUSTOM_INCREMENT)
        speed.speed_up_horizontal()
        assert speed.x == SPEED_X_2_5
        assert speed.y == SPEED_Y_3  # Should not change

    def test_speed_up_vertical(self):  # noqa: PLR6301
        """Test Speed speed_up_vertical method."""
        speed = Speed(SPEED_X_2, SPEED_Y_3, CUSTOM_INCREMENT)
        speed.speed_up_vertical()
        assert speed.x == SPEED_X_2  # Should not change
        assert speed.y == SPEED_Y_3_5

    def test_speed_up_negative_values(self):  # noqa: PLR6301
        """Test Speed speed_up with negative values."""
        speed = Speed(-SPEED_X_2, -SPEED_Y_3, CUSTOM_INCREMENT)
        speed.speed_up()
        assert speed.x == SPEED_X_NEGATIVE_2_5
        assert speed.y == SPEED_Y_NEGATIVE_3_5


class TestHorizontal(unittest.TestCase):
    """Test Horizontal movement class."""

    def test_horizontal_initialization(self):  # noqa: PLR6301
        """Test Horizontal initialization."""
        speed = Speed(SPEED_X_5, 0)
        horizontal = Horizontal(speed)
        assert horizontal.speed == speed
        assert horizontal.current_speed == SPEED_X_5

    def test_horizontal_left(self):  # noqa: PLR6301
        """Test Horizontal left movement."""
        speed = Speed(SPEED_X_5, 0)
        horizontal = Horizontal(speed)
        horizontal.left()
        assert horizontal.current_speed == SPEED_X_NEGATIVE_5

    def test_horizontal_right(self):  # noqa: PLR6301
        """Test Horizontal right movement."""
        speed = Speed(SPEED_X_5, 0)
        horizontal = Horizontal(speed)
        horizontal.right()
        assert horizontal.current_speed == SPEED_X_5

    def test_horizontal_stop(self):  # noqa: PLR6301
        """Test Horizontal stop movement."""
        speed = Speed(SPEED_X_5, 0)
        horizontal = Horizontal(speed)
        horizontal.stop()
        assert horizontal.current_speed == 0

    def test_horizontal_change_speed(self):  # noqa: PLR6301
        """Test Horizontal _change_speed method."""
        speed = Speed(SPEED_X_5, 0)
        horizontal = Horizontal(speed)
        horizontal._change_speed(SPEED_X_10)
        assert horizontal.current_speed == SPEED_X_10


class TestVertical(unittest.TestCase):
    """Test Vertical movement class."""

    def test_vertical_initialization(self):  # noqa: PLR6301
        """Test Vertical initialization."""
        speed = Speed(0, SPEED_Y_5)
        vertical = Vertical(speed)
        assert vertical.speed == speed
        assert vertical.current_speed == SPEED_Y_5

    def test_vertical_up(self):  # noqa: PLR6301
        """Test Vertical up movement."""
        speed = Speed(0, SPEED_Y_5)
        vertical = Vertical(speed)
        vertical.up()
        assert vertical.current_speed == SPEED_X_NEGATIVE_5

    def test_vertical_down(self):  # noqa: PLR6301
        """Test Vertical down movement."""
        speed = Speed(0, SPEED_Y_5)
        vertical = Vertical(speed)
        vertical.down()
        assert vertical.current_speed == SPEED_Y_5

    def test_vertical_stop(self):  # noqa: PLR6301
        """Test Vertical stop movement."""
        speed = Speed(0, SPEED_Y_5)
        vertical = Vertical(speed)
        vertical.stop()
        assert vertical.current_speed == 0

    def test_vertical_change_speed(self):  # noqa: PLR6301
        """Test Vertical _change_speed method."""
        speed = Speed(0, SPEED_Y_5)
        vertical = Vertical(speed)
        vertical._change_speed(SPEED_Y_10)
        assert vertical.current_speed == SPEED_Y_10


class TestBallSpriteMethods(unittest.TestCase):
    """Test BallSprite methods that don't require full initialization."""

    def test_ball_color_property(self):  # noqa: PLR6301
        """Test BallSprite color property without initialization."""
        # Create a mock ball sprite
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.circle") as _,
            patch("pygame.Surface", return_value=MockFactory.create_pygame_surface_mock()),
            patch("pygame.display.get_surface", return_value=MockFactory.create_display_mock()),
        ):
            ball = BallSprite()
            test_color = (255, 0, 0)
            ball.color = test_color
            assert ball.color == test_color

    def test_ball_bounce_method(self):  # noqa: PLR6301
        """Test BallSprite bounce method without full initialization."""
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.circle") as _,
            patch("pygame.Surface", return_value=MockFactory.create_pygame_surface_mock()),
            patch("pygame.display.get_surface", return_value=MockFactory.create_display_mock()),
        ):
            ball = BallSprite()
            original_direction = ball.direction

            # Provide a dummy speed that supports in-place multiplication
            class _DummySpeed:
                def __init__(self, x: float, y: float) -> None:
                    self.x = x
                    self.y = y

                def __imul__(self, factor: float):
                    self.x *= factor
                    self.y *= factor
                    return self

            ball.speed = _DummySpeed(4.0, 2.0)
            original_speed_x = ball.speed.x
            ball.bounce(10)
            assert ball.direction != original_direction
            assert ball.speed.x > original_speed_x


if __name__ == "__main__":
    unittest.main()


class TestPaddles(unittest.TestCase):
    """Focused tests for HorizontalPaddle and VerticalPaddle using centralized mocks.

    Note: These tests rely on mocked pygame display/surface; production behavior
    should remain unchanged. If paddle behavior changes, update tests accordingly.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.surface_mock = MockFactory.create_pygame_surface_mock()
        self.display_mock = MockFactory.create_display_mock(800, 600)

    def test_horizontal_paddle_initialization_and_update(self):
        """Test horizontal paddle initialization and update functionality."""
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.rect") as _,
            patch("pygame.Surface", return_value=self.surface_mock),
            patch("pygame.display.get_surface", return_value=self.display_mock),
        ):
            # Patch movement classes used inside paddle to accept int speeds
            class _DummyHorizontal:
                def __init__(self, speed: int):
                    self.speed = Mock(x=float(speed), y=0.0)
                    self.current_speed = float(speed)

                def left(self): self.current_speed = -abs(self.speed.x)

                def right(self): self.current_speed = abs(self.speed.x)

                def stop(self): self.current_speed = 0.0
            with patch("glitchygames.game_objects.paddle.Horizontal", _DummyHorizontal):
                paddle = HorizontalPaddle(
                name="hp",
                size=(100, 20),
                position=(50, 100),
                color=(255, 0, 0),
                speed=5,
                )
                # normal update should move horizontally from current x
                start_x = paddle.rect.x
                paddle.update()
                assert paddle.rect.x != start_x

    def test_horizontal_paddle_bounds_left_right(self):
        """Test horizontal paddle left and right boundary behavior."""
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.rect") as _,
            patch("pygame.Surface", return_value=self.surface_mock),
            patch("pygame.display.get_surface", return_value=self.display_mock),
        ):
            class _DummyHorizontal:
                def __init__(self, speed: int):
                    self.speed = Mock(x=float(speed), y=0.0)
                    self.current_speed = -10.0

                def left(self): self.current_speed = -abs(self.speed.x)

                def right(self): self.current_speed = abs(self.speed.x)

                def stop(self): self.current_speed = 0.0
            with patch("glitchygames.game_objects.paddle.Horizontal", _DummyHorizontal):
                paddle = HorizontalPaddle(
                name="hp",
                size=(100, 20),
                position=(0, 100),
                color=(255, 0, 0),
                speed=5,
                )
                # Force left bound
                paddle._move.current_speed = -10
                paddle.update()
                assert paddle.rect.x == 0

                # Move to right bound
                paddle.rect.x = 1000
                paddle.rect.right = paddle.rect.x + paddle.rect.width
                paddle._move.current_speed = 10
                paddle.update()
                assert paddle.rect.x == self.display_mock.right - paddle.rect.width

    def test_vertical_paddle_initialization_and_update(self):
        """Test vertical paddle initialization and update functionality."""
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.rect") as _,
            patch("pygame.Surface", return_value=self.surface_mock),
            patch("pygame.display.get_surface", return_value=self.display_mock),
        ):
            class _DummyVertical:
                def __init__(self, speed: int):
                    self.speed = Mock(x=0.0, y=float(speed))
                    self.current_speed = float(speed)

                def up(self): self.current_speed = -abs(self.speed.y)

                def down(self): self.current_speed = abs(self.speed.y)

                def stop(self): self.current_speed = 0.0
            with patch("glitchygames.game_objects.paddle.Vertical", _DummyVertical):
                paddle = VerticalPaddle(
                name="vp",
                size=(20, 100),
                position=(100, 50),
                color=(0, 255, 0),
                speed=5,
                )
                start_y = paddle.rect.y
                paddle.update()
                assert paddle.rect.y != start_y

    def test_vertical_paddle_bounds_top_bottom(self):
        """Test vertical paddle top and bottom boundary behavior."""
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.rect") as _,
            patch("pygame.Surface", return_value=self.surface_mock),
            patch("pygame.display.get_surface", return_value=self.display_mock),
        ):
            class _DummyVertical:
                def __init__(self, speed: int):
                    self.speed = Mock(x=0.0, y=float(speed))
                    self.current_speed = -10.0

                def up(self): self.current_speed = -abs(self.speed.y)

                def down(self): self.current_speed = abs(self.speed.y)

                def stop(self): self.current_speed = 0.0
            with patch("glitchygames.game_objects.paddle.Vertical", _DummyVertical):
                paddle = VerticalPaddle(
                name="vp",
                size=(20, 100),
                position=(100, 0),
                color=(0, 255, 0),
                speed=5,
                )
                # Force top bound
                paddle._move.current_speed = -10
                paddle.update()
                assert paddle.rect.y == 0

                # Move to bottom bound
                paddle.rect.y = self.display_mock.bottom - paddle.rect.height + 10
                paddle.rect.bottom = paddle.rect.y + paddle.rect.height
                paddle._move.current_speed = 10
                paddle.update()
                assert paddle.rect.y == self.display_mock.bottom - paddle.rect.height

    def test_paddles_movement_methods_and_sound(self):
        """Test paddle movement methods and sound functionality."""
        with (
            patch("pygame.sprite.LayeredDirty") as _,
            patch("pygame.draw.rect") as _,
            patch("pygame.Surface", return_value=self.surface_mock),
            patch("pygame.display.get_surface", return_value=self.display_mock),
            patch("glitchygames.game_objects.load_sound") as mock_load_sound,
        ):
            mock_load_sound.return_value = Mock()

            class _DummyHorizontal:
                def __init__(self, speed: int):
                    self.speed = Mock(x=float(speed), y=0.0)
                    self.current_speed = 0.0

                def left(self): self.current_speed = -abs(self.speed.x)

                def right(self): self.current_speed = abs(self.speed.x)

                def stop(self): self.current_speed = 0.0

            class _DummyVertical:
                def __init__(self, speed: int):
                    self.speed = Mock(x=0.0, y=float(speed))
                    self.current_speed = 0.0

                def up(self): self.current_speed = -abs(self.speed.y)

                def down(self): self.current_speed = abs(self.speed.y)

                def stop(self): self.current_speed = 0.0
            with (
                patch("glitchygames.game_objects.paddle.Horizontal", _DummyHorizontal),
                patch("glitchygames.game_objects.paddle.Vertical", _DummyVertical),
                patch("pygame.mixer.Sound"),
                patch("glitchygames.game_objects.paddle.load_sound") as mock_paddle_load_sound,
            ):
                hp = HorizontalPaddle(
                    "hp", (100, 20), (50, 100), (255, 0, 0), 5,
                    collision_sound="slap.wav"
                )
                hp.left()
                assert hp.dirty == 1
                hp.right()
                assert hp.dirty == 1
                hp.stop()
                assert hp.dirty == 1
                hp.speed_up()  # no assertion, just ensure it doesn't crash

                vp = VerticalPaddle(
                    "vp", (20, 100), (100, 50), (0, 255, 0), 5,
                    collision_sound="bounce.wav"
                )
                vp.up()
                assert vp.dirty == 1
                vp.down()
                assert vp.dirty == 1
                vp.stop()
                assert vp.dirty == 1
                vp.speed_up()
                mock_paddle_load_sound.assert_any_call("slap.wav")
                mock_paddle_load_sound.assert_any_call("bounce.wav")
