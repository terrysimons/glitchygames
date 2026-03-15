#!/usr/bin/env python3
"""Drop Events.

This is a simple drop event class that can be used to handle drag & drop events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

    import pygame

import pygame
from glitchygames.events import DROP_EVENTS, DropEvents, ResourceManager

log = logging.getLogger("game.events.drop_events")
log.addHandler(logging.NullHandler())


class DropEventManager(ResourceManager):
    """Manage drop events."""

    class DropEventProxy(DropEvents, ResourceManager):
        """Proxy class for drop events."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the drop proxy.

            Args:
                game: The game instance.

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game]

        def on_drop_begin_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop begin event.

            Args:
                event: The pygame event.

            """
            self.game.on_drop_begin_event(event)

        def on_drop_complete_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop complete event.

            Args:
                event: The pygame event.

            """
            self.game.on_drop_complete_event(event)

        def on_drop_file_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop file event.

            Args:
                event: The pygame event.

            """
            self.game.on_drop_file_event(event)

        def on_drop_text_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop text event.

            Args:
                event: The pygame event.

            """
            self.game.on_drop_text_event(event)

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add arguments to the argument parser.

        Args:
            parser: The argument parser.

        Returns:
            The argument parser.

        """
        _group = parser.add_argument_group("Drop Options")

        return parser

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the drop manager.

        Args:
            game: The game instance.

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(DROP_EVENTS)
        except pygame.error:
            log.debug("Failed to set allowed drop events: pygame not fully initialized")

        self.proxies = [DropEventManager.DropEventProxy(game=game)]
