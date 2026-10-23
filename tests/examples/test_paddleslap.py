#!/usr/bin/env python3
"""Test the PaddleSlap example game (real pygame, real sprites)."""

from __future__ import annotations

import logging
import math
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.events.base import HashableEvent
from glitchygames.examples.paddleslap import (
    GAME_OVER_IDLE_SECONDS,
    PADDLESLAP_DEMO_PATH,
    PADDLESLAP_SERVE,
    PADDLESLAP_SPAWN_SERVE,
    PADDLESLAP_SPEED_UP,
    Game,
    PaddleSlapGameOverScene,
)
from glitchygames.examples.paddleslap import log as paddleslap_log
from glitchygames.game_objects.ball import (
    BallSpawnMode,
    BallSprite,
    SpeedUpAxes,
    SpeedUpCurve,
    SpeedUpTrigger,
    speed_up_step_ratio,
)
from glitchygames.randomness import RANDOM_STREAM_KIND, reset_streams, stream_seed
from glitchygames.sources import advance_frame_clock
from glitchygames.world import position_world_sprites

if TYPE_CHECKING:
    from pytest_mock import MockType

PADDLESLAP_STREAM_TEST_SEED = 41


def _reference_stream(name: str) -> random.Random:
    """Return a fresh copy of what random_stream(name) is after PADDLESLAP_STREAM_TEST_SEED.

    Returns:
        A generator seeded as the named stream is.

    """
    return random.Random(
        stream_seed(kind=RANDOM_STREAM_KIND, master_seed=PADDLESLAP_STREAM_TEST_SEED, name=name)
    )


