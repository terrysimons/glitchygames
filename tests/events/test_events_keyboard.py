"""Tests for keyboard event functionality.

This module tests keyboard event interfaces, stubs, and event handling.
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
    KeyboardEvents,
    KeyboardEventStubs,
)


class TestKeyboardEvents:
    """Test KeyboardEvents interface functionality."""

    def test_keyboard_events_interface(self, mock_pygame_patches):
        """Test KeyboardEvents interface methods."""
        # Test that KeyboardEvents has required abstract methods
        assert hasattr(KeyboardEvents, "on_key_down_event")
        assert hasattr(KeyboardEvents, "on_key_up_event")
        assert hasattr(KeyboardEvents, "on_key_chord_up_event")
        assert hasattr(KeyboardEvents, "on_key_chord_down_event")

    def test_keyboard_event_stubs_implementation(self, mock_pygame_patches):
        """Test KeyboardEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = KeyboardEventStubs()
        assert hasattr(stub, "on_key_down_event")
        assert hasattr(stub, "on_key_up_event")
        assert hasattr(stub, "on_key_chord_up_event")
        assert hasattr(stub, "on_key_chord_down_event")

        # Test that stub methods can be called with proper game object
        self._setup_mock_game_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_down_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_key_down_event(self, mock_pygame_patches):
        """Test key down event handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test space key down
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_down_event(event)
        # Exception was raised as expected

    def test_key_up_event(self, mock_pygame_patches):
        """Test key up event handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test space key up
        event = HashableEvent(pygame.KEYUP, key=pygame.K_SPACE)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_up_event(event)
        # Exception was raised as expected

    def test_key_chord_down_event(self, mock_pygame_patches):
        """Test key chord down event handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test key chord down
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_c)
        keys = (pygame.K_LCTRL, pygame.K_c)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_chord_down_event(event, keys)
        # Exception was raised as expected

    def test_key_chord_up_event(self, mock_pygame_patches):
        """Test key chord up event handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test key chord up
        event = HashableEvent(pygame.KEYUP, key=pygame.K_c)
        keys = (pygame.K_LCTRL, pygame.K_c)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_chord_up_event(event, keys)
        # Exception was raised as expected

    def test_specific_key_events(self, mock_pygame_patches):
        """Test specific key event handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test various keys
        test_keys = [
            pygame.K_SPACE,
            pygame.K_RETURN,
            pygame.K_ESCAPE,
            pygame.K_UP,
            pygame.K_DOWN,
            pygame.K_LEFT,
            pygame.K_RIGHT,
            pygame.K_a,
            pygame.K_b,
            pygame.K_c,
        ]

        for key in test_keys:
            # Test key down
            event = HashableEvent(pygame.KEYDOWN, key=key)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_key_down_event(event)
            # Exception was raised as expected

            # Test key up
            event = HashableEvent(pygame.KEYUP, key=key)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_key_up_event(event)
            # Exception was raised as expected

    def test_modifier_key_events(self, mock_pygame_patches):
        """Test modifier key event handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test modifier keys
        modifier_keys = [
            pygame.K_LSHIFT,
            pygame.K_RSHIFT,
            pygame.K_LCTRL,
            pygame.K_RCTRL,
            pygame.K_LALT,
            pygame.K_RALT,
            pygame.K_LMETA,
            pygame.K_RMETA,
        ]

        for key in modifier_keys:
            # Test key down
            event = HashableEvent(pygame.KEYDOWN, key=key, mod=pygame.KMOD_NONE)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_key_down_event(event)
            # Exception was raised as expected

            # Test key up
            event = HashableEvent(pygame.KEYUP, key=key, mod=pygame.KMOD_NONE)
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_key_up_event(event)
            # Exception was raised as expected

    def test_key_chord_combinations(self, mock_pygame_patches):
        """Test key chord combination handling."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test common key chord combinations
        chord_combinations = [
            (pygame.K_LCTRL, pygame.K_c),  # Ctrl+C
            (pygame.K_LCTRL, pygame.K_v),  # Ctrl+V
            (pygame.K_LCTRL, pygame.K_x),  # Ctrl+X
            (pygame.K_LCTRL, pygame.K_z),  # Ctrl+Z
            (pygame.K_LCTRL, pygame.K_s),  # Ctrl+S
            (pygame.K_LCTRL, pygame.K_o),  # Ctrl+O
            (pygame.K_LCTRL, pygame.K_n),  # Ctrl+N
        ]

        for keys in chord_combinations:
            # Test chord down
            event = HashableEvent(pygame.KEYDOWN, key=keys[1])
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_key_chord_down_event(event, keys)
            # Exception was raised as expected

            # Test chord up
            event = HashableEvent(pygame.KEYUP, key=keys[1])
            with pytest.raises((Exception, SystemExit)) as exc_info:
                stub.on_key_chord_up_event(event, keys)
            # Exception was raised as expected

    def test_key_with_modifiers(self, mock_pygame_patches):
        """Test key events with modifier keys."""
        stub = KeyboardEventStubs()
        self._setup_mock_game_for_stub(stub)

        # Test key with shift modifier
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_SHIFT)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_down_event(event)
        # Exception was raised as expected

        # Test key with ctrl modifier
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_down_event(event)
        # Exception was raised as expected

        # Test key with alt modifier
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_ALT)
        with pytest.raises((Exception, SystemExit)) as exc_info:
            stub.on_key_down_event(event)
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
