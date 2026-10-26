"""Tests for keyboard event functionality.

This module tests keyboard event interfaces, stubs, event handling,
KeyboardEventProxy forwarding and chord detection, and
KeyboardEventManager initialization.
"""

import argparse

import pygame
import pytest

from glitchygames.events import (
    HashableEvent,
    KeyboardEvents,
    KeyboardEventStubs,
    ResourceManager,
    UnhandledEventError,
)
from glitchygames.events.keyboard import KeyboardEventManager
from glitchygames.scenes import Scene

# Options of a strict game: unhandled events raise UnhandledEventError
STRICT_EVENT_OPTIONS = {'debug_events': False, 'no_unhandled_events': True}


class KeyboardRecordingScene(Scene):
    """A real scene that records the keyboard events it receives.

    Each received event is recorded in keyboard_events_received as (handler tag, event), and a
    chord as (handler tag, event, keys down).
    """

    def __init__(self, options=None, groups=None):
        """Create the scene with strict event options and no keyboard events received yet."""
        super().__init__(
            options=dict(STRICT_EVENT_OPTIONS) if options is None else options, groups=groups
        )
        self.keyboard_events_received = []

    def on_key_down_event(self, event):
        """Record the key down event."""
        self.keyboard_events_received.append(('down', event))

    def on_key_up_event(self, event):
        """Record the key up event."""
        self.keyboard_events_received.append(('up', event))

    def on_key_chord_down_event(self, event, keys):
        """Record the chord down event with the keys down."""
        self.keyboard_events_received.append(('chord_down', event, keys))

    def on_key_chord_up_event(self, event, keys):
        """Record the chord up event with the keys down."""
        self.keyboard_events_received.append(('chord_up', event, keys))

    def received_tags(self):
        """The handler tags of the received events, in order.

        Returns:
            list[str]: The tags.

        """
        return [received[0] for received in self.keyboard_events_received]

    def received_with_tag(self, tag):
        """The recorded entries with one handler tag, in order.

        Returns:
            list[tuple]: The entries.

        """
        return [received for received in self.keyboard_events_received if received[0] == tag]


@pytest.fixture
def keyboard_scene():
    """A real scene that records the keyboard events it receives.

    Returns:
        KeyboardRecordingScene: The scene.

    """
    return KeyboardRecordingScene()


class TestKeyboardEventProxy:
    """Test KeyboardEventProxy event delegation."""

    def test_proxy_init(self, keyboard_scene):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=keyboard_scene)
        assert proxy.game is keyboard_scene
        assert proxy.keys == {}
        assert proxy.proxies == [keyboard_scene, pygame.key]

    def test_on_key_down_event(self, keyboard_scene):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=keyboard_scene)
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a', scancode=30)
        proxy.on_key_down_event(event)
        assert keyboard_scene.received_tags() == ['down', 'chord_down']
        assert keyboard_scene.keyboard_events_received[0] == ('down', event)

    def test_on_key_up_event(self, keyboard_scene):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=keyboard_scene)
        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0, scancode=30)
        proxy.on_key_up_event(event)
        assert keyboard_scene.received_tags() == ['up', 'chord_up']
        assert keyboard_scene.keyboard_events_received[0] == ('up', event)

    def test_on_key_chord_down_event_tracks_keys(self, keyboard_scene):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=keyboard_scene)
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a', scancode=30)
        proxy.on_key_down_event(event)
        # The key's latest event, keyed by its key code
        assert proxy.keys == {pygame.K_a: event}

    def test_on_key_chord_up_event_after_down(self, keyboard_scene):
        proxy = KeyboardEventManager.KeyboardEventProxy(game=keyboard_scene)
        down_event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a', scancode=30)
        proxy.on_key_down_event(down_event)

        up_event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0, scancode=30)
        proxy.on_key_up_event(up_event)
        assert len(keyboard_scene.received_with_tag('chord_up')) == 1


class TestKeyboardEventManager:
    """Test KeyboardEventManager initialization."""

    def test_init(self, keyboard_scene):
        manager = KeyboardEventManager(game=keyboard_scene)
        assert len(manager.proxies) == 1

    def test_args(self):
        parser = argparse.ArgumentParser()
        result = KeyboardEventManager.args(parser)
        assert result is parser


