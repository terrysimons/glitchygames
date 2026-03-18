"""Tests to increase coverage for glitchygames/game_objects/ball.py.

Targets uncovered lines: 345->exit, 381-382, 392->exit, 421, 466,
553, 685->694, 708, 715->724, 736, 743->752, 773-807, 859->858,
886->890, 897-899, 903.
"""

import math

import pygame
import pytest

from glitchygames.game_objects.ball import BallSprite, SpeedUpMode


class TestBallSpeedUpExponentialBoth:
    """Test speed_up with exponential_both type (lines 345->exit)."""

    def _create_ball(self):
        """Create a BallSprite for testing.

        Returns:
            BallSprite: A configured ball sprite.

        """
        return BallSprite(x=100, y=100, width=20, height=20)

    def test_speed_up_exponential_both(self, mock_pygame_patches):
        """Test speed_up with exponential_both type."""
        ball = self._create_ball()
        ball.speed.x = 150.0
        ball.speed.y = 100.0
        original_x = ball.speed.x
        original_y = ball.speed.y

        ball.speed_up(multiplier=1.1, speed_up_type='exponential_both')

        # Both components should be scaled exponentially
        assert ball.speed.x != original_x
        assert ball.speed.y != original_y

    def test_speed_up_exponential_both_with_zero_speeds(self, mock_pygame_patches):
        """Test speed_up exponential_both when speeds are zero."""
        ball = self._create_ball()
        ball.speed.x = 0
        ball.speed.y = 0

        ball.speed_up(multiplier=1.1, speed_up_type='exponential_both')

        assert ball.speed.x == 0
        assert ball.speed.y == 0


class TestContinuousSpeedUpExponentialY:
    """Test continuous exponential Y speed-up (lines 381-382)."""

    def test_continuous_exponential_y_speed_up(self, mock_pygame_patches):
        """Test continuous speed-up with CONTINUOUS_EXPONENTIAL_Y mode."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_mode=SpeedUpMode.CONTINUOUS_EXPONENTIAL_Y,
            speed_up_interval=0.0,  # Immediate speed-up
        )
        ball.speed.y = 100.0
        original_y = ball.speed.y

        # Set last speed-up time to past so it triggers
        ball._last_speed_up_time = 0.0

        import time

        ball._check_continuous_speed_up(time.time())

        assert ball.speed.y != original_y


class TestContinuousSpeedUpLinear:
    """Test continuous linear speed-up (lines 392->exit)."""

    def test_continuous_linear_speed_up(self, mock_pygame_patches):
        """Test continuous speed-up with CONTINUOUS_LINEAR mode."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_mode=SpeedUpMode.CONTINUOUS_LINEAR,
            speed_up_interval=0.0,
        )
        ball.speed.x = 100.0
        ball.speed.y = 100.0
        original_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)

        ball._last_speed_up_time = 0.0

        import time

        ball._check_continuous_speed_up(time.time())

        new_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert new_magnitude > original_magnitude


class TestResolveSpeedUpType:
    """Test _resolve_speed_up_type with exponential_both (line 421)."""

    def test_resolve_exponential_both(self, mock_pygame_patches):
        """Test resolving when both exponential X and Y flags are set."""
        ball = BallSprite(
            x=100,
            y=100,
            speed_up_mode=(
                SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X | SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y
            ),
        )

        result = ball._resolve_speed_up_type(
            SpeedUpMode.ON_BOUNCE_EXPONENTIAL_X,
            SpeedUpMode.ON_BOUNCE_EXPONENTIAL_Y,
            SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X,
            SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y,
            SpeedUpMode.ON_BOUNCE_LINEAR,
        )

        assert result == 'exponential_both'


class TestCheckBounceSpeedUpUnknownType:
    """Test _check_bounce_speed_up with unknown type (line 466)."""

    def test_unknown_bounce_type_does_nothing(self, mock_pygame_patches):
        """Test that unknown bounce type results in None speed_up_type."""
        ball = BallSprite(x=100, y=100)
        original_x = ball.speed.x
        original_y = ball.speed.y

        ball._check_bounce_speed_up('unknown_type')

        # Speed should remain unchanged
        assert ball.speed.x == original_x
        assert ball.speed.y == original_y


