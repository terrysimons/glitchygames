"""Test paddle game objects with simplified approach."""

from unittest.mock import Mock, patch

import pytest
from glitchygames.game_objects.paddle import BasePaddle, HorizontalPaddle, VerticalPaddle
from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.speed import Speed
from glitchygames.movement.vertical import Vertical


class TestPaddleBasicFunctionality:
    """Test basic paddle functionality without complex movement."""

    def test_base_paddle_initialization(self, mock_pygame_patches):
        """Test BasePaddle initialization with proper movement objects."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        assert paddle.name == "test_paddle"
        assert paddle.rect.x == 100
        assert paddle.rect.y == 200
        assert paddle.width == 50
        assert paddle.height == 20
        assert paddle.use_gfxdraw is True
        assert paddle.moving is False
        assert paddle.dirty == 1
        assert isinstance(paddle._move, Horizontal)

    def test_base_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test BasePaddle initialization with custom groups."""
        groups = Mock()
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20,
            groups=groups
        )
        
        assert groups in paddle.groups()

    def test_base_paddle_initialization_without_groups(self, mock_pygame_patches):
        """Test BasePaddle creates default groups when None provided."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Should have default groups
        assert len(paddle.groups()) > 0

    def test_base_paddle_initialization_with_collision_sound(self, mock_pygame_patches):
        """Test BasePaddle initialization with collision sound."""
        with patch("glitchygames.game_objects.paddle.load_sound") as mock_load_sound:
            mock_sound = Mock()
            mock_load_sound.return_value = mock_sound
            
            paddle = BasePaddle(
                axis=Horizontal,
                speed=5,
                name="test_paddle",
                color=(255, 0, 0),
                x=100,
                y=200,
                width=50,
                height=20,
                collision_sound="hit.wav"
            )
            
            assert paddle.snd == mock_sound
            mock_load_sound.assert_called_once_with("hit.wav")

    def test_base_paddle_initialization_without_collision_sound(self, mock_pygame_patches):
        """Test BasePaddle initialization without collision sound."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Should not have collision sound
        assert not hasattr(paddle, "snd")


class TestPaddleMovement:
    """Test paddle movement functionality."""

    def test_move_horizontal(self, mock_pygame_patches):
        """Test horizontal movement."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Set up movement
        paddle._move.current_speed = 3
        original_x = paddle.rect.x
        
        paddle.move_horizontal()
        
        assert paddle.rect.x == original_x + 3

    def test_move_vertical(self, mock_pygame_patches):
        """Test vertical movement."""
        paddle = BasePaddle(
            axis=Vertical,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Set up movement
        paddle._move.current_speed = 4
        original_y = paddle.rect.y
        
        paddle.move_vertical()
        
        assert paddle.rect.y == original_y + 4


class TestPaddleBoundaryDetection:
    """Test paddle boundary detection methods."""

    def test_is_at_bottom_of_screen(self, mock_pygame_patches):
        """Test bottom boundary detection."""
        paddle = BasePaddle(
            axis=Vertical,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Set screen dimensions
        paddle.screen_height = 400
        
        # Test at bottom - paddle at y=380 with speed=5 would go to y=385, which is > screen_height=400
        paddle.rect.y = 380  # 20 pixels from bottom (height=20)
        paddle.rect.height = 20  # Ensure height is set correctly
        paddle.rect.bottom = 400  # Set bottom to 400 (y + height)
        paddle._move.current_speed = 5  # Moving down
        assert paddle.is_at_bottom_of_screen() is True
        
        # Test not at bottom
        paddle.rect.y = 200
        paddle.rect.bottom = 220  # Reset bottom to y + height (200 + 20)
        paddle._move.current_speed = 5  # Moving down
        assert paddle.is_at_bottom_of_screen() is False

    def test_is_at_top_of_screen(self, mock_pygame_patches):
        """Test top boundary detection."""
        paddle = BasePaddle(
            axis=Vertical,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Test at top - paddle at y=0 with speed=-5 would go to y=-5, which is < 0
        paddle.rect.y = 0
        paddle.rect.top = 0  # Set top to 0
        paddle._move.current_speed = -5  # Moving up
        assert paddle.is_at_top_of_screen() is True
        
        # Test not at top
        paddle.rect.y = 200
        paddle.rect.top = 200  # Reset top to y
        paddle._move.current_speed = -5  # Moving up
        assert paddle.is_at_top_of_screen() is False

    def test_is_at_left_of_screen(self, mock_pygame_patches):
        """Test left boundary detection."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Set screen dimensions
        paddle.screen = Mock()
        paddle.screen.left = 0
        
        # Test at left - paddle at x=0 with speed=5 would go to x=-5, which is < screen.left=0
        paddle.rect.x = 0
        paddle._move.current_speed = -5  # Moving left
        assert paddle.is_at_left_of_screen() is True
        
        # Test not at left
        paddle.rect.x = 100
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_left_of_screen() is False

    def test_is_at_right_of_screen(self, mock_pygame_patches):
        """Test right boundary detection."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=100,
            y=200,
            width=50,
            height=20
        )
        
        # Set screen dimensions
        paddle.screen = Mock()
        paddle.screen.right = 800
        
        # Test at right - paddle at x=750 with speed=5 would go to x=755, which is > screen.right=800
        paddle.rect.x = 750  # 50 pixels from right (width=50)
        paddle.rect.right = 800  # Set right to 800
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_right_of_screen() is True
        
        # Test not at right
        paddle.rect.x = 100
        paddle.rect.right = 150  # Reset right to x + width (100 + 50)
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_right_of_screen() is False


class TestHorizontalPaddle:
    """Test HorizontalPaddle class."""

    def test_horizontal_paddle_initialization(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization."""
        paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(100, 20),
            position=(200, 300),
            color=(0, 255, 0),
            speed=5
        )
        
        assert paddle.name == "horizontal_paddle"
        assert paddle.rect.x == 200
        assert paddle.rect.y == 300
        assert paddle.width == 100
        assert paddle.height == 20
        assert isinstance(paddle._move, Horizontal)

    def test_horizontal_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization with custom groups."""
        groups = Mock()
        paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(100, 20),
            position=(200, 300),
            color=(0, 255, 0),
            speed=5,
            groups=groups
        )
        
        assert groups in paddle.groups()

    def test_horizontal_paddle_initialization_with_collision_sound(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization with collision sound."""
        with patch("glitchygames.game_objects.paddle.load_sound") as mock_load_sound:
            mock_sound = Mock()
            mock_load_sound.return_value = mock_sound
            
            paddle = HorizontalPaddle(
                name="horizontal_paddle",
                size=(100, 20),
                position=(200, 300),
                color=(0, 255, 0),
                speed=5,
                collision_sound="hit.wav"
            )
            
            assert paddle.snd == mock_sound


