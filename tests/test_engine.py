"""Tests for the engine module."""

import unittest
import pygame
from glitchygames.engine import GameEngine
from glitchygames.scenes import Scene

class TestScene(Scene):
    """Test scene for testing."""
    
    NAME = "Test Scene"
    VERSION = "0.0.1"
    
    def __init__(self, options=None, groups=None):
        """Initialize the test scene."""
        super().__init__(options=options, groups=groups)

class TestEngine(unittest.TestCase):
    """Tests for the GameEngine class."""
    
    def setUp(self):
        """Set up the test."""
        # Initialize pygame
        pygame.init()
        
    def tearDown(self):
        """Clean up after the test."""
        pygame.quit()
        
    def test_engine_initialization(self):
        """Test that the engine initializes correctly."""
        engine = GameEngine(game=TestScene)
        self.assertEqual(engine.game_class, TestScene)
        self.assertIsNone(engine.game)
        
    def test_parse_args(self):
        """Test argument parsing."""
        engine = GameEngine(game=TestScene)
        options = engine._parse_args([])
        self.assertTrue(hasattr(options, 'windowed'))
        self.assertTrue(hasattr(options, 'resolution'))
        self.assertEqual(options.resolution, '1024x768')

if __name__ == '__main__':
    unittest.main()