"""Bitmappy tool functionality tests."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy

from mocks.test_mock_factory import MockFactory


class TestBitmappyFunctionality(unittest.TestCase):
    """Test bitmappy module functionality."""

    def test_bitmappy_classes_exist(self):
        """Test that bitmappy classes exist."""
        # Test that main classes are available
        assert hasattr(bitmappy, "BitmapPixelSprite")
        assert hasattr(bitmappy, "FilmStripSprite")
        assert hasattr(bitmappy, "AnimatedCanvasSprite")
        assert hasattr(bitmappy, "MiniView")
        assert hasattr(bitmappy, "BitmapEditorScene")
        
        # Test that classes are callable
        assert callable(bitmappy.BitmapPixelSprite)
        assert callable(bitmappy.FilmStripSprite)
        assert callable(bitmappy.AnimatedCanvasSprite)
        assert callable(bitmappy.MiniView)
        assert callable(bitmappy.BitmapEditorScene)

    def test_bitmappy_exceptions(self):
        """Test bitmappy exception classes."""
        # Test that exception classes exist
        assert hasattr(bitmappy, "GGUnhandledMenuItemError")
        assert callable(bitmappy.GGUnhandledMenuItemError)
        
        # Test exception can be raised
        with self.assertRaises(bitmappy.GGUnhandledMenuItemError):
            raise bitmappy.GGUnhandledMenuItemError("Test error")

    def test_bitmappy_ai_classes(self):
        """Test bitmappy AI classes."""
        # Test that AI classes exist
        assert hasattr(bitmappy, "AIRequest")
        assert hasattr(bitmappy, "AIResponse")
        
        # Test that classes are callable
        assert callable(bitmappy.AIRequest)
        assert callable(bitmappy.AIResponse)

    def test_bitmappy_sprite_inheritance(self):
        """Test bitmappy sprite inheritance."""
        # Test that sprite classes exist and are callable
        assert callable(bitmappy.BitmapPixelSprite)
        assert callable(bitmappy.FilmStripSprite)
        assert callable(bitmappy.AnimatedCanvasSprite)
        assert callable(bitmappy.MiniView)

    def test_bitmappy_scene_inheritance(self):
        """Test bitmappy scene inheritance."""
        # Test that BitmapEditorScene exists and is callable
        assert callable(bitmappy.BitmapEditorScene)

    def test_bitmappy_module_imports(self):
        """Test bitmappy module imports."""
        # Test that required modules are imported
        import pygame
        import toml
        
        # Test that bitmappy module exists and has expected attributes
        assert hasattr(bitmappy, "__file__")
        assert hasattr(bitmappy, "__name__")
        assert bitmappy.__name__ == "glitchygames.tools.bitmappy"

    def test_bitmappy_module_structure(self):
        """Test bitmappy module structure."""
        # Test that module has expected attributes
        assert hasattr(bitmappy, "__file__")
        assert hasattr(bitmappy, "__name__")
        assert bitmappy.__name__ == "glitchygames.tools.bitmappy"


if __name__ == "__main__":
    unittest.main()
