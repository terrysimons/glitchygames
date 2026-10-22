"""Tests for paddle game objects."""

import pygame

from glitchygames.game_objects.paddle import BasePaddle, HorizontalPaddle, VerticalPaddle
from glitchygames.game_objects.sounds import SFX, load_sound
from glitchygames.movement.horizontal import Horizontal
from glitchygames.movement.vertical import Vertical

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

    def _create_screen(self, left=0, right=800, top=0, bottom=600):
        """Create a real screen-sized surface for the paddle's boundary checks.

        get_rect() gives the Rect is_at_right_of_screen, is_at_left_of_screen, etc. use.

        Returns:
            pygame.Surface: The screen.

        """
        width = right - left
        height = bottom - top
        return pygame.Surface((width, height))


class TestPaddleBasicFunctionality(BasePaddleTest):
    """Test basic paddle functionality without complex movement."""

    def test_base_paddle_initialization(self):
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

    def test_base_paddle_initialization_with_groups(self):
        """Test BasePaddle initialization with custom groups."""
        groups = pygame.sprite.LayeredDirty()
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
        assert paddle in groups

    def test_base_paddle_initialization_without_groups(self):
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

    def test_base_paddle_initialization_with_collision_sound(self):
        """Test BasePaddle initialization with collision sound."""
        paddle = BasePaddle(
            axis=Horizontal,
            speed=5,
            name='test_paddle',
            color=(255, 0, 0),
            x=POS_100,
            y=POS_200,
            width=SIZE_50,
            height=SIZE_20,
            collision_sound=SFX.SLAP,
        )

        assert isinstance(paddle.snd, pygame.mixer.Sound)
        assert paddle.snd.get_raw() == load_sound(SFX.SLAP).get_raw()

    def test_base_paddle_initialization_without_collision_sound(self):
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


class TestPaddleDrawing(BasePaddleTest):
    """A paddle is a solid rectangle of its color, drawn where its rect is."""

    def test_paddle_image_is_filled_with_its_color(self):
        """Every pixel of the paddle's image is its color."""
        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
        )

        assert paddle.image.get_size() == (SIZE_20, SIZE_100)
        # One color fills the whole image: no other color shrinks the bounding box of a
        # threshold match, and the count of matching pixels is the area
        matching_pixels = pygame.transform.threshold(
            None, paddle.image, search_color=(0, 0, 255), threshold=(0, 0, 0, 255), set_behavior=0
        )
        assert matching_pixels == SIZE_20 * SIZE_100

    def test_paddle_draws_onto_the_display(self):
        """Drawing the paddle's group puts its color on the display at its rect, nothing else."""
        display = pygame.display.get_surface()
        display.fill((0, 0, 0))
        groups = pygame.sprite.LayeredDirty()
        paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
            groups=groups,
        )

        groups.draw(display)

        paddle_area = display.subsurface(paddle.rect)
        assert pygame.transform.average_color(paddle_area)[:3] == (0, 255, 0)
        # Everything outside the paddle stayed black: the green pixels are exactly its area
        green_pixels = pygame.transform.threshold(
            None, display, search_color=(0, 255, 0), threshold=(0, 0, 0, 255), set_behavior=0
        )
        assert green_pixels == SIZE_100 * SIZE_20


class TestPaddleMovement(BasePaddleTest):
    """Test paddle movement functionality."""

    def test_move_horizontal(self):
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

    def test_move_vertical(self):
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

    def test_is_at_bottom_of_screen(self):
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

    def test_is_at_top_of_screen(self):
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

    def test_is_at_left_of_screen(self):
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
        paddle.screen = self._create_screen(left=0)

        # Test at left - paddle at x=0 with speed=5 would go to x=-5, which is < screen.left=0
        assert paddle.rect is not None
        paddle.rect.x = 0
        paddle._move.current_speed = -5  # Moving left
        assert paddle.is_at_left_of_screen() is True

        # Test not at left
        paddle.rect.x = POS_100
        paddle._move.current_speed = 5  # Moving right
        assert paddle.is_at_left_of_screen() is False

    def test_is_at_right_of_screen(self):
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
        paddle.screen = self._create_screen(right=800)

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

    def test_horizontal_paddle_initialization(self):
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

    def test_horizontal_paddle_initialization_with_groups(self):
        """Test HorizontalPaddle initialization with custom groups."""
        groups = pygame.sprite.LayeredDirty()
        paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
            groups=groups,
        )

        assert groups in paddle.groups()
        assert paddle in groups

    def test_horizontal_paddle_initialization_with_collision_sound(
        self,
    ):
        """Test HorizontalPaddle initialization with collision sound."""
        paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(POS_200, POS_300),
            color=(0, 255, 0),
            speed=5,
            collision_sound=SFX.SLAP,
        )

        assert isinstance(paddle.snd, pygame.mixer.Sound)
        assert paddle.snd.get_raw() == load_sound(SFX.SLAP).get_raw()


