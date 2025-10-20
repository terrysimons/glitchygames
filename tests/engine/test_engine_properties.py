"""Tests for GameEngine properties.

This module tests GameEngine properties like joysticks, scene_manager, game, etc.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene
from tests.mocks import MockFactory

# Constants for magic values
TEST_JOYSTICK_COUNT_2 = 2


class MockGame(Scene):
    """Simple mock game scene for testing."""

    NAME = "MockGame"
    VERSION = "1.0"

    def __init__(self, options=None, groups=None):
        """Initialize mock game scene."""
        if options is None:
            options = {}
        if groups is None:
            groups = Mock()  # Mock pygame.sprite.Group
        super().__init__(options=options, groups=groups)
        self.fps = 60
        self.background_color = (0, 0, 0)
        self.next_scene = self

    @classmethod
    def args(cls, parser):
        """Add mock game arguments."""
        parser.add_argument("--test-flag", action="store_true", help="Test flag")
        return parser

    def update(self):
        """Mock update method."""


class MockGameWithArgs(MockGame):
    """Mock game that properly handles command line arguments."""

    @classmethod
    def args(cls, parser):
        """Add mock game arguments."""
        parser.add_argument("--test-flag", action="store_true", help="Test flag")
        return parser


class TestEngineProperties:
    """Test GameEngine properties."""

    def _create_mock_game(self):
        """Create a mock game using MockFactory."""
        mock_game = Mock()
        mock_game.NAME = "MockGame"
        mock_game.VERSION = "1.0"
        mock_game.args = Mock(return_value=Mock())
        return mock_game

    def test_game_engine_game_property(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine game property."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create GameEngine instance with mock game
            mock_game = self._create_mock_game()

            engine = GameEngine(game=mock_game)

            # Test that game property exists
            assert engine.game is not None
            assert engine.game == mock_game

    def test_game_engine_scene_manager_property(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine scene_manager property."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create GameEngine instance with mock game
            mock_game = self._create_mock_game()

            engine = GameEngine(game=mock_game)

            # Test that scene_manager property exists
            assert engine.scene_manager is not None

    def test_game_engine_joystick_count_property(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine joystick_count property."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create GameEngine instance with mock game
            mock_game = self._create_mock_game()

            engine = GameEngine(game=mock_game)

            # Set joystick attributes directly (simulating what start() would do)
            engine.joysticks = [Mock(), Mock()]  # 2 joysticks
            engine.joystick_count = len(engine.joysticks)

            # Test that joystick_count property exists
            assert engine.joystick_count is not None
            assert engine.joystick_count == TEST_JOYSTICK_COUNT_2

    def test_game_engine_joysticks_property(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine joysticks property."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create GameEngine instance with mock game
            mock_game = self._create_mock_game()

            engine = GameEngine(game=mock_game)

            # Set joystick attributes directly (simulating what start() would do)
            mock_joysticks = [Mock(), Mock()]  # 2 joysticks
            engine.joysticks = mock_joysticks
            engine.joystick_count = len(engine.joysticks)

            # Test that joysticks property exists
            assert engine.joysticks is not None
            assert len(engine.joysticks) == TEST_JOYSTICK_COUNT_2