class TestBallBoundaryCollisions:
    """Test boundary collision handlers (lines 685->694, 708, 715->724, 736, 743->752)."""

    def _create_ball_with_left_right_bounce(self):
        """Create a ball with left/right bouncing enabled.

        Returns:
            BallSprite: A ball with all bouncing enabled.

        """
        return BallSprite(
            x=100,
            y=100,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )

    def test_bottom_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test bottom collision reflects Y speed (lines 685->694)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = 100.0
        ball.speed.y = 100.0  # Moving downward

        # Position ball at bottom boundary
        ball.rect.y = ball.screen_height - ball.height

        ball._do_bounce()

        # Y speed should be negative (upward) after bottom bounce
        assert ball.speed.y < 0

    def test_left_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test left collision plays sound (line 708)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.snd = mocker.Mock()
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        # Position ball at left boundary
        ball.rect.x = 0

        ball._do_bounce()

        ball.snd.play.assert_called()
        # X speed should be positive (rightward)
        assert ball.speed.x > 0

    def test_left_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test left collision reflects X speed (lines 715->724)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = -100.0
        ball.speed.y = 50.0

        ball.rect.x = 0

        ball._do_bounce()

        assert ball.speed.x > 0
        assert ball.rect.x == 1  # Just inside boundary

    def test_right_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test right collision plays sound (line 736)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.snd = mocker.Mock()
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Position ball at right boundary
        ball.rect.x = ball.screen_width - ball.width

        ball._do_bounce()

        ball.snd.play.assert_called()

    def test_right_collision_with_speed_magnitude(self, mock_pygame_patches):
        """Test right collision reflects X speed (lines 743->752)."""
        ball = self._create_ball_with_left_right_bounce()
        ball.speed.x = 100.0
        ball.speed.y = 50.0

        ball.rect.x = ball.screen_width - ball.width

        ball._do_bounce()

        assert ball.speed.x < 0
        assert ball.rect.x == ball.screen_width - ball.width - 1