class TestVerticalPaddle(BasePaddleTest):
    """Test VerticalPaddle class."""

    def test_vertical_paddle_initialization(self):
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

    def test_vertical_paddle_initialization_with_groups(self):
        """Test VerticalPaddle initialization with custom groups."""
        groups = pygame.sprite.LayeredDirty()
        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
            groups=groups,
        )

        assert groups in paddle.groups()
        assert paddle in groups

    def test_vertical_paddle_initialization_with_collision_sound(self):
        """Test VerticalPaddle initialization with collision sound."""
        paddle = VerticalPaddle(
            name='vertical_paddle',
            size=(SIZE_20, SIZE_100),
            position=(POS_200, POS_300),
            color=(0, 0, 255),
            speed=5,
            collision_sound=SFX.SLAP,
        )

        assert isinstance(paddle.snd, pygame.mixer.Sound)
        assert paddle.snd.get_raw() == load_sound(SFX.SLAP).get_raw()


class TestPaddleIntegration(BasePaddleTest):
    """Test paddle integration scenarios."""

    def test_horizontal_paddle_full_cycle(self):
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
        paddle.screen = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        paddle.rect.x = 0
        paddle.rect.left = 0  # Set left to 0
        paddle._move.current_speed = -5  # Moving left
        assert paddle.is_at_left_of_screen() is True

    def test_vertical_paddle_full_cycle(self):
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

    def test_paddle_boundary_behavior(self):
        """Test paddle behavior at boundaries."""
        # Test horizontal paddle at boundaries
        h_paddle = HorizontalPaddle(
            name='horizontal_paddle',
            size=(SIZE_100, SIZE_20),
            position=(0, POS_300),
            color=(0, 255, 0),
            speed=5,
        )

        h_paddle.screen = self._create_screen(left=0, right=800)
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

        v_paddle.screen = self._create_screen(top=0)
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

    def _create_screen(self, left=0, right=SCREEN_WIDTH):
        """Create a real screen-sized surface for the paddle's boundary checks.

        Returns:
            pygame.Surface: The screen.

        """
        width = right - left
        return pygame.Surface((width, SCREEN_HEIGHT))

    def test_update_clamps_at_left_boundary(self):
        """Test update() clamps paddle at left boundary after dt_tick overshoot."""
        paddle = self._create_horizontal_paddle()
        paddle.screen = self._create_screen(left=0)

        # Simulate paddle that overshot left boundary via dt_tick
        assert paddle.rect is not None
        paddle.rect.x = -5
        paddle._move.current_speed = -5

        paddle.update()

        assert paddle.rect.x == 0
        assert paddle._move.current_speed == 0  # stop() was called

    def test_update_clamps_at_right_boundary(self):
        """Test update() clamps paddle at right boundary after dt_tick overshoot."""
        paddle = self._create_horizontal_paddle()
        paddle.screen = self._create_screen(right=SCREEN_WIDTH)

        # Simulate paddle that overshot right boundary via dt_tick
        assert paddle.rect is not None
        paddle.rect.x = SCREEN_WIDTH - SIZE_100 + 5
        paddle._move.current_speed = 5

        paddle.update()

        assert paddle.rect.x == SCREEN_WIDTH - paddle.rect.width
        assert paddle._move.current_speed == 0  # stop() was called

    def test_update_no_clamp_when_in_bounds(self):
        """Test update() does not modify position when paddle is within bounds."""
        paddle = self._create_horizontal_paddle()
        paddle.screen = self._create_screen(left=0, right=SCREEN_WIDTH)

        # Position paddle in middle of screen
        assert paddle.rect is not None
        paddle.rect.x = POS_200
        paddle._move.current_speed = 3

        original_x = paddle.rect.x
        paddle.update()

        # update() only clamps -- movement happens in dt_tick()
        assert paddle.rect.x == original_x


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

    def test_left_method(self):
        """Test left() sets movement direction left (lines 202-203)."""
        paddle = self._create_horizontal_paddle()
        paddle.left()
        assert paddle._move.current_speed < 0
        assert paddle.dirty == 1

    def test_right_method(self):
        """Test right() sets movement direction right (lines 212-213)."""
        paddle = self._create_horizontal_paddle()
        paddle.right()
        assert paddle._move.current_speed > 0
        assert paddle.dirty == 1

    def test_stop_method(self):
        """Test stop() halts movement (lines 222-223)."""
        paddle = self._create_horizontal_paddle()
        paddle.right()  # Start moving
        paddle.stop()
        assert paddle._move.current_speed == 0
        assert paddle.dirty == 1

    def test_speed_up_method(self):
        """Test speed_up() increases horizontal speed (lines 232-233)."""
        paddle = self._create_horizontal_paddle()
        original_speed_x = paddle._move.speed.x
        paddle.speed_up()
        assert paddle._move.speed.x > original_speed_x


class TestHorizontalPaddleDtTick:
    """Test HorizontalPaddle.dt_tick() method (lines 243-248)."""

    def test_dt_tick_applies_movement(self):
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

    def test_dt_tick_with_zero_speed(self):
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

    def test_update_clamps_at_top_and_stops(self):
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

    def test_update_clamps_at_bottom_and_stops(self):
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

    def test_speed_up_increases_vertical_speed(self):
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
