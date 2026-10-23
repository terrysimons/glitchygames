#!/usr/bin/env python3
"""Test the PaddleSlap example game (real pygame, real sprites)."""

from __future__ import annotations

import logging
import math
import os
import random
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pygame
import pytest
from scripts.record_golden_traces import GoldenTraceEngine, GoldenTraceSceneManager, command_line

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.collision.layers import get_sprite_collision_rect
from glitchygames.events.base import HashableEvent
from glitchygames.examples import paddleslap
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
from glitchygames.exit_codes import ExitCode
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
from glitchygames.state import DiskSaveManager
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


def test_game_built_with_a_sprite_group_holds_its_paddles_and_balls():
    """A Game given a sprite group still draws both paddles and its balls."""
    game = Game(options=dict(PADDLESLAP_TEST_OPTIONS), groups=pygame.sprite.LayeredDirty())
    assert game.player1 in game.all_sprites
    assert game.player2 in game.all_sprites
    assert game.balls[0] in game.all_sprites


@pytest.mark.parametrize(
    ('spawn_mode_option', 'expected_spawn_mode'),
    [
        ('paddle_only', BallSpawnMode.PADDLE_ONLY),
        ('wall_only', BallSpawnMode.WALL_ONLY),
        ('ball_only', BallSpawnMode.BALL_ONLY),
        ('frequent', BallSpawnMode.FREQUENT_SPAWNING),
        ('rare', BallSpawnMode.PADDLE_ONLY | BallSpawnMode.RARE),
        ('none', BallSpawnMode.NO_SPAWNING),
        ('unknown', BallSpawnMode.PADDLE_ONLY),
    ],
)
def test_ball_spawn_mode_option_picks_the_spawn_mode(spawn_mode_option, expected_spawn_mode):
    """--ball-spawn-mode names the spawn flags; an unknown name falls back to paddle_only."""
    game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': spawn_mode_option})
    assert game.ball_spawn_mode == expected_spawn_mode


class TestPaddleslapDebugLoggingDetails:
    """The DEBUG trajectory history's cap, a level ball, and dead balls."""

    def test_trajectory_history_keeps_the_last_ten_positions(self, caplog):
        """A level ball fills the history to its cap and never reports an upward curve."""
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        ball = game.balls[0]
        ball.world_x = 300.0
        ball.world_y = 300.0
        ball.speed.x = 10.0
        ball.speed.y = 0.0

        with caplog.at_level(logging.DEBUG, logger=paddleslap_log.name):
            for _ in range(12):
                game.dt_tick(0.01)

        assert len(ball._debug_positions) == 10
        assert {position[1] for position in ball._debug_positions} == {300}
        assert 'UPWARD CURVE DETECTED' not in caplog.text

    def test_dead_balls_are_not_logged(self, caplog):
        """A ball that left the screen this frame is skipped by every per-ball DEBUG log."""
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'balls': 2})
        dead_ball = game.balls[1]
        dead_ball.kill()

        with caplog.at_level(logging.DEBUG, logger=paddleslap_log.name):
            game.dt_tick(0.01)

        assert 'BALL 1 BEFORE' in caplog.text
        assert 'BALL 1 COLLISION CHECK' in caplog.text
        assert 'BALL 2 BEFORE' not in caplog.text
        assert 'BALL 2 AFTER' not in caplog.text
        assert 'BALL 2 COLLISION CHECK' not in caplog.text
        assert dead_ball not in game.balls
        assert dead_ball._debug_positions == []


