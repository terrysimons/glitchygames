#!/usr/bin/env python3
"""Glitchy Games system event interfaces.

This module contains the abstract event interfaces and default stub
implementations for all system/lifecycle events: audio, app lifecycle,
window, drop, game, and font events.
"""

from __future__ import annotations

import abc
from typing import Self

from glitchygames.events.base import EventInterface, HashableEvent, unhandled_event


# Mixin
class AudioEvents(EventInterface):
    """Mixin for audio events."""

    @abc.abstractmethod
    def on_audio_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle audio device added events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # AUDIODEVICEADDED   which, iscapture

    @abc.abstractmethod
    def on_audio_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle audio device removed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # AUDIODEVICEREMOVED which, iscapture


# Mixin
class AudioEventStubs(AudioEvents):
    """Mixin for audio events."""

    def on_audio_device_added_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle audio device added events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # AUDIODEVICEADDED   which, iscapture
        return unhandled_event(self, event)

    def on_audio_device_removed_event(self: Self, event: HashableEvent) -> None:  # type: ignore[override]
        """Handle audio device removed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # AUDIODEVICEREMOVED which, iscapture
        return unhandled_event(self, event)


class AppEvents(EventInterface):
    """Mixin for application lifecycle events.

    Handles mobile and cross-platform app lifecycle events
    like background/foreground transitions and memory warnings.
    """

    @abc.abstractmethod
    def on_app_did_enter_background_event(self: Self, event: HashableEvent) -> None:
        """Handle app entering background.

        Args:
            event (HashableEvent): The event to handle.

        """
        # APP_DIDENTERBACKGROUND

    @abc.abstractmethod
    def on_app_did_enter_foreground_event(self: Self, event: HashableEvent) -> None:
        """Handle app entering foreground.

        Args:
            event (HashableEvent): The event to handle.

        """
        # APP_DIDENTERFOREGROUND

    @abc.abstractmethod
    def on_app_will_enter_background_event(self: Self, event: HashableEvent) -> None:
        """Handle app about to enter background.

        Args:
            event (HashableEvent): The event to handle.

        """
        # APP_WILLENTERBACKGROUND

    @abc.abstractmethod
    def on_app_will_enter_foreground_event(self: Self, event: HashableEvent) -> None:
        """Handle app about to enter foreground.

        Args:
            event (HashableEvent): The event to handle.

        """
        # APP_WILLENTERFOREGROUND

    @abc.abstractmethod
    def on_app_low_memory_event(self: Self, event: HashableEvent) -> None:
        """Handle low memory warning.

        Args:
            event (HashableEvent): The event to handle.

        """
        # APP_LOWMEMORY

    @abc.abstractmethod
    def on_app_terminating_event(self: Self, event: HashableEvent) -> None:
        """Handle app termination.

        Args:
            event (HashableEvent): The event to handle.

        """
        # APP_TERMINATING


class AppEventStubs(EventInterface):
    """Default implementations for app events."""

    def __init__(self: Self) -> None:
        """Initialize app event stubs."""
        super().__init__()
        self.options = {'debug_events': False, 'no_unhandled_events': True}

    def on_app_did_enter_background_event(self: Self, event: HashableEvent) -> None:
        """Log and raise UnhandledEventError by default."""
        unhandled_event(self, event)

    def on_app_did_enter_foreground_event(self: Self, event: HashableEvent) -> None:
        """Log and raise UnhandledEventError by default."""
        unhandled_event(self, event)

    def on_app_will_enter_background_event(self: Self, event: HashableEvent) -> None:
        """Log and raise UnhandledEventError by default."""
        unhandled_event(self, event)

    def on_app_will_enter_foreground_event(self: Self, event: HashableEvent) -> None:
        """Log and raise UnhandledEventError by default."""
        unhandled_event(self, event)

    def on_app_low_memory_event(self: Self, event: HashableEvent) -> None:
        """Log and raise UnhandledEventError by default."""
        unhandled_event(self, event)

    def on_app_terminating_event(self: Self, event: HashableEvent) -> None:
        """Log and raise UnhandledEventError by default."""
        unhandled_event(self, event)


class WindowEvents(EventInterface):
    """Mixin for window events."""

    @abc.abstractmethod
    def on_window_close_event(self: Self, event: HashableEvent) -> None:
        """Handle window close events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWCLOSE      none

    @abc.abstractmethod
    def on_window_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle window enter events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWENTER      none

    @abc.abstractmethod
    def on_window_exposed_event(self: Self, event: HashableEvent) -> None:
        """Handle window exposed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWEXPOSED    none

    @abc.abstractmethod
    def on_window_focus_gained_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWFOCUSGAINED none

    @abc.abstractmethod
    def on_window_focus_lost_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWFOCUSLOST  none

    @abc.abstractmethod
    def on_window_hidden_event(self: Self, event: HashableEvent) -> None:
        """Handle window hidden events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWHIDDEN     none

    @abc.abstractmethod
    def on_window_hit_test_event(self: Self, event: HashableEvent) -> None:
        """Handle window hit test events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWHITTEST    none

    @abc.abstractmethod
    def on_window_leave_event(self: Self, event: HashableEvent) -> None:
        """Handle window leave events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWLEAVE      none

    @abc.abstractmethod
    def on_window_maximized_event(self: Self, event: HashableEvent) -> None:
        """Handle window maximized events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWMAXIMIZED  none

    @abc.abstractmethod
    def on_window_minimized_event(self: Self, event: HashableEvent) -> None:
        """Handle window minimized events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWMINIMIZED  none

    @abc.abstractmethod
    def on_window_moved_event(self: Self, event: HashableEvent) -> None:
        """Handle window moved events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWMOVED      none

    @abc.abstractmethod
    def on_window_resized_event(self: Self, event: HashableEvent) -> None:
        """Handle window resized events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWRESIZED    size, w, h

    @abc.abstractmethod
    def on_window_restored_event(self: Self, event: HashableEvent) -> None:
        """Handle window restored events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWRESTORED   none

    @abc.abstractmethod
    def on_window_shown_event(self: Self, event: HashableEvent) -> None:
        """Handle window shown events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWSHOWN      none

    @abc.abstractmethod
    def on_window_size_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle window size changed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWSIZECHANGED size, w, h

    @abc.abstractmethod
    def on_window_take_focus_event(self: Self, event: HashableEvent) -> None:
        """Handle window take focus events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWTAKEFOCUS  none


class WindowEventStubs(EventInterface):
    """Mixin for window events."""

    def on_window_close_event(self: Self, event: HashableEvent) -> None:
        """Handle window close events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWCLOSE      none
        unhandled_event(self, event)

    def on_window_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle window enter events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWENTER      none
        unhandled_event(self, event)

    def on_window_exposed_event(self: Self, event: HashableEvent) -> None:
        """Handle window exposed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWEXPOSED    none
        unhandled_event(self, event)

    def on_window_focus_gained_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWFOCUSGAINED none
        unhandled_event(self, event)

    def on_window_focus_lost_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWFOCUSLOST  none
        unhandled_event(self, event)

    def on_window_hidden_event(self: Self, event: HashableEvent) -> None:
        """Handle window hidden events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWHIDDEN     none
        unhandled_event(self, event)

    def on_window_hit_test_event(self: Self, event: HashableEvent) -> None:
        """Handle window hit test events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWHITTEST    none
        unhandled_event(self, event)

    def on_window_leave_event(self: Self, event: HashableEvent) -> None:
        """Handle window leave events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWLEAVE      none
        unhandled_event(self, event)

    def on_window_maximized_event(self: Self, event: HashableEvent) -> None:
        """Handle window maximized events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWMAXIMIZED  none
        unhandled_event(self, event)

    def on_window_minimized_event(self: Self, event: HashableEvent) -> None:
        """Handle window minimized events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWMINIMIZED  none
        unhandled_event(self, event)

    def on_window_moved_event(self: Self, event: HashableEvent) -> None:
        """Handle window moved events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWMOVED      none
        unhandled_event(self, event)

    def on_window_resized_event(self: Self, event: HashableEvent) -> None:
        """Handle window resized events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWRESIZED    size, w, h
        unhandled_event(self, event)

    def on_window_restored_event(self: Self, event: HashableEvent) -> None:
        """Handle window restored events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWRESTORED   none
        unhandled_event(self, event)

    def on_window_shown_event(self: Self, event: HashableEvent) -> None:
        """Handle window shown events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWSHOWN      none
        unhandled_event(self, event)

    def on_window_size_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle window size changed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWSIZECHANGED size, w, h
        unhandled_event(self, event)

    def on_window_take_focus_event(self: Self, event: HashableEvent) -> None:
        """Handle window take focus events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # WINDOWTAKEFOCUS  none
        unhandled_event(self, event)


# Mixin
class DropEvents(EventInterface):
    """Mixin for drop events."""

    @abc.abstractmethod
    def on_drop_begin_event(self: Self, event: HashableEvent) -> None:
        """Handle drop begin event.

        Args:
            event: The pygame event.

        """
        # DROPBEGIN        none

    @abc.abstractmethod
    def on_drop_file_event(self: Self, event: HashableEvent) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event.

        """
        # DROPFILE         file

    @abc.abstractmethod
    def on_drop_text_event(self: Self, event: HashableEvent) -> None:
        """Handle drop text event.

        Args:
            event: The pygame event.

        """
        # DROPTEXT         text

    @abc.abstractmethod
    def on_drop_complete_event(self: Self, event: HashableEvent) -> None:
        """Handle drop complete event.

        Args:
            event: The pygame event.

        """
        # DROPCOMPLETE     none


