#!/usr/bin/env python3
"""Glitchy Games composite events and EventManager.

This module contains the AllEvents and AllEventStubs composite classes
that inherit from all event interfaces, plus the EventManager that
serves as the root event manager for the game engine.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, ClassVar, Self

from glitchygames.events.base import LOG, ResourceManager
from glitchygames.events.input_event_interfaces import (
    ControllerEvents,
    ControllerEventStubs,
    JoystickEvents,
    JoystickEventStubs,
    KeyboardEvents,
    KeyboardEventStubs,
    MidiEvents,
    MidiEventStubs,
    MouseEvents,
    MouseEventStubs,
    TextEvents,
    TextEventStubs,
    TouchEvents,
    TouchEventStubs,
)
from glitchygames.events.system_event_interfaces import (
    AppEvents,
    AppEventStubs,
    AudioEvents,
    AudioEventStubs,
    DropEvents,
    DropEventStubs,
    FontEvents,
    FontEventStubs,
    GameEvents,
    GameEventStubs,
    WindowEvents,
    WindowEventStubs,
)

if TYPE_CHECKING:
    import logging
    from collections.abc import Callable


# Mixin for all events
class AllEvents(
    AppEvents,
    AudioEvents,
    ControllerEvents,
    DropEvents,
    TouchEvents,
    FontEvents,
    GameEvents,
    JoystickEvents,
    KeyboardEvents,
    MidiEvents,
    MouseEvents,
    TextEvents,
    WindowEvents,
):
    """Mixin for all events."""


class AllEventStubs(
    AppEventStubs,
    AudioEventStubs,
    ControllerEventStubs,
    DropEventStubs,
    TouchEventStubs,
    FontEventStubs,
    GameEventStubs,
    JoystickEventStubs,
    KeyboardEventStubs,
    MidiEventStubs,
    MouseEventStubs,
    TextEventStubs,
    WindowEventStubs,
):
    """Mixin for all event stubs."""


class EventManager(ResourceManager):
    """Root event manager."""

    log: ClassVar[logging.Logger] = LOG
    # Interiting from object is default in Python 3.
    # Linters complain if you do it.
    #
    # This isn't a ResourceManager like other proxies, because
    # it's the fallthrough event object, so we don't have a proxy.

    class EventProxy:
        """Proxy for events."""

        log: logging.Logger = LOG

        def __init__(self: Self, event_source: object) -> None:
            """Initialize the event proxy.

            Args:
                event_source: The event source.

            """
            super().__init__()
            # No proxies for the root class.
            self.proxies: list[Any] = []

            # This is used for leave objects which
            # don't have their own proxies.
            #
            # Subclassed managers that set their own proxy
            # will not have this.
            self.event_source = event_source

        def unhandled_event(self: Self, *_args: Any, **kwargs: Any) -> None:
            """Handle unhandled events.

            Args:
                *_args: Additional positional arguments (unused).
                **kwargs: The keyword arguments.

            """
            # inspect.stack()[1] is the call frame above us, so this should be reasonable.
            event_handler = inspect.stack()[1].function

            event = kwargs.get('event')

            event_trigger: dict[str, Any] | None = kwargs.get('trigger')

            self.log.debug(
                f'Unhandled Event {event_handler}: '
                f'{self.event_source}->{event} Event Trigger: {event_trigger}',
            )

        def __getattr__(self: Self, attr: str) -> Callable[..., Any]:
            """Get an attribute.

            This method is called when an attribute is not found.

            Args:
                attr: The attribute to get.

            Returns:
                The attribute.

            """
            return self.unhandled_event

    def __init__(self: Self, game: object = None) -> None:
        """Initialize the event manager.

        Args:
            game: The game instance.

        """
        super().__init__(game)
        self.proxies = [EventManager.EventProxy(event_source=self)]