class TestPaddleslapHighScores:
    """Game over saves the rally count among the ten best (real files in tmp_path)."""

    def test_game_over_keeps_the_ten_best_rallies_best_first(self, tmp_path):
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        game.saves = DiskSaveManager('paddleslap', save_dir=tmp_path)
        game.saves.save('high_scores', {'scores': [{'score': score} for score in range(1, 11)]})
        game.rally_count = 6
        game.balls[0].kill()

        game.dt_tick(0.0)

        expected_scores = [{'score': score} for score in (10, 9, 8, 7, 6, 6, 5, 4, 3, 2)]
        assert game.saves.load('high_scores') == {'scores': expected_scores}
        assert isinstance(game.next_scene, PaddleSlapGameOverScene)
        assert game.next_scene.final_score == 6
        assert game.next_scene.high_scores == expected_scores

    def test_first_game_over_starts_the_high_scores(self, tmp_path):
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        game.saves = DiskSaveManager('paddleslap', save_dir=tmp_path)
        game.rally_count = 3
        game.balls[0].kill()

        game.dt_tick(0.0)

        assert game.saves.load('high_scores') == {'scores': [{'score': 3}]}


class TestPaddleslapSpawnRules:
    """When a paddle hit spawns a ball, and where a crowded court puts it."""

    @staticmethod
    def _ball_centred_at(*, center_x: int, center_y: int) -> BallSprite:
        ball = BallSprite()
        ball.world_x = float(center_x - ball.rect.width // 2)
        ball.world_y = float(center_y - ball.rect.height // 2)
        return ball

    def test_a_crowded_court_spawns_at_the_last_place_tried(self):
        """With every candidate within 100 px of a ball, the tenth candidate is used."""
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        game.ball_spawn_mode = BallSpawnMode.RANDOM_POSITION
        # Balls every 120 px: every point is within 60 * sqrt(2) (< 100) px of one
        game.balls = [
            self._ball_centred_at(center_x=center_x, center_y=center_y)
            for center_x in range(0, game.screen_width + 121, 120)
            for center_y in range(0, game.screen_height + 121, 120)
        ]
        spawn_generator = _reference_stream('paddleslap.spawn')
        candidates = [
            (
                spawn_generator.randrange(game.screen_width - 60) + 30,
                spawn_generator.randrange(game.screen_height - 40) + 20,
            )
            for _ in range(10)
        ]
        reset_streams(seed=PADDLESLAP_STREAM_TEST_SEED)

        game._spawn_new_ball()

        new_ball = game.balls[-1]
        assert (new_ball.world_x, new_ball.world_y) == (
            float(candidates[-1][0]),
            float(candidates[-1][1]),
        )

    def test_no_spawning_counts_the_rally_but_spawns_nothing(self):
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': 'none'})

        game._spawn_new_ball_with_speed_check(game.balls[0])

        assert game.rally_count == 1
        assert len(game.balls) == 1

    def test_without_cooldown_or_speed_check_every_hit_spawns(self):
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        game.ball_spawn_mode = BallSpawnMode.ON_PADDLE_COLLISION
        ball = game.balls[0]
        ball.speed.x = 5000.0

        game._spawn_new_ball_with_speed_check(ball)
        game._spawn_new_ball_with_speed_check(ball)

        assert len(game.balls) == 3
        assert game.last_ball_spawn_time == -math.inf

    def test_a_too_fast_ball_spawns_nothing(self):
        game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))
        ball = game.balls[0]
        ball.speed.x = 900.0
        ball.speed.y = 600.0  # 1082 px/s: over the 1000 px/s limit

        game._spawn_new_ball_with_speed_check(ball)

        assert game.rally_count == 1
        assert len(game.balls) == 1

    @pytest.mark.parametrize(
        ('spawn_mode_option', 'cooldown_seconds'), [('frequent', 0.5), ('rare', 5.0)]
    )
    def test_spawn_mode_sets_the_cooldown(self, spawn_mode_option, cooldown_seconds):
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': spawn_mode_option})
        ball = game.balls[0]

        game._spawn_new_ball_with_speed_check(ball)
        game.advance_game_time(seconds=cooldown_seconds * 0.9)
        game._spawn_new_ball_with_speed_check(ball)
        assert len(game.balls) == 2, 'held back inside the cooldown'

        game.advance_game_time(seconds=cooldown_seconds * 0.1)
        game._spawn_new_ball_with_speed_check(ball)
        assert len(game.balls) == 3, 'the cooldown has ended'