class TestVerticalPaddle:
    """Test VerticalPaddle class."""

    def test_vertical_paddle_initialization(self, mock_pygame_patches):
        """Test VerticalPaddle initialization."""
        paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(20, 100),
            position=(200, 300),
            color=(0, 0, 255),
            speed=5
        )
        
        assert paddle.name == "vertical_paddle"
        assert paddle.rect.x == 200
        assert paddle.rect.y == 300
        assert paddle.width == 20
        assert paddle.height == 100
        assert isinstance(paddle._move, Vertical)

    def test_vertical_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test VerticalPaddle initialization with custom groups."""
        groups = Mock()
        paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(20, 100),
            position=(200, 300),
            color=(0, 0, 255),
            speed=5,
            groups=groups
        )
        
        assert groups in paddle.groups()

    def test_vertical_paddle_initialization_with_collision_sound(self, mock_pygame_patches):
        """Test VerticalPaddle initialization with collision sound."""
        with patch("glitchygames.game_objects.paddle.load_sound") as mock_load_sound:
            mock_sound = Mock()
            mock_load_sound.return_value = mock_sound
            
            paddle = VerticalPaddle(
                name="vertical_paddle",
                size=(20, 100),
                position=(200, 300),
                color=(0, 0, 255),
                speed=5,
                collision_sound="hit.wav"
            )
            
            assert paddle.snd == mock_sound


class TestPaddleIntegration:
    """Test paddle integration scenarios."""

    def test_horizontal_paddle_full_cycle(self, mock_pygame_patches):
        """Test complete horizontal paddle game cycle."""
        paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(100, 20),
            position=(200, 300),
            color=(0, 255, 0),
            speed=5
        )
        
        # Test movement
        paddle._move.current_speed = 3
        original_x = paddle.rect.x
        paddle.move_horizontal()
        assert paddle.rect.x == original_x + 3
        
        # Test boundary detection
        paddle.screen = Mock()
        paddle.screen.left = 0
        paddle.rect.x = 0
        paddle.rect.left = 0  # Set left to 0
        paddle._move.current_speed = -5  # Moving left
        assert paddle.is_at_left_of_screen() is True

    def test_vertical_paddle_full_cycle(self, mock_pygame_patches):
        """Test complete vertical paddle game cycle."""
        paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(20, 100),
            position=(200, 300),
            color=(0, 0, 255),
            speed=5
        )
        
        # Test movement
        paddle._move.current_speed = 4
        original_y = paddle.rect.y
        paddle.move_vertical()
        assert paddle.rect.y == original_y + 4
        
        # Test boundary detection
        paddle.rect.y = 0
        paddle.rect.top = 0  # Set top to 0
        paddle._move.current_speed = -5  # Moving up
        assert paddle.is_at_top_of_screen() is True

    def test_paddle_boundary_behavior(self, mock_pygame_patches):
        """Test paddle behavior at boundaries."""
        # Test horizontal paddle at boundaries
        h_paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(100, 20),
            position=(0, 300),
            color=(0, 255, 0),
            speed=5
        )
        
        h_paddle.screen = Mock()
        h_paddle.screen.left = 0
        h_paddle.screen.right = 800  # Set screen width
        h_paddle.rect.left = 0  # Set left to 0
        h_paddle.rect.right = 100  # Set right to 100 (width=100)
        h_paddle._move.current_speed = -5  # Moving left
        assert h_paddle.is_at_left_of_screen() is True
        assert h_paddle.is_at_right_of_screen() is False
        
        # Test vertical paddle at boundaries
        v_paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(20, 100),
            position=(200, 0),
            color=(0, 0, 255),
            speed=5
        )
        
        v_paddle.screen = Mock()
        v_paddle.screen.top = 0
        v_paddle.rect.y = 0
        v_paddle.rect.top = 0  # Set top to 0
        v_paddle._move.current_speed = -5  # Moving up
        assert v_paddle.is_at_top_of_screen() is True
        assert v_paddle.is_at_bottom_of_screen() is False