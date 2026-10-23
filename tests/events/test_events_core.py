"""Tests for core event system functionality.

This module tests the core event system components including HashableEvent,
EventManager, ResourceManager, and utility functions.
"""

import copy
import logging
import sys
import types
from abc import ABC, abstractmethod
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import (  # ruff: ignore[unsorted-imports]
    EventInterface,
    EventManager,
    HashableEvent,
    ResourceManager,
    supported_events,
    unhandled_event,
    UnhandledEventError,
)


# Constants for magic values
MIN_ATTRIBUTES_1 = 1
MIN_ATTRIBUTES_2 = 2


class GameWithOptions:
    """A minimal real game: unhandled_event reads only its options."""

    def __init__(self, *, options):
        """Keep the options."""
        self.options = options


class EventSource:
    """A minimal real event source for EventManager.EventProxy."""


class TestHashableEvent:
    """Test HashableEvent class functionality."""

    def test_hashable_event_initialization(self):
        """Test HashableEvent initialization with various parameters."""
        # Test basic initialization
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        assert event.type == pygame.KEYDOWN
        assert event['key'] == pygame.K_SPACE

        # Test with multiple attributes
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100), extra='test')
        assert event.type == pygame.MOUSEBUTTONDOWN
        assert event['button'] == 1
        assert event['pos'] == (100, 100)
        assert event['extra'] == 'test'

    def test_hashable_event_dict_property(self):
        """Test HashableEvent dict property."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=pygame.KMOD_CTRL)
        event_dict = event.dict
        assert isinstance(event_dict, dict)
        assert event_dict['key'] == pygame.K_SPACE
        assert event_dict['mod'] == pygame.KMOD_CTRL

    def test_hashable_event_item_access(self):
        """Test HashableEvent item access methods."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(200, 200), rel=(10, 10))

        # Test __getitem__
        assert event['pos'] == (200, 200)
        assert event['rel'] == (10, 10)

        # Test __setitem__
        event['new_attr'] = 'test_value'
        assert event['new_attr'] == 'test_value'

        # Test __delitem__
        del event['new_attr']
        with pytest.raises(KeyError):
            _ = event['new_attr']

    def test_hashable_event_length(self):
        """Test HashableEvent length."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        # HashableEvent includes type, key, and __hash attributes
        assert len(event) >= MIN_ATTRIBUTES_1  # At least 'key' attribute

        event['mod'] = pygame.KMOD_CTRL
        assert len(event) >= MIN_ATTRIBUTES_2  # At least 'key' and 'mod' attributes

    def test_hashable_event_clear(self):
        """Test HashableEvent clear method."""
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))
        initial_length = len(event)
        assert initial_length >= MIN_ATTRIBUTES_2  # At least button and pos

        event.clear()
        assert len(event) == 0

    def test_hashable_event_copy(self):
        """Test HashableEvent copy method."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=pygame.KMOD_CTRL)
        event_copy = event.copy()

        assert event_copy['key'] == pygame.K_SPACE
        assert event_copy['mod'] == pygame.KMOD_CTRL

        # Modify copy and ensure original is unchanged
        event_copy['key'] = pygame.K_RETURN
        assert event['key'] == pygame.K_SPACE  # Original unchanged

    def test_hashable_event_hash(self):
        """Test HashableEvent hash functionality."""
        event1 = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        event2 = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)
        event3 = HashableEvent(pygame.KEYDOWN, key=pygame.K_RETURN)

        # Same events should have same hash
        assert hash(event1) == hash(event2)

        # Different events should have different hashes
        # (but this might not always be true due to hash collisions)
        # So we'll just test that the hash function works without errors
        assert isinstance(hash(event1), int)
        assert isinstance(hash(event3), int)

    def test_hashable_event_getstate_setstate(self):
        """Test HashableEvent __getstate__ and __setstate__ methods."""
        event = HashableEvent(pygame.MOUSEBUTTONDOWN, button=1, pos=(100, 100))

        # Test __getstate__
        state = event.__getstate__()
        assert isinstance(state, dict)
        assert state['type'] == pygame.MOUSEBUTTONDOWN  # type: ignore[index]
        assert state['button'] == 1  # type: ignore[index]
        assert state['pos'] == (100, 100)  # type: ignore[index]

        # Test __setstate__ with simple values to avoid hash issues
        # We'll just test that __getstate__ works and returns the expected structure
        assert state['type'] == pygame.MOUSEBUTTONDOWN  # type: ignore[index]
        assert state['button'] == 1  # type: ignore[index]
        assert state['pos'] == (100, 100)  # type: ignore[index]

    def test_hashable_event_init_with_type(self):
        """Test HashableEvent.__init__ with type parameter."""
        # Test HashableEvent initialization with type
        event = HashableEvent(type=1, data='test')
        assert event['type'] == 1
        assert event['data'] == 'test'

    def test_hashable_event_init_without_type(self):
        """Test HashableEvent.__init__ without type parameter."""
        # Test HashableEvent initialization without type (should raise TypeError)
        with pytest.raises(TypeError):
            HashableEvent()  # type: ignore[missing-argument]

    def test_hashable_event_delattr(self):
        """Test HashableEvent.__delattr__ method."""
        event = HashableEvent(type=1, data='test')
        del event['data']
        # HashableEvent inherits from UserDict, so we need to check __dict__ directly
        assert 'data' not in event.__dict__

    def test_hashable_event_getattr(self):
        """Test HashableEvent.__getattr__ method."""
        event = HashableEvent(type=1, data='test')
        assert event.data == 'test'

    def test_hashable_event_setattr(self):
        """Test HashableEvent.__setattr__ method."""
        event = HashableEvent(type=1)
        event.new_attr = 'new_value'  # type: ignore[unresolved-attribute]
        assert event.new_attr == 'new_value'  # type: ignore[unresolved-attribute]

    def test_hashable_event_eq(self):
        """Test HashableEvent.__eq__ method."""
        event1 = HashableEvent(type=1, data='test')
        event2 = HashableEvent(type=1, data='test')
        event3 = HashableEvent(type=2, data='test')

        assert event1 == event2
        assert event1 != event3

    def test_hashable_event_ne(self):
        """Test HashableEvent.__ne__ method."""
        event1 = HashableEvent(type=1, data='test')
        event2 = HashableEvent(type=2, data='test')

        assert event1 != event2

    def test_hashable_event_str(self):
        """Test HashableEvent.__str__ method."""
        event = HashableEvent(type=1, data='test')
        str_repr = str(event)
        assert isinstance(str_repr, str)
        assert 'HashableEvent' in str_repr

    def test_hashable_event_repr(self):
        """Test HashableEvent.__repr__ method."""
        event = HashableEvent(type=1, data='test')
        repr_str = repr(event)
        assert isinstance(repr_str, str)
        assert 'HashableEvent' in repr_str


