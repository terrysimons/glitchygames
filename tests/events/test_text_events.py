"""Tests for text event functionality.

This module tests text event interfaces, stubs, and event handling.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (
    HashableEvent,
    TextEvents,
    TextEventStubs,
    UnhandledEventError,
)
from glitchygames.scenes import Scene

# Options of a strict game: unhandled events raise UnhandledEventError
STRICT_EVENT_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class TestTextEvents:
    """Test TextEvents interface functionality."""

    def test_text_events_interface(self):
        """Test TextEvents interface methods."""
        # Test that TextEvents has required abstract methods
        assert hasattr(TextEvents, 'on_text_input_event')
        assert hasattr(TextEvents, 'on_text_editing_event')

    def test_text_event_stubs_implementation(self, mocker):
        """Test TextEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = TextEventStubs()
        assert hasattr(stub, 'on_text_input_event')
        assert hasattr(stub, 'on_text_editing_event')

        # Test that stub methods can be called with proper game object
        self._configure_stub_options(stub)

        # Test method calls
        event = HashableEvent(pygame.TEXTINPUT, text='test')
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_text_input_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_input_event(self, mocker):
        """Test text input event handling."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test text input
        event = HashableEvent(pygame.TEXTINPUT, text='Hello World')
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_text_input_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_editing_event(self, mocker):
        """Test text editing event handling."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test text editing
        event = HashableEvent(pygame.TEXTEDITING, text='Hello', start=0, length=5)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_text_editing_event(event)
        # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_input_with_different_characters(self, mocker):
        """Test text input with different character types."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test different character types
        test_texts = [
            'Hello World',  # Basic text
            '123456789',  # Numbers
            '!@#$%^&*()',  # Special characters
            'Hello\nWorld',  # Text with newlines
            'Hello\tWorld',  # Text with tabs
            'Hello World!',  # Mixed characters
            'Café',  # Text with accents
            '你好',  # Unicode text
            'αβγδε',  # Greek letters
            '🚀🎮🎯',  # Emojis
        ]

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        for text in test_texts:
            event = HashableEvent(pygame.TEXTINPUT, text=text)
            with pytest.raises(UnhandledEventError):
                stub.on_text_input_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_editing_with_different_parameters(self, mocker):
        """Test text editing with different parameters."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test different editing scenarios
        editing_scenarios = [
            ('Hello', 0, 5),  # Full text selection
            ('Hello', 2, 3),  # Partial text selection
            ('Hello', 0, 0),  # No selection (cursor position)
            ('Hello', 5, 0),  # Cursor at end
            ('', 0, 0),  # Empty text
            ('Test', 1, 2),  # Middle selection
        ]

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        for text, start, length in editing_scenarios:
            event = HashableEvent(pygame.TEXTEDITING, text=text, start=start, length=length)
            with pytest.raises(UnhandledEventError):
                stub.on_text_editing_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_input_with_single_characters(self, mocker):
        """Test text input with single character events."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test single character inputs
        single_chars = [
            'a',
            'b',
            'c',
            'd',
            'e',
            'f',
            'g',
            'h',
            'i',
            'j',
            'A',
            'B',
            'C',
            'D',
            'E',
            'F',
            'G',
            'H',
            'I',
            'J',
            '1',
            '2',
            '3',
            '4',
            '5',
            '6',
            '7',
            '8',
            '9',
            '0',
            '!',
            '@',
            '#',
            '$',
            '%',
            '^',
            '&',
            '*',
            '(',
            ')',
            ' ',
            '\t',
            '\n',
            '\r',
        ]

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        for char in single_chars:
            event = HashableEvent(pygame.TEXTINPUT, text=char)
            with pytest.raises(UnhandledEventError):
                stub.on_text_input_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_editing_with_cursor_movements(self, mocker):
        """Test text editing with cursor movement scenarios."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test cursor movement scenarios
        cursor_scenarios = [
            ('Hello', 0, 0),  # Cursor at beginning
            ('Hello', 1, 0),  # Cursor after first character
            ('Hello', 2, 0),  # Cursor in middle
            ('Hello', 3, 0),  # Cursor near end
            ('Hello', 4, 0),  # Cursor at end
            ('Hello', 5, 0),  # Cursor beyond end
        ]

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        for text, start, length in cursor_scenarios:
            event = HashableEvent(pygame.TEXTEDITING, text=text, start=start, length=length)
            with pytest.raises(UnhandledEventError):
                stub.on_text_editing_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_input_with_unicode_characters(self, mocker):
        """Test text input with Unicode characters."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test Unicode characters
        unicode_texts = [
            'Café',  # Latin with accents
            'naïve',  # Latin with diaeresis
            'résumé',  # Latin with accents
            '你好',  # Chinese characters
            'こんにちは',  # Japanese characters
            '안녕하세요',  # Korean characters
            'Привет',  # Cyrillic characters
            'αβγδε',  # Greek letters
            '🚀🎮🎯',  # Emojis
            '∞≠≤≥',  # Mathematical symbols
        ]

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        for text in unicode_texts:
            event = HashableEvent(pygame.TEXTINPUT, text=text)
            with pytest.raises(UnhandledEventError):
                stub.on_text_input_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def test_text_editing_with_selection_scenarios(self, mocker):
        """Test text editing with different selection scenarios."""
        stub = TextEventStubs()
        self._configure_stub_options(stub)

        # Test selection scenarios
        selection_scenarios = [
            ('Hello', 0, 5),  # Select all
            ('Hello', 0, 1),  # Select first character
            ('Hello', 1, 3),  # Select middle characters
            ('Hello', 4, 1),  # Select last character
            ('Hello', 0, 0),  # No selection
            ('Hello', 2, 0),  # Cursor position, no selection
        ]

        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        for text, start, length in selection_scenarios:
            event = HashableEvent(pygame.TEXTEDITING, text=text, start=start, length=length)
            with pytest.raises(UnhandledEventError):
                stub.on_text_editing_event(event)
            # Expected to call unhandled_event and raise UnhandledEventError

    def _configure_stub_options(self, stub):
        """Give the stub the options a strict game has, so unhandled events raise."""
        # no_unhandled_events makes unhandled_event raise UnhandledEventError
        stub.options = dict(STRICT_EVENT_OPTIONS)


class TextRecordingScene(Scene):
    """A real scene that records the text events it receives."""

    def __init__(self, options=None, groups=None):
        """Create the scene with strict event options and no text events received yet."""
        super().__init__(
            options=dict(STRICT_EVENT_OPTIONS) if options is None else options, groups=groups
        )
        self.text_events_received = []

    def on_text_editing_event(self, event):
        """Record the text editing event."""
        self.text_events_received.append(('text_editing', event))

    def on_text_input_event(self, event):
        """Record the text input event."""
        self.text_events_received.append(('text_input', event))


class TextStubGame(TextEventStubs):
    """A game whose text handlers are the stubs, with strict event options."""

    def __init__(self):
        """Create the game with strict event options."""
        self.options = dict(STRICT_EVENT_OPTIONS)


class TestTextEventsKeyboardManager:
    """Test text events handled by KeyboardEventManager."""

    def test_text_events_through_keyboard_manager(self):
        """Text events given to the KeyboardEventManager reach the scene's text handlers."""
        from glitchygames.events.keyboard import KeyboardEventManager

        scene = TextRecordingScene()
        manager = KeyboardEventManager(game=scene)

        assert manager.game is scene
        editing_event = HashableEvent(pygame.TEXTEDITING, text='test', start=0, length=4)
        input_event = HashableEvent(pygame.TEXTINPUT, text='test')
        manager.on_text_editing_event(editing_event)
        manager.on_text_input_event(input_event)

        assert scene.text_events_received == [
            ('text_editing', editing_event),
            ('text_input', input_event),
        ]

    def test_text_events(self, mocker):
        """Text events reach a game without text handlers' stubs, which raise."""
        from glitchygames.events.keyboard import KeyboardEventManager

        manager = KeyboardEventManager(game=TextStubGame())

        # Test text editing - suppress log messages since this will trigger unhandled_event
        editing_event = HashableEvent(pygame.TEXTEDITING, text='test', start=0, length=4)
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            manager.on_text_editing_event(editing_event)

        # Test text input - suppress log messages since this will trigger unhandled_event
        input_event = HashableEvent(pygame.TEXTINPUT, text='test')
        with pytest.raises(UnhandledEventError):
            manager.on_text_input_event(input_event)
