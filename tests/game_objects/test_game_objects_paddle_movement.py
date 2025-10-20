"""Test paddle game objects with simplified approach."""

from unittest.mock import Mock, patch

from glitchygames.game_objects.paddle import BasePaddle, HorizontalPaddle, VerticalPaddle
from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.vertical import Vertical
from tests.mocks import MockFactory


class BasePaddleTest:
    """Base test class with common helper methods for paddle tests."""

    def _create_mock_screen(self, left=0, right=800, top=0, bottom=600):
        """Create a mock screen using MockFactory."""
        mock_screen = Mock()
        mock_screen.left = left
        mock_screen.right = right
        mock_screen.top = top
        mock_screen.bottom = bottom
        return mock_screen

# Constants for magic values
POS_100 = 100
POS_200 = 200
POS_300 = 300
SIZE_50 = 50
SIZE_20 = 20
SIZE_100 = 100


class TestPaddleBasicFunctionality(BasePaddleTest):
    """Test basic paddle functionality without complex movement."""

    def test_base_paddle_initialization(self, mock_pygame_patches):
        """Test BasePaddle initialization with proper movement objects."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        assert paddle.name == "test_paddle"
        assert paddle.rect.x == POS_100
        assert paddle.rect.y == POS_200
        assert paddle.width == SIZE_50
        assert paddle.height == SIZE_20
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
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
            groups=groups,
        )

        assert groups in paddle.groups()

    def test_base_paddle_initialization_without_groups(self, mock_pygame_patches):
        """Test BasePaddle creates default groups when None provided."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
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
                x=POS_100,
                y=POS_200,
                width=SIZE_50,
                height=SIZE_20,
                collision_sound="hit.wav",
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
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Should not have collision sound
        assert not hasattr(paddle, "snd")


class TestPaddleMovement(BasePaddleTest):
    """Test paddle movement functionality."""

    def test_move_horizontal(self, mock_pygame_patches):
        """Test horizontal movement."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
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
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set up movement
        paddle._move.current_speed = 4
        original_y = paddle.rect.y

        paddle.move_vertical()

        assert paddle.rect.y == original_y + 4


class TestPaddleBoundaryDetection(BasePaddleTest):
    """Test paddle boundary detection methods."""

    def test_is_at_bottom_of_screen(self, mock_pygame_patches):
        """Test bottom boundary detection."""
        paddle = BasePaddle(
            axis=Vertical,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set screen dimensions
        paddle.screen_height = 400

        # Test bottom boundary:
        # paddle at y=380 with speed=5 would go to y=385,
        # which is > screen_height=400
        paddle.rect.y = 380  # 20px from bottom (height=20)
        paddle.rect.height = SIZE_20  # Ensure height is set correctly
        paddle.rect.bottom = 400  # Set bottom to 400 (y + height)
        paddle._move.current_speed = 5  # Moving down
        assert paddle.is_at_bottom_of_screen() is True

        # Test not at bottom
        paddle.rect.y = POS_200
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
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Test at top - paddle at y=0 with speed=-5 would go to y=-5, which is < 0
        paddle.rect.y = 0
        paddle.rect.top = 0  # Set top to 0
        paddle._move.current_speed = -5  # Moving up
        assert paddle.is_at_top_of_screen() is True

        # Test not at top
        paddle.rect.y = POS_200
        paddle.rect.top = POS_200  # Reset top to y
        paddle._move.current_speed = -5  # Moving up
        assert paddle.is_at_top_of_screen() is False

    def test_is_at_left_of_screen(self, mock_pygame_patches):
        """Test left boundary detection."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set screen dimensions
        paddle.screen = self._create_mock_screen(left=0)

        # Test at left - paddle at x=0 with speed=5 would go to x=-5, which is < screen.left=0
        paddle.rect.x = 0
        paddle._move.current_speed = -5  # Moving left
        assert paddle.is_at_left_of_screen() is True

        # Test not at left
        paddle.rect.x = POS_100
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_left_of_screen() is False

    def test_is_at_right_of_screen(self, mock_pygame_patches):
        """Test right boundary detection."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name="test_paddle",
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set screen dimensions
        paddle.screen = self._create_mock_screen(right=800)

        # Test at right - paddle at x=750 with speed=5 would go to x=755,
        # which is > screen.right=800
        paddle.rect.x = 750  # 50 pixels from right (width=50)
        paddle.rect.right = 800  # Set right to 800
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_right_of_screen() is True

        # Test not at right
        paddle.rect.x = POS_100
        paddle.rect.right = 150  # Reset right to x + width (100 + 50)
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_right_of_screen() is False


class TestHorizontalPaddle(BasePaddleTest):
    """Test HorizontalPaddle class."""

    def test_horizontal_paddle_initialization(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization."""
        paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

        assert paddle.name == "horizontal_paddle"
        assert paddle.rect.x == POS_200
        assert paddle.rect.y == POS_300
        assert paddle.width == SIZE_100
        assert paddle.height == SIZE_20
        assert isinstance(paddle._move, Horizontal)

    def test_horizontal_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization with custom groups."""
        groups = Mock()
        paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
            groups=groups,
        )

        assert groups in paddle.groups()

    def test_horizontal_paddle_initialization_with_collision_sound(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization with collision sound."""
        with patch("glitchygames.game_objects.paddle.load_sound") as mock_load_sound:
            mock_sound = Mock()
            mock_load_sound.return_value = mock_sound

            paddle = HorizontalPaddle(
                name="horizontal_paddle",
                size=(SIZE_100, SIZE_20),
                position=(POS_200, POS_300),
                color=(0, 255, 0),
                speed=5,
                collision_sound="hit.wav",
            )

            assert paddle.snd == mock_sound


