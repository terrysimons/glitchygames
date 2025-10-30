"""Tests for drop event functionality.

This module tests drop event interfaces, stubs, and event handling.
"""

import argparse
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    DropEvents,
    DropEventStubs,
    HashableEvent,
    UnhandledEventError,
)
from glitchygames.events.drop import DropEventManager

from tests.mocks.test_mock_factory import MockFactory


class TestDropEvents:
    """Test DropEvents interface functionality."""

    def test_drop_events_interface(self, mock_pygame_patches):
        """Test DropEvents interface methods."""
        # Test that DropEvents has required abstract methods
        assert hasattr(DropEvents, "on_drop_begin_event")
        assert hasattr(DropEvents, "on_drop_file_event")
        assert hasattr(DropEvents, "on_drop_text_event")
        assert hasattr(DropEvents, "on_drop_complete_event")

    def test_drop_event_stubs_implementation(self, mock_pygame_patches):
        """Test DropEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = DropEventStubs()
        assert hasattr(stub, "on_drop_begin_event")
        assert hasattr(stub, "on_drop_file_event")
        assert hasattr(stub, "on_drop_text_event")
        assert hasattr(stub, "on_drop_complete_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.DROPBEGIN)
        # Mock the logger to suppress "Unhandled Event" messages during testing

        with patch("glitchygames.events.LOG.error"):

            with pytest.raises(UnhandledEventError):
            
                stub.on_drop_begin_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_drop_begin_event(self, mock_pygame_patches):
        """Test drop begin event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_begin_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test drop begin
        event = HashableEvent(pygame.DROPBEGIN)
        result = scene.on_drop_begin_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPBEGIN

    def test_drop_file_event(self, mock_pygame_patches):
        """Test drop file event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_file_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test drop file
        event = HashableEvent(pygame.DROPFILE, file="/path/to/file.txt")
        result = scene.on_drop_file_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPFILE
        assert scene.drop_events_received[0].file == "/path/to/file.txt"

    def test_drop_text_event(self, mock_pygame_patches):
        """Test drop text event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_text_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test drop text
        event = HashableEvent(pygame.DROPTEXT, text="Hello World")
        result = scene.on_drop_text_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPTEXT
        assert scene.drop_events_received[0].text == "Hello World"

    def test_drop_complete_event(self, mock_pygame_patches):
        """Test drop complete event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_complete_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test drop complete
        event = HashableEvent(pygame.DROPCOMPLETE)
        result = scene.on_drop_complete_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPCOMPLETE

    def test_multiple_drop_files(self, mock_pygame_patches):
        """Test multiple drop file events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_file_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test multiple file drops
        file_paths = [
            "/path/to/file1.txt",
            "/path/to/file2.png",
            "/path/to/file3.pdf",
            "/path/to/file4.mp3",
            "/path/to/file5.zip",
        ]

        for file_path in file_paths:
            event = HashableEvent(pygame.DROPFILE, file=file_path)
            result = scene.on_drop_file_event(event)
            assert result is True

        # All events should be handled successfully
        assert len(scene.drop_events_received) == len(file_paths)
        for i, file_path in enumerate(file_paths):
            assert scene.drop_events_received[i].type == pygame.DROPFILE
            assert scene.drop_events_received[i].file == file_path

    def test_multiple_drop_texts(self, mock_pygame_patches):
        """Test multiple drop text events."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_text_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test multiple text drops
        text_contents = [
            "Hello World",
            "This is a test",
            "Drop and drag functionality",
            "Text with special characters: !@#$%^&*()",
            "Multiline\ntext\ncontent",
        ]

        for text in text_contents:
            event = HashableEvent(pygame.DROPTEXT, text=text)
            result = scene.on_drop_text_event(event)
            assert result is True

        # All events should be handled successfully
        assert len(scene.drop_events_received) == len(text_contents)
        for i, text in enumerate(text_contents):
            assert scene.drop_events_received[i].type == pygame.DROPTEXT
            assert scene.drop_events_received[i].text == text

    def test_drop_events_with_positions(self, mock_pygame_patches):
        """Test drop events with position information."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_begin_event": lambda event: (scene.drop_events_received.append(event), True)[1],
                "on_drop_file_event": lambda event: (scene.drop_events_received.append(event), True)[1],
                "on_drop_text_event": lambda event: (scene.drop_events_received.append(event), True)[1],
                "on_drop_complete_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test drop begin with position
        event = HashableEvent(pygame.DROPBEGIN, x=100, y=100)
        result = scene.on_drop_begin_event(event)
        assert result is True

        # Test drop file with position
        event = HashableEvent(pygame.DROPFILE, file="/path/to/file.txt", x=150, y=150)
        result = scene.on_drop_file_event(event)
        assert result is True

        # Test drop text with position
        event = HashableEvent(pygame.DROPTEXT, text="Hello", x=200, y=200)
        result = scene.on_drop_text_event(event)
        assert result is True

        # Test drop complete with position
        event = HashableEvent(pygame.DROPCOMPLETE, x=250, y=250)
        result = scene.on_drop_complete_event(event)
        assert result is True

        # All events should be handled successfully
        assert len(scene.drop_events_received) == 4
        assert scene.drop_events_received[0].type == pygame.DROPBEGIN
        assert scene.drop_events_received[0].x == 100
        assert scene.drop_events_received[0].y == 100

    def test_drop_events_with_different_file_types(self, mock_pygame_patches):
        """Test drop events with different file types."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_file_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test different file types
        file_types = [
            "/path/to/image.png",
            "/path/to/document.pdf",
            "/path/to/audio.mp3",
            "/path/to/video.mp4",
            "/path/to/archive.zip",
            "/path/to/executable.exe",
            "/path/to/script.py",
            "/path/to/data.json",
        ]

        for file_path in file_types:
            event = HashableEvent(pygame.DROPFILE, file=file_path)
            result = scene.on_drop_file_event(event)
            assert result is True

        # All events should be handled successfully
        assert len(scene.drop_events_received) == len(file_types)
        for i, file_path in enumerate(file_types):
            assert scene.drop_events_received[i].type == pygame.DROPFILE
            assert scene.drop_events_received[i].file == file_path

    def test_drop_events_with_special_characters(self, mock_pygame_patches):
        """Test drop events with special characters in file paths and text."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_drop_file_event": lambda event: (scene.drop_events_received.append(event), True)[1],
                "on_drop_text_event": lambda event: (scene.drop_events_received.append(event), True)[1]
            }
        )

        # Test file paths with special characters
        special_file_paths = [
            "/path/with spaces/file.txt",
            "/path/with-dashes/file.txt",
            "/path/with_underscores/file.txt",
            "/path/with.dots/file.txt",
            "/path/with(parantheses)/file.txt",
            "/path/with[brackets]/file.txt",
            "/path/with{braces}/file.txt",
        ]

        for file_path in special_file_paths:
            event = HashableEvent(pygame.DROPFILE, file=file_path)
            result = scene.on_drop_file_event(event)
            assert result is True

        # Test text with special characters
        special_texts = [
            "Text with spaces",
            "Text-with-dashes",
            "Text_with_underscores",
            "Text.with.dots",
            "Text(with)parantheses",
            "Text[with]brackets",
            "Text{with}braces",
            "Text with\nnewlines",
            "Text with\ttabs",
            "Text with unicode: ñáéíóú",
        ]

        for text in special_texts:
            event = HashableEvent(pygame.DROPTEXT, text=text)
            result = scene.on_drop_text_event(event)
            assert result is True

        # All events should be handled successfully
        total_events = len(special_file_paths) + len(special_texts)
        assert len(scene.drop_events_received) == total_events

    def _setup_mock_game_for_stub(self, stub):
        """Set up mock game object for event stubs."""
        mock_game = Mock()
        mock_game.options = {
            "debug_events": False,
            "no_unhandled_events": True
        }
        stub.options = mock_game.options
        return mock_game