# Mixin
class DropEventStubs(EventInterface):
    """Mixin for drop events."""

    def on_drop_begin_event(self: Self, event: HashableEvent) -> None:
        """Handle drop begin event.

        Args:
            event: The pygame event.

        """
        # DROPBEGIN        none
        unhandled_event(self, event)

    def on_drop_file_event(self: Self, event: HashableEvent) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event.

        """
        # DROPFILE         file
        unhandled_event(self, event)

    def on_drop_text_event(self: Self, event: HashableEvent) -> None:
        """Handle drop text event.

        Args:
            event: The pygame event.

        """
        # DROPTEXT         text
        unhandled_event(self, event)

    def on_drop_complete_event(self: Self, event: HashableEvent) -> None:
        """Handle drop complete event.

        Args:
            event: The pygame event.

        """
        # DROPCOMPLETE     none
        unhandled_event(self, event)


# Mixin
# NOTE: Consider adding a glitchy games event index to allow
# games to easily extend pygame further without impacting
# the core engine.
class GameEvents(EventInterface):
    """Mixin for glitchy game events.

    This includes built-ins like QUIT, and synthesized
    events like FPS and GAME events.

    It's sort of a catch-all for event types that didn't have
    a good home otherwise.
    """

    @abc.abstractmethod
    def on_active_event(self: Self, event: HashableEvent) -> None:
        """Handle active events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # ACTIVEEVENT      gain, state

    @abc.abstractmethod
    def on_fps_event(self: Self, event: HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # FPSEVENT is pygame.USEREVENT + 1

    @abc.abstractmethod
    def on_game_event(self: Self, event: HashableEvent) -> None:
        """Handle game events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # GAMEEVENT is pygame.USEREVENT + 2

    @abc.abstractmethod
    def on_menu_item_event(self: Self, event: HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MENUEVENT is pygame.USEREVENT + 3

    @abc.abstractmethod
    def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # SYSWMEVENT

    @abc.abstractmethod
    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Handle user events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # USEREVENT        code

    @abc.abstractmethod
    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # VIDEOEXPOSE      none

    @abc.abstractmethod
    def on_video_resize_event(self: Self, event: HashableEvent) -> None:
        """Handle video resize events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # VIDEORESIZE      size, w, h

    @abc.abstractmethod
    def on_quit_event(self: Self, event: HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # QUIT             none

    @abc.abstractmethod
    def on_render_device_reset_event(self: Self, event: HashableEvent) -> None:
        """Handle render device reset events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # RENDER_DEVICE_RESET

    @abc.abstractmethod
    def on_render_targets_reset_event(self: Self, event: HashableEvent) -> None:
        """Handle render targets reset events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # RENDER_TARGETS_RESET

    @abc.abstractmethod
    def on_clipboard_update_event(self: Self, event: HashableEvent) -> None:
        """Handle clipboard update events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CLIPBOARDUPDATE

    @abc.abstractmethod
    def on_locale_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle locale changed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # LOCALECHANGED


class GameEventStubs(EventInterface):
    """Mixin for glitchy game events.

    This includes built-ins like QUIT, and synthesized
    events like FPS and GAME events.

    It's sort of a catch-all for event types that didn't have
    a good home otherwise.
    """

    def on_active_event(self: Self, event: HashableEvent) -> None:
        """Handle active events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # ACTIVEEVENT      gain, state
        unhandled_event(self, event)

    def on_fps_event(self: Self, event: HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # FPSEVENT is pygame.USEREVENT + 1
        unhandled_event(self, event)

    def on_game_event(self: Self, event: HashableEvent) -> None:
        """Handle game events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # GAMEEVENT is pygame.USEREVENT + 2
        unhandled_event(self, event)

    def on_menu_item_event(self: Self, event: HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # MENUEVENT is pygame.USEREVENT + 3
        unhandled_event(self, event)

    def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # SYSWMEVENT
        unhandled_event(self, event)

    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Handle user events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # USEREVENT        code
        unhandled_event(self, event)

    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # VIDEOEXPOSE      none
        unhandled_event(self, event)

    def on_video_resize_event(self: Self, event: HashableEvent) -> None:
        """Handle video resize events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # VIDEORESIZE      size, w, h
        unhandled_event(self, event)

    def on_quit_event(self: Self, event: HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # QUIT             none
        unhandled_event(self, event)

    def on_render_device_reset_event(self: Self, event: HashableEvent) -> None:
        """Handle render device reset events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # RENDER_DEVICE_RESET
        unhandled_event(self, event)

    def on_render_targets_reset_event(self: Self, event: HashableEvent) -> None:
        """Handle render targets reset events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # RENDER_TARGETS_RESET
        unhandled_event(self, event)

    def on_clipboard_update_event(self: Self, event: HashableEvent) -> None:
        """Handle clipboard update events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # CLIPBOARDUPDATE
        unhandled_event(self, event)

    def on_locale_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle locale changed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # LOCALECHANGED
        unhandled_event(self, event)


# Mixin
class FontEvents(EventInterface):
    """Mixin for font events."""

    @abc.abstractmethod
    def on_font_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle font changed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # FONTS_CHANGED


# Mixin
class FontEventStubs(EventInterface):
    """Mixin for font events."""

    def on_font_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle font changed events.

        Args:
            event (HashableEvent): The event to handle.

        """
        # FONTS_CHANGED
        unhandled_event(self, event)
