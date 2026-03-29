#!/usr/bin/env python3
"""Glitchy Games core event foundations.

This module contains the base classes, constants, and utilities
that underpin the event system. All other event modules depend on this.
"""

from __future__ import annotations

import abc
import collections
import logging
import re
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, cast, override

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable, KeysView, ValuesView


class UnhandledEventError(Exception):
    """Raised when an event is not handled by any event handler.

    This exception is raised by the unhandled_event function when
    an event cannot be handled by any of the available event handlers.
    """


LOG: logging.Logger = logging.getLogger('game.events')
LOG.addHandler(logging.NullHandler())

UNHANDLED_EVENT_MSG = 'Unhandled event: {event_name} {event}'
NO_PROXIES_MSG = 'No proxies for {cls}.{attr}'
MISSING_ATTRIBUTE_MSG = "'{cls}' object has no attribute '{attr}'"


def supported_events(like: str = '.*') -> list[int]:
    """Return a list of supported events.

    This method is crucial for allowing the game engine
    to support both older versions of pygame and newer
    versions.  It allows us to enumerate supported pygame
    events and initialize them dynamically.

    This ensures that the game engine will work with
    many versions of pygame.

    We enumerate all pygame event IDs and then use the pygame.event.event_name()
    method to get the event name.  We then use a regular expression to
    match the event name against the like parameter.

    Args:
        like: A regular expression to match against the event names.

    Returns:
        A list of pygame events whose names match the regular expression.

    """
    # Get a list of all of the events
    # by name, but ignore duplicates.
    event_name_generator = (
        pygame.event.event_name(event_num) for event_num in range(pygame.NUMEVENTS)
    )
    event_names: set[str] = set(event_name_generator) - set('Unknown')

    # Pygame 2.5.1 and maybe others have a bug where the event name lookup
    # is wrong.
    #
    # The error is:
    #
    # AttributeError: module 'pygame' has no attribute 'CONTROLLERDEVICEMAPPED'.
    # Did you mean: 'CONTROLLERDEVICEREMAPPED'?
    #
    # This is a workaround for that.
    #
    # The controller documentation also indicates that it should be CONTROLLERDEVICEREMAPPED
    patched_event_names = {
        'APPDIDENTERBACKGROUND': 'APP_DIDENTERBACKGROUND',
        'APPDIDENTERFOREGROUND': 'APP_DIDENTERFOREGROUND',
        'APPLOWMEMORY': 'APP_LOWMEMORY',
        'APPWILLENTERBACKGROUND': 'APP_WILLENTERBACKGROUND',
        'APPWILLENTERFOREGROUND': 'APP_WILLENTERFOREGROUND',
        'APPTERMINATING': 'APP_TERMINATING',
        'CONTROLLERDEVICEMAPPED': 'CONTROLLERDEVICEREMAPPED',
        'RENDERDEVICERESET': 'RENDER_DEVICE_RESET',
        'RENDERTARGETSRESET': 'RENDER_TARGETS_RESET',
        'UNKNOWN': 'K_UNKNOWN',
    }

    event_list: list[int] = []

    for event_name in list(event_names):
        # If there's a patched event name, use it, otherwise use event_name
        #
        # This works around a pygame bug for CONTROLLERDEVICEREMAPPED
        patched_event_name = patched_event_names.get(event_name.upper(), event_name)
        LOG.info('Adding Event: %s', patched_event_name)

        if re.match(like, patched_event_name.upper()):
            event_list.append(getattr(pygame, patched_event_name.upper()))

    return event_list


# Pygame USEREVENTs
FPSEVENT = pygame.USEREVENT + 1
GAMEEVENT = pygame.USEREVENT + 2
MENUEVENT = pygame.USEREVENT + 3