class TestKeyboardEventManagerInitialization:
    """Test KeyboardEventManager initialization paths."""

    def test_successful_initialization(self, keyboard_scene):
        """KeyboardEventManager should initialize successfully with a valid game."""
        manager = KeyboardEventManager(game=keyboard_scene)

        assert manager is not None
        assert len(manager.proxies) == 1
        assert isinstance(manager.proxies[0], KeyboardEventManager.KeyboardEventProxy)

    def test_initialization_allows_keyboard_events(self, keyboard_scene):
        """KeyboardEventManager unblocks the keyboard events at SDL."""
        pygame.event.set_blocked(pygame.KEYDOWN)
        try:
            KeyboardEventManager(game=keyboard_scene)
            assert not pygame.event.get_blocked(pygame.KEYDOWN)
        finally:
            pygame.event.set_allowed(pygame.KEYDOWN)

    def test_initialization_with_pygame_error(self, mocker, keyboard_scene):
        """KeyboardEventManager should handle pygame.error during set_allowed gracefully."""
        # Simulates set_allowed failing before pygame's video system is up
        mocker.patch(
            'glitchygames.events.keyboard.pygame.event.set_allowed',
            side_effect=pygame.error('test error'),
        )

        # Should not raise - the error is caught and logged
        manager = KeyboardEventManager(game=keyboard_scene)
        assert manager is not None

    def test_proxy_has_correct_game_reference(self, keyboard_scene):
        """KeyboardEventProxy should store the game reference."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        assert proxy.game is keyboard_scene

    def test_proxy_initializes_empty_keys_dict(self, keyboard_scene):
        """KeyboardEventProxy should start with an empty keys dictionary."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        assert proxy.keys == {}


class TestKeyboardEventProxyForwarding:
    """Test KeyboardEventProxy forwarding methods."""

    def test_on_key_down_event_forwards_to_game(self, keyboard_scene):
        """on_key_down_event should forward the event to the game."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event)

        assert keyboard_scene.received_with_tag('down') == [('down', event)]

    def test_on_key_down_event_tracks_key_state(self, keyboard_scene):
        """on_key_down_event should record the key in the keys dictionary."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event)

        assert list(proxy.keys.values()) == [event]

    def test_on_key_up_event_forwards_to_game(self, keyboard_scene):
        """on_key_up_event should forward the event to the game."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        proxy.on_key_up_event(event)

        assert keyboard_scene.received_with_tag('up') == [('up', event)]

    def test_on_key_up_event_tracks_key_state(self, keyboard_scene):
        """on_key_up_event should record the key in the keys dictionary."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        proxy.on_key_up_event(event)

        assert list(proxy.keys.values()) == [event]


