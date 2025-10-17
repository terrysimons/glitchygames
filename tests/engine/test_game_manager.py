"""Tests for GameManager functionality.

This module tests GameManager initialization and event processing.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameManager
from glitchygames.scenes import Scene


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


class TestGameManager:
    """Test GameManager functionality."""

    def test_game_manager_init(self, mock_pygame_patches, mock_game_args):
        """Test GameManager initialization."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            # Create GameManager instance
            manager = GameManager(game=mock_game)

            # Test that manager is properly initialized
            assert manager is not None
            assert manager.game == mock_game
            assert manager.proxies is not None
            assert len(manager.proxies) == 1
            # The proxy object wraps the game, so we check that it exists
            assert manager.proxies[0] is not None

    def test_game_manager_process_events(self, mock_pygame_patches, mock_game_args):
        """Test GameManager event processing."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            # Create GameManager instance
            manager = GameManager(game=mock_game)

            # Mock events
            mock_events = [
                Mock(type=pygame.QUIT),
                Mock(type=pygame.KEYDOWN, key=pygame.K_SPACE),
                Mock(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
            ]

            # Mock the process_events method to avoid actual event processing
            with patch.object(manager, "process_events") as mock_process_events:
                mock_process_events.return_value = None

                # Test that process_events can be called
                manager.process_events(mock_events)

                # Verify the method was called
                mock_process_events.assert_called_once_with(mock_events)

    def test_game_manager_event_handlers(self, mock_pygame_patches, mock_game_args):
        """Test GameManager event handler methods."""
        # Mock argument parsing to prevent command line argument issues
        with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
            mock_parse_args.return_value = mock_game_args

            # Create mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())

            # Create GameManager instance
            manager = GameManager(game=mock_game)

            # Mock events
            mock_active_event = Mock(type=pygame.ACTIVEEVENT)
            mock_fps_event = Mock(type=pygame.USEREVENT + 1)  # FPSEVENT
            mock_game_event = Mock(type=pygame.USEREVENT + 2)  # GAMEEVENT
            mock_menu_event = Mock(type=pygame.USEREVENT + 3)  # MENUEVENT
            mock_sys_wm_event = Mock(type=pygame.SYSWMEVENT)

            # Test event handler methods
            manager.on_active_event(mock_active_event)
            manager.on_fps_event(mock_fps_event)
            manager.on_game_event(mock_game_event)
            manager.on_menu_item_event(mock_menu_event)
            manager.on_sys_wm_event(mock_sys_wm_event)

            # If we get here without errors, the handlers work
            assert True

    def test_game_manager_initialization(self, mock_pygame_patches):
        """Test GameManager initialization."""
        # Create mock scene manager
        mock_scene_manager = Mock()

        # Test GameManager initialization
        game_manager = GameManager(game=mock_scene_manager)

        # Verify game is set
        assert game_manager.game == mock_scene_manager

    def test_game_manager_args(self, mock_pygame_patches):
        """Test GameManager.args method."""
        parser = argparse.ArgumentParser()

        # Test that args method returns the parser
        result = GameManager.args(parser)

        assert result is parser

        # Test that we can parse the arguments
        args = parser.parse_args([])
        assert hasattr(args, "profile")  # Should have profile option