# Options the tests create PaddleSlap with
PADDLESLAP_TEST_OPTIONS: dict[str, object] = {
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


class TestPaddleslapExample:
    """Test the PaddleSlap example game (real pygame, real sprites)."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        self.mock_options: dict[str, object] = dict(PADDLESLAP_TEST_OPTIONS)

    def test_paddleslap_game_initialization(self):
        """Test that the PaddleSlap game initializes correctly."""
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

    def test_game_initialization_leaves_global_random_state_alone(self):
        """Creating the game must not reseed Python's process-wide random module."""
        random_state_before = random.getstate()

        Game(options=self.mock_options)

        random_state_is_unchanged = random.getstate() == random_state_before
        assert random_state_is_unchanged, 'Game() reseeded the global random module'

    def test_opening_ball_colors_come_from_the_colors_stream(self):
        """The opening balls' colours are drawn from random_stream('paddleslap.colors')."""
        reset_streams(seed=PADDLESLAP_STREAM_TEST_SEED)

        game = Game(options=self.mock_options)

        reference_generator = _reference_stream('paddleslap.colors')
        assert game.balls[0].color == tuple(reference_generator.randrange(256) for _ in range(3))

    def test_spawned_ball_position_and_color_come_from_their_streams(self):
        """A random spawn's position is from 'paddleslap.spawn', its colour 'paddleslap.colors'."""
        game = Game(options=self.mock_options)
        game.ball_spawn_mode = BallSpawnMode.RANDOM_POSITION | BallSpawnMode.RANDOM_COLOR
        # No ball to keep away from, so the first drawn position is used
        game.balls = []
        reset_streams(seed=PADDLESLAP_STREAM_TEST_SEED)

        game._spawn_new_ball()

        spawn_generator = _reference_stream('paddleslap.spawn')
        color_generator = _reference_stream('paddleslap.colors')
        new_ball = game.balls[-1]
        assert (new_ball.world_x, new_ball.world_y) == (
            float(spawn_generator.randrange(game.screen_width - 60) + 30),
            float(spawn_generator.randrange(game.screen_height - 40) + 20),
        )
        assert new_ball.color == tuple(color_generator.randrange(256) for _ in range(3))

    def test_spawn_keeps_away_from_where_balls_are_now_not_where_they_were_drawn(self):
        """Spawn spacing uses each ball's current (snapped) world position, not its rect.

        The engine writes a ball's rect only when it positions world sprites before the next
        render, so during dt_tick the rect still holds last frame's place.
        """
        game = Game(options=self.mock_options)
        game.ball_spawn_mode = BallSpawnMode.RANDOM_POSITION
        existing_ball = game.balls[0]
        spawn_generator = _reference_stream('paddleslap.spawn')
        first_candidate = (
            spawn_generator.randrange(game.screen_width - 60) + 30,
            spawn_generator.randrange(game.screen_height - 40) + 20,
        )
        second_candidate = (
            spawn_generator.randrange(game.screen_width - 60) + 30,
            spawn_generator.randrange(game.screen_height - 40) + 20,
        )
        assert math.dist(first_candidate, second_candidate) >= 100
        # The ball is now centred on the first candidate; its rect is still far away
        existing_ball.world_x = float(first_candidate[0] - existing_ball.rect.width // 2)
        existing_ball.world_y = float(first_candidate[1] - existing_ball.rect.height // 2)
        existing_ball.rect.topleft = (-1000, -1000)
        reset_streams(seed=PADDLESLAP_STREAM_TEST_SEED)

        game._spawn_new_ball()

        new_ball = game.balls[-1]
        assert (new_ball.world_x, new_ball.world_y) == (
            float(second_candidate[0]),
            float(second_candidate[1]),
        )

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

    def test_ball_moving_into_paddle_bounces_in_the_same_dt_tick(self, mocker):
        """The game's dt_tick moves the balls, then resolves paddle hits, before rendering.

        Collisions run in dt_tick, not update(): the engine positions world sprites (the ball)
        between the two, so a bounce resolved in update() would be drawn a frame late.
        """
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        paddle = game.player1
        paddle.snd = mocker.Mock()
        handle_spy = mocker.spy(ball, 'handle_paddle_collision')
        check_overlap_spy = mocker.spy(game.collisions, 'check_overlap')

        # Just right of the left paddle, moving left: 15 px into it after a 0.05 s frame.
        ball.world_x = float(paddle.rect.right + 5)
        ball.world_y = float(paddle.rect.centery - ball.rect.height // 2)
        ball.speed.x = -300.0
        ball.speed.y = 0.0

        game.dt_tick(0.05)

        handle_spy.assert_called_once_with(paddle)
        assert any(
            call.args[:2] == ('balls', 'paddles') for call in check_overlap_spy.call_args_list
        )
        assert ball.speed.x > 0
        assert get_sprite_collision_rect(ball).left == paddle.rect.right
        paddle.snd.play.assert_called_once()
        assert ball.alive()

    def test_update_resolves_no_collisions(self, mocker):
        """update() is render-phase only: it neither checks overlaps nor removes balls."""
        game = Game(options=self.mock_options)
        check_overlap_spy = mocker.spy(game.collisions, 'check_overlap')
        handle_ball_collisions_spy = mocker.spy(game, '_handle_ball_collisions')

        game.update()

        check_overlap_spy.assert_not_called()
        handle_ball_collisions_spy.assert_not_called()

    def test_dt_tick_keeps_collided_balls_playable_after_ball_collisions(self, mocker):
        """dt_tick applies the serve-like playability rule after the ball-ball physics."""
        game = Game(options=self.mock_options)
        call_order = mocker.Mock()
        mocker.patch.object(game, '_handle_ball_collisions', call_order.physics)
        mocker.patch.object(game, '_keep_collided_balls_playable', call_order.playability)

        game.dt_tick(0.0)

        assert [call[0] for call in call_order.mock_calls] == ['physics', 'playability']

    def test_dt_tick_removes_dead_balls_and_ends_the_game_without_balls(self, mocker):
        """The last ball leaving the screen ends the game in that frame's dt_tick."""
        game = Game(options=self.mock_options)
        mocker.patch.object(game, '_save_high_score', return_value=[])
        ball = game.balls[0]
        mocker.patch.object(ball, 'alive', return_value=False)

        game.dt_tick(0.0)

        assert game.balls == []
        assert ball not in game.collisions.get_layer('balls').sprites
        assert isinstance(game.next_scene, PaddleSlapGameOverScene)

    def test_dead_ball_still_in_layer_is_not_bounced(self, mocker):
        """A ball killed this frame (still in the 'balls' layer until cleanup) is skipped."""
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        paddle = game.player1
        handle_spy = mocker.spy(ball, 'handle_paddle_collision')
        mocker.patch.object(ball, 'alive', return_value=False)

        game._on_ball_paddle_collision(ball, paddle)

        handle_spy.assert_not_called()

    def test_the_court_draws_both_paddles_and_the_ball(self):
        """Drawn for real, the court shows two white paddles and the ball, and nothing else.

        The engine positions the world-space ball from the camera first (as every frame does),
        then the game's LayeredDirty draws onto a black 32-bit surface (no per-pixel alpha, so
        the result does not depend on the display's pixel format).
        """
        reset_streams(seed=PADDLESLAP_STREAM_TEST_SEED)
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        assert ball.color != (0, 0, 0), 'the ball must differ from the background'
        position_world_sprites(sprites=game.all_sprites, camera=game.camera, screen_size=(800, 600))

        screen = pygame.Surface((800, 600), depth=32)
        screen.fill((0, 0, 0))
        game.all_sprites.draw(screen)
        pixels = pygame.surfarray.array3d(screen)

        drawn_anywhere = np.zeros((800, 600), dtype=bool)
        for paddle in (game.player1, game.player2):
            paddle_pixels = pixels[
                paddle.rect.left : paddle.rect.right, paddle.rect.top : paddle.rect.bottom
            ]
            assert np.all(paddle_pixels == (255, 255, 255)), f'{paddle.name} is not solid white'
            drawn_anywhere[
                paddle.rect.left : paddle.rect.right, paddle.rect.top : paddle.rect.bottom
            ] = True

        ball_box = ball.rect
        ball_pixels = pixels[ball_box.left : ball_box.right, ball_box.top : ball_box.bottom]
        ball_box_colors = {
            tuple(int(channel) for channel in pixel) for pixel in ball_pixels.reshape(-1, 3)
        }
        assert ball_box_colors == {(0, 0, 0), ball.color}
        assert tuple(int(channel) for channel in pixels[ball_box.center]) == ball.color
        drawn_anywhere[ball_box.left : ball_box.right, ball_box.top : ball_box.bottom] = True

        assert not np.any(pixels[~drawn_anywhere]), 'something was drawn off the sprites'

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


class TestPaddleslapBallTrajectoryLogging:
    """The per-frame ball trajectory logs (and their history) run only with DEBUG logging."""

    def test_dt_tick_skips_the_ball_trajectory_logs_without_debug_logging(self, caplog):
        """With DEBUG off, dt_tick neither logs the balls nor keeps their trajectory history."""
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        ball = game.balls[0]
        caplog.clear()  # only these frames count

        with caplog.at_level(logging.INFO, logger=paddleslap_log.name):
            for _ in range(3):
                game.dt_tick(0.01)

        assert ball._debug_positions == []
        assert 'BALL 1 BEFORE' not in caplog.text
        assert 'BALL 1 AFTER' not in caplog.text
        assert 'BALL 1 COLLISION CHECK' not in caplog.text

    def test_dt_tick_logs_the_ball_trajectory_with_debug_logging(self, caplog):
        """With DEBUG on, dt_tick logs each ball and detects an upward curve from its history."""
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        ball = game.balls[0]
        ball.world_x = 300.0
        ball.world_y = 300.0
        ball.speed.x = 10.0
        ball.speed.y = -100.0  # 1 px up per 0.01 s frame: 6 px over 7 frames passes -5

        with caplog.at_level(logging.DEBUG, logger=paddleslap_log.name):
            for _ in range(7):
                game.dt_tick(0.01)

        assert len(ball._debug_positions) == 7
        assert 'BALL 1 BEFORE: pos=(' in caplog.text
        assert 'BALL 1 AFTER:  pos=(' in caplog.text
        assert 'BALL 1 COLLISION CHECK: pos=(' in caplog.text
        assert 'BALL 1 UPWARD CURVE DETECTED' in caplog.text


class TestPaddleslapSpawnCooldown:
    """PaddleSlap's ball spawn cooldown."""

    def test_spawn_cooldown_counts_game_time_only(self, mocker):
        """The spawn cooldown runs on Scene.game_time, so time spent paused never counts.

        The frame clock (like the wall clock the cooldown used before) keeps running while the
        game is paused; game time does not.
        """
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        game.ball_spawn_mode = (
            BallSpawnMode.ON_PADDLE_COLLISION
            | BallSpawnMode.COOLDOWN_ENABLED
            | BallSpawnMode.NORMAL
        )
        spawn_new_ball = mocker.patch.object(game, '_spawn_new_ball')
        ball = game.balls[0]

        game._spawn_new_ball_with_speed_check(ball)
        assert spawn_new_ball.call_count == 1, 'the first spawn is never held back'

        # A minute paused (the frame clock runs on), then one second of play
        advance_frame_clock(seconds=60.0)
        game.advance_game_time(seconds=1.0)
        game._spawn_new_ball_with_speed_check(ball)
        assert spawn_new_ball.call_count == 1, 'held back: 1 s of game time < the 2 s cooldown'

        game.advance_game_time(seconds=1.0)
        game._spawn_new_ball_with_speed_check(ball)
        assert spawn_new_ball.call_count == 2, '2 s of game time ends the cooldown'


class TestPaddleslapGameOverDemo:
    """PaddleSlap's game-over screen plays the bundled demo when nobody presses anything."""

    @staticmethod
    def game_over_screen(mocker) -> tuple[PaddleSlapGameOverScene, MockType]:
        """Make PaddleSlap's game-over screen with the scene manager's play_recording patched.

        Returns:
            The scene and the patched play_recording.

        """
        scene = PaddleSlapGameOverScene(
            final_score=3,
            high_scores=[{'score': 3}],
            options=dict(PADDLESLAP_TEST_OPTIONS),
        )
        play_recording = mocker.patch.object(scene.scene_manager, 'play_recording')
        return scene, play_recording

    def test_the_game_ends_on_paddleslaps_game_over_screen(self, mocker):
        """The last ball leaving ends the game on the screen that plays the demo."""
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        mocker.patch.object(game, '_save_high_score', return_value=[{'score': 0}])
        mocker.patch.object(game.balls[0], 'alive', return_value=False)

        game.dt_tick(0.0)

        assert isinstance(game.next_scene, PaddleSlapGameOverScene)
        assert game.next_scene.replay_arguments() == {
            'final_score': 0,
            'high_scores': [{'score': 0}],
        }

    def test_idle_game_over_screen_plays_the_bundled_demo(self, mocker):
        """After GAME_OVER_IDLE_SECONDS of game time without input, the demo plays."""
        scene, play_recording = self.game_over_screen(mocker)

        scene.advance_game_time(seconds=GAME_OVER_IDLE_SECONDS - 0.5)
        scene.dt_tick(0.0)
        play_recording.assert_not_called()

        scene.advance_game_time(seconds=0.5)
        scene.dt_tick(0.0)
        play_recording.assert_called_once_with(path=PADDLESLAP_DEMO_PATH, then=scene)

    def test_the_demo_waits_a_whole_idle_stretch_again_after_it_played(self, mocker):
        """Back from the demo, the screen waits GAME_OVER_IDLE_SECONDS again before replaying."""
        scene, play_recording = self.game_over_screen(mocker)
        scene.advance_game_time(seconds=GAME_OVER_IDLE_SECONDS)
        scene.dt_tick(0.0)

        scene.advance_game_time(seconds=GAME_OVER_IDLE_SECONDS - 0.5)
        scene.dt_tick(0.0)
        assert play_recording.call_count == 1

        scene.advance_game_time(seconds=0.5)
        scene.dt_tick(0.0)
        assert play_recording.call_count == 2

    @pytest.mark.parametrize(
        ('handler_name', 'event_type', 'event_attributes'),
        [
            ('on_key_down_event', pygame.KEYDOWN, {'key': pygame.K_LSHIFT, 'mod': 0}),
            ('on_joy_button_down_event', pygame.JOYBUTTONDOWN, {'button': 0, 'instance_id': 0}),
            (
                'on_controller_button_down_event',
                pygame.CONTROLLERBUTTONDOWN,
                {'button': 0, 'instance_id': 0},
            ),
        ],
    )
    def test_a_press_restarts_the_idle_wait(
        self, mocker, handler_name, event_type, event_attributes
    ):
        """Any key or button press starts the idle stretch again."""
        scene, play_recording = self.game_over_screen(mocker)
        scene.advance_game_time(seconds=GAME_OVER_IDLE_SECONDS - 0.5)

        getattr(scene, handler_name)(HashableEvent(type=event_type, **event_attributes))
        scene.advance_game_time(seconds=GAME_OVER_IDLE_SECONDS - 0.5)
        scene.dt_tick(0.0)
        play_recording.assert_not_called()

        scene.advance_game_time(seconds=0.5)
        scene.dt_tick(0.0)
        play_recording.assert_called_once()

    def test_restarting_starts_a_new_paddleslap_game(self, mocker):
        """SPACE starts a new Game, whatever scene ran last (a demo's own scenes included)."""
        scene, _play_recording = self.game_over_screen(mocker)
        switch_to_scene = mocker.patch.object(scene.scene_manager, 'switch_to_scene')

        scene.resume()

        (new_game,), _keywords = switch_to_scene.call_args
        assert type(new_game) is Game
        assert new_game.options == scene.options


def test_bundled_demo_exists_and_is_small():
    """PaddleSlap ships its demo in its package, under 100 KB."""
    assert PADDLESLAP_DEMO_PATH.is_file()
    assert PADDLESLAP_DEMO_PATH.stat().st_size < 100_000


def key_at(*, key: int, scancode: int) -> HashableEvent:
    """Return a key press reporting ``key`` at physical position ``scancode`` (another layout).

    Returns:
        The KEYDOWN event.

    """
    return HashableEvent(pygame.KEYDOWN, key=key, scancode=scancode, mod=0, unicode='')


class TestPositionalKeys:
    """Every control is a physical position (scancode bindings), pause included."""

    @pytest.mark.parametrize(
        ('player', 'action', 'scancode', 'qwerty_key'),
        [
            (0, 'up', pygame.KSCAN_W, pygame.K_w),
            (0, 'down', pygame.KSCAN_S, pygame.K_s),
            (1, 'up', pygame.KSCAN_UP, pygame.K_UP),
            (1, 'down', pygame.KSCAN_DOWN, pygame.K_DOWN),
        ],
    )
    def test_a_paddle_key_is_its_position(self, player, action, scancode, qwerty_key):
        actions = Game._create_action_maps()[player]
        # Another layout names the key in that place differently (AZERTY's Z is QWERTY's W)
        assert actions.get_action(key_at(key=pygame.K_F13, scancode=scancode)) == action
        # The QWERTY key code somewhere else is not the paddle key
        assert actions.get_action(key_at(key=qwerty_key, scancode=pygame.KSCAN_F13)) is None

    def test_pause_is_a_position_too(self):
        pause_actions = Game._create_action_maps()[2]
        assert (
            pause_actions.get_action(key_at(key=pygame.K_F13, scancode=pygame.KSCAN_SPACE))
            == 'pause'
        )
        assert (
            pause_actions.get_action(key_at(key=pygame.K_SPACE, scancode=pygame.KSCAN_F13)) is None
        )
