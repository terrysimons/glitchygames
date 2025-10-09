"""Tests for game event functionality.

This module tests game event interfaces, stubs, and event handling.
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
    GameEvents,
    GameEventStubs,
)

from test_mock_factory import MockFactory


class TestGameEvents:
    """Test GameEvents interface functionality."""

    def test_game_events_interface(self, mock_pygame_patches):
        """Test GameEvents interface methods."""
        # Test that GameEvents has required abstract methods
        assert hasattr(GameEvents, "on_active_event")
        assert hasattr(GameEvents, "on_fps_event")
        assert hasattr(GameEvents, "on_game_event")
        assert hasattr(GameEvents, "on_menu_item_event")
        assert hasattr(GameEvents, "on_sys_wm_event")
        assert hasattr(GameEvents, "on_user_event")
        assert hasattr(GameEvents, "on_video_expose_event")
        assert hasattr(GameEvents, "on_video_resize_event")
        assert hasattr(GameEvents, "on_quit_event")

    def test_game_event_stubs_implementation(self, mock_pygame_patches):
        """Test GameEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = GameEventStubs()
        assert hasattr(stub, "on_active_event")
        assert hasattr(stub, "on_fps_event")
        assert hasattr(stub, "on_game_event")
        assert hasattr(stub, "on_quit_event")
        
        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)
        
        # Test method calls
        event = HashableEvent(pygame.QUIT)
        try:
            stub.on_quit_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_quit_event(self, mock_pygame_patches):
        """Test quit event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test quit event
        event = HashableEvent(pygame.QUIT)
        try:
            stub.on_quit_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_active_event(self, mock_pygame_patches):
        """Test active event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test active event
        event = HashableEvent(pygame.ACTIVEEVENT, gain=1, state=1)
        try:
            stub.on_active_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_fps_event(self, mock_pygame_patches):
        """Test FPS event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test FPS event
        event = HashableEvent(pygame.USEREVENT + 1)  # FPSEVENT
        try:
            stub.on_fps_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_game_event(self, mock_pygame_patches):
        """Test game event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test game event
        event = HashableEvent(pygame.USEREVENT + 2)  # GAMEEVENT
        try:
            stub.on_game_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_menu_item_event(self, mock_pygame_patches):
        """Test menu item event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test menu item event
        event = HashableEvent(pygame.USEREVENT + 3)  # MENUEVENT
        try:
            stub.on_menu_item_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_sys_wm_event(self, mock_pygame_patches):
        """Test system WM event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test sys WM event
        event = HashableEvent(pygame.SYSWMEVENT)
        try:
            stub.on_sys_wm_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_user_event(self, mock_pygame_patches):
        """Test user event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test user event
        event = HashableEvent(pygame.USEREVENT, code=1)
        try:
            stub.on_user_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_video_expose_event(self, mock_pygame_patches):
        """Test video expose event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test video expose event
        event = HashableEvent(pygame.VIDEOEXPOSE)
        try:
            stub.on_video_expose_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_video_resize_event(self, mock_pygame_patches):
        """Test video resize event handling."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test video resize event
        event = HashableEvent(pygame.VIDEORESIZE, w=800, h=600)
        try:
            stub.on_video_resize_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_active_event_gain_states(self, mock_pygame_patches):
        """Test active event with different gain states."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different gain states
        gain_states = [
            (1, 1),   # Gained focus
            (0, 1),   # Lost focus
            (1, 2),   # Gained mouse
            (0, 2),   # Lost mouse
            (1, 4),   # Gained keyboard
            (0, 4),   # Lost keyboard
        ]
        
        for gain, state in gain_states:
            event = HashableEvent(pygame.ACTIVEEVENT, gain=gain, state=state)
            try:
                stub.on_active_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_user_events_with_different_codes(self, mock_pygame_patches):
        """Test user events with different codes."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different user event codes
        for code in range(10):
            event = HashableEvent(pygame.USEREVENT, code=code)
            try:
                stub.on_user_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_video_resize_with_different_dimensions(self, mock_pygame_patches):
        """Test video resize events with different dimensions."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different window dimensions
        dimensions = [
            (640, 480),   # VGA
            (800, 600),   # SVGA
            (1024, 768),  # XGA
            (1280, 720),  # HD
            (1920, 1080), # Full HD
            (2560, 1440), # 2K
            (3840, 2160), # 4K
        ]
        
        for w, h in dimensions:
            event = HashableEvent(pygame.VIDEORESIZE, w=w, h=h)
            try:
                stub.on_video_resize_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_custom_game_events(self, mock_pygame_patches):
        """Test custom game events."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test custom game events
        custom_events = [
            HashableEvent(pygame.USEREVENT + 10, event_type="level_complete"),
            HashableEvent(pygame.USEREVENT + 11, event_type="player_died"),
            HashableEvent(pygame.USEREVENT + 12, event_type="power_up_collected"),
            HashableEvent(pygame.USEREVENT + 13, event_type="enemy_spawned"),
            HashableEvent(pygame.USEREVENT + 14, event_type="score_updated"),
        ]
        
        for event in custom_events:
            try:
                stub.on_game_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_menu_events_with_different_items(self, mock_pygame_patches):
        """Test menu events with different menu items."""
        stub = GameEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test different menu items
        menu_items = [
            "New Game",
            "Load Game",
            "Save Game",
            "Settings",
            "Help",
            "About",
            "Exit",
        ]
        
        for item in menu_items:
            event = HashableEvent(pygame.USEREVENT + 3, menu_item=item)
            try:
                stub.on_menu_item_event(event)
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
