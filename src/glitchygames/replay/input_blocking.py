"""Block real input at SDL while recorded input is served, then put the earlier state back.

A replay (glitchygames/replay/driver.py) serves every external event from its recording, so
real input, device and window events are blocked at SDL (``pygame.event.set_blocked``): they
never enter the queue. ``EventTypeBlock`` records each type's blocked state before blocking it
and restores exactly that state, so a type a game had already blocked stays blocked. Event
managers made mid-run (a scene's widgets) call ``pygame.event.set_allowed``, so the replay
blocks the types again on every pump (``reassert``). Part 3's playback scope can reuse it.

Blocking a type also refuses posts of it (``pygame.event.post`` returns False), including the
game's own: game code that fakes input by posting, say, KEYDOWN loses those posts during a
replay. The engine's own posts are QUIT and custom types, which are never blocked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import pygame

if TYPE_CHECKING:
    from collections.abc import Iterable

# Every real input, device and window event type of pygame-ce 2.5.8, blocked during a replay.
# Never blocked: pygame.QUIT and pygame.WINDOWCLOSE (the user can still close the window, which
# ends the replay), and the custom range from pygame.USEREVENT up (FPSEVENT, GAMEEVENT,
# MENUEVENT, pygame.event.custom_type() types), so the game's own posts keep arriving. Left
# unblocked as well, being neither input nor the window's: app lifecycle (APP_*), locale,
# clipboard and renderer resets; the replay's pump drops them as real external events.
#
# Blocking the window types does not starve SDL or pygame of size changes. Source: pygame-ce
# 2.5.8 src_c/event.c (https://github.com/pygame-community/pygame-ce/blob/2.5.8/src_c/event.c):
# on SDL2, pg_event_set_blocked re-enables the raw SDL_WINDOWEVENT after every call ("Never
# block SDL_WINDOWEVENT on SDL2, we need them for translation"), pg_event_filter does not filter
# window events (it still turns SDL_WINDOWEVENT_RESIZED into VIDEORESIZE), and blocked PGE_WINDOW*
# types are "pseudo-blocked": _pg_event_pump removes them from the queue with
# _pg_filter_blocked_events. SDL3 builds of pygame-ce have their own window event types without
# that SDL2 special case: check this again when moving to SDL3.
REAL_INPUT_EVENT_TYPES: tuple[int, ...] = (
    # Keyboard and text input (IME)
    pygame.KEYDOWN,
    pygame.KEYUP,
    pygame.TEXTEDITING,
    pygame.TEXTINPUT,
    pygame.KEYMAPCHANGED,
    # Mouse
    pygame.MOUSEMOTION,
    pygame.MOUSEBUTTONDOWN,
    pygame.MOUSEBUTTONUP,
    pygame.MOUSEWHEEL,
    # Touch
    pygame.FINGERDOWN,
    pygame.FINGERUP,
    pygame.FINGERMOTION,
    pygame.MULTIGESTURE,
    # Joysticks
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
    pygame.JOYDEVICEADDED,
    pygame.JOYDEVICEREMOVED,
    # Game controllers
    pygame.CONTROLLERAXISMOTION,
    pygame.CONTROLLERBUTTONDOWN,
    pygame.CONTROLLERBUTTONUP,
    pygame.CONTROLLERDEVICEADDED,
    pygame.CONTROLLERDEVICEREMOVED,
    pygame.CONTROLLERDEVICEREMAPPED,
    pygame.CONTROLLERTOUCHPADDOWN,
    pygame.CONTROLLERTOUCHPADMOTION,
    pygame.CONTROLLERTOUCHPADUP,
    pygame.CONTROLLERSENSORUPDATE,
    # Audio devices
    pygame.AUDIODEVICEADDED,
    pygame.AUDIODEVICEREMOVED,
    # Drag and drop
    pygame.DROPFILE,
    pygame.DROPTEXT,
    pygame.DROPBEGIN,
    pygame.DROPCOMPLETE,
    # The window (all but WINDOWCLOSE), including pygame's legacy window events
    pygame.ACTIVEEVENT,
    pygame.VIDEORESIZE,
    pygame.VIDEOEXPOSE,
    pygame.SYSWMEVENT,
    pygame.WINDOWSHOWN,
    pygame.WINDOWHIDDEN,
    pygame.WINDOWEXPOSED,
    pygame.WINDOWMOVED,
    pygame.WINDOWRESIZED,
    pygame.WINDOWSIZECHANGED,
    pygame.WINDOWMINIMIZED,
    pygame.WINDOWMAXIMIZED,
    pygame.WINDOWRESTORED,
    pygame.WINDOWENTER,
    pygame.WINDOWLEAVE,
    pygame.WINDOWFOCUSGAINED,
    pygame.WINDOWFOCUSLOST,
    pygame.WINDOWTAKEFOCUS,
    pygame.WINDOWHITTEST,
    pygame.WINDOWICCPROFCHANGED,
    pygame.WINDOWDISPLAYCHANGED,
)


class EventTypeBlock:
    """Blocks event types at SDL and restores each one's blocked state at ``block()`` time.

    ``restore()`` returns every type to the state it had when ``block()`` ran, overriding any
    ``pygame.event.set_allowed`` or ``set_blocked`` calls made for those types in between.

    Attributes:
        event_types: The types ``block()`` blocks.

    """

    def __init__(self: Self, *, event_types: Iterable[int]) -> None:
        """Prepare to block ``event_types`` (nothing is blocked until ``block()``).

        Args:
            event_types: The event types to block.

        """
        self.event_types: tuple[int, ...] = tuple(event_types)
        # Type -> whether it was blocked before block(); None while not active
        self._blocked_before: dict[int, bool] | None = None

    @property
    def is_active(self: Self) -> bool:
        """True between ``block()`` and ``restore()``."""
        return self._blocked_before is not None

    def block(self: Self) -> None:
        """Record each type's blocked state, then block every type (a no-op while active)."""
        if self.is_active:
            return
        self._blocked_before = {
            event_type: pygame.event.get_blocked(event_type) for event_type in self.event_types
        }
        pygame.event.set_blocked(list(self.event_types))

    def reassert(self: Self) -> None:
        """Block every type again, keeping the snapshot ``block()`` took (a no-op unless active).

        Undoes ``pygame.event.set_allowed`` calls made since (an event manager made mid-run).
        """
        if self._blocked_before is None:
            return
        pygame.event.set_blocked(list(self.event_types))

    def restore(self: Self) -> None:
        """Return each type to its state at ``block()`` time (a no-op unless active).

        Types blocked then stay blocked; the others are unblocked, whatever was set in between.
        """
        if self._blocked_before is None:
            return
        pygame.event.set_allowed([
            event_type
            for event_type, was_blocked in self._blocked_before.items()
            if not was_blocked
        ])
        self._blocked_before = None
