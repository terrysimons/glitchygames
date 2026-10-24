"""Tests for drop event functionality.

This module tests drop event interfaces, stubs, and event handling.
"""

import argparse
import sys
from pathlib import Path

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
from glitchygames.scenes import Scene

EVENT_TEST_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class DropRecordingScene(Scene):
    """A real scene that records the drop events it receives, in order."""

    def __init__(self, options=None, groups=None):
        """Create the scene with no drop events received yet."""
        super().__init__(
            options=options if options is not None else dict(EVENT_TEST_OPTIONS),
            groups=groups,
        )
        self.drop_events_received: list[HashableEvent] = []

    def on_drop_begin_event(self, event):
        """Record a drop begin event."""
        self.drop_events_received.append(event)

    def on_drop_file_event(self, event):
        """Record a drop file event."""
        self.drop_events_received.append(event)

    def on_drop_text_event(self, event):
        """Record a drop text event."""
        self.drop_events_received.append(event)

    def on_drop_complete_event(self, event):
        """Record a drop complete event."""
        self.drop_events_received.append(event)


def drop_scene_and_manager():
    """Create a recording scene and a real DropEventManager delivering to it.

    Returns:
        tuple[DropRecordingScene, DropEventManager]: The scene and its manager.

    """
    scene = DropRecordingScene()
    return scene, DropEventManager(game=scene)