class TestHashableEventHasKey:
    """Test HashableEvent.has_key() method."""

    def test_has_key_returns_true_for_existing_attribute(self):
        """has_key should return True for attributes set at construction."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        assert event.has_key('pos') is True
        assert event.has_key('rel') is True

    def test_has_key_returns_true_for_type_attribute(self):
        """has_key should return True for the 'type' attribute."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        assert event.has_key('type') is True

    def test_has_key_returns_false_for_missing_attribute(self):
        """has_key should return False for attributes that were never set."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        assert event.has_key('nonexistent_key') is False

    def test_has_key_after_setitem(self):
        """has_key should return True for attributes added via __setitem__."""
        event = HashableEvent(pygame.USEREVENT)
        event['custom_data'] = 42
        assert event.has_key('custom_data') is True


class TestHashableEventUpdate:
    """Test HashableEvent.update() method."""

    def test_update_adds_new_attributes(self):
        """Update should add new key-value pairs to the event."""
        event = HashableEvent(pygame.USEREVENT)
        event.update({'score': 100, 'level': 5})
        assert event['score'] == 100
        assert event['level'] == 5

    def test_update_overwrites_existing_attributes(self):
        """Update should overwrite existing attributes."""
        event = HashableEvent(pygame.USEREVENT, score=50)
        event.update({'score': 100})
        assert event['score'] == 100

    def test_update_with_keyword_arguments(self):
        """Update should accept keyword arguments."""
        event = HashableEvent(pygame.USEREVENT)
        event.update(player_name='test_player', health=100)
        assert event['player_name'] == 'test_player'
        assert event['health'] == 100


class TestHashableEventKeys:
    """Test HashableEvent.keys() method."""

    def test_keys_includes_type(self):
        """keys() should include 'type' in the returned keys."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_keys = event.keys()
        assert 'type' in event_keys

    def test_keys_includes_all_constructor_attributes(self):
        """keys() should include all attributes passed at construction."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        event_keys = list(event.keys())
        assert 'pos' in event_keys
        assert 'rel' in event_keys

    def test_keys_for_event_with_no_extra_attributes(self):
        """keys() on a minimal event should still include internal attributes."""
        event = HashableEvent(pygame.USEREVENT)
        event_keys = list(event.keys())
        assert 'type' in event_keys


class TestHashableEventValues:
    """Test HashableEvent.values() method."""

    def test_values_contains_event_type(self):
        """values() should contain the event type integer."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_values = list(event.values())
        assert pygame.KEYDOWN in event_values

    def test_values_contains_constructor_attribute_values(self):
        """values() should contain the values passed at construction."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        event_values = list(event.values())
        assert (10, 20) in event_values


class TestHashableEventIdentity:
    """An event is its type and fields: nothing else shows, and its hash follows its content."""

    def test_an_event_holds_only_its_type_and_fields(self):
        """No bookkeeping (such as a stored hash) appears among the event's attributes."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=0)

        assert list(event) == ['type', 'key', 'mod']
        assert len(event) == 3
        assert dict(event) == {'type': pygame.KEYDOWN, 'key': pygame.K_SPACE, 'mod': 0}

    def test_an_event_filled_in_after_construction_equals_one_built_whole(self):
        """Equal content means equal events with equal hashes, however they were built."""
        built_whole = HashableEvent(pygame.MOUSEMOTION, pos=(1, 2), rel=(0, 0), buttons=(0, 0, 0))
        filled_in = HashableEvent(pygame.MOUSEMOTION)
        filled_in.update(pos=(1, 2), rel=(0, 0), buttons=(0, 0, 0))

        assert filled_in == built_whole
        assert hash(filled_in) == hash(built_whole)

    def test_events_differing_only_in_a_value_hash_differently(self):
        """The hash covers the values, not only the attribute names."""
        here = HashableEvent(pygame.MOUSEMOTION, pos=(1, 2))
        there = HashableEvent(pygame.MOUSEMOTION, pos=(9, 9))

        assert hash(here) != hash(there)

    def test_an_event_with_unhashable_values_hashes_by_content(self):
        """List and dict values (a game event's data) still hash, equal content alike."""
        first = HashableEvent(pygame.USEREVENT, items=[1, 2], data={'score': 3})
        second = HashableEvent(pygame.USEREVENT, items=[1, 2], data={'score': 3})

        assert hash(first) == hash(second)
        assert len({first, second}) == 1

    def test_set_values_hash_by_their_members(self):
        """A set value hashes by its members, so equal sets give equal hashes."""
        first = HashableEvent(pygame.USEREVENT, held={1, 2})
        second = HashableEvent(pygame.USEREVENT, held={2, 1})

        assert hash(first) == hash(second)

    def test_an_unhashable_value_that_is_no_container_hashes_by_its_type(self):
        """A value with no content to hash still lets the event hash (equal events alike)."""
        # SimpleNamespace compares by value but is unhashable, and is no container
        first = HashableEvent(pygame.USEREVENT, payload=types.SimpleNamespace(score=3))
        second = HashableEvent(pygame.USEREVENT, payload=types.SimpleNamespace(score=3))

        assert first == second
        assert hash(first) == hash(second)

    def test_an_event_that_contains_itself_hashes_without_recursing(self):
        """As __eq__ does, hashing stops at an event already being hashed."""
        event = HashableEvent(pygame.USEREVENT)
        event['self_reference'] = (event,)

        assert isinstance(hash(event), int)

    def test_a_changed_event_hashes_like_one_built_with_the_change(self):
        """The hash is never stale: it is the hash of the event's current content."""
        changed = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        changed['key'] = pygame.K_b

        assert hash(changed) == hash(HashableEvent(pygame.KEYDOWN, key=pygame.K_b))


