"""Tests for keyboard event functionality.

This module tests keyboard event interfaces, stubs, and event handling.
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
    KeyboardEvents,
    KeyboardEventStubs,
    UnhandledEventError,
)

from tests.mocks.test_mock_factory import MockFactory


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

        # Test that stub methods can be called with proper scene object
        self._setup_mock_scene_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        with patch("glitchygames.events.LOG.error"):
            with pytest.raises(UnhandledEventError):
                stub.on_key_down_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_key_down_event(self, mock_pygame_patches):
        """Test key down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_down_event": lambda event: scene.keyboard_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        result = scene.on_key_down_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.keyboard_events_received) == 1
        assert scene.keyboard_events_received[0].key == pygame.K_SPACE

    def test_key_up_event(self, mock_pygame_patches):
        """Test key up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_up_event": lambda event: scene.keyboard_events_received.append(event) or True
            }
        )
        
        # Test that the scene can handle the event
        event = HashableEvent(pygame.KEYUP, key=pygame.K_SPACE)
        result = scene.on_key_up_event(event)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.keyboard_events_received) == 1
        assert scene.keyboard_events_received[0].key == pygame.K_SPACE

    def test_key_chord_down_event(self, mock_pygame_patches):
        """Test key chord down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_chord_down_event": lambda event, keys: (scene.keyboard_events_received.append(("chord_down", event, keys)), True)[1]
            }
        )

        # Test key chord down
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_c)
        keys = (pygame.K_LCTRL, pygame.K_c)
        result = scene.on_key_chord_down_event(event, keys)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.keyboard_events_received) == 1
        assert scene.keyboard_events_received[0][0] == "chord_down"
        assert scene.keyboard_events_received[0][1].key == pygame.K_c
        assert scene.keyboard_events_received[0][2] == keys

    def test_key_chord_up_event(self, mock_pygame_patches):
        """Test key chord up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_chord_up_event": lambda event, keys: (scene.keyboard_events_received.append(("chord_up", event, keys)), True)[1]
            }
        )

        # Test key chord up
        event = HashableEvent(pygame.KEYUP, key=pygame.K_c)
        keys = (pygame.K_LCTRL, pygame.K_c)
        result = scene.on_key_chord_up_event(event, keys)
        
        # Event should be handled successfully
        assert result is True
        assert len(scene.keyboard_events_received) == 1
        assert scene.keyboard_events_received[0][0] == "chord_up"
        assert scene.keyboard_events_received[0][1].key == pygame.K_c
        assert scene.keyboard_events_received[0][2] == keys

    def test_specific_key_events(self, mock_pygame_patches):
        """Test specific key event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_down_event": lambda event: scene.keyboard_events_received.append(("down", event)) or True,
                "on_key_up_event": lambda event: scene.keyboard_events_received.append(("up", event)) or True
            }
        )

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
            result = scene.on_key_down_event(event)
            assert result is True

            # Test key up
            event = HashableEvent(pygame.KEYUP, key=key)
            result = scene.on_key_up_event(event)
            assert result is True
        
        # Verify all events were received
        assert len(scene.keyboard_events_received) == 20  # 10 keys * 2 events each

    def test_modifier_key_events(self, mock_pygame_patches):
        """Test modifier key event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_down_event": lambda event: (scene.keyboard_events_received.append(("down", event)), True)[1],
                "on_key_up_event": lambda event: (scene.keyboard_events_received.append(("up", event)), True)[1]
            }
        )

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
            result = scene.on_key_down_event(event)
            assert result is True

            # Test key up
            event = HashableEvent(pygame.KEYUP, key=key, mod=pygame.KMOD_NONE)
            result = scene.on_key_up_event(event)
            assert result is True

        # Verify all events were received
        assert len(scene.keyboard_events_received) == 16  # 8 keys * 2 events each

    def test_key_chord_combinations(self, mock_pygame_patches):
        """Test key chord combination handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_chord_down_event": lambda event, keys: (scene.keyboard_events_received.append(("chord_down", event, keys)), True)[1],
                "on_key_chord_up_event": lambda event, keys: (scene.keyboard_events_received.append(("chord_up", event, keys)), True)[1]
            }
        )

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
            result = scene.on_key_chord_down_event(event, keys)
            assert result is True

            # Test chord up
            event = HashableEvent(pygame.KEYUP, key=keys[1])
            result = scene.on_key_chord_up_event(event, keys)
            assert result is True

        # Verify all events were received
        assert len(scene.keyboard_events_received) == 14  # 7 combinations * 2 events each

    def test_key_with_modifiers(self, mock_pygame_patches):
        """Test key events with modifier keys."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                "on_key_down_event": lambda event: (scene.keyboard_events_received.append(("down", event)), True)[1]
            }
        )

        # Test key with shift modifier
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_SHIFT)
        result = scene.on_key_down_event(event)
        assert result is True

        # Test key with ctrl modifier
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL)
        result = scene.on_key_down_event(event)
        assert result is True

        # Test key with alt modifier
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_ALT)
        result = scene.on_key_down_event(event)
        assert result is True

        # Verify all events were received
        assert len(scene.keyboard_events_received) == 3

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


class TestKeyboardManager:
    """Test KeyboardManager in isolation."""

    def test_keyboard_manager_initialization(self, mock_pygame_patches):
        """Test KeyboardManager initializes correctly."""
        from glitchygames.events.keyboard import KeyboardManager
        
        mock_game = Mock()
        manager = KeyboardManager(game=mock_game)
        
        assert manager.game == mock_game
        assert hasattr(manager, "on_key_down_event")
        assert hasattr(manager, "on_key_up_event")

    def test_keyboard_manager_events(self, mock_pygame_patches):
        """Test keyboard event handling through manager."""
        from glitchygames.events.keyboard import KeyboardManager
        
        mock_game = Mock()
        manager = KeyboardManager(game=mock_game)
        
        # Test key down
        down_event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=" ")
        manager.on_key_down_event(down_event)
        
        # Test key up
        up_event = HashableEvent(pygame.KEYUP, key=pygame.K_SPACE, mod=0)
        manager.on_key_up_event(up_event)
