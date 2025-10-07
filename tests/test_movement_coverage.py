"""Test coverage for the movement module.

This module tests the Horizontal, Vertical, and Speed classes which are
essential for sprite movement in the game engine. These classes handle:

1. Horizontal movement (left, right, stop)
2. Vertical movement (up, down, stop)
3. Speed management and acceleration
4. Speed arithmetic operations

Without these tests, the movement module coverage remains incomplete
as the core movement functionality is not exercised.
"""

from glitchygames.movement import Horizontal, Speed, Vertical

# Constants for test values
EXPECTED_SPEED_X = 5
EXPECTED_SPEED_Y = 3
EXPECTED_NEGATIVE_SPEED = -5
EXPECTED_POSITIVE_SPEED = 5
EXPECTED_CHANGE_SPEED = 10
EXPECTED_NEGATIVE_CHANGE = -3
EXPECTED_POSITIVE_CHANGE = 3
EXPECTED_DEFAULT_INCREMENT = 0.2
EXPECTED_CUSTOM_INCREMENT = 0.5
EXPECTED_SPEED_UP_RESULT = 2.5
EXPECTED_NEGATIVE_SPEED_UP = -2.5
EXPECTED_MULTIPLIED_X = 4.0
EXPECTED_MULTIPLIED_Y = 6.0
EXPECTED_NEGATIVE_MULTIPLIED_X = -2.0
EXPECTED_NEGATIVE_MULTIPLIED_Y = -3.0


class TestHorizontalMovementCoverage:
    """Test coverage for Horizontal movement class."""

    def test_horizontal_initialization(self):  # noqa: PLR6301
        """Test Horizontal initialization."""
        speed = Speed(x=EXPECTED_SPEED_X, y=0)
        horizontal = Horizontal(speed)

        assert horizontal.speed == speed
        assert horizontal.current_speed == EXPECTED_SPEED_X

    def test_horizontal_left_movement(self):  # noqa: PLR6301
        """Test moving left."""
        speed = Speed(x=EXPECTED_SPEED_X, y=0)
        horizontal = Horizontal(speed)

        horizontal.left()

        assert horizontal.current_speed == EXPECTED_NEGATIVE_SPEED

    def test_horizontal_right_movement(self):  # noqa: PLR6301
        """Test moving right."""
        speed = Speed(x=EXPECTED_SPEED_X, y=0)
        horizontal = Horizontal(speed)

        horizontal.right()

        assert horizontal.current_speed == EXPECTED_POSITIVE_SPEED

    def test_horizontal_stop(self):  # noqa: PLR6301
        """Test stopping horizontal movement."""
        speed = Speed(x=EXPECTED_SPEED_X, y=0)
        horizontal = Horizontal(speed)

        horizontal.stop()

        assert horizontal.current_speed == 0

    def test_horizontal_change_speed(self):  # noqa: PLR6301
        """Test changing speed directly."""
        speed = Speed(x=EXPECTED_SPEED_X, y=0)
        horizontal = Horizontal(speed)

        horizontal._change_speed(EXPECTED_CHANGE_SPEED)

        assert horizontal.current_speed == EXPECTED_CHANGE_SPEED

    def test_horizontal_negative_speed(self):  # noqa: PLR6301
        """Test horizontal movement with negative speed."""
        speed = Speed(x=EXPECTED_NEGATIVE_CHANGE, y=0)
        horizontal = Horizontal(speed)

        horizontal.left()

        assert horizontal.current_speed == EXPECTED_POSITIVE_CHANGE  # -(-3) = 3

    def test_horizontal_zero_speed(self):  # noqa: PLR6301
        """Test horizontal movement with zero speed."""
        speed = Speed(x=0, y=0)
        horizontal = Horizontal(speed)

        horizontal.right()

        assert horizontal.current_speed == 0


class TestVerticalMovementCoverage:
    """Test coverage for Vertical movement class."""

    def test_vertical_initialization(self):  # noqa: PLR6301
        """Test Vertical initialization."""
        speed = Speed(x=0, y=EXPECTED_SPEED_X)
        vertical = Vertical(speed)

        assert vertical.speed == speed
        assert vertical.current_speed == EXPECTED_SPEED_X

    def test_vertical_up_movement(self):  # noqa: PLR6301
        """Test moving up."""
        speed = Speed(x=0, y=EXPECTED_SPEED_X)
        vertical = Vertical(speed)

        vertical.up()

        assert vertical.current_speed == EXPECTED_NEGATIVE_SPEED

    def test_vertical_down_movement(self):  # noqa: PLR6301
        """Test moving down."""
        speed = Speed(x=0, y=EXPECTED_SPEED_X)
        vertical = Vertical(speed)

        vertical.down()

        assert vertical.current_speed == EXPECTED_POSITIVE_SPEED

    def test_vertical_stop(self):  # noqa: PLR6301
        """Test stopping vertical movement."""
        speed = Speed(x=0, y=EXPECTED_SPEED_X)
        vertical = Vertical(speed)

        vertical.stop()

        assert vertical.current_speed == 0

    def test_vertical_change_speed(self):  # noqa: PLR6301
        """Test changing speed directly."""
        speed = Speed(x=0, y=EXPECTED_SPEED_X)
        vertical = Vertical(speed)

        vertical._change_speed(EXPECTED_CHANGE_SPEED)

        assert vertical.current_speed == EXPECTED_CHANGE_SPEED

    def test_vertical_negative_speed(self):  # noqa: PLR6301
        """Test vertical movement with negative speed."""
        speed = Speed(x=0, y=EXPECTED_NEGATIVE_CHANGE)
        vertical = Vertical(speed)

        vertical.up()

        assert vertical.current_speed == EXPECTED_POSITIVE_CHANGE  # -(-3) = 3

    def test_vertical_zero_speed(self):  # noqa: PLR6301
        """Test vertical movement with zero speed."""
        speed = Speed(x=0, y=0)
        vertical = Vertical(speed)

        vertical.down()

        assert vertical.current_speed == 0


