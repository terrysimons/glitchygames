"""Tests for window event functionality.

This module tests window event interfaces, stubs, and event handling.
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
    WindowEvents,
    WindowEventStubs,
)


class TestWindowEvents:
    """Test WindowEvents interface functionality."""

    def test_window_events_interface(self, mock_pygame_patches):
        """Test WindowEvents interface methods."""
        # Test that WindowEvents has required abstract methods
        assert hasattr(WindowEvents, "on_window_close_event")
        assert hasattr(WindowEvents, "on_window_enter_event")
        assert hasattr(WindowEvents, "on_window_exposed_event")
        assert hasattr(WindowEvents, "on_window_focus_gained_event")
        assert hasattr(WindowEvents, "on_window_focus_lost_event")
        assert hasattr(WindowEvents, "on_window_hidden_event")
        assert hasattr(WindowEvents, "on_window_hit_test_event")
        assert hasattr(WindowEvents, "on_window_leave_event")
        assert hasattr(WindowEvents, "on_window_maximized_event")
        assert hasattr(WindowEvents, "on_window_minimized_event")
        assert hasattr(WindowEvents, "on_window_moved_event")
        assert hasattr(WindowEvents, "on_window_resized_event")
        assert hasattr(WindowEvents, "on_window_restored_event")
        assert hasattr(WindowEvents, "on_window_shown_event")
        assert hasattr(WindowEvents, "on_window_size_changed_event")
        assert hasattr(WindowEvents, "on_window_take_focus_event")

    def test_window_event_stubs_implementation(self, mock_pygame_patches):
        """Test WindowEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = WindowEventStubs()
        assert hasattr(stub, "on_window_close_event")
        assert hasattr(stub, "on_window_enter_event")
        assert hasattr(stub, "on_window_exposed_event")
        assert hasattr(stub, "on_window_focus_gained_event")
        assert hasattr(stub, "on_window_focus_lost_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.WINDOWCLOSE)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_close_event(event)

    def test_window_close_event(self, mock_pygame_patches):
        """Test window close event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window close
        event = HashableEvent(pygame.WINDOWCLOSE)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_close_event(event)

    def test_window_enter_event(self, mock_pygame_patches):
        """Test window enter event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window enter
        event = HashableEvent(pygame.WINDOWENTER)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_enter_event(event)

    def test_window_leave_event(self, mock_pygame_patches):
        """Test window leave event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window leave
        event = HashableEvent(pygame.WINDOWLEAVE)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_leave_event(event)

    def test_window_focus_gained_event(self, mock_pygame_patches):
        """Test window focus gained event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window focus gained
        event = HashableEvent(pygame.WINDOWFOCUSGAINED)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_focus_gained_event(event)

    def test_window_focus_lost_event(self, mock_pygame_patches):
        """Test window focus lost event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window focus lost
        event = HashableEvent(pygame.WINDOWFOCUSLOST)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_focus_lost_event(event)

    def test_window_resized_event(self, mock_pygame_patches):
        """Test window resized event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window resized
        event = HashableEvent(pygame.WINDOWRESIZED, x=800, y=600)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_resized_event(event)

    def test_window_moved_event(self, mock_pygame_patches):
        """Test window moved event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window moved
        event = HashableEvent(pygame.WINDOWMOVED, x=100, y=100)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_moved_event(event)

    def test_window_minimized_event(self, mock_pygame_patches):
        """Test window minimized event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window minimized
        event = HashableEvent(pygame.WINDOWMINIMIZED)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_minimized_event(event)

    def test_window_maximized_event(self, mock_pygame_patches):
        """Test window maximized event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window maximized
        event = HashableEvent(pygame.WINDOWMAXIMIZED)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_maximized_event(event)

    def test_window_restored_event(self, mock_pygame_patches):
        """Test window restored event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window restored
        event = HashableEvent(pygame.WINDOWRESTORED)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_restored_event(event)

    def test_window_shown_event(self, mock_pygame_patches):
        """Test window shown event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window shown
        event = HashableEvent(pygame.WINDOWSHOWN)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_shown_event(event)

    def test_window_hidden_event(self, mock_pygame_patches):
        """Test window hidden event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window hidden
        event = HashableEvent(pygame.WINDOWHIDDEN)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_hidden_event(event)

    def test_window_exposed_event(self, mock_pygame_patches):
        """Test window exposed event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window exposed
        event = HashableEvent(pygame.WINDOWEXPOSED)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_exposed_event(event)

    def test_window_take_focus_event(self, mock_pygame_patches):
        """Test window take focus event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window take focus
        event = HashableEvent(pygame.WINDOWTAKEFOCUS)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_take_focus_event(event)

    def test_window_size_changed_event(self, mock_pygame_patches):
        """Test window size changed event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window size changed
        event = HashableEvent(pygame.WINDOWSIZECHANGED, x=1024, y=768)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_size_changed_event(event)

    def test_window_hit_test_event(self, mock_pygame_patches):
        """Test window hit test event handling."""
        stub = WindowEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test window hit test
        event = HashableEvent(pygame.WINDOWHITTEST)
        with pytest.raises((Exception, SystemExit), match=r"Unhandled Event|SystemExit"):
            stub.on_window_hit_test_event(event)

    def _setup_mock_game_for_stub(self, stub):
        """Set up mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": False
        }
        stub.options = mock_game.options
        return mock_game
