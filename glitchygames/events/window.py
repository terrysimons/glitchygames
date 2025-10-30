#!usr/bin/env python3
"""Window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:  # pragma: no cover
    import argparse  # pragma: no cover

    import pygame  # pragma: no cover

import pygame
from glitchygames.events import WINDOW_EVENTS
from glitchygames.events import ResourceManager, WindowEvents

LOG = logging.getLogger("game.window")
LOG.addHandler(logging.NullHandler())


class WindowManager(ResourceManager):
    """Window manager event handler."""

    class WindowManagerProxy(WindowEvents, ResourceManager):
        """Window manager event proxy."""

        def __init__(self: Self, game: object = None) -> None:
            """Initialize the window manager proxy.

            Args:
                game (object): The game instance.

            Returns:
                None

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game]

        def on_window_close_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window close event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_close_event(event)

        def on_window_enter_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window enter event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_enter_event(event)

        def on_window_exposed_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window exposed event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_exposed_event(event)

        def on_window_focus_gained_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window focus gained event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_focus_gained_event(event)

        def on_window_focus_lost_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window focus lost event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_focus_lost_event(event)

        def on_window_hidden_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window hidden event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_hidden_event(event)

        def on_window_hit_test_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window hit test event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_hit_test_event(event)

        def on_window_leave_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window leave event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_leave_event(event)

        def on_window_maximized_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window maximized event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_maximized_event(event)

        def on_window_minimized_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window minimized event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_minimized_event(event)

        def on_window_moved_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window moved event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_moved_event(event)

        def on_window_resized_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window resized event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_resized_event(event)

        def on_window_restored_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window restored event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_restored_event(event)

        def on_window_shown_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window shown event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_shown_event(event)

        def on_window_size_changed_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window size changed event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_size_changed_event(event)

        def on_window_take_focus_event(self: Self, event: pygame.event.Event) -> None:
            """Handle the window take focus event.

            Args:
                event (pygame.event.Event): The event to handle.

            Returns:
                None

            """
            self.game.on_window_take_focus_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the window event manager.

        Args:
            game (object): The game instance.

        Returns:
            None

        """
        super().__init__(game=game)
        try:
            pygame.event.set_allowed(WINDOW_EVENTS)
        except Exception:
            pass
        self.proxies = [WindowManager.WindowManagerProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add window-specific arguments to the global parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        group = parser.add_argument_group("Window Options")  # noqa: F841

        return parser
