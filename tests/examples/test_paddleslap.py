#!/usr/bin/env python3
"""Test paddleslap example using centralized mocks."""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.examples.paddleslap import Game
from glitchygames.game_objects.ball import SpeedUpMode

from tests.mocks.test_mock_factory import MockFactory


class TestPaddleslapExample:
    """Test paddleslap example using centralized mocks."""

    def setup_method(self):
        """Set up test fixtures using centralized mocks."""
        # Use centralized mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        # Start all the patchers
        for patcher in self.patchers:
            patcher.start()
        
        # Create mock options
        self.mock_options = {
            "balls": 1,
            "fps": 60,
            "resolution": "800x600",
            "windowed": True,
            "use_gfxdraw": False,
            "update_type": "update",
            "fps_refresh_rate": 1000,
            "profile": False,
            "test_flag": False,
            "font_name": "Arial",
            "font_size": 16,
            "font_bold": False,
            "font_italic": False,
            "font_antialias": True,
            "font_dpi": 72,
            "font_system": "pygame",
            "log_level": "info",
            "no_unhandled_events": False,
        }

    def teardown_method(self):
        """Clean up after tests."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_paddleslap_game_initialization(self):
        """Test that paddleslap game initializes correctly with centralized mocks."""
        # Create the game instance
        game = Game(options=self.mock_options)
        
        # Verify basic game properties
        assert game.NAME == "Paddle Slap"
        assert game.VERSION == "1.1"
        
        # Verify game components are created
        assert hasattr(game, "player1")
        assert hasattr(game, "player2")
        assert hasattr(game, "balls")
        assert len(game.balls) == 1
        
        # Verify ball has correct speed-up mode (X-only)
        ball = game.balls[0]
        expected_speed_up_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
        assert ball.speed_up_mode == expected_speed_up_mode
        assert ball.speed_up_multiplier == 1.15
        assert ball.bounce_top_bottom is True
        assert ball.bounce_left_right is False

    def test_paddleslap_ball_speed_up_mechanism(self):
        """Test that the X-only speed-up mechanism works correctly."""
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        
        # Test that the speed-up mode is X-only
        expected_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
        assert ball.speed_up_mode == expected_mode
        
        # Test that only X flag is set
        assert ball.speed_up_mode & SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
        assert not (ball.speed_up_mode & SpeedUpMode.ON_BOUNCE_LOGARITHMIC_Y)

    def test_paddleslap_ball_creation_with_multiple_balls(self):
        """Test creating multiple balls with the new speed-up mechanism."""
        multi_ball_options = self.mock_options.copy()
        multi_ball_options["balls"] = 3
        
        game = Game(options=multi_ball_options)
        
        # Verify correct number of balls
        assert len(game.balls) == 3
        
        # Verify all balls have the correct speed-up mode (X-only)
        expected_mode = SpeedUpMode.ON_BOUNCE_LOGARITHMIC_X
        for ball in game.balls:
            assert ball.speed_up_mode == expected_mode
            assert ball.speed_up_multiplier == 1.15
            assert ball.bounce_top_bottom is True
            assert ball.bounce_left_right is False

    def test_paddleslap_speed_up_logic(self):
        """Test that the speed-up logic correctly handles X-only speed-up."""
        game = Game(options=self.mock_options)
        ball = game.balls[0]
        
        # Set initial speed
        from glitchygames.movement import Speed
        ball.speed = Speed(100.0, 200.0)
        initial_x = ball.speed.x
        initial_y = ball.speed.y
        
        # Simulate paddle bounce (should trigger only X speed-up)
        ball.on_paddle_bounce()
        
        # Only X should be affected by the speed-up, Y should remain unchanged
        assert ball.speed.x != initial_x  # X speed changed
        assert ball.speed.y == initial_y  # Y speed unchanged
        
        # Verify the speed-up was applied correctly to X only
        expected_x = initial_x * 1.15
        assert abs(ball.speed.x - expected_x) < 0.01
        assert ball.speed.y == initial_y  # Y should be exactly the same

    def test_paddleslap_game_setup(self):
        """Test that the game setup method works correctly."""
        game = Game(options=self.mock_options)
        
        # Test setup method
        game.setup()
        
        # Verify setup completed without errors
        assert hasattr(game, "target_fps")
        assert game.target_fps == 60

    def test_paddleslap_args_method(self):
        """Test that the args method works correctly."""
        import argparse
        
        parser = argparse.ArgumentParser()
        Game.args(parser)
        
        # Verify that the parser has the expected arguments
        actions = [action.dest for action in parser._actions]
        assert "balls" in actions
        assert "version" in actions
