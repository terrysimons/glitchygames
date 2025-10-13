"""Bitmappy tool functionality tests."""

import sys
from pathlib import Path

import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.tools import bitmappy


class TestBitmappyFunctionality:
    """Test bitmappy module functionality."""

    def test_bitmappy_classes_exist(self, mock_pygame_patches):
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

    def test_bitmappy_exceptions(self, mock_pygame_patches):
        """Test bitmappy exception classes."""
        # Test that exception classes exist
        assert hasattr(bitmappy, "GGUnhandledMenuItemError")
        assert callable(bitmappy.GGUnhandledMenuItemError)

        # Test exception can be raised
        with pytest.raises(bitmappy.GGUnhandledMenuItemError):
            raise bitmappy.GGUnhandledMenuItemError("Test error")

    def test_bitmappy_ai_classes(self, mock_pygame_patches):
        """Test bitmappy AI classes."""
        # Test that AI classes exist
        assert hasattr(bitmappy, "AIRequest")
        assert hasattr(bitmappy, "AIResponse")

        # Test that classes are callable
        assert callable(bitmappy.AIRequest)
        assert callable(bitmappy.AIResponse)

    def test_bitmappy_sprite_inheritance(self, mock_pygame_patches):
        """Test bitmappy sprite inheritance."""
        # Test that sprite classes exist and are callable
        assert callable(bitmappy.BitmapPixelSprite)
        assert callable(bitmappy.FilmStripSprite)
        assert callable(bitmappy.AnimatedCanvasSprite)
        assert callable(bitmappy.MiniView)

    def test_bitmappy_scene_inheritance(self, mock_pygame_patches):
        """Test bitmappy scene inheritance."""
        # Test that BitmapEditorScene exists and is callable
        assert callable(bitmappy.BitmapEditorScene)

    def test_bitmappy_module_imports(self, mock_pygame_patches):
        """Test bitmappy module imports."""
        # Test that bitmappy module exists and has expected attributes
        assert hasattr(bitmappy, "__file__")
        assert hasattr(bitmappy, "__name__")
        assert bitmappy.__name__ == "glitchygames.tools.bitmappy"

    def test_bitmappy_module_structure(self, mock_pygame_patches):
        """Test bitmappy module structure."""
        # Test that module has expected attributes
        assert hasattr(bitmappy, "__file__")
        assert hasattr(bitmappy, "__name__")
        assert bitmappy.__name__ == "glitchygames.tools.bitmappy"
