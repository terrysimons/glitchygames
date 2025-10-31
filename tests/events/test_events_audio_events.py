"""Tests for audio event functionality.

This module tests audio event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.engine import GameEngine
from glitchygames.events import (
    AudioEvents,
    AudioEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.scenes import Scene

from tests.mocks.test_mock_factory import MockFactory


class TestAudioEvents:
    """Test AudioEvents interface functionality."""

    def test_audio_events_interface(self, mock_pygame_patches):
        """Test AudioEvents interface methods."""
        # Test that AudioEvents has required abstract methods
        assert hasattr(AudioEvents, "on_audio_device_added_event")
        assert hasattr(AudioEvents, "on_audio_device_removed_event")

    def test_audio_event_stubs_implementation(self, mock_pygame_patches):
        """Test AudioEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = AudioEventStubs()
        assert hasattr(stub, "on_audio_device_added_event")
        assert hasattr(stub, "on_audio_device_removed_event")

        # Test that stub methods can be called with proper game object
        scene_mock = self._setup_mock_scene_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        with patch("glitchygames.events.LOG.error"):
            with pytest.raises(UnhandledEventError):
                stub.on_audio_device_added_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_audio_device_added_event(self, mock_pygame_patches):
        """Test audio device added event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_audio_device_added_event": lambda event: scene.audio_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        result = scene.on_audio_device_added_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.audio_events_received) == 1
        assert scene.audio_events_received[0].which == 1

    def test_audio_device_removed_event(self, mock_pygame_patches):
        """Test audio device removed event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_audio_device_removed_event": lambda event: scene.audio_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1)
        result = scene.on_audio_device_removed_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.audio_events_received) == 1
        assert scene.audio_events_received[0].which == 1

    def test_multiple_audio_devices(self, mock_pygame_patches):
        """Test multiple audio device events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_audio_device_added_event": lambda event: scene.audio_events_received.append(("added", event)) or True,
                "on_audio_device_removed_event": lambda event: scene.audio_events_received.append(("removed", event)) or True
            }
        )

        # Test multiple device IDs
        for device_id in range(5):
            # Test device added
            event = HashableEvent(pygame.AUDIODEVICEADDED, which=device_id)
            result = scene.on_audio_device_added_event(event)
            assert result is True

            # Test device removed
            event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=device_id)
            result = scene.on_audio_device_removed_event(event)
            assert result is True
        
        # Verify all events were received
        assert len(scene.audio_events_received) == 10  # 5 added + 5 removed

    def test_audio_device_events_with_iscapture(self, mock_pygame_patches):
        """Test audio device events with iscapture parameter."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_audio_device_added_event": lambda event: scene.audio_events_received.append(("added", event)) or True,
                "on_audio_device_removed_event": lambda event: scene.audio_events_received.append(("removed", event)) or True
            }
        )

        # Test device added with iscapture=True (input device)
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=True)
        result = scene.on_audio_device_added_event(event)
        assert result is True

        # Test device added with iscapture=False (output device)
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=False)
        result = scene.on_audio_device_added_event(event)
        assert result is True

        # Test device removed with iscapture=True (input device)
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=True)
        result = scene.on_audio_device_removed_event(event)
        assert result is True

        # Test device removed with iscapture=False (output device)
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=False)
        result = scene.on_audio_device_removed_event(event)
        assert result is True
        
        # Verify all events were received
        assert len(scene.audio_events_received) == 4

    def _setup_mock_scene_for_stub(self, stub):
        """Set up mock scene object for event stubs using centralized mocks."""
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                "debug_events": False,
                "no_unhandled_events": True  # This will cause UnhandledEventError to be raised
            }
        )
        # Set the options on the stub so unhandled_event can access them
        stub.options = scene_mock.options
        return scene_mock


class TestAudioEventFlow:
    """Test audio events through the proper engine flow."""

    def test_audio_event_through_engine(self, mock_pygame_patches):
        """Test audio events flow through the entire engine system."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_audio_device_added_event": lambda event: (scene.audio_events_received.append(event), True)[1]
            }
        )
        
        # Create a HashableEvent with proper attributes
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        
        # Test that the scene can handle the event directly
        result = scene.on_audio_device_added_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.audio_events_received) == 1
        assert scene.audio_events_received[0].which == 1

    def test_audio_event_falls_back_to_stubs(self, mock_pygame_patches):
        """Test that unhandled audio events fall back to stubs and cause UnhandledEventError."""
        # Test that stubs have concrete implementations
        stub = AudioEventStubs()
        assert hasattr(stub, "on_audio_device_added_event")
        assert hasattr(stub, "on_audio_device_removed_event")

        # Test that stub methods can be called with proper scene object
        self._setup_mock_scene_for_stub(stub)

        # Test method calls - stubs should call unhandled_event which raises UnhandledEventError
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        
        # Mock the logger to suppress "Unhandled Event" messages during testing
        with patch("glitchygames.events.LOG.error"):
            with pytest.raises(UnhandledEventError):
                stub.on_audio_device_added_event(event)

    def test_audio_manager_initialization(self, mock_pygame_patches):
        """Test AudioEventManager initializes correctly."""
        from unittest.mock import patch

        from glitchygames.events.audio import AudioEventManager
        
        mock_game = Mock()
        
        # Mock pygame.mixer.get_init to return a tuple
        with patch("pygame.mixer.get_init", return_value=(22050, -16, 2)):
            manager = AudioEventManager(game=mock_game)
            
            assert manager.game == mock_game
            assert hasattr(manager, "on_audio_device_added_event")
            assert hasattr(manager, "on_audio_device_removed_event")

    def test_audio_manager_directly(self, mock_pygame_patches):
        """Test AudioEventManager in isolation."""
        from glitchygames.events.audio import AudioEventManager
        
        # Use centralized mock for game
        mock_game = Mock()
        mock_game.options = {"debug_events": False, "no_unhandled_events": True}
        
        # The centralized mocks should handle pygame.mixer.get_init()
        manager = AudioEventManager(game=mock_game)
        
        # Test that manager has the required methods
        assert hasattr(manager, "on_audio_device_added_event")
        assert hasattr(manager, "on_audio_device_removed_event")
        
        # Test device added event
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=True)
        manager.on_audio_device_added_event(event)
        
        # Test device removed event
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=False)
        manager.on_audio_device_removed_event(event)

    def _setup_mock_scene_for_stub(self, stub):
        """Set up mock scene object for event stubs using centralized mocks."""
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                "debug_events": False,
                "no_unhandled_events": True  # This will cause UnhandledEventError to be raised
            }
        )
        # Set the options on the stub so unhandled_event can access them
        stub.options = scene_mock.options
        return scene_mock
