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
from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, NoReturn, Protocol, Self, cast, override

import pygame

if TYPE_CHECKING:
    import builtins
    from collections.abc import Callable, Iterator, KeysView, ValuesView
    from types import MemberDescriptorType

    from glitchygames.tracing import JsonValue


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


def allow_every_event_type(*, native_window_messages: bool) -> None:
    """Allow every event type at SDL, SYSWMEVENT only when the game asked for it.

    SYSWMEVENT carries the window system's raw messages (on x11 every X event: focus, exposure,
    property changes; on Windows each window message), which SDL itself leaves disabled. A plain
    ``pygame.event.set_allowed(None)`` would enable them too, flooding the queue (and every
    recording and instant-replay journal) with messages almost no game reads. A game opts in
    with ``NATIVE_WINDOW_MESSAGES = True`` on its scene class; they then reach
    ``on_sys_wm_event`` as plain ``HashableEvent``s holding pygame's platform fields.

    Blocked through ``pygame.event.set_blocked``, so ``pygame.event.get_blocked`` reports it
    truthfully afterwards: before any pygame call blocks it, pygame-ce 2.5.8 reports SYSWMEVENT
    as allowed while SDL ignores it, and a snapshot-and-restore of the blocked types (the
    replay's input blocking) would then enable it.

    Args:
        native_window_messages: Whether SYSWMEVENT is allowed too.

    """
    pygame.event.set_allowed(None)
    if native_window_messages:
        pygame.event.set_allowed(pygame.SYSWMEVENT)
    else:
        pygame.event.set_blocked(pygame.SYSWMEVENT)


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

    ``__new__`` keeps one instance per subclass: a second
    instantiation of MouseEventManager returns the same object
    that the GameEngine created to process mouse events with
    (GameEngine, an EventManager, is a ResourceManager too).

    It is not a full singleton, though: Python still runs
    ``__init__`` on the shared instance at every instantiation,
    so constructing a manager again re-initializes it with the
    new arguments and resets its state (BUGS.md #198). Keep a
    reference to the manager you were given instead of
    constructing it again.
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

    def __init__(self: Self, game: object) -> None:  # ruff: ignore[unused-method-argument]
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
            self.log.error('No proxies for %s.%s', type(self), attr)  # ruff: ignore[error-instead-of-exception]
            raise

        raise AttributeError(NO_PROXIES_MSG.format(cls=type(self), attr=attr))


def _hashable_value(value: object) -> object:
    """Return value, or a hashable stand-in with the same content when it is unhashable.

    Returns:
        object: The value itself, or tuples and frozensets of its contents.

    """
    try:
        hash(value)
    except TypeError:
        # isinstance narrows to unparameterized ABCs; the items are only hashed, so object
        if isinstance(value, Mapping):
            mapping = cast('Mapping[object, object]', value)
            return frozenset(
                (_hashable_value(key), _hashable_value(item)) for key, item in mapping.items()
            )
        if isinstance(value, AbstractSet):
            members = cast('AbstractSet[object]', value)
            return frozenset(_hashable_value(item) for item in members)
        if isinstance(value, Iterable):
            items = cast('Iterable[object]', value)
            return tuple(_hashable_value(item) for item in items)
        return type(value).__qualname__
    return value


IMMUTABLE_EVENT_MSG = (
    '{cls} is immutable: build a changed copy with with_fields(...) (it cannot {operation})'
)
EVENT_TYPE_CHANGE_MSG = (
    "An event's type cannot change ({old} -> {new}): build a new event of the other type"
)
WRONG_EVENT_CLASS_MSG = '{cls} cannot hold a {event_name} event ({event_type}); use {expected}'


def _refused_class(cls: type[HashableEvent], event_type: int) -> NoReturn:
    """Refuse a per-type class called with a type that has no class of its own.

    Raises:
        ValueError: Always.

    """
    raise ValueError(
        WRONG_EVENT_CLASS_MSG.format(
            cls=cls.__name__,
            event_name=pygame.event.event_name(event_type),
            event_type=event_type,
            expected='HashableEvent',
        )
    )


def _event_class_for(
    *, cls: type[HashableEvent], event_type: int, type_class: type[HashableEvent]
) -> type[HashableEvent]:
    """Return the class to build when ``cls`` (not the base, nor the type's class) is called.

    A family class called with one of its subclasses' types builds the subclass
    (``WindowEvent(pygame.WINDOWMOVED)`` is a ``WindowGeometryEvent``); a game's own subclass
    of the type's class is kept.

    Returns:
        type[HashableEvent]: The class.

    Raises:
        ValueError: If ``cls`` is unrelated to the type's class.

    """
    if issubclass(type_class, cls):
        return type_class
    if issubclass(cls, type_class):
        return cls
    raise ValueError(
        WRONG_EVENT_CLASS_MSG.format(
            cls=cls.__name__,
            event_name=pygame.event.event_name(event_type),
            event_type=event_type,
            expected=type_class.__name__,
        )
    )


# Note, we can't subclass pygame's Event because it's a C type.
class HashableEvent(collections.UserDict[str, Any]):  # ruff: ignore[too-many-public-methods]
    """Hashable, immutable event class.

    Hashable events are cacheable, so we can mitigate some of the
    performance overhead of glitchygames' event subsystem by caching
    events, which will result in an immediate return if an identical
    event is encountered, saving some function overhead and processing.

    Games are welcome to use the built-in pygame event subsystem, but
    on_*_event callbacks will not be available in that case.

    The class is chosen by the event's type: ``HashableEvent(pygame.MOUSEMOTION, ...)`` builds
    a ``MouseMotionEvent`` (``EVENT_CLASSES``), so every event of a type is an instance of
    that type's class however it was built; custom and unknown types stay ``HashableEvent``.
    The per-type classes only declare their fields (for the type checker): they store, hash,
    compare, pickle and serialize exactly as this class does. Equality is by type and fields,
    never by Python class.

    An event never changes after construction (it is hashed, and its hash is cached):
    item and attribute assignment, deletion, ``update``, ``clear``, ``pop``, ``popitem``,
    ``setdefault`` and ``|=`` raise TypeError; ``with_fields(**changes)`` returns a changed
    copy. Field values should be immutable too: a list or dict inside a game event is hashed
    by its contents once, so changing it afterwards leaves the cached hash stale.
    """

    # The cached hash lives in a slot, outside __dict__, so it is never one of the event's
    # fields (iteration, len, dict(), keys(), __eq__, pickling, to_json; BUGS.md #179 was a
    # hash stored in __dict__). None until the first __hash__
    __slots__ = ('_content_hash',)

    # Every event has its type (stored in __dict__ with the fields)
    type: int
    _content_hash: int | None

    def __new__(cls, type: int, *_args: Any, **attributes: Any) -> Self:  # ruff: ignore[builtin-argument-shadowing]
        """Create a hashable event, as the class its type maps to (``EVENT_CLASSES``).

        Pygames events are not hashable by default. All of the construction happens here
        (``__init__`` is object's): one Python call per event, which matters for mouse-motion
        floods. A per-type class called with a type it cannot hold (another family's, or a
        type without a class of its own) raises ValueError.

        Args:
            type: The type of the event.
            *_args: Additional positional arguments (unused).
            **attributes: The event's fields.

        Returns:
            Self: An instance of the type's class: ``HashableEvent`` (or the class called) for
            a type with no class of its own.

        """
        type_class = EVENT_CLASSES.get(type)
        if type_class is None:
            event_class = cls if cls not in _TYPED_EVENT_CLASSES else _refused_class(cls, type)
        elif cls is HashableEvent or cls is type_class:
            event_class = type_class
        else:
            event_class = _event_class_for(cls=cls, event_type=type, type_class=type_class)
        event = object.__new__(event_class)
        # The event's attributes are exactly its type and fields: nothing else is stored in
        # __dict__ (a stored hash there showed up as a field, BUGS.md #179). Written through
        # __dict__ because attribute assignment raises (the event is immutable); the cached
        # hash is None until the first __hash__
        fields = event.__dict__
        fields['type'] = type
        fields.update(attributes)
        _CONTENT_HASH_SLOT.__set__(event, None)
        # event_class is cls or one of its subclasses, so the event is a Self
        return cast('Self', event)

    if TYPE_CHECKING:
        # The constructor's signature for the type checker (UserDict's __init__ takes a
        # mapping); at run time __init__ is object's
        def __init__(self, type: int, *_args: Any, **attributes: Any) -> None:  # ruff: ignore[builtin-argument-shadowing]
            """Declare the constructor's arguments (``__new__`` builds the event)."""

    else:
        # Everything is done in __new__; object's __init__ accepts the constructor's arguments
        # (a class that overrides __new__ but not __init__) and does nothing, without a second
        # Python call per event
        __init__ = object.__init__

    @staticmethod
    def from_pygame(pygame_event: pygame.event.Event) -> HashableEvent:
        """Wrap a pygame event, as its type's class (``EVENT_CLASSES``): the engine's dispatch.

        The same event the constructor builds (``HashableEvent(pygame_event.type,
        **pygame_event.dict)``), without unpacking the fields into keyword arguments twice:
        every dispatched event comes through here, mouse-motion floods included.

        Args:
            pygame_event: The raw event.

        Returns:
            HashableEvent: The event.

        """
        event_type = pygame_event.type
        event = object.__new__(EVENT_CLASSES.get(event_type, HashableEvent))
        fields = event.__dict__
        fields['type'] = event_type
        fields.update(pygame_event.dict)
        _CONTENT_HASH_SLOT.__set__(event, None)
        return event

    @property
    def dict(self: Self) -> Mapping[str, Any]:
        """A read-only view of the event's type and fields (pygame's ``Event.dict``)."""
        return MappingProxyType(self.__dict__)

    def with_fields(self: Self, **changes: object) -> Self:
        """Return a copy of the event with some fields changed or added (the same class).

        Args:
            **changes: The fields to change or add; ``type`` may be given only unchanged.

        Returns:
            Self: The changed copy; this event is left as it was.

        Raises:
            TypeError: If ``changes`` gives the event another type.

        """
        fields: dict[str, object] = {**self.__dict__, **changes}
        new_type = fields.pop('type')
        if new_type != self.type:
            raise TypeError(EVENT_TYPE_CHANGE_MSG.format(old=self.type, new=new_type))
        return self.__class__(self.type, **fields)

    def to_json(self: Self) -> builtins.dict[str, JsonValue]:
        """Describe the event as JSON: ``{"type": <number>, "attributes": {...}}``.

        The attributes are encoded as a recording encodes an event's
        (``glitchygames.recording.json_safe_value``: tuples as lists, lists, dicts, bytes and
        non-finite floats tagged), except that a window reference is written as None, as a
        replay serves one. ``from_json`` reverses it.

        Returns:
            dict[str, JsonValue]: The JSON-safe description (``json.dumps`` accepts it).

        """
        # Deferred: glitchygames.recording imports the sources and input modules, which import
        # the events package
        from glitchygames.recording import (
            EVENT_ATTRIBUTES_FIELD,
            EVENT_TYPE_FIELD,
            json_safe_value,
        )

        attributes: dict[str, JsonValue] = {
            name: json_safe_value(None if isinstance(value, pygame.Window) else value)
            for name, value in self.__dict__.items()
            if name != 'type'
        }
        return {EVENT_TYPE_FIELD: self.type, EVENT_ATTRIBUTES_FIELD: attributes}

    @classmethod
    def from_json(cls, record: Mapping[str, JsonValue]) -> Self:
        """Build an event from ``to_json``'s description (or a recording's event record).

        A recorded window reference (a recording's records hold them) becomes None, as a
        replay serves it. The class is the type's (``EVENT_CLASSES``), as for the constructor.
        A malformed record raises the recording's ``TraceFormatError``
        (``glitchygames.recording.event_from_record``).

        Args:
            record: ``{"type": <number>, "attributes": {...}}``, as read back from JSON.

        Returns:
            Self: The event.

        """
        # Deferred: glitchygames.recording imports the sources and input modules, which import
        # the events package
        from glitchygames.recording import (
            WINDOW_REFERENCE,
            RecordedReference,
            event_from_record,
        )

        pygame_event = event_from_record(dict(record))
        attributes = {
            name: (
                None
                if isinstance(value, RecordedReference) and value.kind == WINDOW_REFERENCE
                else value
            )
            for name, value in pygame_event.dict.items()
        }
        return cls(pygame_event.type, **attributes)

    def _refuse_change(self: Self, operation: str) -> NoReturn:
        """Raise the TypeError every mutator raises.

        Args:
            operation: What the caller tried, for the message.

        Raises:
            TypeError: Always: events are immutable.

        """
        raise TypeError(IMMUTABLE_EVENT_MSG.format(cls=type(self).__name__, operation=operation))

    @override
    def __setattr__(self: Self, name: str, value: object) -> None:
        """Refuse: events are immutable (use ``with_fields``)."""
        self._refuse_change(f'set {name!r}')

    @override
    def __delattr__(self: Self, name: str) -> None:
        """Refuse: events are immutable."""
        self._refuse_change(f'delete {name!r}')

    @override
    def __setitem__(self: Self, key: str, item: object) -> None:
        """Refuse: events are immutable (use ``with_fields``)."""
        self._refuse_change(f'set {key!r}')

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
        """Refuse: events are immutable."""
        self._refuse_change(f'delete {key!r}')

    @override
    def clear(self: Self) -> None:
        """Refuse: events are immutable."""
        self._refuse_change('clear')

    @override
    def pop(self: Self, key: str, default: object = None) -> NoReturn:
        """Refuse: events are immutable."""
        self._refuse_change(f'pop {key!r}')

    @override
    def popitem(self: Self) -> NoReturn:
        """Refuse: events are immutable."""
        self._refuse_change('popitem')

    @override
    def setdefault(self: Self, key: str, default: object = None) -> NoReturn:
        """Refuse: events are immutable (use ``with_fields``)."""
        self._refuse_change(f'setdefault {key!r}')

    @override
    def update(self: Self, *args: object, **kwargs: object) -> None:
        """Refuse: events are immutable (use ``with_fields``)."""
        self._refuse_change('update')

    @override
    def __ior__(self: Self, other: object) -> NoReturn:
        """Refuse: events are immutable (``event | changes`` builds a changed copy)."""
        self._refuse_change('|=')

    @override
    def __or__(self: Self, other: object) -> Self:
        """Return a copy with ``other``'s fields changed or added (``with_fields``).

        UserDict's own ``|`` read ``self.data``, which this class never sets, so it raised
        AttributeError.

        Returns:
            Self: The changed copy, or NotImplemented when ``other`` is not a mapping.

        """
        if not isinstance(other, Mapping):
            return NotImplemented
        changes = cast('Mapping[str, object]', other)
        return self.with_fields(**changes)

    @override
    def __ror__(self: Self, other: object) -> Self:
        """Return a copy with ``other``'s fields added where the event has none.

        Returns:
            Self: The copy (the event's own fields win), or NotImplemented when ``other`` is
            not a mapping.

        """
        if not isinstance(other, Mapping):
            return NotImplemented
        additions = cast('Mapping[str, object]', other)
        return self.with_fields(**{**additions, **self.__dict__})

    @override
    def copy(self: Self) -> Self:
        """Shallow copy the object.

        Returns:
            Self: An equal event of the same class.

        """
        return self.with_fields()

    def has_key(self: Self, key: str) -> bool:
        """Return True if the key is in the object.

        Returns:
            bool: True if has key, False otherwise.

        """
        return key in self.__dict__

    # UserDict's own __contains__, __iter__ and get read self.data, which this class never
    # sets (its items live in __dict__, and an event may have an attribute named `data`), so
    # they raised or answered from the wrong object (BUGS.md #88). Mapping's items() and
    # friends go through __iter__ and __getitem__, so they follow these.
    @override
    def __contains__(self: Self, key: object) -> bool:
        """Return True if the event has the attribute `key`.

        Returns:
            bool: True if the event has the attribute, False otherwise.

        """
        return key in self.__dict__

    @override
    def __iter__(self: Self) -> Iterator[str]:
        """Iterate over the event's attribute names.

        Returns:
            Iterator[str]: The attribute names.

        """
        return iter(self.__dict__)

    @override
    def get(self: Self, key: str, default: Any = None) -> Any:
        """Return the event's attribute `key`, or `default` when it has none.

        Returns:
            Any: The attribute's value, or `default`.

        """
        return self.__dict__.get(key, default)

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

    _hashing_ids: ClassVar[set[int]] = set()

    @override
    def __hash__(self: Self) -> int:
        """Return the hash of the event's content (its type and fields), cached.

        Equal events hash alike however they were built. Unhashable values (a game event's
        lists and dicts) hash by their content. Computed on the first call and kept in a slot
        (never a field); a copy (pickled, ``with_fields``) computes its own.

        Returns:
            int: The hash value.

        """
        content_hash: int | None = self._content_hash
        if content_hash is not None:
            return content_hash
        # Guard against infinite recursion when __dict__ contains this event (as __eq__ does);
        # the inner call's stand-in is never cached
        self_id = id(self)
        if self_id in HashableEvent._hashing_ids:
            return hash(self.type)
        HashableEvent._hashing_ids.add(self_id)
        try:
            content_hash = hash(
                frozenset((name, _hashable_value(value)) for name, value in self.__dict__.items())
            )
        finally:
            HashableEvent._hashing_ids.discard(self_id)
        _CONTENT_HASH_SLOT.__set__(self, content_hash)
        return content_hash

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
        equal = self.__eq__(other)
        # NotImplemented in a boolean context raises TypeError since Python 3.14: hand it back
        # so Python falls back to the reflected comparison, then identity
        if equal is NotImplemented:
            return NotImplemented
        return not equal

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
        return self.with_fields()

    def __deepcopy__(self: Self, memo: builtins.dict[int, Any]) -> Self:
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
        # The type is the one required constructor argument (BUGS.md #121)
        return (self.__class__, (self.type,), self.__getstate__())

    @override
    def __getstate__(self: Self) -> builtins.dict[str, Any]:
        """Return the event's type and fields: the state pickling keeps.

        object's own ``__getstate__`` would add the slots, so the cached hash: a copy never
        carries it (it computes its own).

        Returns:
            dict[str, Any]: A copy of the type and fields.

        """
        return dict(self.__dict__)

    def __setstate__(self: Self, state: builtins.dict[str, Any]) -> None:
        """Set the state of the object.

        The event is rebuilt from the state's attributes exactly as __init__ builds it, so it
        equals and hashes like the event the state came from (BUGS.md #121: this hashed a dict).
        """
        attributes = dict(state)
        event_type = attributes.pop('type')
        # A state pickled before BUGS.md #179 carries the hash it stored as an attribute
        attributes.pop('_HashableEvent__hash', None)
        self.__dict__.clear()
        # Rebuilt as __new__ builds an event; the cached hash (none yet: pickle builds the
        # event just before) is cleared, so the event hashes by the state's content
        fields = self.__dict__
        fields['type'] = event_type
        fields.update(attributes)
        _CONTENT_HASH_SLOT.__set__(self, None)

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


# The slot's descriptor: __init__ and __hash__ write the slot through it, since the event's own
# attribute assignment raises
_CONTENT_HASH_SLOT: MemberDescriptorType = vars(HashableEvent)['_content_hash']


# Per-type event classes. Each only declares the fields pygame-ce gives its types (its
# event.c, dict_from_event, and the pygame.event documentation), for the type checker: no
# behaviour, no slots, so they store, hash, compare and pickle exactly as HashableEvent.
# A field a test or a game leaves out is simply absent (AttributeError when read), and any
# other attribute still reads through HashableEvent.__getattr__.
class KeyEvent(HashableEvent):
    """KEYDOWN and KEYUP."""

    key: int
    mod: int
    scancode: int
    unicode: str
    window: pygame.Window | None


class MouseMotionEvent(HashableEvent):
    """MOUSEMOTION."""

    pos: tuple[int, int]
    rel: tuple[int, int]
    buttons: tuple[int, int, int]
    touch: bool
    window: pygame.Window | None


class MouseButtonEvent(HashableEvent):
    """MOUSEBUTTONDOWN and MOUSEBUTTONUP (buttons 4 and 5 are the old scroll wheel)."""

    pos: tuple[int, int]
    button: int
    touch: bool
    window: pygame.Window | None


class MouseWheelEvent(HashableEvent):
    """MOUSEWHEEL."""

    x: int
    y: int
    flipped: bool
    precise_x: float
    precise_y: float
    touch: bool
    window: pygame.Window | None


class TextInputEvent(HashableEvent):
    """TEXTINPUT."""

    text: str
    window: pygame.Window | None


class TextEditingEvent(HashableEvent):
    """TEXTEDITING."""

    text: str
    start: int
    length: int
    window: pygame.Window | None


class JoyAxisEvent(HashableEvent):
    """JOYAXISMOTION (pygame's deprecated ``joy`` is not declared)."""

    instance_id: int
    axis: int
    value: float


class JoyBallEvent(HashableEvent):
    """JOYBALLMOTION."""

    instance_id: int
    ball: int
    rel: tuple[int, int]


class JoyHatEvent(HashableEvent):
    """JOYHATMOTION."""

    instance_id: int
    hat: int
    value: tuple[int, int]


class JoyButtonEvent(HashableEvent):
    """JOYBUTTONDOWN and JOYBUTTONUP."""

    instance_id: int
    button: int


class JoyDeviceAddedEvent(HashableEvent):
    """JOYDEVICEADDED: names a device index, not an instance id."""

    device_index: int
    guid: str


class JoyDeviceRemovedEvent(HashableEvent):
    """JOYDEVICEREMOVED."""

    instance_id: int


class ControllerAxisEvent(HashableEvent):
    """CONTROLLERAXISMOTION (values on pygame's int scale)."""

    instance_id: int
    axis: int
    value: int


class ControllerButtonEvent(HashableEvent):
    """CONTROLLERBUTTONDOWN and CONTROLLERBUTTONUP."""

    instance_id: int
    button: int


class ControllerDeviceAddedEvent(HashableEvent):
    """CONTROLLERDEVICEADDED: names a device index, not an instance id."""

    device_index: int
    guid: str


class ControllerDeviceEvent(HashableEvent):
    """CONTROLLERDEVICEREMOVED and CONTROLLERDEVICEREMAPPED."""

    instance_id: int


class ControllerTouchpadEvent(HashableEvent):
    """CONTROLLERTOUCHPADDOWN, CONTROLLERTOUCHPADMOTION and CONTROLLERTOUCHPADUP."""

    instance_id: int
    touch_id: int
    finger_id: int
    x: float
    y: float
    pressure: float


class TouchFingerEvent(HashableEvent):
    """FINGERDOWN, FINGERMOTION and FINGERUP (positions normalized to 0-1)."""

    touch_id: int
    finger_id: int
    x: float
    y: float
    dx: float
    dy: float
    pressure: float
    window: pygame.Window | None


class MultiGestureEvent(HashableEvent):
    """MULTIGESTURE."""

    touch_id: int
    x: float
    y: float
    rotated: float
    pinched: float
    num_fingers: int


class WindowEvent(HashableEvent):
    """The WINDOW* events without coordinates (shown, hidden, focus, close, ...)."""

    window: pygame.Window | None


class WindowGeometryEvent(WindowEvent):
    """WINDOWMOVED, WINDOWRESIZED and WINDOWSIZECHANGED: a position or a size."""

    x: int
    y: int


class WindowDisplayChangedEvent(WindowGeometryEvent):
    """WINDOWDISPLAYCHANGED."""

    display_index: int


class DropEvent(HashableEvent):
    """DROPBEGIN and DROPCOMPLETE."""

    window: pygame.Window | None


class DropFileEvent(DropEvent):
    """DROPFILE."""

    file: str


class DropTextEvent(DropEvent):
    """DROPTEXT."""

    text: str


class AudioDeviceEvent(HashableEvent):
    """AUDIODEVICEADDED and AUDIODEVICEREMOVED."""

    which: int
    iscapture: int


class MidiEvent(HashableEvent):
    """MIDIIN and MIDIOUT, as ``pygame.midi.midis2events`` builds them."""

    status: int
    data1: int
    data2: int
    data3: int
    timestamp: int
    vice_id: int


class ActiveEvent(HashableEvent):
    """ACTIVEEVENT (legacy)."""

    gain: int
    state: int


class VideoResizeEvent(HashableEvent):
    """VIDEORESIZE (legacy)."""

    size: tuple[int, int]
    w: int
    h: int


class FpsEvent(HashableEvent):
    """FPSEVENT, posted by ``SceneManager`` with its measured frame rate."""

    fps: float


class GameEvent(HashableEvent):
    """GAMEEVENT (``GameEngine.post_game_event``): a subtype plus the game's own fields."""

    subtype: int


def _classes_by_type(
    event_class: type[HashableEvent], *event_types: int
) -> dict[int, type[HashableEvent]]:
    return dict.fromkeys(event_types, event_class)


# Every event type with a class of its own; any other type (custom types, QUIT, the APP_*
# events, the field-less SDL events) is a plain HashableEvent. HashableEvent.__new__ reads it,
# so every construction site (the engine's dispatch, tests, games) gets the type's class
EVENT_CLASSES: dict[int, type[HashableEvent]] = {
    **_classes_by_type(KeyEvent, pygame.KEYDOWN, pygame.KEYUP),
    **_classes_by_type(MouseMotionEvent, pygame.MOUSEMOTION),
    **_classes_by_type(MouseButtonEvent, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP),
    **_classes_by_type(MouseWheelEvent, pygame.MOUSEWHEEL),
    **_classes_by_type(TextInputEvent, pygame.TEXTINPUT),
    **_classes_by_type(TextEditingEvent, pygame.TEXTEDITING),
    **_classes_by_type(JoyAxisEvent, pygame.JOYAXISMOTION),
    **_classes_by_type(JoyBallEvent, pygame.JOYBALLMOTION),
    **_classes_by_type(JoyHatEvent, pygame.JOYHATMOTION),
    **_classes_by_type(JoyButtonEvent, pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP),
    **_classes_by_type(JoyDeviceAddedEvent, pygame.JOYDEVICEADDED),
    **_classes_by_type(JoyDeviceRemovedEvent, pygame.JOYDEVICEREMOVED),
    **_classes_by_type(ControllerAxisEvent, pygame.CONTROLLERAXISMOTION),
    **_classes_by_type(
        ControllerButtonEvent, pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP
    ),
    **_classes_by_type(ControllerDeviceAddedEvent, pygame.CONTROLLERDEVICEADDED),
    **_classes_by_type(
        ControllerDeviceEvent, pygame.CONTROLLERDEVICEREMOVED, pygame.CONTROLLERDEVICEREMAPPED
    ),
    **_classes_by_type(
        ControllerTouchpadEvent,
        pygame.CONTROLLERTOUCHPADDOWN,
        pygame.CONTROLLERTOUCHPADMOTION,
        pygame.CONTROLLERTOUCHPADUP,
    ),
    **_classes_by_type(TouchFingerEvent, pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP),
    **_classes_by_type(MultiGestureEvent, pygame.MULTIGESTURE),
    **_classes_by_type(
        WindowEvent,
        pygame.WINDOWSHOWN,
        pygame.WINDOWHIDDEN,
        pygame.WINDOWEXPOSED,
        pygame.WINDOWMINIMIZED,
        pygame.WINDOWMAXIMIZED,
        pygame.WINDOWRESTORED,
        pygame.WINDOWENTER,
        pygame.WINDOWLEAVE,
        pygame.WINDOWFOCUSGAINED,
        pygame.WINDOWFOCUSLOST,
        pygame.WINDOWCLOSE,
        pygame.WINDOWTAKEFOCUS,
        pygame.WINDOWHITTEST,
        pygame.WINDOWICCPROFCHANGED,
    ),
    **_classes_by_type(
        WindowGeometryEvent, pygame.WINDOWMOVED, pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED
    ),
    **_classes_by_type(WindowDisplayChangedEvent, pygame.WINDOWDISPLAYCHANGED),
    **_classes_by_type(DropEvent, pygame.DROPBEGIN, pygame.DROPCOMPLETE),
    **_classes_by_type(DropFileEvent, pygame.DROPFILE),
    **_classes_by_type(DropTextEvent, pygame.DROPTEXT),
    **_classes_by_type(AudioDeviceEvent, pygame.AUDIODEVICEADDED, pygame.AUDIODEVICEREMOVED),
    **_classes_by_type(MidiEvent, pygame.MIDIIN, pygame.MIDIOUT),
    **_classes_by_type(ActiveEvent, pygame.ACTIVEEVENT),
    **_classes_by_type(VideoResizeEvent, pygame.VIDEORESIZE),
    **_classes_by_type(FpsEvent, FPSEVENT),
    **_classes_by_type(GameEvent, GAMEEVENT),
}

# The per-type classes: one of them called with a type outside its own is refused
_TYPED_EVENT_CLASSES: frozenset[type[HashableEvent]] = frozenset(EVENT_CLASSES.values())


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

        A class that implements every abstract method of the interface counts as a subclass
        even without inheriting from it. Per the `abc` contract, anything else returns
        NotImplemented rather than False: False would mean "definitely not a subclass" and
        hide real subclasses (every concrete class such as Scene has no abstract methods,
        so the structural check never passes for it).

        Returns:
            bool: True if the subclass implements the interface; otherwise NotImplemented
                (typeshed annotates object.__subclasshook__ as bool and types NotImplemented
                as compatible with it), so the normal inheritance check decides.

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
                    cls.log.debug('%s.%s -> implemented (callable)', subclass.__name__, attribute)
                else:
                    cls.log.debug('%s.%s -> implemented (attribute)', subclass.__name__, attribute)
                methods.append(True)
            else:
                cls.log.debug('%s.%s -> unimplemented', subclass.__name__, attribute)
                methods.append(False)

        # all([]) returns True, so mask it
        #
        # This protects against an empty attribute list
        # which would be a misconfiguration of the interface
        if len(methods) > 0 and all(methods):
            interface_is_implemented = all(methods)

        if interface_is_implemented:
            return True
        return NotImplemented
