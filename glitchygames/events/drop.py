#!/usr/bin/env python3
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import argparse

    import pygame

from glitchygames.events import DropEvents, ResourceManager

log = logging.getLogger('game.events.drop_events')
log.addHandler(logging.NullHandler())


class DropManager(ResourceManager):
    class DropProxy(DropEvents, ResourceManager):
        def __init__(self: Self, game: object = None) -> None:
            """
            Pygame drop event proxy.

            DropProxy facilitates mouse handling by bridging DROP* events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game]

        def on_drop_begin_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_drop_begin_event(event)

        def on_drop_complete_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_drop_complete_event(event)

        def on_drop_file_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_drop_file_event(event)

        def on_drop_text_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_drop_text_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """
        Manage controllers.

        DropManager manages drop events.

        Args:
        ----
        game -

        """
        super().__init__(game=game)

        self.proxies = [DropManager.DropProxy(game=game)]

    @classmethod
    def args(cls: Self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        group = parser.add_argument_group('Drop Options')  # noqa: F841

        return parser
