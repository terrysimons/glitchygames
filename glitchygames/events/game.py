"""Game event manager for game-specific events."""

import argparse
import logging
from typing import Self

from glitchygames.events import GameEvents, HashableEvent, ResourceManager
from glitchygames.scenes import Scene

LOG = logging.getLogger(__name__)


class GameEventManager(ResourceManager, GameEvents):
    """Manager for game events."""

    log: logging.Logger = LOG

    class GameEventProxy(ResourceManager):
        """Game event proxy."""

        log: logging.Logger = LOG

        def __init__(self: Self, game: Scene) -> None:
            """Initialize the game proxy.

            Args:
                game: the game instance

            Returns:
                None

            """
            super().__init__(game=game)
            self.game: Scene = game
            self.proxies: list = [self.game]

        def on_active_event(self: Self, event: HashableEvent) -> None:
            """Handle active event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # ACTIVEEVENT      gain, state
            self.game.on_active_event(event=event)

        def on_fps_event(self: Self, event: HashableEvent) -> None:
            """Handle fps event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # FPSEVENT is pygame.USEREVENT + 1
            self.game.on_fps_event(event=event)

        def on_game_event(self: Self, event: HashableEvent) -> None:
            """Handle game event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # GAMEEVENT is pygame.USEREVENT + 2
            self.game.on_game_event(event=event)

        def on_menu_item_event(self: Self, event: HashableEvent) -> None:
            """Handle menu item event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # MENUEVENT is pygame.USEREVENT + 3
            self.game.on_menu_item_event(event=event)

        def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
            """Handle sys wm event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # SYSWMEVENT
            self.game.on_sys_wm_event(event=event)

        def on_user_event(self: Self, event: HashableEvent) -> None:
            """Handle user event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # USEREVENT        code
            self.game.on_user_event(event=event)

        def on_video_expose_event(self: Self, event: HashableEvent) -> None:
            """Handle video expose event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # VIDEOEXPOSE      none
            self.game.on_video_expose_event(event=event)

        def on_video_resize_event(self: Self, event: HashableEvent) -> None:
            """Handle video resize event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # VIDEORESIZE      size, w, h
            self.game.on_video_resize_event(event=event)

        def on_quit_event(self: Self, event: HashableEvent) -> None:
            """Handle quit event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # QUIT             none
            self.game.on_quit_event(event=event)

        def on_render_device_reset_event(self: Self, event: HashableEvent) -> None:
            """Handle render device reset event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # RENDER_DEVICE_RESET
            self.game.on_render_device_reset_event(event=event)

        def on_render_targets_reset_event(self: Self, event: HashableEvent) -> None:
            """Handle render targets reset event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # RENDER_TARGETS_RESET
            self.game.on_render_targets_reset_event(event=event)

        def on_clipboard_update_event(self: Self, event: HashableEvent) -> None:
            """Handle clipboard update event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # CLIPBOARDUPDATE
            self.game.on_clipboard_update_event(event=event)

        def on_locale_changed_event(self: Self, event: HashableEvent) -> None:
            """Handle locale changed event.

            Args:
                event: The pygame event.

            Returns:
                None

            """
            # LOCALECHANGED
            self.game.on_locale_changed_event(event=event)

    def __init__(self: Self, game: Scene) -> None:
        """Initialize the game event manager.

        Args:
            game: The game instance.

        Returns:
            None

        """
        super().__init__(game=game)
        self.proxies: list[GameEventManager.GameEventProxy] = [GameEventManager.GameEventProxy(game=game)]

    def on_active_event(self: Self, event: HashableEvent) -> None:
        """Handle active event."""
        for proxy in self.proxies:
            proxy.on_active_event(event)

    def on_clipboard_update_event(self: Self, event: HashableEvent) -> None:
        """Handle clipboard update event."""
        for proxy in self.proxies:
            proxy.on_clipboard_update_event(event)

    def on_fps_event(self: Self, event: HashableEvent) -> None:
        """Handle fps event."""
        for proxy in self.proxies:
            proxy.on_fps_event(event)

    def on_game_event(self: Self, event: HashableEvent) -> None:
        """Handle game event."""
        for proxy in self.proxies:
            proxy.on_game_event(event)

    def on_locale_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle locale changed event."""
        for proxy in self.proxies:
            proxy.on_locale_changed_event(event)

    def on_menu_item_event(self: Self, event: HashableEvent) -> None:
        """Handle menu item event."""
        for proxy in self.proxies:
            proxy.on_menu_item_event(event)

    def on_quit_event(self: Self, event: HashableEvent) -> None:
        """Handle quit event."""
        for proxy in self.proxies:
            proxy.on_quit_event(event)

    def on_render_device_reset_event(self: Self, event: HashableEvent) -> None:
        """Handle render device reset event."""
        for proxy in self.proxies:
            proxy.on_render_device_reset_event(event)

    def on_render_targets_reset_event(self: Self, event: HashableEvent) -> None:
        """Handle render targets reset event."""
        for proxy in self.proxies:
            proxy.on_render_targets_reset_event(event)

    def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
        """Handle sys wm event."""
        for proxy in self.proxies:
            proxy.on_sys_wm_event(event)

    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Handle user event."""
        for proxy in self.proxies:
            proxy.on_user_event(event)

    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Handle video expose event."""
        for proxy in self.proxies:
            proxy.on_video_expose_event(event)

    def on_video_resize_event(self: Self, event: HashableEvent) -> None:
        """Handle video resize event."""
        for proxy in self.proxies:
            proxy.on_video_resize_event(event)

    @classmethod
    def args(cls, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add arguments to the argument parser.

        Args:
            parser (argparse.ArgumentParser): The argument parser.

        Returns:
            None

        """
        group = parser.add_argument_group("Game Options")
        group.add_argument(
            "-l",
            "--log-level",
            help="set the logging level",
            choices=["debug", "info", "warning", "error", "critical"],
            default="info",
        )
        group.add_argument(
            "--no-unhandled-events",
            help="fail on unhandled events",
            action="store_true",
            default=False,
        )
        group.add_argument(
            "-p", "--profile", help="enable profiling", action="store_true", default=False
        )

        return parser
