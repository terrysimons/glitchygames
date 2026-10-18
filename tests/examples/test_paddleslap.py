#!/usr/bin/env python3
"""Test paddleslap example using centralized mocks."""

import math
import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.examples.paddleslap import (
    PADDLESLAP_SERVE,
    PADDLESLAP_SPAWN_SERVE,
    PADDLESLAP_SPEED_UP,
    Game,
)
from glitchygames.game_objects.ball import (
    BallSpawnMode,
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from tests.mocks.test_mock_factory import MockFactory

# The class's autouse MockFactory patches replace pygame.sprite.LayeredDirty with a mock
# group, so keep the real class for tests that need dt_tick to reach real sprites.
_RealLayeredDirty = pygame.sprite.LayeredDirty


class TestPaddleslapExample:
    """Test paddleslap example using centralized mocks."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Set up pygame mocks for testing."""
        MockFactory.setup_pygame_mocks_with_mocker(mocker)

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Create mock options
        self.mock_options: dict[str, object] = {
            'balls': 1,
            'fps': 60,
            'resolution': '800x600',
            'windowed': True,
            'use_gfxdraw': False,
            'update_type': 'update',
            'fps_refresh_rate': 1000,
            'profile': False,
            'test_flag': False,
            'font_name': 'Arial',
            'font_size': 16,
            'font_bold': False,
            'font_italic': False,
            'font_antialias': True,
            'font_dpi': 72,
            'font_system': 'pygame',
            'log_level': 'info',
            'no_unhandled_events': False,
        }

    def test_paddleslap_game_initialization(self):
        """Test that paddleslap game initializes correctly with centralized mocks."""
        # Create the game instance
        game = Game(options=self.mock_options)

        # Verify basic game properties
        assert game.NAME == 'Paddle Slap'
        assert game.VERSION == '1.1'

        # Verify game components are created
        assert hasattr(game, 'player1')
        assert hasattr(game, 'player2')
        assert hasattr(game, 'balls')
        assert len(game.balls) == 1

        # Verify ball has PaddleSlap's speed-up settings
        ball = game.balls[0]
        assert ball.speed_up_settings == PADDLESLAP_SPEED_UP
        assert math.isclose(ball.speed_up_settings.multiplier, 1.15)
        assert ball.bounce_top_bottom is True
        assert ball.bounce_left_right is False

    def test_paddleslap_ball_speed_up_mechanism(self):
        """Test that the ball speeds up logarithmically on paddle bounces only."""
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        settings = ball.speed_up_settings

        # Paddle bounces are the only trigger (no wall or continuous speed-ups)
        assert settings.triggers == SpeedUpTrigger.PADDLE_BOUNCE
        assert SpeedUpTrigger.WALL_BOUNCE not in settings.triggers
        assert SpeedUpTrigger.CONTINUOUS not in settings.triggers

        # Logarithmic curve on both axes, capped at 500 px/s
        assert settings.curve is SpeedUpCurve.LOGARITHMIC
        assert settings.axes is SpeedUpAxes.BOTH
        assert settings.max_speed == pytest.approx(500.0)

    def test_paddleslap_ball_creation_with_multiple_balls(self):
        """Test creating multiple balls with the new speed-up mechanism."""
        multi_ball_options = self.mock_options.copy()
        multi_ball_options['balls'] = 3

        game = Game(options=multi_ball_options)

        # Verify correct number of balls
        assert len(game.balls) == 3

        # Verify all balls share PaddleSlap's speed-up settings
        for ball in game.balls:
            assert ball.speed_up_settings == PADDLESLAP_SPEED_UP
            assert ball.speed_up_count == 0
            assert ball.bounce_top_bottom is True
            assert ball.bounce_left_right is False

    def test_paddleslap_speed_up_logic(self):
        """Test that a paddle bounce speeds the ball up while preserving its angle.

        PaddleSlap uses PADDLESLAP_SPEED_UP: the LOGARITHMIC curve on BOTH axes with
        multiplier 1.15. The first step (n=0) scales both components by
        1 + 0.15*ln(2) (about 1.104, not 1.15), so the trajectory angle is unchanged.
        See TestBallSpeedUpSweep in tests/game_objects/test_ball_speed_up.py for every
        curve, axis setting, and heading.
        """
        game = Game(options=self.mock_options)
        ball = game.balls[0]

        from glitchygames.movement import Speed

        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y

        ball.on_paddle_bounce()

        # Both components scale by the first logarithmic step, preserving the angle
        expected_ratio = speed_up_step_ratio(
            curve=SpeedUpCurve.LOGARITHMIC, multiplier=1.15, completed_steps=0
        )
        assert math.isclose(expected_ratio, 1.0 + 0.15 * math.log(2.0))
        assert math.isclose(ball.speed.x, initial_x * expected_ratio)
        assert math.isclose(ball.speed.y, initial_y * expected_ratio)
        assert ball.speed_up_count == 1
        assert math.isclose(
            math.atan2(ball.speed.y, ball.speed.x),
            math.atan2(initial_y, initial_x),
        )

    @staticmethod
    def _assert_served_with(ball: BallSprite, serve_settings) -> None:
        """Assert the ball's velocity is a serve within the given settings' band and speed."""
        assert math.hypot(ball.speed.x, ball.speed.y) == pytest.approx(serve_settings.speed)
        angle_from_horizontal = math.degrees(math.atan2(abs(ball.speed.y), abs(ball.speed.x)))
        assert (
            serve_settings.minimum_angle_degrees - 1e-9
            <= angle_from_horizontal
            <= serve_settings.maximum_angle_degrees + 1e-9
        )

    def test_opening_balls_use_paddleslap_serve(self):
        """Opening balls are served Pong-style rather than at one fixed velocity."""
        self.mock_options['balls'] = 3
        game = Game(options=self.mock_options)

        for ball in game.balls:
            assert ball.serve_settings == PADDLESLAP_SERVE
            self._assert_served_with(ball, PADDLESLAP_SERVE)

    def test_random_speed_spawns_use_spawn_serve(self):
        """RANDOM_SPEED spawns are slower diagonal serves, never near-vertical or flat."""
        game = Game(options=self.mock_options)
        game.ball_spawn_mode = BallSpawnMode.ON_PADDLE_COLLISION | BallSpawnMode.RANDOM_SPEED

        for _ in range(50):
            game._spawn_new_ball()
            new_ball = game.balls[-1]
            assert new_ball.serve_settings == PADDLESLAP_SPAWN_SERVE
            self._assert_served_with(new_ball, PADDLESLAP_SPAWN_SERVE)

    def test_fixed_speed_spawns_keep_fixed_velocity(self):
        """Without RANDOM_SPEED, spawned balls keep PaddleSlap's fixed (250, 125) speed."""
        game = Game(options=self.mock_options)
        game.ball_spawn_mode = BallSpawnMode.ON_PADDLE_COLLISION

        game._spawn_new_ball()

        new_ball = game.balls[-1]
        assert (new_ball.speed.x, new_ball.speed.y) == (250.0, 125.0)

    def test_ball_moving_into_paddle_bounces_in_one_game_update(self, mocker):
        """One dt_tick + update: the collision manager finds the overlap and the ball bounces.

        BallSprite.dt_tick no longer checks paddles; the game's update runs
        collisions.check_overlap('balls', 'paddles') and the ball handles the hit.
        """
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        paddle = game.player1
        paddle.snd = mocker.Mock()
        game.all_sprites = _RealLayeredDirty(game.player1, game.player2, ball)
        handle_spy = mocker.spy(ball, 'handle_paddle_collision')
        check_overlap_spy = mocker.spy(game.collisions, 'check_overlap')

        # Just right of the left paddle, moving left: 15 px into it after a 0.05 s frame.
        ball.world_x = float(paddle.rect.right + 5)
        ball.world_y = float(paddle.rect.centery - ball.rect.height // 2)
        ball.speed.x = -300.0
        ball.speed.y = 0.0

        game.dt_tick(0.05)
        assert get_sprite_collision_rect(ball).colliderect(get_sprite_collision_rect(paddle))
        handle_spy.assert_not_called()

        game.update()

        handle_spy.assert_called_once_with(paddle)
        assert any(
            call.args[:2] == ('balls', 'paddles') for call in check_overlap_spy.call_args_list
        )
        assert ball.speed.x > 0
        assert get_sprite_collision_rect(ball).left == paddle.rect.right
        paddle.snd.play.assert_called_once()
        assert ball.alive()

    def test_update_keeps_collided_balls_playable_after_ball_collisions(self, mocker):
        """update() applies the serve-like playability rule after the ball-ball physics."""
        game = Game(options=self.mock_options)
        call_order = mocker.Mock()
        mocker.patch.object(game, '_handle_ball_collisions', call_order.physics)
        mocker.patch.object(game, '_keep_collided_balls_playable', call_order.playability)

        game.update()

        assert [call[0] for call in call_order.mock_calls] == ['physics', 'playability']

    def test_dead_ball_still_in_layer_is_not_bounced(self, mocker):
        """A ball killed this frame (still in the 'balls' layer until cleanup) is skipped."""
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        paddle = game.player1
        handle_spy = mocker.spy(ball, 'handle_paddle_collision')
        mocker.patch.object(ball, 'alive', return_value=False)

        game._on_ball_paddle_collision(ball, paddle)

        handle_spy.assert_not_called()

    def test_paddleslap_game_setup(self):
        """Test that the game setup method works correctly."""
        game = Game(options=self.mock_options)

        # Test setup method
        game.setup()

        # Verify setup completed without errors
        assert hasattr(game, 'target_fps')
        assert math.isclose(game.target_fps, 0.0, abs_tol=1e-9)  # 0 stays uncapped

    def test_paddleslap_args_method(self):
        """Test that the args method works correctly."""
        import argparse

        parser = argparse.ArgumentParser()
        Game.args(parser)

        # Verify that the parser has the expected arguments
        actions = [action.dest for action in parser._actions]
        assert 'balls' in actions
        assert 'version' in actions
