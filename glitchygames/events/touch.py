#!/usr/bin/env python3
"""Touch Event Manager."""

from __future__ import annotations

import logging
from typing import Self

import pygame

from glitchygames.events import TOUCH_EVENTS, ResourceManager, TouchEvents

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
            self.fingers: dict = {}
            self.game: object = game
            try:
                self.proxies: list = [self.game, pygame._sdl2.touch]
            except AttributeError:
                self.proxies = [self.game]

        def on_touch_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle finger down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_touch_down_event(event)

        def on_touch_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle finger motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_touch_motion_event(event)

        def on_touch_up_event(self: Self, event: pygame.event.Event) -> None:
            """Handle finger up events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_touch_up_event(event)

        def on_multi_touch_down_event(self: Self, event: pygame.event.Event) -> None:
            """Handle multi-touch down events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_multi_touch_down_event(event)

        def on_multi_touch_motion_event(self: Self, event: pygame.event.Event) -> None:
            """Handle multi-touch motion events.

            Args:
                event (pygame.event.Event): The event to handle.

            """
            self.game.on_multi_touch_motion_event(event)

        def on_multi_touch_up_event(self: Self, event: pygame.event.Event) -> None:
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
