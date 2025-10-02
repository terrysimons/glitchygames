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

from glitchygames.events import DropEvents, ResourceManager

log = logging.getLogger("game.events.drop_events")
log.addHandler(logging.NullHandler())


class DropManager(ResourceManager):
    """Manage drop events."""

    class DropProxy(DropEvents, ResourceManager):
        """Proxy class for drop events."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the drop proxy.

            Args:
                game: The game instance.

            Returns:
                None

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game]

        def on_drop_begin_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop begin event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            self.game.on_drop_begin_event(event)

        def on_drop_complete_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop complete event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            self.game.on_drop_complete_event(event)

        def on_drop_file_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop file event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            self.game.on_drop_file_event(event)

        def on_drop_text_event(self: Self, event: pygame.event.Event) -> None:
            """Handle drop text event.

            Args:
                event: The pygame event.

            Returns:
                None

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
        group = parser.add_argument_group("Drop Options")  # noqa: F841

        return parser

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the drop manager.

        Args:
            game: The game instance.

        Returns:
            None

        """
        super().__init__(game=game)

        self.proxies = [DropManager.DropProxy(game=game)]
