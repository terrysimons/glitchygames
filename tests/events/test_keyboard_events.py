"""Tests for keyboard event functionality.

This module tests keyboard event interfaces, stubs, event handling,
KeyboardEventProxy forwarding and chord detection, and
KeyboardEventManager initialization.
"""

import argparse
import sys
from pathlib import Path

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
from glitchygames.events.keyboard import KeyboardEventManager
from tests.mocks.test_mock_factory import MockFactory


class TestKeyboardEventProxy:
    """Test KeyboardEventProxy event delegation."""

    def test_proxy_init(self, mock_pygame_patches, mocker):
        mock_game = mocker.Mock()
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        assert proxy.game is mock_game
        assert proxy.keys == {}

    def test_on_key_down_event(self, mock_pygame_patches, mocker):
        mock_game = mocker.Mock()
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        # Use a mock event that supports item assignment like HashableEvent does
        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.dict = {
            'type': pygame.KEYDOWN,
            'key': pygame.K_a,
            'mod': 0,
            'unicode': 'a',
            'scancode': 30,
        }
        event.__setitem__ = mocker.Mock()
        proxy.on_key_down_event(event)
        mock_game.on_key_down_event.assert_called_once_with(event)
        mock_game.on_key_chord_down_event.assert_called_once()

    def test_on_key_up_event(self, mock_pygame_patches, mocker):
        mock_game = mocker.Mock()
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        event = mocker.Mock()
        event.type = pygame.KEYUP
        event.dict = {'type': pygame.KEYUP, 'key': pygame.K_a, 'mod': 0, 'scancode': 30}
        proxy.on_key_up_event(event)
        mock_game.on_key_up_event.assert_called_once_with(event)
        mock_game.on_key_chord_up_event.assert_called_once()

    def test_on_key_chord_down_event_tracks_keys(self, mock_pygame_patches, mocker):
        mock_game = mocker.Mock()
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        event = mocker.Mock()
        event.type = pygame.KEYDOWN
        event.dict = {
            'type': pygame.KEYDOWN,
            'key': pygame.K_a,
            'mod': 0,
            'unicode': 'a',
            'scancode': 30,
        }
        event.__setitem__ = mocker.Mock()
        proxy.on_key_down_event(event)
        assert len(proxy.keys) > 0

    def test_on_key_chord_up_event_after_down(self, mock_pygame_patches, mocker):
        mock_game = mocker.Mock()
        proxy = KeyboardEventManager.KeyboardEventProxy(game=mock_game)
        down_event = mocker.Mock()
        down_event.type = pygame.KEYDOWN
        down_event.dict = {
            'type': pygame.KEYDOWN,
            'key': pygame.K_a,
            'mod': 0,
            'unicode': 'a',
            'scancode': 30,
        }
        down_event.__setitem__ = mocker.Mock()
        proxy.on_key_down_event(down_event)

        up_event = mocker.Mock()
        up_event.type = pygame.KEYUP
        up_event.dict = {'type': pygame.KEYUP, 'key': pygame.K_a, 'mod': 0, 'scancode': 30}
        proxy.on_key_up_event(up_event)
        assert mock_game.on_key_chord_up_event.call_count == 1


class TestKeyboardEventManager:
    """Test KeyboardEventManager initialization."""

    def test_init(self, mock_pygame_patches, mocker):
        mock_game = mocker.Mock()
        manager = KeyboardEventManager(game=mock_game)
        assert len(manager.proxies) == 1

    def test_args(self, mock_pygame_patches):
        parser = argparse.ArgumentParser()
        result = KeyboardEventManager.args(parser)
        assert result is parser


