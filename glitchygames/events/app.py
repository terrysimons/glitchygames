"""App event manager for application lifecycle events."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

if TYPE_CHECKING:
    import argparse

import pygame

from glitchygames.events import APP_EVENTS, AppEvents, HashableEvent, ResourceManager

LOG = logging.getLogger(__name__)


class AppEventManager(ResourceManager):
    """Manager for application lifecycle events."""

    log: ClassVar[logging.Logger] = LOG

    class AppEventProxy(AppEvents, ResourceManager):
        """Proxy for application lifecycle events."""

        log: ClassVar[logging.Logger] = LOG

        def __init__(self: Self, game: object) -> None:
            """Initialize the app event proxy with a game object."""
            super().__init__(game)
            self.game: Any = game
            self.proxies = [self.game]

        @override
        def on_app_did_enter_background_event(self: Self, event: HashableEvent) -> None:
            """Forward the app-did-enter-background event to the game object."""
            if hasattr(self.game, 'on_app_did_enter_background_event'):
                self.game.on_app_did_enter_background_event(event)

        @override
        def on_app_did_enter_foreground_event(self: Self, event: HashableEvent) -> None:
            """Forward the app-did-enter-foreground event to the game object."""
            if hasattr(self.game, 'on_app_did_enter_foreground_event'):
                self.game.on_app_did_enter_foreground_event(event)

        @override
        def on_app_will_enter_background_event(self: Self, event: HashableEvent) -> None:
            """Forward the app-will-enter-background event to the game object."""
            if hasattr(self.game, 'on_app_will_enter_background_event'):
                self.game.on_app_will_enter_background_event(event)

        @override
        def on_app_will_enter_foreground_event(self: Self, event: HashableEvent) -> None:
            """Forward the app-will-enter-foreground event to the game object."""
            if hasattr(self.game, 'on_app_will_enter_foreground_event'):
                self.game.on_app_will_enter_foreground_event(event)

        @override
        def on_app_low_memory_event(self: Self, event: HashableEvent) -> None:
            """Forward the app-low-memory event to the game object."""
            if hasattr(self.game, 'on_app_low_memory_event'):
                self.game.on_app_low_memory_event(event)

        @override
        def on_app_terminating_event(self: Self, event: HashableEvent) -> None:
            """Forward the app-terminating event to the game object."""
            if hasattr(self.game, 'on_app_terminating_event'):
                self.game.on_app_terminating_event(event)

    def __init__(self, game: object) -> None:
        """Initialize app manager.

        Args:
            game: The game/scene object.

        """
        super().__init__(game)
        # Ensure app-related events are enabled
        try:
            pygame.event.set_allowed(APP_EVENTS)
        except pygame.error:
            LOG.debug('Failed to set allowed app events: pygame not fully initialized')
        self.game: Any = game
        self.proxies = [AppEventManager.AppEventProxy(game=game)]

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add app-specific arguments to the global parser.

        This class method will get called automatically by the GameEngine class.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            argparse.ArgumentParser

        """
        _group = parser.add_argument_group('App Options')

        return parser
