#!usr/bin/env python3
import logging
from typing import Self

import pygame

from glitchygames.events import ResourceManager, WindowEvents

LOG = logging.getLogger('game.window')
LOG.addHandler(logging.NullHandler())


class WindowManager(ResourceManager):

    class WindowManagerProxy(WindowEvents, ResourceManager):
        def __init__(self: Self, game: object = None) -> None:
            """
            Pygame window event proxy.

            WindowManagerProxy facilitates window handling by bridging window events between
            pygame and your game.

            Args:
            ----
            game - The game instance.

            """
            super().__init__(game)

            self.game = game
            self.proxies = [self.game]

        def on_window_close_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_close_event(event)

        def on_window_enter_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_enter_event(event)

        def on_window_exposed_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_exposed_event(event)

        def on_window_focus_gained_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_focus_gained_event(event)

        def on_window_focus_lost_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_focus_lost_event(event)

        def on_window_hidden_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_hidden_event(event)

        def on_window_hit_test_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_hit_test_event(event)

        def on_window_leave_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_leave_event(event)

        def on_window_maximized_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_maximized_event(event)

        def on_window_minimized_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_minimized_event(event)

        def on_window_moved_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_moved_event(event)

        def on_window_resized_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_resized_event(event)

        def on_window_restored_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_restored_event(event)

        def on_window_shown_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_shown_event(event)

        def on_window_size_changed_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_size_changed_event(event)

        def on_window_take_focus_event(self: Self, event: pygame.event.Event) -> None:
            self.game.on_window_take_focus_event(event)

    def __init__(self: Self, game: object = None) -> None:
        """
        Window event manager.

        WindowManager interfaces GameEngine with WindowManager.WindowManagerProxy.

        Args:
        ----
        game - The game instance.

        """
        super().__init__(game=game)
        self.proxies = [WindowManager.WindowManagerProxy(game=game)]

    @classmethod
    def args(cls, parser):
        group = parser.add_argument_group('Window Options')  # noqa: F841

        return parser