class TestKeyboardEventManagerInitialization:
    """Test KeyboardEventManager initialization paths."""

    def test_successful_initialization(self, mock_pygame_patches, mocker):
        """KeyboardEventManager should initialize successfully with a valid game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)

        assert manager is not None
        assert len(manager.proxies) == 1
        assert isinstance(manager.proxies[0], KeyboardEventManager.KeyboardEventProxy)

    def test_initialization_with_pygame_error(self, mock_pygame_patches, mocker):
        """KeyboardEventManager should handle pygame.error during set_allowed gracefully."""
        mocker.patch(
            'glitchygames.events.keyboard.pygame.event.set_allowed',
            side_effect=pygame.error('test error'),
        )
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        # Should not raise - the error is caught and logged
        manager = KeyboardEventManager(game=scene)
        assert manager is not None

    def test_proxy_has_correct_game_reference(self, mock_pygame_patches, mocker):
        """KeyboardEventProxy should store the game reference."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        assert proxy.game is scene

    def test_proxy_initializes_empty_keys_dict(self, mock_pygame_patches, mocker):
        """KeyboardEventProxy should start with an empty keys dictionary."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        assert proxy.keys == {}


class TestKeyboardEventProxyForwarding:
    """Test KeyboardEventProxy forwarding methods."""

    def test_on_key_down_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """on_key_down_event should forward the event to the game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event)

        scene.on_key_down_event.assert_called_once_with(event)

    def test_on_key_down_event_tracks_key_state(self, mock_pygame_patches, mocker):
        """on_key_down_event should record the key in the keys dictionary."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event)

        # The keys dict should have at least one entry after a key down
        assert len(proxy.keys) >= 1

    def test_on_key_up_event_forwards_to_game(self, mock_pygame_patches, mocker):
        """on_key_up_event should forward the event to the game."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        proxy.on_key_up_event(event)

        scene.on_key_up_event.assert_called_once_with(event)

    def test_on_key_up_event_tracks_key_state(self, mock_pygame_patches, mocker):
        """on_key_up_event should record the key in the keys dictionary."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        proxy.on_key_up_event(event)

        # The keys dict should have at least one entry after a key up
        assert len(proxy.keys) >= 1


class TestKeyboardEventProxyChords:
    """Test key chord detection in KeyboardEventProxy."""

    def test_on_key_chord_down_event_called_with_keys_down(self, mock_pygame_patches, mocker):
        """on_key_chord_down_event should be called with the keys currently down."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        # Press first key
        event_ctrl = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode='',
        )
        proxy.on_key_down_event(event_ctrl)

        # Verify chord was called with the first key down
        assert scene.on_key_chord_down_event.call_count == 1
        chord_call_args = scene.on_key_chord_down_event.call_args
        # First positional arg is the event, second is the keys_down tuple
        assert chord_call_args[0][0] is event_ctrl

    def test_multiple_keys_down_produces_chord(self, mock_pygame_patches, mocker):
        """Pressing multiple keys should produce chord events with all keys down."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        # Press CTRL
        event_ctrl = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode='',
        )
        proxy.on_key_down_event(event_ctrl)

        # Press 'a' while CTRL is held
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL, unicode='a')
        proxy.on_key_down_event(event_a)

        # Both key presses should trigger chord events
        assert scene.on_key_chord_down_event.call_count == 2

        # The second chord call should have both keys down
        second_chord_call = scene.on_key_chord_down_event.call_args_list[1]
        keys_down = second_chord_call[0][1]
        # Both keys should be in the keys_down tuple (both are KEYDOWN type)
        assert len(keys_down) == 2

    def test_on_key_chord_up_event_called_on_key_release(self, mock_pygame_patches, mocker):
        """on_key_chord_up_event should be called when a key is released."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        # Press a key
        event_down = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event_down)

        # Release the key
        event_up = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        proxy.on_key_up_event(event_up)

        scene.on_key_chord_up_event.assert_called_once()
        chord_call_args = scene.on_key_chord_up_event.call_args
        assert chord_call_args[0][0] is event_up

    def test_chord_up_after_releasing_one_of_two_keys(self, mock_pygame_patches, mocker):
        """Releasing one key of a chord should report remaining keys as still down."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_up_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()
        scene.on_key_chord_up_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        # Press CTRL
        event_ctrl_down = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode='',
        )
        proxy.on_key_down_event(event_ctrl_down)

        # Press 'c'
        event_c_down = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL, unicode='c',
        )
        proxy.on_key_down_event(event_c_down)

        # Release 'c' - CTRL is still down
        event_c_up = HashableEvent(pygame.KEYUP, key=pygame.K_c, mod=pygame.KMOD_CTRL)
        proxy.on_key_up_event(event_c_up)

        # The chord up event should have been called
        assert scene.on_key_chord_up_event.call_count == 1

    def test_key_down_event_adds_keys_down_to_event(self, mock_pygame_patches, mocker):
        """on_key_down_event should add keys_down attribute to the event for chord detection."""
        scene = MockFactory.create_event_test_scene_mock()
        scene.on_key_down_event = mocker.Mock()
        scene.on_key_chord_down_event = mocker.Mock()

        manager = KeyboardEventManager(game=scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event)

        # The event should have had 'keys_down' added to it during chord processing
        assert event.has_key('keys_down')


class TestKeyboardEventManagerArgs:
    """Test KeyboardEventManager.args() class method."""

    def test_args_returns_parser(self, mock_pygame_patches):
        """args() should return the argument parser."""
        parser = argparse.ArgumentParser()
        result = KeyboardEventManager.args(parser)

        assert result is parser

    def test_args_adds_keyboard_options_group(self, mock_pygame_patches):
        """args() should add a 'Keyboard Options' argument group."""
        parser = argparse.ArgumentParser()
        KeyboardEventManager.args(parser)

        group_titles = [group.title for group in parser._action_groups]
        assert 'Keyboard Options' in group_titles


class TestKeyboardEvents:
    """Test KeyboardEvents interface functionality."""

    def test_keyboard_events_interface(self, mock_pygame_patches):
        """Test KeyboardEvents interface methods."""
        # Test that KeyboardEvents has required abstract methods
        assert hasattr(KeyboardEvents, 'on_key_down_event')
        assert hasattr(KeyboardEvents, 'on_key_up_event')
        assert hasattr(KeyboardEvents, 'on_key_chord_up_event')
        assert hasattr(KeyboardEvents, 'on_key_chord_down_event')

    def test_keyboard_event_stubs_implementation(self, mock_pygame_patches, mocker):
        """Test KeyboardEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = KeyboardEventStubs()
        assert hasattr(stub, 'on_key_down_event')
        assert hasattr(stub, 'on_key_up_event')
        assert hasattr(stub, 'on_key_chord_up_event')
        assert hasattr(stub, 'on_key_chord_down_event')

        # Test that stub methods can be called with proper scene object
        self._setup_mock_scene_for_stub(stub)

        # Test method calls
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.core.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_key_down_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_key_down_event(self, mock_pygame_patches):
        """Test key down event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_key_down_event': lambda event: (
                    scene.keyboard_events_received.append(event) or True
                ),
            },
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
                'on_key_up_event': lambda event: (
                    scene.keyboard_events_received.append(event) or True
                ),
            },
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
                'on_key_chord_down_event': lambda event, keys: (
                    scene.keyboard_events_received.append(('chord_down', event, keys)),
                    True,
                )[1],
            },
        )

        # Test key chord down
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_c)
        keys = (pygame.K_LCTRL, pygame.K_c)
        result = scene.on_key_chord_down_event(event, keys)

        # Event should be handled successfully
        assert result is True
        assert len(scene.keyboard_events_received) == 1
        assert scene.keyboard_events_received[0][0] == 'chord_down'
        assert scene.keyboard_events_received[0][1].key == pygame.K_c
        assert scene.keyboard_events_received[0][2] == keys

    def test_key_chord_up_event(self, mock_pygame_patches):
        """Test key chord up event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_key_chord_up_event': lambda event, keys: (
                    scene.keyboard_events_received.append(('chord_up', event, keys)),
                    True,
                )[1],
            },
        )

        # Test key chord up
        event = HashableEvent(pygame.KEYUP, key=pygame.K_c)
        keys = (pygame.K_LCTRL, pygame.K_c)
        result = scene.on_key_chord_up_event(event, keys)

        # Event should be handled successfully
        assert result is True
        assert len(scene.keyboard_events_received) == 1
        assert scene.keyboard_events_received[0][0] == 'chord_up'
        assert scene.keyboard_events_received[0][1].key == pygame.K_c
        assert scene.keyboard_events_received[0][2] == keys

    def test_specific_key_events(self, mock_pygame_patches):
        """Test specific key event handling."""
        # Use centralized mock for scene with proper event handling
        scene = MockFactory.create_event_test_scene_mock(
            event_handlers={
                'on_key_down_event': lambda event: (
                    scene.keyboard_events_received.append(('down', event)) or True
                ),
                'on_key_up_event': lambda event: (
                    scene.keyboard_events_received.append(('up', event)) or True
                ),
            },
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
                'on_key_down_event': lambda event: (
                    scene.keyboard_events_received.append(('down', event)),
                    True,
                )[1],
                'on_key_up_event': lambda event: (
                    scene.keyboard_events_received.append(('up', event)),
                    True,
                )[1],
            },
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
                'on_key_chord_down_event': lambda event, keys: (
                    scene.keyboard_events_received.append(('chord_down', event, keys)),
                    True,
                )[1],
                'on_key_chord_up_event': lambda event, keys: (
                    scene.keyboard_events_received.append(('chord_up', event, keys)),
                    True,
                )[1],
            },
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
                'on_key_down_event': lambda event: (
                    scene.keyboard_events_received.append(('down', event)),
                    True,
                )[1],
            },
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
        """Set up mock scene object for event stubs using centralized mocks.

        Returns:
            object: The result.

        """
        # Create a scene mock with proper event handling configuration
        scene_mock = MockFactory.create_event_test_scene_mock(
            options={
                'debug_events': False,
                'no_unhandled_events': True,  # This will cause UnhandledEventError to be raised
            },
        )
        # Set the options on the stub so unhandled_event can access them
        stub.options = scene_mock.options
        return scene_mock


class TestKeyboardManager:
    """Test KeyboardEventManager in isolation."""

    def test_keyboard_manager_initialization(self, mock_pygame_patches, mocker):
        """Test KeyboardEventManager initializes correctly."""
        mock_game = mocker.Mock()
        manager = KeyboardEventManager(game=mock_game)

        assert manager.game == mock_game
        assert hasattr(manager, 'on_key_down_event')
        assert hasattr(manager, 'on_key_up_event')

    def test_keyboard_manager_events(self, mock_pygame_patches, mocker):
        """Test keyboard event handling through manager."""
        mock_game = mocker.Mock()
        manager = KeyboardEventManager(game=mock_game)

        # Test key down
        down_event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=' ')
        manager.on_key_down_event(down_event)

        # Test key up
        up_event = HashableEvent(pygame.KEYUP, key=pygame.K_SPACE, mod=0)
        manager.on_key_up_event(up_event)
