"""Read a game's objects for the AI: its state, as JSON, kept small.

The AI's tools (plans/lucid-circuit-4b-mirror.md, "The console's design") read the game through
this, in the mirror's clone and its copies. The rules:

1. Nothing runs unless asked. By default only what an object stores is read: its instance
   ``__dict__`` and the values in its ``__slots__``. A property is code, which could do anything, so
   it runs only with ``ReadOptions.include_properties``, which is for the AI's copies of the game
   (the clone and its copies), never the live game (the owner, 2026-11-07). A property that raises
   reads as ``<raised ErrorName>``. No method is ever called. A game needs nothing to be read.
2. Plumbing is left out unless asked for (``include_engine``): what the engine's sprites and scenes
   set up for drawing, dispatch and running (``ENGINE_PLUMBING``, found on real games' objects), and
   the fonts and sounds a game keeps. What's left is the game's state, which keeps prompts small.
   ``screenshot``, which renders a picture, never runs.
3. Every value becomes JSON: plain values as they are, an Enum by name, a rect as ``[x, y, width,
   height]``, a surface by its size, a colour as its channels. Lists, sets and dictionaries keep
   their first ``MAXIMUM_ITEMS`` and say how many more there were.
4. Nested objects are read to a depth, and below it are named, never expanded: a sprite by its
   stable id (``Ball#3``, from the run's ``tracing.StableSpriteIds``), anything else by its class.
   An object met again inside itself is named, so a cycle ends. A sprite group is its members'
   names, from its own storage; a class is its name. Functions and methods are behaviour, left out.
5. Names starting with ``_`` are the object's own business: left out unless asked for. Dunders and
   name-mangled attributes (``__secret``, stored as ``_Class__secret``) never appear.
"""

from __future__ import annotations

import enum
import functools
import inspect
from typing import TYPE_CHECKING, Any, cast

import pygame
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from glitchygames.tracing import StableSpriteIds

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

MAXIMUM_ITEMS = 20
# What the engine's sprites and scenes set up for drawing, dispatch and running, read from real
# games' objects (PaddleSlap, Clockwork Keep and Mr. Muncher, 2026-11-07)
ENGINE_PLUMBING = frozenset({
    'blendmode',
    'callbacks',
    'collisions',
    'debug_subject',
    'dirty',
    'dt',
    'dt_timer',
    'game_engine',
    'input_devices',
    'next_scene',
    'options',
    'parent',
    'proxies',
    'rects',
    'saves',
    'scene_manager',
    'scene_start',
    'scene_start_capture',
    'screen',
    'screen_height',
    'screen_width',
    'snd',
    'source_rect',
    'timer',
    'tweens',
    'use_gfxdraw',
})
# Renders a picture: never run, even when properties are
NEVER_READ = frozenset({'screenshot'})
# Values a game keeps that mean nothing to the AI
PLUMBING_VALUE_TYPES: tuple[type, ...] = (pygame.font.Font, pygame.mixer.Sound)


class ReadOptions(BaseModel):
    """How much of an object to read."""

    model_config = ConfigDict(frozen=True, extra='forbid')

    # Names starting with _ (never dunders or mangled names)
    include_private: bool = False
    # Run properties: only in the AI's copies of the game, never the live game
    include_properties: bool = False
    # The engine's plumbing, and fonts and sounds
    include_engine: bool = False


DEFAULT_OPTIONS = ReadOptions()


def _rect_value(value: pygame.Rect | pygame.FRect) -> JsonValue:
    return [value.x, value.y, value.width, value.height]


# Values that hold no objects, each with its JSON, checked in order: an Enum before the plain
# types, as an IntEnum is an int too
SCALAR_CONVERSIONS: tuple[tuple[type | tuple[type, ...], Callable[[Any], JsonValue]], ...] = (
    (enum.Enum, lambda value: value.name),
    ((bool, int, float, str, type(None)), lambda value: value),
    (type, lambda value: f'<class {value.__qualname__}>'),
    ((pygame.Rect, pygame.FRect), _rect_value),
    (pygame.Color, list),
    (pygame.Surface, lambda value: {'surface': list(value.get_size())}),
)


def object_name(*, value: object, sprite_ids: StableSpriteIds | None) -> str:
    """Name an object that isn't expanded.

    Args:
        value: The object.
        sprite_ids: The run's sprite ids, or None to name every object by its class.

    Returns:
        A sprite's id, or ``<ClassName>``.

    """
    if sprite_ids is not None and isinstance(value, pygame.sprite.Sprite):
        return sprite_ids.id_for(value)
    return f'<{type(value).__qualname__}>'


def is_hidden_name(*, name: str, owner: type) -> bool:
    """Whether a name is a dunder or a name-mangled private one, which never appear.

    Args:
        name: The attribute's name as stored.
        owner: The object's class, whose hierarchy names the mangled attributes.

    Returns:
        True for ``__x__`` and for ``_Class__x`` of any class it inherits from.

    """
    if name.startswith('__'):
        return True
    return any(name.startswith(f'_{cls.__name__.lstrip("_")}__') for cls in owner.__mro__)


def is_left_out(*, name: str, owner: type, options: ReadOptions) -> bool:
    """Whether a name is left out of a reading, by the module's rules.

    Args:
        name: The attribute's or property's name.
        owner: The object's class.
        options: How much is being read.

    Returns:
        True if it isn't read.

    """
    return (
        is_hidden_name(name=name, owner=owner)
        or (name.startswith('_') and not options.include_private)
        or (name in ENGINE_PLUMBING and not options.include_engine)
    )


