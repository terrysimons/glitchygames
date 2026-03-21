#!/usr/bin/env python3
"""Touch Event Manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Self, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import TOUCH_EVENTS, HashableEvent, ResourceManager, TouchEvents

LOG = logging.getLogger('game.touch')
LOG.addHandler(logging.NullHandler())


class TouchEventManager(ResourceManager):
    """Touch event manager."""

    class TouchEventProxy(TouchEvents, ResourceManager):
        """Touch event proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the finger event proxy.

            Args:
                game (object): The game object.

            """
            super().__init__(game=game)
            self.fingers: dict[int, Any] = {}
            self.game: Any = game
            try:
                self.proxies: list[Any] = [self.game, pygame._sdl2.touch]  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]  # ty: ignore[possibly-missing-submodule]
            except AttributeError:
                self.proxies = [self.game]

        @override
        def on_touch_down_event(self: Self, event: HashableEvent) -> None:
            """Handle finger down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_touch_down_event(event)

        @override
        def on_touch_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle finger motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_touch_motion_event(event)

        @override
        def on_touch_up_event(self: Self, event: HashableEvent) -> None:
            """Handle finger up events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_touch_up_event(event)

        @override
        def on_multi_touch_down_event(self: Self, event: HashableEvent) -> None:
            """Handle multi-touch down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_multi_touch_down_event(event)

        @override
        def on_multi_touch_motion_event(self: Self, event: HashableEvent) -> None:
            """Handle multi-touch motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_multi_touch_motion_event(event)

        @override
        def on_multi_touch_up_event(self: Self, event: HashableEvent) -> None:
            """Handle multi-touch up events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_multi_touch_up_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the touch event manager.

        Args:
            game (object): The game object.

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(TOUCH_EVENTS)
        except pygame.error:
            LOG.debug('Failed to set allowed touch events: pygame not fully initialized')
        self.proxies = [TouchEventManager.TouchEventProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add touch-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        _group = parser.add_argument_group('Touch Options')

        return parser
