"""Tests for mouse event functionality.

This module tests mouse event interfaces, stubs, and event handling.
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
    MouseEvents,
    MouseEventStubs,
)

from mocks.test_mock_factory import MockFactory


class TestMouseEvents:
    """Test MouseEvents interface functionality."""

    def test_mouse_events_interface(self, mock_pygame_patches):
        """Test MouseEvents interface methods."""
        # Test that MouseEvents has required abstract methods
        assert hasattr(MouseEvents, "on_mouse_motion_event")
        assert hasattr(MouseEvents, "on_mouse_drag_event")
        assert hasattr(MouseEvents, "on_mouse_drop_event")
        assert hasattr(MouseEvents, "on_left_mouse_drag_event")
        assert hasattr(MouseEvents, "on_left_mouse_drop_event")
        assert hasattr(MouseEvents, "on_middle_mouse_drag_event")
        assert hasattr(MouseEvents, "on_middle_mouse_drop_event")
        assert hasattr(MouseEvents, "on_right_mouse_drag_event")
        assert hasattr(MouseEvents, "on_right_mouse_drop_event")
        assert hasattr(MouseEvents, "on_mouse_button_down_event")
        assert hasattr(MouseEvents, "on_mouse_button_up_event")
        assert hasattr(MouseEvents, "on_mouse_wheel_event")

    def test_mouse_event_stubs_implementation(self, mock_pygame_patches):
        """Test MouseEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = MouseEventStubs()
        assert hasattr(stub, "on_mouse_motion_event")
        assert hasattr(stub, "on_mouse_drag_event")
        assert hasattr(stub, "on_mouse_drop_event")
        assert hasattr(stub, "on_mouse_button_down_event")
        assert hasattr(stub, "on_mouse_button_up_event")
        assert hasattr(stub, "on_mouse_wheel_event")
        
        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)
        
        # Test method calls
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        try:
            stub.on_mouse_motion_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_mouse_button_down_event(self, mock_pygame_patches):
        """Test mouse button down event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test left mouse button down
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        try:
            stub.on_mouse_button_down_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_mouse_button_up_event(self, mock_pygame_patches):
        """Test mouse button up event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test left mouse button up
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        try:
            stub.on_mouse_button_up_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_mouse_motion_event(self, mock_pygame_patches):
        """Test mouse motion event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test mouse motion
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        try:
            stub.on_mouse_motion_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_mouse_wheel_event(self, mock_pygame_patches):
        """Test mouse wheel event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test mouse wheel
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        try:
            stub.on_mouse_wheel_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_mouse_drag_event(self, mock_pygame_patches):
        """Test mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        try:
            stub.on_mouse_drag_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_mouse_drop_event(self, mock_pygame_patches):
        """Test mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        try:
            stub.on_mouse_drop_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_left_mouse_drag_event(self, mock_pygame_patches):
        """Test left mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test left mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        try:
            stub.on_left_mouse_drag_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_left_mouse_drop_event(self, mock_pygame_patches):
        """Test left mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test left mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        try:
            stub.on_left_mouse_drop_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_middle_mouse_drag_event(self, mock_pygame_patches):
        """Test middle mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test middle mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        try:
            stub.on_middle_mouse_drag_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_middle_mouse_drop_event(self, mock_pygame_patches):
        """Test middle mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test middle mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=2, pos=(100, 100))
        try:
            stub.on_middle_mouse_drop_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_right_mouse_drag_event(self, mock_pygame_patches):
        """Test right mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test right mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        try:
            stub.on_right_mouse_drag_event(event, trigger="test_trigger")
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_right_mouse_drop_event(self, mock_pygame_patches):
        """Test right mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test right mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=3, pos=(100, 100))
        try:
            stub.on_right_mouse_drop_event(event, trigger="test_trigger")
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
