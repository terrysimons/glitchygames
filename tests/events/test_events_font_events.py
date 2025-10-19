"""Tests for font event functionality.

This module tests font event interfaces, stubs, and event handling.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    FontEvents,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.fonts import FontManager

from tests.mocks.test_mock_factory import MockFactory


class TestFontEvents:
    """Test FontEvents interface functionality."""

    def test_font_events_interface(self, mock_pygame_patches):
        """Test FontEvents interface methods."""
        # Test that FontEvents has required abstract methods
        assert hasattr(FontEvents, "on_font_changed_event")

    def test_font_event_stubs_implementation(self, mock_pygame_patches):
        """Test FontEventStubs implementation."""
        # Use centralized mock for scene without event handlers (stub behavior)
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Test that stub methods can be called
        event = HashableEvent(pygame.USEREVENT + 1)
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                scene.on_font_changed_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_font_changed_event(self, mock_pygame_patches):
        """Test font changed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test font changed event
        event = HashableEvent(pygame.USEREVENT + 1)  # Custom font change event
        result = scene.on_font_changed_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.font_events_received) == 1
        assert scene.font_events_received[0][0] == "font_changed"
        assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1

    def test_font_changed_event_with_font_info(self, mock_pygame_patches):
        """Test font changed event with font information."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test font changed event with font information
        event = HashableEvent(pygame.USEREVENT + 1, font_name="Arial", font_size=12)
        result = scene.on_font_changed_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.font_events_received) == 1
        assert scene.font_events_received[0][0] == "font_changed"
        assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
        assert scene.font_events_received[0][1].font_name == "Arial"
        assert scene.font_events_received[0][1].font_size == 12

    def test_font_changed_event_with_different_fonts(self, mock_pygame_patches):
        """Test font changed event with different font types."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test different font types
        font_scenarios = [
            {"font_name": "Arial", "font_size": 12},
            {"font_name": "Times New Roman", "font_size": 14},
            {"font_name": "Courier New", "font_size": 10},
            {"font_name": "Helvetica", "font_size": 16},
            {"font_name": "Verdana", "font_size": 18},
            {"font_name": "Georgia", "font_size": 20},
        ]

        for font_info in font_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **font_info)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == font_info["font_name"]
            assert scene.font_events_received[0][1].font_size == font_info["font_size"]
            
            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_different_sizes(self, mock_pygame_patches):
        """Test font changed event with different font sizes."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test different font sizes
        font_sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72]

        for size in font_sizes:
            event = HashableEvent(pygame.USEREVENT + 1, font_name="Arial", font_size=size)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == "Arial"
            assert scene.font_events_received[0][1].font_size == size
            
            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_style_info(self, mock_pygame_patches):
        """Test font changed event with style information."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test font changed event with style information
        style_scenarios = [
            {"font_name": "Arial", "font_size": 12, "bold": True, "italic": False},
            {"font_name": "Arial", "font_size": 12, "bold": False, "italic": True},
            {"font_name": "Arial", "font_size": 12, "bold": True, "italic": True},
            {"font_name": "Arial", "font_size": 12, "bold": False, "italic": False},
        ]

        for style_info in style_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **style_info)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == style_info["font_name"]
            assert scene.font_events_received[0][1].font_size == style_info["font_size"]
            
            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_color_info(self, mock_pygame_patches):
        """Test font changed event with color information."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test font changed event with color information
        color_scenarios = [
            {"font_name": "Arial", "font_size": 12, "color": (255, 0, 0)},      # Red
            {"font_name": "Arial", "font_size": 12, "color": (0, 255, 0)},      # Green
            {"font_name": "Arial", "font_size": 12, "color": (0, 0, 255)},      # Blue
            {"font_name": "Arial", "font_size": 12, "color": (255, 255, 255)},  # White
            {"font_name": "Arial", "font_size": 12, "color": (0, 0, 0)},        # Black
        ]

        for color_info in color_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **color_info)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == color_info["font_name"]
            assert scene.font_events_received[0][1].font_size == color_info["font_size"]
            
            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_unicode_fonts(self, mock_pygame_patches):
        """Test font changed event with Unicode font names."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test Unicode font names
        unicode_fonts = [
            "宋体",           # Chinese font
            "メイリオ",        # Japanese font
            "맑은 고딕",      # Korean font
            "Times New Roman",  # English font
            "Arial Unicode MS",  # Unicode font
        ]

        for font_name in unicode_fonts:
            event = HashableEvent(pygame.USEREVENT + 1, font_name=font_name, font_size=12)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == font_name
            assert scene.font_events_received[0][1].font_size == 12
            
            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_system_fonts(self, mock_pygame_patches):
        """Test font changed event with system fonts."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test system fonts
        system_fonts = [
            "system",        # System default
            "monospace",     # Monospace font
            "serif",         # Serif font
            "sans-serif",    # Sans-serif font
            "cursive",       # Cursive font
            "fantasy",       # Fantasy font
        ]

        for font_name in system_fonts:
            event = HashableEvent(pygame.USEREVENT + 1, font_name=font_name, font_size=12)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_name == font_name
            assert scene.font_events_received[0][1].font_size == 12
            
            # Clear for next iteration
            scene.font_events_received.clear()

    def test_font_changed_event_with_font_path(self, mock_pygame_patches):
        """Test font changed event with font file paths."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_font_changed_event": lambda event: (scene.font_events_received.append(("font_changed", event)), True)[1]
            }
        )

        # Test font file paths
        font_paths = [
            "/System/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/home/user/.fonts/custom-font.otf",
        ]

        for font_path in font_paths:
            event = HashableEvent(pygame.USEREVENT + 1, font_path=font_path, font_size=12)
            result = scene.on_font_changed_event(event)
            
            # Event should be handled successfully
            assert result is True
            assert len(scene.font_events_received) == 1
            assert scene.font_events_received[0][0] == "font_changed"
            assert scene.font_events_received[0][1].type == pygame.USEREVENT + 1
            assert scene.font_events_received[0][1].font_path == font_path
            assert scene.font_events_received[0][1].font_size == 12
            
            # Clear for next iteration
            scene.font_events_received.clear()



