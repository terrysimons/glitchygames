"""App event manager for application lifecycle events."""

import logging
import pygame
from glitchygames.events import APP_EVENTS
from typing import Self

from glitchygames.events import AppEvents, HashableEvent, ResourceManager

LOG = logging.getLogger(__name__)


class AppEventManager(ResourceManager):
    """Manager for application lifecycle events."""

    log: logging.Logger = LOG

    class AppEventProxy(AppEvents, ResourceManager):
        """Proxy for application lifecycle events."""

        log: logging.Logger = LOG

        def __init__(self: Self, game: object) -> None:
            super().__init__(game)
            self.game = game
            self.proxies = [self.game]

        def on_app_did_enter_background_event(self: Self, event: HashableEvent) -> None:
            if hasattr(self.game, "on_app_did_enter_background_event"):
                self.game.on_app_did_enter_background_event(event)

        def on_app_did_enter_foreground_event(self: Self, event: HashableEvent) -> None:
            if hasattr(self.game, "on_app_did_enter_foreground_event"):
                self.game.on_app_did_enter_foreground_event(event)

        def on_app_will_enter_background_event(self: Self, event: HashableEvent) -> None:
            if hasattr(self.game, "on_app_will_enter_background_event"):
                self.game.on_app_will_enter_background_event(event)

        def on_app_will_enter_foreground_event(self: Self, event: HashableEvent) -> None:
            if hasattr(self.game, "on_app_will_enter_foreground_event"):
                self.game.on_app_will_enter_foreground_event(event)

        def on_app_low_memory_event(self: Self, event: HashableEvent) -> None:
            if hasattr(self.game, "on_app_low_memory_event"):
                self.game.on_app_low_memory_event(event)

        def on_app_terminating_event(self: Self, event: HashableEvent) -> None:
            if hasattr(self.game, "on_app_terminating_event"):
                self.game.on_app_terminating_event(event)

    def __init__(self, game: object):
        """Initialize app manager.

        Args:
            game: The game/scene object.

        """
        super().__init__(game)
        # Ensure app-related events are enabled
        try:
            pygame.event.set_allowed(APP_EVENTS)
        except Exception:
            pass
        self.game = game
        self.proxies = [AppEventManager.AppEventProxy(game=game)]
