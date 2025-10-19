"""Tests for mouse event functionality.

This module tests mouse event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    MouseEvents,
    MouseEventStubs,
    UnhandledEventError,
)

from tests.mocks.test_mock_factory import MockFactory


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
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_mouse_motion_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_mouse_button_down_event(self, mock_pygame_patches):
        """Test mouse button down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_mouse_button_down_event": lambda event: scene.mouse_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        result = scene.on_mouse_button_down_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].button == 1

    def test_mouse_button_up_event(self, mock_pygame_patches):
        """Test mouse button up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_mouse_button_up_event": lambda event: scene.mouse_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        result = scene.on_mouse_button_up_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].button == 1

    def test_mouse_motion_event(self, mock_pygame_patches):
        """Test mouse motion event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_mouse_motion_event": lambda event: scene.mouse_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        result = scene.on_mouse_motion_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.mouse_events_received) == 1
        assert scene.mouse_events_received[0].pos == (100, 100)

    def test_mouse_wheel_event(self, mock_pygame_patches):
        """Test mouse wheel event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse wheel
        event = HashableEvent(pygame.MOUSEWHEEL, x=0, y=1)
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_mouse_wheel_event(event)
        # Exception was raised as expected

    def test_mouse_drag_event(self, mock_pygame_patches):
        """Test mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_mouse_drop_event(self, mock_pygame_patches):
        """Test mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_left_mouse_drag_event(self, mock_pygame_patches):
        """Test left mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test left mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_left_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_left_mouse_drop_event(self, mock_pygame_patches):
        """Test left mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test left mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=1, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_left_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_middle_mouse_drag_event(self, mock_pygame_patches):
        """Test middle mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test middle mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_middle_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_middle_mouse_drop_event(self, mock_pygame_patches):
        """Test middle mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test middle mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=2, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_middle_mouse_drop_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_right_mouse_drag_event(self, mock_pygame_patches):
        """Test right mouse drag event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test right mouse drag
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_right_mouse_drag_event(event, trigger="test_trigger")
        # Exception was raised as expected

    def test_right_mouse_drop_event(self, mock_pygame_patches):
        """Test right mouse drop event handling."""
        stub = MouseEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test right mouse drop
        event = HashableEvent(pygame.MOUSEBUTTONUP, button=3, pos=(100, 100))
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_right_mouse_drop_event(event, trigger="test_trigger")
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


class TestMouseManager:
    """Test MouseManager in isolation."""

    def test_mouse_manager_initialization(self, mock_pygame_patches):
        """Test MouseManager initializes correctly."""
        from glitchygames.events.mouse import MouseManager
        
        mock_game = Mock()
        manager = MouseManager(game=mock_game)
        
        assert manager.game == mock_game
        assert hasattr(manager, "on_mouse_motion_event")
        assert hasattr(manager, "on_mouse_button_down_event")

    def test_mouse_manager_events(self, mock_pygame_patches):
        """Test mouse event handling through manager."""
        from unittest.mock import patch

        from glitchygames.events.mouse import MouseManager

        from tests.mocks.test_mock_factory import MockFactory
        
        # Create a proper scene mock with all_sprites that's iterable
        scene_mock = MockFactory.create_event_test_scene_mock()
        
        # Create a mock sprite group that's iterable
        mock_sprites = [Mock(), Mock(), Mock()]  # List of mock sprites
        scene_mock.all_sprites = mock_sprites
        
        # Mock the scene's event handlers to prevent infinite loops
        scene_mock.on_mouse_motion_event = Mock()
        scene_mock.on_mouse_button_down_event = Mock()
        scene_mock.on_mouse_button_up_event = Mock()
        
        # self.game IS the scene, so we pass the scene directly
        manager = MouseManager(game=scene_mock)
        
        # Mock collided_sprites to prevent pygame.sprite.spritecollide calls
        with patch("glitchygames.events.mouse.collided_sprites", return_value=[]):
            # Test mouse motion - use patch to prevent recursive calls
            with patch.object(scene_mock, "on_mouse_motion_event") as mock_handler:
                motion_event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 100), rel=(10, 10), buttons=(0, 0, 0))
                manager.on_mouse_motion_event(motion_event)
                mock_handler.assert_called_once_with(motion_event)
            
            # Test mouse button down
            with patch.object(scene_mock, "on_mouse_button_down_event") as mock_handler:
                down_event = HashableEvent(pygame.MOUSEBUTTONDOWN, pos=(100, 100), button=1)
                manager.on_mouse_button_down_event(down_event)
                mock_handler.assert_called_once_with(down_event)
            
            # Test mouse button up
            with patch.object(scene_mock, "on_mouse_button_up_event") as mock_handler:
                up_event = HashableEvent(pygame.MOUSEBUTTONUP, pos=(100, 100), button=1)
                manager.on_mouse_button_up_event(up_event)
                mock_handler.assert_called_once_with(up_event)
