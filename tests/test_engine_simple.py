"""Simple tests for Engine module to achieve 80%+ coverage.

This module targets the Engine module with simplified mocking.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent))

from glitchygames.engine import GameEngine, GameManager
from glitchygames.scenes import Scene

from test_mock_factory import MockFactory


class MockGame(Scene):
    """Simple mock game scene for testing."""
    
    NAME = "MockGame"
    VERSION = "1.0"

    def __init__(self, options=None, groups=None):
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
        pass


class TestEngineSimple(unittest.TestCase):
    """Simple tests for Engine functionality to achieve 80%+ coverage."""

    def setUp(self):
        """Set up test fixtures using enhanced MockFactory."""
        # Use the enhanced centralized pygame mocks
        self.patchers = MockFactory.setup_pygame_mocks()
        
        # Get the mocked objects for direct access
        self.mock_display = MockFactory.create_pygame_display_mock()
        self.mock_surface = MockFactory.create_pygame_surface_mock()

    def tearDown(self):
        """Clean up test fixtures."""
        MockFactory.teardown_pygame_mocks(self.patchers)

    def test_game_engine_initialize_icon_with_surface(self):
        """Test GameEngine.initialize_icon with pygame.Surface."""
        # Create a mock surface
        mock_icon = Mock()
        mock_icon.get_size.return_value = (32, 32)
        
        # Test the class method
        GameEngine.initialize_icon(mock_icon)
        
        # Verify the icon was set
        self.assertEqual(GameEngine.icon, mock_icon)

    def test_game_engine_initialize_icon_with_path(self):
        """Test GameEngine.initialize_icon with Path."""
        # Create a mock path
        mock_path = Mock()
        mock_path.__fspath__ = Mock(return_value="/path/to/icon.png")
        
        with patch("pygame.image.load") as mock_load:
            mock_surface = Mock()
            mock_load.return_value = mock_surface
            
            GameEngine.initialize_icon(mock_path)
            
            # Verify pygame.image.load was called
            mock_load.assert_called_once()

    def test_game_engine_initialize_icon_with_none(self):
        """Test GameEngine.initialize_icon with None."""
        original_icon = GameEngine.icon
        
        GameEngine.initialize_icon(None)
        
        # Should not change the icon
        self.assertEqual(GameEngine.icon, original_icon)

    def test_game_engine_args(self):
        """Test GameEngine.args method."""
        import argparse
        
        parser = argparse.ArgumentParser()
        result = GameEngine.args(parser)
        
        # Verify the parser was returned
        self.assertEqual(result, parser)

    def test_game_engine_quit_game(self):
        """Test GameEngine.quit_game class method."""
        with patch("pygame.event.post") as mock_post:
            GameEngine.quit_game()
            
            # Verify quit event was posted
            mock_post.assert_called_once()

    def test_game_engine_class_variables(self):
        """Test GameEngine class variables."""
        # Test that class variables are accessible
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
        # Test that the logger is accessible
        self.assertIsNotNone(GameEngine.log)
        self.assertEqual(GameEngine.log.name, "game.engine")

    def test_game_engine_game_property(self):
        """Test GameEngine game property."""
        # Create GameEngine instance
        engine = GameEngine()
        
        # Test that game property is initially None
        self.assertIsNone(engine.game)

    def test_game_engine_scene_manager_property(self):
        """Test GameEngine scene_manager property."""
        # Create GameEngine instance
        engine = GameEngine()
        
        # Test that scene_manager property exists
        self.assertIsNotNone(engine.scene_manager)

    def test_game_engine_joystick_count_property(self):
        """Test GameEngine joystick_count property."""
        # Create GameEngine instance
        engine = GameEngine()
        
        # Test that joystick_count property exists
        self.assertIsNotNone(engine.joystick_count)

    def test_game_engine_joysticks_property(self):
        """Test GameEngine joysticks property."""
        # Create GameEngine instance
        engine = GameEngine()
        
        # Test that joysticks property exists
        self.assertIsNotNone(engine.joysticks)

    def test_game_engine_icon_file_not_found(self):
        """Test GameEngine icon loading with file not found."""
        # Store original icon
        original_icon = GameEngine.icon
        
        # Test with a non-existent file
        with patch("pygame.image.load") as mock_load:
            mock_load.side_effect = FileNotFoundError("File not found")
            
            # This should not raise an exception
            try:
                GameEngine.initialize_icon("/nonexistent/path.png")
            except FileNotFoundError:
                pass  # Expected
        
        # The icon should remain unchanged
        self.assertEqual(GameEngine.icon, original_icon)

    def test_game_engine_icon_with_string_path(self):
        """Test GameEngine.initialize_icon with string path."""
        with patch("pygame.image.load") as mock_load:
            mock_surface = Mock()
            mock_load.return_value = mock_surface
            
            GameEngine.initialize_icon("/path/to/icon.png")
            
            # Verify pygame.image.load was called
            mock_load.assert_called_once()

    def test_game_manager_init(self):
        """Test GameManager initialization."""
        # Create a mock scene manager
        mock_scene_manager = Mock()
        
        # Create GameManager instance
        manager = GameManager(mock_scene_manager)
        
        # Verify the scene manager was set
        self.assertEqual(manager.game, mock_scene_manager)

    def test_game_manager_process_events(self):
        """Test GameManager.process_events method."""
        # Create a mock scene manager
        mock_scene_manager = Mock()
        
        # Create GameManager instance
        manager = GameManager(mock_scene_manager)
        
        # Mock the scene manager's process_events method
        mock_scene_manager.process_events = Mock()
        
        # Test process_events
        manager.process_events()
        
        # Verify the scene manager's process_events was called
        mock_scene_manager.process_events.assert_called_once()


if __name__ == "__main__":
    unittest.main()