# Which events spawn a ball in each --ball-spawn-mode: the BallSpawnMode trigger flags each mode
# holds (glitchygames/game_objects/ball.py: PADDLE_ONLY, WALL_ONLY, BALL_ONLY, FREQUENT_SPAWNING,
# whose ALL_TRIGGERS also spawns on a score, PADDLE_ONLY | RARE, NO_SPAWNING)
SPAWN_TRIGGERS_BY_SPAWN_MODE: dict[str, frozenset[str]] = {
    'paddle_only': frozenset({'paddle'}),
    'wall_only': frozenset({'wall'}),
    'ball_only': frozenset({'ball'}),
    'frequent': frozenset({'paddle', 'wall', 'ball', 'score'}),
    'rare': frozenset({'paddle'}),
    'none': frozenset(),
}
SPAWN_TRIGGER_EVENTS = ('paddle', 'wall', 'ball', 'score')


class TestPaddleslapSpawnTriggers:
    """Each spawn mode spawns a ball on exactly the events its trigger flags name.

    Every event is played for real through Game.dt_tick: a ball hitting the left paddle
    (ON_PADDLE_COLLISION), a ball bouncing off the top wall (ON_WALL_BOUNCE), two balls
    colliding head on (ON_BALL_COLLISION) and a ball leaving past the right paddle (ON_SCORE).
    """

    @staticmethod
    def _play_event(*, game: Game, event: str) -> int:
        """Set the court up for one event, play one dt_tick, and return the balls it leaves.

        Returns:
            The number of balls the event leaves on the court when it spawns nothing.

        """
        if event == 'paddle':
            # Just right of the left paddle, moving left: into it after a 0.05 s frame
            ball = game.balls[0]
            ball.world_x = float(game.player1.rect.right + 5)
            ball.world_y = float(game.player1.rect.centery - ball.rect.height // 2)
            ball.speed.x, ball.speed.y = -300.0, 0.0
            game.dt_tick(0.05)
            return 1
        if event == 'wall':
            # Mid court just below the top wall, moving up: its visible circle (5 px inside the
            # image) is past the wall after a 0.05 s frame
            ball = game.balls[0]
            ball.world_x = 400.0
            ball.world_y = 2.0
            ball.speed.x, ball.speed.y = 100.0, -200.0
            game.dt_tick(0.05)
            return 1
        if event == 'ball':
            # Two balls overlapping head on, mid court (a 0 s frame moves nothing)
            left_ball, right_ball = game.balls
            left_ball.world_x, left_ball.world_y = 300.0, 300.0
            right_ball.world_x, right_ball.world_y = 300.0, 300.0
            _dx, _dy, _distance, collision_distance = game._calculate_ball_distance(
                left_ball, right_ball
            )
            right_ball.world_x = 300.0 + collision_distance - 4
            left_ball.speed.x, left_ball.speed.y = 300.0, 0.0
            right_ball.speed.x, right_ball.speed.y = -300.0, 0.0
            game.dt_tick(0.0)
            return 2
        # 'score': one ball already past the right edge leaves; a still ball keeps the game on
        scoring_ball, staying_ball = game.balls
        scoring_ball.world_x = float(game.screen_width + 10)
        scoring_ball.world_y = 300.0
        scoring_ball.speed.x, scoring_ball.speed.y = 300.0, 0.0
        staying_ball.world_x, staying_ball.world_y = 100.0, 100.0
        staying_ball.speed.x, staying_ball.speed.y = 0.0, 0.0
        game.dt_tick(0.05)
        assert scoring_ball not in game.balls, 'the scoring ball left the court'
        return 1

    @staticmethod
    def _take_off_the_court(*, game: Game, ball: BallSprite) -> None:
        """Remove a ball from the game: its list, its sprite groups and its collision layer."""
        ball.kill()
        game.balls.remove(ball)
        game.collisions.get_layer('balls').remove(ball)

    @pytest.mark.parametrize('event', SPAWN_TRIGGER_EVENTS)
    @pytest.mark.parametrize('spawn_mode_option', list(SPAWN_TRIGGERS_BY_SPAWN_MODE))
    def test_a_spawn_mode_spawns_on_exactly_its_triggers(self, spawn_mode_option, event):
        """The event spawns one ball if the mode's flags name it, and none otherwise."""
        reset_streams(seed=PADDLESLAP_STREAM_TEST_SEED)
        balls = 2 if event in {'ball', 'score'} else 1
        game = Game(
            options={
                **PADDLESLAP_TEST_OPTIONS,
                'balls': balls,
                'ball_spawn_mode': spawn_mode_option,
            }
        )

        balls_without_a_spawn = self._play_event(game=game, event=event)

        spawns = len(game.balls) - balls_without_a_spawn
        expected_spawns = 1 if event in SPAWN_TRIGGERS_BY_SPAWN_MODE[spawn_mode_option] else 0
        assert spawns == expected_spawns
        assert game.rally_count == (1 if event == 'paddle' else 0), 'only paddle hits count'

    def test_the_triggers_share_one_cooldown(self):
        """A wall bounce inside the cooldown a paddle-hit spawn started spawns nothing."""
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': 'frequent'})
        self._play_event(game=game, event='paddle')
        assert len(game.balls) == 2
        self._take_off_the_court(game=game, ball=game.balls[-1])  # the opening ball bounces
        game.advance_game_time(seconds=0.25)  # half the frequent cooldown (0.5 s)

        self._play_event(game=game, event='wall')
        assert len(game.balls) == 1, 'held back inside the shared cooldown'

        game.advance_game_time(seconds=0.25)
        self._play_event(game=game, event='wall')
        assert len(game.balls) == 2, 'the cooldown has ended'

    def test_a_too_fast_wall_bounce_spawns_nothing(self):
        """The speed check applies to wall bounces too: over 1000 px/s spawns nothing."""
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': 'wall_only'})
        ball = game.balls[0]
        # The visible circle sits 5 px inside the image: at world_y -6 it touches the top wall
        ball.world_x = 400.0
        ball.world_y = 0.0
        ball.speed.x, ball.speed.y = 900.0, -600.0  # 1082 px/s

        game.dt_tick(0.01)

        assert ball.speed.y > 0, 'the ball bounced off the top wall'
        assert len(game.balls) == 1

    def test_a_ball_spawned_by_a_wall_bounce_spawns_on_its_own_bounces(self):
        """Spawned balls carry the spawn triggers, as the opening balls do."""
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': 'wall_only'})
        game.ball_spawn_mode &= ~BallSpawnMode.COOLDOWN_ENABLED
        self._play_event(game=game, event='wall')
        assert len(game.balls) == 2
        spawned_ball = game.balls[-1]
        self._take_off_the_court(game=game, ball=game.balls[0])

        self._play_event(game=game, event='wall')

        assert game.balls[0] is spawned_ball
        assert len(game.balls) == 2

    def test_the_last_ball_scoring_spawns_a_replacement_instead_of_ending_the_game(self):
        """With ON_SCORE, the spawn comes before the game-over check, so the game goes on."""
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'ball_spawn_mode': 'frequent'})
        ball = game.balls[0]
        ball.world_x = float(game.screen_width + 10)
        ball.speed.x, ball.speed.y = 300.0, 0.0

        game.dt_tick(0.05)

        assert ball not in game.balls
        assert len(game.balls) == 1
        assert not isinstance(game.next_scene, PaddleSlapGameOverScene)