class TestFontManagerCoverage:
    """Test coverage for FontManager class."""

    def test_font_manager_initialization(self, mock_pygame_patches):
        """Test FontManager initializes correctly."""
        from tests.mocks import MockFactory
        
        # Create a mock game with proper OPTIONS for FontManager
        mock_game = MockFactory.create_event_test_scene_mock()
        mock_game.OPTIONS = {
            "font_name": "Arial",
            "font_size": 12,
            "font_bold": False,
            "font_italic": False,
            "font_antialias": True,
            "font_dpi": 72
        }
        
        # Mock pygame.freetype to avoid import issues
        with patch("pygame.freetype", create=True):
            manager = FontManager(game=mock_game)
            
            assert manager.game == mock_game
            assert hasattr(manager, "proxies")
            assert isinstance(manager.proxies, list)

    def test_font_manager_with_fallback(self, mock_pygame_patches):
        """Test FontManager with pygame.font fallback when freetype is not available."""
        from tests.mocks import MockFactory
        
        # Create a mock game with proper OPTIONS for FontManager
        mock_game = MockFactory.create_event_test_scene_mock()
        mock_game.OPTIONS = {
            "font_name": "Arial",
            "font_size": 12,
            "font_bold": False,
            "font_italic": False,
            "font_antialias": True,
            "font_dpi": 72
        }
        
        # Test that FontManager handles missing freetype gracefully
        with patch("pygame.freetype", side_effect=AttributeError("No module named 'pygame.freetype'")):
            manager = FontManager(game=mock_game)
            
            assert manager.game == mock_game
            assert hasattr(manager, "proxies")
            assert isinstance(manager.proxies, list)

    def setUp(self):
        """Set up test fixtures."""
        # Mock game object with required options
        self.mock_game = Mock()
        self.mock_game.OPTIONS = {
            "font_name": "arial",
            "font_size": 14,
            "font_bold": False,
            "font_italic": False,
            "font_antialias": True,
            "font_dpi": 72,
            "font_system": "freetype"
        }

        # Clear any existing cache
        FontManager._font_cache.clear()
        FontManager.OPTIONS.clear()

    def test_font_manager_initialization(self, mock_pygame_patches):
        """Test FontManager initialization."""
        self.setUp()

        expected_font_size = 14

        with patch("pygame.freetype.init") as mock_init, \
             patch("pygame.freetype.get_cache_size", return_value=100), \
             patch("pygame.freetype.get_default_resolution", return_value=72):

            FontManager(self.mock_game)

            mock_init.assert_called_once()
            assert FontManager.OPTIONS["font_name"] == "arial"
            assert FontManager.OPTIONS["font_size"] == expected_font_size
            assert FontManager.OPTIONS["use_freetype"] is True

    def test_font_proxy_initialization(self, mock_pygame_patches):
        """Test FontProxy initialization."""
        self.setUp()

        # Create a concrete subclass that implements the abstract method
        class ConcreteFontProxy(FontManager.FontProxy):
            def on_font_changed_event(self, event):
                pass

        with patch("pygame.freetype.init"):
            FontManager(self.mock_game)
            proxy = ConcreteFontProxy(self.mock_game)

            assert proxy.game == self.mock_game
            assert pygame.freetype in proxy.proxies

    def test_font_method_freetype_success(self, mock_pygame_patches):
        """Test font method with successful freetype loading."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font) as mock_sysfont:

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.font(font_config)

            mock_sysfont.assert_called_once_with(name="arial", size=16)
            assert result == mock_font
            assert "arial_16" in FontManager._font_cache

    def test_font_method_freetype_fallback(self, mock_pygame_patches):
        """Test font method with freetype fallback to built-in font."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", side_effect=TypeError("Font not found")), \
             patch("pygame.freetype.Font", return_value=mock_font), \
             patch("pathlib.Path") as mock_path:

            mock_path.return_value.parent = Mock()
            mock_path.return_value.parent.__truediv__ = Mock(return_value="path/to/font.ttf")

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.font(font_config)

            # Font was called successfully
            assert result == mock_font

    def test_pygame_font_method_success(self, mock_pygame_patches):
        """Test pygame_font method with successful loading."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.Font", return_value=mock_font), \
             patch("pathlib.Path") as mock_path, \
             patch("pygame.font.SysFont", return_value=mock_font) as mock_sysfont:

            mock_path.return_value.parent = Mock()
            mock_path.return_value.parent.__truediv__ = Mock(return_value="path/to/font.ttf")

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.pygame_font(font_config)

            # Should use SysFont as fallback when Font fails
            mock_sysfont.assert_called_once_with("arial", 16)
            assert result == mock_font
            assert "pygame_arial_16" in FontManager._font_cache

    def test_pygame_font_method_fallback(self, mock_pygame_patches):
        """Test pygame_font method with fallback to default font."""
        self.setUp()

        mock_font = Mock()
        with patch("pygame.font.Font", side_effect=FileNotFoundError("Font not found")), \
             patch("pygame.font.SysFont", return_value=mock_font) as mock_sysfont:

            font_config = {"font_name": "arial", "font_size": 16}
            result = FontManager.pygame_font(font_config)

            mock_sysfont.assert_called_once_with("arial", 16)
            assert result == mock_font

    def test_pygame_font_method_default_config(self, mock_pygame_patches):
        """Test pygame_font method with default configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.font.Font", return_value=mock_font), \
             patch("pygame.font.SysFont", return_value=mock_font) as mock_sysfont:

            result = FontManager.pygame_font(None)

            # Should use SysFont as fallback when Font fails
            mock_sysfont.assert_called_once_with("arial", 16)
            assert result == mock_font
            assert "pygame_arial_16" in FontManager._font_cache

    def test_args_method(self, mock_pygame_patches):
        """Test args class method."""
        parser = argparse.ArgumentParser()
        result = FontManager.args(parser)

        assert result is parser
        # Check that the Font Options group was added
        group_titles = [group.title for group in parser._action_groups]
        assert "Font Options" in group_titles

    def test_font_method_with_default_config(self, mock_pygame_patches):
        """Test font method with default configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font):

            result = FontManager.font()

            assert result == mock_font
            assert "arial_16" in FontManager._font_cache

    def test_font_method_with_partial_config(self, mock_pygame_patches):
        """Test font method with partial configuration."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font):

            # Test with partial config (missing font_size)
            result = FontManager.font({"font_name": "times"})

            assert result == mock_font
            assert "times_14" in FontManager._font_cache  # Uses default size from OPTIONS

    def test_font_method_with_missing_font_name_config(self, mock_pygame_patches):
        """Test font method with missing font name in config."""
        self.setUp()

        # Set up OPTIONS
        FontManager.OPTIONS = {
            "font_name": "arial",
            "font_size": 16
        }

        mock_font = Mock()
        with patch("pygame.freetype.SysFont", return_value=mock_font):

            # Test with config missing font_name
            result = FontManager.font({"font_size": 20})

            assert result == mock_font
            assert "arial_20" in FontManager._font_cache

    def test_font_method_cache_hit(self, mock_pygame_patches):
        """Test font method cache hit behavior."""
        self.setUp()

        # Pre-populate cache
        mock_cached_font = Mock()
        FontManager._font_cache["arial_14"] = mock_cached_font

        config = {"font_name": "arial", "font_size": 14}

        result = FontManager.font(config)

        # Verify cache hit
        assert result == mock_cached_font
