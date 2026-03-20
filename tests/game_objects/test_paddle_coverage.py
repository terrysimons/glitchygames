"""Tests to increase coverage for glitchygames/game_objects/paddle.py.

Targets uncovered lines: 186-193, 202-203, 212-213, 222-223, 232-233,
243-248, 301-306, 345-346.
"""

from glitchygames.game_objects.paddle import HorizontalPaddle, VerticalPaddle
from tests.mocks import MockFactory

# Constants for magic values
POS_100 = 100
POS_200 = 200
POS_300 = 300
SIZE_50 = 50
SIZE_20 = 20
SIZE_100 = 100
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600


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
        """Create a mock screen.

        Returns:
            object: A mock screen with boundary attributes.

        """
        mock_screen = MockFactory.create_pygame_surface_mock()
        mock_screen.left = left
        mock_screen.right = right
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
