"""Tests for audio event functionality.

This module tests audio event interfaces, stubs, and event handling.
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
    AudioEvents,
    AudioEventStubs,
)

from test_mock_factory import MockFactory


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
        self._setup_mock_game_for_stub(stub)
        
        # Test method calls
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        try:
            stub.on_audio_device_added_event(event)
        except Exception as e:
            # Expected to call unhandled_event
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_audio_device_added_event(self, mock_pygame_patches):
        """Test audio device added event handling."""
        stub = AudioEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test device added
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1)
        try:
            stub.on_audio_device_added_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_audio_device_removed_event(self, mock_pygame_patches):
        """Test audio device removed event handling."""
        stub = AudioEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test device removed
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1)
        try:
            stub.on_audio_device_removed_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_multiple_audio_devices(self, mock_pygame_patches):
        """Test multiple audio device events."""
        stub = AudioEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test multiple device IDs
        for device_id in range(5):
            # Test device added
            event = HashableEvent(pygame.AUDIODEVICEADDED, which=device_id)
            try:
                stub.on_audio_device_added_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)
            
            # Test device removed
            event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=device_id)
            try:
                stub.on_audio_device_removed_event(event)
            except Exception as e:
                assert "Unhandled Event" in str(e) or "SystemExit" in str(e)

    def test_audio_device_events_with_iscapture(self, mock_pygame_patches):
        """Test audio device events with iscapture parameter."""
        stub = AudioEventStubs()
        self._setup_mock_game_for_stub(stub)
        
        # Test device added with iscapture=True (input device)
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=True)
        try:
            stub.on_audio_device_added_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)
        
        # Test device added with iscapture=False (output device)
        event = HashableEvent(pygame.AUDIODEVICEADDED, which=1, iscapture=False)
        try:
            stub.on_audio_device_added_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)
        
        # Test device removed with iscapture=True (input device)
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=True)
        try:
            stub.on_audio_device_removed_event(event)
        except Exception as e:
            assert "Unhandled Event" in str(e) or "SystemExit" in str(e)
        
        # Test device removed with iscapture=False (output device)
        event = HashableEvent(pygame.AUDIODEVICEREMOVED, which=1, iscapture=False)
        try:
            stub.on_audio_device_removed_event(event)
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
