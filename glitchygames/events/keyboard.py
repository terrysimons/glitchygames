#!/usr/bin/env python3
"""Keyboard Event Manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import (
    KEYBOARD_EVENTS,
    HashableEvent,
    KeyboardEvents,
    KeyEvent,
    ResourceManager,
)

log = logging.getLogger('game.keyboard')
log.addHandler(logging.NullHandler())


class KeyboardEventManager(ResourceManager):
    """Manage keyboard events."""

    class KeyboardEventProxy(KeyboardEvents, ResourceManager):
        """Keyboard event proxy."""

        # A proxy belongs to its manager: each construction is a new one (ResourceManager)
        SHARES_INSTANCE: ClassVar[bool] = False

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the keyboard event proxy.

            Args:
                game (object): The game object.

            """
            super().__init__(game=game)
            # Each key's latest event, by key code, in the order the keys were last pressed: a
            # key is down while its latest event is its KEYDOWN
            self.keys: dict[int, HashableEvent] = {}
            self.game: Any = game
            self.proxies = [self.game, pygame.key]

        @override
        def on_key_down_event(self: Self, event: KeyEvent) -> None:
            """Handle key down events.

            Args:
                event (KeyEvent): The event to handle.

            """
            # Re-inserted, so a key pressed again is the last key down (BUGS.md #180: keyed by
            # the whole event, a KEYUP never replaced its KEYDOWN, so released keys stayed down)
            self.keys.pop(event.key, None)
            self.keys[event.key] = event

            self.game.on_key_down_event(event)
            self.on_key_chord_down_event(event)

        @override
        def on_key_up_event(self: Self, event: KeyEvent) -> None:
            """Handle key up events.

            Args:
                event (KeyEvent): The event to handle.

            """
            self.keys[event.key] = event

            self.game.on_key_up_event(event)
            self.on_key_chord_up_event(event)

        @override
        def on_key_chord_down_event(
            self: Self,
            event: KeyEvent,
            keys: tuple[KeyEvent, ...] = (),
        ) -> None:
            """Handle key chord down events.

            Args:
                event (KeyEvent): The event to handle.
                keys (tuple[KeyEvent, ...]): Unused: the proxy passes the game the KEYDOWN
                    events of the keys held now, in the order they were pressed.

            """
            keys_down = self._keys_down()

            # The keys down are the chord's argument; the event itself is left unchanged
            self.game.on_key_chord_down_event(event, keys_down)

        @override
        def on_key_chord_up_event(
            self: Self,
            event: KeyEvent,
            keys: tuple[KeyEvent, ...] = (),
        ) -> None:
            """Handle key chord up events.

            Args:
                event (KeyEvent): The event to handle.
                keys (tuple[KeyEvent, ...]): Unused: the proxy passes the game the KEYDOWN
                    events of the keys held now, in the order they were pressed.

            """
            self.game.on_key_chord_up_event(event, self._keys_down())

        def _keys_down(self: Self) -> tuple[HashableEvent, ...]:
            """Return the KEYDOWN events of the keys held now, in the order they were pressed.

            Returns:
                tuple[HashableEvent, ...]: The keys down.

            """
            return tuple(
                key_event for key_event in self.keys.values() if key_event.type == pygame.KEYDOWN
            )

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the keyboard event manager.

        Args:
            game (object): The game object.

        """
        super().__init__(game=game)
        # Enable keyboard events for this manager
        try:
            pygame.event.set_allowed(KEYBOARD_EVENTS)
        except pygame.error:
            log.debug('Failed to set allowed keyboard events: pygame not fully initialized')
        self.proxies = [KeyboardEventManager.KeyboardEventProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add keyboard-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        _group = parser.add_argument_group('Keyboard Options')

        return parser
