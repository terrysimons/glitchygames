"""Tests for GameEngine initialization functionality.

This module tests GameEngine initialization, icon setup, argument parsing,
and class variables.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine, GameManager
from glitchygames.scenes import Scene

from test_mock_factory import MockFactory


class TestEngineInitialization(unittest.TestCase):
    """Test GameEngine initialization functionality."""

    def _create_mock_args(self):
        """Create mock command line arguments."""
        mock_args = Mock()
        mock_args.fps = 60
        mock_args.resolution = (800, 600)
        mock_args.windowed = True
        mock_args.use_gfxdraw = False
        mock_args.update_type = "timestep"
        mock_args.fps_refresh_rate = 1
        mock_args.profile = False
        mock_args.test_flag = False
        mock_args.unknown_args = []
        return mock_args

    def test_game_engine_initialize_icon_with_surface(self):
        """Test GameEngine.initialize_icon with pygame.Surface."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Create a mock surface using the centralized mock factory
            mock_icon = MockFactory.create_pygame_surface_mock(32, 32)
            
            # Make the mock surface implement PathLike protocol so it can be converted to a path
            mock_icon.__fspath__ = Mock(return_value="/path/to/icon.png")
            
            # Mock pygame.image.load to return our mock surface
            with patch("pygame.image.load", return_value=mock_icon):
                # Test the class method
                GameEngine.initialize_icon(mock_icon)
                
                # Verify the icon was set (it will be the result of pygame.image.load, which is our mock)
                self.assertEqual(GameEngine.icon, mock_icon)

    def test_game_engine_initialize_icon_with_path(self):
        """Test GameEngine.initialize_icon with Path."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Create a mock path
            mock_path = Mock()
            mock_path.__fspath__ = Mock(return_value="/path/to/icon.png")
            
            # Mock pygame.image.load to return a mock surface
            mock_surface = MockFactory.create_pygame_surface_mock(32, 32)
            with patch("pygame.image.load", return_value=mock_surface):
                # Test the class method
                GameEngine.initialize_icon(mock_path)
                
                # Verify the icon was set
                self.assertEqual(GameEngine.icon, mock_surface)

    def test_game_engine_initialize_icon_with_none(self):
        """Test GameEngine.initialize_icon with None."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Test the class method with None
            GameEngine.initialize_icon(None)
            
            # Verify the icon remains unchanged (should be the default)
            self.assertIsNotNone(GameEngine.icon)

    def test_game_engine_icon_file_not_found(self):
        """Test GameEngine.initialize_icon when file is not found."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Create a mock path that will cause FileNotFoundError
            mock_path = Mock()
            mock_path.__fspath__ = Mock(return_value="/nonexistent/path.png")
            
            # Mock pygame.image.load to raise FileNotFoundError
            with patch("pygame.image.load", side_effect=FileNotFoundError):
                # Test the class method - should handle FileNotFoundError gracefully
                GameEngine.initialize_icon(mock_path)
                
                # Verify the icon remains unchanged (should be the default)
                self.assertIsNotNone(GameEngine.icon)

    def test_game_engine_icon_with_string_path(self):
        """Test GameEngine.initialize_icon with string path."""
        # Mock argument parsing to prevent command line argument issues
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            mock_parse_args.return_value = self._create_mock_args()
            
            # Mock pygame.image.load to return a mock surface
            mock_surface = MockFactory.create_pygame_surface_mock(32, 32)
            with patch("pygame.image.load", return_value=mock_surface):
                # Test the class method with string path
                GameEngine.initialize_icon("/path/to/icon.png")
                
                # Verify the icon was set
                self.assertEqual(GameEngine.icon, mock_surface)

    def test_game_engine_args(self):
        """Test GameEngine.args method."""
        # Create an argument parser
        import argparse
        parser = argparse.ArgumentParser()
        
        # Test that GameEngine.args returns a parser with expected arguments
        result_parser = GameEngine.args(parser)
        
        # Verify parser is returned
        self.assertIsNotNone(result_parser)
        self.assertEqual(result_parser, parser)
        
        # Test parsing with known arguments
        args = result_parser.parse_args(["--log-level", "debug", "--profile"])
        self.assertEqual(args.log_level, "debug")
        self.assertTrue(args.profile)

    def test_game_engine_class_variables(self):
        """Test GameEngine class variables."""
        # Test that class variables are properly set
        self.assertEqual(GameEngine.NAME, "Boilerplate Adventures")
        self.assertEqual(GameEngine.VERSION, "1.0")
        self.assertIsInstance(GameEngine.OPTIONS, dict)
        self.assertIsInstance(GameEngine.LAST_EVENT_MISS, str)
        self.assertIsInstance(GameEngine.MISSING_EVENTS, list)
        self.assertIsInstance(GameEngine.UNIMPLEMENTED_EVENTS, list)
        self.assertIsInstance(GameEngine.USE_FASTEVENTS, bool)
        self.assertIsInstance(GameEngine.EVENT_HANDLERS, dict)

    def test_game_engine_logger(self):
        """Test GameEngine logger."""
        # Test that logger is properly configured
        self.assertIsNotNone(GameEngine.log)
        self.assertEqual(GameEngine.log.name, "game.engine")


if __name__ == "__main__":
    unittest.main()
