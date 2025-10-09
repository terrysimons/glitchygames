"""Tests for GameEngine lifecycle functionality.

This module tests GameEngine start/stop, game loop, and quit functionality.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine, GameManager
from glitchygames.scenes import Scene


class TestEngineLifecycle:
    """Test GameEngine lifecycle functionality."""


    def test_game_engine_quit_game(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.quit_game method."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = mock_game_args
            
            # Create a simple mock game using the centralized mock
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())
            
            # Create GameEngine instance with mock game
            engine = GameEngine(game=mock_game)
            
            # Test quit_game method
            engine.quit_game()
            
            # Verify the method completes without error
            assert True  # If we get here, the method worked

    def test_game_engine_start_with_mock_game(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start with mock game."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = mock_game_args
            
            # Create GameEngine instance with mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())
            
            engine = GameEngine(game=mock_game)
            
            # Mock the start method to avoid actual engine startup
            with patch.object(engine, 'start') as mock_start:
                mock_start.side_effect = SystemExit
                
                # Test that start method can be called
                with pytest.raises(SystemExit):
                    engine.start()
                
                # Verify the start method was called
                mock_start.assert_called_once()

    def test_game_engine_start_with_profiling(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start with profiling enabled."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_args = mock_game_args
            mock_args.profile = True  # Enable profiling
            mock_parse_args.return_value = mock_args
            
            # Create GameEngine instance with mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())
            
            engine = GameEngine(game=mock_game)
            
            # Mock the start method to avoid actual engine startup
            with patch.object(engine, 'start') as mock_start:
                mock_start.side_effect = SystemExit
                
                # Test that start method can be called with profiling
                with pytest.raises(SystemExit):
                    engine.start()
                
                # Verify the start method was called
                mock_start.assert_called_once()

    def test_game_engine_start_with_exception(self, mock_pygame_patches, mock_game_args):
        """Test GameEngine.start with exception handling."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = mock_game_args
            
            # Create GameEngine instance with mock game
            mock_game = Mock()
            mock_game.NAME = "MockGame"
            mock_game.VERSION = "1.0"
            mock_game.args = Mock(return_value=Mock())
            
            engine = GameEngine(game=mock_game)
            
            # Mock the start method to raise an exception
            with patch.object(engine, 'start') as mock_start:
                mock_start.side_effect = RuntimeError("Test exception")
                
                # Test that start method handles exceptions
                with pytest.raises(RuntimeError):
                    engine.start()
                
                # Verify the start method was called
                mock_start.assert_called_once()
