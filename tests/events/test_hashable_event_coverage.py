"""Coverage tests for HashableEvent methods in glitchygames/events/core.py.

This module tests HashableEvent's dict-like interface methods, equality,
hashing, string representations, and copy/pickle support.
"""

import sys
from pathlib import Path

import pygame
import pytest

# Add project root so direct imports work in isolated runs
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from glitchygames.events import HashableEvent


class TestHashableEventHasKey:
    """Test HashableEvent.has_key() method."""

    def test_has_key_returns_true_for_existing_attribute(self, mock_pygame_patches):
        """has_key should return True for attributes set at construction."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        assert event.has_key('pos') is True
        assert event.has_key('rel') is True

    def test_has_key_returns_true_for_type_attribute(self, mock_pygame_patches):
        """has_key should return True for the 'type' attribute."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        assert event.has_key('type') is True

    def test_has_key_returns_false_for_missing_attribute(self, mock_pygame_patches):
        """has_key should return False for attributes that were never set."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        assert event.has_key('nonexistent_key') is False

    def test_has_key_after_setitem(self, mock_pygame_patches):
        """has_key should return True for attributes added via __setitem__."""
        event = HashableEvent(pygame.USEREVENT)
        event['custom_data'] = 42
        assert event.has_key('custom_data') is True


class TestHashableEventUpdate:
    """Test HashableEvent.update() method."""

    def test_update_adds_new_attributes(self, mock_pygame_patches):
        """Update should add new key-value pairs to the event."""
        event = HashableEvent(pygame.USEREVENT)
        event.update({'score': 100, 'level': 5})
        assert event['score'] == 100
        assert event['level'] == 5

    def test_update_overwrites_existing_attributes(self, mock_pygame_patches):
        """Update should overwrite existing attributes."""
        event = HashableEvent(pygame.USEREVENT, score=50)
        event.update({'score': 100})
        assert event['score'] == 100

    def test_update_with_keyword_arguments(self, mock_pygame_patches):
        """Update should accept keyword arguments."""
        event = HashableEvent(pygame.USEREVENT)
        event.update(player_name='test_player', health=100)
        assert event['player_name'] == 'test_player'
        assert event['health'] == 100


class TestHashableEventKeys:
    """Test HashableEvent.keys() method."""

    def test_keys_includes_type(self, mock_pygame_patches):
        """keys() should include 'type' in the returned keys."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_keys = event.keys()
        assert 'type' in event_keys

    def test_keys_includes_all_constructor_attributes(self, mock_pygame_patches):
        """keys() should include all attributes passed at construction."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        event_keys = list(event.keys())
        assert 'pos' in event_keys
        assert 'rel' in event_keys

    def test_keys_for_event_with_no_extra_attributes(self, mock_pygame_patches):
        """keys() on a minimal event should still include internal attributes."""
        event = HashableEvent(pygame.USEREVENT)
        event_keys = list(event.keys())
        assert 'type' in event_keys


class TestHashableEventValues:
    """Test HashableEvent.values() method."""

    def test_values_contains_event_type(self, mock_pygame_patches):
        """values() should contain the event type integer."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_values = list(event.values())
        assert pygame.KEYDOWN in event_values

    def test_values_contains_constructor_attribute_values(self, mock_pygame_patches):
        """values() should contain the values passed at construction."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        event_values = list(event.values())
        assert (10, 20) in event_values


class TestHashableEventEquality:
    """Test HashableEvent.__eq__ and __ne__ methods."""

    def test_equal_events_are_equal(self, mock_pygame_patches):
        """Two events with the same type and attributes should be equal."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert event_a == event_b

    def test_different_type_events_are_not_equal(self, mock_pygame_patches):
        """Events with different types should not be equal."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYUP, key=pygame.K_a)
        assert event_a != event_b

    def test_different_attribute_values_are_not_equal(self, mock_pygame_patches):
        """Events with different attribute values should not be equal."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_b)
        assert event_a != event_b

    def test_different_attribute_keys_are_not_equal(self, mock_pygame_patches):
        """Events with different attribute keys should not be equal."""
        event_a = HashableEvent(pygame.USEREVENT, score=100)
        event_b = HashableEvent(pygame.USEREVENT, health=100)
        assert event_a != event_b

    def test_ne_returns_true_for_unequal_events(self, mock_pygame_patches):
        """__ne__ should return True for events that differ."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYUP, key=pygame.K_a)
        assert (event_a != event_b) is True

    def test_ne_returns_false_for_equal_events(self, mock_pygame_patches):
        """__ne__ should return False for identical events."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert (event_a != event_b) is False