AUDIO_EVENTS = supported_events(like='AUDIO.*?')
APP_EVENTS = supported_events(like='APP.*?')
CONTROLLER_EVENTS = supported_events(like='CONTROLLER.*?')
DROP_EVENTS = supported_events(like='DROP.*?')
TOUCH_EVENTS = supported_events(like='(FINGER|MULTI).*?')
JOYSTICK_EVENTS = supported_events(like='JOY.*?')
KEYBOARD_EVENTS = supported_events(like='KEY.*?')
MIDI_EVENTS = supported_events(like='MIDI.*?')
MOUSE_EVENTS = supported_events(like='MOUSE.*?')
TEXT_EVENTS = supported_events(like='TEXT.*?')
WINDOW_EVENTS = supported_events(like='WINDOW.*?')
ALL_EVENTS = supported_events()
GAME_EVENTS = list(
    set(ALL_EVENTS)
    - set(AUDIO_EVENTS)
    - set(APP_EVENTS)
    - set(CONTROLLER_EVENTS)
    - set(DROP_EVENTS)
    - set(TOUCH_EVENTS)
    - set(JOYSTICK_EVENTS)
    - set(KEYBOARD_EVENTS)
    - set(MIDI_EVENTS)
    - set(MOUSE_EVENTS)
    - set(TEXT_EVENTS)
    - set(WINDOW_EVENTS),
)

GAME_EVENTS.extend([FPSEVENT, GAMEEVENT, MENUEVENT])


class GameOptionsProvider(Protocol):
    """Protocol for objects that provide game options to the event system.

    Satisfied by Scene and all EventStubs mixins at runtime, since they
    inherit options through the ResourceManager/GameEngine chain.
    """

    options: dict[str, Any]


_unhandled_event_types: set[int] = set()


def unhandled_event(
    game: GameOptionsProvider,
    event: HashableEvent,
    *_args: Any,
    **_kwargs: Any,
) -> None:
    """Handle unhandled events.

    This method is called when an event is not handled by
    any of the event handlers.  Each event type is only logged
    once to avoid per-frame log spam.

    This is helpful for us to debug events that we haven't
    implemented yet.

    Args:
        game: The game instance.
        event: The event that wasn't handled.
        *_args: The positional arguments.
        **_kwargs: The keyword arguments.

    Raises:
        UnhandledEventError: If no_unhandled_events is enabled and the event is not handled.

    """
    raw_options = getattr(game, 'options', None)
    if not isinstance(raw_options, dict):
        # No options available (standalone stub without game context) — silently skip
        return

    options: dict[str, Any] = cast('dict[str, Any]', raw_options)
    no_unhandled_events: bool | None = options.get('no_unhandled_events')

    # Always raise if configured to treat unhandled events as errors
    if no_unhandled_events:
        raise UnhandledEventError(
            UNHANDLED_EVENT_MSG.format(
                event_name=pygame.event.event_name(event.type),
                event=event,
            ),
        )
    if no_unhandled_events is None:
        LOG.error(
            'Error: no_unhandled_events is missing from the game options. '
            "This shouldn't be possible.",
        )
        return

    # Log each unhandled event type only once
    debug_events: bool | None = options.get('debug_events')
    if debug_events and event.type not in _unhandled_event_types:
        _unhandled_event_types.add(event.type)
        LOG.warning(
            'Unhandled Event: %s %s',
            pygame.event.event_name(event.type),
            event,
        )
    elif debug_events is None:
        LOG.error(
            "Error: debug_events is missing from the game options. This shouldn't be possible.",
        )


