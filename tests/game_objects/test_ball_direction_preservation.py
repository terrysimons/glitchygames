#!/usr/bin/env python3
"""Test direction preservation for BallSprite speed-up settings."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.game_objects.ball import (
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpSettings,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from glitchygames.movement import Speed
from tests.mocks.test_mock_factory import MockFactory


def _ball_with_speed_up(**settings_fields) -> BallSprite:
    """Create a ball with the given SpeedUpSettings fields (defaults otherwise).

    Returns:
        BallSprite: The ball.

    """
    return BallSprite(speed_up_settings=SpeedUpSettings(**settings_fields))


class TestBallDirectionPreservation:
    """Test BallSprite direction preservation across different speed-up settings."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)
        # Mock screen dimensions for consistent testing
        self.screen_width = 800
        self.screen_height = 600

    def test_linear_speed_up_preserves_direction(self):
        """Test that linear speed-up preserves direction at all angles."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LINEAR, multiplier=1.5)

        # Test various angles
        test_angles = [
            0,
            15,
            30,
            45,
            60,
            75,
            90,
            105,
            120,
            135,
            150,
            165,
            180,
            195,
            210,
            225,
            240,
            255,
            270,
            285,
            300,
            315,
            330,
            345,
        ]

        for angle_degrees in test_angles:
            # Set speed at specific angle
            angle_radians = math.radians(angle_degrees)
            speed_magnitude = 100.0
            ball.speed.x = speed_magnitude * math.cos(angle_radians)
            ball.speed.y = speed_magnitude * math.sin(angle_radians)

            initial_direction = math.atan2(ball.speed.y, ball.speed.x)

            # Apply linear speed-up
            ball.speed_up()

            # Check direction preservation
            new_direction = math.atan2(ball.speed.y, ball.speed.x)
            assert initial_direction == pytest.approx(new_direction, abs=1e-12), (
                f'Direction not preserved for angle {angle_degrees} degrees'
            )

    def test_logarithmic_both_axes_speed_up_preserves_steep_direction(self):
        """Test that logarithmic speed-up on BOTH axes preserves a steep direction.

        The old logarithmic_x type scaled BOTH components equally; SpeedUpAxes.BOTH is
        its equivalent and preserves the trajectory angle.
        """
        ball = _ball_with_speed_up(
            curve=SpeedUpCurve.LOGARITHMIC, axes=SpeedUpAxes.BOTH, multiplier=1.5
        )

        # Test with non-zero Y component
        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply logarithmic speed-up on both axes
        ball.speed_up()

        # Direction should be preserved (both components scaled equally)
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction, abs=1e-12), (
            'Direction should be preserved with logarithmic speed-up on both axes'
        )

    def test_logarithmic_both_axes_speed_up_preserves_shallow_direction(self):
        """Test that logarithmic speed-up on BOTH axes preserves a shallow direction.

        The old logarithmic_y type scaled BOTH components equally; SpeedUpAxes.BOTH is
        its equivalent and preserves the trajectory angle.
        """
        ball = _ball_with_speed_up(
            curve=SpeedUpCurve.LOGARITHMIC, axes=SpeedUpAxes.BOTH, multiplier=1.3
        )

        # Test with non-zero X component
        ball.speed = Speed(200.0, 100.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply logarithmic speed-up on both axes
        ball.speed_up()

        # Direction should be preserved (both components scaled equally)
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction, abs=1e-12), (
            'Direction should be preserved with logarithmic speed-up on both axes'
        )

    def test_logarithmic_both_speed_up_preserves_direction(self):
        """Test logarithmic both speed-up preserves direction.

        Scales both components equally.
        """
        ball = _ball_with_speed_up(
            curve=SpeedUpCurve.LOGARITHMIC, axes=SpeedUpAxes.BOTH, multiplier=1.2
        )

        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply logarithmic both speed-up
        ball.speed_up()

        # Direction should be preserved (both components scaled equally)
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction), (
            'Direction should be preserved with logarithmic both speed-up'
        )

    def test_direction_preservation_with_bouncing(self):
        """Test direction preservation with bouncing and speed-up."""
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.LINEAR,
                axes=SpeedUpAxes.BOTH,
                multiplier=1.2,
            ),
        )

        # Set initial speed
        ball.speed = Speed(150.0, -100.0)  # moving up, into the top wall
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Simulate wall bounce with linear speed-up (must set world_y)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0
        ball._do_bounce()

        # Y should be reversed, but direction should be preserved relative to the bounce
        # The bounce itself changes direction, but the speed-up should
        # preserve the relative direction
        assert ball.speed.y > 0  # Should be positive after top bounce
        # First linear step from n=0 is exactly the multiplier
        assert ball.speed.x == pytest.approx(150.0 * 1.2)  # X should be scaled
        assert ball.speed.y == pytest.approx(100.0 * 1.2)  # Reversed and scaled

    def test_direction_preserved_with_logarithmic_bouncing(self):
        """Test direction is preserved with logarithmic bouncing.

        SpeedUpAxes.BOTH scales both components equally, so direction is preserved
        relative to the bounce (Y reversal is from the bounce itself, not the speed-up).
        """
        ball = BallSprite(
            bounce_top_bottom=True,
            bounce_left_right=True,
            speed_up_settings=SpeedUpSettings(
                triggers=SpeedUpTrigger.WALL_BOUNCE,
                curve=SpeedUpCurve.LOGARITHMIC,
                axes=SpeedUpAxes.BOTH,
                multiplier=1.3,
            ),
        )

        # Set initial speed
        ball.speed = Speed(100.0, -200.0)  # moving up, into the top wall

        # Simulate wall bounce with logarithmic speed-up (must set world_y)
        assert ball.rect is not None
        ball.rect.y = 0  # Hit top wall
        ball.world_y = 0.0
        ball._do_bounce()

        # Speed-up should scale both components equally (preserving angle relative to bounce)
        # The bounce reverses Y, and speed-up applies the first logarithmic step to both
        expected_ratio = speed_up_step_ratio(
            curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.3, completed_steps=0
        )
        assert ball.speed.x == pytest.approx(100.0 * expected_ratio)
        assert ball.speed.y == pytest.approx(abs(200.0) * expected_ratio)  # Reversed and scaled

    def test_combined_continuous_and_paddle_bounce_direction_behavior(self):
        """Test direction behavior with combined CONTINUOUS and PADDLE_BOUNCE triggers.

        All triggers share one curve, so both steps advance the same LINEAR curve.
        """
        ball = _ball_with_speed_up(
            triggers=SpeedUpTrigger.CONTINUOUS | SpeedUpTrigger.PADDLE_BOUNCE,
            curve=SpeedUpCurve.LINEAR,
            axes=SpeedUpAxes.BOTH,
            multiplier=1.15,
            interval=1.0,
        )

        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Test continuous speed-up (should preserve direction); one interval of game time elapses
        ball._advance_continuous_speed_up(1.0)
        assert ball.speed_up_count == 1

        linear_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(linear_direction), (
            'Linear speed-up should preserve direction'
        )

        # Test paddle bounce on both axes (also preserves direction)
        ball.on_paddle_bounce()
        assert ball.speed_up_count == 2

        bounce_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert linear_direction == pytest.approx(bounce_direction, abs=1e-12), (
            'Paddle bounce speed-up on both axes should preserve direction'
        )

    def test_direction_preservation_with_multiple_linear_speed_ups(self):
        """Test that multiple linear speed-ups preserve direction."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LINEAR, multiplier=1.1)

        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply multiple linear speed-ups
        for _ in range(5):
            ball.speed_up()

        # Direction should still be preserved
        final_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(final_direction, abs=1e-12), (
            'Multiple linear speed-ups should preserve direction'
        )

    def test_direction_preserved_with_multiple_logarithmic_speed_ups(self):
        """Test that multiple logarithmic speed-ups on both axes preserve direction."""
        ball = _ball_with_speed_up(
            curve=SpeedUpCurve.LOGARITHMIC, axes=SpeedUpAxes.BOTH, multiplier=1.2
        )

        ball.speed = Speed(100.0, 200.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply multiple logarithmic speed-ups on both axes
        for _ in range(3):
            ball.speed_up()

        # Direction should be preserved (both components scaled equally each time)
        final_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(final_direction, abs=1e-12), (
            'Multiple logarithmic speed-ups should preserve direction'
        )

    def test_edge_case_pure_horizontal_movement(self):
        """Test direction preservation with pure horizontal movement."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LINEAR, multiplier=1.5)

        # Pure horizontal movement
        ball.speed = Speed(100.0, 0.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Linear speed-up should preserve direction
        ball.speed_up()
        linear_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(linear_direction, abs=1e-12)

        # Logarithmic speed-up on BOTH axes scales both components equally
        ball = _ball_with_speed_up(
            curve=SpeedUpCurve.LOGARITHMIC, axes=SpeedUpAxes.BOTH, multiplier=1.5
        )
        ball.speed = Speed(100.0, 0.0)
        ball.speed_up()
        expected_ratio = speed_up_step_ratio(
            curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.5, completed_steps=0
        )
        assert math.isclose(ball.speed.y, 0.0, abs_tol=1e-9)  # 0 * ratio = 0
        assert ball.speed.x == pytest.approx(100.0 * expected_ratio)  # X also scaled

    def test_edge_case_pure_vertical_movement(self):
        """Test direction preservation with pure vertical movement."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LINEAR, multiplier=1.5)

        # Pure vertical movement
        ball.speed = Speed(0.0, 100.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Linear speed-up should preserve direction
        ball.speed_up()
        linear_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(linear_direction, abs=1e-12)

        # Logarithmic speed-up on BOTH axes scales both components equally
        ball = _ball_with_speed_up(
            curve=SpeedUpCurve.LOGARITHMIC, axes=SpeedUpAxes.BOTH, multiplier=1.5
        )
        ball.speed = Speed(0.0, 100.0)
        ball.speed_up()
        expected_ratio = speed_up_step_ratio(
            curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.5, completed_steps=0
        )
        assert math.isclose(ball.speed.x, 0.0, abs_tol=1e-9)  # 0 * ratio = 0
        assert ball.speed.y == pytest.approx(100.0 * expected_ratio)  # Y also scaled

    def test_direction_preservation_precision(self):
        """Test high-precision direction preservation."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.LINEAR, multiplier=1.234567)

        # Use a very specific angle
        angle_radians = math.radians(33.7)  # A non-standard angle
        speed_magnitude = 100.0
        ball.speed.x = speed_magnitude * math.cos(angle_radians)
        ball.speed.y = speed_magnitude * math.sin(angle_radians)

        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        # Apply linear speed-up
        ball.speed_up()

        # Check very high precision
        new_direction = math.atan2(ball.speed.y, ball.speed.x)
        assert initial_direction == pytest.approx(new_direction, abs=1e-15), (
            'High-precision direction preservation failed'
        )

    @pytest.mark.parametrize(
        ('axes', 'expected_speed_x', 'expected_speed_y'),
        [
            pytest.param(SpeedUpAxes.X_ONLY, 100.0 * 1.5, 100.0, id='x_only_flattens'),
            pytest.param(SpeedUpAxes.Y_ONLY, 100.0, 100.0 * 1.5, id='y_only_steepens'),
        ],
    )
    def test_single_axis_speed_up_changes_direction(self, axes, expected_speed_x, expected_speed_y):
        """Test that X_ONLY / Y_ONLY deliberately change direction (unlike BOTH)."""
        ball = _ball_with_speed_up(curve=SpeedUpCurve.EXPONENTIAL, axes=axes, multiplier=1.5)
        ball.speed = Speed(100.0, 100.0)
        initial_direction = math.atan2(ball.speed.y, ball.speed.x)

        ball.speed_up()

        assert ball.speed.x == pytest.approx(expected_speed_x)
        assert ball.speed.y == pytest.approx(expected_speed_y)
        assert math.atan2(ball.speed.y, ball.speed.x) != pytest.approx(initial_direction)
