"""Tests for paddle game objects."""


from glitchygames.game_objects.paddle import BasePaddle, HorizontalPaddle, VerticalPaddle
from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.vertical import Vertical
from tests.mocks import MockFactory
from glitchygames.game_objects.paddle import HorizontalPaddle, VerticalPaddle


POS_100 = 100
POS_200 = 200
POS_300 = 300
SIZE_50 = 50
SIZE_20 = 20
SIZE_100 = 100
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600


class BasePaddleTest:
    """Base test class with common helper methods for paddle tests."""

    def _create_mock_screen(self, left=0, right=800, top=0, bottom=600):
        """Create a mock screen using MockFactory.

        The screen must be a real pygame.Surface so that get_rect() returns
        a Rect with the correct width/height (used by is_at_right_of_screen,
        is_at_left_of_screen, etc.).

        Returns:
            object: The result.

        """
        width = right - left
        height = bottom - top
        mock_screen = MockFactory.create_pygame_surface_mock(width=width, height=height)
        return mock_screen


class TestPaddleBasicFunctionality(BasePaddleTest):
    """Test basic paddle functionality without complex movement."""

    def test_base_paddle_initialization(self, mock_pygame_patches):
        """Test BasePaddle initialization with proper movement objects."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        assert paddle.name == 'test_paddle'
        assert paddle.rect is not None
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
        groups = MockFactory.create_pygame_sprite_group_mock()
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name='test_paddle',
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
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Should have default groups
        assert len(paddle.groups()) > 0

    def test_base_paddle_initialization_with_collision_sound(self, mock_pygame_patches, mocker):
        """Test BasePaddle initialization with collision sound."""
        mock_load_sound = mocker.patch('glitchygames.game_objects.paddle.load_sound')
        mock_sound = MockFactory.create_pygame_surface_mock()
        mock_load_sound.return_value = mock_sound

        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
            collision_sound='hit.wav',
        )

        assert paddle.snd == mock_sound
        mock_load_sound.assert_called_once_with('hit.wav')

    def test_base_paddle_initialization_without_collision_sound(self, mock_pygame_patches):
        """Test BasePaddle initialization without collision sound."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Should not have collision sound
        assert not hasattr(paddle, 'snd')


class TestPaddleMovement(BasePaddleTest):
    """Test paddle movement functionality."""

    def test_move_horizontal(self, mock_pygame_patches):
        """Test horizontal movement."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set up movement
        paddle._move.current_speed = 3
        assert paddle.rect is not None
        original_x = paddle.rect.x

        paddle.move_horizontal()

        assert paddle.rect.x == original_x + 3

    def test_move_vertical(self, mock_pygame_patches):
        """Test vertical movement."""
        paddle = BasePaddle(
            axis=Vertical,
            speed=5,
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set up movement
        paddle._move.current_speed = 4
        assert paddle.rect is not None
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
            name='test_paddle',
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
        assert paddle.rect is not None
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
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Test at top - paddle at y=0 with speed=-5 would go to y=-5, which is < 0
        assert paddle.rect is not None
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
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
        )

        # Set screen dimensions
        paddle.screen = self._create_mock_screen(left=0)

        # Test at left - paddle at x=0 with speed=5 would go to x=-5, which is < screen.left=0
        assert paddle.rect is not None
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
            name='test_paddle',
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
        assert paddle.rect is not None
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
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

        assert paddle.name == 'horizontal_paddle'
        assert paddle.rect is not None
        assert paddle.rect.x == POS_200
        assert paddle.rect.y == POS_300
        assert paddle.width == SIZE_100
        assert paddle.height == SIZE_20
        assert isinstance(paddle._move, Horizontal)

    def test_horizontal_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test HorizontalPaddle initialization with custom groups."""
        groups = MockFactory.create_pygame_sprite_group_mock()
        paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
            groups=groups,
        )

        assert groups in paddle.groups()

    def test_horizontal_paddle_initialization_with_collision_sound(
        self, mock_pygame_patches, mocker
    ):
        """Test HorizontalPaddle initialization with collision sound."""
        mock_load_sound = mocker.patch('glitchygames.game_objects.paddle.load_sound')
        mock_sound = MockFactory.create_pygame_surface_mock()
        mock_load_sound.return_value = mock_sound

        paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
            collision_sound='hit.wav',
        )

        assert paddle.snd == mock_sound


