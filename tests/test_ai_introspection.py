"""Reading a game's objects for the AI: what's read, what never runs, and the JSON it becomes."""

from __future__ import annotations

import enum
import functools
import json
from typing import Any

import pygame
import pytest

from glitchygames.ai_introspection import MAXIMUM_ITEMS, ReadOptions, plain_value, read_object
from glitchygames.game_objects.ball import BallSprite
from glitchygames.tracing import StableSpriteIds


def as_json(value: object) -> Any:
    """Round-trip a result through JSON, which also proves it is JSON.

    Returns:
        What JSON gives back.

    """
    return json.loads(json.dumps(value))


class Mood(enum.Enum):
    """An enum value a game might keep."""

    CALM = 1


class Guarded:
    """Stores values, and has a property that must never run."""

    def __init__(self) -> None:
        """Store a little of everything."""
        self.score = 7
        self.mood = Mood.CALM
        self._private_note = 'hidden'
        self.__mangled = 'never'
        self.handler = self.react
        self.callback = functools.partial(print, 'x')
        self.anonymous = lambda: None

    @property
    def explosive(self) -> int:
        """A property: code, so reading it is forbidden.

        Raises:
            AssertionError: Always, failing any test that reads it.

        """
        message = 'a property ran'
        raise AssertionError(message)

    def react(self) -> None:
        """A method: behaviour, not state."""


class Slotted:
    """Stores its values in slots, and has no __dict__."""

    # __weakref__ is a slot too, but holds no value of the object's own
    __slots__ = ('__weakref__', 'left_empty', 'speed')

    def __init__(self) -> None:
        """Fill one slot only."""
        self.speed = 3.5


class Node:
    """Points at another node, to make cycles."""

    def __init__(self, label: str) -> None:
        """Start pointing at nothing."""
        self.label = label
        self.other: Node | None = None


def test_only_stored_values_are_read_and_no_property_or_method_runs():
    """The property would fail the test if it ran; methods and partials are left out."""
    description = as_json(read_object(value=Guarded()))

    assert description == {'class': 'Guarded', 'score': 7, 'mood': 'CALM'}


def test_private_names_only_when_asked_and_dunders_never():
    """The object's own business stays out unless asked for."""
    description = as_json(read_object(value=Guarded(), options=ReadOptions(include_private=True)))

    assert description['_private_note'] == 'hidden'
    # __mangled is stored as _Guarded__mangled, which looks merely private: it must still stay out
    assert not [name for name in description if 'mangled' in name or name.startswith('__')]


def test_a_mangled_name_from_a_parent_class_stays_out_too():
    """Each class in the hierarchy mangles with its own name."""

    class Child(Guarded):
        """Inherits Guarded's mangled attribute."""

    assert '_Guarded__mangled' not in as_json(
        read_object(value=Child(), options=ReadOptions(include_private=True))
    )


def test_slots_are_read_and_an_empty_slot_is_left_out():
    """An object with no __dict__ is still read, from its slots."""
    assert as_json(read_object(value=Slotted())) == {'class': 'Slotted', 'speed': 3.5}


def test_an_attribute_stored_under_a_dunder_name_stays_out():
    """Even when a game stores one on purpose."""
    guarded = Guarded()
    guarded.__dict__['__note__'] = 'internal'

    assert '__note__' not in as_json(
        read_object(value=guarded, options=ReadOptions(include_private=True))
    )


def test_values_become_json():
    """Rects, colours, surfaces, classes and containers, all JSON-ready."""
    assert as_json(plain_value(value=pygame.Rect(1, 2, 3, 4), depth=1, sprite_ids=None)) == [
        1,
        2,
        3,
        4,
    ]
    assert as_json(plain_value(value=pygame.FRect(1.5, 2, 3, 4), depth=1, sprite_ids=None)) == [
        1.5,
        2,
        3,
        4,
    ]
    assert as_json(plain_value(value=pygame.Color(1, 2, 3), depth=1, sprite_ids=None)) == [
        1,
        2,
        3,
        255,
    ]
    assert as_json(plain_value(value=pygame.Surface((8, 6)), depth=1, sprite_ids=None)) == {
        'surface': [8, 6]
    }
    assert as_json(plain_value(value=Mood, depth=1, sprite_ids=None)) == '<class Mood>'
    assert as_json(plain_value(value=(1, 'two', None), depth=1, sprite_ids=None)) == [
        1,
        'two',
        None,
    ]
    assert as_json(plain_value(value={5: frozenset({True})}, depth=1, sprite_ids=None)) == {
        '5': [True]
    }


def test_long_containers_keep_their_first_items_and_say_how_many_more():
    """So a list of thousands can't flood a prompt."""
    many = list(range(MAXIMUM_ITEMS + 3))
    mapping = {number: number for number in many}

    listed = as_json(plain_value(value=many, depth=1, sprite_ids=None))
    mapped = as_json(plain_value(value=mapping, depth=1, sprite_ids=None))

    assert listed == [*range(MAXIMUM_ITEMS), '... 3 more']
    assert len(mapped) == MAXIMUM_ITEMS + 1
    assert mapped['...'] == '3 more'