class TestPaddleslapBallCollisionEdges:
    """Ball-ball collisions at their edges: just touching, too fast, already playable."""

    @staticmethod
    def _touching_pair(*, gap: int) -> tuple[Game, BallSprite, BallSprite]:
        """Two balls side by side, collision circles ``gap`` px short of touching (<0: overlap).

        Returns:
            The game and its two balls (left, right).

        """
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'balls': 2})
        left_ball, right_ball = game.balls
        left_ball.world_x = 300.0
        left_ball.world_y = 300.0
        right_ball.world_y = 300.0
        right_ball.world_x = 300.0
        _dx, _dy, _distance, collision_distance = game._calculate_ball_distance(
            left_ball, right_ball
        )
        right_ball.world_x = 300.0 + collision_distance + gap
        return game, left_ball, right_ball

    def test_balls_just_touching_and_moving_apart_do_not_collide(self):
        game, left_ball, right_ball = self._touching_pair(gap=0)
        _dx, _dy, distance, collision_distance = game._calculate_ball_distance(
            left_ball, right_ball
        )
        assert distance == collision_distance
        left_ball.speed.x, left_ball.speed.y = -200.0, 100.0
        right_ball.speed.x, right_ball.speed.y = 200.0, 100.0

        game._on_ball_ball_collision(left_ball, right_ball)

        assert (left_ball.speed.x, left_ball.speed.y) == (-200.0, 100.0)
        assert (right_ball.speed.x, right_ball.speed.y) == (200.0, 100.0)
        assert game._ball_collision_pairs == []

    def test_collision_caps_a_ball_at_500_px_per_second(self):
        game, left_ball, right_ball = self._touching_pair(gap=-4)
        left_ball.speed.x, left_ball.speed.y = 900.0, 0.0
        right_ball.speed.x, right_ball.speed.y = -100.0, 0.0

        game._on_ball_ball_collision(left_ball, right_ball)

        # Head on, the normal components swap: the right ball gets 900, capped at 500
        assert right_ball.speed.x == pytest.approx(500.0)
        assert right_ball.speed.y == pytest.approx(0.0)
        assert left_ball.speed.x == pytest.approx(-100.0)

    def test_a_playable_ball_is_left_alone(self):
        game, left_ball, right_ball = self._touching_pair(gap=0)
        left_ball.speed.x, left_ball.speed.y = -300.0, 200.0  # ~34 degrees, above serve speed

        game._keep_ball_playable(left_ball, partner=right_ball)

        assert (left_ball.speed.x, left_ball.speed.y) == (-300.0, 200.0)

    def test_a_vertical_ball_turns_away_from_its_partner(self):
        """A zero horizontal component takes the direction away from the partner ball."""
        game, left_ball, right_ball = self._touching_pair(gap=0)
        left_ball.speed.x, left_ball.speed.y = 0.0, -400.0

        game._keep_ball_playable(left_ball, partner=right_ball)

        # Into the serve band's steepest angle, leftward (away from the right ball), still up
        maximum_angle = math.radians(left_ball.serve_settings.maximum_angle_degrees)
        assert left_ball.speed.x == pytest.approx(-400.0 * math.cos(maximum_angle))
        assert left_ball.speed.y == pytest.approx(-400.0 * math.sin(maximum_angle))

    def test_a_stopped_ball_level_with_its_partner_goes_right_and_down(self):
        """With no direction and no offset to keep away from, a ball serves right and down."""
        game, left_ball, right_ball = self._touching_pair(gap=0)
        right_ball.world_x = left_ball.world_x  # Same centre: nothing to turn away from
        left_ball.speed.x, left_ball.speed.y = 0.0, 0.0

        game._keep_ball_playable(left_ball, partner=right_ball)

        # A stopped ball's angle reads as 0 degrees, so it takes the band's flattest angle
        serve_speed = left_ball.serve_settings.speed
        minimum_angle = math.radians(left_ball.serve_settings.minimum_angle_degrees)
        assert left_ball.speed.x == pytest.approx(serve_speed * math.cos(minimum_angle))
        assert left_ball.speed.y == pytest.approx(serve_speed * math.sin(minimum_angle))


