"""Coverage tests for keyboard event handling in glitchygames/events/keyboard.py.

This module tests KeyboardEventManager initialization, KeyboardEventProxy
forwarding methods, and key chord detection.
"""

import sys
from pathlib import Path

import pygame

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent
from glitchygames.events.keyboard import KeyboardEventManager
from tests.mocks.test_mock_factory import MockFactory


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
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode=''
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
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode=''
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
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode=''
        )
        proxy.on_key_down_event(event_ctrl_down)

        # Press 'c'
        event_c_down = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL, unicode='c'
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
        import argparse

        parser = argparse.ArgumentParser()
        result = KeyboardEventManager.args(parser)

        assert result is parser

    def test_args_adds_keyboard_options_group(self, mock_pygame_patches):
        """args() should add a 'Keyboard Options' argument group."""
        import argparse

        parser = argparse.ArgumentParser()
        KeyboardEventManager.args(parser)

        group_titles = [group.title for group in parser._action_groups]
        assert 'Keyboard Options' in group_titles