class TestDropEventManagerCoverage:
    """Test coverage for drop manager functionality."""

    def test_drop_manager_initialization(self, mock_pygame_patches):
        """Test DropEventManager initialization."""
        mock_game = Mock()
        manager = DropEventManager(game=mock_game)
        
        assert manager.game == mock_game
        assert hasattr(manager, "on_drop_begin_event")
        assert hasattr(manager, "on_drop_file_event")

    def test_drop_manager_initialization_no_game(self, mock_pygame_patches):
        """Test DropEventManager initialization without game."""
        manager = DropEventManager(game=None)
        assert manager.game is None

    def test_drop_manager_args(self, mock_pygame_patches):
        """Test DropEventManager args method."""
        parser = argparse.ArgumentParser()
        result = DropEventManager.args(parser)

        assert result is parser

    def test_drop_proxy_initialization(self, mock_pygame_patches):
        """Test drop proxy initialization."""
        mock_game = Mock()
        manager = DropEventManager(game=mock_game)

        # Test that proxy is created
        assert hasattr(manager, "proxies")
        assert len(manager.proxies) > 0

    def test_drop_proxy_initialization_no_game(self, mock_pygame_patches):
        """Test drop proxy initialization without game."""
        manager = DropEventManager(game=None)

        # Test that proxy is created even without game
        assert hasattr(manager, "proxies")
        assert len(manager.proxies) > 0

    def test_drop_proxy_on_drop_begin_event(self, mock_pygame_patches):
        """Test drop proxy on_drop_begin_event."""
        # Create a mock game with the required methods
        mock_game = Mock()
        mock_game.on_drop_begin_event = Mock()

        manager = DropEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPBEGIN)
        # Should not raise exception
        proxy.on_drop_begin_event(event)
        mock_game.on_drop_begin_event.assert_called_once_with(event)

    def test_drop_proxy_on_drop_complete_event(self, mock_pygame_patches):
        """Test drop proxy on_drop_complete_event."""
        # Create a mock game with the required methods
        mock_game = Mock()
        mock_game.on_drop_complete_event = Mock()

        manager = DropEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPCOMPLETE)
        # Should not raise exception
        proxy.on_drop_complete_event(event)
        mock_game.on_drop_complete_event.assert_called_once_with(event)

    def test_drop_proxy_on_drop_file_event(self, mock_pygame_patches):
        """Test drop proxy on_drop_file_event."""
        # Create a mock game with the required methods
        mock_game = Mock()
        mock_game.on_drop_file_event = Mock()

        manager = DropEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPFILE, file="/path/to/file.txt")
        # Should not raise exception
        proxy.on_drop_file_event(event)
        mock_game.on_drop_file_event.assert_called_once_with(event)

    def test_drop_proxy_on_drop_text_event(self, mock_pygame_patches):
        """Test drop proxy on_drop_text_event."""
        # Create a mock game with the required methods
        mock_game = Mock()
        mock_game.on_drop_text_event = Mock()

        manager = DropEventManager(game=mock_game)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPTEXT, text="dropped text")
        # Should not raise exception
        proxy.on_drop_text_event(event)
        mock_game.on_drop_text_event.assert_called_once_with(event)