class TestKeyboardEventProxyChords:
    """Test key chord detection in KeyboardEventProxy."""

    def test_on_key_chord_down_event_called_with_keys_down(self, keyboard_scene):
        """on_key_chord_down_event should be called with the keys currently down."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        # Press first key
        event_ctrl = HashableEvent(
            pygame.KEYDOWN,
            key=pygame.K_LCTRL,
            mod=pygame.KMOD_CTRL,
            unicode='',
        )
        proxy.on_key_down_event(event_ctrl)

        # The chord holds the event and the keys down: just the one key
        assert keyboard_scene.received_with_tag('chord_down') == [
            ('chord_down', event_ctrl, (event_ctrl,)),
        ]

    def test_multiple_keys_down_produces_chord(self, keyboard_scene):
        """Pressing multiple keys should produce chord events with all keys down."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        # Press CTRL
        event_ctrl = HashableEvent(
            pygame.KEYDOWN,
            key=pygame.K_LCTRL,
            mod=pygame.KMOD_CTRL,
            unicode='',
        )
        proxy.on_key_down_event(event_ctrl)

        # Press 'a' while CTRL is held
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=pygame.KMOD_CTRL, unicode='a')
        proxy.on_key_down_event(event_a)

        # Both key presses should trigger chord events
        chords = keyboard_scene.received_with_tag('chord_down')
        assert len(chords) == 2

        # The second chord should have both keys down, in the order they were pressed
        assert chords[1] == ('chord_down', event_a, (event_ctrl, event_a))

    def test_a_released_key_is_not_in_a_later_chord(self, keyboard_scene):
        """Press and release A, then press B: only B is down."""
        proxy = KeyboardEventManager(game=keyboard_scene).proxies[0]
        proxy.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a'))
        proxy.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0))
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_b, mod=0, unicode='b')

        proxy.on_key_down_event(event_b)

        assert keyboard_scene.received_with_tag('chord_down')[-1] == (
            'chord_down',
            event_b,
            (event_b,),
        )

    def test_a_released_key_is_not_down_in_its_own_chord_up(self, keyboard_scene):
        """Releasing the only key held leaves no keys down."""
        proxy = KeyboardEventManager(game=keyboard_scene).proxies[0]
        proxy.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a'))
        event_up = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)

        proxy.on_key_up_event(event_up)

        assert keyboard_scene.received_with_tag('chord_up') == [('chord_up', event_up, ())]

    def test_a_key_pressed_again_is_last_in_the_chord(self, keyboard_scene):
        """Keys down are in the order they were (last) pressed."""
        proxy = KeyboardEventManager(game=keyboard_scene).proxies[0]
        proxy.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a'))
        proxy.on_key_up_event(HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0))
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_b, mod=0, unicode='b')
        proxy.on_key_down_event(event_b)
        event_a_again = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')

        proxy.on_key_down_event(event_a_again)

        assert keyboard_scene.received_with_tag('chord_down')[-1][2] == (event_b, event_a_again)

    def test_on_key_chord_up_event_called_on_key_release(self, keyboard_scene):
        """on_key_chord_up_event should be called when a key is released."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        # Press a key
        event_down = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event_down)

        # Release the key
        event_up = HashableEvent(pygame.KEYUP, key=pygame.K_a, mod=0)
        proxy.on_key_up_event(event_up)

        chords_up = keyboard_scene.received_with_tag('chord_up')
        assert len(chords_up) == 1
        assert chords_up[0][1] is event_up

    def test_chord_up_after_releasing_one_of_two_keys(self, keyboard_scene):
        """Releasing one key of a chord should report remaining keys as still down."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        # Press CTRL
        event_ctrl_down = HashableEvent(
            pygame.KEYDOWN,
            key=pygame.K_LCTRL,
            mod=pygame.KMOD_CTRL,
            unicode='',
        )
        proxy.on_key_down_event(event_ctrl_down)

        # Press 'c'
        event_c_down = HashableEvent(
            pygame.KEYDOWN,
            key=pygame.K_c,
            mod=pygame.KMOD_CTRL,
            unicode='c',
        )
        proxy.on_key_down_event(event_c_down)

        # Release 'c' - CTRL is still down
        event_c_up = HashableEvent(pygame.KEYUP, key=pygame.K_c, mod=pygame.KMOD_CTRL)
        proxy.on_key_up_event(event_c_up)

        # The chord up event should have been called with CTRL still down
        chords_up = keyboard_scene.received_with_tag('chord_up')
        assert len(chords_up) == 1
        assert event_ctrl_down in chords_up[0][2]

    def test_key_down_event_leaves_the_event_unchanged(self, keyboard_scene):
        """on_key_down_event passes the keys down as the chord's argument, not on the event."""
        manager = KeyboardEventManager(game=keyboard_scene)
        proxy = manager.proxies[0]

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')
        proxy.on_key_down_event(event)

        assert not event.has_key('keys_down')


class TestKeyboardEventManagerArgs:
    """Test KeyboardEventManager.args() class method."""

    def test_args_returns_parser(self):
        """args() should return the argument parser."""
        parser = argparse.ArgumentParser()
        result = KeyboardEventManager.args(parser)

        assert result is parser

    def test_args_adds_keyboard_options_group(self):
        """args() should add a 'Keyboard Options' argument group."""
        parser = argparse.ArgumentParser()
        KeyboardEventManager.args(parser)

        group_titles = [group.title for group in parser._action_groups]
        assert 'Keyboard Options' in group_titles