class TestDropEvents:
    """Test DropEvents interface functionality."""

    def test_drop_events_interface(self):
        """Test DropEvents interface methods."""
        # Test that DropEvents has required abstract methods
        assert hasattr(DropEvents, 'on_drop_begin_event')
        assert hasattr(DropEvents, 'on_drop_file_event')
        assert hasattr(DropEvents, 'on_drop_text_event')
        assert hasattr(DropEvents, 'on_drop_complete_event')

    def test_drop_event_stubs_implementation(self, mocker):
        """Test DropEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = DropEventStubs()
        assert hasattr(stub, 'on_drop_begin_event')
        assert hasattr(stub, 'on_drop_file_event')
        assert hasattr(stub, 'on_drop_text_event')
        assert hasattr(stub, 'on_drop_complete_event')

        # Unhandled events raise with these options
        self._give_stub_strict_options(stub)

        # Test method calls
        event = HashableEvent(pygame.DROPBEGIN)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_drop_begin_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_drop_begin_event(self):
        """Test drop begin event handling."""
        scene, manager = drop_scene_and_manager()

        # Test drop begin
        event = HashableEvent(pygame.DROPBEGIN)
        manager.on_drop_begin_event(event)

        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPBEGIN

    def test_drop_file_event(self):
        """Test drop file event handling."""
        scene, manager = drop_scene_and_manager()

        # Test drop file
        event = HashableEvent(pygame.DROPFILE, file='/path/to/file.txt')
        manager.on_drop_file_event(event)

        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPFILE
        assert scene.drop_events_received[0].file == '/path/to/file.txt'

    def test_drop_text_event(self):
        """Test drop text event handling."""
        scene, manager = drop_scene_and_manager()

        # Test drop text
        event = HashableEvent(pygame.DROPTEXT, text='Hello World')
        manager.on_drop_text_event(event)

        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPTEXT
        assert scene.drop_events_received[0].text == 'Hello World'

    def test_drop_complete_event(self):
        """Test drop complete event handling."""
        scene, manager = drop_scene_and_manager()

        # Test drop complete
        event = HashableEvent(pygame.DROPCOMPLETE)
        manager.on_drop_complete_event(event)

        assert len(scene.drop_events_received) == 1
        assert scene.drop_events_received[0].type == pygame.DROPCOMPLETE

    def test_multiple_drop_files(self):
        """Test multiple drop file events."""
        scene, manager = drop_scene_and_manager()

        # Test multiple file drops
        file_paths = [
            '/path/to/file1.txt',
            '/path/to/file2.png',
            '/path/to/file3.pdf',
            '/path/to/file4.mp3',
            '/path/to/file5.zip',
        ]

        for file_path in file_paths:
            event = HashableEvent(pygame.DROPFILE, file=file_path)
            manager.on_drop_file_event(event)

        # All events should be handled successfully
        assert len(scene.drop_events_received) == len(file_paths)
        for i, file_path in enumerate(file_paths):
            assert scene.drop_events_received[i].type == pygame.DROPFILE
            assert scene.drop_events_received[i].file == file_path

    def test_multiple_drop_texts(self):
        """Test multiple drop text events."""
        scene, manager = drop_scene_and_manager()

        # Test multiple text drops
        text_contents = [
            'Hello World',
            'This is a test',
            'Drop and drag functionality',
            'Text with special characters: !@#$%^&*()',
            'Multiline\ntext\ncontent',
        ]

        for text in text_contents:
            event = HashableEvent(pygame.DROPTEXT, text=text)
            manager.on_drop_text_event(event)

        # All events should be handled successfully
        assert len(scene.drop_events_received) == len(text_contents)
        for i, text in enumerate(text_contents):
            assert scene.drop_events_received[i].type == pygame.DROPTEXT
            assert scene.drop_events_received[i].text == text

    def test_drop_events_with_positions(self):
        """Test drop events with position information."""
        scene, manager = drop_scene_and_manager()

        # Test drop begin with position
        event = HashableEvent(pygame.DROPBEGIN, x=100, y=100)
        manager.on_drop_begin_event(event)

        # Test drop file with position
        event = HashableEvent(pygame.DROPFILE, file='/path/to/file.txt', x=150, y=150)
        manager.on_drop_file_event(event)

        # Test drop text with position
        event = HashableEvent(pygame.DROPTEXT, text='Hello', x=200, y=200)
        manager.on_drop_text_event(event)

        # Test drop complete with position
        event = HashableEvent(pygame.DROPCOMPLETE, x=250, y=250)
        manager.on_drop_complete_event(event)

        # All events should be handled successfully
        assert len(scene.drop_events_received) == 4
        assert scene.drop_events_received[0].type == pygame.DROPBEGIN
        assert scene.drop_events_received[0].x == 100
        assert scene.drop_events_received[0].y == 100

    def test_drop_events_with_different_file_types(self):
        """Test drop events with different file types."""
        scene, manager = drop_scene_and_manager()

        # Test different file types
        file_types = [
            '/path/to/image.png',
            '/path/to/document.pdf',
            '/path/to/audio.mp3',
            '/path/to/video.mp4',
            '/path/to/archive.zip',
            '/path/to/executable.exe',
            '/path/to/script.py',
            '/path/to/data.json',
        ]

        for file_path in file_types:
            event = HashableEvent(pygame.DROPFILE, file=file_path)
            manager.on_drop_file_event(event)

        # All events should be handled successfully
        assert len(scene.drop_events_received) == len(file_types)
        for i, file_path in enumerate(file_types):
            assert scene.drop_events_received[i].type == pygame.DROPFILE
            assert scene.drop_events_received[i].file == file_path

    def test_drop_events_with_special_characters(self):
        """Test drop events with special characters in file paths and text."""
        scene, manager = drop_scene_and_manager()

        # Test file paths with special characters
        special_file_paths = [
            '/path/with spaces/file.txt',
            '/path/with-dashes/file.txt',
            '/path/with_underscores/file.txt',
            '/path/with.dots/file.txt',
            '/path/with(parantheses)/file.txt',
            '/path/with[brackets]/file.txt',
            '/path/with{braces}/file.txt',
        ]

        for file_path in special_file_paths:
            event = HashableEvent(pygame.DROPFILE, file=file_path)
            manager.on_drop_file_event(event)

        # Test text with special characters
        special_texts = [
            'Text with spaces',
            'Text-with-dashes',
            'Text_with_underscores',
            'Text.with.dots',
            'Text(with)parantheses',
            'Text[with]brackets',
            'Text{with}braces',
            'Text with\nnewlines',
            'Text with\ttabs',
            'Text with unicode: \u00f1\u00e1\u00e9\u00ed\u00f3\u00fa',
        ]

        for text in special_texts:
            event = HashableEvent(pygame.DROPTEXT, text=text)
            manager.on_drop_text_event(event)

        # All events should be handled successfully
        total_events = len(special_file_paths) + len(special_texts)
        assert len(scene.drop_events_received) == total_events

    @staticmethod
    def _give_stub_strict_options(stub):
        """Give the stubs options that make unhandled events raise."""
        stub.options = dict(EVENT_TEST_OPTIONS)


class TestDropEventManagerCoverage:
    """Test coverage for drop manager functionality."""

    def test_drop_manager_initialization(self):
        """Test DropEventManager initialization."""
        scene, manager = drop_scene_and_manager()

        assert manager.game is scene
        assert hasattr(manager, 'on_drop_begin_event')
        assert hasattr(manager, 'on_drop_file_event')

    def test_drop_manager_initialization_no_game(self):
        """Test DropEventManager initialization without game."""
        manager = DropEventManager(game=None)
        assert manager.game is None

    def test_drop_manager_args(self):
        """Test DropEventManager args method."""
        parser = argparse.ArgumentParser()
        result = DropEventManager.args(parser)

        assert result is parser
        assert any(group.title == 'Drop Options' for group in parser._action_groups)

    def test_drop_proxy_initialization(self):
        """Test drop proxy initialization."""
        scene, manager = drop_scene_and_manager()

        # One proxy, delivering to the scene
        assert len(manager.proxies) == 1
        assert manager.proxies[0].game is scene
        assert manager.proxies[0].proxies == [scene]

    def test_drop_proxy_initialization_no_game(self):
        """Test drop proxy initialization without game."""
        manager = DropEventManager(game=None)

        # Test that proxy is created even without game
        assert hasattr(manager, 'proxies')
        assert len(manager.proxies) > 0

    def test_drop_proxy_on_drop_begin_event(self):
        """Test drop proxy on_drop_begin_event."""
        scene, manager = drop_scene_and_manager()
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPBEGIN)
        proxy.on_drop_begin_event(event)
        assert scene.drop_events_received == [event]

    def test_drop_proxy_on_drop_complete_event(self):
        """Test drop proxy on_drop_complete_event."""
        scene, manager = drop_scene_and_manager()
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPCOMPLETE)
        proxy.on_drop_complete_event(event)
        assert scene.drop_events_received == [event]

    def test_drop_proxy_on_drop_file_event(self):
        """Test drop proxy on_drop_file_event."""
        scene, manager = drop_scene_and_manager()
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPFILE, file='/path/to/file.txt')
        proxy.on_drop_file_event(event)
        assert scene.drop_events_received == [event]

    def test_drop_proxy_on_drop_text_event(self):
        """Test drop proxy on_drop_text_event."""
        scene, manager = drop_scene_and_manager()
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.DROPTEXT, text='dropped text')
        proxy.on_drop_text_event(event)
        assert scene.drop_events_received == [event]


class TestDropEventManagerWithoutVideo:
    """Constructing the manager before pygame's video system is up."""

    def test_unallowed_events_are_logged_and_the_manager_still_works(self, mocker, caplog):
        """set_allowed raises 'video system not initialized' before pygame.display.init()."""
        # The video system is up in every test: simulate set_allowed failing before it is
        mocker.patch(
            'pygame.event.set_allowed',
            side_effect=pygame.error('video system not initialized'),
        )
        game = DropRecordingScene()

        with caplog.at_level('DEBUG', logger='game.events.drop_events'):
            manager = DropEventManager(game=game)

        assert manager.game is game
        assert 'Failed to set allowed drop events: pygame not fully initialized' in caplog.text