class TestSpeedCoverage:
    """Test coverage for Speed class."""

    def test_speed_initialization_default(self):  # noqa: PLR6301
        """Test Speed initialization with default values."""
        speed = Speed()

        assert speed.x == 0
        assert speed.y == 0
        assert speed.increment == EXPECTED_DEFAULT_INCREMENT

    def test_speed_initialization_custom(self):  # noqa: PLR6301
        """Test Speed initialization with custom values."""
        speed = Speed(x=EXPECTED_SPEED_X, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        assert speed.x == EXPECTED_SPEED_X
        assert speed.y == EXPECTED_SPEED_Y
        assert speed.increment == EXPECTED_CUSTOM_INCREMENT

    def test_speed_up_both_directions(self):  # noqa: PLR6301
        """Test speeding up in both directions."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)
        initial_x = speed.x
        initial_y = speed.y

        speed.speed_up()

        assert speed.x == initial_x + EXPECTED_CUSTOM_INCREMENT
        assert speed.y == initial_y + EXPECTED_CUSTOM_INCREMENT

    def test_speed_up_horizontal_positive(self):  # noqa: PLR6301
        """Test speeding up horizontally with positive speed."""
        speed = Speed(x=2, y=0, increment=EXPECTED_CUSTOM_INCREMENT)

        speed.speed_up_horizontal()

        assert speed.x == EXPECTED_SPEED_UP_RESULT

    def test_speed_up_horizontal_negative(self):  # noqa: PLR6301
        """Test speeding up horizontally with negative speed."""
        speed = Speed(x=-2, y=0, increment=EXPECTED_CUSTOM_INCREMENT)

        speed.speed_up_horizontal()

        assert speed.x == EXPECTED_NEGATIVE_SPEED_UP  # -2 + (-0.5) = -2.5

    def test_speed_up_horizontal_zero(self):  # noqa: PLR6301
        """Test speeding up horizontally with zero speed."""
        speed = Speed(x=0, y=0, increment=EXPECTED_CUSTOM_INCREMENT)

        speed.speed_up_horizontal()

        assert speed.x == EXPECTED_CUSTOM_INCREMENT

    def test_speed_up_vertical_positive(self):  # noqa: PLR6301
        """Test speeding up vertically with positive speed."""
        speed = Speed(x=0, y=2, increment=EXPECTED_CUSTOM_INCREMENT)

        speed.speed_up_vertical()

        assert speed.y == EXPECTED_SPEED_UP_RESULT

    def test_speed_up_vertical_negative(self):  # noqa: PLR6301
        """Test speeding up vertically with negative speed."""
        speed = Speed(x=0, y=-2, increment=EXPECTED_CUSTOM_INCREMENT)

        speed.speed_up_vertical()

        assert speed.y == EXPECTED_NEGATIVE_SPEED_UP  # -2 + (-0.5) = -2.5

    def test_speed_up_vertical_zero(self):  # noqa: PLR6301
        """Test speeding up vertically with zero speed."""
        speed = Speed(x=0, y=0, increment=EXPECTED_CUSTOM_INCREMENT)

        speed.speed_up_vertical()

        assert speed.y == EXPECTED_CUSTOM_INCREMENT

    def test_speed_multiplication(self):  # noqa: PLR6301
        """Test speed multiplication."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        result = speed * 2.0

        assert result.x == EXPECTED_MULTIPLIED_X
        assert result.y == EXPECTED_MULTIPLIED_Y
        assert result.increment == EXPECTED_CUSTOM_INCREMENT
        assert result is not speed  # Should be a new instance

    def test_speed_inplace_multiplication(self):  # noqa: PLR6301
        """Test in-place speed multiplication."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        speed *= 2.0
        result = speed

        assert speed.x == EXPECTED_MULTIPLIED_X
        assert speed.y == EXPECTED_MULTIPLIED_Y
        assert speed.increment == EXPECTED_CUSTOM_INCREMENT
        assert result is speed  # Should return self

    def test_speed_multiplication_with_zero(self):  # noqa: PLR6301
        """Test speed multiplication with zero."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        result = speed * 0.0

        assert result.x == 0.0
        assert result.y == 0.0
        assert result.increment == EXPECTED_CUSTOM_INCREMENT

    def test_speed_multiplication_with_negative(self):  # noqa: PLR6301
        """Test speed multiplication with negative scalar."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        result = speed * -1.0

        assert result.x == EXPECTED_NEGATIVE_MULTIPLIED_X
        assert result.y == EXPECTED_NEGATIVE_MULTIPLIED_Y
        assert result.increment == EXPECTED_CUSTOM_INCREMENT

    def test_speed_inplace_multiplication_with_zero(self):  # noqa: PLR6301
        """Test in-place speed multiplication with zero."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        speed *= 0.0

        assert speed.x == 0.0
        assert speed.y == 0.0
        assert speed.increment == EXPECTED_CUSTOM_INCREMENT

    def test_speed_inplace_multiplication_with_negative(self):  # noqa: PLR6301
        """Test in-place speed multiplication with negative scalar."""
        speed = Speed(x=2, y=EXPECTED_SPEED_Y, increment=EXPECTED_CUSTOM_INCREMENT)

        speed *= -1.0

        assert speed.x == EXPECTED_NEGATIVE_MULTIPLIED_X
        assert speed.y == EXPECTED_NEGATIVE_MULTIPLIED_Y
        assert speed.increment == EXPECTED_CUSTOM_INCREMENT
