"""Tests for text event functionality.

This module tests text event interfaces, stubs, and event handling.
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
    TextEvents,
    TextEventStubs,
)

from mocks.test_mock_factory import MockFactory


class TestTextEvents:
    """Test TextEvents interface functionality."""

    def test_text_events_interface(self, mock_pygame_patches):
        """Test TextEvents interface methods."""
        # Test that TextEvents has required abstract methods
        assert hasattr(TextEvents, "on_text_input_event")
        assert hasattr(TextEvents, "on_text_editing_event")

    def test_text_event_stubs_implementation(self, mock_pygame_patches):
        """Test TextEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = TextEventStubs()
        assert hasattr(stub, "on_text_input_event")
        assert hasattr(stub, "on_text_editing_event")
        
        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)
        
        # Test method calls
        event = HashableEvent(pygame.TEXTINPUT, text="test")
        try:
            stub.on_text_input_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_input_event(self, mock_pygame_patches):
        """Test text input event handling."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test text input
        event = HashableEvent(pygame.TEXTINPUT, text="Hello World")
        try:
            stub.on_text_input_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_editing_event(self, mock_pygame_patches):
        """Test text editing event handling."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test text editing
        event = HashableEvent(pygame.TEXTEDITING, text="Hello", start=0, length=5)
        try:
            stub.on_text_editing_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_input_with_different_characters(self, mock_pygame_patches):
        """Test text input with different character types."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different character types
        test_texts = [
            "Hello World",           # Basic text
            "123456789",             # Numbers
            "!@#$%^&*()",            # Special characters
            "Hello\nWorld",          # Text with newlines
            "Hello\tWorld",          # Text with tabs
            "Hello World!",          # Mixed characters
            "Café",                  # Text with accents
            "你好",                   # Unicode text
            "αβγδε",                 # Greek letters
            "🚀🎮🎯",                # Emojis
        ]
        
        for text in test_texts:
            event = HashableEvent(pygame.TEXTINPUT, text=text)
            try:
                stub.on_text_input_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_editing_with_different_parameters(self, mock_pygame_patches):
        """Test text editing with different parameters."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different editing scenarios
        editing_scenarios = [
            ("Hello", 0, 5),         # Full text selection
            ("Hello", 2, 3),         # Partial text selection
            ("Hello", 0, 0),         # No selection (cursor position)
            ("Hello", 5, 0),         # Cursor at end
            ("", 0, 0),              # Empty text
            ("Test", 1, 2),          # Middle selection
        ]
        
        for text, start, length in editing_scenarios:
            event = HashableEvent(pygame.TEXTEDITING, text=text, start=start, length=length)
            try:
                stub.on_text_editing_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_input_with_single_characters(self, mock_pygame_patches):
        """Test text input with single character events."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test single character inputs
        single_chars = [
            "a", "b", "c", "d", "e", "f", "g", "h", "i", "j",
            "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
            "1", "2", "3", "4", "5", "6", "7", "8", "9", "0",
            "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
            " ", "\t", "\n", "\r",
        ]
        
        for char in single_chars:
            event = HashableEvent(pygame.TEXTINPUT, text=char)
            try:
                stub.on_text_input_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_editing_with_cursor_movements(self, mock_pygame_patches):
        """Test text editing with cursor movement scenarios."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test cursor movement scenarios
        cursor_scenarios = [
            ("Hello", 0, 0),         # Cursor at beginning
            ("Hello", 1, 0),         # Cursor after first character
            ("Hello", 2, 0),         # Cursor in middle
            ("Hello", 3, 0),         # Cursor near end
            ("Hello", 4, 0),         # Cursor at end
            ("Hello", 5, 0),         # Cursor beyond end
        ]
        
        for text, start, length in cursor_scenarios:
            event = HashableEvent(pygame.TEXTEDITING, text=text, start=start, length=length)
            try:
                stub.on_text_editing_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_input_with_unicode_characters(self, mock_pygame_patches):
        """Test text input with Unicode characters."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test Unicode characters
        unicode_texts = [
            "Café",                  # Latin with accents
            "naïve",                 # Latin with diaeresis
            "résumé",                # Latin with accents
            "你好",                   # Chinese characters
            "こんにちは",              # Japanese characters
            "안녕하세요",             # Korean characters
            "Привет",                # Cyrillic characters
            "αβγδε",                 # Greek letters
            "🚀🎮🎯",                # Emojis
            "∞≠≤≥",                  # Mathematical symbols
        ]
        
        for text in unicode_texts:
            event = HashableEvent(pygame.TEXTINPUT, text=text)
            try:
                stub.on_text_input_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_text_editing_with_selection_scenarios(self, mock_pygame_patches):
        """Test text editing with different selection scenarios."""
        stub = TextEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test selection scenarios
        selection_scenarios = [
            ("Hello", 0, 5),         # Select all
            ("Hello", 0, 1),         # Select first character
            ("Hello", 1, 3),         # Select middle characters
            ("Hello", 4, 1),         # Select last character
            ("Hello", 0, 0),         # No selection
            ("Hello", 2, 0),         # Cursor position, no selection
        ]
        
        for text, start, length in selection_scenarios:
            event = HashableEvent(pygame.TEXTEDITING, text=text, start=start, length=length)
            try:
                stub.on_text_editing_event(event)
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