# Interiting from object is default in Python 3.
# Linters complain if you do it.
class ResourceManager:
    """Singleton aggregator base class for event proxies.

    A ResourceManager subclass will generally pass all
    requests through to its proxy object(s), however, for
    certain types of resources such as joysticks, the
    subclass will manage things itself.  This architecture
    reduces code footprint, and allows maxium flexibility
    when needed, at the expense of a bit of abstraction.

    Unless you're implementing a new pygame event manager,
    you probably don't need to worry about this.

    Any subclass of ResourceManager will become
    a singleton class automatically.  This ensures that
    there is only ever a single manager for any given
    resource.

    For instance, a second instantiation of MouseEventManager
    would return the same MouseEventManager object that the
    GameEngine created to process mouse events with.

    This behavior allows easy access to resource managers
    anywhere in the game without needing an explicit copy
    of the game object, although since GameEngine is also
    a subclass of EventManager, it too is a ResourceManager
    which can be gotten to from anywhere, since it's a singleton.
    """

    log: ClassVar[logging.Logger] = LOG

    __instances__: ClassVar[dict[type, Any]] = {}

    def __new__(cls: type[Self], *_args: Any, **_kwargs: Any) -> Self:
        """Create a new instance of the class.

        This method is called when a new instance of the class

        Args:
            cls: The class.
            *_args: The positional arguments.
            **_kwargs: The keyword arguments.

        Returns:
            The new instance of the class.

        """
        if cls not in cls.__instances__:
            cls.__instances__[cls] = object.__new__(cls)
            LOG.debug('Created Resource Manager: %s', cls)
            cls.__instances__[cls].args = _args
            cls.__instances__[cls].kwargs = _kwargs

        return cls.__instances__[cls]

    def __init__(self: Self, game: object) -> None:  # noqa: ARG002
        """Initialize the resource manager.

        Args:
            game: The game instance (accepted for subclass compatibility).

        """
        super().__init__()
        self.proxies: list[Any] = []

    def __getattr__(self: Self, attr: str) -> Callable[..., Any]:
        """Get an attribute.

        This method is called when an attribute is not found.

        Args:
            attr: The attribute to get.

        Returns:
            The attribute.

        Raises:
            AttributeError: If the attribute is not found.

        """
        # Try each proxy in turn
        try:
            for proxy in self.proxies:
                return getattr(proxy, attr)
        except AttributeError:
            self.log.error(f'No proxies for {type(self)}.{attr}')  # noqa: TRY400
            raise

        raise AttributeError(NO_PROXIES_MSG.format(cls=type(self), attr=attr))


# Note, we can't subclass HashableEvent because it's a C type.
class HashableEvent(collections.UserDict[str, Any]):  # noqa: PLR0904
    """Hashable event class.

    Hashable events are cacheable, so we can mitigate some of the
    performance overhead of glitchygames' event subsystem by caching
    events, which will result in an immediate return if an identical
    event is encountered, saving some function overhead and processing.

    Games are welcome to use the built-in pygame event subsystem, but
    on_*_event callbacks will not be available in that case.

    This also allows us to insert metadata into the pygame events
    which allows us to extend them with additional information.
    """

    def __init__(self: Self, type: int, *_args: Any, **attributes: Any) -> None:  # noqa: A002
        """Create a hashable event.

        Pygames events are not hashable by default.

        Args:
            type: The type of the event.
            *_args: Additional positional arguments (unused).
            **attributes: The keyword arguments.

        """
        self.type = type
        self.__dict__.update(attributes)
        self.__hash = hash((self.type, tuple(self.__dict__.keys())))

    @property
    def dict(self: Self) -> dict[str, Any]:  # ty: ignore[invalid-type-form]
        """Return the dictionary representation of the object."""
        return self.__dict__

    @override
    def __setitem__(self: Self, key: str, item: object) -> None:
        """Set an item in the object."""
        self.__dict__[key] = item

    @override
    def __getitem__(self: Self, key: str) -> object:
        """Get an item from the object.

        Returns:
            object: The item at the given index.

        """
        return self.__dict__[key]

    @override
    def __len__(self: Self) -> int:
        """Return the length of the object.

        Returns:
            int: The number of items.

        """
        return len(self.__dict__)

    @override
    def __delitem__(self: Self, key: str) -> None:
        """Delete an item from the object."""
        del self.__dict__[key]

    @override
    def clear(self: Self) -> None:
        """Clear the object."""
        return self.__dict__.clear()

    @override
    def copy(self: Self) -> Self:
        """Shallow copy the object.

        Returns:
            Self: The result.

        """
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        return clone

    def has_key(self: Self, key: str) -> bool:
        """Return True if the key is in the object.

        Returns:
            bool: True if has key, False otherwise.

        """
        return key in self.__dict__

    @override
    def update(self: Self, *args: Any, **kwargs: Any) -> None:
        """Update the object."""
        return self.__dict__.update(*args, **kwargs)

    @override
    def keys(self: Self) -> KeysView[str]:
        """Return the keys of the object.

        Returns:
            KeysView[str]: The result.

        """
        return self.__dict__.keys()

    @override
    def values(self: Self) -> ValuesView[Any]:
        """Return the values of the object.

        Returns:
            ValuesView[Any]: The result.

        """
        return self.__dict__.values()

    @override
    def __hash__(self: Self) -> int:
        """Return the hash of the object.

        Returns:
            int: The hash value.

        """
        return self.__hash

    _comparing_ids: ClassVar[set[int]] = set()

    @override
    def __eq__(self: Self, other: object) -> bool:
        """Return True if the objects are equal.

        Returns:
            bool: The comparison result.

        """
        if self is other:
            return True
        if not isinstance(other, HashableEvent):
            return NotImplemented
        if self.type != other.type:
            return False
        # Guard against infinite recursion when __dict__ contains HashableEvent values
        self_id = id(self)
        if self_id in HashableEvent._comparing_ids:
            return True
        HashableEvent._comparing_ids.add(self_id)
        try:
            return self.__dict__ == other.__dict__
        finally:
            HashableEvent._comparing_ids.discard(self_id)

    @override
    def __ne__(self: Self, other: object) -> bool:
        """Return the opposite of __eq__.

        Returns:
            bool: The comparison result.

        """
        return not self.__eq__(other)

    @override
    def __repr__(self: Self) -> str:
        """Return a string representation of the object.

        Returns:
            str: The string representation.

        """
        return f'{self.__class__.__name__}({self.__dict__})'

    @override
    def __str__(self: Self) -> str:
        """Return a string representation of the object.

        Returns:
            str: The string representation.

        """
        return f'{self.__class__.__name__}({self.__dict__})'

    @override
    def __copy__(self: Self) -> Self:
        """Shallow copy the object.

        Returns:
            Self: The result.

        """
        return self.__class__(**self.__dict__)

    def __deepcopy__(self: Self, memo: dict[int, Any]) -> Self:  # ty: ignore[invalid-type-form]
        """Deep copy the object.

        Returns:
            Self: The result.

        """
        return self.__copy__()

    @override
    def __reduce__(self: Self) -> tuple[Any, ...]:
        """Reduce the object to a picklable form.

        Returns:
            tuple: The result.

        """
        return (self.__class__, (), self.__dict__)

    def __setstate__(self: Self, state: dict[str, Any]) -> None:  # ty: ignore[invalid-type-form]
        """Set the state of the object."""
        self.__dict__.update(state)
        self.__hash = hash((self.type, self.__dict__))

    def __getattr__(self: Self, name: str) -> Any:
        """Allow dynamic attribute access for event fields.

        HashableEvent stores event attributes in __dict__ via the constructor.
        This method satisfies the type checker for dynamic attribute access
        like event.button, event.axis, event.instance_id, etc.

        Args:
            name: The attribute name.

        Raises:
            AttributeError: If the attribute is not found.

        """
        raise AttributeError(MISSING_ATTRIBUTE_MSG.format(cls=type(self).__name__, attr=name))


