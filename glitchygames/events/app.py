"""App event manager for application lifecycle events."""

import logging
from typing import Self

from glitchygames.events import AppEvents, HashableEvent, ResourceManager

LOG = logging.getLogger(__name__)


class AppManager(ResourceManager, AppEvents):
    """Manager for application lifecycle events."""

    log: logging.Logger = LOG

    def __init__(self, game: object):
        """Initialize app manager.

        Args:
            game: The game/scene object.

        """
        super().__init__(game)
        self.game = game
        self.proxies = []

    def on_app_did_enter_background_event(self: Self, event: HashableEvent) -> None:
        """Handle app did enter background event."""
        # Delegate to game if it has the method
        if hasattr(self.game, "on_app_did_enter_background_event"):
            self.game.on_app_did_enter_background_event(event)

    def on_app_did_enter_foreground_event(self: Self, event: HashableEvent) -> None:
        """Handle app did enter foreground event."""
        # Delegate to game if it has the method
        if hasattr(self.game, "on_app_did_enter_foreground_event"):
            self.game.on_app_did_enter_foreground_event(event)

    def on_app_will_enter_background_event(self: Self, event: HashableEvent) -> None:
        """Handle app will enter background event."""
        # Delegate to game if it has the method
        if hasattr(self.game, "on_app_will_enter_background_event"):
            self.game.on_app_will_enter_background_event(event)

    def on_app_will_enter_foreground_event(self: Self, event: HashableEvent) -> None:
        """Handle app will enter foreground event."""
        # Delegate to game if it has the method
        if hasattr(self.game, "on_app_will_enter_foreground_event"):
            self.game.on_app_will_enter_foreground_event(event)

    def on_app_low_memory_event(self: Self, event: HashableEvent) -> None:
        """Handle app low memory event."""
        # Delegate to game if it has the method
        if hasattr(self.game, "on_app_low_memory_event"):
            self.game.on_app_low_memory_event(event)

    def on_app_terminating_event(self: Self, event: HashableEvent) -> None:
        """Handle app terminating event."""
        # Delegate to game if it has the method
        if hasattr(self.game, "on_app_terminating_event"):
            self.game.on_app_terminating_event(event)