class TestPaddleslapGamepads:
    """Controller and joystick input steer the paddles (player 1 is device 0, player 2 is 1)."""

    @staticmethod
    def _moved_up(game: Game, paddle) -> bool:
        top_before = paddle.rect.top
        game.dt_tick(0.1)
        return paddle.rect.top < top_before

    def test_controller_dpad_and_stick_move_the_paddles(self):
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'input_mode': 'controller'})

        game.on_controller_button_down_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0
            )
        )
        game.on_controller_axis_motion_event(
            HashableEvent(
                pygame.CONTROLLERAXISMOTION,
                axis=pygame.CONTROLLER_AXIS_LEFTY,
                value=-32767,
                instance_id=1,
            )
        )
        assert self._moved_up(game, game.player1)
        assert game.p2_actions.is_held('up')

        game.on_controller_button_up_event(
            HashableEvent(
                pygame.CONTROLLERBUTTONUP, button=pygame.CONTROLLER_BUTTON_DPAD_UP, instance_id=0
            )
        )
        assert not game.p1_actions.is_held('up')

    def test_joystick_buttons_and_stick_move_the_paddles(self):
        game = Game(options={**PADDLESLAP_TEST_OPTIONS, 'input_mode': 'joystick'})

        game.on_joy_button_down_event(
            HashableEvent(
                pygame.JOYBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_DPAD_UP, joy=0, instance_id=0
            )
        )
        game.on_joy_axis_motion_event(
            HashableEvent(
                pygame.JOYAXISMOTION,
                axis=pygame.CONTROLLER_AXIS_LEFTY,
                value=-1.0,
                joy=1,
                instance_id=1,
            )
        )
        assert self._moved_up(game, game.player1)
        assert game.p2_actions.is_held('up')

        game.on_joy_button_up_event(
            HashableEvent(
                pygame.JOYBUTTONUP, button=pygame.CONTROLLER_BUTTON_DPAD_UP, joy=0, instance_id=0
            )
        )
        assert not game.p1_actions.is_held('up')


