#!/usr/bin/env python3
"""Keyboard Event Manager."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import KeyboardEvents, ResourceManager

log = logging.getLogger('game.keyboard')
log.addHandler(logging.NullHandler())


class KeyboardManager(ResourceManager):
    """Manage keyboard events."""

    class KeyboardProxy(KeyboardEvents, ResourceManager):
        """Keyboard event proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the keyboard event proxy.

            Args:
                game (object): The game object.

            Returns:
                None
            """
            super().__init__(game=game)
            self.keys = {}
            self.game = game
            self.proxies = [self.game, pygame.key]

        def on_key_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle key down events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None
            """
            # The KEYUP and KEYDOWN events are
            # different.  KEYDOWN contains an extra
            # key in its dictionary (unicode), which
            # KEYUP does not contain, so we'll make
            # a copy of the dictionary, and then
            # delete the key "unicode" so we can track
            # both sets of events.
            keyboard_key = event.dict.copy()
            del keyboard_key['unicode']

            # This makes it possible to use
            # a dictionary as a key, which is
            # normally not possible.
            self.keys[
                tuple(
                    sorted(
                        frozenset(keyboard_key.items())
                    )
                )
            ] = event

            self.game.on_key_down_event(event)
            self.on_key_chord_down_event(event)

        def on_key_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle key up events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None
            """
            # This makes it possible to use
            # a dictionary as a key, which is
            # normally not possible.
            self.keys[
                tuple(
                    sorted(
                        frozenset(event.dict.items())
                    )
                )
            ] = event

            self.game.on_key_up_event(event)
            self.on_key_chord_up_event(event)

        def on_key_chord_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle key chord down events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None
            """
            keys_down = [self.keys[key]
                         for key in self.keys
                         if self.keys[key].type == pygame.KEYDOWN]

            self.game.on_key_chord_down_event(event, keys_down)

        def on_key_chord_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle key chord up events.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None
            """
            keys_down = [self.keys[key]
                         for key in self.keys
                         if self.keys[key].type == pygame.KEYDOWN]

            self.game.on_key_chord_up_event(event, keys_down)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the keyboard event manager.

        Args:
            game (object): The game object.

        Returns:
            None
        """
        super().__init__(game=game)
        self.proxies = [KeyboardManager.KeyboardProxy(game=game)]

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add keyboard-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser
        """
        group = parser.add_argument_group('Keyboard Options')  # noqa: F841

        return parser