def stored_attributes(*, value: object, options: ReadOptions) -> dict[str, object]:
    """Return what an object stores, without running anything of its class.

    Args:
        value: The object.
        options: How much is being read.

    Returns:
        Its instance attributes, then its slot values, by name.

    """
    found: dict[str, object] = dict(getattr(value, '__dict__', {}))
    for cls in type(value).__mro__:
        for name in cls.__dict__.get('__slots__', ()):
            descriptor = cls.__dict__.get(name)
            # Only a slot's own descriptor reads storage; a property of that name would run code
            if not inspect.ismemberdescriptor(descriptor):
                continue
            try:
                found[name] = descriptor.__get__(value, cls)
            except AttributeError:
                # A slot never assigned holds nothing
                continue
    return {
        name: stored
        for name, stored in found.items()
        if not is_left_out(name=name, owner=type(value), options=options)
    }


def property_values(*, value: object, options: ReadOptions) -> dict[str, object]:
    """Run an object's properties, which only the AI's copies of the game may do.

    Args:
        value: The object.
        options: How much is being read.

    Returns:
        Each property's value by name, or ``<raised ErrorName>`` for one that raised.

    """
    found: dict[str, object] = {}
    for cls in type(value).__mro__:
        for name, member in vars(cls).items():
            if (
                not isinstance(member, property)
                or name in found
                or name in NEVER_READ
                or is_left_out(name=name, owner=type(value), options=options)
            ):
                continue
            try:
                found[name] = getattr(value, name)
            except Exception as error:  # ruff: ignore[blind-except] - a game's property may raise anything
                found[name] = f'<raised {type(error).__name__}>'
    return found


def scalar_value(*, value: object) -> tuple[bool, JsonValue]:
    """Turn a value that holds no objects into JSON.

    Returns:
        Whether it was one, and its JSON (None when it wasn't).

    """
    for kinds, conversion in SCALAR_CONVERSIONS:
        if isinstance(value, kinds):
            return True, conversion(value)
    return False, None


def plain_value(
    *,
    value: object,
    depth: int,
    sprite_ids: StableSpriteIds | None,
    options: ReadOptions = DEFAULT_OPTIONS,
    seen: frozenset[int] = frozenset(),
) -> JsonValue:
    """Turn one value into JSON by the module's rules.

    Args:
        value: The value.
        depth: How many levels of nested objects may still be expanded.
        sprite_ids: The run's sprite ids, or None.
        options: How much of nested objects is read.
        seen: The objects being expanded above this one, by ``id``, to end cycles.

    Returns:
        A JSON-ready value.

    """
    is_scalar, scalar = scalar_value(value=value)
    if is_scalar:
        return scalar
    convert = functools.partial(
        plain_value, depth=depth, sprite_ids=sprite_ids, options=options, seen=seen
    )
    if isinstance(value, pygame.sprite.AbstractGroup):
        # Its members, from what it stores (spritedict), never by calling it, and only named
        members: list[object] = list(cast('Iterable[object]', value.spritedict))
        return [object_name(value=member, sprite_ids=sprite_ids) for member in members]
    if isinstance(value, (list, tuple, set, frozenset)):
        items: list[object] = list(cast('Iterable[object]', value))
        converted: list[JsonValue] = [convert(value=item) for item in items[:MAXIMUM_ITEMS]]
        if len(items) > MAXIMUM_ITEMS:
            converted.append(f'... {len(items) - MAXIMUM_ITEMS} more')
        return converted
    if isinstance(value, dict):
        pairs = list(cast('dict[object, object]', value).items())
        mapped = {str(key): convert(value=item) for key, item in pairs[:MAXIMUM_ITEMS]}
        if len(pairs) > MAXIMUM_ITEMS:
            mapped['...'] = f'{len(pairs) - MAXIMUM_ITEMS} more'
        return mapped
    if depth <= 0 or id(value) in seen:
        return object_name(value=value, sprite_ids=sprite_ids)
    return read_object(
        value=value, depth=depth - 1, sprite_ids=sprite_ids, options=options, seen=seen
    )


def read_object(
    *,
    value: object,
    depth: int = 1,
    sprite_ids: StableSpriteIds | None = None,
    options: ReadOptions = DEFAULT_OPTIONS,
    seen: frozenset[int] = frozenset(),
) -> dict[str, JsonValue]:
    """Read an object's state, as JSON, by the module's rules.

    Args:
        value: The object: a sprite, a scene, or anything the game keeps.
        depth: How many levels of nested objects to expand below this one.
        sprite_ids: The run's sprite ids, so sprites are named as the AI and recordings name them.
        options: How much to read: private names, properties (copies only), plumbing.
        seen: The objects being expanded above this one, by ``id``, to end cycles.

    Returns:
        ``class``, a sprite's ``id``, then its state by name: what it stores, then its properties
        when they're read.

    """
    inside = seen | {id(value)}
    description: dict[str, JsonValue] = {'class': type(value).__qualname__}
    if sprite_ids is not None and isinstance(value, pygame.sprite.Sprite):
        description['id'] = sprite_ids.id_for(value)
    state = stored_attributes(value=value, options=options)
    if options.include_properties:
        state |= property_values(value=value, options=options)
    for name, item in state.items():
        if inspect.isroutine(item) or isinstance(item, functools.partial):
            continue
        if isinstance(item, PLUMBING_VALUE_TYPES) and not options.include_engine:
            continue
        description[name] = plain_value(
            value=item, depth=depth, sprite_ids=sprite_ids, options=options, seen=inside
        )
    return description