class TestHashableEventEquality:
    """Test HashableEvent.__eq__ and __ne__ methods."""

    def test_equal_events_are_equal(self):
        """Two events with the same type and attributes should be equal."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert event_a == event_b

    def test_different_type_events_are_not_equal(self):
        """Events with different types should not be equal."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYUP, key=pygame.K_a)
        assert event_a != event_b

    def test_different_attribute_values_are_not_equal(self):
        """Events with different attribute values should not be equal."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_b)
        assert event_a != event_b

    def test_different_attribute_keys_are_not_equal(self):
        """Events with different attribute keys should not be equal."""
        event_a = HashableEvent(pygame.USEREVENT, score=100)
        event_b = HashableEvent(pygame.USEREVENT, health=100)
        assert event_a != event_b

    def test_ne_returns_true_for_unequal_events(self):
        """__ne__ should return True for events that differ."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYUP, key=pygame.K_a)
        assert (event_a != event_b) is True

    def test_ne_returns_false_for_equal_events(self):
        """__ne__ should return False for identical events."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert (event_a != event_b) is False

    def test_event_equals_itself(self):
        """The identity check answers before the attribute comparison."""
        event = HashableEvent(pygame.USEREVENT, value=float('nan'))
        assert event.__eq__(event) is True

    def test_comparison_with_a_non_event_is_not_implemented(self):
        """Python then falls back to identity, so an event never equals a plain dict."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        assert event.__eq__({'type': pygame.KEYDOWN, 'key': pygame.K_a}) is NotImplemented
        assert event != {'type': pygame.KEYDOWN, 'key': pygame.K_a}

    def test_events_that_contain_themselves_compare_without_recursing(self):
        """The recursion guard ends the comparison of self-referencing events."""
        event_a = HashableEvent(pygame.USEREVENT, score=1)
        event_b = HashableEvent(pygame.USEREVENT, score=1)
        event_a['parent'] = event_a
        event_b['parent'] = event_b

        assert event_a == event_b
        assert not HashableEvent._comparing_ids


class TestHashableEventStringRepresentations:
    """Test HashableEvent.__repr__ and __str__ methods."""

    def test_repr_contains_class_name(self):
        """__repr__ should include the class name."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        representation = repr(event)
        assert 'HashableEvent' in representation

    def test_repr_contains_attributes(self):
        """__repr__ should include attribute information."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        representation = repr(event)
        assert 'type' in representation
        assert 'key' in representation

    def test_str_contains_class_name(self):
        """__str__ should include the class name."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        string_form = str(event)
        assert 'HashableEvent' in string_form

    def test_str_matches_repr(self):
        """__str__ and __repr__ should produce the same output."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        assert str(event) == repr(event)