def test_nested_objects_expand_to_the_depth_and_are_named_below_it():
    """One level down by default; deeper only when asked."""
    outer = Node('outer')
    outer.other = Node('inner')
    outer.other.other = Node('deepest')

    shallow = as_json(read_object(value=outer, depth=0))
    default = as_json(read_object(value=outer))

    assert shallow['other'] == '<Node>'
    assert default['other'] == {'class': 'Node', 'label': 'inner', 'other': '<Node>'}


def test_a_cycle_ends_at_the_object_met_again():
    """However deep the reading may go."""
    first, second = Node('first'), Node('second')
    first.other, second.other = second, first

    description = as_json(read_object(value=first, depth=50))

    assert description['other'] == {'class': 'Node', 'label': 'second', 'other': '<Node>'}


def test_sprites_are_named_by_their_stable_ids_and_groups_by_their_members():
    """As the AI and recordings name them, never by expanding a whole group."""
    sprite_ids = StableSpriteIds()
    group = pygame.sprite.Group()
    first = pygame.sprite.Sprite(group)
    second = pygame.sprite.Sprite(group)
    holder = Node('holder')
    holder.other = None
    holder.__dict__['group'] = group
    holder.__dict__['favourite'] = second

    description = as_json(read_object(value=holder, depth=0, sprite_ids=sprite_ids))
    expanded = as_json(read_object(value=first, sprite_ids=sprite_ids))

    assert sorted(description['group']) == ['Sprite#0', 'Sprite#1']
    assert description['favourite'] == sprite_ids.id_for(second)
    assert expanded['id'] == sprite_ids.id_for(first)


def test_a_real_ball_shows_its_speed_and_turns_into_json():
    """PaddleSlap's balls keep speed where a description reading velocity_x couldn't see it."""
    ball = BallSprite()
    ball.speed.x, ball.speed.y = -275.0, 137.5

    description = as_json(read_object(value=ball, sprite_ids=StableSpriteIds()))

    assert description['speed']['x'] == pytest.approx(-275.0)
    assert description['speed']['y'] == pytest.approx(137.5)
    assert description['id'] == 'BallSprite#0'
    json.dumps(description)


class Reporting:
    """Has properties a copy of the game may run, and some it may never."""

    def __init__(self) -> None:
        """Store a stored value and some plumbing."""
        self.lives = 3
        self.dirty = 1
        self.hud_font = pygame.font.Font(None, 12)

    @property
    def on_ground(self) -> bool:
        """A property a game might compute."""
        return True

    @property
    def broken(self) -> int:
        """A property that raises.

        Raises:
            ValueError: Always.

        """
        message = 'broken'
        raise ValueError(message)

    @property
    def screenshot(self) -> int:
        """Renders a picture in a real scene: must never run.

        Raises:
            AssertionError: Always, failing any test that runs it.

        """
        message = 'screenshot ran'
        raise AssertionError(message)

    @property
    def _private_total(self) -> int:
        """A private property."""
        return 9

    @property
    def lives_left(self) -> int:
        """A property computed from what's stored."""
        return self.lives


def test_properties_run_only_when_asked_and_a_raising_one_is_named():
    """For the AI's copies of the game; screenshot never, private only when asked."""
    stored_only = as_json(read_object(value=Reporting()))
    with_properties = as_json(
        read_object(value=Reporting(), options=ReadOptions(include_properties=True))
    )
    everything = as_json(
        read_object(
            value=Reporting(), options=ReadOptions(include_properties=True, include_private=True)
        )
    )

    assert stored_only == {'class': 'Reporting', 'lives': 3}
    assert with_properties == {
        'class': 'Reporting',
        'lives': 3,
        'on_ground': True,
        'broken': '<raised ValueError>',
        'lives_left': 3,
    }
    assert everything['_private_total'] == 9
    assert 'screenshot' not in everything


def test_plumbing_fonts_and_sounds_only_when_asked():
    """The game's state is what's left by default."""
    assert as_json(read_object(value=Reporting(), options=ReadOptions(include_engine=True))) == {
        'class': 'Reporting',
        'lives': 3,
        'dirty': 1,
        'hud_font': {'class': 'Font'},
    }


def test_a_real_ball_with_properties_has_its_position_and_no_plumbing():
    """What the tools on the clone read: position from properties, none of the engine's wiring."""
    ball = BallSprite()

    description = as_json(
        read_object(
            value=ball, sprite_ids=StableSpriteIds(), options=ReadOptions(include_properties=True)
        )
    )

    assert {'world_x', 'world_y', 'rect', 'speed', 'visible'} <= set(description)
    assert not {'dirty', 'blendmode', 'proxies', 'screen', 'snd'} & set(description)