# We intentionally don't implement any methods here.
class EventInterface(abc.ABC):
    """Abstract base class for event interfaces."""

    log: ClassVar[logging.Logger] = LOG

    # Declared here so EventStubs satisfy GameOptionsProvider when passed to
    # unhandled_event(). At runtime, the concrete class (Scene/GameEngine)
    # provides the real options dict via the ResourceManager singleton chain.
    options: dict[str, Any]

    @classmethod
    @override
    def __subclasshook__(cls, subclass: type[Any]) -> bool:
        """Override the default __subclasshook__ to create an interface.

        Returns:
            bool: True if the condition is met, False otherwise.

        """
        # Note: This accounts for under/dunder methods in addition to regular methods.
        interface_attributes = set(cls.__abstractmethods__)
        abstract_methods = getattr(subclass, '__abstractmethods__', frozenset[str]())
        subclass_attributes: set[str] = set(abstract_methods)

        interface_is_implemented = False
        methods: list[bool] = []
        for attribute in sorted(interface_attributes):
            if hasattr(subclass, attribute) and attribute not in subclass_attributes:
                if callable(getattr(subclass, attribute)):
                    cls.log.info(f'{subclass.__name__}.{attribute} -> ✅ (callable)')
                else:
                    cls.log.info(f'{subclass.__name__}.{attribute} -> ✅ (attribute))')
                methods.append(True)
            else:
                cls.log.info(f'{subclass.__name__}.{attribute} -> ❌ (unimplemented)')
                methods.append(False)

        # all([]) returns True, so mask it
        #
        # This protects against an empty attribute list
        # which would be a misconfiguration of the interface
        if len(methods) > 0 and all(methods):
            interface_is_implemented = all(methods)

        return interface_is_implemented