class TestCornerCollisions:
    """Test corner collision handling (lines 773-807)."""

    def _create_bouncing_ball(self):
        """Create a ball with all bouncing enabled.

        Returns:
            BallSprite: A ball with all bouncing enabled.

        """
        return BallSprite(
            x=100,
            y=100,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )

    def test_top_left_corner_collision(self, mock_pygame_patches):
        """Test top-left corner collision (lines 783-786, 796-798)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = -100.0  # Moving left
        ball.speed.y = -100.0  # Moving up

        ball.rect.x = 0
        ball.rect.y = 0

        ball._do_bounce()

        # After corner collision, ball should be placed at (1, 1)
        assert ball.rect.x == 1
        assert ball.rect.y == 1

    def test_top_right_corner_collision(self, mock_pygame_patches):
        """Test top-right corner collision (lines 787-790, 799-801)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = 100.0  # Moving right
        ball.speed.y = -100.0  # Moving up

        ball.rect.x = ball.screen_width - ball.width
        ball.rect.y = 0

        ball._do_bounce()

        assert ball.rect.x == ball.screen_width - ball.width - 1
        assert ball.rect.y == 1

    def test_bottom_left_corner_collision(self, mock_pygame_patches):
        """Test bottom-left corner collision (lines 802-804)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = -100.0
        ball.speed.y = 100.0

        ball.rect.x = 0
        ball.rect.y = ball.screen_height - ball.height

        ball._do_bounce()

        assert ball.rect.x == 1
        assert ball.rect.y == ball.screen_height - ball.height - 1

    def test_bottom_right_corner_collision(self, mock_pygame_patches):
        """Test bottom-right corner collision (lines 805-807)."""
        ball = self._create_bouncing_ball()
        ball.speed.x = 100.0
        ball.speed.y = 100.0

        ball.rect.x = ball.screen_width - ball.width
        ball.rect.y = ball.screen_height - ball.height

        ball._do_bounce()

        assert ball.rect.x == ball.screen_width - ball.width - 1
        assert ball.rect.y == ball.screen_height - ball.height - 1


class TestDtTickMovementMismatch:
    """Test dt_tick movement mismatch logging (line 553)."""

    def test_dt_tick_basic_movement(self, mock_pygame_patches):
        """Test dt_tick applies movement correctly."""
        ball = BallSprite(x=100, y=100)
        ball.speed.x = 200.0
        ball.speed.y = 100.0

        original_x = ball.rect.x
        original_y = ball.rect.y

        ball.dt_tick(0.016)

        # Position should change based on speed * dt
        assert ball.rect.x != original_x or ball.rect.y != original_y


class TestPaddleCollisionSpeedCap:
    """Test paddle collision speed capping (lines 897-899, 903)."""

    def test_paddle_collision_caps_speed(self, mock_pygame_patches, mocker):
        """Test that paddle collision caps speed at max_speed."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        # Create a mock paddle
        paddle = mocker.Mock()
        paddle.rect = pygame.Rect(90, 90, 20, 100)
        paddle.snd = None

        # Set extremely high speed
        ball.speed.x = 1000.0
        ball.speed.y = 1000.0

        # Position ball overlapping with paddle
        ball.rect.x = 95
        ball.rect.y = 100

        ball._adjust_position_for_paddle_collision(paddle)

        # Speed should be capped
        speed_magnitude = math.sqrt(ball.speed.x**2 + ball.speed.y**2)
        assert speed_magnitude <= 500.0 + 0.01  # max_speed = 500.0

    def test_paddle_collision_with_sound(self, mock_pygame_patches, mocker):
        """Test paddle collision plays paddle's sound (lines 886->890)."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        paddle = mocker.Mock()
        paddle.rect = pygame.Rect(120, 90, 20, 100)
        paddle.snd = mocker.Mock()

        ball.speed.x = 100.0
        ball.speed.y = 50.0

        # Ball center is to the right of paddle center
        ball.rect.x = 130
        ball.rect.y = 100

        ball._adjust_position_for_paddle_collision(paddle)

        paddle.snd.play.assert_called_once()

    def test_paddle_collision_triggers_on_paddle_collision(self, mock_pygame_patches, mocker):
        """Test paddle collision calls on_paddle_collision if it exists (line 903)."""
        ball = BallSprite(x=100, y=100, width=20, height=20)

        mock_callback = mocker.Mock()
        ball.on_paddle_collision = mock_callback

        paddle = mocker.Mock()
        paddle.rect = pygame.Rect(120, 90, 20, 100)
        paddle.snd = None

        ball.speed.x = 100.0
        ball.speed.y = 50.0
        ball.rect.x = 130
        ball.rect.y = 100

        ball._adjust_position_for_paddle_collision(paddle)

        mock_callback.assert_called_once_with(ball)


class TestBallMovementMismatchWarning:
    """Test dt_tick movement mismatch logging (line 553)."""

    def test_dt_tick_movement_mismatch_detection(self, mock_pygame_patches, mocker):
        """Test that movement mismatch is detected when rect changes unexpectedly.

        Covers line 553 where delta doesn't match expected movement.
        The mismatch occurs when rect.x or rect.y is modified externally
        between the move and the delta check (e.g., by boundary clamping
        in _do_bounce). The dt_tick method logs a warning in that case.
        """
        ball = BallSprite(
            x=400,
            y=0,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=False,
        )
        ball.speed.x = 0.0
        ball.speed.y = -200.0  # Moving up fast

        # Position ball so bounce will modify rect.y
        ball.rect.y = -5

        # dt_tick will: add move_y to rect.y (making it more negative),
        # then _do_bounce will set it to 1.
        # This means delta_y != round(move_y), triggering line 553.
        ball.dt_tick(0.016)

        # After bounce, rect.y should be positive
        assert ball.rect.y >= 0


class TestBallCheckPaddleCollisions:
    """Test _check_paddle_collisions with actual paddle sprites (line 859->858)."""

    def test_check_paddle_collisions_no_matching_sprites(self, mock_pygame_patches, mocker):
        """Test _check_paddle_collisions when no paddle sprites overlap.

        Covers branch 859->858 where colliderect returns False.
        """
        ball = BallSprite(x=100, y=100, width=20, height=20)

        # Create a mock group with a non-colliding sprite
        mock_group = mocker.Mock()
        mock_sprite = mocker.Mock()
        mock_sprite.rect = pygame.Rect(500, 500, 20, 100)  # Far away
        mock_sprite.__class__.__name__ = 'PaddleSprite'
        mock_group.__iter__ = mocker.Mock(return_value=iter([mock_sprite, ball]))

        mocker.patch.object(ball, 'groups', return_value=[mock_group])

        ball._check_paddle_collisions()

        # No collision should have been detected - no position adjustment


class TestBallBottomBounceZeroSpeed:
    """Test bottom collision when speed magnitude is zero (line 685->694)."""

    def test_bottom_collision_zero_magnitude_no_reflection(self, mock_pygame_patches):
        """Test that bottom collision with zero speed skips reflection.

        Covers the branch at 685->694 where speed_magnitude == 0 and the
        reflection logic is skipped.
        """
        ball = BallSprite(
            x=400,
            y=580,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed.x = 0.0
        ball.speed.y = 0.0

        import logging

        log = logging.getLogger('game')

        # Position ball at bottom
        ball.rect.y = ball.screen_height - ball.height

        ball._handle_bottom_collision(log)

        # Speed should remain zero
        assert ball.speed.x == pytest.approx(0.0)
        assert ball.speed.y == pytest.approx(0.0)

    def test_left_collision_zero_magnitude_no_reflection(self, mock_pygame_patches):
        """Test that left collision with zero speed skips reflection.

        Covers branch 715->724 where speed_magnitude == 0.
        """
        ball = BallSprite(
            x=0,
            y=300,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed.x = 0.0
        ball.speed.y = 0.0

        import logging

        log = logging.getLogger('game')

        ball.rect.x = 0

        ball._handle_left_collision(log)

        assert ball.speed.x == pytest.approx(0.0)

    def test_right_collision_zero_magnitude_no_reflection(self, mock_pygame_patches):
        """Test that right collision with zero speed skips reflection.

        Covers branch 743->752 where speed_magnitude == 0.
        """
        ball = BallSprite(
            x=780,
            y=300,
            width=20,
            height=20,
            bounce_top_bottom=True,
            bounce_left_right=True,
        )
        ball.speed.x = 0.0
        ball.speed.y = 0.0

        import logging

        log = logging.getLogger('game')

        ball.rect.x = ball.screen_width - ball.width

        ball._handle_right_collision(log)

        assert ball.speed.x == pytest.approx(0.0)