class TestHashableEventStringRepresentations:
    """Test HashableEvent.__repr__ and __str__ methods."""

    def test_repr_contains_class_name(self, mock_pygame_patches):
        """__repr__ should include the class name."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        representation = repr(event)
        assert 'HashableEvent' in representation

    def test_repr_contains_attributes(self, mock_pygame_patches):
        """__repr__ should include attribute information."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        representation = repr(event)
        assert 'type' in representation
        assert 'key' in representation

    def test_str_contains_class_name(self, mock_pygame_patches):
        """__str__ should include the class name."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        string_form = str(event)
        assert 'HashableEvent' in string_form

    def test_str_matches_repr(self, mock_pygame_patches):
        """__str__ and __repr__ should produce the same output."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        assert str(event) == repr(event)


class TestHashableEventGetSetContains:
    """Test HashableEvent.__getitem__, __setitem__, and __contains__."""

    def test_getitem_retrieves_constructor_attribute(self, mock_pygame_patches):
        """__getitem__ should retrieve attributes set at construction."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        assert event['key'] == pygame.K_a
        assert event['mod'] == 0

    def test_getitem_retrieves_type(self, mock_pygame_patches):
        """__getitem__ should retrieve the 'type' attribute."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        assert event['type'] == pygame.KEYDOWN

    def test_getitem_raises_keyerror_for_missing_key(self, mock_pygame_patches):
        """__getitem__ should raise KeyError for missing keys."""
        event = HashableEvent(pygame.USEREVENT)
        with pytest.raises(KeyError):
            _ = event['nonexistent_key']

    def test_setitem_adds_new_attribute(self, mock_pygame_patches):
        """__setitem__ should add a new attribute to the event."""
        event = HashableEvent(pygame.USEREVENT)
        event['custom_data'] = 'test_value'
        assert event['custom_data'] == 'test_value'

    def test_setitem_overwrites_existing_attribute(self, mock_pygame_patches):
        """__setitem__ should overwrite an existing attribute."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event['key'] = pygame.K_b
        assert event['key'] == pygame.K_b

    def test_contains_raises_attribute_error(self, mock_pygame_patches):
        """'in' operator raises AttributeError because UserDict.data is never initialized.

        BUG: HashableEvent extends UserDict but never calls super().__init__(),
        so the inherited __contains__ method fails when trying to access self.data.
        Use has_key() as a workaround.
        """
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        with pytest.raises(AttributeError):
            _ = 'pos' in event

    def test_has_key_workaround_for_contains(self, mock_pygame_patches):
        """has_key() works as a substitute for the broken 'in' operator."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20))
        assert event.has_key('pos') is True
        assert event.has_key('nonexistent_key') is False


