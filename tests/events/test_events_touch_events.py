"""Tests for touch event functionality.

This module tests touch event interfaces, stubs, and event handling.
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
    TouchEvents,
    TouchEventStubs,
)


class TestTouchEvents:
    """Test TouchEvents interface functionality."""

    def test_touch_events_interface(self, mock_pygame_patches):
        """Test TouchEvents interface methods."""
        # Test that TouchEvents has required abstract methods
        assert hasattr(TouchEvents, "on_touch_down_event")
        assert hasattr(TouchEvents, "on_touch_motion_event")
        assert hasattr(TouchEvents, "on_touch_up_event")
        assert hasattr(TouchEvents, "on_multi_touch_down_event")
        assert hasattr(TouchEvents, "on_multi_touch_motion_event")
        assert hasattr(TouchEvents, "on_multi_touch_up_event")

    def test_touch_event_stubs_implementation(self, mock_pygame_patches):
        """Test TouchEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = TouchEventStubs()
        assert hasattr(stub, "on_touch_down_event")
        assert hasattr(stub, "on_touch_motion_event")
        assert hasattr(stub, "on_touch_up_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_down_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_touch_down_event(self, mock_pygame_patches):
        """Test touch down event handling."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test touch down
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_down_event(event)
        # Exception was raised as expected

    def test_touch_motion_event(self, mock_pygame_patches):
        """Test touch motion event handling."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test touch motion
        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10)
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_motion_event(event)
        # Exception was raised as expected

    def test_touch_up_event(self, mock_pygame_patches):
        """Test touch up event handling."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test touch up
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_up_event(event)
        # Exception was raised as expected

    def test_multi_touch_down_event(self, mock_pygame_patches):
        """Test multi touch down event handling."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test multi touch down
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100)
        with pytest.raises((Exception, SystemExit)):
            stub.on_multi_touch_down_event(event)
        # Exception was raised as expected

    def test_multi_touch_motion_event(self, mock_pygame_patches):
        """Test multi touch motion event handling."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test multi touch motion
        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10)
        with pytest.raises((Exception, SystemExit)):
            stub.on_multi_touch_motion_event(event)
        # Exception was raised as expected

    def test_multi_touch_up_event(self, mock_pygame_patches):
        """Test multi touch up event handling."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test multi touch up
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100)
        with pytest.raises((Exception, SystemExit)):
            stub.on_multi_touch_up_event(event)
        # Exception was raised as expected

    def test_multiple_finger_events(self, mock_pygame_patches):
        """Test multiple finger touch events."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test multiple fingers
        for finger_id in range(5):
            # Test finger down
            event = HashableEvent(pygame.FINGERDOWN, finger_id=finger_id, x=100, y=100)
            with pytest.raises((Exception, SystemExit)):
                stub.on_touch_down_event(event)
            # Exception was raised as expected

            # Test finger motion
            event = HashableEvent(pygame.FINGERMOTION, finger_id=finger_id, x=100, y=100, dx=10, dy=10)  # noqa: E501
            with pytest.raises((Exception, SystemExit)):
                stub.on_touch_motion_event(event)
            # Exception was raised as expected

            # Test finger up
            event = HashableEvent(pygame.FINGERUP, finger_id=finger_id, x=100, y=100)
            with pytest.raises((Exception, SystemExit)):
                stub.on_touch_up_event(event)
            # Exception was raised as expected

    def test_touch_events_with_pressure(self, mock_pygame_patches):
        """Test touch events with pressure values."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test touch down with pressure
        event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=100, y=100, pressure=0.8)
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_down_event(event)
        # Exception was raised as expected

        # Test touch motion with pressure
        event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=100, y=100, dx=10, dy=10, pressure=0.6)  # noqa: E501
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_motion_event(event)
        # Exception was raised as expected

        # Test touch up with pressure
        event = HashableEvent(pygame.FINGERUP, finger_id=1, x=100, y=100, pressure=0.0)
        with pytest.raises((Exception, SystemExit)):
            stub.on_touch_up_event(event)
        # Exception was raised as expected

    def test_touch_events_with_different_positions(self, mock_pygame_patches):
        """Test touch events with different positions."""
        stub = TouchEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test different touch positions
        positions = [
            (0, 0),      # Top-left
            (100, 100),  # Center
            (200, 200),  # Bottom-right
            (50, 150),   # Middle-left
            (150, 50),   # Top-right
        ]

        for x, y in positions:
            # Test touch down
            event = HashableEvent(pygame.FINGERDOWN, finger_id=1, x=x, y=y)
            with pytest.raises((Exception, SystemExit)):
                stub.on_touch_down_event(event)
            # Exception was raised as expected

            # Test touch motion
            event = HashableEvent(pygame.FINGERMOTION, finger_id=1, x=x, y=y, dx=5, dy=5)
            with pytest.raises((Exception, SystemExit)):
                stub.on_touch_motion_event(event)
            # Exception was raised as expected

            # Test touch up
            event = HashableEvent(pygame.FINGERUP, finger_id=1, x=x, y=y)
            with pytest.raises((Exception, SystemExit)):
                stub.on_touch_up_event(event)
            # Exception was raised as expected

    def _setup_mock_game_for_stub(self, stub):
        """Set up mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": True
        }
        stub.options = mock_game.options
        return mock_game


class TestTouchManager:
    """Test TouchManager in isolation."""

    def test_touch_manager_initialization(self, mock_pygame_patches):
        """Test TouchManager initializes correctly."""
        from glitchygames.events.touch import TouchManager
        
        mock_game = Mock()
        manager = TouchManager(game=mock_game)
        
        assert manager.game == mock_game
        assert hasattr(manager, "proxies")
        assert isinstance(manager.proxies, list)

    def test_touch_manager_events(self, mock_pygame_patches):
        """Test touch event handling through manager."""
        from glitchygames.events.touch import TouchManager
        
        mock_game = Mock()
        manager = TouchManager(game=mock_game)
        
        # Test touch finger down
        touch_down_event = HashableEvent(pygame.FINGERDOWN, touch_id=1, finger_id=1, x=100, y=100, dx=0, dy=0)
        manager.on_touch_finger_down_event(touch_down_event)
        
        # Test touch finger up
        touch_up_event = HashableEvent(pygame.FINGERUP, touch_id=1, finger_id=1, x=100, y=100, dx=0, dy=0)
        manager.on_touch_finger_up_event(touch_up_event)
        
        # Test touch finger motion
        touch_motion_event = HashableEvent(pygame.FINGERMOTION, touch_id=1, finger_id=1, x=110, y=110, dx=10, dy=10)
        manager.on_touch_finger_motion_event(touch_motion_event)
