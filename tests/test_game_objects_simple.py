"""Simple test coverage for Game Objects module."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.game_objects import load_sound
from glitchygames.game_objects.ball import BallSprite
from glitchygames.game_objects.paddle import BasePaddle, HorizontalPaddle, VerticalPaddle
from glitchygames.game_objects.sounds import SFX
from glitchygames.movement import Horizontal, Speed, Vertical

from test_mock_factory import MockFactory

# Global setup for all test classes
_patchers = None

def setUpModule():
    """Set up pygame mocks for the entire test module."""
    global _patchers
    _patchers = MockFactory.setup_pygame_mocks()
    for patcher in _patchers:
        patcher.start()

def tearDownModule():
    """Clean up pygame mocks for the entire test module."""
    global _patchers
    if _patchers:
        MockFactory.teardown_pygame_mocks(_patchers)


class TestGameObjectsInitCoverage(unittest.TestCase):
    """Test coverage for game_objects/__init__.py."""

    def test_load_sound_function(self):
        """Test load_sound function."""
        with patch("pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound
            
            result = load_sound("test.wav", 0.5)
            
            # Verify the sound was created with correct path
            expected_path = Path(__file__).parent.parent / "glitchygames" / "game_objects" / "snd_files" / "test.wav"
            mock_sound_class.assert_called_once_with(expected_path)
            
            # Verify volume was set
            mock_sound.set_volume.assert_called_once_with(0.5)
            
            # Verify return value
            self.assertEqual(result, mock_sound)

    def test_load_sound_default_volume(self):
        """Test load_sound function with default volume."""
        with patch("pygame.mixer.Sound") as mock_sound_class:
            mock_sound = Mock()
            mock_sound_class.return_value = mock_sound
            
            result = load_sound("test.wav")
            
            # Verify default volume was used
            mock_sound.set_volume.assert_called_once_with(0.25)
            self.assertEqual(result, mock_sound)

    def test_sfx_constants(self):
        """Test SFX constants."""
        self.assertEqual(SFX.BOUNCE, "sfx_bounce.wav")
        self.assertEqual(SFX.SLAP, "sfx_slap.wav")


class TestBallSpriteCoverage(unittest.TestCase):
    """Test coverage for BallSprite class."""

    def setUp(self):
        """Set up test fixtures for each test."""
        # Create ball sprite with mocked pygame
        with patch("glitchygames.game_objects.load_sound"):
            self.ball = BallSprite()

    def test_ball_initialization_default(self):
        """Test BallSprite initialization with default values."""
        self.assertEqual(self.ball.width, 20)
        self.assertEqual(self.ball.height, 20)
        self.assertEqual(self.ball.use_gfxdraw, True)
        self.assertEqual(self.ball.dirty, 2)
        self.assertIsInstance(self.ball.speed, Speed)
        self.assertEqual(self.ball.speed.x, 4)
        self.assertEqual(self.ball.speed.y, 2)

    def test_ball_color_property(self):
        """Test ball color property getter and setter."""
        # Test getter
        color = self.ball.color
        self.assertIsInstance(color, tuple)

        # Test setter
        new_color = (255, 0, 0)
        self.ball.color = new_color
        self.assertEqual(self.ball._color, new_color)

    def test_ball_color_setter_with_drawing(self):
        """Test ball color setter triggers drawing."""
        with patch("pygame.draw.circle") as mock_draw:
            new_color = (0, 255, 0)
            self.ball.color = new_color
            
            mock_draw.assert_called_once()
            call_args = mock_draw.call_args
            self.assertEqual(call_args[0][1], new_color)  # color argument

    def test_ball_do_bounce_top_wall(self):
        """Test _do_bounce with top wall collision."""
        self.ball.rect.y = -1  # Above top wall
        self.ball.speed.y = -2  # Moving up
        
        with patch.object(self.ball, "snd", Mock()) as mock_sound:
            self.ball._do_bounce()
            
            self.assertEqual(self.ball.rect.y, 0)
            self.assertEqual(self.ball.speed.y, 2)  # Reversed
            mock_sound.play.assert_called_once()

    def test_ball_do_bounce_bottom_wall(self):
        """Test _do_bounce with bottom wall collision."""
        self.ball.rect.y = 600  # At bottom wall
        self.ball.speed.y = 2  # Moving down
        
        with patch.object(self.ball, "snd", Mock()) as mock_sound:
            self.ball._do_bounce()
            
            self.assertEqual(self.ball.rect.y, 600 - self.ball.height)
            self.assertEqual(self.ball.speed.y, -2)  # Reversed
            mock_sound.play.assert_called_once()

    def test_ball_reset(self):
        """Test ball reset method."""
        with patch("secrets.randbelow") as mock_rand:
            mock_rand.side_effect = [350, 200, 30, 0]  # x, y, direction, coin flip
            
            self.ball.reset()
            
            # Check position (secrets.randbelow(700) + 50 = 350 + 50 = 400)
            self.assertEqual(self.ball.rect.x, 400)
            # Check y position (secrets.randbelow(375) + 25 = 200 + 25 = 225)
            self.assertEqual(self.ball.rect.y, 225)
            # Check direction (secrets.randbelow(90) - 45 = 30 - 45 = -15, then % 360 = 345)
            self.assertEqual(self.ball.direction, 345)

    def test_ball_bounce(self):
        """Test ball bounce method."""
        original_direction = self.ball.direction = 45
        original_speed_x = self.ball.speed.x
        
        self.ball.bounce(10)
        
        # Direction should be (180 - 45) % 360 = 135, then -10 = 125
        self.assertEqual(self.ball.direction, 125)
        # Speed should be multiplied by 1.1
        self.assertEqual(self.ball.speed.x, original_speed_x * 1.1)

    def test_ball_update_movement(self):
        """Test ball update with normal movement."""
        original_x = self.ball.rect.x = 100
        original_y = self.ball.rect.y = 100
        original_speed_x = self.ball.speed.x
        original_speed_y = self.ball.speed.y
        
        self.ball.update()
        
        # Should move by speed values
        self.assertEqual(self.ball.rect.x, original_x + original_speed_x)
        self.assertEqual(self.ball.rect.y, original_y + original_speed_y)


class TestBasePaddleCoverage(unittest.TestCase):
    """Test coverage for BasePaddle class."""

    def setUp(self):
        """Set up test fixtures for each test."""
        # Create paddle with mocked pygame
        with patch("glitchygames.game_objects.load_sound"):
            self.horizontal_axis = Horizontal(Speed(5, 0))
            self.paddle = BasePaddle(
                axis=self.horizontal_axis,
                speed=5,
                name="test_paddle",
                color=(255, 0, 0),
                x=100,
                y=200,
                width=50,
                height=20
            )

    def test_base_paddle_initialization(self):
        """Test BasePaddle initialization."""
        self.assertEqual(self.paddle.name, "test_paddle")
        self.assertEqual(self.paddle.rect.x, 100)
        self.assertEqual(self.paddle.rect.y, 200)
        self.assertEqual(self.paddle.width, 50)
        self.assertEqual(self.paddle.height, 20)
        self.assertEqual(self.paddle.use_gfxdraw, True)
        self.assertEqual(self.paddle.moving, False)
        self.assertEqual(self.paddle.dirty, 1)
        self.assertEqual(self.paddle._move, self.horizontal_axis)

    def test_base_paddle_move_horizontal(self):
        """Test move_horizontal method."""
        original_x = self.paddle.rect.x
        self.paddle._move.current_speed = 5
        
        self.paddle.move_horizontal()
        
        self.assertEqual(self.paddle.rect.x, original_x + 5)
        self.assertEqual(self.paddle.dirty, 1)

    def test_base_paddle_move_vertical(self):
        """Test move_vertical method."""
        original_y = self.paddle.rect.y
        self.paddle._move.current_speed = 3
        
        self.paddle.move_vertical()
        
        self.assertEqual(self.paddle.rect.y, original_y + 3)
        self.assertEqual(self.paddle.dirty, 1)

    def test_base_paddle_is_at_bottom_of_screen(self):
        """Test is_at_bottom_of_screen method."""
        self.paddle.rect.bottom = 600
        self.paddle._move.current_speed = 5
        
        result = self.paddle.is_at_bottom_of_screen()
        
        self.assertTrue(result)

    def test_base_paddle_is_at_top_of_screen(self):
        """Test is_at_top_of_screen method."""
        self.paddle.rect.top = 0
        self.paddle._move.current_speed = -5
        
        result = self.paddle.is_at_top_of_screen()
        
        self.assertTrue(result)

    def test_base_paddle_is_at_left_of_screen(self):
        """Test is_at_left_of_screen method."""
        self.paddle.rect.left = 0
        self.paddle._move.current_speed = -5
        
        result = self.paddle.is_at_left_of_screen()
        
        self.assertTrue(result)

    def test_base_paddle_is_at_right_of_screen(self):
        """Test is_at_right_of_screen method."""
        self.paddle.rect.right = 800
        self.paddle._move.current_speed = 5
        
        result = self.paddle.is_at_right_of_screen()
        
        self.assertTrue(result)


class TestHorizontalPaddleCoverage(unittest.TestCase):
    """Test coverage for HorizontalPaddle class."""

    def setUp(self):
        """Set up test fixtures for each test."""
        # Create paddle with mocked pygame
        with patch("glitchygames.game_objects.load_sound"):
            self.paddle = HorizontalPaddle(
                name="horizontal_paddle",
                size=(100, 20),
                position=(200, 300),
                color=(0, 255, 0),
                speed=5
            )

    def test_horizontal_paddle_initialization(self):
        """Test HorizontalPaddle initialization."""
        self.assertEqual(self.paddle.name, "horizontal_paddle")
        self.assertEqual(self.paddle.rect.x, 200)
        self.assertEqual(self.paddle.rect.y, 300)
        self.assertEqual(self.paddle.width, 100)
        self.assertEqual(self.paddle.height, 20)
        self.assertIsInstance(self.paddle._move, Horizontal)

    def test_horizontal_paddle_left(self):
        """Test horizontal paddle left movement."""
        with patch.object(self.paddle._move, "left") as mock_left:
            self.paddle.left()
            
            mock_left.assert_called_once()
            self.assertEqual(self.paddle.dirty, 1)

    def test_horizontal_paddle_right(self):
        """Test horizontal paddle right movement."""
        with patch.object(self.paddle._move, "right") as mock_right:
            self.paddle.right()
            
            mock_right.assert_called_once()
            self.assertEqual(self.paddle.dirty, 1)

    def test_horizontal_paddle_stop(self):
        """Test horizontal paddle stop."""
        with patch.object(self.paddle._move, "stop") as mock_stop:
            self.paddle.stop()
            
            mock_stop.assert_called_once()
            self.assertEqual(self.paddle.dirty, 1)

    def test_horizontal_paddle_speed_up(self):
        """Test horizontal paddle speed up."""
        with patch.object(self.paddle._move.speed, "speed_up_horizontal") as mock_speed_up:
            self.paddle.speed_up()
            
            mock_speed_up.assert_called_once()


class TestVerticalPaddleCoverage(unittest.TestCase):
    """Test coverage for VerticalPaddle class."""

    def setUp(self):
        """Set up test fixtures for each test."""
        # Create paddle with mocked pygame
        with patch("glitchygames.game_objects.load_sound"):
            self.paddle = VerticalPaddle(
                name="vertical_paddle",
                size=(20, 100),
                position=(400, 200),
                color=(0, 0, 255),
                speed=5
            )

    def test_vertical_paddle_initialization(self):
        """Test VerticalPaddle initialization."""
        self.assertEqual(self.paddle.name, "vertical_paddle")
        self.assertEqual(self.paddle.rect.x, 400)
        self.assertEqual(self.paddle.rect.y, 200)
        self.assertEqual(self.paddle.width, 20)
        self.assertEqual(self.paddle.height, 100)
        self.assertIsInstance(self.paddle._move, Vertical)

    def test_vertical_paddle_up(self):
        """Test vertical paddle up movement."""
        with patch.object(self.paddle._move, "up") as mock_up:
            self.paddle.up()
            
            mock_up.assert_called_once()
            self.assertEqual(self.paddle.dirty, 1)

    def test_vertical_paddle_down(self):
        """Test vertical paddle down movement."""
        with patch.object(self.paddle._move, "down") as mock_down:
            self.paddle.down()
            
            mock_down.assert_called_once()
            self.assertEqual(self.paddle.dirty, 1)

    def test_vertical_paddle_stop(self):
        """Test vertical paddle stop."""
        with patch.object(self.paddle._move, "stop") as mock_stop:
            self.paddle.stop()
            
            mock_stop.assert_called_once()
            self.assertEqual(self.paddle.dirty, 1)

    def test_vertical_paddle_speed_up(self):
        """Test vertical paddle speed up."""
        with patch.object(self.paddle._move.speed, "speed_up_vertical") as mock_speed_up:
            self.paddle.speed_up()
            
            mock_speed_up.assert_called_once()


if __name__ == "__main__":
    unittest.main()