class TestHashableEventMiscMethods:
    """Test additional HashableEvent methods: len, del, clear, copy, hash, dict."""

    def test_len_counts_all_internal_attributes(self, mock_pygame_patches):
        """__len__ should count all internal attributes including type and hash."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        length = len(event)
        # Should include type, key, mod, and the private __hash attribute
        assert length >= 3

    def test_delitem_removes_attribute(self, mock_pygame_patches):
        """__delitem__ should remove an attribute from the event."""
        event = HashableEvent(pygame.USEREVENT, score=100, level=5)
        del event['score']
        assert event.has_key('score') is False
        assert event.has_key('level') is True

    def test_clear_removes_all_attributes(self, mock_pygame_patches):
        """clear() should remove all attributes from the event."""
        event = HashableEvent(pygame.USEREVENT, score=100, level=5)
        event.clear()
        assert len(event) == 0

    def test_copy_returns_dict_copy(self, mock_pygame_patches):
        """copy() should return a shallow copy as a HashableEvent."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        copied = event.copy()
        assert isinstance(copied, HashableEvent)
        assert hasattr(copied, 'key')
        assert copied.key == pygame.K_a

    def test_hash_is_consistent(self, mock_pygame_patches):
        """hash() should return a consistent value for the same event."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        hash_value_first = hash(event)
        hash_value_second = hash(event)
        assert hash_value_first == hash_value_second

    def test_hash_same_for_same_type_and_keys(self, mock_pygame_patches):
        """Events with the same type and attribute keys should have the same hash."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_b = HashableEvent(pygame.KEYDOWN, key=pygame.K_b, mod=1)
        assert hash(event_a) == hash(event_b)

    def test_hash_differs_for_different_types(self, mock_pygame_patches):
        """Events with different types should typically have different hashes."""
        event_a = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        event_b = HashableEvent(pygame.KEYUP, key=pygame.K_a)
        # Different types should produce different hashes
        assert hash(event_a) != hash(event_b)

    def test_dict_property_returns_internal_dict(self, mock_pygame_patches):
        """Dict property should return the internal __dict__."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        event_dict = event.dict
        assert event_dict['type'] == pygame.KEYDOWN
        assert event_dict['key'] == pygame.K_a
        assert event_dict['mod'] == 0

    def test_hashable_event_usable_as_dict_key(self, mock_pygame_patches):
        """HashableEvent should be usable as a dictionary key."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        test_dict = {event: 'test_value'}
        assert test_dict[event] == 'test_value'


class TestHashableEventCopyAndPickle:
    """Test HashableEvent __copy__, __deepcopy__, __reduce__, __setstate__."""

    def test_shallow_copy(self, mock_pygame_patches):
        """__copy__ should return a new HashableEvent with the same attributes."""
        import copy

        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a, mod=0)
        copied_event = copy.copy(event)
        assert copied_event['key'] == pygame.K_a
        assert copied_event['mod'] == 0

    def test_deep_copy(self, mock_pygame_patches):
        """__deepcopy__ should return a new HashableEvent (delegates to __copy__)."""
        import copy

        event = HashableEvent(pygame.MOUSEMOTION, pos=(10, 20), rel=(1, 2))
        deep_copied_event = copy.deepcopy(event)
        assert deep_copied_event['pos'] == (10, 20)
        assert deep_copied_event['rel'] == (1, 2)

    def test_reduce_returns_tuple(self, mock_pygame_patches):
        """__reduce__ should return a picklable tuple."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_a)
        reduced = event.__reduce__()
        assert isinstance(reduced, tuple)
        assert reduced[0] is HashableEvent

    def test_setstate_raises_type_error(self, mock_pygame_patches):
        """__setstate__ has a bug: it hashes self.__dict__ (a dict, unhashable).

        BUG: __setstate__ uses hash((self.type, self.__dict__)) but __init__ uses
        hash((self.type, tuple(self.__dict__.keys()))). The dict is not hashable,
        so __setstate__ always raises TypeError.
        """
        event = HashableEvent(pygame.USEREVENT)
        state = {'type': pygame.KEYDOWN, 'key': pygame.K_a, 'mod': 0}
        with pytest.raises(TypeError, match='unhashable type'):
            event.__setstate__(state)


class TestHashableEventWithVariousTypes:
    """Test HashableEvent with different pygame event types."""

    def test_mouse_motion_event(self, mock_pygame_patches):
        """HashableEvent should work with MOUSEMOTION type."""
        event = HashableEvent(pygame.MOUSEMOTION, pos=(100, 200), rel=(5, -3), buttons=(1, 0, 0))
        assert event.type == pygame.MOUSEMOTION
        assert event.pos == (100, 200)
        assert event.rel == (5, -3)
        assert event.buttons == (1, 0, 0)

    def test_keyboard_event(self, mock_pygame_patches):
        """HashableEvent should work with KEYDOWN type."""
        event = HashableEvent(pygame.KEYDOWN, key=pygame.K_SPACE, mod=pygame.KMOD_CTRL, unicode=' ')
        assert event.type == pygame.KEYDOWN
        assert event.key == pygame.K_SPACE
        assert event.mod == pygame.KMOD_CTRL

    def test_user_event_with_custom_attributes(self, mock_pygame_patches):
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