class TestVerticalPaddle(BasePaddleTest):
    """Test VerticalPaddle class."""

    def test_vertical_paddle_initialization(self, mock_pygame_patches):
        """Test VerticalPaddle initialization."""
        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
        )

        assert paddle.name == 'vertical_paddle'
        assert paddle.rect is not None
        assert paddle.rect.x == POS_200
        assert paddle.rect.y == POS_300
        assert paddle.width == SIZE_20
        assert paddle.height == SIZE_100
        assert isinstance(paddle._move, Vertical)

    def test_vertical_paddle_initialization_with_groups(self, mock_pygame_patches):
        """Test VerticalPaddle initialization with custom groups."""
        groups = MockFactory.create_pygame_sprite_group_mock()
        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
            groups=groups,
        )

        assert groups in paddle.groups()

    def test_vertical_paddle_initialization_with_collision_sound(self, mock_pygame_patches, mocker):
        """Test VerticalPaddle initialization with collision sound."""
        mock_load_sound = mocker.patch('glitchygames.game_objects.paddle.load_sound')
        mock_sound = MockFactory.create_pygame_surface_mock()
        mock_load_sound.return_value = mock_sound

        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
            collision_sound='hit.wav',
        )

        assert paddle.snd == mock_sound


class TestPaddleIntegration(BasePaddleTest):
    """Test paddle integration scenarios."""

    def test_horizontal_paddle_full_cycle(self, mock_pygame_patches):
        """Test complete horizontal paddle game cycle."""
        paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

        # Test movement
        paddle._move.current_speed = 3
        assert paddle.rect is not None
        original_x = paddle.rect.x
        paddle.move_horizontal()
        assert paddle.rect.x == original_x + 3

        # Test boundary detection
        paddle.screen = MockFactory.create_pygame_surface_mock()
        paddle.screen.left = 0
        paddle.rect.x = 0
        paddle.rect.left = 0  # Set left to 0
        paddle._move.current_speed = -5  # Moving left
        assert paddle.is_at_left_of_screen() is True

    def test_vertical_paddle_full_cycle(self, mock_pygame_patches):
        """Test complete vertical paddle game cycle."""
        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
        )

        # Test movement
        paddle._move.current_speed = 4
        assert paddle.rect is not None
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
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(0, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

        h_paddle.screen = self._create_mock_screen(left=0, right=800)
        assert h_paddle.rect is not None
        h_paddle.rect.left = 0  # Set left to 0
        h_paddle.rect.right = SIZE_100  # Set right to width
        h_paddle._move.current_speed = -5  # Moving left
        assert h_paddle.is_at_left_of_screen() is True
        assert h_paddle.is_at_right_of_screen() is False

        # Test vertical paddle at boundaries
        v_paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, 0),
            color=(0, 0, 255),
            speed=5,
        )

        v_paddle.screen = self._create_mock_screen(top=0)
        assert v_paddle.rect is not None
        v_paddle.rect.y = 0
        v_paddle.rect.top = 0  # Set top to 0
        v_paddle._move.current_speed = -5  # Moving up
        assert v_paddle.is_at_top_of_screen() is True
        assert v_paddle.is_at_bottom_of_screen() is False


