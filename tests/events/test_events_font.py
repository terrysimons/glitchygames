"""Tests for font event functionality.

This module tests font event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    FontEvents,
    FontEventStubs,
)

from test_mock_factory import MockFactory


class TestFontEvents:
    """Test FontEvents interface functionality."""

    def test_font_events_interface(self, mock_pygame_patches):
        """Test FontEvents interface methods."""
        # Test that FontEvents has required abstract methods
        assert hasattr(FontEvents, "on_font_changed_event")

    def test_font_event_stubs_implementation(self, mock_pygame_patches):
        """Test FontEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = FontEventStubs()
        assert hasattr(stub, "on_font_changed_event")
        
        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)
        
        # Test method calls - use a generic event since FONTS_CHANGED doesn't exist
        event = HashableEvent(pygame.USEREVENT + 1)
        try:
            stub.on_font_changed_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event(self, mock_pygame_patches):
        """Test font changed event handling."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test font changed event
        event = HashableEvent(pygame.USEREVENT + 1)  # Custom font change event
        try:
            stub.on_font_changed_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_font_info(self, mock_pygame_patches):
        """Test font changed event with font information."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test font changed event with font information
        event = HashableEvent(pygame.USEREVENT + 1, font_name="Arial", font_size=12)
        try:
            stub.on_font_changed_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_different_fonts(self, mock_pygame_patches):
        """Test font changed event with different font types."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
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
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_different_sizes(self, mock_pygame_patches):
        """Test font changed event with different font sizes."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different font sizes
        font_sizes = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 48, 72]
        
        for size in font_sizes:
            event = HashableEvent(pygame.USEREVENT + 1, font_name="Arial", font_size=size)
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_style_info(self, mock_pygame_patches):
        """Test font changed event with style information."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test font changed event with style information
        style_scenarios = [
            {"font_name": "Arial", "font_size": 12, "bold": True, "italic": False},
            {"font_name": "Arial", "font_size": 12, "bold": False, "italic": True},
            {"font_name": "Arial", "font_size": 12, "bold": True, "italic": True},
            {"font_name": "Arial", "font_size": 12, "bold": False, "italic": False},
        ]
        
        for style_info in style_scenarios:
            event = HashableEvent(pygame.USEREVENT + 1, **style_info)
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_color_info(self, mock_pygame_patches):
        """Test font changed event with color information."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
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
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_unicode_fonts(self, mock_pygame_patches):
        """Test font changed event with Unicode font names."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
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
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_system_fonts(self, mock_pygame_patches):
        """Test font changed event with system fonts."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
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
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_font_changed_event_with_font_path(self, mock_pygame_patches):
        """Test font changed event with font file paths."""
        stub = FontEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test font file paths
        font_paths = [
            "/System/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/home/user/.fonts/custom-font.otf",
        ]
        
        for font_path in font_paths:
            event = HashableEvent(pygame.USEREVENT + 1, font_path=font_path, font_size=12)
            try:
                stub.on_font_changed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def _setup_mock_game_for_stub(self, stub):
        """Helper method to setup mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": False
        }
        stub.options = mock_game.options
        return mock_game