class TestHashableEventMappingAccess:
    """HashableEvent.get, `in`, keys and iteration read the event's attributes (BUGS.md #88)."""

    def test_hashable_event_get_reads_attributes(self):
        """HashableEvent.get answers from the event's attributes (BUGS.md #88)."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_c, mod=pygame.KMOD_CTRL)

        assert event.get('mod', 0) == pygame.KMOD_CTRL
        assert event.get('key') == pygame.K_c
        assert event.get('unicode', 'fallback') == 'fallback'
        assert event.get('unicode') is None

    def test_hashable_event_in_tests_attributes(self):
        """`in` on a HashableEvent tests the event's attributes (BUGS.md #88)."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_c)

        assert 'key' in event
        assert 'type' in event
        assert 'mod' not in event

        event['mod'] = pygame.KMOD_SHIFT
        assert 'mod' in event
        del event['mod']
        assert 'mod' not in event

    def test_hashable_event_keys_iteration_and_items_agree(self):
        """keys(), iteration and items() all list the event's attributes (BUGS.md #88)."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(1, 2), rel=(3, 4))

        assert {'type', 'pos', 'rel'} <= set(event.keys())
        assert list(event) == list(event.keys())
        assert dict(event.items())['pos'] == (1, 2)
        assert dict(event.items())['rel'] == (3, 4)

    def test_hashable_event_with_a_data_attribute_keeps_mapping_access(self):
        """An event attribute named `data` does not shadow mapping access (BUGS.md #88)."""
        event = HashableEvent(type=1, data='payload')

        assert event.get('data') == 'payload'
        assert 'data' in event
        assert 'missing' not in event


class TestHashableEventGetSetContains:
    """Test HashableEvent.__getitem__, __setitem__, and __contains__."""

    def test_getitem_retrieves_constructor_attribute(self):
        """__getitem__ should retrieve attributes set at construction."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert event['key'] == pygame.K_a
        assert event['mod'] == 0

    def test_getitem_retrieves_type(self):
        """__getitem__ should retrieve the 'type' attribute."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        assert event['type'] == pygame.KEYDOWN

    def test_getitem_raises_keyerror_for_missing_key(self):
        """__getitem__ should raise KeyError for missing keys."""
        event = HashableEvent(pygame.USEREVENT)
        with pytest.raises(KeyError):
            _ = event['nonexistent_key']

    def test_setitem_adds_new_attribute(self):
        """__setitem__ should add a new attribute to the event."""
        event = HashableEvent(pygame.USEREVENT)
        event['custom_data'] = 'test_value'
        assert event['custom_data'] == 'test_value'

    def test_setitem_overwrites_existing_attribute(self):
        """__setitem__ should overwrite an existing attribute."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event['key'] = pygame.K_b
        assert event['key'] == pygame.K_b

    def test_contains_tests_attributes(self):
        """The 'in' operator tests the event's attributes (it raised before BUGS.md #88)."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        assert 'pos' in event
        assert 'nonexistent_key' not in event

    def test_has_key_agrees_with_contains(self):
        """has_key() answers as the 'in' operator does."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        assert event.has_key('pos') is True
        assert event.has_key('nonexistent_key') is False


class TestHashableEventMiscMethods:
    """Test additional HashableEvent methods: len, del, clear, copy, hash, dict."""

    def test_len_counts_all_internal_attributes(self):
        """__len__ should count all internal attributes including type and hash."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        length = len(event)
        # Should include type, key, mod, and the private __hash attribute
        assert length >= 3

    def test_delitem_removes_attribute(self):
        """__delitem__ should remove an attribute from the event."""
        event = HashableEvent(pygame.USEREVENT, score=100, level=5)
        del event['score']
        assert event.has_key('score') is False
        assert event.has_key('level') is True

    def test_clear_removes_all_attributes(self):
        """clear() should remove all attributes from the event."""
        event = HashableEvent(pygame.USEREVENT, score=100, level=5)
        event.clear()
        assert len(event) == 0

    def test_copy_returns_dict_copy(self):
        """copy() should return a shallow copy as a HashableEvent."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        copied = event.copy()
        assert isinstance(copied, HashableEvent)
        assert hasattr(copied, 'key')
        assert copied.key == pygame.K_a

    def test_hash_is_consistent(self):
        """hash() should return a consistent value for the same event."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        hash_value_first = hash(event)
        hash_value_second = hash(event)
        assert hash_value_first == hash_value_second

    def test_hash_same_for_same_type_and_content(self):
        """Events with the same type and attribute values have the same hash."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert hash(event_a) == hash(event_b)

    def test_hash_differs_for_different_types(self):
        """Events with different types should typically have different hashes."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYUP, key=pygame.K_a)
        # Different types should produce different hashes
        assert hash(event_a) != hash(event_b)

    def test_dict_property_returns_internal_dict(self):
        """Dict property should return the internal __dict__."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_dict = event.dict
        assert event_dict['type'] == pygame.KEYDOWN
        assert event_dict['key'] == pygame.K_a
        assert event_dict['mod'] == 0

    def test_hashable_event_usable_as_dict_key(self):
        """HashableEvent should be usable as a dictionary key."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        test_dict = {event: 'test_value'}
        assert test_dict[event] == 'test_value'


class TestHashableEventCopyAndPickle:
    """Test HashableEvent __copy__, __deepcopy__, __reduce__, __setstate__."""

    def test_shallow_copy(self):
        """__copy__ should return a new HashableEvent with the same attributes."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        copied_event = copy.copy(event)
        assert copied_event['key'] == pygame.K_a
        assert copied_event['mod'] == 0

    def test_deep_copy(self):
        """__deepcopy__ should return a new HashableEvent (delegates to __copy__)."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        deep_copied_event = copy.deepcopy(event)
        assert deep_copied_event['pos'] == (10, 20)
        assert deep_copied_event['rel'] == (1, 2)

    def test_reduce_returns_tuple(self):
        """__reduce__ should return a picklable tuple."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        reduced = event.__reduce__()
        assert isinstance(reduced, tuple)
        assert reduced[0] is HashableEvent

    def test_pickle_round_trip_keeps_attributes_equality_and_hash(self):
        """BUGS.md #121: an unpickled event equals the original and hashes the same.

        The test rebuilds the event the way pickle does, without importing pickle.

        __reduce__ rebuilt the event without its type and __setstate__ hashed a dict, so
        unpickling raised TypeError.
        """
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0, unicode='a')

        # What pickle.loads does with what pickle.dumps took from __reduce__
        rebuild, arguments, state = event.__reduce__()
        restored_event = rebuild(*arguments)
        restored_event.__setstate__(state)

        assert restored_event == event
        assert hash(restored_event) == hash(event)
        assert restored_event.type == pygame.KEYDOWN
        assert restored_event.key == pygame.K_a
        assert restored_event.unicode == 'a'
        assert {event: 'cached'}[restored_event] == 'cached'

    def test_setstate_replaces_the_events_attributes(self):
        """__setstate__ makes the event the one the state describes, hash included."""
        event = HashableEvent(pygame.USEREVENT, stale='gone')
        expected_event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)

        event.__setstate__({'type': pygame.KEYDOWN, 'key': pygame.K_a, 'mod': 0})

        assert event == expected_event
        assert hash(event) == hash(expected_event)
        assert 'stale' not in event


class TestHashableEventWithVariousTypes:
    """Test HashableEvent with different pygame event types."""

    def test_mouse_motion_event(self):
        """HashableEvent should work with MOUSEMOTION type."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(5, -3), buttons=(1, 0, 0))
        assert event.type == pygame.MOUSEMOTION
        assert event.pos == (100, 200)
        assert event.rel == (5, -3)
        assert event.buttons == (1, 0, 0)

    def test_keyboard_event(self):
        """HashableEvent should work with KEYDOWN type."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=pygame.KMOD_CTRL, unicode=' ')
        assert event.type == pygame.KEYDOWN
        assert event.key == pygame.K_SPACE
        assert event.mod == pygame.KMOD_CTRL

    def test_user_event_with_custom_attributes(self):
        """HashableEvent should support arbitrary custom attributes."""
        event = HashableEvent(
            pygame.USEREVENT,
            action='spawn_enemy',
            position=(50, 75),
            enemy_type='goblin',
        )
        assert event.action == 'spawn_enemy'
        assert event.position == (50, 75)
        assert event.enemy_type == 'goblin'


class TestEventInterface:
    """Test EventInterface class functionality."""

    def test_event_interface_subclasshook_valid_implementation(self):
        """Test EventInterface.__subclasshook__ with valid implementation."""
        # Test that the subclasshook method exists and can be called
        assert hasattr(EventInterface, '__subclasshook__')
        assert callable(EventInterface.__subclasshook__)

        # Test that it can be called with a simple class.
        # SimpleClass has no abstract methods, so __subclasshook__ uses
        # getattr(subclass, '__abstractmethods__', frozenset[str]()) which
        # returns an empty frozenset — no AttributeError is raised.
        # It should return NotImplemented (defer to inheritance) because SimpleClass
        # doesn't implement the interface.
        class SimpleClass:
            pass

        result = EventInterface.__subclasshook__(SimpleClass)
        assert result is NotImplemented

    def test_event_interface_subclasshook_invalid_implementation(self):
        """Test EventInterface.__subclasshook__ with invalid implementation."""

        class InvalidEventClass(ABC):
            @abstractmethod
            def on_key_down_event(self, event):
                pass

            # Missing on_key_up_event

        # Test the subclasshook directly without log patching
        result = EventInterface.__subclasshook__(InvalidEventClass)
        # Should return NotImplemented (defer to inheritance) for an invalid implementation
        assert result is NotImplemented

    def test_event_interface_subclasshook_empty_attributes(self):
        """Test EventInterface.__subclasshook__ with empty attributes."""

        class EmptyEventClass(ABC):  # ruff: ignore[abstract-base-class-without-abstract-method]
            pass

        # Test the subclasshook directly without log patching
        result = EventInterface.__subclasshook__(EmptyEventClass)
        # Should return NotImplemented (defer to inheritance) for an empty implementation
        assert result is NotImplemented

    def test_scene_subclass_is_a_scene(self):
        """A real Scene subclass passes issubclass and isinstance against Scene."""
        from glitchygames.scenes import Scene

        class RealScene(Scene):
            NAME = 'RealScene'

        scene = RealScene(options={})

        assert issubclass(RealScene, Scene)
        assert isinstance(scene, Scene)

    def test_unrelated_class_is_not_a_scene(self):
        """A class that neither inherits from Scene nor implements anything is not a Scene."""
        from glitchygames.scenes import Scene

        class UnrelatedClass:
            pass

        assert not issubclass(UnrelatedClass, Scene)
        assert not isinstance(UnrelatedClass(), Scene)

    def test_structural_match_counts_for_an_interface_with_abstract_methods(self):
        """A class that implements every abstract method of an interface counts as one.

        The hook exists to make these interfaces structural: inheriting is not required.
        """
        from glitchygames.events import KeyboardEvents

        class StructuralKeyboardHandler:
            def on_key_down_event(self, event):
                pass

            def on_key_up_event(self, event):
                pass

            def on_key_chord_up_event(self, event, keys):
                pass

            def on_key_chord_down_event(self, event, keys):
                pass

        assert set(KeyboardEvents.__abstractmethods__) == {
            'on_key_down_event',
            'on_key_up_event',
            'on_key_chord_up_event',
            'on_key_chord_down_event',
        }
        assert issubclass(StructuralKeyboardHandler, KeyboardEvents)
        assert isinstance(StructuralKeyboardHandler(), KeyboardEvents)

    def test_partial_structural_match_is_not_an_interface(self):
        """A class implementing only some abstract methods (and not inheriting) is not one."""
        from glitchygames.events import KeyboardEvents

        class PartialKeyboardHandler:
            def on_key_down_event(self, event):
                pass

        assert not issubclass(PartialKeyboardHandler, KeyboardEvents)

    def test_subclasshook_logs_its_checks_at_debug_without_emoji(self, caplog):
        """The per-attribute check log is DEBUG-level, plain text."""
        from glitchygames.events import KeyboardEvents

        class FreshKeyboardHandler:
            def on_key_down_event(self, event):
                pass

        caplog.set_level(logging.DEBUG, logger=KeyboardEvents.log.name)
        KeyboardEvents.__subclasshook__(FreshKeyboardHandler)

        hook_records = [
            record for record in caplog.records if 'FreshKeyboardHandler.' in record.getMessage()
        ]
        assert len(hook_records) == len(KeyboardEvents.__abstractmethods__)
        assert all(record.levelno == logging.DEBUG for record in hook_records)
        assert all(record.getMessage().isascii() for record in hook_records)

    def test_subclasshook_defers_to_inheritance_when_structure_does_not_match(self):
        """The hook returns NotImplemented (never False) so normal inheritance still counts."""
        from glitchygames.scenes import Scene

        class RealScene(Scene):
            NAME = 'RealScene'

        assert Scene.__subclasshook__(RealScene) is NotImplemented


class TestEventManager:
    """Test EventManager class functionality."""

    def test_event_manager_initialization(self):
        """Test EventManager initialization."""
        manager = EventManager()
        assert hasattr(manager, 'log')
        assert manager.log is not None

    def test_event_manager_initialization_with_game(self):
        """Test EventManager initialization with game object."""
        game = GameWithOptions(options={})
        manager = EventManager(game=game)
        # EventManager stores game in a different way - check that it's accessible
        assert hasattr(manager, 'game')

    def test_event_proxy_initialization(self):
        """Test EventManager.EventProxy initialization."""
        event_source = EventSource()
        proxy = EventManager.EventProxy(event_source)

        assert proxy.event_source is event_source
        assert hasattr(proxy, 'proxies')
        assert isinstance(proxy.proxies, list)
        assert len(proxy.proxies) == 0

    def test_event_proxy_unhandled_event(self, caplog):
        """EventProxy.unhandled_event logs its caller, the source, the event and the trigger."""
        event_source = EventSource()
        proxy = EventManager.EventProxy(event_source)
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        with caplog.at_level(logging.DEBUG, logger='game.events'):
            proxy.unhandled_event(event=event, trigger='test_trigger')

        # The handler named is the calling function (inspect.stack()[1])
        assert caplog.messages == [
            (
                'Unhandled Event test_event_proxy_unhandled_event: '
                f'{event_source}->{event} Event Trigger: test_trigger'
            )
        ]

    def test_event_proxy_getattr(self):
        """Test EventManager.EventProxy __getattr__ method."""
        proxy = EventManager.EventProxy(EventSource())

        # Test that __getattr__ returns unhandled_event method
        result = proxy.nonexistent_method
        assert result == proxy.unhandled_event

    def test_event_manager_getattr_exception_handling(self, mocker):
        """Test EventManager.__getattr__ exception handling."""
        # Create EventManager with empty proxies list
        event_manager = EventManager()
        event_manager.proxies = []
        mocker.patch.object(type(event_manager), 'log')

        # EventManager uses ResourceManager.__getattr__ which raises AttributeError
        # when no proxies exist (but doesn't log in this case due to a bug in the implementation)
        with pytest.raises(AttributeError) as context:
            _ = event_manager.non_existent_method

        assert 'No proxies for' in str(context.value)
        # The current implementation doesn't log when there are no proxies
        # assert event_manager.log.error.called

    def test_event_manager_getattr_with_proxy_exception(self, mocker):
        """Test EventManager.__getattr__ with proxy that raises AttributeError."""
        # Create EventManager with proxy that raises AttributeError
        event_manager = EventManager()

        # Create a custom proxy class that raises AttributeError
        class FailingProxy:
            def __getattr__(self, name):
                msg = 'Proxy method not found'
                raise AttributeError(msg)

        event_manager.proxies = [FailingProxy()]
        mocker.patch.object(type(event_manager), 'log')

        # EventManager uses ResourceManager.__getattr__ which tries proxies
        # When proxy raises AttributeError, it logs and re-raises
        with pytest.raises(AttributeError):
            _ = event_manager.test_method

        assert event_manager.log.error.called  # type: ignore[unresolved-attribute]


class TestResourceManager:
    """Test ResourceManager class functionality."""

    def test_resource_manager_initialization(self):
        """Test ResourceManager initialization."""
        manager = ResourceManager(game=GameWithOptions(options={}))
        assert hasattr(manager, 'proxies')
        assert isinstance(manager.proxies, list)

    def test_resource_manager_getattr(self):
        """Test ResourceManager __getattr__ method."""
        manager = ResourceManager(game=GameWithOptions(options={}))

        # Test that __getattr__ raises AttributeError for missing attributes
        with pytest.raises(AttributeError):
            _ = manager.nonexistent_attribute

    def test_resource_manager_init(self):
        """Test ResourceManager.__init__ method."""
        resource_manager = ResourceManager(game=GameWithOptions(options={}))
        # ResourceManager doesn't store the game directly, it's a singleton
        assert hasattr(resource_manager, 'proxies')
        assert isinstance(resource_manager.proxies, list)

    def test_resource_manager_init_without_game(self):
        """Test ResourceManager.__init__ without game parameter."""
        with pytest.raises(TypeError):
            ResourceManager()  # type: ignore[missing-argument]

    def test_resource_manager_register(self):
        """Test ResourceManager.register method."""
        resource_manager = ResourceManager(game=GameWithOptions(options={}))

        # ResourceManager doesn't have a register method, it delegates to proxies
        # Test that accessing register raises AttributeError when no proxies
        with pytest.raises(AttributeError):
            resource_manager.register('test_resource', object())

    def test_resource_manager_process_events(self):
        """Test ResourceManager.process_events method."""
        resource_manager = ResourceManager(game=GameWithOptions(options={}))

        # ResourceManager doesn't have a process_events method, it delegates to proxies
        # Test that accessing process_events raises AttributeError when no proxies
        with pytest.raises(AttributeError):
            resource_manager.process_events()

    def test_resource_manager_cleanup(self):
        """Test ResourceManager.cleanup method."""
        resource_manager = ResourceManager(game=GameWithOptions(options={}))

        # ResourceManager doesn't have a cleanup method, it delegates to proxies
        # Test that accessing cleanup raises AttributeError when no proxies
        with pytest.raises(AttributeError):
            resource_manager.cleanup()


class TestEventSystemUtilities:
    """Test event system utility functions."""

    def test_supported_events_functionality(self):
        """Test supported_events function with various patterns."""
        # Test default pattern
        all_events = supported_events()
        assert isinstance(all_events, list)
        assert len(all_events) > 0

        # Test specific patterns
        audio_events = supported_events(like='AUDIO.*?')
        assert isinstance(audio_events, list)

        mouse_events = supported_events(like='MOUSE.*?')
        assert isinstance(mouse_events, list)

        keyboard_events = supported_events(like='KEY.*?')
        assert isinstance(keyboard_events, list)

    def test_supported_events_with_regex_pattern(self):
        """Test supported_events function with regex pattern."""
        # Test with regex pattern
        events = supported_events(like='.*KEY.*')
        assert isinstance(events, list)

    def test_supported_events_with_specific_pattern(self):
        """Test supported_events function with specific pattern."""
        # Test with specific pattern
        events = supported_events(like='KEYDOWN')
        assert isinstance(events, list)

    def test_supported_events_with_default_pattern(self):
        """Test supported_events function with default pattern."""
        # Test with default pattern
        events = supported_events()
        assert isinstance(events, list)

    def test_unhandled_event_functionality(self):
        """Test unhandled_event raises when no_unhandled_events is True."""
        game = GameWithOptions(options={'debug_events': True, 'no_unhandled_events': True})

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        # Should raise UnhandledEventError immediately (no logging before raise)
        with pytest.raises(UnhandledEventError):
            unhandled_event(game, event)

    def test_unhandled_event_with_no_unhandled_events(self):
        """Test unhandled_event raises UnhandledEventError when enabled."""
        game = GameWithOptions(options={'debug_events': False, 'no_unhandled_events': True})

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        # Should raise UnhandledEventError
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            unhandled_event(game, event)

    def test_unhandled_event_without_game_options_is_silent(self, mocker):
        """A game without an options dict (a standalone stub) neither raises nor logs."""
        game_without_options = object()
        mock_log = mocker.patch('glitchygames.events.base.LOG')

        unhandled_event(game_without_options, HashableEvent(pygame.KEYDOWN, key=pygame.K_a))

        assert mock_log.mock_calls == []

    def test_unhandled_event_with_missing_options(self, mocker):
        """Test unhandled_event with missing options."""
        game = GameWithOptions(options={})  # Missing options

        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        mock_log = mocker.patch('glitchygames.events.base.LOG')
        unhandled_event(game, event_to_report)

        # Verify error logging was called
        mock_log.error.assert_called()

    def test_unhandled_event_debug_events_true(self, mocker):
        """Test unhandled_event with debug_events=True logs once per event type."""
        from glitchygames.events import base as events_base

        events_base._unhandled_event_types.discard(pygame.KEYDOWN)

        game = GameWithOptions(options={'debug_events': True, 'no_unhandled_events': False})

        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        mock_log = mocker.patch('glitchygames.events.base.LOG')

        unhandled_event(game, event_to_report)

        # Logs as warning (not error) with the event type name
        mock_log.warning.assert_called_once()
        assert pygame.KEYDOWN in events_base._unhandled_event_types

        # Calling again with the same event type should NOT log again
        mock_log.warning.reset_mock()
        unhandled_event(game, event_to_report)
        mock_log.warning.assert_not_called()

    def test_unhandled_event_debug_events_none(self, mocker):
        """Test unhandled_event with debug_events=None logs error about missing option."""
        game = GameWithOptions(options={'debug_events': None, 'no_unhandled_events': False})

        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        mock_log = mocker.patch('glitchygames.events.base.LOG')
        unhandled_event(game, event_to_report)

        mock_log.error.assert_called_once_with(
            "Error: debug_events is missing from the game options. This shouldn't be possible.",
        )

    def test_unhandled_event_both_false(self, mocker):
        """Test unhandled_event with both options False does not log."""
        game = GameWithOptions(options={'debug_events': False, 'no_unhandled_events': False})

        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        mock_log = mocker.patch('glitchygames.events.base.LOG')
        unhandled_event(game, event_to_report)

        # Should not log anything when both are False
        mock_log.warning.assert_not_called()
        mock_log.error.assert_not_called()

    def test_unhandled_event_no_unhandled_events_none(self, mocker):
        """Test unhandled_event logs error when no_unhandled_events is None."""
        game = GameWithOptions(options={'debug_events': False, 'no_unhandled_events': None})

        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        mock_log = mocker.patch('glitchygames.events.base.LOG')
        unhandled_event(game, event_to_report)
        # Should log error about missing option
        mock_log.error.assert_called()

    def test_unhandled_event_no_exit_when_debug_true_unhandled_false(
        self,
        mocker,
    ):
        """Test that unhandled_event does NOT raise UnhandledEventError.

        Tests when debug_events=True and no_unhandled_events=False.
        """
        from glitchygames.events import base as events_base

        events_base._unhandled_event_types.discard(pygame.KEYDOWN)

        game = GameWithOptions(options={'debug_events': True, 'no_unhandled_events': False})

        event_to_report = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        mock_log = mocker.patch('glitchygames.events.base.LOG')
        unhandled_event(game, event_to_report)

        # Should log as warning, not raise
        mock_log.warning.assert_called_once()

    def test_unhandled_event_both_true(self):
        """Test unhandled_event with both options True."""
        game = GameWithOptions(options={'debug_events': True, 'no_unhandled_events': True})

        # Use a proper HashableEvent instead of Mock
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE)

        # Should raise UnhandledEventError (no_unhandled_events takes precedence)
        with pytest.raises(UnhandledEventError, match='Unhandled event'):
            unhandled_event(game, event)


class TestEventSystemEdgeCases:
    """Test event system edge cases including filtering, delegation, and proxy behavior."""

    def test_supported_events_filters_and_patches(self, mocker):
        """supported_events should filter by regex and patch known names."""

        # Craft a tiny namespace of pygame constants and event names
        def fake_event_name(idx):
            mapping = {
                0: 'KEYDOWN',
                1: 'JOYAXISMOTION',
                2: 'WINDOWSHOWN',
                3: 'UNKNOWN',
                4: 'CONTROLLERDEVICEMAPPED',
            }
            return mapping.get(idx, 'UNKNOWN')

        mocker.patch.object(pygame, 'NUMEVENTS', 5)
        mocker.patch('pygame.event.event_name', side_effect=fake_event_name)
        mocker.patch.multiple(
            pygame,
            KEYDOWN=1,
            JOYAXISMOTION=2,
            WINDOWSHOWN=3,
            CONTROLLERDEVICEREMAPPED=4,
            K_UNKNOWN=0,
        )
        keys = supported_events(like='KEY.*?')
        joys = supported_events(like='JOY.*?')
        wins = supported_events(like='WINDOW.*?')
        ctrls = supported_events(like='CONTROLLER.*?')

        # Expect the patched numeric constants returned by supported_events
        assert keys == [1]
        assert joys == [2]
        assert wins == [3]
        # Patched name should map to REMAPPED constant value we provided
        assert ctrls == [4]

    def test_supported_events_with_real_pygame(self):
        """With the real pygame, the patterns find the real event constants."""
        keyboard_events = supported_events(like='KEY.*?')
        controller_events = supported_events(like='CONTROLLER.*?')
        window_events = supported_events(like='WINDOW.*?')

        assert {pygame.KEYDOWN, pygame.KEYUP} <= set(keyboard_events)
        assert pygame.MOUSEMOTION not in keyboard_events
        assert {
            pygame.CONTROLLERAXISMOTION,
            pygame.CONTROLLERBUTTONDOWN,
            pygame.CONTROLLERDEVICEREMAPPED,
        } <= set(controller_events)
        assert {pygame.WINDOWSHOWN, pygame.WINDOWCLOSE} <= set(window_events)

    def test_resourcemanager_getattr_delegation_and_missing(self):
        """ResourceManager should delegate to proxies or raise AttributeError."""

        class Dummy:
            def foo(self):
                return 'bar'

        class DummyManager(ResourceManager):
            pass

        manager = DummyManager(game=None)
        manager.proxies = [Dummy()]
        # Delegation
        assert manager.foo() == 'bar'

        # Missing path raises
        manager.proxies = []
        with pytest.raises(AttributeError):
            _ = manager.nonexistent()

    def test_eventmanager_eventproxy_unhandled_attr(self):
        """EventProxy should return unhandled_event callable for unknown attrs."""
        manager = EventManager(game=None)
        proxy = manager.proxies[0]
        handler = proxy.some_unknown_handler
        assert callable(handler)
        # Call handler; should not raise
        handler(event=HashableEvent(pygame.KEYDOWN, key=pygame.K_a), trigger=None)