def test_a_space_release_without_its_press_neither_pauses_nor_quits():
    """Space released after a press the game never saw (made in another scene) does nothing."""
    game = Game(options=dict(PADDLESLAP_TEST_OPTIONS))

    game.on_key_up_event(
        HashableEvent(pygame.KEYUP, key=pygame.K_SPACE, scancode=pygame.KSCAN_SPACE, mod=0)
    )

    assert game.next_scene is game


GOLDEN_REPLAY_PATH = (
    Path(__file__).parent.parent / 'fixtures' / 'replays' / 'paddleslap' / 'golden.jsonl.gz'
)


def test_main_runs_the_game_through_the_engine(mocker, capsys):
    """main() starts PaddleSlap in the engine: here a headless replay of the golden run.

    GoldenTraceEngine is the GameEngine without the SCALED display flag, which SDL's dummy
    video driver cannot honour; pygame.quit is patched because later tests on this worker
    need pygame (as tests/replay/replay_helpers.replay_through_engine does).
    """
    mocker.patch('pygame.quit')
    mocker.patch('pygame.display.quit')
    mocker.patch.dict(os.environ)  # --headless sets the SDL driver variables
    mocker.patch.object(paddleslap, 'GameEngine', GoldenTraceEngine)
    GoldenTraceSceneManager.install()
    try:
        with (
            command_line([
                '--log-level',
                'warning',
                '--replay-trace',
                str(GOLDEN_REPLAY_PATH),
                '--headless',
            ]),
            pytest.raises(SystemExit) as exit_info,
        ):
            paddleslap.main()
    finally:
        pygame.event.clear()
        GoldenTraceSceneManager.uninstall()

    assert exit_info.value.code == ExitCode.SUCCESS
    assert 'Replay matched' in capsys.readouterr().out
