#!/usr/bin/env python3
"""Glitchy Games event module.

This module contains the event substrate for handling
higher level events in the game engine.

Many events are 1:1 with pygame events, but some are
synthesized.  For example, a mouse drop event is
a synthesized event that is triggered by a mouse
button down event followed by a mouse motion event
followed by a mouse button up event.
"""

from __future__ import annotations

import abc
import functools
import inspect
import logging
import re
import sys
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, Self

import pygame

if TYPE_CHECKING:
    from collections.abc import Callable

    from glitchygames.scenes import Scene


LOG: logging.Logger = logging.getLogger('game.events')
LOG.addHandler(logging.NullHandler())


def supported_events(like: str = '.*') -> list:
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
    event_names = (pygame.event.event_name(event_num) for event_num in range(pygame.NUMEVENTS))
    event_names: set[str] = set(event_names) - set('Unknown')

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

    event_list = []

    for event_name in list(event_names):
        # If there's a patched event name, use it, otherwise use event_name
        #
        # This works around a pygame bug for CONTROLLERDEVICEREMAPPED
        patched_event_name = patched_event_names.get(event_name.upper(), event_name)
        LOG.info(f'Adding Event: {patched_event_name}')

        if re.match(like, patched_event_name.upper()):
            event_list.append(getattr(pygame, patched_event_name.upper()))

    return event_list


# Pygame USEREVENTs
FPSEVENT = pygame.USEREVENT + 1
GAMEEVENT = pygame.USEREVENT + 2
MENUEVENT = pygame.USEREVENT + 3

AUDIO_EVENTS = supported_events(like='AUDIO.*?')
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
    - set(CONTROLLER_EVENTS)
    - set(DROP_EVENTS)
    - set(TOUCH_EVENTS)
    - set(JOYSTICK_EVENTS)
    - set(KEYBOARD_EVENTS)
    - set(MIDI_EVENTS)
    - set(MOUSE_EVENTS)
    - set(TEXT_EVENTS)
    - set(WINDOW_EVENTS)
)

GAME_EVENTS.extend([FPSEVENT, GAMEEVENT, MENUEVENT])


def dump_cache_info(func: Callable, *args: list, **kwargs: dict) -> Callable[..., None]:  # noqa: ARG001
    """Dump the cache info for a function."""

    def wrapper(game: Scene, *args: list, **kwargs: dict) -> None:
        cache_info: Any = func.cache_info()
        LOG.debug(f'Cache Info: {func.__name__} {cache_info}')
        func(game, *args, **kwargs)

    return wrapper