class TestHorizontalPaddleUpdate:
    """Test HorizontalPaddle.update() boundary behavior (lines 186-193)."""

    def _create_horizontal_paddle(self):
        """Create a HorizontalPaddle for testing.

        Returns:
            HorizontalPaddle: A configured horizontal paddle.

        """
        return HorizontalPaddle(
            name='test_horizontal',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

    def _create_mock_screen(self, left=0, right=SCREEN_WIDTH):
        """Create a mock screen with proper dimensions for boundary detection.

        The screen must be a real pygame.Surface so that get_rect() returns
        a Rect with the correct width/height.

        Returns:
            object: A mock screen with correct dimensions.

        """
        width = right - left
        mock_screen = MockFactory.create_pygame_surface_mock(width=width, height=SCREEN_HEIGHT)
        return mock_screen

    def test_update_at_left_boundary_stops_paddle(self, mock_pygame_patches):
        """Test update() when paddle is at left boundary (lines 186-188)."""
        paddle = self._create_horizontal_paddle()
        paddle.screen = self._create_mock_screen(left=0)

        # Position paddle so is_at_left_of_screen returns True
        assert paddle.rect is not None
        paddle.rect.x = 0
        paddle._move.current_speed = -5  # Moving left

        paddle.update()

        assert paddle.rect.x == 0
        assert paddle._move.current_speed == 0  # stop() was called

    def test_update_at_right_boundary_stops_paddle(self, mock_pygame_patches):
        """Test update() when paddle is at right boundary (lines 189-191)."""
        paddle = self._create_horizontal_paddle()
        paddle.screen = self._create_mock_screen(right=SCREEN_WIDTH)

        # Position paddle so is_at_right_of_screen returns True
        assert paddle.rect is not None
        paddle.rect.x = SCREEN_WIDTH - SIZE_100
        paddle.rect.right = SCREEN_WIDTH
        paddle._move.current_speed = 5  # Moving right

        paddle.update()

        assert paddle.rect.x == SCREEN_WIDTH - paddle.rect.width
        assert paddle._move.current_speed == 0  # stop() was called

    def test_update_normal_movement(self, mock_pygame_patches):
        """Test update() when paddle is not at any boundary (lines 192-193)."""
        paddle = self._create_horizontal_paddle()
        paddle.screen = self._create_mock_screen(left=0, right=SCREEN_WIDTH)

        # Position paddle in middle of screen
        assert paddle.rect is not None
        paddle.rect.x = POS_200
        paddle.rect.left = POS_200
        paddle.rect.right = POS_200 + SIZE_100
        paddle._move.current_speed = 3

        original_x = paddle.rect.x
        paddle.update()

        # move_horizontal adds current_speed to rect.x
        assert paddle.rect.x == original_x + 3


class TestHorizontalPaddleDirectionMethods:
    """Test HorizontalPaddle left/right/stop/speed_up methods."""

    def _create_horizontal_paddle(self):
        """Create a HorizontalPaddle for testing.

        Returns:
            HorizontalPaddle: A configured horizontal paddle.

        """
        return HorizontalPaddle(
            name='test_horizontal',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

    def test_left_method(self, mock_pygame_patches):
        """Test left() sets movement direction left (lines 202-203)."""
        paddle = self._create_horizontal_paddle()
        paddle.left()
        assert paddle._move.current_speed < 0
        assert paddle.dirty == 1

    def test_right_method(self, mock_pygame_patches):
        """Test right() sets movement direction right (lines 212-213)."""
        paddle = self._create_horizontal_paddle()
        paddle.right()
        assert paddle._move.current_speed > 0
        assert paddle.dirty == 1

    def test_stop_method(self, mock_pygame_patches):
        """Test stop() halts movement (lines 222-223)."""
        paddle = self._create_horizontal_paddle()
        paddle.right()  # Start moving
        paddle.stop()
        assert paddle._move.current_speed == 0
        assert paddle.dirty == 1

    def test_speed_up_method(self, mock_pygame_patches):
        """Test speed_up() increases horizontal speed (lines 232-233)."""
        paddle = self._create_horizontal_paddle()
        original_speed_x = paddle._move.speed.x
        paddle.speed_up()
        assert paddle._move.speed.x > original_speed_x


class TestHorizontalPaddleDtTick:
    """Test HorizontalPaddle.dt_tick() method (lines 243-248)."""

    def test_dt_tick_applies_movement(self, mock_pygame_patches):
        """Test dt_tick() applies frame-rate independent movement."""
        paddle = HorizontalPaddle(
            name='test_horizontal',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )
        paddle.right()  # Start moving right
        assert paddle.rect is not None
        original_x = paddle.rect.x

        # Use a large enough dt so that round(speed * dt) > 0
        # speed=5, dt=1.0 -> movement = 5 * 1.0 = 5.0 -> round(5.0) = 5
        paddle.dt_tick(1.0)

        # Position should have changed based on movement and dt
        assert paddle.rect.x != original_x
        assert paddle.dirty == 1

    def test_dt_tick_with_zero_speed(self, mock_pygame_patches):
        """Test dt_tick() with zero speed does not move."""
        paddle = HorizontalPaddle(
            name='test_horizontal',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
        )
        paddle.stop()
        assert paddle.rect is not None
        original_x = paddle.rect.x

        paddle.dt_tick(0.016)

        assert paddle.rect.x == original_x


class TestVerticalPaddleUpdate:
    """Test VerticalPaddle.update() boundary behavior (lines 301-306)."""

    def _create_vertical_paddle(self):
        """Create a VerticalPaddle for testing.

        Returns:
            VerticalPaddle: A configured vertical paddle.

        """
        return VerticalPaddle(
            name='test_vertical',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
        )

    def test_update_clamps_at_top_and_stops(self, mock_pygame_patches):
        """Test update() clamps position and stops at top (lines 301-303)."""
        paddle = self._create_vertical_paddle()
        paddle.screen_height = SCREEN_HEIGHT

        # Position paddle above top boundary
        assert paddle.rect is not None
        paddle.rect.y = -10
        paddle.up()  # Moving up

        paddle.update()

        assert paddle.rect.y == 0
        assert paddle._move.current_speed == 0

    def test_update_clamps_at_bottom_and_stops(self, mock_pygame_patches):
        """Test update() clamps position and stops at bottom (lines 304-306)."""
        paddle = self._create_vertical_paddle()
        paddle.screen_height = SCREEN_HEIGHT

        # Position paddle below bottom boundary
        assert paddle.rect is not None
        paddle.rect.y = SCREEN_HEIGHT + 10
        paddle.rect.height = SIZE_100
        paddle.down()  # Moving down

        paddle.update()

        assert paddle.rect.y == SCREEN_HEIGHT - paddle.rect.height
        assert paddle._move.current_speed == 0


class TestVerticalPaddleSpeedUp:
    """Test VerticalPaddle.speed_up() method (lines 345-346)."""

    def test_speed_up_increases_vertical_speed(self, mock_pygame_patches):
        """Test speed_up() increases vertical speed."""
        paddle = VerticalPaddle(
            name='test_vertical',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
        )

        original_speed_y = paddle._move.speed.y
        paddle.speed_up()

        assert paddle._move.speed.y > original_speed_y
        assert paddle._move.current_speed == paddle._move.speed.y