class TestVerticalPaddle(BasePaddleTest):
    """Test VerticalPaddle class."""

    def test_vertical_paddle_initialization(self, mock_pygame_patches):
        """Test VerticalPaddle initialization."""
        paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
        )

        assert paddle.name == "vertical_paddle"
        assert paddle.rect.x == POS_200
        assert paddle.rect.y == POS_300
        assert paddle.width == SIZE_20
        assert paddle.height == SIZE_100
        assert isinstance(paddle._move, Vertical)

    def test_vertical_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test VerticalPaddle initialization with custom groups."""
        groups = Mock()
        paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
            groups=groups,
        )

        assert groups in paddle.groups()

    def test_vertical_paddle_initialization_with_collision_sound(self, mock_pygame_patches):
        """Test VerticalPaddle initialization with collision sound."""
        with patch("glitchygames.game_objects.paddle.load_sound") as mock_load_sound:
            mock_sound = Mock()
            mock_load_sound.return_value = mock_sound

            paddle = VerticalPaddle(
                name="vertical_paddle",
                size=(SIZE_20, SIZE_100),
                position=(POS_200, POS_300),
                color=(0, 0, 255),
                speed=5,
                collision_sound="hit.wav",
            )

            assert paddle.snd == mock_sound


class TestPaddleIntegration(BasePaddleTest):
    """Test paddle integration scenarios."""

    def test_horizontal_paddle_full_cycle(self, mock_pygame_patches):
        """Test complete horizontal paddle game cycle."""
        paddle = HorizontalPaddle(
            name="horizontal_paddle",
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
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
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
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
            size=(SIZE_100, SIZE_20),
            position=(0, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

        h_paddle.screen = self._create_mock_screen(left=0, right=800)
        h_paddle.rect.left = 0  # Set left to 0
        h_paddle.rect.right = SIZE_100  # Set right to width
        h_paddle._move.current_speed = -5  # Moving left
        assert h_paddle.is_at_left_of_screen() is True
        assert h_paddle.is_at_right_of_screen() is False

        # Test vertical paddle at boundaries
        v_paddle = VerticalPaddle(
            name="vertical_paddle",
            size=(SIZE_20, SIZE_100),
            position=(POS_200, 0),
            color=(0, 0, 255),
            speed=5,
        )

        v_paddle.screen = self._create_mock_screen(top=0)
        v_paddle.rect.y = 0
        v_paddle.rect.top = 0  # Set top to 0
        v_paddle._move.current_speed = -5  # Moving up
        assert v_paddle.is_at_top_of_screen() is True
        assert v_paddle.is_at_bottom_of_screen() is False