@dump_cache_info
@functools.cache
def unhandled_event(game: Scene, event: HashableEvent, *args: list, **kwargs: dict) -> NoReturn:
    """Handle unhandled events.

    This method is called when an event is not handled by
    any of the event handlers.

    This is helpful for us to debug events that we haven't
    implemented yet.

    Args:
        game: The game instance.
        event: The event that wasn't handled.
        *args: The positional arguments.
        **kwargs: The keyword arguments.

    Returns:
        None

    Raises:
        AttributeError: If the event is not handled.
    """
    debug_events: bool | None = game.options.get('debug_events', None)
    no_unhandled_events: bool | None = game.options.get('no_unhandled_events', None)

    if debug_events:
        LOG.error(
            f'Unhandled Event: args: {pygame.event.event_name(event.type)} {event} {args} {kwargs}'
        )
    elif debug_events is None:
        LOG.error(
            'Error: debug_events is missing from the game options. ' "This shouldn't be possible."
        )

    if no_unhandled_events:
        LOG.error(
            f'Unhandled Event: args: {pygame.event.event_name(event.type)} {event} {args} {kwargs}'
        )
        sys.exit(-1)
    elif no_unhandled_events is None:
        LOG.error(
            'Error: no_unhandled_events is missing from the game options. '
            "This shouldn't be possible."
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

    For instance, a second instantiation of MouseManager
    would return the same MouseManager object that the
    GameEngine created to process mouse events with.

    This behavior allows easy access to resource managers
    anywhere in the game without needing an explicit copy
    of the game object, although since GameEngine is also
    a subclass of EventManager, it too is a ResourceManager
    which can be gotten to from anywhere, since it's a singleton.
    """

    log: logging.Logger = LOG

    __instances__: ClassVar = {}

    def __new__(cls: Any, *args: list, **kwargs: dict) -> object:
        """Create a new instance of the class.

        This method is called when a new instance of the class

        Args:
            cls: The class.
            *args: The positional arguments.
            **kwargs: The keyword arguments.

        Returns:
            The new instance of the class.

        Raises:
            AttributeError: If the event is not handled by any proxy.
        """
        if cls not in cls.__instances__:
            cls.__instances__[cls] = object.__new__(cls)
            LOG.debug(f'Created Resource Manager: {cls}')
            cls.__instances__[cls].args = args
            cls.__instances__[cls].kwargs = kwargs

        return cls.__instances__[cls]

    def __init__(self: Self, game: object) -> None:
        """Initialize the resource manager.

        Args:
            game: The game instance.

        Returns:
            None
        """
        super().__init__()
        self.proxies = []

    def __getattr__(self: Self, attr: str) -> Callable:
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
            self.log.exception(f'No proxies for {type(self)}.{attr}')
            raise

        raise AttributeError(f'No proxies for {type(self)}.{attr}')


# Note, we can't subclass HashableEvent because it's a C type.
class HashableEvent(dict):
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

    def __init__(self: Self, type: pygame.event, *args: list, **attributes: dict) -> Self:  # noqa: A002
        """Create a hashable event.

        Pygames events are not hashable by default.

        Args:
            type: The type of the event.
            *args: The positional arguments.
            **attributes: The keyword arguments.
        """
        self.type = type
        self.__dict__.update(attributes)
        self.__hash = hash((self.type, tuple(self.__dict__.keys())))

    @property
    def dict(self: Self) -> dict:
        """Return the dictionary representation of the object."""
        return self.__dict__

    def __setitem__(self: Self, key: str, item: object) -> None:
        """Set an item in the object."""
        self.__dict__[key] = item

    def __getitem__(self: Self, key: str) -> object:
        """Get an item from the object."""
        return self.__dict__[key]

    def __len__(self: Self) -> int:
        """Return the length of the object."""
        return len(self.__dict__)

    def __delitem__(self: Self, key: str) -> NoReturn:
        """Delete an item from the object."""
        del self.__dict__[key]

    def clear(self: Self) -> None:
        """Clear the object."""
        return self.__dict__.clear()

    def copy(self: Self) -> Self:
        """Shallow copy the object."""
        return self.__dict__.copy()

    def has_key(self: Self, k: str) -> bool:
        """Return True if the key is in the object."""
        return k in self.__dict__

    def update(self: Self, *args: list, **kwargs: dict) -> None:
        """Update the object."""
        return self.__dict__.update(*args, **kwargs)

    def keys(self: Self) -> list:
        """Return the keys of the object."""
        return self.__dict__.keys()

    def values(self: Self) -> list:
        """Return the values of the object."""
        return self.__dict__.values()

    def __hash__(self: Self) -> int:
        """Return the hash of the object."""
        return self.__hash

    def __eq__(self: Self, other: Self) -> bool:
        """Return True if the objects are equal."""
        return self.type == other.type and self.__dict__ == other.__dict__

    def __ne__(self: Self, other: Self) -> bool:
        """Return the opposite of __eq__."""
        return not self.__eq__(other)

    def __repr__(self: Self) -> str:
        """Return a string representation of the object."""
        return f'{self.__class__.__name__}({self.__dict__})'

    def __str__(self: Self) -> str:
        """Return a string representation of the object."""
        return f'{self.__class__.__name__}({self.__dict__})'

    def __copy__(self: Self) -> Self:
        """Shallow copy the object."""
        return self.__class__(**self.__dict__)

    def __deepcopy__(self: Self, memo: dict) -> Self:
        """Deep copy the object."""
        return self.__copy__()

    def __reduce__(self: Self) -> tuple:
        """Reduce the object to a picklable form."""
        return (self.__class__, (), self.__dict__)

    def __setstate__(self: Self, state: dict) -> None:
        """Set the state of the object."""
        self.__dict__.update(state)
        self.__hash = hash((self.type, self.__dict__))


# We intentionally don't implement any methods here.
class EventInterface(metaclass=abc.ABCMeta):  # noqa: B024
    """Abstract base class for event interfaces."""

    @classmethod
    def __subclasshook__(cls, subclass: object) -> bool:
        """Override the default __subclasshook__ to create an interface."""
        # Note: This accounts for under/dunder methods in addition to regular methods.
        interface_attributes = set(cls.__abstractmethods__)
        subclass_attributes = set(subclass.__abstractmethods__)

        interface_is_implemented = False
        methods = []
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
        if len(methods) and all(methods):
            interface_is_implemented = all(methods)

        return interface_is_implemented


# Mixin
class AudioEvents(EventInterface):
    """Mixin for audio events."""

    @abc.abstractmethod
    def on_audio_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle audio device added events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # AUDIODEVICEADDED   which, iscapture

    @abc.abstractmethod
    def on_audio_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle audio device removed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # AUDIODEVICEREMOVED which, iscapture


# Mixin
class AudioEventStubs(AudioEvents):
    """Mixin for audio events."""

    @functools.cache
    def on_audio_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle audio device added events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # AUDIODEVICEADDED   which, iscapture
        return unhandled_event(self, event)

    @functools.cache
    def on_audio_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle audio device removed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # AUDIODEVICEREMOVED which, iscapture
        return unhandled_event(self, event)


# Mixin
class ControllerEvents(EventInterface):
    """Mixin for controller events."""

    @abc.abstractmethod
    def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERAXISMOTION joy, axis, value

    @abc.abstractmethod
    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONDOWN joy, button

    @abc.abstractmethod
    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONUP   joy, button

    @abc.abstractmethod
    def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device added events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEADDED device_index, guid

    @abc.abstractmethod
    def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device remapped events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEREMAPPED device_index

    @abc.abstractmethod
    def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device removed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEREMOVED device_index

    @abc.abstractmethod
    def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADDOWN joy, touchpad

    @abc.abstractmethod
    def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADMOTION joy, touchpad

    @abc.abstractmethod
    def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADUP joy, touchpad


class ControllerEventStubs(ControllerEvents):
    """Mixin for controller events."""

    @functools.cache
    def on_controller_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERAXISMOTION joy, axis, value
        unhandled_event(self, event)

    @functools.cache
    def on_controller_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONDOWN joy, button
        unhandled_event(self, event)

    @functools.cache
    def on_controller_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERBUTTONUP   joy, button
        unhandled_event(self, event)

    @functools.cache
    def on_controller_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device added events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEADDED device_index, guid
        unhandled_event(self, event)

    @functools.cache
    def on_controller_device_remapped_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device remapped events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEREMAPPED device_index
        unhandled_event(self, event)

    @functools.cache
    def on_controller_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle controller device removed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERDEVICEREMOVED device_index
        unhandled_event(self, event)

    @functools.cache
    def on_controller_touchpad_down_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADDOWN joy, touchpad
        unhandled_event(self, event)

    @functools.cache
    def on_controller_touchpad_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADMOTION joy, touchpad
        unhandled_event(self, event)

    @functools.cache
    def on_controller_touchpad_up_event(self: Self, event: HashableEvent) -> None:
        """Handle controller touchpad up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # CONTROLLERTOUCHPADUP joy, touchpad
        unhandled_event(self, event)


# Mixin
class DropEvents(EventInterface):
    """Mixin for drop events."""

    @abc.abstractmethod
    def on_drop_begin_event(self: Self, event: HashableEvent) -> None:
        """Handle drop begin event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPBEGIN        none

    @abc.abstractmethod
    def on_drop_file_event(self: Self, event: HashableEvent) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPFILE         file

    @abc.abstractmethod
    def on_drop_text_event(self: Self, event: HashableEvent) -> None:
        """Handle drop text event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPTEXT         text

    @abc.abstractmethod
    def on_drop_complete_event(self: Self, event: HashableEvent) -> None:
        """Handle drop complete event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPCOMPLETE     none


# Mixin
class DropEventStubs(EventInterface):
    """Mixin for drop events."""

    @functools.cache
    def on_drop_begin_event(self: Self, event: HashableEvent) -> None:
        """Handle drop begin event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPBEGIN        none
        unhandled_event(self, event)

    @functools.cache
    def on_drop_file_event(self: Self, event: HashableEvent) -> None:
        """Handle drop file event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPFILE         file
        unhandled_event(self, event)

    @functools.cache
    def on_drop_text_event(self: Self, event: HashableEvent) -> None:
        """Handle drop text event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPTEXT         text
        unhandled_event(self, event)

    @functools.cache
    def on_drop_complete_event(self: Self, event: HashableEvent) -> None:
        """Handle drop complete event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # DROPCOMPLETE     none
        unhandled_event(self, event)


# Mixin
class TouchEvents(EventInterface):
    """Mixin for touch events."""

    @abc.abstractmethod
    def on_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle finger down event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERDOWN       finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle finger motion event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERMOTION     finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle finger up event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERUP         finger_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger down event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERDOWN  touch_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger motion event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERMOTION touch_id, x, y, dx, dy, pressure

    @abc.abstractmethod
    def on_multi_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger up event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERUP    touch_id, x, y, dx, dy, pressure


# Mixin
class TouchEventStubs(EventInterface):
    """Mixin for touch events."""

    @functools.cache
    def on_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle finger down event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERDOWN       finger_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    @functools.cache
    def on_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle finger motion event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERMOTION     finger_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    @functools.cache
    def on_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle finger up event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # FINGERUP         finger_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    @functools.cache
    def on_multi_touch_down_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger down event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERDOWN  touch_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    @functools.cache
    def on_multi_touch_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger motion event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERMOTION touch_id, x, y, dx, dy, pressure
        unhandled_event(self, event)

    @functools.cache
    def on_multi_touch_up_event(self: Self, event: HashableEvent) -> None:
        """Handle multi finger up event.

        Args:
            event: The pygame event.

        Returns:
            None
        """
        # MULTIFINGERUP    touch_id, x, y, dx, dy, pressure
        unhandled_event(self, event)


# Mixin
# TODO: Add a glitchy games event index to allow
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

        Returns:
            None
        """
        # ACTIVEEVENT      gain, state

    @abc.abstractmethod
    def on_fps_event(self: Self, event: HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # FPSEVENT is pygame.USEREVENT + 1

    @abc.abstractmethod
    def on_game_event(self: Self, event: HashableEvent) -> None:
        """Handle game events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # GAMEEVENT is pygame.USEREVENT + 2

    @abc.abstractmethod
    def on_menu_item_event(self: Self, event: HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MENUEVENT is pygame.USEREVENT + 3

    @abc.abstractmethod
    def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # SYSWMEVENT

    @abc.abstractmethod
    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Handle user events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # USEREVENT        code

    @abc.abstractmethod
    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # VIDEOEXPOSE      none

    @abc.abstractmethod
    def on_video_resize_event(self: Self, event: HashableEvent) -> None:
        """Handle video resize events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # VIDEORESIZE      size, w, h

    @abc.abstractmethod
    def on_quit_event(self: Self, event: HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # QUIT             none


class GameEventStubs(EventInterface):
    """Mixin for glitchy game events.

    This includes built-ins like QUIT, and synthesized
    events like FPS and GAME events.

    It's sort of a catch-all for event types that didn't have
    a good home otherwise.
    """

    @functools.cache
    def on_active_event(self: Self, event: HashableEvent) -> None:
        """Handle active events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # ACTIVEEVENT      gain, state
        unhandled_event(self, event)

    @functools.cache
    def on_fps_event(self: Self, event: HashableEvent) -> None:
        """Handle FPS events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # FPSEVENT is pygame.USEREVENT + 1
        unhandled_event(self, event)

    @functools.cache
    def on_game_event(self: Self, event: HashableEvent) -> None:
        """Handle game events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # GAMEEVENT is pygame.USEREVENT + 2
        unhandled_event(self, event)

    @functools.cache
    def on_menu_item_event(self: Self, event: HashableEvent) -> None:
        """Handle menu item events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MENUEVENT is pygame.USEREVENT + 3
        unhandled_event(self, event)

    @functools.cache
    def on_sys_wm_event(self: Self, event: HashableEvent) -> None:
        """Handle sys wm events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # SYSWMEVENT
        unhandled_event(self, event)

    @functools.cache
    def on_user_event(self: Self, event: HashableEvent) -> None:
        """Handle user events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # USEREVENT        code
        unhandled_event(self, event)

    @functools.cache
    def on_video_expose_event(self: Self, event: HashableEvent) -> None:
        """Handle video expose events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # VIDEOEXPOSE      none
        unhandled_event(self, event)

    @functools.cache
    def on_video_resize_event(self: Self, event: HashableEvent) -> None:
        """Handle video resize events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # VIDEORESIZE      size, w, h
        unhandled_event(self, event)

    @functools.cache
    def on_quit_event(self: Self, event: HashableEvent) -> None:
        """Handle quit events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # QUIT             none
        unhandled_event(self, event)


# Mixin
class FontEvents(EventInterface):
    """Mixin for font events."""

    @abc.abstractmethod
    def on_font_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle font changed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # FONTS_CHANGED


# Mixin
class FontEventStubs(EventInterface):
    """Mixin for font events."""

    @functools.cache
    def on_font_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle font changed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # FONTS_CHANGED
        unhandled_event(self, event)


# Mixin
class KeyboardEvents(EventInterface):
    """Mixin for keyboard events."""

    # @abc.abstractmethod
    # def on_key_down_event(self: Self, event: HashableEvent) -> None:
    #     """Handle key down events.

    #     Args:
    #         event (HashableEvent): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # KEYDOWN          unicode, key, mod

    # @abc.abstractmethod
    # def on_key_up_event(self: Self, event: HashableEvent) -> None:
    #     """Handle key up events.

    #     Args:
    #         event (HashableEvent): The event to handle.

    #     Returns:
    #         None
    #     """
    #     # KEYUP            key, mod

    # @abc.abstractmethod
    # def on_key_chord_up_event(self: Self, event: HashableEvent, keys: list) -> None:
    #     """Handle key chord up events.

    #     Args:
    #         event (HashableEvent): The event to handle.
    #         keys (list): The keys in the chord.

    #     Returns:
    #         None
    #     """
    #     # Synthesized event.

    # @abc.abstractmethod
    # def on_key_chord_down_event(self: Self, event: HashableEvent, keys: list) -> None:
    #     """Handle key chord down events.

    #     Args:
    #         event (HashableEvent): The event to handle.
    #         keys (list): The keys in the chord.

    #     Returns:
    #         None
    #     """
    #     # Synthesized event.


# Mixin
class KeyboardEventStubs(EventInterface):
    """Mixin for keyboard events."""

    @functools.cache
    def on_key_down_event(self: Self, event: HashableEvent) -> None:
        """Handle key down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # KEYDOWN          unicode, key, mod
        unhandled_event(self, event)

    @functools.cache
    def on_key_up_event(self: Self, event: HashableEvent) -> None:
        """Handle key up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # KEYUP            key, mod
        unhandled_event(self, event)

    @functools.cache
    def on_key_chord_up_event(self: Self, event: HashableEvent, keys: list) -> None:
        """Handle key chord up events.

        Args:
            event (HashableEvent): The event to handle.
            keys (list): The keys in the chord.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, keys)

    @functools.cache
    def on_key_chord_down_event(self: Self, event: HashableEvent, keys: list) -> None:
        """Handle key chord down events.

        Args:
            event (HashableEvent): The event to handle.
            keys (list): The keys in the chord.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, keys)


# Mixin
class JoystickEvents(EventInterface):
    """Mixin for joystick events."""

    @abc.abstractmethod
    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYAXISMOTION    joy, axis, value

    @abc.abstractmethod
    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONDOWN    joy, button

    @abc.abstractmethod
    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONUP      joy, button

    @abc.abstractmethod
    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick hat motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYHATMOTION     joy, hat, value

    @abc.abstractmethod
    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick ball motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYBALLMOTION    joy, ball, rel

    @abc.abstractmethod
    def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device added events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYDEVICEADDED device_index, guid

    @abc.abstractmethod
    def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device removed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYDEVICEREMOVED device_index


# Mixin
class JoystickEventStubs(EventInterface):
    """Mixin for joystick events."""

    @functools.cache
    def on_joy_axis_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick axis motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYAXISMOTION    joy, axis, value
        unhandled_event(self, event)

    @functools.cache
    def on_joy_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONDOWN    joy, button
        unhandled_event(self, event)

    @functools.cache
    def on_joy_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYBUTTONUP      joy, button
        unhandled_event(self, event)

    @functools.cache
    def on_joy_hat_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick hat motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYHATMOTION     joy, hat, value
        unhandled_event(self, event)

    @functools.cache
    def on_joy_ball_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick ball motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYBALLMOTION    joy, ball, rel
        unhandled_event(self, event)

    @functools.cache
    def on_joy_device_added_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device added events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYDEVICEADDED device_index, guid
        unhandled_event(self, event)

    @functools.cache
    def on_joy_device_removed_event(self: Self, event: HashableEvent) -> None:
        """Handle joystick device removed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # JOYDEVICEREMOVED device_index
        unhandled_event(self, event)


# Mixin
class MidiEvents(EventInterface):
    """Mixin for midi events."""


# Mixin
class MidiEventStubs(EventInterface):
    """Mixin for midi events."""


# Mixin
class MouseEvents(EventInterface):
    """Mixin for mouse events."""

    @abc.abstractmethod
    def on_mouse_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MOUSEMOTION      pos, rel, buttons

    @abc.abstractmethod
    def on_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_left_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_left_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle left mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_middle_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle middle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_middle_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle middle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_right_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle right mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_right_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle right mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
        """Handle mouse focus events.

        Args:
            event (HashableEvent): The event to handle.
            entering_focus (object): The object that is entering focus.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_unfocus_event(self: Self, event: HashableEvent, leaving_focus: object) -> None:
        """Handle mouse unfocus events.

        Args:
            event (HashableEvent): The event to handle.
            leaving_focus (object): The object that is leaving focus.

        Returns:
            None
        """
        # Synthesized event.

    @abc.abstractmethod
    def on_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button

    @abc.abstractmethod
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Left Mouse Button Up pos, button

    @abc.abstractmethod
    def on_middle_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Middle Mouse Button Up pos, button

    @abc.abstractmethod
    def on_right_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Right Mouse Button Up pos, button

    @abc.abstractmethod
    def on_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button

    @abc.abstractmethod
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Left Mouse Button Down pos, button

    @abc.abstractmethod
    def on_middle_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Middle Mouse Button Down pos, button

    @abc.abstractmethod
    def on_right_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Right Mouse Button Down pos, button

    @abc.abstractmethod
    def on_mouse_scroll_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # This is a synthesized event.

    @abc.abstractmethod
    def on_mouse_scroll_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # This is a synthesized event.

    @abc.abstractmethod
    def on_mouse_wheel_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse wheel events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None

        """
        # MOUSEWHEEL flipped, y, x, touch, window


# Mixin
class MouseEventStubs(EventInterface):
    """Mixin for mouse events."""

    @functools.cache
    def on_mouse_motion_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse motion events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MOUSEMOTION      pos, rel, buttons
        unhandled_event(self, event)

    @functools.cache
    def on_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_left_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle left mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_left_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle left mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_middle_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle middle mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_middle_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle middle mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_right_mouse_drag_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle right mouse drag events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_right_mouse_drop_event(self: Self, event: HashableEvent, trigger: object) -> None:
        """Handle right mouse drop events.

        Args:
            event (HashableEvent): The event to handle.
            trigger (object): The object that triggered the event.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, trigger)

    @functools.cache
    def on_mouse_focus_event(self: Self, event: HashableEvent, entering_focus: object) -> None:
        """Handle mouse focus events.

        Args:
            event (HashableEvent): The event to handle.
            entering_focus (object): The object that is entering focus.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, entering_focus)

    @functools.cache
    def on_mouse_unfocus_event(self: Self, event: HashableEvent, leaving_focus: object) -> None:
        """Handle mouse unfocus events.

        Args:
            event (HashableEvent): The event to handle.
            leaving_focus (object): The object that is leaving focus.

        Returns:
            None
        """
        # Synthesized event.
        unhandled_event(self, event, leaving_focus)

    @functools.cache
    def on_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONUP    pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_left_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Left Mouse Button Up pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_middle_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Middle Mouse Button Up pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_right_mouse_button_up_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Right Mouse Button Up pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # MOUSEBUTTONDOWN  pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_left_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle left mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Left Mouse Button Down pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_middle_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle middle mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Middle Mouse Button Down pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_right_mouse_button_down_event(self: Self, event: HashableEvent) -> None:
        """Handle right mouse button down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # Right Mouse Button Down pos, button
        unhandled_event(self, event)

    @functools.cache
    def on_mouse_scroll_down_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll down events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # This is a synthesized event.
        unhandled_event(self, event)

    @functools.cache
    def on_mouse_scroll_up_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse scroll up events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # This is a synthesized event.
        unhandled_event(self, event)

    @functools.cache
    def on_mouse_wheel_event(self: Self, event: HashableEvent) -> None:
        """Handle mouse wheel events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None

        """
        # MOUSEWHEEL flipped, y, x, touch, window
        unhandled_event(self, event)


class TextEvents(EventInterface):
    """Mixin for text events."""

    @abc.abstractmethod
    def on_text_editing_event(self: Self, event: HashableEvent) -> None:
        """Handle text editing events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # TEXTEDITING      text, start, length

    @abc.abstractmethod
    def on_text_input_event(self: Self, event: HashableEvent) -> None:
        """Handle text input events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # TEXTINPUT        text


class TextEventStubs(EventInterface):
    """Mixin for text events."""

    @functools.cache
    def on_text_editing_event(self: Self, event: HashableEvent) -> None:
        """Handle text editing events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # TEXTEDITING      text, start, length
        unhandled_event(self, event)

    @functools.cache
    def on_text_input_event(self: Self, event: HashableEvent) -> None:
        """Handle text input events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # TEXTINPUT        text
        unhandled_event(self, event)


class WindowEvents(EventInterface):
    """Mixin for window events."""

    @abc.abstractmethod
    def on_window_close_event(self: Self, event: HashableEvent) -> None:
        """Handle window close events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWCLOSE      none

    @abc.abstractmethod
    def on_window_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle window enter events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWENTER      none

    @abc.abstractmethod
    def on_window_exposed_event(self: Self, event: HashableEvent) -> None:
        """Handle window exposed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWEXPOSED    none

    @abc.abstractmethod
    def on_window_focus_gained_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSGAINED none

    @abc.abstractmethod
    def on_window_focus_lost_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSLOST  none

    @abc.abstractmethod
    def on_window_hidden_event(self: Self, event: HashableEvent) -> None:
        """Handle window hidden events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWHIDDEN     none

    @abc.abstractmethod
    def on_window_hit_test_event(self: Self, event: HashableEvent) -> None:
        """Handle window hit test events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWHITTEST    none

    @abc.abstractmethod
    def on_window_leave_event(self: Self, event: HashableEvent) -> None:
        """Handle window leave events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWLEAVE      none

    @abc.abstractmethod
    def on_window_maximized_event(self: Self, event: HashableEvent) -> None:
        """Handle window maximized events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWMAXIMIZED  none

    @abc.abstractmethod
    def on_window_minimized_event(self: Self, event: HashableEvent) -> None:
        """Handle window minimized events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWMINIMIZED  none

    @abc.abstractmethod
    def on_window_moved_event(self: Self, event: HashableEvent) -> None:
        """Handle window moved events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWMOVED      none

    @abc.abstractmethod
    def on_window_resized_event(self: Self, event: HashableEvent) -> None:
        """Handle window resized events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWRESIZED    size, w, h

    @abc.abstractmethod
    def on_window_restored_event(self: Self, event: HashableEvent) -> None:
        """Handle window restored events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWRESTORED   none

    @abc.abstractmethod
    def on_window_shown_event(self: Self, event: HashableEvent) -> None:
        """Handle window shown events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWSHOWN      none

    @abc.abstractmethod
    def on_window_size_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle window size changed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWSIZECHANGED size, w, h

    @abc.abstractmethod
    def on_window_take_focus_event(self: Self, event: HashableEvent) -> None:
        """Handle window take focus events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWTAKEFOCUS  none


class WindowEventStubs(EventInterface):
    """Mixin for window events."""

    @functools.cache
    def on_window_close_event(self: Self, event: HashableEvent) -> None:
        """Handle window close events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWCLOSE      none
        unhandled_event(self, event)

    @functools.cache
    def on_window_enter_event(self: Self, event: HashableEvent) -> None:
        """Handle window enter events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWENTER      none
        unhandled_event(self, event)

    @functools.cache
    def on_window_exposed_event(self: Self, event: HashableEvent) -> None:
        """Handle window exposed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWEXPOSED    none
        unhandled_event(self, event)

    @functools.cache
    def on_window_focus_gained_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus gained events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSGAINED none
        unhandled_event(self, event)

    @functools.cache
    def on_window_focus_lost_event(self: Self, event: HashableEvent) -> None:
        """Handle window focus lost events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWFOCUSLOST  none
        unhandled_event(self, event)

    @functools.cache
    def on_window_hidden_event(self: Self, event: HashableEvent) -> None:
        """Handle window hidden events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWHIDDEN     none
        unhandled_event(self, event)

    @functools.cache
    def on_window_hit_test_event(self: Self, event: HashableEvent) -> None:
        """Handle window hit test events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWHITTEST    none
        unhandled_event(self, event)

    @functools.cache
    def on_window_leave_event(self: Self, event: HashableEvent) -> None:
        """Handle window leave events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWLEAVE      none
        unhandled_event(self, event)

    @functools.cache
    def on_window_maximized_event(self: Self, event: HashableEvent) -> None:
        """Handle window maximized events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWMAXIMIZED  none
        unhandled_event(self, event)

    @functools.cache
    def on_window_minimized_event(self: Self, event: HashableEvent) -> None:
        """Handle window minimized events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWMINIMIZED  none
        unhandled_event(self, event)

    @functools.cache
    def on_window_moved_event(self: Self, event: HashableEvent) -> None:
        """Handle window moved events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWMOVED      none
        unhandled_event(self, event)

    @functools.cache
    def on_window_resized_event(self: Self, event: HashableEvent) -> None:
        """Handle window resized events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWRESIZED    size, w, h
        unhandled_event(self, event)

    @functools.cache
    def on_window_restored_event(self: Self, event: HashableEvent) -> None:
        """Handle window restored events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWRESTORED   none
        unhandled_event(self, event)

    @functools.cache
    def on_window_shown_event(self: Self, event: HashableEvent) -> None:
        """Handle window shown events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWSHOWN      none
        unhandled_event(self, event)

    @functools.cache
    def on_window_size_changed_event(self: Self, event: HashableEvent) -> None:
        """Handle window size changed events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWSIZECHANGED size, w, h
        unhandled_event(self, event)

    @functools.cache
    def on_window_take_focus_event(self: Self, event: HashableEvent) -> None:
        """Handle window take focus events.

        Args:
            event (HashableEvent): The event to handle.

        Returns:
            None
        """
        # WINDOWTAKEFOCUS  none
        unhandled_event(self, event)


# Mixin for all events
class AllEvents(
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

    log: logging.Logger = LOG
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

            Returns:
                None
            """
            super().__init__()
            # No proxies for the root class.
            self.proxies = []

            # This is used for leave objects which
            # don't have their own proxies.
            #
            # Subclassed managers that set their own proxy
            # will not have this.
            self.event_source = event_source

        def unhandled_event(self: Self, *args: list, **kwargs: dict) -> None:
            """Handle unhandled events.

            Args:
                *args: The positional arguments.
                **kwargs: The keyword arguments.

            Returns:
                None
            """
            # inspect.stack()[1] is the call frame above us, so this should be reasonable.
            event_handler = inspect.stack()[1].function

            event = kwargs.get('event')

            event_trigger: dict | None = kwargs.get('trigger')

            self.log.debug(
                f'Unhandled Event {event_handler}: '
                f'{self.event_source}->{event} Event Trigger: {event_trigger}'
            )

        def __getattr__(self: Self, attr: str) -> Callable:
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

        Returns:
            None
        """
        super().__init__(game)
        self.proxies = [EventManager.EventProxy(event_source=self)]