class TestKeyboardEvents:
    """Test KeyboardEvents interface functionality."""

    def test_keyboard_events_interface(self):
        """Test KeyboardEvents interface methods."""
        # Test that KeyboardEvents has required abstract methods
        assert hasattr(KeyboardEvents, 'on_key_down_event')
        assert hasattr(KeyboardEvents, 'on_key_up_event')
        assert hasattr(KeyboardEvents, 'on_key_chord_up_event')
        assert hasattr(KeyboardEvents, 'on_key_chord_down_event')

    def test_keyboard_event_stubs_implementation(self, mocker):
        """Test KeyboardEventStubs implementation."""
        # Test that stubs have concrete implementations
        stub = KeyboardEventStubs()
        assert hasattr(stub, 'on_key_down_event')
        assert hasattr(stub, 'on_key_up_event')
        assert hasattr(stub, 'on_key_chord_up_event')
        assert hasattr(stub, 'on_key_chord_down_event')

        # The stub's options are a strict game's, so unhandled events raise
        stub.options = dict(STRICT_EVENT_OPTIONS)

        # Test method calls
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        # Mock the logger to suppress "Unhandled Event" messages during testing
        mocker.patch('glitchygames.events.base.LOG.error')
        with pytest.raises(UnhandledEventError):
            stub.on_key_down_event(event)
        # Expected to call unhandled_event
        # Exception was raised as expected

    def test_key_down_event(self, keyboard_scene):
        """A key down given to the manager reaches the scene's key down handler."""
        manager = KeyboardEventManager(game=keyboard_scene)

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=' ')
        manager.on_key_down_event(event)

        assert keyboard_scene.received_with_tag('down') == [('down', event)]
        assert keyboard_scene.received_with_tag('down')[0][1].key == pygame.K_SPACE

    def test_key_up_event(self, keyboard_scene):
        """A key up given to the manager reaches the scene's key up handler."""
        manager = KeyboardEventManager(game=keyboard_scene)

        event = HashableEvent(pygame.KEYUP, key=pygame.K_SPACE, mod=0)
        manager.on_key_up_event(event)

        assert keyboard_scene.received_with_tag('up') == [('up', event)]
        assert keyboard_scene.received_with_tag('up')[0][1].key == pygame.K_SPACE

    def test_key_chord_down_event(self, keyboard_scene):
        """Holding Ctrl and pressing C gives the scene a chord down with both keys."""
        manager = KeyboardEventManager(game=keyboard_scene)

        control_down = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode=''
        )
        c_down = HashableEvent(pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL, unicode='c')
        manager.on_key_down_event(control_down)
        manager.on_key_down_event(c_down)

        last_chord = keyboard_scene.received_with_tag('chord_down')[-1]
        assert last_chord[0] == 'chord_down'
        assert last_chord[1].key == pygame.K_c
        assert [key_event.key for key_event in last_chord[2]] == [pygame.K_LCTRL, pygame.K_c]

    def test_key_chord_up_event(self, keyboard_scene):
        """Releasing C while Ctrl is held gives a chord up for C with the keys still down."""
        manager = KeyboardEventManager(game=keyboard_scene)

        control_down = HashableEvent(
            pygame.KEYDOWN, key=pygame.K_LCTRL, mod=pygame.KMOD_CTRL, unicode=''
        )
        c_down = HashableEvent(pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL, unicode='c')
        c_up = HashableEvent(pygame.KEYUP, key=pygame.K_c, mod=pygame.KMOD_CTRL)
        manager.on_key_down_event(control_down)
        manager.on_key_down_event(c_down)
        manager.on_key_up_event(c_up)

        (chord_up,) = keyboard_scene.received_with_tag('chord_up')
        assert chord_up[0] == 'chord_up'
        assert chord_up[1].key == pygame.K_c
        # C is released: the keys still down are Ctrl's (the chord is those plus the event)
        assert [key_event.key for key_event in chord_up[2]] == [pygame.K_LCTRL]

    def test_specific_key_events(self, keyboard_scene):
        """Test specific key event handling."""
        manager = KeyboardEventManager(game=keyboard_scene)

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
            manager.on_key_down_event(HashableEvent(pygame.KEYDOWN, key=key, mod=0, unicode=''))
            manager.on_key_up_event(HashableEvent(pygame.KEYUP, key=key, mod=0))

        # Verify all events were received, in order
        received_downs = keyboard_scene.received_with_tag('down')
        received_ups = keyboard_scene.received_with_tag('up')
        assert [received[1].key for received in received_downs] == test_keys
        assert [received[1].key for received in received_ups] == test_keys

    def test_modifier_key_events(self, keyboard_scene):
        """Test modifier key event handling."""
        manager = KeyboardEventManager(game=keyboard_scene)

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
            manager.on_key_down_event(
                HashableEvent(pygame.KEYDOWN, key=key, mod=pygame.KMOD_NONE, unicode='')
            )
            manager.on_key_up_event(HashableEvent(pygame.KEYUP, key=key, mod=pygame.KMOD_NONE))

        # Verify all events were received (8 keys * 2 events each)
        assert len(keyboard_scene.received_with_tag('down')) == 8
        assert len(keyboard_scene.received_with_tag('up')) == 8

    def test_key_chord_combinations(self, keyboard_scene):
        """Each Ctrl+key combination gives a chord down holding both keys, then a chord up."""
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

        for modifier_key, key in chord_combinations:
            # A fresh manager per combination, so no earlier key stays tracked (constructing
            # the shared manager again would return it as it is: BUGS.md #198)
            ResourceManager.release_shared_instances()
            scene = KeyboardRecordingScene()
            manager = KeyboardEventManager(game=scene)
            manager.on_key_down_event(
                HashableEvent(pygame.KEYDOWN, key=modifier_key, mod=pygame.KMOD_CTRL, unicode='')
            )
            manager.on_key_down_event(
                HashableEvent(pygame.KEYDOWN, key=key, mod=pygame.KMOD_CTRL, unicode='')
            )
            manager.on_key_up_event(HashableEvent(pygame.KEYUP, key=key, mod=pygame.KMOD_CTRL))

            chord_down = scene.received_with_tag('chord_down')[-1]
            (chord_up,) = scene.received_with_tag('chord_up')
            assert [key_event.key for key_event in chord_down[2]] == [modifier_key, key]
            assert chord_up[1].key == key
            assert [key_event.key for key_event in chord_up[2]] == [modifier_key]

    def test_key_with_modifiers(self, keyboard_scene):
        """Test key events with modifier keys."""
        manager = KeyboardEventManager(game=keyboard_scene)

        modifiers = [pygame.KMOD_SHIFT, pygame.KMOD_CTRL, pygame.KMOD_ALT]
        for modifier in modifiers:
            manager.on_key_down_event(
                HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=modifier, unicode='a')
            )

        # Verify all events were received with their modifiers
        received_downs = keyboard_scene.received_with_tag('down')
        assert [received[1].mod for received in received_downs] == modifiers


class TestKeyboardManager:
    """Test KeyboardEventManager in isolation."""

    def test_keyboard_manager_initialization(self, keyboard_scene):
        """Test KeyboardEventManager initializes correctly."""
        manager = KeyboardEventManager(game=keyboard_scene)

        assert manager.game is keyboard_scene
        assert hasattr(manager, 'on_key_down_event')
        assert hasattr(manager, 'on_key_up_event')

    def test_keyboard_manager_events(self, keyboard_scene):
        """Test keyboard event handling through manager."""
        manager = KeyboardEventManager(game=keyboard_scene)

        # Test key down
        down_event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0, unicode=' ')
        manager.on_key_down_event(down_event)

        # Test key up
        up_event = HashableEvent(pygame.KEYUP, key=pygame.K_SPACE, mod=0)
        manager.on_key_up_event(up_event)

        assert keyboard_scene.received_tags() == ['down', 'chord_down', 'up', 'chord_up']
        assert keyboard_scene.received_with_tag('down') == [('down', down_event)]
        assert keyboard_scene.received_with_tag('up') == [('up', up_event)]
