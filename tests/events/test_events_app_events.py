"""Tests for app event functionality.

This module tests app event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.events import (
    AppEvents,
    AppEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.events.app import AppManager

from tests.mocks.test_mock_factory import MockFactory


class TestAppEvents:
    """Test AppEvents interface functionality."""

    def test_app_events_interface(self, mock_pygame_patches):
        """Test AppEvents interface methods."""
        # Test that AppEvents has required abstract methods
        assert hasattr(AppEvents, "on_app_did_enter_background_event")
        assert hasattr(AppEvents, "on_app_did_enter_foreground_event")
        assert hasattr(AppEvents, "on_app_will_enter_background_event")
        assert hasattr(AppEvents, "on_app_will_enter_foreground_event")
        assert hasattr(AppEvents, "on_app_low_memory_event")
        assert hasattr(AppEvents, "on_app_terminating_event")

    def test_app_event_stubs_implementation(self, mock_pygame_patches):
        """Test AppEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = AppEventStubs()
        assert hasattr(stub, "on_app_did_enter_background_event")
        assert hasattr(stub, "on_app_did_enter_foreground_event")
        assert hasattr(stub, "on_app_will_enter_background_event")
        assert hasattr(stub, "on_app_will_enter_foreground_event")
        assert hasattr(stub, "on_app_low_memory_event")
        assert hasattr(stub, "on_app_terminating_event")

        # Test method calls - suppress log messages since these will trigger unhandled_event
        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        with patch("glitchygames.events.LOG.error"), pytest.raises(UnhandledEventError):
            stub.on_app_did_enter_background_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_app_did_enter_background_event(self, mock_pygame_patches):
        """Test app did enter background event."""
        # Use centralized mock for scene with event handlers
        def app_did_enter_background_handler(event):
            scene.game_events_received.append(("app_did_enter_background", event))

        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={"on_app_did_enter_background_event": app_did_enter_background_handler}
        )

        # Test app did enter background event
        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        result = scene.on_app_did_enter_background_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_did_enter_background"
        assert scene.game_events_received[0][1].type == pygame.APP_DIDENTERBACKGROUND

    def test_app_did_enter_foreground_event(self, mock_pygame_patches):
        """Test app did enter foreground event."""
        # Use centralized mock for scene with event handlers
        def app_did_enter_foreground_handler(event):
            scene.game_events_received.append(("app_did_enter_foreground", event))

        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={"on_app_did_enter_foreground_event": app_did_enter_foreground_handler}
        )

        # Test app did enter foreground event
        event = HashableEvent(pygame.APP_DIDENTERFOREGROUND)
        result = scene.on_app_did_enter_foreground_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_did_enter_foreground"
        assert scene.game_events_received[0][1].type == pygame.APP_DIDENTERFOREGROUND

    def test_app_will_enter_background_event(self, mock_pygame_patches):
        """Test app will enter background event."""
        # Use centralized mock for scene with event handlers
        def app_will_enter_background_handler(event):
            scene.game_events_received.append(("app_will_enter_background", event))

        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={"on_app_will_enter_background_event": app_will_enter_background_handler}
        )

        # Test app will enter background event
        event = HashableEvent(pygame.APP_WILLENTERBACKGROUND)
        result = scene.on_app_will_enter_background_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_will_enter_background"
        assert scene.game_events_received[0][1].type == pygame.APP_WILLENTERBACKGROUND

    def test_app_will_enter_foreground_event(self, mock_pygame_patches):
        """Test app will enter foreground event."""
        # Use centralized mock for scene with event handlers
        def app_will_enter_foreground_handler(event):
            scene.game_events_received.append(("app_will_enter_foreground", event))

        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={"on_app_will_enter_foreground_event": app_will_enter_foreground_handler}
        )

        # Test app will enter foreground event
        event = HashableEvent(pygame.APP_WILLENTERFOREGROUND)
        result = scene.on_app_will_enter_foreground_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_will_enter_foreground"
        assert scene.game_events_received[0][1].type == pygame.APP_WILLENTERFOREGROUND

    def test_app_low_memory_event(self, mock_pygame_patches):
        """Test app low memory event."""
        # Use centralized mock for scene with event handlers
        def app_low_memory_handler(event):
            scene.game_events_received.append(("app_low_memory", event))

        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={"on_app_low_memory_event": app_low_memory_handler}
        )

        # Test app low memory event
        event = HashableEvent(pygame.APP_LOWMEMORY)
        result = scene.on_app_low_memory_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_low_memory"
        assert scene.game_events_received[0][1].type == pygame.APP_LOWMEMORY

    def test_app_terminating_event(self, mock_pygame_patches):
        """Test app terminating event."""
        # Use centralized mock for scene with event handlers
        def app_terminating_handler(event):
            scene.game_events_received.append(("app_terminating", event))

        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={"on_app_terminating_event": app_terminating_handler}
        )

        # Test app terminating event
        event = HashableEvent(pygame.APP_TERMINATING)
        result = scene.on_app_terminating_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_terminating"
        assert scene.game_events_received[0][1].type == pygame.APP_TERMINATING


class TestAppEventFlow:
    """Test app event flow through the engine."""

    def test_app_event_through_engine(self, mock_pygame_patches):
        """Test app event processing through the engine."""
        # Create a mock scene with app event handlers
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_app_did_enter_background_event": lambda event: scene.game_events_received.append(("app_did_enter_background", event)) or True
            }
        )

        # Mock the argument parsing to avoid command line issues
        with patch("glitchygames.engine.GameEngine.initialize_arguments") as mock_init_args:
            mock_init_args.return_value = {
                "debug_events": False, 
                "no_unhandled_events": True,
                "fps": 60.0,
                "update_type": "update",
                "use_gfxdraw": False,
                "windowed": True,
                "resolution": "800x600",
                "fps_refresh_rate": 1.0
            }
            
            # Create engine with the scene
            engine = GameEngine(scene)
            
            # Initialize the app manager manually since start() isn't called
            from glitchygames.events.app import AppManager
            engine.app_manager = AppManager(game=scene)
            
            # Also initialize event handlers manually
            engine.initialize_event_handlers()

            # Test app did enter background event
            event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
            
            # Call the event handler directly (bypassing handle_event)
            engine.process_app_event(event)

            # Verify the event was processed
            assert len(scene.game_events_received) == 1
            assert scene.game_events_received[0][0] == "app_did_enter_background"
            assert scene.game_events_received[0][1].type == pygame.APP_DIDENTERBACKGROUND

    def test_app_event_falls_back_to_stubs(self, mock_pygame_patches):
        """Test that app events fall back to stubs when no handlers are defined."""
        # Create a scene without app event handlers
        scene = MockFactory.create_event_test_scene_mock(event_handlers={})

        # Create app manager
        manager = AppManager(game=scene)

        # Test app did enter background event - should fall back to stubs
        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        with patch("glitchygames.events.LOG.error"), pytest.raises(UnhandledEventError):
            manager.on_app_did_enter_background_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_app_manager_directly(self, mock_pygame_patches):
        """Test app manager directly."""
        # Create a scene with app event handlers
        scene = MockFactory.create_event_test_scene_mock()

        # Create app manager
        manager = AppManager(game=scene)

        # Test app did enter background event
        event = HashableEvent(pygame.APP_DIDENTERBACKGROUND)
        result = manager.on_app_did_enter_background_event(event)

        # Verify the event was processed
        assert result is None
        assert len(scene.game_events_received) == 1
        assert scene.game_events_received[0][0] == "app_did_enter_background"
        assert scene.game_events_received[0][1].type == pygame.APP_DIDENTERBACKGROUND
