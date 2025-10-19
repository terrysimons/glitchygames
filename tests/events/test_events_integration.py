"""Integration tests for event system through GameEngine.

This module tests the full event flow: Engine → Managers → Scene → Stubs.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.events import HashableEvent, UnhandledEventError
from glitchygames.scenes import Scene

from tests.mocks.test_mock_factory import MockFactory


class TestEventIntegration:
    """Test full event flow through GameEngine."""

    def test_audio_event_through_engine(self, mock_pygame_patches, mock_managers):
        """Test audio events flow through the entire engine system."""
        # Use global mocks from mock_pygame_patches fixture
        # no_unhandled_events is enabled globally in conftest.py
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_audio_device_added_event": lambda event: True
            }
        )

        # Mock sys.argv to prevent argument parsing issues
        with patch("sys.argv", ["test_engine.py"]):
            # Create engine with test scene
            engine = GameEngine(game=scene)
            
            # Use centralized mocks for managers
            engine.scene_manager = Mock()
            engine.scene_manager.game_engine = engine
            engine.audio_manager = mock_managers["audio_manager"]
            engine.audio_manager.on_audio_device_added_event = Mock(return_value=True)
        
        # Create a proper HashableEvent
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        
        # Mock pygame.event.get to return our test event
        with patch("pygame.event.get", return_value=[event]):
            # Process events through the engine
            result = engine.process_events()
            
        # The event should be handled by the engine's audio manager
        assert result is True

    def test_controller_event_through_engine(self, mock_pygame_patches, mock_managers):
        """Test controller events flow through the entire engine system."""
        # Use global mocks from mock_pygame_patches fixture
        # no_unhandled_events is enabled globally in conftest.py
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_controller_axis_motion_event": lambda event: True
            }
        )

        # Mock sys.argv to prevent argument parsing issues
        with patch("sys.argv", ["test_engine.py"]):
            engine = GameEngine(game=scene)
            
            # Use centralized mocks for managers
            engine.scene_manager = Mock()
            engine.scene_manager.game_engine = engine
            engine.controller_manager = mock_managers["controller_manager"]
            engine.controller_manager.on_controller_axis_motion_event = Mock(return_value=True)
        
        # Create a proper pygame event with dict attribute
        pygame_event = pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=0, value=0.5)
        pygame_event.dict = {"type": pygame.CONTROLLERAXISMOTION, "axis": 0, "value": 0.5}
        
        with patch("pygame.event.get", return_value=[pygame_event]):
            result = engine.process_events()
            
        assert result is True

    def test_unhandled_event_falls_back_to_stubs(self, mock_pygame_patches, mock_managers):
        """Test that unhandled events fall back to stubs and cause UnhandledEventError."""
        # Use global mocks from mock_pygame_patches fixture
        # no_unhandled_events is enabled globally in conftest.py
        scene = MockFactory.create_event_test_scene_mock(
            options={
                "debug_events": False,
                "no_unhandled_events": True,  # Explicitly set to True
                "resolution": "800x480",  # Required by GameEngine
                "fps": 60.0,  # Required by GameEngine
                "update_type": "update",  # Required by GameEngine
                "use_gfxdraw": False,  # Required by GameEngine
                "windowed": True,  # Required by GameEngine
                "fps_refresh_rate": 1000,  # Required by GameEngine
            },
            event_handlers={}  # No event handlers - will fall back to stubs
        )

        # Mock sys.argv to prevent argument parsing issues
        with patch("sys.argv", ["test_engine.py"]):
            # Mock initialize_arguments to prevent it from overriding scene options
            with patch.object(GameEngine, "initialize_arguments", return_value=scene.options):
                engine = GameEngine(game=scene)
                
                # Use centralized mocks for managers
                engine.scene_manager = Mock()
                engine.scene_manager.game_engine = engine
                
                # Create a proper audio manager mock that calls the scene's audio event handlers
                mock_audio_manager = Mock()
                def audio_device_added_handler(event):
                    scene.on_audio_device_added_event(event)
                mock_audio_manager.on_audio_device_added_event = audio_device_added_handler
                engine.audio_manager = mock_audio_manager
        
        # Create a proper HashableEvent
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        
        with patch("pygame.event.get", return_value=[event]):
            # This should cause UnhandledEventError due to unhandled_event
            with pytest.raises(UnhandledEventError):
                engine.process_events()

    def test_event_routing_through_managers(self, mock_pygame_patches, mock_managers):
        """Test that events are properly routed through managers."""
        # Use global mocks from mock_pygame_patches fixture
        # For this test, we need to disable no_unhandled_events to test routing
        scene = MockFactory.create_event_test_scene_mock(
            options={
                "debug_events": False,
                "no_unhandled_events": False  # Don't exit on unhandled events for this test
            },
            event_handlers={
                "on_audio_device_added_event": lambda event: scene.audio_events_received.append(event) or True
            }
        )

        # Mock sys.argv to prevent argument parsing issues
        with patch("sys.argv", ["test_engine.py"]):
            engine = GameEngine(game=scene)
            
            # Use centralized mocks for managers
            engine.scene_manager = Mock()
            engine.scene_manager.game_engine = engine
            engine.audio_manager = mock_managers["audio_manager"]
        
        # Create multiple HashableEvents
        events = [
            HashableEvent(pygame.AUDIODEVICEADDED, which=1),
            HashableEvent(pygame.AUDIODEVICEADDED, which=2),
        ]
        
        with patch("pygame.event.get", return_value=events):
            result = engine.process_events()
            
        # Events should be routed to the scene
        assert result is True
        assert len(scene.audio_events_received) == 2
        assert scene.audio_events_received[0].which == 1
        assert scene.audio_events_received[1].which == 2

    def test_engine_event_handlers_are_configured(self, mock_pygame_patches, mock_managers):
        """Test that the engine's event handlers are properly configured."""
        # Use global mocks from mock_pygame_patches fixture
        scene = MockFactory.create_event_test_scene_mock()
        
        # Mock sys.argv to prevent argument parsing issues
        with patch("sys.argv", ["test_engine.py"]):
            engine = GameEngine(game=scene)
            
            # Use centralized mocks for managers
            engine.scene_manager = Mock()
            engine.scene_manager.game_engine = engine
        
        # Check that event handlers are registered
        assert pygame.AUDIODEVICEADDED in GameEngine.EVENT_HANDLERS
        assert pygame.AUDIODEVICEREMOVED in GameEngine.EVENT_HANDLERS
        assert pygame.CONTROLLERAXISMOTION in GameEngine.EVENT_HANDLERS
        assert pygame.CONTROLLERBUTTONDOWN in GameEngine.EVENT_HANDLERS
        
        # Check that handlers point to the right methods
        assert GameEngine.EVENT_HANDLERS[pygame.AUDIODEVICEADDED] == engine.process_audio_event
        assert GameEngine.EVENT_HANDLERS[pygame.CONTROLLERAXISMOTION] == engine.process_controller_event
